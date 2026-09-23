"""Finite trap commands publish their actual geometry and native consequences."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions_functional import setup_standard_actions
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.environment_item_builders import build_directional_door
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import DamageAppliedEvent, Event, EventPhase, EventQueue, EventType, MechanismActivationEvent
from dnd.core.gridmap import get_map
from dnd.core.world_edges import CardinalDirection, ElevationSurfaceKind
from dnd.core.creature_types import DamageType
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.environmental_conditions import materialize_spike_trap_condition
from dnd.spatial.mechanisms import (
    AreaGeometry, CRUSHER_CONTENT_REF, LaneGeometry, SWINGING_BLADE_CONTENT_REF,
    TrapSave, materialize_finite_trap,
)
from dnd.types.traps import TrapConditionPayload, TrapDamage, TrapPayload, TrapState


@pytest.fixture
def arena() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(9, 9))
    game = Game()
    try:
        yield game
    finally:
        game.close()
        reset_engine_runtime()


def actor(game: Game, position: tuple[int, int]) -> Entity:
    entity = Entity.create(uuid4(), "Trap recipient", config=EntityConfig(position=position,
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")])))
    setup_standard_actions(entity)
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


def pulse(trap, *faces: int) -> MechanismActivationEvent:
    # The stable domain boundary is the mechanism command. Plate/lever tests
    # separately exercise the controllers which submit this same operation.
    cause = EventQueue.publish_declaration(Event(name="Mechanism control pulse",
        event_type=EventType.BASE_ACTION, source_entity_uuid=trap.uuid, use_register=False))
    cause = cause.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
    with fixed_dice_faces(*faces):
        result = trap.fire(parent_event=cause)
    cause.phase_to(EventPhase.COMPLETION)
    return result


@pytest.mark.parametrize("direction", ((1, 0), (-1, 0), (0, 1), (0, -1)))
def test_one_dart_stops_at_first_recipient_and_rearms(arena, direction):
    origin = (4, 4)
    first = actor(arena, (4 + 2 * direction[0], 4 + 2 * direction[1]))
    second = actor(arena, (4 + 3 * direction[0], 4 + 3 * direction[1]))
    trap = materialize_finite_trap(origin, geometry=LaneGeometry(range_feet=15), direction=direction)
    cursor = EventQueue.event_cursor()
    result = pulse(trap, 1, 4)
    assert result.committed and result.phase is EventPhase.COMPLETION
    assert result.origin_position == origin and result.end_position == first.position
    assert result.affected_positions == tuple((4 + step * direction[0], 4 + step * direction[1]) for step in (1, 2))
    assert (first.get_hp(), second.get_hp()) == (76, 80)
    assert trap.trap_state is TrapState.READY
    assert first.action_economy.actions.normalized_score == 1
    damage, = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, DamageAppliedEvent) and event.phase is EventPhase.COMPLETION]
    assert damage.source_entity_uuid == trap.uuid
    ancestor = damage
    while ancestor.parent_event is not None and ancestor.lineage_uuid != result.lineage_uuid:
        ancestor = EventQueue.get_event_by_uuid(ancestor.parent_event)
        assert ancestor is not None
    assert ancestor.lineage_uuid == result.lineage_uuid
    assert pulse(trap, 1, 3).committed
    assert first.get_hp() == 73


@pytest.mark.parametrize("save,expected_hp", ((1, 76), (20, 80)))
def test_avoidance_save_does_not_send_the_dart_on_to_another_target(arena, save, expected_hp):
    target = actor(arena, (2, 3))
    beyond = actor(arena, (3, 3))
    trap = materialize_finite_trap((0, 3), geometry=LaneGeometry())
    result = pulse(trap, *((save, 4) if save == 1 else (save,)))
    assert result.end_position == target.position
    assert target.get_hp() == expected_hp and beyond.get_hp() == 80


@pytest.mark.parametrize("blocker", ("center", "closed-door", "open-door"))
def test_dart_uses_native_center_and_boundary_propagation(arena, blocker):
    target = actor(arena, (4, 3))
    if blocker == "center":
        get_map().set_tile(3, 3, name="Wall", walking_cost=0, blocks_propagation=True)
    else:
        door = build_directional_door(is_open=blocker == "open-door")
        door.place_on_grid((2, 3), boundary_direction=CardinalDirection.EAST)
    trap = materialize_finite_trap((0, 3), geometry=LaneGeometry())
    result = pulse(trap, *((1, 4) if blocker == "open-door" else ()))
    assert result.committed
    assert result.end_position == ((4, 3) if blocker == "open-door" else (2, 3))
    assert target.get_hp() == (76 if blocker == "open-door" else 80)


def test_empty_lane_is_recorded_and_respects_range(arena):
    target = actor(arena, (4, 3))
    trap = materialize_finite_trap((0, 3), geometry=LaneGeometry(range_feet=10))
    result = pulse(trap)
    assert result.committed and result.target_entity_uuid is None
    assert result.affected_positions == ((1, 3), (2, 3))
    assert result.end_position == (2, 3) and target.get_hp() == 80


def test_elevated_support_lane_uses_the_same_native_boundary_rule(arena):
    grid = get_map()
    for x in range(5):
        grid.set_tile_elevation((x, 3), height=2, surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
    target = actor(arena, (4, 3))
    door = build_directional_door()
    door.place_on_grid((2, 3), boundary_direction=CardinalDirection.EAST)
    trap = materialize_finite_trap((0, 3), geometry=LaneGeometry())
    assert pulse(trap).end_position == (2, 3)
    door.open()
    assert pulse(trap, 1, 4).end_position == (4, 3)
    assert target.get_hp() == 76


@pytest.mark.parametrize("reference,damage_type", (
    (SWINGING_BLADE_CONTENT_REF, DamageType.SLASHING),
    (CRUSHER_CONTENT_REF, DamageType.BLUDGEONING),
))
def test_area_stroke_affects_only_authored_reachable_cells_once(arena, reference, damage_type):
    targets = [actor(arena, position) for position in ((3, 3), (3, 4))]
    outside = actor(arena, (4, 3))
    payload = TrapPayload(damages=(TrapDamage(dice_count=1, dice_sides=6, damage_type=damage_type),))
    trap = materialize_finite_trap((2, 3), geometry=AreaGeometry(offsets=((1, 0), (1, 1), (1, 0))),
        content_ref=reference, payload=payload)
    result = pulse(trap, 1, 4, 1, 4)
    assert result.committed and result.affected_positions == ((3, 3), (3, 4))
    assert [target.get_hp() for target in targets] == [76, 76]
    assert outside.get_hp() == 80 and trap.trap_state is TrapState.READY


def test_area_stroke_does_not_cross_closed_boundary(arena):
    target = actor(arena, (3, 3))
    door = build_directional_door()
    door.place_on_grid((2, 3), boundary_direction=CardinalDirection.EAST)
    trap = materialize_finite_trap((2, 3), geometry=AreaGeometry(offsets=((1, 0),)),
        content_ref=SWINGING_BLADE_CONTENT_REF)
    assert pulse(trap).affected_positions == ()
    assert target.get_hp() == 80


def test_authored_half_damage_and_poison_payload_use_actual_saves(arena):
    target = actor(arena, (2, 3))
    trap = materialize_finite_trap((0, 3), geometry=LaneGeometry(),
        avoidance=TrapSave(half_damage_on_success=True),
        payload=TrapPayload(damages=(TrapDamage(dice_count=1, dice_sides=6, damage_type=DamageType.PIERCING),),
            condition=TrapConditionPayload(save_dc=12, duration_rounds=2)))
    pulse(trap, 20, 5)
    assert target.get_hp() == 78 and "Poisoned" not in target.active_conditions
    pulse(trap, 1, 4, 1)
    assert target.get_hp() == 74 and "Poisoned" in target.active_conditions


def test_disable_spent_reset_and_removal_are_mechanical(arena):
    target = actor(arena, (2, 3))
    trap = materialize_finite_trap((0, 3), geometry=LaneGeometry(), rearm_after_activation=False)
    assert pulse(trap, 1, 4).committed and trap.trap_state is TrapState.ACTIVATED
    assert pulse(trap).canceled and target.get_hp() == 76
    control = Event(source_entity_uuid=trap.uuid, event_type=EventType.BASE_ACTION, phase=EventPhase.EFFECT)
    assert trap.set_trap_state(TrapState.DEACTIVATED, parent_event=control)
    assert pulse(trap).canceled and target.get_hp() == 76
    assert trap.set_trap_state(TrapState.READY, parent_event=control)
    assert pulse(trap, 1, 3).committed and target.get_hp() == 73
    assert trap.deactivate(parent_event=control)
    assert pulse(trap).canceled and target.get_hp() == 73
    control.phase_to(EventPhase.COMPLETION)


@pytest.mark.parametrize("trap_first", (False, True))
def test_fixed_mechanism_coexists_with_ground_surface_in_either_installation_order(arena, trap_first):
    position = (2, 3)
    if trap_first:
        trap = materialize_finite_trap(position, geometry=AreaGeometry())
        spikes = materialize_spike_trap_condition({position})
    else:
        spikes = materialize_spike_trap_condition({position})
        trap = materialize_finite_trap(position, geometry=AreaGeometry())
    assert trap.is_active_spatial_condition() and spikes.is_active_spatial_condition()
    assert pulse(trap).committed
