"""Manual Chapter 05 checks for event lifecycle and handler dispatch."""

from uuid import UUID, uuid4

from dnd.core.base_object import BaseObject
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)


def reset_event_state() -> None:
    """Clear global event state touched by this chapter's examples."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()


def test_phase_versions_share_one_lineage() -> None:
    """Phase transitions create separate versions under one lineage."""
    reset_event_state()
    source_id = uuid4()
    target_id = uuid4()

    declaration = Event(
        source_entity_uuid=source_id,
        target_entity_uuid=target_id,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        status_message="hero declares an action",
    )
    execution = declaration.phase_to(
        EventPhase.EXECUTION,
        status_message="the action is being checked",
    )
    effect = execution.phase_to(
        EventPhase.EFFECT,
        status_message="the action changes state",
    )
    completion = effect.phase_to(
        EventPhase.COMPLETION,
        status_message="the action is complete",
    )

    versions = [declaration, execution, effect, completion]

    assert [event.phase for event in versions] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    assert len({event.uuid for event in versions}) == 4
    assert {event.lineage_uuid for event in versions} == {declaration.lineage_uuid}
    assert EventQueue.get_event_history(completion.uuid) == versions


def test_passive_observation_sees_stored_completion() -> None:
    """Passive callbacks observe every stored phase including completion."""
    reset_event_state()
    source_id = uuid4()
    target_id = uuid4()
    observed_phases = []

    def observe(event: Event) -> None:
        observed_phases.append(event.phase)

    EventQueue.add_on_event_callback(observe)

    observed = Event(
        source_entity_uuid=source_id,
        target_entity_uuid=target_id,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
    )
    observed_completion = (
        observed.phase_to(EventPhase.EXECUTION)
        .phase_to(EventPhase.EFFECT)
        .phase_to(EventPhase.COMPLETION)
    )

    assert observed_completion.phase == EventPhase.COMPLETION
    assert observed_phases == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]


def test_triggered_handler_runs_before_completion() -> None:
    """A matching handler can mutate an execution-phase event."""
    reset_event_state()
    source_id = uuid4()
    target_id = uuid4()
    calls = []

    def mark_execution(event: Event, handler_source_id: UUID) -> Event:
        calls.append(event.status_message or "")
        event.status_message = "handler checked execution"
        return event

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_id,
            name="Execution checker",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.BASE_ACTION,
                    event_phase=EventPhase.EXECUTION,
                    event_source_entity_uuid=source_id,
                    event_target_entity_uuid=target_id,
                )
            ],
            event_processor=mark_execution,
        )
    )

    handler_declaration = Event(
        source_entity_uuid=source_id,
        target_entity_uuid=target_id,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        status_message="before handler",
    )
    handler_execution = handler_declaration.phase_to(EventPhase.EXECUTION)

    assert calls == ["before handler"]
    assert handler_execution.status_message == "handler checked execution"


def test_completion_skips_event_handlers() -> None:
    """Completion is stored but does not dispatch EventHandlers."""
    reset_event_state()
    source_id = uuid4()
    target_id = uuid4()
    completion_calls = []

    def completion_handler(event: Event, handler_source_id: UUID) -> Event:
        completion_calls.append(event.phase)
        return event

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_id,
            name="Completion checker",
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
        source_entity_uuid=source_id,
        target_entity_uuid=target_id,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
    )
    completed = (
        event.phase_to(EventPhase.EXECUTION)
        .phase_to(EventPhase.EFFECT)
        .phase_to(EventPhase.COMPLETION)
    )

    assert completed.phase == EventPhase.COMPLETION
    assert completion_calls == []


def test_cancellation_posts_cancel_phase_and_stops_later_handlers() -> None:
    """Canceling from a handler records CANCEL and stops later handlers."""
    reset_event_state()
    source_id = uuid4()
    cancel_calls = []

    def canceling_handler(event: Event, handler_source_id: UUID) -> Event:
        cancel_calls.append("canceling")
        return event.cancel(status_message="blocked by handler")

    def later_handler(event: Event, handler_source_id: UUID) -> Event:
        cancel_calls.append("later")
        return event

    execution_trigger = Trigger(
        event_type=EventType.BASE_ACTION,
        event_phase=EventPhase.EXECUTION,
    )
    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_id,
            name="Canceling handler",
            trigger_conditions=[execution_trigger],
            event_processor=canceling_handler,
        )
    )
    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_id,
            name="Later handler",
            trigger_conditions=[execution_trigger],
            event_processor=later_handler,
        )
    )

    blocked = Event(
        source_entity_uuid=source_id,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
    ).phase_to(EventPhase.EXECUTION)

    assert cancel_calls == ["canceling"]
    assert blocked.canceled is True
    assert blocked.phase == EventPhase.CANCEL
    assert blocked.status_message == "blocked by handler"
