# World modification event implementation plan

Status: **review-accepted implementation plan — implementation still requires
human authorization**

This plan covers one feature: a typed, causal authoring boundary for changing
an already-running world. It is intended for a future in-process map editor,
live GM edits, and LLM-assisted map construction. It also defines the exact
renderer-neutral fact that the planned pygame-ce bridge will consume when a
Tile, placed world item, or traversal connector is added, changed, or removed.

It does **not** implement pygame, an editor interface, persistence, networking,
undo, multi-edit transactions, or a new spatial system.

## 1. Requested behavior and observable boundary

Given one explicit authoring request against a running `GridMap`, the engine
must produce one honest causal tree:

```text
WorldModifiedEvent declaration / execution / effect
  -> the existing typed Tile, object, or connector mutation
    -> the existing cache/revision changes
    -> the existing light and propagation settlement, where relevant
    -> the existing observer-owned SensoryUpdateEvent deltas
  -> WorldModifiedEvent completion with exact cold before/after values
```

The public observable result is:

1. the ordinary authoritative engine state is changed exactly once;
2. the ordinary detailed events and sensory cascades still occur exactly once;
3. every detailed event actually required by the edit is a child of the
   world-modification lineage; a semantic-only change does not manufacture a
   spatial child;
4. one completed `WorldModifiedEvent` contains enough detached state for an
   external in-process materializer to add, replace, move, or remove the
   affected visual without reading mutable engine objects; and
5. a rejected or canceled edit produces no partial world mutation and no
   successful world-modification completion.

This is the stable feature boundary that tests must exercise. Tests must not
freeze private helper call order.

## 2. Why the world-level event exists

The current runtime already has precise mechanics events:

- `SpatialChangeEvent` for Tile and placed-object changes;
- `TileElevationChangeEvent`;
- `TraversalConnectorChangeEvent`;
- objective light events;
- spatial-effect events; and
- observer-specific `SensoryUpdateEvent` values.

Those facts are correct for rules recomputation, but they are not one complete
authoring record. In particular:

- a surface/name-only Tile replacement may currently publish no Tile event;
- Tile runtime events do not carry the complete semantic `WorldTileState`;
- object spatial events carry exact geometry but not the complete current
  `ItemPresentationState` and direct contained-item presentation;
- connector cold state currently omits its client-facing semantic
  `presentation_key`; and
- there is no terminal value that says one authoring gesture succeeded only
  after its detailed causal children settled.

`WorldModifiedEvent` fills only this live structural-materialization gap. It
does not replace any detailed event and no rules system subscribes to its
completion to recompute state.

## 3. Governing laws

### 3.1 One edit, one existing atomic mechanical mutation

The first version admits exactly one already-atomic domain mutation:

- one Tile slot add/replace/remove;
- one Tile elevation or base-light change;
- one placed `BaseItem` place/move/orient/remove operation; or
- one traversal connector register/replace/enable/disable/remove operation.

For a placed `BaseItem`, the GridMap mutation is followed by one total,
non-vetoable BaseItem-owned synchronization of its redundant floor-location
fields. That mirror assignment is not a second mechanics mutation.

There is no batch command, transaction object, rollback manager, undo stack,
branch, collaboration protocol, or generic command interpreter.

### 3.2 Existing owners remain authoritative

- `GridMap` remains the sole owner of Tile admission, world-object placement,
  connector indexes, spatial revisions, caches, and light settlement.
- `BaseItem` remains the owner of its item presentation and floor-location
  fields.
- `SpatialSensesSystem` remains the only subjective spatial reducer.
- existing concrete item behavior remains responsible for door state, torch
  state, destruction effects, and other gameplay transitions.

The new authoring functions compose those owners. They do not duplicate their
mechanics.

### 3.3 The root groups causality; children do mechanics

`WorldModifiedEvent` is vetoable through its normal declaration, execution,
and effect phases. Once its effect is accepted, the explicit authoring
function passes that effect UUID as `parent_event` to the existing owner
mutation. All light/sensory descendants therefore remain inside the same
lineage. The root completes only after the owner call and its children have
completed.

No handler on `WORLD_MODIFIED` may be required for the feature to work. The
implementation adds no pre-completion callback, passive callback chain,
context manager, or event-queue transaction mode.

An event that reports owner state which has already committed is not a
proposal and cannot honestly be vetoed. The existing
`GridMap._fire_committed_spatial_event` seam already claims that law, but its
execution/effect transitions currently use ordinary registration and can
store a handler-produced cancellation after the state changed. Repair that
seam with one explicit `EventQueue.publish_committed_phase(...)` operation:

- it accepts only an unregistered, uncanceled `EXECUTION` or `EFFECT` version;
- it stores that exact phase once;
- it invokes every matching handler with an unregistered view so handlers may
  publish their ordinary reactions/subevents but cannot repost, transform, or
  cancel the committed fact;
- it does not store or chain any event version returned by a handler and still
  runs later matching handlers; and
- it returns the stored authoritative phase for normal completion.

This is not a new event phase, callback path, transaction, or type-specific
exception. It is the publication law for the existing committed-fact path.
Vetoable proposal paths continue to use ordinary registration unchanged.

### 3.4 Completion is passive, complete, and detachable

The completed root contains frozen/value-safe state models. Applying it to a
renderer materializer must not invoke GridMap, registries, handlers, light
computation, or sensory computation.

Creation and deletion are represented by ordinary absence:

```text
before is None, after is present -> creation
before is present, after is present -> replacement/change/move
before is present, after is None -> removal
```

There is no string operation field, sentinel dictionary, `dict[str, Any]`,
field-mask language, or parallel renderer DTO.

### 3.5 Objective authoring is not subjective revelation

The completed root is an objective world fact. It may populate the in-process
renderer's objective scene store and omniscient debug rail. A player view still
draws cells and objects only from each controlled observer's existing sensory
state/deltas. Adding an object behind an opaque wall must not reveal it merely
because the objective materializer knows it exists.

### 3.6 Structural authoring is not every gameplay transition

Opening a door, lighting a torch, damaging a barrel, applying darkness, moving
an Entity, or activating a spatial condition continues through its current
concrete event path. These transitions do not gain redundant
`WorldModifiedEvent` roots. The pygame bridge will consume those ordinary
events for animation/state changes and use `WorldModifiedEvent` only when the
structural set of admitted Tiles, world-item placements, or connectors is
edited.

## 4. Exact event value contract

Add `EventType.WORLD_MODIFIED` and one concrete `WorldModifiedEvent` in
`dnd/core/events.py`.

The event uses the existing cold state models:

```python
WorldMaterializedState = WorldTileState | WorldObjectState | WorldConnectorState

class WorldModifiedEvent(Event):
    event_type = EventType.WORLD_MODIFIED

    tile_position: tuple[int, int] | None = None
    object_uuid: UUID | None = None
    connector_uuid: UUID | None = None

    before: WorldMaterializedState | None = None
    after: WorldMaterializedState | None = None
```

This is a schema sketch, not authorized code. The final implementation must
preserve these semantics even if annotation syntax changes.

### 4.1 Target validation

Exactly one target address is selected:

- Tile: `tile_position` only;
- object: `object_uuid` only; or
- connector: `connector_uuid` only.

No new target-kind enum is needed: the three address shapes are already a
closed sum. Connector registration preallocates its UUID and passes it through
the existing `connector_uuid` argument, so its address is known before the
root is published. Any present connector state supplies and validates its
authored ID; the root does not duplicate that identity.

### 4.2 Phase validation

- Declaration/execution/effect may contain the exact `before` state and no
  `after` state. A creation legitimately has neither state yet.
- Completion requires at least one of `before` or `after` and requires them to
  differ.
- Cancel may retain `before` for diagnostics but is never a successful
  materialization record.
- Any present state must match the selected target family and address.
- Object before/after values preserve the same item UUID.
- Connector before/after values preserve connector UUID and authored ID.
- Tile replacement preserves the addressed `(x, y)` slot but may replace the
  concrete Tile UUID.

The union must JSON-round-trip back into the exact concrete state member. The
three existing state models have non-overlapping required fields; no custom
serializer is authorized.

### 4.3 Complete connector state repair

`WorldConnectorState` must add the renderer-neutral semantic data already
owned by `TraversalConnector` but currently missing from the cold snapshot:

- `presentation_key`;
- the two support Tile UUIDs.

Endpoint positions/elevations and all existing traversal mechanics remain.
Runtime revision and objective digest are concurrency/integrity derivations,
not pygame materialization inputs, and are not duplicated into the cold
presentation state.

`WorldInitializedEvent` and `WorldModifiedEvent` must use the same corrected
connector projection.

## 5. One high-level leaf module, not a framework

Create one high-level leaf module: `dnd/world_authoring.py`.

It is allowed to import concrete `GridMap`, `Tile`, `BaseItem`, `Inventory`,
event values, and connector values because no lower-level module imports it.
The import direction is one way:

```text
dependency-neutral value types / events
        ^
GridMap, Tile, BaseItem, Inventory, connectors
        ^
dnd.world_authoring
        ^
battlefield builders now reuse its pure projection functions
future game/GM/LLM command boundary
```

`dnd/core/events.py`, `GridMap`, and `BaseItem` must never import
`dnd.world_authoring`. This prevents a cycle and avoids late imports.

The module contains only:

1. three pure cold-state projection functions, one for each world state; and
2. explicit authoring functions that begin a root, call one existing owner
   mutation, and complete or cancel that root.

It must not contain a `WorldManager`, `WorldAuthoringService`, controller,
repository, mutable session, command base class, visitor, dispatch registry,
generic `apply(command)`, or function accepting a mutation callback.

Two small local lifecycle helpers are permitted:

- begin one already-constructed `WorldModifiedEvent` through declaration,
  execution, and effect; and
- complete/cancel that same accepted root.

They receive event values, not executable callbacks, and do not mutate world
state themselves.

## 6. Public authoring operations

The leaf module exposes explicit functions. Names may be adjusted for current
repository style, but the closed operation set and ownership must not change.

Every public function receives an exact `author_uuid` and optional author name
for the root source identity. That UUID is audit/causal identity and need not
be a registered combat Entity. The functions do not expose a speculative
parent parameter; a future concrete GM-command boundary may add composition
when it actually exists.

Return/error semantics are uniform:

- success returns the completed `WorldModifiedEvent`;
- an exact no-op returns `None` and emits nothing;
- invalid input fails before root declaration and emits nothing;
- a veto before commit stores the appropriate CANCEL lineage and raises
  `ValueError`.

### 6.1 Tiles

- `set_world_tile(...)`
- `remove_world_tile(...)`
- `set_world_tile_elevation(...)`
- `set_world_tile_base_light(...)`

`set_world_tile` accepts graphic-agnostic Tile values already supported by
`Tile.create`: semantic `TileSurface`, name, traversal costs, optics,
propagation, base light, height, elevation surface kind, and slope axis. It
does not accept a concrete sprite filename. The existing legacy
`sprite_name` field is not expanded by this feature.

To keep Tile construction after event acceptance, `GridMap.set_tile` is
extended to forward the existing semantic surface/elevation arguments to
`Tile.create`; the authoring function does not pre-create and later clean up a
registered candidate Tile.

Before any root or allocation, `set_world_tile` compares the requested
intrinsic authored values with the live Tile: semantic surface/name, intrinsic
optics/propagation, base movement costs, default light, height, elevation kind,
and slope axis. UUID and currently resolved light are excluded. Equal input is
an exact no-op; a new Tile identity is allocated only for a real requested
change.

### 6.2 World items

- `place_world_item(item, ...)`
- `move_world_item(item, ...)`
- `orient_world_item(item, ...)`
- `remove_world_item(item, ...)`

The initial supported object domain is the same renderer-materializable domain
as `WorldInitializedEvent`: a registered `BaseItem` with exact
`WorldObjectPlacement`, complete `ItemPresentationState`, and direct contained
item presentations when its storage block is an `Inventory`.

Location authority is validated before root declaration:

- placement requires `owner_uuid`, `stored_in_uuid`, `tile_uuid`, and equipped
  slot authority to be absent, `is_equipped` to be false, and no existing
  GridMap placement; and
- move, orientation, and removal require no owner/container/equipment
  authority plus one exact existing GridMap placement whose position and
  support Tile UUID agree with the BaseItem floor mirror.

An inconsistent or inventory/equipment-owned item is rejected without events
or mutation. Moving an item from inventory/equipment to the floor remains the
existing inventory/gameplay owner's responsibility; this API does not create
a second location authority.

Non-`BaseItem` spatial anchors remain valid for their existing mechanics but
are rejected by this structural-authoring API until the initial cold-world
contract can also materialize them. Entities are explicitly outside this
feature and retain `EntityCreatedEvent` and movement events.

`BaseItem.place_on_grid` must accept the causal parent and synchronize its
floor fields only after `GridMap.place_object` succeeds. One small explicit
BaseItem floor-placement synchronization method is reused by
place/move/orient/remove authoring functions. All fallible UUID/Tile/placement
validation occurs before the GridMap call. Once GridMap returns a committed
placement, synchronization is a total, non-vetoable assignment of `position`
and `tile_uuid`. Synchronization with absence clears `tile_uuid`.

Place, move, and removal reject a live `SpatialCondition` attached to that
item before the root because they can establish, change, or remove its anchor
position. The current event algebra allows later arrival EFFECT handlers to
cancel after an earlier handler has mutated; therefore this single-edit
feature cannot honestly claim atomic condition relocation or deletion. The
caller must first use the explicit condition lifecycle. Orientation-only edits
remain legal when their ordinary placement/location preconditions pass: they
do not change the anchor position, support Tile, condition footprint, or
condition handler. A future coordinated multi-edit/event-phase plan may add
atomic relocation as a separate feature.

Moving a world item does move every GridMap light source attached to that item.
Removing an item with attached light sources suppresses their illumination
while the anchor is absent and preserves their light identities/state so a
later placement can resume them. These are existing GridMap-owned mechanics
consequences inside the detailed placement lineage, not a second authoring
operation.

For authoring removal, `remove_world_item` calls `GridMap.remove_object` with
`clear_object_location=False`, verifies the mechanical removal succeeded, and
then explicitly synchronizes the BaseItem with absence. It does not rely on
GridMap's legacy `on_grid_object_removed` polymorphic callback. Existing
non-authoring callers may retain that callback until a separately scoped
cleanup; this feature neither expands nor pretends to remove it.

Removing an item here removes its world placement; it does not silently call
the item's destruction behavior or unregister the item. Destruction remains a
separate gameplay lifecycle because barrels and other items may have semantic
on-destroy effects.

### 6.3 Traversal connectors

- `register_world_connector(...)`
- `replace_world_connector(...)`
- `set_world_connector_enabled(...)`
- `remove_world_connector(...)`

These functions reuse the current immutable connector definitions and the
existing GridMap connector APIs. They add no connector manager or secondary
index. `replace_world_connector` compares the complete requested definition
with `previous.definition()` before root declaration or replacement
allocation; equality is an exact no-op with no connector revision/index/event
change.

## 7. Required bounded owner repairs

These repairs are necessary for the feature to make an honest atomic claim.
They are not authorization for a wider GridMap refactor.

### 7.1 Tile causal parent and complete semantic mutation

`GridMap.set_tile` and `GridMap.remove_tile` gain an optional parent UUID, as
elevation, base-light, object, and connector mutations already have.

A Tile replacement produces a detailed spatial child only when traversal,
optics, propagation, default/resolved light, or derived-light settlement
actually requires that mechanics boundary. A surface/name-only change in an
otherwise equivalent unlit slot emits only the `WorldModifiedEvent` lifecycle.
The root is already the exact semantic fact; manufacturing a spatial child
would make `SpatialSensesSystem` recompute observers for no reason.

Replacing a Tile under an active objective light field recomputes the new
support's derived illumination through the existing light owner, because the
new Tile cannot inherit the old Tile's private derived modifiers. Actual light
deltas remain detailed children. No delta means no light/sensory event.

### 7.2 Allocation-free Tile validation

Add one pure `validate_tile_creation_inputs(...)` routine in
`dnd/core/base_tiles.py`. It validates every authoring/`Tile.create` input—exact
position, booleans, strings/optional sprite legacy value, `TileSurface`, four
costs, `LightLevel`, height, surface kind, and slope axis—before constructing
any `BaseValue`, modifier, `ModifiableValue`, or Tile.

`Tile.create` reuses this validator before its current child allocations. The
authoring function calls it before root declaration. Invalid input therefore
leaves EventQueue, GridMap, `BaseBlock`, `BaseObject`, `BaseValue`, modifiers,
and related registries byte-for-byte/identity-for-identity unchanged. No
cleanup-on-failure routine is added.

### 7.3 Tile removal/replacement commit and owned-graph release

Current `remove_tile` deletes the Tile before publishing its vetoable spatial
event. Reverse that order:

1. validate references;
2. accept the detailed effect;
3. commit Tile/index removal and revisions;
4. settle light/senses through the existing completion boundary; and
5. return success.

If the detailed event is canceled, the Tile and all indexes remain unchanged.
No compensating rollback event is added.

After an accepted replacement/removal detaches the old Tile from GridMap, the
old Tile's finite owned ECS graph must also be released. Add one explicit local
Tile cleanup routine in `base_tiles.py`; do not add a generic recursive
destructor. It releases exactly:

1. the Tile's four movement `ModifiableValue` roots;
2. each root's four locally owned channels (`self_static`,
   `to_target_static`, `self_contextual`, `to_target_contextual`);
3. the Tile-sourced modifiers and constraints stored by those channels; and
4. the old Tile registry entry itself.

Imported `from_target_*` channels are references, not Tile-owned values: clear
those references without unregistering the imported objects. The cleanup must
not use `ModifiableValue.get_all_modifier_uuids()` because that traversal also
includes imported channels. Referential preflight rejects any remaining
foreign-owned live modifier/handler/condition attachment before effect
acceptance. Cleanup runs child-first only after map/index commit; an unrelated
Tile and all of its registry members must remain byte-identical.

### 7.4 Tile referential integrity

Replacing or removing a Tile must reject while any of these live references
exist:

- Entity occupancy;
- direct or spatial-condition coverage;
- Tile-owned live handlers or attached light sources that would outlive the
  removed Tile;
- any foreign-owned modifier still attached to a Tile movement value;
- any center or boundary world-object placement on that Tile; or
- a traversal connector endpoint anchored to that Tile.

The first version does not cascade-delete dependents. A future coordinated
multi-edit feature may own that policy; this single-edit feature must fail
clearly rather than create dangling support UUIDs.

### 7.5 Base-light commit ordering and exact no-op

`GridMap.set_tile_base_light` currently mutates `default_light` before its
vetoable event and treats a masked resolved-light equality as a no-op. Repair
that owner boundary:

1. compare requested `default_light` with current `default_light` before any
   event; only equality is a no-op;
2. preview the resolved after-value without mutation using the Tile's current
   illumination/cap values;
3. when the resolved value will change, accept the existing typed light/Tile
   effect before mutation, then commit, complete it with the actual resolved
   value, and run the existing light/sensory path; and
4. when the resolved value is masked and will not change, commit the authored
   default only after the accepted world root and represent it only in the
   root's exact cold after-state.

The masked case does not manufacture an empty detailed event or request
observer recomputation. `SpatialSensesSystem` therefore needs no new hint,
predicate, or event subscription for this feature.

### 7.6 Object floor-field commit ordering

`BaseItem.place_on_grid` currently writes local floor fields before GridMap
accepts placement. It must write them only from the returned committed
`WorldObjectPlacement`. Move/orient authoring uses the same total explicit
synchronization step, and removal uses explicit synchronization with absence.
A canceled operation leaves both GridMap and BaseItem unchanged.

`GridMap.move_object` also needs one bounded lifecycle repair. It accepts the
departure effect before attempting arrival. If arrival is rejected or raises
before commit, the already-accepted departure must be terminally canceled
before the root is canceled. State is not rolled back because it was never
committed; this merely prevents an orphan EFFECT lineage.

Before any place, move, or removal item root, the high-level leaf scans the
current finite active spatial-condition collection and rejects when a
`SpatialCondition` has `anchor_kind=WORLD_OBJECT` and the target item UUID.
This is one closed-domain `SpatialCondition` check at the high-level
composition boundary; GridMap and BaseItem do not import that subclass.
Orientation does not perform this exclusion because it preserves anchor
position and support. No condition is moved, deactivated, or otherwise
modified by this feature.

`GridMap.move_object` still terminally cancels its accepted departure if the
arrival is rejected. Slice 0 must prove that, after excluding an attached
condition through the pre-root rule, no active production departure EFFECT
handler mutates another owner. The existing departure/arrival values remain
the movement facts consumed by senses and future presentation. No relocation
event, condition manager, anchor index, callback API, effect-order rule,
transaction, or rollback object is added.

### 7.7 Attached light settlement follows world-object presence

GridMap already owns light source positions, affected Tile deltas, anchor
bindings, and composable suppression tokens. Extend that existing owner with
the object equivalent of its current entity-presence settlement:

- after first placement or move arrival commits, move every light attached to
  the object to the committed placement and clear the object-absence
  suppression token;
- after terminal object removal commits, add that suppression token, removing
  current illumination without deleting the light source; and
- a move departure (identified by its destination `old_position`) neither
  suppresses nor deletes the light; the paired arrival moves it once.

Light batch events and resulting sensory deltas remain children of the
detailed object placement/removal effect and settle before that effect and the
world root complete. The feature does not duplicate light positions in
`WorldModifiedEvent` or manipulate Tile illumination directly.

`_fire_light_batch_events` currently routes its fact through the vetoable
spatial-event path after illumination has already committed. Route that same
existing `SPATIAL_LIGHT_CHANGED` value through GridMap's committed-spatial-
fact seam, repaired as specified in §3.3. This does not add an event or bypass
a valid precommit veto: the light delta already exists. Declaration validators
are not redispatched; execution/effect handlers still receive the fact and may
publish ordinary reactions, including `Hidden: Reveal`, but their returned
event replacements/cancellations cannot rewrite it. The observer reducer sees
the committed batch exactly once and no false cancellation can be stored after
Tile illumination changed.

`WallTorch` currently also stores `_wall_torch_position`, duplicating GridMap
placement. Remove that private position authority. `light()` resolves the
torch's exact current GridMap placement and refuses to ignite while unplaced;
`mount()` places first, then lights. Its existing `is_lit`, attached light UUID,
and light/put-out event paths remain unchanged.

### 7.8 Existing completion algebra is unchanged

This feature does not alter `Event.phase_to`, pre-completion system iteration,
or `publish_completed_fact`, and it introduces no completion-error wrapper.
The single `publish_committed_phase` repair changes only how execution/effect
handlers observe an owner fact that is already committed; ordinary proposal
and completion semantics are unchanged. Existing expected veto/validation
outcomes are handled before commit as described above. An unexpected exception
from an engine system remains a fatal engine bug and propagates through the
existing event algebra; this structural authoring feature neither swallows it
nor invents rollback/cancellation facts after an unknown partial failure.

Global postcommit fault semantics affect progression, conditions, combat, and
other reversible publications. If that contract needs repair, it requires a
separate engine-lifecycle plan and its existing rollback regressions. It is not
smuggled into world materialization.

`WorldModifiedEvent` is not added to `SpatialSensesSystem.EVENT_TYPES`; its
children already perform all required reduction.

### 7.9 Shared cold projection

Move the three projection routines currently embedded in
`battlefield_catalog._world_initialized_event` into pure functions in the new
leaf module. Both initialization and modification use those functions. This
prevents initial and dynamic state contracts from drifting without moving
mechanics or ownership out of their existing modules.

## 8. Exact lifecycle for each call

### 8.1 Successful edit

1. Resolve and validate the current target through public owner APIs.
2. Capture the exact cold `before` value, if one exists.
3. Return without events if the requested state is already equal/no-op.
4. Publish the `WorldModifiedEvent` declaration with the address and `before`.
5. Advance the root explicitly through execution and effect. Stop if canceled.
6. Call exactly one existing mechanical owner mutation with
   `parent_event=root_effect.uuid`.
7. Allow that synchronous owner call to commit and complete all detailed,
   anchored-light, spatial-effect, and sensory descendants.
8. For a BaseItem operation, perform its total owner mirror synchronization
   from the committed placement/absence.
9. Capture the exact cold `after` value, if one exists.
10. Complete the root with `before` and `after`.
11. Return the completed root to the authoring caller.

The returned completion and its lineage are the semantic delimiter for this
authoring call. It is not assumed to be the final global EventQueue append,
because passive observers may append diagnostics after storing it.

### 8.2 Rejection or cancellation

- Pure invalid input discovered before declaration raises without touching the
  event queue or world.
- Root cancellation stores the CANCEL lineage, raises `ValueError`, and
  performs no child mutation.
- If the detailed owner event is canceled or rejects before commit, the root
  is explicitly canceled and never completed successfully. A move's accepted
  departure is canceled before its root when arrival rejects.
- No exception path may publish a successful root after a precommit failure,
  and expected veto/validation paths never cross the owner commit boundary.
- No rollback framework is introduced. The plan relies only on the current
  atomic owner methods; `remove_tile` is repaired to meet that law.
- Unexpected internal system exceptions retain the existing event-algebra
  behavior and are outside the supported authoring rejection contract.

### 8.3 No-op

An exact no-op creates no root and no detailed events. This applies to
unchanged elevation/light, unchanged object placement/orientation, and
unchanged connector enabled state or replacement definition.
`set_world_tile` compares requested intrinsic values before allocating
identity, so semantically equal Tile input is also a no-op.

## 9. Pygame-ce connection

No pygame code is part of this implementation. The feature establishes the
contract that the later pygame plan consumes.

### 9.1 Objective scene materialization

The future in-process bridge starts with one `WorldInitializedEvent`, then
folds completed `WorldModifiedEvent` values into an objective scene store:

- Tile slot key: `(x, y)`;
- object key: item UUID;
- connector key: connector UUID.

The renderer applies add/change/remove from before/after presence. It selects
client assets using existing semantic state:

- Tile `surface`, name, elevation kind/axis, and support height;
- object `item_id`, presentation state, placement side/orientation, and
  vertical extent; and
- connector `presentation_key`, kind, endpoints, and elevation values.

No PNG path, pixel pivot, pygame surface, camera rotation, or Z-grid pixel
offset enters the engine event.

### 9.2 Async queue and causal batching

The future game runner serializes engine commands on its engine side. Before
one synchronous command it captures `{generation_id, start_cursor}`. Before
yielding to asyncio or starting another command it captures `end_cursor`,
verifies the generation is unchanged, and copies that closed interval into the
presentation queue. It does not register a pygame callback inside EventQueue.

For an authoring command, the returned completed root/lineage is the semantic
delimiter within that interval; it need not be the last global append. Pygame
ingests the whole copied interval before drawing a frame, so an object
placement child cannot be displayed before the same interval supplies the
terminal root's complete item state. A lit fixture move/removal supplies its
objective placement root plus ordinary light and observer-sensory descendants
in that same interval; the future reducer updates both sprite placement and
illumination from their proper owners. Enemy processing may resume only after
the interval has been detached, not after its animations finish.

Engine mechanics never wait for animation. The player-command UI may wait for
presentation acknowledgment before accepting the next player action; the
enemy loop may continue to resolve and enqueue work. A renderer acknowledgment
never completes, cancels, or mutates an engine event.

### 9.3 Subjective player display

The objective store is not the player-visible answer. Each of the two
player-controlled characters retains its independent `SensoryUpdateEvent`
reduction. The later pygame reducer combines:

```text
objective materialization from WorldInitialized/WorldModified
  + observer sensory after-values
  + same-model subjective combat logs
  = one controlled-observer presentation
```

The omniscient objective log remains available for debugging and for the
automatic `UNREPRESENTED` event inventory.

### 9.4 Exact materialization limit

This feature promises convergence for structural membership/placement and
authored definitions across one copied presentation interval. It does not
define durable history, save files, or general replay.

`WorldTileState.resolved_light` and parts of `ItemPresentationState` (HP,
charges, open/lit state) are live presentation values. Ordinary gameplay may
change them without a world-authoring root. Therefore:

- a test with no intervening gameplay may fold initialization plus world roots
  and compare the structural/materialized result with live state; but
- after gameplay, the later pygame/event-coverage plan must specify how its
  reducers apply the existing item, damage, object-state, light, and sensory
  events from the same objective intervals.

This feature proves only that ordinary door/torch/damage transitions do not
emit redundant `WorldModifiedEvent` roots. It does not implement or test their
presentation reducers. Persistence remains a separate future plan.

## 10. Implementation slices and stop points

Every slice is reviewed before the next begins. No pygame/game folder is
touched.

### Slice 0 — characterization only

- Record current event trees and revision/sensory results for one Tile, object,
  elevation/light, and connector mutation.
- Prove the current surface-only Tile-event gap without prescribing a fake
  spatial child.
- Characterize the current invalid-`Tile.create` registry leak, postcommit
  Tile removal and owned-graph leak, masked base-light behavior, and
  move-arrival rejection with an accepted departure EFFECT.
- Inventory every active declaration/EFFECT handler for object placement,
  change, and removal; after the pre-root attached-condition exclusion, no
  remaining production departure handler may mutate another owner under the
  relocation-removal interpretation.
- Inventory active production callers of the owner methods being changed.
- Characterize the existing committed-spatial path with an EFFECT canceller
  and with `Hidden: Reveal`: the former currently records a false cancellation
  while the latter is a required reaction that must survive the repair.
- Confirm the import DAG before adding the leaf module.

Stop: no production changes.

### Slice 1 — cold value contract and shared projections

- Add `WORLD_MODIFIED` and the validated event model.
- Complete `WorldConnectorState`.
- Add pure Tile/object/connector projection functions in
  `dnd/world_authoring.py`.
- Migrate `WorldInitializedEvent` construction to those projections without
  changing battlefield output except for the newly completed connector fields.
- Add schema, value-safety, JSON round-trip, and initialization parity tests.

Stop: no authoring mutation API yet.

### Slice 2 — Tile authoring

- Add the four explicit Tile authoring functions.
- Add the allocation-free Tile input validator and reuse it from both the
  authoring boundary and `Tile.create` before any registered child is built.
- Add parent lineage to set/remove Tile.
- Admit semantic surface/elevation input through the existing Tile creation
  path;
- make Tile removal precommit;
- release the successfully displaced Tile's exact locally owned value graph;
- add all declared Tile referential-integrity rejection;
- repair base-light no-op/preview/commit ordering; and
- avoid sensory work and fake children for masked semantic light changes.
- Prove intrinsic equality before identity allocation, conditional detailed
  children, exact revisions, masked and unmasked light, sensory selection,
  cancellation, old-graph release with sibling preservation, registry
  cleanliness, and cold before/after values.

Stop and review the exact Tile candidate.

### Slice 3 — placed world-item authoring

- Add explicit place/move/orient/remove functions for registered `BaseItem`.
- Repair postcommit floor-field synchronization as an explicit total
  BaseItem mirror write; removal must not use GridMap's polymorphic cleanup
  callback.
- Enforce the exact inventory/equipment/floor location-authority preconditions
  before root declaration.
- Reject place, move, and remove pre-root when the item anchors a live spatial
  condition; allow orientation because it preserves the anchor position and
  support; do not alter the condition handler or event-phase algebra.
- Terminally cancel an accepted move-departure effect if arrival rejects
  before commit.
- Settle attached light movement/presence through GridMap's existing light
  owner and suppression mechanism, and remove WallTorch's duplicate private
  position authority.
- Repair the existing committed-spatial-fact seam with the one explicit
  `EventQueue.publish_committed_phase` law, then publish the resulting
  already-committed light batch through it.
- Reuse complete object projections including direct Inventory contents.
- Prove center and directional-boundary placement, including the fact that
  walls may independently occupy either incident Tile side.
- Prove place/move/remove reject an attached spatial condition without events
  or mutation, prove orientation remains legal and leaves the condition
  untouched, and prove lit WallTorch move/remove/re-place with exact light and
  sensory descendants.
- Prove an injected execution/effect cancellation cannot rewrite or terminate
  a committed fact, cannot prevent later reaction handlers, and leaves no
  CANCEL version, while `Hidden: Reveal` still publishes its ordinary child
  condition-removal lineage.
- Prove removal does not invoke destruction behavior.

Stop and review the exact object candidate.

### Slice 4 — connector authoring

- Add the four explicit connector functions; the typed enabled setter covers
  both enable and disable operations.
- Treat a requested definition equal to `previous.definition()` as a no-op
  before root declaration or connector allocation.
- Reuse existing connector identity/index owners.
- Prove register/replace/enable/disable/remove before/after values and support
  integrity.

Stop and review the exact connector candidate.

### Slice 5 — causal/materializer/pygame-contract closure

- Prove complete causal trees and that the root completes after its semantic
  descendants without asserting that it is the queue's globally last append.
- Prove one initialization plus ordered structural modifications folds to the
  same structural state as the live GridMap/materialized items/connectors when
  no intervening gameplay state changes exist.
- Prove a test-local external materializer can consume only cold event values;
  it must not read registries or GridMap while applying changes.
- Prove ordinary door/torch/damage gameplay emits no redundant world root;
  presentation reduction of those events remains in the pygame/event-coverage
  plan.
- Prove two observers receive only the existing independent sensory changes
  and that the objective root causes no duplicate reduction.
- Prove the future bridge can detach a generation-checked closed cursor
  interval and use the returned root lineage as the semantic delimiter inside
  that interval.
- Run affected gameplay, light/senses, pathing, item, connector, battlefield,
  and architecture lanes.

Stop: feature is complete only after final correctness, anti-slop, and
anti-OOP/import-DAG approval.

## 11. Acceptance test matrix

Tests follow `HOW_TO_TEST.MD`: public operation in, authoritative state and
event values out; no mocks of internal engine owners and no arbitrary sleeps.

| Case | Required observable result |
|---|---|
| Add semantic ground Tile | Tile admitted; one root completion with `None -> WorldTileState`; a detailed child exists only if mechanics/light actually change; no false sensory work |
| Replace ground with water | exact old/new surface, costs, UUIDs, and light; relevant path/light deltas only |
| Surface/name-only replacement | root exists with exact old/new semantic state; no fake spatial child and no path/FOV/light revision or sensory work |
| Equal semantic Tile request | no identity allocation, registry change, root, or detailed event |
| Invalid Tile request | validation fails before root and before any Tile/BaseValue/modifier/BaseObject registration; every affected registry and GridMap remains unchanged |
| Remove free Tile | detailed event accepted before deletion; root is `state -> None` |
| Replace/remove Tile registry ownership | old Tile, four movement values, their four local channels, and Tile-owned modifiers/constraints are gone; imported references are not unregistered; unrelated Tile graph is unchanged |
| Cancel Tile removal | Tile and UUID index remain; root cancels; no success completion |
| Replace/remove referenced Tile | clear rejection for Entity, direct/spatial condition, live Tile handler/light source, placed center object, placed boundary object, and connector endpoint; no mutation |
| Elevation edit | exact before/after support state; existing elevation child; paths invalidated once; pygame support height changes |
| Unmasked base-light edit | event acceptance precedes commit; exact default/resolved before/after state; objective light and affected observers update once |
| Masked base-light edit | changed default light is committed and represented only by the root; resolved light remains exact; no fake child or sensory recomputation is requested |
| Cancel base-light edit | default/resolved light and revisions remain unchanged; root has no successful completion |
| Place item | complete placement/item/contents after-value; BaseItem floor fields match GridMap after commit |
| Reject owned/inconsistent item | inventory-, equipment-, or conflicting-floor-owned item is rejected before root with every authority unchanged |
| Cancel item placement | neither GridMap nor BaseItem floor state changes |
| Move item | one root; exact before/after placement; departure/arrival and sensory descendants remain children; BaseItem mirror matches committed placement |
| Reject attached spatial condition | place/move/remove authoring rejects before root; GridMap, BaseItem, condition position/footprint/handlers, revisions, registries, and event queue remain unchanged |
| Orient item with attached spatial condition | orientation succeeds under the ordinary placement/location preconditions; position, support Tile, condition footprint/handlers, and condition identity remain unchanged |
| Reject move arrival | accepted departure is terminally canceled; GridMap and BaseItem remain at the original placement |
| Move lit WallTorch | attached light UUID/is-lit state are preserved; source position and illumination move exactly once; light/sensory deltas are detailed descendants |
| Remove/re-place lit WallTorch | removal suppresses illumination without deleting light identity; placement moves and unsuppresses it; private duplicate fixture position does not exist |
| Attempt to cancel committed light batch | illumination remains authoritative; execution/effect handler returns are not stored or chained; all later reactions still run; one non-vetoable committed light fact drives exact observer deltas; no false CANCEL fact is stored |
| Hidden reaction to committed light | `Hidden: Reveal` still observes EFFECT and publishes its ordinary condition-removal child when the committed light fact satisfies its rule |
| Orient item | same position/identity, changed orientation, no invented movement |
| Remove item placement | root after is `None`; explicit BaseItem mirror clears the floor location; GridMap callback is not used; destruction hook is not called; registry identity remains |
| Directional wall on either side | placement retains the owning Tile and direction independently for both adjacent Tiles |
| Register connector | complete state includes presentation key, support UUIDs, and elevations without duplicating a runtime revision |
| Replace/toggle/remove connector | stable UUID/authored ID and exact old/new mechanics; current indexes agree |
| Equal connector replacement | equality with `previous.definition()` is detected before root/allocation; revision, indexes, identities, and events remain unchanged |
| Detailed child cancellation | root cancels; no partial state or successful terminal |
| Exact no-op | no root and no detailed events |
| Structural materializer fold | with no intervening gameplay change, initialized state plus successful roots equals the final structural live snapshot |
| Ordinary gameplay separation | door/torch/damage transitions use their existing events and emit no redundant world root; their pygame reducers are not implemented here |
| Detached consumer | applying cold values succeeds after live registries/GridMap are reset |
| Closed async interval | generation and start/end cursors select an immutable copied interval; the returned root lineage delimits its authoring gesture even when a passive observer appends afterward |
| Hidden object edit | objective store changes; an observer without sensory access does not gain a visible object |
| Two controlled observers | each receives its own correct sensory delta; neither inherits the other's result |
| Root non-duplication | handling root completion does not bump revisions, recompute light, or emit sensory events |

Test-local materialization helpers may be small pure dictionaries keyed by the
public identities above. They must not become production replay, persistence,
or renderer frameworks.

## 12. Architecture and anti-slop gates

The exact candidate is rejected if it introduces any of the following:

- server, SDK, transport, renderer, pygame, TypeScript, or asset-file imports
  into engine modules;
- a late import or new import cycle;
- `getattr`, type-name strings, or broad `isinstance` dispatch used to evade
  the DAG (the high-level leaf's exact `BaseItem`/`Inventory` materialization
  checks and `SpatialCondition` attachment precondition are closed-domain
  checks, not a generic dispatcher);
- a manager, controller, service, repository, receipt, edit session, command
  hierarchy, visitor, event adapter, second event queue, or secondary spatial
  index;
- a generic mutation callback, context manager, transaction wrapper, undo log,
  or compensating-event protocol;
- a change to global event completion/failure ordering, a new completion
  exception/receipt, or any change to vetoable proposal registration beyond
  the single committed-phase publication repair;
- a durable authoring-history store, persistence format, replay framework, or
  promise that structural roots replace ordinary gameplay events;
- `dict[str, Any]`, sentinel strings, duplicate renderer DTOs, or custom
  serialization;
- dual writes of GridMap-owned placement/index/cache state;
- postcommit validation or reliance on GridMap's polymorphic removal callback
  for BaseItem authoring synchronization;
- any place/move/remove item edit while a live spatial condition is attached,
  rejection of an otherwise-valid orientation solely because a condition is
  attached, or any attempt to change condition handler/effect ordering in this
  feature;
- a second WallTorch position field or a light move performed outside the
  GridMap light owner;
- any light/senses/cache update caused by `WorldModifiedEvent` rather than its
  existing detailed children;
- an empty detailed event or sensory hint manufactured for a semantic-only
  authored change already represented by the root;
- pixel coordinates, concrete asset paths, pivots, animation frames, camera
  orientation, or Z-grid offsets in engine state;
- conversion of normal gameplay state changes into redundant world-authoring
  roots; or
- production changes outside the declared file envelope without a new human
  scope decision.

## 13. Planned file envelope

Expected production files:

- `dnd/core/events.py`
- `dnd/core/base_tiles.py`
- `dnd/core/gridmap.py`
- `dnd/blocks/base_item.py`
- `dnd/items/torches.py`
- `dnd/scenarios/battlefield_catalog.py`
- new `dnd/world_authoring.py`

Expected tests:

- new `tests/engine/test_world_modification.py`
- focused updates to `tests/engine/test_world_entity_initialization.py`
- focused existing Tile/elevation/light/senses/item/connector feature modules
  only where their public expected output changes;
- new or focused architecture tests for the import DAG and prohibited layers.

Not authorized:

- `/game` or pygame code;
- MapEditor/NeuroClient source or assets;
- server/deprecated server/SDK/transport/generated code;
- entity, encounter, action, spell, condition, or content-recovery redesign;
- renderer bindings or asset JSON;
- persistence or networking.

If implementation proves a required production file outside this envelope,
work stops for a plan amendment and human review.

## 14. Validation protocol for this plan

Before implementation, the same frozen plan candidate must be reviewed by:

1. **Correctness/causality/pygame reviewer** — checks atomicity, event ordering,
   sensory/light interaction, structural materializer sufficiency, ordinary
   gameplay coexistence, and the async consumer boundary against current code.
2. **Anti-slop reviewer** — looks for speculative layers, duplicate data,
   overbroad scope, unnecessary APIs, and test ceremony that does not protect
   behavior.
3. **Anti-OOP/ECS/import-DAG reviewer** — checks owner authority, system
   composition, absence of upward imports/type switches/hidden callbacks, and
   whether the single leaf module preserves a directed import graph.

Any substantive revision invalidates the earlier approvals and the revised
candidate is returned to all affected reviewers. Review metadata is appended
below; reviewers do not edit production or test code.

## 15. Review record

### Round 1 — rejected and corrected

All three reviewers rejected the first candidate. That review produced the
following candidate-two revisions (one was subsequently removed in Round 2):

- correctness: allocation-free Tile validation, honest masked base-light
  semantics, a proposed terminal-completion fault law, move-departure
  cancellation, cursor-bounded async detachment, and explicit coexistence with
  ordinary gameplay events;
- anti-slop: no fake spatial event for a semantic-only Tile edit, no needless
  Tile identity churn, no duplicate connector identity/revision fields, and no
  durable history/replay overclaim; and
- anti-OOP/ECS/import-DAG: explicit total BaseItem synchronization instead of a
  hidden polymorphic callback, plus terminal closure of both halves of a
  rejected move.

### Round 2 — rejected and corrected

The anti-OOP/ECS/import-DAG reviewer approved the second candidate. The other
two reviewers found further scope and ownership defects, all corrected:

- the global completion-failure redesign and its injected callback test were
  removed from this feature;
- masked base-light editing now uses only the semantic root when resolved light
  does not change, with no empty spatial child or new sensory selector;
- speculative public parent parameters and gameplay presentation reducers were
  removed;
- accepted Tile replacement/removal now releases the exact old Tile-owned
  value graph without touching imported or sibling state;
- equal connector replacement is a pre-root no-op; and
- BaseItem authoring now enforces a single inventory/equipment/floor location
  authority before root declaration.

### Round 3 — rejected and corrected

The anti-slop and anti-OOP/ECS/import-DAG reviewers approved the third
candidate. A fresh correctness reviewer found two current owner interactions
that contradicted atomic world-item authoring:

- the removal half of object movement deactivated an attached spatial
  condition before arrival admission; and
- placed-item movement/removal did not settle GridMap light sources attached to
  that item, while `WallTorch` retained a second private position authority.

The fourth candidate preserves the existing departure/arrival event values,
preflights attached-condition translation at arrival declaration, distinguishes
move departure from terminal removal, settles attached lights through the
existing GridMap owner/suppression seam, and removes WallTorch's redundant
position.

### Round 4 — rejected and narrowed

The anti-slop and anti-OOP/ECS/import-DAG reviewers approved the fourth
candidate. Correctness rejected relocation during arrival EFFECT because a
later, reorderable handler may still cancel after the condition has committed
its translated footprint but before GridMap commits the object.

The fifth candidate removes spatial-condition relocation from this feature
entirely. Position-establishing, position-changing, and removal operations
reject a live attached condition before their root. This preserves honest
atomicity without adding effect-handler priorities, a postcommit
callback/system, transaction state, rollback, or a new event phase. Attached
light movement remains supported because GridMap already owns an explicit
postcommit light settlement seam.

### Round 5 — rejected and corrected

The anti-OOP/ECS/import-DAG reviewer approved the narrowed ownership and import
design. The anti-slop reviewer found one unnecessary restriction: an
orientation-only edit had been rejected with a live attached condition even
though it changes neither anchor position nor support. The sixth candidate
limits the exclusion to place/move/remove and explicitly proves that
orientation remains legal and leaves the condition untouched.

### Round 6 — rejected and corrected

The anti-slop reviewer approved the corrected scope. The anti-OOP/ECS/import-
DAG reviewer found one stale sentence in the detailed item flow that still
said the attached-condition check ran before every item root. The seventh
candidate aligns that sentence with the operation contract, slice, proof
matrix, and gate: the check runs for place/move/remove only; orientation
preserves the anchor and remains legal.

### Round 7 — rejected and corrected

The anti-slop and anti-OOP/ECS/import-DAG reviewers approved the internally
aligned candidate. Correctness found that the existing method named as the
committed-spatial seam was not actually non-vetoable: ordinary EFFECT
registration could store a handler cancellation after illumination had
already changed. Simply suppressing EFFECT was invalid because the current
`Hidden: Reveal` handler must react there.

The eighth candidate adds one explicit committed-phase publication law to the
existing EventQueue owner. It stores the authoritative phase, lets every
handler publish ordinary reactions from an unregistered view, and never stores
or chains handler attempts to rewrite/cancel the committed fact. Vetoable
event registration and global completion semantics remain unchanged.

### Round 8 — accepted

The exact semantic candidate at SHA-256
`a53afe31439c7675b959c7f573b18e4cb2fb239ec505aff422f082a9dcd43a55`
received all three required approvals:

- correctness/causality/pygame: **APPROVE** — committed light publication can
  no longer record a false veto while `Hidden: Reveal` remains an ordinary
  reaction;
- anti-slop: **APPROVE** — the single committed-phase queue operation is the
  smallest principled repair and adds no dispatcher, callback chain,
  transaction, manager, duplicate state, or type switch; and
- anti-OOP/ECS/import-DAG: **APPROVE** — owner authority, causal identities,
  handler ordering, and the acyclic import structure remain intact.

No production or test code was changed during planning or review.
