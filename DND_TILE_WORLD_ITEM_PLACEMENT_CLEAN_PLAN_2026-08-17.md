# Tile, world-item, and entity-position clean migration plan

Status: approved by two independent reviewers and a three-way anti-slop audit.

Date: 2026-08-17

The detailed source record remains in
`DND_TILE_WORLD_ITEM_VERTICAL_BOUNDARY_MIGRATION_PLAN_2026-08-17.md`.
This document names the implementation surface selected from that study.

## 1. Outcome

The migration establishes one `GridMap` with one playable `Tile` at each XY,
typed semantic surfaces, Tile-owned center and boundary object placement,
integer vertical bands, exact world-edge derivation, and exact placement facts
in the existing event stream.

Entity instances retain their direct position. GridMap retains its UUID-based
occupancy indexes. One Entity-owned write path synchronizes the two stores.
Temporary spatial suspension becomes a named Entity capability used by
Banishment while Game ownership and the live Entity remain intact.

The result supports authored ground, surface cover, walls, doors, cliffs,
boundary attachments, ordinary floor items, entity movement, and temporary
removal from spatial play.

## 2. Dependency and ownership map

Arrows point from importer to imported dependency. Reverse arrows identify the
principal consumers.

```text
dnd/types/materials.py
  [-> enum, pydantic]
  [<- base_tiles, world_items, world events, authored map content]
  MaterialKind
  SurfaceCoverKind
  BoundaryStructureKind
  TileSurfaceState

dnd/types/world.py
  [-> enum, pydantic, UUID, dnd/types/materials.py]
  [<- base_block, base_tiles, base_item, world_items, gridmap, world events]
  existing CardinalDirection and WorldEdgeChannel
  WorldPlacementKind
  WorldPlacementPolicy
  WorldObjectPlacement
  BoundaryStructureState

dnd/types/items.py
  [-> pydantic, dnd/types/world.py]
  [<- BaseItem, item events, senses/reducers]
  existing ItemObservationState vocabulary migrated to BoundaryStructureState

dnd/core/base_block.py
  [-> dnd/types/world.py]
  [<- Tile, BaseItem, GridMap]
  neutral typed world-placement and boundary-structure capabilities

dnd/core/base_tiles.py
  [-> base_block, dnd/types/materials.py, dnd/types/world.py]
  [<- GridMap, world events, authored map builders]
  TileSurfaceState
  TileObjectBand
  Tile center/boundary band storage

dnd/blocks/base_item.py
  [-> base_block, dnd/types/world.py, existing item events]
  [<- portable items, usable items, equipment, world_items]
  ordinary floor-item placement through GridMap

dnd/blocks/world_items.py
  [-> base_item, dnd/types/materials.py, dnd/types/world.py]
  [<- environment items and authored map content]
  WorldItem
  BoundaryStructureItem

dnd/items/environment.py
  [-> world_items, existing actions, existing light machinery]
  [<- authored map content]
  BoundaryWall
  BoundaryDoor
  CliffFace

dnd/items/torches.py
  [-> UsableItem, existing light machinery, dnd/types/world.py]
  [<- authored item/map content]
  WallTorch boundary placement capability

dnd/core/world_edges.py
  [-> dnd/types/world.py]
  [<- GridMap path, sight, light, and propagation queries]
  canonical adjacent-edge identity and structural contribution values

dnd/core/gridmap.py
  [-> Tile, BaseBlock, world edges, world events, dnd/types/world.py]
  [<- Entity, actions, items, spatial systems, content builders]
  object placement mutation boundary
  entity UUID occupancy indexes
  exact spatial publication

dnd/entities/entity.py
  [-> GridMap public entity APIs, existing sensory system]
  [<- Game, Encounter, actions, spells]
  direct Entity.position
  one synchronized movement path
  spatial suspension and restoration

dnd/game.py
  [-> Entity]
  [<- future in-process game bootstrap]
  Entity ownership and terminal deployment lifecycle

dnd/core/events/world_events.py
  [-> event registry, cold world/material types]
  [<- GridMap, reducers, combat log, subjective projection]
  existing SpatialChangeEvent with exact placement payloads
  existing WorldInitialized snapshot with exact world state

dnd/core/events/item_events.py
  [-> event registry, cold item/world/material types]
  [<- BaseItem, inventory, equipment, reducers]
  existing ItemState with boundary structure state
  existing ItemLocationStateEvent with exact world placement
```

## 3. Semantic surface contracts

Create `dnd/types/materials.py` with frozen Pydantic values and enums.

```python
class MaterialKind(StrEnum):
    EARTH = "earth"
    SAND = "sand"
    ROCK = "rock"
    DRESSED_STONE = "dressed_stone"
    WOOD = "wood"
    WATER = "water"


class SurfaceCoverKind(StrEnum):
    GRASS = "grass"
    WOOD_FLOOR = "wood_floor"
    STONE_FLOOR = "stone_floor"


class BoundaryStructureKind(StrEnum):
    CLIFF = "cliff"
    WALL = "wall"
    DOOR = "door"


class TileSurfaceState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    substrate: MaterialKind
    cover: SurfaceCoverKind | None = None
    description: str = ""
```

`substrate` is the supporting material. `cover` is the mechanically distinct
top layer. Grass over earth and wooden flooring over stone therefore remain
separate authored facts and can later react independently.

`Tile.height` remains the support elevation in the engine's current integer
five-foot steps. One playable support surface exists at each XY.

## 4. Placement contracts

Add these frozen Pydantic values to `dnd/types/world.py` beside the current
cardinal-direction and world-edge-channel vocabulary.

```python
class WorldPlacementKind(StrEnum):
    CENTER = "center"
    BOUNDARY = "boundary"


class WorldPlacementPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: WorldPlacementKind
    occupies_bands: bool
    vertical_extent_steps: int = Field(ge=1)


class WorldObjectPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    object_uuid: UUID
    tile_uuid: UUID
    position: tuple[int, int]
    occupies_bands: bool
    boundary_direction: CardinalDirection | None = None
    base_height_steps: int
    top_height_steps: int
    orientation: CardinalDirection | None = None


class BoundaryStructureState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: BoundaryStructureKind
    material: MaterialKind
    blocked_channels: tuple[WorldEdgeChannel, ...] = ()
```

The cold values validate their intrinsic shape:

1. `top_height_steps` is greater than `base_height_steps`; and
2. the structure state carries typed kind, material, and current channels.

GridMap resolves the complete placement against the live Tile and provider. It
validates that the height interval equals the provider policy's extent, that a
center placement begins at `Tile.height`, and that a boundary placement uses a
complete integer interval. An omitted `base_height_steps` resolves to
`Tile.height`. An authored boundary may supply any explicit integer base;
GridMap derives `top_height_steps = base_height_steps + vertical_extent_steps`
and validates band collisions. A cliff rising to the support surface supplies
`base_height_steps = Tile.height - vertical_extent_steps`. GridMap resolves
omitted boundary orientation to the selected boundary direction.

Provider policy supplies center/boundary kind during validation. Center policy
requires an empty `boundary_direction`; boundary policy requires one cardinal
side. The committed placement is a boundary placement exactly when
`boundary_direction` is present.

Boundary direction chooses the Tile side. Orientation chooses the direction
the object faces. Center objects may carry orientation. Every boundary
placement supplies exactly one `boundary_direction`; the provider/factory owns
placement policy and extent while the authored placement owns side, base, and
orientation.

## 5. Typed placement capabilities

Add two polymorphic methods to `BaseBlock`:

```python
def get_world_placement_policy(self) -> WorldPlacementPolicy:
    return WorldPlacementPolicy(
        kind=WorldPlacementKind.CENTER,
        occupies_bands=False,
        vertical_extent_steps=1,
    )


def get_boundary_structure_state(self) -> BoundaryStructureState | None:
    return None
```

The neutral policy preserves ordinary dropped `BaseItem` objects as
nonoccupying center placements.

Create the active structural hierarchy in `dnd/blocks/world_items.py`:

```text
BaseBlock
  BaseItem
    portable and equipment items
    UsableItem
      BoundaryDoor
      WallTorch
    WorldItem
      BoundaryStructureItem
        BoundaryWall
        CliffFace
```

`WorldItem` owns fixed placement-policy fields. `BoundaryStructureItem` owns:

- `structure_kind: BoundaryStructureKind`;
- `material: MaterialKind`;
- `vertical_extent_steps: int`;
- `blocked_channels_closed: tuple[WorldEdgeChannel, ...]`; and
- its current mechanical open/closed state where applicable.

Its boundary-state capability returns the current kind, material, and blocked
channels. `BoundaryDoor` implements the same neutral capability directly.

`BoundaryDoor` remains a direct `UsableItem` so current action discovery and
execution continue to recognize it. It owns the same structure kind, material,
extent, and closed-channel fields, overrides the boundary placement and
boundary-state capability methods, and changes its blocked-channel result when opened or
closed. Its placement remains stable.

`WallTorch` preserves its usable behavior and overrides the typed placement
policy as a nonoccupying boundary attachment. Its light anchor reads the
current placement through GridMap.

The concrete defaults preserve the current interaction surface:

| Class | Default material | Pickable | Usable discovery | Scalar cell blocking | Senses/object actions |
|---|---|---:|---:|---:|---|
| `BoundaryWall` | `DRESSED_STONE` | false | false | false | hidden from ordinary object/action discovery |
| `CliffFace` | `ROCK` | false | false | false | hidden from ordinary object/action discovery |
| `BoundaryDoor` | `WOOD` | false | true | false | visible in senses and available object actions |
| `WallTorch` | attachment state | false | true | false | retains current usable/light discovery |

Boundary bands and `BoundaryStructureState.blocked_channels` own edge blocking
for walls, cliffs, and doors. Their scalar BaseItem walking/vision flags remain
clear, preserving traversal through the Tile center.

## 6. Tile forward storage

Add this Pydantic model to `dnd/core/base_tiles.py`:

```python
class TileObjectBand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objects: set[UUID] = Field(default_factory=set)
    occupant_uuid: UUID | None = None
```

Add these fields to `Tile`:

```python
surface: TileSurfaceState
center_object_bands: dict[int, TileObjectBand]
boundary_object_bands: dict[
    CardinalDirection,
    dict[int, TileObjectBand],
]
```

Every integer band key represents `[z, z + 1)`. An object placed at `[0, 2)`
appears in bands `0` and `1`. Each occurrence carries the same resolved
UUID membership. An occupying object is also recorded as `occupant_uuid` in
every covered band. Attachments share those bands through the `objects` set.
Orientation is read from the single reverse `WorldObjectPlacement`.

The four boundary dictionaries are always present. Empty band rows are removed
after object removal.

Tile storage and the GridMap reverse placement satisfy these invariants:

1. each placed object has one `WorldObjectPlacement`;
2. its UUID occurs in every covered band at the recorded center or boundary;
3. its UUID occurs in the corresponding bands of one Tile;
4. occupying objects own `occupant_uuid` in every covered band;
5. each band has at most one occupying object;
6. attachments may share a band with its occupying structure; and
7. opposite sides of one physical edge are checked together during placement.

## 7. GridMap object APIs

Replace the flat object indexes with:

```python
_object_placements: dict[UUID, WorldObjectPlacement]
```

`get_objects_at(position)` unions the local Tile's center and boundary bands.
`get_object_placement(object_uuid)` returns the reverse placement value.

`BaseItem.place_on_grid` remains the canonical object-placement boundary and
becomes:

```python
def place_on_grid(
    self,
    position: tuple[int, int],
    *,
    boundary_direction: CardinalDirection | None = None,
    base_height_steps: int | None = None,
    orientation: CardinalDirection | None = None,
    parent_event: UUID | None = None,
) -> WorldObjectPlacement: ...
```

It forwards the complete request once to `GridMap.place_object`, returns the
committed placement, and leaves final item-location publication with the
existing inventory, equipment, Entity, and destruction transaction owners.
Structural items, WallTorch, and authored builders use this method. Bootstrap
placements are represented by the final `WorldInitializedEvent`.

The public validation and mutation surface is:

```python
def validate_object_placement(
    self,
    object_uuid: UUID,
    position: tuple[int, int],
    *,
    boundary_direction: CardinalDirection | None = None,
    base_height_steps: int | None = None,
    orientation: CardinalDirection | None = None,
) -> WorldObjectPlacement: ...

def place_object(
    self,
    object_uuid: UUID,
    position: tuple[int, int],
    *,
    boundary_direction: CardinalDirection | None = None,
    base_height_steps: int | None = None,
    orientation: CardinalDirection | None = None,
    parent_event: UUID | None = None,
) -> WorldObjectPlacement: ...

def move_object(
    self,
    object_uuid: UUID,
    position: tuple[int, int],
    *,
    boundary_direction: CardinalDirection | None = None,
    base_height_steps: int | None = None,
    orientation: CardinalDirection | None = None,
    parent_event: UUID | None = None,
) -> WorldObjectPlacement: ...

def orient_object(
    self,
    object_uuid: UUID,
    orientation: CardinalDirection | None,
    *,
    parent_event: UUID | None = None,
) -> WorldObjectPlacement: ...

def remove_object(
    self,
    object_uuid: UUID,
    *,
    parent_event: UUID | None = None,
) -> WorldObjectPlacement: ...
```

`validate_object_placement` resolves the Tile, live provider policy, complete
placement, local/opposite-edge bands, and collisions while preserving current
state. `place_object` uses the same resolver before committing.

Each operation performs this sequence:

1. resolve the Tile and live `BaseBlock`;
2. read the typed provider policy once;
3. resolve the complete target placement;
4. validate all covered local and opposite-edge bands;
5. update the Tile bands and `_object_placements` together;
6. invalidate affected occupancy and world-edge revisions;
7. publish the existing completed spatial fact; and
8. return the committed placement.

`set_tile`, `remove_tile`, and support-elevation mutation reject a Tile that
contains object bands. The caller moves or removes those objects first. The
origin lookup in `get_tile_by_uuid` uses an explicit presence check so position
`(0, 0)` resolves correctly.

## 8. Physical edge derivation

For an edge from Tile A toward direction D, GridMap reads:

- the existing intrinsic contribution authored on Tile A at D;
- the existing intrinsic contribution authored on the adjacent Tile at
  `opposite(D)`;
- A's boundary bands at D; and
- the adjacent Tile's boundary bands at `opposite(D)`.

For each occupying boundary placement, GridMap resolves the live `BaseBlock`
and reads its neutral boundary-state capability. The edge contribution carries
the provider UUID, the placement's exact height interval, and the current
blocked channels. Current XY transition queries union the channels from every
occupied boundary band on both sides plus both intrinsic Tile-side
contributions. Walking, flying, swimming, burrowing, vision, light, and
propagation therefore retain their current 2D endpoint API and consume the
same complete edge union. The exact stored intervals remain available to the
world state and future query evolution. Structure kind and material remain
authoritative item state carried by the existing item event model.

This drives the existing walking, sight, light, and propagation queries.
Subjective queries retain their current `BaseBlock.is_perceivable_by()` filter
for each object provider before unioning its channels. Intrinsic Tile-side
contributions remain objective. GridMap's object-derived directional Tile
caches are replaced by the boundary-band query; intrinsic Tile borders remain.
Door open/close invalidates the affected edge revision and publishes the
existing item/spatial state facts while retaining the same placement.

Current traversal connectors continue to express ladders, stairs, ramps, and
other authored passage. A cliff expresses a physical boundary contribution.

## 9. Existing event contracts after the cut

Evolve the existing event models with cold placement values.

`SpatialChangeEvent` gains:

```python
placement: WorldObjectPlacement | None = None
previous_placement: WorldObjectPlacement | None = None
tile_surface: TileSurfaceState | None = None
previous_tile_surface: TileSurfaceState | None = None
```

Object placement publishes the existing `OBJECT_PLACED` fact. Object movement
publishes the existing `OBJECT_REMOVED` followed by `OBJECT_PLACED` under one
causal parent, carrying previous and current placements. Orientation and
placement-state changes publish the existing `OBJECT_CHANGED` fact. Removal
publishes the existing `OBJECT_REMOVED` fact. Tile created/changed facts carry
the complete current and previous surface state.

`ItemLocationStateEvent` represents floor location with:

```python
world_placement: WorldObjectPlacement | None = None
```

`FLOOR` location carries the exact placement. Inventory, equipment, merged,
and destroyed locations carry an empty world placement.

The existing `ItemState` and `ItemObservationState` gain:

```python
boundary_structure: BoundaryStructureState | None = None
```

They retain the current open state. `WorldObjectState` replaces its former
position field with:

```python
placement: WorldObjectPlacement
```

It carries the complete placement and semantic item state. `WorldInitialized` remains the
map-bootstrap snapshot and contains exact Tile surfaces, object placements with
item states, and the existing traversal connectors. World-edge contributions
derive from those placements. Entity, spatial-effect, and light facts continue
through their existing lifecycles.

GridMap continues to publish through the current EventQueue lifecycle and
completed-fact APIs. Existing sensory, combat-log, subjective, and callback
machinery consumes the evolved facts.

## 10. Caller migration ledger

| Active surface | Migration |
|---|---|
| `BaseItem.place_on_grid`, removal, inventory, equipment, and destruction | use GridMap placement APIs; floor state is read from `get_object_placement`; item-location facts carry `world_placement` |
| loot/drop/pickup/equip floor transitions | call `validate_object_placement` before inventory/ownership mutation, then place and publish one final `ItemLocationStateEvent(world_placement=...)` from the existing transaction owner |
| `DirectionalWall` | become one `BoundaryWall` placed on one selected side |
| `DirectionalDoor` and `DoorObject` callers | converge on `BoundaryDoor` with existing use/open/close behavior |
| `WallTorch.mount` | accept authored `boundary_direction`, optional base/orientation, call `place_on_grid`, and resolve its light anchor from GridMap |
| `BattlefieldObjectDefinition` | replace multi-direction blocking with one optional authored `boundary_direction`, base, and orientation per placed object |
| old multi-direction structural rows | expand deterministically into one structure instance and placement per authored side |
| `dnd/content/items/environment_item_builders.py` | construct `BoundaryWall`/`BoundaryDoor` with intrinsic structure fields; placement side arrives later through `place_on_grid` |
| `dnd/items/environment_content.py` | preserve intact in the content-migration ledger together with its action-declaration dependency; active structural construction uses `environment_item_builders.py` |
| arena and scenario map builders | supply semantic surfaces and call each item's `place_on_grid` with explicit boundary placement |
| battlefield rectangle helpers | supply `TileSurfaceState` and retain their current event-suppression/final snapshot flow |
| object attack/use actions | resolve floor position through `get_object_placement` |
| `BaseItem`, inventory, Entity, standard actions, evocation spells, environment items, environment interactables, scenario compatibility, battlefield builders | replace `get_object_position` and `get_all_object_positions` reads with `get_object_placement`; `get_objects_at` callers continue using `get_objects_at` |
| GridMap's map-character, sensing, targeting, edge, path, reset, and snapshot internals | replace direct `_objects_by_position`/`_object_positions` reads with Tile-band iteration and `_object_placements` |
| world-object spatial-effect anchors | resolve their Tile and position from `get_object_placement` during footprint synchronization |
| runtime reset | clear object placement through GridMap reset and clear entity occupancy through GridMap entity APIs |
| Entity registry setup, deployment, movement, teardown, and Banishment | use GridMap entity occupancy APIs plus `Entity.get(uuid)` |

`WallTorch.mount` forwards this authored placement shape:

```python
def mount(
    self,
    position: tuple[int, int],
    *,
    boundary_direction: CardinalDirection,
    base_height_steps: int | None = None,
    orientation: CardinalDirection | None = None,
    lit: bool = True,
) -> WorldObjectPlacement: ...
```

`BattlefieldObjectDefinition` carries the matching cold fields:

```python
boundary_direction: CardinalDirection | None = None
base_height_steps: int | None = None
orientation: CardinalDirection | None = None
```

Rows with boundary placement require `boundary_direction`; center rows carry an
empty side. The builder passes these fields to the constructed item's
`place_on_grid` call.

The migrated floor lifecycle removes `BaseItem.tile_uuid` as floor authority
and removes direct item-position writes for floor placement. GridMap placement
is the sole floor-location read/write value. The item-location event replaces
its former floor `tile_uuid` and `position` fields with `world_placement`.

The concrete object-position caller inventory covers:

- `dnd/blocks/base_item.py` placement, removal, and destruction;
- `dnd/blocks/inventory.py` pickup/drop transitions;
- `dnd/entities/entity.py` floor-item interaction and deployment paths;
- `dnd/actions/standard.py` object attack/use resolution;
- `dnd/spells/evocation.py` object-target position resolution;
- `dnd/items/environment.py` and
  `dnd/items/environment_interactables.py` anchors and interactions;
- `dnd/content/scenarios/scenario_compatibility.py` authored compatibility;
- `dnd/content/scenarios/battlefield_builders.py` battlefield placement;
- `dnd/spatial/effect_base.py` world-object anchor synchronization; and
- `dnd/runtime_reset.py`, Entity registry/deployment/movement/teardown, and
  `dnd/spells/abjuration.py::BanishedCondition` for entity occupancy.

The GridMap-internal migration includes every direct flat-index read in the
current baseline at `gridmap.py:1140,1287,1326,1389,1465,1500,1838,2158,3069,
3208,3218`. Each becomes either Tile-band iteration, reverse placement lookup,
or `get_objects_at`, according to whether the operation begins from XY or UUID.

## 11. Entity position synchronization

Entity keeps `position` as its direct gameplay value. GridMap keeps:

```python
_entity_positions: dict[UUID, tuple[int, int]]
_entities_by_position: defaultdict[tuple[int, int], set[UUID]]
```

Delete `Entity._entity_by_position`. Positional entity lookup uses
`GridMap.get_entities_at(position)` followed by `Entity.get(uuid)`.

`Entity.update_entity_position` remains the single public movement owner and
performs this sequence:

1. validate the live deployed Entity and destination;
2. stage the existing GridMap position change;
3. update `Entity.position` and sensory position;
4. publish the existing LEFT and ENTERED spatial facts through GridMap; and
5. restore both Entity and GridMap values if the pre-publication commit fails.

`Game.deploy_entity` and `Game.remove_entity` use Entity attach/detach methods,
which call the same GridMap public occupancy APIs. Encounter and content remain
callers of Game/Entity rather than writers of private position dictionaries.

Architecture tests assert that production code writes `_entity_positions` and
`_entities_by_position` inside GridMap and writes `Entity.position` inside the
Entity spatial methods.

## 12. Temporary spatial suspension

Add two Entity methods:

```python
def suspend_from_world(
    self,
    *,
    parent_event: UUID | None = None,
) -> tuple[int, int]: ...

def restore_to_world(
    self,
    position: tuple[int, int],
    *,
    parent_event: UUID | None = None,
) -> None: ...
```

Entity gains the explicit Pydantic state field:

```python
is_spatially_suspended: bool = Field(default=False)
```

Extend the existing `GridEntityPositionReceipt` stage/publish path to represent
an optional destination. `stage_entity_position(entity_uuid, None)` commits an
occupancy removal and returns the exact LEFT metadata. Staging from empty
occupancy to a position commits restoration and returns the exact ENTERED
metadata. `publish_staged_entity_position` publishes the applicable existing
fact once after Entity state commits.

Suspension:

1. requires `is_deployed=True` and `is_spatially_suspended=False`;
2. captures and returns `Entity.position`;
3. stages removal from both GridMap occupancy indexes;
4. sets `is_spatially_suspended=True` while retaining `is_deployed=True`;
5. preserves Game ownership, Entity identity, conditions, actions, values,
   observer state, attached lights, entity-anchored effects, and the captured
   direct position; and
6. publishes the staged existing spatial LEFT fact with an empty destination.

Restoration:

1. requires `is_deployed=True` and `is_spatially_suspended=True`;
2. validates the chosen return Tile;
3. stages GridMap occupancy at the chosen position;
4. synchronizes `Entity.position` and sensory position when the chosen return
   differs from the captured position;
5. sets `is_spatially_suspended=False`; and
6. publishes the staged existing spatial ENTERED fact with an empty origin.

Ordinary Entity movement requires `is_spatially_suspended=False`. Ordinary
deployment retains its current `is_deployed` guard, so restoration is the
return path for a suspended Entity. Terminal detach accepts either occupancy
state, clears `is_spatially_suspended`, unregisters the observer and GridMap
entity ownership through the existing teardown path, and completes with
`is_deployed=False`. `Game.entities` remains unchanged throughout suspension.

`BanishedCondition` stores the returned position in its existing typed field,
calls `suspend_from_world` during application, resolves the current occupied
return rule, and calls `restore_to_world` during removal. Its private writes to
GridMap and Entity registries disappear.

Gust of Wind continues to move entities through
`Entity.update_entity_position`. The existing `_pushes_in_flight` guard remains
the re-entrancy owner. Regression tests cover entry push, turn-start push,
ordinary LEFT/ENTERED ordering, and one movement per admitted trigger.

## 13. Implementation sequence

### Phase 0 — Pin current behavior

1. record direct object-placement callers;
2. record wall, door, WallTorch, item-floor, world-edge, and snapshot behavior;
3. record environment item builders, registered parameter models, factories,
   recipes, and every selected placement side;
4. checksum `dnd/items/environment_content.py` and record it with its
   action-declaration dependency in `DND_CONTENT_MIGRATION_LEDGER_2026-08-16.md`;
5. record every positional Entity writer and reader;
6. record Banishment suspend/return behavior and Gust movement behavior;
7. pin current event JSON for object placement, entity movement, item floor
   location, and world initialization; and
8. record the active test-preservation ledger in Section 14.

Gate: every active caller has one target operation in Sections 10–12.

### Phase 1 — Cold types and Tile storage

1. add semantic material/surface contracts;
2. add placement contracts;
3. add BaseBlock capabilities;
4. add Tile bands and invariants;
5. migrate GridMap Tile constructors and active Tile factories in the same cut,
   using `TileSurfaceState(substrate=MaterialKind.EARTH)` for the generic GridMap
   default, dressed stone for current floor factories, water for `water_factory`,
   dressed stone for `wall_factory`, and earth for difficult terrain;
6. preserve those explicit values until authored builders supply their selected
   surfaces in Phase 3; and
7. add focused model/serialization tests.

Gate: cold types import cleanly; Tile band round trips preserve exact UUID,
side, interval, and occupant state; and the cold `WorldObjectPlacement` round
trip preserves orientation.

### Phase 2 — GridMap object placement

1. add `_object_placements`;
2. implement pure validation plus place, move, orient, remove, and query;
3. implement local/opposite-edge collision validation;
4. migrate every GridMap-internal flat-index read;
5. preserve intrinsic Tile-side contributions and subjective provider
   filtering;
6. add populated-Tile mutation rejection and the origin UUID lookup fix; and
7. derive the current 2D edge union from intrinsic borders and boundary bands.

Gate: every object placement has one reverse value and exact Tile forward rows.

### Phase 3 — Active structural items and direct callers

1. add the minimal structural item hierarchy;
2. migrate wall, door, cliff, and WallTorch with the exact pickable, usable,
   scalar-blocking, senses, and action-discovery defaults in Section 5;
3. extend `BaseItem.place_on_grid` and `WallTorch.mount` with the exact placement
   parameters in Sections 4 and 7;
4. migrate ordinary floor item helpers;
5. migrate `environment_item_builders.py` to the new boundary classes and
   intrinsic structure parameters;
6. migrate battlefield definitions and expand multi-side rows;
7. migrate arena/scenario builders through `BaseItem.place_on_grid`; and
8. migrate action position lookups.

Gate: active map construction and object interactions use the new GridMap API.

### Phase 4 — Exact event payloads

1. evolve `SpatialChangeEvent`;
2. evolve `ItemLocationStateEvent`;
3. evolve `ItemState`, `ItemObservationState`, `WorldObjectState`, and the
   map-bootstrap `WorldInitialized`;
4. migrate combat-log and subjective readers to the new fields; and
5. pin canonical JSON and replay order.

Gate: the existing event stream reconstructs Tile surfaces and object
placements exactly.

### Phase 5 — Entity position cleanup

1. migrate inverse positional lookup to GridMap;
2. delete `Entity._entity_by_position`;
3. make Entity movement the single synchronization path;
4. migrate Game deployment/removal and active direct callers; and
5. update reset and architecture gates.

Gate: Entity and GridMap positions remain synchronized across deploy, move,
failure rollback, and removal.

### Phase 6 — Spatial suspension

1. add Entity suspension state and Entity suspend/restore methods;
2. extend the existing GridMap entity-position receipt to stage an empty or
   occupied destination and publish its applicable fact once;
3. migrate Banishment;
4. preserve occupied-return behavior through public movement APIs;
5. verify the existing observer, light, entity-anchor, and LEFT/ENTERED
   behavior; and
6. run Gust movement regressions through the shared movement path.

Gate: a Game-owned Entity can leave spatial occupancy and return while its
identity and gameplay state survive unchanged.

### Phase 7 — Hard cut and verification

1. delete the flat object indexes;
2. delete Tile directional object caches, directional item placement fields,
   `BaseItem.tile_uuid`, and direct floor-position writes;
3. delete `Entity._entity_by_position` and all private external position
   writers;
4. delete the former item-location floor `tile_uuid` and `position` fields;
5. replace `WorldObjectState.position` with
   `placement: WorldObjectPlacement` and migrate
   `dnd/content/scenarios/battlefield_builders.py` snapshot assembly;
6. delete legacy object-position getters after every ledgered caller uses the
   placement value;
7. delete `get_objective_directional_structural_channels`,
   `get_directional_structure_state`, `ItemDirectionalStructureState`, and the
   former `directional_structure` event/observation fields after every consumer
   uses `BoundaryStructureState`;
8. delete duplicate directional door/wall constructors after callers converge;
9. scan the active runtime and remaining default-collected tests for every
   deleted private store, method, type, field, and constructor symbol, while
   verifying the separate checksum of the content-ledger source artifact;
10. run focused and architecture suites; and
11. categorize unrelated collection blockers separately.

## 14. Capability tests

Follow `HOW_TO_TEST.MD` before editing tests.

The active test-preservation ledger is:

| Current file | Preserved in-process capability |
|---|---|
| `tests/engine/test_world_edge_identity_and_elevation.py` | split and retain intrinsic/object edge identity, elevation, movement, visibility, and subjective-provider cases using active imports |
| `tests/engine/test_elevation_proving_battlefield.py` | migrate proving-ground door setup and actions to `BoundaryDoor` plus explicit placement side |
| `tests/engine/test_action_discovery.py` | migrate object discovery and position assertions to `WorldObjectPlacement` |
| `tests/engine/test_grid_pathfinding.py` | migrate placed-object and structural-edge path cases to Tile bands |
| `tests/engine/test_items_inventory_equipment.py` | migrate floor lifecycle assertions from `tile_uuid` to GridMap placement |
| `tests/engine/test_equipment_replication_facts.py` | migrate location-event assertions to `world_placement` |
| `tests/engine/test_manual_21_arena_game_sessions_client_state.py` | extract its in-process arena object-position assertion into the active placement/replay suite |
| `tests/engine/support.py` | replace direct Entity inverse-index mutation with public Entity/GridMap positioning helpers before dependent suites run |
| `tests/engine/test_condition_transform_ownership.py` | assert Banishment occupancy through `GridMap.get_entities_at` |
| `tests/engine/test_runtime_identity_registries.py` | reset Entity/GridMap ownership through the public runtime-reset surface |
| `tests/engine/test_runtime_reset.py` | seed and verify Entity occupancy through GridMap/public reset APIs |
| `tests/engine/test_dice_event_semantics.py` | use the shared public runtime reset fixture |
| `tests/engine/test_manual_07_entity_composition.py` | use the shared public runtime reset fixture |
| `tests/engine/test_manual_09_conditions.py` | use the shared public runtime reset fixture |
| `tests/engine/test_manual_10_standard_conditions.py` | use the shared public runtime reset fixture |
| `tests/engine/test_objective_state.py` | create an actual placed object through `BaseItem.place_on_grid` instead of seeding the flat index |
| `tests/manual/test_directional_environment_legacy_contract.py` | migrate its in-process wall/door recipes, edge behavior, actions, and perception cases to boundary items with explicit placement side |
| `tests/engine/test_spell_families.py` | extract Oil Barrel, WallTorch, and spatial-interaction spell cases to active direct-item/spatial tests; record the content-shaped remainder in the content test ledger |

Default-collected manual test dispositions are:

| Current files | Recorded disposition |
|---|---|
| `test_01_runtime_identity_and_registries.py`, `test_02_entity_anatomy.py`, `test_09_action_discovery_and_costs.py`, `test_103_game_summary_store.py`, `test_10_combat_resolution.py`, `test_11_equipment_inventory_and_items.py`, `test_12_perception_light_stealth_and_invisibility.py`, `test_13_spellcasting_core.py`, `test_14_spell_families.py`, `test_17_encounters_turns_controllers.py`, `test_18_sessions_api_client_contract.py`, `test_20_content_extension_basics.py`, `test_21_spell_and_feature_extensions.py`, `test_53_srd_monster_traits.py` | migrate direct `Entity._entity_by_position.clear()` setup to the shared public runtime reset fixture; each test retains its existing capability classification in the server/content cleanup ledger |
| `test_09_action_discovery_and_costs.py`, `test_11_equipment_inventory_and_items.py`, `test_131_advanced_item_world_legacy_contract.py`, `test_133_item_core_lifecycle_legacy_contract.py`, `test_134_stackable_usable_item_legacy_contract.py` | migrate floor assertions to `WorldObjectPlacement` and transaction-owned item-location facts; retain action, pickup/drop, stack, destruction, and equipment behavior |
| `test_133_new_spells_batch4_legacy_contract.py` | migrate displacement and Banishment occupancy assertions to `GridMap.get_entities_at`; retain the spell behavior |
| `test_37_authored_encounter_mechanics.py` | migrate door lookup, placement, and actions to `BoundaryDoor` and `get_object_placement`; retain authored encounter mechanics |
| `test_directional_environment_legacy_contract.py` | migrate direct recipes and wall/door mechanics into engine boundary-item tests using `environment_item_builders.py` and explicit placement sides |
| `test_113_subjective_replication_routes.py`, `test_120_subjective_world_projection.py`, `test_125_subjective_objective_render_parity.py` | extract engine-native door state, perception, and event assertions into boundary-item/event tests; remove their server-shaped wrappers from the active suite |
| `test_11_equipment_inventory_and_items.py` door cases | replace `directional_door_recipe`/`TutorialDoor` with `environment_item_builders.build_directional_door` returning `BoundaryDoor`, plus explicit placement side; retain inventory/use-action behavior |
| `test_134_stackable_usable_item_legacy_contract.py` door cases | extract the three door/path/action cases to active `BoundaryDoor` capability tests; record the remaining mixed recipe tests in the content test ledger |
| `test_legacy_reactive_reaction_coverage.py` door cases | replace `door_recipe`/`DoorFixture` with the direct BoundaryDoor builder; retain path invalidation and open/close reaction behavior |
| `test_134_cleric_batch1_legacy_contract.py` Oil Barrel cases | migrate to the direct Oil Barrel construction established by the spatial-reaction recovery; retain the cleric/spatial interaction behavior |
| `test_131_inventory_use_actions_legacy_contract.py` | record its arcane-device mixed recipe coverage in the content test ledger and move the content-shaped wrapper outside the default suite |

Every default-suite import of `dnd.items.environment_content` has one of these
destinations:

- `tests/engine/test_spatial_effects.py`: direct Oil Barrel construction in the
  spatial-reaction recovery plan;
- `tests/engine/test_spell_families.py`: extracted active Oil/WallTorch/spatial
  cases;
- the three subjective/server files: extracted engine-native door facts;
- `test_11_equipment_inventory_and_items.py`: direct BoundaryDoor builder;
- `test_134_cleric_batch1_legacy_contract.py`: direct recovered Oil Barrel;
- `test_legacy_reactive_reaction_coverage.py`: direct BoundaryDoor builder; and
- the three content-shaped wrappers
  (`test_131_inventory_use_actions_legacy_contract.py`,
  `test_134_stackable_usable_item_legacy_contract.py`, and
  `test_directional_environment_legacy_contract.py`): extracted engine-native
  cases plus content-ledger source tests stored outside the default suite.

`dnd/items/environment_content.py` and tests whose capability belongs to its
mixed item/action recipe catalog remain recorded in the content-migration test
ledger. This placement cut consumes the direct structural builder and the
engine-native assertions listed above.

The active-runtime/default-suite symbol scan covers `_objects_by_position`, `_object_positions`,
`Entity._entity_by_position`, `BaseItem.tile_uuid`, the former item-location and
world-object position fields, the directional structure methods/type/fields,
and legacy directional wall/door constructor names across production and tests.
The content-migration ledger separately inventories the preserved mixed
`environment_content.py` source artifact and its recipe tests. The default
suite contains zero imports of that source artifact at the Phase 7 gate.

Placement tests cover:

- pure placement validation preserving current state;
- invalid drop and displaced-equipment destinations preserving inventory,
  ownership, and floor state;
- center placement and optional center orientation;
- one boundary side plus independent orientation;
- multi-band structure extent;
- occupying collision and nonoccupying attachment coexistence;
- opposite-side physical-edge collision;
- cliff below a support surface and wall above it;
- door channel changes with stable placement;
- exact nonpickable, usable-discovery, scalar-blocking, senses, and action
  defaults for every structural class;
- substrate and cover serialization;
- populated-Tile mutation rejection;
- `(0, 0)` UUID lookup;
- placement move/orient/remove consistency; and
- wall, door, cliff, and WallTorch direct construction.

Event/replay tests cover:

- exact current/previous placement JSON;
- exact floor item location;
- one final floor-location fact from each inventory/equipment/Entity
  transaction owner;
- bootstrap object placement represented by one final `WorldInitializedEvent`;
- complete WorldInitialized surfaces and placements;
- `WorldObjectState.placement` as the sole snapshot position;
- movement/vision/light/propagation edge queries;
- intrinsic Tile-border union and subjective object-provider filtering;
- combat-log and subjective consumption; and
- reconstruction from the existing event stream.

Entity tests cover:

- deploy, move, and terminal removal synchronization;
- inverse lookup through GridMap;
- pre-publication movement failure restoration;
- suspension preserving Game ownership and Entity state;
- suspension preserving current observer, attached-light, and entity-anchor
  effect state;
- restoration to the captured or resolved return position;
- Banishment application/removal using public methods;
- occupied Banishment return behavior;
- preservation of the current sensory-observer state; and
- Gust entry and turn-start push re-entrancy.

Architecture tests cover the dependency graph in Section 2, the Pydantic cold
contracts, the single object reverse index, the two synchronized entity stores,
and the absence of external writes to their private dictionaries.

## 15. Completion criteria

1. Tile surface substrate and cover are explicit semantic facts.
2. Center and four boundary placements support integer vertical bands.
3. GridMap owns one reverse object-placement value per placed object.
4. Active walls, doors, cliffs, attachments, and floor items use the same API.
5. Drop and displaced-equipment transactions preflight through the pure GridMap
   placement validator.
6. World-edge queries derive from neutral capabilities on placed boundary
   providers while retaining intrinsic Tile borders and subjective filtering.
7. Existing events carry exact placement and surface facts.
8. Existing replay, combat log, and subjective consumers use those facts.
9. Entity retains direct position and GridMap retains synchronized UUID indexes.
10. `Entity._entity_by_position` and private external position writes are gone.
11. Banishment uses general Entity suspension/restoration.
12. Suspended entities preserve current observer, attached-light, and
    spatial-effect anchor state.
13. Gust uses the shared ordinary movement path with preserved re-entrancy.
14. BaseItem floor authority and former item-location floor fields are removed.
15. The former directional structure type, methods, and fields are removed.
16. `WorldObjectState` owns one complete placement value.
17. The active-runtime/default-suite deleted-symbol scan is empty, and the
    mixed content source artifact has an exact content-ledger checksum.
18. The default suite imports active direct modules for every extracted
    capability and contains zero `environment_content.py` imports.
19. Focused capability and architecture tests pass.
20. Both independent reviewers approve this document revision.
