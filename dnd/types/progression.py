"""Character-progression policy vocabulary."""

from enum import Enum


class CasterProgression(str, Enum):
    """Normal shared-slot contribution category for one class."""

    NON_CASTER = "non_caster"
    FULL_CASTER = "full_caster"
    HALF_CASTER = "half_caster"
    THIRD_CASTER = "third_caster"


class MulticlassSlotRoundingPolicy(str, Enum):
    """Selected hybrid rule for aggregate half-caster contributions."""

    SRD_5_2_ROUND_UP = "srd_5_2_round_up"
    SRD_5_1_ROUND_DOWN = "srd_5_1_round_down"


__all__ = ["CasterProgression", "MulticlassSlotRoundingPolicy"]

