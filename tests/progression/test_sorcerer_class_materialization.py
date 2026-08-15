"""A real level-one Sorcerer installs exact, reversible weapon training."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.classes.sorcerer_progression_definitions import (
    DRACONIC_BLOODLINE_SUBCLASS_DEFINITION,
    DRACONIC_BLOODLINE_SUBCLASS_REF,
    SORCERER_CLASS_DEFINITION,
    SORCERER_CLASS_REF,
)
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.character_materialization import (
    materialize_character,
    remove_character_composition,
)
from dnd.content_system.character_appearance import SORCERER_HUMAN_APPEARANCE
from dnd.content_system.system import LoadedContentSystem
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.content_system.starting_equipment_definitions import (
    STARTING_EQUIPMENT_PACKAGE_DECLARATIONS_BY_PRESET,
)
from dnd.core.content.descriptors import (
    ContentDescriptor,
    ContentDescriptorSpec,
    ContentVisibility,
)
from dnd.core.content.durable_characters import (
    AbilityScoreAllocation,
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
    FlexibleAbilityBonusSelection,
    SpeciesDefinition,
    SpellKnownChoice,
    StartingEquipmentPackageChoice,
    SubclassChoice,
)
from dnd.types.abilities import AbilityName
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.origin_support import OriginRuntimeSupport
from dnd.core.content.materialization import CreatureDeploymentRole
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
from dnd.core.content.registry import FrozenContentRegistry
from dnd.types.equipment import WeaponProperty
from dnd.items.weapons import (
    CLUB_REF,
    DAGGER_REF,
    DART_REF,
    LIGHT_CROSSBOW_REF,
    QUARTERSTAFF_REF,
    SLING_REF,
)
from dnd.player_character_body import PLAYER_CHARACTER_BODY_RECIPE
from dnd.runtime_reset import reset_engine_runtime


_RULESET_DIGEST = "c" * 64
_NEUTRAL_ORIGIN_PROVENANCE = ContentProvenance(
    primary_source_id="fixture.sorcerer_materialization.source",
    source_anchor="complete no-op origin fixture",
    relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
    fidelity=ContentFidelity.COMPLETE,
    review_status=ContentReviewStatus.REVIEWED,
    notes="Complete by definition: this fixture origin grants no mechanics.",
)
_EXACT_WEAPON_REFS = (
    DAGGER_REF,
    DART_REF,
    LIGHT_CROSSBOW_REF,
    QUARTERSTAFF_REF,
    SLING_REF,
)


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(12, 12))
    yield
    reset_engine_runtime()


def _origin_declaration(
    *,
    kind: ContentDefinitionKind,
    content_id: str,
    payload: SpeciesDefinition | BackgroundDefinition,
    provenance: ContentProvenance,
) -> ContentDeclaration:
    ref = ContentRef(
        pack_id="fixture.sorcerer_materialization",
        definition_kind=kind,
        content_id=content_id,
        content_version=1,
        definition_contract_hash=compute_definition_contract_hash(
            mode=ContentDeclarationMode.TYPED_DEFINITION,
            definition_kind=kind,
            definition_model=type(payload),
        ),
    )
    return ContentDeclaration(
        ref=ref,
        mode=ContentDeclarationMode.TYPED_DEFINITION,
        descriptor=ContentDescriptor.from_spec(
            ref,
            ContentDescriptorSpec(
                display_name=content_id,
                description="Complete no-op origin fixture.",
                tags=("character_creation", "player_capable", "fixture_noop_origin"),
                visibility=ContentVisibility.DEVELOPER,
            ),
        ),
        provenance=provenance,
        definition_payload=payload,
    )


def _runtime_with_neutral_origins() -> tuple[
    ContentSystemRuntime,
    str,
    ContentRef,
    ContentRef,
]:
    loaded = bootstrap_content_system()
    species = _origin_declaration(
        kind=ContentDefinitionKind.SPECIES,
        content_id="species.neutral_sorcerer_origin",
        payload=SpeciesDefinition(
            runtime_support=OriginRuntimeSupport.available(),
        ),
        provenance=_NEUTRAL_ORIGIN_PROVENANCE,
    )
    background = _origin_declaration(
        kind=ContentDefinitionKind.BACKGROUND,
        content_id="background.neutral_sorcerer_origin",
        payload=BackgroundDefinition(
            runtime_support=OriginRuntimeSupport.available(),
        ),
        provenance=_NEUTRAL_ORIGIN_PROVENANCE,
    )
    declarations = dict(loaded.registry.declarations)
    declarations[species.ref.identity_key] = species
    declarations[background.ref.identity_key] = background
    runtime = ContentSystemRuntime()
    runtime.install(
        LoadedContentSystem(
            registry=FrozenContentRegistry(
                declarations=declarations,
                recipe_presets=loaded.registry.recipe_presets,
                sources=loaded.registry.sources,
            ),
            built_in_artifact_digest=loaded.built_in_artifact_digest,
            content_set_digest=loaded.content_set_digest,
        ),
    )
    return runtime, loaded.content_set_digest, species.ref, background.ref


def _first_level_choices() -> tuple[BuildChoiceSelection, ...]:
    class_level = SORCERER_CLASS_DEFINITION.level_definitions[0]
    requirements = {
        row.choice_id: row for row in class_level.choice_requirements
    }
    cantrip_refs = requirements[
        "class.sorcerer.level_1.cantrips"
    ].allowed_refs[:4]
    rank_one_keys = {
        row.spell_ref.identity_key
        for row in SORCERER_CLASS_DEFINITION.spell_entitlements
        if row.spell_rank == 1
    }
    ranked_refs = tuple(
        ref
        for ref in requirements[
            "class.sorcerer.level_1.spell_known"
        ].allowed_refs
        if ref.identity_key in rank_one_keys
    )[:2]
    ancestry_requirement = (
        DRACONIC_BLOODLINE_SUBCLASS_DEFINITION
        .level_definitions[0]
        .choice_requirements[0]
    )
    return tuple(sorted(
        (
            CantripChoice(
                choice_id="class.sorcerer.level_1.cantrips",
                selected_refs=cantrip_refs,
            ),
            SpellKnownChoice(
                choice_id="class.sorcerer.level_1.spell_known",
                selected_refs=ranked_refs,
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
            ClassSkillChoice(
                choice_id="class.sorcerer.proficiencies.skills",
                skills=("arcana", "deception"),
            ),
            ElementalAncestryChoice(
                choice_id=ancestry_requirement.choice_id,
                selected_ref=ancestry_requirement.allowed_refs[0],
            ),
        ),
        key=lambda choice: choice.choice_id,
    ))


def test_level_one_sorcerer_installs_and_removes_all_exact_weapon_refs() -> None:
    runtime, content_set_digest, species_ref, background_ref = (
        _runtime_with_neutral_origins()
    )
    character_id = uuid4()
    definition = CharacterDefinitionRevisionV2.create(
        character_id=character_id,
        definition_revision=1,
        body_recipe=PLAYER_CHARACTER_BODY_RECIPE,
        species_ref=species_ref,
        background_ref=background_ref,
        appearance=SORCERER_HUMAN_APPEARANCE,
        base_ability_scores=AbilityScoreAllocation(
            strength=8,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=10,
            charisma=15,
        ),
        flexible_ability_bonuses=FlexibleAbilityBonusSelection(
            plus_two=AbilityName.CHARISMA,
            plus_one=AbilityName.CONSTITUTION,
        ),
        class_levels=(
            ClassLevelEntry(
                class_level_id=ClassLevelId(value="sorcerer.level_1"),
                character_level=1,
                class_ref=SORCERER_CLASS_REF,
                resulting_class_level=1,
                subclass_ref=DRACONIC_BLOODLINE_SUBCLASS_REF,
                choices=_first_level_choices(),
            ),
        ),
        earned_character_level=1,
        content_set_digest=content_set_digest,
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
        display_name="Exact Weapon Sorcerer",
        faction="heroes",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id="test.sorcerer.exact_weapon_proficiencies",
        ),
        expected_ruleset_digest=_RULESET_DIGEST,
        runtime=runtime,
    )
    entity = result.entity
    receipt = result.composition_receipt
    assert receipt is not None

    exact_sources = entity.creature_proficiencies.specific_weapon_sources
    assert frozenset(exact_sources) == frozenset(
        ref.identity_key for ref in _EXACT_WEAPON_REFS
    )
    assert all(
        entity.creature_proficiencies.is_weapon_proficient((), ref)
        for ref in _EXACT_WEAPON_REFS
    )
    assert all(source.sources for source in exact_sources.values())
    assert not entity.creature_proficiencies.is_weapon_proficient(
        (WeaponProperty.SIMPLE,),
        CLUB_REF,
    )

    runtime_entity_uuid = entity.uuid
    remove_character_composition(entity, receipt)

    assert entity.uuid == runtime_entity_uuid
    assert entity.creature_proficiencies.specific_weapon_sources == {}
    assert all(
        not entity.creature_proficiencies.is_weapon_proficient((), ref)
        for ref in _EXACT_WEAPON_REFS
    )
