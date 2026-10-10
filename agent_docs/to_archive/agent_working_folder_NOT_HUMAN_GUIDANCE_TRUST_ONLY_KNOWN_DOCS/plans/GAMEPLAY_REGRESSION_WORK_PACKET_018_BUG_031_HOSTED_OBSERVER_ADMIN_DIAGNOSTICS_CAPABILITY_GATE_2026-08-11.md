# Gameplay Regression Work Packet 018 — BUG-031 Hosted Observer Admin-Diagnostics Capability Gate

Date: 2026-08-11
Owner: Planner / External Reviewer 1
Implementation owner: HOLD; the production edit stage is closed historical evidence
Tester owner: HOLD; the Tester edit stage is closed historical evidence
Execution owner: Tester, only after fresh combined-static approval

## 0. Decision and boundary

WP-017 is consumed, non-green, and `NO RETRY`. Its reached fresh-fixture,
runtime, input, End Turn, reconnect, objective-history settlement, rendered,
and observer receipts are historical evidence only. They are not Gate B
acceptance and do not authorize another WP-017 execution.

The governed WP-017 terminal browser errors separated into three independent
successors:

- A: owner available-actions browser dispatch/delivery observation;
- B1: observer admission of admin-only objective diagnostics;
- B2: observer reviewed-portrait identity observation.

The public split-successor scope ledger approved all three only as separate
packets. B1 was selected as the next seam because its production owner and
invariant are already source-selected. This packet implements only B1. A and
B2 remain separately authorized backlog seams and may not be observed,
implemented, filtered, suppressed, or bundled here.

The exact defect is bounded. `bindHostedRuntime()` already receives the
authoritative `HostedGameConnection.access_mode`. For an observer connection
it still binds an `ObjectiveDiagnosticsClient` carrying the observer runtime
token. Once subjective bootstrap is installed, `startObjectiveDiagnostics()`
starts both:

1. the objective-history follower, whose first request is
   `GET diagnostics/objective/bootstrap`;
2. the subjective-render-parity poller, whose request is
   `GET diagnostics/subjective-parity?session_id=...`.

The gateway correctly classifies both route families as `ADMINISTER`. Hosted
observer memberships intentionally omit administration authority. The worker
independently requires administration projection. The two observed HTTP 403s
were therefore correct server enforcement of an invalid client admission,
not portrait/static requests and not a server-policy defect.

### 0.1 Frozen selected correction

The current immutable candidate contains the smallest source-consistent
correction in one production file:

- `app/src/engine/runtimeConnection.ts`.

For `connection.access_mode === "observer"`, `bindHostedRuntime()` retires
the objective-diagnostics client through the existing
`stopObjectiveDiagnostics()` owner instead of binding an admin client. For
participant connections, the existing `bindObjectiveDiagnostics()` call
remains unchanged. Hosted-agent diagnostics admission is not affirmatively
classified by this observer-only packet: frozen authority shows that an
`agent` connection may lack `ADMINISTER`, so agent and any other non-observer
connection lacking `ADMINISTER` are explicitly deferred to a separate
admission seam.

The shared subjective runtime binding remains unconditional and byte-stable:

- `directoryClient.runtimeClient(connection)` remains installed;
- `bindHostedRuntimeClients(...)` remains installed before the diagnostic
  branch;
- game ID, durable runtime session, runtime token, and access mode remain the
  current production values;
- observer controlled entities remain empty by the existing gateway and
  subjective-replication contracts.

When `eventStream` later calls `startObjectiveDiagnostics()` for the observer,
the existing null-client branch supplies the exact local non-running receipt:

- `objectiveDiagnosticsStatus === "disabled"`;
- `objectiveDiagnosticsDetail === "no objective diagnostics client is bound"`.

The preceding `stopObjectiveDiagnostics()` call also preserves the existing
backend-parity receipt:

- `backend.status === "disabled"`;
- `backend.reason === "no active player runtime"`;
- `backend.response === null`.

No new status, message, enum, capability, contract, or policy is introduced.
The correction does not manufacture an HTTP `unauthorized` result because no
request is issued.

### 0.2 Focused Tester evidence

The consumed hosted-game smoke is not a lawful B1 executor because it also
reaches the separately deferred A and B2 faults. Reusing it would bundle three
owners or require forbidden browser-error filtering.

The current immutable Tester surface contains one isolated registered
Vite/module smoke:

- `app/scripts/hosted-observer-admin-diagnostics-smoke.mjs`.

The production import extension also required one exact static expectation
change in the already registered `player-replication-boundary:smoke`. The
current immutable ownership-smoke identity contains only that import-list
change. This is a direct static-authority correction, not a second product
behavior owner.

The smoke loads a source module as the document so `main.ts` cannot bootstrap
a match. It imports the real production runtime/diagnostics/store/parity
owners, binds a synthetic but shape-valid hosted observer connection to an
unserved probe origin, explicitly invokes the same production
`startObjectiveDiagnostics()` entry point that event-stream bootstrap owns,
and observes only:

- actual runtime mode/game/session/access-mode identity;
- exact objective-diagnostics status/detail and zero objective history;
- exact backend-parity status/reason/null response;
- actual CDP and Playwright requests for only the two forbidden route paths;
- page errors and console errors.

The probe origin is never contacted by a conforming implementation. It is not
a mock server, interception, route fulfillment, response fabrication, or
alternate API. Any objective-bootstrap or subjective-parity request is actual
failure evidence and makes the smoke nonzero.

The smoke does not claim real gateway, worker, observer game, rendering,
portrait, or available-actions correctness. Preservation of subjective
observer replication is established by the one-file production diff:
`bindHostedRuntimeClients(...)`, `eventStream`, replication clients, gateway,
worker, and contracts are frozen. The historical WP-017 real observer receipt
remains historical corroboration only.

### 0.3 Strict claim

Successful Gate B may establish only:

> BUG-031 B1: a hosted observer connection does not bind or start the two
> admin-only objective-diagnostics owners, produces the existing local
> disabled/non-running diagnostics receipts, and issues zero objective-
> bootstrap or subjective-parity requests, while participant diagnostics and
> subjective hosted runtime binding remain source-identical.

It does not claim WP-017 green, hosted-game correctness, gateway or worker
correctness, observer rendering, portraits, available-actions transport,
reconnect, End Turn, transcript, presentation, replication, or any deferred
packet.

## 1. Frozen authority identity

Every identity is exact. Intake fails closed on any mismatch. No refresh,
substitution, regeneration, or retained-root access is permitted.

### 1.1 Governance and predecessor authority

- frozen WP-017 plan:
  `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_WORK_PACKET_017_BUG_031_HOSTED_RUNTIME_READINESS_RESOLVED_WAIT_2026-08-11.md`
  — 2,826 lines / 117,362 bytes /
  `496b04ec54a9bead64f7258af482cb03b26ed02246b83481f06d3b6bdeae627e`;
- frozen WP-017 census authority: predecessor-plan lines 908-2550 — 1,643
  lines / 49,258 bytes /
  `7c1159d1c18b0fc05e0fa2865b0642ed7bf77ba2758e2bd6fa81bc84d4ec7ff3`;
- frozen WP-017 checker: `app/scripts/check-node-sources.mjs` — 126 lines /
  4,812 bytes /
  `e9ab23a4b99927b673c1fd08dcb6c63d30aa40c5cee9616e3b5c88e54792fda8`;
- frozen WP-017 hosted smoke: `app/scripts/hosted-game-smoke.mjs` — 568
  lines / 22,507 bytes /
  `de9c9a1bf53ceb65601d7d8f2cf376d907758536951f3b0eec23d3fe464d13e8`.

The accepted split-successor ledger is normative governance evidence:

- A remains observation-only backlog;
- B1 alone is ready for this normal plan gate;
- B2 remains observation-only backlog;
- cleanup and the two-census process protocol are closed;
- WP-017 remains `NO RETRY`.

No retained stdout, stderr, JSON, database, artifact, or earlier root may be
opened or rehashed for this packet.

### 1.2 Immutable production identity

- `app/src/engine/runtimeConnection.ts` — 150 lines / 4,549 bytes /
  `e0471fcd0737733645d48f301c1f04be30ab5d554aa21a9b7d3b578b2d88deb7`;
- `app/src/engine/objectiveDiagnostics.ts` — 389 lines / 11,970 bytes /
  `06bac0fe2b9f4943f3055298a65f8a5c890d56279f7f9f568f3cc96a32da2cc8`;
- `app/src/render/renderParity.ts` — 720 lines / 22,966 bytes /
  `6ae2d160a292e30e75a060443feebad0be603dbc93a7b0c8189a022d3e809b58`;
- `app/src/engine/store.ts` — 431 lines / 13,882 bytes /
  `b0c428f266cf3c23608143e3ee73fc048f82bfb0afb5ffee3e317b1aff859537`;
- `app/src/engine/eventStream.ts` — 974 lines / 34,021 bytes /
  `912ef41889c5a1a753d8969037550e3fabc6ecbd126e1d417e4cced6290fd522`.
- `app/src/engine/replication.ts` — 69 lines / 1,923 bytes /
  `6e23abd575a12eac18cccec7a5d25119250b2ecc4d22de6941fcdf8def2c9c6d`;
- `app/src/engine/debugUiVisibility.ts` — 26 lines / 834 bytes /
  `7eb8cef545ded9963ca9d34863cfe533b7c308cac7c2e497fd97bab26a54d630`;
- `app/src/api/gameDirectory.ts` — 961 lines / 30,497 bytes /
  `7c302315a8da021fb7652baf09d2d5c9575cd82893fe15729a80a85968fe6560`.

All eight files are now immutable. The `runtimeConnection.ts` identity is the
current strict-B1 candidate. Its earlier one-file production approval is
historical completed evidence only; no source edit or technical vote carries
into this revised plan.

### 1.3 Immutable Tester and package identity

- `app/scripts/hosted-game-smoke.mjs` — frozen above and not editable;
- `app/scripts/check-node-sources.mjs` — frozen above and not editable;
- `app/scripts/hosted-observer-admin-diagnostics-smoke.mjs` — 234 lines /
  7,981 bytes /
  `e27d6cf10ddee0aca252029a0f2e3013c5e5f785aaeb2b9743e94f109dcc4f58`;
- `app/scripts/player-replication-boundary-smoke.mjs` — 967 lines / 34,564
  bytes /
  `a702ff918b1a13b3b42ceb18a02170048f8139de36b510cbd7518c155c09cf5d`;
- `app/package.json` — 166 lines / 16,476 bytes /
  `ad20b15ee4713532b381d50cf0c9dee7616cb117580cf4fc6072e42ec8c7b062`.

The immutable package registers
`player-replication-boundary:smoke` as exactly
`node scripts/player-replication-boundary-smoke.mjs` and includes it in the
complete `check` surface. It also contains exactly the new non-aggregate key:

```json
"hosted-observer-admin-diagnostics:smoke":
  "node scripts/hosted-observer-admin-diagnostics-smoke.mjs"
```

The immutable ownership smoke expects the
`src/engine/runtimeConnection.ts` importer names to be exactly
`["bindObjectiveDiagnostics", "stopObjectiveDiagnostics"]`. No Tester edit,
package edit, smoke edit, checker edit, or aggregate change is released.

### 1.3.1 Exact LF accommodation and closed edit history

The current package and ownership-smoke identities are accepted only with
these four exhaustive terminator facts:

1. the existing package `hosted-game:smoke` line changed from CRLF to LF;
2. the new package `hosted-observer-admin-diagnostics:smoke` line uses LF;
3. the existing package `render-anchors:smoke` line changed from CRLF to LF;
4. the changed ownership-smoke `runtimeConnection.ts` expected-import line
   uses LF.

There is no generic whitespace, line-ending, platform, formatter, diff-check,
future-file, or future-drift waiver. No other current or later byte mismatch
is accepted. These exact hashes and facts are immutable review evidence.

The accepted historical baselines were package
165/16,371/`36515d20ea94ebc0c49a47b79bd455fee0eddceea2eb5e52713163eff159d9e3`
and ownership smoke
967/34,537/`4a557a70d59842c2394c8d7ba585a7ad14ae70cfc2b07506bb3d843d86293733`.
Two authorized file-edit attempts, including a literal-CR `apply_patch`, did
not write the requested CR bytes. That correction path is closed historical
process evidence. This plan requires no CRLF reconstruction, normalization,
or further edit attempt.

### 1.4 Contract and server authorities

- `sdk/typescript/src/generated/contracts.generated.ts` — 7,860 lines /
  894,890 bytes /
  `1d5da717cac4aa767bf87b789336b33649cf5e9567261ac71d31b069716a88b5`;
- `sdk/typescript/src/directoryClient.ts` — 1,016 lines / 31,785 bytes /
  `f9f839cb1376c5a19611ea6d62c34591eb16c04acce95c694973ff093f0b5648`;
- `server/game_gateway.py` — 2,732 lines / 109,250 bytes /
  `6f950eef1cf0fd94c23408f48462b9af5611b5f3d69641c2a1dc8ca087ca87af`;
- `server/worker_proxy.py` — 314 lines / 10,296 bytes /
  `6cfe0931c0124e12445a5e9a0f05e5b497c6851f552f8a1234a39518f3087b2d`;
- `server/event_server.py` — 6,978 lines / 258,369 bytes /
  `eb1f6e891bc4cb149c8f054bb8ae36e4df7f2a7a7d47e6cc91af2a3e7394cdc5`.

All five are frozen. The authoritative facts are:

- `HostedGameConnection.access_mode` distinguishes `observer`;
- observer memberships omit objective-replay administration;
- runtime scopes omit `ADMINISTER` for observers;
- objective bootstrap and subjective parity require `ADMINISTER`.

The same frozen authority also shows that `access_mode === "agent"` is not by
itself proof of `ADMINISTER`: agent capabilities do not grant
`may_manage_game`, while runtime `ADMINISTER` derives from that capability.
This packet neither validates nor changes hosted-agent diagnostics admission.

## 2. Causal finding

### 2.1 Current production control flow

`bindHostedRuntime(connection)` currently performs, in order:

1. runtime generation retirement;
2. hosted subjective runtime-client binding using the connection token;
3. objective-diagnostics client binding using the same base URL/token;
4. publication of hosted game/session/access-mode identity.

`eventStream` later calls `startObjectiveDiagnostics(generationId,
sessionId)` after a real subjective bootstrap. With debug UI visible, the
current non-null client starts both admin request owners.

The defect is step 3 for observer access only. Step 2 is valid and must remain
unchanged.

### 2.2 Existing disabled owner

`stopObjectiveDiagnostics()` is already the sole owner of retiring the active
diagnostics client. It:

- aborts any active run;
- clears objective event/history/cursors;
- writes objective status `disabled` with detail `no active player runtime`;
- writes backend parity `disabled` with reason `no active player runtime`;
- nulls the diagnostics client.

When event-stream bootstrap later calls `startObjectiveDiagnostics()`, the
null-client branch synchronously writes the more specific objective detail
`no objective diagnostics client is bound` and returns before parity checking,
objective bootstrap, or parity polling begins. The backend parity receipt
therefore remains the earlier exact disabled receipt.

This is an existing production semantic, not a new test-only state.

### 2.3 Why server or SDK changes are forbidden

The two 403 responses are correct capability enforcement. Granting observer
administration, weakening worker projection checks, changing route kinds, or
suppressing HTTP errors at the fetch/SDK layer would broaden authority and
hide an invalid client request. None is lawful.

## 3. Immutable production correction

No Implementation edit is released. The immutable
`app/src/engine/runtimeConnection.ts` identity must contain exactly the
following already-present correction.

### 3.1 Import

The existing objective-diagnostics import includes the existing retirement
owner:

```ts
import {
  bindObjectiveDiagnostics,
  stopObjectiveDiagnostics,
} from "./objectiveDiagnostics";
```

No alias, wrapper, capability adapter, or new module is allowed.

### 3.2 Hosted binding branch

`bindHostedRuntimeClients(...)` remains byte-identical and in its current
order. The immutable diagnostic branch is exactly:

```ts
if (connection.access_mode === "observer") {
  stopObjectiveDiagnostics();
} else {
  bindObjectiveDiagnostics(connection.engine_base_url, headers);
}
```

`activeConnection` publication remains byte-identical. `agent` continues
through the syntactically unchanged non-observer branch because this packet
changes only exact `observer`. That fact is not an affirmative claim that the
agent branch is admin-capable or lawful; hosted-agent diagnostics admission is
outside WP-018 and remains deferred.

### 3.3 Forbidden production changes

- no edit to objective-diagnostics state machines, polling, HTTP handling, or
  status enums;
- no edit to subjective runtime clients, event-stream start order, store,
  parity logic, SDK, gateway, worker, or authorization;
- no console filtering, HTTP-error conversion, retry, delay, timeout, catch,
  or warning change;
- no public contract, persistence, schema, service, or dependency change.

## 4. Immutable focused Tester surface

No Tester edit is released. The current new smoke, package key, and ownership
expectation are immutable and require fresh combined-static review after this
revised plan passes Gate A.

### 4.1 New registered smoke

The immutable new file is:

`app/scripts/hosted-observer-admin-diagnostics-smoke.mjs`

The immutable package registration is exactly:

```json
"hosted-observer-admin-diagnostics:smoke":
  "node scripts/hosted-observer-admin-diagnostics-smoke.mjs"
```

The smoke is not added to a broad aggregate. No package, smoke, or checker
edit is released.

### 4.1.1 Registered ownership-smoke correction

In the immutable `app/scripts/player-replication-boundary-smoke.mjs`, the
`src/engine/runtimeConnection.ts` value inside
`assertObjectiveDiagnosticsImportBoundary()` is exactly:

```js
["src/engine/runtimeConnection.ts", ["bindObjectiveDiagnostics", "stopObjectiveDiagnostics"]],
```

No other expected importer, assertion, output field, helper, or behavior in
that registered smoke changed. The exact whole-file hash and Section 1.3.1 LF
fact are normative; this line records the import extension without relaxing
ownership enumeration.

### 4.2 Isolated browser owner

The smoke must:

1. launch one headless Chromium through the installed Playwright package;
2. create one context and one page;
3. attach pageerror and console-error collection before navigation;
4. attach one CDP session, enable `Network`, and collect only requests whose
   pathname exactly equals either probe route below;
5. navigate to `${NEUROCLIENT_URL}/src/engine/runtimeConnection.ts` as a
   source document so `main.ts` never executes;
6. import only the real production modules in one page evaluation;
7. always call `stopObjectiveDiagnostics()` and close context/browser in
   `finally`;
8. print exactly one final JSON object and throw afterward on any failure.

The exact probe base is:

`http://127.0.0.1:9/games/wp018-observer-probe/runtime`

The only classified paths are:

- `/games/wp018-observer-probe/runtime/diagnostics/objective/bootstrap`;
- `/games/wp018-observer-probe/runtime/diagnostics/subjective-parity`.

Count every CDP request for either exact pathname regardless of method,
query, initiator, or outcome. Also attach Playwright `request` and
`requestfailed` observation for the same exact paths. A conforming run has no
such events.

The smoke must not route, abort, fulfill, continue, modify, or synthesize a
request. It must not start a server on port 9.

### 4.3 Synthetic connection input

Inside the page, call the real `bindHostedRuntime()` with this complete frozen
`HostedGameConnection`-shaped object:

```js
{
  game_id: "wp018-observer-probe",
  attachment_id: "wp018-observer-attachment",
  engine_base_url:
    "http://127.0.0.1:9/games/wp018-observer-probe/runtime",
  runtime_session_id: "wp018-observer-session",
  runtime_token: "wp018-observer-token",
  membership: {
    membership_id: "wp018-observer-membership",
    game_id: "wp018-observer-probe",
    principal_id: "wp018-observer-principal",
    role: "observer",
    side_id: null,
    controller_kind: null,
    membership_state: "active",
    capabilities: {
      may_connect: true,
      may_observe_public_state: true,
      may_observe_subjective_state: true,
      may_control_entities: false,
      may_view_agent_telemetry: false,
      may_manage_members: false,
      may_manage_game: false,
      may_view_objective_replay: false,
    },
    subjective_source_membership_id: null,
    authority_epoch: 1,
    joined_at: "2026-08-11T00:00:00.000Z",
    disconnected_at: null,
    revoked_at: null,
    left_at: null,
  },
  controlled_entity_uuids: [],
  observer_entity_uuids: ["wp018-observer-entity"],
  active_observer_uuid: "wp018-observer-entity",
  takeover_claim_uuids: [],
  access_mode: "observer",
  authority_epoch: 1,
  expires_at: 4102444800,
}
```

Then call the real `startObjectiveDiagnostics()` with generation
`wp018-observer-generation` and session `wp018-observer-session`. No
event-stream, store write, HTTP call, fake response, or alternate start owner
may replace these production entry points.

### 4.4 Required local receipt

Read and return:

- `currentRuntimeConnection()`:
  - mode `hosted`;
  - game ID `wp018-observer-probe`;
  - session ID `wp018-observer-session`;
  - access mode `observer`;
- store objective state:
  - status `disabled`;
  - detail `no objective diagnostics client is bound`;
  - event count 0;
  - objective event cursor 0;
  - objective combat-log count 0;
  - objective combat-log cursor 0;
- `getRenderParitySnapshot().backend`:
  - status `disabled`;
  - reason `no active player runtime`;
  - response `null`;
  - actual non-null `checked_at` string.

After the page evaluation and one subsequent protocol round trip with no
timer/sleep, require:

- zero exact CDP request records;
- zero exact Playwright request records;
- zero exact request-failure records;
- zero page/console errors.

No timeout extension, fixed delay, retry, polling helper, or network-idle
substitute is allowed. The synchronous disabled receipt and the absence of a
bound client are the production authority; request journals are independent
negative evidence.

### 4.5 Participant and subjective preservation

Static combined review must prove:

- the participant path retains the exact pre-packet
  `bindObjectiveDiagnostics(connection.engine_base_url, headers)` call;
- `bindHostedRuntimeClients(...)` and its arguments are byte-identical and
  unconditional;
- `activeConnection` publication is byte-identical;
- `objectiveDiagnostics.ts`, `eventStream.ts`, replication modules, SDK, and
  server files are unchanged.

The review must not infer that the unchanged agent path is admin-capable.
Hosted-agent and any other non-observer/non-`ADMINISTER` diagnostics admission
remain explicitly unclaimed and deferred.

No synthetic participant request is issued. Such a request would introduce
intentional network errors and would not improve proof over the exact retained
branch plus the already frozen participant owner implementation.

## 5. Static gates and owner separation

### 5.1 Gate A

Fresh R1-R4 approval is required on this complete plan identity. No prior
scope vote, prior Plan Gate A vote, production-diff vote, or combined-surface
finding is technical approval of this revised plan.

### 5.2 Closed historical edit stages

The one-file production edit and its earlier 4/4 diff review are historical
completed evidence only. The Tester edit stage and failed byte-correction
attempts are also historical evidence only. They release no technical vote,
repeat edit, review shortcut, command, or execution under this plan.

Implementation and Tester remain `HOLD`. All four current surfaces are
immutable.

### 5.3 Fresh combined-static gate

After this wholly new plan identity passes fresh Gate A 4/4, R1-R4 must
independently review the exact immutable four-surface identity from Sections
1.2-1.3, including the complete new smoke and all four LF facts. Fresh
combined-static approval 4/4 plus Coordinator verification is required before
Section 6.

Any identity mismatch, unlisted byte, source drift, extra hunk, changed hosted
smoke/checker, broad package change, formatter/normalization, timeout, filter,
or extra file fails closed. No correction edit follows from static review.

## 6. One-shot governed execution

Execution is not released by plan approval. It requires the completed static
gates and a fresh Coordinator release.

### 6.1 Frozen prerequisites

From NeuroClient root, exactly once each, stopping on nonzero:

1. `./app/node_modules/.bin/tsc --noEmit -p ./app/tsconfig.json`;
2. `node --check app/scripts/hosted-observer-admin-diagnostics-smoke.mjs`;
3. `npm --prefix app run node-sources:check`;
4. `npm --prefix app run player-replication-boundary:smoke`, under one exact
   60-second outer owner.

The fourth command must exit 0 before its timeout, emit exactly one script
JSON payload in addition to the ordinary npm registered-command banner, keep
stderr empty, and report the existing exact
`objectiveDiagnosticsImporters` list containing only
`src/engine/eventStream.ts` and `src/engine/runtimeConnection.ts`. Any
nonzero, timeout, missing/malformed/duplicate script JSON, unexpected script
output, stderr, changed importer inventory, or prerequisite error consumes the
attempt with `NO RETRY`.

### 6.2 Preflight and evidence root

Invoke the exact previously approved stdin-only token-aware census from the
frozen WP-017 plan Section 6.2.1 exactly once, labeled `preflight`, without
copying, editing, extracting, piping, or transforming its program bytes.
Require its controls green, `errors=[]`, `matches=[]`, and only fully evidenced
reviewed systemd-PAM exclusions. Preserve its compact JSON byte/SHA receipt.

This is normative reuse of the already approved census command and literal
here-document, not reuse or retry of the consumed WP-017 product execution.
The execution owner opens the frozen plan authority and invokes that exact
command as printed; the program is not regenerated into this plan or a new
file.

Independently require port 5173 free. Do not inspect or touch any prior
retained root. Create one fresh attempt root matching:

`/tmp/neurodragon-wp018-observer-admin-diagnostics-*`

It owns only Vite stdout/stderr, smoke stdout/stderr, PID receipts, and census
receipts. Retain it on every exit.

### 6.3 Vite and focused smoke

Start exactly one recorded Vite using the repository's existing registered
Vite command on 127.0.0.1:5173. Require exact-root readiness. Do not start the
gateway, worker, preview server, port 8000, or any packet service.

Run exactly once under a 60-second recorded outer owner:

```sh
NEUROCLIENT_URL=http://127.0.0.1:5173 \
  npm --prefix app run hosted-observer-admin-diagnostics:smoke
```

Require exit 0, no timeout, exactly one final JSON object, every Section 4.4
receipt, zero classified request/error arrays, and browser/context close.

Any nonzero, missing field, unexpected request, browser error, malformed JSON,
or contradictory receipt consumes the attempt with `NO RETRY`. No alternate
probe, direct module call, follow-up command, timeout extension, or diagnosis
is authorized.

### 6.4 Teardown and final proof

Allow smoke browser `finally` first. Join only recorded smoke and Vite trees.
Use ordinary Vite shutdown, then recorded-tree-only termination if needed.
Require:

- recorded smoke/Vite PIDs and descendants absent;
- port 5173 closed;
- no owned filesystem artifact except retained logs/receipts;
- no access to earlier roots.

Invoke the exact same frozen stdin census once more after teardown, labeled
`post-teardown`, with a separate byte/SHA receipt and the same success rules.
Exactly two census invocations total are permitted.

Any cleanup mismatch freezes the attempt. No broad matcher, kill-by-name,
port killing, cleanup expansion, or third census is allowed.

## 7. Gate B acceptance

Gate B requires all of the following on one frozen combined identity:

- fresh plan Gate A 4/4;
- exact immutable four-surface combined-static approval 4/4;
- all four current hashes and all four enumerated LF facts unchanged;
- no repeat production or Tester edit/review stage;
- prerequisites green once;
- registered player-replication-boundary smoke green once with its exact
  importer inventory;
- preflight census green once;
- focused smoke green once;
- exact local disabled/parity/runtime receipts;
- zero observer admin-diagnostics requests;
- zero browser errors;
- teardown and final census green once;
- no unrelated edit, command, retry, or retained-root access.

Gate B may accept only the strict B1 claim in Section 0.3.

## 8. Performance and architecture

Production hot-path cost is one access-mode branch during hosted runtime
binding. Observer mode avoids two long-lived diagnostics tasks and their
network traffic. Participant cost and behavior are unchanged. No Gate B claim
is made about hosted-agent diagnostics admission; that separate seam remains
deferred even though this exact observer-only branch does not edit it.

The focused smoke performs constant work: one page, one production binding,
one diagnostics start, bounded snapshots, and two exact empty request
journals. Census cost is the already reviewed bounded same-euid process scan.
The additional registered ownership-smoke prerequisite is the existing
bounded static TypeScript ownership scan, invoked once and never on a product
hot path.

No adapter, parallel status owner, schema, API, persistence, dependency,
service, background worker, serializer, or framework is added.

## 9. Deferred and forbidden work

- A available-actions request identity remains a separate observation packet.
- B2 observer portrait identity remains a separate observation packet.
- hosted-agent and any other non-observer connection lacking `ADMINISTER`
  diagnostics admission remain a separate deferred candidate requiring fresh
  scope classification and a normal gate if later selected;
- WP-017 may not be retried.
- WP-016 SELF/TARGET, inventory three, multi-character seven, and unavailable
  sentinels remain deferred.
- no browser-error allowlist or expected-noise classification is introduced.
- no gateway/server authorization change is allowed.
- no CRLF reconstruction, line-ending edit, formatter normalization, generic
  whitespace waiver, or alternate file-write mechanism is allowed.

## 10. Mandatory Gate A questions

Every reviewer must answer all questions on the same frozen plan identity.

1. Does the plan truthfully keep WP-017 consumed non-green and NO RETRY?
2. Does it keep A and B2 separate and untouched?
3. Are the two 403 routes conclusively admin diagnostics rather than portrait
   resources?
4. Does observer access mode already lack ADMINISTER authority?
5. Is server 403 enforcement correct and frozen?
6. Does `bindHostedRuntime()` already own the authoritative access mode?
7. Is `bindHostedRuntimeClients(...)` independent of objective diagnostics?
8. Does the correction preserve that subjective binding unconditionally?
9. Is exact observer-only branching the smallest production correction?
10. Does `stopObjectiveDiagnostics()` retire the sole diagnostics client?
11. Does the later null-client start path return before both network owners?
12. Is `disabled / no objective diagnostics client is bound` existing source
    truth rather than a fabricated receipt?
13. Is backend parity `disabled / no active player runtime / null response`
    the exact retained source truth?
14. Does the plan avoid a fabricated HTTP unauthorized result?
15. Does participant binding retain the exact existing call while hosted-agent
    and other non-observer/non-`ADMINISTER` admission is explicitly unclaimed
    and deferred?
16. Are objectiveDiagnostics, eventStream, store, parity, SDK, and server files
    frozen?
17. Is the exact current one-file production identity sufficient without a
    repeat edit or production-diff gate?
18. Is the focused smoke isolated from `main.ts` and the consumed hosted smoke?
19. Does isolation avoid bundling A and B2?
20. Does the smoke call the real production bind and start entry points?
21. Is the synthetic connection limited to fields actually read?
22. Can a conforming run avoid contacting the unserved probe origin entirely?
23. Do CDP and Playwright journals observe without intercepting or mutating?
24. Are the two forbidden paths exact and bounded?
25. Does counting every method prevent a hidden preflight request?
26. Are objective history/cursors independently proved empty and disabled?
27. Is the backend parity receipt independently read from its production owner?
28. Are runtime game/session/access-mode values actual observations?
29. Is zero request evidence independent of the local status receipt?
30. Does any request, console error, page error, missing field, or nonzero fail?
31. Are context/browser finally and JSON-after-finally preserved?
32. Is the new registration the only logical package change?
33. Are the hosted smoke/checker and every unrelated smoke frozen, with only
    the exact current ownership-smoke import expectation present and immutable?
34. Are the production and Tester edit stages historical-only, with fresh
    plan and exact combined-static gates before every command?
35. Are tsc, node syntax, node-sources, the registered ownership smoke, and one
    focused observer smoke sufficient?
36. Does the execution avoid gateway, worker, port 8000, database, and UDS?
37. Are one recorded Vite, one 60-second focused browser-smoke owner, and the
    one bounded registered ownership-smoke prerequisite sufficient?
38. Are exactly two already-approved census invocations retained without
    protocol revision?
39. Are recorded PID/descendant and port proofs sufficient for this topology?
40. Is the fresh root retained and every earlier root protected?
41. Does the plan forbid retry, alternate probe, timeout extension, filtering,
    cleanup expansion, and any further line-ending edit?
42. Is production cost one cold binding branch with no participant hot-path
    change and no claim about the deferred agent seam?
43. Are all four current line/byte/SHA identities frozen exactly?
44. Are the four LF terminator facts exhaustive, explicit, and non-semantic?
45. Does the plan forbid every generic whitespace/platform/formatter/future
    waiver and close the failed CRLF edit path historically?
46. Is fresh revised-plan Gate A followed by fresh exact combined-static 4/4,
    with no edit stage or vote carry, fail-closed?
47. Does the packet add no API/schema/SDK/server-policy/persistence/dependency
    or human product decision?
48. Is the strict claim limited to observer admin-diagnostics admission?
49. Do all prior deferrals and the newly explicit hosted-agent admission seam
    remain frozen?
50. Is any remaining blocker concrete rather than speculative?

## 11. Owner matrix

| Stage | Owner | Authorized surface | Stop condition |
| --- | --- | --- | --- |
| Plan Gate A | R1-R4 via Planner | this plan only | any non-approval |
| Combined static | R1-R4 via Planner | exact immutable four-surface identity and four LF facts | any non-approval or byte drift |
| One-shot execution | Tester | Section 6 only | any nonzero or mismatch |
| Gate B | R1-R4 via Planner | exact receipt only | any missing/contradictory evidence |

Production and Tester edit stages are closed historical evidence and have no
active owner-matrix row. No owner may authorize itself, inherit a prior vote,
combine A/B2, normalize bytes, or expand scope after a failure.
