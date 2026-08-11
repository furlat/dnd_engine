# Gameplay Regression Work Packet 012 — Frontend Render-Parity Fault Chronology Evidence

Date: 2026-08-11  
Owner: Planner / External Reviewer 1  
Execution owner: Tester only after public Gate A 4/4 and Coordinator release  
Implementation owner: HOLD; no production edit is authorized by this packet

## 0. Decision and boundary

WP-011 corrected the selected BUG-031 readiness boundary and produced a
truthful resolved receipt, but its governed one-shot remained non-green. The
inherited console gate captured two production presentation faults:

`[presentation-fault] control_plane_failure: frontend render parity failed`

Terminal render parity later converged to backend/frontend `pass/pass`. Frozen
source inspection proves that later convergence does not acknowledge or remove
an earlier fault. The production fault owner persists the fault with
`reconciliation: null`; only an indiscriminate diagnostics clear removes it.

The consumed receipt did not retain the structured `runtime.mismatches`, fault
signature, trace lineage, or exact action checkpoint at which each fault first
appeared. A scheduling or recovery change would therefore be speculative.

This evidence-only packet changes exactly one existing Tester file:

`/home/tommaso/Dev/NeuroClient/app/scripts/live-subjective-actions-smoke.mjs`

It adds observation-only diagnostic checkpoints around the already-maintained
action chronology. It does not alter the existing console/page failure gate,
clear or suppress a fault, modify product code, or claim WP-011 green.

### 0.1 Human authorization and automatic progression

The human authorized the production diagnostic-owner path and directed that
routine bounded evidence/fix packets progress automatically. This packet is
the first evidence phase of that path. It may be followed by a separately
frozen production-owner fix only after the structured result identifies the
causal owner.

### 0.2 Consumed WP-011 evidence

The WP-011 attempt is consumed and cannot be rerun under its identity.

- focused tsc: once, exit 0;
- checker: once, exit 0;
- one fresh no-force standalone stack;
- live-subjective smoke: once, exit 1 without timeout;
- fixture/readiness: passed, including eight resolved attempts over
  1351.608341 ms and equal active/actions UUIDs;
- inherited Jump, Move, equipment, reset, objective-debug, and terminal parity
  receipts: completed;
- exact failure: two open frontend render-parity presentation faults;
- teardown: complete.

Evidence root `/tmp/neurodragon-wp011-green-KZW8go` remains retained and is a
forbidden target for this packet. All earlier retained roots are likewise
forbidden.

### 0.3 Non-claims

This packet does not claim:

- WP-011 green or BUG-031 Stage 4 closure;
- that a transient mismatch is harmless;
- that terminal parity acknowledges an earlier fault;
- a render-parity scheduling fix;
- a recovery or reconciliation contract;
- Jump, Move, equipment, reset, replication, or rendering correctness;
- production, backend, service, schema, persistence, protocol, or public-
  contract correctness.

## 1. Frozen authorities

All identities below are read-only authorities. Any mismatch fails intake
closed and returns to Planner; no automatic refresh is allowed.

### 1.1 Predecessor and mutable Tester authority

| File | Lines | SHA-256 |
|---|---:|---|
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_WORK_PACKET_011_BUG_031_SUBJECTIVE_ACTION_READINESS_RESOLVED_WAIT_2026-08-11.md` | 428 | `1e7925843ff2832664e0e8eb99f1a7bac5e27cee02586cad5bf3e067af13fca0` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/check-node-sources.mjs` | 100 | `d46c4d12a5d23f4a2a496bafc544a7a8b7ac499e89c4496a00e564b88689c3d1` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/live-subjective-actions-smoke.mjs` | 710 | `517dc7ea1ba92a606e19c782e0fb825616f9959fed6ba5b7ee54510a3376425d` |
| `/home/tommaso/Dev/NeuroClient/app/package.json` | 165 | `36515d20ea94ebc0c49a47b79bd455fee0eddceea2eb5e52713163eff159d9e3` |

Only the 710-line smoke is mutable after Gate A. The checker, package, and
WP-011 plan remain byte-frozen.

### 1.2 Production diagnostic and presentation owners

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/src/render/renderParity.ts` | 720 | `6ae2d160a292e30e75a060443feebad0be603dbc93a7b0c8189a022d3e809b58` |
| `/home/tommaso/Dev/NeuroClient/app/src/render/presentationDiagnostics.ts` | 1264 | `4271e3b7711b8964212f9d0994877768c386c1ac359b476f5c3b94d3d8233f69` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/eventIngestion.ts` | 935 | `c05d9b3eb83f907608f41c6ee1df56b3ce08732a9fd1aaca1250850f41b86828` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/stateSync.ts` | 612 | `030308d2e949c9404b61ad9238635cc83311e87c741f5da8432cdcc3d077a969` |
| `/home/tommaso/Dev/NeuroClient/app/src/render/sceneRenderer.ts` | 797 | `60adef2ecc5935efaf48890ea8d7df8c374635402cb1b629d2c572e4a48b35fc` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/eventStream.ts` | 974 | `912ef41889c5a1a753d8969037550e3fabc6ecbd126e1d417e4cced6290fd522` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/store.ts` | 431 | `b0c428f266cf3c23608143e3ee73fc048f82bfb0afb5ffee3e317b1aff859537` |
| `/home/tommaso/Dev/NeuroClient/app/src/api/actions.ts` | 111 | `857d866984ac43699d019aa4490dfa2cd0ff1fa68d82b961cb2b1a0112503462` |
| `/home/tommaso/Dev/NeuroClient/app/src/api/equipment.ts` | 79 | `2ddbf96158473cb04973c648c414d6d2db7fd976081687f4d4b61ee41ed7e5e8` |

These production owners remain byte-frozen. The smoke observes their existing
diagnostic snapshot and parity snapshot APIs.

### 1.3 Runtime and service authorities

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/vite.config.ts` | 235 | `7d70b9fae8cf5d4a8d38762865ac8f36adba1247721212fcb5b3d7455f247153` |
| `server/event_server.py` | 6978 | `eb1f6e891bc4cb149c8f054bb8ae36e4df7f2a7a7d47e6cc91af2a3e7394cdc5` |

`package.json:25` directly registers `live-subjective-actions:smoke` as the
selected Node script. The backend must launch directly through the repository
venv without `--force`. `server.sh` is not a governed launcher.

## 2. Frozen causal finding

### 2.1 Fault emission

`renderParity.ts` records an open `control_plane_failure` for each distinct
frontend mismatch signature. The fault runtime already contains projection,
compared path count, and the exact mismatch rows. A later pass only resets the
in-memory de-duplication signature.

### 2.2 Fault persistence

`presentationDiagnostics.ts` records the fault with:

- exact id and timestamp;
- kind and message;
- serialized error and diagnostic code;
- root cue, frame, transaction, and intent when present;
- runtime evidence;
- recent trace with sequence, timestamp, phase, observation cursor, root
  lineage, and detail;
- `reconciliation: null`.

No source-backed fault-specific recovery transition exists. The diagnostics UI
describes such a fault as open. `clearPresentationDiagnostics()` erases the
whole ledger and is not acknowledgement.

### 2.3 Ordering ambiguity

The product claims the expected world is installed only after a visual
transaction drains, and parity sampling is microtask-scheduled after the
current stack. The prior receipt proves a mismatch was nevertheless sampled.
Without the structured mismatch and first-observed action checkpoint, source
inspection cannot distinguish:

1. an expected-world scheduling defect;
2. a scene/Pixi settlement defect;
3. an equipment/appearance projection defect;
4. a parity observer defect;
5. a genuine transient invariant violation that later recovers.

The evidence packet must discriminate these without changing the owner.

## 3. Required evidence contract

### 3.1 Observation-only checkpoint helper

Inside the existing large `page.evaluate`, add a file-local browser-side helper
`capturePresentationCheckpoint(label)` using only the already imported:

- `getPresentationDiagnosticsSnapshot`;
- `getRenderParitySnapshot`;
- production `store`.

The helper must not call a parity check, clear diagnostics, write the store,
change a renderer, wait, or mutate a production object.

For each checkpoint, append one JSON-serializable record containing actual:

1. `label`;
2. checkpoint ISO timestamp;
3. client state, replication generation, presentation event/combat-log
   cursors, backlog, and active entity UUID;
4. backend parity status/reason/checked-at and response identity/cursor fields
   when present;
5. frontend parity status/reason/checked-at/projection and exact mismatches;
6. the exact frontend signature derived with the production algorithm
   `path + ":" + actual_json`, joined by `|`, or null when no mismatch;
7. complete currently open presentation faults, preserving every existing
   fault field;
8. `newFaultIds` and `newFaults` relative only to earlier checkpoints in this
   page evaluation;
9. for each new frontend parity fault, a derived mismatch signature from its
   existing `runtime.mismatches`, without changing the fault object;
10. the current diagnostics trace tail with its existing sequence, phase,
    observation cursor, root lineage, and detail.

The helper may maintain only a local `Set` of previously observed fault ids and
a local checkpoint array. This is test-owned observation state, not product
state.

### 3.2 Exact chronology

Capture checkpoints in this exact order without reordering the inherited work:

1. `before_jump`;
2. `after_jump` immediately after Jump returns;
3. `after_move` immediately after Move returns;
4. `after_equipment` immediately after equipment returns;
5. `before_replica_reset` immediately before the inherited reset helper;
6. `after_replica_reset` immediately after it returns;
7. `after_objective_debug` immediately after objective-debug isolation;
8. `after_terminal_render_parity` immediately after terminal parity returns.

The existing reset helper continues to call `clearPresentationDiagnostics()`.
The earlier checkpoint objects must retain their copied/serializable fault
evidence after that clear. No new clear is added.

### 3.3 Final output

Add exactly one new top-level result field:

`presentationFaultChronology`

It contains the ordered checkpoint array. All WP-011 fields and inherited
result keys remain unchanged.

### 3.4 Existing failure semantics

Preserve without weakening:

- pre-navigation console and page-error listeners;
- console errors as final failures;
- every production presentation fault as a console error;
- the inherited reset diagnostic assertion;
- terminal parity convergence assertion;
- final failure aggregation and nonzero exit;
- browser `finally` cleanup.

The new evidence is emitted before the existing failure aggregation, exactly
as the current result JSON is. It never converts a failing smoke to green.

## 4. Authorized Tester edit

After Gate A 4/4 plus Coordinator verification, Tester may edit only:

`/home/tommaso/Dev/NeuroClient/app/scripts/live-subjective-actions-smoke.mjs`

The edit is limited to Sections 3.1–3.3. Tester runs no command during the edit
phase and returns exact diff, line count, SHA-256, diff-check, and hunk
confinement.

Checker, package, production, service, SDK, generated, schema, persistence,
protocol, dependency, and every other smoke remain frozen.

## 5. Static review

The changed smoke requires fresh isolated R1-R4 static approval. Reviewers must
prove:

1. observation-only behavior;
2. exact checkpoint ordering;
3. complete fault/runtime/trace preservation;
4. correct production-compatible signature derivation;
5. evidence survives the inherited ledger clear only in local test records;
6. no failure suppression or acceptance change;
7. all WP-011 and inherited behavior remains present;
8. constant bounded test-only cost;
9. production authorities remain byte-frozen;
10. the packet makes only an evidence claim.

No execution is released before public static 4/4 plus Coordinator verification.

## 6. Governed diagnostic execution

### 6.1 Prerequisites

From NeuroClient root, exactly once each and stop on unexpected result:

1. `./app/node_modules/.bin/tsc --noEmit -p ./app/tsconfig.json`;
2. `npm --prefix app run node-sources:check`.

Both must exit zero. No alternate or aggregate command is authorized.

### 6.2 Fresh stack

Only after prerequisites pass:

1. prove ports 8000/5173 and matching packet processes absent;
2. create one brand-new disposable `/tmp` runtime root;
3. from dnd_engine root launch exactly one owned backend, without `--force`:

   `DND_LOCAL_PROFILE_RUNTIME_ROOT=<brand-new> ./.venv/bin/python -m server.event_server --host 127.0.0.1 --port 8000`

4. require direct `/server/capabilities` HTTP 200 and
   `server_mode=standalone` within 90 seconds;
5. start exactly one owned registered Vite and require exact-root HTTP 200
   within its bounded window;
6. run `npm --prefix app run live-subjective-actions:smoke` exactly once as one
   recorded process session under an exact 300-second outer wall clock.

A bind-race loss, timeout, missing output, or unrelated failure freezes. No
rerun, alternate probe, force launcher, ambient service, or retained root is
allowed.

### 6.3 Evidence outcomes

Exactly one final JSON containing the complete inherited result plus
`presentationFaultChronology` is required.

Outcome A — reproduced structured fault:

- smoke may exit nonzero only through the unchanged console-error aggregation;
- every accepted console presentation fault must have the exact structured
  fault id in the chronology;
- at least one new fault must be kind `control_plane_failure`, message
  `frontend render parity failed`, reconciliation null, with a nonempty exact
  `runtime.mismatches` array and derived signature;
- the first checkpoint containing each new fault identifies the causal action
  interval;
- trace lineage and cursor evidence must be retained;
- all unrelated inherited assertions must complete or the result freezes.

Outcome B — no reproduction:

- smoke exits zero;
- chronology has zero presentation faults at every checkpoint;
- all inherited assertions and error gates pass;
- classification is `not_reproduced_once`, not product green and not fault
  resolution.

Any other nonzero, malformed chronology, missing fault correlation, page error,
unrelated console error, or inherited assertion failure freezes as unexpected.

### 6.4 Teardown

On every exit:

1. allow the smoke's browser `finally` to run;
2. terminate/join only a still-active recorded smoke tree;
3. stop/join only the owned Vite and backend trees;
4. prove ports 8000/5173 closed;
5. prove every recorded PID/child and matching Playwright, Chromium, smoke,
   Vite, and event-server process absent;
6. remove only the exact owned runtime if deletion is explicitly part of the
   governed runner; otherwise retain it.

Never touch `/tmp/neurodragon-wp011-green-KZW8go` or any earlier retained root.

## 7. Acceptance and successor routing

This packet is complete only when the one governed result is accepted by fresh
R1-R4 evidence review plus Coordinator verification.

Acceptance means only that structured causal evidence was captured (or one
lawful non-reproduction was recorded). It does not close WP-011 or accept a
production fix.

After Outcome A, Planner must use the exact first-fault checkpoint, mismatch
paths/signature, runtime, trace lineage, and cursor chronology to select the
smallest production owner:

- parity scheduling/expected-world owner;
- scene settlement owner;
- appearance/equipment projection owner;
- parity observer owner;
- explicit recovery owner only if evidence proves a lawful recovery lifecycle.

The production fix receives a new work packet and fresh Gate A. After Outcome
B, Planner must determine whether another bounded deterministic evidence seam
exists; no blind repeat is authorized.

## 8. Prohibited shortcuts

- no text filtering of console faults;
- no clearing or mutating `consoleErrors`;
- no extra `clearPresentationDiagnostics()`;
- no mutation of a fault or its reconciliation field;
- no final-pass-overrides-fault rule;
- no direct parity check added at a checkpoint;
- no artificial sleep to provoke or hide a fault;
- no route interception, response fixture, store write, or mocked diagnostic;
- no retained-runtime reuse or inspection;
- no production/package/service edit;
- no second smoke or shared diagnostic framework;
- no rerun, debug command, formatter, dependency action, or workaround.

## 9. Performance and architecture

The packet adds eight snapshots in one diagnostic smoke. State is bounded by
the existing diagnostics maximums plus one local checkpoint array and one fault
id set. It adds no product hot-path work and changes no allocation owner,
runtime contract, serialization, schema, persistence, or public export.

The temporary duplication is deliberate observation at a test boundary. It
must not become a shared framework before the production causal owner is known.

## 10. Gate and owner matrix

| Stage | Owner | Authorized work |
|---|---|---|
| Plan Gate A | R1-R4 | Review this exact frozen plan only |
| Edit | Tester | One smoke, Sections 3.1–3.3 only |
| Combined static | R1-R4 | Review frozen changed smoke |
| Diagnostic run | Tester | Exact Section 6 sequence once |
| Evidence acceptance | R1-R4 | Classify Outcome A/B and causal sufficiency |
| Successor plan | Planner | Freeze owner-correct production packet |
| Production implementation | Implementation | HOLD until successor Gate A 4/4 |

Coordinator performs governance verification and casts no technical vote.

## 11. Mandatory Gate A questions

Reviewers must answer all questions on the identical frozen packet.

1. Does package.json directly register the selected smoke?
2. Is the prior WP-011 failure receipt preserved as non-green?
3. Does source prove later parity pass does not reconcile an earlier fault?
4. Does source prove a recorded fault has complete runtime and recent-trace data?
5. Does source prove `reconciliation` remains null absent a missing owner?
6. Is whole-ledger clear distinct from fault-specific acknowledgement?
7. Is a production fix unsafe without the missing mismatch/action chronology?
8. Does the packet edit only one existing Tester smoke?
9. Does the checkpoint helper remain read-only?
10. Are all eight checkpoint labels and order exact?
11. Are pre-reset faults retained in local evidence despite inherited clear?
12. Are exact fault ids correlated to first-observed checkpoints?
13. Is the production-compatible mismatch signature derived without mutation?
14. Are runtime mismatches, reconciliation, trace lineage, and cursors retained?
15. Does the packet avoid calling a parity check or adding timing perturbation?
16. Does final output add only presentationFaultChronology?
17. Do console/page error gates remain fatal and unchanged?
18. Do all WP-011 fixture/readiness fields remain present?
19. Do inherited Jump/Move/equipment/reset/objective/parity receipts remain?
20. Can Outcome A accept only the unchanged console-failure path plus structured
    correlation, not green?
21. Can Outcome B claim only one non-reproduction, not resolution?
22. Are all other outcomes fail-closed?
23. Is one focused tsc, one checker, and one bounded smoke sufficient?
24. Is the direct no-force backend launcher ownership-safe?
25. Is the smoke process enforceably bounded to 300 seconds?
26. Is teardown exclusive to recorded owned trees?
27. Are retained roots forbidden and preserved?
28. Is runtime/memory work bounded and Tester-only?
29. Are production/package/contracts/schema/persistence unchanged?
30. Does the successor require fresh Gate A before any production fix?
31. Is any human product choice still implicated at this evidence stage?
32. Is there any concrete false-evidence, cleanup, scope, or architecture blocker?

Only an unconditional approval on all answers contributes to Gate A.
