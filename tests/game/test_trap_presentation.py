"""Saved trap/control lineages use the ordinary painter and historical clock."""

import os
from uuid import UUID

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from game.animation_data import load_animation_data
from game.app import draw_frame
from game.assets import SurfaceCache, load_catalog
from game.choreography import bind_choreography
from game.choreography_draw import load_choreography_media, load_motion_media
from game.motion import bind_motion
from game.playback_frame import sample_playback_frame
from game.player_facts import ActionFact, MovementFact, SpatialEffectStateFact
from game.player_reduction import reduce_lineage, stage_lineage
from game.projection import Camera, camera_pose
from game.scene import load_scene_media, scene_actors
from game.world_animation import sample_world_transitions, world_transitions
from tests.game.player_helpers import player_history
from tests.game.test_trap_player_replay import recorded_traps
from tests.game.trap_scenarios import trap_history


@pytest.fixture(scope="module")
def histories():
    return {detected: trap_history(detected=detected) for detected in (False, True)}


@pytest.fixture(scope="module")
def rendering():
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    catalog = load_catalog()
    yield screen, catalog, SurfaceCache(catalog), load_animation_data(), pygame.font.Font(None, 20)
    pygame.quit()


def selected(history, role, kind, occurrence=0):
    before, roots = player_history(history, role=role)
    for root in roots:
        if isinstance(root.root.fact, kind):
            if occurrence == 0:
                return before, root
            occurrence -= 1
        before = reduce_lineage(before, root)
    raise AssertionError("Recorded scenario has no requested action")


def drawn(frame, camera, rendering):
    screen, catalog, cache, _, _ = rendering
    evidence = draw_frame(screen, frame.displayed, catalog, cache, camera, 0,
        show_grid=False, show_debug=False, mouse_position=None, collect_evidence=True,
        extra_commands=frame.commands, world_transitions=frame.world_transitions)
    assert evidence is not None and evidence.matches
    return evidence.actual_draws


@pytest.mark.parametrize("detected", (False, True))
@pytest.mark.parametrize("role", ("walker", "operator"))
def test_entry_plays_damage_and_received_deployment_after_arrival_in_four_views(histories, rendering, detected, role):
    screen, _, _, data, font = rendering
    before, root = selected(histories[detected], role, MovementFact)
    motion = bind_motion(before, root, data)
    assert motion is not None
    reaction, = motion.reactions
    assert reaction.start_ms == motion.legs[-1].end_ms
    assert reaction.contact.grid == (5, 3)
    assert reaction.end_ms >= reaction.start_ms + 250, "the head must retain all seven deployment poses"
    assert len(reaction.choreography.damage) == 1 and not reaction.choreography.gaps
    actor = UUID(motion.actor.actor_uuid)
    rows = {}
    body_media = load_scene_media(scene_actors(stage_lineage(before, root), data, {}), data, body_rows=rows)
    reaction_media = load_motion_media(motion, data, body_rows=rows)
    after = reduce_lineage(before, root)
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus((5, 3))
        def frame(at):
            return sample_playback_frame(before, after, data, at, at, camera, {}, body_media, font, font,
                motion=motion, reaction_media=reaction_media)
        pending = frame(reaction.start_ms - 1)
        pending_rows = [row for row in drawn(pending, camera, rendering) if len(row) > 6 and row[6] == "spatial_effect"]
        assert len(pending_rows) == int(detected and role == "walker")
        assert pending.displayed.actors[actor].normal_hp == before.actors[actor].normal_hp
        for offset, expected_frame in ((0, 0), (125, 3), (300, 6)):
            sample = frame(reaction.start_ms + offset)
            effect, = (row for row in drawn(sample, camera, rendering) if len(row) > 6 and row[6] == "spatial_effect")
            assert effect[2] == f"spikes.{camera_pose('east', quadrant)}.{expected_frame}"
            assert effect[1] == (5, 3) and effect[8] == before.tiles[(5, 3)].elevation_steps
            assert sample.actors and next(row for row in sample.actors if row.contact.actor_uuid == str(actor)).contact.grid == (5, 3)
            assert sample.displayed.actors[actor].last_visual_position == (5, 3)
        reached = frame(reaction.start_ms + 125)
        assert reached.displayed.actors[actor].normal_hp == after.actors[actor].normal_hp
        assert frame(reaction.start_ms - 1).displayed == pending.displayed


@pytest.mark.parametrize("role", ("walker", "operator"))
@pytest.mark.parametrize("occurrence", (0, 1))
def test_lever_and_spikes_share_original_contact_anchor_and_seek_back(histories, rendering, role, occurrence):
    screen, _, _, data, font = rendering
    before, root = selected(histories[False], role, ActionFact, occurrence)
    group = bind_choreography(before, root, data)
    cue, = group.body_actions
    assert cue.effect_ms == pytest.approx(250)
    assert group.complete_ms >= cue.effect_ms + 250
    assert not group.gaps
    rows = {}
    body_media = load_scene_media(scene_actors(stage_lineage(before, root), data, {}), data, body_rows=rows)
    media = load_choreography_media(group, body_rows=rows)
    walker = histories[False].views["walker"].initialization.observer_uuid
    starting_hp = before.actors[walker].normal_hp
    assert group.after.actors[walker].normal_hp == starting_hp - (4 if occurrence else 0)
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus((5, 3))
        def frame(at):
            return sample_playback_frame(before, group.after, data, at, at, camera, {}, body_media, font, font,
                choreography=group, choreography_media=media)
        for at, lever_frame, spike_frame in ((249, 0, 6), (250, 0, 6), (375, 3, 3), (550, 6, 0), (249, 0, 6)):
            sample = frame(at)
            evidence = drawn(sample, camera, rendering)
            if occurrence:
                lever_frame, spike_frame = 6 - lever_frame, 6 - spike_frame
                assert sample.displayed.actors[walker].last_visual_position == (5, 3)
                assert sample.displayed.actors[walker].normal_hp == starting_hp - (4 if at >= 250 else 0)
            lever, = (row for row in evidence if row[0] == cue.interaction_object_uuid)
            spike, = (row for row in evidence if len(row) > 6 and row[6] == "spatial_effect")
            assert lever[2] == f"lever.{camera_pose('east', quadrant)}.{lever_frame}"
            assert spike[2] == f"spikes.{camera_pose('east', quadrant)}.{spike_frame}"


@pytest.mark.parametrize("payload", ("poison-damage", "poisoned"))
def test_explicit_received_poison_content_selects_coated_sheet(rendering, payload):
    screen, catalog, cache, data, font = rendering
    before, root = selected(trap_history(payload=payload), "walker", MovementFact)
    motion = bind_motion(before, root, data)
    assert motion is not None
    rows = {}
    body_media = load_scene_media(scene_actors(stage_lineage(before, root), data, {}), data, body_rows=rows)
    reactions = load_motion_media(motion, data, body_rows=rows)
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus((5, 3))
        sample = sample_playback_frame(before, reduce_lineage(before, root), data, motion.complete_ms,
            motion.complete_ms, camera, {}, body_media, font, font, motion=motion, reaction_media=reactions)
        effect, = (row for row in drawn(sample, camera, rendering) if len(row) > 6 and row[6] == "spatial_effect")
        assert effect[2] == f"spikes.coated.{camera_pose('east', quadrant)}.6"


def test_unseen_toggle_reacquisition_uses_received_endpoint_without_replaying_motion(recorded_traps, rendering):
    history, identity, _ = recorded_traps
    before, roots = player_history(history, role="scout")
    for root in roots:
        after = reduce_lineage(before, root)
        assert before.senses is not None and after.senses is not None
        old = before.senses.spatial_effects.get(identity)
        new = after.senses.spatial_effects.get(identity)
        if (old is not None and new is not None and old.trap_state is not new.trap_state
                and not any(isinstance(row.fact, SpatialEffectStateFact) for row in root.events)):
            break
        before = after
    else:
        pytest.fail("Expected remembered trap reacquisition after an unseen toggle")
    transitions = sample_world_transitions(world_transitions(before, ((250, after),)), 250)
    assert not transitions
    screen, catalog, cache, _, _ = rendering
    camera = Camera(viewport=screen.get_size()).with_focus((3, 1))
    evidence = draw_frame(screen, after, catalog, cache, camera, 0,
        show_grid=False, show_debug=False, mouse_position=None, collect_evidence=True,
        world_transitions=transitions)
    assert evidence is not None
    effect, = (row for row in evidence.actual_draws if len(row) > 6 and row[6] == "spatial_effect")
    assert effect[2] == f"spikes.{camera_pose('east', 0)}.6"


def test_observed_spikes_finish_motion_without_an_actor_animation(recorded_traps, rendering):
    history, identity, _ = recorded_traps
    before, roots = player_history(history, role="scout")
    screen, _, _, data, font = rendering
    for root in roots:
        after = reduce_lineage(before, root)
        changes = [row.fact for row in root.events if isinstance(row.fact, SpatialEffectStateFact)
                   and row.fact.previous_state.value == "activated" and row.fact.state.value == "deactivated"]
        if changes:
            break
        before = after
    else:
        pytest.fail("Expected recorded native lowering")
    group = bind_choreography(before, root, data)
    assert not group.body_actions and not group.damage and not group.gaps
    assert group.complete_ms == pytest.approx(250)
    assert before.senses is not None and identity in before.senses.spatial_effects
    rows = {}
    bodies = load_scene_media(scene_actors(before, data, {}), data, body_rows=rows)
    media = load_choreography_media(group, body_rows=rows)
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus((3, 1))
        for at, expected, complete in ((0, 6, False), (125, 3, False), (250, 0, True), (125, 3, False)):
            frame = sample_playback_frame(before, after, data, at, at, camera, {}, bodies, font, font,
                choreography=group, choreography_media=media)
            effect, = (row for row in drawn(frame, camera, rendering)
                       if len(row) > 6 and row[6] == "spatial_effect")
            assert effect[2] == f"spikes.{camera_pose('east', quadrant)}.{expected}"
            assert frame.complete is complete
