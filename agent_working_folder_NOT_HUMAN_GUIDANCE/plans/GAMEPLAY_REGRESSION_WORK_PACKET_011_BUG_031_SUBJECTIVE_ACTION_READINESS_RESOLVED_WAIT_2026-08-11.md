# Gameplay Regression Work Packet 011 — BUG-031 Stage 4 Subjective Action Readiness Resolved Wait

Date: 2026-08-11

Status: **PLANNER-FROZEN GATE A CANDIDATE — NO TESTER EDIT OR EXECUTION BEFORE FRESH PUBLIC 4/4 PLUS COORDINATOR VERIFICATION**

## 0. Decision and boundary

This packet repairs the single Promise-valued Playwright wait in:

`/home/tommaso/Dev/NeuroClient/app/scripts/live-subjective-actions-smoke.mjs`.

The wait is the exact player-input/action-availability admission boundary
before the smoke discovers live modules and exercises its inherited Jump,
Move, equipment, reset, diagnostics, and render-parity receipts.

The packet changes only two existing Tester files:

1. `app/scripts/check-node-sources.mjs`, adding one target-local source guard;
2. `app/scripts/live-subjective-actions-smoke.mjs`, replacing the one unsafe
   wait with bounded resolved polling, an independent actual state receipt,
   and the lawful fresh-character UI prerequisite needed by an isolated
   standalone run.

No production, package, Vite, SDK, generated, backend, schema, persistence,
protocol, dependency, public-contract, asset, framework, or second-smoke edit
is authorized.

### 0.1 Continuity and inventory

WP-008, WP-009, and WP-010 closed three bounded BUG-031 stages and left their
three checker rules frozen. The current inventory is 15 Promise-valued
`waitForFunction` occurrences. WP-011 selects exactly one and leaves 14 open.

The selected smoke is directly registered and uses the standalone topology
already proven in WP-008 and WP-010. A brand-new profile has no character, so
the same production-owned premade-character prerequisite is required in the
same smoke. No retained or ambient profile may be reused.

### 0.2 Candidate triage

Hosted remains failed closed because no packet-local hosted launcher exists.
The seven multi-character waits and three inventory waits span several owners
and are deferred. HUD and shove depend on broader durable/hosted fixtures. The
single subjective-action wait is the smallest remaining standalone seam.

### 0.3 Execution-safety inheritance

WP-011 incorporates WP-010's confirmed execution-safety lessons from the
start:

- `server.sh` is context only and is never the governed launcher because it
  passes destructive `--force`;
- the backend launches directly through the dnd_engine venv without
  `--force`, so a bind race fails closed;
- the registered smoke runs as one recorded process session under an exact
  300-second outer wall-clock;
- teardown targets only recorded owned process trees.

## 1. Frozen authority identity

Any mismatch stops the packet.

### 1.1 Program authorities

| Authority | Lines | SHA-256 |
|---|---:|---|
| `agent_working_folder_NOT_HUMAN_GUIDANCE/USER_REPORTED_GAMEPLAY_AND_PRODUCT_REGRESSION_LEDGER_2026-08-10.md` | 607 | `9ac0633322a2203222076a54bd2a8edb23c10e17b49b84562a77d971b922a805` |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/CURRENT_GAMEPLAY_STABILIZATION_MANIFEST_2026-08-10.md` | 798 | `0048c7192773c2a0086a540fabda89023830408ad7ecaf9894c6e34e7529fe5b` |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_STATIC_CAUSAL_STUDY_AND_WORK_PACKET_001_2026-08-10.md` | 767 | `ede1cc4b074ed0bebc104f13197bf02b80ee9cca5311c804a9f29ef7f6d14eff` |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_WORK_PACKET_008_BUG_031_TURN_BURST_RESOLVED_WAIT_2026-08-10.md` | 785 | `40c59a2a4aa954c8fe214cddd536d63101de18b02edbd54959711e1d60cf3de4` |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_WORK_PACKET_009_BUG_031_REAL_CHARACTER_TARGETING_RESOLVED_WAIT_2026-08-11.md` | 545 | `c9ac9933f99e4217c5fb1fbf673d4a1a1467124c30a826d1b67c7bbcd68349da` |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_WORK_PACKET_010_BUG_031_REPLICATION_ACTION_READINESS_RESOLVED_WAIT_2026-08-11.md` | 622 | `9e2893073f6a6d954bc77c5dda8f465d98e75449dbab975f4f7828f28bd30c07` |

### 1.2 Mutable Tester baselines

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/scripts/check-node-sources.mjs` | 88 | `8e18d618bb352db610a8ef5147a4b3a660dbd966191c72e28c10221c420d043d` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/live-subjective-actions-smoke.mjs` | 519 | `dff1d0cb048c5393befdf789f8dad94b44fb1dd421b6622e394e83c3f0a1f13f` |

The three accepted checker blocks and their corrected target files are frozen.

### 1.3 Package and Playwright authorities

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/package.json` | 165 | `36515d20ea94ebc0c49a47b79bd455fee0eddceea2eb5e52713163eff159d9e3` |
| `/home/tommaso/Dev/NeuroClient/app/vite.config.ts` | 235 | `7d70b9fae8cf5d4a8d38762865ac8f36adba1247721212fcb5b3d7455f247153` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/package.json` | 48 | `d4b8727c495ff2632084e922ee1c7f19a608ed23d86e8f3b0ba0ff317eea58ec` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/frames.js` | 1500 | `a0a5c3655b86edeb1e6acb8133d40769dda53c246340271251598dac5ff48594` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/javascript.js` | 291 | `134f2aae953ca802c3d8c4da2ddb0857129ae3044f8958cdb857993341aec257` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/chromium/crExecutionContext.js` | 146 | `4b4da27c16c2ec7094dcc3cc78313eb9ac8f15a9ed3b7589118a883d6d339b7f` |

Installed Playwright is 1.59.1. No dependency action exists.

### 1.4 Production action and replication owners

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/src/main.ts` | 636 | `e8749ccf14f3a5eed27b5d3fc8e5deff4dbbe3fc45062524eeeca787ec816440` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/store.ts` | 431 | `b0c428f266cf3c23608143e3ee73fc048f82bfb0afb5ffee3e317b1aff859537` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/actionResultHandler.ts` | 81 | `7dc73b4db848bbc57e97ca8ba493438462e44d12f7d95ff641d5c27e052bc34d` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/eventStream.ts` | 974 | `912ef41889c5a1a753d8969037550e3fabc6ecbd126e1d417e4cced6290fd522` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/clientStateMachine.ts` | 393 | `960b5efad1012accc86633f7be42c66d6ff3109114f1dce92d5cbb82a8d9d285` |
| `/home/tommaso/Dev/NeuroClient/app/src/api/actions.ts` | 111 | `857d866984ac43699d019aa4490dfa2cd0ff1fa68d82b961cb2b1a0112503462` |
| `/home/tommaso/Dev/NeuroClient/app/src/api/equipment.ts` | 79 | `2ddbf96158473cb04973c648c414d6d2db7fd976081687f4d4b61ee41ed7e5e8` |

These owners remain byte-frozen. The smoke observes their state and behavior.

### 1.5 Character and service prerequisites

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameCreationReadiness.ts` | 38 | `1dd39360063376c67a8a028742e11fdab769c3888bd6b6599f5999498ea7c1ac` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameBrowser.ts` | 1097 | `6bf4ad5e856cd38ea671218b1e9d928d51e04bcc1c054329a587fef7b9cd896c` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/characterCreator.ts` | 2772 | `bb6365ca79164a13467699d2c3142134b61f71a3560b0ef89f5f31cd3f15e20b` |
| `/home/tommaso/Dev/NeuroClient/app/src/api/gameDirectory.ts` | 961 | `7c302315a8da021fb7652baf09d2d5c9575cd82893fe15729a80a85968fe6560` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/characterSheet.ts` | 1266 | `9bdf076f1b1383e297143c044ff116b2f792c1ba1af994d29e731ebc6774ba0b` |
| `/home/tommaso/Dev/NeuroClient/server.sh` | 19 | `fd4db2fc27366f963308a93dd6c07096566b8c58bb1515a4dfbc95e8e6f1a22a` |
| `server/event_server.py` | 6978 | `eb1f6e891bc4cb149c8f054bb8ae36e4df7f2a7a7d47e6cc91af2a3e7394cdc5` |
| `server/game_directory/local_profiles.py` | 420 | `7ce82baee1b1b413c1a5b35467489c52eae53d59fabe583446ac21fb856e0ade` |

`server.sh` is context only and must not be launched. No character or backend
correctness claim is added.

## 2. Causal finding

### 2.1 Installed wait behavior

Frozen Playwright invokes the injected predicate, branches on its immediate
return, fulfills and returns for immediate truthy, then later adopts the
result. An async predicate returns a truthy Promise object. If that Promise
resolves false, the wait still completes without another predicate call.

Ordinary `page.evaluate` uses Chromium `awaitPromise: true`; Node receives the
resolved serializable value. Explicit Node polling therefore tests a Boolean.

### 2.2 Selected stale wait

After setup detaches, the smoke's async predicate imports the production store
and asks for:

- `clientState === "my_turn_input"`;
- a non-null active actor action set in `availableActionsByEntityId`.

One resolved false can complete the current wait. The later large browser
evaluation eventually checks the state before each action and will often fail
or wait elsewhere, so this defect is primarily an unreliable/unauthoritative
readiness boundary rather than a new production defect. The maintained smoke
must explicitly prove that the named admission state was resolved before live
module discovery and inherited action work begins.

### 2.3 Fresh standalone prerequisite

A brand-new standalone root contains no character. Production lawfully renders
one create requirement and disabled New Match. The current smoke clicks New
Match immediately. The packet adds the same bounded real premade-character UI
flow accepted in WP-008 and WP-010, using fixed name
`Subjective Actions Fixture`, one exact character POST, selected card, enabled
New Match, and real sheet close.

No response body is parsed and no DTO, seed, route, store, or retained profile
is used.

## 3. Required evidence

Final green must require and report:

1. initial create requirement count exactly 1;
2. New Match initially disabled;
3. one exact POST `/api/directory/characters` with successful actual status;
4. one selected card with exact rendered name `Subjective Actions Fixture`;
5. remaining requirement count 0 and New Match enabled;
6. real character sheet visible, closed, and detached;
7. resolved readiness attempts and elapsed time;
8. an independent state snapshot containing exact `my_turn_input`, non-null
   active entity UUID, and actions entity UUID equal to the active entity;
9. all inherited Jump, Move, equipment, reset, diagnostics, render-parity,
   bootstrap-count, console/page-error, and browser-cleanup receipts.

No minimum attempt count is required.

## 4. Checker first red

### 4.1 Authorized checker edit

Tester may first edit only `app/scripts/check-node-sources.mjs`. Immediately
after the accepted replication rule, add one target block equivalent to:

```js
const liveSubjectiveActionsPath = resolve(
  "scripts/live-subjective-actions-smoke.mjs",
);
const liveSubjectiveActionsSource = readFileSync(
  liveSubjectiveActionsPath,
  "utf8",
);
if (/\.waitForFunction\s*\(\s*async(?:\s+function\b|\s*\()/u.test(liveSubjectiveActionsSource)) {
  failures.push(
    "scripts/live-subjective-actions-smoke.mjs: Promise-valued waitForFunction predicate is forbidden; use explicit resolved page polling.",
  );
}
```

Path, regex semantics, order, and diagnostic are frozen. It reads only this
file and leaves 14 occurrences open.

### 4.2 Preserved checker behavior

All three accepted target blocks, recursive `.mjs` syntax checks, Vite
diagnostics, aggregation, and success summary remain byte-preserved outside
the new block.

### 4.3 Natural red

After checker-only static approval, run once from NeuroClient root:

`npm --prefix app run node-sources:check`

Accept only nonzero with the sole exact Section 4.1 diagnostic. No service or
browser starts. Any competing error freezes.

## 5. Final Tester correction

The exact first red releases an edit only to
`app/scripts/live-subjective-actions-smoke.mjs`. The checker freezes.

### 5.1 File-local helper

Add one file-local helper using Node `performance.now()` with one absolute
deadline, O(1) state, and at most one evaluation/timer in flight. It must:

1. reject expired budget before evaluation;
2. increment attempts once per actual `page.evaluate`;
3. race each evaluation against a timer for exactly remaining budget;
4. clear the timer in `finally`;
5. reject truth settling at/after the deadline;
6. return attempts/elapsed only for pre-deadline resolved truth;
7. clamp false delay to 50 ms or remaining budget, whichever is less;
8. reject stalled/repeated-false/late results with exact
   `<label> did not resolve within <timeoutMs>ms`;
9. start no post-expiry poll.

No evaluation argument is needed for this selected condition.

### 5.2 Deterministic character prerequisite

After game-browser visibility and replacing the immediate New Match click:

1. require one visible create requirement and actual disabled New Match;
2. install an exact-path POST request counter;
3. open the real premade creator and fill `Subjective Actions Fixture`;
4. arm a 60-second response wait before one real enabled create click;
5. require actual successful response status and creator detachment;
6. require one selected card with exact rendered fixed name;
7. require zero requirements and enabled New Match;
8. require real character sheet visible, close, and detached;
9. require exactly one request;
10. click the same real New Match and resume inherited setup.

No response body, request DTO, route interception, direct API/store/context
mutation, retained profile, or mock exists.

### 5.3 Resolved readiness and independent receipt

Replace only the selected async wait with the helper using 30,000 ms and label
`subjective action readiness`. Preserve the exact condition:

- production state is `my_turn_input`;
- active entity is non-null;
- `availableActionsByEntityId` returns a non-null action set for that active
  entity.

After helper success, independently evaluate the production store and record:

- `clientState`;
- `activeEntityUuid`;
- `actionsEntityUuid`.

Require exact `my_turn_input`, non-null active UUID, and action entity UUID
equal to active before live module discovery.

### 5.4 Actual output

Extend only the existing final JSON with:

- the eight actual character prerequisite fields used in WP-010;
- `subjectiveReadinessWait` actual attempts/elapsed;
- `subjectiveReadinessState` actual state and actor/action identities.

All values come from DOM/network/helper/production-store observations.

### 5.5 Inherited body frozen

Outside authorized hunks preserve:

- pageerror/console/replication-bootstrap listeners;
- setup/start/bootstrap/subscribe;
- live module URL discovery;
- real Jump and Move execution/endpoints/presentation commit;
- equipment equip/unequip receipts;
- replica reset and exact bootstrap count;
- objective diagnostics isolation;
- render parity;
- error aggregation and browser finally;
- all existing result keys and helper functions.

## 6. Exclusions

No production, package, backend, Vite, SDK, generated, dependency, schema,
protocol, persistence, public contract, asset, shared helper, second smoke,
route fixture, DTO, seed, direct state mutation, or other BUG-031 edit.

This packet does not change or claim Jump/Move/equipment/replication/rendering
behavior. Those remain inherited evidence only. Tester owns both files;
Implementation is unused.

## 7. Governed protocol

### 7.1 Gate A

Fresh isolated R1-R4 approve this exact plan; Coordinator verifies 4/4.

### 7.2 Checker first red

1. Tester edits only checker and runs nothing.
2. Freeze identity/diff; smoke remains baseline.
3. Fresh static R1-R4 plus Coordinator.
4. Checker command once; accept only exact sole red.
5. Fresh correction-release R1-R4 plus Coordinator.

### 7.3 Final combined static

1. Tester edits only selected smoke and runs nothing.
2. Freeze checker/smoke/diff.
3. Fresh combined R1-R4 plus Coordinator.

### 7.4 One-shot green

Exactly one atomic attempt:

1. focused app/src tsc once;
2. checker once;
3. prove 8000/5173 and matching packet processes free;
4. create one brand-new disposable runtime root;
5. from dnd_engine root start one owned backend without `--force`:
   `DND_LOCAL_PROFILE_RUNTIME_ROOT=<fresh> ./.venv/bin/python -m server.event_server --host 127.0.0.1 --port 8000`;
6. require direct `/server/capabilities` HTTP 200 and standalone within 90s;
7. start one owned registered Vite with bounded exact-root readiness;
8. run `npm --prefix app run live-subjective-actions:smoke` exactly once in
   one recorded process session under an exact 300-second wall-clock;
9. require exit 0 and one final JSON with all Section 3 and inherited evidence;
10. any error/timeout/missing evidence freezes without rerun.

On every exit allow browser finally, then terminate/join only a still-active
recorded smoke tree, followed by owned Vite/backend trees. Prove ports closed,
recorded PIDs/children absent, and no matching browser/smoke/Vite/event-server
process. Remove only the exact fresh runtime if governed; otherwise retain it.
Never touch retained roots.

No alternate command, probe, debug, formatter, workaround, dependency action,
force launcher, ambient service, edit, or rerun.

## 8. Owners and review

Planner owns plan; R1-R4 review independently; Coordinator verifies but does
not vote; Tester owns checker/smoke stages; Implementation has no assignment.
Every changed identity invalidates prior votes for that surface.

## 9. Complexity and contracts

Checker adds one constant read/regex. Helper is O(1), one evaluation/timer, one
30-second bound. Character setup is one bounded test-only UI action. No product
hot-path, allocation owner, contract, serializer, persistence key, route,
schema, dependency, or public export changes.

## 10. Strict closure

Acceptance may claim only:

> BUG-031 Stage 4: the maintained live-subjective-actions smoke is statically
> guarded against its Promise-valued player-input/action-availability wait and
> observes resolved production readiness on a lawful fresh character fixture
> before its inherited subjective-action receipts.

It may not claim production, character creation, Jump, Move, equipment,
replication, rendering, backend, gameplay, or closure of the 14 remaining
occurrences.

## 11. Mandatory Gate A questions

1. Does package directly register the selected smoke and include it live?
2. Is there exactly one Promise-valued wait in the selected smoke?
3. Does Playwright branch on the immediate Promise before assimilation?
4. Can resolved false complete without repolling?
5. Is the intended condition exactly input state plus active actions?
6. Can the current call continue without proving that readiness boundary?
7. Does the checker target only this smoke and preserve three prior rules?
8. Will stale source deterministically emit the exact sole red?
9. Does first red require no service/browser?
10. Does page.evaluate return the resolved Boolean?
11. Does helper use one monotonic deadline?
12. Is every evaluation bounded by remaining time with timer cleanup?
13. Are late truth, repeated false, stalls, and post-expiry polls excluded?
14. Does final condition preserve exact store ownership?
15. Is readiness independently re-read/asserted/reported?
16. Does a brand-new profile lawfully start character-empty?
17. Do initial requirement/disabled assertions exclude ambient state?
18. Does fixture use real creator and one exact POST without DTO/body parsing?
19. Are response, detach, card/name, requirement, enabled, and sheet receipts
    all mandatory?
20. Are all new fields actual observations?
21. Are inherited Jump/Move/equipment/reset/diagnostics/parity receipts frozen?
22. Are page/console/bootstrap listeners and browser finally preserved?
23. Does checker preserve syntax/Vite/aggregation behavior?
24. Are two Tester files sufficient?
25. Is direct no-force standalone launch ownership-safe?
26. Is the 300-second recorded smoke process enforceably bounded?
27. Does teardown target only recorded owners and fresh runtime?
28. Is overhead bounded/test-only with zero product hot-path cost?
29. Does closure leave 14 occurrences and product owners unchanged?
30. Is any concrete causal, false-green/red, cleanup, service, duplication,
    serialization, scope, performance, contract, or human blocker unresolved?

## 12. Review record

Gate A begins at public 0/4 on this exact plan identity. No prior vote carries.
