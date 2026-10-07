"""Native birth/placement commitment and passive allegiance after-values."""

from uuid import uuid4

import pytest

from dnd.actor_projection import actor_from_birth, apply_actor_fact
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, ConditionApplicationEvent
from dnd.core.events import EntityCreatedEvent, EntityFactionChangedEvent, Event, EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.player.event_record import decode_event, encode_event


def actor() -> Entity:
    reset_engine_runtime(grid_size=(5, 5))
    return Entity.create(source_entity_uuid=uuid4(), name="Incoming creature",
        config=EntityConfig(position=(2, 2), faction="party"))


def test_prepared_creation_publishes_one_complete_birth_before_presence() -> None:
    incoming = actor()
    game = Game()
    start = EventQueue.event_cursor()
    birth = incoming.prepare_birth()
    deployment = game.prepare_deployment(incoming, (2, 2))
    assert list(EventQueue.iter_events_since(start)) == []
    assert not incoming.creation_committed and not incoming.is_deployed
    incoming.commit_birth(birth)
    game.commit_deployment(deployment)
    assert game.get_entity(incoming.uuid) is incoming
    assert get_map().get_entity_position(incoming.uuid) == (2, 2)
    assert list(EventQueue.iter_events_since(start)) == []
    created = incoming.publish_birth(birth)
    game.publish_deployment(deployment)
    incoming.commit_birth(birth)
    game.commit_deployment(deployment)
    incoming.publish_birth(birth)
    game.publish_deployment(deployment)
    completed = [event for _, event in EventQueue.iter_events_since(start)
                 if event.phase is EventPhase.COMPLETION]
    assert sum(isinstance(event, EntityCreatedEvent) for event in completed) == 1
    entered = next(event for event in completed if event.event_type is EventType.SPATIAL_ENTITY_ENTERED)
    assert completed.index(created) < completed.index(entered)


def test_birth_publication_error_does_not_unregister_committed_actor() -> None:
    incoming = actor()
    birth = incoming.prepare_birth()
    incoming.commit_birth(birth)

    def fail_publication(event: Event) -> None:
        if isinstance(event, EntityCreatedEvent):
            raise RuntimeError("birth publication failed")

    EventQueue.add_pre_completion_callback(fail_publication)
    with pytest.raises(RuntimeError, match="birth publication failed"):
        incoming.publish_birth(birth)
    assert incoming.creation_committed
    assert Entity.get(incoming.uuid) is incoming
    with pytest.raises(RuntimeError, match="already committed"):
        incoming.compose_entity()
    assert Entity.get(incoming.uuid) is incoming


def test_invalid_incoming_placement_keeps_birth_unpublished() -> None:
    incoming = actor()
    start = EventQueue.event_cursor()
    with pytest.raises(ValueError, match="unavailable"):
        Game().prepare_deployment(incoming, (9, 9))
    assert not incoming.creation_committed and not incoming.is_deployed
    assert list(EventQueue.iter_events_since(start)) == []


def test_ordinary_birth_keeps_actor_when_interrupted_after_publication() -> None:
    incoming = actor()

    def fail_observer(event: Event) -> None:
        if isinstance(event, EntityCreatedEvent):
            raise KeyboardInterrupt("interrupted after birth")

    EventQueue.add_on_event_callback(fail_observer)
    with pytest.raises(KeyboardInterrupt, match="interrupted after birth"):
        incoming.compose_entity()

    assert Entity.get(incoming.uuid) is incoming
    assert incoming.creation_committed
    births = EventQueue.get_events_by_type(EventType.ENTITY_CREATED)
    assert len(births) == 1
    assert births[0].source_entity_uuid == incoming.uuid


def test_faction_after_value_round_trips_without_recreating_actor() -> None:
    incoming = actor()
    born = incoming.compose_entity()
    state = actor_from_birth(born)
    game = Game()
    game.deploy_entity(incoming, (2, 2))
    hp = incoming.get_hp()
    event = incoming.set_faction("uncontrolled", parent_event=born)
    assert isinstance(event, EntityFactionChangedEvent)
    assert event.parent_event == born.uuid and event.previous_faction == "party"
    retained = decode_event(encode_event(event))
    changed = apply_actor_fact(state, retained)
    assert changed.uuid == state.uuid and changed.faction == "uncontrolled"
    assert changed.normal_hp == state.normal_hp and incoming.get_hp() == hp
    cursor = EventQueue.event_cursor()
    assert incoming.set_faction("uncontrolled") is None
    assert EventQueue.event_cursor() == cursor


def test_initial_publication_failure_still_publishes_other_committed_memberships() -> None:
    incoming = actor()
    first, second = [BaseCondition(name=name, source_entity_uuid=incoming.uuid,
                                  target_entity_uuid=incoming.uuid)
                     for name in ("First initial effect", "Second initial effect")]
    prepared = incoming.prepare_initial_conditions((first, second))
    birth = incoming.prepare_birth(initial_conditions=prepared)

    def fail_first(event: Event) -> None:
        if isinstance(event, ConditionApplicationEvent) and event.condition.uuid == first.uuid:
            raise RuntimeError("First membership observer failed")

    with BaseBlock.condition_removal_scope():
        incoming.commit_initial_conditions(prepared)
        incoming.commit_birth(birth)
        incoming.publish_birth(birth)
        EventQueue.add_pre_completion_callback(fail_first)
        with pytest.raises(BaseExceptionGroup):
            incoming.publish_initial_conditions(prepared)
        incoming.publish_initial_conditions(prepared)
    assert all(effect.applied for effect in (first, second))
    completed = [event for event in EventQueue.get_events_by_type(EventType.CONDITION_APPLICATION)
                 if event.phase is EventPhase.COMPLETION]
    assert sum(event.condition.uuid == second.uuid for event in completed) == 1
