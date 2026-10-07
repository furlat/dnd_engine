"""Position discovery preserves exact costs without spending or selecting templates."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions_functional import execute_available_action, get_available_actions, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.conditions import Incapacitated
from dnd.core.base_actions import ActionAvailabilityStatus
from dnd.core.events import EventQueue
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture
def jumper() -> Iterator[Entity]:
    reset_engine_runtime(grid_size=(11, 11))
    game = Game()
    try:
        actor = Entity.create(uuid4(), "Jumper", config=EntityConfig(
            position=(5, 5), ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=14))))
        setup_standard_actions(actor)
        actor.compose_entity()
        game.deploy_entity(actor, actor.position)
        yield actor
    finally:
        game.close()
        reset_engine_runtime()


@pytest.mark.parametrize("movement_used, bonus_used, incapacitated, expected_status", (
    (0, False, False, ActionAvailabilityStatus.AVAILABLE),
    (20, False, False, ActionAvailabilityStatus.AVAILABLE),
    (30, False, False, ActionAvailabilityStatus.TARGET_COST_UNAFFORDABLE),
    (0, True, False, ActionAvailabilityStatus.SOURCE_UNAFFORDABLE),
    (0, False, True, ActionAvailabilityStatus.SOURCE_UNAFFORDABLE),
))
def test_jump_discovery_preserves_selected_costs_and_native_state(
    jumper: Entity, movement_used: int, bonus_used: bool, incapacitated: bool,
    expected_status: ActionAvailabilityStatus,
) -> None:
    initial = get_available_actions(jumper)
    assert any(row.behavior_id == "action.jump" and row.valid_targets
               for row in initial.position_actions)
    if movement_used:
        jumper.action_economy.consume("movement", movement_used)
    if bonus_used:
        jumper.action_economy.consume("bonus_actions", 1)
    if incapacitated:
        result = jumper.add_condition(Incapacitated(
            source_entity_uuid=jumper.uuid, target_entity_uuid=jumper.uuid))
        assert result is not None and not result.canceled
    cursor = EventQueue.event_cursor()
    templates = [row.model_dump(mode="json") for row in jumper.registered_actions]
    resources = jumper.action_economy.model_dump(mode="json")
    probes = {(6, 5): 5, (7, 5): 10, (8, 5): 15, (9, 5): 20,
              (10, 5): 25, (4, 5): 5, (5, 7): 10, (10, 10): 35}
    expected = ({position: cost for position, cost in probes.items()
                 if cost <= min(25, 30 - movement_used)}
                if expected_status is ActionAvailabilityStatus.AVAILABLE else {})
    previous = None
    for _ in range(3):
        available = get_available_actions(jumper)
        jump = next(row for row in available.position_actions if row.behavior_id == "action.jump")
        assert jump.availability_status is expected_status
        assert jump.can_afford is (expected_status is not ActionAvailabilityStatus.SOURCE_UNAFFORDABLE)
        assert {row.position: row.path_cost for row in jump.valid_targets if row.position in probes} == expected
        if not expected:
            assert jump.valid_targets == []
        assert [row.index for row in jump.valid_targets] == list(range(len(jump.valid_targets)))
        current = jump.model_dump(mode="json")
        if previous is not None:
            assert current == previous
        previous = current
        assert EventQueue.event_cursor() == cursor
        assert jumper.position == (5, 5)
        assert jumper.action_economy.model_dump(mode="json") == resources
        assert [row.model_dump(mode="json") for row in jumper.registered_actions] == templates


@pytest.mark.parametrize("destination, movement_cost", (((6, 5), 5), ((8, 5), 15)))
def test_discovered_jump_executes_with_its_own_distance_cost(
    jumper: Entity, destination: tuple[int, int], movement_cost: int,
) -> None:
    available = get_available_actions(jumper)
    jump = next(row for row in available.position_actions if row.behavior_id == "action.jump")
    target = next(row for row in jump.valid_targets if row.position == destination)
    assert target.path_cost == movement_cost
    before = jumper.action_economy.movement_remaining()
    result = execute_available_action(jumper, jump, target)
    assert result is not None and not result.canceled
    assert jumper.position == destination
    assert jumper.action_economy.movement_remaining() == before - movement_cost
    assert jumper.action_economy.bonus_actions.normalized_score == 0
