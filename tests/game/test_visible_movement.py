"""Actual subjective packets preserve sight changes within a complete walk."""


import pygame
import pytest

from game.animation_draw import LoadedBodyRows
from game.animation_data import load_animation_data
from dnd.core.life_types import LifeState
from tests.game.scenarios import movement_with_paralysis
from game.motion import bind_motion, sample_motion
from game.playback_frame import sample_playback_frame
from game.player_facts import MovementFact, StepFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage, stage_lineage
from game.projection import Camera
from game.scene import load_scene_media, scene_actors
from game.choreography_draw import load_motion_media
from tests.game.visibility_scenarios import visibility_history


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


def player_views(history):
    return {role: decode_player_sequence(encode_player_sequence(project_sequence(sequence)))
            for role, sequence in history.views.items()}


def test_paired_doorway_walk_keeps_only_authorized_edges_and_same_root(data) -> None:
    views = player_views(visibility_history())
    observer_before, (observer_root,) = views["observer"]
    subject_before, (subject_root,) = views["subject"]
    assert observer_root.root.uuid == subject_root.root.uuid
    assert isinstance(observer_root.root.fact, MovementFact)
    mover = observer_root.root.fact.source_entity_uuid
    assert mover not in observer_before.actors
    assert observer_root.root.fact.path == () and observer_root.root.fact.start_position is None
    observed_steps = tuple(node.fact for node in observer_root.events if isinstance(node.fact, StepFact))
    assert [(step.from_position, step.to_position) for step in observed_steps] == [
        ((8, 6), (8, 7)), ((8, 7), (8, 8))]
    motion = bind_motion(observer_before, observer_root, data)
    own_motion = bind_motion(subject_before, subject_root, data)
    assert motion is not None and own_motion is not None
    assert motion.complete_ms == pytest.approx(data.movement_context.walkStepDurationMs * 2)
    assert own_motion.complete_ms == pytest.approx(data.movement_context.walkStepDurationMs * 6)
    latest = reduce_lineage(observer_before, observer_root)
    assert latest.senses is not None and mover not in latest.senses.entities
    earlier = sample_motion(motion, data, motion.complete_ms / 2)
    assert earlier.contact is not None and earlier.contact.grid == (8, 7)
    assert earlier.displayed is not None and earlier.displayed.senses is not None
    assert mover in earlier.displayed.senses.entities
    assert sample_motion(motion, data, motion.complete_ms / 2) == earlier
    assert sample_motion(motion, data, motion.complete_ms).contact is None
    assert mover not in observer_before.actors  # staging never changes the historical input

    pygame.init()
    try:
        pygame.display.set_mode((640, 480))
        body_rows: LoadedBodyRows = {}
        media = load_scene_media(scene_actors(stage_lineage(observer_before, observer_root), data, {}), data, body_rows=body_rows)
        load_motion_media(motion, data, body_rows=body_rows)
        fonts = tuple(pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                      for style in (data.number_style, data.badge_style))
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus((7, 7))
            active = sample_playback_frame(observer_before, latest, data, motion.complete_ms / 2,
                5000, camera, {}, media, *fonts, motion=motion)
            paused = sample_playback_frame(observer_before, latest, data, motion.complete_ms / 2,
                5000, camera, {}, media, *fonts, motion=motion)
            complete = sample_playback_frame(observer_before, latest, data, motion.complete_ms,
                5000, camera, {}, media, *fonts, motion=motion)
            body = tuple(command for command in active.commands
                         if command[4][0] == str(mover) and command[4][6] == "actor")
            assert len(body) == 1 and pygame.mask.from_surface(body[0][1]).count() > 0
            paused_body = next(command for command in paused.commands
                               if command[4][0] == str(mover) and command[4][6] == "actor")
            assert body[0][2] == paused_body[2]
            assert pygame.image.tobytes(body[0][1], "RGBA") == pygame.image.tobytes(paused_body[1], "RGBA")
            assert not any(command[4][0] == str(mover) and command[4][6] == "actor"
                           for command in complete.commands)
    finally:
        pygame.quit()


@pytest.mark.parametrize(("start", "end", "visible_at_end"), [
    ((8, 4), (8, 6), True),
    ((8, 8), (8, 10), False),
])
def test_isolated_disclosed_point_dwells_without_inventing_hidden_edge(data, start, end, visible_at_end) -> None:
    history = visibility_history(subject_position=start, route=(("subject", end),))
    before, (root,) = player_views(history)["observer"]
    assert isinstance(root.root.fact, MovementFact)
    assert not any(isinstance(node.fact, StepFact) for node in root.events)
    motion = bind_motion(before, root, data)
    assert motion is not None and motion.legs == ()
    assert motion.complete_ms == pytest.approx(data.movement_context.walkStepDurationMs)
    point = end if visible_at_end else start
    for elapsed in (0, motion.complete_ms / 2, motion.complete_ms - .001):
        sample = sample_motion(motion, data, elapsed)
        assert sample.contact is not None and sample.contact.grid == point
        assert sample.body is not None and sample.body.clip == "Idle"
    final = sample_motion(motion, data, motion.complete_ms)
    assert (final.contact is not None) is visible_at_end


def test_reacquisition_uses_new_actor_values_without_changing_earlier_head(data) -> None:
    history = visibility_history(subject_position=(8, 7),
        route=(("subject", (8, 4)), ("subject", (8, 7))), hidden_change_after=0)
    before, roots = player_views(history)["observer"]
    motions = []
    snapshots = []
    for root in roots:
        motion = bind_motion(before, root, data)
        if motion is not None:
            motions.append(motion)
            snapshots.append(sample_motion(motion, data, motion.complete_ms / 2))
        before = reduce_lineage(before, root)
    assert len(motions) == 2
    initial, reacquired = snapshots
    assert initial.displayed is not None and reacquired.displayed is not None
    identity = motions[0].actor_state.uuid
    first_actor, later_actor = initial.displayed.actors[identity], reacquired.displayed.actors[identity]
    assert later_actor.normal_hp < first_actor.normal_hp
    assert later_actor.visual_loadout != first_actor.visual_loadout
    assert sample_motion(motions[0], data, motions[0].complete_ms / 2) == initial


def test_one_complete_walk_keeps_two_visible_runs_and_a_geometry_free_hidden_interval(data) -> None:
    history = visibility_history(battlefield_id="battlefield.visibility_two_doors_open",
        observer_position=(3, 7), subject_position=(10, 1), route=(("subject", (10, 13)),), dash_before=True)
    before, roots = player_views(history)["observer"]
    movement = None
    for root in roots:
        if isinstance(root.root.fact, MovementFact):
            movement = root
            break
        before = reduce_lineage(before, root)
    assert movement is not None
    motion = bind_motion(before, movement, data)
    assert motion is not None
    assert [(leg.start, leg.end) for leg in motion.legs] == [
        ((10, 2), (10, 3)), ((10, 3), (10, 4)),
        ((10, 10), (10, 11)), ((10, 11), (10, 12))]
    step_ms = data.movement_context.walkStepDurationMs
    assert motion.complete_ms == pytest.approx(5 * step_ms)
    assert motion.legs[2].start_ms - motion.legs[1].end_ms == pytest.approx(step_ms)
    first = sample_motion(motion, data, step_ms)
    unseen = sample_motion(motion, data, 2.5 * step_ms)
    second = sample_motion(motion, data, 4 * step_ms)
    assert first.contact is not None and first.contact.grid == (10, 3)
    assert unseen.contact is None and unseen.body is None
    assert second.contact is not None and second.contact.grid == (10, 11)
    latest = reduce_lineage(before, movement)
    assert latest.senses is not None and motion.actor_state.uuid not in latest.senses.entities
    assert sample_motion(motion, data, step_ms) == first
    assert sample_motion(motion, data, 2.5 * step_ms) == unseen


@pytest.mark.parametrize("behavior", ["action.move", "action.jump"])
def test_opaque_attempt_keeps_visible_lethal_reaction_at_known_origin(data, behavior) -> None:
    history = movement_with_paralysis(5, 4, movement_behavior=behavior)
    spectator, (root,) = player_views(history)["reactor"]
    controlled, (own_root,) = player_views(history)["mover"]
    assert root.root.uuid == own_root.root.uuid
    assert isinstance(root.root.fact, MovementFact)
    assert not any(isinstance(node.fact, StepFact) for node in root.events)
    assert any(isinstance(node.fact, StepFact) for node in own_root.events)
    motion = bind_motion(spectator, root, data)
    own_motion = bind_motion(controlled, own_root, data)
    assert motion is not None and own_motion is not None
    assert len(motion.reactions) == 1 and not motion.legs
    reaction, = motion.reactions
    assert reaction.start_ms == 0 and reaction.contact.grid == (3, 3)
    for elapsed in (0, reaction.end_ms / 2, motion.complete_ms):
        sample = sample_motion(motion, data, elapsed)
        assert sample.contact is not None and sample.contact.grid == (3, 3)
        assert sample.lift_px == 0
    final = sample_motion(motion, data, motion.complete_ms)
    assert final.contact is not None and final.contact.life_state is LifeState.DEAD
    assert final.body is not None and final.body.clip == "Die"
    if behavior == "action.move":
        assert own_motion.reactions[0].start_ms > 0
        assert own_motion.reactions[0].contact.grid != reaction.contact.grid
