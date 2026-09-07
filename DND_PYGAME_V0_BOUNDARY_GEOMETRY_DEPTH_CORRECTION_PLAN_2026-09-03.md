# Pygame V0 Boundary Geometry and Depth Correction Plan

Status: `REVIEW CANDIDATE — NO IMPLEMENTATION AUTHORIZED`

This plan replaces the conclusions of
`DND_PYGAME_V0_A_WALLSET_CAMERA_LIGHT_CORRECTION_PLAN_2026-09-03.md` without
overwriting or deleting that rejected document. It corrects only the active
pygame V0 boundary-rendering seam. The accepted in-process Event capture,
subjective reduction, async engine/renderer queues, terrain, Water, torch,
mouse picking, and engine world-placement design remain governing.

The implementation stays in `game -> dnd`. It does not touch the server,
SDK, TypeScript clients, MapEditor, NeuroMapEditor, generated code, or engine
event semantics.

## 1. Evidence and fixed decisions

Two independent read-only visual audits inspected the raw PNGs, current pygame
renderer, imported Unity scene occurrences, layer order, pivots, and the three
reported failure screenshots:

- task `01a06747-9a86-7b62-8c25-ca524fb5a96b`;
- task `01a06766-efff-7cc1-99f8-208665dbc0e3`.

Both audits reject the A1/A2/A9 proposal. The active correction uses:

| Presentation | Exact asset family |
|---|---|
| straight dressed-stone wall | `Wall D1_{E,N,S,W}` |
| perpendicular dressed-stone corner | `Wall D2_{E,N,S,W}` |
| dressed-stone doorway frame | `Wall D6_{E,N,S,W}` |
| closed wooden door leaf | `Door A1_{E,N,S,W}` |
| open wooden door leaf | `Door A2_{E,N,S,W}` |

Why this set is fixed for this slice:

- D1, D2, and D6 occur in all four poses in the imported Unity scene;
- D2 is the coherent perpendicular-corner family for D1;
- D6 is the only inspected stone frame with source-witnessed co-locations for
  both A1 and A2 door states;
- the six witnessed D6/door co-locations always draw D6 in the Walls group and
  the leaf later in the Roof2 group; and
- A9 is center-pivoted damaged masonry, has no witnessed A2 pairing, and only
  looked like a doorway after an incorrect 80-pixel lift.

The E/S D6-door combinations are directly witnessed. N/W use the supplied
four-pose assets with the same rotation law; this is explicit inference rather
than falsely claimed source occurrence evidence.

## 2. Coordinate and asset contracts

### 2.1 Engine and camera vocabulary

Engine directions never change:

```text
NORTH = (0,+1)    EAST = (+1,0)
SOUTH = (0,-1)    WEST = (-1,0)
```

Camera diagnostics use one exact vocabulary:

| Camera | Viewpoint | Looking toward | Map N on screen | Map E on screen |
|---|---|---|---|---|
| q0 | NE | SW | down-left | down-right |
| q1 | SE | NW | up-left | down-left |
| q2 | SW | NE | up-right | up-left |
| q3 | NW | SE | down-right | up-right |

Asset suffixes are fixed package identities. The renderer selects them with
this complete table:

| Engine owner-side direction | q0 | q1 | q2 | q3 |
|---|---|---|---|---|
| NORTH | S | W | N | E |
| EAST | E | S | W | N |
| SOUTH | N | E | S | W |
| WEST | W | N | E | S |

`camera_pose()` remains one small pure conversion. The existing table and its
test are wrong for NORTH/SOUTH and are replaced, not wrapped or aliased. PNGs
are never rotated at runtime.

The on-screen map-N/map-E compass is computed by projecting one-unit engine
axis deltas through the same camera rotation. It is not a second handwritten
direction table.

### 2.2 Authored contact transforms

All five families are 256 by 256 and use zero family occurrence offset. Their
source-occurrence transforms are not the approximate catalog default:

| Assets | Pivot | Scale |
|---|---:|---:|
| D1, D2, D6 | `(128,207.36)` | `128/127` |
| Door A1, A2 | `(128,209.92)` | `128/127` |

They share the existing owner-Tile contact. There is no edge-midpoint shift or
direction-specific offset. A few historical A1 leaf occurrences with a
`0.128`-pixel offset remain occurrence facts and do not become family defaults.

The asset JSON stores these exact floats. `SurfaceCache.blit_position()` keeps
using the declared pivot and scale; no wall-specific positioning branch is
added.

### 2.3 Elevation and depth are separate

Engine XY, physical height, visual lift, and painter depth remain distinct:

- Tile surfaces use their existing Tile elevation for visual projection.
- A world object uses `WorldObjectPlacement.base_height_steps` for its visual
  contact; it does not silently reuse the owner Tile elevation.
- `top_height_steps` remains physical extent and is never treated as a pivot.
- the existing 64-pixel height-step calibration changes the blit contact only;
- painter depth uses the unlifted, camera-rotated ground-plan contact; and
- z level/elevation is not inserted into the painter key.

This fixes the present coupling in which lifted screen Y incorrectly changes
draw order. It does not introduce a Z-grid type or alter engine placement.
The rule applies to boundaries, door frame/leaf composition, and the existing
StandingTorch body and flame. Body and flame share their one committed
placement base.

## 3. Minimal painter contract

This section explicitly supersedes the contact-first painter ordering and the
old provisional role order in section 10.3 of
`DND_PYGAME_V0_MINIMUM_V1_VERTICAL_SEAM_IMPLEMENTATION_PLAN_2026-09-03.md`.
All accepted Water material, chunk ownership, per-support output, subjective
treatment, time, and caching laws remain unchanged.

Replace the current `(lifted Y, X, role, UUID)` key with one direct tuple:

```text
(composition phase, unlifted contact Y, unlifted contact X,
 same-contact direction rank, stable identity)
```

The finite numeric phases used by V0 are:

```text
10  water/planar background
40  earth/surface
100 walls, door frames, and ordinary spatial objects including fixture bodies
110 door leaves
120 fixture overlay/flame
```

This preserves the source facts that planar material is composed before
spatial geometry, spatial geometry and ordinary object bodies share the
source `00-walls` group and Y-sort by ground contact, and D6 draws before its
Roof2 leaf. Same-contact independent wall primitives use package-pose rank
`E,S,W,N`, matching the existing MapEditor deterministic tie. Every stable
identity is a tuple of UUID strings: a singleton for an ordinary primitive and
the sorted two-UUID tuple for D2. Identity is only the last stability tie and
cannot decide geometry. This homogeneous field makes every admitted
same-contact comparison total, including D2 beside another primitive.

After height-aware inverse projection and exact diamond matching,
`pick_support()` selects the maximum of this pick-only tuple:

```text
(unlifted camera contact Y, unlifted camera contact X, stable Tile UUID)
```

It reports every distinct tested elevation. It no longer borrows the renderer
painter key once that key becomes phase-aware and elevation-independent. The
overlap oracle is q0 `(20,20)` at height 1 and `(19,19)` at height 0: their
lifted projected contacts coincide, both diamonds contain that exact cursor,
the tested set is `(0,1)`, and unlifted depth selects `(20,20)`.

Do not add a scene graph, z-index manager, render node hierarchy, protocol,
callback, registry, or generic sorting policy object.

## 4. Direct bindings and copied assets

The active binding file contains five exact four-pose tables:

```text
stone_wall_straight.{e,n,s,w} -> wall-d1-*.png
stone_wall_corner.{e,n,s,w}   -> wall-d2-*.png
stone_door_frame.{e,n,s,w}    -> wall-d6-*.png
wood_door_closed.{e,n,s,w}    -> door-a1-*.png
wood_door_open.{e,n,s,w}      -> door-a2-*.png
```

Copy only missing D1/D2 files from NeuroMapEditor. D6 and Door A1/A2 are
already copied and are rebound with their exact transforms. Once no active
binding references B1, B4, or D8, remove those exact obsolete V0 copies. Do
not retain fallbacks, scan directories, infer family names, authenticate
assets, hash assets at runtime, or add a selector/resolver layer.

`game/assets.py` validates exactly these tables and their four poses through
its existing finite JSON loader. Engine material and structure choose the
table directly:

- `STONE + WALL` -> D1/D2 composition;
- `WOOD + DOOR` -> D6 plus A1/A2 leaf; D6's dressed-stone appearance is
  finite client composition around the wooden mechanical door and does not
  alter or misstate the door's engine material;
- any disclosed structure/material outside the admitted V0 set remains an
  explicit coverage error.

No asset identifier enters engine state.

## 5. Boundary disclosure and face lighting

Wall geometry and a door's D6 frame remain incident to both supports.
Treatment is selected from only the face displayed by the current camera.

For owner position `P`, engine direction `D`, and camera-viewpoint vector `C`:

```text
displayed support = P + D  when dot(C,D) > 0
displayed support = P      otherwise
```

```text
q0 NE=(+1,+1)   q1 SE=(+1,-1)
q2 SW=(-1,-1)   q3 NW=(-1,+1)
```

For each boundary:

- geometry is disclosed if either incident support is currently visible or
  remembered; the boundary does not disappear merely because the transition
  blocks its owner/far support;
- if the displayed support is visible, use that support's existing subjective
  `effective_light_levels` entry;
- if it is remembered, use the existing memory treatment;
- if only the reverse support discloses the geometry, use memory treatment for
  the hidden displayed face;
- never take the maximum of the incident levels;
- never read objective resolved light; and
- never cast renderer-side rays or add directional-light engine state.

This is a pure presentation choice over the selected observer's reduced
values. It fixes the torch-lit interior leaking onto the exterior face.

The door leaf and its open/closed state have the stricter existing subjective
contract: they are drawable only while the door UUID is present in the
observer's current `senses.objects`. Incident support disclosure alone may
show D6, but cannot disclose A1/A2 or the current `is_open` value.

## 6. Wall, corner, and door composition

### 6.1 One wall entry

Each disclosed `DirectionalWall` selects D1 using the complete table in 2.1,
uses the object's base-height contact, and retains its own UUID in frame
evidence.

### 6.2 All four possible entries on one Tile

A Tile may own an independent wall entry in each of NORTH, EAST, SOUTH, and
WEST. Presentation groups only the disclosed walls at that exact owner Tile.
The complete power set is defined:

- zero entries: no boundary draw;
- one entry: one D1;
- exactly two perpendicular entries with identical treatment and base height:
  one D2 representing both source UUIDs;
- exactly two perpendicular entries with different treatment or height: two
  independently treated D1 primitives;
- two opposite entries: two D1 primitives;
- three or four entries: independent D1 primitives in the deterministic
  same-contact pose order.

The four exact corner mappings are:

| Engine pair | q0 | q1 | q2 | q3 |
|---|---|---|---|---|
| N+E | D2.E | D2.S | D2.W | D2.N |
| E+S | D2.N | D2.E | D2.S | D2.W |
| S+W | D2.W | D2.N | D2.E | D2.S |
| W+N | D2.S | D2.W | D2.N | D2.E |

This 4-by-4 table is an acceptance oracle, not a second runtime camera table.
Runtime stores only the four q0 pair orientations:

```text
N+E -> EAST    E+S -> SOUTH
S+W -> WEST    W+N -> NORTH
```

It passes that one representative direction through the same corrected
`camera_pose()` used by straight walls. No separate corner rotation formula or
16-cell lookup is implemented.

The D2 raster is presentation coalescing only. Both engine wall objects and
UUIDs continue to exist independently. No corner entity/component is created;
no wall state is merged, removed, or rewritten.

For a qualifying D2 draw, the lexicographically sorted pair of wall UUID
strings is both the stability identity and the `source_wall_uuids` evidence.
The tuple contains each source UUID exactly once. The renderer suppresses
exactly those two corresponding D1 candidates for that frame. Every fallback
path emits one D1 evidence row for each original wall UUID exactly once.

### 6.3 Door

Each incident-disclosed `DirectionalDoor` creates a D6 frame command at its
owner contact and pose. That frame evidence carries the door UUID and geometry
disclosure, but never carries `is_open`.

Only a door whose UUID is in current `senses.objects` creates its leaf command
at the same owner contact and pose:

```text
closed: D6 frame, then Door A1 leaf
open:   D6 frame, then Door A2 leaf
```

Only the leaf evidence carries the one door UUID and current `is_open` state.
Door state still changes only through the existing door action and
Event/reduction path. The renderer never writes `is_open` and does not create
frame/leaf entities, events, timers, or animation state.

A door `SpatialChangeEvent` is represented only by a successfully published
leaf row whose door UUID, position, boundary direction, base-height steps, and
`is_open` equal the corresponding admitted after-values on the event's
`object_uuid`, `placement`, and `object_is_open`. A frame-only result settles
that event as not disclosed; the persistent frame cannot falsely acknowledge
an unseen state transition, and a correctly shaped leaf drawn at a stale
placement cannot falsely acknowledge the committed move/state.

The source compositor uses one monolithic leaf later than the wall group. The
MVP reproduces that exact rule. It does not invent runtime connected-component
analysis, masks, or sprite splitting. Because some A2 poses contain separated
alpha islands, one draw primitive cannot provide arbitrary per-pixel
interleaving with unrelated neighboring walls. The 32-case door sheet is an
acceptance gate: if source-order composition still visibly breaks the actual
demo, this plan stops rather than claiming success or quietly adding a mask
system.

## 7. Demo world and diagnostics

The existing 64-by-64 `battlefield.visual_vertical_seam` remains the real
Event/reduction/render proof. Make only these content corrections:

- author its barrier as dressed stone rather than wooden palisade;
- keep the existing east-side wall run and real door;
- add a SOUTH stone wall at owner `(31,26)` alongside its existing EAST wall;
- add a NORTH stone wall at owner `(31,37)` alongside its existing EAST wall,
  so both endpoint corners run through real world initialization; and
- preserve Water, torch, observer, and door open/reclose mechanics.

The overlay changes from `camera=R*` to the exact q/viewpoint/looking wording
and displays projected map-N/map-E arrows. Mouse diagnostics continue to show
authoritative XY, engine height, pixel lift, and projected contact.

No scripted combat, character rendering, VFX expansion, editor UI, or Phase V2
work enters this correction.

## 8. Observable proofs

Tests follow `HOW_TO_TEST.MD`: behavior tables at the smallest stable boundary,
plus reviewed images because pixel appearance is the feature.

### 8.1 Pure coordinate/depth proofs

- all 16 engine-direction/camera pose results equal the table in 2.1;
- compass arrows equal projected engine-axis deltas in all four cameras;
- the painter key is unchanged when only visual elevation changes;
- planar phases precede spatial phases;
- same-contact wall order is `E,S,W,N`, never UUID order; and
- height-aware mouse selection uses the exact two-candidate overlap oracle in
  section 3, chooses `(20,20)` at height 1, and reports tested heights `(0,1)`.

### 8.2 Asset/composition proofs

- the exact D1/D2/D6/A1/A2 resources, pivots, scales, and five four-pose
  bindings load;
- obsolete B1/B4/D8 bindings and files are absent;
- all four singleton wall entries render the expected D1 pose in all four
  cameras;
- all four adjacent pairs select the expected D2 pose in all four cameras;
- both opposite pairs render two D1 primitives in all four cameras;
- three-entry and four-entry owner Tiles retain every UUID exactly once;
- unequal-treatment adjacent walls remain separate and do not leak light;
- unequal-base-height adjacent walls remain two independently positioned D1
  draws and are never flattened into one D2;
- closed/open/reclosed doors draw frame plus the correct leaf; and
- wall/frame/leaf placement uses object base height rather than a differing
  owner-Tile height;
- incident support without door object contact draws D6 only, hides leaf/state,
  and does not represent the door event;
- a wall whose near incident support is visible while its blocked owner/far
  support is not visible still draws exactly once, using the near face's
  reduced treatment rather than disappearing or borrowing hidden-side light;
- stale leaf evidence with the right UUID/state but the wrong position,
  boundary direction, or base height does not represent a door event;
- a same-contact D2 and another boundary primitive sort without a type error
  and keep the prescribed geometry/pose order;
- StandingTorch body and flame use their shared placement base when it differs
  from the owner-Tile elevation.

### 8.3 Real-path and visual proofs

- the existing real pygame interval test still settles startup/open/reclose;
- objective and subjective text rails remain populated;
- opening now draws A2 rather than deleting the door Sprite;
- face-specific treatment makes the torch-lit interior bright only from the
  appropriate viewpoints;
- locality counters, cache behavior, Water animation, flame animation, and
  startup/runtime bounds remain intact;
- the real q0 Water/barrier overlap composites Water before spatial geometry,
  matches that pixel order, differs from the reversed composite, and records
  the same draw sequence; and
- Q0-Q3 closed, open, and reclosed captures visibly show the subjectively
  disclosed continuous D1 runs, aligned D6/A1/A2 compositions, and correct
  compass labels; geometry whose two incident supports are neither visible nor
  remembered remains absent rather than leaking objective world state.

The engine exact-placement/count proof establishes both authored endpoint caps,
and the exhaustive wall-entry/camera matrix establishes their D2 composition.
The real subjective captures do not require an undisclosed endpoint cap to be
drawn merely to manufacture visual evidence.

The validation contact sheet contains the same scene/state/time/viewport/zoom
for every camera; only camera quadrant changes. Review is performed at original
resolution. Connected-component counts and alpha-union scores may supplement
inspection but cannot approve appearance.

## 9. Implementation order and checkpoints

1. Correct `camera_pose()`, compass derivation, unlifted painter depth, and
   object-base-height contact. Run projection and picking proofs.
2. Replace the active bindings/resources with exact D1/D2/D6/A1/A2 data and
   transforms. Run catalog/decode proofs.
3. Implement face-specific boundary treatment and the finite wall grouping
   table. Run the exhaustive wall-entry/camera matrix.
4. Render D6 plus A1/A2 in source phase order. Run closed/open/reclosed and
   32-case door proofs.
5. Add the two real endpoint caps and camera/compass diagnostics. Run the full
   real pygame seam, the Water/barrier overlap regression, and generate the
   twelve reviewed frames. Update the scenario preview/runtime object manifest
   with the exact `(31,26,SOUTH)` and `(31,37,NORTH)` cap entries.
6. Run the complete `tests/game` lane, affected engine scenario/light/world
   tests, architecture checks, compileall, diff-check, and the documented
   clean-environment launch command.
7. Obtain exact-candidate correctness, anti-slop, and anti-OOP/ECS review.
   Any code or data repair invalidates the visual acceptance and reviews.

Do not advance past a checkpoint whose observable matrix or screenshot is
wrong.

## 10. Expected touched files

Production/data:

- `game/projection.py`
- `game/app.py`
- `game/assets.py`
- `game/data/assets.json`
- `game/data/world_bindings.json`
- exact files under `game/assets/environment/`
- `dnd/scenarios/battlefield_catalog.py`

Tests:

- `tests/game/test_projection.py`
- `tests/game/test_assets.py`
- `tests/game/test_app_smoke.py`
- at most one focused `tests/game/test_boundary_rendering.py` if keeping the
  64-case table readable requires it
- `tests/engine/test_world_entity_initialization.py`

No engine entity, component, Event, reducer, registry, server, SDK, renderer
bridge, or cross-language file is in scope.

## 11. Stop conditions

Stop and return to the user if:

- D1/D2/D6 is still visually unacceptable in the reviewed real scene;
- N/W inferred door poses do not compose correctly;
- source-order A2 still requires per-pixel occlusion in the actual demo;
- correct Z/depth behavior would require changing engine XY or placement
  semantics;
- subjective light values are insufficient without objective-state access; or
- implementation would require a new renderer abstraction rather than the
  finite V0 tables above.
