"""Pure authored Fighter and Champion progression definitions.

This module owns only immutable build data and exact content references.  It
does not install runtime conditions, mutate entities, or call the legacy
one-shot class factories.
"""

from dnd.classes import feats, fighter
from dnd.classes.structural_feature_definitions import (
    REMARKABLE_ATHLETE_DECLARATION,
)
from dnd.content_system.condition_definitions import (
    CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS,
)
from dnd.classes.starting_equipment_refs import (
    STARTING_EQUIPMENT_PACKAGE_REFS_BY_CLASS,
)
from dnd.core.base_conditions import BaseCondition
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
from dnd.core.content.durable_characters import (
    AbilityScoreName,
    AbilityScorePrerequisite,
    AnyOfPrerequisite,
    BuildChoiceRequirement,
    ChoiceRequirementKind,
    ClassDefinition,
    ClassLevelDefinition,
    ClassProficiencyPackage,
    ProficiencySubject,
    ProficiencySubjectKind,
    SubclassDefinition,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
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
    typed_definition,
)
from dnd.core.progression import CasterProgression


_PACK_ID = "content.srd_5_1_cc"
_VERSION = 1


def _typed_ref(
    definition_kind: ContentDefinitionKind,
    content_id: str,
    definition_model: type[ClassDefinition] | type[SubclassDefinition],
) -> ContentRef:
    """Build the exact ref used by a typed-definition declaration."""
    return ContentRef(
        pack_id=_PACK_ID,
        definition_kind=definition_kind,
        content_id=content_id,
        content_version=_VERSION,
        definition_contract_hash=compute_definition_contract_hash(
            mode=ContentDeclarationMode.TYPED_DEFINITION,
            definition_kind=definition_kind,
            definition_model=definition_model,
        ),
    )


FIGHTER_CLASS_REF = _typed_ref(
    ContentDefinitionKind.CLASS,
    "class.fighter",
    ClassDefinition,
)
CHAMPION_SUBCLASS_REF = _typed_ref(
    ContentDefinitionKind.SUBCLASS,
    "subclass.fighter.champion",
    SubclassDefinition,
)


def _feature_ref(condition_type: type[BaseCondition]) -> ContentRef:
    """Resolve one existing condition-backed feature to its exact ref."""
    return CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[condition_type].ref


_SECOND_WIND_REF = _feature_ref(fighter.SecondWindFeature)
_ACTION_SURGE_REF = _feature_ref(fighter.ActionSurgeFeature)
_EXTRA_ATTACK_REF = _feature_ref(fighter.ExtraAttackFeature)
_INDOMITABLE_REF = _feature_ref(fighter.Indomitable)
_IMPROVED_CRITICAL_REF = _feature_ref(fighter.ImprovedCritical)
_SUPERIOR_CRITICAL_REF = _feature_ref(fighter.SuperiorCritical)
_SURVIVOR_REF = _feature_ref(fighter.Survivor)
_LUCKY_FEAT_REF = _feature_ref(feats.LuckyFeature)

_FIGHTING_STYLE_REFS = tuple(sorted(
    (
        _feature_ref(fighter.FightingStyleArchery),
        _feature_ref(fighter.FightingStyleDefense),
        _feature_ref(fighter.FightingStyleDueling),
        _feature_ref(fighter.GreatWeaponFighting),
        _feature_ref(fighter.FightingStyleProtection),
        _feature_ref(fighter.FightingStyleTwoWeaponFighting),
    ),
    key=lambda ref: ref.identity_key,
))


def _subject(
    kind: ProficiencySubjectKind,
    subject_id: str,
) -> ProficiencySubject:
    return ProficiencySubject(subject_kind=kind, subject_id=subject_id)


_FIGHTER_SKILL_SUBJECTS = tuple(
    _subject(ProficiencySubjectKind.SKILL, f"skill.{skill}")
    for skill in (
        "acrobatics",
        "animal_handling",
        "athletics",
        "history",
        "insight",
        "intimidation",
        "perception",
        "survival",
    )
)

_FIGHTER_FIRST_PROFICIENCIES = ClassProficiencyPackage(
    automatic=(
        _subject(ProficiencySubjectKind.ARMOR, "armor.heavy"),
        _subject(ProficiencySubjectKind.ARMOR, "armor.light"),
        _subject(ProficiencySubjectKind.ARMOR, "armor.medium"),
        _subject(ProficiencySubjectKind.SHIELD, "shield.shield"),
        _subject(ProficiencySubjectKind.WEAPON, "weapon.martial"),
        _subject(ProficiencySubjectKind.WEAPON, "weapon.simple"),
    ),
    choices=(
        BuildChoiceRequirement(
            choice_id="class.fighter.first_class.starting_equipment",
            choice_kind=ChoiceRequirementKind.STARTING_EQUIPMENT_PACKAGE,
            minimum_selections=1,
            maximum_selections=1,
            allowed_refs=STARTING_EQUIPMENT_PACKAGE_REFS_BY_CLASS["fighter"],
        ),
        BuildChoiceRequirement(
            choice_id="class.fighter.proficiencies.skills",
            choice_kind=ChoiceRequirementKind.CLASS_SKILL,
            minimum_selections=2,
            maximum_selections=2,
            allowed_proficiency_subjects=_FIGHTER_SKILL_SUBJECTS,
        ),
    ),
)

_FIGHTER_MULTICLASS_PROFICIENCIES = ClassProficiencyPackage(
    automatic=(
        _subject(ProficiencySubjectKind.ARMOR, "armor.light"),
        _subject(ProficiencySubjectKind.ARMOR, "armor.medium"),
        _subject(ProficiencySubjectKind.SHIELD, "shield.shield"),
        _subject(ProficiencySubjectKind.WEAPON, "weapon.martial"),
        _subject(ProficiencySubjectKind.WEAPON, "weapon.simple"),
    ),
)


def _choice(
    *,
    choice_id: str,
    choice_kind: ChoiceRequirementKind,
    allowed_refs: tuple[ContentRef, ...] = (),
) -> BuildChoiceRequirement:
    return BuildChoiceRequirement(
        choice_id=choice_id,
        choice_kind=choice_kind,
        minimum_selections=1,
        maximum_selections=1,
        allowed_refs=allowed_refs,
    )


def _asi_or_feat(level: int) -> BuildChoiceRequirement:
    return _choice(
        choice_id=f"class.fighter.level_{level}.asi_or_feat",
        choice_kind=ChoiceRequirementKind.ABILITY_SCORE_IMPROVEMENT_OR_FEAT,
        allowed_refs=(_LUCKY_FEAT_REF,),
    )


_FIGHTER_LEVEL_GRANTS: dict[int, tuple[ContentRef, ...]] = {
    1: (_SECOND_WIND_REF,),
    2: (_ACTION_SURGE_REF,),
    5: (_EXTRA_ATTACK_REF,),
    9: (_INDOMITABLE_REF,),
    11: (_EXTRA_ATTACK_REF,),
    13: (_INDOMITABLE_REF,),
    17: tuple(sorted(
        (_ACTION_SURGE_REF, _INDOMITABLE_REF),
        key=lambda ref: ref.identity_key,
    )),
    20: (_EXTRA_ATTACK_REF,),
}
_FIGHTER_LEVEL_CHOICES: dict[int, tuple[BuildChoiceRequirement, ...]] = {
    1: (
        _choice(
            choice_id="class.fighter.level_1.fighting_style",
            choice_kind=ChoiceRequirementKind.FIGHTING_STYLE,
            allowed_refs=_FIGHTING_STYLE_REFS,
        ),
    ),
    3: (
        _choice(
            choice_id="class.fighter.level_3.subclass",
            choice_kind=ChoiceRequirementKind.SUBCLASS,
            allowed_refs=(CHAMPION_SUBCLASS_REF,),
        ),
    ),
    **{
        level: (_asi_or_feat(level),)
        for level in (4, 6, 8, 12, 14, 16, 19)
    },
}

FIGHTER_CLASS_DEFINITION = ClassDefinition(
    hit_die=10,
    caster_progression=CasterProgression.NON_CASTER,
    multiclass_prerequisite=AnyOfPrerequisite(
        prerequisites=(
            AbilityScorePrerequisite(
                ability=AbilityScoreName.DEXTERITY,
                minimum=13,
            ),
            AbilityScorePrerequisite(
                ability=AbilityScoreName.STRENGTH,
                minimum=13,
            ),
        ),
    ),
    first_class_proficiencies=_FIGHTER_FIRST_PROFICIENCIES,
    multiclass_proficiencies=_FIGHTER_MULTICLASS_PROFICIENCIES,
    saving_throw_proficiencies=(
        AbilityScoreName.CONSTITUTION,
        AbilityScoreName.STRENGTH,
    ),
    level_definitions=tuple(
        ClassLevelDefinition(
            class_level=level,
            automatic_grant_refs=_FIGHTER_LEVEL_GRANTS.get(level, ()),
            choice_requirements=_FIGHTER_LEVEL_CHOICES.get(level, ()),
        )
        for level in range(1, 21)
    ),
)

_CHAMPION_LEVEL_GRANTS: dict[int, tuple[ContentRef, ...]] = {
    3: (_IMPROVED_CRITICAL_REF,),
    7: (REMARKABLE_ATHLETE_DECLARATION.ref,),
    15: (_SUPERIOR_CRITICAL_REF,),
    18: (_SURVIVOR_REF,),
}
_CHAMPION_LEVEL_CHOICES: dict[int, tuple[BuildChoiceRequirement, ...]] = {
    10: (
        _choice(
            choice_id="subclass.fighter.champion.level_10.fighting_style",
            choice_kind=ChoiceRequirementKind.FIGHTING_STYLE,
            allowed_refs=_FIGHTING_STYLE_REFS,
        ),
    ),
}

CHAMPION_SUBCLASS_DEFINITION = SubclassDefinition(
    parent_class_ref=FIGHTER_CLASS_REF,
    level_definitions=tuple(
        ClassLevelDefinition(
            class_level=level,
            automatic_grant_refs=_CHAMPION_LEVEL_GRANTS.get(level, ()),
            choice_requirements=_CHAMPION_LEVEL_CHOICES.get(level, ()),
        )
        for level in range(1, 21)
    ),
)


def _provenance(source_anchor: str) -> ContentProvenance:
    return ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=source_anchor,
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Pure additive structural definition; runtime mechanics are "
            "installed separately through exact source-owned grant bindings."
        ),
    )


def _feature_dependencies(
    refs: tuple[ContentRef, ...],
) -> tuple[ContentDependency, ...]:
    unique = {
        ref.identity_key: ref
        for ref in refs
    }
    return tuple(
        ContentDependency(
            relation=ContentDependencyRelation.GRANTS_FEATURE,
            target_ref=ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Offered or granted by this structural progression.",
        )
        for _, ref in sorted(unique.items())
    )


_FIGHTER_FEATURE_DEPENDENCIES = _feature_dependencies((
    _SECOND_WIND_REF,
    _ACTION_SURGE_REF,
    _EXTRA_ATTACK_REF,
    _INDOMITABLE_REF,
    _LUCKY_FEAT_REF,
    *_FIGHTING_STYLE_REFS,
))
_CHAMPION_FEATURE_DEPENDENCIES = _feature_dependencies((
    _IMPROVED_CRITICAL_REF,
    REMARKABLE_ATHLETE_DECLARATION.ref,
    _SUPERIOR_CRITICAL_REF,
    _SURVIVOR_REF,
    *_FIGHTING_STYLE_REFS,
))


@typed_definition(
    definition_kind=ContentDefinitionKind.CLASS,
    pack_id=_PACK_ID,
    content_id="class.fighter",
    version=_VERSION,
    descriptor=ContentDescriptorSpec(
        display_name="Fighter",
        description=(
            "A master of martial combat with adaptable Fighting Styles, "
            "Second Wind, Action Surge, and progressively stronger attacks."
        ),
        tags=("class", "fighter", "martial", "player_capable"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="action.extra-attack",
            visual_variant_key="class.fighter",
            ui_group="classes",
        ),
        ordering=ContentOrdering(sort_group="classes", sort_order=20),
        related_content_refs=(CHAMPION_SUBCLASS_REF,),
    ),
    provenance=_provenance("SRD 5.1 Fighter class progression, levels 1–20"),
    definition=FIGHTER_CLASS_DEFINITION,
    dependencies=(
        *_FIGHTER_FEATURE_DEPENDENCIES,
        *(
            ContentDependency(
                relation=(
                    ContentDependencyRelation.OFFERS_STARTING_EQUIPMENT
                ),
                target_ref=ref,
                phase=ContentDependencyPhase.RUNTIME_REFERENCE,
                notes="Exact Fighter starting package offered at level one.",
            )
            for ref in STARTING_EQUIPMENT_PACKAGE_REFS_BY_CLASS["fighter"]
        ),
        ContentDependency(
            relation=ContentDependencyRelation.OFFERS_SUBCLASS,
            target_ref=CHAMPION_SUBCLASS_REF,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Champion is the SRD Fighter subclass.",
        ),
    ),
)
class FighterProgressionDefinition:
    """Marker for the immutable Fighter progression declaration."""


@typed_definition(
    definition_kind=ContentDefinitionKind.SUBCLASS,
    pack_id=_PACK_ID,
    content_id="subclass.fighter.champion",
    version=_VERSION,
    descriptor=ContentDescriptorSpec(
        display_name="Champion",
        description=(
            "A Fighter archetype focused on expanded critical hits, broad "
            "athletic talent, another Fighting Style, and martial endurance."
        ),
        tags=("champion", "fighter", "martial", "subclass"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="condition.dnd-classes-fighter-improvedcritical",
            visual_variant_key="subclass.fighter.champion",
            ui_group="subclasses.fighter",
        ),
        ordering=ContentOrdering(
            sort_group="subclasses.fighter",
            sort_order=10,
        ),
        related_content_refs=(FIGHTER_CLASS_REF,),
    ),
    provenance=_provenance(
        "SRD 5.1 Fighter: Champion martial archetype, levels 3–18",
    ),
    definition=CHAMPION_SUBCLASS_DEFINITION,
    dependencies=_CHAMPION_FEATURE_DEPENDENCIES,
)
class ChampionProgressionDefinition:
    """Marker for the immutable Champion progression declaration."""


FIGHTER_CLASS_DECLARATION: ContentDeclaration = get_content_declaration(
    FighterProgressionDefinition,
)
CHAMPION_SUBCLASS_DECLARATION: ContentDeclaration = get_content_declaration(
    ChampionProgressionDefinition,
)
if (
    FIGHTER_CLASS_DECLARATION.ref != FIGHTER_CLASS_REF
    or CHAMPION_SUBCLASS_DECLARATION.ref != CHAMPION_SUBCLASS_REF
):
    raise RuntimeError("Fighter progression declaration contract mismatch")

FIGHTER_PROGRESSION_DECLARATIONS: tuple[ContentDeclaration, ...] = (
    FIGHTER_CLASS_DECLARATION,
    CHAMPION_SUBCLASS_DECLARATION,
)


__all__ = [
    "CHAMPION_SUBCLASS_DECLARATION",
    "CHAMPION_SUBCLASS_DEFINITION",
    "CHAMPION_SUBCLASS_REF",
    "ChampionProgressionDefinition",
    "FIGHTER_CLASS_DECLARATION",
    "FIGHTER_CLASS_DEFINITION",
    "FIGHTER_CLASS_REF",
    "FIGHTER_PROGRESSION_DECLARATIONS",
    "FighterProgressionDefinition",
]
