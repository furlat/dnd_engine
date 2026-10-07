# Playtest recovery implementation evidence

Scope: [approved plan](../PLAYER_PLAYTEST_RECOVERY_PLAN_2026-10-06.md), including all P01–P29, P30 potion crash, P31 incapacitated turn boundary and earlier UI requirements. Implementation resumed after the human's “let's go save this.” This is an ongoing receipt, not acceptance of the whole app.

## Step 0: native and startup costs

Frozen starting source: commit `bcea72668fd` plus `.runtime/playtest-recovery-20261006/baseline/source.diff` and `source.sha256`. Linux Python 3.13.12 from `/home/tommaso/.cache/dnd-engine/venv`; Windows Python 3.13.12 from `.runtime/windows/venv`. Diagnostics and profiles stay outside Git. Required event retention and capture/projection remained active. No video export was enabled. cProfile results locate work; separately recorded unprofiled wall times measure its cost.

These are bounded diagnostic samples, not p95/p99 acceptance runs or real-display FPS measurements:

| Stage | WSL | Native Windows | Interpretation |
| --- | --- | --- | --- |
| Native/capture module imports | 4,541 ms | 2,929 ms | Mounted-drive/import overhead contributes, but isn't the whole problem. |
| Small four-creature session construction | 189 ms | 212 ms | Content bootstrap separately takes about 14–16 ms. |
| Controller advancement, 18 calls, maximum | 330 ms | 321 ms | Native decision/execution can block many SDL frames on either OS. |
| Two player attacks, maximum | 164 ms | 184 ms | Capture and rendering are additional costs. |
| Scorching Ray, one command | 31 ms | 35 ms | Does not justify declaring all spell operations cheap. |
| Unchanged discovery, three calls, median | 25 ms | 28 ms | Session currently recomputes even for identical requests. Live caller frequency must be measured separately. |
| Per-root/per-observer capture, maximum | 9.6 ms | 11 ms | Current caller multiplies history traversal; planned single-audience batch remains necessary. |

The crypt sample separates imports (4,597 ms), session construction (434 ms), ordinary short moves (about 14 ms) and fresh discovery (26 ms median). A later dedicated Fireball run after the tile-refresh change takes 143 ms for its one command. These are small fixed scenes, not evidence for large encounters.

Historical comparison uses isolated extracted source `946fb23fe78` with its own `content_data` and `content_packs`, current interpreter/dependencies, the same native common script, default skirmish and seed 713. Its session API lacks preview, so that common script omits preview in both revisions. Current/historical controller totals are 716/730 ms; attack totals 213/223 ms. This comparison does **not** establish a broad engine slowdown since that revision. UUIDs are not fixed by `random.seed`; final paired comparisons must retain normalized selected commands, loadouts/positions and results, not assume equal stage counts prove equivalent outcomes.

### Ranked measured work and repair owners

1. **Imports and metadata startup.** The existing launcher statically imports native session and rendering before opening a window. Animation metadata separately takes 3.38 s under cProfile: 1.99 s JSON validation, 0.91 s reads, with overlapping nested timings. There are 222 text reads; rig identity validation reparses files already loaded. Keep validation and the complete supported content. Remove repeated reads inside the existing loader; separate worker bootstrap and scene preparation under plan steps 2–3. No late-import trick or new persistent cache format.
2. **Tile after-value publication recomputes sight.** Nineteen inert tile publications consume 535 ms inclusive in the profiled skirmish. Accumulating residue uses this path. `SpatialSensesSystem` now refreshes hazards while retaining resolved contacts only for an explicit non-FOV tile event, an already-published observer, matching occupancy and valid optical/light/propagation/position/capability revisions. Native tile events and their recorded world after-values remain intact. The two sampled attacks total 223→139 ms; this is preliminary, not a universal speedup. Controller peak and discovery did not improve.
3. **Discovery and capture.** Retain the reviewed single native owner, revision-driven discovery, existing capture batching and party audience. Do not add caches before establishing their invalidation or drop required events. Controller lookahead and serialized payload costs still need actual-loop measurement.
4. **Drawing.** Earlier five-draw profile finds 861 alpha-array extractions, with 78 ms copying, 54 ms cutaway and 23 ms selection composition inclusive. This remains a separate measured problem; neither the native change nor switching OS repairs it.

### Native checks and findings

- 74 sensory/replay cases passed after the tile-refresh change, including recorded body-residue replay.
- Another run passed 106 cases then exposed an ally traversal endpoint defect: directly submitted `Move` could stop on an ally. This was introduced by the provisional transit permission, not by tile refresh. Do not hide it by changing the fear test.
- Native `Move` now rejects a known occupied destination at declaration without spending movement, and checks actual destination occupancy at step commitment. Ordinary ally transit remains legal. The 12 residue-fear cases then pass. Door/route and broader movement checks are ongoing.
- The test failure's rewritten assertion recursively formats large native graphs; the initial pytest process was stopped. Plain assertion mode produced the actual failing requirement promptly. This is distinct from app performance.

### Independent checkpoint reviews

Anti-slop: source-level approval of the tile-refresh change; no blocking defect. Requested normalized commands/outcomes and repeated paired timings before final speedup claims. Step 0 remains open for complete startup/live-loop and acceptance evidence. Anti-OOP/ECS approved the narrowed inert-tile guard after the elevation/upper-cloud sight case was added. Neither review certifies the whole dirty tree or smooth live play.

## Completion status

All P01–P29 remain tracked in the complaint ledger. No full-app completion claim. Upcoming work includes party audience and remembered navigation, the independent native process, bounded media preparation and drawing caches, and the remaining interaction/rendering regressions. The required suites, actual Windows journey and both final reviews remain outstanding.


## Step 1 in progress: one party audience

Capture now projects one controlled party audience from actual member grants. The live loop retains one latest/history stream across turn handoff, admits each witnessed outcome once, retains both heroes' own equipment, and reuses the operation's already-captured HUD. Public schema 3 has one boundary conversion for singleton schema-2 recordings. No actor is granted another actor's native senses.

Effect observations need independently recorded provenance: owner changes distinguish a moved/changed effect from a mere sight refresh; upper-volume plane groups remain alternative complete witnesses; partial authorized footprints, anchors and construction sections combine. The first review found two faults (concealed-trap nondetection treated as absence, and differing disclosed anchors preventing combination). Both were corrected; subsequent anti-slop and ECS source reviews approved this
bounded audience checkpoint. Jaw callbacks, pressure-release cleanup and anchor
rollback now publish observation revisions at their actual commit points. Concealed custom effects default to requiring actual prior-discovery removal evidence. Apparent effects explicitly publish whether visible empty ground can confirm their absence. Footprint revisions advance at membership commits before dependent publications.

- Party/native trap/cloud/payload batch: 44 passed. Includes two observers with different perception, remembered traps after the discovering hero loses sight, and later authorized removal.
- Party/public projection/held-door/cloud batch: 58 passed. Includes source-once split-room damage and replay after resetting the engine, old singleton packet conversion, independent volume planes, shared light, disjoint wall sections and precise door contact. These runs overlap; do not sum them as unique coverage.
- Earlier actual dummy-SDL encounter checks: 5 passed, with stable viewing audience across both player turns. This is not real-display performance acceptance.
- Door contact is narrowed through the door provider's contact range. Other boundary props retain their existing five-foot contact rule. A memory fixture now places its operator at the actual opposite incident support, rather than the formerly allowed extra tile.
- A broad typing invocation hit a checker recursion failure in the large existing frame-loop function. Correctly configured core typing identified four new set/frozenset argument annotations; these were repaired. Full changed-file typing remains pending.

Native DiscoveryKnowledge routes, the isolated worker and remaining P rows are still open. No smooth-play claim follows from this checkpoint.

## Bounded startup repair

The metadata loader reuses already-validated rig identities during its installed-rig identity check. Unloaded files still receive the existing validation; no content or assets are skipped. This removes the repeated rig-file reads identified in Step 0. It does not resolve all startup costs; measurements and loader checks are pending.


## October 7 — P30: Haste potion crashes after companion sight loss

A regression in the party projection could replace a controlled companion's
recorded position with `None` when potion consumption published inventory state.
Real Fighter/Sorcerer builds plus loss of the other hero's sight reproduce the
same binding failure as the human's trace. Same-room visible contacts can mask it.

The correction folds sensory and spatial facts into projection's remembered
actor state through the existing player reducer. Its spatial commit-order check
is now one shared function used by both projection and replay. An initial review
caught that skipping this check could let an enclosing move overwrite a nested
portal arrival; the shared fold and walk/jump → inventory regressions close it.

- `potion-crash-reproduced.log`: actual missing-contact exception before repair.
- `potion-projection-tests.log`: **37 passed**, including potion consumption,
  separated/lost-sight party, independent replay and nested portal arrivals.
- `potion-live-fixed.log`: actual crypt frame pump, both heroes drink Haste,
  three commands complete, both positions retained, latest/history equal. Uses
  dummy SDL; this proves integration, not real-display frame-rate acceptance.
- Missing actor/support errors name actor, observer, source cursor and contact
  information. They still raise. There is no fallback pose or skipped rendering.
- Intentional unavailable/stale commands use `CommandRejected`. The live loop
  catches only that type and reraises after native mutation; unexpected value
  errors propagate. `command-boundary-tests.log`: **11 passed**.
- Scoped projection/reduction/combat/session/protocol/transport typing: zero errors.
- Independent anti-slop review approved P30 and the narrow fail-fast distinction.
  ECS follow-up also approved P30 and this failure-handling boundary. Their
  requested explicit rejection-type assertions are now in the session tests;
  `potion-final-loop-tests.log` passes all **6** affected session/actual SDL
  encounter-loop checks in 34.66 s. The overlapping batches must not be summed
  as unique suite coverage.

## Step 2 preparation — isolated native owner

The approved process boundary now exists in `runtime_protocol`, `runtime_worker`
and `runtime_connection`, using existing detached discovery and player facts.
The original UI intent records moved into `player_commands` rather than being
copied. One bounded pipe exchange and a bounded stderr buffer serve one request
at a time. A real-process check covers discovery, preview, committed movement,
stale rejection, unchanged resources on rejection and shutdown.

The worker is now connected to the SDL loop. Native session ownership, discovery,
preview and action execution run in that process; the parent pumps SDL while
awaiting replies. One request is in flight, with at most one operation of
lookahead beyond current playback. Historical HUD updates follow their operation
markers rather than immediately showing the worker's future state. Cleanup owns
the display, connection and startup request lifetime. Shutdown acknowledgement
follows native cleanup with bounded grace, termination and kill fallbacks.

The protocol uses passive CharacterBuild and UIContentManifest data. Their
definitions were moved, not duplicated; the native worker no longer imports
Pygame through UI composition. Focused protocol/UI/door checks: 12 passed;
focused import-boundary typing: zero errors. Broader source review and real-display
acceptance remain open. Media preparation is still synchronous and remains a
major unfinished part of this recovery.

## October 7 — measured rendering and P31 checkpoint

The native action-cost filter now reuses one deep-copied template per invocation
instead of copying for every candidate. The same 18-operation crypt diagnostic
retains 207 event cursors: cost-filter time 180.39 → 73.15 ms across 21 calls,
copying 107.87 → 7.61 ms; whole profile 4.405 → 4.238 s. Twenty-five native
cost/discovery checks pass. This is a bounded improvement, not engine acceptance.

Renderer changes reuse existing bounded caches for support/coverage masks and
avoid calculating palette distances for transparent item pixels. All 2,356 real
crypt material samples match the old RGBA exactly. A native Windows 360-frame
pan/rotation diagnostic improved p95 frame time from 25.47 to 17.58 ms and p99
from 32.14 to 20.16 ms. Maximum remains 149.41 ms; first draw 6.337 s and first
camera change about 67 ms. These fail the full performance gates.

Fireball is measured separately: one native operation 207 ms, preparation 482 ms,
but a rendered frame can still cost over 500 ms with profiling enabled. The
hot paths are decoded/expanded XYZ surfaces, physical floor composition, depth
partitioning and large blits. Depth partition now classifies pixels once and
finds band bounds with the existing SciPy dependency; floor composition skips
height lookup only when no disclosed support can clip a sample. Seventy depth
checks and a 120-case exact old/new pixel/selection differential passed. Updated
real-display profiling and broader regressions are in progress; do not interpret
the worker's responsiveness as proof that effects are smooth.

P08 now covers all projectile bindings, not only Fireball and Scorching Ray.
The shared blitter discarded cropped layer offsets before rotation; it now uses
the existing registered-pivot transformation. Produce Flame's travel binding
also disabled residual alignment; it now uses the same isometric alignment
policy. Seventy-four tangent/crop/repacking checks passed. Thirteen travel
bindings were inventoried; actual-frame orientation and release/travel/playback
timing review across cameras and heights remain open. No global speed multiplier
has been applied to hide rendering stalls.

P31: turn-start death saves still execute. If the actor remains incapacitated,
the native boundary completes its turn and reconciles encounter termination
instead of waiting for human input. Natural-20 recovery remains playable, and
conscious actors with depleted ordinary resources retain their free choices.
Equipment commands reject incapacitated actors before any events are emitted.
The completed 112-case encounter/session/XYZ/area/depth regression partition
passes, including the last-party failed-save case. Independent anti-slop review
approved the bounded turn correction. The witness test fixture was independently
shown to have sight after start-turn; it now asserts the intended actual absence
of sight. The raw-fringe area assertion also failed on the pre-change compositor;
it now preserves original unowned art when there is no physical clipping input.

The staged Fireball failure was real: later sibling whole-world snapshots could
publish the same destroyed door's clearance before its authored destruction
moment. Existing dated-node binding now carries that owner's clearance deadline
to later native-order snapshots. Thirteen breach/transfer/area-timing checks
pass, and the ECS reviewer approved the bounded historical-publication repair.

Outstanding acceptance work includes party-explored navigation, media readiness,
first camera/frame startup stalls, complete projectile visual evidence, remaining
complaint regressions, the actual Windows journey, memory endurance and both final
reviews. There is no full-app completion or smooth-play claim.

## October 7 — first-principles rendering and media readiness

The human explicitly stopped the incremental CPU-compositor repair strategy.
The [rendering amendment](../GPU_RENDERER_AND_MEDIA_READINESS_2026-10-07.md)
records primary pygame-ce/ModernGL/PixiJS documentation, measured depth-split
amplification, the complete lazy-resource families, passive boundary/module
design and readiness/picking/transparency gates. It is integrated with the
parent recovery plan; none of P01–P31 was dropped.

Both independent reviewers approve feasibility work only. A private Windows
ModernGL proof uses original Fireball RGBA/XYZ/owner packets with 163 scalar
cuts, preserving normal/add layer order. The shader output differs by no more
than one color byte from the SE CPU reference; ownership is exact. A small
WebGL 2 harness runs the same shared color/XYZ functions and confirms byte-domain
palette matching, unchanged alpha and data-plane decoding. This is not the full
game or proof of all materials, selection and transparent scene composition.

Storage inspection finds about 3.32 GiB of decoded payload for one Fireball
impact's 64 frames across four views. Sequential read/decode takes about 5.32 s.
The existing 640 MiB unpinned projectile cache cannot retain even one complete
camera bank of that impact. Readiness needs a measured scheduling/residency
contract, not merely requesting everything earlier.

Proof dependencies are isolated in ignored `.runtime/gpu-proof-packages`.
Production dependency pins and application renderer selection are unchanged by
this study. The shader proof removes neither artwork nor current CPU features.
