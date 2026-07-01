"""
Dice Roll Manipulation Utilities

Reference implementations for dice manipulation features.
These serve as templates for future features like:
- Elemental Adept (floor_results)
- Halfling Lucky (reroll_below_keep_best)
- Savage Attacker (reroll_ones_once)

The core utility `create_modified_dice_roll` remains in fighter.py
as it's used directly by Great Weapon Fighting.
"""

from dnd.core.dice import DiceRoll
import random

from dnd.classes.fighter import create_modified_dice_roll


def maximize_all(roll: DiceRoll, dice_size: int) -> DiceRoll:
    """All dice show maximum value. Use for: testing, divine intervention."""
    results = roll.results if isinstance(roll.results, list) else [roll.results]
    return create_modified_dice_roll(roll, [dice_size] * len(results))


def minimize_all(roll: DiceRoll) -> DiceRoll:
    """All dice show minimum value (1). Use for: cursed weapons, testing."""
    results = roll.results if isinstance(roll.results, list) else [roll.results]
    return create_modified_dice_roll(roll, [1] * len(results))


def set_all_to(roll: DiceRoll, value: int) -> DiceRoll:
    """All dice show specific value. Use for: fixed damage effects."""
    results = roll.results if isinstance(roll.results, list) else [roll.results]
    return create_modified_dice_roll(roll, [value] * len(results))


def substitute_value(roll: DiceRoll, from_val: int, to_val: int) -> DiceRoll:
    """Replace specific value with another. Use for: treat 1s as 2s."""
    results = roll.results if isinstance(roll.results, list) else [roll.results]
    new_results = [to_val if r == from_val else r for r in results]
    return create_modified_dice_roll(roll, new_results)


def floor_results(roll: DiceRoll, minimum: int) -> DiceRoll:
    """No result below minimum. Use for: Elemental Adept (treat 1s as 2s)."""
    results = roll.results if isinstance(roll.results, list) else [roll.results]
    new_results = [max(r, minimum) for r in results]
    return create_modified_dice_roll(roll, new_results)


def ceiling_results(roll: DiceRoll, maximum: int) -> DiceRoll:
    """No result above maximum. Use for: damage reduction, weakened attacks."""
    results = roll.results if isinstance(roll.results, list) else [roll.results]
    new_results = [min(r, maximum) for r in results]
    return create_modified_dice_roll(roll, new_results)


def reroll_below_and_substitute(roll: DiceRoll, threshold: int, dice_size: int) -> DiceRoll:
    """
    Reroll dice below threshold, MUST use new result.

    Use for: Great Weapon Fighting (reroll 1s and 2s on damage dice).
    """
    results = roll.results if isinstance(roll.results, list) else [roll.results]
    new_results = []
    for r in results:
        if r <= threshold:
            new_results.append(random.randint(1, dice_size))
        else:
            new_results.append(r)
    return create_modified_dice_roll(roll, new_results)


def reroll_below_keep_best(roll: DiceRoll, threshold: int, dice_size: int) -> DiceRoll:
    """Reroll dice below threshold, keep best. Use for: Halfling Lucky on damage."""
    results = roll.results if isinstance(roll.results, list) else [roll.results]
    new_results = []
    for r in results:
        if r <= threshold:
            rerolled = random.randint(1, dice_size)
            new_results.append(max(r, rerolled))
        else:
            new_results.append(r)
    return create_modified_dice_roll(roll, new_results)


def reroll_ones_once(roll: DiceRoll, dice_size: int) -> DiceRoll:
    """Reroll 1s once, must use new result. Use for: Savage Attacker variant."""
    return reroll_below_and_substitute(roll, 1, dice_size)
