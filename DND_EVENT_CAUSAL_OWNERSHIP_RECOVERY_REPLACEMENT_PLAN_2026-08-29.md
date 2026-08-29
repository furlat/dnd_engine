# QUARANTINED — SUPERSEDED OOP-CENTRIC RECOVERY DRAFT — DO NOT IMPLEMENT

> This draft is preserved as evidence. It partially adopted ECS terminology
> while still assigning cross-component orchestration to autonomous objects and
> lifecycle hooks. It is superseded by
> `DND_ECS_EVENT_CAUSALITY_RECOVERY_PLAN_2026-08-29.md` and grants no authority.
>
> Pre-quarantine SHA-256:
> `d6ce130ff597d307012b3566800aff4fb810006e39f211200be485838ae2bcdc`

## Historical title: Event Causal Ownership Recovery — Replacement Plan

**Status:** QUARANTINED — REJECTED — NO IMPLEMENTATION OR ROLLBACK AUTHORITY  
**Scope:** recover the engine event work from the rejected native-resolution cleanup without changing the accepted Tile/world-item model  
**Implementation may begin only after:** the user accepts this document, the recovery boundary is selected, and the exact first implementation cut is separately authorized

## 1. Why this document exists

The previous event-cleanup plan is rejected. It put domain work into Event subclasses, used terminal completion as an orchestration hook, flattened causal relationships to convenient outer roots, and enabled strict tree admission before the callers were ready. The resulting implementation has real gameplay regressions, not merely stale tests.

The rejected plan remains preserved as evidence:

- `DND_EVENT_NATIVE_CAUSAL_RESOLUTION_CLEANUP_PLAN_2026-08-28.md`
- pre-quarantine SHA-256: `a739521673ecdfed95c237f28f8c5fbcf5d6e8aede4a5f56a926225b265fdc81`
- quarantined SHA-256: `415963af7e9d90885b8fe17a1c58beabcef42217bd5116399d81cf0a3cabeeb8`
- associated implementation ledger: `DND_EVENT_NATIVE_CAUSAL_RESOLUTION_CLEANUP_IMPLEMENTATION_LEDGER_2026-08-28.md`
- ledger SHA-256: `3910fa979f3586b5a8ad0c0508dfdd4ce2fab1f0fcb00156d691a81ec75d4ab4`

The rejected plan and ledger must not be deleted, silently edited into acceptance, or used as implementation authority.

This replacement is deliberately independent of the current implementation. It first defines the correct engine, then provides a controlled decision between rollback/reimplementation and repair-forward.

## 2. Non-negotiable outcome

The engine must produce one append-only causal event tree for each public operation while preserving the component/system authority that already exists in the domain model.

The runtime roles are:

1. **Entity/composition identity:** identifies the runtime subject and exposes its composed components. It is not a god object that owns every mechanic.
2. **Authoritative component store:** holds the state being changed: condition indexes, Health, ActionEconomy, Senses, Inventory/item state, GridMap indexes, and similar blocks.
3. **Rule/operation system:** reads the relevant components, applies D&D rules, mutates the authoritative stores, and emits the lifecycle facts. In the current Python code this is often exposed as a method on `Entity`, `BaseBlock`, `BaseAction`, `SpatialCondition`, or `Encounter`; that call location does not turn the object into an autonomous orchestrator.
4. **Concrete Event:** records the proposed, accepted, committed, canceled, or completed fact. It does not find components or execute mechanics.
5. **EventQueue:** dispatches phase rule handlers, stores immutable event versions, enforces structural tree rules, and exposes closed trees by cursor. It does not coordinate gameplay.
6. **Reducer:** reads a detached closed tree and masks facts for one observer. It never repairs mechanics, consults live state to fill missing causality, or invents a parallel event ontology.
7. **Renderer/client:** consumes the reduced stream. It never participates in engine commitment.

The authoritative flow is therefore:

```text
public command/rule operation
  -> system queries the exact composed components/indexed relations
  -> system publishes and inspects the operation lifecycle phases
  -> system mutates the authoritative component stores at the declared seam
  -> system invokes the next concrete rule/system for mandatory consequences
  -> nested systems publish direct child lifecycles
  -> initiating system closes the event only after every child closes
  -> EventQueue exposes the closed tree
  -> reducer captures and censors that same tree
  -> presentation consumes the reduced result
```

There is no terminal callback, completion resolver, Event-driven component discovery, raw registry scan, or second orchestration layer in this flow.

### 2.1 ECS/D&D interpretation

This repository is an ECS-like composition adapted to D&D rather than a traditional object graph:

- `Entity.uuid` is identity and Entity composes Blocks.
- `BaseBlock.blocks`/`values` and concrete blocks are component storage and capability surfaces.
- Conditions, modifiers, granted actions, links, memberships, and source UUIDs are runtime components/relations attached to those stores.
- `BaseBlock.active_conditions*`, component-local source maps, GridMap occupancy/spatial indexes, and item/component indexes are authoritative query surfaces.
- Actions/spells/encounter steps are commands or rule systems operating over those components.
- Concrete condition/action subclasses may carry D&D behavior, but they do not acquire authority over unrelated component stores.
- Events are append-only facts emitted by systems. They are not systems and are not another component registry.

The recovery does not introduce formal `System` base classes, a component framework, a dispatcher service, or a new ECS package. It preserves the current Python representation and corrects responsibility: component data remains where it is; the existing functional/system seams perform ordered work; leaf overrides survive only where a D&D rule truly varies and never become lifecycle orchestration.

Throughout this document, “owner” is shorthand for **the authoritative component store plus the existing rule/system seam that is allowed to mutate it**. It never means that arbitrary object methods should call one another to simulate ownership.

Indexed ECS queries are valid when they use an authoritative store. What is forbidden is treating identity registries such as `BaseCondition._registry` as an active-world query, because they contain objects without proving active membership, manifestation, target ownership, or spatial authority. If a required query has no authoritative existing index, the plan must expose that gap; it may not hide it behind a scan or invent an index during implementation.

`EventHandler` rule processors are distinct from passive callbacks. A rule processor may react synchronously at a documented phase inside the open tree and emit nested mechanics through the relevant component system. Logging, reduction, rendering, and delayed cleanup may not use handler/callback side channels.

## 3. Historical ownership that the recovery must preserve

The ownership decision is not speculative:

- `4d3aae6` moved condition-tree removal out of `BaseCondition` and into Entity.
- `7766fc3` deliberately generalized the same function to `BaseBlock`, deleting the duplicate Entity removal implementation.
- `1a918b6` kept ordinary conditions BaseBlock-owned and added only the narrow independently owned `SpatialCondition` path.
- The accepted spatial recovery plan explicitly kept `BaseBlock._remove_condition_tree()` for ordinary conditions, `SpatialCondition` for its independent lifecycle, and GridMap membership as the active spatial authority.

The recovery must restore and preserve that direction. It must not generalize runtime ownership back into Event, `BaseCondition._registry`, or a new manager.

## 4. Core causal laws

These laws apply before any implementation detail:

1. A nested event's `parent_event` is the exact stored phase that directly caused it, not merely an outer event that keeps the queue open.
2. A parent terminal is stored only after every direct and indirect child is terminal.
3. Completion and cancellation are closure facts. They begin no mechanics, cleanup, lookup, notification, observer projection, or child publication. Pure structural/log metadata may be computed from already stored facts immediately before atomic terminal storage.
4. Every event-emitting owner inspects cancellation from the phase or child it invoked. Cancellation is never ignored.
5. No authoritative mutation happens before the operation's declared veto boundary has been accepted.
6. A fact describing state that is already irreversibly committed is non-vetoable for its entire stored lifecycle, not only its declaration. It is stored through one structural EventQueue primitive that performs normal tree admission and storage without handler dispatch.
7. Unexpected exceptions do not fabricate a success terminal. The open tree remains diagnostic evidence and the generation is treated as failed.
8. Structural validity belongs to EventQueue. Semantic parentage belongs to the concrete domain owner and is proved by owner-specific tests.
9. The exact same committed facts feed objective logs, subjective reduction, replay, and presentation.
10. No test may call flattened sibling ancestry correct merely because all descendants share the same root.

Phase vocabulary remains small:

| Phase | Meaning |
|---|---|
| `DECLARATION` | proposed intent and declaration-time veto |
| `EXECUTION` | accepted prerequisites and execution-time rules |
| `EFFECT` | the owner-specific commit authorization; handler-visible before the associated mutation unless the lifecycle records an already committed fact |
| `COMPLETION` | successful closure after all consequences |
| `CANCEL` | rejected closure with no work after the rejected boundary |

This table does **not** impose one universal cost or mutation phase on every event family. The commit table below fixes each changed family. Existing handlers on `EXECUTION` and `EFFECT` must be inventoried before changing a family.

## 5. Canonical component/system authority matrix

| Operation | Authoritative component store | Existing rule/system seam | Event's permitted role |
|---|---|---|---|
| Apply condition to an Entity | target Entity composition for immunity/save inputs; inherited BaseBlock condition indexes for collection/policy | `Entity.add_condition()` | Record proposal, save, application, and result |
| Apply condition to Tile/item/other block | target BaseBlock condition indexes | `BaseBlock.add_condition()` | Record the condition-system operation |
| Ordinary condition indexes, policy, leases, dependency traversal | Target BaseBlock | `add_condition`, `remove_condition`, `remove_condition_by_uuid`, `advance_duration` | No policy or index ownership |
| One condition's modifiers/handlers/custom mechanics | condition component plus target component stores | condition behavior invoked once by the target condition system | Record those mechanics; never install itself into target indexes |
| Same-block subcondition | same BaseBlock condition store; parent condition stores the relation edge | BaseBlock condition-tree traversal system | Child lifecycle is caused by parent lifecycle |
| Cross-block linked condition | child target's BaseBlock condition store; parent condition stores link | `BaseCondition.add_linked_condition`, child `BaseBlock.remove_condition_by_uuid` | Carry exact causal parent only |
| Most-potent lease set and promotion | Target BaseBlock | existing BaseBlock arbitration helpers | Record admitted/dormant/promoted/removed facts |
| Independent spatial condition | SpatialCondition world-effect component plus GridMap membership | `activate`, `deactivate`, `progress_spatial_duration` | Record the independent spatial-system lifecycle |
| Spatial footprint and Tile indexes | GridMap | existing spatial-condition position/index system | Record committed spatial changes |
| Entity position/occupancy | entity position component plus GridMap occupancy indexes | existing position update/settlement system | Record physical transition and children |
| Light propagation/cache | GridMap/light component indexes | existing light recomputation system | Record light changes |
| Subjective perception projection | each Senses component plus SpatialSensesSystem | `reduce_event`, `recompute_observer` | Record explicit sensory consequences; Event never invokes it at terminal |
| Action validation and settlement timing | action command data plus source/target components | `BaseAction.apply` / `_apply_action` rule system | Record action lifecycle and direct children |
| Action economy and named resources | source ActionEconomy/component capability | existing consume methods | Record exact accepted consumption |
| Item charge/destruction | exact item component state | `UsableItem.consume_charge_with_event` | Record exact item mutation |
| Concentration cast-local sequencing | caster condition store plus Concentrating relation/slots | `SpellAction.ensure_concentration`, caster condition APIs | Keep concentration children under the cast |
| Turn and round ordering | Encounter scheduler state | `start_turn`, `end_turn`, `next_turn`, round systems | Event phases are causal records/veto points; Encounter remains the scheduler |
| Entity turn mechanics | acting Entity composition and owned Blocks | `on_turn_start`, `on_turn_end` systems | Record explicit child operations |
| Life state | Health component plus derived entity capability modifiers | damage/healing/death/revival systems | Record the already accepted transition; the installed rule initiates external cleanup through its actual component system |
| Event structure and retrieval | EventQueue | publish/store/admission/cursor methods | Structural only |
| Observer censorship | EventReducer/EventKnowledge | closed-tree pull boundary | Read-only same-type masking only |

`BaseCondition._registry` remains identity lookup. It is never an active-condition inventory, source-left-play resolver, lease authority, or world-membership database.

### 5.1 Exact commit and veto boundaries

| Family | Stored causal boundary | Mutation timing | Cancellation/failure rule |
|---|---|---|---|
| Ordinary condition apply/remove | normal handler-visible `DECLARATION`, `EXECUTION`, `EFFECT` | target owner mutates only after its `EFFECT` is accepted | pre-effect cancellation changes no authoritative condition state |
| Mandatory owned sub/linked retirement after accepted parent removal | parent removal `EFFECT`; child lifecycle stored entirely as authoritative phases without handler dispatch | actual child condition/spatial system retires its store inside the parent operation | not vetoable; any exception is fatal generation failure, never a deliverable parent/child split |
| Optional membership/application attempt | exact spatial/rule `EFFECT` | target owner mutates only after the child `EFFECT` is accepted | immunity/save/handler cancellation is a valid absence and parent inspects it |
| Entity position/occupancy | pure validation of declaration/execution precedes mutation; after mutation effect/completion are authoritative non-dispatching phases | entity position component/GridMap existing committed-spatial-fact seam | validation failure changes nothing; post-commit exception poisons generation and requires full world reset |
| Spatial footprint create/transform/remove | same committed-spatial-fact seam | declaration/execution validate first; SpatialCondition/GridMap commit once; effect/completion are authoritative phases | post-commit publication or mandatory cleanup failure is fatal/full reset |
| Object placement/location | builder/item/GridMap validate declaration/execution facts before mutation | placement commits once; effect/completion are authoritative phases | no supported veto after commit; failure after commit is fatal/full reset |
| Light/cache recomputation | exact committed physical/spatial `EFFECT` | GridMap/light owner recomputes synchronously | failure after physical commit is fatal/reset |
| Sensory projection | exact physical, light, condition, or life-state effect | SpatialSensesSystem recomputes synchronously and emits committed projection facts | failure prevents owner terminal; if upstream state committed, generation resets |
| Action costs, item charge, pending metamagic | stored accepted Action `DECLARATION`, after pure validation and before Action execution dispatch; admitted child lifecycles are authoritative non-dispatching facts | source ActionEconomy/item/condition stores commit once | no gameplay veto after pure admission; invariant failure is fatal, and later Action execution cancellation keeps these committed costs |
| Action reactions | handler-visible Action `EXECUTION` | no action effect state before execution accepts | cancellation prevents effect state but does not refund documented pre-execution costs |
| Action effects/concentration | accepted Action `EFFECT` | concrete action/spell and actual target owners mutate | every consequence closes before Action terminal |
| TurnStart/TurnEnd/RoundEnd | normal handler-visible lifecycle owned by Encounter/Entity operations | no scheduler advancement/notification before root `EFFECT` accepts | cancellation stops that boundary; Encounter does not notify, advance, or increment |
| LifeStateChange | entire lifecycle stored as authoritative non-dispatching phases after Health transition | Health and derived capability state are already committed | non-vetoable record; source-local anchor cleanup follows through actual component systems before terminal |
| WorldInitialized | builder-owned normal lifecycle | validate authored inputs before `EFFECT`; owner calls begin after `EFFECT` | root cancellation commits nothing; any post-effect authored-child failure is fatal/reset |
| Terminal metadata | terminal candidate before atomic store | pure calculation from immutable event payload and already stored descendants only | failure leaves terminal unstored and generation failed; no domain calls |
| Observer reduction/log delivery | detached closed-tree pull | no domain mutation | failure does not advance reducer cursor; source journal remains closed and retryable |

### 5.2 Minimal structural storage primitive

The current API contract is not good enough for the table above:

- `EventQueue.preflight()` accepts only `DECLARATION` and `EXECUTION` proposals and runs validation-only handlers.
- `EventQueue.publish_preflighted()` claims the exact version was accepted by `preflight()`.
- Therefore using `publish_preflighted()` for an `EFFECT` or `COMPLETION` that never passed `preflight()` is rejected contract abuse, even though the current method body happens to store it.

The replacement introduces exactly one queue-kernel semantic, implemented by renaming/extracting the current structural store behavior rather than adding a layer:

```text
EventQueue.store_authoritative_phase(event)
```

It accepts one unregistered, noncanceled Event phase whose outcome has already been determined by the calling rule/system; performs normal tree admission; timestamps and stores it; and dispatches no handlers. It contains no family switch, component lookup, callback, ownership rule, or mutation. `preflight()`/`publish_preflighted()` remain paired only for the declaration/execution proposals they actually support, or are mechanically folded into the new name if the final implementation can remove the ambiguity without two public paths.

`store_authoritative_phase()` is permitted only for the committed-state, life-state, mandatory-retirement, and admitted action-prerequisite families enumerated in section 5.1. The restriction lives in reviewed call sites and architecture dependencies, not a runtime caller allowlist or manager.

## 6. Explicitly forbidden design

The replacement must not contain any of the following:

- `Event.resolve_sub_events()` or an equivalent completion hook that executes mechanics.
- Event subclasses importing Entity, BaseBlock, GridMap, SpatialCondition, SpatialSensesSystem, or spell owners to perform lifecycle work.
- Mechanics in `finalize_terminal`, completion handlers, log builders, reducer capture, or renderer delivery.
- Global scans of `BaseCondition._registry` to infer active ownership.
- New lifecycle coordinators, services, managers, controllers, transaction wrappers, context managers, callback registries, priority chains, or event-type switches.
- Generic `begin_*` / `finish_*` protocols added across the domain. Each public owner operation performs its operation synchronously and closes its own event before returning.
- A generic runtime-owner interface for ordinary conditions.
- Parenting every descendant to TurnStart, LifeState, RoundEnd, spell root, or another convenient outer effect.
- New roots opened after a semantic owner completed too early.
- State mutation followed by a vetoable publication describing that state.
- Ignoring child cancellation, including metamagic removal and linked-condition cleanup.
- No-op virtual hooks such as a base `_close_concentration()` whose only body discards an argument.
- Architecture allowlists that legalize reverse event-to-domain imports.
- Tests whose primary proof is an internal call count, `handler_calls == []`, a hash, or a flattened root relationship.
- A second `CanonicalEventView`/DTO event hierarchy. Subjective knowledge masks the concrete captured event.

## 7. Correct operation shapes

### 7.1 Ordinary condition removal

`BaseBlock.remove_condition*()` remains the single condition-system entry point over the target's indexed condition components. It is not moved into each condition object or an Event. No public paired lifecycle API is introduced.

Within that one synchronous system call:

1. Resolve the exact condition from its authoritative indexes.
2. Publish and inspect that condition's removal declaration, execution, and effect boundary.
3. Keep the accepted removal effect open.
4. Remove same-owner subconditions depth-first through the same BaseBlock.
5. Remove cross-block linked children through each child's actual BaseBlock.
6. Process reverse-parent policy through the actual parent owner.
7. Retire condition-owned actions and condition-specific runtime mechanics.
8. Remove the condition from authoritative indexes and registry.
9. Perform most-potent promotion, when required, as a child of the manifested lease removal effect.
10. Complete the parent removal only after all children and promotion close.

The old functional invariant is restored: children are owned and removed before the parent's terminal. The new causal invariant is added: each child removal is parented to the exact parent removal effect.

Condition-specific polymorphism is a leaf behavior carried by the condition component and is limited to that condition's own mechanics. The BaseBlock condition system, not the condition object, traverses relations and phases the lifecycle. The current convention in which `_remove()` both mutates mechanics and advances an event phase must be inventoried and normalized to one meaning before implementation. There must be one committed leaf-removal behavior plus the already distinct uncommitted-discard path. Redundant `_remove`/`_release` wrappers are deleted rather than retained beside it.

Mandatory cascade cancellation has one exact rule:

- Before the root removal effect is accepted, normal vetoes may reject the operation and no owned state changes.
- After that effect is accepted, owned sub/linked cleanup is mandatory and cannot leave a parent removed with children active.
- The child target's actual condition/spatial system performs the retirement against its authoritative store. Every phase of that mandatory child lifecycle is stored non-vetoably with `EventQueue.store_authoritative_phase()`.
- A normal condition-removal handler is not dispatched for these post-commit child facts. Any rule that may prevent the cascade must intercept the owning root before its effect. Any rule that reacts after mandatory removal must be invoked explicitly by the condition/rule owner and publish its own child event; it may not rely on a generic removal callback.
- Child removal events remain complete journal facts with exact ancestry; they are not discarded, flattened, or reduced to `del` operations.

This is the simplest atomic rule that avoids a new transaction planner or compensation layer. The implementation inventory must identify and migrate every current child-removal veto/reaction before this rule is enabled. The cross-block call uses one narrow BaseBlock condition-system path for mandatory dependency retirement; it is not a runtime-owner protocol and is unavailable to ordinary callers.

```text
ConditionRemoval DECLARATION / EXECUTION / EFFECT
├─ same-block child ConditionRemoval ... COMPLETION
├─ linked-owner ConditionRemoval ... COMPLETION
├─ optional reverse-parent retirement ... COMPLETION
├─ condition-owned action/runtime retirement facts
├─ most-potent promotion, when applicable ... COMPLETION
└─ ConditionRemoval COMPLETION
```

The parent effect remains the direct parent for each immediate cleanup operation; grandchildren parent to the exact child effect that caused them.

### 7.2 Condition application and replacement

Entity/BaseBlock condition storage remains authoritative. A condition component contributes only its leaf D&D behavior and relation data.

For a new condition:

1. Entity opens the condition application declaration under the caller's exact cause.
2. Entity performs immunity and any saving throw as prerequisites inside that still-open application.
3. The save's roll is a child of SavingThrow execution; the completed save result determines whether the enclosing application cancels or continues.
4. BaseBlock applies the selected policy and controls indexes.
5. Condition-owned subconditions, spatial activation, and perception consequences are children of the application effect.
6. The application completes only after all mandatory children close and the authoritative indexes agree with installed mechanics.

For `REPLACE_EXISTING`, the incoming application is the semantic cause of retiring the incumbent. The incumbent removal tree is a child of the incoming application effect and closes before incoming completion. The owner must never expose a completed incoming condition beside a still-active incumbent.

The exact replacement commit rule is:

1. Accept the incoming declaration/execution/effect without changing authoritative indexes.
2. Install the incoming condition's own mechanics provisionally through its one custom application hook.
3. If provisional installation fails, discard only those provisional artifacts; the incumbent and indexes remain untouched, and an unexpected exception fails the generation.
4. Retire the incumbent through the mandatory owner path as a child of the incoming effect.
5. Replace the authoritative indexes exactly once.
6. Publish any mandatory incoming children and complete the incoming application.

There is no observable completed state in which both conditions are authoritative. A fatal failure after mandatory incumbent retirement does not fabricate rollback or success; it fails the generation and requires reset.

For most-potent conditions, BaseBlock remains the lease authority. Admission, suspension, dormant leases, manifested removal, and promotion are separate explicit outcomes under the same family owner. Promotion is never a parentless fallback root.

For a stronger incoming lease, its mechanics are installed provisionally before the incumbent is suspended. Failure discards the candidate and leaves the incumbent authoritative. After the candidate is proven installable, BaseBlock suspends the incumbent, swaps indexes/lease manifestation once, publishes the exact child facts, and completes. Promotion after manifested removal applies the previously admitted next lease as a mandatory child; failure is an invariant-breaking generation failure, not a fallback root or silent empty family.

Before coding, one characterization table must state for every repeated-application family:

- what can veto before commit;
- which mechanics are provisional;
- how provisional mechanics are discarded;
- when indexes change;
- which condition is visible during replacement;
- what a failed custom hook leaves behind.

No implementation cut may proceed while that table has an unclassified family.

### 7.3 Saving throws

An Event phase is never the owner of a consequence. Entity owns the save calculation; the concrete rule/operation owns what the result means.

For condition application and removal, the condition operation is opened first and owns the save as a prerequisite:

```text
outer cause EFFECT
└─ ConditionApplication or ConditionRemoval DECLARATION
   └─ SavingThrow DECLARATION / EXECUTION
      └─ D20 result under SavingThrow EXECUTION
      └─ SavingThrow EFFECT / COMPLETION
   └─ condition operation CANCEL, or EXECUTION / EFFECT / COMPLETION
└─ outer cause COMPLETION
```

This preserves the existing synchronous `Entity.saving_throw()` contract: the save closes before returning. No callback, open save handle, begin/finish pair, or SavingThrow coordinator is introduced.

For a spell or other rule where the save selects among later effects, the concrete action/rule effect owns both ordered children:

```text
Spell/rule EFFECT
├─ SavingThrow ... COMPLETION
└─ selected Damage/Condition/Movement operation ... COMPLETION
```

The rule reads the returned result and invokes the selected component system. The consequence is not a child of a closed SavingThrow and Event never executes it. If an existing concrete per-target rule operation already encloses both, the save nests inside that operation's declaration; no wrapper event is invented solely to improve the diagram.

The current parentage of the d20 result to a save declaration instead of accepted save execution must not survive. Immunity/no-save, failed save, successful save, standalone save, condition application, duration removal, and spell-nested cases each receive an explicit transcript test.

### 7.4 Spatial conditions and memberships

SpatialCondition remains an independently active world-effect component; GridMap remains the authoritative active collection and positional index.

- Existing SpatialCondition methods expose the activation/deactivation system seam; lifecycle logic is not moved into Event methods or distributed among component objects.
- The spatial-condition system writes membership/footprint changes through GridMap's indexed operations at the accepted commit seam.
- `CREATED`, `TRANSFORMED`, and `REMOVED` validate declaration/execution before mutation; after the GridMap commit, their effect/completion use `EventQueue.store_authoritative_phase()`.
- APPEAR/entry membership application is a normal vetoable child of the exact spatial-change effect; immunity/save/cancellation means that target validly receives no membership.
- Exit/removal of an existing membership is a mandatory non-vetoable child lifecycle through the target's BaseBlock condition system.
- Membership child terminals precede the spatial-change terminal.
- The spatial-condition lifecycle terminal follows the spatial-change terminal.
- Movement passes its active step/spatial cause into membership release; `parent_event=None` is not an admissible escape hatch inside an open operation.
- Overlapping zones keep independent membership sources and remove only their own source.

No global spatial resolver, membership manager, or secondary index is added.

### 7.5 Movement, light, and subjective senses

Every committed movement step remains dynamically observable. The system order is:

```text
Movement action EFFECT
└─ StepMovement lifecycle
   ├─ validate exact physical declaration/execution
   ├─ authoritative position/occupancy settlement
   └─ physical SpatialChange DECLARATION / EXECUTION / EFFECT
      ├─ anchored light and footprint changes
      ├─ zone exit/entry operations
      └─ explicit SensoryUpdate facts from SpatialSensesSystem
   └─ physical SpatialChange COMPLETION
└─ StepMovement COMPLETION
...
└─ Movement action COMPLETION
```

After settlement, the physical SpatialChange effect/completion are stored non-vetoably through `store_authoritative_phase()`. The GridMap/light and SpatialSenses systems are invoked directly by the movement/physical system while the stored physical effect is open. An Event subclass never calls them from completion. Light-driven sensory facts parent to the exact light-change effect; motion/occupancy-driven sensory facts parent to the exact physical movement effect. The same rule applies to optical-condition changes, light creation/removal, and life-state perception changes.

Objective physical visibility/light state and observer-relative perception remain distinct outputs of the same committed physical facts. The reducer consumes observer-relative results; it does not recompute engine visibility from presentation state.

### 7.6 Turn, round, life state, and world initialization

- The Encounter scheduler system controls turn/round ordering.
- The turn system queries the acting Entity composition and asks each duration-bearing component store to advance through its existing seam.
- A TurnStart operation invokes an Entity/BaseBlock condition-removal operation; that operation encloses its prerequisite save as described in section 7.3.
- The RoundEnd system invokes each scheduled Tile/item/spatial component system under the accepted RoundEnd effect; each mutates only its authoritative store.
- TurnStart, TurnEnd, and RoundEnd are vetoable before their effects. Encounter must inspect cancellation before notifying nonmechanical controllers, advancing combatant state, incrementing the round, or emitting the next boundary.
- Health stores life state; the Entity-level health-transition system also updates only the derived capability components belonging to that same composition.
- LifeState events never scan a global condition registry.
- Rule-specific source-left-play behavior is represented by an exact active anchor condition/capability on the source composition, installed and linked by that rule. After the committed LifeState effect, the life-state system queries only that Entity's authoritative active-condition indexes for those anchors and mandatorily removes them. Linked ordinary/spatial children then retire through their target BaseBlock condition system or SpatialCondition system. There is no global registry scan, outgoing-effect manager, new source index, or claim that Entity stores the external child.
- The concrete scenario/bootstrap system controls world initialization. It validates authored inputs before the accepted WorldInitialized effect, invokes each authored component's existing system seam, and nests the resulting lifecycle before completion.
- A post-effect world-initialization child failure is a fatal authoring/generation error requiring reset, not a partially successful initialization or a late gameplay veto.

### 7.7 Actions, resources, charges, metamagic, and concentration

Keep the existing component/system authority:

- The concrete action rule system decides validation and accepted cost timing.
- The source ActionEconomy/component capability stores action economy and named resources.
- The exact item component stores charge/destruction state.
- The spell rule system performs cast-local concentration sequencing.
- The caster's BaseBlock condition indexes store the Concentrating condition and its relations.
- MetamagicActive carries its override lease; the accepted spell rule causes its removal through the caster condition system.

Required laws:

- Declaration/validation rejection spends nothing.
- Every affordability check is pure and complete before the first mutation.
- The concrete action constructs and purely validates every exact prerequisite fact before the first prerequisite mutation. This is local data inside the action rule system, not a transaction object, plan schema, or reusable coordinator.
- After pure validation, action economy, named resources, item charge, and pending metamagic consumption are mandatory direct children of the stored accepted Action declaration and occur once before handler-visible Action execution. Their admitted lifecycles are stored non-vetoably with `store_authoritative_phase()` while the actual ActionEconomy/item/condition store performs the mutation.
- Action execution is published only after those prerequisite children close. Execution cancellation, including Counterspell-style reactions, prevents action effect state but does not refund the documented committed prerequisites.
- Item charge consumption is a direct item-owned child, never a global callback.
- Metamagic cleanup cancellation cannot be ignored.
- Concentration acquisition, replacement, linked-effect retirement, and empty-slot cleanup all close before the spell terminal.
- Nested spell actions such as Eyebite remain inside the initiating spell tree.
- Spell-created placement such as Heroes' Feast cannot leave paid resources and an unreported/partial world object.
- The generic no-op concentration hook is removed; SpellAction uses its concrete cast logic directly.

The required action transcript is:

```text
Action DECLARATION (stored and accepted)
├─ ActionCost/resource fact(s), if eventful, under Action DECLARATION
├─ ItemChargeConsumption under Action DECLARATION
├─ pending Metamagic removal under Action DECLARATION
├─ Action EXECUTION
│  └─ execution reaction trees such as Counterspell
├─ Action EFFECT
│  ├─ target damage/condition/movement/object operations
│  └─ concentration acquisition/replacement/closure
└─ Action COMPLETION or the phase-appropriate CANCEL
```

Every prerequisite child closes before Action execution is published. A cancellation at declaration spends nothing. A cancellation at execution preserves the already documented declaration-owned prerequisites. Effect cancellation produces no effect-owned target state. No store-without-dispatch or later-dispatch API is introduced.

Every active `_apply`, `_remove`, cost, charge, metamagic, and concentration override is inventoried before deciding which current hunks survive. Focused green tests are insufficient if the full active spell family lane disagrees.

### 7.8 Combat logs, reduction, and delivery

Reducer work is frozen until the mechanics tree is correct.

Once mechanics are accepted:

1. Before atomic terminal storage, EventQueue may compute only pure structural and typed-log metadata from the terminal candidate plus already stored immutable descendants. It performs no domain lookup or mechanics.
2. A pure terminal-metadata failure prevents that terminal from being stored and marks the generation failed; it is not swallowed.
3. Encounter obtains objective log entries by cursor from the closed journal tree.
4. `next_committed_tree(cursor)` returns one exact closed tree.
5. Reducer deep-captures it once, then returns Known/Unknown views of those same concrete Event types.
6. Subjective typed logs are projected by the trusted reducer from the same captured terminal UUID and lineage.
7. Reducer-side projection failure does not alter the source tree and does not advance the reducer cursor.
8. The reducer cursor advances only after event views, logs, coverage, and diagnostics are all committed.
9. Before Pygame exists, the scripted encounter runner directly drains the existing public `EventReducer.reduce_next_committed_tree()` pull seam and proves slow/late consumption. No pump, subscriber, background service, receipt, or callback replacement is introduced. The later Pygame loop will call the same pull seam.

No live-state repair, pending-log reconciliation, cross-archive search, callback push, or duplicate canonical event DTO is allowed.

## 8. Known current failures that the recovery must close

The following are semantic acceptance cases, not optional test cleanup:

| Family | Required public cases |
|---|---|
| Condition tree | parent/subcondition, linked, reverse-parent `any`/`last`, most-potent removal/promotion, child rejection |
| Saves | application save, standalone removal save, turn-start removal save |
| Active handler | Prone auto-stand without movement loss on rejected removal |
| Replacement | Mirror Image recast without double condition, spent resource, or open root |
| Spell-created world state | Heroes' Feast placement with complete causal publication |
| Nested action | Eyebite first strike inside original tree |
| Perception | See Invisibility produces condition-caused sensory result |
| Spatial | Spirit Guardians enter/exit/movement/overlap; exact-source cleanup |
| APPEAR semantics | Grease, Insect Plague, Incendiary Cloud, plus authored no-APPEAR zones |
| Source departure | Leadership owns and retires its exact aura without a registry scan |
| Turn/round | cancellation and advancement agree |
| Action resources | Counterspell, item charge, metamagic, concentration timing |
| Delivery | two roots, slow consumer, consumer starts late, cancellation tree, reset generation, replay, repeated empty drain |

The life-state test that treats every descendant removal as a direct child of LifeState is rejected. Tests asserting implementation call sequences instead of domain state and event transcript are also rejected.

## 9. Recovery decision: rollback/reimplement versus repair-forward

No destructive operation is authorized by this document. The shared checkout is dirty and mixes Phase 6, event-knowledge work, cleanup cuts, tests, and documentation. Hashes prove bytes; they do not prove design and they cannot reconstruct an uncommitted checkpoint.

### 9.1 Evidence preservation before either strategy

Before any rollback or repair:

1. Preserve the current tracked and untracked bytes in a lossless immutable evidence artifact outside the shared checkout. A binary tracked diff plus an untracked-file archive, or an isolated snapshot commit/ref, must round-trip into a temporary directory with a byte-for-byte manifest check. A plain `git diff` is insufficient.
2. Record the last committed baseline (`513dd970e73f0d7a24678a98ee7ef32886a75032`).
3. Separate the semantic changes into four inventories:
   - accepted Tile/world-item Phase 6 work;
   - event-knowledge/reducer work;
   - rejected native-resolution cleanup;
   - later unledgered repairs/drift.
4. Classify every changed production hunk as `KEEP`, `REVERT`, `REBUILD`, or `UNDECIDED`, with its owner and public proof.
5. Do the same for tests; a test that blesses the rejected model is `REVERT`, not evidence for keeping code.

### 9.2 Candidate A — clean baseline strategy

Cut 0 identifies committed Phase 6 as Candidate A's immutable starting ref and classifies which slices would later be reapplied. It does not reapply them before strategy approval. If selected, implementation cuts materialize the candidate and reapply only independently justified slices:

- pure detached EventKnowledge masking, if it passes review on that baseline;
- cursor-based closed-tree pull, once mechanics trees close correctly;
- owner-correct action cost/item/metamagic/concentration timing;
- owner-correct turn/round changes;
- no `resolve_sub_events`, global scan, dependency exemption, or strict caller freeze.

This is the preferred strategy if an exact trusted pre-strict checkpoint cannot be reproduced. It is slower but has the smallest uncertainty.

### 9.3 Candidate B — surgical repair-forward strategy

Cut 0 identifies the lossless current snapshot as Candidate B's immutable starting ref and classifies every removal/rebuild hunk. It does not change those bytes before strategy approval. If selected, implementation cuts remove/rebuild every rejected surface:

- delete Event `resolve_sub_events` orchestration and its imports;
- delete global source-left-play scan and architecture exemptions;
- restore owner-driven condition and spatial ordering;
- repair every listed caller and active spell path;
- remove tests that encode flattened ancestry;
- prove a real reducer consumer;
- pass the complete public acceptance matrix.

Repair-forward is eligible only if its reviewed semantic diff is smaller and clearer than Candidate A and it closes every known regression. “We already spent time on it” is not a criterion.

### 9.4 Decision rule

Choose one strategy after both immutable starting points and their complete semantic hunk inventories can be inspected without changing the shared checkout. No speculative implementation prototype is required or authorized for this choice.

The selected recovery boundary must have:

- no event-to-domain orchestration;
- no unexplained changed production hunk;
- no known public regression;
- no open event root after a supported cancellation;
- no incomplete reducer accounting;
- the smaller owner-reviewed semantic diff;
- explicit user approval.

If exact intermediate bytes cannot be reproduced, do not approximate them from ledger hashes. Fall back to Candidate A.

## 10. Implementation cuts after the user selects a recovery boundary

Each cut is separately reviewed before the next. There is no Luna dispatch, automation, or implementation authority in this draft.

### Cut 0 — semantic inventory and boundary selection

Documentation and read-only proof only:

- exact owner/caller/override/test inventory;
- exact classification of every current hunk;
- immutable Candidate A/B starting artifacts and semantic hunk comparisons outside the shared checkout; no production/test repair in either candidate;
- public characterization runs;
- user chooses the recovery boundary.

Exit: one selected, reproducible baseline; no ambiguous carried hunk.

### Cut 1 — restore condition and save correctness

- establish the single `store_authoritative_phase()` kernel primitive and remove effect/completion misuse of `publish_preflighted` in the cut's touched paths;
- ordinary BaseBlock owner path;
- one synchronous removal lifecycle with child-first terminal order;
- Entity immunity/application/removal saves;
- replace-existing and most-potent policy;
- linked/reverse-parent relationships;
- removal override normalization;
- cancellation non-mutation.

Exit: all condition/save/replacement cases green using public operations; no strict kernel dependency needed to make them work.

### Cut 2 — restore independent spatial, movement, light, and senses

- SpatialCondition/GridMap ownership;
- non-vetoable committed spatial facts across all phases;
- exact membership parentage and overlap cleanup;
- per-step movement updates;
- direct GridMap/light/SpatialSensesSystem calls from the physical owner;
- no event completion mechanics.

Exit: spatial, movement, optics/light, and perception cases green with exact ancestry.

### Cut 3 — restore actions, spells, turn/round, and life state

- action/cost/item/metamagic/concentration timing;
- known spell regressions;
- turn/round cancellation and ownership;
- rule-local source-left-play behavior;
- world initialization;
- no global resolver.

Exit: full active action/spell/encounter lane green; every direct consequence closes before its owner.

### Cut 4 — structural EventQueue enforcement

Only after Cuts 1–3 callers are correct:

- remove completion orchestration;
- retain/store immutable phase versions;
- enforce one open root and closed-parent rules;
- enforce terminal-last structurally;
- preserve non-vetoable committed publication and childless inert facts;
- prove a fresh root succeeds after every supported cancellation.

Strict admission is a certification gate, not a mechanism used to discover ownership by crashing gameplay.

Exit: broad gameplay lanes remain green with strict admission active; no caller exemption list.

### Cut 5 — reducer, typed logs, and in-process delivery

- closed-tree pull;
- detached capture;
- same-concrete-event Known/Unknown masking;
- typed subjective log linkage;
- async/slow/late consumer proofs;
- reset/replay behavior;
- removal or formal retirement of stale callback consumers.

Exit: objective and subjective delivery account for every source slot exactly once without live reads or callbacks.

### Cut 6 — final recovery certification

- complete public gameplay lane;
- event-relevant collection blockers classified and approved;
- dependency and anti-slop review after mechanics pass;
- correctness, ownership, causality, reducer, and presentation reviews on the exact candidate;
- hashes and manifest only after semantic freeze.

Hashes are evidence of an already reviewed candidate, never a substitute for reading the implementation.

## 11. Validation contract

Read and follow `HOW_TO_TEST.MD` before editing tests.

Validation is staged; later cuts replay the earlier corpus through additional rails.

Cuts 1–3 prove:

1. authoritative domain state;
2. resource/charge/index ownership and exact-once mutation;
3. exact journal phases and direct parent UUIDs;
4. child terminals before owner terminal;
5. queue accepts a fresh unrelated root after every supported cancellation;
6. repeating the operation/reset does not leak prior-generation state.

Cut 4 replays the complete Cuts 1–3 corpus and additionally proves:

7. strict admission accepts the exact tree and rejects closed-parent/second-root violations;
8. closed-tree pull returns the exact journal slice.

Cut 5 replays the same complete corpus and additionally proves:

9. reducer accounts for every source slot and reaches the source stop;
10. the scripted encounter's direct pull consumer receives every deliverable exactly once;
11. repeated empty drain, late/slow drain, replay, and reset do not leak or duplicate prior-generation state.

Cut 6 runs all eleven rails together on the final candidate.

Cancellation is proved independently at declaration, execution, and effect boundaries:

- no pre-boundary mutation;
- only explicitly documented declaration-owned prerequisites survive execution cancellation;
- no later children after cancellation;
- one cancellation terminal is last;
- no dangling condition, placement, membership, resource, or open root.

Supported cancellation must close its tree, mutate only what its documented commit boundary permits, and admit a fresh root. An unexpected exception is different: no fabricated terminal is stored, the generation becomes undeliverable, and reset must create a clean generation before any further supported operation. Tests must not demand fresh-root continuation from a fatally failed generation.

Required duration cases include ordinary expiry on Entity, equipped item, inventory item, Tile, placed object, and independent SpatialCondition. Required failure cases include application-hook failure, removal-hook failure, mandatory-child failure, committed physical/spatial/object publication failure, terminal-metadata failure, and reducer projection failure. Each asserts authoritative state, journal boundary, delivery/cursor behavior, and reset behavior appropriate to whether the failure occurred before or after commit.

Architecture tests run last. They may reject forbidden dependencies but cannot prove mechanics.

The current broad collectible event/gameplay lane reported by independent review contains 837 nodes. That is a starting floor, not a frozen allowlist. It must explicitly include the full spell-family and remaining-zone files. Every blocked event-relevant file is inventoried individually with its owner; restoration or an explicit user-approved waiver requires named equivalent public coverage. Category-level waivers are forbidden.

## 12. Review gates

Before implementation, this exact plan requires:

1. ownership review against current and historical authoritative APIs;
2. causality review of exact parent/terminal tables;
3. rollback-versus-repair review against public regressions;
4. anti-slop review rejecting extra lifecycle surfaces and callback-like indirection;
5. user acceptance.

Any reviewer proposal that reintroduces `resolve_sub_events`, a generic begin/finish lifecycle protocol, global discovery, or callback orchestration is rejected even if the remainder of that review is useful.

After implementation begins, any semantic repair invalidates affected reviews and tests. It does not require repeated ceremonial hashing during active work; exact hashes are frozen only at accepted cut boundaries and final certification.

## 13. Decisions that must be explicit before Cut 1

The recovery inventory must answer these from existing supported behavior and user approval; the implementer may not guess:

1. Which concrete handlers currently veto/react to condition removal, and where must each move under the fixed root-veto/mandatory-child model?
2. Which TurnStart/TurnEnd/RoundEnd handlers assume scheduler advancement despite cancellation and therefore require migration to the fixed cancellation-stops-advancement model?
3. For each replace-existing and most-potent family, what is the exact provisional/commit/rollback behavior?
4. Which current EventKnowledge/reducer slices are retained at the existing direct pull seam, and which callback-era public contracts are explicitly migrated or retired?
5. Which exact current action/cost/concentration changes match the fixed declaration-parent prerequisite model and are behaviorally green enough to reapply?

Until those answers and the recovery boundary are accepted, the only authorized work is read-only study and revision of this document.
