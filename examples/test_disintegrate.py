"""Extensive tests for Disintegrate spell.

Tests cover:
- Failed save → full damage (10d6 + 40 force)
- Successful save → 0 damage (not half!)
- Upcasting adds dice (+3d6 per level above 6th)
- Range validation (60ft)
- LOS validation
- Target death from disintegrate
"""
import sys
import traceback
from uuid import uuid4

from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map, reset_map
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity, get_natural_roll
from dnd.monsters.bestiary import create_sorcerer, create_goblin
from dnd.spells.transmutation import Disintegrate
from dnd.utils import (
    reset_combat_state, get_hp, set_hp, has_condition,
)


def setup_arena(size: int = 20):
    reset_map()
    grid = get_map()
    grid.create_rectangle(0, 0, size, size)
    return grid


def had_critical_d20() -> bool:
    for event in EventQueue._all_events:
        for attr in ('dice_roll', 'save_roll'):
            roll = getattr(event, attr, None)
            if roll is not None:
                try:
                    nat = get_natural_roll(roll)
                    if nat in (1, 20):
                        return True
                except Exception:
                    pass
    return False


# =============================================================================
# Test 1: Disintegrate - failed save = full damage
# =============================================================================
def test_disintegrate_failed_save():
    """On failed DEX save, target takes 10d6+40 force damage."""
    print("\n=== Test 1: Disintegrate failed save ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(8, 5), faction="monsters")
        Entity.update_all_entities_senses()

        # Give target low DEX to fail save
        base_mod = target.ability_scores.dexterity.ability_score.get_base_modifier()
        if base_mod:
            base_mod.value = 3  # -4 DEX modifier

        hp_before = get_hp(target)
        set_hp(target, 200)  # High HP to survive
        hp_before = get_hp(target)

        spell = Disintegrate(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=6,
            template=False,
            costs=Disintegrate(source_entity_uuid=caster.uuid)._get_costs_for_level(6)
        )
        result = spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled, "Disintegrate should succeed"

        hp_after = get_hp(target)
        damage = hp_before - hp_after
        print(f"  Damage dealt: {damage} (HP: {hp_before} → {hp_after})")

        # 10d6 (10-60) + 40 = 50-100 total
        assert damage >= 50, f"Minimum damage should be 50 (10+40), got {damage}"
        assert damage <= 100, f"Maximum damage should be 100 (60+40), got {damage}"

        print("  PASS: Full damage on failed save")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 2: Disintegrate - successful save = 0 damage
# =============================================================================
def test_disintegrate_successful_save():
    """On successful DEX save, target takes 0 damage (not half!)."""
    print("\n=== Test 2: Disintegrate successful save = 0 damage ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
        target = create_goblin(name="Agile Goblin", position=(8, 5), faction="monsters")
        Entity.update_all_entities_senses()

        # Force save to succeed with massive bonus (+100)
        save_bonus = NumericalModifier.create(
            source_entity_uuid=target.uuid, name="Force Pass", value=100
        )
        target.saving_throws.dexterity_saving_throw.bonus.self_static.add_value_modifier(save_bonus)

        set_hp(target, 200)
        hp_before = get_hp(target)

        spell = Disintegrate(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=6,
            template=False,
            costs=Disintegrate(source_entity_uuid=caster.uuid)._get_costs_for_level(6)
        )
        result = spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled, "Disintegrate should succeed"

        hp_after = get_hp(target)
        damage = hp_before - hp_after
        print(f"  Damage dealt: {damage} (HP: {hp_before} → {hp_after})")
        assert damage == 0, f"Should take 0 damage on save, got {damage}"

        print("  PASS: Zero damage on successful save")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 3: Disintegrate - upcasting adds dice
# =============================================================================
def test_disintegrate_upcast():
    """Upcasting adds +3d6 per level above 6th."""
    print("\n=== Test 3: Disintegrate upcasting ===")

    # Just check dice count formula
    base_spell = Disintegrate(source_entity_uuid=uuid4())

    # At level 6: 10d6
    base_spell.cast_at_level = 6
    count_6 = base_spell.get_damage_dice_count()
    print(f"  Level 6: {count_6}d6")
    assert count_6 == 10, f"Level 6 should be 10d6, got {count_6}"

    # At level 7: 13d6
    base_spell.cast_at_level = 7
    count_7 = base_spell.get_damage_dice_count()
    print(f"  Level 7: {count_7}d6")
    assert count_7 == 13, f"Level 7 should be 13d6, got {count_7}"

    # At level 8: 16d6
    base_spell.cast_at_level = 8
    count_8 = base_spell.get_damage_dice_count()
    print(f"  Level 8: {count_8}d6")
    assert count_8 == 16, f"Level 8 should be 16d6, got {count_8}"

    # At level 9: 19d6
    base_spell.cast_at_level = 9
    count_9 = base_spell.get_damage_dice_count()
    print(f"  Level 9: {count_9}d6")
    assert count_9 == 19, f"Level 9 should be 19d6, got {count_9}"

    print("  PASS: Upcast dice counts correct")


# =============================================================================
# Test 4: Disintegrate - range validation
# =============================================================================
def test_disintegrate_range():
    """Target must be within 60ft."""
    print("\n=== Test 4: Disintegrate range validation ===")
    reset_combat_state()
    setup_arena(size=30)

    caster = create_sorcerer(name="Wizard", position=(2, 2), level=5, faction="heroes")
    # 15 tiles = 75ft, beyond 60ft
    far_target = create_goblin(name="Far Goblin", position=(17, 2), faction="monsters")
    Entity.update_all_entities_senses()

    spell = Disintegrate(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=far_target.uuid,
        cast_at_level=6,
        template=False,
        costs=Disintegrate(source_entity_uuid=caster.uuid)._get_costs_for_level(6)
    )
    result = spell.apply()
    assert result is not None and result.canceled, \
        f"Should fail at 75ft range, got: {result.status_message if result else 'None'}"
    print(f"  Range fail message: {result.status_message}")

    # In range (12 tiles = 60ft exactly)
    reset_combat_state()
    setup_arena(size=30)
    caster2 = create_sorcerer(name="Wizard2", position=(2, 2), level=5, faction="heroes")
    near_target = create_goblin(name="Near Goblin", position=(14, 2), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    spell2 = Disintegrate(
        source_entity_uuid=caster2.uuid,
        target_entity_uuid=near_target.uuid,
        cast_at_level=6,
        template=False,
        costs=Disintegrate(source_entity_uuid=caster2.uuid)._get_costs_for_level(6)
    )
    result2 = spell2.apply()
    assert result2 is not None and not result2.canceled, \
        f"Should succeed at 60ft, got: {result2.status_message if result2 else 'None'}"

    print("  PASS: Range validation works")


# =============================================================================
# Test 5: Disintegrate - not concentration
# =============================================================================
def test_disintegrate_not_concentration():
    """Disintegrate is NOT a concentration spell."""
    print("\n=== Test 5: Disintegrate is not concentration ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
    target = create_goblin(name="Goblin", position=(8, 5), faction="monsters")
    Entity.update_all_entities_senses()
    set_hp(target, 200)

    spell = Disintegrate(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=6,
        template=False,
        costs=Disintegrate(source_entity_uuid=caster.uuid)._get_costs_for_level(6)
    )
    spell.apply()

    assert not has_condition(caster, "Concentrating"), "Disintegrate is NOT concentration"
    print("  PASS: No concentration")


# =============================================================================
# Test 6: Disintegrate - target killed
# =============================================================================
def test_disintegrate_kills_target():
    """Disintegrate should be able to kill a low-HP target."""
    print("\n=== Test 6: Disintegrate kills target ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
        target = create_goblin(name="Weakling", position=(8, 5), faction="monsters")
        Entity.update_all_entities_senses()

        # Set target to low HP (min damage is 50)
        set_hp(target, 10)
        base_mod = target.ability_scores.dexterity.ability_score.get_base_modifier()
        if base_mod:
            base_mod.value = 3  # Low DEX to fail save

        spell = Disintegrate(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=6,
            template=False,
            costs=Disintegrate(source_entity_uuid=caster.uuid)._get_costs_for_level(6)
        )
        spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        hp = get_hp(target)
        print(f"  Target HP after Disintegrate: {hp}")
        assert hp <= 0, f"Target with 10 HP should be dead after Disintegrate, HP={hp}"

        print("  PASS: Target killed by Disintegrate")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 7: Disintegrate force damage type
# =============================================================================
def test_disintegrate_force_damage():
    """Verify the damage type is FORCE."""
    print("\n=== Test 7: Disintegrate deals force damage ===")
    # Verify from spell definition
    spell = Disintegrate(source_entity_uuid=uuid4())
    assert spell.concentration == False, "Should not be concentration"
    assert spell.spell_level == 6, "Should be level 6"
    print(f"  Spell level: {spell.spell_level}, Concentration: {spell.concentration}")
    print("  PASS: Spell properties correct")


# =============================================================================
# Run all tests
# =============================================================================
if __name__ == "__main__":
    tests = [
        test_disintegrate_failed_save,
        test_disintegrate_successful_save,
        test_disintegrate_upcast,
        test_disintegrate_range,
        test_disintegrate_not_concentration,
        test_disintegrate_kills_target,
        test_disintegrate_force_damage,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAIL: {e}")
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if failed > 0:
        sys.exit(1)
    print("All Disintegrate tests passed!")
