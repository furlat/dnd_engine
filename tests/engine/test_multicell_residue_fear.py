"""A connected dread pool has one entry response, not a per-tile bounce."""

import pytest

from dnd.actions import Jump
from dnd.conditions import Frightened
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue, SavingThrowEvent, StepMovementEvent
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.game import Game
from dnd.residues import DREAD_RESIDUE, deposit_residue
from dnd.spells.conjuration import MistyStep
from tests.engine.test_residue_fear import actor, completed, game as game, walk


def pool_cells(positions: set[tuple[int, int]]) -> None:
    for position in sorted(positions):
        tile = get_map().get_tile(*position)
        assert tile is not None
        assert deposit_residue(tile, DREAD_RESIDUE) is not None
    Entity.update_all_entities_senses()


def fear_changes(cursor: int):
    events = completed(cursor)
    return [event for event in events if isinstance(event, (ConditionApplicationEvent, ConditionRemovalEvent))
            and event.condition_state is not None and event.condition_state.name == "Frightened"]


def test_successful_boundary_save_covers_internal_cells_until_real_exit_and_reentry(game: Game) -> None:
    traveler = actor(game, (0, 1))
    pool_cells({(1, 1), (2, 1), (3, 1)})
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(20, 20):
        result = walk(traveler, [(0, 1), (1, 1), (2, 1), (3, 1), (4, 1)])
        assert not result.canceled and traveler.position == (4, 1)
        result = walk(traveler, [(4, 1), (3, 1)])
    assert not result.canceled and traveler.position == (3, 1)
    assert len([event for event in completed(cursor) if isinstance(event, SavingThrowEvent)]) == 2
    assert not fear_changes(cursor)
    assert traveler.action_economy.movement.normalized_score == 5


@pytest.mark.parametrize("entry", ("teleport", "jump"))
def test_deep_arrival_pays_one_step_then_keeps_one_fear_and_outward_heading(game: Game, entry: str) -> None:
    traveler = actor(game, (0, 1), caster=entry == "teleport")
    pool_cells({(x, y) for x in (2, 3, 4) for y in (0, 1, 2)})
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(1):
        result = (MistyStep(source_entity_uuid=traveler.uuid, end_position=(3, 1)).apply()
                  if entry == "teleport" else Jump(source_entity_uuid=traveler.uuid, end_position=(3, 1)).apply())
    assert result is not None and not result.canceled
    assert traveler.position == (2, 1)
    fear = traveler.active_conditions["Frightened"]
    assert isinstance(fear, Frightened)
    assert fear.residue_origin is not None and fear.residue_origin.position == (3, 1)
    assert len([event for event in completed(cursor) if isinstance(event, SavingThrowEvent)]) == 1
    assert len(fear_changes(cursor)) == 1
    expected_budget = 25 if entry == "teleport" else 10
    assert traveler.action_economy.movement.normalized_score == expected_budget

    blocked = walk(traveler, [(2, 1), (3, 1)])
    assert blocked.canceled and traveler.position == (2, 1)
    assert traveler.action_economy.movement.normalized_score == expected_budget
    assert traveler.active_conditions["Frightened"].uuid == fear.uuid
    exit_move = walk(traveler, [(2, 1), (1, 1)])
    assert not exit_move.canceled and traveler.position == (1, 1)
    assert traveler.action_economy.movement.normalized_score == expected_budget - 5
    assert "Frightened" not in traveler.active_conditions
    assert len(fear_changes(cursor)) == 2
    steps = [event for event in completed(cursor) if isinstance(event, StepMovementEvent) and event.committed]
    assert [(step.from_position, step.to_position) for step in steps][-2:] == [((3, 1), (2, 1)), ((2, 1), (1, 1))]


def test_exhausted_deep_entrant_keeps_fear_then_can_retreat_across_multiple_cells(game: Game) -> None:
    traveler = actor(game, (0, 1), movement=15, caster=True)
    traveler.action_economy.consume("movement", 15)
    pool_cells({(2, 1), (3, 1), (4, 1)})
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(1):
        result = MistyStep(source_entity_uuid=traveler.uuid, end_position=(4, 1)).apply()
    assert result is not None and not result.canceled and traveler.position == (4, 1)
    fear_uuid = traveler.active_conditions["Frightened"].uuid
    traveler.on_turn_end()
    traveler.on_turn_start(round_number=2)
    result = walk(traveler, [(4, 1), (3, 1), (2, 1)])
    assert not result.canceled and traveler.position == (2, 1)
    assert traveler.active_conditions["Frightened"].uuid == fear_uuid
    result = walk(traveler, [(2, 1), (1, 1)])
    assert not result.canceled and traveler.position == (1, 1)
    assert traveler.action_economy.movement.normalized_score == 0
    assert "Frightened" not in traveler.active_conditions
    assert len([event for event in completed(cursor) if isinstance(event, SavingThrowEvent)]) == 1


def test_removing_old_entry_cell_keeps_fear_but_removing_current_material_releases_it(game: Game) -> None:
    traveler = actor(game, (0, 1), caster=True)
    pool_cells({(2, 1), (3, 1)})
    with fixed_dice_faces(1):
        result = MistyStep(source_entity_uuid=traveler.uuid, end_position=(3, 1)).apply()
    assert result is not None and not result.canceled and traveler.position == (2, 1)
    fear_uuid = traveler.active_conditions["Frightened"].uuid
    former = get_map().get_tile(3, 1)
    current = get_map().get_tile(2, 1)
    assert former is not None and current is not None
    assert former.remove_condition(DREAD_RESIDUE.name)
    assert traveler.active_conditions["Frightened"].uuid == fear_uuid
    assert current.remove_condition(DREAD_RESIDUE.name)
    assert "Frightened" not in traveler.active_conditions


@pytest.mark.parametrize("connected", (True, False))
def test_teleport_between_material_cells_checks_the_actual_connected_region(game: Game, connected: bool) -> None:
    traveler = actor(game, (1, 1), caster=True)
    pool_cells({(1, 1), (2, 1), (3, 1)} if connected else {(1, 1), (3, 1)})
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(1):
        result = MistyStep(source_entity_uuid=traveler.uuid, end_position=(3, 1)).apply()
    assert result is not None and not result.canceled
    assert traveler.position == ((3, 1) if connected else (2, 1))
    assert len([event for event in completed(cursor) if isinstance(event, SavingThrowEvent)]) == int(not connected)
    assert "Frightened" not in traveler.active_conditions
