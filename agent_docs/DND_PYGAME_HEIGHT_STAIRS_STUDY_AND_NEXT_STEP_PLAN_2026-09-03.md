# Pygame height and stairs: study and next-step plan

Status: **reviewed study and staged plan; no height implementation authorized**.

This continues V-1 of `DND_IN_PROCESS_PYGAME_SYSTEM_ARCHITECTURE_ROADMAP_2026-09-02.md`.
It does not start a new engine, editor, importer, networking layer, or encounter
controller. The immediate user request is to investigate height and stair art,
then plan the next small extension of the current 64-by-64 map.

## 1. Starting point and prerequisite

The separate doorway follow-up removes the false-shadow-like memory contrast
with one RGB-row change. Its real-frame regression passed and the full pygame
suite has 201 passing tests. The door/masonry join is **not** declared fixed:
source pivots match, but global masonry-last ordering hides exposed open
leaves. Human visual acceptance of that join and a demonstrated depth rule are
still required before accepting a height implementation. Read-only height
study can proceed without pretending that prerequisite is complete.

The deliverable here is an evidence-backed staged plan. The calibration and
stair-to-support questions below must be resolved before a practical code
patch is authorized. Review acceptance of this study does not approve an
unwritten sorting algorithm or a new gameplay rule.

## 2. Existing authorities — reuse these

| Question | Current owner/value | Meaning |
| --- | --- | --- |
| Where is the support? | `Tile.position`, `WorldTileState.position` | Exact engine `(x,y)`; never shift these to fit a picture. |
| How high? | `Tile.height`, `WorldTileState.elevation_steps` | Integer five-foot steps, including negative values. |
| What kind of support? | `ElevationSurfaceKind` | `ORDINARY`, `STAIRS`, `RAMP`. |
| Along which axis? | `SlopeAxis` | North/south or east/west, not an independently stored uphill direction. |
| What is its material? | `Tile.surface` / `TileSurface` | Existing graphic-independent terrain semantics. |
| Where does a placed item sit? | `WorldObjectPlacement` | Owner Tile, boundary side or center, orientation, base and top heights. |
| How does walking climb? | `progressive_elevation_transition` and `GridMap` | Adjacent height difference exactly one; both supports must be the same progressive kind and aligned to the edge axis. |
| What is a special transfer? | `TraversalConnector` | An existing explicit route with endpoints, costs and policy; not the same thing as ordinary stair Tiles. |
| How does the client learn the world? | `WorldInitializedEvent`, `WorldModifiedEvent` | Detached world state; no renderer reads of live Tile/GridMap registries. |

The engine has **one support Tile per XY**, not independently walkable floors
stacked at the same XY. Object vertical bands do not change this. No bridges
with underpasses, stacked rooms, free Z movement, or fine64 grid conversion in
this slice.

`DirectionalWall` and `DirectionalDoor` currently occupy two height steps.
Their placement base may differ from the support height; draw from the stored
base, not by adding the Tile's height again. `BoundaryStructureKind.CLIFF`
exists as vocabulary, but there is no concrete cliff provider in
`dnd/items/environment.py`. An enum is not an implemented physical item.
Do not invent a second world-object schema or relabel a wall to fill that gap.

## 3. Height is an offset after horizontal camera rotation

Retain `game/projection.py` as the sole projection owner. For rotated planar
coordinates `(u,v)` and height `h`:

```text
world_px = (64*(u-v), 32*(u+v) - 64*h)
screen_px = zoom * world_px + pan
```

Thus one engine step (5 ft) is 64 native pixels vertically; a two-step terrace
is 10 ft and 128 pixels. These pixel constants are client calibration, not
engine units or values stored on Tiles.

Camera rotation acts only on engine XY around the existing map center. Height
always lifts upward on screen. Raising `(x,y)` must not translate it to
`(x+h,y+h)` in the engine. That latter transformation appears in MapEditor's
flat-image reconstruction only because it preserves an already drawn picture:
`P(x+h,y+h,h) = P(x,y,0)` at the reference view. We are authoring an actual
world, not reverse-engineering a flat image, so we must not port that rebase.

Z grids need no new runtime objects: distinct heights already define the
parallel projection planes. Keep existing pan/zoom/rotation contracts. For a
rotated capture use exactly the same world anchor, zoom and viewport; report
the viewpoint and engine N/E axes, not ambiguous screen directions.

## 4. What the actual stair assets contain

Inspected local catalog, source scene, model rules, and native PNGs:

- `public/assets/fantasy/catalog.json`: exact resource paths and defaults;
- `src/model/causalHeight.ts`: `directionalHeightGeometry`,
  `elevationTraversalForAssetLabel`, `cliffBoundaryDirections`;
- `docs/CAUSAL_HEIGHT_ASSIGNMENT.md` and
  `docs/FORMAL_HEIGHT_GRAPH_AND_ISOMETRIC_GEOMETRY.md`;
- `docs/WESTERN_MULTI_HEIGHT_VERTICAL_COMPLETION_STUDY.md`: correction of
  earlier assumptions, notably that a stair does not delete its base surface.

All are under `/home/tommaso/Dev/NeuroMapEditor`. The source's labels and
inference rules are evidence for the artwork, not engine authority.

| Family | Inspected role | Native visual rise | Initial disposition |
| --- | --- | --- | --- |
| Ground G17 E/N/S/W | Clean stair lane | 128 px / two Z-grid levels | First flight candidate. |
| Ground G16 E/N/S/W | Rocky edge of the same stair family | Same two levels | Optional side lane after one flight fits; not a second flight. |
| Ground G12, G13, G14 | Tall rocky face and two corner topologies | 128 px / two levels | Candidate sides for a small two-step terrace. Validate corner contacts before binding. |
| Ground G1–G5 and G8–G11 | Low banks | 64 px / one level | Studied but deferred; G1–G5 suffix normals differ from G8–G11. |

G16/G17 are 256-by-256 transparent PNGs, catalog pivot `(128,208)`, scale 1,
zero occurrence offset. Catalog E has exact Unity correspondence; N/S/W
exist locally but have no matching source occurrence in this catalog. That
does not make them missing; all four were visually inspected. E/S show the
stair surface; N/W are thin rear profiles, not broken or empty resources.
They require correct adjoining terrain and occlusion, not mirroring or
rotating an E PNG. Calibrate the assembled result in all four cameras.

Catalog defaults and imported occurrence transforms are not interchangeable.
The source scene contains 8 G16_E and 12 G17_E occurrences at pivot
`(128,207.36)`, scale `128/127`. Tall G12/G13/G14 source occurrences instead
use pivot Y `145.92`, with the same scale (a few also have a 0.128px Y offset).
The editor's physical-height model rebases those cliff owners and normalizes
their pivots to a base contact. H0 must compare the canonical catalog assembly
against that documented contact geometry. Never combine an imported top-pivot
with a canonical base owner or apply the same vertical lift twice. Record the
chosen complete owner/pivot/scale convention before copying any assets.

One G17 depicts a complete flight, not one five-foot step and not one full
flat Tile. Adjacent G17s widen a flight; they do not increase its rise. G16
adds the rocky side treatment. Do not stamp a complete flight once per
progressive support Tile.

For the editor's reference E art at owner `p`, its documented visual contacts
are:

| Contact | Native pixel offset from owner | Editor interpretation |
| --- | --- | --- |
| Entry | `(+64,0)` | Corner at base level |
| Midpoint | `(0,-64)` | Contact at base + 1 |
| Top contact | `(-64,-192)` | Shared corner at base + 2 |
| Upper landing center | `(-128,-192)` | `p + (-2,0)` at base + 2 |

Those contact identities mix corners and centers. They are **not four engine
Tiles**, and in particular the editor's same-XY midpoint must not become a
second walkable support at that XY. A legal tactical footprint has to be
checked against them, not copied verbatim.

Direction tables must be derived and checked for this family. MapEditor's
`causalHeight.ts` asset-suffix table uses `+Y = south`, while its own
`lattice.ts` cardinal table uses `+Y = north`, like this engine. Those are
different conventions even inside the source project. The old bridge note's
wall pose table was also superseded by the corrected `camera_pose()` code.
Do not reuse a wall table on stairs or cliffs merely because filenames end
with the same letters. A small client-side family binding can express the
verified conversion; no asset suffix enters the backend.

## 5. What already works, what is missing

Already implemented:

- support projection and inverse projection accept height;
- terrain and items use their stored support/base elevation;
- picking tests candidate height planes rather than silently assuming Z=0;
- world snapshots contain support height, stair/ramp kind and slope axis;
- the maintained `battlefield.elevation_proving_ground` builder in
  `battlefield_catalog.py` already authors progressive height rows and special
  connector examples;
- `set_world_tile_elevation` already creates a `WorldModifiedEvent` root with
  a `TileElevationChangeEvent` spatial child and complete Tile before/after.

Missing in pygame:

- visual stair/terrace-side binding; `draw_frame` currently selects ordinary
  Earth/Wood/Water and ignores `surface_kind`/`slope_axis` when selecting art;
- demonstrated multi-height composition: the current global terrain-before-
  walls and leaf-after-walls phases are not proof that foreground raised
  ground will cover a lower object behind it;
- a verified stair footprint, pose and contact mapping;
- admission/reduction/display accounting for runtime Tile-height edits:
  current capture admits startup, the selected door, standing torch and
  sensory events, not general `WorldModifiedEvent` or elevation children.

Preserve the current async producer -> detached interval -> reducer -> draw ->
settlement path. Do not add a height queue, parallel scene state, polling,
callback chain, or a new event type.

Optics caution: current edge blocking uses vertical intervals for walking,
but its nonmovement channel check is not a 3D ray/face intersection. Height
rendering does not imply light passing above low walls or under bridges.
Keep present engine optics and neutral composite-wall treatment; do not invent
shadows or advertise physically height-aware lighting from prettier pictures.

## 6. Proposed sequence

### H0 — small contact/depth calibration, before map implementation

Use the selected real PNGs with explicit engine-coordinate test values. This
is a bounded diagnostic fixture, not a new gameplay gallery or map importer.

1. At heights 0, 1, 2 and one negative example, verify a fixed support contact
   moves exactly by `-64*h*zoom` and preserves XY in all four cameras.
2. Assemble one G17 with lower and upper floors. Overlay the source entry,
   midpoint, top and landing contacts AND the proposed engine support centers.
   Inspect all four suffixes/cameras at native scale and the usual zooms.
3. Try the existing progressive-support model first: a finite straight run
   with heights 0,1,2, matching `STAIRS` kinds/axis, same-height ordinary
   entry/exit neighbors, and one complete flight drawn for that run. Determine
   whether its physical support centers and landing lie on the actual art.
   This is a hypothesis, not an accepted mapping. Document which supports the
   flight represents and which floor pixels it replaces; preserve their
   engine identities. An ambiguous/nonmatching run remains unsupported.
4. Do not replace that run with `VERTICAL_STAIRS` merely to fit the picture:
   that connector is an adjacent endpoint transfer, not multi-cell progressive
   walking. Do not weaken its endpoint validation to accommodate G17.
5. Compare the existing painter output against concrete overlap cases:
   raised foreground floor versus lower rear wall/torch; low foreground
   wall/torch versus raised rear floor; open/closed door at its own height;
   stair upper landing versus flight rear profile; mixed-height wall corners.
   Use actual assets and identify the pixels that must be in front.
6. Derive the smallest sufficient ordering rule from those cases and record
   it before editing production. Neither lifted screen-Y alone, unlifted
   contact alone, nor globally drawing all upper floors last is accepted by
   assertion. No general occlusion graph, per-pixel depth, sprite slicing, or
   scene graph is authorized by this study.

Exit: reviewed four-camera contact/overlap evidence, one accepted stair
footprint, and an explicit bounded painter rule. If these fail, report the
specific mismatch/needed choice rather than inventing mechanics or offsets.

### H1 — one small authored terrace in the current map

After H0 and a practical patch plan are accepted, add one coherent terrace
near the lodge, with support heights 0 and 2 and one approved stair run through
height 1. Keep the 64-by-64 map, lodge, pond, storehouse, real door and torch.
Use ordinary Tile values/builders, not a new terrain object hierarchy.

Place a short existing wall/door or standing fixture on the upper surface
only after its support height is authored. Its stored base/top must agree;
do not add height a second time in rendering. Keep the original door seam as
a regression rather than redesigning both buildings at once.

Recommendation for the first exposed terrace side: derive a visual terrain
riser from two neighboring support heights and their existing material.
That draw represents the high Tile's terrain, not a new targetable wall/item
or a new optical blocker. Plain walking already rejects an ordinary height
step. Validate the selected rocky G12/corner art against that semantic use.
If independently targetable/optically blocking cliff objects are wanted,
that is a separate backend rules decision, not an implicit part of drawing a
height discontinuity. Do not silently add a cliff provider now.

No source inference, flood/height solver, missing-wall reconstruction,
runtime asset-name heuristics, extra maps, ramp family, multilevel rooms or
large terrain library. Copy only the finally selected poses after H0.

### H2 — picking, movement and dynamic edit proof

- Hover reports the chosen Tile UUID/XY, support steps/feet, projected contact,
  all tested height planes and all matching support candidates, plus viewpoint.
  Current picking returns tested levels and only the winner; expose the
  actual overlapping candidates in the existing diagnostic output if needed.
- Pick the foremost rendered support consistently with the accepted ordering.
  Do not make a cliff facade a new walkable Tile or call a sprite hit a support
  hit. Stair contact/pick semantics must follow H0's accepted footprint.
- Use existing public movement for the accepted run: walking up/down succeeds;
  ordinary cliff crossing and height-changing wrong-axis stair crossing fail.
  Same-height sideways movement remains allowed by the elevation rule, subject
  to the usual occupancy/boundary checks. No renderer position writes; no new
  character animation subsystem in this step.
- For live height, first edit one unoccupied ordinary support through
  `set_world_tile_elevation` and retain its normal child/sensory cascade.
  Existing guards against changing supports with center objects or anchored
  connectors remain in force; do not auto-lift contents or bypass them.
- Extend the existing capture/reducer/display branches only for the selected
  completed Tile-height edit. The full structural after-value replaces that
  Tile; sensory knowledge still comes from the sensory child stream. Reduce
  the Tile state once (root after-value), account for the spatial child without
  applying the change twice, and settle only after actual rendered evidence
  includes the correct Tile UUID/height. Unsupported edits stay explicit.
- Queue two completed height changes ahead of rendering to prove old displayed
  geometry remains stable until its interval is consumed. No live GridMap
  reads, board rebuild or special height completion system.

### H3 — acceptance before adding more vertical content

- Four-camera original-resolution captures of the same fixed world anchor,
  open/closed door, terrace sides, stair landings and object bases.
- Projection/picking cases with overlapping screen positions and different
  heights, negative height, rotation/pan/zoom and correct corner ownership.
- Public engine movement and world-modification tests, event replay through
  the detached renderer, and complete `tests/game`.
- Verify the existing XY optics behavior and no invented directional tint;
  list its height limitations honestly.
- Re-run the current warmed 64-by-64 interaction protocol. Contour lookup is
  bounded neighboring-Tile work, not a world scan for every sprite; no new
  cache or index unless a measured failure justifies a separate amendment.
- Correctness/visual, anti-slop, and anti-OOP/ECS review. Human visual approval
  is required for the previously disputed doorway and the new height assembly.

## 7. Likely later patch boundary, not current authorization

Expected client paths: existing `game/projection.py`, `game/app.py`,
`game/presentation.py`, asset/binding JSON, finally selected environment PNGs,
and relevant `tests/game` modules. Authored content stays in
`dnd/scenarios/battlefield_catalog.py`; existing engine geometry and world-edit
tests supply mechanical proofs. Any new engine rule/schema, broader event
admission, or different ordering architecture needs an explicit reviewed
amendment. No server, SDK, TypeScript, MapEditor or source-asset edits.

## 8. Review questions

Correctness: Are support facts, art contacts, rotations, overlap requirements,
progressive walking and special connectors distinguished without overclaiming
implemented behavior? Are remaining hypotheses explicit?

Anti-slop: Is this a small extension of the current map/client, with no copied
image-to-map solver, generic height manager, importer, cache or render framework?

Anti-OOP/ECS: Do engine objects remain existing data/system compositions, with
height owned by Tiles, placement by GridMap, runtime facts by existing events,
and assets/projection only client-side?

## 9. Review outcome and evidence

Correctness, anti-slop, and anti-OOP/ECS reviewers approved this study and its
staged scope. Approval does not resolve the stair-footprint or painter-order
hypotheses, accept the doorway join, or authorize height implementation.
The ECS review clarified that wrong-axis rejection concerns height-changing
crossings; same-height sideways movement retains the existing rules.

Read-only rerun of six existing engine tests: **6 passed in 0.63s**. These cover
progressive endpoint matching, strict support data, elevation completion and
cancellation, the existing WorldModified/elevation-child relationship, and
invalid owner rejection. They establish current engine behavior, not a new
pygame height capability. The separate doorway correction passed all
**201 pygame tests**.

Native stair/cliff asset study, source E/N/S/W columns:
[asset contact sheet](/mnt/c/Users/tommaso/.codex/visualizations/2026/08/14/01a00009-b71d-72e3-9fa6-9520e110433c/doorway_followup_2026_09_03/height_asset_study.png).
Current flat-map closed/open/reclosed captures, all four cameras at the same
world focus:
[four-camera evidence](/mnt/c/Users/tommaso/.codex/visualizations/2026/08/14/01a00009-b71d-72e3-9fa6-9520e110433c/doorway_followup_2026_09_03/all_views.png).

No height production/test changes or new assets were introduced for this
study. Next is H0's contact/depth evidence, followed by the bounded practical
patch plan; the original doorway alignment concern remains open.
