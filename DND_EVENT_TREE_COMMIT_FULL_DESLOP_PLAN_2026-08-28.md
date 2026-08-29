# Event-tree commit full de-slop plan

Date: 2026-08-28  
Status: replacement candidate for independent correctness and anti-slop review  
Scope: active in-process engine event mechanics, committed observation, and the
event-knowledge reducer required before the pygame client

## 1. Decision

The real event graph is the causal boundary.

The engine already has the required semantic structure:

- concrete `Event` subclasses are the event types;
- phase versions share one `lineage_uuid`;
- `parent_event` and the derived parent/child lineage fields form the causal
  graph;
- handlers and spatial handlers create reactions and nested mechanics; and
- a terminal root event means its synchronous child tree is finished.

The rejected callback-batch repair tried to add a second answer to a question
the event graph already answers. It is superseded. It must not be repaired by
adding wider batches, controller wrappers, delayed terminal searches,
authentication tokens, pending requests, or callback context.

The governing runtime law is:

```text
one parentless root lineage opens
    -> its phase versions and explicit descendants execute synchronously
    -> completion contributors may emit explicit descendants
    -> the parentless root reaches terminal COMPLETION or CANCEL
one committed event tree closes
    -> passive listeners receive that exact ordered range once
```

No mechanical event may occur from a passive listener. No descendant may be
published after its root closes. No second root may interleave while a root is
open.

### 1.1 Measured current graph

A read-only application of these invariants to the current 244-event proving
encounter found 27 natural root trees and one concrete ownership defect:

- three condition-removal lineages execute during `TurnStartEvent` but lose
  their parent;
- those lineages account for exactly 12 violating phase versions; and
- every other source event already fits one root or an explicit descendant of
  that root.

The correct repair is at turn-start duration progression: pass the current
turn event through entity, equipped-item, and inventory-item condition
expiration/removal paths, including any removal save child. Do not create a
turn wrapper or admit nested parentless roots.

## 2. What is rejected

The following current or proposed mechanisms are rejected as causal
authorities:

- `batch_on_event_callbacks()` and its depth/pending `ContextVar` state;
- immediate, sequence, and batch observer APIs existing simultaneously;
- action, controller, encounter, or deployment methods choosing ad-hoc source
  ranges;
- GridMap mechanics running from post-storage passive observers;
- swallowed exceptions from cache, lighting, or sensory mechanics;
- a generic pre-completion callback list beside a second indexed system list;
- combat-log delivery before the real terminal event is stored;
- fake events created only to push a combat-log callback;
- reducer-side cross-archive searches that repair an unclosed cause;
- deferred sensory requests, callback identities, receipts, transactions,
  coordinators, buses, or another event/view ontology.

The existing `Known`/`Unknown`, detached real-event archive,
`EventKnowledge[E]`, class-keyed disclosure policy, and renderer-neutral
delivery model remain valid. This plan repairs the event closure feeding them.

## 3. Exact event-tree invariants

`EventQueue` derives closure from stored real events. Callers do not open or
close a separate transaction object.

### 3.1 Opening a root

When no root is open:

- a parentless nonterminal event opens its concrete class and lineage as the
  active root;
- a parentless terminal completion fact is a valid one-event committed tree;
- a parented event is invalid because its causal root is already closed or
  absent.

The queue records only the active root lineage and the first source cursor.
It does not create an ID, wrapper, receipt, or parallel registry.

### 3.2 Admitting descendants

While a root is open:

- another version of the root must preserve the exact concrete class and
  lineage;
- every other stored event must carry `parent_event`;
- following the stored parent links must resolve to the active root lineage;
- a second parentless lineage is an error;
- a missing parent, a parent from an earlier closed tree, or a cycle is an
  error.

These checks apply to ordinary handlers, spatial handlers, completion
contributors, conditions, movement steps, reactions, damage, lighting,
sensory facts, and every other active producer. There is no privileged bypass.

### 3.3 Closing a root

A root closes only when its parentless exact-class/exact-lineage version is:

- `EventPhase.COMPLETION` with `is_last is True`; or
- `EventPhase.CANCEL` as the terminal cancellation of the open lineage.

The closed source range is the contiguous slice from the recorded first root
slot through that terminal slot. Admission has already proved every member is
the root or its descendant. A child terminal never closes or notifies the
tree. Closing clears the root state before passive notification.

If mechanics raise before a root terminates, the incomplete root remains a
visible engine error. The next unrelated event must not silently hide it.
Normal rejection paths must publish the existing cancellation event; reset is
the recovery boundary for an exceptional aborted test/game.

## 4. One synchronous mechanical extension seam

Replace both generic pre-completion callback storage and indexed
pre-completion systems with one small indexed `CompletionContributor`
protocol.

A contributor:

- is registered under one stable name for explicit event types;
- runs synchronously after the authoritative mutation and before the terminal
  version is built;
- may update derived engine caches and emit real child events;
- must parent every emitted event to the event being completed;
- propagates exceptions to the mechanic that is completing; and
- has `reset()` because it owns live in-process derived state.

Contributors execute in deterministic registration order. The fresh
`GridMap` registers its contributor when the map singleton is constructed.
`SpatialSensesSystem` registers after observers begin attaching, so physical
world settlement always precedes subjective reduction without a priority
framework.

### 4.1 GridMap contribution

Move all active GridMap event reactions out of passive observers and into the
GridMap completion contributor:

1. invalidate subjective occupancy/path caches for committed
   perceivability changes;
2. settle light sources attached to a committed entering/leaving anchor;
3. recompute illumination affected by committed optical topology; and
4. emit the existing `SpatialChangeEvent` light children with the completing
   event as their explicit parent.

Delete `_on_perceivability_changed`, `_on_vision_blocking_changed`, both
`_ensure_*callback` methods, their flags, and their registrations. The result
must compute from committed state, not declaration-time old geometry.

### 4.2 Sensory contribution

`SpatialSensesSystem` remains the sole perception authority. Its contribution
runs after physical settlement and:

- selects affected observers;
- recomputes their existing `Senses` state;
- creates the existing real `SensoryUpdateEvent` values; and
- publishes them as completed children of the event being completed.

Replace `register_completion_sequence()` with one explicit
`publish_completed_children(parent, children)` operation. It validates exact
completion phase, exact parent UUID, deterministic order, and membership in
the current open root. It has no observer side effect of its own.

The contributor must not reduce `SensoryUpdateEvent` again. Existing
event-type indexing retains that exclusion without a recursion flag or
special callback guard.

## 5. One passive committed-tree seam

After a root terminal has been stored, `EventQueue` invokes one kind of
passive listener with `tuple[Event, ...]`: the exact committed tree in source
order.

This is the only general observation API. Hard-delete:

- per-event observer registration and filters;
- event-sequence observer registration and filters;
- causal-batch observer registration;
- `batch_on_event_callbacks()` and all batch depth/pending state;
- passive handler-dispatch callbacks; and
- their reset and dispatch machinery.

Handler dispatch continues to compute the existing outcome/effective reaction
evidence used by the real event result. It no longer creates a second live
observer channel merely for tests.

Committed-tree listeners are read-only sinks:

- they run only after root state has closed;
- they may detach, reduce, log, or enqueue;
- they may not publish, register, or phase an event;
- attempted event publication during listener dispatch raises immediately;
- one failing listener is logged and does not prevent later listeners from
  receiving the already-committed tree; and
- listeners never trigger one another.

One simple synchronous dispatch guard enforces the no-publication rule. It is
not a token, authentication mechanism, or causal context.

## 6. Event observer evidence remains one authority

The existing three injected sensory functions are not event reactions, but
three separate callback slots obscure their common authority. Replace them
with one dependency-neutral `EventObserverEvidenceProvider` protocol owned by
the existing `SpatialSensesSystem`.

The queue asks that provider for existing event-time identity, location,
perceiver, and reveal evidence while storing/building the event. These are
pure reads of already-computed sensory state. They cannot emit events. No new
state owner is created.

## 7. Combat logs use the real terminal event

`Event._completion_updates()` may generate and attach the existing typed
`CombatLogEntry`, but it must not notify the encounter before the terminal
event exists.

The active `Encounter` subscribes to committed event trees. When the final
root terminal carries a combat log, it appends that exact log from that exact
stored event. It unsubscribes only after its end event is committed.

Delete:

- `EventQueue.set_combat_log_callback()`;
- `EventQueue.push_combat_log()`;
- the pre-storage temporary terminal copy;
- `Encounter` combat-log listener fan-out; and
- reducer pending-log evidence/reconciliation.

The sole current standalone push—the condition-immunity result—attaches its
already-built `CombatLogEntry` to the real condition cancellation event.

The event source index and terminal event identity are the objective log
provenance. The reducer does not mirror `Encounter.combat_log` indices. The
encounter list remains a convenient objective text index; it is not a second
causal identity system.

## 8. Reducer hard simplification

Rename the reducer input method to `on_committed_tree(events)` and register it
only through the committed-tree listener API.

For every call it must:

1. verify generation, exact cursor contiguity, UUID/class equality with the
   current queue tail, one parentless exact terminal root, and complete tree
   membership;
2. deep-capture that exact range once;
3. resolve every sensory disclosure cause and its exact-class/exact-lineage
   terminal inside the current captured tree;
4. reject zero, duplicate, wrong-class, wrong-lineage, nonterminal, or
   cross-tree causative terminals;
5. retain prior detached archives only for remembered/provenance source
   values and later knowledge acquisition, never to close current causality;
6. route the same captured real subclasses through their knowledge masks;
7. emit the existing deliveries/coverage and advance the source cursor only
   after the entire result succeeds; and
8. derive objective log provenance directly from captured terminal events
   carrying `combat_log`.

Delete `on_combat_log`, pending log evidence, cross-archive terminal repair,
and documentation/tests claiming caller-selected batches are causal.

The existing range-based `BatchId`/`EventBatch` accounting may remain: after
this cut each range is exactly one committed event tree. Do not invent a new
envelope merely to rename it.

## 9. Production change envelope

Expected active production paths:

- `dnd/core/events/events_registry.py`;
- `dnd/core/gridmap.py`;
- `dnd/blocks/sensory.py`;
- `dnd/entities/entity.py`;
- `dnd/encounters/encounter.py`;
- `dnd/core/base_actions.py`;
- `dnd/core/base_block.py` and `dnd/core/base_conditions.py` only for explicit
  parent propagation through block-owned duration/removal;
- `dnd/runtime_reset.py`;
- `dnd/event_reduction.py`;
- `dnd/core/events/knowledge.py` only if docstrings/type spelling must reflect
  committed-tree input.

An additional active event owner may change only when the root-admission gate
exposes a real missing/wrong `parent_event`, incomplete lifecycle, or late
descendant. The repair is to parent/complete the real event at its current
owner. Do not wrap the caller, weaken the gate, or add an allowlist.

No server, deprecated server, SDK, transport, generated, renderer, pygame,
editor, cross-language, content-recovery, map-authoring, or Phase 7 work is in
scope. Preserve unrelated dirty work. Do not reset, checkout, clean, commit,
or normalize unrelated files.

## 10. Implementation cuts

### Cut 0 — read-only freeze

- Record the current focused and active-lane baseline.
- Freeze all active production users of the observer, batch, pre-completion,
  combat-log, and handler-dispatch callback APIs.
- Freeze every active public root producer and every current late/missing
  parent found by the proving encounter.
- Make no production or test edits.

### Cut 1 — event kernel hard cut

In one coherent production/test cut:

- implement automatic open-root/descendant/terminal-close validation;
- implement the single indexed completion-contributor registry;
- implement the one committed-tree listener registry and no-publication guard;
- implement explicit completed-child publication;
- delete all superseded EventQueue callback/batch APIs and state; and
- add focused event-kernel proofs.

Do not leave dual observer or batch paths after this cut.

### Cut 2 — physical and subjective contributors

- migrate GridMap cache/light reactions to its completion contributor;
- migrate `SpatialSensesSystem` to the same contributor contract;
- combine the three sensory evidence function slots into its one provider;
- remove all attachment/registration residue; and
- prove committed geometry -> light children -> sensory children -> root
  terminal ordering with exceptions propagated.

### Cut 3 — logs, reducer, and async consumer boundary

- move encounter combat-log capture to committed trees;
- attach immunity text to the real cancellation event;
- remove combat-log callback/listener/pending reconciliation paths;
- remove action/controller batch wrappers;
- simplify `EventReducer` to `on_committed_tree` and current-tree causality;
- migrate the headless async queues to one reduction result per committed
  tree; and
- run the twice-cold proving encounter.

### Cut 4 — active caller closure

- run the root-admission gate across the governed active engine lanes;
- repair the measured turn-start condition/item expiration paths by carrying
  the current turn event as their real parent;
- repair only real missing parent or incomplete lifecycle owners;
- delete stale observer-dependent tests rather than reproducing internal
  timing through another spy API;
- retain direct behavior/event-tree assertions for every migrated mechanic;
  and
- stop if an active rule truly requires events to outlive their root.

### Cut 5 — final full anti-slop certification

- inspect the complete changed production diff, not only the final cut;
- run correctness and anti-slop reviews against the same frozen bytes;
- apply no repair without invalidating and rerunning both reviews; and
- certify only after every validation below is green.

## 11. Required proof

### 11.1 Event-kernel laws

Direct tests must prove:

- parentless declaration opens one root;
- exact lineage phases remain admitted;
- explicit children and grandchildren resolve to that root;
- a second root, missing parent, closed-root parent, cycle, wrong root class,
  or wrong root lineage fails;
- child terminal does not notify;
- top-level completion and cancellation each notify exactly once;
- the delivered tuple is contiguous and ends with the stored root terminal;
- contributor exceptions propagate and leave an incomplete root visible;
- listener event publication fails; and
- listener failure does not invoke mechanics or block later passive listeners.

### 11.2 World/sensory laws

Direct tests must prove:

- a blocking geometry commit recomputes light from committed geometry;
- attached light settlement precedes subjective sensory reduction;
- perceivability changes invalidate subjective navigation before sensory
  snapshots;
- light and sensory facts are explicit descendants of the physical cause;
- no light/cache/sensory mechanic is reachable through a passive listener;
- movement still updates FOV/light/senses at every committed step; and
- turn-start sensory refresh remains inside the turn-start tree.

### 11.3 End-to-end laws

The real two-controlled-character/two-enemy scripted encounter must run twice
from cold reset and prove:

- every source index belongs to exactly one committed tree;
- committed trees cover the complete source stream without gap or overlap;
- every tree has exactly one root and one terminal close;
- every sensory cause and exact terminal are in the same tree;
- opportunity attacks remain children of movement;
- player commands may wait for presentation acknowledgement while enemy
  commands enqueue later committed trees without waiting;
- reduction/formatting never reads live Entity, GridMap, Encounter, or
  EventQueue state after capture;
- objective and subjective logs derive from the same terminal real events;
- both cold runs produce structurally identical committed trees, deliveries,
  coverage, and text; and
- no unrepresented event class/path is silently dropped.

### 11.4 Hard-cut gates

Active production and current tests must contain no use or definition of:

- `add_on_event_callback` / `remove_on_event_callback`;
- `add_on_event_sequence_callback` /
  `remove_on_event_sequence_callback`;
- `add_on_event_batch_callback` / `remove_on_event_batch_callback`;
- `batch_on_event_callbacks` or event-batch depth/pending state;
- `add_pre_completion_callback` or `add_pre_completion_system`;
- `register_completion_sequence`;
- `set_combat_log_callback` or `push_combat_log`;
- `add_combat_log_listener` / `remove_combat_log_listener`;
- `add_on_handler_dispatch_callback` /
  `remove_on_handler_dispatch_callback`;
- reducer `on_event_batch` or `on_combat_log`; or
- cross-archive causative-terminal resolution.

The replacement names must express their actual role: completion
contribution, committed-tree observation, and completed child publication.

## 12. Acceptance

This plan is accepted only if independent correctness and anti-slop reviewers
both agree that:

- the event graph alone owns causal closure;
- no callback or manually wrapped caller can alter that closure;
- physical and subjective derived mechanics are synchronous explicit child
  production;
- passive observation is one-way and post-commit;
- the reducer no longer repairs engine-boundary defects; and
- no additional framework, compatibility path, or parallel ontology was
  introduced.

Implementation begins only from the accepted exact plan. Each cut stops for
coordinator review before the next cut.
