# Pygame V-0 plus minimum V-1 vertical-seam implementation plan

Date: 2026-09-03  
Status: **accepted implementation plan — implementation has not begun**

## 1. Requested result

Implement one truthful end-to-end slice from the current in-process D&D engine
to a real `pygame-ce` window:

```text
one direct authored Earth battlefield
  + one direct premade observer
  + one closed authoritative EventQueue interval
        |
        | synchronous inspection; no EventQueue callback
        v
objective diagnostic rows for every stored Event version
  + detached copies of exactly two admitted concrete Event families
        |
        | one ordinary asyncio queue
        v
engine-owned sensory-delta reduction into a cold target scene
        |
        | human-time pygame frame pump
        v
observer-authorized isometric ground, grid, rails, and mouse/Z diagnostics
        |
        v
one exact presentation terminal for the interval
```

The executable is deliberately small. It starts, materializes the scene,
allows camera inspection, reports every unrepresented Event, and exits cleanly.
It does not yet play the scripted encounter.

“Vertical seam” means the complete mechanics-to-pixels path. This cut also
implements the real support-height projection law and proves it against the
existing elevation battlefield, but the default displayed map remains flat so
asset semantics, event detachment, subjectivity, and camera math are isolated
before walls, doors, water, props, and elevation art are combined.

## 2. Governing authority and verified starting point

This plan is subordinate to:

- `AGENTS.md`;
- `HOW_TO_TEST.MD`;
- `DND_IN_PROCESS_PYGAME_SYSTEM_ARCHITECTURE_ROADMAP_2026-09-02.md`;
- `PYGAME_P0_NEUROCLIENT_SYSTEM_STUDY_2026-09-02.md`; and
- `PYGAME_WORLD_ASSET_BRIDGE_NOTES_2026-09-02.md`.

The current checkout has already proved the specific mechanics seams this cut
uses:

- `EventQueue.generation_id()`, `event_cursor()`, and
  `iter_events_since()` expose one ordered in-process history;
- `WorldInitializedEvent` contains the complete actor-free cold world;
- `SensoryUpdateEvent` contains complete observer-owned sensory deltas;
- `capture_senses_snapshot()` and `Senses.apply_sensory_update()` already
  define the authoritative sensory replay semantics;
- `project_combat_log()` already censors a `CombatLogEntry` using event-time
  evidence without changing its model type;
- direct premade characters and `Game.deploy_entity()` provide a real observer;
- `battlefield.elevation_proving_ground` supplies current engine elevation
  values for projection/picking proof; and
- five focused existing proofs covering closed world intervals, cold world
  materialization, sensory replay, and elevation round-trip passed on the
  planning checkout.

The current uncommitted `WorldModifiedEvent` work is preserved but is neither a
dependency nor a deliverable of this cut. No structural edit, door transition,
torch transition, or incremental world mutation is required here.

## 3. Exact scope

### 3.1 Included

1. Add `pygame-ce` to the ordinary Python application dependencies and include
   `/game` in static type/dependency checking.
2. Add one direct, actor-free battlefield whose Tiles truthfully use
   `Material.EARTH`, bright light, height zero, and no world objects or
   connectors.
3. Compose that battlefield, one current direct fighter premade, one `Game`,
   and one deployment in-process.
4. Capture the whole startup as one closed EventQueue interval.
5. Produce primitive objective rows for every stored Event version without
   retaining unadmitted Events.
6. Detach only completed `WorldInitializedEvent` and `SensoryUpdateEvent`
   values.
7. Extract the existing sensory replay calculation into one pure function and
   make both the live `Senses` block and `/game` use that same calculation.
8. Keep a minimal cold renderer target: the detached world Event, one detached
   observer sensory snapshot, text rows, coverage, and reducer cursor.
9. Load one exact copied NeuroMapEditor ground PNG through a tiny client-owned
   JSON asset catalog and one exact `earth -> asset_id` binding.
10. Draw observer-authorized macro128 ground in pygame-ce with visible,
    remembered, and unseen display states driven only by engine sensory facts.
11. Implement WASD pan, cursor-centered stepped zoom, four camera quadrants,
    grid overlay, and height-aware mouse diagnostics.
12. Maintain the engine/reducer/display clocks and return one deterministic
    terminal when the interval is visibly settled or has failed.
13. Show objective and subjective text rails plus unsupported/failure counts.
14. Prove reset/generation fencing, exact event coverage, projection,
    subjectivity, asset loading, and a headless pygame frame through observable
    tests.

### 3.2 Explicitly excluded

- walls, doors, water, torches, fire, and runtime world modification;
- object or actor Sprite drawing;
- full entity creation/movement/life reducers;
- animation clips, actor rigs, attacks, reactions, spells, or VFX;
- player action input, action discovery, targeting, or Encounter orchestration;
- the two-character scripted encounter;
- CR-6 through CR-10 content recovery;
- exact decorated-map occurrence companions;
- fine64 anchors, edge/corner Sprite picking, or alpha-mask narrow phase;
- a general subjective projector for arbitrary Events;
- server, SSE, SDK, transport, persistence, save/load, or replay frameworks;
- threads, worker processes, networking, or a second event loop;
- asset inference, filename guessing, auto-discovery, hot reload, streaming, or
  an asynchronous loader;
- a scene ECS, renderer component system, manager, service, controller,
  command bus, event bus, callback chain, or dependency-injection container;
- a new Event base class, presentation Event hierarchy, cue, journal,
  transaction, receipt, acknowledgement-per-Event, or field-mask language; and
- screenshot goldens or pixel-perfect claims about unreviewed art.

Any excluded feature discovered while implementing this plan is recorded as a
visible unsupported coverage row. It is not pulled into this cut.

## 4. The one startup scenario

### 4.1 A semantically honest battlefield

Add one current public battlefield, `battlefield.open_ground_bright`, through
the existing `dnd/scenarios/battlefield_catalog.py` owner.

Its first definition is exact:

- bounds `(0, 0)` through `(8, 8)`;
- 81 ordinary support Tiles;
- `TileSurface(base_material=Material.EARTH)` on every Tile;
- ordinary movement costs;
- `LightLevel.BRIGHT_LIGHT` as base light;
- `elevation_steps == 0`;
- no objects;
- no connectors; and
- no spatial conditions.

It is a normal graphic-agnostic engine battlefield. It contains no asset ID,
path, pivot, camera, tint, or renderer tag. It may later become the base of the
small visual capability map, but this cut does not add future features to it.
Adding it is not a CR-7 completion claim and does not add a generic scenario
adapter.

The existing `GridMap`/Tile APIs are sufficient. Do not expand
`GridMap.create_rectangle()` merely to make this one builder shorter. The
builder may use the existing `set_tile(..., surface=...)` operation while
battlefield construction has already disabled event publication.

### 4.2 One real observer

After the world is built, create the current direct fighter premade through
`create_premade_character(FIGHTER_PREMADE_ID, faction="heroes",
position=(4, 4))` and deploy it through one `Game` using the existing public
deployment path.

The observer is not drawn in this cut. Its purpose is to exercise the same
Senses, light, FOV, contact, and sensory-event path that later actor rendering
will consume.

Immediately before deployment, record the EventQueue cursor and capture one
`SensesSnapshot` from the newly composed observer without allowing either the
generation or cursor to change. That cursor identifies the state boundary of
the authorized bootstrap/recovery seed. It is not a per-frame poll. After
deployment, every renderer-owned sensory change comes from detached
`SensoryUpdateEvent` values at or after the seed cursor.

On this exact unobstructed 9 x 9 bright map, deployment must emit a completed
selected-observer sensory update whose reduction discloses all 81 support
Tiles and records bright effective-light after-values for all 81. This is the
non-vacuous mechanics-to-pixels proof, not an incidental screenshot claim.

### 4.3 One closed source interval

Startup is one source interval:

1. reset the engine through the existing reset boundary;
2. record the EventQueue generation and start cursor;
3. build the battlefield;
4. create the direct observer;
5. record the observer seed cursor and capture the bootstrap snapshot, while
   proving capture itself emitted no Event;
6. deploy the observer;
7. record the end cursor;
8. inspect and detach the interval synchronously; and
9. revalidate the generation before any async yield.

The interval intentionally includes unadmitted character/equipment/deployment
Events. This proves that the bridge can report all objective history without
copying live component-bearing Events. One interval enters the presentation
queue and produces one terminal.

## 5. Event and information boundary

### 5.1 No EventQueue callback

The application calls an ordinary capture function after the complete startup
command returns. It must not register any presentation callback with:

- `add_on_event_callback()`;
- `add_on_event_sequence_callback()`;
- `add_on_event_batch_callback()`;
- pre-completion callbacks/systems; or
- Encounter combat-log callbacks.

Engine event completion remains wholly independent of presentation. Capture is
a synchronous read of the already-committed interval.

### 5.2 Interval validity

The capture function requires:

```text
same_generation_before_and_after
0 <= start_cursor <= observer_seed_cursor <= end_cursor
end_cursor <= EventQueue.event_cursor()
exact indexes start_cursor ... end_cursor - 1
storage order preserved
```

`iter_events_since()` currently clamps a negative start. The presentation
boundary must validate its own cursors first; it must not treat that clamping
as protocol behavior.

A generation change, missing index, duplicate index, out-of-range cursor, or
EventQueue reset during capture rejects the whole interval. No partial batch
is enqueued.

For this exact first startup, any selected-observer `SensoryUpdateEvent` at a
source index before `observer_seed_cursor` also rejects the whole interval.
The seed already describes observer state at that boundary, so replaying an
earlier delta would be a causal double application. Later work may design a
different recovery interval if a real producer requires it; this cut does not.

### 5.3 Exact admitted Event families

This cut admits only these exact concrete completion values:

| Concrete Event | Why it is needed | Payload law |
|---|---|---|
| `WorldInitializedEvent` | cold target world | tuples of current frozen/value world state models |
| `SensoryUpdateEvent` | observer knowledge/light/contact delta | typed positions, primitive flags, enums, UUIDs, `SenseMode`, and frozen `PerceivedContact` values |

Admission is an explicit two-case branch over the existing `event_type` and
completion phase, followed by validation that the object is the corresponding
concrete class. It is not a registry, decorator, visitor, protocol, serializer,
or extensible dispatch framework. Adding a third family requires a later
bounded plan and its own payload audit.

For either admitted family, the normal engine-produced instance must also have:

- `context is None`;
- `combat_log is None`; and
- no effective handler-presentation attachments.

Those inherited escape hatches are not needed by these facts and are not part
of their admitted contract. A value that violates one of these requirements is
left in the authoritative queue, recorded as unsupported, and is not copied.

The complete payload types of both families are enumerated by their current
Pydantic fields. Tests audit their declared fields and representative normal
values. Production code does **not** recursively walk arbitrary values, call
`getattr`, import runtime owners, serialize arbitrary Events, or guess whether
an unknown payload is safe.

The detached copy is `event.model_copy(deep=True)`. It remains the same
concrete Event subclass with the same UUID, lineage, parent, phase, and payload.
Model copying does not register a new engine Event. No field is masked, no
replacement Event is constructed, and no Event is deleted from the objective
queue.

### 5.4 Unsafe and unadmitted Events

Every other Event stays only in `EventQueue`. During the synchronous scan the
application extracts a plain primitive diagnostic row containing only the
current common Event facts needed by the objective rail:

- source index;
- UUID and lineage UUID;
- parent Event and parent lineage UUID, if any;
- Event type and phase;
- source/target UUID and already-captured names;
- turn execution UUID, if any;
- status message, outcome code, canceled flag, and modified flag; and
- the already-generated combat-log text, if present.

The row contains strings, integers, booleans, and `None`. It is not a generic
Event dump. It does not retain `context`, a condition, Entity, item, block,
handler, modifier, or arbitrary subclass field.

Unadmitted versions receive `unsupported` in the plain coverage map keyed by
source queue index. The objective row retains that index and the Event UUID,
so every stored phase version remains a separate coverage entry even when
versions share a lineage. Their objective row and unsupported badge make the
omission visible. They are not passed to subjective or Sprite code.

### 5.5 Subjective text

When a completed Event already has a `CombatLogEntry`, the privileged rail may
read its already-generated display text synchronously. The observer rail calls
the existing `project_combat_log()` during the same synchronous inspection and
uses the returned same-model entry, or omits it when projection returns
`None`. Only the chosen text string is retained by the pygame rail.

This does not create a general subjective Event conversion. Ordinary action
Events remain unadmitted until the later surgical event-family plans required
by V-2/V-3.

### 5.6 The queue envelope is not another Event

One small frozen Python value may carry:

- source generation UUID;
- inclusive start cursor;
- selected observer UUID, observer seed cursor, and detached seed
  `SensesSnapshot`;
- exclusive end cursor;
- primitive objective diagnostic rows in source order;
- already-projected subjective text rows in source order;
- initial `source queue index -> unsupported` coverage entries for every
  unadmitted source version; and
- ordered `(source queue index, detached admitted concrete Event)` pairs.

The objective rows' `(queue index, Event UUID)` fields are the interval's one
source-record identity/order list. Do not copy that list into a parallel field.
Admitted indexes receive no provisional disposition: reduction either closes
them directly or creates their exact pending display obligation.

The source index attached to each detached Event is boundary metadata, not an
Event field or replacement identity. It lets reduction close the disposition
for the exact queue record without consulting `EventQueue` again.

The target starts from the carried seed snapshot and applies selected-observer
sensory deltas only at source indexes greater than or equal to the carried seed
cursor. The capture invariant above guarantees that no selected-observer delta
was silently skipped before that boundary.

The envelope and its rows carry no `kind`, gameplay payload union, handler,
callback, or mutation method. They are merely ownership/boundary metadata and
primitive diagnostics. They are never stored in `EventQueue` and never
participate in mechanics.

## 6. One sensory computation, not a renderer rewrite

### 6.1 Extract the existing calculation

`Senses.apply_sensory_update()` currently performs two concerns together:

1. calculate the next sensory snapshot from a prior snapshot plus one
   `SensoryUpdateEvent`; and
2. write that result into the live `Senses` block.

Extract concern 1 into one pure function beside the existing sensory snapshot
code in `dnd/blocks/sensory.py`:

```text
reduce_senses_snapshot(expected_observer_uuid, previous, sensory_event)
    -> next_snapshot
```

The exact name may change if an existing local naming convention is clearer,
but the ownership may not.

The function:

- validates that the event belongs to the snapshot's observer identity passed
  by the caller;
- applies visible removals before additions;
- unions seen-cell additions monotonically;
- applies entity/object contact removals before changed after-values;
- removes effective-light values for cells that ceased to be visible;
- applies exact effective-light after-values from the event;
- applies observer position, passive perception, sense modes, and visual access
  only when their corresponding changed flag says so;
- derives the sense-mode hash directly from the reduced mode tuple using the
  existing sorted `(sense_type.value, range_feet)` formula, without consulting
  a live `Senses` block;
- preserves an already-dirty path cache and allows the event only to assert
  dirtiness: `next.paths_dirty = previous.paths_dirty or event.paths_dirty`;
- returns fresh collections plus deep-copied effective `SenseMode` values, so
  neither the prior snapshot nor Event-owned mutable values are aliased; and
- performs no GridMap, Entity, registry, FOV, light, hidden, or condition query.

The returned `sense_modes` and `visual_access` are reduced **effective cache
facts** only. The pure function does not own, model, or mutate
`sense_mode_sources`, the source-owned `visual_access` `ModifiableValue`, or
any other live component channel.

The pure reducer also does not call `SensoryUpdateEvent.validate_replay_payload()`
or perform any recursive passivity/type walk. The existing validation call
stays at the start of the live `Senses.apply_sensory_update()` wrapper to
preserve that public behavior. `/game` instead relies on the exact
two-concrete-family admission contract and its declared-field tests from
Section 5.3; it must not reuse that recursive runtime walker as a generic
presentation safety layer.

Because `SensesSnapshot` currently has no observer UUID field, the caller
passes the expected observer UUID explicitly. Do not broaden the snapshot type
solely to avoid that argument.

### 6.2 The live block remains the owner

Refactor `Senses.apply_sensory_update()` to call the pure reducer and then
commit the returned fields through its existing block state. Its observable
behavior must remain byte/value equivalent to the current implementation.

That wrapper retains three ownership details which are intentionally absent from
`SensesSnapshot`:

- when `sense_modes_changed` is true and the incoming effective modes already
  equal `self.get_sense_modes()`, leave both `self.sense_modes` and
  `self.sense_mode_sources` untouched;
- only when the incoming effective modes differ, replace the direct
  `self.sense_modes` after-value and clear `self.sense_mode_sources`, exactly
  as the existing method does; and
- commit reduced visual access only to `_last_visual_access`; never write or
  replace the source-owned `self.visual_access` `ModifiableValue`.

The wrapper may therefore inspect its own pre-commit effective mode tuple to
choose the existing preserve-versus-clear branch. That is component-owned
commit behavior, not a query performed by the pure reducer or by `/game`.

The pygame target scene stores one detached `SensesSnapshot` and calls the
same pure reducer. It never creates a second `Senses` block, never registers a
component, and never calls the live observer after bootstrap.

This is a two-consumer extraction of an existing rule, not a new observer
service or projection hierarchy.

### 6.3 Tile visibility is not content visibility

The target keeps these facts separate exactly as the sensory Event does:

| Fact | First-cut display use |
|---|---|
| visible Tile positions | full current terrain and effective-light treatment |
| seen but not visible positions | dim remembered terrain |
| unseen positions | no terrain disclosure; fog/background only |
| entity contacts | retained as subjective facts; not drawn yet |
| object contacts | retained as subjective facts; not drawn yet |

A visible Tile never implies that every Entity/object at that position is
visible. Later object/actor drawing must consult its corresponding observer
contact, not the Tile visibility set. This first map contains no world objects,
which keeps that law explicit without pretending object rendering is finished.

The renderer never computes ordinary sight, darkvision, truesight, magical
darkness, invisibility, hidden detection, line of sight, or light propagation.
It consumes the effective result already present in the sensory snapshot.

## 7. Minimal renderer target, displayed state, and coverage

### 7.1 Cold target state

Do not build a scene ECS or duplicate the world schemas. The minimum target
holds:

- the latest detached `WorldInitializedEvent`;
- one observer UUID and its detached `SensesSnapshot` as plain fields, not a
  multi-observer mapping;
- source generation;
- reducer cursor `R`;
- objective and subjective text lines; and
- the plain source-index disposition mapping.

The world Event's existing `WorldTileState` values remain the target Tile
values. No `RenderTile`, `CanonicalTile`, or presentation-world Pydantic model
is added.

### 7.2 Displayed semantic state

The displayed side owns only what is required to prove convergence:

- Tile UUIDs actually drawn in the last presented frame;
- their selected asset IDs and applied appearance keys;
- camera state and hover diagnostics;
- display cursor `D`; and
- the last terminal/failure text.

It does not mirror traversal costs, blockers, occupancy, light sources, or any
other mechanics.

The appearance key is one plain tuple derived only from already-reduced
subjective facts:

```text
visible Tile:          ("visible", effective LightLevel value)
seen, not visible:     ("memory", None)
unseen:                no drawn-Tile evidence
```

The client chooses a visual treatment for each finite key; it does not infer
or simulate the light. Scaled/tinted Surface caching includes this appearance
key so the semantic evidence records the treatment actually selected for the
blit, rather than merely echoing target data beside an untreated image.

### 7.3 Coverage dispositions in this cut

- a fully bound and drawn `WorldInitializedEvent` becomes `represented`;
- a successfully applied `SensoryUpdateEvent` becomes `state_only` because its
  knowledge/light facts control the frame without a separate animation;
- an Event version not admitted by this plan remains `unsupported`;
- a sensory Event for another observer would be `not_disclosed` and would not
  affect the selected target;
- an Event that cannot be reduced or drawn becomes `failed`.

`diagnostic_only` is reserved for a later family explicitly admitted only for
text. Do not use it to hide missing state-bearing visual work.

Unsupported is a valid closed development outcome and is displayed loudly. It
does not mean the corresponding mechanics failed. A false `represented` or a
silent omission is a terminal failure.

## 8. Asset boundary

### 8.1 Exact first asset

Copy exactly this reviewed source asset into `/game`:

```text
/home/tommaso/Dev/NeuroMapEditor/public/assets/fantasy/environment/ground-a1-e.png
```

The source is a 256 x 256 RGBA PNG. Record provenance in the client catalog,
but the executable loads only the repository-owned copy. It must never depend
on the external WSL repository at runtime.

This asset is the reviewed ordinary dirt/Earth ground family. The selected
battlefield therefore uses `Material.EARTH`; the renderer must not bind this
image to a Stone Tile for convenience.

The `e/n/s/w` Ground A1 files are visual variations, not current engine
directions. This cut uses the exact high-evidence `e` occurrence in all camera
quadrants and does not raster-rotate it. Direction-to-pose selection begins
with the later wall family, where direction is semantic.

### 8.2 Two tiny JSON files

Add:

1. an asset catalog with one exact record: stable asset ID, relative PNG path,
   expected 256 x 256 size, pivot `(128, 208)`, scale `1`, and planar surface
   role; and
2. a Tile binding mapping the exact `earth` base material to that asset ID.

The files are JSON-compatible and contain no Python class names or engine
objects. The first binding file is a direct map, not a selector language. Do
not add tags, priorities, predicates, inheritance, fallback chains, regexes,
or variant algorithms before a real second case requires them.

There is no exact battlefield occurrence companion in this cut. Its precedence
law remains accepted for the later decorated map.

### 8.3 Loading and failure

After `pygame.display.set_mode()`:

- load the one PNG synchronously;
- verify the catalog ID, relative-path containment, file existence, and native
  dimensions;
- call `convert_alpha()` once;
- derive any light/fog variants from copies, never mutate the canonical
  Surface; and
- cache derived Surfaces only for the finite `(zoom level, appearance key)`
  combinations.

A missing, malformed, escaping, wrongly sized, or undecodable asset is a
visible startup failure and produces a failed terminal. There is no filename
guess or procedural ground fallback. The grid/debug background may remain
visible so the error can be read.

`pygame-ce` is imported as `pygame`. Use the current stable 2.5 series in the
project dependency/lock. The implementation follows the official pygame-ce
display, Surface, transform, mouse, and Clock contracts: one display Surface,
event pumping each frame, alpha-converted images, finite cached scaling, one
`Clock.tick()` limiter, and one display update per frame. Do not combine a
vsync wait with the Clock limiter in this first software renderer.

Official references consulted for this plan:

- <https://pyga.me/docs/ref/display.html>
- <https://pyga.me/docs/ref/surface.html>
- <https://pyga.me/docs/ref/transform.html>
- <https://pyga.me/docs/ref/mouse.html>
- <https://pyga.me/docs/ref/time.html>
- <https://pypi.org/project/pygame-ce/>

## 9. Projection, camera, painter order, and picking

### 9.1 One pure projection owner

`game/projection.py` owns the complete forward/inverse relationship. No other
module repeats it.

For one macro128 Tile contact after camera-quarter rotation:

```text
world_x = (camera_x - camera_y) * 64
world_y = (camera_x + camera_y) * 32 - elevation_steps * 64
```

The `-64 px` vertical lift per current five-foot engine elevation step is the
selected NeuroMapEditor macro128 Z-grid calibration. It changes only the
display contact. Engine position remains `(x, y)`.

Keep the projection offset as a named function/value, not as a field added to
Tile. A future exact presentation companion may supply a different calibrated
Z-grid offset for a particular authored map, but this cut adds no general
calibration schema.

### 9.2 Four camera quadrants

With x right and y south, rotate around the map-center pivot:

```text
R0   (x, y)
R90  (-y, x)
R180 (-x, -y)
R270 (y, -x)
```

The inverse uses the opposite quarter turn. Rotation affects only client
projection, picking, and later asset-pose selection. It never changes engine
coordinates, wall ownership, light, perception, or Event facts.

### 9.3 Camera transform and controls

The screen transform is one explicit composition:

```text
engine contact
  -> rotate around map pivot
  -> macro128 projection + support-height offset
  -> finite zoom
  -> pixel pan / viewport origin
```

Controls:

- `W/A/S/D`: pan in screen space;
- mouse wheel: select the next finite zoom level while preserving the world
  pixel under the cursor;
- `Q/E`: rotate one quarter turn and recenter on the same map pivot;
- `G`: toggle grid overlay; and
- `Escape` or window close: clean shutdown.

Use a small fixed tuple of zoom levels covering useful overview and inspection
scales. This bounds the scaled-Surface cache. Do not add smooth kinetic pan,
camera animation, free rotation, controller input, or configurable bindings.

### 9.4 Ground painter order

This cut has one planar surface role. Its deterministic order is derived from
the camera-rotated, **unshifted** macro contact `(projected_y, projected_x)`,
then stable Tile UUID. Z-grid identity, engine elevation, and its pixel lift do
not enter painter rank; that is the retained NeuroMapEditor law. The lift only
changes the rendered contact position.

The same painter rank is used when overlapping ground candidates must be
resolved by picking. Do not use insertion order or a mutable arbitrary z-index.

### 9.5 Height-aware support-cell picking

Build the candidate support set only from target Tiles whose positions occur
in the selected observer's `visible` or `seen` facts. Objective world Tiles
outside that disclosed set must not participate in player picking. For every
distinct support elevation present in that disclosed support set:

1. remove viewport/pan and zoom;
2. remove that candidate elevation's calibrated pixel offset;
3. invert macro128 projection;
4. apply the inverse camera-quarter rotation;
5. round to the candidate owner cell;
6. require that exact Tile to exist and have the candidate elevation;
7. test the point against its projected 128 x 64 diamond; and
8. choose the visually foremost valid candidate by the same deterministic
   painter order.

The hover panel reports:

- screen pixel;
- unzoomed world pixel;
- camera quadrant and zoom;
- each candidate support elevation considered;
- candidate and chosen engine `(x, y)`;
- Tile UUID;
- elevation steps and feet;
- renderer Z-grid label and pixel offset;
- projected contact;
- painter rank; and
- diamond containment result.

When no disclosed support contains the pointer, the panel may still report
screen pixel, unzoomed world pixel, camera, zoom, and the raw algebraic plane
estimate. It reports no existing Tile, Tile UUID, support elevation, Z-grid
identity, or objective-map membership. This cut adds no privileged/omniscient
pick mode.

This is ground/support picking only. There is no Sprite rectangle or alpha
mask pick in this cut.

## 10. Pygame and asyncio execution model

### 10.1 One thread and one event loop

Pygame initialization, event pumping, drawing, and display update all remain
on the process main thread. Use one `asyncio.run()` composition and no worker
thread.

The startup engine work is synchronous and finishes before it is allowed to
yield. It returns the one detached interval envelope, including its observer
bootstrap snapshot and seed cursor.
The authoritative EventQueue may therefore already be at `E` while reducer
and display remain at their earlier cursors.

### 10.2 One input queue and one terminal queue

Use one `asyncio.Queue(maxsize=1)` for the one captured presentation interval
and one `asyncio.Queue(maxsize=1)` for its terminal result. Enqueue with
`put_nowait()` after successful capture so presentation can never make engine
event completion await animation time. Overflow is a surfaced fatal
presentation error, not a sleep or silent drop. Later encounter work may
change capacity only from measured real accumulation.

These are ordinary scheduling queues, not buses. Nothing subscribes. There is
no callback registered in mechanics and no future/promise map keyed per Event.

The pygame frame coroutine:

1. drains available presentation intervals in storage order;
2. reduces admitted Events into target state immediately;
3. advances `R` after every source queue record has been processed into either
   a closed non-display disposition or an exact pending display obligation;
4. pumps pygame input;
5. draws one frame from target state and current camera;
6. updates displayed semantic evidence;
7. flips/updates the display once;
8. advances `D` and emits the interval terminal when parity is true; and
9. calls one `Clock.tick(60)` plus an event-loop yield.

No arbitrary sleep synchronizes tests or runtime.

### 10.3 Three clocks

- `E`: end cursor captured after mechanics committed;
- `R`: end cursor of the last interval whose admitted facts were reduced and
  whose full ordered source-record set was processed into either a closed
  non-display disposition or an exact pending display obligation; and
- `D`: end cursor of the last interval whose owned semantic target was present
  in a displayed frame.

The runtime asserts `E >= R >= D` within one generation. Camera-only frames do
not advance these cursors. After target reduction and before the first matching
frame, the world Event has a display obligation but not yet the final
`represented` disposition; `E == R > D` is therefore lawful.

### 10.4 One terminal

The one startup interval has one small terminal value containing generation,
cursor range, outcome (`settled`, `failed`, or `cancelled`), and a
human-readable failure message when applicable. The tuple `(generation,
start_cursor, end_cursor)` already identifies the interval; do not add a second
boundary UUID.

It settles only when:

- every original source queue index has exactly one closed disposition tied to
  its recorded Event UUID;
- the admitted world and sensory values reduced in order;
- the one required asset loaded;
- the expected disclosed `(Tile UUID, asset ID, appearance key)` triples equal
  the triples actually drawn in one displayed frame;
- the display frame was published; and
- generation still matches.

Publishing the matching frame closes the pending world display obligation as
`represented` and advances `D`. Never label it represented merely because a
draw was scheduled or target state exists.

There are no terminal objects for individual Events, Tiles, assets, or frames.
Queue emptiness alone never settles the interval.

### 10.5 Reset and shutdown

A new EventQueue generation invalidates every old queued interval and target.
Stale intervals are closed as cancelled and cannot change `R`, `D`, the scene,
or coverage for the new generation. A fresh run constructs a fresh target from
one new world Event and observer seed.

Shutdown stops accepting intervals, closes pygame exactly once, and leaves
engine registries to the existing reset boundary. It does not delete or mutate
authoritative Events.

## 11. Minimal visible product

The first window contains only:

- observer-authorized isometric Earth ground;
- optional macro grid lines;
- a hover diamond;
- objective Event rows;
- observer-subjective Event/log rows;
- E/R/D and generation diagnostics;
- camera/zoom/quadrant diagnostics;
- mouse-to-grid/Z diagnostics; and
- visible counts/messages for unsupported and failed representations.

Grid overlay diamonds are generated from the same visible-or-remembered
support set used by picking. They never outline an unseen objective Tile.

Visible ground uses the observer's effective light after-value in its applied
appearance key. Seen but no longer visible ground uses one fixed memory
treatment. Unseen ground is not blitted. This is client display policy over
engine-authorized facts, not light simulation.

The exact widget geometry, font sizes, colors, and line wrapping are not a
stable contract. The stable contract is that each diagnostic value is readable
and updates with its owning state.

## 12. Planned modules and dependency DAG

The intended small module shape is:

```text
game/__main__.py
        |
        v
game/app.py ----------------------> pygame
   |        |        |
   v        v        v
game/presentation.py  game/projection.py  game/assets.py
   |                         |                 |
   v                         |                 v
dnd Events + sensory values  |          JSON + copied PNG
   |                         |
   +-------------------------+
```

Responsibilities:

- `game/presentation.py`: closed capture, exact two-family admission,
  objective/subjective rows, cold target reduction, coverage, cursors, and the
  one interval terminal value;
- `game/projection.py`: pure camera rotation, forward/inverse macro128 math,
  Z-grid offsets, painter key, and support-cell picking;
- `game/assets.py`: exact JSON validation plus synchronous Surface loading and
  finite zoom cache;
- `game/app.py`: direct scenario composition, the two asyncio queues, pygame
  frame/input/draw loop, and diagnostics layout; and
- `game/__main__.py`: one tiny executable entry point.

If one of these modules remains tiny, it may be merged into its direct caller.
Do not split additional `managers`, `controllers`, `services`, `stores`,
`repositories`, `systems`, `adapters`, or `interfaces` to mirror this diagram.

Dependency laws:

- `/game` may import public `dnd` values/builders and pygame;
- `dnd` must never import `/game`, pygame, or concrete `/game/assets` paths;
- `/game` must not import `server`, `sdk`, `services`, `deprecated`, `ai`, or
  the external MapEditor/NeuroClient repositories;
- asset and projection modules do not import mechanics owners they do not use;
- all imports are module-level;
- no `TYPE_CHECKING`, dynamic import, `getattr`, or import-cycle workaround is
  admitted; and
- Entity remains a data aggregate/system composer, never a renderer object.

## 13. Planned file envelope

Expected existing-file changes:

- `pyproject.toml` — add pygame-ce, include `/game` in pyright;
- `uv.lock` — lock the selected pygame-ce release;
- `requirements.txt` — retain the repository's existing pip dependency entry
  surface rather than making installation paths disagree;
- `dnd/blocks/sensory.py` — pure sensory-snapshot reducer extraction and live
  block reuse;
- `dnd/scenarios/battlefield_catalog.py` — one direct Earth battlefield;
- `tests/engine/test_senses_light_stealth.py` or the existing closest sensory
  replay module — public value-equivalence proof;
- `tests/engine/test_world_entity_initialization.py` — exact battlefield cold
  fact proof; and
- `tests/architecture/test_dependency_boundaries.py` — include `/game` in the
  existing graph where that is the smaller honest change.

Expected new files:

- `game/__init__.py`;
- `game/__main__.py`;
- `game/app.py`;
- `game/presentation.py`;
- `game/projection.py`;
- `game/assets.py`;
- `game/data/assets.json`;
- `game/data/tile_bindings.json`;
- `game/assets/environment/ground-a1-e.png`;
- `tests/game/test_presentation_boundary.py`;
- `tests/game/test_projection.py`;
- `tests/game/test_assets.py`; and
- `tests/game/test_app_smoke.py`.

A new architecture test file is allowed only if extending the current general
dependency graph would make that test less clear. Do not touch server, SDK,
transport, generated, renderer/editor TypeScript, NeuroClient, NeuroMapEditor,
or unrelated content files.

No implementation ledger, manifest, source hash ritual, compatibility file,
or generated schema is required for this bounded cut. Test results, the exact
diff, and independent reviews are sufficient evidence.

## 14. Observable acceptance matrix

### 14.1 Battlefield and cold world

1. Building `battlefield.open_ground_bright` through the public builder emits
   exactly one first `WorldInitializedEvent` before any later dynamics.
2. Its bounds, 81 unique Tile UUIDs/positions, Earth surfaces, bright resolved
   light, height zero, and empty objects/connectors match the live world.
3. No asset/path/pivot field appears in its engine state.
4. Existing battlefield catalog and cold-world tests remain green.

### 14.2 Pure sensory reducer

5. Given a named prior snapshot and one real/synthetic typed sensory delta, the
   pure reducer returns the exact expected position, visible/seen, contacts,
   effective light, modes, perception, access, and dirty state.
6. Applying the same delta through live `Senses.apply_sensory_update()` yields
   the exact same snapshot, while explicit live-owner proofs show that equal
   incoming effective modes preserve `sense_mode_sources`, differing modes
   clear sources and replace direct modes, and visual-access replay changes
   only `_last_visual_access` rather than the source `ModifiableValue`.
7. Removal-before-change behavior is proven for visible cells, entity contacts,
   and object contacts.
8. A different observer UUID is rejected without changing the prior snapshot.
9. The reducer performs no live GridMap/Entity/registry lookup; an engine reset
   after capture does not affect its result.

### 14.3 Closed interval and passivity

10. One real startup produces one valid interval containing world, direct
    character, deployment, and sensory facts in exact source order; the seed
    cursor is inside the interval, snapshot capture changes neither cursor nor
    generation, and every selected-observer sensory update is at or after that
    seed boundary.
11. Objective rows and coverage jointly preserve every `(index, Event UUID)`
    in `[start, end)` exactly once, including multiple phase versions sharing
    one lineage.
12. Only completed exact `WorldInitializedEvent` and `SensoryUpdateEvent`
    instances are deep-copied and enqueued.
13. Copied values preserve concrete class, UUID, lineage, parentage, cause UUID,
    ordering, and payload.
14. Resetting all engine runtime after capture does not change the detached
    world or sensory reduction result.
15. A `ConditionApplicationEvent`/`ConditionRemovalEvent`, Entity-bearing
    Event, or arbitrary base Event is never copied and becomes visibly
    unsupported.
16. An otherwise admitted family with non-null arbitrary `context`, a combat
    log, or an effective handler-presentation attachment is rejected from the
    async payload.
17. Negative start, seed outside `[start, end]`, end before start, end past
    current cursor, a selected-observer sensory delta before the seed, missing
    index, and generation change reject the whole interval with no partial
    enqueue.
18. The capture function registers no EventQueue callback.

### 14.4 Subjective disclosure

19. Before the first sensory delta, the detached objective world exists but no
    Tile is disclosed to the observer map. The real deployment then emits a
    completed selected-observer sensory update whose reduction yields exactly
    81 visible Tiles and 81 `BRIGHT_LIGHT` effective-light after-values.
20. Visible cells draw with their engine-resolved effective-light appearance
    key. A value/draw-semantic test with at least two distinct effective
    `LightLevel` after-values proves that the actual headless frame selects and
    records distinct treatments; it uses neither a screenshot golden nor a
    draw-call mock.
21. Seen-but-not-visible cells draw only with the fixed memory treatment.
22. Unseen cells draw neither the ground asset nor grid geometry and yield no
    player pick, Tile UUID, support elevation, Z-grid identity, or objective
    membership disclosure.
23. Object/entity contacts remain separate from Tile visibility.
24. A sensory Event for another observer cannot mutate this target and is
    closed as `not_disclosed`.
25. Existing combat-log projection can produce different objective and
    subjective rail text without a new Event/log model.

### 14.5 Projection and picking

26. Forward/inverse round trips recover representative positive, negative,
    boundary, and map-center cells in all four quadrants.
27. Cursor-centered zoom preserves the same unzoomed world point within
    floating-point tolerance.
28. Camera pan and window origin do not change recovered engine coordinates.
29. A current `battlefield.elevation_proving_ground` cold world projects every
    support at `(0, -64 * elevation_steps)` relative to the same XY contact.
30. Given an explicitly observer-disclosed support set from the current
    `battlefield.elevation_proving_ground`, height-aware picking recovers the
    exact engine position, Tile UUID, elevation steps/feet, and Z-grid offset
    for real elevated cells in all four quadrants.
31. An overlap chooses the visually foremost valid support by the same painter
    rank used for drawing.
32. Painter order is deterministic and independent of pan, zoom, input order,
    z-grid identity, and elevation value.

### 14.6 Assets and pygame

33. The catalog accepts the exact copied PNG and Earth binding.
34. Missing file, `..`/absolute path escape, unknown binding, wrong dimensions,
    duplicate asset ID, and malformed JSON fail visibly.
35. The original alpha Surface is loaded once; derived variants are reused
    only at finite `(zoom level, appearance key)` combinations.
36. Under SDL's dummy video driver, the real pygame app initializes a display,
    loads the PNG, consumes the real detached startup interval, draws all 81
    observer-authorized Earth Tiles with bright appearance evidence in one
    frame, updates diagnostics, and shuts down.
37. The smoke test waits on the terminal/result queue, never a sleep.

### 14.7 Async, clocks, terminal, and reset

38. Enqueuing returns without waiting for any frame or animation duration.
39. Before presentation consumes the batch, `E > R == D` is observable.
40. After reduction but before a matching display frame, `E == R > D` is
    observable.
41. After the frame, `E == R == D` and the one terminal is settled.
42. Every source queue index has exactly one final disposition tied to its
    Event UUID, including unsupported versions that never crossed the queue.
43. Queue empty without displayed parity does not settle the terminal.
44. Missing asset, reducer failure, false represented state, or parity mismatch
    produces one failed terminal and visible diagnostics.
45. Reset between capture and reduction/display cancels the old interval;
    stale work changes neither scene nor new-generation clocks.
46. There is exactly one terminal for the startup interval and no per-Event,
    per-asset, per-Tile, or per-frame terminal collection.

### 14.8 Architecture

47. No `dnd` module imports `game` or pygame.
48. No `game` module imports server/SDK/services/deprecated/AI or external
    editor/client source.
49. The active Python graph including `/game` has no cycle, function-local
    import, `TYPE_CHECKING` workaround, or dynamic project import.
50. Source scans find no new manager/service/controller, Event subclass,
    callback registration, reflection-based passivity scanner, generic asset
    inference, or live renderer polling.

Tests must assert the stable value/visible boundary. They must not freeze
private function call order, exact module-internal collection shape, arbitrary
font pixels, or pygame draw-call mocks.

## 15. Test lanes and commands

### 15.1 Fast value lane

Run the new pure boundary/projection/assets tests plus the exact existing
world/sensory contracts they extend:

```bash
uv run pytest -q \
  tests/game/test_presentation_boundary.py \
  tests/game/test_projection.py \
  tests/game/test_assets.py \
  tests/engine/test_world_entity_initialization.py \
  tests/engine/test_subjective_combat_log_replay.py \
  tests/engine/test_senses_light_stealth.py
```

### 15.2 Pygame smoke lane

The test itself sets SDL's dummy video/audio environment before pygame is
initialized and waits on the semantic terminal:

```bash
uv run pytest -q tests/game/test_app_smoke.py
```

It uses the real copied PNG and real software Surface. Mocking pygame, replacing
the asset with an in-memory square, or sleeping until a guessed frame time does
not prove the feature.

### 15.3 Architecture and type lane

```bash
uv run pytest -q tests/architecture
uv run pyright game dnd/blocks/sensory.py dnd/scenarios/battlefield_catalog.py
uv run python -m compileall -q game dnd tests/game
git diff --check
```

### 15.4 Broad regression lane

Run the active engine, progression, and architecture suites that own the
touched public behavior. Preserve and report pre-existing governed exclusions;
do not create stubs in excluded/deprecated/server areas to make unrelated
collection green.

### 15.5 Human visual proof

After automated lanes pass:

```bash
uv run python -m game
```

Manually verify pan, every zoom step, all four quadrants, grid toggle, hover
diagnostics, both rails, unsupported count, E/R/D convergence, and clean close.
Record the observed result; do not promote a screenshot to a general golden.

## 16. Ordered implementation slices and stop points

### Slice 0 — dependency and exact source preflight

- confirm the pygame-ce release resolves on Python 3.12;
- confirm the exact source PNG hash/dimensions and copy only that file;
- add the dependency/lock and minimal `/game` package shell; and
- add/extend the dependency-DAG gate before application modules grow.

Stop if pygame-ce cannot initialize under both the real local display and SDL
dummy driver, or if adding `/game` reveals a real pre-existing import cycle.

### Slice 1 — pure sensory replay extraction

- add value-equivalence tests first;
- extract the one pure snapshot reducer;
- delegate live `Senses.apply_sensory_update()` to it; and
- run the complete existing sensory/light/replay lane.

Stop if any live Senses behavior differs. Do not patch pygame around an engine
replay discrepancy.

### Slice 2 — authored world and V-0 capture

- add the Earth battlefield and cold-world proof;
- implement the primitive objective/subjective rail capture;
- implement exact interval validation;
- implement only the two admitted family cases and detached copies;
- implement the cold target reducer and coverage; and
- prove engine-reset independence and negative unsafe Events.

Stop before pygame until every original interval source record has an exact
disposition and no unadmitted Event survives outside the objective queue.

### Slice 3 — projection and first asset

- implement one pure projection/camera owner;
- prove four-quadrant forward/inverse behavior;
- prove real elevation-proving-world projection and support picking;
- add the two minimal JSON files and exact asset loader; and
- prove deterministic ground materialization and asset failures.

Stop if Earth cannot be bound without a fallback or if projection and picking
do not share an exact inverse.

### Slice 4 — pygame/async vertical seam

- compose the real startup interval and observer seed;
- add the interval and terminal queues;
- render terrain, grid, rails, and diagnostics;
- implement controls and semantic displayed evidence;
- close E/R/D and the one terminal; and
- add the real SDL-dummy integrated smoke.

Stop before any actor marker, object Sprite, animation, door/torch reducer, or
world-modification reducer.

### Slice 5 — final acceptance

- run every lane in Section 15;
- perform the human visual proof;
- inspect the exact diff for scope and unrelated dirty-work preservation;
- obtain correctness/information-boundary review;
- obtain anti-slop review;
- obtain anti-OOP/ECS/dependency-DAG review; and
- repair only findings inside this plan, then rerun affected evidence and all
  three reviews.

No implementation slice is accepted merely because code compiles or the window
opens.

## 17. Rejected shortcuts

- copying all Events because Pydantic happens to deep-copy the happy path;
- invoking `model_dump()` on arbitrary Events and treating the result as safe;
- deleting or mutating objective Events after capture;
- adding a `to_subjective()`, `to_render_event()`, or polymorphic render method
  to the Event hierarchy;
- adding a presentation-event enum or discriminated union;
- instantiating `Senses` in the renderer;
- reimplementing FOV/light/perceivability in `/game`;
- importing the existing AI/server subjective frame hierarchy;
- binding dirt art to the existing default Stone floor;
- encoding asset IDs in Tile or battlefield mechanics;
- reading the external NeuroMapEditor path at runtime;
- loading every asset in either editor repository;
- scanning directories or filenames to infer bindings;
- using an EventQueue passive callback because it already exists;
- waiting on queue emptiness or `sleep()` as presentation completion;
- allowing a full queue to block engine execution;
- advancing D before a frame with target/display parity was published;
- deriving painter rank from elevation, z-grid identity, insertion order, pan,
  or zoom;
- using Sprite rectangles for ground picking;
- using a procedural diamond when the required PNG fails;
- adding a new GridMap rectangle API for one 9 x 9 builder;
- refactoring existing battlefields/content beyond the one direct addition;
- touching the unaccepted world-modification candidate to make this slice look
  more complete; and
- continuing into V-2 after this cut passes.

## 18. Completion boundary and immediate successor

This plan is complete when one command opens the minimal pygame scene and one
automated semantic terminal proves:

- the current engine authored and committed the world/observer;
- one exact interval was synchronously inspected;
- only the two audited Event families crossed async ownership;
- the existing sensory calculation produced the observer target;
- Earth art and grid were drawn through exact four-quadrant projection;
- mouse diagnostics recover engine coordinates and support height;
- every source Event is visible in objective coverage;
- subjective output reveals only authorized facts;
- E/R/D converge without making mechanics wait for rendering; and
- no second mechanics world, event ontology, callback chain, import cycle, or
  asset inference system was introduced.

The next plan completes the rest of V-1 by extending the same proven seams to
water, one directional wall family, the matching door frame/leaf, one honest
light-bearing object, real ordinary after-value Events, incremental
`WorldModifiedEvent` materialization after its own acceptance, and one displayed
elevation composition case. It may not change the V-0 boundary merely to make
those new families easier.

## 19. Plan validation protocol

Before implementation, three independent reviewers must read this exact
candidate against the current checkout and governing roadmap:

1. **correctness/information-boundary reviewer** — Event passivity, interval
   closure, sensory replay reuse, subjectivity, clocks, reset, and testability;
2. **anti-slop reviewer** — unnecessary types/modules/queues/records, premature
   generality, excess gates, and inflated scope; and
3. **anti-OOP/ECS/dependency-DAG reviewer** — Entity/component ownership,
   sensory ownership, import direction, callback/reflection pressure, and
   shadow state/ontology risks.

Any rejection requires a written correction to this file and a complete reread
by all three reviewers. Approval authorizes only the bounded implementation
described here.

## 20. Review record

The final substantive candidate was independently approved on 2026-09-03 by:

- the correctness/information-boundary reviewer;
- the anti-slop reviewer; and
- the anti-OOP/ECS/dependency-DAG reviewer.

Review corrections made before acceptance:

- source-record coverage uses queue indexes and preserves Event UUID/lineage
  evidence without collapsing phase versions;
- the one envelope carries its sanitized rows, initial unsupported outcomes,
  indexed admitted Events, and exact observer seed boundary without a side
  channel;
- `R` records completed reduction/classification while `D` and
  `represented` require a matching published frame;
- the pure sensory reducer preserves live source ownership, does not inherit
  the recursive runtime validator, and cannot double-apply pre-seed deltas;
- effective-light treatment participates in actual display parity and the
  real startup must disclose and draw all 81 Tiles; and
- player grid/picking considers only visible-or-remembered supports, never
  unseen objective geometry.

The reviewers found no remaining correctness, slop, OOP/ECS, dependency-DAG,
or sequencing blocker. This review record changes no implementation contract;
the accepted scope remains exactly Sections 1 through 19.
