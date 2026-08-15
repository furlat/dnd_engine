"""Pure authored Barbarian and Berserker progression definitions.

This module owns only immutable build data and exact content references. It
does not install runtime conditions, mutate entities, or call the legacy
one-shot class factory.
"""

from dnd.classes.permanent_feature_definitions import (
    BARBARIAN_BRUTAL_CRITICAL_DECLARATION,
    BARBARIAN_DANGER_SENSE_DECLARATION,
    BARBARIAN_FAST_MOVEMENT_DECLARATION,
    BARBARIAN_FERAL_INSTINCT_DECLARATION,
    BARBARIAN_FRENZY_DECLARATION,
    BARBARIAN_INDOMITABLE_MIGHT_DECLARATION,
    BARBARIAN_INTIMIDATING_PRESENCE_DECLARATION,
    BARBARIAN_MINDLESS_RAGE_DECLARATION,
    BARBARIAN_PERSISTENT_RAGE_DECLARATION,
    BARBARIAN_PRIMAL_CHAMPION_DECLARATION,
    BARBARIAN_RAGE_DECLARATION,
    BARBARIAN_RECKLESS_ATTACK_DECLARATION,
    BARBARIAN_RELENTLESS_RAGE_DECLARATION,
    BARBARIAN_RETALIATION_DECLARATION,
    FIGHTER_EXTRA_ATTACK_DECLARATION,
    LUCKY_FEAT_DECLARATION,
)
from dnd.classes.progression_definition_helpers import (
    ordered_refs,
    proficiency_subject,
    progression_dependencies,
    single_ref_choice,
    structural_progression_provenance,
    typed_progression_ref,
)
from dnd.classes.structural_feature_definitions import (
    UNARMORED_DEFENSE_DECLARATION,
)
from dnd.classes.starting_equipment_refs import (
    STARTING_EQUIPMENT_PACKAGE_REFS_BY_CLASS,
)
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.types.abilities import AbilityName
from dnd.core.content.durable_characters import (
    AbilityScorePrerequisite,
    BuildChoiceRequirement,
    ChoiceRequirementKind,
    ClassDefinition,
    ClassLevelDefinition,
    ClassProficiencyPackage,
    ProficiencySubjectKind,
    SubclassDefinition,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.registration import (
    ContentDeclaration,
    get_content_declaration,
    typed_definition,
)
from dnd.types.progression import CasterProgression


_PACK_ID = "content.srd_5_1_cc"
_VERSION = 1


BARBARIAN_CLASS_REF = typed_progression_ref(
    pack_id=_PACK_ID,
    version=_VERSION,
    definition_kind=ContentDefinitionKind.CLASS,
    content_id="class.barbarian",
    definition_model=ClassDefinition,
)
BERSERKER_SUBCLASS_REF = typed_progression_ref(
    pack_id=_PACK_ID,
    version=_VERSION,
    definition_kind=ContentDefinitionKind.SUBCLASS,
    content_id="subclass.barbarian.berserker",
    definition_model=SubclassDefinition,
)


_RAGE_REF = BARBARIAN_RAGE_DECLARATION.ref
_RECKLESS_ATTACK_REF = BARBARIAN_RECKLESS_ATTACK_DECLARATION.ref
_DANGER_SENSE_REF = BARBARIAN_DANGER_SENSE_DECLARATION.ref
_EXTRA_ATTACK_REF = FIGHTER_EXTRA_ATTACK_DECLARATION.ref
_FAST_MOVEMENT_REF = BARBARIAN_FAST_MOVEMENT_DECLARATION.ref
_FERAL_INSTINCT_REF = BARBARIAN_FERAL_INSTINCT_DECLARATION.ref
_BRUTAL_CRITICAL_REF = BARBARIAN_BRUTAL_CRITICAL_DECLARATION.ref
_RELENTLESS_RAGE_REF = BARBARIAN_RELENTLESS_RAGE_DECLARATION.ref
_PERSISTENT_RAGE_REF = BARBARIAN_PERSISTENT_RAGE_DECLARATION.ref
_INDOMITABLE_MIGHT_REF = BARBARIAN_INDOMITABLE_MIGHT_DECLARATION.ref
_PRIMAL_CHAMPION_REF = BARBARIAN_PRIMAL_CHAMPION_DECLARATION.ref
_FRENZY_REF = BARBARIAN_FRENZY_DECLARATION.ref
_MINDLESS_RAGE_REF = BARBARIAN_MINDLESS_RAGE_DECLARATION.ref
_INTIMIDATING_PRESENCE_REF = (
    BARBARIAN_INTIMIDATING_PRESENCE_DECLARATION.ref
)
_RETALIATION_REF = BARBARIAN_RETALIATION_DECLARATION.ref
_LUCKY_FEAT_REF = LUCKY_FEAT_DECLARATION.ref


_BARBARIAN_SKILL_SUBJECTS = tuple(
    proficiency_subject(ProficiencySubjectKind.SKILL, f"skill.{skill}")
    for skill in (
        "animal_handling",
        "athletics",
        "intimidation",
        "nature",
        "perception",
        "survival",
    )
)

_BARBARIAN_FIRST_PROFICIENCIES = ClassProficiencyPackage(
    automatic=(
        proficiency_subject(ProficiencySubjectKind.ARMOR, "armor.light"),
        proficiency_subject(ProficiencySubjectKind.ARMOR, "armor.medium"),
        proficiency_subject(ProficiencySubjectKind.SHIELD, "shield.shield"),
        proficiency_subject(ProficiencySubjectKind.WEAPON, "weapon.martial"),
        proficiency_subject(ProficiencySubjectKind.WEAPON, "weapon.simple"),
    ),
    choices=(
        BuildChoiceRequirement(
            choice_id="class.barbarian.first_class.starting_equipment",
            choice_kind=ChoiceRequirementKind.STARTING_EQUIPMENT_PACKAGE,
            minimum_selections=1,
            maximum_selections=1,
            allowed_refs=STARTING_EQUIPMENT_PACKAGE_REFS_BY_CLASS[
                "barbarian"
            ],
        ),
        BuildChoiceRequirement(
            choice_id="class.barbarian.proficiencies.skills",
            choice_kind=ChoiceRequirementKind.CLASS_SKILL,
            minimum_selections=2,
            maximum_selections=2,
            allowed_proficiency_subjects=_BARBARIAN_SKILL_SUBJECTS,
        ),
    ),
)

_BARBARIAN_MULTICLASS_PROFICIENCIES = ClassProficiencyPackage(
    automatic=(
        proficiency_subject(ProficiencySubjectKind.SHIELD, "shield.shield"),
        proficiency_subject(ProficiencySubjectKind.WEAPON, "weapon.martial"),
        proficiency_subject(ProficiencySubjectKind.WEAPON, "weapon.simple"),
    ),
)


def _asi_or_feat(level: int) -> BuildChoiceRequirement:
    return single_ref_choice(
        choice_id=f"class.barbarian.level_{level}.asi_or_feat",
        choice_kind=ChoiceRequirementKind.ABILITY_SCORE_IMPROVEMENT_OR_FEAT,
        allowed_refs=(_LUCKY_FEAT_REF,),
    )


_BARBARIAN_LEVEL_GRANTS: dict[int, tuple[ContentRef, ...]] = {
    1: ordered_refs(
        _RAGE_REF,
        UNARMORED_DEFENSE_DECLARATION.ref,
    ),
    2: ordered_refs(_RECKLESS_ATTACK_REF, _DANGER_SENSE_REF),
    3: (_RAGE_REF,),
    5: ordered_refs(_EXTRA_ATTACK_REF, _FAST_MOVEMENT_REF),
    6: (_RAGE_REF,),
    7: (_FERAL_INSTINCT_REF,),
    9: ordered_refs(_RAGE_REF, _BRUTAL_CRITICAL_REF),
    11: (_RELENTLESS_RAGE_REF,),
    12: (_RAGE_REF,),
    13: (_BRUTAL_CRITICAL_REF,),
    15: (_PERSISTENT_RAGE_REF,),
    16: (_RAGE_REF,),
    17: ordered_refs(_RAGE_REF, _BRUTAL_CRITICAL_REF),
    18: (_INDOMITABLE_MIGHT_REF,),
    20: ordered_refs(_RAGE_REF, _PRIMAL_CHAMPION_REF),
}
_BARBARIAN_LEVEL_CHOICES: dict[
    int,
    tuple[BuildChoiceRequirement, ...],
] = {
    3: (
        single_ref_choice(
            choice_id="class.barbarian.level_3.subclass",
            choice_kind=ChoiceRequirementKind.SUBCLASS,
            allowed_refs=(BERSERKER_SUBCLASS_REF,),
        ),
    ),
    **{
        level: (_asi_or_feat(level),)
        for level in (4, 8, 12, 16, 19)
    },
}

BARBARIAN_CLASS_DEFINITION = ClassDefinition(
    hit_die=12,
    caster_progression=CasterProgression.NON_CASTER,
    multiclass_prerequisite=AbilityScorePrerequisite(
        ability=AbilityName.STRENGTH,
        minimum=13,
    ),
    first_class_proficiencies=_BARBARIAN_FIRST_PROFICIENCIES,
    multiclass_proficiencies=_BARBARIAN_MULTICLASS_PROFICIENCIES,
    saving_throw_proficiencies=(
        AbilityName.CONSTITUTION,
        AbilityName.STRENGTH,
    ),
    level_definitions=tuple(
        ClassLevelDefinition(
            class_level=level,
            automatic_grant_refs=_BARBARIAN_LEVEL_GRANTS.get(level, ()),
            choice_requirements=_BARBARIAN_LEVEL_CHOICES.get(level, ()),
        )
        for level in range(1, 21)
    ),
)

_BERSERKER_LEVEL_GRANTS: dict[int, tuple[ContentRef, ...]] = {
    3: (_FRENZY_REF,),
    6: (_MINDLESS_RAGE_REF,),
    10: (_INTIMIDATING_PRESENCE_REF,),
    14: (_RETALIATION_REF,),
}

BERSERKER_SUBCLASS_DEFINITION = SubclassDefinition(
    parent_class_ref=BARBARIAN_CLASS_REF,
    level_definitions=tuple(
        ClassLevelDefinition(
            class_level=level,
            automatic_grant_refs=_BERSERKER_LEVEL_GRANTS.get(level, ()),
        )
        for level in range(1, 21)
    ),
)


_BARBARIAN_FEATURE_DEPENDENCIES = progression_dependencies(
    (
        UNARMORED_DEFENSE_DECLARATION.ref,
        _RAGE_REF,
        _RECKLESS_ATTACK_REF,
        _DANGER_SENSE_REF,
        _EXTRA_ATTACK_REF,
        _FAST_MOVEMENT_REF,
        _FERAL_INSTINCT_REF,
        _BRUTAL_CRITICAL_REF,
        _RELENTLESS_RAGE_REF,
        _PERSISTENT_RAGE_REF,
        _INDOMITABLE_MIGHT_REF,
        _PRIMAL_CHAMPION_REF,
        _LUCKY_FEAT_REF,
    ),
    relation=ContentDependencyRelation.GRANTS_FEATURE,
    notes="Offered or granted by this structural progression.",
)
_BERSERKER_FEATURE_DEPENDENCIES = progression_dependencies(
    (
        _FRENZY_REF,
        _MINDLESS_RAGE_REF,
        _INTIMIDATING_PRESENCE_REF,
        _RETALIATION_REF,
    ),
    relation=ContentDependencyRelation.GRANTS_FEATURE,
    notes="Offered or granted by this structural progression.",
)


@typed_definition(
    definition_kind=ContentDefinitionKind.CLASS,
    pack_id=_PACK_ID,
    content_id="class.barbarian",
    version=_VERSION,
    descriptor=ContentDescriptorSpec(
        display_name="Barbarian",
        description=(
            "A primal warrior who channels Rage, fights recklessly, and "
            "survives through instinct, endurance, and overwhelming strength."
        ),
        tags=("barbarian", "class", "martial", "player_capable"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="action.rage",
            visual_variant_key="class.barbarian",
            ui_group="classes",
        ),
        ordering=ContentOrdering(sort_group="classes", sort_order=10),
        related_content_refs=(BERSERKER_SUBCLASS_REF,),
    ),
    provenance=structural_progression_provenance(
        "SRD 5.1 Barbarian class progression, levels 1–20",
    ),
    definition=BARBARIAN_CLASS_DEFINITION,
    dependencies=(
        *_BARBARIAN_FEATURE_DEPENDENCIES,
        *(
            ContentDependency(
                relation=(
                    ContentDependencyRelation.OFFERS_STARTING_EQUIPMENT
                ),
                target_ref=ref,
                phase=ContentDependencyPhase.RUNTIME_REFERENCE,
                notes="Exact Barbarian starting package offered at level one.",
            )
            for ref in STARTING_EQUIPMENT_PACKAGE_REFS_BY_CLASS[
                "barbarian"
            ]
        ),
        ContentDependency(
            relation=ContentDependencyRelation.OFFERS_SUBCLASS,
            target_ref=BERSERKER_SUBCLASS_REF,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Path of the Berserker is the SRD Barbarian subclass.",
        ),
    ),
)
class BarbarianProgressionDefinition:
    """Marker for the immutable Barbarian progression declaration."""


@typed_definition(
    definition_kind=ContentDefinitionKind.SUBCLASS,
    pack_id=_PACK_ID,
    content_id="subclass.barbarian.berserker",
    version=_VERSION,
    descriptor=ContentDescriptorSpec(
        display_name="Path of the Berserker",
        description=(
            "A Barbarian path focused on Frenzy, fearless Rage, an "
            "intimidating presence, and immediate retaliation."
        ),
        tags=("barbarian", "berserker", "martial", "subclass"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="condition.dnd-classes-rage-frenzyfeature",
            visual_variant_key="subclass.barbarian.berserker",
            ui_group="subclasses.barbarian",
        ),
        ordering=ContentOrdering(
            sort_group="subclasses.barbarian",
            sort_order=10,
        ),
        related_content_refs=(BARBARIAN_CLASS_REF,),
    ),
    provenance=structural_progression_provenance(
        "SRD 5.1 Barbarian: Path of the Berserker, levels 3–14",
    ),
    definition=BERSERKER_SUBCLASS_DEFINITION,
    dependencies=_BERSERKER_FEATURE_DEPENDENCIES,
)
class BerserkerProgressionDefinition:
    """Marker for the immutable Berserker progression declaration."""


BARBARIAN_CLASS_DECLARATION: ContentDeclaration = get_content_declaration(
    BarbarianProgressionDefinition,
)
BERSERKER_SUBCLASS_DECLARATION: ContentDeclaration = get_content_declaration(
    BerserkerProgressionDefinition,
)
if (
    BARBARIAN_CLASS_DECLARATION.ref != BARBARIAN_CLASS_REF
    or BERSERKER_SUBCLASS_DECLARATION.ref != BERSERKER_SUBCLASS_REF
):
    raise RuntimeError("Barbarian progression declaration contract mismatch")

BARBARIAN_PROGRESSION_DECLARATIONS: tuple[ContentDeclaration, ...] = (
    BARBARIAN_CLASS_DECLARATION,
    BERSERKER_SUBCLASS_DECLARATION,
)


__all__ = [
    "BARBARIAN_CLASS_DECLARATION",
    "BARBARIAN_CLASS_DEFINITION",
    "BARBARIAN_CLASS_REF",
    "BARBARIAN_PROGRESSION_DECLARATIONS",
    "BERSERKER_SUBCLASS_DECLARATION",
    "BERSERKER_SUBCLASS_DEFINITION",
    "BERSERKER_SUBCLASS_REF",
    "BarbarianProgressionDefinition",
    "BerserkerProgressionDefinition",
    "UNARMORED_DEFENSE_DECLARATION",
]
