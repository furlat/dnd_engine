# Small cliff terrace and stair flight

Status: bounded implementation complete and reviewed. Functional and visual
checks passed; unrelated baseline failures and launch-timing variability are
recorded below. No expansion to further height features is authorized here.

User authorization: bring cliffs and stairs from NeuroMapEditor into the
current pygame map, retaining their layer, support, direction and height data.
This is the first static assembly from the reviewed height study. Runtime
height editing, extra encounters, stacked floors and broader content remain
later work. The disputed existing doorway join is not declared fixed by this
addition; its open/closed four-camera appearance remains a regression check.

## Boundary and expected result

Existing battlefield creation -> detached WorldInitializedEvent -> existing
presentation reduction -> real pygame frames. One five-by-five earth terrace
at height 2 (10 ft), rocky straight/convex cliff sides, and one full two-step
flight with three existing STAIRS supports at heights 0,1,2. One support per
XY throughout. Current map remains 64 by 64; buildings, pond, door, light
sequence, controls and queues remain intact.

Use plateau x26..30/y18..22, with lower stair (28,24,h0), middle (28,23,h1),
upper (28,22,h2). All three use STAIRS/NORTH_SOUTH. Neighboring same-height
ordinary supports provide entry/exit. No new engine schema, systems or classes.
Cliff faces are visual parts of elevated terrain, not secretly targetable
items or new light blockers.

## Recovered asset data, not source inference

NeuroMapEditor `AssetDefinition.elevationBoundary` supplies face normals,
rise, supported-surface footprint and material role. Its
`elevationTraversal` supplies direction, edge/continuation lane role, total
rise, entry/mid/top/landing contacts and upper support footprint.
`VisualPlacement.visualTilemapId` is separate from `zGridId` and the contact.

Source scene occurrences: G16/G17 use Ground 2 (-11) and Ground 3 (-10).
G12/G13/G14 occur in Ground, Ground 2, Ground 3, Walls and (some) Objects.
There is no single universal source layer for every cliff. Preserve explicit
client rendering roles; never interpret sortingOrder or Ground 3 as height 3.
Do not port the image-to-map height inference, source rebase or gap solver.

Copy only G12 straight, G13 convex corner and G17 stair E/N/S/W PNGs (12 files).
G14 and rocky stair side G16 stay deferred until actually needed. Keep
canonical 256px resources, scale 1. Add direct JSON bindings with explicit
draw role, two-step rise, face/footprint/contact data and four poses. Engine
enums and support facts select the binding; PNG names never drive gameplay.

## H0 calibration carried into the patch

Actual whole G17 rasters have these entry-edge center contacts. Express each
as its pivot so the existing placement projection maps the lower Tile center
to that contact. This is a contact conversion, not a moved engine Tile.

| Asset pose | Lower edge/pivot | Mid tread contact | Upper edge |
| --- | --- | --- | --- |
| E | (160,224) | (96,128) | (32,32) |
| S | (96,224) | (160,128) | (224,32) |
| W | (96,192) | (160,160) | (224,128) |
| N | (160,192) | (96,160) | (32,128) |

An uphill -X run projects by (-64,-96) per step in q0. These contacts match
exactly a two-cell run rising two engine steps. Rotation yields E,S,W,N;
other downhill directions are the corresponding rotations. This family
mapping has been derived from its contacts, not assumed from wall filenames.
The source's corner contacts and imported pivot are not these tactical
center contacts. Do not replace source documentation with the conversion.

Cliffs keep catalog pivot (128,208), base at the lower height, top at base+2.
Upper flat terrain draws at its real elevation. G13 corners combine two
perpendicular exposed faces; defer the alternate G14 corner topology. The source
pose naming uses +Y=S while engine +Y=N; convert explicitly client-side.

The diagnostic `/tmp/dnd-height-calibration-MtI8V0/study.py` assembles actual
cliffs, upper/lower terrain and flight in all four cameras. Front views show
the flight, back views occlude its thin rear profile. It also exposes why
deleting the base terrain produces black holes beside the stair. Preserve a
lower decorative ground bed beneath the raised-terrain/stair assembly, then
draw its actual cliff/top/tread subparts. This bed uses the assembly's actual
lower support datum; it is not a second walkable floor. The completed
diagnostic includes the lower bed beneath all raised terrain and closes those
background gaps. This is an engine-to-art composition using the source
rasters, not a pixel-identical copy of the editor's inferred support graph.

## Small rendering change

1. In existing app code, derive the finite accepted three-support stair runs
   from detached Tile kind/axis/heights using bounded cardinal lookups. Keep
   the three support UUIDs. Reject malformed/overlapping ambiguous runs;
   do not render an ordinary floor and quietly call it a stair.
2. Existing binding JSON supplies each supported family role, rise, contact
   convention and pose table. No new framework/catalog loader or asset scan.
3. For the accepted raised assembly derive exposed straight/two-face convex
   contours from neighboring heights. Omit only the cliff face crossed by
   the accepted stair flight. One flight raster per run, not per support.
   A complete three-support run is required before its midpoint floor is
   replaced by tread art. Support identity stays intact.
4. Ground bed has no Tile, pick candidate, occupancy, senses or independent
   height. Its evidence is explicitly a decorative bed draw; it cannot alone
   count as displaying the middle-height support. Actual tread evidence lists
   the three UUIDs and heights. Top floor and placement bases retain height.
   Whole cliff and stair sprites use the existing neutral structural
   treatment, like composite walls. Record each involved support's real
   current/memory/authored status and effective light separately in evidence;
   never extend the lower Tile's light/disclosure to the whole flight. Ground
   bed is neutral structural decoration. Existing actual flat support surfaces
   retain their existing per-Tile treatment. Add a mixed-state/light support
   regression; no face shading, masking, shadows or sprite splitting.
5. Separate low planar water/ground from spatial cliff/top/stair/object draws.
   Within spatial draws use rotated physical planar depth before local role:
   cliff, upper floor, stair, frame/wall/body, leaf, flame, with deterministic
   position/pose/identity ties. Stair depth uses its middle support; its raster
   anchor uses the lower support contact. No lifted-screen-Y or globally
   highest-first ordering. This explicitly amends the old global leaf-last
   ordering: verify the old door in all four views, never approve only tests.
   Raised foreground terrain must cover a lower rear object, while a lower
   foreground object covers raised rear terrain. If those concrete cases
   fail, stop this ordering candidate rather than add an occlusion framework.
6. Keep mouse picking on real support planes/UUIDs. Expose surface kind/axis
   beside the existing XY/steps/feet diagnostics. No picking decorative beds.
   No live engine registry reads; no changes to capture/reduce/settle queues.

## Validation before handoff

- Add feature tests red first: actual startup snapshot has the finite terrain
  and stair values; public walking climbs/descends the run while ordinary
  cliff crossings fail; no state mutation on rejected movement.
- Real frames at four cameras select the proper straight/corner/flight
  family; entry/mid/upper contacts reproject exactly. Frame evidence preserves
  source support UUIDs/heights and distinguishes bed from support/tread.
- Pixel proof for height/object overlap in both directions; stair pixels and
  landings inspected at native scale. No black openings to framebuffer behind
  a solid ground bed. Keep the existing wall/door/light regression tests.
- Height-aware picking chooses real supports, never a bed at the same XY.
- Complete tests/game, affected battlefield/geometry tests, compile and
  diff-check. Record timings. Use existing venv, no path hacks or dependencies.
- Warmed 64-by-64 draw/rotation/zoom: reuse the current benchmark protocol,
  finite existing SurfaceCache only; no new cache/index, no per-sprite world
  scan. Bounded cardinal lookup and at most this small assembly's extra draws.
- Correctness/visual, anti-slop, anti-OOP/ECS plan and candidate review.
  Captures must show the same world focus and label every camera viewpoint.

## Authorized files

Existing `game/app.py`, `game/projection.py`, `game/assets.py`, the two existing
game JSON files, 12 specified PNG copies, relevant tests/game and battlefield
tests, the visual battlefield builder in `dnd/scenarios/battlefield_catalog.py`,
and this plan. No core mechanics, event types, server, SDK, MapEditor edits,
new asset-import tool, source solver, shadows, masks or sprite slicing.

Reviewers must judge the ground-bed distinction, tactical contact conversion,
support/axis preservation, ordering witnesses and bounded work. Any mismatch
requiring new engine topology returns for a user decision.

## Implementation and verification record

Implemented the single terrace and flight described above. Copied exactly the
12 selected rasters. The scene still has 4,096 independent Tile supports;
the decorative beds add no state or pick candidates. Engine creation emits
the actual height/kind/axis in its existing detached world snapshot. No core
mechanic, event, server, SDK or MapEditor source changed in this slice.

The complete stair raster keeps three support identities and their separate
disclosure/light facts. Client JSON records rise, support offsets, corner
normals, poses and native contacts. Composition roles remain separate from
height; source Ground 2/Ground 3 sorting orders are not engine elevations.
Current hover diagnostics include surface kind and slope axis.

Validation completed so far:

- New elevation/frame module: 13 passed in 5.48s. This includes all four PNG
  contact-to-destination mappings, mixed support knowledge, square corners,
  two-way opaque-pixel floor/wall overlap, and malformed/unsupported flights.
- Actual darkvision-equipped walker climbs, takes a same-height sidestep,
  attempts the forbidden ordinary cliff crossing without changing position
  or spending movement, then descends. No injected paths or lighting changes
  are used for the successful movement; the forbidden command supplies its
  explicit direct path.
- The six-support continuous-slope case already fails at the public frame
  boundary. Added a regression without another validator or segmentation
  layer merely to change a private helper.
- Four-camera production images inspected by coordinator and correctness
  reviewer: coherent terrace contacts, convex corners and rear occlusion.
  Door open/closed comparison found no new visual blocker. Physical ordering
  hides small leaf-edge slivers behind foreground wall bases; it does not
  establish that the previously disputed doorway join is fully resolved.
- Compileall and tracked diff-check passed (existing CRLF notices only).
- Broader regression run: 312 passed, 3 unrelated failures in 149.09s.
  `tests/engine/test_manual_11_grid_tiles_terrain_movement.py::test_paths_price_destination_tiles_and_directional_borders`
  omits the required `DirectionalWall.item_id`. The two architecture failures,
  `test_event_server_import_does_not_load_client_facing_ai_package` and
  `test_world_contracts_are_a_cold_transport_leaf`, reference the retired
  `dnd.core.senses` from `server/world_contracts.py:17`. The missing required
  constructor argument and server import also exist in HEAD. These paths
  were not repaired or brought into this feature's scope.
- A separate game + world-initialization + world-modification run produced
  287 passes and one elapsed-time failure in 123.33s: the successful launcher
  subprocess took 8.348s against the existing 8s whole-process limit. That run
  briefly overlapped a dependency scan; contention is plausible, not proven
  as the sole cause. The identical launcher test passed alone afterward
  (pytest total 8.63s; subprocess below 8s), and passed in the earlier broader
  run. No timeout or expectation was relaxed. Do not describe the last
  monolithic run as entirely green or startup timing as stable.
- Five direct dependency/import-DAG checks passed in 6.04s: no local/dynamic
  project imports, no active local imports or TYPE_CHECKING workarounds,
  acyclic import graph, and respected dependency direction.

The exact mouse-enabled actual-interaction protocol in
`DND_PYGAME_V0_ACTUAL_INTERACTION_PERFORMANCE_AMENDMENT_2026-09-03.md`
was run independently of heavy tests: 60 warm-up plus 300 measured frames,
incremental panning, quarter-turns, 4,096-support picking, 1280x720.

| Grid | Zoom | Median ms | Maximum ms |
| --- | --- | --- | --- |
| Off | 0.15 | 16.485 | 148.043 |
| Off | 0.50 | 13.693 | 138.915 |
| On | 0.15 | 23.509 | 153.669 |
| On | 0.50 | 16.999 | 137.058 |

Both required grid-off medians meet 16.67 ms; full-map headroom is narrow.
The maximum-frame spikes and grid-on costs remain reported limitations, not
hidden by the median. Earlier mouse-disabled capture timings were diagnostics,
not acceptance evidence.

Correctness, anti-slop and anti-OOP/ECS reviewers approved this bounded
implementation. Final validation limitations were disclosed to reviewers.
No general 3D optical blocking,
arbitrary cliff/stair topology, runtime height editing or universal painter
ordering is claimed.

Production captures:

- [Terrace, four cameras](/mnt/c/Users/tommaso/.codex/visualizations/2026/08/14/01a00009-b71d-72e3-9fa6-9520e110433c/cliff-stairs-four-cameras-2026-09-03.png)
- [Open door regression](/mnt/c/Users/tommaso/.codex/visualizations/2026/08/14/01a00009-b71d-72e3-9fa6-9520e110433c/cliff-stairs-door-open-regression-2026-09-03.png)
- [Closed door regression](/mnt/c/Users/tommaso/.codex/visualizations/2026/08/14/01a00009-b71d-72e3-9fa6-9520e110433c/cliff-stairs-door-closed-regression-2026-09-03.png)

## Requested spacing and material follow-up — 2026-09-04

Show the four unmodified G17 images independently of the map. E/S contain
full treads; N/W are thin rear profiles in the source itself. Label source
pose separately from camera: this north-downhill flight uses S/W/N/E in
camera q0/q1/q2/q3. Do not alter sprites or force rear treads over the plateau.

Translate only the terrace and its three supports twelve cells toward -X:
plateau x14..18/y18..22, flight (16,24,h0)/(16,23,h1)/(16,22,h2).
House, pond, light, door, camera controls, heights and traversal stay unchanged.
Use the already-bound WOOD floor on the 24 upper non-stair supports; the
three stair supports retain EARTH, including the small upper landing. Ground
below remains EARTH. The selected rocky cliff profile explicitly names EARTH
as its decorative bed material; it must not clone the new upper wood surface
onto the lower datum. This is client asset composition, not another Tile.

Scope: existing battlefield builder, cliff binding JSON and its validation,
one bed-asset selection in draw_frame, affected tests, this note and diagnostic
images. No new assets, types, lighting treatments, events, systems or sorting
changes. Confirm translated supports, 24 wooden upper tiles, earth beds,
separation from walls, unchanged ascent/descent and four real camera frames.
Obtain anti-slop and anti-OOP review before applying the change.

### Same-turn clarification: tread-only sprite needs flanking mass

The user identified the empty sides beneath the G17 sheet. Source comparison
confirms G16 adds edge trim, not a solid underside. G15 has rock-face mass but
no verified attachment to this flight; do not introduce it by guessed pivots.
The reconstructed original scene around G16/G17 at imported (-6,-16)/(-6,-15)
instead demonstrates stairs recessed between full-height cliff banks.

Superseding only the footprint/count above: use plateau x14..18/y18..24,
with the same (16,24,h0)/(16,23,h1)/(16,22,h2) staircase cut into its near edge.
This produces 33 height-2 supports: 32 WOOD ordinary supports and one EARTH
upper stair support. Middle/lower remain EARTH. The two flanking banks are
real height-2 terrain, not new wall entities or visual-only fake collision.

For the two bank faces adjacent to the h1 middle tread, render the existing
two-step cliff face from the flight's known h0 datum to the adjacent bank's
h2 surface. Keep both the h1 neighboring support and h0 datum identity in
cliff evidence. This is the one allowed partial-tread intersection; arbitrary
one-step cliff drops still reject. Reuse the existing call-local middle-to-
lower map with full detached Tile values, instead of inventing a new index.
The upper exit remains open. Same-axis movement is unchanged; side bank
crossings remain forbidden by existing height/kind rules.

Use unchanged G12/G13 rasters, depth rules and support coordinates. Validate
native-scale four-camera frames: tread meets the bank sides, rear profiles
are naturally occluded, no house overlap, upper wood/lower earth distinguish
the planes. Add assertions for both flanking supports, their datum evidence,
and rejected sideways movement. No new art, masks, polygon fill, lighting,
events, mechanical walls, or backend systems.

### Height-hover clarification and implemented result — 2026-09-04

The recessed-bank amendment was approved by both anti-slop and anti-OOP/ECS
reviewers before production edits. The world now has the footprint and
materials above, 21 cliff-owning Tiles (19 outer-rim owners and two inner bank
faces), including six convex corner placements. The unchanged G17 sheet is
partly hidden by the front bank in q0/q3 and mostly hidden by the terrace in
q1/q2; it has not been artificially made visible through terrain.

The user's subsequent height-hover question was checked against the existing
projection and picking code. XY coordinates remain engine coordinates;
height is the Tile's support elevation in five-foot steps. Existing movement
rules test both supports, their heights and stair axes before accepting an XY
neighbor. A screen offset at height does not create a new engine adjacency.

The existing picker inverses each actual elevation plane and chooses the
foremost matching support. Its algorithm was not changed. The HUD now puts
XY, elevation steps and feet before the UUID, so the important information is
not lost off-screen. A full 4,096-support test checks the raised floor in all
four camera views with pan and zoom. The debug grid remains an X-ray overlay
drawn after geometry: lower outlines may show through cliffs/walls. This is
not an occlusion-aware grid or a pixel-accurate cliff-face picker, and each XY
currently has one terrain support rather than multiple stacked walkable
floors. No broader topology or picking redesign was included.

Before implementation, the new placement and four full-map hover cases failed
against the old footprint (5 failures). After implementation, the complete
elevation-rendering and world-initialization modules passed: 39 tests in
15.45s. Actual native-scale grid-on and grid-off captures were inspected in
all four views. Both reviewers approved the scoped implementation and
explicitly retained the grid/picking limitations above.

- [Original four G17 poses](/mnt/c/Users/tommaso/.codex/visualizations/2026/08/14/01a00009-b71d-72e3-9fa6-9520e110433c/stair-g17-original-four-poses-2026-09-04.png)
- [Recessed stairs, four cameras](/mnt/c/Users/tommaso/.codex/visualizations/2026/08/14/01a00009-b71d-72e3-9fa6-9520e110433c/recessed-stairs-four-cameras-grid0-2026-09-04.png)
- [Actual height-aware hover and X-ray grid](/mnt/c/Users/tommaso/.codex/visualizations/2026/08/14/01a00009-b71d-72e3-9fa6-9520e110433c/recessed-stairs-four-cameras-grid1-2026-09-04.png)

Final functional validation: `tests/game` plus
`tests/engine/test_world_entity_initialization.py`: **240 passed in 124.24s**.
Five direct dependency/import-DAG checks: **5 passed in 6.03s**.
Compileall passed; tracked diff-check passed with existing CRLF notices.

The same 60-warm/300-measured mouse-enabled interaction protocol was rerun.
Grid-off median/max: zoom 0.15 **18.597/160.264ms**, zoom 0.5
**13.825/133.737ms**. The full-map median does not meet the 16.67ms gate in
this run. A separate pre-existing interactive `python -m game` process was
running at about one CPU core throughout; it was left untouched. This is
observed contention, not proof of the cause or an excuse to mark the timing
gate passed. Functional/visual approval must not be read as fresh performance
certification. No unrelated optimization or timeout relaxation was attempted.
