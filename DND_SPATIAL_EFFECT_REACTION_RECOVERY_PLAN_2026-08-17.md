# Spatial Effect Reaction Recovery Plan

Status: planning revision approved by both independent reviewers; implementation
remains unauthorized until explicitly requested.

Date: 2026-08-17

This is a planning document only. It authorizes no implementation by itself.

## 1. Objective

Recover the existing environmental-reaction capability without restoring the
deprecated generic content system and without creating another state/event
contract.

The recovered path must let an already-installed `SpatialEffect` react to the
existing `SpatialEffectInteractionEvent`, select the exact authored transition
row bound to that effect, and publish the resulting existing
`SpatialEffectChangeEvent` facts.

Examples already represented by authored rules include oil igniting into fire,
water freezing into ice, water electrifying, ice vaporizing into steam, fire
being doused, Web burning, and clouds dispersing.

## 2. Non-negotiable decisions

1. `SpatialEffectInteractionEvent` is the interaction command and reaction
   context. No copied `SpatialEffectInteractionContext` survives.
2. `SpatialEffectChangeEvent` is the authoritative result/state fact. No result
   DTO, projection event, or reaction receipt is inserted above it.
3. The event stream remains the only replay/history boundary.
4. No installed/mutable runtime content registry, content gateway, runtime
   installer, or startup bootstrap is restored. The direct materializer's
   private, import-time built-in declaration dictionary remains a permitted
   static authored lookup and is never replaced or mutated during gameplay.
5. Every effect instance is bound directly to its immutable authored
   transition tuple when it is materialized.
6. The event handler owns event dispatch only. A stateless spatial function
   owns transition selection and execution mechanics. Authored content owns the
   actual transition rows and replacement recipes.
7. The one-process/one-game runtime remains the target.
8. All newly authored models are Pydantic or existing enums. No dataclass,
   custom serializer, `TYPE_CHECKING`, late import, `getattr`, compatibility
   facade, optional dormant gateway, or reflection is introduced.
9. `ContentRef` and the current spatial-effect definition location are not
   redesigned in this recovery. That belongs to the later content migration.
10. The Tile/world-item master plan's Phase 3C committed-event foundation is
    the prerequisite. This plan's Phase 2 prepared controller-mutation
    primitive then becomes the prerequisite for the master's Phase 3D
    Entity-anchor migration and Phase 3F BaseItem world-object-anchor
    migration. The rest of either migration is not a circular prerequisite.

## 3. Scope

Included:

- the six existing interaction operations;
- the three existing transition actions;
- all 14 active authored transition rows;
- direct binding of authored rows during built-in effect materialization;
- event-indexed multi-cell dispatch;
- immediate remove, replace, secondary creation, and delayed retirement;
- exact parent/child event causality;
- interaction-handler footprint reindexing;
- recovery and porting of valuable spatial-effect reaction tests;
- deletion of the dead gateway/context path and deprecated executor; and
- correction of postcommit `SpatialEffectChangeEvent` publication.

Excluded:

- new fire, material, chemistry, weather, or damage reaction rules;
- redesign of actions, conditions, spells, effect controllers, or content
  identities;
- moving all spatial-effect definitions out of `dnd/core/content` before the
  later content hard cut;
- general content registries, external packs, server/SDK/database/frontend
  integration;
- map elevation, walls, cliffs, object placement, and entity position except
  where the separately approved master plan changes the facts consumed by an
  existing spatial anchor; and
- a generic transaction framework.

## 4. Current event-system verdict

### 4.1 Machinery that is already proper and must be preserved

`dnd/core/events/world_events.py::SpatialEffectInteractionEvent` already
carries the complete interaction input:

```python
operation: SpatialEffectInteractionOperation
positions: tuple[tuple[int, int], ...]
intensity: SpatialEffectInteractionIntensity
duration_rounds: int | None
damage_type: DamageType | None
source_object_uuid: UUID | None
source_content_ref: ContentRef | None
```

Its validator requires a nonempty, unique, sorted footprint. It is a
`SpatiallyIndexedEvent`, so the EventQueue can dispatch it through the spatial
handler index without asking content what occupies each cell.

`EventQueue._get_handlers_for_spatial_event` deduplicates handler UUIDs across
all dispatch positions. Therefore one effect spanning several affected cells
receives one event exactly once, not once per cell.

Each installed `SpatialEffect` already owns one spatial handler indexed at:

```text
EventType.SPATIAL_EFFECT_INTERACTION / EventPhase.EFFECT
```

`synchronize_footprint` already moves that handler's indexed cells with the
effect footprint.

`dnd/core/events/world_events.py::SpatialEffectChangeEvent` already carries
the exact child state fact:

```python
operation: SpatialEffectChangeOperation
spatial_effect_uuid: UUID
spatial_effect_content_ref: ContentRef
spatial_effect_name: str
layer: SpatialEffectLayer
anchor_position: tuple[int, int]
affected_positions: tuple[tuple[int, int], ...]
previous_positions: tuple[tuple[int, int], ...]
```

Its `CREATED`, `FOOTPRINT_CHANGED`, `REVEALED`, `REMOVED`, and `TRANSFORMED`
operations are sufficient for the recovered reactions. No new event class is
required.

The parent interaction reaches EFFECT before reaction children are created.
The child change facts use that EFFECT event as their parent, and the parent
interaction COMPLETION follows handler work. This is the correct causal shape.

### 4.2 The hacked/severed seam

The live `dnd/spatial/effect_base.py` handler does not use the event directly.
It copies its fields into
`dnd/core/spatial_effect_runtime.py::SpatialEffectInteractionContext` and calls
`apply_spatial_effect_interaction`.

That runtime module owns:

- a Protocol gateway;
- two process-global gateway variables;
- an install function keyed by a content-set digest; and
- a runtime error when no gateway was installed.

No active one-process content path installs it. The only installer remains in
`deprecated/content_system_deprecated/runtime.py`.

The actual selection/execution algorithm remains stranded in
`deprecated/content_system_deprecated/spatial_effect_transitions.py`. It
requires `FrozenContentRegistry`, resolves the live effect through a global
registry, looks up authored definitions indirectly, and materializes
replacement effects through a deprecated registry materializer.

Consequently the live event and spatial-handler system reaches EFFECT and then
fails with:

```text
RuntimeError: Spatial-effect interaction authority is not installed
```

The tests conceal this architectural break by importing deprecated bootstrap,
deprecated materialization, and server projection code.

### 4.3 Existing state-fact defect to correct during recovery

`SpatialEffect.synchronize_footprint` and `retire` mutate the GridMap/effect
state first, then `_publish_change` calls ordinary cancelable
`EventQueue.publish_lifecycle`.

That permits an EFFECT handler to cancel or rewrite a state fact after the
state already committed. Recovery must use the committed lifecycle mechanism
defined by the Tile/world-item master plan:

1. build and prepare the exact `SpatialEffectChangeEvent` lifecycle before
   mutation;
2. mutate effect/controller/GridMap state;
3. publish the prepared, non-vetoable EXECUTION/EFFECT/COMPLETION lifecycle;
4. isolate observer/projection failures; and
5. never publish a cancelable statement about already-committed state.

`REVEALED` is different: revelation may remain a cancelable command until the
stealth state changes, followed by a distinct committed change fact. It may not
reuse the current method that turns the same mutable declaration into a
post-mutation completion.

## 5. Dependency graph and file ownership

Arrows point from importer to imported dependency. Reverse arrows list the
expected consumers.

```text
dnd/types/spatial_effects.py
  [-> enum only]
  [<- core events, core definitions, spatial runtime, authored content]
  interaction/change/anchor/layer/occupancy/transition enums

dnd/core/events/world_events.py
  [-> events_registry, dnd/types, deferred ContentRef]
  [<- EventQueue dispatch, spatial effects, actions/items/spells, reducers]
  SpatialEffectInteractionEvent
  SpatialEffectChangeEvent

dnd/core/events/events_registry.py
  [-> core event/projection machinery and Pydantic]
  [<- world events, base conditions, controller_mutations, all publishers]
  prepared committed/postcommit lifecycle receipts
  one bounded publish-children hook between parent EFFECT and COMPLETION
  stateful child producers before COMPLETION; pure projection afterward
  one stable logless-root child-log delivery path
  no late-child repair or completed-parent mutation

dnd/core/content/spatial_effect_definitions.py
  [-> Pydantic, content recipe, dnd/types]
  [<- authored spatial_effect_recipes, spatial transition executor]
  SpatialEffectDefinition
  SpatialEffectTransitionDefinition
  TEMPORARILY RETAINED UNTIL CONTENT MIGRATION

dnd/spatial/effect_base.py
  [-> BaseBlock/BaseCondition, core events, GridMap, dnd/types,
      controller_mutations]
  [<- concrete effects, content materializer, spells/items]
  effect/controller lifetime
  footprint and handler installation
  direct bound interaction callback
  committed SpatialEffectChangeEvent publication

dnd/spatial/controller_mutations.py               NEW LOWER LEAF
  [-> Pydantic, core BaseCondition/condition events, events_registry receipts,
      dnd/types; never Entity, BaseItem, effect_base, or a concrete controller]
  [<- effect_base, environmental_effects, effect_controllers,
      effect_memberships, anchor_mutations]
  frozen PreparedSpatialControllerMutation base receipt
  frozen PreparedConditionLifecycle receipt
  pure condition preflight and guarded postcommit lifecycle publication helpers

dnd/spatial/environmental_effects.py
dnd/spatial/effect_controllers.py
dnd/spatial/effect_memberships.py
  [-> effect_base, controller_mutations, core/types dependencies]
  [<- authored materialization and runtime spatial owners]
  concrete Pydantic receipt subclasses and pure prepare/reversible commit/rollback
  no shared transaction primitive is defined here

dnd/spatial/effect_transitions.py                  NEW
  [-> effect_base, controller_mutations, core event objects,
      current cold transition definition, dnd/types]
  [<- dnd/content/spatial_effect_materialization.py]
  strongest-admitted-row selection
  intersected-cell calculation
  remove/replace/delay execution
  no registry and no authored declaration import

dnd/content/spatial_effect_recipes.py
  [-> current definitions, recipes, concrete spatial effects]
  [<- direct materializer]
  exact authored transition tuples and replacement recipes

dnd/content/spatial_effect_materialization.py
  [-> authored recipes, direct construction, effect_base,
      effect_transitions]
  [<- spells/items/scenarios]
  resolves one declaration directly
  validates/materializes effect
  binds exact transition tuple and direct replacement builder
```

Forbidden edges:

```text
dnd.core                         -X-> dnd.spatial
dnd.core                         -X-> dnd.content
dnd.spatial                      -X-> dnd.content
dnd.spatial                      -X-> deprecated content
dnd.spatial                      -X-> server/frontend/SDK
dnd.core.events                  -X-> transition executor/materializer
dnd.content.spatial_effect_*     -X-> global content registry/gateway
controller_mutations.py          -X-> Entity/BaseItem/effect_base/concrete controller
```

The temporary `dnd/spatial/effect_transitions.py ->
dnd/core/content/spatial_effect_definitions.py` edge is downward into an
existing Pydantic definition module. It does not authorize core to import
spatial. The later content migration may relocate this cold definition, but
this recovery does not combine those cuts.

## 6. Exact preserved reaction ledger

Intensity order remains `MINOR < MODERATE < STRONG`. For a matching operation,
the highest minimum intensity admitted by the event wins. A missing match is a
truthful no-op and produces no child state event.

| Existing effect | Operation | Minimum | Action | Replacement/delay |
|---|---|---|---|---|
| Fire Surface | `DOUSE` | `MINOR` | `REMOVE_AFFECTED` | none |
| Ice Surface | `VAPORIZE` | `MINOR` | `REMOVE_AFFECTED_AND_CREATE_SECONDARY` | Steam Cloud |
| Electrified Water | `FREEZE` | `MINOR` | `REPLACE_AFFECTED` | Ice Surface |
| Electrified Water | `VAPORIZE` | `MINOR` | `REMOVE_AFFECTED_AND_CREATE_SECONDARY` | Steam Cloud |
| Wet Surface | `FREEZE` | `MINOR` | `REPLACE_AFFECTED` | Ice Surface |
| Wet Surface | `ELECTRIFY` | `MINOR` | `REPLACE_AFFECTED` | Electrified Water |
| Wet Surface | `VAPORIZE` | `MINOR` | `REMOVE_AFFECTED_AND_CREATE_SECONDARY` | Steam Cloud |
| Burning Web Fire | `DOUSE` | `MINOR` | `REMOVE_AFFECTED` | none |
| Oil Surface | `IGNITE` | `MINOR` | `REPLACE_AFFECTED` | Fire Surface |
| Web Surface | `IGNITE` | `MINOR` | `REPLACE_AFFECTED` | Burning Web Fire |
| Fog Cloud | `DISPERSE` | `MODERATE` | `REMOVE_AFFECTED` | none |
| Cloudkill Cloud | `DISPERSE` | `STRONG` | `REMOVE_AFFECTED` | none |
| Stinking Cloud | `DISPERSE` | `MODERATE` | `REMOVE_AFFECTED` | retire after 4 rounds |
| Stinking Cloud | `DISPERSE` | `STRONG` | `REMOVE_AFFECTED` | retire after 1 round |

All six existing operations remain even where production currently has only a
test producer. Current production producers include torch/flame and oil-barrel
`IGNITE` interactions and spell wind `DISPERSE` interactions. Tests preserve
`DOUSE`, `FREEZE`, `ELECTRIFY`, and `VAPORIZE` until their direct action/content
producers are rebuilt.

The three actions retain their present distinction:

- `REMOVE_AFFECTED`: delete only intersecting cells, retiring the effect only
  when no cells remain;
- `REPLACE_AFFECTED`: remove the intersecting original cells and place the
  replacement effect on exactly those cells; and
- `REMOVE_AFFECTED_AND_CREATE_SECONDARY`: the same spatial transformation,
  with the replacement semantically belonging to another layer/material.

No rule is inferred from names, damage types, colors, item presentation, or
frontend assets.

## 7. Direct per-effect binding

`materialize_spatial_effect` already resolves one exact built-in declaration
through its private import-time `_DECLARATIONS_BY_IDENTITY` dictionary, not an
installed runtime registry. Retain that direct hash lookup and extend this
point, not startup:

1. verify the recipe and resolve the exact declaration;
2. validate and construct the concrete `SpatialEffect` as today;
3. take the declaration's frozen `definition.transitions` tuple;
4. bind one interaction processor to the effect, capturing only that tuple
   and the direct built-in replacement materializer;
5. install the ordinary controller;
6. let `SpatialEffect._install_interaction_handler` index that bound processor
   across the committed footprint; and
7. fail installation before `CREATED` if a transition-capable effect has no
   bound processor or a replacement recipe cannot resolve.

An effect with an empty transition tuple needs no interaction handler. This
keeps the spatial handler index small and prevents a dormant runtime hook.

Add one narrow `SpatialEffect.discard_unpublished_runtime()` cleanup method for
provisional replacement failure. It is valid only while
`_created_event_published` is false. It removes a provisional controller and
handler, clears any staged footprint, removes the effect from
`BaseBlock._registry` and `SpatialEffect._effect_registry`, and publishes no
change fact. Calling it for a published effect is an error. This is runtime
cleanup, not a compatibility facade or serialized receipt.

Construction itself is guarded: once a concrete effect has registered during
`model_post_init`, every subsequent type/content/anchor/definition validation
and processor-binding step runs under `try/except`. Any exception before the
materializer returns calls `discard_unpublished_runtime()` so a failed direct
materialization cannot leak a BaseBlock/effect registry entry.

The processor signature uses the existing objects directly:

```python
Callable[[SpatialEffect, SpatialEffectInteractionEvent], None]
```

It is a Python callable held in a Pydantic private attribute, not serialized
game data and not a new API/event schema. There is no Protocol class, global
installer, content-set digest, or second interaction context.

## 8. Runtime algorithm

For one effect handler and one interaction EFFECT:

1. resolve the live effect captured by the handler UUID;
2. intersect `event.positions` with `effect.affected_positions`;
3. return when the intersection is empty;
4. filter the bound tuple by exact `event.operation` and admitted intensity;
5. return when no row is admitted;
6. select the row with the greatest admitted minimum intensity;
7. for delayed removal, install/replace the existing retirement countdown,
   preserving the shortest admitted delay;
8. for immediate removal with untouched cells, transition the original to the
   remaining footprint;
9. for immediate removal of the complete footprint, retire it with
   `TRANSFORMED` when a replacement follows and `REMOVED` otherwise; and
10. for replacement, materialize and install exactly one replacement effect on
    the intersected cells with the interaction EFFECT as causal parent.

The handler never looks up the parent event by UUID because it already receives
the actual registered `SpatialEffectInteractionEvent`. This removes another
registry round trip and prevents copied context from drifting from stored event
truth.

## 9. Replacement atomicity

The deprecated executor retires/shrinks the original before it knows whether
replacement construction and controller installation will succeed. That is
not acceptable to recover unchanged.

Use the existing overlap mechanics inside one **spatial-effect-specific
prepared controller mutation**, not a general transaction framework and not
ordinary `BaseCondition.apply`/`cleanup_own_state` during the shared commit.

The shared primitive has one exact dependency-safe owner:
`dnd/spatial/controller_mutations.py`. It imports only Pydantic, the core
condition/event values and prepared EventQueue receipts, and `dnd/types`.
It must not import `Entity`, `BaseItem`, `effect_base`, any concrete controller,
authored content, or a runtime registry. It defines:

- frozen, `extra="forbid"` Pydantic
  `PreparedSpatialControllerMutation`, the lower common receipt containing
  owner/controller UUIDs, before/after footprint values, ordered owned-state
  UUIDs, exact prepared condition lifecycles, exact prepared effect-change
  lifecycles, and collision-checked publication order;
- frozen `PreparedConditionLifecycle`, containing the pristine deep-detached
  declaration/execution proposals, their one accepted cancellation result or
  unchanged result, the terminal detached condition snapshots, and the
  preallocated guarded EFFECT/COMPLETION receipt; and
- pure condition-preflight plus guarded postcommit publication helpers.

The base receipt contains cold values only. Concrete controllers extend it
with Pydantic receipt subclasses in `environmental_effects.py`,
`effect_controllers.py`, or `effect_memberships.py` for their exact
terrain/light/modifier/handler/membership state. Those concrete modules own
pure preparation and reversible silent commit/rollback methods. The lower
module never calls upward into them. `SpatialEffect` coordinates those typed
methods and lower helpers. Entity and BaseItem orchestration therefore call
the typed `SpatialEffect.prepare_anchor_transition`/commit/rollback/publish
boundary (BaseItem through `anchor_mutations.py`); they do not import a
concrete controller or invent another receipt. This is the sole shared
primitive in both plans and cannot cycle through live `effect_controllers.py`,
which currently imports Entity.

### 9.1 Condition events must contain detached facts

The current `ConditionApplicationEvent.condition` and
`ConditionRemovalEvent.condition` fields hold the live mutable
`BaseCondition`. That aliases runtime controller state into historical events:
later mutation changes old event payloads, and an event handler can mutate the
controller through the event. This must be cut before prepared controller
publication is safe.

Retain the two existing condition event families and their existing
`condition` field, but change that field to a frozen, `extra="forbid"`
Pydantic `ConditionEventState` declared beside those events in
`dnd/core/base_conditions.py`. It is the event payload itself, not a DTO above
the event. It contains only detached serialized facts required by current
logging/replay/condition consumers: condition UUID, semantic name and
description, direct behavior/content kind, category, tags, source/target UUIDs,
duration kind and remaining rounds/expiry state, immutable effect origin,
typed `ConditionAgencyDenial`, derived `magical_origin`, perceivability flag,
the resulting applied boolean, and the already-resolved application log text.
`magical_origin` is validated to equal membership of `ConditionTag.MAGICAL` in
the frozen tags. The event retains its own disposition, resulting AC/max HP,
names, expired flag, lineage, and causal identities. Callable duration context,
modifier/handler UUIDs, registry links, private ownership, and the live
condition object never enter the snapshot.

Every declaration/execution/application/removal version is prepared from an
independent deep-frozen snapshot of the planned state. After commit, condition
EFFECT and COMPLETION use the prepared terminal snapshot (`applied=True` for a
successful application, `False` for removal). Combat-log generation and
`get_effect_origin` read these event facts and never call a live condition
method. The ordinary non-spatial condition path migrates to the same event
schema in this cut, so there is not a second live-reference compatibility path.

Port every active condition-event consumer in the same schema cut:

- Hidden's full-agency-loss reveal handler and Leadership's source-agency
  retirement read frozen `condition.agency_denial`;
- Globe of Invulnerability reads frozen `magical_origin` plus
  `effect_origin`;
- game-summary condition aggregation uses frozen `condition.behavior_id`
  directly instead of `BaseCondition.get_semantic_key()`; and
- combat logs, origin lookup, JSON/wire assertions, and reducers read only
  snapshot/event fields.

No consumer resolves the live condition UUID merely to recover event facts.

### 9.2 Phase-specific condition guards and publication

Precommit condition DECLARATION/EXECUTION keeps only its ordinary legal
cancellation semantics under a strengthened mutation/publication fence. The
live Globe of Invulnerability declaration blocker in
`dnd/spells/abjuration.py` is proven pure and changed to
`validation_only=True`; no other matching handler may enter transactional
preflight until it is explicitly audited and marked pure. `EventQueue.preflight`
passes every such handler a deep detached proposal and retains a second
pristine deep copy. It rejects emitted events, changes to either copy through
an aliased nested value, and a mutate-then-return-`None` attempt.

ConditionApplicationEvent and ConditionRemovalEvent define a phase-specific
default-deny guard for DECLARATION and EXECUTION. The only accepted results
are:

- the exact unchanged event value; or
- the canonical same-family `CANCEL` transition from the input phase, with
  only `status_message` supplied by the validator.

Concrete class, event type, UUID, lineage, parent, source/target, frozen
condition state, behavior identity, disposition/expiry/result values,
registration mode, children, observer evidence, projection evidence, and all
other queue-owned facts are reconstructed from the pristine truthful input.
A rewritten or forged value is a protocol failure, never an accepted
preflight result. The accepted unregistered DECLARATION and EXECUTION are
later indexed without redispatch.

Once the prepared spatial-controller mutation commits, its condition EFFECT
is postcommit and default-deny:

- concrete event class, event type/phase, UUIDs, parent/lineage, source/target,
  frozen `ConditionEventState`, behavior identity, disposition/expired flag,
  resulting stats, and every other fact must exactly match the prepared value;
- the only handler-authored field is `status_message`;
- children and all observer/projection evidence are copied only from
  EventQueue-owned state and are never accepted from handler output; and
- cancellation, class replacement, or any protected-field rewrite is captured
  as a protocol failure while the last truthful EFFECT remains authoritative.

Add one bounded prepared-condition publisher/coordinator used only by the
spatial controller transaction (and by the master plan's attached-effect use
of the same primitive). It indexes the already accepted declaration/execution
without redispatch and uses the EventQueue prepared publisher's one bounded
`publish_children(effect)` hook: dispatch the prepared postcommit EFFECT
exactly once, publish every preprepared authoritative state child, then run
ordinary result-dependent gameplay reactions over the stable pre-enumerated
target list while that EFFECT lineage remains open. Saving throws, damage
rolls, and their conditional ordinary child lifecycles are generated at this
point rather than fabricated during pure preparation. The hook is invoked
synchronously between EFFECT and COMPLETION; it continues remaining targets
after captured errors and COMPLETION is guaranteed in `finally`. The outer
coordinator never aborts the predetermined sequence on one postcommit failure:
it finishes every remaining condition application/removal, spatial-effect
change lifecycle, and APPEAR consequence, then surfaces the accumulated
failure. This does not weaken ordinary cancelable condition paths and does not
permit a child to be indexed after its causal parent COMPLETION.

The narrow transaction covers every state the current condition lifecycle can
touch:

- controller application/removal declaration, execution, effect, and
  completion events;
- `active_conditions` and condition registries;
- numerical modifiers and source-owned handles;
- ordinary and spatial handlers;
- terrain cost modifiers and light sources;
- controller/effect footprints and GridMap layer indexes;
- interaction/anchor handler UUIDs;
- the controller-owned `_membership_source_uuids` ledger, every referenced
  membership source/manifestation condition tree, and its source-owned
  modifiers/leases, including stale/off-footprint sources;
- stable original-departure target order plus replacement APPEAR target order;
- ordered APPEAR target/admission state, including first-per-turn bookkeeping;
- retirement-countdown ownership; and
- original and replacement effect registries.

Preparation:

1. validate the selected row and replacement recipe;
2. materialize the provisional replacement and guard every post-construction
   validation/binding failure with unpublished cleanup;
3. create its default controller while the original remains active;
4. use pure spatial-controller preparation methods to resolve exact positions,
   handler specifications, terrain/light/modifier changes, and every original
   controller shrink/removal without registering or mutating them;
5. enumerate the controller's authoritative `_membership_source_uuids` ledger
   in stable UUID order and resolve each source's target plus manifestation
   tree. On full retirement, prepare removal of every owned tree even when its
   target is already off-footprint, undeployed, or unavailable. On partial
   shrink, retain only a source whose resolved target is still valid and
   inside the resulting footprint; prepare every other owned tree for complete
   removal. Current removed-cell occupants are enumerated separately only to
   discover/reconcile missing ownership and to build replacement APPEAR
   targets; they never replace the controller ledger. An unexplained active
   membership absent from the ledger is an invariant failure before mutation;
6. preflight every cancelable controller/membership condition
   application/removal
   DECLARATION and EXECUTION handler with EventQueue's mutation/publication
   fence;
7. prepare the detached precommit and predicted terminal `ConditionEventState`
   values for every controller/membership application/removal;
8. enumerate APPEAR target UUIDs in stable order and capture trigger-admission
   bookkeeping so one target failure cannot omit later targets;
9. preallocate and collision-check all authoritative controller/membership
   condition lifecycles, original `TRANSFORMED`/`REMOVED`, replacement
   `CREATED`, and every deterministic state-fact UUID before world mutation.
   Freeze APPEAR target order/admission, but do not precompute random saves,
   damage, conditional results, or their ordinary child event UUIDs; and
10. reject unrelated exclusive occupants. A different authored material is
   admitted only for the exact `replacement_target_uuid` and intersected cells.

Commit:

1. capture exact Pydantic rollback values/owned UUID sets for every state above;
2. install replacement controller state, handlers, modifiers, terrain/light,
   and footprint **without** calling the publishing `BaseCondition.apply`;
3. shrink or remove the original controller state, handlers, modifiers,
   terrain/light, membership sources/manifestations, conditions, and footprint
   **without** calling cancelable condition removal;
4. install replacement interaction/anchor handlers but do not publish
   `CREATED` or run APPEAR;
5. if any mutation raises, restore every captured owner/index/value, discard
   the provisional replacement/controller, and leave the event cursor and
   parent children unchanged; and
6. after commit succeeds, no handler can veto or roll back the accepted state.

Publication uses the complete predetermined order. Every child is published
after its causal parent's EFFECT and before that parent's COMPLETION so
EventQueue freezes complete `children_lineages`, combat-log subentries, and
subjective evidence:

1. original-controller removal condition lifecycle when the original fully
   retires;
2. original `TRANSFORMED` or `REMOVED` EXECUTION and EFFECT;
3. stable-order original-departure membership-source/manifestation removal
   lifecycles, all parented to the original change EFFECT;
4. original change COMPLETION, which now freezes those children;
5. replacement-controller application condition lifecycle, if a replacement
   exists;
6. replacement `CREATED` EXECUTION and EFFECT;
7. stable-order APPEAR membership/gameplay consequences, parented to the
   replacement `CREATED` EFFECT; and
8. replacement `CREATED` COMPLETION, which freezes those children.

Every prepared controller lifecycle uses its frozen condition snapshot. A
raising/canceling/rewriting controller EFFECT is recorded but cannot truncate
this list: remaining condition lifecycles, effect changes, replacement
`CREATED`, and each already-enumerated APPEAR target are finalized in order.
Only then does the coordinator raise the aggregate postcommit failure.

The already-preflighted condition DECLARATION/EXECUTION values are indexed
without redispatch. Their EFFECT is a guarded postcommit reaction and their
COMPLETION is derived from the last truthful EFFECT, using the master plan's
postcommit publisher. Spatial-controller condition events therefore retain
their event family and lineage without exposing committed state to a late
veto. Partial shrink, which retains the original controller condition, emits
no false condition-removal lifecycle.

Audit every concrete `SpatialEffectController.transition_footprint`,
`relocate_anchor`, `apply_effect_exit_trigger`, `apply_effect_entry_trigger`,
`_apply`, `_remove`, `_release_owned_runtime_state`, and appearance
implementation. Their preparation must perform all rejectable validation;
their accepted commit methods must be reversible until publication and
non-vetoable afterward.

The replacement exception is not a general overlap escape hatch. It requires
the exact original UUID supplied by the already-selected transition and cannot
displace a third effect.

No provisional object may emit `CREATED`, install a spatial interaction
handler, remain in `BaseBlock._registry`/`SpatialEffect._effect_registry`, or
leave a GridMap/controller index when preparation fails.

APPEAR is a postcommit gameplay reaction, not decoration. After replacement
`CREATED` EFFECT is indexed, the bounded child hook runs every stable
pre-enumerated APPEAR target before `CREATED` COMPLETION is indexed. Ice saving
throws and conditional Prone, Electrified Water's inherited Wet membership
plus rolled lightning damage, and Steam Cloud's inherited
`WetSurfaceMembership` for every current occupant are preserved as ordinary
result-dependent child lifecycles; their outcomes are deliberately not guessed
during pure preparation. If one APPEAR target raises, the replacement and its
committed facts remain, already-published child facts remain truthful, later
prepared targets still run, `CREATED` COMPLETION is guaranteed, and only then
does the aggregate failure propagate from the parent interaction EFFECT. No
APPEAR failure rolls the transformation back.

For one interaction affecting several effects, each spatial handler is one
causal child transaction. Successful earlier effect transformations remain
truthful children if a later handler encounters an unexpected programmer
error. The ordinary EventQueue currently aborts that parent lifecycle at
EFFECT, so this plan does **not** claim a parent COMPLETION or a global
all-effects rollback in that exceptional case. It does require every earlier
committed child fact to remain truthful and indexed. Redesigning generic
handler-failure completion belongs to the later EventQueue cleanup, not this
recovery.

### 9.3 Delayed-retirement countdown transactions

`SpatialEffect` overrides `advance_duration(condition_name)` for the exact
condition UUID held in `_retirement_countdown_uuid`. It does not call inherited
`condition.progress()` for that countdown:

- when more than one round remains, capture the old positive integer and commit
  the validated decrement directly; no retirement event is due;
- when exactly one round remains, leave it unchanged during preparation and
  invoke the complete expiry transaction below; the transition from one to
  removed belongs to that commit/rollback receipt; and
- for any other condition, delegate to `BaseBlock.advance_duration` unchanged.

Thus Encounter may keep its polymorphic `block.advance_duration(name)` call,
while the terminal countdown tick reaches preparation before any duration
mutation. A rejected/failed terminal tick retains the original value `1` and
zero cursor/lineage change.

`schedule_retirement` cannot remove a longer countdown and then discover that
the shorter application fails. It uses the same narrow prepared-condition
primitive:

- no current countdown: preflight/prepare one application, commit its exact
  active-condition/index/owner state, then publish its lifecycle;
- an equal or shorter existing countdown: truthful no-op;
- a longer existing countdown: preflight and preallocate the old removal and
  new application together, capture both condition/index states and
  `_retirement_countdown_uuid`, commit the swap without ordinary publishing
  condition APIs, then publish old removal through COMPLETION followed by new
  application through COMPLETION, both parented to the interaction EFFECT.

Cancellation, schema failure, UUID collision, or mutation failure before
publication leaves the original countdown and event cursor unchanged. After
commit, a postcommit handler failure cannot suppress either completion; the
coordinator finishes both and then surfaces the failure.

Expiry is also one transaction, not `cleanup_own_state` followed by a late
best-effort `retire`. Before mutation, prepare and collision-check the countdown
removal lifecycle, every remaining controller/membership-condition removal
lifecycle, the effect `REMOVED` lifecycle,
registry/handler/terrain/light/footprint cleanup, and exact rollback state.
Commit all removals and cleanup silently. On mutation failure, restore every
owner and leave the cursor unchanged. After commit:

1. index the countdown condition-removal DECLARATION, EXECUTION, and guarded
   EFFECT, leaving its prepared lineage open;
2. publish remaining controller-removal lifecycles as children of that
   countdown EFFECT;
3. publish the effect `REMOVED` EXECUTION and EFFECT as another child of the
   countdown EFFECT;
4. publish every controller-ledger membership departure as a child of the
   effect-`REMOVED` EFFECT, then publish the effect-`REMOVED` COMPLETION; and
5. only then publish the countdown condition-removal COMPLETION, which freezes
   the complete controller/effect child lineages and forwards their logs once.

The coordinator finishes all groups despite captured postcommit
raise/cancel/rewrite failures and surfaces them afterward. It passes the
actual open countdown EFFECT and returned COMPLETION directly; no one-use
private event cache, registry lookup, fabricated parent, late child, or
bool-only cleanup return is introduced. Because the internal countdown has no
own useful combat log, use the master EventQueue's single
`_deliver_projected_combat_log` path for a logless root: recursively select the
nearest completed descendant logs in stable `children_lineages` order and
deliver each once on a detached root-completion candidate. Zero logged
children delivers nothing; the ordinary expiry case delivers the one
effect-`REMOVED` aggregate once; multiple logged children deliver once each in
stable order without duplicating their subentries. A nested logless countdown
waits for its eventual top-level root to perform the same selection. No
synthetic log, serialized forwarding field, or second callback registry is
introduced.

## 10. Event and replay contract

The exact sequence for immediate replacement is:

```text
SpatialEffectInteractionEvent DECLARATION
  -> EXECUTION
  -> EFFECT
       -> original controller removal condition lifecycle (full retirement only)
       -> original SpatialEffectChangeEvent TRANSFORMED EXECUTION/EFFECT
            -> stable original membership-departure condition lifecycles
          -> original SpatialEffectChangeEvent COMPLETION
       -> replacement controller condition lifecycle
       -> replacement SpatialEffectChangeEvent CREATED EXECUTION/EFFECT
            -> replacement APPEAR gameplay consequences
          -> replacement SpatialEffectChangeEvent COMPLETION
  -> COMPLETION
```

Immediate pure removal emits `REMOVED` when the original disappears and
`TRANSFORMED` when only its footprint shrinks. Delayed removal emits no false
immediate change event; the retirement countdown later publishes the actual
`REMOVED` lifecycle between the countdown condition-removal EFFECT and
COMPLETION.

Section 9.3's expiry coordinator returns and uses the actual removal
COMPLETION. `BaseCondition.cleanup_own_state` remains the ordinary condition
path and does not cache events for a later caller.

Requirements:

- interaction DECLARATION/EXECUTION remain cancelable before reaction;
- the interaction event itself is never rewritten into an outcome record;
- state-change children use the master plan's prepared committed lifecycle;
- child `previous_positions` and `affected_positions` exactly bracket the
  mutation;
- stored child EFFECT/COMPLETION payloads are non-vetoable;
- parent/child UUID and lineage indexes are complete;
- countdown expiry removal EFFECT directly parents the
  `SpatialEffectChangeEvent(REMOVED)` lifecycle, and its COMPLETION occurs only
  after that child settles;
- original `TRANSFORMED`/`REMOVED` EFFECT directly parents every
  controller-ledger membership-source/manifestation departure in stable order,
  and its COMPLETION occurs afterward;
- replacement `CREATED` EFFECT directly parents APPEAR gameplay consequences,
  and `CREATED` COMPLETION occurs only after those children settle;
- combat log and subjective reducers consume these events, not runtime
  transition definitions;
- one effect receives one interaction even if several event cells overlap it;
- unsupported operation or insufficient intensity produces no child fact;
- partial overlap changes only intersected cells; and
- replay requires no content registry or transition executor to reproduce the
  recorded state change.

## 11. Exact deletion ledger

Delete in the same recovery cut, with no compatibility exports:

- `dnd/core/spatial_effect_runtime.py`;
- `SpatialEffectInteractionContext`;
- `SpatialEffectInteractionGateway`;
- `install_spatial_effect_interaction_gateway`;
- `apply_spatial_effect_interaction`;
- both process-global gateway variables and the content-set digest path;
- imports of that runtime from `dnd/spatial/effect_base.py`;
- `deprecated/content_system_deprecated/spatial_effect_transitions.py` after
  its 14-row behavior is covered by the new direct executor;
- the spatial gateway installer in
  `deprecated/content_system_deprecated/runtime.py`;
- deprecated spatial registry materialization used only by that executor; and
- retained tests' imports of `dnd.content_system`, deprecated materializers,
  and `server.world_projection`.

Do not delete the active concrete effects/controllers in
`dnd/spatial/environmental_effects.py`, the active recipes/14 rows in
`dnd/content/spatial_effect_recipes.py`, the direct built-in materializer, the
two event classes, the EventQueue spatial index, or the combat-log reducers.

Before deletion, an `rg` ledger must prove whether any deprecated runtime or
materializer symbol has a second live consumer. Unknown consumers stop the cut;
they do not justify a facade.

## 12. Production caller ledger

| Module | Current use | Recovery |
|---|---|---|
| `dnd/spatial/effect_base.py` | copies event to gateway context | bind direct callable and pass the event itself |
| `dnd/content/spatial_effect_materialization.py` | static built-in declaration dict constructs exact effect but does not bind reactions; postconstruction validation can leak registered owner | retain static hash lookup, bind transition tuple/direct replacement materializer, and clean every failed constructed effect |
| `dnd/content/spatial_effect_recipes.py` | owns 14 valid rows | preserve rows byte-for-semantic-byte; no registry wrapper |
| `dnd/spatial/environmental_effects.py` and `effect_controllers.py` | concrete controllers, APPEAR gameplay, terrain/light/handler footprint mechanics | retain; split pure preparation from reversible silent commit and postcommit APPEAR |
| `dnd/spatial/effect_memberships.py` | source/manifestation trees are cleaned by publishing condition APIs and partial shrink misses departure cleanup | use `_membership_source_uuids` as authority, prepare every invalid/stale/off-footprint owned tree, silently commit, then publish removals between original effect-change EFFECT and COMPLETION |
| `dnd/core/base_conditions.py`/`base_block.py` | events embed live mutable conditions; ordinary controller application/removal publishes during mutation; expiry is bool-shaped | replace the event field with detached frozen `ConditionEventState`, add exact pre/postcommit guards and the bounded prepared spatial-controller publisher |
| `dnd/spatial/effect_base.py::advance_duration` | inherits mutation-first countdown progression | override exact countdown UUID path so terminal tick prepares before decrement/removal and joins expiry receipt |
| `dnd/conditions.py` Hidden handler | reads live event condition agency denial | consume frozen typed `ConditionEventState.agency_denial` |
| `dnd/monsters/traits.py` Leadership | reads live agency denial and owns anchor relocation memberships | consume frozen agency fact; master/shared anchor receipt preserves lease reconciliation |
| `dnd/spells/abjuration.py` Globe/Antimagic | Globe reads live magical origin and its pure declaration blocker is not marked validation-only; Antimagic relocation mutates protection/suppression state | consume frozen origin facts, mark the proven-pure Globe blocker `validation_only=True`, and capture exact Antimagic state in the shared anchor receipt |
| `dnd/analytics/game_summary.py` | calls live condition semantic method | aggregate by frozen `ConditionEventState.behavior_id` |
| `dnd/items/torches.py` | publishes `IGNITE` | preserve event producer and event lineage |
| `dnd/items/environment_content.py::OilBarrel` | publishes `IGNITE` on destruction | preserve; coordinate item destruction ordering with master plan |
| `dnd/spells/evocation.py` | publishes `DISPERSE` wind | preserve event producer |
| `dnd/spells/conjuration.py::SleetStormGroundEffect` | observes `IGNITE` to douse exposed item flames inside Sleet Storm | preserve this independent event consumer; Web transformation remains in the authored transition row/general effect handler |
| GridMap spatial-effect index | footprint/layer occupancy | preserve and use during direct transaction |
| EventQueue spatial handler index | dispatches interactions over cells | preserve deduplication and handler reindex |
| combat log/subjective reducers | serialize both event families | preserve exact events; no transition-definition access |

## 13. Implementation phases

### Phase 0 — Freeze behavior and inventory

1. pin the exact 14-row ledger and hashes/JSON of each current definition;
2. inventory every interaction producer and event consumer;
3. inventory every direct/deprecated materialization and gateway symbol;
4. pin event JSON/lineage for no-op, partial removal, replacement, secondary
   creation, controller application/removal, APPEAR, and delayed retirement;
5. inventory every concrete controller `_apply`, `_remove`,
   `transition_footprint`, `relocate_anchor`, entry/exit reactions,
   membership trees, owned-state cleanup, terrain/light/modifier/handler
   mutation, and APPEAR implementation;
6. pin Ice, Electrified Water, and Steam Cloud APPEAR consequences—including
   Steam's inherited Wet membership—and the actual countdown removal event
   chain;
7. pin Hidden/Leadership agency handling, Globe magical-origin admission, and
   game-summary condition aggregation against current event JSON;
8. record the current clean direct-materialization behavior and the current
   missing-gateway failure; and
9. make no production edit.

Gate: every row, producer, executor, materializer, handler, controller, and test
has an explicit disposition.

### Phase 1 — Committed state-fact prerequisite

Land or verify the Tile/world-item master plan's EventQueue prepared committed
lifecycle and migrate `SpatialEffect._publish_change` to it. Split revelation
command validation from the committed `REVEALED` fact.

Gate: create/footprint/reveal/remove/transform state facts cannot be canceled or
rewritten after state mutation, and observer failure cannot suppress their
completion.

### Phase 2 — Direct transition executor

1. add `dnd/spatial/effect_transitions.py`;
2. port only intensity selection, intersection, remove/replace/secondary, and
   delayed-retirement mechanics from the deprecated executor;
3. accept the actual interaction event rather than copied context;
4. add dependency-safe `dnd/spatial/controller_mutations.py` with the frozen
   common Pydantic receipts and pure lifecycle helpers, then split concrete
   spatial-controller installation/removal into pure preflight, reversible
   silent commit, and predetermined publication through typed SpatialEffect
   methods;
5. migrate both existing condition event families from live `BaseCondition`
   references to frozen `ConditionEventState`, including ordinary callers,
   typed agency/magical-origin facts, Hidden, Leadership, Globe, game summary,
   combat log, JSON, effect origin, deep-detached preflight, Globe's
   `validation_only=True` marker, and phase-specific guards;
6. cover conditions, modifiers, ordinary/spatial handlers, terrain, light,
   footprints, registries, countdown state, and every child lifecycle in the
   narrow transaction;
7. prepare/commit every membership-source/manifestation tree selected from the
   controller-owned ledger and publish stable departures between the original
   effect-change EFFECT and COMPLETION;
8. add the exact replacement-target overlap path and rollback cleanup;
9. add guarded unpublished-effect cleanup, including materializer failures;
10. prepare controller/membership-condition plus original/replacement change lifecycles
   before shared mutation;
11. run every predetermined APPEAR target after committed `CREATED` EFFECT but
    before `CREATED` COMPLETION, including Steam Wet membership, and preserve
    all-facts failure semantics;
12. override `SpatialEffect.advance_duration` for the exact countdown and
    implement atomic creation/shortening/expiry with the actual removal EFFECT
    as parent and all children settled before its COMPLETION;
13. audit/harden concrete controller commit/cleanup/relocation methods; and
14. add focused unit tests without installing a global runtime.

Gate: all 14 rows execute through direct arguments in a fresh process; the only
module-level content selector is the private import-time built-in declaration
dictionary, and no installed/mutable runtime registry selects content.

### Phase 3 — Per-effect materialization binding

1. bind each definition's frozen transition tuple during direct materialization;
2. bind the direct replacement builder;
3. install no handler for empty transition tuples;
4. install/reindex/remove exactly one handler for transition-capable effects;
5. reject incomplete replacement bindings before `CREATED`;
6. clean every constructed effect when later validation/binding fails; and
7. delete the gateway/context imports from live spatial code.

Gate: ordinary direct materialization plus controller installation is enough to
run interactions; no startup call is required.

### Phase 4 — Deprecated cut and caller/test port

1. port production producers and valuable tests to active imports;
2. remove server projection assertions from the engine test and assert event
   state/combat-log output directly;
3. delete the exact runtime/deprecated files and symbols in Section 11;
4. rerun the removal ledger;
5. run focused, spatial, item, spell, architecture, and collect-only gates; and
6. report unrelated pre-existing collection blockers separately.

Gate: zero live/deprecated compatibility import is required to create an
effect, interact with it, replay its changes, or run the retained tests.

## 14. Test plan

Follow `HOW_TO_TEST.MD`: test observable event/state outcomes, not mock call
counts or private helper choreography.

Create `tests/engine/test_spatial_effect_reactions.py` covering:

- all 14 authored rows in a table-driven test;
- all six operations and three actions;
- exact intensity threshold and strongest-admitted selection;
- unsupported operation and insufficient intensity are no-ops;
- partial intersection changes only intersected cells;
- multi-cell dispatch calls one effect handler once;
- handler positions follow footprint shrink/move and disappear at retirement;
- Fire/Burning Web douse;
- Oil/Web ignite replacement;
- Wet/Electrified Water freeze/electrify/vaporize;
- Ice vaporize to Steam;
- Fog/Cloudkill immediate dispersal thresholds;
- Stinking Cloud shortest delayed retirement and eventual truthful removal;
- replacement preparation failure leaves original effect, controller,
  condition indexes/modifiers, terrain/light state, ordinary/spatial handlers,
  footprint, registries, event cursor, and child lineage unchanged;
- direct materialization validation/binding failure leaks no BaseBlock/effect;
- unrelated exclusive occupant cannot be displaced by replacement;
- successful replacement emits original `TRANSFORMED` then replacement
  `CREATED` with the predetermined controller-condition lifecycle order, all
  under interaction EFFECT before interaction COMPLETION;
- stored application/removal events contain frozen detached
  `ConditionEventState`; mutating or unregistering the live controller later
  cannot change prior event JSON, logs, origin, or equality;
- Hidden and Leadership react to frozen agency denial, Globe uses frozen
  magical/effect origin, and game-summary aggregation uses frozen behavior ID
  with no live condition lookup;
- condition DECLARATION and EXECUTION preflight rejects source/target/parent
  rewrites, child/evidence forgery, nested snapshot mutation, and
  mutate-then-return-`None`; unchanged values and the one canonical legal
  cancellation remain valid, and an active Globe blocker cancels without
  publishing or mutating anything;
- raising, canceling, class-replacing, condition-snapshot rewriting, causal-field
  rewriting, child forging, and observer-evidence forging are tested separately
  for condition application and removal EFFECT; every case retains the truthful
  terminal snapshot and every later predetermined completion, then surfaces the
  captured protocol failure;
- Ice replacement runs its APPEAR saving throw after `CREATED` EFFECT and
  before `CREATED` COMPLETION, Electrified
  Water applies inherited Wet membership plus damage, and every Ice/Water/
  Electrified-Water vaporization to Steam applies one exact Wet membership to
  each occupied replacement cell between Steam `CREATED` EFFECT and
  COMPLETION;
- APPEAR failure retains replacement state and committed facts, then surfaces
  through the parent interaction's existing EFFECT-failure semantics;
- full retirement preflights and commits controller condition removal without a
  late cancelable cleanup path;
- partial and full Wet->Ice/Steam transitions remove every exact Wet membership
  source/manifestation selected by the controller ledger, including stale
  off-footprint and unavailable-target ownership, publish those condition
  trees between original change EFFECT and COMPLETION, and leave only valid
  untouched-cell leases intact;
- countdown shortening either leaves the shorter/equal countdown untouched or
  atomically publishes old removal then new application; rejected/failed swaps
  retain the exact old countdown with zero cursor change;
- countdown expiry mutation failure restores countdown, controller, effect,
  positive remaining value (including the terminal value `1`),
  terrain/light/handlers/footprint/registries and cursor; the
  `SpatialEffect.advance_duration` override never decrements before preflight;
  success publishes controller-removal and effect-`REMOVED` children after the
  countdown EFFECT and before countdown COMPLETION, completing every fact
  despite postcommit failures;
- committed child facts resist cancellation, mutation, and observer failure;
- original departures, replacement APPEAR damage/membership, and countdown
  expiry have complete UUID/lineage traversal, serialized order, subjective
  projection, and exactly-once combat-log delivery before each parent
  completion freezes its child evidence;
- logless top-level countdown projection forwards zero, one, and several
  completed descendant logs as zero or stable exactly-once deliveries; nested
  logless parents wait for root delivery and never duplicate subentries;
- combat log/replay reads only the two event families; and
- a fresh Python process needs no installer/bootstrap/global gateway.

Preserve/port valuable coverage from:

- `tests/engine/test_spatial_effects.py`;
- the spatial-effect cases in `tests/engine/test_spell_families.py`;
- spatial item interactions in
  `tests/engine/test_items_inventory_equipment.py`;
- the event wire behavior currently in the manual event contract, if it is
  still a core capability; and
- spatial controller/condition tests that cover footprint transition cleanup.

Explicitly preserve/extract these existing cases when their containing files
still have deprecated/server collection blockers:

- `test_gust_wind_exposure_uses_the_complete_child_lifecycle`;
- `test_eb_15_044_stinking_cloud_wind_dispersal_uses_srd_rounds`;
- `test_eb_15_043_sleet_storm_douses_exposed_flames`;
- `test_eb_15_042_web_fire_exposure_burns_one_cube_for_one_round`;
- `test_eb_13_011_torch_lifecycle_manages_attached_light_sources`; and
- the canonical `SpatialEffectInteractionEvent` JSON assertion from the manual
  event-wire contract.

Architecture tests must assert:

- `dnd/core/spatial_effect_runtime.py` and all four gateway/context symbols are
  absent;
- no active module imports deprecated content or server code;
- `dnd.spatial` does not import `dnd.content`;
- core events do not import the executor/materializer;
- no installed/mutable runtime transition selector is process-global; the
  private import-time built-in declaration dictionary is permitted and tested
  as immutable during gameplay;
- `dnd/spatial/controller_mutations.py` imports only Pydantic, core
  condition/event modules, and `dnd/types`; it imports no Entity, BaseItem,
  effect_base, concrete controller, content, or deprecated/runtime registry;
- Entity and BaseItem reach controller mutation only through typed
  SpatialEffect/anchor boundaries, and no concrete controller imports them
  back through the lower primitive;
- the new modules contain no dataclass, custom serializer, `TYPE_CHECKING`,
  late import, `getattr`, or reflection;
- condition events contain no live `BaseCondition` field and the bounded
  postcommit condition publisher is callable only by the spatial-controller
  transaction/shared Entity-anchor primitive; and
- every declaration containing a replacement row resolves its replacement
  recipe through the direct built-in materializer.

## 15. Completion criteria

Recovery is complete only when:

1. all 14 rows have exact retained behavior;
2. the existing interaction event reaches each overlapping effect exactly once;
3. the actual event is the reaction context;
4. existing `SpatialEffectChangeEvent` values are the only spatial outcome/state
   facts, while existing condition events retain controller lifecycle history;
5. partial, complete, replacement, secondary, and delayed transitions work;
6. replacement validation/commit failure leaves no partial condition,
   modifier, terrain/light, handler, footprint, event, or provisional owner;
7. controller application/removal validation finishes before mutation and its
   accepted spatial transaction is reversible before publication and
   non-vetoable afterward;
8. condition application/removal events carry immutable detached event facts,
   never live runtime conditions, and their postcommit guard completes the
   entire prepared sequence before surfacing failures; agency denial,
   magical/effect origin, behavior identity, logs, and summary consumers are
   preserved from those facts;
9. every controller-ledger membership tree no longer valid for the resulting
   footprint departs between original effect-change EFFECT and COMPLETION,
   without stale leases, while valid untouched memberships remain;
10. replacement APPEAR gameplay runs between committed `CREATED` EFFECT and
   COMPLETION, including Ice,
   Electrified Water, and Steam's inherited Wet membership, and cannot roll
   committed transformation back;
11. countdown creation/shortening/expiry is atomic, terminal countdown
    detection happens before decrement, and delayed retirement is parented to
    the actual countdown removal EFFECT and settles before its COMPLETION;
12. committed effect-state facts cannot be canceled after mutation;
13. parent/child ordering is deterministic and replayable without content;
14. no gateway, context copy, global installer, installed/mutable runtime
   registry, or deprecated runtime is required; the static direct built-in
   declaration dictionary is the only permitted lookup;
15. no new content system, DTO, facade, cycle, late import, reflection,
    dataclass, or custom serializer was introduced;
16. active production producers and Sleet Storm's independent IGNITE consumer
    keep their event semantics;
17. focused and preserved tests pass in a fresh process; and
18. both independent reviewers approve the same frozen document revision.

## 16. External review record

Both reviewers approved the same substantive frozen revision,
`6e972841953a390413280622215da7e54e0d81271056607e022c0647d9abead7`.
The final file checksum differs only because this status/review record was
updated after approval and is reported in the handoff.

| Reviewer | Focus | Status |
|---|---|---|
| Architecture/invariants reviewer | event truth, file ownership, dependency direction, no parallel contract/global authority | **APPROVED** |
| Migration/events/tests reviewer | live callers, 14-row preservation, phase order, causality, rollback, test salvage | **APPROVED** |
