"""Held door requests respect occupants and close under the departure lineage."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest

from dnd.actions import Move
from dnd.actions_functional import setup_standard_actions
from dnd.content.items.environment_item_builders import build_directional_door
from dnd.core.events import Event, EventPhase, EventQueue, EventType, SpatialChangeEvent
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.environment import DirectionalDoor
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world import CardinalDirection


DOORWAY = (3, 1)


@pytest.fixture
def game() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(7, 4))
    instance = Game()
    yield instance
    instance.close()
    reset_engine_runtime()


def occupied_door(game: Game) -> tuple[DirectionalDoor, Entity]:
    door = build_directional_door(is_open=True)
    door.place_on_grid(DOORWAY, boundary_direction=CardinalDirection.EAST)
    occupant = Entity.create(uuid4(), "Crossing occupant", config=EntityConfig(position=DOORWAY))
    setup_standard_actions(occupant)
    occupant.compose_entity()
    game.deploy_entity(occupant, DOORWAY)
    return door, occupant


def request(door: DirectionalDoor, value: bool, controller: UUID, *, defer: bool = True) -> tuple[bool, Event]:
    cause = EventQueue.publish_declaration(Event(
        name="Door control input", event_type=EventType.BASE_ACTION,
        source_entity_uuid=controller, phase=EventPhase.DECLARATION, use_register=False,
    ))
    cause = cause.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
    achieved = door.request_open(value, parent_event=cause, controller_uuid=controller, defer_close=defer)
    return achieved, cause.phase_to(EventPhase.COMPLETION)


def walk_out(occupant: Entity) -> Event:
    occupant.update_entity_senses()
    result = Move(source_entity_uuid=occupant.uuid, end_position=(3, 2),
                  path=[DOORWAY, (3, 2)], prefer_safe=False).apply()
    assert result is not None and not result.canceled, result.status_message if result is not None else None
    assert occupant.position == (3, 2)
    return result


def completed_door_changes(door: DirectionalDoor, cursor: int) -> list[SpatialChangeEvent]:
    return [event for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, SpatialChangeEvent)
            and event.phase is EventPhase.COMPLETION
            and event.event_type is EventType.SPATIAL_OBJECT_CHANGED
            and event.object_uuid == door.uuid]


def root_of(event: Event) -> Event:
    while event.parent_event is not None:
        parent = EventQueue.get_event_by_uuid(event.parent_event)
        assert parent is not None
        event = parent
    return event


def test_held_close_waits_then_belongs_to_departure_not_completed_request(game: Game) -> None:
    door, occupant = occupied_door(game)
    cursor = EventQueue.event_cursor()
    achieved, original = request(door, False, uuid4())
    assert not achieved and door.is_open
    assert not completed_door_changes(door, cursor)

    movement = walk_out(occupant)

    assert not door.is_open
    change, = completed_door_changes(door, cursor)
    assert change.object_is_open is False
    assert root_of(change).lineage_uuid == movement.lineage_uuid
    assert root_of(change).lineage_uuid != original.lineage_uuid
    assert change.parent_event is not None
    departure = EventQueue.get_event_by_uuid(change.parent_event)
    assert departure is not None
    assert departure.event_type is EventType.SPATIAL_ENTITY_LEFT
    assert departure.phase is EventPhase.EFFECT


@pytest.mark.parametrize("operation", ("request", "direct"))
def test_ordinary_close_respects_occupied_door_and_does_not_retry(game: Game, operation: str) -> None:
    door, occupant = occupied_door(game)
    if operation == "request":
        achieved, _ = request(door, False, uuid4(), defer=False)
        assert not achieved
    else:
        door.close()
    assert door.is_open
    walk_out(occupant)
    assert door.is_open


@pytest.mark.parametrize("supersession", ("repress", "explicit_open", "explicit_close"))
def test_new_explicit_request_supersedes_pending_close(game: Game, supersession: str) -> None:
    door, occupant = occupied_door(game)
    controller = uuid4()
    request(door, False, controller)
    if supersession == "repress":
        achieved, _ = request(door, True, controller)
        assert achieved
    elif supersession == "explicit_open":
        door.open()
    else:
        door.close()  # Refused occupancy still supersedes the old held request.
    walk_out(occupant)
    assert door.is_open


@pytest.mark.parametrize("withdraw_current", (False, True))
def test_only_current_controller_can_withdraw_pending_close(game: Game, withdraw_current: bool) -> None:
    door, occupant = occupied_door(game)
    first, current = uuid4(), uuid4()
    request(door, False, first)
    request(door, False, current)
    door.cancel_pending_close(current if withdraw_current else first)
    walk_out(occupant)
    assert door.is_open is withdraw_current


def test_removing_occupant_also_resolves_pending_close(game: Game) -> None:
    door, occupant = occupied_door(game)
    request(door, False, uuid4())
    cursor = EventQueue.event_cursor()
    game.remove_entity(occupant.uuid)
    assert not door.is_open
    change, = completed_door_changes(door, cursor)
    assert change.parent_event is not None
    departure = EventQueue.get_event_by_uuid(change.parent_event)
    assert isinstance(departure, SpatialChangeEvent)
    assert departure.entity_uuid == occupant.uuid
    assert departure.occupancy_layer is None


@pytest.mark.parametrize("removal", ("remove", "destroy"))
def test_removed_door_discards_pending_request_and_subscription(game: Game, removal: str) -> None:
    door, occupant = occupied_door(game)
    request(door, False, uuid4())
    if removal == "remove":
        assert get_map().remove_object(door.uuid)
        door.place_on_grid(DOORWAY, boundary_direction=CardinalDirection.EAST)
    else:
        door.destroy()
    assert all(handler.source_entity_uuid != door.uuid for handler in EventQueue.get_spatial_handlers_at(
        DOORWAY, EventType.SPATIAL_ENTITY_LEFT, EventPhase.EFFECT))
    cursor = EventQueue.event_cursor()
    walk_out(occupant)
    assert door.is_open
    assert not completed_door_changes(door, cursor)


def test_unoccupied_request_commits_under_the_current_input(game: Game) -> None:
    door = build_directional_door(is_open=True)
    door.place_on_grid(DOORWAY, boundary_direction=CardinalDirection.EAST)
    cursor = EventQueue.event_cursor()
    achieved, cause = request(door, False, uuid4())
    assert achieved and not door.is_open
    change, = completed_door_changes(door, cursor)
    assert root_of(change).lineage_uuid == cause.lineage_uuid
