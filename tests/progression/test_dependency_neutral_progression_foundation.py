"""Focused contracts for additive character builds and shared progression."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.core.content.descriptors import ContentDescriptorSpec, ContentVisibility
from dnd.core.content.durable_characters import (
    AbilityScoreAllocation,
    AbilityScoreName,
    AbilityScorePrerequisite,
    CharacterAppearanceSelection,
    CharacterDefinitionRevisionV2,
    CharacterLoadoutRevisionV1,
    ClassDefinition,
    ClassLevelDefinition,
    ClassLevelEntry,
    ClassLevelId,
    ClassProficiencyPackage,
    ClassSpellEntitlement,
    ClassSkillChoice,
    CantripChoice,
    BuildChoiceRequirement,
    BackgroundDefinition,
    ChoiceRequirementKind,
    FlexibleAbilityBonusSelection,
    ProficiencySubject,
    ProficiencySubjectKind,
    PreparedSpellSourceLoadout,
    RitualPreparationPolicy,
    SpellcastingSourceId,
    StartingProficiencyChoice,
    SpeciesDefinition,
    SpeciesVariantDefinition,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.origin_support import (
    OriginRuntimeSupport,
    OriginRuntimeSupportStatus,
)
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
    ContentSource,
    ContentSourceFamily,
    RulesBaseline,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import (
    ContentDeclarationMode,
    get_content_declaration,
    typed_definition,
)
from dnd.core.content.registry import (
    ContentRegistryBuilder,
    NonTypedDefinitionError,
)
from dnd.core.proficiency_types import ProficiencyMode
from dnd.core.progression import (
    CasterProgression,
    MulticlassSlotRoundingPolicy,
    SpellcastingClassContribution,
    character_ruleset_digest,
    effective_spellcaster_level,
    point_buy_cost,
    resolve_proficiency_bonus,
)


_SOURCE = ContentSource(
    source_id="fixture.progression",
    source_family=ContentSourceFamily.FIXTURE_INTERNAL,
    title="Progression fixture",
    source_version="1",
    rules_baseline=RulesBaseline.ENGINE_NEUTRAL,
    license_id="fixture",
    canonical_uri="fixture://progression",
    document_digest="a" * 64,
    attribution_text="Internal test fixture.",
)
_PROVENANCE = ContentProvenance(
    primary_source_id=_SOURCE.source_id,
    source_anchor="fixture",
    relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
    fidelity=ContentFidelity.COMPLETE,
    review_status=ContentReviewStatus.REVIEWED,
)


def _ref(kind: ContentDefinitionKind, content_id: str) -> ContentRef:
    return ContentRef(
        pack_id="fixture.progression",
        definition_kind=kind,
        content_id=content_id,
        content_version=1,
        definition_contract_hash="b" * 64,
    )


@typed_definition(
    definition_kind=ContentDefinitionKind.CLASS,
    pack_id="fixture.progression",
    content_id="class.fighter",
    version=1,
    descriptor=ContentDescriptorSpec(
        display_name="Fighter",
        visibility=ContentVisibility.PUBLIC,
    ),
    provenance=_PROVENANCE,
    definition=ClassDefinition(
        hit_die=10,
        caster_progression=CasterProgression.NON_CASTER,
    ),
)
class _FighterDefinition:
    pass


def test_progression_definition_kinds_are_exact_content_identities() -> None:
    assert ContentDefinitionKind.CLASS.value == "class"
    assert ContentDefinitionKind.SUBCLASS.value == "subclass"
    assert ContentDefinitionKind.SPECIES.value == "species"
    assert ContentDefinitionKind.SPECIES_VARIANT.value == "species_variant"
    assert ContentDefinitionKind.BACKGROUND.value == "background"


def test_origin_runtime_support_is_closed_and_requires_an_exact_block_reason() -> None:
    available = OriginRuntimeSupport.available()
    blocked = OriginRuntimeSupport.blocked(
        "The authored runtime grants are not installed.",
    )

    assert available.status is OriginRuntimeSupportStatus.AVAILABLE
    assert available.blocked_reason is None
    assert blocked.status is OriginRuntimeSupportStatus.BLOCKED
    assert blocked.blocked_reason == (
        "The authored runtime grants are not installed."
    )

    with pytest.raises(ValidationError, match="blocked.*reason"):
        OriginRuntimeSupport(status=OriginRuntimeSupportStatus.BLOCKED)
    with pytest.raises(ValidationError, match="available.*blocked reason"):
        OriginRuntimeSupport(
            status=OriginRuntimeSupportStatus.AVAILABLE,
            blocked_reason="Contradictory unavailable state.",
        )
    with pytest.raises(ValidationError, match="exact reason"):
        OriginRuntimeSupport.blocked("   ")


def test_every_origin_definition_requires_explicit_runtime_support() -> None:
    with pytest.raises(ValidationError, match="runtime_support"):
        SpeciesDefinition.model_validate({})
    with pytest.raises(ValidationError, match="runtime_support"):
        BackgroundDefinition.model_validate({})
    with pytest.raises(ValidationError, match="runtime_support"):
        SpeciesVariantDefinition.model_validate({
            "parent_species_ref": _ref(
                ContentDefinitionKind.SPECIES,
                "species.fixture",
            ).model_dump(mode="json"),
        })


def test_point_buy_and_flexible_bonuses_follow_selected_bg3_policy() -> None:
    assert point_buy_cost(8) == 0
    assert point_buy_cost(15) == 9
    with pytest.raises(ValueError, match="between 8 and 15"):
        point_buy_cost(16)

    allocation = AbilityScoreAllocation(
        strength=15,
        dexterity=15,
        constitution=15,
        intelligence=8,
        wisdom=8,
        charisma=8,
    )
    assert allocation.points_spent == 27
    with pytest.raises(ValidationError, match="exactly 27"):
        AbilityScoreAllocation(
            strength=14,
            dexterity=15,
            constitution=15,
            intelligence=8,
            wisdom=8,
            charisma=8,
        )
    with pytest.raises(ValidationError, match="different abilities"):
        FlexibleAbilityBonusSelection(
            plus_two=AbilityScoreName.STRENGTH,
            plus_one=AbilityScoreName.STRENGTH,
        )


@pytest.mark.parametrize(
    ("modes", "expected"),
    [
        ((), 0),
        ((ProficiencyMode.HALF_ROUND_DOWN,), 1),
        (
            (
                ProficiencyMode.HALF_ROUND_DOWN,
                ProficiencyMode.HALF_ROUND_UP,
            ),
            2,
        ),
        (
            (
                ProficiencyMode.FULL,
                ProficiencyMode.HALF_ROUND_UP,
            ),
            3,
        ),
        ((ProficiencyMode.EXPERTISE,), 0),
        (
            (
                ProficiencyMode.FULL,
                ProficiencyMode.EXPERTISE,
                ProficiencyMode.EXPERTISE,
            ),
            6,
        ),
    ],
)
def test_proficiency_sources_compete_instead_of_stacking(
    modes: tuple[ProficiencyMode, ...],
    expected: int,
) -> None:
    assert resolve_proficiency_bonus(3, modes) == expected


def test_effective_spellcaster_level_uses_single_source_table_then_aggregate() -> None:
    paladin_3 = SpellcastingClassContribution(
        class_level=3,
        progression=CasterProgression.HALF_CASTER,
        spellcasting_feature_class_level=2,
    )
    fighter_2 = SpellcastingClassContribution(
        class_level=2,
        progression=CasterProgression.NON_CASTER,
    )
    sorcerer_3 = SpellcastingClassContribution(
        class_level=3,
        progression=CasterProgression.FULL_CASTER,
        spellcasting_feature_class_level=1,
    )
    ranger_3 = SpellcastingClassContribution(
        class_level=3,
        progression=CasterProgression.HALF_CASTER,
        spellcasting_feature_class_level=2,
    )
    assert effective_spellcaster_level((paladin_3, fighter_2)) == 2
    assert effective_spellcaster_level((paladin_3, ranger_3)) == 3
    assert effective_spellcaster_level((sorcerer_3, paladin_3)) == 5
    assert effective_spellcaster_level(
        (sorcerer_3, paladin_3),
        policy=MulticlassSlotRoundingPolicy.SRD_5_1_ROUND_DOWN,
    ) == 4


@pytest.mark.parametrize(
    ("rows", "policy", "expected"),
    [
        (
            (
                SpellcastingClassContribution(
                    class_level=1,
                    progression=CasterProgression.HALF_CASTER,
                    spellcasting_feature_class_level=2,
                ),
            ),
            MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP,
            0,
        ),
        (
            (
                SpellcastingClassContribution(
                    class_level=2,
                    progression=CasterProgression.HALF_CASTER,
                    spellcasting_feature_class_level=2,
                ),
            ),
            MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP,
            1,
        ),
        (
            (
                SpellcastingClassContribution(
                    class_level=3,
                    progression=CasterProgression.HALF_CASTER,
                    spellcasting_feature_class_level=2,
                ),
                SpellcastingClassContribution(
                    class_level=2,
                    progression=CasterProgression.NON_CASTER,
                ),
            ),
            MulticlassSlotRoundingPolicy.SRD_5_1_ROUND_DOWN,
            2,
        ),
        (
            (
                SpellcastingClassContribution(
                    class_level=1,
                    progression=CasterProgression.HALF_CASTER,
                    spellcasting_feature_class_level=2,
                ),
                SpellcastingClassContribution(
                    class_level=1,
                    progression=CasterProgression.HALF_CASTER,
                    spellcasting_feature_class_level=2,
                ),
                SpellcastingClassContribution(
                    class_level=1,
                    progression=CasterProgression.FULL_CASTER,
                    spellcasting_feature_class_level=1,
                ),
            ),
            MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP,
            1,
        ),
    ],
)
def test_effective_spellcaster_level_feature_gate_boundaries(
    rows: tuple[SpellcastingClassContribution, ...],
    policy: MulticlassSlotRoundingPolicy,
    expected: int,
) -> None:
    assert effective_spellcaster_level(rows, policy=policy) == expected


def test_character_v2_is_an_ordered_self_authenticating_level_ledger() -> None:
    body_ref = _ref(ContentDefinitionKind.CREATURE, "creature.hero_body")
    class_ref = _ref(ContentDefinitionKind.CLASS, "class.fighter")
    definition = CharacterDefinitionRevisionV2.create(
        character_id=uuid4(),
        definition_revision=1,
        body_recipe=ContentRecipe.create(ref=body_ref, parameters={}),
        species_ref=_ref(ContentDefinitionKind.SPECIES, "species.human"),
        background_ref=_ref(
            ContentDefinitionKind.BACKGROUND,
            "background.soldier",
        ),
        appearance=CharacterAppearanceSelection(),
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
        class_levels=(
            ClassLevelEntry(
                class_level_id=ClassLevelId(value="level.one"),
                character_level=1,
                class_ref=class_ref,
                resulting_class_level=1,
                choices=(
                    ClassSkillChoice(
                        choice_id="fighter.skills",
                        skills=("athletics", "perception"),
                    ),
                ),
            ),
        ),
        earned_character_level=1,
        content_set_digest="c" * 64,
        ruleset_digest="d" * 64,
    )
    definition.verify_integrity()
    tampered = definition.model_dump(mode="json")
    tampered["earned_character_level"] = 2
    with pytest.raises(ValidationError):
        CharacterDefinitionRevisionV2.model_validate(tampered)


def test_loadout_has_one_exact_empty_seed_and_source_owned_spell_rows() -> None:
    character_id = uuid4()
    empty = CharacterLoadoutRevisionV1.create(
        character_id=character_id,
        loadout_revision=1,
        based_on_definition_revision=1,
    )
    assert empty.prepared_spells == ()
    assert empty.feature_toggles == ()
    empty.verify_integrity()

    source_id = SpellcastingSourceId(value="source.cleric")
    spell_ref = _ref(ContentDefinitionKind.SPELL, "spell.bless")
    populated = CharacterLoadoutRevisionV1.create(
        character_id=character_id,
        loadout_revision=2,
        based_on_definition_revision=1,
        prepared_spells=(
            PreparedSpellSourceLoadout(
                spellcasting_source_id=source_id,
                spell_refs=(spell_ref,),
            ),
        ),
    )
    assert populated.prepared_spells[0].spell_refs == (spell_ref,)


def test_typed_definitions_use_the_existing_frozen_registry() -> None:
    declaration = get_content_declaration(_FighterDefinition)
    assert declaration.mode == ContentDeclarationMode.TYPED_DEFINITION
    builder = ContentRegistryBuilder()
    builder.add_source(_SOURCE)
    builder.add_declaration(declaration)
    registry = builder.freeze(
        pack_dependencies={"fixture.progression": frozenset()},
    )
    resolved = registry.resolve_typed_definition(
        declaration.ref,
        ClassDefinition,
    )
    assert resolved.hit_die == 10
    with pytest.raises(NonTypedDefinitionError):
        registry.resolve_factory(declaration.ref)


def test_class_definitions_separate_entry_proficiencies_and_reject_bad_order() -> None:
    first = ClassProficiencyPackage(
        automatic=(
            ProficiencySubject(
                subject_kind=ProficiencySubjectKind.ARMOR,
                subject_id="armor.light",
            ),
        ),
    )
    multiclass = ClassProficiencyPackage(
        automatic=(
            ProficiencySubject(
                subject_kind=ProficiencySubjectKind.ARMOR,
                subject_id="armor.light",
            ),
        ),
    )
    definition = ClassDefinition(
        hit_die=10,
        caster_progression=CasterProgression.NON_CASTER,
        first_class_proficiencies=first,
        multiclass_proficiencies=multiclass,
        saving_throw_proficiencies=(
            AbilityScoreName.CONSTITUTION,
            AbilityScoreName.STRENGTH,
        ),
    )
    assert definition.first_class_proficiencies == first
    assert definition.multiclass_proficiencies == multiclass

    with pytest.raises(ValidationError, match="automatic grants"):
        ClassLevelDefinition(
            class_level=1,
            automatic_grant_refs=(
                _ref(ContentDefinitionKind.CLASS_FEATURE, "feature.second"),
                _ref(ContentDefinitionKind.CLASS_FEATURE, "feature.first"),
            ),
        )


def test_caster_definition_owns_exact_source_list_and_multiclass_gate() -> None:
    spell_ref = _ref(ContentDefinitionKind.SPELL, "spell.cure_wounds")
    definition = ClassDefinition(
        hit_die=8,
        caster_progression=CasterProgression.FULL_CASTER,
        spellcasting_feature_class_level=1,
        spellcasting_source_id=SpellcastingSourceId(value="class.cleric"),
        spellcasting_ability=AbilityScoreName.WISDOM,
        ritual_policy=RitualPreparationPolicy.PREPARED,
        spell_entitlements=(
            ClassSpellEntitlement(spell_ref=spell_ref, spell_rank=1),
        ),
        multiclass_prerequisite=AbilityScorePrerequisite(
            ability=AbilityScoreName.WISDOM,
            minimum=13,
        ),
    )

    assert definition.spellcasting_source_id == SpellcastingSourceId(
        value="class.cleric",
    )
    assert definition.spell_entitlements[0].spell_ref == spell_ref
    assert definition.multiclass_prerequisite is not None


def test_class_spell_contract_fails_closed_for_incomplete_or_incoherent_rows() -> None:
    with pytest.raises(ValidationError, match="exact spellcasting source"):
        ClassDefinition(
            hit_die=6,
            caster_progression=CasterProgression.FULL_CASTER,
            spellcasting_feature_class_level=1,
        )

    with pytest.raises(ValidationError, match="non-caster"):
        ClassDefinition(
            hit_die=10,
            caster_progression=CasterProgression.NON_CASTER,
            spellcasting_source_id=SpellcastingSourceId(
                value="class.impossible",
            ),
            spellcasting_ability=AbilityScoreName.INTELLIGENCE,
        )

    with pytest.raises(ValidationError, match="spell definition"):
        ClassSpellEntitlement(
            spell_ref=_ref(
                ContentDefinitionKind.CLASS_FEATURE,
                "feature.not_a_spell",
            ),
            spell_rank=1,
        )

    with pytest.raises(ValidationError, match="unique and ordered"):
        ClassDefinition(
            hit_die=8,
            caster_progression=CasterProgression.FULL_CASTER,
            spellcasting_feature_class_level=1,
            spellcasting_source_id=SpellcastingSourceId(value="class.cleric"),
            spellcasting_ability=AbilityScoreName.WISDOM,
            spell_entitlements=(
                ClassSpellEntitlement(
                    spell_ref=_ref(
                        ContentDefinitionKind.SPELL,
                        "spell.zeta",
                    ),
                    spell_rank=1,
                ),
                ClassSpellEntitlement(
                    spell_ref=_ref(
                        ContentDefinitionKind.SPELL,
                        "spell.alpha",
                    ),
                    spell_rank=1,
                ),
            ),
        )


def test_proficiency_choice_requirements_use_exact_subjects_not_content_refs() -> None:
    requirement = BuildChoiceRequirement(
        choice_id="fighter.first.skills",
        choice_kind=ChoiceRequirementKind.CLASS_SKILL,
        minimum_selections=2,
        maximum_selections=2,
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
    )
    assert tuple(
        row.subject_id for row in requirement.allowed_proficiency_subjects
    ) == ("skill.athletics", "skill.perception")

    with pytest.raises(ValidationError, match="allowed_refs"):
        BuildChoiceRequirement(
            choice_id="fighter.first.skills",
            choice_kind=ChoiceRequirementKind.CLASS_SKILL,
            allowed_refs=(
                _ref(
                    ContentDefinitionKind.CLASS_FEATURE,
                    "feature.not_a_skill",
                ),
            ),
        )

    selected = StartingProficiencyChoice(
        choice_id="origin.starting.proficiencies",
        proficiencies=(
            ProficiencySubject(
                subject_kind=ProficiencySubjectKind.ARMOR,
                subject_id="armor.light",
            ),
            ProficiencySubject(
                subject_kind=ProficiencySubjectKind.WEAPON,
                subject_id="weapon.simple",
            ),
        ),
    )
    assert tuple(
        (row.subject_kind, row.subject_id) for row in selected.proficiencies
    ) == (
        (ProficiencySubjectKind.ARMOR, "armor.light"),
        (ProficiencySubjectKind.WEAPON, "weapon.simple"),
    )

    with pytest.raises(ValidationError, match="skill subjects"):
        BuildChoiceRequirement(
            choice_id="fighter.first.skills",
            choice_kind=ChoiceRequirementKind.CLASS_SKILL,
            allowed_proficiency_subjects=(
                ProficiencySubject(
                    subject_kind=ProficiencySubjectKind.WEAPON,
                    subject_id="weapon.simple",
                ),
            ),
        )


def test_exact_weapon_proficiency_uses_authenticated_item_identity() -> None:
    weapon_ref = _ref(
        ContentDefinitionKind.ITEM,
        "item.weapon.light_crossbow",
    )
    subject = ProficiencySubject(
        subject_kind=ProficiencySubjectKind.WEAPON,
        content_ref=weapon_ref,
    )

    assert subject.subject_id is None
    assert subject.content_ref == weapon_ref
    assert subject.identity_key == weapon_ref.identity_key

    with pytest.raises(ValidationError, match="only for weapons"):
        ProficiencySubject(
            subject_kind=ProficiencySubjectKind.ARMOR,
            content_ref=weapon_ref,
        )

    with pytest.raises(ValidationError, match="must reference an item"):
        ProficiencySubject(
            subject_kind=ProficiencySubjectKind.WEAPON,
            content_ref=_ref(
                ContentDefinitionKind.SPELL,
                "spell.false_weapon",
            ),
        )


def test_delivered_spell_choices_reject_non_spell_content_refs() -> None:
    with pytest.raises(ValidationError, match="only spells"):
        CantripChoice(
            choice_id="sorcerer.cantrips",
            selected_refs=(
                _ref(
                    ContentDefinitionKind.CLASS_FEATURE,
                    "feature.not_a_spell",
                ),
            ),
        )


def test_character_ruleset_digest_authenticates_only_build_rules_policy() -> None:
    default_digest = character_ruleset_digest(
        permissive_multiclass_prerequisites=True,
        multiclass_slot_rounding_policy=(
            MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
        ),
    )

    assert len(default_digest) == 64
    assert default_digest == character_ruleset_digest(
        permissive_multiclass_prerequisites=True,
        multiclass_slot_rounding_policy=(
            MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
        ),
    )
    assert default_digest != character_ruleset_digest(
        permissive_multiclass_prerequisites=False,
        multiclass_slot_rounding_policy=(
            MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
        ),
    )
    assert default_digest != character_ruleset_digest(
        permissive_multiclass_prerequisites=True,
        multiclass_slot_rounding_policy=(
            MulticlassSlotRoundingPolicy.SRD_5_1_ROUND_DOWN
        ),
    )
