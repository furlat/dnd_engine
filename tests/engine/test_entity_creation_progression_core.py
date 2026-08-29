"""Focused tests for entity-owned creation and reversible progression."""

from uuid import uuid4

import pytest

from dnd.blocks.base_item import BaseItem
from dnd.blocks.equipment import Shield
from dnd.core.values import ModifiableValue
from dnd.entities.creature_transforms import EntityTransform
from dnd.entities.entity_creation import (
    compose_entity,
    create_entity,
    initial_item_transform,
)
from dnd.entities.entity import Entity
from dnd.entities.entity_progression import (
    ResolvedLevelStep,
    apply_level,
    hydrate_progression,
    remove_last_level,
)
from dnd.types.progression import (
    AppliedClassLevel,
    AppliedOriginState,
    CharacterClass,
)
from dnd.types.equipment import WeaponSlot
from dnd.types.items import ItemKind
from dnd.core.events.events_registry import EventPhase, EventQueue, EventType
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture(autouse=True)
def _reset_event_history() -> None:
    EventQueue.reset()


def _weight_transform(transform_id: str, amount: int) -> EntityTransform:
    def apply(target):
        target.weight += amount

        def undo() -> None:
            target.weight -= amount

        return undo

    return EntityTransform(transform_id, apply)


def _level(
    *,
    step_id: str,
    character_level: int,
    class_id: CharacterClass,
    resulting_class_level: int,
    amount: int,
) -> ResolvedLevelStep:
    return ResolvedLevelStep(
        level=AppliedClassLevel(
            step_id=step_id,
            character_level=character_level,
            class_id=class_id,
            resulting_class_level=resulting_class_level,
        ),
        transforms=(_weight_transform(f"{step_id}.weight", amount),),
    )


def test_create_entity_is_the_universal_semantic_birth_path() -> None:
    entity = create_entity(uuid4(), entity_kind_id="test.neutral")
    try:
        assert entity.entity_kind_id == "test.neutral"
        assert entity.uuid == entity.source_entity_uuid
        assert entity.applied_class_levels == []
        assert entity.model_dump(mode="json")["entity_kind_id"] == "test.neutral"
    finally:
        entity.discard_unpublished_runtime()


def test_composition_commits_one_terminal_creation_fact() -> None:
    entity = create_entity(uuid4(), entity_kind_id="test.composed")
    try:
        compose_entity(
            entity,
            transforms=(_weight_transform("birth.weight", 4),),
        )
        facts = EventQueue.get_events_by_type(EventType.ENTITY_CREATED)
        assert len(facts) == 1
        assert facts[0].phase is EventPhase.COMPLETION
        assert facts[0].entity_kind_id == "test.composed"
        assert facts[0].entity_uuid == entity.uuid
        assert dict(facts[0].ability_scores) == {
            ability.name: ability.ability_score.score
            for ability in entity.ability_scores.abilities_list
        }
        assert facts[0].current_hit_points == entity.get_hp()
        assert facts[0].maximum_hit_points == entity.get_max_hp()
        assert facts[0].walking_speed_feet == entity.action_economy.current_speed()
        assert facts[0].armor_class == entity.ac_bonus().normalized_score
    finally:
        entity.discard_unpublished_runtime()


def test_creation_fact_uses_the_normal_completion_metadata_path() -> None:
    entity = create_entity(uuid4(), entity_kind_id="test.completion-metadata")
    observer_uuid = str(uuid4())
    cursor = EventQueue.event_cursor()
    EventQueue.set_identified_entity_observer_computer(
        lambda event: (
            {str(entity.uuid): {observer_uuid}}
            if event.event_type is EventType.ENTITY_CREATED
            else {}
        ),
    )
    try:
        compose_entity(entity)
        facts = [
            event
            for _, event in EventQueue.iter_events_since(cursor)
            if event.event_type is EventType.ENTITY_CREATED
        ]
        assert len(facts) == 1
        fact = facts[0]
        assert fact.phase is EventPhase.COMPLETION
        committed = Entity.get(fact.entity_uuid)
        assert committed is not None
        assert committed.creation_committed is True
        assert fact.located_entity_observer_uuids == {
            str(entity.uuid): {observer_uuid},
        }
    finally:
        entity.discard_unpublished_runtime()


def test_game_deploys_only_after_the_creation_fact() -> None:
    reset_engine_runtime(grid_size=(8, 8))
    entity = create_entity(uuid4(), entity_kind_id="test.deployable")
    game = Game()
    try:
        with pytest.raises(RuntimeError, match="before creation commits"):
            game.deploy_entity(entity, (4, 6))
        compose_entity(entity)
        creation_cursor = EventQueue.event_cursor()
        game.deploy_entity(entity, (4, 6))
        assert entity.is_deployed
        assert game.get_entity(entity.uuid) is entity
        events = EventQueue.get_events_chronological()
        assert events[creation_cursor - 1].event_type is EventType.ENTITY_CREATED
        assert events[creation_cursor].event_type is EventType.SPATIAL_ENTITY_ENTERED
    finally:
        game.close()
        entity.discard_unpublished_runtime()


def test_level_application_and_removal_are_exactly_reversible() -> None:
    entity = create_entity(uuid4(), entity_kind_id="test.classable")
    initial_weight = entity.weight
    try:
        compose_entity(entity)
        first = _level(
            step_id="fighter.1",
            character_level=1,
            class_id=CharacterClass.FIGHTER,
            resulting_class_level=1,
            amount=3,
        )
        second = _level(
            step_id="barbarian.1",
            character_level=2,
            class_id=CharacterClass.BARBARIAN,
            resulting_class_level=1,
            amount=5,
        )
        apply_level(entity, first)
        apply_level(entity, second)
        assert entity.weight == initial_weight + 8
        assert [row.step_id for row in entity.applied_class_levels] == [
            "fighter.1",
            "barbarian.1",
        ]

        with pytest.raises(ValueError, match="last level step"):
            remove_last_level(entity, "fighter.1")
        assert entity.weight == initial_weight + 8

        assert remove_last_level(entity, "barbarian.1") == second.level
        assert remove_last_level(entity, "fighter.1") == first.level
        assert entity.weight == initial_weight
        assert entity.applied_class_levels == []
        assert [
            event.event_type
            for event in EventQueue.get_events_chronological()
            if event.event_type in {
                EventType.ENTITY_LEVEL_ADDED,
                EventType.ENTITY_LEVEL_REMOVED,
            }
        ] == [
            EventType.ENTITY_LEVEL_ADDED,
            EventType.ENTITY_LEVEL_ADDED,
            EventType.ENTITY_LEVEL_REMOVED,
            EventType.ENTITY_LEVEL_REMOVED,
        ]
    finally:
        entity.discard_unpublished_runtime()


def test_failed_level_and_hydration_rollback_every_completed_transform() -> None:
    entity = create_entity(uuid4(), entity_kind_id="test.rollback")
    initial_weight = entity.weight

    def fail(_target):
        raise RuntimeError("broken authored operation")

    broken = ResolvedLevelStep(
        level=AppliedClassLevel(
            step_id="fighter.1",
            character_level=1,
            class_id=CharacterClass.FIGHTER,
            resulting_class_level=1,
        ),
        transforms=(
            _weight_transform("weight.first", 7),
            EntityTransform("fail", fail),
        ),
    )
    try:
        with pytest.raises(RuntimeError, match="broken authored operation"):
            hydrate_progression(
                entity,
                AppliedOriginState(),
                (broken,),
                origin_transforms=(_weight_transform("origin.weight", 2),),
            )
        assert entity.weight == initial_weight
        assert entity.applied_origin_state is None
        assert entity.applied_class_levels == []
        assert entity._progression_receipts == {}
        assert EventQueue.event_cursor() == 0
    finally:
        entity.discard_unpublished_runtime()


def test_failed_birth_discards_the_unpublished_entity_aggregate() -> None:
    entity = create_entity(uuid4(), entity_kind_id="test.failed-birth")

    def fail(_target):
        raise RuntimeError("invalid final composition")

    with pytest.raises(RuntimeError, match="invalid final composition"):
        compose_entity(
            entity,
            transforms=(EntityTransform("birth.fail", fail),),
        )

    assert Entity.get(entity.uuid) is None
    assert EventQueue.get_events_by_type(EventType.ENTITY_CREATED) == []


def test_failed_birth_fact_publication_rolls_back_the_committed_aggregate() -> None:
    entity = create_entity(uuid4(), entity_kind_id="test.failed-birth-fact")

    def fail_publication(event):
        if event.event_type is EventType.ENTITY_CREATED:
            raise RuntimeError("observer snapshot failed")
        return {}

    EventQueue.set_identified_entity_observer_computer(fail_publication)
    try:
        with pytest.raises(RuntimeError, match="observer snapshot failed"):
            compose_entity(
                entity,
                transforms=(_weight_transform("birth.weight", 4),),
            )
    finally:
        EventQueue.set_identified_entity_observer_computer(None)

    assert not entity.creation_committed
    assert Entity.get(entity.uuid) is None
    assert EventQueue.event_cursor() == 0


def test_failed_level_fact_publication_restores_the_exact_previous_state() -> None:
    entity = create_entity(uuid4(), entity_kind_id="test.failed-level-fact")
    initial_weight = entity.weight
    step = _level(
        step_id="fighter.1",
        character_level=1,
        class_id=CharacterClass.FIGHTER,
        resulting_class_level=1,
        amount=3,
    )
    compose_entity(entity)

    def fail_added_publication(event):
        if event.event_type is EventType.ENTITY_LEVEL_ADDED:
            raise RuntimeError("level observer snapshot failed")
        return {}

    EventQueue.set_identified_entity_observer_computer(fail_added_publication)
    try:
        with pytest.raises(RuntimeError, match="level observer snapshot failed"):
            apply_level(entity, step)
    finally:
        EventQueue.set_identified_entity_observer_computer(None)

    assert entity.weight == initial_weight
    assert entity.applied_class_levels == []
    assert entity._progression_receipts == {}
    assert EventQueue.get_events_by_type(EventType.ENTITY_LEVEL_ADDED) == []

    apply_level(entity, step)

    def fail_removed_publication(event):
        if event.event_type is EventType.ENTITY_LEVEL_REMOVED:
            raise RuntimeError("removal observer snapshot failed")
        return {}

    EventQueue.set_identified_entity_observer_computer(fail_removed_publication)
    try:
        with pytest.raises(RuntimeError, match="removal observer snapshot failed"):
            remove_last_level(entity, step.level.step_id)
    finally:
        EventQueue.set_identified_entity_observer_computer(None)

    assert entity.weight == initial_weight + 3
    assert entity.applied_class_levels == [step.level]
    assert tuple(entity._progression_receipts) == (step.level.step_id,)
    assert EventQueue.get_events_by_type(EventType.ENTITY_LEVEL_REMOVED) == []
    entity.discard_unpublished_runtime()


def test_starting_inventory_and_equipment_are_part_of_birth_not_gameplay() -> None:
    entity = create_entity(uuid4(), entity_kind_id="test.loadout")
    ration = BaseItem(
        source_entity_uuid=entity.uuid,
        semantic_key="item.ration",
        name="Ration",
    )
    shield = Shield(
        source_entity_uuid=entity.uuid,
        semantic_key="item.shield",
        ac_bonus=ModifiableValue.create(
            source_entity_uuid=entity.uuid,
            base_value=2,
            value_name="Shield Armor Class",
        ),
    )
    try:
        compose_entity(
            entity,
            transforms=(
                initial_item_transform(
                    transform_id="holding.ration",
                    item=ration,
                ),
                initial_item_transform(
                    transform_id="equipment.shield",
                    item=shield,
                    equipment_slot=WeaponSlot.MELEE_OFF,
                ),
            ),
        )

        assert entity.inventory.items == {ration.uuid: ration}
        assert entity.equipment.weapon_melee_off is shield
        assert shield.stored_in_uuid == entity.equipment.uuid
        assert shield.uuid not in entity.inventory.items
        events = EventQueue.get_events_chronological()
        assert [event.event_type for event in events] == [EventType.ENTITY_CREATED]
        birth = events[0]
        assert birth.inventory_item_uuids == (ration.uuid,)
        assert birth.equipment == ((WeaponSlot.MELEE_OFF.value, shield.uuid),)
        item_states = {state.item_uuid: state for state in birth.items}
        assert item_states[ration.uuid].semantic_key == "item.ration"
        assert item_states[ration.uuid].item_kind is ItemKind.ITEM
        assert item_states[shield.uuid].semantic_key == "item.shield"
        assert item_states[shield.uuid].item_kind is ItemKind.SHIELD
        assert item_states[shield.uuid].shield_armor_class_bonus == 2
        payload = birth.model_dump(mode="json")
        assert "visual_item_name" not in str(payload)
        assert "visual_variant_id" not in str(payload)
        assert "content_ref" not in str(payload)
    finally:
        entity.discard_unpublished_runtime()


def test_failed_birth_silently_removes_starting_items() -> None:
    entity = create_entity(uuid4(), entity_kind_id="test.failed-loadout")
    item = BaseItem(
        source_entity_uuid=entity.uuid,
        semantic_key="item.failed",
    )

    def fail(_target):
        raise RuntimeError("invalid loadout")

    with pytest.raises(RuntimeError, match="invalid loadout"):
        compose_entity(
            entity,
            transforms=(
                initial_item_transform(
                    transform_id="holding.failed",
                    item=item,
                ),
                EntityTransform("birth.fail-after-item", fail),
            ),
        )

    assert item.owner_uuid is None
    assert item.stored_in_uuid is None
    assert Entity.get(entity.uuid) is None
    assert EventQueue.event_cursor() == 0
