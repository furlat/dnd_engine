# Event knowledge-context E3–E6 implementation plan

Date: 2026-08-27
Status: candidate for independent review
Scope: complete the headless event-reduction boundary after accepted E1/E2

## 1. Governing authorities and accepted starting point

This plan is subordinate to:

- `DND_EVENT_KNOWLEDGE_CONTEXT_REDUCTION_PLAN_2026-08-27.md`, SHA-256
  `7856a537f0b75063fe5bcb012fd7d020b2f92a1e018c17d1ccf6b5e830605c21`;
- `DND_EVENT_KNOWLEDGE_CONTEXT_IMPLEMENTATION_PLAN_2026-08-27.md`, SHA-256
  `3f98f0b926fce8e9662c5718c01aa863734a563897bebe0b403173d8eba0a9ad`;
- the broader pygame proving-encounter plan,
  `DND_PYGAME_SCRIPTED_ENCOUNTER_MVP_IMPLEMENTATION_PLAN_2026-08-27.md`,
  SHA-256
  `8e83dde4916ca3a6a4691bd9b25f720d3e381fe49e6458d4c0800007f9b390b9`.

Accepted E1/E2 implementation bytes at planning time:

| Path | SHA-256 |
| --- | --- |
| `dnd/core/events/knowledge.py` | `dccc01145c03949cbd7d3a39fdf2a5cac28c7e2ae1b1b9b7e4e0d34c4662f373` |
| `dnd/blocks/sensory.py` | `d34977d94df4224b6e9708b7d92fc46453bb59df002f4eec9a1e010621f5d5ad` |
| `tests/engine/test_event_knowledge_context.py` | `5c2527859498edf08b13eba4940a77df533d69bc2f54ab1867d82a2f0a4d3ba1` |
| `tests/architecture/test_event_knowledge_context_architecture.py` | `f4f96e53cdbef505501887cbd786c1f1275fb1bd6a101e76e41f8a2addbbb3d3` |

The accepted combined proof cut is 264 passing nodes. The focused E1/E2
feature and architecture files collect 21 nodes. E1/E2 are not to be
redesigned during this track.

## 2. Exact outcome

Complete the event-knowledge system needed by the fixed headless proving
encounter before pygame exists:

1. run the real two-hero/two-enemy encounter through public in-process engine
   commands and freeze its exact concrete event-class and requested-path
   inventory;
2. reduce closed `EventQueue` ranges into party-readable deliveries over the
   real captured event subclasses;
3. retain latest committed provenance as archive references and existing
   event paths, never copied world values;
4. disclose current scene state at the exact sensory boundary that grants it,
   including causative terminal-resolution checks;
5. admit and format every concrete class emitted by the proving encounter;
6. retain the engine's actual objective `CombatLogEntry` trees with their
   real event/source/log-index linkage, while deriving subjective prose only
   from admitted event knowledge;
7. prove the two asynchronous application queues, player acknowledgement,
   enemy run-ahead, terminal receipts, and cursor catch-up with a deterministic
   headless consumer;
8. certify the exact candidate with correctness and anti-slop reviews.

“Complete” means complete for the frozen proving encounter and its explicit
fallback/unknown-class rules. It does not mean speculative policies for every
event subclass in the repository.

## 3. Non-negotiable architecture

### 3.1 One event ontology

- Real `Event` subclasses remain the only semantic event types.
- `Known(value)` and `Unknown(reason)` are the only subjective value states.
- No canonical event, kind, fact atom, view model, subjective event subclass,
  dictionary payload, serializer, generated accessor, or copied log model.
- Actual-class routing remains a dictionary keyed by the concrete Python
  class.

### 3.2 Dependency direction

- `dnd/core/events/knowledge.py` stays dependency-neutral and must not import
  sensory, actions, entities, grid map, encounters, content, renderer, or
  transport code.
- `dnd/blocks/sensory.py` remains the sole sensory-delta replay and two-party
  join authority. It does not import actions or use function-local imports.
- One new top-level composition module, `dnd/event_reduction.py`, is
  authorized because it may legally import both the dependency-neutral
  knowledge primitives and concrete event families. It is the only new
  production module in this track.
- When `dnd/event_reduction.py` exists, the temporary E2 class-policy assembly
  functions move there in one hard cut. No re-export, alias, compatibility
  facade, or dual registration path remains in `sensory.py`.

### 3.3 One bounded reducer, no framework

`dnd/event_reduction.py` may own exactly one stateful reducer object. Its state
is limited to:

- current `EventQueue` generation and exclusive source cursor;
- the detached `EventArchive` entries already captured;
- the two-observer `PartyKnowledge` replay;
- a dictionary from reviewed semantic keys to archive source-index/read-path
  references;
- paths already disclosed and last-known terrain paths;
- bounded pending objective-log listener evidence using the existing typed
  `CombatLogEntry` only until its causal batch closes;
- accepted `(encounter UUID, log index)` references to captured terminal
  archive entries;
- ordered deliveries, coverage diagnostics, and cursors for the current
  closed range.

It is not a manager, controller family, service layer, event bus, second
world, second registry, persistent replay store, or general projection
framework.

The existing envelopes receive only the accounting metadata required by the
governing design:

- `BatchId` is the stable tuple `(generation_id, start, stop)` proven by one
  completed `EventQueue` causal-batch callback;
- `DeliveryId` is that `BatchId` plus the deterministic delivery ordinal;
- `EventDelivery` gains `delivery_id`, `batch_id`, and optional
  `disclosure_cause_source_index` around its existing `knowledge`;
- one payload-free `SourceCoverage` record exists per current captured source
  slot. It contains generation, source index, event UUID, one
  `SourceDisposition`, and the ordered `DeliveryId` values owned by that
  slot;
- `SourceDisposition` has exactly four values: `DELIVERED`,
  `INTENTIONALLY_SILENT`, `HIDDEN`, or `ERROR`.

An ordinary occurrence delivery is owned by its own current source slot. A
late disclosure retains the older captured event/source index as provenance,
uses the current batch ID and a new delivery ID, and is owned by its current
sensory `disclosure_cause_source_index`. Several disclosures may therefore be
owned by one sensory slot. Historical coverage is never rewritten on later
reacquisition. `DELIVERED` coverage has one or more owned delivery IDs; all
other dispositions have none.

These values are cursor/accounting metadata, not semantic events, facts,
presentation instructions, or a second event schema. They use existing
generation/range/source identities and deterministic ordinals; no random or
parallel semantic identity system is introduced. No other receipt, coverage,
or disposition production type is authorized.

## 4. Authorized paths

### 4.1 Production

- `dnd/core/events/knowledge.py`;
- `dnd/blocks/sensory.py`;
- new `dnd/event_reduction.py`.

An authoritative existing event-owner file may be added to the manifest only
after Slice 3.1 proves that a required presentation value has no existing
cold event path. The ledger must identify the missing fact, exact computing
owner, exact new field, and tests before the coordinator authorizes that file.
No reducer-side workaround is allowed.

### 4.2 Tests and records

- existing `tests/engine/test_event_knowledge_context.py`;
- existing `tests/architecture/test_event_knowledge_context_architecture.py`;
- new `tests/engine/test_event_knowledge_scripted_encounter.py`;
- new `tests/engine/test_event_knowledge_async_boundary.py`;
- new `tests/architecture/test_event_reduction_architecture.py` only if the
  existing architecture file cannot state the new composition-root gates
  clearly;
- one implementation ledger,
  `DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_LEDGER_2026-08-27.md`;
- one final manifest,
  `DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_MANIFEST_2026-08-27.json`.

The direct proving fixture stays in its test module. There is no scenario DSL,
fixture package, replay script format, or general authored-data schema.

## 5. Chunk protocol

Luna implements one chunk and stops. The coordinator independently reviews
the shared checkout, exact diff, tests, ledger, scope, and governing hashes
before authorizing the next chunk. A later chunk is never silently bundled
with an earlier checkpoint.

Any production or test repair after a frozen candidate invalidates affected
test results, hashes, manifests, and reviews. Documentation-only checkpoint
metadata may be appended after approval when the final reviewers reconfirm
the resulting bytes.

No automation is part of this plan.

## 6. Slice 3.0 — preflight and ledger

Authorization: ledger only; no production or test edits.

1. Read `agents.md` and `HOW_TO_TEST.MD` completely.
2. Verify all governing and E1/E2 hashes above.
3. Record the dirty checkout and preserve unrelated work.
4. Re-run the accepted 264-node combined cut exactly.
5. Record collection identities and normalized node hash.
6. Inspect public encounter construction, reset, action discovery, action
   execution, controller boundary, encounter completion, and event-batch APIs.
7. Inspect the existing tests for movement-generated opportunity attacks,
   legal caster actions, deterministic initiative, and ordinary encounter end.
8. Record proposed direct fixture roles and the smallest existing public
   commands capable of the required beats; do not claim legality until run.

Checkpoint status:

`SLICE_3_0_PREFLIGHT_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

## 7. Slice 3.1 — direct proving encounter and exact inventory

Authorization: test-only fixture/inventory plus ledger.

Create `tests/engine/test_event_knowledge_scripted_encounter.py` with direct
Python setup for these stable roles:

- `hero_frontline` — controlled martial actor;
- `hero_caster` — controlled caster;
- `enemy_guard` — melee reactor that generates an opportunity attack;
- `enemy_raider` — second autonomous actor.

The fixture must use existing public engine APIs and direct battlefield data.
It must not instantiate expected events or outcomes. Required beats:

1. cold reset and world initialization;
2. four ordinary entity creations and deterministic initiative;
3. encounter/round/turn start;
4. `hero_frontline` movement leaving `enemy_guard` reach;
5. engine-generated opportunity attack;
6. discovered player weapon attack;
7. enemy movement and enemy attack;
8. at least two consecutive enemy action boundaries recorded without a
   presentation acknowledgement between them;
9. one legal spell discovered for `hero_caster` and cast through the public
   command path;
10. distinct turns for both controlled actors;
11. ordinary explicit encounter end through `Encounter.end_encounter(...)`.

The script stores intentions only: role, expected turn, public discovery
selector, target role/position, and whether to continue/end the turn. It never
stores events, rolls, results, damage, sensory deltas, or presentation cues.
Live dice are allowed; test assertions and later commands must be
outcome-independent. A fixed ordinary RNG seed may make CI reproducible but
must not bypass any engine resolver.

Freeze in the ledger, directly from the resulting stream:

- every `(module, qualname, EventPhase, EventType)` emitted;
- counts and source-index ranges by action boundary;
- parent/lineage relationships and sensory-before-causative-completion cases;
- combat-log entry kinds attached to terminal real events;
- exact encounter UUID/objective combat-log indices; the listener event's
  transient UUID, real lineage, and concrete class; the distinct stored
  terminal UUID/source index resolved after batch close; and the actual
  parent/sub-entry tree shape for each mechanics boundary;
- the encounter combat-log length before and after each boundary and whether
  any standalone entry lacks a linked source event;
- every event path required for bootstrap, scene state, movement, attack,
  damage, life, condition, equipment, turn, text, and fallback presentation;
- whether each requested path is already a reviewed cold read;
- exact missing facts, if any;
- whether the chosen spell creates a persistent spatial effect. Prefer the
  smallest legal spell that avoids persistent-effect enrichment while still
  proving spell execution.

No production reducer work begins in this slice. If the fixture cannot achieve
a required beat through existing public APIs, stop with the exact blocker; do
not fabricate events, add content, or bypass discovery.

Checkpoint status:

`SLICE_3_1_INVENTORY_FROZEN — READY_FOR_COORDINATOR_REVIEW`

## 8. Slice 3.2 — composition hard cut and causal-batch reducer

Authorization: create `dnd/event_reduction.py`, move only policy assembly out
of `sensory.py`, extend existing knowledge tests/architecture gates, update
the ledger.

1. Move the E2 occurrence/path policies and `party_event_router`/
   `party_event_delivery` from `sensory.py` to `dnd/event_reduction.py`.
2. Leave `SensesSnapshot`, `reduce_sensory_snapshot`, `ObserverKnowledge`,
   `PartyKnowledge`, and their evidence/join methods in `sensory.py`.
3. Import at module scope only the E2 concrete classes required at this
   checkpoint. Keep the remaining Slice 3.1 manifest classes explicit as
   `NO_CLASS_POLICY` coverage until Slice 3.3 authorizes their policies. No
   local/dynamic imports and no premature Slice 3.3 admission.
4. Add one `EventReducer` which:
   - accepts exactly two controlled UUIDs;
   - starts at one explicit accepted generation and source cursor;
   - exposes one method compatible with the existing passive
     `EventQueue.add_on_event_batch_callback` and one method compatible with
     `Encounter.add_combat_log_listener`;
   - on each completed causal-batch callback, derives `stop` from the current
     queue cursor and `start = stop - len(events)`, then requires the exact
     ordered callback UUID/class sequence to equal that queue tail before
     capture;
   - captures that callback-proven range immediately through
     `EventArchive.capture_queue_range`; arbitrary contiguous ranges, merged
     callbacks, split callbacks, or caller-invented batch boundaries are
     rejected;
   - rejects generation changes, gaps, overlaps, backwards cursors, or
     duplicate processing;
   - routes each exact concrete class to an admitted policy or a structured
     `NO_CLASS_POLICY` failure;
   - replays controlled sensory updates in source order through the existing
     pure reducer;
   - produces `EventBatch` with its stable `BatchId`, deliveries, one ordered
     `SourceCoverage` record for every current source slot, and payload-free
     diagnostics without querying live world state.
5. Preserve actual captured class, UUID, lineage, phase, source index, and
   existing source values. The reducer never calls an event method.
6. The combat-log listener records exact encounter UUID/log index, the
   listener event's UUID/lineage/concrete class, and one detached deep copy of
   the actual typed `CombatLogEntry` solely as pending comparison evidence
   until that causal batch closes. The listener event is a transient
   completion-shaped value: its UUID is diagnostic only and must not be looked
   up as the stored terminal UUID. At callback-proven batch capture, require
   exactly one captured top-level terminal completion with the same lineage
   and exact concrete class. Verify by value that its captured
   `CombatLogEntry` tree equals the pending typed entry, discard the pending
   tree immediately, then retain only `(encounter UUID, log index)` as an
   archive reference to that stored terminal's actual UUID/source index/tree.
   The detached terminal snapshot already contains the engine's actual
   deep-copied tree. Do not convert the pending entry into a DTO, retain it
   after matching, import it into subjective knowledge, or generate a second
   log. A missing or ambiguous terminal match is fatal; a standalone log entry
   without one is a Slice 3.1 stop condition, not a reducer invention.

Public proofs:

- one closed range produces deterministic identical reads on repeated fresh
  reduction;
- merged, split, reordered, or non-tail sequences are rejected as non-batches;
- batch and delivery IDs are deterministic from the callback-proven range and
  delivery order, and a repeat reduction from a fresh reducer yields the same
  IDs;
- objective top and party knowledge share the same captured source entry;
- hidden/unadmitted occurrences produce no payload;
- every source slot has exactly one structured coverage record, and only
  `DELIVERED` slots have a corresponding delivery;
- every delivery ID is owned by exactly one current source coverage record;
- objective log slots resolve to the actual captured event/log tree and keep
  their original encounter log indices;
- listener UUID and stored terminal UUID are characterized as distinct; exact
  lineage/class matching resolves one terminal and rejects zero or several;
- pending typed log evidence is empty after every accepted batch, and no live
  encounter/log lookup is performed during or after comparison;
- cursor and generation failures are fatal and cannot partially advance;
- E1/E2 behavior remains unchanged after the policy-assembly move;
- dependency and no-local-import architecture gates pass.

Checkpoint status:

`SLICE_3_2_REDUCER_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

## 9. Slice 3.3 — exact admission, provenance, causal disclosure, and memory

Authorization: generic archive-reference provenance inside the single reducer;
no domain event enrichment unless separately authorized from Slice 3.1.

Before provenance or disclosure runs, import every exact concrete class in the
Slice 3.1 manifest at module scope and register its one class-keyed occurrence,
read-path, collection-path, lifecycle/source-coverage, and provenance-update
policy in the existing router. This is the sole manifest policy table. Shared
policy functions are allowed, but base-class inference, field-name inference,
and a second provenance dispatch table are forbidden. Formatting remains
Slice 4.0.

### 9.1 Reference-only provenance

The provenance dictionary stores only:

```text
semantic key -> (generation_id, source_index, existing ReadPath)
```

Semantic keys use existing identities and coordinates, for example an actual
entity/item/object UUID plus an existing field path, or an exact tile
coordinate plus an existing world/tile-state path. They do not introduce a
new semantic enum or copy any tile/entity/item/effect value.

On committed authoritative events, replace the relevant reference with the
latest source index. Hidden changes update references only; they do not update
party scene memory.

### 9.2 Exact causative resolution

For each controlled `SensoryUpdateEvent` that grants a newly visible cell or
contact:

1. resolve `cause_event_uuid` to its captured source event;
2. obtain that event's actual lineage;
3. stage a disclosure request at the sensory source index without emitting a
   historical action delivery or advancing the presentation cursor;
4. after the full closed range is captured, find exactly one causative
   terminal event in the same closed causal batch and lineage;
5. require the terminal source index not to precede the cause;
6. open only preflight-admitted current paths from that terminal event or the
   latest earlier committed provenance reference;
7. attach the resolved scene-state disclosure to the original sensory source
   index while leaving the later terminal event in its original source order;
8. mark disclosure as idempotent scene state, never historical animation.

This ordering rule handles the existing lifecycle in which a sensory update
may precede the causative terminal completion. Resolution may inspect later
entries inside the already closed causal range, but it may not deliver that
later terminal event early, replay the causal action, sample beyond the closed
range, or reorder source coverage.

Missing, duplicate, wrong-lineage, later-unrelated, or nonterminal matches are
fatal reduction diagnostics. Never sample the final global value of the
batch.

### 9.3 Loss, memory, and reacquisition

- visible/seen/contact removal comes only from `SensoryUpdateEvent`;
- explored terrain retains only its last delivered surface/elevation paths;
- entity/object contact loss removes current presence;
- one observer's loss cannot remove the other observer's current contact;
- reacquisition opens the latest committed archived paths;
- a nonvisual contact opens only marker identity/position/supported sense
  paths, not ordinary sprite appearance or visually readable tile content;
- a visible boundary object may be disclosed while cells beyond remain
  unknown;
- adjacent tile-owned wall objects keep separate UUID/placement provenance.

Public proofs cover bootstrap, first reveal, hidden change, loss, reacquisition,
wall-side visibility, adjacent walls, light changes, invisibility, special
senses, and a same-batch unrelated-later change that must not be sampled.
Repeated reacquisition of the same archived source produces a distinct stable
delivery ID in each current batch, keeps the older captured source index, and
records the new sensory disclosure cause without rewriting historical
coverage.
After capture, monkeypatched live GridMap/Entity/BaseObject accessors must fail
without affecting reduction.

Checkpoint status:

`SLICE_3_3_DISCLOSURE_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

## 10. Slice 4.0 — presentation completion and shared text formatting

Authorization: only the concrete class manifest frozen in Slice 3.1 plus
generic unknown-class failure.

1. Verify the Slice 3.3 router covers every frozen concrete class exactly once
   and that its occurrence/read/provenance policy has no missing or extra
   class. Inheritance may share a function, but dispatch remains exact.
2. Complete the reviewed presentation classification and intentionally-silent
   reasons for every admitted class; a missing class/readability policy is
   fatal.
3. Admit only fields required by the proving encounter. Mutable mechanics,
   event methods, free-form context, handler objects, and objective
   `CombatLogEntry.data` remain unreadable.
4. Add actual-class formatters which accept only `EventKnowledge[E]` and
   return plain text. The same formatter runs under top knowledge for the
   objective rail and party knowledge for the subjective rail.
5. Subjective parent/child text uses real source UUID/lineage. A delivered
   child whose parent is hidden becomes a local root without a synthetic ID.
6. Recompute subjective counts/totals from delivered children. Never copy an
   objective aggregate after hiding children.
7. A known occurrence without a specialized formatter produces a visible
   plain-text fallback using only already-known base paths. A missing
   readability policy is fatal; a hidden occurrence never produces a badge.
8. Preserve the objective rail's actual captured `CombatLogEntry` tree and
   real log index/linkage for comparison. Objective comparison text may use
   the same event formatter under top knowledge. Subjective text is derived
   only from delivered real events; it never sanitizes/copies objective
   strings or `CombatLogEntry.data`.

Required admitted families, only when actually emitted by Slice 3.1:

- world/entity bootstrap;
- encounter/round/turn boundaries;
- sensory updates;
- step/root/forced movement and opportunity-attack children;
- attacks, rolls, applied damage, healing/temp HP, and life state;
- spell/action events and their real consequence children;
- condition/effect facts;
- item/equipment/world-object/connector facts.

Public proofs align objective/subjective rows by real source index, UUID,
lineage, concrete class, and phase, and record requested `Known/Unknown` paths.

Checkpoint status:

`SLICE_4_0_ADMISSION_AND_TEXT_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

## 11. Slice 5.0 — deterministic fake async consumer

Authorization: headless tests only unless a production seam is proven
unavoidable and separately approved. Do not create `game/` or import pygame.

Use exactly two local `asyncio.Queue` instances in
`tests/engine/test_event_knowledge_async_boundary.py`:

```text
game_to_presentation: EventBatch
presentation_to_game: terminal receipts/errors
```

The fake presentation consumer:

- reads only deliveries/knowledge and never a live event/world/entity;
- dispatches on actual concrete event class;
- uses a manually advanced deterministic presentation gate, not wall-clock
  sleeps;
- assigns exactly one terminal disposition per delivered event: animated,
  scene-state-applied, text fallback, intentionally silent, or errored;
- consumes the reducer's `SourceCoverage` record for every
  hidden/lifecycle-only source slot; test-local terminal receipts may refer to
  these existing records but may not define another production disposition
  type;
- advances the presentation cursor only across a contiguous fully disposed
  source range;
- rejects duplicate, missing, overlapping, backwards, or wrong-generation
  receipts.

Timing proofs:

1. a player command waits for all earlier required receipts;
2. a second player command in the same turn also waits;
3. at least two autonomous enemy boundaries reduce/enqueue while presentation
   is deliberately gated;
4. the engine lead and queue high-water become greater than one;
5. the next player decision blocks until presentation catches up;
6. terminal encounter completion waits for the terminal receipt;
7. no delivery or coverage gap deadlocks or silently advances a cursor.

No sleep, timeout-as-correctness, worker thread, server envelope, event bus,
queue manager, coalescing, dropping, or backpressure framework.

Checkpoint status:

`SLICE_5_0_ASYNC_PROOF_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

## 12. Slice 6.0 — final certification

1. Freeze exact changed active paths and SHA-256 manifest members.
2. Freeze the exact proving-encounter concrete-class/phase/path admission
   manifest and demonstrate zero missing/extra handlers.
3. Freeze the exact source-node union and normalized node hash.
4. Run the complete admitted headless encounter twice from cold reset and
   prove deterministic class/order/cursor/disposition structure. Dice values
   may differ only where assertions are explicitly outcome-independent.
5. Run proportional lanes for event lifecycle, sensory, movement, light,
   conditions, items/equipment, actions/rolls/damage, spells, encounter,
   scenario, async, and all architecture tests.
6. Run compileall, diff check, dependency/locality gates, type checking for
   changed/new modules, and hard-cut scans.
7. Replace live-world accessors with fatal stubs after batch capture and rerun
   the complete reducer/consumer proof.
8. Obtain two independent exact-candidate reviews:
   - correctness, causality, replay, coverage, and scope;
   - anti-slop, dependency, locality, and type/ontology duplication.
9. Any repair invalidates both approvals and all affected validation/hashes.
10. Append review metadata only, then have both reviewers reconfirm final
    manifest and ledger bytes.

Final status:

`E3_E6_COMPLETE — HEADLESS_EVENT_BOUNDARY_ACCEPTED`

## 13. Hard cuts

- No server, deprecated server, SDK, transport, HTTP, websocket, TypeScript,
  renderer, pygame, assets, editor, save, persistence, or networking changes.
- No `game/` package in this track.
- No canonical view/kind/fact, projection event, subjective DTO, mirror event
  subclass, serialized envelope, or dictionary event payload.
- No second EventQueue, GridMap, Senses registry, combat-log generator, scene
  mechanics model, objective catalog, or copied world snapshot.
- No reducer-side FOV, lighting, darkness, invisibility, special-sense,
  stealth, movement legality, targeting, damage, condition, or effect
  calculation.
- No event method call, live registry query, or live-world access after
  capture.
- No compatibility facade, alias, dual write, dual policy table, transitional
  re-export, or old/new code path.
- No manager/controller/service hierarchy, plugin system, generalized
  reducer framework, mapper hierarchy, lens/HKT library, custom serializer,
  generated accessors, or reflection dump.
- No invented semantic IDs. The authorized deterministic `BatchId` and
  `DeliveryId` are accounting tuples over existing generation/range plus an
  ordinal, never domain identity.
- No arbitrary sleeps, event dropping, coalescing, acknowledgement over a
  gap, or hidden-event badge.
- No persistent spatial-effect presentation unless Slice 3.1 proves the real
  sensory stream carries sufficient effect contacts or an exact authoritative
  enrichment is separately approved.
- Preserve every unrelated dirty file. Never reset, checkout, clean, commit,
  or rewrite user work.

## 14. Stop conditions

Stop for coordinator/user direction when:

- the proving fixture cannot achieve a required beat through public engine
  commands;
- a required path exists only behind a live mechanics object/event method;
- the proving fixture emits an objective combat-log entry with no linked
  source event;
- a real sensory fact required by the frozen spell is missing;
- exact same-batch causative terminal resolution is ambiguous under current
  lifecycle facts;
- implementation requires a second production module beyond
  `dnd/event_reduction.py`;
- an existing architecture gate conflicts with the accepted ownership above;
- any server/renderer/pygame/content-authoring change appears necessary.

Ordinary code defects and test repairs inside an authorized chunk are not new
product decisions, but Luna must still stop at that chunk's checkpoint before
continuing.

## 15. Reviewer acceptance questions

Correctness reviewers must confirm:

1. the fixture uses public commands and real generated events;
2. the class/path inventory precedes and bounds policy implementation;
3. causal disclosure cannot sample an unrelated later value;
4. provenance stores references, not copied world values;
5. current contact, visual tile, remembered terrain, identity, location, and
   boundary-object knowledge remain distinct;
6. objective and subjective formatting read the same captured event;
7. the queue proof enforces player waits, enemy run-ahead, and contiguous
   terminal receipts without sleeps;
8. final completion is measurable and does not claim whole-repository event
   coverage.

Anti-slop reviewers must confirm:

1. exactly one new production composition module is justified;
2. exactly one reducer state owner exists;
3. temporary E2 policy assembly is removed in the hard cut;
4. no new ontology, DTO layer, serializer, manager/controller/service,
   registry, or event bus appears;
5. event policy/formatting code is limited to the frozen class/path manifest;
6. the fake async consumer remains test-local and contains exactly two queues;
7. no compatibility residue or speculative persistent-effect support remains.
