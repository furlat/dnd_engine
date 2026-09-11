"""Native forced lineages in; authored bodies, placed pixels and historical HP out."""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from uuid import UUID

import numpy as np
import pygame
import pytest

from devtools.animation_review.cases import load_cases, produce
from dnd.core.life_types import LifeState
from game.animation import ActorContact, body_clip
from game.animation_data import load_animation_data
from game.animation_draw import AnimationDrawCommand, BodyRows
from game.animation_types import AnimationData
from game.app import draw_frame
from game.assets import SurfaceCache, load_catalog
from game.choreography import BoundChoreography, bind_choreography, sample_choreography
from game.choreography_draw import ChoreographyMedia, load_choreography_media
from game.feedback import choreography_feedback
from game.playback_frame import PlaybackFrame, sample_playback_frame
from game.projection import Camera, TILE_WIDTH, project_screen
from game.scene import load_scene_media, scene_actors


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data(rig_files=(Path("game/data/rigs/goblin01.json"),))


@pytest.fixture(scope="module")
def fonts(data: AnimationData) -> Iterator[tuple[pygame.font.Font, pygame.font.Font]]:
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((960, 640))
        number, badge = (pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                         for style in (data.number_style, data.badge_style))
        yield number, badge
        pygame.quit()


@dataclass(frozen=True)
class PlaybackScene:
    group: BoundChoreography
    bodies: BodyRows
    media: ChoreographyMedia


def load_scene(case_id: str, data: AnimationData) -> PlaybackScene:
    sequence = produce(next(case for case in load_cases() if case.id == case_id))
    lineage, = sequence.lineages
    group = bind_choreography(sequence.before, lineage, data)
    assert group.gaps == (), (case_id, group.gaps)
    return PlaybackScene(group, load_scene_media(scene_actors(sequence.before, data, {}), data),
                         load_choreography_media(group))


def frame_at(scene: PlaybackScene, data: AnimationData, fonts: tuple[pygame.font.Font, pygame.font.Font],
             time: float, camera: Camera) -> PlaybackFrame:
    group = scene.group
    return sample_playback_frame(group.before, group.after, data, time, 5000 + time,
        camera, {}, scene.bodies, *fonts, choreography=group, choreography_media=scene.media,
        feedback=choreography_feedback(group, data, 5000))


def actor_body(frame: PlaybackFrame, identity: str) -> AnimationDrawCommand:
    command, = (row for row in frame.commands if row[4][0] == identity and row[4][6] == "actor")
    assert command[1].get_bounding_rect().width > 0
    return command


def actor_contact(frame: PlaybackFrame, identity: str) -> ActorContact:
    return next(actor.contact for actor in frame.actors if actor.contact.actor_uuid == identity)


def body_pixels(command: AnimationDrawCommand) -> bytes:
    return pygame.image.tobytes(command[1], "RGBA")


@pytest.mark.parametrize("case_id", ["shove-success", "shove-partly-blocked", "shove-goblin", "telekinesis-displacement"])
def test_native_displacement_plays_brace_travel_release_and_idle_without_latest_leaking(
    data: AnimationData, fonts: tuple[pygame.font.Font, pygame.font.Font], case_id: str,
) -> None:
    scene = load_scene(case_id, data)
    group = scene.group
    cue, = group.forced_movement
    identity = cue.actor.actor_uuid
    target = UUID(identity)
    assert not group.nodes and not group.damage
    clip = body_clip(data, cue.actor, "TakeDamage")
    frame_ms = 1000 / clip.fps
    start_ms = 7 * 1000 / 12 if group.shoves else 0
    assert cue.start_ms == pytest.approx(start_ms)
    assert cue.travel_start_ms == pytest.approx(start_ms + 3 * frame_ms)
    assert cue.travel_end_ms - cue.travel_start_ms == pytest.approx(420)
    assert cue.body_end_ms == pytest.approx(start_ms + (clip.frames - 1) * frame_ms + 420)
    assert group.after.actors[target].last_visual_position != cue.actor.grid
    halfway = cue.travel_start_ms + 210
    end = cue.points[-1].grid
    expected = tuple(a + .75 * (b - a) for a, b in zip(cue.actor.grid, end))
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=(960, 640)).with_focus((4.5, 3.5))
        first = frame_at(scene, data, fonts, start_ms, camera)
        brace = frame_at(scene, data, fonts, cue.travel_start_ms, camera)
        travelling = frame_at(scene, data, fonts, halfway, camera)
        end_travel = frame_at(scene, data, fonts, cue.travel_end_ms, camera)
        released = frame_at(scene, data, fonts, cue.travel_end_ms + frame_ms + .001, camera)
        assert actor_body(first, identity)[4][8:10] == ("TakeDamage", 0)
        for frame in (brace, travelling, end_travel):
            assert actor_body(frame, identity)[4][8:10] == ("TakeDamage", 3)
        assert body_pixels(actor_body(brace, identity)) == body_pixels(actor_body(travelling, identity))
        assert actor_contact(travelling, identity).grid == pytest.approx(expected)
        assert actor_contact(end_travel, identity).grid == end
        assert actor_body(released, identity)[4][8:10] == ("TakeDamage", 4)
        assert travelling.displayed.actors[target] == group.before.actors[target]
        assert not travelling.complete
        # Latest has already settled; an absolute paused presentation seek is
        # still byte-identical and never consumes the retained lineage.
        paused = frame_at(scene, data, fonts, halfway, camera)
        assert paused.displayed == travelling.displayed
        assert paused.actors == travelling.actors
        assert [(row[0], row[2:], body_pixels(row)) for row in paused.commands] == [
            (row[0], row[2:], body_pixels(row)) for row in travelling.commands]
        completed = frame_at(scene, data, fonts, group.complete_ms, camera)
        assert completed.complete and completed.displayed == group.after
        assert actor_contact(completed, identity).grid == end
        assert actor_body(completed, identity)[4][8] == "Idle"
        idle = sample_playback_frame(group.after, None, data, 0, 5000 + group.complete_ms,
            camera, completed.facings, scene.bodies, *fonts, positions=completed.positions)
        assert actor_body(completed, identity)[2:] == actor_body(idle, identity)[2:]
        assert body_pixels(actor_body(completed, identity)) == body_pixels(actor_body(idle, identity))
        if group.shoves:
            source = group.shoves[0].source.actor_uuid
            assert actor_body(first, source)[4][8:10] == ("Kick", 7)
            before_contact = frame_at(scene, data, fonts, start_ms - .001, camera)
            assert actor_body(before_contact, identity)[4][8] == "Idle"


@pytest.mark.parametrize(("case_id", "label"), [("shove-resisted", "Resisted"), ("shove-blocked", "Blocked")])
def test_native_no_displacement_keeps_recipient_idle_and_displays_original_outcome(
    data: AnimationData, fonts: tuple[pygame.font.Font, pygame.font.Font], case_id: str, label: str,
) -> None:
    scene = load_scene(case_id, data)
    group = scene.group
    shove, = group.shoves
    assert not group.forced_movement and not group.damage
    tracks = choreography_feedback(group, data, 5000)
    assert [track.label for track in tracks] == [label]
    camera = Camera(viewport=(960, 640)).with_focus((4.5, 3))
    for time in (0, shove.contact_ms, group.complete_ms):
        frame = frame_at(scene, data, fonts, time, camera)
        assert actor_contact(frame, shove.target.actor_uuid).grid == shove.target.grid
        assert actor_body(frame, shove.target.actor_uuid)[4][8] == "Idle"
        assert actor_contact(frame, shove.target.actor_uuid).hp == shove.target.hp
        badges = tuple(row for row in frame.commands if row[4][6] == "floating_number")
        if time == 0:
            assert not badges
        elif time == shove.contact_ms:
            assert len(badges) == 1 and badges[0][1].get_bounding_rect().width > 0
    assert group.complete_ms == shove.body_end_ms


def test_native_spatial_entries_apply_each_damage_once_at_the_reached_cell(
    data: AnimationData, fonts: tuple[pygame.font.Font, pygame.font.Font],
) -> None:
    scene = load_scene("shove-spikes", data)
    group = scene.group
    cue, = group.forced_movement
    assert len(group.damage) == 2
    assert [damage.applied_damage for damage in group.damage] == [5, 7]
    assert [damage.contact.grid for damage in group.damage] == [(2, 11), (2, 12)]
    camera = Camera(viewport=(960, 640)).with_focus((2, 11))
    identity = cue.actor.actor_uuid
    before_hp = frame_at(scene, data, fonts, group.damage[0].timing.hp_ms - .001, camera)
    assert actor_contact(before_hp, identity).hp == 40
    for damage, hp in zip(group.damage, (35, 28)):
        reached = frame_at(scene, data, fonts, damage.timing.start_ms, camera)
        assert actor_contact(reached, identity).grid == pytest.approx(damage.contact.grid)
        frame = frame_at(scene, data, fonts, damage.timing.hp_ms + .001, camera)
        assert frame.shown_hp[identity] == actor_contact(frame, identity).hp == hp
        assert actor_body(frame, identity)[4][8] == "TakeDamage"
        assert frame_at(scene, data, fonts, damage.timing.hp_ms + .001, camera).shown_hp == frame.shown_hp
    assert group.after.actors[UUID(identity)].normal_hp == 28
    assert sample_choreography(group, 0).displayed == group.before


def test_lethal_entry_stays_at_native_reached_cell_across_completion_and_idle(
    data: AnimationData, fonts: tuple[pygame.font.Font, pygame.font.Font],
) -> None:
    scene = load_scene("shove-spikes-lethal", data)
    group = scene.group
    cue, = group.forced_movement
    damage, = group.damage
    identity = cue.actor.actor_uuid
    assert damage.contact.grid == cue.points[-1].grid == (2, 11)
    assert group.after.actors[UUID(identity)].normal_hp == -1
    assert group.after.actors[UUID(identity)].life_state is LifeState.DEAD
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=(960, 640)).with_focus((2, 11))
        dying = frame_at(scene, data, fonts, damage.timing.start_ms + .001, camera)
        assert actor_body(dying, identity)[4][8:10] == ("Die", 0)
        completed = frame_at(scene, data, fonts, group.complete_ms, camera)
        idle = sample_playback_frame(group.after, None, data, 0, 5000 + group.complete_ms,
            camera, completed.facings, scene.bodies, *fonts, positions=completed.positions)
        for frame in (dying, completed, idle):
            assert actor_contact(frame, identity).grid == (2, 11)
            assert actor_contact(frame, identity).hp == -1
        assert completed.displayed == idle.displayed == group.after
        assert actor_body(completed, identity)[2:] == actor_body(idle, identity)[2:]
        assert body_pixels(actor_body(completed, identity)) == body_pixels(actor_body(idle, identity))


@pytest.mark.parametrize(("case_id", "height"), [("shove-stairs-up", 1.5), ("shove-stairs-down", .5)])
def test_stair_displacement_projects_real_body_pixels_and_height_in_every_camera(
    data: AnimationData, fonts: tuple[pygame.font.Font, pygame.font.Font], case_id: str, height: float,
) -> None:
    scene = load_scene(case_id, data)
    cue, = scene.group.forced_movement
    identity = cue.actor.actor_uuid
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=(960, 640)).with_focus((16, 23), elevation_steps=1)
        frame = frame_at(scene, data, fonts, cue.travel_start_ms + 210, camera)
        contact = actor_contact(frame, identity)
        assert contact.elevation_steps == pytest.approx(height) and contact.body_lift_px == 0
        command = actor_body(frame, identity)
        rig = data.rigs[contact.rig_id]
        projected = project_screen(contact.grid, camera, elevation_steps=height)
        factor = contact.visual_scale * TILE_WIDTH / data.rig.TILE_W * camera.zoom
        assert command[2] == (round(projected[0] - command[1].width / 2),
                              round(projected[1] + rig.origin_y_from_ground * factor - command[1].height))
        assert command[4][8:10] == ("TakeDamage", 3)
        assert np.count_nonzero(pygame.surfarray.array_alpha(command[1]) >= 250) > 100


@pytest.mark.parametrize("case_id", ["shove-stairs-up", "shove-stairs-down"])
@pytest.mark.xfail(strict=True, reason=(
    "Existing terrain occlusion: up q0/q3 exposes 66/31 body pixels; "
    "down q0..3 exposes 1/5/54/93 at half travel. Contact/height/media pass separately."
))
def test_stair_map_keeps_displaced_recipient_readable_in_every_camera(
    data: AnimationData, fonts: tuple[pygame.font.Font, pygame.font.Font], case_id: str, tmp_path: Path,
) -> None:
    scene = load_scene(case_id, data)
    cue, = scene.group.forced_movement
    identity = cue.actor.actor_uuid
    catalog = load_catalog()
    cache = SurfaceCache(catalog)
    screen = pygame.display.get_surface()
    assert screen is not None
    visibility: list[tuple[int, int, int]] = []
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus((16, 23), elevation_steps=1)
        frame = frame_at(scene, data, fonts, cue.travel_start_ms + 210, camera)
        command = actor_body(frame, identity)
        draw_frame(screen, frame.displayed, catalog, cache, camera, 1, show_grid=False,
                   mouse_position=None, extra_commands=frame.commands, show_debug=False)
        with_actor = pygame.surfarray.array3d(screen)
        pygame.image.save(screen, tmp_path / f"{case_id}-q{quadrant}.png")
        draw_frame(screen, frame.displayed, catalog, cache, camera, 1, show_grid=False,
                   mouse_position=None, extra_commands=tuple(row for row in frame.commands if row[4][0] != identity),
                   show_debug=False)
        without_actor = pygame.surfarray.array3d(screen)
        body = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        body.blit(command[1], command[2])
        opaque = pygame.surfarray.array_alpha(body) >= 250
        # The four images retain the visible exception as evidence. This
        # criterion concerns readability, not a demand to draw over all terrain.
        visibility.append((quadrant, int(np.count_nonzero(opaque)),
                           int(np.count_nonzero(opaque & np.any(with_actor != without_actor, axis=2)))))
    assert all(visible > 100 for _, _, visible in visibility), (visibility, tmp_path)
