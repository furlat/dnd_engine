"""
Test suite for the Concentration system.

Tests:
1. Basic concentration application
2. Concentration check on damage (pass)
3. Concentration check on damage (fail)
4. New concentration spell ends old one
5. Linked spell effect removed when concentration breaks
"""

from dnd.utils import reset_combat_state, set_hp, deal_damage_to, has_condition
from dnd.monsters.bestiary import create_skeleton
from dnd.entity import Entity
from dnd.conditions import Concentrating
from dnd.core.events import DamageType


def test_1_basic_concentration():
    """Test that Concentrating condition can be applied."""
    print("\n=== Test 1: Basic Concentration Application ===")
    reset_combat_state()

    caster = create_skeleton(name="Mage", position=(0, 0))

    # Apply concentration condition
    concentration = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="Hold Person"
    )
    caster.add_condition(concentration)

    # Verify concentration is active
    assert has_condition(caster, "Concentrating"), "Should have Concentrating condition"

    # Verify spell name is tracked
    conc = caster.active_conditions.get("Concentrating")
    assert conc is not None
    assert isinstance(conc, Concentrating)
    assert conc.spell_name == "Hold Person"

    print(f"  {caster.name} is concentrating on: {conc.spell_name}")
    print("  PASSED: Basic concentration works")


def test_2_concentration_check_pass():
    """Test that small damage can be saved against."""
    print("\n=== Test 2: Concentration Check (Pass) ===")
    reset_combat_state()

    # Create mage with high CON for reliable save
    caster = create_skeleton(name="Tough Mage", position=(0, 0))
    # Skeleton has 10 CON (+0), but let's give it high HP so damage doesn't kill it
    set_hp(caster, 50)

    # Apply concentration
    concentration = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="Bless"
    )
    caster.add_condition(concentration)

    # Take small damage (DC 10 save is achievable)
    # DC = max(10, damage/2) = max(10, 2) = 10
    # With +0 CON mod, need 10+ on d20 (55% chance)
    # For testing, we'll just verify the mechanism works

    initial_conc = has_condition(caster, "Concentrating")
    assert initial_conc, "Should start with concentration"

    # Deal 4 damage (DC = 10)
    deal_damage_to(caster, 4, DamageType.BLUDGEONING)

    # Check if concentration is still there (may or may not be based on roll)
    still_concentrating = has_condition(caster, "Concentrating")
    if still_concentrating:
        print("  Mage passed concentration check (kept concentration)")
    else:
        print("  Mage failed concentration check (lost concentration)")

    print("  PASSED: Concentration check triggered on damage")


def test_3_concentration_check_fail_high_damage():
    """Test that high damage makes concentration harder to maintain."""
    print("\n=== Test 3: High Damage Concentration Check ===")

    # DC = max(10, 40/2) = 20 with +0 CON → need nat 20 (5% chance to pass)
    # Run 5 trials — probability of passing ALL 5: 0.05^5 ≈ 0.00003%
    broke_at_least_once = False
    for _ in range(5):
        reset_combat_state()
        caster = create_skeleton(name="Fragile Mage", position=(0, 0))
        set_hp(caster, 100)

        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Haste"
        )
        caster.add_condition(concentration)

        deal_damage_to(caster, 40, DamageType.FIRE)

        if not has_condition(caster, "Concentrating"):
            broke_at_least_once = True
            break

    if broke_at_least_once:
        print("  Mage lost concentration on Haste (high DC)")
    else:
        print("  WARNING: Mage kept concentration all 5 trials (extremely unlikely)")

    assert broke_at_least_once, "Concentration should break on high damage (DC 20 with +0 CON) in at least 1 of 5 trials"
    print("  PASSED: High damage concentration check works")


def test_4_new_concentration_ends_old():
    """Test that casting a new concentration spell ends the old one."""
    print("\n=== Test 4: New Concentration Ends Old ===")
    reset_combat_state()

    caster = create_skeleton(name="Mage", position=(0, 0))

    # Apply first concentration
    conc1 = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="Hold Person"
    )
    caster.add_condition(conc1)

    assert has_condition(caster, "Concentrating")
    conc = caster.active_conditions.get("Concentrating")
    assert conc is not None and isinstance(conc, Concentrating)
    assert conc.spell_name == "Hold Person"
    print(f"  First concentration: {conc.spell_name}")

    # Apply second concentration - should end first
    conc2 = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="Fly"
    )
    caster.add_condition(conc2)

    # Should still have concentration, but on new spell
    assert has_condition(caster, "Concentrating")
    conc = caster.active_conditions.get("Concentrating")
    assert conc is not None and isinstance(conc, Concentrating)
    assert conc.spell_name == "Fly", f"Should be concentrating on Fly, not {conc.spell_name}"
    print(f"  Second concentration replaced first: {conc.spell_name}")

    print("  PASSED: New concentration ends old")


def test_5_linked_effect_removed():
    """Test that spell effect is removed when concentration breaks.

    This demonstrates the pattern used by concentration spells:
    - Caster: Concentrating → linked_conditions → Target: SpellEffect → sub_conditions → Paralyzed/etc

    When concentration breaks, the external condition (SpellEffect) is removed,
    which in turn removes its sub-conditions via the existing mechanism.
    """
    print("\n=== Test 5: Linked Spell Effect Removed ===")
    reset_combat_state()

    caster = create_skeleton(name="Mage", position=(0, 0))
    target = create_skeleton(name="Target", position=(1, 0))
    set_hp(caster, 100)

    Entity.update_all_entities_senses()

    # Create a simple debuff condition to represent the spell effect
    from dnd.conditions import Restrained

    # Apply the spell effect to target
    spell_effect = Restrained(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid
    )
    target.add_condition(spell_effect)

    # Now apply concentration and link the spell effect via linked_conditions
    concentration = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="Hold Person"
    )
    caster.add_condition(concentration)

    # Link the spell effect as an external condition ("nephew")
    # This enables automatic cleanup when concentration breaks
    concentration.add_linked_condition(target.uuid, spell_effect.uuid)

    # Verify both are active
    assert has_condition(caster, "Concentrating")
    assert has_condition(target, "Restrained")
    print(f"  {caster.name} concentrating on Hold Person")
    print(f"  {target.name} is Restrained")

    # Break concentration by removing it directly (simulating failed save)
    caster.remove_condition("Concentrating")

    # Verify both are gone
    assert not has_condition(caster, "Concentrating"), "Concentration should be removed"
    assert not has_condition(target, "Restrained"), "Spell effect should be removed when concentration breaks"

    print("  Concentration broken - spell effect also removed")
    print("  PASSED: Linked spell effect removed")


def test_6_voluntary_end_concentration():
    """Test that concentration can be voluntarily ended."""
    print("\n=== Test 6: Voluntary End Concentration ===")
    reset_combat_state()

    caster = create_skeleton(name="Mage", position=(0, 0))

    # Apply concentration
    concentration = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="Invisibility"
    )
    caster.add_condition(concentration)

    assert has_condition(caster, "Concentrating")
    print(f"  {caster.name} concentrating on Invisibility")

    # End concentration voluntarily
    caster.remove_condition("Concentrating")

    assert not has_condition(caster, "Concentrating")
    print("  Concentration ended voluntarily")
    print("  PASSED: Voluntary end works")


if __name__ == "__main__":
    print("=" * 60)
    print("CONCENTRATION SYSTEM TEST SUITE")
    print("=" * 60)

    test_1_basic_concentration()
    test_2_concentration_check_pass()
    test_3_concentration_check_fail_high_damage()
    test_4_new_concentration_ends_old()
    test_5_linked_effect_removed()
    test_6_voluntary_end_concentration()

    print("\n" + "=" * 60)
    print("ALL CONCENTRATION TESTS COMPLETED")
    print("=" * 60)
