# Pygame V0 Full-Map, Camera, and Structure-Debug Plan

Status: `REVIEW CANDIDATE — NO IMPLEMENTATION AUTHORIZED`

This is the next bounded pygame V0 slice after the accepted boundary geometry,
depth, face-lighting, and four-camera correction. It turns that narrow visual
seam into a useful 64-by-64 map-debugging scene without changing engine event
semantics. This V0 deliberately exposes objective terrain plus static
wall/frame identity while preserving subjective control of dynamic/private
state.

The implementation remains an in-process Python/pygame-ce client over detached
engine Event values. It does not touch the server, SDK, TypeScript clients,
MapEditor, NeuroMapEditor, generated code, combat content recovery, entity
sprites, spell VFX, or later elevation work.

## 1. Outcome

The completed slice must provide all of the following at once:

1. Every authored support Tile can be drawn and picked across the complete
   64-by-64 world, instead of the map appearing as only the observer's small
   visible/remembered island.
2. Terrain and static wall/door-frame identity form an explicit objective
   structural map. Hidden door leaf/open state, fixtures, later dynamic
   objects, and their display obligations remain subjective.
3. Camera rotation preserves the same engine-plane point under the viewport
   center after arbitrary WASD panning. Zoom preserves the engine point under
   the cursor. WASD remains screen-relative in all four camera quadrants.
4. One coherent broader battlefield naturally contains wooden floors, wooden
   and dressed-stone straight walls/corners, a real door, Earth, Water, and the
   lit StandingTorch. It is a small playable place, not a test gallery.
5. The overlay makes coordinate, height, visibility, material, boundary, and
   camera-anchor mistakes directly observable.

This is a debugging foundation, not a map editor or a generic render engine.

## 2. Fixed architecture boundaries

### 2.1 One world and one full structural extent

`PresentationTarget.tiles` and `PresentationTarget.objects` continue to be
reduced only from detached admitted Events. The renderer never queries live
`GridMap`, `Tile`, `BaseItem`, registries, or systems.

There is one direct V0 extent, with no mode switch:

- every `WorldTileState` is eligible for the terrain pass;
- every static wall and doorway-frame geometry in the materialized world is
  eligible for the structural pass;
- visible supports/faces retain their existing subjective light treatment;
- remembered supports/faces retain the existing memory treatment;
- undisclosed terrain and static geometry use one neutral `authored`
  presentation treatment; and
- visible and undisclosed-authored Water animate, while remembered Water keeps
  its accepted frozen-memory treatment.

Door leaves/open state, fixture body/flame state, and later creature/item
state remain subjectively disclosed exactly as today. Terrain, wall identity,
and doorway-frame identity are the intentional objective exception. Static
geometry answers "what map did the world event materialize?"; dynamic/private
state still answers "what did this observer receive?"

`authored` is presentation provenance, never an engine light level. Existing
semantic object evidence and `_display_sources()` remain the only route by
which a door/fixture/spatial-state Event settles. An authored wall or frame
draw cannot represent a hidden leaf/state Event. The completed
`WorldInitializedEvent` may be represented by its full structural world
because it is the objective world-creation fact.

Do not add a toggle, view-model hierarchy, scene graph, render protocol,
observer facade, debug reducer, second world copy, or compatibility path.

### 2.2 Finite scale and culling

The full world remains 64 by 64. Add `0.15` to the finite zoom set; at this
zoom the unlifted 64-by-64 diamond is approximately 1229 by 614 pixels and can
be inspected in the 1280-by-720 window. Existing zooms remain unchanged.

Candidate enumeration may inspect the 4,096 detached Tile values, but asset
blits and grid-line draws are clipped to the viewport before submission.
Water retains its existing 16-by-16 chunk ownership and bounded pixel
calculation. No cache, quadtree, spatial index, batch manager, or dirty-region
system is added speculatively. A measured failure of the performance gate is a
stop for a focused amendment, not permission to invent one.

## 3. Camera contract from first principles

The stable camera fact is the engine-plane coordinate under a screen anchor.
Raw `pan` is only the translation needed by the current projection basis; its
numeric value is not invariant under a quarter-turn.

The contracts are:

- **Q/E rotation:** keep `inverse_plane(viewport_center, camera)` exactly fixed
  while changing the camera quadrant.
- **Mouse-wheel zoom:** keep `inverse_plane(mouse_position, camera)` fixed.
- **WASD:** move the camera in screen space at a constant pixels-per-second
  rate. W always moves the viewed content down, S up, A right, and D left,
  independent of map cardinal orientation.
- **Composition:** pan, rotate, zoom, and rotate again preserve the anchor of
  each operation; four consecutive quarter-turns return to the same semantic
  camera within absolute floating tolerance `1e-9` (quadrant/zoom/viewport
  exact, pan and derived anchor approximate).

The existing `Camera.quarter_turned()` already follows the first contract and
is not rewritten merely because its derived pan changes. The implementation
adds proofs and diagnostics around it. A fixed viewport-center crosshair and
an overlay field for the engine-plane center anchor make the preserved point
visible. If the crosshair remains fixed while artwork appears to jump, inspect
the selected pose's pivot/contact; do not compensate an asset defect by
corrupting camera math.

The initial camera still focuses the current seam at a useful detail zoom.
The user can wheel to the new overview zoom. No free rotation, inertial camera,
camera entity, controller class, or stored second `focus` authority is added.

## 4. Uniform terrain-pose binding

Raster terrain becomes a direct finite mapping for the families that actually
have four supplied camera poses:

```text
terrain.earth.{e,n,s,w} -> Ground A1_{E,N,S,W}
terrain.wood.{e,n,s,w}  -> Ground F1_{E,N,S,W}
terrain.water           -> water.unity
```

The raster pose is selected from the existing four-camera conversion using
EAST as the package reference orientation. Procedural Water has no fake pose
table. There is no runtime PNG rotation and no asset-name inference.

Copy only the missing Ground A1 poses and the four Ground F1 PNGs from:

`/home/tommaso/Dev/NeuroMapEditor/public/assets/fantasy/environment/`

Ground F1 is the second terrain type and maps to the existing
`Material.WOOD`. It is a 256-by-256 RGBA wooden-plank floor with pivot
`(128, 208)`, scale `1`, and zero occurrence offset. Its directional grain is
deliberately useful for exposing wrong pose selection during camera turns.

The binding file remains the finite client-side materialization of graphical
assets. No asset ID, pose, pivot, or client taxonomy enters engine state.

## 5. Wooden wall family and composition

Add exactly one wall family, also selected from existing engine facts:

```text
Material.STONE + WALL -> existing D1 straight / D2 corner
Material.WOOD  + WALL -> C1 straight / C2 corner
```

Copy only:

```text
wall-c1-{e,n,s,w}.png
wall-c2-{e,n,s,w}.png
```

from the same NeuroMapEditor environment directory. All eight are 256 by 256
RGBA, use pivot `(128, 208)`, scale `1`, and zero occurrence offset. No wooden
door family is inferred in this slice; the existing wooden mechanical door
continues to use its accepted D6 frame plus A1/A2 leaf composition.

Wall composition is performed per owner Tile and per material:

1. Partition that Tile's disclosed wall rows by `BoundaryStructure.material`.
2. Within one material, exactly two perpendicular directions with identical
   presentation treatment and base height may become that material's one
   matching corner primitive.
3. Opposite directions, three/four-entry sets, unequal height/treatment, or
   same-material sets that do not meet rule 2 remain independent straight
   primitives.
4. Different materials never merge. A wood/stone perpendicular junction is
   two independently identifiable straight primitives, not an invented hybrid
   corner.
5. Existing painter phase, unlifted depth, package-pose tie, and stable UUID
   identity remain governing.

This is a small extension of the current finite wall grouping, not a new
structure-composition subsystem.

## 6. Coherent broader battlefield

Expand `battlefield.visual_vertical_seam` into one comprehensible map; do not
create a parallel fake pygame map or scatter isolated test pieces through the
world. The existing battlefield ID and scripted closed/open/reclosed door
sequence remain stable.

The 64-by-64 authored layout is:

- Earth remains the background across the complete map.
- A stone lodge occupies supports `x=24..31`, `y=26..37`.
- The lodge interior uses `Material.WOOD` Ground F1 floor.
- Its ordinary perimeter is made from the existing dressed-stone wall family:
  - WEST entries on owners `(24, 26..37)`;
  - EAST entries on owners `(31, 26..37)`;
  - SOUTH entries on owners `(24..31, 26)`;
  - NORTH entries on owners `(24..31, 37)`.
- The accepted real door remains the EAST entry at `(31,31)`, replacing the
  wall at that exact boundary.
- The observer and StandingTorch remain inside the lodge at their accepted
  positions. Closed/open/reclosed door actions therefore exercise a real room,
  not an isolated wall strip.
- A Water pond occupies `x=34..41`, `y=27..35`, outside and east of the lodge.
- A wooden storehouse occupies supports `x=35..42`, `y=38..44`, uses Ground
  F1 floor, and uses the C1/C2 wall family around its perimeter:
  - WEST entries on owners `(35, 38..44)`;
  - EAST entries on owners `(42, 38..44)`;
  - NORTH entries on owners `(35..42, 44)`; and
  - SOUTH entries on owners `(35..42, 38)` except for the two-support entrance
    gap at `(38,38)` and `(39,38)`.
  No unsupported wooden door is invented.

This layout naturally exercises:

- long straight D1 and C1 runs;
- all four engine boundary directions;
- D2 and C2 corners produced by two ordinary walls sharing a corner owner;
- the existing D6/A1/A2 door composition;
- Earth/Wood/Water terrain transitions;
- an interior light source, opaque room boundaries, and visibility through a
  door after it opens; and
- depth/layering across two nearby buildings and the pond in all four cameras.

Named notable positions and object UUIDs cover the door, torch, one interior
floor, pond edge, each building corner, entrance gap, and representative stone
and wood straight walls. Tests use those names rather than registry order.

Everything is authored through ordinary `TileSurface`, `DirectionalWall`,
`DirectionalDoor`, placement, world initialization, and sensory facts. Add no
renderer-only wall, special Tile subclass, new material enum, gallery event,
or map-specific rendering rule.

## 7. Diagnostics

The overlay must show:

- `extent=full-structural`;
- camera quadrant, viewpoint, looking direction, zoom, and derived pan;
- the engine-plane coordinate under the viewport-center crosshair;
- hovered Tile position, UUID, material, elevation steps/feet, projected
  contact, and whether it is `current`, `memory`, or `authored`;
- every boundary owned by the hovered Tile as
  `UUID / structure / material / engine direction / base height`; and
- candidate, clipped draw, Water chunk/pixel, and cache counters.

Boundary UUID/material/direction in the hover line belong to the explicit
objective structural exception; leaf/open state is never added there.

Picking uses all 4,096 detached Tile candidates and remains height-aware. The
overlay is text only; do not add panels, buttons, selection state, an inspector
model, or editor mutations.

## 8. Observable validation

Tests follow `HOW_TO_TEST.MD` and use public/pure boundaries.

### 8.1 Camera and picking

- arbitrary noncentral pans preserve the exact engine center anchor across
  every Q/E turn and across all four starting quadrants;
- four turns return the same semantic camera within absolute tolerance `1e-9`;
- W/S and A/D are inverse screen displacements in every quadrant and after a
  turn;
- pan then turn preserves the newly panned engine anchor, not the original map
  center;
- zoom preserves its mouse anchor at every adjacent finite zoom, including
  `0.15`;
- an undisclosed Tile can be picked and reports presentation provenance
  `authored`; and
- height-overlap picking remains correct.

### 8.2 Terrain, assets, and locality

- the Earth and Wood raster pose tables have no missing or extra pose member,
  while Water remains one procedural binding;
- Ground A1, Ground F1, C1, and C2 resources load with the exact files and
  transforms;
- camera q0..q3 selects the expected terrain pose without rotating a PNG;
- the real frame has 4,096 terrain candidates and produces only viewport-
  intersecting draw commands;
- grid-outline candidates rejected by the viewport are counted separately and
  never submitted to pygame drawing;
- undisclosed authored Water animates, visible Water receives subjective light
  treatment, and remembered Water remains frozen;
- at 0.15 zoom the full unlifted map bounds fit the 1280-by-720 viewport when
  centered; and
- one reproducible manual run uses the normal venv launch, discards 60 warm-up
  frames, then records 300 frames at zoom `0.15` and 300 at zoom `0.50` while
  panning and quarter-turning. Each sample reports median and worst frame time;
  the acceptance statistic is median <= 16.67 ms at both zooms. Permanent
  tests assert bounded terrain/static-structure/grid counters rather than
  flaky wall-clock timing. Algorithmic work is limited to the fixed 4,096
  Tile/static-structure scan plus existing viewport-qualified/Water work.

### 8.3 World structure and interaction

- the real world event contains the exact lodge, pond, storehouse, floors,
  entrance gap, and named wall/door placements;
- the lodge's four corners compose as D2 and the storehouse's four corners as
  C2 in all cameras;
- representative lodge and storehouse runs select D1 and C1 respectively in
  all cameras;
- existing wall-entry geometry proofs remain green;
- one direct binding proof establishes `STONE -> D1/D2` and `WOOD -> C1/C2`;
- the actual lodge/storehouse corners prove per-material grouping without an
  artificial mixed-material scene;
- one pure value-level same-owner wood/stone case proves the rows remain two
  straight primitives, retain both UUIDs, select C1 plus D1, and do so in all
  four cameras; it is test data only, never authored map content;
- the existing D6/A1/A2 door, boundary-face lighting, synthetic Water/spatial
  ordering regression, torch, and event-display obligations remain green; and
- objective structural rows cannot settle a hidden door leaf/open-state,
  fixture, or other dynamic spatial-state event.

### 8.4 Human visual acceptance

Generate original-resolution captures for:

- q0..q3 at the same detail zoom and same engine center anchor;
- q0..q3 at 0.15 full-map overview;
- the lodge, pond, and wooden storehouse together and as useful close-ups; and
- the existing closed/open/reclosed stone door seam.

The center crosshair must touch the same engine support in every rotated
capture. Review must explicitly confirm complete floor coverage, no contact
jump, correct Ground F1 grain rotation, C1/C2/D1/D2 selection, coherent
building corners/openings, deterministic layering, and no exterior/interior
light leak.
Image heuristics cannot replace visual inspection.

## 9. Implementation order

1. Add the camera invariant tests, center-anchor/crosshair diagnostics, 0.15
   zoom, and full-world picking proof. Do not alter rotation math
   unless a proof demonstrates an actual failure.
2. Make the terrain binding uniformly pose-complete; copy the exact A1/F1
   files and validate q0..q3 selection.
3. Expand the existing detached-value draw pass to full terrain/static
   geometry. Prove dynamic evidence and display-settlement isolation before
   adding content.
4. Copy/bind C1/C2, extend the finite per-material wall grouping, and run its
   direct binding and real-map composition proofs.
5. Author the exact lodge/pond/storehouse world through existing engine
   builders and world initialization. Run engine placement and real pygame
   proofs.
6. Record the warm interaction performance check; run complete `tests/game`,
   affected engine world/senses/light tests, architecture tests, compileall,
   diff-check, and the clean documented venv launch.
7. Generate the required captures and obtain correctness, anti-slop, and
   anti-OOP/ECS acceptance on the exact candidate. Any repair invalidates
   affected results and visual acceptance.

Do not proceed past a step with a failing invariant or visibly wrong frame.

## 10. Expected touched files

Production/data:

- `game/projection.py`
- `game/app.py`
- `game/assets.py`
- `game/data/assets.json`
- `game/data/world_bindings.json`
- the exact copied PNGs under `game/assets/environment/`
- `dnd/scenarios/battlefield_catalog.py`

Tests:

- `tests/game/test_projection.py`
- `tests/game/test_assets.py`
- `tests/game/test_app_smoke.py`
- `tests/game/test_boundary_rendering.py`
- the existing engine battlefield/world-initialization test module that owns
  `battlefield.visual_vertical_seam`

No other production or test file is authorized without a reviewed amendment.

## 11. Stop conditions

Stop and amend this plan if:

- authored terrain requires live engine access or a second reduction path;
- full-map warm performance misses the fixed gate;
- a pose has a different verified pivot/scale than specified here;
- C1/C2 do not form a visually coherent straight/corner family;
- camera anchor tests fail for a reason not explained by current projection
  values;
- the broader battlefield breaks the accepted door/torch subjective sequence;
  or
- correct rendering would require a new engine rule, event type, material,
  scene graph, spatial index, or generalized asset resolver.

## 12. Acceptance required before implementation

The same final bytes of this plan require:

1. correctness review of camera math, evidence ownership, asset mapping,
   geometry, and validation coverage;
2. anti-slop review for speculative layers, duplicated state, overgeneralized
   data structures, and unnecessary scope; and
3. anti-OOP/ECS review confirming detached Event data remains authoritative,
   engine objects stay data/system composition, import direction remains
   `game -> dnd`, and no renderer concern enters engine schemas.

Any plan edit after acceptance invalidates all three approvals.
