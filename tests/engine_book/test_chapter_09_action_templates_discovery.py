"""Engine book parity tests for action templates, costs, and discovery."""

from typing import cast
from uuid import uuid4

from dnd.actions import Dash, MovementEvent, SpellEvent
from dnd.actions_functional import (
    apply_action_overrides,
    clear_action_overrides,
    execute_by_index,
    get_available_actions,
    register_spell,
    setup_standard_actions,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.base_item import BaseItem
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.base_actions import ActionCategory, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import HazardFilter
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.core.modifiers import DamageType
from dnd.core.values import BaseValue
from dnd.entity import Entity, EntityConfig
from dnd.items.consumables import HEALING_POTION_RECIPE
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.spells import Fireball, MagicMissile
from dnd.utils import reset_combat_state


def reset_action_state() -> None:
    """Clear global state touched by these action examples."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    get_map().create_rectangle(0, 0, 20, 20)


def configured_entity(
    name: str = "Hero",
    position: tuple[int, int] = (2, 2),
    faction: str | None = "heroes",
) -> Entity:
    """Create a deterministic entity with standard actions registered."""
    source_uuid = uuid4()
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=14),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=12),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=12),
            charisma=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(
            hit_dices=[
                HitDiceConfig(hit_dice_value=8, hit_dice_count=2, mode="maximums")
            ]
        ),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(source_entity_uuid=source_uuid, name=name, config=config)
    setup_standard_actions(entity)
    return entity


def find_action(actions, template_name: str):
    """Find an action info by exact template name."""
    for info in actions.all_actions:
        if info.template_name == template_name:
            return info
    raise AssertionError(
        f"{template_name!r} not found in {[info.template_name for info in actions.all_actions]}"
    )


def find_attack_action(actions):
    """Find the first attack action in an available-actions result."""
    for info in actions.entity_actions:
        if info.is_attack:
            return info
    raise AssertionError("No attack action found")


def test_eb_09_001_templates_must_be_registered_and_instantiated() -> None:
    """EB-09-001: only templates register; templates instantiate into ephemeral actions."""
    reset_action_state()
    entity = configured_entity()

    non_template = Dash(source_entity_uuid=entity.uuid, template=False)
    try:
        entity.register_action(non_template)
    except ValueError as exc:
        assert "template" in str(exc)
    else:
        raise AssertionError("register_action accepted a non-template action")

    template = Dash(source_entity_uuid=entity.uuid, template=True)
    entity.register_action(template)
    assert entity.get_action_template("Dash") is not None

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


def test_eb_09_002_standard_actions_discover_self_position_and_entity_groups() -> None:
    """EB-09-002: standard setup produces grouped available actions."""
    reset_action_state()
    goblin = create_goblin(name="Goblin", position=(5, 5), faction="heroes")
    skeleton = create_skeleton(name="Skeleton", position=(6, 5), faction="monsters")
    Entity.update_all_entities_senses()

    available = get_available_actions(goblin)
    self_names = {info.template_name for info in available.self_actions}
    position_names = {info.template_name for info in available.position_actions}

    assert available.entity_uuid == goblin.uuid
    assert available.remaining_movement == goblin.action_economy.movement.normalized_score
    assert {"Dash", "Dodge", "Disengage"}.issubset(self_names)
    assert "Hide" not in self_names
    assert "Move" in position_names
    assert "Jump" in position_names

    dash_info = find_action(available, "Dash")
    assert dash_info.target_type == TargetType.SELF
    assert dash_info.valid_targets[0].index == 0
    assert dash_info.cost_type == "actions"
    assert dash_info.cost_amount == 1
    assert dash_info.can_afford is True

    move_info = find_action(available, "Move")
    assert move_info.target_type == TargetType.POSITION_PATH
    assert move_info.action_category == ActionCategory.MOVEMENT
    assert move_info.valid_targets
    assert move_info.valid_targets[0].position is not None
    assert move_info.valid_targets[0].path is not None

    jump_info = find_action(available, "Jump")
    assert jump_info.target_type == TargetType.POSITION_LOS

    attack_infos = [info for info in available.entity_actions if info.is_attack]
    assert attack_infos
    attack_info = attack_infos[0]
    assert attack_info.action_category == ActionCategory.ATTACK
    assert attack_info.weapon_slot is not None
    assert attack_info.weapon_name is not None
    assert any(target.target_uuid == skeleton.uuid for target in attack_info.valid_targets)

    assert available.all_actions == (
        available.entity_actions
        + available.position_actions
        + available.self_actions
        + available.object_actions
    )


def test_eb_09_003_execute_by_index_instantiates_and_applies_costs() -> None:
    """EB-09-003: execute_by_index applies a template and consumes its cost."""
    reset_action_state()
    entity = configured_entity()
    available = get_available_actions(entity)
    dash_info = find_action(available, "Dash")

    result = execute_by_index(entity, dash_info.template_name, 0, available=available)

    assert result is not None
    assert not result.canceled
    assert "Dashing" in entity.active_conditions
    assert entity.action_economy.actions.normalized_score == 0

    after = get_available_actions(entity)
    dash_after = find_action(after, "Dash")
    assert dash_after.can_afford is False
    assert dash_after.valid_targets == []


def test_eb_09_004_floor_objects_create_object_actions_and_can_be_picked_up() -> None:
    """EB-09-004: visible floor objects surface OBJECT actions."""
    reset_action_state()
    entity = configured_entity(position=(3, 3))
    potion = materialize_item(
        HEALING_POTION_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.LOOT,
    )
    potion.place_on_grid((4, 3))
    Entity.update_all_entities_senses()

    available = get_available_actions(entity)
    pickup_info = find_action(available, "Pick Up")

    assert pickup_info.target_type == TargetType.OBJECT
    assert pickup_info.cost_amount == 0
    assert any(target.target_uuid == potion.uuid for target in pickup_info.valid_targets)

    target_index = next(
        target.index for target in pickup_info.valid_targets if target.target_uuid == potion.uuid
    )
    result = execute_by_index(entity, "Pick Up", target_index, available=available)

    assert result is not None
    assert not result.canceled
    assert potion.uuid in entity.inventory.items
    assert get_map().get_object_position(potion.uuid) is None


def test_eb_09_005_inventory_use_actions_are_routed_and_consume_charges() -> None:
    """EB-09-005: inventory use actions appear with item metadata and execute by index."""
    reset_action_state()
    entity = configured_entity(position=(3, 3))
    potion = materialize_item(
        HEALING_POTION_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    assert entity.loot_item(potion)

    available = get_available_actions(entity)
    potion_info = next(
        info for info in available.self_actions
        if info.is_item_use and info.source_item_uuid == potion.uuid
    )

    assert potion_info.template_name.startswith("Drink Potion__item_")
    assert potion_info.display_name == "Drink Potion (Potion of Healing)"
    assert potion_info.target_type == TargetType.SELF
    assert potion_info.valid_targets[0].index == 0

    result = execute_by_index(entity, potion_info.template_name, 0, available=available)

    assert result is not None
    assert not result.canceled
    assert potion.uuid not in entity.inventory.items
    assert BaseBlock.get(potion.uuid) is None


def test_eb_09_006_nearby_environment_use_actions_are_distance_gated() -> None:
    """EB-09-006: environment UsableItem actions only appear within 5 feet."""
    reset_action_state()
    entity = configured_entity(position=(3, 3))
    nearby = materialize_item(
        HEALING_POTION_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.LOOT,
    )
    far = materialize_item(
        HEALING_POTION_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.LOOT,
    )
    nearby.place_on_grid((4, 3))
    far.place_on_grid((8, 8))
    Entity.update_all_entities_senses()

    available = get_available_actions(entity)
    source_item_uuids = {
        info.source_item_uuid
        for info in available.self_actions
        if info.is_item_use
    }

    assert nearby.uuid in source_item_uuids
    assert far.uuid not in source_item_uuids


def test_eb_09_007_action_overrides_change_cost_display_and_consumption() -> None:
    """EB-09-007: action overrides affect discovery and execution costs."""
    reset_action_state()
    entity = configured_entity()
    dash_template = entity.get_action_template("Dash")
    assert dash_template is not None

    modified = apply_action_overrides(
        entity,
        lambda action: action.name == "Dash",
        {"alt_cost_type": "bonus_actions"},
    )
    assert dash_template.uuid in modified

    available = get_available_actions(entity)
    dash_info = find_action(available, "Dash")
    assert dash_info.cost_type == "bonus_actions"

    result = execute_by_index(entity, "Dash", 0, available=available)

    assert result is not None
    assert not result.canceled
    assert entity.action_economy.actions.normalized_score == 1
    assert entity.action_economy.bonus_actions.normalized_score == 0

    clear_action_overrides(entity, modified)
    assert dash_template.alt_cost_type is None


def test_eb_09_008_target_filters_and_dead_targets_shape_entity_actions() -> None:
    """EB-09-008: target_filter and include_dead control entity target pools."""
    reset_action_state()
    hero = create_goblin(name="Hero", position=(5, 5), faction="heroes")
    ally = create_goblin(name="Ally", position=(5, 6), faction="heroes")
    enemy = create_skeleton(name="Enemy", position=(6, 5), faction="monsters")
    dead_enemy = create_skeleton(name="Dead Enemy", position=(6, 6), faction="monsters")
    dead_enemy.health.take_damage(999, DamageType.BLUDGEONING, hero.uuid)
    Entity.update_all_entities_senses()

    default_attack = find_attack_action(hero.get_available_actions())
    assert [target.target_uuid for target in default_attack.valid_targets] == [enemy.uuid]

    ally_attack = find_attack_action(hero.get_available_actions(target_filter="allies"))
    assert [target.target_uuid for target in ally_attack.valid_targets] == [ally.uuid]

    all_living_attack = find_attack_action(hero.get_available_actions(target_filter="all"))
    assert [target.target_uuid for target in all_living_attack.valid_targets] == [
        enemy.uuid,
        ally.uuid,
    ]

    all_targets_attack = find_attack_action(
        hero.get_available_actions(target_filter="all", include_dead=True)
    )
    assert [target.target_uuid for target in all_targets_attack.valid_targets] == [
        enemy.uuid,
        dead_enemy.uuid,
        ally.uuid,
    ]


def test_eb_09_009_registered_multi_entity_spell_discovers_and_executes() -> None:
    """EB-09-009: registered Magic Missile exposes and executes MULTI_ENTITY metadata."""
    reset_action_state()
    caster_config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            intelligence=AbilityConfig(ability_score=16),
        ),
        action_economy=ActionEconomyConfig(spell_slots={1: 2}),
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
        proficiency_bonus=3,
        position=(1, 1),
        faction="heroes",
    )
    caster = Entity.create(
        source_entity_uuid=uuid4(),
        name="Wizard",
        config=caster_config,
    )
    setup_standard_actions(caster)
    targets = [
        create_skeleton(name="Target 1", position=(3, 1), faction="monsters"),
        create_skeleton(name="Target 2", position=(3, 2), faction="monsters"),
        create_skeleton(name="Target 3", position=(3, 3), faction="monsters"),
    ]
    Entity.update_all_entities_senses()
    register_spell(caster, MagicMissile, caster_level=5)

    available = get_available_actions(caster)
    missile_info = find_action(available, "Magic Missile__slot_1")
    targets_by_name = {
        target.target_name: target for target in missile_info.valid_targets
    }

    assert missile_info.target_type == TargetType.MULTI_ENTITY
    assert missile_info.action_category == ActionCategory.SPELL
    assert missile_info.base_template_name == "Magic Missile"
    assert missile_info.cast_at_level == 1
    assert missile_info.is_spell_variant
    assert missile_info.num_projectiles == 3
    assert missile_info.allow_same_target is True
    assert missile_info.can_afford is True
    assert missile_info.cost_type == "actions"
    assert set(targets_by_name) == {"Target 1", "Target 2", "Target 3"}

    hp_before = {target.uuid: target.get_hp() for target in targets}
    result = execute_by_index(
        caster,
        "Magic Missile__slot_1",
        targets_by_name["Target 1"].index,
        extra_target_uuids=[
            str(targets_by_name["Target 2"].target_uuid),
            str(targets_by_name["Target 3"].target_uuid),
        ],
        available=available,
    )

    assert result is not None
    assert not result.canceled
    spell_result = cast(SpellEvent, result)
    assert spell_result.total_targets == 3
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_1.normalized_score == 1

    damages = {
        target.uuid: hp_before[target.uuid] - target.get_hp()
        for target in targets
    }
    assert all(2 <= damage <= 5 for damage in damages.values())
    assert spell_result.total_damage == sum(damages.values())


def test_eb_09_010_registered_position_aoe_spell_previews_and_executes() -> None:
    """EB-09-010: registered Fireball exposes POSITION_AOE preview metadata."""
    reset_action_state()
    caster_config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            intelligence=AbilityConfig(ability_score=16),
        ),
        health=HealthConfig(
            hit_dices=[
                HitDiceConfig(hit_dice_value=10, hit_dice_count=10, mode="maximums")
            ]
        ),
        action_economy=ActionEconomyConfig(spell_slots={3: 1}),
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
        proficiency_bonus=3,
        position=(1, 1),
        faction="heroes",
    )
    caster = Entity.create(
        source_entity_uuid=uuid4(),
        name="Wizard",
        config=caster_config,
    )
    setup_standard_actions(caster)

    creature_config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            dexterity=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(
            hit_dices=[
                HitDiceConfig(hit_dice_value=10, hit_dice_count=10, mode="maximums")
            ]
        ),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
    )
    affected = [
        Entity.create(
            source_entity_uuid=uuid4(),
            name="Goblin 1",
            config=creature_config.model_copy(update={"position": (6, 6), "faction": "monsters"}),
        ),
        Entity.create(
            source_entity_uuid=uuid4(),
            name="Goblin 2",
            config=creature_config.model_copy(update={"position": (7, 6), "faction": "monsters"}),
        ),
        Entity.create(
            source_entity_uuid=uuid4(),
            name="Ally",
            config=creature_config.model_copy(update={"position": (6, 7), "faction": "heroes"}),
        ),
    ]
    outsider = Entity.create(
        source_entity_uuid=uuid4(),
        name="Outsider",
        config=creature_config.model_copy(update={"position": (12, 12), "faction": "monsters"}),
    )
    Entity.update_all_entities_senses()
    register_spell(caster, Fireball, caster_level=5)

    available = get_available_actions(caster)
    fireball_info = find_action(available, "Fireball__slot_3")
    center_target = next(
        target for target in fireball_info.valid_targets if target.position == (6, 6)
    )

    assert fireball_info.target_type == TargetType.POSITION_AOE
    assert fireball_info.action_category == ActionCategory.SPELL
    assert fireball_info.base_template_name == "Fireball"
    assert fireball_info.cast_at_level == 3
    assert fireball_info.is_spell_variant
    assert fireball_info.can_afford is True
    assert fireball_info.cost_type == "actions"
    assert center_target.affected_count == 3
    assert set(center_target.affected_entity_names or []) == {
        "Goblin 1",
        "Goblin 2",
        "Ally",
    }
    assert set(center_target.affected_entity_uuids or []) == {
        creature.uuid for creature in affected
    }
    assert outsider.uuid not in set(center_target.affected_entity_uuids or [])
    assert (6, 6) in set(center_target.affected_positions or [])

    hp_before = {
        creature.uuid: creature.get_hp()
        for creature in [*affected, outsider, caster]
    }
    result = execute_by_index(
        caster,
        "Fireball__slot_3",
        center_target.index,
        available=available,
    )

    assert result is not None
    assert not result.canceled
    spell_result = cast(SpellEvent, result)
    assert spell_result.total_targets == 3
    assert spell_result.aoe_position == (6, 6)
    assert spell_result.aoe_shape_type == "sphere"
    assert spell_result.aoe_radius_ft == 20
    assert spell_result.total_damage > 0
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_3.normalized_score == 0

    damages = {
        creature.uuid: hp_before[creature.uuid] - creature.get_hp()
        for creature in affected
    }
    assert all(damage > 0 for damage in damages.values())
    assert spell_result.total_damage == sum(damages.values())
    assert outsider.get_hp() == hp_before[outsider.uuid]
    assert caster.get_hp() == hp_before[caster.uuid]


def test_eb_09_011_move_discovery_marks_hazardous_and_safe_paths() -> None:
    """EB-09-011: Move targets expose hazardous paths and safe alternatives."""
    reset_action_state()
    grid = get_map()
    hazard_position = (5, 5)
    hazard_tile = grid.get_tile(*hazard_position)
    assert hazard_tile is not None
    hazard = BaseCondition(
        name="Test Hazard",
        source_entity_uuid=uuid4(),
        target_entity_uuid=hazard_tile.uuid,
        hazard_filter=HazardFilter.ALL,
    )
    hazard_tile.add_condition(hazard)

    scout = create_skeleton(name="Scout", position=(5, 3), faction="heroes")
    Entity.update_all_entities_senses()

    available = get_available_actions(scout)
    move_info = find_action(available, "Move")
    hazard_target = next(
        target for target in move_info.valid_targets if target.position == (5, 6)
    )

    assert hazard_target.is_path_hazardous is True
    assert hazard_target.path is not None
    assert hazard_target.safe_path is not None
    assert hazard_target.safe_path_cost is not None
    assert hazard_position in hazard_target.path[1:]
    assert hazard_position not in hazard_target.safe_path[1:]
    assert all(
        not grid.is_position_hazardous_for(step[0], step[1], scout.uuid)
        for step in hazard_target.safe_path[1:]
    )

    movement_before = scout.action_economy.movement.normalized_score
    result = execute_by_index(
        scout,
        "Move",
        hazard_target.index,
        available=available,
        prefer_safe=True,
    )

    assert result is not None
    assert not result.canceled
    movement_result = cast(MovementEvent, result)
    assert movement_result.path == hazard_target.safe_path
    assert scout.position == hazard_target.position
    assert scout.action_economy.movement.normalized_score == (
        movement_before - hazard_target.safe_path_cost
    )


def test_eb_09_012_attack_object_discovers_and_destroys_breakables() -> None:
    """EB-09-012: Attack Object targets nearby breakables and can destroy them."""
    reset_action_state()
    entity = configured_entity(position=(3, 3))
    crate_source = uuid4()
    crate = BaseItem(
        source_entity_uuid=crate_source,
        name="Training Crate",
        is_pickable=False,
        is_targetable=True,
        health=BaseItem.create_item_health(
            crate_source,
            hp=4,
            hit_dice_value=4,
            vulnerabilities=[DamageType.BLUDGEONING],
        ),
        weight=50,
    )
    crate.place_on_grid((4, 3))
    Entity.update_all_entities_senses()

    available = get_available_actions(entity)
    attack_info = find_action(available, "Attack Object")
    crate_target = next(
        target for target in attack_info.valid_targets if target.target_uuid == crate.uuid
    )

    assert attack_info.target_type == TargetType.OBJECT
    assert attack_info.action_category == ActionCategory.ATTACK
    assert attack_info.can_afford is True
    assert attack_info.cost_type == "actions"
    assert attack_info.cost_amount == 1
    assert crate_target.target_name == "Training Crate"
    assert crate_target.distance == 5
    assert get_map().get_object_position(crate.uuid) == (4, 3)

    result = execute_by_index(
        entity,
        "Attack Object",
        crate_target.index,
        available=available,
    )

    assert result is not None
    assert not result.canceled
    assert "Dealt" in (result.status_message or "")
    assert BaseBlock.get(crate.uuid) is None
    assert get_map().get_object_position(crate.uuid) is None

    Entity.update_all_entities_senses()
    assert crate.uuid not in entity.senses.objects
    assert entity.action_economy.actions.normalized_score == 0


if __name__ == "__main__":
    test_eb_09_001_templates_must_be_registered_and_instantiated()
    test_eb_09_002_standard_actions_discover_self_position_and_entity_groups()
    test_eb_09_003_execute_by_index_instantiates_and_applies_costs()
    test_eb_09_004_floor_objects_create_object_actions_and_can_be_picked_up()
    test_eb_09_005_inventory_use_actions_are_routed_and_consume_charges()
    test_eb_09_006_nearby_environment_use_actions_are_distance_gated()
    test_eb_09_007_action_overrides_change_cost_display_and_consumption()
    test_eb_09_008_target_filters_and_dead_targets_shape_entity_actions()
    test_eb_09_009_registered_multi_entity_spell_discovers_and_executes()
    test_eb_09_010_registered_position_aoe_spell_previews_and_executes()
    test_eb_09_011_move_discovery_marks_hazardous_and_safe_paths()
    test_eb_09_012_attack_object_discovers_and_destroys_breakables()
    print("Chapter 09 engine-book action template/discovery tests passed.")
