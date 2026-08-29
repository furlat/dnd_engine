# Event knowledge-context E3–E6 de-slop repair plan

Date: 2026-08-28  
Status: candidate for independent correctness and anti-slop review  
Scope: repair the rejected E3–E6 candidate without adding another runtime
boundary, ontology, state owner, or testing framework

## 1. Authority and exact starting point

This is a narrow corrective amendment to
`DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_PLAN_2026-08-27.md`, raw
SHA-256
`aaf75e26e3b1e13419caf3d0b7e8346ad8a86531bc155b90f6d37767a8328c98`.
It supersedes only the contradictory callback-authentication and same-batch
causality requirements identified below. Every other scope limit, dependency
rule, hard cut, and higher-level goal in that plan remains governing.

The earlier frozen candidate was rejected. Its ledger and manifest are
historical evidence, not accepted completion records:

| Record | SHA-256 | Status |
| --- | --- | --- |
| `DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_LEDGER_2026-08-27.md` | `afb9b1c3b9f136b78181d76c1712ab590685df23742a3736b47ee5e33838a723` | rejected/stale |
| `DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_MANIFEST_2026-08-27.json` | `fd9bd2055f67b48b2861ff1fe94d665e98a3d78341990d0e257af4ebbba13772` | rejected/stale |

Current repair-checkpoint bytes at planning time:

| Path | SHA-256 |
| --- | --- |
| `dnd/core/events/knowledge.py` | `f9347cdeb21591b051014b06a90d4d5604904abdfe1c0d40d4d55d2c7d433026` |
| `dnd/blocks/sensory.py` | `75d508f52156bd6d1ce73b0d5eafe25eee804cd4b3e1056b943c365435bec8ee` |
| `dnd/event_reduction.py` | `ba9f9a361e2608c190793aa275b2eb3a1ca3378f1ca7938adcf6dbcccb6a7c73` |
| `tests/architecture/test_event_knowledge_context_architecture.py` | `7f9b310f71216ba1b29ff582f38bc157b14a6a07c6440c16b083b9e00a85cc8e` |
| `tests/engine/test_event_knowledge_context.py` | `d4a3e8d1feec813c5497ff025377986c99997799efddd2101dbf51c87012d273` |
| `tests/engine/test_event_knowledge_scripted_encounter.py` | `ffaac5ff4ea8993c00790cf75da44bd8570d614073548381f8e1108da469c454` |
| `tests/engine/test_event_knowledge_async_boundary.py` | `1d014da295dc4a812725a903cef996207e595439b37d892c9b9c3ffaa73d0f4e` |

The current focused context module proves this checkpoint is not acceptable:

```text
44 passed, 7 failed
```

The failures cover exact causative-terminal selection, duplicate/nonterminal/
wrong-lineage rejection, reacquisition attribution, terminal-owned provenance,
and `StepMovementEvent.trajectory` readability.

## 2. Exact repair outcome

Produce the smallest correct E3–E6 candidate which:

1. consumes every real `EventQueue` causal-batch callback separately;
2. never adds callback tokens, authentication context, receipts, or another
   EventQueue seam;
3. resolves sensory causality across the current and already-closed reducer
   archives using existing event UUID, lineage, class, phase, and source index;
4. keeps one class-keyed manifest as the maximum subjective read capability;
5. enforces manifest containment at the one mask-composition boundary;
6. removes the test-local AST interpreter and replaces it with small
   behavior/data assertions;
7. corrects scalar/collection categories without creating accessors or a
   second schema; and
8. passes the real twice-cold, actual-callback proving encounter before a new
   manifest or approval is claimed.

This repair does not redesign accepted `Known`/`Unknown`, `EventKnowledge`,
sensory reduction, the engine event lifecycle, the async consumer, or the
higher pygame plan.

## 3. Governing clarifications

### 3.1 Callback boundary: integrity, not authentication

`EventReducer.on_event_batch` is an internal callback target for
`EventQueue.add_on_event_batch_callback`. The real in-process callback is the
trusted application boundary. It is not a security or adversarial boundary.

The reducer must continue to verify:

- the accepted EventQueue generation;
- exact cursor contiguity;
- no gap, overlap, backwards movement, or duplicate consumption; and
- exact UUID/concrete-class equality between the supplied sequence and the
  unconsumed current queue tail.

Those checks reject reordered, split, stale, overlapping, non-tail, and
already-consumed sequences. A manually concatenated set of entirely
unconsumed callback payloads can equal the same queue tail and is therefore
indistinguishable from one real callback when the only input is
`Sequence[Event]`. The reducer is not required to distinguish that artificial
direct call.

The accepted proof is registration through the real callback API and one
archive/batch per callback. Delete or narrow any test or documentation claim
that arbitrary manual Python calls are authenticated. Do not modify
`dnd/core/events/events_registry.py`, add a `ContextVar`, callback token,
callback ID, active-batch context, wrapper object, or new EventQueue method.

### 3.2 Exact causality across real closed callbacks

The previous same-causal-batch-only rule conflicts with the observed engine
lifecycle: real setup/spatial processing can close the authoritative cause and
emit its sensory grant in a later callback. Keeping the callbacks separate is
more important than pretending they were one range.

For each controlled `SensoryUpdateEvent` which grants new cells or contacts:

1. search the current archive plus already-closed archives owned by the same
   reducer generation for the exact `cause_event_uuid`;
2. require exactly one cause event;
3. inspect only those already-captured archives, in source order;
4. identify terminal candidates which have the cause's exact concrete class
   and lineage, have `phase == EventPhase.COMPLETION` and `is_last == True`,
   and have a source index not preceding the cause;
5. count the cause itself only when it independently satisfies those same
   completion-phase terminal rules; never use a shortcut that accepts it
   without checking the complete candidate set;
6. require exactly one terminal candidate; zero, duplicate, wrong-lineage,
   wrong-class, or nonterminal resolution is fatal and must not advance reducer
   state;
7. use that terminal's source index as the disclosure cause;
8. let the current sensory source slot own any late disclosure delivery, while
   the disclosed historical event retains its original captured source index;
9. prefer exact paths from the resolved terminal when it is their committed
   owner, then use the latest earlier provenance references for other admitted
   scene state; and
10. never reopen, merge, or rewrite prior batch coverage.

No future archive may be sampled. If the real callback proof demonstrates a
sensory grant whose required terminal has not yet been captured, stop for a
new design decision; do not add deferred requests speculatively.

Simple traversal of the reducer's existing immutable archives is authorized.
No causality index, second registry, pending-event manager, replay store, or
EventQueue lookup is authorized.

### 3.3 Manifest meaning and minimal enforcement

The one `_CONCRETE_EVENT_MANIFEST` remains the maximum readable capability for
each exact event class. It is not a second event schema and need not duplicate
the formatter's control flow.

At `_manifest_mask`, after the existing selector returns:

- reject `allow_all` for subjective delivery;
- require returned scalar paths to be a subset of base event paths plus that
  row's scalar paths; and
- require returned collection paths to be a subset of that row's collection
  paths.

This is the sole production containment invariant. Do not add decorators,
generated readers, reflection metadata, a validation service, or another
policy table.

Replace the large AST call-graph/path interpreter with one compact
manifest-data test which checks, for every row:

- exact concrete-class uniqueness;
- referenced root fields exist on that event model;
- scalar and collection paths are disjoint; and
- selector, provenance policy, and formatter are callable.

Retain or add direct behavior regressions for the concrete mistakes already
found. Do not build a generic formatter interpreter.

### 3.4 Correct scalar/collection categories

- `StepMovementEvent.trajectory` is one `MovementTrajectory` enum value. It is
  scalar: admit it in scalar paths, read it with `read`, and format it as a
  field.
- `StepMovementEvent.disclosed_path` remains one atomic, authorized geometry
  value. It stays scalar unless partial member disclosure becomes a separately
  requested feature.
- `MovementEvent.path` and `MovementEvent.costs` are collections and remain
  readable only through `known_items`.
- `MovementEvent.trajectory` is scalar.
- `EntityCreatedEvent.equipment` is a tuple collection. Remove its duplicate
  scalar admission and keep it collection-only.
- Preserve the repaired `SpatialChangeEvent.change_type` and
  `AttackEvent.presentation_kind` scalar manifest paths.

Direct tests must prove both readable and deliberately unreadable access modes
for these category boundaries and prove the affected formatter emits the
admitted value/count.

## 4. Exact authorized files

Production repair:

- `dnd/event_reduction.py` only.

Test repair, only where required:

- `tests/engine/test_event_knowledge_context.py`;
- `tests/architecture/test_event_knowledge_context_architecture.py`;
- `tests/engine/test_event_knowledge_scripted_encounter.py` only if the actual
  callback proof itself requires correction.

Certification records:

- the existing E3–E6 ledger;
- the existing E3–E6 manifest, regenerated only after production/test freeze.

`dnd/core/events/knowledge.py`, `dnd/blocks/sensory.py`,
`tests/engine/test_event_knowledge_async_boundary.py`, EventQueue, event
models, encounters, actions, and every broader system are read-only. If one of
them appears necessary, Luna stops for coordinator review.

## 5. Repair protocol

Luna implements one cut and stops. No certification work is bundled with the
repair. The coordinator independently reviews the exact diff and focused
results before authorizing certification.

Any production/test edit after candidate freeze invalidates the new manifest,
affected validation, and both reviews. Preserve all unrelated dirty work. Do
not reset, checkout, clean, commit, or normalize unrelated files.

## 6. Cut D1 — surgical de-slop and correctness repair

1. Record the current hashes and reproduce the seven focused failures.
2. Remove the AST formatter/selector call-graph interpreter. Replace it only
   with the compact manifest-data assertions in Section 3.3.
3. Add the central `_manifest_mask` containment invariant.
4. Correct the exact scalar/collection rows, masks, and formatters in Section
   3.4 without changing event models.
5. Repair causative-terminal resolution exactly as Section 3.2 specifies,
   requiring exact-class/exact-lineage `EventPhase.COMPLETION` entries with
   `is_last == True`; `is_last` at an earlier phase is never terminal.
6. Preserve simple current/prior archive traversal. Remove shortcuts which
   accept `cause.is_last` without exact candidate selection.
7. Keep the proving encounter's immediate per-callback reduction, fatal live
   Entity/EventQueue/GridMap access guards, complete source coverage, ordinary
   formatting, and twice-cold structural comparison.
8. Catch ordinary callback proof failures as `Exception`, not
   `BaseException`; keyboard/system termination is not test evidence.
9. Delete stale assertions that require authentication of a fresh manually
   concatenated callback history. Keep real cursor/generation/tail failure
   tests.
10. Update the existing ledger with the rejected starting point, exact D1
    changed paths, tests, and hashes. Do not regenerate the final manifest.

Required D1 validation:

- `tests/engine/test_event_knowledge_context.py`: all 51 existing nodes pass;
- the exact architecture file passes with the AST interpreter absent;
- the exact actual-callback scripted encounter passes twice from cold reset;
- every real callback produces one reducer archive/batch with matching
  `(start, stop)`; no synthetic all-events merge is used;
- total source coverage is exact and contiguous across the encounter;
- fatal post-capture live-access guards remain active inside every callback;
- focused asynchronous-boundary tests remain green without edits;
- compileall for changed production/tests;
- `git diff --check`;
- no EventQueue, event-model, sensory, knowledge primitive, server, renderer,
  pygame, transport, SDK, or content change.

Checkpoint status:

`E3_E6_DESLOP_D1_REPAIR_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

## 7. Cut D2 — freeze, certification, and independent acceptance

Authorization begins only after the coordinator accepts D1. No production or
test edits are permitted in D2.

1. Recompute the exact E3–E6 changed-path manifest from current accepted
   bytes; do not reuse the rejected manifest hashes.
2. Recompute the exact source-node union and normalized node hash.
3. Run the complete E3–E6 candidate lane, including the context,
   architecture, scripted encounter, and async boundary proofs.
4. Run the proportional engine lanes required by the governing E3–E6 plan.
5. Run compileall, diff check, dependency/locality gates, hard-cut scans, and
   the configured changed-module type check.
6. Verify every manifest member exists, is unique, current, and hash-exact.
7. Freeze the ledger and manifest and obtain two independent reviews of those
   exact bytes:
   - correctness: callback boundaries, causality, state rollback, provenance,
     coverage, formatter behavior, and scope;
   - anti-slop: no queue authentication, AST interpreter, duplicate ontology,
     second state owner, index, manager/service, generated accessor, or
     speculative abstraction.
8. Any finding requiring code/test repair returns to D1 and invalidates both
   approvals.
9. Append review metadata only after both approvals, then have both reviewers
   reconfirm the final ledger bytes.

Final status:

`E3_E6_COMPLETE — HEADLESS_EVENT_BOUNDARY_ACCEPTED`

## 8. Hard prohibitions

- No edit to `dnd/core/events/events_registry.py` or EventQueue behavior.
- No callback token, callback UUID, callback provenance object, authenticity
  context, `ContextVar`, wrapper batch, receipt, or new queue method.
- No new production file, class hierarchy, event type, DTO, view event,
  projection object, serializer, schema, manager, controller, service,
  registry, index, cache, or replay framework.
- No second class/path/policy table.
- No AST/static-analysis mini-framework in tests.
- No live world/entity/event lookup after archive capture.
- No merging actual callbacks for convenience and no rewriting historical
  coverage.
- No server, deprecated server, SDK, transport, renderer, pygame, assets,
  editor, content recovery, persistence, or networking work.
- No compatibility facade, alias, dual write, re-export, or transitional path.

## 9. Stop conditions

Stop for coordinator/user direction if:

- a real sensory grant requires a terminal event which exists only in a future
  callback;
- exact cause UUID/class/lineage/terminal selection remains ambiguous after
  inspecting existing captured facts;
- correction requires EventQueue or event-model changes;
- correction requires another production state owner or lookup index;
- the real callback fixture cannot pass without synthetic events or merged
  ranges; or
- any broader pygame, renderer, server, content, or mechanics change appears
  necessary.

Ordinary defects inside `dnd/event_reduction.py` or the exact authorized tests
are D1 repair work, not a reason to widen scope.

## 10. Acceptance questions

Correctness approval requires “yes” to all:

1. Does the proving encounter reduce every actual callback separately?
2. Do queue generation/cursor/tail checks reject every real sequencing error
   they can observe without claiming call authentication?
3. Does each sensory grant resolve its exact cause and exactly one
   `EventPhase.COMPLETION`, `is_last == True` terminal of the same class and
   lineage from current/already-closed archives?
4. Are zero, duplicate, nonterminal, wrong-class, and wrong-lineage cases
   fatal without reducer-state advance?
5. Does terminal-owned provenance win without sampling future or unrelated
   state?
6. Are scalar and collection capabilities correct and behaviorally proven?
7. Does each current source slot retain exact coverage and ownership?
8. Does the twice-cold detached encounter pass with live access forbidden?

Anti-slop approval requires “yes” to all:

1. Is EventQueue unchanged and free of callback-authentication machinery?
2. Is the AST test interpreter gone?
3. Is manifest enforcement one small containment invariant plus direct tests?
4. Is archive traversal performed by the existing reducer without a new index
   or owner?
5. Are there still exactly the original event ontology, knowledge states, one
   manifest, and one reducer?
6. Are all edits confined to the exact repair boundary?
