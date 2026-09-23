"""The native mechanism transcript works after reset and keeps links private."""

import pytest

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import SpatialChangeType
from dnd.types.world import OccupancyLayer
from devtools.animation_review.trace import motion_trace
from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.player_facts import MechanismActivationFact, SpatialEffectStateFact, MovementFact, SpatialFact
from game.motion import bind_motion, sample_motion
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.replay import RecordedSequence
from tests.game.mechanism_scenarios import mechanism_history


@pytest.mark.parametrize("program", ("darts", "blade", "crusher", "door", "light"))
def test_native_contact_replays_both_observers_after_engine_reset(program):
    history = mechanism_history(program=program)
    data = load_animation_data()
    for role, saved in history.views.items():
        native = RecordedSequence.model_validate_json(saved.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        public = encode_player_sequence(project_sequence(native))
        assert b"target_condition_uuid" not in public and b"target_item_uuid" not in public
        before, roots = decode_player_sequence(public)
        facts = [node.fact for root in roots for node in root.events]
        edges = [fact.pressed for fact in facts if isinstance(fact, SpatialEffectStateFact)
                 and fact.pressed is not None]
        assert edges == [True, False, True], role
        activations = [fact for fact in facts if isinstance(fact, MechanismActivationFact) and fact.committed]
        assert len(activations) == (0 if program in ("door", "light") else 2)
        for root in roots:
            bound = bind_choreography(before, root, data)
            assert not bound.gaps, bound.gaps
            before = reduce_lineage(before, root)


def test_hidden_launcher_does_not_hide_visible_dart_or_disclose_origin():
    history = mechanism_history(hidden_launcher=True)
    data = load_animation_data()
    for role, saved in history.views.items():
        before, roots = decode_player_sequence(encode_player_sequence(project_sequence(saved)))
        activations = [node.fact for root in roots for node in root.events
            if isinstance(node.fact, MechanismActivationFact) and node.fact.committed]
        assert len(activations) == 2
        for fact in activations:
            assert fact.end_position == (3, 2)
            assert fact.affected_positions == ((3, 4), (3, 3), (3, 2))
            if role == "witness":
                assert fact.origin_position is None and fact.mechanism_uuid is None
            else:
                assert fact.origin_position == (3, 5) and fact.mechanism_uuid is not None
        for root in roots:
            group = bind_choreography(before, root, data)
            assert not group.gaps
            before = reduce_lineage(before, root)


@pytest.mark.parametrize("program", ("darts", "door", "light"))
def test_actual_motion_preserves_plate_release_and_empty_discharge(program):
    history = mechanism_history(program=program, save=True)
    data = load_animation_data()
    for role, saved in history.views.items():
        before, roots = decode_player_sequence(encode_player_sequence(project_sequence(saved)))
        edges, shots = [], []
        hidden_mover_traced = False
        for root in roots:
            if isinstance(root.root.fact, MovementFact):
                motion = bind_motion(before, root, data)
                assert motion is not None
                edges.extend(change.current for change in motion.world_transitions if change.field == "pressed")
                shots.extend(change for change in motion.world_transitions if change.field == "activation")
                trace = motion_trace(motion)
                for reaction, recorded in zip(motion.reactions, trace["reactions"], strict=True):
                    if reaction.contact is None:
                        assert recorded["held_grid"] is None
                        hidden_mover_traced = True
            before = reduce_lineage(before, root)
        assert edges == ["true", "false", "true"]
        assert len(shots) == (2 if program == "darts" else 0)
        if program == "darts":
            assert all(change.projectile is not None for change in shots)
        if program == "door" and role == "witness":
            assert hidden_mover_traced, "The closed door hides the mover but not the observed opening."


@pytest.mark.parametrize("program", ("light", "door"))
def test_jump_takeoff_releases_held_plate_while_airtime_continues(program):
    history = mechanism_history(program=program, jump_release=True)
    data = load_animation_data()
    for role, saved in history.views.items():
        native = RecordedSequence.model_validate_json(saved.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        before, roots = decode_player_sequence(encode_player_sequence(project_sequence(native)))
        checked = False
        for root in roots:
            movement = root.root.fact
            releases = [node.fact for node in root.events if isinstance(node.fact, SpatialEffectStateFact)
                        and node.fact.previous_pressed is True and node.fact.pressed is False]
            if isinstance(movement, MovementFact) and releases:
                motion = bind_motion(before, root, data)
                assert motion is not None and motion.clip == data.movement_context.jumpClip
                plate = releases[0].spatial_effect_uuid
                edges = [change for change in motion.world_transitions
                         if change.identity == plate and change.field == "pressed"]
                assert len(edges) == 1 and edges[0].previous == "true" and edges[0].current == "false", role
                leg, = motion.legs
                assert edges[0].start_ms == leg.start_ms, "Ground pressure releases at takeoff, not landing."
                halfway = sample_motion(motion, data, (leg.start_ms + leg.end_ms) / 2)
                assert halfway.body is not None and halfway.body.clip == data.movement_context.jumpClip
                assert halfway.lift_px > 0 and halfway.reaction is None
                assert halfway.displayed is not None and halfway.displayed.senses is not None
                assert halfway.displayed.senses.spatial_effects[plate].pressed is False
                if program == "light":
                    lights = [identity for identity, obj in before.objects.items() if obj.item.is_lit is True]
                    assert len(lights) == 1
                    assert halfway.displayed.objects[lights[0]].item.is_lit is False
                assert sample_motion(motion, data, (leg.start_ms + leg.end_ms) / 2) == halfway
                checked = True
            before = reduce_lineage(before, root)
        assert checked, role


def test_jump_from_occupied_door_closes_pending_control_when_leaving_first_cell():
    history = mechanism_history(program="door", jump_release=True)
    data = load_animation_data()
    native = RecordedSequence.model_validate_json(
        history.views["witness"].model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    before, roots = decode_player_sequence(encode_player_sequence(project_sequence(native)))
    checked = False
    for root in roots:
        after = reduce_lineage(before, root)
        closing = [identity for identity, obj in before.objects.items()
                   if obj.item.is_open is True and identity in after.objects
                   and after.objects[identity].item.is_open is False]
        if isinstance(root.root.fact, MovementFact) and closing:
            assert not any(isinstance(node.fact, SpatialEffectStateFact) for node in root.events), (
                "This departure closes the doorway after the plate was already released.")
            door, = closing
            update = next(update for update in root.world_updates
                          if any(obj.item.item_uuid == door and obj.item.is_open is False
                                 for obj in update.objects))
            event = next(node for node in root.events if node.uuid == update.event_uuid)
            by_lineage = {node.lineage_uuid: node for node in root.events}
            while not isinstance(event.fact, SpatialFact):
                assert event.parent_lineage is not None
                event = by_lineage[event.parent_lineage]
            assert event.fact.change_type is SpatialChangeType.ENTITY_LEFT
            assert event.fact.position == root.root.fact.start_position
            assert event.fact.previous_occupancy_layer is OccupancyLayer.AIR
            assert event.fact.occupancy_layer is OccupancyLayer.AIR
            motion = bind_motion(before, root, data)
            assert motion is not None and motion.clip == data.movement_context.jumpClip
            leg, = motion.legs
            change, = [change for change in motion.world_transitions
                       if change.identity == door and change.field == "is_open"]
            assert change.previous == "true" and change.current == "false"
            assert change.start_ms == leg.start_ms, "Vacating the first cell closes the door as the arc starts."
            midpoint = (leg.start_ms + leg.end_ms) / 2
            airborne = sample_motion(motion, data, midpoint)
            assert airborne.body is not None and airborne.body.clip == data.movement_context.jumpClip
            assert airborne.lift_px > 0 and airborne.reaction is None
            assert airborne.displayed is not None and airborne.displayed.objects[door].item.is_open is False
            landed = sample_motion(motion, data, motion.complete_ms)
            assert landed.displayed is not None and landed.displayed.objects[door].item.is_open is False
            assert sample_motion(motion, data, midpoint) == airborne
            checked = True
        before = after
    assert checked, "The native witness must jump out of the pending-close doorway."
