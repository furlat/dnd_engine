"""Native sensory initialization and explicit refresh survive event-only replay."""

import json
from dataclasses import replace
from uuid import UUID

import pytest
from pydantic import ValidationError

from dnd.blocks.sensory import capture_senses_snapshot, reduce_senses_snapshot
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventPhase, EventQueue, SensoryUpdateEvent
from game.event_record import decode_event, encode_event
from tests.engine.test_senses_light_stealth import (
    create_skeleton, reset_senses_state,
)


def sensory_since(observer_uuid: UUID, cursor: int = 0) -> tuple[SensoryUpdateEvent, ...]:
    return tuple(event for _, event in EventQueue.iter_events_since(cursor)
                 if isinstance(event, SensoryUpdateEvent)
                 and event.observer_uuid == observer_uuid
                 and event.phase is EventPhase.COMPLETION)


def test_first_native_sensory_fact_seeds_complete_capabilities_and_world_view() -> None:
    reset_senses_state(width=6, height=2)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=True)
    events = sensory_since(observer.uuid)
    assert events and events[0].initial
    initial = events[0]
    assert initial.observer_position_changed and initial.sense_modes_changed
    assert initial.passive_perception_changed and initial.visual_access_changed
    assert initial.cause_event_uuid == initial.parent_event
    assert initial.cause_event_uuid is not None
    assert EventQueue.get_event_by_uuid(initial.cause_event_uuid) is not None

    state = None
    for event in events:
        restored = decode_event(encode_event(event))
        assert isinstance(restored, SensoryUpdateEvent)
        state = reduce_senses_snapshot(observer.uuid, state, restored)
    assert state is not None
    actual = capture_senses_snapshot(observer.senses)
    # Dirty paths request client invalidation; local navigation may already have
    # materialized them. It is not an authoritative navigation-cache after-value.
    assert replace(state, paths_dirty=False) == replace(actual, paths_dirty=False)


def test_explicit_refresh_records_changed_view_without_reparenting_or_empty_events() -> None:
    reset_senses_state(width=7, height=2)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    target = create_skeleton(name="Target", position=(4, 0), darkvision=False)
    assert target.uuid in observer.senses.entities
    state = None
    for event in sensory_since(observer.uuid):
        state = reduce_senses_snapshot(observer.uuid, state, event)
    assert state is not None

    cursor = EventQueue.event_cursor()
    observer.update_entity_senses(max_distance=1)
    changes = sensory_since(observer.uuid, cursor)
    assert len(changes) == 1
    event = changes[0]
    assert not event.initial
    assert event.cause_event_uuid is None
    assert event.parent_event is None and event.parent_lineage is None
    assert target.uuid not in observer.senses.entities
    restored = decode_event(encode_event(event))
    assert isinstance(restored, SensoryUpdateEvent)
    state = reduce_senses_snapshot(observer.uuid, state, restored)
    actual = capture_senses_snapshot(observer.senses)
    assert replace(state, paths_dirty=False) == replace(actual, paths_dirty=False)

    cursor = EventQueue.event_cursor()
    observer.update_entity_senses(max_distance=1)
    assert sensory_since(observer.uuid, cursor) == ()

    cursor = EventQueue.event_cursor()
    observer.update_entity_senses(max_distance=6)
    changes = sensory_since(observer.uuid, cursor)
    assert len(changes) == 1 and not changes[0].initial
    assert target.uuid in changes[0].entity_contacts_changed
    state = reduce_senses_snapshot(observer.uuid, state, changes[0])
    actual = capture_senses_snapshot(observer.senses)
    assert replace(state, paths_dirty=False) == replace(actual, paths_dirty=False)


def test_initial_scalar_omissions_and_delta_without_baseline_are_rejected() -> None:
    reset_senses_state(width=3, height=1)
    observer = create_skeleton(name="Observer", position=(0, 0))
    initial = sensory_since(observer.uuid)[0]
    payload = encode_event(initial)
    payload.pop("passive_perception")
    with pytest.raises(ValidationError, match="initial sensory update requires complete"):
        SensoryUpdateEvent.model_validate_json(json.dumps(payload), context=PASSIVE_EVENT_REPLAY)
    with pytest.raises(ValueError, match="previously recorded initial state"):
        reduce_senses_snapshot(observer.uuid, None, initial.model_copy(update={"initial": False}))
