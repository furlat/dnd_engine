# Gameplay Regression Work Packet 004

## BUG-010 Stage 1: cue-less visible-position terminal settlement

Status: **REVISION 3 DRAFT FOR GATE A REVIEW — NO IMPLEMENTATION OR EXECUTION AUTHORIZED**

Date: 2026-08-10

Revision: 3

Owner: Planner / External Reviewer 1

This packet is inside the already authorized BUG-001--BUG-034 gameplay-
regression program. It follows the accepted causal sequence after WP-003:
visible position patches must reach an explicit state-only presentation
settlement before the SDK journal advances.

This is deliberately only BUG-010 Stage 1. It covers a retained visible actor
whose final position arrives through an `entity_upsert` in a NORMAL frame that
produces no visual transaction. It does not address BUG-011's separate case
where a movement or forced-movement cue animates one endpoint but a later fact
in the same frame makes another coordinate terminal. That later supersession
requires a fresh packet and Gate A.

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
| accepted WP-003 plan | 601 | `612aed71deea05b7c7e448c76c1a3bd355c64d4cf68758d8b87851d4f30af827` |

The regression ledger says:

- a visible entity position patch may lawfully arrive without a movement cue;
- every disclosed visible movement requires a lawful visual or an explicit
  state-only presentation disposition;
- the client must not infer a hidden path or treat cue order as terminal world
  authority.

The causal study selects this family next: visible position patch to
movement/state-only settlement, BUG-010/011.

### 1.2 Authorized NeuroClient production surface

Repository: `/home/tommaso/Dev/NeuroClient`

| File | Lines | SHA-256 | Baseline note |
| --- | ---: | --- | --- |
| `app/src/engine/eventIngestion.ts` | 921 | `30b76e8dc47de40c957f713070e59853d4097c7b701f958879e7bcbef992f800` | contains accepted prior-work edits; preserve every unrelated hunk |
| `app/src/render/sceneRenderer.ts` | 756 | `7673f26d639c41713a1e32cfece29cd144d83a033253216913e9ee65f9e261b3` | current scene/barrier authority |

Implementation may edit exactly these two files and no others.

### 1.3 Authorized Tester surface

| File | Lines | SHA-256 |
| --- | ---: | --- |
| `app/scripts/presentation-head-drain-live-smoke.mjs` | 811 | `ed509777fed3180300b69af9157cabb3c2f6924bd41f0b70f4f272c013c2222b` |

Tester may edit exactly this existing registered smoke and no other file.

### 1.4 Frozen supporting authorities

These files are read-only proof authorities and must remain byte-identical:

| File | Lines | SHA-256 |
| --- | ---: | --- |
| `app/src/engine/stateSync.ts` | 612 | `030308d2e949c9404b61ad9238635cc83311e87c741f5da8432cdcc3d077a969` |
| `app/src/render/visualEntityRegistry.ts` | 34 | `ab87c84a9dc1de270529ca0bceca21030d6bb60e89d600b49c86a4eb05541c54` |
| `app/package.json` | 165 | `36515d20ea94ebc0c49a47b79bd455fee0eddceea2eb5e52713163eff159d9e3` |
| `sdk/typescript/src/subjectiveJournal.ts` | 842 | `fa0cc0c3aa86a391ae84845ec77d39d3c3363fa9af0905d6cc81e95c2c398e54` |
| `sdk/typescript/src/subjectiveSse.ts` | 1303 | `1c711f181decac37a033d498929acacda8524735321767ab712c8f84661b958f` |
| `sdk/typescript/src/tests/fixtures.ts` | 298 | `722878db4396dcfb522f7e92c7905d4ba9d97a2ec07f88d410a32a16c1611a7a` |
| `server/player_replication/mapper.py` | 4136 | `9c1195d5fa8b4ca0eda000e3739fda9058e0762a48efd7d3bddbdb9215f168f1` |
| `server/player_replication_contract.py` | 2481 | `6c3639a0bea5de33b08f7405c42c20c3818d3e7c1e587e9cd509a5441ad9d3b6` |
| `server/agent_runtime/observation_journal.py` | 2059 | `10eb9b3479d1af7fede7e97ed8f273923abaea5ca4b570dd7f40fbf395389344` |
| `tests/manual/test_121_canonical_presentation_mapper.py` | 4146 | `8f34e0a1861ec1ac6a014ac47899c4a3eb2703b7448ef2e0024301a168f3638e` |
| `tests/manual/test_122_canonical_replication_runtime.py` | 1994 | `3c5614a2c73eee2df370f89a3b6f24f5dc69c158e136fba7080a86a14000f743` |

`app/package.json` and `app/src/engine/eventIngestion.ts` are already modified
in the shared worktree by accepted earlier packets. Their hashes above, not a
clean `HEAD`, are this packet's baselines. No owner may normalize or revert
those accepted changes.

---

## 2. Exact problem and current causal path

### 2.1 Lawful producer behavior

The backend visibility boundary is intentionally privacy-safe:

1. `server/agent_runtime/observation_journal.py` may publish an entity upsert
   containing the final known position when the destination is visible;
2. `server/player_replication/mapper.py::_step_geometry_allowed` emits a
   movement cue only when one authorized observer saw both step endpoints, or
   the mover is controlled;
3. therefore a retained visible actor may lawfully receive a new position in
   frame patches while the same frame contains no movement cue.

This packet must not weaken that privacy rule. It must not disclose the hidden
origin, fabricate an anchor sequence, or cause the server to emit a cue whose
geometry was not authorized.

### 2.2 SDK behavior is already correct

`SubjectiveReplicationJournal.previewPresentationFrame` reduces the frozen
NORMAL frame patches into `candidatePresentation`. The candidate is the sole
already-validated post-frame world. The journal does not invent animation and
does not commit until the client spends the opaque preview token.

A cue-less entity upsert is therefore a lawful SDK state transition, not an
SDK error and not an absent update.

### 2.3 Current NeuroClient failure

For one cue-less NORMAL frame:

1. `PresentationHeadDrain.consumeNormalHead` previews the exact candidate;
2. `planLivePresentationFrame` returns `kind: "state_only"` because there is
   no visual transaction;
3. staging preserves the already-presented actor;
4. the current code skips the visual-transaction barrier entirely;
5. the exact journal token commits and `applySubjectiveReplicaView` installs
   the new entity position in the store;
6. `sceneRenderer` deliberately refuses to copy store positions onto existing
   visual entities because ordinary movement is clip-driven;
7. the retained Pixi/AnimatedEntity therefore remains at the old coordinate.

The journal and store advance while the visible actor does not. This is the
direct BUG-010 state-only settlement gap.

### 2.4 Why the usual alternatives are wrong

- Emitting a movement cue is wrong when the origin/path was hidden.
- Reusing `MoveIntent`, `SlideIntent`, `ForcedMoveIntent`, or `JumpIntent`
  invents trajectory, timing, facing, or causal ownership not present in the
  frame.
- Reading the store position in the ordinary scene subscription would bypass
  the presentation head and could teleport an actor before a lawful movement
  clip begins.
- Snapping every actor after every visual transaction would silently mask
  BUG-011 and other animation failures. That broader policy is not authorized.
- Adding a wire field, SDK patch, schema, or persisted disposition changes the
  public contract and is unnecessary for this internal receipt.

---

## 3. Accepted boundary and objective

### 3.1 Exact accepted input

One generated-SDK-valid NORMAL head with:

- one retained visible entity already materialized in the visual registry;
- one `entity_upsert` whose candidate position differs from both the retained
  visual coordinate and that actor's pre-frame presented-store coordinate;
- no presentation cues and therefore no visual transaction;
- a candidate presentation in which that retained entity owns the new final
  coordinate.

### 3.2 Exact output

Before the opaque journal token commits, NeuroClient must perform one explicit
state-only terminal settlement:

- identify only entity UUIDs named by `entity_upsert` patches;
- require the staged presented-store entity to exist and its preserved
  pre-frame position to differ from the candidate position;
- resolve their final coordinates from the already-reduced candidate world;
- ignore an upserted entity which is absent from the final candidate because
  a later patch removed it;
- ignore a newly admitted entity and an upsert which changes only HP, name,
  appearance, or another non-position field;
- require a retained final entity to have a registered visual actor;
- call that actor's existing `setGridPosition` only when its current grid
  coordinate differs from the candidate coordinate;
- expose no path, duration, facing, VFX, body clip, or target lookup;
- fail the presentation head rather than silently skip a missing retained
  visual actor.

The operation is synchronous, exact-coordinate, and terminal. It is not an
animation.

### 3.3 Stage boundary

This Stage 1 packet applies the settlement only when the frozen plan is
`state_only` **and** the exact frame has `presentation.length === 0`. The
caller-owned conjunction is the admission boundary; the scene helper does not
reclassify plans or cues. It does not run for a nonempty state-only cue frame
or after a visual transaction. A nonempty door/light/spatial-effect state-only
frame which also carries a position upsert is deferred, as is a frame
containing a movement/forced-movement/other visual cue plus a later terminal
position. Those require later packets and fresh Gate A.

---

## 4. Production algorithm

### 4.1 `app/src/render/sceneRenderer.ts`

Add one narrowly named exported internal function owned by the scene boundary,
for example `settleStateOnlyEntityPositionPatches`.

Inputs must be the exact frozen `SubjectiveReplicationFrame` and its
already-reduced `ReplicatedRenderWorld` candidate. The helper may read the
staged presented-store `store.entitiesById` only as the position-delta witness.
For an existing actor, staging preserves the pre-frame presented row; a newly
admitted actor is staged from the candidate and therefore has no delta under
this comparison. Do not accept raw JSON, a caller-supplied position, a callback
that can invent positions, or a second reducer.

Algorithm:

1. scan `frame.patches` once and collect only UUIDs from
   `kind === "entity_upsert"`;
2. if that set is empty, return without scanning candidate entities;
3. index the already-reduced candidate entity rows by UUID once;
4. for each collected UUID:
   - if no candidate entity remains, continue because final reduction removed
     it;
   - read the existing staged presented-store entity for that UUID;
   - if no presented entity exists, continue because the UUID is outside this
     retained-actor packet;
   - if presented-store position equals candidate position, continue even if
     the visual actor is deliberately divergent; the current frame did not
     change position and must not repair an earlier transaction;
   - require the existing registry's visual entity;
   - if absent, throw an exact settlement error;
   - compare its current `gx`/`gy` with the candidate's two-number position;
   - call existing `setGridPosition(x, y)` exactly once only when different;
5. return `void` without mutating store, journal, queue, visibility,
   equipment, vitals, appearance, body state, or diagnostics authority.

The helper must not return a list, count, receipt DTO, or diagnostic value.
The live visual result is the evidence surface; no caller needs another API or
allocation.

The candidate world, not the patch payload or store, owns the terminal
coordinate. For a retained actor, the staged presented-store position is only
evidence that this exact frame changes position. This distinction prevents a
later HP/name-only full entity upsert from repairing a visual left stale by an
earlier visual transaction and thereby masking BUG-011. Candidate membership
still makes a later remove win over an earlier upsert.

This helper does not decide whether a frame is cue-less, state-only, or
otherwise admissible. It has exactly one caller-owned route in this packet,
and it must not become a second admission authority.

### 4.2 `app/src/engine/eventIngestion.ts`

Import the exact scene settlement owner without adding a reverse dependency.

Inside `consumeNormalHead`, after staging and exact-head recheck but before
`commitNormalOnce`:

1. run the settlement only when both `plan.kind === "state_only"` and
   `preview.frame.presentation.length === 0`;
2. pass exactly `preview.frame` and the already-projected `renderWorld`;
3. require the active owner/incarnation to remain current before mutation;
4. treat any settlement exception as the existing presentation barrier
   failure, preserving the one blocked/recovery path;
5. never call it for `visual_transaction` in this packet;
6. never call it for a nonempty state-only cue frame;
7. never call it for RESET handling;
8. then spend the same opaque journal token once through the existing commit
   path.

Do not change SDK preview/commit ordering, head identity checks, staging token
ownership, recovery latching, state synchronization, diagnostics isolation,
or reset behavior.

### 4.3 Failure atomicity

The state-only settlement happens only after the exact queue head and live
consumer identity have passed the existing precommit recheck. It is
synchronous, so another attachment cannot interleave inside the operation.

If settlement fails, the head remains uncommitted and the existing recovery
latch owns replacement. Do not catch and continue, retry locally, or commit a
store coordinate which the retained visual actor did not accept.

### 4.4 Performance and allocation

The hot path must remain:

- O(P + E) for the state-only frame only, where P is patch count and E is the
  already-reduced candidate entity count; the candidate index is built only
  when at least one entity upsert exists;
- one short-lived UUID set and, if needed, one short-lived candidate index;
- zero new traversal of presentation cues, scene children, tiles, objects, or
  the global Pixi graph;
- zero timer, RAF, Promise, queue transaction, animation asset, cache,
  registry, or persistent allocation;
- no entity-by-coordinate lookup.

Reviewers should reject an O(P*E) repeated `find`, a full scene scan, or a
generic post-frame snap pass.

---

## 5. Tester assignment

Tester edits exactly:

`/home/tommaso/Dev/NeuroClient/app/scripts/presentation-head-drain-live-smoke.mjs`

Tester runs nothing during the edit-only phase and returns only the exact diff,
line count, and SHA-256.

### 5.1 Fixture placement

Append one independently named case after all current inherited head-drain
cases so the natural first red proves every existing case reached green first.
Use a fresh SDK journal generation and live attachment identity; do not reuse a
partially consumed prior case.

### 5.2 Real authority path

The case must use:

- the existing linked generated SDK and its real `replicationJournal`;
- `bootstrap`, `ingest`, `projectSubjectiveReplicationUpdate`, and
  `waitForPresentationHeadDrainIdle`;
- the production store/state projection path;
- the production `visualEntityRegistry` only to install one bounded visual
  double for the retained actor;
- no direct call to the new settlement function;
- no hand-authored plan, token, candidate world, drain result, or committed
  replica.

Python source inspection, not this client smoke, proves that a non-controlled
mover can have no common authorized witness for both endpoints while the final
position remains lawfully disclosed. The client smoke proves only the exact
generated-SDK receipt boundary after that privacy decision; it must not claim
to recreate backend event-time witness evidence.

### 5.3 Exact frame

Construct one SDK-valid NORMAL frame at observation cursor 1 with:

- the fresh generation's exact source stream, generation, and perspective
  identity;
- hero retained as the sole controlled observer;
- the fixture monster retained in world state and added to hero's
  `visible_entities` in the fresh bootstrap seed before journal bootstrap;
- an explicit pre-ingest assertion that monster is present in the projected
  visible-entity set and absent from `controlled_entity_uuids`;
- one `entity_upsert` for that same non-controlled monster;
- the same full entity row except for a discriminating position change, for
  example `[4, 0]` to `[5, 0]`;
- `presentation: []` and `presentation_from_cursor: 0`;
- presentation watermark unchanged at zero;
- no movement cue, no forced-movement cue, no reset, and no other patch;
- ordinary valid source/observation watermark progression.

The tested frame must contain no visibility patch or reveal/hide transition.
Monster is already visible at bootstrap and remains in the candidate visible-
entity set. Do not use the controlled hero as the mover: backend
`_step_geometry_allowed` always authorizes controlled movers, so hero cannot
represent the packet's privacy branch.

### 5.4 Visual double

Register one case-local visual double under the exact retained UUID. It must:

- start with `gx`/`gy` equal to the pre-frame coordinate;
- record every `setGridPosition` call and update `gx`/`gy` exactly;
- expose no movement, slide, facing, timer, asset, VFX, or entity-query logic;
- be unregistered in a case-local `finally` block.

The double is observation machinery only. It must not implement the settlement
policy, inspect patches, or read the candidate world.

### 5.5 Required assertions

After one ingest/update/drain:

1. SDK ingest status is `applied`;
2. the head drain is idle, unblocked, and has no active cursor;
3. presentation backlog is zero;
4. the SDK presentation replica owns the exact new coordinate;
5. the production store owns the same new coordinate;
6. the frame still has zero presentation cues;
7. final visual-double `gx`/`gy` equal that coordinate;
8. the visual double received exactly one `setGridPosition` call with the exact
   candidate coordinate;
9. no recovery request occurred;
10. no ClipQueue/intent lifecycle or invented movement proof is claimed.

The SDK replica and production-store assertions must precede the exact final
visual-position assertion. That visual-position assertion must be the first
new assertion that fails on unchanged production. Call count and cleanup
assertions follow it so the first red remains causal.

### 5.6 Required negative controls

In the same bounded case or a small adjacent case, prove without another run:

- an entity upsert whose candidate position equals the current visual
  position produces zero `setGridPosition` calls;
- a full entity upsert which changes a non-position field while the staged
  presented-store and candidate positions remain equal produces zero calls
  even when the visual double is deliberately placed at a different
  coordinate; this proves the current frame cannot repair an earlier visual
  mismatch;
- a cue-less state-only frame with no entity upsert does not touch the visual
  double;
- a retained candidate entity missing from the visual registry fails closed
  at the settlement/barrier owner and does not commit the journal head.

The missing-visual negative may use a separate local `PresentationHeadDrain`
only if the real singleton would otherwise poison later inherited cases. It
must still use a real SDK journal/token path, not a fabricated error callback.

If fitting all four negatives would require a second Tester file or duplicate
the journal, revise the packet rather than silently omitting proof.

---

## 6. Governed evidence sequence

### 6.1 Tester edit-only review

After Tester returns the one-file diff:

- freeze its line count and SHA-256;
- verify production/package/supporting hashes unchanged;
- run isolated R1--R4 static review;
- no command is authorized until 4/4 plus Coordinator verification.

### 6.2 Natural first red

From `/home/tommaso/Dev/NeuroClient`, Tester may later run exactly:

```text
./app/node_modules/.bin/tsc --noEmit -p ./app/tsconfig.json
```

once. This gates `app/src` production only; it does not typecheck the `.mjs`
smoke.

Only if zero:

1. preflight port 5173 and stop if occupied;
2. start one owned `npm --prefix app run dev` process;
3. wait through one bounded Vite readiness probe;
4. invoke exactly once:

```text
npm --prefix app run presentation-head-drain-live:smoke
```

The required first red is:

- all inherited head-drain assertions have passed;
- SDK ingest/preview/commit and the state-only drain have completed;
- journal/store position is the new coordinate;
- the retained visual double is still at the old coordinate;
- the exact first new final-position assertion fails.

Any compiler failure, Vite failure, SDK rejection, identity mismatch, head-drain
blocker, inherited failure, recovery request, missing reachability, unexpected
green, or different first assertion freezes the result. No rerun, debug,
alternate command, or workaround is authorized.

Always stop/join only the owned Vite process and prove port 5173 plus owned
PID/children are closed. No backend is required or authorized.

### 6.3 Implementation edit-only

Only after the exact first red receives fresh R1--R4 approval and Coordinator
verification may Implementation edit the two Section 1.2 files. Implementation
runs nothing and returns exact diffs, line counts, and SHA-256 values.

### 6.4 Combined green review

Freeze the two production files plus the one unchanged Tester file. Review the
complete combined surface independently through R1--R4. Green execution stays
closed until 4/4 plus Coordinator verification.

### 6.5 One-shot green

Tester repeats the exact Section 6.2 compiler/Vite/smoke protocol once on a
fresh owned Vite process. Required result:

- compiler exit 0 with no diagnostics;
- registered smoke exit 0;
- new exact settlement positive and all negatives pass;
- all inherited head-drain/reset/rebind/catch-up/recovery cases pass;
- owned Vite teardown is clean.

No rerun is authorized. Any nonzero or unexpected result freezes as a blocker.

---

## 7. Ownership and isolation

- Planner owns routing, frozen gates, and the public ledger.
- Tester continuation `019fec24-ec85-7eb1-9676-5bab2853a627` owns only the
  one Section 5 smoke file and later one-shot compiler/Vite/smoke protocols.
- Implementation `019feaea-52c1-7053-a709-4d4c739e0530` owns only the two
  Section 1.2 production files and performs no execution.
- R1 Planner, R2 Backend, R3 Frontend, and R4 Scope/Duplication/Serialization
  review identical frozen surfaces independently and return only to Planner.
- Coordinator independently verifies unanimous transitions and boundaries.
- Live Stack and Full Suite monitors remain advisory/non-gating and are not
  execution owners for this packet.

No owner contacts another owner or reviewer. No reviewer receives a peer
verdict before blind review closes.

---

## 8. Performance, duplication, and serialization constraints

The accepted correction must:

- use the already-reduced SDK candidate as final position authority;
- use the retained actor's staged presented-store position only as a
  same-frame delta witness, never as the terminal coordinate;
- retain the scene registry as sole visual-entity owner;
- retain the journal token as sole commit authority;
- retain the head drain as sole state-only settlement caller;
- perform one bounded patch scan and at most one candidate index;
- use existing `setGridPosition` and no alternate scene mutation API;
- add no path classifier, movement mapper, reducer, cache, index, registry,
  queue, timer, RAF, Promise, retry, adapter, DTO, or telemetry stream;
- add no JSON field, persistence value, local/session storage, public API,
  SDK/generated contract, Python model, schema, or protocol version;
- add no diagnostic return value capable of controlling admission;
- preserve all existing accepted WP-001/WP-002/WP-003 work byte-for-byte
  outside the exact new hunks.

The smoke may create one bounded local visual double. It must not copy the SDK
reducer, planner, head drain, scene registry, or settlement algorithm.

---

## 9. Explicit non-goals

This packet does not prove or change:

- BUG-011 terminal supersession after a movement/forced-movement/other visual
  transaction;
- nonempty state-only cue frames which also carry entity position upserts;
- movement cue privacy, server projection, or observer geometry rules;
- path interpolation, locomotion continuity, facing, timing, or animation;
- a hidden origin or any inferred intermediate coordinate;
- entity removal, reveal/hide animation, HP/lifecycle state-only settlement,
  equipment, visibility, door, light, spatial-effect, or encounter settlement;
- repair of a visual mismatch when the current frame did not change the
  retained actor's presented-store position;
- SDK reduction, journal schema, wire contracts, generated models, or backend;
- RESET behavior;
- queue transaction semantics for state-only frames;
- scene/Pixi pixel evidence or mounted gameplay;
- BUG-009 locomotion continuity;
- BUG-012 through BUG-034 or any other bug family;
- refactoring `sceneRenderer`, `eventIngestion`, or the existing smoke.

---

## 10. Stop conditions

Stop and return to Planner without further edit or execution if:

1. a third production file or second Tester file appears necessary;
2. a new ClipIntent, clip runner, queue transaction, animation, or timer appears
   necessary;
3. backend, SDK, generated, contract, package, stateSync, registry, store,
   persistence, diagnostics, or public API changes appear necessary;
4. the first red occurs before the exact final visual-position assertion;
5. the real SDK journal does not accept/commit the lawful fixture;
6. the case requires a hidden origin, fabricated path, or movement cue;
7. correct handling would also snap after a visual transaction;
8. correct handling would settle a nonempty state-only cue frame in this
   packet;
9. correct handling would repair a divergent visual when staged presented-
   store and candidate positions are equal;
10. Vite cannot start from a free port or leaks a process;
11. a negative requires duplicating the SDK reducer or production settlement
   policy in the smoke;
12. any dependency, framework, schema, protocol, persistence, public contract,
    materially different architecture, or out-of-backlog bug is proposed.

Items 1--3, 7--9, and 12 require a revised packet and may require human scope
review if the resulting proposal materially expands the accepted boundary.

---

## 11. Gate A reviewer questions

Each reviewer must inspect the complete packet and frozen sources and answer:

1. Does the fixture represent the real lawful privacy case: final visible
   non-controlled entity upsert, no authorized movement geometry, no
   presentation cue, with Python source remaining the witness authority?
2. Is a synchronous exact-coordinate state-only settlement the smallest
   truthful receipt, with every animated/path alternative demonstrably false?
3. Do `eventIngestion.ts` and `sceneRenderer.ts` form the complete necessary
   production surface without a hidden third file or import cycle?
4. Does the algorithm derive terminal coordinates from the already-reduced
   candidate while using the staged presented-store position only as a delta
   witness, rather than becoming a second patch reducer or cross-frame repair
   pass?
5. Is settlement ordered after exact-head recheck and before one token commit,
   with failures using the existing barrier/recovery latch?
6. Does the exact `state_only && presentation.length === 0` predicate keep
   Stage 1 isolated from nonempty state-only cues and visual-transaction
   settlement, avoiding BUG-011 or unrelated animation failures?
7. Do the positive, same-position, non-position-only divergent-visual,
   no-upsert, and missing-visual controls isolate false acceptance without
   duplicating production authority?
8. Is the first red naturally reachable only at the final visual-position
   assertion after inherited cases and SDK/head-drain completion?
9. Are O(P + E), allocation, duplication, serialization, service, ownership,
   and teardown constraints sufficient?
10. Is any extra file, contract change, new intent, or human scope decision
    actually required before edit-only release?

Allowed verdicts:

- `APPROVE_WORK_PACKET_004_GATE_A`
- `CHANGES_REQUIRED`
- `HUMAN_SCOPE_REQUIRED`

Approval authorizes no edit or execution by itself. Progression requires fresh
unanimous R1--R4 approval on one exact frozen packet identity plus Coordinator
governance verification.
