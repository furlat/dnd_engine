# Gameplay Regression Work Packet 005

## BUG-022: pre-try browser-storage startup recovery

Status: **REVISION 2 DRAFT FOR GATE A REVIEW — NO EDIT OR EXECUTION AUTHORIZED**

Date: 2026-08-10

Revision: 2

Owner: Planner / External Reviewer 1

This packet is inside the already authorized BUG-001--BUG-034 gameplay-
regression program. It follows the completed read-only BUG-011 source-boundary
segmentation study. That study proved that ordered Move/Jump Step projection is
already sound, while generic forced-movement/teleport terminal reconciliation
cannot be added safely without new producer authority. BUG-011 therefore
remains fail-closed and is not part of this packet.

The next already-authorized bounded seam is BUG-022. NeuroClient currently
invokes the presentation persistence hard-cut before the startup `try`. A
synchronous browser `Storage` access failure can reject `init()` before the
existing recoverable startup UI owns the error. This packet closes only that
pre-try admission gap using the existing internal startup failure surface.

Revision 2 adds only two existing-diagnostic assertions to the browser proof:
the denied page must report an empty startup-stage list and zero presentation-
bundle fetches. This prevents a misplaced later catch from passing after fonts,
pretext, or presentation preparation already began. It changes no production
algorithm, file boundary, service protocol, or claim.

Approval of this document authorizes no edit, typecheck, browser, Vite,
backend, smoke, formatter, or other execution. Progression requires isolated
R1--R4 unanimous approval of one exact frozen identity plus Coordinator
governance verification.

---

## 1. Frozen authority and baseline identity

### 1.1 Program authorities

| Authority | Lines | SHA-256 |
| --- | ---: | --- |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/USER_REPORTED_GAMEPLAY_AND_PRODUCT_REGRESSION_LEDGER_2026-08-10.md` | 607 | `9ac0633322a2203222076a54bd2a8edb23c10e17b49b84562a77d971b922a805` |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/CURRENT_GAMEPLAY_STABILIZATION_MANIFEST_2026-08-10.md` | 798 | `0048c7192773c2a0086a540fabda89023830408ad7ecaf9894c6e34e7529fe5b` |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_STATIC_CAUSAL_STUDY_AND_WORK_PACKET_001_2026-08-10.md` | 767 | `ede1cc4b074ed0bebc104f13197bf02b80ee9cca5311c804a9f29ef7f6d14eff` |
| accepted WP-004 plan | 641 | `e05200a2d19446b5ddcfccb5d2d1fb243853871bec6eedeaafc91ffd810ec731` |

The regression ledger classifies BUG-022 as live because presentation
persistence reads/removes browser storage before the main startup `try`.
`Storage.getItem`, `removeItem`, or the storage-area getter itself may throw a
`SecurityError`, preventing the application from reaching its existing
recovery UI.

The stabilization manifest says a deterministic current red is required
before expanding production scope. This packet provides that red first,
through the existing registered persistence-cut smoke, before releasing the
one-file production edit.

### 1.2 Authorized NeuroClient production surface

Repository: `/home/tommaso/Dev/NeuroClient`

| File | Lines | SHA-256 |
| --- | ---: | --- |
| `app/src/main.ts` | 610 | `cd393f9820e7e7cf84da291b490b6b88c4e338e9bb2cb89483e4a2b27f8704bc` |

Implementation may edit exactly this file and no other file.

### 1.3 Authorized Tester surface

| File | Lines | SHA-256 |
| --- | ---: | --- |
| `app/scripts/presentation-persistence-cut-smoke.mjs` | 189 | `4acb3a49301b0042c58a61f6aa1aba47c28ffa338d9b20809235ace5edd8fd2d` |

Tester may edit exactly this existing registered smoke and no other file.

### 1.4 Frozen supporting authorities

These files are read-only proof authorities and must remain byte-identical:

| File | Lines | SHA-256 |
| --- | ---: | --- |
| `app/src/engine/presentationPersistenceCut.ts` | 132 | `c133c3d55ad62575d7619e6a365edd6ddca5e6076be8354da94dc06d6c4d2d15` |
| `app/src/render/presentationLedger.ts` | 1082 | `49bbaffce6dcbd9d4f4ad7bcb8bda039dc02b2cab283d62dcb36b4047e4d6300` |
| `app/src/render/presentationDiagnostics.ts` | 1264 | `4271e3b7711b8964212f9d0994877768c386c1ac359b476f5c3b94d3d8233f69` |
| `app/src/errorText.ts` | 109 | `5d64b37c7c0281c8ec228d30a73d82a6c50628126f5b2e8c96c203bcf15fa77f` |
| `app/src/render/presentationBundleBootstrap.ts` | 362 | `439ef047b972d9ceb538c1ecc298a354f782dfa36c5358443bffc5ea38c92cfa` |
| `app/src/performance/startupTiming.ts` | 155 | `415935b9555d377cc791c152d7d64c1bf69170e81bfea94dcfc4d7c9cea17ae7` |
| `app/index.html` | 15 | `06d0f1e2a0be03f19ce4db213fa79929063f09feff201f09a9d30dc9b2025baf` |
| `app/scripts/startup-transport-failure-smoke.mjs` | 164 | `279c7cd8b23d162016cae89b44c5be2422ef8cd2efa9b09535f781d6a0e94c61` |
| `app/vite.config.ts` | 235 | `7d70b9fae8cf5d4a8d38762865ac8f36adba1247721212fcb5b3d7455f247153` |
| `app/package.json` | 165 | `36515d20ea94ebc0c49a47b79bd455fee0eddceea2eb5e52713163eff159d9e3` |

`app/package.json` and several unrelated NeuroClient files are already dirty in
the shared worktree from accepted earlier packets. Their frozen identities,
not clean `HEAD`, are authoritative. No owner may normalize, revert, or fold
those changes into WP-005.

---

## 2. Exact problem and current causal path

### 2.1 Maintained persistence admission

`initializePresentationPersistenceCut` is the sole startup coordinator for
three cue-shaped evidence stores:

- session presentation ledger;
- session frame archive;
- local presentation fault history.

The coordinator intentionally inspects the top-level envelope identity before
either owner decodes nested rows. It deletes only incompatible maintained keys,
clears the in-memory connector cache when invalidation requires authenticated
bootstrap, then initializes the two persistence owners.

This authority is correct and remains frozen. The packet must not duplicate
its descriptor list, parse its envelopes, broaden cleanup, or change its
one-shot decision.

### 2.2 Uncaught startup boundary

Current `main.ts` begins `init()` with:

1. `initializePresentationPersistenceCut()`;
2. font/pretext/Pixi initialization;
3. scene/UI shell construction;
4. only then the existing main startup `try` around presentation bundle,
   directory, match bootstrap, and gameplay installation.

The persistence call is therefore outside every startup recovery catch. Its
descriptor scan invokes `window.sessionStorage`/`window.localStorage` and
`getItem`. If an incompatible descriptor exists, it later invokes
`removeItem`. Either the area getter or method may synchronously throw a
browser `DOMException` named `SecurityError`.

Because `init()` is invoked without an outer `.catch`, the rejection becomes a
page error. `showStartupFailure` is never called, no copyable diagnostic panel
is mounted, and the user sees a blank/incomplete application.

### 2.3 Existing recovery surface is sufficient

`app/index.html` provides `#ui-root` before `main.ts` executes. The existing
`showStartupFailure` function:

- mounts a visible failure panel into that root;
- produces the existing `neuroclient.startup-failure.v1` diagnostic value;
- preserves error name, message, stack, cause, location, user agent,
  presentation bootstrap state, and startup timing;
- provides copy, download, and reload controls;
- starts no empty-grid or procedural fallback.

It is safe to call this function before fonts, Pixi, scene, directory, backend,
or presentation runtime initialization. The function uses already imported
pure/in-memory diagnostics and requires no storage access.

### 2.4 Storage writes are not this uncaught seam

The ledger and diagnostic owners already catch their ordinary load/write
failures and retain bounded in-memory evidence. This packet does not change
that policy. Its production change guards only the coordinator call whose
top-level identity scan and incompatible-key removal currently escape.

The new test covers the two concrete uncaught method boundaries:

- managed-key `getItem` denial during preflight;
- maintained incompatible-key `removeItem` denial during scoped cleanup.

The same production catch also owns a `SecurityError` thrown by retrieving the
storage area itself because the entire coordinator call is inside the guard.

---

## 3. Accepted boundary and objective

### 3.1 Exact accepted inputs

Two fresh browser pages, each loading the ordinary NeuroClient root before any
backend request:

1. `getItem` denial:
   - patch only `Storage.prototype.getItem` for the maintained presentation
     ledger key;
   - throw `new DOMException(..., "SecurityError")`;
   - leave unrelated storage methods and keys unchanged.
2. `removeItem` denial:
   - seed only the maintained presentation ledger key with an incompatible
     top-level value before application startup;
   - patch only `Storage.prototype.removeItem` for that same key;
   - throw `new DOMException(..., "SecurityError")`;
   - leave reads, other keys, and other methods unchanged.

These are ordinary browser-origin failures at the existing maintained
persistence boundary. The test must not import or call `showStartupFailure`,
author a replacement startup promise, or invoke the coordinator directly for
these two cases.

### 3.2 Exact required output

For each case, ordinary `main.ts` startup must:

- catch the exact thrown `SecurityError` synchronously;
- perform no font, pretext, Pixi, scene, directory, or backend startup after
  the failed persistence admission;
- mount exactly one existing startup-failure panel;
- identify the cause to the user as browser storage unavailability;
- state truthfully that startup stopped and storage access must be restored
  before reload;
- include the exact `SecurityError` name/message in the existing structured
  diagnostics;
- retain the existing copy, download, and reload controls;
- create no canvas, game browser, fallback grid, storage shim, retry loop, or
  substitute in-memory persistence coordinator;
- report an empty `startup_timing.stages` array in the existing diagnostic
  payload;
- report `presentation.actualFetchCount === 0` in that payload;
- generate no uncaught page error.

### 3.3 Existing success behavior

When the coordinator succeeds:

- its call remains the first operation in `init()` before font loading;
- the returned decision remains the value compared with the later
  authenticated-bootstrap acknowledgement;
- valid current envelopes remain preserved;
- incompatible maintained keys remain narrowly invalidated;
- unrelated local/session keys and the run ID remain preserved;
- the normal application follows the existing font/Pixi/UI/startup path.

### 3.4 Claim boundary

This packet closes only the pre-try presentation-persistence `SecurityError`
startup failure. It does not claim:

- browser storage becomes available automatically;
- a denied origin can delete or repair inaccessible data;
- all product storage users are migrated to one new abstraction;
- quota failures during later best-effort evidence persistence are fatal;
- stale principal/profile cleanup beyond existing BUG-023 behavior;
- Studio document-history storage semantics;
- service-worker, IndexedDB, cache, cookie, or filesystem recovery;
- backend availability, gameplay, presentation execution, or mounted pixels.

---

## 4. Tester-first algorithm

### 4.1 File and placement

Tester edits only
`app/scripts/presentation-persistence-cut-smoke.mjs`.

Preserve every inherited assertion. Append the startup-denial proof only after
the existing direct-coordinator cut, envelope identity, unrelated-key,
one-shot, reload, and current-envelope assertions have passed.

### 4.2 Case-local browser helper

Add one local helper in the smoke, for example
`assertDeniedStorageStartupRecovery`, which accepts only:

- the operation discriminator `"getItem" | "removeItem"`;
- the maintained ledger key;
- the expected operation label for failure evidence.

For each call it must:

1. create a fresh browser page;
2. attach a page-error listener before navigation;
3. attach an API-request recorder before navigation;
4. install one `addInitScript` before navigating to `baseUrl`;
5. for `removeItem` only, seed the maintained ledger key with an incompatible
   JSON value using the original unpatched setter;
6. retain the exact original method and patch only the selected method;
7. throw a `DOMException` named `SecurityError` only when the exact maintained
   ledger key is accessed through that method;
8. navigate to the ordinary application root with `domcontentloaded`;
9. wait a fixed bounded interval for `[data-startup-failure="true"]`, catching
   the locator timeout only to produce the smoke's own exact assertion;
10. inspect the real mounted panel and structured diagnostic JSON;
11. close the page in a case-local `finally`.

The helper must not restore the patched prototype because the page is
destroyed. It must not patch a browser context shared with the inherited
direct-coordinator case.

### 4.3 Required runtime assertions

For both operation cases, require:

- exactly one startup-failure panel;
- title text exactly identifies `Browser storage unavailable`;
- explanation says required browser storage could not be accessed, startup
  stopped cleanly, and the user should restore access and reload;
- diagnostic schema equals `neuroclient.startup-failure.v1`;
- diagnostic `error.name === "SecurityError"`;
- diagnostic message contains the case-specific denial marker;
- diagnostic `startup_timing.stages` is an empty array;
- diagnostic `presentation.actualFetchCount === 0`;
- one copy diagnostics control;
- one download JSON control;
- one reload control;
- zero `[data-testid="game-browser"]` nodes;
- zero canvas elements;
- zero `/api/` requests;
- zero uncaught page errors.

Return actual observed evidence from each case. The final smoke summary must
include operation, panel count, diagnostic error name, startup stage names,
presentation fetch count, API request count, canvas count, and page-error count
rather than hard-coded booleans.

### 4.4 Natural first red

Run the `getItem` case first.

On unchanged production:

1. every inherited persistence-cut assertion passes;
2. the fresh page invokes ordinary `main.ts`;
3. the first managed-key `getItem` throws the injected `SecurityError`;
4. that call is outside the current startup `try`;
5. `init()` rejects and a page error is observed;
6. no startup-failure panel appears;
7. the smoke's bounded panel wait ends;
8. the first new assertion fails with the exact boundary:
   `getItem storage denial escaped startup recovery UI`.

No backend, font, Pixi, fixture, stale-envelope, or coordinator import failure
may substitute for this red. If the existing inherited portion fails, the
panel appears unexpectedly, a different error occurs, or the exact first-red
message is not produced, stop and freeze the result as a blocker.

The `removeItem` case is green-only. It must not be claimed reached during the
natural red.

### 4.5 No duplicated authority

The browser fixture may name the already public maintained ledger storage key
which the existing smoke already owns. It must not copy:

- the coordinator descriptor list;
- envelope validation;
- key invalidation policy;
- persistence owner initialization;
- startup failure UI construction;
- error serialization;
- startup sequencing.

The fixture creates only browser failure conditions and observes production
output.

---

## 5. Production algorithm

### 5.1 Guard the existing coordinator call

Implementation edits only `app/src/main.ts`.

At the beginning of `init()`:

1. declare `persistenceCut` with the exact return type of
   `initializePresentationPersistenceCut`;
2. invoke the existing coordinator inside a narrow synchronous `try`;
3. on any thrown value:
   - log through the same `NeuroClient startup failed:` owner used by the later
     startup catch;
   - call the existing `showStartupFailure` with the exact thrown value;
   - return immediately from `init()`;
4. continue to `game_ui_fonts` only when the coordinator returned normally.

Do not move the main startup `try`, reindent the application, attach a second
`init().catch`, or wrap unrelated font/Pixi work. The narrow guard preserves
the one causal boundary this packet proves.

### 5.2 Storage failure classifier

Add one private pure predicate in `main.ts`, for example
`isBrowserStorageUnavailable(error)`.

It must return true only when:

- the value is an `Error`/`DOMException`; and
- its exact `.name` is `SecurityError` or `QuotaExceededError`.

`QuotaExceededError` is included only for truthful UI classification if a
browser reports a maintained startup storage denial under that standard name.
It does not change later best-effort quota policy.

Do not classify by message substring. Do not wrap or replace the original
error; structured diagnostics must retain its exact name, message, stack, and
cause.

### 5.3 Truthful UI copy

Extend only the existing `showStartupFailure` title/explanation selection:

1. backend transport errors retain their current exact title and explanation;
2. browser storage errors use the title `Browser storage unavailable`;
3. their explanation states that NeuroClient could not access required browser
   storage during startup, gameplay/presentation startup stopped cleanly, and
   storage access should be restored before reload;
4. every other error retains the current generic presentation/game startup
   title and explanation byte-for-behavior.

The existing panel DOM shape, dataset attributes, diagnostics, copy/download
buttons, reload button, styles, and event handlers remain unchanged.

### 5.4 No fallback or cleanup invention

The failure branch must not:

- call `localStorage.clear()` or `sessionStorage.clear()`;
- retry the coordinator;
- swallow the failure and continue with empty evidence;
- install mock storage;
- mutate any maintained or unrelated key;
- start Pixi, scene, directory, backend, presentation, or gameplay;
- manufacture an authenticated-bootstrap acknowledgement;
- alter the coordinator's module-level `decision` or pending flag.

A denied origin cannot be truthfully repaired by application code. The correct
receipt is a clean stopped startup with actionable diagnostics and reload.

---

## 6. Red-to-green discrimination

### 6.1 Unchanged production

The frozen Tester must establish:

- inherited persistence behavior remains green;
- the injected managed-key `getItem` error is a real `SecurityError`;
- ordinary root startup is used;
- no panel is mounted;
- an uncaught page error is observed;
- the exact new assertion is the first red.

### 6.2 Correct production

With the one-file production change:

- the same injected `getItem` error is caught before font/Pixi/network startup;
- one truthful storage failure panel appears;
- structured diagnostics preserve `SecurityError`;
- structured diagnostics prove zero startup stages and zero presentation
  bundle fetches;
- no page error, API request, game browser, or canvas appears;
- the separate incompatible-key `removeItem` case proves the same boundary;
- inherited valid/incompatible/current envelope behavior remains green.

### 6.3 False greens excluded

The test cannot turn green through:

- direct invocation of `showStartupFailure`;
- direct invocation of a new exported helper;
- suppressing or removing the injected error;
- globally disabling storage use;
- accepting a generic unrelated startup failure panel;
- allowing Pixi/backend startup before displaying the panel;
- swallowing a page error;
- skipping the remove case;
- hard-coding summary booleans.

### 6.4 Preserved success path

The existing inherited smoke continues to prove:

- no persistence owner reads storage at module evaluation;
- the coordinator is the sole initialization owner;
- invalidation is limited to the three maintained cue-shaped keys;
- the run ID and unrelated keys survive;
- no unauthenticated network request occurs during cut;
- connector cache clearing occurs only for recovery-required invalidation;
- current envelopes survive reload;
- the coordinator remains one-shot/idempotent.

---

## 7. Owner sequence and execution protocol

### 7.1 Gate A

R1--R4 independently review this exact plan identity. Approval authorizes no
edit or execution.

### 7.2 Tester edit-only release

After unanimous Gate A plus Coordinator verification:

- Tester edits only
  `app/scripts/presentation-persistence-cut-smoke.mjs`;
- Tester runs nothing;
- Tester returns exact diff, line count, and SHA-256;
- production, package, and every other test remain frozen.

The changed Tester identity then receives fresh isolated R1--R4 static review
plus Coordinator verification.

### 7.3 One-shot natural first red

After the Tester sub-gate opens, Tester runs exactly:

1. from `/home/tommaso/Dev/NeuroClient`:
   `./app/node_modules/.bin/tsc --noEmit -p ./app/tsconfig.json` once;
2. only if zero, prove port 5173 is free and no existing Vite owner exists;
3. start one owned `npm --prefix app run dev` process;
4. use one bounded Vite readiness probe;
5. run exactly once:
   `npm --prefix app run presentation-persistence-cut:smoke`;
6. require the inherited cases to pass and the exact natural red
   `getItem storage denial escaped startup recovery UI`;
7. stop immediately after the red;
8. interrupt/join only the owned Vite process;
9. prove port 5173, the owned PID, and its children are closed.

No backend is started. No rerun, edit, alternate command/probe, debug,
formatter, workaround, or unrelated inspection is allowed.

Any compiler failure, inherited-smoke failure, Vite failure, unexpected pass,
different red, leak, or teardown mismatch freezes as a blocker.

### 7.4 Implementation edit-only release

Only after fresh R1--R4 approval of the exact natural red plus Coordinator
verification:

- Implementation edits only `app/src/main.ts`;
- Implementation runs nothing;
- Implementation returns exact diff, line count, and SHA-256;
- Tester and package remain frozen.

The combined two-file identity then receives fresh isolated R1--R4 static
review plus Coordinator verification.

### 7.5 One-shot green

After the combined sub-gate opens, Tester runs exactly the same bounded
protocol:

1. focused app/src TypeScript command once;
2. free-port preflight;
3. one owned Vite and bounded readiness;
4. the registered persistence-cut smoke once;
5. require exit zero with all inherited assertions plus both storage-denial
   cases and actual-evidence summary;
6. always stop/join only owned Vite and prove PID/children/port closed.

No backend, rerun, debug, alternate path, build, full suite, install, cleanup,
or formatter is authorized.

### 7.6 Gate B

The identical-test natural red and green result, final identities, focused
compiler result, runtime summary, and teardown evidence receive fresh isolated
R1--R4 review plus Coordinator verification. Automatic technical closure is
allowed only at unconditional 4/4 on the exact frozen surface.

---

## 8. Performance, duplication, and serialization bounds

### 8.1 Runtime cost

Successful startup adds one narrow `try` boundary and no new work. Failure adds
one constant-time error classifier before rendering the existing panel.

There is:

- no extra storage read/write;
- no retry;
- no scan;
- no timer, worker, RAF, queue, listener, or retained cache;
- no backend/network call;
- no persistent allocation.

### 8.2 Authority ownership

Authority remains single-owned:

- `presentationPersistenceCut.ts` owns descriptors, envelope identity,
  invalidation, and owner initialization;
- `main.ts` owns startup admission and recovery UI;
- `errorText.ts` owns structured error serialization;
- ledger/diagnostics owners retain their existing later best-effort behavior;
- the browser smoke only injects failure and observes output.

No second coordinator, descriptor table, storage adapter, recovery state
machine, or error serializer is introduced.

### 8.3 Serialization/public contract

The packet adds no:

- storage key or envelope field;
- JSON schema/version;
- persisted value;
- DTO or public API;
- backend route/model;
- SDK/generated type;
- package dependency/script;
- browser protocol;
- diagnostic schema change.

The existing diagnostic schema remains `neuroclient.startup-failure.v1`.

---

## 9. Explicit non-goals

This packet does not:

- resume or modify BUG-011;
- add a movement/settlement contract;
- alter Move, Jump, ForcedMove, ClipQueue, journal, or scene behavior;
- fix BUG-023 stale-principal policy beyond its current behavior;
- migrate action-bar, HUD, combat-history, Studio-history, or directory identity
  storage;
- make unavailable storage available;
- delete inaccessible or unrelated storage;
- add service worker/IndexedDB/cache recovery;
- test backend startup, gameplay, mounted Pixi pixels, or a live match;
- run the full check/build/verify suites;
- address the advisory full-suite collection or authoring blockers;
- normalize accepted prior dirty worktree changes.

Any requirement for another production file, second test file, package change,
storage abstraction, schema change, backend, or public contract stops the
packet and returns to Planner.

---

## 10. Stop/freeze conditions

Stop without workaround if:

1. any frozen identity differs before its owner begins;
2. Tester needs a second file or new package command;
3. the current smoke cannot inject an exact managed-key `SecurityError` in a
   fresh page without affecting inherited cases;
4. unchanged production does not reach the exact first red;
5. another storage user fails before the coordinator and owns the observed
   page error;
6. the UI root is unavailable at the failure boundary;
7. structured diagnostics themselves access denied storage;
8. production requires moving/restructuring the entire startup `try`;
9. a second production file is required;
10. normal current-envelope behavior changes;
11. denial is swallowed and startup continues;
12. any API request, Pixi canvas, or game browser appears in the denied case;
13. compiler, Vite, smoke, or teardown differs from the exact protocol;
14. a rerun/debug/alternate probe would be needed;
15. any owner sees pressure to broaden BUG-022 into BUG-023 or general storage
    architecture.

---

## 11. Gate A review questions

Each reviewer must answer all questions against source, not merely restate the
plan.

1. Is `main.ts` the complete production surface for catching the current
   coordinator failure and mounting the existing UI?
2. Does `#ui-root` exist before `main.ts` and require no renderer initialization?
3. Can `showStartupFailure` and its diagnostic payload execute before fonts,
   Pixi, scene, presentation, directory, or backend startup without storage?
4. Are top-level coordinator `getItem` and incompatible-key `removeItem` the
   concrete uncaught methods, while later owner failures remain caught?
5. Does the narrow guard preserve the persistence decision for later
   authenticated-bootstrap acknowledgement on the success path?
6. Is exact error-name classification sufficient and free from message parsing?
7. Is the storage-specific title/explanation truthful without promising data
   cleanup or automatic repair?
8. Does the test use ordinary root startup rather than directly invoking UI or
   coordinator production owners for the denial cases?
9. Are the two fresh pages isolated from inherited storage/prototype state?
10. Is the `getItem` red naturally first after all inherited assertions?
11. Does the green `removeItem` case actually seed an incompatible maintained
    value and fail at scoped cleanup?
12. Do empty diagnostic startup stages, zero presentation fetches, zero API
    requests, and zero canvas/game-browser nodes together prove startup stopped
    before unrelated owners?
13. Does actual summary evidence prevent hard-coded success?
14. Is one focused TypeScript check plus one Vite-only registered smoke
    sufficient and discriminating?
15. Does the packet preserve storage keys/envelopes, public contracts,
    dependencies, and package commands?
16. Is any second production/test file, backend, new framework, or human scope
    decision actually required?

Any `no`, hidden prerequisite, false-red path, extra-file requirement, or
material ambiguity is `CHANGES_REQUIRED`.

---

## 12. Required Gate A verdict form

Approval token:

`APPROVE_WORK_PACKET_005_GATE_A`

Changes token:

`CHANGES_REQUIRED`

An approval must explicitly cover:

- exact plan and baseline identity;
- one-production/one-Tester scope;
- current uncaught causal path;
- pre-render recoverable UI safety;
- truthful error classification/copy;
- isolated get/remove fixtures;
- natural first-red discrimination;
- preserved persistence success behavior;
- execution/teardown protocol;
- performance, duplication, serialization, and non-goal boundaries.

Approval itself authorizes no edit or execution.
