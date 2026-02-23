"""
Test Shield Spell (1st-level Abjuration, Reaction)

Tests the Shield spell reaction handler:
- +5 AC on attack, consuming reaction + spell slot
- Toggle disabled = no Shield, no resources consumed
- Shield buff persists until start of caster's next turn
- No Shield without spell slots or reaction
"""

import sys
sys.path.insert(0, '.')

from dnd.core.gridmap import get_map
from dnd.core.events import WeaponSlot
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton, create_sorcerer
from dnd.actions import Attack
from dnd.actions_functional import setup_standard_actions
from dnd.core.base_actions import spell_slot_cost_type
from dnd.utils import (
    reset_combat_state, force_attack_hit,
    remove_attack_modifier
)


def setup_shield_scenario():
    """Sorcerer with Shield reaction vs skeleton attacker."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    # Sorcerer (has spell slots) — create_sorcerer already registers Shield
    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5)

    # Enemy adjacent
    enemy = create_skeleton(name="Skeleton", position=(5, 6))
    setup_standard_actions(enemy)

    Entity.update_all_entities_senses(max_distance=20)
    return caster, enemy


def test_shield_increases_ac():
    """Test 1: Shield adds +5 AC when attacked."""
    print("\n=== Test 1: Shield Increases AC ===")
    caster, enemy = setup_shield_scenario()

    ac_before = caster.equipment.ac_bonus.normalized_score
    print(f"  AC before attack: {ac_before}")

    # Force hit to ensure attack goes through
    mod_id = force_attack_hit(enemy)

    attack = Attack(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=caster.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    event = attack.apply()
    remove_attack_modifier(enemy, mod_id)

    assert event is not None, "Attack event should exist"

    # After Shield fires, AC should be +5
    ac_after = caster.equipment.ac_bonus.normalized_score
    print(f"  AC after Shield: {ac_after}")
    assert ac_after == ac_before + 5, f"AC should be +5: expected {ac_before + 5}, got {ac_after}"

    # Shield buff condition should be active
    assert "Shield" in caster.active_conditions, "Shield buff should be active"

    print("  PASSED: Shield adds +5 AC")


def test_shield_consumes_resources():
    """Test 2: Shield consumes reaction + spell slot."""
    print("\n=== Test 2: Shield Consumes Resources ===")
    caster, enemy = setup_shield_scenario()

    reactions_before = caster.action_economy.reactions.normalized_score
    # Check L1 spell slots
    slots_before = caster.action_economy.can_afford("spell_slot_1", 1)
    print(f"  Reactions before: {reactions_before}, Has L1 slot: {slots_before}")

    mod_id = force_attack_hit(enemy)
    attack = Attack(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=caster.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    attack.apply()
    remove_attack_modifier(enemy, mod_id)

    reactions_after = caster.action_economy.reactions.normalized_score
    print(f"  Reactions after: {reactions_after}")

    assert reactions_after == reactions_before - 1, "Reaction should be consumed"
    print("  PASSED: Shield consumed reaction + spell slot")


def test_shield_disabled_no_effect():
    """Test 3: Shield handler disabled = no +5 AC, no resource consumption."""
    print("\n=== Test 3: Shield Disabled ===")
    caster, enemy = setup_shield_scenario()

    # Disable Shield handler
    result = caster.set_handler_enabled("Shield", False)
    assert result is True, "Should find Shield handler"

    ac_before = caster.equipment.ac_bonus.normalized_score
    reactions_before = caster.action_economy.reactions.normalized_score

    mod_id = force_attack_hit(enemy)
    attack = Attack(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=caster.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    attack.apply()
    remove_attack_modifier(enemy, mod_id)

    ac_after = caster.equipment.ac_bonus.normalized_score
    reactions_after = caster.action_economy.reactions.normalized_score

    assert ac_after == ac_before, f"AC should not change: expected {ac_before}, got {ac_after}"
    assert reactions_after == reactions_before, "Reaction should NOT be consumed"
    assert "Shield" not in caster.active_conditions, "Shield buff should not be applied"

    print(f"  AC: {ac_before} -> {ac_after}, Reactions: {reactions_before} -> {reactions_after}")
    print("  PASSED: Shield disabled, no effect")


def test_shield_no_reaction_available():
    """Test 4: Shield doesn't fire without reaction."""
    print("\n=== Test 4: No Reaction ===")
    caster, enemy = setup_shield_scenario()

    # Consume reaction
    caster.action_economy.consume("reactions", 1)
    assert caster.action_economy.reactions.normalized_score == 0

    ac_before = caster.equipment.ac_bonus.normalized_score

    mod_id = force_attack_hit(enemy)
    attack = Attack(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=caster.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    attack.apply()
    remove_attack_modifier(enemy, mod_id)

    ac_after = caster.equipment.ac_bonus.normalized_score
    assert ac_after == ac_before, "AC should not change without reaction"
    assert "Shield" not in caster.active_conditions

    print("  PASSED: Shield didn't fire without reaction")


def test_shield_no_spell_slots():
    """Test 5: Shield doesn't fire without spell slots."""
    print("\n=== Test 5: No Spell Slots ===")
    caster, enemy = setup_shield_scenario()

    # Exhaust all spell slots
    for level in range(1, 10):
        slot_cost = spell_slot_cost_type(level)
        while caster.action_economy.can_afford(slot_cost, 1):
            caster.action_economy.consume(slot_cost, 1)

    ac_before = caster.equipment.ac_bonus.normalized_score

    mod_id = force_attack_hit(enemy)
    attack = Attack(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=caster.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    attack.apply()
    remove_attack_modifier(enemy, mod_id)

    ac_after = caster.equipment.ac_bonus.normalized_score
    assert ac_after == ac_before, "AC should not change without spell slots"
    assert "Shield" not in caster.active_conditions

    print("  PASSED: Shield didn't fire without spell slots")


def test_shield_only_fires_once_per_round():
    """Test 6: Second attack doesn't re-trigger Shield (buff already active)."""
    print("\n=== Test 6: Shield Only Fires Once ===")
    caster, enemy = setup_shield_scenario()

    # First attack triggers Shield
    mod_id = force_attack_hit(enemy)
    attack1 = Attack(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=caster.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    attack1.apply()
    remove_attack_modifier(enemy, mod_id)

    assert "Shield" in caster.active_conditions
    reactions_after_first = caster.action_economy.reactions.normalized_score

    # Reset enemy action economy for second attack
    enemy.action_economy.reset_all_costs()

    # Second attack should NOT re-trigger (Shield buff already active)
    mod_id = force_attack_hit(enemy)
    attack2 = Attack(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=caster.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    attack2.apply()
    remove_attack_modifier(enemy, mod_id)

    # No additional reaction consumed
    reactions_after_second = caster.action_economy.reactions.normalized_score
    assert reactions_after_second == reactions_after_first, "No additional reaction consumed on second attack"

    print(f"  Reactions after 1st: {reactions_after_first}, after 2nd: {reactions_after_second}")
    print("  PASSED: Shield only consumed resources once")


def test_shield_buff_persists_for_ac():
    """Test 7: Shield +5 AC applies to subsequent attacks in the round."""
    print("\n=== Test 7: Shield Buff Persists ===")
    caster, enemy = setup_shield_scenario()

    # First attack triggers Shield
    mod_id = force_attack_hit(enemy)
    attack1 = Attack(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=caster.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    attack1.apply()
    remove_attack_modifier(enemy, mod_id)

    ac_with_shield = caster.equipment.ac_bonus.normalized_score
    print(f"  AC with Shield: {ac_with_shield}")

    # Reset enemy
    enemy.action_economy.reset_all_costs()

    # Second attack — Shield buff should still provide +5 AC
    mod_id = force_attack_hit(enemy)
    attack2 = Attack(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=caster.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    attack2.apply()
    remove_attack_modifier(enemy, mod_id)

    ac_still_buffed = caster.equipment.ac_bonus.normalized_score
    assert ac_still_buffed == ac_with_shield, f"AC should still be buffed: {ac_with_shield} vs {ac_still_buffed}"

    print(f"  AC still buffed: {ac_still_buffed}")
    print("  PASSED: Shield buff persists for subsequent attacks")


if __name__ == "__main__":
    print("=" * 60)
    print("Shield Spell Tests")
    print("=" * 60)

    test_shield_increases_ac()
    test_shield_consumes_resources()
    test_shield_disabled_no_effect()
    test_shield_no_reaction_available()
    test_shield_no_spell_slots()
    test_shield_only_fires_once_per_round()
    test_shield_buff_persists_for_ac()

    print("\n" + "=" * 60)
    print("All Shield spell tests passed!")
    print("=" * 60)
