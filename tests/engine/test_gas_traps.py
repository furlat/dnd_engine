"""Real gas releases own their exposure, footprint and lifetime independently."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest

from dnd.actions import Jump, Move
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.environment_item_builders import build_directional_door
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import (
    DamageAppliedEvent, Event, EventPhase, EventQueue, EventType, MechanismActivationEvent,
    SavingThrowEvent, SpatialEffectChangeEvent, SpatialEffectInteractionEvent,
)
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.gas_traps import GasCloud, GasCloudSpec, GasVent, materialize_gas_vent
from dnd.spatial.triggers import materialize_pressure_plate
from dnd.types.controls import ActivationLink
from dnd.types.senses import OpticalObscurement
from dnd.types.spatial_effects import SpatialEffectInteractionIntensity, SpatialEffectInteractionOperation
from dnd.types.traps import TrapState
from dnd.types.world import CardinalDirection, OccupancyLayer


@pytest.fixture
def arena() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(9, 5))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime()


def actor(game: Game, position: tuple[int, int], *, damage_immune: bool = False,
          condition_immune: bool = False) -> Entity:
    creature = Entity.create(uuid4(), "Gas recipient", config=EntityConfig(position=position,
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=18)),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")],
                            immunities=[DamageType.POISON] if damage_immune else [])))
    setup_standard_actions(creature)
    creature.compose_entity()
    if condition_immune:
        creature.add_condition_immunity("Poisoned", immunity_name="Poisoned immunity")
    game.deploy_entity(creature, position)
    return creature


def cause(source_uuid: UUID) -> Event:
    declaration = EventQueue.publish_declaration(Event(name="Gas mechanism input",
        source_entity_uuid=source_uuid, event_type=EventType.BASE_ACTION, use_register=False))
    return declaration.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)


def pulse(vent: GasVent, *faces: int) -> MechanismActivationEvent:
    command = cause(vent.uuid)
    with fixed_dice_faces(*faces):
        result = vent.fire(parent_event=command)
    command.phase_to(EventPhase.COMPLETION)
    return result


def clouds() -> list[GasCloud]:
    return [condition for condition in get_map().get_spatial_conditions() if isinstance(condition, GasCloud)]


def completed[EventT: Event](cursor: int, model: type[EventT]) -> list[EventT]:
    return [event for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, model) and event.phase is EventPhase.COMPLETION and not event.canceled]


def descends_from(event: Event, ancestor: Event) -> bool:
    while event.lineage_uuid != ancestor.lineage_uuid and event.parent_event is not None:
        parent = EventQueue.get_event_by_uuid(event.parent_event)
        assert parent is not None
        event = parent
    return event.lineage_uuid == ancestor.lineage_uuid


@pytest.mark.parametrize("save,damage_immune,condition_immune,loss,poisoned", (
    (1, False, False, 4, True), (20, False, False, 2, False),
    (1, True, False, 0, True), (1, False, True, 4, False),
))
def test_release_uses_one_native_save_and_distinguishes_poison_immunities(
    arena, save, damage_immune, condition_immune, loss, poisoned,
):
    target = actor(arena, (3, 2), damage_immune=damage_immune, condition_immune=condition_immune)
    vent = materialize_gas_vent((3, 2), gas=GasCloudSpec(radius_feet=5))
    cursor = EventQueue.event_cursor()
    result = pulse(vent, save, 4)
    cloud, = clouds()
    assert result.committed and result.mechanism_content_ref == vent.content_ref
    assert set(result.affected_positions) == cloud.affected_positions
    assert target.get_hp() == 80 - loss
    assert ("Poisoned" in target.active_conditions) is poisoned
    applications = completed(cursor, ConditionApplicationEvent)
    poison_applications = [event for event in applications if event.condition.name == "Poisoned"]
    assert bool(poison_applications) is poisoned
    saves = completed(cursor, SavingThrowEvent)
    assert len(saves) == 1 and saves[0].saving_throw_context is not None
    assert not saves[0].saving_throw_context.is_magical
    assert descends_from(saves[0], result)
    for fact in completed(cursor, DamageAppliedEvent) + completed(cursor, SpatialEffectChangeEvent):
        assert descends_from(fact, result)
    assert vent.trap_state is TrapState.READY and cloud.uuid != vent.uuid
    assert not cloud.magical_origin and not cloud.linked_conditions


def test_appearance_entry_and_turn_start_share_one_exposure_per_turn(arena):
    target = actor(arena, (3, 2))
    vent = materialize_gas_vent((3, 2), gas=GasCloudSpec(radius_feet=0))
    turn = EventQueue.begin_turn_execution()
    try:
        pulse(vent, 1, 4)
        command = cause(target.uuid)
        Entity.update_entity_position(target, (4, 2), parent_event=command.uuid)
        Entity.update_entity_position(target, (3, 2), parent_event=command.uuid)
        target.on_turn_start(round_number=1)
        command.phase_to(EventPhase.COMPLETION)
        assert target.get_hp() == 76
    finally:
        EventQueue.end_turn_execution(turn)
    next_turn = EventQueue.begin_turn_execution()
    try:
        with fixed_dice_faces(1, 4):
            target.on_turn_start(round_number=2)
        assert target.get_hp() == 72
    finally:
        EventQueue.end_turn_execution(next_turn)


def test_walking_across_several_cloud_cells_exposes_once(arena):
    target = actor(arena, (0, 2))
    vent = materialize_gas_vent((3, 2), gas=GasCloudSpec(radius_feet=10))
    pulse(vent)
    target.update_entity_senses()
    turn = EventQueue.begin_turn_execution()
    try:
        with fixed_dice_faces(1, 4):
            result = Move(source_entity_uuid=target.uuid, end_position=(4, 2),
                path=[(x, 2) for x in range(5)], prefer_safe=False).apply()
        assert result is not None and not result.canceled
        assert target.position == (4, 2) and target.get_hp() == 76
    finally:
        EventQueue.end_turn_execution(turn)


@pytest.mark.parametrize("cloud_position,expected_loss", (((1, 2), 0), ((3, 2), 4)))
def test_jump_skips_low_cloud_crossing_but_landing_makes_ground_contact(arena, cloud_position, expected_loss):
    target = actor(arena, (0, 2))
    vent = materialize_gas_vent(cloud_position, gas=GasCloudSpec(radius_feet=0))
    pulse(vent)
    target.update_entity_senses()
    with fixed_dice_faces(*((1, 4) if expected_loss else ())):
        result = Jump(source_entity_uuid=target.uuid, end_position=(3, 2)).apply()
    assert result is not None and not result.canceled
    assert target.position == (3, 2) and target.occupancy_layer is OccupancyLayer.GROUND
    assert target.get_hp() == 80 - expected_loss


@pytest.mark.parametrize("remove_vent", (False, True))
def test_released_cloud_and_poisoning_outlive_disabled_or_removed_vent(arena, remove_vent):
    target = actor(arena, (3, 2))
    vent = materialize_gas_vent((3, 2), gas=GasCloudSpec(
        radius_feet=0, duration_rounds=2, poisoned_duration_rounds=3))
    pulse(vent, 1, 4)
    cloud, = clouds()
    command = cause(vent.uuid)
    assert vent.set_trap_state(TrapState.DEACTIVATED, parent_event=command)
    assert not vent.fire(parent_event=command).committed
    if remove_vent:
        assert vent.deactivate(parent_event=command)
    assert cloud.is_active_spatial_condition()
    assert "Poisoned" in target.active_conditions
    assert not cloud.progress_spatial_duration(parent_event=command)
    assert cloud.progress_spatial_duration(parent_event=command)
    assert not clouds()
    assert "Poisoned" in target.active_conditions
    for _ in range(2):
        assert not target.advance_duration_condition("Poisoned")
    assert target.advance_duration_condition("Poisoned")
    assert "Poisoned" not in target.active_conditions
    cursor = EventQueue.event_cursor()
    target.on_turn_start(round_number=3)
    assert not completed(cursor, DamageAppliedEvent)


def test_new_same_gas_replaces_overlap_without_erasing_older_remainder(arena):
    first = materialize_gas_vent((2, 2), gas=GasCloudSpec(radius_feet=5))
    second = materialize_gas_vent((3, 2), gas=GasCloudSpec(radius_feet=5))
    pulse(first)
    old, = clouds()
    original = set(old.affected_positions)
    assert not old.progress_spatial_duration()
    pulse(second)
    fresh, = [cloud for cloud in clouds() if cloud.uuid != old.uuid]
    assert original & fresh.affected_positions
    assert old.affected_positions == original - fresh.affected_positions
    assert old.affected_positions and old.duration.duration == 2
    assert fresh.duration.duration == 3
    assert old.affected_positions.isdisjoint(fresh.affected_positions)


@pytest.mark.parametrize("open_door", (False, True))
def test_release_footprint_follows_current_boundary_propagation(arena, open_door):
    door = build_directional_door(is_open=open_door)
    door.place_on_grid((3, 2), boundary_direction=CardinalDirection.EAST)
    vent = materialize_gas_vent((3, 2), gas=GasCloudSpec(radius_feet=5))
    result = pulse(vent)
    cloud, = clouds()
    assert ((4, 2) in cloud.affected_positions) is open_door
    assert set(result.affected_positions) == cloud.affected_positions


@pytest.mark.parametrize("obscurement", (None, OpticalObscurement.HEAVY))
def test_authored_obscuration_and_native_wind_dispersal(arena, obscurement):
    vent = materialize_gas_vent((3, 2), gas=GasCloudSpec(radius_feet=5, optical_obscurement=obscurement))
    pulse(vent)
    cloud, = clouds()
    assert get_map().get_optical_obscurements_at((3, 2)) == (set() if obscurement is None else {obscurement})
    original = set(cloud.affected_positions)
    for intensity in (SpatialEffectInteractionIntensity.MINOR, SpatialEffectInteractionIntensity.MODERATE):
        event = EventQueue.publish_declaration(SpatialEffectInteractionEvent(
            source_entity_uuid=uuid4(), operation=SpatialEffectInteractionOperation.DISPERSE,
            positions=((3, 2),), intensity=intensity, use_register=False))
        event = event.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
        event.phase_to(EventPhase.COMPLETION)
        assert cloud.affected_positions == (original if intensity is SpatialEffectInteractionIntensity.MINOR
                                            else original - {(3, 2)})
    assert not get_map().get_optical_obscurements_at((3, 2))
    assert vent.is_active_spatial_condition() and vent.trap_state is TrapState.READY


def test_real_plate_walk_releases_once_per_press_and_keeps_cloud_on_release(arena):
    traveler = actor(arena, (0, 2))
    recipient = actor(arena, (4, 2))
    vent = materialize_gas_vent((4, 2), gas=GasCloudSpec(radius_feet=0))
    plate = materialize_pressure_plate({(1, 2), (1, 3)}, ActivationLink(target_condition_uuid=vent.uuid))
    cursor = EventQueue.event_cursor()
    turn = EventQueue.begin_turn_execution()
    try:
        for destination, faces, expected_pulses in (
            ((1, 2), (1, 4), 1), ((1, 3), (), 1), ((2, 3), (), 1), ((1, 3), (1, 3), 2),
        ):
            traveler.update_entity_senses()
            with fixed_dice_faces(*faces):
                result = Move(source_entity_uuid=traveler.uuid, end_position=destination,
                    path=[traveler.position, destination], prefer_safe=False).apply()
            assert result is not None and not result.canceled
            pulses = [event for event in completed(cursor, MechanismActivationEvent)
                      if event.mechanism_uuid == vent.uuid and event.committed]
            assert len(pulses) == expected_pulses
            assert len(clouds()) == 1
            if faces:
                assert descends_from(pulses[-1], result)
    finally:
        EventQueue.end_turn_execution(turn)
    assert plate.pressed and vent.trap_state is TrapState.READY
    assert recipient.get_hp() == 73
