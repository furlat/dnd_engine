"""Real clothed body pixels disappear beneath bare and hatch portal openings."""

from dataclasses import replace

import numpy as np
import pygame
import pytest

from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.motion import bind_motion
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.portal_draw import clip_portal_bodies
from game.projection import Camera, project_screen
from game.scene import load_scene_media, scene_actors, scene_draw_commands
from tests.game.portal_scenarios import portal_history


@pytest.fixture(scope="module")
def graphics():
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((640, 480))
        yield
        pygame.quit()


@pytest.fixture(scope="module", params=("bare-walk", "hatch-open"))
def crossing(request, graphics):
    history = portal_history(program=request.param)
    data = load_animation_data()
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views["traveler"])))
    for root in roots:
        motion = bind_motion(state, root, data)
        groups = ([reaction.choreography for reaction in motion.reactions] if motion is not None
                  else [bind_choreography(state, root, data)])
        for group in groups:
            if not group.portals:
                continue
            cue, = group.portals
            actor = next(actor for actor in scene_actors(group.before, data, {})
                         if actor.contact.actor_uuid == cue.actor_uuid)
            media = load_scene_media((actor,), data)
            return data, group, cue, actor, media
        state = reduce_lineage(state, root)
    raise AssertionError("Native portal recording contains no crossing")


@pytest.mark.parametrize("quadrant", range(4))
def test_falling_body_clips_at_ground_without_erasing_upper_body_or_mutating_cached_art(crossing, quadrant):
    data, group, cue, actor, media = crossing
    assert cue.departure is not None
    elapsed = cue.fall_start_ms + .6 * (cue.disappear_ms - cue.fall_start_ms)
    sampled = sample_choreography(group, elapsed)
    contact = next(contact for contact in sampled.contacts if contact.actor_uuid == cue.actor_uuid)
    assert contact.body_lift_px < 0 and cue.actor_uuid not in sampled.hidden_actors
    camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus(cue.departure.grid)
    commands = scene_draw_commands((replace(actor, contact=contact),), data, media, camera, 0)
    source, = (command for command in commands if command.evidence[6] == "actor")
    original_pixels = pygame.image.tobytes(source.surface, "RGBA")
    cached_pixels = {key: pygame.image.tobytes(surface, "RGBA") for key, surface in media.items()}
    clipped = clip_portal_bodies(commands, camera, sampled.portals, sampled.hidden_actors)
    body, = (command for command in clipped if command.evidence[6] == "actor")
    without_diagnostics = clip_portal_bodies(tuple(command._replace(evidence=()) for command in commands),
        camera, sampled.portals, sampled.hidden_actors)
    assert [(row.role, row.owner, row.destination, pygame.image.tobytes(row.surface, "RGBA"))
            for row in without_diagnostics] == [
        (row.role, row.owner, row.destination, pygame.image.tobytes(row.surface, "RGBA")) for row in clipped]
    assert not any(command.evidence[6] == "actor_shadow" for command in clipped)
    before = pygame.surfarray.array_alpha(source.surface)
    after = pygame.surfarray.array_alpha(body.surface)
    ground = project_screen(cue.departure.grid, camera, elevation_steps=cue.departure.elevation_steps)
    ys = np.arange(source.surface.height)[None, :] + source.destination[1] + .5 - ground[1]
    below_opening = np.broadcast_to(ys > cue.art.entrance_aperture.half_height_px * cue.art.scale * camera.zoom, before.shape)
    upper_body = np.broadcast_to(ys < 0, before.shape)
    assert np.any(before[below_opening] > 0), "This pose must actually descend below the front edge."
    assert not np.any(after[below_opening]), "Body pixels below the opening cannot paint over the floor."
    assert np.any(before[upper_body] > 0), "A visible upper body must remain above ground."
    np.testing.assert_array_equal(after[upper_body], before[upper_body])
    assert 0 < np.count_nonzero(after) < np.count_nonzero(before)
    assert pygame.image.tobytes(source.surface, "RGBA") == original_pixels
    assert {key: pygame.image.tobytes(surface, "RGBA") for key, surface in media.items()} == cached_pixels
    held = clip_portal_bodies(commands, camera, ((cue, cue.fall_start_ms),), frozenset())
    assert pygame.image.tobytes(next(command.surface for command in held if command.evidence[6] == "actor"), "RGBA") == original_pixels
    sought = clip_portal_bodies(commands, camera, sampled.portals, sampled.hidden_actors)
    assert pygame.image.tobytes(next(command.surface for command in sought if command.evidence[6] == "actor"), "RGBA") == pygame.image.tobytes(body.surface, "RGBA")


@pytest.mark.parametrize("quadrant", range(4))
def test_body_fully_disappears_before_transfer_then_emerges_from_exit(crossing, quadrant):
    data, group, cue, actor, media = crossing
    assert cue.departure is not None and cue.arrival is not None
    counts = []
    for elapsed in (cue.disappear_ms - .001, cue.arrival_ms,
                    cue.arrival_ms + (cue.settled_ms - cue.arrival_ms) * .5, cue.settled_ms):
        sampled = sample_choreography(group, elapsed)
        contact = next(contact for contact in sampled.contacts if contact.actor_uuid == cue.actor_uuid)
        camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus(contact.grid)
        commands = scene_draw_commands((replace(actor, contact=contact),), data, media, camera, 0)
        clipped = clip_portal_bodies(commands, camera, sampled.portals, sampled.hidden_actors)
        body, = (command for command in clipped if command.evidence[6] == "actor")
        counts.append(np.count_nonzero(pygame.surfarray.array_alpha(body.surface)))
        if elapsed < cue.settled_ms:
            assert not any(command.evidence[6] == "actor_shadow" for command in clipped)
        else:
            original, = (command for command in commands if command.evidence[6] == "actor")
            assert pygame.image.tobytes(body.surface, "RGBA") == pygame.image.tobytes(original.surface, "RGBA")
    assert counts[0] == counts[1] == 0, "No head pixels should pop off/on at transfer."
    assert 0 < counts[2] < counts[3], "The body must emerge progressively through the exit opening."
