"""Shared character-level progression tables used by engine factories."""

from typing import Dict


FULL_CASTER_SPELL_SLOTS: Dict[int, Dict[int, int]] = {
    1: {1: 2},
    2: {1: 3},
    3: {1: 4, 2: 2},
    4: {1: 4, 2: 3},
    5: {1: 4, 2: 3, 3: 2},
    6: {1: 4, 2: 3, 3: 3},
    7: {1: 4, 2: 3, 3: 3, 4: 1},
    8: {1: 4, 2: 3, 3: 3, 4: 2},
    9: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    11: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    12: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    13: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    14: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    15: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
    16: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
    17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1},
    18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1, 7: 1, 8: 1, 9: 1},
    19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 1, 8: 1, 9: 1},
    20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1},
}


def proficiency_bonus_for_level(level: int) -> int:
    """Return the standard proficiency bonus for a character level.

    Args:
        level: Character level from 1 through 20.

    Returns:
        Proficiency bonus for the requested level.

    Raises:
        ValueError: If the level is outside the supported character range.
    """
    _validate_character_level(level)
    return 2 + (level - 1) // 4


def full_caster_spell_slots_for_level(level: int) -> Dict[int, int]:
    """Return an independent full-caster spell-slot allocation.

    Args:
        level: Character level from 1 through 20.

    Returns:
        Spell slot counts keyed by spell level. Absent levels have zero slots.

    Raises:
        ValueError: If the level is outside the supported character range.
    """
    _validate_character_level(level)
    return dict(FULL_CASTER_SPELL_SLOTS[level])


def _validate_character_level(level: int) -> None:
    """Reject levels outside the implemented character progression."""
    if level < 1 or level > 20:
        raise ValueError(f"Character level must be between 1 and 20, got {level}")
