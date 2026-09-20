"""Both players reconstruct trap knowledge from saved subjective events alone."""

from uuid import uuid4

import pytest

from dnd.conditions import Blinded
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spatial.environmental_conditions import materialize_spike_trap_condition
from dnd.types.traps import TrapState
from game.player_projection import project_sequence
from game.player_facts import SpatialEffectStateFact
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import capture_interval, reduce_interval
from game.replay import ObserverCapture, RecordedSequence, capture_history
from tests.engine.test_senses_light_stealth import PerceptionModifierCondition


@pytest.fixture(scope="module")
def recorded_traps():
    reset_engine_runtime()
    built = build_battlefield("battlefield.visibility_open_range")
    game = Game()
    try:
        actors = {}
        for role, position in (("scout", (0, 1)), ("witness", (1, 1))):
            actor = Entity.create(uuid4(), role, config=EntityConfig(position=position))
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        scout, witness = actors["scout"], actors["witness"]
        scout.add_condition(PerceptionModifierCondition(
            source_entity_uuid=scout.uuid, target_entity_uuid=scout.uuid, modifier_amount=10))
        trap = materialize_spike_trap_condition({(3, 1), (23, 1)}, stealth_dc=15)
        secret = materialize_spike_trap_condition({(4, 3)}, stealth_dc=40)
        assert trap.uuid in scout.senses.spatial_effects
        assert trap.uuid not in witness.senses.spatial_effects
        cursor = EventQueue.event_cursor()
        initial = capture_interval(name="Trap room", start_cursor=0, end_cursor=cursor,
            observer_uuid=scout.uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, initial)

        def operate(state: TrapState) -> None:
            event = Event(name="Operate trap", event_type=EventType.BASE_ACTION,
                source_entity_uuid=witness.uuid, phase=EventPhase.EFFECT)
            assert trap.set_trap_state(state, parent_event=event)
            event.phase_to(EventPhase.COMPLETION)

        operate(TrapState.DEACTIVATED)
        operate(TrapState.ACTIVATED)
        operate(TrapState.DEACTIVATED)
        blindness = Blinded(source_entity_uuid=scout.uuid, target_entity_uuid=scout.uuid)
        scout.add_condition(blindness)
        operate(TrapState.ACTIVATED)
        assert scout.senses.spatial_effects[trap.uuid].trap_state is TrapState.DEACTIVATED
        scout.remove_condition_by_uuid(blindness.uuid)
        assert scout.senses.spatial_effects[trap.uuid].trap_state is TrapState.ACTIVATED

        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, cursor) for role, actor in actors.items()))
        return captured, trap.uuid, secret.uuid
    finally:
        game.close()
        reset_engine_runtime()


@pytest.mark.parametrize("role", ("scout", "witness"))
def test_public_saved_packets_retain_only_that_players_observed_trap_state(recorded_traps, role):
    history, trap_uuid, secret_uuid = recorded_traps
    native = RecordedSequence.model_validate_json(
        history.views[role].model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    payload = encode_player_sequence(project_sequence(native))
    assert str(secret_uuid).encode() not in payload
    state, roots = decode_player_sequence(payload)
    assert state.senses is not None
    initial = state

    def mode(current):
        row = current.senses.spatial_effects.get(trap_uuid)
        if row is not None:
            assert row.positions == ((3, 1),), "An unseen network cell must not travel in player input"
        return row.trap_state if row else None

    states = [mode(state)]
    transitions = []
    for root in roots:
        transitions.extend(node.fact for node in root.events if isinstance(node.fact, SpatialEffectStateFact))
        state = reduce_lineage(state, root)
        assert secret_uuid not in state.senses.spatial_effects
        value = mode(state)
        if value != states[-1]:
            states.append(value)
    assert states == ([TrapState.READY, TrapState.DEACTIVATED] if role == "scout" else [None]) + [
        TrapState.ACTIVATED, TrapState.DEACTIVATED, TrapState.ACTIVATED]
    assert mode(initial) is (TrapState.READY if role == "scout" else None)
    expected = [(TrapState.READY, TrapState.DEACTIVATED), (TrapState.DEACTIVATED, TrapState.ACTIVATED),
                (TrapState.ACTIVATED, TrapState.DEACTIVATED)] if role == "scout" else [
                    (TrapState.DEACTIVATED, TrapState.ACTIVATED), (TrapState.ACTIVATED, TrapState.DEACTIVATED),
                    (TrapState.DEACTIVATED, TrapState.ACTIVATED)]
    assert [(fact.previous_state, fact.state) for fact in transitions] == expected
    assert all(fact.positions == ((3, 1),) for fact in transitions)
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
