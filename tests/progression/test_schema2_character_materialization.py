"""Schema-2 characters compose reversible structure through the sole path."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from uuid import uuid4, uuid5

import pytest

from dnd.extensions.aegis_spark import AegisTrainingFeature
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.character_materialization import (
    materialize_character,
    remove_character_composition,
)
from dnd.content_system.extra_attack_character_grant_appliers import (
    EXTRA_ATTACK_FEATURE_REF,
)
from dnd.content_system.condition_definitions import (
    CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS,
)
from dnd.content_system.pack_loader import LoadedContentSystem
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.controller import PassController
from dnd.classes.structural_feature_definitions import (
    REMARKABLE_ATHLETE_DECLARATION,
)
from dnd.core.content.descriptors import (
    ContentDescriptor,
    ContentDescriptorSpec,
    ContentVisibility,
)
from dnd.core.content.durable_characters import (
    AbilityScoreAllocation,
    AbilityScoreName,
    CharacterAppearanceSelection,
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
    ClassDefinition,
    ClassLevelDefinition,
    ClassLevelEntry,
    ClassLevelId,
    ClassProficiencyPackage,
    FlexibleAbilityBonusSelection,
    ProficiencySubject,
    ProficiencySubjectKind,
    SpeciesDefinition,
    BackgroundDefinition,
    SpellcastingSourceId,
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
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.core.life_types import LifeState
from dnd.core.modifiers import DamageType
from dnd.core.progression import CasterProgression
from dnd.encounter import Encounter, EncounterState
from dnd.monsters.bestiary import create_goblin
from dnd.player_character_body import PLAYER_CHARACTER_BODY_RECIPE
from dnd.runtime_reset import reset_engine_runtime


_CONTENT_SET_DIGEST = "b" * 64
_RULESET_DIGEST = "c" * 64
_FIXTURE_PROVENANCE = ContentProvenance(
    primary_source_id="fixture.schema2_materialization.source",
    source_anchor="complete schema-2 fixture definitions",
    relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
    fidelity=ContentFidelity.COMPLETE,
    review_status=ContentReviewStatus.REVIEWED,
    notes=(
        "Fixture definitions are complete for their explicitly declared "
        "test-only mechanics."
    ),
)


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(12, 12))
    yield
    reset_engine_runtime()


def _typed_declaration(
    kind: ContentDefinitionKind,
    content_id: str,
    payload,
) -> ContentDeclaration:
    ref = ContentRef(
        pack_id="fixture.schema2_materialization",
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
                tags=(
                    ("character_creation", "player_capable")
                    if kind in {
                        ContentDefinitionKind.SPECIES,
                        ContentDefinitionKind.BACKGROUND,
                    }
                    else ()
                ),
                visibility=ContentVisibility.DEVELOPER,
            ),
        ),
        provenance=_FIXTURE_PROVENANCE,
        definition_payload=payload,
    )


def _runtime_with(
    class_definition: ClassDefinition,
) -> tuple[
    ContentSystemRuntime,
    ContentRef,
    ContentRef,
    ContentRef,
]:
    built_in = bootstrap_content_system()
    species = _typed_declaration(
        ContentDefinitionKind.SPECIES,
        "species.human",
        SpeciesDefinition(),
    )
    background = _typed_declaration(
        ContentDefinitionKind.BACKGROUND,
        "background.soldier",
        BackgroundDefinition(),
    )
    class_declaration = _typed_declaration(
        ContentDefinitionKind.CLASS,
        "class.fixture",
        class_definition,
    )
    declarations = dict(built_in.registry.declarations)
    for declaration in (species, background, class_declaration):
        declarations[declaration.ref.identity_key] = declaration
    registry = FrozenContentRegistry(
        declarations=declarations,
        recipe_presets=built_in.registry.recipe_presets,
        sources=built_in.registry.sources,
    )
    runtime = ContentSystemRuntime()
    runtime.install(
        LoadedContentSystem(
            registry=registry,
            packs=(),
            built_in_artifact_digest="a" * 64,
            content_set_digest=_CONTENT_SET_DIGEST,
        ),
    )
    return runtime, species.ref, background.ref, class_declaration.ref


def _definition(
    *,
    character_id,
    species_ref: ContentRef,
    background_ref: ContentRef,
    class_ref: ContentRef,
    levels: int,
) -> CharacterDefinitionRevisionV2:
    return CharacterDefinitionRevisionV2.create(
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
        class_levels=tuple(
            ClassLevelEntry(
                class_level_id=ClassLevelId(
                    value=f"class.fixture.level_{level}",
                ),
                character_level=level,
                class_ref=class_ref,
                resulting_class_level=level,
            )
            for level in range(1, levels + 1)
        ),
        earned_character_level=levels,
        content_set_digest=_CONTENT_SET_DIGEST,
        ruleset_digest=_RULESET_DIGEST,
    )


def _materialize(
    class_definition: ClassDefinition,
    *,
    levels: int,
):
    runtime, species_ref, background_ref, class_ref = _runtime_with(
        class_definition,
    )
    character_id = uuid4()
    definition = _definition(
        character_id=character_id,
        species_ref=species_ref,
        background_ref=background_ref,
        class_ref=class_ref,
        levels=levels,
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
        display_name="Schema Two Hero",
        faction="heroes",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id="test.schema2.character",
        ),
        expected_ruleset_digest=_RULESET_DIGEST,
        runtime=runtime,
    )
    return result


def test_schema2_materializer_applies_and_removes_neutral_structure() -> None:
    result = _materialize(
        ClassDefinition(
            hit_die=10,
            caster_progression=CasterProgression.NON_CASTER,
            first_class_proficiencies=ClassProficiencyPackage(
                automatic=(
                    ProficiencySubject(
                        subject_kind=ProficiencySubjectKind.ARMOR,
                        subject_id="armor.light",
                    ),
                    ProficiencySubject(
                        subject_kind=ProficiencySubjectKind.SKILL,
                        subject_id="skill.athletics",
                    ),
                    ProficiencySubject(
                        subject_kind=ProficiencySubjectKind.WEAPON,
                        subject_id="weapon.simple",
                    ),
                ),
            ),
            saving_throw_proficiencies=(
                AbilityScoreName.CONSTITUTION,
                AbilityScoreName.STRENGTH,
            ),
            level_definitions=(
                ClassLevelDefinition(class_level=1),
                ClassLevelDefinition(class_level=2),
            ),
        ),
        levels=2,
    )
    entity = result.entity
    receipt = result.composition_receipt
    assert receipt is not None
    assert entity.ability_scores.strength.ability_score.score == 17
    assert entity.ability_scores.constitution.ability_score.score == 14
    assert entity.initiative.normalized_score == 2
    assert entity.proficiency_bonus.normalized_score == 2
    assert entity.health.total_hit_dices_number == 2
    assert entity.health.get_max_hit_dices_points(2) == 20
    assert entity.skill_set.athletics.get_score(2) == 2
    assert entity.saving_throws.strength_saving_throw.get_bonus(2) == 2
    assert entity.creature_proficiencies.is_weapon_proficient(
        (WeaponProperty.SIMPLE,),
    )
    scheduled_grants = tuple(
        grant
        for grant in receipt.grants
        if grant.grant_token is not None
    )
    assert scheduled_grants
    assert all(
        grant.grant_id == uuid5(receipt.character_id, grant.grant_token)
        for grant in scheduled_grants
        if grant.grant_token is not None
    )

    runtime_uuid = entity.uuid
    remove_character_composition(entity, receipt)

    assert entity.uuid == runtime_uuid
    assert entity.ability_scores.strength.ability_score.score == 0
    assert entity.ability_scores.constitution.ability_score.score == 0
    assert entity.initiative.normalized_score == -5
    assert entity.proficiency_bonus.normalized_score == 0
    assert entity.health.total_hit_dices_number == 0
    assert entity.skill_set.athletics.get_score(2) == 0
    assert entity.saving_throws.strength_saving_throw.get_bonus(2) == 0
    assert not entity.creature_proficiencies.is_armor_proficient(
        ArmorType.LIGHT,
    )


def test_schema2_player_zero_hp_commits_dead_and_terminal_encounter() -> None:
    """Persistent player bodies use the product's direct zero-HP death rule."""
    result = _materialize(
        ClassDefinition(
            hit_die=10,
            caster_progression=CasterProgression.NON_CASTER,
            level_definitions=(ClassLevelDefinition(class_level=1),),
        ),
        levels=1,
    )
    hero = result.entity
    enemy = create_goblin(
        name="Terminal Enemy",
        position=(3, 2),
        faction="monsters",
    )
    encounter = Encounter(
        name="Schema Two Terminal Encounter",
        source_entity_uuid=uuid4(),
    )
    encounter.add_combatant(
        hero,
        PassController(source_entity_uuid=hero.uuid),
    )
    encounter.add_combatant(
        enemy,
        PassController(source_entity_uuid=enemy.uuid),
    )
    encounter.roll_initiative()
    encounter.start_encounter()
    source_cursor = EventQueue.event_cursor()

    hero.receive_damage(
        hero.get_normal_hp(),
        DamageType.FORCE,
        source_entity_uuid=enemy.uuid,
    )
    encounter.check_deaths()

    assert not hero.uses_death_saves
    assert hero.health.life_state is LifeState.DEAD
    assert encounter.state is EncounterState.ENDED
    completed_types = [
        event.event_type
        for _, event in EventQueue.iter_events_since(source_cursor)
        if event.phase is EventPhase.COMPLETION
    ]
    assert EventType.DEATH in completed_types
    assert EventType.LIFE_STATE_CHANGE in completed_types
    assert completed_types[-1] is EventType.ENCOUNTER_END


def test_composition_receipt_rejects_another_runtime_entity() -> None:
    result = _materialize(
        ClassDefinition(
            hit_die=8,
            caster_progression=CasterProgression.NON_CASTER,
            level_definitions=(ClassLevelDefinition(class_level=1),),
        ),
        levels=1,
    )
    receipt = result.composition_receipt
    assert receipt is not None
    other = _materialize(
        ClassDefinition(
            hit_die=8,
            caster_progression=CasterProgression.NON_CASTER,
            level_definitions=(ClassLevelDefinition(class_level=1),),
        ),
        levels=1,
    ).entity

    with pytest.raises(ValueError, match="different runtime entity"):
        remove_character_composition(other, receipt)


def test_schema2_materializer_installs_one_shared_normal_slot_table() -> None:
    result = _materialize(
        ClassDefinition(
            hit_die=6,
            caster_progression=CasterProgression.FULL_CASTER,
            spellcasting_feature_class_level=1,
            spellcasting_source_id=SpellcastingSourceId(
                value="spellcasting.fixture",
            ),
            spellcasting_ability=AbilityScoreName.CHARISMA,
            level_definitions=(
                ClassLevelDefinition(class_level=1),
                ClassLevelDefinition(class_level=2),
                ClassLevelDefinition(class_level=3),
            ),
        ),
        levels=3,
    )
    entity = result.entity
    receipt = result.composition_receipt
    assert receipt is not None
    assert len(entity.spellcasting.sources) == 1
    assert entity.action_economy.spell_slot_1.normalized_score == 4
    assert entity.action_economy.spell_slot_2.normalized_score == 2
    assert entity.action_economy.get_normal_spell_slot_capacity_source() is not None

    remove_character_composition(entity, receipt)

    assert entity.spellcasting.sources == {}
    assert entity.action_economy.spell_slot_1.normalized_score == 0
    assert entity.action_economy.spell_slot_2.normalized_score == 0
    assert entity.action_economy.get_normal_spell_slot_capacity_source() is None


def test_remarkable_athlete_applies_and_removes_without_a_condition() -> None:
    result = _materialize(
        ClassDefinition(
            hit_die=10,
            caster_progression=CasterProgression.NON_CASTER,
            level_definitions=(
                ClassLevelDefinition(
                    class_level=1,
                    automatic_grant_refs=(
                        REMARKABLE_ATHLETE_DECLARATION.ref,
                    ),
                ),
            ),
        ),
        levels=1,
    )
    entity = result.entity
    receipt = result.composition_receipt
    assert receipt is not None

    assert entity.ability_check_bonus(
        None,
        "strength",
    ).normalized_score == 4
    assert entity.skill_bonus(None, "athletics").normalized_score == 4
    assert entity.jump_distance_additive.normalized_score == 3
    assert "Remarkable Athlete" not in entity.active_conditions
    remarkable_receipt = next(
        grant
        for grant in receipt.grants
        if grant.definition_ref == REMARKABLE_ATHLETE_DECLARATION.ref
    )

    remove_character_composition(
        entity,
        replace(receipt, grants=(remarkable_receipt,)),
    )

    assert entity.ability_check_bonus(
        None,
        "strength",
    ).normalized_score == 3
    assert entity.skill_bonus(None, "athletics").normalized_score == 3
    assert entity.jump_distance_additive.normalized_score == 0


def test_extra_attack_resolves_repeated_ranks_and_removes_one_family() -> None:
    result = _materialize(
        ClassDefinition(
            hit_die=10,
            caster_progression=CasterProgression.NON_CASTER,
            level_definitions=tuple(
                ClassLevelDefinition(
                    class_level=level,
                    automatic_grant_refs=(
                        (EXTRA_ATTACK_FEATURE_REF,)
                        if level in {5, 11}
                        else ()
                    ),
                )
                for level in range(1, 12)
            ),
        ),
        levels=11,
    )
    entity = result.entity
    receipt = result.composition_receipt
    assert receipt is not None

    assert entity.action_economy.resolve_attacks_per_attack_action() == 3
    assert entity.action_economy.resources["extra_attacks"].maximum == 2
    family_actions = [
        action
        for action in entity.registered_actions
        if action.name == "Extra Attack"
    ]
    assert len(family_actions) == 1
    assert family_actions[0].behavior_binding is not None
    assert (
        family_actions[0].behavior_binding.provided_by_ref
        == EXTRA_ATTACK_FEATURE_REF
    )
    assert len([
        handler
        for handler in entity.event_handlers.values()
        if handler.name == "Extra Attack Resource"
    ]) == 1
    assert "Extra Attack" not in entity.active_conditions

    remove_character_composition(entity, receipt)

    assert entity.action_economy.resolve_attacks_per_attack_action() == 1
    assert "extra_attacks" not in entity.action_economy.resources
    assert all(
        action.name != "Extra Attack"
        for action in entity.registered_actions
    )
    assert all(
        handler.name != "Extra Attack Resource"
        for handler in entity.event_handlers.values()
    )


def test_unimplemented_structural_feature_fails_closed() -> None:
    with pytest.raises(
        RuntimeError,
        match="No structural character applier is installed",
    ):
        _materialize(
            ClassDefinition(
                hit_die=10,
                caster_progression=CasterProgression.NON_CASTER,
                level_definitions=(
                    ClassLevelDefinition(
                        class_level=1,
                        automatic_grant_refs=(
                            CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
                                AegisTrainingFeature
                            ].ref,
                        ),
                    ),
                ),
            ),
            levels=1,
        )
