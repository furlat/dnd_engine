# Tile surface and world-placement implementation plan — Phases 0, 1, and 2

Status: approved detailed implementation plan. Implementation has not started.
Both independent reviewers approved substantive content SHA-256
`d04e7cd6c4a9819f8dd273aefabc0f9db29877d42549be33cab1c47c2f6875bb`.

This is the execution plan for Phases 0, 1, and 2 of
`DND_TILE_WORLD_ITEM_VERTICAL_BOUNDARY_MIGRATION_PLAN_2026-08-17.md`. It does
not replace that master plan. The master remains the architectural authority;
this document fixes the implementation order, atomic cuts, caller ledgers, and
verification gates for the first three phases.

Frozen architectural prerequisites:

- master plan SHA-256:
  `01b0d5aa27b7617666d85da3e167da9d4b59d21b95f5073b41eb25821bdcde77`;
- unified optics/illumination plan SHA-256:
  `3c9c58483440640837bc38fdaa6b624f358e1098c9a957f65923cd64f83a270b`;
- testing rules: `HOW_TO_TEST.MD`, read before writing or changing tests.

## 1. Result of this implementation slice

After Phase 2:

1. every Tile has a validated semantic surface consisting of one base material
   and an ordered tuple of layers;
2. every placed object has one exact `WorldObjectPlacement` owned by GridMap;
3. each Tile privately indexes the object's center or cardinal-boundary bands;
4. GridMap owns the only reverse object-placement dictionary and every write;
5. BaseItem no longer owns a floor `tile_uuid` or floor coordinate;
6. item, world, and initialization facts carry exact placement values rather
   than reconstructing floor location from mutable objects;
7. object-attached spatial conditions, lights, destruction hooks, sensory
   evidence, and authored builders read the GridMap authority; and
8. the existing event lifecycle, sensory reducer, spatial-condition lifecycle,
   inventory/equipment behavior, and directional edge implementation remain
   the mechanisms around that new authority.

The slice establishes storage and exact facts. Structure-to-world-edge
derivation and the deletion of current directional booleans belong to Phase 3.
Entity/Tile occupancy belongs to Phase 4. Cold bootstrap completion belongs to
Phase 5. These later owners must continue to work against the Phase-2 placement
query without being pulled into this cut.

## 2. Authority and dependency constraints

| Concern | Phase-2 authority | Permitted derived reader |
|---|---|---|
| Tile surface | `Tile.surface` | rules, snapshots, content |
| Object placement specification | neutral BaseBlock capability | GridMap admission |
| Object forward membership | private Tile bands | GridMap local queries |
| Object reverse placement | `GridMap._object_placements` | items, actions, events, snapshots |
| Portable-item ownership | existing inventory/equipment owners | item location facts |
| Spatial-condition mechanics | existing `SpatialCondition` owner | Tile/GridMap UUID indexes |
| Attached light state | existing light-owning condition/item | GridMap light APIs |
| Subjective contacts | `SpatialSensesSystem`/`Senses` reducer | actions, clients |
| Directional blocking | existing Tile/object directional fields | current world-edge queries until Phase 3 |

Dependency direction:

```text
dnd/types/materials.py
  -> stdlib, pydantic

dnd/types/world_placement.py
  -> stdlib, pydantic, dnd/types/world.py, dnd/types/materials.py

dnd/core/base_tiles.py
  -> BaseBlock, BaseCondition, hot world-edge values, cold type modules

dnd/core/events/*
  -> cold core/type values

dnd/core/gridmap.py
  -> BaseBlock, BaseCondition, Tile, existing event modules, cold type modules
  -X-> Entity, concrete items, concrete SpatialCondition classes, authored content

dnd/blocks/base_item.py
  -> BaseBlock, GridMap placement/query boundary, cold types

dnd/spatial/area_conditions.py and concrete light owners
  -> GridMap queries and existing spatial events
```

No phase introduces a late import, `TYPE_CHECKING` cycle mask, `getattr`
protocol, renderer type, compatibility location property, second placement
index, or custom serializer.

## 3. Non-negotiable atomicity rule

Phase 2 is one activation cut even if its edits are prepared in several local
commits. The following cannot coexist in an accepted revision:

- active Tile bands/GridMap `_object_placements`; and
- active `_object_positions`, `_objects_by_position`, BaseItem `tile_uuid`, or
  inherited BaseBlock `position` used as floor authority.

During implementation, schema/storage code may be written before callers, but
the new path stays unreferenced until every caller category in section 8 has
been ported. The activation commit switches all writers/readers and deletes the
old authorities. There is no dual-write bridge and no compatibility facade.

## 4. Phase 0 — freeze the live contract

Phase 0 changes no production behavior. It produces checked-in ledgers or
recorded command outputs sufficient to distinguish existing failures from
migration regressions.

### 4.1 Test baseline

Before edits:

1. collect the complete Python suite;
2. store the sorted set of collecting module paths and node IDs;
3. store each blocked module's exception class, normalized terminal message,
   and first stable project frame; store a missing import root, missing symbol,
   or missing filesystem path only when that classification applies;
4. run the collecting module lane and record every failing node with its first
   stable exception signature;
5. run the focused Phase-0 capability lane listed in section 10; and
6. record wall-clock values only as diagnostics, never as the sole performance
   proof.

The post-cut comparison permits only node additions explicitly named in this
plan. It permits no deletion of a collecting behavioral test. A test can move
files while preserving the same capability, but the ledger must link the old
and new node IDs.

### 4.2 Surface-authoring ledger

Inventory every production call to `Tile(...)`, `Tile.create`,
`GridMap.create_rectangle`, the five Tile factories, and authored battlefield
or arena construction. Each row records:

- constructor/factory path;
- authored purpose;
- exact base material;
- ordered semantic layers;
- retained intrinsic mechanics and default light; and
- the behavioral tests that exercise it.

No surface is inferred from `sprite_name`, a filename, or a renderer category.
The initial active factory crosswalk is deliberately explicit:

| Factory | Surface |
|---|---|
| ordinary floor | stone base, no layers |
| dark floor | stone base, no layers; darkness remains illumination |
| solid wall Tile | stone base, no layers; solid-cell mechanics remain intrinsic |
| water | water base, no layers |
| difficult terrain | earth base, no layers |

Every authored constructor that means something else must state that meaning
directly. Raw test Tiles use an explicit test-appropriate surface rather than a
production default.

### 4.3 Object-location caller ledger

The ledger is grouped by capability, not merely by matching symbol names:

| Capability | Required production owners/callers to inspect |
|---|---|
| flat GridMap storage and commands | `dnd/core/gridmap.py` |
| neutral coordinate hooks/evidence | `dnd/core/base_block.py` |
| BaseItem placement, destruction, equip | `dnd/blocks/base_item.py` |
| inventory snapshots and rollback | `dnd/blocks/inventory.py` |
| entity loot/drop/equipment displacement | `dnd/entities/entity.py` |
| item-location wire facts | `dnd/core/events/item_events.py` |
| spatial object facts and initialization snapshots | `dnd/core/events/world_events.py` |
| object-anchored condition relocation/removal | `dnd/spatial/area_conditions.py` |
| object perceivability candidate selection | `dnd/blocks/sensory.py` |
| Continual Flame object anchor/light | `dnd/spells/evocation.py` |
| mounted torch placement/light | `dnd/items/torches.py` |
| chest destruction and content spill | `dnd/items/environment_interactables.py` |
| OilBarrel destruction position | `dnd/items/environment_content.py` |
| Heroes' Feast runtime floor placement | `dnd/spells/conjuration.py` |
| actions and environment objects | `dnd/actions/standard.py`, `dnd/items/environment.py` |
| authored map build and compatibility | `dnd/content/scenarios/battlefield_builders.py`, `dnd/content/scenarios/scenario_compatibility.py`, `dnd/maps/arena_layout.py` |
| runtime clearing | `dnd/runtime_reset.py` and `GridMap.clear/reset` |

The implementation must rerun repository-wide searches for these families at
the beginning and end of Phase 2. The table is a minimum capability ledger,
not permission to ignore additional discovered callers.

### 4.4 Event-order baselines

Capture public event traces for:

- place, true remove, relocate, and same-XY state/orientation change;
- floor to inventory, inventory to floor, floor to equipment, item destruction,
  and container destruction/spill;
- an object-anchored SpatialCondition relocation and true removal;
- a lit wall-mounted object relocation and true removal;
- world initialization containing floor objects; and
- an object's perceivability change while placed.

The trace records event type, phase, parent UUID, position fields, item
location, and relevant sensory child facts. It does not assert private method
names or internal dictionary layout.

### 4.5 Phase-0 exit gate

Phase 0 is complete when the surface crosswalk, caller ledger, test baseline,
blocked-module signatures, and event traces are reviewable. Any unclassified
production floor-coordinate reader blocks Phase 2.

## 5. Phase 1 — cold surface and placement values

Phase 1 lands dependency-leaf vocabulary and makes Tile surfaces explicit.
It does not activate band placement.

### 5.1 Files and values

Add `dnd/types/materials.py`:

- `Material(StrEnum)` with the master-plan initial values;
- frozen, `extra="forbid"` Pydantic `SurfaceLayer`;
- frozen, `extra="forbid"` Pydantic `TileSurface`.

Add `dnd/types/world_placement.py`:

- `WorldPlacementKind`;
- `WorldPlacementSpec`;
- `WorldObjectPlacement`;
- `BoundaryStructureKind`; and
- `BoundaryStructure`.

All persisted/authored/event values are Pydantic. `StrictInt` coordinates and
height fields reject booleans, floats, strings, and coercion. Models reject
unknown fields. `WorldObjectPlacement` validates center/boundary shape and
`top_height_steps > base_height_steps`; provider-specific extent equality is
validated by GridMap in Phase 2 because the value alone does not own the
provider.

Boundary values land because they are part of the frozen semantic contract,
but no world-edge consumer switches to them until Phase 3.

### 5.2 Tile surface cut

`Tile` gains required `surface: TileSurface`. In the same cut:

1. every production Tile constructor and factory supplies it;
2. `GridMap.create_rectangle` accepts an explicit surface and passes it to each
   created Tile;
3. authored battlefield/arena definitions provide exact surfaces from the
   Phase-0 ledger;
4. test fixtures provide explicit surfaces; and
5. no default is added to hide an unported constructor.

`sprite_name` may remain temporarily for existing client-facing code, but it
does not populate or override the surface. Phase 1 adds no renderer field to a
new value.

### 5.3 Surface mutation and facts

Add one GridMap command that replaces the `TileSurface` on the existing Tile.
It validates before mutation, preserves Tile UUID and all existing Tile-owned
state, invalidates only rules that explicitly depend on material/surface, and
publishes the existing Tile-change lifecycle with the complete `tile_surface`
after-value.

Extend existing cold/event contracts:

- `WorldTileState.surface: TileSurface` is required;
- `SpatialChangeEvent.tile_surface: TileSurface | None` is populated on a
  surface change.

There is no live objective world reducer to extend in this cut. The completed
Pydantic after-value and cold snapshot must be sufficient for a future reducer
to replace the surface directly, but Phase 1 does not restore deprecated/server
reducers or create a new reducer framework.

Wet, fire, ice mechanics, fog, and darkness remain independent
SpatialConditions or illumination state. Phase 1 does not copy them into
`TileSurface`.

### 5.4 Phase-1 tests

Behavioral tests prove:

- deterministic Pydantic round trip and JSON schema;
- strict coordinate/height rejection, including `True` as invalid integer;
- ordered layers preserve order and repeated materials;
- every active factory produces its ledgered surface;
- runtime replacement preserves Tile identity, direct conditions,
  SpatialCondition references, and illumination;
- a completed Tile-change fact contains the exact after-value, round-trips, and
  is sufficient for a pure reference fold to replace the surface without a
  live Tile or registry lookup;
- temporary wet/darkness state does not mutate the surface; and
- no dependency-leaf module imports gameplay, content, or renderer modules.

Phase 1 is its own rollback unit: types, constructor ports, surface command,
event-contract changes, and tests revert together.

## 6. Phase 2 — Tile/GridMap object-placement authority

Phase 2 prepares its pieces in the order below but activates them atomically as
required by section 3.

### 6.1 Neutral provider capability

Add to `BaseBlock` one explicit method:

```python
def get_world_placement_spec(self) -> WorldPlacementSpec:
    return WorldPlacementSpec(
        kind=WorldPlacementKind.CENTER,
        occupies_bands=False,
        vertical_extent_steps=1,
    )
```

This supports current generic objects and dropped items without type checks.
Concrete boundary/occupying policies activate in Phase 3. Phase 2 does not
create a class registry, decorator, dynamic protocol, or placement subclass
hierarchy.

Promote the already-existing BaseItem position query shape to one neutral
BaseBlock query:

```python
def get_position(self) -> tuple[int, int] | None:
    return self.position
```

`BaseItem` overrides it: an owned item calls its owner's neutral position query,
a floor item resolves `GridMap.get_object_placement(self.uuid).position`, and
an unowned/unplaced item returns `None`. BaseBlock's existing perceivability
publisher calls this virtual query and emits no spatial fact when it returns
`None`. This keeps BaseBlock free of a GridMap import and leaves Entity's
objective coordinate unchanged.

### 6.2 Private Tile bands

Add the internal frozen slot dataclass `TileObjectBand` beside Tile. Tile owns:

- `_center_object_bands: dict[int, TileObjectBand]`;
- `_boundary_object_bands: dict[CardinalDirection, dict[int, TileObjectBand]]`.

Both are `PrivateAttr`; all four boundary dictionaries are initialized. GridMap
replaces complete immutable band values. Tile exposes only frozen/copy query
results. No caller can mutate membership directly.

Do not add `_entity_uuids` in this phase; Entity occupancy is Phase 4.

### 6.3 GridMap command and query semantics

Replace the two flat object dictionaries with exactly:

```python
_object_placements: dict[UUID, WorldObjectPlacement]
```

The command family is:

- `place_object`: only for an unplaced object; identical replay is idempotent;
- `move_object`: only for an already placed object; validates the entire
  destination before altering the origin;
- `orient_object`: changes orientation in place after validation;
- `remove_object`: terminally unplaces one object;
- `get_object_placement`;
- `get_object_position`, a permanent derived convenience;
- local center/boundary/edge queries; and
- a frozen placement iterator for snapshots and validation.

The provider decides kind, occupancy, and extent. The caller selects the Tile,
boundary side when required, optional explicit base height, and orientation.
Default base height is Tile support height. Placement fails before mutation for
missing Tiles, shape mismatch, strict-value errors, local occupant overlap, or
opposite-side occupant overlap.

`get_objects_at(position)` reads only that Tile's bands and deduplicates UUIDs.
No global scan or second position cache is added.

### 6.4 Mutation algorithm

For place/move/orient:

1. resolve registered BaseBlock and its spec;
2. build the complete candidate placement;
3. validate candidate bands and opposite boundary locally;
4. snapshot only the previous placement and touched immutable band values;
5. replace touched Tile band values and reverse placement;
6. if an unexpected mutation failure occurs, restore those local values before
   publication;
7. invalidate existing channel revisions required by the old/new provider
   mechanics; and
8. publish through the existing spatial lifecycle.

No general receipt type or EventQueue transaction is introduced. A move does
not call terminal removal cleanup between its departure and arrival. Each
placement command performs its complete admission before its own mutation and
publication.

GridMap also exposes `validate_object_placement(...) -> WorldObjectPlacement`,
a read-only call to the exact candidate builder/admission logic used by the
commit commands. It does not reserve bands, cache a result, publish, or weaken
commit-time revalidation. Its purpose is to let an owner prove a floor fallback
before another domain publishes an irreversible transition.

### 6.5 Exact spatial facts

Extend `SpatialChangeEvent` with:

```python
placement: WorldObjectPlacement | None = None
previous_placement: WorldObjectPlacement | None = None
```

Use this table:

| Operation fact | `position` | `old_position` | `previous_placement` | `placement` |
|---|---|---|---|---|
| first placement | new XY | `None` | `None` | new |
| relocation departure | old XY | destination XY | old | `None` |
| relocation arrival | new XY | old XY | old | new |
| orientation/state change | current XY | current XY or `None` per existing factory | old | new/current |
| terminal removal | old XY | `None` | old | `None` |

Preserve the existing full spatial lifecycle and `SensesUpdateHint` behavior.
Do not add an event type or publisher family. Remove `object_map_char` from the
object spatial payload once placement/item semantics cover the active wire;
the underlying legacy visual fields may remain for the later content/client
cut and are not placement authority.

Pydantic validators require every nested placement's `object_uuid` to equal
the enclosing `SpatialChangeEvent.object_uuid`. The event's affected-position
query includes the coordinates of both exact placements when present.

Object relocation keeps both existing topology/light steps while avoiding a
subjective projection of a half-settled move:

1. departure publishes the old placement and retains its ordinary old-position
   topology/light hint, but `SpatialSensesSystem` explicitly skips subjective
   reduction when an object-removal fact carries a destination;
2. arrival publishes the new placement and recomputes destination topology;
3. arrival EFFECT handlers relocate object-anchored SpatialConditions;
4. a condition such as Continual Flame settles its condition-owned footprint
   and light before publishing its completed footprint-change fact; and
5. at arrival pre-completion the existing attached-light callback moves any
   remaining source whose stored light position is not already the destination,
   publishes its ordinary child light facts, and then the indexed sensory
   system reduces once using the event's old/new affected-position union.

The exact old/new placement fields make both steps self-contained. This does
not add an EventQueue API, batch settlement, or second callback family.

### 6.6 Item location facts

Replace FLOOR `tile_uuid` and `position` on `ItemLocationStateEvent` with:

```python
world_placement: WorldObjectPlacement | None
```

Validation requires a placement exactly for FLOOR and forbids it for other
locations. Inventory/equipment/container/destroyed fields retain their current
meaning and order. Producers capture the committed placement from GridMap;
consumers and replay never query the mutable item to reconstruct it.

Model validators also require
`item_state.item_uuid == world_placement.object_uuid` for FLOOR facts and
`item.item_uuid == placement.object_uuid` for `WorldObjectState`. Mismatched
identities are rejected before publication or bootstrap serialization.

`WorldObjectState` similarly stores exact `placement` plus `ItemState` and
contained item states. `WorldInitializedEvent` otherwise retains its current
bootstrap role; its broader completion is Phase 5.

### 6.7 BaseItem and inventory hard cut

Delete BaseItem `tile_uuid` and stop treating inherited `position` as floor
authority. Migrate:

- `BaseItem.get_position` to owner position or GridMap placement position;
- floor placement/removal/destruction;
- equip cleanup;
- inventory add/remove/stack rollback snapshots;
- Entity loot/drop/equipment displacement; and
- all FLOOR item-location publications.

An ordinary inventory drop validates the exact GridMap candidate before
detaching the item and retains its existing local snapshot until the physical
commit succeeds. Equipment exposes one pure derived conflict query returning
the selected slot and current displaced-item tuple; it does not expose its
private prepared transitions. Entity validates every possible floor fallback
at its current valid Tile before calling `equip_transaction` or `unequip`.
Equipment then uses its existing validation-only preflight before publishing,
and both domains retain their existing commit paths. GridMap revalidates when
the later floor placement commits.

The single-process cut relies on the existing validation-only rule: Equipment
preflight cannot publish or mutate objective world state between floor
admission and its preflighted transition publication. Ordinary drop restores
its local snapshot on rejection before any success fact. No new equipment
event, public prepared-transition type, reservation, receipt, or transaction
framework is added. Preserve current inventory, equipment, stack, charge, and
destruction event families.

Every runtime BaseItem floor entry publishes exactly one existing
`ItemLocationStateEvent` with `location=FLOOR` and the committed placement.
This includes ordinary drops/equipment displacement, Heroes' Feast, and chest
spill. Event-disabled cold map construction remains represented only by its
`WorldInitializedEvent`; its builders use the physical GridMap boundary and do
not pretend bootstrap placement was a runtime item transition.

The obsolete `clear_location`/`clear_object_location` switch is deleted because
there is no longer an item-side floor location to protect. True removal/clear
invokes the existing object cleanup hook once with terminal meaning; relocation
does not pretend the object was destroyed.

### 6.8 Attached consumers

All coordinate consumers move before old authority is deleted:

1. Object-anchored SpatialCondition handlers use the exact departure/arrival
   placement facts. A departure with a destination is relocation; a departure
   without one is true removal and follows the existing deactivation and
   concentration unlink lifecycle. Same-XY changes do not relocate.
2. Continual Flame and WallTorch resolve their coordinate from GridMap.
   WallTorch deletes `_wall_torch_position`, creates its existing light with
   `anchor_uuid=self.uuid`, and uses placement for ignite facts. The existing
   GridMap attached-light pre-completion callback expands from Entity arrival
   to object arrival and moves only attached sources whose stored position is
   not already the destination. Continual Flame retains its condition-owned
   footprint and direct light move before its completed footprint fact; the
   callback therefore observes it already settled and does not move it twice.
   WallTorch's narrow terminal-removal hook calls its existing extinguish
   cleanup once; no new light owner or callback family is added.
3. `StorageChest` captures its committed placement before terminal removal and
   uses that coordinate for existing spill behavior. OilBarrel resolves its
   destruction position through the same BaseItem query.
4. BaseBlock perceivability/evidence publication uses the neutral `get_position`
   query; the BaseItem override resolves GridMap placement while Entity keeps
   its objective coordinate. `SpatialSensesSystem.candidate_observer_uuids`
   deletes its later `BaseBlock.position` fallback and relies on the exact
   perceivability-event position plus its existing reverse observer indexes.
   `SpatialSensesSystem` remains the only subjective reducer.
5. battlefield snapshots, scenario compatibility, actions, and environment
   objects use placement queries or exact event values.

No attached-object UUID index, anchor receipt, callback framework, or new light
lifecycle is added.

### 6.9 Clear, Tile replacement, and rebuild

`GridMap.clear()` runs each placed object's existing terminal cleanup exactly
once, then clears forward bands and reverse placements. It rejects deployed
entities and live direct/independent conditions before mutation; it preserves
the current owned light teardown rather than silently orphaning a source.

A support-height change validates every existing local placement against the
candidate Tile support and rejects before mutation if any placement would stop
satisfying its admission rules. A full Tile replacement/removal or rectangle
overwrite rejects a Tile with entity occupancy in the current Phase-2 index,
object bands, direct conditions, SpatialCondition references, connector
endpoints, or live illumination contributions. Surface replacement remains
in-place and allowed. These are guards over existing owners; Phase 2 does not
migrate Entity, condition, connector, or light ownership.

Serialized `WorldObjectPlacement` values are load authority. Rebuild validates
providers and constructs bands plus reverse placements together. It then scans
the two directions to prove bijection. Bands are never used to guess
orientation, occupancy, or missing placement values, and ambiguity is never
auto-repaired.

## 7. Phase-2 activation and deletion checklist

The activation commit is incomplete until repository-wide searches prove:

- no `_object_positions` or `_objects_by_position`;
- no BaseItem `tile_uuid` field or assignment;
- no floor caller reads inherited object `position`;
- no object-owned auxiliary floor coordinate such as `_wall_torch_position`;
- no `clear_object_location` or `clear_location` placement switch;
- no FLOOR item fact with separate `tile_uuid`/`position`;
- no object snapshot containing only XY without exact placement;
- no direct mutation of Tile band storage;
- no implicit move through `place_object`; and
- no `object_map_char` in the authoritative spatial wire.

Current directional Tile/object booleans and structure projection remain until
Phase 3 and are not included in this deletion list.

## 8. Mandatory caller disposition

Every Phase-0 discovered caller gets one of these recorded outcomes:

| Current use | Phase-2 replacement |
|---|---|
| position of one object | `get_object_placement` or derived `get_object_position` |
| all objects at XY | Tile-band-backed `get_objects_at` |
| all placed objects | frozen placement iterator |
| item floor state | `ItemLocationStateEvent.world_placement` |
| bootstrap floor object | `WorldObjectState.placement` |
| object anchor transition | exact `SpatialChangeEvent` placements |
| attached light coordinate | GridMap placement query/event |
| destruction spill coordinate | pre-removal placement snapshot |
| runtime item floor entry | physical GridMap commit followed by one FLOOR item fact |
| authored placement | single GridMap command family |
| legacy directional mechanics | preserved until Phase 3 |

An unclassified caller is a stop condition, not justification for a facade.

## 9. Verification strategy

Tests follow `HOW_TO_TEST.MD`: use public commands/events/replay and observable
state; do not inspect private dictionaries, monkeypatch internals to prove
behavior, or assert source layout.

### 9.1 Placement behavior

Add focused tests for:

- strict placement validation;
- center and each cardinal boundary membership through public queries;
- nonoccupying coexistence and occupying collision;
- opposite-side boundary collision;
- move preflight leaving origin unchanged on rejection;
- failed drop/equipment displacement restoring owner, slot, item, GridMap, and
  event state exactly;
- idempotent identical placement;
- same-XY orientation change;
- terminal remove and clear cleanup;
- exact event table in section 6.5;
- rejection of mismatched outer/item/placement UUIDs;
- exact cold snapshot and Pydantic round trip; and
- rebuild success plus rejection of malformed/ambiguous values.

### 9.2 Preserved domain behavior

Retain or recover tests for:

- loot, drop, equip, unequip, stack, destroy, and container spill;
- WallTorch lit/unlit move and true removal;
- Continual Flame object move and true removal;
- concentration unlink after anchored condition retirement;
- object perceivability and sensory contact updates;
- current directional wall/door blocking before Phase 3; and
- world initialization containing the same semantic item state at the exact
  placement.

### 9.3 Event and replay behavior

Assert public serialized models and replay-sufficient state:

- placement/surface after-values are sufficient for a pure reference fold
  without live-object lookup;
- FLOOR item facts are exact and non-floor facts reject placement;
- relocation has one departure and one arrival under the same causal parent;
- attached light/spatial-condition children occur through existing lifecycle
  boundaries;
- generic wire projection still excludes observer-only grants as established
  by the unified vision cut; and
- no EventQueue, base Event, combat-log fold, or controller contract changes.

### 9.4 Dependency behavior

AST dependency gates assert the arrows in section 2, including:

- type leaves import no gameplay/content/render modules;
- GridMap imports no Entity, concrete item, or concrete SpatialCondition;
- BaseItem/Entity do not import concrete spatial owners to coordinate anchors;
- authored content cannot mutate Tile bands; and
- no late/dynamic import or `TYPE_CHECKING` cycle mask is introduced.

## 10. Focused baseline and execution lanes

Phase 0 resolves exact selectors from the current collecting set. At minimum,
the lanes cover:

- grid/path/world-edge behavior;
- item inventory/equipment/action-discovery behavior;
- spatial effects and object-anchor behavior;
- sensory/light/stealth behavior;
- objective event lifecycle and wire projection;
- authored battlefield construction and world initialization;
- runtime reset/clear; and
- existing elevation and spatial-condition performance contracts.

The implementation ledger records exact module paths because the currently
blocked suite is still being migrated. The final validation runs:

1. all focused lanes after each atomic phase;
2. the complete pre-edit collecting module lane;
3. full collection with blocked signatures compared; and
4. the complete collecting suite when affordable, with any unrelated retained
   failures reported rather than hidden.

## 11. Locality and performance gates

Correctness requires work proportional to the changed placement and used
space, not total map area.

GridMap exposes one intentionally diagnostic, read-only snapshot of the most
recent placement/query operation. It reports operation name, Tiles inspected,
bands inspected, bands replaced, and placement-iterator rows visited. The
snapshot is a frozen slots record, is reset at the start of the next measured
operation, and never participates in validation, mutation, events, caching, or
serialization. It is not an index, receipt, or alternate authority.

Deterministic gates combine that diagnostic snapshot with exact command/event
facts:

- placement and event footprints name only the owner/neighbor cells and
  `[base_height_steps, top_height_steps)` bands implicated by the operation;
- diagnostic Tile/band counts are invariant under adding distant unused Tiles;
- relocation diagnostics and facts name only old/new local placements;
- placement-iterator visits equal returned placed objects, not total map area;
  and
- existing sensory/light candidate selection remains indexed and event-driven.

Supplementary timing tests follow the existing spatial-condition pattern:

- run the same fixed number and shape of object operations in a small and much
  larger mostly unused map;
- use medians over repeated runs;
- require a generous upper bound and bounded large/small ratio; and
- pair timing with the structured footprint/locality assertions so a
  fast machine cannot hide a map-wide scan.

No performance-only cache or diagnostic index is added.

## 12. Stop, rollback, and review rules

Stop the phase when:

- a new cycle appears;
- a floor-coordinate consumer cannot be ported without another domain rewrite;
- existing event ordering cannot be preserved through the current lifecycle;
- a new global scan is required;
- an unclassified authored surface or placement is encountered; or
- the pre-edit collecting set loses an unapproved capability.

Rollback units:

- Phase 1: types + all Tile constructors + surface event-contract changes;
- Phase 2: bands + GridMap placement + every caller/event/snapshot port + all
  old-authority deletions.

Do not retain partial compatibility code after rollback.

## 13. Exact completion gate

Phases 0–2 are complete only when:

1. the ledgers and baseline are frozen;
2. every Tile constructor supplies an explicit semantic surface;
3. surface change and cold snapshot round-trip exact replay-sufficient values;
4. Tile private bands and one GridMap reverse placement are bijective;
5. every object writer uses the single GridMap command family;
6. every object-location consumer reads placement authority or exact facts;
7. BaseItem has no floor location authority;
8. item/world events carry exact placement values;
9. anchored conditions, lights, spills, senses, and bootstrap behavior remain
   covered at public boundaries;
10. placement work scales with occupied bands/placed objects, not unused area;
11. current directional mechanics still pass, ready for Phase 3;
12. no EventQueue, reducer, inventory/equipment, or controller framework was
    introduced; and
13. both reviewers approve the exact implementation diff and test manifest.

## 14. Plan review record

| Role | Revision | Verdict |
|---|---|---|
| dependency/executability reviewer | `d04e7cd6c4a9819f8dd273aefabc0f9db29877d42549be33cab1c47c2f6875bb` | APPROVED |
| event/lifecycle and anti-slop reviewer | `d04e7cd6c4a9819f8dd273aefabc0f9db29877d42549be33cab1c47c2f6875bb` | APPROVED |

Implementation begins only after both rows bind to one SHA-256 with verdict
`APPROVED`; only then is this plan submitted to the Luna implementation task.

## Historical correction notice — appended 2026-08-24

The accepted pre-correction implementation was bound to manifest
`34de6db66c80d336044ab90abd13e284971722551d4d2018678a12808971aad9` and
contained the wrong reciprocal collision authority and preliminary merged edge
view. The reviewed correction is governed by correction plan
`ae189282687fdcb7baa88ca3b393af593c6db345029a89da9cfcc36b76f021c1`, its
companion ledger
`DND_TILE_WORLD_ITEM_PHASES_0_1_2_SIDE_GEOMETRY_CORRECTION_LEDGER_2026-08-24.md`,
and reviewed implementation manifest
`DND_TILE_WORLD_ITEM_PHASES_0_1_2_IMPLEMENTATION_MANIFEST_2026-08-23.json`
at SHA-256
`3eb3b75864cda77052675e93b82f43bdf89c5177930a4fa4518db3884900d98c`.
Phase 3 must use the correction state, not the pre-correction implementation.
