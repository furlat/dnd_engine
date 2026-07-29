"""Built-in SRD 5.1 character origins are exact authored catalog data."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.classes.barbarian_progression_definitions import BARBARIAN_CLASS_REF
from dnd.classes.progression_definitions import FIGHTER_CLASS_REF
from dnd.classes.sorcerer_progression_definitions import (
    DRACONIC_BLOODLINE_SUBCLASS_DEFINITION,
    DRACONIC_BLOODLINE_SUBCLASS_REF,
    SORCERER_CLASS_DEFINITION,
    SORCERER_CLASS_REF,
)
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.character_appearance import FIGHTER_HUMAN_APPEARANCE
from dnd.content_system.character_materialization import (
    materialize_character,
    remove_character_composition,
)
from dnd.content_system.fighter_character_grant_appliers import (
    FIGHTING_STYLE_ARCHERY_REF,
)
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.content_system.starting_equipment_definitions import (
    STARTING_EQUIPMENT_PACKAGE_DECLARATIONS_BY_PRESET,
)
from dnd.core.content.dependencies import ContentDependencyRelation
from dnd.core.content.durable_characters import (
    AbilityScoreAllocation,
    AbilityScoreName,
    BackgroundDefinition,
    BuildChoiceSelection,
    CantripChoice,
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
    ClassLevelEntry,
    ClassLevelId,
    ClassSkillChoice,
    ElementalAncestryChoice,
    FightingStyleChoice,
    FlexibleAbilityBonusSelection,
    ProficiencySubject,
    ProficiencySubjectKind,
    SpeciesDefinition,
    SpeciesVariantDefinition,
    SpellKnownChoice,
    StartingEquipmentPackageChoice,
    StartingProficiencyChoice,
    SubclassChoice,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.materialization import CreatureDeploymentRole
from dnd.core.content.origin_support import OriginRuntimeSupportStatus
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentReviewStatus,
)
from dnd.core.content.registration import ContentDeclarationMode
from dnd.player_character_body import PLAYER_CHARACTER_BODY_RECIPE
from dnd.runtime_reset import reset_engine_runtime
from dnd.core.language_types import SrdLanguageId
from server.content_catalog import build_public_content_catalog


_EXPECTED_SPECIES_IDS = {
    "species.dragonborn",
    "species.dwarf",
    "species.elf",
    "species.gnome",
    "species.half_elf",
    "species.half_orc",
    "species.halfling",
    "species.human",
    "species.tiefling",
}
_EXPECTED_VARIANT_PARENTS = {
    "species_variant.dwarf.hill": "species.dwarf",
    "species_variant.elf.high": "species.elf",
    "species_variant.gnome.rock": "species.gnome",
    "species_variant.halfling.lightfoot": "species.halfling",
}
_EXPECTED_BACKGROUND_IDS = {"background.acolyte"}
_RULESET_DIGEST = "c" * 64


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(12, 12))
    yield
    reset_engine_runtime()


def test_srd_character_origins_are_public_exact_typed_definitions() -> None:
    loaded = bootstrap_content_system()
    declarations = tuple(loaded.registry.declarations.values())
    origins = tuple(
        declaration
        for declaration in declarations
        if declaration.ref.definition_kind
        in {
            ContentDefinitionKind.SPECIES,
            ContentDefinitionKind.SPECIES_VARIANT,
            ContentDefinitionKind.BACKGROUND,
        }
        and declaration.ref.pack_id == "content.srd_5_1_cc"
    )

    assert {
        row.ref.content_id
        for row in origins
        if row.ref.definition_kind == ContentDefinitionKind.SPECIES
    } == _EXPECTED_SPECIES_IDS
    assert {
        row.ref.content_id
        for row in origins
        if row.ref.definition_kind == ContentDefinitionKind.BACKGROUND
    } == _EXPECTED_BACKGROUND_IDS
    variants = {
        row.ref.content_id: row.definition_payload
        for row in origins
        if row.ref.definition_kind == ContentDefinitionKind.SPECIES_VARIANT
    }
    assert set(variants) == set(_EXPECTED_VARIANT_PARENTS)
    for variant_id, parent_id in _EXPECTED_VARIANT_PARENTS.items():
        payload = variants[variant_id]
        assert isinstance(payload, SpeciesVariantDefinition)
        assert payload.parent_species_ref.content_id == parent_id

    for declaration in origins:
        assert declaration.mode == ContentDeclarationMode.TYPED_DEFINITION
        assert declaration.descriptor.description
        assert declaration.descriptor.presentation.visual_variant_key
        assert declaration.provenance.primary_source_id == "wotc.srd_5_1_cc"
        assert declaration.provenance.review_status == ContentReviewStatus.REVIEWED
        assert declaration.ref.content_version == 2
        payload = declaration.definition_payload
        assert isinstance(
            payload,
            SpeciesDefinition
            | SpeciesVariantDefinition
            | BackgroundDefinition,
        )
        assert declaration.provenance.fidelity is not ContentFidelity.BLOCKED
        assert (
            payload.runtime_support.status
            is OriginRuntimeSupportStatus.AVAILABLE
        )
        assert payload.runtime_support.blocked_reason is None
        assert "player_capable" not in declaration.descriptor.tags
        assert "implementation_blocked" not in declaration.descriptor.tags

    species_payloads = {
        row.ref.content_id: row.definition_payload
        for row in origins
        if row.ref.definition_kind == ContentDefinitionKind.SPECIES
    }
    for content_id, payload in species_payloads.items():
        assert isinstance(payload, SpeciesDefinition)
        assert payload.level_grants, content_id
        assert all(row.grant_refs for row in payload.level_grants)
    half_elf = species_payloads["species.half_elf"]
    assert isinstance(half_elf, SpeciesDefinition)
    assert tuple(
        requirement.choice_id
        for requirement in half_elf.choice_requirements
    ) == (
        "species.half_elf.additional_language",
        "species.half_elf.skill_versatility",
    )
    skill_versatility = half_elf.choice_requirements[1]
    assert skill_versatility.choice_kind.value == "starting_proficiency"
    assert skill_versatility.minimum_selections == 2
    assert skill_versatility.maximum_selections == 2
    assert len(skill_versatility.allowed_proficiency_subjects) == 18
    background_payload = next(
        row.definition_payload
        for row in origins
        if row.ref.content_id == "background.acolyte"
    )
    assert isinstance(background_payload, BackgroundDefinition)
    assert len(background_payload.automatic_grant_refs) == 2
    assert tuple(
        requirement.choice_id
        for requirement in background_payload.choice_requirements
    ) == ("background.acolyte.languages",)
    assert (
        background_payload.runtime_support.status
        is OriginRuntimeSupportStatus.AVAILABLE
    )

    adventurer = next(
        row for row in declarations
        if row.ref.identity_key
        == "content.neurodragon:background:background.adventurer@2"
    )
    assert adventurer.provenance.fidelity == ContentFidelity.COMPLETE
    assert (
        adventurer.provenance.primary_source_id
        == "neurodragon.original_b2b3930"
    )
    assert isinstance(adventurer.definition_payload, BackgroundDefinition)
    assert (
        adventurer.definition_payload.runtime_support.status
        is OriginRuntimeSupportStatus.AVAILABLE
    )
    assert adventurer.definition_payload.runtime_support.blocked_reason is None
    assert adventurer.definition_payload.automatic_grant_refs == ()
    assert adventurer.definition_payload.choice_requirements == ()


def test_srd_species_variant_edges_are_closed_and_catalog_visible() -> None:
    loaded = bootstrap_content_system()
    declarations = loaded.registry.declarations
    catalog = build_public_content_catalog(loaded)
    catalog_refs = {entry.ref.identity_key for entry in catalog.entries}

    for species_id in _EXPECTED_SPECIES_IDS:
        species = declarations[
            f"content.srd_5_1_cc:species:{species_id}@2"
        ]
        assert species.ref.identity_key in catalog_refs
        variant_edges = tuple(
            dependency
            for dependency in species.dependencies
            if dependency.relation
            == ContentDependencyRelation.HAS_SPECIES_VARIANT
        )
        expected_variant_ids = {
            variant_id
            for variant_id, parent_id in _EXPECTED_VARIANT_PARENTS.items()
            if parent_id == species_id
        }
        assert {
            edge.target_ref.content_id for edge in variant_edges
        } == expected_variant_ids
        assert {
            ref.content_id
            for ref in species.descriptor.related_content_refs
            if ref.definition_kind
            is ContentDefinitionKind.SPECIES_VARIANT
        } == expected_variant_ids

    for background_id in _EXPECTED_BACKGROUND_IDS:
        key = f"content.srd_5_1_cc:background:{background_id}@2"
        assert key in declarations
        assert key in catalog_refs


def _sorcerer_level_one_choices() -> tuple[BuildChoiceSelection, ...]:
    requirements = {
        row.choice_id: row
        for row in SORCERER_CLASS_DEFINITION.level_definitions[
            0
        ].choice_requirements
    }
    ancestry_requirement = (
        DRACONIC_BLOODLINE_SUBCLASS_DEFINITION
        .level_definitions[0]
        .choice_requirements[0]
    )
    rank_one_keys = {
        row.spell_ref.identity_key
        for row in SORCERER_CLASS_DEFINITION.spell_entitlements
        if row.spell_rank == 1
    }
    rank_one_refs = tuple(
        ref
        for ref in requirements[
            "class.sorcerer.level_1.spell_known"
        ].allowed_refs
        if ref.identity_key in rank_one_keys
    )
    return tuple(sorted(
        (
            CantripChoice(
                choice_id="class.sorcerer.level_1.cantrips",
                selected_refs=requirements[
                    "class.sorcerer.level_1.cantrips"
                ].allowed_refs[:4],
            ),
            ClassSkillChoice(
                choice_id="class.sorcerer.proficiencies.skills",
                skills=("arcana", "deception"),
            ),
            ElementalAncestryChoice(
                choice_id=ancestry_requirement.choice_id,
                selected_ref=ancestry_requirement.allowed_refs[0],
            ),
            SpellKnownChoice(
                choice_id="class.sorcerer.level_1.spell_known",
                selected_refs=rank_one_refs[:2],
            ),
            StartingEquipmentPackageChoice(
                choice_id="class.sorcerer.first_class.starting_equipment",
                selected_ref=(
                    STARTING_EQUIPMENT_PACKAGE_DECLARATIONS_BY_PRESET[
                        ("sorcerer", "dagger")
                    ].ref
                ),
            ),
            SubclassChoice(
                choice_id="class.sorcerer.level_1.subclass",
                selected_ref=DRACONIC_BLOODLINE_SUBCLASS_REF,
            ),
        ),
        key=lambda choice: choice.choice_id,
    ))


@pytest.mark.parametrize(
    ("class_id", "class_level", "primary_ability"),
    (
        (
            "fighter",
            ClassLevelEntry(
                class_level_id=ClassLevelId(value="fighter.level_1"),
                character_level=1,
                class_ref=FIGHTER_CLASS_REF,
                resulting_class_level=1,
                choices=(
                    StartingEquipmentPackageChoice(
                        choice_id="class.fighter.first_class.starting_equipment",
                        selected_ref=(
                            STARTING_EQUIPMENT_PACKAGE_DECLARATIONS_BY_PRESET[
                                ("fighter", "sword_shield")
                            ].ref
                        ),
                    ),
                    FightingStyleChoice(
                        choice_id="class.fighter.level_1.fighting_style",
                        selected_ref=FIGHTING_STYLE_ARCHERY_REF,
                    ),
                    ClassSkillChoice(
                        choice_id="class.fighter.proficiencies.skills",
                        skills=("athletics", "perception"),
                    ),
                ),
            ),
            AbilityScoreName.STRENGTH,
        ),
        (
            "barbarian",
            ClassLevelEntry(
                class_level_id=ClassLevelId(value="barbarian.level_1"),
                character_level=1,
                class_ref=BARBARIAN_CLASS_REF,
                resulting_class_level=1,
                choices=(
                    StartingEquipmentPackageChoice(
                        choice_id=(
                            "class.barbarian.first_class.starting_equipment"
                        ),
                        selected_ref=(
                            STARTING_EQUIPMENT_PACKAGE_DECLARATIONS_BY_PRESET[
                                ("barbarian", "greataxe")
                            ].ref
                        ),
                    ),
                    ClassSkillChoice(
                        choice_id="class.barbarian.proficiencies.skills",
                        skills=("athletics", "perception"),
                    ),
                ),
            ),
            AbilityScoreName.STRENGTH,
        ),
        (
            "sorcerer",
            ClassLevelEntry(
                class_level_id=ClassLevelId(value="sorcerer.level_1"),
                character_level=1,
                class_ref=SORCERER_CLASS_REF,
                resulting_class_level=1,
                subclass_ref=DRACONIC_BLOODLINE_SUBCLASS_REF,
                choices=_sorcerer_level_one_choices(),
            ),
            AbilityScoreName.CHARISMA,
        ),
    ),
)
def test_human_adventurer_validates_materializes_and_reverses_existing_classes(
    class_id: str,
    class_level: ClassLevelEntry,
    primary_ability: AbilityScoreName,
) -> None:
    loaded = bootstrap_content_system()
    runtime = ContentSystemRuntime()
    runtime.install(loaded)
    character_id = uuid4()
    definition = CharacterDefinitionRevisionV2.create(
        character_id=character_id,
        definition_revision=1,
        body_recipe=PLAYER_CHARACTER_BODY_RECIPE,
        species_ref=loaded.registry.declarations[
            "content.srd_5_1_cc:species:species.human@2"
        ].ref,
        background_ref=loaded.registry.declarations[
            "content.neurodragon:background:background.adventurer@2"
        ].ref,
        immutable_origin_choices=(
            StartingProficiencyChoice(
                choice_id="species.human.additional_language",
                proficiencies=(
                    ProficiencySubject(
                        subject_kind=ProficiencySubjectKind.LANGUAGE,
                        subject_id=SrdLanguageId.DRACONIC.value,
                    ),
                ),
            ),
        ),
        appearance=FIGHTER_HUMAN_APPEARANCE,
        base_ability_scores=AbilityScoreAllocation(
            strength=15,
            dexterity=14,
            constitution=13,
            intelligence=8,
            wisdom=10,
            charisma=12,
        ),
        flexible_ability_bonuses=FlexibleAbilityBonusSelection(
            plus_two=primary_ability,
            plus_one=AbilityScoreName.CONSTITUTION,
        ),
        class_levels=(class_level,),
        earned_character_level=1,
        content_set_digest=loaded.content_set_digest,
        ruleset_digest=_RULESET_DIGEST,
    )
    loadout = CharacterLoadoutRevisionV1.create(
        character_id=character_id,
        loadout_revision=1,
        based_on_definition_revision=definition.definition_revision,
    )

    result = materialize_character(
        definition=definition,
        holdings=CharacterHoldingsRevision.create(
            character_id=character_id,
            holdings_revision=1,
        ),
        loadout=loadout,
        runtime_entity_uuid=uuid4(),
        display_name=f"Human Adventurer {class_id}",
        faction="heroes",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id=f"test.origins.{class_id}",
        ),
        expected_ruleset_digest=_RULESET_DIGEST,
        runtime=runtime,
    )

    assert result.composition_receipt is not None
    assert result.entity.health.total_hit_dices_number == 1
    remove_character_composition(
        result.entity,
        result.composition_receipt,
    )
    assert result.entity.health.total_hit_dices_number == 0
