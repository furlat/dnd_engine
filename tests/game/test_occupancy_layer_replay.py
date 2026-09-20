"""Committed contact layers survive saved player inputs without hidden origins."""

import json
from pathlib import Path

import pytest

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue, SpatialChangeType
from dnd.entity import Entity
from dnd.types.world import MovementMode, OccupancyLayer
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.motion import bind_motion, sample_motion
from game.player_facts import MovementFact, SpatialFact, StepFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import reduce_interval, reduce_lineage as reduce_native_lineage
from game.replay import RecordedSequence
from tests.game.ground_contact_scenarios import ground_contact_history
from tests.game.scenarios import attack_history
from tests.game.teleport_scenarios import teleport_history as paired_teleport_history


@pytest.fixture(scope="module", params=(
    ((8, 10), (8, 7)), ((8, 7), (8, 10)),
), ids=("hidden-departure", "hidden-arrival"))
def teleport_history(request):
    origin, destination = request.param
    history = paired_teleport_history(battlefield_id="battlefield.visibility_doorway_open",
        caster_position=origin, destination=destination, witness_position=(5, 7),
        caster_layer=OccupancyLayer.AIR)
    return history, origin, destination


def saved_player(native: RecordedSequence):
    restored = RecordedSequence.model_validate_json(native.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    return decode_player_sequence(encode_player_sequence(project_sequence(restored)))


@pytest.fixture(scope="module")
def jump_history():
    return ground_contact_history(program="jump")


@pytest.mark.parametrize("role", ("mover", "operator"))
def test_saved_jump_layers_match_native_contact_history(jump_history, role):
    history = jump_history
    before, roots = saved_player(history.views[role])
    native = history.views[role]
    native_state, _ = reduce_interval(None, native.initialization)
    identity = history.views["mover"].initialization.observer_uuid
    state = before
    for root, native_root in zip(roots, native.lineages, strict=True):
        state = reduce_lineage(state, root)
        native_state = reduce_native_lineage(native_state, native_root)
        assert state.actors[identity].occupancy_layer is OccupancyLayer.GROUND
        assert state.actors[identity].occupancy_layer is native_state.actors[identity].occupancy_layer
        assert state.actors[identity].normal_hp == native_state.actors[identity].normal_hp
    steps = [node.fact for root in roots for node in root.events if isinstance(node.fact, StepFact)]
    assert steps and any(step.to_layer is OccupancyLayer.AIR for step in steps)
    assert all(step.movement_mode is MovementMode.WALKING for step in steps)
    assert before.actors[identity].occupancy_layer is OccupancyLayer.GROUND
    assert state.actors[identity].normal_hp == before.actors[identity].normal_hp - 2
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def test_jump_playback_uses_recorded_takeoff_and_plays_landing_damage(jump_history):
    history = jump_history
    state, roots = saved_player(history.views["mover"])
    identity = state.observer_uuid
    data = load_animation_data()
    landings = 0
    for root in roots:
        if isinstance(root.root.fact, MovementFact):
            timeline = bind_motion(state, root, data)
            assert timeline is not None and timeline.legs
            leg = timeline.legs[0]
            airborne = sample_motion(timeline, data, (leg.start_ms + leg.end_ms) / 2)
            assert airborne.displayed is not None
            assert airborne.displayed.actors[identity].occupancy_layer is OccupancyLayer.AIR
            assert airborne.displayed.actors[identity].normal_hp == state.actors[identity].normal_hp
            final = sample_motion(timeline, data, timeline.complete_ms)
            expected = reduce_lineage(state, root)
            assert final.displayed is not None and final.displayed.actors == expected.actors
            assert final.displayed.actors[identity].occupancy_layer is OccupancyLayer.GROUND
            if expected.actors[identity].normal_hp < state.actors[identity].normal_hp:
                landing = next(cue for cue in timeline.reactions if cue.choreography.damage)
                assert landing.start_ms >= leg.end_ms
                impact = sample_motion(timeline, data, landing.start_ms)
                assert impact.displayed is not None
                assert impact.displayed.actors[identity].occupancy_layer is OccupancyLayer.GROUND
                assert impact.reaction_sample is not None
                landings += 1
        state = reduce_lineage(state, root)
    assert landings == 1
    assert EventQueue.event_cursor() == 0


def test_interrupted_jump_retains_root_landing_and_its_damage():
    history = ground_contact_history(program="interrupted-jump")
    before, (root,) = saved_player(history.views["mover"])
    identity = before.observer_uuid
    expected = reduce_lineage(before, root)
    assert expected.actors[identity].normal_hp == before.actors[identity].normal_hp - 4
    assert expected.actors[identity].occupancy_layer is OccupancyLayer.GROUND
    data = load_animation_data()
    timeline = bind_motion(before, root, data)
    assert timeline is not None
    landing = next(cue for cue in timeline.reactions if cue.action_label is None and cue.choreography.damage)
    impact = sample_motion(timeline, data, landing.start_ms)
    assert impact.displayed is not None and impact.reaction_sample is not None
    assert impact.displayed.actors[identity].occupancy_layer is OccupancyLayer.GROUND
    final = sample_motion(timeline, data, timeline.complete_ms)
    assert final.displayed is not None and final.displayed.actors == expected.actors
    assert sample_motion(timeline, data, landing.start_ms) == impact
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def test_jump_retains_launch_layer_through_multiple_preflight_reactions():
    history = attack_history("weapon.longsword", 17, opportunity=True, whole_movement=True,
        movement_behavior="action.jump", destination=(3, 1), watcher_positions=((4, 3), (2, 3)))
    native = RecordedSequence(initialization=history.initialization, lineages=history.lineages)
    before, (root,) = saved_player(native)
    assert isinstance(root.root.fact, MovementFact)
    identity = root.root.fact.source_entity_uuid
    data = load_animation_data(rig_files=(Path("game/data/rigs/goblin01.json"),))
    timeline = bind_motion(before, root, data)
    assert timeline is not None and len(timeline.reactions) == 2 and timeline.legs
    for reaction in timeline.reactions:
        pending = sample_motion(timeline, data, (reaction.start_ms + reaction.end_ms) / 2)
        assert pending.displayed is not None
        assert pending.displayed.actors[identity].occupancy_layer is OccupancyLayer.GROUND
    leg, = timeline.legs
    airborne = sample_motion(timeline, data, (leg.start_ms + leg.end_ms) / 2)
    assert airborne.displayed is not None
    assert airborne.displayed.actors[identity].occupancy_layer is OccupancyLayer.AIR
    landed = sample_motion(timeline, data, timeline.complete_ms)
    assert landed.displayed is not None
    assert landed.displayed.actors[identity].occupancy_layer is OccupancyLayer.GROUND


def test_supported_teleport_preserves_owned_airborne_history_until_release(teleport_history):
    history, _, _ = teleport_history
    before, (root,) = saved_player(history.views["caster"])
    identity = before.observer_uuid
    assert before.actors[identity].occupancy_layer is OccupancyLayer.AIR
    after = reduce_lineage(before, root)
    assert after.actors[identity].occupancy_layer is OccupancyLayer.GROUND
    group = bind_choreography(before, root, load_animation_data())
    cue, = group.body_actions
    pending = sample_choreography(group, cue.effect_ms - 1)
    arrived = sample_choreography(group, cue.effect_ms)
    assert pending.displayed.actors[identity].occupancy_layer is OccupancyLayer.AIR
    assert arrived.displayed.actors[identity].occupancy_layer is OccupancyLayer.GROUND
    assert sample_choreography(group, cue.effect_ms - 1) == pending
    assert before.actors[identity].occupancy_layer is OccupancyLayer.AIR
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def test_witness_receives_only_the_observed_endpoint_layer(teleport_history):
    history, origin, _ = teleport_history
    before, (root,) = saved_player(history.views["witness"])
    identity = history.views["caster"].initialization.observer_uuid
    facts = [node.fact for node in root.events if isinstance(node.fact, SpatialFact)
             and node.fact.entity_uuid == identity]
    after = reduce_lineage(before, root)
    if origin == (8, 10):
        assert facts
        assert identity not in before.actors
        assert all(fact.change_type is SpatialChangeType.ENTITY_ENTERED for fact in facts)
        assert all(fact.previous_occupancy_layer is None for fact in facts)
        assert all(fact.occupancy_layer is OccupancyLayer.GROUND for fact in facts)
        assert all(row.actor.occupancy_layer is OccupancyLayer.GROUND
                   for row in root.observations if row.actor.uuid == identity)
        assert after.actors[identity].occupancy_layer is OccupancyLayer.GROUND
    else:
        assert before.actors[identity].occupancy_layer is OccupancyLayer.AIR
        assert all(fact.change_type is SpatialChangeType.ENTITY_LEFT for fact in facts)
        assert all(fact.previous_occupancy_layer is OccupancyLayer.AIR for fact in facts)
        assert all(fact.occupancy_layer is None for fact in facts)
        assert after.actors[identity].occupancy_layer is OccupancyLayer.AIR
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def test_legacy_recording_without_layers_does_not_invent_grounded_actors(jump_history):
    history = jump_history
    payload = json.loads(history.views["mover"].model_dump_json())
    pending = [payload]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            for name in ("occupancy_layer", "previous_occupancy_layer", "movement_mode",
                         "start_layer", "end_layer", "from_layer", "to_layer"):
                value.pop(name, None)
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    restored = RecordedSequence.model_validate_json(json.dumps(payload), context=PASSIVE_EVENT_REPLAY)
    before, roots = saved_player(restored)
    assert all(actor.occupancy_layer is None for actor in before.actors.values())
    for root in roots:
        before = reduce_lineage(before, root)
        assert all(actor.occupancy_layer is None for actor in before.actors.values())
        assert all(node.fact.previous_occupancy_layer is None and node.fact.occupancy_layer is None
                   for node in root.events if isinstance(node.fact, SpatialFact))
        assert all(node.fact.movement_mode is None and node.fact.start_layer is None
                   and node.fact.end_layer is None for node in root.events if isinstance(node.fact, MovementFact))
        assert all(node.fact.movement_mode is None and node.fact.from_layer is None
                   and node.fact.to_layer is None for node in root.events if isinstance(node.fact, StepFact))
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
