"""Successful physical avoidance returns to the actual entry cell through events."""

from uuid import UUID

import pytest

from dnd.actions import Move
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, ForcedMovementEvent, SavingThrowEvent, Trigger
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.environmental_conditions import materialize_spike_trap_condition
from dnd.spatial.jaws import materialize_jaw_trap
from dnd.spatial.mechanisms import AreaGeometry, TrapSave, SWINGING_BLADE_CONTENT_REF, CRUSHER_CONTENT_REF, materialize_finite_trap
from dnd.spatial.triggers import materialize_pressure_plate
from dnd.types.controls import ActivationLink
from dnd.types.traps import TrapDamage, TrapPayload, TrapState
from dnd.types.world import OccupancyLayer
from tests.engine.test_jaw_traps import actor, pulse


@pytest.fixture
def arena():
    reset_engine_runtime(grid_size=(8, 6))
    game = Game()
    try:
        yield game
    finally:
        game.close()
        reset_engine_runtime()


def mechanism(program):
    if program == "jaw":
        return materialize_jaw_trap((3, 3))
    trap = materialize_finite_trap((3, 3), geometry=AreaGeometry(),
        content_ref=SWINGING_BLADE_CONTENT_REF if program == "blade" else CRUSHER_CONTENT_REF,
        avoidance=TrapSave(retreat_on_success=True))
    materialize_pressure_plate({(3, 3)}, ActivationLink(target_condition_uuid=trap.uuid))
    return trap


def enter(target, *dice, final=(2, 3)):
    target.update_entity_senses()
    with fixed_dice_faces(*dice):
        result = Move(source_entity_uuid=target.uuid, end_position=(3, 3),
            path=[target.position, (3, 3)], prefer_safe=False).apply()
    assert result is not None and not result.canceled
    assert target.position == result.end_position == final
    return result


def forced_events(cursor):
    return [event for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, ForcedMovementEvent) and event.phase is EventPhase.COMPLETION]


@pytest.mark.parametrize("program", ("jaw", "blade", "crusher"))
def test_success_retreats_without_extra_cost_or_voluntary_movement(arena, program):
    target = actor(arena, (2, 3))
    trap = mechanism(program)
    before = target.action_economy.movement.normalized_score
    cursor = EventQueue.event_cursor()
    result = enter(target, 20)
    movement, = forced_events(cursor)
    assert movement.cause == "saved_entry_avoidance"
    assert (movement.start_position, movement.end_position, movement.actual_distance) == ((3, 3), (2, 3), 5)
    assert movement.target_entity_uuid == target.uuid and movement.source_entity_uuid == trap.uuid
    assert target.get_hp() == 80 and target.occupancy_layer is OccupancyLayer.GROUND
    assert target.action_economy.movement.normalized_score == before - 5
    assert target.action_economy.actions.normalized_score == 1
    assert target.action_economy.bonus_actions.normalized_score == 1
    assert "Restrained" not in target.active_conditions
    assert result.requested_end_position == (3, 3)


@pytest.mark.parametrize("block", ("occupant", "wall"))
def test_success_does_not_invent_another_retreat_when_previous_cell_changes(arena, block):
    target = actor(arena, (2, 3))
    blocker = actor(arena, (6, 3)) if block == "occupant" else None
    materialize_jaw_trap((3, 3))

    def close_exit(event: Event, _source: UUID):
        assert isinstance(event, SavingThrowEvent)
        if blocker is not None:
            Entity.update_entity_position(blocker, (2, 3), parent_event=event.uuid)
        else:
            get_map().set_tile(2, 3, walking_cost=0)
        return None

    target.add_event_handler(EventHandler(name="Exit changes during save", source_entity_uuid=target.uuid,
        trigger_conditions=[Trigger(event_type=EventType.SAVING_THROW, event_phase=EventPhase.EXECUTION,
                                    event_target_entity_uuid=target.uuid)], event_processor=close_exit))
    cursor = EventQueue.event_cursor()
    enter(target, 20, final=(3, 3))
    assert not forced_events(cursor)
    assert target.get_hp() == 80 and "Restrained" not in target.active_conditions


def test_retreat_commits_real_ground_arrival_damage(arena):
    target = actor(arena, (2, 3))
    materialize_spike_trap_condition({(2, 3)}, trap_state=TrapState.ACTIVATED,
        payload=TrapPayload(damages=(TrapDamage(dice_count=1, dice_sides=6, damage_type=DamageType.PIERCING),)))
    jaw = materialize_jaw_trap((3, 3))
    enter(target, 20, 4)
    assert target.get_hp() == 76 and jaw.trap_state is TrapState.ACTIVATED
    assert not jaw.linked_conditions


def test_remote_success_has_no_entry_origin_to_reuse(arena):
    target = actor(arena, (3, 3))
    jaw = materialize_jaw_trap((3, 3))
    cursor = EventQueue.event_cursor()
    pulse(jaw, 20)
    assert target.position == (3, 3) and target.get_hp() == 80
    assert not forced_events(cursor)
