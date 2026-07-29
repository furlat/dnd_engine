"""Active regression coverage restored from ``to_archive/examples/test_jump.py``.

The legacy file was removed from active collection during the July test
reorganization.  These tests retain every distinct rule assertion while using
normal pytest assertions and top-level imports.
"""

from uuid import uuid4

import pytest

from dnd.actions import Disengage, Jump, entity_resource_cost_evaluator
from dnd.actions_functional import get_available_actions, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig, RechargeType
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.core.base_actions import Cost, TargetType
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity, EntityConfig
from dnd.monsters.bestiary import create_skeleton
from dnd.reactions import add_opportunity_attack_handler
from tests.engine.support import (
    force_attack_hit,
    get_hp,
    remove_attack_modifier,
    reset_combat_state,
)


def _reset_state(
    *,
    width: int = 20,
    height: int = 20,
    create_rectangle: bool = True,
) -> None:
    reset_combat_state()
    if create_rectangle:
        get_map().create_rectangle(0, 0, width, height)


def _create_jumper(
    *,
    strength: int = 16,
    position: tuple[int, int] = (5, 5),
    faction: str = "heroes",
) -> Entity:
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=strength),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=14),
        ),
        action_economy=ActionEconomyConfig(),
        health=HealthConfig(
            hit_dices=[
                HitDiceConfig(
                    hit_dice_value=10,
                    hit_dice_count=5,
                    mode="maximums",
                )
            ]
        ),
        position=position,
        faction=faction,
    )
    jumper = Entity.create(
        source_entity_uuid=uuid4(),
        name="Legacy Jump Tester",
        config=config,
    )
    setup_standard_actions(jumper)
    return jumper


def _jump_template(entity: Entity) -> Jump:
    template = entity.get_action_template("Jump")
    assert isinstance(template, Jump)
    return template


@pytest.mark.parametrize(
    ("strength", "expected_range"),
    [(10, 15), (18, 35)],
)
def test_jump_range_scales_with_strength(
    strength: int,
    expected_range: int,
) -> None:
    """Legacy ``test_jump.py::test_jump_range_calculation``."""
    _reset_state()
    jumper = _create_jumper(strength=strength)

    jump_range = _jump_template(jumper).get_range()

    assert jump_range is not None
    assert jump_range.normal == expected_range


def test_jump_reaches_visible_island_that_move_cannot_path_to() -> None:
    """Legacy ``test_jump.py::test_jump_valid_positions``."""
    _reset_state(create_rectangle=False)
    grid = get_map()
    for x in range(5):
        for y in range(5):
            grid.set_tile(x, y, walkable=True, visible=True, name="Floor")
    for x in range(5, 8):
        for y in range(5):
            grid.set_tile(x, y, walkable=False, visible=True, name="Water")
    island_positions = {
        (x, y)
        for x in range(8, 11)
        for y in range(2, 5)
    }
    for x, y in island_positions:
        grid.set_tile(x, y, walkable=True, visible=True, name="Island")

    jumper = _create_jumper(strength=18, position=(2, 2))
    Entity.update_all_entities_senses()
    jump_positions = set(_jump_template(jumper).get_valid_positions())
    available = get_available_actions(jumper)
    move_positions = {
        target.position
        for row in available.position_actions
        if row.template_name == "Move"
        for target in row.valid_targets
        if target.position is not None
    }

    assert jump_positions & island_positions
    assert not (move_positions & island_positions)


def test_jump_moves_and_spends_bonus_action_and_distance() -> None:
    """Legacy ``test_jump.py::test_jump_execution``."""
    _reset_state()
    jumper = _create_jumper(strength=16)
    Entity.update_all_entities_senses()
    initial_bonus_actions = jumper.action_economy.bonus_actions.normalized_score
    initial_movement = jumper.action_economy.movement.normalized_score

    event = Jump(
        source_entity_uuid=jumper.uuid,
        end_position=(8, 5),
        template=False,
    ).apply()

    assert event is not None
    assert not event.canceled
    assert jumper.position == (8, 5)
    assert (
        jumper.action_economy.bonus_actions.normalized_score
        == initial_bonus_actions - 1
    )
    assert jumper.action_economy.movement.normalized_score == initial_movement - 15


def test_jump_declares_bonus_action_before_target_distance_cost() -> None:
    """Jump owns one ordered typed cost list before the event enters the queue."""
    _reset_state()
    jumper = _create_jumper(strength=16)
    Entity.update_all_entities_senses()
    jump = Jump(
        source_entity_uuid=jumper.uuid,
        end_position=(8, 5),
        template=False,
    )

    effective_costs = [
        (cost.cost_type, cost.cost)
        for cost in jump.effective_costs
    ]
    declaration = jump._create_declaration_event(use_register=False)

    assert effective_costs == [
        ("bonus_actions", 1),
        ("movement", 15),
    ]
    assert declaration is not None
    assert [
        (cost.cost_type, cost.cost)
        for cost in declaration.costs
    ] == effective_costs
    assert [
        (cost.cost_type, cost.cost)
        for cost in jump.costs
    ] == [("bonus_actions", 1)]


def test_jump_pays_named_resources_without_double_spending_movement() -> None:
    """The movement exception still uses the canonical named-resource payer."""
    _reset_state()
    jumper = _create_jumper(strength=16)
    jumper.action_economy.add_resource(
        "jump_tokens",
        maximum=1,
        recharge_type=RechargeType.LONG_REST,
    )
    Entity.update_all_entities_senses()
    jump = Jump(
        source_entity_uuid=jumper.uuid,
        end_position=(8, 5),
        template=False,
        alt_extra_costs=[
            Cost(
                name="Jump Token",
                cost_type="bonus_actions",
                cost=0,
                resource_name="jump_tokens",
                resource_cost=1,
                resource_evaluator=entity_resource_cost_evaluator,
            )
        ],
    )

    result = jump.apply()

    assert result is not None and not result.canceled
    assert jumper.action_economy.get_resource_current("jump_tokens") == 0
    assert jumper.action_economy.movement.normalized_score == 15


def test_jump_rejects_an_occupied_landing_position() -> None:
    """Legacy ``test_jump.py::test_jump_occupied_position``."""
    _reset_state()
    jumper = _create_jumper()
    blocker = _create_jumper(position=(8, 5), faction="monsters")
    Entity.update_all_entities_senses()

    event = Jump(
        source_entity_uuid=jumper.uuid,
        end_position=blocker.position,
        template=False,
    ).apply()

    assert event is None or event.canceled
    assert jumper.position == (5, 5)


def test_jump_range_is_capped_by_remaining_movement_budget() -> None:
    """Legacy ``test_jump.py::test_jump_movement_budget``."""
    _reset_state(width=30, height=30)
    jumper = _create_jumper(strength=20)
    Entity.update_all_entities_senses()
    jumper.action_economy.movement.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=jumper.uuid,
            target_entity_uuid=jumper.uuid,
            name="Spend all but five feet",
            value=-25,
        )
    )

    too_far = Jump(
        source_entity_uuid=jumper.uuid,
        end_position=(9, 5),
        template=False,
    ).apply()

    assert too_far is None or too_far.canceled
    assert jumper.position == (5, 5)
    assert jumper.action_economy.bonus_actions.normalized_score == 1

    affordable = Jump(
        source_entity_uuid=jumper.uuid,
        end_position=(6, 5),
        template=False,
    ).apply()

    assert affordable is not None
    assert not affordable.canceled
    assert jumper.position == (6, 5)
    assert jumper.action_economy.movement.normalized_score == 0
    assert jumper.action_economy.bonus_actions.normalized_score == 0


def test_jump_discovery_uses_position_los_targets() -> None:
    """Legacy ``test_jump.py::test_jump_in_available_actions``."""
    _reset_state()
    jumper = _create_jumper(strength=14)
    Entity.update_all_entities_senses()

    available = get_available_actions(jumper)
    jump_row = next(
        row
        for row in available.position_actions
        if row.template_name == "Jump"
    )

    assert jump_row.target_type is TargetType.POSITION_LOS
    assert jump_row.valid_targets


def test_jump_provokes_opportunity_attack_when_leaving_reach() -> None:
    """Legacy ``test_jump.py::test_jump_provokes_opportunity_attack``."""
    _reset_state()
    jumper = _create_jumper()
    watcher = create_skeleton(
        name="Jump Watcher",
        position=(6, 5),
        faction="monsters",
    )
    add_opportunity_attack_handler(watcher)
    Entity.update_all_entities_senses()
    hit_modifier = force_attack_hit(watcher)
    hp_before = get_hp(jumper)

    event = Jump(
        source_entity_uuid=jumper.uuid,
        end_position=(5, 8),
        template=False,
    ).apply()

    remove_attack_modifier(watcher, hit_modifier)
    assert event is not None
    assert not event.canceled
    assert jumper.position == (5, 8)
    assert get_hp(jumper) < hp_before
    assert watcher.action_economy.reactions.normalized_score == 0


def test_disengage_prevents_opportunity_attack_during_jump() -> None:
    """Legacy ``test_jump.py::test_jump_disengage_prevents_oa``."""
    _reset_state()
    jumper = _create_jumper()
    watcher = create_skeleton(
        name="Disengaged Jump Watcher",
        position=(6, 5),
        faction="monsters",
    )
    add_opportunity_attack_handler(watcher)
    Entity.update_all_entities_senses()
    disengage_event = Disengage(
        source_entity_uuid=jumper.uuid,
        template=False,
    ).apply()
    assert disengage_event is not None
    assert not disengage_event.canceled
    hit_modifier = force_attack_hit(watcher)
    hp_before = get_hp(jumper)

    event = Jump(
        source_entity_uuid=jumper.uuid,
        end_position=(5, 8),
        template=False,
    ).apply()

    remove_attack_modifier(watcher, hit_modifier)
    assert event is not None
    assert not event.canceled
    assert jumper.position == (5, 8)
    assert get_hp(jumper) == hp_before
    assert watcher.action_economy.reactions.normalized_score == 1
