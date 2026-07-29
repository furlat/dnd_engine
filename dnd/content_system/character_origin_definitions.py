"""Pure SRD 5.1 character-origin definitions.

These declarations expose exact creator identities and family relationships.
They deliberately do not claim that species traits or background benefits are
installed at runtime: the current structural contracts have no source-owned
automatic proficiency, language, speed, sense, or innate-spell grant surface.
"""

from __future__ import annotations

from pydantic import BaseModel

from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import (
    ContentDescriptor,
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.durable_characters import (
    AbilityScoreName,
    BackgroundDefinition,
    BuildChoiceRequirement,
    ChoiceRequirementKind,
    OriginLevelGrant,
    OriginInnateSpellGrant,
    OriginInnateSpellcastingDefinition,
    ProficiencySubject,
    ProficiencySubjectKind,
    SpeciesDefinition,
    SpeciesVariantDefinition,
    SpellcastingSourceId,
)
from dnd.content_system.origin_feature_definitions import (
    ACOLYTE_PROFICIENCIES_REF,
    ACOLYTE_SHELTER_OF_THE_FAITHFUL_REF,
    DRAGONBORN_LANGUAGES_REF,
    DWARF_COMBAT_TRAINING_REF,
    DWARF_DWARVEN_RESILIENCE_REF,
    DWARF_LANGUAGES_REF,
    DWARF_MEDIUM_25_PHYSICAL_REF,
    DWARF_STONECUNNING_REF,
    ELF_FEY_ANCESTRY_REF,
    ELF_KEEN_SENSES_REF,
    ELF_LANGUAGES_REF,
    ELF_TRANCE_REF,
    GNOME_LANGUAGES_REF,
    GNOME_CUNNING_REF,
    HALF_ELF_LANGUAGES_REF,
    HALF_ORC_LANGUAGES_REF,
    HALF_ORC_MENACING_REF,
    HALF_ORC_SAVAGE_ATTACKS_REF,
    HALFLING_LANGUAGES_REF,
    HALFLING_BRAVE_REF,
    HALFLING_NIMBLENESS_REF,
    HIGH_ELF_WEAPON_TRAINING_REF,
    HILL_DWARF_DWARVEN_TOUGHNESS_REF,
    HUMAN_LANGUAGES_REF,
    LIGHTFOOT_NATURALLY_STEALTHY_REF,
    ROCK_GNOME_ARTIFICERS_LORE_REF,
    ROCK_GNOME_TINKER_REF,
    SHARED_DARKVISION_60_REF,
    SHARED_MEDIUM_30_PHYSICAL_REF,
    SHARED_SMALL_25_PHYSICAL_REF,
    TIEFLING_FIRE_RESISTANCE_REF,
    TIEFLING_LANGUAGES_REF,
)
from dnd.content_system.acolyte_starting_holdings import (
    ACOLYTE_STARTING_HOLDINGS_REF,
)
from dnd.content_system.dragonborn_origin_definitions import (
    DRAGONBORN_ANCESTRY_DECLARATIONS,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.origin_support import OriginRuntimeSupport
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.registration import (
    ContentDeclaration,
    ContentDeclarationMode,
    compute_definition_contract_hash,
)
from dnd.core.language_types import SrdLanguageId
from dnd.origins.halfling import HALFLING_LUCKY_REF
from dnd.origins.half_orc import HALF_ORC_RELENTLESS_ENDURANCE_REF
from dnd.content_system.spell_catalog_composition import (
    SPELL_CATALOG_COMPOSITION_ROWS,
)


_PACK_ID = "content.srd_5_1_cc"
_VERSION = 2
_SOURCE_ID = "wotc.srd_5_1_cc"
_NEURODRAGON_PACK_ID = "content.neurodragon"
_NEURODRAGON_SOURCE_ID = "neurodragon.original_b2b3930"


def _typed_ref(
    definition_kind: ContentDefinitionKind,
    content_id: str,
    definition_model: type[BaseModel],
    *,
    pack_id: str = _PACK_ID,
) -> ContentRef:
    return ContentRef(
        pack_id=pack_id,
        definition_kind=definition_kind,
        content_id=content_id,
        content_version=_VERSION,
        definition_contract_hash=compute_definition_contract_hash(
            mode=ContentDeclarationMode.TYPED_DEFINITION,
            definition_kind=definition_kind,
            definition_model=definition_model,
        ),
    )


_SPECIES_REFS = {
    name: _typed_ref(
        ContentDefinitionKind.SPECIES,
        f"species.{name}",
        SpeciesDefinition,
    )
    for name in (
        "dragonborn",
        "dwarf",
        "elf",
        "gnome",
        "half_elf",
        "half_orc",
        "halfling",
        "human",
        "tiefling",
    )
}
_VARIANT_REFS = {
    name: _typed_ref(
        ContentDefinitionKind.SPECIES_VARIANT,
        f"species_variant.{name}",
        SpeciesVariantDefinition,
    )
    for name in (
        "dwarf.hill",
        "elf.high",
        "gnome.rock",
        "halfling.lightfoot",
    )
}
ACOLYTE_BACKGROUND_REF = _typed_ref(
    ContentDefinitionKind.BACKGROUND,
    "background.acolyte",
    BackgroundDefinition,
)
ADVENTURER_BACKGROUND_REF = _typed_ref(
    ContentDefinitionKind.BACKGROUND,
    "background.adventurer",
    BackgroundDefinition,
    pack_id=_NEURODRAGON_PACK_ID,
)
HUMAN_SPECIES_REF = _SPECIES_REFS["human"]

_AVAILABLE_RUNTIME_SUPPORT = OriginRuntimeSupport.available()
_DRAGONBORN_ANCESTRY_REFS = tuple(
    declaration.ref
    for declaration in DRAGONBORN_ANCESTRY_DECLARATIONS
)


def _provenance(
    source_anchor: str,
    *,
    notes: str,
    primary_source_id: str = _SOURCE_ID,
    relation: ContentProvenanceRelation = (
        ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION
    ),
    fidelity: ContentFidelity = ContentFidelity.COMPLETE,
    adapted_from_source_id: str | None = None,
) -> ContentProvenance:
    return ContentProvenance(
        primary_source_id=primary_source_id,
        source_anchor=source_anchor,
        relation=relation,
        fidelity=fidelity,
        review_status=ContentReviewStatus.REVIEWED,
        adapted_from_source_id=adapted_from_source_id,
        notes=notes,
    )


def _declaration(
    *,
    ref: ContentRef,
    display_name: str,
    description: str,
    definition: SpeciesDefinition
    | SpeciesVariantDefinition
    | BackgroundDefinition,
    source_anchor: str,
    sort_group: str,
    sort_order: int,
    related_content_refs: tuple[ContentRef, ...] = (),
    dependencies: tuple[ContentDependency, ...] = (),
    source_tag: str = "srd_5_1",
    provenance: ContentProvenance | None = None,
) -> ContentDeclaration:
    return ContentDeclaration(
        ref=ref,
        mode=ContentDeclarationMode.TYPED_DEFINITION,
        descriptor=ContentDescriptor.from_spec(
            ref,
            ContentDescriptorSpec(
                display_name=display_name,
                description=description,
                tags=(
                    "character_creation",
                    ref.definition_kind.value,
                    source_tag,
                ),
                visibility=ContentVisibility.PUBLIC,
                presentation=ContentPresentation(
                    visual_variant_key=ref.content_id,
                    ui_group=sort_group,
                ),
                ordering=ContentOrdering(
                    sort_group=sort_group,
                    sort_order=sort_order,
                ),
                related_content_refs=related_content_refs,
            ),
        ),
        provenance=provenance
        or _provenance(
            source_anchor,
            notes=(
                "Complete reviewed creator identity with exact source-owned, "
                "reversible structural grants and validated choices."
            ),
        ),
        definition_payload=definition,
        dependencies=dependencies,
    )


def _variant_edges(
    *variant_refs: ContentRef,
) -> tuple[ContentDependency, ...]:
    return tuple(
        ContentDependency(
            relation=ContentDependencyRelation.HAS_SPECIES_VARIANT,
            target_ref=variant_ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Authored SRD species variant offered by this family.",
        )
        for variant_ref in sorted(
            variant_refs,
            key=lambda ref: ref.identity_key,
        )
    )


def _grant_edges(
    *feature_refs: ContentRef,
) -> tuple[ContentDependency, ...]:
    return tuple(
        ContentDependency(
            relation=ContentDependencyRelation.GRANTS_FEATURE,
            target_ref=feature_ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Authored structural feature granted by this origin.",
        )
        for feature_ref in sorted(
            feature_refs,
            key=lambda ref: ref.identity_key,
        )
    )


def _spell_edges(
    *spell_refs: ContentRef,
) -> tuple[ContentDependency, ...]:
    return tuple(
        ContentDependency(
            relation=ContentDependencyRelation.GRANTS_SPELL,
            target_ref=spell_ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Authored innate spell granted by this origin.",
        )
        for spell_ref in sorted(
            spell_refs,
            key=lambda ref: ref.identity_key,
        )
    )


def _level_one(
    *feature_refs: ContentRef,
) -> tuple[OriginLevelGrant, ...]:
    return (
        OriginLevelGrant(
            character_level=1,
            grant_refs=tuple(sorted(
                feature_refs,
                key=lambda ref: ref.identity_key,
            )),
        ),
    )


_ALL_SKILL_SUBJECTS = tuple(
    ProficiencySubject(
        subject_kind=ProficiencySubjectKind.SKILL,
        subject_id=f"skill.{skill}",
    )
    for skill in (
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
)
_ALL_LANGUAGE_SUBJECTS = tuple(
    ProficiencySubject(
        subject_kind=ProficiencySubjectKind.LANGUAGE,
        subject_id=language.value,
    )
    for language in sorted(SrdLanguageId, key=lambda row: row.value)
)
_HIGH_ELF_WIZARD_CANTRIP_REFS = tuple(sorted(
    (
        row.declaration.ref
        for row in SPELL_CATALOG_COMPOSITION_ROWS
        if row.level == 0 and "wizard" in row.metadata.classes
    ),
    key=lambda ref: ref.identity_key,
))
_THAUMATURGY_REF = next(
    row.declaration.ref
    for row in SPELL_CATALOG_COMPOSITION_ROWS
    if row.metadata.catalog_id == "thaumaturgy"
)
_HELLISH_REBUKE_REF = next(
    row.declaration.ref
    for row in SPELL_CATALOG_COMPOSITION_ROWS
    if row.metadata.catalog_id == "hellish_rebuke"
)
_DARKNESS_REF = next(
    row.declaration.ref
    for row in SPELL_CATALOG_COMPOSITION_ROWS
    if row.metadata.catalog_id == "darkness"
)


DRAGONBORN_SPECIES_DECLARATION = _declaration(
    ref=_SPECIES_REFS["dragonborn"],
    display_name="Dragonborn",
    description=(
        "A draconic people with a chosen draconic ancestry, an ancestry-shaped "
        "breath weapon, and resistance to its associated damage type."
    ),
    definition=SpeciesDefinition(
        runtime_support=_AVAILABLE_RUNTIME_SUPPORT,
        level_grants=_level_one(
            SHARED_MEDIUM_30_PHYSICAL_REF,
            DRAGONBORN_LANGUAGES_REF,
        ),
        choice_requirements=(
            BuildChoiceRequirement(
                choice_id="species.dragonborn.draconic_ancestry",
                choice_kind=ChoiceRequirementKind.ORIGIN_TRAIT,
                minimum_selections=1,
                maximum_selections=1,
                allowed_refs=_DRAGONBORN_ANCESTRY_REFS,
            ),
        ),
    ),
    source_anchor="SRD 5.1 Races: Dragonborn Traits",
    sort_group="species",
    sort_order=10,
    related_content_refs=tuple(sorted(
        (
            *_DRAGONBORN_ANCESTRY_REFS,
            DRAGONBORN_LANGUAGES_REF,
            SHARED_MEDIUM_30_PHYSICAL_REF,
        ),
        key=lambda ref: ref.identity_key,
    )),
    dependencies=_grant_edges(
        *_DRAGONBORN_ANCESTRY_REFS,
        DRAGONBORN_LANGUAGES_REF,
        SHARED_MEDIUM_30_PHYSICAL_REF,
    ),
    provenance=_provenance(
        "SRD 5.1 Races: Dragonborn Traits",
        fidelity=ContentFidelity.COMPLETE,
        notes=(
            "Complete source-owned runtime grants for Dragonborn size, speed, "
            "languages, selected ancestry resistance, and Breath Weapon."
        ),
    ),
)
DWARF_SPECIES_DECLARATION = _declaration(
    ref=_SPECIES_REFS["dwarf"],
    display_name="Dwarf",
    description=(
        "A sturdy people with darkvision, poison resilience, dwarven combat "
        "training, tool training, and stonecunning."
    ),
    definition=SpeciesDefinition(
        runtime_support=_AVAILABLE_RUNTIME_SUPPORT,
        level_grants=_level_one(
            DWARF_COMBAT_TRAINING_REF,
            DWARF_DWARVEN_RESILIENCE_REF,
            DWARF_LANGUAGES_REF,
            DWARF_MEDIUM_25_PHYSICAL_REF,
            DWARF_STONECUNNING_REF,
            SHARED_DARKVISION_60_REF,
        ),
        choice_requirements=(
            BuildChoiceRequirement(
                choice_id="species.dwarf.artisans_tool",
                choice_kind=ChoiceRequirementKind.STARTING_PROFICIENCY,
                minimum_selections=1,
                maximum_selections=1,
                allowed_proficiency_subjects=(
                    ProficiencySubject(
                        subject_kind=ProficiencySubjectKind.TOOL,
                        subject_id="tool.artisan.brewers_supplies",
                    ),
                    ProficiencySubject(
                        subject_kind=ProficiencySubjectKind.TOOL,
                        subject_id="tool.artisan.masons_tools",
                    ),
                    ProficiencySubject(
                        subject_kind=ProficiencySubjectKind.TOOL,
                        subject_id="tool.artisan.smiths_tools",
                    ),
                ),
            ),
        ),
    ),
    source_anchor="SRD 5.1 Races: Dwarf Traits",
    sort_group="species",
    sort_order=20,
    related_content_refs=(
        DWARF_COMBAT_TRAINING_REF,
        DWARF_DWARVEN_RESILIENCE_REF,
        DWARF_LANGUAGES_REF,
        DWARF_MEDIUM_25_PHYSICAL_REF,
        DWARF_STONECUNNING_REF,
        SHARED_DARKVISION_60_REF,
        _VARIANT_REFS["dwarf.hill"],
    ),
    dependencies=(
        *_grant_edges(
            DWARF_COMBAT_TRAINING_REF,
            DWARF_DWARVEN_RESILIENCE_REF,
            DWARF_LANGUAGES_REF,
            DWARF_MEDIUM_25_PHYSICAL_REF,
            DWARF_STONECUNNING_REF,
            SHARED_DARKVISION_60_REF,
        ),
        *_variant_edges(_VARIANT_REFS["dwarf.hill"]),
    ),
)
ELF_SPECIES_DECLARATION = _declaration(
    ref=_SPECIES_REFS["elf"],
    display_name="Elf",
    description=(
        "A perceptive, long-lived people with darkvision, keen senses, fey "
        "ancestry, and trance."
    ),
    definition=SpeciesDefinition(
        runtime_support=_AVAILABLE_RUNTIME_SUPPORT,
        level_grants=_level_one(
            ELF_FEY_ANCESTRY_REF,
            ELF_KEEN_SENSES_REF,
            ELF_LANGUAGES_REF,
            ELF_TRANCE_REF,
            SHARED_DARKVISION_60_REF,
            SHARED_MEDIUM_30_PHYSICAL_REF,
        ),
    ),
    source_anchor="SRD 5.1 Races: Elf Traits",
    sort_group="species",
    sort_order=30,
    related_content_refs=(
        ELF_FEY_ANCESTRY_REF,
        ELF_KEEN_SENSES_REF,
        ELF_LANGUAGES_REF,
        ELF_TRANCE_REF,
        SHARED_DARKVISION_60_REF,
        SHARED_MEDIUM_30_PHYSICAL_REF,
        _VARIANT_REFS["elf.high"],
    ),
    dependencies=(
        *_grant_edges(
            ELF_FEY_ANCESTRY_REF,
            ELF_KEEN_SENSES_REF,
            ELF_LANGUAGES_REF,
            ELF_TRANCE_REF,
            SHARED_DARKVISION_60_REF,
            SHARED_MEDIUM_30_PHYSICAL_REF,
        ),
        *_variant_edges(_VARIANT_REFS["elf.high"]),
    ),
)
GNOME_SPECIES_DECLARATION = _declaration(
    ref=_SPECIES_REFS["gnome"],
    display_name="Gnome",
    description=(
        "A small, inventive people with darkvision and Gnome Cunning against "
        "mental magic."
    ),
    definition=SpeciesDefinition(
        runtime_support=_AVAILABLE_RUNTIME_SUPPORT,
        level_grants=_level_one(
            GNOME_CUNNING_REF,
            GNOME_LANGUAGES_REF,
            SHARED_DARKVISION_60_REF,
            SHARED_SMALL_25_PHYSICAL_REF,
        ),
    ),
    source_anchor="SRD 5.1 Races: Gnome Traits",
    sort_group="species",
    sort_order=40,
    related_content_refs=(
        GNOME_CUNNING_REF,
        GNOME_LANGUAGES_REF,
        SHARED_DARKVISION_60_REF,
        SHARED_SMALL_25_PHYSICAL_REF,
        _VARIANT_REFS["gnome.rock"],
    ),
    dependencies=(
        *_grant_edges(
            GNOME_CUNNING_REF,
            GNOME_LANGUAGES_REF,
            SHARED_DARKVISION_60_REF,
            SHARED_SMALL_25_PHYSICAL_REF,
        ),
        *_variant_edges(_VARIANT_REFS["gnome.rock"]),
    ),
)
HALF_ELF_SPECIES_DECLARATION = _declaration(
    ref=_SPECIES_REFS["half_elf"],
    display_name="Half-Elf",
    description=(
        "A versatile people with darkvision, fey ancestry, two chosen skill "
        "proficiencies, and additional languages."
    ),
    definition=SpeciesDefinition(
        runtime_support=_AVAILABLE_RUNTIME_SUPPORT,
        level_grants=_level_one(
            ELF_FEY_ANCESTRY_REF,
            HALF_ELF_LANGUAGES_REF,
            SHARED_DARKVISION_60_REF,
            SHARED_MEDIUM_30_PHYSICAL_REF,
        ),
        choice_requirements=(
            BuildChoiceRequirement(
                choice_id="species.half_elf.additional_language",
                choice_kind=ChoiceRequirementKind.STARTING_PROFICIENCY,
                minimum_selections=1,
                maximum_selections=1,
                allowed_proficiency_subjects=tuple(
                    subject
                    for subject in _ALL_LANGUAGE_SUBJECTS
                    if subject.subject_id
                    not in {
                        SrdLanguageId.COMMON.value,
                        SrdLanguageId.ELVISH.value,
                    }
                ),
            ),
            BuildChoiceRequirement(
                choice_id="species.half_elf.skill_versatility",
                choice_kind=ChoiceRequirementKind.STARTING_PROFICIENCY,
                minimum_selections=2,
                maximum_selections=2,
                allowed_proficiency_subjects=_ALL_SKILL_SUBJECTS,
            ),
        ),
    ),
    source_anchor="SRD 5.1 Races: Half-Elf Traits",
    sort_group="species",
    sort_order=50,
    related_content_refs=(
        ELF_FEY_ANCESTRY_REF,
        HALF_ELF_LANGUAGES_REF,
        SHARED_DARKVISION_60_REF,
        SHARED_MEDIUM_30_PHYSICAL_REF,
    ),
    dependencies=_grant_edges(
        ELF_FEY_ANCESTRY_REF,
        HALF_ELF_LANGUAGES_REF,
        SHARED_DARKVISION_60_REF,
        SHARED_MEDIUM_30_PHYSICAL_REF,
    ),
)
HALF_ORC_SPECIES_DECLARATION = _declaration(
    ref=_SPECIES_REFS["half_orc"],
    display_name="Half-Orc",
    description=(
        "A powerful people with darkvision, Menacing, Relentless Endurance, "
        "and Savage Attacks."
    ),
    definition=SpeciesDefinition(
        runtime_support=_AVAILABLE_RUNTIME_SUPPORT,
        level_grants=_level_one(
            HALF_ORC_LANGUAGES_REF,
            HALF_ORC_MENACING_REF,
            HALF_ORC_RELENTLESS_ENDURANCE_REF,
            HALF_ORC_SAVAGE_ATTACKS_REF,
            SHARED_DARKVISION_60_REF,
            SHARED_MEDIUM_30_PHYSICAL_REF,
        ),
    ),
    source_anchor="SRD 5.1 Races: Half-Orc Traits",
    sort_group="species",
    sort_order=60,
    related_content_refs=(
        HALF_ORC_LANGUAGES_REF,
        HALF_ORC_MENACING_REF,
        HALF_ORC_RELENTLESS_ENDURANCE_REF,
        HALF_ORC_SAVAGE_ATTACKS_REF,
        SHARED_DARKVISION_60_REF,
        SHARED_MEDIUM_30_PHYSICAL_REF,
    ),
    dependencies=_grant_edges(
        HALF_ORC_LANGUAGES_REF,
        HALF_ORC_MENACING_REF,
        HALF_ORC_RELENTLESS_ENDURANCE_REF,
        HALF_ORC_SAVAGE_ATTACKS_REF,
        SHARED_DARKVISION_60_REF,
        SHARED_MEDIUM_30_PHYSICAL_REF,
    ),
)
HALFLING_SPECIES_DECLARATION = _declaration(
    ref=_SPECIES_REFS["halfling"],
    display_name="Halfling",
    description=(
        "A small and nimble people with Lucky, Brave, and Halfling Nimbleness."
    ),
    definition=SpeciesDefinition(
        runtime_support=_AVAILABLE_RUNTIME_SUPPORT,
        level_grants=_level_one(
            HALFLING_BRAVE_REF,
            HALFLING_LANGUAGES_REF,
            HALFLING_LUCKY_REF,
            HALFLING_NIMBLENESS_REF,
            SHARED_SMALL_25_PHYSICAL_REF,
        ),
    ),
    source_anchor="SRD 5.1 Races: Halfling Traits",
    sort_group="species",
    sort_order=70,
    related_content_refs=(
        HALFLING_BRAVE_REF,
        HALFLING_LANGUAGES_REF,
        HALFLING_LUCKY_REF,
        HALFLING_NIMBLENESS_REF,
        SHARED_SMALL_25_PHYSICAL_REF,
        _VARIANT_REFS["halfling.lightfoot"],
    ),
    dependencies=(
        *_grant_edges(
            HALFLING_BRAVE_REF,
            HALFLING_LANGUAGES_REF,
            HALFLING_LUCKY_REF,
            HALFLING_NIMBLENESS_REF,
            SHARED_SMALL_25_PHYSICAL_REF,
        ),
        *_variant_edges(_VARIANT_REFS["halfling.lightfoot"]),
    ),
)
HUMAN_SPECIES_DECLARATION = _declaration(
    ref=HUMAN_SPECIES_REF,
    display_name="Human",
    description=(
        "An adaptable people. Character creation applies the profile's "
        "flexible +2/+1 ability-score policy independently of species."
    ),
    definition=SpeciesDefinition(
        runtime_support=_AVAILABLE_RUNTIME_SUPPORT,
        level_grants=_level_one(
            HUMAN_LANGUAGES_REF,
            SHARED_MEDIUM_30_PHYSICAL_REF,
        ),
        choice_requirements=(
            BuildChoiceRequirement(
                choice_id="species.human.additional_language",
                choice_kind=ChoiceRequirementKind.STARTING_PROFICIENCY,
                minimum_selections=1,
                maximum_selections=1,
                allowed_proficiency_subjects=tuple(
                    subject
                    for subject in _ALL_LANGUAGE_SUBJECTS
                    if subject.subject_id != SrdLanguageId.COMMON.value
                ),
            ),
        ),
    ),
    source_anchor="SRD 5.1 Races: Human Traits",
    sort_group="species",
    sort_order=80,
    related_content_refs=(
        HUMAN_LANGUAGES_REF,
        SHARED_MEDIUM_30_PHYSICAL_REF,
    ),
    dependencies=_grant_edges(
        HUMAN_LANGUAGES_REF,
        SHARED_MEDIUM_30_PHYSICAL_REF,
    ),
    provenance=_provenance(
        "BG3-compatible character creation: flexible ability bonuses",
        relation=ContentProvenanceRelation.COMPATIBLE_ADAPTATION,
        fidelity=ContentFidelity.COMPLETE,
        adapted_from_source_id=_SOURCE_ID,
        notes=(
            "Complete for the selected character-creation rules: Human adds "
            "no hidden species grants, while the profile-owned flexible +2/+1 "
            "selection supplies the intended BG3-compatible ability bonuses."
        ),
    ),
)
TIEFLING_SPECIES_DECLARATION = _declaration(
    ref=_SPECIES_REFS["tiefling"],
    display_name="Tiefling",
    description=(
        "An infernal-blooded people with darkvision, fire resistance, and a "
        "level-based Infernal Legacy."
    ),
    definition=SpeciesDefinition(
        runtime_support=_AVAILABLE_RUNTIME_SUPPORT,
        level_grants=_level_one(
            SHARED_DARKVISION_60_REF,
            SHARED_MEDIUM_30_PHYSICAL_REF,
            TIEFLING_FIRE_RESISTANCE_REF,
            TIEFLING_LANGUAGES_REF,
        ),
        innate_spellcasting=(
            OriginInnateSpellcastingDefinition(
                source_id=SpellcastingSourceId(
                    value="species.tiefling.infernal_legacy",
                ),
                ability=AbilityScoreName.CHARISMA,
                grants=(
                    OriginInnateSpellGrant(
                        grant_id="tiefling.infernal_legacy.darkness",
                        unlock_character_level=5,
                        spell_ref=_DARKNESS_REF,
                        fixed_cast_rank=2,
                        uses_per_long_rest=1,
                    ),
                    OriginInnateSpellGrant(
                        grant_id="tiefling.infernal_legacy.hellish_rebuke",
                        unlock_character_level=3,
                        spell_ref=_HELLISH_REBUKE_REF,
                        fixed_cast_rank=2,
                        uses_per_long_rest=1,
                    ),
                    OriginInnateSpellGrant(
                        grant_id="tiefling.infernal_legacy.thaumaturgy",
                        unlock_character_level=1,
                        spell_ref=_THAUMATURGY_REF,
                        fixed_cast_rank=0,
                        uses_per_long_rest=None,
                    ),
                ),
            ),
        ),
    ),
    source_anchor="SRD 5.1 Races: Tiefling Traits",
    sort_group="species",
    sort_order=90,
    related_content_refs=(
        SHARED_DARKVISION_60_REF,
        SHARED_MEDIUM_30_PHYSICAL_REF,
        TIEFLING_FIRE_RESISTANCE_REF,
        TIEFLING_LANGUAGES_REF,
        _DARKNESS_REF,
        _HELLISH_REBUKE_REF,
        _THAUMATURGY_REF,
    ),
    dependencies=(
        *_grant_edges(
            SHARED_DARKVISION_60_REF,
            SHARED_MEDIUM_30_PHYSICAL_REF,
            TIEFLING_FIRE_RESISTANCE_REF,
            TIEFLING_LANGUAGES_REF,
        ),
        *_spell_edges(
            _DARKNESS_REF,
            _HELLISH_REBUKE_REF,
            _THAUMATURGY_REF,
        ),
    ),
)


HILL_DWARF_VARIANT_DECLARATION = _declaration(
    ref=_VARIANT_REFS["dwarf.hill"],
    display_name="Hill Dwarf",
    description=(
        "A Dwarf variant with Dwarven Toughness, increasing maximum hit "
        "points as character level rises."
    ),
    definition=SpeciesVariantDefinition(
        parent_species_ref=_SPECIES_REFS["dwarf"],
        runtime_support=_AVAILABLE_RUNTIME_SUPPORT,
        level_grants=_level_one(
            HILL_DWARF_DWARVEN_TOUGHNESS_REF,
        ),
    ),
    source_anchor="SRD 5.1 Races: Hill Dwarf",
    sort_group="species_variants.dwarf",
    sort_order=10,
    related_content_refs=(
        HILL_DWARF_DWARVEN_TOUGHNESS_REF,
        _SPECIES_REFS["dwarf"],
    ),
    dependencies=_grant_edges(HILL_DWARF_DWARVEN_TOUGHNESS_REF),
)
HIGH_ELF_VARIANT_DECLARATION = _declaration(
    ref=_VARIANT_REFS["elf.high"],
    display_name="High Elf",
    description=(
        "An Elf variant with elf weapon training, one wizard cantrip, and one "
        "additional language."
    ),
    definition=SpeciesVariantDefinition(
        parent_species_ref=_SPECIES_REFS["elf"],
        runtime_support=_AVAILABLE_RUNTIME_SUPPORT,
        level_grants=_level_one(
            HIGH_ELF_WEAPON_TRAINING_REF,
        ),
        choice_requirements=(
            BuildChoiceRequirement(
                choice_id="species_variant.high_elf.additional_language",
                choice_kind=ChoiceRequirementKind.STARTING_PROFICIENCY,
                minimum_selections=1,
                maximum_selections=1,
                allowed_proficiency_subjects=tuple(
                    subject
                    for subject in _ALL_LANGUAGE_SUBJECTS
                    if subject.subject_id
                    not in {
                        SrdLanguageId.COMMON.value,
                        SrdLanguageId.ELVISH.value,
                    }
                ),
            ),
            BuildChoiceRequirement(
                choice_id="species_variant.high_elf.wizard_cantrip",
                choice_kind=ChoiceRequirementKind.CANTRIP,
                minimum_selections=1,
                maximum_selections=1,
                allowed_refs=_HIGH_ELF_WIZARD_CANTRIP_REFS,
            ),
        ),
        innate_spellcasting=(
            OriginInnateSpellcastingDefinition(
                source_id=SpellcastingSourceId(
                    value="species_variant.high_elf.innate_spellcasting",
                ),
                ability=AbilityScoreName.INTELLIGENCE,
                grants=(
                    OriginInnateSpellGrant(
                        grant_id="high_elf.wizard_cantrip",
                        unlock_character_level=1,
                        choice_id=(
                            "species_variant.high_elf.wizard_cantrip"
                        ),
                        allowed_spell_refs=_HIGH_ELF_WIZARD_CANTRIP_REFS,
                        fixed_cast_rank=0,
                        uses_per_long_rest=None,
                    ),
                ),
            ),
        ),
    ),
    source_anchor="SRD 5.1 Races: High Elf",
    sort_group="species_variants.elf",
    sort_order=10,
    related_content_refs=tuple(sorted(
        (
            _SPECIES_REFS["elf"],
            HIGH_ELF_WEAPON_TRAINING_REF,
            *_HIGH_ELF_WIZARD_CANTRIP_REFS,
        ),
        key=lambda ref: ref.identity_key,
    )),
    dependencies=(
        *_grant_edges(HIGH_ELF_WEAPON_TRAINING_REF),
        *_spell_edges(*_HIGH_ELF_WIZARD_CANTRIP_REFS),
    ),
)
ROCK_GNOME_VARIANT_DECLARATION = _declaration(
    ref=_VARIANT_REFS["gnome.rock"],
    display_name="Rock Gnome",
    description=(
        "A Gnome variant with Artificer's Lore and the ability to create "
        "simple clockwork devices."
    ),
    definition=SpeciesVariantDefinition(
        parent_species_ref=_SPECIES_REFS["gnome"],
        runtime_support=_AVAILABLE_RUNTIME_SUPPORT,
        level_grants=_level_one(
            ROCK_GNOME_ARTIFICERS_LORE_REF,
            ROCK_GNOME_TINKER_REF,
        ),
    ),
    source_anchor="SRD 5.1 Races: Rock Gnome",
    sort_group="species_variants.gnome",
    sort_order=10,
    related_content_refs=(
        ROCK_GNOME_ARTIFICERS_LORE_REF,
        ROCK_GNOME_TINKER_REF,
        _SPECIES_REFS["gnome"],
    ),
    dependencies=_grant_edges(
        ROCK_GNOME_ARTIFICERS_LORE_REF,
        ROCK_GNOME_TINKER_REF,
    ),
)
LIGHTFOOT_HALFLING_VARIANT_DECLARATION = _declaration(
    ref=_VARIANT_REFS["halfling.lightfoot"],
    display_name="Lightfoot Halfling",
    description=(
        "A Halfling variant able to hide behind larger creatures through "
        "Naturally Stealthy."
    ),
    definition=SpeciesVariantDefinition(
        parent_species_ref=_SPECIES_REFS["halfling"],
        runtime_support=_AVAILABLE_RUNTIME_SUPPORT,
        level_grants=_level_one(
            LIGHTFOOT_NATURALLY_STEALTHY_REF,
        ),
    ),
    source_anchor="SRD 5.1 Races: Lightfoot Halfling",
    sort_group="species_variants.halfling",
    sort_order=10,
    related_content_refs=(
        LIGHTFOOT_NATURALLY_STEALTHY_REF,
        _SPECIES_REFS["halfling"],
    ),
    dependencies=_grant_edges(LIGHTFOOT_NATURALLY_STEALTHY_REF),
)


ACOLYTE_BACKGROUND_DECLARATION = _declaration(
    ref=ACOLYTE_BACKGROUND_REF,
    display_name="Acolyte",
    description=(
        "A life of temple service granting Insight and Religion training, "
        "two languages, religious equipment, and Shelter of the Faithful."
    ),
    definition=BackgroundDefinition(
        runtime_support=_AVAILABLE_RUNTIME_SUPPORT,
        automatic_grant_refs=tuple(sorted(
            (
                ACOLYTE_PROFICIENCIES_REF,
                ACOLYTE_SHELTER_OF_THE_FAITHFUL_REF,
            ),
            key=lambda ref: ref.identity_key,
        )),
        starting_holdings_package_ref=ACOLYTE_STARTING_HOLDINGS_REF,
        choice_requirements=(
            BuildChoiceRequirement(
                choice_id="background.acolyte.languages",
                choice_kind=ChoiceRequirementKind.STARTING_PROFICIENCY,
                minimum_selections=2,
                maximum_selections=2,
                allowed_proficiency_subjects=_ALL_LANGUAGE_SUBJECTS,
            ),
        ),
    ),
    source_anchor="SRD 5.1 Backgrounds: Acolyte",
    sort_group="backgrounds",
    sort_order=10,
    related_content_refs=(
        ACOLYTE_PROFICIENCIES_REF,
        ACOLYTE_SHELTER_OF_THE_FAITHFUL_REF,
        ACOLYTE_STARTING_HOLDINGS_REF,
    ),
    dependencies=(
        *_grant_edges(
            ACOLYTE_PROFICIENCIES_REF,
            ACOLYTE_SHELTER_OF_THE_FAITHFUL_REF,
        ),
        ContentDependency(
            relation=ContentDependencyRelation.OFFERS_STARTING_EQUIPMENT,
            target_ref=ACOLYTE_STARTING_HOLDINGS_REF,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes=(
                "Acolyte grants one exact background starting-possession "
                "package."
            ),
        ),
    ),
    provenance=_provenance(
        "SRD 5.1 Backgrounds: Acolyte",
        fidelity=ContentFidelity.PARTIAL,
        notes=(
            "Skills, two chosen languages, Shelter of the Faithful, and every "
            "durable item possession are installed through exact source-owned "
            "facts. The SRD's 15 gp remains intentionally unclaimed until the "
            "engine owns canonical durable currency."
        ),
    ),
)
ADVENTURER_BACKGROUND_DECLARATION = _declaration(
    ref=ADVENTURER_BACKGROUND_REF,
    display_name="Adventurer",
    description=(
        "A mechanically neutral Neurodragon background. It grants no skills, "
        "languages, equipment, features, or other background benefits."
    ),
    definition=BackgroundDefinition(
        runtime_support=_AVAILABLE_RUNTIME_SUPPORT,
    ),
    source_anchor="Neurodragon original: neutral adventurer background",
    sort_group="backgrounds",
    sort_order=20,
    source_tag="neurodragon_original",
    provenance=_provenance(
        "Neurodragon original: neutral adventurer background",
        primary_source_id=_NEURODRAGON_SOURCE_ID,
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        notes=(
            "Complete by definition: this neutral background intentionally "
            "owns no mechanical grants."
        ),
    ),
)


SRD_CHARACTER_ORIGIN_DECLARATIONS: tuple[ContentDeclaration, ...] = (
    ACOLYTE_BACKGROUND_DECLARATION,
    DRAGONBORN_SPECIES_DECLARATION,
    DWARF_SPECIES_DECLARATION,
    ELF_SPECIES_DECLARATION,
    GNOME_SPECIES_DECLARATION,
    HALF_ELF_SPECIES_DECLARATION,
    HALF_ORC_SPECIES_DECLARATION,
    HALFLING_SPECIES_DECLARATION,
    HUMAN_SPECIES_DECLARATION,
    TIEFLING_SPECIES_DECLARATION,
    HILL_DWARF_VARIANT_DECLARATION,
    HIGH_ELF_VARIANT_DECLARATION,
    ROCK_GNOME_VARIANT_DECLARATION,
    LIGHTFOOT_HALFLING_VARIANT_DECLARATION,
)
NEURODRAGON_CHARACTER_ORIGIN_DECLARATIONS: tuple[
    ContentDeclaration,
    ...,
] = (ADVENTURER_BACKGROUND_DECLARATION,)


__all__ = [
    "ACOLYTE_BACKGROUND_DECLARATION",
    "ACOLYTE_BACKGROUND_REF",
    "ADVENTURER_BACKGROUND_DECLARATION",
    "ADVENTURER_BACKGROUND_REF",
    "HUMAN_SPECIES_DECLARATION",
    "HUMAN_SPECIES_REF",
    "NEURODRAGON_CHARACTER_ORIGIN_DECLARATIONS",
    "SRD_CHARACTER_ORIGIN_DECLARATIONS",
]
