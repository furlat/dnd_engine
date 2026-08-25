# Tile, surface, world-placement, and GridMap master migration plan

Status: ordered geometry and active-runtime scope APPROVED. The previously
approved ordered-geometry revision is SHA-256
`46de9f570fb59fd8c9e8a105a3a699287a7881c93c880827d804faefad9c7f2d`.
The geometry and ownership decisions remain unchanged. The active-runtime
scope set was independently approved on master SHA
`abe1a01dbf54b84b23c94488931177c23d9498747c1e75b87b1137c3fd1bd83c`.
Implementation may resume only through the approved active-only Slice 3.2
ledger.

Revision note: this version defines cardinal boundaries as Tile-owned side
volumes. Adjacent `I:EAST` and `J:WEST` bands are distinct spatial volumes and
may both contain occupying objects at the same heights. Ordered world
transitions evaluate the source Tile's exit side and the destination Tile's
entry side; no boundary object is owned by an abstract in-between edge.

This document is the authoritative placement plan. It supersedes both
`DND_TILE_OBJECT_PLACEMENT_AGREEMENT_2026-08-17.md` and
`DND_TILE_WORLD_ITEM_PLACEMENT_CLEAN_PLAN_2026-08-17.md`. It incorporates the
implemented optical, illumination, subjective-observation, spatial-condition,
and turn-start boundaries described by `unified_vision_light.md`.

The previously approved Phase 3 implementation guidance used a shared-edge
collision model and is revoked by this revision. It must not be implemented or
used as migration authority. New Phase 3 guidance is written only after this
master and the bounded Phase 0-2 correction have been accepted.

The plan describes the durable destination and the order in which it can be
reached. Exact current call sites, temporary test counts, and one-off content
coordinates belong in an implementation ledger captured at the beginning of
each phase; they are not architectural rules.

## 1. Objective

Create one coherent in-process world model in which:

1. one `GridMap` contains one playable `Tile` at each `(x, y)`;
2. each Tile describes its support surface, intrinsic cell mechanics, objective
   illumination, active condition references, entities, center objects, and
   four cardinal boundaries;
3. placed objects are real engine objects with semantic game properties, not
   anonymous booleans or renderer identifiers;
4. Tile owns forward spatial membership while GridMap owns the corresponding
   reverse placement lookup and every spatial mutation;
5. Entity owns its objective coordinate, while subjective `Senses` remains a
   reducer-owned projection produced from objective events;
6. movement, ordinary optics, physical propagation, and illumination retain
   distinct meanings and explicit invalidation rules;
7. completed events contain the exact committed facts needed for replay,
   summaries, and any client implementation; and
8. authored content can later construct maps declaratively without becoming a
   second world-state, event, or rendering system.

The result is first and foremost the map foundation for a single-process
Python `Game` and its pygame presentation. The engine still publishes
renderer-neutral semantic facts, but this migration is proved entirely inside
that process. Cross-process servers, HTTP transport, SDKs, TypeScript or other
language projections, generated wire mirrors, and networking compatibility
are deliberately deferred until the in-process mechanics are complete and
flawless. A later transport plan may consume the established semantic event
boundary; it cannot constrain or broaden this migration in advance.

### 1.1 Current product and validation boundary

The implementation boundary for every phase of this plan is:

- active Python mechanics under `dnd/`;
- active authored Python content needed to construct and exercise those
  mechanics in process;
- the existing in-process EventQueue, objective state, sensory reducer, light,
  condition, movement, item, and GridMap lifecycles; and
- collecting public behavior, dependency, replay, and locality tests whose
  maintained subject is that active Python runtime.

The following are not callers, compatibility targets, validation gates, or
zero-reference obligations for this migration:

- `deprecated/**`;
- removed or deprecated `server/**` modules and server-only tests;
- SDKs, TypeScript/JavaScript sources, declarations, distributions, maps, or
  fixtures;
- generated cross-language wire contracts and deprecated replay/projection
  models; and
- presentation/icon ledgers whose rows no longer identify any constructible
  active mechanic.

Those artifacts may remain stale or collection-blocked while deprecated. Do
not restore a dependency, generator, facade, DTO, or transport layer to keep
them synchronized. Active Python generated modules are edited only when the
single-process runtime imports them and would otherwise fail to load; unused
presentation rows are not a mechanics blocker.

`DND_TILE_WORLD_ITEM_ACTIVE_RUNTIME_SCOPE_AMENDMENT_2026-08-24.md` is the
bounded review artifact for this scope correction. Phase implementation may
resume only after that amendment, this master revision, the corrected Phase 3
guidance, and the active-only Slice 3.2 ledger are approved together.

## 2. Enduring architectural decisions

### 2.1 One playable surface per XY

There is exactly one playable support surface at `(x, y)`. `Tile.height` is
its support elevation in the engine's existing five-foot integer steps.

Several independent grids, stacked playable Tiles at one XY, volumetric actor
occupancy, and 3D ray casting are not part of this world model. Vertical bands
describe the physical placement and rendering extent of world objects around
the one support surface; they do not create another playable cell.

### 2.2 Height has a deliberately narrow mechanical role

Height and vertical bands participate in:

- support-surface traversal;
- stairs, ramps, and connector admission;
- placement collision between structures occupying the same center bands or
  the same side bands of one Tile;
- exact world serialization; and
- client rendering of cliffs, walls, raised terrain, and attachments.

Ordinary optics and physical propagation remain conservative two-dimensional
XY calculations. They use explicit authored `OPTICAL` and `PROPAGATION`
policies and do not perform eye-height, ray-height, or band-intersection math.
A structure's vertical interval therefore never silently invents its optical
or propagation behavior.

### 2.3 Objective and subjective state remain separate

`Entity.position` is objective world state. A deployed Entity's UUID is also
present in exactly one Tile's forward occupant set.

`Senses.position`, visible cells, explored cells, effective observer light,
and perceived contacts are subjective projection state. Only
`SpatialSensesSystem`, or replay of its `SensoryUpdateEvent`, writes those
fields. Entity, Game, GridMap, movement actions, and encounter code do not
mirror objective position directly into Senses.

EFFECT-phase mechanics use `Entity.position` or an exact position carried by
the event. This is essential because the subjective projection intentionally
settles later, at pre-completion.

### 2.4 Surface composition and active mechanics are different ownership forms

A Tile owns persistent surface composition:

- one base material; and
- an ordered sequence of surface layers above it.

Grass over earth, boards over stone, snow over ground, and similar authored
composition belong here. The ordering is semantic game data and can later
guide client asset binding.

Wetness, burning, fog, magical darkness, grease, ice mechanics, spikes, and
other active rules remain `SpatialCondition` instances. GridMap owns their
footprint indexes and each Tile stores condition UUID references by layer.
There is no parallel `tile.effects` collection and no second condition type.

A permanent terrain transformation replaces the Tile's surface through a
GridMap mutation and event. A temporary or source-owned rule uses the existing
condition lifecycle.

### 2.5 Placement authority

- Tile owns forward object membership at its center and boundaries.
- GridMap owns `object UUID -> WorldObjectPlacement` and all placement writes.
- An object owns its intrinsic placement specification: center or boundary,
  whether it reserves bands, and its vertical extent.
- A placement owns the selected Tile, boundary side, base height, top height,
  and orientation.
- Boundary side and object orientation are separate facts.
- A boundary side is inside and owned by its selected Tile. The adjacent
  Tile's opposing side is another valid volume, not a mirror or shared slot.
- Two opposing side volumes may both be occupied; their objects render as
  adjacent layers and are evaluated in traversal order.
- The caller never chooses whether an object occupies a slot and never passes
  blocked channels as placement arguments.
- A floor item does not retain a second `tile_uuid` or floor-position authority.

### 2.6 Three structural channels

The structural channels are exactly:

- `MOVEMENT`;
- `OPTICAL`; and
- `PROPAGATION`.

Ordinary sight and ordinary light-source geometry use the same `OPTICAL`
topology. Objective illumination remains separate Tile state. Special senses
interpret objective optics, propagation, illumination, obscurement, and
perceivability later in `SpatialSensesSystem`.

### 2.7 Pydantic and dependency discipline

Persisted, authored, placement, event, and replay contracts are Pydantic
models. Exact coordinates and height steps reject booleans, floats, strings,
and coercion. Internal hot query views may remain frozen slot dataclasses when
they are not serialized or exposed through the API. No custom serialization
layer is introduced.

The migration preserves direct imports and explicit typed capabilities. It
introduces no late imports, `TYPE_CHECKING` cycle masks, dynamic `getattr`
contracts, concrete-item imports in GridMap, compatibility aliases, dual-write
periods, or renderer asset fields.

## 3. Authoritative ownership model

| Fact | Authoritative owner | Derived/indexed readers |
|---|---|---|
| Tile identity at XY | GridMap Tile dictionary | world snapshots, spatial queries |
| Surface composition | Tile | content authoring, rules, event projection |
| Support elevation | Tile | movement edges, connectors, placement defaults |
| Intrinsic center optics/propagation | Tile | GridMap topology queries |
| Objective illumination contributions/caps | Tile, mutated through GridMap | resolved light, sensory reducer |
| Direct Tile conditions | Tile/BaseBlock condition ownership | rules and inspection |
| Spatial-condition identity and mechanics | SpatialCondition | GridMap footprint index, Tile UUID references |
| Object forward membership | Tile center/boundary bands | local spatial queries |
| Object reverse placement | GridMap | items, actions, events, content, clients |
| Object placement specification | placed BaseBlock capability/value | GridMap admission |
| Entity objective coordinate | Entity | GridMap objective queries |
| Entity inverse occupancy | Tile `entity_uuids` | collision, targeting, pathfinding |
| Deployed Entity ownership | Game | Entity lifecycle commands |
| Ordered boundary-transition topology | derived by GridMap from the source exit side and destination entry side | movement, FOV, light, propagation |
| Subjective observation | Senses reduced by SpatialSensesSystem | actions, subjective reducers, clients |
| Completed historical facts | Event stream | replay, summaries, combat logs, clients |

An index is permitted only when it answers the inverse direction of an
authoritative relation and has one mutation owner. Tile forward membership and
GridMap reverse object placement are such a pair. A second item location field,
Entity class position map, or GridMap entity-position dictionary is not.

## 4. Dependency graph

Arrows mean direct imports.

```text
dnd/types/*
  -> stdlib, pydantic

dnd/core/world_edges.py
  -> dnd/types/*

dnd/core/base_tiles.py
  -> base_block, base_conditions, world_edges, dnd/types/*

dnd/core/events/*
  -> cold core values, dnd/types/*
  -X-> GridMap, Entity, Senses, authored content, renderer code

dnd/core/gridmap.py
  -> base_block, base_conditions, base_tiles, world_edges, core/events,
     dnd/types/*
  -X-> Entity, concrete BaseItem subclasses, concrete SpatialCondition classes

dnd/blocks/base_item.py
  -> base_block, GridMap public placement/query boundary, dnd/types/*

dnd/blocks/sensory.py
  -> BaseBlock, GridMap queries, core/events, dnd/types/*
  -X-> Entity, Encounter, authored content

dnd/entities/entity.py
  -> entity blocks, GridMap internal occupancy primitives, sensory registration
  -X-> dnd/spatial/*

dnd/spatial/area_conditions.py
  -> Entity, GridMap, events, dnd/types/*

dnd/items/* and dnd/content/*
  -> blocks, GridMap commands, semantic types
```

The dependency direction is important: Entity and BaseItem do not coordinate
concrete spatial mechanics. `SpatialCondition` observes exact spatial events
through the existing EFFECT-phase handler boundary. GridMap sees only neutral
BaseBlock/BaseCondition capabilities and UUIDs.

## 5. Cold semantic and placement vocabulary

Exact module names may follow the repository's established `dnd/types`
organization. The ownership and field semantics below are normative.

### 5.1 Materials and surface composition

Use `Material`, not `MaterialKind`:

```python
class Material(StrEnum):
    EARTH = "earth"
    SAND = "sand"
    STONE = "stone"
    WOOD = "wood"
    METAL = "metal"
    FABRIC = "fabric"
    GLASS = "glass"
    WATER = "water"
    ICE = "ice"
    VEGETATION = "vegetation"


class SurfaceLayer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    material: Material
    description: str = ""


class TileSurface(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_material: Material
    layers: tuple[SurfaceLayer, ...] = ()
    description: str = ""
```

`TileSurface` is an immutable structural value, not a `ModifiableValue` and not
a new state system. Runtime replacement occurs through GridMap, which stores a
new validated value and publishes the resulting Tile fact. Ordered layers may
repeat a material when the descriptions represent distinct authored strata;
the engine does not deduplicate them implicitly.

The enum begins with materials used by active maps and can grow when a game
rule or authored surface requires a distinction. It is not a generic tag bag
and does not contain sprite names, tileset coordinates, or renderer layers.

### 5.2 Placement values

```python
class WorldPlacementKind(StrEnum):
    CENTER = "center"
    BOUNDARY = "boundary"


class WorldPlacementSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: WorldPlacementKind
    occupies_bands: bool
    vertical_extent_steps: StrictInt = Field(ge=1)


class WorldObjectPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    object_uuid: UUID
    tile_uuid: UUID
    position: tuple[StrictInt, StrictInt]
    kind: WorldPlacementKind
    occupies_bands: bool
    boundary_direction: CardinalDirection | None = None
    base_height_steps: StrictInt
    top_height_steps: StrictInt
    orientation: CardinalDirection | None = None
```

The object owns `WorldPlacementSpec`. `WorldObjectPlacement` is its resolved,
committed snapshot. The placement flattens the resolved fields instead of
embedding a second nested copy of the specification.

Validation requires:

1. `top_height_steps > base_height_steps`;
2. `top - base` equals the object's declared vertical extent;
3. center placement has no boundary direction;
4. boundary placement has one cardinal boundary direction;
5. the placement kind and occupancy equal the provider's current specification;
6. center placement begins at the Tile support height; and
7. boundary side never supplies an implicit orientation. Symmetric objects may
   remain unoriented; an object whose authored semantics require a facing must
   provide it explicitly before placement.

### 5.3 Boundary semantics

Use one semantic item value for authored structures:

```python
class BoundaryStructureKind(StrEnum):
    CLIFF = "cliff"
    EMBANKMENT = "embankment"
    RETAINING_WALL = "retaining_wall"
    WALL = "wall"
    DOOR = "door"
    FENCE = "fence"


class BoundaryStructure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    structure: BoundaryStructureKind
    material: Material
    blocked_channels: tuple[WorldEdgeChannel, ...]
```

The value is a computed current snapshot, not a second stored state object. A
closed door returns its closed channels; an open door returns the remaining
channels, normally none. The placement supplies side and height. Kind and
material do not automatically imply channels inside GridMap.

## 6. Tile storage

### 6.1 Tile fields retained and added

Tile continues to own:

- identity, name, and objective coordinate;
- movement costs by movement mode;
- intrinsic `blocks_optics` and `blocks_propagation` cell policies;
- support height, progressive-surface kind, and slope axis;
- base and resolved objective illumination through source-owned contributions;
- direct BaseCondition children; and
- UUID references to independently owned SpatialConditions by layer.

It gains private forward stores initialized as Pydantic private attributes:

```python
surface: TileSurface
_entity_uuids: set[UUID] = PrivateAttr(default_factory=set)
_center_object_bands: dict[StrictInt, TileObjectBand] = PrivateAttr(
    default_factory=dict,
)
_boundary_object_bands: dict[
    CardinalDirection,
    dict[StrictInt, TileObjectBand],
] = PrivateAttr(
    default_factory=lambda: {
        direction: {} for direction in CardinalDirection
    },
)
```

The current intrinsic and object-derived cardinal booleans disappear after
their authored uses have migrated to real boundary objects. Solid wall cells
remain valid center Tile mechanics through movement cost and intrinsic optics/
propagation; they are not silently converted into four boundary walls.

### 6.2 Band record

```python
@dataclass(frozen=True, slots=True)
class TileObjectBand:
    object_uuids: frozenset[UUID] = frozenset()
    occupant_uuid: UUID | None = None
```

Orientation is not copied into every occupied band. It exists once in the
GridMap placement value. `occupant_uuid`, when present, must be a member of
`object_uuids`.

The band record is an internal hot value, not a persisted contract. GridMap
replaces a complete frozen record when membership changes; it never mutates an
exposed set in place. Tile exposes copy/frozen query views, and no content or
gameplay caller receives a mutable reference to any forward store.

Each key `z` represents `[z, z + 1)`. One object covering `[0, 2)` appears in
bands `0` and `1`, but remains one object with one reverse placement. Empty
band rows are removed immediately. All four boundary dictionaries always
exist.

### 6.3 Object invariants

For every placed object:

1. exactly one reverse placement exists;
2. its Tile UUID and XY resolve to the same live Tile;
3. its UUID occurs in every band in `[base, top)` at exactly one center or
   boundary location;
4. it occurs nowhere else;
5. an occupying object is the occupant of every band it covers;
6. a nonoccupying attachment is never the band occupant;
7. overlapping nonoccupying objects are allowed;
8. two occupying objects cannot overlap on the same center bands;
9. two occupying objects cannot overlap on the same cardinal side bands of the
   same Tile;
10. an occupying object on the adjacent Tile's opposing side is independent
    and may cover the same heights; and
11. the adjacent Tile never receives a mirror copy.

GridMap reads both independent side volumes when resolving an ordered
transition: the source-facing side is the exit layer and the
destination-facing side is the entry layer.

### 6.4 Entity invariants

For every deployed Entity:

1. `Entity.position` resolves to one Tile;
2. that Tile contains the Entity UUID once;
3. no other Tile contains it;
4. GridMap's objective query resolves the Entity through neutral UUID lookup and
   verifies matching Tile membership; and
5. Senses may temporarily represent the prior subjective projection until the
   causal spatial event reaches pre-completion.

An undeployed or suspended Entity is absent from every Tile. Its own objective
position may retain the intended or last coordinate according to the Entity
lifecycle, but it is not spatially present.

### 6.5 Tile mutation rules

GridMap owns Tile creation, surface replacement, support mutation, identity
replacement, removal, and clear.

- Surface replacement mutates the existing Tile and preserves entity, object,
  light, and condition ownership.
- Support-height mutation mutates the existing Tile. It rejects a change that
  would invalidate a support-relative placed object or connector. Spatial
  conditions remain valid because their footprint is XY-owned.
- A full Tile identity replacement or removal is rejected while it would
  orphan entities, objects, direct conditions, spatial-condition references,
  connectors, or live illumination contributions.
- `GridMap.clear()` performs its defined object/light teardown through existing
  hooks and rejects remaining deployed entities or live conditions. Runtime
  reset remains the whole-process registry reset boundary.

These rules prevent Tile identity changes from becoming an implicit removal
mechanism for other owners.

## 7. Object capabilities and concrete world items

### 7.1 Neutral BaseBlock surface

GridMap accepts any registered BaseBlock UUID and uses two explicit neutral
capabilities:

```python
def get_world_placement_spec(self) -> WorldPlacementSpec:
    return WorldPlacementSpec(
        kind=WorldPlacementKind.CENTER,
        occupies_bands=False,
        vertical_extent_steps=1,
    )


def get_boundary_structure(self) -> BoundaryStructure | None:
    return None
```

This is the complete object-placement capability surface. A boundary provider
returns one freshly computed `BoundaryStructure` containing its current
channels; there is no separately stored or overridable channel answer. GridMap
never discovers placement semantics with reflection or concrete type checks.

### 7.2 Item organization

`WorldItem(BaseItem)` is the useful shared base for fixed environmental objects
that own an explicit `WorldPlacementSpec`. Concrete classes express mechanics:

```text
BaseItem
  portable/equipment/usable items
  WorldItem
    fixed center structures
    walls, cliffs, retaining walls, fences
  UsableItem
    doors
    wall-mounted interactive fixtures
```

The hierarchy is not the GridMap contract. A usable boundary door can remain a
direct `UsableItem` and override the same two neutral capabilities, avoiding
multiple inheritance and preserving truthful action discovery. Semantic-only
`CenterWorldItem` and `BoundaryWorldItem` layers are unnecessary.

Placement-shape fields are immutable while placed. A geometry change removes
and re-places the object through GridMap. Door open/close and similar mechanical
state changes preserve placement and publish an object-state spatial event.

### 7.3 Required concrete semantics

- One wall or door object occupies one cardinal boundary, not several
  `blocked_directions` at once.
- A cliff is an authored boundary structure, never inferred merely from a Tile
  height difference.
- A drape, torch, sign, or decorative attachment can share bands with one
  occupying boundary structure.
- A boulder, barricade, barrel, or other physical center blocker explicitly
  declares center-band occupancy.
- Dropped portable objects use the neutral nonoccupying center specification
  unless their actual mechanics require occupancy.
- Door open/close changes its current movement, optical, and propagation
  channels without changing placement.
- Wall-mounted lights query their GridMap placement and do not own another
  private world coordinate.

## 8. GridMap placement boundary

### 8.1 Stored index

The flat object dictionaries become:

```python
_object_placements: dict[UUID, WorldObjectPlacement]
```

There is no separate `objects_by_position` cache. `get_objects_at(position)`
reads the one Tile's band collections, deduplicates UUIDs, and returns a copy.
`get_object_placement(uuid)` returns the reverse value.
`get_object_position(uuid)` remains a durable derived convenience that returns
the placement coordinate or `None`; it never owns state.

### 8.2 Commands

GridMap exposes one physical command family for every object:

```python
place_object(object_uuid, position, *, boundary_direction=None,
             base_height_steps=None, orientation=None, parent_event=None)
move_object(object_uuid, position, *, boundary_direction=None,
            base_height_steps=None, orientation=None, parent_event=None)
orient_object(object_uuid, orientation, *, parent_event=None)
remove_object(object_uuid, *, parent_event=None)
```

Item, action, inventory, content, and map-building code call this same boundary.
There is no parallel BaseItem placement framework. Item workflows retain their
existing item-location lifecycle and adapt its FLOOR payload to the committed
placement.

### 8.3 Admission and mutation

For every command GridMap:

1. resolves the provider and its placement specification;
2. resolves the target Tile and defaults support-relative values;
3. builds the exact frozen placement;
4. validates only the selected Tile's local center or cardinal-side bands
   before mutation;
5. records the previous placement when present;
6. mutates only Tile bands and `_object_placements`;
7. invalidates the exact changed structural channels;
8. publishes the existing spatial lifecycle with exact before/after placement
   facts and affected owner/adjacent cells; and
9. returns the committed placement.

An identical place is idempotent. A different existing placement is handled by
`move_object`, not an implicit hidden move. Destination validation completes
before the old placement is removed.

Object relocation preserves the existing removal-then-placement affordance:

1. the removal fact carries the complete previous placement and the intended
   destination coordinate in `SpatialChangeEvent.old_position`, whose existing
   leave-event meaning is the destination rather than another copy of the
   origin;
2. the placement fact carries the complete new placement; and
3. both share the caller's causal parent.

This lets existing EFFECT handlers distinguish relocation from terminal
removal without consulting an obsolete BaseItem position. Orientation or
open/close at the same coordinate emits `SPATIAL_OBJECT_CHANGED`, not a false
movement or anchor relocation.

### 8.4 Queries

The public query surface includes:

- `get_object_placement(uuid)`;
- `get_objects_at(position)`;
- `get_center_objects_at(position, *, height=None)`;
- `get_boundary_objects_at(position, direction, *, height=None)`;
- `get_world_edge(source, destination)` for one ordered transition view; and
- a full placement iterator used by snapshots and validation.

Queries return copies or frozen values. Gameplay callers do not inspect the
private Tile dictionaries. The preliminary flattened
`get_boundary_objects_on_edge(first, second)` helper is deleted after callers
move to exact side membership or the ordered view; an unordered UUID union is
not a final mechanical or rendering contract.

### 8.5 Rebuild validation

Serialized `WorldObjectPlacement` values are the load authority. Load validates
each value and builds Tile bands and `_object_placements` together. Diagnostics
then scan forward bands against those placements to prove the bijection; they
do not attempt to recover orientation or other lost placement facts from band
membership alone. Validation rejects partial band coverage, multiple locations,
inconsistent occupancy, missing providers, provider-policy drift,
same-Tile/same-side occupying collisions, missing Tiles, and invalid heights.
Opposing sides on adjacent Tiles are not a collision. Validation never chooses
a winner or silently repairs authored ambiguity.

## 9. Ordered boundary-transition derivation and movement height

### 9.1 Adjacency identity and ordered view

`AdjacentEdgeKey` is the canonical unordered identity of two cardinally
adjacent Tiles. It exists only for deduplication, invalidation, and diagnostic
identity. It is not an object slot and owns no structure.

`GridMap.get_world_edge(source, destination)` derives an ordered frozen
`WorldEdgeView` for the requested transition. The view contains:

- exact source and destination Tile facts;
- the source-facing exit direction and the destination-facing entry direction;
- `exit_contributions`, read only from the source Tile's facing side; and
- `entry_contributions`, read only from the destination Tile's opposing side.

The hot internal shape is conceptually:

```python
@dataclass(frozen=True, slots=True)
class WorldEdgeStructuralContribution:
    provider_uuid: UUID
    base_height_steps: int
    top_height_steps: int
    blocked_channels: tuple[WorldEdgeChannel, ...]


@dataclass(frozen=True, slots=True)
class WorldEdgeView:
    key: AdjacentEdgeKey
    source_position: tuple[int, int]
    destination_position: tuple[int, int]
    source_tile_uuid: UUID
    destination_tile_uuid: UUID
    source_height_steps: int
    destination_height_steps: int
    elevation_delta_steps: int  # destination - source
    source_surface_kind: ElevationSurfaceKind
    destination_surface_kind: ElevationSurfaceKind
    source_slope_axis: SlopeAxis | None
    destination_slope_axis: SlopeAxis | None
    exit_direction: CardinalDirection
    entry_direction: CardinalDirection
    exit_contributions: tuple[WorldEdgeStructuralContribution, ...]
    entry_contributions: tuple[WorldEdgeStructuralContribution, ...]
```

The reverse query shares the same `AdjacentEdgeKey` but swaps source and
destination facts and swaps the two contribution layers. The two views are not
equal and are never flattened into one unordered contribution tuple.

The adjacency key, ordered view, and its contributions remain internal frozen
derived values. This migration adds no persisted, event, or API copy of them;
placements plus object mechanics are the replay authority. Any future public
transport representation is a separately scoped contract, not a reason to
duplicate the internal view now.

Each structural contribution contains:

- provider UUID;
- base and top height steps from placement; and
- current blocked channels.

Kind, material, item state, and placement remain resolvable from their existing
authorities and are not copied into every hot edge query.

Contribution order is deterministic within each layer. A provider appears in
the layer owned by its placement Tile and side only. Two opposing walls are two
different providers in two different layers, even when their vertical bands
overlap. A placed open door remains present as a contribution with an empty
blocked-channel tuple so identity, placement, contacts, rendering, and replay
do not disappear merely because it currently transmits all channels.

### 9.2 Channel evaluation

Objective transition topology always includes every provider in both ordered
layers, even when an observer does not perceive it. A hidden wall does not
cease blocking sight, light, propagation, or movement.

For a transition `I -> J`, a channel is allowed only when both layers allow it:

1. the exit side `I:facing(J)` must transmit the channel; and
2. the entry side `J:facing(I)` must transmit the channel.

Any relevant blocker in either layer blocks that channel. Reverse traversal
evaluates `J`'s exit layer first and `I`'s entry layer second. Current wall,
door, and cliff channel policies remain physically symmetric, so passability
may be symmetric even though the derived view and observation route are
ordered. A future one-way mechanic requires an explicit authored contract; it
is not inferred from side or orientation.

For example, a wall on `I:EAST` and a wall on `J:WEST` both remain placed and
renderable. `I -> J` encounters the first wall and then the second; `J -> I`
encounters them in the reverse order. Removing or opening only one wall does
not make the transition passable while the other still blocks the channel.

- Walking support transitions use Tile elevation/progressive-surface rules and
  movement contributions from both ordered layers that intersect the traversed
  support interval
  `[min(source_height, destination_height), max(source_height, destination_height) + 1)`.
- Flying retains the engine's current 2D movement policy until actor altitude
  exists; authored movement barriers remain authoritative.
- Optical queries require both layers to transmit `OPTICAL`, without vertical-
  ray intersection. Ordinary sight and light use this same result.
- Propagation queries require both layers to transmit `PROPAGATION`, without
  vertical-ray intersection.

A height difference is not automatically a cliff object. An ordinary unequal
support transition can block walking while still having no rendered cliff. An
authored cliff provides the semantic structure and vertical extent. A ladder,
rope, lift, portal, or other discrete traversal remains a connector.

When a caller needs a blocking provider rather than only a boolean answer, the
deterministic search order is exit layer first, then entry layer, with UUID
order inside each layer.

### 9.3 Ordered boundary observability

From source Tile `I` toward adjacent Tile `J`, subjective reduction evaluates
the same physical order as the objective transition:

1. expose the objects in `I`'s exit-side layer to the shared contact resolver;
2. if that layer blocks the relevant route, stop there;
3. otherwise expose the objects in `J`'s entry-side layer;
4. if that layer blocks the route, stop there; and
5. only when both layers transmit optics may the far Tile and its center
   contents become visually reachable.

`SpatialSensesSystem` therefore asks GridMap for boundary objects exposed to
each visible cell. Its shared contact resolver evaluates the object's raw
`stealth_dc`/`is_invisible` facts together with the observer's exact sense
modes, ranges, route, and visual state. A boundary object does not own another
subjective perceivability hook. Temporary route evidence accumulates every
reached layer in order, through and including the first blocking layer, and
resolves each reached provider once into the existing typed contact map. Thus a
transparent exit-layer door and an opaque entry-layer wall can both be
contacted; an opaque exit layer prevents the entry layer from being reached.
No stopped route adds the far Tile to `Senses.visible`.

All objects sharing one side volume are treated as one co-visible layer:
attachments do not disappear merely because an occupying structure shares
their band, and no unmodelled depth ordering is invented. Nonvisual senses use
the analogous ordered propagation route. Candidate resolution reads the
canonical GridMap `WorldObjectPlacement`, but `PerceivedContact` remains the
existing exact `position`/`visual`/`special_senses` value. Authorized clients
correlate its provider UUID with the canonical object and placement facts
rather than receiving copied placement fields in a second contact schema.
Outer boundaries have only their one live Tile-owned layer; no synthetic
neighboring Tile or mirrored side is created.

## 10. Entity occupancy and movement

### 10.1 Single objective coordinate

Remove:

- `Entity._entity_by_position`;
- `GridMap._entity_positions`; and
- `GridMap._entities_by_position`.

Entity retains its objective `position`. Tile gains the inverse `entity_uuids`
membership. `Entity.get_all_entities_at_position` migrates to a Tile/GridMap
query that resolves UUIDs through the Entity registry.

GridMap's occupancy mutation primitives are internal and callable only through
Entity attach, detach, move, suspend, and restore. Entity leads the transaction:
it validates the strict destination through GridMap, snapshots its objective
coordinate, updates its own objective position with its Entity-only setter, and
asks GridMap to replace old/new Tile membership. If membership commit fails,
Entity restores its coordinate and GridMap restores the prior membership before
any spatial fact is published.

GridMap never calls inherited `BaseBlock.set_position`, which would recursively
write child blocks including Senses. It needs no actor marker or Entity import;
its private occupancy primitive accepts only the Entity-owned call path and
validates Tile identity, exact coordinates, expected old membership, and UUID
uniqueness. The primitive is private and non-exported. Public-behavior tests
prove that Tile Entity membership changes only through Entity
attach/move/detach/suspend/restore commands and that arbitrary BaseBlock UUIDs
cannot enter through a public command.

### 10.2 Game and Entity lifecycle

Game owns which committed Entities belong to the one in-process game. Entity
owns these world commands:

- attach/deploy;
- move;
- detach/undeploy;
- suspend spatial presence while preserving Game ownership; and
- restore suspended spatial presence to an admitted coordinate.

Suspension is the generic capability required by banishment-like mechanics. It
removes Tile membership, observer registration/subscriptions, and objective
spatial presence without deleting Game ownership or the Entity. Restore uses
ordinary placement admission and publishes the ordinary entry fact. Specific
conditions keep their own duration and destination-choice rules.

### 10.3 Per-step settlement contract

Every settled movement step remains an objective event boundary. It is not
collapsed into an end-of-path refresh.

For one step:

1. the movement family's established precommit event phases admit or veto the
   proposed ordered source-to-destination transition before objective mutation;
   ordinary path steps enter this
   boundary at `StepMovementEvent` EFFECT after their earlier admission work,
   while connector/direct-arc movement retains its existing
   DECLARATION-to-EFFECT sequence;
2. the accepted step commits Entity objective position and old/new Tile
   membership;
3. the post-commit LEFT lifecycle publishes departure, and a LEFT carrying its
   destination does not manufacture an intermediate subjective projection;
4. the post-commit ENTERED lifecycle runs entry/zone spatial EFFECT handlers,
   which use `Entity.position` or exact event coordinates;
5. at ENTERED pre-completion, the existing carried-light callback settles and
   publishes nested light facts before indexed sensory systems;
6. those light children and then the outer ENTERED event cause
   `SpatialSensesSystem` to reduce the complete objective result and emit only
   real `SensoryUpdateEvent` deltas;
7. ENTERED completes; and
8. the accepted `StepMovementEvent` completes with `committed=True`, its causal
   children, and event-time evidence.

This ordering preserves dynamic FOV, illumination, perceived contacts, and
navigation invalidation at every movement step. EFFECT mechanics always use
objective Entity/event coordinates. `Senses.position` remains the subjective
before-state until the relevant spatial event reaches its pre-completion
reducer boundary; a synchronously completed nested displacement may therefore
advance Senses before its outer EFFECT handler returns.

### 10.4 Turn start

Turn start remains an indexed event handled by `SpatialSensesSystem`:

1. only the turn actor is selected;
2. perception recomputes before `TurnStartEvent` completion;
3. a real delta is a causal `SensoryUpdateEvent` child with reason
   `TURN_START`;
4. an unchanged projection emits no sensory event; and
5. unchanged visual/contact state does not dirty navigation merely because a
   turn began.

Encounter may request navigation materialization for gameplay, but it does not
own or perform perception refresh.

## 11. Spatial-condition integration

The recovered spatial architecture is a prerequisite and remains intact:

```text
SpatialCondition
  owns identity, anchor, footprint, layer, active mechanics,
  observer-relative optical obscurement, optional physical optical
  obstruction, objective light contribution,
  handlers, memberships, linked condition children, and transitions

GridMap
  owns condition UUID -> owner/positions/layer indexes

Tile
  stores UUID references by spatial layer

EventQueue
  dispatches anchor and occupant reactions at EFFECT

SpatialSensesSystem
  reduces the settled objective result at pre-completion
```

Placement bands do not copy conditions. Ordered WorldEdge views do not copy
conditions.
GridMap asks the Tile-indexed condition owners for movement hazards, optical
obscurement, and objective light contributions at the queried position.

Condition optics have two explicit meanings. `optical_obscurement` remains an
observer-relative rule interpreted by `SpatialSensesSystem`. A condition which
physically prevents ordinary optical transmission exposes the neutral
`BaseCondition.blocks_physical_optics_at(position)` capability; the default is
`False`, and an active SpatialCondition answers `True` only for its indexed
footprint when its authored mechanics require it. GridMap queries that
capability without importing a concrete condition class. The condition remains
the source owner: its footprint lifecycle invalidates physical FOV and affected
light geometry, and no Tile/object mirror is created.

World-object anchor handlers consume exact placement events:

- placement creates or relocates the anchored footprint;
- a relocation departure retains the anchor until the destination placement
  fact arrives;
- orientation or door-state-only change at the same XY does not relocate it;
- terminal removal deactivates or detaches it through its existing condition
  lifecycle; and
- no handler reads inherited BaseItem floor position.

Entity anchors consume objective entity spatial facts with this transition
contract:

| Entity transition | Anchored SpatialCondition behavior |
|---|---|
| LEFT with a destination during movement | retain the current condition and wait for ENTERED; do not emit an empty intermediate footprint |
| ENTERED after move/deploy/restore | relocate or restore the footprint at the committed Entity position |
| LEFT without a destination during suspend/detach | transition the footprint to empty while retaining condition identity, handlers, duration, and links |
| explicit condition/concentration/anchor destruction | deactivate through the existing BaseCondition lifecycle |

This requires the existing anchor handler to observe the relevant LEFT and
ENTERED facts; it does not require Entity to import SpatialCondition. Dropping
concentration continues removing the linked condition through the existing
BaseCondition lifecycle.

Spatial-condition footprint and light work remain proportional to affected
positions. This placement migration does not introduce a controller registry,
anchor receipt hierarchy, or second transition system.

## 12. Optics, illumination, propagation, and subjective reduction

### 12.1 Objective topology

GridMap answers:

- center-cell movement/optical/propagation blocking;
- ordered cardinal movement/optical/propagation transitions, evaluating the
  source exit side and destination entry side independently;
- support-height walking transitions; and
- boundary objects exposed to an adjacent cell.

Materials are semantic inputs but do not silently select channels. A material
or layer change affects topology only when the committed Tile/object mechanics
also change.

### 12.2 Cache families

The placement cut preserves four distinct concerns:

| Concern | Invalidation source | Settlement |
|---|---|---|
| Movement topology | cell costs, occupancy, either ordered movement side, elevation/connector changes | path caches |
| Physical optical topology | intrinsic optics and either ordered optical side | FOV cache and affected light geometry |
| Physical propagation | intrinsic propagation and either ordered propagation side | propagation caches and nonvisual candidate reach |
| Objective illumination | base light, source footprint, caps, carried lights | Tile resolved light and observer deltas |

Optical and propagation cache invalidation stays global and lazy. It does not
eagerly recompute every observer. A local optical mutation radius-filters the
existing active light sources, diffs their prior `affected_tiles`, updates only
changed Tile illumination, and then selects observers from existing spatial
subscriptions/reverse indexes.

Revision settlement compares the derived transition result before and after
the mutation. If removing one side object leaves the other side blocking the
same channel, physical FOV/light/path topology has not changed and that channel
revision does not advance. The placement/state lifecycle and subjective contact
hint still select the live incident endpoint cells, because any reached object
layer may have changed even when aggregate transmission did not.

No placement, light, spatial-condition, or observer mutation scans every Tile.
A small side-object change mutates only its owner Tile bands and reverse row.
It selects the owner Tile and the adjacent live Tile when applicable for
transition invalidation, relevant active lights, and indexed observer
candidates; it never writes a mirror band on that neighbor.

Fog, magical darkness, and other `SpatialCondition.optical_obscurement`
changes are observer-relative inputs. They select observers from the condition
footprint and rerun subjective reduction, but do not invalidate physical FOV or
recompute ordinary light transport. A rule which truly changes physical
optical topology commits either an explicit Tile/object `OPTICAL` change or an
explicit condition-owned physical-optics footprint change through the ordinary
topology boundary.

### 12.3 Event order for optical changes

For an object or Tile mutation affecting physical optics:

1. objective placement/topology commits;
2. optical revision and query caches invalidate;
3. the existing spatial lifecycle begins with complete after-values;
4. existing light-topology handling recomputes affected active light sources
   and publishes causal light children;
5. spatial EFFECT handlers settle objective mechanics; and
6. `SpatialSensesSystem` observes the complete objective result before parent
   completion.

When a SpatialCondition activation, footprint transition, or movement changes
objective illumination, that condition publishes its light facts synchronously
immediately after its own footprint/index/light commit and before sensory
reduction. There is no after-all-handlers light barrier or new callback stage.

Illumination-only changes do not invalidate physical optical geometry.
Propagation-only changes do not invalidate ordinary FOV or light geometry.

### 12.4 Subjective navigation

Objective topology always includes every blocker in both ordered side layers.
Subjective path discovery may omit a blocking entity/object which the observer
does not know, according
to the existing collision-memory rules. It reads typed `PerceivedContact`
maps; it does not call a range-free perceivability hook and does not alter the
objective transition.

## 13. Event and replay contract

### 13.1 Existing machinery remains authoritative

The current Event/EventQueue lifecycle, phase handlers, indexed spatial
handlers, pre-completion callbacks, pre-completion systems, child lineage, and
combat-log projection remain the event machinery. This migration adds exact
domain payloads and updates their consumers. It does not add another publisher,
event index, completion transaction, controller protocol, callback isolation
framework, or child-fold.

Events remain mutable reaction context until completion. Completed events are
cold facts. `SensesUpdateHint` selects efficient work but is not replay state.
Replay correctness comes from complete event payloads.

### 13.2 Placement facts

`SpatialChangeEvent` gains exact optional placement fields:

```python
placement: WorldObjectPlacement | None
previous_placement: WorldObjectPlacement | None
```

Their meaning is uniform:

| Operation | `previous_placement` | `placement` |
|---|---|---|
| initial placement | `None` | committed placement |
| relocation departure | old placement | `None`; `SpatialChangeEvent.old_position` is the intended destination |
| relocation arrival | old placement | committed new placement |
| orientation/state change | old placement | committed placement |
| terminal removal | old placement | `None` |

Object facts also carry final movement/optical/propagation mechanics needed by
the existing reducers. They stop carrying `object_map_char`, sprite names, or
other renderer/debug bindings. Boundary kind/material remains in the item's
semantic state and placement side/height/orientation remains in placement.
No event carries a flattened adjacency occupant list: two opposing structures
are two ordinary object facts with two exact Tile-side placements.

The existing Tile-change fact gains one exact optional after-value:

```python
tile_surface: TileSurface | None
```

A committed runtime surface replacement carries the complete new
`TileSurface`. The reducer replaces that value directly; it does not infer a
surface from materials, conditions, renderer metadata, or a partial patch.

`ItemLocationStateEvent` uses `world_placement` when location is FLOOR. It does
not retain separate floor `tile_uuid` and `position` fields. Inventory,
equipment, merged, and destroyed locations preserve their established domain
fields and event order.

### 13.3 Entity facts

Existing LEFT and ENTERED events carry objective coordinates and Entity UUID.
They do not carry or mutate Senses. Movement event-time observer evidence keeps
the established pre-mutation origin and committed destination semantics.

### 13.4 World initialization

Successful cold map construction publishes one deterministic
`WorldInitializedEvent`; failed construction publishes none. Bootstrap builds
final state directly rather than pretending runtime actions occurred. It uses
the existing GridMap-disabled build boundary and does not introduce a global
EventQueue mute.

The initialization fact contains:

- exact bounds;
- every Tile UUID and coordinate;
- `TileSurface` base material and ordered layers;
- movement costs;
- intrinsic optics and propagation;
- support height, progressive-surface kind, and slope;
- base and resolved objective light;
- every exact world-object placement plus semantic item state and contained
  item state;
- complete existing objective state for any direct Tile condition,
  SpatialCondition, or light source that belongs to the cold map; and
- every traversal connector.

Cold `WorldInitializedEvent` contains no deployed actors. Entity creation and
deployment follow it through their established objective lifecycles; observer
registration and the resulting ENTERED event then produce exactly one initial
empty-to-full sensory delta for each deployed observer.

Every direct Tile BaseCondition, independently owned SpatialCondition, and
light source authored as part of the cold map is represented by complete
initialization state. If a family does not yet have a complete cold snapshot,
it is created only after initialization through its ordinary objective
lifecycle. The implementation ledger classifies every authored case before
build-time publication is disabled. Objective state never exists outside
replay history.

### 13.5 Reducer guarantees

Objective replay can reconstruct Tile surfaces, support facts, resolved light,
independent Tile-side object placements, object mechanics, and connectors.
Ordered WorldEdge views are derived from that replayed state and are never a
second serialized authority. Subjective replay applies
recorded `SensoryUpdateEvent` deltas to reproduce visible cells, explored
cells, typed contacts, effective observer light, sense modes, passive
perception, and visual access. Navigation caches remain derived and are
recomputed from objective world state plus observer knowledge.

## 14. Content and client boundary

Authored map content chooses semantic facts and calls ordinary engine builders:

- Tile surface and intrinsic cell mechanics;
- support height and progressive-surface facts;
- concrete world objects and their placement;
- object mechanical state;
- spatial conditions and light sources; and
- traversal connectors.

Content is not a runtime registry, state gateway, package system, or alternate
event source. A declarative map definition may be Pydantic data plus a direct
sequence of construction functions. Procedural generation uses the same
commands.

Current multi-direction wall declarations migrate mechanically to one concrete
boundary object per authored side. Existing one-to-one semantic choices are
preserved in a migration ledger before the old declarations are removed.

The backend may say that a structure is a stone wall, a surface is earth with
grass, or an object is a red flaming sword. It never selects a sprite, tileset
coordinate, VFX name, pixel offset, painter layer, or renderer rotation. A
client binds stable semantic content and exact placement to its own assets.

## 15. Migration sequence

Each phase is a reviewable hard cut. A phase captures its exact caller/test
ledger before edits, lands one coherent ownership boundary, validates behavior,
and deletes the replaced authority before proceeding.

### Phase 0 — Freeze the live contract

1. Record the collecting runnable test set and blocked-module failure
   signatures at implementation start.
2. Inventory all Tile constructors, rectangle builders, map factories, direct
   surface/height/border writes, object placements, entity-position mutations,
   item floor-location readers, world snapshots, and frontend fields.
3. Inventory every wall, door, cliff-like structure, center blocker,
   attachment, light-owning object, object-anchored SpatialCondition, and
   multi-direction authored declaration.
4. Record event order for per-step movement, carried light, object anchors,
   optical topology changes, spatial-condition light changes, sensory deltas,
   turn start, and world initialization.
5. Preserve currently blocked capabilities in a separate migration ledger;
   do not weaken collecting tests to accommodate moved modules.

### Phase 1 — Land cold surface and placement values

1. Add `Material`, `SurfaceLayer`, `TileSurface`, placement values, and boundary
   semantic values in dependency-leaf type modules.
2. Make every Tile constructor, rectangle builder, factory, and authored map
   definition supply an explicit surface in the same phase that the field
   becomes required.
3. Convert persisted/event boundary values to Pydantic with strict integer
   validation; retain hot internal dataclasses where appropriate.
4. Add dependency and schema gates before runtime migration.

### Phase 2 — Make Tile and GridMap the placement authorities

1. Add private Tile center/boundary band storage.
2. Add the sole GridMap reverse placement dictionary and command/query family.
3. Implement local center/same-Tile-side admission, mutation, rebuild
   validation, and exact placement events. Opposing sides of adjacent Tiles are
   independent and never collide during admission.
4. Port ordinary flat objects and every object-location consumer: BaseItem
   floor workflows, item-location facts, wall-mounted lights, object-anchored
   SpatialConditions, perceivability/evidence publication, snapshots, and
   authored callers. Preserve each established item/condition/light lifecycle.
5. In this same atomic cut, remove the flat object-position stores, BaseItem or
   BaseBlock floor-position authority, old FLOOR event coordinates, and direct
   Tile band access. No dual-write interval is permitted.

### Phase 3 — Migrate structures and ordered transitions

1. Port walls, doors, cliffs, attachments, and center blockers to explicit
   placement specifications and semantic state.
2. Port every authored directional declaration and preserve its semantic
   crosswalk, then expand it into one object per boundary.
3. Derive ordered world-transition views directly from the source exit-side and
   destination entry-side bands. The reverse query swaps the two layers while
   retaining the same canonical adjacency key.
4. Migrate movement, FOV, light geometry, propagation, and exposed-boundary
   queries to require transmission through both ordered layers.
5. Delete intrinsic/object-derived directional booleans and their authored
   inputs only after every declaration has moved, then recompute caches.
6. Prove shared XY optics, ordered near-side/entry-side observability,
   propagation independence, legal opposing structures, and movement-only
   height semantics.

### Phase 4 — Migrate Entity occupancy

1. Add private Tile forward Entity membership and internal GridMap occupancy
   helpers.
2. Route Game deployment and Entity move/detach through Entity-owned commands.
3. Add the minimal suspend/restore world-presence boundary.
4. Delete the Entity class position index and both GridMap entity-position
   dictionaries.
5. Port collision, targeting, pathfinding, runtime reset, and tests to Tile/
   GridMap queries.
6. Preserve objective-before-subjective movement order, per-step light/FOV
   settlement, and reducer-owned Senses.

### Phase 5 — Migrate authored maps and bootstrap

1. Emit the complete deterministic `WorldInitializedEvent` from final state.
2. Classify every bootstrap-created direct Tile condition, SpatialCondition,
   and light source so its objective state is represented exactly once.
3. Deploy Entities only after initialization through the ordinary creation and
   spatial lifecycles.
4. Validate content-built path, optics, light, propagation, condition, object,
   and connector behavior.

### Phase 6 — Certify the hard cuts

1. Require zero remaining imports/calls of every symbol deleted in its owning
   phase.
2. Prove there is no remaining duplicate placement, floor-location,
   directional, or Entity-position authority.
3. Run full collecting tests, compare blocked-module signatures, validate
   replay, and record the final caller ledger.

## 16. Verification gates

### 16.1 Surface and Tile

- base material and ordered layers serialize deterministically;
- surface replacement preserves Tile identity, occupants, conditions, and
  illumination;
- temporary wet/burning/fog/darkness remains condition-owned;
- Tile replacement/removal cannot orphan any live owner;
- support mutation preserves XY condition indexes and invalidates movement
  results correctly; and
- no frontend asset identifier enters Tile or surface contracts.

### 16.2 Placement and edges

- center and each boundary side admit correct z-band membership;
- nonoccupying attachments coexist with one occupying structure;
- center and same-Tile/same-side boundary collisions reject before mutation;
- occupying objects on adjacent opposing sides coexist at the same heights and
  retain distinct placement, identity, and rendering facts;
- reverse placement and every forward band remain bijectively coherent;
- move, orient, state change, removal, clear, and rebuild preserve invariants;
- one wall object occupies one authored boundary;
- cliffs and walls at different bands serialize distinctly;
- only movement uses height intersection;
- a forward WorldEdge view reads source-exit then destination-entry layers, and
  its reverse swaps them without merging provider identity;
- walking, optics/light, and propagation each require both ordered side layers
  to allow their channel;
- objective optical/propagation topology never omits an unseen provider;
- an exit-layer blocker hides the entry layer and far Tile, while a transmitting
  exit layer exposes an entry-layer blocker without revealing the far Tile or
  contents;
- transparent exit plus opaque entry produces contacts for both reached layers,
  opaque exit hides the entry provider, and reverse observation swaps the
  ordered route;
- with occupying blockers on both opposing sides, opening/removing only one
  preserves the still-blocked movement/optical/propagation results and their
  revisions and performs no affected-light topology recomputation, while the
  existing object lifecycle/hint settles endpoint-indexed contact deltas from
  the exit layer to the newly reached entry layer; and
- replaying the two exact placements and object states derives the same forward
  and reverse ordered views without a serialized edge fact.

### 16.3 Spatial conditions and illumination

- Tile condition references and GridMap footprint indexes survive unrelated
  placement mutations;
- object and Entity anchors relocate through exact spatial events;
- orientation/open-state changes at the same XY do not move an anchor;
- true removal retires the anchored condition through its established
  lifecycle;
- concentration removal still removes the linked SpatialCondition;
- optical-condition and light contributions settle before sensory reduction;
- local condition work scales with affected footprint; and
- wall-mounted and carried lights have one position authority each.

### 16.4 Entity and turn lifecycle

- deployed Entity position and Tile membership always agree;
- suspended/undeployed Entities occupy no Tile;
- rejected movement changes no Entity, Tile, cache, or event state;
- every movement step updates objective position, lights, FOV, typed contacts,
  and sensory deltas before completion;
- EFFECT mechanics observe objective position while Senses remains the prior
  projection;
- TURN_START recomputes only its actor, emits a causal delta only when changed,
  and does not dirty clean navigation; and
- Encounter never becomes a perception owner.

### 16.5 Events, bootstrap, and replay

- placement facts contain exact before/after placement without renderer data;
- runtime surface facts contain the complete committed `TileSurface` after-value;
- item FLOOR facts contain the exact placement and no duplicate coordinates;
- `SensesUpdateHint` omission cannot change replay results;
- objective and sensory replay reproduce the defined world/projection state;
- event-time location and identity evidence remains correct across movement;
- successful bootstrap produces one actor-free complete initialization fact,
  followed by ordinary Entity deployment and exactly one initial sensory delta
  per deployed observer, with no unrepresented objective state;
- failed bootstrap records no initialized world; and
- completed events remain immutable cold facts.

### 16.6 Locality and performance

- placement and removal touch only covered bands and the reverse entry;
- position queries inspect one Tile or one ordered adjacent transition, not the
  whole map;
- optical/propagation invalidation is lazy and does not eagerly recompute every
  observer;
- light recomputation scales with active relevant sources plus footprint deltas,
  not map area;
- observer recomputation scales with indexed candidates;
- spatial-condition work scales with footprint; and
- fixed-radius timing/counter tests compare small and large maps without using
  wall-clock thresholds as their only assertion.

### 16.7 Architecture

- dependency arrows in Section 4 hold under AST/import inspection;
- core/events imports no GridMap, Entity, Senses, authored `dnd/content`, or
  renderer module;
- GridMap imports no concrete items, Entity, or concrete SpatialConditions;
- Entity and BaseItem import no `dnd.spatial` module;
- persisted/event contracts are Pydantic and hot internal views remain simple;
- no late imports, cycle masks, reflection contracts, parallel registries,
  compatibility facade, or custom serialization is introduced; and
- tests assert public behavior and replay, not private source layout.

## 17. Current authority migration ledger

This table identifies families of live authority to replace. Phase 0 expands
each row into exact callers for the implementation revision.

| Current family | Destination |
|---|---|
| Tile authored/object-derived cardinal booleans | real Tile-side placements and ordered derived WorldEdgeView |
| GridMap flat object position dictionaries | Tile forward bands plus one reverse placement dictionary |
| BaseItem `tile_uuid` and floor `position` | GridMap placement query |
| multi-direction walls/doors | one concrete object per boundary |
| duplicate door families | one usable boundary-door implementation |
| wall-torch private position | GridMap placement plus its existing light UUID |
| item/world events with map glyphs or sprite fields | semantic item state plus exact placement |
| `Entity._entity_by_position` | Tile Entity UUID membership |
| GridMap entity position dictionaries | Entity.position plus Tile inverse membership |
| direct private-index Banishment writes | Entity suspend/restore world commands |
| object anchors reading BaseItem position | exact placement spatial events |
| subjective edge filtering through perceivability hooks | ordered objective side layers plus typed-contact subjective navigation |
| renderer-facing Tile/item fields | client-side semantic-to-asset binding |

Inventory/equipment domain behavior, EventQueue internals, action/condition
definitions, encounter decisions, server/API transport, and content packaging
are not redefined by this plan. Only active in-process Python floor/world
callers migrate to the new authority while preserving their established
lifecycle. Deprecated/server/SDK/generated transport callers are excluded by
Section 1.1 and may not expand a phase's mutation or validation envelope.

## 18. Completion definition

The migration is complete when:

1. one Tile per XY owns semantic surface composition, condition references,
   Entity membership, and center/boundary object bands;
2. GridMap is the sole writer of Tile spatial membership and the sole owner of
   reverse object placement;
3. Entity.position and Tile membership are the only objective actor-position
   authorities;
4. Senses is changed only by `SpatialSensesSystem` or sensory-event replay;
5. walls, doors, cliffs, fixtures, and blockers are real placed objects with
   exact semantic state and placement;
6. movement, optical, and propagation topology derive from both ordered
   Tile-owned side layers, with height participating only in placement and
   movement;
7. ordinary sight and light share objective optical topology while objective
   illumination remains Tile-owned;
8. SpatialConditions retain their recovered ownership, indexes, reactions,
   concentration links, optics, and light contributions;
9. every movement step and turn-start boundary preserves the accepted
   objective-to-subjective event order;
10. world initialization and subsequent events provide a complete replay
    boundary without renderer identifiers;
11. old directional fields, flat indexes, duplicate floor/entity positions,
    duplicate door types, and compatibility paths are gone;
12. content and procedural generation use the same direct world commands; and
13. behavior, replay, dependency, and locality gates all pass on the frozen
    active in-process test surface; deprecated/server/SDK collection is not a
    completion gate.

## 19. Review record

The prior approval record applied to a superseded revision and is intentionally
retired. This section records only reviews of the current target architecture.

| Review | Focus | Status |
|---|---|---|
| Ordered geometry and executability | independent side ownership, transition ordering, replay, phase cuts | APPROVED on substantive SHA `46de9f57...` |
| Optics/light/event consistency | unified topology, contacts, cache settlement, replay | APPROVED on substantive SHA `46de9f57...` |
| Anti-slop review | duplicate layers, speculative machinery, compatibility surfaces, genericity | APPROVED on substantive SHA `46de9f57...` |
| Active-runtime scope amendment | in-process Python/Pygame boundary; deprecated transport exclusion | APPROVED on master SHA `abe1a01d...` |
