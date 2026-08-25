# Tile / World-Item Phase 3 — Practical Implementation Guidance

Status: REVOKED — DO NOT IMPLEMENT

This guidance assumed that adjacent opposing Tile sides were one shared
physical edge slot. The corrected master plan instead defines two independent
Tile-owned side volumes and ordered exit-side/entry-side transitions. This file
is retained only as superseded review history and must be replaced after the
Phase 0-2 geometry correction is accepted. Governing master file SHA-256:
`73335294139bdc81306f17381afe22f27fb94c9c48bcf07c1312eb9eeefafe63`;
substantive corrected master SHA-256:
`46de9f570fb59fd8c9e8a105a3a699287a7881c93c880827d804faefad9c7f2d`.

Substantive approved revision:
`7ad7ec686f6c9e41ac6a8af5ce8cb0c83be97ff966601a933d5064c3a52fe097`.

Implementer: Luna. Reviewers are independent from the implementer.

This document refines only Phase 3 of
`DND_TILE_WORLD_ITEM_VERTICAL_BOUNDARY_MIGRATION_PLAN_2026-08-17.md`.
It does not authorize Phase 4 Entity occupancy, Phase 5 bootstrap redesign, an
EventQueue rewrite, or a new frontend projection system.

## 1. Frozen inputs and scope

Before editing, verify these exact inputs:

| Input | Required SHA-256 |
|---|---|
| Approved master plan | `01b0d5aa27b7617666d85da3e167da9d4b59d21b95f5073b41eb25821bdcde77` |
| Approved unified optics plan | `3c9c58483440640837bc38fdaa6b624f358e1098c9a957f65923cd64f83a270b` |
| Approved Phase 0/1/2 implementation plan | `8cedc4e437d1a5c3bd1c02e4db6fbfbcc04fefe7768f44c97671837bcf0adeb2` |
| Accepted Phase 0/1/2 implementation manifest | `34de6db66c80d336044ab90abd13e284971722551d4d2018678a12808971aad9` |

Read `AGENTS.md` and all of `HOW_TO_TEST.MD` before writing or running tests.
Freeze a fresh pre-edit test/collection ledger using the Phase 0/1/2 method.
The accepted Phase 0/1/2 behavior is the starting state, not work to redo.

### 1.1 Goal

At the end of Phase 3:

1. a wall, door, cliff, or attachment is an ordinary placed world object;
2. the object's placement supplies its cardinal boundary and vertical interval;
3. the object supplies one computed semantic/mechanical boundary snapshot;
4. an objective edge is derived on demand from the two facing Tile boundary
   stores;
5. movement, ordinary FOV, light-source geometry, and propagation consume that
   edge;
6. one physical optical topology is shared by ordinary vision and light;
7. subjective perception may reveal the boundary object from the near side
   without revealing the far Tile or its contents; and
8. the old Tile/BaseItem directional projection no longer exists.

### 1.2 Strict exclusions

Do not add:

- an edge registry, edge cache, edge entity, mirrored edge ownership, or
  materialized edge table;
- separate vision and light channels;
- ray height, eye height, actor altitude, voxel visibility, or other 3D optics;
- a new EventQueue publisher, event transaction, reducer framework, callback
  family, receipt hierarchy, controller layer, or compatibility facade;
- a range-free object `is_perceivable_by()` policy;
- content-ID switches, `getattr`, late imports, `TYPE_CHECKING` cycle masks, or
  concrete item/SpatialCondition imports in GridMap;
- Phase 4 Tile Entity membership or Entity index work; or
- renderer assets, sprites, map characters, or presentation identifiers in
  world values/events.

If an implementation choice would require one of these, stop and ask the
supervisor. Do not solve it locally.

## 2. Authority after the cut

| Fact | Sole authority | Derived consumers |
|---|---|---|
| Object boundary side and height | `GridMap._object_placements[uuid]` | edge derivation, serialization, events, rendering |
| Boundary band membership | private Tile boundary bands | local edge membership lookup |
| Structure kind/material/current channels | object's freshly computed `BoundaryStructure` | edge view, item/event state |
| Objective cardinal topology | on-demand `WorldEdgeView` | movement, FOV/light geometry, propagation |
| Center-cell mechanics | Tile intrinsic cell policy plus placed center objects/conditions | movement, optics, propagation |
| Subjective contacts | reducer-owned typed `Senses` contact maps | targeting, navigation knowledge, projection |
| Objective illumination | existing GridMap light-source/Tile contribution system | subjective light reduction |

`WorldEdgeView` is a frozen hot result. It is never stored as authority.

## 3. Exact target values and neutral capabilities

### 3.1 Reuse existing cold values

Reuse the existing Pydantic values in `dnd/types/world_placement.py`:

- `WorldPlacementSpec`;
- `WorldObjectPlacement`;
- `BoundaryStructureKind`; and
- `BoundaryStructure`.

Do not introduce a second structure value or placement policy.

`BoundaryStructure.blocked_channels` must be canonical: unique and ordered by
`WorldEdgeChannel` declaration order. Add ordinary Pydantic validation if the
live value does not already guarantee this. Do not add custom serialization.

### 3.2 Neutral object surface

GridMap continues to use only these neutral `BaseBlock` capabilities:

```python
def get_world_placement_spec(self) -> WorldPlacementSpec: ...
def get_boundary_structure(self) -> BoundaryStructure | None: ...
```

The default placement remains one nonoccupying center band. The default
boundary structure remains `None`.

There is one channel answer. A boundary provider returns a newly computed
`BoundaryStructure`; GridMap must not call a second channel method or retain a
copy. An open door returns the same kind/material and an empty channel tuple.

### 3.3 Edge contribution

Extend the existing frozen hot dataclass only:

```python
@dataclass(frozen=True, slots=True)
class WorldEdgeStructuralContribution:
    provider_uuid: UUID
    base_height_steps: int
    top_height_steps: int
    blocked_channels: tuple[WorldEdgeChannel, ...]
```

The height fields come from the committed placement. Kind/material remain on
the item semantic state and are not duplicated into the hot contribution.

## 4. Concrete object cut

### 4.1 Shared fixed-object base

Use `WorldItem(BaseItem)` only if it owns reused fixed placement-spec behavior.
Do not create semantic-only center/boundary subclasses. Usable boundary
fixtures remain direct `UsableItem` subclasses and override the same neutral
capabilities.

Placement shape is immutable while placed. A change of side, extent, or
occupancy is a GridMap remove/place operation. Door open/close is mechanical
state only and preserves placement.

Freeze these Phase 3 authored constants; Luna does not choose them:

| Family | Placement spec | Material | Default structural channels | Base rule |
|---|---|---|---|---|
| Standard wall | boundary, occupying, extent 2 | `STONE` | movement, optical, propagation | Tile support |
| Standard door | boundary, occupying, extent 2 | `WOOD` | closed: movement, optical, propagation; open: none | Tile support |
| Proving cliff face | boundary, occupying, extent 2 | `STONE` | movement only | explicit 0 |
| WallTorch | boundary, nonoccupying, extent 1 | no boundary structure | none | explicitly authored; maintained arena rows use 1 |
| Boulder/barricade/oil barrel | center, occupying, extent 1 | no boundary structure | preserve current center fields | Tile support |

The maintained eastern arena torches use boundary EAST, orientation WEST,
base 1, and top 2. These values are authored row data, never inferred from
coordinates. Other authored families require their own explicit constants
before construction.

Structure material and closed-channel policy are fixed authored fields for
these families. `is_open` is the door's only mutable structural input and may
change only through its existing open/close operation and GridMap settlement.

### 4.2 Wall

Keep the existing `DirectionalWall` concrete family/name unless a required
public contract proves a rename necessary. Change its semantics to:

- `WorldPlacementKind.BOUNDARY`;
- `occupies_bands=True`;
- an explicit fixed vertical extent;
- `BoundaryStructureKind.WALL`;
- explicit `Material`; and
- a closed/current channel tuple.

Delete `blocked_directions` and the twelve per-direction boolean fields. One
wall instance represents one boundary because its committed placement carries
one `boundary_direction`.

### 4.3 Door consolidation

Use the current mature boundary family as the surviving implementation:
`DirectionalDoor`, its existing directional action behavior IDs, and
`environment.directional_door` are canonical for this cut.

Make it one occupying boundary provider with explicit extent, material, closed
channels, and current `is_open`. Opening returns an empty current channel tuple;
closing restores the authored closed tuple. Placement and UUID do not change.

Migrate all active and blocked callers of `DoorObject`, `environment.door`,
`door_recipe`, `build_door`, `OpenDoorAction`, and `CloseDoorAction` to the
canonical family, then delete that duplicate class/content/action family and
its generated bindings. Do not leave an alias or a second content declaration
that constructs the same semantic door.

If removing either public content identity conflicts with external persisted
content not represented in this repository, stop for a product decision. Do
not silently preserve a compatibility identity.

### 4.4 Cliff

Add one concrete fixed boundary provider for authored cliff faces:

- `WorldPlacementKind.BOUNDARY`;
- `occupies_bands=True`;
- `BoundaryStructureKind.CLIFF`;
- explicit material, extent, base height, and channels.

The elevation proving battlefield must author the face on `(11, 5)`, WEST,
covering `[0, 2)` with `Material.STONE` and only the `MOVEMENT` channel. The
support-height delta remains independently authoritative:
walking still rejects an ordinary unsupported two-step transition when no
cliff object exists, and flying retains its current 2D movement policy.

Do not infer or auto-create a cliff from an elevation delta.

### 4.5 Wall attachment

`WallTorch` becomes a nonoccupying boundary object with an explicit extent.
Every mount, authored row, editor row, and save/load value supplies its side,
base, and orientation through the existing placement command family.

Keep the already accepted attached-light owner from Phase 2. Do not add a
second torch coordinate or a new light callback. A torch can share its exact
bands with an occupying wall. The standard arena torch side/orientation/height
comes from the constants table; do not infer side from `x == 14` at runtime.

### 4.6 Center blockers

Give boulder, barricade, and oil barrel explicit occupying center placement
specs. Preserve their current center mechanics. The current nonblocking crate
may remain nonoccupying unless a real authored rule says otherwise.

Do not discover this policy from semantic keys or concrete classes in GridMap.

## 5. Authored crosswalk

### 5.1 Hard rule

Every current `blocked_directions` declaration expands before that field is
deleted:

```text
legacy object at position P with directions (D1, D2, ...)
    -> one newly constructed object at P/boundary D1
    -> one newly constructed object at P/boundary D2
    -> ...
```

Each expanded object has a distinct UUID and one placement. Never place one
UUID on multiple sides. Preserve label, kind, material, channels, open state,
and content identity on every expanded row. Expansion order follows canonical
cardinal enum order so cold facts are deterministic.

`blocked_directions` is legacy placement authorship, not current door state.
An open door retains the same authored closed side while its current
`BoundaryStructure.blocked_channels` is empty. In particular, the maintained
open standard-hazards layout is WEST exactly like the closed layout; its
current empty `blocked_directions=()` row is corrected rather than expanded to
zero objects.

Before Slice 3.3, freeze a complete caller-level door-side ledger covering
every `DoorObject`, `environment.door`, `door_recipe`, `build_door`, and direct
placement. For each row record:

- file/caller and maintained behavior;
- exact owner Tile and `boundary_direction`;
- orientation when distinct;
- closed channels, material, extent, and initial open state; and
- the public test which proves the migrated route/action.

Where current geometry establishes an approach side, author that exact side in
the caller. Do not apply a repository-wide WEST default. A legacy center door
whose capability genuinely blocks several approaches must be re-authored as
multiple distinct boundary objects or escalated as a product decision; it may
not silently become one boundary. Slice 3.3 cannot begin while any no-side door
caller remains unclassified.

### 5.2 Cold battlefield definitions

Replace `BattlefieldObjectDefinition.blocked_directions` with exact placement
facts appropriate to one object:

- `boundary_direction`;
- optional explicit `base_height_steps` where it differs from support;
- optional `orientation`; and
- one object row per side.

Add `cliff` to the authored object kind set. Wall-torch rows must also carry a
boundary side. Center objects have no boundary direction.

The cold definition validates shape without importing concrete item classes.

### 5.3 Maintained runtime builders and recipes

Port, at minimum:

- `dnd/maps/arena_layout.py`;
- `dnd/content/scenarios/battlefield_definitions.py`;
- `dnd/content/scenarios/battlefield_builders.py`;
- `dnd/content/items/environment_item_builders.py`;
- `dnd/content/items/authored_item_builders.py`;
- `dnd/items/environment_content.py`;
- every direct wall/door/torch/cliff/blocker constructor; and
- every direct `place_on_grid()` or `mount()` call for a boundary object.

Builder APIs construct one object. They do not retain a plural direction
parameter. Layout expansion owns multiplicity.

### 5.4 Deprecated editor and projection callers

These files remain in the manifest and must compile against the cut even when
their modules are blocked by unrelated imports:

- `deprecated/server_deprecated/api_models.py`;
- `deprecated/server_deprecated/mapeditor_support.py`;
- `deprecated/server_deprecated/world_projection.py`;
- `deprecated/server_deprecated/player_replication/world_projection.py`; and
- `deprecated/server_deprecated/subjective_parity_diagnostics.py`.

Extend the existing editor placement/save row with the exact
`WorldObjectPlacement` shape or equivalent Pydantic fields. Remove Tile
directional patch/restore and duplicate-door branches. Subjective projections
read typed `Senses` contacts plus committed placements; they do not rebuild a
subjective edge or call object-owned perceivability.

Do not add AST/source-layout gameplay tests for blocked editor code. Preserve
its behavior-level tests for restoration of the deprecated stack, and use
compile/schema/deleted-symbol gates in this cut.

## 6. Objective edge derivation

### 6.1 One local query

`GridMap.get_world_edge(A, B)` must:

1. validate exact cardinal adjacency and live endpoint Tiles;
2. canonicalize `AdjacentEdgeKey`;
3. determine the facing side on A and the opposite facing side on B;
4. read only those two private boundary-band dictionaries;
5. union provider UUIDs without duplicates;
6. resolve each exact committed placement and neutral `BaseBlock`;
7. reject/diagnose any provider whose placement does not name this physical
   edge;
8. call `get_boundary_structure()` once per provider;
9. omit attachments whose result is `None`;
10. return sorted contributions with placement base/top and current channels;
    and
11. include the existing endpoint elevation/surface facts.

The result is reciprocal: `get_world_edge(A, B) == get_world_edge(B, A)`.
Provider order is deterministic by UUID string. Work is proportional to the
two facing used band stores and unique providers, not map area or all objects
at either endpoint.

`get_world_edge()` represents an internal edge and therefore requires two live
Tiles. An outer-boundary placement remains valid on its owner's outward band.
The exposed-boundary query inspects that owner band even though there is no
adjacent edge/Tile; it simply has one live incident endpoint. Missing space
outside the map retains the engine's existing transition/optics policy and is
not materialized as a synthetic Tile or edge.

### 6.2 Channel evaluation

Use exactly `MOVEMENT`, `OPTICAL`, and `PROPAGATION`.

- Ordinary optics: block when any contribution contains `OPTICAL`; ignore its
  height interval.
- Physical propagation: block when any contribution contains `PROPAGATION`;
  ignore its height interval.
- Walking movement: after the existing support/progressive-surface admission,
  block a `MOVEMENT` contribution only when its interval intersects the
  support traversal interval
  `[min(first_height, second_height), max(first_height, second_height) + 1)`.
- Flying, swimming, burrowing, and other current modes retain their present 2D
  authored-barrier behavior unless that mode already has a more specific
  established rule. Do not invent altitude.

This proves the required upper terrace case: a cliff face `[0, 2)` below two
height-2 supports does not block walking across the upper edge, while a wall
`[2, 4)` does. Both structures affect optics/propagation only according to
their authored channels, regardless of height.

### 6.3 No inferred semantics

Material and structure kind do not select channels inside GridMap. Elevation
does not create a cliff. An unseen provider remains in the objective edge.

## 7. Mechanical consumer hard cut

The following consumers move to derived edge queries before the old booleans
are deleted:

1. `_tile_allows_transition_side`, `can_transition`, diagonal bridge checks,
   voluntary movement, forced movement, paths, and collision reporting;
2. `can_optical_transition`, both ordinary FOV paths, line-of-sight, cover
   geometry, and light-source `compute_fov` geometry;
3. `can_propagate_transition`, propagation FOV, AoE filtering, sense
   propagation, and the propagation barrier fast path;
4. subjective navigation's known-blocker reduction; and
5. boundary-object exposure queries used by perception/projection.

### 7.1 Diagonal movement

Preserve the current diagonal policy. Its cardinal bridge legs call the same
derived cardinal edge query. Do not create diagonal edges or infer corner
walls.

### 7.2 Propagation fast path

Replace the no-argument global fast path with a bounded query such as
`get_barrier_positions(candidate_positions)`. It inspects only the supplied
geometric/candidate cells, their center propagation blockers, and their
incident derived edges. Adding the relevant endpoints of a
propagation-blocking edge is an acceleration only;
`can_propagate_transition()` remains the exact answer.

Port AoE objective/subjective/targeting and action-discovery callers to pass
the geometric footprint or already known bounded candidate set. Do not retain
the global barrier cache and do not materialize a global edge index merely to
keep the no-argument signature.

### 7.3 Directional FOV selection

Replace the old Tile-boolean scan with a bounded edge-derived check over the
query footprint. Preserve the accepted behavior:

- zero boundary blockers may use the ordinary symmetric cell FOV;
- one or more blockers uses the current bounded directional/supercover path;
- fixed-radius work is independent of total map area.

Do not add per-ray dependency indexes in this cut.

## 8. Near-side boundary observability

Add one neutral GridMap query that returns boundary object UUIDs exposed to a
given cell. It inspects only the four owner-side stores and, where a neighbor
Tile exists, the four facing neighbor stores. It deduplicates UUIDs and also
works at an outer boundary with only the owner Tile.

During `SpatialSensesSystem` recomputation:

1. enumerate ordinary entity/center-object contacts exactly as now;
2. locally aggregate exposed route cells by provider UUID across every visual
   candidate and each blindsight/tremorsense propagation footprint;
3. resolve each provider UUID once, in deterministic UUID order, through the
   existing exact raw-fact contact resolver;
4. keep route evidence separate from the output position: evaluate visual,
   range, stealth, invisibility, and each special sense against every
   qualifying near-side route cell, while writing the committed
   `WorldObjectPlacement.position` to `PerceivedContact.position`;
5. merge routes deterministically with `visual=any(qualifying visual route)`
   and the canonical enum-ordered union of all qualifying special senses;
6. do not add the far Tile to `visible` or `seen` merely to expose the object;
7. do not enumerate far-side center objects or entities; and
8. keep the result in the existing `PerceivedContact` value and contact maps.

The aggregation is a local temporary dictionary/set inside one observer
recompute. It is not a new contact type, wrapper, registry, reverse index, or
persisted state. A provider exposed from both reachable endpoints still yields
one deterministic contact. A provider may be contacted through a nonvisual
near-side route even when neither endpoint is visually visible.

The object does not own this subjective decision. Objective FOV/light still
includes every physical blocker whether or not an observer perceives it.

Observer candidate selection for a changed edge uses the existing spatial
event position/hint and existing subscriber/reverse observer indexes. It does
not scan all observers.

## 9. Mutation, cache, light, and event settlement

### 9.1 Derive deltas from complete edges

For runtime placement, relocation, orientation, removal, and door state
change:

1. capture the affected incident `WorldEdgeView` values before mutation;
2. validate or compute all provider values which may fail before mutation;
3. commit the existing object bands/reverse placement or item state;
4. derive the same incident edges after mutation;
5. compare complete channel answers;
6. invalidate each changed existing revision/cache family once;
7. begin/register the existing spatial lifecycle with exact after-values and a
   nonauthoritative `SensesUpdateHint`;
8. let the existing declaration-time optical-topology callback radius-filter
   relevant active lights, diff `affected_tiles`, and publish causal light
   children parented to that spatial event;
9. let existing spatial EFFECT handlers settle; and
10. let `SpatialSensesSystem` reduce the complete objective result at the
    established pre-completion seam.

The incident set is the physical edge named by a boundary placement; for a
center object it is the existing center-cell topology path. A relocation keeps
the accepted Phase 2 departure and arrival lifecycles and their current
two-step topology/light/sensory settlement. Do not add a batch event system.

On a prepublication failure, restore the same local bands/reverse placement,
provider state, revisions, and source-owned light contributions covered by the
accepted Phase 2 rollback boundary. Derived caches may be cleared rather than
copied. No fact survives a rejected mutation.

Every boundary-object placement/removal/state event selects every live incident
endpoint in its existing `SensesUpdateHint`, including an attachment event or
an open-door change whose aggregate structural channels are empty/unchanged.
An internal edge has two live endpoints; an outer boundary has only its owner.
This is required for object-contact admission/removal; the hint still does not
become replay state.

### 9.2 Cold rebuild

`rebuild_object_placements()` is not a runtime per-object lifecycle. It remains
the accepted event-suppressed cold/load operation:

1. stage and validate the complete forward/reverse placement bijection;
2. deduplicate the union of old/new incident edges;
3. commit bands/reverse placements and derive changed channel families;
4. update each changed revision/cache family and radius-filtered active-light
   objective footprint atomically;
5. restore all local objective state and event cursors on failure; and
6. publish no object, light, or sensory lifecycle.

It runs before the sole `WorldInitializedEvent` and before observers are
deployed. If a caller requires a live/eventful rebuild, stop: a batch runtime
lifecycle is outside Phase 3. Do not weaken event suppression or manufacture
one event per rebuilt object.

### 9.3 Door state change

Use the surviving door's existing action/lifecycle. The authoritative state
mutation must be followed by one GridMap topology settlement using the old and
new computed `BoundaryStructure`.

Closing collision/admission remains validated before `is_open` changes.
Opening/closing:

- preserves placement and UUID;
- publishes `OBJECT_CHANGED`, not remove/place;
- changes only channels which differ;
- does not relocate object-anchored SpatialConditions;
- does not move an attached light at the same XY; and
- recomputes optical light geometry before sensory pre-completion.

### 9.4 Event payloads

Replace the legacy item directional value with the existing semantic value:

```python
ItemState.boundary_structure: BoundaryStructure | None
ItemObservationState.boundary_structure: BoundaryStructure | None
```

Delete `ItemDirectionalStructureState` after all callers migrate.

Add one exact final semantic after-value to the existing spatial object fact:

```python
SpatialChangeEvent.object_boundary_structure: BoundaryStructure | None
```

It is the provider's committed structure after the operation according to this
exact matrix:

| Operation | `object_boundary_structure` |
|---|---|
| initial placement | current `BoundaryStructure`, or `None` for a center object/attachment |
| relocation departure | `None` |
| relocation arrival | current `BoundaryStructure`, or `None` for a center object/attachment |
| orientation or mechanical state change | current `BoundaryStructure`, or `None` for a center object/attachment |
| terminal removal | `None` |

`previous_placement` retains the old spatial authority on relocation departure
and terminal removal; arrival/change carries the committed placement. Do not
add a previous-structure field. Existing center
`object_blocks_movement/object_blocks_optics/object_blocks_propagation` facts
remain center mechanics, not boundary topology.

Delete the authoritative `SpatialChangeEvent.directional_position`,
`directional_directions`, `directional_channels`, and three directional map
fields after their consumers use placement plus `object_boundary_structure`.
The existing `SensesUpdateHint` may retain bounded incident positions and
changed channel names as acceleration; it is never replay state.

Add ordinary Pydantic identity/shape validation only. Do not add a reducer
framework or custom serializer.

### 9.5 World initialization

`WorldTileState` deletes `movement_open`, `optical_open`, and
`propagation_open`. Boundary topology is replayed from each
`WorldObjectState.placement` plus `item.boundary_structure`.

This Phase changes the existing bootstrap payload/schema only as required by
the topology cut. It does not alter the accepted one-`WorldInitializedEvent`
cold-build boundary and does not deploy Entities during initialization.

## 10. Atomic activation order

The implementation may be developed in the following green slices. Do not
activate a runtime dual authority between slices.

### Slice 3.0 — Freeze and inventory

1. Verify the frozen hashes and 88-file Phase 0/1/2 manifest.
2. Freeze fresh collecting/runnable node and blocked-signature ledgers.
3. Freeze every production/test/deprecated caller of the deletion symbols in
   section 11.
4. Add only characterization tests whose current behavior is an intended
   capability. New target-only tests may initially fail.

### Slice 3.1 — Cold and neutral target surface

1. Tighten `BoundaryStructure` canonical validation.
2. Extend `WorldEdgeStructuralContribution` with height.
3. Implement the new local `get_world_edge()` and exposed-boundary query over
   Phase 2 bands while legacy mechanics still consume their old projection.
4. Add reciprocal/locality/value tests.

This slice is safe because the new edge is derived read-only and is not a
second mutation authority.

### Slice 3.2 — Independent center-occupant cut

1. Add `WorldItem(BaseItem)` only as the reused fixed-spec implementation.
2. Port boulder, barricade, oil barrel, and every other ledgered physical
   center blocker to explicit occupying specs.
3. Preserve each center movement/optical/propagation rule and port authored
   builders.
4. Prove public collision, rollback, event, and locality behavior.

This slice uses the accepted Phase 2 center bands and does not depend on world
edges. It must not infer occupancy from a blocking boolean or content ID.

### Slice 3.3 — Atomic boundary/topology hard cut

Land these together before declaring the slice green:

1. concrete wall/door placement specs and semantic state;
2. every active, test, blocked, and deprecated wall/door authored, builder,
   editor, placement, and projection caller plus multi-side expansion;
3. door consolidation;
4. every movement/FOV/light/propagation consumer moved to derived edges;
5. near-side perception;
6. old/new edge cache/light/event settlement;
7. item/spatial/bootstrap event schema changes; and
8. regenerated content/icon bindings where their source declarations changed;
   and
9. deletion of the old live directional projection and every caller in the
   section 11 ledger.

Do not merge or hand off a state where new boundary objects no longer feed the
old booleans while consumers still read them, or where both systems remain
writable.

### Slice 3.4 — Authored cliff and attachment cut

1. Add and author the proving-ground cliff on the now-authoritative edge.
2. Port WallTorch and every ledgered fixture to an explicitly authored,
   nonoccupying boundary placement.
3. Prove height/channel independence, near-side contact, attachment coexistence,
   attached-light behavior, save/load, and initialization facts.

Do not infer either cliff existence or attachment side.

### Slice 3.5 — Hard deletion and certification

1. Prove every obsolete symbol and caller in section 11 is absent.
2. Run public behavior, wire/schema, dependency, locality, and full collection
   gates.
3. Write a final implementation manifest with exact file hashes and test
   evidence.
4. Freeze the implementation for two independent read-only reviews plus the
   required anti-slop pass.

## 11. Required deletion ledger

At completion, repository-wide Python search must find no production/test use
of:

- Tile's intrinsic `border_*`, `optical_border_*`, and
  `propagation_border_*` fields;
- Tile's `object_movement_border_*`, `object_optical_border_*`, and
  `object_propagation_border_*` fields;
- `_intrinsic_border`, `_derived_border`, `set_intrinsic_border`,
  `set_object_border`, and `allows_direction(s)`;
- BaseItem's twelve `blocks_{movement,optics,propagation}_{direction}` fields;
- `_blocks_direction`, `set_directional_blocking`,
  `set_directional_blocking_bulk`, and old directional blocker overrides;
- `get_objective_directional_structural_channels`;
- `ItemDirectionalStructureState` and `directional_structure` event fields;
- GridMap `_OBJECT_BORDER_FIELDS`, `_directional_block_map`,
  `recompute_tile_directional_blocking`, subjective directional Tile rebuild,
  and `set_tile_directional_border`;
- authored `blocked_directions` parameters/fields/defaults;
- `WorldTileState.movement_open`, `optical_open`, and `propagation_open`;
- authoritative `SpatialChangeEvent.directional_*` fields;
- `DoorObject`, its two actions, recipe/builder/content declaration, and
  duplicate generated binding entries; and
- old `is_perceivable_by`/bypass hooks in objective/subjective boundary paths.

Names inside historical documentation or an explicit deletion-gate string are
not gameplay references. Do not retain production aliases to satisfy old
tests.

## 12. Public behavior gates

Tests must use public commands, queries, events, and typed values. Do not
inspect private band dictionaries, cache dictionaries, source text, AST call
shape, or implementation call counts. If locality needs observation, extend
the existing structured last-operation diagnostic with edge/band/provider
counts; do not add a history or authority.

### 12.1 Structure and edge

- a concrete wall placed on either facing Tile yields the same reciprocal
  edge key and one contribution with exact UUID/base/top/channels;
- a concrete closed door preserves its provider contribution when open but has
  empty channels;
- the maintained initially-open door still has its authored WEST placement and
  one object identity;
- every migrated former center-door caller has one reviewed side/route proof
  or an explicit approved multi-boundary expansion;
- a nonoccupying wall torch shares every band with one occupying wall;
- an outer EAST WallTorch is exposed from its one live owner endpoint without a
  synthetic neighbor;
- facing occupying structures collide before mutation;
- one legacy multi-side authored row expands into distinct one-side objects in
  canonical order; and
- boulder, barricade, and oil barrel reject overlapping occupying center
  placement while crate preserves its authored nonblocking choice.

### 12.2 Height and channel independence

- ordinary unsupported two-step height blocks walking without a cliff object;
- the proving battlefield also contains the explicit `[0, 2)` cliff face;
- a lower `[0, 2)` cliff does not block height-2 upper walking when its movement
  interval does not intersect, but `[2, 4)` wall does;
- ordinary optics and propagation ignore boundary height and obey only their
  authored channels;
- flying/nonwalking behavior matches the pre-cut 2D contract; and
- no elevation creates optical blocking implicitly.

### 12.3 Movement, optics, light, propagation

- standard arena movement/path behavior is unchanged;
- one opaque wall blocks ordinary observer FOV and light-source geometry on
  the same edge;
- propagation-only, optical-only, and movement-only structures affect exactly
  their authored consumers;
- diagonal movement preserves its existing cardinal-bridge rule;
- moving/removing/rebuilding a wall updates edge mechanics and active light
  shadows;
- cold rebuild publishes no object/light/sensory lifecycle and is represented
  only by the eventual `WorldInitializedEvent`; and
- door open/close changes each affected revision exactly once and leaves
  unrelated channel revisions unchanged.

### 12.4 Subjective reduction

- an ordinary observer with a visible near cell receives a visual contact for
  its opaque boundary object;
- the same provider exposed through two reachable endpoint routes yields one
  deterministic contact;
- a nonvisual-only near-side route yields the canonical blindsight/tremorsense
  contact without making either endpoint visually visible;
- the far Tile is absent from `visible` and `seen` because of that wall;
- far-side center objects and entities are absent;
- invisibility, stealth, darkness, darkvision, truesight, blindsight, and
  tremorsense continue through the shared typed contact resolver; and
- objective edge topology is identical for observers who do and do not
  perceive the provider.

### 12.5 Events and replay

- place/change/remove facts contain exact placement and final boundary
  structure after-values;
- relocation departure carries no current boundary structure and arrival
  carries the committed current structure;
- open/close is one `OBJECT_CHANGED` lifecycle, not remove/place;
- same-XY door/attachment changes do not relocate anchors or lights;
- optical light settlement and its causal sensory deltas occur before the
  outer spatial completion, using the existing pre-completion order;
- `WorldInitializedEvent` reconstructs the same surfaces, placements, and item
  boundary states with no Tile directional tuples; and
- generic wire projection still excludes internal observer grants and no new
  Event/EventQueue fields appear.

### 12.6 Failure and locality

- collision or provider failure leaves object state, placement, bands,
  revisions, light, and event cursor unchanged;
- door close rejection leaves it open and publishes no false topology fact;
- an edge query inspects only two facing band stores and unique providers;
- near-side enumeration inspects only four incident edges;
- propagation barrier discovery inspects only its supplied bounded candidate
  footprint and incident edges and retains no global barrier cache;
- fixed-radius FOV work is independent of distant unused map Tiles for zero,
  one, and many boundary blockers;
- light recomputation scans active source count/radii plus used footprints, not
  map Tiles; and
- adding distant unused Tiles, objects, conditions, or observers does not
  change local eager-work diagnostics.

## 13. Validation commands and evidence

Use the workspace virtual environment and the practices in `HOW_TO_TEST.MD`.
The implementer must record exact commands, counts, durations, and failures in
the Phase 3 implementation ledger.

Required lanes:

1. compile/diff checks for every changed Python file;
2. focused structure/edge/placement tests;
3. movement/path/forced-movement/elevation tests;
4. FOV/light/senses/propagation/AoE tests;
5. item/action/content/bootstrap/wire tests;
6. all previously accepted Phase 0/1/2 lanes;
7. dependency and deleted-symbol gates;
8. fixed-radius locality/timing tests with warmup and repeated medians where
   timing is used; and
9. the frozen full collection/runnable lane, compared to the pre-edit module,
   node, and normalized blocked-signature ledgers.

A stale blocked module is not permission to skip its mechanical caller port.
No new collection-success module may become blocked. No baseline node may be
removed without an explicit, reviewed deletion ledger.

## 14. Stop conditions for Luna

Stop implementation and report to the supervisor if:

- any legacy door caller lacks enough maintained geometry/capability evidence
  to author one exact side or reviewed multi-boundary expansion;
- a content identity must remain for external persisted data not represented
  in the repository;
- a current movement mode needs a new altitude model to preserve behavior;
- event ordering cannot be preserved with the existing lifecycle and
  pre-completion seams;
- exact replay would require inventing an objective reducer framework;
- a required editor behavior cannot be ported without restoring its unrelated
  deprecated dependency stack;
- a performance gate suggests a new edge/light/ray index; or
- Phase 4 Entity occupancy appears necessary.

Do not broaden the phase to solve those questions.

## 15. Completion definition

Phase 3 is complete only when:

1. all section 12 behavior gates pass;
2. the section 11 production/caller deletion ledger is zero;
3. Tile bands and GridMap placement remain the only object-position authority;
4. `WorldEdgeView` is derived and nonauthoritative;
5. movement/optics/light/propagation share the intended three-channel model;
6. height affects boundary mechanics only for movement;
7. near-side boundary perception does not leak far content;
8. no EventQueue/reducer/controller/compatibility layer was introduced;
9. the full frozen collection comparison has no unapproved loss;
10. an exact implementation manifest is frozen; and
11. two independent reviewers approve correctness/executability and the final
    anti-slop audit reports no removable abstraction, duplicate authority,
    source-layout gameplay test, or global hot-path scan.

## 16. Review record

| Review | Revision | Verdict | Notes |
|---|---|---|---|
| Live code-surface/caller review | `7ad7ec686f6c9e41ac6a8af5ce8cb0c83be97ff966601a933d5064c3a52fe097` | APPROVED | correctness, dependency, lifecycle, locality, replay, and executability |
| Optics/light/cache and anti-slop review | `7ad7ec686f6c9e41ac6a8af5ce8cb0c83be97ff966601a933d5064c3a52fe097` | APPROVED + ANTI-SLOP APPROVED | no duplicate authority, speculative framework, global hot scan, or 3D optics creep |
