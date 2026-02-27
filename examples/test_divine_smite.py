"""
Test Divine Smite (Paladin Feature)

Tests the per-level Divine Smite handler system:
- Correct dice count per spell slot level (L1=2d8, L2=3d8, L3=4d8, L4/L5=5d8 cap)
- Critical strikes double smite dice
- Highest available slot fires first
- Disabling highest handler falls through to next
- No smite on miss, on ranged attack, or without spell slots
- Only one smite per attack (no double-dipping)
- Smite consumes the correct spell slot
"""

import sys
sys.path.insert(0, '.')

from dnd.core.gridmap import get_map
from dnd.core.events import WeaponSlot
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton, create_caster
from dnd.actions import Attack
from dnd.actions_functional import setup_standard_actions
from dnd.classes.paladin import register_divine_smite
from dnd.core.base_actions import spell_slot_cost_type
from dnd.items import create_longsword
from dnd.utils import (
    reset_combat_state, force_attack_hit, force_attack_miss,
    force_attack_crit, remove_attack_modifier
)


def create_paladin(name="Paladin", position=(5, 5), level=5):
    """Create a paladin-like entity with melee weapon and spell slots.

    Uses create_caster as base (has spell slots), then equips a longsword.
    """
    entity = create_caster(name=name, position=position, level=level)
    # Equip a longsword for melee attacks
    sword = create_longsword(entity.uuid)
    entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)
    return entity


def setup_smite_scenario(max_slot_level=5):
    """Paladin with Divine Smite vs skeleton target."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    paladin = create_paladin(name="Paladin", position=(5, 5))
    register_divine_smite(paladin, max_slot_level=max_slot_level)

    target = create_skeleton(name="Skeleton", position=(5, 6))
    setup_standard_actions(target)

    Entity.update_all_entities_senses(max_distance=20)
    return paladin, target


def do_melee_attack(attacker, target, force="hit"):
    """Execute a melee attack with forced outcome. Returns (event, mod_id)."""
    mod_ids = []
    if force == "hit":
        mod_ids.append(force_attack_hit(attacker))
    elif force == "miss":
        mod_ids.append(force_attack_miss(attacker))
    elif force == "crit":
        # Need both hit guarantee AND crit modifier
        mod_ids.append(force_attack_hit(attacker))
        mod_ids.append(force_attack_crit(attacker))
    else:
        raise ValueError(f"Unknown force type: {force}")

    attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    event = attack.apply()
    for mod_id in mod_ids:
        remove_attack_modifier(attacker, mod_id)
    return event


def count_smite_dice_in_rolls(paladin):
    """Count the number of d8 radiant damage dice from Divine Smite.

    Returns (dice_count, actual_dice_rolled, smite_total, slot_level) by
    checking the DamageRollResultEvent context in the object registry.
    """
    from dnd.core.events import DamageRollResultEvent
    from dnd.core.base_object import BaseObject

    for obj in BaseObject._registry.values():
        if isinstance(obj, DamageRollResultEvent):
            if obj.source_entity_uuid == paladin.uuid and obj.context.get("divine_smite_applied"):
                slot_level = obj.context.get("divine_smite_slot_level", 0)
                dice_count = obj.context.get("divine_smite_dice_count", 0)
                # Find the smite roll (last entry in final_rolls, added by smite)
                smite_roll = obj.final_rolls[-1] if len(obj.final_rolls) > len(obj.original_rolls) else None
                smite_total = smite_roll.total if smite_roll else 0
                results = smite_roll.results if smite_roll else []
                actual_dice_rolled = len(results) if isinstance(results, list) else 1
                return dice_count, actual_dice_rolled, smite_total, slot_level
    return 0, 0, 0, 0


def test_smite_dice_per_slot_level():
    """Test 1: Correct dice count for each spell slot level."""
    print("\n=== Test 1: Dice Count Per Slot Level ===")

    for slot_level in range(1, 6):
        paladin, target = setup_smite_scenario(max_slot_level=slot_level)

        # Disable all handlers except the one for this slot level
        for handler in paladin.get_event_handlers_by_name(f"Divine Smite (L{slot_level})"):
            handler.enabled = True
        for other_level in range(1, 6):
            if other_level != slot_level:
                for handler in paladin.get_event_handlers_by_name(f"Divine Smite (L{other_level})"):
                    handler.enabled = False

        do_melee_attack(paladin, target, force="hit")

        dice_count, actual_dice, _, used_slot = count_smite_dice_in_rolls(paladin)
        expected_dice = min(1 + slot_level, 5)

        print(f"  L{slot_level} slot: expected {expected_dice}d8, got {dice_count}d8 (rolled {actual_dice} dice), slot used: L{used_slot}")
        assert dice_count == expected_dice, f"L{slot_level}: expected {expected_dice}d8, got {dice_count}d8"
        assert used_slot == slot_level, f"Expected slot L{slot_level}, used L{used_slot}"

    print("  PASSED: All slot levels produce correct dice counts")


def test_smite_crit_doubles_dice():
    """Test 2: Critical hit doubles smite dice."""
    print("\n=== Test 2: Critical Hit Doubles Smite Dice ===")

    for slot_level in [1, 3, 4]:
        paladin, target = setup_smite_scenario(max_slot_level=slot_level)

        # Disable all handlers except the one for this slot level
        for handler in paladin.get_event_handlers_by_name(f"Divine Smite (L{slot_level})"):
            handler.enabled = True
        for other_level in range(1, 6):
            if other_level != slot_level:
                for handler in paladin.get_event_handlers_by_name(f"Divine Smite (L{other_level})"):
                    handler.enabled = False

        do_melee_attack(paladin, target, force="crit")

        _, actual_dice, _, crit_used_slot = count_smite_dice_in_rolls(paladin)
        base_dice = min(1 + slot_level, 5)
        expected_rolled = base_dice * 2  # Crit doubles

        print(f"  L{slot_level} crit: expected {expected_rolled} dice rolled (base {base_dice}d8 doubled), got {actual_dice} (slot L{crit_used_slot})")
        assert actual_dice == expected_rolled, f"L{slot_level} crit: expected {expected_rolled} dice, got {actual_dice}"

    print("  PASSED: Critical hits double smite dice")


def test_smite_highest_slot_fires_first():
    """Test 3: Highest available slot is used by default."""
    print("\n=== Test 3: Highest Slot Fires First ===")
    paladin, target = setup_smite_scenario(max_slot_level=5)

    # All handlers enabled — should use highest available slot
    do_melee_attack(paladin, target, force="hit")

    _, _, _, used_slot = count_smite_dice_in_rolls(paladin)
    # Paladin (sorcerer base) has slots up to L9, but handlers only up to L5
    assert used_slot == 5, f"Expected L5 slot used, got L{used_slot}"

    print(f"  Used slot: L{used_slot}")
    print("  PASSED: Highest slot fires first")


def test_smite_disable_highest_falls_through():
    """Test 4: Disabling highest handler causes next-highest to fire."""
    print("\n=== Test 4: Disable Highest Falls Through ===")
    paladin, target = setup_smite_scenario(max_slot_level=5)

    # Disable L5 handler
    paladin.set_handler_enabled("Divine Smite (L5)", False)

    do_melee_attack(paladin, target, force="hit")

    dice_count, _, _, used_slot = count_smite_dice_in_rolls(paladin)
    assert used_slot == 4, f"Expected L4 slot used after disabling L5, got L{used_slot}"
    assert dice_count == 5, f"Expected 5d8 (capped), got {dice_count}d8"

    print(f"  Disabled L5 → used L{used_slot} ({dice_count}d8)")
    print("  PASSED: Falls through to next highest")


def test_smite_disable_all_no_smite():
    """Test 5: Disabling all smite handlers = no smite, no slot consumed."""
    print("\n=== Test 5: All Disabled = No Smite ===")
    paladin, target = setup_smite_scenario(max_slot_level=3)

    # Check slots before
    slots_before = {}
    for level in range(1, 10):
        slot_attr = getattr(paladin.action_economy, f"spell_slot_{level}", None)
        if slot_attr:
            slots_before[level] = slot_attr.normalized_score

    # Disable all smite handlers
    for level in range(1, 4):
        paladin.set_handler_enabled(f"Divine Smite (L{level})", False)

    do_melee_attack(paladin, target, force="hit")

    dice_count, _, _, _ = count_smite_dice_in_rolls(paladin)
    assert dice_count == 0, f"Expected no smite, got {dice_count}d8"

    # Check no slots consumed
    for level in range(1, 10):
        slot_attr = getattr(paladin.action_economy, f"spell_slot_{level}", None)
        if slot_attr:
            assert slot_attr.normalized_score == slots_before[level], \
                f"Slot L{level} changed: {slots_before[level]} → {slot_attr.normalized_score}"

    print("  PASSED: All disabled, no smite, no slots consumed")


def test_smite_no_fire_on_miss():
    """Test 6: Smite doesn't fire on a miss."""
    print("\n=== Test 6: No Smite on Miss ===")
    paladin, target = setup_smite_scenario(max_slot_level=3)

    do_melee_attack(paladin, target, force="miss")

    dice_count, _, _, _ = count_smite_dice_in_rolls(paladin)
    assert dice_count == 0, f"Expected no smite on miss, got {dice_count}d8"

    print("  PASSED: No smite on miss")


def test_smite_no_fire_on_ranged():
    """Test 7: Smite doesn't fire on ranged attacks."""
    print("\n=== Test 7: No Smite on Ranged Attack ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 30, 30)

    paladin = create_paladin(name="Paladin", position=(5, 5))
    register_divine_smite(paladin, max_slot_level=3)

    # Equip a ranged weapon
    from dnd.items import create_shortbow
    bow = create_shortbow(paladin.uuid)
    paladin.equipment.equip(bow, WeaponSlot.RANGED_MAIN)

    target = create_skeleton(name="Skeleton", position=(5, 15))  # Far away
    setup_standard_actions(target)

    Entity.update_all_entities_senses(max_distance=30)

    mod_id = force_attack_hit(paladin)
    attack = Attack(
        source_entity_uuid=paladin.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.RANGED_MAIN
    )
    attack.apply()
    remove_attack_modifier(paladin, mod_id)

    dice_count, _, _, _ = count_smite_dice_in_rolls(paladin)
    assert dice_count == 0, f"Expected no smite on ranged, got {dice_count}d8"

    print("  PASSED: No smite on ranged attack")


def test_smite_no_slots_no_fire():
    """Test 8: No smite when spell slots are exhausted."""
    print("\n=== Test 8: No Slots = No Smite ===")
    paladin, target = setup_smite_scenario(max_slot_level=3)

    # Exhaust all spell slots
    for level in range(1, 10):
        slot_cost = spell_slot_cost_type(level)
        while paladin.action_economy.can_afford(slot_cost, 1):
            paladin.action_economy.consume(slot_cost, 1)

    do_melee_attack(paladin, target, force="hit")

    dice_count, _, _, _ = count_smite_dice_in_rolls(paladin)
    assert dice_count == 0, f"Expected no smite without slots, got {dice_count}d8"

    print("  PASSED: No smite without spell slots")


def test_smite_one_per_attack():
    """Test 9: Only one smite fires per attack (no double-dipping)."""
    print("\n=== Test 9: One Smite Per Attack ===")
    paladin, target = setup_smite_scenario(max_slot_level=5)

    # All 5 handlers enabled — only highest should fire
    do_melee_attack(paladin, target, force="hit")

    dice_count, _, _, used_slot = count_smite_dice_in_rolls(paladin)
    assert dice_count == 5, f"Expected 5d8 (one smite), got {dice_count}d8"
    assert used_slot == 5, f"Expected L5, got L{used_slot}"

    # Check that only one slot was consumed (L5)
    slot5 = paladin.action_economy.spell_slot_5.normalized_score
    # Sorcerer has 2 L5 slots, should have 1 remaining
    assert slot5 == 1, f"Expected 1 L5 slot remaining, got {slot5}"

    # L4 should be untouched (2 slots)
    slot4 = paladin.action_economy.spell_slot_4.normalized_score
    assert slot4 == 2, f"Expected 2 L4 slots remaining, got {slot4}"

    print(f"  One smite (L{used_slot}, {dice_count}d8), L5 remaining: {slot5}, L4 remaining: {slot4}")
    print("  PASSED: Only one smite per attack")


def test_smite_consumes_correct_slot():
    """Test 10: Smite consumes the exact spell slot level of the handler."""
    print("\n=== Test 10: Correct Slot Consumed ===")
    paladin, target = setup_smite_scenario(max_slot_level=3)

    # Disable L3 and L2, only L1 should fire
    paladin.set_handler_enabled("Divine Smite (L3)", False)
    paladin.set_handler_enabled("Divine Smite (L2)", False)

    slot1_before = paladin.action_economy.spell_slot_1.normalized_score
    slot2_before = paladin.action_economy.spell_slot_2.normalized_score
    slot3_before = paladin.action_economy.spell_slot_3.normalized_score

    do_melee_attack(paladin, target, force="hit")

    slot1_after = paladin.action_economy.spell_slot_1.normalized_score
    slot2_after = paladin.action_economy.spell_slot_2.normalized_score
    slot3_after = paladin.action_economy.spell_slot_3.normalized_score

    assert slot1_after == slot1_before - 1, f"L1 should be consumed: {slot1_before} → {slot1_after}"
    assert slot2_after == slot2_before, f"L2 should be untouched: {slot2_before} → {slot2_after}"
    assert slot3_after == slot3_before, f"L3 should be untouched: {slot3_before} → {slot3_after}"

    print(f"  L1: {slot1_before} → {slot1_after}, L2: {slot2_before} → {slot2_after}, L3: {slot3_before} → {slot3_after}")
    print("  PASSED: Correct spell slot consumed")


def test_smite_fallthrough_on_empty_slot():
    """Test 11: If highest slot is empty, falls through to next with slots."""
    print("\n=== Test 11: Fallthrough on Empty Slot ===")
    paladin, target = setup_smite_scenario(max_slot_level=3)

    # Exhaust L3 slots
    while paladin.action_economy.can_afford(spell_slot_cost_type(3), 1):
        paladin.action_economy.consume(spell_slot_cost_type(3), 1)

    do_melee_attack(paladin, target, force="hit")

    dice_count, _, _, used_slot = count_smite_dice_in_rolls(paladin)
    assert used_slot == 2, f"Expected L2 after L3 exhausted, got L{used_slot}"
    assert dice_count == 3, f"Expected 3d8 for L2, got {dice_count}d8"

    print(f"  L3 exhausted → used L{used_slot} ({dice_count}d8)")
    print("  PASSED: Falls through to next slot with availability")


if __name__ == "__main__":
    print("=" * 60)
    print("Divine Smite Tests")
    print("=" * 60)

    test_smite_dice_per_slot_level()
    test_smite_crit_doubles_dice()
    test_smite_highest_slot_fires_first()
    test_smite_disable_highest_falls_through()
    test_smite_disable_all_no_smite()
    test_smite_no_fire_on_miss()
    test_smite_no_fire_on_ranged()
    test_smite_no_slots_no_fire()
    test_smite_one_per_attack()
    test_smite_consumes_correct_slot()
    test_smite_fallthrough_on_empty_slot()

    print("\n" + "=" * 60)
    print("All Divine Smite tests passed!")
    print("=" * 60)
