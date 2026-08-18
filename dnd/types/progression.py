"""Dependency-neutral persisted entity-progression state."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from dnd.types.abilities import AbilityName


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


class RitualPreparationPolicy(str, Enum):
    """How one spellcasting source proves ritual entitlement."""

    NONE = "none"
    KNOWN = "known"
    PREPARED = "prepared"
    SPELLBOOK = "spellbook"


class CharacterClass(str, Enum):
    """Built-in class identities supported by the current authored rules."""

    BARBARIAN = "barbarian"
    FIGHTER = "fighter"
    SORCERER = "sorcerer"


class CharacterSubclass(str, Enum):
    """Built-in subclass identities supported by the current authored rules."""

    BERSERKER = "berserker"
    CHAMPION = "champion"
    DRACONIC_BLOODLINE = "draconic_bloodline"


@dataclass(frozen=True, slots=True)
class OriginChoiceSelection:
    """The ordered values selected for one authored origin choice."""

    choice_id: str
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.choice_id:
            raise ValueError("origin choice_id cannot be empty")
        if not self.values:
            raise ValueError("origin choice requires at least one value")
        if any(not value for value in self.values):
            raise ValueError("origin choice values cannot be empty")
        if len(set(self.values)) != len(self.values):
            raise ValueError("origin choice values must be unique")


@dataclass(frozen=True, slots=True)
class ClassChoiceSelection:
    """The ordered semantic values selected for one authored level choice."""

    choice_id: str
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.choice_id:
            raise ValueError("class choice_id cannot be empty")
        if not self.values:
            raise ValueError("class choice requires at least one value")
        if any(not value for value in self.values):
            raise ValueError("class choice values cannot be empty")
        if len(set(self.values)) != len(self.values):
            raise ValueError("class choice values must be unique")


@dataclass(frozen=True, slots=True)
class AppliedOriginState:
    """Persisted construction inputs needed to rebuild origin mechanics."""

    base_ability_scores: tuple[tuple[AbilityName, int], ...] = ()
    flexible_ability_bonuses: tuple[tuple[AbilityName, int], ...] = ()
    choices: tuple[OriginChoiceSelection, ...] = ()

    def __post_init__(self) -> None:
        ability_names = tuple(name for name, _ in self.base_ability_scores)
        if len(set(ability_names)) != len(ability_names):
            raise ValueError("base ability scores contain duplicate abilities")
        if any(score < 0 for _, score in self.base_ability_scores):
            raise ValueError("base ability scores cannot be negative")
        bonus_names = tuple(name for name, _ in self.flexible_ability_bonuses)
        if len(set(bonus_names)) != len(bonus_names):
            raise ValueError("flexible bonuses contain duplicate abilities")
        choice_ids = tuple(choice.choice_id for choice in self.choices)
        if len(set(choice_ids)) != len(choice_ids):
            raise ValueError("origin choices contain duplicate choice IDs")


@dataclass(frozen=True, slots=True)
class AppliedClassLevel:
    """One serialized, ordered class-level step installed on an Entity."""

    step_id: str
    character_level: int
    class_id: CharacterClass
    resulting_class_level: int
    subclass_id: Optional[CharacterSubclass] = None
    choices: tuple[ClassChoiceSelection, ...] = ()

    def __post_init__(self) -> None:
        if not self.step_id:
            raise ValueError("class-level step_id cannot be empty")
        if not 1 <= self.character_level <= 20:
            raise ValueError("character_level must be between 1 and 20")
        if not 1 <= self.resulting_class_level <= 20:
            raise ValueError("resulting_class_level must be between 1 and 20")
        choice_ids = tuple(choice.choice_id for choice in self.choices)
        if len(set(choice_ids)) != len(choice_ids):
            raise ValueError("level choices contain duplicate choice IDs")


__all__ = [
    "AppliedClassLevel",
    "AppliedOriginState",
    "CasterProgression",
    "ClassChoiceSelection",
    "CharacterClass",
    "CharacterSubclass",
    "MulticlassSlotRoundingPolicy",
    "OriginChoiceSelection",
    "RitualPreparationPolicy",
]
