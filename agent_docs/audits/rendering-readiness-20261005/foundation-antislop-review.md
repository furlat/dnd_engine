# Foundation checkpoint — independent anti-slop review

2026-10-05. Read-only review of the implementation checkpoint against base HEAD `092e9daedaa7e0c65a54632b7085ab60ade642ca`. Reviewed current working source; no production edits by this reviewer. Prior condition/material changes in the same working tree are outside this checkpoint.

## Disposition

**APPROVE this bounded foundation checkpoint.** No unnecessary second scheduler, reducer, runtime registry or graphics executor was introduced. This approval is not final acceptance of the full presentation plan, full trace coverage or current pixels.

## Exact checks

- `StateCommitEvidence` is a passive record appended at the existing `reduce_nodes` call. Its nodes are the same sorted nodes passed to reduction; observation/world event IDs come from the exact tuples passed to that same call. It does not independently infer a cause, replay gameplay or reduce state twice. Recorded `at_ms` is local to the owning BoundChoreography, as are its existing state times.
- Existing state reduction arguments and order remain unchanged. The new tuple is attached to the existing bound owner. Keeping immutable PlayerNode references here is appropriate; no deep copy of the encounter or alternate event stream is introduced.
- The new trace fields inspect existing bound families and retain event/owner identities. `trace_version=2` explicitly distinguishes the extended group output. Additional world changes, stationary/contact media, condition responses, turn starts, reaction media, lifecycle and finite-material records are useful evidence rather than new execution objects.
- The lethal-damage test checks a real shared HP boundary for both caster and recipient: the recorded applied packet can have negative intermediate HP while the same boundary's native DYING edge normalizes the visible HP to zero. This is an appropriate external-behavior test of provenance and timing, not an implementation-mirroring assertion.

An AST comparison against HEAD found the following eight moved definitions identical, excluding line locations:

1. `stationary_media_draw_commands` → `stationary_draw.py`.
2. `spatial_response_draw_commands` → `spatial_response_draw.py`.
3. `_rotated` → `mechanism_projectile_draw.py`.
4. `mechanism_projectile_draw_command` → `mechanism_projectile_draw.py`.
5. `ConstructionMediaLifetime` → existing `construction_transitions.py`.
6. `construction_duration` → existing `construction_transitions.py`.
7. `construction_media_limitation` → existing `construction_transitions.py`.
8. `AreaSolid` → existing `animation_types.py`.

The later wall extraction also compares identical after normalizing the intentional `_selected_bank` → `select_wall_bank` rename: bank selection and `wall_media_limitation` remain the same algorithms. The draw module calls the new pure owner. Production callers of all three moved draw functions now use their draw adapters; a repository search found no stale Python import of those draw functions through the old binding modules.

These are dependency-boundary extractions, not new rendering paths. Drawing mathematics, cache behavior, layer ordering, pivots and limits survive unchanged. Existing functional family owners remain explicit.

## Headless boundary

An initial fresh-process import caught the remaining `choreography → wall_media` graphics dependency. The parent then extracted wall profile selection. A second fresh-process import with a meta-path hook **raising on any `pygame` import** successfully imported `game.choreography`. No SDL dummy mode or display initialization was used to bypass the dependency check.

NumPy is still imported through numeric directed-contact computations. That is not a Pygame/display dependency and is not an issue for this bounded headless requirement; numerical portability remains a later contract topic. This receipt does not claim that every application or trace module imports without graphics dependencies. `devtools.animation_review.trace` intentionally references graphical playback records and is not the future headless narrative entry point.

## Remaining implementation obligations, not checkpoint defects

- Movement-only state boundaries still need equivalent exact provenance; this patch annotates the BoundChoreography reduction loop, not every reducer call inside MotionTimeline construction.
- Group `trace_version=2` does not mean every family is fully exported. Motion trace still omits some body/recovery/context and world/residue/contact fields. Retained lifetimes and direct initial/observation state remain separate instrumentation work.
- `state_commits` supplies actual folded evidence, not a solved declarative milestone graph. Do not call its timestamps authored dependencies until producer/dependency annotations exist.
- Observation and world IDs resolve through the retained public input. The review trace alone is not a complete independent playback format or portable client schema.
- Full runtime/render regression and material selection validation remain the parent's verification work. No independent pixel acceptance or full-suite result is claimed here.

The checkpoint is an appropriate first implementation step: it makes existing behavior inspectable and removes graphics import coupling without prematurely changing the presentation model.
