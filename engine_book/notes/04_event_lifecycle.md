# 04. Event Lifecycle

## Purpose

Events are the engine's causal ledger. Actions, rolls, conditions, spatial updates, turn changes, and many derived effects are represented as event objects and posted through `EventQueue`.

This chapter documents current behavior in `dnd/core/events.py` from first principles. It treats comments and older examples as hints only; executable parity lives in `tests/engine_book/test_chapter_04_event_lifecycle.py`.

## Source Files Studied

- `dnd/core/events.py`
- `dnd/core/combat_log.py`
- `dnd/actions.py`
- `examples/test_event_hierarchy.py`
- `examples/test_turn_end_handler.py`
- `examples/test_combat_log_hierarchy.py`
- `examples/test_saving_throw_events.py`
- `examples/test_reactive_senses.py`
- `tests/engine_book/test_chapter_04_event_lifecycle.py`

## Rules Relationship

Status: `Engine extension` as engine infrastructure.

The SRD describes the game procedures that higher layers model: making attacks, resolving saving throws, taking damage, concentrating, moving, reacting, and ending turns. The event lifecycle is the engine's internal mechanism for representing those procedures. It is not itself an SRD rule, but it is the boundary where SRD procedures become auditable state transitions.

## Event Identity

`Event` extends `BaseObject`, so every event has:

- `uuid`: identity of this specific event version.
- `source_entity_uuid`: required source identity.
- `target_entity_uuid`: optional target identity.
- optional source and target names.
- optional runtime `context`.
- `use_register`: whether construction and posting should register the event.

Events add lifecycle fields:

- `lineage_uuid`: stable identity for all versions of the same logical event.
- `event_type`: exact event family, such as `ATTACK`, `D20_ROLL_RESULT`, or `TURN_END`.
- `phase`: current phase.
- `modified`: true after `post()` creates a replacement version.
- `canceled`: true for canceled events.
- `parent_event`: phase-specific UUID of a parent event.
- `status_message`: optional human-readable state.
- `is_first` and `is_last`: flags for repeated phases.
- `children_events`: child UUIDs created in the current phase.
- `lineage_children_events`: child UUIDs accumulated across the event lifetime.
- `parent_lineage` and `children_lineages`: stable lineage references populated at completion.
- `combat_log`: optional generated log entry populated at completion.

Creating an event with `use_register=True` immediately registers it through `EventQueue.register()` during Pydantic post-init.

## Phase Progression

The normal ordered phases are:

1. `DECLARATION`
2. `EXECUTION`
3. `EFFECT`
4. `COMPLETION`

`CANCEL` is a terminal cancellation phase, but it is not part of the normal ordered progression.

`phase_to()` creates a new event version by calling `post()`:

- The new version gets a fresh `uuid`.
- The new version keeps the same `lineage_uuid`.
- The new version refreshes its timestamp.
- The new version is registered unless `use_register=False`.
- If no phase is passed, the next ordered phase is used.
- If called on a completion event, it returns the same completion event.

Example EB-04-001:

```python
declaration = Event(
    source_entity_uuid=source_uuid,
    target_entity_uuid=target_uuid,
    event_type=EventType.BASE_ACTION,
    phase=EventPhase.DECLARATION,
)
execution = declaration.phase_to(EventPhase.EXECUTION)
effect = execution.phase_to(EventPhase.EFFECT)
completion = effect.phase_to(EventPhase.COMPLETION)

versions = [declaration, execution, effect, completion]
assert len({event.uuid for event in versions}) == 4
assert {event.lineage_uuid for event in versions} == {declaration.lineage_uuid}
assert EventQueue.get_event_history(completion.uuid) == versions
```

Parity test: `tests/engine_book/test_chapter_04_event_lifecycle.py::test_eb_04_001_phase_to_creates_versions_with_one_lineage`.

## Queue Storage And Handler Dispatch

`EventQueue.register()` stores the event before it dispatches handlers.

Storage indexes the event by:

- lineage UUID
- event UUID
- timestamp
- event type
- phase
- source entity UUID
- target entity UUID when present
- append-ordered raw event stream

After storage, the queue asks for matching handlers. A trigger matches only when:

- `event_type` is exactly equal.
- `event_phase` is exactly equal.
- `event_source_entity_uuid`, when set, equals the event source.
- `event_target_entity_uuid`, when set, equals the event target.

There is no event-type inheritance in trigger matching. For example, a `D20_ROLL_RESULT` trigger does not catch `ATTACK_D20_ROLL_RESULT` unless a separate trigger is registered for that exact type.

Handler results are interpreted as follows:

- `None`: no change; the next handler receives the current event.
- modified event: stored and passed to later handlers.
- canceled event: stored and returned immediately; later handlers do not run.

`EventQueue.event_cursor()` returns a raw append-stream cursor. It is not a
timestamp cursor. This matters because some event objects can be created with a
timestamp before they are registered. The raw stream must stay append-stable for
API/SSE cursors and for tests that call `iter_events_since(cursor)`.
`get_events_chronological()` is the separate timestamp-sorted read model.

Example EB-04-013:

```python
first = Event(source_entity_uuid=uuid4(), event_type=EventType.BASE_ACTION)
second = Event(source_entity_uuid=uuid4(), event_type=EventType.BASE_ACTION)
cursor = EventQueue.event_cursor()

late_backdated = Event(
    source_entity_uuid=uuid4(),
    event_type=EventType.BASE_ACTION,
    timestamp=datetime.now() - timedelta(days=1),
    use_register=False,
)
EventQueue.register(late_backdated)

since_cursor = EventQueue.iter_events_since(cursor)
chronological = EventQueue.get_events_chronological()

assert [event for _, event in since_cursor] == [late_backdated]
assert EventQueue.get_event_index(late_backdated.uuid) == cursor
assert EventQueue._all_events == [first, second, late_backdated]
assert chronological[0] is late_backdated
```

Parity test: `tests/engine_book/test_chapter_04_event_lifecycle.py::test_eb_04_013_event_stream_cursors_are_append_stable_not_timestamp_sorted`.

Example EB-04-002:

```python
def first_handler(event, source_uuid):
    event.status_message = "first changed this"
    return event

def filtered_handler(event, source_uuid):
    event.status_message = "filtered saw the change"
    return event

EventQueue.add_event_handler(
    EventHandler(
        source_entity_uuid=source_uuid,
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

execution = declaration.phase_to(EventPhase.EXECUTION)
assert execution.status_message == "filtered saw the change"
```

Parity test: `tests/engine_book/test_chapter_04_event_lifecycle.py::test_eb_04_002_handlers_match_exact_phase_source_and_target`.

## Empty-Trigger Handlers

An `EventHandler` with no `trigger_conditions` fires when called directly:
`EventHandler.__call__()` treats an empty trigger list as an always-match local
call. Queue dispatch is different. `EventQueue` discovers handlers through
trigger indexes and trigger iteration, so a handler registered with no triggers
is present in the main handler registry but is not found by ordinary queue
lookup.

Example EB-04-012:

```python
handler = EventHandler(
    source_entity_uuid=source_uuid,
    trigger_conditions=[],
    event_processor=direct_only_handler,
)

direct_result = handler(event, source_uuid)
assert direct_result is event
assert event.status_message == "direct handler ran"

event.status_message = None
EventQueue.add_event_handler(handler)
execution = event.phase_to(EventPhase.EXECUTION)

assert calls == []
assert execution.status_message is None
assert EventQueue._event_handlers[handler.uuid] is handler
assert EventQueue._event_handlers_by_source_entity_uuid[source_uuid] == [handler]
```

Parity test: `tests/engine_book/test_chapter_04_event_lifecycle.py::test_eb_04_012_empty_trigger_handlers_are_direct_only`.

## Completion Boundary

Completion is different from earlier phases.

When a completion event is registered, it is stored and passive callbacks observe it, but event handlers do not run. This is deliberate: handlers participate in the causal chain before completion; completion is the observation and log boundary.

Example EB-04-003:

```python
EventQueue.add_on_event_callback(observe)
EventQueue.add_event_handler(
    EventHandler(
        source_entity_uuid=source_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.BASE_ACTION,
                event_phase=EventPhase.COMPLETION,
            )
        ],
        event_processor=completion_handler,
    )
)

completion = (
    event.phase_to(EventPhase.EXECUTION)
    .phase_to(EventPhase.EFFECT)
    .phase_to(EventPhase.COMPLETION)
)

assert completion.phase == EventPhase.COMPLETION
assert completion_handler_calls == 0
assert observed_phases[-1] == EventPhase.COMPLETION
```

Parity test: `tests/engine_book/test_chapter_04_event_lifecycle.py::test_eb_04_003_completion_skips_handlers_but_not_passive_callbacks`.

## Passive Callbacks

Passive callbacks are registered with `EventQueue.add_on_event_callback()`.

They run after every event is stored, including completion and cancel events. They cannot alter queue dispatch because their return values are ignored. Callback exceptions are swallowed so passive monitoring cannot break event flow.

Use passive callbacks for observation: logging, transport updates, stream cursors, and other non-causal consumers.

Example EB-04-009:

```python
def failing_callback(event):
    calls.append(f"failing:{event.phase.value}")
    raise RuntimeError("passive callback failure")

def later_callback(event):
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
```

Parity test: `tests/engine_book/test_chapter_04_event_lifecycle.py::test_eb_04_009_passive_callback_exceptions_do_not_block_storage`.

## Pre-Completion Callbacks

Pre-completion callbacks are registered with `EventQueue.add_pre_completion_callback()`.

They run inside `phase_to(EventPhase.COMPLETION)` before completion metadata is computed. Unlike passive callbacks, they are lifecycle systems and may create child events. This is what lets reactive systems attach final child events before `children_lineages` and combat-log sub-entries are frozen.

Pre-completion callbacks:

- do not run for `SENSORY_UPDATE` events.
- are protected from re-entry by event UUID.
- run before `parent_lineage` and `children_lineages` are computed.

Example EB-04-004:

```python
def attach_child(event):
    child = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.DECLARATION,
        parent_event=event.uuid,
    )
    child.phase_to(EventPhase.COMPLETION)

EventQueue.add_pre_completion_callback(attach_child)
completion = parent.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)

assert child_lineage in completion.children_lineages
assert completion.get_children_events()[0].phase == EventPhase.COMPLETION
```

Parity test: `tests/engine_book/test_chapter_04_event_lifecycle.py::test_eb_04_004_pre_completion_callbacks_can_attach_children`.

## Parent And Child Structure

During the live causal chain, parent/child structure uses event UUIDs:

- A child stores `parent_event` as the UUID of the parent phase it was created under.
- When the child is stored, the queue mutates the parent phase and existing parent lineage versions to include the child UUID.
- Non-completion parent phases move current `children_events` into `lineage_children_events`.

At completion, the engine resolves UUIDs into stable lineage fields:

- `parent_lineage`: the lineage UUID of the parent event.
- `children_lineages`: deduped lineage UUIDs of direct children.

`get_parent_event()` and `get_children_events()` prefer stable lineage fields. They return the latest event version in each lineage, not necessarily the specific UUID originally stored in `parent_event` or `children_events`.

If `parent_event` points at an event UUID that is not in the queue, the child is
still stored normally. No parent receives a child pointer, completion cannot
resolve `parent_lineage`, and `get_parent_event()` returns `None`.

Example EB-04-010:

```python
missing_parent_uuid = uuid4()
child = Event(
    source_entity_uuid=source_uuid,
    event_type=EventType.TRIGGER_EVENT,
    phase=EventPhase.DECLARATION,
    parent_event=missing_parent_uuid,
)
completion = child.phase_to(EventPhase.COMPLETION)

assert child.get_parent_event() is None
assert completion.parent_lineage is None
assert completion.get_parent_event() is None
assert EventQueue.get_event_by_uuid(completion.uuid) is completion
assert EventQueue.get_events_by_phase(EventPhase.COMPLETION) == [completion]
```

Parity test: `tests/engine_book/test_chapter_04_event_lifecycle.py::test_eb_04_010_missing_parent_event_does_not_block_child_storage`.

Late children can still attach to a completed parent by UUID, but the completed
parent's stable `children_lineages` are not recomputed. If `children_lineages`
was already populated, `get_children_events()` continues to prefer that frozen
lineage list. This preserves the event tree that existed at the moment the
parent completed.

Example EB-04-011:

```python
early_child = Event(
    source_entity_uuid=source_uuid,
    event_type=EventType.TRIGGER_EVENT,
    phase=EventPhase.DECLARATION,
    parent_event=parent.uuid,
)
early_child_completion = early_child.phase_to(EventPhase.COMPLETION)
parent_completion = parent.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)

late_child = Event(
    source_entity_uuid=source_uuid,
    event_type=EventType.TRIGGER_EVENT,
    phase=EventPhase.DECLARATION,
    parent_event=parent_completion.uuid,
)
late_child_completion = late_child.phase_to(EventPhase.COMPLETION)

assert late_child_completion.parent_lineage == parent.lineage_uuid
assert late_child.uuid in parent_completion.children_events
assert parent_completion.children_lineages == [early_child.lineage_uuid]
assert parent_completion.get_children_events() == [early_child_completion]
```

Parity test: `tests/engine_book/test_chapter_04_event_lifecycle.py::test_eb_04_011_late_children_do_not_recompute_completed_parent_lineages`.

## Combat Log Boundary

Combat logs are generated at completion.

For events that override `generate_combat_log()`, `phase_to(COMPLETION)`:

1. Builds a temporary completion-shaped event.
2. Calls `generate_combat_log()`.
3. Collects completed child logs centrally into `sub_entries`.
4. Unions child perceiver and revealed-entity sets into the parent log.
5. Calls the combat-log callback only for top-level events with `parent_event is None`.
6. Posts the final completion event.

Child completion events may have their own `combat_log`, but they do not call the top-level combat-log callback when they have a `parent_event`.

Example EB-04-005:

```python
EventQueue.set_combat_log_callback(capture_log)

parent = LoggableEvent(
    source_entity_uuid=source_uuid,
    event_type=EventType.BASE_ACTION,
    phase=EventPhase.DECLARATION,
    status_message="Parent log",
)
child = LoggableEvent(
    source_entity_uuid=source_uuid,
    event_type=EventType.TRIGGER_EVENT,
    phase=EventPhase.DECLARATION,
    status_message="Child log",
    parent_event=parent.uuid,
)
child.phase_to(EventPhase.COMPLETION)
parent_completion = parent.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)

assert len(captured_logs) == 1
assert captured_logs[0].compact == "Parent log"
assert [entry.compact for entry in parent_completion.combat_log.sub_entries] == ["Child log"]
```

Parity test: `tests/engine_book/test_chapter_04_event_lifecycle.py::test_eb_04_005_completion_collects_child_combat_logs_top_level_only`.

## Combat Log Callback Ordering

The completion combat-log callback runs before the final completion event is
posted to queue storage. Current implementation builds a completion-shaped
temporary event for the callback, then `post()` creates and stores the actual
completion event with a fresh UUID.

The callback therefore observes:

- a temporary event whose `phase` is `COMPLETION`.
- no stored completion event yet.
- the pre-completion event version still present under that temporary event's
  UUID.

Example EB-04-008:

```python
def capture_event_state(event):
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
effect = declaration.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
completion = effect.phase_to(EventPhase.COMPLETION)

observed_uuid, observed_phase, observed_completions, observed_stored_phase = observations[0]
assert observed_phase == EventPhase.COMPLETION
assert observed_uuid == effect.uuid
assert observed_completions == []
assert observed_stored_phase == EventPhase.EFFECT
assert completion.uuid != observed_uuid
assert EventQueue.get_events_by_phase(EventPhase.COMPLETION) == [completion]
```

Parity test: `tests/engine_book/test_chapter_04_event_lifecycle.py::test_eb_04_008_completion_log_callback_runs_before_completion_storage`.

## Cancellation

`cancel()` posts a new event version with:

- `canceled=True`
- `phase=EventPhase.CANCEL`
- optional updated `status_message`

When a handler returns a canceled event, `EventQueue.register()` stores it and stops the handler chain.

Example EB-04-006:

```python
def canceling_handler(event, source_uuid):
    return event.cancel(status_message="blocked by handler")

def later_handler(event, source_uuid):
    calls.append("later")
    return event

canceled = event.phase_to(EventPhase.EXECUTION)

assert calls == ["canceling"]
assert canceled.canceled is True
assert canceled.phase == EventPhase.CANCEL
assert canceled.status_message == "blocked by handler"
```

Parity test: `tests/engine_book/test_chapter_04_event_lifecycle.py::test_eb_04_006_cancel_posts_cancel_phase_and_stops_handler_chain`.

## Standalone Combat Logs

Some visibility and perception notifications are combat-log entries but are not
normal causal events. `EventQueue.push_combat_log()` handles those cases by
creating a lightweight completion event with `use_register=False` and calling
the combat-log callback directly.

This means:

- no callback means the entry is dropped without side effects.
- the lightweight event is not stored in event indexes.
- consumers still receive an event-shaped object with `combat_log` attached.

Example EB-04-007:

```python
entry = CombatLogEntry(
    entry_type=CombatLogEntryType.ENTITY_SPOTTED,
    source_name="Observer",
    source_uuid=str(source_uuid),
    compact="Observer spots a hidden foe",
    verbose="Observer spots a hidden foe",
    detailed="Observer spots a hidden foe",
)

EventQueue.set_combat_log_callback(captured_events.append)
EventQueue.push_combat_log(entry, source_uuid)

event = captured_events[0]
assert event.phase == EventPhase.COMPLETION
assert event.combat_log is entry
assert EventQueue.get_event_by_uuid(event.uuid) is None
assert EventQueue.get_events_by_phase(EventPhase.COMPLETION) == []
```

Parity test: `tests/engine_book/test_chapter_04_event_lifecycle.py::test_eb_04_007_push_combat_log_bypasses_event_storage`.

## Current Edges To Preserve

- `EventQueue.reset()` clears event, handler, spatial, passive, pre-completion, perceiver, and revealed-computer state, but current implementation does not clear the combat-log callback. Tests that rely on clean callback state should call `EventQueue.set_combat_log_callback(None)`.
- Parent completion freezes `children_lineages` for that completion version. A child created after parent completion will not retroactively update that already completed event.

## Documentation Hygiene Status

The Chapter 04 hygiene pass reviewed the public event-lifecycle surface in
`dnd/core/events.py`: module contract, `EventType`, `EventPhase`, `Event`,
`Trigger`, handler classes, `EventQueue`, `SensesUpdateHint`,
`SensoryUpdateEvent`, `SpatialChangeEvent`, legacy d20 events, result events,
damage/healing events, and encounter/turn/death events. The combat-log model
surface in `dnd/core/combat_log.py` is also cleaned and guarded: every public
Pydantic model field on the 15 combat-log DTOs uses described `Field(...)`
metadata, each model has a Google-style `Attributes:` docstring, and the module
has no inline comments.

Only required `# type: ignore[...]` pragmas remain in `dnd/core/events.py` after
this pass.
