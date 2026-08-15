"""Focused authored-definition coverage for Fighter and Champion."""

from dnd.classes.progression_definitions import (
    CHAMPION_SUBCLASS_DECLARATION,
    CHAMPION_SUBCLASS_DEFINITION,
    FIGHTER_CLASS_DECLARATION,
    FIGHTER_CLASS_DEFINITION,
    FIGHTER_PROGRESSION_DECLARATIONS,
)
from dnd.classes.permanent_feature_definitions import (
    FIGHTER_ACTION_SURGE_DECLARATION,
    FIGHTER_ARCHERY_DECLARATION,
    FIGHTER_DEFENSE_DECLARATION,
    FIGHTER_DUELING_DECLARATION,
    FIGHTER_EXTRA_ATTACK_DECLARATION,
    FIGHTER_GREAT_WEAPON_FIGHTING_DECLARATION,
    FIGHTER_INDOMITABLE_DECLARATION,
    FIGHTER_PROTECTION_DECLARATION,
    FIGHTER_SECOND_WIND_DECLARATION,
    FIGHTER_TWO_WEAPON_FIGHTING_DECLARATION,
)
from dnd.classes.structural_feature_definitions import (
    REMARKABLE_ATHLETE_DECLARATION,
)
from dnd.types.abilities import AbilityName
from dnd.core.content.durable_characters import (
    AbilityScorePrerequisite,
    AnyOfPrerequisite,
    ChoiceRequirementKind,
    ClassDefinition,
    ProficiencySubjectKind,
    SubclassDefinition,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.registration import ContentDeclarationMode
from dnd.types.progression import CasterProgression
def _level(definition: ClassDefinition | SubclassDefinition, level: int):
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


def test_fighter_and_champion_are_exact_nonconstructible_definitions() -> None:
    assert FIGHTER_PROGRESSION_DECLARATIONS == (
        FIGHTER_CLASS_DECLARATION,
        CHAMPION_SUBCLASS_DECLARATION,
    )
    assert FIGHTER_CLASS_DECLARATION.mode is ContentDeclarationMode.TYPED_DEFINITION
    assert (
        CHAMPION_SUBCLASS_DECLARATION.mode
        is ContentDeclarationMode.TYPED_DEFINITION
    )
    assert FIGHTER_CLASS_DECLARATION.ref.definition_kind is ContentDefinitionKind.CLASS
    assert (
        CHAMPION_SUBCLASS_DECLARATION.ref.definition_kind
        is ContentDefinitionKind.SUBCLASS
    )
    assert FIGHTER_CLASS_DECLARATION.ref.content_id == "class.fighter"
    assert (
        CHAMPION_SUBCLASS_DECLARATION.ref.content_id
        == "subclass.fighter.champion"
    )
    assert CHAMPION_SUBCLASS_DEFINITION.parent_class_ref == (
        FIGHTER_CLASS_DECLARATION.ref
    )


def test_fighter_entry_modes_and_saves_are_authored_exactly() -> None:
    definition = FIGHTER_CLASS_DEFINITION
    assert definition.hit_die == 10
    assert definition.caster_progression is CasterProgression.NON_CASTER
    assert definition.saving_throw_proficiencies == (
        AbilityName.CONSTITUTION,
        AbilityName.STRENGTH,
    )

    assert tuple(
        (row.subject_kind, row.subject_id)
        for row in definition.first_class_proficiencies.automatic
    ) == (
        (ProficiencySubjectKind.ARMOR, "armor.heavy"),
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
        (ProficiencySubjectKind.ARMOR, "armor.light"),
        (ProficiencySubjectKind.ARMOR, "armor.medium"),
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
    assert (skill_choice.minimum_selections, skill_choice.maximum_selections) == (
        2,
        2,
    )
    assert tuple(
        row.subject_id for row in skill_choice.allowed_proficiency_subjects
    ) == (
        "skill.acrobatics",
        "skill.animal_handling",
        "skill.athletics",
        "skill.history",
        "skill.insight",
        "skill.intimidation",
        "skill.perception",
        "skill.survival",
    )
    assert definition.multiclass_proficiencies.choices == ()
    assert isinstance(definition.multiclass_prerequisite, AnyOfPrerequisite)
    assert tuple(
        (row.ability, row.minimum)
        for row in definition.multiclass_prerequisite.prerequisites
        if isinstance(row, AbilityScorePrerequisite)
    ) == (
        (AbilityName.DEXTERITY, 13),
        (AbilityName.STRENGTH, 13),
    )


def test_fighter_has_every_level_and_exact_threshold_grants() -> None:
    assert tuple(
        row.class_level for row in FIGHTER_CLASS_DEFINITION.level_definitions
    ) == tuple(range(1, 21))

    expected = {
        1: ("class_feature.fighter.second_wind",),
        2: ("class_feature.fighter.action_surge",),
        5: ("class_feature.extra_attack",),
        9: ("class_feature.fighter.indomitable",),
        11: ("class_feature.extra_attack",),
        13: ("class_feature.fighter.indomitable",),
        17: (
            "class_feature.fighter.action_surge",
            "class_feature.fighter.indomitable",
        ),
        20: ("class_feature.extra_attack",),
    }
    assert {
        level: grants
        for level in range(1, 21)
        if (grants := _grant_ids(FIGHTER_CLASS_DEFINITION, level))
    } == expected

    assert FIGHTER_SECOND_WIND_DECLARATION.ref in (
        _level(FIGHTER_CLASS_DEFINITION, 1).automatic_grant_refs
    )
    assert FIGHTER_ACTION_SURGE_DECLARATION.ref in (
        _level(FIGHTER_CLASS_DEFINITION, 2).automatic_grant_refs
    )
    assert FIGHTER_EXTRA_ATTACK_DECLARATION.ref in (
        _level(FIGHTER_CLASS_DEFINITION, 5).automatic_grant_refs
    )
    assert FIGHTER_INDOMITABLE_DECLARATION.ref in (
        _level(FIGHTER_CLASS_DEFINITION, 9).automatic_grant_refs
    )


def test_fighter_level_choices_are_complete_and_exact() -> None:
    assert _choice_kinds(FIGHTER_CLASS_DEFINITION, 1) == (
        ChoiceRequirementKind.FIGHTING_STYLE,
    )
    assert _choice_kinds(FIGHTER_CLASS_DEFINITION, 3) == (
        ChoiceRequirementKind.SUBCLASS,
    )
    for level in (4, 6, 8, 12, 14, 16, 19):
        assert _choice_kinds(FIGHTER_CLASS_DEFINITION, level) == (
            ChoiceRequirementKind.ABILITY_SCORE_IMPROVEMENT_OR_FEAT,
        )

    first_style = _level(FIGHTER_CLASS_DEFINITION, 1).choice_requirements[0]
    second_style = _level(
        CHAMPION_SUBCLASS_DEFINITION,
        10,
    ).choice_requirements[0]
    expected_styles = tuple(sorted(
        (
            FIGHTER_ARCHERY_DECLARATION.ref,
            FIGHTER_DEFENSE_DECLARATION.ref,
            FIGHTER_DUELING_DECLARATION.ref,
            FIGHTER_GREAT_WEAPON_FIGHTING_DECLARATION.ref,
            FIGHTER_PROTECTION_DECLARATION.ref,
            FIGHTER_TWO_WEAPON_FIGHTING_DECLARATION.ref,
        ),
        key=lambda ref: ref.identity_key,
    ))
    assert first_style.allowed_refs == expected_styles
    assert second_style.allowed_refs == expected_styles
    assert first_style.choice_id != second_style.choice_id

    subclass = _level(FIGHTER_CLASS_DEFINITION, 3).choice_requirements[0]
    assert subclass.allowed_refs == (CHAMPION_SUBCLASS_DECLARATION.ref,)

    for level in (4, 6, 8, 12, 14, 16, 19):
        requirement = _level(
            FIGHTER_CLASS_DEFINITION,
            level,
        ).choice_requirements[0]
        assert requirement.minimum_selections == 1
        assert requirement.maximum_selections == 1
        assert tuple(ref.content_id for ref in requirement.allowed_refs) == (
            "feat.lucky",
        )


def test_champion_has_every_level_and_exact_feature_rows() -> None:
    assert tuple(
        row.class_level for row in CHAMPION_SUBCLASS_DEFINITION.level_definitions
    ) == tuple(range(1, 21))
    assert {
        level: grants
        for level in range(1, 21)
        if (grants := _grant_ids(CHAMPION_SUBCLASS_DEFINITION, level))
    } == {
        3: ("class_feature.fighter.improved_critical",),
        7: ("class_feature.fighter.remarkable_athlete",),
        15: ("class_feature.fighter.superior_critical",),
        18: ("class_feature.fighter.survivor",),
    }
    assert _level(
        CHAMPION_SUBCLASS_DEFINITION,
        7,
    ).automatic_grant_refs == (REMARKABLE_ATHLETE_DECLARATION.ref,)
    assert _choice_kinds(CHAMPION_SUBCLASS_DEFINITION, 10) == (
        ChoiceRequirementKind.FIGHTING_STYLE,
    )
