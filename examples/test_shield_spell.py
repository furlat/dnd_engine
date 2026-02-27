"""
Test Shield Spell (1st-level Abjuration, Reaction)

Shield fires AFTER seeing the attack roll (5e timing):
- Only on normal HIT (not CRIT, MISS, CRIT_MISS, AUTOHIT)
- Only if +5 AC would change the outcome to MISS
- Consumes reaction + spell slot
- Shield vs Magic Missile: blocks all darts (separate trigger)

Sorcerer (AC 12, unarmored DEX 14) vs Skeleton (+4 attack, finesse shortsword)
- total = d20 + 4, AC = 12, AC + 5 = 17
- Shield range: d20 in [8..12] (total 12..16)
"""

import sys
sys.path.insert(0, '.')

import random

from dnd.core.gridmap import get_map
from dnd.core.events import WeaponSlot
from dnd.core.dice import AttackOutcome
from dnd.core.modifiers import NumericalModifier
from dnd.core.base_actions import spell_slot_cost_type
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton, create_caster
from dnd.actions import Attack
from dnd.actions_functional import setup_standard_actions
from dnd.utils import reset_combat_state, get_hp


# ---------------------------------------------------------------------------
# Dice control helpers
# ---------------------------------------------------------------------------
_original_randint = random.randint


def force_d20(value: int):
    """Force d20 rolls (randint(1,20)) to return `value`. Other dice unaffected."""
    def patched(a, b):
        if a == 1 and b == 20:
            return value
        return _original_randint(a, b)
    random.randint = patched


def restore_d20():
    random.randint = _original_randint


# ---------------------------------------------------------------------------
# Scenario setup
# ---------------------------------------------------------------------------
def setup_shield_scenario():
    """Sorcerer (AC 12) with Shield reaction vs skeleton attacker (+4 to hit)."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    caster = create_caster(name="Wizard", position=(5, 5), level=5)
    enemy = create_skeleton(name="Skeleton", position=(5, 6))
    setup_standard_actions(enemy)

    Entity.update_all_entities_senses(max_distance=20)
    return caster, enemy


def do_attack(enemy, caster):
    """Execute a melee attack from enemy -> caster. Returns the event."""
    attack = Attack(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=caster.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    return attack.apply()


# ===================================================================
# Tests: Shield reaction firing logic
# ===================================================================

def test_shield_fires_on_marginal_hit():
    """Test 1: Shield fires when attack hits but +5 AC would block it."""
    print("\n=== Test 1: Shield Fires on Marginal Hit ===")
    caster, enemy = setup_shield_scenario()
    ac_before = caster.equipment.ac_bonus.normalized_score

    # d20=10 → total=14, HIT (14 >= 12), Shield helps (14 < 17)
    force_d20(10)
    try:
        event = do_attack(enemy, caster)
    finally:
        restore_d20()

    ac_after = caster.equipment.ac_bonus.normalized_score
    print(f"  AC: {ac_before} → {ac_after}")
    assert ac_after == ac_before + 5, f"Expected AC {ac_before + 5}, got {ac_after}"
    assert "Shield" in caster.active_conditions, "Shield condition should be active"

    # Attack outcome changed to MISS by Shield
    assert event is not None
    assert event.attack_outcome == AttackOutcome.MISS, f"Expected MISS, got {event.attack_outcome}"

    print("  PASSED: Shield fired, attack became MISS")


def test_shield_does_not_fire_on_crit():
    """Test 2: Shield does NOT fire on natural 20 (CRIT can't be blocked)."""
    print("\n=== Test 2: No Shield on Crit ===")
    caster, enemy = setup_shield_scenario()
    ac_before = caster.equipment.ac_bonus.normalized_score
    reactions_before = caster.action_economy.reactions.normalized_score

    force_d20(20)
    try:
        do_attack(enemy, caster)
    finally:
        restore_d20()

    assert caster.equipment.ac_bonus.normalized_score == ac_before, "AC unchanged"
    assert caster.action_economy.reactions.normalized_score == reactions_before, "Reaction not consumed"
    assert "Shield" not in caster.active_conditions

    print("  PASSED: Shield did not fire on crit")


def test_shield_does_not_fire_on_miss():
    """Test 3: Shield does NOT fire on a miss (no need)."""
    print("\n=== Test 3: No Shield on Miss ===")
    caster, enemy = setup_shield_scenario()
    ac_before = caster.equipment.ac_bonus.normalized_score
    reactions_before = caster.action_economy.reactions.normalized_score

    # d20=5 → total=9, MISS (9 < 12)
    force_d20(5)
    try:
        do_attack(enemy, caster)
    finally:
        restore_d20()

    assert caster.equipment.ac_bonus.normalized_score == ac_before, "AC unchanged"
    assert caster.action_economy.reactions.normalized_score == reactions_before, "Reaction not consumed"
    assert "Shield" not in caster.active_conditions

    print("  PASSED: Shield did not fire on miss")


def test_shield_does_not_fire_on_crit_miss():
    """Test 4: Shield does NOT fire on natural 1 (CRIT_MISS)."""
    print("\n=== Test 4: No Shield on Crit Miss ===")
    caster, enemy = setup_shield_scenario()
    reactions_before = caster.action_economy.reactions.normalized_score

    force_d20(1)
    try:
        do_attack(enemy, caster)
    finally:
        restore_d20()

    assert caster.action_economy.reactions.normalized_score == reactions_before, "Reaction not consumed"
    assert "Shield" not in caster.active_conditions

    print("  PASSED: Shield did not fire on crit miss")


def test_shield_does_not_fire_when_unhelpful():
    """Test 5: Shield does NOT fire when +5 AC wouldn't block the attack."""
    print("\n=== Test 5: No Shield When +5 Wouldn't Help ===")
    caster, enemy = setup_shield_scenario()
    ac_before = caster.equipment.ac_bonus.normalized_score
    reactions_before = caster.action_economy.reactions.normalized_score

    # d20=15 → total=19, HIT, 19 >= 17 (AC+5) → Shield useless
    force_d20(15)
    try:
        event = do_attack(enemy, caster)
    finally:
        restore_d20()

    assert caster.equipment.ac_bonus.normalized_score == ac_before, "AC unchanged"
    assert caster.action_economy.reactions.normalized_score == reactions_before, "Reaction saved"
    assert "Shield" not in caster.active_conditions
    # Attack still hits (no Shield to block it)
    assert event is not None
    assert event.attack_outcome == AttackOutcome.HIT, f"Should still HIT, got {event.attack_outcome}"

    print("  PASSED: Shield saved resources on unblockable hit")


# ===================================================================
# Tests: Shield resource consumption
# ===================================================================

def test_shield_consumes_resources():
    """Test 6: Shield consumes reaction + L1 spell slot."""
    print("\n=== Test 6: Shield Consumes Resources ===")
    caster, enemy = setup_shield_scenario()

    reactions_before = caster.action_economy.reactions.normalized_score

    force_d20(10)
    try:
        do_attack(enemy, caster)
    finally:
        restore_d20()

    reactions_after = caster.action_economy.reactions.normalized_score
    assert reactions_after == reactions_before - 1, "Reaction should be consumed"
    assert "Shield" in caster.active_conditions

    print(f"  Reactions: {reactions_before} → {reactions_after}")
    print("  PASSED")


def test_shield_disabled_no_effect():
    """Test 7: Shield handler disabled → attack hits, no resources consumed."""
    print("\n=== Test 7: Shield Disabled ===")
    caster, enemy = setup_shield_scenario()

    result = caster.set_handler_enabled("Shield", False)
    assert result is True, "Should find Shield handler"

    ac_before = caster.equipment.ac_bonus.normalized_score
    reactions_before = caster.action_economy.reactions.normalized_score

    force_d20(10)
    try:
        do_attack(enemy, caster)
    finally:
        restore_d20()

    assert caster.equipment.ac_bonus.normalized_score == ac_before, "AC unchanged"
    assert caster.action_economy.reactions.normalized_score == reactions_before, "Reaction not consumed"
    assert "Shield" not in caster.active_conditions

    print("  PASSED: Shield disabled, no effect")


def test_shield_no_reaction_available():
    """Test 8: Shield doesn't fire without reaction."""
    print("\n=== Test 8: No Reaction ===")
    caster, enemy = setup_shield_scenario()

    caster.action_economy.consume("reactions", 1)
    assert caster.action_economy.reactions.normalized_score == 0

    ac_before = caster.equipment.ac_bonus.normalized_score

    force_d20(10)
    try:
        do_attack(enemy, caster)
    finally:
        restore_d20()

    assert caster.equipment.ac_bonus.normalized_score == ac_before, "AC unchanged"
    assert "Shield" not in caster.active_conditions

    print("  PASSED: No reaction, Shield didn't fire")


def test_shield_no_spell_slots():
    """Test 9: Shield doesn't fire without spell slots."""
    print("\n=== Test 9: No Spell Slots ===")
    caster, enemy = setup_shield_scenario()

    for level in range(1, 10):
        slot_cost = spell_slot_cost_type(level)
        while caster.action_economy.can_afford(slot_cost, 1):
            caster.action_economy.consume(slot_cost, 1)

    ac_before = caster.equipment.ac_bonus.normalized_score

    force_d20(10)
    try:
        do_attack(enemy, caster)
    finally:
        restore_d20()

    assert caster.equipment.ac_bonus.normalized_score == ac_before, "AC unchanged"
    assert "Shield" not in caster.active_conditions

    print("  PASSED: No spell slots, Shield didn't fire")


# ===================================================================
# Tests: Shield buff persistence and stacking
# ===================================================================

def test_shield_only_fires_once_per_round():
    """Test 10: Second attack doesn't re-trigger Shield (buff already active)."""
    print("\n=== Test 10: Shield Only Fires Once ===")
    caster, enemy = setup_shield_scenario()

    force_d20(10)
    try:
        do_attack(enemy, caster)
    finally:
        restore_d20()

    assert "Shield" in caster.active_conditions
    reactions_after_first = caster.action_economy.reactions.normalized_score

    # Second attack (buff active → handler skips)
    enemy.action_economy.reset_all_costs()
    force_d20(10)
    try:
        do_attack(enemy, caster)
    finally:
        restore_d20()

    reactions_after_second = caster.action_economy.reactions.normalized_score
    assert reactions_after_second == reactions_after_first, "No additional reaction consumed"

    print(f"  Reactions: {reactions_after_first} → {reactions_after_second}")
    print("  PASSED")


def test_shield_buff_persists_for_ac():
    """Test 11: Shield +5 AC persists for subsequent attacks in the round."""
    print("\n=== Test 11: Shield Buff Persists ===")
    caster, enemy = setup_shield_scenario()
    ac_before = caster.equipment.ac_bonus.normalized_score

    force_d20(10)
    try:
        do_attack(enemy, caster)
    finally:
        restore_d20()

    ac_with_shield = caster.equipment.ac_bonus.normalized_score
    assert ac_with_shield == ac_before + 5, f"AC should be +5: {ac_with_shield}"

    # Second attack — AC should still be buffed
    enemy.action_economy.reset_all_costs()
    force_d20(10)
    try:
        do_attack(enemy, caster)
    finally:
        restore_d20()

    ac_still = caster.equipment.ac_bonus.normalized_score
    assert ac_still == ac_with_shield, f"AC should stay buffed: {ac_still} vs {ac_with_shield}"

    print(f"  AC persists at {ac_still}")
    print("  PASSED")


def test_shield_no_stacking():
    """Test 12: Shield does not stack to +10 even with extra reactions."""
    print("\n=== Test 12: No Shield Stacking ===")
    caster, enemy = setup_shield_scenario()
    ac_base = caster.equipment.ac_bonus.normalized_score

    # Give caster 2 reactions
    caster.action_economy.reactions.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            name="Extra Reaction",
            value=1
        )
    )

    force_d20(10)
    try:
        do_attack(enemy, caster)
    finally:
        restore_d20()

    assert caster.equipment.ac_bonus.normalized_score == ac_base + 5

    enemy.action_economy.reset_all_costs()
    force_d20(10)
    try:
        do_attack(enemy, caster)
    finally:
        restore_d20()

    ac_after = caster.equipment.ac_bonus.normalized_score
    assert ac_after == ac_base + 5, f"Must NOT stack to +10: got {ac_after}"

    print(f"  AC stayed at +5: {ac_after}")
    print("  PASSED")


def test_shield_refires_after_removal():
    """Test 13: Shield can fire again after buff is removed (dispel etc.)."""
    print("\n=== Test 13: Shield Refires After Removal ===")
    caster, enemy = setup_shield_scenario()
    ac_base = caster.equipment.ac_bonus.normalized_score

    # Give caster 2 reactions
    caster.action_economy.reactions.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            name="Extra Reaction",
            value=1
        )
    )

    # First attack → Shield fires
    force_d20(10)
    try:
        do_attack(enemy, caster)
    finally:
        restore_d20()

    assert "Shield" in caster.active_conditions
    assert caster.equipment.ac_bonus.normalized_score == ac_base + 5

    # Remove Shield (dispel)
    caster.remove_condition("Shield")
    assert "Shield" not in caster.active_conditions
    assert caster.equipment.ac_bonus.normalized_score == ac_base

    # Second attack → Shield fires again
    enemy.action_economy.reset_all_costs()
    force_d20(10)
    try:
        do_attack(enemy, caster)
    finally:
        restore_d20()

    assert "Shield" in caster.active_conditions, "Shield should refire"
    assert caster.equipment.ac_bonus.normalized_score == ac_base + 5

    print(f"  Shield refired, AC back to {ac_base + 5}")
    print("  PASSED")


# ===================================================================
# Tests: Shield vs Magic Missile
# ===================================================================

def setup_shield_vs_mm_scenario():
    """Sorcerer with Shield reaction vs enemy caster with Magic Missile."""
    from dnd.spells.evocation import MagicMissile
    from dnd.actions_functional import register_spell

    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)

    caster = create_caster(name="Wizard", position=(5, 5), level=5)
    enemy = create_caster(name="Enemy Mage", position=(5, 10), level=5)
    enemy.faction = None
    register_spell(enemy, MagicMissile, caster_level=5)

    Entity.update_all_entities_senses(max_distance=20)
    return caster, enemy


def test_shield_blocks_all_mm_darts():
    """Test 14: Shield blocks ALL Magic Missile darts on single target."""
    from dnd.spells.evocation import MagicMissile

    print("\n=== Test 14: Shield Blocks All MM Darts ===")
    caster, enemy = setup_shield_vs_mm_scenario()

    hp_before = get_hp(caster)
    mm = MagicMissile(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=caster.uuid,
        cast_at_level=1
    )
    mm.apply()

    hp_after = get_hp(caster)
    assert hp_after == hp_before, f"Shield blocks all MM: {hp_before} → {hp_after}"
    assert "Shield" in caster.active_conditions
    assert caster.action_economy.reactions.normalized_score == 0, "Reaction consumed"

    print(f"  HP unchanged: {hp_after}")
    print("  PASSED")


def test_shield_blocks_own_darts_others_take_damage():
    """Test 15: Shield only blocks darts on shielded entity; others take damage."""
    from dnd.spells.evocation import MagicMissile

    print("\n=== Test 15: Shield Blocks Own Darts Only ===")
    caster, enemy = setup_shield_vs_mm_scenario()

    ally = create_skeleton(name="Fighter", position=(5, 6))
    setup_standard_actions(ally)
    ally.faction = "heroes"
    Entity.update_all_entities_senses(max_distance=20)

    hp_wizard_before = get_hp(caster)
    hp_fighter_before = get_hp(ally)

    mm = MagicMissile(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=caster.uuid,
        extra_target_entity_uuids=[ally.uuid],
        cast_at_level=1
    )
    mm.apply()

    hp_wizard_after = get_hp(caster)
    hp_fighter_after = get_hp(ally)

    assert hp_wizard_after == hp_wizard_before, "Wizard takes 0 damage (Shield)"
    assert hp_fighter_after < hp_fighter_before, "Fighter takes damage (no Shield)"

    print(f"  Wizard: {hp_wizard_before} → {hp_wizard_after}, Fighter: {hp_fighter_before} → {hp_fighter_after}")
    print("  PASSED")


def test_shield_mm_consumes_resources():
    """Test 16: Shield vs MM consumes reaction + spell slot."""
    from dnd.spells.evocation import MagicMissile

    print("\n=== Test 16: Shield vs MM Resources ===")
    caster, enemy = setup_shield_vs_mm_scenario()

    reactions_before = caster.action_economy.reactions.normalized_score
    mm = MagicMissile(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=caster.uuid,
        cast_at_level=1
    )
    mm.apply()

    reactions_after = caster.action_economy.reactions.normalized_score
    assert reactions_after == reactions_before - 1
    assert "Shield" in caster.active_conditions

    print(f"  Reactions: {reactions_before} → {reactions_after}")
    print("  PASSED")


def test_shield_disabled_doesnt_block_mm():
    """Test 17: Shield disabled → MM deals damage normally."""
    from dnd.spells.evocation import MagicMissile

    print("\n=== Test 17: Shield Disabled, MM Hits ===")
    caster, enemy = setup_shield_vs_mm_scenario()

    caster.set_handler_enabled("Shield", False)
    hp_before = get_hp(caster)

    mm = MagicMissile(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=caster.uuid,
        cast_at_level=1
    )
    mm.apply()

    hp_after = get_hp(caster)
    assert hp_after < hp_before, "MM should deal damage when Shield disabled"
    assert "Shield" not in caster.active_conditions

    print(f"  HP: {hp_before} → {hp_after}")
    print("  PASSED")


if __name__ == "__main__":
    print("=" * 60)
    print("Shield Spell Tests")
    print("=" * 60)

    print("\n--- Shield Reaction Behavior ---")
    test_shield_fires_on_marginal_hit()
    test_shield_does_not_fire_on_crit()
    test_shield_does_not_fire_on_miss()
    test_shield_does_not_fire_on_crit_miss()
    test_shield_does_not_fire_when_unhelpful()

    print("\n--- Shield Resources ---")
    test_shield_consumes_resources()
    test_shield_disabled_no_effect()
    test_shield_no_reaction_available()
    test_shield_no_spell_slots()

    print("\n--- Shield Buff Persistence ---")
    test_shield_only_fires_once_per_round()
    test_shield_buff_persists_for_ac()
    test_shield_no_stacking()
    test_shield_refires_after_removal()

    print("\n--- Shield vs Magic Missile ---")
    test_shield_blocks_all_mm_darts()
    test_shield_blocks_own_darts_others_take_damage()
    test_shield_mm_consumes_resources()
    test_shield_disabled_doesnt_block_mm()

    print("\n" + "=" * 60)
    print("All 17 Shield spell tests passed!")
    print("=" * 60)
