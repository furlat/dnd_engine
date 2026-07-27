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
    BackgroundDefinition,
    BuildChoiceRequirement,
    ChoiceRequirementKind,
    ProficiencySubject,
    ProficiencySubjectKind,
    SpeciesDefinition,
    SpeciesVariantDefinition,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
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


_PACK_ID = "content.srd_5_1_cc"
_VERSION = 1
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


def _provenance(
    source_anchor: str,
    *,
    notes: str,
    primary_source_id: str = _SOURCE_ID,
    relation: ContentProvenanceRelation = (
        ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION
    ),
    fidelity: ContentFidelity = ContentFidelity.BLOCKED,
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
    player_capable: bool = False,
    source_tag: str = "srd_5_1",
    provenance: ContentProvenance | None = None,
) -> ContentDeclaration:
    implementation_tag = (
        "player_capable" if player_capable else "implementation_blocked"
    )
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
                    implementation_tag,
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
                "Exact reviewed creator identity and rules summary. Runtime "
                "species/background trait installation remains intentionally "
                "blocked until source-owned origin grant contracts exist."
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


DRAGONBORN_SPECIES_DECLARATION = _declaration(
    ref=_SPECIES_REFS["dragonborn"],
    display_name="Dragonborn",
    description=(
        "A draconic people with a chosen draconic ancestry, an ancestry-shaped "
        "breath weapon, and resistance to its associated damage type."
    ),
    definition=SpeciesDefinition(),
    source_anchor="SRD 5.1 Races: Dragonborn Traits",
    sort_group="species",
    sort_order=10,
)
DWARF_SPECIES_DECLARATION = _declaration(
    ref=_SPECIES_REFS["dwarf"],
    display_name="Dwarf",
    description=(
        "A sturdy people with darkvision, poison resilience, dwarven combat "
        "training, tool training, and stonecunning."
    ),
    definition=SpeciesDefinition(),
    source_anchor="SRD 5.1 Races: Dwarf Traits",
    sort_group="species",
    sort_order=20,
    related_content_refs=(_VARIANT_REFS["dwarf.hill"],),
    dependencies=_variant_edges(_VARIANT_REFS["dwarf.hill"]),
)
ELF_SPECIES_DECLARATION = _declaration(
    ref=_SPECIES_REFS["elf"],
    display_name="Elf",
    description=(
        "A perceptive, long-lived people with darkvision, keen senses, fey "
        "ancestry, and trance."
    ),
    definition=SpeciesDefinition(),
    source_anchor="SRD 5.1 Races: Elf Traits",
    sort_group="species",
    sort_order=30,
    related_content_refs=(_VARIANT_REFS["elf.high"],),
    dependencies=_variant_edges(_VARIANT_REFS["elf.high"]),
)
GNOME_SPECIES_DECLARATION = _declaration(
    ref=_SPECIES_REFS["gnome"],
    display_name="Gnome",
    description=(
        "A small, inventive people with darkvision and Gnome Cunning against "
        "mental magic."
    ),
    definition=SpeciesDefinition(),
    source_anchor="SRD 5.1 Races: Gnome Traits",
    sort_group="species",
    sort_order=40,
    related_content_refs=(_VARIANT_REFS["gnome.rock"],),
    dependencies=_variant_edges(_VARIANT_REFS["gnome.rock"]),
)
HALF_ELF_SPECIES_DECLARATION = _declaration(
    ref=_SPECIES_REFS["half_elf"],
    display_name="Half-Elf",
    description=(
        "A versatile people with darkvision, fey ancestry, two chosen skill "
        "proficiencies, and additional languages."
    ),
    definition=SpeciesDefinition(
        choice_requirements=(
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
)
HALF_ORC_SPECIES_DECLARATION = _declaration(
    ref=_SPECIES_REFS["half_orc"],
    display_name="Half-Orc",
    description=(
        "A powerful people with darkvision, Menacing, Relentless Endurance, "
        "and Savage Attacks."
    ),
    definition=SpeciesDefinition(),
    source_anchor="SRD 5.1 Races: Half-Orc Traits",
    sort_group="species",
    sort_order=60,
)
HALFLING_SPECIES_DECLARATION = _declaration(
    ref=_SPECIES_REFS["halfling"],
    display_name="Halfling",
    description=(
        "A small and nimble people with Lucky, Brave, and Halfling Nimbleness."
    ),
    definition=SpeciesDefinition(),
    source_anchor="SRD 5.1 Races: Halfling Traits",
    sort_group="species",
    sort_order=70,
    related_content_refs=(_VARIANT_REFS["halfling.lightfoot"],),
    dependencies=_variant_edges(_VARIANT_REFS["halfling.lightfoot"]),
)
HUMAN_SPECIES_DECLARATION = _declaration(
    ref=HUMAN_SPECIES_REF,
    display_name="Human",
    description=(
        "An adaptable people. Character creation applies the profile's "
        "flexible +2/+1 ability-score policy independently of species."
    ),
    definition=SpeciesDefinition(),
    source_anchor="SRD 5.1 Races: Human Traits",
    sort_group="species",
    sort_order=80,
    player_capable=True,
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
    definition=SpeciesDefinition(),
    source_anchor="SRD 5.1 Races: Tiefling Traits",
    sort_group="species",
    sort_order=90,
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
    ),
    source_anchor="SRD 5.1 Races: Hill Dwarf",
    sort_group="species_variants.dwarf",
    sort_order=10,
    related_content_refs=(_SPECIES_REFS["dwarf"],),
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
    ),
    source_anchor="SRD 5.1 Races: High Elf",
    sort_group="species_variants.elf",
    sort_order=10,
    related_content_refs=(_SPECIES_REFS["elf"],),
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
    ),
    source_anchor="SRD 5.1 Races: Rock Gnome",
    sort_group="species_variants.gnome",
    sort_order=10,
    related_content_refs=(_SPECIES_REFS["gnome"],),
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
    ),
    source_anchor="SRD 5.1 Races: Lightfoot Halfling",
    sort_group="species_variants.halfling",
    sort_order=10,
    related_content_refs=(_SPECIES_REFS["halfling"],),
)


ACOLYTE_BACKGROUND_DECLARATION = _declaration(
    ref=ACOLYTE_BACKGROUND_REF,
    display_name="Acolyte",
    description=(
        "A life of temple service granting Insight and Religion training, "
        "two languages, religious equipment, and Shelter of the Faithful."
    ),
    definition=BackgroundDefinition(),
    source_anchor="SRD 5.1 Backgrounds: Acolyte",
    sort_group="backgrounds",
    sort_order=10,
)
ADVENTURER_BACKGROUND_DECLARATION = _declaration(
    ref=ADVENTURER_BACKGROUND_REF,
    display_name="Adventurer",
    description=(
        "A mechanically neutral Neurodragon background. It grants no skills, "
        "languages, equipment, features, or other background benefits."
    ),
    definition=BackgroundDefinition(),
    source_anchor="Neurodragon original: neutral adventurer background",
    sort_group="backgrounds",
    sort_order=20,
    player_capable=True,
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
