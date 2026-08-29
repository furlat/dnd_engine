"""Engine semantic tests for event lifecycle behavior."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from dnd.core.base_object import BaseObject
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.encounters.encounter import Encounter


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


def test_eb_04_003_completion_skips_handlers_and_is_stored_in_the_journal() -> None:
    """EB-04-003: completion is stored, but not handler-dispatched."""
    reset_event_state()
    source_uuid = uuid4()
    completion_handler_calls = 0
    cursor = EventQueue.event_cursor()

    def completion_handler(event: Event, _: UUID) -> Event:
        nonlocal completion_handler_calls
        completion_handler_calls += 1
        return event

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
    assert [
        event.phase
        for _, event in EventQueue.iter_events_since(cursor)
        if event.lineage_uuid == completion.lineage_uuid
    ] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]


def test_eb_04_005_completion_collects_child_combat_logs_top_level_only() -> None:
    """EB-04-005: completion builds parent logs from completed child logs."""
    reset_event_state()
    source_uuid = uuid4()

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
    assert parent_completion.combat_log.compact == "Parent log"
    assert [entry.compact for entry in parent_completion.combat_log.sub_entries] == [
        "Child log",
    ]


def test_terminal_metadata_uses_stored_parentage_for_detached_completion() -> None:
    """A copied proposal still discovers children through the stored journal."""
    reset_event_state()
    source_uuid = uuid4()
    parent = LoggableEvent(
        name="Detached parent",
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        status_message="Detached parent log",
    )
    effect = parent.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
    detached_effect = effect.model_copy(deep=True)
    child = LoggableEvent(
        name="Stored child",
        source_entity_uuid=source_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.DECLARATION,
        status_message="Stored child log",
        parent_event=effect.uuid,
    )
    child_completion = child.phase_to(EventPhase.COMPLETION)

    completion = detached_effect.phase_to(EventPhase.COMPLETION)

    assert child.lineage_uuid in completion.children_lineages
    assert completion.get_children_events() == [child_completion]
    assert completion.combat_log is not None
    assert [entry.compact for entry in completion.combat_log.sub_entries] == [
        "Stored child log",
    ]


def test_canceled_terminal_aggregates_completed_reaction_children() -> None:
    """Cancellation preserves completed reaction descendants in its log tree."""
    reset_event_state()
    source_uuid = uuid4()
    parent = LoggableEvent(
        name="Interrupted parent",
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        status_message="Interrupted parent log",
    )
    effect = parent.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
    reaction = LoggableEvent(
        name="Completed reaction",
        source_entity_uuid=source_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.DECLARATION,
        status_message="Reaction log",
        parent_event=effect.uuid,
    )
    reaction_completion = reaction.phase_to(EventPhase.COMPLETION)

    cancel_cursor = EventQueue.event_cursor()
    canceled = effect.cancel(status_message="Interrupted after reaction")
    repeated = effect.cancel(status_message="Repeated cancellation")

    assert canceled.phase is EventPhase.CANCEL
    assert repeated is canceled
    assert EventQueue.event_cursor() == cancel_cursor + 1
    cancel_rows = [
        event
        for _, event in EventQueue.iter_events_since(cancel_cursor)
        if event.lineage_uuid == canceled.lineage_uuid
        and event.phase is EventPhase.CANCEL
    ]
    assert cancel_rows == [canceled]
    assert reaction.lineage_uuid in canceled.children_lineages
    assert canceled.get_children_events() == [reaction_completion]
    assert canceled.combat_log is not None
    assert [entry.compact for entry in canceled.combat_log.sub_entries] == [
        "Reaction log",
    ]


def test_terminal_resolution_is_idempotent_for_one_event_lineage() -> None:
    """A second completion attempt returns the stored terminal unchanged."""
    reset_event_state()

    class ResolvingEvent(Event):
        def resolve_sub_events(self) -> None:
            Event(
                source_entity_uuid=self.source_entity_uuid,
                event_type=EventType.TRIGGER_EVENT,
                phase=EventPhase.DECLARATION,
                parent_event=self.uuid,
            ).phase_to(EventPhase.COMPLETION)

    event = ResolvingEvent(
        source_entity_uuid=uuid4(),
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
    )
    effect = event.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
    completion = effect.phase_to(EventPhase.COMPLETION)
    cursor = EventQueue.event_cursor()

    repeated = effect.phase_to(EventPhase.COMPLETION)

    assert repeated is completion
    assert EventQueue.event_cursor() == cursor
    assert len([
        stored
        for stored in EventQueue.get_event_history(completion.uuid)
        if stored.phase is EventPhase.COMPLETION
    ]) == 1


def test_unregistered_validation_cancellation_is_detached_and_silent() -> None:
    """Validation cancellation does not publish a phantom terminal or log."""
    reset_event_state()
    source_uuid = uuid4()

    def canceling_validator(event: Event, _: UUID) -> Event:
        return event.cancel(status_message="rejected during validation")

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_uuid,
            name="Validation cancellation",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.BASE_ACTION,
                    event_phase=EventPhase.DECLARATION,
                )
            ],
            event_processor=canceling_validator,
            validation_only=True,
        )
    )

    proposal = LoggableEvent(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        use_register=False,
    )
    cursor = EventQueue.event_cursor()
    canceled = EventQueue.preflight(proposal)

    assert canceled.canceled is True
    assert canceled.phase is EventPhase.CANCEL
    assert canceled.use_register is False
    assert EventQueue.get_event_by_uuid(canceled.uuid) is None
    assert EventQueue.event_cursor() == cursor


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

    event = LoggableEvent(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        status_message="handler cancellation",
    )
    cancel_cursor = EventQueue.event_cursor()
    canceled = event.phase_to(EventPhase.EXECUTION)
    repeated = canceled.cancel(status_message="Repeated handler cancellation")

    assert calls == ["canceling"]
    assert repeated is canceled
    assert EventQueue.event_cursor() == cancel_cursor + 2
    cancel_rows = [
        stored
        for _, stored in EventQueue.iter_events_since(cancel_cursor)
        if stored.lineage_uuid == canceled.lineage_uuid
        and stored.phase is EventPhase.CANCEL
    ]
    assert cancel_rows == [canceled]
    assert canceled.canceled is True
    assert canceled.phase == EventPhase.CANCEL
    assert canceled.status_message == "blocked by handler"
    assert EventQueue.get_events_by_phase(EventPhase.CANCEL)


def test_eb_04_007_terminal_log_is_attached_to_the_real_terminal_fact() -> None:
    """EB-04-007: logs are read from the real terminal fact, never a fake event."""
    reset_event_state()
    source_uuid = uuid4()
    cursor = EventQueue.event_cursor()
    event = LoggableEvent(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        status_message="real terminal",
    )
    execution = event.phase_to(EventPhase.EXECUTION)
    terminal = execution.phase_to(EventPhase.COMPLETION)

    assert terminal.combat_log is not None
    assert terminal.combat_log.compact == "real terminal"
    assert [stored for _, stored in EventQueue.iter_events_since(cursor)] == [
        event,
        execution,
        terminal,
    ]
    assert EventQueue.get_event_by_uuid(terminal.uuid) is terminal


def test_eb_04_008_completion_terminal_is_stored_with_its_log() -> None:
    """EB-04-008: the stored completion owns its generated log."""
    reset_event_state()
    source_uuid = uuid4()
    cursor = EventQueue.event_cursor()

    declaration = LoggableEvent(
        name="Completion callback ordering",
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        status_message="Callback ordering log",
    )
    effect = declaration.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
    completion = effect.phase_to(EventPhase.COMPLETION)

    assert completion.uuid != effect.uuid
    assert EventQueue.get_event_by_uuid(completion.uuid) is completion
    assert completion.combat_log is not None
    assert [stored for _, stored in EventQueue.iter_events_since(cursor)][-1] is completion


def test_round_end_cancellation_closes_before_round_increment_and_round_start() -> None:
    """A canceled round end is still terminal before the next round starts."""
    reset_event_state()
    encounter = Encounter(name="Round lifecycle", source_entity_uuid=uuid4())
    encounter.round_number = 1

    def cancel_round_end(event: Event, _: UUID) -> Event:
        return event.cancel(status_message="round end veto")

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=encounter.uuid,
            name="Cancel round end",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ROUND_END,
                    event_phase=EventPhase.EXECUTION,
                ),
            ],
            event_processor=cancel_round_end,
        ),
    )
    cursor = EventQueue.event_cursor()

    encounter._advance_round()

    assert encounter.round_number == 2
    events = [event for _, event in EventQueue.iter_events_since(cursor)]
    round_end = next(
        event
        for event in events
        if event.event_type is EventType.ROUND_END
        and event.phase is EventPhase.CANCEL
    )
    assert round_end.phase is EventPhase.CANCEL
    assert round_end.status_message == "round end veto"
    terminal_index = events.index(round_end)
    round_start_index = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.ROUND_START
    )
    assert terminal_index < round_start_index


def test_encounter_combat_log_projects_root_terminal_facts_inside_its_cursor_window() -> None:
    """Encounter logs read real terminal facts without a mutable log sink."""
    reset_event_state()
    encounter = Encounter(name="Journal projection", source_entity_uuid=uuid4())
    encounter.combat_log_source_start = EventQueue.event_cursor()

    root = LoggableEvent(
        source_entity_uuid=uuid4(),
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        status_message="inside window",
    )
    child = LoggableEvent(
        source_entity_uuid=root.source_entity_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.DECLARATION,
        parent_event=root.uuid,
        status_message="child is nested",
    )
    child.phase_to(EventPhase.COMPLETION)
    terminal = root.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.COMPLETION)
    encounter.combat_log_source_end = EventQueue.event_cursor()

    outside = LoggableEvent(
        source_entity_uuid=uuid4(),
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        status_message="outside window",
    )
    outside.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.COMPLETION)

    assert terminal.combat_log is not None
    assert encounter.combat_log == [terminal.combat_log]
    assert encounter.combat_log[0].sub_entries
    assert encounter.get_combat_log() == encounter.combat_log


def test_eb_04_010_missing_parent_event_is_rejected() -> None:
    """EB-04-010: a child cannot enter the journal without its parent."""
    reset_event_state()
    source_uuid = uuid4()
    missing_parent_uuid = uuid4()

    with pytest.raises(ValueError, match="missing parent"):
        Event(
            name="Orphan child event",
            source_entity_uuid=source_uuid,
            event_type=EventType.TRIGGER_EVENT,
            phase=EventPhase.DECLARATION,
            parent_event=missing_parent_uuid,
        )


def test_eb_04_011_late_children_are_rejected() -> None:
    """EB-04-011: a completed root cannot accept a late child."""
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

    with pytest.raises(ValueError, match="closed lineage"):
        Event(
            name="Late child",
            source_entity_uuid=source_uuid,
            event_type=EventType.TRIGGER_EVENT,
            phase=EventPhase.DECLARATION,
            parent_event=parent_completion.uuid,
        )

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
    first = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
    )
    first.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(
        EventPhase.COMPLETION
    )
    second = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
    )
    second.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(
        EventPhase.COMPLETION
    )
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
    assert EventQueue._all_events[cursor:] == [late_backdated]
    assert EventQueue._all_events[0] is first
    assert second in EventQueue._all_events
    assert chronological[0] is late_backdated
    assert first in chronological
    assert second in chronological


def test_strict_queue_admits_one_exact_root_and_its_descendants() -> None:
    """Every stored member belongs to one exact open causal tree."""
    reset_event_state()

    class OtherEvent(Event):
        pass

    source_uuid = uuid4()
    root = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.DECLARATION,
        use_register=False,
    )
    EventQueue.register(root)

    with pytest.raises(ValueError, match="exact .*class"):
        EventQueue.register(OtherEvent(
            source_entity_uuid=source_uuid,
            event_type=EventType.TRIGGER_EVENT,
            phase=EventPhase.EXECUTION,
            lineage_uuid=root.lineage_uuid,
            use_register=False,
        ))
    with pytest.raises(ValueError, match="exact class and lineage"):
        EventQueue.register(Event(
            source_entity_uuid=source_uuid,
            event_type=EventType.TRIGGER_EVENT,
            phase=EventPhase.DECLARATION,
            use_register=False,
        ))

    child = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EFFECT,
        parent_event=root.uuid,
        use_register=False,
    )
    EventQueue.register(child)
    with pytest.raises(ValueError, match="root lineage must remain parentless"):
        EventQueue.register(Event(
            source_entity_uuid=source_uuid,
            event_type=EventType.TRIGGER_EVENT,
            phase=EventPhase.EXECUTION,
            lineage_uuid=root.lineage_uuid,
            parent_event=child.uuid,
            use_register=False,
        ))
    grandchild = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.EXECUTION,
        parent_event=child.uuid,
        use_register=False,
    )
    EventQueue.register(grandchild)
    grandchild_terminal = EventQueue.register(
        grandchild.phase_to(EventPhase.COMPLETION)
    )
    child_terminal = EventQueue.register(child.phase_to(EventPhase.COMPLETION))

    assert EventQueue.next_committed_tree(0) is None
    root_terminal = EventQueue.register(root.phase_to(EventPhase.COMPLETION))
    assert EventQueue.next_committed_tree(0) == (
        root,
        child,
        grandchild,
        grandchild_terminal,
        child_terminal,
        root_terminal,
    )

    with pytest.raises(ValueError, match="closed lineage"):
        EventQueue.register(Event(
            source_entity_uuid=source_uuid,
            event_type=EventType.TRIGGER_EVENT,
            parent_event=root_terminal.uuid,
            use_register=False,
        ))


def test_strict_queue_rejects_parent_cycles_and_incomplete_root_interleaving() -> None:
    """A failed or incomplete root cannot be bypassed by another causal tree."""
    reset_event_state()
    source_uuid = uuid4()
    root = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.TRIGGER_EVENT,
        use_register=False,
    )
    EventQueue.register(root)

    with pytest.raises(ValueError, match="exact class and lineage"):
        EventQueue.register(Event(
            source_entity_uuid=uuid4(),
            event_type=EventType.TRIGGER_EVENT,
            use_register=False,
        ))

    child = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.TRIGGER_EVENT,
        parent_event=root.uuid,
        use_register=False,
    )
    EventQueue.register(child)
    root.parent_event = child.uuid
    with pytest.raises(ValueError, match="parent cycle"):
        EventQueue.register(Event(
            source_entity_uuid=source_uuid,
            event_type=EventType.TRIGGER_EVENT,
            parent_event=child.uuid,
            use_register=False,
        ))


def test_strict_queue_cancel_closes_once_and_reset_changes_generation() -> None:
    """A root cancellation is its final slot and reset is the recovery boundary."""
    reset_event_state()
    generation = EventQueue.generation_id()
    root = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
    )
    terminal = root.phase_to(EventPhase.CANCEL, status_message="stop")

    assert EventQueue.next_committed_tree(0) == (root, terminal)
    assert terminal.canceled is True
    assert terminal.canceled_from_phase is EventPhase.DECLARATION
    with pytest.raises(ValueError, match="non-inert terminal"):
        EventQueue.register(terminal.model_copy(update={"uuid": uuid4()}))
    with pytest.raises(ValueError, match="after its terminal"):
        EventQueue.register(root.model_copy(update={
            "uuid": uuid4(),
            "phase": EventPhase.EFFECT,
            "use_register": False,
        }))

    fresh = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        use_register=False,
    )
    EventQueue.register(fresh)
    EventQueue.register(fresh.phase_to(EventPhase.COMPLETION))

    EventQueue.reset()
    assert EventQueue.generation_id() != generation
    assert EventQueue.event_cursor() == 0


def test_inert_fact_classes_can_only_form_one_completion_slot_tree() -> None:
    """Reviewed inert types cannot bypass their completion-only contract."""
    reset_event_state()

    class InertEvent(Event):
        inert_terminal_fact = True

    declaration = InertEvent(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.DECLARATION,
        use_register=False,
    )
    with pytest.raises(ValueError, match="completion-only"):
        EventQueue.register(declaration)

    canceled = declaration.model_copy(update={
        "uuid": uuid4(),
        "phase": EventPhase.CANCEL,
        "canceled": True,
        "canceled_from_phase": EventPhase.DECLARATION,
    })
    with pytest.raises(ValueError, match="completion-only"):
        EventQueue.register(canceled)

    completion = declaration.model_copy(update={
        "uuid": uuid4(),
        "phase": EventPhase.COMPLETION,
    })
    committed = EventQueue.publish_inert_terminal_fact(completion)
    assert EventQueue.next_committed_tree(0) == (committed,)

    EventQueue.reset()
    root = Event(
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        use_register=False,
    )
    EventQueue.register(root)
    parented_declaration = declaration.model_copy(update={
        "uuid": uuid4(),
        "lineage_uuid": uuid4(),
        "parent_event": root.uuid,
    })
    with pytest.raises(ValueError, match="completion-only"):
        EventQueue.register(parented_declaration)
    with pytest.raises(ValueError, match="completion-only"):
        EventQueue.register(parented_declaration.model_copy(update={
            "uuid": uuid4(),
            "phase": EventPhase.CANCEL,
            "canceled": True,
            "canceled_from_phase": EventPhase.DECLARATION,
        }))

    parented_completion = parented_declaration.model_copy(update={
        "uuid": uuid4(),
        "phase": EventPhase.COMPLETION,
    })
    EventQueue.register(parented_completion)
    root_terminal = EventQueue.register(root.phase_to(EventPhase.COMPLETION))
    assert EventQueue.next_committed_tree(0) == (
        root,
        parented_completion,
        root_terminal,
    )


if __name__ == "__main__":
    test_eb_04_001_phase_to_creates_versions_with_one_lineage()
    test_eb_04_002_handlers_match_exact_phase_source_and_target()
    test_eb_04_003_completion_skips_handlers_and_is_stored_in_the_journal()
    test_eb_04_005_completion_collects_child_combat_logs_top_level_only()
    test_eb_04_006_cancel_posts_cancel_phase_and_stops_handler_chain()
    test_eb_04_007_terminal_log_is_attached_to_the_real_terminal_fact()
    test_eb_04_008_completion_terminal_is_stored_with_its_log()
    test_eb_04_010_missing_parent_event_does_not_block_child_storage()
    test_eb_04_011_late_children_do_not_recompute_completed_parent_lineages()
    test_eb_04_012_empty_trigger_handlers_are_direct_only()
    test_eb_04_013_event_stream_cursors_are_append_stable_not_timestamp_sorted()
    print("PASS: engine book event lifecycle tests")
