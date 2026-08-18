"""Cold authored definitions for character origins and their choices."""

from dataclasses import dataclass
from typing import Mapping, Optional

from dnd.types.abilities import SkillName
from dnd.types.creatures import (
    Background,
    OriginCapability,
    Size,
    Species,
    SpeciesVariant,
)
from dnd.types.languages import SrdLanguageId


@dataclass(frozen=True, slots=True)
class OriginChoiceDefinition:
    """Allowed values and cardinality for one persisted origin choice."""

    choice_id: str
    minimum_selections: int
    maximum_selections: int
    allowed_values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SpeciesDefinition:
    """One authored species identity and its complete semantic grant list."""

    species: Species
    display_name: str
    description: str
    size: Size
    walking_speed_feet: int
    fixed_languages: tuple[SrdLanguageId, ...]
    variants: tuple[SpeciesVariant, ...] = ()
    fixed_skills: tuple[SkillName, ...] = ()
    capabilities: tuple[OriginCapability, ...] = ()
    feature_ids: tuple[str, ...] = ()
    choices: tuple[OriginChoiceDefinition, ...] = ()


@dataclass(frozen=True, slots=True)
class SpeciesVariantDefinition:
    """One authored species variant and its additional grants."""

    variant: SpeciesVariant
    parent_species: Species
    display_name: str
    description: str
    fixed_languages: tuple[SrdLanguageId, ...] = ()
    capabilities: tuple[OriginCapability, ...] = ()
    feature_ids: tuple[str, ...] = ()
    choices: tuple[OriginChoiceDefinition, ...] = ()


@dataclass(frozen=True, slots=True)
class BackgroundDefinition:
    """One authored background and its complete starting grant list."""

    background: Background
    display_name: str
    description: str
    fixed_skills: tuple[SkillName, ...] = ()
    capabilities: tuple[OriginCapability, ...] = ()
    feature_ids: tuple[str, ...] = ()
    choices: tuple[OriginChoiceDefinition, ...] = ()


_ALL_LANGUAGES = tuple(language.value for language in SrdLanguageId)
_ALL_SKILLS = tuple(skill.value for skill in SkillName)
_DRACONIC_ANCESTRIES = (
    "black",
    "blue",
    "brass",
    "bronze",
    "copper",
    "gold",
    "green",
    "red",
    "silver",
    "white",
)


SPECIES_DEFINITIONS: Mapping[Species, SpeciesDefinition] = {
    Species.DRAGONBORN: SpeciesDefinition(
        species=Species.DRAGONBORN,
        display_name="Dragonborn",
        description=(
            "A draconic people with an ancestry-shaped breath weapon and "
            "resistance to its associated damage type."
        ),
        size=Size.MEDIUM,
        walking_speed_feet=30,
        fixed_languages=(SrdLanguageId.COMMON, SrdLanguageId.DRACONIC),
        feature_ids=(
            "species.dragonborn.ancestry_resistance",
            "species.dragonborn.breath_weapon",
        ),
        choices=(OriginChoiceDefinition(
            choice_id="species.dragonborn.draconic_ancestry",
            minimum_selections=1,
            maximum_selections=1,
            allowed_values=_DRACONIC_ANCESTRIES,
        ),),
    ),
    Species.DWARF: SpeciesDefinition(
        species=Species.DWARF,
        display_name="Dwarf",
        description=(
            "A sturdy people with darkvision, poison resilience, combat "
            "training, tool training, and stonecunning."
        ),
        size=Size.MEDIUM,
        walking_speed_feet=25,
        fixed_languages=(SrdLanguageId.COMMON, SrdLanguageId.DWARVISH),
        variants=(SpeciesVariant.HILL_DWARF,),
        capabilities=(OriginCapability.STONECUNNING,),
        feature_ids=(
            "sense.darkvision.60",
            "species.dwarf.combat_training",
            "species.dwarf.poison_resilience",
        ),
        choices=(OriginChoiceDefinition(
            choice_id="species.dwarf.artisans_tool",
            minimum_selections=1,
            maximum_selections=1,
            allowed_values=(
                "tool.artisan.brewers_supplies",
                "tool.artisan.masons_tools",
                "tool.artisan.smiths_tools",
            ),
        ),),
    ),
    Species.ELF: SpeciesDefinition(
        species=Species.ELF,
        display_name="Elf",
        description=(
            "A perceptive, long-lived people with darkvision, keen senses, "
            "fey ancestry, and trance."
        ),
        size=Size.MEDIUM,
        walking_speed_feet=30,
        fixed_languages=(SrdLanguageId.COMMON, SrdLanguageId.ELVISH),
        variants=(SpeciesVariant.HIGH_ELF,),
        fixed_skills=(SkillName.PERCEPTION,),
        capabilities=(
            OriginCapability.MAGICAL_SLEEP_IMMUNITY,
            OriginCapability.TRANCE,
        ),
        feature_ids=("sense.darkvision.60", "species.elf.fey_ancestry"),
    ),
    Species.GNOME: SpeciesDefinition(
        species=Species.GNOME,
        display_name="Gnome",
        description=(
            "A small, inventive people with darkvision and Gnome Cunning "
            "against mental magic."
        ),
        size=Size.SMALL,
        walking_speed_feet=25,
        fixed_languages=(SrdLanguageId.COMMON, SrdLanguageId.GNOMISH),
        variants=(SpeciesVariant.ROCK_GNOME,),
        feature_ids=("sense.darkvision.60", "species.gnome.cunning"),
    ),
    Species.HALF_ELF: SpeciesDefinition(
        species=Species.HALF_ELF,
        display_name="Half-Elf",
        description=(
            "A versatile people with darkvision, fey ancestry, two chosen "
            "skill proficiencies, and an additional language."
        ),
        size=Size.MEDIUM,
        walking_speed_feet=30,
        fixed_languages=(SrdLanguageId.COMMON, SrdLanguageId.ELVISH),
        capabilities=(OriginCapability.MAGICAL_SLEEP_IMMUNITY,),
        feature_ids=("sense.darkvision.60", "species.elf.fey_ancestry"),
        choices=(
            OriginChoiceDefinition(
                choice_id="species.half_elf.additional_language",
                minimum_selections=1,
                maximum_selections=1,
                allowed_values=tuple(
                    value for value in _ALL_LANGUAGES
                    if value not in {
                        SrdLanguageId.COMMON.value,
                        SrdLanguageId.ELVISH.value,
                    }
                ),
            ),
            OriginChoiceDefinition(
                choice_id="species.half_elf.skill_versatility",
                minimum_selections=2,
                maximum_selections=2,
                allowed_values=_ALL_SKILLS,
            ),
        ),
    ),
    Species.HALF_ORC: SpeciesDefinition(
        species=Species.HALF_ORC,
        display_name="Half-Orc",
        description=(
            "A powerful people with darkvision, Menacing, Relentless "
            "Endurance, and Savage Attacks."
        ),
        size=Size.MEDIUM,
        walking_speed_feet=30,
        fixed_languages=(SrdLanguageId.COMMON, SrdLanguageId.ORC),
        fixed_skills=(SkillName.INTIMIDATION,),
        feature_ids=(
            "sense.darkvision.60",
            "species.half_orc.relentless_endurance",
            "species.half_orc.savage_attacks",
        ),
    ),
    Species.HALFLING: SpeciesDefinition(
        species=Species.HALFLING,
        display_name="Halfling",
        description=(
            "A small and nimble people with Lucky, Brave, and Halfling "
            "Nimbleness."
        ),
        size=Size.SMALL,
        walking_speed_feet=25,
        fixed_languages=(SrdLanguageId.COMMON, SrdLanguageId.HALFLING),
        variants=(SpeciesVariant.LIGHTFOOT_HALFLING,),
        capabilities=(OriginCapability.HALFLING_NIMBLENESS,),
        feature_ids=("species.halfling.brave", "species.halfling.lucky"),
    ),
    Species.HUMAN: SpeciesDefinition(
        species=Species.HUMAN,
        display_name="Human",
        description="An adaptable people using the selected flexible bonuses.",
        size=Size.MEDIUM,
        walking_speed_feet=30,
        fixed_languages=(SrdLanguageId.COMMON,),
        choices=(OriginChoiceDefinition(
            choice_id="species.human.additional_language",
            minimum_selections=1,
            maximum_selections=1,
            allowed_values=tuple(
                value for value in _ALL_LANGUAGES
                if value != SrdLanguageId.COMMON.value
            ),
        ),),
    ),
    Species.TIEFLING: SpeciesDefinition(
        species=Species.TIEFLING,
        display_name="Tiefling",
        description=(
            "An infernal-blooded people with darkvision, fire resistance, "
            "and a level-based Infernal Legacy."
        ),
        size=Size.MEDIUM,
        walking_speed_feet=30,
        fixed_languages=(SrdLanguageId.COMMON, SrdLanguageId.INFERNAL),
        feature_ids=(
            "sense.darkvision.60",
            "species.tiefling.fire_resistance",
            "species.tiefling.infernal_legacy",
        ),
    ),
}


SPECIES_VARIANT_DEFINITIONS: Mapping[
    SpeciesVariant,
    SpeciesVariantDefinition,
] = {
    SpeciesVariant.HILL_DWARF: SpeciesVariantDefinition(
        variant=SpeciesVariant.HILL_DWARF,
        parent_species=Species.DWARF,
        display_name="Hill Dwarf",
        description="A Dwarf with one additional maximum hit point per level.",
        feature_ids=("species_variant.hill_dwarf.dwarven_toughness",),
    ),
    SpeciesVariant.HIGH_ELF: SpeciesVariantDefinition(
        variant=SpeciesVariant.HIGH_ELF,
        parent_species=Species.ELF,
        display_name="High Elf",
        description=(
            "An Elf with weapon training, one wizard cantrip, and one "
            "additional language."
        ),
        feature_ids=(
            "species_variant.high_elf.weapon_training",
            "species_variant.high_elf.wizard_cantrip",
        ),
        choices=(
            OriginChoiceDefinition(
                choice_id="species_variant.high_elf.additional_language",
                minimum_selections=1,
                maximum_selections=1,
                allowed_values=tuple(
                    value for value in _ALL_LANGUAGES
                    if value not in {
                        SrdLanguageId.COMMON.value,
                        SrdLanguageId.ELVISH.value,
                    }
                ),
            ),
            OriginChoiceDefinition(
                choice_id="species_variant.high_elf.wizard_cantrip",
                minimum_selections=1,
                maximum_selections=1,
                allowed_values=("spell.fire_bolt",),
            ),
        ),
    ),
    SpeciesVariant.ROCK_GNOME: SpeciesVariantDefinition(
        variant=SpeciesVariant.ROCK_GNOME,
        parent_species=Species.GNOME,
        display_name="Rock Gnome",
        description="A Gnome with Artificer's Lore and Tinker.",
        capabilities=(
            OriginCapability.ARTIFICERS_LORE,
            OriginCapability.TINKER,
        ),
        feature_ids=("species_variant.rock_gnome.tinkers_tools",),
    ),
    SpeciesVariant.LIGHTFOOT_HALFLING: SpeciesVariantDefinition(
        variant=SpeciesVariant.LIGHTFOOT_HALFLING,
        parent_species=Species.HALFLING,
        display_name="Lightfoot Halfling",
        description="A Halfling able to hide behind larger creatures.",
        capabilities=(OriginCapability.NATURALLY_STEALTHY,),
    ),
}


BACKGROUND_DEFINITIONS: Mapping[Background, BackgroundDefinition] = {
    Background.ACOLYTE: BackgroundDefinition(
        background=Background.ACOLYTE,
        display_name="Acolyte",
        description=(
            "Temple service granting Insight and Religion, two languages, "
            "religious equipment, and Shelter of the Faithful."
        ),
        fixed_skills=(SkillName.INSIGHT, SkillName.RELIGION),
        capabilities=(OriginCapability.SHELTER_OF_THE_FAITHFUL,),
        feature_ids=("background.acolyte.starting_holdings",),
        choices=(OriginChoiceDefinition(
            choice_id="background.acolyte.languages",
            minimum_selections=2,
            maximum_selections=2,
            allowed_values=_ALL_LANGUAGES,
        ),),
    ),
    Background.ADVENTURER: BackgroundDefinition(
        background=Background.ADVENTURER,
        display_name="Adventurer",
        description="A deliberately neutral background with no grants.",
    ),
}


def get_species_variant_definition(
    variant: Optional[SpeciesVariant],
) -> Optional[SpeciesVariantDefinition]:
    """Resolve an optional variant without a generic content registry."""
    return None if variant is None else SPECIES_VARIANT_DEFINITIONS[variant]


__all__ = [
    "BACKGROUND_DEFINITIONS",
    "SPECIES_DEFINITIONS",
    "SPECIES_VARIANT_DEFINITIONS",
    "BackgroundDefinition",
    "OriginChoiceDefinition",
    "SpeciesDefinition",
    "SpeciesVariantDefinition",
    "get_species_variant_definition",
]
