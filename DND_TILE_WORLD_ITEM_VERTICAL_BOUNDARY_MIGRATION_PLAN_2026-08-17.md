# Tile, world-item, and vertical-boundary hard-cut plan

Status: planning revision approved by both independent reviewers; implementation
remains unauthorized until explicitly requested.

This document supersedes `DND_TILE_OBJECT_PLACEMENT_AGREEMENT_2026-08-17.md`.
That note captured the initial center/boundary agreement but did not yet model
vertical bands. This plan is the implementation contract for the migration. It
does not authorize implementation by itself.

## 1. Objective

Replace the present flat object-position indexes and directional-boolean
projection with one authoritative, Pydantic-validated model in which:

1. one `Tile` exists at each `(x, y)`;
2. the Tile owns the forward record of objects at its center and four cardinal
   boundaries;
3. boundary storage is indexed by integer vertical bands so a cliff below a
   terrace and a wall above it are distinct physical structures;
4. `GridMap` is the only mutation boundary and owns the reverse object-placement
   index;
5. `Entity.position` remains the authoritative objective coordinate for a
   deployed actor, while the containing Tile owns only the forward occupant
   UUID index used by spatial queries;
6. an object owns its intrinsic placement policy and physical semantics, while
   the placement owns the chosen Tile, boundary, base height, and orientation;
7. completed events carry the exact committed facts required to replay the
   world and to drive any client without asset or renderer identifiers; and
8. the old directional fields, cached Tile projections, duplicate entity and
   item location indexes, and compatibility APIs are deleted rather than
   retained beside the new model.

The immediate result is a clean engine substrate on which later authored map
content can declaratively create ground, overlays, cliffs, walls, doors,
objects, and traversal connectors.

## 2. Non-negotiable decisions

### 2.1 One surface per XY

There is exactly one playable support surface at `(x, y)`. `Tile.height` is its
support elevation in the engine's existing five-foot integer steps. There are
no stacked Tile surfaces, `ZGrid` objects, or parallel `GridMap` instances.

Vertical boundary bands do **not** create additional playable surfaces. They
describe physical volumes around the one Tile.

### 2.2 Placement ownership

- `Tile` owns the persistent forward placement collections.
- `Entity.position` owns an actor's objective coordinate. Tile owns the
  forward `entity_uuids` membership index; it does not copy entity state.
- `GridMap` owns the reverse `object UUID -> placement` index and all mutations.
- `BaseItem`/`WorldItem` does not store `tile_uuid`, floor `position`, boundary,
  base height, or placed orientation.
- The content/caller chooses target position, boundary when required, base
  height when permitted, and orientation.
- The object decides whether it is a center or boundary object, whether it
  reserves physical bands, its vertical extent, and which world-edge channels
  it blocks in its current state.
- No caller API accepts `occupies_slot` or blocked channels.

### 2.3 Pydantic and dependency discipline

All newly authored value objects are Pydantic `BaseModel` objects with
`ConfigDict(extra="forbid", frozen=True)` unless they are mutable engine
objects such as `Tile`, `BaseItem`, or `GridMap`. Existing enums remain enums.
The three dataclasses currently in `dnd/core/world_edges.py` become frozen
Pydantic models during this cut. The obsolete `GridEntityPositionReceipt` is
deleted with the duplicate indexes it stages. There is no custom serialization
layer.

The migration may not introduce:

- `TYPE_CHECKING` imports;
- function-local or late imports used to hide cycles;
- `getattr`-based capability discovery;
- concrete `isinstance(WorldItem, ...)` checks inside `GridMap`;
- duplicate event DTOs for the same placement fact;
- compatibility facades, deprecated aliases, or dual-write periods; or
- renderer asset names, sprite paths, pivots, pixel offsets, painter layers, or
  renderer rotations in the new contracts.

### 2.4 Placement direction is not orientation

`boundary_direction` says which side of a Tile contains a boundary object.
`orientation` says which cardinal direction the object faces. Both reuse the
existing `CardinalDirection`; no second directional enum is introduced.

A center object may have an orientation. A boundary object's orientation
defaults to its boundary direction but is stored as a resolved value so replay
does not need to repeat defaulting logic.

### 2.5 Cliff, wall, and height are different facts

A height difference is not rendered or interpreted automatically as a cliff.
The support height and boundary structure are separately authoritative:

- `Tile.height = 2` says the playable surface is at step 2.
- a cliff on the Tile's west boundary at `[0, 2)` says rock supports/exposes
  the rise below it;
- a stone wall on that boundary at `[2, 4)` says masonry continues above the
  playable surface; and
- `Tile.height = 4` with no wall says a playable terrace exists at step 4, not
  that an invisible wall or cliff has been inferred.

A cliff never grants traversal. A ladder, rope, lift, or atomic vertical
passage is a separate traversal connector. Ordinary stairs and ramps continue
to use progressive support-surface topology.

## 3. Explicit scope

### Included

- dependency-neutral world/material/placement vocabulary;
- Tile center and z-banded boundary storage;
- GridMap placement, move, rotation, removal, lookup, validation, and reset;
- structural world-item hierarchy sufficient for walls, doors, cliffs,
  retaining walls, fences, and nonoccupying attachments;
- migration of existing flat floor objects to center placement;
- removal of directional item fields and Tile directional caches;
- world-edge derivation from boundary objects;
- exact placement facts in spatial, item-location, and world-initialization
  events;
- bootstrap and load/rebuild validation;
- current arena/scenario/environment item callers; and
- consolidation of entity position/occupancy storage without redesigning
  entity creation, progression, Encounter, or movement rules; and
- focused engine, event, replay, subjective-query, and architecture tests.

### Excluded

- stacked playable surfaces at one XY;
- full 3D entity altitude, 3D ray casting, flying-volume collision, or vertical
  action targeting;
- animation or action presentation;
- client asset selection and renderer code;
- generic content packages, registries, hashes, or external formats;
- full fire/material reaction rules;
- rewriting traversal-connector content identity and presentation fields;
- server, SDK, database, or TypeScript work;
- entity/encounter/content migrations beyond the position/occupancy hard cut
  and direct placement callers that must compile after it; and
- global removal of `BaseBlock.position` or `map_char`, because those are wider
  migrations. Floor-item placement stops using both as authority here.

## 4. Current-state defect ledger

The implementation must begin by pinning these live defects with focused tests:

| Current owner | Current fact | Defect |
|---|---|---|
| `dnd/blocks/base_item.py::BaseItem` | inherited `position` plus `tile_uuid` | duplicates GridMap floor authority and is manually cleared/restored by inventory code |
| `dnd/core/gridmap.py::GridMap` | `_object_positions` plus `_objects_by_position` | flat XY only; the second index duplicates information that the Tile should own |
| `dnd/core/base_tiles.py::Tile` | 16 authored border booleans plus 16 object-derived booleans | physical providers are flattened into anonymous cached truth |
| `dnd/blocks/base_item.py::BaseItem` | 16 directional block booleans | direction is stored on the object even though actual boundary is placement state |
| `dnd/items/environment.py::DirectionalWall` | `blocked_directions` | one item can pretend to occupy several edges and defaults to all four |
| `dnd/types/items.py::ItemDirectionalStructureState` | directions plus channels | repeats placement direction inside item state |
| `dnd/core/gridmap.py::recompute_tile_directional_blocking` | scans objects/entities and rewrites Tile booleans | creates a third derived authority and expensive synchronization path |
| `dnd/core/world_edges.py` | dataclass edge DTOs | deviates from the repository's Pydantic validation/serialization boundary |
| `dnd/core/gridmap.py::GridEntityPositionReceipt` | dataclass tied to duplicate entity-position indexes | becomes obsolete when one GridMap call preflights, commits Entity/Tile state, and publishes already-prepared events |
| `dnd/entities/entity.py::Entity.position` | correct objective actor coordinate | is manually mirrored into Senses and two independent position indexes |
| `dnd/entities/entity.py::_entity_by_position` | position-to-Entity registry | duplicates GridMap occupancy and is directly edited by Banishment/tests |
| `dnd/core/gridmap.py::_entity_positions` | UUID-to-position registry | duplicates `Entity.position` and can disagree with the actor |
| `dnd/core/gridmap.py::_entities_by_position` | position-to-UUID registry | belongs on the Tile as forward occupant membership |
| `dnd/spells/abjuration.py::BanishedCondition` | writes all three private entity-position stores | bypasses the movement boundary and proves the duplicated authorities are externally mutable |
| `dnd/core/events/world_events.py::WorldObjectState` | only XY plus `ItemState` | cannot replay center/boundary, orientation, base height, or vertical extent |
| `SpatialChangeEvent` | flat directional maps and `object_map_char` | emits a lossy projection and renderer/debug data rather than exact placement |
| `ItemLocationStateEvent` | `tile_uuid` plus `position` | repeats a partial floor placement and cannot represent boundaries |
| object placement lifecycle | mutation occurs before a cancelable declaration event | cancellation cannot roll back the already-mutated GridMap |

The amended scope includes the entity-occupancy hard cut. `Entity.position`
remains the actor's objective coordinate, `Tile.entity_uuids` becomes the sole
forward occupant index, and both GridMap entity dictionaries plus
`Entity._entity_by_position` are deleted.

## 5. Target dependency graph

Arrows mean “imports”. No arrow may point upward from core to authored items.

```text
dnd/types/world.py
  -> enum, pydantic, UUID
  <- base_block, base_tiles, world_edges, gridmap, events, items, content

dnd/types/materials.py
  -> enum, pydantic
  <- base_tiles, world_items, events, content

dnd/core/base_block.py
  -> dnd/types/world.py, dnd/types/items.py
  <- base_tiles, base_item, gridmap

dnd/core/base_tiles.py
  -> base_block, dnd/types/world.py, dnd/types/materials.py
  <- gridmap, world events, content

dnd/core/world_edges.py
  -> dnd/types/world.py, dnd/types/materials.py, pydantic
  <- gridmap, tests

dnd/blocks/base_item.py
  -> base_block, dnd/types/world.py, dnd/spatial/anchor_mutations.py
  <- dnd/blocks/world_items.py and all concrete items

dnd/blocks/world_items.py
  -> base_item, dnd/types/world.py, dnd/types/materials.py
  <- dnd/items/environment.py and authored content

dnd/core/gridmap.py
  -> base_block, base_tiles, world_edges, events, dnd/types/world.py
  <- gameplay/content callers

dnd/entities/entity.py
  -> gridmap, base_block, entity-owned blocks, dnd/spatial/effect_base.py
  <- game, encounter, actions, content

dnd/spatial/controller_mutations.py
  -> Pydantic, core BaseCondition/condition events, events_registry receipts,
     dnd/types
  <- effect_base, environmental_effects, effect_controllers,
     effect_memberships, anchor_mutations
  -X-> Entity, BaseItem, effect_base, concrete controllers, content
  frozen lower PreparedSpatialControllerMutation and
  PreparedConditionLifecycle receipts plus pure lifecycle helpers

dnd/spatial/effect_base.py
  -> core/base machinery, controller_mutations, dnd/types
  <- Entity attached-effect orchestration, anchor_mutations,
     concrete spatial controllers, authored materialization
  typed prepare/commit/rollback/publish anchor-transition boundary

dnd/spatial/anchor_mutations.py
  -> effect_base, controller_mutations, core UUID lookup/event values
  <- BaseItem public world-placement commands
  BaseItem-anchor compound coordination without importing BaseItem

Entity position dependency rule
  Entity.move -> GridMap entity mutation API
  GridMap -> BaseBlock.get(uuid).supports_spatial_actor_occupancy()
  GridMap -> BaseBlock.get(uuid).set_position(...)
  GridMap -X-> dnd.entities.entity
  Tile -> UUID occupant membership only

dnd/core/events/world_events.py
  -> dnd/types/world.py, materials.py, world_edges.py, item events
  <- reducers, combat log, senses, content bootstrap

dnd/core/events/events_registry.py
  -> core event/projection machinery and Pydantic
  <- every event producer, controller_mutations
  sole authoritative index writer
  passive committed and guarded postcommit lifecycles share one
  between-EFFECT-and-COMPLETION child hook
  no late-child repair or completed-parent mutation
```

Hard dependency rules:

1. `dnd/types/*` imports no `dnd/core`, `dnd/blocks`, `dnd/items`, or content.
2. `Tile` stores UUIDs and cold values only; it never imports `BaseItem` or
   concrete item classes.
3. `GridMap` resolves a UUID to `BaseBlock` and calls one typed polymorphic
   method. It never imports `dnd.blocks.world_items` or `dnd.items`.
4. Concrete items may depend downward on blocks/core/types.
5. Events may import cold Pydantic types and core edge values, but never
   concrete item or content builders.
6. `BaseBlock.supports_spatial_actor_occupancy()` returns `False`; `Entity`
   overrides it with `True`. Every GridMap entity API requires this typed
   capability before touching Tile state, then invokes polymorphic
   `set_position`. GridMap never imports or type-checks `Entity`, and no
   reflection or `getattr` is used.
7. Entity may depend downward on GridMap. Tile stores entity UUIDs only and
   never imports Entity, Senses, Game, or Encounter.
8. `dnd/spatial/controller_mutations.py` is a lower leaf relative to all
   runtime spatial owners: it imports no Entity, BaseItem, effect_base,
   concrete controller, authored content, or runtime registry. In particular,
   it can never import live `effect_controllers.py`, which already depends on
   Entity.
9. Entity and BaseItem do not import concrete spatial controllers. Entity calls
   the typed `SpatialEffect` anchor-transition boundary; BaseItem calls
   `anchor_mutations.py`, which calls that same boundary. Concrete Pydantic
   receipt subclasses depend downward on the frozen lower receipt, never the
   reverse.

## 6. Exact cold vocabulary

### 6.1 `dnd/types/world.py`

Add these enums and models beside `CardinalDirection` and `WorldEdgeChannel`:

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
    policy: WorldPlacementPolicy
    boundary_direction: CardinalDirection | None = None
    base_height_steps: int
    top_height_steps: int
    orientation: CardinalDirection | None = None
```

`WorldObjectPlacement` is the one placement fact used by the reverse index and
events. It validates:

- both coordinates and both heights are exact `int`, not coercible strings,
  floats, or booleans;
- `top_height_steps > base_height_steps`;
- `policy.kind == CENTER` requires `boundary_direction is None`;
- `policy.kind == BOUNDARY` requires a boundary direction;
- UUIDs are present; and
- `top - base == policy.vertical_extent_steps`; and
- when GridMap validates a live object, the embedded policy must equal the
  provider's current policy exactly.

The model deliberately includes `object_uuid` although the reverse dictionary
is keyed by it: an event payload and serialized placement remain self-contained.

### 6.2 `dnd/types/materials.py`

Introduce only semantic game facts needed by this cut:

```python
class MaterialKind(StrEnum):
    EARTH = "earth"
    SAND = "sand"
    ROCK = "rock"
    DRESSED_STONE = "dressed_stone"
    WOOD = "wood"
    METAL = "metal"
    FABRIC = "fabric"
    GLASS = "glass"
    WATER = "water"
    ICE = "ice"
    VEGETATION = "vegetation"


class SurfaceCoverKind(StrEnum):
    GRASS = "grass"
    WOOD_FLOOR = "wood_floor"
    STONE_FLOOR = "stone_floor"
    RUBBLE = "rubble"
    SNOW = "snow"


class BoundaryStructureKind(StrEnum):
    CLIFF = "cliff"
    EMBANKMENT = "embankment"
    RETAINING_WALL = "retaining_wall"
    WALL = "wall"
    DOOR = "door"
    FENCE = "fence"
```

These are not asset keys. The deliberate current overfit is domain vocabulary
that distinguishes structures the rules and authoring system genuinely need.
Do not add generic semantic-tag bags.

Add:

```python
class TileSurfaceState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    substrate: MaterialKind
    cover: SurfaceCoverKind | None = None
    description: str = ""
```

`substrate` is the supporting material; `cover` is the distinct top layer that
later conditions may alter, such as grass burning above earth. This migration
stores and emits the distinction but does not implement reactions.

`Tile.surface` has no silent default. `Tile.create(..., *, surface=...)` and
`GridMap.set_tile(..., surface=...)` require the exact state whenever they
construct a Tile. Existing canonical factories use:

| Factory | Substrate | Cover |
|---|---|---|
| `floor_factory` | `DRESSED_STONE` | `STONE_FLOOR` |
| `dark_floor_factory` | `DRESSED_STONE` | `STONE_FLOOR` |
| solid-cell `wall_factory` | `DRESSED_STONE` | `None` |
| `water_factory` | `WATER` | `None` |
| `difficult_terrain_factory` | `EARTH` | `RUBBLE` |

Phase 0 inventories every direct `Tile.create`, `GridMap.set_tile`, rectangle
builder, test Tile fixture, and map factory. Each supplies an explicit value;
unknown authored terrain is resolved in that ledger rather than hidden behind
an `EARTH` or `STONE` default. The cut also removes `sprite_name` from these
factory calls.

### 6.3 `BaseBlock` capability

Add exactly three typed capability methods to `BaseBlock`:

```python
def get_world_placement_policy(self) -> WorldPlacementPolicy:
    return WorldPlacementPolicy(
        kind=WorldPlacementKind.CENTER,
        occupies_bands=False,
        vertical_extent_steps=1,
    )


def get_world_edge_blocked_channels(
    self,
) -> tuple[WorldEdgeChannel, ...]:
    return ()


def get_world_boundary_structure_state(
    self,
) -> ItemBoundaryStructureState | None:
    return None
```

This neutral default lets existing dropped `BaseItem` objects remain center,
nonoccupying floor objects during the hard cut. It is the only capability hook
`GridMap` needs. It replaces reflection and concrete type checks.

Only boundary providers override the latter two methods. The structure hook is
the dependency-safe route by which GridMap obtains semantic kind/material for
`WorldEdgeStructuralContribution`; GridMap never imports or type-checks a
concrete item. Neither hook contains direction. Direction comes from
`WorldObjectPlacement`.

## 7. Tile storage

### 7.1 Band record

Define in `dnd/core/base_tiles.py`:

```python
class TileObjectBand(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    objects: dict[UUID, CardinalDirection | None] = Field(default_factory=dict)
    occupant_uuid: UUID | None = None
```

The dictionary value is the resolved orientation. `occupant_uuid` must either
be `None` or be a key in `objects`. A band may contain any number of
nonoccupying objects and at most one occupying object.

### 7.2 Tile fields

Replace all intrinsic and object-derived directional border booleans with:

```python
surface: TileSurfaceState
entity_uuids: set[UUID]
center_object_bands: dict[int, TileObjectBand]
boundary_object_bands: dict[
    CardinalDirection,
    dict[int, TileObjectBand],
]
```

Each integer key represents the half-open unit interval `[z, z + 1)`. An object
at `[0, 2)` appears in bands `0` and `1`, always with the same orientation and
occupancy role. The object itself is still a single object.

Every Tile initializes all four boundary dictionaries. Empty band rows are
removed immediately after removal; empty sides remain present.

`entity_uuids` is the sole forward objective occupant index. It is not a second
position field: the coordinate remains on the Entity, while Tile membership
answers the inverse query "which deployed actors occupy this cell?". World
snapshot/event serializers sort the UUIDs; runtime membership remains a set.

### 7.3 Storage invariants

For every placed object:

1. exactly one `WorldObjectPlacement` exists in GridMap;
2. the placement's `tile_uuid` and `position` resolve to the same live Tile;
3. its UUID occurs once in every band in `[base, top)` at exactly the center or
   boundary side selected by the placement;
4. it occurs in no other Tile, side, or band;
5. every occurrence has the same orientation;
6. if its policy occupies bands, every occurrence is that band's
   `occupant_uuid`; otherwise it is never an occupant;
7. a center placement's base equals `Tile.height`; floating and stacked center
   objects are rejected in this version;
8. a boundary placement may explicitly begin below, at, or above Tile height;
9. a boundary placement cannot overlap an occupying placement stored on the
   adjacent Tile's opposite side of the same physical edge; and
10. no mirror copy is written to the adjacent Tile. Edge queries inspect the
    owning side and the neighbor's opposite side.

The Tile exposes narrow mutation helpers used only by GridMap. Public gameplay
and content code never edits the dictionaries directly.

For every spatially present Entity:

1. `Entity.position` resolves to one live Tile;
2. that Tile contains the Entity UUID exactly once in `entity_uuids`;
3. no other Tile contains the UUID;
4. an undeployed or spatially suspended Entity occurs in no Tile even though
   its own position may retain its intended/last coordinate;
5. `GridMap.get_entity_position(uuid)` returns the Entity coordinate only when
   the matching Tile membership exists, otherwise `None`; and
6. `GridMap.get_entities_at(position)` reads only that Tile and returns a copy.

## 8. Item hierarchy and concrete semantics

Create `dnd/blocks/world_items.py`:

```text
BaseBlock
  BaseItem
    existing portable/usable/equipment items
    WorldItem
      CenterWorldItem
      BoundaryWorldItem
        BoundaryStructureItem
          BoundaryWall
          CliffFace
          RetainingWall
          BoundaryFence
    UsableItem
      BoundaryDoor
      WallTorch
```

This hierarchy does not use multiple inheritance.

### `WorldItem`

Owns explicit Pydantic fields:

- `occupies_bands: bool = Field(..., frozen=True)`;
- `vertical_extent_steps: int = Field(..., ge=1, frozen=True)`.

It overrides `get_world_placement_policy`. `CenterWorldItem` fixes `kind` to
`CENTER`; `BoundaryWorldItem` fixes it to `BOUNDARY`. Ordinary portable
`BaseItem` objects use the neutral BaseBlock policy and therefore remain
nonoccupying center objects when dropped.

### `BoundaryStructureItem`

Adds topology-defining frozen fields:

- `structure_kind: BoundaryStructureKind = Field(..., frozen=True)`;
- `material: MaterialKind = Field(..., frozen=True)`;
- `blocked_channels_closed: tuple[WorldEdgeChannel, ...] = Field(..., frozen=True)`.

It occupies bands by default. Its blocked-channel method returns current
mechanical state. A wall or cliff normally blocks movement, vision, light, and
propagation. A fence can expose a narrower tuple. A door returns the closed
tuple when closed and `()` when open. Placement direction is never stored on
the object.

The fields above may not drift while placed. Pydantic field-level freezing is
required because live `BaseBlock` deliberately has assignment validation
disabled. Changing extent, occupancy, placement kind, structure kind,
material, or closed-channel policy requires removing the object and creating
or explicitly re-placing a correctly configured object. This cut does not add
a resize/restructure transaction. Mutable mechanical state such as a door's
`is_open` changes only through the in-place GridMap transaction in Section
9.9.

### Usable boundary fixtures

`BoundaryDoor` remains a direct `UsableItem` subclass because live action
discovery, inventory use, and execution currently require `UsableItem`. It
declares the frozen boundary policy/structure fields and overrides all three
BaseBlock capability methods. `WallTorch` also remains a direct `UsableItem`
subclass, but it owns only a frozen nonoccupying boundary placement policy: it
returns no blocked channels and `None` from
`get_world_boundary_structure_state()`. It is an attachment, not a physical
edge structure. Neither class uses a mixin or multiple inheritance.

`BoundaryDoor` preserves `bind_dynamic_use_action()` and `get_use_actions()`.
`WallTorch` is a nonoccupying boundary fixture with no structural
contribution. Its `mount` API becomes:

```python
def mount(
    self,
    position: tuple[int, int],
    *,
    boundary_direction: CardinalDirection,
    base_height_steps: int | None = None,
    orientation: CardinalDirection | None = None,
    lit: bool = True,
) -> WorldObjectPlacement:
```

Delete `_wall_torch_position`. Lighting queries the authoritative placement;
the light source is anchored with `anchor_uuid=self.uuid` and joins the
BaseItem compound world-object receipt. Place/move uses the committed placement
position; removal removes/deactivates the source. No passive callback remains a
light state writer. Orientation alone does not move light. Phase 0 assigns an
explicit boundary to all active
arena, scenario, and test mounts before code changes.

The current call sites migrate with these explicit fixture semantics:

| Caller/position | Boundary |
|---|---|
| standard arena `(14, 1)` and `(14, 13)` | `EAST` outer boundary |
| multi-object dark battlefield `(4, 10)` | `WEST` control-room boundary |
| Sleet Storm regression `(10, 6)` and `(1, 1)` | `NORTH` test-fixture boundary |

These directions are game-space attachment facts, not renderer rotations. If
Phase 0 finds another active mount, implementation stops and adds it to this
table before the hard cut.

Replace `ItemDirectionalStructureState` with this exact cold event state in
`dnd/types/items.py`:

```python
class ItemBoundaryStructureState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    structure_kind: BoundaryStructureKind
    material: MaterialKind
    blocked_channels: tuple[WorldEdgeChannel, ...]
```

`ItemState` and `ItemObservationState` rename `directional_structure` to
`boundary_structure`. The state contains semantic kind/material and current
channels, not direction, occupancy, or extent. The universal placement embeds
the resolved policy, so occupying center objects and nonstructural boundary
attachments replay just as exactly as structural items without duplicating the
policy in item state.

### Existing concrete cut

| Current type | Target | Required change |
|---|---|---|
| `DirectionalWall` | `BoundaryWall` | one object occupies one chosen boundary; delete `blocked_directions` and all projected booleans |
| `DirectionalDoor` | `BoundaryDoor(UsableItem)` | preserve open/close/use discovery and binding; state changes channels, not placement |
| `DoorObject` | delete after callers move to `BoundaryDoor` | removes duplicate door family; do not leave alias |
| `wall_factory()` impassable Tile | retain as solid-cell terrain for this cut | it is not silently redefined as a boundary wall |
| portable torch/chests/cannons/levers/feast/dropped gear | center placement | preserve current item classes unless they genuinely require `CenterWorldItem` occupancy |
| active `WallTorch` | `WallTorch(UsableItem)` with boundary policy, `occupies_bands=False` | explicit authored side; delete private position; anchor light to UUID |
| future drape | `BoundaryWorldItem`, `occupies_bands=False` | may coexist with an occupying wall in the same bands |
| cliff/embankment/retaining wall | new `BoundaryStructureItem` subclasses | exact structure kind/material/extent; never inferred from height |

The door/torch action code may still resolve the linked UUID through
`BaseBlock` and validate the exact usable fixture type. Existing
`isinstance(..., UsableItem)` discovery/execution checks remain truthful. This
is action-domain validation, not a GridMap dependency.

## 9. GridMap API and algorithms

### 9.1 Stored indices

Replace:

```python
_object_positions: dict[UUID, tuple[int, int]]
_objects_by_position: defaultdict[tuple[int, int], set[UUID]]
```

with:

```python
_object_placements: dict[UUID, WorldObjectPlacement]
```

There is no third `objects_by_position` cache. `get_objects_at(position)` reads
that Tile's center and boundary bands, unions UUIDs, and returns a copy. Tile
lookup is O(number of objects on that Tile), not O(world objects).

Also delete all three duplicate entity-position stores:

```python
Entity._entity_by_position
GridMap._entity_positions
GridMap._entities_by_position
```

There is no replacement entity-position dictionary. `Entity.position` is the
UUID-to-position state and `Tile.entity_uuids` is the position-to-UUID index.
GridMap reads the former through `BaseBlock.get` and the latter through Tile.

### 9.2 Public placement API

This one-step GridMap API is public only for dependency-neutral non-item
BaseBlocks whose default-false `requires_compound_world_placement()` remains
false. `BaseItem` overrides it to true; GridMap rejects direct BaseItem calls
before mutation and the item uses the complete commands in Section 9.12.1.
Both paths use the same internal physical receipt, so GridMap still accepts
BaseBlock providers and remains the sole Tile-band/reverse-index writer.

```python
def place_object(
    self,
    object_uuid: UUID,
    position: tuple[int, int],
    *,
    boundary_direction: CardinalDirection | None = None,
    base_height_steps: int | None = None,
    orientation: CardinalDirection | None = None,
    parent_event: UUID | None = None,
) -> WorldObjectPlacement:
```

Rules:

- resolve the object through `BaseBlock.get`; missing UUID is an error;
- resolve the Tile; missing Tile is an error rather than a partial placement;
- call `get_world_placement_policy()` once;
- center policy rejects a boundary and rejects an explicit base unequal to
  `Tile.height`;
- boundary policy requires a boundary;
- omitted base defaults to `Tile.height`;
- omitted boundary orientation resolves to the boundary direction;
- omitted center orientation remains `None`;
- calculate exclusive top as `base + policy.vertical_extent_steps`;
- validate all local bands and the neighbor's opposite physical-edge bands;
- an already-placed UUID with the exact same resolved placement is idempotent;
- any different existing placement is rejected with an instruction to call
  `move_object`; it is not implemented as remove-then-place; and
- callers cannot pass occupancy or channels.

### 9.3 Atomic placement

Placement is one transaction under the single-process assumption:

1. resolve and validate every input without mutation;
2. build the frozen placement value;
3. construct the exact spatial fact and, for BaseItem, exact floor-location
   fact, then call `EventQueue.prepare_committed_lifecycle`/
   `prepare_completed_fact` to validate schemas, allocate every phase UUID, and
   collision-check them before mutation;
4. calculate the exact Tile bands and affected channel revisions;
5. write all Tile band occurrences;
6. write `_object_placements[uuid]`;
7. invalidate channel/path/FOV/light caches once;
8. publish only the already-prepared non-vetoable facts; and
9. return the placement.

For a boundary placement, the affected XY set is the owning position plus the
adjacent position across the boundary when that Tile exists. Move/state-change
invalidation uses the union of affected sets from old and new placements. This
set drives spatial subscriptions, senses, paths, FOV, propagation, and light;
invalidating only the owner Tile is incorrect.

The same prepare-before-mutate rule is mandatory for public move, orient,
remove, object-state change, `set_tile`, `remove_tile`, elevation, surface, and
rectangle operations. A public one-step mutation never constructs its event
after changing world state.

If steps 5 or 6 raise unexpectedly, restore touched bands and the old reverse
entry before publishing anything. Once state commits, prepared publication has
no schema/UUID/ordinary observer failure path; only fatal corruption in the
shared index core can interrupt it. The old allowance for an ordinary event
failure after state commit is deleted.

### 9.4 Move

```python
def move_object(
    self,
    object_uuid: UUID,
    position: tuple[int, int],
    *,
    boundary_direction: CardinalDirection | None = None,
    base_height_steps: int | None = None,
    orientation: CardinalDirection | None = None,
    parent_event: UUID | None = None,
) -> WorldObjectPlacement:
```

It preflights the destination while treating the moving UUID as absent, then
removes old bands and inserts new bands in one commit. It publishes one
`OBJECT_CHANGED` fact carrying both `previous_placement` and `placement`; it
does not publish a misleading remove/place pair.

### 9.5 Rotate

```python
def orient_object(
    self,
    object_uuid: UUID,
    orientation: CardinalDirection | None,
    *,
    parent_event: UUID | None = None,
) -> WorldObjectPlacement:
```

It changes only resolved orientation in every occupied band and the reverse
record. It cannot move an object between center/boundary or change the boundary
side. It publishes `OBJECT_CHANGED` with old/new placement.

### 9.6 Remove

```python
def remove_object(
    self,
    object_uuid: UUID,
    *,
    parent_event: UUID | None = None,
) -> WorldObjectPlacement | None:
```

It obtains all bands from the reverse placement, validates their consistency,
removes them, prunes empty band records, deletes the reverse entry, invalidates
caches once, publishes committed `OBJECT_REMOVED` with
`previous_placement`, and returns it. Missing placement is idempotently `None`.
The obsolete `clear_object_location` switch is deleted because the item no
longer stores floor location.

### 9.7 Queries

Add or replace with:

```python
get_object_placement(uuid) -> WorldObjectPlacement | None
get_all_object_placements() -> dict[UUID, WorldObjectPlacement]
get_objects_at(position) -> set[UUID]
get_center_objects_at(position, *, z: int | None = None) -> set[UUID]
get_boundary_objects_at(position, direction, *, z: int | None = None) -> set[UUID]
```

Without `z`, band queries union and deduplicate UUIDs. Returned collections and
models are copies/frozen values. Delete `get_object_position`; callers use
`get_object_placement(...).position`. Delete `get_all_object_positions` after
all callers migrate.

### 9.8 Rebuild and load validation

`GridMap.rebuild_object_placement_index()` is allowed only during load/reset.
It scans Tiles once, groups each UUID, and rejects:

- appearances in multiple Tiles or center/boundary locations;
- noncontiguous bands;
- different orientations among bands;
- partial or inconsistent occupant markers;
- a reverse placement inconsistent with the live provider policy;
- missing BaseBlock providers;
- center bases different from support height; and
- opposite-side occupant overlap on one physical edge.

It then replaces the reverse dictionary atomically. Runtime lookup never scans
the map.

### 9.9 In-place object state change

Add the missing mutation boundary used by doors and other stateful structures:

```python
def object_state_changed(
    self,
    object_uuid: UUID,
    *,
    previous_structure: ItemBoundaryStructureState | None,
    parent_event: UUID | None = None,
) -> WorldObjectPlacement:
```

The owning object captures its frozen previous structure snapshot and computes
the intended new structure/`ItemState` without assignment. GridMap first
preflights the transition and prepares every spatial/item fact. Only then does
the owning method assign local state and call the prepared commit. GridMap:

1. requires an existing placement;
2. obtains the current structure through
   `BaseBlock.get_world_boundary_structure_state()`;
3. rejects a structure kind/material change or a live placement-policy change;
4. computes changed channels from the symmetric difference of previous/current
   blocked-channel sets;
5. invalidates that channel set for both physical-edge positions exactly once;
6. publishes committed `OBJECT_CHANGED` with the unchanged placement; and
7. invokes the BaseItem location-state hook so the current `ItemState` is
   recorded with the same parent lineage.

`BoundaryDoor.set_open` uses this prepare/assign/commit boundary and never
assigns `is_open` when preflight fails. An unexpected assignment/commit failure
restores the captured value before publication. Direct assignment to spatially
meaningful mutable state is forbidden. This replaces
`BaseItem._notify_blocking_changed`; no new generic directional notifier
survives.

### 9.10 Populated Tile mutation rules

Tile placement storage may never be silently discarded or detached from its
reverse index:

- `set_tile` may create a missing Tile. Replacing an existing Tile is rejected
  while it has any center/boundary object, entity occupant, spatial-effect
  membership, or connector endpoint.
- `remove_tile` applies the same rejection rules.
- `set_tile_elevation` rejects a height change while any center object is
  placed because the center-base invariant would move. Boundary bands remain
  independent, but this cut still rejects the height change when any object is
  present so authored support/boundary edits are explicit and atomic later.
- surface-only change is allowed through `set_tile_surface` because it does not
  move bands.
- all rejections occur before mutation/event publication and leave serialized
  Tile/GridMap state and the event cursor unchanged.
- `get_tile_by_uuid` tests `position is not None`, fixing the live `(0, 0)`
  falsy-position bug.

The later declarative map builder creates support/elevation before objects, so
these conservative rules do not impede normal initialization.

Delete `fire_event` from `set_tile` and `remove_tile`, delete
`GridMap.disable_events`, `enable_events`, `_events_enabled`, `_pending_events`,
and `_pending_committed_events`, and remove any equivalent public suppression
switch. `create_rectangle` becomes a guarded loop over ordinary `set_tile`
transactions with explicit surface state; outside the EventQueue bootstrap
context every created Tile produces its committed fact. The EventQueue
context-local bootstrap gate in Section 12.3 is the only fact-suppression path.
Arena/scenario callers using `fire_event=False` migrate to normal calls inside
that context, never to a replacement bypass.

### 9.11 Item location and preflight transactions

Add `ItemLocation.UNPLACED` as the explicit state of a live item that belongs
to no floor, inventory, equipment, merge target, or destruction state. A bare
successful removal of a `BaseItem` therefore has a truthful terminal location;
it never silently lacks a location fact.

Add a BaseBlock postcommit hook taking the frozen placement and parent lineage;
the default is a no-op. BaseItem emits `ItemLocationStateEvent(UNPLACED)` only
when bare removal is the completed terminal operation. Placement emits
`FLOOR`. Composite higher-level item operations suppress the primitive
`UNPLACED` hook and own the one truthful final fact (`INVENTORY`, `FLOOR`,
`EQUIPMENT`, `MERGED`, or `DESTROYED`) because only those domains know the
final owner/container/slot/merge state.

Add `BaseItem.get_authoritative_location()` as a strict query, not stored state.
It resolves exactly one live source:

1. a GridMap placement means `FLOOR` and forbids owner/container/equipped state;
2. membership in the exact `Equipment` referenced by `stored_in_uuid` plus its
   occupied slot means `EQUIPMENT`;
3. membership in the exact `Inventory` referenced by `stored_in_uuid` means
   `INVENTORY`, whether the owner is an Entity or a container such as a chest;
4. no placement/membership/owner means `UNPLACED`; and
5. conflicting or stale evidence is an invariant error, never resolved by
   priority or `getattr` fallback.

`MERGED` and `DESTROYED` are terminal event facts for objects removed from the
live registry, not live source locations.

To resolve `stored_in_uuid` without `isinstance` or reflection, add the neutral
`BaseBlock.get_contained_item_location(item_uuid) -> ItemLocation | None`
capability returning `None`; Inventory returns `INVENTORY` only for an exact
member and Equipment returns `EQUIPMENT` only for an exact occupied slot. This
is part of the item-location cut, separate from the three world-placement
capabilities in Section 6.3.

The required source/destination matrix is:

| Source | Allowed operation/destination | Required preflight and facts |
|---|---|---|
| `FLOOR` | loot to inventory/merge; destroy; move | exact source placement; destination capacity/stack; removal topology then truthful final location |
| `UNPLACED` | scenario/character grant to inventory; explicit placement; destroy | verify no hidden owner/container; no false `OBJECT_REMOVED`; final inventory/floor/destroyed fact |
| entity `INVENTORY` | transfer, equip, drop, consume/destroy | exact source membership and target/slot/drop preflight; no spatial departure unless dropping creates arrival |
| contained `INVENTORY` | chest/container transfer, spill/drop, destroy | exact container membership and target capacity/all spill placements before removal |
| `EQUIPMENT` | unequip to inventory/drop; replace; consume/destroy | accepted equipment phase train, exact slot/hooks, final destination preflight |

`Entity.loot_item` therefore accepts both `FLOOR` and genuinely `UNPLACED`
items. Fresh scenario grants are `UNPLACED`; chest code may either transfer
directly from contained `INVENTORY` or remove it into a validated `UNPLACED`
state before loot. `Inventory.transfer_to` uses the same transaction and cannot
detach the source before target preflight. Destruction works from every live
source row, not only the floor.

Before the first mutation, each higher-level operation preflights every strict
destination:

- drop: destination Tile, center policy, every target band, and stack behavior;
- loot: the exact source row above plus target inventory capacity/stack result;
- equip: source location, equipment slot, and destination for every displaced
  item;
- merge: surviving stack identity/capacity and destroyed/merged remainder; and
- destroy: containment removal and any contained-item drop placements.

Add one internal frozen Pydantic `GridObjectMutationReceipt` in GridMap holding
`previous_placement`, `placement`, exact touched-band snapshots, and affected
channels/positions. The public one-step APIs use the same pure preflight and
silent commit primitives as higher-level item operations; they merely publish
immediately afterward. This is a rollback receipt, not a second placement or
event DTO.

After successful preflight, a higher-level operation mutates inventory,
equipment, stack state, item state, Tile bands, and reverse placements
synchronously **without publishing**. A normal validation failure is therefore
impossible after the first mutation. An unexpected exception uses the captured
Pydantic receipts to restore every structure before any event publication and
leaves the cursor unchanged.

Only after the complete state commit succeeds does it publish the prepared
spatial committed lifecycles, followed by terminal item-location snapshots.
Item snapshots that become simultaneously observable use
`EventQueue.register_completion_sequence`; do not use the current callback
batching context, which stores and exposes individual events early. Required
causal order is:

| Operation | Facts after full state commit |
|---|---|
| bare terminal removal | `OBJECT_REMOVED`, then `UNPLACED` |
| loot to inventory | `OBJECT_REMOVED`, then `INVENTORY` or `MERGED` |
| fresh/scenario `UNPLACED` grant | `INVENTORY` or `MERGED`; no removal fact |
| inventory/container transfer | source and target truthful `INVENTORY`/`MERGED` snapshots; no spatial fact |
| drop | `OBJECT_PLACED`, then `FLOOR` |
| equip | conflict unequip completion(s), equip completion, newly equipped item `EQUIPMENT`, then displaced-item final snapshot(s); add object placement facts only when displaced to floor |
| stack merge | survivor final snapshot, then source `MERGED` |
| destroy floor item | hook/contained-item child facts, `OBJECT_REMOVED`, then source `DESTROYED` |
| destroy inventory/equipped/unplaced item | accepted equipment removal when applicable, hook/contained child facts, container/source removal, then `DESTROYED`; no false spatial fact |

All state is already final when the first passive observer runs. Observer
failure cannot roll back committed state but the committed publisher guarantees
the corresponding completion remains stored.

### 9.12 Equipment and item lifecycle hooks

The placement cut must preserve existing hook mechanics and `EquipmentEvent`
coverage; Pydantic field rollback alone is insufficient.

#### Equipment phase train

For equip, unequip, replacement, and equipped destruction:

1. pure-preflight only each declaration and execution proposal, plus all item
   destinations and hook prerequisites; `EventQueue.preflight` remains limited
   to `DECLARATION` and `EXECUTION` because equipment `EFFECT` handlers are
   stateful reactions, not validators;
2. on ordinary rejection, publish nothing and mutate nothing;
3. publish the accepted declaration and execution proposals without
   redispatch, preserving their existing identities/order as reaction context;
4. capture lifecycle receipts, then commit the **complete** loadout: slots,
   ownership, placement,
   modifiers/handlers/conditions, and item hook state;
5. if that pre-EFFECT commit fails, restore every receipt and index one
   non-dispatched `CANCEL` record with
   `canceled_from_phase=EventPhase.EFFECT` for **every** published transition,
   in deterministic conflict-unequip order followed by equip; this terminates
   every accepted lineage while publishing no location/spatial completion for
   state that was rolled back;
6. after the whole loadout is committed, dispatch each real `EquipmentEvent`
   EFFECT exactly once through normal handler dispatch, in deterministic
   conflict-unequip order followed by equip; every EFFECT handler therefore
   observes the final loadout, as required by
   `test_committed_armor_effect_handlers_observe_the_final_loadout`; and
7. after EFFECT dispatch, publish each corresponding `EquipmentEvent`
   completion, then spatial lifecycles, then the newly equipped item's final
   snapshot followed by displaced-item snapshots in conflict order.

The preflight EventQueue context forbids child publication or game mutation.
No EFFECT is preflighted or published without dispatch. The first and only
EFFECT dispatch deliberately occurs after slot and hook mutation, because
rules such as Rage and Mage Armor must inspect and react to the final equipment
state.

Post-commit EFFECT failure is not a rollback boundary. Add one internal
`EventQueue.dispatch_postcommit_effect(execution)` path which first indexes the
EFFECT, then invokes each matching handler exactly once and returns both the
stored final EFFECT version and any raised/cancel-protocol failure to the
equipment transaction instead of losing the stored phase. A handler-returned
cancellation at this point is a protocol error: declaration/execution already
accepted and the loadout already committed, so it cannot unequip the item.

Before using that dispatcher, make `EquipmentEvent` a guarded event family by
overriding `validate_handler_result`. Define the guard by an exact allowlist,
not by trying to enumerate a partial causal-field denylist:

- handler-controlled fields are only `status_message`, `outcome_code`, and
  `outcome_source_entity_uuid`;
- `uuid`, `timestamp`, `modified`, and `use_register` may change only according
  to the existing generic guarded-version and registration rules;
- `children_events`, `lineage_children_events`, `children_lineages`,
  `identified_entity_observer_uuids`, `located_entity_observer_uuids`, and
  `located_position_observer_uuids` are deep-copied from actual queue-owned
  evidence on the current truthful event; handler-supplied values for them are
  never trusted; and
- every other public Pydantic model field must be exact-type and exact-value
  equal to the current truthful event. This includes concrete event class,
  `event_type`, `lineage_uuid`,
  `parent_event`, `parent_lineage`, `turn_execution_id`, source/target identity
  and names, `item_uuid`, `slot`, ordering flags, and any future field added to
  `EquipmentEvent` or `Event`.

This default-deny comparison makes future causal fields protected
automatically. Lifecycle handling is explicitly phase-specific:

- during DECLARATION or EXECUTION preflight, an ordinary unchanged result must
  retain the same `phase`, `canceled`, and `canceled_from_phase`; a validator may
  also make the one generic legal veto transition to `phase=CANCEL`,
  `canceled=True`, and `canceled_from_phase=<input phase>`;
- the guard never trusts the validator's cancel object directly. It constructs
  the canonical cancellation from the truthful input, copies immutable and
  queue-owned evidence from that input, and accepts only the allowlisted
  status/outcome plus valid generic UUID/timestamp/version metadata. This
  remains an ordinary precommit rejection: nothing is mutated or published by
  the transaction; and
- during postcommit EFFECT dispatch, `phase`, `canceled`, and
  `canceled_from_phase` must remain exactly unchanged. Any attempted EFFECT
  cancellation or immutable/queue-evidence rewrite is a postcommit protocol
  failure: the rejected proposal never replaces the indexed truthful EFFECT,
  and completion is derived from that last truthful EFFECT value.

Postcommit guard failures use the terminal failure sequence below; they are not
converted into vetoes of committed equipment.

Whether a handler raises or attempts cancellation, the transaction must:

1. retain the committed loadout and every already-published child fact;
2. index a truthful, non-canceled `EquipmentEvent` COMPLETION describing that
   committed transition;
3. publish the remaining spatial and final item-location snapshots in the
   normal order so replay sees the state that actually exists; and
4. only then re-raise/report the post-commit reaction failure.

It must not restore receipts after EFFECT dispatch starts: a stateful handler
may already have emitted child events or changed other game state, so such a
rollback would manufacture a false history. Tests must cover a raising EFFECT
handler, a canceling EFFECT handler, and EFFECT handlers that attempt to
rewrite causal or queue-owned evidence. They assert exactly one EFFECT
dispatch, no false causal replacement, completion from the last truthful
EFFECT, committed slots plus terminal equipment/location facts, and that the
failure is surfaced after those facts are indexed. The forged-evidence cases
must include `item_uuid`, `slot`, owner identity, `parent_lineage`, child-event
UUIDs, and observer-evidence maps. A separate guarded EXECUTION-validator test
must return `event.cancel(...)` and prove that it remains an ordinary
precommit veto with no state or cursor change.

#### Reversible hook receipt

Add a frozen Pydantic `ItemLifecycleReceipt`, owned by the item transaction,
with exact before/after ownership for:

- registered action/handler UUIDs;
- modifier/contribution UUIDs and their target values;
- conditions or feature handles installed/removed by equip/unequip;
- light-source state and source UUID;
- spatial-effect/controller/handler UUIDs created by destruction;
- BaseBlock registry entries removed by merge/destruction; and
- local item state changed by `_on_equip`, `_on_unequip`, `_on_drop`, and
  `_on_destroy`.

Each active hook in the Phase-0 ledger must either return this source-owned
receipt or be wrapped by a domain-specific receipt builder using explicit APIs.
Rollback removes/restores only those recorded handles—no registry snapshot,
reflection, or guessed inverse. Hooks that cannot yet supply a reversible
receipt block the cut; they are not silently called outside the transaction.

Required active migrations include portable Torch drop/destruction and its
light, OilBarrel destruction and its installed oil/controller handlers,
StorageChest contained-item spill, equippable handler/modifier hooks, and stack
merge/destruction registry removal.

#### Postcommit event order

| Operation | Required order after accepted precommit phases and successful state commit |
|---|---|
| equip/replace/unequip | conflict `EquipmentEvent` completions, equip completion, spatial facts for any floor transition, newly equipped final snapshot, then displaced final snapshots in conflict order |
| charge without destruction | `ItemChargeConsumptionEvent` completion; location is unchanged and no redundant location event is required |
| charge causing destruction | preflight source removal/equipment transition first; equipment completion if applicable, hook-derived child light/effect facts, spatial removal if floor, child `DESTROYED`, then parent `ItemChargeConsumptionEvent` completion |
| ordinary destruction | equipment completion if applicable, hook-derived child light/effect/spill facts, spatial removal if floor, then `DESTROYED` |
| container destruction | preflighted contained-item placement/final-location hook facts, container spatial removal, then container `DESTROYED` |

Hook-derived events preserve their current causal parent (damage, charge
EFFECT, action, or destruction cause), whose accepted phase is already indexed;
their state was included in the successful receipt commit. Prepared hook facts
are published before the terminal item-location snapshot exactly as the live
tests require. For charge destruction, `DESTROYED` is a child completion of the
already-indexed charge EFFECT and therefore precedes the parent charge
COMPLETION. The existing equipment replication ordering assertions remain
normative and are updated only for the new exact location payload.

### 9.12.1 World-object anchor compound mutation

World-object lights/effects cannot remain passive postcommit callback
mutations. A callback exception would leave authoritative placement committed
while its anchored mechanics stayed at the old cell. Continual Flame also
currently lets both GridMap and its controller move the same light.

Keep GridMap as the core physical store accepting dependency-neutral BaseBlock
UUIDs, but split its physical object methods into internal
prepare/commit/rollback/publish receipt primitives. `BaseItem` overrides one
default-false BaseBlock capability indicating that its world placement requires
the complete item/location/anchor orchestration. Direct one-step GridMap calls
reject such providers. The public BaseItem floor commands are
`place_in_world`, `move_in_world`, `orient_in_world`,
`world_state_changed`, and `remove_from_world`; all former BaseItem
`place_on_map`/direct GridMap callers migrate to them. They compose:

1. the internal GridMap Tile-band/reverse-placement receipt;
2. the ItemLocation/ItemState receipt;
3. all attached light sources, affected Tile modifiers, and suppression tokens;
4. every world-object-anchored SpatialEffect/controller receipt; and
5. every already-prepared placement, location, light, condition, and
   effect-change lifecycle.

Put the non-core composition mechanics in
`dnd/spatial/anchor_mutations.py`. `BaseItem` may import this module;
`dnd.core` does not. The module imports the GridMap receipt API plus
`dnd/spatial/effect_base.py`, never authored content or concrete recipes, and
uses existing direct effect/controller objects. This produces the acyclic
direction `BaseItem -> spatial.anchor_mutations -> spatial.effect_base -> core`.
No core-to-spatial import, late import, protocol gateway, reflection, or global
installer is added.

SpatialEffect installation/removal maintains one exact anchor-owned UUID list
on the BaseBlock, analogous to its existing attached-light UUID list. It is an
ownership relation, not another position index, and validation requires each
listed effect's `anchor_uuid` to equal that block. This lets BaseItem enumerate
attachments without a global scan and lets GridMap reject an incomplete direct
mutation.

Move commits physical placement, anchored light position/illumination, effect
footprint/controller contributions, and all rollback state together. Removal
commits physical removal, location state, attached-light cleanup/deactivation,
and the existing world-object effect retirement. Only after the shared commit
does it publish object EFFECT, anchored light/effect children, object
COMPLETION, and the final item-location fact in the order already specified.
Orientation-only changes do not relocate anchors. Continual Flame's controller
is split so it prepares only its effect footprint; the compound receipt is the
sole owner of its object-anchored light relocation/removal.

The old world-object anchor `EventHandler` and GridMap light callback branches
are deleted as state writers. Passive callbacks may observe detached completed
facts but cannot mutate anchored state. Phase 0 proves the current authored
world-object set (currently Continual Flame), every attached-light caller, and
every BaseItem production placement caller before switching the boundary.
Tests inject prepare and commit failures and prove complete placement, light,
effect/controller, condition, registry, and cursor rollback. Separate
postcommit child/observer/projection failures prove that committed anchor state
and already-indexed facts remain, every remaining child/system runs,
COMPLETION is guaranteed, and diagnostics/failures surface only afterward.
They also prove exactly one Continual Flame light relocation owner.

### 9.13 Entity position and Tile occupancy

This cut keeps position on the Entity. It removes duplicate authorities rather
than moving actor state into GridMap.

`Entity` overrides the existing dependency-neutral method:

```python
def set_position(self, position: tuple[int, int]) -> None:
    self.position = position
    self.senses.set_position(position)

def supports_spatial_actor_occupancy(self) -> bool:
    return True
```

This is the only production assignment boundary for the actor and its isolated
Senses component mirror. GridMap calls it polymorphically through
`BaseBlock.get(entity_uuid)` only after the default-false
`supports_spatial_actor_occupancy()` capability accepts the block. A Tile,
item, condition, or arbitrary BaseBlock UUID is therefore rejected before
occupancy mutation. GridMap never imports Entity and uses no reflection. Other
entity-owned blocks are not recursively rewritten unless their existing
semantics expressly require the actor coordinate.

`Entity` also owns one explicit `is_spatially_suspended` boolean. The state
matrix is closed:

| State | in `Game.entities` | `is_deployed` | `is_spatially_suspended` | Tile membership | spatial-senses observer |
|---|---:|---:|---:|---:|---:|
| not deployed (fresh or deliberately detached) | no | false | false | no | no |
| active in world | yes | true | false | exactly one | yes |
| temporarily suspended | yes | true | true | no | no |

The retained `Entity.position` in the suspended state is the return
coordinate, not active occupancy. Deliberate Game detachment is reversible:
the Entity retains its semantic state and may later be deployed again. This
plan does not invent terminal destruction. Existing explicit Entity destruction
is a separate irreversible capability and is not called by Game detachment.

Do **not** expose lifecycle-changing GridMap calls as an independently usable
public API. Actor lifecycle state spans Game, Entity, Tile membership, senses,
attached light/effect state, and event publication; a caller that mutates only
GridMap cannot maintain that state machine.

The public command boundary is exactly:

```python
Game.deploy_entity(entity, position, *, parent_event=None)
Game.undeploy_entity(entity_uuid, *, parent_event=None)
Entity.move(position, *, parent_event=None)
Entity.suspend_spatially(*, parent_event)
Entity.restore_spatially(*, parent_event)
```

GridMap supplies dependency-neutral **internal** receipt primitives such as
`_prepare_actor_transition`, `_commit_actor_transition`,
`_rollback_actor_transition`, and `_publish_actor_transition`. Only
`dnd/game.py` and `dnd/entities/entity.py` may call them. They resolve the block,
validate old/new Tile membership plus the default-false actor capability,
prepare exact LEFT/ENTERED lifecycles, and capture/restore GridMap-owned state.
They never decide or mutate `is_deployed`, `is_spatially_suspended`, Game
ownership, observer ownership, attached-effect lifetime, or condition state.
The Game/Entity command composes the GridMap receipt with those higher-owned
values into one transaction and is the only public committer/publisher.

GridMap's public actor surface is read-only:
`get_entity_position(entity_uuid)` and `get_entities_at(position)`. Any
standalone call to a lifecycle-changing GridMap actor primitive is forbidden by
an architecture caller-boundary test. This is an enforceable underscore
boundary backed by the test; it is not a capability inferred from a live
Entity or a reflection hook.

`Entity.suspend_spatially` is the Banishment-style operation: it retains
`Entity.position` as the return coordinate while the compound receipt removes
active Tile membership and actor-owned spatial contributions. Restore validates
that retained coordinate and reinstalls the complete active contribution before
ENTERED. `Game.undeploy_entity` is reversible world detachment and returns the
intact Entity. Bootstrap/teardown uses the one approved bootstrap publication
context; it does not gain another silent flag.

### 9.13.1 Deployment ownership and transaction order

The complete deployment transaction has three explicit owners:

- `Game` owns `Game.entities` and is the sole public deploy/undeploy
  boundary;
- `Entity` owns `is_deployed`, `is_spatially_suspended`, and registration of
  its `spatial_senses_system` observer; and
- `GridMap` owns Tile membership, cell subscriptions, block-light
  suppressions, attached-light projection, spatial-effect footprint indexes,
  spatial revisions, and LEFT/ENTERED publication.

`Game.deploy_entity` executes:

1. pure preflight of committed entity identity, Game UUID ownership,
   `is_deployed == False`, `is_spatially_suspended == False`, actor capability,
   destination Tile/rules, observer identity, and the complete preprepared
   ENTERED lifecycle;
2. add the Entity to `Game.entities`, set `is_deployed=True`, register its
   spatial-senses observer, add Tile membership/subscriptions, set
   Entity/Senses position, and invalidate spatial caches;
3. if any step before event indexing fails, restore Game ownership, flags,
   observer registration, subscriptions, Tile membership, position, attached
   light/effect state, suppression tokens, and cache revisions from exact
   captured values; and
4. publish the preprepared postcommit ENTERED lifecycle. A postcommit reaction
   failure is surfaced only after the Entity remains fully Game-owned and
   active; it is never rolled back out of `Game.entities`.

Ordinary movement retains Game ownership, both Entity flags, and observer
registration. It atomically changes old/new Tile membership, Entity/Senses
position, subscriptions, every UUID-anchored light, every Entity-anchored
spatial-effect footprint/controller contribution, and affected spatial
revisions before LEFT then ENTERED dispatch.

Suspension retains `Game.entities` and `is_deployed=True`, sets
`is_spatially_suspended=True`, unregisters the spatial-senses observer, removes
Tile membership/subscriptions and active attached-effect footprints, and adds
one dedicated actor-suspension light-suppression token before LEFT. It does not
erase any independent suppression token. LEFT handlers therefore see a still
Game-owned but objectively absent actor. Restore requires that exact suspended
state, re-adds membership/subscriptions and attached-effect footprints, removes
only the actor-suspension light token, re-registers the observer, sets
`is_spatially_suspended=False`, and then publishes ENTERED. Another token such
as DEAD continues suppressing the light. Prepublication failure restores the
prior suspended state; postcommit reaction failure retains the active restored
state.

`Game.undeploy_entity` and `Game.close` preflight the detachment LEFT lifecycle,
then remove `Game.entities`, set `is_deployed=False` and
`is_spatially_suspended=False`, unregister the observer, remove Tile
membership/subscriptions, add the dedicated `actor_not_deployed` light token,
and transition Entity-anchored effects to retained empty footprints before LEFT
dispatch. LEFT handlers therefore see the detached state. A prepublication
mutation failure restores every owner; a postcommit reaction failure leaves the
Entity truthfully detached and is surfaced afterward. A later deploy removes
only `actor_not_deployed`, restores attachments at the requested coordinate,
and preserves every independent suppression. No attached source/effect is
destroyed by Game ownership changes.

### 9.13.2 Attached lights and Entity-anchored spatial effects

The actor receipt explicitly owns two existing spatial capabilities which the
old completion callbacks currently update too late.

For every light UUID returned by `Entity.get_attached_light_sources()`, prepare
and capture its `LightSourceData`, affected Tile modifiers, exact suppression
token set, and light/FOV revisions. Deploy/move places or relocates its source
and illumination during the compound commit, before LEFT/ENTERED EFFECT
handlers observe final state. Suspension adds only the dedicated
`actor_spatially_suspended` token and removes illumination while retaining the
source. Restore removes only that token and reapplies illumination only if no
other token remains. Game undeploy adds `actor_not_deployed` and retains the
source; redeploy removes only that token. Explicit irreversible Entity
destruction, outside this Game-detachment cut, remains the owner that deletes
attached sources. The old
ENTERED-completion light mover is deleted for Entity anchors; it cannot remain
as a second writer. Every emitted light fact is prepared with the actor facts
and included in the predetermined publication sequence.

For each active `SpatialEffect` whose `anchor_kind` is `ENTITY` and whose
`anchor_uuid` is the actor, the receipt captures effect/controller footprints,
GridMap layer entries, interaction/anchor handlers, terrain/light/modifier
contributions, and controller ownership. Move relocates the footprint and
controller contributions in the same commit and prepares one truthful
`FOOTPRINT_CHANGED` lifecycle. Suspension is not retirement: it changes the
active footprint to empty, removes the corresponding world contributions and
handlers, retains the effect/controller/anchor ownership, and publishes
`FOOTPRINT_CHANGED(previous -> empty)`. Restore reinstalls the prepared
footprint at the retained coordinate and publishes
`FOOTPRINT_CHANGED(empty -> restored)`. Game undeploy uses the same retained
empty-footprint state as suspension, and redeploy restores it at the requested
coordinate. Only explicit irreversible Entity destruction retires the attached
effect and publishes its existing `REMOVED` lifecycle. Game ownership changes
never destroy it.

Phase 0 must prove the complete active Entity-anchor ledger, not just the base
controller class. The current authored set is exactly Spirit Guardians,
Leadership, Draconic Presence, and Antimagic Field. For each controller,
preparation audits `relocate_anchor`, `apply_effect_exit_trigger`,
`apply_effect_entry_trigger`, footprint transitions, and owned cleanup. The
shared receipt additionally captures:

- stable old-only/new-only occupant UUID lists and first-per-turn admission
  maps;
- Spirit Guardians membership-source/manifestation condition trees, exit
  cleanup, entry save/damage/slow consequences, and trigger admission;
- Leadership membership leases, potency promotion/reconciliation, modifier
  ownership, and exact ally entry/exit results;
- Antimagic `SpellProtectionRegistry` rows, suppression-marker condition trees,
  the conditions held by those markers, and exact restoration/resuppression
  state; and
- Draconic Presence's reindexed turn-start handler, source-specific immunity,
  and admission state.

Movement, suspension, restore, and undeploy prepare every membership-condition
application/removal lifecycle and every registry/marker mutation before the
actor commit. State-bearing membership/protection/suppression changes join the
reversible silent commit. After commit, publish the existing
`FOOTPRINT_CHANGED` EXECUTION and EFFECT, then stable-order old-only departure
condition lifecycles/reactions and stable-order new-only arrival condition
lifecycles/gameplay reactions, all parented to that footprint EFFECT. Publish
the `FOOTPRINT_CHANGED` COMPLETION only after every predetermined child has
settled so its frozen lineage/projection/combat-log state is complete. Suspension
and undeploy use old-only departures into an empty footprint; restore/deploy
use new-only arrivals from empty. Explicit destruction retires the effect only
after the same departure cleanup.

Random saves/damage and other gameplay reactions are not rolled back after the
footprint fact commits. Their target list and admission state are prepared;
raise/cancel/rewrite failures are accumulated while the remaining prepared
condition/fact sequence and remaining target reactions continue, then surfaced.
This preserves the concrete behavior rather than merely moving stored cells.

These effect mutations reuse the narrow prepared controller mutation specified
by the spatial-effect recovery plan and owned exactly by
`dnd/spatial/controller_mutations.py`; they do not call ordinary publishing
condition apply/cleanup during the actor commit. That lower module owns the
frozen common Pydantic receipt and condition-lifecycle helpers but imports no
Entity, BaseItem, effect_base, or concrete controller. Concrete controller
modules extend the receipt with their cold exact state. Entity calls the typed
`SpatialEffect.prepare_anchor_transition`/commit/rollback/publish boundary;
BaseItem reaches the same boundary through `anchor_mutations.py`. Neither
imports `effect_controllers.py`. The executable order is: master Phase 3C event
foundation, recovery Phase 2's exact lower primitive, then master Phase 3D
actor authority and Phase 3F BaseItem anchor authority. Full authored reaction
binding may continue afterward. This one shared primitive prevents either
document from inventing a second effect transaction or a cycle through the
live concrete controller module.

Publication preserves one causal order after the shared state commit:

- move: actor LEFT, actor ENTERED EFFECT, attached-light relocation facts and
  attached-effect `FOOTPRINT_CHANGED` children, then actor ENTERED COMPLETION;
- suspend: actor LEFT EFFECT, light-suppression and effect
  `FOOTPRINT_CHANGED(previous -> empty)` children, then LEFT COMPLETION;
- restore/deploy: actor ENTERED EFFECT, light activation and effect
  `FOOTPRINT_CHANGED(empty -> restored)` children when applicable, then
  ENTERED COMPLETION; and
- Game undeploy: actor LEFT EFFECT, retained-light suppression and effect
  `FOOTPRINT_CHANGED(previous -> empty)` children, then LEFT COMPLETION.

The state is already final when the parent EFFECT is dispatched. The publisher
captures failures, finishes every predetermined child and the parent
COMPLETION, then surfaces the accumulated error. No completion callback performs
a second relocation or cleanup.

### 9.13.3 Actor-transition re-entrancy fence

An Entity cannot begin another spatial transition while its current
LEFT/ENTERED lifecycle and attached children are being finalized. Otherwise an
ENTERED handler such as Gust of Wind can synchronously move B -> C inside the
outer A -> B EFFECT and cause the outer completion to lie about B.

The fence is Entity-owned and per actor. The public `Entity.move` rejects a
direct re-entrant call. A handler that legitimately causes movement uses one
narrow Entity method to defer the **entire causal command**, not just its final
position write. The private runtime queue holds callables, matching the existing
handler model; it is not serialized game state, a DTO, or a registry. Gust
therefore queues its complete forced-movement declaration/execution/move/
completion operation before publishing any part of that nested command.

After the outer actor COMPLETION and every attached child has been indexed, the
Entity clears the fence and drains deferred commands FIFO. A deferred command
must **not** become a late child of that completed lineage: EventQueue freezes
`children_lineages`, combat-log subentries, and subjective projection at
COMPLETION. Instead, extend the existing `ForcedMovementEvent` with one frozen
optional `trigger_event_uuid`. The queued Gust command publishes a new
top-level forced-movement root (`parent_event=None`) whose
`trigger_event_uuid` is the exact outer ENTERED EFFECT UUID. The reference is
audit/causal evidence, not parent lineage and not a second state model. The
root therefore receives its own projection and combat-log callback exactly
once, while the completed A -> B lineage remains immutable and truthful. A
command failure does not reopen or rewrite the completed outer transition.
Phase 0 inventories every spatial handler that can cause actor movement;
architecture tests forbid a direct `Entity.move` call from such a handler.
Gust is the required A -> B followed by independently completed B -> C root
regression.

`ForcedMovementEvent.validate_handler_result` becomes an explicit family
guard. It preserves existing legal forced-movement handler behavior but
requires `trigger_event_uuid` to remain exactly equal to the truthful input on
every produced phase. When that field is non-`None`, `parent_event` must remain
`None` for the entire independent root lineage. Concrete class, event type,
UUID/lineage, source/target, and queue-owned evidence retain the ordinary
guarded-event protections; only the canonical same-family cancellation remains
legal before movement commits. A handler rewrite of the trigger reference or
attempt to attach the deferred root as a child is rejected/canceled before the
state transition and is covered by a direct regression. Pydantic field
freezing alone is not treated as protection because handler versions use
`model_copy(update=...)`.

### 9.13.4 Banishment occupied return

Preserve the current occupied-return capability through Entity commands.
`BaseCondition.cleanup_own_state` gains one pure
`preflight_removal(expire, parent_event)` hook, defaulting to success and
running **before** `_declare_removal_event`. It may validate and prepare a
subclass removal plan but may not mutate or publish. `BanishedCondition`
overrides it to inspect the retained return Tile. If another blocking
occupant is present, deterministically test the existing neighbor order
`N, E, S, W, NE, NW, SE, SW`, preflight that occupant's complete move and the
banished Entity's restore as one compound Entity-owned receipt. The prepared
receipt is a nonserialized Pydantic private attribute consumed exactly once by
`_remove`; it is never a registry or parallel saved state.

All three lifecycles are prepared before the compound mutation. After commit,
publication continues through all truthful lifecycles even if an earlier
postcommit handler fails; captured failures are surfaced only after the target
ENTERED completion exists.

If no admitted adjacent destination exists, preflight returns false **before
the condition-removal declaration**, with the target still suspended, the
occupant unmoved, and an unchanged event cursor.
It never restores into an illegally occupied Tile and never performs half of
the compound move. The ported legacy regression proves both the successful
occupied return and the no-destination rollback.

On success, condition-removal DECLARATION and EXECUTION handlers first run
under the pure EventQueue mutation/publication fence. Their accepted canonical
values and every spatial/condition lifecycle are preallocated and
collision-checked, but **nothing is indexed**. Only then does the compound
actor mutation commit. If it raises, every owner is restored and the cursor,
lineage, and condition remain unchanged.

After a successful commit, index the already-accepted condition-removal
DECLARATION and EXECUTION without redispatch, then dispatch/index the guarded
condition-removal EFFECT while its lineage remains open. Publish occupant
LEFT/ENTERED and target ENTERED as stable-order children of that EFFECT, then
publish condition-removal COMPLETION only after all three causal actor
lifecycles settle. The postcommit coordinator continues through every spatial
and condition fact even if a handler raises or attempts a forbidden rewrite,
and surfaces accumulated failures only after the condition COMPLETION exists
with complete child lineage/projection evidence.

The existing `Entity.update_entity_position` is removed or becomes a private
implementation detail of `Entity.move`; it cannot remain a second public
command. `Entity.move` owns the compound command and calls the internal GridMap
receipt primitives. It never edits a registry ad hoc.
Delete `Entity.get_all_entities_at_position`; callers use
`GridMap.get_entities_at` and resolve UUIDs through the ordinary entity/block
registry when they require live objects.

Entity LEFT/ENTERED facts are different from passive object placement facts:
their EFFECT phase drives existing entry/leave hazards and spatial membership
rules. Add `EventQueue.publish_prepared_postcommit_lifecycle(prepared)`, using
the same fully preallocated `PreparedCommittedLifecycle` value as passive
committed facts but a different publisher:

1. preparation allocates/collision-checks EXECUTION, EFFECT, and COMPLETION UUIDs
   and snapshots every causal field before mutation;
2. after commit, index the already-prepared EXECUTION;
3. index the already-prepared EFFECT, dispatch its spatial handlers exactly
   once against final state, LEFT before ENTERED, and retain real child facts;
4. accept only the guarded annotation fields from handler results; cancellation
   or protected-field rewrite becomes a captured protocol failure;
5. derive/index truthful COMPLETION from the last truthful EFFECT even when a
   handler raises or violates the guard; and
6. return the completion plus captured postcommit failure so the caller can
   surface it after all committed position facts exist.

Passive object/Tile facts continue using `publish_committed_lifecycle`, which
dispatches no modifying handlers. No phase UUID is allocated after world
mutation in either path.

For ENTITY_LEFT/ENTITY_ENTERED at EFFECT,
`SpatialChangeEvent.validate_handler_result` is default-deny:

- handler-controlled fields are only `status_message`, `outcome_code`, and
  `outcome_source_entity_uuid`;
- concrete class, `event_type`, phase, UUID/lineage/parent, entity/source/target
  identities, `position`, `old_position`, transition metadata, and every other
  causal payload field must exactly match the truthful event; and
- children and all identified/located/position observer evidence are copied
  only from EventQueue-owned state, never accepted from handler output.

This guard is phase/event-type specific; it does not silently change ordinary
cancelable `SpatialChangeEvent` command paths.

An EFFECT cancellation cannot undo committed movement and is a protocol
failure. Movement vetoes remain on the existing precommit movement/action
events. This storage hard cut does not redesign movement cost, opportunity
attacks, connectors, forced movement, or encounter decisions.

Reads are equally narrow:

- `get_entity_position(uuid)` resolves `BaseBlock.position`, then returns it
  only if the corresponding Tile contains the UUID;
- `get_entities_at(position)` returns a copy of that Tile's UUID set; and
- code already holding an Entity reads `entity.position` directly.

`Senses.entities`, `Senses.objects`, sensory snapshots, completed events, and
subjective reducers deliberately retain their own observed/historical
positions. They are perception/history, not competing objective authorities.

## 10. World-edge derivation

Convert `AdjacentEdgeKey`, `WorldEdgeStructuralContribution`, and
`WorldEdgeView` in `dnd/core/world_edges.py` to frozen, `extra="forbid"`
Pydantic models while preserving their present equality and validation.
Do not replace `GridEntityPositionReceipt`; delete it with the staged duplicate
index path. Entity position/occupancy is explicitly in scope in Section 9.13.

Extend `WorldEdgeStructuralContribution` with:

```python
provider_uuid: UUID
owner_tile_uuid: UUID
owner_direction: CardinalDirection
base_height_steps: int
top_height_steps: int
structure_kind: BoundaryStructureKind | None
material: MaterialKind | None
blocked_channels: tuple[WorldEdgeChannel, ...]
```

For adjacent Tiles, GridMap creates the canonical edge once and reads providers
from both relevant Tile-side dictionaries. It deduplicates UUIDs, validates
opposite-side consistency, resolves current blocked channels through
`BaseBlock`, resolves kind/material through the neutral structure-state hook,
and emits contributions in deterministic UUID order. A boundary provider with
nonempty blocked channels but no boundary structure state is invalid; a
nonblocking attachment with no structure state is present in placement facts
but contributes no physical edge blocker.

Delete `Tile.allows_direction`, `allows_directions`, `set_border`,
`set_object_border`, GridMap `set_tile_directional_border`,
`recompute_tile_directional_blocking`, `_directional_block_map`, and the flat
directional metadata projection after all edge callers move.

Transition rules after the cut:

1. center blockers remain cell occupancy queried through existing
   `blocks_walking`/`blocks_vision` behavior;
2. boundary blockers are read only from edge contributions;
3. ordinary walking between unequal support heights remains rejected before
   blocker evaluation unless existing progressive stairs/ramp rules or a
   connector permit it;
4. walking between equal-height supports tests movement contributions against
   `[support_height, support_height + 1)`;
5. progressive stairs/ramp walking from heights `a` to `b` tests the swept
   movement interval `[min(a, b), max(a, b) + 1)`; any movement contribution
   intersecting that half-open interval blocks the transition;
6. connectors remain separate transfer edges governed by their connector
   definition and endpoint validation; a boundary item never creates a
   connector implicitly;
7. flying, swimming, and burrowing currently have no persistent altitude/depth
   coordinate. Preserve the live conservative 2D directional behavior: any
   boundary contribution with the movement channel blocks those modes,
   regardless of its z interval. Elevation support itself remains ignored for
   flying exactly as today; and
8. vision, light, and propagation remain the current 2D conservative model in
   this cut: any contribution whose interval rises above the lower endpoint
   support and whose current channels include the query channel blocks it; and
9. full eye-height, aerial, swimming-depth, burrowing-depth, and vertical-ray
   rules are explicitly deferred.

Subjective edge queries use the same contributions but omit a provider that
`provider.is_perceivable_by(requester_uuid)` says the observer cannot perceive.
They do not fall back to scanning every object in either cell.

## 11. Support height, cliffs, and connectors

### 11.1 Mechanical separation

- support: `Tile.height`, `elevation_surface_kind`, `slope_axis`;
- boundary volume: z-banded `BoundaryStructureItem` placement;
- traversal: progressive surface rule or `TraversalConnector`;
- rendering: client binding from semantic facts.

`GridMap.place_object` never changes support height. `set_tile` never invents a
cliff. Later content operations may compose both atomically, but the core
primitives stay separate.

### 11.2 Authoring validation

Add a pure `GridMap.validate_authored_height_boundaries()` report used by map
content finalization, not by ordinary mechanical mutation. For each exposed
height interval on an adjacent edge it reports uncovered boundary bands and
overlapping occupying structures. It does not invent a fallback material or
asset and does not make a mechanically valid experimental map impossible to
construct incrementally.

The later declarative content layer must run this validator before publishing
`WorldInitializedEvent` for a renderable authored map.

### 11.3 Connectors

Keep connectors in GridMap's existing separate graph unchanged. Do **not** add
the previously considered partial `provider_uuid`: correct provider ownership
would require an atomic migration of connector definition, digest, runtime and
reverse indices, change events, world initialization, and removal lifecycle.
That is deferred as one later connector cut.

Do not add a connector for a cliff by default. Do not use a connector for
ordinary progressive stairs/ramps. Existing connector content identity and
presentation cleanup also remains outside this cut; the new placement/event
contracts do not copy those fields.

## 12. Event and replay contract

Events are the authoritative history. No projection type is inserted above the
event stream.

### 12.1 Spatial events

Evolve `SpatialChangeEvent` rather than add a parallel placement event:

```python
placement: WorldObjectPlacement | None = None
previous_placement: WorldObjectPlacement | None = None
tile_state: WorldTileState | None = None
previous_tile_state: WorldTileState | None = None
```

Required combinations:

| Change | `placement` | `previous_placement` |
|---|---|---|
| `OBJECT_PLACED` | required | `None` |
| `OBJECT_REMOVED` | `None` | required |
| object move/orientation change | required | required |
| door mechanical state change | current placement required | same placement allowed |

Tile fact combinations are equally closed:

| Change | `tile_state` | `previous_tile_state` |
|---|---|---|
| `TILE_CREATED` | required | `None` |
| `TILE_CHANGED` | required | required |
| `TILE_REMOVED` | `None` | required |

Add `GridMap.set_tile_surface(position, surface, *, parent_event=None)` as the
only runtime surface mutation. It validates and commits the complete
`TileSurfaceState`, invalidates the channels whose mechanics actually changed,
and emits a terminal `TILE_CHANGED` fact. Later burning/freezing rules call this
boundary; they never mutate `Tile.surface.cover` directly.

For these object state facts, delete flat `directional_position`,
`directional_directions`, the four directional-block maps, and
`object_map_char`. Keep exact mechanical booleans only where another
non-placement object state genuinely requires them; derive edge topology from
the provider plus placement, not event maps.

Object placement/removal/move/orientation and Tile create/change/remove facts
are post-commit and non-vetoable. The current
`GridMap._fire_committed_spatial_event` does **not** satisfy this contract: its
unregistered EXECUTION/EFFECT values are invisible and only COMPLETION is
stored. Replace it with preparation followed by
`EventQueue.publish_committed_lifecycle(prepared, publish_children=None)` and a
thin GridMap delegate. BaseItem supplies its already-prepared anchored
light/effect publisher through that hook; an unanchored Tile/object fact leaves
it `None`.

Add frozen Pydantic `PreparedCommittedLifecycle` and `PreparedCompletedFact`
receipts inside `events_registry.py`. `prepare_committed_lifecycle(event)`
accepts one unregistered declaration-shaped event, constructs exact
EXECUTION/EFFECT/neutral-COMPLETION versions with fresh UUIDs in one lineage,
validates every schema, collision-checks the complete UUID set, and snapshots
their causal fields. `prepare_completed_fact(event)` performs the equivalent
work for one terminal fact. These pure methods index nothing and run no
observer/handler/projection.

The new publishers accept only those prepared receipts; they do not register
DECLARATION and never call `EventQueue.register`. Extract
one minimal `_index_authoritative_event()` from the
existing `_store_event` implementation. It is the **single** owner of all
UUID/lineage/timestamp/type/phase/source/target/all-events and parent/child index
mutation and cannot invoke observer computers, projections, handlers, or
callbacks. Normal `register`/`_store_event`, committed lifecycles, completed
facts, and completion sequences all delegate to this exact core;
`_store_event` retains only its normal projection/handler/notification wrapper.
There is no parallel second index writer. After domain state commits, the
prepared committed publisher indexes, in order:

1. `EXECUTION`;
2. `EFFECT`;
3. the explicit domain `publish_children` sequence, when present;
4. every registered **stateful child-producing pre-completion system** in its
   existing stable order, including `SpatialSensesSystem`; and only then
5. neutral causal `COMPLETION` with notifications disabled, followed by pure
   completion projection, whitelisted projection attachment, and detached
   passive completion notification.

`publish_committed_lifecycle(prepared, publish_children=None)` is the passive
route for Tile/object state facts. It performs the sequence above, including
the same bounded hook between EFFECT and stateful pre-completion systems, but
dispatches **no modifying EventHandler or SpatialHandler at any phase**. The
hook receives the truthful stored EFFECT and is the sole BaseItem route for
publishing its prepared anchored-light and anchored-effect children before the
object COMPLETION freezes lineage. Child failures are accumulated; the
publisher continues stateful pre-completion systems, guarantees COMPLETION,
and surfaces diagnostics/failures afterward. It provides no callback-based
state mutation authority: the BaseItem compound mutation already committed all
placement/light/effect state, and the hook publishes only its resulting facts.

All three versions have `canceled=False`. After authoritative EFFECT indexing,
passive observers receive deep detached copies, never the stored mutable
object. Return values are ignored; exceptions are caught and converted to
diagnostics. The stored EFFECT is compared with its pre-observer causal
snapshot and restored/rejected if any out-of-band reference mutated it.

Stateful pre-completion systems are not projections. Phase 0 classifies every
live callback before migration. A callback such as `SpatialSensesSystem` that
updates Senses and may publish `SensoryUpdateEvent` runs after explicit domain
children but **before** COMPLETION indexing. Each runs under its existing
causal parent, independently under `try/except`; its already-published facts
remain truthful, later callbacks still run, and failures become diagnostics
surfaced only after completion. No child-producing callback is moved into the
post-index projection stage. The completion is built only after these callbacks
finish, so their child lineages and logs are frozen into it.

Pure completion projection is split from authoritative storage. After all
stateful child producers settle, index a COMPLETION carrying the immutable
causal payload and neutral projection fields without notifying passive
observers. Then each identified/located observer computer,
perceiver/revealed computation, and combat-log projection runs independently on
a detached completion candidate under `try/except`. Failure records a frozen
`EventProjectionDiagnostic` (`system_name`, exception class, safe message) and
supplies the neutral empty/absent projection value; it cannot remove
completion. One controlled internal update may attach only the whitelisted
projection/diagnostic fields to the already-indexed completion before passive
completion callbacks receive detached copies. Authoritative causal fields are
never replaced. EventHandlers and SpatialHandlers are never dispatched during
this pure projection stage.

Combat-log projection always resolves completed child logs before deciding
delivery. Preserve the ordinary case: when the top-level completion generates
its own log, attach child logs as subentries and deliver that aggregate once.
For a top-level completion whose own `generate_combat_log()` returns `None`,
do not silently drop its logged children. Add one internal
`_deliver_projected_combat_log(completion, log)` path used by both cases. The
logless root recursively selects the nearest completed descendant logs in
stable `children_lineages` order (a selected log already owns its subentries)
and invokes the existing callback once per selected log using a detached root
completion candidate carrying that log. Zero selected logs emits nothing; one
emits once; several emit once each in stable order. A non-root logless parent
does not deliver early: its eventual root performs the same recursive
selection. No serialized forwarding field, synthetic combat-log entry, or
second callback registry is added.

`publish_prepared_postcommit_lifecycle(prepared, publish_children=None)` accepts
the same fully preallocated receipt only for event families with an explicit
postcommit handler-result guard. It indexes the prepared EXECUTION and EFFECT
through the same authoritative index core, dispatches the already-indexed
EFFECT exactly once, retains only allowlisted annotations, and restores the
last truthful EFFECT on cancellation/protected rewrite. When supplied, the one
bounded synchronous `publish_children(truthful_effect)` hook publishes two
explicitly separated classes of work: preprepared authoritative state
lifecycles, and ordinary result-dependent gameplay reactions over a stable
pre-enumerated target list. The latter may roll saves/damage and publish their
ordinary child lifecycles; their outcomes need not be guessed during pure
preparation. The hook continues remaining targets after a captured failure. It
runs after EFFECT and before stateful pre-completion systems and COMPLETION; a
`finally` path always runs the remaining child-producing systems and indexes
the prepared truthful COMPLETION after those attempted children. The
completion projection therefore freezes every successfully indexed child
lineage/log/evidence. The publisher returns completion plus all captured
handler/protocol/child failures. It rejects use of an already completed parent
and provides no late-child repair API. ENTITY_LEFT/ENTERED and spatial-effect
change/controller lifecycles use this route; passive Tile/object facts do not.

The only failures permitted before authoritative indexing are input/schema or
UUID-collision validation, which happen before world mutation publication is
attempted. Once EXECUTION indexing begins, observer/projection failure cannot
leave a lifecycle prefix: the publisher always indexes COMPLETION and returns
it with diagnostics. Core in-memory index corruption is a fatal process error,
not a gameplay cancellation path.

Refactor `EventQueue.publish_completed_fact(prepared)` to use the same
prevalidated, projection-isolated authoritative completion store for a single terminal
snapshot such as `ItemLocationStateEvent`; it is not used when EFFECT
observation is required. Door actions, tile-elevation commands, and later
terrain-changing actions remain cancelable before mutation; their subsequent
spatial state lifecycle is committed and non-vetoable.

Concretely, existing `TileElevationChangeEvent` remains the cancelable command
context. Only after its EFFECT validation accepts does GridMap mutate support
height and publish a separate committed `SpatialChangeEvent(TILE_CHANGED)` with
old/new complete Tile facts. `set_tile`, `remove_tile`, and
`set_tile_surface` likewise publish committed Tile facts after their own
preflight/commit. Completed command events do not substitute for the spatial
state fact consumed by replay and senses.

The spatial fact carries topology. The existing `ItemLocationStateEvent`
carries the complete `ItemState`. Every `BaseItem` floor placement, move,
orientation change, removal, and in-place mechanical state change publishes the
corresponding idempotent item-location snapshot with the same parent lineage.
The two existing event families are not wrapped in a third projection. A
generic non-item `BaseBlock` may still be spatially indexed by GridMap, but an
authored/renderable world object must provide the item snapshot or world
initialization validation fails.

The remaining GridMap light callback may observe precommit perceivability and
committed Tile/blocking changes, but it does not move or remove an anchored
source. Entity anchors settle inside Section 9.13.2's actor receipt;
world-object anchors settle inside Section 9.12.1's BaseItem receipt. Their
prepared light/effect facts are published as children of the causal actor or
object EFFECT before its COMPLETION, so senses observes final state. Delete the
world-object modifying anchor `EventHandler` and both light-callback anchor
branches. Passive callbacks receive detached facts and cannot be state writers.

### 12.2 Entity occupancy events

Retain `SpatialChangeEvent.entity_left` and `.entity_entered`; do not create a
parallel entity-position event. Their existing `position`, `old_position`, and
`entity_uuid` fields are sufficient to replay objective actor movement.

For a move, LEFT carries the former coordinate and the destination in
`old_position`; ENTERED carries the destination and the former coordinate in
`old_position`. For suspension/removal, LEFT has no destination. For initial
placement/restoration, ENTERED has no former coordinate unless the retained
suspension coordinate is intentionally reported.

The completion event must agree with `Entity.position` and Tile membership.
No completed ENTERED fact may name an Entity absent from that Tile; no completed
LEFT-only fact may leave the UUID in the departed Tile. Subjective reducers
consume these facts exactly as before.

### 12.3 Item location events

Replace `ItemLocationStateEvent.tile_uuid` and `.position` with:

```python
world_placement: WorldObjectPlacement | None = None
```

`location == FLOOR` requires placement. All other locations forbid it.
Inventory/equipment/merged/destroyed invariants remain. Event producers query
GridMap; they never read floor fields from the item.

### 12.4 World initialization

`WorldObjectState` becomes:

```python
placement: WorldObjectPlacement
item: ItemState
contained_items: tuple[ItemState, ...] = ()
```

`WorldTileState` adds `surface: TileSurfaceState` and sorted
`entity_uuids: tuple[UUID, ...]`, and removes sprite data and the four `*_open`
directional tuples. Boundary topology is completely present in the object
placements and item structural facts; replay must not receive a second
flattened copy. Entity details remain in their entity-created/deployment facts;
the Tile tuple is only the exact initialized occupancy index.

Replace the current bare `disable_events()`/`enable_events()` pair with one
exception-safe `with EventQueue.suppress_bootstrap_publication():` context.
Unlike GridMap's current flag, the context-local EventQueue gate covers spatial,
item-location, light, spatial-effect-interaction, and connector facts emitted
by any bootstrap caller. It rejects nested use, stores nothing, clears its
context token on success or exception in `finally`, and does not affect another
execution context. Under the accepted one-process/one-game model no gameplay
runs concurrently with bootstrap.

After all Tiles, objects, and connectors pass validation, the builder exits the
context and publishes exactly one completed `WorldInitializedEvent` containing
deterministic ordering:

- tiles by `(x, y)`;
- objects by `(position, policy.kind, boundary direction or empty, base, UUID)`;
- connectors by stable existing identity.

The bootstrap cursor must therefore advance by exactly one completion and
contain no individual Tile, placement, item-location, light, or connector
facts. A failed bootstrap advances it by zero.

The event can reconstruct every Tile band and a cold reverse-placement index
without consulting authored content or concrete builders. It cannot recreate
the live Python behavior of concrete item classes; full engine save
rehydration remains part of the later content migration. This plan's replay
gate is the event/subjective-reducer boundary, not construction of a playable
live GridMap from `ItemState` alone.

### 12.5 Atomic completion sequences

Rewrite `EventQueue.register_completion_sequence` rather than relying on its
current sequential `_store_event` loop:

1. require every input be an unregistered COMPLETION;
2. validate the entire tuple, including duplicate UUIDs within it and
   collisions against all live indexes, before indexing one event;
3. compute only isolated/neutral projection fields and prepare detached passive
   callback copies;
4. snapshot the affected index tails/parent lineage rows;
5. index **all** events through `_index_authoritative_event` with every
   notification disabled;
6. on an unexpected core index exception, restore all captured indexes and
   parent rows before re-raising; and
7. only after all are indexed, dispatch per-event passive callbacks in tuple
   order, then one sequence callback and one batch callback.

Observer errors are isolated and never roll back indexed facts. When the first
ordinary callback runs, `event_cursor()` and every UUID/type/phase/lineage
lookup already contains the complete sequence. A collision in any position
stores none. This exact primitive is used for simultaneously committed item
location snapshots.

## 13. Removal ledger

The following disappear in the same hard cut; no alias or deprecated path is
left:

- `BaseItem.tile_uuid`;
- all 16 `BaseItem.blocks_{movement,vision,light,propagation}_{direction}`
  fields and their directional setter/query machinery;
- `ItemDirectionalStructureState.blocked_directions` and ultimately the type
  itself, replaced by placement plus structural state without direction;
- all 32 Tile intrinsic/object-derived directional border fields;
- Tile directional mutation/query helpers;
- `GridMap._object_positions` and `_objects_by_position`;
- `Entity._entity_by_position`;
- `GridMap._entity_positions` and `_entities_by_position`;
- `Entity.get_all_entities_at_position`; all callers use
  `GridMap.get_entities_at` and resolve UUIDs only when they need live
  Entities;
- `GridMap.get_object_position`, `get_all_object_positions`,
  `set_tile_directional_border`, and `recompute_tile_directional_blocking`;
- `GridMap.remove_object(clear_object_location=...)`;
- `GridMap`/Tile `fire_event` parameters, event enable/disable methods, pending
  spatial queues, and direct-writing rectangle construction;
- `DirectionalWall`, `DirectionalDoor`, and duplicate `DoorObject`;
- `blocked_directions` in environment content parameters;
- flat directional metadata on object spatial events;
- `WorldTileState.*_open` fields;
- `ItemLocationStateEvent.tile_uuid` and `.position`; and
- use of `Tile.sprite_name` in world initialization. Remove the field itself
  if its live caller ledger is empty after migration; otherwise record the
  exact remaining non-renderer use as an explicit blocker before completion.
- the placement-path `getattr` fallback in GridMap object/entity movement and
  the object-distance `getattr` fallback in Entity; and
- the affected `GridEntityPositionReceipt` and world-edge dataclasses.

No replacement process-global or GridMap entity-position dictionary is added.
`Entity.position` plus the containing `Tile.entity_uuids` are the complete
objective representation. Direct private writes in `BanishedCondition`, test
support, and runtime reset are deleted, not redirected through aliases.

`BaseBlock.position` remains for entities and Tiles. `BaseItem.get_position()`
is preserved as a compatibility **behavior**, not a facade: for an owned item
it returns the owner position; for a floor item it queries
`GridMap.get_object_placement`; otherwise it returns `None`. BaseItem never
writes inherited `position` when placed.

## 14. Production caller migration ledger

Every live call must be mechanically classified before editing:

| Module | Current use | Target |
|---|---|---|
| `dnd/core/base_tiles.py` | `Tile.create` and five canonical factories with sprite/default assumptions | require explicit surface values from Section 6.2; remove sprite input; add bands |
| `dnd/core/gridmap.py` Tile/rectangle creation callers | `set_tile`, rectangle construction, replacement/removal/elevation | explicit surface; populated-Tile rejection; fix origin UUID lookup |
| `dnd/blocks/base_item.py` | place/remove, location synchronization, object-changed facts | delegate to new GridMap APIs; delete local floor authority |
| `dnd/blocks/base_item.py` charge/destruction | charge-triggered destruction and hook publication from every location | source-location preflight, lifecycle receipt, exact charge/destroy ordering |
| `dnd/blocks/inventory.py` | inspect/save/clear/restore `tile_uuid`, add/merge/detach, `transfer_to` | strict location query; target preflight; reversible transfer/merge receipt |
| `dnd/blocks/equipment.py` | preflighted events, slot mutation, equip/unequip hooks | preserve accepted phase train; lifecycle receipts; completion before final location snapshots |
| `dnd/entities/entity.py` | drop/loot and floor event snapshot | use GridMap placement and `world_placement` event field |
| `dnd/entities/entity.py` object distance/action discovery | reads item/inherited position with fallback/reflection | query exact placement; remove fallback; preserve usable boundary discovery |
| `dnd/entities/entity.py` deploy/move/detach | writes its class position registry, Senses, and both GridMap position indexes | retain `Entity.position`; override `set_position`; own public move/suspend/restore commands and compose internal GridMap receipts; delete class position registry |
| `dnd/game.py` | deploys before adding Game ownership and pops ownership before detach | own complete reversible deploy/undeploy so postcommit failure never leaves world occupancy and `Game.entities` divergent; never destroy detached runtime state |
| `dnd/core/gridmap.py` entity occupancy | two duplicate entity-position dictionaries plus staged receipt | store occupant UUIDs on Tiles, resolve UUID position from `BaseBlock.position`, expose read-only actor queries, and provide internal prepare/commit/rollback/publish primitives callable only by Game/Entity |
| `dnd/core/base_tiles.py` | no entity occupant storage | add validated `entity_uuids`; Tile does not resolve or mutate Entities |
| `dnd/blocks/sensory.py` objective owner position | mutable position copied beside Entity position | retain only as an Entity-owned mirror updated exclusively by the Entity `set_position` override; subjective/historical perceived positions remain distinct facts |
| `spatial_senses_system` plus GridMap subscriptions/suppressions | attach/detach side state around old registries | Entity owns observer registration; GridMap owns subscriptions and token-composed light suppression; both join actor receipts |
| GridMap Entity-anchor light completion callback | moves attached lights only after ENTERED completion | delete as a writer; capture sources, affected Tile modifiers, and all suppression tokens in the actor receipt, then publish prepared child facts |
| `SpatialEffect._install_anchor_handler` Entity branch | reacts only to ENTERED, so suspend/remove retain stale attached effect state | delete as a writer after actor receipts own move/empty/restore/retire and publish existing footprint/removal facts |
| `dnd/spells/abjuration.py::BanishedCondition` | directly edits all three private position registries and moves an occupant aside on return | pure pre-removal planning before any removal event; call Entity compound receipt; preserve occupied return and zero-cursor no-destination rejection |
| `dnd/runtime_reset.py` and test support | clear/mutate `Entity._entity_by_position` and GridMap private maps | clear Tiles through GridMap reset and exercise public movement/deployment APIs only |
| `dnd/actions/standard.py` | pickup and attack-object floor position/removal | preflight placement/location transaction; no stale item position |
| `dnd/actions/operations.py` | `UsableItem` execution gate | retain truthful usable door/torch inheritance |
| `dnd/items/environment.py` | directional walls/doors/actions | new boundary classes; preserve door state/actions |
| `dnd/items/environment_interactables.py` | duplicate `DoorObject`, chest destruction/drop at `self.position`, actions | converge on `BoundaryDoor`; preflight contained-item drops from placement; delete duplicate |
| `dnd/items/environment_content.py::OilBarrel` | destruction installs oil spatial effect/controllers | reversible lifecycle receipt; hook child facts before the terminal `DESTROYED` snapshot |
| `dnd/content/items/environment_item_builders.py` | direct constructors | build new types with structure/material/extent, no direction |
| `dnd/items/environment_content.py` | legacy definitions/parameters | migrate active builders or classify for later content deletion; it may not keep old runtime types compiling |
| `dnd/content/scenarios/scenario_definitions.py` and battlefield definitions | authored object/wall/door declarations | add exact side/base/orientation/material/extent where the builder cannot derive them |
| `dnd/content/scenarios/scenario_deployment.py` | loots fresh unplaced grants into entities | explicit `UNPLACED -> INVENTORY/MERGED`, no false floor removal |
| `dnd/content/scenarios/battlefield_builders.py` | Tile factories, wall/door/torch placement and world-init snapshot | explicit surface/boundary; suppress bootstrap facts; serialize placement from GridMap |
| `dnd/maps/arena_layout.py` | Tile factories, wall/door/torch and center object placement | explicit surfaces/boundaries; preserve solid-cell wall factory separately |
| `dnd/items/torches.py::WallTorch` | duplicate private position, boundary-less mount, unanchored light | usable nonoccupying boundary fixture; explicit mounts; UUID-anchored light |
| `dnd/spells/conjuration.py` | feast placement | center placement |
| `dnd/spells/evocation.py` Continual Flame | resolves placed object position/light anchor | query placement and use committed placement facts |
| `dnd/spatial/effect_base.py` world-object anchor | modifying EFFECT handler runs after placement commit and can leave stale state | register exact anchor ownership; BaseItem compound receipt owns relocation/retirement; delete handler as writer |
| Continual Flame controller/GridMap anchor light | controller and GridMap callback can move the same source | compound BaseItem receipt is sole light owner; controller prepares footprint only |
| `dnd/spatial/effect_memberships.py` | locate placed providers | exact placement query |
| GridMap senses/FOV/path/propagation methods | `_objects_by_position`, Tile booleans | Tile object query and world-edge contributions |
| BaseItem world placement + `dnd/spatial/anchor_mutations.py` | no atomic owner for physical placement plus anchored mechanics | compose physical, location, light, and effect receipts without a core-to-spatial edge |
| GridMap reset/bootstrap | dual indexes and callbacks | Tile cleanup plus one reverse index; no anchor callback writer |
| `dnd/blocks/sensory.py` observation producer/reducer | object position sets and spatial completion hints | consume owner+neighbor affected positions and exact placement facts |
| `dnd/core/combat_log.py` and world/event reducers | flat event fields | consume exact placement/tile facts; no second DTO |
| `dnd/core/events/world_events.py` and `item_events.py` consumers | flat directional/tile/location state | closed validators and new exact fields |
| all direct `Tile.create`/`GridMap.set_tile` test/content callers from Phase-0 `rg` | implicit terrain/sprite defaults | exact `TileSurfaceState` chosen in ledger before cut |
| all `fire_event=False`, `disable_events`, `enable_events`, and `create_rectangle` callers | silent world mutation | ordinary committed mutation under the sole bootstrap suppression context |

Before Phase 1, rerun `rg` for every removed symbol. Completion requires zero
live production or retained-test references, not only this known list.

## 15. Implementation phases

Phase 0 and Phase 1 are separately reviewable rollback units. Phase 2 is
additive preparation and leaves the old path authoritative. Phase 3 is one
deliberately large atomic hard cut: its ordered substeps may leave the branch
temporarily broken, but none is an integration/merge boundary. Tile storage,
GridMap indices, edge queries, event schemas, BaseItem location, and their live
callers cannot be cut in separate commits without either a broken committed
tree or a forbidden dual-write compatibility layer. Phase 4 and Phase 5 are
again independent units after the atomic cut passes.

### Phase 0 — Freeze baseline and caller ledger

Actions:

1. record `rg` inventories for every field/API in the removal ledger;
2. identify every current wall/door placement and its intended one boundary;
3. identify the boundary for every active `WallTorch.mount` call;
4. classify current four-direction/default-all test fixtures into one or more
   explicit boundary objects;
5. inventory and assign exact surfaces to every `Tile.create`, `set_tile`,
   rectangle builder, canonical factory, content builder, and retained fixture;
6. inventory every BaseItem floor removal and classify its terminal location;
7. inventory fresh/unplaced grants, inventory/container transfers, equipped and
   consumable destruction, and every active item lifecycle hook/owned handle;
8. inventory every `fire_event`, GridMap enable/disable, pending-queue, and
   rectangle construction bypass;
9. pin present event JSON for center item, directional wall, closed/open door,
   and world initialization;
10. inventory every direct read/write/clear of `_entity_by_position`,
   `_entity_positions`, `_entities_by_position`, `get_all_entities_at_position`,
   and `senses.position`, classifying objective, subjective, historical, or
   entity-owned mirror semantics;
11. pin present LEFT/ENTERED JSON and Banishment suspend/restore behavior;
12. inventory all four Entity-anchor recipes/controllers (Spirit Guardians,
    Leadership, Draconic Presence, Antimagic Field), every relocate/entry/exit
    side effect, and every spatial handler capable of nested actor movement;
13. inventory every world-object anchor and attached-light writer, including
    Continual Flame's controller plus GridMap callbacks;
14. record known collection blockers from deprecated/server imports; and
15. add no production code.

Gate: the migration ledger accounts for every hit. Unknown semantics stop the
phase; they are not guessed.

### Phase 1 — Cold types and dependency guards

Actions:

1. add `WorldPlacementKind`, `WorldPlacementPolicy`, and
   `WorldObjectPlacement` to `dnd/types/world.py`;
2. add `dnd/types/materials.py` exactly as specified;
3. add validation/JSON schema tests;
4. extend safe-leaf architecture discovery; and
5. add forbidden dependency tests for types/core/items direction.

Gate: fresh imports succeed in arbitrary order; cold model JSON round trips;
no new cycle, late import, `TYPE_CHECKING`, reflection, dataclass, or custom
serializer is introduced.

### Phase 2 — Additive world-item preparation

Actions:

1. add the three BaseBlock polymorphic methods with neutral defaults;
2. add default-false `supports_spatial_actor_occupancy` and override it only on
   Entity;
3. add `dnd/blocks/world_items.py` and the new concrete boundary classes;
4. add `ItemBoundaryStructureState` without switching live old wall callers;
5. implement wall, door, cliff, retaining-wall, and fence semantics;
6. port door and wall-torch behavior as direct `UsableItem` subclasses without
   redesigning actions;
7. freeze every topology-defining field; and
8. add focused tests for intrinsic policy and structural snapshots.

Gate: the new classes import and test independently, `GridMap` still imports no
concrete item type, and the old runtime remains untouched. These are new target
implementations, not aliases or facades around old types.

### Phase 3 — Atomic storage/runtime/event hard cut

This entire phase is one rollback unit. Execute its substeps in this order:

#### 3A — Tile and surface storage

1. add `TileObjectBand`, surface state, and z-banded fields;
2. add `entity_uuids` plus narrow Tile occupant insert/remove validation;
3. add narrow Tile object insert/remove/orient validation helpers; and
4. remove all 32 directional fields and Tile directional helpers.

#### 3B — GridMap placement authority

1. replace both old object indexes with `_object_placements`;
2. implement place/move/orient/remove/query algorithms;
3. implement physical-edge opposite-side collision validation;
4. implement rebuild/load validation;
5. delete old index/query/recompute APIs immediately;
6. add `object_state_changed` and populated-Tile rejection rules;
7. fix origin Tile UUID lookup; and
8. delete public event-suppression flags/queues and make rectangle construction
   use guarded Tile mutation; and
9. migrate internal GridMap scans and reset.

#### 3C — Event publication foundation and schema cut

1. evolve `SpatialChangeEvent`, `ItemLocationStateEvent`, `WorldTileState`, and
   `WorldObjectState`;
2. implement the projection-isolated authoritative index core and robust
   `publish_committed_lifecycle`/`publish_completed_fact`;
3. implement the same bounded between-EFFECT-and-COMPLETION
   `publish_children` hook on passive `publish_committed_lifecycle` and guarded
   `publish_prepared_postcommit_lifecycle`; preserve zero modifying-handler
   dispatch for the passive route, then add the ENTITY_LEFT/ENTERED default-deny
   EFFECT guard;
4. classify every pre-completion callback; retain stateful child producers such
   as SpatialSenses before COMPLETION indexing and move only pure computers to
   isolated post-index projection; add logless-root stable child-log
   forwarding through the single combat-log delivery path;
5. make `register_completion_sequence` prevalidated and all-or-nothing;
6. implement the sole context-local EventQueue bootstrap suppression route;
7. move Tile/object spatial facts to committed publication;
8. adjust light/senses callback phases and delete every entity/world-object
   anchor callback as a state writer exactly as specified;
9. update combat-log serialization to report semantic placement without
   inventing a second state model; and
10. add frozen optional `ForcedMovementEvent.trigger_event_uuid`, which is not
   parent lineage and is used only by post-settlement independent roots, plus
   the family guard that preserves it and `parent_event=None` through every
   handler-produced phase; and
11. delete old event fields and factories' old parameters.

This event foundation lands before entity/object callers are switched so every
subsequent world mutation can preflight exact schemas and publish truthful
postcommit lifecycles immediately; no temporary silent or legacy publication
path is admitted.

#### 3D — Entity position and occupancy authority

1. override `Entity.set_position` so BaseBlock propagation updates Entity and
   its owned Senses block through one entity-local write path;
2. implement public `Game.deploy_entity`/`Game.undeploy_entity` and
   `Entity.move`/`suspend_spatially`/`restore_spatially`, backed only by the
   internal GridMap prepare/commit/rollback/publish receipt primitives and the
   public read-only `get_entity_position`/`get_entities_at` queries;
3. mutate old/new `Tile.entity_uuids` membership and the polymorphic
   `BaseBlock.position` atomically, with pure preflight before either change;
4. preserve an Entity's last semantic coordinate while suspended/undeployed,
   while removing it from every Tile occupant set;
5. add Entity's explicit suspended state and the exact Game/Entity/GridMap
   transaction order from Section 9.13.1;
6. land/reuse recovery Phase 2's
   `dnd/spatial/controller_mutations.py` frozen lower receipts/helpers and the
   typed SpatialEffect anchor boundary,
   then include every Entity-attached light and Entity-anchored spatial effect
   in actor deploy/move/suspend/restore/undeploy receipts exactly as Section
   9.13.2 specifies;
7. audit and preserve all four authored Entity-anchor controllers, including
   memberships, admission, protections/suppression, entry/exit reactions, and
   their complete condition lifecycle receipts;
8. add the per-actor re-entrancy fence and port Gust's whole forced-movement
   command to FIFO post-settlement deferral; add frozen
   `ForcedMovementEvent.trigger_event_uuid` and publish each deferred command
   as an independent root rather than a late child;
9. add the pure pre-removal hook and port deploy, ordinary movement, teardown,
   Banishment including occupied return, reset, observers/subscriptions,
   senses/path readers, action discovery, and test support to the public
   boundaries;
10. delete the Entity-ENTERED completion light mover and the Entity-anchor
   relocation handler as independent writers; their mechanics now execute
   inside the compound receipt;
11. delete `Entity._entity_by_position`, both GridMap entity dictionaries,
   `Entity.get_all_entities_at_position`, `GridEntityPositionReceipt`, and
   every direct private write; and
12. publish truthful LEFT then ENTERED committed lifecycles from the completed
    mutation, with prepared light/effect facts parented to the causal actor
    EFFECT and all predetermined facts finalized despite captured postcommit
    failures.

#### 3E — Edge and spatial queries

1. convert edge dataclasses to Pydantic;
2. remove the placement-path reflection fallback;
3. derive structural contributions from the two physical edge sides;
4. migrate movement, vision, light, propagation, path, subjective, and barrier
   queries;
5. implement the deliberately scoped vertical intersection rules; and
6. delete all flat directional projection/cache code.

#### 3F — Item and gameplay callers

1. delete `BaseItem.tile_uuid` and stop floor writes to inherited `position`;
2. make `get_position` query GridMap for floor items;
3. port inventory/equipment/loot/drop rollback using placement receipts;
4. add explicit `UNPLACED`, pure preflight, rollback receipts, and completion
   sequence publication for item-world transactions;
5. implement the full source-location matrix, equipment phase train, and
   reversible item lifecycle receipts;
6. add the BaseItem compound world-object commands and
   `dnd/spatial/anchor_mutations.py`, register exact attached effect ownership,
   and make direct GridMap calls reject incomplete BaseItem mutations;
7. port torches, spell-created objects, environment interactables, and every
   world-object anchor, with Continual Flame proving one light writer and exact
   rollback;
8. delete world-object effect/light callbacks as state writers; and
9. remove directional fields/methods from BaseItem and item observation facts.

#### 3G — Old environment types and all remaining callers

1. migrate all direct construction and placement hits from the Phase-0 ledger;
2. replace each multi-direction provider with separate single-boundary objects;
3. delete `DirectionalWall`, `DirectionalDoor`, `DoorObject`, old parameters,
   and every removed symbol; and
4. run the complete Phase-3 gate before integration.

Phase-3 gate:

- Tile validation rejects corrupt bands and surface state round trips;
- arbitrary placement/move/orient/remove sequences preserve forward/reverse
  equivalence;
- entity deploy/move/suspend/restore/undeploy/redeploy sequences preserve exact
  `Entity.position`/Senses/Tile membership invariants without any global
  position dictionary;
- Game ownership, deployment/suspension flags, senses observers, GridMap cell
  subscriptions, token-composed light state, and Entity-anchored effect state
  match the closed state matrix after every success, rejected preflight,
  rollback, and postcommit reaction error;
- every rejected operation leaves serialized world state byte-identical;
- closed/open walls and doors preserve movement/vision/light/propagation
  outcomes;
- cliff/wall stacked bands remain distinct and subjective blockers do not leak;
- completed spatial plus item-location facts replay placement, orientation,
  structural material/state, support height, and every z band in a cold reducer;
- no canceled fact describes committed placement;
- pickup/drop/merge/destroy/equip rollback, lights, conditions, and anchors
  preserve observable behavior; and
- Banishment and teardown use the same public Entity/Game command boundary and
  never edit GridMap occupancy internals;
- occupied Banishment return either commits occupant displacement followed by
  target restore or leaves both unchanged and the target suspended;
- LEFT/ENTERED EFFECT handlers observe the final Entity coordinate and Tile
  membership and their completions replay the same objective transition; and
- the branch compiles with zero active reference to old fields/APIs. No
  intermediate 3A–3G state may be merged.

### Phase 4 — Authored map content and bootstrap

Actions:

1. finish the authored semantics of arena/scenario builders that were minimally
   compile-ported during Phase 3F;
2. verify each former multi-direction wall is represented by the exact required
   set of single-boundary objects from the Phase-0 ledger;
3. finalize exact structure kind/material/extent for walls and doors;
4. add cliff/retaining-wall primitives without inferring them from height;
5. run authored height-boundary validation;
6. wrap bootstrap in the exception-safe EventQueue suppression context; and
7. publish the new deterministic `WorldInitializedEvent`.

Gate: an authored battlefield builds from a clean registry, publishes one world
initialization fact, replays into an equivalent cold world/subjective state,
and the content-built live GridMap produces the expected path, vision, light,
and propagation results.

### Phase 5 — Removal audit and documentation closure

Actions:

1. rerun the full removal-ledger search;
2. delete obsolete tests rather than preserving old fields;
3. port valuable legacy/server-shaped behavioral coverage to engine tests;
4. update the earlier placement agreement to point only to this approved plan;
5. report any unrelated pre-existing collection failures separately; and
6. run focused, architecture, and collect-only gates.

Gate: zero retained reference to any removed runtime symbol, Tile/object
forward storage and the sole object reverse index agree by construction,
Entity/Tile occupancy agrees by construction, event schemas contain no
affected renderer identifiers, and all tests in Section 16 meet their stated
outcome.

## 16. Test plan

Tests follow `HOW_TO_TEST.MD`: assert observable outcomes, not internal helper
calls, implementation call counts, or mocks of internals. Shared setup goes in
`tests/engine/support.py` only when at least two test modules require it.

### 16.1 New focused files

`tests/engine/test_world_object_placement.py`

- center placement with and without orientation;
- boundary requires direction and resolves default orientation;
- caller cannot override intrinsic occupancy/channels;
- center base must equal Tile support;
- boundary interval expands to exact half-open bands;
- nonoccupying overlay coexists with occupying structure;
- overlapping occupant rejected locally and from neighbor opposite side;
- idempotent exact placement; different replacement rejected;
- move/orient/remove remain atomic on failure;
- schema/UUID-collision failure during fact preparation precedes every public
  world mutation and leaves state/cursor unchanged;
- reverse lookup and Tile forward storage agree after a sequence; and
- rebuild rejects every corrupt invariant.
- populated Tile replacement/removal/elevation rejection is byte-identical and
  leaves the event cursor unchanged; and
- Tile UUID lookup works at `(0, 0)`.

`tests/engine/test_vertical_boundary_structures.py`

- cliff `[0,2)` and wall `[2,4)` coexist on one side;
- their structure kinds/materials remain distinct in edge facts/events;
- a door opening changes channels but not placement/bands;
- one corner uses two independent boundary objects;
- uncovered elevation is reported by authoring validation, not invented; and
- a cliff does not make the elevation traversable;
- equal and progressive walking use the exact support/swept z intervals;
- flying ignores support elevation but, like swimming/burrowing, conservatively
  respects any movement-channel boundary until altitude/depth exists;
- boundary mutation invalidates owner and neighbor senses/path/FOV/light; and
- an active wall torch mounts on an explicit side and its UUID-anchored light
  relocates with committed placement.

`tests/engine/test_world_placement_events.py`

- exact JSON for place/move/orient/remove;
- committed GridMap state exists at EFFECT and COMPLETION;
- no DECLARATION callback sees committed object facts;
- modifying handlers cannot see/cancel committed EFFECT, passive EFFECT is
  delivered, observer failure does not suppress COMPLETION, and causal payload
  mutation is rejected;
- stateful pre-completion SpatialSenses updates and their SensoryUpdateEvent
  children settle before parent COMPLETION; an injected stateful-callback
  failure is diagnosed, later callbacks still run, and COMPLETION still
  freezes every child already published;
- failing pure identified/located/perceiver/combat-log computers run only after
  neutral COMPLETION storage, produce diagnostics, and cannot emit a late
  child or suppress exact COMPLETION;
- a logless top-level completion with zero logged descendants delivers none,
  with one delivers that completed descendant once, and with several delivers
  each nearest logged descendant once in stable lineage order; a nested
  logless parent waits for root delivery and no subentry is duplicated;
- passive EFFECT receives a detached copy and cannot mutate the stored version;
- passive object publication dispatches no modifying handler, but its bounded
  hook publishes prepared anchored-light/effect children after object EFFECT
  and before object COMPLETION; child failure still guarantees truthful
  completion and surfaces afterward;
- completion sequences reject any collision before storage and every ordinary
  callback sees the entire sequence already indexed/cursor-visible;
- light updates before senses completion;
- item floor location contains the same placement value;
- world initialization reconstructs Tile bands/reverse index without content;
- no renderer field appears in the new schemas; and
- event order/deterministic sorting is stable.
- world-object spatial effects and attached lights already match `placement`
  at object EFFECT, retire/clean from the captured `previous_placement`, and
  are never mutated by a passive callback;
- Continual Flame has exactly one light relocation owner and injected anchor
  commit failure restores placement, light, effect, condition, and cursor; and
- successful bootstrap appends exactly one `WorldInitializedEvent`, while
  failed bootstrap appends nothing.

`tests/engine/test_item_world_transactions.py`

- invalid drop destination changes no inventory, GridMap, item, or event cursor;
- loot preflights inventory/merge before floor removal;
- displaced equipment destination failure changes nothing;
- successful loot/drop/equip/merge/destroy emits the exact causal sequence and
  final location;
- bare removal ends at explicit `UNPLACED`; and
- fresh scenario grant, chest/container transfer, `Inventory.transfer_to`, and
  floor/unplaced/inventory/equipped destruction follow the source matrix;
- equipped replacement preserves declaration/execution/effect/completion order
  and modifier/handler rollback receipts;
- a guarded DECLARATION/EXECUTION validator returning `event.cancel(...)`
  remains a sanitized ordinary precommit veto with no mutation or event-cursor
  change;
- portable Torch light and OilBarrel spatial-effect hooks restore on failure;
- charge-triggered destruction orders charge/equipment/spatial/item/hook facts
  exactly; and
- unexpected destination or hook-commit failure **before Equipment EFFECT
  dispatch** restores all Pydantic receipts before terminal state-fact
  publication; a multi-conflict replacement failure emits one non-dispatched
  `CANCEL(canceled_from_phase=EFFECT)` for every published unequip/equip
  lineage in deterministic order; and
- a raising, canceling, or evidence-rewriting post-commit Equipment EFFECT runs
  exactly once, cannot replace any non-allowlisted field or forge queue-owned
  evidence (`item_uuid`, slot, owner, `parent_lineage`, children, and observer
  maps are explicit cases), does not roll back the final loadout, still indexes
  truthful equipment/spatial/location completions in order from the last
  truthful EFFECT, and surfaces the reaction failure only after those facts
  exist.

`tests/engine/test_world_mutation_publication.py`

- no public `fire_event` or GridMap enable/disable API exists;
- rectangle creation outside bootstrap emits one committed Tile lifecycle per
  created Tile;
- ordinary Tile/object callers cannot mutate without facts;
- the bootstrap context is the sole suppression route and restores on
  exception; and
- architecture search finds no pending-event queue or silent mutation flag.

`tests/engine/test_entity_position_authority.py`

- fresh creation alone does not place an Entity into a Tile;
- a non-Entity BaseBlock UUID is rejected before Tile/event mutation;
- deploy adds the UUID to exactly one Tile and agrees with `Entity.position`
  and the Senses mirror; `Game.entities`, deployment/suspension flags,
  observer registration, subscriptions, and suppressions all match;
- move atomically removes old membership, adds new membership, and updates
  Entity/Senses through the single polymorphic setter;
- failed destination, schema validation, or event UUID collision changes no
  Entity, Senses, Tile, cache revision, or event cursor state;
- suspend removes Tile membership while retaining the Entity coordinate;
- suspend retains Game ownership/`is_deployed`, marks suspended, and removes
  observer/subscription state, adds only its dedicated light-suppression token,
  and transitions Entity-anchored effect footprints to empty without retiring
  them;
- restore uses that retained coordinate and rejects an illegal destination
  without partial mutation;
- restore reinstalls observer/subscriptions, removes only the suspension light
  token, restores Entity-anchored effects, and clears suspended state before
  ENTERED handlers run; independent light-suppression tokens remain effective;
- Game undeploy/teardown removes Game ownership, active occupancy,
  observers/subscriptions, suppresses retained lights with only the undeployed
  token, and empties but does not destroy Entity-anchored effects before LEFT
  handlers run; redeploy restores the intact Entity;
- LEFT precedes ENTERED, both EFFECT handlers observe the committed final
  state, child hazard facts keep their parent, and both completions are
  truthful even when a postcommit reaction raises or attempts cancellation;
- identity rewrite, coordinate rewrite, child forgery, and observer-evidence
  forgery are rejected; completion derives from the last truthful EFFECT;
- Banishment applies and removes through suspend/restore without any private
  position-index access;
- occupied Banishment return atomically moves the occupant aside then restores
  the target in deterministic event order: condition-removal EFFECT, occupant
  LEFT/ENTERED and target ENTERED children, then condition-removal COMPLETION
  with complete lineage/log projection; no available adjacent destination
  is rejected before the condition-removal declaration and leaves both actors
  and the event cursor unchanged with the target suspended;
- injected Banishment compound-commit failure occurs after fenced
  DECLARATION/EXECUTION acceptance but before indexing and restores condition,
  both actors, attachments, cursor, and empty lineage exactly;
- lit deploy/move/suspend/restore/undeploy/redeploy preserves exact source state, Tile
  illumination, and independently owned suppression tokens through success and
  rollback;
- an Entity-anchored Spirit Guardians effect moves with its actor, becomes
  inactive with an empty footprint during suspension, restores at the retained
  coordinate, and survives undeploy/redeploy, with truthful existing
  effect-change facts and exact entry/exit membership plus damage semantics;
- Leadership leases and Antimagic protection/suppression state follow the same
  move/suspend/restore/undeploy lifecycle without stale memberships or markers;
- a Gust ENTERED reaction queues its entire forced-movement command until the
  outer actor completion, producing a truthful completed A -> B lineage then a
  top-level B -> C forced-movement lineage whose frozen `trigger_event_uuid`
  points to the A -> B ENTERED EFFECT; traversal, serialized order, subjective
  projection, and combat-log delivery occur exactly once with no late child;
- forced-movement handlers cannot rewrite/clear that trigger UUID or attach the
  deferred root as a child through `model_copy(update=...)`; a legal precommit
  cancellation remains valid and leaves actor state unchanged;
- `get_entities_at` inspects one Tile, and callers resolve returned UUIDs only
  when live objects are needed; and
- no process-global or GridMap entity-position dictionary remains.

`tests/architecture/test_world_placement_boundaries.py`

- all new types are Pydantic or enums;
- all `dnd.types` modules remain dependency leaves;
- Tile/GridMap do not import concrete items/content;
- GridMap does not import Entity, and Entity position mutation reaches core
  only through `BaseBlock.set_position` plus Tile UUID membership;
- lifecycle-changing GridMap actor primitives are internal and have no callers
  outside `dnd/game.py` and `dnd/entities/entity.py`; every other module uses
  Game/Entity commands or the read-only Tile queries;
- physical GridMap object primitives reject BaseItems outside their compound
  floor commands; no world-object anchor/light callback or concrete controller
  remains a competing placement-driven state writer;
- every GridMap entity-occupancy entry validates the default-false typed actor
  capability; no arbitrary BaseBlock can enter `Tile.entity_uuids`;
- no `TYPE_CHECKING`, late-import workaround, dataclass, or reflection exists in
  the new placement/edge/entity-occupancy path; the old
  `GridEntityPositionReceipt` no longer exists;
  unrelated pre-existing diagnostic/event-guard reflection elsewhere in the
  large affected files is neither copied nor falsely claimed removed; and
- removed symbol names have no active imports/definitions;
- architecture search forbids `_entity_by_position`, `_entity_positions`,
  `_entities_by_position`, `get_all_entities_at_position`, and direct writes to
  `senses.position` outside the Entity-owned setter; and
- architecture tests require the postcommit SpatialChangeEvent guard and
  forbid a second unprepared LEFT/ENTERED publication route; and
- spatial handlers capable of actor movement call the Entity post-settlement
  deferral boundary; direct re-entrant `Entity.move` calls are absent;
- a deferred forced-movement event with `trigger_event_uuid` must have
  `parent_event=None`, and no code may append a child to an already completed
  lineage; and
- `dnd/spatial/controller_mutations.py` has only its declared lower imports;
  Entity/BaseItem import no concrete controller, and the common receipt has no
  dataclass, custom serializer, late import, `TYPE_CHECKING`, `getattr`, or
  reflection escape hatch.

### 16.2 Existing capability suites to preserve/port

- `tests/engine/test_grid_pathfinding.py`;
- `tests/engine/test_progressive_elevation_movement.py`;
- `tests/engine/test_traversal_connectors.py`;
- `tests/engine/test_world_edge_identity_and_elevation.py` after removing its
  unrelated server import blocker;
- `tests/engine/test_senses_light_stealth.py`;
- `tests/engine/test_spatial_effects.py`;
- `tests/engine/test_items_inventory_equipment.py`;
- `tests/engine/test_equipment_domain_ownership.py`;
- `tests/engine/test_action_discovery.py`;
- `tests/engine/test_action_cost_and_position_commit.py`;
- `tests/engine/test_move_settlement.py`;
- `tests/engine/test_condition_transform_ownership.py`;
- the occupied Banishment-return behavior from
  `tests/manual/test_133_new_spells_batch4_legacy_contract.py`, extracted into
  the new focused engine test without deprecated imports;
- `tests/engine/test_runtime_identity_registries.py`, rewritten to assert the
  surviving identity registry and Tile-owned occupancy rather than the removed
  class position registry;
- `tests/engine/test_manual_11_grid_tiles_terrain_movement.py`;
- `tests/engine/test_equipment_replication_facts.py`;
- `tests/engine/test_direct_scenario_deployment.py` if that live path remains at
  implementation time, otherwise its exact successor;
- `tests/engine/test_elevation_proving_battlefield.py`; and
- the valuable behavior in
  `tests/manual/test_directional_environment_legacy_contract.py`, rewritten as
  an engine test without deprecated content imports.

Delete only assertions whose sole subject is a removed representation:
individual directional booleans, `blocked_directions`,
`set_tile_directional_border`, `tile_uuid`, or flat event maps. Preserve the
movement/vision/light/propagation, open/close, subjective perception, item
location, and replay outcomes they were trying to prove.

### 16.3 Baseline known failures

Before this plan, the focused baseline was:

- 46 passed and one existing failure in progressive elevation plus connectors:
  hidden destination discovery returned `known_clear` instead of `unknown`;
- 57 passed for grid pathfinding, item inventory/equipment, and elevation
  proving battlefield;
- world-edge identity/elevation collection blocked by missing
  `server.api_models`; and
- the manual directional environment contract collection blocked by missing
  `dnd.content_system`.

These must be reported separately. This migration must not silently claim them
as regressions or hide them by deleting valuable coverage. The two blocked
capabilities are ported to core/engine imports before being used as gates.

### 16.4 Required commands at completion

1. focused new files;
2. all existing suites in 16.2;
3. `tests/architecture`;
4. `pytest --collect-only -q` with failures classified against the recorded
   baseline; and
5. the widest runnable engine suite after collection blockers are isolated.

Exact commands must use the repository virtual environment and current test
layout discovered at implementation time; do not invent stale file paths.

## 17. Performance and serialization acceptance

- UUID-to-placement lookup is O(1).
- object position lookup is O(1); Entity position is an O(1) `BaseBlock`
  lookup followed by one Tile membership check.
- position-to-object and position-to-entity lookup inspect one Tile only.
- edge lookup inspects the two relevant boundary-side band maps only.
- no placement/movement/removal scans all Tiles or all world objects.
- a tall object has O(vertical extent) storage by deliberate design; one UUID
  is not cloned into several engine objects.
- deterministic `model_dump(mode="json")`/`model_validate_json` round trips all
  cold values without custom codecs.
- Tile forward storage and the reverse index have a validation/rebuild path.
- Tile Entity membership validates against each deployed Entity's inherited
  position without creating a second UUID-to-position index.
- cache revision increments are coalesced once per committed mutation.

## 18. Completion criteria

The migration is complete only when all are true:

1. one playable Tile remains per XY;
2. center and four boundary placements live on Tile in z bands;
3. GridMap is the only physical Tile-band/reverse-placement mutation owner,
   while BaseItem is the sole compound lifecycle coordinator for item location
   and anchored light/effect state;
4. object intrinsic policy cannot be overridden by callers;
5. floor items store no duplicate Tile/position authority;
6. there is one reverse placement index and no position-to-object cache;
7. Entity position remains on Entity, every active occupant appears on exactly
   one matching Tile, and no global/GridMap entity-position map remains;
8. the Senses coordinate is written only by the Entity-owned position setter
   and never acts as world occupancy authority;
9. Game ownership, deployment/suspension flags, observer registration,
   subscriptions, exact light-suppression tokens, attached-light state,
   Entity-anchored effect state, and Tile membership always match the closed
   entity state matrix;
10. walls/doors occupy one chosen boundary per object;
11. cliff, embankment, retaining wall, wall, door, and fence are distinguishable
   semantic game facts with material and exact vertical interval;
12. support height, boundary structures, and traversal connectors remain
   separate facts;
13. events replay every placement, actor transition, and band without content
    code;
14. committed placement and entity occupancy facts are non-vetoable and match
    Entity/Tile/GridMap at every
    observable event phase;
15. old directional booleans/maps/recompute paths and duplicate door type are
    gone;
16. the new path contains no frontend asset/render identifiers;
17. all new schemas use Pydantic and dependency boundaries are cycle-free;
18. no compatibility facade, late import, `TYPE_CHECKING`, reflection, or
    custom serializer was added, and no reflection/dataclass remains in the
    new placement/edge path; and
19. no ordinary Tile/object/entity mutation has a fact-suppression switch;
20. every live item source location and lifecycle hook is preflighted,
    reversible, and publishes only truthful final snapshots; and
21. focused and preserved behavioral tests pass, with unrelated baseline
    failures reported honestly; and
22. lifecycle-changing GridMap actor primitives have only Game/Entity callers,
    while Banishment rejection, attached lights, and Entity-anchored effects
    satisfy the atomic event/rollback contracts in Section 9.13; and
23. BaseItem compound world commands are the only callers of internal physical
    GridMap primitives for items; object-anchored lights/effects commit
    atomically and no callback/controller duplicates their state writes; and
24. every prepared causal child settles between its parent EFFECT and
    COMPLETION; deferred forced movement is an independent root with a frozen
    trigger reference, never a late child, and receives projection/combat-log
    delivery exactly once; and
25. the sole shared spatial-controller mutation receipt/helper lives in the
    dependency-safe lower module, while Entity/BaseItem use typed SpatialEffect
    boundaries and no upward concrete-controller cycle exists.

## 19. External review record

Both reviewers approved the same substantive frozen revision,
`fe7d83ad5c662d7ec1f14e055e5807742fb5f69d120b42dcb71911f1d1bf464f`.
The final file checksum differs only because this status/review record was
updated after approval and is reported in the handoff.

| Reviewer | Focus | Status |
|---|---|---|
| Architecture/invariants reviewer | dependency graph, ownership, Pydantic schemas, vertical/edge/entity invariants, cycles | **APPROVED** |
| Migration/events/tests reviewer | live callers, phase order, event/replay semantics, data loss, rollback, test preservation | **APPROVED** |
