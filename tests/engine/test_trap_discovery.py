"""A fixture's discovery and last observed state survive mechanical toggles."""

from uuid import UUID

from dnd.conditions import Blinded
from dnd.core.events import Event, EventPhase, EventQueue, EventType, SensoryUpdateEvent
from dnd.entity import Entity
from dnd.spatial.environmental_conditions import materialize_spike_trap_condition
from dnd.types.senses import reduce_senses_snapshot
from dnd.types.traps import TrapState
from game.event_record import decode_event, encode_event
from tests.engine.test_senses_light_stealth import (
    PerceptionModifierCondition, create_skeleton, reset_senses_state,
)


def cause(actor: Entity) -> Event:
    return Event(source_entity_uuid=actor.uuid, event_type=EventType.BASE_ACTION,
                 phase=EventPhase.EFFECT, name="Operate trap")


def recorded_senses(observer: UUID):
    state = None
    for _, event in EventQueue.iter_events_since(0):
        if isinstance(event, SensoryUpdateEvent) and event.observer_uuid == observer:
            restored = decode_event(encode_event(event))
            assert isinstance(restored, SensoryUpdateEvent)
            state = reduce_senses_snapshot(observer, state, restored)
    assert state is not None
    return state


def test_detected_inert_trap_remains_known_after_perception_drops() -> None:
    reset_senses_state(width=6, height=2)
    scout = create_skeleton(name="Scout", position=(0, 0))
    witness = create_skeleton(name="Witness", position=(0, 1))
    bonus = PerceptionModifierCondition(source_entity_uuid=scout.uuid,
        target_entity_uuid=scout.uuid, modifier_amount=10)
    scout.add_condition(bonus)
    trap = materialize_spike_trap_condition({(3, 0)}, stealth_dc=15)
    assert scout.get_passive_perception() > 15 >= witness.get_passive_perception()
    known = scout.senses.spatial_effects[trap.uuid]
    assert known.trap_state is TrapState.READY
    assert trap.uuid not in witness.senses.spatial_effects

    scout.remove_condition_by_uuid(bonus.uuid)
    assert scout.get_passive_perception() <= 15
    assert scout.senses.spatial_effects[trap.uuid] == known
    assert scout.senses.hazardous_cells[(3, 0)]
    assert trap.set_trap_state(TrapState.DEACTIVATED, parent_event=cause(scout))
    inert = scout.senses.spatial_effects[trap.uuid]
    assert inert.trap_state is TrapState.DEACTIVATED
    assert inert.description != known.description
    assert not scout.senses.hazardous_cells[(3, 0)]
    assert trap.uuid not in witness.senses.spatial_effects

    trap.set_trap_state(TrapState.ACTIVATED, parent_event=cause(scout))
    for observer in (scout, witness):
        assert observer.senses.spatial_effects[trap.uuid].trap_state is TrapState.ACTIVATED
        assert recorded_senses(observer.uuid).spatial_effects == observer.senses.spatial_effects


def test_unseen_toggle_keeps_remembered_description_until_sight_returns() -> None:
    reset_senses_state(width=6, height=2)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    trap = materialize_spike_trap_condition({(3, 0)})
    remembered = observer.senses.spatial_effects[trap.uuid]
    blindness = Blinded(source_entity_uuid=observer.uuid, target_entity_uuid=observer.uuid)
    observer.add_condition(blindness)
    assert (3, 0) not in observer.senses.visible
    trap.set_trap_state(TrapState.DEACTIVATED, parent_event=cause(observer))
    assert observer.senses.spatial_effects[trap.uuid] == remembered
    assert recorded_senses(observer.uuid).spatial_effects[trap.uuid] == remembered
    observer.remove_condition_by_uuid(blindness.uuid)
    observed = observer.senses.spatial_effects[trap.uuid]
    assert observed.trap_state is TrapState.DEACTIVATED
    assert observed.description != remembered.description
    assert recorded_senses(observer.uuid).spatial_effects == observer.senses.spatial_effects


def test_network_only_discloses_observed_cells_and_remembers_unseen_removal() -> None:
    reset_senses_state(width=9, height=1)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    observer.update_entity_senses(max_distance=3)
    trap = materialize_spike_trap_condition({(2, 0), (7, 0)})
    observed = observer.senses.spatial_effects[trap.uuid]
    assert observed.positions == ((2, 0),)
    assert recorded_senses(observer.uuid).spatial_effects[trap.uuid].positions == ((2, 0),)

    blindness = Blinded(source_entity_uuid=observer.uuid, target_entity_uuid=observer.uuid)
    observer.add_condition(blindness)
    trap.deactivate(parent_event=cause(observer))  # Actual destruction/removal, not lowering.
    assert observer.senses.spatial_effects[trap.uuid] == observed
    observer.remove_condition_by_uuid(blindness.uuid)
    assert trap.uuid not in observer.senses.spatial_effects
    assert trap.uuid not in recorded_senses(observer.uuid).spatial_effects
