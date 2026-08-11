# Gameplay Regression Work Packet 013 — State-Only Scene Appearance Settlement

Date: 2026-08-11
Owner: Planner / External Reviewer 1
Implementation owner: Implementation only after public Gate A 4/4 and Coordinator release
Execution owner: Tester only after changed-production static 4/4 and Coordinator release

## 0. Decision and boundary

WP-012 captured and received public 4/4 acceptance for one exact structured
Outcome A receipt. The evidence selects the frontend scene-settlement boundary,
not the backend, equipment mapping, render-parity comparison, diagnostics, or a
fault-recovery policy.

The two faults occur only in the inherited equipment interval. For the same
controlled actor and the same effective-appearance path, Pixi is exactly one
transition behind:

1. equip expects weapon `Melee15` while Pixi still exposes `Melee14`;
2. unequip expects weapon `null` while Pixi still exposes `Melee15`.

Jump and Move checkpoints are clean. Backend parity and the expected subjective
projection are correct. Both failing frames are cue-less state-only frames.
The scene store subscriber synchronously detects the new appearance and calls
`AnimatedEntity.setAppearance`, but that call installs an asynchronous
`_appearanceReady` operation. `applySubjectiveReplicaView` currently records the
new expected render world immediately after the store write, so the existing
microtask parity sample can observe the previous complete Pixi rig before the
new rig finishes settling.

The existing visual-transaction boundary already uses
`assertSceneMatchesPresentedWorld`, which awaits every entity's existing
`waitForPresentationReady()` owner. Cue-less state-only heads do not use that
post-application fence.

This packet makes the smallest owner-correct production change in exactly two
existing internal files:

- `/home/tommaso/Dev/NeuroClient/app/src/engine/stateSync.ts`;
- `/home/tommaso/Dev/NeuroClient/app/src/engine/eventIngestion.ts`.

For one cue-less state-only head only, the state projection is applied while
expected-world publication is explicitly deferred. The existing scene
assertion then waits for and validates the applied Pixi world. Only after that
exact fence succeeds and the head owner is still current is the same projected
world published to the existing parity owner. Visual-transaction, reset,
bootstrap, reconnect, and every other application path keep their present
default behavior.

### 0.1 Human authorization and automatic progression

The human explicitly authorized Option A: an owner-correct production packet
for this presentation-fault family. The accepted WP-012 chronology has now
identified the bounded owner. No additional human product choice is implicated
by this internal ordering correction.

### 0.2 Accepted natural red

WP-012 is the natural runtime red for this packet. It used the exact unchanged
Tester smoke that will be used for green and produced:

- one governed run, exit 1 without timeout;
- exactly two unchanged-console-gate presentation faults;
- exact structured ids correlated to `after_equipment`;
- equip and unequip lag-one appearance mismatches;
- all unrelated inherited assertions completed;
- complete owned teardown.

The accepted JSON line is 163,196 bytes with SHA-256
`669ebe01f8b37df9975a15c8192b66cdd4c9acc13d0e3670fbcd0a85f6dcbed0`.
No additional red execution is authorized or necessary.

### 0.3 Strict claim

Successful Gate B may establish only:

> Cue-less state-only subjective frames do not publish their new expected
> render world or complete their presentation head until the already-applied
> scene has reached the existing presentation-readiness and exact-scene
> assertion boundary. The two WP-012 equip/unequip lag-one frontend parity
> faults no longer occur in the maintained live-subjective smoke.

It does not claim general equipment correctness, every appearance transition,
all state-only semantics, Jump/Move correctness, backend parity correctness,
general render-parity correctness, recovery semantics, or WP-011/BUG-031 Stage
4 closure before a fresh green receipt and final review.

## 1. Frozen authorities

All identities are exact read-only authorities. Any mismatch fails intake
closed and returns to Planner. No automatic refresh is allowed.

### 1.1 Accepted predecessor and evidence identities

| Authority | Lines | SHA-256 |
|---|---:|---|
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_WORK_PACKET_012_FRONTEND_RENDER_PARITY_FAULT_CHRONOLOGY_EVIDENCE_2026-08-11.md` | 446 | `15dd822ba7ca3af2b17c22225ba7a3fe8ce56c65e354f2bda644276e8a1b9e04` |
| `/tmp/neurodragon-wp012-diagnostic-JBdpUA/live-subjective-actions-smoke.stdout` | 5 | `b9cc08ba870e69a1daa5c00906c068417e517a4f96ef4111f72d6ff65852990d` |
| `/tmp/neurodragon-wp012-diagnostic-JBdpUA/live-subjective-actions-smoke.stderr` | 9 | `7ad92c44536dee4e695afb3a50d3856505ecd529396f874d170e45d74f9dc011` |

The evidence files were already accepted at public 4/4. They are frozen
authorities, not mutable packet state. The retained evidence root must not be
modified, cleaned, or reused.

### 1.2 Mutable production owners

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/src/engine/eventIngestion.ts` | 935 | `c05d9b3eb83f907608f41c6ee1df56b3ce08732a9fd1aaca1250850f41b86828` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/stateSync.ts` | 612 | `030308d2e949c9404b61ad9238635cc83311e87c741f5da8432cdcc3d077a969` |

Only these two files may change after Gate A. Their accepted current working-
tree content, not the repository tracked baseline, is the edit baseline.

### 1.3 Frozen scene, parity, and planning owners

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/src/render/sceneRenderer.ts` | 797 | `60adef2ecc5935efaf48890ea8d7df8c374635402cb1b629d2c572e4a48b35fc` |
| `/home/tommaso/Dev/NeuroClient/app/src/render/AnimatedEntity.ts` | 1306 | `9c411a9efbd5f1260c36f968b56ac3ca4e3edab89de6f73b4ffc1bfc331e1756` |
| `/home/tommaso/Dev/NeuroClient/app/src/render/renderParity.ts` | 720 | `6ae2d160a292e30e75a060443feebad0be603dbc93a7b0c8189a022d3e809b58` |
| `/home/tommaso/Dev/NeuroClient/app/src/render/presentationDiagnostics.ts` | 1264 | `4271e3b7711b8964212f9d0994877768c386c1ac359b476f5c3b94d3d8233f69` |
| `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts` | 3259 | `87025f16de08abb58ddab3fa65d27ab9562bf7bf0e65dc18d7a6e68598994278` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/eventStream.ts` | 974 | `912ef41889c5a1a753d8969037550e3fabc6ecbd126e1d417e4cced6290fd522` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/store.ts` | 431 | `b0c428f266cf3c23608143e3ee73fc048f82bfb0afb5ffee3e317b1aff859537` |

These files establish the existing readiness, assertion, mapping, parity,
diagnostic, and subscription behavior. They remain byte-frozen.

### 1.4 Frozen Tester and runtime authorities

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/scripts/live-subjective-actions-smoke.mjs` | 780 | `c04a200674d41e4b2711cfabc4a9870f93421a59d84380aac37fbaf72bb69fa4` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/check-node-sources.mjs` | 100 | `d46c4d12a5d23f4a2a496bafc544a7a8b7ac499e89c4496a00e564b88689c3d1` |
| `/home/tommaso/Dev/NeuroClient/app/package.json` | 165 | `36515d20ea94ebc0c49a47b79bd455fee0eddceea2eb5e52713163eff159d9e3` |
| `/home/tommaso/Dev/NeuroClient/app/vite.config.ts` | 235 | `7d70b9fae8cf5d4a8d38762865ac8f36adba1247721212fcb5b3d7455f247153` |
| `server/event_server.py` | 6978 | `eb1f6e891bc4cb149c8f054bb8ae36e4df7f2a7a7d47e6cc91af2a3e7394cdc5` |

`package.json:25` directly registers `live-subjective-actions:smoke` as the
selected command. No Tester, package, Vite, backend, SDK, or generated file may
change.

## 2. Frozen causal proof

### 2.1 Exact fault interval and values

The accepted chronology contains the eight exact checkpoints with fault counts
`0,0,0,2,2,0,0,0`. Both faults first appear at `after_equipment`; therefore the
bounded causal interval is `after_move -> after_equipment`.

Both faults compare exactly one path for the same controlled entity:

`pixi.entity_effective_appearance.<controlled UUID>`

The first expected value has weapon `Melee15` while actual remains `Melee14`.
The second expected value has weapon `null` while actual remains `Melee15`.
All other effective-appearance fields match. This is an exact one-transition
scene lag, twice, not an equipment-authoring or whole-projection disagreement.

### 2.2 Exact state-only chronology

The recent trace for each fault ends at a `frame_mapped` record whose detail is
`state-only frame; no presentation cues`, at observation cursors 13 and 21.
Each fault is recorded before the corresponding `frame_presented` trace is
appended. Jump, Move, and their visual lineages completed earlier with zero
faults and zero backlog.

### 2.3 Existing asynchronous scene owner

The store subscription in `sceneRenderer.ts` synchronously calls
`syncSceneLifecycle` when `visualLoadoutByEntity` changes. That owner resolves
the new presentation and calls `AnimatedEntity.setAppearance`.

`setAppearance` updates the base appearance but assigns the work to
`_appearanceReady = _applyAppearanceWhenReady(...)`. The asynchronous owner
preloads the current clip and preserves the prior complete rig until it can
patch the new layers. `waitForPresentationReady()` already awaits that exact
promise and rejects if required assets are unavailable.

### 2.4 Missing state-only fence

For a normal head, `eventIngestion.ts` already:

1. stages the candidate;
2. drains and asserts a visual transaction when present;
3. commits the exact journal head;
4. calls `applySubjectiveReplicaView(committed)`;
5. later records the successful frame.

The cue-less state-only precommit path settles exact position patches, but it
does not and cannot await a loadout that has not yet been applied. After commit,
`applySubjectiveReplicaView` updates the store and immediately calls
`recordExpectedRenderWorld`. That call schedules parity in a microtask while
the new rig may still be awaiting appearance assets.

The final terminal pass proves eventual convergence only. It does not make the
premature samples correct or reconcile their faults.

## 3. Required production correction

### 3.1 Internal two-phase state application

In `stateSync.ts`, extend only the existing internal
`applySubjectiveReplicaView` function so that:

1. it returns the exact `ReplicatedRenderWorld` it projected and installed;
2. it accepts one optional internal expected-world mode with exactly two
   literal values: `"record_expected_world"` and
   `"defer_expected_world_until_scene_settled"`;
3. its default remains `"record_expected_world"`, preserving every existing
   caller;
4. in normal mode it calls `recordExpectedRenderWorld(renderWorld)` exactly
   where it does today;
5. in deferred mode it does not call, schedule, clear, replace, or otherwise
   mutate render parity;
6. every store projection field, atomic store write, visibility calculation,
   equipment calculation, selection behavior, comment-owned invariant, and
   error remains unchanged;
7. it returns the same exact `renderWorld` after the store write and optional
   normal publication.

The mode must be an internal literal discriminant, not an exported framework,
public option, configuration flag, dependency, or persisted state. Existing
reset/bootstrap/reconnect callers invoke the default and remain source-
compatible even though they ignore the newly returned value.

### 3.2 Cue-less state-only post-application fence

In `eventIngestion.ts`, derive one exact local condition:

- `plan.kind === "state_only"`; and
- `preview.frame.presentation.length === 0`.

Preserve the existing precommit position-settlement behavior for that same
condition.

Inside the existing `postcommit_state_sync` try block:

1. call `applySubjectiveReplicaView(committed)` in deferred mode only for that
   exact condition by passing
   `"defer_expected_world_until_scene_settled"`; all other plans use the
   unchanged `"record_expected_world"` default mode;
2. retain the returned exact projected render world;
3. only for that exact condition, await the already-existing
   `assertSceneMatchesPresentedWorld(returnedRenderWorld)`;
4. after the await, require the same head owner still current before publishing
   or progressing;
5. only after the assertion succeeds, call the existing
   `recordExpectedRenderWorld(returnedRenderWorld)` once;
6. then preserve the existing metadata sync, staging release, configured state
   notifier, terminal handling, and successful-frame recording order.

The existing catch remains authoritative. Scene asset rejection, an exact
scene mismatch, or another assertion error must take the existing
`postcommit_state_sync` committed-failure/recovery path. No catch, retry,
fallback, snap, timeout, filter, or fault clear may be added.

### 3.3 Identity and ordering guarantees

The same returned `ReplicatedRenderWorld` object must be used for both the
scene assertion and expected-world publication. Do not re-project the replica,
re-read a later journal state, copy a DTO, or construct a second expected
world.

Expected-world publication must not occur before the assertion settles. It
must not be placed in `finally`. If the owner is retired during the await, the
old owner must not publish its world or record the frame; the authenticated
replacement/reset path remains authoritative.

### 3.4 Frozen neighboring behavior

Preserve byte-for-byte outside the narrow hunks:

- visual-transaction enqueue, outcome, precommit assertion, and cursor order;
- cue mapping and exact head recheck;
- state-only position patch settlement;
- journal commit and committed-failure recovery semantics;
- terminal encounter installation/commit;
- staging release/teardown;
- configured notifier behavior;
- reset-head application;
- bootstrap, reconnect, and authenticated-resume applications;
- scene lifecycle, appearance implementation, parity comparison/scheduling,
  diagnostics, and every Tester failure gate.

No change to `sceneRenderer.ts`, `AnimatedEntity.ts`, `renderParity.ts`, or
`eventStream.ts` is authorized. Those existing owners are reused, not
duplicated.

## 4. Prohibited alternatives

- no `setTimeout`, sleep, animation frame, debounce, throttle, or parity delay;
- no parity retry or repeated parity sampling;
- no filtering, suppression, clearing, acknowledgement, or reconciliation of
  a presentation fault;
- no final-pass-overrides-earlier-fault rule;
- no eager half-loaded rig installation;
- no direct layer patch from event ingestion or state sync;
- no backend, equipment mapper, SDK, generated, schema, protocol, persistence,
  package, dependency, or public-contract change;
- no new scene-readiness framework or duplicate appearance owner;
- no special casing of `Melee14`, `Melee15`, the fixture, entity UUID, slot, or
  smoke-only state;
- no mutation of the accepted WP-012 chronology smoke;
- no unrelated cleanup or refactor.

## 5. Authorized implementation phase

After public Gate A 4/4 plus Coordinator verification, Implementation may edit
only the two files in Section 1.2 and only the exact Sections 3.1–3.3 surface.

Implementation runs no project command. It returns to Planner only:

- exact current-vs-frozen diff;
- line counts and SHA-256 identities;
- diff-check evidence;
- proof that all frozen authorities remain unchanged;
- proof that the only new dependency edge is the existing
  `recordExpectedRenderWorld` owner imported by `eventIngestion.ts`.

Tester remains HOLD. No formatter, generated action, dependency action, build,
tsc, checker, smoke, backend, Vite, browser, probe, or cleanup is authorized in
the implementation phase.

## 6. Changed-production static review

The frozen changed identities require fresh isolated R1-R4 review. Reviewers
must prove:

1. exactly two production files changed;
2. default application behavior is preserved for every existing caller;
3. the returned render world is the exact installed projection;
4. deferral only omits the existing publication call and mutates no parity
   state;
5. the exact cue-less state-only condition owns both deferral and the new
   post-application fence;
6. the same render-world identity crosses apply, assertion, and publication;
7. scene assertion is awaited before publication and successful-frame
   recording;
8. owner retirement cannot publish stale expected state;
9. assertion failure reaches the existing committed recovery path;
10. visual transactions, reset, reconnect, and Move/Jump ordering are
    unchanged;
11. no diagnostic or Tester acceptance weakening exists;
12. cost and scope remain bounded and owner-correct.

No execution is released before public static 4/4 plus Coordinator
verification.

## 7. Governed same-policy green

### 7.1 Frozen Tester policy

The exact WP-012 smoke remains unchanged at 780 lines / SHA-256
`c04a200674d41e4b2711cfabc4a9870f93421a59d84380aac37fbaf72bb69fa4`.
Its pre-navigation console/page listeners, structured chronology, unchanged
console fault aggregation, Jump/Move/equipment/reset/objective/parity receipts,
and browser `finally` remain the same policy that produced the accepted red.

### 7.2 Prerequisites

From NeuroClient root, exactly once each, stopping on nonzero:

1. `./app/node_modules/.bin/tsc --noEmit -p ./app/tsconfig.json`;
2. `npm --prefix app run node-sources:check`.

No alternate or aggregate command is authorized.

### 7.3 Fresh owned stack

Only after both prerequisites exit zero:

1. prove ports 8000/5173 and matching packet processes absent;
2. create one brand-new disposable `/tmp` runtime root;
3. from dnd_engine root start exactly one owned backend without `--force`:

   `DND_LOCAL_PROFILE_RUNTIME_ROOT=<brand-new> ./.venv/bin/python -m server.event_server --host 127.0.0.1 --port 8000`

4. require direct `/server/capabilities` HTTP 200 with
   `server_mode=standalone` within 90 seconds;
5. start exactly one owned registered Vite and require exact-root HTTP 200 in a
   bounded window;
6. run `npm --prefix app run live-subjective-actions:smoke` exactly once as one
   recorded owned process session under an exact 300-second outer wall clock.

A preflight/start race must cause ordinary bind failure and freeze. The direct
backend launch omits `--force` and may never terminate an unrelated listener.

### 7.4 Required green evidence

The registered smoke must exit zero without timeout and emit exactly one final
JSON. That JSON must preserve every WP-011/WP-012 actual and inherited receipt,
including:

- one real fresh-character fixture and exact selected identity;
- resolved subjective readiness with equal non-null active/actions UUIDs;
- completed Jump and Move action/presentation evidence;
- completed equip and unequip evidence for the actual weapon slot;
- same-generation reset and exact bootstrap count two;
- objective-debug isolation;
- terminal backend/frontend parity `pass/pass`;
- zero console errors and zero page errors;
- all eight exact `presentationFaultChronology` labels.

Every chronology checkpoint must contain:

- zero current presentation faults;
- zero `newFaultIds` and zero `newFaults`;
- no frontend mismatch signature;
- no frontend `fail` status.

The equipment interval must complete without either accepted-red lag-one
signature, while the unchanged later action/reset/parity receipts also pass.
The final JSON and exit zero together are required; terminal convergence alone
is insufficient.

Any presentation fault, console/page error, missing/malformed chronology,
inherited assertion failure, timeout, nonzero command, or unrelated error
freezes immediately. No rerun or alternate probe is allowed.

### 7.5 Teardown

On every exit:

1. allow the smoke's browser `finally` to run;
2. terminate/join only a still-active recorded smoke tree;
3. stop/join only the owned Vite and backend trees;
4. prove ports 8000/5173 closed;
5. prove every recorded PID/child and matching Playwright, Chromium, selected
   smoke, Vite, and event-server process absent;
6. remove only the exact attempt runtime if its deletion is explicitly governed;
   otherwise retain it.

Never touch `/tmp/neurodragon-wp012-diagnostic-JBdpUA`,
`/tmp/neurodragon-wp011-green-KZW8go`, or any earlier retained root.

## 8. Gate B acceptance

After the one green attempt, fresh R1-R4 must independently assess:

- same-smoke natural red to green causality;
- exact state-only owner and render-world identity;
- absence of both equip/unequip lag-one faults;
- preservation of visual-transaction and Move/Jump ordering;
- all inherited smoke evidence and unchanged error gates;
- committed-failure behavior and owner retirement;
- process/runtime cleanup;
- performance, contracts, architecture, duplication, and strict claim scope.

Gate B closes only at public 4/4 plus Coordinator verification. WP-011 and
BUG-031 Stage 4 may then close only to the exact selected readiness correction
plus this owner-correct inherited production blocker. No broader rendering,
equipment, state-only, or BUG-031 claim follows.

## 9. Performance and architecture

The change adds one existing scene assertion to cue-less state-only normal
heads. The assertion is O(number of currently rendered entities), retains only
bounded local failure strings, and awaits readiness promises already owned by
each entity. `syncSceneLifecycle` already traverses the same entity set for the
applied projection. There is no polling, timer, retry, extra render, duplicated
asset load, or additional scene mutation.

For an unchanged appearance, the existing readiness promises are already
settled. For a changed appearance, waiting is required before the head can be
truthfully declared presented. Asset or exact-scene failure takes the existing
recovery path rather than exposing a half-settled frame.

The expected-world mode is internal and ephemeral. There is no new package,
dependency, service, schema, persistence key, wire protocol, serializer,
public API, framework, store field, or state authority. The scene renderer and
AnimatedEntity remain the sole appearance/readiness owners; event ingestion
only orders their existing fence before the existing parity publication.

## 10. Gate and owner matrix

| Stage | Owner | Authorized work |
|---|---|---|
| Plan Gate A | R1-R4 | Review this exact frozen plan only |
| Production edit | Implementation | Two files, Sections 3.1–3.3 only |
| Changed-production static | R1-R4 | Review exact changed identities |
| Same-policy green | Tester | Exact Section 7 sequence once |
| Gate B | R1-R4 | Technical acceptance on frozen evidence |

Coordinator performs governance verification and casts no technical vote.

## 11. Mandatory Gate A questions

Reviewers must answer every question on the identical frozen plan.

1. Is the accepted WP-012 Outcome A a valid same-smoke natural red?
2. Do both faults first occur only in the equipment interval?
3. Do the exact mismatch values prove Pixi is one equipment transition behind?
4. Do clean Jump/Move and passing backend parity exclude those owners?
5. Does source prove both failing frames are cue-less state-only frames?
6. Does the scene subscriber synchronously invoke `setAppearance` for the new
   projected loadout?
7. Does `setAppearance` retain the prior complete rig while
   `_appearanceReady` settles?
8. Does `waitForPresentationReady` already own that exact promise and asset
   failure?
9. Does current state sync publish the expected world before that promise is
   awaited for a state-only head?
10. Is the existing scene assertion the correct owner to await and validate
    the exact applied world?
11. Are exactly `eventIngestion.ts` and `stateSync.ts` sufficient?
12. Does the internal expected-world mode preserve default behavior for every
    other caller?
13. Does returning the existing render world avoid re-projection or copied
    authority?
14. Is deferral a no-op on parity state rather than a delay/filter/clear?
15. Is the exact condition limited to state-only plus zero presentation cues?
16. Does the post-apply fence occur inside the existing committed-failure
    boundary?
17. Is the owner rechecked after the await and before publication?
18. Does the same render-world identity cross apply, assert, and publish?
19. Is expected-world publication impossible before settlement success?
20. Do scene mismatch or asset failure remain hard recovery failures?
21. Are visual-transaction enqueue/barrier/commit boundaries unchanged?
22. Are reset, bootstrap, reconnect, and authenticated resume unchanged?
23. Are state-only position patches and successful-frame ordering preserved?
24. Are the WP-012 smoke and all console/page failure gates frozen?
25. Can green require zero faults at every chronology checkpoint, not only a
    terminal parity pass?
26. Is focused tsc plus checker plus the one registered smoke sufficient and
    causal?
27. Is the direct no-force stack ownership-safe and bounded?
28. Is teardown exclusive and are all retained roots protected?
29. Is the additional O(rendered entities) state-only boundary work necessary,
    bounded, and free of polling/duplicate asset work?
30. Does the change add no public contract, dependency, schema, persistence,
    protocol, framework, or second owner?
31. Is Gate B's claim strict enough to avoid general equipment/rendering or
    BUG-031 overclaim?
32. Is there any concrete false-red, false-green, cleanup, concurrency,
    performance, scope, contract, or human-decision blocker?

Only an unconditional approval on all answers contributes to Gate A.
