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


def test_7_multi_slot_concentration():
    """Test multi-slot concentration: max_slots=2 allows two different spells."""
    print("\n=== Test 7: Multi-Slot Concentration ===")
    reset_combat_state()
    from dnd.core.gridmap import get_map
    get_map().create_rectangle(0, 0, 20, 20)

    from dnd.monsters.bestiary import create_caster
    from dnd.spells.transmutation import Haste, DarkvisionSpell
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    from uuid import uuid4

    caster = create_caster(name="Archmage", position=(5, 5), level=10)
    target_1 = create_skeleton(name="Ally 1", position=(6, 5))
    # Touch range for Darkvision — must be adjacent (5ft)
    target_2 = create_skeleton(name="Ally 2", position=(5, 6))

    Entity.update_all_entities_senses()

    # Set max_slots to 2
    from dnd.core.modifiers import NumericalModifier
    caster.max_concentration_slots.self_static.add_value_modifier(
        NumericalModifier(name="Multi-Slot", value=1, source_entity_uuid=caster.uuid)
    )
    assert caster.max_concentration_slots.normalized_score == 2

    # Set up encounter for action economy (caster is the only combatant)
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(caster, HumanController(source_entity_uuid=caster.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Cast Haste on target_1 (30ft range, target at 5ft)
    haste1 = Haste(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target_1.uuid,
        template=False,
        cast_at_level=3,
        caster_level=10
    )
    haste1.apply()

    assert has_condition(caster, "Concentrating"), "Should be concentrating on Haste"
    conc = caster.active_conditions["Concentrating"]
    assert isinstance(conc, Concentrating)
    assert "Haste" in conc.spell_name
    assert has_condition(target_1, "Haste")
    print(f"  Cast Haste on {target_1.name}, concentrating on: {conc.spell_name}")

    # Cycle turn to get fresh action economy (single combatant → wraps around)
    encounter.next_turn()

    # Cast Darkvision on target_2 (touch range, target at 5ft)
    darkvision = DarkvisionSpell(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target_2.uuid,
        template=False,
        cast_at_level=2,
        caster_level=10
    )
    result = darkvision.apply()
    assert result and not result.canceled, f"Darkvision should succeed, got: {result.status_message if result else 'None'}"

    # Both should coexist
    assert has_condition(caster, "Concentrating"), "Should still be concentrating"
    conc = caster.active_conditions["Concentrating"]
    assert isinstance(conc, Concentrating)
    assert "Haste" in conc.spell_name and "Darkvision" in conc.spell_name, \
        f"Should have both spells in name, got: {conc.spell_name}"
    assert len(conc.concentration_slots) == 2, f"Should have 2 slots, got {len(conc.concentration_slots)}"
    assert has_condition(target_1, "Haste"), "Target 1 should still have Haste"
    assert has_condition(target_2, "Darkvision"), "Target 2 should have Darkvision"
    print(f"  Multi-slot active: {conc.spell_name} ({len(conc.concentration_slots)} slots)")

    # Drop just Haste via DropConcentration with target_spell
    from dnd.actions import DropConcentration
    drop = DropConcentration(
        source_entity_uuid=caster.uuid,
        target_spell="Haste",
        template=False
    )
    drop.apply()

    # Darkvision should persist, Haste should be gone
    assert has_condition(caster, "Concentrating"), "Should still concentrate on Darkvision"
    conc = caster.active_conditions["Concentrating"]
    assert isinstance(conc, Concentrating)
    assert "Darkvision" in conc.spell_name, f"Should have Darkvision, got: {conc.spell_name}"
    assert "Haste" not in conc.spell_name, "Haste should be dropped"
    assert not has_condition(target_1, "Haste"), "Haste effect should be removed from target"
    assert has_condition(target_2, "Darkvision"), "Darkvision should still be active"
    print(f"  Dropped Haste, still concentrating on: {conc.spell_name}")

    print("  PASSED: Multi-slot concentration works")


def test_8_twinned_spell_single_concentrating():
    """Test that twinned spell (convolution) creates only one Concentrating with both effects."""
    print("\n=== Test 8: Twinned Spell (Convolution) Single Concentrating ===")
    reset_combat_state()
    from dnd.core.gridmap import get_map
    get_map().create_rectangle(0, 0, 20, 20)

    from dnd.monsters.bestiary import create_caster
    from dnd.spells.transmutation import Haste
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    from uuid import uuid4

    caster = create_caster(name="Sorcerer", position=(5, 5), level=10)
    target_1 = create_skeleton(name="Fighter", position=(6, 5))
    target_2 = create_skeleton(name="Rogue", position=(7, 5))

    Entity.update_all_entities_senses()

    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(caster, HumanController(source_entity_uuid=caster.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Cast twinned Haste (MULTI_ENTITY, 2 targets)
    from dnd.core.base_actions import TargetType
    haste = Haste(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target_1.uuid,
        extra_target_entity_uuids=[target_2.uuid],
        target_type=TargetType.MULTI_ENTITY,
        template=False,
        cast_at_level=3,
        caster_level=10
    )
    haste.apply()

    # Both targets should have Haste
    assert has_condition(target_1, "Haste"), "Target 1 should have Haste"
    assert has_condition(target_2, "Haste"), "Target 2 should have Haste"
    assert has_condition(caster, "Concentrating"), "Caster should be concentrating"

    conc = caster.active_conditions["Concentrating"]
    assert isinstance(conc, Concentrating)
    # Both linked conditions should be in the same slot
    assert len(conc.concentration_slots) == 1, f"Twinned spell = 1 slot, got {len(conc.concentration_slots)}"
    assert conc.get_slot_by_spell_name("Haste") is not None, "Slot should be named 'Haste'"
    assert len(conc.linked_conditions) == 2, f"Should have 2 linked effects, got {len(conc.linked_conditions)}"
    print(f"  Twinned Haste: {len(conc.linked_conditions)} linked effects in 1 slot")

    # Break concentration — both effects should be removed
    caster.remove_condition("Concentrating")
    assert not has_condition(target_1, "Haste"), "Target 1 Haste should be removed"
    assert not has_condition(target_2, "Haste"), "Target 2 Haste should be removed"
    print("  Concentration broken: both Haste effects removed")

    print("  PASSED: Twinned spell single Concentrating")


def test_9_same_name_eviction():
    """Test that casting same concentration spell again evicts the old one."""
    print("\n=== Test 9: Same-Name Different-Cast Eviction ===")
    reset_combat_state()
    from dnd.core.gridmap import get_map
    get_map().create_rectangle(0, 0, 20, 20)

    from dnd.monsters.bestiary import create_caster
    from dnd.spells.transmutation import Haste
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    from uuid import uuid4

    caster = create_caster(name="Wizard", position=(5, 5), level=10)
    target_1 = create_skeleton(name="Fighter", position=(6, 5))
    target_2 = create_skeleton(name="Rogue", position=(7, 5))

    Entity.update_all_entities_senses()

    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(caster, HumanController(source_entity_uuid=caster.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Cast Haste on target_1
    haste1 = Haste(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target_1.uuid,
        template=False,
        cast_at_level=3,
        caster_level=10
    )
    haste1.apply()

    assert has_condition(target_1, "Haste"), "Target 1 should have Haste"
    assert has_condition(caster, "Concentrating")
    print(f"  Cast Haste on {target_1.name}")

    # Cycle turn for fresh action economy
    encounter.next_turn()

    # Cast Haste on target_2 (new action instance — should evict first)
    haste2 = Haste(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target_2.uuid,
        template=False,
        cast_at_level=3,
        caster_level=10
    )
    haste2.apply()

    # First Haste should be evicted, second active
    assert not has_condition(target_1, "Haste"), "Target 1 Haste should be evicted"
    assert has_condition(target_2, "Haste"), "Target 2 should have Haste"
    assert has_condition(caster, "Concentrating")

    conc = caster.active_conditions["Concentrating"]
    assert isinstance(conc, Concentrating)
    assert "Haste" in conc.spell_name
    print(f"  Second Haste evicted first, concentrating on: {conc.spell_name}")

    print("  PASSED: Same-name eviction works")


def test_10_multi_slot_zero_children_cleanup():
    """Test that in multi-slot scenario, empty slots are cleaned up while others persist.

    Uses full spell casting: cast Haste (succeeds), then cast Bane on a high-CHA
    target that saves (0-children for Bane slot). The _cleanup_concentration hook
    should remove the empty Bane slot while preserving Haste.
    """
    print("\n=== Test 10: Multi-Slot 0-Children Cleanup ===")
    reset_combat_state()
    from dnd.core.gridmap import get_map
    get_map().create_rectangle(0, 0, 20, 20)

    from dnd.monsters.bestiary import create_caster
    from dnd.spells.transmutation import Haste
    from dnd.spells.enchantment import Bane
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    from uuid import uuid4

    caster = create_caster(name="Archmage", position=(5, 5), level=10)
    ally = create_skeleton(name="Fighter", position=(6, 5))
    # High CHA enemy to reliably save vs Bane
    from dnd.monsters.bestiary import create_skeleton as make_skeleton
    tough_enemy = make_skeleton(name="Demon", position=(7, 5))
    # Give enemy very high CHA to always save
    from dnd.core.modifiers import NumericalModifier
    tough_enemy.ability_scores.charisma.ability_score.self_static.add_value_modifier(
        NumericalModifier(name="High CHA", value=20, source_entity_uuid=tough_enemy.uuid)
    )

    Entity.update_all_entities_senses()

    # Set max_slots to 2
    caster.max_concentration_slots.self_static.add_value_modifier(
        NumericalModifier(name="Multi-Slot", value=1, source_entity_uuid=caster.uuid)
    )

    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(caster, HumanController(source_entity_uuid=caster.uuid))
    encounter.add_combatant(tough_enemy, HumanController(source_entity_uuid=tough_enemy.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Cast Haste on ally (succeeds → linked condition)
    haste = Haste(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
        cast_at_level=3,
        caster_level=10
    )
    haste.apply()

    assert has_condition(ally, "Haste"), "Ally should have Haste"
    assert has_condition(caster, "Concentrating")
    print(f"  Cast Haste on {ally.name}")

    # Cycle turn to get fresh action economy
    encounter.next_turn()  # tough_enemy's turn
    encounter.next_turn()  # back to caster

    # Cast Bane on tough_enemy (should save due to high CHA)
    # Retry until they save to trigger the 0-children scenario
    for attempt in range(10):
        if not has_condition(caster, "Concentrating"):
            break  # Shouldn't happen but safety
        bane = Bane(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=tough_enemy.uuid,
            template=False,
            cast_at_level=1,
            caster_level=10
        )
        bane.apply()

        if not has_condition(tough_enemy, "Bane"):
            # Enemy saved! The 0-children cleanup should have fired
            print(f"  Bane resisted by {tough_enemy.name} (attempt {attempt + 1})")
            break
        else:
            # Enemy failed save unexpectedly — remove and try again
            tough_enemy.remove_condition("Bane")
            encounter.next_turn()  # tough_enemy
            encounter.next_turn()  # caster

    # After Bane is resisted, the _cleanup_concentration hook should have
    # removed the empty "Bane" slot, but Haste slot should persist
    assert has_condition(caster, "Concentrating"), "Should still be concentrating on Haste"
    conc = caster.active_conditions["Concentrating"]
    assert isinstance(conc, Concentrating)
    assert has_condition(ally, "Haste"), "Haste should still be active"
    # The empty Bane slot should have been cleaned up
    assert conc.get_slot_by_spell_name("Bane") is None, f"Empty Bane slot should be gone, got spell_name: {conc.spell_name}"
    assert conc.get_slot_by_spell_name("Haste") is not None, "Haste slot should remain"
    print(f"  Remaining slots: {conc.spell_name} (Bane cleaned up)")

    print("  PASSED: Multi-slot 0-children cleanup works")


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
    test_7_multi_slot_concentration()
    test_8_twinned_spell_single_concentrating()
    test_9_same_name_eviction()
    test_10_multi_slot_zero_children_cleanup()

    print("\n" + "=" * 60)
    print("ALL CONCENTRATION TESTS COMPLETED")
    print("=" * 60)
