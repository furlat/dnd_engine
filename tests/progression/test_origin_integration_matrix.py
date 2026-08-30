"""Every installed origin validates, composes, reverses, and reapplies."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.content_system.builtin_character_builds import (
    compose_character_creation_plans,
)
from dnd.content_system.builtin_inventory import (
    BUILT_IN_DECLARATION_INVENTORY,
    BUILT_IN_RECIPE_PRESET_INVENTORY,
)
from dnd.content_system.character_build_validation import (
    CharacterBuildValidator,
)
from dnd.content_system.character_materialization import (
    apply_character_composition,
    materialize_character,
    remove_character_composition,
)
from dnd.content_system.character_origin_definitions import (
    ACOLYTE_BACKGROUND_DECLARATION,
    ADVENTURER_BACKGROUND_DECLARATION,
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
from dnd.content_system.pack_loader import LoadedContentSystem
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.core.content.durable_characters import (
    BackgroundDefinition,
    BuildChoiceRequirement,
    BuildChoiceSelection,
    CantripChoice,
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
    ChoiceRequirementKind,
    OriginTraitChoice,
    SpeciesDefinition,
    SpeciesVariantDefinition,
    StartingApparelPackageChoice,
    StartingProficiencyChoice,
)
from dnd.core.content.materialization import CreatureDeploymentRole
from dnd.core.content.registry import FrozenContentRegistry
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import ResistanceStatus
from dnd.types.senses import SensesType
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime


_RULESET_DIGEST = "e" * 64
_SPECIES_CASES = (
    (DRAGONBORN_SPECIES_DECLARATION, None),
    (DWARF_SPECIES_DECLARATION, None),
    (DWARF_SPECIES_DECLARATION, HILL_DWARF_VARIANT_DECLARATION),
    (ELF_SPECIES_DECLARATION, None),
    (ELF_SPECIES_DECLARATION, HIGH_ELF_VARIANT_DECLARATION),
    (GNOME_SPECIES_DECLARATION, None),
    (GNOME_SPECIES_DECLARATION, ROCK_GNOME_VARIANT_DECLARATION),
    (HALF_ELF_SPECIES_DECLARATION, None),
    (HALF_ORC_SPECIES_DECLARATION, None),
    (HALFLING_SPECIES_DECLARATION, None),
    (HALFLING_SPECIES_DECLARATION, LIGHTFOOT_HALFLING_VARIANT_DECLARATION),
    (HUMAN_SPECIES_DECLARATION, None),
    (TIEFLING_SPECIES_DECLARATION, None),
)


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(12, 12))
    yield
    reset_engine_runtime()


def _loaded_builtin() -> LoadedContentSystem:
    return LoadedContentSystem(
        registry=FrozenContentRegistry(
            declarations={
                declaration.ref.identity_key: declaration
                for declaration in BUILT_IN_DECLARATION_INVENTORY
            },
            recipe_presets={
                preset.ref.identity_key: preset
                for preset in BUILT_IN_RECIPE_PRESET_INVENTORY
            },
            sources={},
        ),
        packs=(),
        built_in_artifact_digest="c" * 64,
        content_set_digest="d" * 64,
    )


def _choice_for(
    requirement: BuildChoiceRequirement,
) -> BuildChoiceSelection:
    if requirement.choice_kind is ChoiceRequirementKind.ORIGIN_TRAIT:
        return OriginTraitChoice(
            choice_id=requirement.choice_id,
            selected_ref=requirement.allowed_refs[0],
        )
    if requirement.choice_kind is ChoiceRequirementKind.CANTRIP:
        return CantripChoice(
            choice_id=requirement.choice_id,
            selected_refs=requirement.allowed_refs[
                :requirement.minimum_selections
            ],
        )
    if (
        requirement.choice_kind
        is ChoiceRequirementKind.STARTING_PROFICIENCY
    ):
        return StartingProficiencyChoice(
            choice_id=requirement.choice_id,
            proficiencies=requirement.allowed_proficiency_subjects[
                :requirement.minimum_selections
            ],
        )
    raise AssertionError(
        f"Unhandled origin choice {requirement.choice_kind.value}",
    )


def _origin_choices(
    *definitions: (
        SpeciesDefinition
        | SpeciesVariantDefinition
        | BackgroundDefinition
        | None
    ),
) -> tuple[BuildChoiceSelection, ...]:
    blank = compose_character_creation_plans()[0].build
    apparel = tuple(
        choice
        for choice in blank.immutable_origin_choices
        if isinstance(choice, StartingApparelPackageChoice)
    )
    selected = [
        _choice_for(requirement)
        for definition in definitions
        if definition is not None
        for requirement in definition.choice_requirements
    ]
    return tuple(sorted(
        (*apparel, *selected),
        key=lambda choice: choice.choice_id,
    ))


def _definition_payload(
    declaration: object,
    expected_type: type[
        SpeciesDefinition | SpeciesVariantDefinition | BackgroundDefinition
    ],
) -> SpeciesDefinition | SpeciesVariantDefinition | BackgroundDefinition:
    payload = getattr(declaration, "definition_payload")
    assert isinstance(payload, expected_type)
    return payload


def _semantic_composition_snapshot(entity: Entity) -> tuple[object, ...]:
    return (
        entity.character_species_ref,
        entity.character_species_variant_ref,
        entity.character_background_ref,
        entity.size,
        entity.action_economy.current_speed(),
        tuple(sorted(entity.creature_proficiencies.language_sources)),
        tuple(sorted(entity.creature_proficiencies.tool_sources)),
        entity.senses.get_sense_range(SensesType.DARKVISION),
        tuple(sorted(
            capability.value for capability in entity.origin_capability_sources
        )),
        tuple(sorted(
            action.name or ""
            for action in entity.registered_actions
        )),
        tuple(sorted(
            handler.name or ""
            for handler in entity.event_handlers.values()
        )),
        tuple(sorted(
            (
                source.source_kind,
                source.provider_ref.identity_key,
                source.provider_level,
            )
            for source in entity.spellcasting.sources.values()
        )),
        tuple(
            entity.health.get_resistance(damage_type)
            for damage_type in DamageType
        ),
        entity.health.max_hit_points_bonus.normalized_score,
        entity.equipment.crit_extra_dice_melee.normalized_score,
        entity.health.total_hit_dices_number,
    )


def _assert_receipt_handles_removed(
    entity: Entity,
    receipt,
) -> None:
    action_ids = {action.uuid for action in entity.registered_actions}
    for grant in receipt.grants:
        assert action_ids.isdisjoint(grant.action_uuids)
        assert set(entity.event_handlers).isdisjoint(grant.handler_uuids)
        assert set(entity.spellcasting.sources).isdisjoint(
            grant.spellcasting_source_ids,
        )
        for handle in grant.proficiency_handles:
            assert not entity.creature_proficiencies.remove_source(
                handle.source_id,
            )
    assert entity.character_species_ref is None
    assert entity.character_species_variant_ref is None
    assert entity.character_background_ref is None
    assert entity.health.total_hit_dices_number == 0
    assert entity.creature_proficiencies.language_sources == {}
    assert entity.creature_proficiencies.tool_sources == {}
    assert entity.origin_capability_sources == {}
    assert entity.senses.get_sense_range(SensesType.DARKVISION) == -1
    assert all(
        entity.health.get_resistance(damage_type) is ResistanceStatus.NONE
        for damage_type in DamageType
    )


@pytest.mark.parametrize(
    ("species_declaration", "variant_declaration"),
    _SPECIES_CASES,
    ids=tuple(
        (
            variant.ref.content_id
            if variant is not None
            else species.ref.content_id
        )
        for species, variant in _SPECIES_CASES
    ),
)
def test_every_srd_species_validates_composes_reverses_and_reapplies(
    species_declaration,
    variant_declaration,
) -> None:
    _exercise_origin(
        species_declaration=species_declaration,
        variant_declaration=variant_declaration,
        background_declaration=ADVENTURER_BACKGROUND_DECLARATION,
    )


def test_acolyte_validates_composes_reverses_and_reapplies() -> None:
    _exercise_origin(
        species_declaration=HUMAN_SPECIES_DECLARATION,
        variant_declaration=None,
        background_declaration=ACOLYTE_BACKGROUND_DECLARATION,
    )


def _exercise_origin(
    *,
    species_declaration,
    variant_declaration,
    background_declaration,
) -> None:
    loaded = _loaded_builtin()
    runtime = ContentSystemRuntime()
    runtime.install(loaded)
    blank = compose_character_creation_plans()[0]
    character_id = uuid4()
    species = _definition_payload(
        species_declaration,
        SpeciesDefinition,
    )
    variant = (
        _definition_payload(
            variant_declaration,
            SpeciesVariantDefinition,
        )
        if variant_declaration is not None
        else None
    )
    background = _definition_payload(
        background_declaration,
        BackgroundDefinition,
    )
    definition = CharacterDefinitionRevisionV2.create(
        character_id=character_id,
        definition_revision=1,
        body_recipe=blank.build.body_recipe,
        species_ref=species_declaration.ref,
        species_variant_ref=(
            variant_declaration.ref
            if variant_declaration is not None
            else None
        ),
        background_ref=background_declaration.ref,
        immutable_origin_choices=_origin_choices(
            species,
            variant,
            background,
        ),
        appearance=blank.build.appearance,
        base_ability_scores=blank.build.base_ability_scores,
        flexible_ability_bonuses=blank.build.flexible_ability_bonuses,
        class_levels=blank.build.class_levels,
        earned_character_level=1,
        content_set_digest=loaded.content_set_digest,
        ruleset_digest=_RULESET_DIGEST,
    )
    loadout = CharacterLoadoutRevisionV1.create(
        character_id=character_id,
        loadout_revision=1,
        based_on_definition_revision=1,
        prepared_spells=blank.loadout.prepared_spells,
        feature_toggles=blank.loadout.feature_toggles,
    )
    validation = CharacterBuildValidator(
        loaded,
        expected_ruleset_digest=_RULESET_DIGEST,
    ).validate(definition, loadout)
    assert validation.valid, validation.issues
    assert validation.preview is not None

    materialized = materialize_character(
        definition=definition,
        holdings=CharacterHoldingsRevision.create(
            character_id=character_id,
            holdings_revision=1,
        ),
        loadout=loadout,
        runtime_entity_uuid=uuid4(),
        display_name=species_declaration.descriptor.display_name,
        faction="heroes",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id=f"test.origin.{species_declaration.ref.content_id}",
        ),
        expected_ruleset_digest=_RULESET_DIGEST,
        runtime=runtime,
    )
    receipt = materialized.composition_receipt
    assert receipt is not None
    original = _semantic_composition_snapshot(materialized.entity)
    assert materialized.entity.character_species_ref == species_declaration.ref
    assert (
        materialized.entity.character_species_variant_ref
        == (
            variant_declaration.ref
            if variant_declaration is not None
            else None
        )
    )
    assert (
        materialized.entity.character_background_ref
        == background_declaration.ref
    )

    remove_character_composition(materialized.entity, receipt)
    _assert_receipt_handles_removed(materialized.entity, receipt)

    reapplied = apply_character_composition(
        entity=materialized.entity,
        definition=definition,
        loadout=loadout,
        preview=validation.preview,
        runtime=runtime,
    )
    assert _semantic_composition_snapshot(materialized.entity) == original
    remove_character_composition(materialized.entity, reapplied)
    _assert_receipt_handles_removed(materialized.entity, reapplied)
