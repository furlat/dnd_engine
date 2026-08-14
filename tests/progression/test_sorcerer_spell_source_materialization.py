"""Source-owned spell knowledge and runtime spell materialization."""

from collections.abc import Iterator
from dataclasses import replace
from unittest.mock import patch
from uuid import uuid4

import pytest
from pydantic import BaseModel

from dnd.actions import SpellEvent
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingBlock
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.character_build_validation import (
    CharacterBuildIssueCode,
    CharacterBuildValidator,
)
from dnd.content_system.character_materialization import (
    materialize_character,
    remove_character_composition,
)
from dnd.content_system.character_appearance import SORCERER_HUMAN_APPEARANCE
from dnd.content_system.system import LoadedContentSystem
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.content_system.spell_catalog_composition import (
    SPELL_CATALOG_COMPOSITION_BY_CLASS,
    SPELL_CATALOG_COMPOSITION_ROWS,
)
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import (
    ContentDescriptor,
    ContentDescriptorSpec,
    ContentVisibility,
)
from dnd.core.content.durable_characters import RitualPreparationPolicy
from dnd.core.content.durable_characters import (
    AbilityScoreAllocation,
    AbilityScoreName,
    BackgroundDefinition,
    BuildChoiceRequirement,
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
    ChoiceRequirementKind,
    ClassDefinition,
    ClassLevelDefinition,
    ClassLevelEntry,
    ClassLevelId,
    ClassSpellEntitlement,
    FlexibleAbilityBonusSelection,
    MetamagicChoice,
    SpeciesDefinition,
    SpellcastingSourceId,
    SpellKnownChoice,
    SpellReplacementChoice,
)
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
    get_content_declaration,
)
from dnd.core.content.registry import FrozenContentRegistry
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.events import EventPhase, EventType
from dnd.core.progression import CasterProgression
from dnd.entity import Entity, EntityConfig
from dnd.player_character_body import PLAYER_CHARACTER_BODY_RECIPE
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.evocation import FireBolt, MagicMissile
from dnd.spells.abjuration import (
    SHIELD_REACTION_DECLARATION,
    ShieldReactionHandler,
)
from dnd.spells.reaction_spell_content import (
    COUNTERSPELL_SPELL_DECLARATION,
    LEARNED_REACTION_SPELL_SPECS,
    SHIELD_SPELL_DECLARATION,
)


_CONTENT_SET_DIGEST = "8" * 64
_RULESET_DIGEST = "9" * 64
_FIXTURE_PROVENANCE = ContentProvenance(
    primary_source_id="fixture.spell_sources.source",
    source_anchor="complete spell-source fixture definitions",
    relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
    fidelity=ContentFidelity.COMPLETE,
    review_status=ContentReviewStatus.REVIEWED,
    notes=(
        "Fixture definitions are complete for their explicitly declared "
        "test-only mechanics."
    ),
)


@pytest.fixture(autouse=True)
def _reset_runtime() -> Iterator[None]:
    reset_engine_runtime(grid_size=(12, 12))
    yield
    reset_engine_runtime()


def _class_ref(content_id: str) -> ContentRef:
    return ContentRef(
        pack_id="fixture.spell_sources",
        definition_kind=ContentDefinitionKind.CLASS,
        content_id=content_id,
        content_version=1,
        definition_contract_hash="a" * 64,
    )


def _typed_declaration(
    *,
    kind: ContentDefinitionKind,
    content_id: str,
    payload: BaseModel,
    dependencies: tuple[ContentDependency, ...] = (),
) -> ContentDeclaration:
    ref = ContentRef(
        pack_id="fixture.spell_sources",
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
        dependencies=dependencies,
    )


def _feature_declaration(content_id: str) -> ContentDeclaration:
    ref = ContentRef(
        pack_id="fixture.spell_sources",
        definition_kind=ContentDefinitionKind.CLASS_FEATURE,
        content_id=content_id,
        content_version=1,
        definition_contract_hash=compute_definition_contract_hash(
            mode=ContentDeclarationMode.BEHAVIOR_IDENTITY,
            definition_kind=ContentDefinitionKind.CLASS_FEATURE,
            runtime_behavior_kind=RuntimeBehaviorKind.CLASS_FEATURE,
        ),
    )
    return ContentDeclaration(
        ref=ref,
        mode=ContentDeclarationMode.BEHAVIOR_IDENTITY,
        descriptor=ContentDescriptor.from_spec(
            ref,
            ContentDescriptorSpec(
                display_name=content_id,
                visibility=ContentVisibility.DEVELOPER,
            ),
        ),
        provenance=_FIXTURE_PROVENANCE,
        runtime_behavior_kind=RuntimeBehaviorKind.CLASS_FEATURE,
    )
def _spell_dependency(spell_ref: ContentRef) -> ContentDependency:
    return ContentDependency(
        relation=ContentDependencyRelation.GRANTS_SPELL,
        target_ref=spell_ref,
        phase=ContentDependencyPhase.RUNTIME_REFERENCE,
    )


def _caster_definition(
    *,
    source_id: str,
    ability: AbilityScoreName,
    spell_refs: tuple[ContentRef, ...],
    level_definitions: tuple[ClassLevelDefinition, ...],
) -> ClassDefinition:
    ranks = {
        row.declaration.ref.identity_key: row.level
        for row in SPELL_CATALOG_COMPOSITION_ROWS
    }
    return ClassDefinition(
        hit_die=6,
        caster_progression=CasterProgression.FULL_CASTER,
        spellcasting_feature_class_level=1,
        spellcasting_source_id=SpellcastingSourceId(value=source_id),
        spellcasting_ability=ability,
        ritual_policy=RitualPreparationPolicy.KNOWN,
        spell_entitlements=tuple(
            sorted(
                (
                    ClassSpellEntitlement(
                        spell_ref=ref,
                        spell_rank=ranks[ref.identity_key],
                    )
                    for ref in spell_refs
                ),
                key=lambda row: row.spell_ref.identity_key,
            ),
        ),
        level_definitions=level_definitions,
    )


def _loaded_with_classes(
    class_declarations: tuple[ContentDeclaration, ...],
) -> tuple[LoadedContentSystem, ContentRef, ContentRef]:
    built_in = bootstrap_content_system()
    species = _typed_declaration(
        kind=ContentDefinitionKind.SPECIES,
        content_id="species.human",
        payload=SpeciesDefinition(
            runtime_support=OriginRuntimeSupport.available(),
        ),
    )
    background = _typed_declaration(
        kind=ContentDefinitionKind.BACKGROUND,
        content_id="background.sage",
        payload=BackgroundDefinition(
            runtime_support=OriginRuntimeSupport.available(),
        ),
    )
    declarations = dict(built_in.registry.declarations)
    for declaration in (species, background, *class_declarations):
        declarations[declaration.ref.identity_key] = declaration
    return (
        LoadedContentSystem(
            registry=FrozenContentRegistry(
                declarations=declarations,
                recipe_presets=built_in.registry.recipe_presets,
                sources=built_in.registry.sources,
            ),
            built_in_artifact_digest="7" * 64,
            content_set_digest=_CONTENT_SET_DIGEST,
        ),
        species.ref,
        background.ref,
    )


def _definition(
    *,
    species_ref: ContentRef,
    background_ref: ContentRef,
    levels: tuple[ClassLevelEntry, ...],
) -> CharacterDefinitionRevisionV2:
    return CharacterDefinitionRevisionV2.create(
        character_id=uuid4(),
        definition_revision=1,
        body_recipe=PLAYER_CHARACTER_BODY_RECIPE,
        species_ref=species_ref,
        background_ref=background_ref,
        appearance=SORCERER_HUMAN_APPEARANCE,
        base_ability_scores=AbilityScoreAllocation(
            strength=15,
            dexterity=15,
            constitution=15,
            intelligence=8,
            wisdom=8,
            charisma=8,
        ),
        flexible_ability_bonuses=FlexibleAbilityBonusSelection(
            plus_two=AbilityScoreName.CHARISMA,
            plus_one=AbilityScoreName.WISDOM,
        ),
        class_levels=levels,
        earned_character_level=len(levels),
        content_set_digest=_CONTENT_SET_DIGEST,
        ruleset_digest=_RULESET_DIGEST,
    )


def _loadout(
    definition: CharacterDefinitionRevisionV2,
) -> CharacterLoadoutRevisionV1:
    return CharacterLoadoutRevisionV1.create(
        character_id=definition.character_id,
        loadout_revision=1,
        based_on_definition_revision=definition.definition_revision,
    )


def test_spellcasting_source_owns_exact_progression_facts() -> None:
    block = SpellcastingBlock.create(source_entity_uuid=uuid4())
    source_id = uuid4()
    provider_ref = _class_ref("class.sorcerer")

    block.add_source(
        source_id,
        "charisma",
        provider_ref=provider_ref,
        caster_progression=CasterProgression.FULL_CASTER,
        provider_level=5,
        maximum_spell_rank=3,
        ritual_policy=RitualPreparationPolicy.KNOWN,
    )

    source = block.sources[source_id]
    assert source.provider_ref == provider_ref
    assert source.caster_progression is CasterProgression.FULL_CASTER
    assert source.provider_level == 5
    assert source.maximum_spell_rank == 3
    assert source.ritual_policy is RitualPreparationPolicy.KNOWN


def test_learned_reaction_spells_close_exact_handler_dependencies() -> None:
    for spec in LEARNED_REACTION_SPELL_SPECS:
        dependencies = tuple(
            dependency
            for dependency in spec.declaration.dependencies
            if dependency.relation
            is ContentDependencyRelation.INSTALLS_HANDLER
        )
        assert len(dependencies) == 1
        assert dependencies[0].target_ref == get_content_declaration(
            spec.handler_type,
        ).ref
        row = next(
            row
            for row in SPELL_CATALOG_COMPOSITION_ROWS
            if row.declaration == spec.declaration
        )
        assert row.spell_type is None
        assert row.reaction_handler_factory is spec.handler_factory


def test_same_spell_is_owned_and_materialized_once_per_exact_source() -> None:
    fire_ref = SPELL_CATALOG_COMPOSITION_BY_CLASS[FireBolt].declaration.ref
    class_rows: list[ContentDeclaration] = []
    for content_id, source_id, ability, choice_id in (
        (
            "class.arcane",
            "source.arcane",
            AbilityScoreName.CHARISMA,
            "class.arcane.level_1.spell",
        ),
        (
            "class.divine",
            "source.divine",
            AbilityScoreName.WISDOM,
            "class.divine.level_1.spell",
        ),
    ):
        class_rows.append(
            _typed_declaration(
                kind=ContentDefinitionKind.CLASS,
                content_id=content_id,
                payload=_caster_definition(
                    source_id=source_id,
                    ability=ability,
                    spell_refs=(fire_ref,),
                    level_definitions=(
                        ClassLevelDefinition(
                            class_level=1,
                            choice_requirements=(
                                BuildChoiceRequirement(
                                    choice_id=choice_id,
                                    choice_kind=(
                                        ChoiceRequirementKind.SPELL_KNOWN
                                    ),
                                    allowed_refs=(fire_ref,),
                                ),
                            ),
                        ),
                    ),
                ),
                dependencies=(_spell_dependency(fire_ref),),
            ),
        )
    loaded, species_ref, background_ref = _loaded_with_classes(
        tuple(class_rows),
    )
    definition = _definition(
        species_ref=species_ref,
        background_ref=background_ref,
        levels=tuple(
            ClassLevelEntry(
                class_level_id=ClassLevelId(
                    value=("level.one" if index == 1 else "level.two"),
                ),
                character_level=index,
                class_ref=declaration.ref,
                resulting_class_level=1,
                choices=(
                    SpellKnownChoice(
                        choice_id=(
                            f"class."
                            f"{'arcane' if index == 1 else 'divine'}"
                            ".level_1.spell"
                        ),
                        selected_refs=(fire_ref,),
                    ),
                ),
            )
            for index, declaration in enumerate(class_rows, start=1)
        ),
    )
    validation = CharacterBuildValidator(
        loaded,
        expected_ruleset_digest=_RULESET_DIGEST,
    ).validate(definition, _loadout(definition))
    assert validation.issues == ()
    assert validation.preview is not None
    assert len(validation.preview.final_known_spells) == 2
    assert {
        row.spellcasting_source_id.value
        for row in validation.preview.final_known_spells
    } == {"source.arcane", "source.divine"}

    runtime = ContentSystemRuntime()
    runtime.install(loaded)
    result = materialize_character(
        definition=definition,
        holdings=CharacterHoldingsRevision.create(
            character_id=definition.character_id,
            holdings_revision=1,
        ),
        loadout=_loadout(definition),
        runtime_entity_uuid=uuid4(),
        display_name="Two Source Caster",
        faction="heroes",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(role_id="test.spell.sources"),
        expected_ruleset_digest=_RULESET_DIGEST,
        runtime=runtime,
    )
    receipt = result.composition_receipt
    assert receipt is not None
    spells = [
        action
        for action in result.entity.registered_actions
        if isinstance(action, FireBolt)
    ]
    assert len(spells) == 2
    assert len({spell.spellcasting_source_id for spell in spells}) == 2
    assert {
        spell.behavior_binding.provided_by_ref.identity_key
        for spell in spells
        if spell.behavior_binding is not None
    } == {row.ref.identity_key for row in class_rows}
    assert all(
        source.maximum_spell_rank == 1
        and source.ritual_policy is RitualPreparationPolicy.KNOWN
        for source in result.entity.spellcasting.sources.values()
    )

    remove_character_composition(result.entity, receipt)
    assert not any(
        isinstance(action, FireBolt)
        for action in result.entity.registered_actions
    )
    assert result.entity.spellcasting.sources == {}


def test_replacement_is_source_local_and_materializes_only_final_spell() -> None:
    fire_ref = SPELL_CATALOG_COMPOSITION_BY_CLASS[FireBolt].declaration.ref
    missile_ref = (
        SPELL_CATALOG_COMPOSITION_BY_CLASS[MagicMissile].declaration.ref
    )
    class_declaration = _typed_declaration(
        kind=ContentDefinitionKind.CLASS,
        content_id="class.sorcerer",
        payload=_caster_definition(
            source_id="source.sorcerer",
            ability=AbilityScoreName.CHARISMA,
            spell_refs=(fire_ref, missile_ref),
            level_definitions=(
                ClassLevelDefinition(
                    class_level=1,
                    choice_requirements=(
                        BuildChoiceRequirement(
                            choice_id="class.sorcerer.level_1.spell",
                            choice_kind=ChoiceRequirementKind.SPELL_KNOWN,
                            allowed_refs=(missile_ref,),
                        ),
                    ),
                ),
                ClassLevelDefinition(
                    class_level=2,
                    choice_requirements=(
                        BuildChoiceRequirement(
                            choice_id="class.sorcerer.level_2.replace",
                            choice_kind=(
                                ChoiceRequirementKind.SPELL_REPLACEMENT
                            ),
                            allowed_refs=(fire_ref,),
                        ),
                    ),
                ),
            ),
        ),
        dependencies=(
            _spell_dependency(fire_ref),
            _spell_dependency(missile_ref),
        ),
    )
    loaded, species_ref, background_ref = _loaded_with_classes(
        (class_declaration,),
    )
    levels = (
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.one"),
            character_level=1,
            class_ref=class_declaration.ref,
            resulting_class_level=1,
            choices=(
                SpellKnownChoice(
                    choice_id="class.sorcerer.level_1.spell",
                    selected_refs=(missile_ref,),
                ),
            ),
        ),
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.two"),
            character_level=2,
            class_ref=class_declaration.ref,
            resulting_class_level=2,
            choices=(
                SpellReplacementChoice(
                    choice_id="class.sorcerer.level_2.replace",
                    replaced_spell_ref=missile_ref,
                    learned_spell_ref=fire_ref,
                ),
            ),
        ),
    )
    definition = _definition(
        species_ref=species_ref,
        background_ref=background_ref,
        levels=levels,
    )
    validation = CharacterBuildValidator(
        loaded,
        expected_ruleset_digest=_RULESET_DIGEST,
    ).validate(definition, _loadout(definition))
    assert validation.issues == ()
    assert validation.preview is not None
    assert tuple(
        row.spell_ref for row in validation.preview.final_known_spells
    ) == (fire_ref,)

    runtime = ContentSystemRuntime()
    runtime.install(loaded)
    result = materialize_character(
        definition=definition,
        holdings=CharacterHoldingsRevision.create(
            character_id=definition.character_id,
            holdings_revision=1,
        ),
        loadout=_loadout(definition),
        runtime_entity_uuid=uuid4(),
        display_name="Replacement Caster",
        faction="heroes",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id="test.spell.replacement",
        ),
        expected_ruleset_digest=_RULESET_DIGEST,
        runtime=runtime,
    )
    assert sum(
        isinstance(action, FireBolt)
        for action in result.entity.registered_actions
    ) == 1
    assert not any(
        isinstance(action, MagicMissile)
        for action in result.entity.registered_actions
    )

    invalid_levels = (
        levels[0],
        levels[1].model_copy(
            update={
                "choices": (
                    SpellReplacementChoice(
                        choice_id="class.sorcerer.level_2.replace",
                        replaced_spell_ref=fire_ref,
                        learned_spell_ref=missile_ref,
                    ),
                ),
            },
        ),
    )
    invalid = _definition(
        species_ref=species_ref,
        background_ref=background_ref,
        levels=invalid_levels,
    )
    rejected = CharacterBuildValidator(
        loaded,
        expected_ruleset_digest=_RULESET_DIGEST,
    ).validate(invalid, _loadout(invalid))
    assert rejected.preview is None
    assert {
        CharacterBuildIssueCode.SPELL_REPLACEMENT_SOURCE_MISMATCH,
        CharacterBuildIssueCode.SPELL_REPLACEMENT_DUPLICATE,
    }.issubset({issue.code for issue in rejected.issues})


def test_metamagic_cannot_be_selected_again_at_a_later_level() -> None:
    option = _feature_declaration("metamagic.quickened")
    class_declaration = _typed_declaration(
        kind=ContentDefinitionKind.CLASS,
        content_id="class.sorcerer",
        payload=_caster_definition(
            source_id="source.sorcerer",
            ability=AbilityScoreName.CHARISMA,
            spell_refs=(),
            level_definitions=tuple(
                ClassLevelDefinition(
                    class_level=level,
                    choice_requirements=(
                        BuildChoiceRequirement(
                            choice_id=(
                                f"class.sorcerer.level_{level}.metamagic"
                            ),
                            choice_kind=ChoiceRequirementKind.METAMAGIC,
                            allowed_refs=(option.ref,),
                        ),
                    ),
                )
                for level in (1, 2)
            ),
        ),
    )
    loaded, species_ref, background_ref = _loaded_with_classes(
        (class_declaration, option),
    )
    definition = _definition(
        species_ref=species_ref,
        background_ref=background_ref,
        levels=tuple(
            ClassLevelEntry(
                class_level_id=ClassLevelId(
                    value=("level.one" if level == 1 else "level.two"),
                ),
                character_level=level,
                class_ref=class_declaration.ref,
                resulting_class_level=level,
                choices=(
                    MetamagicChoice(
                        choice_id=(
                            f"class.sorcerer.level_{level}.metamagic"
                        ),
                        selected_refs=(option.ref,),
                    ),
                ),
            )
            for level in (1, 2)
        ),
    )

    result = CharacterBuildValidator(
        loaded,
        expected_ruleset_digest=_RULESET_DIGEST,
    ).validate(definition, _loadout(definition))

    assert result.preview is None
    assert CharacterBuildIssueCode.DUPLICATE_METAMAGIC in {
        issue.code for issue in result.issues
    }


def test_learned_shield_installs_one_shared_exact_handler() -> None:
    shield_ref = SHIELD_SPELL_DECLARATION.ref
    class_rows: list[ContentDeclaration] = []
    for content_id, source_id, ability, choice_id in (
        (
            "class.arcane",
            "source.arcane",
            AbilityScoreName.CHARISMA,
            "class.arcane.level_1.spell",
        ),
        (
            "class.divine",
            "source.divine",
            AbilityScoreName.WISDOM,
            "class.divine.level_1.spell",
        ),
    ):
        class_rows.append(
            _typed_declaration(
                kind=ContentDefinitionKind.CLASS,
                content_id=content_id,
                payload=_caster_definition(
                    source_id=source_id,
                    ability=ability,
                    spell_refs=(shield_ref,),
                    level_definitions=(
                        ClassLevelDefinition(
                            class_level=1,
                            choice_requirements=(
                                BuildChoiceRequirement(
                                    choice_id=choice_id,
                                    choice_kind=(
                                        ChoiceRequirementKind.SPELL_KNOWN
                                    ),
                                    allowed_refs=(shield_ref,),
                                ),
                            ),
                        ),
                    ),
                ),
                dependencies=(_spell_dependency(shield_ref),),
            ),
        )
    loaded, species_ref, background_ref = _loaded_with_classes(
        tuple(class_rows),
    )
    definition = _definition(
        species_ref=species_ref,
        background_ref=background_ref,
        levels=tuple(
            ClassLevelEntry(
                class_level_id=ClassLevelId(
                    value="level.one" if index == 1 else "level.two",
                ),
                character_level=index,
                class_ref=declaration.ref,
                resulting_class_level=1,
                choices=(
                    SpellKnownChoice(
                        choice_id=(
                            "class.arcane.level_1.spell"
                            if index == 1
                            else "class.divine.level_1.spell"
                        ),
                        selected_refs=(shield_ref,),
                    ),
                ),
            )
            for index, declaration in enumerate(class_rows, start=1)
        ),
    )
    runtime = ContentSystemRuntime()
    runtime.install(loaded)
    result = materialize_character(
        definition=definition,
        holdings=CharacterHoldingsRevision.create(
            character_id=definition.character_id,
            holdings_revision=1,
        ),
        loadout=_loadout(definition),
        runtime_entity_uuid=uuid4(),
        display_name="Two Source Shield Caster",
        faction="heroes",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id="test.learned.reaction.shared",
        ),
        expected_ruleset_digest=_RULESET_DIGEST,
        runtime=runtime,
    )
    receipt = result.composition_receipt
    assert receipt is not None
    handlers = [
        handler
        for handler in result.entity.event_handlers.values()
        if isinstance(handler, ShieldReactionHandler)
    ]
    assert len(handlers) == 1
    handler = handlers[0]
    assert handler.behavior_binding is not None
    assert handler.behavior_binding.definition_ref == (
        SHIELD_REACTION_DECLARATION.ref
    )
    assert handler.behavior_binding.provided_by_ref == shield_ref
    assert len(
        result.entity.spellcasting.learned_reaction_spell_source_ids(
            shield_ref,
        ),
    ) == 2
    assert not any(
        action.behavior_binding is not None
        and action.behavior_binding.definition_ref == shield_ref
        for action in result.entity.registered_actions
    )

    spell_grants = tuple(
        grant
        for grant in receipt.grants
        if grant.definition_ref == shield_ref
    )
    assert len(spell_grants) == 2
    remove_character_composition(
        result.entity,
        replace(receipt, grants=(spell_grants[0],)),
    )
    assert handler.uuid in result.entity.event_handlers
    assert len(
        result.entity.spellcasting.learned_reaction_spell_source_ids(
            shield_ref,
        ),
    ) == 1

    remove_character_composition(
        result.entity,
        replace(receipt, grants=(spell_grants[1],)),
    )
    assert handler.uuid not in result.entity.event_handlers
    assert (
        result.entity.spellcasting.learned_reaction_spell_source_ids(
            shield_ref,
        )
        == ()
    )
    remove_character_composition(
        result.entity,
        replace(
            receipt,
            grants=tuple(
                grant
                for grant in receipt.grants
                if grant not in spell_grants
            ),
        ),
    )


def test_counterspell_uses_strongest_exact_learned_source_ability() -> None:
    caster = Entity.create(
        source_entity_uuid=uuid4(),
        name="Caster",
        config=EntityConfig(position=(2, 2), faction="heroes"),
    )
    counterspeller = Entity.create(
        source_entity_uuid=uuid4(),
        name="Counterspeller",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                intelligence=AbilityConfig(ability_score=8),
                wisdom=AbilityConfig(ability_score=20),
            ),
            action_economy=ActionEconomyConfig(spell_slots={3: 1}),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=6,
                        hit_dice_count=5,
                        mode="maximums",
                    ),
                ],
            ),
            position=(6, 2),
            faction="monsters",
        ),
    )
    intelligence_source = uuid4()
    wisdom_source = uuid4()
    counterspeller.spellcasting.add_source(
        intelligence_source,
        "intelligence",
        provider_ref=_class_ref("class.intelligence"),
        caster_progression=CasterProgression.FULL_CASTER,
        provider_level=5,
        maximum_spell_rank=3,
        ritual_policy=RitualPreparationPolicy.KNOWN,
    )
    counterspeller.spellcasting.add_source(
        wisdom_source,
        "wisdom",
        provider_ref=_class_ref("class.wisdom"),
        caster_progression=CasterProgression.FULL_CASTER,
        provider_level=5,
        maximum_spell_rank=3,
        ritual_policy=RitualPreparationPolicy.KNOWN,
    )
    counterspell_spec = next(
        spec
        for spec in LEARNED_REACTION_SPELL_SPECS
        if spec.declaration == COUNTERSPELL_SPELL_DECLARATION
    )
    handler = counterspell_spec.handler_factory(counterspeller.uuid)
    for source_id in (intelligence_source, wisdom_source):
        counterspeller.spellcasting.add_learned_reaction_spell_source(
            spell_ref=COUNTERSPELL_SPELL_DECLARATION.ref,
            source_id=source_id,
            handler_uuid=handler.uuid,
        )
    Entity.update_all_entities_senses()
    event = SpellEvent(
        name="Incoming Level Six Spell",
        event_type=EventType.CAST_SPELL,
        phase=EventPhase.EXECUTION,
        source_entity_uuid=caster.uuid,
        target_entity_uuid=counterspeller.uuid,
        spell_level=6,
        cast_at_level=6,
    )

    with patch("dnd.spells.abjuration.random.randint", return_value=11):
        result = handler(event)

    assert result is not None
    assert result.canceled
    assert counterspeller.action_economy.spell_slot_3.normalized_score == 0
