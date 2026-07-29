"""Focused validation for authenticated schema-2 character builds."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from dnd.content_system.character_build_validation import (
    CharacterBuildIssueCode,
    CharacterGrantScheduleKind,
    CharacterGrantSourceKind,
    CharacterBuildValidator,
)
from dnd.content_system.character_appearance import FIGHTER_HUMAN_APPEARANCE
from dnd.content_system.pack_loader import LoadedContentSystem
from dnd.core.content.descriptors import (
    ContentDescriptor,
    ContentDescriptorSpec,
    ContentVisibility,
)
from dnd.core.content.durable_characters import (
    AbilityScoreAllocation,
    AbilityScoreImprovementChoice,
    AbilityScoreName,
    AbilityScorePrerequisite,
    AllOfPrerequisite,
    AnyOfPrerequisite,
    BackgroundDefinition,
    BuildChoiceRequirement,
    CantripChoice,
    CharacterAppearanceSelection,
    CharacterDefinitionRevisionV2,
    CharacterLoadoutRevisionV1,
    ChoiceRequirementKind,
    ClassDefinition,
    ClassLevelDefinition,
    ClassLevelEntry,
    ClassLevelId,
    ClassLevelPrerequisite,
    ClassProficiencyPackage,
    ClassSpellEntitlement,
    ClassSkillChoice,
    PreparedSpellSourceLoadout,
    SpeciesDefinition,
    SpeciesVariantDefinition,
    SpellcastingSourceId,
    SpellKnownChoice,
    SpellReplacementChoice,
    SubclassChoice,
    SubclassDefinition,
    FeatChoice,
    FlexibleAbilityBonusSelection,
    FightingStyleChoice,
    HasFeaturePrerequisite,
    KnowsSpellPrerequisite,
    NotPrerequisite,
    OriginLevelGrant,
    ProficiencySubject,
    ProficiencySubjectKind,
    StartingProficiencyChoice,
    TotalCharacterLevelPrerequisite,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.origin_support import OriginRuntimeSupport
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import (
    ContentConstruction,
    ContentDeclaration,
    ContentDeclarationMode,
    compute_definition_contract_hash,
)
from dnd.core.content.registry import FrozenContentRegistry
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.progression import (
    CasterProgression,
    MulticlassSlotRoundingPolicy,
)


_PACK_ID = "fixture.character_validation"
_CONTENT_SET_DIGEST = "c" * 64
_RULESET_DIGEST = "d" * 64
_PROVENANCE = ContentProvenance(
    primary_source_id="fixture.character_validation.source",
    source_anchor="character validator fixture",
    relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
    fidelity=ContentFidelity.COMPLETE,
    review_status=ContentReviewStatus.REVIEWED,
    notes=(
        "Complete for the exact mechanics declared by the character validator "
        "fixture."
    ),
)


class _BodyParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    body_id: str = Field(min_length=1)


def _body_factory(_context: object, _parameters: BaseModel) -> object:
    raise AssertionError("pure build validation must not execute body factories")


def _descriptor(ref: ContentRef, display_name: str) -> ContentDescriptor:
    tags: tuple[str, ...] = ()
    if ref.definition_kind in {
        ContentDefinitionKind.SPECIES,
        ContentDefinitionKind.SPECIES_VARIANT,
        ContentDefinitionKind.BACKGROUND,
    }:
        tags = ("character_creation", "player_capable")
    elif ref.content_id == "creature.player_body":
        tags = ("character_body", "player_capable")
    return ContentDescriptor.from_spec(
        ref,
        ContentDescriptorSpec(
            display_name=display_name,
            tags=tags,
            visibility=ContentVisibility.PUBLIC,
        ),
    )


def _typed_declaration(
    kind: ContentDefinitionKind,
    content_id: str,
    payload: BaseModel,
) -> ContentDeclaration:
    contract_hash = compute_definition_contract_hash(
        mode=ContentDeclarationMode.TYPED_DEFINITION,
        definition_kind=kind,
        definition_model=type(payload),
    )
    ref = ContentRef(
        pack_id=_PACK_ID,
        definition_kind=kind,
        content_id=content_id,
        content_version=1,
        definition_contract_hash=contract_hash,
    )
    return ContentDeclaration(
        ref=ref,
        mode=ContentDeclarationMode.TYPED_DEFINITION,
        descriptor=_descriptor(ref, content_id),
        provenance=_PROVENANCE,
        definition_payload=payload,
    )


def _behavior_declaration(
    kind: ContentDefinitionKind,
    content_id: str,
    runtime_kind: RuntimeBehaviorKind,
) -> ContentDeclaration:
    contract_hash = compute_definition_contract_hash(
        mode=ContentDeclarationMode.BEHAVIOR_IDENTITY,
        definition_kind=kind,
        runtime_behavior_kind=runtime_kind,
    )
    ref = ContentRef(
        pack_id=_PACK_ID,
        definition_kind=kind,
        content_id=content_id,
        content_version=1,
        definition_contract_hash=contract_hash,
    )
    return ContentDeclaration(
        ref=ref,
        mode=ContentDeclarationMode.BEHAVIOR_IDENTITY,
        descriptor=_descriptor(ref, content_id),
        provenance=_PROVENANCE,
        runtime_behavior_kind=runtime_kind,
    )


def _body_declaration() -> ContentDeclaration:
    contract_hash = compute_definition_contract_hash(
        mode=ContentDeclarationMode.FACTORY,
        definition_kind=ContentDefinitionKind.CREATURE,
        parameter_model=_BodyParameters,
    )
    ref = ContentRef(
        pack_id=_PACK_ID,
        definition_kind=ContentDefinitionKind.CREATURE,
        content_id="creature.player_body",
        content_version=1,
        definition_contract_hash=contract_hash,
    )
    return ContentDeclaration(
        ref=ref,
        mode=ContentDeclarationMode.FACTORY,
        descriptor=_descriptor(ref, "Player body"),
        provenance=_PROVENANCE,
        construction=ContentConstruction(
            parameter_model=_BodyParameters,
            factory=_body_factory,
        ),
    )


@dataclass(frozen=True, slots=True)
class _Fixture:
    loaded: LoadedContentSystem
    body_ref: ContentRef
    species_ref: ContentRef
    variant_ref: ContentRef
    background_ref: ContentRef
    fighter_ref: ContentRef
    sorcerer_ref: ContentRef
    champion_ref: ContentRef
    grant_refs: tuple[ContentRef, ...]
    spell_ref: ContentRef


def _fixture() -> _Fixture:
    body = _body_declaration()
    grants = tuple(
        _behavior_declaration(
            ContentDefinitionKind.CLASS_FEATURE,
            content_id,
            RuntimeBehaviorKind.CLASS_FEATURE,
        )
        for content_id in (
            "feature.background",
            "feature.fighter.one",
            "feature.sorcerer.one",
            "feature.species",
            "feature.variant",
        )
    )
    spell = _behavior_declaration(
        ContentDefinitionKind.SPELL,
        "spell.fire_bolt",
        RuntimeBehaviorKind.SPELL,
    )
    species = _typed_declaration(
        ContentDefinitionKind.SPECIES,
        "species.human",
        SpeciesDefinition(
            runtime_support=OriginRuntimeSupport.available(),
            level_grants=(
                OriginLevelGrant(
                    character_level=1,
                    grant_refs=(grants[3].ref,),
                ),
            ),
        ),
    )
    variant = _typed_declaration(
        ContentDefinitionKind.SPECIES_VARIANT,
        "species_variant.human_variant",
        SpeciesVariantDefinition(
            parent_species_ref=species.ref,
            runtime_support=OriginRuntimeSupport.available(),
            level_grants=(
                OriginLevelGrant(
                    character_level=1,
                    grant_refs=(grants[4].ref,),
                ),
            ),
        ),
    )
    background = _typed_declaration(
        ContentDefinitionKind.BACKGROUND,
        "background.soldier",
        BackgroundDefinition(
            runtime_support=OriginRuntimeSupport.available(),
            automatic_grant_refs=(grants[0].ref,),
        ),
    )
    champion_placeholder = _typed_declaration(
        ContentDefinitionKind.SUBCLASS,
        "subclass.champion",
        SubclassDefinition(
            parent_class_ref=ContentRef(
                pack_id=_PACK_ID,
                definition_kind=ContentDefinitionKind.CLASS,
                content_id="class.fighter",
                content_version=1,
                definition_contract_hash=compute_definition_contract_hash(
                    mode=ContentDeclarationMode.TYPED_DEFINITION,
                    definition_kind=ContentDefinitionKind.CLASS,
                    definition_model=ClassDefinition,
                ),
            ),
        ),
    )
    fighter = _typed_declaration(
        ContentDefinitionKind.CLASS,
        "class.fighter",
        ClassDefinition(
            hit_die=10,
            caster_progression=CasterProgression.NON_CASTER,
            multiclass_prerequisite=AbilityScorePrerequisite(
                ability=AbilityScoreName.STRENGTH,
                minimum=13,
            ),
            first_class_proficiencies=ClassProficiencyPackage(
                automatic=(
                    ProficiencySubject(
                        subject_kind=ProficiencySubjectKind.WEAPON,
                        subject_id="weapon.martial",
                    ),
                ),
                choices=(
                    BuildChoiceRequirement(
                        choice_id="fighter.first.skills",
                        choice_kind=ChoiceRequirementKind.CLASS_SKILL,
                        minimum_selections=1,
                        maximum_selections=1,
                        allowed_proficiency_subjects=(
                            ProficiencySubject(
                                subject_kind=ProficiencySubjectKind.SKILL,
                                subject_id="skill.athletics",
                            ),
                            ProficiencySubject(
                                subject_kind=ProficiencySubjectKind.SKILL,
                                subject_id="skill.perception",
                            ),
                        ),
                    ),
                    BuildChoiceRequirement(
                        choice_id="fighter.first.starting_proficiency",
                        choice_kind=(
                            ChoiceRequirementKind.STARTING_PROFICIENCY
                        ),
                        allowed_proficiency_subjects=(
                            ProficiencySubject(
                                subject_kind=ProficiencySubjectKind.ARMOR,
                                subject_id="armor.light",
                            ),
                        ),
                    ),
                ),
            ),
            saving_throw_proficiencies=(
                AbilityScoreName.CONSTITUTION,
                AbilityScoreName.STRENGTH,
            ),
            level_definitions=(
                ClassLevelDefinition(
                    class_level=1,
                    automatic_grant_refs=(grants[1].ref,),
                ),
                ClassLevelDefinition(class_level=2),
                ClassLevelDefinition(
                    class_level=3,
                    choice_requirements=(
                        BuildChoiceRequirement(
                            choice_id="fighter.subclass",
                            choice_kind=ChoiceRequirementKind.SUBCLASS,
                            allowed_refs=(champion_placeholder.ref,),
                        ),
                    ),
                ),
            ),
        ),
    )
    assert champion_placeholder.definition_payload is not None
    champion = champion_placeholder.model_copy(
        update={
            "definition_payload": SubclassDefinition(
                parent_class_ref=fighter.ref,
            ),
        },
    )
    sorcerer = _typed_declaration(
        ContentDefinitionKind.CLASS,
        "class.sorcerer",
        ClassDefinition(
            hit_die=6,
            caster_progression=CasterProgression.FULL_CASTER,
            spellcasting_feature_class_level=1,
            spellcasting_source_id=SpellcastingSourceId(
                value="class.sorcerer",
            ),
            spellcasting_ability=AbilityScoreName.CHARISMA,
            spell_entitlements=(
                ClassSpellEntitlement(
                    spell_ref=spell.ref,
                    spell_rank=0,
                ),
            ),
            multiclass_prerequisite=AbilityScorePrerequisite(
                ability=AbilityScoreName.CHARISMA,
                minimum=13,
            ),
            multiclass_proficiencies=ClassProficiencyPackage(
                automatic=(
                    ProficiencySubject(
                        subject_kind=ProficiencySubjectKind.WEAPON,
                        subject_id="weapon.simple",
                    ),
                ),
                choices=(
                    BuildChoiceRequirement(
                        choice_id="sorcerer.multiclass.skill",
                        choice_kind=ChoiceRequirementKind.CLASS_SKILL,
                        minimum_selections=1,
                        maximum_selections=1,
                    ),
                ),
            ),
            level_definitions=(
                ClassLevelDefinition(
                    class_level=1,
                    automatic_grant_refs=(grants[2].ref,),
                    choice_requirements=(
                        BuildChoiceRequirement(
                            choice_id="sorcerer.cantrip",
                            choice_kind=ChoiceRequirementKind.CANTRIP,
                            allowed_refs=(spell.ref,),
                        ),
                    ),
                ),
            ),
        ),
    )
    declarations = (
        body,
        *grants,
        spell,
        species,
        variant,
        background,
        fighter,
        champion,
        sorcerer,
    )
    registry = FrozenContentRegistry(
        declarations={row.ref.identity_key: row for row in declarations},
        recipe_presets={},
        sources={},
    )
    return _Fixture(
        loaded=LoadedContentSystem(
            registry=registry,
            packs=(),
            built_in_artifact_digest="b" * 64,
            content_set_digest=_CONTENT_SET_DIGEST,
        ),
        body_ref=body.ref,
        species_ref=species.ref,
        variant_ref=variant.ref,
        background_ref=background.ref,
        fighter_ref=fighter.ref,
        sorcerer_ref=sorcerer.ref,
        champion_ref=champion.ref,
        grant_refs=tuple(row.ref for row in grants),
        spell_ref=spell.ref,
    )


def _replace_loaded_declaration(
    fixture: _Fixture,
    declaration: ContentDeclaration,
) -> LoadedContentSystem:
    declarations = dict(fixture.loaded.registry.declarations)
    declarations[declaration.ref.identity_key] = declaration
    return LoadedContentSystem(
        registry=FrozenContentRegistry(
            declarations=declarations,
            recipe_presets=fixture.loaded.registry.recipe_presets,
            sources=fixture.loaded.registry.sources,
        ),
        packs=fixture.loaded.packs,
        built_in_artifact_digest=fixture.loaded.built_in_artifact_digest,
        content_set_digest=fixture.loaded.content_set_digest,
    )


def _definition(
    fixture: _Fixture,
    *,
    class_levels: tuple[ClassLevelEntry, ...] | None = None,
    content_set_digest: str = _CONTENT_SET_DIGEST,
    ruleset_digest: str = _RULESET_DIGEST,
) -> CharacterDefinitionRevisionV2:
    levels = class_levels or (
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.one"),
            character_level=1,
            class_ref=fixture.fighter_ref,
            resulting_class_level=1,
            choices=(
                ClassSkillChoice(
                    choice_id="fighter.first.skills",
                    skills=("athletics",),
                ),
                StartingProficiencyChoice(
                    choice_id="fighter.first.starting_proficiency",
                    proficiencies=(
                        ProficiencySubject(
                            subject_kind=ProficiencySubjectKind.ARMOR,
                            subject_id="armor.light",
                        ),
                    ),
                ),
            ),
        ),
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.two"),
            character_level=2,
            class_ref=fixture.sorcerer_ref,
            resulting_class_level=1,
            choices=(
                CantripChoice(
                    choice_id="sorcerer.cantrip",
                    selected_refs=(fixture.spell_ref,),
                ),
                ClassSkillChoice(
                    choice_id="sorcerer.multiclass.skill",
                    skills=("arcana",),
                ),
            ),
        ),
    )
    return CharacterDefinitionRevisionV2.create(
        character_id=uuid4(),
        definition_revision=3,
        body_recipe=ContentRecipe.create(
            ref=fixture.body_ref,
            parameters={"body_id": "humanoid"},
        ),
        species_ref=fixture.species_ref,
        species_variant_ref=fixture.variant_ref,
        background_ref=fixture.background_ref,
        appearance=FIGHTER_HUMAN_APPEARANCE,
        base_ability_scores=AbilityScoreAllocation(
            strength=15,
            dexterity=15,
            constitution=15,
            intelligence=8,
            wisdom=8,
            charisma=8,
        ),
        flexible_ability_bonuses=FlexibleAbilityBonusSelection(
            plus_two=AbilityScoreName.STRENGTH,
            plus_one=AbilityScoreName.CONSTITUTION,
        ),
        class_levels=levels,
        earned_character_level=len(levels),
        content_set_digest=content_set_digest,
        ruleset_digest=ruleset_digest,
    )


def _validator(fixture: _Fixture) -> CharacterBuildValidator:
    return CharacterBuildValidator(
        fixture.loaded,
        expected_ruleset_digest=_RULESET_DIGEST,
        multiclass_slot_rounding_policy=(
            MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
        ),
    )


def _with_sorcerer_prerequisite(
    fixture: _Fixture,
    prerequisite,
) -> LoadedContentSystem:
    declarations = dict(fixture.loaded.registry.declarations)
    declaration = declarations[fixture.sorcerer_ref.identity_key]
    payload = declaration.definition_payload
    assert isinstance(payload, ClassDefinition)
    declarations[fixture.sorcerer_ref.identity_key] = declaration.model_copy(
        update={
            "definition_payload": payload.model_copy(
                update={"multiclass_prerequisite": prerequisite},
            ),
        },
    )
    return LoadedContentSystem(
        registry=FrozenContentRegistry(
            declarations=declarations,
            recipe_presets={},
            sources={},
        ),
        packs=(),
        built_in_artifact_digest="b" * 64,
        content_set_digest=_CONTENT_SET_DIGEST,
    )


def _loadout(
    definition: CharacterDefinitionRevisionV2,
    *,
    based_on_definition_revision: int | None = None,
    prepared_spells: tuple[PreparedSpellSourceLoadout, ...] = (),
) -> CharacterLoadoutRevisionV1:
    return CharacterLoadoutRevisionV1.create(
        character_id=definition.character_id,
        loadout_revision=1,
        based_on_definition_revision=(
            definition.definition_revision
            if based_on_definition_revision is None
            else based_on_definition_revision
        ),
        prepared_spells=prepared_spells,
    )


def _replace_definition(
    definition: CharacterDefinitionRevisionV2,
    **updates,
) -> CharacterDefinitionRevisionV2:
    values = {
        "character_id": definition.character_id,
        "definition_revision": definition.definition_revision,
        "body_recipe": definition.body_recipe,
        "species_ref": definition.species_ref,
        "species_variant_ref": definition.species_variant_ref,
        "background_ref": definition.background_ref,
        "immutable_origin_choices": definition.immutable_origin_choices,
        "appearance": definition.appearance,
        "base_ability_scores": definition.base_ability_scores,
        "flexible_ability_bonuses": definition.flexible_ability_bonuses,
        "class_levels": definition.class_levels,
        "premade_id": definition.premade_id,
        "earned_character_level": definition.earned_character_level,
        "content_set_digest": definition.content_set_digest,
        "ruleset_digest": definition.ruleset_digest,
    }
    values.update(updates)
    return CharacterDefinitionRevisionV2.create(**values)


def _codes(result) -> set[CharacterBuildIssueCode]:
    return {issue.code for issue in result.issues}


def test_valid_multiclass_build_returns_deterministic_pure_preview() -> None:
    fixture = _fixture()
    definition = _definition(fixture)

    result = _validator(fixture).validate(
        definition,
        _loadout(definition),
    )

    assert result.issues == ()
    assert result.preview is not None
    assert result.preview.class_level_counts == (
        (fixture.fighter_ref, 1),
        (fixture.sorcerer_ref, 1),
    )
    assert result.preview.automatic_grant_refs == (
        fixture.grant_refs[3],
        fixture.grant_refs[4],
        fixture.grant_refs[0],
        fixture.grant_refs[1],
        fixture.grant_refs[2],
    )
    assert result.preview.effective_spellcaster_level == 1
    assert result.preview.normal_spell_slots == ((1, 2),)


def test_origin_runtime_support_alone_controls_build_availability() -> None:
    fixture = _fixture()
    definition = _definition(fixture)
    species = fixture.loaded.registry.declarations[
        fixture.species_ref.identity_key
    ]
    assert isinstance(species.definition_payload, SpeciesDefinition)

    blocked_species = species.model_copy(
        update={
            "definition_payload": species.definition_payload.model_copy(
                update={
                    "runtime_support": OriginRuntimeSupport.blocked(
                        "Fixture origin mechanics are intentionally unavailable.",
                    ),
                },
            ),
        },
    )
    blocked_result = CharacterBuildValidator(
        _replace_loaded_declaration(fixture, blocked_species),
        expected_ruleset_digest=_RULESET_DIGEST,
    ).validate(definition, _loadout(definition))

    assert blocked_result.preview is None
    blocked_issue = next(
        issue
        for issue in blocked_result.issues
        if issue.code is CharacterBuildIssueCode.ORIGIN_IMPLEMENTATION_BLOCKED
    )
    assert blocked_issue.path == ("species_ref",)
    assert blocked_issue.detail == (
        "Fixture origin mechanics are intentionally unavailable."
    )
    assert "player_capable" in blocked_species.descriptor.tags
    assert blocked_species.provenance.fidelity is ContentFidelity.COMPLETE

    available_without_legacy_signals = species.model_copy(
        update={
            "descriptor": species.descriptor.model_copy(
                update={"tags": ("character_creation",)},
            ),
            "provenance": species.provenance.model_copy(
                update={
                    "fidelity": ContentFidelity.BLOCKED,
                    "notes": "Source-review state must not control execution.",
                },
            ),
        },
    )
    available_result = CharacterBuildValidator(
        _replace_loaded_declaration(
            fixture,
            available_without_legacy_signals,
        ),
        expected_ruleset_digest=_RULESET_DIGEST,
    ).validate(definition, _loadout(definition))

    assert available_result.issues == ()
    assert available_result.preview is not None


def test_empty_appearance_selection_fails_closed() -> None:
    """A durable character never receives an inferred renderer identity."""
    fixture = _fixture()
    definition = _replace_definition(
        _definition(fixture),
        appearance=CharacterAppearanceSelection(),
    )

    result = _validator(fixture).validate(
        definition,
        _loadout(definition),
    )

    assert result.preview is None
    assert _codes(result) == {
        CharacterBuildIssueCode.APPEARANCE_SELECTION_INVALID,
    }


def test_grant_schedule_preserves_authored_ledger_order_and_provenance() -> None:
    fixture = _fixture()
    definition = _definition(fixture)
    validator = _validator(fixture)

    first = validator.validate(definition, _loadout(definition))
    second = validator.validate(definition, _loadout(definition))

    assert first.preview is not None
    assert second.preview is not None
    schedule = first.preview.grant_schedule
    assert schedule == second.preview.grant_schedule
    assert len({row.grant_token for row in schedule}) == len(schedule)
    assert tuple((row.kind, row.provenance.source_kind) for row in schedule) == (
        (
            CharacterGrantScheduleKind.AUTOMATIC_CONTENT,
            CharacterGrantSourceKind.SPECIES,
        ),
        (
            CharacterGrantScheduleKind.AUTOMATIC_CONTENT,
            CharacterGrantSourceKind.SPECIES_VARIANT,
        ),
        (
            CharacterGrantScheduleKind.AUTOMATIC_CONTENT,
            CharacterGrantSourceKind.BACKGROUND,
        ),
        (
            CharacterGrantScheduleKind.PROFICIENCY,
            CharacterGrantSourceKind.FIRST_CLASS_PACKAGE,
        ),
        (
            CharacterGrantScheduleKind.PROFICIENCY,
            CharacterGrantSourceKind.FIRST_CLASS_PACKAGE,
        ),
        (
            CharacterGrantScheduleKind.PROFICIENCY,
            CharacterGrantSourceKind.FIRST_CLASS_PACKAGE,
        ),
        (
            CharacterGrantScheduleKind.AUTOMATIC_CONTENT,
            CharacterGrantSourceKind.CLASS_LEVEL,
        ),
        (
            CharacterGrantScheduleKind.PROFICIENCY,
            CharacterGrantSourceKind.FIRST_CLASS_PACKAGE,
        ),
        (
            CharacterGrantScheduleKind.PROFICIENCY,
            CharacterGrantSourceKind.FIRST_CLASS_PACKAGE,
        ),
        (
            CharacterGrantScheduleKind.PROFICIENCY,
            CharacterGrantSourceKind.MULTICLASS_CLASS_PACKAGE,
        ),
        (
            CharacterGrantScheduleKind.AUTOMATIC_CONTENT,
            CharacterGrantSourceKind.CLASS_LEVEL,
        ),
        (
            CharacterGrantScheduleKind.SPELL_LEARN,
            CharacterGrantSourceKind.CLASS_LEVEL,
        ),
        (
            CharacterGrantScheduleKind.PROFICIENCY,
            CharacterGrantSourceKind.MULTICLASS_CLASS_PACKAGE,
        ),
    )
    assert tuple(
        row.proficiency.subject_id
        for row in schedule
        if row.proficiency is not None
    ) == (
        "weapon.martial",
        "saving_throw.constitution",
        "saving_throw.strength",
        "skill.athletics",
        "armor.light",
        "weapon.simple",
        "skill.arcana",
    )
    assert schedule[0].provenance.source_ref == fixture.species_ref
    assert schedule[1].provenance.source_ref == fixture.variant_ref
    assert schedule[2].provenance.source_ref == fixture.background_ref
    assert schedule[6].provenance.class_level_id == "level.one"
    assert schedule[6].provenance.class_level == 1
    assert schedule[11].provenance.choice_id == "sorcerer.cantrip"
    assert first.preview.final_known_spell_refs == (fixture.spell_ref,)


def test_spell_replacement_schedule_derives_the_final_ordered_spell_state() -> None:
    fixture = _fixture()
    old_spell = _behavior_declaration(
        ContentDefinitionKind.SPELL,
        "spell.magic_missile",
        RuntimeBehaviorKind.SPELL,
    )
    new_spell = _behavior_declaration(
        ContentDefinitionKind.SPELL,
        "spell.shield",
        RuntimeBehaviorKind.SPELL,
    )
    declarations = dict(fixture.loaded.registry.declarations)
    declarations[old_spell.ref.identity_key] = old_spell
    declarations[new_spell.ref.identity_key] = new_spell
    sorcerer = declarations[fixture.sorcerer_ref.identity_key]
    payload = sorcerer.definition_payload
    assert isinstance(payload, ClassDefinition)
    entitlements = tuple(
        sorted(
            (
                *payload.spell_entitlements,
                ClassSpellEntitlement(
                    spell_ref=old_spell.ref,
                    spell_rank=1,
                ),
                ClassSpellEntitlement(
                    spell_ref=new_spell.ref,
                    spell_rank=1,
                ),
            ),
            key=lambda row: row.spell_ref.identity_key,
        ),
    )
    declarations[fixture.sorcerer_ref.identity_key] = sorcerer.model_copy(
        update={
            "definition_payload": payload.model_copy(
                update={
                    "spell_entitlements": entitlements,
                    "level_definitions": (
                        ClassLevelDefinition(
                            class_level=1,
                            automatic_grant_refs=(fixture.grant_refs[2],),
                            choice_requirements=(
                                BuildChoiceRequirement(
                                    choice_id="sorcerer.cantrip",
                                    choice_kind=ChoiceRequirementKind.CANTRIP,
                                    allowed_refs=(fixture.spell_ref,),
                                ),
                                BuildChoiceRequirement(
                                    choice_id="sorcerer.spell_known",
                                    choice_kind=ChoiceRequirementKind.SPELL_KNOWN,
                                    allowed_refs=(old_spell.ref,),
                                ),
                            ),
                        ),
                        ClassLevelDefinition(
                            class_level=2,
                            choice_requirements=(
                                BuildChoiceRequirement(
                                    choice_id="sorcerer.spell_replacement",
                                    choice_kind=(
                                        ChoiceRequirementKind.SPELL_REPLACEMENT
                                    ),
                                    allowed_refs=(new_spell.ref,),
                                ),
                            ),
                        ),
                    ),
                },
            ),
        },
    )
    loaded = LoadedContentSystem(
        registry=FrozenContentRegistry(
            declarations=declarations,
            recipe_presets={},
            sources={},
        ),
        packs=(),
        built_in_artifact_digest="b" * 64,
        content_set_digest=_CONTENT_SET_DIGEST,
    )
    levels = (
        _definition(fixture).class_levels[0],
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.two"),
            character_level=2,
            class_ref=fixture.sorcerer_ref,
            resulting_class_level=1,
            choices=(
                CantripChoice(
                    choice_id="sorcerer.cantrip",
                    selected_refs=(fixture.spell_ref,),
                ),
                ClassSkillChoice(
                    choice_id="sorcerer.multiclass.skill",
                    skills=("arcana",),
                ),
                SpellKnownChoice(
                    choice_id="sorcerer.spell_known",
                    selected_refs=(old_spell.ref,),
                ),
            ),
        ),
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.three"),
            character_level=3,
            class_ref=fixture.sorcerer_ref,
            resulting_class_level=2,
            choices=(
                SpellReplacementChoice(
                    choice_id="sorcerer.spell_replacement",
                    replaced_spell_ref=old_spell.ref,
                    learned_spell_ref=new_spell.ref,
                ),
            ),
        ),
    )
    definition = _definition(fixture, class_levels=levels)

    result = CharacterBuildValidator(
        loaded,
        expected_ruleset_digest=_RULESET_DIGEST,
    ).validate(definition, _loadout(definition))

    assert result.issues == ()
    assert result.preview is not None
    spell_rows = tuple(
        row
        for row in result.preview.grant_schedule
        if row.kind
        in {
            CharacterGrantScheduleKind.SPELL_LEARN,
            CharacterGrantScheduleKind.SPELL_REPLACEMENT,
        }
    )
    assert tuple(row.kind for row in spell_rows) == (
        CharacterGrantScheduleKind.SPELL_LEARN,
        CharacterGrantScheduleKind.SPELL_LEARN,
        CharacterGrantScheduleKind.SPELL_REPLACEMENT,
    )
    assert spell_rows[-1].content_ref == new_spell.ref
    assert spell_rows[-1].replaced_content_ref == old_spell.ref
    assert result.preview.final_known_spell_refs == (
        fixture.spell_ref,
        new_spell.ref,
    )


def test_schedule_keeps_subclass_selected_ref_and_asi_sources_distinct() -> None:
    fixture = _fixture()
    style = _behavior_declaration(
        ContentDefinitionKind.CLASS_FEATURE,
        "feature.fighting_style.defense",
        RuntimeBehaviorKind.CLASS_FEATURE,
    )
    declarations = dict(fixture.loaded.registry.declarations)
    declarations[style.ref.identity_key] = style

    fighter = declarations[fixture.fighter_ref.identity_key]
    fighter_payload = fighter.definition_payload
    assert isinstance(fighter_payload, ClassDefinition)
    declarations[fixture.fighter_ref.identity_key] = fighter.model_copy(
        update={
            "definition_payload": fighter_payload.model_copy(
                update={
                    "level_definitions": (
                        fighter_payload.level_definitions[0],
                        ClassLevelDefinition(
                            class_level=2,
                            choice_requirements=(
                                BuildChoiceRequirement(
                                    choice_id="fighter.asi",
                                    choice_kind=(
                                        ChoiceRequirementKind
                                        .ABILITY_SCORE_IMPROVEMENT
                                    ),
                                ),
                                BuildChoiceRequirement(
                                    choice_id="fighter.style",
                                    choice_kind=(
                                        ChoiceRequirementKind.FIGHTING_STYLE
                                    ),
                                    allowed_refs=(style.ref,),
                                ),
                            ),
                        ),
                        fighter_payload.level_definitions[2],
                    ),
                },
            ),
        },
    )
    champion = declarations[fixture.champion_ref.identity_key]
    champion_payload = champion.definition_payload
    assert isinstance(champion_payload, SubclassDefinition)
    declarations[fixture.champion_ref.identity_key] = champion.model_copy(
        update={
            "definition_payload": champion_payload.model_copy(
                update={
                    "level_definitions": (
                        ClassLevelDefinition(
                            class_level=3,
                            automatic_grant_refs=(fixture.grant_refs[0],),
                        ),
                    ),
                },
            ),
        },
    )
    loaded = LoadedContentSystem(
        registry=FrozenContentRegistry(
            declarations=declarations,
            recipe_presets={},
            sources={},
        ),
        packs=(),
        built_in_artifact_digest="b" * 64,
        content_set_digest=_CONTENT_SET_DIGEST,
    )
    base = _definition(fixture).class_levels[0]
    levels = (
        base,
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.two"),
            character_level=2,
            class_ref=fixture.fighter_ref,
            resulting_class_level=2,
            choices=(
                AbilityScoreImprovementChoice(
                    choice_id="fighter.asi",
                    increases=(
                        (AbilityScoreName.DEXTERITY, 1),
                        (AbilityScoreName.STRENGTH, 1),
                    ),
                ),
                FightingStyleChoice(
                    choice_id="fighter.style",
                    selected_ref=style.ref,
                ),
            ),
        ),
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.three"),
            character_level=3,
            class_ref=fixture.fighter_ref,
            resulting_class_level=3,
            subclass_ref=fixture.champion_ref,
            choices=(
                SubclassChoice(
                    choice_id="fighter.subclass",
                    selected_ref=fixture.champion_ref,
                ),
            ),
        ),
    )
    definition = _definition(fixture, class_levels=levels)

    result = CharacterBuildValidator(
        loaded,
        expected_ruleset_digest=_RULESET_DIGEST,
    ).validate(definition, _loadout(definition))

    assert result.issues == ()
    assert result.preview is not None
    asi_rows = tuple(
        row
        for row in result.preview.grant_schedule
        if row.kind == CharacterGrantScheduleKind.ABILITY_SCORE_INCREASE
    )
    assert tuple((row.ability, row.amount) for row in asi_rows) == (
        (AbilityScoreName.DEXTERITY, 1),
        (AbilityScoreName.STRENGTH, 1),
    )
    style_row = next(
        row
        for row in result.preview.grant_schedule
        if row.content_ref == style.ref
    )
    assert style_row.kind == CharacterGrantScheduleKind.SELECTED_CONTENT
    assert style_row.provenance.source_kind == (
        CharacterGrantSourceKind.CLASS_LEVEL
    )
    subclass_automatic = next(
        row
        for row in result.preview.grant_schedule
        if (
            row.content_ref == fixture.grant_refs[0]
            and row.provenance.source_kind
            == CharacterGrantSourceKind.SUBCLASS_LEVEL
        )
    )
    assert subclass_automatic.provenance.source_ref == fixture.champion_ref
    subclass_selection = next(
        row
        for row in result.preview.grant_schedule
        if row.content_ref == fixture.champion_ref
    )
    assert subclass_selection.kind == (
        CharacterGrantScheduleKind.SELECTED_CONTENT
    )
    assert subclass_selection.provenance.source_ref == fixture.fighter_ref


def test_fighting_style_choices_must_be_unique_across_class_levels() -> None:
    fixture = _fixture()
    style = _behavior_declaration(
        ContentDefinitionKind.CLASS_FEATURE,
        "feature.fighting_style.defense",
        RuntimeBehaviorKind.CLASS_FEATURE,
    )
    declarations = dict(fixture.loaded.registry.declarations)
    declarations[style.ref.identity_key] = style
    fighter = declarations[fixture.fighter_ref.identity_key]
    fighter_payload = fighter.definition_payload
    assert isinstance(fighter_payload, ClassDefinition)
    first_level = fighter_payload.level_definitions[0]
    declarations[fixture.fighter_ref.identity_key] = fighter.model_copy(
        update={
            "definition_payload": fighter_payload.model_copy(
                update={
                    "level_definitions": (
                        first_level.model_copy(
                            update={
                                "choice_requirements": (
                                    BuildChoiceRequirement(
                                        choice_id="fighter.style.one",
                                        choice_kind=(
                                            ChoiceRequirementKind.FIGHTING_STYLE
                                        ),
                                        allowed_refs=(style.ref,),
                                    ),
                                ),
                            },
                        ),
                        ClassLevelDefinition(
                            class_level=2,
                            choice_requirements=(
                                BuildChoiceRequirement(
                                    choice_id="fighter.style.two",
                                    choice_kind=(
                                        ChoiceRequirementKind.FIGHTING_STYLE
                                    ),
                                    allowed_refs=(style.ref,),
                                ),
                            ),
                        ),
                        fighter_payload.level_definitions[2],
                    ),
                },
            ),
        },
    )
    loaded = LoadedContentSystem(
        registry=FrozenContentRegistry(
            declarations=declarations,
            recipe_presets={},
            sources={},
        ),
        packs=(),
        built_in_artifact_digest="b" * 64,
        content_set_digest=_CONTENT_SET_DIGEST,
    )
    levels = (
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.one"),
            character_level=1,
            class_ref=fixture.fighter_ref,
            resulting_class_level=1,
            choices=(
                ClassSkillChoice(
                    choice_id="fighter.first.skills",
                    skills=("athletics",),
                ),
                StartingProficiencyChoice(
                    choice_id="fighter.first.starting_proficiency",
                    proficiencies=(
                        ProficiencySubject(
                            subject_kind=ProficiencySubjectKind.ARMOR,
                            subject_id="armor.light",
                        ),
                    ),
                ),
                FightingStyleChoice(
                    choice_id="fighter.style.one",
                    selected_ref=style.ref,
                ),
            ),
        ),
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.two"),
            character_level=2,
            class_ref=fixture.fighter_ref,
            resulting_class_level=2,
            choices=(
                FightingStyleChoice(
                    choice_id="fighter.style.two",
                    selected_ref=style.ref,
                ),
            ),
        ),
    )
    definition = _definition(fixture, class_levels=levels)

    result = CharacterBuildValidator(
        loaded,
        expected_ruleset_digest=_RULESET_DIGEST,
    ).validate(definition, _loadout(definition))

    assert result.preview is None
    duplicate = next(
        issue
        for issue in result.issues
        if issue.code
        == CharacterBuildIssueCode.DUPLICATE_FIGHTING_STYLE
    )
    assert duplicate.content_refs == (style.ref,)
    assert duplicate.path == (
        "class_levels",
        "1",
        "choices",
        "fighter.style.two",
    )


def test_one_advancement_slot_accepts_exactly_one_asi_or_feat_choice() -> None:
    fixture = _fixture()
    feat = _behavior_declaration(
        ContentDefinitionKind.FEAT,
        "feat.fixture",
        RuntimeBehaviorKind.FEAT,
    )
    declarations = dict(fixture.loaded.registry.declarations)
    declarations[feat.ref.identity_key] = feat
    fighter = declarations[fixture.fighter_ref.identity_key]
    fighter_payload = fighter.definition_payload
    assert isinstance(fighter_payload, ClassDefinition)
    first_level = fighter_payload.level_definitions[0]
    declarations[fixture.fighter_ref.identity_key] = fighter.model_copy(
        update={
            "definition_payload": fighter_payload.model_copy(
                update={
                    "level_definitions": (
                        first_level,
                        ClassLevelDefinition(
                            class_level=2,
                            choice_requirements=(
                                BuildChoiceRequirement(
                                    choice_id="fighter.advancement.two",
                                    choice_kind=(
                                        ChoiceRequirementKind
                                        .ABILITY_SCORE_IMPROVEMENT_OR_FEAT
                                    ),
                                    allowed_refs=(feat.ref,),
                                ),
                            ),
                        ),
                        fighter_payload.level_definitions[2],
                    ),
                },
            ),
        },
    )
    loaded = LoadedContentSystem(
        registry=FrozenContentRegistry(
            declarations=declarations,
            recipe_presets={},
            sources={},
        ),
        packs=(),
        built_in_artifact_digest="b" * 64,
        content_set_digest=_CONTENT_SET_DIGEST,
    )
    first = _definition(fixture).class_levels[0]
    asi_levels = (
        first,
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.two"),
            character_level=2,
            class_ref=fixture.fighter_ref,
            resulting_class_level=2,
            choices=(
                AbilityScoreImprovementChoice(
                    choice_id="fighter.advancement.two",
                    increases=((AbilityScoreName.STRENGTH, 2),),
                ),
            ),
        ),
    )
    feat_levels = (
        first,
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.two"),
            character_level=2,
            class_ref=fixture.fighter_ref,
            resulting_class_level=2,
            choices=(
                FeatChoice(
                    choice_id="fighter.advancement.two",
                    selected_ref=feat.ref,
                ),
            ),
        ),
    )

    for levels in (asi_levels, feat_levels):
        definition = _definition(fixture, class_levels=levels)
        result = CharacterBuildValidator(
            loaded,
            expected_ruleset_digest=_RULESET_DIGEST,
        ).validate(definition, _loadout(definition))
        assert result.issues == ()
        assert result.preview is not None


def test_digest_and_loadout_heads_fail_closed_with_typed_issues() -> None:
    fixture = _fixture()
    definition = _definition(
        fixture,
        content_set_digest="e" * 64,
        ruleset_digest="f" * 64,
    )
    loadout = _loadout(
        definition,
        based_on_definition_revision=definition.definition_revision + 1,
    )

    result = _validator(fixture).validate(definition, loadout)

    assert result.preview is None
    assert _codes(result) >= {
        CharacterBuildIssueCode.CONTENT_SET_MISMATCH,
        CharacterBuildIssueCode.RULESET_MISMATCH,
        CharacterBuildIssueCode.LOADOUT_DEFINITION_MISMATCH,
    }


def test_body_factory_parameters_are_validated_without_execution() -> None:
    fixture = _fixture()
    original = _definition(fixture)
    definition = _replace_definition(
        original,
        body_recipe=ContentRecipe.create(
            ref=fixture.body_ref,
            parameters={},
        ),
    )

    result = _validator(fixture).validate(
        definition,
        _loadout(definition),
    )

    assert result.preview is None
    assert CharacterBuildIssueCode.BODY_PARAMETERS_INVALID in _codes(result)


def test_variant_parent_and_subclass_parent_are_exact() -> None:
    fixture = _fixture()
    unrelated_species = _typed_declaration(
        ContentDefinitionKind.SPECIES,
        "species.elf",
        SpeciesDefinition(
            runtime_support=OriginRuntimeSupport.available(),
        ),
    )
    wrong_variant = _typed_declaration(
        ContentDefinitionKind.SPECIES_VARIANT,
        "species_variant.wrong",
        SpeciesVariantDefinition(
            parent_species_ref=unrelated_species.ref,
            runtime_support=OriginRuntimeSupport.available(),
        ),
    )
    declarations = dict(fixture.loaded.registry.declarations)
    declarations[unrelated_species.ref.identity_key] = unrelated_species
    declarations[wrong_variant.ref.identity_key] = wrong_variant
    loaded = LoadedContentSystem(
        registry=FrozenContentRegistry(
            declarations=declarations,
            recipe_presets={},
            sources={},
        ),
        packs=(),
        built_in_artifact_digest="b" * 64,
        content_set_digest=_CONTENT_SET_DIGEST,
    )
    original = _definition(fixture)
    definition = _replace_definition(
        original,
        species_variant_ref=wrong_variant.ref,
    )

    result = CharacterBuildValidator(
        loaded,
        expected_ruleset_digest=_RULESET_DIGEST,
    ).validate(definition, _loadout(definition))

    assert result.preview is None
    assert CharacterBuildIssueCode.SPECIES_VARIANT_PARENT_MISMATCH in _codes(
        result,
    )


def test_required_unexpected_and_disallowed_choices_are_reported() -> None:
    fixture = _fixture()
    disallowed_spell = _behavior_declaration(
        ContentDefinitionKind.SPELL,
        "spell.disallowed",
        RuntimeBehaviorKind.SPELL,
    )
    declarations = dict(fixture.loaded.registry.declarations)
    declarations[disallowed_spell.ref.identity_key] = disallowed_spell
    loaded = LoadedContentSystem(
        registry=FrozenContentRegistry(
            declarations=declarations,
            recipe_presets={},
            sources={},
        ),
        packs=(),
        built_in_artifact_digest="b" * 64,
        content_set_digest=_CONTENT_SET_DIGEST,
    )
    levels = (
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.one"),
            character_level=1,
            class_ref=fixture.fighter_ref,
            resulting_class_level=1,
            choices=(),
        ),
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.two"),
            character_level=2,
            class_ref=fixture.sorcerer_ref,
            resulting_class_level=1,
            choices=(
                CantripChoice(
                    choice_id="sorcerer.cantrip",
                    selected_refs=(disallowed_spell.ref,),
                ),
                ClassSkillChoice(
                    choice_id="unexpected.choice",
                    skills=("arcana",),
                ),
            ),
        ),
    )
    definition = _definition(fixture, class_levels=levels)

    result = CharacterBuildValidator(
        loaded,
        expected_ruleset_digest=_RULESET_DIGEST,
    ).validate(definition, _loadout(definition))

    assert result.preview is None
    assert _codes(result) >= {
        CharacterBuildIssueCode.MISSING_REQUIRED_CHOICE,
        CharacterBuildIssueCode.UNEXPECTED_CHOICE,
        CharacterBuildIssueCode.CHOICE_REF_NOT_ALLOWED,
    }


def test_subclass_must_be_selected_at_its_authored_class_level() -> None:
    fixture = _fixture()
    levels = (
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.one"),
            character_level=1,
            class_ref=fixture.fighter_ref,
            resulting_class_level=1,
            choices=(
                ClassSkillChoice(
                    choice_id="fighter.first.skills",
                    skills=("athletics",),
                ),
                StartingProficiencyChoice(
                    choice_id="fighter.first.starting_proficiency",
                    proficiencies=(
                        ProficiencySubject(
                            subject_kind=ProficiencySubjectKind.ARMOR,
                            subject_id="armor.light",
                        ),
                    ),
                ),
            ),
        ),
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.two"),
            character_level=2,
            class_ref=fixture.fighter_ref,
            resulting_class_level=2,
            subclass_ref=fixture.champion_ref,
            choices=(),
        ),
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.three"),
            character_level=3,
            class_ref=fixture.fighter_ref,
            resulting_class_level=3,
            subclass_ref=fixture.champion_ref,
            choices=(
                SubclassChoice(
                    choice_id="fighter.subclass",
                    selected_ref=fixture.champion_ref,
                ),
            ),
        ),
    )
    definition = _definition(fixture, class_levels=levels)

    result = _validator(fixture).validate(
        definition,
        _loadout(definition),
    )

    assert result.preview is None
    assert CharacterBuildIssueCode.SUBCLASS_SELECTION_TIMING in _codes(result)


def test_prepared_spells_require_exact_active_source_and_entitlement() -> None:
    fixture = _fixture()
    definition = _definition(fixture)
    valid_loadout = _loadout(
        definition,
        prepared_spells=(
            PreparedSpellSourceLoadout(
                spellcasting_source_id=SpellcastingSourceId(
                    value="class.sorcerer",
                ),
                spell_refs=(fixture.spell_ref,),
            ),
        ),
    )

    valid = _validator(fixture).validate(definition, valid_loadout)
    assert valid.issues == ()

    unknown_source = _loadout(
        definition,
        prepared_spells=(
            PreparedSpellSourceLoadout(
                spellcasting_source_id=SpellcastingSourceId(
                    value="class.wizard",
                ),
                spell_refs=(fixture.spell_ref,),
            ),
        ),
    )
    result = _validator(fixture).validate(definition, unknown_source)
    assert (
        CharacterBuildIssueCode.PREPARED_SPELL_SOURCE_UNKNOWN
        in _codes(result)
    )


def test_prepared_spell_rank_is_bounded_by_its_own_class_source() -> None:
    fixture = _fixture()
    declarations = dict(fixture.loaded.registry.declarations)
    declaration = declarations[fixture.sorcerer_ref.identity_key]
    payload = declaration.definition_payload
    assert isinstance(payload, ClassDefinition)
    declarations[fixture.sorcerer_ref.identity_key] = declaration.model_copy(
        update={
            "definition_payload": payload.model_copy(
                update={
                    "spell_entitlements": (
                        ClassSpellEntitlement(
                            spell_ref=fixture.spell_ref,
                            spell_rank=2,
                        ),
                    ),
                },
            ),
        },
    )
    loaded = LoadedContentSystem(
        registry=FrozenContentRegistry(
            declarations=declarations,
            recipe_presets={},
            sources={},
        ),
        packs=(),
        built_in_artifact_digest="b" * 64,
        content_set_digest=_CONTENT_SET_DIGEST,
    )
    definition = _definition(fixture)
    loadout = _loadout(
        definition,
        prepared_spells=(
            PreparedSpellSourceLoadout(
                spellcasting_source_id=SpellcastingSourceId(
                    value="class.sorcerer",
                ),
                spell_refs=(fixture.spell_ref,),
            ),
        ),
    )

    result = CharacterBuildValidator(
        loaded,
        expected_ruleset_digest=_RULESET_DIGEST,
    ).validate(definition, loadout)

    assert result.preview is None
    assert CharacterBuildIssueCode.PREPARED_SPELL_RANK_UNAVAILABLE in _codes(
        result,
    )


def test_multiclass_prerequisites_are_profile_controlled_and_exact() -> None:
    fixture = _fixture()
    definition = _definition(fixture)
    loadout = _loadout(definition)

    permissive = _validator(fixture).validate(definition, loadout)
    strict = CharacterBuildValidator(
        fixture.loaded,
        expected_ruleset_digest=_RULESET_DIGEST,
        permissive_multiclass_prerequisites=False,
    ).validate(definition, loadout)

    assert permissive.issues == ()
    assert strict.preview is None
    assert CharacterBuildIssueCode.MULTICLASS_PREREQUISITE_UNMET in _codes(
        strict,
    )


def test_closed_prerequisite_tree_uses_prior_ledger_facts() -> None:
    fixture = _fixture()
    loaded = _with_sorcerer_prerequisite(
        fixture,
        AllOfPrerequisite(
            prerequisites=(
                ClassLevelPrerequisite(
                    class_ref=fixture.fighter_ref,
                    minimum=1,
                ),
                TotalCharacterLevelPrerequisite(minimum=1),
                AbilityScorePrerequisite(
                    ability=AbilityScoreName.STRENGTH,
                    minimum=13,
                ),
                HasFeaturePrerequisite(
                    feature_ref=fixture.grant_refs[1],
                ),
                AnyOfPrerequisite(
                    prerequisites=(
                        AbilityScorePrerequisite(
                            ability=AbilityScoreName.CHARISMA,
                            minimum=30,
                        ),
                        TotalCharacterLevelPrerequisite(minimum=1),
                    ),
                ),
                NotPrerequisite(
                    prerequisite=KnowsSpellPrerequisite(
                        spell_ref=fixture.spell_ref,
                    ),
                ),
            ),
        ),
    )
    definition = _definition(fixture)

    result = CharacterBuildValidator(
        loaded,
        expected_ruleset_digest=_RULESET_DIGEST,
        permissive_multiclass_prerequisites=False,
    ).validate(definition, _loadout(definition))

    assert result.issues == ()
    assert result.preview is not None


def test_skill_and_starting_proficiency_allowlists_are_exact() -> None:
    fixture = _fixture()
    levels = (
        ClassLevelEntry(
            class_level_id=ClassLevelId(value="level.one"),
            character_level=1,
            class_ref=fixture.fighter_ref,
            resulting_class_level=1,
            choices=(
                ClassSkillChoice(
                    choice_id="fighter.first.skills",
                    skills=("stealth",),
                ),
                StartingProficiencyChoice(
                    choice_id="fighter.first.starting_proficiency",
                    proficiencies=(
                        ProficiencySubject(
                            subject_kind=ProficiencySubjectKind.ARMOR,
                            subject_id="armor.heavy",
                        ),
                    ),
                ),
            ),
        ),
    )
    definition = _definition(fixture, class_levels=levels)

    result = _validator(fixture).validate(
        definition,
        _loadout(definition),
    )

    assert result.preview is None
    failures = tuple(
        issue
        for issue in result.issues
        if (
            issue.code
            == CharacterBuildIssueCode.CHOICE_PROFICIENCY_SUBJECT_NOT_ALLOWED
        )
    )
    assert tuple(issue.detail for issue in failures) == (
        "skill.stealth",
        "armor:armor.heavy",
    )
