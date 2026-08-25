# Phase 0–2 Tile-side geometry correction pre-edit ledger

Status: FROZEN PRE-EDIT BASELINE. No production or test file was changed for
this correction checkpoint. Phase 1 has not started.

## Governing inputs and hash verification

| Input | Verified SHA-256 |
| --- | --- |
| `DND_TILE_WORLD_ITEM_VERTICAL_BOUNDARY_MIGRATION_PLAN_2026-08-17.md` | `73335294139bdc81306f17381afe22f27fb94c9c48bcf07c1312eb9eeefafe63` |
| master substantive approved SHA | `46de9f570fb59fd8c9e8a105a3a699287a7881c93c880827d804faefad9c7f2d` |
| `DND_TILE_WORLD_ITEM_PHASES_0_1_2_SIDE_GEOMETRY_CORRECTION_PLAN_2026-08-24.md` | `ae189282687fdcb7baa88ca3b393af593c6db345029a89da9cfcc36b76f021c1` |
| correction-plan substantive approved SHA | `d7d423408fd79796c53d2ffac1b95b536e3b53ae6a57416ac6143391949ec33f` |
| `unified_vision_light.md` | `3c9c58483440640837bc38fdaa6b624f358e1098c9a957f65923cd64f83a270b` |
| accepted Phase 0–2 manifest | `34de6db66c80d336044ab90abd13e284971722551d4d2018678a12808971aad9` |

`agents.md` and all 517 lines of `HOW_TO_TEST.MD` were read before test work;
all 528 lines of the correction plan were read before this ledger was frozen.
The revoked `DND_TILE_WORLD_ITEM_PHASE_3_IMPLEMENTATION_GUIDANCE_2026-08-24.md`
was not used.

## Accepted scoped manifest baseline

The accepted manifest algorithm is: enumerate the repository's modified or
untracked `.py` and `.json` files, excluding this manifest and the plan/ledger
Markdown files; sort paths lexically; hash each file's raw bytes with SHA-256;
store one `{path, sha256}` row per member. The accepted manifest contains 88
members. Verification before this ledger edit reported:

```text
manifest_member_count=88
duplicate_members=0
member_mismatches=[]
actual_scoped_member_count=88
missing_from_manifest=[]
extra_in_manifest=[]
```

The accepted manifest itself has SHA-256
`34de6db66c80d336044ab90abd13e284971722551d4d2018678a12808971aad9`.

## Complete collection baseline

Command, with the repository virtual environment and the cache plugin disabled:

```text
./.venv/bin/pytest --collect-only -q -p no:cacheprovider
```

Result: exit 2; 1,314 collected node IDs; 105 collection errors; 113 modules
with collected nodes; 105 blocked modules; 218 modules in the complete union.
The complete sorted node set is identified by SHA-256
`1a62a543af12b8178a4881d0815e70ad533d7263e833108caab11d7f9447dfb6`.
The successful-module set (113 paths) has SHA-256
`8a609e8b85157ad9c1db2e085c4f3ca82a6bcb9e4abc84ee4e278da4912873bb`.
The blocked-module set (105 paths) has SHA-256
`ff2ebd76d5772a93dff7723f9869316eb92fe05b10d7b916a6465005ef6bf531`.
The complete 218-path module union has SHA-256
`003720b0a00ac1ab53af1aabdebaeaf10b324b7e7a7e92b0d25e1e702e6ef7a6`.
These hashes are over sorted paths joined by one newline.

The 113 modules with collected nodes are:

```text
tests/architecture/test_action_discovery_requirements.py
tests/architecture/test_content_ledger_boundary.py
tests/architecture/test_dependency_boundaries.py
tests/architecture/test_source_model_hygiene.py
tests/architecture/test_spell_catalog_composition.py
tests/engine/test_action_cost_and_position_commit.py
tests/engine/test_action_discovery.py
tests/engine/test_block_context.py
tests/engine/test_cold_presentation_facts.py
tests/engine/test_combat_actions.py
tests/engine/test_condition_lifecycle.py
tests/engine/test_condition_transform_ownership.py
tests/engine/test_direct_behavior_identity.py
tests/engine/test_direct_item_content.py
tests/engine/test_direct_monster_creation.py
tests/engine/test_direct_scenario_deployment.py
tests/engine/test_direct_spatial_effect_materialization.py
tests/engine/test_effect_origin.py
tests/engine/test_elevated_jump_transaction.py
tests/engine/test_elevation_distance_and_threat.py
tests/engine/test_elevation_performance_contract.py
tests/engine/test_elevation_proving_battlefield.py
tests/engine/test_entity_composition.py
tests/engine/test_entity_creation_progression_core.py
tests/engine/test_event_lifecycle.py
tests/engine/test_event_wire_visibility_contract.py
tests/engine/test_grid_pathfinding.py
tests/engine/test_items_inventory_equipment.py
tests/engine/test_life_state_ownership.py
tests/engine/test_manual_05_events_before_handlers.py
tests/engine/test_manual_06_dice_and_roll_result_events.py
tests/engine/test_manual_07_entity_composition.py
tests/engine/test_manual_08_blocks_ownership_context_cleanup.py
tests/engine/test_manual_09_conditions.py
tests/engine/test_manual_10_standard_conditions.py
tests/engine/test_manual_11_grid_tiles_terrain_movement.py
tests/engine/test_modifiable_value_semantics.py
tests/engine/test_move_settlement.py
tests/engine/test_objective_state.py
tests/engine/test_progressive_elevation_movement.py
tests/engine/test_runtime_identity_registries.py
tests/engine/test_runtime_reset.py
tests/engine/test_senses_light_stealth.py
tests/engine/test_spatial_condition_performance_contract.py
tests/engine/test_spatial_effect_reveal_idempotency.py
tests/engine/test_spatial_effects.py
tests/engine/test_spatial_restraints.py
tests/engine/test_spell_families.py
tests/engine/test_standard_conditions.py
tests/engine/test_tile_surface_contract.py
tests/engine/test_traversal_connectors.py
tests/engine/test_world_edge_identity_and_elevation.py
tests/manual/test_01_runtime_identity_and_registries.py
tests/manual/test_02_entity_anatomy.py
tests/manual/test_03_values_and_modifiers.py
tests/manual/test_04_dice_rolls.py
tests/manual/test_05_event_lifecycle.py
tests/manual/test_06_reactions_to_events.py
tests/manual/test_07_conditions_and_cleanup.py
tests/manual/test_08_world_model_and_movement.py
tests/manual/test_10_combat_resolution.py
tests/manual/test_126_action_override_runtime.py
tests/manual/test_126_jump_legacy_contract.py
tests/manual/test_126_shatter.py
tests/manual/test_126_two_weapon_fighting_legacy_contract.py
tests/manual/test_127_lightning_bolt.py
tests/manual/test_128_antimagic_field.py
tests/manual/test_129_disintegrate.py
tests/manual/test_130_tier2_spells.py
tests/manual/test_131_tier1_spell_legacy_gaps.py
tests/manual/test_133_item_core_lifecycle_legacy_contract.py
tests/manual/test_133_new_spells_batch4_legacy_contract.py
tests/manual/test_134_cleric_batch1_legacy_contract.py
tests/manual/test_136_healing_spell_legacy_contract.py
tests/manual/test_137_sense_buff_spell_legacy_contract.py
tests/manual/test_138_mixed_damage_spell_contract.py
tests/manual/test_13_spellcasting_core.py
tests/manual/test_140_shake_awake_trigger.py
tests/manual/test_141_combat_condition_legacy_contract.py
tests/manual/test_143_condition_removal_legacy_contract.py
tests/manual/test_148_event_lifecycle_legacy_contract.py
tests/manual/test_14_spell_families.py
tests/manual/test_150_prepared_scenario_lifecycle.py
tests/manual/test_17_encounters_turns_controllers.py
tests/manual/test_184_turn_execution_identity.py
tests/manual/test_190_encounter_recipe_foundation.py
tests/manual/test_191_authored_encounter_catalog.py
tests/manual/test_22_playable_scenario_packages.py
tests/manual/test_24_built_in_controllers.py
tests/manual/test_37_authored_encounter_mechanics.py
tests/manual/test_50_counterspell_engine_contract.py
tests/manual/test_53_srd_monster_traits.py
tests/manual/test_71_authored_roster_catalog.py
tests/manual/test_72_battlefield_deployment_catalog.py
tests/manual/test_84_generic_roster_duels.py
tests/manual/test_aoe_shape_legacy_contract.py
tests/manual/test_legacy_geometry_dice_coverage.py
tests/manual/test_legacy_information_privacy_coverage.py
tests/manual/test_remaining_zone_spell_legacy_contract.py
tests/manual/test_spell_critical_dice_legacy_contract.py
tests/manual/test_spike_zone_movement_legacy_contract.py
tests/manual/test_tile_condition_duration_legacy_contract.py
tests/progression/test_direct_character_creation.py
tests/progression/test_direct_class_progression.py
tests/progression/test_direct_premade_characters.py
tests/progression/test_dragonborn_origin_definitions.py
tests/progression/test_dragonborn_origin_runtime.py
tests/progression/test_half_orc_origin_runtime.py
tests/progression/test_halfling_origin_runtime.py
tests/progression/test_normal_spell_slot_capacity.py
tests/progression/test_source_owned_engine_primitives.py
tests/progression/test_spell_damage_affinity_contributions.py
tests/progression/test_spellcasting_source_action_propagation.py
```

The 105 blocked module paths are:

```text
tests/engine/test_condition_content_evidence.py
tests/engine/test_counterspell_evidence.py
tests/engine/test_dice_event_semantics.py
tests/engine/test_encounter_apis.py
tests/engine/test_equipment_domain_ownership.py
tests/engine/test_equipment_replication_facts.py
tests/engine/test_manual_14_core_combat_flow.py
tests/engine/test_manual_20_encounters_turns_controllers_apis.py
tests/engine/test_manual_21_arena_game_sessions_client_state.py
tests/engine/test_monster_presets.py
tests/engine/test_spellcasting.py
tests/manual/test_09_action_discovery_and_costs.py
tests/manual/test_102_game_summary.py
tests/manual/test_103_game_summary_store.py
tests/manual/test_112_server_life_state_contract.py
tests/manual/test_113_subjective_combat_log_projection.py
tests/manual/test_113_subjective_replication_contract.py
tests/manual/test_113_subjective_replication_routes.py
tests/manual/test_114_timeline_contracts.py
tests/manual/test_115_objective_timeline.py
tests/manual/test_116_objective_replay.py
tests/manual/test_117_player_replication_contract.py
tests/manual/test_118_game_replay.py
tests/manual/test_11_equipment_inventory_and_items.py
tests/manual/test_120_player_replication_journal.py
tests/manual/test_120_subjective_world_projection.py
tests/manual/test_121_canonical_presentation_mapper.py
tests/manual/test_122_canonical_replication_runtime.py
tests/manual/test_123_subjective_player_replay.py
tests/manual/test_125_active_weapon_stance.py
tests/manual/test_125_haste_restricted_action.py
tests/manual/test_125_subjective_objective_render_parity.py
tests/manual/test_126_action_surge_extra_attack_legacy_contract.py
tests/manual/test_126_slow_legacy_contract.py
tests/manual/test_131_advanced_item_world_legacy_contract.py
tests/manual/test_131_inventory_use_actions_legacy_contract.py
tests/manual/test_132_barbarian_unarmored_defense.py
tests/manual/test_134_stackable_usable_item_legacy_contract.py
tests/manual/test_135_cleric_batches_2_4_5_legacy_contract.py
tests/manual/test_135_stealth_lighting_legacy_contract.py
tests/manual/test_138_skeleton_units_legacy_contract.py
tests/manual/test_139_condition_presentation_contract.py
tests/manual/test_142_item_equip_hooks_legacy_contract.py
tests/manual/test_144_handler_toggle_legacy_contract.py
tests/manual/test_145_haste_legacy_manifest.py
tests/manual/test_149_remaining_legacy_contract.py
tests/manual/test_166_club_content_factory.py
tests/manual/test_167_srd_weapon_content_factories.py
tests/manual/test_169_neurodragon_weapon_content_factories.py
tests/manual/test_170_neurodragon_consumable_content_factories.py
tests/manual/test_174_premade_character_composition.py
tests/manual/test_175_character_runtime_materialization.py
tests/manual/test_178_remaining_possession_item_roots.py
tests/manual/test_180_srd_creature_possession_bindings.py
tests/manual/test_189_game_creation_visual_preview.py
tests/manual/test_18_sessions_api_client_contract.py
tests/manual/test_193_game_creation_composition.py
tests/manual/test_20_content_extension_basics.py
tests/manual/test_21_spell_and_feature_extensions.py
tests/manual/test_25_live_replication_streams.py
tests/manual/test_43_runtime_performance.py
tests/manual/test_50_movement_revalidation.py
tests/manual/test_51_srd_monster_roster.py
tests/manual/test_96_game_creation_api.py
tests/manual/test_97_event_wire_contract.py
tests/manual/test_directional_environment_legacy_contract.py
tests/manual/test_legacy_reactive_reaction_coverage.py
tests/manual/test_neurodragon_apparel_content_factories.py
tests/manual/test_neurodragon_spell_item_content_factories.py
tests/manual/test_protection_reaction_legacy_contract.py
tests/manual/test_remaining_spell_legacy_contract.py
tests/manual/test_srd_armor_content_factories.py
tests/manual/test_srd_creature_content_factories.py
tests/progression/test_barbarian_berserker_materialization.py
tests/progression/test_barbarian_character_grant_appliers.py
tests/progression/test_bg3_spell_action_economy.py
tests/progression/test_builtin_character_origins.py
tests/progression/test_character_appearance.py
tests/progression/test_character_build_validation.py
tests/progression/test_character_grant_receipt_cleanup.py
tests/progression/test_dependency_neutral_progression_foundation.py
tests/progression/test_dwarf_acolyte_authored_content.py
tests/progression/test_editable_character_creation_plans.py
tests/progression/test_fighter_champion_materialization.py
tests/progression/test_fighter_character_grant_appliers.py
tests/progression/test_fighter_progression_definitions.py
tests/progression/test_multiclass_composition.py
tests/progression/test_origin_feature_contract.py
tests/progression/test_origin_feature_definitions.py
tests/progression/test_origin_innate_spellcasting.py
tests/progression/test_origin_integration_matrix.py
tests/progression/test_origin_structural_feature_applier.py
tests/progression/test_origin_structural_primitives.py
tests/progression/test_player_character_body.py
tests/progression/test_saving_throw_context.py
tests/progression/test_schema2_character_materialization.py
tests/progression/test_schema2_sorcerer_runtime_actions.py
tests/progression/test_sorcerer_character_grant_appliers.py
tests/progression/test_sorcerer_class_materialization.py
tests/progression/test_sorcerer_progression_definitions.py
tests/progression/test_sorcerer_spell_source_materialization.py
tests/progression/test_starting_apparel_packages.py
tests/progression/test_starting_equipment_packages.py
tests/progression/test_structural_class_feature_definitions.py
```

Normalized blocked signatures, with count and first stable project frame:

| Count | Signature | First stable project frame |
| ---: | --- | --- |
| 57 | `ModuleNotFoundError: No module named 'dnd.content_system'` | `tests/engine/test_dice_event_semantics.py:49` |
| 15 | `ModuleNotFoundError: No module named 'server'` | `tests/manual/server_test_client.py:11` |
| 6 | `ModuleNotFoundError: No module named 'dnd.classes.barbarian_progression_definitions'` | `tests/progression/test_barbarian_berserker_materialization.py:9` |
| 4 | `ModuleNotFoundError: No module named 'dnd.classes.progression_definitions'` | `tests/progression/test_fighter_champion_materialization.py:10` |
| 3 | `ModuleNotFoundError: No module named 'dnd.classes.sorcerer_progression_definitions'` | `tests/progression/test_sorcerer_character_grant_appliers.py:9` |
| 3 | `ModuleNotFoundError: No module named 'dnd.core.content.runtime'` | `tests/engine/test_condition_content_evidence.py:19` |
| 3 | `ModuleNotFoundError: No module named 'dnd.monsters.bestiary_content'` | `tests/engine/test_manual_20_encounters_turns_controllers_apis.py:41` |
| 3 | `ModuleNotFoundError: No module named 'dnd.monsters.circus_fighter'` | `tests/engine/test_monster_presets.py:33` |
| 4 | `FileNotFoundError: content_data/ledgers/neuroclient_authored_item_visuals.json` | `tests/manual/test_166_club_content_factory.py:12` |
| 2 | `ImportError: dnd.presentation.EquippedVisualPolicy` | `tests/manual/test_117_player_replication_contract.py:17` |
| 2 | `ImportError: dnd.core.content.origin_features.OriginCapability` | `tests/progression/test_origin_feature_contract.py:11` |
| 1 | `ModuleNotFoundError: No module named 'devtools'` | `tests/manual/test_139_condition_presentation_contract.py:10` |
| 1 | `ModuleNotFoundError: No module named 'dnd.core.content.registry'` | `tests/progression/test_dependency_neutral_progression_foundation.py:59` |
| 1 | `ModuleNotFoundError: No module named 'dnd.scenarios.encounter_catalog'` | `tests/manual/test_96_game_creation_api.py:17` |
```

## Accepted focused-lane baseline

The accepted Phase 0–2 capability lane is the following exact 14-module set.
Each lane was rerun on 2026-08-24 with `-p no:cacheprovider` and no edits:

```text
tests/engine/test_grid_pathfinding.py
tests/engine/test_world_edge_identity_and_elevation.py
tests/engine/test_elevation_performance_contract.py
tests/engine/test_items_inventory_equipment.py
tests/engine/test_action_discovery.py
tests/engine/test_spatial_effects.py
tests/engine/test_direct_spatial_effect_materialization.py
tests/engine/test_senses_light_stealth.py
tests/engine/test_event_lifecycle.py
tests/engine/test_event_wire_visibility_contract.py
tests/engine/test_objective_state.py
tests/engine/test_direct_scenario_deployment.py
tests/engine/test_runtime_reset.py
tests/engine/test_tile_surface_contract.py
```

The exact commands were:

```text
./.venv/bin/pytest -q -p no:cacheprovider [the 14 modules above]
./.venv/bin/pytest -q -p no:cacheprovider tests/engine/test_spell_families.py
./.venv/bin/pytest -q -p no:cacheprovider tests/architecture
```

| Lane | Result | Sorted node-set SHA-256 |
| --- | --- | --- |
| 14-module capability lane | 278 passed in 55.69s | `4dde915b6e7b3e32913bad3b148946d9282d5fc99dec51b7aad47c49da47ef0a` |
| spell family | 62 passed in 22.33s | `ad7621520d51fcc44ea528ded2a6a8a21a03768150cb36f7c39155f253c572b1` |
| architecture | 42 passed in 22.06s | `d42394976e706ef4ad0a9fa01c68d479651a9ee873402602aeda198ca3e5c904` |

The exact public opposing-side trace was run without changing its expected
behavior:

```text
first_placement_succeeds=True
first_completion_success_facts=1
second_rejection=reciprocal boundary band is occupied by <incumbent UUID>
second_success_events=0
legal_single_rebuild=True
```

The current trace proves the migration case, not the corrected outcome. It
uses only `place_object`, `get_boundary_objects_at`, completed
`SpatialChangeEvent` observation, `remove_object`, and
`rebuild_object_placements`.

## Exact current caller inventory

### Ordered-view and world-edge fields

| Symbol/field | Current definitions and callers |
| --- | --- |
| `WorldEdgeView` and current `first_*`/`second_*` fields | `dnd/core/world_edges.py:73-87`; no production callers outside the type and `dnd/core/gridmap.py:727-797` |
| `get_world_edge` | `dnd/core/gridmap.py:727`; tests `tests/engine/test_world_edge_identity_and_elevation.py:84,107,116,730,750,760` and `tests/engine/test_elevation_proving_battlefield.py:142` |
| `first_tile_uuid`/`second_tile_uuid` | `tests/engine/test_world_edge_identity_and_elevation.py:90-91,731,767` |
| `structural_contributions` | `tests/engine/test_world_edge_identity_and_elevation.py:95,110,119`; `tests/engine/test_elevation_proving_battlefield.py:151-152` |
| `WorldEdgeStructuralContribution` | `dnd/core/world_edges.py:65-70`; constructed only by `dnd/core/gridmap.py:769-778` |
| `get_boundary_objects_on_edge` | definition `dnd/core/gridmap.py:3113-3155`; test-only callers `tests/engine/test_tile_surface_contract.py:391,620,636`; no production caller |

`get_world_edge` currently consumes `AdjacentEdgeKey.between` and the two
endpoint Tiles (`dnd/core/gridmap.py:733-737`), each Tile's
`directions_toward` (`dnd/core/base_tiles.py:306-322`), intrinsic/derived
directional channel checks through `allows_direction`
(`dnd/core/base_tiles.py:468-477`), Tile `uuid`, `height`,
`elevation_surface_kind`, and `slope_axis`, the all-object query
`GridMap.get_objects_at` (`dnd/core/gridmap.py:3155-3181`),
`BaseBlock.get`, and the neutral provider hook
`get_objective_directional_structural_channels`
(`dnd/core/base_block.py:174-184`). It emits the current
`WorldEdgeStructuralContribution(provider_uuid, blocked_channels)` and all
current `WorldEdgeView` fields (`key`, first/second Tile UUIDs, heights,
elevation delta, surface kinds, slope axes, and merged
`structural_contributions`) at `dnd/core/gridmap.py:768-791`.

Caller classification for this inventory is explicit:

- active production: `get_world_edge` and its only construction path are in
  `dnd/core/gridmap.py`; no active production reader consumes a `WorldEdgeView`
  field or calls `get_boundary_objects_on_edge`;
- active tests: the three listed engine files are the only readers of the
  current edge fields/helpers, and `test_tile_surface_contract.py` contains the
  public opposing-side and rebuild migration cases;
- blocked collecting modules: repository-wide exact-symbol search found no
  blocked test module calling these helpers or reading these edge fields;
- deprecated: reciprocal terminology and independent legacy edge projection
  remain only in `deprecated/server_deprecated/world_projection.py:577-603`
  and `deprecated/server_deprecated/subjective_parity_diagnostics.py:204,406,526-544`;
  these do not call the active GridMap APIs; and
- generated: no generated Python/JSON caller or generated edge view contract
  was found.

### Reciprocal/opposite collision and staging

| Current residue | Exact locations |
| --- | --- |
| `staged_physical_edge_occupants` parameter/probe | `dnd/core/gridmap.py:2443-2499` |
| batch physical-edge staging | `dnd/core/gridmap.py:2524-2559` |
| cold-rebuild physical-edge staging and error | `dnd/core/gridmap.py:2750-2794` |
| public wrong-geometry tests | `tests/engine/test_tile_surface_contract.py:366-400,620-665` |
| deprecated reciprocal wording in non-scope server projection/diagnostics | `deprecated/server_deprecated/world_projection.py:577-603`; `deprecated/server_deprecated/subjective_parity_diagnostics.py:204,406,526-544`; these are not Phase 1/2 correction callers |

### Boundary orientation and placement work diagnostics

| Current behavior | Exact locations |
| --- | --- |
| implicit `orientation = boundary_direction` | `dnd/core/gridmap.py:2391-2395` |
| boundary omitted-orientation public caller | `tests/engine/test_tile_surface_contract.py:394-397` |
| explicit side/orientation and orient-in-place coverage | `tests/engine/test_tile_surface_contract.py:410-453` |
| local work-count implementation, currently counting a live neighbor | `dnd/core/gridmap.py:2339-2360` |
| diagnostics value and lifecycle | `dnd/core/gridmap.py:83-89,2287-2309` |
| diagnostics command owners | `dnd/core/gridmap.py:2685-3015,3061-3173,3231-3496` |
| diagnostics public assertions | `tests/engine/test_tile_surface_contract.py:269-270,684,731,999,1118-1141` |

`get_world_edge` currently starts no diagnostics row. The flattened edge helper
starts and finishes `get_boundary_objects_on_edge` diagnostics at
`dnd/core/gridmap.py:3131-3152`; placement admission/rebuild and exact local
queries use the same `GridMapOperationDiagnostics` lifecycle listed above.
The only public diagnostics readers in this scope are the eight assertions in
`tests/engine/test_tile_surface_contract.py:269-270,684,731,999,1118-1141`.

## Exact intended correction implementation ledger

No Phase 1 or Phase 2 correction edit is authorized at this checkpoint. On
coordinator approval, the intended file/caller/test scope is exactly:

| Slice | Production files and bounded symbols | Tests/callers |
| --- | --- | --- |
| Phase 1 ordered cold view | `dnd/core/world_edges.py::WorldEdgeStructuralContribution, WorldEdgeView`; `dnd/core/gridmap.py::get_world_edge, _resolve_object_placement, get_boundary_objects_on_edge` | `tests/engine/test_world_edge_identity_and_elevation.py`; `tests/engine/test_elevation_proving_battlefield.py`; `tests/engine/test_tile_surface_contract.py`; exact placement/bootstrap identity coverage in `tests/engine/test_direct_scenario_deployment.py` and `tests/engine/test_event_wire_visibility_contract.py` |
| Phase 2 local geometry admission/rebuild | `dnd/core/gridmap.py::_placement_work_counts, _validate_placement_collision, validate_object_placement_batch, rebuild_object_placements`; preserve the existing `dnd/entities/entity.py` batch caller unchanged | `tests/engine/test_tile_surface_contract.py` placement, event, rebuild, locality, and rollback cases; `tests/engine/test_world_edge_identity_and_elevation.py` and `tests/engine/test_elevation_proving_battlefield.py` ordered-view cases; existing focused placement/item/equipment/light/spatial lanes as non-regression gates |

No other production or test file is proposed. In particular, this ledger does
not authorize Entity occupancy work, Phase 3 consumers, movement/FOV/light/
propagation migration, EventQueue/schema changes, new indexes/caches/facades,
or edits to the master, correction, unified, revoked-guidance, accepted
manifest, or this ledger's governing inputs.

## Phase 0 handoff

Hashes, manifest members, collection identity/signatures, accepted focused
results, caller inventory, and the current public migration trace are frozen.
There is no contradiction with the approved correction plan. Await explicit
`GO PHASE1` before any production or test edit.

## Phase 1 checkpoint — ordered cold view complete

Status: **PHASE 1 COMPLETE; PHASE 2 NOT STARTED.** The accepted Phase 0
checkpoint was `a54b7c8fe996393f6f83aa5f84ddd36513e0f172492eff84677119e76cfba4ed`.

### Exact changed files

Authorized production changes:

- `dnd/core/world_edges.py` — replaced the merged contribution/view fields
  with exact vertical intervals and ordered source/destination exit/entry
  layers while retaining frozen slotted dataclasses and canonical
  `AdjacentEdgeKey` identity;
- `dnd/core/gridmap.py` — made `get_world_edge` caller-ordered and
  side-specific, retained empty-channel providers, used committed placement
  intervals, removed the flattened `get_boundary_objects_on_edge` helper, and
  stopped orientation defaulting/inferred rebuild rejection; and

direct collecting public-test ports:

- `tests/engine/test_world_edge_identity_and_elevation.py`;
- `tests/engine/test_elevation_proving_battlefield.py`; and
- `tests/engine/test_tile_surface_contract.py`.

The current implementation manifest was regenerated as the governance artifact
`DND_TILE_WORLD_ITEM_PHASES_0_1_2_IMPLEMENTATION_MANIFEST_2026-08-23.json`.
The correction ledger was the only other file edited by this task. Existing
dirty production, test, plan, and unified-document changes were preserved.

### Public behavior now covered

- forward and reverse views share one canonical key but swap endpoint facts,
  exit/entry directions, contribution layers, and the sign of elevation delta;
- boundary providers are read only from the exact owner-Tile facing side;
  off-side providers do not leak into either layer;
- contribution rows carry exact provider UUID, base/top height, deterministic
  UUID order, and empty blocked-channel tuples when the provider remains
  present but currently open;
- retained center legacy directional providers and intrinsic Tile blockers use
  their correct layer and intervals;
- boundary placement with omitted orientation commits `None` and cold rebuild
  round-trips that value; and
- no active Python caller retains old `WorldEdgeView` fields,
  `structural_contributions`, or `get_boundary_objects_on_edge`.

The static residue search found only the legitimate unrelated progressive
elevation function parameters `first_height_steps`/`second_height_steps` and
similar names at `dnd/core/world_edges.py:108-125`; plan/ledger history text is
also retained. No old view/helper API use remains in active Python.

### Validation

| Check | Result |
| --- | --- |
| Direct affected public modules | 62 passed in 9.78s |
| Architecture lane (`tests/architecture`) | 42 passed in 23.51s |
| Edited production compile | `./.venv/bin/python -m py_compile dnd/core/world_edges.py dnd/core/gridmap.py` passed |
| Exact old-view/helper residue search | no active API residue; legitimate elevation parameters/history classified above |
| `git diff --check` | passed; existing LF/CRLF conversion warnings only |

The existing wrong opposing-side collision behavior remains intentionally
unchanged, including `staged_physical_edge_occupants`, neighbor probing,
opposite-edge rebuild rejection, and neighbor-inclusive placement work counts.
Those are Phase 2 corrections and were not edited or validated as completed by
this checkpoint.

### Current implementation manifest

```text
path=DND_TILE_WORLD_ITEM_PHASES_0_1_2_IMPLEMENTATION_MANIFEST_2026-08-23.json
plan_sha256=ae189282687fdcb7baa88ca3b393af593c6db345029a89da9cfcc36b76f021c1
member_count=90
member_set_match=True
member_hash_mismatches=[]
manifest_sha256=9758f6dd2767bdb1a36f0fe9aa901689b015fad8353969f365d1fb22ee7aed33
```

Phase 1 is stopped here. Remaining Phase 2 work is the local-only admission
and cold-rebuild geometry correction, including deletion of reciprocal
opposite-side collision/staging machinery and its Phase 2 behavioral tests.
Await explicit `GO PHASE2`.

## Phase 2 final correction checkpoint — local admission and rebuild complete

Status: **PHASE 2 COMPLETE; PHASE 3 NOT STARTED.** The implementation began
from the accepted Phase-1 manifest
`9758f6dd2767bdb1a36f0fe9aa901689b015fad8353969f365d1fb22ee7aed33` with 90
members and the accepted Phase-1 ledger SHA
`e93947d9a83d1bdb1b84620cc666ffe7b4150e86459219ca41e23c7f8c10da17`.

### Exact files and node changes

Phase-2 production scope was exactly:

- `dnd/core/gridmap.py` — `_placement_work_counts` now counts distinct owner
  Tiles and distinct exact local band keys; `_validate_placement_collision`
  retains only local live/staged occupant checks; the physical-edge staging
  parameter, batch map, adjacent lookup, opposite-side probe, and rebuild
  physical-edge staging/error are deleted; `get_world_edge` records one
  existing diagnostics snapshot for exactly its two endpoint Tiles, facing
  bands, and visited center/facing providers; and the unused positional
  neighbor helper is deleted while `_opposite_direction` remains a live
  ordered entry-direction derivation.

Direct public-test ports and proofs:

- `tests/engine/test_tile_surface_contract.py` — opposing boundary occupants
  succeed independently; a nonoccupying attachment coexists; same-side
  collision remains atomic with no success fact; placement iteration preserves
  exact owner-side rows; orient/move/remove of A leaves B's placement,
  membership, and completed facts unchanged; rebuild accepts opposing sides
  and rejects same-side collisions.
- `tests/engine/test_world_edge_identity_and_elevation.py` — ordered query
  diagnostics remain fixed after adding a distant provider; old reciprocal
  wording was removed from the renamed public node.
- `tests/engine/test_elevation_proving_battlefield.py` — the renamed ordered
  edge public node retains the existing door-state proof.

No new production type, edge key/map, cache, index, DTO, facade, serializer,
event schema, reducer, EventQueue phase, or Phase-3 consumer was added. The
existing equipment batch signature and caller remain unchanged.

The exact selector delta against the captured Phase-0 node set
`/tmp/tmp.KVeUPOdFN8/nodes` is:

Removed/renamed old selectors:

- `tests/engine/test_world_edge_identity_and_elevation.py::test_world_edge_is_one_reciprocal_objective_structural_fact`;
- `tests/engine/test_tile_surface_contract.py::test_boundary_bands_are_edge_queries_and_reciprocal_collisions`;
- `tests/engine/test_elevation_proving_battlefield.py::test_elevation_proving_battlefield_exercises_reciprocal_edge_rules`.

Their renamed replacements are:

- `tests/engine/test_world_edge_identity_and_elevation.py::test_world_edge_is_ordered_and_reverses_endpoint_layers`;
- `tests/engine/test_tile_surface_contract.py::test_boundary_bands_are_exact_side_queries_and_independent_collisions`;
- `tests/engine/test_elevation_proving_battlefield.py::test_elevation_proving_battlefield_exercises_ordered_edge_rules`.

Genuinely added selectors are:

- Phase 1: `tests/engine/test_world_edge_identity_and_elevation.py::test_world_edge_uses_exact_facing_side_intervals_and_uuid_order`;
- Phase 1: `tests/engine/test_world_edge_identity_and_elevation.py::test_symmetric_boundary_without_orientation_round_trips_through_rebuild`;
- Phase 2: `tests/engine/test_tile_surface_contract.py::test_boundary_placement_diagnostics_count_only_owner_and_local_bands`;
- Phase 2: `tests/engine/test_tile_surface_contract.py::test_world_initialized_round_trip_rebuilds_opposing_boundary_placements`.

The net is exactly `1,314 - 3 + 7 = 1,318` selectors. The Phase-2
§7.1(4) mutation-isolation proof extends the renamed boundary node and adds
no generalized batch API.

### Validation commands and results

| Check | Result |
| --- | --- |
| Direct Tile/world-edge/elevation modules | 64 passed in 10.23s |
| Accepted 14-module capability lane | 282 passed in 54.22s |
| Spell-family lane | 62 passed in 23.09s |
| Architecture lane | 42 passed in 20.96s |
| Runnable placement/item/light/spatial subset | 145 passed in 30.68s |
| Edited production `py_compile` | passed for `dnd/core/gridmap.py` and `dnd/core/world_edges.py` |
| `git diff --check` | passed; existing LF/CRLF conversion warnings only |

The explicitly attempted equipment-replication focused module remains blocked
by the accepted pre-existing `ModuleNotFoundError: No module named
'dnd.content_system'` class; it was not changed or masked.

### Full collection comparison

Command: `./.venv/bin/pytest --collect-only -q -p no:cacheprovider`

- exit code: 2 because of the accepted pre-existing collection blockers;
- current collected nodes: 1,318;
- current sorted newline-joined node SHA-256:
  `d5a34d1de6683d8145a4895233f0348249a1e7d7d89fd8478c976c6edc5b404c`;
- exact Phase-0 baseline: 1,314 nodes,
  `1a62a543af12b8178a4881d0815e70ad533d7263e833108caab11d7f9447dfb6`;
- current modules with collected nodes: 113,
  `8a609e8b85157ad9c1db2e085c4f3ca82a6bcb9e4abc84ee4e278da4912873bb`;
- current blocked modules: 105,
  `ff2ebd76d5772a93dff7723f9869316eb92fe05b10d7b916a6465005ef6bf531`;
- current complete module union: 218,
  `003720b0a00ac1ab53af1aabdebaeaf10b324b7e7a7e92b0d25e1e702e6ef7a6`;
- normalized blocked signatures, unchanged from Phase 0:
  `dnd.content_system` 57; `server` 15;
  `dnd.classes.barbarian_progression_definitions` 6;
  `dnd.classes.progression_definitions` 4;
  `dnd.classes.sorcerer_progression_definitions` 3;
  `dnd.core.content.runtime` 3; `dnd.monsters.bestiary_content` 3;
  `dnd.monsters.circus_fighter` 3; `devtools` 1;
  `dnd.core.content.registry` 1; `dnd.scenarios.encounter_catalog` 1;
  missing visual-ledger file 4; `EquippedVisualPolicy` import 2; and
  `OriginCapability` import 2.

The successful-module, blocked-module, and complete-union path sets are
identical to Phase 0. The selector delta above is the complete authorized
change; no collecting module was removed or added, no blocked module was
removed or masked, and no normalized collection error signature changed.

### Static deletion gates

Repository searches over active `dnd`, `tests`, and deprecated Python found
zero occurrences of `staged_physical_edge_occupants`, `opposite-edge
collision`, `reciprocal boundary`, `get_boundary_objects_on_edge`,
`structural_contributions`, or implicit `orientation=boundary_direction`.
The remaining generic `first_*`/`second_*` matches are the unrelated
progressive-elevation helper parameters in `dnd/core/world_edges.py:108-125`
and ordinary scenario/elevation coordinate variables. Deprecated/manual
reciprocal parity terminology is historical and does not call the active
GridMap authority.

### Final implementation manifest

The final scoped manifest contains every modified or untracked Python/JSON
member, sorted lexicographically. Its algorithm is explicit in the manifest:
each member hash is SHA-256 of exact raw bytes; the member set is the sorted
`git status` `.py`/`.json` set excluding the manifest and Markdown governance
files.

```text
path=DND_TILE_WORLD_ITEM_PHASES_0_1_2_IMPLEMENTATION_MANIFEST_2026-08-23.json
plan_sha256=ae189282687fdcb7baa88ca3b393af593c6db345029a89da9cfcc36b76f021c1
member_count=90
declared_member_count=90
member_set_match=True
hash_mismatches=[]
manifest_sha256=c5d467881b82261b0a36ae00842d19bfd0af1b3c7079bed2a45fe925ca86b4cf
```

All opposing-side admission/rebuild behavior, exact local diagnostics, event
and rollback preservation, and the retained current hints are complete for
this correction slice. Aggregate Phase-3 mechanics/contact/revision/light
migration remains deferred. Stop here for supervisor implementation review;
do not mark the global master or Phase 3 complete.

## Supervised correctness-review continuation — 2026-08-24

The requested review gates were added without production changes. The only
review code edit is
`tests/engine/test_tile_surface_contract.py`; the governance edits are
this continuation, the two historical notices in the implementation plan and
pre-correction ledger, and the regenerated scoped manifest. No GridMap,
WorldEdge, event schema, reducer, EventQueue, or Phase-3 code changed.

The existing renamed independence selector now uses a dedicated two-band
structural boundary provider. Its public proof covers A at I:EAST [0,2) and B
at J:WEST [0,2), exact height-0/height-1 side memberships, exact placement
rows and completed placement facts, ordered forward/reverse exit and entry
layers, a base-1 same-side collision with zero mutation and zero success fact,
nonoccupying attachment coexistence, and orient/move/remove isolation of A
from B. The serialized WorldInitialized rebuild proof remains public and
semantic-item based. The serialized rebuild test now also proves zero events
for a successful cold rebuild, captures public placement rows, both exact side
memberships, movement/optical/propagation revisions, resolved light levels
under an active source, and the EventQueue cursor before a same-side staged
collision; rejection preserves all captures, emits no events, and reports
zero replacements before public light cleanup.

### Review validation

| Check | Result |
| --- | --- |
| Direct Tile/world-edge/elevation modules | 64 passed in 10.60s |
| Tile contract module after review additions | 32 passed in 6.50s |
| Accepted 14-module capability lane | 282 passed in 57.05s |
| Spell-family lane | 62 passed in 23.66s |
| Architecture lane | 42 passed in 23.29s |
| Edited-module py_compile | passed |
| Static deletion gates | zero active matches for staged physical-edge occupants, opposite-side probing/collision, old boundary collector, old structural contribution helper, or implicit boundary orientation |
| `git diff --check` | passed; existing LF/CRLF conversion warnings only |

### Final collection and selector delta

The final cache-disabled collection rerun exited 2 with the same accepted
pre-existing collection blockers:

- 1,318 nodes; sorted node SHA-256
  `d5a34d1de6683d8145a4895233f0348249a1e7d7d89fd8478c976c6edc5b404c`;
- 113 successful modules; SHA-256
  `8a609e8b85157ad9c1db2e085c4f3ca82a6bcb9e4abc84ee4e278da4912873bb`;
- 105 blocked modules; SHA-256
  `ff2ebd76d5772a93dff7723f9869316eb92fe05b10d7b916a6465005ef6bf531`;
- 218-module union; SHA-256
  `003720b0a00ac1ab53af1aabdebaeaf10b324b7e7a7e92b0d25e1e702e6ef7a6`.

Compared with the frozen Phase-0 set, the exact selector delta is unchanged:

- removed/renamed:
  `test_world_edge_is_one_reciprocal_objective_structural_fact`,
  `test_boundary_bands_are_edge_queries_and_reciprocal_collisions`, and
  `test_elevation_proving_battlefield_exercises_reciprocal_edge_rules`;
- renamed replacements:
  `test_world_edge_is_ordered_and_reverses_endpoint_layers`,
  `test_boundary_bands_are_exact_side_queries_and_independent_collisions`, and
  `test_elevation_proving_battlefield_exercises_ordered_edge_rules`;
- genuinely added Phase-1/2 selectors:
  `test_world_edge_uses_exact_facing_side_intervals_and_uuid_order`,
  `test_symmetric_boundary_without_orientation_round_trips_through_rebuild`,
  `test_boundary_placement_diagnostics_count_only_owner_and_local_bands`,
  and `test_world_initialized_round_trip_rebuilds_opposing_boundary_placements`.

Thus the exact reconciliation remains `1,314 - 3 + 7 = 1,318`; extending
the existing independence and serialized-rebuild selectors added no nodes.

### Reviewed implementation manifest

The scoped manifest was regenerated after the review tests and verified with
90 members, exact member-set equality, and zero hash mismatches:

`DND_TILE_WORLD_ITEM_PHASES_0_1_2_IMPLEMENTATION_MANIFEST_2026-08-23.json`
`member_count=90`
`manifest_sha256=3eb3b75864cda77052675e93b82f43bdf89c5177930a4fa4518db3884900d98c`

The two requested historical correction notices point to this reviewed
manifest and state that Phase 3 must use the corrected side-geometry state.
This continuation does not mark the global master or Phase 3 complete.
