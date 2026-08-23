# Tile, world-item, and entity-position clean migration plan

Status: planning complete; approved by two independent read-only reviewers and
the root pass in the final three-way anti-slop audit. Implementation has not
started.

Date: 2026-08-18

The detailed source record remains in
`DND_TILE_WORLD_ITEM_VERTICAL_BOUNDARY_MIGRATION_PLAN_2026-08-17.md`.
This document names the implementation surface selected from that study.

## 1. Outcome

The migration establishes one `GridMap` with one playable `Tile` at each XY,
direct semantic material fields on each Tile, Tile-owned center and boundary
object placement, integer vertical bands, exact world-edge derivation, and
exact placement facts in the existing event stream.

The already-implemented spatial-condition system is a foundation of this
migration, not a neighboring system to replace. GridMap continues to own every
active `SpatialCondition` and its reverse footprint. Each covered Tile keeps
its existing layer-indexed condition UUID references, and `Tile.get_conditions()`
continues to return direct Tile conditions and independently owned spatial
conditions together.

Entity instances retain their direct position. GridMap retains its UUID-based
occupancy indexes. One Entity-owned write path synchronizes the two stores.
Temporary spatial suspension becomes a named Entity capability used by
Banishment while Game ownership and the live Entity remain intact.

The result supports authored ground, ordered surface layers, walls, doors,
cliffs, boundary attachments, ordinary floor items, entity movement,
temporary removal from spatial play, and the existing dynamic spatial
conditions without duplicating their state onto Tile or world items.

## 2. Dependency and ownership map

Arrows point from importer to imported dependency. Reverse arrows identify the
principal consumers.

```text
dnd/types/materials.py
  [-> enum]
  [<- base_tiles, world_items, world events, authored map content]
  Material
  SurfaceLayer
  BoundaryStructure

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
  [-> base_block, base_conditions, dnd/types/materials.py,
       dnd/types/world.py, dnd/types/spatial_effects.py]
  [<- GridMap, world events, authored map builders, spatial conditions]
  direct base_material and ordered surface_layers
  TileObjectBand
  Tile center/boundary band storage
  existing spatial-condition UUID references and complete condition query

dnd/blocks/base_item.py
  [-> base_block, dnd/types/world.py, existing item events]
  [<- portable items, usable items, equipment, world_items]
  ordinary floor-item placement through GridMap

dnd/blocks/world_items.py
  [-> base_item, dnd/types/materials.py, dnd/types/world.py]
  [<- environment items and authored map content]
  WorldItem center-occupying fixture base
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
  [-> pydantic, dnd/types/world.py]
  [<- GridMap path, sight, light, and propagation queries]
  frozen Pydantic adjacent-edge identity, structural contribution, and view values

dnd/core/gridmap.py
  [-> Tile, BaseBlock, BaseCondition, world edges, world events,
       dnd/types/world.py, dnd/types/spatial_effects.py]
  [<- Entity, actions, items, spatial systems, content builders]
  object placement mutation boundary
  entity UUID occupancy indexes
  existing spatial-condition owners, reverse footprints, and layer indexes
  exact spatial publication

dnd/spatial/area_conditions.py
  [-> BaseCondition, GridMap public condition APIs, existing world events]
  [<- environmental conditions, spell zones, auras, content materialization]
  existing SpatialCondition and AreaCondition ownership
  existing object/entity anchor event handling

dnd/entities/entity.py
  [-> GridMap entity queries and internal occupancy primitives,
       existing sensory system]
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

## 3. Static Tile materials and dynamic spatial conditions

Create `dnd/types/materials.py` as a dependency leaf containing the exact
authored enums needed by the first map cut.

```python
class Material(StrEnum):
    EARTH = "earth"
    SAND = "sand"
    ROCK = "rock"
    DRESSED_STONE = "dressed_stone"
    WOOD = "wood"
    WATER = "water"


class SurfaceLayer(StrEnum):
    GRASS = "grass"
    WOOD_FLOOR = "wood_floor"
    STONE_FLOOR = "stone_floor"


class BoundaryStructure(StrEnum):
    CLIFF = "cliff"
    WALL = "wall"
    DOOR = "door"
```

`Tile` stores these as ordinary validated Pydantic fields rather than wrapping
them in another state model:

```python
base_material: Material = Material.EARTH
surface_layers: tuple[SurfaceLayer, ...] = ()
```

`base_material` is the permanent supporting material. `surface_layers` is
ordered from bottom to top. Grass over earth, wooden flooring over stone, and
later multi-layer authored surfaces therefore remain separate game facts. They
are not `ModifiableValue` objects: changing authored material is an explicit
GridMap Tile mutation with a normal Tile-change event, not modifier stacking.
The tuple is the ordered stored value because layer changes replace the sequence
through GridMap instead of mutating it silently in place; XY lookup remains the
existing GridMap dictionary.

Dynamic mechanics are not copied into these fields. Wet, Water, Ice, Oil,
Fire, Steam, spell zones, traps, and auras remain `SpatialCondition` instances.
GridMap owns each condition and its reverse footprint; the covered Tiles retain
UUID references grouped by `SpatialEffectLayer`. `Tile.get_conditions()` is the
single query for direct and spatial conditions. The migration adds no
`tile.effects`, `wet`, `burning`, or other parallel collection/boolean.

`Material.WATER` is reserved for an authored liquid Tile whose structural
movement mode is swimming, such as the current deep-water factory.
`WaterSurface` remains the recovered shallow/dynamic spatial condition that
applies Wet over an otherwise existing Tile. Those are distinct game facts and
the migration does not infer one from the other.

Concentration remains an ownership link, not Tile state. The concentrating
condition retains the exact linked spatial-condition UUID. Dropping the slot
removes that condition through the ordinary condition lifecycle;
`SpatialCondition.deactivate()` then removes its GridMap footprint and every
Tile reference. Consequently a covered Tile cannot be replaced while the spell
is active, but becomes replaceable after concentration cleanup completes. The
placement migration changes none of this ownership path.

For example, grass on fire is represented initially as `GRASS` in
`surface_layers` plus a `FireSurface` condition covering the Tile. If authored
rules later consume the grass, that rule explicitly removes `GRASS` through
the Tile-material mutation API and the event stream records the changed static
Tile state. The placement migration does not invent that reaction rule.

The recovered `SpatialEffectInteractionEvent` and its fourteen direct
condition-to-condition transitions remain unchanged. A later authored rule that
reacts to permanent Tile material reads `base_material`/`surface_layers` from
the covered Tile and, only when the rule changes permanent material, calls the
single GridMap material mutation. It does not add a material registry, effect
gateway, Tile boolean, or second reaction-state owner in this cut.

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
    vertical_extent_steps: StrictInt = Field(ge=1)


class WorldObjectPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    object_uuid: UUID
    tile_uuid: UUID
    position: tuple[int, int]
    occupies_bands: bool
    boundary_direction: CardinalDirection | None = None
    base_height_steps: StrictInt
    top_height_steps: StrictInt
    orientation: CardinalDirection | None = None


class BoundaryStructureState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    structure: BoundaryStructure
    material: Material
    blocked_channels: tuple[WorldEdgeChannel, ...] = ()
```

The cold values validate their intrinsic shape:

1. every height/extent is an exact integer (`bool`, numeric strings, and floats
   are rejected rather than coerced);
2. `top_height_steps` is greater than `base_height_steps`; and
3. the structure snapshot carries typed structure, material, and current
   channels.

`BoundaryStructureState` is a frozen return/event snapshot of item-owned fields,
not another mutable state owner. The live wall, door, or cliff remains the
authority for its material, structure, and open-dependent channel policy.

GridMap resolves the complete placement against the live Tile and provider. It
validates that the height interval equals the provider policy's extent, that a
center placement begins at `Tile.height`, and that a boundary placement uses a
complete integer interval. An omitted `base_height_steps` resolves to
`Tile.height`. An authored boundary may supply any explicit integer base;
GridMap derives `top_height_steps = base_height_steps + vertical_extent_steps`
and validates band collisions. A cliff rising to the support surface supplies
`base_height_steps = Tile.height - vertical_extent_steps`. GridMap resolves
omitted boundary orientation to the selected boundary direction.

The public Python methods retain `int | None` annotations, but the shared
resolver rejects a provided value unless `type(value) is int` before doing any
arithmetic. Pydantic-authored fields use `StrictInt`. Thus direct calls and
serialized content enforce the same exact-integer boundary.

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

`WorldItem` is the center-placed, nonpickable world-fixture base and defaults to
`occupies_bands=True`. Active boulders and barricades use it, so two physical
center blockers cannot claim the same band. Ordinary portable/dropped
`BaseItem` remains nonoccupying by default. `BoundaryStructureItem` changes the
policy to boundary placement and owns:

- `structure: BoundaryStructure`;
- `material: Material`;
- `vertical_extent_steps: StrictInt`;
- `blocked_channels: tuple[WorldEdgeChannel, ...]`.

Its boundary-state capability returns the current structure, material, and blocked
channels. `BoundaryDoor` implements the same neutral capability directly.

`BoundaryDoor` remains a direct `UsableItem` so current action discovery and
execution continue to recognize it. It owns the same structure, material,
extent, plus `blocked_channels_closed` and `is_open`; it overrides the boundary
placement and boundary-state capability methods and changes its returned
blocked channels when opened or closed. Its placement remains stable. Fixed
walls and cliffs have no open/closed field or closed-channel alias.

`WallTorch` preserves its usable behavior and overrides the typed placement
policy as a nonoccupying boundary attachment. Its light anchor reads the
current placement through GridMap.

Its existing light source becomes attached with `anchor_uuid=self.uuid`; the
private `_wall_torch_position` is deleted. The existing GridMap attached-light
callback also consumes committed object placed/removed lifecycles:

- placement resolves `get_object_placement(self.uuid)`, moves the
  existing light only when XY changed, and removes the existing
  `"world_unplaced"` suppression token;
- the removal leg of a move sees the already-committed destination and does not
  suppress the light;
- ordinary true removal adds that token through the existing block-light suppression
  machinery, clearing illumination while retaining the torch's `is_lit` and
  light UUID for possible re-placement; and
- destruction continues to call existing `cleanup_block_light_sources`, which
  deletes the source and its suppression state.

GridMap's bulk `clear` is terminal rather than reversible unplacement. Replace
the old compatibility hook with
`on_grid_object_removed(position, *, terminal: bool = False)`. Delete
`clear_location` and `GridMap.remove_object(..., clear_object_location=...)`
completely: their only purpose was preserving the duplicate `BaseItem.tile_uuid`
during remove-then-place reindexing, while the new `move_object` commits the
placement atomically. Ordinary `remove_object()` passes `terminal=False` and
`clear()` passes true exactly once.
WallTorch's override calls its existing `put_out()` for terminal removal, which
sets `is_lit=False`, removes the light source, and clears
`_light_source_uuid`. It does not install `"world_unplaced"` during clear, so
the later clearing of GridMap light/suppression dictionaries cannot strand
stale torch state. No second light position or light registry is introduced.

The current `OilBarrel` is the one active center blocker whose mechanics exist
only inside the broken mixed `environment_content.py` catalog. Move that exact
authored subclass and one direct `build_oil_barrel` function into the existing
downward-depending `dnd/content/items/environment_item_builders.py`. It adopts
the center-occupying `WorldItem` base and retains its exact destruction-to-
`OilSurface` behavior through the already-active direct spatial materializer.
The old mixed catalog imports and reuses that class/builder for its preserved
declaration until the later content migration; it does not retain a second
implementation. No module under `dnd/items` or `dnd/blocks` imports authored
content. Crates remain explicitly nonoccupying because their current rules do
not block the cell.

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

Add direct material fields to `Tile`. Keep both object-band stores private,
beside its existing private spatial-condition reference index:

```python
base_material: Material = Material.EARTH
surface_layers: tuple[SurfaceLayer, ...] = ()
_center_object_bands: dict[int, TileObjectBand] = PrivateAttr(default_factory=dict)
_boundary_object_bands: dict[
    CardinalDirection,
    dict[int, TileObjectBand],
] = PrivateAttr(
    default_factory=lambda: {direction: {} for direction in CardinalDirection},
)
```

Every integer band key represents `[z, z + 1)`. An object placed at `[0, 2)`
appears in bands `0` and `1`. Each occurrence carries the same resolved
UUID membership. An occupying object is also recorded as `occupant_uuid` in
every covered band. Attachments share those bands through the `objects` set.
Orientation is read from the single reverse `WorldObjectPlacement`.

The four boundary dictionaries are always present. Empty band rows are removed
after object removal. These object bands do not replace or absorb
`Tile._spatial_condition_uuids`. The two indexes answer different questions:

- object bands say which placed `BaseBlock` UUIDs occupy or attach at a height
  interval; and
- spatial-condition references say which independently owned `BaseCondition`
  UUIDs mechanically affect this Tile, grouped by `SpatialEffectLayer`.

A wall, door, cliff, torch, or dropped item uses the object bands. Wet, Fire,
Water, Ice, Oil, Steam, traps, spell zones, and auras use the existing condition
references. Being visible or spatial does not turn a condition into a placed
world object. `Tile.get_conditions()` keeps merging direct Tile conditions and
resolved spatial conditions exactly as it does now.

Tile exposes narrow band methods matching the recovered condition-index pattern:

- read the object UUIDs and occupying UUID for one center/boundary band through
  copied/frozen return values;
- add one already-resolved placement reference to every covered band; and
- remove one already-resolved placement reference and delete empty rows.

Only GridMap calls the two mutation methods. Callers never receive the mutable
dictionaries or `TileObjectBand` instances. GridMap remains responsible for
cross-Tile/opposite-edge validation and for synchronizing these forward rows
with `_object_placements`.

```python
def get_object_band(
    self,
    *,
    band: int,
    boundary_direction: CardinalDirection | None = None,
) -> TileObjectBand | None: ...  # deep copy

def get_placed_object_uuids(self) -> set[UUID]: ...  # new set

def has_light_modifiers(self) -> bool: ...  # existing private light maps

def add_object_placement_reference(
    self,
    placement: WorldObjectPlacement,
) -> None: ...

def remove_object_placement_reference(
    self,
    placement: WorldObjectPlacement,
) -> None: ...
```

The mutation methods validate that `placement.tile_uuid` and
`placement.position` identify this exact Tile. Collision admission happens in
GridMap before the add method; the Tile method enforces its local occupant
invariant and rejects inconsistent removal.

Tile storage and the GridMap reverse placement satisfy these invariants:

1. each placed object has one `WorldObjectPlacement`;
2. its UUID occurs in every covered band at the recorded center or boundary;
3. its UUID occurs in the corresponding bands of one Tile;
4. occupying objects own `occupant_uuid` in every covered band;
5. each band has at most one occupying object;
6. attachments may share a band with its occupying structure; and
7. opposite sides of one physical edge are checked together during placement;
8. object placement never mutates the Tile's spatial-condition references; and
9. changing direct material fields never replaces the Tile or loses either
   object bands, direct conditions, spatial-condition references, or light
   modifiers.

`has_light_modifiers()` reports only whether either existing private
illumination/obscurement map is nonempty; it does not expose or duplicate those
maps. `set_tile`, `remove_tile`, and `create_rectangle` reject replacement/
removal of a Tile with placed object bands, direct active conditions, spatial-
condition references, active light modifiers, or entity occupancy at that XY.
Existing connector guards remain. In-place material and elevation mutations
remain valid because they preserve the Tile identity, direct condition owner,
light modifiers, and Entity coordinate. Support-elevation mutation preserves
direct and spatial conditions because their footprints are XY-owned. Its exact
placement rule requires no new provenance field:

- when `Tile.height` changes, reject if a center placement is present because
  its stored `base_height_steps` must equal the support height;
- boundary placement intervals are absolute and remain valid; callers that
  want a wall/cliff to move vertically must move that object explicitly;
- changing only `elevation_surface_kind` or `slope_axis` does not invalidate
  either center or boundary bands; and
- existing connector guards remain unchanged.

An accepted height change invalidates movement, vision, light-geometry, and
propagation revisions for every incident edge, then recomputes affected
existing light sources through current GridMap light recomputation methods.
This is necessary because the adjacent Tile may own a boundary provider that
enters or leaves the height-filtered relevant band set.

`clear()` continues to reject active SpatialConditions, rejects any Tile-owned
direct active condition, and additionally rejects nonempty entity occupancy.
Live condition and Game/Entity teardown must run first so GridMap cannot orphan
condition owners or clear its indexes while leaving an Entity deployed. After
those guards pass, it removes every placed object through its existing removal
hook exactly once before clearing private bands and reverse placements. Clear's
existing terminal light teardown remains valid; unlike full identity
replacement, it does not reject light modifiers. The separate whole-runtime
reset remains the owner for coordinated global test/runtime teardown. A direct
material change is not Tile replacement.
GridMap provides one explicit mutation:

```python
def set_tile_materials(
    self,
    position: tuple[int, int],
    *,
    base_material: Material | None = None,
    surface_layers: tuple[SurfaceLayer, ...] | None = None,
    parent_event: UUID | None = None,
) -> Tile: ...
```

It validates the new direct values, mutates the existing Tile instance, leaves
all object/condition indexes and light modifiers intact, and publishes the
existing Tile-change lifecycle with complete previous and current
`WorldTileState` snapshots.

## 7. GridMap object APIs

Replace the flat object indexes with:

```python
_object_placements: dict[UUID, WorldObjectPlacement]
```

This changes only world-object placement. GridMap preserves its existing
spatial-condition authority unchanged:

```python
_spatial_conditions: dict[UUID, BaseCondition]
_spatial_condition_positions: dict[UUID, set[tuple[int, int]]]
_spatial_condition_layers: dict[UUID, SpatialEffectLayer]
```

`SpatialCondition` continues to use `validate_spatial_condition_positions`,
`set_spatial_condition_positions`, `remove_spatial_condition`, and the existing
condition queries. Object placement APIs never write those dictionaries or the
Tile condition-reference index.

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
7. publish the existing spatial event through
   `GridMap._fire_spatial_event()`'s full phase lifecycle; and
8. return the committed placement.

The placement mutation is already committed before publication, matching the
current object path. Do not use `_fire_committed_spatial_event()` or
`EventQueue.publish_completed_fact()` here: neither dispatches the EFFECT
handlers that currently own object-attached condition relocation/removal. This
plan changes no EventQueue method or event phase contract.

Object movement preserves the current `OBJECT_REMOVED` then `OBJECT_PLACED`
fact sequence under one causal parent, but both are published after the reverse
placement has committed to the destination. The existing object-anchor handler
in `dnd/spatial/area_conditions.py` migrates its move/removal distinction from
`BaseBlock.position` to `GridMap.get_object_placement(anchor_uuid)`:

- during the removal leg of a move, a different current placement exists, so
  the condition stays alive and waits for the placement fact;
- on the placement fact, the handler resolves the committed placement and
  relocates only when its XY differs from `condition.position`; and
- on true removal, no placement exists, so the attached condition deactivates.

This is the required companion edit when direct item floor position is removed.
It does not change the condition lifecycle or introduce another anchor store.
Remove `SPATIAL_OBJECT_CHANGED` from both the object-condition anchor handler
and attached-light movement callback. Orientation and open/close changes never
change XY in the new API; real movement always emits REMOVED then PLACED. The
existing blocking/light-recomputation consumers of `OBJECT_CHANGED` remain.

`set_tile`, `remove_tile`, and `create_rectangle` reject a Tile that contains
object bands, direct active conditions, spatial-condition references, active
light modifiers, or entity occupancy. Support-elevation mutation preserves
direct conditions, spatial condition references, light modifiers, and entity
coordinates; rejects a height change when center placements exist; preserves
absolute boundary intervals; retains connector guards; and invalidates/
recomputes every incident structural channel plus existing light.
`clear` preserves terminal bulk object teardown and rejects active
SpatialConditions, Tile-owned direct active conditions, or nonempty entity
occupancy. The origin lookup in `get_tile_by_uuid` uses an explicit presence
check so position `(0, 0)` resolves correctly.

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
blocked channels.

Convert the three existing public values in `dnd/core/world_edges.py` from
agent-authored dataclasses to frozen Pydantic models in place; do not add a
parallel edge contract:

```python
class AdjacentEdgeKey(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    first: tuple[StrictInt, StrictInt]
    second: tuple[StrictInt, StrictInt]


class WorldEdgeStructuralContribution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_uuid: UUID
    base_height_steps: StrictInt
    top_height_steps: StrictInt
    blocked_channels: tuple[WorldEdgeChannel, ...] = ()


class WorldEdgeView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    # Preserve the existing fields, with every integer height/delta strict.
```

`AdjacentEdgeKey` keeps its current exact two-integer, cardinal-adjacency, and
canonical-order validation plus `between()` constructor. Structural
contributions require `top_height_steps > base_height_steps`.
`WorldEdgeView` keeps its existing surface/elevation facts and contribution
tuple, but validates them through Pydantic rather than custom dataclass
construction. Delete the module's dataclass import; normal Pydantic model
serialization is the only serialization path.

Both preserved intrinsic Tile-side borders and placed objects use that one
contribution model. An intrinsic contribution uses the owning Tile's support
band `[Tile.height, Tile.height + 1)`; an object contribution uses its exact
`WorldObjectPlacement` interval. Both then pass through the same relevant-band
filter and union. No second intrinsic-edge value or unbounded-height sentinel
is added.

The existing XY endpoint API derives the exact integer bands relevant to a
transition between support heights `a` and `b`:

```python
relevant_bands = range(min(a, b), max(a, b) + 1)
```

Only boundary placements covering at least one relevant band contribute their
channels. For equal height `2`, only band `2` is queried: a supporting cliff at
`[0, 2)` does not block movement across the upper terrace, while a wall at
`[2, 4)` does. A transition from height `0` to height `2` queries bands `0`,
`1`, and `2`, so the cliff face blocks the unsupported climb. Both intrinsic
Tile-side contributions are then unioned with the filtered object providers.

Walking, flying, swimming, burrowing, vision, light, and propagation retain
their current 2D endpoint API and consume this height-filtered edge union. The
engine still has no independent entity altitude. Structure and material remain
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

Spatial conditions remain mechanical conditions, not boundary objects. Their
existing handlers, Tile modifiers, membership conditions, and GridMap condition
queries continue to affect walking, visibility, light, and other mechanics.
They contribute a physical height-band edge only when an actual placed boundary
item provides that edge; the placement migration does not reinterpret a Fire,
Wet, Web, Darkness, or aura footprint as a wall.

## 9. Existing event contracts after the cut

Evolve the existing event models with cold placement values.

`SpatialChangeEvent` gains:

```python
placement: WorldObjectPlacement | None = None
previous_placement: WorldObjectPlacement | None = None
tile_state: WorldTileState | None = None
previous_tile_state: WorldTileState | None = None
```

Object placement publishes the existing `OBJECT_PLACED` fact. Object movement
publishes the existing `OBJECT_REMOVED` followed by `OBJECT_PLACED` under one
causal parent, carrying previous and current placements. Orientation and
placement-state changes publish the existing `OBJECT_CHANGED` fact. Removal
publishes the existing `OBJECT_REMOVED` fact. Tile created/changed facts carry
the complete current and previous existing `WorldTileState` snapshots.

`WorldTileState` itself gains the direct fields:

```python
base_material: Material
surface_layers: tuple[SurfaceLayer, ...] = ()
```

This evolves the event snapshot that already describes a Tile; it does not add
a second mutable Tile state object. Dynamic spatial conditions do not appear in
these two fields and do not gain another snapshot contract.

After every reader uses `tile_state`, delete the former optional
`SpatialChangeEvent.tile_walkable` and `tile_visible` scalars. They duplicate
fields in `WorldTileState` and are not retained as aliases. The shared required
`position` remains because `SpatialChangeEvent` uses it for every spatial event
family and for event indexing.

Delete the seven optional directional-cache parameters from
`SpatialChangeEvent.entity_entered()` and `.entity_left()` together with their
empty hint plumbing. Their only producer is the deleted entity-stage call to
`recompute_tile_directional_blocking`; entities do not own boundary geometry.
Keep the shared event fields and the Tile/object factories that still carry
their own relevant spatial hints.

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

They retain the current open state. `BoundaryStructureState` is assembled from
the live item's typed capability when the fact is created; it is not stored as
a second mutable copy on GridMap. `WorldObjectState` replaces its former
position field with:

```python
placement: WorldObjectPlacement
```

It carries the complete placement and semantic item state. `WorldInitialized`
remains the static map-bootstrap snapshot and contains exact direct Tile
materials, support/elevation state, object placements with item states, and the
existing traversal connectors. World-edge contributions derive from those
placements. Entity, `SpatialCondition`, and light facts continue through their
existing lifecycles.

Bootstrap ordering is explicit: build the static Tiles, place bootstrap objects,
mount authored WallTorches without igniting them, and publish
`WorldInitialized`; then activate authored starting `SpatialCondition`
instances and ignite the selected starting torches through their ordinary
application/interaction lifecycles. The bootstrap builder therefore calls
`WallTorch.mount(..., lit=False)`, records authored-lit torches in a local list,
and calls `light()` for that list after initialization. Ordinary runtime
`mount(..., lit=True)` remains immediate; it is never used while only GridMap
events are disabled. The map snapshot does not duplicate live condition
instances or their footprints, and this ordering needs no EventQueue
transaction, suppression layer, reducer rewrite, or new spatial event.

GridMap object and Tile changes continue through `_fire_spatial_event()`'s full
existing lifecycle so EFFECT handlers run. The terminal map-bootstrap
`WorldInitializedEvent` continues through `publish_completed_fact()`. Existing
sensory, combat-log, subjective, and callback machinery consumes the evolved
facts.

## 10. Caller migration ledger

| Active surface | Migration |
|---|---|
| `BaseItem.place_on_grid`, removal, inventory, equipment, and destruction | use GridMap placement APIs; floor state is read from `get_object_placement`; item-location facts carry `world_placement` |
| loot/drop/pickup/equip floor transitions | call `validate_object_placement` before inventory/ownership mutation, then place and publish one final `ItemLocationStateEvent(world_placement=...)` from the existing transaction owner |
| `DirectionalWall` | become one `BoundaryWall` placed on one selected side |
| `DirectionalDoor` and `DoorObject` callers | converge on `BoundaryDoor` with existing use/open/close behavior |
| `WallTorch.mount` and attached light | accept authored `boundary_direction`, optional base/orientation, call `place_on_grid`, delete `_wall_torch_position`, attach the existing light UUID to the torch, synchronize reversible placement through existing suppression, and use `put_out()` on terminal GridMap clear |
| active boulder and barricade builders | return center-occupying `WorldItem` instances while preserving exact HP, targetability, blocking, and sight behavior |
| active `OilBarrel` | move the one authored subclass and direct builder from the broken mixed catalog to `dnd/content/items/environment_item_builders.py`, use the center-occupying `WorldItem` base, preserve destruction-to-`OilSurface` exactly, and make the mixed catalog reuse rather than duplicate it |
| active crate builders | retain an explicit nonoccupying center policy and current nonblocking behavior |
| `BattlefieldObjectDefinition` | replace multi-direction blocking with one optional authored `boundary_direction`, base, and orientation per placed object |
| old multi-direction structural rows | expand deterministically into one structure instance and placement per authored side |
| `dnd/content/items/environment_item_builders.py` | construct `BoundaryWall`/`BoundaryDoor` with intrinsic structure fields; placement side arrives later through `place_on_grid` |
| `dnd/items/environment_content.py` | preserve its authored source inventory/checksum in the content-migration ledger together with its action-declaration dependency; replace only its local OilBarrel implementation with the direct active builder import required by this cut, while later content work owns the remaining catalog migration |
| arena and scenario map builders | supply `base_material` and ordered `surface_layers`, then call each item's `place_on_grid` with explicit boundary placement |
| battlefield rectangle helpers | supply direct Tile material fields and retain their current static-build/final-snapshot flow |
| object attack/use actions | resolve floor position through `get_object_placement` |
| `BaseItem`, inventory, Entity, standard actions, evocation spells, environment items, environment interactables, scenario compatibility, battlefield builders | replace `get_object_position` and `get_all_object_positions` reads with `get_object_placement`; `get_objects_at` callers continue using `get_objects_at` |
| GridMap's map-character, sensing, targeting, edge, path, reset, and snapshot internals | replace direct `_objects_by_position`/`_object_positions` reads with Tile-band iteration and `_object_placements` |
| `GridMap.move_entity` callers | call `Entity.update_entity_position`; delete the GridMap bypass after migration |
| `Entity.get_all_entities_at_position` callers | use `GridMap.get_entities_at(position)` and resolve the returned UUIDs through `Entity.get`; delete the storeless Entity facade |
| GridMap entity occupancy mutation/publication | rename `register_entity`, `unregister_entity`, `stage_entity_position`, and `publish_staged_entity_position` as internal underscored primitives with Entity attach/detach/move/suspend/restore as their sole production caller; retain public read-only queries |
| `GridMap.set_tile_elevation` | preserve conditions; reject height changes with center placements; retain absolute boundary bands/connector guards; invalidate movement, vision, light, and propagation on incident edges and recompute affected current lights |
| `dnd/spatial/area_conditions.py::_install_anchor_handler` | replace its `BaseBlock.position` move/removal guard with `GridMap.get_object_placement`; relocate only when committed XY changed; keep the existing condition lifecycle and footprint APIs |
| all existing `SpatialCondition` implementations | retain `validate_spatial_condition_positions`, `set_spatial_condition_positions`, `remove_spatial_condition`, Tile condition references, and footprint-sized work unchanged |
| runtime reset | invoke the separate `GridMap.reset()` owner, which clears GridMap object/entity indexes internally; never call the Entity-only occupancy primitives |
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
base_height_steps: StrictInt | None = None
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
- `dnd/content/items/authored_item_builders.py` boulder, barricade, and crate
  construction;
- the active direct `OilBarrel` builder, destruction position lookup, and center
  placement in `dnd/content/items/environment_item_builders.py`;
- `dnd/content/scenarios/scenario_compatibility.py` authored compatibility;
- `dnd/content/scenarios/battlefield_builders.py` battlefield placement;
- `dnd/spatial/area_conditions.py` world-object anchor synchronization; and
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
Delete `Entity.get_all_entities_at_position`; after its private index is gone it
would only be a second facade over the GridMap query. Delete `GridMap.move_entity`
as well: it mutates GridMap occupancy without synchronizing the Entity and is a
bypass around the public movement owner.

Make GridMap's remaining occupancy mutation/publication primitives internal:
`_register_entity`, `_unregister_entity`, `_stage_entity_position`, and
`_publish_staged_entity_position`. Entity attach/detach/move/suspend/restore are
their only production caller. `get_entity_position` and `get_entities_at`
remain the public read-only GridMap queries. Do not retain public aliases.

`Entity.update_entity_position` remains the single public movement owner and
performs this sequence:

1. validate the live deployed Entity and destination;
2. construct and validate the three-field GridMap receipt before mutation;
3. commit the two GridMap occupancy indexes with no callbacks or cache work;
4. update `Entity.position` and sensory position; and
5. publish the existing LEFT and ENTERED spatial facts through GridMap.

A rejected destination raises the existing position-commit failure before any
owner changes. Once validation succeeds, the commit contains only dictionary
and direct Pydantic-field writes; do not retain a synthetic rollback framework
for impossible directional-cache failures. The existing publication-failure
contract remains distinct because the position is already committed before the
event lifecycle runs.

`Game.deploy_entity` and `Game.remove_entity` use Entity attach/detach methods,
which call GridMap's internal occupancy primitives. Encounter and content
remain callers of Game/Entity rather than writers of private position
dictionaries.

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
) -> None: ...

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

Replace the existing internal dataclass `GridEntityPositionReceipt` with a
frozen Pydantic `BaseModel` in `dnd/core/gridmap.py`; this plan does not extend
the dataclass deviation from the surrounding Pydantic engine models. Its whole
target payload is only:

```python
model_config = ConfigDict(extra="forbid", frozen=True)

entity_uuid: UUID
old_position: tuple[StrictInt, StrictInt] | None
new_position: tuple[StrictInt, StrictInt] | None
```

Delete `old_directional_metadata`, `new_directional_metadata`,
`_OBJECT_BORDER_FIELDS`, the dynamic `getattr`/`setattr` snapshot/rollback
loop, and entity-stage calls to `recompute_tile_directional_blocking`. Those
values exist only for the object-derived directional Tile cache removed by this
plan; LEFT/ENTERED already carry the authoritative occupancy/path facts.
`_stage_entity_position(entity_uuid, None)` commits an occupancy removal and
returns the exact old/new position transition. Staging from empty occupancy to
a position commits restoration and returns the inverse transition.
`_publish_staged_entity_position` derives and publishes the applicable existing
LEFT or ENTERED fact once after Entity state commits.

Suspension:

1. requires `is_deployed=True` and `is_spatially_suspended=False`;
2. preserves the existing `Entity.position` as the sole return-position fact;
3. stages removal from both GridMap occupancy indexes;
4. sets `is_spatially_suspended=True` while retaining `is_deployed=True`;
5. preserves Game ownership, Entity identity, conditions, actions, values,
   observer state, attached lights, entity-anchored `SpatialCondition` instances,
   and the Entity's unchanged direct position; and
6. publishes the staged existing spatial LEFT fact with an empty destination.

Restoration:

1. requires `is_deployed=True` and `is_spatially_suspended=True`;
2. validates the chosen return Tile;
3. stages GridMap occupancy at the chosen position;
4. synchronizes `Entity.position` and sensory position when the chosen return
   differs from the preserved pre-suspension position;
5. sets `is_spatially_suspended=False`; and
6. publishes the staged existing spatial ENTERED fact with an empty origin.

Ordinary Entity movement requires `is_spatially_suspended=False`. Ordinary
deployment retains its current `is_deployed` guard, so restoration is the
return path for a suspended Entity. Terminal detach accepts either occupancy
state, clears `is_spatially_suspended`, unregisters the observer and GridMap
entity ownership through the existing teardown path, and completes with
`is_deployed=False`. `Game.entities` remains unchanged throughout suspension.

Delete `BanishedCondition.original_position`; it duplicates the unchanged
`Entity.position`. Banishment calls `suspend_from_world` during application.
During removal it reads the suspended Entity's preserved position, resolves the
current occupied-return rule, and passes the chosen destination to
`restore_to_world`. Its private writes to GridMap and Entity registries
disappear.

The recovered anchor behavior remains exact during suspension. Entity-anchored
conditions listen to the existing ENTERED fact, not LEFT: suspension therefore
does not destroy, unregister, or rewrite their GridMap footprint; restoration's
ENTERED fact relocates them through their existing `relocate_anchor` path. This
cut does not add a second suspended-condition state or mutate GridMap's
condition indexes from Entity code.

Gust of Wind continues to move entities through
`Entity.update_entity_position`. The existing `_pushes_in_flight` guard remains
the re-entrancy owner. Regression tests cover entry push, turn-start push,
ordinary LEFT/ENTERED ordering, and one movement per admitted trigger.

## 13. Implementation sequence

### Phase 0 — Pin current behavior

1. record direct object-placement callers;
2. record wall, door, WallTorch placement/light, center blocker, item-floor,
   height-filtered world-edge, bulk clear, and snapshot behavior;
3. record environment item builders, registered parameter models, factories,
   recipes, and every selected placement side;
4. checksum `dnd/items/environment_content.py` and record it with its
   action-declaration dependency in `DND_CONTENT_MIGRATION_LEDGER_2026-08-16.md`;
5. record every positional Entity writer and reader;
6. record Banishment suspend/return behavior and Gust movement behavior;
7. pin current event JSON for object placement, entity movement, item floor
   location, and world initialization; and
8. pin the recovered spatial-condition boundary: GridMap's three authoritative
   indexes, Tile layer references, `Tile.get_conditions()`, condition
   activation/movement/removal, entity-anchor relocation, object-anchor
   move-versus-removal behavior, concentration cleanup, and footprint-local
   performance; and
9. record the active test-preservation ledger in Section 14.

Gate: every active caller has one target operation in Sections 10–12.

### Phase 1 — Cold types and Tile storage

1. add semantic material/surface contracts;
2. add placement contracts with exact-integer rejection;
3. convert `AdjacentEdgeKey`, `WorldEdgeStructuralContribution`, and
   `WorldEdgeView` in place from dataclasses to frozen Pydantic models, adding
   the exact provider height interval and deleting the dataclass import;
4. add BaseBlock capabilities;
5. add `Tile.base_material`, `Tile.surface_layers`, and private Tile object bands
   with narrow GridMap-only mutation methods beside the unchanged
   `_spatial_condition_uuids` index;
6. add the read-only `Tile.has_light_modifiers()` guard over its existing
   private illumination/obscurement maps;
7. migrate GridMap Tile constructors and active Tile factories in the same cut,
   using `Material.EARTH` plus an empty layer tuple for the generic GridMap
   default, dressed stone for current floor factories, water for `water_factory`,
   dressed stone for `wall_factory`, and earth for difficult terrain;
8. add `set_tile_materials` as an in-place Tile mutation that preserves object
   bands and spatial-condition references;
9. preserve those explicit values until authored builders supply their selected
   materials/layers in Phase 3; and
10. add focused model/serialization and coexistence tests.

Gate: cold types import cleanly; Tile band round trips preserve exact UUID,
side, interval, and occupant state; the cold `WorldObjectPlacement` round trip
preserves orientation; and material mutation leaves the existing Tile UUID,
direct conditions, spatial-condition references, light modifiers, and object
bands unchanged.

### Phase 2 — GridMap object placement

1. add `_object_placements`;
2. implement pure validation plus place, move, orient, remove, and query;
3. implement local/opposite-edge collision validation and support-height band
   filtering;
4. migrate every GridMap-internal flat-index read;
5. preserve intrinsic Tile-side contributions and subjective provider
   filtering;
6. preserve the existing spatial-condition dictionaries and every public
   condition-footprint API without routing conditions through object bands;
7. publish object changes through the existing full `_fire_spatial_event`
   lifecycle;
8. migrate the object-anchor move/removal guard in
   `dnd/spatial/area_conditions.py` to `get_object_placement`, remove its
   `SPATIAL_OBJECT_CHANGED` subscription, and keep the same-XY PLACED no-op
   guard in the same cut;
9. preserve `clear()` object teardown, add replacement/removal guards, preserve
   conditions across in-place elevation change, enforce the exact
   center-versus-boundary elevation rules, reject direct conditions and
   nonempty entity occupancy in clear, reject light modifiers as well during
   full Tile replacement/removal, and fix the origin UUID lookup;
10. make accepted height changes invalidate movement, vision, light, and
    propagation for incident edges and recompute affected existing light; and
11. derive the current 2D edge union from intrinsic borders and only the
    relevant boundary height bands.

Gate: every object placement has one reverse value and exact Tile forward rows;
the condition indexes equal their pre-operation snapshots after object
operations; same-XY placement does not move attached conditions; and an
object-anchored condition follows a real move but retires on true removal.

### Phase 3 — Active structural items and direct callers

1. add the minimal structural item hierarchy;
2. migrate wall, door, cliff, and WallTorch with the exact pickable, usable,
   scalar-blocking, senses, and action-discovery defaults in Section 5;
3. migrate boulder and barricade to center-occupying `WorldItem` policy while
   leaving crates nonoccupying; move the exact authored `OilBarrel` subclass
   and direct builder into `dnd/content/items/environment_item_builders.py`,
   make the old mixed catalog reuse it, and do not move its spatial
   materialization dependency upward into an engine item/block module;
4. extend `BaseItem.place_on_grid` and `WallTorch.mount` with the exact placement
   parameters in Sections 4 and 7, remove `_wall_torch_position`, and attach its
   existing light source to the torch UUID;
5. extend the existing attached-light callback and bulk-clear path to
   synchronize object-anchored lights from GridMap placement, with reversible
   ordinary unplacement and terminal `put_out()` during clear;
6. migrate ordinary floor item helpers;
7. migrate `environment_item_builders.py` to the new boundary classes and
   intrinsic structure parameters;
8. migrate battlefield definitions and expand multi-side rows;
9. migrate arena/scenario builders through direct Tile materials and
   `BaseItem.place_on_grid`;
10. place starting torches unlit, publish static initialization, then ignite the
    selected torches and activate authored starting spatial conditions through
    their existing lifecycles; and
11. migrate action position lookups.

Gate: active map construction and object interactions use the new GridMap API.

### Phase 4 — Exact event payloads

1. evolve `SpatialChangeEvent`;
2. evolve the existing `WorldTileState` with direct material fields;
3. evolve `ItemLocationStateEvent`;
4. evolve `ItemState`, `ItemObservationState`, `WorldObjectState`, and the
   map-bootstrap `WorldInitialized`;
5. keep dynamic conditions on the existing `SpatialEffectChangeEvent`
   lifecycle rather than embedding them in `WorldInitialized`;
6. migrate combat-log and subjective readers to the new fields; and
7. pin canonical JSON and replay order, including static initialization before
   authored starting-condition application and starting-torch ignition.

Gate: the existing event stream reconstructs direct Tile materials and object
placements exactly, then reconstructs every active dynamic condition from its
existing condition/spatial facts without duplicate snapshot state.

### Phase 5 — Entity position cleanup

1. migrate inverse positional lookup to GridMap;
2. delete `Entity._entity_by_position`;
3. replace the existing `GridEntityPositionReceipt` dataclass with the internal
   three-field frozen Pydantic model; delete its directional metadata, dynamic
   cache snapshot/rollback, and the now-unused dataclass import;
4. remove the entity-entered/left factory's optional directional-cache
   parameters and their dead hint plumbing;
5. make Entity movement the single synchronization path;
6. migrate Game deployment/removal and every `GridMap.move_entity` caller, then
   delete that bypass;
7. migrate every `Entity.get_all_entities_at_position` reader to the public
   GridMap UUID query plus `Entity.get`, then delete that facade;
8. rename GridMap's register/unregister/stage/publish occupancy methods as
   internal primitives, migrate their only production calls into Entity's
   spatial methods, and prohibit public aliases;
9. preserve entity-anchor ENTERED relocation through the existing
   `SpatialCondition` handler; and
10. update reset and architecture gates.

Gate: Entity and GridMap positions remain synchronized across deploy, accepted
move, rejected preflight, committed publication failure, and removal.

### Phase 6 — Spatial suspension

1. add Entity suspension state and Entity suspend/restore methods;
2. extend the existing internal GridMap entity-position receipt to stage an
   empty or occupied destination and publish its applicable fact once through
   the underscored primitives;
3. migrate Banishment;
4. delete `BanishedCondition.original_position` and use the suspended Entity's
   preserved position as the sole return origin;
5. preserve occupied-return behavior through public movement APIs;
6. verify the existing observer, light, entity-anchor, and LEFT/ENTERED
   `SpatialCondition` behavior without condition-index writes from Entity; and
7. run Gust movement regressions through the shared movement path.

Gate: a Game-owned Entity can leave spatial occupancy and return while its
identity and gameplay state survive unchanged.

### Phase 7 — Hard cut and verification

1. delete the flat object indexes;
2. delete Tile directional object caches, directional item placement fields,
   `BaseItem.tile_uuid`, `WallTorch._wall_torch_position`, and direct
   floor-position writes;
3. delete `clear_location` and `clear_object_location` from hooks, GridMap APIs,
   overrides, and tests with no compatibility alias;
4. delete `Entity._entity_by_position` and all private external position
   writers;
5. delete `GridMap.move_entity`, `Entity.get_all_entities_at_position`,
   `recompute_tile_directional_blocking`, `_OBJECT_BORDER_FIELDS`, and the
   receipt's former directional metadata/cache rollback;
6. delete the entity-entered/left factory's former optional directional-cache
   arguments and `BanishedCondition.original_position`;
7. delete the public GridMap entity occupancy mutation/publication method names
   after their underscored replacements are called only from Entity; retain no
   aliases;
8. delete the former item-location floor `tile_uuid` and `position` fields and
   the duplicated `SpatialChangeEvent.tile_walkable`/`tile_visible` fields;
9. replace `WorldObjectState.position` with
   `placement: WorldObjectPlacement` and migrate
   `dnd/content/scenarios/battlefield_builders.py` snapshot assembly;
10. delete legacy object-position getters after every ledgered caller uses the
   placement value;
11. delete `get_objective_directional_structural_channels`,
   `get_directional_structure_state`, `ItemDirectionalStructureState`, and the
   former `directional_structure` event/observation fields after every consumer
   uses `BoundaryStructureState`;
12. delete duplicate directional door/wall constructors after callers converge;
13. scan the active runtime and remaining default-collected tests for every
   deleted private store, method, type, field, and constructor symbol, while
   verifying the separate checksum of the content-ledger source artifact;
14. assert that only GridMap mutates its spatial-condition dictionaries and only
   Tile methods mutate its spatial-condition reference index;
15. assert that only GridMap calls Tile object-band mutation methods and that no
   production caller reads or writes the private band dictionaries directly;
16. assert exact-integer rejection for every placement height/extent and
    world-edge integer field;
17. assert that object-anchor and attached-light movement subscriptions contain
   PLACED/REMOVED but not `SPATIAL_OBJECT_CHANGED`;
18. assert that no deleted spatial-effect wrapper/controller/materializer owner
   is reintroduced by the placement cut;
19. run focused and architecture suites; and
20. categorize unrelated collection blockers separately.

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
| `tests/engine/support.py` | replace direct Entity inverse-index mutation with the public Entity positioning method and GridMap read queries before dependent suites run |
| `tests/engine/test_condition_transform_ownership.py` | assert Banishment occupancy through `GridMap.get_entities_at` |
| `tests/engine/test_runtime_identity_registries.py` | reset Entity/GridMap ownership through the public runtime-reset surface |
| `tests/engine/test_entity_composition.py`, `tests/engine/test_action_cost_and_position_commit.py`, `tests/engine/test_manual_07_entity_composition.py`, `tests/engine/test_manual_11_grid_tiles_terrain_movement.py`, `tests/engine/test_runtime_identity_registries.py`, `tests/manual/test_01_runtime_identity_and_registries.py` | replace `Entity.get_all_entities_at_position` assertions with `GridMap.get_entities_at` UUID assertions plus `Entity.get` only where the live object is needed |
| `tests/engine/test_runtime_reset.py` | seed and verify Entity occupancy through GridMap/public reset APIs |
| `tests/engine/test_dice_event_semantics.py` | use the shared public runtime reset fixture |
| `tests/engine/test_manual_07_entity_composition.py` | use the shared public runtime reset fixture |
| `tests/engine/test_manual_09_conditions.py` | use the shared public runtime reset fixture |
| `tests/engine/test_manual_10_standard_conditions.py` | use the shared public runtime reset fixture |
| `tests/engine/test_spatial_effects.py` | retain the recovered condition activation, Tile-reference, footprint, replacement, transition, entity/object-anchor, concentration-linked, reveal, and cleanup capabilities; add placement/material coexistence plus direct `build_oil_barrel` destruction/material-transition coverage |
| `tests/engine/test_spatial_condition_performance_contract.py` | retain the footprint-local scaling contract unchanged while object-band operations are added beside it |
| `tests/engine/test_spatial_restraints.py` | retain linked spatial-condition ownership and public event assertions unchanged |
| `tests/engine/test_direct_spatial_effect_materialization.py` | retain exact direct condition subtype and authored-definition binding; map content remains the caller |
| `tests/engine/test_spatial_effect_reveal_idempotency.py` | retain existing reveal lifecycle semantics unchanged |
| `tests/engine/test_objective_state.py` | create an actual placed object through `BaseItem.place_on_grid` instead of seeding the flat index |
| `tests/manual/test_directional_environment_legacy_contract.py` | migrate its in-process wall/door recipes, edge behavior, actions, and perception cases to boundary items with explicit placement side |
| `tests/engine/test_spell_families.py` | retain its generic object-target validation without coupling it to authored OilBarrel content; extract WallTorch and placement-relevant spatial spell cases to active direct-item/spatial tests, and record the content-shaped remainder in the content test ledger |
| `tests/manual/test_133_item_core_lifecycle_legacy_contract.py` | extract and retain `GridMap.clear()` synchronizing each placed item exactly once against the new private bands/reverse placement, rejecting Tile-owned direct conditions and live entity occupancy, and not preserving `clear_location`/`clear_object_location` |
| `tests/manual/test_08_world_model_and_movement.py`, `tests/manual/test_128_antimagic_field.py` | replace direct `GridMap.move_entity` calls with a live Entity fixture and `Entity.update_entity_position`; retain LEFT/ENTERED and zone-entry/exit behavior |
| `tests/engine/test_action_cost_and_position_commit.py`, `tests/engine/test_move_settlement.py`, `tests/engine/test_elevated_jump_transaction.py`, `tests/engine/test_traversal_connectors.py` | delete only the synthetic staging-failure cases that monkeypatch the removed directional cache recomputation; retain invalid-destination, event-veto/publication-failure, debit rollback, movement settlement, jump, and connector capability tests |

Default-collected manual test dispositions are:

| Current files | Recorded disposition |
|---|---|
| `test_01_runtime_identity_and_registries.py`, `test_02_entity_anatomy.py`, `test_09_action_discovery_and_costs.py`, `test_103_game_summary_store.py`, `test_10_combat_resolution.py`, `test_11_equipment_inventory_and_items.py`, `test_12_perception_light_stealth_and_invisibility.py`, `test_13_spellcasting_core.py`, `test_14_spell_families.py`, `test_17_encounters_turns_controllers.py`, `test_18_sessions_api_client_contract.py`, `test_20_content_extension_basics.py`, `test_21_spell_and_feature_extensions.py` | migrate direct `Entity._entity_by_position.clear()` setup to the shared public runtime reset fixture; each test retains its existing capability classification in the server/content cleanup ledger |
| `test_09_action_discovery_and_costs.py`, `test_11_equipment_inventory_and_items.py`, `test_131_advanced_item_world_legacy_contract.py`, `test_133_item_core_lifecycle_legacy_contract.py`, `test_134_stackable_usable_item_legacy_contract.py` | migrate floor assertions to `WorldObjectPlacement` and transaction-owned item-location facts; retain action, pickup/drop, stack, destruction, and equipment behavior |
| `test_133_new_spells_batch4_legacy_contract.py` | migrate displacement and Banishment occupancy assertions to `GridMap.get_entities_at`; retain the spell behavior |
| `test_37_authored_encounter_mechanics.py` | migrate door lookup, placement, and actions to `BoundaryDoor` and `get_object_placement`; retain authored encounter mechanics |
| `test_directional_environment_legacy_contract.py` | migrate direct recipes and wall/door mechanics into engine boundary-item tests using `environment_item_builders.py` and explicit placement sides |
| `test_113_subjective_replication_routes.py`, `test_120_subjective_world_projection.py`, `test_125_subjective_objective_render_parity.py` | extract engine-native door state, perception, and event assertions into boundary-item/event tests; remove their server-shaped wrappers from the active suite |
| `test_11_equipment_inventory_and_items.py` door cases | replace `directional_door_recipe`/`TutorialDoor` with `environment_item_builders.build_directional_door` returning `BoundaryDoor`, plus explicit placement side; retain inventory/use-action behavior |
| `test_134_stackable_usable_item_legacy_contract.py` door cases | extract the three door/path/action cases to active `BoundaryDoor` capability tests; record the remaining mixed recipe tests in the content test ledger |
| `test_legacy_reactive_reaction_coverage.py` door cases | replace `door_recipe`/`DoorFixture` with the direct BoundaryDoor builder; retain path invalidation and open/close reaction behavior |
| `test_131_inventory_use_actions_legacy_contract.py` | record its arcane-device mixed recipe coverage in the content test ledger and move the content-shaped wrapper outside the default suite |

Every current default-suite import of `dnd.items.environment_content` has one
of these destinations:

- the three subjective/server files: extracted engine-native door facts;
- `test_11_equipment_inventory_and_items.py`: direct BoundaryDoor builder;
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
`Entity._entity_by_position`, `BaseItem.tile_uuid`,
`WallTorch._wall_torch_position`, the former item-location and world-object
position fields, `SpatialChangeEvent.tile_walkable`/`tile_visible`,
`clear_location`/`clear_object_location`, the directional structure
methods/type/fields, `GridMap.move_entity`,
`Entity.get_all_entities_at_position`, `recompute_tile_directional_blocking`,
`_OBJECT_BORDER_FIELDS`, receipt directional metadata,
`BanishedCondition.original_position`, the former public GridMap occupancy
mutation/publication names, the entity-entered/left directional-cache
parameters, external Tile band writes, and legacy directional wall/door
constructor names across production and tests.
The content-migration ledger separately inventories the preserved mixed
`environment_content.py` source artifact and its recipe tests. The default
suite contains zero imports of that source artifact at the Phase 7 gate.

Placement tests cover:

- pure placement validation preserving current state;
- invalid drop and displaced-equipment destinations preserving inventory,
  ownership, and floor state;
- center placement and optional center orientation;
- exact-integer rejection for every extent/base/top value, including `True`,
  floats, and numeric strings;
- one boundary side plus independent orientation;
- multi-band structure extent;
- occupying collision and nonoccupying attachment coexistence;
- opposite-side physical-edge collision;
- height-filtered edge queries: a lower supporting cliff does not block travel
  across the upper terrace, an upper wall does, and the cliff blocks travel from
  the lower surface to the upper surface;
- door channel changes with stable placement;
- exact nonpickable, usable-discovery, scalar-blocking, senses, and action
  defaults for every structural class;
- boulder, barricade, and OilBarrel center-slot collision plus explicit
  nonoccupying crate coexistence;
- direct base-material and ordered-layer serialization;
- in-place material mutation preserving Tile UUID, direct conditions,
  spatial-condition references, and object bands;
- `Tile.get_conditions()` returning direct and spatial conditions while placed
  object bands coexist independently;
- object place/move/orient/remove leaving all condition indexes unchanged;
- object-populated, direct-condition-owning, spatial-condition-covered,
  illumination/obscurement-modified, and entity-occupied Tile replacement,
  removal, and rectangle-overwrite rejection;
- support-height mutation preserving direct/spatial conditions, rejecting any
  center placement, retaining absolute boundary intervals and connector guards,
  while surface-kind/slope-only mutation preserves both placement classes;
- primed path/FOV/light/propagation caches all changing correctly when endpoint
  height makes an adjacent boundary provider enter or leave relevant bands;
- bulk clear invoking each object-removal hook exactly once, clearing private
  bands/reverse placements, putting out a lit WallTorch without stale light
  UUID/state, and retaining active-SpatialCondition, Tile-owned direct-
  condition, and nonempty-entity-occupancy rejection;
- `(0, 0)` UUID lookup;
- placement move/orient/remove consistency; and
- wall, door, cliff, and WallTorch direct construction;
- object-anchored condition relocation following committed GridMap placement;
- same-cell orientation/open/close `OBJECT_CHANGED` facts never entering the
  condition-anchor or attached-light movement handlers and producing no false
  `FOOTPRINT_CHANGED` fact;
- a lit WallTorch's existing light following real object movement, becoming
  non-illuminating while unplaced, and restoring on re-placement; and
- true anchor removal retiring the attached condition through its existing
  lifecycle.

Event/replay tests cover:

- exact current/previous placement JSON;
- exact floor item location;
- one final floor-location fact from each inventory/equipment/Entity
  transaction owner;
- bootstrap object placement represented by one final `WorldInitializedEvent`;
- complete `WorldInitialized` direct Tile materials and placements;
- absence of duplicated dynamic-condition state in `WorldInitialized`;
- authored starting-condition application after world initialization through
  existing condition and `SpatialEffectChangeEvent` facts;
- authored WallTorches unlit in the static snapshot and ignited only afterward
  through their existing interaction/light lifecycle;
- `WorldObjectState.placement` as the sole snapshot position;
- movement/vision/light/propagation edge queries;
- intrinsic Tile-border union and subjective object-provider filtering;
- intrinsic Tile providers carrying their exact support band while object
  providers carry their exact placement interval;
- combat-log and subjective consumption; and
- reconstruction from the existing event stream.

Entity tests cover:

- deploy, move, and terminal removal synchronization;
- inverse lookup through GridMap;
- invalid/rejected movement preflight preserving every position owner;
- committed movement publication failure retaining its existing distinct
  `position_committed=True` semantics;
- suspension preserving Game ownership and Entity state;
- suspension preserving current observer, attached-light, and entity-anchor
  `SpatialCondition` state and authoritative footprint;
- restoration to the preserved or resolved return position;
- Banishment application/removal using public methods;
- occupied Banishment return behavior;
- preservation of the current sensory-observer state; and
- Gust entry and turn-start push re-entrancy.

Architecture tests cover the dependency graph in Section 2, the Pydantic cold
contracts, the single object reverse index, the two synchronized entity stores,
the existing three GridMap spatial-condition indexes plus Tile references, the
separate object/condition mutation owners, private Tile band stores, full
spatial-event lifecycle publication for object facts, a Pydantic rather than
dataclass entity-position receipt with no directional-cache payload, frozen
Pydantic world-edge values, exact anchor/light subscriptions, the single Entity
movement entry point, Entity as the sole caller of GridMap's internal occupancy
mutation/publication primitives, and the absence of external writes to private
dictionaries.

## 15. Completion criteria

1. Tile base material and ordered surface layers are direct validated semantic
   facts, not another mutable state wrapper.
2. Center and four boundary placements support exact integer vertical bands
   with no coercion.
3. GridMap owns one reverse object-placement value per placed object.
4. Active walls, doors, cliffs, attachments, boulders, barricades, OilBarrels,
   and floor items use the same API with explicit occupying policy.
5. Drop and displaced-equipment transactions preflight through the pure GridMap
   placement validator.
6. World-edge queries derive from neutral capabilities on placed boundary
   providers, filtered to bands relevant to endpoint support heights, while
   retaining intrinsic Tile borders and subjective filtering.
7. Existing events carry exact placement and direct Tile-material facts.
8. Existing replay, combat log, and subjective consumers use those facts.
9. Entity retains direct position and GridMap retains synchronized UUID indexes.
10. `Entity._entity_by_position` and private external position writes are gone.
11. Banishment uses general Entity suspension/restoration.
12. Suspended entities preserve current observer, attached-light, and
    entity-anchored `SpatialCondition` state.
13. Gust uses the shared ordinary movement path with preserved re-entrancy.
14. BaseItem floor authority and former item-location floor fields are removed.
15. `clear_location` and `clear_object_location` are deleted with no alias or
    compatibility branch.
16. `GridEntityPositionReceipt` is an internal three-field frozen Pydantic
    model; its directional-cache payload and the obsolete GridMap dataclass
    import are gone.
17. `SpatialChangeEvent.tile_walkable` and `tile_visible` are deleted after
    migration to the complete `WorldTileState` payload.
18. The former directional structure type, methods, and fields are removed.
19. `WorldObjectState` owns one complete placement value.
20. The active-runtime/default-suite deleted-symbol scan is empty, and the
    mixed content source artifact has an exact content-ledger checksum.
21. The default suite imports active direct modules for every extracted
    capability and contains zero `environment_content.py` imports.
22. GridMap remains the sole spatial-condition footprint owner; Tile retains
    its layer-indexed condition references and complete condition query.
23. World-object bands never contain spatial-condition UUIDs, and world-object
    operations never mutate condition indexes.
24. Material mutation preserves the live Tile, its direct conditions, its
    spatial-condition references, light modifiers, and all object bands.
25. `WorldInitialized` contains static map state only; dynamic conditions replay
    from their existing application and spatial-change facts.
26. Object-anchored conditions follow committed object moves and retire on true
    removal without reading duplicate item position; their handler and the
    attached-light movement callback do not subscribe to `OBJECT_CHANGED`.
27. WallTorch has no private position; its existing attached light follows,
    suppresses, restores, and destroys from GridMap placement and current light
    machinery.
28. Bulk clear removes every placed object exactly once and clears bands while
    terminally putting out WallTorches and continuing to reject active
    SpatialConditions, Tile-owned direct conditions, or nonempty entity
    occupancy.
29. Accepted height changes preserve condition footprints, obey exact
    center/boundary admission, invalidate all structural channel caches, and
    recompute affected existing lights.
30. Full Tile replacement/removal rejects direct conditions,
    spatial-condition coverage, object placement, light modifiers, and entity-
    occupied XY while in-place material/elevation mutation preserves Tile
    identity and those owners/references.
31. Existing spatial-condition performance remains proportional to the
    condition footprint and touched positions, not total map size.
32. `AdjacentEdgeKey`, `WorldEdgeStructuralContribution`, and `WorldEdgeView`
    are frozen Pydantic models with exact integer validation and no custom
    serializer or parallel contract.
33. `GridMap.move_entity`, `Entity.get_all_entities_at_position`,
    `recompute_tile_directional_blocking`, and their dead cache machinery are
    gone; Entity movement and GridMap UUID lookup are the only public paths.
34. GridMap's entity occupancy mutation/publication primitives are internal and
    called only by Entity; their former public names have no aliases.
35. Banishment uses the suspended Entity's preserved position directly and has
    no `original_position` mirror.
36. Entity-entered/left factories carry no dead directional-cache parameters.
37. Focused capability and architecture tests pass.
38. Both independent reviewers and the final three-way anti-slop pass approve
    this document revision.
