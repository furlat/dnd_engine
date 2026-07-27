"""A real Fighter/Champion build composes and reverses through schema 2."""

from collections import Counter
from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.classes import fighter
from dnd.classes.progression_definitions import (
    CHAMPION_SUBCLASS_REF,
    FIGHTER_CLASS_REF,
)
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.character_materialization import (
    materialize_character,
    remove_character_composition,
)
from dnd.content_system.extra_attack_character_grant_appliers import (
    EXTRA_ATTACK_FEATURE_REF,
)
from dnd.content_system.fighter_character_grant_appliers import (
    ACTION_SURGE_REF,
    FIGHTING_STYLE_ARCHERY_REF,
    IMPROVED_CRITICAL_REF,
    SECOND_WIND_REF,
)
from dnd.content_system.pack_loader import LoadedContentSystem
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
    AbilityScoreImprovementChoice,
    AbilityScoreName,
    BackgroundDefinition,
    CharacterAppearanceSelection,
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
    ClassLevelEntry,
    ClassLevelId,
    ClassSkillChoice,
    FightingStyleChoice,
    FlexibleAbilityBonusSelection,
    SpeciesDefinition,
    StartingEquipmentPackageChoice,
    SubclassChoice,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
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
from dnd.core.equipment_types import ArmorType, WeaponProperty
from dnd.player_character_body import PLAYER_CHARACTER_BODY_RECIPE
from dnd.runtime_reset import reset_engine_runtime


_RULESET_DIGEST = "c" * 64
_NEUTRAL_ORIGIN_PROVENANCE = ContentProvenance(
    primary_source_id="fixture.fighter_materialization.source",
    source_anchor="complete no-op origin fixture",
    relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
    fidelity=ContentFidelity.COMPLETE,
    review_status=ContentReviewStatus.REVIEWED,
    notes="Complete by definition: this fixture origin grants no mechanics.",
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
    provenance,
) -> ContentDeclaration:
    ref = ContentRef(
        pack_id="fixture.fighter_materialization",
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
        content_id="species.neutral_test_origin",
        payload=SpeciesDefinition(),
        provenance=_NEUTRAL_ORIGIN_PROVENANCE,
    )
    background = _origin_declaration(
        kind=ContentDefinitionKind.BACKGROUND,
        content_id="background.neutral_test_origin",
        payload=BackgroundDefinition(),
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
            packs=loaded.packs,
            built_in_artifact_digest=loaded.built_in_artifact_digest,
            content_set_digest=loaded.content_set_digest,
        ),
    )
    return (
        runtime,
        loaded.content_set_digest,
        species.ref,
        background.ref,
    )


def test_fighter_five_champion_materializes_and_reverses_exactly() -> None:
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
        appearance=CharacterAppearanceSelection(),
        base_ability_scores=AbilityScoreAllocation(
            strength=15,
            dexterity=14,
            constitution=13,
            intelligence=12,
            wisdom=10,
            charisma=8,
        ),
        flexible_ability_bonuses=FlexibleAbilityBonusSelection(
            plus_two=AbilityScoreName.STRENGTH,
            plus_one=AbilityScoreName.CONSTITUTION,
        ),
        class_levels=(
            ClassLevelEntry(
                class_level_id=ClassLevelId(value="fighter.level_1"),
                character_level=1,
                class_ref=FIGHTER_CLASS_REF,
                resulting_class_level=1,
                choices=(
                    StartingEquipmentPackageChoice(
                        choice_id=(
                            "class.fighter.first_class.starting_equipment"
                        ),
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
            ClassLevelEntry(
                class_level_id=ClassLevelId(value="fighter.level_2"),
                character_level=2,
                class_ref=FIGHTER_CLASS_REF,
                resulting_class_level=2,
            ),
            ClassLevelEntry(
                class_level_id=ClassLevelId(value="fighter.level_3"),
                character_level=3,
                class_ref=FIGHTER_CLASS_REF,
                resulting_class_level=3,
                subclass_ref=CHAMPION_SUBCLASS_REF,
                choices=(
                    SubclassChoice(
                        choice_id="class.fighter.level_3.subclass",
                        selected_ref=CHAMPION_SUBCLASS_REF,
                    ),
                ),
            ),
            ClassLevelEntry(
                class_level_id=ClassLevelId(value="fighter.level_4"),
                character_level=4,
                class_ref=FIGHTER_CLASS_REF,
                resulting_class_level=4,
                subclass_ref=CHAMPION_SUBCLASS_REF,
                choices=(
                    AbilityScoreImprovementChoice(
                        choice_id="class.fighter.level_4.asi_or_feat",
                        increases=((AbilityScoreName.STRENGTH, 2),),
                    ),
                ),
            ),
            ClassLevelEntry(
                class_level_id=ClassLevelId(value="fighter.level_5"),
                character_level=5,
                class_ref=FIGHTER_CLASS_REF,
                resulting_class_level=5,
                subclass_ref=CHAMPION_SUBCLASS_REF,
            ),
        ),
        earned_character_level=5,
        content_set_digest=content_set_digest,
        ruleset_digest=_RULESET_DIGEST,
    )
    loadout = CharacterLoadoutRevisionV1.create(
        character_id=character_id,
        loadout_revision=1,
        based_on_definition_revision=1,
    )

    result = materialize_character(
        definition=definition,
        holdings=CharacterHoldingsRevision.create(
            character_id=character_id,
            holdings_revision=1,
        ),
        loadout=loadout,
        runtime_entity_uuid=uuid4(),
        display_name="Fighter Five",
        faction="heroes",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id="test.fighter_champion",
        ),
        expected_ruleset_digest=_RULESET_DIGEST,
        runtime=runtime,
    )
    entity = result.entity
    receipt = result.composition_receipt
    assert receipt is not None

    assert receipt.automatic_grant_refs == (
        SECOND_WIND_REF,
        ACTION_SURGE_REF,
        IMPROVED_CRITICAL_REF,
        EXTRA_ATTACK_FEATURE_REF,
    )
    assert Counter(
        grant.definition_ref
        for grant in receipt.grants
        if grant.definition_ref in {
            SECOND_WIND_REF,
            ACTION_SURGE_REF,
            IMPROVED_CRITICAL_REF,
            EXTRA_ATTACK_FEATURE_REF,
            FIGHTING_STYLE_ARCHERY_REF,
        }
    ) == Counter({
        SECOND_WIND_REF: 1,
        ACTION_SURGE_REF: 1,
        IMPROVED_CRITICAL_REF: 1,
        EXTRA_ATTACK_FEATURE_REF: 2,
        FIGHTING_STYLE_ARCHERY_REF: 1,
    })
    assert not entity.active_conditions
    assert all(not grant.condition_handles for grant in receipt.grants)

    feature_actions = {
        type(action): action
        for action in entity.registered_actions
        if isinstance(
            action,
            (
                fighter.SecondWind,
                fighter.ActionSurge,
                fighter.ExtraAttack,
            ),
        )
    }
    assert set(feature_actions) == {
        fighter.SecondWind,
        fighter.ActionSurge,
        fighter.ExtraAttack,
    }
    expected_action_providers = {
        fighter.SecondWind: SECOND_WIND_REF,
        fighter.ActionSurge: ACTION_SURGE_REF,
        fighter.ExtraAttack: EXTRA_ATTACK_FEATURE_REF,
    }
    for action_type, provider_ref in expected_action_providers.items():
        action = feature_actions[action_type]
        assert action.behavior_binding is not None
        assert action.behavior_binding.provided_by_ref == provider_ref
        assert action.source_entity_uuid == entity.uuid
    assert feature_actions[fighter.SecondWind].fighter_level == 5

    extra_attack_handlers = tuple(
        handler
        for handler in entity.event_handlers.values()
        if (
            handler.behavior_binding is not None
            and handler.behavior_binding.provided_by_ref
            == EXTRA_ATTACK_FEATURE_REF
        )
    )
    assert len(extra_attack_handlers) == 1
    assert extra_attack_handlers[0].name == "Extra Attack Resource"

    assert entity.equipment.ranged_attack_bonus.normalized_score == 2
    assert entity.get_crit_threshold() == 19
    assert entity.get_spell_crit_threshold() == 20
    assert entity.action_economy.resolve_attacks_per_attack_action() == 2
    assert (
        entity.action_economy.resources["extra_attacks"].current,
        entity.action_economy.resources["extra_attacks"].maximum,
    ) == (1, 1)
    assert (
        entity.action_economy.resources["second_wind"].current,
        entity.action_economy.resources["second_wind"].maximum,
    ) == (1, 1)
    assert (
        entity.action_economy.resources["action_surge"].current,
        entity.action_economy.resources["action_surge"].maximum,
    ) == (1, 1)

    assert entity.ability_scores.strength.ability_score.score == 19
    assert entity.ability_scores.constitution.ability_score.score == 14
    assert entity.proficiency_bonus.normalized_score == 3
    assert entity.initiative.normalized_score == 2
    assert entity.health.total_hit_dices_number == 5
    assert entity.health.hit_dices_total_hit_points == 34
    assert {
        hit_die.hit_dice_value.normalized_score
        for hit_die in entity.health.hit_dices
    } == {10}
    assert (
        entity.skill_set.athletics.proficiency_sources.sources
        and entity.skill_set.perception.proficiency_sources.sources
    )
    assert (
        entity.saving_throws.strength_saving_throw
        .proficiency_sources.sources
    )
    assert (
        entity.saving_throws.constitution_saving_throw
        .proficiency_sources.sources
    )
    assert entity.creature_proficiencies.is_weapon_proficient(
        (WeaponProperty.SIMPLE,),
    )
    assert entity.creature_proficiencies.is_weapon_proficient(
        (WeaponProperty.MARTIAL,),
    )
    assert all(
        entity.creature_proficiencies.is_armor_proficient(armor_type)
        for armor_type in (ArmorType.LIGHT, ArmorType.MEDIUM, ArmorType.HEAVY)
    )
    assert entity.creature_proficiencies.is_shield_proficient()

    feature_action_uuids = {
        action.uuid for action in feature_actions.values()
    }
    feature_handler_uuids = {
        handler.uuid for handler in extra_attack_handlers
    }
    body_action_uuids = {
        action.uuid
        for action in entity.registered_actions
        if action.uuid not in feature_action_uuids
    }
    body_handler_uuids = (
        set(entity.event_handlers) - feature_handler_uuids
    )
    remove_character_composition(entity, receipt)

    remaining_action_uuids = {
        action.uuid for action in entity.registered_actions
    }
    remaining_handler_uuids = set(entity.event_handlers)
    assert body_action_uuids <= remaining_action_uuids
    assert feature_action_uuids.isdisjoint(remaining_action_uuids)
    assert body_handler_uuids <= remaining_handler_uuids
    assert feature_handler_uuids.isdisjoint(remaining_handler_uuids)
    assert not entity.active_conditions
    assert entity.action_economy.resolve_attacks_per_attack_action() == 1
    assert not {
        "second_wind",
        "action_surge",
        "extra_attacks",
    } & entity.action_economy.resources.keys()
    assert entity.equipment.ranged_attack_bonus.normalized_score == 0
    assert entity.get_crit_threshold() == 20
    assert entity.ability_scores.strength.ability_score.score == 0
    assert entity.ability_scores.constitution.ability_score.score == 0
    assert entity.proficiency_bonus.normalized_score == 0
    assert entity.initiative.normalized_score == -5
    assert entity.health.hit_dices == []
    assert (
        entity.skill_set.athletics.proficiency_sources.sources == {}
        and entity.skill_set.perception.proficiency_sources.sources == {}
    )
    assert (
        entity.saving_throws.strength_saving_throw
        .proficiency_sources.sources
        == {}
    )
    assert (
        entity.saving_throws.constitution_saving_throw
        .proficiency_sources.sources
        == {}
    )
    assert not entity.creature_proficiencies.is_weapon_proficient(
        (WeaponProperty.SIMPLE,),
    )
    assert not entity.creature_proficiencies.is_weapon_proficient(
        (WeaponProperty.MARTIAL,),
    )
    assert not any(
        entity.creature_proficiencies.is_armor_proficient(armor_type)
        for armor_type in (ArmorType.LIGHT, ArmorType.MEDIUM, ArmorType.HEAVY)
    )
    assert not entity.creature_proficiencies.is_shield_proficient()
