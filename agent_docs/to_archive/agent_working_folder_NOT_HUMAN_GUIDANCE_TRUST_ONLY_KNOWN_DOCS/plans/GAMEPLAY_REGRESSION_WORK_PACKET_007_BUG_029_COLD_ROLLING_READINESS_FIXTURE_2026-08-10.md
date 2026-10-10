# Gameplay Regression Work Packet 007

## BUG-029: current-owner cold Rolling readiness fixture

Revision: **4 — exact ordering, page-error truth, and cached-request proof**

Date: 2026-08-10  
Owner model: Planner -> External Review R1-R4 -> Coordinator -> Tester ->
External Review R1-R4 -> Coordinator -> Tester -> External Review R1-R4 ->
Coordinator  
Execution state at Revision 1 intake: **fresh Gate A only; no source/test edit
or command is authorized by this artifact**

---

## 0. Decision and packet boundary

WP-006 closed only malformed persisted gateway identity quarantine. The next
already-authorized non-human-dependent seam is BUG-029, a maintained test
authority defect.

`app/scripts/animation-readiness-smoke.mjs` claims two concrete Rolling
readiness receipts:

1. a first cold Jump must remain spatially and logically Idle while the real
   `Rolling.png` request is held, then complete one arc after release;
2. a required `Rolling.png` HTTP 404 must fail the visual lineage explicitly,
   drain the queue, preserve the prior visible Idle clip, and start no motion.

Both Jump fixtures still construct a retired, structurally incomplete intent.
They omit the current presentation identity, source identity, locomotion and
trajectory families, current variant/profile/connector fields, and the two
required anchors. The direct-success case reaches `JumpClip.run`, whose first
current boundary reads `intent.anchors.length`; the host/queue failure case
reaches `LocomotionSessionOwner`, whose current boundary first reads
`intent.source`. Each fixture can therefore reject before
`AnimatedEntity.prepareBodyClip("Rolling")` requests any sprite sheet.

A stale fixture failure is not evidence about production media readiness. The
smallest truthful repair is one existing Tester file. No production change is
indicated or authorized.

This packet is limited to:

- one existing registered Tester file:
  `app/scripts/animation-readiness-smoke.mjs`;
- one first-red route-admission witness around the existing cold Rolling case;
- replacing only the two retired Jump fixture objects with the complete
  current `JumpIntent` shape;
- observing actual Rolling sprite requests in the success and failure cases;
- one owned Vite process and the already-registered smoke command.

It does not change or claim:

- `JumpClip`, `MoveClip`, `AnimatedEntity`, `PresentationRuntimeHost`,
  `ClipQueue`, the subjective mapper, or any production owner;
- the backend locomotion/cue/frame contract;
- BUG-009 locomotion-session continuity or BUG-011 frame-final settlement;
- connector, vertical, forced-movement, gameplay, backend, Pixi pixel, Studio,
  or product-browser behavior;
- general animation-asset readiness for every clip/category;
- an asset cache redesign, retry, fallback clip, preload policy, or error
  policy;
- a new test file, package command, dependency, helper framework, or public
  contract.

No material human product or architecture decision is implicated. The user
already authorized repair of maintained false/vacuous gates, and the frozen
current production contract supplies the exact fixture shape.

### 0.1 Revision 1 review receipt

Fresh Revision 1 Gate A review rejected one plan-only ordering mismatch. The
registered smoke invokes `exerciseColdCacheSuccess()` first. The accepted red
is thrown from that function's first Jump, before the top-level runner can
invoke `exerciseLateInitialIdle()`, `exerciseActionSettlesRenderedIdle()`, or
`exerciseFailedLoadDrain()`.

Revision 2 changes no algorithm, file scope, fixture, command, or closure
claim. It limits the first-red prerequisites to the work that actually
precedes that Jump inside `exerciseColdCacheSuccess`: module/import readiness,
initial Idle, first cold Run, and second cached Run. The later inherited cases
remain byte-preserved and become mandatory only on the final green run.

### 0.2 Revision 2 review receipt

Fresh Revision 2 Gate A review rejected one remaining observational gap. The
standalone Playwright script did not subscribe to `pageerror`. An exception
from either request-animation-frame update loop could therefore coexist with
the accepted stale-fixture red or a nominal green without rejecting the
Node-side assertions.

Revision 3 authorizes one case-local page-error recorder in each mutable
Rolling case, installed before navigation. The first-red branch and both final
green receipts require zero captured page errors and return actual counts.
Listeners die with the already-owned pages. No production, fixture contract,
command, file scope, or closure claim changes.

### 0.3 Revision 3 review receipt

Fresh Revision 3 Gate A review rejected one last evidence gap. A positive
aggregate Rolling request count proves that the first cold Jump reached the
asset owner, but the already-released gate would also allow an unintended
second network request to pass immediately. Endpoint/clip/arc assertions alone
would not prove the second Jump was cache-only.

Revision 4 snapshots the Rolling request count after the first Jump fully
completes, then requires the count to remain unchanged after the second Jump.
The final result emits the first-Jump snapshot and actual second-Jump delta.
No route, fixture shape, production file, command, or closure scope changes.

---

## 1. Frozen identity

### 1.1 Program authorities

| Authority | Lines | SHA-256 | Role |
| --- | ---: | --- | --- |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/USER_REPORTED_GAMEPLAY_AND_PRODUCT_REGRESSION_LEDGER_2026-08-10.md` | 607 | `9ac0633322a2203222076a54bd2a8edb23c10e17b49b84562a77d971b922a805` | BUG-029 user/test failure receipt |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/CURRENT_GAMEPLAY_STABILIZATION_MANIFEST_2026-08-10.md` | 798 | `0048c7192773c2a0086a540fabda89023830408ad7ecaf9894c6e34e7529fe5b` | current accepted program boundary |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_STATIC_CAUSAL_STUDY_AND_WORK_PACKET_001_2026-08-10.md` | 767 | `ede1cc4b074ed0bebc104f13197bf02b80ee9cca5311c804a9f29ef7f6d14eff` | current-source BUG-029 classification |

### 1.2 Sole mutable baseline

| File | Lines | SHA-256 | Proposed owner |
| --- | ---: | --- | --- |
| `/home/tommaso/Dev/NeuroClient/app/scripts/animation-readiness-smoke.mjs` | 940 | `573f56b7f18cf2fdb6503221c1b691d7ed1a814c7c0f639655292e3c7815f1a3` | Tester only |

No Implementation production assignment exists in WP-007.

### 1.3 Frozen production/package authorities

| File | Lines | SHA-256 | Why frozen |
| --- | ---: | --- | --- |
| `/home/tommaso/Dev/NeuroClient/app/src/render/clips/JumpClip.ts` | 185 | `f6c3be762133da0ac2988afacbbcd5bba0ade338bf9d7610cb2ca3e0dd97301b` | current two-anchor Jump primitive and readiness caller |
| `/home/tommaso/Dev/NeuroClient/app/src/render/types.ts` | 920 | `1f47dd5b08a3db428d58b3e2bf5ac22137a08d1e12cf6418218730dc71cd32cc` | current `JumpIntent` contract |
| `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts` | 3259 | `87025f16de08abb58ddab3fa65d27ab9562bf7bf0e65dc18d7a6e68598994278` | production current-intent construction authority |
| `/home/tommaso/Dev/NeuroClient/app/src/render/AnimatedEntity.ts` | 1306 | `9c411a9efbd5f1260c36f968b56ac3ca4e3edab89de6f73b4ffc1bfc331e1756` | requested/applied clip and readiness owner |
| `/home/tommaso/Dev/NeuroClient/app/src/render/presentationAssetService.ts` | 1067 | `8623eb057e433c30bb61607e3325ef9188e7c7e5176978f78974610d88d727bc` | real sprite request/cache owner |
| `/home/tommaso/Dev/NeuroClient/app/src/render/runtimeBoundaryTelemetry.ts` | 176 | `256adb571386cd8dd8df504c97aa4680f20e4abc2a73199a790d0211178d9453` | applied/unavailable readiness telemetry owner |
| `/home/tommaso/Dev/NeuroClient/app/src/render/presentationRuntimeHost.ts` | 210 | `4bf3f0870461bdfee3d61273891bb090a8a43940380d1de0a05b13a0281f1d95` | real queue/locomotion-session host |
| `/home/tommaso/Dev/NeuroClient/app/src/render/clipQueue.ts` | 690 | `dd891b5f9ee11cbcde433b5a49d944c05b4cfc8ddaaeba1b497e3027be065c8f` | lineage failure/drain owner |
| `/home/tommaso/Dev/NeuroClient/app/src/render/LocomotionSessionExecutor.ts` | 110 | `779e8c74c0ee1dd7d1db2f85d35a7a288e02f1ac2340a631a719acc62ba100ac` | current source/variant session admission |
| `/home/tommaso/Dev/NeuroClient/app/src/render/dispatcher.ts` | 200 | `de8825f402596b13aa22eee3a930b619eeb095433de9d5527f134b94bc9606c2` | host intent dispatch owner |
| `/home/tommaso/Dev/NeuroClient/app/package.json` | 165 | `36515d20ea94ebc0c49a47b79bd455fee0eddceea2eb5e52713163eff159d9e3` | existing `animation-readiness:smoke` registration |
| `/home/tommaso/Dev/NeuroClient/app/vite.config.ts` | 235 | `7d70b9fae8cf5d4a8d38762865ac8f36adba1247721212fcb5b3d7455f247153` | owned frontend execution boundary |

Every identity above must be re-matched at each public sub-gate. Existing
unrelated worktree changes belong to their owners and must not be attributed
to WP-007.

---

## 2. Current causal boundary

### 2.1 Retired direct-success Jump fixture

`exerciseColdCacheSuccess` imports and calls `JumpClip.run` directly. Its
`startJump` object includes retired fields such as `movementSequenceId`,
`pathStartIndex`, `pathSegmentSteps`, `pathTotalSteps`, and
`finalFacingTargetUuid`, but omits the current `anchors` array and
`presentationId`.

`JumpClip.run` requires exactly two anchors before it calls
`preloadActionVfx` or `entity.beginBodyTravel`. Reading the absent
`intent.anchors.length` rejects the Promise before
`AnimatedEntity.prepareBodyClip` sets `requestedClip="Rolling"` or invokes
the presentation asset service.

The current smoke then observes a completed rejected Promise, unchanged Idle,
and no Rolling request while expecting a held Rolling transition. That is a
fixture failure, not a readiness failure.

### 2.2 Retired queue-failure Jump fixture

`exerciseFailedLoadDrain` creates the same retired shape and enqueues it through
`PresentationRuntimeHost`. The production dispatcher sends a Jump to
`LocomotionSessionOwner`, which keys the session from
`intent.source.sourceStreamId`, `generationId`, and `entityUuid`, then switches
on the current `intent.variant`.

The absent source/variant can reject before `JumpClip`, before Rolling media,
and before the deliberately routed HTTP 404. A generic failed lineage and an
unchanged entity would therefore be insufficient proof; the 404 owner must be
observed directly.

### 2.3 Current contract authority

`types.ts::JumpLocomotionIntent` plus the base locomotion intent requires:

- `type: "jump"` and `variant: "jump"`;
- `entityUuid` and `presentationId`;
- exact source stream/generation/perspective/cursor identity;
- `locomotionFamily: "jump"`;
- `trajectoryFamily: "direct_arc"`;
- exactly two `{position, elevationFeet}` anchors;
- `endpointOutcome` and reaction groups;
- `connector: null` and `profile: "jump_planar"`;
- from/to/duration/arc/clip/playback/VFX/recovery fields.

`subjectivePresentationMapper` remains the production constructor. The smoke
may hand-author only this complete typed fixture because its scope is the
lower-level readiness primitive and queue, not subjective cue mapping.

---

## 3. Accepted receipts

### 3.1 First-red receipt: stale fixture proven

With production frozen and only the admission witness added:

1. module/import readiness, initial Idle, the first cold Run hold/release/
   completion, and the second cached Run completion pass before the first
   Jump;
2. the first Jump settles rejected before any routed Rolling request;
3. its entity remains at `[4, 0]`, logical/applied/requested presentation
   remains Idle, and the captured Jump error is non-null;
4. the exact accepted red is:
   `cold Rolling fixture rejected before reaching current sprite owner`;
5. the cold-case page-error count is zero;
6. `exerciseLateInitialIdle`, `exerciseActionSettlesRenderedIdle`,
   `exerciseFailedLoadDrain`, and the final summary are unreached on first red
   but remain byte-preserved mandatory green cases;
7. owned Vite/browser cleanup completes.

This is a natural test-authority red. It is not a product regression and does
not release production Implementation.

### 3.2 Green receipt: repaired fixture reaches current owners

With the same production identities and the final Tester correction:

1. the first cold Jump reaches at least one real routed `Rolling.png` request;
2. while that request is held, requested clip is Rolling, applied/logical clip
   is Idle, position remains `[4, 0]`, and the Jump Promise is unsettled;
3. release completes one continuous arc to `[6, 0]` with Rolling applied;
4. after the first Jump completes, its positive Rolling request count is
   snapshotted; the second Jump completes one continuous arc to `[8, 0]` and
   the actual Rolling-request delta remains exactly zero;
5. the 404 case reaches at least one real routed `Rolling.png` request;
6. the host returns an explicit failed lineage mentioning Rolling, is idle,
   starts no motion, preserves Idle, records unavailable Rolling telemetry,
   and fabricates no reset/rebuild;
7. each Rolling page reports zero captured page errors;
8. actual success/failure Rolling request and page-error counts appear in the
   final JSON.

---

## 4. Tester first-red witness

### 4.1 Sole edit location

Tester edits only:

`app/scripts/animation-readiness-smoke.mjs`.

For the first-red identity, modify only `exerciseColdCacheSuccess`:

1. add one case-local page-error array and register `page.on("pageerror", ...)`
   before navigation, retaining each actual error string;
2. add one Node-side Rolling request counter;
3. add one deferred `rollingRequestSeen` signal;
4. in the existing `**/spritesheets/**/*.png` route, when the pathname ends
   in `/Rolling.png`, increment the counter and resolve the signal before
   awaiting the existing `rollingGate`;
5. after `startJump([4, 0], [6, 0])` and before the current fixed-delay state
   snapshot, race boundedly among:
   - the Rolling request signal;
   - the existing page fixture reporting `jumpDone`;
   - a 2.5-second observation timeout.

Do not correct the Jump object yet. Do not edit the failure case yet.

### 4.2 Natural-red classification

If `rollingRequestSeen` wins, continue to the current blocked-state assertion.
That is not expected on the frozen stale fixture.

If `jumpDone` wins first:

- read actual `gx`, `gy`, FSM state, requested clip, applied clip,
  `jumpDone`, and `jumpError`;
- require Rolling request count `0`;
- require `[gx, gy]` equals `[4, 0]`;
- require FSM/applied/requested clip remain Idle;
- require `jumpDone === true` and a non-null error;
- require the case-local page-error array length to equal zero, otherwise fail
  with a distinct diagnostic containing the captured strings;
- then throw exactly:
  `cold Rolling fixture rejected before reaching current sprite owner`.

If the observation timeout wins, throw a distinct timeout/boundary message.
Do not translate it into the accepted red.

The case's existing `finally` must still resolve both media gates and close the
page. The outer browser `finally` must remain unchanged.

### 4.3 False-red exclusions

The exact red is admissible only after:

- module navigation/import succeeded;
- initial Idle loaded;
- the first cold Run reached its gate, stayed blocked, released, and completed;
- the second cached Run completed;
- the Jump fixture settled with a captured error;
- no Rolling route was invoked;
- the entity stayed visibly and spatially Idle.

A Vite failure, missing Idle/Run asset, route timeout, browser page error, or
unexpected motion must retain its own existing/distinct assertion.

---

## 5. Final Tester correction

After the governed first red and fresh release review, Tester edits only the
same file. Preserve the route-admission witness.

### 5.1 Current direct-success Jump shape

Replace only the retired `startJump` object fields with one complete current
`JumpIntent` fixture. It must carry:

```js
{
  type: "jump",
  variant: "jump",
  entityUuid: entity.uuid,
  presentationId: `readiness-jump:${from.join(",")}`,
  source: Object.freeze({
    sourceStreamId: "animation-readiness-cold",
    generationId: "animation-readiness-cold-generation",
    perspectiveEpochId: "animation-readiness-cold-epoch",
    observationCursor: 1,
    sourceEventCursor: 1,
  }),
  locomotionFamily: "jump",
  trajectoryFamily: "direct_arc",
  anchors: Object.freeze([
    Object.freeze({ position: Object.freeze([...from]), elevationFeet: 0 }),
    Object.freeze({ position: Object.freeze([...to]), elevationFeet: 0 }),
  ]),
  endpointOutcome: "committed",
  connector: null,
  profile: "jump_planar",
  from: Object.freeze([...from]),
  to: Object.freeze([...to]),
  durationMs: 240,
  arcHeightPx: 36,
  clip: "Rolling",
  playbackSpeed: (14 / 12 * 1000) / 240,
  vfx: Object.freeze({}),
  recovery: /* preserve existing disabled recovery */,
  reactionLeadInMs: 40,
  preMotionGroups: Object.freeze([]),
}
```

Do not retain the retired movement-sequence/path-segment/final-facing fields.
Do not import or call the subjective mapper; this remains a direct primitive
fixture.

After the route-admission signal wins, require the actual Rolling request
count to be positive before the existing blocked-state assertions. Return the
actual count as `coldRollingRequestCount` in the success evidence. Before the
case returns, require the case-local page-error array to remain empty and
return its actual length as `coldPageErrorCount`. Do not substitute new
hard-coded success flags.

Immediately after the first cold Jump fully completes and all of its endpoint,
Rolling-sample, and one-arc assertions pass, snapshot the current request
count as `coldRollingRequestCountAfterFirstJump`. After the second Jump fully
completes and its existing assertions pass, compute
`secondJumpRollingRequestDelta` from the current count minus that snapshot and
require the delta to equal exactly `0`. Return both actual numeric values.

Do not fulfill, abort, or route the second Jump differently. The zero delta
must come only from the unchanged production asset cache for the same fresh
page and appearance.

### 5.2 Current queue-failure Jump shape

In `exerciseFailedLoadDrain`, replace only the retired Jump object with the
same complete current contract, using case-local stable identities such as:

- `presentationId: "failed-rolling-jump"`;
- source stream/generation/epoch values scoped to `failed-rolling`;
- observation/source cursors `1`;
- anchors `[0,0]` and `[2,0]`, both elevation `0`;
- the existing duration, arc, Rolling clip, playback, disabled recovery, VFX,
  reaction lead-in, and empty pre-motion groups.

Add one Node-side count in the existing exact Rolling route before its 404
fulfillment. After `page.evaluate` returns, require the count to be positive
and return it as `failedRollingRequestCount` in the failure evidence.

Install a separate case-local `pageerror` recorder before the failure page's
navigation. After the evaluated queue receipt returns and before the case
returns, require the captured list to be empty and return its actual length as
`failedPageErrorCount`.

The existing failure assertions remain mandatory:

- lineage status `failed` and detail includes `Rolling`;
- host idle;
- entity remains `[0,0]`;
- FSM/applied clip remains Idle;
- telemetry contains requested Rolling / unavailable / applied Idle;
- no presentation reset or static board rebuild;
- zero captured page errors.

### 5.3 Frozen inherited behavior

Do not change:

- rendered-Idle action settlement;
- cold/cached Run behavior;
- late initial Idle invalidation;
- movement sampling/arc expectations;
- telemetry semantics;
- page/browser cleanup;
- package command or Vite ownership;
- production source.

The currently stale Move fixture is outside BUG-029 because its direct
`MoveClip` path reaches the claimed Run owner and the existing cold/cached Run
assertions are an inherited prerequisite. This packet must not broaden into a
general fixture-schema migration.

---

## 6. No production algorithm

WP-007 has no Implementation edit. All production authorities in Section 1.3
remain byte-frozen across red and green.

The result may close only the maintained BUG-029 fixture authority and verify
the already-existing production Rolling readiness behavior that the corrected
fixture reaches. Any observed product failure after the corrected current
fixture is a new frozen result requiring its own bounded packet; Tester must
not patch production or weaken assertions during this packet.

---

## 7. Governed execution protocol

### 7.1 Preconditions for each attempt

From `/home/tommaso/Dev/NeuroClient`:

1. re-match the frozen plan, Tester, production, package, and Vite identities;
2. prove port 5173 is free and no owned/stale Vite/npm-dev process is active;
3. run focused app TypeScript once:
   `./app/node_modules/.bin/tsc --noEmit -p ./app/tsconfig.json`;
4. only if zero, start exactly one owned:
   `npm --prefix app run dev`;
5. wait boundedly for the exact Vite root readiness response;
6. run exactly once:
   `npm --prefix app run animation-readiness:smoke`;
7. stop immediately at the governed result;
8. always interrupt/join only the owned Vite tree and prove port, PID, and
   children absent.

No backend is required. Do not start `server.sh`, gateway, preview worker, or
another service.

### 7.2 First-red attempt

Use the frozen first-red Tester identity from Section 4.

Require:

- tsc exit `0`;
- one Vite and one smoke invocation;
- module/import readiness, initial Idle, first cold Run hold/release/
  completion, and second cached Run completion pass before the first Jump;
- smoke exit nonzero only at exact message:
  `cold Rolling fixture rejected before reaching current sprite owner`;
- the reported red evidence shows Jump done/error, position `[4,0]`, Idle
  requested/applied/FSM, Rolling request count `0`, and page-error count `0`;
- late-initial-Idle, rendered-Idle action settlement, the failure-load case,
  and final summary are unreached on first red and reserved for green;
- teardown is complete.

Any other result freezes. No rerun, edit, debug, alternate command, direct
module probe, cache deletion, formatter, or workaround is permitted.

### 7.3 Green attempt

After the first-red release and fresh static approval of the final Tester
identity, repeat the same atomic protocol exactly once.

Require smoke exit `0` and final actual evidence including:

- positive `coldRollingRequestCount`;
- positive `coldRollingRequestCountAfterFirstJump`;
- `secondJumpRollingRequestDelta === 0`;
- `coldPageErrorCount === 0`;
- first cold and second cached Jump endpoints/arcs;
- positive `failedRollingRequestCount`;
- `failedPageErrorCount === 0`;
- explicit failed Rolling lineage;
- queue idle;
- prior Idle state/clip preserved;
- unavailable Rolling telemetry;
- zero reset/rebuild evidence;
- every inherited assertion green.

Any other result freezes. No rerun or production edit is authorized.

### 7.4 Cleanup

The Tester owns each browser page in its existing `finally` and the browser in
the outer `finally`. The runner owns Vite. Completion requires:

- browser process joined by Playwright;
- owned Vite interrupted and joined;
- port 5173 closed;
- owned PID and descendants absent;
- no backend/service process started by the packet.

---

## 8. Role assignments and gates

### 8.1 Gate A

Fresh isolated R1-R4 review the complete plan and frozen identities. Unanimous
approval plus Coordinator verification may release only Section 4's
first-red Tester edit.

### 8.2 Tester first-red edit-only

Tester may inspect only the accepted plan and the smoke file, apply only the
Section 4 witness, and use read-only diff/line-count/SHA checks. Tester runs no
project command. Freeze the resulting identity for fresh R1-R4 static review.

### 8.3 First-red release

After static 4/4 and Coordinator verification, Tester runs Section 7.2 once.
The exact accepted red releases only the Section 5 Tester correction for fresh
review. It does not release Implementation.

### 8.4 Tester final edit-only

Tester may apply only Section 5 in the same file, run nothing, and return exact
diff/line-count/SHA evidence. Freeze the identity for fresh R1-R4 combined
static review.

### 8.5 Green release and Gate B

After combined 4/4 and Coordinator verification, Tester runs Section 7.3 once.
Fresh R1-R4 then assess final causal acceptance. Gate B closes automatically
only at public unconditional 4/4 on identical frozen identities and complete
teardown.

Implementation remains HOLD/unused throughout WP-007.

---

## 9. Scope, duplication, serialization, and performance

- Mutable scope is one existing Tester file.
- No production source, backend, SDK, generated file, package, asset, or
  dependency changes.
- The fixture copies only the current typed `JumpIntent` fields necessary to
  call the lower-level primitive/host it is explicitly testing; it does not
  reproduce subjective cue mapping or a validator.
- Production remains sole owner of clip readiness, sprite loading, state
  transition, arc motion, lineage failure, queue drain, and telemetry.
- Request counters/snapshots/deltas are transient per-case observations and
  are emitted only in console test evidence; they add no persistent schema or
  application DTO.
- No scan, retry, cache mutation, listener in production, timer in production,
  or hot-path cost is added.
- Two bounded test-only admission observations and two page-local error
  recorders replace vacuous inference from a malformed intent and unobserved
  browser exceptions.

---

## 10. Closure claim

Gate B may state only:

> BUG-029 is guarded: the maintained animation-readiness smoke now constructs
> current two-anchor Jump intents, proves the first cold Rolling request is
> actually held before motion/FSM transition, and proves a real Rolling 404
> fails and drains the production queue while preserving Idle.

Gate B must not state:

- all animation readiness is correct;
- gameplay Jump was exercised end-to-end;
- subjective cue mapping, backend locomotion, frame settlement, connectors,
  verticality, or product Pixi pixels were proven;
- BUG-009, BUG-011, BUG-027, BUG-031, or BUG-032 is closed;
- production source changed.

---

## 11. Mandatory Gate A reviewer questions

Reviewers must answer every question with source-backed evidence:

1. Is the existing smoke the maintained and registered owner of both claimed
   Rolling readiness cases?
2. Does the current direct-success Jump fixture omit `anchors` and therefore
   reject before `beginBodyTravel("Jumping")` and Rolling asset admission?
3. Does the current queue-failure fixture omit `source`/`variant` and therefore
   admit failure before the routed Rolling 404?
4. Does the Section 4 witness observe the route before gate release without
   changing the stale intent or production?
5. Can the exact accepted red occur only after Run prerequisites passed, Jump
   settled rejected, request count stayed zero, and visible/spatial Idle was
   preserved?
6. Is the red timeout distinct and bounded rather than translated into the
   accepted result?
7. Does each final Jump fixture exactly satisfy the current
   `JumpLocomotionIntent` base and variant fields?
8. Are the anchors exactly two, positionally equal to from/to, with finite
   elevation values, without copying production validation?
9. Are retired movement-sequence/path-segment/final-facing fields removed only
   from the two Jump fixtures?
10. Does the cold success route signal resolve before awaiting the existing
    Rolling gate, making the blocked-state observation causal?
11. Do positive actual route counts prevent a malformed/alternate-owner false
    green, and does the post-first-Jump snapshot plus zero second-Jump delta
    prove the second Jump is cache-only?
12. Does release of the existing gate remain the only reason the first Jump can
    proceed after the blocked assertion?
13. Do endpoint, clip samples, lift segments, and the zero request delta still
    prove one cold and one cached continuous Jump?
14. Does the 404 case use the real host/session/dispatcher/Jump/AnimatedEntity
    chain and a real routed Rolling request?
15. Do failed-lineage detail, host idle, no motion, Idle preservation, and
    unavailable telemetry jointly exclude an early schema failure?
16. Are request counts returned as actual evidence in the final summary rather
    than hard-coded pass flags?
17. Are page-error listeners installed before navigation in both Rolling cases,
    required empty before the accepted red/green returns, and emitted as
    actual counts?
18. Are every inherited non-Rolling assertion and all page/browser cleanups
    preserved?
19. Is one Tester file complete with no production, mapper, package, asset, or
    second-test edit pressure?
20. Is focused tsc plus one owned Vite and the registered smoke once sufficient
    for each governed red/green attempt, without backend or ambient process?
21. Is the accepted closure limited to repaired BUG-029 test authority and the
    two concrete existing Rolling readiness receipts?
22. Does any proposed edit inadvertently broaden into the stale Move fixture or
    general locomotion contract migration?
23. Is all runtime overhead test-only, bounded, transient, and absent from
    production hot paths?
24. Is there any remaining false-red, false-green, cleanup, serialization,
    duplication, scope, or human-decision blocker?

Any `CHANGES_REQUIRED` rejects the current identity. Votes never carry across
revisions or changed Tester identities.
