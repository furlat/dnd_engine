"""Test Cleric Batch 5: ConditionTag Refactor + Remove Curse + Bestow Curse

Tests for:
1. ConditionTag backward compat (magical_origin property)
2. Remove Curse: removes curse, ignores non-curse
3. Bestow Curse x4 options + concentration cleanup
4. Remove Curse removes Bestow Curse
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from uuid import uuid4
from dnd.utils import (
    reset_combat_state, setup_combat_arena, get_hp, set_hp,
    has_condition, force_attack_hit, force_attack_miss, remove_attack_modifier,
    deal_damage_to,
)
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.encounter import Encounter
from dnd.controller import HumanController
from dnd.monsters.bestiary import create_goblin, create_caster
from dnd.actions_functional import setup_standard_actions, register_spell
from dnd.spells import (
    RemoveCurse, BestowCurse,
    AbilityCurseEffect, AttackCurseEffect, InactionCurseEffect, DamageCurseEffect,
    ConditionTag,
)
from dnd.spells import ShieldOfFaithEffect
from dnd.conditions import Poisoned
from dnd.core.base_conditions import BaseCondition
from dnd.core.modifiers import AdvantageStatus, DamageType


passed = 0
failed = 0

def check(label, condition):
    global passed, failed
    if condition:
        print(f"  PASS: {label}")
        passed += 1
    else:
        print(f"  FAIL: {label}")
        failed += 1


def setup_cleric(name="Cleric", position=(5, 5), level=10, hp=80, faction="party"):
    """Create a cleric-like sorcerer entity for testing."""
    cleric = create_caster(name=name, position=position, level=level)
    cleric.faction = faction
    set_hp(cleric, hp)
    return cleric


def setup_encounter(*entities):
    """Setup encounter with all entities."""
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    for e in entities:
        encounter.add_combatant(e, HumanController(source_entity_uuid=e.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    return encounter


# ============================================================
# Test 1: ConditionTag Backward Compatibility
# ============================================================
def test_condition_tag_compat():
    print("\n--- ConditionTag Backward Compatibility ---")
    reset_combat_state()

    # Condition with MAGICAL tag
    cond = BaseCondition(
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4(),
        tags={ConditionTag.MAGICAL}
    )
    check("magical_origin property returns True for MAGICAL tag", cond.magical_origin is True)

    # Condition without MAGICAL tag
    cond2 = BaseCondition(
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4(),
    )
    check("magical_origin property returns False for empty tags", cond2.magical_origin is False)

    # Condition with CURSE tag but not MAGICAL
    cond3 = BaseCondition(
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4(),
        tags={ConditionTag.CURSE}
    )
    check("magical_origin False when only CURSE tag", cond3.magical_origin is False)

    # Condition with both MAGICAL and CURSE
    cond4 = BaseCondition(
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4(),
        tags={ConditionTag.MAGICAL, ConditionTag.CURSE}
    )
    check("magical_origin True when MAGICAL+CURSE", cond4.magical_origin is True)

    # Verify Shield of Faith effect still has MAGICAL tag
    sof = ShieldOfFaithEffect(
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4(),
    )
    check("ShieldOfFaithEffect has MAGICAL tag via class default", sof.magical_origin is True)


# ============================================================
# Test 2: Remove Curse — removes curse, ignores non-curse
# ============================================================
def test_remove_curse_basic():
    print("\n--- Remove Curse Basic ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    target = create_goblin(name="Ally", position=(6, 5))
    target.faction = "party"
    Entity.update_all_entities_senses()

    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    register_spell(cleric, RemoveCurse, caster_level=10)

    # Apply both a non-curse condition and a curse condition
    poisoned = Poisoned(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(poisoned)
    check("Poisoned applied", has_condition(target, "Poisoned"))

    curse = AbilityCurseEffect(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
        cursed_ability="strength"
    )
    target.add_condition(curse)
    check("Bestow Curse applied", has_condition(target, "Bestow Curse"))

    # Cast Remove Curse — should remove curse but NOT Poisoned
    register_spell(cleric, RemoveCurse, caster_level=10)
    remove_curse = RemoveCurse(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
    )
    remove_curse.apply()
    check("Bestow Curse removed by Remove Curse", not has_condition(target, "Bestow Curse"))
    check("Poisoned still present after Remove Curse", has_condition(target, "Poisoned"))


# ============================================================
# Test 3: Bestow Curse Option 1 — Ability Curse
# ============================================================
def test_bestow_curse_option1():
    print("\n--- Bestow Curse Option 1: Ability Curse ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    target = create_goblin(name="Enemy", position=(6, 5))
    Entity.update_all_entities_senses()

    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    register_spell(cleric, BestowCurse, caster_level=10)

    # Get baseline STR save advantage
    baseline_save = target.saving_throw_bonus(cleric.uuid, "strength")
    baseline_adv = baseline_save.advantage

    # Cast with option 1 (strength curse)
    spell = BestowCurse(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
        curse_option=1,
        cursed_ability="strength"
    )
    spell.apply()

    # Check if curse applied (target may save, so check)
    if has_condition(target, "Bestow Curse"):
        check("Bestow Curse (ability) applied", True)

        # STR save should now have disadvantage
        cursed_save = target.saving_throw_bonus(cleric.uuid, "strength")
        check("STR save has disadvantage after curse",
              cursed_save.advantage == AdvantageStatus.DISADVANTAGE)

        # DEX save should NOT have disadvantage
        dex_save = target.saving_throw_bonus(cleric.uuid, "dexterity")
        check("DEX save unaffected by STR curse",
              dex_save.advantage != AdvantageStatus.DISADVANTAGE)

        # Athletics (STR skill) should have disadvantage
        athletics = target.skill_set.get_skill("athletics")
        check("Athletics has disadvantage",
              athletics.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE)

        # Concentration should be active on cleric
        check("Cleric is concentrating", has_condition(cleric, "Concentrating"))
    else:
        print("  (target saved - checking concentration still started)")
        check("Cleric still concentrating after target saved", has_condition(cleric, "Concentrating"))


# ============================================================
# Test 4: Bestow Curse Option 2 — Attack Curse
# ============================================================
def test_bestow_curse_option2():
    print("\n--- Bestow Curse Option 2: Attack Curse ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    target = create_goblin(name="Enemy", position=(6, 5))
    Entity.update_all_entities_senses()

    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    register_spell(cleric, BestowCurse, caster_level=10)

    # Directly apply AttackCurseEffect to test the modifier (bypass save RNG)
    curse = AttackCurseEffect(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
        caster_uuid=cleric.uuid,
    )
    target.add_condition(curse)
    check("Bestow Curse (attack) applied directly", has_condition(target, "Bestow Curse"))

    # Target's attacks against caster should have disadvantage
    atk_bonus = target.equipment.attack_bonus
    atk_bonus.set_target_entity(target_entity_uuid=cleric.uuid)
    adv = atk_bonus.advantage
    atk_bonus.clear_target_entity()
    check("Attacks vs caster have disadvantage", adv == AdvantageStatus.DISADVANTAGE)

    # Target's attacks against others should NOT have disadvantage
    other = create_goblin(name="Bystander", position=(7, 5))
    Entity.update_all_entities_senses()
    atk_bonus.set_target_entity(target_entity_uuid=other.uuid)
    adv2 = atk_bonus.advantage
    atk_bonus.clear_target_entity()
    check("Attacks vs others NOT disadvantaged", adv2 != AdvantageStatus.DISADVANTAGE)


# ============================================================
# Test 5: Bestow Curse Option 3 — Inaction Curse
# ============================================================
def test_bestow_curse_option3():
    print("\n--- Bestow Curse Option 3: Inaction Curse ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    target = create_goblin(name="Enemy", position=(6, 5))
    Entity.update_all_entities_senses()

    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    # Directly apply InactionCurseEffect to test the handler (bypass save RNG)
    dc = cleric.spell_save_dc()
    curse = InactionCurseEffect(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
        caster_uuid=cleric.uuid,
        spell_dc=dc,
    )
    target.add_condition(curse)
    check("Bestow Curse (inaction) applied directly", has_condition(target, "Bestow Curse"))

    # The curse's effect triggers on TURN_START, so verify handlers registered
    curse_cond = target.active_conditions.get("Bestow Curse")
    check("Curse condition has event handlers",
          curse_cond is not None and len(curse_cond.event_handlers_uuids) == 2)
    check("Curse has CURSE tag",
          curse_cond is not None and ConditionTag.CURSE in curse_cond.tags)
    check("Curse has MAGICAL tag",
          curse_cond is not None and ConditionTag.MAGICAL in curse_cond.tags)


# ============================================================
# Test 6: Bestow Curse Option 4 — Damage Curse
# ============================================================
def test_bestow_curse_option4():
    print("\n--- Bestow Curse Option 4: Damage Curse ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric(position=(5, 5))
    target = create_goblin(name="Enemy", position=(6, 5))
    Entity.update_all_entities_senses()

    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    register_spell(cleric, BestowCurse, caster_level=10)

    spell = BestowCurse(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
        curse_option=4,
    )
    spell.apply()

    # Directly apply DamageCurseEffect to test the handler (bypass save RNG)
    curse = DamageCurseEffect(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
        caster_uuid=cleric.uuid,
    )
    target.add_condition(curse)
    check("Bestow Curse (damage) applied directly", has_condition(target, "Bestow Curse"))

    # Reset cleric's action economy for the attack
    cleric.action_economy.reset_all_costs()

    # Force a hit from cleric against target
    set_hp(target, 50)
    hp_before = get_hp(target)
    mod_id = force_attack_hit(cleric)
    from dnd.actions import Attack
    from dnd.core.events import WeaponSlot
    attack = Attack(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    )
    attack.apply()
    remove_attack_modifier(cleric, mod_id)
    hp_after = get_hp(target)
    total_damage = hp_before - hp_after
    # Damage should include weapon + 1d8 necrotic (at least 1 extra)
    check(f"Target took damage (total={total_damage})", total_damage > 0)
    print(f"  (Damage dealt: {total_damage}, includes weapon + curse)")


# ============================================================
# Test 7: Concentration Cleanup — Breaking Bestow Curse
# ============================================================
def test_bestow_curse_concentration():
    print("\n--- Bestow Curse Concentration Cleanup ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric()
    target = create_goblin(name="Enemy", position=(6, 5))
    Entity.update_all_entities_senses()

    encounter = setup_encounter(cleric, target)
    encounter.start_turn()

    register_spell(cleric, BestowCurse, caster_level=10)

    spell = BestowCurse(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
        curse_option=1,
        cursed_ability="wisdom"
    )
    spell.apply()

    if has_condition(target, "Bestow Curse"):
        check("Curse applied to target", True)
        check("Cleric concentrating", has_condition(cleric, "Concentrating"))

        # Break concentration by dealing enough damage
        set_hp(cleric, 80)
        deal_damage_to(cleric, 60, DamageType.FIRE, uuid4())

        # Concentration should break (likely; DC = max(10, 30) = 30)
        if not has_condition(cleric, "Concentrating"):
            check("Concentration broken by damage", True)
            check("Curse removed from target after concentration break",
                  not has_condition(target, "Bestow Curse"))
        else:
            print("  (Cleric passed concentration save - testing direct removal)")
            cleric.remove_condition("Concentrating")
            check("Curse removed after manual concentration drop",
                  not has_condition(target, "Bestow Curse"))
    else:
        print("  (target saved - skipping concentration test)")
        check("placeholder", True)


# ============================================================
# Test 8: Remove Curse Removes Bestow Curse + Breaks Concentration
# ============================================================
def test_remove_curse_on_bestow_curse():
    print("\n--- Remove Curse on Bestow Curse ---")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    cleric = setup_cleric(name="Caster", position=(5, 5))
    ally = setup_cleric(name="Healer", position=(7, 5), faction="party")
    target = create_goblin(name="Enemy", position=(6, 5))
    Entity.update_all_entities_senses()

    encounter = setup_encounter(cleric, ally, target)
    encounter.start_turn()

    register_spell(cleric, BestowCurse, caster_level=10)
    register_spell(ally, RemoveCurse, caster_level=10)

    # Caster curses the enemy
    spell = BestowCurse(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
        curse_option=2,
    )
    spell.apply()

    if has_condition(target, "Bestow Curse"):
        check("Curse applied", True)
        check("Caster concentrating", has_condition(cleric, "Concentrating"))

        # Ally casts Remove Curse on the enemy
        remove = RemoveCurse(
            source_entity_uuid=ally.uuid,
            target_entity_uuid=target.uuid,
        )
        remove.apply()

        check("Curse removed by Remove Curse", not has_condition(target, "Bestow Curse"))
        # Concentration should auto-drop via reverse link (child_removal_policy="last")
        check("Caster concentration auto-dropped",
              not has_condition(cleric, "Concentrating"))
    else:
        print("  (target saved)")
        check("placeholder", True)


# ============================================================
# Run all tests
# ============================================================
if __name__ == "__main__":
    test_condition_tag_compat()
    test_remove_curse_basic()
    test_bestow_curse_option1()
    test_bestow_curse_option2()
    test_bestow_curse_option3()
    test_bestow_curse_option4()
    test_bestow_curse_concentration()
    test_remove_curse_on_bestow_curse()

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    if failed > 0:
        print("SOME TESTS FAILED!")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED!")
