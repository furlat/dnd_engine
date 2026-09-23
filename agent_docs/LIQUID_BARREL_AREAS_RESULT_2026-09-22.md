# Surrounding liquid areas — gameplay result and visual work still required

**Historical checkpoint:** the subsequent [liquid-media result](LIQUID_MEDIA_INTEGRATION_RESULT_2026-09-22.md)
completes the approved surrounding-pool and discharge artwork. Pending-media
statements below describe this earlier native-area checkpoint.

The user corrected all six barrels to spill over surrounding ground and then
rejected the static square/stamped appearance. The native area correction is
implemented. **The requested rounded material tiles and spilling animation are
not yet integrated or approved.** Follow the
[reviewed revised plan](LIQUID_BARREL_AREAS_2026-09-22.md) for that visual unit.

## Gameplay delivered

All six authored barrels share a passive one-cell radius, reaching up to 3×3
cells through connected ground at the same elevation. Existing movement and
propagation boundaries constrain the footprint; closed doors, walls, solid
props, missing supports and elevation changes block it. Creatures do not shrink
the spill. An explicit radius zero remains available for small authored contents
and existing point-isolation tests.

Destruction still keeps the same item identity and causal lineage. Oil, Water
and Grease retain one existing spatial owner; blood, poison and dread blood use
the existing tile-owned residues. Cells whose existing ground owner would reject
activation remain unchanged. Fire destruction ignites the actually admitted oil
footprint; partial subsequent ignition/dousing keeps its established semantics.

Water and Grease retain appearance effects on grounded occupants. Poison/dread
deposition retains its existing entry-only behavior; no fabricated movement or
splash damage was added. Jumping beyond the whole area avoids ground contact;
landing in an outer cell contacts the material.

Wider dread pools exposed repeated entry saves and reversing retreats between
adjacent residue tiles. Internal movement now retains the original entry result
and fear direction. A deep landing/teleport makes one automatic paid retreat;
fear remains while still inside, and further ordinary paid outward steps clear
it on exit. Exhaustion retains fear. Removal of the old entry tile does not clear
fear on another dread tile; removal of the currently contacted material does.
This uses the existing condition and committed spatial events, without a new
pool registry or automatic multi-step evacuation.

## Replay and visual status

The catalog now defines fourteen real experiments, each with traveler/witness
perspectives and four cameras: all six break/outer-contact stories, failed saves,
whole-area jump/landing, closed/open door controls and a deep dread landing.
Twenty public replay tests cover these histories plus late initialization, after
native runtime teardown. Observers retain their own visible subsets; a witness
behind a wall is not given the traveler's full material observations.

New videos have **not** been rendered for the revised tile-art direction.
The historical `20260921T231101Z-2f7c49` gallery shows the superseded one-cell
result. The current renderer can draw the expanded received cells with the prior
static material sampler, but that picture is unfinished and not approved.

A repeating procedural field was explored, then withdrawn following the user's
tile-map correction. Its production changes were selectively restored, keeping
earlier material support and native nine-cell coverage. It is not another
retained rendering path. Diagnostics remain only under `.runtime`.

The later [topology handoff](</home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/material-pools/HANDOFF.md>)
records the user's reassignment of both persistent materials and animations to
Godot task `01a0b6af-5fa9-7ec0-9915-0ecee0a6baec`. Environment task
`01a0b501-8a27-7413-ba24-4a36e5b140d2` paused overlapping authoring. The request
now includes all six materials, with Grease reusing its accepted spell shader.
The static research PNGs are provisional and were not installed.

Godot exports must share palette, world texel density, final coverage and loop
phase across discharge, settling and persistent material tiles. Rounded edges
occupy real affected cells; artwork never adds gameplay reach. The topology study
still looks like a rounded rectangle, so the circular-outline request remains
open. Persistent ground-fire artwork is a separate pending request.

## Verification

WSL uv environment: `/home/tommaso/.cache/dnd-engine/venv`.
Source: `/mnt/c/users/tommaso/documents/dev/dnd_engine`.

- Full `tests/engine` plus maintained direct-item registry tests: **1,459 passed**
  in 159.52 seconds (`.runtime/liquid-barrels-20260922/area-full-engine.log`).
- Updated barrel public replay: **20 passed** in 19.45 seconds
  (`area-replay-tests.log` in that directory).
- Existing dread/body-residue/prop-destruction replay: **52 passed** in 35.90
  seconds (`area-neighbor-replay.log`).
- Restored liquid-media and related presentation selection: **68 passed** in
  34.94 seconds (`.runtime/liquid-area-20260922/media-restored.log`).
- Native/game/review-tool Pyright: **zero errors/warnings**; restored media files
  separately type-checked clean. Logs: `area-typing.log` and
  `.runtime/liquid-area-20260922/media-types-restored.log`.
- Existing shaped injury output: **120 RGBA comparisons identical**, without a
  persistent visual-testing framework or hashes (`pixel-preservation-restored.log`).

Native anti-slop, independent ECS and presentation reviews accepted the scoped
area implementation and revised tile-art plan. Detailed review records are in
`.runtime/liquid-barrel-areas-20260922/` and
`.runtime/liquid-area-20260922/media-result.md`. Passing these checks does not
approve the unfinished appearance. No commit was made.
