# Gameplay Regression Work Packet 008

## BUG-031 Stage 1: resolved turn-readiness polling in the turn-burst smoke

Date: 2026-08-10; Revision 3: 2026-08-11  
Planner owner: Planner  
Required public reviewers: R1 correctness, R2 backend/runtime, R3 frontend/test, R4 scope/duplication/serialization  
Execution owners: Tester only  
Production Implementation: unused / HOLD

---

## 0. Decision and packet boundary

The maintained `turn-burst:smoke` currently calls Playwright
`page.waitForFunction(async () => ...)` while waiting for the real client store
to reach `my_turn_input`.

In the installed Playwright runtime, `waitForFunction` calls the predicate and
tests the returned value for truthiness without first awaiting it. An `async`
predicate therefore selects the success branch on its first invocation because
its immediate `Promise` is truthy. Promise assimilation then waits for that one
evaluation to settle, but a resolved `false` returns from the call instead of
causing another poll. The smoke can leave its readiness boundary after one
false evaluation before the store has reached the state it claims to require.

WP-008 is a deliberately narrow BUG-031 Stage 1 packet. It owns exactly:

1. one targeted static regression rule in the existing Node-source checker;
2. one explicit resolved-polling correction in the existing turn-burst smoke;
3. actual character-prerequisite, readiness, and page-error evidence from the
   corrected smoke;
4. one governed static natural red and one governed product green.

Mutable files are limited to:

- `/home/tommaso/Dev/NeuroClient/app/scripts/check-node-sources.mjs`;
- `/home/tommaso/Dev/NeuroClient/app/scripts/turn-burst-smoke.mjs`.

No production, package, Vite, backend, SDK, generated, schema, asset, or second
smoke assignment exists.

The other eighteen currently inventoried `waitForFunction(async ...)`
occurrences remain explicitly open for later BUG-031 stages. This packet does
not claim that they are safe or repaired.

Excluded:

- general Playwright wrapper design;
- conversion of any other browser smoke;
- BUG-030 Studio navigation;
- BUG-032 ambient-service ownership outside this attempt's governed runner;
- turn-burst performance threshold redesign;
- event-sidebar behavior changes;
- game creation, turn scheduling, networking, rendering, or backend changes;
- any user/product decision.

### 0.1 Revision 2 governed green blocker

The first governed green attempt consumed exactly one focused TypeScript check,
one Node-source checker invocation, one fresh standalone runtime, one Vite, and
one turn-burst smoke invocation. TypeScript and the checker passed. The backend
reported HTTP 200 with `server_mode = "standalone"`; Vite reported HTTP 200.

The smoke stopped before game setup at the frozen immediate New Match click.
The fresh standalone profile lawfully contained no character, so production
rendered `[data-create-game]` disabled with title
`Create a character to start a match`. The click timed out after 30 seconds.
The corrected polling helper, observed store state, event burst, page-error
summary, and every later WP-008 receipt were unreached.

The attempt is fixture-precondition evidence only, not a BUG-031 behavioral
result. Owned Vite/backend/browser trees were stopped and ports were closed.
The retained evidence root
`/tmp/neurodragon-wp008-green-JGpsMv` must not be reused or removed by this
packet.

Fresh R1-R4 blocker review unanimously selected the smallest truthful
correction: the same turn-burst smoke must prove the empty profile, create one
premade character through the real production UI and exact real directory
request, close the real character sheet, prove New Match becomes enabled, and
then continue the already-frozen turn-burst path. Runner-side seeding, ambient
profile reuse, API mocks, direct store mutation, and production changes remain
forbidden.

---

## 1. Frozen identity

### 1.1 Program authorities

| Authority | Lines | SHA-256 | Role |
| --- | ---: | --- | --- |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/USER_REPORTED_GAMEPLAY_AND_PRODUCT_REGRESSION_LEDGER_2026-08-10.md` | 607 | `9ac0633322a2203222076a54bd2a8edb23c10e17b49b84562a77d971b922a805` | BUG-031 user/program receipt |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/CURRENT_GAMEPLAY_STABILIZATION_MANIFEST_2026-08-10.md` | 798 | `0048c7192773c2a0086a540fabda89023830408ad7ecaf9894c6e34e7529fe5b` | current accepted stabilization boundary |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_STATIC_CAUSAL_STUDY_AND_WORK_PACKET_001_2026-08-10.md` | 767 | `ede1cc4b074ed0bebc104f13197bf02b80ee9cca5311c804a9f29ef7f6d14eff` | current-source BUG-031 classification |

### 1.2 Mutable Tester baselines

| File | Lines | SHA-256 | Proposed owner |
| --- | ---: | --- | --- |
| `/home/tommaso/Dev/NeuroClient/app/scripts/check-node-sources.mjs` | 67 | `c8f79d24fda293636789c6d94930b878a9cfa302e9fa1c7abd287e463929e4bf` | Tester static gate |
| `/home/tommaso/Dev/NeuroClient/app/scripts/turn-burst-smoke.mjs` | 156 | `ddb3f145f778a5532a7551e035cf096ee52653e6158c9c58ac2e8d1be54177c5` | Tester runtime correction/evidence |

No production Implementation assignment exists in WP-008.

Revision 3 begins from this already-approved combined Tester state:

| File | Lines | SHA-256 | State |
| --- | ---: | --- | --- |
| `/home/tommaso/Dev/NeuroClient/app/scripts/check-node-sources.mjs` | 74 | `9f2be912ea3f805dac235bb3a63ed8d021422511a883ad91676cd1f225975052` | byte-frozen targeted checker |
| `/home/tommaso/Dev/NeuroClient/app/scripts/turn-burst-smoke.mjs` | 222 | `5e76c90ee7e107eb2f4ba867f2bf971ff89b06f008593f56aa3b001d6fa833de` | sole Revision 3 mutable Tester |

The current combined accepted-baseline diff is `+78/-5`: checker `+7/-0`,
turn-burst `+71/-5`.

### 1.3 Frozen runtime, product, package, and service authorities

| File | Lines | SHA-256 | Why frozen |
| --- | ---: | --- | --- |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/frames.js` | 1500 | `a0a5c3655b86edeb1e6acb8133d40769dda53c246340271251598dac5ff48594` | installed `waitForFunction` truthiness behavior |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/store.ts` | 431 | `b0c428f266cf3c23608143e3ee73fc048f82bfb0afb5ffee3e317b1aff859537` | claimed `clientState` readiness owner |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameBrowser.ts` | 1097 | `6bf4ad5e856cd38ea671218b1e9d928d51e04bcc1c054329a587fef7b9cd896c` | ordinary standalone game-browser entry |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameSetup.ts` | 2228 | `eba13f093bd5a8c6006e73d7b1918a1a1a9a7c64953adc20474d2e895baa17e1` | real create/start-match UI owner |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameCreationReadiness.ts` | 38 | `1dd39360063376c67a8a028742e11fdab769c3888bd6b6599f5999498ea7c1ac` | exact empty-profile New Match gate |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/characterCreator.ts` | 2772 | `bb6365ca79164a13467699d2c3142134b61f71a3560b0ef89f5f31cd3f15e20b` | real premade-character UI owner |
| `/home/tommaso/Dev/NeuroClient/app/src/api/gameDirectory.ts` | 961 | `7c302315a8da021fb7652baf09d2d5c9575cd82893fe15729a80a85968fe6560` | generated creation, hydration, selection owner |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/characterSheet.ts` | 1266 | `9bdf076f1b1383e297143c044ff116b2f792c1ba1af994d29e731ebc6774ba0b` | production-opened character-sheet close owner |
| `/home/tommaso/Dev/NeuroClient/app/scripts/real-character-game-creation-live-smoke.mjs` | 449 | `104216107f465e364ab35131de48ec4102bb471d78c36df7546b1709770a91d6` | maintained reference for the same fresh-profile UI prerequisite |
| `/home/tommaso/Dev/NeuroClient/app/package.json` | 165 | `36515d20ea94ebc0c49a47b79bd455fee0eddceea2eb5e52713163eff159d9e3` | existing checker and smoke registrations |
| `/home/tommaso/Dev/NeuroClient/app/vite.config.ts` | 235 | `7d70b9fae8cf5d4a8d38762865ac8f36adba1247721212fcb5b3d7455f247153` | owned frontend/proxy execution boundary |
| `/home/tommaso/Dev/NeuroClient/server.sh` | 19 | `fd4db2fc27366f963308a93dd6c07096566b8c58bb1515a4dfbc95e8e6f1a22a` | existing standalone backend launcher |
| `server/event_server.py` | 6978 | `eb1f6e891bc4cb149c8f054bb8ae36e4df7f2a7a7d47e6cc91af2a3e7394cdc5` | real standalone capability/game runtime |
| `server/game_directory/local_profiles.py` | 420 | `7ce82baee1b1b413c1a5b35467489c52eae53d59fabe583446ac21fb856e0ade` | fresh profile creation without character seeding |

The installed Playwright package version is frozen by the existing dependency
tree at `1.59.1`. No dependency action is authorized.

Every identity above must be re-matched at every public sub-gate. Existing
unrelated worktree changes belong to their owners and must not be attributed to
WP-008.

---

## 2. Current causal boundary

### 2.1 Maintained stale wait

The accepted original turn-burst baseline performed:

```js
await page.waitForFunction(async () => {
  const { store } = await import("/src/engine/store.ts");
  return store.getState().clientState === "my_turn_input";
}, undefined, { timeout: 30_000 });
```

The intended contract is: keep polling until the imported store reports
`my_turn_input`, or reject at the existing 30-second bound.

### 2.2 Installed runtime behavior

The frozen Playwright implementation at `frames.js:1241-1284`:

1. invokes the supplied predicate;
2. assigns the immediate result to `success`;
3. checks `if (success)`;
4. calls the result resolver immediately when that value is truthy;
5. later awaits the adopted result promise through `h.result`.

It does not await a predicate-returned promise before choosing whether to poll
again. The immediate result of an `async` function is a truthy `Promise`, so
the polling branch is never scheduled. JavaScript promise assimilation waits
for that single predicate promise to settle, but even a resolved `false` is
returned as the completed wait result. The defect is one-shot evaluation, not
an assertion that the asynchronous work itself is never awaited.

### 2.3 Consequence in the maintained smoke

On that original baseline, after the one-shot wait resolves false, the smoke
sleeps 250 ms and begins its
event burst. A fixed sleep is not the claimed state receipt. Depending on
startup timing, the script may run its later assertions before a real
player-turn state exists, or may pass only because the state happens to arrive
within that sleep.

The bug is in Tester authority. Production owns the client state; the smoke
owns waiting truthfully for it.

### 2.4 Why this stage is bounded

The selected occurrence is:

- one async predicate;
- one store condition;
- one already-bounded wait;
- one registered live smoke;
- independently executable with the existing standalone service topology.

No shared wrapper or broad conversion is needed to correct and guard this one
receipt.

---

## 3. Accepted receipts

### 3.1 First-red receipt: targeted static policy reaches the stale source

After only the Section 4 checker edit:

1. `node-sources:check` still syntax-checks every `.mjs` and Vite config;
2. its new targeted rule reads the maintained turn-burst source;
3. the exact forbidden async `waitForFunction` call remains present;
4. the command rejects exactly with a diagnostic containing:

   `scripts/turn-burst-smoke.mjs: Promise-valued waitForFunction predicate is forbidden; use explicit resolved page polling.`

5. no backend, Vite, browser, or smoke is started;
6. no other checker failure precedes or substitutes for the exact diagnostic.

This is a deterministic Tester-authority red. It releases no production work.

### 3.2 Green receipt: explicit resolved polling and real product state

On the frozen final Tester pair:

1. `node-sources:check` exits zero and therefore proves the targeted forbidden
   call is absent;
2. focused app TypeScript exits zero;
3. one owned standalone backend reports HTTP 200 and
   `server_mode = "standalone"` on its direct capability route;
4. one owned Vite becomes ready;
5. the registered turn-burst smoke runs exactly once;
6. the smoke proves New Match is initially disabled and the exact production
   `create-match-requirement` is visible on the fresh profile;
7. the smoke opens the real premade creator, fills the fixed name
   `Turn Burst Fixture`, and causes exactly one real
   `POST /api/directory/characters` response with a successful status;
8. the real creator detaches, exactly one selected character card bears that
   name, the requirement disappears, and New Match becomes enabled;
9. the production-opened character sheet is closed through its real control;
10. the explicit Node-side loop repeatedly calls `page.evaluate`;
11. each `page.evaluate` awaits the async dynamic import and Boolean result and
   is raced against the one monotonic overall deadline;
12. the loop returns only after the observed store value is exactly
   `my_turn_input` strictly before that deadline, or throws the exact timeout
   at 30 seconds, including when an evaluation stalls;
13. the final summary emits actual initial/final New Match state, exact
    character-request count/status, created-card count/name, poll attempts,
    elapsed time, observed state, and page-error count;
14. every inherited event-burst, render-window, entity-map, scene-sync, DOM,
    frame-gap, long-task, and sidebar assertion passes;
15. page-error count is zero;
16. smoke exits zero and owned service/browser processes are fully joined.

### 3.3 False-green exclusions

Green cannot be produced by:

- a Promise object being treated as readiness;
- a hard-coded `true` receipt;
- retaining the original fixed sleep as the authority;
- reading a test-authored shadow state;
- catching or suppressing the 30-second timeout;
- skipping the real create/start-match UI;
- reusing an ambient, retained, or preseeded profile;
- constructing or mocking a character response/request;
- directly mutating directory context, selected character, or store state;
- a character request count other than one;
- a created card not selected or not bearing the fixed name;
- leaving the empty-profile requirement mounted or New Match disabled;
- failing to close the production-opened character sheet;
- reusing an ambient backend or Vite;
- a page exception coexisting with the summary;
- changing production state, game setup, or event-sidebar behavior;
- running a different script or an unregistered helper.

---

## 4. Tester first-red static gate

### 4.1 Sole first-red edit

Tester edits only:

`app/scripts/check-node-sources.mjs`

After the existing `failures` declaration, it resolves and reads exactly
`scripts/turn-burst-smoke.mjs`. It tests the source with a whitespace-tolerant
pattern limited to an async first argument of `.waitForFunction`:

```js
const turnBurstPath = resolve("scripts/turn-burst-smoke.mjs");
const turnBurstSource = readFileSync(turnBurstPath, "utf8");
if (/\.waitForFunction\s*\(\s*async(?:\s+function\b|\s*\()/u.test(turnBurstSource)) {
  failures.push(
    "scripts/turn-burst-smoke.mjs: Promise-valued waitForFunction predicate is forbidden; use explicit resolved page polling.",
  );
}
```

The rule is intentionally target-specific for Stage 1. It does not scan or
silently bless the other known BUG-031 occurrences.

### 4.2 Frozen checker behavior

All existing syntax traversal, per-file `node --check`, Vite config diagnostic
handling, aggregate failure behavior, and success summary remain unchanged.

### 4.3 Natural-red execution

After static 4/4 approval of the checker-only identity, Tester runs exactly:

`npm --prefix app run node-sources:check`

once. The only accepted nonzero is the exact Stage 1 diagnostic in Section
3.1. Any syntax, TypeScript-node-config, path, timeout, or other checker error
freezes the packet.

---

## 5. Final Tester correction

After the governed natural red and a fresh 4/4 release review, Tester edits
only `app/scripts/turn-burst-smoke.mjs`. The checker remains byte-frozen.

Sections 5.1, 5.3, 5.4, and 5.5 describe the already-frozen 222-line Revision 2
correction. Revision 3 authorizes only the additional Section 5.2 prerequisite
and evidence on that identity.

### 5.1 Explicit resolved polling helper

Add one file-local helper after the existing executable body:

```js
async function waitForResolvedPageCondition(
  page,
  evaluateCondition,
  { timeoutMs, pollIntervalMs = 50, label },
) {
  const startedAt = performance.now();
  const deadline = startedAt + timeoutMs;
  const timeoutError = () => new Error(
    `${label} did not resolve within ${timeoutMs}ms`,
  );
  let attempts = 0;
  while (true) {
    const remainingMs = deadline - performance.now();
    if (remainingMs <= 0) throw timeoutError();
    attempts += 1;
    let timeoutId;
    let ready;
    try {
      ready = await Promise.race([
        page.evaluate(evaluateCondition),
        new Promise((_, reject) => {
          timeoutId = setTimeout(() => reject(timeoutError()), remainingMs);
        }),
      ]);
    } finally {
      if (timeoutId !== undefined) clearTimeout(timeoutId);
    }
    if (performance.now() >= deadline) throw timeoutError();
    if (ready) {
      return { attempts, elapsedMs: performance.now() - startedAt };
    }
    const delayMs = Math.min(
      pollIntervalMs,
      Math.max(0, deadline - performance.now()),
    );
    if (delayMs <= 0) throw timeoutError();
    await new Promise((resolve) => setTimeout(resolve, delayMs));
  }
}
```

The helper is deliberately local. It adds no shared framework or authority.
`page.evaluate` is the resolved-value boundary: Playwright resolves the async
browser function result before the Node loop tests it. `performance.now()`
provides one monotonic deadline. Every in-flight evaluation is observed by
`Promise.race`; its timer is cleared on settlement, a truthy result is rejected
if it arrives at or after the deadline, and no later poll is started after the
timeout wins. Browser closure in the smoke's existing `finally` cancels the
losing page work.

### 5.2 Deterministic real-character prerequisite

Immediately after the existing game-browser visible receipt and before the
current New Match click, add the following bounded real UI flow.

1. Bind `page.getByTestId("create-hosted-game")` as `newMatch` and
   `page.getByTestId("create-match-requirement")` as `createRequirement`.
2. Require `createRequirement` visible within 30 seconds.
3. Observe `initialCreateRequirementCount = await createRequirement.count()`
   and require exactly one.
4. Observe `initialNewMatchDisabled = await newMatch.isDisabled()` and throw
   unless it is `true`. This is mandatory freshness evidence, not a fallback.
5. Define one exact matcher:

   ```js
   const isCharacterCreateRequest = (request) => (
     request.method() === "POST"
     && new URL(request.url()).pathname === "/api/directory/characters"
   );
   ```

6. Install one request counter whose match is exactly
   `isCharacterCreateRequest(request)`.
7. Click the real `create-premade-character` control.
8. Require the real `custom-character-creator` visible within 30 seconds.
9. Fill `[data-custom-character-name]` with exactly `Turn Burst Fixture`.
10. Require `[data-character-create]:not([disabled])` visible.
11. In one `Promise.all`, arm `page.waitForResponse` with a 60-second bound and
    predicate `isCharacterCreateRequest(response.request())`, and click the
    real create control once.
12. Require the returned response `ok()` and record its actual status.
13. Require the creator detached within 60 seconds.
14. Locate `.game-browser-character.is-selected` filtered by the fixed name,
    require visible within 30 seconds, require its `strong` text exactly equals
    the fixed name, and record/require the filtered count equals exactly one.
15. Observe `remainingCreateRequirementCount = await createRequirement.count()`
    and require it equals zero.
16. Observe `finalNewMatchEnabled = await newMatch.isEnabled()` and throw
    unless it is `true`.
17. Require the production `character-sheet` visible within 30 seconds, click
    its first `[data-character-sheet-close]`, and require it detached within
    30 seconds.
18. Require `characterCreateRequestCount === 1` before continuing through the
    existing New Match click.

The URL matcher must parse the response/request URL and compare `pathname`
exactly. It may not use a broad substring that admits another endpoint.

The smoke must not parse or copy a character DTO. Production
`createPremadePersistentCharacter` remains sole request-shape/catalog/digest
authority; its generated client decode and `installCreatedCharacterSnapshot`
remain sole hydration/selection owners.

The request counter is installed before the create click and remains
observation-only. No route interception, fixture response, direct API call,
store write, or context mutation is permitted.

### 5.3 Exact call replacement

Replace only the current async `waitForFunction` block with:

```js
const turnReadinessWait = await waitForResolvedPageCondition(
  page,
  async () => {
    const { store } = await import("/src/engine/store.ts");
    return store.getState().clientState === "my_turn_input";
  },
  {
    timeoutMs: 30_000,
    label: "turn-burst player turn readiness",
  },
);
const observedTurnState = await page.evaluate(async () => {
  const { store } = await import("/src/engine/store.ts");
  return store.getState().clientState;
});
if (observedTurnState !== "my_turn_input") {
  throw new Error(
    `turn-burst readiness returned at ${String(observedTurnState)}`,
  );
}
```

Remove the following obsolete `await page.waitForTimeout(250);`. No fixed
sleep remains as readiness authority.

### 5.4 Page-error and actual evidence

Immediately after `browser.newPage`, before `addInitScript` and navigation:

```js
const pageErrors = [];
page.on("pageerror", (error) => pageErrors.push(error.message));
```

Before the final summary:

- append a failure when `pageErrors.length !== 0`, including the captured
  messages;
- emit actual `turnReadinessWait`, `observedTurnState`, and
  `pageErrorCount: pageErrors.length` fields in the existing JSON summary;
- emit actual `initialNewMatchDisabled`, `characterCreateRequestCount`,
  `characterCreateStatus`, `createdCharacterCardCount`,
  `characterFixtureName`, `finalNewMatchEnabled`,
  `initialCreateRequirementCount`, and
  `remainingCreateRequirementCount` fields.

No Boolean success substitute is permitted.

### 5.5 Frozen inherited behavior

Byte-preserve except for the exact changes above:

- init-script frame/long-task/mutation probes;
- ordinary root navigation;
- real game-browser, character creation, and game-setup clicks;
- 250-event burst construction;
- entities-map identity assertion;
- zero scene-sync assertion;
- raw-event hidden/visible windowing assertions;
- sidebar DOM bound;
- frame-gap and long-task thresholds;
- Events/Combat Log tab checks;
- browser `finally` cleanup;
- aggregate failures and exit semantics;
- package command registration.

---

## 6. No production algorithm or contract change

WP-008 changes no production code. In particular:

- `store.clientState` remains the readiness value;
- backend turn admission and scheduling are unchanged;
- game-browser/game-setup behavior is unchanged;
- no runtime polling loop is added to the product;
- no SDK, wire, persistence, schema, serializer, event, or UI contract changes;
- no dependency or package command changes;
- no production timer, listener, cache, retry, or allocation is introduced.

All added polling/listener/static work is Tester-only and bounded.

---

## 7. Governed execution protocol

### 7.1 Preconditions for every sub-gate

1. re-match the plan and all Section 1 identities;
2. confirm only authorized files differ at the current phase;
3. run `git diff --check` only as authorized read-only evidence;
4. prove ports 8000 and 5173 free before any service attempt;
5. prove no standalone backend, Vite, Playwright, Chromium, or turn-burst
   process is active;
6. never reuse runtime state or a service from another attempt.

### 7.2 First-red protocol

After checker-only static 4/4 plus Coordinator verification:

1. run `npm --prefix app run node-sources:check` exactly once;
2. require nonzero only at the exact Section 3.1 diagnostic;
3. run no backend, Vite, browser, smoke, or alternate probe;
4. stop immediately and freeze the result;
5. no edit, rerun, debug, formatter, workaround, or unrelated inspection.

### 7.3 Green protocol

After combined static 4/4 plus Coordinator verification:

1. from NeuroClient root run focused app TypeScript exactly once:
   `./app/node_modules/.bin/tsc --noEmit -p ./app/tsconfig.json`;
2. only if zero, run `npm --prefix app run node-sources:check` exactly once;
3. only if zero, prove ports 8000/5173 free and create a fresh disposable
   `/tmp` runtime root;
   the retained Revision 2 root and every ambient/developer profile are
   forbidden;
4. start exactly one owned standalone backend from NeuroClient root:
   `DND_LOCAL_PROFILE_RUNTIME_ROOT=<fresh> bash ./server.sh`;
5. probe exactly `http://127.0.0.1:8000/server/capabilities` for at most
   90 seconds, requiring HTTP 200 and `server_mode = "standalone"`;
6. only after backend readiness, start exactly one owned Vite and wait boundedly
   for its exact root readiness response;
7. run `npm --prefix app run turn-burst:smoke` exactly once;
8. require exit zero and every Section 3.2 receipt, including the exact
   empty-profile -> one real created character -> enabled New Match evidence;
9. any nonzero/unexpected result freezes immediately;
10. no rerun, alternate command/probe, debug, formatter, workaround, dependency
    action, or unrelated execution.

### 7.4 Cleanup

The smoke owns its browser via `finally`. The runner owns standalone and Vite.
On every exit:

1. interrupt only the owned Vite process tree;
2. interrupt only the owned standalone backend process tree;
3. join all owned descendants;
4. prove ports 8000/5173 closed;
5. prove every recorded owned PID and child absent;
6. prove no Playwright/Chromium/turn-burst process remains.

The disposable runtime may be removed only if the governed runner already owns
that exact path and removal is explicitly included in the attempt protocol.
Otherwise it remains for Coordinator inspection; no later cleanup is implied.

---

## 8. Role assignments and gates

### 8.1 Gate A

For Revision 3, R1-R4 independently review the complete revised frozen plan.
Unanimous approval plus Coordinator verification releases only the Section 5.2
prerequisite/evidence edit on top of the frozen 222-line smoke. It does not
repeat or reopen the completed checker/first-red work.

### 8.2 Tester first-red edit-only

Completed historical gate: Tester edited only `check-node-sources.mjs`; its
74-line identity is now frozen. No Revision 3 checker edit or first-red rerun is
authorized.

### 8.3 First-red release review

Completed historical gate: the exact targeted checker red released the
resolved-polling correction. That result remains causal evidence and is not
rerun in Revision 3.

### 8.4 Tester final edit-only

Tester edits only `turn-burst-smoke.mjs`, performs read-only diff/line/SHA
evidence, and runs nothing. The checker is frozen. Revision 3 permits only the
Section 5.2 prerequisite/evidence addition on top of the already-frozen
Sections 5.1, 5.3, 5.4, and 5.5 implementation.

Fresh R1-R4 combined static approval plus Coordinator verification releases
Section 7.3 exactly once.

### 8.5 Gate B

R1-R4 independently assess:

- same-policy red to green causality;
- actual resolved-polling evidence;
- actual fresh-profile/real-character prerequisite evidence;
- inherited turn-burst behavior;
- page-error truth;
- owned standalone/Vite/browser cleanup;
- Tester-only scope and strict Stage 1 claim.

At public unconditional 4/4 plus Coordinator verification, Gate B closes
automatically under standing policy.

---

## 9. Scope, duplication, serialization, and performance

### 9.1 Scope

Two existing Tester files only. No production owner is assigned.

The extra Revision 3 edit remains inside the already-owned turn-burst smoke;
the maintained real-character smoke is reference authority only and remains
byte-frozen.

### 9.2 Duplication

The helper is intentionally file-local because only one occurrence is in this
stage. Creating a shared polling framework for unresolved future scripts would
expand authority and is forbidden.

The static rule reuses the existing Node-source checker rather than adding a
new package command or checker file.

### 9.3 Serialization/contracts

No product payload or stored representation changes. The summary adds only
test-process evidence fields.

### 9.4 Complexity

The final wait uses one monotonic 30-second deadline, races every in-flight
evaluation against the remaining budget, and polls at 50 ms:

- worst-case evaluations: approximately 600;
- each evaluation reads one already-loaded module/store state;
- a stalled evaluation cannot prevent the exact overall timeout;
- a truthy evaluation settling at or after the deadline is not admitted;
- each evaluation timer is cleared and every inter-poll delay is clamped to
  the remaining budget;
- transient space: O(1), excluding bounded page-error messages;
- product hot-path cost: zero;
- no retry after timeout.

### 9.5 Open BUG-031 debt

This packet deliberately does not edit or approve the other known occurrences
in:

- `hud-rpg-smoke.mjs`;
- `multi-character-live-smoke.mjs`;
- `real-character-game-creation-live-smoke.mjs`;
- `live-subjective-actions-smoke.mjs`;
- `hosted-game-smoke.mjs`;
- `replication-smoke.mjs`;
- `live-shove-presentation-smoke.mjs`;
- `inventory-panel-smoke.mjs`.

Their exact inventory must be refreshed before a later stage; this packet does
not freeze their current count as a permanent allowlist.

---

## 10. Closure claim

If and only if Gate B closes, WP-008 may claim:

> BUG-031 Stage 1 is guarded for the maintained turn-burst smoke: its player-
> turn readiness no longer uses a Promise-valued Playwright wait predicate; an
> existing static checker rejects recurrence in that script; the corrected
> smoke creates its isolated character prerequisite through the real UI/API,
> observes the real store at `my_turn_input`, reports actual prerequisite,
> polling, and page-error evidence, and preserves its inherited event-burst
> assertions.

Do not claim:

- full BUG-031 closure;
- that the other async predicates are fixed or safe;
- a Playwright dependency fix;
- a shared polling framework;
- general browser-smoke readiness correctness;
- backend/game creation/turn-scheduling correctness beyond the one prerequisite;
- general character-creation correctness or coverage;
- event-sidebar or performance redesign;
- BUG-030 or BUG-032 closure;
- any production behavior change.

---

## 11. Mandatory Gate A reviewer questions

Every reviewer must answer all questions with source-backed evidence:

1. Is `turn-burst-smoke.mjs` registered directly as `turn-burst:smoke`?
2. Did its accepted original readiness boundary use an async first argument to
   `page.waitForFunction`, while the frozen 222-line correction removes it?
3. Does the frozen Playwright implementation test the immediate predicate
   Promise for truthiness before awaiting it, choose the success branch once,
   and then return its single resolved value without re-polling false?
4. Is a JavaScript Promise truthy even when it later resolves false?
5. Could the original 250 ms sleep substitute for an observed
   `my_turn_input` receipt?
6. Is the targeted checker regex sufficient for the accepted original arrow
   form and an `async function` form without scanning unrelated scripts?
7. Does first red arise deterministically from the stale source rather than
   backend/browser timing?
8. Does the first-red protocol run no service or smoke?
9. Does `page.evaluate(async () => ...)` return the resolved Boolean to the
   Node-side helper before the helper tests it?
10. Does one monotonic deadline race every in-flight evaluation, clamp every
    delay, and reject a late truthy result?
11. Does a stalled evaluation or repeated false result reject with the exact
    distinct timeout instead of returning a false readiness receipt?
12. Is the original store/client-state condition preserved exactly?
13. Is the obsolete 250 ms sleep removed as readiness authority?
14. Are prerequisite counts/status/state, attempts, elapsed time, observed turn
    state, and page-error count actual observations in the final summary?
15. Is the page-error listener installed before init script/navigation and
    required empty before success?
16. Are all inherited burst/performance/sidebar assertions preserved?
17. Is the existing checker behavior preserved apart from one targeted policy?
18. Do two existing Tester files suffice without package or production edits?
19. Is the standalone backend the truthful service topology for this existing
    create/start-match smoke?
20. Is direct `/server/capabilities` HTTP 200 plus standalone mode the correct
    pre-Vite backend readiness receipt?
21. Are tsc, checker, one backend, one Vite, and one registered smoke sufficient
    and bounded for green?
22. Does cleanup cover browser, Vite, backend, ports, PIDs, and children?
23. Is runtime overhead confined to the Tester and bounded O(1) state?
24. Does the strict claim leave every other BUG-031 occurrence open?
25. Is there any false-red, false-green, duplication, serialization, cleanup,
    scope, or human-decision blocker?
26. Does fresh standalone initialization create only a profile and no selected
    character, making the consumed disabled New Match result truthful?
27. Does production itself expose the premade creator in an empty profile and
    own the exact catalog-derived creation request?
28. Does the exact successful POST plus one selected named card, absent
    requirement, and enabled New Match prove the prerequisite without parsing
    or fabricating a character DTO?
29. Is the real character sheet closed before New Match so it cannot intercept
    the inherited click?
30. Does the retry use a brand-new runtime while retaining and forbidding the
    consumed evidence root?

Any unresolved question is `CHANGES_REQUIRED`, not conditional approval.
