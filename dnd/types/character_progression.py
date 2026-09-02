"""Dependency-leaf semantic state for direct characters."""

from dataclasses import dataclass
from enum import Enum, StrEnum

from dnd.types.abilities import AbilityName


class Species(StrEnum):
    DRAGONBORN = "species.dragonborn"
    DWARF = "species.dwarf"
    ELF = "species.elf"
    GNOME = "species.gnome"
    HALF_ELF = "species.half_elf"
    HALF_ORC = "species.half_orc"
    HALFLING = "species.halfling"
    HUMAN = "species.human"
    TIEFLING = "species.tiefling"


class SpeciesVariant(StrEnum):
    HILL_DWARF = "species_variant.dwarf.hill"
    HIGH_ELF = "species_variant.elf.high"
    ROCK_GNOME = "species_variant.gnome.rock"
    LIGHTFOOT = "species_variant.halfling.lightfoot"


class Background(StrEnum):
    ACOLYTE = "background.acolyte"
    ADVENTURER = "background.adventurer"


class CharacterClass(StrEnum):
    BARBARIAN = "class.barbarian"
    FIGHTER = "class.fighter"
    SORCERER = "class.sorcerer"


class CharacterSubclass(StrEnum):
    BERSERKER = "subclass.barbarian.berserker"
    CHAMPION = "subclass.fighter.champion"
    DRACONIC_BLOODLINE = "subclass.sorcerer.draconic_bloodline"


class RitualPreparationPolicy(str, Enum):
    """How one spellcasting source proves ritual entitlement."""

    NONE = "none"
    KNOWN = "known"
    PREPARED = "prepared"
    SPELLBOOK = "spellbook"


class OriginCapability(str, Enum):
    """Durable non-numerical origin capabilities with exact rules identity."""

    ARTIFICERS_LORE = "origin_capability.artificers_lore"
    HALFLING_NIMBLENESS = "origin_capability.halfling_nimbleness"
    MAGICAL_SLEEP_IMMUNITY = "origin_capability.magical_sleep_immunity"
    NATURALLY_STEALTHY = "origin_capability.naturally_stealthy"
    SHELTER_OF_THE_FAITHFUL = "origin_capability.shelter_of_the_faithful"
    STONECUNNING = "origin_capability.stonecunning"
    TINKER = "origin_capability.tinker"
    TRANCE = "origin_capability.trance"


def _require_semantic_id(value: str, field_name: str) -> None:
    if not value or "." not in value:
        raise ValueError(f"{field_name} must be a namespaced semantic ID")


def _require_unique_choice_ids(
    choices: tuple["OriginChoiceSelection | ClassChoiceSelection", ...],
) -> None:
    choice_ids = tuple(choice.choice_id for choice in choices)
    if len(set(choice_ids)) != len(choice_ids):
        raise ValueError("choices contain duplicate choice IDs")


@dataclass(frozen=True, slots=True)
class OriginChoiceSelection:
    """The ordered values selected for one authored origin choice."""

    choice_id: str
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_semantic_id(self.choice_id, "choice_id")
        if not self.values or any(not value for value in self.values):
            raise ValueError("origin choice values cannot be empty")
        if len(set(self.values)) != len(self.values):
            raise ValueError("origin choice values must be unique")


@dataclass(frozen=True, slots=True)
class ClassChoiceSelection:
    """The ordered semantic values selected for one authored class choice."""

    choice_id: str
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_semantic_id(self.choice_id, "choice_id")
        if not self.values or any(not value for value in self.values):
            raise ValueError("class choice values cannot be empty")
        if len(set(self.values)) != len(self.values):
            raise ValueError("class choice values must be unique")


@dataclass(frozen=True, slots=True)
class AppliedOriginState:
    """Selections required to rebuild one installed character origin."""

    base_ability_scores: tuple[tuple[AbilityName, int], ...] = ()
    flexible_ability_bonuses: tuple[tuple[AbilityName, int], ...] = ()
    choices: tuple[OriginChoiceSelection, ...] = ()

    def __post_init__(self) -> None:
        base_names = tuple(name for name, _ in self.base_ability_scores)
        if len(set(base_names)) != len(base_names):
            raise ValueError("base ability scores contain duplicate abilities")
        if any(score < 0 for _, score in self.base_ability_scores):
            raise ValueError("base ability scores cannot be negative")
        bonus_names = tuple(name for name, _ in self.flexible_ability_bonuses)
        if len(set(bonus_names)) != len(bonus_names):
            raise ValueError("flexible bonuses contain duplicate abilities")
        _require_unique_choice_ids(self.choices)


@dataclass(frozen=True, slots=True)
class AppliedClassLevel:
    """One ordered class-level step installed on an Entity."""

    step_id: str
    character_level: int
    class_id: CharacterClass
    resulting_class_level: int
    subclass_id: CharacterSubclass | None = None
    choices: tuple[ClassChoiceSelection, ...] = ()

    def __post_init__(self) -> None:
        _require_semantic_id(self.step_id, "step_id")
        if not 1 <= self.character_level <= 20:
            raise ValueError("character_level must be between 1 and 20")
        if not 1 <= self.resulting_class_level <= 20:
            raise ValueError("resulting_class_level must be between 1 and 20")
        _require_unique_choice_ids(self.choices)


@dataclass(frozen=True, slots=True)
class PreparedSpellSelection:
    """Ordered prepared spells owned by one semantic casting source."""

    source_id: str
    spell_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_semantic_id(self.source_id, "source_id")
        if len(set(self.spell_ids)) != len(self.spell_ids):
            raise ValueError("prepared spells must be unique within a source")
        for spell_id in self.spell_ids:
            _require_semantic_id(spell_id, "spell_id")


@dataclass(frozen=True, slots=True)
class FeatureToggleSelection:
    """One explicit enabled or disabled player-facing feature toggle."""

    feature_id: str
    enabled: bool

    def __post_init__(self) -> None:
        _require_semantic_id(self.feature_id, "feature_id")


__all__ = [
    "AppliedClassLevel",
    "AppliedOriginState",
    "Background",
    "CharacterClass",
    "CharacterSubclass",
    "ClassChoiceSelection",
    "FeatureToggleSelection",
    "OriginCapability",
    "OriginChoiceSelection",
    "PreparedSpellSelection",
    "RitualPreparationPolicy",
    "Species",
    "SpeciesVariant",
]
