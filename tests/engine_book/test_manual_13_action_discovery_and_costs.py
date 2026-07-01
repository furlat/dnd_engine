"""Manual Chapter 13 checks for action discovery and costs."""

from uuid import uuid4

from dnd.actions import Dash, MovementEvent
from dnd.actions_functional import execute_by_index, get_available_actions, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.core.base_actions import ActionCategory, AvailableActionInfo, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.core.values import BaseValue
from dnd.entity import Entity, EntityConfig
from dnd.items.test_items import create_healing_potion
from dnd.utils import reset_combat_state


def reset_action_state(width: int = 10, height: int = 10) -> None:
    """Clear global state and create a small action-discovery arena."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    get_map().create_rectangle(0, 0, width, height)


def create_action_actor(
    name: str,
    position: tuple[int, int],
    faction: str | None,
    strength: int = 14,
) -> Entity:
    """Create an actor with health, movement, and standard action templates."""
    actor_id = uuid4()
    actor = Entity.create(
        source_entity_uuid=actor_id,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=strength),
                dexterity=AbilityConfig(ability_score=14),
                constitution=AbilityConfig(ability_score=12),
                intelligence=AbilityConfig(ability_score=10),
                wisdom=AbilityConfig(ability_score=12),
                charisma=AbilityConfig(ability_score=10),
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(hit_dice_value=8, hit_dice_count=2, mode="maximums")
                ],
            ),
            action_economy=ActionEconomyConfig(movement=30),
            proficiency_bonus=2,
            position=position,
            faction=faction,
        ),
    )
    setup_standard_actions(actor)
    return actor


def find_action(actions, template_name: str) -> AvailableActionInfo:
    """Return the discovery row with the requested template name."""
    for action_info in actions.all_actions:
        if action_info.template_name == template_name:
            return action_info
    raise AssertionError(f"{template_name} was not discovered")


def test_templates_register_as_reusable_actions_and_instantiate_for_execution() -> None:
    """Registered actions are templates; executable actions are instances."""
    reset_action_state()
    hero = create_action_actor("Hero", (1, 1), "heroes")

    non_template = Dash(source_entity_uuid=hero.uuid, template=False)
    try:
        hero.register_action(non_template)
    except ValueError as exc:
        assert "template" in str(exc)
    else:
        raise AssertionError("register_action accepted a non-template action")

    template = Dash(source_entity_uuid=hero.uuid, template=True)
    hero.register_action(template)
    assert hero.get_action_template("Dash") is not None

    try:
        template.apply()
    except ValueError as exc:
        assert "Cannot apply template" in str(exc)
    else:
        raise AssertionError("template.apply() did not raise")

    instance = template.instantiate()
    assert instance.template is False
    assert instance.uuid != template.uuid
    assert instance.source_entity_uuid == template.source_entity_uuid
    assert instance.use_register is False


def test_standard_actions_discover_grouped_self_position_and_entity_choices() -> None:
    """Discovery groups actions and exposes indexed targets for the UI."""
    reset_action_state()
    hero = create_action_actor("Hero", (1, 1), "heroes", strength=18)
    goblin = create_action_actor("Goblin", (2, 1), "monsters")
    Entity.update_all_entities_senses(max_distance=10)

    available = get_available_actions(hero)
    self_names = {info.template_name for info in available.self_actions}
    position_names = {info.template_name for info in available.position_actions}
    entity_names = {info.template_name for info in available.entity_actions}

    assert available.entity_uuid == hero.uuid
    assert available.remaining_movement == 30
    assert {"Dash", "Dodge", "Disengage"}.issubset(self_names)
    assert {"Move", "Jump"}.issubset(position_names)
    assert "Shove" in entity_names
    assert available.all_actions == (
        available.entity_actions
        + available.position_actions
        + available.self_actions
        + available.object_actions
    )

    dash_info = find_action(available, "Dash")
    assert dash_info.target_type == TargetType.SELF
    assert dash_info.valid_targets[0].index == 0
    assert dash_info.cost_type == "actions"
    assert dash_info.cost_amount == 1
    assert dash_info.can_afford is True

    move_info = find_action(available, "Move")
    assert move_info.target_type == TargetType.POSITION_PATH
    assert move_info.action_category == ActionCategory.MOVEMENT
    assert any(target.position == (3, 1) and target.path for target in move_info.valid_targets)

    shove_info = find_action(available, "Shove")
    assert shove_info.target_type == TargetType.ENTITY
    assert shove_info.valid_targets[0].target_uuid == goblin.uuid
    assert shove_info.valid_targets[0].target_name == "Goblin"


def test_execute_by_index_instantiates_self_action_and_consumes_cost() -> None:
    """Executing by discovery index applies the selected template and cost."""
    reset_action_state()
    hero = create_action_actor("Hero", (1, 1), "heroes")
    available = get_available_actions(hero)
    dash_info = find_action(available, "Dash")

    result = execute_by_index(hero, "Dash", dash_info.valid_targets[0].index, available=available)

    assert result is not None
    assert not result.canceled
    assert "Dashing" in hero.active_conditions
    assert hero.action_economy.actions.normalized_score == 0
    assert hero.action_economy.movement.normalized_score == 60

    after = get_available_actions(hero)
    dash_after = find_action(after, "Dash")
    assert dash_after.can_afford is False
    assert dash_after.valid_targets == []


def test_position_targets_carry_path_metadata_and_execute_by_index() -> None:
    """Position actions expose target indexes, paths, path costs, and execution."""
    reset_action_state()
    hero = create_action_actor("Hero", (1, 1), "heroes")
    Entity.update_all_entities_senses(max_distance=10)
    available = get_available_actions(hero)
    move_info = find_action(available, "Move")
    move_target = next(target for target in move_info.valid_targets if target.position == (3, 1))

    assert move_target.index >= 0
    assert move_target.distance == 10
    assert move_target.path == [(1, 1), (2, 1), (3, 1)]
    assert move_target.path_cost == 10

    movement_before = hero.action_economy.movement.normalized_score
    result = execute_by_index(hero, "Move", move_target.index, available=available)

    assert isinstance(result, MovementEvent)
    assert not result.canceled
    assert result.path == move_target.path
    assert hero.position == (3, 1)
    assert hero.action_economy.movement.normalized_score == movement_before - 10


def test_target_filters_shape_entity_action_targets() -> None:
    """Discovery target filters choose enemy, ally, or all visible targets."""
    reset_action_state()
    hero = create_action_actor("Hero", (1, 1), "heroes", strength=18)
    ally = create_action_actor("Ally", (1, 2), "heroes")
    enemy = create_action_actor("Enemy", (2, 1), "monsters")
    Entity.update_all_entities_senses(max_distance=10)

    enemy_targets = find_action(hero.get_available_actions(), "Shove").valid_targets
    ally_targets = find_action(hero.get_available_actions(target_filter="allies"), "Shove").valid_targets
    all_targets = find_action(hero.get_available_actions(target_filter="all"), "Shove").valid_targets

    assert {target.target_uuid for target in enemy_targets} == {enemy.uuid}
    assert {target.target_uuid for target in ally_targets} == {ally.uuid}
    assert {target.target_uuid for target in all_targets} == {enemy.uuid, ally.uuid}


def test_floor_items_create_object_actions_and_pickup_execution() -> None:
    """Visible floor items appear as object targets and can be picked up."""
    reset_action_state()
    hero = create_action_actor("Hero", (3, 3), "heroes")
    potion = create_healing_potion(uuid4())
    potion.place_on_grid((4, 3))
    Entity.update_all_entities_senses(max_distance=10)

    available = get_available_actions(hero)
    pickup_info = find_action(available, "Pick Up")
    potion_target = next(
        target for target in pickup_info.valid_targets if target.target_uuid == potion.uuid
    )

    assert pickup_info.target_type == TargetType.OBJECT
    assert pickup_info.cost_amount == 0
    assert potion_target.target_name == "Potion of Healing"
    assert potion_target.distance == 5

    result = execute_by_index(hero, "Pick Up", potion_target.index, available=available)

    assert result is not None
    assert not result.canceled
    assert potion.uuid in hero.inventory.items
    assert get_map().get_object_position(potion.uuid) is None


def test_inventory_use_actions_surface_item_metadata_and_consume_the_item() -> None:
    """Usable inventory items add action rows with item metadata."""
    reset_action_state()
    hero = create_action_actor("Hero", (3, 3), "heroes")
    potion = create_healing_potion(hero.uuid, heal_amount=7)
    assert hero.loot_item(potion)

    available = get_available_actions(hero)
    potion_info = next(
        info
        for info in available.self_actions
        if info.is_item_use and info.source_item_uuid == potion.uuid
    )

    assert potion_info.template_name.startswith("Drink Potion__item_")
    assert potion_info.display_name == "Drink Potion (Potion of Healing)"
    assert potion_info.target_type == TargetType.SELF
    assert potion_info.valid_targets[0].index == 0
    assert potion_info.cost_amount == 0

    result = execute_by_index(
        hero,
        potion_info.template_name,
        potion_info.valid_targets[0].index,
        available=available,
    )

    assert result is not None
    assert not result.canceled
    assert potion.uuid not in hero.inventory.items
    assert BaseBlock.get(potion.uuid) is None
