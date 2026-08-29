# QUARANTINED — REJECTED EVENT CLEANUP PLAN — DO NOT IMPLEMENT

> **Evidence preservation notice (2026-08-29):** This plan is rejected and
> quarantined after three independent audits found invalid condition ownership,
> flattened semantic parentage, incomplete caller migration, committed-state
> vetoability, and real gameplay regressions. It is retained in full as evidence
> and must not be used as implementation authority, amended into a new plan, or
> deleted. Its exact SHA-256 immediately before this quarantine banner was added
> was `a739521673ecdfed95c237f28f8c5fbcf5d6e8aede4a5f56a926225b265fdc81`.
> The associated implementation ledger is also evidence, not acceptance.

# Native event causality full-cleanup plan

Date: 2026-08-28  
Status: **REJECTED AND QUARANTINED — NOT IMPLEMENTATION AUTHORITY**  
Supersedes for implementation:
`DND_EVENT_TREE_COMMIT_FULL_DESLOP_PLAN_2026-08-28.md`  
Preserves: the accepted real-event-subclass plus `Known`/`Unknown` knowledge
model; this plan changes its broken runtime boundary, not its value algebra.

## 1. Outcome

The event system will have one causal model and one execution direction:

```text
domain operation
  -> concrete Event subclass lifecycle
  -> concrete event resolves its explicit child events
  -> root terminal is stored last
  -> closed tree is available in the append-only event journal
  -> reducer pulls the closed tree by source cursor
  -> presentation consumes the detached reduced result
```

There is no callback chain between these stages.

- `Event` subclasses remain the only semantic event types.
- `parent_event` remains the only parent edge.
- lifecycle lineage remains the identity of one event occurrence across phases.
- an exact parentless terminal closes one tree.
- mechanics happen before that terminal and appear as real child events.
- reduction is a pull from already-closed source facts, never a live observer.

The queue does not discover gameplay work by callbacks. It does not run a
plugin pipeline. It does not ask controllers to manufacture a transaction.
It validates and stores the event tree that the rule implementation actually
produced.

## 2. Rejected designs

The following are explicitly rejected:

- generic pre-completion callbacks;
- a renamed completion-contributor protocol or registry;
- immediate, sequence, batch, committed-tree, or handler-dispatch listener
  registries;
- `ContextVar` batch depth, pending callback batches, callback tokens, callback
  authentication, receipts, or caller-selected causal ranges;
- mechanical cache, light, senses, item, concentration, or cost work performed
  after a terminal event;
- terminal `CANCEL` handlers;
- reducer searches across earlier archives to repair a missing current-tree
  cause or terminal;
- an event bus, coordinator, manager, controller, service, transaction object,
  or second event/view DTO family;
- a `CanonicalEventView`, kind switch, fact atom, mirrored event subclass, or
  renderer-only event ontology.

The rejected replacement plan remains on disk as design history. It is not an
implementation authority.

## 3. The causal laws

### 3.1 Root opening

When the queue has no open root:

- a parentless `DECLARATION`, `EXECUTION`, or `EFFECT` event opens a root;
- a reviewed inert terminal fact may form a one-event tree;
- a parented event is rejected because its parent tree is absent; and
- the queue records only the root concrete class, lineage, and source start
  cursor required to validate later writes.

There is no separately allocated transaction or batch identity.

### 3.2 Admission while open

Every stored value while a root is open must be either:

1. another phase version with the root's exact concrete class and lineage; or
2. an explicitly parented descendant whose stored parent chain resolves to
   that root.

Reject immediately:

- a second parentless lineage;
- a missing parent;
- a parent from a closed tree;
- a parent cycle;
- a root phase with the wrong concrete class or lineage; or
- a child whose ancestry resolves anywhere except the open root.

There are no privileged writers. Handlers, movement reactions, item resource
events, condition changes, light changes, sensory changes, saving throws, and
damage all pass the same rule.

### 3.3 Terminal means terminal

The root closes only when the parentless exact-class, exact-lineage value is:

- `COMPLETION` with `is_last is True`; or
- terminal `CANCEL`.

The root terminal is the last stored member of the tree. `EventQueue` never
dispatches gameplay handlers for `COMPLETION` or `CANCEL`. A rule that must
react, spend, clean up, or emit children does so at an earlier phase.

Storing the terminal clears the open-root state. Any later event parented to
that tree fails. A child terminal never closes the root.

An exception before terminal publication leaves an incomplete root visible;
the next unrelated root fails. Reset is the recovery boundary for a failed
test/game boot, not an implicit rollback mechanism.

### 3.4 Turn execution is orthogonal

`turn_execution_id` may identify several sequential committed trees belonging
to one gameplay turn. It does not open, merge, authenticate, or close event
trees and the reducer never treats it as a causal boundary.

## 4. Event subclasses resolve their own children

`Event.phase_to(COMPLETION)` performs one ordinary template-method call on the
concrete source event before building or storing its terminal version:

```python
event.resolve_sub_events()
terminal = event.finalize_terminal(EventPhase.COMPLETION)
EventQueue.register(terminal)
```

`Event.resolve_sub_events()` is a no-op in the base class. Concrete existing
event classes override it only when their semantics require child work. This
is normal subclass behavior, not a callback:

- no function is registered;
- no name or priority is assigned;
- no list is iterated;
- no reset contract is added;
- no exception is swallowed; and
- the called method is visible from the event class definition.

Every override emits ordinary events with `parent_event=self.uuid`. It may
call the domain owner that already owns the affected state; it may not create
a second scheduling mechanism.

The reviewed overrides use method-local imports for their existing runtime
owners. This is required by the current dependency direction:

- `world_events.py` is already imported by GridMap and sensory;
- condition and encounter event modules are already imported by their runtime
  owners; and
- a module-level reverse import would create a cycle.

Only `resolve_sub_events()` bodies may locally import `get_map()` or the
existing `spatial_senses_system`. Do not replace those local imports with a
registry, provider, service locator, injected callable, or new runtime owner.
An architecture gate forbids top-level event-module imports of those owners
and forbids any new domain-resolution registration API.

### 4.0 One terminal finalizer, two terminal phases

`COMPLETION` and `CANCEL` share one deterministic terminal metadata finalizer.

- completion first runs the concrete `resolve_sub_events()`, then finalizes;
- cancellation never runs `resolve_sub_events()`, because all cancellation
  mechanics must already have occurred, but it still finalizes;
- handler-returned cancellation proposals pass through the same finalizer
  before `_record_handler_result` stores them; and
- both phases derive parent lineage, descendant lineages, evidence, and the
  typed combat log from the current stored tree before the terminal is stored.

The finalizer is an ordinary `Event` method used by `phase_to(COMPLETION)`,
`cancel()`, and guarded-handler cancellation storage. It is not registrable or
overridable by runtime owners and it never emits an event.

A canceled root therefore aggregates completed reaction children exactly as a
completed root does. In particular, a Counterspell reaction completes before
the interrupted spell's root cancellation, and that cancellation carries the
Counterspell log as a typed sub-entry.

Terminal descendant metadata never trusts a detached proposal's copied
`children_events` arrays. It is derived from stored journal parentage: scan
the current open-tree range, resolve each parent chain, and select descendants
whose ancestry reaches any stored phase UUID of the terminal's lineage. This
also makes an execution proposal created before item-charge or metamagic
children safe to register later; its eventual terminal sees those children
from real parent edges, not stale copied lists.

### 4.1 Spatial event resolution

`SpatialChangeEvent.resolve_sub_events()` performs the fixed causal order:

1. ask the current `GridMap` to settle consequences of that exact committed
   spatial mutation;
2. GridMap invalidates the relevant movement/occupancy/optical/propagation
   caches directly;
3. GridMap moves or suppresses anchored lights and recomputes illumination;
4. illumination deltas are full existing `SpatialChangeEvent` child
   lifecycles parented to the physical event;
5. after physical settlement returns, the existing
   `SpatialSensesSystem.reduce_event(event)` recomputes affected observers; and
6. each changed observer emits one existing completed `SensoryUpdateEvent`
   child in stable observer order.

The light child resolves its own sensory deltas before returning. The outer
physical event then resolves any remaining visibility/path delta. A zero delta
emits no sensory event. This is explicit depth-first event execution, not
subscription order.

Delete GridMap's `_on_perceivability_changed`,
`_on_vision_blocking_changed`, `_ensure_*callback` methods, registration
flags, and passive registrations.

### 4.2 Other perception-changing event resolution

The concrete existing classes for condition application/removal, life-state
change, death, turn start, and spatial-effect change call the same existing
`SpatialSensesSystem.reduce_event(self)` directly from their own
`resolve_sub_events()` override.

Do not add a parallel perception-event enum, dispatcher, registry, or switch.
Do not make every event call the sensory system. Only the existing concrete
event classes whose semantics change perception override the method.

`SensoryUpdateEvent` has the base no-op and therefore cannot recurse.

### 4.3 Sensory children need no batch API

Delete `register_completion_sequence()`.

The sensory reducer registers its already-completed children one at a time in
sorted observer order. Each child has the real cause UUID as `parent_event` and
is admitted into the open tree by the ordinary queue rule. No observer is
notified between them because there are no event observers.

### 4.4 Inert terminal facts are explicit

`publish_completed_fact()` is replaced by a narrowly named terminal-fact
publication method that accepts only reviewed inert fact subclasses. Inert
means that the fact:

- represents state already committed by its owner;
- begins and ends at `COMPLETION`;
- has no validators, handlers, state mutation, or child resolution; and
- forms a one-event root when parentless.

Use existing subclassing to declare this lifecycle property; do not maintain
an EventType allowlist in `EventQueue`.

Entity creation/progression, encounter start/end, and round-start facts are
audited for this contract. Any class that requires child mechanics is not
inert.

`WorldInitializedEvent` is not inert in the current active builder. The
battlefield builder publishes later SpikeTrap activation, torch-light, and
item-location events using the world event as their cause. Authorize the exact
active builder and migrate world initialization to one non-vetoable full
lifecycle:

1. build and validate the disabled-event world as today;
2. store the world declaration and execution without rerunning validators for
   state that is already committed;
3. store its effect phase;
4. materialize authored traps and settle wall torches with that effect as
   their explicit parent; and
5. store the world completion last.

Do not keep closed-world parentage, split these authored consequences into
unrelated roots, or add a setup transaction/wrapper.

`SpatialEffectChangeEvent` is not inert because it can change perception. Its
producer is migrated from a prebuilt completion fact to a full, non-vetoable
committed-state lifecycle whose declaration/effect is stored before its
sensory children and whose completion is last. The existing committed spatial
publication path is generalized or reused; no transaction wrapper is added.

## 5. Rule-owned mechanics move before terminal

No general event hook will hide mechanics that are naturally owned by the
rule being executed.

### 5.1 Action costs

`BaseAction` commits its serialized action-economy and named-resource costs at
the accepted execution boundary, before effect resolution and before any
execution-canceling reaction can terminate the action. This preserves the
rule that an execution-committed spell slot is spent even when a reaction
interrupts the cast.

The exact seam is a direct split inside `BaseAction._apply_action`; it is not a
new transaction:

1. publish the ordinary declaration so declaration handlers may reject it;
2. copy that accepted declaration with `use_register=False` and pass the copy
   to the existing subclass `_validate()` contract;
3. existing `_validate()` implementations use their current `phase_to()` or
   `cancel()` calls to return an unregistered execution/cancellation proposal;
4. validate that proposal's exact class/lineage and expected phase;
5. publish a validation cancellation immediately with no costs;
6. for an accepted execution proposal, commit action/resource/item costs once,
   parenting item-cost children to the stored declaration;
7. if cost commitment fails, publish the root cancellation last; and
8. otherwise register the execution proposal, at which point ordinary
   execution handlers/reactions may run and cancel it.

Cut 0 must prove that active `_validate()` implementations are validation-only
under this split: they may compute and return an event proposal but may not
mutate domain state or emit child events. Any violating validator is repaired
at that rule before the split proceeds. Do not add a validation callback,
transaction object, compatibility path, or deferred execution proposal store.

Replace the post-completion `_apply_costs(completion_event)` contract with an
execution-stage contract. Audit its four active overrides:

- ordinary actions use the neutral owner cost surface;
- Move and connector/jump families remain explicit no-ops where their
  transaction already settles costs;
- Freedom of Movement's escape cost is committed before its effect; and
- the spell-only late cancellation cost override becomes unnecessary once
  spell costs commit before execution reactions.

No cost mutation remains after a root `COMPLETION` or `CANCEL`.

### 5.2 Item charges

Delete the global `consume_item_charge_before_action_completion` callback and
its repeated installation from `dnd/actions/operations.py`.

The accepted root `ActionEvent` already contains the item UUID, charge cost,
and authorized action lineage. `BaseAction` consumes that item charge once at
the same execution-commit boundary, emitting the existing
`ItemChargeConsumptionEvent` child with the current action event as parent.
The item owns charge mutation; the action owns when the cost is incurred.

### 5.3 Concentration cleanup

The current post-completion concentration cleanup is invalid because it can
remove conditions after the cast terminal.

Migrate the 43 active `ensure_concentration()` call sites across the eight
spell files so each cast closes its cast-local concentration slot before
returning its terminal spell event:

- successful linked effects retain the exact slot;
- an empty new slot is removed with the last effect-phase spell event as
  parent;
- old concentration replacement and linked child removals remain explicit
  condition sub-events; and
- multi-target convolution cleans the cast-local slot once, after all target
  effects and before root completion.

The migration may introduce one ordinary `SpellAction` completion helper for
this exact operation, but no deferred callback, pending-concentration manager,
lease registry, or terminal interception is allowed. Single-target spell
implementations call it at their natural final effect point.

Five active multi-entity concentration spells—`BeaconOfHope`, `HoldMonster`,
`Bane`, `Bless`, and `NecroticBless`—may create/link concentration inside each
per-target `_apply()`. They close concentration exactly once in
`BaseAction`'s existing post-convolution path: after every target application
and `_finalize_aoe()`, using the root effect event as parent, and immediately
before the root completion. Per-target completion must not run empty-slot
cleanup. This remains correct when an early target saves, a later target
links, or the final application cancels.

A hard gate forbids `_cleanup_concentration` from running after `_apply()` has
returned a root terminal.

### 5.4 Cancellation cleanup

Remove the sole active terminal-cancel handler,
`MetamagicAutoRemove`'s `CAST_SPELL/CANCEL` trigger.

Consume the pending metamagic condition at the accepted spell execution
phase, before a later execution reaction may cancel the cast. Successful and
execution-canceled casts therefore share the same earlier causal transition.
The condition-removal lifecycle is a spell child and precedes either terminal.

Add a repository gate forbidding handlers whose trigger phase is
`COMPLETION` or `CANCEL`.

### 5.5 Turn-start duration ownership

Carry the active `TurnStartEvent` through:

- entity condition duration advancement;
- equipped-item condition duration advancement;
- inventory-item condition duration advancement;
- condition removal; and
- any removal saving throw or linked cleanup.

This repairs the measured current graph: three parentless condition-removal
lineages (12 phase versions) inside turn start. They become descendants of the
turn-start tree; no turn wrapper or nested-root exception is allowed.

### 5.6 Round-end environment ownership

`RoundEndEvent` is not inert. Migrate `Encounter._advance_round()` to a full
lifecycle:

1. publish round-end declaration and execution;
2. publish its effect;
3. call `_environment_step(parent_event=effect)`;
4. pass that parent through tile, placed-object, and spatial-condition duration
   advancement and every resulting removal/transform child; and
5. publish round-end completion last.

Only after that tree closes does the encounter increment the round, reset
combatant round flags, and publish the next inert `RoundStartEvent`. Do not
retain environment expiration as unrelated roots or wrap both rounds in one
tree.

## 6. Closed trees are pulled, never pushed

Delete all passive EventQueue observer/listener registries.

`EventQueue.next_committed_tree(source_cursor)` is a read-only query over the
existing append-only source journal:

- it requires the current generation;
- it requires `source_cursor` to begin at the first member of a tree;
- it validates the root and descendant laws over the contiguous source range;
- it returns the exact tuple ending at the root terminal; and
- it returns no tree when that cursor currently points at an incomplete open
  root.

The boundary is derived from stored root/parent/terminal facts. Do not add a
second list of ranges, commit records, batch objects inside EventQueue, or
notification callbacks.

`EventReducer.reduce_next_committed_tree()` pulls this tuple, deep-captures it
once, reduces it, and advances its own source cursor only after success.
`drain_committed_trees()` is a simple loop over that one operation. Existing
`EventBatch`/`BatchId` values may remain as detached reduction output, with
their range now equal to one real committed tree.

For pygame later, one small async pump will repeatedly drain reduced trees and
put detached `EventBatch` values on the game-to-presentation queue. That pump
is a consumer loop, not an EventQueue callback and not part of this cleanup.

## 7. Combat logs are projections of terminal facts

The shared terminal finalizer may build and attach the typed `CombatLogEntry`
to the real completion or cancellation terminal, but it does not notify
anything.

Delete:

- `set_combat_log_callback()` and `push_combat_log()`;
- `Encounter._on_event_combat_log()`;
- encounter combat-log listener fan-out; and
- reducer pending-log reconciliation.

`Encounter` stores its start and optional end source cursors. Its objective
combat-log query derives entries from root terminal events in committed trees
inside that range. It does not duplicate the entries into a mutable causal
store. Existing APIs may retain their return shape while becoming projections.

The condition-immunity standalone text is attached to its real cancellation
event. No fake event is constructed to carry a log.

The subjective reducer derives log deliveries from the same captured real
terminal events. Objective and subjective text therefore share event UUID,
lineage, source index, and typed facts.

## 8. Event-time evidence is not a mechanical callback chain

The existing identified/located/perceiver/reveal computations are pure reads
used to freeze event-time evidence. They emit no events and cannot extend a
causal tree.

This cleanup does not invent a provider protocol merely to rename those
functions. Keep the minimal existing pure query injection until the knowledge
model is reviewed independently. Remove only combat-log notification and
mechanical callbacks. Tests prove that evidence computation cannot publish an
event or mutate the tree.

This distinction is deliberate:

- a pure function supplying immutable event evidence is dependency injection;
- a function invoked because state changed and then causing more state/events
  is a reactive callback and is removed here.

## 9. Reducer simplification

Replace callback entry `on_event_batch(events)` with pull entry
`reduce_next_committed_tree()`.

For each tree the reducer must:

1. read the exact next range from its generation/cursor;
2. verify one parentless root, exact terminal last, no gap, and complete parent
   ancestry;
3. deep-capture that range once;
4. resolve every sensory cause and exact-class/exact-lineage terminal inside
   this captured tree only;
5. retain older detached archives only for memory/provenance values, never to
   complete current causality;
6. route the same captured concrete event subclasses through `Known`/`Unknown`
   masks;
7. derive typed log presentation from captured root terminals;
8. advance its cursor only after the complete result succeeds; and
9. never read live `Entity`, `GridMap`, `Encounter`, or mutable EventQueue event
   values after capture.

Delete callback-tail validation, pending log evidence, cross-archive terminal
repair, and tests that authenticate arbitrary callback payloads.

## 10. Production envelope

Expected core paths:

- `dnd/core/events/events_registry.py`;
- concrete event modules under `dnd/core/events/` that gain native
  `resolve_sub_events()` or inert-fact inheritance;
- `dnd/core/base_actions.py`;
- `dnd/actions/operations.py`;
- `dnd/blocks/base_item.py`;
- `dnd/actions/standard.py`;
- the eight active concentration-spell files containing the 43 inventoried
  calls;
- `dnd/classes/sorcerer.py`;
- `dnd/core/gridmap.py`;
- `dnd/blocks/sensory.py`;
- `dnd/spatial/area_conditions.py`;
- `dnd/entities/entity.py` and the exact block/item duration owners reached by
  turn start;
- `dnd/encounters/encounter.py`;
- `dnd/content/scenarios/battlefield_builders.py` solely for the world
  lifecycle and authored trap/torch parentage described in Section 4.4;
- `dnd/runtime_reset.py`;
- `dnd/event_reduction.py`; and
- focused active tests and architecture gates.

Scope is authorized only for the causal migrations above. Do not change rule
content, numerical mechanics, renderer, pygame, server, deprecated server,
SDK, transport, generated code, editor, cross-language code, general content
recovery, or map authoring. Preserve unrelated dirty work. Never reset,
checkout, clean, commit, or normalize unrelated files.

## 11. Implementation cuts

Each cut stops for coordinator validation. A failing invariant is repaired at
the real event owner; never weaken the gate or add an allowlist.

The hard cuts are dependency-ordered. A legacy mechanism remains unchanged
only until the cut that migrates its last active mechanic, and that same cut
deletes it. Architecture proofs freeze the exact shrinking caller set between
cuts and forbid new callers. There is no permissive/strict queue mode, runtime
allowlist, compatibility wrapper, dual publication, or transitional adapter.
Strict root admission is installed only after the known active root owners are
causally correct, so the kernel never needs exceptions for known-bad trees.

### Cut 0 — exact inventory and baseline

- freeze current tests and normalized node hash;
- AST-inventory every passive callback API, pre-completion user, terminal-phase
  handler, completed-fact producer, action cost override, concentration call,
  root producer, and `_validate()` implementation that mutates state or emits
  an event;
- rerun the real scripted encounter graph measurement; and
- make no production/test edits.

### Cut 1 — native resolution and spatial callback removal

- add the base no-op `resolve_sub_events()` template method;
- add the shared completion/cancellation terminal finalizer derived from real
  journal parentage, while retaining the sole exact terminal handler until its
  Cut 2 mechanic migration;
- migrate GridMap physical settlement, cache invalidation, and attached-light
  settlement to concrete event resolution;
- migrate spatial and nonspatial sensory resolution to concrete event
  overrides;
- replace sensory sequence publication with ordinary parented child writes;
- migrate `SpatialEffectChangeEvent` to its non-vetoable full lifecycle;
- migrate `WorldInitializedEvent` and authored trap/torch settlement to its
  non-vetoable full lifecycle;
- classify inert terminal facts without yet enabling strict global root
  admission;
- delete the per-event callback registry after its two exact GridMap callers
  move;
- delete the indexed pre-completion-system registry after SpatialSenses moves;
  and
- retain only the exact item-charge generic pre-completion callback for Cut 2,
  with an architecture proof forbidding every other or new registration.

The queue still records the existing active roots during this migration cut.
It does not gain a permissive mode or an exception list. No batch or reducer
boundary is changed here.

### Cut 2 — action terminal correctness and final pre-completion removal

- move generic/special action costs to execution commit;
- move item charge consumption to action execution commit;
- migrate all 43 concentration call sites, including the five named
  post-convolution cases, to close before spell terminal;
- move metamagic removal to accepted spell execution;
- remove the last generic pre-completion callback API/list/reset residue in the
  same checkpoint as item-charge migration;
- remove terminal-phase handlers and forbid terminal handler dispatch in the
  same checkpoint as metamagic migration;
- remove late action cleanup contracts; and
- prove success and every cancellation branch end with their terminal last.

### Cut 3 — turn, round, and combat-log ownership

- propagate TurnStart parentage through entity/equipment/inventory duration
  removal;
- migrate RoundEnd environment progression and parentage before its terminal;
- replace Encounter combat-log state/callbacks with journal projection;
- attach standalone immunity text to the real cancellation event;
- prove the real scripted encounter has no second-root interleaving, late
  child, missing parent, or non-final root terminal; and
- retain the existing batch/reducer boundary unchanged until Cut 4.

### Cut 4 — strict queue kernel and pull-only reduction

- add root/descendant/terminal admission after the known active root owners are
  correct;
- implement journal-derived `next_committed_tree()` with no second range
  ledger;
- remove passive sequence/batch/handler observer APIs and batch context/state;
- remove action and encounter batch wrappers;
- replace reducer callback entry with next-tree pull/drain;
- remove pending/cross-archive causal repair;
- migrate the async boundary test to an explicit reducer pump; and
- add direct kernel, pull-boundary, and no-new-observer proofs.

Tests use minimal explicit trees for rejection laws and the real scripted
encounter for active closure. Do not leave a compatibility observer path.

### Cut 5 — governed active closure

- run root admission across all governed active engine lanes;
- repair only concrete missing-parent, late-child, or incomplete-root owners;
- remove tests of deleted internals and retain public event-tree behavior
  proofs; and
- stop for a real rule decision if any mechanic genuinely must outlive its
  root.

### Cut 6 — frozen final review

- freeze exact changed bytes and manifest;
- run the complete accepted active lane twice from cold reset;
- run independent correctness/causality and anti-slop/dependency reviews on
  the same bytes;
- any repair invalidates both reviews and affected validation; and
- certify only after both reviewers reconfirm the final ledger bytes.

## 12. Required proofs

### 12.1 Queue laws

- root opens from the first parentless nonterminal;
- root phases preserve exact class and lineage;
- children/grandchildren resolve to the open root;
- second root, missing/closed parent, cycle, wrong class, and wrong lineage
  fail;
- child terminal does not close;
- root completion and cancellation close exactly once;
- completion and cancellation share terminal evidence/descendant/log
  finalization, while only completion resolves children;
- no event or handler runs after root terminal;
- incomplete root blocks a later root;
- `next_committed_tree()` returns exact contiguous trees and cannot accept an
  invented range; and
- reset changes generation and clears only runtime state.

### 12.2 Native resolution laws

- concrete override is called once before terminal construction;
- base/inert/sensory events do not resolve children;
- spatial commit order is state -> caches/light -> light children -> senses ->
  sensory children -> terminal;
- every emitted event is explicitly parented;
- callback registration order cannot affect mechanics because no mechanical
  registry exists;
- mechanic exceptions propagate and leave the root incomplete; and
- completed-fact publication rejects a non-inert class.

### 12.3 Action and cancellation laws

- action and named-resource costs commit once before effect/terminal;
- accepted but reaction-canceled spells still spend their committed cost;
- declaration-rejected actions spend nothing;
- item charges emit exactly one child and cannot double-spend across
  multi-target applications;
- detached execution proposals cannot erase item-charge, metamagic, reaction,
  or other children already attached to their stored root lineage;
- successful concentration retains its linked slot;
- all-save/empty concentration removes its slot before terminal;
- metamagic removal precedes both successful and execution-canceled spell
  terminals;
- canceled spell roots retain completed Counterspell reaction sub-entries in
  objective and subjective logs; and
- no state mutation or child event occurs after action completion/cancel.

### 12.4 World and perception laws

- wall/door/object/tile geometry settles light from committed state;
- attached light moves on every movement step before sensory reduction;
- subjective occupancy paths invalidate on perceivability changes;
- tile visibility and contents/walls remain distinct in sensory results;
- physical light and subjective darkvision/truesight/invisibility reductions
  retain their accepted separation;
- turn-start refresh contains duration removals and sensory children in the
  same tree;
- round-end environment expirations/removals are children of RoundEnd and
  precede its terminal; and
- `SpatialEffectChangeEvent` cause, sensory child, and terminal share one tree.

### 12.5 Pull/reduction/async laws

- reducer consumes every committed source event exactly once without callback;
- same-tree sensory causality never searches an older archive;
- objective and subjective logs use the same terminal event;
- presentation reads only detached `Known`/`Unknown` event knowledge;
- detached batches expose monotonic, gap-free source ranges sufficient for a
  later presentation acknowledgement design;
- two cold scripted runs are structurally identical; and
- every concrete source event is delivered, intentionally hidden/silent, or a
  fatal diagnostic—never dropped.

Presentation receipts, player-wait policy, the production async pump, and
enemy/render scheduling are explicitly deferred to the pygame MVP. Any
acknowledgement used by this cleanup's tests remains test-local.

## 13. Hard-cut gates

Active production and migrated current tests contain no definition/use of:

- `add_on_event_callback` / `remove_on_event_callback`;
- `add_on_event_sequence_callback` /
  `remove_on_event_sequence_callback`;
- `add_on_event_batch_callback` / `remove_on_event_batch_callback`;
- `batch_on_event_callbacks`, batch depth, or pending batch state;
- `add_on_handler_dispatch_callback` /
  `remove_on_handler_dispatch_callback`;
- `add_pre_completion_callback`, `add_pre_completion_system`, or any renamed
  contributor/listener equivalent;
- `register_completion_sequence`;
- `set_combat_log_callback`, `push_combat_log`, or encounter combat-log
  listeners;
- terminal-phase event handlers;
- post-completion `_apply_costs` or `_cleanup_concentration`;
- reducer `on_event_batch`, `on_combat_log`, callback-tail authentication,
  pending log evidence, or cross-archive causative-terminal repair; or
- caller-authored event range wrappers.

Also reject new names or structures containing the same mechanics under
`observer`, `subscriber`, `contributor`, `listener`, `hook`, `middleware`,
`plugin`, `transaction`, `coordinator`, or `receipt`.

The retained pure evidence functions are exempt only because they are
side-effect-free reads and are proven unable to publish events.

## 14. Acceptance questions

Correctness review must answer yes:

1. Is the root terminal always the final member of its tree?
2. Can every child be traced through stored parents to exactly one root?
3. Are all active success/cancellation mechanics before terminal?
4. Are spatial/light/sensory ordering and turn-start parentage complete?
5. Can the reducer consume only exact journal-derived closed trees?
6. Do objective and subjective logs derive from the same real terminal?

Anti-slop review must answer yes:

1. Is there no callback/contributor/listener registry replacing the deleted
   one?
2. Is subclass polymorphism used only for real event semantics?
3. Is EventQueue limited to validation, storage, indexing, and read-only tree
   extraction?
4. Is there no second causal identity, range journal, event ontology, or
   manager layer?
5. Are rule-owned costs, charges, concentration, and condition cleanup still
   owned directly by those rules?
6. Is the async boundary an ordinary consumer pump rather than engine-side
   callback machinery?

Implementation begins only after both independent reviewers accept the same
exact plan bytes.
