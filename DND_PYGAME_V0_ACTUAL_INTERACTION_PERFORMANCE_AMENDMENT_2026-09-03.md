# Pygame V0 Actual-Interaction Performance Amendment

Status: `REVIEW CANDIDATE — NO FURTHER REPAIR AUTHORIZED`

This is a second, narrow amendment to
`DND_PYGAME_V0_FULL_MAP_CAMERA_STRUCTURE_DEBUG_PLAN_2026-09-03.md` and
`DND_PYGAME_V0_FULL_MAP_WARM_FRAME_PERFORMANCE_AMENDMENT_2026-09-03.md`.
It changes no world fact, presentation fact, camera result, pick result, asset,
Water pixel, painter key, evidence identity, or event-settlement rule.

## 1. Trigger

The first performance run omitted mouse picking by passing
`mouse_position=None`. The normal application always supplies the current
mouse position, and full-world height-aware picking is part of the accepted
debug seam. An independent rerun with the normal 4,096-candidate pick active
measured a 20.269 ms median at zoom 0.50, above the fixed 16.67 ms gate.

The exact acceptance protocol is therefore fixed here: SDL dummy at
1280-by-720; final closed-door presentation target; one loaded catalog and
surface cache; camera centered on `MAP_CENTER` at the start of each case; 60
discarded frames followed by 300 timed frames; `mouse_position=(0, 0)`;
grid off for the gate and on for the diagnostic; pan deltas over each repeating
40-frame cycle are `(1.5, 0.75)`, `(-1.5, 0.75)`, `(-1.5, -0.75)`, and
`(1.5, -0.75)` for ten frames each; pan precedes a `+1` quarter-turn whenever
the frame index is positive and divisible by 30; presentation time is the
frame index divided by 60; only `draw_frame` is timed. The grid-off median at
both zoom 0.15 and 0.50 must be at most 16.67 ms. Worst times and grid-on
medians remain diagnostic and are reported.

## 2. Exact repair

Only already-required work may be removed or shared:

1. `pick_support` must still visit every supplied detached candidate. For each
   distinct elevation encountered in that same call, it derives the inverse
   plane coordinate once instead of repeating identical camera math for every
   Tile at that elevation. The small call-local height-to-coordinate table is
   discarded on return. It is not persistent state, a world index, a spatial
   index, a cache between frames, or a second authority. Diamond containment,
   foremost ordering, UUID tie-breaking, returned candidate, and reported
   tested elevations stay exact.
2. `pick_support` expresses its existing three-field input as a static
   structural value contract (`position`, `elevation_steps`, `tile_uuid`) and
   returns the same input value type. `draw_frame` therefore passes the
   already-detached `WorldTileState` values directly instead of allocating
   4,096 duplicate `PickCandidate` wrappers. The concrete `PickCandidate`
   remains available for isolated projection callers and tests. This adds no
   runtime wrapper, conversion, inheritance, registry, or ownership. The
   optional grid may retain its own one-frame traversal. Candidate scope and
   count do not change.
3. Full-raster viewport rejection may express exact rectangle non-overlap as
   scalar edge comparisons rather than allocate 4,096 transient pygame Rects.
   The tested bounds remain the original full raster, including transparent
   margins.
4. Per-support Water treatment may apply the same unequal RGB multipliers in
   one owner-batch array operation before the existing per-support scatter.
   Owner chunks, active pixels, rounding, per-support surfaces/destinations,
   painter slots, and pixels remain identical.
5. Remove the redundant frame-local terrain treatment memo. The accepted
   `SurfaceCache` remains the sole persistent derived-raster cache and its
   counters observe every request.
6. The four quarter-turn coefficients become one immutable module constant
   used by both `rotate_position` and `project_world`. `project_world` applies
   those same coefficients directly instead of paying a second Python
   function call for every projection. All four formulas and all returned
   floats remain exact; no alternate projection or camera authority is added.
7. A direct shader dataflow check found that the imported graph's two normal
   samples terminate in `normal_xy`, which is never read by color, alpha, or
   any returned value—the same disconnected condition already documented for
   its detail branch. Remove only that dead evaluation. Retain the normal
   resource and public material argument so the copied material signature and
   catalog remain stable. The frozen TypeScript oracle and the complete
   pre-repair digest matrix must remain byte-exact, proving this is dead-work
   elimination rather than a visual approximation.

No early outside-map picking shortcut, reduced candidate set, persistent
hover state, scene graph, spatial index, dirty region, second cache, time
quantization, lower resolution, approximate shader, or altered diagnostic is
authorized.

## 3. Scope

The repair may touch only:

- `game/projection.py`
- `game/app.py`
- `game/water.py`
- `tests/game/test_projection.py`
- `tests/game/test_app_smoke.py`
- `tests/game/test_water.py`

## 4. Proof and acceptance

- Existing all-quadrant, all-height, overlap, and outside-world pick proofs
  remain green; add a counted iterable proof that all candidates are consumed
  while one inverse coordinate is shared per encountered elevation, and prove
  the concrete and detached-world value inputs select the same support.
- Exhaustively compare `rotate_position` and `project_world` against the prior
  formulas over every integer point in the 64-by-64 map, all four quadrants,
  and representative elevation steps.
- Freeze pre-repair Water SHA-256 outputs for both real owner chunks, every
  finite zoom, times 0.2 and 1.25, unequal treatments, and distinct screen
  positions. The repaired full restored RGBA raster must match every digest.
- The real full-map frame asserts 4,096 candidates and a viewport-bounded
  static submission count in addition to its grid bound.
- Complete `tests/game`, affected engine tests, relevant dependency/import-DAG
  architecture gates, compileall, and diff-check pass.
- The exact actual-interaction timing protocol above passes and is repeated
  after all code/test edits.
- Correctness, anti-slop, and anti-OOP/ECS reviewers approve the unchanged
  final candidate. Any repair invalidates those approvals and affected
  runtime/visual evidence.

If these exact reductions cannot provide reproducible headroom under the
16.67 ms median without changing observable semantics, stop for a new design
decision.
