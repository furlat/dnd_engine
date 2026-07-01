# Chapter 05 Plan: Event Lifecycle

## Status

Published with real tutorial tests. The public Astro page is available for
browser review.

Prepared test file:

- `tests/manual/test_05_event_lifecycle.py`

Focused test run:

- `uv run pytest tests/manual/test_05_event_lifecycle.py`
- Result: 5 passed.

Manual arc focused test run:

- `uv run pytest tests/manual/test_01_runtime_identity_and_registries.py tests/manual/test_02_entity_anatomy.py tests/manual/test_03_values_and_modifiers.py tests/manual/test_04_dice_rolls.py tests/manual/test_05_event_lifecycle.py`
- Result: 22 passed.

Public file:

- `src/content/manual/05-event-lifecycle.mdx`

Public route:

- `http://127.0.0.1:4327/manual/05-event-lifecycle/`

Astro build:

- `npm run build`
- Result: 7 pages built.

## Reader Promise

By the end of the chapter, the reader should understand:

- Why all game-state changes are represented as events.
- How one logical event becomes several event versions through phases.
- Why `lineage_uuid` is stable while `uuid` changes per version.
- How declaration, execution, effect, completion, and cancel phases differ.
- How `EventQueue` stores event versions in lookup indexes.
- How parent and child events become stable lineage relationships at
  completion.
- How completion combat logs are generated from event data.
- How passive callbacks can observe event versions without changing them.

This chapter should define the event model before any reaction system appears.
It should not teach trigger matching, event handlers, spatial handlers, result
processors, action templates, or condition lifecycle yet.

## Evidence Studied From Source

Current-source evidence read for this plan:

- `dnd/core/events.py`
- `dnd/core/combat_log.py`
- `dnd/actions.py` event subclasses at a surface level
- `tests/manual/test_05_event_lifecycle.py`

Evidence conclusions below come from source inspection and focused tests, not
old prose.

## Source Facts To Teach

### Event

`Event` inherits from `BaseObject`. Creating an event with `use_register=True`
registers it in `EventQueue`.

Important fields:

- `uuid`
- `lineage_uuid`
- `event_type`
- `phase`
- `source_entity_uuid`
- optional `target_entity_uuid`
- optional source/target display names
- `modified`
- `canceled`
- optional `parent_event`
- optional `status_message`
- child event UUIDs and completed child lineage UUIDs
- optional `combat_log`

`phase_to()` creates a new event version with a new `uuid` and the same
`lineage_uuid`.

`cancel()` creates a cancel-phase version with `canceled=True`.

### EventPhase

Phases:

- `DECLARATION`: intent exists.
- `EXECUTION`: validation or execution preparation has passed.
- `EFFECT`: state change is being applied or has been applied.
- `COMPLETION`: final record and completion-time log metadata.
- `CANCEL`: aborted lineage.

Completion is a boundary: the queue stores completion events, runs
pre-completion callbacks before metadata is resolved, and generates combat logs
when the event subclass supports them. Triggered reaction systems are for the
next chapter.

### EventQueue Storage

`EventQueue` stores each event version in several indexes:

- by UUID,
- by lineage,
- by type,
- by phase,
- by source,
- by target,
- by timestamp,
- chronological stream.

Focused test evidence:

- A declaration -> execution -> effect -> completion chain has four different
  event UUIDs and one shared lineage UUID.
- `EventQueue.get_event_history(completion.uuid)` returns the four versions.
- Type, phase, source, and target indexes can recover the completion version.

### Cancellation

`cancel()` posts a cancel-phase version in the same lineage.

Focused test evidence:

- A canceled declaration has history `[DECLARATION, CANCEL]`.
- The cancel version has `canceled is True` and carries the status message.

### Parent And Child Events

An event can name a causal parent event version with `parent_event`.

When the parent completes, completion metadata resolves child event UUIDs into
stable `children_lineages`.

When a child completes, completion metadata resolves the parent's lineage into
`parent_lineage`.

Focused test evidence:

- A parent cast event and child damage event resolve to stable parent/child
  lineages at completion.
- `parent_completion.get_children_events()` returns the latest child event.
- `child_completion.get_parent_event()` returns the latest parent event.

### Combat Logs At Completion

`Event.generate_combat_log()` returns a combat log entry or `None`. The base
implementation returns an existing `combat_log`; subclasses can override it.

At completion, `phase_to(EventPhase.COMPLETION)` can:

- generate the event's combat log,
- collect child combat logs into `sub_entries`,
- invoke the combat-log callback for top-level events only.

Focused test evidence:

- A test-only `TutorialLogEvent` subclass can generate an action log.
- Completing a child first and then a parent creates a parent combat log with
  the child log in `sub_entries`.
- The top-level combat-log callback receives the completed top-level lineage.

### Passive Callbacks

`EventQueue.add_on_event_callback()` registers passive observers that fire for
stored events. They are for observation, not modification.

Focused test evidence:

- A passive callback sees declaration, execution, effect, and completion
  versions with their status messages.

## Concepts Allowed In This Chapter

Allowed:

- event
- event version
- event lineage
- phase
- declaration
- execution
- effect
- completion
- cancel
- event queue
- event indexes
- parent event
- child event
- lineage child
- combat log generation
- combat-log callback
- passive event callback

Allowed as future landmarks only:

- trigger
- handler
- spatial handler
- result processor

## Concepts Forbidden In This Chapter

Do not teach:

- trigger matching
- event handlers
- spatial handlers
- result processors
- condition lifecycle
- action templates
- attack flow
- movement opportunity attacks
- dice reroll mechanics
- spell concentration
- API event streams

Do not use hidden helpers from old tests.

Forbidden public names:

- `EB-*`
- parity
- `tests/engine_book`
- private notes
- `make_bonus`
- `make_damage_roll`
- `make_d20_roll`
- `fixed_randint`
- `completed_damage_events`

## Public Page Shape

### 1. Why Events Exist

Start from the game:

The engine is the software dungeon master. It needs records for intent, checks,
state changes, completion, narration, and client observation.

### 2. Event Versions And Lineage

Teach `uuid` versus `lineage_uuid`, then phases.

### 3. Where The Imports Come From

This import map must appear before code:

| Symbol | Import | Why it appears |
| --- | --- | --- |
| `uuid4` | `from uuid import uuid4` | Creates tutorial source and target IDs. |
| `CombatLogEntry`, `CombatLogEntryType` | `from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType` | Builds a small completion log example. |
| `Event`, `EventPhase`, `EventQueue`, `EventType` | `from dnd.core.events import Event, EventPhase, EventQueue, EventType` | Creates event records, advances phases, and inspects queue indexes. |

Do not include reset helpers in the public import map.

### 4. One Event Through Four Phases

Show declaration -> execution -> effect -> completion.

Teach:

- different UUID per version,
- same lineage UUID,
- event history,
- queue indexes.

### 5. Cancellation

Show `cancel(status_message=...)` and history `[DECLARATION, CANCEL]`.

### 6. Parent And Child Lineages

Show a parent spell event and child damage event. Keep it generic; do not teach
spell or damage mechanics yet.

### 7. Completion Combat Logs

Define `TutorialLogEvent` visibly before use.

Show:

- child log completes first,
- parent log completes after,
- parent log receives child `sub_entries`,
- top-level callback gets the top-level completed event.

### 8. Passive Event Observation

Show `add_on_event_callback()` observing event versions.

Make clear this is observation only. The next chapter explains reaction systems.

### 9. What Comes Next

Next chapter: reactions to events.

Events define the record. The next chapter teaches trigger matching, event
handlers, result processors, and spatial handlers.

## Diagram Requirement

Create a fresh diagram:

- `event-lifecycle-records.svg`
- `event-lifecycle-records.excalidraw`

Visual shape:

- One horizontal lineage with declaration -> execution -> effect -> completion.
- Each phase has its own event UUID and shared lineage UUID.
- A cancel branch from declaration/execution.
- EventQueue indexes underneath.
- Parent event with child event branch resolving to child lineage at completion.
- Completion log box with child sub-entry.

Caption:

> An event lineage is one logical game occurrence stored as multiple phase
> versions; completion resolves child lineages and turns supported events into
> combat-log records.

## Test Requirement

The test file must remain a real pytest file:

- `tests/manual/test_05_event_lifecycle.py`

It must include:

- visible imports,
- visible `TutorialLogEvent` subclass,
- no wrappers around examples,
- no imports from `examples`,
- no imports from `tests.engine_book`,
- no `iter_example_tests`,
- behavior names instead of EB numbers.

Required focused tests:

- `test_event_phases_create_versions_with_one_lineage()`
- `test_event_cancel_records_canceled_version_in_same_lineage()`
- `test_parent_child_events_resolve_stable_lineages_at_completion()`
- `test_completion_generates_top_level_log_with_child_sub_entries()`
- `test_passive_event_callbacks_observe_stored_event_versions()`

Run focused only:

```bash
uv run pytest tests/manual/test_05_event_lifecycle.py
```

Do not run the full test suite.

## Public Acceptance Gate

Completed before keeping the page public:

- Chapter 05 includes the import map before code.
- Every code symbol is imported or defined before use.
- No public note/test/parity links.
- No hidden helpers in public snippets.
- No trigger-matching, event-handler, spatial-handler, result-processor, action
  template, or condition lifecycle explanation before introduced.
- Diagram renders at desktop and narrow widths.
- Focused pytest file passes.
- Astro build passes.
- Route returns `200`.
- Public hygiene scan finds no `engine_book`, `tests/`, `parity`, `notes/`,
  `TODO`, `placeholder`, or old helper names.
