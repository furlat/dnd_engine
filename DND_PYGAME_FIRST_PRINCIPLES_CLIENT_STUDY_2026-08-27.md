# First-principles pygame-ce client study

Date: 2026-08-27  
Status: read/plan study only; no `/game` implementation has started

## Decision summary

Build a new local Python client under a future top-level `/game` directory,
using `pygame-ce` and the existing Python engine directly. Do not port the old
browser client, server protocol, SDK, TypeScript reducer, or replication stack.

The first playable product is one encounter with:

- two player-controlled characters from the first slice;
- a small enemy group;
- real isometric terrain and modular character assets;
- engine and presentation clocks that may advance independently;
- event-time subjective reduction before presentation mapping;
- an explicit disposition for every presentation-eligible engine event;
- a visible diagnostic fallback for an event without a visual handler.

The first terrain contract is deliberately simple:

> One 128x64 isometric asset diamond represents one engine cell.

The assets strongly suggest that the eventual authoring grid may subdivide one
of these diamonds into a 2x2 set of smaller tactical cells. That is deferred.
The first client must not add scale factors, parent-cell identities, subdivision
adapters, or dual coordinate systems in anticipation of it.

Elevation is independent of that footprint choice. One engine cell has one
authoritative support height, and the client must render and pick that height
correctly from the beginning.

## Scope and non-goals

This study covers:

1. the isometric grid, camera, screen/cell conversion, multi-height placement,
   mouse picking, and their debugging tools;
2. modular entity composition, animation, facing, tinting, and asset loading;
3. terrain composition from the existing isometric pack and the useful parts
   of the experimental MapEditor project;
4. a local engine/presentation queue boundary that lets mechanics run ahead of
   human-speed animation without exposing future state;
5. a minimal subjective projection for two controlled observers;
6. exhaustive event-to-presentation accounting, including a diagnostic badge
   fallback.

It does not cover:

- server, SDK, API, websocket, transport, or cross-language compatibility;
- the deprecated TypeScript runtime or its state model;
- networking, multiplayer security, save games, campaigns, menus, or character
  creation;
- a full MapEditor rewrite;
- full spell VFX authoring;
- true 3D physics, free camera rotation, voxel terrain, or multiple support
  surfaces at the same `(x, y)`;
- the possible future 2x2 subdivision of an asset diamond.

## Evidence studied

### Current engine

The useful active-runtime seams are:

- `dnd/core/base_tiles.py`: one `Tile` per strict two-integer position, with
  `height` stored in five-foot steps, an elevation surface kind, and an
  optional slope axis;
- `dnd/core/gridmap.py`: the authoritative tile, support-elevation, placement,
  ordered-edge, path, and connector queries;
- `dnd/core/world_edges.py`: directed views over cardinal neighbors, including
  source/destination support heights and exact facing-side structural
  contributions;
- `dnd/types/world_placement.py`: center or directional-boundary object
  placement with `base_height_steps` and `top_height_steps`;
- `dnd/core/traversal_connectors.py`: exact endpoints, endpoint elevations,
  authored `presentation_key`, directionality, and action/movement costs;
- `dnd/core/events/world_events.py`: renderer-neutral initial world facts in
  `WorldInitializedEvent`, including tile UUID, position, elevation, surface,
  light, costs, objects, vertical bands, and connectors;
- `dnd/core/events/events_registry.py`: stable event generation identity, raw
  event cursor, incremental iteration, event batches, lifecycle lineage, and
  event-time observer evidence;
- `dnd/blocks/sensory.py`: per-observer perception and movement-step sensory
  updates through the event system;
- `dnd/encounters/encounter.py`: synchronous controller and decision
  boundaries that can be wrapped by an in-process application coordinator.

Important current geometry facts:

- An entity position remains `(x, y)`. Its support elevation is obtained from
  `GridMap.get_support_elevation_feet(position)`.
- A tile height may be negative and is an exact integer number of five-foot
  steps.
- The engine has one support tile at each `(x, y)`, not a stack of mechanical
  tiles at `(x, y, z)`.
- Stairs and ramps are endpoint-authored progressive surfaces. The engine does
  not require continuous within-cell 3D interpolation.
- An elevation difference does not create a cliff, wall, optical blocker, or
  prop automatically. Those are separate authored world objects and ordered
  side facts.
- Two opposite-facing boundary objects remain two distinct placements. The
  renderer must not collapse them into one edge object merely because they
  touch.

### Deprecated Neuroclient

Source inspected under:

`/mnt/c/users/tommaso/documents/dev/NeuroClientDeprecatedSeeWSL/app/src`

Useful concepts to retain:

- authoritative-world versus presentation-world separation;
- a presentation player that consumes ordered event-derived cues;
- modular entities with one synchronized frame/facing shared by all visual
  layers;
- bottom-contact anchoring and isometric painter ordering;
- a pure mapping from identity/equipment facts to appearance data;
- camera inverse before isometric inverse for mouse picking;
- a visual debugging stage and asset catalog.

Architecture to discard:

- server/API orchestration;
- the TypeScript wire models and duplicate reducer state;
- transport reconciliation and cross-language serialization;
- any renderer access to a live authoritative store during playback;
- silent default branches in the event mapper;
- fabricated wall/floor geometry as the final terrain representation.

Observed failure modes that the new client must prevent:

- an animation reporting completion without visibly advancing its displayed
  frames;
- assets loading late and causing a frozen or invisible clip;
- child events being marked consumed and silently disappearing;
- death cleanup removing a visual entity before its queued presentation ends;
- selection changing the player's subjective visibility perspective;
- renderer state jumping to the engine's future position during an animation.

### Asset evidence

Modular character sprites are under:

`/mnt/c/users/tommaso/documents/dev/NeuroClientDeprecatedSeeWSL/app/public/spritesheets`

The primary contract established by the old asset loader is:

- sheet size: 15 columns by 8 facing rows;
- frame size: 128x128 pixels;
- row order: E, SE, S, SW, W, NW, N, NE;
- nominal playback: 12 frames per second;
- common animations include Idle, Walk, Run, Attack1-5, Special1,
  TakeDamage, Die, and Taunt;
- all equipped layers use the same facing, animation, and frame index.

The established bottom-to-top slot order is:

1. shadow;
2. body;
3. legs;
4. shoes;
5. mount;
6. chest;
7. belt;
8. hands;
9. offhand;
10. weapon;
11. weapon glow;
12. backpack;
13. head;
14. beard;
15. helmet;
16. aura, slash, and effect overlays.

Useful authored appearance data exists in:

- `render/data/characterPresets.ts`;
- `render/data/defaultItemVisualMap.json`;
- `render/data/defaultMonsterVisualMap.json`;
- `render/data/animation/clipMaps.json`;
- `render/data/animation/clipTiming.json`.

These files may be mined as content data. Their TypeScript renderer and runtime
must not become dependencies of the new Python client.

The terrain source is:

`/mnt/c/users/tommaso/documents/dev/assets/Fantasy tileset - 2D Isometric V1.1/Fantasy tileset - 2D Isometric`

Relevant facts:

- environment sprites are normally 256x256 RGBA images;
- their usable cell diamond is 128x64;
- directional environment variants use `_E`, `_N`, `_S`, and `_W` names;
- the pack contains ground, walls, roofs, doors, props, flora, animated props,
  and effects;
- animated props are ordinary ordered image frames;
- the Godot experiment uses a 128x64 isometric TileSet and a repeated
  `texture_origin = Vector2i(0, 80)` for packed 256x256 ground sprites.

The Godot experiment at
`/mnt/c/users/tommaso/documents/dev/small-scale-fantasy` is only an asset and
TileSet experiment. It has no editor/controller code worth adopting. Its
128x64 cell setting and texture-origin experiment are useful calibration
evidence, not a runtime specification.

The JSON files in `data/mapeditor/maps` are old schemas with legacy scalar
walkability/visibility fields. They must not be loaded as authoritative maps
for the new engine/client boundary.

## Recommended runtime shape

The new client should be one process with three distinct cursors:

- **simulation cursor**: the latest engine event committed;
- **presentation cursor**: the latest event whose visual disposition has
  finished playing;
- **decision cursor**: the engine boundary at which a particular controlled
  entity is waiting for input.

These are logical clocks, not three copies of the game.

The application boundary has two queues:

1. commands from the pygame/UI side to the sole engine owner;
2. immutable presentation batches from the engine owner to pygame.

The engine remains synchronous and deterministic. Async orchestration exists
only around it. A first implementation may run a single asyncio loop and yield
after each synchronous controller-decision boundary. It does not need a worker
thread, because a synchronous mechanic should be short and the purpose of the
queue is to prevent animation time from delaying subsequent engine decisions.
More importantly, avoiding a worker thread keeps the engine's global
registries under one owner.

The engine may resolve an enemy's full turn, or an autonomous chain up to the
next human boundary, while pygame is still playing prior presentation batches.
The queue holds that backlog. The engine stops at the next external decision
boundary; it does not run past an unanswered player choice.

Pygame must not read live engine entities, tiles, senses, registries, or event
objects during playback. Every batch contains immutable copies of the exact
facts necessary to present that boundary.

One practical boundary is:

1. capture `generation_id` and `cursor_before`;
2. execute one controller action/turn boundary;
3. capture `cursor_after`;
4. copy events in `[cursor_before, cursor_after)`;
5. perform subjective projection and presentation mapping;
6. copy the small after-state facts explicitly required by the resulting
   cues;
7. enqueue one immutable, ordered presentation batch.

The exact Python class names are implementation details. This should remain a
small coordinator plus two queues, not become a transport-shaped service,
manager/controller hierarchy, or serialization framework.

## Two controlled characters are a first-slice invariant

Maintain these identities independently:

- `controlled_entity_uuids`: exactly the two player characters;
- `decision_actor_uuid`: the character whose turn currently accepts a command;
- `selected_entity_uuid`: the character inspected or highlighted by the UI;
- camera focus/follow target;
- the observer set used to build the player's subjective world.

Selecting the other player character must not grant an out-of-turn command and
must not change what the player is allowed to perceive.

For the initial single-player party, the normal subjective view is the union
of the two controlled observers' independently reduced perceptions. A debug
toggle must show either character's individual reduction so that accidental
information sharing can be diagnosed.

The initial encounter should deliberately place the two characters at
different locations and give them different sensory evidence. At least one
entity or cell must be perceivable by only one of them. This proves that party
union, selection, current turn, and camera focus are not conflated.

Player commands become available only when:

- the engine is waiting at a decision boundary;
- the waiting actor is controlled by the player; and
- the presentation cursor has caught up to that decision boundary.

The UI may visually select either controlled character while catching up, but
it may command only the current decision actor.

## Canonical scripted proving encounter

Before interactive input is connected, the first engine/client integration
must be driven by one scripted encounter that runs from cold world assembly to
an explicit encounter end.

The script defines **commands and turn intentions**, never events, rolls,
damage, reactions, sensory deltas, or presentation cues. It drives the same
public action-discovery and execution boundary that later receives pygame
input. The engine must generate the complete causal event tree.

The initial script should contain at least these beats:

1. cold battlefield, object, connector, entity, equipment, controller, and
   initiative setup;
2. encounter, round, and first-turn start;
3. movement over several committed steps;
4. voluntary movement out of a hostile threat area;
5. the resulting engine-generated opportunity attack and reaction debit;
6. a melee or ranged weapon attack;
7. an enemy movement and attack turn;
8. a spell cast by the second controlled character, including its ordinary
   engine-generated roll/save/effect children;
9. enough additional turn transitions to exercise both controlled characters
   in distinct initiative slots; and
10. an explicit scripted encounter end after the planned sequence completes.

Opportunity attack is not a script row. The script installs/uses the ordinary
reactive capability and chooses a movement target whose real discovered path
exits reach. The reaction must arise from the committed movement-step event
path. The same rule applies to attack rolls, misses, criticals, damage,
concentration consequences, conditions, sensory updates, and deaths.

The intended actions are fixed a priori, but dice outcomes may vary. Therefore
later script rows must not depend on a prior hit, failed save, or exact damage
total. Give proving actors enough durability, and reserve any likely death for
the end, so either hit/miss branch can still reach the remaining planned
actions. A reproducible dice seed is useful for diagnostics, but it must enter
through the ordinary engine dice source; the script must not manufacture event
outcomes.

Each planned command identifies:

- the stable scenario role of the actor;
- the expected turn/decision boundary;
- an action selector from current public discovery;
- an exact target role, object identity, or position;
- movement safe-path preference when applicable; and
- whether the turn continues or ends after the command.

At execution time, resolve that intention against a fresh
`get_available_actions()` result and execute the exact discovered action row
and target. Do not persist or rely on target-list indexes across decisions.
Fail loudly if an intended action is absent, unaffordable, ambiguous, or has a
different legal target. Such a failure is useful engine/client contract
evidence, not a reason to bypass discovery or post events manually.

Keep this proving script as direct Python encounter-fixture data. Do not create
a general scripting language, JSON DSL, replay framework, behavior tree, or a
second controller hierarchy for it.

### How the scripted encounter drives presentation development

Capture from the event generation/cursor established immediately after runtime
reset. Cold assembly produces the real `WorldInitializedEvent`, entity and
equipment facts, initial sensory state, and encounter-start lineage. Every
subsequent planned command is captured as its own cursor-bounded immutable
presentation batch.

Pygame consumes those batches while the script continues resolving later
decisions. This directly proves that simulation can reach the next planned
boundary while presentation remains on an earlier human-speed animation.

The scripted run is the canonical automated vertical-slice fixture for:

- initial presentation-world construction;
- multi-height terrain and object placement;
- composed entity creation and equipment appearance;
- movement interpolation and facing;
- nested reaction ordering;
- attack and spell presentation;
- subjective projection for the two controlled observers;
- total event-disposition receipts;
- death/end cleanup ordering; and
- final equality between the consumed presentation cursor and the scripted
  terminal cursor.

The two hero identities remain the controlled observer set during this
automated run even though their decisions are supplied by the script. Replacing
the script's command source with real pygame input must not change the event,
projection, queue, or presentation path.

## 0. Isometric grid, elevation, mouse picking, and debug

### Coordinate domains

Keep four explicit coordinate domains:

1. **screen pixels**: pygame window coordinates;
2. **camera/world pixels**: screen pixels after undoing viewport origin, pan,
   and zoom;
3. **engine cell**: exact `(x, y)`;
4. **support plane**: the tile's authoritative `height` in five-foot steps.

Never mix camera zoom or offsets into the grid formulas. First convert screen
to camera/world pixels, then perform isometric projection or picking.

For the accepted 128x64 first-slice cell footprint, the flat projection is:

```text
world_x = origin_x + (x - y) * 64
world_y = origin_y + (x + y) * 32
```

An elevated support uses the same grid on a renderer-owned visual plane:

```text
support_x = world_x
support_y = world_y + grid_plane_offset_y[height_steps]
```

The engine coordinate remains exactly `(x, y)` and the engine support height
remains exactly `height_steps`. `grid_plane_offset_y` belongs only to visual
projection, so a higher tile never acquires a conflicting gameplay position.
The offsets will probably be the linear sequence
`-height_steps * elevation_step_pixels`, but the G0 harness must measure and
freeze that asset contract rather than smuggling pixel units into engine state.
The engine's step is always five feet. The offset must not be guessed from the
old 64x32 Neuroclient grid.

### Multi-Z grid technique

Treat every distinct engine support height as a virtual copy of the same
isometric plane with its own renderer-only Y offset. All planes share the same
engine `(x, y)` coordinate system; they differ only in pixel projection.

For picking on a candidate height `h`:

1. transform the mouse from screen pixels into camera/world pixels;
2. subtract `grid_plane_offset_y[h]` from its world Y coordinate, effectively
   moving that visual plane back to the zero-height projection;
3. apply the ordinary inverse 128x64 isometric transform;
4. snap to a candidate `(x, y)`;
5. accept it only if a live presentation tile exists there and its frozen
   engine `height` equals `h`;
6. test the mouse against that tile's projected top-diamond polygon.

Do this for the distinct heights present in the presentation snapshot,
including negative heights. This is the useful multi-Z technique: multiple
shifted projection planes, not 3D ray casting.

Several projected diamonds can contain the same pixel. The winning cell must
be the frontmost visible selectable surface according to the same stable draw
order used by the renderer. The safest implementation retains the projected
pick polygons in actual painter order and tests them in reverse. Do not choose
only the highest elevation or the first flat inverse result.

Current progressive stairs and ramps still use the whole tile's support
height for picking. The engine has no within-cell creature height coordinate,
so interpolating a 3D slope under the cursor would fabricate precision.

### Painter order and higher tiles

The old `zIndex = x + y` rule is insufficient once support heights and tall
assets exist. Every drawable should have a bottom/contact anchor derived from:

- cell `(x, y)`;
- support or object `base_height_steps`;
- boundary side, for directional objects;
- an explicit layer rank;
- a stable identity tie-breaker.

The initial painter key should be based on the projected contact anchor rather
than raw grid coordinates. It must be proven visually with overlapping higher
and lower tiles, walls, entities, and tall props before being frozen.

Do not infer vertical faces or cliffs from a height delta. A tile top, an
authored cliff/retaining face, a wall, and a boundary object are distinct
drawables. The engine already keeps the corresponding mechanics distinct.

Do not merge opposite-facing boundary placements. A wall stored on the east
side of one tile and a wall stored on the west side of its neighbor are two
objects and may intentionally render as adjacent/thicker structures.

### Required mouse/grid debug overlay

This is production development tooling, not an optional polish item. With a
single toggle, show:

- screen mouse `(sx, sy)`;
- camera/world mouse `(wx, wy)`;
- camera origin, pan, and zoom;
- flat-grid fractional inverse before snapping;
- every tested virtual height plane;
- candidate `(x, y, height_steps)` for each plane;
- diamond hit/miss result for each candidate;
- final winner and the painter-order reason it won;
- tile UUID, position, `height` in steps, and support elevation in feet;
- elevation surface kind and slope axis;
- resolved mechanical movement costs and light level;
- center object placements and their base/top vertical bands;
- all four boundary-side placements without coalescing opposite sides;
- connector endpoints and endpoint elevations;
- entities on the cell and their inherited support elevation;
- tile visibility separately from each tile-content visibility result;
- the selected subjective observer mode: party union, character A, or
  character B.

Visual debug geometry must include:

- the projected top diamond for every visible cell;
- a height-colored outline or label;
- the current candidate diamonds in one color;
- the winning diamond in another;
- projected cell axes and the map origin;
- the selected tile's contact anchor and sprite anchor;
- optional painter-order numbers over nearby drawables.

The debug view must remain correct while panning and zooming. A round-trip
check should continuously project the winning cell back to its elevated
diamond and report an error if the mouse no longer lies inside it.

### First grid/elevation harness

Before encounter integration, render a small authored test surface using real
assets with:

- ordinary height-zero cells;
- at least one negative-height cell;
- a two-step plateau;
- a legal one-step progressive stairs run;
- a legal one-step ramp run;
- an explicit cliff boundary beside a height change;
- a same-height wall;
- two opposite-side neighboring wall placements;
- a center prop and an entity at different support heights;
- a traversal connector between distinct endpoint elevations.

Acceptance requires reliable picking of every exposed top diamond at multiple
camera pans and zoom levels, with the debug overlay explaining every winner.

## A. Entity composition and animation

### Asset model

Implement a Python asset catalog over the existing spritesheets. A composed
entity owns one logical facing, animation, frame index, loop/one-shot state,
and bottom-contact position. Each occupied visual slot draws the corresponding
frame from its own sheet at that same state.

Grid movement facing must preserve the established isometric camera
compensation. Verify all eight directions visually instead of porting the old
function without evidence.

The first encounter should use fixed, authored appearance presets for the two
player characters and its enemies. Equipment-driven appearance mutation can
then reuse the existing item/monster visual mappings as data.

### Loading and tinting

Required encounter assets should be catalog-validated and preloaded before the
encounter starts. Missing files produce a deterministic diagnostic placeholder
and a structured coverage entry during development; the accepted encounter
must start with zero missing required assets.

Do not port the browser GPU tint filter blindly. Build deterministic tinted
pygame surfaces at asset-load time and cache them by source frame and tint
tuple. Support the exact tint zones required by the chosen first-slice
appearances; extend multi-zone fidelity only from inspected asset evidence.

### Animation correctness

One-shot presentation cues own their visual entity until their required frames
finish. Later authoritative state cannot reposition, replace, or delete that
visual entity early.

Animation diagnostics must record:

- requested clip and source event lineage;
- asset keys and loaded layer count;
- facing row;
- current displayed frame and elapsed presentation time;
- hit/release marker frame when applicable;
- observed frame changes;
- completion reason.

The acceptance check is visual frame progression, not merely a completed timer
or callback. Death presentation completes before the presentation entity is
removed. A damage cue cannot be hidden by immediately applying a future idle
or death state.

## B. Terrain and MapEditor direction

Mechanics and appearance are related but not interchangeable:

- `TileSurface`, movement costs, elevation, optics, propagation, light, and
  boundary contributions are authoritative engine facts;
- the chosen ground/wall/prop sprite, art variant, orientation, animation, and
  anchor are authored presentation facts.

A stone mechanical surface does not uniquely identify one stone texture. A
visually tall wall does not become an optical blocker by appearance. The new
client must never derive mechanics from filenames or sprite pixels.

For the first encounter, use a small local presentation layout that binds the
known battlefield cells and placements to semantic asset keys. Do not design
a general editor schema before the 128x64 alignment, height offset, boundary
orientation, and painter rules have been proven in pygame.

The eventual MapEditor should author one renderer-neutral local document from
which:

- the engine receives mechanical cell, elevation, object, edge, light, and
  connector facts; and
- pygame receives terrain/object visual keys and anchor/orientation data.

Both consumers should load the same authored map in process. There is no server
adapter between them.

The first-slice 1:1 asset-diamond/cell rule belongs to this local presentation
layout. If later asset authoring confirms that one diamond must cover a 2x2
tactical footprint, migrate the map-authoring contract deliberately. Do not
hide that future change behind a premature generic coordinate wrapper.

## C. Spell VFX

Full spell VFX authoring is deferred. The first client still has to represent
spell events through existing character clips, projectile/area placeholders,
condition badges, text cues, or the general unmapped-event badge.

This preserves total event coverage without blocking the engine/client
architecture on the VFX catalog.

## D. Subjective reduction and total event representation

### Reduction boundary

Subjective reduction happens before visual mapping. The renderer receives only
the facts the player presentation is allowed to use.

Use the engine's event-time evidence:

- `identified_entity_observer_uuids` for identity;
- `located_entity_observer_uuids` for exact entity location;
- `located_position_observer_uuids` for independent coordinate evidence;
- the controlled entities' reducer-owned senses state for current tile/entity
  presentation.

An event is available to the normal party presentation when either controlled
observer has the required evidence. Identity, location, and other carried
fields must be reduced independently; event visibility must not imply that the
entire objective event object can be copied to pygame.

This is intentionally a small in-process projector over current engine facts,
not a revival of the deprecated server replication framework.

Tile visibility and content visibility remain separate. A tile surface may be
presentable while an entity or object on it is not. A visible wall may be the
thing that blocks visibility beyond itself. The reduction output therefore
cannot be a single boolean attached to the whole cell.

### Presentation-eligible event versions

The raw queue stores lifecycle versions. Presentation mapping should normally
receive terminal `COMPLETION` and `CANCEL` facts plus explicitly selected
stream facts such as sensory deltas. Declaration/execution/effect versions are
not each separate animations unless a reviewed cue explicitly needs them.

Filtering lifecycle versions before mapping must itself be explicit and
tested; it cannot be another silent default branch.

### Total disposition

Every presentation-eligible event receives exactly one terminal disposition:

- `ANIMATED`: a timed spatial/entity animation;
- `STATE_CUE`: a visible state update, log cue, icon, or overlay;
- `BADGE_FALLBACK`: a diagnostic on-screen representation because no specific
  handler exists;
- `INTENTIONALLY_SILENT`: a reviewed policy with a recorded reason;
- `HIDDEN_BY_SUBJECTIVE_POLICY`: the player lacks the required evidence.

`UNMAPPED` is a diagnostic input state, never a terminal outcome. At runtime it
must become `BADGE_FALLBACK`, carrying enough reduced information to add the
missing handler safely.

Each source stream index/event UUID/lineage in a presentation batch receives a
coverage receipt. If a parent cue visually represents a child event, the child
receipt says which parent cue represented it. There is no anonymous consumed
set.

A hidden event still receives a `HIDDEN_BY_SUBJECTIVE_POLICY` receipt and keeps
its ordering/barrier role, but it must not display a badge that leaks its
existence or data to the ordinary player view.

### Coverage diagnostics

The debug event panel should expose, for each reduced event:

- stream index and generation;
- UUID, lineage, parent, and children;
- concrete event class, `EventType`, phase, and status;
- reduced actor/target/position fields;
- chosen disposition and handler key;
- cue IDs produced;
- missing fields or assets;
- completion/presentation cursor state.

Two forms of verification are required:

1. enumerate every loaded concrete `Event` subclass and require an explicit
   presentation policy or reviewed exclusion;
2. run representative encounter batches and prove every eligible source event
   receives exactly one terminal coverage receipt.

The concrete event class matters in addition to `EventType`, because different
subclasses may share a dispatch category while needing different presentation.

## Minimal implementation sequence

No implementation is authorized by this document alone. Once this study is
accepted, produce bounded practical guidance for one slice at a time.

### Slice G0 — real-asset isometric and multi-height debug harness

- create the minimal pygame-ce shell;
- load a few real terrain assets;
- implement camera transforms and the 128x64 projection;
- calibrate asset contact anchors and elevation-step pixel offset;
- implement virtual-plane multi-Z picking;
- implement the full mouse/grid/elevation debug overlay;
- prove draw order with elevated tiles, explicit boundaries, props, and one
  placeholder entity.

This slice must precede gameplay. It establishes the coordinate truth on which
terrain, entities, selection, targeting, and VFX depend.

### Slice G1 — modular entity animation lab

- load and validate the selected character layers;
- compose synchronized eight-facing entities;
- implement idle, walk/run, attack, damage, and death clips;
- implement deterministic tint caches and missing-asset diagnostics;
- prove actual displayed frame progression and bottom-contact anchoring at
  multiple elevations.

### Slice G2 — local engine/presentation queue, scripted encounter, and coverage receipts

- wrap existing encounter decision boundaries without changing engine event
  semantics;
- assemble the canonical scripted proving encounter and resolve each planned
  command through fresh public action discovery;
- capture cold bootstrap through explicit encounter end without scripting any
  event or outcome;
- copy immutable event batches by generation/cursor;
- implement the terminal-event eligibility rule;
- implement total presentation dispositions and the fallback badge;
- keep simulation, presentation, and decision cursors visible in debug UI;
- prove no renderer access to live engine objects;
- prove every scripted command and every engine-generated child event reaches
  one terminal presentation disposition.

### Slice G3 — two-character subjective encounter

- assemble one existing-engine encounter with two player controllers and a
  small enemy group;
- distinguish controlled, selected, decision actor, and camera identities;
- reduce presentation as the union of the two controlled observers;
- add individual-observer debug modes;
- let autonomous turns resolve into a queue while pygame plays at human speed;
- unlock input only after presentation catches the human decision boundary.

### Slice G4 — authored terrain bridge

- replace the temporary encounter visual layout with the smallest validated
  renderer-neutral local authoring document;
- connect mechanical battlefield authorship and visual asset keys without
  merging them;
- use the proven pygame coordinate/anchor contract as the basis for renewed
  MapEditor work.

### Later slices

- fuller item/equipment-driven appearance;
- animated terrain props;
- spell/projectile/area VFX catalog;
- more encounters and character presets;
- only after map-authoring evidence, decide whether asset diamonds remain 1:1
  or migrate to a 2x2 tactical footprint.

## Anti-slop constraints

- No server-shaped local facade.
- No Python mirror of the SDK or TypeScript store.
- No custom network serialization in an in-process client.
- No renderer reads from live engine registries during playback.
- No second authoritative world model; presentation state is an immutable,
  cursor-bounded projection.
- No generic event bus beside the current engine event stream and the two app
  queues.
- No scripted event, roll result, reaction, damage packet, or sensory delta;
  the proving script submits only public gameplay commands.
- No scripting DSL or replay subsystem for the single proving encounter.
- No silent event default branch.
- No hidden event badge that leaks subjective information.
- No equation that treats entity selection as player perspective.
- No `x + y`-only depth sort after elevation is enabled.
- No height-to-cliff, height-to-wall, art-to-optics, or material-to-texture
  inference.
- No merging of the two sides of a boundary.
- No speculative 2x2 coordinate abstraction in the 1:1 first slice.
- No within-cell 3D slope interpolation the engine does not model.
- No full editor schema before the real-asset pygame harness proves anchors,
  orientation, elevation offset, picking, and painter order.

## Questions deliberately deferred until the G0 evidence exists

1. Exact `elevation_step_pixels` for the asset pack.
2. Exact contact-anchor offsets for every terrain/prop family.
3. The final stable painter key for all higher/lower overlap cases.
4. Whether some directional environment variants are rotation alternatives,
   boundary-side alternatives, or both.
5. Whether the asset diamond remains one tactical cell or later becomes a 2x2
   authoring parent.

These are visual-authoring facts to measure in the pygame harness. None require
changing current engine geometry before implementation begins.
