"""Seamless event-first observation/runtime contract tests."""

import time
from typing import Sequence
from uuid import uuid4

from dnd.action_timing import reset_action_timing_recorder, set_action_timing_recorder
from dnd.actions_functional import execute_by_index
from dnd.core.events import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
)
from tests.manual.authored_encounter_support import (
    assemble_authored_encounter,
    reset_authored_encounter_state,
)


def test_passive_event_batch_observer_receives_standalone_event_immediately() -> None:
    """An event outside an action remains immediately observable."""
    EventQueue.reset()
    batches: list[tuple[Event, ...]] = []

    def capture_batch(events: Sequence[Event]) -> None:
        batches.append(tuple(events))

    EventQueue.add_on_event_batch_callback(capture_batch)
    try:
        event = EventQueue.register(Event(
            source_entity_uuid=uuid4(),
            event_type=EventType.BASE_ACTION,
            phase=EventPhase.COMPLETION,
            use_register=False,
        ))
    finally:
        EventQueue.remove_on_event_batch_callback(capture_batch)

    assert batches == [(event,)]


def test_nested_passive_event_batches_flush_once_in_storage_order() -> None:
    """Nested causal scopes share the outer action's ordered event batch."""
    EventQueue.reset()
    batches: list[tuple[Event, ...]] = []

    def capture_batch(events: Sequence[Event]) -> None:
        batches.append(tuple(events))

    EventQueue.add_on_event_batch_callback(capture_batch)
    try:
        with EventQueue.batch_on_event_callbacks():
            first = EventQueue.register(Event(
                source_entity_uuid=uuid4(),
                event_type=EventType.BASE_ACTION,
                phase=EventPhase.DECLARATION,
                use_register=False,
            ))
            with EventQueue.batch_on_event_callbacks():
                second = EventQueue.register(Event(
                    source_entity_uuid=first.source_entity_uuid,
                    event_type=EventType.BASE_ACTION,
                    phase=EventPhase.COMPLETION,
                    use_register=False,
                ))
    finally:
        EventQueue.remove_on_event_batch_callback(capture_batch)

    assert batches == [(first, second)]


def test_completion_sequence_preserves_events_and_notifies_projection_once() -> None:
    """One derived-state cause stores every completion before one projection pass."""
    EventQueue.reset()
    immediate: list[Event] = []
    sequences: list[tuple[Event, ...]] = []

    def capture_event(event: Event) -> None:
        immediate.append(event)

    def capture_sequence(events: Sequence[Event]) -> None:
        sequences.append(tuple(events))

    EventQueue.add_on_event_callback(capture_event)
    EventQueue.add_on_event_sequence_callback(capture_sequence)
    events = (
        Event(
            source_entity_uuid=uuid4(),
            event_type=EventType.SENSORY_UPDATE,
            phase=EventPhase.COMPLETION,
            use_register=False,
        ),
        Event(
            source_entity_uuid=uuid4(),
            event_type=EventType.SENSORY_UPDATE,
            phase=EventPhase.COMPLETION,
            use_register=False,
        ),
    )
    try:
        stored = EventQueue.register_completion_sequence(events)
    finally:
        EventQueue.remove_on_event_callback(capture_event)
        EventQueue.remove_on_event_sequence_callback(capture_sequence)

    assert stored == events
    assert immediate == list(events)
    assert sequences == [events]
    assert tuple(EventQueue._all_events) == events


def test_position_aoe_action_lifecycle_timing_records_convolution_phases() -> None:
    """A real area spell exposes the action lifecycle inside execute-by-index."""
    reset_authored_encounter_state()
    arena = assemble_authored_encounter("line_aoe_corridor")
    hero = arena.hero
    hero.update_entity_senses(max_distance=20)
    actions = hero.get_available_actions()
    fireball = next(
        row
        for row in actions.position_actions
        if row.template_name == "Fireball__slot_3"
    )
    target = max(fireball.valid_targets, key=lambda candidate: candidate.affected_count or 0)
    phases: dict[str, float] = {}

    def record_phase(phase: str, started_at: float) -> None:
        phases[phase] = phases.get(phase, 0.0) + ((time.perf_counter() - started_at) * 1000)

    token = set_action_timing_recorder(record_phase)
    try:
        event = execute_by_index(hero, fireball.template_name, target.index, available=actions)
    finally:
        reset_action_timing_recorder(token)

    assert event is not None
    assert not event.canceled
    assert target.affected_count == 4
    assert "base_action.check_costs_ms" in phases
    assert "base_action.create_declaration_event_ms" in phases
    assert "base_action.validate_ms" in phases
    assert "base_action.resolve_convolution_targets_ms" in phases
    assert "base_action.convolution_apply_targets_ms" in phases
    assert "base_action.apply_costs_ms" in phases
    assert "base_action.apply_total_ms" in phases
    assert all(elapsed >= 0 for elapsed in phases.values())
    assert event.combat_log is not None
    assert event.total_targets >= target.affected_count


