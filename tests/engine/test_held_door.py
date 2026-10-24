"""A door on an edge is used from either of its two cells, and nobody standing beside it blocks it."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest

from dnd.actions import Move
from dnd.actions_functional import setup_standard_actions, get_available_actions, execute_available_action
from dnd.content.items.environment_item_builders import build_directional_door
from dnd.core.events import Event, EventPhase, EventQueue, EventType, SpatialChangeEvent, StepMovementEvent
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


def request(door: DirectionalDoor, value: bool, controller: UUID) -> tuple[bool, Event]:
    cause = EventQueue.publish_declaration(Event(
        name="Door control input", event_type=EventType.BASE_ACTION,
        source_entity_uuid=controller, phase=EventPhase.DECLARATION, use_register=False,
    ))
    cause = cause.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
    achieved = door.request_open(value, parent_event=cause)
    return achieved, cause.phase_to(EventPhase.COMPLETION)


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


def door_row(entity: Entity, name: str):
    entity.update_entity_senses()
    entity.action_economy.reset_all_costs()
    return next(row for row in get_available_actions(entity).all_actions if row.template_name.split("__")[0] == name)


def test_a_door_on_an_edge_closes_and_opens_from_either_cell_whoever_stands_beside_it(game: Game) -> None:
    door, occupant = occupied_door(game)  # someone on each side of the open door
    other = Entity.create(uuid4(), "Other side", config=EntityConfig(position=(4, 1)))
    setup_standard_actions(other)
    other.compose_entity()
    game.deploy_entity(other, (4, 1))
    for user in (occupant, other):
        for name, is_open in (("Close Door", False), ("Open Door", True)):
            row = door_row(user, name)
            result = execute_available_action(user, row, row.valid_targets[0])
            assert result is not None and not result.canceled and door.is_open is is_open


def test_a_control_closes_its_door_at_once_whoever_stands_beside_it(game: Game) -> None:
    door, _ = occupied_door(game)
    achieved, _ = request(door, False, uuid4())
    assert achieved and not door.is_open


@pytest.mark.parametrize('allied', (True, False))
def test_open_door_route_can_cross_an_ally_but_cannot_end_on_them(game: Game, allied: bool) -> None:
    # A one-cell passage makes crossing the occupant the only route.
    grid = get_map()
    for x in range(7):
        for y in (0, 2, 3):
            grid.remove_tile(x, y)
    door, occupant = occupied_door(game)
    occupant.faction = 'party' if allied else 'enemy'
    mover = Entity.create(uuid4(), 'Walker', config=EntityConfig(position=(2, 1), faction='party'))
    setup_standard_actions(mover)
    mover.compose_entity()
    game.deploy_entity(mover, mover.position)
    Entity.update_all_entities_senses()
    choices = get_available_actions(mover)
    move = next(row for row in choices.all_actions if row.behavior_id == 'action.move')
    assert not any(target.position == occupant.position for target in move.valid_targets)
    target = next((target for target in move.valid_targets if target.position == (4, 1)), None)
    if not allied:
        assert target is None
        return
    assert target is not None
    assert target.path == [(2, 1), (3, 1), (4, 1)]
    remaining = mover.action_economy.movement_remaining()
    rejected = Move(source_entity_uuid=mover.uuid, end_position=occupant.position,
                    path=[mover.position, occupant.position], prefer_safe=False).apply()
    assert rejected is not None and rejected.canceled
    assert mover.position == (2, 1)
    assert mover.action_economy.movement_remaining() == remaining
    result = execute_available_action(mover, move, target)
    assert result is not None and not result.canceled
    assert mover.position == (4, 1)
    assert occupant.position == DOORWAY


def test_opening_two_doors_refreshes_the_exact_route_through_a_party_member(game: Game) -> None:
    grid = get_map()
    for x in range(7):
        for y in (0, 2, 3):
            grid.remove_tile(x, y)
    doors = tuple(build_directional_door(is_open=False) for _ in range(2))
    for door, position in zip(doors, ((2, 1), (4, 1))):
        door.place_on_grid(position, boundary_direction=CardinalDirection.EAST)
    heroes = tuple(Entity.create(uuid4(), name, config=EntityConfig(position=position, faction="party"))
                   for name, position in (("Walker", (2, 1)), ("Ally", (3, 1))))
    for hero in heroes:
        setup_standard_actions(hero)
        hero.compose_entity()
        game.deploy_entity(hero, hero.position)
    mover, ally = heroes
    Entity.update_all_entities_senses()
    for door in doors:
        before = get_available_actions(mover)
        assert not any(target.position == (5, 1) for row in before.all_actions
                       if row.behavior_id == "action.move" for target in row.valid_targets)
        achieved, _ = request(door, True, mover.uuid)
        assert achieved
    choices = get_available_actions(mover)
    move = next(row for row in choices.all_actions if row.behavior_id == "action.move")
    selected = next(target for target in move.valid_targets if target.position == (5, 1))
    assert selected.path == [(2, 1), (3, 1), (4, 1), (5, 1)]
    cursor = EventQueue.event_cursor()
    result = execute_available_action(mover, move, selected)
    assert result is not None and not result.canceled
    steps = [event.to_position for _, event in EventQueue.iter_events_since(cursor)
             if isinstance(event, StepMovementEvent) and event.phase is EventPhase.COMPLETION and event.committed]
    assert steps == selected.path[1:]
    assert mover.position == (5, 1) and ally.position == (3, 1)


@pytest.mark.parametrize('position, admitted', [((3, 1), True), ((4, 1), True),
                                               ((2, 1), False), ((3, 2), False), ((5, 1), False)])
def test_wall_door_hand_use_requires_one_of_its_two_incident_cells(game: Game, position, admitted):
    door = build_directional_door(is_open=False)
    door.place_on_grid(DOORWAY, boundary_direction=CardinalDirection.EAST)
    actor = Entity.create(uuid4(), 'Door user', config=EntityConfig(position=position))
    setup_standard_actions(actor)
    actor.compose_entity()
    game.deploy_entity(actor, position)
    Entity.update_all_entities_senses()
    assert (get_map().manual_object_contact(actor.uuid, door.uuid) is not None) is admitted
    choices = get_available_actions(actor)
    usable = [row for row in choices.all_actions if row.source_item_uuid == door.uuid and row.valid_targets]
    assert bool(usable) is admitted


def test_unoccupied_request_commits_under_the_current_input(game: Game) -> None:
    door = build_directional_door(is_open=True)
    door.place_on_grid(DOORWAY, boundary_direction=CardinalDirection.EAST)
    cursor = EventQueue.event_cursor()
    achieved, cause = request(door, False, uuid4())
    assert achieved and not door.is_open
    change, = completed_door_changes(door, cursor)
    assert root_of(change).lineage_uuid == cause.lineage_uuid
