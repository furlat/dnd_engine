# Pygame V0 Full-Map Warm-Frame Performance Amendment

Status: `REVIEW CANDIDATE — NO PERFORMANCE REPAIR AUTHORIZED`

This is a measured, bounded amendment to
`DND_PYGAME_V0_FULL_MAP_CAMERA_STRUCTURE_DEBUG_PLAN_2026-09-03.md`. It changes
no engine fact, event, reduction rule, map content, asset binding, camera rule,
Water appearance, or painter order.

## 1. Trigger and evidence

The accepted plan requires a warm median of at most 16.67 ms at zoom 0.15 and
0.50 and requires a focused amendment when that gate fails. On the exact
implemented map, after 60 discarded frames and during 300 panned/quarter-turned
samples at each zoom, SDL-dummy measured:

| zoom | grid | median | worst |
| --- | --- | ---: | ---: |
| 0.15 | on | 24.160 ms | 136.662 ms |
| 0.50 | on | 32.926 ms | 135.585 ms |

An isolating run showed:

| zoom | grid | complete scene | scene without Water |
| --- | --- | ---: | ---: |
| 0.15 | off | 18.571 ms | 14.510 ms |
| 0.15 | on | 23.707 ms | 20.215 ms |
| 0.50 | off | 28.864 ms | 11.110 ms |
| 0.50 | on | 32.321 ms | 14.286 ms |

One profiled 0.50 frame found the existing Water batch at 17 ms cumulative,
including 11 ms in the exact Water kernel. It also showed 4,086 static
`treated()` lookups and 4,159 full transparent-square visibility checks before
viewport rejection. Alpha inspection confirms the 128-by-128 Earth raster has
only a 64-by-40 nontransparent bound at zoom 0.50; the Water mask has a
63-by-32 bound. The failure is therefore concrete repeated transparent work,
not justification for a scene graph, spatial index, scheduler, or renderer
redesign.

## 2. Exact repair boundary

The repair may touch only:

- `game/assets.py`
- `game/app.py`
- `game/water.py`
- `tests/game/test_assets.py`
- `tests/game/test_app_smoke.py`
- `tests/game/test_boundary_rendering.py`
- `tests/game/test_water.py`

The already implemented full-map plan files remain in scope for their current
changes. No engine, scenario, projection, binding JSON, asset file, server,
SDK, TypeScript, or MapEditor change is authorized by this amendment.

## 3. Static raster repair

Extend the existing `SurfaceCache`; do not add another cache/controller.

For a finite scaled/treatment key, retain the smallest alpha-bearing rectangle
and its offset from the original full raster. Static terrain, wall, door, and
fixture draws use that cropped treated surface at:

`original authored destination + alpha-bound offset`.

The crop is computed from the already-scaled surface and cached with the
existing finite derivative. It is a lossless omission of pixels whose alpha is
zero. Painter keys, evidence rows, authored pivots, support contacts, and draw
order do not change. Procedural Water sampling continues to receive the full
scaled mask coordinates; the optimization must not silently alter its world
UV origin.

Before asking the cache for a treated static raster, `draw_frame` may reject
the translated **full scaled-raster rectangle** against the viewport. It must
use the same full rectangle as the current implementation, not the tighter
alpha bound: a transparent margin intersecting the viewport still retains the
same draw evidence and settlement eligibility even when the submitted cropped
surface has no visible pixel in-frame. The alpha bound is used only to reduce
the submitted surface and to add its offset to the authored destination. The
renderer still enumerates all 4,096 detached Tile candidates and all static
objects. No spatial index, dirty rectangle, scene node, or second ownership
structure is added.

## 4. Water repair

Keep `shade_water_packed` as the one source-faithful mathematical kernel and
keep the frozen TypeScript oracle tolerance unchanged.

The repair is limited to removing repeated representation work around that
same calculation:

1. Normalize each immutable ripple/normal source texture once in the existing
   `SurfaceCache.rgb` entry rather than copying and normalizing both 512-square
   textures for each owner chunk and frame. Direct uint8 inputs to the public
   kernel remain supported for the oracle test.
2. Build returned per-support pygame surfaces only over the mask's
   alpha-bearing rectangle. Local sample coordinates remain coordinates in the
   original full scaled mask, and each returned destination receives the same
   rectangle offset. This may be expressed by adding a matching destination
   tuple to `WaterBatchOutput`; it must not move sampling, merge painter slots,
   or change per-Tile evidence identity.
3. Remove avoidable temporary arrays or repeated material decoding inside the
   batch only where pixel-for-pixel comparison proves equivalence. Do not
   quantize time, skip animation frames, lower Water resolution, memoize by
   presentation time, introduce workers, or approximate the shader.

The two existing 16-by-16 owner chunks remain the only batching boundary.
Water stays before terrain/static structure in the accepted painter law.
`WaterBatchOutput.destination_bounds` remains the original full-mask authored
footprint used by calculation evidence. Cropped per-support blit destinations
are separate output metadata and cannot redefine that diagnostic bound.

## 5. Grid and acceptance clarification

The grid is an explicitly toggleable debug overlay, not scene content. The
warm 16.67 ms acceptance run is performed with `G` off so it measures the
rendered world rather than 4,096 diagnostic polygon submissions. A second
grid-on run is recorded honestly but is diagnostic, not the gameplay-frame
gate. No grid cache or special rectangular-map algorithm is authorized.

Both runs still pan and quarter-turn. Each zoom discards 60 frames and samples
300. The required result remains median <= 16.67 ms at 0.15 and 0.50 with the
grid off. Worst times and grid-on medians are reported, not hidden.

## 6. Proofs

Before acceptance:

- cropped and uncropped static composition must be pixel-identical, including
  an asset partially clipped by every viewport edge;
- one transparent-margin-only fringe case must preserve draw evidence,
  `static_draws`, and display-settlement eligibility even though the cropped
  submission contributes no visible pixel;
- the cached alpha offset plus cropped destination must resolve to the same
  authored contact in all four camera poses and all finite zooms;
- the frozen Water oracle remains within its existing channel tolerance;
- split and unsplit Water batches remain pixel-identical;
- old and repaired Water output are pixel-identical for both owner chunks,
  all finite zooms, at two nonzero times, with unequal treatments and screen
  positions;
- the Water/wall real-pixel painter regression remains green;
- the real frame retains 4,096 candidates, exact evidence identity, viewport
  culling counters, objective/subjective treatments, and door/fixture
  settlement isolation;
- complete `tests/game`, affected engine tests, architecture, compileall, and
  diff-check remain green; and
- the exact warm protocol is rerun and recorded.

## 7. Anti-slop and ECS constraints

This amendment adds no manager, renderer class hierarchy, scene graph, spatial
index, background worker, callback, compatibility path, engine field, event,
or second state authority. Cache keys contain render inputs only. `game`
continues to consume detached engine values; `dnd` never imports `game`.

If exact pixel equivalence fails, or the scoped representation repair cannot
meet the grid-off median gate, stop for a new decision. Do not trade away the
Water oracle, animation continuity, evidence identity, or painter semantics.

## 8. Acceptance before repair

The same bytes require correctness, anti-slop, and anti-OOP/ECS review. Any
edit after approval invalidates all three approvals.
