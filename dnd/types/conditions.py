"""Dependency-neutral condition classification and lifecycle enums."""

from enum import Enum


class HazardFilter(str, Enum):
    """Pathfinding hazard targeting policy for condition-bearing blocks."""

    ALL = "all"
    ENEMIES = "enemies"
    NON_SOURCE = "non_source"


class ConditionTag(str, Enum):
    """Tags used by spell and restoration effects to classify conditions."""

    MAGICAL = "magical"
    CURSE = "curse"
    DISEASE = "disease"
    POISON = "poison"
    EXHAUSTION = "exhaustion"
    PETRIFICATION = "petrification"
    ABILITY_SCORE_REDUCTION = "ability_score_reduction"
    HIT_POINT_MAXIMUM_REDUCTION = "hit_point_maximum_reduction"
    CONCENTRATION = "concentration"


class ConditionCategory(str, Enum):
    """Broad condition category used by logs, reducers, and cleanup policy."""

    CONDITION = "condition"
    STATUS = "status"
    INTERNAL = "internal"


class ConditionRemovalTrigger(str, Enum):
    """Observable state transition that removes a condition."""

    POSITIVE_DAMAGE_APPLIED = "positive_damage_applied"
    SHAKE_AWAKE = "shake_awake"


class ConditionAgencyDenial(str, Enum):
    """Degree of turn agency denied while a condition remains active."""

    NONE = "none"
    FULL_TURN = "full_turn"


class ConditionApplicationPolicy(str, Enum):
    """How one authored condition family admits a repeated application."""

    REPLACE_EXISTING = "replace_existing"
    MOST_POTENT_ACTIVE = "most_potent_active"


class ConditionApplicationDisposition(str, Enum):
    """Observable outcome of one condition-application attempt."""

    APPLIED = "applied"
    REJECTED = "rejected"
    RETAINED_STRONGER = "retained_stronger"
    PROMOTED = "promoted"
    IMMUNE = "immune"


class DurationType(str, Enum):
    """Supported duration progression modes for conditions."""

    ROUNDS = "rounds"
    PERMANENT = "permanent"
    UNTIL_LONG_REST = "until_long_rest"
    ON_CONDITION = "on_condition"


__all__ = [
    "ConditionAgencyDenial",
    "ConditionApplicationDisposition",
    "ConditionApplicationPolicy",
    "ConditionCategory",
    "ConditionRemovalTrigger",
    "ConditionTag",
    "DurationType",
    "HazardFilter",
]

