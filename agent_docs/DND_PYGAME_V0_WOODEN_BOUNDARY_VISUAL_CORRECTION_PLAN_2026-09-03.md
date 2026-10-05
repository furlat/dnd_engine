# Pygame V0 Wooden Boundary Visual Correction Plan

Status: `REVIEW CANDIDATE`

This plan replaces only the wall/door asset and direction claims in
`DND_PYGAME_V0_VERTICAL_SEAM_CORRECTIVE_IMPLEMENTATION_PLAN_V2_2026-09-03.md`.
The V2 document remains unchanged as evidence of the rejected candidate. All
other accepted V0 vertical-seam boundaries remain governing.

## 1. Failure being repaired

The current screenshots are visually invalid. The wall objects are real and
their engine placements are stable, but the renderer selects asset poses using
an invented cardinal permutation:

```text
north -> w, east -> s, south -> e, west -> n
```

The permutation makes the Sprite's long axis perpendicular to the projected
wall run in some camera quadrants. Repetition then looks like isolated slabs,
overlapping columns, and a floating doorway instead of a wall.

The second error is semantic. `DirectionalWall` currently reports stone while
the selected replacement art is a wooden palisade. The renderer must not infer
wood from a generic wall kind while the engine says stone.

The previous filename/event reviews did not inspect the four rendered views at
original resolution. Their visual approval is rejected.

## 2. Evidence and fixed vocabulary

The correction uses the imported NeuroMapEditor catalog and scene as asset
evidence, not filename intuition:

- `Wall B1_{E,N,S,W}` is the straight wooden palisade family.
- `Wall B4_{E,N,S,W}` is the wooden palisade gate family. The imported scene's
  B4 gate is flanked by B1 segments on the same macro128 run.
- both selected families use a 256 by 256 canvas, pivot `(128, 208)`, scale `1`,
  zero occurrence offset, and a `grid-contact` anchor;
- MapEditor macro128 projects an adjacent engine cell by one 128 by 64
  isometric diamond; and
- the existing pygame `project_screen(owner_tile_position, camera)` therefore
  remains the correct visual support contact. No midpoint, shared edge, inset,
  or hidden half-cell offset is added.

The engine law remains unchanged: a wall or door belongs to one Tile and one
explicit boundary side. Two incident Tiles may independently own structures;
the renderer never canonicalizes them into one between-cell object.

## 3. Exact cardinal bridge

`CardinalDirection` and `rotate_position` use the same engine plane. Replace
`camera_pose`'s handwritten `r0` permutation with the finite rotation of the
direction itself:

| Engine direction | Q0 | Q1 | Q2 | Q3 |
|---|---|---|---|---|
| NORTH | N | W | S | E |
| EAST | E | N | W | S |
| SOUTH | S | E | N | W |
| WEST | W | S | E | N |

The resulting lower-case cardinal is the asset suffix directly. The helper is
pure and may be named `camera_pose`; no asset-specific direction service or
adapter is introduced.

For every row in the table, the projected tangent between adjacent owner Tiles
must be collinear with the selected B1 Sprite. Tests must cover all 16 cells,
not only one EAST example.

## 4. Honest wooden engine facts

Make `DirectionalWall`'s material an ordinary strict data field with default
`Material.STONE`, and have `get_boundary_structure()` return that field. This
preserves every current caller while allowing the proving battlefield to
instantiate the same existing component as:

```text
DirectionalWall(name="Wooden Palisade", material=Material.WOOD)
```

Do not add `WoodenWall`, an asset-bearing engine subtype, a material registry,
or a renderer callback. `DirectionalDoor` already reports `Material.WOOD` and
needs no engine redesign.

The existing `build_directional_wall()` content helper gains the keyword
`material: Material = Material.STONE` and forwards it directly into
`DirectionalWall`. The eleven battlefield calls pass `Material.WOOD` through
that normal helper route. Do not bypass the helper, add a second builder, or
alter `build_cliff_face` or unrelated callers. Existing omitted-material callers
remain stone.

The battlefield changes only the eleven wall instances' authored name and
material. Positions, sides, blocked channels, UUID ownership, visibility,
lighting, movement, and event behavior remain unchanged.

## 5. Direct asset bindings

Copy only the eight selected B1/B4 PNGs from NeuroMapEditor into the local
pygame asset directory. Bindings are semantic and finite:

```text
wooden_palisade.straight.{e,n,s,w} -> wall-b1-*.png
wooden_palisade.gate.closed.{e,n,s,w} -> wall-b4-*.png
wooden_palisade.gate.open -> no Sprite
```

The open door is represented by the disclosed one-cell opening and the normal
subjective text/event coverage; it is not represented by a fabricated open
asset. Do not retain an active stone arch, door leaf, or D8 binding in this
wooden battlefield. Do not add hashes, authentication, discovery, fallback
assets, path guessing, or a general material resolver.

The renderer chooses this table only when the disclosed boundary structure's
material is `WOOD`. An unsupported material/family is a closed coverage error;
it may not silently render the wooden family.

## 6. Straight walls and gate state

For each disclosed wooden wall:

1. retain its owner Tile position and boundary direction;
2. rotate the direction by the camera quadrant using section 3;
3. select B1 with that direct suffix;
4. use the owner Tile's existing projected macro128 support contact and
   elevation; and
5. retain the existing semantic painter key and subjective light treatment.

For the disclosed wooden door:

- closed: draw exactly one B4 Sprite at the same support contact and pose rule;
- open: draw no boundary Sprite, leaving the one-cell gap;
- retain the door UUID/state in displayed semantic state and event coverage in
  both cases; and
- do not manufacture frame/leaf entities or animation events.

Opening and closing still come solely from the existing door action. Startup
arrives through `WorldInitializedEvent`, the door transition arrives through
the admitted `SpatialChangeEvent`, and disclosure/light changes arrive through
selected-observer `SensoryUpdateEvent`. Rendering never changes the door.

The open gate's intentional no-Sprite result records one primitive tuple in the
existing calculation-evidence set containing the original door UUID and
`is_open=True`, after the contacted/disclosed gate is evaluated. The original
source Event index is represented from that evidence. Do not add a new
disposition, Event, object, or coverage key.

## 7. Corner readiness, explicitly deferred

`Wall B2_{E,N,S,W}` is the wooden corner family, and the imported MapEditor
scene proves how it joins B1 runs. It is not copied, bound, or rendered in this
repair because the proving battlefield contains no same-Tile adjacent wall
pair. Adding grouping, source consumption, suppression, mixed-treatment rules,
and two-UUID evidence without an end-to-end authored corner would be premature.

The cardinal correction in section 3 is the necessary foundation for corners.
The first real map containing a corner must author two independent
`DirectionalWall` facts on adjacent sides of one Tile, then define and prove
the B2 presentation composition through the ordinary
Event/reduction/rendering path. It must not create a gameplay corner object or
merge either wall identity. This is a later, bounded visual slice rather than
hidden scope in the straight-wall repair.

## 8. Implementation order

1. Add the material field, forward it through the existing
   `build_directional_wall()` helper with a stone default, and prove both the
   unchanged default route and the battlefield's wooden projection.
2. Replace the cardinal mapping and its exhaustive 16-case proof.
3. Copy and bind B1/B4; retire the active D8/D6/A1/A2 tables.
4. Render the existing straight wall and B4 gate with open/closed state.
5. Run focused engine, presentation, projection, asset, water/light, and app
   lanes before the complete game lane.
6. Capture startup, open, and closed states in Q0-Q3 at original resolution.
   Inspect every image. Any perpendicular segment, discontinuity outside the
   intentional open gate, floating gate, wrong corner, or owner-contact drift
   rejects the candidate regardless of test results.

## 9. Required proof

Automated proof must establish:

- all 16 direction/quadrant mappings in section 3;
- B1 repeated at adjacent owner contacts forms one connected alpha component
  in every camera quadrant;
- replacing the center segment with B4 remains connected when closed and has
  exactly the intentional one-cell opening when open;
- the battlefield projects `Material.WOOD` for its walls and door;
- an omitted-material `build_directional_wall()` caller still builds and
  projects `Material.STONE`;
- wall/door visibility and light treatment still use subjective state;
- opening and closing remain driven by the existing event stream;
- no visual asset ID/path enters engine state or events;
- no frame performs a 4,096-Tile scan; and
- all existing V0 lifecycle, queue, water, light, picking, and shutdown gates
  remain green.

## 10. Review and stop rules

Before implementation, the exact bytes require:

1. correctness/visual-geometry approval against GridMap, MapEditor source
   occurrences, and the four diagnostic views;
2. anti-slop approval that the change is finite and adds no resolver, facade,
   registry, discovery, hash, cache tier, corner composition, or duplicated
   event/state model; and
3. anti-OOP/ECS approval that material is data, rendering composition does not
   mutate or merge engine components, and import dependencies remain a DAG.

After implementation, the same three concerns review the exact rendered
candidate. Test success without original-resolution screenshot inspection is
not acceptance.

Stop for user direction if the B4 closed / empty open representation is not
acceptable. Selecting an invented open asset or retaining the stone doorway is
not authorized.
