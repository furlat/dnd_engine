# Wall breakability completion — October 8

The human requested completion of ordinary wall breakability. This is a bounded
wall task, separate from the ongoing client positioning repair.

- **Behavior:** ordinary solid walls can be discovered and attacked from either
  incident side, lose health, and stop blocking when destroyed. Existing window
  walls retain their independent inserts and supported-item destruction cascade.
- **Boundary:** direct item authoring, native actions/spatial state, serialized
  player events, and the authored environment export for Pixi. Pygame is retired;
  its renderer is not this task's destination.
- **Input:** admitted ordinary wall IDs, committed owner/edge/base placement,
  available attack actions, and recorded destruction events.
- **Output:** one destruction per UUID, empty boundary channels and cleared bands
  at the same owner/base, supported-item cascade once, and source-authored finite
  debris. A surviving corner constituent remains standing as a straight wall.

## Bounded implementation

1. Compose existing Health and ItemDestructionProfile on DirectionalWall and make
   its structural queries respect the destroyed profile. Terrain cliff faces
   remain explicit nonbreakable terrain providers.
2. Admit the seven already installed solid siblings through direct item builders.
   Reuse stone 27 HP / wood 18 HP and existing material armor classes; do not
   invent material resistance or a new wall entity/lifecycle.
3. Reuse original Unity debris, with measured source pivots, 12 FPS and explicit
   source wall-to-effect assignments. Preserve the existing intact wall/corner
   selectors. Remove the intact wall at impact and clear transient debris at
   its authored endpoint; do not hold its final smoke frame as permanent rubble.
4. Verify actual attack discovery, damage/clearance, elevation, independent
   corner pieces, attachment cascade and cold serialized replay. Preserve the
   four source registrations for Pixi. Reuse approved window/door media without
   rebuilding them. Browser acceptance must use the active client.

Anti-slop reviewer: wall_break_source_review, checking preserved media and Unity
source provenance. Anti-OOP reviewer: wall_break_ecs_review, checking composition,
native lifecycle ownership and minimal presentation changes. Review findings are
evidence, not a substitute for native and presentation validation.

## Status

Native mechanics and authored media are delivered. Pixi consumer integration and
browser acceptance remain outstanding: `/home/tommaso/Dev/NDClient` currently
contains only `node_modules`; its source, tools and public directories were
externally removed during this work. They were not restored. Read the explicit
[consumer handoff](WALL_BREAKABILITY_PIXI_HANDOFF_2026-10-08.md).

The human corrected the destination during continuation: **Pygame is off**.
Investigation there stopped, this task's `game/app.py` edits were removed, and the
new wall replay tests now verify native/public values and authored clocks without
opening or rendering a Pygame scene. Historical raster checks are not Pixi
acceptance evidence.

Coverage: existing stone/wood `environment.directional_wall`, their independent
corner constituents, and the seven installed A1/C1/D1/D8/F1/F8/G1 solid siblings.
The ten already admitted fantasy window families retain their independent insert
targets, traversal contracts and parent destruction cascade. Cliffs remain terrain.
No wall, window or door artwork was regenerated.

Four existing source debris banks retain 64 exact RGBA frames, source pivots,
12 FPS and 1300 ms finite cleanup. Source literal selections, including masonry
F1/F8's Wood Small debris, are recorded in
[SOURCE_REUSE](audits/wall-breakability-20261008/SOURCE_REUSE.md).

Preserved atlas payloads, checksums and nine paired-observer native experiments:
`/home/tommaso/Dev/neurodragon_art/sources/solid-wall-debris-20261008/`.
Private production payloads:
`/home/tommaso/Dev/neurodragon_art-production/game/assets/environment/wall_debris/`.
All 11,180 prior production manifest entries remain unchanged. All 47 existing
window banks and 19 window prop registrations match HEAD.

The [ECS review](audits/wall-breakability-20261008/ECS_REVIEW.md) records 16 passing
privacy/contact tests and verified wall/door causal timing. A separate existing
trap condition-removal ancestry defect reproduces with the previous projector;
its pinned inputs are preserved under `native-diagnostics/`. No renderer heuristic
or unrelated trap repair was added.

Final active-scope check after removing the retired-renderer work: **28 passed
in 123.89 s**, using
`uv run --no-sync python -m pytest -q tests/engine/test_solid_walls.py tests/game/test_solid_wall_destruction.py --tb=short`.
The second module tests replay/data contracts without a raster fixture. Earlier
canonical presentation/schema export checks also passed (2 tests); the browser
must regenerate its authored types from that existing boundary when available.
The durable recording receipt pins all 45 files for the 18 observer views.
