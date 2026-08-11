# User-Reported Gameplay and Product Regression Ledger — 2026-08-10

Status: **RECOVERED AFTER ROLLBACK — EVERY FIX IS UNVERIFIED**

This document restores the gameplay, presentation, product, startup, and test
failures reported by the user or found while investigating those reports. It
is a bug ledger, not an implementation plan and not acceptance evidence.

The repositories were externally rolled back after the attempted stabilization
work. Therefore:

- no earlier `GREEN`, `FIXED`, or `ACCEPT` label transfers to the current tree;
- no earlier implementation hash is assumed to exist now;
- a surviving test, screenshot, JSON artifact, or manifest records evidence,
  but does not prove the current product;
- every row below starts at `UNVERIFIED_AFTER_ROLLBACK` until reproduced or
  disproved against the current exact source and a real mounted product flow;
- production code was not inspected, edited, built, or run while recovering
  this ledger.

## Recovery baseline

| Repository | Observed HEAD | Observed worktree state during recovery |
|---|---:|---|
| NeuroClient | `f403f8b81e34` | clean |
| dnd_engine | `74cc1f9e3d2d` | tracked testing-plan edit plus untracked stabilization documents/evidence; no production-source edit was made by this recovery |

The surviving
`agent_docs/plans/CURRENT_GAMEPLAY_STABILIZATION_MANIFEST_2026-08-10.md`
contains later-cutoff claims and hashes. Those claims are retained as
investigation history only. This ledger deliberately resets them.

## Status vocabulary

- `USER_OBSERVED`: directly reported from real play or a pasted browser error.
- `CAPTURED_ARTIFACT`: surviving machine-readable evidence exists.
- `HISTORICALLY_CONFIRMED_ROOT`: a later investigation identified and tested a
  cause, but the rollback makes the current source status unknown.
- `INDEPENDENT_AUDIT_FINDING`: found by read-only architecture/source audit;
  it was not necessarily observed in the same live session.
- `HISTORICAL_FAILED_CUT`: failure from the abandoned Runtime V2 frontend cut;
  it is a permanent do-not-regress record, not a claim about the restored UI.
- `UNVERIFIED_AFTER_ROLLBACK`: mandatory current status for every row in this
  document.

## Priority index

| ID | Severity | Short name | Evidence class | Current status |
|---|---|---|---|---|
| BUG-001 | P0 | Fatal Fireball sequence stops presenting after the first damage | USER_OBSERVED + CAPTURED_ARTIFACT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-002 | P0 | Encounter-ending death may overtake/hide earlier queued visuals | USER_OBSERVED | UNVERIFIED_AFTER_ROLLBACK |
| BUG-003 | P0 | Fatal spell root/second Fireball cue omitted | CAPTURED_ARTIFACT + HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-004 | P0 | Corpse-memory objective/subjective parity false failure | USER_OBSERVED + HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-005 | P0 | Fire Bolt black screen from unsupported authored atlas | USER_OBSERVED + HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-006 | P0 | Failed required-media presentation does not preserve last committed scene | USER_OBSERVED + INDEPENDENT_AUDIT_FINDING | UNVERIFIED_AFTER_ROLLBACK |
| BUG-007 | P1 | Missing spell FX, damage popup, condition, death, and turn-end feedback | USER_OBSERVED | UNVERIFIED_AFTER_ROLLBACK |
| BUG-008 | P1 | Haste Potion uses generic/non-semantic feedback | USER_OBSERVED + HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-009 | P0 | Multi-tile walking restarts its body cycle at every tile | USER_OBSERVED + HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-010 | P0 | Visible movement patch can arrive without a movement cue | CAPTURED_ARTIFACT + HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-011 | P0 | Movement cue is not sufficient terminal-position authority | HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-012 | P0 | Acid Splash cannot lawfully finish with one of up to two targets | USER_OBSERVED | UNVERIFIED_AFTER_ROLLBACK |
| BUG-013 | P0 | Acid Splash command succeeds or starts but its presentation does not settle | USER_OBSERVED + HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-014 | P1 | Water is rendered as floor | USER_OBSERVED + HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-015 | P1 | Default persisted Sorcerer lacks Invisibility | USER_OBSERVED + HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-016 | P0 | Position-only spatial effects disagree across engine, SDK, and client | INDEPENDENT_AUDIT_FINDING + HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-017 | P0 | Reconciliation diagnostics do not identify the first failed animation node | USER_OBSERVED + INDEPENDENT_AUDIT_FINDING | UNVERIFIED_AFTER_ROLLBACK |
| BUG-018 | P0 | Diagnostic callbacks can influence authoritative presentation admission | INDEPENDENT_AUDIT_FINDING | UNVERIFIED_AFTER_ROLLBACK |
| BUG-019 | P1 | Terminal parity polling races subjective-partition retirement | CAPTURED_ARTIFACT + HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-020 | P0 | Canceled generation can mutate the replacement scene/store | INDEPENDENT_AUDIT_FINDING | UNVERIFIED_AFTER_ROLLBACK |
| BUG-021 | P1 | Non-zero or negative grid origins render inconsistently | INDEPENDENT_AUDIT_FINDING | UNVERIFIED_AFTER_ROLLBACK |
| BUG-022 | P0 | Storage failure before startup try/catch can blank/crash the app | USER_EXPECTATION + INDEPENDENT_AUDIT_FINDING | UNVERIFIED_AFTER_ROLLBACK |
| BUG-023 | P0 | Stale principal/cache state crashes startup instead of auto-cleaning | USER_OBSERVED + CAPTURED_ARTIFACT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-024 | P0 | Deferred bootstrap wire validation can fail on missing `code` | USER_OBSERVED | UNVERIFIED_AFTER_ROLLBACK |
| BUG-025 | P0 | Empty-profile/AI-only player game can be created and replace a live game | USER_OBSERVED + HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-026 | P0 | Multi-target actions rolled damage independently instead of sharing the authored roll | HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-027 | P1 | Connector state is dropped or lacks one neutral presentation path | INDEPENDENT_AUDIT_FINDING | UNVERIFIED_AFTER_ROLLBACK |
| BUG-028 | P1 | Action Studio rejects or fails connector preview | HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-029 | P1 | Cold Rolling readiness fixture does not intercept the real current owner | HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-030 | P1 | Studio presentation smokes navigate to stale tabs | HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-031 | P0 | Async Playwright predicates pass/fail vacuously | HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-032 | P0 | Browser smokes silently depend on an ambient/stale Vite process | HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-033 | P1 | Decorative RAF/timer callbacks outlive transactions and touch destroyed Pixi nodes | HISTORICALLY_CONFIRMED_ROOT | UNVERIFIED_AFTER_ROLLBACK |
| BUG-034 | P1 | Objective Events/Combat Log diagnostic surface may be absent or stale | USER_OBSERVED | UNVERIFIED_AFTER_ROLLBACK |

## Directly reported gameplay failures

### BUG-001 and BUG-002 — fatal Fireball chain stops and encounter death may overtake it

The exact user-observed combat-log order was:

1. Goblin Caster casts Fireball at `(10, 8)`.
2. Draconic Sorcerer saves and takes 16 fire damage.
3. Goblin Caster drinks a Haste Potion and gains Haste.
4. Goblin Caster casts a second Fireball.
5. Draconic Sorcerer fails the save and takes 25 fire damage.
6. Goblin Caster loses Invisibility.
7. Draconic Sorcerer is defeated.
8. Goblin Caster's turn ends.

The client visibly showed only the first take-damage portion. The user did not
see the potion, Haste feedback, second cast, Invisibility removal, second
damage, death animation, or final turn-end pixels. The strongest user
hypothesis was that the single-character encounter-ending death/result path
overtook, canceled, or hid all earlier queued visuals.

That hypothesis must remain separate from the independently observed producer
omission in BUG-003: one sequence can contain both a missing cue and a client
drain/order defect. Final state, combat-log completion, a terminal banner, or
cue counts cannot prove the missing intermediate visuals.

Required reproduction boundary after rollback: the exact ordered sequence
must be captured from real engine/server output and consumed by the production
live presentation root and isolated replay root. At every delivered head, the
journal head/token, mapped semantic intent, transaction/clip terminal,
presentation cursor, state synchronization, and scene semantic must advance in
order. Encounter death/result is allowed only after all prior required visual
transactions have lawfully terminalized.

Surviving evidence:

- `agent_docs/evidence/current_gameplay_stabilization/fireball-haste-fatal-objective-pre-fix.json`
- `agent_docs/evidence/current_gameplay_stabilization/fireball-haste-fatal-subjective-pre-fix.json`
- `agent_docs/evidence/current_gameplay_stabilization/fireball-haste-fatal-combat-log-pre-fix.json`
- the `current-nearest` pair, which intentionally lacks Invisibility removal
  and therefore is not a full positive counterpart.

Nearest old tests and why they escaped:

- `app/scripts/presentation-head-drain-live-smoke.mjs`: synthetic heads, not
  the real long combat sequence;
- `app/scripts/clip-queue-liveness-smoke.mjs`: synthetic stall/timeout, not
  ordered semantic completion across death;
- final-state/cue-count checks could pass while intermediate heads were absent,
  blocked, skipped, or hidden by terminal presentation.

### BUG-003 — fatal spell root/second Fireball cue omitted

The preserved pre-fix objective artifact contains the fatal second Fireball
root, while the paired subjective artifact contains resulting damage, death,
light, turn-end, and encounter-end presentation without the spell cue.

A later investigation attributed this to completion-time disclosure being
re-evaluated after the only observer died. That is a
`HISTORICALLY_CONFIRMED_ROOT`, not proof of the rolled-back source.

Required current oracle: producer-side expected presentation must be compared
against emitted subjective delivery at each lawful privacy boundary. The
ordinary player must never learn hidden objective lineage merely to diagnose a
missing cue.

### BUG-004 — remembered corpse parity false failure

Observed browser fault:

`presentationDiagnostics.ts:669 [presentation-fault] ... kind:
control_plane_failure, message: objective-to-subjective render parity failed`

It occurred after a Fireball killed multiple goblins. The suspected/previously
confirmed mismatch was that the subjective reducer lawfully remembered an
unseen corpse while the parity oracle compared against only the currently
visible objective set. The reducer must not be weakened to make the diagnostic
green.

Nearest old coverage:

- `tests/manual/test_120_subjective_world_projection.py::test_perceived_corpse_persists_privately_until_authoritative_reobservation`
  proved one memory rule in isolation;
- `app/scripts/render-parity-live-smoke.mjs` compared a final snapshot;
- neither proved every multi-target lethal prefix through emitted patches,
  SDK reduction, presentation state, and mounted scene.

### BUG-005 and BUG-006 — Fire Bolt black screen and recovery

The user observed Fire Bolt causing a black screen/reconciliation failure and
suspected the spritesheet route. Later evidence identified an authored atlas
of `9216x2048` against live Chromium WebGL `MAX_TEXTURE_SIZE=8192`.

Two non-substitutable behaviors are required:

- the shipped Fire Bolt visual must use a supported authored asset and visibly
  settle through the real Pixi/WebGL path;
- the preserved oversized fixture must fail before GPU upload, report the
  exact asset/dimensions/device limit, terminalize the failed presentation
  head, and keep the last committed canvas/scene visible.

Dropping optional media, swallowing the GPU fault, rebuilding a blank scene,
or checking only final HP is not a fix.

Nearest old tests:

- `app/scripts/subjective-presentation-semantic-smoke.mjs` checked that Fire
  Bolt maps to projectile/damage semantics;
- `app/scripts/presentation-asset-service-smoke.mjs` used synthetic asset
  behavior;
- icon-atlas validation did not upload the actual spell-FX atlas to the actual
  device.

### BUG-007 and BUG-008 — absent semantic feedback

Reported missing visuals include:

- Fireball spell FX;
- damage popups;
- Drink Haste Potion animation/prop/feedback;
- Haste condition application;
- second spell cast;
- Invisibility removal;
- damage/death animation;
- turn-end visual settlement.

Potion coverage previously accepted a generic `Taunt` body clip plus cue
presence. That is not recognizable Haste Potion feedback. The current product
must prove the authored potion identity, effect/condition feedback, equipment
restoration, and one lawful transaction terminal.

Nearest old tests: `app/scripts/potion-animation-smoke.mjs` and
`app/scripts/condition-presentation-smoke.mjs`.

### BUG-009 — walking loop resets at every tile

The user observed a multi-tile walk repeatedly returning to/restarting the
walking animation at every cell instead of playing one natural continuous body
cycle.

The historically identified cause was one frame-local cue per Step with the
clip returning the actor to Idle after each fragment. A frontend coordinate,
time, or adjacency heuristic is forbidden because it would stitch hidden
movement. Any repair needs an authored privacy-safe continuity/terminal fact;
each spatial head must still commit independently.

Nearest old tests:

- `app/scripts/locomotion-presentation-smoke.mjs`
- `app/scripts/movement-presentation-smoke.mjs`
- `app/scripts/movement-animation-smoke.mjs`

They tested individual family/ordering behavior, not four adjacent real Step
heads with one Walking entry, no intermediate Idle, monotonic animation phase,
and one authored settlement.

### BUG-010 and BUG-011 — movement cue/settlement integrity

A surviving seed-7301 artifact recorded already-visible enemy position upserts
without movement cues, leaving Pixi behind the SDK projection. A later partial
correction established that a movement cue's endpoint still cannot by itself
be treated as terminal position authority when later forced movement,
relocation, death, or state-only supersession changes the frame's final
occupancy.

These are separate from body-cycle continuity:

- every disclosed visible movement needs a lawful privacy-safe visual or an
  explicit state-only presentation disposition;
- the frame needs an authoritative terminal settlement relation;
- the client may not infer paths, hidden gaps, or final position from cue order.

The surviving manifest explicitly left this contract rejected/open. It must
not be silently characterized as fixed after rollback.

### BUG-012 and BUG-013 — Acid Splash targeting and presentation

User-observed behavior:

- Acid Splash asks for two targets even though the spell permits one or two;
- with only one lawful target, the UI will not finish/cast;
- after selection, the cast/presentation can still fail to appear.

Required cases are distinct:

- at least two lawful targets exist, select exactly one, finish by click;
- same world, select exactly one, finish by Enter;
- only one lawful target is discoverable;
- select the full two targets;
- duplicate, stale, enemy-invalid, and canceled allocations remain inert;
- exactly one request reaches mechanics, damage/presentation settles, and
  lawful input returns.

Later investigation found one separate presentation failure where an authored
child clone discarded already-authorized intent/disposition evidence after the
HTTP-200 action. Both input cardinality and post-command presentation must be
rechecked.

Nearest old tests: `app/scripts/targeting-authority-smoke.mjs` and
`app/scripts/action-ui-authority-smoke.mjs`; they used a synthetic generic
multi-target row and did not prove canonical Acid Splash mechanics plus pixels.

### BUG-014 — Water renders as floor

The user saw water cells displayed as ordinary floor. A later source finding
was that an arena authored a tile named Water without the canonical water
factory, so the wire projected `floor.png`.

Required current proof: a canonical authored water tile must project and mount
the semantic `water.png` material, retain the correct walking/swimming costs,
and require no display-name inference in the client.

The old `static-board-sync-smoke.mjs` and `render-parity-live-smoke.mjs` generic
tile fixtures did not prove this.

### BUG-015 — default Sorcerer lacks Invisibility

The user reported that the default Sorcerer no longer had Invisibility, which
also removed the intended live test path. Later source history said
`hero.sorcerer_l5_standard_torch` omitted the spell.

Required current proof: create the canonical default Sorcerer, persist it,
reload it, materialize it, expose exact lawful Invisibility action variants,
cast one through mounted UI, present the condition/actor opacity, and restore
input. A catalog test proving the spell exists is insufficient.

## Cross-stack correctness and recovery failures

### BUG-016 — position-only SpatialEffect contract mismatch

The independent audit found three incompatible rules:

- the Python player contract permitted a position-only spell application for
  a spatial-effect child;
- the TypeScript SDK rejected position-only applications with effects;
- NeuroClient filtered or explicitly rejected position-only applications in
  projectile/missile mapping.

This affects zone-creating spells such as Grease/Fog Cloud. One lawful real
engine output must pass through contract generation, SDK decode/follower,
journal, client mapper, reducer, and scene without inventing an entity target
or AoE. Malformed entity/position combinations remain negative.

### BUG-017 and BUG-018 — reconciliation is opaque and diagnostics are not safely observational

The user explicitly requires the debug surface to say which events failed to
animate and why. The observed generic
`control_plane_failure: objective-to-subjective render parity failed` does not
identify:

- accepted delivery/head/token;
- cue root/parent/disposition;
- authored recipe/profile/asset;
- VisualTransaction and clip lifecycle;
- the first causal failure stage;
- which later work completed, was blocked, or was never materialized.

The audit also found diagnostic recording/listeners running synchronously in
mapping/queue paths, with a diagnostic return value capable of rejecting live
admission. Evidence failures must be observational; real mapper, asset, GPU,
clip, watchdog, scene-barrier, commit, and state-sync failures must retain their
actual product semantics.

The old `subjective-animation-coverage-smoke.mjs` called recorders directly and
asserted aggregate/final JSON. It did not prove an immutable first-cause graph
through the mounted production composition root or equality between exported
JSON and debug UI.

### BUG-019 — terminal parity acquisition retirement race

After a fatal Fireball chain completed, the player partition closed while one
subjective-parity GET was already in flight. It returned typed HTTP 409
`subjective_parity_partition_unavailable`, producing a browser network/console
fault. Canceling after the terminal head cannot erase a response the server
already completed.

The narrow boundary is:

- accepted terminal head fences every new parity request;
- one already-started request must receive an authoritative retained terminal
  result or a typed non-fault result;
- diagnostic acquisition remains observational and cannot mutate terminal
  gameplay authority;
- late callback, no-later-frame, reconnect/reset, identity replacement, and
  hosted worker-lifetime behavior are explicit.

Surviving red artifact named in the manifest:
`/home/tommaso/Dev/NeuroClient/app/test-results/sorcerer-fatal-fireball-red-2026-08-10T02-02-51.391Z.json`.
Its presence after rollback is not assumed.

### BUG-020 — canceled generation writes into replacement state

The audit found that cancellation gated entity lookup/dispatch but passed some
store mutation sinks through raw. In particular, a weapon-switch clip could
write visual state in `finally` after its generation had been canceled and a
replacement replica installed.

Required proof stalls and releases every actual mutation sink—entity pose,
weapon/equipment, condition, terminal, scene child, timer/RAF, store write—after
generation replacement and proves the replacement remains unchanged.

### BUG-021 — non-zero and negative grid origin

The audit found board dimensions derived from bounds while `min_x/min_y` were
discarded for grid/light/camera consumers. Tiles/entities retained real
coordinates, so overlays, lighting, highlights, picking, and camera centering
could disagree outside a zero-based map.

Existing smokes were mostly zero-origin. Required current cases cover positive
offset, nonzero, and negative-inclusive bounds and compare every consumer's
screen coordinate for the same authoritative cells.

### BUG-022 and BUG-023 — storage/principal startup should recover, not crash

The user explicitly requested automatic cleanup instead of a startup crash.
Two captured failures showed directory profile discovery aborting startup:

- `NotFoundError: Requested principal does not exist`;
- generic HTTP 404 from `GameDirectoryClient.requestModel`.

The audit additionally found persistence/storage access occurring before the
main startup `try`, so `Storage.getItem`, `setItem`, or `removeItem` throwing a
`SecurityError` could prevent the app from reaching its recovery UI.

The production pre-parse owner must scope-clean or quarantine stale identity,
presentation, journal, archive, and cache entries, preserve valid profile,
replay, and preferences, then authenticate/rebootstrap. Storage denial/quota
failure must show a truthful recoverable UI and tear down resources. It must
not require manual database deletion.

Captured attachments:

- `/mnt/c/Users/tommaso/.codex/attachments/35cdfe24-488c-4c93-98da-852d50e9f5de/pasted-text.txt`
- `/mnt/c/Users/tommaso/.codex/attachments/af8d681c-4295-4954-8508-a3b614c90263/pasted-text.txt`

### BUG-024 — deferred bootstrap missing required `code`

Observed live failure:

`ContractValidationError $SubjectiveBootstrapDeferred.code missing required field`

This occurred in SDK `bootstrapAttempt` from the canonical game-setup connect
path. Required current proof uses the real backend response and generated SDK
decoder, including the prepared/deferred branch, activation/follow-up, and
playable scene. A hand-authored fixture or relaxed decoder is insufficient.

### BUG-025 — empty-profile and AI-only player game creation

The canonical UI allowed game creation with no created character/playable
owned roster. A direct player-facing start could accept an AI-only recipe and
destructively replace the hot game before rejecting the missing player-product
invariant.

Required current boundary:

- mounted empty profile disables the player-game action and sends zero
  compose/start requests;
- server rejects an explicit forged empty/AI-only player-game request before
  any reset, worker, deployment, directory, membership, or game mutation;
- valid owned Human roster reaches bootstrap, rendered controllable actor, and
  one state-changing command;
- administrative simulation is an explicit authenticated server-owned
  operation, not a browser self-asserted flag.

### BUG-026 — shared multi-target damage roll allocation

A later stabilization run found one Fireball rolling separate totals for three
failed saves instead of sharing the authored execution-scoped damage roll.
This was independently fixed/tested at that later cutoff, but must be
reverified after rollback. The current oracle needs one execution-scoped roll
identity/result shared across target-local save/resistance/HP/log application,
with a fresh identity on the next execution and correct multi-component rules.

## Connector, Studio, and test-infrastructure failures

### BUG-027 and BUG-028 — connector projection/presentation and Studio preview

The earlier engine/client audit recorded:

- `APIGrid.connectors` existed but SDK `renderProjection` dropped them;
- connector geometry/assets lacked one complete neutral client path;
- locomotion presentation did not carry enough typed Swim/Fly/Burrow/connector
  identity, elevation, or connector kind for one authored animation path;
- Action Studio rejected or failed `action.traverse_connector` preview;
- public structural edges lacked a stable identity, leaving reciprocal-edge
  normalization drift possible.

These are adjacent integration defects, not permission to redesign Pixi. The
working recovered renderer remains the owner; connector state must enter only
through the existing SDK presentation-replica projection and one neutral
connector layer with typed interaction, accessibility, ordering, and teardown.
No connector-name switch or hidden path inference is acceptable.

### BUG-029 — cold Rolling readiness fixture is stale/vacuous

The maintained readiness smoke completed the Jump and returned to Idle before
the intended cold texture gate was released. Later investigation found its
fixture did not match the current cue/anchor identity or did not intercept the
actual asset owner. A direct stale fixture must not diagnose production
readiness.

### BUG-030 — Studio navigation smokes target stale tabs

Reaction, movement, and condition browser smokes timed out looking for old
Spell Studio buttons such as `Actions` and `Conditions` without first opening
and asserting the current exact workspace/tab. They failed before exercising
the claimed presentation behavior.

### BUG-031 — async Playwright waits can pass vacuously

Seventeen predicates used `page.waitForFunction(async ...)` in an installed
runtime that treated the Promise object as truthy instead of repolling its
resolved `false`. These tests could declare readiness without the condition
ever becoming true.

Required invariant: polling predicates are synchronous or explicitly polled by
the harness; a static maintained gate rejects Promise-valued
`waitForFunction` predicates.

### BUG-032 — ambient Vite/process dependency

Several browser smokes defaulted to `127.0.0.1:5173` and could test no process,
a stale process, or the wrong source. A green result was not necessarily owned
by the invoking test.

Every maintained browser/product gate must own or explicitly attach to an
identity-verified backend, Vite/preview server, browser profile, and teardown.
Cold/default checks cannot require ambient ports.

### BUG-033 — decorative callback lifetime

A completed Banner/FloatingText transaction could leave RAF/timer work alive;
later replay/state synchronization destroyed its Pixi child and the stale
callback dereferenced it. Every RAF/timer/deferred/decorative callback needs a
transaction/session lease canceled and joined at terminal, failure, reset,
seek, generation replacement, and host destruction.

### BUG-034 — objective Events/Combat Log debug surface

The user specifically asked not to lose the objective Events and Combat Log
debug view. During the failed UI cut, its continued presence and correctness
were uncertain. It is a read-only ADMIN/debug capability and must never feed
player reducer/render/command authority, but its absence or stale navigation is
still a product regression for diagnostics.

## Historical failed Runtime V2 frontend cut — permanent do-not-regress record

These failures motivated the rollback. They are not merged into current
gameplay root-cause claims, but must remain visible so a future integration
does not repeat them.

### HIST-001 — safe catalog role mismatch crashed the action bar

Observed error:

`PlayerRuntimeProtocolError: presentation item... has asset role ITEM; expected CONTENT_PRESENTATION`

The action bar resolved an item presentation reference through a content-only
asset route and crashed repeatedly during rebuild/resize.

### HIST-002 — missing portrait identity crashed startup

Observed error:

`PlayerRuntimeProtocolError: appearance ... has no authored portrait identity`

Initiative-bar construction turned missing optional/authored portrait evidence
into a fatal whole-app startup error.

### HIST-003 — working Pixi product was replaced instead of adapted

Reported regressions included huge object icons, wrong map proportions and
sizes, different board rendering, missing abilities, and loss of the familiar
game setup/interface. The permanent rule is preserve pixels and legitimate
presentation ownership; adapt backend state behind one seam rather than
rebuilding the product.

### HIST-004 — setup/capability deletion before parity

The failed cut removed or bypassed working setup, roster/controller, command,
Studio, and diagnostic capability before the replacement was mounted and
visually proven. No legacy/product owner may be deleted merely because a new
type compiles.

### HIST-005 — catalog/portrait errors were discovered by the user

The maintained checks did not mount the actual production action bar and
initiative bar against the real catalog/appearance data. Acceptance must
include the canonical browser journey, console/network/WebGL capture, and
reviewed screenshots—not just TypeScript or synthetic smokes.

## Recovered evidence and nearest old gates

| Failure | Nearest prior gate | Why it was not sufficient |
|---|---|---|
| Corpse-memory parity | `test_120_subjective_world_projection.py`; `render-parity-live-smoke.mjs` | isolated/final-state, not every lethal prefix |
| Fatal Fireball head liveness | `presentation-head-drain-live-smoke.mjs`; `clip-queue-liveness-smoke.mjs` | synthetic heads, no real long semantic chain |
| Potion/Haste | `potion-animation-smoke.mjs`; `condition-presentation-smoke.mjs` | accepted generic Taunt/cue presence |
| Continuous walk | locomotion/movement presentation smokes | no adjacent real Step heads or body-phase oracle |
| Fire Bolt | subjective-presentation and asset-service smokes | no actual device GPU limit and scene-survival proof |
| Acid Splash | targeting/action authority smokes | generic synthetic row, not canonical spell/mechanics/pixels |
| Water | static-board/render-parity smokes | generic zero-origin tile, no authored water material |
| Invisibility | spell catalog/progression tests | spell existence, not default persisted/materialized build |
| Position-only effect | Python mapper/contract tests and Neuro mapper | contradictory isolated laws, no cross-stack trace |
| Diagnostic non-authority | live/replay head-drain smokes | narrow synthetic observer throws only |
| Canceled generation | runtime-host/lifecycle/queue smokes | did not stall every real mutation sink |
| Grid origin | static-board/depth/anchor smokes | zero-origin fixtures |
| Startup storage | persistence-cut/startup-transport smokes | no storage throw before `init()` |
| Reconciliation | animation-coverage smoke | direct recorder/aggregate counts, no causal product chain |

## Current verification rule

No row may leave `UNVERIFIED_AFTER_ROLLBACK` based on prose, an old hash, or a
focused smoke alone. A row changes status only when the current exact source is
frozen and the row's actual owner plus its real cross-stack/product boundary
are exercised. Where the behavior is visual or interactive, the proof must
include mounted Pixi/DOM semantics, console/network/WebGL evidence, and an
owned-process browser journey. Where privacy or authority is involved, the
negative perspective/identity cases are mandatory.

This ledger is the recovered intake. It does not authorize fixes, a new
testing-surface implementation, renderer redesign, service changes, or source
deletion.
