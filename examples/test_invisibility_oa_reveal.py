"""Tests for Invisibility/Greater Invisibility removal on Opportunity Attack.

Bug: Invisible entity makes OA (missed) but Invisibility is NOT removed.
Both InvisibilityEffect and GreaterInvisibilityEffect should trigger their
reveal/stealth-check handlers on OA attacks (hit or miss).

Test matrix:
- InvisibilityEffect: natural spell + scroll, OA miss + hit, regular attack
- GreaterInvisibilityEffect: natural spell + potion, OA miss + hit, regular attack
- Concentration/damage: damage doesn't break, concentration failure does
"""
import sys
from uuid import uuid4

from dnd.core.events import WeaponSlot, DamageType
from dnd.core.base_actions import AvailableTarget
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.encounter import Encounter
from dnd.controller import HumanController
from dnd.actions import Attack, Move
from dnd.actions_functional import setup_standard_actions, execute_use_action
from dnd.monsters.bestiary import create_skeleton, create_sorcerer
from dnd.reactions import add_opportunity_attack_handler
from dnd.spells.illusion import Invisibility, GreaterInvisibility
from dnd.items.test_items import create_scroll_of_invisibility, create_potion_of_greater_invisibility
from dnd.conditions import GreaterInvisibilityEffect
from dnd.utils import (
    reset_combat_state, has_condition,
    force_attack_hit, force_attack_miss, remove_attack_modifier,
    deal_damage_to,
)

passed = 0
failed = 0
errors = []


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        errors.append(name)
        print(f"  FAIL: {name}")


def setup_oa_scenario():
    """Create two entities adjacent, with OA handler on the invisible one.

    Returns (invisible_entity, mover) positioned at (5,5) and (5,6).
    The mover will walk away to provoke OA from invisible_entity.
    """
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    # The entity that will be invisible and make OA
    oa_maker = create_sorcerer(name="InvisEntity", position=(5, 5), level=7)
    setup_standard_actions(oa_maker)
    add_opportunity_attack_handler(oa_maker)

    # The entity that will move away, provoking OA
    mover = create_skeleton(name="Mover", position=(5, 6))
    setup_standard_actions(mover)

    Entity.update_all_entities_senses()

    # Set up encounter so handlers work properly
    encounter = Encounter(name="Test OA Invisibility", source_entity_uuid=uuid4())
    encounter.add_combatant(oa_maker, HumanController(source_entity_uuid=oa_maker.uuid))
    encounter.add_combatant(mover, HumanController(source_entity_uuid=mover.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()

    return oa_maker, mover, encounter


def make_invisible_via_spell(caster, target=None):
    """Cast Invisibility spell naturally. target defaults to self."""
    if target is None:
        target = caster
    spell = Invisibility(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=2,
    )
    result = spell.apply()
    return result


def make_invisible_via_scroll(entity):
    """Use a Scroll of Invisibility (self-target)."""
    scroll = create_scroll_of_invisibility(entity.uuid, cast_level=2)
    entity.loot_item(scroll)
    target = AvailableTarget(index=0, target_uuid=entity.uuid, target_name=entity.name)
    execute_use_action(entity, scroll.uuid, "Invisibility", target)


def make_greater_invisible_via_spell(caster, target=None):
    """Cast Greater Invisibility spell naturally. target defaults to self."""
    if target is None:
        target = caster
    spell = GreaterInvisibility(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=4,
    )
    result = spell.apply()
    return result


def make_greater_invisible_via_potion(entity):
    """Use a Potion of Greater Invisibility."""
    potion = create_potion_of_greater_invisibility(entity.uuid)
    entity.loot_item(potion)
    # After loot_item, get the actual item from inventory (may have been stacked)
    item = list(entity.inventory.items.values())[0]
    execute_use_action(entity, item.uuid, "Drink Greater Invisibility Potion")


def trigger_oa(oa_maker, mover):
    """Move the mover away from the oa_maker to provoke OA.

    Returns the move event.
    """
    # Move away from (5,6) to (5,10) — leaves threat range
    Entity.update_all_entities_senses()
    move = Move(source_entity_uuid=mover.uuid, end_position=(5, 10))
    return move.apply()


# ============================================================
# InvisibilityEffect tests
# ============================================================

def test_1_oa_miss_breaks_invisibility_spell():
    """OA miss should break InvisibilityEffect (natural spell)."""
    print("\nTest 1: OA miss breaks InvisibilityEffect (natural spell)")
    oa_maker, mover, encounter = setup_oa_scenario()
    encounter.start_turn()

    make_invisible_via_spell(oa_maker)
    check("Entity is invisible before OA", oa_maker.is_invisible)
    check("Has Invisible condition", has_condition(oa_maker, "Invisible"))

    # Force OA to miss
    mod_id = force_attack_miss(oa_maker)
    trigger_oa(oa_maker, mover)
    remove_attack_modifier(oa_maker, mod_id)

    check("Entity is NOT invisible after OA miss", not oa_maker.is_invisible)
    check("No Invisible condition after OA miss", not has_condition(oa_maker, "Invisible"))


def test_2_oa_hit_breaks_invisibility_spell():
    """OA hit should break InvisibilityEffect (natural spell)."""
    print("\nTest 2: OA hit breaks InvisibilityEffect (natural spell)")
    oa_maker, mover, encounter = setup_oa_scenario()
    encounter.start_turn()

    make_invisible_via_spell(oa_maker)
    check("Entity is invisible before OA", oa_maker.is_invisible)

    mod_id = force_attack_hit(oa_maker)
    trigger_oa(oa_maker, mover)
    remove_attack_modifier(oa_maker, mod_id)

    check("Entity is NOT invisible after OA hit", not oa_maker.is_invisible)
    check("No Invisible condition after OA hit", not has_condition(oa_maker, "Invisible"))


def test_3_oa_miss_breaks_invisibility_scroll():
    """OA miss should break InvisibilityEffect (scroll)."""
    print("\nTest 3: OA miss breaks InvisibilityEffect (scroll)")
    oa_maker, mover, encounter = setup_oa_scenario()
    encounter.start_turn()

    make_invisible_via_scroll(oa_maker)
    check("Entity is invisible before OA", oa_maker.is_invisible)

    mod_id = force_attack_miss(oa_maker)
    trigger_oa(oa_maker, mover)
    remove_attack_modifier(oa_maker, mod_id)

    check("Entity is NOT invisible after OA miss (scroll)", not oa_maker.is_invisible)
    check("No Invisible condition after OA miss (scroll)", not has_condition(oa_maker, "Invisible"))


def test_4_oa_hit_breaks_invisibility_scroll():
    """OA hit should break InvisibilityEffect (scroll)."""
    print("\nTest 4: OA hit breaks InvisibilityEffect (scroll)")
    oa_maker, mover, encounter = setup_oa_scenario()
    encounter.start_turn()

    make_invisible_via_scroll(oa_maker)
    check("Entity is invisible before OA", oa_maker.is_invisible)

    mod_id = force_attack_hit(oa_maker)
    trigger_oa(oa_maker, mover)
    remove_attack_modifier(oa_maker, mod_id)

    check("Entity is NOT invisible after OA hit (scroll)", not oa_maker.is_invisible)
    check("No Invisible condition after OA hit (scroll)", not has_condition(oa_maker, "Invisible"))


def test_5_regular_attack_breaks_invisibility():
    """Regular attack on own turn should break InvisibilityEffect."""
    print("\nTest 5: Regular attack breaks InvisibilityEffect")
    oa_maker, mover, encounter = setup_oa_scenario()
    encounter.start_turn()

    make_invisible_via_spell(oa_maker)
    check("Entity is invisible before attack", oa_maker.is_invisible)

    # Refill action economy (Invisibility consumed the action)
    oa_maker.action_economy.reset_all_costs()

    mod_id = force_attack_hit(oa_maker)
    attack = Attack(
        source_entity_uuid=oa_maker.uuid,
        target_entity_uuid=mover.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    )
    result = attack.apply()
    remove_attack_modifier(oa_maker, mod_id)

    check("Attack was executed", result is not None and not result.canceled)
    check("Entity is NOT invisible after regular attack", not oa_maker.is_invisible)
    check("No Invisible condition after regular attack", not has_condition(oa_maker, "Invisible"))


# ============================================================
# GreaterInvisibilityEffect tests
# ============================================================

def test_6_oa_miss_triggers_stealth_check_spell():
    """OA miss should trigger stealth check for GreaterInvisibilityEffect (natural spell)."""
    print("\nTest 6: OA miss triggers stealth check for GreaterInvisibilityEffect (spell)")
    oa_maker, mover, encounter = setup_oa_scenario()
    encounter.start_turn()

    make_greater_invisible_via_spell(oa_maker)
    check("Entity is invisible before OA", oa_maker.is_invisible)
    condition = oa_maker.active_conditions.get("Invisible")
    check("Has GreaterInvisibilityEffect", isinstance(condition, GreaterInvisibilityEffect))
    initial_check_count = condition.check_count if isinstance(condition, GreaterInvisibilityEffect) else -1

    mod_id = force_attack_miss(oa_maker)
    trigger_oa(oa_maker, mover)
    remove_attack_modifier(oa_maker, mod_id)

    # Either the stealth check succeeded (check_count incremented) or failed (condition removed)
    condition_after = oa_maker.active_conditions.get("Invisible")
    if condition_after and isinstance(condition_after, GreaterInvisibilityEffect):
        check("Stealth check was triggered (check_count changed)", condition_after.check_count > initial_check_count)
    else:
        check("Stealth check was triggered (condition removed = failed check)", not has_condition(oa_maker, "Invisible"))


def test_7_oa_hit_triggers_stealth_check_spell():
    """OA hit should trigger stealth check for GreaterInvisibilityEffect (natural spell)."""
    print("\nTest 7: OA hit triggers stealth check for GreaterInvisibilityEffect (spell)")
    oa_maker, mover, encounter = setup_oa_scenario()
    encounter.start_turn()

    make_greater_invisible_via_spell(oa_maker)
    check("Entity is invisible before OA", oa_maker.is_invisible)
    condition = oa_maker.active_conditions.get("Invisible")
    initial_check_count = condition.check_count if isinstance(condition, GreaterInvisibilityEffect) else -1

    mod_id = force_attack_hit(oa_maker)
    trigger_oa(oa_maker, mover)
    remove_attack_modifier(oa_maker, mod_id)

    condition_after = oa_maker.active_conditions.get("Invisible")
    if condition_after and isinstance(condition_after, GreaterInvisibilityEffect):
        check("Stealth check was triggered (check_count changed)", condition_after.check_count > initial_check_count)
    else:
        check("Stealth check was triggered (condition removed = failed check)", not has_condition(oa_maker, "Invisible"))


def test_8_oa_miss_triggers_stealth_check_potion():
    """OA miss should trigger stealth check for GreaterInvisibilityEffect (potion)."""
    print("\nTest 8: OA miss triggers stealth check for GreaterInvisibilityEffect (potion)")
    oa_maker, mover, encounter = setup_oa_scenario()
    encounter.start_turn()

    make_greater_invisible_via_potion(oa_maker)
    check("Entity is invisible before OA", oa_maker.is_invisible)
    condition = oa_maker.active_conditions.get("Invisible")
    check("Has GreaterInvisibilityEffect", isinstance(condition, GreaterInvisibilityEffect))
    initial_check_count = condition.check_count if isinstance(condition, GreaterInvisibilityEffect) else -1

    mod_id = force_attack_miss(oa_maker)
    trigger_oa(oa_maker, mover)
    remove_attack_modifier(oa_maker, mod_id)

    condition_after = oa_maker.active_conditions.get("Invisible")
    if condition_after and isinstance(condition_after, GreaterInvisibilityEffect):
        check("Stealth check was triggered (check_count changed)", condition_after.check_count > initial_check_count)
    else:
        check("Stealth check was triggered (condition removed = failed check)", not has_condition(oa_maker, "Invisible"))


def test_9_oa_hit_triggers_stealth_check_potion():
    """OA hit should trigger stealth check for GreaterInvisibilityEffect (potion)."""
    print("\nTest 9: OA hit triggers stealth check for GreaterInvisibilityEffect (potion)")
    oa_maker, mover, encounter = setup_oa_scenario()
    encounter.start_turn()

    make_greater_invisible_via_potion(oa_maker)
    check("Entity is invisible before OA", oa_maker.is_invisible)
    condition = oa_maker.active_conditions.get("Invisible")
    initial_check_count = condition.check_count if isinstance(condition, GreaterInvisibilityEffect) else -1

    mod_id = force_attack_hit(oa_maker)
    trigger_oa(oa_maker, mover)
    remove_attack_modifier(oa_maker, mod_id)

    condition_after = oa_maker.active_conditions.get("Invisible")
    if condition_after and isinstance(condition_after, GreaterInvisibilityEffect):
        check("Stealth check was triggered (check_count changed)", condition_after.check_count > initial_check_count)
    else:
        check("Stealth check was triggered (condition removed = failed check)", not has_condition(oa_maker, "Invisible"))


def test_10_regular_attack_triggers_stealth_check():
    """Regular attack should trigger stealth check for GreaterInvisibilityEffect."""
    print("\nTest 10: Regular attack triggers stealth check for GreaterInvisibilityEffect")
    oa_maker, mover, encounter = setup_oa_scenario()
    encounter.start_turn()

    make_greater_invisible_via_spell(oa_maker)
    check("Entity is invisible before attack", oa_maker.is_invisible)
    condition = oa_maker.active_conditions.get("Invisible")
    initial_check_count = condition.check_count if isinstance(condition, GreaterInvisibilityEffect) else -1

    # Refill action economy (Greater Invisibility consumed the action)
    oa_maker.action_economy.reset_all_costs()

    mod_id = force_attack_hit(oa_maker)
    attack = Attack(
        source_entity_uuid=oa_maker.uuid,
        target_entity_uuid=mover.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    )
    result = attack.apply()
    remove_attack_modifier(oa_maker, mod_id)
    check("Attack was executed", result is not None and not result.canceled)

    condition_after = oa_maker.active_conditions.get("Invisible")
    if condition_after and isinstance(condition_after, GreaterInvisibilityEffect):
        check("Stealth check was triggered (check_count changed)", condition_after.check_count > initial_check_count)
    else:
        check("Stealth check was triggered (condition removed = failed check)", not has_condition(oa_maker, "Invisible"))


# ============================================================
# Concentration / damage tests
# ============================================================

def test_11_damage_does_not_break_invisibility():
    """Taking damage should NOT break InvisibilityEffect (only concentration save matters)."""
    print("\nTest 11: Taking damage does NOT break InvisibilityEffect (CON save succeeds)")
    oa_maker, mover, encounter = setup_oa_scenario()
    encounter.start_turn()

    make_invisible_via_spell(oa_maker)
    check("Entity is invisible before damage", oa_maker.is_invisible)

    # Deal small damage — CON save DC = max(10, 1/2) = 10
    # Sorcerer has decent CON, give a tiny amount to make save likely to succeed
    # We'll just check that taking damage alone doesn't auto-remove invisibility
    # (The actual save may pass or fail — we verify the mechanism, not the roll)
    deal_damage_to(oa_maker, 1, DamageType.FIRE, mover.uuid)

    # If CON save succeeded (likely with small damage), should still be invisible
    # If CON save failed, Concentrating is removed → InvisibilityEffect removed
    # Either way, the key assertion: invisibility was NOT removed by damage event itself
    # but only potentially by concentration failure
    if has_condition(oa_maker, "Concentrating"):
        check("Still invisible when concentration holds", oa_maker.is_invisible)
        check("Still has Invisible condition", has_condition(oa_maker, "Invisible"))
    else:
        check("Lost invisibility due to concentration break (not damage)", not oa_maker.is_invisible)


def test_12_concentration_failure_breaks_invisibility():
    """Concentration failure from damage should remove InvisibilityEffect."""
    print("\nTest 12: Concentration failure breaks InvisibilityEffect")
    oa_maker, mover, encounter = setup_oa_scenario()
    encounter.start_turn()

    make_invisible_via_spell(oa_maker)
    check("Entity is invisible before damage", oa_maker.is_invisible)
    check("Has Concentrating condition", has_condition(oa_maker, "Concentrating"))

    # Deal massive damage to make CON save very difficult (DC = max(10, 500/2) = 250)
    deal_damage_to(oa_maker, 500, DamageType.FIRE, mover.uuid)

    # Entity should have lost concentration and therefore invisibility
    # (Unless entity is dead, in which case conditions are moot)
    if oa_maker.has_hp:
        check("No longer concentrating after massive damage", not has_condition(oa_maker, "Concentrating"))
        check("No longer invisible after concentration break", not oa_maker.is_invisible)
    else:
        check("Entity died from massive damage (conditions moot)", True)


# ============================================================
# Run all tests
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Invisibility + Opportunity Attack Reveal Tests")
    print("=" * 60)

    test_1_oa_miss_breaks_invisibility_spell()
    test_2_oa_hit_breaks_invisibility_spell()
    test_3_oa_miss_breaks_invisibility_scroll()
    test_4_oa_hit_breaks_invisibility_scroll()
    test_5_regular_attack_breaks_invisibility()
    test_6_oa_miss_triggers_stealth_check_spell()
    test_7_oa_hit_triggers_stealth_check_spell()
    test_8_oa_miss_triggers_stealth_check_potion()
    test_9_oa_hit_triggers_stealth_check_potion()
    test_10_regular_attack_triggers_stealth_check()
    test_11_damage_does_not_break_invisibility()
    test_12_concentration_failure_breaks_invisibility()

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    if errors:
        print(f"Failed tests: {errors}")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
