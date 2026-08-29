# Event knowledge-context practical implementation plan

Date: 2026-08-27
Status: governing practical plan for the headless event boundary
Design authority: `DND_EVENT_KNOWLEDGE_CONTEXT_REDUCTION_PLAN_2026-08-27.md`

## 1. Outcome and current authorization

Implement and headlessly certify the event knowledge-context boundary before
pygame. The complete track ends with a deterministic fake presentation
consumer, but the current implementation pass is limited to E1 and E2:

- E1: detached capture, `Known/Unknown`, masks, actual-class routing, and
  coverage;
- E2: the single shared sensory replay, two controlled observers, party join,
  and base event-time readability.

E3+ must not begin during this pass. There is no automation, subagent
implementation, server, SDK, transport, pygame, asset, or renderer work.

## 2. Observable boundary

Input:

- one closed `EventQueue` source range;
- the UUIDs of exactly two controlled entities;
- real event-time observer evidence and real `SensoryUpdateEvent` values.

E1/E2 output:

- one detached archive entry per real source event;
- objective top-knowledge reads over admitted cold paths;
- party event deliveries that preserve the real concrete event class;
- `Known(value)` or `Unknown(reason)` for every requested path;
- replayed observer and party perception state;
- explicit class-policy and read diagnostics.

The feature is correct when those outputs are deterministic and replayable
without querying live `GridMap`, `Entity`, `Encounter`, registries, or
`Senses` after capture.

## 3. Singular ownership and files

### Production

1. New `dnd/core/events/knowledge.py`
   - owns only the dependency-neutral knowledge primitives, detached archive,
     masks, actual-class router, deliveries, and diagnostics;
   - contains no mechanics rules and imports no server, SDK, renderer, or
     pygame code.
2. Existing `dnd/blocks/sensory.py`
   - extracts one pure sensory replay function from
     `Senses.apply_sensory_update()`;
   - both live `Senses` replay and event knowledge use that same function;
   - owns the two-observer join and E2 subjective policies because the
     enforced dependency arrow permits sensory -> core events and forbids
     core events -> sensory;
   - receives higher concrete action/consequence event classes from its
     caller when assembling the actual-class table, avoiding upward or local
     imports;
   - no FOV/light/contact rule is duplicated or moved.
3. Existing `dnd/core/events/__init__.py`
   - remains unchanged unless one direct public export is proven necessary;
   - no compatibility re-export surface.

### Tests

1. New `tests/engine/test_event_knowledge_context.py`
   - feature tests at captured-events-in / readable-deliveries-out;
   - one small data-driven helper, no private call-sequence assertions.
2. New `tests/architecture/test_event_knowledge_context_architecture.py`
   - protects no parallel event schema, no transport/renderer dependency, no
     live-world import, and one sensory replay owner.
3. Existing sensory/objective tests change only if needed to assert the shared
   replay public result; no mechanical expectation migration.

No other production or test file is authorized in E1/E2 without a concrete
blocking reason recorded before the edit.

## 4. E0 preflight

Before production edits:

1. read `agents.md` and `HOW_TO_TEST.MD` completely;
2. record the dirty checkout and preserve every unrelated file;
3. run the focused baseline:
   - `test_objective_state.py`;
   - `test_event_wire_visibility_contract.py`;
   - `test_direct_scenario_deployment.py`;
   - `test_move_settlement.py`;
4. inspect the actual `Event`, `EventQueue`, `SensoryUpdateEvent`, `Senses`,
   event cursor, and generation APIs;
5. confirm the earlier design document remains unchanged.

## 5. E1 — knowledge primitive and detached capture

### 5.1 Minimal types

`dnd/core/events/knowledge.py` defines only:

```text
Known(value)
Unknown(reason)
UnknownReason
KnowledgeMask
CapturedEvent[E]
EventKnowledge[E]
EventDelivery[E]
EventBatch
EventArchive
EventKnowledgeRouter
KnowledgeDiagnostic
```

These are bounded values, not services or model hierarchies.

### 5.2 Capture

`EventArchive.capture_queue_range(start, stop)`:

- validates one unchanged `EventQueue.generation_id()`;
- validates `0 <= start <= stop <= EventQueue.event_cursor()`;
- consumes the exact contiguous `iter_events_since(start)` slice;
- makes one `model_copy(deep=True)` detached snapshot per source slot;
- preserves `type(snapshot)`, UUID, lineage, phase, and source index;
- never mutates or exposes the archive-owned snapshot;
- fails on source gaps, duplicate UUIDs, generation changes, or cursor drift.

No EventQueue callback, second queue, observer service, or persistent archive is
added.

### 5.3 Reads

Paths are tuples of existing model-field names and collection keys. They do
not create another schema.

- `EventKnowledge.read(path)` returns `Knowledge[object]`;
- scalar/enum/UUID/datetime and reviewed frozen typed records may be `Known`;
- callable values, event methods, `BaseObject`, `ModifiableValue`, handlers,
  live conditions, arbitrary context, and mutable mechanics owners are never
  returned;
- list/dict/set reads use `known_items(path)` and return deterministic
  immutable containers;
- `Known(None)` remains distinct from `Unknown`;
- top knowledge bypasses subjective masking but not cold-value admission;
- a party mask can only narrow, never rewrite, a source value.

No generated field tokens, lenses, HKT framework, serializer, proxy freezer,
recursive object dump, or mirror Pydantic models.

### 5.4 Actual-class router

One internal dictionary is keyed by `type(captured.snapshot)`. The router uses
the private snapshot only to choose the handler, then passes
`EventKnowledge[E]` to it.

There is no `CanonicalKind`, new event enum, `EventType` switch, mapper class
hierarchy, or `singledispatch` on an erased generic wrapper.

### 5.5 E1 checkpoint

Public proofs:

- real subclass and source identity are preserved;
- archive snapshot is detached from later EventQueue mutation;
- returned mutable collections cannot mutate the archive;
- `Known(None) != Unknown`;
- top and narrowed masks read the same source values;
- mask intersection and party union are idempotent;
- runtime type mismatch becomes a structured diagnostic;
- actual-class handler coverage is exact.

## 6. E2 — shared sensory replay and party knowledge

### 6.1 Extract the existing replay once

Add one dependency-neutral state value and pure function in
`dnd/blocks/sensory.py` only if the existing `SensesSnapshot` cannot express
the exact replay:

```text
SensoryReplayState
reduce_sensory_update(state, SensoryUpdateEvent) -> SensoryReplayState
```

Prefer extending/reusing `SensesSnapshot` over adding another value. The final
choice must preserve a single implementation of delta application.

`Senses.apply_sensory_update()` delegates to the pure reducer and applies the
returned after-state to the live block. Event knowledge calls the same pure
reducer and never instantiates/registers a second `Senses` block.

### 6.2 Exact cold seed

```text
position = (0, 0)
visible = empty
seen = empty
entities = empty
objects = empty
effective_light_levels = empty
sense_modes = empty
passive_perception = 0
visual_access = 1
paths_dirty = false
```

Changed-flag laws:

- false retains the prior value;
- true replaces with the exact after-value;
- true without the matching optional after-value is an error;
- the first update with unchanged visual access reuses cold `1`.

### 6.3 Observer and party state

`ObserverKnowledge` owns one replay state for one controlled UUID.

`PartyKnowledge` owns exactly two observers and provides:

- visible/seen cell union;
- entity/object contact union;
- visual contact if either observer is visual;
- unioned special-sense modes;
- maximum current observer-effective light per visible cell;
- participant identity and location checks using the event's frozen evidence;
- coordinate checks using exact `x,y` evidence keys.

No selected-character perspective, subjective GridMap, navigation cache,
perception recomputation, or third observer abstraction.

### 6.4 E2 class policies

This pass implements only policies required to prove the boundary:

1. base `Event` occurrence and base participant fields;
2. `SensoryUpdateEvent` for either controlled observer;
3. `StepMovementEvent` committed endpoints and elevation;
4. one attack/action event using actual subclass dispatch;
5. one controlled direct-consequence event.

Every other concrete event class remains unadmitted and reports
`NO_CLASS_POLICY`; it is not copied into subjective output. Complete MVP event
admission belongs to E3/E4 after the scripted encounter inventory is frozen.

### 6.5 E2 checkpoint

Public proofs:

- the pure reducer exactly reproduces live `Senses.apply_sensory_update()`;
- two cold replays reproduce both controlled observers from recorded events;
- party union preserves one hero's contact when the other loses it;
- darkness/darkvision, invisibility/special-sense, light, and wall outcomes are
  consumed from real sensory deltas without recomputation;
- controlled self identity/location is known;
- non-controlled participant identity and location follow separate frozen
  evidence;
- a committed visible movement step can expose both endpoints/elevation;
- a hidden or partially known step does not invent geometry;
- unknown class/policy/read paths produce diagnostics and no payload leak.

## 7. E3 — provenance and causative late disclosure

Not authorized in the current pass.

- index latest committed real-event paths without copying values;
- stage pre-completion sensory disclosures;
- resolve `cause_event_uuid`/lineage to the exact causative terminal fact;
- reject missing, ambiguous, or unrelated later sampling;
- disclose bootstrap/entity/object/equipment/connector paths from archived real
  events;
- preserve last-known terrain and current-contact removal.

## 8. E4 — complete class admission and text logs

Not authorized in the current pass.

- freeze the actual scripted encounter's concrete class manifest;
- implement every required real-class occurrence/path policy;
- format objective and subjective event/log text from the same knowledge reads;
- recompute subjective aggregates from delivered children;
- add fallback/coverage diagnostics without a new log DTO.

## 9. E5 — deterministic fake presentation sink

Not authorized in the current pass.

- add the two in-process `asyncio.Queue` boundaries in the future `game/`
  application package;
- consume delivery batches with a manual/deterministic presentation clock;
- emit one terminal receipt per delivery;
- prove player acknowledgement, enemy run-ahead, and player-boundary catch-up;
- use explicit completion events/futures, never sleeps.

The fake sink belongs to tests unless a minimal production coordinator seam is
required by the real application. It must not become a framework.

## 10. E6 — headless certification

- complete focused feature lanes;
- run existing event, sensory, movement, light, condition, item, action, spell,
  scenario, and architecture lanes proportionally;
- compile `dnd` and tests;
- run diff check;
- run hard cuts for canonical-view/fact schemas, server/SDK/renderer imports,
  live-world reads, second queues/worlds, and sleeps;
- freeze exact changed paths and test node hashes;
- perform correctness and anti-slop review before pygame integration.

## 11. Hard cuts

- No `CanonicalEventView`, `CanonicalKind`, `FactAtom`, mirror event subclass,
  objective/subjective DTO family, or copied world catalog.
- No FOV, light, invisibility, special-sense, stealth, movement, or targeting
  computation in event knowledge.
- No raw event escape to presentation.
- No event methods or mutable mechanics owners exposed as reads.
- No renderer, pygame, assets, server, SDK, transport, TypeScript, persistence,
  replay framework, or network dependency.
- No new manager/controller/service hierarchy.
- No second EventQueue, GridMap, Senses registry, or combat-log generator.
- No compatibility facade or old/new dual path.
- No arbitrary sleeps or mock-heavy collaborator tests.
- No edits outside the authorized files without a recorded blocker.

## 12. Stop conditions

Stop and request a new decision only if:

- a required E1/E2 value exists only behind live mechanics behavior and cannot
  be proven from an existing cold event field;
- exact observer replay requires changing perception rules rather than
  extracting the existing reducer;
- a current engine invariant makes detached same-subclass capture impossible;
- E1/E2 requires an additional production layer or file beyond the authorized
  boundary.

Ordinary implementation failures, test repairs, and type corrections inside
this plan are not new product decisions.
