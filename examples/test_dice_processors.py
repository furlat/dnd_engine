"""
Test Dice Roll Processor Functions

Tests all dice manipulation patterns for damage roll modification.
"""

import sys
sys.path.insert(0, '.')

from uuid import uuid4
from dnd.core.dice import DiceRoll, RollType
from dnd.core.values import AdvantageStatus, CriticalStatus, AutoHitStatus
# Core utility stays in fighter.py
from dnd.classes.fighter import create_modified_dice_roll

# Test/reference utilities moved to dice_processor_utils.py
from dnd.classes.dice_processor_utils import (
    maximize_all,
    minimize_all,
    set_all_to,
    substitute_value,
    floor_results,
    ceiling_results,
    reroll_below_and_substitute,
    reroll_below_keep_best,
    reroll_ones_once,
)


def create_test_roll(results: list, bonus: int = 2) -> DiceRoll:
    """Create a test DiceRoll with given results."""
    return DiceRoll(
        dice_uuid=uuid4(),
        roll_type=RollType.DAMAGE,
        results=results,
        total=sum(results) + bonus,
        bonus=bonus,
        advantage_status=AdvantageStatus.NONE,
        critical_status=CriticalStatus.NONE,
        auto_hit_status=AutoHitStatus.NONE,
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4()
    )


def test_create_modified_dice_roll():
    """Test the base modification function."""
    print("TEST: create_modified_dice_roll")

    original = create_test_roll([1, 2, 5], bonus=2)
    assert original.results == [1, 2, 5]
    assert original.total == 10  # 1+2+5+2

    modified = create_modified_dice_roll(original, [4, 6, 5])
    assert modified.results == [4, 6, 5]
    assert modified.total == 17  # 4+6+5+2
    assert modified.bonus == original.bonus
    assert modified.dice_uuid == original.dice_uuid

    print(f"  Original: {original.results} + {original.bonus} = {original.total}")
    print(f"  Modified: {modified.results} + {modified.bonus} = {modified.total}")
    print("  PASSED")


def test_maximize_all():
    """Test maximize_all - all dice show maximum."""
    print("\nTEST: maximize_all")

    roll = create_test_roll([1, 2, 3], bonus=0)
    maximized = maximize_all(roll, dice_size=6)

    assert maximized.results == [6, 6, 6]
    assert maximized.total == 18

    print(f"  [1, 2, 3] -> {maximized.results} = {maximized.total}")
    print("  PASSED")


def test_minimize_all():
    """Test minimize_all - all dice show 1."""
    print("\nTEST: minimize_all")

    roll = create_test_roll([4, 5, 6], bonus=0)
    minimized = minimize_all(roll)

    assert minimized.results == [1, 1, 1]
    assert minimized.total == 3

    print(f"  [4, 5, 6] -> {minimized.results} = {minimized.total}")
    print("  PASSED")


def test_set_all_to():
    """Test set_all_to - all dice show specific value."""
    print("\nTEST: set_all_to")

    roll = create_test_roll([1, 6, 3], bonus=0)
    set_to_4 = set_all_to(roll, value=4)

    assert set_to_4.results == [4, 4, 4]
    assert set_to_4.total == 12

    print(f"  [1, 6, 3] -> {set_to_4.results} = {set_to_4.total}")
    print("  PASSED")


def test_substitute_value():
    """Test substitute_value - replace specific values."""
    print("\nTEST: substitute_value")

    roll = create_test_roll([1, 3, 1, 5], bonus=0)
    substituted = substitute_value(roll, from_val=1, to_val=2)

    assert substituted.results == [2, 3, 2, 5]
    assert substituted.total == 12

    print(f"  [1, 3, 1, 5] with 1->2: {substituted.results} = {substituted.total}")
    print("  PASSED")


def test_floor_results():
    """Test floor_results - no result below minimum (Elemental Adept style)."""
    print("\nTEST: floor_results")

    roll = create_test_roll([1, 2, 1, 6], bonus=0)
    floored = floor_results(roll, minimum=2)

    assert floored.results == [2, 2, 2, 6]
    assert floored.total == 12

    print(f"  [1, 2, 1, 6] floor(2): {floored.results} = {floored.total}")
    print("  PASSED")


def test_ceiling_results():
    """Test ceiling_results - no result above maximum."""
    print("\nTEST: ceiling_results")

    roll = create_test_roll([5, 6, 4, 6], bonus=0)
    ceilinged = ceiling_results(roll, maximum=4)

    assert ceilinged.results == [4, 4, 4, 4]
    assert ceilinged.total == 16

    print(f"  [5, 6, 4, 6] ceiling(4): {ceilinged.results} = {ceilinged.total}")
    print("  PASSED")


def test_reroll_below_and_substitute():
    """Test reroll_below_and_substitute - GWF style, must use new roll."""
    print("\nTEST: reroll_below_and_substitute (stochastic)")

    # Run multiple times to verify behavior
    successes = 0
    for _ in range(100):
        roll = create_test_roll([1, 2, 5], bonus=0)
        rerolled = reroll_below_and_substitute(roll, threshold=2, dice_size=6)

        # Third die (5) should never change
        if rerolled.results[2] == 5:
            successes += 1

        # All results should be 1-6
        for r in rerolled.results:
            assert 1 <= r <= 6, f"Invalid result: {r}"

    assert successes == 100, "Third die was modified when it shouldn't be"

    # Show one example
    roll = create_test_roll([1, 2, 5], bonus=0)
    rerolled = reroll_below_and_substitute(roll, threshold=2, dice_size=6)
    print(f"  [1, 2, 5] reroll <=2: {rerolled.results} (5 unchanged)")
    print("  PASSED (100 iterations verified)")


def test_reroll_below_keep_best():
    """Test reroll_below_keep_best - Halfling Lucky style."""
    print("\nTEST: reroll_below_keep_best (stochastic)")

    # With keep-best, result should never be worse
    improvements = 0
    same = 0

    for _ in range(100):
        roll = create_test_roll([1, 1, 1], bonus=0)  # All 1s
        original_total = sum(roll.results)

        rerolled = reroll_below_keep_best(roll, threshold=1, dice_size=6)
        new_total = sum(rerolled.results)

        # Should never be worse (kept best)
        assert new_total >= original_total, f"Got worse: {original_total} -> {new_total}"

        if new_total > original_total:
            improvements += 1
        else:
            same += 1

    print(f"  Starting with [1, 1, 1], after 100 rerolls:")
    print(f"    Improved: {improvements}")
    print(f"    Same: {same}")
    print(f"  (Never got worse - keep best working correctly)")
    print("  PASSED")


def test_reroll_ones_once():
    """Test reroll_ones_once - only reroll 1s."""
    print("\nTEST: reroll_ones_once")

    for _ in range(50):
        roll = create_test_roll([1, 2, 3], bonus=0)
        rerolled = reroll_ones_once(roll, dice_size=6)

        # 2 and 3 should never change
        assert rerolled.results[1] == 2, f"2 was changed to {rerolled.results[1]}"
        assert rerolled.results[2] == 3, f"3 was changed to {rerolled.results[2]}"

    # Show one example
    roll = create_test_roll([1, 2, 3], bonus=0)
    rerolled = reroll_ones_once(roll, dice_size=6)
    print(f"  [1, 2, 3] reroll 1s: {rerolled.results} (2 and 3 unchanged)")
    print("  PASSED (50 iterations verified)")


def test_chained_processors():
    """Test chaining multiple processors together."""
    print("\nTEST: Chained processors (GWF + Elemental Adept)")

    roll = create_test_roll([1, 2, 4], bonus=0)
    print(f"  Original: {roll.results}")

    # First: GWF rerolls 1s and 2s
    after_gwf = reroll_below_and_substitute(roll, threshold=2, dice_size=6)
    print(f"  After GWF: {after_gwf.results}")

    # Then: Elemental Adept floors to 2 (in case GWF rolled another 1)
    after_ea = floor_results(after_gwf, minimum=2)
    print(f"  After EA: {after_ea.results}")

    # Verify no result is below 2
    for r in after_ea.results:
        assert r >= 2, f"Result {r} is below minimum 2"

    # Verify third die (4) was never changed
    assert after_ea.results[2] == 4, "Third die was modified incorrectly"

    print("  PASSED")


def test_preserves_metadata():
    """Test that all processors preserve dice metadata."""
    print("\nTEST: Metadata preservation")

    original = create_test_roll([1, 2, 3], bonus=5)
    original_uuid = original.dice_uuid
    original_source = original.source_entity_uuid
    original_target = original.target_entity_uuid

    processors = [
        ("maximize_all", lambda r: maximize_all(r, 6)),
        ("minimize_all", minimize_all),
        ("set_all_to", lambda r: set_all_to(r, 4)),
        ("floor_results", lambda r: floor_results(r, 2)),
        ("ceiling_results", lambda r: ceiling_results(r, 5)),
    ]

    for name, processor in processors:
        modified = processor(original)
        assert modified.dice_uuid == original_uuid, f"{name} changed dice_uuid"
        assert modified.source_entity_uuid == original_source, f"{name} changed source"
        assert modified.target_entity_uuid == original_target, f"{name} changed target"
        assert modified.bonus == 5, f"{name} changed bonus"
        assert modified.roll_type == RollType.DAMAGE, f"{name} changed roll_type"

    print("  All processors preserve: dice_uuid, source, target, bonus, roll_type")
    print("  PASSED")


if __name__ == "__main__":
    print("=" * 60)
    print("DICE PROCESSOR TESTS")
    print("=" * 60)

    test_create_modified_dice_roll()
    test_maximize_all()
    test_minimize_all()
    test_set_all_to()
    test_substitute_value()
    test_floor_results()
    test_ceiling_results()
    test_reroll_below_and_substitute()
    test_reroll_below_keep_best()
    test_reroll_ones_once()
    test_chained_processors()
    test_preserves_metadata()

    print()
    print("=" * 60)
    print("ALL DICE PROCESSOR TESTS PASSED")
    print("=" * 60)
