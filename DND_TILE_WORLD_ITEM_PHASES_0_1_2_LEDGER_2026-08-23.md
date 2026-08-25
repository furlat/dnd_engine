# Tile / GridMap / WorldItem Phases 0–2 implementation ledger

Status: Phases 0, 1, and 2 implemented; final focused and collecting gates recorded below.

Authoritative plan: `DND_TILE_WORLD_ITEM_PHASES_0_1_2_IMPLEMENTATION_PLAN_2026-08-23.md`
SHA-256: `8cedc4e437d1a5c3bd1c02e4db6fbfbcc04fefe7768f44c97671837bcf0adeb2`

Frozen prerequisite SHAs:

- `DND_TILE_WORLD_ITEM_VERTICAL_BOUNDARY_MIGRATION_PLAN_2026-08-17.md`:
  `01b0d5aa27b7617666d85da3e167da9d4b59d21b95f5073b41eb25821bdcde77`;
- `unified_vision_light.md`:
  `3c9c58483440640837bc38fdaa6b624f358e1098c9a957f65923cd64f83a270b`.

## Baseline commands and results

All commands below were run from the repository root with the checked-in
`.venv` runtime. The node hashes are SHA-256 of the sorted newline-joined
pytest node IDs, excluding collection diagnostics.

| Lane | Command | Result |
| --- | --- | --- |
| Complete collection | `./.venv/bin/pytest --collect-only -q` | exit 2; 1,274 nodes; 105 blocked modules |
| Complete node set | same command | sorted node SHA `da2c0d74324640e5709782d9ffbbb9cfb437d9e01444cb0b7350b9f6090c66bb` |
| Focused Phase-0 lane | `./.venv/bin/pytest -q` over the 13 modules listed below | exit 0; 240 passed in 46.19s |
| Focused node set | same modules with `--collect-only -q` | 240 nodes; sorted node SHA `5056813558729a03cbc2e1c3f3c38475ab423d1bf702d0a661f3fa0c49b3479d` |

The complete collection had these normalized blocked signatures. Counts are
blocked modules, not test nodes:

| Count | Signature |
| ---: | --- |
| 57 | `ModuleNotFoundError: No module named 'dnd.content_system'` |
| 15 | `ModuleNotFoundError: No module named 'server'` |
| 6 | `ModuleNotFoundError: No module named 'dnd.classes.barbarian_progression_definitions'` |
| 4 | `ModuleNotFoundError: No module named 'dnd.classes.progression_definitions'` |
| 3 | `ModuleNotFoundError: No module named 'dnd.classes.sorcerer_progression_definitions'` |
| 3 | `ModuleNotFoundError: No module named 'dnd.core.content.runtime'` |
| 3 | `ModuleNotFoundError: No module named 'dnd.monsters.bestiary_content'` |
| 3 | `ModuleNotFoundError: No module named 'dnd.monsters.circus_fighter'` |
| 1 | `ModuleNotFoundError: No module named 'devtools'` |
| 1 | `ModuleNotFoundError: No module named 'dnd.core.content.registry'` |
| 1 | `ModuleNotFoundError: No module named 'dnd.scenarios.encounter_catalog'` |
| 4 | `FileNotFoundError: content_data/ledgers/neuroclient_authored_item_visuals.json` |
| 2 | `ImportError: dnd.presentation.EquippedVisualPolicy` |
| 2 | `ImportError: dnd.core.content.origin_features.OriginCapability` |

The complete collecting output is reproducible from the command above; the
sorted node hash and signature table are the comparison ledger. No blocked
module was removed from the collecting surface.

## Focused Phase-0 capability lane

The exact collecting/runnable modules were:

- `tests/engine/test_grid_pathfinding.py`;
- `tests/engine/test_world_edge_identity_and_elevation.py`;
- `tests/engine/test_elevation_performance_contract.py`;
- `tests/engine/test_items_inventory_equipment.py`;
- `tests/engine/test_action_discovery.py`;
- `tests/engine/test_spatial_effects.py`;
- `tests/engine/test_direct_spatial_effect_materialization.py`;
- `tests/engine/test_senses_light_stealth.py`;
- `tests/engine/test_event_lifecycle.py`;
- `tests/engine/test_event_wire_visibility_contract.py`;
- `tests/engine/test_objective_state.py`;
- `tests/engine/test_direct_scenario_deployment.py`; and
- `tests/engine/test_runtime_reset.py`.

These cover grid/path/world-edge, inventory/equipment/action discovery,
spatial effects and anchors, sensory/light/stealth, objective event/wire
behavior, authored battlefield/bootstrap, runtime reset/clear, and existing
elevation/performance contracts.

## Surface-authoring ledger

The production AST inventory found seven `Tile.create` call sites and no
direct `Tile(...)` calls. `GridMap.create_rectangle` is the shared authored
constructor used by arena/runtime bootstrap; its callers are recorded below.
The Phase-1 crosswalk is explicit and does not infer a surface from a sprite.

| Owner | Current authored purpose | Phase-1 surface |
| --- | --- | --- |
| `dnd/core/base_tiles.py::floor_factory` | ordinary floor | stone base, no layers |
| `dnd/core/base_tiles.py::dark_floor_factory` | ordinary floor with dark illumination | stone base, no layers; darkness remains illumination |
| `dnd/core/base_tiles.py::wall_factory` | solid wall Tile mechanics | stone base, no layers; intrinsic solid-cell mechanics remain |
| `dnd/core/base_tiles.py::water_factory` | water support surface | water base, no layers |
| `dnd/core/base_tiles.py::difficult_terrain_factory` | difficult movement terrain | earth base, no layers |
| `dnd/core/gridmap.py::set_tile` | generic authored/test tile | explicit caller surface; no production default |
| `dnd/core/gridmap.py::create_rectangle` | rectangular authored/test map | explicit caller surface; no production default |

`dnd/maps/arena_layout.py` and `dnd/runtime_reset.py` call
`GridMap.create_rectangle`; their authored meaning is ordinary stone floor
unless a later explicit tile replacement supplies another surface. Tests and
all other constructors must pass an explicit test-appropriate surface after
the required-field cut.

## Object-location caller ledger

The following Phase-0 capability families were found and are the migration
worklist. The old flat authority is intentionally retained only until the
Phase-2 activation cut.

| Capability | Current owners/callers | Phase-2 disposition |
| --- | --- | --- |
| Flat storage and commands | `dnd/core/gridmap.py` | replace both flat dictionaries with Tile bands plus one reverse placement map |
| Neutral coordinate hooks | `dnd/core/base_block.py`, `dnd/blocks/base_item.py` | promote `get_position`; remove floor authority from inherited position/tile UUID |
| Item placement/destruction/equip | `dnd/blocks/base_item.py`, `dnd/blocks/inventory.py`, `dnd/blocks/equipment.py` | use GridMap placement/query commands and existing item lifecycle |
| Entity loot/drop/displacement | `dnd/entities/entity.py` | capture committed placement; validate floor fallback before domain commit |
| Item-location facts | `dnd/core/events/item_events.py` | replace FLOOR `tile_uuid`/`position` with exact `world_placement` |
| World snapshots | `dnd/core/events/world_events.py`, `dnd/content/scenarios/battlefield_builders.py` | serialize exact object placement |
| Anchored conditions | `dnd/spatial/area_conditions.py`, `dnd/spells/evocation.py` | consume departure/arrival placement facts |
| Perceivability | `dnd/core/base_block.py`, `dnd/blocks/sensory.py` | neutral `get_position` and exact placement-backed object evidence |
| Attached lights | `dnd/spells/evocation.py`, `dnd/items/torches.py`, `dnd/core/gridmap.py` | resolve location from GridMap; delete private wall-torch coordinate |
| Destruction/spill | `dnd/items/environment_interactables.py`, `dnd/items/environment_content.py` | snapshot committed placement before terminal removal |
| Runtime clearing | `dnd/runtime_reset.py`, `dnd/core/gridmap.py::clear/reset` | terminal cleanup once, then clear bands and reverse placements |
| Authored maps/actions | `dnd/content/scenarios/battlefield_builders.py`, `dnd/content/scenarios/scenario_compatibility.py`, `dnd/maps/arena_layout.py`, `dnd/actions/standard.py`, `dnd/items/environment.py` | use the single command/query family |

## Event-order baseline

The focused public lifecycle lane passed before edits. Its stable event
contracts are the Phase-2 comparison points: existing spatial place/remove
facts; item FLOOR/inventory/equipment/destroyed location facts; object-anchor
spatial-effect children; attached-light children; world initialization; and
perceivability sensory deltas. The Phase-2 tests must compare event type,
causal parent, position fields, item location, and child facts—not private
dictionary layout or method names.

The Phase-2 event matrix is frozen from the plan: initial placement carries a
new exact placement; relocation departure carries the old placement and the
destination in `old_position`; relocation arrival carries old and new exact
placements; same-XY orientation/state change carries old and current
placement; terminal removal carries old placement only. Item FLOOR facts carry
only the committed placement.

## Phase-0 exit gate

This ledger, the complete collecting command/output, the focused passing lane,
the blocked-signature table, and the surface/caller crosswalk constitute the
reviewable Phase-0 baseline. No production behavior or test expectation was
changed in Phase 0.

## Phase-1 and Phase-2 implementation record

Phase 1 added dependency-leaf `Material`, `SurfaceLayer`, and `TileSurface`
values; made Tile surface required; migrated every active Tile/create-rectangle
caller to an explicit surface; added in-place surface replacement and complete
Tile/world surface after-values; and added strict public surface/placement tests.

Phase 2 replaced both flat object indexes with GridMap's single
`_object_placements` authority and Tile-owned private center/four-boundary band
storage. It added provider-owned placement capabilities, strict immutable
`WorldObjectPlacement` snapshots, public center/boundary/edge queries,
read-only candidate validation, explicit place/move/orient/remove commands,
immutable locality diagnostics, atomic preflight and lifecycle facts, and all
item/inventory/entity/anchor/light/chest/feast/snapshot/deprecated-caller
migrations. `BaseItem.tile_uuid`, implicit `place_object` movement,
`clear_location` switches, object spatial `object_map_char`, and XY-only world
object snapshots are absent. Tile replacement/rectangle/elevation/clear guards
reject live owners before mutation, and terminal cleanup remains one-shot.

## Intermediate / pre-review verification

| Lane | Result |
| --- | --- |
| Focused Phase-0 lane plus `tests/engine/test_tile_surface_contract.py` | 249 passed in 50.21s |
| `tests/engine/test_spell_families.py` | 60 passed in 21.03s |
| Focused collected node set | 249 nodes; sorted node SHA `702d60f10216196f9f9a718e7c1252e3f9d668d74d5f3c2eb56ca3631538ad18` |
| Architecture/dependency suite | 42 passed in 20.17s |
| `./.venv/bin/python -m compileall -q dnd deprecated tests` | passed |
| `git diff --check` | passed; only existing LF/CRLF warnings |
| Full collection | exit 2; 1,283 nodes; 105 blocked modules |

The full collecting blocked-module count and normalized exception families are
unchanged from the Phase-0 baseline; the node increase is the nine explicitly
added public placement-contract tests. The full collecting command remains
blocked by the pre-existing missing content/server/progression modules,
missing visual-ledger file, and pre-existing presentation/origin imports listed
in the baseline table. No blocked collecting module was removed or masked.

Repository deletion-gate searches are clean for `_object_positions`,
`_objects_by_position`, BaseItem `.tile_uuid`, `clear_location`,
`clear_object_location`, `object_map_char`, `get_all_object_positions`,
`_wall_torch_position`, and dynamic/late/TYPE_CHECKING imports in the new
placement/surface leaves. The three plan documents were not edited.

## Final verification (latest supervised rollback-order correction)

The latest supervised correction remains inside the approved Phase-0–2 scope.
It moves bounded light snapshots into the rollback guard after the complete
directional settlement and immediately before local light recomputation. The
new public regression covers two overlapping lights, a removed saved
directional optical wall, and an unchanged farther center-optics provider that
throws during the later light's FOV; the failed rebuild restores public
placement/topology/revisions/events and the surviving light's exact resolved
field.

The earlier bounded implementation retains these verified properties:
boundary side and orientation remain separate committed values; center
placements require Tile support height while boundary base height remains
independent; place/move/orient return the committed immutable placement;
rebuild uses only the old/new placement-band union, stages opposite-edge
collisions separately from authoritative anchor-side membership, restores
directional/optical/illumination mechanics, and proves the public neighbor
query round trip. Object commands restore exact bands, reverse placement, and
border snapshots on provider failure. WallTorch cleanup preserves the outer
causal parent and previous blocker mechanics. Equipment fallback admission now
uses the Inventory-compatible sequential weight shadow before any equipment,
ownership, floor, or event mutation. The neutral object range seam uses typed
`get_position()` only, and every deprecated `create_rectangle`/`set_tile`
caller uses explicit semantic surface and current blocking arguments.

Additional public gates now cover the exact object event matrix, independent
boundary/orientation and support-height rules, nonoccupying coexistence,
rebuild success/rejection and bijection, failed drop/equipment nonmutation,
unplaced range, surface/condition/illumination preservation, WallTorch and
Continual Flame relocation/removal, chest spill cardinality, and Heroes' Feast
floor-fact cardinality.

| Gate | Result |
| --- | --- |
| Exact rebuild regression subset | 7 passed, 23 deselected; 5.46s |
| Focused Phase-0/1/2 capability lane plus Tile contract | 278 passed; 61.56s |
| Full spell-family lane | 62 passed; 25.24s |
| Architecture/dependency suite after removing the blocked mapeditor source-layout gate | 42 passed; 25.06s |
| Exact new Tile correction regressions | 29 passed; 6.47s |
| Exact new equipment fallback regression | passed in focused lane |
| Exact WorldInitialized identity/surface regression | passed in focused lane |
| Exact terminal-hook diagnostic regression | passed in Tile lane |
| `./.venv/bin/python -m compileall -q dnd deprecated tests` | passed |
| `git diff --check` | passed; existing LF/CRLF warnings only |
| Direct `set_tile`/`create_rectangle` stale-kw AST scan | `[]` |
| Complete collection | exit 2; 1,314 tests collected; 105 pre-existing collection errors; sorted node SHA `1a62a543af12b8178a4881d0815e70ad533d7263e833108caab11d7f9447dfb6` |

The complete collection remains blocked by the same missing content/server/
progression/runtime modules, visual-ledger file, and pre-existing presentation
and origin imports recorded in the baseline; no blocked lane was removed or
masked. The exact final plan SHA remains
`8cedc4e437d1a5c3bd1c02e4db6fbfbcc04fefe7768f44c97671837bcf0adeb2`.

The frozen external-review manifest contains 88 scoped Python/JSON files; its
hash is regenerated after the latest test/edit pass:
`DND_TILE_WORLD_ITEM_PHASES_0_1_2_IMPLEMENTATION_MANIFEST_2026-08-23.json`,
SHA-256
`34de6db66c80d336044ab90abd13e284971722551d4d2018678a12808971aad9`.

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
