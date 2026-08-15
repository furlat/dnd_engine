"""Canonical dice and roll vocabulary."""

from enum import Enum
from typing import Literal


DieSize = Literal[4, 6, 8, 10, 12, 20]
HitDieSize = Literal[4, 6, 8, 10, 12]


class AdvantageStatus(str, Enum):
    """Net d20 advantage state after advantage and disadvantage cancel."""

    NONE = "None"
    ADVANTAGE = "Advantage"
    DISADVANTAGE = "Disadvantage"


class AutoHitStatus(str, Enum):
    """Automatic hit or miss override applied to a roll."""

    NONE = "None"
    AUTOHIT = "Autohit"
    AUTOMISS = "Automiss"


class CriticalStatus(str, Enum):
    """Critical-hit override applied to a roll."""

    NONE = "None"
    AUTOCRIT = "Autocrit"
    NOCRIT = "Critical Immune"


class AttackOutcome(str, Enum):
    """Resolved attack-roll outcome."""

    HIT = "Hit"
    MISS = "Miss"
    CRIT = "Crit"
    CRIT_MISS = "Crit Miss"


class RollType(str, Enum):
    """Rules category of a concrete dice roll."""

    DAMAGE = "Damage"
    ATTACK = "Attack"
    SAVE = "Save"
    CHECK = "Check"
    HEAL = "Heal"


__all__ = [
    "AdvantageStatus",
    "AttackOutcome",
    "AutoHitStatus",
    "CriticalStatus",
    "DieSize",
    "HitDieSize",
    "RollType",
]

