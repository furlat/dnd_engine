"""Pure authored Sorcerer and Draconic Bloodline progression definitions.

The class table is immutable build data.  It installs no runtime behavior and
never consults spell display names or Python implementation paths.  Its spell
entitlement ledger is the exact intersection of installed SRD spell ContentRefs
and the SRD 5.1 Sorcerer list.
"""

from dnd.classes import feats, sorcerer
from dnd.classes.sorcerer_structural_feature_definitions import (
    DISTANT_SPELL_DECLARATION,
    DRACONIC_ANCESTRY_DECLARATIONS,
    DRACONIC_PRESENCE_DECLARATION,
    DRAGON_WINGS_DECLARATION,
    ELEMENTAL_AFFINITY_DECLARATION,
    QUICKENED_SPELL_DECLARATION,
    SORCERER_STRUCTURAL_FEATURE_DECLARATIONS,
    SORCEROUS_RESTORATION_DECLARATION,
    TWINNED_SPELL_DECLARATION,
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
    BuildChoiceRequirement,
    ChoiceRequirementKind,
    ClassDefinition,
    ClassLevelDefinition,
    ClassProficiencyPackage,
    ClassSpellEntitlement,
    ProficiencySubject,
    ProficiencySubjectKind,
    RitualPreparationPolicy,
    SpellcastingSourceId,
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
from dnd.core.progression import (
    CasterProgression,
    SpellcastingClassContribution,
    maximum_spell_rank_for_contribution,
)
from dnd.spells.catalog_content import SPELL_CONTENT_DECLARATIONS
from dnd.spells.reaction_spell_content import (
    LEARNED_REACTION_SPELL_DECLARATIONS,
)


_PACK_ID = "content.srd_5_1_cc"
_VERSION = 1


def _typed_ref(
    definition_kind: ContentDefinitionKind,
    content_id: str,
    definition_model: type[ClassDefinition] | type[SubclassDefinition],
) -> ContentRef:
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


SORCERER_CLASS_REF = _typed_ref(
    ContentDefinitionKind.CLASS,
    "class.sorcerer",
    ClassDefinition,
)
DRACONIC_BLOODLINE_SUBCLASS_REF = _typed_ref(
    ContentDefinitionKind.SUBCLASS,
    "subclass.sorcerer.draconic_bloodline",
    SubclassDefinition,
)


def _feature_ref(condition_type: type[BaseCondition]) -> ContentRef:
    return CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[condition_type].ref


_SORCERY_POINTS_REF = _feature_ref(sorcerer.SorceryPointsFeature)
_DRACONIC_RESILIENCE_REF = _feature_ref(sorcerer.DraconicResilience)
_ELEMENTAL_AFFINITY_REF = ELEMENTAL_AFFINITY_DECLARATION.ref
_LUCKY_FEAT_REF = _feature_ref(feats.LuckyFeature)


SORCERER_REACTION_ONLY_SPELL_IDENTITY_GAPS: tuple[str, ...] = ()


# Exact authored SRD list intersection.  No display-name normalization or
# catalog class-tag inference participates in this ledger.
_SORCERER_INSTALLED_SPELL_RANKS_BY_CONTENT_ID: dict[str, int] = {
    "spell.acid_splash": 0,
    "spell.chill_touch": 0,
    "spell.fire_bolt": 0,
    "spell.light": 0,
    "spell.poison_spray": 0,
    "spell.ray_of_frost": 0,
    "spell.shocking_grasp": 0,
    "spell.true_strike": 0,
    "spell.burning_hands": 1,
    "spell.charm_person": 1,
    "spell.color_spray": 1,
    "spell.expeditious_retreat": 1,
    "spell.false_life": 1,
    "spell.fog_cloud": 1,
    "spell.jump": 1,
    "spell.mage_armor": 1,
    "spell.magic_missile": 1,
    "spell.shield": 1,
    "spell.sleep": 1,
    "spell.thunderwave": 1,
    "spell.blindness_deafness": 2,
    "spell.blur": 2,
    "spell.darkness": 2,
    "spell.darkvision": 2,
    "spell.enhance_ability": 2,
    "spell.enlarge_reduce": 2,
    "spell.gust_of_wind": 2,
    "spell.hold_person": 2,
    "spell.invisibility": 2,
    "spell.mirror_image": 2,
    "spell.misty_step": 2,
    "spell.scorching_ray": 2,
    "spell.see_invisibility": 2,
    "spell.shatter": 2,
    "spell.web": 2,
    "spell.daylight": 3,
    "spell.counterspell": 3,
    "spell.fear": 3,
    "spell.fireball": 3,
    "spell.haste": 3,
    "spell.hypnotic_pattern": 3,
    "spell.lightning_bolt": 3,
    "spell.protection_from_energy": 3,
    "spell.sleet_storm": 3,
    "spell.slow": 3,
    "spell.stinking_cloud": 3,
    "spell.banishment": 4,
    "spell.blight": 4,
    "spell.dimension_door": 4,
    "spell.greater_invisibility": 4,
    "spell.ice_storm": 4,
    "spell.stoneskin": 4,
    "spell.cloudkill": 5,
    "spell.cone_of_cold": 5,
    "spell.hold_monster": 5,
    "spell.insect_plague": 5,
    "spell.telekinesis": 5,
    "spell.chain_lightning": 6,
    "spell.circle_of_death": 6,
    "spell.disintegrate": 6,
    "spell.eyebite": 6,
    "spell.globe_of_invulnerability": 6,
    "spell.sunbeam": 6,
    "spell.true_seeing": 6,
    "spell.finger_of_death": 7,
    "spell.prismatic_spray": 7,
    "spell.incendiary_cloud": 8,
    "spell.power_word_stun": 8,
    "spell.sunburst": 8,
    "spell.power_word_kill": 9,
}

_INSTALLED_SPELL_DECLARATIONS_BY_CONTENT_ID = {
    declaration.ref.content_id: declaration
    for declaration in (
        *SPELL_CONTENT_DECLARATIONS,
        *LEARNED_REACTION_SPELL_DECLARATIONS,
    )
}
_missing_entitlements = (
    _SORCERER_INSTALLED_SPELL_RANKS_BY_CONTENT_ID.keys()
    - _INSTALLED_SPELL_DECLARATIONS_BY_CONTENT_ID.keys()
)
if _missing_entitlements:
    raise RuntimeError(
        "Sorcerer entitlement ledger names uninstalled exact spell refs: "
        f"{sorted(_missing_entitlements)!r}",
    )

_SORCERER_SPELL_ENTITLEMENTS = tuple(
    sorted(
        (
            ClassSpellEntitlement(
                spell_ref=(
                    _INSTALLED_SPELL_DECLARATIONS_BY_CONTENT_ID[
                        content_id
                    ].ref
                ),
                spell_rank=rank,
            )
            for content_id, rank in (
                _SORCERER_INSTALLED_SPELL_RANKS_BY_CONTENT_ID.items()
            )
        ),
        key=lambda row: row.spell_ref.identity_key,
    )
)
_SORCERER_CANTRIP_REFS = tuple(
    row.spell_ref
    for row in _SORCERER_SPELL_ENTITLEMENTS
    if row.spell_rank == 0
)
_METAMAGIC_REFS = tuple(
    sorted(
        (
            DISTANT_SPELL_DECLARATION.ref,
            QUICKENED_SPELL_DECLARATION.ref,
            TWINNED_SPELL_DECLARATION.ref,
        ),
        key=lambda ref: ref.identity_key,
    )
)
_DRACONIC_ANCESTRY_REFS = tuple(
    declaration.ref for declaration in DRACONIC_ANCESTRY_DECLARATIONS
)


def _subject(
    kind: ProficiencySubjectKind,
    subject_id: str,
) -> ProficiencySubject:
    return ProficiencySubject(subject_kind=kind, subject_id=subject_id)


def _weapon_subject(item_id: str) -> ProficiencySubject:
    return ProficiencySubject(
        subject_kind=ProficiencySubjectKind.WEAPON,
        subject_id=item_id,
    )


_SORCERER_SKILL_SUBJECTS = tuple(
    _subject(ProficiencySubjectKind.SKILL, f"skill.{skill}")
    for skill in (
        "arcana",
        "deception",
        "insight",
        "intimidation",
        "persuasion",
        "religion",
    )
)
_SORCERER_FIRST_PROFICIENCIES = ClassProficiencyPackage(
    automatic=tuple(
        _weapon_subject(item_id)
        for item_id in (
            "weapon.dagger",
            "weapon.dart",
            "weapon.light_crossbow",
            "weapon.quarterstaff",
            "weapon.sling",
        )
    ),
    choices=(
        BuildChoiceRequirement(
            choice_id="class.sorcerer.first_class.starting_equipment",
            choice_kind=ChoiceRequirementKind.STARTING_EQUIPMENT_PACKAGE,
            minimum_selections=1,
            maximum_selections=1,
            allowed_refs=STARTING_EQUIPMENT_PACKAGE_REFS_BY_CLASS[
                "sorcerer"
            ],
        ),
        BuildChoiceRequirement(
            choice_id="class.sorcerer.proficiencies.skills",
            choice_kind=ChoiceRequirementKind.CLASS_SKILL,
            minimum_selections=2,
            maximum_selections=2,
            allowed_proficiency_subjects=_SORCERER_SKILL_SUBJECTS,
        ),
    ),
)


def _choice(
    *,
    choice_id: str,
    choice_kind: ChoiceRequirementKind,
    allowed_refs: tuple[ContentRef, ...],
    count: int = 1,
    minimum_selections: int | None = None,
) -> BuildChoiceRequirement:
    return BuildChoiceRequirement(
        choice_id=choice_id,
        choice_kind=choice_kind,
        minimum_selections=(
            count if minimum_selections is None else minimum_selections
        ),
        maximum_selections=count,
        allowed_refs=allowed_refs,
    )


def _asi_or_feat(level: int) -> BuildChoiceRequirement:
    return _choice(
        choice_id=f"class.sorcerer.level_{level}.asi_or_feat",
        choice_kind=ChoiceRequirementKind.ABILITY_SCORE_IMPROVEMENT_OR_FEAT,
        allowed_refs=(_LUCKY_FEAT_REF,),
    )


_CANTRIP_LEARN_COUNTS = {1: 4, 4: 1, 10: 1}
_SPELL_LEARN_COUNTS = {
    1: 2,
    2: 1,
    3: 1,
    4: 1,
    5: 1,
    6: 1,
    7: 1,
    8: 1,
    9: 1,
    10: 1,
    11: 1,
    13: 1,
    15: 1,
    17: 1,
}
_METAMAGIC_LEARN_COUNTS = {3: 2, 10: 1}
_ASI_LEVELS = frozenset({4, 8, 12, 16, 19})


def _ranked_spell_refs_for_sorcerer_level(
    level: int,
) -> tuple[ContentRef, ...]:
    """Return exact Sorcerer spells legal at the resulting class level."""

    maximum_rank = maximum_spell_rank_for_contribution(
        SpellcastingClassContribution(
            class_level=level,
            progression=CasterProgression.FULL_CASTER,
            spellcasting_feature_class_level=1,
        ),
    )
    return tuple(
        entitlement.spell_ref
        for entitlement in _SORCERER_SPELL_ENTITLEMENTS
        if 0 < entitlement.spell_rank <= maximum_rank
    )


def _sorcerer_level_choices(
    level: int,
) -> tuple[BuildChoiceRequirement, ...]:
    rows: list[BuildChoiceRequirement] = []
    if level == 1:
        rows.append(_choice(
            choice_id="class.sorcerer.level_1.subclass",
            choice_kind=ChoiceRequirementKind.SUBCLASS,
            allowed_refs=(DRACONIC_BLOODLINE_SUBCLASS_REF,),
        ))
    cantrip_count = _CANTRIP_LEARN_COUNTS.get(level)
    if cantrip_count is not None:
        rows.append(_choice(
            choice_id=f"class.sorcerer.level_{level}.cantrips",
            choice_kind=ChoiceRequirementKind.CANTRIP,
            allowed_refs=_SORCERER_CANTRIP_REFS,
            count=cantrip_count,
        ))
    spell_count = _SPELL_LEARN_COUNTS.get(level)
    if spell_count is not None:
        rows.append(_choice(
            choice_id=f"class.sorcerer.level_{level}.spell_known",
            choice_kind=ChoiceRequirementKind.SPELL_KNOWN,
            allowed_refs=_ranked_spell_refs_for_sorcerer_level(level),
            count=spell_count,
        ))
    if level > 1:
        rows.append(_choice(
            choice_id=f"class.sorcerer.level_{level}.spell_replacement",
            choice_kind=ChoiceRequirementKind.SPELL_REPLACEMENT,
            allowed_refs=_ranked_spell_refs_for_sorcerer_level(level),
            count=1,
            minimum_selections=0,
        ))
    metamagic_count = _METAMAGIC_LEARN_COUNTS.get(level)
    if metamagic_count is not None:
        rows.append(_choice(
            choice_id=f"class.sorcerer.level_{level}.metamagic",
            choice_kind=ChoiceRequirementKind.METAMAGIC,
            allowed_refs=_METAMAGIC_REFS,
            count=metamagic_count,
        ))
    if level in _ASI_LEVELS:
        rows.append(_asi_or_feat(level))
    return tuple(sorted(rows, key=lambda row: row.choice_id))


def _sorcerer_level_grants(level: int) -> tuple[ContentRef, ...]:
    refs: list[ContentRef] = []
    if level >= 2:
        refs.append(_SORCERY_POINTS_REF)
    if level == 20:
        refs.append(SORCEROUS_RESTORATION_DECLARATION.ref)
    return tuple(sorted(refs, key=lambda ref: ref.identity_key))


SORCERER_CLASS_DEFINITION = ClassDefinition(
    hit_die=6,
    caster_progression=CasterProgression.FULL_CASTER,
    spellcasting_feature_class_level=1,
    spellcasting_source_id=SpellcastingSourceId(
        value="class.sorcerer.spellcasting",
    ),
    spellcasting_ability=AbilityScoreName.CHARISMA,
    ritual_policy=RitualPreparationPolicy.NONE,
    spell_entitlements=_SORCERER_SPELL_ENTITLEMENTS,
    multiclass_prerequisite=AbilityScorePrerequisite(
        ability=AbilityScoreName.CHARISMA,
        minimum=13,
    ),
    first_class_proficiencies=_SORCERER_FIRST_PROFICIENCIES,
    multiclass_proficiencies=ClassProficiencyPackage(),
    saving_throw_proficiencies=(
        AbilityScoreName.CHARISMA,
        AbilityScoreName.CONSTITUTION,
    ),
    level_definitions=tuple(
        ClassLevelDefinition(
            class_level=level,
            automatic_grant_refs=_sorcerer_level_grants(level),
            choice_requirements=_sorcerer_level_choices(level),
        )
        for level in range(1, 21)
    ),
)


DRACONIC_BLOODLINE_SUBCLASS_DEFINITION = SubclassDefinition(
    parent_class_ref=SORCERER_CLASS_REF,
    level_definitions=tuple(
        ClassLevelDefinition(
            class_level=level,
            automatic_grant_refs={
                1: (_DRACONIC_RESILIENCE_REF,),
                6: (_ELEMENTAL_AFFINITY_REF,),
                14: (DRAGON_WINGS_DECLARATION.ref,),
                18: (DRACONIC_PRESENCE_DECLARATION.ref,),
            }.get(level, ()),
            choice_requirements=(
                (
                    _choice(
                        choice_id=(
                            "subclass.sorcerer.draconic_bloodline."
                            "level_1.ancestry"
                        ),
                        choice_kind=ChoiceRequirementKind.ELEMENTAL_ANCESTRY,
                        allowed_refs=_DRACONIC_ANCESTRY_REFS,
                    ),
                )
                if level == 1
                else ()
            ),
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


def _dependencies(
    refs: tuple[ContentRef, ...],
    *,
    relation: ContentDependencyRelation,
    notes: str,
) -> tuple[ContentDependency, ...]:
    unique = {ref.identity_key: ref for ref in refs}
    return tuple(
        ContentDependency(
            relation=relation,
            target_ref=ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes=notes,
        )
        for _, ref in sorted(unique.items())
    )


_SORCERER_FEATURE_DEPENDENCIES = _dependencies(
    (
        _SORCERY_POINTS_REF,
        SORCEROUS_RESTORATION_DECLARATION.ref,
        _LUCKY_FEAT_REF,
        *_METAMAGIC_REFS,
    ),
    relation=ContentDependencyRelation.GRANTS_FEATURE,
    notes="Offered or granted by the Sorcerer progression.",
)
_SORCERER_SPELL_DEPENDENCIES = _dependencies(
    tuple(
        entitlement.spell_ref
        for entitlement in _SORCERER_SPELL_ENTITLEMENTS
    ),
    relation=ContentDependencyRelation.GRANTS_SPELL,
    notes="Exact installed SRD Sorcerer spell-list entitlement.",
)
_DRACONIC_FEATURE_DEPENDENCIES = _dependencies(
    (
        _DRACONIC_RESILIENCE_REF,
        _ELEMENTAL_AFFINITY_REF,
        DRAGON_WINGS_DECLARATION.ref,
        DRACONIC_PRESENCE_DECLARATION.ref,
        *_DRACONIC_ANCESTRY_REFS,
    ),
    relation=ContentDependencyRelation.GRANTS_FEATURE,
    notes="Offered or granted by the Draconic Bloodline progression.",
)


@typed_definition(
    definition_kind=ContentDefinitionKind.CLASS,
    pack_id=_PACK_ID,
    content_id="class.sorcerer",
    version=_VERSION,
    descriptor=ContentDescriptorSpec(
        display_name="Sorcerer",
        description=(
            "A Charisma-based full caster who shapes innate magic through "
            "Sorcery Points, Flexible Casting, and selected Metamagic."
        ),
        tags=("arcane", "class", "full_caster", "player_capable", "sorcerer"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="condition.dnd-classes-sorcerer-sorcerypointsfeature",
            visual_variant_key="class.sorcerer",
            ui_group="classes",
        ),
        ordering=ContentOrdering(sort_group="classes", sort_order=30),
        related_content_refs=(DRACONIC_BLOODLINE_SUBCLASS_REF,),
    ),
    provenance=_provenance(
        "SRD 5.1 Sorcerer class progression and spell list, levels 1–20",
    ),
    definition=SORCERER_CLASS_DEFINITION,
    dependencies=(
        *_SORCERER_FEATURE_DEPENDENCIES,
        *_SORCERER_SPELL_DEPENDENCIES,
        *(
            ContentDependency(
                relation=(
                    ContentDependencyRelation.OFFERS_STARTING_EQUIPMENT
                ),
                target_ref=ref,
                phase=ContentDependencyPhase.RUNTIME_REFERENCE,
                notes="Exact Sorcerer starting package offered at level one.",
            )
            for ref in STARTING_EQUIPMENT_PACKAGE_REFS_BY_CLASS["sorcerer"]
        ),
        ContentDependency(
            relation=ContentDependencyRelation.OFFERS_SUBCLASS,
            target_ref=DRACONIC_BLOODLINE_SUBCLASS_REF,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Draconic Bloodline is the SRD Sorcerer origin.",
        ),
    ),
)
class SorcererProgressionDefinition:
    """Marker for the immutable Sorcerer progression declaration."""


@typed_definition(
    definition_kind=ContentDefinitionKind.SUBCLASS,
    pack_id=_PACK_ID,
    content_id="subclass.sorcerer.draconic_bloodline",
    version=_VERSION,
    descriptor=ContentDescriptorSpec(
        display_name="Draconic Bloodline",
        description=(
            "A Sorcerous Origin with an exact dragon ancestry, resilient "
            "scales, elemental affinity, wings, and a draconic presence."
        ),
        tags=("arcane", "draconic_bloodline", "sorcerer", "subclass"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="condition.dnd-classes-sorcerer-draconicresilience",
            visual_variant_key="subclass.sorcerer.draconic_bloodline",
            ui_group="subclasses.sorcerer",
        ),
        ordering=ContentOrdering(
            sort_group="subclasses.sorcerer",
            sort_order=10,
        ),
        related_content_refs=(SORCERER_CLASS_REF,),
    ),
    provenance=_provenance(
        "SRD 5.1 Sorcerer: Draconic Bloodline, levels 1–18",
    ),
    definition=DRACONIC_BLOODLINE_SUBCLASS_DEFINITION,
    dependencies=_DRACONIC_FEATURE_DEPENDENCIES,
)
class DraconicBloodlineProgressionDefinition:
    """Marker for the immutable Draconic Bloodline declaration."""


SORCERER_CLASS_DECLARATION: ContentDeclaration = get_content_declaration(
    SorcererProgressionDefinition,
)
DRACONIC_BLOODLINE_SUBCLASS_DECLARATION: ContentDeclaration = (
    get_content_declaration(DraconicBloodlineProgressionDefinition)
)
if (
    SORCERER_CLASS_DECLARATION.ref != SORCERER_CLASS_REF
    or DRACONIC_BLOODLINE_SUBCLASS_DECLARATION.ref
    != DRACONIC_BLOODLINE_SUBCLASS_REF
):
    raise RuntimeError("Sorcerer progression declaration contract mismatch")

SORCERER_PROGRESSION_DECLARATIONS: tuple[ContentDeclaration, ...] = (
    SORCERER_CLASS_DECLARATION,
    DRACONIC_BLOODLINE_SUBCLASS_DECLARATION,
)


__all__ = [
    "DRACONIC_BLOODLINE_SUBCLASS_DECLARATION",
    "DRACONIC_BLOODLINE_SUBCLASS_DEFINITION",
    "DRACONIC_BLOODLINE_SUBCLASS_REF",
    "DraconicBloodlineProgressionDefinition",
    "SORCERER_CLASS_DECLARATION",
    "SORCERER_CLASS_DEFINITION",
    "SORCERER_CLASS_REF",
    "SORCERER_PROGRESSION_DECLARATIONS",
    "SORCERER_REACTION_ONLY_SPELL_IDENTITY_GAPS",
    "SORCERER_STRUCTURAL_FEATURE_DECLARATIONS",
    "SorcererProgressionDefinition",
]
