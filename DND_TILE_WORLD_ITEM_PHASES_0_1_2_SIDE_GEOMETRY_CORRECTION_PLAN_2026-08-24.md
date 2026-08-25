# Phase 0-2 Tile-side geometry correction plan

Status: APPROVED FOR IMPLEMENTATION GUIDANCE. The substantive reviewed revision
is SHA-256
`d7d423408fd79796c53d2ffac1b95b536e3b53ae6a57416ac6143391949ec33f`.
Implementation still requires an explicit request. Intended implementer: Luna;
implementation reviewers remain independent.

Governing inputs:

- corrected master plan file SHA-256:
  `73335294139bdc81306f17381afe22f27fb94c9c48bcf07c1312eb9eeefafe63`;
- corrected master substantive SHA-256:
  `46de9f570fb59fd8c9e8a105a3a699287a7881c93c880827d804faefad9c7f2d`;
- unified optics/illumination plan SHA-256:
  `3c9c58483440640837bc38fdaa6b624f358e1098c9a957f65923cd64f83a270b`;
- accepted pre-correction Phase 0-2 implementation manifest SHA-256:
  `34de6db66c80d336044ab90abd13e284971722551d4d2018678a12808971aad9`;
- testing rules: all of `HOW_TO_TEST.MD`.

The former Phase 3 guidance is revoked. Phase 3 does not begin until this
correction has been implemented, independently reviewed, and bound to a new
manifest.

## 1. Outcome

Correct the Phase 0-2 foundation without rolling it back:

1. a boundary object occupies one side volume inside its owner Tile;
2. adjacent `I:EAST` and `J:WEST` are independent volumes and may both contain
   occupying objects over the same height bands;
3. only same-center or same-Tile/same-side occupying bands collide;
4. GridMap writes no mirror membership on the adjacent Tile;
5. the preliminary world-edge query becomes an ordered source-to-destination
   view with distinct exit and entry contribution layers;
6. reverse traversal swaps those layers and endpoint facts instead of returning
   the same merged object;
7. serialized placements, placement events, and cold rebuild preserve both
   objects independently; and
8. the existing surfaces, placement authority, item workflows, events, lights,
   SpatialConditions, inventory/equipment behavior, and rollback/locality fixes
   remain intact.

This is a geometry correction, not a reimplementation of Phases 0-2.

## 2. Exact scope

### 2.1 Production scope

The required production surface is bounded to:

| File/owner | Correction |
|---|---|
| `dnd/core/world_edges.py` | make the hot `WorldEdgeView` ordered; retain `AdjacentEdgeKey` only as unordered adjacency identity |
| `dnd/core/gridmap.py::_resolve_object_placement` | stop inferring orientation from boundary side |
| `GridMap._placement_work_counts` | count only the owner Tile and locally covered bands for placement admission |
| `GridMap._validate_placement_collision` | delete neighbor/opposite-side occupancy probing and its staging parameter |
| `GridMap.validate_object_placement_batch` | delete canonical physical-edge staging; retain exact same-local-band joint admission |
| `GridMap.rebuild_object_placements` | accept opposing placements, retain same-side collision validation and existing atomic rollback/light settlement |
| `GridMap.get_world_edge` | preserve source/destination order and return separate exit/entry contributions |
| `GridMap.get_boundary_objects_on_edge` | delete the flattened unordered helper after its real callers are ported |

Repository-wide search at implementation start may add a directly affected
caller to this table. It does not authorize adjacent refactors.

### 2.2 Test and document scope

Port only behavioral tests and ledgers that encode the wrong geometry or the
changed ordered view. The known minimum is:

- `tests/engine/test_tile_surface_contract.py`;
- `tests/engine/test_world_edge_identity_and_elevation.py`;
- `tests/engine/test_elevation_proving_battlefield.py`;
- world initialization/replay coverage for exact object placements;
- placement event, locality, rebuild, light, and equipment fallback coverage;
- the Phase 0-2 implementation plan/ledger/manifest references; and
- the revoked Phase 3 guidance status.

Do not mechanically change a test merely because it uses words such as
`forward`, `reverse`, or `edge`. For example, observer-input order invariance is
not the same requirement as reciprocal world-transition equality. Classify the
capability before editing the expectation.

### 2.3 Explicit exclusions

This correction does not:

- implement Phase 3 structure migration;
- delete legacy directional Tile/item booleans;
- route production movement, FOV, light, or propagation through the new view;
- implement ordered boundary-contact reduction or aggregate two-layer
  movement/optical/propagation revision and active-light settlement;
- create walls, doors, cliffs, or attachments from authored declarations;
- change Entity occupancy or movement settlement;
- change EventQueue, reducers, pre-completion ordering, or event schemas;
- alter SpatialCondition ownership or light-source ownership;
- add an edge/side registry, cache, manager, mirror, receipt, or reservation;
- introduce `BoundarySideKey`, another direction enum, a compatibility view, or
  a public serialization DTO for the internal edge view; or
- reset, revert, or discard the accepted Phase 0-2 working tree.

## 3. Phase 0 — freeze the correction baseline

Before production edits:

1. verify the governing document and manifest hashes;
2. regenerate a scoped manifest for the current Python/JSON files and retain
   each member hash;
3. collect the complete suite with cache disabled and record:
   - collecting module paths and node IDs;
   - blocked module exception class, normalized terminal message, and first
     stable project frame; and
   - current failure signatures for collecting tests;
4. rerun the accepted Phase 0-2 focused lanes from the supervised ledger;
5. record the current public trace: first opposing-side placement succeeds,
   the second is rejected before mutation with no success event, and a legal
   single-placement cold rebuild succeeds; and
6. freeze repository-wide caller results for:
   - `get_world_edge` and every current `WorldEdgeView` field;
   - `get_boundary_objects_on_edge`;
   - `structural_contributions`;
   - reciprocal/opposite-edge collision messages and staging symbols;
   - boundary placements with omitted orientation; and
   - placement work diagnostics.

The current wrong rejection/equality tests are migration cases, not desired
baseline behavior. Preserve their capability and invert the expected result at
the proper public boundary; do not delete them to make the lane green.

## 4. Corrected cold geometry contract

### 4.1 Placement and collision identity

The only collision key is:

```text
(owner Tile position, center-or-cardinal-side, integer height band)
```

For adjacent Tiles `I` and `J`:

```text
I:EAST != J:WEST
```

Both keys may have an `occupant_uuid` over the same heights. Each Tile keeps
only its own forward band. `_object_placements` keeps one reverse value per
object. Neither command admission nor rebuild derives a canonical physical-edge
occupant.

`GridMap.get_boundary_objects_at(position, side, height)` remains the exact
side-membership query. The flattened unordered
`get_boundary_objects_on_edge(first, second)` is removed; its current test-only
callers use exact side queries or the ordered view.

### 4.2 Side and orientation

`boundary_direction` chooses the owner Tile's side. `orientation` is a separate
optional facing fact.

- GridMap does not default orientation to `boundary_direction`.
- A symmetric boundary object may commit `orientation=None`.
- An authored object which needs a facing supplies one explicitly.
- Rebuild accepts the exact stored optional orientation and never reconstructs
  it from band membership.

No `requires_orientation` capability or new policy field is added in this cut.
Phase 3's authored caller ledger supplies orientation only where the concrete
content needs it.

### 4.3 Ordered hot edge view

Keep the existing type names to avoid a second abstraction, but replace their
mechanical meaning in one hard cut:

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
    elevation_delta_steps: int
    source_surface_kind: ElevationSurfaceKind
    destination_surface_kind: ElevationSurfaceKind
    source_slope_axis: SlopeAxis | None
    destination_slope_axis: SlopeAxis | None
    exit_direction: CardinalDirection
    entry_direction: CardinalDirection
    exit_contributions: tuple[WorldEdgeStructuralContribution, ...]
    entry_contributions: tuple[WorldEdgeStructuralContribution, ...]
```

`AdjacentEdgeKey.between(source, destination)` remains canonical and unordered.
It is used only as adjacency identity and by existing bounded elevation
deduplication. It owns no placement and no merged mechanics.

For `get_world_edge(I, J)`:

1. retain caller order as source/destination;
2. require both live cardinally adjacent Tiles;
3. derive `exit_direction` from `I` toward `J`;
4. derive `entry_direction` from `J` toward `I`;
5. build `exit_contributions` from `I`'s facing intrinsic legacy facts, exact
   `I:exit_direction` boundary-band providers, and retained center-placed
   legacy directional providers at `I`;
6. build `entry_contributions` from `J`'s facing intrinsic legacy facts, exact
   `J:entry_direction` boundary-band providers, and retained center-placed
   legacy directional providers at `J`;
7. use each provider's exact placement base/top interval;
8. represent a legacy intrinsic Tile-side blocker with that Tile UUID and
   support band `[Tile.height, Tile.height + 1)`;
9. retain providers with an empty current channel tuple; and
10. sort providers deterministically by UUID inside each layer.

A boundary placement contributes only when its exact
`placement.boundary_direction` equals the layer direction. An object on another
side of the same Tile is never consulted for that layer. A retained
`WorldPlacementKind.CENTER` provider may temporarily contribute through
`get_objective_directional_structural_channels(direction)` until Phase 3 ports
the legacy wall/door family. `None` means absent; `()` retains the provider with
no blocked channel.

`get_world_edge(J, I)` has the same `.key`, swapped endpoints/layers/directions,
and the negated elevation delta. It is not equal to the forward view. There is
no `structural_contributions`, `first_*`, or `second_*` compatibility property.

The view remains an internal frozen derived value. It is not serialized,
published, cached as authority, or copied into events.

Phase 2 may still derive provider channels through the retained legacy
directional capability. Phase 3 replaces that capability with exact boundary
structures and routes the real mechanics through both layers. This correction
must not partially perform Phase 3.

## 5. Phase 1 correction — land the cold/view hard cut

1. Replace the `WorldEdgeStructuralContribution` and `WorldEdgeView` field
   contracts atomically.
2. Port every collecting caller from canonical `first/second` or merged
   `structural_contributions` to ordered source/destination and exit/entry
   fields.
3. Remove implicit orientation defaulting from placement resolution and the
   rebuild rule that rejects an otherwise valid `orientation=None` boundary
   placement.
4. Preserve strict exact-integer validation in persisted placement values.
5. Preserve Pydantic for authored/persisted/event values and frozen dataclasses
   for the hot derived view; add no custom serializer.
6. Add no compatibility alias for deleted fields or flattened contribution
   access.

Phase 1 exits only when the cold types and their direct callers compile and no
old view field remains.

## 6. Phase 2 correction — admission, rebuild, and exact facts

### 6.1 Local placement admission

In `_validate_placement_collision`:

1. retain the existing same-local-band occupant check;
2. retain the optional local `staged_occupants` input used by pure batch
   admission;
3. delete the adjacent Tile lookup and opposite-side band probe;
4. delete `staged_physical_edge_occupants`; and
5. do not replace it with another canonical adjacency key or neighbor scan.

In `validate_object_placement_batch`, retain one transient local staged-band map
so predicted candidates collide with one another on the same local band. Delete
only the physical-edge staging map. The method remains a pure admission query,
not a reservation or second authority. Its equipment caller and all previously
verified joint-fallback nonmutation behavior remain unchanged.

`_placement_work_counts` counts the distinct owner Tiles and exact locally
covered bands. A boundary placement does not count the neighbor merely because
one exists.

### 6.2 Mutation behavior

Place, move, and orient retain the accepted algorithm:

1. resolve and precompute provider mechanics used by facts/invalidation;
2. validate the complete local candidate before mutation;
3. snapshot only touched bands/reverse/border state;
4. commit the local forward bands and reverse placement;
5. settle existing legacy directional/cache/light behavior;
6. restore exact state on pre-publication failure; and
7. publish the existing exact placement lifecycle.

Changing one side never mutates or replaces the opposing side's bands or
placement. Both incident positions may remain event/sensory/cache candidates
when a live adjacent Tile exists; affected-query selection is not neighbor
storage ownership.

This correction preserves the current placement hints only. Ordered
boundary-contact accumulation and aggregate two-layer channel/revision/light
settlement begin in Phase 3, when the real mechanics consume the ordered view.
Do not pull `SpatialSensesSystem`, FOV, light, propagation, or movement callers
into this correction.

No EventQueue phase, callback, event field, or rollback framework changes.

### 6.3 Cold rebuild

`rebuild_object_placements` remains the cold/event-suppressed load boundary.
Modify only its geometry admission:

1. stage memberships and occupants by exact local band key;
2. accept `I:EAST` and `J:WEST` occupants at equal heights;
3. reject two occupants of the same Tile/side/height;
4. retain provider identity/spec/extent/Tile validation;
5. prove the exact placement-to-band bijection and occupant UUID locally;
6. retain existing bounded directional settlement, revision settlement,
   relevant-light recomputation, event-cursor suppression, and rollback; and
7. never persist or rebuild a world-edge row.

A failure while validating or settling one provider restores the entire prior
placement/band/topology/light state and publishes no fact. The already accepted
two-light directional-optics rollback regression remains mandatory.

### 6.4 Ordered query implementation

Rewrite `get_world_edge` to the contract in §4.3. It may inspect only the two
endpoint Tiles, their exact facing boundary bands, retained center providers,
and the corresponding reverse placements/providers. It must not scan the map
or mutate world, cache, event, or replay state. It may replace the existing
non-authoritative `GridMapOperationDiagnostics` snapshot with one aggregate
read-only-query row for this call; no new diagnostic type or history is added.

This slice proves the ordered data foundation. It does not yet replace the
legacy movement/FOV/light/propagation consumers; that is Phase 3.

### 6.5 Events, bootstrap, and replay

Existing event schemas already carry the authority required by this
correction:

- each placement event carries its exact owner Tile, side, height, occupancy,
  and optional orientation;
- two opposing objects publish two independent ordinary object facts;
- removing one carries only that object's previous placement;
- a constructed `WorldInitializedEvent` can contain both exact placements and
  both semantic item states; and
- its ordinary Pydantic round-trip yields placements that public
  `rebuild_object_placements`, with registered providers and live Tiles, uses to
  rebuild both local memberships and derive forward/reverse views on demand.

Do not add an edge event, side event, flattened adjacency field, or
`previous_boundary_structure` field.

An end-to-end authored-bootstrap/reducer proof is deferred until Phase 3/5 has
real authored boundary objects and its established initialization boundary. Do
not restore deprecated server reducers, call a private snapshot helper, or add
an objective reducer framework for this correction.

## 7. Public behavioral gates

All gameplay tests use public commands, queries, completed events, canonical
snapshots, resolved light, or the existing structured operation diagnostics.
They do not inspect private band dictionaries, monkeypatch internal helpers,
assert source text, or count private calls.

### 7.1 Placement and independence

1. Place occupying `A` at `I:EAST [0,2)` and occupying `B` at
   `J:WEST [0,2)`; both commands succeed.
2. Exact side queries return `A` only from `I:EAST` and `B` only from `J:WEST`.
3. Placement iteration and completed events retain two UUIDs and two exact
   owner-side placements.
4. Removing, orienting, or moving `A` leaves `B` unchanged.
5. A second occupant on `I:EAST` over either band rejects before mutation and
   publishes no event.
6. A nonoccupying attachment may share `I:EAST` with `A` but is not the
   occupant.
7. A symmetric boundary object placed without orientation commits `None`; an
   explicitly oriented object retains its independent facing.

### 7.2 Ordered view

1. `get_world_edge(I, J)` and `get_world_edge(J, I)` share the canonical key but
   swap source/destination, exit/entry directions, and contribution tuples.
2. Directed elevation delta changes sign.
3. `A` appears only in the forward exit/reverse entry layer; `B` appears only
   in the forward entry/reverse exit layer.
4. Contribution base/top and channel tuples equal the exact provider state.
5. A current open door remains in its layer with empty channels.
6. A structural boundary provider anchored on another side of the source Tile
   is absent from this transition layer, while a retained center legacy
   directional provider remains represented during the transition cut.
7. A missing endpoint rejects; an outer boundary remains inspectable through
   the exact one-side query.

### 7.3 Rebuild, bootstrap, and rollback

1. Save the two opposing placements, remove them, rebuild, and observe both
   exact local side memberships and ordered views.
2. A public Pydantic round-trip of `WorldInitializedEvent` preserves two
   `WorldObjectState` rows with their exact opposing placements and semantic
   item state.
3. Feeding those round-tripped placements to public rebuild with registered
   providers/live Tiles produces the same forward and reverse ordered views.
4. Same-side staged collision rejects the whole rebuild with old authoritative
   state, revisions, lights, and events unchanged. The existing diagnostics
   boundary records the current failed rebuild with zero replacements rather
   than retaining a stale previous-operation row.
5. Retain the accepted directional-provider failure and two-light optical
   failure rollback cases.

### 7.4 Locality and non-regression

1. Placement diagnostics report one owner Tile and exactly the object's covered
   bands regardless of whether the adjacent Tile or distant unused Tiles exist.
2. The one aggregate `GridMapOperationDiagnostics` row for an ordered-view query
   reports two endpoint Tiles plus the exact facing bands and center providers
   visited; the same local scenario reports identical work after adding distant
   unused Tiles.
3. Nonoptical rebuild does not scan light sources; optical rebuild retains the
   accepted active-source radius scan and affected-footprint diff.
4. Joint equipment fallback rejection remains zero-mutation/zero-event when
   predicted items conflict on the same local center bands.
5. WallTorch, Continual Flame, spatial anchors, floor-item facts, chest spill,
   Heroes' Feast, surface replacement, and live illumination preservation
   retain their accepted behavior.

## 8. Required validation sequence

Run with the repository virtual environment and cache disabled where collection
identity is recorded.

1. compile and diff hygiene;
2. exact new side-geometry, ordered-view, rebuild, event, replay, and locality
   regressions;
3. complete Tile surface/world-edge/elevation files;
4. placement/item/equipment/light/spatial-anchor focused lanes;
5. the accepted Phase 0-2 capability lane, spell-family lane, and architecture
   lane recorded in the supervised ledger;
6. complete collection and comparison with the Phase-0 module/node/error
   signatures; and
7. a final scoped Python/JSON manifest with every member hash.

Expected comparison rules:

- no collecting capability disappears;
- only explicitly named new regressions may add nodes;
- blocked-module failure classes/signatures do not change accidentally;
- every new behavior case passes;
- no stale shared-edge symbol or reciprocal-collision expectation remains; and
- relevant focused timing/diagnostic results remain proportional to used local
  bands/providers, not map area.

The final implementation review binds the exact correction manifest, not a
moving worktree or the superseded `34de6db...` manifest.

## 9. Deletion and residue gates

After implementation, repository-wide searches must find zero active uses of:

- `staged_physical_edge_occupants`;
- reciprocal/opposite-edge collision errors or expectations;
- `WorldEdgeView.structural_contributions`;
- `WorldEdgeView.first_*` / `second_*` endpoint fields;
- forward/reverse `WorldEdgeView` equality expectations;
- `get_boundary_objects_on_edge`; and
- implicit `orientation = boundary_direction` placement defaulting.

Retain `_opposite_direction` only for real ordered entry-direction derivation
and other live geometry callers; do not delete it merely because collision
admission no longer uses it.

No compatibility property, deprecated alias, dual field, or source-layout
gameplay assertion may satisfy these gates.

## 10. Documentation and handoff

On successful implementation:

1. add a correction notice to the old Phase 0-2 implementation plan and ledger
   without erasing their historical evidence;
2. create a new exact implementation manifest and supervised verification
   continuation;
3. keep the old Phase 3 guidance marked revoked;
4. regenerate Phase 3 guidance from the corrected master and accepted
   correction manifest; and
5. require independent correctness and anti-slop implementation reviews before
   Phase 3 begins.

Do not describe the old `34de6db...` implementation as wholly broken. Its Tile
side storage, reverse placement, surfaces, exact facts, rollback, light,
SpatialCondition, inventory/equipment, and locality work are retained. The
correction removes the wrong reciprocal collision authority and replaces the
preliminary merged edge view.

## 11. Completion definition

The correction is complete only when:

1. opposing Tile sides accept independent occupying objects at identical
   heights;
2. same-Tile/same-side occupancy still rejects atomically;
3. local bands and the one reverse placement dictionary remain bijective;
4. ordered edge views preserve exit and entry provider identity and reverse
   correctly;
5. orientation is never inferred from side;
6. rebuild, bootstrap, replay, event, light, anchor, and equipment behavior is
   preserved;
7. the flattened edge helper and reciprocal-collision machinery are gone;
8. public behavior/locality gates and the full collecting comparison pass;
9. two independent reviewers approve the exact implementation manifest, with
   an explicit anti-slop verdict; and
10. new Phase 3 guidance is based only on this accepted state.

## 12. Review record

| Review | Focus | Status |
|---|---|---|
| Correctness/executability | geometry, atomicity, rebuild, callers, tests | APPROVED on substantive SHA `d7d42340...` |
| Optics/movement/anti-slop | ordered view, locality, replay, scope discipline | APPROVED + ANTI-SLOP APPROVED on substantive SHA `d7d42340...` |
