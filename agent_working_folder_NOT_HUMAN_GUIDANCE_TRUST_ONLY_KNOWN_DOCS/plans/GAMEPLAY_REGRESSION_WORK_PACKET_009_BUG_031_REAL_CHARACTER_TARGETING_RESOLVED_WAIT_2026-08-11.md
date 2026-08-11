# Gameplay Regression Work Packet 009 — BUG-031 Stage 2 Real-Character Targeting Resolved Wait

Date: 2026-08-11

Status: **PLANNER-FROZEN GATE A CANDIDATE — NO TESTER EDIT OR EXECUTION AUTHORIZED BEFORE FRESH PUBLIC 4/4 PLUS COORDINATOR VERIFICATION**

This packet is the next bounded seam under the standing automatic-progression
policy. It repairs exactly two Promise-valued Playwright polling predicates in
the maintained real-character product smoke. It is a Tester-authority repair,
not a production behavior change.

## 0. Decision and packet boundary

The selected seam is the coherent Move-targeting receipt in:

`/home/tommaso/Dev/NeuroClient/app/scripts/real-character-game-creation-live-smoke.mjs`.

The current smoke focuses the real mounted Move accessibility button, presses
Enter, waits for `targetingMode` to become a populated `position_path`, records
the targeting snapshot, presses Escape, and waits for the mode to return to
`none`. Both state waits pass an async function as the first argument to
`page.waitForFunction`.

The installed Playwright runtime does not re-poll those functions by their
resolved Boolean. It invokes the predicate, sees the immediate Promise object
as truthy, selects the success branch once, and later assimilates that single
Promise. A resolved `false` completes the wait rather than scheduling another
poll.

The packet changes only two existing Tester files:

1. `app/scripts/check-node-sources.mjs`, adding one target-specific source rule;
2. `app/scripts/real-character-game-creation-live-smoke.mjs`, replacing exactly
   the two unsafe waits with explicit resolved polling and actual evidence.

No production, package, Vite, SDK, generated, backend, schema, persistence,
protocol, public-contract, dependency, asset, or second-smoke edit exists.

### 0.1 Continuity from WP-008

WP-008 closed BUG-031 Stage 1 for `turn-burst-smoke.mjs`. Its checker rule,
resolved-poll implementation, exact frozen identities, and strict closure
remain accepted history. This packet does not revise or rerun WP-008 evidence.

The current static inventory contains 18 Promise-valued `waitForFunction`
occurrences after WP-008. This packet selects the two occurrences in one
maintained smoke. If accepted, 16 occurrences remain explicitly open.

### 0.2 Candidate triage

The Planner failed the following nearby candidates closed for this packet:

- `live-subjective-actions-smoke.mjs`, `replication-smoke.mjs`, and
  `live-shove-presentation-smoke.mjs` require ambient or durable character
  prerequisites not owned by those smokes;
- `hud-rpg-smoke.mjs` and `inventory-panel-smoke.mjs` also depend on broader
  character/roster fixtures, and the latter contains three unrelated polling
  receipts;
- `multi-character-live-smoke.mjs` contains seven occurrences spanning several
  independent authorities;
- hosted and Studio surfaces require different service or workspace ownership.

The chosen real-character smoke already owns its fresh runtime, standalone
backend, Vite server, browser, real character creation, match start, mounted
gameplay receipt, and cleanup. Repairing its two adjacent targeting waits does
not introduce a new prerequisite or process owner.

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

The regression ledger is intake authority only. This packet's authorization
comes from the standing bounded-packet policy and the fresh Gate A ledger.

### 1.2 Mutable Tester baselines

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/scripts/check-node-sources.mjs` | 74 | `9f2be912ea3f805dac235bb3a63ed8d021422511a883ad91676cd1f225975052` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/real-character-game-creation-live-smoke.mjs` | 449 | `104216107f465e364ab35131de48ec4102bb471d78c36df7546b1709770a91d6` |

`check-node-sources.mjs` already contains the accepted WP-008 rule targeting
only `turn-burst-smoke.mjs`. That rule and its exact diagnostic must remain
byte-preserved.

### 1.3 Frozen package and runtime authorities

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/package.json` | 165 | `36515d20ea94ebc0c49a47b79bd455fee0eddceea2eb5e52713163eff159d9e3` |
| `/home/tommaso/Dev/NeuroClient/app/vite.config.ts` | 235 | `7d70b9fae8cf5d4a8d38762865ac8f36adba1247721212fcb5b3d7455f247153` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/package.json` | 48 | `d4b8727c495ff2632084e922ee1c7f19a608ed23d86e8f3b0ba0ff317eea58ec` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/client/frame.js` | 404 | `49a0d5aa0c154b4fd588eda16a25cc93909923f91c06ce9afdd384506b703991` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/frames.js` | 1500 | `a0a5c3655b86edeb1e6acb8133d40769dda53c246340271251598dac5ff48594` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/javascript.js` | 291 | `134f2aae953ca802c3d8c4da2ddb0857129ae3044f8958cdb857993341aec257` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/chromium/crExecutionContext.js` | 146 | `4b4da27c16c2ec7094dcc3cc78313eb9ac8f15a9ed3b7589118a883d6d339b7f` |

The installed Playwright version is `1.59.1`. No dependency action is
authorized.

### 1.4 Frozen production owners

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/src/main.ts` | 636 | `e8749ccf14f3a5eed27b5d3fc8e5deff4dbbe3fc45062524eeeca787ec816440` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/store.ts` | 431 | `b0c428f266cf3c23608143e3ee73fc048f82bfb0afb5ffee3e317b1aff859537` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/control.ts` | 304 | `f321847ba5df055269eb483006f289642a30c8ee6f3b2da46ae898630157f483` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/actionBar.ts` | 2429 | `0f741a9a0abcf69ff9d62ad2685ba052531d0b4ba842edcc5c72693c60a8f52e` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/targeting.ts` | 854 | `aa924b618a59dbf4588b203ad21bfa9359834d48a486a49c68f57fc84e458930` |

`control.ts` is the sole targeting transition owner. `actionBar.ts` requests
the open transition for an available Move action. `targeting.ts` requests the
cancel transition on Escape. This packet observes those owners; it does not
duplicate or change them.

### 1.5 Frozen inherited product and service prerequisites

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameCreationReadiness.ts` | 38 | `1dd39360063376c67a8a028742e11fdab769c3888bd6b6599f5999498ea7c1ac` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameBrowser.ts` | 1097 | `6bf4ad5e856cd38ea671218b1e9d928d51e04bcc1c054329a587fef7b9cd896c` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/characterCreator.ts` | 2772 | `bb6365ca79164a13467699d2c3142134b61f71a3560b0ef89f5f31cd3f15e20b` |
| `/home/tommaso/Dev/NeuroClient/app/src/api/gameDirectory.ts` | 961 | `7c302315a8da021fb7652baf09d2d5c9575cd82893fe15729a80a85968fe6560` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/characterSheet.ts` | 1266 | `9bdf076f1b1383e297143c044ff116b2f792c1ba1af994d29e731ebc6774ba0b` |
| `server/event_server.py` | 6978 | `eb1f6e891bc4cb149c8f054bb8ae36e4df7f2a7a7d47e6cc91af2a3e7394cdc5` |
| `server/game_directory/local_profiles.py` | 420 | `7ce82baee1b1b413c1a5b35467489c52eae53d59fabe583446ac21fb856e0ade` |

These authorities are inherited prerequisites only. No character-creation,
game-creation, backend, or gameplay correctness claim is added.

## 2. Exact causal finding

### 2.1 Installed wait behavior

In frozen `frames.js`, the injected wait loop:

1. calls `predicate()`;
2. stores the immediate result in `success`;
3. branches on `if (success)`;
4. calls `fulfill(success)` and returns without scheduling `next`;
5. later awaits `h.result` outside that branch.

An async predicate returns a Promise immediately. The Promise object is truthy
regardless of the Boolean it will resolve to. Promise assimilation means the
wait call eventually receives that one predicate's resolved Boolean, but a
resolved `false` does not cause another predicate invocation.

Ordinary `page.evaluate` has different semantics. The client evaluates one
function and Chromium uses `awaitPromise: true`; Node receives the resolved
serializable result. Explicit Node polling over `page.evaluate` therefore
tests a resolved Boolean rather than a Promise object.

### 2.2 First stale predicate: targeting open

After the mounted action bar exposes one enabled Move accessibility button,
the smoke focuses it and presses Enter. Its current async wait dynamically
imports `store.ts` and asks for:

- `targetingMode.type === "position_path"`;
- non-null targeting action;
- at least one valid target.

If the single evaluation resolves false, the installed wait still completes.
The smoke then reads `picking`, but only includes that object in the final JSON.
It never asserts its type, template, or target count. A smoke can therefore
report success with `picking.type === "none"` or with an empty/incorrect action.

### 2.3 Second stale predicate: targeting cancel

After recording `picking`, the smoke presses Escape. Its second async wait asks
whether `targetingMode.type === "none"`. A single resolved false again completes
without re-polling. No later assertion reads the cleared mode. The remaining
composition, start, bootstrap, error, and canvas checks do not establish that
the transient targeting authority was canceled.

### 2.4 One coherent seam

The two waits are not independent feature expansion. They form one exact
interaction receipt:

`none` before Move -> real Move `position_path` with valid targets -> `none`
after Escape.

Both mutations remain production-owned by `transitionTargeting`. The Tester
only waits for and records the resulting store state.

## 3. Required acceptance evidence

The final frozen smoke must require and report actual values for all of the
following:

1. `targetingTypeBeforeMove === "none"` immediately before Enter;
2. a bounded resolved-poll receipt for opening Move targeting, including actual
   `attempts` and `elapsedMs`;
3. `picking.type === "position_path"`;
4. `picking.template === "Move"`;
5. `picking.targetCount > 0`;
6. a bounded resolved-poll receipt after Escape, including actual `attempts`
   and `elapsedMs`;
7. an independent post-wait store read equal to
   `targetingTypeAfterEscape === "none"`;
8. all existing character, compose, start, bootstrap, mounted actor, canvas,
   request, console, page-error, and cleanup assertions unchanged.

No minimum attempt count is required. The open and cancel transitions may
lawfully settle before the first evaluation. The correctness boundary is that
Node tests the resolved value and the independent snapshots prove the exact
states.

## 4. First-red checker witness

### 4.1 Authorized checker edit

Tester may first edit only:

`/home/tommaso/Dev/NeuroClient/app/scripts/check-node-sources.mjs`.

Immediately after the existing accepted turn-burst rule, add a second explicit
target rule equivalent to:

```js
const realCharacterPath = resolve(
  "scripts/real-character-game-creation-live-smoke.mjs",
);
const realCharacterSource = readFileSync(realCharacterPath, "utf8");
if (/\.waitForFunction\s*\(\s*async(?:\s+function\b|\s*\()/u.test(realCharacterSource)) {
  failures.push(
    "scripts/real-character-game-creation-live-smoke.mjs: Promise-valued waitForFunction predicate is forbidden; use explicit resolved page polling.",
  );
}
```

Formatting may follow the existing file, but path, regex semantics, and exact
diagnostic are frozen. The rule reads only this named source. It must not scan
or fail the other 16 open occurrences.

### 4.2 Preserved checker behavior

The accepted turn-burst rule, recursive `.mjs` `node --check` traversal,
`vite.config.ts` diagnostics, aggregate failure behavior, and success summary
remain byte-preserved outside the new target block.

### 4.3 Natural first red

After fresh static approval of the checker-only identity, Tester runs exactly
once from NeuroClient root:

```text
npm --prefix app run node-sources:check
```

The sole accepted result is nonzero with the exact diagnostic from Section
4.1. No backend, Vite, browser, or product smoke starts. A syntax, TypeScript,
Vite-config, path, timeout, or other checker failure is not the accepted red.

## 5. Final Tester correction

The natural red releases only an edit to:

`/home/tommaso/Dev/NeuroClient/app/scripts/real-character-game-creation-live-smoke.mjs`.

The checker is frozen after first red.

### 5.1 File-local resolved poll helper

Add one file-local helper with the shape:

```js
async function waitForResolvedPageCondition(
  targetPage,
  evaluateCondition,
  timeoutMs,
  label,
  pollIntervalMs = 50,
) {
  // bounded resolved polling described below
}
```

The helper must:

1. use Node's monotonic `performance.now()`;
2. compute one absolute deadline for the entire wait;
3. keep only constant state: start, deadline, attempts, one timer, one result;
4. before each evaluation, reject if no time remains;
5. increment `attempts` once for each actual `page.evaluate` invocation;
6. race every `page.evaluate(evaluateCondition)` against a Node timer for the
   exact remaining budget;
7. clear that timer in `finally` for every evaluation outcome;
8. after the race settles, reject if the deadline is reached before accepting
   a truthy result;
9. return `{ attempts, elapsedMs }` only for a pre-deadline resolved truthy
   result;
10. for resolved false, delay by at most
    `min(pollIntervalMs, remaining budget)` and recheck the same deadline;
11. on stalled evaluation, repeated false, or late truth, throw exactly:
    `<label> did not resolve within <timeoutMs>ms`;
12. never start another poll after timeout.

`Promise.race` observes the losing evaluation. The smoke's existing outer
`finally` closes the browser, then stops Vite/backend and removes its fresh
runtime, canceling outstanding page work.

### 5.2 Open-targeting correction and evidence

Immediately before pressing Enter:

1. read the actual production store targeting type through one ordinary
   `page.evaluate`;
2. store it as `targetingTypeBeforeMove`;
3. require it equals `none`.

Replace only the first unsafe wait with a helper call using a 10,000 ms bound
and label `real-character Move targeting readiness`.

The page condition must dynamically import the existing store and return true
only when:

- type is exactly `position_path`;
- action is non-null;
- action `template_name` is exactly `Move`;
- valid target count is positive.

Retain the existing `picking` snapshot, then require its actual values satisfy
the same type/template/positive-count receipt.

### 5.3 Cancel-targeting correction and evidence

After the existing Escape press, replace only the second unsafe wait with a
helper call using a 10,000 ms bound and label
`real-character Move targeting cancellation`.

The condition remains the exact production store check that type is `none`.
After the helper returns, perform a second ordinary store evaluation, record
`targetingTypeAfterEscape`, and require it equals `none`.

### 5.4 Final summary

Add only these actual fields to the existing JSON summary:

- `targetingTypeBeforeMove`;
- `targetingReadyWait` with actual attempts/elapsed;
- existing `picking`;
- `targetingClearWait` with actual attempts/elapsed;
- `targetingTypeAfterEscape`.

The existing `picking` key is not duplicated or replaced by a success Boolean.

### 5.5 Byte-preserved inherited body

Outside the exact insertions/replacements above, preserve:

- owned runtime/backend/Vite/browser creation;
- empty-profile rejection and real premade-character flow;
- exact owned roster compose/start/bootstrap evidence;
- game setup and typed replication bootstrap;
- mounted controlled actor/body/action-bar receipt;
- nonblank canvas pixel sampling;
- Move accessibility-button discovery/focus/Enter and Escape inputs;
- failed-response, console-error, and page-error gates;
- failure screenshot behavior;
- browser, child-process, and runtime-root `finally` cleanup;
- all other helper functions and output fields.

## 6. Explicit exclusions and owner separation

This packet does not authorize:

- any production edit;
- changing `transitionTargeting`, action admission, targeting keyboard behavior,
  available actions, or Move semantics;
- changing character creation, game composition/start, bootstrap, rendering,
  canvas, or error policy;
- changing package scripts, Vite config, dependencies, Playwright, SDK, backend,
  generated models, schema, protocol, persistence, public contracts, or assets;
- a shared polling framework or utility module;
- scanning or fixing any other BUG-031 occurrence;
- moving, Jumping, path, animation, or clip-order behavior;
- direct store mutation, route interception, response fixture, mock, or API seed;
- a second smoke or an ambient service.

Tester owns both permitted files. Implementation remains unused.

## 7. Governed execution protocol

### 7.1 Gate A

Fresh isolated R1-R4 review must approve this exact plan identity. Coordinator
verifies public 4/4 before any Tester edit.

### 7.2 Checker first-red sub-gate

1. Tester edits only the checker as Section 4 specifies and runs nothing.
2. Freeze checker identity and diff; smoke remains 449 / baseline hash.
3. Fresh isolated static R1-R4 review plus Coordinator verification.
4. Run `npm --prefix app run node-sources:check` exactly once.
5. Accept only the sole exact Section 4.1 diagnostic.
6. Stop on every other result; no rerun or follow-up inspection.
7. Fresh isolated correction-release review plus Coordinator verification.

### 7.3 Final correction static sub-gate

1. Tester edits only the smoke as Section 5 specifies and runs nothing.
2. Freeze checker/smoke identities, complete baseline diff, and diff-check.
3. Fresh isolated combined R1-R4 review plus Coordinator verification.

### 7.4 One-shot green

After the combined static sub-gate closes:

1. from NeuroClient root, run focused app/src TypeScript exactly once:
   `./app/node_modules/.bin/tsc --noEmit -p ./app/tsconfig.json`;
2. only if zero, run `npm --prefix app run node-sources:check` exactly once;
3. only if zero, prove no matching real-character smoke, owned Vite, or owned
   event-server process is active;
4. start exactly one owned outer process session for
   `npm --prefix app run real-character-game-creation-live:smoke`;
5. the registered smoke itself must create exactly one fresh runtime, one
   dynamic-port standalone backend, one dynamic-port Vite, and one browser;
6. impose one 300-second outer wall-clock bound on that owned command session;
7. require exit zero and one final JSON with all Section 3 evidence plus every
   inherited smoke receipt;
8. any nonzero, timeout, malformed/missing evidence, unexpected error, or
   cleanup mismatch freezes immediately;
9. no rerun, alternate command/probe, debug, edit, formatter, workaround,
   dependency action, ambient service, or unrelated execution.

On every exit, allow the existing smoke `finally` to close the browser, stop
its Vite/backend, and remove only its own fresh runtime. The outer owner must
join/terminate only its recorded session if necessary, then prove:

- the smoke process and every recorded descendant are absent;
- the dynamic backend and Vite ports reported on success are closed;
- no matching Playwright/Chromium, real-character smoke, Vite, or owned
  event-server process remains.

The previous WP-008 retained evidence roots are outside this packet and must
not be reused or removed.

## 8. Owner and review workflow

1. Planner owns this plan only.
2. R1 correctness, R2 backend/runtime, R3 frontend/test, and R4
   scope/duplication/serialization review independently.
3. Coordinator verifies governance and public ledgers but casts no technical
   vote.
4. Tester performs the checker edit, checker first red, final smoke edit, and
   one-shot green only when individually released.
5. Implementation has no assignment.
6. Every changed frozen identity invalidates prior votes for that surface.
7. Findings route through Planner to the one affected Tester owner.

## 9. Complexity, contracts, and performance

The source rule adds constant file-read/regex work to an existing Tester
checker. The runtime helper uses O(1) state, at most one evaluation and one
timer in flight, and two waits bounded to 10 seconds each. It adds no product
runtime listener, timer, retry, cache, storage, allocation owner, or hot-path
cost.

No wire model, generated type, JSON representation, storage key, backend route,
request/response, serializer, public export, package command, dependency, or
schema changes.

The file-local helper is intentionally not generalized. A shared framework
would materially expand architecture and is forbidden.

## 10. Strict closure claim

Acceptance may claim only:

> BUG-031 Stage 2: the maintained real-character live smoke is statically
> guarded against Promise-valued `waitForFunction` predicates and explicitly
> observes resolved production store values for Move targeting open and Escape
> cancellation, while its inherited real-character product journey remains
> green.

It may not claim:

- a production fix;
- general Playwright readiness correctness;
- closure of the remaining 16 BUG-031 occurrences;
- Move targeting, keyboard, pathfinding, gameplay, animation, Pixi, character
  creation, game creation, backend, or replication correctness beyond the
  inherited prerequisite evidence;
- BUG-009, BUG-011, BUG-030, BUG-032, BUG-033, or full regression-ledger
  closure.

## 11. Mandatory Gate A review questions

Reviewers must answer every question against the exact frozen sources.

1. Does package.json directly register the selected real-character smoke?
2. Are there exactly two Promise-valued `waitForFunction` calls in that smoke?
3. Does frozen Playwright branch on the immediate Promise object before
   assimilating its eventual Boolean?
4. Can a resolved false complete that wait without a second predicate call?
5. Can the current first wait green with `picking.type` still `none` because
   `picking` is only reported, not asserted?
6. Can the current second wait green without a post-Escape `none` assertion?
7. Do both waits form one coherent none/open/none targeting receipt?
8. Does the checker rule read only the selected smoke and preserve WP-008?
9. Will the frozen stale source deterministically produce the exact first red?
10. Does first red require no backend, Vite, browser, or smoke?
11. Does ordinary page.evaluate return the async condition's resolved Boolean?
12. Does the helper use one monotonic deadline for each complete wait?
13. Is every evaluation bounded by its remaining budget with timer cleanup?
14. Are late truth, repeated false, and stalled evaluation all rejected?
15. Is actual pre-Enter targeting type observed and required to be none?
16. Does the open condition require exact position_path, Move, and targets?
17. Is the post-open picking object independently asserted and reported?
18. Does Escape use the real production keyboard/targeting owner?
19. Is post-Escape none independently re-read, asserted, and reported?
20. Do zero page/console/failed-response and all inherited assertions remain?
21. Does the selected smoke already own fresh runtime/backend/Vite/browser and
    real character/game prerequisites without ambient state?
22. Are two existing Tester files sufficient, with no package or production
    edit?
23. Is the one-shot tsc/checker/smoke protocol sufficient and bounded?
24. Does cleanup cover browser, child services, ports, PIDs, descendants, and
    the smoke-owned temporary runtime on every exit?
25. Is runtime/checker overhead test-only, constant-space, and bounded?
26. Does final checker green prove both selected async call shapes are absent?
27. Are the other 16 occurrences explicitly left open without an allowlist?
28. Are Move/Jump ordering, targeting production semantics, and product
    contracts unchanged?
29. Is there no duplicated validator, mapper, DTO, state authority, protocol,
    persistence, serialization, dependency, or shared framework?
30. Is there any concrete false-red, false-green, cleanup, scope, performance,
    contract, or human-decision blocker requiring rejection?

## 12. Review record

Gate A begins at public 0/4 on this exact plan identity. No review from WP-008
or any earlier plan carries forward.
