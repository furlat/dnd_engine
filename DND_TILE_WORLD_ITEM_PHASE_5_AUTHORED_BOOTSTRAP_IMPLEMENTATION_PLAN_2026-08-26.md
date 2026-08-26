# Phase 5 authored-map and bootstrap implementation plan

Status: APPROVED IMPLEMENTATION AUTHORITY

Date: 2026-08-26

## 1. Objective

Complete Phase 5 of the Tile / world-item migration for the active
single-process Python runtime.

The result must make authored battlefield construction one truthful sequence:

1. construct the complete actor-free cold world directly while GridMap event
   publication is disabled;
2. publish exactly one deterministic `WorldInitializedEvent` containing that
   complete cold world;
3. create every authored dynamic SpatialCondition and light source only after
   initialization through its existing objective lifecycle;
4. create and deploy Entities only after the battlefield's authored dynamic
   state has settled; and
5. prove that the recorded cold fact plus ordinary subsequent facts reproduce
   the defined objective and subjective state.

This is an in-process mechanics phase. It is not a server, transport, SDK,
renderer, editor, generated-contract, or cross-language migration.

## 2. Governing authority

The implementation is governed, in order, by:

| Artifact | SHA-256 at plan freeze |
|---|---|
| `DND_TILE_WORLD_ITEM_VERTICAL_BOUNDARY_MIGRATION_PLAN_2026-08-17.md` | `50411e5575e6336ca0301acf032797cdf1d5ea885df5ccd37d6619f593e7a193` |
| `DND_TILE_WORLD_ITEM_ACTIVE_RUNTIME_SCOPE_AMENDMENT_2026-08-24.md` | `f10e2fbbcb6ba8732d078f0c4f2f5276716eb51e32c083068f3cae93c9ba52d6` |
| `DND_TILE_WORLD_ITEM_PHASE_4_IMPLEMENTATION_LEDGER_2026-08-25.md` | `b8f5fb6e1f7aed573900120f5705e561465ad4c45d76eaaf57763f4da2b86395` |
| `DND_TILE_WORLD_ITEM_PHASE_4_IMPLEMENTATION_MANIFEST_2026-08-25.json` | `e66f767412230e0ed9e0c024b1e155d27b581599375ee330d5759dcd498b0d85` |
| `HOW_TO_TEST.MD` | `96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013` |

The accepted Phase 4 execution baseline is 647 active nodes with normalized
node-set SHA-256
`0062d230c5a85ab1a08eb4ad6ebdf7c75ffed01e99d81b10dba561e9440e9cbe`.
The accepted Phase 4 manifest has 78 sorted unique members: 36 production and
42 active tests.

If any governing byte changes before implementation begins, Slice 5.0 stops
and the coordinator revalidates the affected authority. Historical or revoked
plans do not override this chain.

## 3. Scope

### 3.1 Included production behavior

- active authored battlefield definitions and direct Python builders;
- `build_battlefield` cold construction and publication order;
- the existing GridMap-disabled construction boundary for initial elevation
  and connector facts;
- authored spike-trap identity reservation and post-initialization activation;
- authored WallTorch static placement and post-initialization lighting;
- the existing item-state fact extended with the one missing typed
  per-instance spatial-condition link used by authored TrapLever objects;
- one complete post-light `ItemLocationStateEvent` after-value for each
  authored WallTorch and bounded bootstrap checks over its existing light and
  IGNITE lifecycles;
- the exact `BuiltBattlefield` identity classification needed by active
  in-process callers;
- the existing `WorldInitializedEvent` snapshot construction;
- ordinary Entity creation, deployment, occupancy, light, FOV, and sensory
  reduction after world initialization; and
- public active tests and migration governance artifacts.

### 3.2 Explicitly excluded

- `server/**`, `deprecated/**`, SDKs, TypeScript/JavaScript, generated wire
  contracts, transports, sessions, APIs, editor code, renderers, pygame asset
  binding, source maps, and cross-language fixtures;
- inactive `dnd.content_system` packaging and its blocked tests;
- compatibility facades or dual old/new bootstrap paths;
- a new event publisher, event index, completion transaction, callback stage,
  controller, service, manager, replay framework, receipt, or global
  EventQueue mute;
- a generalized map DSL, condition registry, light registry, plugin system, or
  callback-based deferred-activation framework;
- cold snapshot schemas for dynamic condition or light-source families that
  active authored maps do not place before initialization;
- Phase 6 hard-cut certification beyond the gates required to accept Phase 5;
  and
- unrelated cleanup, naming modernization, or content expansion.

### 3.3 Preservation rules

- Preserve unrelated dirty work. Never reset, checkout, clean, or commit.
- Use the current in-process Event/EventQueue and reducer boundaries exactly.
- Keep `WorldInitializedEvent` renderer-neutral and actor-free.
- Keep height relevant to movement only; do not add 3D light, FOV, or
  propagation calculations.
- Keep physical light/FOV topology and subjective sensory reduction unchanged.
- Keep per-step movement light/FOV settlement and turn-start sensory refresh
  unchanged.
- Do not add a compatibility property for any hard-cut result-field migration.

## 4. Accepted current state

### 4.1 What is already correct

`WorldInitializedEvent` already carries, in frozen nested value models:

- bounds, width, and height;
- every Tile UUID, coordinate, surface, movement cost, intrinsic optical and
  propagation policy, elevation tuple, base light, and resolved light;
- every exact object placement, semantic item state, and direct contained-item
  state; and
- every traversal connector in stable authored/runtime identity order.

`scenario_deployment.assemble_scenario` already calls `build_battlefield`
before it creates any Entity. It then uses the established Entity-created and
Game deployment/occupancy lifecycles. `SpatialSensesSystem` already reduces an
observer at the ENTERED pre-completion boundary and records a cold
`SensoryUpdateEvent` when the projection changes.

The active caller surface is narrow. Production reaches the builder only from
`assemble_scenario`; `prepare_scenario` is its no-start wrapper. Maintained
direct/indirect callers are the direct scenario, elevation proving and
performance, authored encounter, battlefield catalog, generic roster duel,
and prepared-scenario lifecycle tests. The shared manual authored-encounter
support also feeds excluded server/content-system modules; those excluded
callers are not migrated.

No active authored battlefield creates a direct Tile BaseCondition. Base Tile
light selected by `darken_arena` is intrinsic cold Tile state, not a dynamic
light-source lifecycle.

### 4.2 Current defects

The existing GridMap-disabled boundary suppresses ordinary Tile/object facts,
but four authored operations bypass or outlive that boundary, and the authored
construction sequence leaves replaced Tile identities registered:

1. `materialize_spike_trap_condition` publishes BASE_ACTION and condition
   lifecycles directly through EventQueue before world initialization;
2. `WallTorch.mount(..., lit=True)` creates an objective light source before
   initialization and publishes IGNITE interaction lifecycles directly;
3. `GridMap.set_tile_elevation` always publishes a guarded runtime lifecycle,
   even during cold construction; and
4. `GridMap.register_connector` always publishes a guarded runtime lifecycle,
   even during cold construction; and
5. authored builders create a floor and then replace final water, difficult,
   gap, elevation, or barrier-support Tiles. GridMap drops the former UUID from
   its reverse index but the replaced Tile remains in the BaseBlock registry,
   outside both GridMap and `WorldInitializedEvent`.

A read-only catalog probe from the accepted checkout found:

| Battlefield family | Event versions before `WorldInitialized` | Dynamic objective state already present |
|---|---:|---|
| standard hazards closed | 17 | one 20-cell SpikeTrap, two WallTorch light sources |
| standard hazards open | 17 | one 20-cell SpikeTrap, two WallTorch light sources |
| multi-object dark | 21 | one 20-cell SpikeTrap, three WallTorch light sources |
| elevation proving ground | 89 | 15 elevation lifecycles, five connector lifecycles, one SpikeTrap |
| other six battlefields | 0 | none |

The proving-ground 89 versions are 60 elevation versions, 20 connector
versions, four BASE_ACTION versions, four condition-application versions, and
one spatial-effect change fact. The standard/multi maps also publish four
IGNITE interaction versions per WallTorch before initialization. Light-change
facts themselves are buffered by GridMap and discarded, leaving the pre-world
light-source state especially incomplete as replay history.

The cold world event currently snapshots the lit WallTorch and its resulting
resolved Tile light. That makes the snapshot look complete while the source
identity/lifecycle that caused the light occurred before the world existed in
history. This is the exact double-representation gap Phase 5 must remove.

Two smaller completeness defects also exist at the post-initialization edge:

1. `ItemState` does not carry the TrapLever's exact linked SpatialCondition
   UUID, although that UUID is per-instance mechanics rather than catalog
   definition; and
2. `WallTorch.light()` commits item/source and Tile-light state, then ignores
   cancellation results from the ordinary light-change and IGNITE lifecycles.
   A bootstrap call can therefore appear successful without the complete
   completion facts needed to reproduce its final state.

Phase 5 closes these locally. It does not serialize action templates or
internal light-source registry rows, and it does not redesign EventQueue.

The accepted checkout also has these authored Tile identity orphans:

| Battlefield family | Current Tiles | Registered Tiles | Stale registered Tiles |
|---|---:|---:|---:|
| open floor | 225 | 225 | 0 |
| standard hazards | 225 | 258 | 33 |
| double-door/reveal | 225 | 243 | 18 |
| elevation proving ground | 225 | 235 | 10 |

The bounded repair is authored final-Tile-once construction. Phase 5 does not
reopen generic runtime Tile retirement or registry teardown.

### 4.3 Exact active authored classification

Every active case is classified exactly once as follows:

| Authored fact | Active cases | Classification |
|---|---|---|
| Tile UUID/position/surface/cost/intrinsic optics/propagation/base light/elevation | all ten maps | cold `WorldInitializedEvent` Tile state |
| boundary and center objects, including WallTorch fixtures while unlit | all object-bearing maps | cold object placement + item state |
| TrapLever-to-SpikeTrap per-instance link | standard closed/open and multi-object maps | typed `ItemState.linked_spatial_condition_uuid` in the cold object row |
| contained chest items | field-cache and multi-object maps | cold contained item state |
| open/closed door mechanics | relevant maps | cold item and boundary-structure state |
| traversal connectors | five proving-ground connectors | cold connector state; no pre-world lifecycle |
| direct Tile BaseCondition | none | forbidden inside current cold builders; no snapshot model added |
| independently owned SpatialCondition | four SpikeTrap map builds | reserve identity during cold build; construct and activate after initialization |
| dynamic light source | seven WallTorch instances across the three applicable catalog builds | place fixture unlit in cold snapshot; call existing `WallTorch.light` after initialization; require completed light-change + IGNITE facts, then publish the existing complete item/location after-value |
| Entity | none in `build_battlefield` | ordinary creation/deployment after complete battlefield setup |

The seven WallTorch instances above are catalog-case instances (two closed,
two open, and three multi-object), not seven simultaneous sources.

Any future authored family that would violate this table must choose one of
the two master-plan policies before construction: a complete cold snapshot or
creation after initialization through an existing complete lifecycle. It must
not silently reuse a partial case here.

## 5. Target ownership and event sequence

Every build requires a fresh authored-world runtime. Before any mutation,
`build_battlefield` resolves the battlefield ID and then rejects unless the
EventQueue cursor is zero, GridMap has no Tiles, object placements,
connectors, or SpatialConditions, and the BaseBlock registry contains no Tile.
With no Tiles there can be no valid Tile-owned entity occupancy; the later
cold invariant still checks every newly built Tile's membership explicitly.
This is an admission rule, not rollback. It makes repeat
build rejection objective-atomic and makes a partial cold-build failure
terminal until `reset_engine_runtime()`.

For every successful admitted `build_battlefield` call, the authoritative
order is:

```text
record EventQueue cursor
    -> pass the fresh authored-world admission gate without mutation
    -> GridMap.disable_events
    -> create each final Tile identity once, with its final terrain/elevation
    -> build static objects, contents, and connectors directly
    -> reserve but do not construct authored dynamic-condition identities
    -> mount authored WallTorches unlit
    -> validate that the cold builder emitted no EventQueue facts and owns no
       direct Tile conditions, SpatialConditions, WallTorch sources, Entities,
       or stale/extra registered Tile identities
    -> construct the complete unregistered WorldInitializedEvent while the
       cold boundary remains active
    -> GridMap.enable_events(flush_pending=False)
    -> publish exactly one actor-free WorldInitializedEvent
    -> materialize authored SpikeTrap conditions in deterministic authored order
    -> for each authored WallTorch in deterministic authored order:
         call the existing light method once
         require this call's completed objective light-change and IGNITE facts
         publish one existing ItemLocationStateEvent with the complete lit
         item/source state after-value and unchanged exact floor placement
    -> return the fully settled BuiltBattlefield
    -> scenario assembly creates Entities
    -> scenario assembly deploys Entities through ordinary occupancy lifecycles
    -> each observer's own ENTERED effect causes its one initial sensory delta
```

The cold event is therefore a complete snapshot of the world immediately
before authored dynamic setup. The later condition/light facts transform that
snapshot to the final pre-actor battlefield. No state is represented twice.

### 5.1 Failure semantics

- Unknown battlefield identity or any exception during static construction,
  cold-state validation, or snapshot creation publishes no
  `WorldInitializedEvent` for that attempt.
- Fresh-world admission is checked before GridMap is disabled or any authored
  object is constructed. A rejected repeat build therefore emits no event and
  changes no objective state.
- The `finally`/exception path always re-enables GridMap and discards pending
  bootstrap facts; it does not flush them.
- No rollback manager or event deletion is added.
- A failure after partial cold mutation is terminal for that runtime even
  though no world fact was published. The caller must use the existing
  `reset_engine_runtime()` boundary before retrying; Phase 5 does not claim the
  partial unpublished registry/GridMap state was rolled back.
- Dynamic setup runs only after a completed world fact. A later dynamic
  lifecycle cancellation/failure is recorded honestly as post-initialization
  setup failure; it is not relabeled as a failed cold construction and its
  history is not erased. The builder raises and never returns a successful
  `BuiltBattlefield` unless every authored WallTorch has both required
  completion facts and its complete post-light item-state fact.
- Before the world fact is published, the implementation validates every
  dynamic instruction structurally: reserved condition identity, nonempty
  in-bounds footprint, placed unlit WallTorch identity, and duplicate-free
  ordering. This keeps ordinary post-init operations free of avoidable content
  errors while preserving runtime handler authority.

## 6. Minimal implementation design

### 6.1 Construct every authored final Tile identity once

Do not use runtime elevation mutation to author the proving map. Create each
proving-ground Tile once with its final walkability, support height,
progressive-surface kind, and slope axis. The gap is likewise created once as
the final nonwalkable Tile.

For the standard hazard floor, create each coordinate once as exactly one of:
stone, water, or difficult terrain. Spike cells retain their ordinary final
support Tile because the SpikeTrap remains an independent post-init
SpatialCondition.

Delete the redundant `set_tile` calls from both barrier placement helpers.
The supporting floor already exists with its final Tile identity before a
wall or door is placed.

Open bright/dark floors keep the existing rectangle construction because they
do not replace any resulting Tile.

After every authored build, the set of registered Tile identities must equal
the set of current GridMap Tile identities and the Tile identities in the
cold world fact. Do not fix this by generically unregistering old Tiles from
`GridMap.set_tile` or `create_rectangle`; runtime Tile replacement is outside
this phase.

Before any of those writes, the fresh-world admission gate rejects a nonzero
event cursor, any existing GridMap world membership, or any registered Tile.
The gate uses public GridMap/EventQueue queries plus one direct, read-only
`BaseBlock._registry` scan filtered to Tile. That private scan is explicitly
authorized only at this authored-world authority boundary because BaseBlock
has no public registry enumerator and extra Tile identities are the defect to
reject. Do not add a generic registry enumeration API for this phase.

### 6.2 Complete initial connector registration inside the cold boundary

`GridMap.register_connector` retains definition/support/identity validation.
If events are disabled, it indexes the newly built connector directly, bumps
the connector revision once, and returns it without constructing or
publishing `TraversalConnectorChangeEvent`. With events enabled, its existing
guarded, vetoable lifecycle remains unchanged.

Do not broaden this branch to runtime replacement, enabling/disabling, or
removal. Cold authored construction uses initial registration only.

### 6.3 Reserve SpikeTrap identity without constructing objective state

Extend the existing `materialize_spike_trap_condition` seam with one optional
`condition_uuid`. When present, it is forwarded as the concrete condition's
UUID through the existing materializer. It does not replace
`source_entity_uuid`, change the recipe, or create a new materialization path.

During static construction:

- reserve one UUID for the standard spike network;
- build `TrapLever` against that future condition UUID;
- reserve one UUID for the proving-ground landing hazard; and
- do not instantiate, register, index, activate, or publish either condition.

After `WorldInitializedEvent`, materialize each reserved SpikeTrap through the
existing `materialize_spike_trap_condition` root lifecycle. The created
condition UUID must equal the reserved UUID already referenced by the lever or
the battlefield result.

Add one optional frozen `linked_spatial_condition_uuid` field to `ItemState`.
`TrapLever.to_item_state()` derives it from its linked `PullLeverAction`
template, rejects multiple distinct non-null targets, and leaves it `None`
when a non-authored/unlinked lever has no target. This carries the one
per-instance mechanic that its semantic catalog identity cannot reconstruct.
Do not serialize the action template, add a generic binding collection, or
make the snapshot a second action registry.

Keep the existing notable handles rather than redesigning `BuiltBattlefield`:

- standard maps retain `StandardArenaObjects.spike_condition_uuid`; and
- the proving map retains `BuiltBattlefield.object_uuids["landing_hazard"]`.

The latter name is imperfect but actively consumed and is not a serialization
authority. `_world_initialized_event` inventories actual GridMap placements,
not that notable-handle dictionary. Renaming result mappings, adding aliases,
or introducing pending-condition metadata would add migration work without
closing the bootstrap defect.

### 6.4 Place light fixtures cold; activate light sources hot

Every authored WallTorch is built and mounted with `lit=False` during static
construction. Its exact boundary placement, height, orientation, semantic
item state, and unlit light capability are captured by
`WorldInitializedEvent`.

After the world fact and after SpikeTrap activation, collect all placed
WallTorch fixtures from the finished object placements and concrete BaseItem
identities, sort them by `(placement.position, object_uuid)`, and call each
existing `light()` method once.

For each call, record the public EventQueue cursor immediately before the call
and inspect only the synchronous events returned by
`EventQueue.iter_events_since(cursor)`. Require at least one completed
`SPATIAL_LIGHT_CHANGED` fact and the exact completed IGNITE interaction whose
`source_object_uuid` and target are that WallTorch. If either lifecycle was
canceled or failed to complete, raise a post-initialization setup error. The
already published world fact and any ordinary partial dynamic history remain;
the runtime is terminal until reset.

Only after both lifecycles complete, call the existing
`BaseItem.publish_location_state(ItemLocation.FLOOR, ...)` with the unchanged
exact placement and the completed IGNITE event as parent. This publishes the
existing complete `ItemState` after-value, including `light_source.is_lit` and
its radii. Together, the object placement/item fact and resolved-Tile
light-change map reproduce the source's authored mechanics without exposing
the private encounter-local light-source UUID. No pending-work registry,
bootstrap-only light event, direct `_light_sources` write, new event family,
or EventQueue lifecycle seam is allowed.

The current authored policy is exact: every placed battlefield WallTorch is
initially lit. Standard closed/open therefore activate two, multi-object dark
activates three, and every other map activates zero. A future authored unlit
fixture requires an explicit content-field decision; Phase 5 does not invent
that unused variant.

### 6.5 Cold-state validation

Immediately after the static builder returns and before GridMap is re-enabled,
construct the frozen world event and validate from public/read-only state
that:

- the EventQueue cursor has not advanced;
- every Tile's direct `active_conditions_by_uuid` is empty;
- `GridMap.get_spatial_conditions()` is empty;
- every Tile's entity UUID set is empty;
- a direct read-only BaseBlock registry scan filtered to Tile has exactly the
  same UUID-to-object mapping as `GridMap.get_all_tiles()`;
- the world event Tile UUID-to-position rows equal that same complete set, so
  neither missing nor extra registered Tile identities can pass;
- the reserved standard/proving SpikeTrap UUID is not yet a live
  BaseCondition;
- every connector snapshot source resolves to the matching live connector;
- every current object placement resolves to a BaseItem;
- every placed WallTorch is currently unlit and has no attached light source;
  and
- the authored spike footprint and reserved identity exist together.

This is one content-boundary invariant function beside `build_battlefield`.
It is not added to EventQueue, GridMap, or a new validation framework.

### 6.6 World snapshot remains minimal

Do not add condition or light-source fields to `WorldInitializedEvent` in this
phase. The active cold world owns none after the separation above. The one
missing TrapLever link belongs to its existing `ItemState`, not to a new world
schema layer. Existing Tile base/resolved light remains complete cold Tile
state. Existing unlit
WallTorch item state declares the fixture's semantic radii and current unlit
state. Ordinary post-init events carry all changes to resolved Tile light, the
authored object IGNITE operation, and the exact lit item/source after-value.

Keep the existing deterministic ordering:

- Tiles by coordinate;
- objects by `(position, object_uuid)`;
- contained items by UUID; and
- connectors by `(authored_id, connector_uuid)`.

### 6.7 Entity and subjective reduction order

Do not add an Entity bootstrap path. `assemble_scenario` continues to:

1. call the fully settling `build_battlefield`;
2. validate the built map;
3. create Entities through the current `EntityCreatedEvent` seam;
4. deploy each Entity through `Game` and Tile-owned occupancy; and
5. apply scenario setup effects through their current lifecycles.

For each deployed observer, its own ENTERED EFFECT must cause exactly one
initial `SensoryUpdateEvent` before that ENTERED completion when the projection
changes. Later actors, portable-torch setup, conditions, or other ordinary
facts may correctly cause further deltas. `Senses.position` remains reducer
owned and no Encounter refresh is added.

### 6.8 Replay proof is a detached projection, not a new runtime

There is currently no production objective replay consumer, and Phase 5 does
not create a live-world rehydration service or second state authority. Replay
sufficiency is proved in tests by reducing the public frozen
`WorldInitializedEvent` and the complete post-init completion facts into a
detached value projection containing Tiles, placements/item state,
connectors, per-instance object links, SpatialCondition
identities/footprints, resolved light, WallTorch lit/source capability,
Entity positions, and Senses fields. That projection must equal the
corresponding public live state.

Do not call `rebuild_object_placements` against still-live BaseItem registry
objects and label that a complete replay proof. Placement rebuild remains its
own accepted invariant. Do not add a production reducer merely to host test
assertions; if a future active consumer needs live materialization, it requires
its own explicit plan and ownership decision.

## 7. Implementation slices

### Slice 5.0 — Freeze and preflight

No production or test edits.

1. Verify the five governing hashes in Section 2.
2. Verify the accepted Phase 4 manifest has 78 exact current members and no
   hash mismatches.
3. Recollect the accepted 647-node baseline and confirm its normalized hash.
4. Record `git status --short`, preserving every unrelated path.
5. Re-run the authored catalog/caller inventory and record exact active
   dynamic cases, callers, and tests.
6. Create one append-only Phase 5 implementation ledger:
   `DND_TILE_WORLD_ITEM_PHASE_5_IMPLEMENTATION_LEDGER_2026-08-26.md`.
7. Record the exact authorized initial production/test envelope and the
   governed exclusions.

Stop for coordinator review if any authority, baseline membership, or current
case classification differs materially from this plan.

### Slice 5.1 — Cold-build boundary and identity hard cut

1. Add the pre-mutation fresh authored-world admission rule, including the
   exact registered-Tile absence check.
2. Build every final authored Tile identity once, including terrain and
   elevation, and remove redundant barrier Tile replacements.
3. Add the disabled cold-commit branch for initial connector registration.
4. Add optional exact condition UUID support to the existing spike
   materializer.
5. Change standard/proving builders to reserve SpikeTrap identities without
   constructing conditions.
6. Add the typed TrapLever linked-SpatialCondition field to its existing
   `ItemState` snapshot.
7. Mount every authored WallTorch unlit.
8. Add the cold-state invariant and prove the static builders advance no
   EventQueue cursor.

Run the focused public cold-boundary, elevation, connector, condition
identity, object placement, and catalog tests. Stop for coordinator review if
any repair requires a new abstraction or scope expansion.

### Slice 5.2 — Initialization and ordinary dynamic setup

1. Construct the complete unregistered `WorldInitializedEvent` inside the
   guarded cold-build block.
2. Re-enable GridMap with `flush_pending=False` and publish that exact event.
3. Materialize reserved SpikeTrap conditions in deterministic content order.
4. Light placed authored WallTorches in deterministic placement order; require
   the completed light-change and exact completed IGNITE facts from each call.
5. Publish one existing floor `ItemLocationStateEvent` per successfully lit
   fixture as its complete post-light item/source after-value.
6. Return only after post-init dynamic state settles; lifecycle cancellation
   raises a post-init setup error and requires runtime reset.
7. Preserve the existing scenario Entity creation/deployment sequence.

Run the focused bootstrap chronology, cold-vs-dynamic replay, light/FOV,
condition/lever, object, connector, and scenario sensory tests. Stop before
certification if any active behavior is not represented by the cold fact plus
ordinary subsequent facts.

### Slice 5.3 — Certification candidate

No new behavior unless validation exposes a real Phase 5 defect.

1. Run every focused and affected lane in Section 8.
2. Recollect the accepted baseline plus authorized Phase 5 nodes into one
   sorted unique active node set; record count and normalized SHA-256.
3. Execute that exact node set.
4. Run compile, diff, dependency, locality, cold-boundary, scope, and hard-cut
   gates.
5. Create one exact final Phase 5 manifest containing all governed active
   production/tests and current hashes.
6. Append final validation, failures/repairs, manifest hash, node count/hash,
   and candidate status to the existing Phase 5 ledger.
7. Freeze the candidate before independent review.

Any production/test repair after candidate freeze invalidates affected
validation, the manifest, and both independent reviews.

## 8. Test and evidence plan

All tests follow `HOW_TO_TEST.MD`: public behavior first, deterministic data,
no mocking of engine internals, no assertions over private storage except an
explicit architecture/deletion gate, and no transport assertions.

### 8.1 New or strengthened public proofs

#### Catalog cold chronology

For all ten active battlefields:

- the first event emitted by that build attempt is one completed
  `WorldInitializedEvent`;
- exactly one such event is emitted;
- it contains no actor field or Entity-created/deployed fact;
- Tiles, objects, contents, and connectors are in canonical order and equal
  the exact public runtime state at the cold boundary;
- no elevation or connector lifecycle exists before or during cold
  publication; and
- every declared dynamic condition/light fact follows the world event.

The explicit Tile-identity authority gate may inspect the BaseBlock registry:
for each map, exactly 225 registered/current/world Tile UUIDs exist and the
three sets are equal. This is an architecture/ownership invariant, not a
gameplay test or permission to assert other private layouts.

Before catalog construction, prove the fresh-world admission predicate. After
one successful object-free open-floor build, call the public builder again and
prove rejection occurs before any event, UUID set, Tile/object/connector,
condition/light, or resolved-state change. This is the repeat-build failure
proof; no rollback is inferred.

#### Exact authored classification

- maps without authored dynamic state emit no post-init condition/light setup;
- the three standard-family builds create exactly one SpikeTrap with the
  reserved `environment.spike_condition_uuid` and exact authored footprint;
- the proving map creates exactly one reserved landing SpikeTrap at `(11, 9)`;
- the standard closed/open maps light exactly two placed WallTorches;
- multi-object dark lights exactly three; and
- no cold direct Tile condition or unclassified light source is admitted.

#### Cold snapshot then dynamic light replay

On a dark standard map:

- each WorldInitialized WallTorch item state is unlit;
- its runtime item is lit only after the world fact;
- the world Tile `resolved_light` map, reduced by completed post-init
  `SPATIAL_LIGHT_CHANGED.light_level_map` after-values, equals every live
  Tile's final resolved light; and
- the IGNITE interaction for each fixture follows its objective light commit
  through the existing lifecycle; and
- the later floor `ItemLocationStateEvent` carries the exact same placement
  plus complete lit `ItemState`, and the detached reducer replaces the cold
  unlit item row with this after-value before comparing source capability to
  live public item state.

#### Cold snapshot then SpatialCondition replay

Reduce completed post-init `SpatialEffectChangeEvent` facts from the empty
cold condition set. The resulting condition UUID/content identity/layer/exact
footprint must equal the live GridMap SpatialCondition state. The TrapLever's
cold `ItemState.linked_spatial_condition_uuid`, runtime action target, and
materialized condition UUID must be identical, and the lever must still
deactivate the live condition through the ordinary lifecycle.

#### Elevation and connector cold commit

Prove that authored elevation is present in each final Tile at first
publication and emits no elevation lifecycle. Using public GridMap APIs, prove
that initial connector registration while events are disabled commits its
exact state and emits no lifecycle. Existing enabled-runtime tests must
continue to prove that connector registration is guarded/vetoable and eventful
when enabled. Runtime `set_tile_elevation` semantics remain unchanged.

#### Failure

A public repeat build emits no event, leaves GridMap publication enabled, and
does not alter the complete public world/event projection because admission
rejects it before mutation. Do not monkeypatch engine internals or infer
rollback.

Separately, register an ordinary public validation handler that cancels either
the authored WallTorch's light-change lifecycle or its IGNITE lifecycle.
Prove the world fact remains completed, the cancellation is recorded, no
complete WallTorch item after-value is published for that failed fixture, and
`build_battlefield` raises instead of returning success. The resulting partial
post-init runtime is terminal and reset before the next case. This test uses
public EventQueue handler/event APIs, not a mock and not a test-only builder
injection.

#### Scenario and sensory sequence

For an assembled authored encounter:

- cold world first;
- authored SpikeTrap/light setup after world and before first Entity creation;
- Entity-created before that Entity's ENTERED lifecycle;
- each observer has exactly one initial self-movement sensory delta parented to
  its own ENTERED EFFECT before that ENTERED completion;
- applying all recorded sensory deltas to a fresh Senses projection reproduces
  the final replay-owned fields; and
- later actor/setup deltas remain ordinary and causal rather than being folded
  into bootstrap.

#### Mechanics from content-built state

Retain or strengthen public assertions for:

- pathfinding and movement across open/closed ordered boundaries;
- physical optics and FOV across both ordered Tile sides;
- WallTorch light occlusion and resolved objective light;
- propagation across doors/walls;
- SpikeTrap hazard/trigger/lever behavior;
- exact object placement, contents, open state, and boundary mechanics;
- all traversal connector kinds and endpoint support; and
- elevation proving-ground playability.

### 8.2 Focused/affected lanes

At minimum run the collecting active nodes from:

- `tests/engine/test_direct_scenario_deployment.py`;
- `tests/engine/test_elevation_proving_battlefield.py`;
- `tests/engine/test_elevation_performance_contract.py`;
- `tests/engine/test_traversal_connectors.py`;
- `tests/engine/test_world_edge_identity_and_elevation.py`;
- `tests/engine/test_spatial_effects.py`;
- `tests/engine/test_senses_light_stealth.py`;
- `tests/engine/test_objective_state.py`;
- `tests/engine/test_event_wire_visibility_contract.py`;
- `tests/engine/test_tile_surface_contract.py`;
- `tests/engine/test_items_inventory_equipment.py`;
- `tests/manual/test_72_battlefield_deployment_catalog.py`;
- `tests/manual/test_37_authored_encounter_mechanics.py`;
- `tests/manual/test_84_generic_roster_duels.py`;
- `tests/manual/test_150_prepared_scenario_lifecycle.py`;
- any other collecting active authored encounter mechanics test that consumes
  the spike UUID or WallTorch state; and
- any new dedicated authored-bootstrap behavioral module.

Do not port a blocked server/content-system/manual file merely to increase
coverage. Transplant only an active in-process capability if it has no
collecting proof.

### 8.3 Certification gates

- exact Phase 4 647-node baseline remains green;
- exact expanded Phase 5 active union collects and passes;
- changed/scoped Python compiles;
- `git diff --check` passes for scoped changes;
- final manifest membership is sorted, unique, present, and hash-exact;
- `core/events` still imports no GridMap, Entity, Senses, authored content, or
  renderer;
- GridMap imports no concrete item, Entity, or concrete SpatialCondition;
- Entity/BaseItem import no `dnd.spatial` module;
- no active server/SDK/generated/renderer/editor path is changed;
- no global EventQueue mute, deferred callback list, generic activation
  registry, compatibility alias, duplicate placement/Entity authority, or new
  replay manager exists;
- the fresh-world admission rule runs before mutation and no generic rollback
  or Tile-retirement path exists;
- cold builders emit no EventQueue fact before the world event;
- no cold builder leaves a direct Tile condition, SpatialCondition, light
  source, or Entity membership before world publication;
- dynamic condition/light work remains footprint/source local and does not
  scan every map cell except the existing bounded light geometry computation;
  and
- existing movement, optical, light, propagation, turn-start, occupancy, and
  per-step sensory gates remain green.

Repository-wide collection may be recorded diagnostically. Missing
`dnd.content_system`, `server`, circus-fighter, SDK, or transport modules remain
governed exclusions and are not repaired or counted as Phase 5 failures.

## 9. Authorized initial file envelope

The expected production envelope is:

- `dnd/core/gridmap.py`;
- `dnd/content/spike_trap_materialization.py`;
- `dnd/maps/arena_layout.py`;
- `dnd/content/scenarios/battlefield_builders.py`;
- `dnd/core/events/item_events.py`; and
- `dnd/items/environment_interactables.py`.

`dnd/content/scenarios/scenario_deployment.py`, `dnd/blocks/base_item.py`,
`dnd/items/torches.py`, and `dnd/core/events/world_events.py` require no
production change. The existing BaseItem item-state and location-state seams
are reused unchanged.

Expected active test/governance edits are limited to the files needed for the
proofs in Section 8, the new Phase 5 ledger, and the final Phase 5 manifest.

`dnd/core/events/world_events.py` may enter only if implementation proves the
active cold world still owns an unsnapshotted condition/light source after the
required separation. `dnd/items/torches.py`, `dnd/blocks/base_item.py`, or
generic EventQueue lifecycle code may enter only if the exact bounded outcome
check and existing item fact described above prove insufficient. Either case
is a coordinator stop, not unilateral permission to add schema or lifecycle
layers.

Any new production file, any excluded path, or any unplanned change to generic
EventQueue lifecycle, senses, movement, Entity occupancy, server, transport,
renderer, or SDK code is a scope stop requiring coordinator review. The single
optional `ItemState` field in this envelope is the only authorized generic
event-value change.

## 10. Reviewer instructions

Before implementation, two independent reviewers must inspect the exact plan
bytes and current accepted checkout:

1. correctness/scope reviewer: prove that every active authored objective fact
   is represented exactly once, event order and failure semantics match the
   master, all callers/tests are covered, and no Phase 5 requirement is
   deferred accidentally;
2. anti-slop/dependency reviewer: prove the plan adds only the minimum seams,
   avoids generalized deferred activation/replay/schema layers, preserves
   dependency arrows, and does not leak into excluded product surfaces.

Both must report APPROVED with the exact plan SHA-256 or list concrete
MUST-FIX findings. Any substantive plan edit invalidates both verdicts. A
status/review-record-only finalization must be rehashed and explicitly
reconfirmed by both reviewers before dispatch.

After implementation, two independent reviews bind the exact final manifest,
ledger, node-set hash, and current changed bytes:

- correctness/replay/scope; and
- anti-slop/dependency/locality.

No reviewer may approve its own implementation work.

## 11. Implementer handoff and stop rules

Luna receives only the exact double-approved plan hash and starts at Slice
5.0. Luna must checkpoint after each slice. The coordinator independently
reviews each checkpoint before authorizing the next.

Luna stops immediately if:

- a governing hash or accepted baseline differs;
- an unclassified authored condition/light/entity exists;
- an ordinary dynamic lifecycle cannot represent the required after-state;
- a production change outside Section 9 appears necessary;
- a new event/world schema or any payload beyond the authorized optional
  `ItemState` field, manager, registry, callback, or facade seems necessary;
- an excluded file appears necessary;
- validation exposes a rules decision rather than an implementation defect;
  or
- unrelated dirty work overlaps an authorized hunk.

Luna does not stop merely because tests are slow, a known excluded collection
blocker remains, or the work requires bounded mechanical test migration.

Phase 5 is complete only when the exact final candidate passes all gates, both
independent implementation reviews approve it, the final ledger/manifest are
hash-bound, and no required work remains. Phase 6 does not begin automatically.

## 12. Pre-implementation review record

The exact substantive candidate with SHA-256
`fdfb1584f166960af17f48c626bcf165a16b2436959f5ee6c65c311b649be1fe`
received both required independent verdicts on 2026-08-26:

- correctness/scope: APPROVED; and
- anti-slop/dependency: APPROVED.

Only the status line and this review record were added after those verdicts.
Both reviewers must explicitly reconfirm the final bytes before implementer
dispatch; that reconfirmation is external to this immutable authority file.
