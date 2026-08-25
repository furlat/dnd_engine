# Phase 3.0 Ordered-Side Implementation Ledger

Status: REVOKED AS IMPLEMENTATION AUTHORITY. This historical ledger mixed the
active in-process mechanics cut with deprecated server/editor, SDK,
cross-language generation, and transport-only tests. It is retained only as
review history. Luna must use the separately reviewed active-runtime Slice 3.2
ledger and must not implement, regenerate, compile, or validate any excluded
artifact named below.

Date: 2026-08-24
Mode: read-only Phase 3.0 pre-edit review
Implementation authority: not granted

## Verdict

**STOPPED.** The legacy `DoorObject` / `environment.door` family is a center-global blocker with no authored boundary owner side. Existing maintained routes and public tests prove only center-cell behavior. Assigning a side would be speculation. Guidance §7 requires each row to be resolved or escalated before the boundary hard cut.

No production code, tests, documents other than this ledger, Git state, or dependency files were edited during this review.

## Governing binds

| Artifact | SHA-256 |
|---|---|
| `/mnt/c/users/tommaso/documents/dev/dnd_engine/DND_TILE_WORLD_ITEM_PHASE_3_ORDERED_SIDE_IMPLEMENTATION_GUIDANCE_2026-08-24.md` | `560dbef81b39c43657d32087c1e7ab85c7d08ffa790df780f631358176994326` |
| substantive Phase 3 guidance revision | `495914ec28df82b553f23347f2a29eb9be7764f21039e5619e083c1a20b4e7de` |
| `/mnt/c/users/tommaso/documents/dev/dnd_engine/DND_TILE_WORLD_ITEM_VERTICAL_BOUNDARY_MIGRATION_PLAN_2026-08-17.md` | `73335294139bdc81306f17381afe22f27fb94c9c48bcf07c1312eb9eeefafe63` |
| substantive master revision | `46de9f570fb59fd8c9e8a105a3a699287a7881c93c880827d804faefad9c7f2d` |
| `/mnt/c/users/tommaso/documents/dev/dnd_engine/unified_vision_light.md` | `3c9c58483440640837bc38fdaa6b624f358e1098c9a957f65923cd64f83a270b` |
| `/mnt/c/users/tommaso/documents/dev/dnd_engine/DND_TILE_WORLD_ITEM_PHASES_0_1_2_SIDE_GEOMETRY_CORRECTION_PLAN_2026-08-24.md` | `ae189282687fdcb7baa88ca3b393af593c6db345029a89da9cfcc36b76f021c1` |
| substantive correction revision | `d7d423408fd79796c53d2ffac1b95b536e3b53ae6a57416ac6143391949ec33f` |
| revoked Phase 3 guidance | `5644d79ed9149b6a028bc34725c0aa01c60ee26b63abe3b2fb5944063fb7d58a` |
| accepted Phase 0–2 manifest | `3eb3b75864cda77052675e93b82f43bdf89c5177930a4fa4518db3884900d98c` |
| Phase 0–2 correction ledger | `cca4f33e324b47accaf01ecb794c1c4325595dd6e2b53adf99252e9e538cf5c1` |
| `/mnt/c/users/tommaso/documents/dev/dnd_engine/AGENTS.md` | `fcc5dd1e15bae2ff86a7203f42b0c55de4d51dd0d93bc3a3ae059b7e58ee39b1` |
| `/mnt/c/users/tommaso/documents/dev/dnd_engine/HOW_TO_TEST.MD` | `96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013` |

The complete `HOW_TO_TEST.MD` was read before the authorized baseline work.

## Accepted manifest verification

Manifest: `/mnt/c/users/tommaso/documents/dev/dnd_engine/DND_TILE_WORLD_ITEM_PHASES_0_1_2_IMPLEMENTATION_MANIFEST_2026-08-23.json`

- Declared members: 90
- Actual scoped members: 90
- Duplicate members: 0
- Manifest member set equals current scoped set: true
- Missing members: `[]`
- Extra members: `[]`
- Member hash mismatches: `[]`

Manifest algorithm: scoped members are the sorted lexicographic set of modified or untracked `.py`/`.json` paths from Git status, excluding the manifest and Markdown governance files; each member hash is SHA-256 of its exact raw bytes.

## Collection freeze

Command:

```text
./.venv/bin/pytest --collect-only -q -p no:cacheprovider
```

Duration: 22.17s. Exit status: 2, caused by the accepted collection blockers below.

| Set | Count | SHA-256 |
|---|---:|---|
| sorted collected selector set | 1,318 | `d5a34d1de6683d8145a4895233f0348249a1e7d7d89fd8478c976c6edc5b404c` |
| sorted collecting-module set | 113 | `8a609e8b85157ad9c1db2e085c4f3ca82a6bcb9e4abc84ee4e278da4912873bb` |
| sorted blocked-module set | 105 | `ff2ebd76d5772a93dff7723f9869316eb92fe05b10d7b916a6465005ef6bf531` |
| sorted collecting/blocked union | 218 | `003720b0a00ac1ab53af1aabdebaeaf10b324b7e7a7e92b0d25e1e702e6ef7a6` |

Collection algorithm: normalize each pytest collected node/module/error set, sort lexicographically, join with one newline and no trailing newline, then SHA-256 the UTF-8 bytes. The unique normalized error-signature set hash is `6bfee118f232e569cc28ed3d12fccc775b806401287b3ba2a69c8a8ed38cfb8c`; the sorted `count<TAB>signature` representation hash is `ef1ee83014de3e077b6539367d7cdb2f4cb9c563cda4d31c21d80e0aa6289f8c`.

Normalized blocked signatures:

- 57 `ModuleNotFoundError: No module named 'dnd.content_system'`
- 15 `ModuleNotFoundError: No module named 'server'`
- 6 `ModuleNotFoundError: No module named 'dnd.classes.barbarian_progression_definitions'`
- 4 `ModuleNotFoundError: No module named 'dnd.classes.progression_definitions'`
- 3 `ModuleNotFoundError: No module named 'dnd.classes.sorcerer_progression_definitions'`
- 3 `ModuleNotFoundError: No module named 'dnd.core.content.runtime'`
- 3 `ModuleNotFoundError: No module named 'dnd.monsters.bestiary_content'`
- 3 `ModuleNotFoundError: No module named 'dnd.monsters.circus_fighter'`
- 4 `FileNotFoundError: content_data/ledgers/neuroclient_authored_item_visuals.json`
- 2 `ImportError: dnd.presentation.EquippedVisualPolicy`
- 2 `ImportError: dnd.core.content.origin_features.OriginCapability`
- 1 `ModuleNotFoundError: No module named 'devtools'`
- 1 `ModuleNotFoundError: No module named 'dnd.core.content.registry'`
- 1 `ModuleNotFoundError: No module named 'dnd.scenarios.encounter_catalog'`

## Authorized starting lanes

The 14-module capability command was:

```text
./.venv/bin/pytest -q -p no:cacheprovider tests/engine/test_grid_pathfinding.py tests/engine/test_world_edge_identity_and_elevation.py tests/engine/test_elevation_performance_contract.py tests/engine/test_items_inventory_equipment.py tests/engine/test_action_discovery.py tests/engine/test_spatial_effects.py tests/engine/test_direct_spatial_effect_materialization.py tests/engine/test_senses_light_stealth.py tests/engine/test_event_lifecycle.py tests/engine/test_event_wire_visibility_contract.py tests/engine/test_objective_state.py tests/engine/test_direct_scenario_deployment.py tests/engine/test_runtime_reset.py tests/engine/test_tile_surface_contract.py
```

Results:

- Capability lane: 282 passed, 58.22s.
- `./.venv/bin/pytest -q -p no:cacheprovider tests/engine/test_spell_families.py`: 62 passed, 23.95s.
- `./.venv/bin/pytest -q -p no:cacheprovider tests/architecture`: 42 passed, 23.96s.
- No focused-lane failures.
- Collection was the only authorized failure and was caused by the normalized blockers above.

## Section 14 caller/deletion inventory

### Tile intrinsic/object-derived directional borders

Declarations and helpers are in `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_tiles.py:107-484`: intrinsic `border_*`, `optical_border_*`, `propagation_border_*`, object-derived directional fields, `_intrinsic_border`, `_derived_border`, `set_intrinsic_border`, `set_object_border`, `allows_direction`, and `allows_directions`.

Active callers are in `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:760,850-882,1580-1740,3454,4507`, `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/scenarios/battlefield_builders.py:854-869`, and `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/scenarios/scenario_compatibility.py:406`.

Editor/deprecated callers are in `/mnt/c/users/tommaso/documents/dev/dnd_engine/deprecated/server_deprecated/mapeditor_support.py:752,1280-1302`, `/mnt/c/users/tommaso/documents/dev/dnd_engine/deprecated/server_deprecated/world_projection.py:718-741`, and `/mnt/c/users/tommaso/documents/dev/dnd_engine/deprecated/server_deprecated/subjective_parity_diagnostics.py:388-399,467`.

Test callers are in:

- `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_action_cost_and_position_commit.py:222-229`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_elevated_jump_transaction.py:358-368`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_encounter_apis.py:463,649` (blocked module)
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_grid_pathfinding.py:296,308,435`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_manual_11_grid_tiles_terrain_movement.py:124`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_move_settlement.py:96-108`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_senses_light_stealth.py:217,797-812,839,853,860`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_tile_surface_contract.py:1207-1375`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_traversal_connectors.py:1568-1575`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_world_edge_identity_and_elevation.py:138`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/manual/test_08_world_model_and_movement.py:153`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/manual/test_149_remaining_legacy_contract.py:220` (blocked module)

### BaseItem directional fields and APIs

The twelve fields and `_blocks_direction`, `_set_directional_blocking`, `blocks_directional_*`, `set_directional_blocking`, and bulk setter are in `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/base_item.py:130-429`. DirectionalWall and DirectionalDoor construct and mutate these values in `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/environment.py:118-375`. Active GridMap dispatch is `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:1573-1577`; tests include `test_grid_pathfinding.py`, `test_manual_11_grid_tiles_terrain_movement.py`, and blocked `test_directional_environment_legacy_contract.py`.

### BaseBlock hooks and objective directional structure

Neutral hooks `get_objective_directional_structural_channels` and `blocks_directional_movement/optics/propagation` are declared in `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_block.py:174,380-396`. BaseItem overrides and structure projection are in `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/base_item.py:255-397`; GridMap consumes them in `gridmap.py:760-816,1573-1577`.

`ItemDirectionalStructureState` is `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/items.py:35-42`; `ItemState`/observation fields are in `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events/item_events.py` and `dnd/types/items.py`. Deprecated projection callers include `/mnt/c/users/tommaso/documents/dev/dnd_engine/deprecated/server_deprecated/player_replication/world_projection.py`, `world_projection.py`, and `subjective_parity_diagnostics.py`.

### Authored directions, scenario duplicate, and world state

`blocked_directions` declarations/parameters/defaults are in `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/environment.py`, `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/environment_content.py:123-137,889-915`, `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/environment_item_builders.py:33-61`, `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/scenarios/battlefield_definitions.py:54`, `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/scenarios/battlefield_builders.py:120-215,510-545`, and `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/maps/arena_layout.py:37-44,97,112`.

The duplicate scenario topology implementation is `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/scenarios/scenario_compatibility.py:285-429`.

`WorldTileState.movement_open`, `optical_open`, and `propagation_open` are `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events/world_events.py:56-79`; battlefield serialization reads the old Tile border fields at `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/scenarios/battlefield_builders.py:836-869`.

### Spatial event directional fields

Authoritative `SpatialChangeEvent.directional_position`, `directional_directions`, `directional_channels`, and directional block maps are `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events/world_events.py:604-609`, with constructors through that module. Producers include `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/base_item.py:449-505`, `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py`, and `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions/standard.py:1163-1168`. `SensesUpdateHint` directional endpoint/channel hints remain bounded nonauthoritative candidates for later migration.

### Door, barrier, generated, and perceivability callers

`DoorObject`, `OpenDoorAction`, `CloseDoorAction`, `door_recipe`, `build_door`, and `environment.door` catalog declarations are in `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/environment_interactables.py:33-177`, `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/environment_content.py:320-347,925-974`, `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/environment_item_builders.py:67-79`, and `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/authored_item_builders.py:529,654-655`.

Editor callers are `/mnt/c/users/tommaso/documents/dev/dnd_engine/deprecated/server_deprecated/mapeditor_support.py:903-940,1359-1364`. Generated callers include `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/content/icon_bindings_generated.py:39-43,303`, deprecated TypeScript generated contracts/projection files, and deprecated content ledgers. Blocked test callers include `test_encounter_apis.py`, `test_legacy_reactive_reaction_coverage.py`, and `test_134_stackable_usable_item_legacy_contract.py`; collecting direct callers include `test_senses_light_stealth.py` and `test_items_inventory_equipment.py`.

`_barrier_positions_cache` is initialized/cleared in `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:173,367,2868,4561`; global `get_barrier_positions` is `gridmap.py:4496-4513`, consumed by `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/aoe.py:221` and `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entities/entity.py:6962`. Deprecated event-server callers also remain.

No active `is_perceivable_by` definition/use was found. Only deprecated projection modules and `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/manual/test_135_stealth_lighting_legacy_contract.py` reference it.

## Authored crosswalk

| Family | Live evidence | Proposed exact disposition |
|---|---|---|
| Standard wall | Arena and battlefield builders explicitly pass WEST; standard Tile support material is STONE | One boundary occupant per row, owner WEST, `[0,2)`, STONE/WALL, all closed channels |
| Standard directional door | Arena/battlefield builders explicitly pass WEST; open state is separate | One boundary occupant per row, owner WEST, `[0,2)`, WOOD/DOOR; open retains placement with empty channels |
| Proving cliff | Current proving layout records only height/notable positions at `(11,5)`; no object provider exists | Explicit provider at `(11,5)`, owner WEST, `[0,2)`, STONE, MOVEMENT only |
| Standard WallTorch rows | `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/maps/arena_layout.py:150-154` mounts `(14,1)` and `(14,13)` without side data | EAST owner, WEST orientation, `[1,2)`, nonoccupying |
| Control-room WallTorch | `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/scenarios/battlefield_builders.py:675-676` mounts `(4,10)` without side data | Unresolved; explicit side required before Slice 3.4 |
| Crate | Authored blocker has no movement/optical/propagation blocking | Center, nonoccupying |
| Boulder | Authored definitions/builders block movement and propagation | Center occupant, extent 1 |
| Barricade | Authored definitions/builders block all three channels | Center occupant, extent 1 |
| Oil Barrel | Dedicated class blocks movement/propagation and spills oil on destruction | Center occupant, extent 1; preserve spill behavior |

## Caller-level no-side door ledger

### DirectionalDoor family

The exact owner side(s) are the caller-supplied `blocked_directions` tuple. Standard arena, standard hazards, two-barrier, and proving routes all explicitly use WEST. Direct manual/projection tests explicitly use EAST, WEST, NORTH, or a parameterized side. The legacy default in `DirectionalWallParameters`, `DirectionalDoorParameters`, and `directional_door_recipe` is the explicit four-direction tuple; if used, it requires one object/UUID per side in canonical order.

### DoorObject / environment.door family — STOP

| Caller | Maintained evidence | Owner side |
|---|---|---|
| `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/environment_interactables.py:137` | Center-global movement/optical/propagation fields | **STOP — none authored** |
| `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/environment_content.py:320-347` | Factory accepts only `is_open` | **STOP** |
| `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/environment_item_builders.py:67-79` | Direct builder has no side parameter | **STOP** |
| `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/authored_item_builders.py:529,654-655` | Authored item accepts only `is_open` | **STOP** |
| `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/environment_content.py:925,974` | No-side recipe/constants | **STOP** |
| `/mnt/c/users/tommaso/documents/dev/dnd_engine/deprecated/server_deprecated/mapeditor_support.py:903-940,1359-1364` | Save/load persists position/open state only | **STOP** |
| `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_senses_light_stealth.py:701-729` | Places at `(2,0)` and tests center transition/FOV/propagation | **STOP** |
| `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_items_inventory_equipment.py:1043-1070` | Places authored door at `(1,0)` and tests actions | **STOP** |
| Blocked legacy tests at `tests/manual/test_legacy_reactive_reaction_coverage.py:923,1036` and `tests/manual/test_134_stackable_usable_item_legacy_contract.py:506-512,685` | Center placements and open/close behavior | **STOP** |
| `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/content/icon_bindings_generated.py:39-43,303` | Generated content/action identity only | Inherits unresolved `environment.door` status |

Required product choice: reauthor every maintained route with exact boundary side(s), or formally retire the center-door family. A side cannot be inferred from the center coordinate.

Additional live contradiction: `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/scenarios/battlefield_builders.py:160-165` changes an initially open standard door’s authored WEST tuple to `()`. Authored WEST ownership must remain while current blocked channels become empty.

## Section 9 consumer classification

- **MOVEMENT:** GridMap transitions/pathing, diagonal bridges, collision reporting, voluntary/forced movement, and movement spell consumers. Evidence: `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:1967`, `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entities/entity.py:5938`, `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions/standard.py:966,1128,1317,1607`.
- **OPTICAL/contact.visual:** `can_optical_transition`, FOV, light-source FOV, and `SpatialSensesSystem.recompute_observer`. Evidence: `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:2028,3594,4147`, `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/sensory.py:653-806`. Visible-target rules read `PerceivedContact.visual`.
- **PROPAGATION/line of effect:** propagation transitions/FOV/filtering, raycast, AoE, jump/physical reach, and nonvisual senses. Evidence: `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:2045,3480,4377-4459`, `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/aoe.py:141,221`, `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entities/entity.py:3076,5091`, `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/sensory.py:313,719`.
- **Typed-contact existence:** `SpatialSensesSystem` creates entity/object contacts; awareness and action discovery read `senses.entities` and `senses.objects`. Evidence: `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/sensory.py:721-806`, `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entities/entity.py:5623-5691`, `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_actions.py:1089`.
- **Scenario compatibility:** `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/scenarios/scenario_compatibility.py:285-429` currently duplicates topology and ignores closed spatial-open objects. It must use the same public MOVEMENT query with `treat_closed_doors_as_interactable=True`; ordinary movement remains unchanged.

## Missing characterization tests

1. Center blocker specs, collision/rejection atomicity, replay, event after-values, and locality.
2. `BoundaryStructure` exact owner/material/extent/channel behavior, including open-door empty channels.
3. Ordered channel-selective movement/optical/propagation and near-side contact reduction.
4. Closed-door scenario compatibility versus a permanently blocking wall.
5. Explicit proving cliff behavior independent of elevation alone.
6. WallTorch explicit side plus attached-light movement/removal/save-load.
7. Item/spatial/world Pydantic round-trip using `boundary_structure` without authoritative directional fields.

No characterization tests were written.

## Exact proposed Slice 3.1 scope

Production:

- `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/environment_content.py`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/authored_item_definitions.py`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/authored_item_builders.py`

Tests:

- `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_tile_surface_contract.py`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_items_inventory_equipment.py`
- `/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_families.py` only for the existing Oil Barrel regression if required.

No GridMap, event-schema, movement, FOV, propagation, door, cliff, or WallTorch hard-cut edits are proposed for Slice 3.1 absent a concrete public center-blocker defect.

## Ledger scope and algorithm

This file is the sole authorized Phase 3.0 durable ledger mutation. It records only the completed read-only evidence above. Its SHA-256 is computed over the exact raw bytes after writing, without normalization or post-hash rewriting.

Unbound ledger SHA-256 placeholder: `UNBOUND_AFTER_WRITE`

## Supervised Slice 3.1 continuation — 2026-08-24

Status: **SLICE 3.1 IMPLEMENTED; STOPPED FOR SUPERVISOR REVIEW.** Slice 3.2
and all later Phase 3 work were not started.

### Governing re-verification and starting bind

The required governing files were rehashed before editing and matched their
bound values:

| Artifact | SHA-256 |
|---|---|
| Phase 3 guidance final | `560dbef81b39c43657d32087c1e7ab85c7d08ffa790df780f631358176994326` |
| Phase 3 guidance substantive revision | `495914ec28df82b553f23347f2a29eb9be7764f21039e5619e083c1a20b4e7de` |
| corrected master | `73335294139bdc81306f17381afe22f27fb94c9c48bcf07c1312eb9eeefafe63` |
| unified vision/light | `3c9c58483440640837bc38fdaa6b624f358e1098c9a957f65923cd64f83a270b` |
| AGENTS.md | `fcc5dd1e15bae2ff86a7203f42b0c55de4d51dd0d93bc3a3ae059b7e58ee39b1` |
| HOW_TO_TEST.MD | `96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013` |
| accepted Phase 0–2 manifest | `3eb3b75864cda77052675e93b82f43bdf89c5177930a4fa4518db3884900d98c` |
| Phase 3.0 ledger starting bind | `f7291a5e99de7584b41bd04201ead14610e28637a1bd8b139e27c1a79ad162ab` |

The accepted Phase 0–2 manifest still declared 90 members and verified with
90 actual scoped members, exact set equality, zero duplicates, and zero member
hash mismatches before Slice 3.1 edits.

### Exact Slice 3.1 changes

Production scope was limited to these four authorized files:

- `dnd/blocks/base_item.py`: added the reusable `WorldItem(BaseItem)` with one
  required frozen `WorldPlacementSpec` field and a truthful
  `get_world_placement_spec()` implementation. No GridMap, event, movement,
  FOV, propagation, schema, or consumer code changed.
- `dnd/content/items/authored_item_definitions.py`: added explicit cold
  `placement_spec` facts to `StaticBlockerDefinition`; authored validation
  requires CENTER and exactly one vertical band. Crate, boulder, and barricade
  rows each provide their own explicit spec; occupancy is not derived from
  blocking flags.
- `dnd/content/items/authored_item_builders.py`: the direct blocker path now
  constructs `WorldItem` and passes the definition-owned spec unchanged.
- `dnd/items/environment_content.py`: the environment blocker factory path
  now constructs `WorldItem` with explicit CENTER specs; OilBarrel reuses
  `WorldItem` with an explicit occupying CENTER spec. Its destruction and oil
  spill implementation was not changed.

The authorized test scope changed only
`tests/engine/test_items_inventory_equipment.py`. Three public tests prove:

1. the direct authored path returns exact immutable CENTER capabilities for
   crate, boulder, and barricade, with the authored movement/optical/
   propagation flags preserved;
2. public placement emits exact placement after-values, permits a
   nonoccupying crate to coexist with a boulder at one center band, places a
   barricade as an occupying center object, and rejects a duplicate boulder
   atomically with no placement-specific spatial fact; and
3. a direct-authored boulder survives public `WorldInitializedEvent` Pydantic
   JSON round-trip and public cold rebuild with exact semantic `ItemState` and
   placement.

No directly necessary export/import file was added. No GridMap or other
out-of-scope production file was edited for Slice 3.1.

### Public test and validation evidence

Commands and final results:

| Command/lane | Result | Duration |
|---|---:|---:|
| focused three Slice 3.1 selectors in `tests/engine/test_items_inventory_equipment.py` | 3 passed, 31 deselected | 4.04s |
| accepted 14-module capability lane | 285 passed | 53.71s |
| `tests/engine/test_spell_families.py` | 62 passed | 22.04s |
| `tests/architecture` | 42 passed | 21.69s |
| `py_compile` on the four edited production modules | passed | — |
| `git diff --check` | passed; existing LF/CRLF warnings only | — |

The capability lane command was the exact Phase 3.0 14-module command, with
the three authorized public tests included through its existing
`test_items_inventory_equipment.py` member. The spell and architecture lanes
were rerun after the final test edit.

The environment-content module remains blocked by the accepted pre-existing
collection dependency gap. The exact read-only import check was:

```text
./.venv/bin/python -c "import dnd.items.environment_content"
```

and produced `ModuleNotFoundError: No module named 'dnd.content_system'`, the
same normalized blocker as 57 existing collection modules. Consequently the
environment factory callables and direct OilBarrel destruction path could not
be executed in this checkout without changing out-of-scope dependency state;
no private factory test, import shim, or spell-scope expansion was added. The
authorized spell lane remained green, and OilBarrel's `_on_destroy` body was
unchanged.

### Final collection freeze and exact selector delta

Command:

```text
./.venv/bin/pytest --collect-only -q -p no:cacheprovider
```

The command exited 2 after 17.64s because of the same 105 accepted collection
blockers. The final sets are:

| Set | Count | SHA-256 |
|---|---:|---|
| sorted collected selector set | 1,321 | `baa12b11304b01234423130708fa4f2e6ef2b533e5cb0eaeda9f65fab0146780` |
| sorted collecting-module set | 113 | `8a609e8b85157ad9c1db2e085c4f3ca82a6bcb9e4abc84ee4e278da4912873bb` |
| sorted blocked-module set | 105 | `ff2ebd76d5772a93dff7723f9869316eb92fe05b10d7b916a6465005ef6bf531` |
| sorted collecting/blocked union | 218 | `003720b0a00ac1ab53af1aabdebaeaf10b324b7e7a7e92b0d25e1e702e6ef7a6` |

Normalized blocked signatures are unchanged: 14 unique signatures with
unique-set SHA-256
`6bfee118f232e569cc28ed3d12fccc775b806401287b3ba2a69c8a8ed38cfb8c` and
sorted signature-count representation SHA-256
`ef1ee83014de3e077b6539367d7cdb2f4cb9c563cda4d31c21d80e0aa6289f8c`.
The counts remain 57 `dnd.content_system`, 15 `server`, 6
`dnd.classes.barbarian_progression_definitions`, 4
`dnd.classes.progression_definitions`, 3
`dnd.classes.sorcerer_progression_definitions`, 3
`dnd.core.content.runtime`, 3 `dnd.monsters.bestiary_content`, 3
`dnd.monsters.circus_fighter`, 4 missing visual-ledger files, 2
`EquippedVisualPolicy` imports, 2 `OriginCapability` imports, and one each for
`devtools`, `dnd.core.content.registry`, and
`dnd.scenarios.encounter_catalog`.

The exact authorized selector delta is three genuinely added selectors:

- `tests/engine/test_items_inventory_equipment.py::test_authored_static_blockers_expose_exact_center_capabilities`
- `tests/engine/test_items_inventory_equipment.py::test_authored_center_blockers_use_public_admission_and_collision`
- `tests/engine/test_items_inventory_equipment.py::test_authored_center_occupant_round_trips_world_state_and_cold_rebuild`

There were no removed selectors and no renamed selectors in Slice 3.1. The
Phase 0 reconciliation is `1,314 - 0 + 7 = 1,321`: the prior accepted Phase
3.0 state had already authorized the earlier `+7`, and Slice 3.1 adds these
three selectors to reach the final count. No collecting or blocked module was
added, removed, or masked.

### Static deletion/prohibited-construct audit

The active-source searches found zero Slice 3.1 occurrences of
`CenterWorldItem`, `BoundaryWorldItem`, registry/factory/facade/cache/index
machinery, reflection/dynamic imports, `TYPE_CHECKING`, custom serialization,
`staged_physical_edge_occupants`, physical-edge staging, opposite-side probing,
`get_boundary_objects_on_edge`, old `WorldEdgeView` fields,
`structural_contributions`, or implicit `orientation=boundary_direction`.
The audit included the edited production/test files and the active `dnd` and
`tests` trees for the deleted/residue symbols. `git diff --check` passed.

### Final Slice 3.1 implementation manifest

Manifest:
`DND_TILE_WORLD_ITEM_PHASE_3_SLICE_3_1_IMPLEMENTATION_MANIFEST_2026-08-24.json`

The manifest uses the exact raw-byte SHA-256 algorithm: its members are the
sorted lexicographic set of modified or untracked `.py`/`.json` paths from
`git status`, excluding this candidate manifest and Markdown governance files;
each member row stores SHA-256 of that member's exact raw bytes. The prior
accepted Phase 0–2 JSON manifest remains a current JSON member under this
literal algorithm. Verification after writing reported:

- declared member count: 94;
- actual scoped member count: 94;
- file-row count: 94;
- duplicate members: 0;
- member-set match: true;
- missing members: `[]`;
- extra members: `[]`;
- member hash mismatches: `[]`; and
- manifest SHA-256: `9dd8adc06df2e5d385ca6f4c5102ca61f5efb7aa42ba641feb4ee3aeace27e9f`.

The increase from the bound 90-member Phase 0–2 manifest is exactly three
newly modified Slice 3.1 production paths plus the already accepted prior
manifest JSON, which is included transparently by the stated candidate
algorithm. No Markdown governance file or manifest self-hash was included.

### Handoff boundary

Slice 3.1 is complete within the authorized scope and is stopped for
supervisor implementation review. The only unresolved evidence is the
pre-existing `dnd.content_system` import blocker described above; resolving it
would require out-of-scope dependency changes. Slice 3.2, walls, doors,
cliffs, WallTorch, GridMap topology/edge derivation, movement/FOV/light/
propagation consumers, sensory reduction, event schemas, scenario
compatibility, and deprecated/generated callers remain untouched.

The continuation SHA is computed over this ledger's exact raw bytes after this
append and is reported in the handoff; it is intentionally not embedded in
the file to avoid a self-referential hash.

## Supervisor gate-closure continuation — 2026-08-24

The requested final Slice 3.1 gates were closed without production-scope
expansion or any Phase 3.2 work.

### Locality diagnostics proof

`tests/engine/test_items_inventory_equipment.py::test_authored_center_placement_diagnostics_are_local`
uses only public `GridMapOperationDiagnostics`. It places the same authored
boulder at `(0, 0)` on a 2x2 map, then repeats it on a 40x40 map after placing
an authored nonoccupying crate at distant `(39, 39)`. The two public
`last_operation_diagnostics` snapshots have identical
`tiles_inspected`, `bands_inspected`, and `bands_replaced` values. No private
Tile band, index, cache, or monkeypatch is read.

### Exact completion-fact proof

The public placement-event assertion now collects the complete lifecycle
records rather than a UUID-keyed dictionary. The three placements produce
exactly 12 matching `SpatialChangeEvent` records: exactly three each at
DECLARATION, EXECUTION, EFFECT, and COMPLETION. It then asserts exactly three
COMPLETION records in placement order, with each exact committed
`WorldObjectPlacement` after-value for boulder, crate, and barricade. This
cannot silently collapse phase records.

The final focused gate was:

```text
./.venv/bin/pytest -q -p no:cacheprovider tests/engine/test_items_inventory_equipment.py -k 'authored_static_blockers_expose_exact_center_capabilities or authored_center_blockers_use_public_admission_and_collision or authored_center_occupant_round_trips_world_state_and_cold_rebuild or authored_center_placement_diagnostics_are_local'
```

Result: `4 passed, 31 deselected in 4.63s`.

### Bootstrap and environment-materializer limitation

The direct authored constructor path is active and publicly tested through
`build_authored_item`. The environment-content path has no active public
materializer in this checkout: importing
`dnd.items.environment_content` fails at its top-level
`dnd.content_system.action_definitions` dependency with the frozen collection
error `ModuleNotFoundError: No module named 'dnd.content_system'`.

The exact missing bootstrap seam is a public battlefield/bootstrap builder
that can materialize a registered environment blocker (or consume a
`WorldObjectState.item`) and register its live provider before public
`rebuild_object_placements`. No such active seam is available within the
authorized Slice 3.1 files, and calling private declaration factories or
adding an import shim would broaden scope. Therefore the existing public
WorldInitialized test remains intentionally limited to Pydantic JSON
round-trip plus public cold rebuild using the live direct-authored boulder;
actual WorldInitialized/bootstrap publication for this blocker is explicitly
**deferred and blocking for Slice 3.3**. No private bootstrap proof was added.

### Final post-gate lanes and collection

After these gate changes, the exact bounded lanes passed:

| Lane | Result | Duration |
|---|---:|---:|
| accepted 14-module capability lane | 286 passed | 56.36s |
| `tests/engine/test_spell_families.py` | 62 passed | 22.81s |
| `tests/architecture` | 42 passed | 22.52s |

The final cache-disabled collection command exited 2 with the same accepted
105 collection blockers after 16.92s:

| Set | Count | SHA-256 |
|---|---:|---|
| sorted collected selector set | 1,322 | `9c67b3e4f95c3054354f04d439428b9360a42021931d506ea73acdb49d61fc3a` |
| sorted collecting-module set | 113 | `8a609e8b85157ad9c1db2e085c4f3ca82a6bcb9e4abc84ee4e278da4912873bb` |
| sorted blocked-module set | 105 | `ff2ebd76d5772a93dff7723f9869316eb92fe05b10d7b916a6465005ef6bf531` |
| sorted collecting/blocked union | 218 | `003720b0a00ac1ab53af1aabdebaeaf10b324b7e7a7e92b0d25e1e702e6ef7a6` |

The 14 normalized blocker signatures remain unchanged, with unique-set SHA
`6bfee118f232e569cc28ed3d12fccc775b806401287b3ba2a69c8a8ed38cfb8c` and
sorted signature-count SHA
`ef1ee83014de3e077b6539367d7cdb2f4cb9c563cda4d31c21d80e0aa6289f8c`.

The final Slice 3.1 selector delta contains four genuinely added selectors:

- `tests/engine/test_items_inventory_equipment.py::test_authored_static_blockers_expose_exact_center_capabilities`
- `tests/engine/test_items_inventory_equipment.py::test_authored_center_blockers_use_public_admission_and_collision`
- `tests/engine/test_items_inventory_equipment.py::test_authored_center_occupant_round_trips_world_state_and_cold_rebuild`
- `tests/engine/test_items_inventory_equipment.py::test_authored_center_placement_diagnostics_are_local`

There were no Slice 3.1 removals or renames. The exact Phase 0
reconciliation is `1,314 - 0 + 8 = 1,322`: the accepted Phase 3.0 state
already accounted for seven prior authorized selectors, and Slice 3.1 adds
these four.

### Final manifest refresh

The candidate manifest was refreshed after the strict authored-type validation
and final test additions. Verification remains 94 declared/actual members,
94 file rows, zero duplicates, exact set match, empty missing/extra sets, and
zero member hash mismatches.

Final candidate manifest SHA-256:
`a4c0d33b6a4966de5c4769e533421b60f456879fb1d80099760e11251b45cc53`.

The only unresolved Slice 3.1 evidence is the explicitly recorded public
environment materializer/bootstrap gap. The implementation and all runnable
authorized gates are stopped here for supervisor review; Slice 3.2 remains
unstarted.

## Supervised anti-slop correction/rebind — 2026-08-24

Applied exactly the two approved deletions from the correctness-reviewed
manifest `a4c0d33b6a4966de5c4769e533421b60f456879fb1d80099760e11251b45cc53`:

- removed only the redundant `StaticBlockerDefinition` class-wide
  `vertical_extent_steps != 1` rejection; `WorldPlacementSpec` still enforces
  the lower bound, CENTER-kind validation remains, and all three authored rows
  remain explicitly extent 1;
- removed only the test-only `isinstance(item, WorldItem)` assertion and its
  now-unused `WorldItem` test import. Public spec and behavior assertions
  remain unchanged.

No other production or test change was made. The four Slice 3.1 selectors
passed (`4 passed, 31 deselected in 4.61s`), the full
`tests/engine/test_items_inventory_equipment.py` module passed (`35 passed in
5.21s`), edited production modules compiled, and `git diff --check` passed
with only the existing line-ending warnings.

The selector set is provably unchanged: only assertions/import/validation
statements were deleted; no test function, parameterization, or collection
surface changed. Therefore the frozen final collection remains the prior
1,322-selector set and SHA
`9c67b3e4f95c3054354f04d439428b9360a42021931d506ea73acdb49d61fc3a`, with
113 collecting modules, 105 blocked modules, 218 union modules, and unchanged
blocked-module/signature hashes recorded above. No collection rerun was
needed under the supervisor instruction.

The refreshed candidate manifest remains 94/94 exact members with zero
duplicates, exact set match, and zero member hash mismatches:

`DND_TILE_WORLD_ITEM_PHASE_3_SLICE_3_1_IMPLEMENTATION_MANIFEST_2026-08-24.json`

Final refreshed manifest SHA-256:
`2501ed3fb35c9b17ad5ef3dcd3bc289ef2145c9ea2ea60ab47164bacba099320`.

Stop here for supervisor review. Slice 3.2 was not started.

## Supervised Slice 3.2 atomic-boundary ledger — 2026-08-24

This is the read-only atomic-boundary preparation requested by the supervisor.
No Python, JSON, test, dependency, Git, or other-document mutation was made
in this continuation. The only permitted mutation is this Markdown append.

### Authority and starting-state verification

The following exact raw-byte SHA-256 values were reverified before this
ledger append:

| Artifact | SHA-256 | Result |
|---|---|---|
| DND_TILE_WORLD_ITEM_PHASE_3_SLICE_3_1_IMPLEMENTATION_MANIFEST_2026-08-24.json | 2501ed3fb35c9b17ad5ef3dcd3bc289ef2145c9ea2ea60ab47164bacba099320 | exact |
| this Phase 3 implementation ledger, pre-append | 1ebb8a8cbdfd0f5cff59efa02515b5c7477a184c094b373c33b64719fea13b95 | exact |
| DND_TILE_WORLD_ITEM_PHASE_3_ORDERED_SIDE_IMPLEMENTATION_GUIDANCE_2026-08-24.md | 560dbef81b39c43657d32087c1e7ab85c7d08ffa790df780f631358176994326 | exact |
| guidance substantive approved revision | 495914ec28df82b553f23347f2a29eb9be7764f21039e5619e083c1a20b4e7de | bound inside guidance |
| DND_TILE_WORLD_ITEM_VERTICAL_BOUNDARY_MIGRATION_PLAN_2026-08-17.md | 73335294139bdc81306f17381afe22f27fb94c9c48bcf07c1312eb9eeefafe63 | exact |
| unified_vision_light.md | 3c9c58483440640837bc38fdaa6b624f358e1098c9a957f65923cd64f83a270b | exact |
| AGENTS.md | fcc5dd1e15bae2ff86a7203f42b0c55de4d51dd0d93bc3a3ae059b7e58ee39b1 | exact |
| HOW_TO_TEST.MD | 96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013 | exact; 517 lines read |

The manifest verifier reported 94 declared rows, 94 actual scoped files, 94
rows in the file, zero duplicates, exact member-set equality, empty missing
and extra sets, and zero member-hash mismatches. Its scope is the existing
sorted git-status .py/.json raw-byte set, excluding Markdown governance and
the candidate manifest itself. The 94-member manifest therefore remains the
exact no-Python/JSON-change invariant for this read-only preparation.

The only bounded discovery command run in this continuation was:

    ./.venv/bin/pytest --collect-only -q -p no:cacheprovider tests/engine/test_senses_light_stealth.py tests/engine/test_items_inventory_equipment.py tests/manual/test_legacy_reactive_reaction_coverage.py tests/manual/test_134_stackable_usable_item_legacy_contract.py

It collected 66 selectors and exited 2 after 6.89 seconds. The two manual
modules were blocked at collection by the unchanged
ModuleNotFoundError: No module named 'dnd.content_system'; no test body ran.
No broad lane was rerun. The previously frozen Slice 3.1 collection remains
1,322 selectors (9c67b3e4f95c3054354f04d439428b9360a42021931d506ea73acdb49d61fc3a),
113 collecting modules (8a609e8b85157ad9c1db2e085c4f3ca82a6bcb9e4abc84ee4e278da4912873bb),
105 blocked modules (ff2ebd76d5772a93dff7723f9869316eb92fe05b10d7b916a6465005ef6bf531),
218 collecting/blocked union modules
(003720b0a00ac1ab53af1aabdebaeaf10b324b7e7a7e92b0d25e1e702e6ef7a6), and
the previously recorded normalized blocker-signature hashes. Those values are
carried forward, not re-claimed as a new broad run here.

### 1. Authored DirectionalWall/DirectionalDoor placement table

#### Canonical expansion rule

The old blocked_directions tuple is an authorship list, not a current door
state. The exact migration expansion is:

| Old authored value | Exact new rows | Canonical order/disposition |
|---|---|---|
| (NORTH, SOUTH, EAST, WEST) or the current four-direction default | four distinct object UUIDs and four distinct boundary placements at the same authored position/base, one per side | NORTH, EAST, SOUTH, WEST; no one object owns four sides |
| (WEST,) | one UUID, one WEST placement | unchanged |
| (EAST,) | one UUID, one EAST placement | unchanged |
| (NORTH,) | one UUID, one NORTH placement | unchanged |
| (SOUTH,) | one UUID, one SOUTH placement | unchanged |
| (neighbor_direction,) | one UUID on that exact authored side | the value is preserved, never inferred from the query |
| () on the initially-open standard door | one WEST placement with empty current BoundaryStructure.blocked_channels | placement is retained while open; it is not zero objects |
| () on a non-wall/non-door definition | no boundary placement | remains a center/other authored object, not a hidden side default |

The enum declaration is not used as the expansion order: its current order is
NORTH, SOUTH, EAST, WEST, while the required persisted expansion order is
explicitly NORTH, EAST, SOUTH, WEST.

#### Production definitions, builders, recipes, maps, and scenarios

| Live caller / evidence | Current authored fact | Slice 3.3 exact disposition |
|---|---|---|
| dnd/items/environment.py:64-128, DirectionalWall | one class has tuple blocked_directions, channels, and a directional-state projection | retain the semantic wall identity but replace tuple projection with one explicit boundary placement/spec and current BoundaryStructure; each expanded side is a distinct object UUID |
| dnd/items/environment.py:130-234, OpenDirectionalDoorAction/CloseDirectionalDoorAction | existing canonical directional actions mutate channel state by direction | retain the canonical environment.directional_door lifecycle/action identity; open/close changes only current channels, never placement; delete only the duplicate no-side actions below |
| dnd/items/environment.py:236-377, DirectionalDoor | one class has tuple blocked_directions and open/close directional updates | retain DirectionalDoor as the canonical door; replace tuple with one explicit side and BoundaryStructure; closed is WOOD/DOOR with all three channels, open is the same placement with empty channels |
| dnd/items/environment_content.py:125-139, DirectionalWallParameters/DirectionalDoorParameters | defaults use all DIRECTIONS | remove global four-side defaults; callers must pass an explicit side or an explicit expansion list; each resulting item is one side |
| dnd/items/environment_content.py:257-317, _build_directional_wall/_build_directional_door | builders pass the parameter tuple into the old classes | port to the explicit placement facts and preserve the same canonical content IDs/actions |
| dnd/items/environment_content.py:913-947, directional_wall_recipe/directional_door_recipe | recipe defaults use all DIRECTIONS | require/serialize explicit one-side authored data; multi-side source rows expand in canonical NORTH/EAST/SOUTH/WEST order before construction |
| dnd/items/environment_content.py:996-998, DIRECTIONAL_WALL_RECIPE/DIRECTIONAL_DOOR_RECIPE/DOOR_RECIPE | module constants materialize the four-direction and no-side families | directional constants become explicit one-side recipes or are removed in favor of explicit recipe calls; DOOR_RECIPE is deleted with the no-side family |
| dnd/items/environment_content.py:318-350, 880-882, environment.door declaration/ref and _build_door | no-side DoorObject construction | delete the no-side declaration/ref/builder/content identity; maintained callers move to environment.directional_door with an explicit side |
| dnd/content/items/environment_item_builders.py:31-64, build_directional_wall/build_directional_door | direct builders already receive explicit tuples | preserve the one-side direct route; reject multi-side construction or expand before construction, with exact NORTH/EAST/SOUTH/WEST UUID order |
| dnd/content/items/environment_item_builders.py:67-79,256, build_door | no-side DoorObject builder/export | delete; no compatibility alias or facade |
| dnd/content/items/authored_item_builders.py:50,529,655-656 | environment.door parameter map and branch call build_door | delete the no-side branch and parameter row; direct callers use an explicit environment.directional_door recipe/builder. There is no global side fallback |
| dnd/maps/arena_layout.py:18,61-114 | DOOR_DIRECTIONS and WALL_DIRECTIONS are (WEST,); runtime strip builds each wall/door with that tuple | preserve exact WEST one-object-per-position rows; preserve standard channels and closed/open lifecycle |
| dnd/content/scenarios/battlefield_definitions.py:37-59 | BattlefieldObjectDefinition.blocked_directions=() and is_open | replace boundary rows with explicit boundary_direction, base/orientation, and current open state. Non-boundary kinds retain no boundary placement; missing side on a boundary row rejects |
| dnd/content/scenarios/battlefield_builders.py:115-129 | _object_definition defaults side tuple to empty | remove inferred default for wall/door; require explicit authored side for those kinds |
| dnd/content/scenarios/battlefield_builders.py:147-177 | standard wall rows use WALL_DIRECTIONS; standard open door currently changes tuple to () | all standard wall/door rows author WEST; open_door=True changes only current channels to empty and retains the WEST placement |
| dnd/content/scenarios/battlefield_builders.py:180-202 | double-barrier rows at columns 5 and 9 use WEST for every wall/door | preserve one explicit WEST object per row and door |
| dnd/content/scenarios/battlefield_builders.py:206-218 | proving barrier rows at x=4 use WEST; cliff is a separate no-object elevation fact | preserve WEST wall/door rows; leave proving cliff to Slice 3.4 with its frozen crosswalk below |
| dnd/content/scenarios/battlefield_builders.py:347-361 | control-room (4,10) wall_torch has no side | defer to Slice 3.4; do not convert this unresolved attachment into a wall/door row |
| dnd/content/scenarios/battlefield_builders.py:518-542 | runtime barrier placement passes WEST explicitly | preserve exact WEST specs and use the same placement/structure source as cold layout |
| dnd/core/content/icon_bindings_generated.py:39,43,303 | generated no-side environment.door and duplicate action bindings | regenerate only after canonical IDs are frozen: retain directional door action/content bindings, delete environment.door/duplicate action bindings; no hand alias |

#### Current direct and recipe callers

| Caller | Exact current side evidence and disposition |
|---|---|
| tests/engine/test_world_edge_identity_and_elevation.py:183-186, direct default DirectionalWall and DirectionalDoor at (0,0), queried (0,0)->(1,0) | reauthor both as explicit EAST. The test source Tile is (0,0) and its exit direction is EAST; the reverse query expects the same providers on the reverse entry layer. |
| tests/engine/test_senses_light_stealth.py:176-177, direct default DirectionalDoor at (1,0) with observer (0,0) | reauthor WEST: the owner is the destination of the (0,0)->(1,0) route. |
| tests/engine/test_tile_surface_contract.py:1202-1206,1230-1234 | already explicit EAST; retain exact one-side rows. |
| tests/engine/test_elevation_proving_battlefield.py:136,314-315 | runtime builder supplies the explicit WEST proving door; retain and port structure assertions, not a default. |
| tests/manual/test_11_equipment_inventory_and_items.py:829-834 | directional_door_recipe("Tutorial Door") is placed at (1,0) for patient/actor at (0,0); add explicit WEST. |
| tests/manual/test_113_subjective_replication_routes.py:145-152 | already explicit WEST; retain. |
| tests/manual/test_117_player_replication_contract.py:541-552 | explicit legacy projection WEST; replace the projection fact with WorldObjectPlacement plus BoundaryStructure, retaining WEST. |
| tests/manual/test_120_subjective_world_projection.py:637-645,719-724,783-790,839-845,899-905,940-945,973-980,1058-1075 | each row already supplies EAST, a named variable side, or WEST; preserve each exact one-side authored value and port projections to ordered layers. |
| tests/manual/test_125_subjective_objective_render_parity.py:546-563,949-956,1020-1027 | each recipe already supplies NORTH, EAST, a neighbor-derived authored variable, or WEST; retain the explicit row and delete only legacy projection reads. |
| tests/manual/test_directional_environment_legacy_contract.py:107-110,157-162,237-240,291-295 | all direct/recipe rows are explicit EAST; retain exact side values and migrate assertions to BoundaryStructure. |
| tests/manual/test_72_battlefield_deployment_catalog.py:58-66 | closed standard door remains WEST; the open assertion must change from blocked_directions == () to authored WEST placement plus empty current channels. |
| tests/manual/test_37_authored_encounter_mechanics.py:125-127 | helper locates DirectionalDoor by type; no constructor side is authored at this site. Port the helper to canonical placement/structure identity. |
| tests/manual/test_legacy_reactive_reaction_coverage.py:923 | door_recipe(is_open=True) at owner (4,2) intercepting x=3->4; reauthor canonical directional door WEST and keep initially-open channels empty. |
| tests/manual/test_legacy_reactive_reaction_coverage.py:1036 | second door_recipe() at owner (5,2) with attacker/defender route through x=4->5; reauthor explicit WEST. The module remains collection-blocked by dnd.content_system. |
| tests/manual/test_134_stackable_usable_item_legacy_contract.py:501-518 | two no-side recipes are placed at (4,3) from actor (3,3) and (3,4) from actor (3,3); reauthor first WEST and second NORTH. |
| tests/manual/test_134_stackable_usable_item_legacy_contract.py:684-692 | far-only no-side door has no route evidence. Reauthor the fixture at (8,1) with explicit WEST while retaining its out-of-range-only purpose; do not infer from runtime geometry. The module is collection-blocked. |
| tests/engine/test_items_inventory_equipment.py:1187-1207 | no-side environment.door at (1,0) for actor (0,0); replace with canonical directional door explicit WEST and preserve stateful action assertions. |
| tests/engine/test_encounter_apis.py:703,750,777,1671,1753 | API/editor identity-only rows use no world-crossing route. Replace environment.door with canonical explicit-side recipe/request data; where the endpoint is only catalog identity, assert the canonical ID rather than retaining the retired identity. |

### 2. No-side DoorObject/environment.door migration and deletion map

No external persisted identity representing the repository’s no-side DoorObject
family was found. Repository evidence is limited to the following active,
blocked, deprecated, editor, and generated callers:

| Family/caller | Exact migration or deletion |
|---|---|
| dnd/items/environment_interactables.py:33-177, OpenDoorAction/CloseDoorAction/DoorObject | delete the class and duplicate actions. Canonical DirectionalDoor actions remain the one door lifecycle and preserve action.environment.directional_door.open/close. |
| dnd/items/environment_content.py:318-350,880-882,949-998,1077-1082,1098 | delete _build_door, DOOR_DECLARATION, DOOR_REF, door_recipe, DOOR_RECIPE, and related exports; retain only canonical directional content with explicit side. |
| dnd/content/items/environment_item_builders.py:13,67-79,256 | delete DoorObject import, build_door, and export. |
| dnd/content/items/authored_item_builders.py:50,529,655-656 | delete no-side import/parameter/branch; migrate maintained callers to canonical explicit-side construction. |
| dnd/content/items/item_catalog.py:121 | delete environment.door; register only environment.directional_door with explicit placement parameters. |
| dnd/core/content/icon_bindings_generated.py:39,43,303 | regenerate without no-side content/duplicate actions; do not add aliases. |
| deprecated/content_system_deprecated/action_definitions.py:228-234 and deprecated/devtools_deprecated/import_neuroclient_content_icon_bindings.py:494-498 | retire duplicate action.environment.door.*; retain historical records only as non-gameplay history. |
| deprecated/content_data_deprecated/ledgers/content_icon_bindings.json, deprecated/tools_deprecated/PRESENTATION_BRIDGE_AUDIT.json, and deprecated SDK generated contracts/reducer/render projections/tests | regenerate/delete the retired no-side identity and directional projection fields in the governed hard cut; these are deprecated/generated callers, not a compatibility target. |
| deprecated/server_deprecated/mapeditor_support.py:64-67,890-936,1337-1374 | delete DoorObject branches. Editor save/load moves to canonical directional recipes carrying required boundary_direction. A legacy boundary row missing that side is rejected with validation error; no side is guessed. Existing editor fixtures are reauthored with an explicit WEST field. |
| deprecated/server_deprecated/world_projection.py:764, player_replication/world_projection.py:574,731,766, subjective_parity_diagnostics.py:284-285,479,482,649-691, and player_replication_contract.py:223-238 | delete directional/no-side projection fields; replace with WorldObjectPlacement and BoundaryStructure after-values/observation facts. |
| tests/engine/test_senses_light_stealth.py:701-735 | replace center DoorObject at (2,0) with canonical directional door WEST, preserve open/close movement/optics/propagation behavior, and assert one canonical lifecycle. |
| tests/engine/test_items_inventory_equipment.py:1187-1207 | replace no-side content with canonical WEST recipe and preserve public action/state assertions. |
| tests/engine/test_encounter_apis.py:703,750,777,1671,1753 | migrate mapeditor/catalog payloads to canonical explicit-side content; no external identity is preserved by repository evidence. |
| tests/manual/test_legacy_reactive_reaction_coverage.py:60,64,923,1036 | replace door_recipe/DoorFixture with canonical directional door and explicit WEST rows; collection remains blocked until the frozen content dependency is restored. |
| tests/manual/test_134_stackable_usable_item_legacy_contract.py:58,71,501-518,684-692 | replace DOOR_RECIPE/OverrideDoorFixture; use WEST, NORTH, and explicit far WEST fixture rows above. |

The only product-level preservation stop would be new evidence of an external
persisted environment.door identity. None was found in the repository. A
future external-identity discovery must stop the hard cut rather than add an
alias.

### 3. Authored wall/door/cliff/WallTorch/center-blocker crosswalk

| Authored family | Exact placement/structure semantics | Slice disposition |
|---|---|---|
| DirectionalWall | boundary, occupying, extent 2, support-relative base/top, Material.STONE, BoundaryStructureKind.WALL, MOVEMENT + OPTICAL + PROPAGATION | Slice 3.3; one object per authored side |
| DirectionalDoor closed | boundary, occupying, extent 2, support-relative base/top, Material.WOOD, BoundaryStructureKind.DOOR, all three channels | Slice 3.3; close admission happens before state mutation |
| DirectionalDoor open | identical UUID/placement/extent/material/kind; blocked_channels=() | Slice 3.3; placement is unchanged and the provider remains in ordered layers |
| proving cliff | explicit boundary row at (11,5), owner WEST, [0,2), STONE, MOVEMENT only; existence never inferred from elevation | Slice 3.4 deferred; no implementation in 3.3 |
| WallTorch | explicit nonoccupying boundary placement with authored side/base/orientation; attached light remains source-owned | Slice 3.4 deferred; do not route control-room torch through wall/door migration |
| control-room WallTorch | (4,10) currently has no side in battlefield_builders.py:347-361 | true unresolved product decision; blocks Slice 3.4 only, not Slice 3.3 |
| center blockers from Slice 3.1 | Crate remains nonoccupying CENTER; Boulder, Barricade, and OilBarrel remain occupying CENTER extent 1 with their existing movement/optical/propagation semantics | already frozen in Slice 3.1; never expand a whole-cell blocker into four boundary objects |

Whole-cell Tile blocking and SpatialConditions remain separate center/route
mechanics. They are not converted into synthetic side objects.

### 4. Section 9 consumer-classification ledger

The replacement for every consumer is the existing ordered GridMap answer and
one pure MOVEMENT/OPTICAL/PROPAGATION channel evaluation. No generic policy
facade or second topology answer is proposed.

| Classification | Current exact callers | Required replacement |
|---|---|---|
| MOVEMENT | dnd/actions/standard.py:966,1128,1317,1607,4450,4639; dnd/entities/entity.py:5938; dnd/core/gridmap.py:1967 and its internal transition/diagonal bridge paths; current dnd/core/gridmap.py:760,1573-1619,1734-1736,3454 directional checks | call the ordered transition evaluator with MOVEMENT; retain support/progressive-surface height intersection, ordinary nonwalking authored barrier behavior, collision reporting, voluntary/forced movement, pathing, and diagonal one-of-two bridge rules |
| OPTICAL / contact.visual | dnd/core/gridmap.py:3594-3767,4147; dnd/blocks/sensory.py:653; dnd/core/gridmap.py:760,1575; visual/light/FOV paths | evaluate both ordered layers with OPTICAL, then run existing objective-light and sense/stealth resolver. Near-side effective light is used for a reached entry blocker; no destination-Tile light shortcut or far-content leak |
| PROPAGATION / line-of-effect | dnd/core/gridmap.py:4377-4459; dnd/blocks/sensory.py:719; dnd/core/aoe.py:141,221,226; dnd/entities/entity.py:6962 and the AoE collection chain; dnd/core/gridmap.py:1577 | use ordered PROPAGATION for LoE, total cover, AoE, jump/physical reach, and nonvisual propagation route. The dnd/core/aoe.py:221 no-argument barrier call becomes a bounded query over the shape’s already-known geometric footprint; the dnd/entities/entity.py:6962 action-discovery call passes each already-known candidate shape footprint, never a global map scan |
| typed contact existence | dnd/blocks/sensory.py:721-806 and contact reduction; dnd/entities/entity.py:5623-5691 target/action discovery; dnd/core/base_actions.py:1089 awareness/action path | use the ordered near-side route query for typed existence, expose source exit then transmitting destination entry at most once per UUID, and let existing range/stealth/invisibility/sense resolver decide contact.visual or special senses. Awareness-only action discovery reads contact existence, not propagation |
| scenario compatibility special case | dnd/content/scenarios/scenario_compatibility.py:285-429, especially duplicate _topology_cardinal_transition_allows, _topology_transition_allows, _topology_side_allows at :380-429 and tile.allows_direction/block.blocks_directional_movement at :406-420 | delete duplicate topology helpers and call the same public movement transition query with treat_closed_doors_as_interactable=True. The rule is transient, not persisted/cached/published; walls, both layers, support/height, and diagonal bridge remain active. Ordinary gameplay leaves the flag false |

The two candidate-bounded get_barrier_positions consumers are explicitly
covered: dnd/core/aoe.py:221 receives the current shape footprint, and
dnd/entities/entity.py:6962 receives the already-known candidate footprint
inside AoE action discovery. dnd/core/gridmap.py:4496-4513 and cache fields
at :173,367,2868,4561 lose the no-argument global scan/cache. The bounded
set is only an acceleration; the ordered channel evaluator remains authority.

### 5. Complete Section 14 deletion/replacement ledger

| Deletion authority | Live callers/evidence | Exact replacement and public wire/replay proof |
|---|---|---|
| Tile border_*, optical_border_*, propagation_border_*, object-derived directional fields, _intrinsic_border, _derived_border, set_intrinsic_border, set_object_border, allows_direction(s) | dnd/core/base_tiles.py:107-129,324-484; builder serialization dnd/content/scenarios/battlefield_builders.py:853-868; GridMap calls :760,1590-1736,3454,4507 | Tile intrinsic/center mechanics remain explicit; boundary mechanics derive from exact placements and WorldEdgeView. WorldTileState serializes no directional-open tuples; test_event_wire_visibility_contract.py::test_bootstrap_tile_and_object_carry_final_optical_channels and direct world-initialized round-trip prove the new wire |
| BaseItem twelve directional fields/helpers/setters | dnd/blocks/base_item.py:184,255-295,382-393,463-464,489-490; item snapshots at dnd/types/items.py:88 | ItemState.boundary_structure/ItemObservationState.boundary_structure plus exact WorldObjectPlacement; test_items_inventory_equipment.py and test_tile_surface_contract.py::test_world_initialized_round_trip_rebuilds_opposing_boundary_placements prove public round-trip |
| neutral BaseBlock.blocks_directional_movement, blocks_directional_optics, blocks_directional_propagation; get_objective_directional_structural_channels | dnd/core/base_block.py:174,380-391; dnd/core/gridmap.py:791,1573-1577; scenario compatibility :419; characterization test provider methods in test_world_edge_identity_and_elevation.py:54,72,90 and test_tile_surface_contract.py:80,104,126 | provider get_boundary_structure() is resolved once during ordered layer derivation; public edge/view/channel tests replace hook tests |
| ItemDirectionalStructureState and directional_structure projections | dnd/types/items.py:46-54,88; dnd/core/events/item_events.py:52; BaseItem snapshots; deprecated projections and manual parity tests | ItemState.boundary_structure and ItemObservationState.boundary_structure; SpatialChangeEvent.object_boundary_structure; ordinary Pydantic JSON round-trip plus public cold rebuild, not custom serialization |
| _OBJECT_BORDER_FIELDS, _directional_block_map, get_subjective_directional_block_map, recompute_tile_directional_blocking, subjective Tile rebuilding, set_tile_directional_border | dnd/core/gridmap.py:64,452,497-498,850-891,1580-1714,2189-2302,2617,2822,2898,3180,3257-3258,3341,3388; dnd/blocks/base_item.py:463-464; event metadata construction | exact local placement bands/reverse row plus ordered edge query; WorldEdgeView is derived and nonauthoritative. Existing placement/rebuild failure/locality tests assert authority, revisions, light, events, and diagnostics remain atomic |
| authored blocked_directions fields/parameters/defaults | dnd/items/environment.py, environment_content.py, environment_item_builders.py, authored_item_builders.py, battlefield definitions/builders, arena map, test/manual rows above | explicit boundary_direction, base/orientation, extent, material, kind, and current BoundaryStructure; multi-side authored data expands to distinct UUIDs before construction |
| scenario_compatibility duplicate directional topology | dnd/content/scenarios/scenario_compatibility.py:285-429 | same GridMap public movement query with the one narrow closed-door-interactable flag |
| WorldTileState.movement_open, .optical_open, .propagation_open | dnd/core/events/world_events.py:77-79; scenario bootstrap dnd/content/scenarios/battlefield_builders.py:853-868; tests/engine/test_event_wire_visibility_contract.py:128-130 | derive all boundary topology from WorldObjectState.placement and item.boundary_structure; retain one actor-free WorldInitializedEvent and ordinary Pydantic wire tests |
| authoritative SpatialChangeEvent.directional_position, directional_directions, directional_channels, and directional_blocks_* maps | dnd/core/events/world_events.py:604-609,630-681,689-738,752-795,808-858,870-914,994-1046; callers pass metadata throughout GridMap | delete the maps after migration; add only object_boundary_structure after-value. Retain SensesUpdateHint endpoint/channel candidate hints as nonauthoritative acceleration. Public completion-event and wire tests assert exact placement/structure after-values |
| DoorObject, duplicate actions, recipe, builder, content, generated bindings | inventory above | one DirectionalDoor action/lifecycle; open/close is one OBJECT_CHANGED, keeps placement/UUID, changes only actually changed channel revisions, and settles existing light/sensory lifecycle |
| no-argument global barrier discovery/cache | dnd/core/gridmap.py:173,367,2868,4496-4513,4561; dnd/core/aoe.py:221; dnd/entities/entity.py:6962 | bounded candidate-footprint barrier query backed by ordered channel evaluation; no global scan/cache/index |
| object-owned is_perceivable_by and subjective boundary bypass | historical/deprecated projections plus current sensory consumers identified in Section 9 | one ordered near-side route plus existing objective-light/sense resolver; no second contact schema or bypass hook |

The exact Tile 24-field deletion set is:

- intrinsic: border_north, border_south, border_east, border_west;
- intrinsic optical: optical_border_north, optical_border_south,
  optical_border_east, optical_border_west;
- intrinsic propagation: propagation_border_north,
  propagation_border_south, propagation_border_east,
  propagation_border_west;
- object movement: object_movement_border_north,
  object_movement_border_south, object_movement_border_east,
  object_movement_border_west;
- object optical: object_optical_border_north,
  object_optical_border_south, object_optical_border_east,
  object_optical_border_west; and
- object propagation: object_propagation_border_north,
  object_propagation_border_south, object_propagation_border_east,
  object_propagation_border_west.

The exact BaseItem 12-field deletion set is:
blocks_movement_north, blocks_movement_south, blocks_movement_east,
blocks_movement_west, blocks_optics_north, blocks_optics_south,
blocks_optics_east, blocks_optics_west, blocks_propagation_north,
blocks_propagation_south, blocks_propagation_east, and
blocks_propagation_west. Their direct helpers/setters are
_blocks_direction, _set_directional_blocking_field,
blocks_directional_movement, blocks_directional_optics,
blocks_directional_propagation, set_directional_blocking, and
set_directional_blocking_bulk. The exact three neutral BaseBlock hooks are
blocks_directional_movement, blocks_directional_optics, and
blocks_directional_propagation.

The authoritative replacement for every schema deletion is the exact
WorldObjectPlacement plus current BoundaryStructure. The operation matrix is:
placement/change arrival carries current structure or None; relocation
departure and terminal removal carry None with previous_placement still
authoritative; door state change carries current placement/structure and is
not remove/place. WorldInitializedEvent is the sole cold replay boundary and
publishes no per-object load lifecycle.

### 6. Required public Slice 3.3 behavior/test matrix

The following are the exact existing public modules/selectors to migrate and
the narrowly missing characterization selectors to add during Slice 3.3.
No selector was added in this read-only turn.

| Capability | Existing public module/selectors | Required additional public proof |
|---|---|---|
| one-object-per-side placement/ordered layers | tests/engine/test_tile_surface_contract.py::test_boundary_bands_are_exact_side_queries_and_independent_collisions; tests/engine/test_world_edge_identity_and_elevation.py::test_world_edge_is_ordered_and_reverses_endpoint_layers; ::test_world_edge_uses_exact_facing_side_intervals_and_uuid_order | one multi-side authored row expands to NORTH/EAST/SOUTH/WEST distinct UUIDs and placements; open door retains placement with empty channels |
| legal opposing occupants/same-local collision | same tile-surface tests; ::test_world_initialized_round_trip_rebuilds_opposing_boundary_placements; ::test_serialized_placement_rebuild_is_bijective_and_rejects_ambiguity | forward/reverse two-layer coexistence plus same-side atomic rejection and zero events |
| movement/height/diagonal | tests/engine/test_grid_pathfinding.py::test_eb_11_006_directional_borders_block_transitions_and_emit_metadata, ::test_eb_11_007_directional_channels_are_independent, ::test_eb_11_021_diagonal_transitions_need_one_cardinal_bridge_route, ::test_eb_11_017_forced_movement_and_jump_respect_directional_blockers; tests/engine/test_elevation_proving_battlefield.py::test_elevation_proving_battlefield_exercises_ordered_edge_rules | height-sensitive [0,2)/[2,4) walking and retained nonwalking answer; opposing redundant blockers do not bump movement revision |
| optical/contact/light | tests/engine/test_senses_light_stealth.py::test_one_optical_boundary_blocks_sight_and_light_but_not_propagation, ::test_opaque_endpoint_is_visible_while_cells_and_content_behind_are_not, ::test_each_move_step_emits_objective_and_subjective_facts_before_step_completion, ::test_optical_change_recomputes_only_light_sources_within_radius; tests/engine/test_world_edge_identity_and_elevation.py ordered view tests | near-side lit/dark-far visual contact; transparent/opaque ordered prefixes; duplicate route deterministic UUID merge; hidden/invisible wall objective blocking |
| propagation/AoE | tests/engine/test_grid_pathfinding.py::test_eb_11_009_geometry_and_aoe_are_grid_aware_where_needed, ::test_eb_11_018_zone_control_cone_and_line_use_directional_geometry; tests/engine/test_action_discovery.py::test_eb_09_010_registered_position_aoe_spell_previews_and_executes; tests/engine/test_senses_light_stealth.py::test_nonvisual_senses_create_contacts_without_visual_cells | channel-selective exit/entry propagation, bounded candidate footprint, nonvisual ordered route, and no distant-map work |
| scenario compatibility | tests/engine/test_elevation_proving_battlefield.py scenario movement; existing scenario compatibility callers | closed door is interactable only through the same public movement query with the explicit flag; wall remains blocked |
| door lifecycle/revisions | tests/engine/test_senses_light_stealth.py::test_center_door_changes_movement_optics_and_propagation_together; tests/engine/test_tile_surface_contract.py::test_rejected_move_leaves_authority_and_events_unchanged | one lifecycle/one bump per changed channel, same-XY light/anchor preservation, opposite redundant blocker leaves aggregate revisions/light unchanged while contact terminal layer changes |
| events/replay/bootstrap | tests/engine/test_tile_surface_contract.py::test_object_event_matrix_carries_exact_before_and_after_placements, ::test_world_initialized_round_trip_rebuilds_opposing_boundary_placements; tests/engine/test_event_wire_visibility_contract.py::test_bootstrap_tile_and_object_carry_final_optical_channels; tests/engine/test_direct_scenario_deployment.py::test_world_birth_and_deployment_are_ordered_event_facts, ::test_real_world_initialized_fact_keeps_surface_and_object_identity; tests/engine/test_objective_state.py::test_typed_sensory_events_replay_the_complete_subjective_projection | exact boundary-structure after-values, no cold lifecycle, one WorldInitialized replay authority, Pydantic wire round-trip of two opposing placements and semantic states |
| failure/locality | tests/engine/test_tile_surface_contract.py::test_rebuild_provider_failure_restores_live_state_and_current_diagnostics, ::test_rebuild_light_failure_restores_bounded_light_state_after_directional_settlement, ::test_malformed_rebuild_preserves_authority_mechanics_and_diagnostics, ::test_boundary_placement_diagnostics_count_only_owner_and_local_bands, ::test_rebuild_diagnostics_ignore_distant_unused_tiles; tests/engine/test_senses_light_stealth.py::test_fixed_radius_optical_query_cost_is_independent_of_total_map_size | public event cursor, revisions, resolved light, ordered layers, and diagnostics remain identical after failed same-side rebuild |
| conditions/anchors/WallTorch/Continual Flame | tests/engine/test_spatial_effects.py::test_world_object_anchor_moves_then_retires_with_its_object; tests/engine/test_items_inventory_equipment.py::test_eb_13_011_torch_lifecycle_manages_attached_light_sources, ::test_wall_torch_attached_light_follows_move_and_terminal_removal; tests/engine/test_spell_families.py existing torch/Continual Flame selectors | Slice 3.3 preserves existing center/condition-owned behavior. Physical condition optics settlement is a required new public test; WallTorch explicit-side characterization is Slice 3.4, with control-room decision unresolved |

All new proofs must use public commands, typed values, completed events,
ordered views, replay, resolved light, and structured diagnostics. Private
bands/caches/indexes, monkeypatching, AST/source-layout assertions, and timing
substitutes for diagnostics are excluded.

### 7. Proposed Slice 3.3 mutation envelope and atomic coding order

The following is a proposed file-by-file envelope only; no file in it was
edited in this preparation. Production scope is:

    dnd/core/base_tiles.py
    dnd/core/base_block.py
    dnd/blocks/base_item.py
    dnd/blocks/sensory.py
    dnd/types/items.py
    dnd/core/events/item_events.py
    dnd/core/events/world_events.py
    dnd/core/gridmap.py
    dnd/core/aoe.py
    dnd/entities/entity.py
    dnd/actions/standard.py
    dnd/items/environment.py
    dnd/items/environment_content.py
    dnd/items/environment_interactables.py
    dnd/content/items/environment_item_builders.py
    dnd/content/items/authored_item_builders.py
    dnd/content/items/item_catalog.py
    dnd/content/scenarios/battlefield_definitions.py
    dnd/content/scenarios/battlefield_builders.py
    dnd/content/scenarios/scenario_compatibility.py
    dnd/maps/arena_layout.py
    dnd/core/content/icon_bindings_generated.py
    deprecated/server_deprecated/mapeditor_support.py
    deprecated/server_deprecated/world_projection.py
    deprecated/server_deprecated/player_replication/world_projection.py
    deprecated/server_deprecated/player_replication_contract.py
    deprecated/server_deprecated/subjective_parity_diagnostics.py
    deprecated/content_system_deprecated/action_definitions.py
    deprecated/devtools_deprecated/import_neuroclient_content_icon_bindings.py
    deprecated/sdk_deprecated/typescript/src/generated/contract.generated.json
    deprecated/sdk_deprecated/typescript/src/generated/contracts.generated.ts
    deprecated/sdk_deprecated/typescript/dist/generated/contracts.generated.d.ts
    deprecated/sdk_deprecated/typescript/src/reducer.ts
    deprecated/sdk_deprecated/typescript/src/renderProjection.ts
    deprecated/sdk_deprecated/typescript/dist/renderProjection.d.ts

The authorized test envelope is the existing engine modules named in Section 6,
the blocked/manual caller modules listed in Sections 1–2 when their dependency
blocker is available, tests/engine/test_items_inventory_equipment.py,
tests/engine/test_spell_families.py, tests/architecture, and the direct
world-edge/elevation/senses/action/AoE/spatial/replay modules named above.

The safe internal order is:

1. freeze this ledger and supervisor approval;
2. replace cold authored wall/door schemas and one-side expansion, including
   editor/recipe definitions;
3. make canonical DirectionalWall/DirectionalDoor structures and action state
   use the exact placement/structure values;
4. switch ordered edge derivation and local GridMap mechanics to
   BoundaryStructure and both layers;
5. migrate movement, optical/light/contact, propagation/AoE, condition optics,
   and scenario compatibility consumers;
6. migrate event/item/tile/bootstrap wire facts and replay;
7. replace bounded barrier/FOV paths and near-side contact reduction;
8. regenerate maintained generated/editor/deprecated projections and delete
   all Section 14 authorities in the same hard cut;
9. run public behavior, failure/locality, wire/replay, dependency, deletion,
   collection, and manifest gates.

This order is an internal implementation sequence only. The entire cut must
freeze atomically: no intermediate state may be handed off with new boundary
objects feeding old booleans, old consumers reading deleted facts, or two
writable topology authorities. No compatibility alias, dual write, cache/index
layer, DTO/facade, reducer/controller, or custom serializer is authorized.

### 8. Unresolved questions and verdict

Resolved for Slice 3.3:

- every maintained wall/door row has an explicit side disposition above;
- initially-open standard door retains WEST placement and only empties current
  channels;
- no-side direct tests have explicit WEST/NORTH/EAST reauthorings or the far
  fixture reauthoring at (8,1)/WEST;
- editor/persisted rows missing a side reject instead of guessing; and
- no repository evidence requires preserving the no-side external identity.

Known non-product evidence limitation:

- the two manual discovery modules remain blocked by the frozen
  dnd.content_system import failure. Their caller obligations are ledgered;
  this does not authorize an import shim or relax the side rules.

The only unresolved product question is the control-room WallTorch at (4,10).
It blocks Slice 3.4 only and does not block Slice 3.3. No unresolved wall or
door side remains. Verdict: READY FOR SUPERVISOR PHASE-3.2 REVIEW; no Slice 3.3
implementation authority is granted by this ledger.

### Scope and SHA algorithm

This continuation contains only the caller/deletion/consumer/test/mutation
ledger requested for Slice 3.2. Its manifest invariant is the exact raw-byte
SHA-256 of every sorted .py/.json member in the already frozen candidate
scope, excluding Markdown governance files and the manifest itself. The new
complete-ledger SHA is intentionally computed and reported externally after
this append, so it is not embedded self-referentially in this file.

## Supervised Slice 3.2 correction/rebind — 2026-08-24

This correction section supersedes conflicting dispositions in the preceding
Slice 3.2 preparation while preserving that history. It is still read-only
preparation: no Python, JSON, TypeScript, JavaScript, test, dependency, Git,
or other-document edit was made. The only mutation is this Markdown append.

### Starting rebind and construction authority

Before this append, the exact starting values were reverified:

- Phase 3 implementation ledger:
  efcc26f3ef499204675398721ee108d01b6ec89e9fb77c5bf210de9eaad9316c;
- Slice 3.1 code manifest:
  2501ed3fb35c9b17ad5ef3dcd3bc289ef2145c9ea2ea60ab47164bacba099320;
- manifest declaration, rows, and unique members: 94, 94, and 94;
- manifest member mismatches: zero; and
- this ledger is excluded from the code manifest.

The one expansion owner and one construction contract are now fixed:

1. Runtime DirectionalWallParameters and DirectionalDoorParameters each have
   exactly one required explicit boundary_direction: CardinalDirection.
   Neither model has blocked_directions, a tuple-valued side field, or a
   default side. Their orientation is explicitly None in this cut.
2. Direct/runtime builders construct exactly one side. Missing side input,
   a legacy multi-side tuple, or any extra side field is rejected by the
   strict authored parameter/recipe boundary. A side never implies
   orientation.
3. Authored layout/scenario migration is the sole expansion owner. It expands
   each legacy multi-side authored row into N distinct recipe/materialization
   requests and UUIDs in NORTH, EAST, SOUTH, WEST order, then calls the
   one-side runtime contract once per request. Runtime builders never expand.
4. DIRECTIONAL_WALL_RECIPE and DIRECTIONAL_DOOR_RECIPE are deleted, including
   their exact definition lines 996-997 and exports 1077-1079 in
   dnd/items/environment_content.py. Exact search found no other definitions
   or uses. The no-side DOOR_RECIPE family remains deleted as already bound.
5. The wall and door placement orientation is None, not a side-derived value.
   Any stored non-None orientation is preserved only where the existing public
   placement contract explicitly authors it; these wall/door rows author None.

The editor catalog contract is also fixed. The current
deprecated/server_deprecated/mapeditor_support.py:466-489 build_catalog path
must not call construction.parameter_model.model_validate({}). It instead
exposes the existing Pydantic parameter model JSON schema and its required
fields in the catalog row, without constructing a runtime item or fabricating
defaults. Construction is permitted only from a fully validated explicit
ContentRecipe containing boundary_direction. The exact editor callers/tests
are build_catalog and _content_catalog_entry at
deprecated/server_deprecated/mapeditor_support.py:408-489 and :1461-1495,
the mapeditor_object_request helper at
tests/engine/test_encounter_apis.py:238-252, the catalog assertions at
tests/engine/test_encounter_apis.py:1611-1674, and all placement/save/load
requests at rows 703, 750, 753-777, and 1751-1755. Catalog-only rows expose
required schema fields; they do not assert a materialized side.

### Corrected authored side and fixture facts

The following exact choices supersede the earlier table entries:

| Caller | Correct old/new authored fact |
|---|---|
| tests/manual/test_134_stackable_usable_item_legacy_contract.py:501-518 | old no-side door at (3,4), viewed from actor (3,3), becomes explicit SOUTH. Positive Y is NORTH; therefore the owner-facing side is SOUTH. The other door at (4,3) remains WEST. Any earlier NORTH entry for (3,4) is superseded. |
| tests/engine/test_world_edge_identity_and_elevation.py:183-203 | the old wall and door co-placement at (0,0) is not retained. The exact rewrite is wall source I at (0,0), side EAST, and door destination J at (1,0), side WEST. The forward query I->J therefore proves wall in exit and door in entry without same-local collision; after opening the door, its entry contribution remains present with empty channels. |
| tests/manual/test_134_stackable_usable_item_legacy_contract.py:684-692 | old far-only door position (8,8) becomes (8,1); actor remains (1,1); side is explicitly WEST. The new fixture is cardinally aligned on the row y=1 and remains out of range. This is authored fixture data, not runtime side inference. |
| tests/engine/test_encounter_apis.py:701-705,748-752,1751-1755 | placement/save/load rows use a canonical environment.directional_door recipe/payload with explicit WEST boundary_direction. |
| tests/engine/test_encounter_apis.py:775-779 | row 777 asserts saved canonical identity environment.directional_door and its explicit WEST side, not environment.door. |
| tests/engine/test_encounter_apis.py:1671-1674 | catalog identity-only row asserts environment.directional_door and the required boundary_direction schema field. It does not invent a placement or side value. |

Every deprecated mapeditor fixture which constructs, saves, or loads a door is
fixed to the same explicit policy. Existing route-backed fixtures retain their
reviewed side: owner (2,0) WEST for the crossing (1,0)->(2,0), owner (1,0)
WEST for the actor route from (0,0), owner (4,2) WEST for x=3->4, owner
(4,3) WEST for the (3,3)->(4,3) route, and owner (3,4) SOUTH for the
(3,3)->(3,4) route. Generic editor-only fixtures are reauthored with an
explicit WEST recipe/payload and assert schema/identity separately from
placement mechanics. A legacy saved boundary row without boundary_direction
is rejected; it is never guessed.

### Physical-condition owner and settlement correction

The exact Slice 3.3 production owners now include:

- dnd/core/base_conditions.py: add neutral default-false
  blocks_physical_optics_at(position), with no observer-relative
  optical_obscurement behavior and no side-layer contribution;
- dnd/spatial/area_conditions.py: own activation, displacement,
  transition_footprint, move_zone, and deactivation physical-optics settlement;
- dnd/spatial/environmental_conditions.py: SpikeTrap.extend_footprint at
  :517 remains nonphysical/default-false in this cut, while its generic
  footprint lifecycle is covered by the same transition/failure tests; and
- dnd/types/world_placement.py: add canonical unique
  BoundaryStructure.blocked_channels validation. The tuple must contain only
  WorldEdgeChannel values, no duplicates, in canonical channel order.

The exact area-condition settlement is: after the old/new footprint index
commit, evaluate the aggregate physical obstruction at every position in
previous_positions union current_positions, including overlapping Tiles,
objects, and conditions. Bump the existing optical revision once only when
an aggregate answer changes. Radius-filter and deduplicate the relevant
active light sources and recompute each source once. Publish the causal
existing light facts before the existing SpatialEffect completion reaches
sensory reduction. Failure restores the prior footprint/index, obstruction
answer, revision, source-owned light, and event cursor through the existing
bounded rollback. No EventQueue callback, event type, cache, or new condition
index is introduced.

The exact public characterization selectors to add in
tests/engine/test_spatial_effects.py are:

- test_physical_optics_condition_blocks_only_its_indexed_footprint;
- test_overlapping_physical_optics_conditions_do_not_bump_optical_revision_or_recompute_light;
- test_physical_optics_condition_transition_settles_light_before_completion; and
- test_failed_physical_optics_condition_transition_restores_authority_light_and_events.

These use public condition activation/displacement/transition/move/deactivation
commands, public Tile/condition obstruction answers, optical revisions,
resolved light, completed causal events, and EventQueue cursors. They do not
read a private condition index or monkeypatch callback counts.

dnd/core/world_edges.py is reviewed and is not in the planned mutation set.
The sole pure ordered channel evaluator remains in the planned GridMap owner;
world_edges.py changes only if supervisor later deliberately assigns that
single evaluator there, not speculatively.

### Complete bounded barrier caller correction

The complete live caller set is exactly:

| Caller | Exact bounded footprint passed |
|---|---|
| dnd/core/aoe.py:221 | the already computed local geometric shape set in compute_objective |
| dnd/entities/entity.py:6962 | each already-known candidate AoE shape footprint inside _collect_aoe_actions; the shared no-argument precompute is deleted |
| deprecated/server_deprecated/event_server.py:3284 | the shape instance’s already-known target footprint for the requested preview position |
| tests/engine/test_grid_pathfinding.py:776,784 | the already computed Cylinder target footprint, separately for subjective and targeting preview |

The exact API is one bounded public get_barrier_positions(footprint) query;
there is no no-argument overload. dnd/core/gridmap.py:173,367,2868,4496-4513,
4561 loses the global cache and whole-map scan. All four callers pass a
known footprint; the bounded result accelerates only the exact ordered
PROPAGATION evaluator and never becomes a second authority.

### Deprecated editor mutation owners

The complete editor directional mutation path is included in the hard cut:

- deprecated/server_deprecated/api_models.py:356-410
  MapEditorTilePatch.directional_channel, direction, and passable fields and
  MapEditorTilePatchRequest;
- deprecated/server_deprecated/mapeditor_support.py:609-618,
  657,686,700,722,737-758, and 1282-1296, including every old
  set_tile_directional_border call;
- deprecated/server_deprecated/event_server.py:1199 and the directional tile
  patch endpoint around the mapeditor tile routes, plus the barrier preview
  at :3284; and
- tests/engine/test_encounter_apis.py:463,649,669-672,737,797,1611-1693
  and 1751-1755, together with the manual wire rows below.

The exact replacement is a canonical boundary-object placement/update
containing explicit side, current structure, and placement facts. Tile patch
requests no longer write deleted Tile booleans. A legacy directional tile
patch is rejected as an unsupported schema, not wrapped by a compatibility
facade. Catalog-only tests assert the canonical identity and required schema;
placement tests submit a fully validated explicit recipe.

### Generated and deprecated artifact envelope

The exact choice is: regenerate all tracked governed outputs from their
maintained source. The affected source and generated files are:

Core/deprecated Python and JSON:

- dnd/core/content/icon_bindings_generated.py;
- deprecated/server_deprecated/world_contracts.py;
- deprecated/server_deprecated/event_contract.generated.json;
- deprecated/content_data_deprecated/ledgers/content_icon_bindings.json;
- deprecated/tools_deprecated/PRESENTATION_BRIDGE_AUDIT.json;
- deprecated/content_system_deprecated/action_definitions.py; and
- deprecated/devtools_deprecated/import_neuroclient_content_icon_bindings.py.

SDK authored/generated sources:

- deprecated/sdk_deprecated/typescript/src/generated/contract.generated.json;
- deprecated/sdk_deprecated/typescript/src/generated/contracts.generated.ts;
- deprecated/sdk_deprecated/typescript/src/reducer.ts;
- deprecated/sdk_deprecated/typescript/src/renderProjection.ts;
- deprecated/sdk_deprecated/typescript/src/tests/fixtures.ts;
- deprecated/sdk_deprecated/typescript/src/tests/renderProjection.test.ts; and
- deprecated/sdk_deprecated/typescript/src/tests/replication.test.ts.

Affected tracked SDK outputs and maps:

- deprecated/sdk_deprecated/typescript/dist/generated/contracts.generated.js;
- deprecated/sdk_deprecated/typescript/dist/generated/contracts.generated.js.map;
- deprecated/sdk_deprecated/typescript/dist/generated/contracts.generated.d.ts;
- deprecated/sdk_deprecated/typescript/dist/generated/contracts.generated.d.ts.map;
- deprecated/sdk_deprecated/typescript/dist/reducer.js;
- deprecated/sdk_deprecated/typescript/dist/reducer.js.map;
- deprecated/sdk_deprecated/typescript/dist/reducer.d.ts;
- deprecated/sdk_deprecated/typescript/dist/reducer.d.ts.map;
- deprecated/sdk_deprecated/typescript/dist/renderProjection.js;
- deprecated/sdk_deprecated/typescript/dist/renderProjection.js.map;
- deprecated/sdk_deprecated/typescript/dist/renderProjection.d.ts;
- deprecated/sdk_deprecated/typescript/dist/renderProjection.d.ts.map;
- deprecated/sdk_deprecated/typescript/dist/tests/fixtures.js;
- deprecated/sdk_deprecated/typescript/dist/tests/fixtures.js.map;
- deprecated/sdk_deprecated/typescript/dist/tests/fixtures.d.ts;
- deprecated/sdk_deprecated/typescript/dist/tests/fixtures.d.ts.map;
- deprecated/sdk_deprecated/typescript/dist/tests/renderProjection.test.js;
- deprecated/sdk_deprecated/typescript/dist/tests/renderProjection.test.js.map;
- deprecated/sdk_deprecated/typescript/dist/tests/renderProjection.test.d.ts;
- deprecated/sdk_deprecated/typescript/dist/tests/renderProjection.test.d.ts.map;
- deprecated/sdk_deprecated/typescript/dist/tests/replication.test.js;
- deprecated/sdk_deprecated/typescript/dist/tests/replication.test.js.map;
- deprecated/sdk_deprecated/typescript/dist/tests/replication.test.d.ts; and
- deprecated/sdk_deprecated/typescript/dist/tests/replication.test.d.ts.map.

No affected deprecated output family is deleted in this rebind. Source
generation and every listed tracked output are one governed regeneration unit;
there is no hand-edited alias or partial dist refresh.

### Additional manual and wire dispositions

The exact additional callers are:

- tests/manual/test_08_world_model_and_movement.py:175-186: replace the
  directional Tile setter and directional event fields with an explicit
  boundary-object recipe/update and ordered movement answer;
- tests/manual/test_149_remaining_legacy_contract.py:270-273: migrate the
  directional event payload assertion to the canonical boundary structure,
  retaining optical channel vocabulary;
- tests/manual/test_120_player_replication_journal.py:196-199: replace
  directional projection fields with placement/BoundaryStructure facts and
  preserve journal ordering; and
- tests/manual/test_97_event_wire_contract.py:285-329: migrate topology
  vocabulary to OPTICAL, keep illumination evidence in its separate light
  fields, and preserve ordinary Pydantic wire round-trip.

The complete Python test residue for deleted setters/recompute hooks is:

- tests/engine/test_grid_pathfinding.py:296,308,435;
- tests/engine/test_manual_11_grid_tiles_terrain_movement.py:124;
- tests/engine/test_world_edge_identity_and_elevation.py:138;
- tests/engine/test_move_settlement.py:96,108;
- tests/engine/test_action_cost_and_position_commit.py:222,229;
- tests/engine/test_traversal_connectors.py:1568,1575;
- tests/engine/test_elevated_jump_transaction.py:358,368;
- tests/engine/test_encounter_apis.py:463,649;
- tests/engine/test_senses_light_stealth.py:217,797,839,853,860;
- tests/manual/test_08_world_model_and_movement.py:153;
- tests/manual/test_149_remaining_legacy_contract.py:220; and
- tests/manual/test_directional_environment_legacy_contract.py:165.

The exact disposition is to migrate public setter callers to explicit
boundary-object placement/update and ordered channel queries. The four tests
which currently monkeypatch recompute_tile_directional_blocking
(test_move_settlement.py, test_action_cost_and_position_commit.py,
test_traversal_connectors.py, and test_elevated_jump_transaction.py) either
move to the public provider-failure gate below or delete the obsolete helper
assertion; no monkeypatch remains as a gameplay proof. Test-only providers in
test_world_edge_identity_and_elevation.py:54,72,90 and
test_tile_surface_contract.py:80,104,126 implement the public
get_boundary_structure capability or are deleted when their old hook proof is
redundant.

The Slice 3.3 deletion gate is exact: after the hard cut, active Python has
zero references to set_tile_directional_border,
recompute_tile_directional_blocking, set_directional_blocking,
set_directional_blocking_bulk, blocks_directional_movement,
blocks_directional_optics, blocks_directional_propagation,
get_objective_directional_structural_channels, and
get_directional_structure_state. Historical governance text is excluded from
this gameplay-symbol gate.

### Public failure and lifecycle gates

The existing public provider-failure selector
tests/engine/test_tile_surface_contract.py::test_object_commands_restore_bands_borders_and_events_when_provider_throws
is ported to a provider whose public get_boundary_structure() raises. The
proof captures only public placement/view/revision/resolved-light/event-cursor
and GridMapOperationDiagnostics values, then asserts exact restoration after
place, move, and orient failure. The existing
test_rebuild_provider_failure_restores_live_state_and_current_diagnostics
and same-side rebuild rejection receive the same public structure-provider
coverage.

Door close does not re-admit bands. An open door remains an occupying provider
with its existing placement; close validates the resulting BoundaryStructure
and current fact before mutating state, but never removes/re-adds the band or
changes placement. The phrase close admission in earlier ledger wording is
superseded by this rule.

The exact public door-failure selector to add in
tests/engine/test_senses_light_stealth.py is
test_rejected_door_close_preserves_placement_structure_revisions_light_contacts_and_events.
It precomputes the resulting BoundaryStructure/fact, requests a close that is
publicly vetoed, and asserts unchanged is_open, placement, ordered forward
and reverse views, movement/optical/propagation revisions, resolved light,
typed contacts, event cursor, accepted completion facts, and diagnostics.
There is no new transaction or EventQueue framework.

The existing
tests/engine/test_senses_light_stealth.py::test_center_door_changes_movement_optics_and_propagation_together
is migrated from EventQueue._all_events to a cursor captured before each
operation and public EventQueue.iter_events_since(cursor), filtering only
completed facts for the door UUID. It asserts exact one lifecycle per
open/close and exact after-values. The existing failed same-side placement,
failed same-side rebuild, aggregate-unchanged opposing blocker, local
diagnostics, and cold event-suppression gates remain mandatory.

### Corrected complete Slice 3.3 mutation and test envelopes

The exact production mutation envelope is:

- dnd/types/world_placement.py;
- dnd/core/base_conditions.py;
- dnd/spatial/area_conditions.py;
- dnd/spatial/environmental_conditions.py;
- dnd/core/base_tiles.py;
- dnd/core/base_block.py;
- dnd/blocks/base_item.py;
- dnd/blocks/sensory.py;
- dnd/types/items.py;
- dnd/core/events/item_events.py;
- dnd/core/events/world_events.py;
- dnd/core/gridmap.py;
- dnd/core/aoe.py;
- dnd/entities/entity.py;
- dnd/actions/standard.py;
- dnd/items/environment.py;
- dnd/items/environment_content.py;
- dnd/items/environment_interactables.py;
- dnd/content/items/environment_item_builders.py;
- dnd/content/items/authored_item_builders.py;
- dnd/content/items/authored_item_definitions.py;
- dnd/content/items/item_catalog.py;
- dnd/content/scenarios/battlefield_definitions.py;
- dnd/content/scenarios/battlefield_builders.py;
- dnd/content/scenarios/scenario_compatibility.py;
- dnd/maps/arena_layout.py;
- deprecated/server_deprecated/api_models.py;
- deprecated/server_deprecated/mapeditor_support.py;
- deprecated/server_deprecated/event_server.py;
- deprecated/server_deprecated/world_contracts.py;
- deprecated/server_deprecated/world_projection.py;
- deprecated/server_deprecated/player_replication/world_projection.py;
- deprecated/server_deprecated/player_replication_contract.py;
- deprecated/server_deprecated/subjective_parity_diagnostics.py;
- deprecated/server_deprecated/event_contract.generated.json;
- deprecated/content_data_deprecated/ledgers/content_icon_bindings.json;
- deprecated/tools_deprecated/PRESENTATION_BRIDGE_AUDIT.json;
- deprecated/content_system_deprecated/action_definitions.py;
- deprecated/devtools_deprecated/import_neuroclient_content_icon_bindings.py;
- dnd/core/content/icon_bindings_generated.py;
- the exact SDK source/generated/dist files listed in the artifact envelope;
- dnd/core/world_edges.py is explicitly reviewed/no edit; and
- any sole pure evaluator edit is assigned to dnd/core/gridmap.py, not both
  owners.

The exact test mutation envelope includes:

- tests/engine/test_tile_surface_contract.py;
- tests/engine/test_world_edge_identity_and_elevation.py;
- tests/engine/test_senses_light_stealth.py;
- tests/engine/test_grid_pathfinding.py;
- tests/engine/test_action_discovery.py;
- tests/engine/test_elevation_proving_battlefield.py;
- tests/engine/test_spatial_effects.py;
- tests/engine/test_condition_lifecycle.py;
- tests/engine/test_event_wire_visibility_contract.py;
- tests/engine/test_objective_state.py;
- tests/engine/test_direct_scenario_deployment.py;
- tests/engine/test_items_inventory_equipment.py;
- tests/engine/test_spell_families.py;
- tests/engine/test_move_settlement.py;
- tests/engine/test_action_cost_and_position_commit.py;
- tests/engine/test_traversal_connectors.py;
- tests/engine/test_elevated_jump_transaction.py;
- tests/engine/test_encounter_apis.py;
- tests/engine/test_manual_11_grid_tiles_terrain_movement.py;
- tests/manual/test_08_world_model_and_movement.py;
- tests/manual/test_97_event_wire_contract.py;
- tests/manual/test_120_player_replication_journal.py;
- tests/manual/test_149_remaining_legacy_contract.py;
- tests/manual/test_117_player_replication_contract.py;
- tests/manual/test_113_subjective_replication_routes.py;
- tests/manual/test_120_subjective_world_projection.py;
- tests/manual/test_125_subjective_objective_render_parity.py;
- tests/manual/test_134_stackable_usable_item_legacy_contract.py;
- tests/manual/test_legacy_reactive_reaction_coverage.py; and
- tests/manual/test_directional_environment_legacy_contract.py.

No test file is edited in this preparation. The hard cut is one atomic review
unit: no independent green handoff is permitted between schema, authored
construction, topology, consumer, event, editor, generated, or deletion
steps.

### Slice 3.3 final manifest binding

The current Slice 3.1 94-member manifest remains unchanged and is not
regenerated in this read-only correction. The final Slice 3.3 manifest
algorithm is fixed now: sort every changed tracked or untracked governed
member with extension .py, .json, .ts, .js, .d.ts, or .map; hash each exact
raw byte sequence with SHA-256; record every path and hash; exclude all
Markdown governance files and the manifest itself; and verify declared count,
row count, uniqueness, set equality, and every member hash. This includes
the full regenerated SDK source/dist/test/map family and the listed
deprecated/generated Python/JSON artifacts. No other extension is silently
included.

After this correction append, the ledger will be externally rehashed and the
new SHA reported. No implementation, test execution, broad collection, or
Slice 3.3 start is authorized.

## Final supervised Slice 3.2 correction/rebind — 2026-08-24

This is the final read-only ledger correction. It supersedes conflicting
catalog, AoE-footprint, and test-envelope wording above while preserving all
prior history. No Python, JSON, TypeScript, JavaScript, test, dependency, or
Git edit was made.

### 1. Executable MapEditorContentCatalogEntry contract

The exact replacement for the current
deprecated/server_deprecated/api_models.py:701-731
MapEditorContentCatalogEntry is:

- ref: ContentRef, always present;
- parameter_schema: dict, always present, containing the existing Pydantic
  JSON schema and required fields;
- recipe: ContentRecipe | None;
- recipe_preset_ref: ContentRecipePresetRef | None; and
- the existing content_set_digest, display, tags, presentation, and ordering
  fields.

Its model validator enforces exactly two variants:

1. A definition row has recipe=None and recipe_preset_ref=None. ref identifies
   the constructible definition and parameter_schema exposes every required
   parameter. A required-parameter definition never receives a fake default
   recipe.
2. A preset row has recipe present, recipe.ref == ref, and an optional
   recipe_preset_ref. Its parameter_schema is the same definition schema.

The validator also enforces content-set equality for every row and exact ref
equality for preset rows. No second wrapper DTO and no compatibility recipe is
introduced.

The row identity/uniqueness key is exact:

- definition row: ('definition', ref.identity_key);
- preset row: ('preset', recipe.recipe_digest).

MapEditorCatalog rejects duplicate keys and any row whose content_set_digest
differs from the catalog digest. Stable row sorting is the existing ordering
tuple, then ref.identity_key, then recipe.recipe_digest or the empty string.
Objects and loot classification reads ref.definition_kind directly; it never
dereferences row.recipe.ref because definition rows have no recipe.

The exact construction owners are:

- deprecated/server_deprecated/mapeditor_support.py:408-489
  build_catalog and :1461-1495 _content_catalog_entry create one definition
  row for every public constructible definition;
- build_catalog creates a preset row only from an authenticated preset and
  sets recipe.ref equal to the row ref;
- deprecated/server_deprecated/mapeditor_support.py:760-817
  place_catalog_object and the event-server placement endpoint require
  recipe is not None and full recipe validation; and
- tests/engine/test_encounter_apis.py:238-252
  mapeditor_object_request, :703-779, :1611-1674, and :1751-1755 are the
  exact public catalog/placement/save/load callers to migrate.

Selecting a definition row without a recipe returns typed validation guidance
containing parameter_schema and its required parameter names. Error/correction
context uses recipe_digest for preset rows and otherwise ref.identity_key plus
the required parameter names. event_server.py catalog/error construction and
the generated SDK contract/source/dist fixtures/tests carry the optional
recipe, required ref/schema, and both variants. No catalog manager or facade
is added.

### 2. One pure public AoE geometry query

The exact new public method in dnd/core/aoe.py is:

    AoEShape.get_geometric_footprint(
        caster_pos,
        *,
        target_override=None,
    ) -> frozenset[tuple[int, int]]

It is geometry-only. It does not mutate affected_positions or computed_origin.
When target_override is supplied, it uses a transient model_copy only inside
this method, then reuses the existing get_origin and
_get_positions_in_shape. It creates no persistent cache or state.

compute_objective and compute_subjective use this method for their raw
candidate shape before route filtering. Existing compute_for_targeting uses
the same query when it needs a raw candidate, so no caller duplicates shape
geometry. The event preview at
deprecated/server_deprecated/event_server.py:3281-3285 calls
get_geometric_footprint(entity.position, target_override=pos) before passing
that footprint to bounded grid.get_barrier_positions. Entity action discovery
at dnd/entities/entity.py:6962 calls it separately for each target_override
inside its existing AoE candidate loop; it no longer computes one global
barrier set. The two public Cylinder paths at
tests/engine/test_grid_pathfinding.py:772-785 use the same method before
subjective and targeting route filtering.

The returned footprint is geometry only, not propagation authority.
get_barrier_positions(footprint) remains bounded acceleration, and the
ordered PROPAGATION evaluator remains the sole transmission authority.

### 3. Corrected exact test envelope

The exact additions to the previously frozen Slice 3.3 test envelope are:

- tests/manual/test_11_equipment_inventory_and_items.py:829-834, explicit
  WEST directional-door recipe for owner (1,0) viewed from (0,0);
- tests/manual/test_72_battlefield_deployment_catalog.py:58-66, retain
  authored WEST placement for both closed and open standard-door rows and
  assert that open state has empty current channels rather than an empty side;
  and
- tests/manual/test_37_authored_encounter_mechanics.py:35,125-127 is reviewed
  and NO EDIT. Its door_at helper only locates the canonical DirectionalDoor
  by type and does not assert blocked_directions, directional_structure, or
  any deleted field. This remains valid while DirectionalDoor remains the
  canonical type.

The corrected complete Slice 3.3 test envelope is therefore:

- tests/engine/test_tile_surface_contract.py;
- tests/engine/test_world_edge_identity_and_elevation.py;
- tests/engine/test_senses_light_stealth.py;
- tests/engine/test_grid_pathfinding.py;
- tests/engine/test_action_discovery.py;
- tests/engine/test_elevation_proving_battlefield.py;
- tests/engine/test_spatial_effects.py;
- tests/engine/test_condition_lifecycle.py;
- tests/engine/test_event_wire_visibility_contract.py;
- tests/engine/test_objective_state.py;
- tests/engine/test_direct_scenario_deployment.py;
- tests/engine/test_items_inventory_equipment.py;
- tests/engine/test_spell_families.py;
- tests/engine/test_move_settlement.py;
- tests/engine/test_action_cost_and_position_commit.py;
- tests/engine/test_traversal_connectors.py;
- tests/engine/test_elevated_jump_transaction.py;
- tests/engine/test_encounter_apis.py;
- tests/engine/test_manual_11_grid_tiles_terrain_movement.py;
- tests/manual/test_08_world_model_and_movement.py;
- tests/manual/test_11_equipment_inventory_and_items.py;
- tests/manual/test_37_authored_encounter_mechanics.py is reviewed/no edit;
- tests/manual/test_72_battlefield_deployment_catalog.py;
- tests/manual/test_97_event_wire_contract.py;
- tests/manual/test_120_player_replication_journal.py;
- tests/manual/test_149_remaining_legacy_contract.py;
- tests/manual/test_117_player_replication_contract.py;
- tests/manual/test_113_subjective_replication_routes.py;
- tests/manual/test_120_subjective_world_projection.py;
- tests/manual/test_125_subjective_objective_render_parity.py;
- tests/manual/test_134_stackable_usable_item_legacy_contract.py;
- tests/manual/test_legacy_reactive_reaction_coverage.py; and
- tests/manual/test_directional_environment_legacy_contract.py.

No test in this envelope is edited in this read-only turn, and Slice 3.3 is
not implemented.

### Final rebind and stop

The 94-member Slice 3.1 code manifest remains unchanged and was reverified
after this append: 94 declared rows, 94 rows, 94 unique members, zero
mismatches, and this Markdown ledger excluded. The appended section is the
only mutation. Its complete-ledger SHA is computed externally and reported
after writing. Stop for final supervisor and independent re-review; do not
begin Slice 3.3.

## Supervised Slice 3.3 implementation — STOPPED at governed generation gate

The frozen Slice 3.2 ledger chose one regeneration unit for the complete
tracked governed generated/deprecated envelope. No affected output family may
be hand-edited or partially refreshed. This implementation turn therefore
stops before a green handoff and before any generated artifact mutation.

### Verified bounded work before the stop

- The frozen governing hashes and 94-member Slice 3.1 manifest were verified
  before editing as required by the supervisor instruction.
- `./.venv/bin/python -m py_compile dnd/core/gridmap.py
  dnd/core/events/world_events.py dnd/core/base_conditions.py
  dnd/spatial/area_conditions.py dnd/items/environment.py
  dnd/actions/standard.py` completed successfully after the bounded core
  edits.
- `./.venv/bin/pytest -q tests/engine/test_tile_surface_contract.py
  --disable-warnings --tb=short` completed `32 passed` after porting that
  authorized public module from deleted directional Tile hooks to ordered
  boundary queries and `BoundaryStructure` provider facts.
- No accepted capability, spell, architecture, full collection, generated
  check, or final candidate manifest is claimed in this stopped checkpoint.

### Exact generation blocker

The required SDK generator path from the frozen envelope does not exist:

```
test -f devtools/generate_typescript_sdk.py
typescript_generator_status=1
```

The only repository event generator found is
`deprecated/devtools_deprecated/generate_event_contract.py`. Its bounded check
also fails in both relevant invocations:

```
./.venv/bin/python deprecated/devtools_deprecated/generate_event_contract.py --check
ModuleNotFoundError: No module named dnd

PYTHONPATH=. ./.venv/bin/python deprecated/devtools_deprecated/generate_event_contract.py --check
ImportError: cannot import name Event from dnd.core.events
```

The first failure follows from the stale generator root/path setup; the second
proves that the script's imported `dnd.core.events.Event` authority is no
longer compatible with the current runtime package. It also targets the old
`server/event_contract.generated.json` location rather than the frozen
`deprecated/server_deprecated/event_contract.generated.json` output. No
approved generator exists for the governed TypeScript source/dist family.

Per the implementation authority, this is a hard STOP: do not invent a
generator, hand-edit generated source/dist files, delete the selected governed
output family, or claim a final Slice 3.3 manifest. The production/test tree
is an unhanded intermediate candidate and requires supervisor direction after
the generator blocker is resolved.

### Stopped-artifact boundary

No Slice 3.3 final manifest was created or bound. The pre-existing Slice 3.1
manifest remains the only valid manifest and does not describe this candidate.
The next authorized continuation must first provide or repair the exact
repository generator for every governed source/output listed in the frozen
Slice 3.2 envelope, then rerun the complete Slice 3.3 gates atomically.
