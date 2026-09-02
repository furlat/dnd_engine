"""Public aggregate progression proofs over the three direct class families."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.creature_proficiencies import CreatureProficienciesConfig
from dnd.blocks.health import HealthConfig
from dnd.content.characters.progression import (
    add_class_level,
    hydrate_class_progression,
    remove_last_class_level,
)
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.values import BaseValue, ModifiableValue
from dnd.entity import Entity, EntityConfig
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.character_progression import (
    AppliedClassLevel,
    AppliedOriginState,
    Background,
    CharacterClass,
    CharacterSubclass,
    ClassChoiceSelection,
    OriginChoiceSelection,
    Species,
)


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(8, 8))
    yield
    reset_engine_runtime()


def _entity(*, strength: int = 14, charisma: int = 14) -> Entity:
    entity = Entity.create(
        uuid4(),
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=strength),
                charisma=AbilityConfig(ability_score=charisma),
            ),
            health=HealthConfig(),
            proficiency_bonus=2,
            creature_proficiencies=CreatureProficienciesConfig(
                base_simple_weapons=False,
                base_martial_weapons=False,
                base_armor_types=(),
                base_shields=False,
            ),
        ),
    )
    entity.set_character_body_identity("creature.player.humanoid_body")
    return entity


def _post_birth_fighter_one(
    style: str = "class_feature.fighter.fighting_style.dueling",
) -> AppliedClassLevel:
    return AppliedClassLevel(
        step_id="class.fighter.level_1",
        character_level=1,
        class_id=CharacterClass.FIGHTER,
        resulting_class_level=1,
        choices=(ClassChoiceSelection(
            "class.fighter.level_1.fighting_style",
            (style,),
        ),),
    )


def _multiclass_sorcerer_one() -> AppliedClassLevel:
    return AppliedClassLevel(
        step_id="class.sorcerer.level_1",
        character_level=2,
        class_id=CharacterClass.SORCERER,
        resulting_class_level=1,
        subclass_id=CharacterSubclass.DRACONIC_BLOODLINE,
        choices=(
            ClassChoiceSelection(
                "class.sorcerer.level_1.subclass",
                (CharacterSubclass.DRACONIC_BLOODLINE.value,),
            ),
            ClassChoiceSelection(
                "class.sorcerer.level_1.cantrips",
                (
                    "spell.acid_splash",
                    "spell.chill_touch",
                    "spell.fire_bolt",
                    "spell.light",
                ),
            ),
            ClassChoiceSelection(
                "class.sorcerer.level_1.spell_known",
                ("spell.burning_hands", "spell.charm_person"),
            ),
            ClassChoiceSelection(
                "subclass.sorcerer.draconic_bloodline.level_1.ancestry",
                ("class_feature.sorcerer.draconic_ancestry.red",),
            ),
        ),
    )


def _sorcerer_level(level: int) -> AppliedClassLevel:
    if level == 1:
        choices = (
            ClassChoiceSelection(
                "class.sorcerer.level_1.subclass",
                (CharacterSubclass.DRACONIC_BLOODLINE.value,),
            ),
            ClassChoiceSelection(
                "class.sorcerer.level_1.cantrips",
                (
                    "spell.acid_splash",
                    "spell.chill_touch",
                    "spell.fire_bolt",
                    "spell.light",
                ),
            ),
            ClassChoiceSelection(
                "class.sorcerer.level_1.spell_known",
                ("spell.burning_hands", "spell.charm_person"),
            ),
            ClassChoiceSelection(
                "subclass.sorcerer.draconic_bloodline.level_1.ancestry",
                ("class_feature.sorcerer.draconic_ancestry.red",),
            ),
        )
    elif level == 2:
        choices = (
            ClassChoiceSelection(
                "class.sorcerer.level_2.spell_known",
                ("spell.color_spray",),
            ),
            ClassChoiceSelection(
                "class.sorcerer.level_2.spell_replacement",
                ("spell.burning_hands", "spell.magic_missile"),
            ),
        )
    elif level == 3:
        choices = (
            ClassChoiceSelection(
                "class.sorcerer.level_3.spell_known",
                ("spell.blindness_deafness",),
            ),
            ClassChoiceSelection(
                "class.sorcerer.level_3.metamagic",
                (
                    "class_feature.sorcerer.metamagic.quickened_spell",
                    "class_feature.sorcerer.metamagic.twinned_spell",
                ),
            ),
        )
    else:
        raise ValueError("aggregate fixture only defines Sorcerer levels 1-3")
    return AppliedClassLevel(
        step_id=f"class.sorcerer.level_{level}",
        character_level=level,
        class_id=CharacterClass.SORCERER,
        resulting_class_level=level,
        subclass_id=CharacterSubclass.DRACONIC_BLOODLINE,
        choices=choices,
    )


def _runtime_snapshot(entity: Entity) -> dict[str, object]:
    hit_dice = tuple(
        (
            row.uuid,
            row.spent_hit_dice,
            row.hit_dice_value.uuid,
            row.hit_dice_value.self_static.uuid,
            row.hit_dice_value.to_target_static.uuid,
            row.hit_dice_value.self_contextual.uuid,
            row.hit_dice_value.to_target_contextual.uuid,
            row.hit_dice_count.uuid,
            row.hit_dice_count.self_static.uuid,
            row.hit_dice_count.to_target_static.uuid,
            row.hit_dice_count.self_contextual.uuid,
            row.hit_dice_count.to_target_contextual.uuid,
        )
        for row in entity.health.hit_dices
    )
    return {
        "levels": entity.applied_class_levels,
        "actions": tuple(
            (action.uuid, action.semantic_key)
            for action in entity.registered_actions
        ),
        "handlers": tuple(
            (handler_uuid, handler.enabled)
            for handler_uuid, handler in entity.event_handlers.items()
        ),
        "global_handlers": EventQueue.event_handler_order(),
        "hit_dice": hit_dice,
        "resources": tuple(
            (name, resource.model_dump(mode="python"))
            for name, resource in entity.action_economy.resources.items()
        ),
        "features": tuple(
            (feature_id, tuple(sorted(source_ids, key=str)))
            for feature_id, source_ids in entity.feature_sources.items()
        ),
        "receipts": tuple(
            (level.step_id, entity.character_grant_receipt(level.step_id))
            for level in entity.applied_class_levels
        ),
        "base_objects": frozenset(BaseObject._registry),
        "base_blocks": frozenset(BaseBlock._registry),
        "base_values": frozenset(BaseValue._registry),
        "modifiable_values": frozenset(ModifiableValue._registry),
        "cursor": EventQueue.event_cursor(),
    }


def test_public_mixed_fighter_sorcerer_add_remove_uses_terminal_facts() -> None:
    entity = _entity()
    fighter = _post_birth_fighter_one()
    sorcerer = _multiclass_sorcerer_one()

    fighter_event = add_class_level(entity, fighter)
    sorcerer_event = add_class_level(entity, sorcerer)

    assert fighter_event.event_type is EventType.ENTITY_LEVEL_ADDED
    assert sorcerer_event.event_type is EventType.ENTITY_LEVEL_ADDED
    assert fighter_event.phase is sorcerer_event.phase is EventPhase.COMPLETION
    assert entity.applied_class_levels == (fighter, sorcerer)
    assert sorcerer_event.resulting_class_levels == (
        (CharacterClass.FIGHTER, 1),
        (CharacterClass.SORCERER, 1),
    )
    assert entity.proficiency_bonus.score == 2
    assert entity.action_economy.get_normal_spell_slot_capacities() == {1: 2}
    assert all(
        ".first_class." not in choice.choice_id
        for level in entity.applied_class_levels
        for choice in level.choices
    )

    removed_sorcerer = remove_last_class_level(entity)
    removed_fighter = remove_last_class_level(entity)
    assert removed_sorcerer.event_type is EventType.ENTITY_LEVEL_REMOVED
    assert removed_fighter.event_type is EventType.ENTITY_LEVEL_REMOVED
    assert entity.applied_class_levels == ()
    assert entity.action_economy.get_normal_spell_slot_capacities() == {}
    assert tuple(
        event.phase
        for _, event in EventQueue.iter_events_since(0)
        if event.event_type in {
            EventType.ENTITY_LEVEL_ADDED,
            EventType.ENTITY_LEVEL_REMOVED,
        }
    ) == (
        EventPhase.COMPLETION,
        EventPhase.COMPLETION,
        EventPhase.COMPLETION,
        EventPhase.COMPLETION,
    )


def test_public_multiclass_prerequisite_fails_before_owner_mutation() -> None:
    entity = _entity(charisma=12)
    add_class_level(entity, _post_birth_fighter_one())
    levels = entity.applied_class_levels
    actions = tuple(entity.registered_actions)
    hit_dice = tuple(entity.health.hit_dices)
    cursor = EventQueue.event_cursor()

    with pytest.raises(ValueError, match="multiclass prerequisite"):
        add_class_level(entity, _multiclass_sorcerer_one())

    assert entity.applied_class_levels == levels
    assert tuple(entity.registered_actions) == actions
    assert tuple(entity.health.hit_dices) == hit_dice
    assert EventQueue.event_cursor() == cursor


def test_hydration_rebuilds_receipts_silently_from_semantic_levels() -> None:
    semantic_levels = (
        _post_birth_fighter_one(),
        _multiclass_sorcerer_one(),
    )
    loaded = _entity()
    loaded.applied_class_levels = semantic_levels

    hydrate_class_progression(loaded)

    assert loaded.applied_class_levels == semantic_levels
    assert loaded.character_grant_receipt(semantic_levels[0].step_id).step_id == (
        semantic_levels[0].step_id
    )
    assert loaded.character_grant_receipt(semantic_levels[1].step_id).step_id == (
        semantic_levels[1].step_id
    )
    assert EventQueue.event_cursor() == 0


def test_existing_monster_can_receive_and_remove_an_ordinary_class_level() -> None:
    monster = Entity.create(
        uuid4(),
        content_ref=ContentRef(
            pack_id="fixture.progression",
            definition_kind=ContentDefinitionKind.CREATURE,
            content_id="creature.fixture.classed",
            content_version=1,
            definition_contract_hash="a" * 64,
        ),
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=14),
            ),
            health=HealthConfig(),
        ),
    )
    base_proficiency = monster.proficiency_bonus.score

    added = add_class_level(monster, _post_birth_fighter_one())
    assert added.phase is EventPhase.COMPLETION
    assert monster.applied_class_levels == (_post_birth_fighter_one(),)
    assert monster.proficiency_bonus.score == base_proficiency

    removed = remove_last_class_level(monster)
    assert removed.phase is EventPhase.COMPLETION
    assert monster.applied_class_levels == ()
    assert monster.proficiency_bonus.score == base_proficiency


def test_add_publication_failure_leaves_no_progression_owner_residue() -> None:
    entity = _entity()
    before = _runtime_snapshot(entity)

    def fail_added_fact(event: Event) -> None:
        if event.event_type is EventType.ENTITY_LEVEL_ADDED:
            raise RuntimeError("fixture completion observer failed")

    EventQueue.add_pre_completion_callback(fail_added_fact)
    with pytest.raises(RuntimeError, match="completion observer failed"):
        add_class_level(entity, _post_birth_fighter_one())

    assert _runtime_snapshot(entity) == before


def test_remove_publication_failure_restores_exact_runtime_identity_and_order() -> None:
    entity = _entity()
    level = _post_birth_fighter_one(
        "class_feature.fighter.fighting_style.protection",
    )
    add_class_level(entity, level)
    entity.action_economy.consume_resource("second_wind", 1)
    handler = next(iter(entity.event_handlers.values()))
    handler.enabled = False
    before = _runtime_snapshot(entity)

    def fail_removed_fact(event: Event) -> None:
        if event.event_type is EventType.ENTITY_LEVEL_REMOVED:
            raise RuntimeError("fixture completion observer failed")

    EventQueue.add_pre_completion_callback(fail_removed_fact)
    with pytest.raises(RuntimeError, match="completion observer failed"):
        remove_last_class_level(entity)

    assert _runtime_snapshot(entity) == before


def test_active_child_removal_completes_one_level_lineage_after_child_facts() -> None:
    entity = _entity()
    for level in range(1, 4):
        add_class_level(entity, _sorcerer_level(level))
    quickened = next(
        action
        for action in entity.registered_actions
        if action.semantic_key == "action.class.sorcerer.quickened_spell"
    )
    applied = quickened.instantiate().apply()
    assert applied is not None and not applied.canceled
    root_uuid = quickened.active_metamagic_condition_uuid
    assert root_uuid is not None

    cursor = EventQueue.event_cursor()
    removed = remove_last_class_level(entity)
    emitted = tuple(event for _, event in EventQueue.iter_events_since(cursor))

    execution = next(
        event
        for event in emitted
        if event.event_type is EventType.ENTITY_LEVEL_REMOVED
        and event.phase is EventPhase.EXECUTION
    )
    root_completion_index = next(
        index
        for index, event in enumerate(emitted)
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.phase is EventPhase.COMPLETION
        and event.condition.uuid == root_uuid
    )
    level_completion_index = emitted.index(removed)
    assert removed.uuid != execution.uuid
    assert removed.lineage_uuid == execution.lineage_uuid
    assert root_completion_index < level_completion_index
    assert entity.applied_class_levels == (
        _sorcerer_level(1),
        _sorcerer_level(2),
    )


def test_active_child_removal_keeps_terminal_fact_when_observation_fails() -> None:
    entity = _entity()
    for level in range(1, 4):
        add_class_level(entity, _sorcerer_level(level))
    quickened = next(
        action
        for action in entity.registered_actions
        if action.semantic_key == "action.class.sorcerer.quickened_spell"
    )
    applied = quickened.instantiate().apply()
    assert applied is not None and not applied.canceled
    root_uuid = quickened.active_metamagic_condition_uuid
    assert root_uuid is not None

    def fail_removed_observation(event: Event) -> None:
        if (
            event.event_type is EventType.ENTITY_LEVEL_REMOVED
            and event.phase is EventPhase.COMPLETION
        ):
            raise RuntimeError("fixture level observation failed")

    EventQueue.add_pre_completion_callback(fail_removed_observation)
    cursor = EventQueue.event_cursor()
    with pytest.raises(RuntimeError, match="level observation failed"):
        remove_last_class_level(entity)

    emitted = tuple(event for _, event in EventQueue.iter_events_since(cursor))
    execution = next(
        event
        for event in emitted
        if event.event_type is EventType.ENTITY_LEVEL_REMOVED
        and event.phase is EventPhase.EXECUTION
    )
    completion = next(
        event
        for event in emitted
        if event.event_type is EventType.ENTITY_LEVEL_REMOVED
        and event.phase is EventPhase.COMPLETION
    )
    child_index = next(
        index
        for index, event in enumerate(emitted)
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.phase is EventPhase.COMPLETION
        and event.condition.uuid == root_uuid
    )
    assert child_index < emitted.index(completion)
    assert completion.lineage_uuid == execution.lineage_uuid
    assert entity.applied_class_levels == (
        _sorcerer_level(1),
        _sorcerer_level(2),
    )
    assert root_uuid not in entity.active_conditions_by_uuid


def test_active_child_owner_corruption_fails_before_level_publication() -> None:
    entity = _entity()
    for level in range(1, 4):
        add_class_level(entity, _sorcerer_level(level))
    level = _sorcerer_level(3)
    receipt = entity.character_grant_receipt(level.step_id)
    quickened = next(
        action
        for action in entity.registered_actions
        if action.uuid == receipt.metamagic_root_owner_action_uuids[0]
    )
    applied = quickened.instantiate().apply()
    assert applied is not None and not applied.canceled
    root_uuid = quickened.active_metamagic_condition_uuid
    assert root_uuid is not None
    feature_id, source_id = receipt.feature_sources[0]
    assert entity.remove_feature_source(feature_id, source_id)
    levels = entity.applied_class_levels
    cursor = EventQueue.event_cursor()

    with pytest.raises(RuntimeError, match="feature source ownership changed"):
        remove_last_class_level(entity)

    assert EventQueue.event_cursor() == cursor
    assert entity.applied_class_levels == levels
    assert entity.active_conditions_by_uuid[root_uuid].uuid == root_uuid
    assert entity.character_grant_receipt(level.step_id) is receipt


def test_hydration_rebuilds_origin_before_class_owners_without_events() -> None:
    loaded = _entity(strength=10, charisma=10)
    origin_state = AppliedOriginState(
        base_ability_scores=(
            ("strength", 10),
            ("dexterity", 10),
            ("constitution", 10),
            ("intelligence", 10),
            ("wisdom", 10),
            ("charisma", 10),
        ),
        flexible_ability_bonuses=(("strength", 2), ("dexterity", 1)),
        choices=(OriginChoiceSelection(
            "species.human.additional_language",
            ("language.dwarvish",),
        ),),
    )
    loaded.character_species = Species.HUMAN
    loaded.character_background = Background.ADVENTURER
    loaded.applied_origin_state = origin_state
    loaded.applied_class_levels = (_post_birth_fighter_one(),)

    hydrate_class_progression(loaded)

    assert loaded.applied_origin_state == origin_state
    assert loaded.character_species is Species.HUMAN
    assert loaded.character_background is Background.ADVENTURER
    assert loaded.ability_scores.strength.ability_score.score == 12
    assert loaded.character_grant_receipt("origin.character").step_id == (
        "origin.character"
    )
    assert EventQueue.event_cursor() == 0
