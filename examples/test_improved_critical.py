"""
Test Improved Critical and Superior Critical implementations.

Tests:
1. Default threshold (20) - Natural 19 should NOT crit, Natural 20 should crit
2. Improved Critical (+1) - Natural 19 should crit, Natural 18 should NOT crit
3. Superior Critical (+2) - Natural 18 should crit, Natural 17 should NOT crit
4. Advantage handling - Both dice checked against threshold
5. Condition removal - Threshold returns to normal
"""

from uuid import uuid4

# Reset registries before imports to ensure clean state
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue

BaseObject._registry.clear()
EventQueue._events_by_uuid.clear()
EventQueue._events_by_lineage.clear()
EventQueue._events_by_type.clear()
EventQueue._events_by_phase.clear()
EventQueue._events_by_source.clear()
EventQueue._events_by_target.clear()
EventQueue._events_by_timestamp.clear()
EventQueue._all_events.clear()

from dnd.entity import Entity, determine_attack_outcome, get_natural_roll
from dnd.core.values import AdvantageStatus, CriticalStatus, AutoHitStatus
from dnd.core.dice import DiceRoll, RollType, AttackOutcome
from dnd.core.gridmap import reset_map
from dnd.classes.fighter import ImprovedCritical, SuperiorCritical
from dnd.monsters.bestiary import create_goblin

# Reset entity registries
Entity._entity_registry.clear()
Entity._entity_by_position.clear()
reset_map()


def create_mock_dice_roll(
    natural_roll: int,
    bonus: int = 0,
    advantage_status: AdvantageStatus = AdvantageStatus.NONE,
    all_rolls: list = None
) -> DiceRoll:
    """Create a mock DiceRoll for testing."""
    source_uuid = uuid4()

    if all_rolls is None:
        results = [natural_roll]
    else:
        results = all_rolls

    # Calculate total based on used roll
    if advantage_status == AdvantageStatus.ADVANTAGE:
        used_roll = max(results)
    elif advantage_status == AdvantageStatus.DISADVANTAGE:
        used_roll = min(results)
    else:
        used_roll = results[0] if results else natural_roll

    return DiceRoll(
        dice_uuid=uuid4(),
        roll_type=RollType.ATTACK,
        results=results,
        total=used_roll + bonus,
        bonus=bonus,
        advantage_status=advantage_status,
        critical_status=CriticalStatus.NONE,
        auto_hit_status=AutoHitStatus.NONE,
        source_entity_uuid=source_uuid
    )


def test_get_natural_roll():
    """Test the get_natural_roll helper function."""
    print("\n=== Test: get_natural_roll helper ===")

    # Single roll
    roll = create_mock_dice_roll(15)
    assert get_natural_roll(roll) == 15, "Single roll should return the value"
    print("  [PASS] Single roll returns correct value")

    # Advantage - should return max
    roll = create_mock_dice_roll(15, advantage_status=AdvantageStatus.ADVANTAGE, all_rolls=[10, 15])
    assert get_natural_roll(roll) == 15, "Advantage should return max roll"
    print("  [PASS] Advantage returns max roll")

    # Disadvantage - should return min
    roll = create_mock_dice_roll(10, advantage_status=AdvantageStatus.DISADVANTAGE, all_rolls=[10, 15])
    assert get_natural_roll(roll) == 10, "Disadvantage should return min roll"
    print("  [PASS] Disadvantage returns min roll")

    print("  All get_natural_roll tests passed!")


def test_default_threshold():
    """Test default crit threshold of 20."""
    print("\n=== Test: Default Crit Threshold (20) ===")

    # Natural 20 should crit (AC doesn't matter for crit)
    roll_20 = create_mock_dice_roll(20, bonus=5)
    outcome = determine_attack_outcome(roll_20, 15, crit_threshold=20)
    assert outcome == AttackOutcome.CRIT, f"Natural 20 should crit, got {outcome}"
    print("  [PASS] Natural 20 is a crit")

    # Natural 19 should NOT crit (but still hits)
    roll_19 = create_mock_dice_roll(19, bonus=5)
    outcome = determine_attack_outcome(roll_19, 15, crit_threshold=20)
    assert outcome == AttackOutcome.HIT, f"Natural 19 should hit (not crit), got {outcome}"
    print("  [PASS] Natural 19 is a hit (not crit)")

    # Natural 1 is always crit miss
    roll_1 = create_mock_dice_roll(1, bonus=20)
    outcome = determine_attack_outcome(roll_1, 5, crit_threshold=20)
    assert outcome == AttackOutcome.CRIT_MISS, f"Natural 1 should be crit miss, got {outcome}"
    print("  [PASS] Natural 1 is always crit miss")

    print("  All default threshold tests passed!")


def test_improved_critical_threshold():
    """Test Improved Critical (threshold 19)."""
    print("\n=== Test: Improved Critical Threshold (19) ===")

    # Natural 19 should crit
    roll_19 = create_mock_dice_roll(19, bonus=5)
    outcome = determine_attack_outcome(roll_19, 15, crit_threshold=19)
    assert outcome == AttackOutcome.CRIT, f"Natural 19 should crit with threshold 19, got {outcome}"
    print("  [PASS] Natural 19 is a crit with Improved Critical")

    # Natural 20 still crits
    roll_20 = create_mock_dice_roll(20, bonus=5)
    outcome = determine_attack_outcome(roll_20, 15, crit_threshold=19)
    assert outcome == AttackOutcome.CRIT, f"Natural 20 should still crit, got {outcome}"
    print("  [PASS] Natural 20 is still a crit")

    # Natural 18 should NOT crit
    roll_18 = create_mock_dice_roll(18, bonus=5)
    outcome = determine_attack_outcome(roll_18, 15, crit_threshold=19)
    assert outcome == AttackOutcome.HIT, f"Natural 18 should hit (not crit), got {outcome}"
    print("  [PASS] Natural 18 is a hit (not crit)")

    print("  All Improved Critical tests passed!")


def test_superior_critical_threshold():
    """Test Superior Critical (threshold 18)."""
    print("\n=== Test: Superior Critical Threshold (18) ===")

    # Natural 18 should crit
    roll_18 = create_mock_dice_roll(18, bonus=5)
    outcome = determine_attack_outcome(roll_18, 15, crit_threshold=18)
    assert outcome == AttackOutcome.CRIT, f"Natural 18 should crit with threshold 18, got {outcome}"
    print("  [PASS] Natural 18 is a crit with Superior Critical")

    # Natural 19 still crits
    roll_19 = create_mock_dice_roll(19, bonus=5)
    outcome = determine_attack_outcome(roll_19, 15, crit_threshold=18)
    assert outcome == AttackOutcome.CRIT, f"Natural 19 should crit, got {outcome}"
    print("  [PASS] Natural 19 is still a crit")

    # Natural 17 should NOT crit
    roll_17 = create_mock_dice_roll(17, bonus=5)
    outcome = determine_attack_outcome(roll_17, 15, crit_threshold=18)
    assert outcome == AttackOutcome.HIT, f"Natural 17 should hit (not crit), got {outcome}"
    print("  [PASS] Natural 17 is a hit (not crit)")

    print("  All Superior Critical tests passed!")


def test_advantage_with_improved_critical():
    """Test that the correct die is checked with advantage/disadvantage."""
    print("\n=== Test: Advantage with Improved Critical ===")

    # Advantage: rolls [17, 19], uses 19, should crit with threshold 19
    roll_adv = create_mock_dice_roll(19, bonus=5,
                                      advantage_status=AdvantageStatus.ADVANTAGE,
                                      all_rolls=[17, 19])
    outcome = determine_attack_outcome(roll_adv, 15, crit_threshold=19)
    assert outcome == AttackOutcome.CRIT, f"Advantage using 19 should crit, got {outcome}"
    print("  [PASS] Advantage using 19 is a crit")

    # Advantage: rolls [19, 17], uses 19, should crit
    roll_adv2 = create_mock_dice_roll(19, bonus=5,
                                       advantage_status=AdvantageStatus.ADVANTAGE,
                                       all_rolls=[19, 17])
    outcome = determine_attack_outcome(roll_adv2, 15, crit_threshold=19)
    assert outcome == AttackOutcome.CRIT, f"Advantage using 19 should crit, got {outcome}"
    print("  [PASS] Advantage with 19 first is a crit")

    # Disadvantage: rolls [19, 12], uses 12, should NOT crit
    roll_dis = create_mock_dice_roll(12, bonus=5,
                                      advantage_status=AdvantageStatus.DISADVANTAGE,
                                      all_rolls=[19, 12])
    outcome = determine_attack_outcome(roll_dis, 15, crit_threshold=19)
    assert outcome == AttackOutcome.HIT, f"Disadvantage using 12 should hit (not crit), got {outcome}"
    print("  [PASS] Disadvantage using 12 (ignoring 19) is NOT a crit")

    print("  All advantage tests passed!")


def test_condition_application():
    """Test applying Improved Critical and Superior Critical conditions."""
    print("\n=== Test: Condition Application ===")

    # Create a test entity
    fighter = create_goblin(name="Champion Fighter", position=(0, 0))
    Entity.update_all_entities_senses()

    # Check default threshold
    default_threshold = fighter.get_crit_threshold()
    assert default_threshold == 20, f"Default threshold should be 20, got {default_threshold}"
    print(f"  [PASS] Default crit threshold is {default_threshold}")

    # Apply Improved Critical
    improved_crit = ImprovedCritical(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid
    )
    fighter.add_condition(improved_crit)

    improved_threshold = fighter.get_crit_threshold()
    assert improved_threshold == 19, f"Improved Critical threshold should be 19, got {improved_threshold}"
    print(f"  [PASS] After Improved Critical, threshold is {improved_threshold}")

    # Remove Improved Critical
    fighter.remove_condition("Improved Critical")

    removed_threshold = fighter.get_crit_threshold()
    assert removed_threshold == 20, f"After removal, threshold should be 20, got {removed_threshold}"
    print(f"  [PASS] After removal, threshold returns to {removed_threshold}")

    # Apply Superior Critical
    superior_crit = SuperiorCritical(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid
    )
    fighter.add_condition(superior_crit)

    superior_threshold = fighter.get_crit_threshold()
    assert superior_threshold == 18, f"Superior Critical threshold should be 18, got {superior_threshold}"
    print(f"  [PASS] After Superior Critical, threshold is {superior_threshold}")

    print("  All condition application tests passed!")


def test_ranged_vs_melee_thresholds():
    """Test that melee and ranged have separate thresholds."""
    print("\n=== Test: Separate Melee/Ranged Thresholds ===")

    from dnd.blocks.equipment import WeaponSlot

    # Create entity and reset
    fighter = create_goblin(name="Specialized Fighter", position=(2, 2))
    Entity.update_all_entities_senses()

    # Verify both start at 20
    melee_threshold = fighter.get_crit_threshold(WeaponSlot.MELEE_MAIN)
    ranged_threshold = fighter.get_crit_threshold(WeaponSlot.RANGED_MAIN)
    assert melee_threshold == 20, f"Melee threshold should be 20, got {melee_threshold}"
    assert ranged_threshold == 20, f"Ranged threshold should be 20, got {ranged_threshold}"
    print(f"  [PASS] Both thresholds start at 20")

    # Apply Improved Critical (affects both)
    improved = ImprovedCritical(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid
    )
    fighter.add_condition(improved)

    melee_threshold = fighter.get_crit_threshold(WeaponSlot.MELEE_MAIN)
    ranged_threshold = fighter.get_crit_threshold(WeaponSlot.RANGED_MAIN)
    assert melee_threshold == 19, f"Melee threshold should be 19, got {melee_threshold}"
    assert ranged_threshold == 19, f"Ranged threshold should be 19, got {ranged_threshold}"
    print(f"  [PASS] After Improved Critical, both thresholds are 19")

    print("  All melee/ranged threshold tests passed!")


if __name__ == "__main__":
    print("=" * 60)
    print("IMPROVED CRITICAL / SUPERIOR CRITICAL TESTS")
    print("=" * 60)

    test_get_natural_roll()
    test_default_threshold()
    test_improved_critical_threshold()
    test_superior_critical_threshold()
    test_advantage_with_improved_critical()
    test_condition_application()
    test_ranged_vs_melee_thresholds()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
