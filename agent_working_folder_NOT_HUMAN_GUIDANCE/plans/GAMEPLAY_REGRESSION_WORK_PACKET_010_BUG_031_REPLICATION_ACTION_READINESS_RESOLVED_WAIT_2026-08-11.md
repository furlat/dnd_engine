# Gameplay Regression Work Packet 010 — BUG-031 Stage 3 Replication Action Readiness Resolved Wait

Date: 2026-08-11

Status: **PLANNER-FROZEN GATE A REVISION 2 CANDIDATE — REVISION 1 REJECTED/VOID; NO TESTER EDIT OR EXECUTION AUTHORIZED BEFORE FRESH PUBLIC 4/4 PLUS COORDINATOR VERIFICATION**

This packet is the next bounded seam under the standing automatic-progression
policy. It repairs exactly one Promise-valued Playwright polling predicate in
the maintained replication smoke and makes that smoke's fresh standalone
character prerequisite deterministic through the existing production UI. It
is a Tester-authority repair, not a production behavior change.

## 0. Decision and packet boundary

The selected seam is the action-readiness receipt in:

`/home/tommaso/Dev/NeuroClient/app/scripts/replication-smoke.mjs`.

After the real match bootstrap, the smoke discovers the live Vite URL for
`actionBar.ts`, then passes an async first argument to `page.waitForFunction`.
That predicate imports the live action-bar module and production store and asks
whether End Turn geometry is available while `clientState` is
`my_turn_input`.

The installed Playwright runtime does not re-poll that predicate by its
resolved Boolean. It invokes the predicate, sees the immediate Promise object
as truthy, selects success once, and later assimilates that single Promise. A
resolved `false` completes the wait rather than scheduling another predicate
invocation.

The packet changes only two existing Tester files:

1. `app/scripts/check-node-sources.mjs`, adding one target-specific source rule;
2. `app/scripts/replication-smoke.mjs`, replacing the one unsafe wait with
   explicit bounded resolved polling, actual state evidence, and the lawful
   fresh-character UI prerequisite needed by an isolated standalone run.

No production, package, Vite, SDK, generated, backend, schema, persistence,
protocol, public-contract, dependency, asset, or second-smoke edit exists.

### 0.1 Continuity from WP-008 and WP-009

WP-008 closed BUG-031 Stage 1 for `turn-burst-smoke.mjs`. WP-009 closed Stage
2 for the two Move-targeting waits in
`real-character-game-creation-live-smoke.mjs`. Their target-specific checker
rules, final source identities, evidence, and strict closures remain accepted
history and must be byte-preserved.

The current static inventory contains 16 Promise-valued `waitForFunction`
occurrences after WP-009. This packet selects the single occurrence in
`replication-smoke.mjs`. If accepted, 15 occurrences remain explicitly open.

### 0.2 Candidate triage

The Planner failed the hosted candidate closed because the repository exposes
no packet-local launcher for the hosted topology consumed by
`hosted-game-smoke.mjs`; inventing that service protocol would materially
expand this packet.

The Planner also deferred:

- seven occurrences in `multi-character-live-smoke.mjs`, which span turn
  handoff, selection, target, and movement authorities;
- three occurrences in `inventory-panel-smoke.mjs`, which span initial game,
  equipment loading, and test-authored pagination;
- two hosted-game occurrences, which require hosted service ownership;
- the remaining single-occurrence HUD, shove, and subjective-action smokes,
  which depend on broader durable or hosted fixtures.

The selected replication wait is one coherent readiness boundary. Its smoke is
directly registered, uses the same standalone backend/Vite topology already
governed in WP-008, and can establish its missing fresh-character prerequisite
inside the same file through the exact real UI/API owner already accepted in
WP-008. No ambient or retained profile is needed.

### 0.3 Revision 1 execution-safety rejection

Revision 1 is rejected and void at public 0/4. No Revision 1 vote carries.
Two plan-only execution blockers were confirmed before any packet execution:

1. Revision 1 launched `bash ./server.sh`. Frozen `server.sh` always passes
   `--force`; frozen `event_server.py` then calls `kill_process_on_port(8000)`
   and signals listeners. A free-port preflight cannot eliminate a
   check/start race, so that launcher violated exclusive process ownership.
2. Revision 1 did not put the registered replication smoke itself under an
   enforceable outer wall-clock. An unrelated stalled page evaluation could
   prevent browser `finally` and make teardown unenforceable.

Revision 2 uses the repository venv interpreter to launch the same frozen
standalone module directly without `--force`. A raced listener causes ordinary
bind failure instead of termination. Revision 2 also owns the replication
smoke as one recorded process session under an exact 300-second outer bound.
These are execution-protocol corrections only. No source/test/package/backend
or service design changes.

## 1. Frozen authority identity

All review and work must use the following exact files. Any mismatch stops the
packet and returns to Planner intake.

### 1.1 Program authorities

| Authority | Lines | SHA-256 |
|---|---:|---|
| `agent_working_folder_NOT_HUMAN_GUIDANCE/USER_REPORTED_GAMEPLAY_AND_PRODUCT_REGRESSION_LEDGER_2026-08-10.md` | 607 | `9ac0633322a2203222076a54bd2a8edb23c10e17b49b84562a77d971b922a805` |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/CURRENT_GAMEPLAY_STABILIZATION_MANIFEST_2026-08-10.md` | 798 | `0048c7192773c2a0086a540fabda89023830408ad7ecaf9894c6e34e7529fe5b` |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_STATIC_CAUSAL_STUDY_AND_WORK_PACKET_001_2026-08-10.md` | 767 | `ede1cc4b074ed0bebc104f13197bf02b80ee9cca5311c804a9f29ef7f6d14eff` |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_WORK_PACKET_008_BUG_031_TURN_BURST_RESOLVED_WAIT_2026-08-10.md` | 785 | `40c59a2a4aa954c8fe214cddd536d63101de18b02edbd54959711e1d60cf3de4` |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_WORK_PACKET_009_BUG_031_REAL_CHARACTER_TARGETING_RESOLVED_WAIT_2026-08-11.md` | 545 | `c9ac9933f99e4217c5fb1fbf673d4a1a1467124c30a826d1b67c7bbcd68349da` |

The regression ledger is intake authority only. Authorization comes from the
standing bounded-packet policy and the fresh Gate A ledger.

### 1.2 Mutable Tester baselines

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/scripts/check-node-sources.mjs` | 81 | `abe8b5d3ffae6abad4ab8658dc137bd8870144818d39220eab85c918d7759898` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/replication-smoke.mjs` | 217 | `aaf14ee160c4a84e8a5cfe81a6ff170c759eaaa4ef71340ccd1439e711a39f39` |

The checker already contains the accepted WP-008 turn-burst and WP-009
real-character rules. Both exact paths, regexes, diagnostics, and order must
remain byte-preserved.

### 1.3 Frozen accepted checker targets

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/scripts/turn-burst-smoke.mjs` | 336 | `3e71c47d90d983df2a88d5483f288454bf476e4b81cb1f3108f35c1660495420` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/real-character-game-creation-live-smoke.mjs` | 528 | `01650889d45e6d77db0f96ee22bbfd84f99125592db88ca2be1dd68f81fdcd5a` |

These files are immutable in WP-010.

### 1.4 Frozen package and Playwright authorities

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/package.json` | 165 | `36515d20ea94ebc0c49a47b79bd455fee0eddceea2eb5e52713163eff159d9e3` |
| `/home/tommaso/Dev/NeuroClient/app/vite.config.ts` | 235 | `7d70b9fae8cf5d4a8d38762865ac8f36adba1247721212fcb5b3d7455f247153` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/package.json` | 48 | `d4b8727c495ff2632084e922ee1c7f19a608ed23d86e8f3b0ba0ff317eea58ec` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/client/frame.js` | 404 | `49a0d5aa0c154b4fd588eda16a25cc93909923f91c06ce9afdd384506b703991` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/frames.js` | 1500 | `a0a5c3655b86edeb1e6acb8133d40769dda53c246340271251598dac5ff48594` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/javascript.js` | 291 | `134f2aae953ca802c3d8c4da2ddb0857129ae3044f8958cdb857993341aec257` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/chromium/crExecutionContext.js` | 146 | `4b4da27c16c2ec7094dcc3cc78313eb9ac8f15a9ed3b7589118a883d6d339b7f` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/dispatchers/pageDispatcher.js` | 456 | `eccc0ce018eb6c8dc04b9ba495303fa88f6f1f7d560bec14082a7c06d7a526ba` |

The installed Playwright version is `1.59.1`. No dependency action is
authorized.

### 1.5 Frozen production readiness and replication owners

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/src/main.ts` | 636 | `e8749ccf14f3a5eed27b5d3fc8e5deff4dbbe3fc45062524eeeca787ec816440` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/store.ts` | 431 | `b0c428f266cf3c23608143e3ee73fc048f82bfb0afb5ffee3e317b1aff859537` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/actionBar.ts` | 2429 | `0f741a9a0abcf69ff9d62ad2685ba052531d0b4ba842edcc5c72693c60a8f52e` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/eventStream.ts` | 974 | `912ef41889c5a1a753d8969037550e3fabc6ecbd126e1d417e4cced6290fd522` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/actionResultHandler.ts` | 81 | `7dc73b4db848bbc57e97ca8ba493438462e44d12f7d95ff641d5c27e052bc34d` |
| `/home/tommaso/Dev/NeuroClient/app/src/render/presentationDiagnostics.ts` | 1264 | `4271e3b7711b8964212f9d0994877768c386c1ac359b476f5c3b94d3d8233f69` |

The action bar remains the End Turn geometry owner. The store remains the
client-state and replication-cursor owner. The smoke observes those owners; it
does not duplicate or mutate them.

### 1.6 Frozen character and service prerequisites

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

These are frozen prerequisites. No character, match, backend, or replication
production correctness claim is added. `server.sh` is frozen causal context
only: its unconditional `--force` behavior is why it is explicitly not the
Revision 2 governed launcher.

## 2. Exact causal finding

### 2.1 Installed wait behavior

In frozen `frames.js`, the injected wait loop calls `predicate()`, branches on
the immediate result, fulfills and returns for immediate truthy, and only later
awaits the adopted result. An async predicate immediately returns a Promise.
That Promise object is truthy even when it later resolves false. The eventual
false completes the wait and does not schedule another poll.

Ordinary `page.evaluate` is different. Chromium uses `awaitPromise: true`, so
the Node caller receives the page function's resolved serializable Boolean.
Explicit Node polling around `page.evaluate` tests the resolved value.

### 2.2 Selected stale readiness receipt

The current replication smoke discovers the live action-bar module URL after
match setup, then waits with an async predicate requiring both:

- `getActionBarDebugGeometry().endTurnCenter !== null`;
- `store.getState().clientState === "my_turn_input"`.

The current call can complete after one resolved false. The smoke then reads
End Turn geometry again, but it does not independently require the exact
client state when geometry exists. Timing can therefore turn the intended
polling boundary into an early continuation or a nondeterministic later
failure rather than proving the combined readiness state.

### 2.3 Fresh standalone prerequisite

The governed green must not reuse an ambient or retained profile. A brand-new
standalone profile contains no character, so production correctly renders New
Match disabled with one `create-match-requirement`. The current replication
smoke clicks New Match immediately and would stop before the repaired seam.

The smallest truthful prerequisite is the same real UI/API flow already
accepted in WP-008: prove the initial disabled requirement, create one premade
character with a fixed name through the production creator and exact character
POST, prove the selected named card and enabled New Match, close the real
character sheet, then continue the inherited replication path.

This is not a replication or character feature claim. It is attempt-local
fixture admission inside the same Tester file. A runner-side seed, retained
profile, request DTO, mock, or direct store write would duplicate production
authority and is forbidden.

## 3. Required final evidence

The final smoke must require and report actual values for:

1. exactly one initial visible create-match requirement;
2. actual initial New Match disabled state equal to true;
3. exactly one observed POST whose parsed pathname is exactly
   `/api/directory/characters`;
4. actual successful character response status;
5. exactly one selected character card with fixed name
   `Replication Readiness Fixture`;
6. zero remaining create-match requirements;
7. actual final New Match enabled state equal to true;
8. real character-sheet visibility followed by its real close and detachment;
9. a bounded resolved readiness receipt with actual `attempts` and
   `elapsedMs`;
10. an independent post-helper snapshot with
    `clientState === "my_turn_input"` and non-null End Turn geometry;
11. every inherited bootstrap, stream, End Turn, authoritative/presentation
    cursor, backlog, replication-health, console-error, page-error, and cleanup
    assertion unchanged.

No minimum poll attempt count is required. Readiness may lawfully be true on
the first resolved evaluation. The correctness boundary is the resolved value
plus the independent actual snapshot.

## 4. First-red checker witness

### 4.1 Authorized checker edit

Tester may first edit only:

`/home/tommaso/Dev/NeuroClient/app/scripts/check-node-sources.mjs`.

Immediately after the accepted real-character rule, add one block equivalent
to:

```js
const replicationSmokePath = resolve("scripts/replication-smoke.mjs");
const replicationSmokeSource = readFileSync(replicationSmokePath, "utf8");
if (/\.waitForFunction\s*\(\s*async(?:\s+function\b|\s*\()/u.test(replicationSmokeSource)) {
  failures.push(
    "scripts/replication-smoke.mjs: Promise-valued waitForFunction predicate is forbidden; use explicit resolved page polling.",
  );
}
```

Formatting may follow the checker, but path, regex semantics, order, and exact
diagnostic are frozen. The rule reads only the named replication smoke and
must not scan or fail the other 15 open occurrences.

### 4.2 Preserved checker behavior

The accepted WP-008 and WP-009 rules, recursive `.mjs` `node --check`
traversal, Vite-config diagnostics, aggregate failure, and success summary
remain byte-preserved outside the new block.

### 4.3 Natural first red

After fresh static approval of the checker-only identity, Tester runs exactly
once from NeuroClient root:

`npm --prefix app run node-sources:check`

The sole accepted result is nonzero with the exact Section 4.1 diagnostic. No
backend, Vite, browser, or product smoke starts. Any TypeScript, syntax, Vite,
path, timeout, or competing checker failure freezes the packet.

## 5. Final Tester correction

The exact natural red releases an edit only to:

`/home/tommaso/Dev/NeuroClient/app/scripts/replication-smoke.mjs`.

The checker is frozen after first red.

### 5.1 File-local resolved poll helper

Add one file-local helper accepting:

- the page;
- an async page condition;
- one serializable evaluation argument;
- timeout, label, and optional poll interval.

The helper must:

1. use Node `performance.now()`;
2. compute one absolute deadline for the whole wait;
3. keep O(1) state: start, deadline, attempts, one timer, one result;
4. reject exhausted budget before every evaluation;
5. increment attempts once per actual evaluation;
6. call `page.evaluate(evaluateCondition, evaluateArgument)`;
7. race every evaluation against a Node timer for exactly the remaining
   budget;
8. clear the timer in `finally` on every outcome;
9. reject a truthy result settling at or after the deadline;
10. return `{ attempts, elapsedMs }` only for a pre-deadline resolved truthy
    value;
11. on false, delay by no more than the lesser of 50 ms and remaining budget;
12. on stalled evaluation, repeated false, or late truth, throw exactly
    `<label> did not resolve within <timeoutMs>ms`;
13. never begin a poll after expiry.

`Promise.race` observes losing evaluation work. The smoke's browser `finally`
closes the page on error. Runner-owned backend and Vite teardown remains
separate.

### 5.2 Deterministic real-character prerequisite

Immediately after the existing game-browser visibility receipt and replacing
the immediate New Match click:

1. bind the real New Match and `create-match-requirement` locators;
2. require exactly one visible requirement and New Match disabled;
3. install an observation-only request counter before creator interaction;
4. match only POST requests whose parsed pathname equals exactly
   `/api/directory/characters`;
5. click the real premade-character control;
6. require the production custom creator visible;
7. fill the fixed name `Replication Readiness Fixture`;
8. arm one bounded exact response wait before clicking the real enabled create
   control once;
9. record actual response status and require `ok()`;
10. require creator detachment;
11. require exactly one selected card with exact rendered fixed name;
12. require zero remaining create requirements and New Match enabled;
13. require the real character sheet visible, close it with its existing close
    control, and require detachment;
14. require the character POST counter equals exactly one;
15. click the same real New Match control and resume the inherited setup.

The smoke must not parse/copy the response body, construct a request DTO,
intercept a route, seed an API, or mutate store/directory context.

### 5.3 Resolved action-readiness correction

Replace only the selected async `waitForFunction` call with the helper using:

- evaluation argument: the already-discovered live action-bar module URL;
- timeout: 30,000 ms;
- label: `replication action readiness`.

The page condition must preserve the exact conjunction:

- imported live `getActionBarDebugGeometry().endTurnCenter !== null`;
- imported production `store.getState().clientState === "my_turn_input"`.

After the helper returns, independently evaluate the same owners and record:

- actual `clientState`;
- actual `endTurnCenter`.

Require the state equals `my_turn_input` and center is non-null before
installing the backlog probe or clicking End Turn. Retain the later existing
End Turn center/canvas/action-state handling.

### 5.4 Actual summary evidence

Add only these fields to the existing `observed` JSON:

- `initialCreateRequirementCount`;
- `initialNewMatchDisabled`;
- `characterCreateRequestCount`;
- `characterCreateStatus`;
- `createdCharacterCardCount`;
- `characterFixtureName`;
- `remainingCreateRequirementCount`;
- `finalNewMatchEnabled`;
- `actionReadinessWait` with actual attempts/elapsed;
- `actionReadinessState` with actual client state and End Turn center.

The values must come from the real DOM, response/request events, helper, and
production-owner snapshot. No hard-coded success Boolean substitutes for an
observation.

### 5.5 Byte-preserved inherited body

Outside the exact insertions and replacement above, preserve:

- pre-navigation console/page-error listeners and failure aggregation;
- real game setup and start;
- exact bootstrap and subscribe response assertions;
- action-bar live-module discovery;
- backlog probe installation and cleanup;
- real canvas End Turn click and exact response;
- authoritative cursor advance;
- presentation cursor equality;
- zero final backlog and ready replication health;
- positive maximum presentation backlog proof;
- body diagnostics on failure;
- browser finally cleanup;
- every pre-existing output field and package command.

## 6. Explicit exclusions and owner separation

This packet does not authorize:

- any production edit;
- changing action-bar geometry, End Turn, store state, replication, event
  stream, presentation backlog, or cursor semantics;
- changing character/game creation behavior;
- package, Vite, Playwright, SDK, generated, backend, schema, persistence,
  protocol, public contract, dependency, or asset changes;
- a shared polling or character-fixture framework;
- direct API seeding, retained or ambient profile reuse, response fixtures,
  route interception, DTO construction, or direct store/context mutation;
- a second smoke or a checker-wide allowlist;
- fixing or claiming any other BUG-031 occurrence;
- Move/Jump, animation, path, pixels, gameplay, or general replication claims.

Tester owns both permitted files. Implementation remains unused.

## 7. Governed execution protocol

### 7.1 Gate A

Fresh isolated R1-R4 review must approve this exact plan identity. Coordinator
verifies public 4/4 before any Tester edit.

### 7.2 Checker first-red sub-gate

1. Tester edits only the checker and runs nothing.
2. Freeze checker identity/diff; replication smoke remains at baseline.
3. Obtain fresh isolated static R1-R4 plus Coordinator verification.
4. Run `npm --prefix app run node-sources:check` exactly once.
5. Accept only the sole exact Section 4.1 diagnostic.
6. Any other result freezes; no rerun or follow-up command.
7. Obtain fresh correction-release R1-R4 plus Coordinator verification.

### 7.3 Final correction static sub-gate

1. Tester edits only the replication smoke as Section 5 specifies and runs
   nothing.
2. Freeze final checker/smoke identities, complete baseline diff, and
   diff-check evidence.
3. Obtain fresh combined R1-R4 plus Coordinator verification.

### 7.4 One-shot green

After the combined static sub-gate closes, exactly one atomic attempt may run:

1. from NeuroClient root, run
   `./app/node_modules/.bin/tsc --noEmit -p ./app/tsconfig.json` once;
2. only if zero, run `npm --prefix app run node-sources:check` once;
3. only if zero, prove ports 8000/5173 free and no matching backend, Vite,
   browser, or replication-smoke process active;
4. create one brand-new disposable `/tmp` runtime root; every retained or
   ambient/developer profile is forbidden;
5. from dnd_engine root, start exactly one owned standalone backend without
   `--force` using the repository venv interpreter:
   `DND_LOCAL_PROFILE_RUNTIME_ROOT=<brand-new> ./.venv/bin/python -m server.event_server --host 127.0.0.1 --port 8000`;
   if another listener wins the preflight/start race, ordinary bind failure
   freezes the attempt and must never terminate that listener;
6. probe only `http://127.0.0.1:8000/server/capabilities` for at most 90
   seconds, requiring HTTP 200 and `server_mode=standalone`;
7. only after backend readiness, start one owned Vite from the registered app
   development command with exact root HTTP readiness and a bounded wait;
8. run `npm --prefix app run replication:smoke` exactly once as one recorded
   owned process session under an exact 300-second outer wall-clock;
9. require exit zero and one final JSON with every Section 3 field plus all
   inherited replication evidence;
10. any nonzero, timeout, missing/malformed evidence, error, or cleanup mismatch
    freezes immediately.

On every exit, first allow the smoke's existing browser `finally` to complete.
If the 300-second outer bound expires or the smoke session otherwise remains
active, terminate and join only that recorded smoke process tree. Then
stop/join only the owned Vite and backend process trees, prove ports 8000/5173
closed, prove all recorded owned PIDs/children absent, and prove no matching
Playwright/Chromium/replication-smoke/Vite/event-server process remains. A
timeout is a frozen non-green result and never authorizes a rerun.

The brand-new runtime may be removed only if exact owned removal is part of the
governed attempt; otherwise retain it for inspection. WP-008 evidence roots
and all other retained roots are outside this packet and must not be reused or
removed.

No rerun, alternate probe/command, debug, formatter, workaround, dependency
action, mock, ambient service, or unrelated execution is authorized.

## 8. Owner and review workflow

1. Planner owns this plan only.
2. R1 correctness, R2 backend/runtime, R3 frontend/test, and R4
   scope/duplication/serialization review independently.
3. Coordinator verifies governance and public ledgers but casts no technical
   vote.
4. Tester performs checker edit, first red, final smoke edit, and one-shot
   green only when individually released.
5. Implementation has no assignment.
6. Every changed frozen identity invalidates earlier votes for that surface.
7. Findings route through Planner to the one affected Tester owner.

## 9. Complexity, contracts, and performance

The checker adds one constant file read/regex. The runtime helper keeps O(1)
state with at most one evaluation and one timer in flight under one 30-second
deadline. Character setup performs one bounded real UI/API creation in the
test only. No product hot-path work is added.

No wire model, generated type, JSON representation, persistence key, backend
route, request/response schema, serializer, public export, package command,
dependency, or production allocation owner changes.

The local helper and prerequisite remain deliberately test-local. Extracting a
shared polling or fixture framework would materially expand architecture and
is forbidden.

## 10. Strict closure claim

Acceptance may claim only:

> BUG-031 Stage 3: the maintained replication smoke is statically guarded
> against its Promise-valued action-readiness predicate and explicitly waits
> on resolved production action-bar/store readiness before exercising its
> inherited replication receipt on a fresh lawful character fixture.

It may not claim:

- a production fix;
- general Playwright readiness correctness;
- closure of the remaining 15 BUG-031 occurrences;
- character or game creation correctness beyond prerequisite evidence;
- general replication, End Turn, presentation, backend, gameplay, Move/Jump,
  animation, Pixi, or product-browser correctness;
- BUG-009, BUG-011, BUG-023, BUG-029, BUG-030, BUG-032, or full ledger closure.

## 11. Mandatory Gate A review questions

Reviewers must answer every question against the exact frozen sources.

1. Does package.json directly register `replication:smoke` to the selected
   file and include it in `live:check`?
2. Is there exactly one Promise-valued `waitForFunction` call in that smoke?
3. Does frozen Playwright branch on the immediate Promise object before later
   assimilating its eventual Boolean?
4. Can one resolved false complete the current wait without another poll?
5. Does the current wait intend the exact combined End Turn geometry plus
   `my_turn_input` receipt?
6. Does the later current geometry read fail to independently require the
   exact client state when geometry is present?
7. Does the checker addition read only replication-smoke and preserve both
   accepted earlier rules?
8. Will the frozen stale source deterministically produce the exact first red?
9. Does first red require no backend, Vite, browser, or product smoke?
10. Does ordinary page.evaluate return the async condition's resolved value?
11. Does the helper use one monotonic deadline for the complete wait?
12. Is every evaluation raced against exactly its remaining budget with timer
    cleanup?
13. Are stalled evaluation, repeated false, and late truth all rejected with
    the exact label timeout and no post-expiry poll?
14. Does the helper pass the live action-bar URL as a serializable evaluation
    argument rather than capturing a Node closure?
15. Does the final condition preserve non-null End Turn geometry and exact
    `my_turn_input`?
16. Is the post-helper production-owner snapshot independently asserted and
    reported?
17. Does a brand-new standalone profile lawfully start with no character and
    disabled New Match?
18. Does the same-file prerequisite require the exact initial requirement and
    disabled control rather than accepting ambient state?
19. Does it use the real premade creator and exactly one exact-path character
    POST without parsing/copying a response DTO?
20. Does it require successful response, creator detach, one selected named
    card, requirement removal, and enabled New Match?
21. Does it close and detach the real production-opened character sheet before
    clicking New Match?
22. Are all prerequisite and readiness values actual observations in the
    final JSON rather than hard-coded success flags?
23. Are bootstrap, subscribe, End Turn, cursors, backlog, health, errors, and
    browser cleanup byte-preserved outside authorized hunks?
24. Does the checker retain recursive Node syntax, Vite diagnostics,
    aggregation, and success behavior?
25. Are exactly two existing Tester files sufficient with no package,
    production, service, or third-file edit?
26. Is focused tsc, one checker, one direct no-force standalone backend, one
    Vite, and one registered replication smoke under an exact 300-second outer
    session sufficient and bounded?
27. Does teardown cover the recorded smoke tree, browser, owned services,
    ports, PIDs, descendants, and fresh runtime without touching retained roots
    or terminating any listener not owned by the attempt?
28. Is test overhead O(1)/bounded with zero product hot-path cost?
29. Does final checker green close only the selected call while leaving 15
    occurrences open and all product owners unchanged?
30. Is there any concrete false-red, false-green, cleanup, duplication,
    serialization, scope, service, performance, contract, or human-decision
    blocker requiring rejection?

## 12. Review record

Revision 2 Gate A begins at public 0/4 on this exact plan identity. Revision 1
is rejected/void and no vote from Revision 1, WP-008, WP-009, or any earlier
packet carries forward.
