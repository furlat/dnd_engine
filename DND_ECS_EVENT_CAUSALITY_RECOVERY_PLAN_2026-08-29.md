# ECS Event-Causality Recovery Plan

**Status:** QUARANTINED — REJECTED OVERCORRECTION; NOT IMPLEMENTATION AUTHORITY  
**Authority:** documentation and read-only study only  
**No authority for:** implementation, rollback, test migration, Luna dispatch, automation, cleanup, or deletion of prior evidence

> Quarantine note (2026-08-29): this draft imposed an unsupported ID/value-only
> Event payload rule, a blanket migration from established component/system-
> composer methods to free functions, and a speculative replacement layer model.
> Historical inspection disproved those premises: the 2026-07-30 design and the
> accepted Phase 6 baseline both retained typed live component payloads and
> component-owned composition surfaces while maintaining an acyclic import
> graph. Preserve this file as evidence; do not implement it.

## 1. Why this plan exists

The rejected event cleanup treated Event subclasses and domain objects as lifecycle orchestrators. Completion started mechanics, objects called other objects to simulate ownership, causal children were flattened to convenient roots, and import cycles were hidden with function-local imports.

That is incompatible with the engine's actual architecture: an entity/component system adapted to D&D.

The rejected artifacts remain preserved:

- `DND_EVENT_NATIVE_CAUSAL_RESOLUTION_CLEANUP_PLAN_2026-08-28.md`
- pre-quarantine SHA-256: `a739521673ecdfed95c237f28f8c5fbcf5d6e8aede4a5f56a926225b265fdc81`
- quarantined SHA-256: `415963af7e9d90885b8fe17a1c58beabcef42217bd5116399d81cf0a3cabeeb8`
- `DND_EVENT_NATIVE_CAUSAL_RESOLUTION_CLEANUP_IMPLEMENTATION_LEDGER_2026-08-28.md`
- ledger SHA-256: `3910fa979f3586b5a8ad0c0508dfdd4ce2fab1f0bcb00156d691a81ec75d4ab4`
- superseded OOP-centric replacement draft: `DND_EVENT_CAUSAL_OWNERSHIP_RECOVERY_REPLACEMENT_PLAN_2026-08-29.md`

None may be deleted or silently edited into acceptance.

## 2. Non-negotiable engine model

### 2.1 Runtime roles

- **Entity UUID:** runtime identity.
- **Entity composition:** the set of capability components for that identity.
- **Component store:** authoritative state such as Health, ActionEconomy, Senses, Inventory, Equipment, SavingThrows, condition indexes, item charge, GridMap occupancy, or Encounter schedule.
- **Relation component:** explicit identity edges such as condition parent/child, linked condition, granted action, spatial membership source, concentration relation, or placed-object source.
- **D&D system operation:** a narrow function that queries explicit components, applies one rule family, mutates the authoritative stores, and emits typed causal events.
- **Concrete Event subclass:** immutable typed intent/fact/cancellation data. It does not locate components or execute mechanics.
- **EventQueue:** append-only structural journal plus synchronous rule-handler dispatch at explicit pre-commit phases.
- **EventReducer:** observer-relative masking over a detached closed tree of the same concrete event types.
- **Renderer:** consumer of reduced events; never part of commitment.

Entity and component classes are data structures and capability surfaces. They are not autonomous actors exchanging lifecycle messages.

### 2.2 Permitted Python shapes

This recovery does not introduce an ECS framework, `System` base class, service, manager, controller, command bus, transaction object, context manager, or new dispatch layer.

Permitted shapes are:

| Shape | Responsibility |
|---|---|
| Component method | Query or mutate only that component's own state |
| System function | Order explicit component operations and event phases for one named D&D rule family |
| Pure query/projection | Read explicit inputs and return a value without mutation |
| Public command function | Validate external arguments and call one or more named system functions without storing authority |

Every touched callable is classified into one of those shapes during Cut 0. A callable that discovers unrelated state, advances another lifecycle, performs terminal cleanup, or chains cross-object hooks is rejected orchestration and must be removed or rebuilt.

Concrete condition, action, and spatial subclasses may retain authored data. They do not expose virtual lifecycle hooks. Declarative cases are handled by shared data-driven system logic; exceptional mechanics use an exact named system callsite or explicitly registered D&D rule handler. Cut 0 maps every active variation to that callsite. Callable behavior fields, reflection, type switches, and a second behavior registry are forbidden.

L1 data objects never delegate upward to a system. Current cross-component methods such as `Entity.add_condition`, `BaseBlock.remove_condition*`, `BaseAction.apply`, and `SpatialCondition.activate/deactivate` are classified and their active callers migrate to public/system functions. Component-local query/mutation helpers may remain. No L4 facade object is invented merely to preserve method syntax.

### 2.3 System composition

The normal flow is:

```text
public command
  -> one system function receives explicit entity/component identities
  -> it queries authoritative component stores/relations
  -> it publishes a typed operation phase
  -> registered D&D rules synchronously accept, modify, or cancel
  -> it inspects the exact returned event
  -> it mutates the authoritative component store at the declared commit seam
  -> it invokes any mandatory downstream system with the exact causal phase
  -> descendants close
  -> it records its terminal
  -> reducer later pulls the detached closed tree
```

During rule dispatch a handler may emit only a complete reaction tree whose semantics remain valid even if a later handler cancels the triggering phase, such as a reaction attempting to cancel that proposal. The reaction tree closes before the handler returns. A consequence that depends on final acceptance is invoked by the system only after `publish` returns an accepted stored phase.

No Event completion, component hook, passive subscriber, or renderer callback continues this flow.

## 3. Import DAG is an acceptance criterion

### 3.1 Current diagnostic

A read-only AST import scan of the current checkout found one static strongly connected component containing seven production modules:

```text
dnd.blocks.sensory
dnd.core.base_block
dnd.core.base_conditions
dnd.core.base_tiles
dnd.core.events.encounter_events
dnd.core.events.world_events
dnd.core.gridmap
```

It also found nine function-local `dnd.*` imports in `base_conditions.py`, `encounter_events.py`, and `world_events.py` used to reach sensory, condition, or GridMap code after module load.

This is existing architectural debt and evidence that Event/domain orchestration has created circularity. The recovery may not preserve it behind late imports, `TYPE_CHECKING`-only domain imports, `getattr`, `isinstance` routing, `importlib`, registries, or service locators.

Ordinary local attribute access and genuine D&D type predicates are not banned. Using them to hide a dependency edge is banned.

### 3.2 Target dependency direction

The exact files are decided by Cut 0, but every runtime import must follow one global direction:

```text
L0   enums, IDs, immutable value/snapshot types, geometry, dice,
     and small genuine capability Protocols
  ↓
L1C  component records and component-local stores/queries
     (Entity composition, BaseCondition data, BaseBlock indexes, Tile data,
     Senses data, GridMap data, Encounter schedule)
L1E  generic Event/EventQueue kernel and concrete Event schemas
     (L1C and L1E are peers and may import only L0, never one another)
  ↓
L2   D&D system and public-command functions
     (condition, save, spatial, movement, light, senses, action, life-state)
  ↓
L3   scenario/bootstrap/encounter orchestration functions and reducer consumers
  ↓
L4   in-process game loop and renderer
```

L2 never imports an L3/L4 Entity or Encounter facade because no such facade is introduced. It receives explicit L1C component records or genuine L0 capability Protocols. L1C never imports L2 to preserve an object method. Existing public callers migrate to the L2/L3 functions.

Event payloads contain only UUIDs and immutable L0 values/snapshots. They never retain Entity, BaseBlock, BaseCondition, GridMap, Senses, item, or another authoritative component/store instance. Cut 0 inventories every current event field that violates this rule. This removes mutable live object graphs from the supposedly detached journal without adding a parallel event DTO.

Protocols are permitted only when they describe a real stable capability surface, as in the existing creature-transform pattern. They may not be used solely to disguise an otherwise circular dependency.

### 3.3 Required cycle cuts

Cut 0 must validate these prospective cuts before implementation:

1. Event subclasses lose sensory, GridMap, BaseCondition, Entity, spell, and condition-lifecycle mechanics; therefore event schema modules do not import systems.
2. Senses component data and spatial-senses computation no longer occupy one mutually dependent module surface.
3. BaseCondition and BaseBlock data/index code do not call sensory systems or concrete Event-family orchestration.
4. GridMap store/query code does not construct concrete world-event lifecycles; the spatial/movement system imports both.
5. Component modules never import Event modules or higher system modules, including through function-local imports.
6. Action/spatial/condition systems import L1C components and L1E events; neither lower peer imports those systems back.
7. L1C component stores retain only installed handler/relation UUIDs. L1E handler entries retain owner/source UUIDs, never component objects. L2 installation/removal functions update the component IDs and the one synchronous EventQueue handler registry through explicit inputs.

Cut 0 produces an exhaustive active-production module-to-layer manifest and allowed-edge matrix. “Active production” means every production module reachable from the named in-process engine, scenario, encounter, and game entrypoints; every exclusion is named and proven inactive individually. No category allowlist is permitted.

The exact candidate must have zero production import SCCs, zero reversed or unclassified layer edges, and zero unauthorized function-local imports in that exhaustive graph. L2 systems hold no authoritative state, owner registry, or L3/L4 import. An architecture test may enforce this only after mechanics and dependency direction have been reviewed.

## 4. Event algebra

The existing concrete Event subclasses remain the canonical event space. Observer censorship creates masked copies of those same types. No canonical wrapper, duplicate DTO, parallel event hierarchy, or generic `kind/facts` object is introduced.

### 4.1 Two semantic event shapes

1. **Operation event:** represents a D&D operation that rules may modify or cancel before mutation. It uses the typed lifecycle phases required by that family.
2. **Leaf fact event:** records already committed state that can cause no further mechanics. It is one terminal typed fact without handler dispatch.

Anything that can trigger more mechanics is an operation. A fake multi-phase lifecycle is not manufactured for a committed leaf fact.

### 4.2 Phase law

| Phase | Meaning |
|---|---|
| `DECLARATION` | Proposed operation and declaration-time rule boundary |
| `EXECUTION` | Accepted prerequisites and execution-time rule boundary |
| `EFFECT` | Final family-specific authorization immediately before mutation |
| `COMPLETION` | Successful closure after mutation and all consequences |
| `CANCEL` | Rejected closure at the exact rejected boundary |

An operation uses only the phases its existing public semantics require. Cut 0 freezes a per-family phase/commit table before implementation.

### 4.3 Minimal queue semantics

The queue exposes two structural behaviors over one append-only store:

- **publish:** append a proposed typed phase, synchronously evaluate matching D&D rule handlers in deterministic order, append each accepted modification before passing it to the next handler, append the first cancellation once, stop dispatch, and return the exact final stored result;
- **record:** append an already authorized phase, a true leaf fact, or a system-decided cancellation without rule-handler dispatch.

Every handler modification preserves exact concrete class, lineage, active phase, parent/root identity, generation, and registration mode. A handler cancellation is the same concrete lineage at `CANCEL`, carries the exact `canceled_from_phase`, is terminal, and stops later handlers. A handler may not replace one semantic event with another.

A system-decided cancellation is constructed from the latest stored same-lineage phase after existing children close, records exact `canceled_from_phase`, and never dispatches or deletes the proposal. Saving-throw interpretation and system validation use this path.

`record` contains no family switch, component discovery, callback, mutation, or runtime caller allowlist. Ordinary vetoable phases always use `publish`. Cut 0's exact family/phase table identifies every permitted `record` callsite, and architecture review matches a static callsite inventory to that table. No token, transaction wrapper, runtime allowlist, or third queue API is added.

The rejected `preflight()` / `publish_preflighted()` split has no presumed right to survive. Cut 0 classifies it. No phase may be passed through an API that falsely claims a preflight occurred.

`Event.phase_to()` may remain only as same-subclass value construction. `Event.cancel()` may remain only as same-subclass cancel construction. Neither publishes, discovers, mutates, resolves children, or chooses publish versus record.

### 4.4 Append-only causality

1. Every stored version remains in the journal. `CANCEL` is appended; prior declarations/phases are never deleted.
2. Same-lineage phase progression is not a parent/child edge.
3. A child points to the exact stored phase that directly caused it.
4. A terminal is stored only after all descendants are terminal.
5. Completion and cancellation begin no mechanics, cleanup, lookup, notification, reduction, or rendering.
6. Each system inspects the returned phase/child result it invoked.
7. No authoritative mutation occurs before the family's accepted veto boundary.
8. After an accepted effect authorizes a mandatory cascade, descendant retirements cannot be vetoed into a split state.
9. Unexpected exceptions append no fabricated success and delete no evidence. The current generation becomes undeliverable until full authoritative world reconstruction/reset.
10. Objective logs, observer views, replay, and rendering derive from the same closed tree.

Terminal metadata must be a pure projection over the terminal candidate and already stored descendants. It may not consult live domain state or swallow failures.

Rule-handler ownership crosses layers in one explicit way: L1C components store installed handler UUIDs only; L1E EventQueue stores handler entries containing trigger data, an owner/source UUID, and the one synchronous rule callable; L2 installation/removal functions update both. EventHandler never stores an `owner_block` object or calls back into a component. This EventQueue registry is the sole permitted callable rule registry.

## 5. Component/system map

| Rule family | Authoritative data | System function boundary |
|---|---|---|
| Condition lifecycle | target BaseBlock indexes, condition records, explicit relation rows | condition apply/remove/arbitrate functions |
| Entity condition prerequisites | target immunity/save components | entity-condition admission function delegating to condition lifecycle |
| Saving throw | SavingThrowSet, ability/modifier components, dice | saving-throw function; enclosing rule interprets result |
| Spatial effect | SpatialCondition record and GridMap spatial indexes | activate/transform/deactivate functions |
| Membership | source relation plus target condition index | entry/exit membership functions |
| Position/occupancy | entity position plus GridMap occupancy | movement settlement function |
| Light/optics | Tile/material/light-source components plus GridMap caches | light/optics recomputation functions |
| Subjective senses | observer Senses components plus derived sensory state | sensory recomputation/reduction functions |
| Action | action command data plus source/target capabilities | action execution function |
| Resources/items | ActionEconomy, named resources, exact item charge | exact consumption functions |
| Concentration/metamagic | caster conditions, spellcasting state, exact leases | spell function plus condition lifecycle |
| Turn/round | Encounter schedule and duration-bearing components | turn/round functions |
| Life state | Health, same-entity capabilities, explicit source relations | damage/healing/life-state functions |
| Bootstrap | authored scenario plus normal creation/placement systems | bootstrap function |
| Rule-handler installation | component-owned handler UUID rows plus EventQueue trigger entries with owner/source UUID | exact L2 install/remove functions; no component object callback |
| Journal | EventQueue indexes and cursor | EventQueue only |
| Observer knowledge | detached tree and EventKnowledge | EventReducer only |

## 6. Required rule-family shapes

### 6.1 Conditions and saves

Condition records store authored parameters, exact owned artifact IDs, and explicit relation IDs. They do not traverse the world or advance events.

```text
remove_condition(target_store, condition_uuid, cause)
  -> resolve from the target's active index
  -> publish and inspect the root removal phases
  -> after accepted effect, retire same-store and linked descendants
     through the narrow mandatory-dependency function with explicit IDs
  -> remove exact owned modifiers/handlers/actions/relations
  -> update active and lease indexes exactly once
  -> perform required promotion as a direct child operation
  -> record completion after descendants close
```

Cross-component `BaseBlock.remove_condition*()` methods do not remain as upward delegates. Active callers migrate to the L2 condition function; BaseBlock retains only component-local index/query/mutation helpers. Entity does not duplicate generic graph traversal, and concrete conditions do not become alternate removers.

The root removal is vetoable before its effect. After accepted effect, `retire_condition_dependency(target_id, condition_id, cause_effect)` records the descendant declaration/execution/effect without handler dispatch; recursively retires and closes every same-store and linked descendant first; then removes the condition's exact artifacts, relations, and authoritative index row; performs promotion if applicable; and finally records descendant completion. At no supported point is a removed parent exposed beside active owned descendants. It is a private condition-system operation, not a public mode, begin/finish protocol, or third queue API. Any rule that can prevent the cascade acts on the root pre-commit. A post-removal reaction is an explicit child operation invoked by an exact named L2 rule/system callsite, never a completion callback.

Application uses the same authority:

- Entity-specific immunity and saves are queried from composition components.
- the condition system controls indexes for Entity, Tile, item, and placed-object stores;
- declarative component transforms and exact named L2 rule functions install artifacts and return/store their identities without virtual dispatch;
- subconditions, linked conditions, spatial manifestations, and sensory consequences are explicit child system operations;
- completion occurs only when authoritative indexes and artifacts agree.

The current overlap among `_apply`, `_remove`, `_release_owned_runtime_state`, `_finalize_application`, and rollback hooks is not accepted architecture. Cut 0 maps every override to an exact direct L2 callsite or shared declarative transform and inventories its owned artifact identities. BaseCondition/BaseAction virtual lifecycle hooks, callable behavior fields, reflection, type-switch selection, and behavior registries are removed. Generic retirement deletes exact owned artifacts/relations by identity; exceptional mechanics use explicit registered rule handlers or named system calls, not renamed install/uninstall callbacks. Uncommitted artifact discard is a direct condition-system operation over the same identities.

`REPLACE_EXISTING` and most-potent behavior remain explicit condition-system policies, not transaction abstractions. Cut 0 characterizes every active family: vetoes, provisional artifacts, exact inverse, index swap, visible condition, promotion, and failure boundary.

SavingThrow computes a result from entity components. The enclosing condition/spell/hazard/action system owns the meaning:

```text
ConditionApplication DECLARATION
└─ SavingThrow operation
   └─ SavingThrow EXECUTION
      └─ D20 operation/fact as its direct child
   └─ SavingThrow EFFECT / COMPLETION
└─ ConditionApplication CANCEL or accepted later phases
```

The D20 parent is the exact accepted SavingThrow execution phase. SavingThrow completion starts nothing. A selected spell consequence is a sibling under the enclosing spell/rule effect, never a child of the closed SavingThrow. There is no open handle, callback, coordinator, or begin/finish pair.

### 6.2 Spatial, movement, light, and senses

SpatialCondition is an independently active component. GridMap is an indexed spatial store. Neither is a controller object.

- spatial functions validate and commit activation, transformation, and deactivation;
- membership functions use exact source relations and target condition indexes;
- APPEAR/entry application is a normal published/vetoable condition operation parented to the exact spatial-change effect;
- exit/removal of an existing membership after accepted spatial change is a recorded mandatory retirement parented to that exact spatial-change effect;
- overlaps remove only their exact source relation;
- no global resolver, membership manager, or secondary general index is added.

Each committed movement step runs the same explicit system sequence:

```text
Movement EFFECT
└─ StepMovement operation
   └─ accepted PhysicalChange EFFECT
      -> settle position and occupancy once
      ├─ motion/occupancy sensory operations/facts
      ├─ exact spatial membership exit/entry operations
      └─ LightChange operation
         └─ light-driven sensory operations/facts
   └─ PhysicalChange COMPLETION
└─ StepMovement COMPLETION
```

Motion/occupancy sensory consequences parent directly to `PhysicalChange EFFECT`. Light-driven sensory consequences parent directly to the exact `LightChange EFFECT`; they are never flattened under movement merely because movement began the tree. Engine position/elevation stays objective spatial state. Projected pixel height is renderer-only. Objective light/optics and observer-relative perception are distinct component outputs driven by the same physical facts; the reducer does not recompute vision.

### 6.3 Actions, resources, items, spells, and concentration

The action system queries authored action data and source/target components. The action object carries authored rule data only; exact exceptional behavior is a named L2 callsite, never a virtual lifecycle hook or dynamic behavior selection.

- affordability/target validation finishes before the first mutation;
- accepted action costs, named resources, item charges, and pending metamagic consumption commit exactly once as direct children of accepted Action declaration;
- declaration rejection spends nothing;
- documented execution cancellation retains committed declaration prerequisites;
- damage, condition, movement, placement, and concentration are explicit child system operations under Action effect;
- concentration replacement and linked-effect retirement close before spell completion;
- no no-op lifecycle hook, resource transaction object, or generic spell coordinator is added.

### 6.4 Turn, round, life state, and bootstrap

Encounter schedule is component state. Turn/round functions query duration-bearing components and invoke normal systems.

- boundary cancellation prevents scheduler advancement and notification;
- nonmechanical controller notification occurs only after mechanical descendants close and cannot emit mechanics;
- Health is authoritative for life state; same-entity capabilities update through the life-state function;
- once Damage/Healing commits Health, any resulting LifeStateChange is a recorded mandatory operation parented to that exact Damage/Healing effect; its relation-owned cleanup closes beneath LifeStateChange effect before its terminal and cannot be vetoed after Health commitment;
- any feature that can prevent the transition must act on the Damage/Healing operation before Health commitment;
- source-left-play cleanup requires a genuine explicit active relation already attached to source composition;
- Cut 0 must prove such a relation exists for Leadership and similar rules; it may not synthesize an anchor to avoid a registry scan;
- a missing relation is a user-visible model decision, not permission for global discovery;
- bootstrap invokes ordinary creation/placement systems, not a parallel lifecycle framework.

### 6.5 Reducer and delivery

Reducer work remains frozen until mechanics trees are correct.

- one cursor returns one detached closed tree;
- observer censorship masks deep-copied instances of the same Event subclasses;
- logs derive from the captured tree;
- no live-state repair, duplicate DTO, subscriber callback, pump service, or receipt layer;
- cursor advances only after views/logs/coverage/diagnostics all succeed;
- reset means full authoritative world reconstruction and a new journal generation.

The later scripted encounter and Pygame renderer consume this same pull boundary. Renderer pacing is outside this recovery.

## 7. Explicitly forbidden

- `Event.resolve_sub_events` or terminal/completion mechanics.
- Event-to-system/component imports used for runtime lookup or mutation.
- components acting as lifecycle coordinators or calling one another as autonomous actors.
- late imports, `TYPE_CHECKING` domain links, reflective lookup, or type-switch routing used to hide a cycle.
- deletion, rewriting, or flattening of stored event facts.
- global active-world scans through identity registries.
- `_apply`/`_remove`/`_finalize` callback chains.
- manager/service/controller/coordinator/transaction/context-manager/receipt layers.
- generic begin/finish APIs, deferred callbacks, subscriber mechanics, or event-family switches.
- duplicate canonical event/view hierarchies.
- tests whose primary proof is method calls, callback counts, hashes, or convenient ancestry.

## 8. Required public acceptance cases

| Family | Cases |
|---|---|
| Conditions | subcondition, cross-block link, reverse-parent `any`/`last`, replacement, most-potent removal/promotion, root rejection |
| Saves | immunity/no-save, failed save, successful save, standalone save, application, removal, duration/turn-start, spell-nested |
| Reactions | Prone auto-stand and other removal reactions without lost/duplicate mechanics |
| Spells | Mirror Image recast, Heroes' Feast placement, Eyebite nesting, See Invisibility sensory output |
| Spatial | Spirit Guardians entry/exit/movement/overlap, Grease, Insect Plague, Incendiary Cloud, authored no-APPEAR zones, concentration-linked zone teardown, exact source cleanup |
| Source departure | Leadership retires its exact aura through an authoritative relation |
| Movement/perception | every step updates occupancy, memberships, light/FOV, senses, and transcript |
| Turn/round | cancellation and scheduler state agree |
| Resources | Counterspell timing, item charge, metamagic, concentration |
| Delivery | multiple roots, slow/late consumer, cancellation, replay, empty drain, full reset |
| Bootstrap/failure | initialization cancellation, authored placement, and post-commit child failure requiring full reconstruction |
| Dependency | zero exhaustive active-production SCCs, reversed/unclassified edges, and unauthorized local imports |

### 8.1 Accepted Phase 6 is non-regressible

This recovery is downstream of the accepted Tile/world-item Phase 6 contract. Neither Candidate A nor Candidate B may silently reinterpret it.

The protected proof anchor is the accepted 695-node manifest `DND_TILE_WORLD_ITEM_PHASE_6_IMPLEMENTATION_MANIFEST_2026-08-26.json`, manifest SHA-256 `425deda5bb0a204cb1963d24569ebdfe41811591f841d80abd289f5b9ce92f71`, node-set SHA-256 `efa4e7fc84129d246b523d413e7c27e7434047934d87337f8b9d3947ae26c48a`.

Protected semantics include:

- Tile four-channel/four-cost traversal and replay facts;
- renderer-neutral Tile/world-item schemas and placement;
- elevation, boundaries, and traversal connectors;
- authored bootstrap and object placement;
- spatial reveal and source-exact memberships;
- accepted Phase 6 position/occupancy hard cuts.

The exact accepted lane, or named equivalent public coverage approved by the user, runs for both recovery candidates and at every implementation-cut exit. A semantic change to any accepted Phase 6 behavior requires explicit user approval; hunk reclassification is insufficient.

The previously reviewed collectible event/gameplay lane of 837 nodes is the starting broad floor and is recomputed exactly by Cut 0. It must include full spell-family and remaining-zone files. Every event-relevant collection blocker is inventoried individually with a named equivalent proof or explicit user waiver; category waivers are forbidden.

## 9. Cut 0 — evidence and recovery-boundary decision

Cut 0 is read-only/documentation work. It creates no implementation prototype.

1. Preserve the dirty checkout in a lossless immutable evidence artifact outside the shared checkout and prove byte-for-byte reconstruction in a temporary directory.
2. Record committed baseline `513dd970e73f0d7a24678a98ee7ef32886a75032` and accepted Phase 6 artifacts.
3. Classify every changed production/test hunk as accepted Phase 6, event/reducer, rejected cleanup, or later drift.
4. Classify every touched callable by section 2.2.
5. Generate the exhaustive active-production module set from named in-process entrypoints, list every proven-inactive exclusion, and freeze a module-to-layer manifest plus allowed-edge matrix.
6. Generate the exact import graph, SCCs, reversed/unclassified edges, function-local imports, and proposed DAG moves.
7. Inventory every Event payload field that retains a live L1C object and define its immutable L0 ID/value replacement on the same concrete Event type.
8. Classify every Event subclass as operation or leaf fact with exact phases, `publish`/`record` choice, rule handlers, commit seam, component mutations, children, and terminal; freeze the matching static queue-callsite inventory.
9. Inventory every EventHandler installation/removal path, stored component handler ID, owner/source ID, and direct rule callable.
10. Classify every condition/action/spatial override and every relation traversal, mapping each variation to shared data-driven logic or one exact named L2 callsite.
11. Mark every hunk `KEEP`, `REVERT`, `REBUILD`, or `UNDECIDED` with component/system reason and public proof.
12. Recompute the 695-node Phase 6 anchor and 837-node broad floor, then inventory all individual collection blockers.

### Candidate A — accepted baseline plus selective reapplication

Start from the reproducible accepted Phase 6 boundary. Reapply only independently justified component/system and pure reducer slices. Do not reapply Event orchestration, registry scans, callback guards, preflight splits, dependency escapes, strict-caller exemptions, or tests that bless them.

### Candidate B — surgical repair-forward

Start from the lossless current snapshot. Remove/rebuild every rejected surface and prove the remaining component/system semantic diff is smaller and clearer than Candidate A. Time spent is not evidence.

### Selection

The user selects only after both immutable candidates and complete hunk/dependency inventories are readable without changing the checkout. The selected boundary must have:

- the smaller component/system semantic diff;
- a credible zero-cycle target DAG;
- no Event-to-domain mechanics;
- no unexplained production hunk;
- no known public regression/open root;
- complete reducer accounting;
- exact reproducibility.

If an intermediate boundary is not reproducible byte-for-byte, Candidate A wins.

## 10. Implementation cuts after explicit user selection

No cut is authorized by this draft.

Implementation uses causally closed vertical cuts. A migrated family has exactly one active path; no compatibility facade, dual write, or family switch is added. Every cut includes all transitive event-emitting descendant seams reachable from its migrated public roots. A cut cannot close while a tree rooted in a migrated operation contains a legacy lifecycle callsite, even if that descendant is nominally assigned to a later family. The legacy path remains untouched only for roots not yet migrated, and the exact remaining caller inventory shrinks at every cut. The complete accepted Phase 6 lane and accumulated broad gameplay lane remain green at every exit.

### Cut 1 — conditions, saves, and their minimum event/DAG slice

- establish only the final `publish`/`record` and pure typed-transition behavior needed by the condition/save family;
- migrate the full active condition/save family to functional L2 systems and public command functions;
- migrate the final spatial-activation and sensory-update descendant seams reached by condition application/removal, so every migrated condition tree is wholly on the new contract;
- normalize artifact/relation cleanup without virtual lifecycle hooks;
- remove condition/save completion resolution, preflight abuse, callback guards, live Event payload objects, late imports, and reversed edges in the same family;
- normalize direct artifact installation, identity-based cleanup, and uncommitted discard;
- restore indexes, relations, replacement, most-potent, duration, and saves;
- prove root-veto/mandatory cascade without callbacks or scans.

Exit: condition/save public matrix, accepted Phase 6 lane, broad accumulated lane, family layer edges, and queue algebra all green; no migrated condition root reaches a legacy spatial, sensory, or other lifecycle callsite. Untouched roots remain behaviorally unchanged.

### Cut 2 — spatial, movement, light, and senses

- restore functional SpatialCondition/GridMap/membership boundaries;
- preserve per-step occupancy, membership, light/FOV, and subjective updates;
- prove exact overlap/source ancestry;
- remove spatial/sensory Event mechanics and the reviewed seven-module cycle in this vertical cut;
- add no renderer/server work.

### Cut 3 — actions, spells, turn/round, life state, bootstrap

- restore component-based resource/item/metamagic/concentration ordering;
- close known spell regressions;
- restore scheduler cancellation, source relations, and bootstrap.

### Cut 4 — kernel convergence and DAG hard cut

Only after every active family uses the reviewed contract:

- remove the legacy side-effecting phase/completion/preflight/guard surfaces and their last callers;
- remove every remaining Event-to-domain dependency and live component payload;
- close every reversed/unclassified layer edge and unauthorized local import;
- prove the exhaustive production module graph matches the frozen layer manifest;
- retain one append-only store, `publish`, `record`, the synchronous EventQueue rule registry, and the same concrete Event subclasses.

### Cut 5 — strict event structure

After Cuts 2–4 callers are correct, enforce one open root, stored parent, closed-parent prohibition, phase order, and terminal-last. Strictness certifies correct systems; it does not discover them by crashing gameplay.

### Cut 6 — reducer, delivery, and final certification

- detached tree pull and same-type masking;
- typed logs and cursor accounting;
- slow/late/replay/reset proofs;
- complete gameplay, dependency, correctness, anti-OOP, and anti-slop review;
- hashes/manifest after semantic freeze only.

## 11. Validation law

Read `HOW_TO_TEST.MD` before editing tests.

Every supported operation proves:

1. authoritative component state/indexes;
2. exact-once resource/modifier/handler/relation mutation;
3. exact concrete event type, phases, direct parents, and order;
4. descendant terminal before ancestor terminal;
5. no deleted declaration or fabricated terminal;
6. a fresh root after supported cancellation;
7. full reset removes prior-generation state;
8. production dependency graph has no SCC, reversed/unclassified edge, hidden local import, live-component Event payload, stateful L2 system, or L2→L3/L4 import;
9. every `record` callsite matches the frozen family/phase table and every rule handler retains only owner/source IDs;
10. accepted Phase 6 and accumulated broad gameplay lanes remain green.

Cancellation is tested at each admitted phase. Unexpected failure leaves diagnostic journal/state, stops delivery, and requires full reconstruction. Duration coverage includes Entity, equipped item, inventory item, Tile, placed object, and SpatialCondition. Failure coverage includes direct artifact installation/cleanup, mandatory descendant, spatial/object commit, terminal metadata, and reducer projection.

Tests assert public component state and event transcript. Architecture tests run after mechanics and cannot substitute for behavior.

## 12. Review and user gates

Before implementation, these exact bytes require:

1. **anti-OOP/ECS reviewer:** component authority, functional systems, and target import DAG;
2. **causality reviewer:** phase/commit/parent/terminal algebra;
3. **regression reviewer:** recovery candidates and public behavior coverage;
4. **anti-slop reviewer:** redundant seams, wrappers, hooks, reflective escapes, and needless abstractions;
5. user acceptance.

One reviewer may cover more than one gate, but anti-OOP and anti-slop verdicts must be explicit. Any edit invalidates approvals.

Cut 0 must return these decisions to the user before Cut 1:

1. selected reproducible boundary;
2. final target DAG and exact module moves;
3. any missing authoritative relation/index;
4. condition removal/reaction handler disposition;
5. repeated-application semantics by active family;
6. operation-versus-leaf-fact event classification;
7. reducer slices retained or rebuilt.
8. exact Event payload migrations and handler-registration ownership rows;
9. individually classified event-relevant collection blockers.

Until then, only read-only study and plan revision are authorized.
