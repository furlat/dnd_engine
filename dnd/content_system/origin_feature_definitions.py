"""Pure typed declarations for passive SRD 5.1 character-origin features."""

from __future__ import annotations

from dnd.core.content.descriptors import (
    ContentDescriptor,
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.durable_characters import (
    AbilityScoreName,
    ProficiencySubject,
    ProficiencySubjectKind,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.origin_features import (
    OriginCapability,
    OriginSavingThrowAdvantageRule,
    OriginStructuralFeatureDefinition,
)
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
from dnd.core.creature_types import DamageType, Size
from dnd.core.saving_throw_types import SavingThrowEffectTag
from dnd.types.senses import SenseMode, SensesType
from dnd.items.weapons import (
    BATTLEAXE_REF,
    HANDAXE_REF,
    LIGHT_HAMMER_REF,
    LONGBOW_REF,
    LONGSWORD_REF,
    SHORTBOW_REF,
    SHORTSWORD_REF,
    WARHAMMER_REF,
)


_PACK_ID = "content.srd_5_1_cc"
_SOURCE_ID = "wotc.srd_5_1_cc"
_NEURODRAGON_SOURCE_ID = "neurodragon.original_b2b3930"
_VERSION = 1
_DEFINITION_KIND = ContentDefinitionKind.TRAIT
_CONTRACT_HASH = compute_definition_contract_hash(
    mode=ContentDeclarationMode.TYPED_DEFINITION,
    definition_kind=_DEFINITION_KIND,
    definition_model=OriginStructuralFeatureDefinition,
)
_PASSIVE_TAGS = (
    "character_creation",
    "origin_feature",
    "passive",
    "srd_5_1",
)


def _ref(content_id: str) -> ContentRef:
    return ContentRef(
        pack_id=_PACK_ID,
        definition_kind=_DEFINITION_KIND,
        content_id=content_id,
        content_version=_VERSION,
        definition_contract_hash=_CONTRACT_HASH,
    )


def _provenance(
    source_anchor: str,
    *,
    primary_source_id: str = _SOURCE_ID,
    relation: ContentProvenanceRelation = (
        ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION
    ),
    adapted_from_source_id: str | None = None,
    fidelity: ContentFidelity = ContentFidelity.COMPLETE,
    notes: str = (
        "Complete typed data for this passive structural contribution. "
        "Runtime ownership belongs to the general source-owned character "
        "composition applier."
    ),
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
    content_id: str,
    display_name: str,
    description: str,
    source_anchor: str,
    sort_order: int,
    definition: OriginStructuralFeatureDefinition,
    fidelity: ContentFidelity = ContentFidelity.COMPLETE,
    provenance_notes: str | None = None,
    primary_source_id: str = _SOURCE_ID,
    relation: ContentProvenanceRelation = (
        ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION
    ),
    adapted_from_source_id: str | None = None,
) -> ContentDeclaration:
    ref = _ref(content_id)
    return ContentDeclaration(
        ref=ref,
        mode=ContentDeclarationMode.TYPED_DEFINITION,
        descriptor=ContentDescriptor.from_spec(
            ref,
            ContentDescriptorSpec(
                display_name=display_name,
                description=description,
                tags=_PASSIVE_TAGS,
                visibility=ContentVisibility.PUBLIC,
                presentation=ContentPresentation(
                    visual_variant_key=content_id,
                    ui_group="origin_features.passive",
                ),
                ordering=ContentOrdering(
                    sort_group="origin_features.passive",
                    sort_order=sort_order,
                ),
            ),
        ),
        provenance=_provenance(
            source_anchor,
            primary_source_id=primary_source_id,
            relation=relation,
            adapted_from_source_id=adapted_from_source_id,
            fidelity=fidelity,
            notes=(
                provenance_notes
                if provenance_notes is not None
                else (
                    "Complete typed data for this passive structural "
                    "contribution. Runtime ownership belongs to the general "
                    "source-owned character composition applier."
                )
            ),
        ),
        definition_payload=definition,
    )


def _subject(
    kind: ProficiencySubjectKind,
    subject_id: str,
) -> ProficiencySubject:
    return ProficiencySubject(
        subject_kind=kind,
        subject_id=subject_id,
    )


def _language_subjects(
    *language_ids: SrdLanguageId,
) -> tuple[ProficiencySubject, ...]:
    return tuple(
        _subject(ProficiencySubjectKind.LANGUAGE, language_id.value)
        for language_id in sorted(language_ids, key=lambda row: row.value)
    )


def _weapon_subject(ref: ContentRef) -> ProficiencySubject:
    return ProficiencySubject(
        subject_kind=ProficiencySubjectKind.WEAPON,
        content_ref=ref,
    )


SHARED_MEDIUM_30_PHYSICAL_DECLARATION = _declaration(
    content_id="trait.origin.shared.physical.medium_30",
    display_name="Medium, 30-Foot Speed",
    description="Medium physical size and a 30-foot walking speed.",
    source_anchor="SRD 5.1 Races: Size and Speed",
    sort_order=10,
    definition=OriginStructuralFeatureDefinition(
        size=Size.MEDIUM,
        walking_speed_feet=30,
    ),
)
SHARED_MEDIUM_30_PHYSICAL_REF = SHARED_MEDIUM_30_PHYSICAL_DECLARATION.ref

SHARED_SMALL_25_PHYSICAL_DECLARATION = _declaration(
    content_id="trait.origin.shared.physical.small_25",
    display_name="Small, 25-Foot Speed",
    description=(
        "Small physical size and an explicitly authored 25-foot walking "
        "speed. Mechanical size does not implicitly determine speed."
    ),
    source_anchor="BG3-compatible character creation: short ancestry speed",
    sort_order=20,
    definition=OriginStructuralFeatureDefinition(
        size=Size.SMALL,
        walking_speed_feet=25,
    ),
    fidelity=ContentFidelity.COMPLETE,
    primary_source_id=_NEURODRAGON_SOURCE_ID,
    relation=ContentProvenanceRelation.COMPATIBLE_ADAPTATION,
    adapted_from_source_id=_SOURCE_ID,
    provenance_notes=(
        "Compatible BG3 ruleset adaptation: Gnome and Halfling origins grant "
        "25-foot speed explicitly. Size and speed remain independent facts."
    ),
)
SHARED_SMALL_25_PHYSICAL_REF = SHARED_SMALL_25_PHYSICAL_DECLARATION.ref

DWARF_MEDIUM_25_PHYSICAL_DECLARATION = _declaration(
    content_id="trait.origin.dwarf.physical.medium_25",
    display_name="Dwarf Size and Speed",
    description=(
        "Medium physical size and a 25-foot walking speed; heavy armor does "
        "not reduce that authored speed."
    ),
    source_anchor="SRD 5.1 Races: Dwarf Traits — Size and Speed",
    sort_order=30,
    definition=OriginStructuralFeatureDefinition(
        size=Size.MEDIUM,
        walking_speed_feet=25,
    ),
)
DWARF_MEDIUM_25_PHYSICAL_REF = DWARF_MEDIUM_25_PHYSICAL_DECLARATION.ref

SHARED_DARKVISION_60_DECLARATION = _declaration(
    content_id="trait.origin.shared.darkvision_60",
    display_name="Darkvision",
    description="Darkvision to a range of 60 feet.",
    source_anchor="SRD 5.1 Races: Darkvision",
    sort_order=40,
    definition=OriginStructuralFeatureDefinition(
        sense_modes=(
            SenseMode(
                sense_type=SensesType.DARKVISION,
                range_feet=60,
            ),
        ),
    ),
)
SHARED_DARKVISION_60_REF = SHARED_DARKVISION_60_DECLARATION.ref


DRAGONBORN_LANGUAGES_DECLARATION = _declaration(
    content_id="trait.origin.species.dragonborn.languages",
    display_name="Dragonborn Languages",
    description="Knowledge of Common and Draconic.",
    source_anchor="SRD 5.1 Races: Dragonborn Traits — Languages",
    sort_order=100,
    definition=OriginStructuralFeatureDefinition(
        automatic_proficiencies=_language_subjects(
            SrdLanguageId.COMMON,
            SrdLanguageId.DRACONIC,
        ),
    ),
)
DRAGONBORN_LANGUAGES_REF = DRAGONBORN_LANGUAGES_DECLARATION.ref

DWARF_LANGUAGES_DECLARATION = _declaration(
    content_id="trait.origin.species.dwarf.languages",
    display_name="Dwarf Languages",
    description="Knowledge of Common and Dwarvish.",
    source_anchor="SRD 5.1 Races: Dwarf Traits — Languages",
    sort_order=110,
    definition=OriginStructuralFeatureDefinition(
        automatic_proficiencies=_language_subjects(
            SrdLanguageId.COMMON,
            SrdLanguageId.DWARVISH,
        ),
    ),
)
DWARF_LANGUAGES_REF = DWARF_LANGUAGES_DECLARATION.ref

ELF_LANGUAGES_DECLARATION = _declaration(
    content_id="trait.origin.species.elf.languages",
    display_name="Elf Languages",
    description="Knowledge of Common and Elvish.",
    source_anchor="SRD 5.1 Races: Elf Traits — Languages",
    sort_order=120,
    definition=OriginStructuralFeatureDefinition(
        automatic_proficiencies=_language_subjects(
            SrdLanguageId.COMMON,
            SrdLanguageId.ELVISH,
        ),
    ),
)
ELF_LANGUAGES_REF = ELF_LANGUAGES_DECLARATION.ref

GNOME_LANGUAGES_DECLARATION = _declaration(
    content_id="trait.origin.species.gnome.languages",
    display_name="Gnome Languages",
    description="Knowledge of Common and Gnomish.",
    source_anchor="SRD 5.1 Races: Gnome Traits — Languages",
    sort_order=130,
    definition=OriginStructuralFeatureDefinition(
        automatic_proficiencies=_language_subjects(
            SrdLanguageId.COMMON,
            SrdLanguageId.GNOMISH,
        ),
    ),
)
GNOME_LANGUAGES_REF = GNOME_LANGUAGES_DECLARATION.ref

HALF_ELF_LANGUAGES_DECLARATION = _declaration(
    content_id="trait.origin.species.half_elf.languages",
    display_name="Half-Elf Fixed Languages",
    description=(
        "Knowledge of Common and Elvish. The additional chosen language is "
        "authored separately as an immutable origin choice."
    ),
    source_anchor="SRD 5.1 Races: Half-Elf Traits — Languages",
    sort_order=140,
    definition=OriginStructuralFeatureDefinition(
        automatic_proficiencies=_language_subjects(
            SrdLanguageId.COMMON,
            SrdLanguageId.ELVISH,
        ),
    ),
)
HALF_ELF_LANGUAGES_REF = HALF_ELF_LANGUAGES_DECLARATION.ref

HALF_ORC_LANGUAGES_DECLARATION = _declaration(
    content_id="trait.origin.species.half_orc.languages",
    display_name="Half-Orc Languages",
    description="Knowledge of Common and Orc.",
    source_anchor="SRD 5.1 Races: Half-Orc Traits — Languages",
    sort_order=150,
    definition=OriginStructuralFeatureDefinition(
        automatic_proficiencies=_language_subjects(
            SrdLanguageId.COMMON,
            SrdLanguageId.ORC,
        ),
    ),
)
HALF_ORC_LANGUAGES_REF = HALF_ORC_LANGUAGES_DECLARATION.ref

HALFLING_LANGUAGES_DECLARATION = _declaration(
    content_id="trait.origin.species.halfling.languages",
    display_name="Halfling Languages",
    description="Knowledge of Common and Halfling.",
    source_anchor="SRD 5.1 Races: Halfling Traits — Languages",
    sort_order=160,
    definition=OriginStructuralFeatureDefinition(
        automatic_proficiencies=_language_subjects(
            SrdLanguageId.COMMON,
            SrdLanguageId.HALFLING,
        ),
    ),
)
HALFLING_LANGUAGES_REF = HALFLING_LANGUAGES_DECLARATION.ref

HUMAN_LANGUAGES_DECLARATION = _declaration(
    content_id="trait.origin.species.human.languages",
    display_name="Human Fixed Language",
    description=(
        "Knowledge of Common. The additional chosen language is authored "
        "separately as an immutable origin choice."
    ),
    source_anchor="SRD 5.1 Races: Human Traits — Languages",
    sort_order=170,
    definition=OriginStructuralFeatureDefinition(
        automatic_proficiencies=_language_subjects(
            SrdLanguageId.COMMON,
        ),
    ),
)
HUMAN_LANGUAGES_REF = HUMAN_LANGUAGES_DECLARATION.ref

TIEFLING_LANGUAGES_DECLARATION = _declaration(
    content_id="trait.origin.species.tiefling.languages",
    display_name="Tiefling Languages",
    description="Knowledge of Common and Infernal.",
    source_anchor="SRD 5.1 Races: Tiefling Traits — Languages",
    sort_order=180,
    definition=OriginStructuralFeatureDefinition(
        automatic_proficiencies=_language_subjects(
            SrdLanguageId.COMMON,
            SrdLanguageId.INFERNAL,
        ),
    ),
)
TIEFLING_LANGUAGES_REF = TIEFLING_LANGUAGES_DECLARATION.ref


ELF_KEEN_SENSES_DECLARATION = _declaration(
    content_id="trait.origin.elf.keen_senses",
    display_name="Keen Senses",
    description="Proficiency in the Perception skill.",
    source_anchor="SRD 5.1 Races: Elf Traits — Keen Senses",
    sort_order=200,
    definition=OriginStructuralFeatureDefinition(
        automatic_proficiencies=(
            _subject(ProficiencySubjectKind.SKILL, "skill.perception"),
        ),
    ),
)
ELF_KEEN_SENSES_REF = ELF_KEEN_SENSES_DECLARATION.ref

ELF_TRANCE_DECLARATION = _declaration(
    content_id="trait.origin.elf.trance",
    display_name="Trance",
    description="The exact durable capability to complete an elven trance.",
    source_anchor="SRD 5.1 Races: Elf Traits — Trance",
    sort_order=210,
    definition=OriginStructuralFeatureDefinition(
        capabilities=(OriginCapability.TRANCE,),
    ),
)
ELF_TRANCE_REF = ELF_TRANCE_DECLARATION.ref

HALF_ORC_MENACING_DECLARATION = _declaration(
    content_id="trait.origin.half_orc.menacing",
    display_name="Menacing",
    description="Proficiency in the Intimidation skill.",
    source_anchor="SRD 5.1 Races: Half-Orc Traits — Menacing",
    sort_order=220,
    definition=OriginStructuralFeatureDefinition(
        automatic_proficiencies=(
            _subject(ProficiencySubjectKind.SKILL, "skill.intimidation"),
        ),
    ),
)
HALF_ORC_MENACING_REF = HALF_ORC_MENACING_DECLARATION.ref

HALF_ORC_SAVAGE_ATTACKS_DECLARATION = _declaration(
    content_id="trait.origin.half_orc.savage_attacks",
    display_name="Savage Attacks",
    description=(
        "Roll one additional weapon damage die on a critical hit with a "
        "melee weapon."
    ),
    source_anchor="SRD 5.1 Races: Half-Orc Traits — Savage Attacks",
    sort_order=225,
    definition=OriginStructuralFeatureDefinition(
        melee_critical_extra_dice=1,
    ),
)
HALF_ORC_SAVAGE_ATTACKS_REF = HALF_ORC_SAVAGE_ATTACKS_DECLARATION.ref

HILL_DWARF_DWARVEN_TOUGHNESS_DECLARATION = _declaration(
    content_id="trait.origin.hill_dwarf.dwarven_toughness",
    display_name="Dwarven Toughness",
    description="Maximum hit points increase by 1 for every character level.",
    source_anchor="SRD 5.1 Races: Hill Dwarf — Dwarven Toughness",
    sort_order=230,
    definition=OriginStructuralFeatureDefinition(
        maximum_hit_points_per_character_level=1,
    ),
)
HILL_DWARF_DWARVEN_TOUGHNESS_REF = (
    HILL_DWARF_DWARVEN_TOUGHNESS_DECLARATION.ref
)

ROCK_GNOME_TINKER_DECLARATION = _declaration(
    content_id="trait.origin.rock_gnome.tinker",
    display_name="Tinker",
    description=(
        "Proficiency with tinker's tools and the exact durable Tinker "
        "capability."
    ),
    source_anchor="SRD 5.1 Races: Rock Gnome — Tinker",
    sort_order=240,
    definition=OriginStructuralFeatureDefinition(
        automatic_proficiencies=(
            _subject(ProficiencySubjectKind.TOOL, "tool.tinkers_tools"),
        ),
        capabilities=(OriginCapability.TINKER,),
    ),
)
ROCK_GNOME_TINKER_REF = ROCK_GNOME_TINKER_DECLARATION.ref

ROCK_GNOME_ARTIFICERS_LORE_DECLARATION = _declaration(
    content_id="trait.origin.rock_gnome.artificers_lore",
    display_name="Artificer's Lore",
    description="The exact durable Artificer's Lore capability.",
    source_anchor="SRD 5.1 Races: Rock Gnome — Artificer's Lore",
    sort_order=250,
    definition=OriginStructuralFeatureDefinition(
        capabilities=(OriginCapability.ARTIFICERS_LORE,),
    ),
)
ROCK_GNOME_ARTIFICERS_LORE_REF = (
    ROCK_GNOME_ARTIFICERS_LORE_DECLARATION.ref
)

TIEFLING_FIRE_RESISTANCE_DECLARATION = _declaration(
    content_id="trait.origin.tiefling.fire_resistance",
    display_name="Hellish Resistance",
    description="Resistance to fire damage.",
    source_anchor="SRD 5.1 Races: Tiefling Traits — Hellish Resistance",
    sort_order=260,
    definition=OriginStructuralFeatureDefinition(
        damage_resistances=(DamageType.FIRE,),
    ),
)
TIEFLING_FIRE_RESISTANCE_REF = TIEFLING_FIRE_RESISTANCE_DECLARATION.ref

ACOLYTE_PROFICIENCIES_DECLARATION = _declaration(
    content_id="trait.origin.background.acolyte.proficiencies",
    display_name="Acolyte Skill Proficiencies",
    description="Proficiency in Insight and Religion.",
    source_anchor="SRD 5.1 Backgrounds: Acolyte — Skill Proficiencies",
    sort_order=270,
    definition=OriginStructuralFeatureDefinition(
        automatic_proficiencies=(
            _subject(ProficiencySubjectKind.SKILL, "skill.insight"),
            _subject(ProficiencySubjectKind.SKILL, "skill.religion"),
        ),
    ),
)
ACOLYTE_PROFICIENCIES_REF = ACOLYTE_PROFICIENCIES_DECLARATION.ref

ACOLYTE_SHELTER_OF_THE_FAITHFUL_DECLARATION = _declaration(
    content_id="trait.origin.background.acolyte.shelter_of_the_faithful",
    display_name="Shelter of the Faithful",
    description="The exact durable Shelter of the Faithful capability.",
    source_anchor="SRD 5.1 Backgrounds: Acolyte — Shelter of the Faithful",
    sort_order=280,
    definition=OriginStructuralFeatureDefinition(
        capabilities=(OriginCapability.SHELTER_OF_THE_FAITHFUL,),
    ),
)
ACOLYTE_SHELTER_OF_THE_FAITHFUL_REF = (
    ACOLYTE_SHELTER_OF_THE_FAITHFUL_DECLARATION.ref
)

DWARF_COMBAT_TRAINING_DECLARATION = _declaration(
    content_id="trait.origin.dwarf.combat_training",
    display_name="Dwarven Combat Training",
    description=(
        "Exact proficiency with battleaxes, handaxes, light hammers, and "
        "warhammers."
    ),
    source_anchor="SRD 5.1 Races: Dwarf Traits — Dwarven Combat Training",
    sort_order=290,
    definition=OriginStructuralFeatureDefinition(
        automatic_proficiencies=tuple(
            _weapon_subject(ref)
            for ref in (
                BATTLEAXE_REF,
                HANDAXE_REF,
                LIGHT_HAMMER_REF,
                WARHAMMER_REF,
            )
        ),
    ),
    provenance_notes=(
        "All four SRD weapon proficiencies use exact installed item refs and "
        "the ordinary source-owned proficiency materialization path."
    ),
)
DWARF_COMBAT_TRAINING_REF = DWARF_COMBAT_TRAINING_DECLARATION.ref

HIGH_ELF_WEAPON_TRAINING_DECLARATION = _declaration(
    content_id="trait.origin.high_elf.weapon_training",
    display_name="Elf Weapon Training",
    description=(
        "Exact proficiency with longswords, shortswords, shortbows, and "
        "longbows."
    ),
    source_anchor="SRD 5.1 Races: High Elf — Elf Weapon Training",
    sort_order=295,
    definition=OriginStructuralFeatureDefinition(
        automatic_proficiencies=tuple(
            _weapon_subject(ref)
            for ref in (
                LONGBOW_REF,
                LONGSWORD_REF,
                SHORTBOW_REF,
                SHORTSWORD_REF,
            )
        ),
    ),
)
HIGH_ELF_WEAPON_TRAINING_REF = (
    HIGH_ELF_WEAPON_TRAINING_DECLARATION.ref
)

DWARF_DWARVEN_RESILIENCE_DECLARATION = _declaration(
    content_id="trait.origin.dwarf.dwarven_resilience",
    display_name="Dwarven Resilience",
    description=(
        "Advantage on saving throws against poison and resistance to poison "
        "damage."
    ),
    source_anchor="SRD 5.1 Races: Dwarf Traits — Dwarven Resilience",
    sort_order=300,
    definition=OriginStructuralFeatureDefinition(
        damage_resistances=(DamageType.POISON,),
        saving_throw_advantages=(
            OriginSavingThrowAdvantageRule(
                effect_tags=(SavingThrowEffectTag.POISON,),
            ),
        ),
    ),
)
DWARF_DWARVEN_RESILIENCE_REF = (
    DWARF_DWARVEN_RESILIENCE_DECLARATION.ref
)

DWARF_STONECUNNING_DECLARATION = _declaration(
    content_id="trait.origin.dwarf.stonecunning",
    display_name="Stonecunning",
    description=(
        "The exact durable capability for doubled History proficiency on "
        "checks about the origin of stonework."
    ),
    source_anchor="SRD 5.1 Races: Dwarf Traits — Stonecunning",
    sort_order=310,
    definition=OriginStructuralFeatureDefinition(
        capabilities=(OriginCapability.STONECUNNING,),
    ),
)
DWARF_STONECUNNING_REF = DWARF_STONECUNNING_DECLARATION.ref

ELF_FEY_ANCESTRY_DECLARATION = _declaration(
    content_id="trait.origin.elf.fey_ancestry",
    display_name="Fey Ancestry",
    description=(
        "Advantage on saving throws against being charmed and immunity to "
        "magical sleep."
    ),
    source_anchor="SRD 5.1 Races: Elf Traits — Fey Ancestry",
    sort_order=320,
    definition=OriginStructuralFeatureDefinition(
        capabilities=(OriginCapability.MAGICAL_SLEEP_IMMUNITY,),
        saving_throw_advantages=(
            OriginSavingThrowAdvantageRule(
                effect_tags=(SavingThrowEffectTag.CHARM,),
            ),
        ),
    ),
)
ELF_FEY_ANCESTRY_REF = ELF_FEY_ANCESTRY_DECLARATION.ref

GNOME_CUNNING_DECLARATION = _declaration(
    content_id="trait.origin.gnome.cunning",
    display_name="Gnome Cunning",
    description=(
        "Advantage on Intelligence, Wisdom, and Charisma saving throws "
        "against magic."
    ),
    source_anchor="SRD 5.1 Races: Gnome Traits — Gnome Cunning",
    sort_order=330,
    definition=OriginStructuralFeatureDefinition(
        saving_throw_advantages=(
            OriginSavingThrowAdvantageRule(
                abilities=(
                    AbilityScoreName.INTELLIGENCE,
                    AbilityScoreName.WISDOM,
                    AbilityScoreName.CHARISMA,
                ),
                requires_magical=True,
            ),
        ),
    ),
)
GNOME_CUNNING_REF = GNOME_CUNNING_DECLARATION.ref

HALFLING_BRAVE_DECLARATION = _declaration(
    content_id="trait.origin.halfling.brave",
    display_name="Brave",
    description="Advantage on saving throws against being frightened.",
    source_anchor="SRD 5.1 Races: Halfling Traits — Brave",
    sort_order=340,
    definition=OriginStructuralFeatureDefinition(
        saving_throw_advantages=(
            OriginSavingThrowAdvantageRule(
                effect_tags=(SavingThrowEffectTag.FEAR,),
            ),
        ),
    ),
)
HALFLING_BRAVE_REF = HALFLING_BRAVE_DECLARATION.ref

HALFLING_NIMBLENESS_DECLARATION = _declaration(
    content_id="trait.origin.halfling.nimbleness",
    display_name="Halfling Nimbleness",
    description=(
        "The exact durable capability to move through the space of a "
        "creature larger than the halfling."
    ),
    source_anchor="SRD 5.1 Races: Halfling Traits — Halfling Nimbleness",
    sort_order=350,
    definition=OriginStructuralFeatureDefinition(
        capabilities=(OriginCapability.HALFLING_NIMBLENESS,),
    ),
)
HALFLING_NIMBLENESS_REF = HALFLING_NIMBLENESS_DECLARATION.ref

LIGHTFOOT_NATURALLY_STEALTHY_DECLARATION = _declaration(
    content_id="trait.origin.lightfoot.naturally_stealthy",
    display_name="Naturally Stealthy",
    description=(
        "The exact durable capability to attempt to hide when obscured only "
        "by a creature at least one size larger."
    ),
    source_anchor="SRD 5.1 Races: Lightfoot Halfling — Naturally Stealthy",
    sort_order=360,
    definition=OriginStructuralFeatureDefinition(
        capabilities=(OriginCapability.NATURALLY_STEALTHY,),
    ),
)
LIGHTFOOT_NATURALLY_STEALTHY_REF = (
    LIGHTFOOT_NATURALLY_STEALTHY_DECLARATION.ref
)


SRD_PASSIVE_ORIGIN_FEATURE_DECLARATIONS: tuple[
    ContentDeclaration,
    ...,
] = tuple(sorted(
    (
        ACOLYTE_PROFICIENCIES_DECLARATION,
        ACOLYTE_SHELTER_OF_THE_FAITHFUL_DECLARATION,
        DRAGONBORN_LANGUAGES_DECLARATION,
        DWARF_COMBAT_TRAINING_DECLARATION,
        DWARF_DWARVEN_RESILIENCE_DECLARATION,
        DWARF_LANGUAGES_DECLARATION,
        DWARF_MEDIUM_25_PHYSICAL_DECLARATION,
        DWARF_STONECUNNING_DECLARATION,
        ELF_FEY_ANCESTRY_DECLARATION,
        ELF_KEEN_SENSES_DECLARATION,
        ELF_LANGUAGES_DECLARATION,
        ELF_TRANCE_DECLARATION,
        GNOME_CUNNING_DECLARATION,
        GNOME_LANGUAGES_DECLARATION,
        HALF_ELF_LANGUAGES_DECLARATION,
        HALF_ORC_LANGUAGES_DECLARATION,
        HALF_ORC_MENACING_DECLARATION,
        HALF_ORC_SAVAGE_ATTACKS_DECLARATION,
        HALFLING_BRAVE_DECLARATION,
        HALFLING_LANGUAGES_DECLARATION,
        HALFLING_NIMBLENESS_DECLARATION,
        HIGH_ELF_WEAPON_TRAINING_DECLARATION,
        HILL_DWARF_DWARVEN_TOUGHNESS_DECLARATION,
        HUMAN_LANGUAGES_DECLARATION,
        LIGHTFOOT_NATURALLY_STEALTHY_DECLARATION,
        ROCK_GNOME_ARTIFICERS_LORE_DECLARATION,
        ROCK_GNOME_TINKER_DECLARATION,
        SHARED_DARKVISION_60_DECLARATION,
        SHARED_MEDIUM_30_PHYSICAL_DECLARATION,
        SHARED_SMALL_25_PHYSICAL_DECLARATION,
        TIEFLING_FIRE_RESISTANCE_DECLARATION,
        TIEFLING_LANGUAGES_DECLARATION,
    ),
    key=lambda declaration: declaration.ref.identity_key,
))


__all__ = [
    "ACOLYTE_PROFICIENCIES_DECLARATION",
    "ACOLYTE_PROFICIENCIES_REF",
    "ACOLYTE_SHELTER_OF_THE_FAITHFUL_DECLARATION",
    "ACOLYTE_SHELTER_OF_THE_FAITHFUL_REF",
    "DRAGONBORN_LANGUAGES_DECLARATION",
    "DRAGONBORN_LANGUAGES_REF",
    "DWARF_COMBAT_TRAINING_DECLARATION",
    "DWARF_COMBAT_TRAINING_REF",
    "DWARF_DWARVEN_RESILIENCE_DECLARATION",
    "DWARF_DWARVEN_RESILIENCE_REF",
    "DWARF_LANGUAGES_DECLARATION",
    "DWARF_LANGUAGES_REF",
    "DWARF_MEDIUM_25_PHYSICAL_DECLARATION",
    "DWARF_MEDIUM_25_PHYSICAL_REF",
    "DWARF_STONECUNNING_DECLARATION",
    "DWARF_STONECUNNING_REF",
    "ELF_FEY_ANCESTRY_DECLARATION",
    "ELF_FEY_ANCESTRY_REF",
    "ELF_KEEN_SENSES_DECLARATION",
    "ELF_KEEN_SENSES_REF",
    "ELF_LANGUAGES_DECLARATION",
    "ELF_LANGUAGES_REF",
    "ELF_TRANCE_DECLARATION",
    "ELF_TRANCE_REF",
    "GNOME_CUNNING_DECLARATION",
    "GNOME_CUNNING_REF",
    "GNOME_LANGUAGES_DECLARATION",
    "GNOME_LANGUAGES_REF",
    "HALF_ELF_LANGUAGES_DECLARATION",
    "HALF_ELF_LANGUAGES_REF",
    "HALF_ORC_LANGUAGES_DECLARATION",
    "HALF_ORC_LANGUAGES_REF",
    "HALF_ORC_MENACING_DECLARATION",
    "HALF_ORC_MENACING_REF",
    "HALF_ORC_SAVAGE_ATTACKS_DECLARATION",
    "HALF_ORC_SAVAGE_ATTACKS_REF",
    "HALFLING_BRAVE_DECLARATION",
    "HALFLING_BRAVE_REF",
    "HALFLING_LANGUAGES_DECLARATION",
    "HALFLING_LANGUAGES_REF",
    "HALFLING_NIMBLENESS_DECLARATION",
    "HALFLING_NIMBLENESS_REF",
    "HIGH_ELF_WEAPON_TRAINING_DECLARATION",
    "HIGH_ELF_WEAPON_TRAINING_REF",
    "HILL_DWARF_DWARVEN_TOUGHNESS_DECLARATION",
    "HILL_DWARF_DWARVEN_TOUGHNESS_REF",
    "HUMAN_LANGUAGES_DECLARATION",
    "HUMAN_LANGUAGES_REF",
    "LIGHTFOOT_NATURALLY_STEALTHY_DECLARATION",
    "LIGHTFOOT_NATURALLY_STEALTHY_REF",
    "ROCK_GNOME_ARTIFICERS_LORE_DECLARATION",
    "ROCK_GNOME_ARTIFICERS_LORE_REF",
    "ROCK_GNOME_TINKER_DECLARATION",
    "ROCK_GNOME_TINKER_REF",
    "SHARED_DARKVISION_60_DECLARATION",
    "SHARED_DARKVISION_60_REF",
    "SHARED_MEDIUM_30_PHYSICAL_DECLARATION",
    "SHARED_MEDIUM_30_PHYSICAL_REF",
    "SHARED_SMALL_25_PHYSICAL_DECLARATION",
    "SHARED_SMALL_25_PHYSICAL_REF",
    "SRD_PASSIVE_ORIGIN_FEATURE_DECLARATIONS",
    "TIEFLING_FIRE_RESISTANCE_DECLARATION",
    "TIEFLING_FIRE_RESISTANCE_REF",
    "TIEFLING_LANGUAGES_DECLARATION",
    "TIEFLING_LANGUAGES_REF",
]
