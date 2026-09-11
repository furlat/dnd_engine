"""Public movement budgets and full authored jump flights after engine teardown."""

from math import hypot
from pathlib import Path
import random

import pygame
import pytest

from dnd.actions import AttackEvent, JumpEvent, MovementEvent
from dnd.core.base_actions import ActionEvent
from dnd.core.events import EventPhase, EventQueue, StepMovementEvent
from dnd.core.life_types import LifeState
from game.animation import body_clip
from game.animation_data import load_animation_data
from game.animation_types import AnimationData
from game.motion import bind_motion, sample_motion
from game.playback_frame import sample_playback_frame
from game.presentation import reduce_lineage
from game.projection import Camera
from game.scene import load_scene_media, scene_actors
from tests.game.movement_scenarios import movement_history
from tests.game.scenarios import attack_history


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data(rig_files=(Path("game/data/rigs/goblin01.json"),))


@pytest.mark.parametrize(("route", "battlefield", "behavior", "boost", "cost"), [
    (((3, 3), (6, 3)), "battlefield.open_floor_bright", "action.move", "none", 15),
    (((3, 3), (5, 3), (5, 5), (3, 5)), "battlefield.open_floor_bright", "action.move", "none", 30),
    (((3, 3), (8, 3), (8, 8)), "battlefield.open_floor_bright", "action.move", "haste", 50),
    (((3, 3), (8, 3), (8, 8)), "battlefield.open_floor_bright", "action.move", "bonus-dash", 50),
    (((1, 1), (3, 1)), "battlefield.standard_hazards_open", "action.jump", "none", 10),
    (((8, 5), (8, 4)), "battlefield.elevation_proving_ground", "action.jump", "none", 5),
    (((8, 4), (8, 5)), "battlefield.elevation_proving_ground", "action.jump", "none", 5),
    (((5, 4), (8, 4)), "battlefield.elevation_proving_ground", "action.jump", "none", 15),
    (((33, 28), (35, 26)), "battlefield.visual_vertical_seam", "action.jump", "none", 10),
    (((13, 20), (14, 20)), "battlefield.visual_vertical_seam", "action.jump", "none", 5),
    (((14, 20), (13, 20)), "battlefield.visual_vertical_seam", "action.jump", "none", 5),
    (((16, 25), (16, 22)), "battlefield.visual_vertical_seam", "action.jump", "none", 15),
])
def test_native_routes_keep_actual_costs_conditions_terrain_and_replayable_steps(
    data: AnimationData, route: tuple[tuple[int, int], ...], battlefield: str,
    behavior: str, boost: str, cost: int,
) -> None:
    random_state = random.getstate()
    # Literal inputs are the same finite choices exposed by the catalog.
    assert behavior in ("action.move", "action.jump") and boost in ("none", "haste", "bonus-dash")
    captured = movement_history(route=route, battlefield_id=battlefield, behavior=behavior, boost=boost)
    before, roots = captured.before, captured.lineages
    assert random.getstate() == random_state
    mover = before.observer_uuid
    assert before.senses is not None and before.senses.position == route[0]
    assert before.actors[mover].items and before.actors[mover].equipment
    assert all(actor.normal_hp == 8 and actor.life_state is LifeState.ALIVE for actor in before.actors.values())
    if boost == "haste":
        assert "Haste" in {condition.name for condition in before.actors[mover].conditions}
    latest = before
    spent = 0
    motions = []
    for lineage in roots:
        assert EventQueue.get_event_by_uuid(lineage.root.uuid) is None
        assert not lineage.dispositions and lineage.root.parent_lineage is None
        assert all(event.phase is EventPhase.COMPLETION for event in lineage.events)
        identities = {event.lineage_uuid for event in lineage.events}
        assert all(event.parent_lineage in identities for event in lineage.events if event is not lineage.root)
        assert all(child in identities for event in lineage.events for child in event.children_lineages)
        motion = bind_motion(latest, lineage, data)
        after = reduce_lineage(latest, lineage)
        if isinstance(lineage.root, (MovementEvent, JumpEvent)):
            assert motion is not None and motion.reactions == ()
            motions.append(motion)
            steps = tuple(event for event in lineage.events if isinstance(event, StepMovementEvent))
            assert steps and all(step.committed and step.parent_lineage == lineage.root.lineage_uuid for step in steps)
            spent += sum(step.movement_cost for step in steps)
            end = sample_motion(motion, data, motion.complete_ms)
            assert end.contact.grid == lineage.root.end_position and end.contact.body_lift_px == 0
            assert end.contact.elevation_steps == after.tiles[lineage.root.end_position].elevation_steps
            assert sample_motion(motion, data, 0).contact.grid == lineage.root.start_position
            if behavior == "action.move":
                expected_ms = sum(hypot(step.to_position[0] - step.from_position[0],
                                        step.to_position[1] - step.from_position[1])
                                  for step in steps) * data.movement_context.walkStepDurationMs
                assert motion.complete_ms == pytest.approx(expected_ms)
                assert motion.playback_speed == data.movement_context.walkPlaybackSpeed
        latest = after
    assert spent == cost and latest.senses is not None and latest.senses.position == route[-1]
    assert len(motions) == len(route) - 1
    if boost == "bonus-dash":
        dash = roots[0]
        assert isinstance(dash.root, ActionEvent)
        assert dash.root.behavior_id == "action.dash"
        assert [(cost.cost_type, cost.cost) for cost in dash.root.costs] == [("bonus_actions", 1)]
        assert "Dashing" in {condition.name for condition in latest.actors[mover].conditions}
    if behavior == "action.jump":
        motion, = motions
        context = data.movement_context
        distance = hypot(route[-1][0] - route[0][0], route[-1][1] - route[0][1])
        duration = min(context.jumpMaxDurationMs, max(context.jumpMinDurationMs,
                       context.jumpBaseDurationMs + distance * context.jumpPerCellDurationMs))
        arc = min(context.jumpArcMaxPx, context.jumpArcBasePx + distance * context.jumpArcPerCellPx)
        assert motion.complete_ms == pytest.approx(duration)
        middle = sample_motion(motion, data, duration / 2)
        assert middle.contact.grid == tuple((start + end) / 2 for start, end in zip(route[0], route[-1]))
        assert middle.lift_px == arc > 0
        assert middle.contact.elevation_steps == pytest.approx(
            (before.tiles[route[0]].elevation_steps + before.tiles[route[-1]].elevation_steps) / 2)
        if battlefield == "battlefield.standard_hazards_open":
            assert before.tiles[(2, 1)].walking_cost == 0
            assert middle.contact.grid == (2, 1) and middle.lift_px > 0
        if route == ((33, 28), (35, 26)):
            assert before.tiles[(34, 27)].surface.base_material.value == "water"
            assert before.tiles[(34, 27)].walking_cost == 0
            assert all(before.tiles[bank].surface.base_material.value != "water" for bank in route)
            assert middle.contact.grid == (34, 27) and middle.lift_px > 0
        # No intermediate tile crossing becomes a landing or a fresh arc.
        for leg in motion.legs[:-1]:
            crossing = sample_motion(motion, data, leg.end_ms)
            assert crossing.lift_px > 0 and not crossing.complete


@pytest.mark.parametrize(("seed", "maximum_hp", "survives"), [(17, 80, True), (5, 4, False)])
@pytest.mark.parametrize("destination", [(3, 1), (1, 3)])
def test_multicell_jump_resolves_its_actual_reaction_before_takeoff_or_stops_grounded(
    data: AnimationData, seed: int, maximum_hp: int, survives: bool, destination: tuple[int, int],
) -> None:
    captured = attack_history("weapon.longsword", seed, opportunity=True, whole_movement=True,
        maximum_hp=maximum_hp, movement_behavior="action.jump", destination=destination)
    before, lineage = captured.before, captured.lineages[0]
    assert isinstance(lineage.root, JumpEvent)
    motion = bind_motion(before, lineage, data)
    assert motion is not None
    reaction, = motion.reactions
    duration = data.movement_context.jumpBaseDurationMs + 2 * data.movement_context.jumpPerCellDurationMs
    arc = data.movement_context.jumpArcBasePx + 2 * data.movement_context.jumpArcPerCellPx
    held = sample_motion(motion, data, reaction.start_ms)
    assert reaction.start_ms == 0
    assert held.contact.grid == lineage.root.start_position
    assert held.lift_px == held.contact.body_lift_px == 0
    during = sample_motion(motion, data, (reaction.start_ms + reaction.end_ms) / 2)
    assert (during.contact.grid, during.lift_px) == (held.contact.grid, held.lift_px)
    final = sample_motion(motion, data, motion.complete_ms)
    after = reduce_lineage(before, lineage)
    if survives:
        assert motion.complete_ms == pytest.approx(duration + reaction.end_ms - reaction.start_ms)
        resumed = sample_motion(motion, data, reaction.end_ms)
        assert resumed.contact.grid == held.contact.grid and resumed.lift_px == held.lift_px
        midpoint_ms = reaction.end_ms + duration / 2
        midpoint = sample_motion(motion, data, midpoint_ms)
        assert midpoint.contact.grid == tuple((3 + end) / 2 for end in destination) and midpoint.lift_px == arc
        assert final.contact.grid == destination and final.contact.body_lift_px == 0
        count = body_clip(data, motion.actor, motion.clip).frames
        samples = [sample_motion(motion, data, reaction.end_ms + duration * (index + .5) / count)
                   for index in range(count)]
        assert [sample.body.frame for sample in samples] == list(range(count))
        assert all(sample.body.clip == motion.clip and sample.reaction is None for sample in samples)
    else:
        assert motion.complete_ms == reaction.end_ms
        assert final.contact.life_state is LifeState.DEAD
        assert (final.contact.grid, final.contact.body_lift_px) == (held.contact.grid, held.lift_px)
        assert after.senses is not None and after.senses.entities.get(lineage.root.source_entity_uuid) is None
        stopped_step, = (event for event in lineage.events
                         if isinstance(event, StepMovementEvent) and not event.committed)
        assert after.actors[lineage.root.source_entity_uuid].last_visual_position == stopped_step.from_position
        assert not motion.legs
        if stopped_step.path_index > 1:
            assert stopped_step.from_position != final.contact.grid
            assert any(event.committed and event.path_index < stopped_step.path_index
                       for event in lineage.events if isinstance(event, StepMovementEvent))
    assert sample_motion(motion, data, reaction.start_ms) == held


def test_multiple_native_opportunity_attacks_join_on_the_ground_before_one_jump(data: AnimationData) -> None:
    captured = attack_history("weapon.longsword", 17, opportunity=True, whole_movement=True,
        movement_behavior="action.jump", destination=(3, 1), watcher_positions=((4, 3), (2, 3)))
    before, lineage = captured.before, captured.lineages[0]
    assert isinstance(lineage.root, JumpEvent)
    native = tuple(event for event in lineage.events if isinstance(event, AttackEvent))
    assert len(native) == 2
    motion = bind_motion(before, lineage, data)
    assert motion is not None and len(motion.reactions) == len(native)
    assert [row.choreography.root_uuid for row in motion.reactions] == [event.uuid for event in native]
    elapsed = 0.0
    for reaction in motion.reactions:
        assert reaction.start_ms == elapsed
        for time in (reaction.start_ms, (reaction.start_ms + reaction.end_ms) / 2, reaction.end_ms - .001):
            sample = sample_motion(motion, data, time)
            assert sample.reaction is reaction.choreography
            assert sample.contact.grid == lineage.root.start_position
            assert sample.lift_px == sample.contact.body_lift_px == 0
            assert sample.body.clip != data.movement_context.jumpClip
        elapsed = reaction.end_ms
    takeoff = sample_motion(motion, data, elapsed)
    assert takeoff.reaction is None and takeoff.body.frame == 0
    assert takeoff.contact.grid == lineage.root.start_position and takeoff.lift_px == 0
    landed = sample_motion(motion, data, motion.complete_ms)
    assert landed.complete and landed.contact.grid == lineage.root.end_position and landed.lift_px == 0
    assert landed.contact.hp == reduce_lineage(before, lineage).actors[lineage.root.source_entity_uuid].normal_hp


@pytest.mark.parametrize(("battlefield", "route"), [
    ("battlefield.open_floor_bright", ((3, 3), (2, 3))),
    ("battlefield.open_floor_bright", ((3, 3), (6, 3))),
    ("battlefield.visual_vertical_seam", ((33, 28), (35, 26))),
    ("battlefield.visual_vertical_seam", ((13, 20), (14, 20))),
    ("battlefield.visual_vertical_seam", ((14, 20), (13, 20))),
])
def test_jump_draws_one_complete_clip_over_its_airtime_and_lands_without_a_camera_snap(
    data: AnimationData, battlefield: str, route: tuple[tuple[int, int], ...],
) -> None:
    captured = movement_history(route=route, battlefield_id=battlefield, behavior="action.jump")
    before, roots = captured.before, captured.lineages
    lineage, = roots
    after = reduce_lineage(before, lineage)
    motion = bind_motion(before, lineage, data)
    assert motion is not None
    identity = motion.actor.actor_uuid
    pygame.init()
    try:
        pygame.display.set_mode((960, 640))
        media = load_scene_media(scene_actors(before, data, {}), data)
        number, badge = (pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                         for style in (data.number_style, data.badge_style))
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=(960, 640)).with_focus(route[0])
            count = body_clip(data, motion.actor, motion.clip).frames
            pixels = []
            for index in range(count):
                time = motion.complete_ms * (index + .5) / count
                sampled = sample_motion(motion, data, time)
                frame = sample_playback_frame(before, after, data, time, 5000 + time,
                    camera, {}, media, number, badge, motion=motion)
                command, = (row for row in frame.commands if row[4][0] == identity and row[4][6] == "actor")
                assert sampled.body.clip == motion.clip and sampled.body.frame == index
                assert command[4][8:] == (motion.clip, index)
                assert sampled.lift_px > 0 and not frame.complete
                assert pygame.mask.from_surface(command[1]).count() > 0
                pixels.append(pygame.image.tobytes(command[1], "RGBA"))
            # Read the actual layered draw surfaces, not only a reported frame
            # counter: a restarted/modulo clip repeats these rendered poses.
            assert len(set(pixels)) == count
            assert sample_motion(motion, data, 0).body.frame == 0
            assert sample_motion(motion, data, motion.complete_ms - .001).body.frame == count - 1
            for time in (0, motion.complete_ms / 2, motion.complete_ms):
                sampled = sample_motion(motion, data, time)
                frame = sample_playback_frame(before, after, data, time, 5000 + time,
                    camera, {}, media, number, badge, motion=motion)
                actor, = (row for row in frame.actors if row.contact.actor_uuid == identity)
                command, = (row for row in frame.commands if row[4][0] == identity and row[4][6] == "actor")
                shadow, = (row for row in frame.commands if row[4][0] == identity and row[4][6] == "actor_shadow")
                assert actor.contact == sampled.contact
                assert command[4][1] == shadow[4][1] == sampled.contact.grid
                if time == motion.complete_ms / 2:
                    body_depth, shadow_depth = command[4][7], shadow[4][7]
                    assert isinstance(body_depth, (int, float)) and isinstance(shadow_depth, (int, float))
                    assert body_depth > shadow_depth and sampled.contact.body_lift_px > 0
                if time == motion.complete_ms:
                    assert frame.complete and frame.displayed == after and not frame.positions
                    idle = sample_playback_frame(after, None, data, 0, 5000 + time, camera, frame.facings,
                        media, number, badge, positions=frame.positions)
                    idle_body, = (row for row in idle.commands if row[4][0] == identity and row[4][6] == "actor")
                    assert command[2:] == idle_body[2:]
                    assert pygame.image.tobytes(command[1], "RGBA") == pygame.image.tobytes(idle_body[1], "RGBA")
    finally:
        pygame.quit()
