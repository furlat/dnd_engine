# Presentation foundation — ECS implementation review

2026-10-05. Independent current-source review of the implementation checkpoint. Scope: StateCommitEvidence instrumentation, trace expansion, AreaSolid move, stationary/spatial-response/mechanism draw extraction, construction passive data/duration/limitation move. Earlier condition/material corrections in the working tree were not re-reviewed here.

## Disposition

**Approve behavior-preserving extraction, commit instrumentation and the checked headless import boundary.** No gameplay, entity behavior, duplicate reducer or second lifetime store was introduced in the inspected changes. This is not approval of the entire presentation migration.

## Concrete checks

- Compared ASTs with HEAD for `AreaSolid`, `ConstructionMediaLifetime`, `construction_duration`, `construction_media_limitation`, `stationary_media_draw_commands`, `spatial_response_draw_commands`, `_rotated`, and `mechanism_projectile_draw_command`. All eight definitions match exactly after relocation (ignoring source locations). Thus the inspected numerical/rendering functions have no algorithm or parameter changes.
- Built the explicit `from game...` dependency graph over current top-level game modules and found no cycles. This bounded AST check does not claim to prove dynamic or external-package imports.
- Consumers now import raster functions from adapter modules; pure cue/binding owners retain their original types/functions. No late imports or reflection escape hatch added.
- `StateCommitEvidence` is frozen/slotted passive data on BoundChoreography. It records the exact already-selected nodes/observations/world updates at the existing `reduce_nodes` boundary. Sorting, reducer arguments, state times and completion updates are unchanged. The reducer still owns state; instrumentation does not reconstruct it.
- Expanded trace records use bound values directly, with `trace_version=2`; StationaryMediaCue excludes its AnimationData reference. New evidence is observer-projected PlayerNode data, not private engine entities.

## Required correction before claiming headless completion

A fresh Python process installed a meta-path finder rejecting every `pygame` import, then imported `game.choreography`. It failed at:

`game.choreography → game.wall_media.wall_media_limitation → game.draw_commands → pygame`.

Move the pure wall limitation predicate to a suitable existing nonraster owner and update binder/draw consumers, then rerun the same probe. Do not use dummy SDL as evidence of this boundary.

An additional stricter probe rejecting both pygame and NumPy first stopped at `directed_contacts → numpy`. Numerical geometry may legitimately use NumPy; the stated headless requirement is no Pygame/texture/display initialization, not no numerical dependency. Do not claim the stronger property without separate work.

## Follow-through requirements, not checkpoint defects

StateCommitEvidence does not embed version indices or full world/observation payloads. Those are available from the retained public sequence and should be resolved there; this record is local instrumentation, not a complete portable protocol. Do not let its convenience become a parallel state archive. Lifetime clocks and motion-specific provenance remain separate coverage work. Expanded historical trace format is not proof of runtime timing or current pixels.

No production edits or test-suite runs by this reviewer. Checks were source/AST equivalence and fresh-process import probes.

## Follow-up: headless blocker cleared

The parent moved the bank selector and `wall_media_limitation` into `game/wall_profile.py`. Both definitions compare AST-identical to HEAD after normalizing the selector rename `_selected_bank` → `select_wall_bank`. A new isolated process with all Pygame imports rejected successfully imported choreography, combat, construction_transitions and wall_profile. The concrete blocker above is resolved. Numerical NumPy use remains permitted. This confirms import independence, not a complete runtime/text renderer test.

## Follow-up: retained lifetimes and trace imports

Reviewed the next extraction checkpoint. `scene_actors` and `available_clips` moved from raster scene.py into scene_actors.py; SceneActor consumers now import the existing passive body_pose_types owner. Concentration drawing moved into concentration_draw.py while concentration registration retains its existing ownership and clocks. Frame/draw diagnostics moved from the shared trace module into frame_trace.py. All five moved functions compare AST-identical against HEAD.

Executed the expanded headless test's program in a new interpreter: choreography, catalog loading, public sequence decoder, group/motion trace and all six retained registration families imported with every Pygame import prohibited; the real catalog loaded successfully. Explicit game and animation-review module import graph remained acyclic. Approved this extraction checkpoint. No runtime timing modification or fresh visual acceptance is implied.
