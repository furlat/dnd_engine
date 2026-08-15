"""Focused authored-definition coverage for Sorcerer and Draconic Bloodline."""

from dnd.classes import sorcerer
from dnd.classes.sorcerer_progression_definitions import (
    DRACONIC_BLOODLINE_SUBCLASS_DECLARATION,
    DRACONIC_BLOODLINE_SUBCLASS_DEFINITION,
    SORCERER_CLASS_DECLARATION,
    SORCERER_CLASS_DEFINITION,
    SORCERER_PROGRESSION_DECLARATIONS,
    SORCERER_REACTION_ONLY_SPELL_IDENTITY_GAPS,
)
from dnd.classes.permanent_feature_definitions import (
    SORCERER_DRACONIC_RESILIENCE_DECLARATION,
    SORCERER_SORCERY_POINTS_DECLARATION,
)
from dnd.classes.sorcerer_structural_feature_definitions import (
    DISTANT_SPELL_DECLARATION,
    DRACONIC_ANCESTRY_DECLARATIONS,
    DRACONIC_PRESENCE_DECLARATION,
    DRAGON_WINGS_DECLARATION,
    ELEMENTAL_AFFINITY_DECLARATION,
    METAMAGIC_OPTION_DECLARATIONS,
    QUICKENED_SPELL_DECLARATION,
    SORCERER_STRUCTURAL_FEATURE_DEFINITIONS_BY_REF,
    SORCEROUS_RESTORATION_DECLARATION,
    SorcererMetamagicOption,
    SorcererStructuralFeatureKind,
    SorcererStructuralFeatureDefinition,
    TWINNED_SPELL_DECLARATION,
)
from dnd.content_system.action_definitions import (
    ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS,
)
from dnd.content_system.condition_definitions import (
    CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS,
)
from dnd.core.content.dependencies import ContentDependencyPhase
from dnd.core.content.dependencies import ContentDependencyRelation
from dnd.types.abilities import AbilityName
from dnd.core.content.durable_characters import (
    AbilityScorePrerequisite,
    ChoiceRequirementKind,
    ClassDefinition,
    ProficiencySubjectKind,
    RitualPreparationPolicy,
    SpellcastingSourceId,
    SubclassDefinition,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.registration import ContentDeclarationMode
from dnd.types.progression import CasterProgression
from dnd.items.weapons import (
    DAGGER_REF,
    DART_REF,
    LIGHT_CROSSBOW_REF,
    QUARTERSTAFF_REF,
    SLING_REF,
)


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


def _requirement(
    definition: ClassDefinition | SubclassDefinition,
    level: int,
    kind: ChoiceRequirementKind,
):
    return next(
        row
        for row in _level(definition, level).choice_requirements
        if row.choice_kind is kind
    )


def test_sorcerer_and_draconic_bloodline_are_exact_typed_definitions() -> None:
    assert SORCERER_PROGRESSION_DECLARATIONS == (
        SORCERER_CLASS_DECLARATION,
        DRACONIC_BLOODLINE_SUBCLASS_DECLARATION,
    )
    assert (
        SORCERER_CLASS_DECLARATION.mode
        is ContentDeclarationMode.TYPED_DEFINITION
    )
    assert (
        DRACONIC_BLOODLINE_SUBCLASS_DECLARATION.mode
        is ContentDeclarationMode.TYPED_DEFINITION
    )
    assert (
        SORCERER_CLASS_DECLARATION.ref.definition_kind
        is ContentDefinitionKind.CLASS
    )
    assert (
        DRACONIC_BLOODLINE_SUBCLASS_DECLARATION.ref.definition_kind
        is ContentDefinitionKind.SUBCLASS
    )
    assert SORCERER_CLASS_DECLARATION.ref.content_id == "class.sorcerer"
    assert (
        DRACONIC_BLOODLINE_SUBCLASS_DECLARATION.ref.content_id
        == "subclass.sorcerer.draconic_bloodline"
    )
    assert DRACONIC_BLOODLINE_SUBCLASS_DEFINITION.parent_class_ref == (
        SORCERER_CLASS_DECLARATION.ref
    )


def test_sorcerer_entry_modes_spell_source_and_saves_are_exact() -> None:
    definition = SORCERER_CLASS_DEFINITION
    assert definition.hit_die == 6
    assert definition.caster_progression is CasterProgression.FULL_CASTER
    assert definition.spellcasting_feature_class_level == 1
    assert definition.spellcasting_source_id == SpellcastingSourceId(
        value="class.sorcerer.spellcasting",
    )
    assert definition.spellcasting_ability is AbilityName.CHARISMA
    assert definition.ritual_policy is RitualPreparationPolicy.NONE
    assert definition.saving_throw_proficiencies == (
        AbilityName.CHARISMA,
        AbilityName.CONSTITUTION,
    )
    assert isinstance(
        definition.multiclass_prerequisite,
        AbilityScorePrerequisite,
    )
    assert (
        definition.multiclass_prerequisite.ability,
        definition.multiclass_prerequisite.minimum,
    ) == (AbilityName.CHARISMA, 13)

    assert tuple(
        (row.subject_kind, row.subject_id, row.content_ref)
        for row in definition.first_class_proficiencies.automatic
    ) == tuple(
        (ProficiencySubjectKind.WEAPON, None, content_ref)
        for content_ref in (
            DAGGER_REF,
            DART_REF,
            LIGHT_CROSSBOW_REF,
            QUARTERSTAFF_REF,
            SLING_REF,
        )
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
        "skill.arcana",
        "skill.deception",
        "skill.insight",
        "skill.intimidation",
        "skill.persuasion",
        "skill.religion",
    )
    assert definition.multiclass_proficiencies.automatic == ()
    assert definition.multiclass_proficiencies.choices == ()


def test_implemented_metamagic_features_close_their_exact_action_roots() -> None:
    expected = {
        DISTANT_SPELL_DECLARATION.ref.identity_key: (
            ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[sorcerer.DistantSpell].ref
        ),
        QUICKENED_SPELL_DECLARATION.ref.identity_key: (
            ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[sorcerer.QuickenedSpell].ref
        ),
        TWINNED_SPELL_DECLARATION.ref.identity_key: (
            ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[sorcerer.TwinnedSpell].ref
        ),
    }
    declarations_by_ref = {
        declaration.ref.identity_key: declaration
        for declaration in METAMAGIC_OPTION_DECLARATIONS
    }
    for feature_ref, action_ref in expected.items():
        assert len(declarations_by_ref[feature_ref].dependencies) == 1
        dependency = declarations_by_ref[feature_ref].dependencies[0]
        assert dependency.relation is ContentDependencyRelation.GRANTS_ACTION
        assert dependency.target_ref == action_ref
        assert dependency.phase is ContentDependencyPhase.RUNTIME_REFERENCE

    assert all(
        declaration.dependencies == ()
        for declaration in METAMAGIC_OPTION_DECLARATIONS
        if declaration.ref.identity_key not in expected
    )


def test_dragon_wings_closes_toggle_flight_and_active_state() -> None:
    expected = {
        (
            ContentDependencyRelation.GRANTS_ACTION,
            ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[
                sorcerer.DragonWings
            ].ref.identity_key,
        ),
        (
            ContentDependencyRelation.APPLIES_CONDITION,
            CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
                sorcerer.DragonWingsActive
            ].ref.identity_key,
        ),
    }
    assert {
        (dependency.relation, dependency.target_ref.identity_key)
        for dependency in DRAGON_WINGS_DECLARATION.dependencies
    } == expected
    assert all(
        dependency.phase is ContentDependencyPhase.RUNTIME_REFERENCE
        for dependency in DRAGON_WINGS_DECLARATION.dependencies
    )
    toggle = ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[sorcerer.DragonWings]
    assert len(toggle.dependencies) == 1
    assert (
        toggle.dependencies[0].relation,
        toggle.dependencies[0].target_ref,
    ) == (
        ContentDependencyRelation.GRANTS_ACTION,
        ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[sorcerer.Fly].ref,
    )


def test_sorcerer_spell_entitlement_is_exact_installed_srd_intersection() -> None:
    expected_by_rank = {
        0: (
            "spell.acid_splash",
            "spell.chill_touch",
            "spell.fire_bolt",
            "spell.light",
            "spell.poison_spray",
            "spell.ray_of_frost",
            "spell.shocking_grasp",
            "spell.true_strike",
        ),
        1: (
            "spell.burning_hands",
            "spell.charm_person",
            "spell.color_spray",
            "spell.expeditious_retreat",
            "spell.false_life",
            "spell.fog_cloud",
            "spell.jump",
            "spell.mage_armor",
            "spell.magic_missile",
            "spell.shield",
            "spell.sleep",
            "spell.thunderwave",
        ),
        2: (
            "spell.blindness_deafness",
            "spell.blur",
            "spell.darkness",
            "spell.darkvision",
            "spell.enhance_ability",
            "spell.enlarge_reduce",
            "spell.gust_of_wind",
            "spell.hold_person",
            "spell.invisibility",
            "spell.mirror_image",
            "spell.misty_step",
            "spell.scorching_ray",
            "spell.see_invisibility",
            "spell.shatter",
            "spell.web",
        ),
        3: (
            "spell.counterspell",
            "spell.daylight",
            "spell.fear",
            "spell.fireball",
            "spell.haste",
            "spell.hypnotic_pattern",
            "spell.lightning_bolt",
            "spell.protection_from_energy",
            "spell.sleet_storm",
            "spell.slow",
            "spell.stinking_cloud",
        ),
        4: (
            "spell.banishment",
            "spell.blight",
            "spell.dimension_door",
            "spell.greater_invisibility",
            "spell.ice_storm",
            "spell.stoneskin",
        ),
        5: (
            "spell.cloudkill",
            "spell.cone_of_cold",
            "spell.hold_monster",
            "spell.insect_plague",
            "spell.telekinesis",
        ),
        6: (
            "spell.chain_lightning",
            "spell.circle_of_death",
            "spell.disintegrate",
            "spell.eyebite",
            "spell.globe_of_invulnerability",
            "spell.sunbeam",
            "spell.true_seeing",
        ),
        7: (
            "spell.finger_of_death",
            "spell.prismatic_spray",
        ),
        8: (
            "spell.incendiary_cloud",
            "spell.power_word_stun",
            "spell.sunburst",
        ),
        9: ("spell.power_word_kill",),
    }
    actual_by_rank = {
        rank: tuple(sorted(
            row.spell_ref.content_id
            for row in SORCERER_CLASS_DEFINITION.spell_entitlements
            if row.spell_rank == rank
        ))
        for rank in range(10)
    }
    assert actual_by_rank == expected_by_rank
    assert all(
        row.spell_ref.pack_id == "content.srd_5_1_cc"
        for row in SORCERER_CLASS_DEFINITION.spell_entitlements
    )
    assert SORCERER_REACTION_ONLY_SPELL_IDENTITY_GAPS == ()
    assert {
        row.spell_ref.content_id
        for row in SORCERER_CLASS_DEFINITION.spell_entitlements
    }.issuperset({"spell.counterspell", "spell.shield"})


def test_sorcerer_level_rows_match_known_spell_and_cantrip_schedule() -> None:
    assert tuple(
        row.class_level for row in SORCERER_CLASS_DEFINITION.level_definitions
    ) == tuple(range(1, 21))
    cantrip_totals = (4, 4, 4, 5, 5, 5, 5, 5, 5, 6) + (6,) * 10
    spell_totals = (
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        12,
        13,
        13,
        14,
        14,
        15,
        15,
        15,
        15,
    )
    cantrip_delta = 0
    spell_delta = 0
    for level in range(1, 21):
        requirements = _level(
            SORCERER_CLASS_DEFINITION,
            level,
        ).choice_requirements
        for row in requirements:
            if row.choice_kind is ChoiceRequirementKind.CANTRIP:
                cantrip_delta += row.minimum_selections
            elif row.choice_kind is ChoiceRequirementKind.SPELL_KNOWN:
                spell_delta += row.minimum_selections
        assert cantrip_delta == cantrip_totals[level - 1]
        assert spell_delta == spell_totals[level - 1]

        replacements = tuple(
            row
            for row in requirements
            if row.choice_kind is ChoiceRequirementKind.SPELL_REPLACEMENT
        )
        if level == 1:
            assert replacements == ()
        else:
            assert len(replacements) == 1
            assert (
                replacements[0].minimum_selections,
                replacements[0].maximum_selections,
            ) == (0, 1)

    cantrip_refs = _requirement(
        SORCERER_CLASS_DEFINITION,
        1,
        ChoiceRequirementKind.CANTRIP,
    ).allowed_refs
    assert {
        row.spell_ref.content_id
        for row in SORCERER_CLASS_DEFINITION.spell_entitlements
        if row.spell_rank == 0
    } == {ref.content_id for ref in cantrip_refs}
    known_refs = _requirement(
        SORCERER_CLASS_DEFINITION,
        1,
        ChoiceRequirementKind.SPELL_KNOWN,
    ).allowed_refs
    assert all(ref.content_id != "spell.necrotic_bless" for ref in known_refs)
    assert all(
        ref.definition_kind is ContentDefinitionKind.SPELL
        for ref in known_refs
    )


def test_sorcerer_spell_choices_are_bounded_by_resulting_class_level() -> None:
    """Known and replacement choices expose only class-level-legal spells."""

    maximum_rank_by_level = (
        1,
        1,
        2,
        2,
        3,
        3,
        4,
        4,
        5,
        5,
        6,
        6,
        7,
        7,
        8,
        8,
        9,
        9,
        9,
        9,
    )
    entitlement_rank_by_ref = {
        row.spell_ref: row.spell_rank
        for row in SORCERER_CLASS_DEFINITION.spell_entitlements
        if row.spell_rank > 0
    }
    for level, maximum_rank in enumerate(
        maximum_rank_by_level,
        start=1,
    ):
        requirements = _level(
            SORCERER_CLASS_DEFINITION,
            level,
        ).choice_requirements
        expected_refs = tuple(sorted(
            (
                ref
                for ref, rank in entitlement_rank_by_ref.items()
                if rank <= maximum_rank
            ),
            key=lambda ref: ref.identity_key,
        ))
        known = tuple(
            row
            for row in requirements
            if row.choice_kind is ChoiceRequirementKind.SPELL_KNOWN
        )
        for requirement in known:
            assert requirement.allowed_refs == expected_refs
        replacements = tuple(
            row
            for row in requirements
            if row.choice_kind
            is ChoiceRequirementKind.SPELL_REPLACEMENT
        )
        if level == 1:
            assert replacements == ()
        else:
            assert len(replacements) == 1
            assert replacements[0].allowed_refs == expected_refs

    level_one = _requirement(
        SORCERER_CLASS_DEFINITION,
        1,
        ChoiceRequirementKind.SPELL_KNOWN,
    )
    assert {
        entitlement_rank_by_ref[ref] for ref in level_one.allowed_refs
    } == {1}
    level_two_replacement = _requirement(
        SORCERER_CLASS_DEFINITION,
        2,
        ChoiceRequirementKind.SPELL_REPLACEMENT,
    )
    assert {
        entitlement_rank_by_ref[ref]
        for ref in level_two_replacement.allowed_refs
    } == {1}
    assert {
        "spell.banishment",
        "spell.chain_lightning",
        "spell.power_word_kill",
    }.isdisjoint(ref.content_id for ref in level_one.allowed_refs)


def test_sorcerer_feature_resource_metamagic_and_asi_rows_are_exact() -> None:
    sorcery_points_ref = SORCERER_SORCERY_POINTS_DECLARATION.ref
    for level in range(2, 21):
        assert sorcery_points_ref in _level(
            SORCERER_CLASS_DEFINITION,
            level,
        ).automatic_grant_refs
    assert sorcery_points_ref not in _level(
        SORCERER_CLASS_DEFINITION,
        1,
    ).automatic_grant_refs
    assert SORCEROUS_RESTORATION_DECLARATION.ref in _level(
        SORCERER_CLASS_DEFINITION,
        20,
    ).automatic_grant_refs

    subclass = _requirement(
        SORCERER_CLASS_DEFINITION,
        1,
        ChoiceRequirementKind.SUBCLASS,
    )
    assert subclass.allowed_refs == (
        DRACONIC_BLOODLINE_SUBCLASS_DECLARATION.ref,
    )

    expected_metamagic_delta = {3: 2, 10: 1}
    assert tuple(
        declaration.ref.content_id
        for declaration in METAMAGIC_OPTION_DECLARATIONS
    ) == (
        "class_feature.sorcerer.metamagic.careful_spell",
        "class_feature.sorcerer.metamagic.distant_spell",
        "class_feature.sorcerer.metamagic.empowered_spell",
        "class_feature.sorcerer.metamagic.extended_spell",
        "class_feature.sorcerer.metamagic.heightened_spell",
        "class_feature.sorcerer.metamagic.quickened_spell",
        "class_feature.sorcerer.metamagic.subtle_spell",
        "class_feature.sorcerer.metamagic.twinned_spell",
    )
    assert {
        SORCERER_STRUCTURAL_FEATURE_DEFINITIONS_BY_REF[
            declaration.ref
        ].metamagic_option
        for declaration in METAMAGIC_OPTION_DECLARATIONS
    } == set(SorcererMetamagicOption)
    for level, count in expected_metamagic_delta.items():
        row = _requirement(
            SORCERER_CLASS_DEFINITION,
            level,
            ChoiceRequirementKind.METAMAGIC,
        )
        assert (row.minimum_selections, row.maximum_selections) == (
            count,
            count,
        )
        assert row.allowed_refs == tuple(
            sorted(
                (
                    DISTANT_SPELL_DECLARATION.ref,
                    QUICKENED_SPELL_DECLARATION.ref,
                    TWINNED_SPELL_DECLARATION.ref,
                ),
                key=lambda ref: ref.identity_key,
            )
        )
    assert not any(
        requirement.choice_kind is ChoiceRequirementKind.METAMAGIC
        for requirement in _level(
            SORCERER_CLASS_DEFINITION,
            17,
        ).choice_requirements
    )
    assert sum(expected_metamagic_delta.values()) == 3

    for level in (4, 8, 12, 16, 19):
        row = _requirement(
            SORCERER_CLASS_DEFINITION,
            level,
            ChoiceRequirementKind.ABILITY_SCORE_IMPROVEMENT_OR_FEAT,
        )
        assert (row.minimum_selections, row.maximum_selections) == (1, 1)


def test_draconic_bloodline_rows_and_structural_payloads_are_exact() -> None:
    ancestry = _requirement(
        DRACONIC_BLOODLINE_SUBCLASS_DEFINITION,
        1,
        ChoiceRequirementKind.ELEMENTAL_ANCESTRY,
    )
    assert ancestry.allowed_refs == tuple(
        sorted(
            (
                declaration.ref
                for declaration in DRACONIC_ANCESTRY_DECLARATIONS
            ),
            key=lambda ref: ref.identity_key,
        )
    )
    assert len(ancestry.allowed_refs) == 10

    assert _grant_ids(DRACONIC_BLOODLINE_SUBCLASS_DEFINITION, 1) == (
        "class_feature.sorcerer.draconic_resilience",
    )
    assert _grant_ids(DRACONIC_BLOODLINE_SUBCLASS_DEFINITION, 6) == (
        "class_feature.sorcerer.elemental_affinity",
    )
    assert _grant_ids(DRACONIC_BLOODLINE_SUBCLASS_DEFINITION, 14) == (
        "class_feature.sorcerer.dragon_wings",
    )
    assert _grant_ids(DRACONIC_BLOODLINE_SUBCLASS_DEFINITION, 18) == (
        "class_feature.sorcerer.draconic_presence",
    )

    ancestry_payloads = tuple(
        SORCERER_STRUCTURAL_FEATURE_DEFINITIONS_BY_REF[declaration.ref]
        for declaration in DRACONIC_ANCESTRY_DECLARATIONS
    )
    assert all(
        isinstance(payload, SorcererStructuralFeatureDefinition)
        for payload in ancestry_payloads
    )
    assert {
        payload.feature_kind for payload in ancestry_payloads
    } == {SorcererStructuralFeatureKind.DRACONIC_ANCESTRY}
    assert {
        payload.ancestry_damage_type for payload in ancestry_payloads
    } == {"acid", "cold", "fire", "lightning", "poison"}
    assert {
        (
            payload.draconic_ancestry.value,
            payload.ancestry_damage_type,
        )
        for payload in ancestry_payloads
        if payload.draconic_ancestry is not None
    } == {
        ("black", "acid"),
        ("blue", "lightning"),
        ("brass", "fire"),
        ("bronze", "lightning"),
        ("copper", "acid"),
        ("gold", "fire"),
        ("green", "poison"),
        ("red", "fire"),
        ("silver", "cold"),
        ("white", "cold"),
    }
    assert SORCERER_STRUCTURAL_FEATURE_DEFINITIONS_BY_REF[
        DRAGON_WINGS_DECLARATION.ref
    ].feature_kind is SorcererStructuralFeatureKind.DRAGON_WINGS
    assert SORCERER_STRUCTURAL_FEATURE_DEFINITIONS_BY_REF[
        DRACONIC_PRESENCE_DECLARATION.ref
    ].feature_kind is SorcererStructuralFeatureKind.DRACONIC_PRESENCE
    restoration = SORCERER_STRUCTURAL_FEATURE_DEFINITIONS_BY_REF[
        SORCEROUS_RESTORATION_DECLARATION.ref
    ]
    assert (
        restoration.feature_kind
        is SorcererStructuralFeatureKind.SORCEROUS_RESTORATION
    )
    assert restoration.short_rest_sorcery_point_recovery == 4


def test_sorcerer_declarations_close_exact_dependencies() -> None:
    class_dependencies = {
        dependency.target_ref.identity_key: dependency.relation
        for dependency in SORCERER_CLASS_DECLARATION.dependencies
    }
    assert class_dependencies[
        DRACONIC_BLOODLINE_SUBCLASS_DECLARATION.ref.identity_key
    ] is ContentDependencyRelation.OFFERS_SUBCLASS
    for entitlement in SORCERER_CLASS_DEFINITION.spell_entitlements:
        assert class_dependencies[
            entitlement.spell_ref.identity_key
        ] is ContentDependencyRelation.GRANTS_SPELL

    subclass_dependencies = {
        dependency.target_ref.identity_key: dependency.relation
        for dependency in DRACONIC_BLOODLINE_SUBCLASS_DECLARATION.dependencies
    }
    for ref in (
        SORCERER_DRACONIC_RESILIENCE_DECLARATION.ref,
        ELEMENTAL_AFFINITY_DECLARATION.ref,
        DRAGON_WINGS_DECLARATION.ref,
        DRACONIC_PRESENCE_DECLARATION.ref,
        *(row.ref for row in DRACONIC_ANCESTRY_DECLARATIONS),
    ):
        assert subclass_dependencies[
            ref.identity_key
        ] is ContentDependencyRelation.GRANTS_FEATURE
