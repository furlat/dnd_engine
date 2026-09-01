"""Pure authored data gates for passive SRD character-origin features."""

from dnd.content_system.origin_feature_definitions import (
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
    GNOME_LANGUAGES_DECLARATION,
    GNOME_CUNNING_DECLARATION,
    HALF_ELF_LANGUAGES_DECLARATION,
    HALF_ORC_LANGUAGES_DECLARATION,
    HALF_ORC_MENACING_DECLARATION,
    HALF_ORC_SAVAGE_ATTACKS_DECLARATION,
    HALFLING_LANGUAGES_DECLARATION,
    HALFLING_BRAVE_DECLARATION,
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
    SRD_PASSIVE_ORIGIN_FEATURE_DECLARATIONS,
    TIEFLING_FIRE_RESISTANCE_DECLARATION,
    TIEFLING_LANGUAGES_DECLARATION,
)
from dnd.content_system.character_origin_definitions import (
    ACOLYTE_BACKGROUND_DECLARATION,
    DRAGONBORN_SPECIES_DECLARATION,
    DWARF_SPECIES_DECLARATION,
    ELF_SPECIES_DECLARATION,
    GNOME_SPECIES_DECLARATION,
    HALF_ELF_SPECIES_DECLARATION,
    HALF_ORC_SPECIES_DECLARATION,
    HALFLING_SPECIES_DECLARATION,
    HIGH_ELF_VARIANT_DECLARATION,
    HILL_DWARF_VARIANT_DECLARATION,
    HUMAN_SPECIES_DECLARATION,
    LIGHTFOOT_HALFLING_VARIANT_DECLARATION,
    ROCK_GNOME_VARIANT_DECLARATION,
    TIEFLING_SPECIES_DECLARATION,
)
from dnd.content_system.builtin_character_builds import (
    BUILTIN_PREMADE_BUILDS,
    compose_builtin_character_drafts,
)
from dnd.content_system.builtin_inventory import (
    BUILT_IN_DECLARATION_INVENTORY,
)
from dnd.core.content.durable_characters import (
    AbilityScoreName,
    BackgroundDefinition,
    ChoiceRequirementKind,
    ProficiencySubjectKind,
    SpeciesDefinition,
    SpeciesVariantDefinition,
    StartingProficiencyChoice,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.origin_features import (
    OriginCapability,
    OriginStructuralFeatureDefinition,
)
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentReviewStatus,
)
from dnd.core.content.origin_support import OriginRuntimeSupportStatus
from dnd.core.content.registration import ContentDeclarationMode
from dnd.core.language_types import SrdLanguageId
from dnd.core.creature_types import DamageType, Size
from dnd.core.saving_throw_types import SavingThrowEffectTag
from dnd.types.senses import SensesType


def _payload(
    declaration,
) -> OriginStructuralFeatureDefinition:
    payload = declaration.definition_payload
    assert isinstance(payload, OriginStructuralFeatureDefinition)
    return payload


def _subject_ids(declaration) -> tuple[str, ...]:
    return tuple(
        row.identity_key
        for row in _payload(declaration).automatic_proficiencies
    )


def test_every_installed_srd_origin_is_mechanically_available() -> None:
    """A public origin card cannot outlive its blocked implementation shell."""
    origins = (
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
        ACOLYTE_BACKGROUND_DECLARATION,
    )

    for declaration in origins:
        definition = declaration.definition_payload
        assert isinstance(
            definition,
            SpeciesDefinition | SpeciesVariantDefinition | BackgroundDefinition,
        )
        assert (
            definition.runtime_support.status
            is OriginRuntimeSupportStatus.AVAILABLE
        ), declaration.ref.identity_key
        assert definition.runtime_support.blocked_reason is None
        assert declaration.provenance.fidelity is not ContentFidelity.BLOCKED


def test_passive_origin_feature_inventory_is_exact_public_typed_data() -> None:
    expected_content_ids = {
        "trait.origin.background.acolyte.proficiencies",
        "trait.origin.background.acolyte.shelter_of_the_faithful",
        "trait.origin.dwarf.combat_training",
        "trait.origin.dwarf.dwarven_resilience",
        "trait.origin.dwarf.physical.medium_25",
        "trait.origin.dwarf.stonecunning",
        "trait.origin.elf.fey_ancestry",
        "trait.origin.elf.keen_senses",
        "trait.origin.elf.trance",
        "trait.origin.half_orc.menacing",
        "trait.origin.half_orc.savage_attacks",
        "trait.origin.hill_dwarf.dwarven_toughness",
        "trait.origin.rock_gnome.artificers_lore",
        "trait.origin.rock_gnome.tinker",
        "trait.origin.gnome.cunning",
        "trait.origin.halfling.brave",
        "trait.origin.halfling.nimbleness",
        "trait.origin.high_elf.weapon_training",
        "trait.origin.lightfoot.naturally_stealthy",
        "trait.origin.shared.darkvision_60",
        "trait.origin.shared.physical.medium_30",
        "trait.origin.shared.physical.small_25",
        "trait.origin.species.dragonborn.languages",
        "trait.origin.species.dwarf.languages",
        "trait.origin.species.elf.languages",
        "trait.origin.species.gnome.languages",
        "trait.origin.species.half_elf.languages",
        "trait.origin.species.half_orc.languages",
        "trait.origin.species.halfling.languages",
        "trait.origin.species.human.languages",
        "trait.origin.species.tiefling.languages",
        "trait.origin.tiefling.fire_resistance",
    }
    declarations = SRD_PASSIVE_ORIGIN_FEATURE_DECLARATIONS

    assert {row.ref.content_id for row in declarations} == expected_content_ids
    assert tuple(row.ref.identity_key for row in declarations) == tuple(
        sorted(row.ref.identity_key for row in declarations),
    )
    for declaration in declarations:
        assert declaration.ref.pack_id == "content.srd_5_1_cc"
        assert declaration.ref.definition_kind is ContentDefinitionKind.TRAIT
        assert declaration.ref.content_version == 1
        assert declaration.mode is ContentDeclarationMode.TYPED_DEFINITION
        assert declaration.descriptor.visibility.value == "public"
        assert declaration.descriptor.description
        assert declaration.descriptor.tags == (
            "character_creation",
            "origin_feature",
            "passive",
            "srd_5_1",
        )
        assert declaration.provenance.primary_source_id in {
            "wotc.srd_5_1_cc",
            "neurodragon.original_b2b3930",
        }
        assert (
            declaration.provenance.review_status
            is ContentReviewStatus.REVIEWED
        )
        assert declaration.runtime_behavior_kind is None
        assert declaration.construction is None
        assert declaration.dependencies == ()
        _payload(declaration)


def test_trait_kind_supports_pure_typed_structure_without_runtime_behavior() -> None:
    declaration = ELF_TRANCE_DECLARATION

    assert declaration.ref.definition_kind is ContentDefinitionKind.TRAIT
    assert declaration.mode is ContentDeclarationMode.TYPED_DEFINITION
    assert isinstance(
        declaration.definition_payload,
        OriginStructuralFeatureDefinition,
    )
    assert declaration.runtime_behavior_kind is None
    assert declaration.construction is None


def test_physical_and_darkvision_features_are_exact() -> None:
    medium = _payload(SHARED_MEDIUM_30_PHYSICAL_DECLARATION)
    small = _payload(SHARED_SMALL_25_PHYSICAL_DECLARATION)
    dwarf = _payload(DWARF_MEDIUM_25_PHYSICAL_DECLARATION)
    darkvision = _payload(SHARED_DARKVISION_60_DECLARATION)

    assert (medium.size, medium.walking_speed_feet) == (Size.MEDIUM, 30)
    assert (small.size, small.walking_speed_feet) == (Size.SMALL, 25)
    assert (dwarf.size, dwarf.walking_speed_feet) == (Size.MEDIUM, 25)
    assert len(darkvision.sense_modes) == 1
    assert darkvision.sense_modes[0].sense_type is SensesType.DARKVISION
    assert darkvision.sense_modes[0].range_feet == 60


def test_fixed_species_language_packages_use_only_exact_srd_ids() -> None:
    expected = (
        (
            DRAGONBORN_LANGUAGES_DECLARATION,
            (SrdLanguageId.COMMON.value, SrdLanguageId.DRACONIC.value),
        ),
        (
            DWARF_LANGUAGES_DECLARATION,
            (SrdLanguageId.COMMON.value, SrdLanguageId.DWARVISH.value),
        ),
        (
            ELF_LANGUAGES_DECLARATION,
            (SrdLanguageId.COMMON.value, SrdLanguageId.ELVISH.value),
        ),
        (
            GNOME_LANGUAGES_DECLARATION,
            (SrdLanguageId.COMMON.value, SrdLanguageId.GNOMISH.value),
        ),
        (
            HALF_ELF_LANGUAGES_DECLARATION,
            (SrdLanguageId.COMMON.value, SrdLanguageId.ELVISH.value),
        ),
        (
            HALF_ORC_LANGUAGES_DECLARATION,
            (SrdLanguageId.COMMON.value, SrdLanguageId.ORC.value),
        ),
        (
            HALFLING_LANGUAGES_DECLARATION,
            (SrdLanguageId.COMMON.value, SrdLanguageId.HALFLING.value),
        ),
        (
            HUMAN_LANGUAGES_DECLARATION,
            (SrdLanguageId.COMMON.value,),
        ),
        (
            TIEFLING_LANGUAGES_DECLARATION,
            (SrdLanguageId.COMMON.value, SrdLanguageId.INFERNAL.value),
        ),
    )

    for declaration, language_ids in expected:
        assert _subject_ids(declaration) == language_ids
        assert all(
            row.subject_kind is ProficiencySubjectKind.LANGUAGE
            for row in _payload(declaration).automatic_proficiencies
        )


def test_passive_trait_payloads_claim_only_installed_structural_facts() -> None:
    assert _subject_ids(ELF_KEEN_SENSES_DECLARATION) == (
        "skill.perception",
    )
    assert _payload(ELF_TRANCE_DECLARATION).capabilities == (
        OriginCapability.TRANCE,
    )
    assert _subject_ids(HALF_ORC_MENACING_DECLARATION) == (
        "skill.intimidation",
    )
    assert (
        _payload(
            HALF_ORC_SAVAGE_ATTACKS_DECLARATION,
        ).melee_critical_extra_dice
        == 1
    )
    assert (
        _payload(
            HILL_DWARF_DWARVEN_TOUGHNESS_DECLARATION,
        ).maximum_hit_points_per_character_level
        == 1
    )
    assert _subject_ids(ROCK_GNOME_TINKER_DECLARATION) == (
        "tool.tinkers_tools",
    )
    assert _payload(ROCK_GNOME_TINKER_DECLARATION).capabilities == (
        OriginCapability.TINKER,
    )
    assert _payload(
        ROCK_GNOME_ARTIFICERS_LORE_DECLARATION,
    ).capabilities == (OriginCapability.ARTIFICERS_LORE,)
    assert _payload(TIEFLING_FIRE_RESISTANCE_DECLARATION).damage_resistances == (
        DamageType.FIRE,
    )
    assert _subject_ids(ACOLYTE_PROFICIENCIES_DECLARATION) == (
        "skill.insight",
        "skill.religion",
    )
    assert _payload(
        ACOLYTE_SHELTER_OF_THE_FAITHFUL_DECLARATION,
    ).capabilities == (OriginCapability.SHELTER_OF_THE_FAITHFUL,)
    dwarf_resilience = _payload(DWARF_DWARVEN_RESILIENCE_DECLARATION)
    assert dwarf_resilience.damage_resistances == (DamageType.POISON,)
    assert dwarf_resilience.saving_throw_advantages[0].effect_tags == (
        SavingThrowEffectTag.POISON,
    )
    assert _payload(DWARF_STONECUNNING_DECLARATION).capabilities == (
        OriginCapability.STONECUNNING,
    )
    fey_ancestry = _payload(ELF_FEY_ANCESTRY_DECLARATION)
    assert fey_ancestry.capabilities == (
        OriginCapability.MAGICAL_SLEEP_IMMUNITY,
    )
    assert fey_ancestry.saving_throw_advantages[0].effect_tags == (
        SavingThrowEffectTag.CHARM,
    )
    gnome_cunning = _payload(GNOME_CUNNING_DECLARATION)
    assert gnome_cunning.saving_throw_advantages[0].abilities == (
        AbilityScoreName.INTELLIGENCE,
        AbilityScoreName.WISDOM,
        AbilityScoreName.CHARISMA,
    )
    assert gnome_cunning.saving_throw_advantages[0].requires_magical is True
    assert _payload(
        HALFLING_BRAVE_DECLARATION,
    ).saving_throw_advantages[0].effect_tags == (
        SavingThrowEffectTag.FEAR,
    )
    assert _payload(HALFLING_NIMBLENESS_DECLARATION).capabilities == (
        OriginCapability.HALFLING_NIMBLENESS,
    )
    assert _payload(
        LIGHTFOOT_NATURALLY_STEALTHY_DECLARATION,
    ).capabilities == (OriginCapability.NATURALLY_STEALTHY,)


def test_all_passive_origin_features_enter_the_one_builtin_inventory() -> None:
    inventory_keys = {
        declaration.ref.identity_key
        for declaration in BUILT_IN_DECLARATION_INVENTORY
    }

    assert {
        declaration.ref.identity_key
        for declaration in SRD_PASSIVE_ORIGIN_FEATURE_DECLARATIONS
    } <= inventory_keys


def test_builtin_humans_select_the_required_additional_language() -> None:
    for build in BUILTIN_PREMADE_BUILDS.values():
        draft, _ = compose_builtin_character_drafts(build)

        assert len(draft.immutable_origin_choices) == 1
        choice = draft.immutable_origin_choices[0]
        assert isinstance(choice, StartingProficiencyChoice)
        assert choice.choice_id == "species.human.additional_language"
        assert tuple(
            (row.subject_kind, row.subject_id)
            for row in choice.proficiencies
        ) == (
            (
                ProficiencySubjectKind.LANGUAGE,
                SrdLanguageId.DRACONIC.value,
            ),
        )


def test_passive_origin_grants_and_choices_are_wired_to_exact_origins() -> None:
    expected_grants = {
        DWARF_SPECIES_DECLARATION.ref.identity_key: {
            "trait.origin.dwarf.combat_training",
            "trait.origin.dwarf.dwarven_resilience",
            "trait.origin.dwarf.physical.medium_25",
            "trait.origin.dwarf.stonecunning",
            "trait.origin.shared.darkvision_60",
            "trait.origin.species.dwarf.languages",
        },
        ELF_SPECIES_DECLARATION.ref.identity_key: {
            "trait.origin.elf.fey_ancestry",
            "trait.origin.elf.keen_senses",
            "trait.origin.elf.trance",
            "trait.origin.shared.darkvision_60",
            "trait.origin.shared.physical.medium_30",
            "trait.origin.species.elf.languages",
        },
        GNOME_SPECIES_DECLARATION.ref.identity_key: {
            "trait.origin.gnome.cunning",
            "trait.origin.shared.darkvision_60",
            "trait.origin.shared.physical.small_25",
            "trait.origin.species.gnome.languages",
        },
        HALF_ELF_SPECIES_DECLARATION.ref.identity_key: {
            "trait.origin.elf.fey_ancestry",
            "trait.origin.shared.darkvision_60",
            "trait.origin.shared.physical.medium_30",
            "trait.origin.species.half_elf.languages",
        },
        HALF_ORC_SPECIES_DECLARATION.ref.identity_key: {
            "trait.origin.half_orc.menacing",
            "trait.origin.half_orc.relentless_endurance",
            "trait.origin.half_orc.savage_attacks",
            "trait.origin.shared.darkvision_60",
            "trait.origin.shared.physical.medium_30",
            "trait.origin.species.half_orc.languages",
        },
        HALFLING_SPECIES_DECLARATION.ref.identity_key: {
            "trait.origin.halfling.brave",
            "trait.origin.halfling.lucky",
            "trait.origin.halfling.nimbleness",
            "trait.origin.shared.physical.small_25",
            "trait.origin.species.halfling.languages",
        },
        LIGHTFOOT_HALFLING_VARIANT_DECLARATION.ref.identity_key: {
            "trait.origin.lightfoot.naturally_stealthy",
        },
        HIGH_ELF_VARIANT_DECLARATION.ref.identity_key: {
            "trait.origin.high_elf.weapon_training",
        },
    }
    declarations = (
        DWARF_SPECIES_DECLARATION,
        ELF_SPECIES_DECLARATION,
        GNOME_SPECIES_DECLARATION,
        HALF_ELF_SPECIES_DECLARATION,
        HALF_ORC_SPECIES_DECLARATION,
        HALFLING_SPECIES_DECLARATION,
        HIGH_ELF_VARIANT_DECLARATION,
        LIGHTFOOT_HALFLING_VARIANT_DECLARATION,
    )
    for declaration in declarations:
        payload = declaration.definition_payload
        assert isinstance(
            payload,
            SpeciesDefinition | SpeciesVariantDefinition,
        )
        grant_refs = (
            tuple(
                ref
                for row in payload.level_grants
                for ref in row.grant_refs
            )
        )
        assert {ref.content_id for ref in grant_refs} == expected_grants[
            declaration.ref.identity_key
        ]

    dwarf = DWARF_SPECIES_DECLARATION.definition_payload
    assert isinstance(dwarf, SpeciesDefinition)
    tool_requirement = next(
        requirement
        for requirement in dwarf.choice_requirements
        if requirement.choice_id == "species.dwarf.artisans_tool"
    )
    assert tuple(
        subject.subject_id
        for subject in tool_requirement.allowed_proficiency_subjects
    ) == (
        "tool.artisan.brewers_supplies",
        "tool.artisan.masons_tools",
        "tool.artisan.smiths_tools",
    )


def test_dwarf_combat_training_owns_all_four_exact_srd_weapon_refs() -> None:
    declaration = DWARF_COMBAT_TRAINING_DECLARATION
    payload = _payload(declaration)

    assert tuple(
        row.subject_id for row in payload.automatic_proficiencies
    ) == (
        "weapon.battleaxe",
        "weapon.handaxe",
        "weapon.light_hammer",
        "weapon.warhammer",
    )
    assert all(
        row.subject_kind is ProficiencySubjectKind.WEAPON
        for row in payload.automatic_proficiencies
    )
    assert declaration.provenance.fidelity is ContentFidelity.COMPLETE
    assert "partial" not in declaration.descriptor.display_name.lower()


def test_high_elf_owns_exact_weapon_training_cantrip_and_language_choices() -> None:
    payload = _payload(HIGH_ELF_WEAPON_TRAINING_DECLARATION)
    variant = HIGH_ELF_VARIANT_DECLARATION.definition_payload
    assert isinstance(variant, SpeciesVariantDefinition)

    assert tuple(
        row.subject_id for row in payload.automatic_proficiencies
    ) == (
        "weapon.longbow",
        "weapon.longsword",
        "weapon.shortbow",
        "weapon.shortsword",
    )
    requirements = {
        requirement.choice_id: requirement
        for requirement in variant.choice_requirements
    }
    assert set(requirements) == {
        "species_variant.high_elf.additional_language",
        "species_variant.high_elf.wizard_cantrip",
    }
    language = requirements["species_variant.high_elf.additional_language"]
    assert language.choice_kind is ChoiceRequirementKind.STARTING_PROFICIENCY
    assert language.minimum_selections == language.maximum_selections == 1
    assert all(
        row.subject_kind is ProficiencySubjectKind.LANGUAGE
        and row.subject_id
        not in {SrdLanguageId.COMMON.value, SrdLanguageId.ELVISH.value}
        for row in language.allowed_proficiency_subjects
    )
