# Pygame P0 NeuroClient system study

Status: **read-only architecture study; not an implementation plan**

This document studies the live WSL NeuroClient as evidence for the first
pygame-ce battlefield seam. It does not propose a TypeScript port and does not
treat NeuroClient as map or asset-placement authority. The purpose is to
identify what is principled and reusable, what should be collapsed for an
in-process Python runtime, and what must not be carried forward.

The audited NeuroClient checkout was:

- repository: `/home/tommaso/Dev/NeuroClient`
- commit: `d274f2d`
- latest commit date/subject: `2026-08-11 flockfailed`
- worktree: clean at the time of study

The relevant engine checkout is the current repository containing this study.

## Source authority is deliberately split

The three WSL repositories answer different questions. They must not be blended
into one inherited client architecture:

| Source | Authority for the pygame work | Not authority for |
|---|---|---|
| `/home/tommaso/Dev/NeuroMapEditor` | macro/fine lattice, explicit Z-grid projection, visual composition, exact asset occurrence presentation, painter order, transformed bounds, and alpha picking | game mechanics, observer knowledge, event reduction, actor behavior |
| `/home/tommaso/Dev/MapEditor` | older authoring ergonomics and the original fantasy asset evidence/catalog | the new runtime world model or reconstruction machinery |
| `/home/tommaso/Dev/NeuroClient` | runtime input lessons, asynchronous presentation, layered actor sprites, animation, VFX evidence, diagnostics, and failure history | terrain placement, structural ownership, visibility mechanics, or an event type system to port |

The live NeuroMapEditor checkout inspected for this correction was at commit
`8f11814` with existing local work in progress. Its read-only evidence is used
here only for stable implemented contracts corroborated by source and tests;
none of its local changes were modified.

NeuroMapEditor's clean model already gives the correct separation:

- `ZGrid` owns a stable height identity and an explicit pixel projection
  offset; neither value is painter order;
- `VisualTilemap` owns composition role and visibility, independently of world
  position and walkability;
- `VisualPlacement` owns an asset identity, one geometric anchor, one Z-grid,
  one visual composition membership, and occurrence presentation;
- `SpritePresentation` owns pivot, occurrence offset, scale, tint/alpha,
  optional affine evidence, animation metadata, and material role; and
- selection first resolves authoritative grid contact; transformed bounds and
  source-alpha sampling are only the Sprite narrow phase.

P0 should translate those small laws into Python/pygame-ce. It should not port
NeuroMapEditor's Unity import compiler, causal-height inference, enclosure
repair, filename inference, asset matching, or editor store.

## Executive verdict

P0 and P1 should be treated as one small vertical seam. Drawing an isometric
diamond without proving input, assets, height, event ingestion, subjectivity,
presentation lag, and diagnostics would validate almost nothing.

The useful NeuroClient design is concentrated at its boundaries:

1. pure grid-to-screen and screen-to-grid transforms;
2. ground-cell picking instead of sprite-rectangle picking;
3. camera input owned by the renderer rather than the game model;
4. exact asset identities and joined asynchronous loads;
5. renderer initialization before the event source starts;
6. explicit separation between engine progress and presentation progress;
7. result-bearing presentation completion and generation cancellation;
8. fail-closed subjective visibility;
9. objective diagnostics kept separate from player rendering; and
10. semantic render-parity and event-coverage evidence.

The parts that should not be ported are equally clear:

1. server, SSE, SDK, reconnect, and replication-journal machinery;
2. `SubjectivePresentationCue -> VisualTransaction -> ClipIntent -> Clip`
   as a second ontology beside engine Events;
3. a large compiled presentation bundle and recipe compiler before a real
   pygame presentation need exists;
4. a mixed global store containing projection, staged animation, UI caches,
   authoring state, and diagnostics;
5. full-board string signatures and broad rebuilds for local changes;
6. fixed 64 x 32, zero-based, planar-only battlefield assumptions;
7. canonicalized structural edges that can erase the engine's actual
   tile-owned, four-sided wall and door identity;
8. client-side reconstruction of visibility or mechanics; and
9. procedural placeholder terrain as the primary map renderer.

The pygame seam should consume detached copies of the engine's **existing
concrete Event subclasses**. It should not invent presentation-event DTOs.
Objective and subjective consumers remain in the same Event type space. A
small interval envelope may carry queue identity and cursor bounds, but it is
not another event model.

## Corrected P0 scope

P0 is one executable renderer seam containing all of the following:

- pygame-ce application shell and frame pump;
- MapEditor-compatible 128 x 64 macro-cell projection;
- renderer-local WASD pan and zoom;
- camera-aware grid drawing and tile highlighting;
- exact mouse-to-grid diagnostics;
- support-height/Z-grid projection and picking diagnostics;
- a minimal data-driven asset catalog and cache;
- the already-selected dirt, water, wall, door, and torch assets;
- renderer-local scene state initialized from `WorldInitializedEvent`;
- incremental scene updates from ordinary engine Events, especially
  `WorldModifiedEvent` and `SensoryUpdateEvent`;
- objective event and combat-log text rails;
- one active observer's subjective scene/log rail;
- an asynchronous presentation queue whose displayed state may lag engine
  execution; and
- fail-visible coverage for every consumed event.

Layered actors and full action animation follow in the next renderer phases,
not as optional leftovers. P0 must already have the queue, acknowledgement,
generation, exact asset identity, scene-anchor, and diagnostics contracts they
will use.

## What NeuroClient actually does

### Composition and startup

The current production entry is `app/src/main.ts` (636 lines). It:

1. initializes persistence and presentation data;
2. creates Pixi;
3. creates a `pixi-viewport` camera;
4. creates the complete layer stack;
5. initializes `sceneRenderer` and its presentation runtime;
6. installs the viewport/input controller;
7. bootstraps or joins the server game;
8. initializes static-board synchronization;
9. mounts UI/debug surfaces; and
10. materializes the committed subjective projection.

One startup law is particularly valuable. The scene renderer and its sole
production presentation queue are installed before the subjective event stream
can deliver work. This was introduced after NeuroClient had previously allowed
events to arrive before a visual scheduler existed.

The large composition root itself is a warning. It is not evidence that all of
those responsibilities belong in one object. Pygame P0 should have a small
composition entry that wires independently owned state and loops, rather than
becoming a second 600-line `main`.

### Current high-level event/presentation flow

NeuroClient currently follows this shape:

```text
server bootstrap / SSE
        |
        v
SubjectiveReplicationClient
        |
        v
SubjectiveReplicationJournal
  - authoritative replica may advance
  - presentation replica waits
        |
        v
exact presentation head coordinator
        |
        v
SubjectivePresentationCue mapper
        |
        v
VisualTransaction / ClipIntent graph
        |
        v
PresentationRuntimeHost / ClipQueue / dispatcher
        |
        v
Pixi scene reaches and proves projected state
        |
        v
journal presentation head commits
```

Objective Events travel through a second, independently authorized diagnostics
connection. They populate debug history and parity evidence but never drive
player rendering.

This architecture repaired several real network-client problems. It is not the
right literal architecture for an in-process Python client. The journal,
transport identity, reconnect policy, SDK projection, compiled cues, and
client-side transaction ontology are mostly conversion machinery required by
the server boundary.

### Isometric projection and grid

`app/src/iso.ts` contains a clean fixed-orientation transform:

```text
screen_x = (grid_x - grid_y) * tile_width / 2
screen_y = (grid_x + grid_y) * tile_height / 2
```

It also contains the exact inverse and rounds the fractional coordinate to a
ground diamond. `app/src/grid.ts` repeats the same inverse in a shader and draws
the whole grid with one mesh. Hovering changes only two shader uniform values.

What is good:

- the forward and inverse formulas agree;
- coordinates are transformed in world space, after screen-to-world camera
  conversion;
- hover state is renderer-local;
- repeated pointer movement inside one tile performs no repeated write;
- the pointer resolves a ground diamond, not a sprite bounding rectangle; and
- selecting an entity means selecting the visible occupant of the resolved
  cell.

What is not reusable as-is:

- tile size is hard-coded to 64 x 32 while our first MapEditor seam is
  `macro128`, 128 x 64;
- the shader assumes grid cells begin at `(0, 0)` and checks only `cols/rows`;
- there is no support-height or Z-grid offset;
- there is no four-quadrant camera rotation;
- the picker produces one planar candidate and cannot resolve overlapping
  elevated contacts; and
- grid, fog, and light duplicate projection formulas in separate shaders.

Pygame should keep one pure projection owner and have drawing, picking,
ordering, fog, and diagnostics all call it.

### Camera and controls

`app/src/ui/boardViewportController.ts` owns transient camera and pointer
state. It provides:

- middle-button drag;
- smooth wheel zoom;
- zoom clamping;
- WASD/arrow-key pan on the frame ticker;
- keyboard suppression while UI owns focus;
- canvas-to-world pointer conversion;
- hover debouncing; and
- resize handling.

This ownership is good. Camera state is presentation state and does not enter
the engine.

The implementation itself is browser/Pixi-specific and incomplete for our
needs. There is no camera rotation and no elevated picking. Pan is fixed in
screen/world axes and is not defined relative to a rotated battlefield. P0
should preserve the ownership boundary, not the controller implementation.

### Depth and visual anchors

`app/src/render/worldDepth.ts` orders cells principally by `x + y`, reserves
small bands for structures, entities, objects, and effects, and adds a stable
fractional tie derived from identity. `visualAnchors.ts` distinguishes the
ground contact from the authored 128-pixel actor rig origin.

These are good ideas:

- physical depth dominates insertion order;
- same-depth ties are deterministic;
- a sprite's art rectangle does not define its gameplay contact; and
- body, shadow, and VFX anchors can differ while sharing one ground fact.

The exact formulas are planar and fixed-camera. They do not consume support
height, Z-grid projection offset, camera quadrant, or MapEditor asset pivots.
Pygame must derive ordering from the active projection context and explicit
asset contact metadata rather than copying the numeric bands.

### Static terrain, walls, doors, and objects

`app/src/tiles.ts` primarily draws procedural diamonds, cubes, panels, chests,
lights, levers, hazards, and generic markers. Tile material is inferred from
small keys such as `water.png` and `wall.png`.

`staticBoardSync.ts` computes large string signatures for geometry, effects,
objects, structures, fog, and light. It then either updates a retained subset
or destroys and rebuilds broad layer contents.

This is not the map renderer we want. It was useful as a debug/product
baseline, but it does not load the MapEditor terrain library or preserve its
pivots, affine offsets, Z-grid offsets, or orientation variants.

There is also a direct model mismatch. NeuroClient projects SDK
`structural_edges` through canonical north/east edge ownership. The current
engine owns a `DirectionalWall` or `DirectionalDoor` as one world item placed
on one explicit side—north, east, south, or west—of one Tile. Two incident
Tiles may each own their own adjacent boundary item. The renderer must retain
those distinct objects and placements; it cannot collapse them into one
canonical between-cell edge.

The only static-board principle worth retaining is incremental reconciliation
by stable Tile/item/connector identity. P0 should reduce exact
`WorldInitializedEvent`/`WorldModifiedEvent` after-values into small renderer
indexes and change only the affected display nodes.

### Asset loading

NeuroClient has three relevant levels:

1. `SpriteAssetRegistry.ts` loads one image, slices exact directional rows and
   frames, configures nearest-neighbor sampling, caches the derived frames,
   and joins later consumers through Pixi's cache.
2. `presentationAssetManifest.ts` compiles authored media into immutable asset
   identities, sources, frame metadata, bundle identities, and revision keys.
3. `PresentationAssetService` adds pending-request joining, renderer texture
   limits, leases, retention counts, unloading, failure policy, and bounded
   diagnostic evidence.

The core principles are strong:

- callers ask for exact asset IDs;
- frame layout is data, not guessed from a filename at render time;
- concurrent loads of one asset are joined;
- nearest-neighbor sampling is configured once;
- a complete layered appearance becomes active atomically only after all
  required frames are ready;
- stale asynchronous loads are generation/id fenced; and
- load failures produce structured, bounded evidence.

The full service is much too large for P0. Its manifests, bundles, digests,
leases, pinning, GPU-limit preflight, Studio sharing, projectile authoring, and
hot replacement solve a mature web-client problem.

Pygame P0 needs one small JSON catalog and one cache with:

- stable semantic asset ID;
- exact file path;
- image kind;
- frame rectangle/count when animated;
- pivot/contact point;
- orientation/camera variant identity;
- scale and optional occurrence offset;
- alpha/collision-mask metadata only when actually used;
- one load-in-flight per asset; and
- a fail-visible missing/invalid asset record.

There must be no filename inference, similar-name fallback, image reconstruction,
bundle compiler, lease manager, or asset autodetection in P0.

The catalog shape should be reduced from NeuroMapEditor's existing data rather
than invented from NeuroClient. Its current fantasy catalog already records
stable semantic ID, exact URL, category, pixel dimensions, pivot, occurrence
offset, scale, tint, alpha, optional affine/animation/material data, source
identity, and exact-match status. Its palette groups terminal `E/N/S/W`
variants into asset families and keeps direction cycling (`E,N,S,W`) separate
from its wall painter tie order (`E,S,W,N`).

For the MVP, we should hand-author a small checked subset of that data for the
selected dirt, water, wall, door, and torch families. We should not run or port
the 1,882-asset generator at application startup. Asset-family membership and
camera-facing selection are explicit data; a missing variant is a visible
catalog error, not an invitation to rotate the PNG or guess from its name.

### Layered actors

`AnimatedEntity.ts` is the most useful future actor reference, not a P0 terrain
template. Its positive design includes:

- one shared animation clock across body/equipment layers;
- explicit layer order;
- 8 directional rows;
- exact 128 x 128 frames;
- atomic clip/appearance readiness;
- stale-load cancellation;
- distinct ground, body, and shadow anchors;
- visual modifiers that recompose from authoritative base appearance rather
  than permanently mutating it; and
- entity grid position owned by the presentation runtime while a clip runs.

The current actor shell is also large and contains several controllers and
presentation concerns that should not be ported wholesale. When actors enter
scope, the rig layout and shared clock can be recovered independently from the
web client. P0 only needs to leave a clean scene-node and asset-cache boundary
for that future work.

This recovery is an expected phase sequence, not an indefinite deferral:

1. **P0 — map seam:** NeuroMapEditor projection/placement laws, minimal terrain
   and structures, input/picking/Z diagnostics, event ingestion, async display
   lag, coverage, and text rails.
2. **Actor phase — complete entity visual system:** inventory and port the
   NeuroClient entity asset bindings, body/equipment layers, shared animation
   clock, direction/clip selection, shadows, visual status overlays, atomic rig
   readiness, and event-driven movement/attack/reaction/death transitions.
3. **Effects phase — complete animation/VFX integration:** recover action,
   projectile, impact, persistent-area, light-emitter, and spell VFX assets and
   bind them to the same ordinary engine Event stream and presentation
   terminals.

The later phases may expand the asset catalog and scene nodes, but they must
not replace the P0 event bridge, introduce presentation-event DTOs, or let
animation state become game authority.

### Visibility and light

NeuroClient now consumes backend-projected subjective visibility rather than
recomputing FOV. In subjective mode:

- absence of a committed perspective hides actors and objects;
- visible cells are clear;
- seen cells receive dim memory fog;
- unseen cells are opaque;
- visible objects and entities are explicit sets; and
- effective subjective light replaces objective Tile light for disclosed
  cells.

The fail-closed behavior and the distinction between cell visibility, entity
visibility, object visibility, and effective light are correct and should be
retained.

The current client still contains presentation policy that should be treated
with caution:

- remembered corpse visibility is partly renderer-owned history;
- wall visibility is inferred from adjacent visible/seen cells;
- solid wall cells and canonical structural edges follow different client
  rules; and
- missing effective light defaults to darkness inside the shader.

For pygame, the engine's `Senses`/`SensoryUpdateEvent` is the subjective spatial
authority. The renderer may apply those delivered after-values and style
visible versus remembered geometry, but it must not recompute line of sight,
darkvision, invisibility, hidden state, magical darkness, object
perceivability, or boundary mechanics.

NeuroClient's light implementation uses a one-texel-per-cell categorical map
and a multiply shader. This is a useful first visual approximation because the
engine has already resolved physical and subjective light categories. Pygame
can initially tint or overlay each disclosed support cell. The standing torch
sprite/flame is a separate object visual; it is not itself the source of rules
illumination.

### Objective and subjective text rails

NeuroClient correctly preserves two distinct debug products:

- the player's subjective human-readable combat log; and
- the objective Events/objective combat log available only as diagnostics.

The objective stream never drives player rendering, picking, or command
authority. This separation was essential for debugging desynchronization and
must remain in P0.

The in-process implementation is simpler: one detached engine interval can be
given to an objective logger and separately reduced for the active observer.
No second server request, polling loop, authorization client, or cursor stream
is required.

### Presentation queue and acknowledgement

The present NeuroClient queue is materially better than its historical
versions. `ClipQueue` now:

- returns an accepted or rejected result;
- exposes a terminal outcome of completed, failed, or cancelled;
- owns a cancellable generation;
- has an execution deadline;
- retains bounded lineage outcomes; and
- distinguishes causal from decorative work.

The current presentation head also checks scene convergence before advancing
the journal presentation cursor. These repairs directly address the older
failure in which `queue idle` was mistaken for `success` and resync left stale
sprites alive.

The principles should be retained, but not the web implementation. For pygame:

- engine execution is never blocked by visual time;
- copied event intervals enter a bounded async bridge;
- the renderer owns displayed state and animation time;
- a player-side scripted/input action may wait for its exact presentation
  terminal before the next player command is submitted;
- enemy mechanics may continue and accumulate presentation work;
- `queue empty` is not presentation proof;
- presentation success requires a terminal disposition for every required
  event plus displayed-scene convergence; and
- reset/restart retires one renderer generation so old work cannot mutate the
  new scene.

This does not require callback chains. It is ordinary event ownership plus
awaitable queue results.

### Diagnostics and parity

NeuroClient's diagnostic direction is worth preserving:

- every delivered subjective cue is recorded before mapping;
- each cue receives an explicit disposition;
- transactions and intents record lifecycle terminals;
- diagnostics are bounded;
- asset failures are copyable evidence;
- reset/rebuild boundaries are recorded;
- the expected semantic projection is compared to semantic evidence from the
  actual Pixi graph; and
- failures remain visible instead of selecting a guessed fallback.

The current implementation is more elaborate than P0 needs because it audits
SDK frames, cues, transactions, intents, Pixi nodes, server parity, and persisted
incidents.

P0 needs one small coverage ledger keyed by existing event UUID/lineage. Every
consumed event must end in one of these closed outcomes:

- `represented`: changed visible scene or scheduled visible animation;
- `state_only`: correctly reduced but requires no distinct visual;
- `diagnostic_only`: intentionally belongs only in text/debug evidence;
- `not_disclosed`: removed by the observer reduction;
- `unsupported`: no visual rule exists yet; show a visible debug badge; or
- `failed`: a declared visual rule or asset failed.

`unsupported` must not stop the scripted encounter. It must be impossible to
miss in the log. A required initialization asset or invalid world projection
may fail startup because no truthful scene can be constructed; a missing
optional event visual must remain local and inspectable rather than destroy the
whole application.

## Good, simplify, reject

| NeuroClient subsystem | Judgment | Pygame consequence |
|---|---|---|
| `iso.ts` forward/inverse algebra | **Keep principle** | One parameterized 128 x 64 projection owner with an exact inverse. |
| Ground-diamond entity picking | **Keep** | Resolve gameplay contact first; never select by sprite rectangle. |
| `boardViewportController` ownership | **Keep boundary** | Camera/input stays renderer-local; rewrite in pygame. |
| Shader grid | **Simplify** | Draw/cache a debug surface; do not add a shader abstraction for P0. |
| `worldDepth` deterministic ties | **Keep principle** | Projection-aware painter key plus stable identity tie. |
| Fixed planar depth formula | **Reject formula** | Include support height, camera quadrant, and asset contact. |
| Procedural `tiles.ts` battlefield | **Reject as product renderer** | Use the MapEditor asset subset and exact engine world facts. |
| Static-board content signatures | **Reject** | Apply identity-addressed Event after-values incrementally. |
| Canonical structural edges | **Reject** | Preserve each concrete tile-owned wall/door object and side. |
| `SpriteAssetRegistry` | **Keep core** | Exact catalog identity, frame slicing, nearest sampling, cache. |
| Full `PresentationAssetService` | **Collapse** | Small JSON catalog, joined loads, local diagnostics. |
| Atomic layered actor readiness | **Keep for later** | Do not show half-loaded rigs when actor work begins. |
| Subjective journal | **Transport-specific** | Replace with one in-process detached-event bridge. |
| Subjective cue mapper | **Reject** | Consume the same concrete Event subclasses; no cue DTO ontology. |
| Presentation bundle/recipes | **Defer/reject for P0** | Add data only when a real repeated visual binding requires it. |
| Result-bearing queue terminal | **Keep** | Exact awaitable success/failure/cancel outcome per interval/root. |
| Generation cancellation | **Keep** | Retire all stale renderer work on reset/restart. |
| Mixed Zustand store | **Reject** | Explicit small objective, observer, displayed, UI, and diagnostic owners. |
| Fail-closed visibility | **Keep** | Missing observer projection reveals nothing. |
| Client FOV/mechanics inference | **Reject** | Apply engine sensory facts only. |
| Objective debug rail | **Keep** | Same copied interval, separate non-rendering consumer. |
| Render parity/coverage | **Keep and simplify** | Semantic scene manifest plus closed event dispositions. |
| Server parity polling | **Reject for in-process** | Compare renderer reduction directly against copied cold values. |

## The pygame event seam implied by the study

### Same Event space, three different clocks

There are three distinct notions of progress, but only one event type system:

```text
engine clock
  authoritative mechanics have executed through event cursor E

renderer reduction clock
  detached Event values have been reduced through cursor R

display clock
  animations/pixels have visibly settled through cursor D

E >= R >= D is legal
```

The engine Event classes are not converted into presentation Events. A tiny
queue envelope may contain:

- EventQueue generation UUID;
- inclusive start cursor;
- exclusive end cursor;
- the detached tuple of concrete Event copies; and
- optional causal/turn identity already present in the Events.

That envelope is transport metadata inside one process. It does not duplicate
event semantics.

### Safe capture boundary

The current engine already supplies the pieces:

- `EventQueue.generation_id()`;
- `EventQueue.event_cursor()`;
- `EventQueue.iter_events_since()`;
- passive per-event, atomic-sequence, and completed causal-batch observers;
- deep-copyable Pydantic Event values; and
- action-owned event batches that include nested reactions/child actions in
  storage order.

The P0 bridge should copy the closed interval before yielding to another task.
The accepted world-modification tests already prove the essential pattern:
validate generation, validate `[start, end)`, deep-copy each Event, and
revalidate generation after the copy.

The event callback must perform no rendering and no blocking wait. It only
captures a closed value interval and enqueues it.

### Objective reduction

The objective debug consumer records every copied event version in storage
order. The objective scene reducer uses only the exact phases/facts that own
renderer state, for example:

- `WorldInitializedEvent` for the cold battlefield;
- `WorldModifiedEvent` for Tile/object/connector changes;
- entity creation/placement/movement/lifecycle events for actors; and
- ordinary completion Events for coverage and future animation.

It never reads the live mutable engine after the interval is detached.

### Subjective reduction

The engine already has two authoritative subjective ingredients:

1. `Senses` plus `SensoryUpdateEvent` owns visible/seen cells, complete
   perceived entity/object contacts, effective subjective light, sense modes,
   visual access, and path dirtiness.
2. `project_combat_log()` returns the **same `CombatLogEntry` model** with
   event-time unauthorized identity/location facts censored.

There is not currently one active, general-purpose subjective projector for
all concrete engine Event subclasses. The old server/manual replication
fixtures contain broader projection machinery, but P0 must not revive their
SDK/cue stack.

Therefore the first renderer seam may trust `SensoryUpdateEvent` for spatial
knowledge and `project_combat_log()` for text, but it must treat a general
observer-safe action Event stream as a named dependency. Its eventual law is:

```text
objective copied Event value
        |
        v
event-time observer reduction
        |
        v
same concrete Event subclass with unauthorized facts unavailable/censored
```

It must not become `CanonicalEventView`, `SubjectivePresentationCue`, or a
second discriminated event union. The implementation details of inaccessible
required fields require their own surgical design review; this study does not
pretend that problem is already solved.

### Renderer-local state is not a second game world

The renderer necessarily owns a projection of what it can currently draw. It
must not own mechanics.

The minimum useful distinction is:

```text
reduced target scene
  cold, renderer-neutral after-values obtained from copied Events

displayed scene
  mutable sprites, animation positions, frame counters, camera, and overlays
```

The target scene tells presentation where it must eventually converge. The
displayed scene may lag while animation plays. Neither may answer movement
legality, targeting legality, light propagation, visibility, damage, or AI
questions.

### Presentation terminal

An interval/root is presented only when:

1. every disclosed event has a closed coverage disposition;
2. every required animation has completed successfully or the event was
   explicitly `state_only`/`diagnostic_only`;
3. every required asset load has succeeded;
4. the displayed semantic scene matches the reduced target scene for the
   fields owned by that interval; and
5. the renderer generation is still current.

Queue emptiness alone is insufficient.

## Projection and placement authority from NeuroMapEditor

NeuroMapEditor supplies the map-side rules that NeuroClient lacks. The P0
translation should preserve these relationships while shrinking the editor
model to the needs of one authored encounter.

### Independent facts

One render occurrence combines independent facts:

```text
engine Tile/world-item identity and placement
  + renderer Z-grid projection context
  + semantic asset-family binding
  + occurrence presentation (pivot/offset/scale/orientation)
  + visual composition role
  = one displayed occurrence
```

Changing height reprojects the occurrence; it does not move the engine `(x,y)`
or change painter class. Changing visual composition does not change gameplay
height. Nudging a Sprite pivot or occurrence offset does not change its world
owner. These separations are essential for elevated tiles, walls, doors, and
later actor rigs.

### Anchors and asset-family placement

NeuroMapEditor can represent contacts, fine child cells, edges, and corners.
P0 only needs the smallest admitted subset:

- Tile surfaces use one macro-cell ground contact;
- ordinary world items use the owning Tile contact plus explicit occurrence
  pivot/offset metadata;
- each `DirectionalWall`/`DirectionalDoor` retains its engine-owned Tile side
  and selects the matching authored orientation variant;
- the door frame and stateful leaf may be two display occurrences referencing
  one engine `DirectionalDoor`; and
- an elevated occurrence uses the support Tile's Z-grid projection offset,
  never a per-Sprite height guess.

If a selected family later proves it requires an edge/corner anchor or fine64
child, that exact authored metadata can be admitted. P0 should not pre-port the
whole anchor union before a chosen asset uses it.

### Composition and painter order

NeuroMapEditor distinguishes planar passes (background, water, surface,
details, shadows) from spatial groups (walls, objects, roofs). Inside a spatial
group it orders by projected contact geometry, uses an explicit narrow
direction tie where needed, and finishes with stable identity. Z-grid identity,
Z level, and pixel lift are deliberately absent from the composition-group
decision.

P0 needs a small explicit subset of those passes for its selected assets. It
must not revive arbitrary `sortOffset`, one giant Z band, or insertion order.
The painter key must remain deterministic under pan/zoom and must be derived
again for each camera quadrant.

### Picking

NeuroMapEditor's two-stage rule is the correct model:

1. invert the exact active projection to obtain authoritative support-cell/Z
   candidates;
2. for object inspection only, query transformed Sprite alpha bounds and
   inverse-transform the click into the source PNG alpha mask.

Transparent PNG rectangles therefore cannot steal ground selection, while a
wall or object can still be selected by its visible pixels. The debug overlay
must expose both stages rather than collapsing them into one guessed hit.

## Pygame projection requirements

### Macro128

The first map uses a 128 x 64 cell footprint:

```text
screen_x = (camera_x - camera_y) * 64 + origin_x
screen_y = (camera_x + camera_y) * 32 + origin_y + z_offset_y
```

The exact sign and Z offset come from the selected NeuroMapEditor projection
context. All modules consume that one context; none repeat the formula.

### Four camera quadrants

NeuroClient has no battlefield camera rotation. P0 should represent the camera
quarter-turn explicitly from the start:

1. rotate engine `(x, y)` into camera-relative lattice coordinates;
2. project those coordinates to isometric pixels;
3. map each world cardinal orientation to the correct camera-relative asset
   variant; and
4. apply the exact inverse transform during picking.

The source PNG is never raster-rotated. Camera rotation selects one of the
authored directional assets.

### Support height and Z-grid offset

Normal NeuroClient battlefield rendering ignores support elevation. Connector
diagnostics carry endpoint elevations and locomotion intents carry elevation,
but ordinary ground, entity anchoring, fog, light, and picking remain planar.

Our engine has one support Tile per `(x, y)`, with elevation in five-foot
steps. P0 must keep gameplay position `(x, y)` unchanged and apply height only
through the renderer's projection context:

```text
engine position = (x, y)
support height  = Tile.elevation_steps
visual contact  = iso(camera_rotate(x, y)) + z_grid_offset(height)
```

This is 2D gameplay plus a visual support offset, not general 3D simulation.

### Height-aware mouse diagnostics

The mouse debugger should expose at least:

- screen pixel;
- camera/world pixel after pan and zoom inversion;
- camera quarter-turn;
- every candidate support-height projection considered;
- candidate engine `(x, y)`;
- Tile UUID;
- support height in steps and feet;
- chosen Z-grid identity/offset;
- projected ground contact;
- painter/depth key;
- whether the point lies inside the candidate diamond; and
- the final selected support.

When multiple candidates overlap, the selected Tile is the visually foremost
valid ground contact under the active painter order. Sprite alpha picking is a
later object-selection narrow phase; it must not replace ground-cell picking.

## Minimal P0 runtime shape

This is an ownership sketch, not a file/class mandate:

```text
serialized engine executor
  owns all game mechanics and EventQueue mutation
        |
        | closed, detached Event intervals
        v
bounded async bridge
        |
        +--> objective text/coverage consumer
        |
        +--> observer reduction using engine event-time sensory evidence
                    |
                    v
              renderer target scene
                    |
                    v
              presentation scheduler
                    |
                    v
              pygame displayed scene

pygame input/camera --------------------^ renderer-local only
asset catalog/cache --------------------^ exact files/frames/pivots only
```

The pygame frame pump stays on the display-owning thread. Engine mutation is
serialized elsewhere or in one explicitly scheduled task. The renderer never
calls arbitrary live engine getters while drawing; it uses the detached values
already delivered to its scene reducer.

No manager/controller/service vocabulary is required to realize this shape.
Small modules/functions can own projection, camera state, asset loading, scene
reduction, presentation scheduling, and diagnostics directly.

## P0 evidence that matters

The first seam is successful only if it can demonstrate all of these together:

1. An authored battlefield initializes from `WorldInitializedEvent`.
2. Dirt, water, one wall family, one door frame/leaf pair, and one lit/unlit
   torch render from exact catalog bindings.
3. Adjacent separately owned walls remain two separately identifiable objects.
4. Door state changes from a real engine action/Event and does not require a
   board rebuild.
5. Torch/light changes update both physical display tint and observer-effective
   light through engine events.
6. WASD, zoom, and four camera quadrants preserve the same engine Tile under
   projection/inverse-projection round trips.
7. Elevated support picking reports the correct `(x, y)` and height without
   changing engine coordinates.
8. Objective and subjective logs visibly differ when event-time knowledge
   differs.
9. Missing subjective state reveals nothing.
10. Engine execution can advance ahead of the display without corrupting the
    displayed scene.
11. A player-side barrier waits for one exact presentation terminal while
    enemy execution remains mechanically unblocked.
12. Every copied event receives a closed coverage disposition.
13. An unsupported visual creates a visible badge/log record instead of a
    silent no-op.
14. Reset/restart cancels stale presentation work and rebuilds from one new
    generation.
15. Semantic target/display parity is checked at each acknowledged boundary.

## Final recommendation

Use NeuroMapEditor as the map projection, asset occurrence, and placement
authority. Use NeuroClient as a catalog of hard-earned runtime invariants,
future actor/animation/VFX evidence, and failure cases—not as a codebase to
translate wholesale.

The pygame implementation should directly reuse the engine's Event hierarchy,
world materialization values, sensory deltas, and combat-log reduction. It
should recover the NeuroMapEditor projection and asset metadata. It should borrow
NeuroClient's exact asset/cache, ground-picking, presentation-lag, failure,
and parity principles while deliberately omitting its network replication,
cue ontology, compiled presentation pipeline, mixed store, procedural board,
and planar structural assumptions.

The next planning step should turn this study into a practical P0 plan only,
while recording the actor and VFX phases as explicit successors
after separately resolving the one real missing seam: observer-safe reduction
of ordinary concrete Events without creating a parallel event type hierarchy.
