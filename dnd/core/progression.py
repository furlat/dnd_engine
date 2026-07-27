"""Pure shared character-progression rules.

This dependency-neutral leaf owns calculations only.  Durable authored build
data lives in :mod:`dnd.core.content.durable_characters`.
"""

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import ceil
from typing import Dict, Iterable

from dnd.core.proficiency_types import ProficiencyMode

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

POINT_BUY_COSTS: dict[int, int] = {
    8: 0,
    9: 1,
    10: 2,
    11: 3,
    12: 4,
    13: 5,
    14: 7,
    15: 9,
}

CHARACTER_RULESET_SCHEMA_VERSION = 1


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


def character_ruleset_digest(
    *,
    permissive_multiclass_prerequisites: bool,
    multiclass_slot_rounding_policy: MulticlassSlotRoundingPolicy,
) -> str:
    """Authenticate the complete build-rules policy pinned by a character.

    Deployment permissions such as whether a profile currently permits
    respec, and timing policy for changing prepared spells, do not change the
    structural meaning of an already-authored build. They therefore remain
    profile policy rather than inputs to this digest.
    """

    payload = {
        "schema_version": CHARACTER_RULESET_SCHEMA_VERSION,
        "rules_baseline": "srd_5_1_with_selected_bg3_creation_rules",
        "character_level_cap": 20,
        "ability_scores": {
            "point_buy_budget": 27,
            "minimum_score": 8,
            "maximum_pre_bonus_score": 15,
            "flexible_bonus": {
                "plus_two": 2,
                "plus_one": 1,
                "must_target_distinct_abilities": True,
            },
            "ordinary_cap": 20,
        },
        "hit_points_after_character_level_one": "fixed_class_average",
        "permissive_multiclass_prerequisites": (
            permissive_multiclass_prerequisites
        ),
        "multiclass_slot_rounding_policy": (
            multiclass_slot_rounding_policy.value
        ),
    }
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class SpellcastingClassContribution:
    """One class's inputs to normal shared spell-slot progression."""

    class_level: int
    progression: CasterProgression
    spellcasting_feature_class_level: int | None = None

    def __post_init__(self) -> None:
        _validate_character_level(self.class_level)
        feature_level = self.spellcasting_feature_class_level
        if self.progression == CasterProgression.NON_CASTER:
            if feature_level is not None:
                raise ValueError(
                    "non-caster contribution cannot declare a spellcasting "
                    "feature level",
                )
            return
        if feature_level is None:
            raise ValueError(
                "caster contribution requires spellcasting_feature_class_level",
            )
        _validate_character_level(feature_level)

    @property
    def is_eligible(self) -> bool:
        """Whether this class has actually gained Spellcasting."""
        feature_level = self.spellcasting_feature_class_level
        return (
            self.progression != CasterProgression.NON_CASTER
            and feature_level is not None
            and self.class_level >= feature_level
        )


def point_buy_cost(score: int) -> int:
    """Return the standard 27-point-buy cost of one pre-bonus score."""
    try:
        return POINT_BUY_COSTS[score]
    except KeyError as error:
        raise ValueError(
            f"Point-buy score must be between 8 and 15, got {score}",
        ) from error


def resolve_proficiency_bonus(
    proficiency_bonus: int,
    applications: Iterable[ProficiencyMode],
) -> int:
    """Resolve competing proficiency sources without stacking duplicates."""
    if proficiency_bonus < 0:
        raise ValueError("proficiency_bonus cannot be negative")
    modes = frozenset(applications)
    if ProficiencyMode.FULL in modes:
        if ProficiencyMode.EXPERTISE in modes:
            return 2 * proficiency_bonus
        return proficiency_bonus
    if ProficiencyMode.HALF_ROUND_UP in modes:
        return ceil(proficiency_bonus / 2)
    if ProficiencyMode.HALF_ROUND_DOWN in modes:
        return proficiency_bonus // 2
    return 0


def effective_spellcaster_level(
    contributions: Iterable[SpellcastingClassContribution],
    *,
    policy: MulticlassSlotRoundingPolicy = (
        MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
    ),
) -> int:
    """Resolve the normal shared-slot ESL for an additive class ledger.

    A sole eligible casting class uses its own class table equivalence.  Two or
    more eligible sources use the aggregate multiclass rule.
    """
    rows = tuple(contributions)
    if sum(row.class_level for row in rows) > 20:
        raise ValueError("total character level cannot exceed 20")
    eligible = tuple(row for row in rows if row.is_eligible)
    if not eligible:
        return 0
    if len(eligible) == 1:
        return _single_class_spellcaster_level(eligible[0])

    full_levels = sum(
        row.class_level
        for row in eligible
        if row.progression == CasterProgression.FULL_CASTER
    )
    half_levels = sum(
        row.class_level
        for row in eligible
        if row.progression == CasterProgression.HALF_CASTER
    )
    third_levels = sum(
        row.class_level
        for row in eligible
        if row.progression == CasterProgression.THIRD_CASTER
    )
    half_contribution = (
        ceil(half_levels / 2)
        if policy == MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
        else half_levels // 2
    )
    return full_levels + half_contribution + third_levels // 3


def maximum_spell_rank_for_contribution(
    contribution: SpellcastingClassContribution,
) -> int:
    """Return the highest normal spell rank unlocked by one exact source."""
    if not contribution.is_eligible:
        return 0
    individual_level = _single_class_spellcaster_level(contribution)
    if individual_level <= 0:
        return 0
    return max(FULL_CASTER_SPELL_SLOTS[individual_level], default=0)


def _single_class_spellcaster_level(
    contribution: SpellcastingClassContribution,
) -> int:
    if contribution.progression == CasterProgression.FULL_CASTER:
        return contribution.class_level
    if contribution.progression == CasterProgression.HALF_CASTER:
        return ceil(contribution.class_level / 2)
    if contribution.progression == CasterProgression.THIRD_CASTER:
        return contribution.class_level // 3
    return 0


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
