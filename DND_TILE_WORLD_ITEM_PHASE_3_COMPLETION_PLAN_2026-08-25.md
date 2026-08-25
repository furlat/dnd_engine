# Phase 3 completion plan: Slice 3.4 and Slice 3.5

Status: `APPROVED_FOR_LUNA_IMPLEMENTATION`.

Substantive independently reviewed revision:
`22e45a4b0a27dfa8952d534d08e9beef3922b28594b4bc6ab9314be9d652000b`

Review verdict: `APPROVED`. Slice 3.3 remains frozen; this document authorizes
only the bounded Slice 3.4/3.5 work below.

Date: 2026-08-25

## 1. Purpose

Complete only the work still missing from Phase 3 after the accepted Slice 3.3
repair:

1. Slice 3.4: make the proving cliff and every active WallTorch a real,
   explicitly authored Tile-side object; then prove the required height,
   channel, attachment, light, event, round-trip, rebuild, and bootstrap
   behavior.
2. Slice 3.5: remove the last active dead authoring residue, prove all deletion
   gates, run the complete active in-process validation envelope, freeze exact
   artifacts, and obtain independent correctness and anti-slop approval.

This plan does not redesign the accepted ordered-side system. It finishes the
two content families deliberately deferred from Slice 3.3 and certifies the
whole Phase 3 result.

## 2. Frozen baseline and authority

Implementation starts only from the exact accepted Slice 3.3 bytes.

| Authority | SHA-256 |
|---|---|
| Master migration plan | `50411e5575e6336ca0301acf032797cdf1d5ea885df5ccd37d6619f593e7a193` |
| Ordered-side Phase 3 guidance | `ed3b4afbe88ab4278c27429b3c9b1727a8ccdc144c3019ab5dcef00ca1715cd0` |
| Active-runtime scope amendment | `f10e2fbbcb6ba8732d078f0c4f2f5276716eb51e32c083068f3cae93c9ba52d6` |
| Active-runtime ledger | `63e25aac3f0136daa8d43b860c328fe8b7b9f26529f65792b123dc77293c059a` |
| Slice 3.3 repair plan | `5b8c50f6cbbd8100380fb5fc091e9b4389406d024256063d03632af6445b937e` |
| Slice 3.3 implementation manifest | `2e1ed59f9615bc4c97863cb46cbfa9328d35d145f080f48b90b44656c852a296` |
| Slice 3.3 implementation ledger | `cefc0700bdadcce62d419a20f5c8261c10e9c4ae3c10d8e7fef9badcffbe6cc1` |

The 44 Slice 3.3 manifest members were rechecked against the live tree on
2026-08-25 with zero hash mismatches. The accepted test baseline is:

- complete active in-process lane: 612 tests;
- 14-module capability lane: 319 tests;
- spell-family lane: 62 tests;
- architecture lane: 41 tests; and
- normalized active node-set hash:
  `44879b5db62038d56191eb427d9c29c9b2f9194a2bae70ac32b1a20a51f03184`.

Any mismatch before implementation is a stop, not permission to absorb new
changes.

## 3. Scope boundary

### Included

- active single-process Python mechanics and authored Python content;
- real `GridMap` placement, ordered edge, movement, optics, light,
  propagation, event, item-state, and cold-bootstrap boundaries;
- collecting in-process engine/manual/architecture tests in the accepted
  active lane; and
- final Markdown ledgers and exact Python/JSON manifests.

### Excluded

- deprecated server or editor code;
- SDK, TypeScript, JavaScript, generated transport, cross-language schemas,
  HTTP, and replication work;
- inactive `dnd/items/environment_content.py` and its deleted content-system
  dependencies;
- pygame rendering changes, new glyph policy, and map-editor persistence;
- Phase 4 entity occupancy or any 3D actor-volume calculation; and
- new registries, caches, indexes, reducers, controllers, compatibility
  facades, custom serializers, or event families.

Existing excluded-file dirt is frozen and ignored. Slice 3.4/3.5 must not edit
or validate it.

## 4. Frozen mechanical and authored facts

### 4.1 Geometry rules that must not change

- `I:EAST` and `J:WEST` are independent Tile-owned side volumes, not one
  shared edge slot.
- Same-Tile, same-side, overlapping occupying bands collide. Equal-height
  occupants on opposing Tile sides are legal.
- A transition reads source exit and destination entry in that order. Both
  layers must transmit the requested channel.
- Height intersection affects walking only. OPTICAL and PROPAGATION remain
  two-dimensional and use authored channels.
- Objective sight and light use the same OPTICAL topology. Subjective
  perception remains reducer-owned.
- Tile bands plus the one GridMap reverse-placement map remain the only
  placement authority. `WorldEdgeView` remains derived.

### 4.2 Exact content rows

| Object | Owner Tile and side | Bands | Orientation | Structure/channels |
|---|---|---:|---|---|
| Proving cliff | `(11,5)`, WEST | `[0,2)` | none | STONE / CLIFF; MOVEMENT only |
| Arena torch A | `(14,1)`, EAST | `[1,2)` | WEST | no structure; no blocked channels |
| Arena torch B | `(14,13)`, EAST | `[1,2)` | WEST | no structure; no blocked channels |
| Control-room torch | `(4,10)`, WEST | `[1,2)` | EAST | no structure; no blocked channels |

The control-room row resolves the only content decision left open by the Slice
3.3 ledger: it is mounted on the owner Tile's western side and faces east into
the control room. Approval of this plan approves that exact row. If the row is
rejected, revise it before implementation; never infer a replacement from
coordinates.

Owner side, base, and orientation are independent authored values. Runtime
code must derive none of them from coordinates, elevation, wall presence, or
one another.

## 5. Current gaps

| Gap | Current state | Required end state |
|---|---|---|
| Cliff provider | `CLIFF` enum exists, but the proving height change has no placed cliff object | One concrete fixed item provides the exact proving cliff |
| Cliff authorship | `(11,5)` is only an elevation row | Cold layout contains a separate explicit cliff object row |
| WallTorch placement | Inherits center/nonoccupying placement and `mount()` accepts only position/lit | Fixed boundary/nonoccupying/extent-1 spec; every mount supplies side/base/orientation |
| Arena torch facts | Position-only constant | One exact mount-fact collection used by cold and hot construction |
| Control-room torch facts | Position only | Exact WEST/base-1/EAST cold and hot row |
| Battlefield object schema | Knows wall/door sides only | Knows cliff and exact optional boundary/base/orientation facts with kind-specific validation |
| Public proof | Generic topology primitives exist | Real cliff and real WallTorch prove the complete Slice 3.4 matrix |
| Residue/certification | Slice 3.3 scoped audit only | Phase-wide active zero-reference audit, exact final manifest/ledger, two approvals |

## 6. Authorized mutation envelope

Slice 3.4 is expected to change only these production files:

| File | Authorized purpose |
|---|---|
| `dnd/items/environment.py` | concrete fixed cliff provider |
| `dnd/items/torches.py` | WallTorch boundary capability and explicit mount command |
| `dnd/content/items/environment_item_builders.py` | direct cliff builder/export |
| `dnd/content/items/item_catalog.py` | direct `environment.cliff_face` identity |
| `dnd/maps/arena_layout.py` | exact arena torch mount facts and hot placement |
| `dnd/content/scenarios/battlefield_definitions.py` | cliff kind and exact placement fields/validation |
| `dnd/content/scenarios/battlefield_builders.py` | cold/hot cliff and torch authoring |

Expected test edits are limited to:

- `tests/engine/test_tile_surface_contract.py`;
- `tests/engine/test_elevation_proving_battlefield.py`;
- `tests/engine/test_items_inventory_equipment.py`;
- `tests/engine/test_spell_families.py`;
- `tests/engine/test_direct_scenario_deployment.py`;
- `tests/manual/test_37_authored_encounter_mechanics.py`; and
- `tests/manual/test_72_battlefield_deployment_catalog.py`.

Slice 3.5 may additionally edit `dnd/maps/arena_layout.py` only to delete the
unused `DOOR_DIRECTIONS` and `WALL_DIRECTIONS` constants. No core `GridMap`,
world-edge, event, senses, light, condition, or cache file is expected to
change. Needing any file outside this envelope is a stop for supervisor review.

## 7. Slice 3.4 implementation sequence

### 7.1 Preflight

Before editing:

1. verify all 44 Slice 3.3 manifest hashes;
2. collect the exact active lane and confirm the 612-node baseline/hash;
3. run the current 612 active tests once;
4. record existing unrelated/excluded dirt without modifying it; and
5. freeze the exact WallTorch caller inventory in Section 7.3.

Do not start from a partially modified Slice 3.4 tree.

### 7.2 Add one concrete cliff provider

In `dnd/items/environment.py`, add `CliffFace(BaseItem)` with only the fixed
behavior needed by this content family:

- boundary placement;
- occupying bands;
- vertical extent 2;
- nonpickable, nonusable, nontargetable fixed environment object;
- included as a sensory object but not an available object action;
- `BoundaryStructureKind.CLIFF`;
- `Material.STONE`; and
- `(WorldEdgeChannel.MOVEMENT,)` exactly.

Do not add configurable cliff channels, an elevation observer, a generic
boundary-provider hierarchy, or automatic cliff creation/removal.

Add `build_cliff_face(display_name="Cliff Face")` to the active direct
environment builder with semantic key `environment.cliff_face`, and add the
same identity to the direct item catalog. Construction does not own side or
base; the placement command does.

### 7.3 Convert WallTorch to an explicit attachment

`WallTorch.get_world_placement_spec()` returns:

- `WorldPlacementKind.BOUNDARY`;
- `occupies_bands=False`; and
- `vertical_extent_steps=1`.

It does not provide a boundary structure and therefore contributes no
movement, optical, or propagation blocker. Its existing UUID-anchored light,
ignite/extinguish actions, light lifecycle, and terminal-removal cleanup stay
unchanged.

Change `mount()` so callers must provide all three placement facts:

- `boundary_direction: CardinalDirection`;
- `base_height_steps: int`; and
- `orientation: CardinalDirection`.

`mount()` delegates those values to `GridMap.place_object()` and then applies
the requested `lit` state. It stores no duplicate private coordinate, side,
base, or orientation. There is no default side/base/orientation overload and
no compatibility facade.

Port every active call site:

| Caller | Exact treatment |
|---|---|
| standard arena loop (two objects) | use the two EAST/base-1/WEST authored rows |
| multi-object control room | WEST/base-1/EAST |
| two item/light lifecycle fixtures | explicit fixture facts; repeat them in `move_object()` |
| two Sleet Storm fixtures | explicit fixture facts while preserving inside/outside spell geometry |

For non-content fixtures whose side is not the behavior under test, author an
explicit local row (recommended EAST/base-1/WEST); do not create a production
default. The unmounted invalid-light fixture needs no placement change.

Replace `WALL_TORCH_POSITIONS` with one compact immutable
`WALL_TORCH_MOUNTS` tuple containing position, owner side, base, and
orientation. Both hot arena construction and cold battlefield projection read
that tuple. Do not introduce a mount DTO, registry, policy object, or second
position-only authority.

### 7.4 Extend cold battlefield definitions without a materializer framework

In `BattlefieldObjectDefinition`:

1. add `"cliff"` to `BattlefieldObjectKind`;
2. add optional `base_height_steps: StrictInt | None`;
3. add optional `orientation: CardinalDirection | None`; and
4. enforce these exact invariants:
   - wall, door, cliff, and WallTorch rows require `boundary_direction`;
   - center kinds forbid boundary direction, explicit base, and orientation;
   - cliff rows require an explicit base;
   - cliff orientation remains optional and independent of owner side;
   - WallTorch rows require explicit base and orientation;
   - wall/door rows retain their accepted support-relative base and optional
     orientation behavior; and
   - `is_open` is valid only for doors.

Do not assert that orientation is the opposite of owner side. They remain
independent even when a particular authored row uses opposing directions.
Do not encode the proving battlefield's base or orientation as a reusable
`cliff`-kind rule: only the exact `(11,5)` proving row is base 0 with no
orientation.

Extend `_object_definition()` only enough to pass these values into the cold
model.

Author and build content directly:

- `_standard_hazards_layout()` emits both maintained arena torch rows from
  `WALL_TORCH_MOUNTS`;
- the hot standard arena mounts those exact same rows;
- `multi_object_dark` emits the plan-frozen control-room row, and its hot builder
  selects that unique cold row and passes its exact placement fields;
- `_elevation_proving_layout()` adds the exact cliff row at `(11,5)` WEST,
  base 0; and
- `_build_elevation_proving_ground()` selects the unique cold cliff row,
  directly builds/places it from those facts, and records its UUID as
  `object_uuids["cliff"]`.

The battlefield builder may select the known cliff row directly. Do not add a
generic content materializer, factory registry, dispatch framework, or schema
translation layer for one item.

### 7.5 Public proof matrix

Tests follow `HOW_TO_TEST.md`: real providers through public commands/queries,
structured values and completed events, no private band inspection,
monkey-patched call counts, source-text assertions, or arbitrary sleeps.

Add exactly two new test nodes.

#### New node A

`tests/engine/test_tile_surface_contract.py::test_cliff_and_wall_torch_use_exact_boundary_height_contracts`

Using real `CliffFace`, `WallTorch`, and `DirectionalWall` objects, prove in one
small two-Tile scenario:

- both Tiles have support height 2;
- destination WEST holds the occupying cliff at `[0,2)`;
- the same destination side also holds a nonoccupying torch at `[1,2)`;
- the torch is returned as a side object but never as a structural
  contribution;
- the low movement-only cliff does not block height-2 upper walking;
- that same authored MOVEMENT channel blocks nonwalking movement such as
  flying, because only walking applies height-band intersection;
- the cliff does not block OPTICAL or PROPAGATION;
- a source EAST wall is first placed at `[0,2)`, exactly overlapping the
  destination-WEST cliff's occupied heights, and both occupying objects
  legally coexist with distinct UUIDs and ordered layers;
- height-2 upper walking remains open while both structures occupy only
  `[0,2)`;
- `GridMap.move_object()` then moves that same wall, with explicit EAST side,
  base 2, and orientation, to `[2,4)`, after which upper walking is blocked;
  and
- the before/after placements retain independent UUID, owner side, base/top,
  orientation, occupancy, structure, and channel facts.

This is the real-content replacement proof for height/channel independence,
same-side attachment coexistence, equal-height opposing occupants, and the
explicit boundary move contract.

#### New node B

`tests/engine/test_direct_scenario_deployment.py::test_world_initialized_round_trip_preserves_cliff_and_wall_torch_boundary_state`

Through `build_battlefield()` and the emitted `WorldInitializedEvent`, prove:

- standard hazards emit exactly one completed `WorldInitializedEvent`;
  condition, connector, flame, and other legitimate bootstrap lifecycles may
  also exist in the EventQueue;
- an arena WallTorch snapshot has boundary/nonoccupying/base-1/top-2/EAST/WEST
  placement and a lit item-light state;
- its outer EAST route exposes the owner layer and has no synthetic entry
  Tile/layer;
- the event survives `model_dump_json()` ->
  `WorldInitializedEvent.model_validate_json()` exactly;
- rebuilding the complete placement tuple from the round-tripped event emits
  no per-object runtime lifecycle and leaves the torch's settled anchored
  light exact;
- elevation proving emits exactly one completed `WorldInitializedEvent`, not
  one total EventQueue event;
- its cliff snapshot has boundary/occupying/WEST/base-0/top-2 placement and
  CLIFF/STONE/MOVEMENT-only semantic state;
- the cliff event row survives the same Pydantic round-trip; and
- after an intentional cliff placement removal, public cold placement rebuild
  receives the complete placement tuple from the round-tripped event and
  restores the cliff plus every other battlefield placement without emitting
  rebuild lifecycle events or silently retiring unrelated objects.

Do not claim that placement rebuild hydrates mutable item state. Torch light
state is proved in the serialized `ItemState`; terminal removal still
correctly douses it.

#### Extend existing nodes without renaming them

- `test_elevation_proving_battlefield_cold_layout_matches_runtime`: cold and
  hot cliff row/UUID/placement equality.
- `test_elevation_proving_battlefield_exercises_ordered_edge_rules`: entry
  layer contains the explicit cliff; walking and flying are blocked by its
  authored MOVEMENT channel; optical and propagation pass. This deliberately
  replaces the old flying-allowed expectation at `(10,5) -> (11,5)`. Preserve
  the separate rule that elevation alone does not block flying by proving
  `(11,5) -> (12,5)` remains flyable and has no inferred CLIFF contribution.
- `test_wall_torch_attached_light_follows_move_and_terminal_removal`: explicit
  mount/move placement fields and anchored-light movement.
- `test_terminal_torch_cleanup_keeps_previous_mechanics_and_outer_parent`:
  explicit mount facts; preserve event ordering and parentage.
- `test_eb_15_043_sleet_storm_douses_exposed_flames`: explicit mount facts;
  preserve spell behavior and inside/outside distinction.
- `test_multi_object_control_room_exposes_several_nearby_object_actions`:
  exact control-room placement plus unchanged extinguish/action discovery.
- `test_battlefield_layouts_retain_terrain_barriers_and_objects`: exact cold
  arena/control torch rows and proving cliff row.
- `test_every_battlefield_has_one_builder_and_layout_matches_runtime`: cold/hot
  placement equality for the new rows.

No existing selector is deleted or renamed.

### 7.6 Event, cache, light, and replay guardrails

Slice 3.4 consumes accepted systems; it does not add a new propagation path.

- `GridMap.place_object`, `move_object`, `remove_object`, and
  `rebuild_object_placements` remain the placement boundaries.
- Existing `SpatialChangeEvent` placement after-values already carry exact
  side/base/top/orientation and structure facts.
- Existing light callbacks already follow the WallTorch's placement UUID.
- Existing spatial revisions, light settlement, sensory pre-completion, and
  movement-step settlement remain unchanged.
- Existing `WorldInitializedEvent`/`WorldObjectState` Pydantic models already
  carry placement plus item state; use them directly.
- Cold rebuild remains silent and cache invalidation remains owned by GridMap.

If any proof requires changing event schemas, reducer ordering, sensory
ownership, light scanning, revision semantics, or cache/index design, stop and
report the exact missing contract. Do not reopen Slice 3.3 inside Slice 3.4.

### 7.7 Slice 3.4 checkpoint

Before starting Slice 3.5:

1. compile only the changed active Python files;
2. run `git diff --check` on the active candidate;
3. run the two new selectors and every extended selector;
4. run the 14-module capability lane, spell-family lane, architecture lane,
   and complete active lane;
5. collect and hash the active node set;
6. preserve the exact checkpoint commands, results, and changed-file hashes
   for the final completion ledger; and
7. supervisor-audit all changes against Sections 4-7 of this plan.

Do not create a second provisional manifest/ledger layer. Slice 3.5 owns the
one final Phase 3 manifest and completion ledger.

Expected collection is exactly 614 nodes: the accepted 612 plus the two named
nodes above. Expected capability count is 321; spell remains 62 and
architecture remains 41. Any different count requires an explicit node-level
explanation and review; never adjust the expectation merely to make a run
green.

The exact 14-module capability command is frozen here rather than reconstructed
from a historical ledger:

```bash
./.venv/bin/pytest -q -p no:cacheprovider \
  tests/engine/test_grid_pathfinding.py \
  tests/engine/test_world_edge_identity_and_elevation.py \
  tests/engine/test_elevation_performance_contract.py \
  tests/engine/test_items_inventory_equipment.py \
  tests/engine/test_action_discovery.py \
  tests/engine/test_spatial_effects.py \
  tests/engine/test_direct_spatial_effect_materialization.py \
  tests/engine/test_senses_light_stealth.py \
  tests/engine/test_event_lifecycle.py \
  tests/engine/test_event_wire_visibility_contract.py \
  tests/engine/test_objective_state.py \
  tests/engine/test_direct_scenario_deployment.py \
  tests/engine/test_runtime_reset.py \
  tests/engine/test_tile_surface_contract.py
```

## 8. Slice 3.5 deletion and certification

### 8.1 Remove only confirmed dead active residue

Delete the unused `DOOR_DIRECTIONS` and `WALL_DIRECTIONS` constants from
`dnd/maps/arena_layout.py`. Their only remaining caller is an excluded legacy
test. Do not edit that test or restore compatibility fields.

Retain these approved, mechanically meaningful names:

- `SensesUpdateHint.directional_positions`;
- `SensesUpdateHint.directional_neighbors`;
- `SensesUpdateHint.directional_channels_changed`;
- `Senses.directional_collision_blocked`; and
- the bounded `GridMap` propagation caches.

Also retain `place_standard_directional_barrier` and historical test wording
where the word “directional” describes current behavior rather than an old
authority. Do not spend the certification cut on cosmetic renames.

### 8.2 Prove Section 14 zero-reference gates in the active envelope

Search active production and the exact accepted test paths, while explicitly
excluding deprecated/server/editor/SDK/generated paths and
`dnd/items/environment_content.py`. Classify every textual match. Active
gameplay use of any of the following is a blocker:

- Tile `border_*`, `optical_border_*`, `propagation_border_*`, intrinsic or
  derived directional-border authorities/setters, and directional
  `allows_direction(s)`;
- BaseItem's twelve directional blocking fields/helpers and neutral BaseBlock
  directional-block hooks;
- `get_objective_directional_structural_channels`;
- `ItemDirectionalStructureState` or `directional_structure` state;
- object-border maps/recomputation, subjective Tile-border rebuilding, or
  `set_tile_directional_border`;
- authored `blocked_directions` fields, parameters, or defaults;
- duplicate scenario-compatibility topology evaluators;
- `WorldTileState` directional-open tuples;
- authoritative `SpatialChangeEvent.directional_*` maps;
- active `DoorObject`, duplicate door actions/builders/catalog construction;
- no-argument global barrier discovery/cache; and
- object-owned `is_perceivable_by` or subjective boundary bypass hooks.

Historical governance text, explicit deletion-gate strings, excluded files,
and the retained hint/collision-memory fields are not gameplay references.
Record them as classified exclusions instead of editing them.

### 8.3 Final validation sequence

Run and record, in this order:

1. verify that every Slice 3.3 member outside the authorized Slice 3.4/3.5
   mutation envelope still matches its accepted hash, and that every intended
   divergence is explicitly ledgered;
2. compile of every changed active production/test Python file;
3. `git diff --check` scoped to the active candidate;
4. exact new/extended Slice 3.4 selectors;
5. placement/ordered-edge/elevation/movement/path/forced-movement lanes;
6. FOV/light/senses/propagation/AoE/condition lanes;
7. item/action/content/bootstrap/event/replay/WallTorch/spatial-anchor/
   concentration/Continual-Flame lanes;
8. the exact 14-module capability lane;
9. the complete spell-family lane;
10. the complete architecture lane;
11. the complete active in-process lane;
12. exact active collect-only, sorted node-set count, and hash;
13. Section 14 zero-reference searches;
14. existing structured locality gates; and
15. exact active implementation manifest verification with zero mismatches.

The event/mechanics run explicitly includes the accepted per-movement-step
settlement proofs in `tests/engine/test_move_settlement.py` and the exact
turn-start perception selector from
`tests/manual/test_17_encounters_turns_controllers.py`. They must remain green
without late refreshes, new reducer ownership, or changed event ordering.

Repository-wide or excluded test collection may be diagnostic only. It cannot
block or enlarge this active-runtime cut.

### 8.4 Final artifacts

Create:

- `DND_TILE_WORLD_ITEM_PHASE_3_IMPLEMENTATION_MANIFEST_2026-08-25.json`; and
- `DND_TILE_WORLD_ITEM_PHASE_3_COMPLETION_LEDGER_2026-08-25.md`.

The final manifest is the sorted union of:

1. the exact 41-path retained active Slice 3.1 seed frozen below;
2. all 44 accepted Slice 3.3 manifest members; and
3. every additional active `.py`/`.json` file actually changed by approved
   Slice 3.4/3.5 work.

The exact retained Slice 3.1 seed is:

```text
dnd/blocks/base_item.py
dnd/blocks/equipment.py
dnd/blocks/inventory.py
dnd/blocks/sensory.py
dnd/content/items/authored_item_builders.py
dnd/content/items/authored_item_definitions.py
dnd/content/scenarios/battlefield_builders.py
dnd/core/base_block.py
dnd/core/base_tiles.py
dnd/core/events/item_events.py
dnd/core/events/world_events.py
dnd/core/gridmap.py
dnd/core/world_edges.py
dnd/entities/entity.py
dnd/items/environment_interactables.py
dnd/items/torches.py
dnd/maps/arena_layout.py
dnd/runtime_reset.py
dnd/spatial/area_conditions.py
dnd/spells/conjuration.py
dnd/types/materials.py
dnd/types/world_placement.py
tests/architecture/test_dependency_boundaries.py
tests/engine/test_action_discovery.py
tests/engine/test_condition_lifecycle.py
tests/engine/test_direct_scenario_deployment.py
tests/engine/test_elevation_proving_battlefield.py
tests/engine/test_event_wire_visibility_contract.py
tests/engine/test_grid_pathfinding.py
tests/engine/test_items_inventory_equipment.py
tests/engine/test_manual_11_grid_tiles_terrain_movement.py
tests/engine/test_objective_state.py
tests/engine/test_runtime_reset.py
tests/engine/test_senses_light_stealth.py
tests/engine/test_spatial_effects.py
tests/engine/test_spell_families.py
tests/engine/test_tile_surface_contract.py
tests/engine/test_traversal_connectors.py
tests/engine/test_world_edge_identity_and_elevation.py
tests/manual/test_08_world_model_and_movement.py
tests/manual/test_17_encounters_turns_controllers.py
```

This union prevents unchanged-but-still-governed Slice 3.1 files from
disappearing merely because Slice 3.3 did not touch them. Conversely, files
listed by the old Slice 3.1 manifest but later classified as deprecated,
server/editor, inactive content packaging, SDK/cross-language, generated, or
otherwise excluded by the amendment do not enter the final active manifest.

It excludes Markdown governance, itself, all excluded runtime/toolchain files,
and unrelated dirty files. Duplicate paths across the Slice 3.1 seed, Slice
3.3 manifest, and Slice 3.4/3.5 additions are emitted exactly once in sorted
lexicographic order. Every member is hashed from its current final raw bytes,
not copied from an earlier manifest. The ledger binds this plan, all governing
hashes, final manifest hash, exact
commands, selectors, node-set algorithm/count/hash, timings, failures and
repairs, exclusions, deletions, and review verdicts.

Do not infer manifest membership from raw `git status`.

### 8.5 Independent implementation review

After the manifest and ledger are frozen, obtain two independent reviews of
the exact same candidate hashes:

1. correctness/executability review covering geometry, content authorship,
   height/channels, events/light, round-trip/rebuild, deletion gates, and test
   sufficiency; and
2. anti-slop review covering duplicate authority, unnecessary abstraction,
   compatibility residue, private/source-layout tests, scope creep, and dead
   plumbing.

Any code or test repair invalidates both approvals. Update the manifest and
ledger, rerun affected/full gates, and obtain both reviews again.

## 9. Stop conditions

Stop and report instead of improvising if:

- the accepted Slice 3.3 hashes or 612-node baseline do not match;
- an active WallTorch caller exists outside the frozen inventory or lacks
  enough evidence for exact placement facts;
- the control-room row is not accepted;
- CliffFace or WallTorch appears to require a second placement authority;
- same-side nonoccupying coexistence or opposing-side occupancy fails in the
  accepted GridMap primitives;
- an event/cache/light/senses/replay framework change appears necessary;
- a generic materializer, registry, adapter, serializer, or compatibility
  facade appears necessary;
- a requested edit enters an excluded file or Phase 4 entity occupancy;
- a test would need private state, source-text coupling, call-count mocks, or
  timing sleeps; or
- any active selector disappears, is renamed, or changes subject without an
  explicit reviewed replacement ledger.

## 10. Completion definition

Phase 3 is complete only when all of the following are true:

1. the proving cliff is a real explicit `(11,5):WEST:[0,2)` object, never an
   elevation inference;
2. every active WallTorch is a real explicit nonoccupying boundary attachment
   with authored side/base/orientation;
3. cliff and WallTorch content has one direct active identity/construction
   path each;
4. real-content tests prove height/channel independence, same-side attachment
   coexistence, opposing occupants, outer contact, light following,
   Pydantic round-trip, complete-set cold rebuild, and exactly one completed
   `WorldInitializedEvent` per bootstrap;
5. accepted event, cache, light, reducer, movement-step, and turn-start
   responsibilities remain intact;
6. all Section 14 active gameplay references are zero, with retained
   diagnostic names explicitly classified;
7. the final active collection contains the accepted 612 nodes plus only the
   two authorized Slice 3.4 nodes, unless a reviewed ledger explains an exact
   difference;
8. all focused, capability, spell, architecture, locality, and complete active
   lanes pass;
9. the final manifest verifies every governed active member with zero hash
   mismatches; and
10. independent correctness and anti-slop reviewers approve that exact final
    candidate.

Only then may the supervisor mark Phase 3 complete and hand the master
migration to Phase 4.
