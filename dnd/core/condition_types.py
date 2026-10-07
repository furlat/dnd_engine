"""Dependency-neutral condition classification and lifecycle enums."""

from dataclasses import dataclass
from enum import Enum
from uuid import UUID



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


class DurationType(str, Enum):
    """Supported duration progression modes for conditions."""

    ROUNDS = "rounds"
    PERMANENT = "permanent"
    UNTIL_LONG_REST = "until_long_rest"
    ON_CONDITION = "on_condition"


@dataclass(frozen=True, slots=True)
class ConditionDurationSummary:
    """Recorded native duration; clients never advance a separate clock."""

    duration_type: DurationType
    remaining_rounds: int | None

    def __post_init__(self) -> None:
        if (self.duration_type is DurationType.ROUNDS) != (self.remaining_rounds is not None):
            raise ValueError("Only round durations have remaining_rounds")


class SustainLossPolicy(str, Enum):
    """Whether involuntary loss must release this exact sustained branch."""

    ORDINARY = "ordinary"
    REQUIRED = "required"


class SustainLossCause(str, Enum):
    FAILED_SAVE = "failed_save"
    ZERO_HP = "zero_hp"
    DEATH = "death"


@dataclass(frozen=True)
class InvoluntarySustainLoss:
    cause: SustainLossCause
    sustaining_condition_uuid: UUID
    parent_event_uuid: UUID
    slot_uuid: UUID | None = None
