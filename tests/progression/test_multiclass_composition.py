"""Cross-class release gate for the three implemented character classes."""

from __future__ import annotations

from collections.abc import Iterator
from itertools import permutations
from typing import Literal
from uuid import UUID, uuid4

import pytest

from dnd.actions.standard import (
    SpellAction,
)
from dnd.classes.barbarian_progression_definitions import BARBARIAN_CLASS_REF
from dnd.classes.progression_definitions import FIGHTER_CLASS_REF
from dnd.classes.sorcerer_progression_definitions import SORCERER_CLASS_REF
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    BUILTIN_PREMADE_BUILDS,
    BuiltinMulticlassBuild,
    BuiltinSingleClassBuild,
    compose_builtin_character_revisions,
)
from dnd.content_system.character_build_validation import (
    CharacterBuildValidator,
    CharacterGrantSourceKind,
)
from dnd.content_system.character_appearance import (
    BARBARIAN_HUMAN_APPEARANCE,
    FIGHTER_HUMAN_APPEARANCE,
    SORCERER_HUMAN_APPEARANCE,
)
from dnd.content_system.character_materialization import (
    MaterializedCharacter,
    apply_character_composition,
    materialize_character,
    remove_character_composition,
)
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.core.content.durable_characters import (
    AbilityScoreAllocation,
    CantripChoice,
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
    ClassLevelEntry,
    ClassSkillChoice,
    ElementalAncestryChoice,
    FlexibleAbilityBonusSelection,
    MetamagicChoice,
    SpellKnownChoice,
    StartingEquipmentPackageChoice,
    SubclassChoice,
)
from dnd.types.abilities import AbilityName
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.materialization import CreatureDeploymentRole
from dnd.types.equipment import ArmorType, WeaponProperty, WeaponSlot
from dnd.types.progression import MulticlassSlotRoundingPolicy
from dnd.core.progression import character_ruleset_digest, proficiency_bonus_for_level
from dnd.runtime_reset import reset_engine_runtime


ClassId = Literal["barbarian", "fighter", "sorcerer"]

_CLASS_IDS: tuple[ClassId, ...] = ("barbarian", "fighter", "sorcerer")
_CLASS_REFS: dict[ClassId, ContentRef] = {
    "barbarian": BARBARIAN_CLASS_REF,
    "fighter": FIGHTER_CLASS_REF,
    "sorcerer": SORCERER_CLASS_REF,
}
_HIT_DICE: dict[ClassId, int] = {
    "barbarian": 12,
    "fighter": 10,
    "sorcerer": 6,
}
_EQUIPMENT_PRESETS: dict[ClassId, str] = {
    "barbarian": "greataxe",
    "fighter": "sword_shield",
    "sorcerer": "dagger",
}
_STRICT_RULESET_DIGEST = character_ruleset_digest(
    permissive_multiclass_prerequisites=False,
    multiclass_slot_rounding_policy=(
        MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
    ),
)
_BASE_ABILITIES = AbilityScoreAllocation(
    strength=15,
    dexterity=13,
    constitution=13,
    intelligence=8,
    wisdom=9,
    charisma=14,
)
_FLEXIBLE_BONUSES = FlexibleAbilityBonusSelection(
    plus_two=AbilityName.STRENGTH,
    plus_one=AbilityName.CHARISMA,
)
_ASI_BY_CLASS: dict[
    ClassId,
    tuple[tuple[int, tuple[tuple[AbilityName, int], ...]], ...],
] = {
    "fighter": (
        (4, ((AbilityName.STRENGTH, 2),)),
        (
            6,
            (
                (AbilityName.STRENGTH, 1),
                (AbilityName.CONSTITUTION, 1),
            ),
        ),
        (8, ((AbilityName.CONSTITUTION, 2),)),
        (12, ((AbilityName.CONSTITUTION, 2),)),
        (
            14,
            (
                (AbilityName.CONSTITUTION, 1),
                (AbilityName.WISDOM, 1),
            ),
        ),
        (16, ((AbilityName.WISDOM, 2),)),
        (19, ((AbilityName.DEXTERITY, 2),)),
    ),
    "barbarian": (
        (4, ((AbilityName.STRENGTH, 2),)),
        (
            8,
            (
                (AbilityName.STRENGTH, 1),
                (AbilityName.CONSTITUTION, 1),
            ),
        ),
        (12, ((AbilityName.CONSTITUTION, 2),)),
        (16, ((AbilityName.CONSTITUTION, 2),)),
        (19, ((AbilityName.WISDOM, 2),)),
    ),
    "sorcerer": (
        (4, ((AbilityName.CHARISMA, 2),)),
        (
            8,
            (
                (AbilityName.CHARISMA, 1),
                (AbilityName.CONSTITUTION, 1),
            ),
        ),
        (12, ((AbilityName.CONSTITUTION, 2),)),
        (16, ((AbilityName.CONSTITUTION, 2),)),
        (
            19,
            (
                (AbilityName.CONSTITUTION, 1),
                (AbilityName.WISDOM, 1),
            ),
        ),
    ),
}
_SAVES_BY_FIRST_CLASS: dict[ClassId, frozenset[str]] = {
    "barbarian": frozenset({"constitution", "strength"}),
    "fighter": frozenset({"constitution", "strength"}),
    "sorcerer": frozenset({"charisma", "constitution"}),
}


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(12, 12))
    yield
    reset_engine_runtime()


@pytest.fixture(scope="module")
def runtime() -> ContentSystemRuntime:
    installed = ContentSystemRuntime()
    installed.install(bootstrap_content_system())
    return installed


def _single_class_build(class_id: ClassId, level: int) -> BuiltinSingleClassBuild:
    appearances = {
        "barbarian": BARBARIAN_HUMAN_APPEARANCE,
        "fighter": FIGHTER_HUMAN_APPEARANCE,
        "sorcerer": SORCERER_HUMAN_APPEARANCE,
    }
    return BuiltinSingleClassBuild(
        class_id=class_id,
        level=level,
        equipment_preset=_EQUIPMENT_PRESETS[class_id],
        appearance=appearances[class_id],
        asi_by_level=_ASI_BY_CLASS[class_id],
    )


def _authored_levels(
    runtime: ContentSystemRuntime,
    class_id: ClassId,
    level: int,
) -> tuple[ClassLevelEntry, ...]:
    return compose_builtin_character_revisions(
        character_id=uuid4(),
        build=_single_class_build(class_id, level),
        content_system=runtime.require(),
    ).definition.class_levels


def _ordered_class_levels(
    runtime: ContentSystemRuntime,
    distribution: tuple[tuple[ClassId, int], ...],
) -> tuple[ClassLevelEntry, ...]:
    levels: list[ClassLevelEntry] = []
    character_level = 0
    for class_index, (class_id, class_level) in enumerate(distribution):
        for entry in _authored_levels(runtime, class_id, class_level):
            character_level += 1
            choices = entry.choices
            if class_index > 0 and entry.resulting_class_level == 1:
                choices = tuple(
                    choice
                    for choice in choices
                    if not isinstance(
                        choice,
                        (
                            ClassSkillChoice,
                            StartingEquipmentPackageChoice,
                        ),
                    )
                )
            levels.append(entry.model_copy(update={
                "character_level": character_level,
                "choices": choices,
            }))
    return tuple(levels)


def _revisions(
    runtime: ContentSystemRuntime,
    distribution: tuple[tuple[ClassId, int], ...],
    *,
    character_id: UUID | None = None,
    definition_revision: int = 1,
) -> tuple[
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
]:
    resolved_character_id = character_id or uuid4()
    loaded = runtime.require()
    seed = compose_builtin_character_revisions(
        character_id=resolved_character_id,
        build=_single_class_build(distribution[0][0], distribution[0][1]),
        content_system=loaded,
    )
    levels = _ordered_class_levels(runtime, distribution)
    definition = CharacterDefinitionRevisionV2.create(
        character_id=resolved_character_id,
        definition_revision=definition_revision,
        body_recipe=seed.definition.body_recipe,
        species_ref=seed.definition.species_ref,
        species_variant_ref=seed.definition.species_variant_ref,
        background_ref=seed.definition.background_ref,
        immutable_origin_choices=(
            seed.definition.immutable_origin_choices
        ),
        appearance=seed.definition.appearance,
        base_ability_scores=_BASE_ABILITIES,
        flexible_ability_bonuses=_FLEXIBLE_BONUSES,
        class_levels=levels,
        earned_character_level=len(levels),
        content_set_digest=loaded.content_set_digest,
        ruleset_digest=_STRICT_RULESET_DIGEST,
    )
    return (
        definition,
        CharacterHoldingsRevision.create(
            character_id=resolved_character_id,
            holdings_revision=1,
        ),
        CharacterLoadoutRevisionV1.create(
            character_id=resolved_character_id,
            loadout_revision=1,
            based_on_definition_revision=definition_revision,
        ),
    )


def _materialize(
    runtime: ContentSystemRuntime,
    distribution: tuple[tuple[ClassId, int], ...],
) -> MaterializedCharacter:
    definition, holdings, loadout = _revisions(runtime, distribution)
    validation = CharacterBuildValidator(
        runtime.require(),
        expected_ruleset_digest=_STRICT_RULESET_DIGEST,
        permissive_multiclass_prerequisites=False,
    ).validate(definition, loadout)
    assert validation.valid, validation.issues
    assert validation.preview is not None
    return materialize_character(
        definition=definition,
        holdings=holdings,
        loadout=loadout,
        runtime_entity_uuid=uuid4(),
        display_name="Cross Class Gate",
        faction="heroes",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id="test.progression.multiclass_composition",
        ),
        expected_ruleset_digest=_STRICT_RULESET_DIGEST,
        permissive_multiclass_prerequisites=False,
        runtime=runtime,
    )


def _assert_composition_removed(
    result: MaterializedCharacter,
    *,
    expected_noncomposition_scores: dict[AbilityName, int] | None = None,
) -> None:
    receipt = result.composition_receipt
    assert receipt is not None
    entity = result.entity
    runtime_uuid = entity.uuid

    remove_character_composition(entity, receipt)

    assert entity.uuid == runtime_uuid
    expected_scores = expected_noncomposition_scores or {}
    assert {
        ability: (
            entity.ability_scores.get_ability(ability.value).ability_score.score
        )
        for ability in AbilityName
    } == {
        ability: expected_scores.get(ability, 0)
        for ability in AbilityName
    }
    assert entity.proficiency_bonus.normalized_score == 0
    assert entity.health.total_hit_dices_number == 0
    assert entity.health.max_hit_points_bonus.normalized_score == 0
    assert entity.spellcasting.sources == {}
    assert entity.action_economy.get_normal_spell_slot_capacity_source() is None
    assert entity.action_economy.get_attack_multiplicity_grants() == ()
    assert entity.equipment.armor_class_formula_candidates == {}
    assert all(
        not sources.sources
        for sources in entity.creature_proficiencies.weapon_sources.values()
    )
    assert all(
        not sources.sources
        for sources in entity.creature_proficiencies.armor_sources.values()
    )
    assert entity.creature_proficiencies.shield_sources.sources == {}
    assert entity.creature_proficiencies.specific_weapon_sources == {}
    assert all(
        not entity.saving_throws.get_saving_throw(ability.value)
        .proficiency_sources.sources
        for ability in AbilityName
    )


@pytest.mark.parametrize("class_id", _CLASS_IDS)
@pytest.mark.parametrize("level", range(1, 21))
def test_existing_class_validates_materializes_and_reverses_at_every_level(
    runtime: ContentSystemRuntime,
    class_id: ClassId,
    level: int,
) -> None:
    result = _materialize(runtime, ((class_id, level),))
    entity = result.entity

    assert entity.health.total_hit_dices_number == level
    assert entity.proficiency_bonus.normalized_score == (
        proficiency_bonus_for_level(level)
    )
    assert {
        hit_die.hit_dice_value.normalized_score
        for hit_die in entity.health.hit_dices
    } == {_HIT_DICE[class_id]}

    _assert_composition_removed(result)


@pytest.mark.parametrize(
    ("first_class", "second_class"),
    tuple(permutations(_CLASS_IDS, 2)),
)
def test_all_ordered_pairs_preserve_first_class_saves_and_entry_proficiencies(
    runtime: ContentSystemRuntime,
    first_class: ClassId,
    second_class: ClassId,
) -> None:
    result = _materialize(
        runtime,
        ((first_class, 1), (second_class, 1)),
    )
    entity = result.entity
    proficient_saves = frozenset(
        ability.value
        for ability in AbilityName
        if entity.saving_throws.get_saving_throw(
            ability.value,
        ).proficiency_sources.sources
    )

    assert proficient_saves == _SAVES_BY_FIRST_CLASS[first_class]
    assert entity.proficiency_bonus.normalized_score == 2
    assert [
        hit_die.hit_dice_value.normalized_score
        for hit_die in entity.health.hit_dices
    ] == [_HIT_DICE[first_class], _HIT_DICE[second_class]]
    assert entity.health.hit_dices_total_hit_points == (
        _HIT_DICE[first_class] + (_HIT_DICE[second_class] // 2) + 1
    )
    assert entity.creature_proficiencies.is_armor_proficient(
        ArmorType.HEAVY,
    ) is (first_class == "fighter")
    if "fighter" in (first_class, second_class):
        assert entity.creature_proficiencies.is_weapon_proficient(
            (WeaponProperty.MARTIAL,),
        )

    _assert_composition_removed(result)


@pytest.mark.parametrize(
    ("first_class", "second_class"),
    tuple(permutations(_CLASS_IDS, 2)),
)
def test_multiclass_entry_never_requests_or_grants_starting_equipment(
    runtime: ContentSystemRuntime,
    first_class: ClassId,
    second_class: ClassId,
) -> None:
    definition, holdings, loadout = _revisions(
        runtime,
        ((first_class, 1), (second_class, 1)),
    )
    package_choices = tuple(
        (level, choice)
        for level in definition.class_levels
        for choice in level.choices
        if isinstance(choice, StartingEquipmentPackageChoice)
    )

    assert len(package_choices) == 1
    package_level, _ = package_choices[0]
    assert package_level.character_level == 1
    assert package_level.class_ref == _CLASS_REFS[first_class]
    assert not any(
        isinstance(choice, StartingEquipmentPackageChoice)
        for choice in definition.class_levels[1].choices
    )

    validation = CharacterBuildValidator(
        runtime.require(),
        expected_ruleset_digest=_STRICT_RULESET_DIGEST,
        permissive_multiclass_prerequisites=False,
    ).validate(definition, loadout)
    assert validation.valid, validation.issues
    assert validation.preview is not None
    package_grants = tuple(
        row
        for row in validation.preview.grant_schedule
        if (
            row.content_ref is not None
            and row.content_ref.definition_kind
            is ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE
        )
    )
    assert len(package_grants) == 1
    assert (
        package_grants[0].provenance.source_kind
        is CharacterGrantSourceKind.FIRST_CLASS_PACKAGE
    )
    assert package_grants[0].provenance.source_ref == _CLASS_REFS[first_class]
    assert holdings.items == ()


def test_fighter_two_sorcerer_three_premade_uses_canonical_composition(
    runtime: ContentSystemRuntime,
) -> None:
    build = BUILTIN_PREMADE_BUILDS[
        "hero.fighter_2_sorcerer_3_spellblade"
    ]
    assert isinstance(build, BuiltinMulticlassBuild)
    assert tuple(
        (row.class_id, row.level)
        for row in build.class_builds
    ) == (("fighter", 2), ("sorcerer", 3))

    revisions = compose_builtin_character_revisions(
        character_id=uuid4(),
        build=build,
        content_system=runtime.require(),
        ruleset_digest=_STRICT_RULESET_DIGEST,
    )
    definition = revisions.definition
    assert tuple(
        (
            row.character_level,
            row.class_ref,
            row.resulting_class_level,
        )
        for row in definition.class_levels
    ) == (
        (1, FIGHTER_CLASS_REF, 1),
        (2, FIGHTER_CLASS_REF, 2),
        (3, SORCERER_CLASS_REF, 1),
        (4, SORCERER_CLASS_REF, 2),
        (5, SORCERER_CLASS_REF, 3),
    )
    package_choices = tuple(
        (level, choice)
        for level in definition.class_levels
        for choice in level.choices
        if isinstance(choice, StartingEquipmentPackageChoice)
    )
    assert len(package_choices) == 1
    assert package_choices[0][0].class_ref == FIGHTER_CLASS_REF
    assert package_choices[0][0].character_level == 1
    assert not any(
        isinstance(choice, ClassSkillChoice)
        for choice in definition.class_levels[2].choices
    )
    assert any(
        isinstance(choice, SubclassChoice)
        for choice in definition.class_levels[2].choices
    )
    assert any(
        isinstance(choice, ElementalAncestryChoice)
        for choice in definition.class_levels[2].choices
    )
    assert any(
        isinstance(choice, CantripChoice)
        for choice in definition.class_levels[2].choices
    )
    assert all(
        any(
            isinstance(choice, SpellKnownChoice)
            for choice in level.choices
        )
        for level in definition.class_levels[2:]
    )
    assert any(
        isinstance(choice, MetamagicChoice)
        for choice in definition.class_levels[4].choices
    )

    validation = CharacterBuildValidator(
        runtime.require(),
        expected_ruleset_digest=_STRICT_RULESET_DIGEST,
        permissive_multiclass_prerequisites=False,
    ).validate(definition, revisions.loadout)
    assert validation.valid, validation.issues

    result = materialize_character(
        definition=definition,
        holdings=revisions.holdings,
        loadout=revisions.loadout,
        runtime_entity_uuid=uuid4(),
        display_name="Draconic Spellblade",
        faction="heroes",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id="test.progression.fighter_2_sorcerer_3",
        ),
        expected_ruleset_digest=_STRICT_RULESET_DIGEST,
        permissive_multiclass_prerequisites=False,
        runtime=runtime,
    )
    entity = result.entity
    assert [
        row.hit_dice_value.normalized_score
        for row in entity.health.hit_dices
    ] == [10, 10, 6, 6, 6]
    assert entity.proficiency_bonus.normalized_score == 3
    assert {
        ability.value
        for ability in AbilityName
        if entity.saving_throws.get_saving_throw(
            ability.value,
        ).proficiency_sources.sources
    } == {"constitution", "strength"}
    assert len(entity.spellcasting.sources) == 1
    spell_source = next(iter(entity.spellcasting.sources.values()))
    assert spell_source.provider_ref == SORCERER_CLASS_REF
    assert spell_source.provider_level == 3
    assert entity.action_economy.spell_slot_1.normalized_score == 4
    assert entity.action_economy.spell_slot_2.normalized_score == 2
    assert revisions.holdings.items

    _assert_composition_removed(
        result,
        expected_noncomposition_scores={AbilityName.CHARISMA: 3},
    )


@pytest.mark.parametrize(
    "distribution",
    (
        (("fighter", 5), ("barbarian", 5)),
        (("barbarian", 5), ("fighter", 5)),
    ),
)
def test_overlapping_extra_attack_uses_highest_rank_without_stacking(
    runtime: ContentSystemRuntime,
    distribution: tuple[tuple[ClassId, int], ...],
) -> None:
    result = _materialize(runtime, distribution)
    entity = result.entity

    assert entity.proficiency_bonus.normalized_score == 4
    assert len(
        entity.action_economy.get_attack_multiplicity_grants(),
    ) == 2
    assert entity.action_economy.resolve_attacks_per_attack_action() == 2
    assert entity.action_economy.resources["extra_attacks"].maximum == 1
    assert len([
        action
        for action in entity.registered_actions
        if action.name == "Extra Attack"
    ]) == 1
    assert len([
        handler
        for handler in entity.event_handlers.values()
        if handler.name == "Extra Attack Resource"
    ]) == 1
    assert {
        hit_die.hit_dice_value.normalized_score
        for hit_die in entity.health.hit_dices
    } == {10, 12}
    first_class, first_levels = distribution[0]
    second_class, second_levels = distribution[1]
    assert entity.health.hit_dices_total_hit_points == (
        _HIT_DICE[first_class]
        + (first_levels - 1) * ((_HIT_DICE[first_class] // 2) + 1)
        + second_levels * ((_HIT_DICE[second_class] // 2) + 1)
    )
    first_spend = entity.spend_hit_dice(hit_dice_index=0)[0]
    second_spend = entity.spend_hit_dice(
        hit_dice_index=first_levels,
    )[0]
    assert first_spend.die_value == _HIT_DICE[first_class]
    assert second_spend.die_value == _HIT_DICE[second_class]
    assert entity.health.hit_dices[0].spent_hit_dice == 1
    assert entity.health.hit_dices[first_levels].spent_hit_dice == 1
    assert all(
        hit_die.spent_hit_dice == 0
        for index, hit_die in enumerate(entity.health.hit_dices)
        if index not in {0, first_levels}
    )

    _assert_composition_removed(result)


@pytest.mark.parametrize(
    "distribution",
    (
        (("barbarian", 1), ("sorcerer", 1)),
        (("sorcerer", 1), ("barbarian", 1)),
    ),
)
def test_overlapping_ac_candidates_resolve_by_score_not_class_order(
    runtime: ContentSystemRuntime,
    distribution: tuple[tuple[ClassId, int], ...],
) -> None:
    result = _materialize(runtime, distribution)
    entity = result.entity
    candidates = tuple(entity.equipment.armor_class_formula_candidates.values())
    winner = entity.equipment.resolve_armor_class_formula_candidate(
        entity.ability_scores,
    )

    assert len(candidates) == 2
    assert {
        (candidate.base_ac, candidate.ability_names)
        for candidate in candidates
    } == {
        (10, ("dexterity", "constitution")),
        (13, ("dexterity",)),
    }
    assert winner is not None
    assert (winner.base_ac, winner.ability_names) == (13, ("dexterity",))
    assert entity.ac_bonus().normalized_score == 14

    _assert_composition_removed(result)


@pytest.mark.parametrize(
    "distribution",
    (
        (("fighter", 2), ("sorcerer", 3)),
        (("sorcerer", 3), ("fighter", 2)),
        (("barbarian", 2), ("sorcerer", 3)),
        (("sorcerer", 3), ("barbarian", 2)),
    ),
)
def test_martial_levels_do_not_replace_sorcerer_spell_source(
    runtime: ContentSystemRuntime,
    distribution: tuple[tuple[ClassId, int], ...],
) -> None:
    result = _materialize(runtime, distribution)
    entity = result.entity

    assert len(entity.spellcasting.sources) == 1
    source_id, source = next(iter(entity.spellcasting.sources.items()))
    assert source.provider_ref == SORCERER_CLASS_REF
    assert source.provider_level == 3
    assert (
        entity.action_economy.spell_slot_1.normalized_score,
        entity.action_economy.spell_slot_2.normalized_score,
    ) == (4, 2)
    spells = tuple(
        action
        for action in entity.registered_actions
        if isinstance(action, SpellAction)
    )
    assert spells
    assert all(spell.spellcasting_source_id == source_id for spell in spells)

    _assert_composition_removed(result)


def test_three_class_build_uses_total_level_and_keeps_each_source(
    runtime: ContentSystemRuntime,
) -> None:
    result = _materialize(
        runtime,
        (("fighter", 2), ("barbarian", 1), ("sorcerer", 2)),
    )
    entity = result.entity

    assert entity.proficiency_bonus.normalized_score == 3
    assert [
        hit_die.hit_dice_value.normalized_score
        for hit_die in entity.health.hit_dices
    ] == [10, 10, 12, 6, 6]
    assert entity.get_action_template("Action Surge") is not None
    assert entity.get_action_template("Reckless Attack") is None
    assert len(entity.spellcasting.sources) == 1
    assert next(iter(entity.spellcasting.sources.values())).provider_ref == (
        SORCERER_CLASS_REF
    )

    _assert_composition_removed(result)


def test_added_fighter_martial_training_contributes_to_attack_math(
    runtime: ContentSystemRuntime,
) -> None:
    character_id = uuid4()
    definition, _, loadout = _revisions(
        runtime,
        (("sorcerer", 1), ("fighter", 1)),
        character_id=character_id,
    )
    fighter_holdings = compose_builtin_character_revisions(
        character_id=character_id,
        build=_single_class_build("fighter", 1),
        content_system=runtime.require(),
    ).holdings
    result = materialize_character(
        definition=definition,
        holdings=fighter_holdings,
        loadout=loadout,
        runtime_entity_uuid=uuid4(),
        display_name="Multiclass Martial Training",
        faction="heroes",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id="test.progression.multiclass_attack_math",
        ),
        expected_ruleset_digest=_STRICT_RULESET_DIGEST,
        permissive_multiclass_prerequisites=False,
        runtime=runtime,
    )
    entity = result.entity

    assert entity.creature_proficiencies.is_weapon_proficient(
        (WeaponProperty.MARTIAL,),
    )
    assert entity.weapon_attack_outcome_baseline(
        WeaponSlot.MELEE_MAIN,
    ).attack_bonus == 5

    _assert_composition_removed(result)


def test_same_entity_can_replace_composition_without_touching_holdings_or_state(
    runtime: ContentSystemRuntime,
) -> None:
    character_id = uuid4()
    first_definition, _, first_loadout = _revisions(
        runtime,
        (("fighter", 5),),
        character_id=character_id,
    )
    holdings = compose_builtin_character_revisions(
        character_id=character_id,
        build=_single_class_build("fighter", 5),
        content_system=runtime.require(),
    ).holdings
    first = materialize_character(
        definition=first_definition,
        holdings=holdings,
        loadout=first_loadout,
        runtime_entity_uuid=uuid4(),
        display_name="Same Entity Respec",
        faction="heroes",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id="test.progression.same_entity_recomposition",
        ),
        expected_ruleset_digest=_STRICT_RULESET_DIGEST,
        permissive_multiclass_prerequisites=False,
        runtime=runtime,
    )
    entity = first.entity
    first_receipt = first.composition_receipt
    assert first_receipt is not None
    runtime_uuid = entity.uuid
    item_uuids = frozenset(
        item.uuid for item in entity.inventory.items.values()
    )
    equipped_item_uuids = frozenset(
        item.uuid
        for item in entity.equipment.get_all_equipped_items()
    )

    remove_character_composition(entity, first_receipt)
    second_definition, _, second_loadout = _revisions(
        runtime,
        (("barbarian", 3), ("sorcerer", 2)),
        character_id=character_id,
        definition_revision=2,
    )
    validation = CharacterBuildValidator(
        runtime.require(),
        expected_ruleset_digest=_STRICT_RULESET_DIGEST,
        permissive_multiclass_prerequisites=False,
    ).validate(second_definition, second_loadout)
    assert validation.valid, validation.issues
    assert validation.preview is not None

    second_receipt = apply_character_composition(
        entity=entity,
        definition=second_definition,
        loadout=second_loadout,
        preview=validation.preview,
        runtime=runtime,
    )

    assert entity.uuid == runtime_uuid
    assert entity.name == "Same Entity Respec"
    assert entity.position == (2, 2)
    assert frozenset(
        item.uuid for item in entity.inventory.items.values()
    ) == item_uuids
    assert frozenset(
        item.uuid
        for item in entity.equipment.get_all_equipped_items()
    ) == equipped_item_uuids
    assert [
        hit_die.hit_dice_value.normalized_score
        for hit_die in entity.health.hit_dices
    ] == [12, 12, 12, 6, 6]
    assert entity.get_action_template("Extra Attack") is None
    assert entity.get_action_template("Action Surge") is None
    assert entity.get_action_template("Frenzy") is not None
    assert len(entity.spellcasting.sources) == 1

    remove_character_composition(entity, second_receipt)

    assert entity.uuid == runtime_uuid
    assert entity.name == "Same Entity Respec"
    assert entity.position == (2, 2)
    assert frozenset(
        item.uuid for item in entity.inventory.items.values()
    ) == item_uuids
    assert frozenset(
        item.uuid
        for item in entity.equipment.get_all_equipped_items()
    ) == equipped_item_uuids
