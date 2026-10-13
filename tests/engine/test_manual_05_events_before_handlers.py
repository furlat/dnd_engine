"""Focused checks for event lifecycle and handler dispatch."""

from uuid import UUID, uuid4

from dnd.core.content.runtime import HandlerDispatchOutcome
from dnd.core.base_object import BaseObject
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    SpatialChangeEvent,
    SpatialChangeType,
    SpatialHandler,
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


def test_filtered_and_legacy_handlers_keep_native_order_and_lifetime() -> None:
    """Source/target filters, reordered registrations and legacy removal compose."""
    reset_event_state()
    source, target, remote = uuid4(), uuid4(), uuid4()

    def handler(label, *, source_filter=None, target_filter=None, enabled=True):
        def append(event, _source):
            return event.with_updates(status_message=(event.status_message or "") + label)
        return EventHandler(source_entity_uuid=source, name=label, enabled=enabled,
            trigger_conditions=[Trigger(event_type=EventType.BASE_ACTION,
                event_phase=EventPhase.EXECUTION, event_source_entity_uuid=source_filter,
                event_target_entity_uuid=target_filter)], event_processor=append)

    by_source = handler("S", source_filter=source)
    by_target = handler("T", target_filter=target)
    both = handler("B", source_filter=source, target_filter=target)
    simple = handler("G")
    absent = handler("X", source_filter=remote)
    disabled = handler("D", target_filter=target, enabled=False)
    for row in (by_source, simple, by_target, both, absent, disabled):
        EventQueue.add_event_handler(row)
    legacy = handler("L", source_filter=source)
    EventQueue.add_spatial_handler(legacy, {(10, 10)})

    def execute():
        return Event(source_entity_uuid=source, target_entity_uuid=target,
            event_type=EventType.BASE_ACTION, phase=EventPhase.DECLARATION,
            status_message="").phase_to(EventPhase.EXECUTION).status_message

    assert execute() == "GSTBL"
    EventQueue.set_event_handler_order(tuple(reversed(EventQueue.event_handler_order())))
    assert execute() == "GLBTS"
    assert EventQueue.remove_spatial_handler(legacy.uuid)
    EventQueue.remove_event_handler(by_target)
    assert execute() == "GBS"


def test_multi_position_dispatch_preserves_local_global_local_order() -> None:
    """A global consequence stays between the first and second support's rules."""
    reset_event_state()
    source = uuid4()

    def append(label):
        def process(event, _source):
            return event.with_updates(status_message=(event.status_message or "") + label)
        return process

    for label, positions in (("A", {(0, 0)}), ("B", {(1, 0)})):
        EventQueue.add_spatial_handler(SpatialHandler(source_entity_uuid=source,
            name=label, positions=positions, event_type=EventType.SPATIAL_OBJECT_CHANGED,
            event_phase=EventPhase.EFFECT, event_processor=append(label)))
    EventQueue.add_event_handler(EventHandler(source_entity_uuid=source, name="global",
        trigger_conditions=[Trigger(event_type=EventType.SPATIAL_OBJECT_CHANGED,
            event_phase=EventPhase.EFFECT, event_source_entity_uuid=source)],
        event_processor=append("G")))
    event = SpatialChangeEvent(source_entity_uuid=source, event_type=EventType.SPATIAL_OBJECT_CHANGED,
        change_type=SpatialChangeType.OBJECT_CHANGED, position=(0, 0), old_position=(1, 0),
        status_message="", phase=EventPhase.DECLARATION)
    completed = event.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
    assert completed.status_message == "AGB"


def test_spatial_legacy_handlers_keep_global_filters_and_nonpositioned_fallback() -> None:
    """Local rules, global reactions and legacy no-position events keep their order."""
    reset_event_state()
    source, target, other = uuid4(), uuid4(), uuid4()

    def handler(label, *, source_filter=None, target_filter=None, enabled=True):
        def append(event, _source):
            return event.with_updates(status_message=(event.status_message or "") + label)
        return EventHandler(source_entity_uuid=source, name=label, enabled=enabled,
            trigger_conditions=[Trigger(event_type=EventType.SPATIAL_OBJECT_CHANGED,
                event_phase=EventPhase.EFFECT, event_source_entity_uuid=source_filter,
                event_target_entity_uuid=target_filter)], event_processor=append)

    first, second, remote = handler("A"), handler("B"), handler("R")
    for row, position in ((first, (0, 0)), (second, (1, 0)), (remote, (9, 9))):
        EventQueue.add_spatial_handler(row, {position}, EventType.SPATIAL_OBJECT_CHANGED)
    for row in (handler("G"), handler("F", source_filter=source),
                handler("T", target_filter=target),
                handler("M", source_filter=source, target_filter=target),
                handler("X", source_filter=other), handler("D", enabled=False)):
        EventQueue.add_event_handler(row)

    def execute(positioned=True):
        common = dict(source_entity_uuid=source, target_entity_uuid=target,
            event_type=EventType.SPATIAL_OBJECT_CHANGED, phase=EventPhase.DECLARATION,
            status_message="")
        event = (SpatialChangeEvent(**common, change_type=SpatialChangeType.OBJECT_CHANGED,
            position=(0, 0), old_position=(1, 0)) if positioned else Event(**common))
        return event.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).status_message

    assert execute() == "AGFTMB"
    assert EventQueue.update_spatial_handler_positions(first.uuid, {(9, 9)})
    assert execute() == "GFTMB"
    assert EventQueue.remove_spatial_handler(second.uuid)
    assert execute() == "GFTM"
    assert execute(positioned=False) == "GARFTM"


def test_dispatch_observers_added_during_handlers_keep_indices_and_child_order() -> None:
    """Late passive subscribers see the current dispatch and prior cursor gaps."""
    reset_event_state()
    source = uuid4()
    evidence = []
    executed = []

    def process(event, _source):
        executed.append(event.status_message)
        if event.status_message in ("subscribe", "child"):
            EventQueue.add_on_handler_dispatch_callback(evidence.append)
        if event.status_message == "parent":
            Event(source_entity_uuid=source, event_type=EventType.BASE_ACTION,
                phase=EventPhase.DECLARATION, status_message="child",
                parent_event=event.uuid).phase_to(EventPhase.EXECUTION)
        return event

    EventQueue.add_event_handler(EventHandler(source_entity_uuid=source,
        name="Native no-op or child emitter",
        trigger_conditions=[Trigger(event_type=EventType.BASE_ACTION,
            event_phase=EventPhase.EXECUTION)], event_processor=process))

    def execute(label):
        return Event(source_entity_uuid=source, event_type=EventType.BASE_ACTION,
            phase=EventPhase.DECLARATION,
            status_message=label).phase_to(EventPhase.EXECUTION)

    silent = execute("silent")
    subscribed = execute("subscribe")
    EventQueue.remove_on_handler_dispatch_callback(evidence.append)
    silent_again = execute("silent again")
    parent = execute("parent")

    assert executed == ["silent", "subscribe", "silent again", "parent", "child"]
    assert [row.dispatch_index for row in evidence] == [1, 3, 4]
    assert [row.outcome for row in evidence] == [HandlerDispatchOutcome.NO_EFFECT,
        HandlerDispatchOutcome.NO_EFFECT, HandlerDispatchOutcome.EMITTED_EVENTS]
    assert evidence[0].event_uuid == str(subscribed.uuid)
    assert evidence[-1].event_uuid == str(parent.uuid)
    children = parent.get_children_events()
    assert len(children) == 2
    assert all(child.parent_lineage == parent.lineage_uuid for child in children)
    assert evidence[1].event_uuid == str(children[-1].uuid)
    assert all(not event.effective_handler_presentations
        for event in (silent, subscribed, silent_again, parent, *children))
