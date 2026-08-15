"""Tutorial tests for event records, phases, lineage, and completion logs."""

from uuid import uuid4

from dnd.core.base_object import BaseObject
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
)


def reset_event_state() -> None:
    """Clear global event state touched by these event lifecycle examples."""
    EventQueue.reset()
    BaseObject._registry.clear()
    EventQueue.set_combat_log_callback(None)


class TutorialLogEvent(Event):
    """Focused event subclass that can generate a completion combat log."""

    event_type: EventType = EventType.BASE_ACTION

    def generate_combat_log(self) -> CombatLogEntry:
        """Build a compact log entry from fields stored on the event."""
        return CombatLogEntry(
            entry_type=CombatLogEntryType.ACTION,
            source_name=self.source_entity_name or "Unknown",
            source_uuid=str(self.source_entity_uuid),
            target_name=self.target_entity_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else None,
            compact=f"{self.source_entity_name or 'Unknown'} resolves {self.name}",
            verbose=f"{self.source_entity_name or 'Unknown'} resolves {self.name}",
            detailed=f"{self.source_entity_name or 'Unknown'} resolves {self.name}",
            success=not self.canceled,
        )


def test_first_event_example_prints_visible_lineage_history(capsys) -> None:
    """One event lineage prints phase history, status, and queue lookup state."""
    reset_event_state()

    hero_id = uuid4()
    target_id = uuid4()
    declaration = Event(
        name="Open Door",
        source_entity_uuid=hero_id,
        target_entity_uuid=target_id,
        event_type=EventType.BASE_ACTION,
    )
    execution = declaration.phase_to(EventPhase.EXECUTION)
    effect = execution.phase_to(EventPhase.EFFECT, status_message="Door opens")
    completion = effect.phase_to(EventPhase.COMPLETION, status_message="Done")

    history = EventQueue.get_event_history(completion.uuid)
    phase_text = " -> ".join(event.phase.value for event in history)
    lookup_state = (
        "registered"
        if EventQueue.get_event_by_uuid(completion.uuid) is completion
        else "missing"
    )
    readout_lines = [
        f"event: {completion.name}",
        f"type: {completion.event_type.value}",
        f"phase history: {phase_text}",
        f"versions stored: {len(history)}",
        f"lineages stored: {len({event.lineage_uuid for event in history})}",
        f"effect status: {effect.status_message}",
        f"completion status: {completion.status_message}",
        f"queue lookup: {lookup_state}",
    ]

    print("\n".join(readout_lines))

    expected_lines = [
        "event: Open Door",
        "type: base_action",
        "phase history: declaration -> execution -> effect -> completion",
        "versions stored: 4",
        "lineages stored: 1",
        "effect status: Door opens",
        "completion status: Done",
        "queue lookup: registered",
    ]
    assert readout_lines == expected_lines
    assert len({event.uuid for event in history}) == 4
    assert completion in EventQueue.get_events_by_phase(EventPhase.COMPLETION)
    assert capsys.readouterr().out.splitlines() == expected_lines


def test_event_phases_create_versions_with_one_lineage(capsys) -> None:
    """Each phase transition prints one lineage with indexed event versions."""
    reset_event_state()
    hero_id = uuid4()
    target_id = uuid4()

    declaration = Event(
        name="Open Door",
        source_entity_uuid=hero_id,
        target_entity_uuid=target_id,
        event_type=EventType.BASE_ACTION,
    )
    execution = declaration.phase_to(EventPhase.EXECUTION)
    effect = execution.phase_to(EventPhase.EFFECT, status_message="Door opens")
    completion = effect.phase_to(EventPhase.COMPLETION, status_message="Done")
    history = EventQueue.get_event_history(completion.uuid)

    assert declaration.phase == EventPhase.DECLARATION
    assert execution.phase == EventPhase.EXECUTION
    assert effect.phase == EventPhase.EFFECT
    assert completion.phase == EventPhase.COMPLETION

    assert {
        declaration.uuid,
        execution.uuid,
        effect.uuid,
        completion.uuid,
    } == {event.uuid for event in history}

    assert len({declaration.uuid, execution.uuid, effect.uuid, completion.uuid}) == 4
    assert {
        declaration.lineage_uuid,
        execution.lineage_uuid,
        effect.lineage_uuid,
        completion.lineage_uuid,
    } == {declaration.lineage_uuid}

    assert EventQueue.get_event_by_uuid(completion.uuid) is completion
    assert completion in EventQueue.get_events_by_type(EventType.BASE_ACTION)
    assert completion in EventQueue.get_events_by_phase(EventPhase.COMPLETION)
    assert completion in EventQueue.get_events_by_source(hero_id)
    assert completion in EventQueue.get_events_by_target(target_id)

    phase_lines = [
        f"history phases: {' -> '.join(event.phase.value for event in history)}",
        f"unique event versions: {len({event.uuid for event in history})}",
        f"single lineage: {len({event.lineage_uuid for event in history}) == 1}",
        (
            "type index contains completion: "
            f"{completion in EventQueue.get_events_by_type(EventType.BASE_ACTION)}"
        ),
        (
            "source index contains completion: "
            f"{completion in EventQueue.get_events_by_source(hero_id)}"
        ),
        (
            "target index contains completion: "
            f"{completion in EventQueue.get_events_by_target(target_id)}"
        ),
    ]

    print("\n".join(phase_lines))

    expected_phase_lines = [
        "history phases: declaration -> execution -> effect -> completion",
        "unique event versions: 4",
        "single lineage: True",
        "type index contains completion: True",
        "source index contains completion: True",
        "target index contains completion: True",
    ]
    assert phase_lines == expected_phase_lines
    assert capsys.readouterr().out.splitlines() == expected_phase_lines


def test_event_cancel_records_canceled_version_in_same_lineage(capsys) -> None:
    """Canceling an event prints the cancel-phase version and reason."""
    reset_event_state()
    hero_id = uuid4()

    declaration = Event(
        name="Locked Door",
        source_entity_uuid=hero_id,
        event_type=EventType.BASE_ACTION,
    )
    canceled = declaration.cancel(status_message="The door is locked")
    history = EventQueue.get_event_history(canceled.uuid)

    assert canceled.phase == EventPhase.CANCEL
    assert canceled.canceled is True
    assert canceled.status_message == "The door is locked"
    assert canceled.lineage_uuid == declaration.lineage_uuid
    assert [event.phase for event in history] == [
        EventPhase.DECLARATION,
        EventPhase.CANCEL,
    ]

    cancel_lines = [
        f"event: {canceled.name}",
        f"phase history: {' -> '.join(event.phase.value for event in history)}",
        f"canceled: {canceled.canceled}",
        f"reason: {canceled.status_message}",
        f"same lineage: {canceled.lineage_uuid == declaration.lineage_uuid}",
    ]

    print("\n".join(cancel_lines))

    expected_cancel_lines = [
        "event: Locked Door",
        "phase history: declaration -> cancel",
        "canceled: True",
        "reason: The door is locked",
        "same lineage: True",
    ]
    assert cancel_lines == expected_cancel_lines
    assert capsys.readouterr().out.splitlines() == expected_cancel_lines


def test_parent_child_events_resolve_stable_lineages_at_completion(capsys) -> None:
    """Completion prints resolved parent and child event-tree relationships."""
    reset_event_state()
    hero_id = uuid4()
    target_id = uuid4()

    parent = Event(
        name="Cast Simple Spell",
        source_entity_uuid=hero_id,
        target_entity_uuid=target_id,
        event_type=EventType.CAST_SPELL,
    )
    parent_execution = parent.phase_to(EventPhase.EXECUTION)

    child = Event(
        name="Spell Damage",
        source_entity_uuid=hero_id,
        target_entity_uuid=target_id,
        event_type=EventType.TAKE_DAMAGE,
        parent_event=parent_execution.uuid,
    )
    child_completion = child.phase_to(EventPhase.EXECUTION).phase_to(
        EventPhase.EFFECT
    ).phase_to(EventPhase.COMPLETION)

    parent_completion = parent_execution.phase_to(EventPhase.EFFECT).phase_to(
        EventPhase.COMPLETION
    )

    assert child_completion.parent_lineage == parent.lineage_uuid
    assert parent_completion.children_lineages == [child.lineage_uuid]
    assert parent_completion.get_children_events() == [child_completion]
    assert child_completion.get_parent_event() == parent_completion

    child_event_names = [
        event.name for event in parent_completion.get_children_events()
    ]
    parent_lines = [
        f"parent event: {parent_completion.name}",
        f"child event: {child_completion.name}",
        (
            "child parent lineage set: "
            f"{child_completion.parent_lineage == parent.lineage_uuid}"
        ),
        f"parent child lineages: {len(parent_completion.children_lineages)}",
        f"resolved child names: {child_event_names}",
        f"resolved parent name: {child_completion.get_parent_event().name}",
    ]

    print("\n".join(parent_lines))

    expected_parent_lines = [
        "parent event: Cast Simple Spell",
        "child event: Spell Damage",
        "child parent lineage set: True",
        "parent child lineages: 1",
        "resolved child names: ['Spell Damage']",
        "resolved parent name: Cast Simple Spell",
    ]
    assert parent_lines == expected_parent_lines
    assert capsys.readouterr().out.splitlines() == expected_parent_lines


def test_completion_generates_top_level_log_with_child_sub_entries(capsys) -> None:
    """Completed top-level events print parent and child combat-log output."""
    reset_event_state()
    hero_id = uuid4()
    target_id = uuid4()
    completed_top_level_events: list[Event] = []

    EventQueue.set_combat_log_callback(completed_top_level_events.append)

    parent = TutorialLogEvent(
        name="Training Action",
        source_entity_uuid=hero_id,
        source_entity_name="Hero",
        target_entity_uuid=target_id,
        target_entity_name="Training Dummy",
    )
    parent_execution = parent.phase_to(EventPhase.EXECUTION)

    child = TutorialLogEvent(
        name="Training Effect",
        source_entity_uuid=hero_id,
        source_entity_name="Hero",
        target_entity_uuid=target_id,
        target_entity_name="Training Dummy",
        parent_event=parent_execution.uuid,
    )
    child.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(
        EventPhase.COMPLETION
    )

    parent_completion = parent_execution.phase_to(EventPhase.EFFECT).phase_to(
        EventPhase.COMPLETION
    )

    assert len(completed_top_level_events) == 1
    assert completed_top_level_events[0].lineage_uuid == parent.lineage_uuid
    assert parent_completion.combat_log is not None
    assert parent_completion.combat_log.compact == "Hero resolves Training Action"
    assert [
        sub_entry.compact for sub_entry in parent_completion.combat_log.sub_entries
    ] == ["Hero resolves Training Effect"]

    child_log_lines = [
        sub_entry.compact for sub_entry in parent_completion.combat_log.sub_entries
    ]
    log_lines = [
        f"callback events: {len(completed_top_level_events)}",
        f"top-level log: {parent_completion.combat_log.compact}",
        f"child logs: {child_log_lines}",
        (
            "callback lineage match: "
            f"{completed_top_level_events[0].lineage_uuid == parent.lineage_uuid}"
        ),
    ]

    print("\n".join(log_lines))

    expected_log_lines = [
        "callback events: 1",
        "top-level log: Hero resolves Training Action",
        "child logs: ['Hero resolves Training Effect']",
        "callback lineage match: True",
    ]
    assert log_lines == expected_log_lines
    assert capsys.readouterr().out.splitlines() == expected_log_lines


def test_passive_event_callbacks_observe_stored_event_versions(capsys) -> None:
    """Passive callbacks print stored event versions without changing them."""
    reset_event_state()
    hero_id = uuid4()
    observed: list[tuple[EventPhase, str | None]] = []

    def remember_event(event: Event) -> None:
        observed.append((event.phase, event.status_message))

    EventQueue.add_on_event_callback(remember_event)

    declaration = Event(
        name="Observe Me",
        source_entity_uuid=hero_id,
        event_type=EventType.BASE_ACTION,
    )
    completion = declaration.phase_to(EventPhase.EXECUTION).phase_to(
        EventPhase.EFFECT,
        status_message="Effect resolved",
    ).phase_to(EventPhase.COMPLETION, status_message="Complete")

    assert completion.phase == EventPhase.COMPLETION
    assert observed == [
        (EventPhase.DECLARATION, None),
        (EventPhase.EXECUTION, None),
        (EventPhase.EFFECT, "Effect resolved"),
        (EventPhase.COMPLETION, "Complete"),
    ]

    observed_lines = [
        f"observed phases: {' -> '.join(phase.value for phase, _ in observed)}",
        f"observed statuses: {[status for _, status in observed]}",
        f"completion phase: {completion.phase.value}",
        f"callback count: {len(observed)}",
    ]

    print("\n".join(observed_lines))

    expected_observed_lines = [
        "observed phases: declaration -> execution -> effect -> completion",
        "observed statuses: [None, None, 'Effect resolved', 'Complete']",
        "completion phase: completion",
        "callback count: 4",
    ]
    assert observed_lines == expected_observed_lines
    assert capsys.readouterr().out.splitlines() == expected_observed_lines
