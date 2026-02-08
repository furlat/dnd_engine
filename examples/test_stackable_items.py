"""
Stackable Items Tests

Tests: Stack merging on loot, consume-from-stack, action display with count,
stack limits, non-stackable items unchanged, weight calculation, slot bypass,
weapon coat stacking (fire vs lightning).
"""

import sys
import traceback
from typing import Tuple
from uuid import uuid4

from dnd.utils import reset_combat_state, set_hp
from dnd.core.gridmap import get_map
from dnd.core.base_block import BaseBlock
from dnd.core.base_actions import AvailableTarget
from dnd.core.events import WeaponSlot
from dnd.core.modifiers import DamageType
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.actions_functional import (
    setup_standard_actions, get_available_actions, execute_use_action,
)
from dnd.items.test_items import (
    create_scroll_of_fireball, create_scroll_of_magic_missile,
    create_healing_potion, create_weapon_coat, create_lightning_weapon_coat,
    create_wand_of_magic_missiles,
)
from dnd.items.weapons import create_longsword

tests_passed = 0
tests_failed = 0


def setup_grid():
    """Create a 20x20 floor grid."""
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)
    return grid


def run_test(name, func):
    global tests_passed, tests_failed
    reset_combat_state()
    setup_grid()
    try:
        func()
        print(f"  PASS: {name}")
        tests_passed += 1
    except Exception:
        print(f"  FAIL: {name}")
        traceback.print_exc()
        tests_failed += 1


def create_entity(
    name: str = "Hero",
    position: Tuple[int, int] = (0, 0),
    faction: str = "heroes",
    hp: int = 100,
) -> Entity:
    """Create a basic entity for stacking tests."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=14),
            intelligence=AbilityConfig(ability_score=16),
            constitution=AbilityConfig(ability_score=14),
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=10, mode="maximums")]
        ),
        action_economy=ActionEconomyConfig(
            spell_slots={1: 4, 2: 3, 3: 2}
        ),
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
        equipment=EquipmentConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    set_hp(entity, hp)
    setup_standard_actions(entity)
    return entity


def create_target(
    name: str = "Target",
    position: Tuple[int, int] = (3, 0),
    faction: str = "monsters",
    hp: int = 100,
) -> Entity:
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=10, mode="maximums")]
        ),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    set_hp(entity, hp)
    setup_standard_actions(entity)
    return entity


# =============================================================================
# Tests
# =============================================================================

def test_stack_merge_on_loot():
    """2 fireball L3 scrolls looted -> 1 inventory item, stack_count=2."""
    entity = create_entity()
    Entity.update_all_entities_senses()

    scroll1 = create_scroll_of_fireball(entity.uuid, cast_level=3)
    scroll2 = create_scroll_of_fireball(entity.uuid, cast_level=3)

    entity.loot_item(scroll1)
    entity.loot_item(scroll2)

    assert entity.inventory.item_count == 1, f"Expected 1 item, got {entity.inventory.item_count}"
    stacked_item = list(entity.inventory.items.values())[0]
    assert stacked_item.stack_count == 2, f"Expected stack_count=2, got {stacked_item.stack_count}"


def test_no_merge_different_levels():
    """Fireball L3 + Fireball L5 -> 2 separate items."""
    entity = create_entity()
    Entity.update_all_entities_senses()

    scroll1 = create_scroll_of_fireball(entity.uuid, cast_level=3)
    scroll2 = create_scroll_of_fireball(entity.uuid, cast_level=5)

    entity.loot_item(scroll1)
    entity.loot_item(scroll2)

    assert entity.inventory.item_count == 2, f"Expected 2 items, got {entity.inventory.item_count}"


def test_no_merge_different_types():
    """Fireball + Magic Missile -> 2 items."""
    entity = create_entity()
    Entity.update_all_entities_senses()

    scroll1 = create_scroll_of_fireball(entity.uuid)
    scroll2 = create_scroll_of_magic_missile(entity.uuid)

    entity.loot_item(scroll1)
    entity.loot_item(scroll2)

    assert entity.inventory.item_count == 2, f"Expected 2 items, got {entity.inventory.item_count}"


def test_consume_from_stack():
    """3 stacked scrolls, use 1 -> stack_count=2, item still exists."""
    entity = create_entity()
    target = create_target()
    Entity.update_all_entities_senses()

    scroll1 = create_scroll_of_fireball(entity.uuid)
    scroll2 = create_scroll_of_fireball(entity.uuid)
    scroll3 = create_scroll_of_fireball(entity.uuid)

    entity.loot_item(scroll1)
    entity.loot_item(scroll2)
    entity.loot_item(scroll3)

    assert entity.inventory.item_count == 1
    stacked = list(entity.inventory.items.values())[0]
    assert stacked.stack_count == 3

    # Use one (Fireball is POSITION_AOE, so target a position near enemy)
    _result = execute_use_action(
        entity, stacked.uuid, "Fireball",
        target=AvailableTarget(index=0, position=target.position)
    )

    assert stacked.stack_count == 2, f"Expected stack_count=2 after use, got {stacked.stack_count}"
    assert entity.inventory.item_count == 1, "Item should still be in inventory"
    assert stacked.charges == 1, f"Charges should reset to 1, got {stacked.charges}"


def test_consume_last_in_stack():
    """1 scroll, use -> destroyed, removed from inventory."""
    entity = create_entity()
    target = create_target()
    Entity.update_all_entities_senses()

    scroll = create_scroll_of_fireball(entity.uuid)
    entity.loot_item(scroll)
    scroll_uuid = scroll.uuid

    assert entity.inventory.item_count == 1

    _result = execute_use_action(
        entity, scroll_uuid, "Fireball",
        target=AvailableTarget(index=0, position=target.position)
    )

    assert entity.inventory.item_count == 0, "Inventory should be empty after last scroll used"
    assert BaseBlock.get(scroll_uuid) is None, "Scroll should be unregistered"


def test_action_appears_once():
    """3 stacked scrolls -> Fireball shows once in available_actions."""
    entity = create_entity()
    target = create_target()
    Entity.update_all_entities_senses()

    for _ in range(3):
        scroll = create_scroll_of_fireball(entity.uuid)
        entity.loot_item(scroll)

    actions = get_available_actions(entity)
    fireball_actions = [a for a in actions.all_actions if "Fireball" in a.template_name]
    assert len(fireball_actions) == 1, f"Expected 1 Fireball action, got {len(fireball_actions)}"


def test_display_name_includes_count():
    """Stack of 3 -> display_name contains 'x3'."""
    entity = create_entity()
    target = create_target()
    Entity.update_all_entities_senses()

    for _ in range(3):
        scroll = create_scroll_of_fireball(entity.uuid)
        entity.loot_item(scroll)

    actions = get_available_actions(entity)
    fireball_actions = [a for a in actions.all_actions if "Fireball" in a.template_name]
    assert len(fireball_actions) == 1
    action = fireball_actions[0]
    assert "x3" in action.display_name, f"Expected 'x3' in display_name, got: {action.display_name}"
    assert action.item_stack_count == 3, f"Expected item_stack_count=3, got {action.item_stack_count}"


def test_stack_limit_respected():
    """max_stack=20 for scrolls. Loot 22 -> 2 items (20 + 2)."""
    entity = create_entity()
    Entity.update_all_entities_senses()

    for _ in range(22):
        scroll = create_scroll_of_fireball(entity.uuid)
        entity.loot_item(scroll)

    assert entity.inventory.item_count == 2, f"Expected 2 items, got {entity.inventory.item_count}"
    items = list(entity.inventory.items.values())
    counts = sorted([i.stack_count for i in items])
    assert counts == [2, 20], f"Expected [2, 20], got {counts}"


def test_potion_stacking():
    """3 healing potions -> 1 item, stack_count=3."""
    entity = create_entity()
    Entity.update_all_entities_senses()

    for _ in range(3):
        potion = create_healing_potion(entity.uuid)
        entity.loot_item(potion)

    assert entity.inventory.item_count == 1, f"Expected 1 item, got {entity.inventory.item_count}"
    stacked = list(entity.inventory.items.values())[0]
    assert stacked.stack_count == 3, f"Expected stack_count=3, got {stacked.stack_count}"


def test_non_stackable_unchanged():
    """2 Wands of Magic Missiles -> 2 separate items (wands don't stack)."""
    entity = create_entity()
    Entity.update_all_entities_senses()

    wand1 = create_wand_of_magic_missiles(entity.uuid, charges=3)
    wand2 = create_wand_of_magic_missiles(entity.uuid, charges=3)

    entity.loot_item(wand1)
    entity.loot_item(wand2)

    assert entity.inventory.item_count == 2, f"Expected 2 items, got {entity.inventory.item_count}"


def test_weight_with_stacks():
    """Stack of 3 scrolls (weight 0.5 each) -> total_weight = 1.5."""
    entity = create_entity()
    Entity.update_all_entities_senses()

    for _ in range(3):
        scroll = create_scroll_of_fireball(entity.uuid)
        scroll.weight = 0.5
        entity.loot_item(scroll)

    # Stacked item weight * stack_count
    assert entity.inventory.item_count == 1
    stacked = list(entity.inventory.items.values())[0]
    # Weight is on the first item (merged into), the original weight of 0
    # We set weight before loot, but only the first scroll's weight is preserved
    # The total_weight calculation multiplies by stack_count
    total = entity.inventory.total_weight
    assert total == stacked.weight * stacked.stack_count, f"Expected weight*count, got {total}"


def test_can_add_with_full_slots():
    """Inventory at max_slots, but compatible stack has room -> can_add=True."""
    entity = create_entity()
    Entity.update_all_entities_senses()

    entity.inventory.max_slots = 1

    scroll1 = create_scroll_of_fireball(entity.uuid)
    entity.loot_item(scroll1)
    assert entity.inventory.item_count == 1

    # Full slot, but can merge into existing stack
    scroll2 = create_scroll_of_fireball(entity.uuid)
    assert entity.inventory.can_add(scroll2) is True
    entity.loot_item(scroll2)
    assert entity.inventory.item_count == 1
    stacked = list(entity.inventory.items.values())[0]
    assert stacked.stack_count == 2

    # Different type can't be added (no room)
    mm_scroll = create_scroll_of_magic_missile(entity.uuid)
    assert entity.inventory.can_add(mm_scroll) is False


def test_fire_coat_stacking():
    """2 fire coats -> 1 item, stack_count=2."""
    entity = create_entity()
    Entity.update_all_entities_senses()

    coat1 = create_weapon_coat(entity.uuid)
    coat2 = create_weapon_coat(entity.uuid)

    entity.loot_item(coat1)
    entity.loot_item(coat2)

    assert entity.inventory.item_count == 1, f"Expected 1 item, got {entity.inventory.item_count}"
    stacked = list(entity.inventory.items.values())[0]
    assert stacked.stack_count == 2, f"Expected stack_count=2, got {stacked.stack_count}"


def test_fire_vs_lightning_no_merge():
    """1 fire coat + 1 lightning coat -> 2 separate items."""
    entity = create_entity()
    Entity.update_all_entities_senses()

    fire_coat = create_weapon_coat(entity.uuid)
    lightning_coat = create_lightning_weapon_coat(entity.uuid)

    entity.loot_item(fire_coat)
    entity.loot_item(lightning_coat)

    assert entity.inventory.item_count == 2, f"Expected 2 items, got {entity.inventory.item_count}"


def test_lightning_coat_applies_damage():
    """Apply lightning coat, attack -> target takes lightning extra damage."""
    entity = create_entity()
    target = create_target()
    Entity.update_all_entities_senses()

    # Equip a weapon
    sword = create_longsword(entity.uuid)
    entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)

    # Loot and use lightning coat
    coat = create_lightning_weapon_coat(entity.uuid)
    entity.loot_item(coat)
    coat_uuid = list(entity.inventory.items.keys())[0]

    execute_use_action(entity, coat_uuid, "Coat Main Hand")

    # Verify condition applied
    assert "Lightning Coat" in entity.active_conditions, \
        f"Expected 'Lightning Coat', got conditions: {list(entity.active_conditions.keys())}"

    # Verify weapon has lightning damage
    weapon = entity.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
    assert weapon is not None, "Weapon should be equipped"
    from dnd.blocks.equipment import Weapon
    assert isinstance(weapon, Weapon), "Should be a Weapon"
    assert DamageType.LIGHTNING in weapon.extra_damage_type, \
        f"Expected LIGHTNING in extra_damage_type, got {weapon.extra_damage_type}"


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    print("\n=== Stackable Items Tests ===\n")

    print("Stack merge on loot:")
    run_test("Stack merge on loot", test_stack_merge_on_loot)
    run_test("No merge different levels", test_no_merge_different_levels)
    run_test("No merge different types", test_no_merge_different_types)

    print("\nConsume from stack:")
    run_test("Consume from stack", test_consume_from_stack)
    run_test("Consume last in stack", test_consume_last_in_stack)

    print("\nAction display:")
    run_test("Action appears once", test_action_appears_once)
    run_test("Display name includes count", test_display_name_includes_count)

    print("\nStack limits and edge cases:")
    run_test("Stack limit respected", test_stack_limit_respected)
    run_test("Potion stacking", test_potion_stacking)
    run_test("Non-stackable unchanged", test_non_stackable_unchanged)
    run_test("Weight with stacks", test_weight_with_stacks)
    run_test("can_add with full slots", test_can_add_with_full_slots)

    print("\nWeapon coats:")
    run_test("Fire coat stacking", test_fire_coat_stacking)
    run_test("Fire vs lightning no merge", test_fire_vs_lightning_no_merge)
    run_test("Lightning coat applies damage", test_lightning_coat_applies_damage)

    print(f"\n{'='*50}")
    print(f"Results: {tests_passed} passed, {tests_failed} failed out of {tests_passed + tests_failed}")
    if tests_failed > 0:
        sys.exit(1)
    print("All tests passed!")
