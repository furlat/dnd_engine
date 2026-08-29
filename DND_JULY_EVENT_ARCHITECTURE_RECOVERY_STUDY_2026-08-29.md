# July Event Architecture Recovery Study

Status: **READ-ONLY HISTORICAL STUDY — NOT IMPLEMENTATION AUTHORITY**

Date: 2026-08-29  
Repository: `/mnt/c/users/tommaso/documents/dev/dnd_engine`  
Primary historical reference: `4ebe523f9c3e0a93b6d6cbfdbba3363d1cd3dc35` (2026-07-30)  
Accepted geometry baseline: `513dd970e73f0d7a24678a98ee7ef32886a75032` (accepted Phase 6)  
Current checkout: accepted Phase 6 plus uncommitted event/reduction work

This document records what the working July design actually was, which defects
were genuinely present, which later changes fixed them, and which current
changes contradict that design. It does not authorize edits, deletion,
rollback, or implementation.

## 1. Corrected conclusion

The July architecture was already a coherent D&D-oriented entity-component
design:

- `Entity` was a data aggregate and system composer.
- `BaseBlock` owned ordinary condition indexing and condition-graph traversal.
- `BaseCondition` owned the mechanics and runtime artifacts of one authored
  condition.
- `BaseAction` owned the authored action lifecycle through its established
  template-method seam.
- `Event` values were concrete, typed phase records used synchronously by
  handlers.
- `EventQueue` owned event storage, phase dispatch, lineage, handler routing,
  and dependency-inverted observation callbacks.
- Concrete domain systems depended on the generic event infrastructure; Event
  classes did not import those concrete systems back.

The rule proposed in a quarantined replacement plan—"Events contain immutable
IDs/value snapshots, never live components"—is unsupported and is retracted.
July and accepted Phase 6 both used typed live payloads, including
`ConditionApplicationEvent.condition: BaseCondition`, while retaining zero
late imports and zero import cycles.

The equally broad proposal to replace established component methods and
authored hooks with free-function systems is also retracted. It would rewrite
the working ownership model rather than repair it.

## 2. Reference states

| Reference | What it proves | What it does not prove |
| --- | --- | --- |
| `4ebe523` | The intended July component ownership, typed synchronous event bus, event-time perception evidence, and subjective projection semantics | That every July lifecycle edge was correct or replay-safe |
| `513dd970` | The accepted Tile/world-item/geometry baseline and several bounded event/condition repairs | That all deleted July subjective tests remained covered, or that the August condition-terminal order was correct |
| Current dirty checkout | The exact post-Phase-6 experiment that must be audited | An accepted architecture or implementation baseline |

The historical merge base of `4ebe523` and `513dd970` is exactly `4ebe523`.
The accepted Phase 6 state is therefore a direct descendant of the July
reference, not a separate rewrite.

## 3. Import and ownership evidence

An AST import scan over every `dnd/**/*.py` module produced:

| Tree | Modules | Project imports including local imports | Function-local project imports | `TYPE_CHECKING` imports | Dependency SCCs |
| --- | ---: | ---: | ---: | ---: | ---: |
| July `4ebe523` | 238 | 1,726 | 0 | 0 | 0 |
| Accepted Phase 6 `513dd970` | 204 | 1,449 | 0 | 0 | 0 |
| Current dirty checkout | 206 | 1,465 | 9 | 0 | 1 |

The current seven-module strongly connected component is:

- `dnd.blocks.sensory`
- `dnd.core.base_block`
- `dnd.core.base_conditions`
- `dnd.core.base_tiles`
- `dnd.core.events.encounter_events`
- `dnd.core.events.world_events`
- `dnd.core.gridmap`

All nine local imports are uncommitted. They are the reverse edges used by
Event subclasses' new `resolve_sub_events()` methods to call sensory, GridMap,
and condition owners. The existing architecture gates were changed to
allowlist those imports and then to ignore function-local imports when checking
one dependency boundary. That concealed the cycle rather than resolving it.

This directly validates the current `AGENTS.md` rules:

- entities are data structures and system composers;
- imports form DAGs;
- no late imports, `TYPE_CHECKING`, or `getattr`-style dependency evasion.

"Not an OOP codebase" must not be misread as "ban component methods" or "ban
typed authored hooks." The historical problem is autonomous orchestration in
passive Event records, not the existence of methods on owning components.

## 4. July component responsibilities

### 4.1 Entity

July `Entity` composed abilities, skills, saves, health, equipment, action
economy, senses, inventory, appearance, and spellcasting. Its
`add_condition()` boundary owned entity-specific prerequisites:

1. bind the incoming condition to the runtime owner;
2. establish source and target names;
3. test static/contextual immunity;
4. perform any application saving throw;
5. delegate authored mechanics to `condition.apply()`;
6. index the accepted result on the entity.

Evidence: `4ebe523:dnd/entity.py:887-953`.

This is a legitimate aggregate/composer boundary, not a condition object
reaching upward into its owner.

### 4.2 BaseBlock

`BaseBlock` was the common condition-bearing component/container. It owned:

- `add_condition()` for non-Entity blocks;
- `remove_condition()` and `remove_condition_by_uuid()`;
- `_remove_condition_tree()` for same-block and cross-block dependency
  traversal;
- condition indexes by name, UUID, and source;
- duration advancement.

Evidence: `4ebe523:dnd/core/base_block.py:819-1002`.

Historical commits reinforce that intent:

- `4d3aae6`: condition removal moved to Entity responsibility;
- `7766fc3`: common condition management/removal moved down from Entity to
  `BaseBlock` so every condition-bearing block could own the same contract.

### 4.3 BaseCondition

`BaseCondition.apply()` invoked the authored `_apply()` hook and recorded the
exact modifiers, event handlers, subconditions, and spatial handlers produced
by that condition. `cleanup_own_state()` removed only those owned artifacts and
ran the authored `_remove()`/`_expire()` hooks.

Its own documentation explicitly delegated same-block and cross-block graph
traversal to `BaseBlock._remove_condition_tree()`.

Evidence: `4ebe523:dnd/core/base_conditions.py:573-690,710-726,781-825`.

The hundreds of authored `_apply()` implementations are rule content, not
accidental object-oriented infrastructure. A blanket migration of these hooks
would be a new engine rewrite.

### 4.4 BaseAction

`BaseAction.apply()`/`_apply_action()` owned declaration, validation, target
resolution, authored `_apply()`, costs, cancellation costs, and concentration
hooks. Functional action APIs bound/discovered an action and delegated to this
owner; they did not replace the lifecycle.

Evidence: `4ebe523:dnd/core/base_actions.py:1630-1703` and accepted Phase 6
`dnd/actions/operations.py:459,494-534`.

### 4.5 Spatial owners

July spatial conditions were authored condition owners that composed their
footprint, tile markers, spatial handlers, and terrain/light effects. Accepted
Phase 6 intentionally separated the replacement `SpatialCondition` family:
it owns its world footprint directly and exposes authoritative
`activate()`/`deactivate()` entry points.

Ordinary conditions and independent spatial conditions therefore have
different runtime-owner removal paths. An Event class cannot correctly replace
both with one global registry scan.

## 5. July Event/EventQueue semantics

July used one concrete typed event space.

### 5.1 Identity and phases

- Every `post()` or `phase_to()` created a new event UUID while preserving
  `lineage_uuid`.
- `parent_event` identified a causal parent event version; it did not identify
  the previous phase.
- declaration, execution, and effect were handler-visible;
- completion was stored but skipped handler dispatch;
- cancel recorded an aborted lineage and stopped the current handler chain.

Evidence: `4ebe523:dnd/core/events.py:236-250,426-589,1631-1664`.

### 5.2 Typed synchronous interception

Handlers received the concrete Event subclass and could return the same,
modified, or canceled typed value. The D20 replacement regression explicitly
asserted `event.original_roll is original_roll` while a handler replaced the
effective final roll.

Evidence: `4ebe523:tests/engine/test_dice_event_semantics.py:335-375`.

Live typed payloads were therefore intentional and functional for synchronous
mechanics. They did not introduce an import cycle because condition Event
classes remained co-located with `BaseCondition`; the generic event package did
not import the concrete condition owner.

### 5.3 Queue and dependency direction

`EventQueue` stored the incoming event, synchronously dispatched matching
handlers, stored handler-produced versions, updated lineage/parent indexes, and
notified passive observers. Concrete sensory and GridMap systems registered
themselves with the generic queue.

This dependency direction was acyclic:

```text
Entity / BaseBlock / BaseCondition / GridMap / SpatialSensesSystem
                         ↓
                 Event / EventQueue
```

The current `resolve_sub_events()` change reverses that arrow:

```text
Event subclass
    ↓ imports and executes
GridMap / SpatialSensesSystem / BaseCondition registry
```

That reversal is the direct cause of the current late-import cycle.

### 5.4 Completion and observation

Before a completion was stored, July ran explicit pre-completion systems,
captured observer evidence and child lineage, generated a typed
`CombatLogEntry`, and notified the top-level encounter log callback.

The generic callback surfaces already existed in July; they were not invented
by the recent work. They mixed responsibilities and deserve later scrutiny,
but replacing them with virtual Event methods that call upper-layer systems is
not a cleanup.

## 6. July condition lifecycle and the August regression

### 6.1 July application

```text
Entity.add_condition
  → declare typed condition application
  → immunity/save gates
  → condition._apply(declaration)
  → install authored modifiers/handlers/subconditions
  → effect
  → mark applied
  → completion
  → owner indexes accepted condition
```

Same-block children were applied through their owner, and linked children were
delegated to the linked target block.

### 6.2 July removal

```text
owner removes root/descendant indexes
  → recursively remove same-block children
  → ask linked target blocks to remove their own children
  → clean the root's own mechanics and publish its terminal
  → evaluate reverse any/last child-removal policy
```

Evidence: `4ebe523:dnd/core/base_block.py:819-943`.

The mechanics/ownership relationship was substantially correct: children were
removed before the parent terminal, and cross-owner children were removed by
their own blocks. Two defects remained:

- indexes were removed before a removal could be canceled;
- every descendant removal reused the same external `parent_event`, flattening
  descendant removal lineages instead of parenting them to their direct
  semantic cause.

### 6.3 August 1 change

Commit `e745f38` correctly fixed canceled application/removal consistency and
retained handler-modified declaration values. However, it changed removal to:

```text
clean root and publish root completion
  → discard root indexes
  → remove same-block and linked descendants
```

Evidence: `e745f38:dnd/core/base_block.py:1212-1273`.

Accepted Phase 6 inherited this ordering. It is a genuine regression: the
parent claims terminal completion before mandatory dependent teardown.

The recovery target is therefore not literal July code. It must combine:

- the later cancellation/index safety;
- the original owner-driven child-first teardown;
- direct causal parentage for descendant removals;
- the root terminal only after required descendant mechanics are finished.

The exact implementation remains a plan decision. It must not be hidden in
Event terminalization, callbacks, context managers, transactions, or a new
manager/service abstraction.

## 7. Genuine bounded July defects

The historical architecture was coherent, but the following defects are real:

1. Event construction auto-registered a declaration but could not return a
   handler's modified/canceled replacement to the constructor caller.
2. A condition whose effect event was canceled could still be marked applied.
3. Condition indexes were discarded before removal cancellation was known.
4. Base condition `_apply()` created effect from the declaration again rather
   than chaining from the accepted execution event.
5. Condition removal checked the returned effect but completed the original
   declaration; expiration could form parallel same-lineage branches.
6. Saving throws parented the D20 child to the request declaration rather than
   the accepted execution and did not stop after execution cancellation.
7. CANCEL was described as terminal/non-handler-visible while queue dispatch
   skipped only COMPLETION.
8. Missing parents and late children were intentionally tolerated, so the
   event list was not a strictly closed causal journal.
9. Stored phase values used shallow copies and could retain mutable,
   registry-backed payload aliases.

Items 1-3 received legitimate later fixes. Items 4-9 require focused decisions
and public behavior tests; they do not justify replacing the architecture.

## 8. July subjective projection and replay semantics

July did not have `EventKnowledge`, `CapturedEvent`, or `EventReducer`.
Instead:

- the raw queue was pullable by append cursor;
- event storage captured event-time observer/position evidence;
- `SpatialSensesSystem` was a concrete pre-completion system that updated live
  `Senses` and emitted typed sensory facts;
- typed `CombatLogEntry` trees were projected subjectively;
- server observation journals reduced the raw stream into session-subjective
  state and replay frames.

The server implementation is not the architecture to reproduce in the new
in-process Pygame client. Its preserved semantic contracts are relevant:

- deferred delivery must still use event-time evidence;
- later visibility must not retroactively reveal old events;
- later loss of visibility must not erase identity known at event time;
- hidden identity is scrubbed without mutating the objective source;
- a visible child retains causal meaning when its parent is hidden;
- aggregates are rebuilt from visible children only;
- batches preserve storage order and do not silently skip input;
- replay freezes recorded subjective inputs rather than reconstructing them
  from later objective state.

Historical proofs include:

- `tests/manual/test_28_subjective_observation_stream.py`;
- `tests/manual/test_36_seamless_subjective_runtime.py`;
- `tests/manual/test_113_subjective_combat_log_projection.py`;
- `tests/manual/test_123_subjective_player_replay.py`;
- `tests/manual/test_124_worker_subjective_replay.py`.

Several of these tests were later deleted. Accepted Phase 6 passing tests do
not prove those semantics still exist.

## 9. Why the current reducer is rejected

The current uncommitted implementation adds approximately:

- 462 lines in `dnd/core/events/knowledge.py`;
- 2,010 lines in `dnd/event_reduction.py`;
- 4,628 lines of dedicated new tests, plus architecture tests.

It is not used by a production consumer outside those tests. More importantly:

1. It enumerates only a subset of the concrete Event classes.
2. An unsupported concrete Event produces `ERROR` coverage with no delivery.
3. The reducer still advances `source_cursor`, archives the tree, and treats
   the slot as acknowledged.
4. The test consumer maps that result to an `"errored"` receipt.

This permanently consumes an unsupported presentation fact. It violates the
MVP requirement that every engine event be represented or surfaced as an
actionable missing-presentation diagnostic.

The snapshot boundary is also mistimed. `EventArchive.capture_queue_range()`
deep-copies events only after a causal tree is considered closed. Mutation
between original storage and late capture is therefore recorded at capture
time, not event time. The implementation pays to clone forbidden live fields
and then refuses to expose them through `_FORBIDDEN_ROOT_FIELDS`.

Finally, the reducer creates another formatting policy over Event fields while
the engine already has typed `CombatLogEntry` projection. This duplicates
presentation authority.

## 10. Why the current Event terminal hooks are rejected

The dirty checkout adds:

- `Event.resolve_sub_events()`;
- `Event.finalize_terminal()`;
- virtual overrides on condition, turn, life-state, death, spatial-effect, and
  spatial-change Events;
- direct calls from these Event records into sensory, GridMap, and condition
  registries.

This is not event-native causality. It is callback orchestration renamed as
virtual dispatch, with the dependency arrow reversed.

The `LifeStateChangeEvent` implementation is also concretely wrong for ordinary
conditions. It scans the global `BaseCondition` registry and calls
`remove_from_runtime_owner()`, but ordinary conditions intentionally return
`False` from that method because their owner is the `BaseBlock` condition tree.
The Event then raises if the condition remains applied. Independent spatial
conditions are the family that legitimately overrides that removal seam.

Event records must remain facts/interceptor values. They must not become
autonomous executors of unrelated domain systems.

## 11. Test-quality regressions in the current work

The new tests frequently freeze internal machinery rather than observable
behavior:

- exact private class inventories and manifest shapes;
- private cursor ranges and exact tree counts;
- AST implementation details unrelated to a public contract;
- a test-local queue/receipt consumer absent from production;
- object identity between a journal log and its mutable source Event;
- explicit acceptance of cursor advancement after unsupported Event errors.

This conflicts with `HOW_TO_TEST.md`: gameplay tests should assert public
state/events/presentation results, while architecture tests should protect only
explicit dependency rules.

The dependency tests were additionally weakened to allow the exact local
imports that violate the repository DAG rule.

## 12. Historically grounded recovery boundary

Any future implementation plan must start from these constraints.

### Preserve

- accepted Phase 6 Tile/world-item/geometry state;
- concrete typed Event subclasses and stable lineage;
- synchronous typed handler interception;
- `Entity` as aggregate/system composer;
- `BaseBlock` as ordinary condition graph/index owner;
- `BaseCondition` as owner of its authored mechanics and exact artifacts;
- `BaseAction` as owner of authored action execution;
- independent `SpatialCondition.activate()`/`deactivate()` ownership;
- later declaration/cancellation/index rollback repairs;
- accepted scalar aftermath facts such as resulting HP/AC and stable behavior
  identity;
- event-time observer evidence and typed `CombatLogEntry` projection semantics.

### Remove or redesign before acceptance

- Event `resolve_sub_events()` domain execution;
- Event subclasses importing GridMap, sensory, or condition owners;
- all late-import allowlists and module-only cycle checks;
- the current unsupported-event-consuming reducer protocol;
- the generic `Known`/`Unknown` path-capability layer unless a concrete public
  need independently justifies it;
- duplicate text formatting over Event fields;
- fake multi-phase lifecycle records that intentionally bypass handlers;
- tests whose only contract is private machinery.

### Repair surgically

- child-first condition teardown while preserving cancellation/index safety;
- direct semantic parentage for dependent removal Events;
- the bounded condition phase-chain defects;
- saving-throw execution cancellation and child parentage;
- exact CANCEL semantics;
- an event-time, detached presentation boundary only where asynchronous
  rendering/replay actually requires one;
- explicit missing-presentation diagnostics that do not consume unsupported
  source events.

### Do not introduce

- a parallel Event schema;
- a global Event-kind switch or exhaustive private manifest as the primary
  mechanics model;
- new manager/controller/service/transaction/receipt layers;
- free-function rewrites of established component lifecycles;
- callback chains, context-manager causal protocols, or Event-class domain
  orchestration;
- server/SDK/transport work for the in-process Pygame MVP.

## 13. Required decision before implementation

The evidence supports a selective recovery from accepted Phase 6, not a blind
July rollback and not a patch-on-patch repair of the current architecture.

Before any code is touched, the human architect must approve a practical
recovery plan that identifies, hunk by hunk:

1. current changes to discard because they implement the rejected machinery;
2. current scalar or log improvements that are independently worth retaining;
3. exact accepted Phase 6 seams to restore;
4. each bounded historical defect to repair;
5. public behavior tests that prove the result without freezing internals;
6. the in-process presentation boundary that the Pygame MVP genuinely needs.

No implementation is authorized by this study.

## 14. Independent audit record

Three independent read-only audits were commissioned:

- causality/history audit;
- ECS ownership/import-DAG audit;
- regression/subjective-projection/anti-slop audit.

Their findings were incorporated into this draft. Exact-byte review status is
recorded only after reviewers inspect this completed file.
