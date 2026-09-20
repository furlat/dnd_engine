"""Installed spikes keep their mode and resolve authored native payloads."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest

from dnd.actions_functional import execute_use_action
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.environment_item_builders import build_trap_lever
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import (
    DamageAppliedEvent, Event, EventPhase, EventQueue, EventType, SavingThrowEvent,
    SpatialEffectChangeEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.saving_throw_types import SavingThrowEffectTag
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.environmental_conditions import (
    PLAIN_SPIKE_PAYLOAD, POISON_DAMAGE_SPIKE_PAYLOAD, SICKENING_SPIKE_PAYLOAD,
    materialize_spike_trap_condition,
)
from dnd.types.spatial_effects import SpatialEffectChangeOperation
from dnd.types.traps import TrapPayload, TrapState
from game.event_record import decode_event, encode_event


@pytest.fixture(autouse=True)
def arena() -> Iterator[None]:
    reset_engine_runtime(grid_size=(5, 3))
    game = Game()
    try:
        yield
    finally:
        game.close()
        reset_engine_runtime()


def actor(*, poison_resistant: bool = False, poison_immune: bool = False,
          position: tuple[int, int] = (0, 1)) -> Entity:
    creature = Entity.create(uuid4(), "Trap visitor", config=EntityConfig(
        position=position, health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")],
            resistances=[DamageType.POISON] if poison_resistant else [],
            immunities=[DamageType.POISON] if poison_immune else [],
        ),
    ))
    creature.compose_entity()
    Game().deploy_entity(creature, creature.position)
    return creature


def cause(source: UUID) -> Event:
    return Event(source_entity_uuid=source, event_type=EventType.BASE_ACTION,
                 phase=EventPhase.EFFECT)


def completed_since(cursor: int) -> list[Event]:
    return [event for _, event in EventQueue.iter_events_since(cursor)
            if event.phase is EventPhase.COMPLETION and not event.canceled]


def assert_under(event: Event, root: Event) -> None:
    while event.parent_event is not None:
        parent = EventQueue.get_event_by_uuid(event.parent_event)
        assert parent is not None
        event = parent
    assert event.lineage_uuid == root.lineage_uuid


def use_lever(operator: Entity, lever_uuid: UUID, name: str) -> Event:
    operator.update_entity_senses()
    assert any(row.source_item_uuid == lever_uuid
               and row.template_name.split("__item_")[0] == name
               for row in operator.get_available_actions().all_actions)
    result = execute_use_action(operator, lever_uuid, name)
    assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION
    return result


@pytest.mark.parametrize("payload, faces, hp_loss, poisoned", [
    (PLAIN_SPIKE_PAYLOAD, (1, 1), 2, False),
    (POISON_DAMAGE_SPIKE_PAYLOAD, (1, 1, 4), 6, False),
    (SICKENING_SPIKE_PAYLOAD, (1, 1, 1), 2, True),
])
def test_lever_activation_applies_shared_payload_to_stationary_occupant(
    payload: TrapPayload, faces: tuple[int, ...], hp_loss: int, poisoned: bool,
) -> None:
    operator = actor()
    occupant = actor(position=(3, 1))
    trap = materialize_spike_trap_condition({(3, 1)}, payload=payload)
    lever = build_trap_lever(trap.uuid, charges=-1, allow_activation=True)
    lever.place_on_grid((1, 1))
    hp, operator_hp = occupant.get_hp(), operator.get_hp()
    use_lever(operator, lever.uuid, "Deactivate Trap")
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*faces):
        root = use_lever(operator, lever.uuid, "Activate Trap")

    assert occupant.position == (3, 1) and occupant.get_hp() == hp - hp_loss
    assert operator.get_hp() == operator_hp
    assert ("Poisoned" in occupant.active_conditions) is poisoned
    events = completed_since(cursor)
    state = next(event for event in events if isinstance(event, SpatialEffectChangeEvent)
                 and event.operation is SpatialEffectChangeOperation.STATE_CHANGED)
    assert state.previous_trap_state is TrapState.DEACTIVATED
    assert state.trap_state is TrapState.ACTIVATED
    assert_under(state, root)
    consequences = [event for event in events if isinstance(
        event, (DamageAppliedEvent, SavingThrowEvent, ConditionApplicationEvent),
    )]
    assert consequences
    for consequence in consequences:
        assert_under(consequence, root)
        ancestor = consequence
        while ancestor.lineage_uuid != state.lineage_uuid:
            assert ancestor.parent_event is not None
            parent = EventQueue.get_event_by_uuid(ancestor.parent_event)
            assert parent is not None
            ancestor = parent
    assert not trap.set_trap_state(TrapState.ACTIVATED, parent_event=root)
    assert occupant.get_hp() == hp - hp_loss
    use_lever(operator, lever.uuid, "Deactivate Trap")
    assert occupant.get_hp() == hp - hp_loss


def test_lever_activation_hits_each_occupied_cell_once_in_one_network() -> None:
    operator = actor()
    occupants = (actor(position=(3, 1)), actor(position=(4, 1)))
    trap = materialize_spike_trap_condition({(3, 1), (4, 1)})
    lever = build_trap_lever(trap.uuid, charges=-1, allow_activation=True)
    lever.place_on_grid((1, 1))
    use_lever(operator, lever.uuid, "Deactivate Trap")
    hp = tuple(occupant.get_hp() for occupant in occupants)
    with fixed_dice_faces(1, 1, 1, 1):
        use_lever(operator, lever.uuid, "Activate Trap")
    assert tuple(occupant.get_hp() for occupant in occupants) == tuple(value - 2 for value in hp)


def test_ready_entry_raises_once_and_disabled_spikes_retain_identity_without_damage() -> None:
    visitor = actor()
    trap = materialize_spike_trap_condition({(1, 1)})
    identity = trap.uuid
    assert trap.trap_state is TrapState.READY
    assert "Retracted and armed" in trap.describe_trap()
    root = cause(visitor.uuid)
    cursor, hp = EventQueue.event_cursor(), visitor.get_hp()

    with fixed_dice_faces(1, 1):
        Entity.update_entity_position(visitor, (1, 1), parent_event=root.uuid)

    assert visitor.get_hp() == hp - 2
    assert trap.trap_state is TrapState.ACTIVATED
    transitions = [event for event in completed_since(cursor)
                   if isinstance(event, SpatialEffectChangeEvent)
                   and event.operation is SpatialEffectChangeOperation.STATE_CHANGED]
    assert len(transitions) == 1
    assert transitions[0].previous_trap_state is TrapState.READY
    assert transitions[0].trap_state is TrapState.ACTIVATED
    restored = decode_event(encode_event(transitions[0]))
    assert isinstance(restored, SpatialEffectChangeEvent)
    assert restored.spatial_effect_uuid == identity and restored.trap_state is TrapState.ACTIVATED
    assert restored.previous_trap_state is TrapState.READY
    assert_under(transitions[0], root)
    assert "Raised" in trap.describe_trap()

    Entity.update_entity_position(visitor, (0, 1), parent_event=root.uuid)
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(1, 1):
        Entity.update_entity_position(visitor, (1, 1), parent_event=root.uuid)
    assert visitor.get_hp() == hp - 4
    assert not any(isinstance(event, SpatialEffectChangeEvent)
                   and event.operation is SpatialEffectChangeOperation.STATE_CHANGED
                   for event in completed_since(cursor))

    assert trap.set_trap_state(TrapState.DEACTIVATED, parent_event=root)
    assert trap.applied and get_map().get_spatial_condition(identity) is trap
    assert trap.affected_positions == {(1, 1)}
    assert not get_map().is_position_hazardous_for(1, 1, visitor.uuid)
    assert "disabled" in trap.describe_trap()
    Entity.update_entity_position(visitor, (0, 1), parent_event=root.uuid)
    Entity.update_entity_position(visitor, (1, 1), parent_event=root.uuid)
    assert visitor.get_hp() == hp - 4 and trap.trap_state is TrapState.DEACTIVATED

    Entity.update_entity_position(visitor, (0, 1), parent_event=root.uuid)
    assert trap.set_trap_state(TrapState.ACTIVATED, parent_event=root)
    with fixed_dice_faces(1, 1):
        Entity.update_entity_position(visitor, (1, 1), parent_event=root.uuid)
    assert visitor.get_hp() == hp - 6 and trap.uuid == identity
    assert trap.deactivate(parent_event=root)
    assert get_map().get_spatial_condition(identity) is None


def test_authored_raised_spikes_are_perceptible_despite_the_retracted_concealment_dc() -> None:
    visitor = actor()
    trap = materialize_spike_trap_condition(
        {(1, 1)}, trap_state=TrapState.ACTIVATED, stealth_dc=30,
    )
    assert visitor.get_passive_perception() < 30
    assert get_map().is_position_hazardous_for(1, 1, visitor.uuid)
    observation = trap.get_spatial_observation({(1, 1)}, observer_uuid=visitor.uuid)
    assert observation is not None and observation.trap_state is TrapState.ACTIVATED
    assert "Raised" in observation.description


@pytest.mark.parametrize("resistant, immune, expected_damage", [
    (False, False, 8), (True, False, 6), (False, True, 4),
])
def test_poison_damage_spikes_mitigate_poison_separately_from_piercing(
    resistant: bool, immune: bool, expected_damage: int,
) -> None:
    visitor = actor(poison_resistant=resistant, poison_immune=immune)
    trap = materialize_spike_trap_condition({(1, 1)}, payload=POISON_DAMAGE_SPIKE_PAYLOAD)
    hp = visitor.get_hp()
    with fixed_dice_faces(2, 2, 4):
        Entity.update_entity_position(visitor, (1, 1), parent_event=cause(visitor.uuid).uuid)
    assert visitor.get_hp() == hp - expected_damage
    assert trap.trap_state is TrapState.ACTIVATED
    assert "Poisoned" not in visitor.active_conditions


@pytest.mark.parametrize("save_face, immune, poisoned", [
    (20, False, False), (1, False, True), (1, True, False),
])
def test_sickening_spikes_use_native_save_condition_immunity_and_duration(
    save_face: int, immune: bool, poisoned: bool,
) -> None:
    visitor = actor()
    if immune:
        visitor.add_condition_immunity("Poisoned", immunity_name="Poison immunity")
    trap = materialize_spike_trap_condition({(1, 1)}, payload=SICKENING_SPIKE_PAYLOAD)
    cursor, hp = EventQueue.event_cursor(), visitor.get_hp()
    root = cause(visitor.uuid)
    with fixed_dice_faces(1, 1, save_face):
        Entity.update_entity_position(visitor, (1, 1), parent_event=root.uuid)
    assert visitor.get_hp() == hp - 2
    assert ("Poisoned" in visitor.active_conditions) is poisoned
    events = completed_since(cursor)
    saves = [event for event in events if isinstance(event, SavingThrowEvent)]
    assert len(saves) == 1
    context = saves[0].saving_throw_context
    assert context is not None and context.effect_tags == (SavingThrowEffectTag.POISON,)
    assert context.condition_id == "condition.poisoned" and not context.is_magical
    assert_under(saves[0], root)
    applications = [event for event in events if isinstance(event, ConditionApplicationEvent)
                    and event.target_entity_uuid == visitor.uuid]
    assert bool(applications) is poisoned
    for application in applications:
        assert_under(application, root)

    if poisoned:
        assert trap.set_trap_state(TrapState.DEACTIVATED, parent_event=root)
        assert "Poisoned" in visitor.active_conditions
        assert not visitor.advance_duration_condition("Poisoned")
        assert visitor.advance_duration_condition("Poisoned")
        assert "Poisoned" not in visitor.active_conditions
