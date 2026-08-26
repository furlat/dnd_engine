# Phase 6 hard-cut certification implementation ledger

Status: `SLICE_6_0_PREFLIGHT_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

This is the one authorized Slice 6.0 preflight ledger. No production or test
file was edited in Slice 6.0. The Phase 5 accepted dirty work is preserved
exactly; no reset, checkout, clean, commit, broad formatter, dependency
restoration, or excluded-surface edit was used.

## Governing authority verification

| artifact | exact SHA-256 | result |
|---|---|---|
| `DND_TILE_WORLD_ITEM_PHASE_6_HARD_CUT_CERTIFICATION_IMPLEMENTATION_PLAN_2026-08-26.md` | `154b0d9d92cadacbe167ec5908e576398a53377373c94c52862d2746d288f0da` | exact |
| Phase 6 substantive reviewed SHA | `e1b56a6cb29dd64ee2b033eb4e3440e43489f96b4ef409aa56d9319239d8606b` | exact authority metadata |
| `DND_TILE_WORLD_ITEM_VERTICAL_BOUNDARY_MIGRATION_PLAN_2026-08-17.md` | `50411e5575e6336ca0301acf032797cdf1d5ea885df5ccd37d6619f593e7a193` | exact |
| `DND_TILE_WORLD_ITEM_ACTIVE_RUNTIME_SCOPE_AMENDMENT_2026-08-24.md` | `f10e2fbbcb6ba8732d078f0c4f2f5276716eb51e32c083068f3cae93c9ba52d6` | exact |
| `DND_TILE_WORLD_ITEM_PHASE_5_AUTHORED_BOOTSTRAP_IMPLEMENTATION_PLAN_2026-08-26.md` | `892e07aea27cb777fcb6fda6a7f7415d46bd4825a582d5f6001fb383f4a10870` | exact |
| `DND_TILE_WORLD_ITEM_PHASE_5_IMPLEMENTATION_LEDGER_2026-08-26.md` | `b75f690bfe7486d5f63cef3e20a8b8031944e4ae776a4adf4422ef255fe46cfa` | exact |
| `DND_TILE_WORLD_ITEM_PHASE_5_IMPLEMENTATION_MANIFEST_2026-08-26.json` | `c10171e9e64ea96ca93f0b971917aad1824654d950a82bed1b7cb516cbef70b1` | exact |
| `HOW_TO_TEST.MD` | `96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013` | exact |
| `agents.md` | `fcc5dd1e15bae2ff86a7203f42b0c55de4d51dd0d93bc3a3ae059b7e58ee39b1` | exact |

The complete 717-line Phase 6 plan, complete master and scope amendment,
complete Phase 5 plan/ledger/manifest, all 517 lines of HOW_TO_TEST.MD, and
agents.md were read. No revoked or server-oriented authority was used.

## Accepted Phase 5 manifest and baseline

The accepted Phase 5 manifest has exactly 80 sorted unique members: 37
production and 43 tests. Every member was checked against current raw bytes:
zero missing members, zero duplicates, and zero hash mismatches. Its raw-byte
SHA remains `c10171e9e64ea96ca93f0b971917aad1824654d950a82bed1b7cb516cbef70b1`.

The accepted manifest-defined lane was recollected using its frozen path and
selector inputs with `.venv/bin/pytest --collect-only -q -p
no:cacheprovider`, retaining sorted unique node lines containing `::` and
joining them with one terminal newline for SHA-256. It collected exactly 650
nodes with normalized SHA-256
`8202c5f659be52244112818848d40d01f2a358adf3cce17200ccd075e172c2e6`.
Executing that exact newline-safe node set with
`.venv/bin/pytest -q -p no:cacheprovider` returned:
`650 passed in 235.04s (0:03:55)`.

The accepted baseline count and hash therefore match exactly. No production or
test byte changed during manifest verification, collection, or execution.

## Preflight dirty-state snapshot

The exact `git status --short --untracked-files=all` snapshot before creating
this ledger was:

```text
 M dnd/content/scenarios/battlefield_builders.py
 M dnd/content/spike_trap_materialization.py
 M dnd/core/events/item_events.py
 M dnd/core/gridmap.py
 M dnd/items/environment_interactables.py
 M dnd/maps/arena_layout.py
 M tests/engine/test_direct_scenario_deployment.py
 M tests/engine/test_elevation_performance_contract.py
 M tests/engine/test_elevation_proving_battlefield.py
 M tests/manual/test_72_battlefield_deployment_catalog.py
?? DND_TILE_WORLD_ITEM_PHASE_5_AUTHORED_BOOTSTRAP_IMPLEMENTATION_PLAN_2026-08-26.md
?? DND_TILE_WORLD_ITEM_PHASE_5_IMPLEMENTATION_LEDGER_2026-08-26.md
?? DND_TILE_WORLD_ITEM_PHASE_5_IMPLEMENTATION_MANIFEST_2026-08-26.json
?? DND_TILE_WORLD_ITEM_PHASE_6_HARD_CUT_CERTIFICATION_IMPLEMENTATION_PLAN_2026-08-26.md
```

The Phase 5 ten-file implementation candidate and its three governance
artifacts are accepted input. The Phase 6 plan is also accepted input. The
only new repository artifact authorized by this checkpoint is this ledger.

## Repository-wide diagnostic baseline

Exact command:

```text
.venv/bin/python -m pytest --collect-only -q -p no:cacheprovider
```

Result: exit status `2`; `1382 tests collected, 105 errors in 19.94s`.
The terminal exception classes are 97 `ModuleNotFoundError`, 4 `ImportError`,
and 4 `FileNotFoundError`. The stable normalized signature is the sorted tuple
of `(collecting test path, terminal exception class, root-normalized terminal
exception message)`. Checkout prefixes in exception messages were replaced by
`<CHECKOUT>`; traceback line numbers, ordering, elapsed time, and pytest
decoration were excluded. The planning signature SHA-256 is the authority
value `eccd100453848ac9af6a6e028692862dbf0866daaf0c0e3d275b13d4d4e06cd9`.

The exact rows and governed classification are recorded below. Group counts
are: 57 `MISSING_DND_CONTENT_SYSTEM`, 15 `MISSING_SERVER`, and 33
`REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL`. No row belongs to the
accepted active 650-node lane.

## Exact active envelope and 19-node expansion

The initial production envelope declared by Phase 6 Section 7.1 is exactly:

- `dnd/core/base_block.py`
- `dnd/core/base_tiles.py`
- `dnd/core/gridmap.py`
- `dnd/core/base_actions.py`
- `dnd/core/events/world_events.py`
- `dnd/blocks/base_item.py`
- `dnd/blocks/sensory.py`
- `dnd/entities/entity.py` only if the neutral position boundary requires it
- `dnd/spatial/area_conditions.py`
- `dnd/content/scenarios/battlefield_definitions.py`
- `dnd/content/scenarios/battlefield_builders.py`
- `dnd/maps/arena_layout.py`
- active world-item definitions/builders/subclasses proven by the caller audit

The maintained test envelope is the 43 accepted Phase 5 manifest test members
plus the four additional collecting files explicitly admitted by Section 7.2:
`tests/manual/test_84_generic_roster_duels.py`,
`tests/manual/test_150_prepared_scenario_lifecycle.py`,
`tests/engine/test_progressive_elevation_movement.py`, and
`tests/engine/test_spatial_effect_reveal_idempotency.py`. The accepted
`tests/engine/test_combat_actions.py` member supplies the additional combat
selector. No blocked server/content-system/presentation module was admitted.

The exact 19-node collection command was:

```text
.venv/bin/pytest --collect-only -q -p no:cacheprovider \
  tests/manual/test_84_generic_roster_duels.py \
  tests/manual/test_150_prepared_scenario_lifecycle.py \
  tests/engine/test_progressive_elevation_movement.py \
  tests/engine/test_spatial_effect_reveal_idempotency.py \
  tests/engine/test_combat_actions.py::test_eb_10_021_forced_movement_traverses_terrain_without_step_costs
```

It collected exactly 19 nodes, with sorted newline-normalized SHA-256
`3f6cce7327dde51e1bc9b5654e518de8cf87fcd41422915dc48d27105b69d57a`.
The nodes are the three generic roster duel tests, one prepared-scenario
lifecycle test, eight progressive-elevation movement tests, six spatial-effect
reveal-idempotency tests, and the one forced-movement terrain-cost test. They
are characterized now but are not executed or modified in Slice 6.0.

## Slice 6.0 checkpoint

The accepted authorities, 80-member manifest, 650-node count/hash, and green
baseline execution all match exactly. The repository-wide diagnostic consists
only of the three already governed excluded families and introduces no active
geometry failure. The AST/runtime-schema inventory and complete 105-row
diagnostic table follow in this same ledger. No production or test edit was
made.

Status: `READY_FOR_COORDINATOR_REVIEW`.
| 36 | `tests/manual/test_131_inventory_use_actions_legacy_contract.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 37 | `tests/manual/test_132_barbarian_unarmored_defense.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 38 | `tests/manual/test_134_stackable_usable_item_legacy_contract.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 39 | `tests/manual/test_135_cleric_batches_2_4_5_legacy_contract.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 40 | `tests/manual/test_135_stealth_lighting_legacy_contract.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 41 | `tests/manual/test_138_skeleton_units_legacy_contract.py` | `ModuleNotFoundError` | `No module named 'dnd.monsters.circus_fighter'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 42 | `tests/manual/test_139_condition_presentation_contract.py` | `ModuleNotFoundError` | `No module named 'devtools'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 43 | `tests/manual/test_142_item_equip_hooks_legacy_contract.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 44 | `tests/manual/test_144_handler_toggle_legacy_contract.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 45 | `tests/manual/test_145_haste_legacy_manifest.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 46 | `tests/manual/test_149_remaining_legacy_contract.py` | `ModuleNotFoundError` | `No module named 'server'` | `MISSING_SERVER` |
| 47 | `tests/manual/test_166_club_content_factory.py` | `FileNotFoundError` | `[Errno 2] No such file or directory: '<CHECKOUT>/content_data/ledgers/neuroclient_authored_item_visuals.json'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 48 | `tests/manual/test_167_srd_weapon_content_factories.py` | `FileNotFoundError` | `[Errno 2] No such file or directory: '<CHECKOUT>/content_data/ledgers/neuroclient_authored_item_visuals.json'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 49 | `tests/manual/test_169_neurodragon_weapon_content_factories.py` | `FileNotFoundError` | `[Errno 2] No such file or directory: '<CHECKOUT>/content_data/ledgers/neuroclient_authored_item_visuals.json'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 50 | `tests/manual/test_170_neurodragon_consumable_content_factories.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 51 | `tests/manual/test_174_premade_character_composition.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 52 | `tests/manual/test_175_character_runtime_materialization.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 53 | `tests/manual/test_178_remaining_possession_item_roots.py` | `ModuleNotFoundError` | `No module named 'dnd.monsters.circus_fighter'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 54 | `tests/manual/test_180_srd_creature_possession_bindings.py` | `ImportError` | `cannot import name 'EquippedVisualPolicy' from 'dnd.presentation' (<CHECKOUT>/dnd/presentation.py)` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 55 | `tests/manual/test_189_game_creation_visual_preview.py` | `ModuleNotFoundError` | `No module named 'server'` | `MISSING_SERVER` |
| 56 | `tests/manual/test_18_sessions_api_client_contract.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 57 | `tests/manual/test_193_game_creation_composition.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 58 | `tests/manual/test_20_content_extension_basics.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 59 | `tests/manual/test_21_spell_and_feature_extensions.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 60 | `tests/manual/test_25_live_replication_streams.py` | `ModuleNotFoundError` | `No module named 'dnd.monsters.bestiary_content'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 61 | `tests/manual/test_43_runtime_performance.py` | `ModuleNotFoundError` | `No module named 'server'` | `MISSING_SERVER` |
| 62 | `tests/manual/test_50_movement_revalidation.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 63 | `tests/manual/test_51_srd_monster_roster.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 64 | `tests/manual/test_96_game_creation_api.py` | `ModuleNotFoundError` | `No module named 'dnd.scenarios.encounter_catalog'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 65 | `tests/manual/test_97_event_wire_contract.py` | `ModuleNotFoundError` | `No module named 'server'` | `MISSING_SERVER` |
| 66 | `tests/manual/test_directional_environment_legacy_contract.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 67 | `tests/manual/test_legacy_reactive_reaction_coverage.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 68 | `tests/manual/test_neurodragon_apparel_content_factories.py` | `FileNotFoundError` | `[Errno 2] No such file or directory: '<CHECKOUT>/content_data/ledgers/neuroclient_authored_item_visuals.json'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 69 | `tests/manual/test_neurodragon_spell_item_content_factories.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 70 | `tests/manual/test_protection_reaction_legacy_contract.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 71 | `tests/manual/test_remaining_spell_legacy_contract.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 72 | `tests/manual/test_srd_armor_content_factories.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 73 | `tests/manual/test_srd_creature_content_factories.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 74 | `tests/progression/test_barbarian_berserker_materialization.py` | `ModuleNotFoundError` | `No module named 'dnd.classes.barbarian_progression_definitions'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 75 | `tests/progression/test_barbarian_character_grant_appliers.py` | `ModuleNotFoundError` | `No module named 'dnd.classes.barbarian_progression_definitions'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 76 | `tests/progression/test_barbarian_progression_definitions.py` | `ModuleNotFoundError` | `No module named 'dnd.classes.barbarian_progression_definitions'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 77 | `tests/progression/test_bg3_spell_action_economy.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 78 | `tests/progression/test_builtin_character_origins.py` | `ModuleNotFoundError` | `No module named 'dnd.classes.barbarian_progression_definitions'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 79 | `tests/progression/test_character_appearance.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 80 | `tests/progression/test_character_build_validation.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 81 | `tests/progression/test_character_grant_receipt_cleanup.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 82 | `tests/progression/test_dependency_neutral_progression_foundation.py` | `ModuleNotFoundError` | `No module named 'dnd.core.content.registry'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 83 | `tests/progression/test_dwarf_acolyte_authored_content.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 84 | `tests/progression/test_editable_character_creation_plans.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 85 | `tests/progression/test_fighter_champion_materialization.py` | `ModuleNotFoundError` | `No module named 'dnd.classes.progression_definitions'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 86 | `tests/progression/test_fighter_character_grant_appliers.py` | `ModuleNotFoundError` | `No module named 'dnd.classes.progression_definitions'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 87 | `tests/progression/test_fighter_progression_definitions.py` | `ModuleNotFoundError` | `No module named 'dnd.classes.progression_definitions'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 88 | `tests/progression/test_multiclass_composition.py` | `ModuleNotFoundError` | `No module named 'dnd.classes.barbarian_progression_definitions'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 89 | `tests/progression/test_origin_feature_contract.py` | `ImportError` | `cannot import name 'OriginCapability' from 'dnd.core.content.origin_features' (<CHECKOUT>/dnd/core/content/origin_features.py)` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 90 | `tests/progression/test_origin_feature_definitions.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 91 | `tests/progression/test_origin_innate_spellcasting.py` | `ModuleNotFoundError` | `No module named 'dnd.classes.progression_definitions'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 92 | `tests/progression/test_origin_integration_matrix.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 93 | `tests/progression/test_origin_structural_feature_applier.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 94 | `tests/progression/test_origin_structural_primitives.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 95 | `tests/progression/test_player_character_body.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 96 | `tests/progression/test_saving_throw_context.py` | `ImportError` | `cannot import name 'OriginCapability' from 'dnd.core.content.origin_features' (<CHECKOUT>/dnd/core/content/origin_features.py)` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 97 | `tests/progression/test_schema2_character_materialization.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 98 | `tests/progression/test_schema2_sorcerer_runtime_actions.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 99 | `tests/progression/test_sorcerer_character_grant_appliers.py` | `ModuleNotFoundError` | `No module named 'dnd.classes.sorcerer_progression_definitions'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 100 | `tests/progression/test_sorcerer_class_materialization.py` | `ModuleNotFoundError` | `No module named 'dnd.classes.sorcerer_progression_definitions'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 101 | `tests/progression/test_sorcerer_progression_definitions.py` | `ModuleNotFoundError` | `No module named 'dnd.classes.sorcerer_progression_definitions'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 102 | `tests/progression/test_sorcerer_spell_source_materialization.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 103 | `tests/progression/test_starting_apparel_packages.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 104 | `tests/progression/test_starting_equipment_packages.py` | `ModuleNotFoundError` | `No module named 'dnd.classes.barbarian_progression_definitions'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 105 | `tests/progression/test_structural_class_feature_definitions.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
## Semantic AST inventory of the eight governed symbol spellings (corrected)

The AST pass found 249 active input files and the raw lexical totals below. A spelling is not classified by whole file: every decision is made against its qualified owner, receiver, field declaration, or call boundary. Ordinary coordinate values and the four accepted direct owners are retained; only the retired neutral/runtime seams are migration rows.

### Qualified semantic classification

| spelling | exact qualified occurrence | decision | bounded active scope |
|---|---|---|---|
| `position` | `BaseBlock.position`, `BaseBlock.get_position`, recursive `BaseBlock.set_position`, and the inherited `BaseItem` coordinate schema | `MUST_MIGRATE` | `dnd/core/base_block.py`, `dnd/blocks/base_item.py`; `set_position` is the one exact AST row at `base_block.py:336` |
| `position` | Generic `BaseBlock` reads: `BaseAction.target_resolution_sort_key` target coordinate, `BaseAction.get_all_targets` `source_block.position`, and GridMap generic `block.position` membership validation | `MUST_MIGRATE` | `dnd/core/base_actions.py:93,990`; `dnd/core/gridmap.py:2133,2137`; these are admitted existing core envelope paths |
| `position` | Direct `Tile.position`, `Entity/EntityConfig.position`, `SpatialCondition/AreaCondition.position`, `Senses.position`, and ordinary event/placement/connector/target/config coordinates | `VALID_RETAINED` | Qualified owners/values in core, entities, spatial, event, placement, action, scenario, spell, and test code; no whole-file migration follows from the spelling |
| `position` | Test occurrences whose qualified receiver is the retired generic `BaseBlock`/inherited `BaseItem` coordinate seam | `MUST_MIGRATE_OR_PUBLIC_PROOF` | Only the affected selectors in the 47-file maintained test envelope; ordinary tuple coordinates and accepted-owner assertions remain `VALID_RETAINED` |
| `set_position` | `BaseBlock.set_position` recursive neutral mutator | `MUST_MIGRATE` | `dnd/core/base_block.py` only |
| `walkable` | `Senses.walkable` and the public `GridMap.is_walkable` derived query | `VALID_RETAINED` | Reducer-owned subjective state and public derived query; no Tile authority is implied |
| `walkable` | `Tile.walkable`, `BattlefieldTileDefinition.walkable`, `WorldTileState.walkable`, GridMap Tile reads/constructor arguments, and authored arena surface arguments | `MUST_MIGRATE` | `dnd/core/base_tiles.py`, `dnd/core/gridmap.py`, `dnd/core/events/world_events.py`, `dnd/content/scenarios/battlefield_definitions.py`, `dnd/content/scenarios/battlefield_builders.py`, `dnd/maps/arena_layout.py` |
| `walkable` | `SpatialCondition` reads of Tile walkability and maintained tests asserting the retired Tile/world surface | `MUST_MIGRATE_OR_PUBLIC_PROOF` | `dnd/spatial/area_conditions.py` plus only the qualified public test rows in the maintained envelope |
| `tile_walkable` | Serialized `SpatialChangeEvent`/`TileElevationChangeEvent` field and GridMap world-event construction | `MUST_MIGRATE` | `dnd/core/events/world_events.py`, `dnd/core/gridmap.py` |
| `sprite_name` | Tile-owned `sprite_name` schema/constructor/read path | `MUST_MIGRATE` | `dnd/core/base_tiles.py`, `dnd/core/gridmap.py` |
| `sprite_name` | Entity/EntityConfig/Appearance presentation field | `VALID_RETAINED` | `dnd/entities/entity.py`, `dnd/entities/entity_creation.py` |
| `map_char` | Runtime BaseItem field, every active BaseItem subclass declaration, and active constructor keyword/read into that runtime field (including Field Kit, Heroes' Feast, consumables, and environment items) | `MUST_MIGRATE` | Existing 37-file production envelope plus active transitive additions `dnd/items/consumables.py`, `dnd/items/spell_items.py`, `dnd/extensions/field_focus.py`; `dnd/blocks/equipment.py`, torches, environment builders, and authored builders are already in scope |
| `visual_item_name`, `visual_variant_id` | Runtime BaseItem fields, inherited schemas, active BaseItem subclass declarations, and active constructor keywords into those fields | `MUST_MIGRATE` | `dnd/blocks/base_item.py` and active transitive runtime item paths, especially `dnd/items/spell_items.py` and the existing authored item builders; no subclass redeclaration is a retention strategy |
| `map_char`, `visual_item_name`, `visual_variant_id` | Semantic `ContentRef`, authored definition/package, or non-runtime variant data that does not declare/read a BaseItem renderer field | `VALID_RETAINED` | Retain only the qualified content identity/data occurrence, not a runtime BaseItem field |
| `map_char`, `visual_item_name`, `visual_variant_id` | Source rows in `dnd/items/armors.py`, `dnd/items/weapons.py`, `dnd/items/authored_variant_inventory.py`, `dnd/items/authored_variant_presets.py`, and `dnd/items/visual_variants.py` not reached by the accepted collecting/import graph | `GOVERNED_EXCLUDED / STOP-ONLY` | These are not silently ported or relabeled as valid runtime fields; if a later active caller reaches one, Slice 6 must stop and admit the exact path |

### Raw AST count appendix (lexical counts only)

These are the exact pre-classification AST counts, retained to make the semantic audit reproducible without using them as whole-file migration claims.
`position`: 2206 matches — dnd/actions/operations.py=14; dnd/actions/reactions.py=1; dnd/actions/standard.py=64; dnd/analytics/models.py=2; dnd/blocks/base_item.py=6; dnd/blocks/sensory.py=91; dnd/classes/sorcerer.py=3; dnd/conditions.py=6; dnd/content/scenarios/battlefield_builders.py=55; dnd/content/scenarios/battlefield_definitions.py=8; dnd/content/scenarios/scenario_compatibility.py=25; dnd/content/scenarios/scenario_definitions.py=9; dnd/content/scenarios/scenario_deployment.py=1; dnd/content/spatial_effect_materialization.py=3; dnd/content/spike_trap_materialization.py=1; dnd/core/aoe.py=1; dnd/core/base_actions.py=9; dnd/core/base_block.py=13; dnd/core/base_conditions.py=6; dnd/core/base_tiles.py=16; dnd/core/combat_log.py=5; dnd/core/content/materialization.py=2; dnd/core/elevation.py=5; dnd/core/events/events_registry.py=6; dnd/core/events/world_events.py=50; dnd/core/gridmap.py=294; dnd/core/traversal_connectors.py=4; dnd/core/world_edges.py=16; dnd/entities/creature_transforms.py=2; dnd/entities/entity.py=174; dnd/entities/entity_creation.py=4; dnd/game.py=2; dnd/items/torches.py=14; dnd/maps/arena_layout.py=17; dnd/monsters/traits.py=17; dnd/origins/dragonborn.py=1; dnd/spatial/area_conditions.py=79; dnd/spatial/environmental_conditions.py=3; dnd/spatial/memberships.py=2; dnd/spells/abjuration.py=35; dnd/spells/conjuration.py=53; dnd/spells/enchantment.py=13; dnd/spells/evocation.py=41; dnd/spells/illusion.py=7; dnd/spells/necromancy.py=15; dnd/spells/transmutation.py=6; dnd/types/senses.py=5; dnd/types/world_placement.py=2; tests/engine/test_action_cost_and_position_commit.py=16; tests/engine/test_action_discovery.py=35; tests/engine/test_combat_actions.py=102; tests/engine/test_condition_lifecycle.py=27; tests/engine/test_condition_transform_ownership.py=12; tests/engine/test_direct_scenario_deployment.py=9; tests/engine/test_direct_spatial_effect_materialization.py=3; tests/engine/test_elevated_jump_transaction.py=14; tests/engine/test_elevation_performance_contract.py=7; tests/engine/test_elevation_proving_battlefield.py=17; tests/engine/test_entity_composition.py=7; tests/engine/test_event_wire_visibility_contract.py=6; tests/engine/test_grid_pathfinding.py=42; tests/engine/test_items_inventory_equipment.py=40; tests/engine/test_life_state_ownership.py=13; tests/engine/test_manual_07_entity_composition.py=4; tests/engine/test_manual_09_conditions.py=3; tests/engine/test_manual_10_standard_conditions.py=7; tests/engine/test_manual_11_grid_tiles_terrain_movement.py=10; tests/engine/test_move_settlement.py=16; tests/engine/test_objective_state.py=8; tests/engine/test_progressive_elevation_movement.py=9; tests/engine/test_runtime_identity_registries.py=16; tests/engine/test_senses_light_stealth.py=78; tests/engine/test_spatial_effect_reveal_idempotency.py=1; tests/engine/test_spatial_effects.py=29; tests/engine/test_spell_families.py=169; tests/engine/test_tile_surface_contract.py=50; tests/engine/test_traversal_connectors.py=47; tests/engine/test_world_edge_identity_and_elevation.py=4; tests/manual/test_01_runtime_identity_and_registries.py=6; tests/manual/test_02_entity_anatomy.py=5; tests/manual/test_08_world_model_and_movement.py=15; tests/manual/test_10_combat_resolution.py=27; tests/manual/test_128_antimagic_field.py=9; tests/manual/test_133_new_spells_batch4_legacy_contract.py=19; tests/manual/test_13_spellcasting_core.py=3; tests/manual/test_14_spell_families.py=11; tests/manual/test_17_encounters_turns_controllers.py=6; tests/manual/test_37_authored_encounter_mechanics.py=29; tests/manual/test_53_srd_monster_traits.py=49; tests/manual/test_72_battlefield_deployment_catalog.py=16; tests/manual/test_84_generic_roster_duels.py=2
`set_position`: 1 matches — dnd/core/base_block.py=1
`walkable`: 75 matches — dnd/blocks/sensory.py=8; dnd/content/scenarios/battlefield_builders.py=8; dnd/content/scenarios/battlefield_definitions.py=2; dnd/core/base_tiles.py=12; dnd/core/events/world_events.py=4; dnd/core/gridmap.py=11; dnd/entities/entity.py=5; dnd/maps/arena_layout.py=2; dnd/spatial/area_conditions.py=2; tests/engine/test_action_discovery.py=1; tests/engine/test_elevation_proving_battlefield.py=1; tests/engine/test_event_wire_visibility_contract.py=1; tests/engine/test_grid_pathfinding.py=4; tests/engine/test_spell_families.py=3; tests/manual/test_08_world_model_and_movement.py=2; tests/manual/test_37_authored_encounter_mechanics.py=6; tests/manual/test_72_battlefield_deployment_catalog.py=3
`tile_walkable`: 6 matches — dnd/core/events/world_events.py=3; dnd/core/gridmap.py=3
`sprite_name`: 22 matches — dnd/core/base_tiles.py=10; dnd/core/gridmap.py=6; dnd/entities/entity.py=4; dnd/entities/entity_creation.py=2
`map_char`: 37 matches — dnd/blocks/base_item.py=3; dnd/blocks/equipment.py=6; dnd/content/items/authored_item_builders.py=1; dnd/content/items/environment_item_builders.py=1; dnd/extensions/field_focus.py=2; dnd/items/consumables.py=6; dnd/items/environment.py=4; dnd/items/environment_interactables.py=4; dnd/items/spell_items.py=4; dnd/items/torches.py=4; dnd/spells/conjuration.py=2
`visual_item_name`: 33 matches — dnd/blocks/base_item.py=2; dnd/items/armors.py=23; dnd/items/spell_items.py=4; dnd/items/weapons.py=4
`visual_variant_id`: 46 matches — dnd/blocks/base_item.py=2; dnd/items/armors.py=22; dnd/items/authored_variant_inventory.py=5; dnd/items/authored_variant_presets.py=3; dnd/items/spell_items.py=4; dnd/items/visual_variants.py=2; dnd/items/weapons.py=8

The repository-wide blocked test rows are governed excluded by the 105-row diagnostic above. The inactive/generated production exclusions are `dnd/items/environment_content.py` and `dnd/core/content/icon_bindings_generated.py`; neither is a Slice 6 input. No AST spelling alone expands the envelope.
## Runtime Pydantic schema inventory

The runtime schema pass imported the active model modules and recorded the exact public field names for every governed spelling. No import failed and no fallback schema was used.

Command: `.venv/bin/python` schema introspection over the active model classes in `dnd.core.base_block`, `dnd.blocks.base_item`, `dnd.core.base_tiles`, `dnd.core.events.world_events`, `dnd.content.scenarios.battlefield_definitions`, `dnd.entities.entity`, `dnd.blocks.sensory`, `dnd.spatial.area_conditions`, `dnd.core.base_actions`, and `dnd.types.world_placement`.

| module | model | exact public schema fields | classification |
|---|---|---|---|
| `dnd.core.base_block` | `BaseBlock` | `position` | MUST_MIGRATE generic neutral seam |
| `dnd.blocks.base_item` | `BaseItem` | `map_char, position, visual_item_name, visual_variant_id` | MUST_MIGRATE: no runtime renderer fields or neutral coordinate inherited here |
| `dnd.blocks.base_item` | `WorldItem` | `map_char, position, visual_item_name, visual_variant_id` | MUST_MIGRATE world-item boundary fields |
| `dnd.blocks.base_item` | `EquippableItem` | `map_char, position, visual_item_name, visual_variant_id` | MUST_MIGRATE inherited runtime BaseItem fields; no subclass redeclaration |
| `dnd.blocks.base_item` | `UsableItem` | `map_char, position, visual_item_name, visual_variant_id` | MUST_MIGRATE inherited runtime BaseItem fields; no subclass redeclaration |
| `dnd.core.base_tiles` | `Tile` | `position, sprite_name, walkable` | `Tile.position` VALID_RETAINED; `sprite_name` and `walkable` MUST_MIGRATE |
| `dnd.core.events.world_events` | `WorldTileState` | `position, walkable` | MUST_MIGRATE serialized world surface |
| `dnd.core.events.world_events` | `SpatialChangeEvent` | `position, tile_walkable` | MUST_MIGRATE world-event schema |
| `dnd.core.events.world_events` | `TileElevationChangeEvent` | `position, tile_walkable` | MUST_MIGRATE world-event schema |
| `dnd.content.scenarios.battlefield_definitions` | `BattlefieldTileDefinition` | `position, walkable` | MUST_MIGRATE authored surface input |
| `dnd.content.scenarios.battlefield_definitions` | `BattlefieldObjectDefinition` | `position` | VALID_RETAINED authored identity/placement input |
| `dnd.content.scenarios.battlefield_definitions` | `BattlefieldElevationDefinition` | `position` | VALID_RETAINED authored geometry input |
| `dnd.entities.entity` | `EntityConfig` | `position, sprite_name` | VALID_RETAINED Entity objective/presentation authority |
| `dnd.entities.entity` | `Entity` | `position, sprite_name` | VALID_RETAINED Entity objective/presentation authority |
| `dnd.blocks.sensory` | `Senses` | `position, walkable` | VALID_RETAINED reducer-owned subjective snapshot |
| `dnd.spatial.area_conditions` | `SpatialCondition` | `position` | VALID_RETAINED condition anchor/identity seam |
| `dnd.spatial.area_conditions` | `AreaCondition` | `position` | VALID_RETAINED condition anchor/identity seam |
| `dnd.core.base_actions` | `AvailableTarget` | `position` | VALID_RETAINED target projection |
| `dnd.types.world_placement` | `WorldObjectPlacement` | `position` | VALID_RETAINED placement authority |

## Exact active file envelope for later Slice 6 changes

The 37 accepted Phase 5 production members are:

- `dnd/actions/standard.py`
- `dnd/blocks/base_item.py`
- `dnd/blocks/equipment.py`
- `dnd/blocks/inventory.py`
- `dnd/blocks/sensory.py`
- `dnd/content/items/authored_item_builders.py`
- `dnd/content/items/authored_item_definitions.py`
- `dnd/content/items/environment_item_builders.py`
- `dnd/content/items/item_catalog.py`
- `dnd/content/scenarios/battlefield_builders.py`
- `dnd/content/scenarios/battlefield_definitions.py`
- `dnd/content/scenarios/scenario_compatibility.py`
- `dnd/content/spike_trap_materialization.py`
- `dnd/core/aoe.py`
- `dnd/core/base_block.py`
- `dnd/core/base_conditions.py`
- `dnd/core/base_tiles.py`
- `dnd/core/events/item_events.py`
- `dnd/core/events/world_events.py`
- `dnd/core/gridmap.py`
- `dnd/core/world_edges.py`
- `dnd/entities/entity.py`
- `dnd/game.py`
- `dnd/items/environment.py`
- `dnd/items/environment_interactables.py`
- `dnd/items/torches.py`
- `dnd/maps/arena_layout.py`
- `dnd/monsters/traits.py`
- `dnd/runtime_reset.py`
- `dnd/spatial/area_conditions.py`
- `dnd/spells/abjuration.py`
- `dnd/spells/conjuration.py`
- `dnd/spells/evocation.py`
- `dnd/spells/necromancy.py`
- `dnd/types/items.py`
- `dnd/types/materials.py`
- `dnd/types/world_placement.py`

The maintained test envelope is the 43 accepted Phase 5 test members plus the four newly admitted collecting files, deduplicated to 47 files:

- `tests/architecture/test_content_ledger_boundary.py`
- `tests/architecture/test_dependency_boundaries.py`
- `tests/engine/test_action_cost_and_position_commit.py`
- `tests/engine/test_action_discovery.py`
- `tests/engine/test_combat_actions.py`
- `tests/engine/test_condition_lifecycle.py`
- `tests/engine/test_condition_transform_ownership.py`
- `tests/engine/test_direct_scenario_deployment.py`
- `tests/engine/test_direct_spatial_effect_materialization.py`
- `tests/engine/test_elevated_jump_transaction.py`
- `tests/engine/test_elevation_performance_contract.py`
- `tests/engine/test_elevation_proving_battlefield.py`
- `tests/engine/test_entity_composition.py`
- `tests/engine/test_event_wire_visibility_contract.py`
- `tests/engine/test_grid_pathfinding.py`
- `tests/engine/test_items_inventory_equipment.py`
- `tests/engine/test_life_state_ownership.py`
- `tests/engine/test_manual_07_entity_composition.py`
- `tests/engine/test_manual_09_conditions.py`
- `tests/engine/test_manual_10_standard_conditions.py`
- `tests/engine/test_manual_11_grid_tiles_terrain_movement.py`
- `tests/engine/test_move_settlement.py`
- `tests/engine/test_objective_state.py`
- `tests/engine/test_progressive_elevation_movement.py`
- `tests/engine/test_runtime_identity_registries.py`
- `tests/engine/test_runtime_reset.py`
- `tests/engine/test_senses_light_stealth.py`
- `tests/engine/test_spatial_effect_reveal_idempotency.py`
- `tests/engine/test_spatial_effects.py`
- `tests/engine/test_spell_families.py`
- `tests/engine/test_tile_surface_contract.py`
- `tests/engine/test_traversal_connectors.py`
- `tests/engine/test_world_edge_identity_and_elevation.py`
- `tests/manual/test_01_runtime_identity_and_registries.py`
- `tests/manual/test_02_entity_anatomy.py`
- `tests/manual/test_08_world_model_and_movement.py`
- `tests/manual/test_10_combat_resolution.py`
- `tests/manual/test_128_antimagic_field.py`
- `tests/manual/test_133_new_spells_batch4_legacy_contract.py`
- `tests/manual/test_13_spellcasting_core.py`
- `tests/manual/test_14_spell_families.py`
- `tests/manual/test_150_prepared_scenario_lifecycle.py`
- `tests/manual/test_17_encounters_turns_controllers.py`
- `tests/manual/test_37_authored_encounter_mechanics.py`
- `tests/manual/test_53_srd_monster_traits.py`
- `tests/manual/test_72_battlefield_deployment_catalog.py`
- `tests/manual/test_84_generic_roster_duels.py`

The exact later-slice production envelope is the accepted 37 members above plus these three active transitive runtime-item paths proven by the accepted collecting/import graph: `dnd/items/consumables.py`, `dnd/items/spell_items.py`, and `dnd/extensions/field_focus.py`. The already accepted 37 members include the active environment, torch, authored-item, and equipment paths. The exact maintained test envelope is the 47 files above; only qualified retired-seam test rows are migration/proof rows, while ordinary coordinates and accepted-owner assertions remain retained.

The following source paths are stop-only governed inactive residue for this audit, not silent migration scope: `dnd/items/armors.py`, `dnd/items/weapons.py`, `dnd/items/authored_variant_inventory.py`, `dnd/items/authored_variant_presets.py`, and `dnd/items/visual_variants.py`. They are not reached by the accepted 650 collecting/import graph. If a later active caller reaches one, stop and admit that exact path. `dnd/items/environment_content.py`, `dnd/core/content/icon_bindings_generated.py`, and all 105 diagnostic rows remain governed excluded. No other active production path is marked MUST_MIGRATE without being in the envelope above.

## Slice 6.0 final checkpoint

- Authority hashes, complete plan reads, accepted Phase 5 manifest (80/80 current hashes), and accepted 650-node baseline were verified.
- Exact accepted baseline: 650 collected/executed, normalized node SHA `8202c5f659be52244112818848d40d01f2a358adf3cce17200ccd075e172c2e6`; execution `650 passed in 235.04s (0:03:55)`.
- Repository diagnostic: exact command returned exit 2 with `1382 tests collected, 105 errors in 19.94s`; normalized planning signature authority `eccd100453848ac9af6a6e028692862dbf0866daaf0c0e3d275b13d4d4e06cd9`; group counts `57/15/33`; all rows are governed excluded.
- Exact 19-node expansion collected `19`, normalized SHA `3f6cce7327dde51e1bc9b5654e518de8cf87fcd41422915dc48d27105b69d57a`; it was characterized only and not executed in Slice 6.0.
- The exact 19 node IDs were: `tests/manual/test_84_generic_roster_duels.py::test_generic_duel_assembles_two_multi_actor_creature_rosters`, `tests/manual/test_84_generic_roster_duels.py::test_mirrored_roster_keeps_runtime_identity_isolated_by_faction`, `tests/manual/test_84_generic_roster_duels.py::test_character_style_and_creature_rosters_share_one_assembler`, `tests/manual/test_150_prepared_scenario_lifecycle.py::test_prepared_scenario_does_not_start_before_final_controllers_are_installed`, the eight nodes `test_walking_height_change_requires_both_matching_progressive_endpoints`, `test_cliffs_block_walk_swim_burrow_and_forced_displacement_but_not_fly`, `test_forced_movement_revalidates_each_leg_after_effect_topology_change`, `test_diagonal_plateau_needs_one_height_legal_cardinal_bridge`, `test_walking_like_diagonal_cannot_change_endpoint_elevation`, `test_fly_path_and_move_settlement_use_one_support_distance_cost`, `test_flying_discovery_uses_directed_edge_costs_and_affordability`, and `test_progressive_walking_cost_uses_destination_terrain_not_vertical_distance` in `tests/engine/test_progressive_elevation_movement.py`, the six nodes `test_hidden_effect_reveals_once_then_becomes_a_true_noop`, `test_installed_visible_effect_does_not_invent_a_reveal`, `test_uninstalled_effect_cannot_be_revealed`, `test_reveal_veto_preserves_concealment_and_allows_one_later_reveal`, `test_reentrant_reveal_request_does_not_create_a_nested_lifecycle`, and `test_retired_revealed_effect_still_fails_installation_check_first` in `tests/engine/test_spatial_effect_reveal_idempotency.py`, and `tests/engine/test_combat_actions.py::test_eb_10_021_forced_movement_traverses_terrain_without_step_costs`.
- No production or test file was edited. The only new repository artifact is this append-only ledger; the Phase 5 dirty files and governance artifacts remain untouched.
- This ledger-only correction removes the prior path-level false positives, corrects all BaseItem runtime-field classifications, distinguishes Tile sprite/walkability from retained Entity/Senses fields, and makes the production envelope self-consistent. No production or test byte changed; no 650-node rerun was required.
- No active caller outside the corrected envelope, missing manifest member, or baseline drift was found.

## Coordinator acceptance and Slice 6.1 start

Coordinator accepted the corrected Slice 6.0 preflight at ledger SHA
`a5e6cc429e55d9c9bf0662a5ffec7c5ec65e1f5df5bd840bdd5d7a1f630484c6`.
The accepted Phase 5 manifest, baseline, diagnostic, semantic classifications,
and bounded envelope were independently confirmed. Slice 6.1 now begins as the
sole authorized implementation cut; no Slice 6.2, 6.3, 6.4, or final
certification work is included.

Status: `READY_FOR_COORDINATOR_REVIEW`.

## Slice 6.1 implementation checkpoint

Slice 6.1 was implemented as the authorized objective-position hard cut only.
Slice 6.2 movement/walkability/event work, Slice 6.3 renderer-field work,
Slice 6.4 proof closure, and final certification were not started.

### Governing boundary and changed paths

The accepted Slice 6.0 ledger SHA before this checkpoint was
`a5e6cc429e55d9c9bf0662a5ffec7c5ec65e1f5df5bd840bdd5d7a1f630484c6`.
The Phase 6 plan remained the verified final SHA
`154b0d9d92cadacbe167ec5908e576398a53377373c94c52862d2746d288f0da`.
No plan, Phase 5 manifest, Phase 5 ledger, or excluded-scope file was edited.

The exact Slice 6.1 implementation paths were seven active production files
and two active test files:

- Production: `dnd/core/base_block.py`, `dnd/core/base_actions.py`,
  `dnd/core/base_tiles.py`, `dnd/core/gridmap.py`, `dnd/entities/entity.py`,
  `dnd/blocks/sensory.py`, `dnd/spatial/area_conditions.py`.
- Tests: `tests/engine/test_runtime_identity_registries.py`,
  `tests/engine/test_world_edge_identity_and_elevation.py`.

The existing Phase 5 dirty paths and governance artifacts remained unchanged:
`dnd/content/scenarios/battlefield_builders.py`,
`dnd/content/spike_trap_materialization.py`, `dnd/core/events/item_events.py`,
`dnd/items/environment_interactables.py`, `dnd/maps/arena_layout.py`,
`tests/engine/test_direct_scenario_deployment.py`,
`tests/engine/test_elevation_performance_contract.py`,
`tests/engine/test_elevation_proving_battlefield.py`, and
`tests/manual/test_72_battlefield_deployment_catalog.py`, plus the accepted
Phase 5/6 governance documents already listed above.

### Implementation result

- `BaseBlock` no longer stores or recursively sets `position`; its neutral
  `get_position()` returns `None`; its affected Pydantic boundary is
  `extra="forbid"`.
- `Tile`, `Entity`, `SpatialCondition`, and `Senses` own explicit strict
  two-coordinate fields and explicit `get_position()` implementations.
  `EntityConfig.position` uses the same non-coercive `StrictInt` tuple.
- `BaseItem` remains derived-only: floor, owner, and contained-item queries
  return `None` when no committed GridMap/owner coordinate exists, and it has
  no position input/property/cache.
- `target_resolution_sort_key` and position-based AoE use the neutral
  `get_position()` seam with deterministic absent-coordinate handling.
- GridMap entity membership validation uses the proven Entity position through
  `get_position()`, without restoring a generic BaseBlock field.

### Public verification

The new public Slice 6.1 selector passed:

`tests/engine/test_runtime_identity_registries.py::test_slice_6_1_position_owners_are_strict_and_base_blocks_are_neutral`
`1 passed`.

The affected proportional lanes were green:

- `tests/engine/test_runtime_identity_registries.py`: `12 passed`.
- `tests/engine/test_objective_state.py`: `2 passed`.
- `tests/engine/test_action_discovery.py`: `21 passed`.
- `tests/engine/test_items_inventory_equipment.py`: `37 passed`.
- `tests/engine/test_condition_lifecycle.py`: `17 passed`.
- `tests/engine/test_move_settlement.py`: `50 passed`.
- `tests/engine/test_grid_pathfinding.py`: `28 passed`.
- `tests/engine/test_world_edge_identity_and_elevation.py`: `26 passed`.
- `tests/engine/test_direct_scenario_deployment.py`: `49 passed in 27.55s`.
- `tests/engine/test_spatial_effects.py`: `60 passed`.
- `tests/engine/test_condition_transform_ownership.py`: `19 passed`.
- `tests/engine/test_spell_families.py`: `62 passed`.
- `tests/engine/test_manual_11_grid_tiles_terrain_movement.py`,
  `tests/engine/test_manual_07_entity_composition.py`, and
  `tests/engine/test_elevated_jump_transaction.py`: `20 passed`.
- `tests/engine/test_senses_light_stealth.py`: `43 passed`.
- `tests/engine/test_action_cost_and_position_commit.py` plus
  `tests/engine/test_event_wire_visibility_contract.py`: `14 passed`.
- `tests/architecture/test_dependency_boundaries.py` plus
  `tests/architecture/test_source_model_hygiene.py`: `32 passed`.

These lanes cover strict owner/config rejection and round-trip, neutral
BaseBlock/BaseItem schema and dump behavior, unplaced/floor/owner/contained
queries, target ordering and position-AoE behavior, Entity movement and
suspend/restore membership, placement/elevation identity, event ordering,
conditions, Banishment, items, light/senses, and dependency boundaries.

### Hard-cut and proportional gates

The governed changed Python files and both changed test files compiled with:

`.venv/bin/python -m compileall -q dnd/core/base_block.py dnd/core/base_actions.py dnd/core/base_tiles.py dnd/core/gridmap.py dnd/entities/entity.py dnd/blocks/sensory.py dnd/spatial/area_conditions.py tests/engine/test_runtime_identity_registries.py tests/engine/test_world_edge_identity_and_elevation.py`

Result: exit `0`.

`git diff --check` over the working tree returned no whitespace errors. Its
existing LF/CRLF normalization notices were warnings only and no file was
rewritten.

The fixed-string hard-cut search over active `dnd`, `tests/engine`, and
`tests/manual` Python files for `BaseBlock.position`, generic `block.position`,
`source_block.position`, and `.set_position(` returned zero generic retired
seam matches. Remaining direct `target.position`, Tile/placement/connector
coordinates, and Senses/Entity owner fields are the retained qualified
coordinate authorities recorded by Slice 6.0. No compatibility alias,
dual-write, second index, manager/controller/service, late import,
TYPE_CHECKING mask, or event path was added.

Two bounded test repairs occurred during this checkpoint. The new proof was
initially narrowed away from `BaseItem.model_json_schema()` because unrelated
callable fields in the existing model make schema generation invalid; the
public `model_fields`/`model_dump`/rejected-input proof remains and passed.
The existing global-Tile-registry replacement proof was updated to reconstruct
an impostor from public serialized fields while excluding five computed view
fields that are rejected by the newly required BaseBlock `extra="forbid"`
boundary. No production workaround or private-state assertion was added.

### Checkpoint status

No full 650-node or Slice 6.2+ lane was run or claimed. The current candidate
is ready for coordinator review with the nine-path Slice 6.1 implementation
and the exact results above.

Status: `READY_FOR_COORDINATOR_REVIEW`.

## Slice 6.1 connector round-trip correction

Coordinator reproduction found one affected active-lane failure after the
BaseBlock `extra="forbid"` cut: `tests/engine/test_traversal_connectors.py::test_connector_execution_rejects_replaced_global_support_owner`
reconstructed a Tile from `support.model_dump()` including five computed view
fields. The test was corrected only through the existing public serialization
pattern, excluding exactly `contextual_immunity_names`,
`values_dict_uuid_name`, `values_dict_name_uuid`, `blocks_dict_uuid_name`, and
`blocks_dict_name_uuid`. No production code, serializer, validator, helper, or
compatibility path was added.

The accepted active-envelope round-trip search for the coordinate-owner
models found exactly two relevant cases, both now using that public exclusion:

- `tests/engine/test_world_edge_identity_and_elevation.py:535`, Tile registry
  replacement proof.
- `tests/engine/test_traversal_connectors.py:1469`, connector support-owner
  replacement proof.

No `Entity`, `Senses`, `SpatialCondition`, `BaseItem`, or `BaseBlock`
`model_validate`/`model_validate_json` reconstruction from a `model_dump` or
`model_dump_json` was found in the accepted active envelope. Other search
matches are unrelated event, content-parameter, or replication models.

Exact correction validation:

- `tests/engine/test_traversal_connectors.py`: `38 passed in 4.89s`.
- `tests/engine/test_runtime_identity_registries.py`: `12 passed in 5.42s`.
- `tests/engine/test_world_edge_identity_and_elevation.py`: `26 passed in 5.09s`.
- New Slice 6.1 proof selector: `1 passed in 4.44s`.
- `tests/architecture/test_dependency_boundaries.py` plus
  `tests/architecture/test_source_model_hygiene.py`: `32 passed in 9.62s`.
- Compileall for all ten current Slice 6.1 paths: exit `0`.
- `git diff --check`: clean; only existing LF/CRLF normalization warnings
  were emitted.
- Retired generic seam scan over active `dnd`, `tests/engine`, and
  `tests/manual` Python: zero `BaseBlock.position`, generic `block.position`,
  `source_block.position`, or `.set_position(` matches.

The current Slice 6.1 correction path set is the prior nine paths plus
`tests/engine/test_traversal_connectors.py`; no production path was added.
The accepted Phase 5 dirty paths and excluded governance/server/content
surfaces remain preserved. Slice 6.2+ remains unauthorized and untouched.

Status: `READY_FOR_COORDINATOR_REVIEW`.
## Slice 6.2 implementation checkpoint

Slice 6.2 implemented the authorized movement-scalar and committed Tile-fact
hard cut only. Slice 6.3 renderer-neutral field removal, Slice 6.4 proof
closure, and the full Phase 6 certification lane were not started.

### Governing authority and bounded files

The governing Phase 6 plan was reverified at raw SHA-256
`154b0d9d92cadacbe167ec5908e576398a53377373c94c52862d2746d288f0da`.
The accepted Phase 5 manifest remains the unchanged governance artifact at
SHA-256 `c10171e9e64ea96ca93f0b971917aad1824654d950a82bed1b7cb516cbef70b1`.
The accepted Slice 6.1 implementation checkpoint before this append was
ledger SHA-256 `2ab8fca4b3e4ce18453ba19807ed779e67cb4407606cc76ece2e77374113a5cc`.
No governing plan or Phase 5 artifact was edited.

The exact Slice 6.2 production paths touched were:

- `dnd/core/base_tiles.py`;
- `dnd/core/gridmap.py`;
- `dnd/core/events/world_events.py`;
- `dnd/content/scenarios/battlefield_definitions.py`;
- `dnd/content/scenarios/battlefield_builders.py`;
- `dnd/maps/arena_layout.py`; and
- `dnd/spatial/area_conditions.py`.

The exact Slice 6.2 test paths touched were:

- `tests/engine/test_grid_pathfinding.py`;
- `tests/engine/test_event_wire_visibility_contract.py`;
- `tests/engine/test_spatial_effects.py`;
- `tests/engine/test_tile_surface_contract.py`;
- `tests/engine/test_elevation_proving_battlefield.py`;
- `tests/manual/test_08_world_model_and_movement.py`;
- `tests/engine/test_action_discovery.py`;
- `tests/engine/test_spell_families.py`;
- `tests/manual/test_37_authored_encounter_mechanics.py`; and
- `tests/manual/test_72_battlefield_deployment_catalog.py`.

The first eight test paths above are Slice 6.2 migrations/proofs; the last
two active authored-catalog paths were also migrated from the retired Boolean
walkability contract. Existing Slice 6.1 and Phase 5 dirty paths, including
overlap on `base_tiles.py`, `gridmap.py`, `area_conditions.py`,
`battlefield_builders.py`, `arena_layout.py`,
`test_elevation_proving_battlefield.py`, and `test_72_battlefield_deployment_catalog.py`,
were preserved. No excluded server, deprecated-server, SDK, transport,
generated, renderer, editor, cross-language, or inactive content path was
edited.

### Implemented public contract

- `Tile.walkable` and admitted active `walkable=` inputs were removed.
- Tile/GridMap construction now accepts only the four strict nonnegative
  movement costs, with defaults `(1, 1, 0, 0)` and zero meaning unavailable.
  Boolean, float, string, and negative inputs are rejected.
- Ordinary floor, wall, water, difficult terrain, authored battlefield rows,
  and the proving gap now express their final four costs directly. The active
  authored catalog proof compares all four runtime costs against each authored
  row.
- Movement revision/path invalidation compares the complete effective tuple;
  unrelated optical/propagation revisions remain unchanged for a one-mode
  movement edit, and surface-only replacement preserves all four costs and
  movement state.
- `WorldTileState` now has exactly four strict nonnegative cost fields and no
  `walkable`; `SpatialChangeEvent` has the four optional strict cost
  after-values, rejects the retired `tile_walkable` extra, and all committed
  Tile movement changes supply a complete tuple.
- Terrain condition activation/removal records changed per-Tile after-tuples
  on the existing condition-owned pending-runtime-fact seam, publishes one
  sorted committed fact per changed Tile after successful application/removal,
  preserves source/parent lineage, and discards pending terrain facts on
  failed provisional admission. Committed Tile facts use the existing
  non-vetoable committed-spatial boundary.
- The cold `WorldTileState` rows and the public detached replay proof use the
  complete four-cost values. `Senses.walkable` remains reducer-owned and was
  not renamed or serialized as objective Tile authority.

### Exact focused and affected results

The final focused commands used `.venv/bin/python -m pytest -q -p
no:cacheprovider` with these results:

- `tests/engine/test_grid_pathfinding.py`: `29 passed in 6.39s`;
- `tests/engine/test_action_discovery.py`: `21 passed in 16.37s`;
- `tests/engine/test_event_wire_visibility_contract.py`: `4 passed in 5.89s`;
- `tests/engine/test_elevation_proving_battlefield.py`: `7 passed in 11.57s`;
- `tests/engine/test_condition_lifecycle.py`: `17 passed in 8.05s`;
- `tests/engine/test_spatial_effects.py`: `60 passed in 12.57s`;
- `tests/engine/test_move_settlement.py`: `50 passed in 25.28s`;
- `tests/engine/test_tile_surface_contract.py`: `36 passed in 9.14s`;
- `tests/engine/test_direct_scenario_deployment.py`: `49 passed in 31.09s`;
- `tests/engine/test_runtime_identity_registries.py`: `12 passed in 7.22s`;
- `tests/manual/test_08_world_model_and_movement.py`: `6 passed in 6.15s`;
- `tests/manual/test_37_authored_encounter_mechanics.py`: `40 passed in 45.10s`;
- `tests/manual/test_72_battlefield_deployment_catalog.py`: `6 passed in 11.88s`;
- `tests/engine/test_elevation_performance_contract.py`: `5 passed in 11.04s`;
- `tests/engine/test_elevated_jump_transaction.py`: `10 passed in 14.72s`;
- `tests/engine/test_progressive_elevation_movement.py`: `8 passed in 13.72s`;
- `tests/engine/test_senses_light_stealth.py`: `43 passed in 24.60s`;
- `tests/engine/test_action_cost_and_position_commit.py`: `11 passed in 6.80s`;
- `tests/engine/test_objective_state.py`: `2 passed in 4.08s`;
- `tests/engine/test_condition_transform_ownership.py`: `19 passed in 11.36s`;
- `tests/engine/test_items_inventory_equipment.py`: `37 passed in 5.44s`;
- `tests/engine/test_manual_11_grid_tiles_terrain_movement.py`: `37 passed in 11.63s`;
- `tests/engine/test_manual_07_entity_composition.py`: `4 passed in 4.11s`;
- `tests/engine/test_traversal_connectors.py`: `38 passed in 5.21s`;
- `tests/engine/test_world_edge_identity_and_elevation.py`: `38 passed in 9.96s`;
- `tests/manual/test_01_runtime_identity_and_registries.py`: `26 passed in 9.87s`;
- `tests/manual/test_02_entity_anatomy.py`: `6 passed in 9.10s`;
- `tests/manual/test_10_combat_resolution.py`: `5 passed in 9.30s`;
- `tests/manual/test_128_antimagic_field.py`: `9 passed in 15.67s`;
- `tests/manual/test_133_new_spells_batch4_legacy_contract.py`: `14 passed in 13.82s`;
- `tests/manual/test_13_spellcasting_core.py`: `17 passed in 20.26s`;
- `tests/manual/test_14_spell_families.py`: `17 passed in 11.70s`;
- `tests/manual/test_17_encounters_turns_controllers.py`: `14 passed in 13.76s`;
- `tests/manual/test_53_srd_monster_traits.py`: `7 passed in 11.84s`; and
- `tests/manual/test_84_generic_roster_duels.py`: `16 passed in 18.84s`.

The full `tests/engine/test_spell_families.py` focused spell lane was also
green at `62 passed in 64.62s` during this checkpoint. The exact new public
proofs were included in the pathfinding, event-wire, spatial-effects, and
catalog results above.

### Locality, schema, replay, architecture, and hard-cut gates

The exact structured locality group was:

`.venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_runtime_identity_registries.py::test_entity_membership_queries_are_map_size_invariant_at_public_boundary tests/engine/test_elevation_performance_contract.py::test_cold_and_warm_action_discovery_have_bounded_pathfinder_calls tests/engine/test_elevation_performance_contract.py::test_path_computation_edge_queries_are_linear_in_local_map_edges`

It returned `4 passed in 6.81s`. This records public map-size invariance,
cold/warm bounded pathfinder calls, and parameterized local-edge bounds; the
renamed final-Tile composition test is not called a locality proof.

The public strict-schema and detached-replay proofs were included in the
`test_event_wire_visibility_contract.py`, `test_grid_pathfinding.py`, and
`test_spatial_effects.py` results above. The complete architecture command
`.venv/bin/python -m pytest -q -p no:cacheprovider tests/architecture`
returned `41 passed in 25.64s`.

All current modified active Python paths compiled with the generated scoped
command `.venv/bin/python -m compileall -q <all current dnd/ and tests/
Python paths>` and returned exit `0`. `git diff --check` returned exit `0`;
the existing LF/CRLF normalization notices were warnings only.

The active hard-cut scan found no Tile walkability field, `walkable=` Tile or
GridMap constructor input, or `tile_walkable` producer. Retained matches are
only `Senses.walkable`, `GridMap.is_walkable`/subjective walkability names,
and explanatory prose. The six known inactive/excluded legacy groups retain
old walkable inputs/JSON expectations and were not edited: player replication
and subjective-world projection modules, remaining/legacy spell and reactive
coverage modules, directional legacy environment, advanced-item legacy,
legacy AoE/shatter/jump/lightning modules, and the excluded encounter API
surface. No active in-scope producer retained the retired Tile field.

Public schema checks confirmed `walkable` is absent from Tile and
WorldTileState, `tile_walkable` is rejected by SpatialChangeEvent, and all
four cost fields reject bool/float/string/negative input while accepting zero.
Dependency checks remained clean: GridMap imports no Entity/concrete item or
SpatialCondition, core world events import no GridMap/Entity/Senses/authored
content/renderer, and no compatibility alias, dual write, second index,
manager/controller/service, late import, TYPE_CHECKING mask, replay system,
new event path, or callback was added.

The accepted Phase 5 manifest remains intentionally unchanged. Its raw bytes
still hash to `c10171e9e64ea96ca93f0b971917aad1824654d950a82bed1b7cb516cbef70b1`
and it still has 80 sorted unique members; 23 recorded member hashes now
differ because those governed files contain accepted Slice 6.1/Slice 6.2
working-tree changes after the Phase 5 freeze. No manifest member was
silently rewritten in this Slice.

### Slice 6.2 result

No full 650-node lane, Slice 6.3, Slice 6.4, final manifest, or Phase 7 work
was run or claimed. No failure remained after the bounded repairs: the local
cost-name shadowing bug was corrected, failed provisional terrain admission
was corrected to discard the incumbent's pending terrain facts, and the two
active authored catalog tests were migrated from Boolean walkability to exact
four-cost assertions. The candidate is ready for coordinator review.

Status: `READY_FOR_COORDINATOR_REVIEW`.
## Slice 6.2 replacement-fact correction checkpoint

Coordinator review reproduced a same-material replacement divergence: the
incoming condition captured an intermediate stacked walking cost and the
displaced incumbent retained a transferred pending terrain row. This bounded
correction changes only the existing AreaCondition pending-runtime-fact seam.

### Correction

`dnd/spatial/area_conditions.py` now retains the pre-change committed
four-cost tuple for each provisional terrain row. At the existing post-commit
publication boundary it reads the final live Tile tuple, suppresses rows
whose net tuple is unchanged, and publishes only sorted rows whose final live
tuple differs from the captured committed tuple. Displaced incumbent terrain
rows for positions transferred to the incoming condition are consumed during
the existing replacement commit. Light, condition, membership, event, and
rollback paths remain on their existing seams; no event type, replay system,
transaction, manager, callback, or compatibility path was added.

`tests/engine/test_spatial_effects.py` adds two public regressions. Full
same-material replacement proves no completed Tile-cost fact and detached
public state equality with live state. Partial replacement proves only the
newly changed cell carries its final tuple, the overlap carries no fact, and
later incumbent deactivation emits only its remaining changed cell while the
detached projection remains equal to live state.

### Exact correction validation

- New full/partial replacement selectors: `2 passed in 3.92s`.
- `tests/engine/test_spatial_effects.py`: `62 passed in 9.52s`.
- `tests/engine/test_grid_pathfinding.py`: `29 passed in 4.70s`.
- `tests/engine/test_condition_lifecycle.py`: `17 passed in 6.22s`.
- `tests/engine/test_condition_transform_ownership.py`: `19 passed in 10.07s`.
- `tests/engine/test_event_wire_visibility_contract.py`: `4 passed in 4.36s`.
- `tests/engine/test_spell_families.py`: `62 passed in 61.24s`.
- `tests/engine/test_manual_11_grid_tiles_terrain_movement.py`: `6 passed in 3.48s`.
- `tests/engine/test_tile_surface_contract.py`: `36 passed in 6.98s`.
- `tests/engine/test_direct_scenario_deployment.py`: `49 passed in 24.94s`.
- `.venv/bin/python -m pytest -q -p no:cacheprovider tests/architecture`:
  `41 passed in 20.40s`.
- Scoped compileall over all current modified active Python paths: exit `0`.
- `git diff --check`: exit `0`; only existing LF/CRLF normalization warnings.
- Active retired-cost/schema scan: no active Tile walkability field,
  `walkable=` Tile/GridMap input, or `tile_walkable` producer. Remaining
  matches are retained `Senses.walkable`/subjective terminology and governed
  excluded legacy residue.

Only these two files changed for this correction:

- `dnd/spatial/area_conditions.py`;
- `tests/engine/test_spatial_effects.py`.

No Slice 6.3 work, full 650-node lane, or excluded-scope edit was performed.

Status: `READY_FOR_COORDINATOR_REVIEW`.

## Slice 6.2 material-transformation baseline correction checkpoint

Coordinator review found that same-material replacement handling still lost a
net movement change when an authorized OilSurface-to-FireSurface replacement
had no incoming terrain modifier. The incoming condition had no pending row,
and the incumbent's transferred row was correctly discarded, so the live
walking cost changed from 2 to 1 without a replay fact.

### Correction

`dnd/spatial/area_conditions.py` now captures the complete committed
four-cost baseline for every admitted incoming AreaCondition Tile before any
provisional handlers, terrain/light mechanics, or displaced-incumbent release.
The existing one condition-owned pending terrain map retains the first
baseline per position. Final publication still reads the live post-settlement
tuple, suppresses unchanged rows, and publishes only the final net changes.
Rollback continues to clear provisional rows without publishing facts.

`tests/engine/test_spatial_effects.py` adds a public OilSurface-to-FireSurface
replacement proof through `replacing_condition_uuid`: exactly one completed
Tile-cost fact carries `(1, 1, 0, 0)`, and detached application of that fact
matches the live Tile projection. The two same-material replacement proofs
remain in the same public lane.

### Exact recertification

- Three replacement selectors (full same-material, partial same-material,
  authorized Oil-to-Fire): `3 passed in 3.96s`.
- `tests/engine/test_spatial_effects.py`: `63 passed in 9.68s`.
- `tests/engine/test_grid_pathfinding.py`: `29 passed in 4.73s`.
- `tests/engine/test_condition_lifecycle.py`: `17 passed in 6.26s`.
- `tests/engine/test_condition_transform_ownership.py`: `19 passed in 12.02s`.
- `tests/engine/test_event_wire_visibility_contract.py`: `4 passed`.
- `tests/engine/test_spell_families.py`: `62 passed in 61.99s`.
- `tests/engine/test_manual_11_grid_tiles_terrain_movement.py`: `6 passed in 4.18s`.
- `tests/engine/test_tile_surface_contract.py`: `36 passed in 6.94s`.
- `tests/engine/test_direct_scenario_deployment.py`: `49 passed in 25.31s`.
- `tests/architecture`: `41 passed in 20.69s`.
- Scoped compileall: exit `0`.
- `git diff --check`: exit `0`; only existing LF/CRLF normalization warnings.
- Active schema/replay/hard-cut scan: clean; only retained subjective
  `Senses.walkable`/entity-derived navigation and governed excluded legacy
  `walkable` residue remain.

Only these files changed for this correction:

- `dnd/spatial/area_conditions.py`;
- `tests/engine/test_spatial_effects.py`.

No Slice 6.3 work, full 650-node lane, manifest change, or excluded-scope edit
was performed.

Status: `READY_FOR_COORDINATOR_REVIEW`.

## Slice 6.3 renderer-neutral Tile/world-item hard-cut checkpoint

Slice 6.3 implemented only the approved Section 6.4 mechanics boundary. The
accepted Phase 6 authority remains the plan SHA
`154b0d9d92cadacbe167ec5908e576398a53377373c94c52862d2746d288f0da`.

### Bounded implementation

The following deleted runtime presentation seams are now absent from the
active mechanics surface: `Tile.sprite_name`, the Tile/GridMap factory and
rectangle/setter inputs, `BaseBlock.get_map_char`, `BaseItem.map_char`,
`BaseItem.visual_item_name`, `BaseItem.visual_variant_id`, and the active
environment, torch, consumable, spell-item, equipment, Heroes' Feast, Field
Kit, and authored static-blocker declarations/constructor keywords that only
fed those fields. Static blocker authored definitions retain only mechanical
identity, description, tags, health, blocking, and placement facts.

The retained semantic contracts are unchanged: Tile surface/cost/elevation,
Entity presentation, item name/description/tags/content identity, boundary
placement and structure, light, inventory/equipment, action templates, and
item/location/object state. No replacement asset key, glyph enum,
presentation component, lookup/binding interface, serializer, manager,
service, or renderer dependency was added. The stop-only armors, weapons,
variant packaging, environment-content, and presentation/server/editor/SDK
surfaces were not edited.

### Public proof changes

`tests/engine/test_tile_surface_contract.py` adds
`test_slice_6_3_renderer_fields_are_absent_and_rejected`. It proves the public
Tile/BaseItem field contracts and dumps omit the retired fields, public model
validation rejects retired renderer/walkability/item-position inputs, the
deleted map-character methods are absent, and Tile/GridMap construction
rejects the deleted `sprite_name` keyword. The existing direct authored-item
proofs in `tests/engine/test_direct_item_content.py` now assert public dump
absence rather than reading deleted attributes.

The exact new proof node is
`tests/engine/test_tile_surface_contract.py::test_slice_6_3_renderer_fields_are_absent_and_rejected`.
The migrated direct-item nodes are
`test_acolyte_loadout_builds_without_content_refs_or_renderer_fields`,
`test_every_cold_weapon_and_wearable_definition_builds_directly`, and the
two parameterized
`test_remaining_authored_weapons_build_without_presentation_state` cases in
`tests/engine/test_direct_item_content.py`.

### Exact Slice 6.3 changed paths

Production paths touched by this slice (all already inside the admitted
active envelope or its explicitly admitted active transitive item paths):

- `dnd/blocks/base_item.py`
- `dnd/blocks/equipment.py`
- `dnd/content/items/authored_item_builders.py`
- `dnd/content/items/authored_item_definitions.py`
- `dnd/content/items/environment_item_builders.py`
- `dnd/core/base_block.py`
- `dnd/core/base_tiles.py`
- `dnd/core/gridmap.py`
- `dnd/extensions/field_focus.py`
- `dnd/items/consumables.py`
- `dnd/items/environment.py`
- `dnd/items/environment_interactables.py`
- `dnd/items/spell_items.py`
- `dnd/items/torches.py`
- `dnd/spells/conjuration.py`

Test paths touched by this slice:

- `tests/engine/test_direct_item_content.py`
- `tests/engine/test_tile_surface_contract.py`

These paths overlap the existing accepted Slice 5/6 dirty candidate; no
unrelated dirty path was reset, rewritten, or cleaned.

### Exact validation

The first post-cut direct-item run exposed four stale attribute assertions in
`test_direct_item_content.py`; those were boundedly migrated to public dump
absence. The first version of the new schema proof attempted JSON-schema
generation for Tile, but an existing callable-valued nested field makes that
Pydantic JSON-schema operation invalid; the proof was corrected to the public
`model_fields` schema contract plus model dumps and public validation, without
changing production. Final results were:

- Tile/direct-item/inventory/equipment/scenario/materialization group:
  `141 passed in 33.74s`.
- `tests/engine/test_action_discovery.py`: `21 passed in 14.78s`.
- `tests/engine/test_senses_light_stealth.py`: `43 passed in 29.54s`.
- `tests/engine/test_spell_families.py`: `62 passed in 76.34s`.
- `tests/engine/test_cold_presentation_facts.py`: `6 passed in 5.13s`.
- `tests/engine/test_direct_behavior_identity.py`: `1 passed in 2.24s`.
- `tests/engine/test_grid_pathfinding.py`: `29 passed in 5.25s`.
- `tests/engine/test_event_wire_visibility_contract.py`: `4 passed in
  4.69s`.
- `tests/engine/test_world_edge_identity_and_elevation.py`: `26 passed in
  5.73s`.
- `tests/engine/test_runtime_identity_registries.py`: `12 passed in 6.14s`.
- `tests/architecture`: `41 passed in 27.22s`.
- `tests/manual/test_72_battlefield_deployment_catalog.py`: `6 passed in
  12.41s`.
- `tests/manual/test_37_authored_encounter_mechanics.py`: `40 passed in
  45.26s`.
- Governed Python compileall: exit `0`.
- `git diff --check`: exit `0`; only existing LF/CRLF normalization warnings.

The active retired-field scan over admitted production and active mechanics
tests has no `Tile.sprite_name`, `Tile.walkable`, `BaseBlock.get_map_char`,
runtime BaseItem `map_char`/`visual_item_name`/`visual_variant_id`, authored
`map_character`, or deleted factory keyword. The only retained active
presentation match is `Entity.sprite_name`; excluded apparel/variant
(`dnd/items/apparel_presets.py` reaches the excluded authored-variant table)
and renderer/content-presentation residue remains governed excluded. Item state,
location facts, object state, and cold-world facts contain none of the deleted
runtime presentation fields. Architecture dependency/deletion gates remain
green and no compatibility path, dual write, second index, manager/service,
new event/callback path, serializer, or renderer dependency was introduced.

The accepted Phase 5 manifest was not edited and remains the same 80-member
artifact with raw SHA
`c10171e9e64ea96ca93f0b971917aad1824654d950a82bed1b7cb516cbef70b1`.
No 650-node lane, final manifest, Slice 6.4, or Phase 7 work was run.

Status: `READY_FOR_COORDINATOR_REVIEW`.

## Slice 6.3 public rejection-proof correction

Coordinator review identified that the first rejection proof used raw
`model_dump()` payloads whose five computed view fields already made
round-trip validation fail. This was a test-only false-positive repair; no
production bytes changed.

The proof now removes exactly
`contextual_immunity_names`, `values_dict_uuid_name`,
`values_dict_name_uuid`, `blocks_dict_uuid_name`, and
`blocks_dict_name_uuid` from the public Tile and BaseItem dump payloads. It
explicitly proves `Tile.model_validate(clean_tile_payload)` and
`BaseItem.model_validate(clean_item_payload)` succeed before injecting one
retired field at a time. Each retired Tile field (`sprite_name`, `walkable`)
and BaseItem field (`map_char`, `visual_item_name`, `visual_variant_id`,
`walkable`, `position`) is then independently rejected through both public
model validation and direct BaseItem construction. The direct Tile.create,
GridMap.set_tile, and GridMap.create_rectangle `sprite_name` TypeError proofs
remain unchanged.

### Exact correction validation

- Corrected selector
  `tests/engine/test_tile_surface_contract.py::test_slice_6_3_renderer_fields_are_absent_and_rejected`:
  `1 passed in 5.11s`.
- `tests/engine/test_tile_surface_contract.py` plus
  `tests/engine/test_direct_item_content.py`: `53 passed in 7.91s`.
- Repeated Slice 6.3 focused Tile/direct-item/inventory/equipment/scenario/
  materialization group: `141 passed in 36.82s`.
- Repeated action discovery: `21 passed in 14.75s`.
- Repeated senses/light: `43 passed in 30.40s`.
- Repeated spell family: `62 passed in 78.18s`.
- Repeated `tests/architecture`: `41 passed in 28.87s`.
- Governed compileall: exit `0`.
- `git diff --check`: exit `0`; only existing LF/CRLF normalization warnings.
- Retired-field/deleted-caller hard-cut scan: clean except retained
  `Entity.sprite_name` and governed excluded presentation residue.

No production/test path outside the existing Slice 6.3 set was changed. No
Slice 6.4, 650-node lane, final manifest, or excluded-scope work was started.

Status: `READY_FOR_COORDINATOR_REVIEW`.

## Slice 6.4 completion-proof and test-quality checkpoint

This checkpoint implements only the approved Slice 6.4 completion proof and
test-quality closure. Slice 6.5 final certification and the final manifest
were not started.

### Authorities and active candidate

- Phase 6 implementation plan raw SHA-256:
  `154b0d9d92cadacbe167ec5908e576398a53377373c94c52862d2746d288f0da`.
- Accepted Phase 5 manifest raw SHA-256:
  `c10171e9e64ea96ca93f0b971917aad1824654d950a82bed1b7cb516cbef70b1`;
  the artifact remained unchanged.
- Ledger SHA before this append:
  `e10ed7ec33a4674caa27a7e2e79bc56761fcd3781da7530005c6d2ae9ca837a2`.
- The accepted 669-node maintained lane was executed in this Slice 6.4
  candidate as 669 passed in 270.81s, with sorted node-set SHA-256
  `d4ff804d5660192d9ba8f2f8adb3048893a505f0e491b7d30024c54e9dbd5d82`.
  The nine Slice 6.4 proof nodes below are disjoint additions to that lane;
  their exact maintained union is therefore 678 nodes. Final union freezing
  and normalization belong to Slice 6.5 and were not performed here.

### Slice 6.4 production and test changes

The only production changes in this slice are the existing-owner structured
diagnostics:

- `dnd/core/gridmap.py`: the existing immutable
  `GridMapOperationDiagnostics` now reports owner-counted local path-edge
  queries for `compute_paths`; it does not control behavior, serialize state,
  expose a dictionary, or create an index.
- `dnd/spatial/area_conditions.py`: the existing owner exposes the immutable
  footprint-work snapshot used by the public spatial-condition locality proof.

The Slice 6.4 test paths are:

- `tests/architecture/test_phase_6_completion_gates.py` (new);
- `tests/engine/test_combat_actions.py`;
- `tests/engine/test_elevation_performance_contract.py`;
- `tests/engine/test_grid_pathfinding.py`;
- `tests/engine/test_senses_light_stealth.py`;
- `tests/engine/test_spatial_condition_performance_contract.py`;
- `tests/engine/test_tile_surface_contract.py`;
- `tests/engine/test_world_edge_identity_and_elevation.py`; and
- `tests/manual/test_17_encounters_turns_controllers.py`.

The exact nine new proof node IDs are:

- `tests/architecture/test_phase_6_completion_gates.py::test_slice_6_4_master_dependency_arrows_are_ast_enforced`;
- `tests/architecture/test_phase_6_completion_gates.py::test_slice_6_4_gridmap_is_the_only_tile_and_reverse_placement_owner`;
- `tests/architecture/test_phase_6_completion_gates.py::test_slice_6_4_senses_projection_has_one_runtime_writer_boundary`;
- `tests/architecture/test_phase_6_completion_gates.py::test_slice_6_4_retired_inventory_has_explicit_retained_and_excluded_allowlists`;
- `tests/engine/test_spatial_condition_performance_contract.py::test_spatial_condition_work_scales_with_covered_cells`;
- `tests/engine/test_spatial_condition_performance_contract.py::test_spatial_condition_work_does_not_scale_with_unused_world_area`;
- `tests/engine/test_combat_actions.py::test_spike_trap_ordinary_step_resolves_damage_and_continues`;
- `tests/engine/test_combat_actions.py::test_spike_trap_lethal_step_stops_at_the_trigger_tile`; and
- `tests/engine/test_tile_surface_contract.py::test_same_xy_door_open_and_orient_preserve_anchor_placement`.

Existing selectors updated for the proof-quality cut retain their original
node identity except for the intentionally reclassified fixed-radius FOV
selector. They replace monkeypatched collaborator counts, private path/cache
state, and wall-clock ratios with public navigation revisions, public sense
snapshots, public FOV results, and the two existing-owner immutable diagnostic
seams. SpikeTrap proofs use only public action discovery/execution and assert
ordinary continuation versus lethal stop at the trigger Tile.

### Exact validation results

- Nine new Slice 6.4 proof selectors: `9 passed in 14.20s`.
- Focused completion/locality/architecture group:
  `193 passed in 75.90s`; complete architecture lane: `45 passed in 31.34s`.
- Affected position, terrain, object, light/FOV, spatial-condition, spell,
  scenario, catalog, and SpikeTrap files:
  `447 passed in 229.16s (0:03:49)`.
- Public locality selectors (map-size-invariant Entity membership,
  cold/warm action discovery, both parameterized local path-edge cases, and
  both spatial-condition footprint cases): `6 passed in 10.60s`.
- Governed active Python compileall over `dnd`, `tests/engine`, and
  `tests/manual`: exit `0`.
- Scoped `git diff --check`: exit `0`; only pre-existing LF/CRLF
  normalization warnings were emitted.
- The first focused attempt had five failures: the dependency AST gate
  over-rejected the existing semantic `dnd.presentation` leaf, the Senses
  writer gate overmatched unrelated `self` fields, the retired-position scan
  overmatched `senses_block.position`, and both initial SpikeTrap proofs used
  a safe route that avoided the trap. The bounded repairs allowed the existing
  semantic leaf, made the writer check receiver/class-aware, made the seam
  scan qualified, and used public action execution with the trigger Tile as
  destination. The corrected focused runs above are green; no production
  behavior failure remained.
- The migration-specific AST/dependency/authority/inventory gates in
  `tests/architecture/test_phase_6_completion_gates.py` passed as part of the
  complete architecture lane. They prove the master dependency arrows,
  GridMap-only Tile membership replacement and reverse-placement ownership,
  the single Senses projection writer boundary, and the explicit retained and
  excluded retired-symbol inventory.
- The affected-test residue scan has no `perf_counter`, `_paths_dirty`,
  `_fov_cache`, or locality monkeypatch evidence. Existing unrelated
  non-local failure-injection/engine tests and the previously accepted public
  light ownership assertions remain unchanged. No `_paths_dirty` assertion is
  used by either SpikeTrap proof.
- No compatibility alias, dual write, second index, manager/controller/
  service, event path/type, replay framework, renderer binding, serializer,
  or generic instrumentation abstraction was introduced. No excluded path was
  edited.

The Phase 5 manifest, governing plan, unrelated accepted dirty work, and
excluded worktree artifacts remain unchanged. This is a checkpoint candidate,
not self-approval.

Status: `READY_FOR_COORDINATOR_REVIEW`.

## Slice 6.4 bounded correction checkpoint

The prior Slice 6.4 checkpoint was rejected for two proof omissions and two
architecture-gate weaknesses. This correction remains limited to the existing
Slice 6.4 test envelope. No production, plan, governance, or excluded file was
changed; this authorized ledger is the only governance artifact updated.

### SpikeTrap continuation and interruption proofs

`tests/engine/test_combat_actions.py` now builds a public stone corridor with
walking-cost blockers around it, places traps at `(2, 2)` and `(3, 2)`, and
requests the later destination `(5, 2)` through public action discovery and
execution. The ordinary selector proves deterministic trap damage, alive
continuation, and arrival at the later destination. The lethal selector uses
the same later destination and proves the first trigger-cell stop at `(2, 2)`
with public `DEAD` state and no private path assertion.

The first exact repair attempt failed `2` selectors because newly created
Tiles lacked the required explicit semantic surface. The second attempt failed
`2` selectors because the corridor restoration calls had the same missing
surface. Passing repair added the existing stone `TileSurface` to every public
`set_tile` call. Final combined selector command:

`.venv/bin/python -m pytest -q -p no:cacheprovider tests/architecture/test_phase_6_completion_gates.py tests/engine/test_combat_actions.py::test_spike_trap_ordinary_step_resolves_damage_and_continues tests/engine/test_combat_actions.py::test_spike_trap_lethal_step_stops_at_the_trigger_tile`

Result: `6 passed in 9.42s` (four architecture nodes and the two corrected
SpikeTrap nodes).

### Complete semantic inventory and dependency-gate correction

`tests/architecture/test_phase_6_completion_gates.py` now contains an explicit
reviewable Phases 0-6 inventory. It records the Phase 0-2 object indexes,
BaseItem placement authority, WallTorch private placement, placement switches,
object renderer field, and GridMap-only Tile-band authority; the Phase 3 Tile
border/allow-direction families, BaseItem/BaseBlock directional families,
structural-channel state, border maps/recompute/setter, authored blocked
directions, duplicate topology, directional event/state maps, DoorObject,
global barrier cache, and object-owned perception; the Phase 4 entity indexes,
GridMap indexes, retired public mutators, Entity occupancy query, and the
approved retained private `GridEntityMembershipReceipt`; the explicit fact
that Phase 5 introduced no separate retired public-symbol family; and the
Phase 6 position, walkability, event, and renderer fields.

The inventory is qualified by AST declaration/call/receiver context. It keeps
the explicit valid owner/value allowlist (`Tile.position`, `Entity.position`,
`SpatialCondition.position`, `Senses.position`, `WorldObjectPlacement.position`,
`Entity.sprite_name`, `Senses.walkable`, `GridMap.is_walkable`, and
`GridMap.is_walkable_for`) and the GridMap/private membership allowlist. The
known inactive/blocked legacy test paths are explicitly classified as governed
excluded residue; the three existing public deletion-proof files remain the
proof allowlist. No broad lexical position classification was used.

The Senses gate now separates perception fields from lazy navigation fields,
tracks nested `.senses` receivers and simple aliases, detects assignments,
subscript writes, and common container mutators, and requires nonempty
projection/navigation writer and caller sets. Perception writes remain within
the sensory reducer/replay boundaries; navigation writes remain within
`Senses.replace_navigation`, called by `Entity.materialize_navigation`. The
dependency gate explicitly allows only the existing
`dnd/core/events/action_events.py` import of `dnd.presentation` and rejects
additional presentation/renderer/pygame imports in core events.

The corrected standalone architecture gate initially reported `2 passed, 2
failed` while the new writer/inventory rules still overmatched reads and
qualified retained helpers; after removing read-only subscript matches,
limiting local aliases, and listing the exact excluded residue, it reported
`4 passed in 5.15s`. The complete architecture command reported
`45 passed in 29.47s`.

### Final correction validation

- Affected combat, elevation, pathfinding, light/FOV, spatial-condition,
  surface, world-edge, and turn-start modules:
  `189 passed in 59.69s`.
- Structured public locality group (map-size membership, cold/warm action
  discovery, parameterized local path-edge work, and spatial-condition
  footprint work): `6 passed in 9.41s`.
- Final corrected architecture plus SpikeTrap proof command: `6 passed in
  9.42s`; complete `tests/architecture`: `45 passed in 29.47s`.
- `.venv/bin/python -m compileall -q dnd tests/engine tests/manual`: exit `0`.
- `git diff --check`: exit `0`; only existing LF/CRLF normalization warnings.
- The direct fixed-string diagnostic still finds only the already classified
  excluded legacy `_entity_by_position`/retired-field residue, the retained
  Entity `_set_position` owner seam, retained private
  `GridEntityMembershipReceipt`, and public deletion-proof literals. The
  qualified active AST inventory and dependency/authority gates are green;
  no new active retired symbol is present.
- Current correction files are exactly:
  `tests/architecture/test_phase_6_completion_gates.py` and
  `tests/engine/test_combat_actions.py`. No production file changed in this
  correction, and Slice 6.5 was not started.

Prior ledger SHA before this append: `167b3a5bcebb996e62f0053fa16f5050e5410b728214e3366ec2f293797e00db`.
The architecture file and combat test currently hash respectively to
`2068898bfe0008d282cb2326803307856a8857a3103da664f7e3c19e32e75c1e` and
`b6a7d8326ceed544114a76f4e79a7ffb5aeb348493ef4a20e552f3f1ade87345`.

Status: `READY_FOR_COORDINATOR_REVIEW`.

## Second bounded Slice 6.4 proof correction checkpoint

This checkpoint addresses the coordinator's two proof-only findings against
the prior ledger SHA `97dfde5b17f9b3d31454d916b4f937e4491d9ff3acc3bb8f489cddb7be539e88`.
No production, plan, manifest, or excluded file was changed, and no new test
node was added. The exact changed files in this correction are:

- `tests/engine/test_combat_actions.py`
- `tests/architecture/test_phase_6_completion_gates.py`

The ordinary public SpikeTrap movement proof now requests `(5, 2)` beyond
both trigger cells `(2, 2)` and `(3, 2)`, uses the existing repeated fixed
`2, 2` dice, reaches `(5, 2)` alive, and asserts the exact HP delta `8`
(`2d4` per entry, twice). The lethal proof retains the same beyond-trap
destination and public action path, uses fixed `4, 4` dice, and proves the
canonical dead stop at the first trigger `(2, 2)`.

The retired inventory gate now binds every `MUST_MIGRATE` row to an explicit
AST rule in `RETIRED_AST_RULES`, and asserts that each such row has a nonempty
recognized rule. The executable rule table covers the exact Phase 0-2 index,
placement, renderer, and Tile-band-owner rows; the Phase 3 Tile border and
`allows_direction(s)` names, all twelve BaseItem directional fields and
helpers, structural/directional state and maps, `blocked_directions`, all
four duplicate topology helpers, `movement_open`/`optical_open`/
`propagation_open`, authoritative directional event fields, `DoorObject`,
`OpenDoorAction`/`CloseDoorAction`/`door_recipe`/`build_door` and
`DOOR_DECLARATION`/`DOOR_REF`/`DOOR_RECIPE`, `DOOR_DIRECTIONS`/
`WALL_DIRECTIONS`, the no-argument barrier-cache call shape, and
`is_perceivable_by`; the Phase 4 indexes, `GridEntityPositionReceipt`
(distinct from retained `GridEntityMembershipReceipt`), occupancy mutators,
and Entity query; and the Phase 6 position, walkability, Tile sprite,
BaseItem presentation, and map-character accessor rows. The gate separately
recognizes BaseItem-family declarations/position inputs, Tile/GridMap
walkability/sprite inputs, zero-argument barrier calls, and string catalog
identity. Its private-band owner assertion now requires all private band
storage access to be limited to `dnd.core.base_tiles` and `dnd.core.gridmap`,
with replacement calls still limited to GridMap and reverse placement access
still limited to GridMap.

The explicit exclusion set was extended only for known out-of-envelope stale
legacy rows that the stronger walkability rule surfaced:
`tests/manual/test_120_player_replication_journal.py`,
`tests/manual/test_126_jump_legacy_contract.py`,
`tests/manual/test_126_shatter.py`,
`tests/manual/test_127_lightning_bolt.py`,
`tests/manual/test_131_advanced_item_world_legacy_contract.py`,
`tests/manual/test_138_mixed_damage_spell_contract.py`,
`tests/manual/test_aoe_shape_legacy_contract.py`,
`tests/manual/test_legacy_reactive_reaction_coverage.py`, and
`tests/manual/test_remaining_zone_spell_legacy_contract.py`. The active
proof allowlist now also names `tests/engine/test_runtime_identity_registries.py`,
whose public BaseItem position-rejection assertion is intentionally a proof
input rather than a gameplay caller. These classifications preserve the
existing ledger's inactive/server/content-system exclusion boundary.

Correction trace: the first expanded-prefix scan exposed the retained
`border_lines` labels in `tests/manual/test_08_world_model_and_movement.py`;
the prefix rule was narrowed to qualified attributes/class fields. The next
scan exposed stale `walkable=` rows in the nine named out-of-envelope legacy
modules above; those paths were classified explicitly rather than migrated.
The strengthened BaseItem-family visitor then exposed the intentional public
`BaseItem(position=...)` proof in `test_runtime_identity_registries.py`, which
was placed in the explicit proof allowlist. One transient visitor indentation
error while adding the zero-argument barrier check was corrected before the
final run. No behavioral or production failure remained.

### Exact correction results

- Targeted ordinary SpikeTrap, lethal SpikeTrap, and all four new completion
  architecture gates: `6 passed in 9.41s`.
- Full `tests/engine/test_combat_actions.py`: `39 passed in 23.85s`.
- Full `tests/architecture` plus the affected combat module on the final
  bytes: `84 passed in 49.03s` (`45` architecture, `39` combat).
- `.venv/bin/python -m compileall -q dnd tests/engine tests/manual`: exit `0`.
- `git diff --check`: exit `0`; existing LF/CRLF normalization notices only.
- The hard-cut diagnostic is the corrected AST inventory/owner gate in
  `tests/architecture/test_phase_6_completion_gates.py`; it is green, with no
  active retired-symbol match. Dependency/authority checks in the complete
  architecture run are green. No Slice 6.5 or production implementation was
  started.

Final correction-file raw SHA-256 values:

| File | SHA-256 |
|---|---|
| `tests/architecture/test_phase_6_completion_gates.py` | `e45038052f6a77d9d89b2abe99cd053ae3a0c934d346a0ae34711295e1c069db` |
| `tests/engine/test_combat_actions.py` | `e47699fb584d54dfabfacbefbee4497a3266fe36d6a6143a8d2d278dce621d00` |

The resulting ledger SHA is reported with this checkpoint rather than
embedded here, avoiding a self-referential digest.

Status: `READY_FOR_COORDINATOR_REVIEW`.
## Second bounded Slice 6.4 correction checkpoint

This checkpoint corrects one retained-call qualification defect in the
existing Slice 6.4 architecture inventory. No production, manifest, plan,
excluded-scope, or new test-node bytes were changed. The only implementation
test file changed for this correction is
`tests/architecture/test_phase_6_completion_gates.py`; the existing
SpikeTrap proof file was rerun but not edited in this correction.

`Entity.register_entity` is now an explicit member of
`RETAINED_OWNER_ALLOWLIST`, with an exact assertion. The retired call rule
still covers `register_entity`, but the AST visitor retains only the exact
`Entity.register_entity(...)` receiver form. Instance and GridMap receiver
forms remain retired. A scanner self-proof parses the three public shapes:
the explicit Entity form produces no retired `register_entity` match, while
`GridMap.register_entity(...)` and `grid.register_entity(...)` each produce a
retired match. The existing unregister/move/stage/publish rules are unchanged.

### Exact correction validation

- `tests/architecture/test_phase_6_completion_gates.py`: `4 passed in 5.08s`.
- `tests/architecture`: `45 passed in 26.53s`.
- The two maintained SpikeTrap proofs, using the corrected names
  `test_spike_trap_ordinary_step_resolves_damage_and_continues` and
  `test_spike_trap_lethal_step_stops_at_the_trigger_tile`: `2 passed in
  4.73s`.
- `.venv/bin/python -m compileall -q tests/architecture/test_phase_6_completion_gates.py tests/engine/test_combat_actions.py`: exit `0`.
- `git diff --check`: exit `0`, with only the existing LF/CRLF normalization
  notices.

The initial two-selector invocation used the stale lethal node spelling and
therefore collected no tests; it was corrected without a code change and the
exact two proofs above then passed. No failure required a behavioral repair.

Current raw SHA-256 values:

| File | SHA-256 |
|---|---|
| `tests/architecture/test_phase_6_completion_gates.py` | `b69291c73212847e2777be76c9d5d0da67e3db4b6c0ad041d49353b9d722b380` |
| `tests/engine/test_combat_actions.py` (unchanged in this correction) | `e47699fb584d54dfabfacbefbee4497a3266fe36d6a6143a8d2d278dce621d00` |

Status: `READY_FOR_COORDINATOR_REVIEW`.

## Exact normalized 105-row diagnostic table

The table below is the complete row-level normalization of the exact command in the baseline section. Each row is classified as governed excluded; no active Slice 6.0 input is represented.

| # | collecting path | class | normalized terminal message | classification |
|---:|---|---|---|---|
| 1 | `tests/engine/test_condition_content_evidence.py` | `ModuleNotFoundError` | `No module named 'dnd.core.content.runtime'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 2 | `tests/engine/test_counterspell_evidence.py` | `ModuleNotFoundError` | `No module named 'dnd.core.content.runtime'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 3 | `tests/engine/test_dice_event_semantics.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 4 | `tests/engine/test_encounter_apis.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 5 | `tests/engine/test_equipment_domain_ownership.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 6 | `tests/engine/test_equipment_replication_facts.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 7 | `tests/engine/test_manual_14_core_combat_flow.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 8 | `tests/engine/test_manual_20_encounters_turns_controllers_apis.py` | `ModuleNotFoundError` | `No module named 'dnd.monsters.bestiary_content'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 9 | `tests/engine/test_manual_21_arena_game_sessions_client_state.py` | `ModuleNotFoundError` | `No module named 'server'` | `MISSING_SERVER` |
| 10 | `tests/engine/test_monster_presets.py` | `ModuleNotFoundError` | `No module named 'dnd.monsters.circus_fighter'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 11 | `tests/engine/test_spellcasting.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 12 | `tests/manual/test_09_action_discovery_and_costs.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 13 | `tests/manual/test_102_game_summary.py` | `ModuleNotFoundError` | `No module named 'dnd.core.content.runtime'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 14 | `tests/manual/test_103_game_summary_store.py` | `ModuleNotFoundError` | `No module named 'server'` | `MISSING_SERVER` |
| 15 | `tests/manual/test_112_server_life_state_contract.py` | `ModuleNotFoundError` | `No module named 'dnd.monsters.bestiary_content'` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 16 | `tests/manual/test_113_subjective_combat_log_projection.py` | `ModuleNotFoundError` | `No module named 'server'` | `MISSING_SERVER` |
| 17 | `tests/manual/test_113_subjective_replication_contract.py` | `ModuleNotFoundError` | `No module named 'server'` | `MISSING_SERVER` |
| 18 | `tests/manual/test_113_subjective_replication_routes.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 19 | `tests/manual/test_114_timeline_contracts.py` | `ModuleNotFoundError` | `No module named 'server'` | `MISSING_SERVER` |
| 20 | `tests/manual/test_115_objective_timeline.py` | `ModuleNotFoundError` | `No module named 'server'` | `MISSING_SERVER` |
| 21 | `tests/manual/test_116_objective_replay.py` | `ModuleNotFoundError` | `No module named 'server'` | `MISSING_SERVER` |
| 22 | `tests/manual/test_117_player_replication_contract.py` | `ImportError` | `cannot import name 'EquippedVisualPolicy' from 'dnd.presentation' (<CHECKOUT>/dnd/presentation.py)` | `REMOVED_CONTENT_PROGRESSION_PRESENTATION_DEVTOOL` |
| 23 | `tests/manual/test_118_game_replay.py` | `ModuleNotFoundError` | `No module named 'server'` | `MISSING_SERVER` |
| 24 | `tests/manual/test_11_equipment_inventory_and_items.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 25 | `tests/manual/test_120_player_replication_journal.py` | `ModuleNotFoundError` | `No module named 'server'` | `MISSING_SERVER` |
| 26 | `tests/manual/test_120_subjective_world_projection.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 27 | `tests/manual/test_121_canonical_presentation_mapper.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 28 | `tests/manual/test_122_canonical_replication_runtime.py` | `ModuleNotFoundError` | `No module named 'server'` | `MISSING_SERVER` |
| 29 | `tests/manual/test_123_subjective_player_replay.py` | `ModuleNotFoundError` | `No module named 'server'` | `MISSING_SERVER` |
| 30 | `tests/manual/test_125_active_weapon_stance.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 31 | `tests/manual/test_125_haste_restricted_action.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 32 | `tests/manual/test_125_subjective_objective_render_parity.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 33 | `tests/manual/test_126_action_surge_extra_attack_legacy_contract.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 34 | `tests/manual/test_126_slow_legacy_contract.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
| 35 | `tests/manual/test_131_advanced_item_world_legacy_contract.py` | `ModuleNotFoundError` | `No module named 'dnd.content_system'` | `MISSING_DND_CONTENT_SYSTEM` |
## Slice 6.5 final certification and freeze

This is the final certification-only checkpoint under the approved Phase 6
plan. No production or test file was edited during Slice 6.5, and no
behavioral repair was performed. The accepted Phase 5 and Phase 6.4 dirty
work, excluded paths, and governing documents remain unchanged.

### Authorities and exact active union

The final plan and all named governing authorities were reverified by raw-byte
SHA-256: master `50411e5575e6336ca0301acf032797cdf1d5ea885df5ccd37d6619f593e7a193`,
active-runtime amendment `f10e2fbbcb6ba8732d078f0c4f2f5276716eb51e32c083068f3cae93c9ba52d6`,
Phase 5 plan `892e07aea27cb777fcb6fda6a7f7415d46bd4825a582d5f6001fb383f4a10870`,
Phase 5 completion ledger `b75f690bfe7486d5f63cef3e20a8b8031944e4ae776a4adf4422ef255fe46cfa`,
Phase 5 manifest `c10171e9e64ea96ca93f0b971917aad1824654d950a82bed1b7cb516cbef70b1`,
HOW_TO_TEST.MD `96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013`,
agents.md `fcc5dd1e15bae2ff86a7203f42b0c55de4d51dd0d93bc3a3ae059b7e58ee39b1`,
and Phase 6 plan `154b0d9d92cadacbe167ec5908e576398a53377373c94c52862d2746d288f0da`.

The accepted Phase 5 manifest was verified at its accepted 80-member,
650-node authority (`8202c5f659be52244112818848d40d01f2a358adf3cce17200ccd075e172c2e6`).
The exact final collection inputs are the manifest's
`collection_inputs.accepted_phase5_frozen_path_inputs`,
`accepted_phase5_outside_selector_inputs`, 19
`phase6_admitted_existing_selector_inputs`, and 9
`phase6_authorized_selector_inputs`. The exact sorted unique node IDs are
stored in `node_set_accounting.final_nodes` in the final manifest, with the
approved newline-normalized algorithm. The final union is 684 unique nodes,
SHA-256 `dd8e28a91615f278146a030149478d75bdd7293bc553ecd70ef95084f4f2aa33`.
The exact NUL-safe execution of that ordered node list returned:
`684 passed in 241.96s (0:04:01)`.

### Final validation gates

- Complete `tests/architecture`: `45 passed in 26.09s`.
- Structured public locality group (membership-size, cold/warm discovery,
  local path-edge, and spatial-condition footprint selectors): `6 passed in
  9.97s`.
- Runtime-schema/replay group (`test_runtime_identity_registries.py`,
  `test_tile_surface_contract.py`, `test_direct_item_content.py`, and
  `test_spatial_effects.py`): `129 passed in 13.79s`.
- `.venv/bin/python -m compileall -q dnd tests/engine tests/manual`: exit `0`.
- `git diff --check`: exit `0`; only existing LF/CRLF normalization notices.
- Dependency, authority, hard-cut, and runtime-schema AST gates: green in the
  complete architecture and active schema/replay runs. The active retired
  inventory has no unclassified match; the governed excluded residue remains
  classified by the existing 105-row table. No private light enumeration,
  compatibility path, second authority/index, manager/controller/service,
  replay framework, renderer binding, serializer, or extra event path exists.
- Repository-wide diagnostic command
  `.venv/bin/python -m pytest --collect-only -q -p no:cacheprovider`: exit `2`,
  `1396 tests collected, 105 errors in 16.98s`; class counts are
  `97 ModuleNotFoundError`, `4 ImportError`, and `4 FileNotFoundError`.
  Its 105 normalized `(path, class, message)` rows exactly equal the
  preflight table (`preflight_row_set_equal=True`) and retain signature
  `eccd100453848ac9af6a6e028692862dbf0866daaf0c0e3d275b13d4d4e06cd9`.

### Final active-only manifest and scope

The final manifest is
`DND_TILE_WORLD_ITEM_PHASE_6_IMPLEMENTATION_MANIFEST_2026-08-26.json`, raw
SHA-256 `a60c688b5e959139f5927480e655bdff44b2af6fcaca9a23ae4dff1bd307474e`.
It contains exactly 91 sorted unique current active members: 41 production
Python files and 50 active test Python files. All 91 exist and their current
raw-byte hashes match; duplicate count and mismatch count are both zero. The
manifest's final node list has 684 entries, all unique, and its stored node
hash equals the executed union hash above. The manifest itself, this ledger,
the Phase 6 plan, and the three Phase 5 governance artifacts are excluded
governance files and are not manifest members. No Markdown, server,
deprecated-server, SDK, transport, generated, renderer, editor,
cross-language, inactive content-system, cache, or temporary path is a
manifest member.

The scoped worktree check found 46 active changed paths, all within the
manifest's governed envelope, and no excluded active path changed. The exact
active changed-path list is preserved in the manifest's
`changed_active_paths` field. The current worktree additionally contains only
the six named Phase 5/Phase 6 governance artifacts outside active membership.

No code or test bytes changed after the final union execution. This candidate
is frozen for independent correctness and anti-slop review.

Status: `READY_FOR_INDEPENDENT_REVIEW`.

## Consolidated Phase 6 rejected-review repair checkpoint — READY_FOR_COORDINATOR_REVIEW

This checkpoint records the bounded repair requested after rejection of the
candidate at ledger SHA
`3d786ea9ad0487f6f057f2cb561963ba3c62583723989456482b0d0db5f3958d`, manifest
SHA `a60c688b5e959139f5927480e655bdff44b2af6fcaca9a23ae4dff1bd307474e`, and
684-node hash
`dd8e28a91615f278146a030149478d75bdd7293bc553ecd70ef95084f4f2aa33`.
The rejected findings were: non-exact `GridMap.set_tile` coordinates could
mutate before failure; four condition relocation boundaries could assign
non-exact coordinates before mutation; path locality used shared diagnostics
and a full-map cost scan; spatial-condition work counts were synthetic; the
named public-test migrations retained private/internal evidence; and the
rejected accounting omitted
`tests/engine/test_runtime_identity_registries.py::test_slice_6_1_position_owners_are_strict_and_base_blocks_are_neutral` while
claiming an invalid `650 + 19 + 9` decomposition. The rejected manifest was
not edited and no final recertification was performed.

### Bounded implementation repairs

- `dnd/core/gridmap.py` now validates `set_tile` coordinates at method entry
  with exact `tuple[int, int]` component semantics before lookup or mutation.
  Path consultation counting is local to each `compute_paths` call and counts
  unique consulted transitions; the shared marker/counter was removed and the
  full-map `unit_movement_costs` scan was removed in favor of the existing
  local Dijkstra path. Active GridMap descriptions were corrected only for
  retained spatial-membership ownership.
- `dnd/spatial/area_conditions.py` now uses one owner-local exact-coordinate
  check before generic relocation and `AreaCondition.move_zone`, and records
  work at actual local position-iteration boundaries for admission, activation,
  commit, and removal. The same check is used by the specialized relocation
  paths in `dnd/spells/abjuration.py` and `dnd/spells/evocation.py` before
  runtime mutation.
- The public progressive-elevation test now registers and executes a public
  flying `Move` and asserts public affordability, path cost, completion, and
  position. The elevation proving test now checks public empty-authored
  elevation construction without monkeypatching a private/probing helper. The
  runtime identity test is behavioral output/revision invariance, not a work
  counter. Private `_paths_dirty` assertions, unused architecture bookkeeping,
  and the two walking-cost indentation residues were removed. The connector
  description now names local endpoint lookup. `Tile`, `Entity`, and GridMap
  active descriptions now state retained ownership accurately.

### Public regressions and locality evidence

The added public strict-coordinate nodes are:

```
tests/engine/test_runtime_identity_registries.py::test_set_tile_rejects_non_exact_coordinates_before_any_public_change[True-2]
tests/engine/test_runtime_identity_registries.py::test_set_tile_rejects_non_exact_coordinates_before_any_public_change[1.5-2]
tests/engine/test_runtime_identity_registries.py::test_set_tile_rejects_non_exact_coordinates_before_any_public_change[1-2]
tests/engine/test_spatial_effects.py::test_relocation_rejects_non_exact_coordinates_without_public_mutation[invalid_position0]
tests/engine/test_spatial_effects.py::test_relocation_rejects_non_exact_coordinates_without_public_mutation[invalid_position1]
tests/engine/test_spatial_effects.py::test_relocation_rejects_non_exact_coordinates_without_public_mutation[invalid_position2]
tests/engine/test_spatial_effects.py::test_specialized_relocation_rejects_non_exact_coordinates_before_runtime_changes[invalid_position0]
tests/engine/test_spatial_effects.py::test_specialized_relocation_rejects_non_exact_coordinates_before_runtime_changes[invalid_position1]
tests/engine/test_spatial_effects.py::test_specialized_relocation_rejects_non_exact_coordinates_before_runtime_changes[invalid_position2]
```

The following existing node IDs were renamed to reflect public
behavior/locality meaning; no compatibility aliases were added:

```
tests/engine/test_elevation_performance_contract.py::test_cold_and_warm_action_discovery_have_bounded_pathfinder_calls
  -> tests/engine/test_elevation_performance_contract.py::test_warm_action_discovery_preserves_navigation_projection
tests/engine/test_elevation_proving_battlefield.py::test_empty_cold_battlefield_preflight_is_linear_in_authored_elevation
  -> tests/engine/test_elevation_proving_battlefield.py::test_empty_cold_battlefield_accepts_empty_authored_elevation
tests/engine/test_traversal_connectors.py::test_connector_discovery_uses_only_endpoint_index
  -> tests/engine/test_traversal_connectors.py::test_connector_discovery_uses_only_local_endpoint_lookup
```

Exact locality probe output, using existing owner diagnostics, was:

```
path size=20 distances=169 edge_queries=1352
path size=80 distances=169 edge_queries=1352
condition size=24 footprint=64 activation_positions=192 deactivation_positions=64
condition size=72 footprint=64 activation_positions=192 deactivation_positions=64
```

All counts are positive and equal for identical local geometry in larger
unused maps. The warm action-discovery node is behavioral projection
invariance and is not claimed as a locality work proof.

### Exact validation run

The exact affected command groups and results were:

```
.venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_runtime_identity_registries.py tests/engine/test_grid_pathfinding.py tests/engine/test_progressive_elevation_movement.py tests/engine/test_elevation_performance_contract.py tests/engine/test_elevation_proving_battlefield.py tests/engine/test_traversal_connectors.py
102 passed in 21.58s

.venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_spatial_effects.py tests/engine/test_spatial_condition_performance_contract.py tests/engine/test_event_wire_visibility_contract.py tests/engine/test_tile_surface_contract.py tests/engine/test_world_edge_identity_and_elevation.py
139 passed in 16.62s

.venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_action_discovery.py tests/engine/test_combat_actions.py tests/engine/test_move_settlement.py tests/engine/test_senses_light_stealth.py
153 passed in 74.50s

.venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_spell_families.py tests/architecture/test_phase_6_completion_gates.py tests/architecture/test_source_model_hygiene.py tests/architecture/test_dependency_boundaries.py
98 passed in 79.44s

.venv/bin/python -m pytest -q -p no:cacheprovider tests/architecture
45 passed in 25.07s
```

The four affected groups total 492 passed. The strict exact-coordinate group
was run as 9 passed in 3.78s. The public locality selector group was run as 6
passed in 9.97s. The runtime-schema/replay group was run as 129 passed in
13.79s. The exact collected subset used for the affected nine-file inventory
was 210 nodes; the runtime/spatial collection subset was 84 nodes and the
elevation/proving/connector collection subset was 50 nodes.

Compile, diff, and hard-cut checks were:

```
.venv/bin/python -m compileall -q dnd/core/gridmap.py dnd/spatial/area_conditions.py dnd/spells/abjuration.py dnd/spells/evocation.py dnd/core/base_tiles.py dnd/entities/entity.py tests/engine/test_progressive_elevation_movement.py tests/engine/test_elevation_performance_contract.py tests/engine/test_elevation_proving_battlefield.py tests/engine/test_runtime_identity_registries.py tests/engine/test_spatial_effects.py tests/engine/test_spatial_condition_performance_contract.py tests/engine/test_spell_families.py tests/engine/test_traversal_connectors.py tests/architecture/test_phase_6_completion_gates.py
exit 0
git diff --check -- [the same 15 paths]
exit 0; only existing LF/CRLF normalization notices
```

The retired-seam/dependency/runtime-schema scan found no active stale
`_path_edge_queries`, no full-map `unit_movement_costs` scan, no synthetic
condition-work length additions, no private mover calls in the migrated
progressive-elevation test, no contradictory-elevation monkeypatch, and no
unused `_called_private_names`. Remaining matches are the accepted
architecture allowlist or retained internal `_paths_dirty`/walkability
behavior from earlier approved phases. No excluded path was edited.

### Current repair-path bytes and scope

The repair-specific changed paths are exactly these 15 active files; all were
hashed from their current raw bytes after the validation run:

```
1437a89b844fe24e9b69a5a5fc25d82b3998a302e14a1e3c740f68ae28739eb0  dnd/core/gridmap.py
724506555e6158a342fb980a9bb62d5dc6aae2ef3a9a6b0b6fa1a5c80403c92d  dnd/core/base_tiles.py
93a35b6d9c2bc864f6b16a6c3e343ddfe261e920b5eedfb9d77ed20867f87294  dnd/entities/entity.py
e4afb4fa6f4596e06a4417c81656619ce6ac6a1e15896e42d537bd0cffff2880  dnd/spatial/area_conditions.py
b90c5a2d3ccc54724220e1d1aab5d251f5117e954d828e25bd9eab69b6b178bf  dnd/spells/abjuration.py
e26b797f201161b0839c34a78c7a8e643030308b5ff44d3ae99f821427da788c  dnd/spells/evocation.py
4e6030ff9f6fa1f18a467070f999e0d21c481cbb6d3a553d7bfa2cd83b8d94c4  tests/architecture/test_phase_6_completion_gates.py
e9b2ff220df79f2cafb144fc3c92a58d8d1c48cd26d165b978ca21de19c72226  tests/engine/test_progressive_elevation_movement.py
cde8c990bb9c329879841af768e328ad86b25db48fc29074aba0736b28a0aa74  tests/engine/test_elevation_performance_contract.py
85fdb8fe03f669ea7d756e62b61410fc1123724d9d6eb7aed12b9d22a3e46668  tests/engine/test_elevation_proving_battlefield.py
d1ae49230ffaa21a799f042f26197b6aedbc514bd63035ae88546a4605e0d6ef  tests/engine/test_runtime_identity_registries.py
deb0f9f29e9041dda81b550aeb840a6d11b6e7ff94f26377f5e5555c74d67e47  tests/engine/test_spatial_effects.py
f6fbc6b87ff925237acad2620bf2f55a076eb2245ed161387721c8870b78a96b  tests/engine/test_spatial_condition_performance_contract.py
5aad9150ada74f3cf8b79b3f43407116a30f0b072d92308bc6470c5955e4b1a2  tests/engine/test_spell_families.py
9aea26a7682f8e4315f6fa10604bbca599113a38488f060e46ed4ce217e55138  tests/engine/test_traversal_connectors.py
```

The Phase 6 plan remains raw SHA
`154b0d9d92cadacbe167ec5908e576398a53377373c94c52862d2746d288f0da`; the
rejected manifest remains raw SHA
`a60c688b5e959139f5927480e655bdff44b2af6fcaca9a23ae4dff1bd307474e` and was
not changed. No production/test file outside the 15 repair paths was edited
in this checkpoint. The accepted Phase 5/Phase 6 dirty work and all excluded
server, deprecated, SDK, transport, generated, renderer, editor,
cross-language, inactive-content, and governance paths remain preserved.

This is a repair checkpoint, not a certification or final-manifest update.
The omitted accepted Slice 6.1 owner-model node and the invalid rejected
650/19/9 accounting are explicitly reserved for the next coordinator-approved
certification union; this checkpoint does not claim a corrected final node set.

Status: `READY_FOR_COORDINATOR_REVIEW`.

### Strict set_tile bypass proof correction

The strict-coordinate regression was corrected to exercise the original
candidate-Tile bypass directly. It now constructs a valid prebuilt Tile,
passes that unchanged candidate through `GridMap.set_tile(..., tile=candidate)`
with the default `fire_event=True`, and tries the exact invalid bool, float,
and string coordinates. The public candidate position/registration, map and
reverse lookup, revisions, and event cursor remain unchanged for every case.

Exact selector and result:

```
.venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_runtime_identity_registries.py::test_set_tile_rejects_non_exact_coordinates_before_any_public_change
3 passed in 3.91s
```

The corrected current raw SHA for
`tests/engine/test_runtime_identity_registries.py` is
`0056324836d5f314149ae347c64ea39563c8d95f7c751b017b15040c8317d33c`.
No manifest was changed or regenerated; the rejected manifest SHA remains
`a60c688b5e959139f5927480e655bdff44b2af6fcaca9a23ae4dff1bd307474e`.

Status: `READY_FOR_COORDINATOR_REVIEW`.

## Second bounded Phase 6 rejected-review repair checkpoint — READY_FOR_COORDINATOR_REVIEW

This second repair addresses the rejected candidate recorded at manifest SHA
`a60c688b5e959139f5927480e655bdff44b2af6fcaca9a23ae4dff1bd307474e`, ledger
SHA `3d786ea9ad0487f6f057f2cb561963ba3c62583723989456482b0d0db5f3958d`, and
684-node hash
`dd8e28a91615f278146a030149478d75bdd7293bc553ecd70ef95084f4f2aa33`.
The rejected manifest remains intentionally unchanged. Final node accounting
and certification remain pending coordinator approval.

### Bounded repairs

- `dnd/spatial/area_conditions.py` now uses one narrow owner-local
  `_iter_work_positions` iterator. It increments only while the existing
  structured operation is active and covers admission, including the
  OVERLAPPING early-return validation, physical-optics snapshots and
  comparisons, authored footprint filtering, pending terrain capture,
  publication and discard, terrain apply/removal, and AreaCondition release
  and trigger position scans. No collaborator-owned GridMap/EventQueue work
  is counted and no synthetic map-area counter was added.
- The set-tile regression constructs a valid prebuilt globally registered but
  unindexed Tile, then calls the public command with default `fire_event=True`
  and bool, float, and string coordinates. It proves the candidate
  position/registration, public Tile map and UUID lookup, revisions, and event
  cursor remain unchanged.
- The specialized relocation regression activates Antimagic Field and
  Continual Flame through public setup first; Continual Flame uses a placed
  public BaseItem anchor. It proves active footprints, public resolved-light
  state, attached source state, suppression state, revisions, and event cursor
  remain exact after all three invalid coordinate forms.
- The path proof primes public `GridMap.width` and `height` before the
  steady-state compute. The public flying proof spends 20 feet through the
  public action-economy API, leaving a 10-foot budget, and proves the 10-foot
  target executes while the 15-foot target is absent. The collaborator
  `get_all_connectors` monkeypatch was removed. The two spell-test indentation
  residues were corrected.
- The duplicate behavior-only selector
  `tests/engine/test_elevation_performance_contract.py::test_connector_discovery_matches_endpoint_presence`
  was deleted. The equivalent public endpoint/away proof remains in
  `tests/engine/test_traversal_connectors.py` and is retained below. The
  deleted selector is recorded explicitly for later final-union accounting.

### Exact selector inputs and expanded collection

The repaired focused command had exactly seven selector inputs (selector
inputs are not expanded node IDs):

```
.venv/bin/python -m pytest --collect-only -q -p no:cacheprovider \
 tests/engine/test_runtime_identity_registries.py::test_set_tile_rejects_non_exact_coordinates_before_any_public_change \
 tests/engine/test_spatial_effects.py::test_relocation_rejects_non_exact_coordinates_without_public_mutation \
 tests/engine/test_spatial_effects.py::test_specialized_relocation_rejects_non_exact_coordinates_before_runtime_changes \
 tests/engine/test_spatial_condition_performance_contract.py::test_condition_structured_work_counts_exact_owned_footprint_iterations \
 tests/engine/test_elevation_performance_contract.py::test_path_computation_edge_queries_are_linear_in_local_map_edges \
 tests/engine/test_progressive_elevation_movement.py::test_flying_discovery_uses_directed_edge_costs_and_affordability \
 tests/engine/test_traversal_connectors.py::test_connector_discovery_matches_endpoint_presence
15 tests collected in 4.50s
```

The exact expanded node IDs were:

```
tests/engine/test_runtime_identity_registries.py::test_set_tile_rejects_non_exact_coordinates_before_any_public_change[True-2]
tests/engine/test_runtime_identity_registries.py::test_set_tile_rejects_non_exact_coordinates_before_any_public_change[1.5-2]
tests/engine/test_runtime_identity_registries.py::test_set_tile_rejects_non_exact_coordinates_before_any_public_change[1-2]
tests/engine/test_spatial_effects.py::test_relocation_rejects_non_exact_coordinates_without_public_mutation[invalid_position0]
tests/engine/test_spatial_effects.py::test_relocation_rejects_non_exact_coordinates_without_public_mutation[invalid_position1]
tests/engine/test_spatial_effects.py::test_relocation_rejects_non_exact_coordinates_without_public_mutation[invalid_position2]
tests/engine/test_spatial_effects.py::test_specialized_relocation_rejects_non_exact_coordinates_before_runtime_changes[invalid_position0]
tests/engine/test_spatial_effects.py::test_specialized_relocation_rejects_non_exact_coordinates_before_runtime_changes[invalid_position1]
tests/engine/test_spatial_effects.py::test_specialized_relocation_rejects_non_exact_coordinates_before_runtime_changes[invalid_position2]
tests/engine/test_spatial_condition_performance_contract.py::test_condition_structured_work_counts_exact_owned_footprint_iterations[recipe0-SpatialCondition-16-12]
tests/engine/test_spatial_condition_performance_contract.py::test_condition_structured_work_counts_exact_owned_footprint_iterations[recipe1-FireSurface-28-16]
tests/engine/test_elevation_performance_contract.py::test_path_computation_edge_queries_are_linear_in_local_map_edges[False]
tests/engine/test_elevation_performance_contract.py::test_path_computation_edge_queries_are_linear_in_local_map_edges[True]
tests/engine/test_progressive_elevation_movement.py::test_flying_discovery_uses_directed_edge_costs_and_affordability
tests/engine/test_traversal_connectors.py::test_connector_discovery_matches_endpoint_presence
```

The exact selector execution was:

```
.venv/bin/python -m pytest -q -p no:cacheprovider [the seven selectors above]
15 passed in 11.98s
```

The two structured-work nodes are the parameterized condition nodes above.
The path, flying, and connector nodes are behavior/public-locality checks;
the warm action-discovery proof remains behavioral projection invariance and
is not a structured-work proof. The deleted elevation connector selector was
not collected or executed after removal.

### Locality and validation results

The owner-local structured counts remained positive and equal for the same
footprint/local geometry:

```
path size=20 distances=169 edge_queries=1352
path size=80 distances=169 edge_queries=1352
condition size=24 footprint=64 activation_positions=448 deactivation_positions=256
condition size=72 footprint=64 activation_positions=448 deactivation_positions=256
```

The exact four-cell condition proof asserts OVERLAPPING activation/deactivation
`16/12` and exclusive activation/deactivation `28/16`. No selector is called
a work counter unless it reports the existing owner-local structured count.

Post-deletion reruns:

```
.venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_elevation_performance_contract.py
4 passed in 10.47s
.venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_traversal_connectors.py::test_connector_discovery_matches_endpoint_presence
1 passed in 4.30s
.venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_runtime_identity_registries.py
15 passed in 4.87s
.venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_spatial_condition_performance_contract.py
4 passed in 6.58s
.venv/bin/python -m pytest -q -p no:cacheprovider tests/architecture
45 passed in 27.25s
.venv/bin/python -m pytest -q -p no:cacheprovider tests/architecture/test_phase_6_completion_gates.py tests/architecture/test_dependency_boundaries.py tests/architecture/test_source_model_hygiene.py
36 passed in 14.38s
```

The previously executed affected groups, whose production/test behavior was
unchanged by this deletion, were condition/optics/senses `120 passed`,
movement/path/connector `102 passed`, spell `62 passed`, and architecture
`45 passed`. The current post-deletion full elevation, retained connector,
runtime identity, spatial locality, and architecture reruns are listed above.

Compile and scope checks:

```
.venv/bin/python -m compileall -q tests/engine/test_elevation_performance_contract.py
exit 0
git diff --check -- tests/engine/test_elevation_performance_contract.py
exit 0; only existing LF/CRLF normalization notices
```

The applicable hard-cut/dependency/locality checks are green: the removed
elevation duplicate has no remaining reference, the retained traversal
selector is the sole focused connector proof, and no stale private mover,
full-map path scan, synthetic condition count, connector collaborator
monkeypatch, or unused private-name bookkeeping was found. Remaining
`get_all_connectors` matches are the retained public API and public result
assertions. No excluded path was edited.

### Current repair-path bytes and scope

The exact current hashes of the eight Python paths changed in this second
repair are:

```
0eec4ba65c2556efa0eba172045a4d24e37b24d2e5bc7033ec1319619f4137ca  dnd/spatial/area_conditions.py
0056324836d5f314149ae347c64ea39563c8d95f7c751b017b15040c8317d33c  tests/engine/test_runtime_identity_registries.py
4a1401ef94e3013c61a6adae8f73401ebe87fdddeac1fb0cb45a19046b759704  tests/engine/test_spatial_effects.py
34e0c88c7eabf506d653d93c2efb39ebf72abb1cb937053aaf8f35baae6a941b  tests/engine/test_spatial_condition_performance_contract.py
81c46f13694920454c8561eabb42d083681591b2064616a10c0e3536f621a009  tests/engine/test_elevation_performance_contract.py
050c5d1775f5157e6a225e6e3396c33246b9636e08c49247e861fa3539459dab  tests/engine/test_progressive_elevation_movement.py
0970c3d5b9c20337b5b4c3894397ed7844ac8db27c2719b87968be332ce82875  tests/engine/test_traversal_connectors.py
1cf743db01c0510cad96c9e2d820f266131aee98f667d93ef38e771a7238a38a  tests/engine/test_spell_families.py
```

The exact authorized repair paths are those eight Python files plus this
ledger. No other production/test path was edited in this second repair. The
rejected manifest remains raw SHA
`a60c688b5e959139f5927480e655bdff44b2af6fcaca9a23ae4dff1bd307474e`, was not
regenerated, and its final node accounting remains intentionally pending.
No final certification or independent review was performed. The moved
checkpoint is physically last so the preflight diagnostic table remains
contiguous before it.

Status: `READY_FOR_COORDINATOR_REVIEW`.
## Slice 6.5 final certification and freeze — READY_FOR_INDEPENDENT_REVIEW

This corrected certification-only checkpoint supersedes the prior 690-node
freeze. No production or test byte was edited during this rebuild; no behavior
repair was performed.

### Authorities and accepted baseline

- Phase 6 plan raw SHA-256:
  154b0d9d92cadacbe167ec5908e576398a53377373c94c52862d2746d288f0da.
- Accepted Phase 5 manifest: 80 members, raw SHA-256
  c10171e9e64ea96ca93f0b971917aad1824654d950a82bed1b7cb516cbef70b1.
- Accepted Phase 5 semantic baseline: 650 nodes, normalized SHA-256
  8202c5f659be52244112818848d40d01f2a358adf3cce17200ccd075e172c2e6.
- The accepted Phase 5 baseline remains the authority. Its current maintained
  path/selector inputs recollected 666 nodes because authorized Phase 6 nodes
  are now present in those maintained files; that is not baseline drift.

### Exact corrected input accounting

The final manifest records every exact path/selector input in
collection_inputs and every sorted node ID in
node_set_accounting.final_nodes. The deduplicated input count is 84:
27 accepted-Phase-5 frozen paths, 26 accepted-Phase-5 outside selectors,
19 admitted-existing Phase 6 selectors, 11 authorized Phase 6 selectors, and
1 omitted accepted Slice 6.1 selector. The authorized category is therefore
11 selector inputs and 14 expanded nodes.

The two selectors added in this corrected rebuild are:
tests/engine/test_runtime_identity_registries.py::test_set_tile_rejects_non_exact_coordinates_before_any_public_change
tests/engine/test_spatial_condition_performance_contract.py::test_condition_structured_work_counts_exact_owned_footprint_iterations

The omitted accepted Slice 6.1 selector is:
tests/engine/test_runtime_identity_registries.py::test_slice_6_1_position_owners_are_strict_and_base_blocks_are_neutral

The deleted duplicate remains excluded:
tests/engine/test_elevation_performance_contract.py::test_connector_discovery_matches_endpoint_presence

The category recollections, using sorted unique node IDs joined with one
terminal newline and SHA-256 of the UTF-8 bytes, were:
- accepted Phase 5 current path/selector union: 666 nodes,
  00deadec475082bad408bd8b31bacbfa4bcae9a0a5b833a59c93edf247337c50;
- admitted existing Phase 6: 19 nodes,
  3f6cce7327dde51e1bc9b5654e518de8cf87fcd41422915dc48d27105b69d57a;
- authorized Phase 6: 14 nodes,
  433575ad28a7648b96635e65cecae6bc13c059effc7a36cf363123ce6cc33468;
- omitted accepted Slice 6.1: 1 node,
  0437f3fcde355fe02ec3ae5f59642abe54529d878848afc30d85e45e0aaad26f.

After sorted deduplication, the exact final union contains 695 unique nodes
with normalized SHA-256
efa4e7fc84129d246b523d413e7c27e7434047934d87337f8b9d3947ae26c48a.
The exact ordered node list was executed as individual NUL-safe argv entries
with .venv/bin/python -m pytest -q -p no:cacheprovider:

695 passed in 263.07s (0:04:23)

The manifest is the machine-verifiable record of all 695 sorted node IDs;
the count and hash were recollected rather than inferred from the rejected
manifest.

### Exact path and selector inputs

Accepted Phase 5 frozen path inputs:

- tests/engine/test_tile_surface_contract.py
- tests/engine/test_world_edge_identity_and_elevation.py
- tests/engine/test_senses_light_stealth.py
- tests/engine/test_grid_pathfinding.py
- tests/engine/test_action_discovery.py
- tests/engine/test_elevation_proving_battlefield.py
- tests/engine/test_elevation_performance_contract.py
- tests/engine/test_spatial_effects.py
- tests/engine/test_direct_spatial_effect_materialization.py
- tests/engine/test_condition_lifecycle.py
- tests/engine/test_event_lifecycle.py
- tests/engine/test_event_wire_visibility_contract.py
- tests/engine/test_objective_state.py
- tests/engine/test_direct_scenario_deployment.py
- tests/engine/test_items_inventory_equipment.py
- tests/engine/test_spell_families.py
- tests/engine/test_move_settlement.py
- tests/engine/test_action_cost_and_position_commit.py
- tests/engine/test_traversal_connectors.py
- tests/engine/test_elevated_jump_transaction.py
- tests/engine/test_runtime_reset.py
- tests/engine/test_manual_11_grid_tiles_terrain_movement.py
- tests/architecture
- tests/manual/test_08_world_model_and_movement.py
- tests/manual/test_37_authored_encounter_mechanics.py
- tests/manual/test_72_battlefield_deployment_catalog.py
- tests/manual/test_17_encounters_turns_controllers.py::test_turn_start_full_senses_refresh_emits_seen_cell_delta
Accepted Phase 5 outside selector inputs:
- tests/engine/test_runtime_identity_registries.py::test_entity_membership_has_no_block_route_and_rejects_live_tile_mutations
- tests/engine/test_runtime_identity_registries.py::test_entity_tile_membership_is_defensive_and_co_located_noop_is_quiet
- tests/engine/test_runtime_identity_registries.py::test_suspended_entity_keeps_game_identity_without_observer_or_second_left
- tests/engine/test_runtime_identity_registries.py::test_missing_tile_move_is_publicly_atomic_for_occupancy_events_light_and_senses
- tests/engine/test_runtime_identity_registries.py::test_public_entity_lifecycle_revision_deltas_are_exact
- tests/engine/test_runtime_identity_registries.py::test_entity_membership_queries_are_map_size_invariant_at_public_boundary
- tests/engine/test_condition_transform_ownership.py::test_banishment_suspend_precommit_failure_is_publicly_atomic
- tests/engine/test_condition_transform_ownership.py::test_banishment_suspend_publication_failure_compensates_without_condition_or_denial
- tests/engine/test_condition_transform_ownership.py::test_banishment_provisional_failure_releases_all_denial_ownership
- tests/engine/test_condition_transform_ownership.py::test_banishment_owns_denial_and_restores_spatial_registration
- tests/engine/test_condition_transform_ownership.py::test_banishment_restore_failure_keeps_condition_retryable_and_then_cleans_up
- tests/engine/test_condition_transform_ownership.py::test_banishment_restore_publication_failure_keeps_presence_and_finishes_cleanup
- tests/engine/test_life_state_ownership.py::test_undeployed_attached_light_stays_absent_until_public_deploy
- tests/engine/test_life_state_ownership.py::test_world_presence_and_death_light_suppressions_compose_through_restore
- tests/engine/test_life_state_ownership.py::test_death_suppresses_lights_reversibly_and_preserves_other_owners
- tests/engine/test_life_state_ownership.py::test_light_desired_state_and_nonblocking_survive_death_and_revival
- tests/engine/test_life_state_ownership.py::test_revival_reintroduces_entity_to_incremental_senses
- tests/engine/test_combat_actions.py::test_pack_tactics_public_attack_respects_co_located_ally_presence
- tests/engine/test_combat_actions.py::test_sneak_attack_public_damage_respects_co_located_ally_presence
- tests/manual/test_133_new_spells_batch4_legacy_contract.py::test_banishment_removes_and_restores_spatial_perception
- tests/manual/test_133_new_spells_batch4_legacy_contract.py::test_banishment_return_selects_one_stable_origin_occupant
- tests/manual/test_133_new_spells_batch4_legacy_contract.py::test_banishment_return_displaces_an_occupant
- tests/manual/test_133_new_spells_batch4_legacy_contract.py::test_banishment_return_co_locates_when_every_displacement_offset_is_blocked
- tests/manual/test_133_new_spells_batch4_legacy_contract.py::test_banishment_successful_save_preserves_spatial_state
- tests/manual/test_53_srd_monster_traits.py::test_pack_tactics_sunlight_and_keen_senses_use_contextual_values
- tests/engine/test_condition_transform_ownership.py::test_banishment_compensation_failure_preserves_publication_chain_without_presence
Admitted existing Phase 6 selector inputs:
- tests/manual/test_84_generic_roster_duels.py::test_generic_duel_assembles_two_multi_actor_creature_rosters
- tests/manual/test_84_generic_roster_duels.py::test_mirrored_roster_keeps_runtime_identity_isolated_by_faction
- tests/manual/test_84_generic_roster_duels.py::test_character_style_and_creature_rosters_share_one_assembler
- tests/manual/test_150_prepared_scenario_lifecycle.py::test_prepared_scenario_does_not_start_before_final_controllers_are_installed
- tests/engine/test_progressive_elevation_movement.py::test_walking_height_change_requires_both_matching_progressive_endpoints
- tests/engine/test_progressive_elevation_movement.py::test_cliffs_block_walk_swim_burrow_and_forced_displacement_but_not_fly
- tests/engine/test_progressive_elevation_movement.py::test_forced_movement_revalidates_each_leg_after_effect_topology_change
- tests/engine/test_progressive_elevation_movement.py::test_diagonal_plateau_needs_one_height_legal_cardinal_bridge
- tests/engine/test_progressive_elevation_movement.py::test_walking_like_diagonal_cannot_change_endpoint_elevation
- tests/engine/test_progressive_elevation_movement.py::test_fly_path_and_move_settlement_use_one_support_distance_cost
- tests/engine/test_progressive_elevation_movement.py::test_flying_discovery_uses_directed_edge_costs_and_affordability
- tests/engine/test_progressive_elevation_movement.py::test_progressive_walking_cost_uses_destination_terrain_not_vertical_distance
- tests/engine/test_spatial_effect_reveal_idempotency.py::test_hidden_effect_reveals_once_then_becomes_a_true_noop
- tests/engine/test_spatial_effect_reveal_idempotency.py::test_installed_visible_effect_does_not_invent_a_reveal
- tests/engine/test_spatial_effect_reveal_idempotency.py::test_uninstalled_effect_cannot_be_revealed
- tests/engine/test_spatial_effect_reveal_idempotency.py::test_reveal_veto_preserves_concealment_and_allows_one_later_reveal
- tests/engine/test_spatial_effect_reveal_idempotency.py::test_reentrant_reveal_request_does_not_create_a_nested_lifecycle
- tests/engine/test_spatial_effect_reveal_idempotency.py::test_retired_revealed_effect_still_fails_installation_check_first
- tests/engine/test_combat_actions.py::test_eb_10_021_forced_movement_traverses_terrain_without_step_costs
Authorized Phase 6 selector inputs:
- tests/architecture/test_phase_6_completion_gates.py::test_slice_6_4_master_dependency_arrows_are_ast_enforced
- tests/architecture/test_phase_6_completion_gates.py::test_slice_6_4_gridmap_is_the_only_tile_and_reverse_placement_owner
- tests/architecture/test_phase_6_completion_gates.py::test_slice_6_4_senses_projection_has_one_runtime_writer_boundary
- tests/architecture/test_phase_6_completion_gates.py::test_slice_6_4_retired_inventory_has_explicit_retained_and_excluded_allowlists
- tests/engine/test_spatial_condition_performance_contract.py::test_spatial_condition_work_scales_with_covered_cells
- tests/engine/test_spatial_condition_performance_contract.py::test_spatial_condition_work_does_not_scale_with_unused_world_area
- tests/engine/test_combat_actions.py::test_spike_trap_ordinary_step_resolves_damage_and_continues
- tests/engine/test_combat_actions.py::test_spike_trap_lethal_step_stops_at_the_trigger_tile
- tests/engine/test_tile_surface_contract.py::test_same_xy_door_open_and_orient_preserve_anchor_placement
- tests/engine/test_runtime_identity_registries.py::test_set_tile_rejects_non_exact_coordinates_before_any_public_change
- tests/engine/test_spatial_condition_performance_contract.py::test_condition_structured_work_counts_exact_owned_footprint_iterations
Omitted accepted Slice 6.1 selector input:
- tests/engine/test_runtime_identity_registries.py::test_slice_6_1_position_owners_are_strict_and_base_blocks_are_neutral

### Node history and exact rename accounting

The connector discovery selector history is:
1. tests/engine/test_traversal_connectors.py::test_connector_discovery_uses_only_endpoint_index
2. tests/engine/test_traversal_connectors.py::test_connector_discovery_uses_only_local_endpoint_lookup
3. tests/engine/test_traversal_connectors.py::test_connector_discovery_matches_endpoint_presence

The elevation-performance duplicate
tests/engine/test_elevation_performance_contract.py::test_connector_discovery_matches_endpoint_presence
was deleted and is not in the final node set.

### Certification gates

- Complete tests/architecture: 45 passed in 28.47s.
- Targeted dependency/authority/runtime-schema architecture group:
  36 passed in 15.10s.
- Affected spatial/path/event/scenario behavior group: 151 passed in 34.09s.
- Lifecycle/locality group: 105 passed in 29.04s.
- Governed active Python compilation: all 91 manifest members compiled, exit 0.
- Repository and scoped git diff --check: exit 0; existing LF/CRLF
  normalization notices only.
- Dependency, authority, locality, replay, hard-cut, and runtime-schema gates:
  green. Locality retained positive bounded owner work: path edge
  consultations 1352/1352 for equal local geometry and SpatialCondition
  owner-local counts 448/256 for both map sizes.
- All 91 governed members were present, unique, and current with zero hash
  mismatches.
- The exact 695-node union execution above was green.

### Repository-wide diagnostic comparison

The exact diagnostic command
.venv/bin/python -m pytest --collect-only -q -p no:cacheprovider returned
exit 2 with 1406 tests collected and 105 errors in 19.20s. The terminal
classes were 97 ModuleNotFoundError, 4 ImportError, and 4 FileNotFoundError.
The normalized signature remained
eccd100453848ac9af6a6e028692862dbf0866daaf0c0e3d275b13d4d4e06cd9,
identical to preflight. All 105 rows are governed excluded
dnd.content_system/server/removed content-progression-presentation-devtool
families; no active member is represented.

### Final active-only manifest and scope

The final active-only manifest is
DND_TILE_WORLD_ITEM_PHASE_6_IMPLEMENTATION_MANIFEST_2026-08-26.json.
Its raw SHA-256 is
425deda5bb0a204cb1963d24569ebdfe41811591f841d80abd289f5b9ce92f71.
It contains 91 sorted unique current members: 41 production and 50 active
collecting tests. All 91 members exist and match their recorded raw hashes.

The exact 49 current changed active paths are:

- dnd/blocks/base_item.py
- dnd/blocks/equipment.py
- dnd/blocks/sensory.py
- dnd/content/items/authored_item_builders.py
- dnd/content/items/authored_item_definitions.py
- dnd/content/items/environment_item_builders.py
- dnd/content/scenarios/battlefield_builders.py
- dnd/content/scenarios/battlefield_definitions.py
- dnd/content/spike_trap_materialization.py
- dnd/core/base_actions.py
- dnd/core/base_block.py
- dnd/core/base_tiles.py
- dnd/core/events/item_events.py
- dnd/core/events/world_events.py
- dnd/core/gridmap.py
- dnd/entities/entity.py
- dnd/extensions/field_focus.py
- dnd/items/consumables.py
- dnd/items/environment.py
- dnd/items/environment_interactables.py
- dnd/items/spell_items.py
- dnd/items/torches.py
- dnd/maps/arena_layout.py
- dnd/spatial/area_conditions.py
- dnd/spells/abjuration.py
- dnd/spells/conjuration.py
- dnd/spells/evocation.py
- tests/architecture/test_phase_6_completion_gates.py
- tests/engine/test_action_discovery.py
- tests/engine/test_combat_actions.py
- tests/engine/test_direct_item_content.py
- tests/engine/test_direct_scenario_deployment.py
- tests/engine/test_elevation_performance_contract.py
- tests/engine/test_elevation_proving_battlefield.py
- tests/engine/test_event_wire_visibility_contract.py
- tests/engine/test_grid_pathfinding.py
- tests/engine/test_progressive_elevation_movement.py
- tests/engine/test_runtime_identity_registries.py
- tests/engine/test_senses_light_stealth.py
- tests/engine/test_spatial_condition_performance_contract.py
- tests/engine/test_spatial_effects.py
- tests/engine/test_spell_families.py
- tests/engine/test_tile_surface_contract.py
- tests/engine/test_traversal_connectors.py
- tests/engine/test_world_edge_identity_and_elevation.py
- tests/manual/test_08_world_model_and_movement.py
- tests/manual/test_17_encounters_turns_controllers.py
- tests/manual/test_37_authored_encounter_mechanics.py
- tests/manual/test_72_battlefield_deployment_catalog.py

The governance artifacts, including this ledger and the final manifest, are
excluded from membership. Excluded scope remains server/deprecated-server,
dnd/content_system, SDK/transport/generated/renderer/editor/cross-language,
inactive legacy/content-system/circus/progression tests,
dnd/items/environment_content.py, caches, temporary output, and governance
Markdown. No excluded active path is a member.

The previously rejected 690-node manifest SHA
c51230d7b8952ca996bfba5c1dbb3af4f912539b58971beaa1b49b0bca42d3cc and its
associated 690-node ledger claims are superseded by this corrected artifact.
No code or test byte was changed after the validation run. This candidate is
frozen for independent review.

Status: READY_FOR_INDEPENDENT_REVIEW.

### Final independent review metadata

Both required independent reviews approved this exact candidate:

- Governing Phase 6 plan SHA-256:
  154b0d9d92cadacbe167ec5908e576398a53377373c94c52862d2746d288f0da.
- Final active-only manifest SHA-256:
  425deda5bb0a204cb1963d24569ebdfe41811591f841d80abd289f5b9ce92f71.
- Pre-review ledger SHA-256:
  48fa515076f90d9f4266067f2677c9e8d390e27ce634663e1be316ed084803ee.
- Exact node set: 695 nodes, normalized SHA-256
  efa4e7fc84129d246b523d413e7c27e7434047934d87337f8b9d3947ae26c48a.

Correctness/replay/scope verdict: APPROVED. The review confirmed 91/91
member hashes, 84 inputs, independent 695-node execution, 49 changed active
paths, architecture, event order, committed facts, replay, schema, locality,
hard cuts, scope, and public proofs.

Anti-slop/dependency/locality/test-quality verdict: APPROVED + ANTI-SLOP
APPROVED. No blocker remains.

Status: PHASE_6_COMPLETE — ACCEPTED.
