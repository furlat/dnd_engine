# First-Class Sensory Events Refactor Plan

## Status

Implemented in branch `feat-codex-in-control` as a first backend pass.

Current shape:

- `EventType.SENSORY_UPDATE` and `SensoryUpdateEvent` exist in
  `dnd/core/events.py`.
- `EventQueue` has pre-completion lifecycle callbacks. They run from
  `Event.phase_to(EventPhase.COMPLETION)` before stable
  `children_lineages` metadata is computed.
- `SpatialSensesCallback` now runs as the observer-local pre-completion
  sensory system. The class name is retained for compatibility, but it is no
  longer an `_on_event_callbacks` passive observer.
- Sensory deltas are emitted as child event lifecycles under the causative
  event. Empty deltas are skipped.
- Path maps remain lazy: sensory events can report `paths_dirty=True`, but do
  not stream Dijkstra/path data.
- `set_stealth_dc()` and `set_invisible()` can receive a `parent_event` UUID so
  condition-caused perceivability changes have useful lineage.

The rest of this document preserves the first-principles design and repair
plan that led to the implementation.

This document captures the desired shape of the event/senses pipeline after the
animated client exposed a structural problem: sensory state is currently correct
by the time gameplay continues, but the event stream does not explain when and
why perception changed.

The goal is not to patch one visibility bug. The goal is to make perception,
fog of war, light, hidden/invisible reveal, and visible entity/object updates
first-class staged facts in the backend event tree.

## Core Problem

The backend already owns the correct game truth for senses:

- FOV geometry
- light and darkness
- observer-specific effective light
- seen cells
- visible cells
- visible entities
- visible objects
- hidden/invisible filtering
- path dirtiness after spatial/perception changes

But the current update mechanism is mostly passive. `SpatialSensesCallback` is
registered as an `EventQueue` on-event callback. That means many sensory
mutations happen after the event has already been stored and, critically, after
completion events have already computed their child lineage metadata.

That is acceptable for CLI play because final state is right. It is not
acceptable for an animated client because the client needs staged truth:

```text
Open Door
  Spatial object changed
    Spatial light changed
    Sensory update
```

or:

```text
Step movement
  Spatial entity left
  Spatial entity entered
  Sensory update
```

Today the state mutates, but the tree does not faithfully encode the sensory
mutation. The client is then forced to infer timing from snapshots, polling, or
local recomputation, which violates the backend-authority principle.

## Non-Negotiable Invariants

1. The backend is the authority for visibility, light, fog, and perceptibility.
   The client may animate these facts, but must not recompute them as game
   truth.

2. No sensory child events may be created after the causative parent has
   completed. Completion-time children are structurally wrong because the parent
   has already finalized its `children_lineages`.

3. A sensory update is a real game event, not hidden callback behavior and not
   a detached side journal.

4. Sensory updates must be parented under the event that caused them.

5. Sensory updates should be generated after the causative state mutation and
   after normal effect handlers have run, but before the causative event phases
   to completion.

6. Path maps remain lazy. Sensory events can mark `paths_dirty`, but should not
   stream Dijkstra/path data.

7. Light propagation remains backend-computed. The client should never decide
   whether a closed/open door lets light through.

8. The refactor must preserve current gameplay semantics and tests. The point
   is staged observability, not rule changes.

## Current Backend Anatomy

### Event lifecycle

File: `dnd/core/events.py`

Important existing pieces:

- `Event.phase_to(EventPhase.COMPLETION)` builds `parent_lineage` and
  `children_lineages`.
- `EventQueue._store_event()` stores the event and attaches parent/child links.
- `_on_event_callbacks` are called after the event is stored.
- Completion events do not run normal event handlers.

This is the central mismatch. If a callback mutates senses after completion, it
cannot naturally produce a child event that belongs inside the completed
parent's lineage tree.

### Sensory callbacks

File: `dnd/blocks/sensory.py`

`SpatialSensesCallback` currently handles:

- self-movement FOV recompute via `update_entity_visibility()`
- light-change subscription checks
- entity entered/left visibility updates
- entity death visibility removal
- object placed/removed/changed visibility updates
- perceivability changes for hidden/invisible
- condition application/removal that changes the owner's own senses
- `_paths_dirty` marking for later path recompute

This class contains much of the right logic. The problem is where it runs and
how its mutations are represented.

### Entity senses computation

File: `dnd/entity.py`

Relevant methods:

- `compute_senses_from_position()`
- `update_entity_senses()`
- `update_entity_visibility()`
- `get_available_actions()` checks `_paths_dirty` and lazily recomputes paths

Full senses computation includes FOV, visible cells, visible entities, visible
objects, walkable cells, paths, and safe paths.

Lightweight visibility computation updates visible cells/entities/objects while
keeping paths deferred.

### Spatial and light events

File: `dnd/core/gridmap.py`

Relevant mechanisms:

- `_fire_spatial_event()` runs spatial event lifecycle.
- `move_entity()` emits spatial left/entered events.
- `_on_vision_blocking_changed()` reacts to vision-blocking object changes and
  emits light change events.
- `_on_light_movement_event()` reacts to moving light sources.

The light system already produces backend-computed light deltas via
`SPATIAL_LIGHT_CHANGED`. That part should be preserved and integrated with the
new sensory event pipeline.

### Perceivability

Files:

- `dnd/core/base_block.py`
- `dnd/conditions.py`
- `dnd/core/base_conditions.py`

Hidden/invisible/perceivability currently works through condition-agnostic
flags on `BaseBlock`, followed by spatial perceivability events and callback
refiltering.

One important gap: setters such as `set_stealth_dc()` and `set_invisible()`
need reliable parent propagation. A perceivability update caused by a condition
application/removal should be parented under that condition event, not emitted
as an orphan.

## Target Architecture

Introduce a new first-class event:

```python
EventType.SENSORY_UPDATE
```

with a concrete event model, for example:

```python
class SensoryUpdateEvent(Event):
    observer_uuid: UUID
    cause_event_uuid: UUID
    update_reason: SensoryUpdateReason

    visible_cells_added: List[Tuple[int, int]]
    visible_cells_removed: List[Tuple[int, int]]
    seen_cells_added: List[Tuple[int, int]]

    visible_entities_added: Dict[UUID, Tuple[int, int]]
    visible_entities_removed: Dict[UUID, Tuple[int, int]]
    visible_entities_moved: Dict[UUID, EntityMoveDelta]

    visible_objects_added: Dict[UUID, Tuple[int, int]]
    visible_objects_removed: Dict[UUID, Tuple[int, int]]
    visible_objects_changed: Dict[UUID, Tuple[int, int]]

    sense_modes_changed: bool
    paths_dirty: bool
```

Exact field shapes can be refined during implementation, but the event should
carry enough data for a client to animate fog/entity/object changes without
asking `/visibility` for timing.

The backend still updates the actual `Senses` object. The sensory event is both:

- the authoritative state mutation record
- the client-facing staged delta

## Lifecycle Hook

The cleanest backend shape is a pre-completion lifecycle hook in the event
system:

```text
event declaration
event execution
event effect
normal effect handlers run
pre-completion systems run
  sensory system may emit child sensory events
event completion
```

Conceptually:

```python
class EventQueue:
    _pre_completion_systems: list[EventLifecycleSystem]

    @classmethod
    def run_pre_completion_systems(cls, event: Event) -> None:
        ...
```

Then `Event.phase_to(COMPLETION)` or the event queue registration path invokes
the pre-completion systems before computing completion metadata.

The system must guard against recursion:

- `SENSORY_UPDATE` completion must not generate another sensory update.
- Events that do not affect perception must be ignored cheaply.
- Empty deltas should usually be skipped unless `paths_dirty` is gameplay
  meaningful enough to preserve as an event.

## SensoryUpdateSystem

Create a dedicated system that replaces `SpatialSensesCallback` as the owner of
reactive perception updates.

Possible file choices:

- keep in `dnd/blocks/sensory.py` initially, because that is where existing
  logic lives
- later split to `dnd/systems/sensory.py` if systems become a broader pattern

Responsibilities:

1. Decide whether an event can affect senses.

2. Find affected observers.

3. Snapshot an observer's current sensory state.

4. Apply the sensory mutation using extracted logic from
   `SpatialSensesCallback`.

5. Diff the old and new snapshots.

6. Emit one `SensoryUpdateEvent` per observer with a meaningful delta.

7. Preserve `_paths_dirty` semantics without computing paths eagerly.

The important refactor is to separate "what changes in senses" from "how the
callback receives event notifications."

The existing callback logic should become reusable mutation logic, not be
thrown away.

## Sensory Snapshot And Diff

Add small value helpers, probably in `dnd/blocks/sensory.py`:

```python
class SensesSnapshot(BaseModel):
    visible: Set[Tuple[int, int]]
    seen: Set[Tuple[int, int]]
    entities: Dict[UUID, Tuple[int, int]]
    objects: Dict[UUID, Tuple[int, int]]
    paths_dirty: bool
    sense_modes: Tuple[SenseModeSnapshot, ...]
```

The diff layer should produce serializable lists/dicts with stable ordering for
tests.

The diff is the contract with the animated client. The internal `Senses` object
can remain optimized for backend gameplay.

## Event Sources That Must Produce Sensory Updates

### Spatial entity entered/left

Current source:

- `GridMap.move_entity()`
- `SPATIAL_ENTITY_LEFT`
- `SPATIAL_ENTITY_ENTERED`

Expected sensory effects:

- observers may gain or lose visibility of the moved entity
- observers may need path dirtied if the entity blocks movement
- the moving entity may update its own FOV/visible entities/visible objects

Important movement nuance:

The mover's own FOV should update once per step, not once for both left and
entered. The current order updates the entity position before spatial left and
entered are fired. The refactor should explicitly choose one anchor for mover
self-visibility.

Recommended rule:

- other observers update from spatial left/entered
- the mover's own FOV update happens once, preferably on entered or directly
  under `StepMovementEvent`

This preserves the "lightcone while walking" without duplicate deltas.

### Spatial object changed

Current source:

- doors and other objects call `_notify_blocking_changed()`
- emits `SPATIAL_OBJECT_CHANGED`

Expected sensory effects:

- FOV may change if the object blocks/unblocks vision
- paths may become dirty if the object blocks/unblocks movement
- visible objects may change
- light propagation may change if vision blocking changed

Ordering requirement:

```text
object changed
  light changed
  sensory update
```

The sensory update must see the already-updated light state.

### Spatial light changed

Current source:

- tiles/light sources batch light modifications
- `SPATIAL_LIGHT_CHANGED`

Expected sensory effects:

- visible cells may be added/removed due to effective light
- entities/objects in those cells may appear/disappear
- `seen` may grow
- FOV geometry may change for magical darkness

Normal darkness/brightening can often update only subscribed positions.
Magical darkness should be treated as FOV-affecting because it can block vision
like geometry for observers without appropriate senses.

### Spatial perceivability changed

Current source:

- hidden/invisible setters on `BaseBlock`
- conditions that call those setters

Expected sensory effects:

- visible entity/object membership may change without any movement
- hidden enemies may become spotted
- paths may become dirty if imperceivable blockers affect pathing assumptions

Parenting gap to fix:

Condition-caused perceivability events should receive the condition event UUID
as parent. Avoid orphan perception changes.

### Death

Current source:

- `Entity.receive_damage()`
- `DeathEvent` child of `TakeDamageEvent`

Expected sensory effects:

- dead entity removed from observers' visible entity maps
- paths dirty if the corpse/no-longer-blocking behavior changes movement
- client can hide/remove/death-mark the visible entity at the correct point in
  the damage/death tree

The sensory update should be a child of `DeathEvent`, not a late callback after
death completion.

### Condition application/removal affecting the observer's own senses

Examples:

- Darkvision
- See Invisibility
- True Seeing
- Blindsight
- passive perception changes

Expected sensory effects:

- observer's visible cells/entities/objects may change
- sense mode payload may change
- paths dirty may be set if path availability depends on newly visible blockers

The sensory update should be parented under the condition application/removal
event.

## Light System Relationship

This refactor should not collapse light and perception into the same concept.

They are distinct:

- light events describe objective tile light changes
- sensory events describe what an observer perceives after light/object/entity
  changes

So the desired tree for opening a door is not:

```text
Open Door
  Sensory update with locally guessed light
```

It is:

```text
Open Door
  Spatial object changed
    Spatial light changed
    Sensory update
```

The client can render light/fog in sequence, but the backend remains authority
for both.

## Callback Migration

Current callbacks:

- `SpatialSensesCallback` in `dnd/blocks/sensory.py`
- grid light callbacks in `dnd/core/gridmap.py`

Recommended migration:

1. Replace `SpatialSensesCallback` with `SensoryUpdateSystem`.

2. Keep grid light callbacks temporarily if they already emit child events
   before the parent completes.

3. After sensory updates are stable, consider migrating grid light callbacks to
   explicit lifecycle systems too:

   - `SpatialLightSystem`
   - `AttachedLightMovementSystem`

The sensory refactor does not require solving every callback in the codebase at
once. The hard invariant is that perception state changes must be represented
by first-class events before parent completion.

## Backend Touch Points

### `dnd/core/events.py`

Add:

- `EventType.SENSORY_UPDATE`
- `SensoryUpdateEvent`
- optional `SensoryUpdateReason` enum
- event queue pre-completion lifecycle system registry
- recursion guards for lifecycle systems

Review:

- `Event.phase_to(COMPLETION)`
- `EventQueue.register()`
- `_store_event()`
- parent/child lineage resolution

### `dnd/blocks/sensory.py`

Refactor:

- extract reusable mutation logic from `SpatialSensesCallback`
- add snapshot/diff helpers
- add `SensoryUpdateSystem`
- remove passive callback registration path once replaced

Preserve:

- targeted light updates where possible
- subscription behavior
- hidden spotted logging semantics
- `_paths_dirty` lazy path recompute behavior

### `dnd/entity.py`

Change:

- stop registering `SpatialSensesCallback` in `model_post_init`
- expose clean helpers for visibility-only recompute and full senses recompute
  if the sensory system needs them
- keep `get_available_actions()` lazy path recompute behavior

Review:

- movement end `update_entity_senses(max_distance=20)`
- turn start senses refresh
- visible target/action generation

### `dnd/core/gridmap.py`

Review:

- `_fire_spatial_event()`
- `move_entity()`
- `_on_vision_blocking_changed()`
- `_on_light_movement_event()`

Possible change:

- ensure spatial/light events invoke sensory lifecycle before completion
- optionally migrate light callbacks into lifecycle systems later

### `dnd/core/base_block.py`

Change:

- make perceivability-change notification parent-aware
- ensure `set_stealth_dc()` and `set_invisible()` can pass through a
  causative parent event

### `dnd/core/base_conditions.py` and `dnd/conditions.py`

Change:

- condition application/removal should pass parent event IDs into any
  perceivability/sense-mode mutation they cause
- condition events that modify the owner's senses should trigger sensory update
  children before completion

### `server/event_server.py`

Likely minimal:

- `/events` already serializes event models via `model_dump(mode='json')`
- confirm new event type appears correctly
- confirm websocket/event polling streams include or intentionally filter
  sensory events

### CLI display/log filtering

Files:

- `cli/display.py`
- `cli/log_filter.py`

Decision:

- sensory events should probably be hidden from normal human combat logs
- they should remain inspectable in debug/event-tree modes

## Client Contract

The client should use sensory events as the animation source for:

- fog reveal/hide
- seen-cell reveal
- entity appear/disappear
- object appear/disappear
- light-driven perception changes
- death visibility removal

The client should still be allowed to call `/visibility` as a resync snapshot,
but not as the timing source for animation.

The client should not:

- recompute FOV
- recompute light propagation through doors/walls
- infer hidden/invisible visibility locally
- decide whether an entity exists at a cell based on sprite hitboxes

## Examples And Tests To Update

### Must update

`examples/test_reactive_senses.py`

- Replace callback expectations with `SENSORY_UPDATE` expectations.
- Assert final senses are still correct.
- Assert sensory update children are parented under the causative event.

`examples/test_sense_buff_spells.py`

- Darkvision/See Invisibility/True Seeing should produce sensory update events.
- Assert observer sense changes and visible entity deltas.

`examples/test_light_propagation.py`

- Door/light propagation should produce light events and sensory events in
  proper order.
- Assert no light/fog leak through still-closed doors from the client's staged
  perspective.

`examples/test_lighting_system.py`

- Normal light changes and magical darkness should produce appropriate sensory
  deltas.

`examples/test_lighting_stealth_integration.py`

- Hidden reveal through light changes should be represented by sensory events.

`examples/test_invisibility_pathfinding_leak.py`

- Perceivability changes should dirty paths without leaking hidden blockers.

`examples/test_perception_staleness.py`

- This becomes one of the main regression tests for stale perception.

`examples/spatial_events_test.py`

- Event counts/tree expectations may change because sensory events are now
  explicit children.

`examples/test_event_hierarchy.py`

- Add assertions that sensory children are present before parent completion and
  have stable lineage metadata.

`examples/test_serialization.py`

- Add serialization coverage for `SensoryUpdateEvent`.

`server/test_websocket.py`

- Confirm sensory events stream correctly or are intentionally filtered by the
  endpoint being tested.

### Likely affected

`examples/test_intercept_dodge_roll.py`

- Door opening/closing and path dirty behavior.

`examples/test_available_actions_perf.py`

- Visibility/path dirtiness behavior around enemies behind doors.

`examples/test_info_leak_fixes.py`

- Ensure sensory events do not leak data to observers who should not receive
  it.

`examples/test_ice_storm.py`

- Terrain/path dirty interactions.

`examples/test_gust_of_wind.py`

- Forced movement and spatial updates.

`examples/test_spike_growth.py`

- Movement through zones plus perception/path dirtiness.

`examples/test_light_source_cleanup.py`

- Removed light source should produce correct light and sensory updates.

`examples/test_light_source_perf.py`

- Useful for checking the overhead of per-observer sensory events.

## Information Leak Rules

Sensory updates are observer-specific. A sensory event for one observer must not
leak hidden information to another observer.

Open design question:

- Should all sensory events be globally visible in the backend event stream, or
  should server endpoints filter them by requesting player/observer?

Recommended backend stance:

- Store complete sensory events internally.
- Add endpoint filtering rules before multiplayer/human-client exposure.
- Preserve full stream for debug/admin/server tests.

This mirrors combat log visibility concerns. The event tree may contain truth,
but external views should be observer-scoped where necessary.

## Empty Delta Policy

Avoid noisy events where possible.

Do not emit a sensory event if:

- no visible cells changed
- no seen cells changed
- no visible entities changed
- no visible objects changed
- no sense modes changed
- `paths_dirty` did not change

Emit an event even with no renderable delta if:

- `paths_dirty` changed and tests/gameplay need a staged reason
- debug mode explicitly asks for all sensory evaluations

## Performance Notes

The current callback system is optimized in places:

- light subscriptions avoid refiltering every observer for every light tile
- visibility-only updates avoid Dijkstra
- paths are lazy through `_paths_dirty`

The refactor must preserve those properties.

The new cost is diffing. Keep snapshots tight:

- sets/dicts only
- stable sorted serialization at event boundary
- no path maps
- no full grid dumps in normal events

If the event volume becomes high, add batching:

```text
one SensoryUpdateEvent per observer per causative event
```

not one sensory event per cell.

## Proposed Build Order

This is an execution order, not a conceptual compromise.

### 1. Add event model and lifecycle hook

- Add `SENSORY_UPDATE`.
- Add `SensoryUpdateEvent`.
- Add pre-completion lifecycle hook.
- Add guards so sensory events do not recursively trigger themselves.
- Add basic serialization test.

### 2. Extract senses snapshot/diff

- Add snapshot helper.
- Add diff helper.
- Add tests with synthetic before/after senses.

### 3. Move spatial sensory updates into the system

- Port `SpatialSensesCallback._apply_hint()` behavior.
- Disable/remove passive callback registration for spatial perception.
- Assert spatial events now contain sensory children.

### 4. Handle movement carefully

- Avoid duplicate mover self-FOV updates on both left and entered.
- Preserve per-step lightcone behavior.
- Keep full path recompute at movement end.

### 5. Handle light/object/door ordering

- Ensure object changes can trigger light changes before sensory updates.
- Add door-open/door-close tests around visibility and light.

### 6. Handle death

- Emit sensory updates under `DeathEvent`.
- Ensure visible dead entities disappear or update state at the correct staged
  point.

### 7. Handle condition and perceivability changes

- Fix parent propagation through condition-caused setters.
- Emit sensory updates for hidden/invisible/sense-mode changes.
- Update sense buff tests.

### 8. Update server/client contract

- Confirm `/events` and websocket behavior.
- Decide filtering/debug policy.
- Update client event type mirrors after backend stabilizes.

### 9. Remove old callback path

- Delete or deprecate `SpatialSensesCallback` once tests prove parity.
- Keep the extracted mutation logic under a system-owned name.

## Acceptance Criteria

The refactor is correct when:

1. Opening a door emits an event tree that contains light and sensory changes
   before the door/action parent completes.

2. Moving step-by-step emits sensory deltas at the same granularity needed for
   animation.

3. Killing an entity emits the death event and the observer-specific visibility
   update in the same causative tree.

4. Hidden/invisible changes are parented to the condition/action that caused
   them.

5. Sense buffs/debuffs produce sensory updates without manual resync.

6. The client can animate fog/entity/object changes from `/events` alone, using
   `/visibility` only as a recovery snapshot.

7. No client-side FOV/light/perceivability computation is required.

8. Existing gameplay examples still pass after expectation updates.

## Explicit Non-Goals

- Do not move FOV authority to the client.
- Do not stream Dijkstra/path maps in events.
- Do not attach ad hoc visibility payloads to every action type.
- Do not create sensory children after parent completion.
- Do not rewrite lighting rules as part of this refactor unless ordering
  requires it.
- Do not make sprite/container state authoritative for targeting or visibility.

## Final Shape

The desired backend model is:

```text
game action/event mutates world
world systems emit structured child events
sensory system emits observer-specific sensory deltas
parent event completes with full lineage
client animates the lineage
snapshots exist only for resync
```

This turns perception from a hidden side effect into a staged, serialized,
testable part of the event system. That is the shape needed for an animated
client that stays faithful to backend truth.
