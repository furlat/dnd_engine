"""Cold direct definitions and pure resolution for character origins."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping, cast

from dnd.core.creature_types import DamageType, Size
from dnd.core.language_types import SrdLanguageId
from dnd.types.abilities import AbilityName, SkillName
from dnd.types.character_progression import (
    AppliedOriginState,
    Background,
    OriginCapability,
    Species,
    SpeciesVariant,
)


@dataclass(frozen=True, slots=True)
class OriginChoiceDefinition:
    """One exact ordered origin choice requirement."""

    choice_id: str
    selections: int
    allowed_values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SpeciesDefinition:
    """Cold authored values supplied by one species."""

    species: Species
    size: Size
    walking_speed_feet: int
    fixed_languages: tuple[str, ...]
    variants: tuple[SpeciesVariant, ...] = ()
    fixed_skills: tuple[SkillName, ...] = ()
    capabilities: tuple[OriginCapability, ...] = ()
    feature_ids: tuple[str, ...] = ()
    choices: tuple[OriginChoiceDefinition, ...] = ()


@dataclass(frozen=True, slots=True)
class SpeciesVariantDefinition:
    """Cold authored additions supplied by one species variant."""

    variant: SpeciesVariant
    parent_species: Species
    fixed_languages: tuple[str, ...] = ()
    capabilities: tuple[OriginCapability, ...] = ()
    feature_ids: tuple[str, ...] = ()
    choices: tuple[OriginChoiceDefinition, ...] = ()


@dataclass(frozen=True, slots=True)
class BackgroundDefinition:
    """Cold authored values supplied by one background."""

    background: Background
    fixed_skills: tuple[SkillName, ...] = ()
    capabilities: tuple[OriginCapability, ...] = ()
    feature_ids: tuple[str, ...] = ()
    choices: tuple[OriginChoiceDefinition, ...] = ()


@dataclass(frozen=True, slots=True)
class DragonbornAncestryDefinition:
    """Resistance, save, and geometry selected by draconic ancestry."""

    damage_type: DamageType
    geometry: Literal["line", "cone"]
    save_ability: AbilityName


@dataclass(frozen=True, slots=True)
class ResolvedOrigin:
    """Validated direct values consumed by the origin installer."""

    species: Species
    species_variant: SpeciesVariant | None
    background: Background
    state: AppliedOriginState
    size: Size
    walking_speed_feet: int
    languages: tuple[str, ...]
    skills: tuple[SkillName, ...]
    tools: tuple[str, ...]
    capabilities: tuple[OriginCapability, ...]
    feature_ids: tuple[str, ...]
    choices: tuple[tuple[str, tuple[str, ...]], ...]

    def choice(self, choice_id: str) -> tuple[str, ...]:
        """Return one already-validated choice directly."""
        for row_id, values in self.choices:
            if row_id == choice_id:
                return values
        raise KeyError(choice_id)


ABILITY_ORDER: tuple[AbilityName, ...] = (
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)
ALL_SKILLS: tuple[SkillName, ...] = (
    "acrobatics",
    "animal_handling",
    "arcana",
    "athletics",
    "deception",
    "history",
    "insight",
    "intimidation",
    "investigation",
    "medicine",
    "nature",
    "perception",
    "performance",
    "persuasion",
    "religion",
    "sleight_of_hand",
    "stealth",
    "survival",
)
ALL_LANGUAGES = tuple(language.value for language in SrdLanguageId)
DRACONIC_ANCESTRIES = (
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


SPECIES_DEFINITIONS: Mapping[Species, SpeciesDefinition] = MappingProxyType({
    Species.DRAGONBORN: SpeciesDefinition(
        Species.DRAGONBORN,
        Size.MEDIUM,
        30,
        (SrdLanguageId.COMMON.value, SrdLanguageId.DRACONIC.value),
        feature_ids=(
            "species.dragonborn.ancestry_resistance",
            "species.dragonborn.breath_weapon",
        ),
        choices=(OriginChoiceDefinition(
            "species.dragonborn.draconic_ancestry",
            1,
            DRACONIC_ANCESTRIES,
        ),),
    ),
    Species.DWARF: SpeciesDefinition(
        Species.DWARF,
        Size.MEDIUM,
        25,
        (SrdLanguageId.COMMON.value, SrdLanguageId.DWARVISH.value),
        variants=(SpeciesVariant.HILL_DWARF,),
        capabilities=(OriginCapability.STONECUNNING,),
        feature_ids=(
            "sense.darkvision.60",
            "species.dwarf.combat_training",
            "species.dwarf.poison_resilience",
        ),
        choices=(OriginChoiceDefinition(
            "species.dwarf.artisans_tool",
            1,
            (
                "tool.artisan.brewers_supplies",
                "tool.artisan.masons_tools",
                "tool.artisan.smiths_tools",
            ),
        ),),
    ),
    Species.ELF: SpeciesDefinition(
        Species.ELF,
        Size.MEDIUM,
        30,
        (SrdLanguageId.COMMON.value, SrdLanguageId.ELVISH.value),
        variants=(SpeciesVariant.HIGH_ELF,),
        fixed_skills=("perception",),
        capabilities=(
            OriginCapability.MAGICAL_SLEEP_IMMUNITY,
            OriginCapability.TRANCE,
        ),
        feature_ids=("sense.darkvision.60", "species.elf.fey_ancestry"),
    ),
    Species.GNOME: SpeciesDefinition(
        Species.GNOME,
        Size.SMALL,
        25,
        (SrdLanguageId.COMMON.value, SrdLanguageId.GNOMISH.value),
        variants=(SpeciesVariant.ROCK_GNOME,),
        feature_ids=("sense.darkvision.60", "species.gnome.cunning"),
    ),
    Species.HALF_ELF: SpeciesDefinition(
        Species.HALF_ELF,
        Size.MEDIUM,
        30,
        (SrdLanguageId.COMMON.value, SrdLanguageId.ELVISH.value),
        capabilities=(OriginCapability.MAGICAL_SLEEP_IMMUNITY,),
        feature_ids=("sense.darkvision.60", "species.elf.fey_ancestry"),
        choices=(
            OriginChoiceDefinition(
                "species.half_elf.additional_language",
                1,
                tuple(value for value in ALL_LANGUAGES if value not in {
                    SrdLanguageId.COMMON.value,
                    SrdLanguageId.ELVISH.value,
                }),
            ),
            OriginChoiceDefinition(
                "species.half_elf.skill_versatility",
                2,
                ALL_SKILLS,
            ),
        ),
    ),
    Species.HALF_ORC: SpeciesDefinition(
        Species.HALF_ORC,
        Size.MEDIUM,
        30,
        (SrdLanguageId.COMMON.value, SrdLanguageId.ORC.value),
        fixed_skills=("intimidation",),
        feature_ids=(
            "sense.darkvision.60",
            "species.half_orc.relentless_endurance",
            "species.half_orc.savage_attacks",
        ),
    ),
    Species.HALFLING: SpeciesDefinition(
        Species.HALFLING,
        Size.SMALL,
        25,
        (SrdLanguageId.COMMON.value, SrdLanguageId.HALFLING.value),
        variants=(SpeciesVariant.LIGHTFOOT,),
        capabilities=(OriginCapability.HALFLING_NIMBLENESS,),
        feature_ids=("species.halfling.brave", "species.halfling.lucky"),
    ),
    Species.HUMAN: SpeciesDefinition(
        Species.HUMAN,
        Size.MEDIUM,
        30,
        (SrdLanguageId.COMMON.value,),
        choices=(OriginChoiceDefinition(
            "species.human.additional_language",
            1,
            tuple(value for value in ALL_LANGUAGES if value != SrdLanguageId.COMMON.value),
        ),),
    ),
    Species.TIEFLING: SpeciesDefinition(
        Species.TIEFLING,
        Size.MEDIUM,
        30,
        (SrdLanguageId.COMMON.value, SrdLanguageId.INFERNAL.value),
        feature_ids=(
            "sense.darkvision.60",
            "species.tiefling.fire_resistance",
            "species.tiefling.infernal_legacy",
        ),
    ),
})


SPECIES_VARIANT_DEFINITIONS: Mapping[
    SpeciesVariant,
    SpeciesVariantDefinition,
] = MappingProxyType({
    SpeciesVariant.HILL_DWARF: SpeciesVariantDefinition(
        SpeciesVariant.HILL_DWARF,
        Species.DWARF,
        feature_ids=("species_variant.hill_dwarf.dwarven_toughness",),
    ),
    SpeciesVariant.HIGH_ELF: SpeciesVariantDefinition(
        SpeciesVariant.HIGH_ELF,
        Species.ELF,
        feature_ids=(
            "species_variant.high_elf.weapon_training",
            "species_variant.high_elf.wizard_cantrip",
        ),
        choices=(
            OriginChoiceDefinition(
                "species_variant.high_elf.additional_language",
                1,
                tuple(value for value in ALL_LANGUAGES if value not in {
                    SrdLanguageId.COMMON.value,
                    SrdLanguageId.ELVISH.value,
                }),
            ),
            OriginChoiceDefinition(
                "species_variant.high_elf.wizard_cantrip",
                1,
                ("spell.fire_bolt",),
            ),
        ),
    ),
    SpeciesVariant.ROCK_GNOME: SpeciesVariantDefinition(
        SpeciesVariant.ROCK_GNOME,
        Species.GNOME,
        capabilities=(
            OriginCapability.ARTIFICERS_LORE,
            OriginCapability.TINKER,
        ),
        feature_ids=("species_variant.rock_gnome.tinkers_tools",),
    ),
    SpeciesVariant.LIGHTFOOT: SpeciesVariantDefinition(
        SpeciesVariant.LIGHTFOOT,
        Species.HALFLING,
        capabilities=(OriginCapability.NATURALLY_STEALTHY,),
    ),
})


BACKGROUND_DEFINITIONS: Mapping[Background, BackgroundDefinition] = MappingProxyType({
    Background.ACOLYTE: BackgroundDefinition(
        Background.ACOLYTE,
        fixed_skills=("insight", "religion"),
        capabilities=(OriginCapability.SHELTER_OF_THE_FAITHFUL,),
        feature_ids=("background.acolyte.starting_holdings",),
        choices=(OriginChoiceDefinition(
            "background.acolyte.languages",
            2,
            ALL_LANGUAGES,
        ),),
    ),
    Background.ADVENTURER: BackgroundDefinition(Background.ADVENTURER),
})


DRAGONBORN_ANCESTRY_DEFINITIONS: Mapping[
    str,
    DragonbornAncestryDefinition,
] = MappingProxyType({
    "black": DragonbornAncestryDefinition(DamageType.ACID, "line", "dexterity"),
    "blue": DragonbornAncestryDefinition(DamageType.LIGHTNING, "line", "dexterity"),
    "brass": DragonbornAncestryDefinition(DamageType.FIRE, "line", "dexterity"),
    "bronze": DragonbornAncestryDefinition(DamageType.LIGHTNING, "line", "dexterity"),
    "copper": DragonbornAncestryDefinition(DamageType.ACID, "line", "dexterity"),
    "gold": DragonbornAncestryDefinition(DamageType.FIRE, "cone", "dexterity"),
    "green": DragonbornAncestryDefinition(DamageType.POISON, "cone", "constitution"),
    "red": DragonbornAncestryDefinition(DamageType.FIRE, "cone", "dexterity"),
    "silver": DragonbornAncestryDefinition(DamageType.COLD, "cone", "constitution"),
    "white": DragonbornAncestryDefinition(DamageType.COLD, "cone", "constitution"),
})


def resolve_origin(
    *,
    species: Species,
    species_variant: SpeciesVariant | None,
    background: Background,
    state: AppliedOriginState,
) -> ResolvedOrigin:
    """Validate all selections and derive the complete immutable origin row."""
    species_definition = SPECIES_DEFINITIONS[species]
    variant_definition = (
        None
        if species_variant is None
        else SPECIES_VARIANT_DEFINITIONS[species_variant]
    )
    if variant_definition is not None and variant_definition.parent_species is not species:
        raise ValueError("species variant does not belong to species")
    if species_variant is not None and species_variant not in species_definition.variants:
        raise ValueError("species does not offer the selected variant")

    if tuple(name for name, _ in state.base_ability_scores) != ABILITY_ORDER:
        raise ValueError("base ability scores must contain all six abilities in order")
    if any(not 1 <= score <= 20 for _, score in state.base_ability_scores):
        raise ValueError("base ability scores must be between 1 and 20")
    if tuple(
        sorted(
            state.flexible_ability_bonuses,
            key=lambda row: ABILITY_ORDER.index(row[0]),
        )
    ) != state.flexible_ability_bonuses:
        raise ValueError("flexible ability bonuses must use ability order")
    if sorted(amount for _, amount in state.flexible_ability_bonuses) != [1, 2]:
        raise ValueError("character creation requires one +2 and one +1 bonus")

    background_definition = BACKGROUND_DEFINITIONS[background]
    requirements = (
        *species_definition.choices,
        *(variant_definition.choices if variant_definition is not None else ()),
        *background_definition.choices,
    )
    if tuple(choice.choice_id for choice in state.choices) != tuple(
        requirement.choice_id for requirement in requirements
    ):
        raise ValueError("origin choices must exactly follow authored choice order")
    for choice, requirement in zip(state.choices, requirements):
        if len(choice.values) != requirement.selections:
            raise ValueError(f"origin choice {choice.choice_id} has wrong cardinality")
        unsupported = set(choice.values) - set(requirement.allowed_values)
        if unsupported:
            raise ValueError(
                f"origin choice {choice.choice_id} contains unsupported values: "
                f"{', '.join(sorted(unsupported))}",
            )

    choice_rows = tuple((choice.choice_id, choice.values) for choice in state.choices)
    chosen_languages = tuple(
        value
        for choice_id, values in choice_rows
        if "language" in choice_id
        for value in values
    )
    chosen_skills = tuple(
        value
        for choice_id, values in choice_rows
        if "skill" in choice_id
        for value in values
    )
    chosen_tools = tuple(
        value
        for choice_id, values in choice_rows
        if "tool" in choice_id
        for value in values
    )
    resolved_languages = (
        *species_definition.fixed_languages,
        *(variant_definition.fixed_languages if variant_definition is not None else ()),
        *chosen_languages,
    )
    resolved_skills = (
        *species_definition.fixed_skills,
        *background_definition.fixed_skills,
        *chosen_skills,
    )
    if len(set(resolved_languages)) != len(resolved_languages):
        raise ValueError("origin languages cannot duplicate known languages")
    if len(set(resolved_skills)) != len(resolved_skills):
        raise ValueError("origin skills cannot duplicate existing proficiency")
    if len(set(chosen_tools)) != len(chosen_tools):
        raise ValueError("origin tools cannot duplicate existing proficiency")
    return ResolvedOrigin(
        species=species,
        species_variant=species_variant,
        background=background,
        state=state,
        size=species_definition.size,
        walking_speed_feet=species_definition.walking_speed_feet,
        languages=resolved_languages,
        skills=cast(tuple[SkillName, ...], resolved_skills),
        tools=chosen_tools,
        capabilities=(
            *species_definition.capabilities,
            *(variant_definition.capabilities if variant_definition is not None else ()),
            *background_definition.capabilities,
        ),
        feature_ids=(
            *species_definition.feature_ids,
            *(variant_definition.feature_ids if variant_definition is not None else ()),
            *background_definition.feature_ids,
        ),
        choices=choice_rows,
    )


__all__ = [
    "ABILITY_ORDER",
    "ALL_LANGUAGES",
    "ALL_SKILLS",
    "BACKGROUND_DEFINITIONS",
    "DRACONIC_ANCESTRIES",
    "DRAGONBORN_ANCESTRY_DEFINITIONS",
    "BackgroundDefinition",
    "DragonbornAncestryDefinition",
    "OriginChoiceDefinition",
    "ResolvedOrigin",
    "SPECIES_DEFINITIONS",
    "SPECIES_VARIANT_DEFINITIONS",
    "SpeciesDefinition",
    "SpeciesVariantDefinition",
    "resolve_origin",
]
