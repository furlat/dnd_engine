"""Focused authored-definition coverage for Barbarian and Berserker."""

from dnd.classes.barbarian_progression_definitions import (
    BARBARIAN_CLASS_DECLARATION,
    BARBARIAN_CLASS_DEFINITION,
    BARBARIAN_PROGRESSION_DECLARATIONS,
    BERSERKER_SUBCLASS_DECLARATION,
    BERSERKER_SUBCLASS_DEFINITION,
    UNARMORED_DEFENSE_DECLARATION,
)
from dnd.classes.permanent_feature_definitions import (
    BARBARIAN_BRUTAL_CRITICAL_DECLARATION,
    BARBARIAN_FRENZY_DECLARATION,
    BARBARIAN_RAGE_DECLARATION,
    FIGHTER_EXTRA_ATTACK_DECLARATION,
    LUCKY_FEAT_DECLARATION,
)
from dnd.core.content.dependencies import ContentDependencyRelation
from dnd.core.content.durable_characters import (
    AbilityScoreName,
    AbilityScorePrerequisite,
    ChoiceRequirementKind,
    ClassDefinition,
    ProficiencySubjectKind,
    SubclassDefinition,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.registration import ContentDeclarationMode
from dnd.core.progression import CasterProgression


def _level(
    definition: ClassDefinition | SubclassDefinition,
    level: int,
):
    return next(
        row for row in definition.level_definitions if row.class_level == level
    )


def _grant_ids(
    definition: ClassDefinition | SubclassDefinition,
    level: int,
) -> tuple[str, ...]:
    return tuple(
        ref.content_id for ref in _level(definition, level).automatic_grant_refs
    )


def _choice_kinds(
    definition: ClassDefinition | SubclassDefinition,
    level: int,
) -> tuple[ChoiceRequirementKind, ...]:
    return tuple(
        row.choice_kind for row in _level(definition, level).choice_requirements
    )


def test_barbarian_and_berserker_are_exact_nonconstructible_definitions() -> None:
    assert BARBARIAN_PROGRESSION_DECLARATIONS == (
        BARBARIAN_CLASS_DECLARATION,
        BERSERKER_SUBCLASS_DECLARATION,
    )
    assert (
        BARBARIAN_CLASS_DECLARATION.mode
        is ContentDeclarationMode.TYPED_DEFINITION
    )
    assert (
        BERSERKER_SUBCLASS_DECLARATION.mode
        is ContentDeclarationMode.TYPED_DEFINITION
    )
    assert (
        BARBARIAN_CLASS_DECLARATION.ref.definition_kind
        is ContentDefinitionKind.CLASS
    )
    assert (
        BERSERKER_SUBCLASS_DECLARATION.ref.definition_kind
        is ContentDefinitionKind.SUBCLASS
    )
    assert BARBARIAN_CLASS_DECLARATION.ref.content_id == "class.barbarian"
    assert (
        BERSERKER_SUBCLASS_DECLARATION.ref.content_id
        == "subclass.barbarian.berserker"
    )
    assert BERSERKER_SUBCLASS_DEFINITION.parent_class_ref == (
        BARBARIAN_CLASS_DECLARATION.ref
    )


def test_barbarian_entry_modes_saves_and_prerequisite_are_exact() -> None:
    definition = BARBARIAN_CLASS_DEFINITION
    assert definition.hit_die == 12
    assert definition.caster_progression is CasterProgression.NON_CASTER
    assert definition.saving_throw_proficiencies == (
        AbilityScoreName.CONSTITUTION,
        AbilityScoreName.STRENGTH,
    )
    assert isinstance(
        definition.multiclass_prerequisite,
        AbilityScorePrerequisite,
    )
    assert (
        definition.multiclass_prerequisite.ability,
        definition.multiclass_prerequisite.minimum,
    ) == (AbilityScoreName.STRENGTH, 13)

    assert tuple(
        (row.subject_kind, row.subject_id)
        for row in definition.first_class_proficiencies.automatic
    ) == (
        (ProficiencySubjectKind.ARMOR, "armor.light"),
        (ProficiencySubjectKind.ARMOR, "armor.medium"),
        (ProficiencySubjectKind.SHIELD, "shield.shield"),
        (ProficiencySubjectKind.WEAPON, "weapon.martial"),
        (ProficiencySubjectKind.WEAPON, "weapon.simple"),
    )
    assert tuple(
        (row.subject_kind, row.subject_id)
        for row in definition.multiclass_proficiencies.automatic
    ) == (
        (ProficiencySubjectKind.SHIELD, "shield.shield"),
        (ProficiencySubjectKind.WEAPON, "weapon.martial"),
        (ProficiencySubjectKind.WEAPON, "weapon.simple"),
    )
    first_choices = definition.first_class_proficiencies.choices
    assert len(first_choices) == 2
    package_choice = next(
        row
        for row in first_choices
        if row.choice_kind
        is ChoiceRequirementKind.STARTING_EQUIPMENT_PACKAGE
    )
    skill_choice = next(
        row
        for row in first_choices
        if row.choice_kind is ChoiceRequirementKind.CLASS_SKILL
    )
    assert (
        package_choice.minimum_selections,
        package_choice.maximum_selections,
    ) == (1, 1)
    assert all(
        ref.definition_kind
        is ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE
        for ref in package_choice.allowed_refs
    )
    assert (
        skill_choice.minimum_selections,
        skill_choice.maximum_selections,
    ) == (2, 2)
    assert tuple(
        row.subject_id for row in skill_choice.allowed_proficiency_subjects
    ) == (
        "skill.animal_handling",
        "skill.athletics",
        "skill.intimidation",
        "skill.nature",
        "skill.perception",
        "skill.survival",
    )
    assert definition.multiclass_proficiencies.choices == ()


def test_barbarian_has_all_levels_and_exact_threshold_grants() -> None:
    assert tuple(
        row.class_level for row in BARBARIAN_CLASS_DEFINITION.level_definitions
    ) == tuple(range(1, 21))

    expected = {
        1: (
            "class_feature.barbarian.rage",
            "class_feature.barbarian.unarmored_defense",
        ),
        2: (
            "class_feature.barbarian.danger_sense",
            "class_feature.barbarian.reckless_attack",
        ),
        3: ("class_feature.barbarian.rage",),
        5: (
            "class_feature.barbarian.fast_movement",
            "class_feature.extra_attack",
        ),
        6: ("class_feature.barbarian.rage",),
        7: ("class_feature.barbarian.feral_instinct",),
        9: (
            "class_feature.barbarian.brutal_critical",
            "class_feature.barbarian.rage",
        ),
        11: ("class_feature.barbarian.relentless_rage",),
        12: ("class_feature.barbarian.rage",),
        13: ("class_feature.barbarian.brutal_critical",),
        15: ("class_feature.barbarian.persistent_rage",),
        16: ("class_feature.barbarian.rage",),
        17: (
            "class_feature.barbarian.brutal_critical",
            "class_feature.barbarian.rage",
        ),
        18: ("class_feature.barbarian.indomitable_might",),
        20: (
            "class_feature.barbarian.primal_champion",
            "class_feature.barbarian.rage",
        ),
    }
    assert {
        level: grants
        for level in range(1, 21)
        if (grants := _grant_ids(BARBARIAN_CLASS_DEFINITION, level))
    } == expected

    assert _level(
        BARBARIAN_CLASS_DEFINITION,
        1,
    ).automatic_grant_refs == tuple(sorted(
        (
            BARBARIAN_RAGE_DECLARATION.ref,
            UNARMORED_DEFENSE_DECLARATION.ref,
        ),
        key=lambda ref: ref.identity_key,
    ))
    assert FIGHTER_EXTRA_ATTACK_DECLARATION.ref in _level(
        BARBARIAN_CLASS_DEFINITION,
        5,
    ).automatic_grant_refs
    assert _level(
        BARBARIAN_CLASS_DEFINITION,
        9,
    ).automatic_grant_refs == tuple(sorted(
        (
            BARBARIAN_BRUTAL_CRITICAL_DECLARATION.ref,
            BARBARIAN_RAGE_DECLARATION.ref,
        ),
        key=lambda ref: ref.identity_key,
    ))


def test_barbarian_choices_are_subclass_then_exact_asi_or_feat_rows() -> None:
    assert _choice_kinds(BARBARIAN_CLASS_DEFINITION, 1) == ()
    assert _choice_kinds(BARBARIAN_CLASS_DEFINITION, 3) == (
        ChoiceRequirementKind.SUBCLASS,
    )
    subclass = _level(
        BARBARIAN_CLASS_DEFINITION,
        3,
    ).choice_requirements[0]
    assert subclass.allowed_refs == (BERSERKER_SUBCLASS_DECLARATION.ref,)

    lucky_ref = LUCKY_FEAT_DECLARATION.ref
    for level in (4, 8, 12, 16, 19):
        assert _choice_kinds(BARBARIAN_CLASS_DEFINITION, level) == (
            ChoiceRequirementKind.ABILITY_SCORE_IMPROVEMENT_OR_FEAT,
        )
        requirement = _level(
            BARBARIAN_CLASS_DEFINITION,
            level,
        ).choice_requirements[0]
        assert requirement.minimum_selections == 1
        assert requirement.maximum_selections == 1
        assert requirement.allowed_refs == (lucky_ref,)


def test_berserker_rows_cover_all_exact_subclass_thresholds() -> None:
    assert tuple(
        row.class_level
        for row in BERSERKER_SUBCLASS_DEFINITION.level_definitions
    ) == tuple(range(1, 21))
    assert {
        level: grants
        for level in range(1, 21)
        if (grants := _grant_ids(BERSERKER_SUBCLASS_DEFINITION, level))
    } == {
        3: ("class_feature.barbarian.frenzy",),
        6: ("class_feature.barbarian.mindless_rage",),
        10: ("class_feature.barbarian.intimidating_presence",),
        14: ("class_feature.barbarian.retaliation",),
    }
    assert _level(
        BERSERKER_SUBCLASS_DEFINITION,
        3,
    ).automatic_grant_refs == (BARBARIAN_FRENZY_DECLARATION.ref,)


def test_progressions_close_over_every_offered_and_granted_definition() -> None:
    barbarian_dependencies = {
        (row.relation, row.target_ref)
        for row in BARBARIAN_CLASS_DECLARATION.dependencies
    }
    assert (
        ContentDependencyRelation.OFFERS_SUBCLASS,
        BERSERKER_SUBCLASS_DECLARATION.ref,
    ) in barbarian_dependencies
    for level in BARBARIAN_CLASS_DEFINITION.level_definitions:
        for ref in level.automatic_grant_refs:
            assert (
                ContentDependencyRelation.GRANTS_FEATURE,
                ref,
            ) in barbarian_dependencies
        for choice in level.choice_requirements:
            for ref in choice.allowed_refs:
                relation = (
                    ContentDependencyRelation.OFFERS_SUBCLASS
                    if ref.definition_kind is ContentDefinitionKind.SUBCLASS
                    else (
                        ContentDependencyRelation.OFFERS_STARTING_EQUIPMENT
                        if ref.definition_kind
                        is ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE
                        else ContentDependencyRelation.GRANTS_FEATURE
                    )
                )
                assert (relation, ref) in barbarian_dependencies
    for choice in (
        BARBARIAN_CLASS_DEFINITION.first_class_proficiencies.choices
    ):
        for ref in choice.allowed_refs:
            if (
                ref.definition_kind
                is ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE
            ):
                assert (
                    ContentDependencyRelation.OFFERS_STARTING_EQUIPMENT,
                    ref,
                ) in barbarian_dependencies

    berserker_dependencies = {
        (row.relation, row.target_ref)
        for row in BERSERKER_SUBCLASS_DECLARATION.dependencies
    }
    for level in BERSERKER_SUBCLASS_DEFINITION.level_definitions:
        for ref in level.automatic_grant_refs:
            assert (
                ContentDependencyRelation.GRANTS_FEATURE,
                ref,
            ) in berserker_dependencies
