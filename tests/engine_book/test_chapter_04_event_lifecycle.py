"""Engine book parity tests for event lifecycle behavior."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from dnd.core.base_object import BaseObject
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)


class LoggableEvent(Event):
    """Tiny event subclass used to test completion-time combat-log wiring."""

    def generate_combat_log(self) -> CombatLogEntry:
        """Create a deterministic combat log entry for this event."""
        text = self.status_message or self.name or "Loggable event"
        return CombatLogEntry(
            entry_type=CombatLogEntryType.ACTION,
            source_name=self.source_entity_name or "Source",
            source_uuid=str(self.source_entity_uuid),
            target_name=self.target_entity_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else None,
            compact=text,
            verbose=text,
            detailed=text,
        )


def reset_event_state() -> None:
    """Clear global event and object state touched by these examples."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()


def test_eb_04_001_phase_to_creates_versions_with_one_lineage() -> None:
    """EB-04-001: phase transitions create new UUIDs under one lineage."""
    reset_event_state()
    source_uuid = uuid4()
    target_uuid = uuid4()

    declaration = Event(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        status_message="declared",
    )
    execution = declaration.phase_to(EventPhase.EXECUTION, status_message="executing")
    effect = execution.phase_to(EventPhase.EFFECT, status_message="effect")
    completion = effect.phase_to(EventPhase.COMPLETION, status_message="complete")

    versions = [declaration, execution, effect, completion]
    assert [event.phase for event in versions] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    assert len({event.uuid for event in versions}) == 4
    assert {event.lineage_uuid for event in versions} == {declaration.lineage_uuid}
    assert all(EventQueue.get_event_by_uuid(event.uuid) is event for event in versions)

    history = EventQueue.get_event_history(completion.uuid)
    assert [event.phase for event in history] == [event.phase for event in versions]
    assert EventQueue.get_events_by_phase(EventPhase.COMPLETION) == [completion]
    assert EventQueue.get_events_by_source(source_uuid) == versions
    assert EventQueue.get_events_by_target(target_uuid) == versions


def test_eb_04_002_handlers_match_exact_phase_source_and_target() -> None:
    """EB-04-002: handlers dispatch by exact trigger and chain mutations."""
    reset_event_state()
    source_uuid = uuid4()
    target_uuid = uuid4()
    other_uuid = uuid4()
    calls: list[str] = []

    def first_handler(event: Event, _: UUID) -> Event:
        calls.append(f"first:{event.status_message}")
        event.status_message = "first changed this"
        return event

    def filtered_handler(event: Event, _: UUID) -> Event:
        calls.append(f"filtered:{event.status_message}")
        event.status_message = "filtered saw the change"
        return event

    def disabled_handler(event: Event, _: UUID) -> Event:
        calls.append(f"disabled:{event.status_message}")
        return event

    def wrong_target_handler(event: Event, _: UUID) -> Event:
        calls.append(f"wrong-target:{event.status_message}")
        return event

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_uuid,
            name="First execution handler",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.BASE_ACTION,
                    event_phase=EventPhase.EXECUTION,
                )
            ],
            event_processor=first_handler,
        )
    )
    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_uuid,
            name="Disabled execution handler",
            enabled=False,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.BASE_ACTION,
                    event_phase=EventPhase.EXECUTION,
                )
            ],
            event_processor=disabled_handler,
        )
    )
    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_uuid,
            name="Filtered execution handler",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.BASE_ACTION,
                    event_phase=EventPhase.EXECUTION,
                    event_source_entity_uuid=source_uuid,
                    event_target_entity_uuid=target_uuid,
                )
            ],
            event_processor=filtered_handler,
        )
    )
    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_uuid,
            name="Wrong target handler",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.BASE_ACTION,
                    event_phase=EventPhase.EXECUTION,
                    event_source_entity_uuid=source_uuid,
                    event_target_entity_uuid=other_uuid,
                )
            ],
            event_processor=wrong_target_handler,
        )
    )

    event = Event(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        status_message="before handlers",
    )
    execution = event.phase_to(EventPhase.EXECUTION)

    assert calls == ["first:before handlers", "filtered:first changed this"]
    assert execution.status_message == "filtered saw the change"


def test_eb_04_003_completion_skips_handlers_but_not_passive_callbacks() -> None:
    """EB-04-003: completion is stored and observed, but not handler-dispatched."""
    reset_event_state()
    source_uuid = uuid4()
    observed_phases: list[EventPhase] = []
    completion_handler_calls = 0

    def observe(event: Event) -> None:
        observed_phases.append(event.phase)

    def completion_handler(event: Event, _: UUID) -> Event:
        nonlocal completion_handler_calls
        completion_handler_calls += 1
        return event

    EventQueue.add_on_event_callback(observe)
    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_uuid,
            name="Completion handler",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.BASE_ACTION,
                    event_phase=EventPhase.COMPLETION,
                )
            ],
            event_processor=completion_handler,
        )
    )

    event = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
    )
    completion = (
        event.phase_to(EventPhase.EXECUTION)
        .phase_to(EventPhase.EFFECT)
        .phase_to(EventPhase.COMPLETION)
    )

    assert completion.phase == EventPhase.COMPLETION
    assert completion_handler_calls == 0
    assert observed_phases == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]


def test_eb_04_004_pre_completion_callbacks_can_attach_children() -> None:
    """EB-04-004: pre-completion callbacks run before child lineage freezes."""
    reset_event_state()
    source_uuid = uuid4()
    pre_completion_phases: list[EventPhase] = []
    child_lineage: UUID | None = None

    def attach_child(event: Event) -> None:
        nonlocal child_lineage
        pre_completion_phases.append(event.phase)
        if event.event_type != EventType.BASE_ACTION:
            return
        child = Event(
            name="Pre-completion child",
            source_entity_uuid=source_uuid,
            event_type=EventType.TRIGGER_EVENT,
            phase=EventPhase.DECLARATION,
            parent_event=event.uuid,
        )
        child_lineage = child.lineage_uuid
        child.phase_to(EventPhase.COMPLETION)

    EventQueue.add_pre_completion_callback(attach_child)

    parent = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
    )
    completion = (
        parent.phase_to(EventPhase.EXECUTION)
        .phase_to(EventPhase.EFFECT)
        .phase_to(EventPhase.COMPLETION)
    )

    assert pre_completion_phases == [EventPhase.EFFECT, EventPhase.DECLARATION]
    assert child_lineage is not None
    assert child_lineage in completion.children_lineages
    children = completion.get_children_events()
    assert len(children) == 1
    assert children[0].event_type == EventType.TRIGGER_EVENT
    assert children[0].phase == EventPhase.COMPLETION


def test_eb_04_005_completion_collects_child_combat_logs_top_level_only() -> None:
    """EB-04-005: completion builds parent logs from completed child logs."""
    reset_event_state()
    source_uuid = uuid4()
    captured_logs: list[CombatLogEntry] = []

    def capture_log(event: Event) -> None:
        if event.combat_log:
            captured_logs.append(event.combat_log)

    EventQueue.set_combat_log_callback(capture_log)

    parent = LoggableEvent(
        name="Parent action",
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        status_message="Parent log",
    )
    child = LoggableEvent(
        name="Child effect",
        source_entity_uuid=source_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.DECLARATION,
        status_message="Child log",
        parent_event=parent.uuid,
    )
    child_completion = child.phase_to(EventPhase.COMPLETION)
    parent_completion = (
        parent.phase_to(EventPhase.EXECUTION)
        .phase_to(EventPhase.EFFECT)
        .phase_to(EventPhase.COMPLETION)
    )

    assert child_completion.combat_log is not None
    assert parent_completion.combat_log is not None
    assert len(captured_logs) == 1
    assert captured_logs[0].compact == "Parent log"
    assert [entry.compact for entry in captured_logs[0].sub_entries] == ["Child log"]


def test_eb_04_006_cancel_posts_cancel_phase_and_stops_handler_chain() -> None:
    """EB-04-006: canceled events move to CANCEL and stop later handlers."""
    reset_event_state()
    source_uuid = uuid4()
    calls: list[str] = []

    def canceling_handler(event: Event, _: UUID) -> Event:
        calls.append("canceling")
        return event.cancel(status_message="blocked by handler")

    def later_handler(event: Event, _: UUID) -> Event:
        calls.append("later")
        return event

    trigger = Trigger(
        event_type=EventType.BASE_ACTION,
        event_phase=EventPhase.EXECUTION,
    )
    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_uuid,
            name="Canceling handler",
            trigger_conditions=[trigger],
            event_processor=canceling_handler,
        )
    )
    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_uuid,
            name="Later handler",
            trigger_conditions=[trigger],
            event_processor=later_handler,
        )
    )

    event = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
    )
    canceled = event.phase_to(EventPhase.EXECUTION)

    assert calls == ["canceling"]
    assert canceled.canceled is True
    assert canceled.phase == EventPhase.CANCEL
    assert canceled.status_message == "blocked by handler"
    assert EventQueue.get_events_by_phase(EventPhase.CANCEL)


def test_eb_04_007_push_combat_log_bypasses_event_storage() -> None:
    """EB-04-007: standalone combat logs callback without queue storage."""
    reset_event_state()
    source_uuid = uuid4()
    captured_events: list[Event] = []
    entry = CombatLogEntry(
        entry_type=CombatLogEntryType.ENTITY_SPOTTED,
        source_name="Observer",
        source_uuid=str(source_uuid),
        compact="Observer spots a hidden foe",
        verbose="Observer spots a hidden foe",
        detailed="Observer spots a hidden foe",
    )

    EventQueue.push_combat_log(entry, source_uuid)
    assert captured_events == []
    assert EventQueue.get_events_by_phase(EventPhase.COMPLETION) == []

    EventQueue.set_combat_log_callback(captured_events.append)
    EventQueue.push_combat_log(entry, source_uuid)

    assert len(captured_events) == 1
    event = captured_events[0]
    assert event.phase == EventPhase.COMPLETION
    assert event.event_type == EventType.CONDITION_APPLICATION
    assert event.source_entity_uuid == source_uuid
    assert event.combat_log is entry
    assert EventQueue.get_event_by_uuid(event.uuid) is None
    assert EventQueue.get_events_by_phase(EventPhase.COMPLETION) == []


def test_eb_04_008_completion_log_callback_runs_before_completion_storage() -> None:
    """EB-04-008: completion log callbacks run before completion storage."""
    reset_event_state()
    source_uuid = uuid4()
    observations: list[tuple[UUID, EventPhase, list[Event], EventPhase | None]] = []

    def capture_event_state(event: Event) -> None:
        existing_event = EventQueue.get_event_by_uuid(event.uuid)
        observations.append(
            (
                event.uuid,
                event.phase,
                EventQueue.get_events_by_phase(EventPhase.COMPLETION),
                existing_event.phase if existing_event else None,
            )
        )

    EventQueue.set_combat_log_callback(capture_event_state)

    declaration = LoggableEvent(
        name="Completion callback ordering",
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        status_message="Callback ordering log",
    )
    effect = declaration.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
    completion = effect.phase_to(EventPhase.COMPLETION)

    assert len(observations) == 1
    observed_uuid, observed_phase, observed_completions, observed_stored_phase = observations[0]
    assert observed_phase == EventPhase.COMPLETION
    assert observed_uuid == effect.uuid
    assert observed_completions == []
    assert observed_stored_phase == EventPhase.EFFECT
    assert completion.uuid != observed_uuid
    assert EventQueue.get_event_by_uuid(completion.uuid) is completion
    assert EventQueue.get_events_by_phase(EventPhase.COMPLETION) == [completion]


def test_eb_04_009_passive_callback_exceptions_do_not_block_storage() -> None:
    """EB-04-009: passive callback failures are swallowed per callback."""
    reset_event_state()
    source_uuid = uuid4()
    calls: list[str] = []

    def failing_callback(event: Event) -> None:
        calls.append(f"failing:{event.phase.value}")
        raise RuntimeError("passive callback failure")

    def later_callback(event: Event) -> None:
        calls.append(f"later:{event.phase.value}")

    EventQueue.add_on_event_callback(failing_callback)
    EventQueue.add_on_event_callback(later_callback)

    event = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
    )
    execution = event.phase_to(EventPhase.EXECUTION)

    assert calls == [
        "failing:declaration",
        "later:declaration",
        "failing:execution",
        "later:execution",
    ]
    assert EventQueue.get_event_by_uuid(event.uuid) is event
    assert EventQueue.get_event_by_uuid(execution.uuid) is execution
    assert EventQueue.get_events_by_phase(EventPhase.DECLARATION) == [event]
    assert EventQueue.get_events_by_phase(EventPhase.EXECUTION) == [execution]


def test_eb_04_010_missing_parent_event_does_not_block_child_storage() -> None:
    """EB-04-010: missing parent references do not block child storage."""
    reset_event_state()
    source_uuid = uuid4()
    missing_parent_uuid = uuid4()

    child = Event(
        name="Orphan child event",
        source_entity_uuid=source_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.DECLARATION,
        parent_event=missing_parent_uuid,
    )
    completion = child.phase_to(EventPhase.COMPLETION)

    assert child.parent_event == missing_parent_uuid
    assert child.get_parent_event() is None
    assert completion.parent_event == missing_parent_uuid
    assert completion.parent_lineage is None
    assert completion.get_parent_event() is None
    assert completion.children_lineages == []
    assert EventQueue.get_event_by_uuid(child.uuid) is child
    assert EventQueue.get_event_by_uuid(completion.uuid) is completion
    assert EventQueue.get_events_by_phase(EventPhase.DECLARATION) == [child]
    assert EventQueue.get_events_by_phase(EventPhase.COMPLETION) == [completion]


def test_eb_04_011_late_children_do_not_recompute_completed_parent_lineages() -> None:
    """EB-04-011: late child events do not recompute completed parent lineages."""
    reset_event_state()
    source_uuid = uuid4()

    parent = Event(
        name="Parent",
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
    )
    early_child = Event(
        name="Early child",
        source_entity_uuid=source_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.DECLARATION,
        parent_event=parent.uuid,
    )
    early_child_completion = early_child.phase_to(EventPhase.COMPLETION)
    parent_completion = (
        parent.phase_to(EventPhase.EXECUTION)
        .phase_to(EventPhase.EFFECT)
        .phase_to(EventPhase.COMPLETION)
    )

    assert parent_completion.children_lineages == [early_child.lineage_uuid]
    assert parent_completion.get_children_events() == [early_child_completion]

    late_child = Event(
        name="Late child",
        source_entity_uuid=source_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.DECLARATION,
        parent_event=parent_completion.uuid,
    )
    late_child_completion = late_child.phase_to(EventPhase.COMPLETION)

    assert late_child_completion.parent_lineage == parent.lineage_uuid
    assert late_child_completion.get_parent_event() is parent_completion
    assert late_child.uuid in parent_completion.children_events
    assert late_child.uuid in parent_completion.lineage_children_events
    assert parent_completion.children_lineages == [early_child.lineage_uuid]
    assert parent_completion.get_children_events() == [early_child_completion]


def test_eb_04_012_empty_trigger_handlers_are_direct_only() -> None:
    """EB-04-012: empty-trigger handlers fire directly but not by queue lookup."""
    reset_event_state()
    source_uuid = uuid4()
    calls: list[str] = []

    def direct_only_handler(event: Event, _: UUID) -> Event:
        calls.append(event.phase.value)
        event.status_message = "direct handler ran"
        return event

    handler = EventHandler(
        source_entity_uuid=source_uuid,
        name="Direct-only empty-trigger handler",
        trigger_conditions=[],
        event_processor=direct_only_handler,
    )
    event = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
    )

    direct_result = handler(event, source_uuid)
    assert direct_result is event
    assert calls == ["declaration"]
    assert event.status_message == "direct handler ran"

    event.status_message = None
    calls.clear()
    EventQueue.add_event_handler(handler)
    execution = event.phase_to(EventPhase.EXECUTION)

    assert calls == []
    assert execution.status_message is None
    assert EventQueue._event_handlers[handler.uuid] is handler
    assert EventQueue._event_handlers_by_source_entity_uuid[source_uuid] == [handler]
    assert EventQueue.get_events_by_phase(EventPhase.EXECUTION) == [execution]


def test_eb_04_013_event_stream_cursors_are_append_stable_not_timestamp_sorted() -> None:
    """EB-04-013: raw event cursors are append-stable even with older timestamps."""
    reset_event_state()
    first = Event(source_entity_uuid=uuid4(), event_type=EventType.BASE_ACTION)
    second = Event(source_entity_uuid=uuid4(), event_type=EventType.BASE_ACTION)
    cursor = EventQueue.event_cursor()

    late_backdated = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.BASE_ACTION,
        timestamp=datetime.now(UTC) - timedelta(days=1),
        use_register=False,
    )
    EventQueue.register(late_backdated)

    since_cursor = EventQueue.iter_events_since(cursor)
    chronological = EventQueue.get_events_chronological()

    assert [event for _, event in since_cursor] == [late_backdated]
    assert EventQueue.get_event_index(late_backdated.uuid) == cursor
    assert EventQueue.event_cursor() == cursor + 1
    assert EventQueue._all_events == [first, second, late_backdated]
    assert chronological[0] is late_backdated
    assert chronological[-2:] == [first, second]


if __name__ == "__main__":
    test_eb_04_001_phase_to_creates_versions_with_one_lineage()
    test_eb_04_002_handlers_match_exact_phase_source_and_target()
    test_eb_04_003_completion_skips_handlers_but_not_passive_callbacks()
    test_eb_04_004_pre_completion_callbacks_can_attach_children()
    test_eb_04_005_completion_collects_child_combat_logs_top_level_only()
    test_eb_04_006_cancel_posts_cancel_phase_and_stops_handler_chain()
    test_eb_04_007_push_combat_log_bypasses_event_storage()
    test_eb_04_008_completion_log_callback_runs_before_completion_storage()
    test_eb_04_009_passive_callback_exceptions_do_not_block_storage()
    test_eb_04_010_missing_parent_event_does_not_block_child_storage()
    test_eb_04_011_late_children_do_not_recompute_completed_parent_lineages()
    test_eb_04_012_empty_trigger_handlers_are_direct_only()
    test_eb_04_013_event_stream_cursors_are_append_stable_not_timestamp_sorted()
    print("PASS: engine book event lifecycle tests")
