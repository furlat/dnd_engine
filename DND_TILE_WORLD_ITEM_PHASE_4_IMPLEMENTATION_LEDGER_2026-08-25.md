# Phase 4 Entity Occupancy — implementation-start ledger

Status: `PHASE_4_0_PREFLIGHT_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

This is the Phase 4.0 implementation-start checkpoint required by the approved
plan. No production or test file was edited in Phase 4.0. The existing dirty
work and the accepted Phase 3 artifacts were preserved. Phase 4.1 and 4.2 were
not started.

## Governing inputs and accepted handoff

The following raw-byte SHA-256 values were verified before the preflight:

| input | SHA-256 |
|---|---|
| `DND_TILE_WORLD_ITEM_PHASE_4_ENTITY_OCCUPANCY_IMPLEMENTATION_PLAN_2026-08-25.md` | `00c31222bbfeb531cf6817c7e3c159c3eace85580796b49df564cc4b8d0e28f8` |
| `DND_TILE_WORLD_ITEM_PHASE_3_COMPLETION_LEDGER_2026-08-25.md` | `086e09c9f1329563e846dac0fd10b46331e456dfa2c83786e5de48cb96e113cb` |
| `DND_TILE_WORLD_ITEM_VERTICAL_BOUNDARY_MIGRATION_PLAN_2026-08-17.md` | `50411e5575e6336ca0301acf032797cdf1d5ea885df5ccd37d6619f593e7a193` |
| `DND_TILE_WORLD_ITEM_ACTIVE_RUNTIME_SCOPE_AMENDMENT_2026-08-24.md` | `f10e2fbbcb6ba8732d078f0c4f2f5276716eb51e32c083068f3cae93c9ba52d6` |
| `DND_TILE_WORLD_ITEM_PHASE_3_IMPLEMENTATION_MANIFEST_2026-08-25.json` | `08c756ee62b953dd7326de9d5d06345eb3b948743b5d328559da8df6b40027f0` |

The accepted Phase 3 manifest parsed as JSON with 59 members: 33 production
and 26 test members. Every member was hashed from current raw bytes; the
member mismatch count was `0`.

Required instruction files were read completely: `agents.md` (4 lines) and
`HOW_TO_TEST.MD` (517 lines). The entire Phase 4 plan (993 lines), accepted
Phase 3 ledger (174 lines), master plan (1492 lines), and active-runtime
amendment (130 lines) were also read before the caller inventory.

## Frozen active baseline

The accepted active in-process command was rerun with
`./.venv/bin/pytest -q -p no:cacheprovider` over this exact path set:

```text
tests/engine/test_tile_surface_contract.py
tests/engine/test_world_edge_identity_and_elevation.py
tests/engine/test_senses_light_stealth.py
tests/engine/test_grid_pathfinding.py
tests/engine/test_action_discovery.py
tests/engine/test_elevation_proving_battlefield.py
tests/engine/test_elevation_performance_contract.py
tests/engine/test_spatial_effects.py
tests/engine/test_direct_spatial_effect_materialization.py
tests/engine/test_condition_lifecycle.py
tests/engine/test_event_lifecycle.py
tests/engine/test_event_wire_visibility_contract.py
tests/engine/test_objective_state.py
tests/engine/test_direct_scenario_deployment.py
tests/engine/test_items_inventory_equipment.py
tests/engine/test_spell_families.py
tests/engine/test_move_settlement.py
tests/engine/test_action_cost_and_position_commit.py
tests/engine/test_traversal_connectors.py
tests/engine/test_elevated_jump_transaction.py
tests/engine/test_runtime_reset.py
tests/engine/test_manual_11_grid_tiles_terrain_movement.py
tests/architecture
tests/manual/test_08_world_model_and_movement.py
tests/manual/test_37_authored_encounter_mechanics.py
tests/manual/test_72_battlefield_deployment_catalog.py
tests/manual/test_17_encounters_turns_controllers.py::test_turn_start_full_senses_refresh_emits_seen_cell_delta
```

Result: `614 passed in 189.68s (0:03:09)`.

The exact collect-only path set above was rerun with
`./.venv/bin/python -m pytest --collect-only -q -p no:cacheprovider`.
Collection exited `0`, reported `614 tests collected in 10.29s`, and the
sorted unique normalized node-set SHA-256 was
`774c745d442d5db6b8bfb2878309b4eae118e08d264ae4a12370f2a21db05641`.

No additional broad suite was run in this preflight. The relevant Phase 4
characterization selectors were identified below and are intentionally not
run until the authorized implementation checkpoint.

## Caller search and classification

The inventory was made with fixed-string searches over active production
Python (`dnd/`) and collecting tests, followed by classification against the
active-runtime amendment. Line numbers below are the current evidence lines;
they are not source-layout assertions for gameplay tests.

### Deleted Entity index: `Entity._entity_by_position`

Active production definition and writers/readers:

- `dnd/entities/entity.py:520` defines the class index.
- `dnd/entities/entity.py:627` appends during `_attach_to_world`.
- `dnd/entities/entity.py:635,639,650,654` removes/rolls back attach and detach.
- `dnd/entities/entity.py:677,678,681,682,686,688,690` reads, writes, and
  rolls back `update_entity_position`.
- `dnd/entities/entity.py:737,742` cleans up unpublished runtime state.
- `dnd/entities/entity.py:769` implements `get_all_entities_at_position` by
  reading the index.

These are active Phase 4.1 production callers and are in the deletion/reader
migration envelope. `dnd/entities/entity.py:708` is a separate
`Entity.register_entity` identity-registry operation, not an occupancy writer;
it is a governed retained identity operation and must not be confused with
the GridMap mutator.

Collecting-test matches are test migrations, not compatibility requirements:

- reset/seed/assert matches: `tests/engine/test_runtime_reset.py:29,53`,
  `tests/engine/test_runtime_identity_registries.py:32`,
  `tests/engine/test_dice_event_semantics.py:101`,
  `tests/engine/test_manual_09_conditions.py:33`,
  `tests/engine/test_manual_07_entity_composition.py:27`,
  `tests/engine/test_manual_10_standard_conditions.py:51`,
  `tests/manual/test_11_equipment_inventory_and_items.py:76`,
  `tests/manual/test_02_entity_anatomy.py:31`,
  `dnd/runtime_reset.py:55`,
  `tests/manual/test_01_runtime_identity_and_registries.py:33`,
  `tests/manual/test_103_game_summary_store.py:54`,
  `tests/manual/test_10_combat_resolution.py:57`,
  `tests/manual/test_09_action_discovery_and_costs.py:75`,
  `tests/manual/test_13_spellcasting_core.py:380`,
  `tests/manual/test_14_spell_families.py:83`,
  `tests/manual/test_21_spell_and_feature_extensions.py:44`,
  `tests/manual/test_17_encounters_turns_controllers.py:91`, and
  `tests/manual/test_20_content_extension_basics.py:57`.
- active Banishment test assertions: `tests/manual/test_133_new_spells_batch4_legacy_contract.py:369,370,624,632,679`.
  Although the filename says legacy contract, this file imports active spell
  implementations and is in the maintained in-process lane; it is a Phase
  4.2 test migration.
- `tests/manual/test_18_sessions_api_client_contract.py:90` is an excluded
  transport/API test reset and remains excluded; it is not ported for
  compatibility.

### Deleted GridMap dictionaries

`GridMap._entity_positions` has one active production definition and all
current reads/writes in `dnd/core/gridmap.py`:

- definition `:118`;
- register write/read `:2090,2100`;
- unregister removal `:2112`;
- stage/move read/write and rollback `:2151,2160,2168,2170`;
- publication validation read `:2188`;
- public position read `:2210`;
- reset `:4757`.

`dnd/spells/abjuration.py:1391,1427` directly pops/restores this dictionary
for Banishment. This is an active Phase 4.2 migration target, not an
excluded legacy compatibility caller.

`GridMap._entities_by_position` has the active production matches:

- definition `dnd/core/gridmap.py:117`;
- tile-replacement protection `:364`;
- local collision/blocker reads `:1437,1978`;
- register writes `:2092,2101`;
- unregister/remove `:2114-2118`;
- stage/move writes and rollback `:2159-2171`;
- public `get_entities_at` implementation `:2214`;
- clear rejection/reset `:4738,4756`.

`dnd/spells/abjuration.py:1392,1393,1428-1430` directly removes/restores
this dictionary for Banishment. It is the same active Phase 4.2 migration
target. There is no second active production occupancy registry in the
inventory.

### Receipt and five public GridMap mutators

`GridEntityPositionReceipt` occurs only in
`dnd/core/gridmap.py:66` (definition), `:2149` (stage return annotation),
`:2175` (construction), and `:2183` (publisher argument). There is no
external production or test construction/call; it is deleted as part of the
single private commit/publish boundary.

The five public GridMap mutators are defined only in
`dnd/core/gridmap.py`:

| symbol | definition | active callers |
|---|---:|---|
| `register_entity` | 2087 | `dnd/entities/entity.py:632`; `tests/manual/test_08_world_model_and_movement.py:221,305`; direct test migration |
| `unregister_entity` | 2110 | `dnd/entities/entity.py:649,736`; production lifecycle migration |
| `move_entity` | 2123 | `dnd/entities/entity.py:684`; `tests/manual/test_08_world_model_and_movement.py:236,318`; `tests/manual/test_128_antimagic_field.py:192,195,230,393`; active test migration |
| `stage_entity_position` | 2145 | `dnd/entities/entity.py:684`; `dnd/core/gridmap.py:2136` (the public `move_entity` implementation) |
| `publish_staged_entity_position` | 2181 | `dnd/entities/entity.py:698`; `dnd/core/gridmap.py:2138` (the public `move_entity` implementation) |

No other active production caller was found beyond these listed internal
`GridMap.move_entity` calls. The `Entity.register_entity` identity-registry
classmethod at `dnd/entities/entity.py:708` is unrelated and retained.
`tests/manual/test_18_sessions_api_client_contract.py` is excluded
transport/API scope, while `test_128_antimagic_field.py` is an active
in-process maintained test and must migrate.

The complete fixed-string deletion-gate inventory was rerun before this
correction. Current live matches are exactly the definitions, reads, writes,
rollbacks, reset paths, Banishment writes, active test migrations, and the two
`GridMap.move_entity` internal calls enumerated in this section and the
preceding index sections. No additional active production caller was found.
The post-Phase-4 hard-cut gate remains zero active definitions/imports/calls
for all five deleted symbols and zero active direct calls of the five public
mutators; the excluded transport/API reset in
`tests/manual/test_18_sessions_api_client_contract.py:90` is classified
residue, not a compatibility requirement.

### `Entity.get_all_entities_at_position`

The definition is `dnd/entities/entity.py:760`. Its two production readers
are `dnd/entities/entity.py:912` (`can_end_movement_at`) and `:952`
(`is_obscured_by_larger_creature_from`). Both are active Phase 4.1 bounded
Tile-query migrations.

Collecting readers are active test migrations at:

- `tests/engine/test_action_cost_and_position_commit.py:247`;
- `tests/engine/test_entity_composition.py:159`;
- `tests/engine/test_manual_11_grid_tiles_terrain_movement.py:164,165`;
- `tests/engine/test_manual_07_entity_composition.py:94,171,172`;
- `tests/engine/test_runtime_identity_registries.py:102,108,109`; and
- `tests/manual/test_01_runtime_identity_and_registries.py:216,232,241,242,257,258`.

They move to the public GridMap query boundary. No compatibility alias is
planned.

### Game ownership, deployment, detach, and unpublished discard

- `dnd/game.py:15` deploys by calling `entity._attach_to_world`, then records
  the committed entity in `self.entities`.
- `dnd/game.py:31` removes the Game-owned entity before calling
  `_detach_from_world`; `close` uses the same path.
- `dnd/entities/entity.py:619,644,716` are attach, detach, and unpublished
  discard lifecycle paths.
- `dnd/content/scenarios/scenario_deployment.py:425` calls Game deployment.
- `dnd/entities/entity_creation.py:426,450`,
  `dnd/entities/entity_progression.py:424`,
  `dnd/content/monsters/monster_builders.py:716`, and
  `dnd/content/characters/character_builds.py:110` are deployment-state or
  failed-creation callers of those lifecycle seams.
- `dnd/entities/entity.py:4478` iterates the identity registry only for
  `is_deployed` navigation materialization; it is a retained explicitly
  deployed-filtered lifecycle traversal, not an occupancy index.
- `dnd/encounters/encounter.py:866,882` performs controller grouping and is
  unrelated identity ownership text.

The Phase 4.1 mutation is bounded to Entity/GridMap/Game ownership ordering
and these existing lifecycle seams; no new owner/index/controller is needed.

### Observer registration and subscriptions

Observer state and registration are in `dnd/blocks/sensory.py`:

- maps and reset: `:497-498,512-513`;
- `register_observer`: `:518-521`, storing senses and currently refreshing;
- `unregister_observer`: `:523-528`, removing footprint and calling
  `get_map().unsubscribe_entity`;
- footprint refresh/read paths: `:557,561,633,918,928+`.

Entity lifecycle callers are `dnd/entities/entity.py:630,634,648,735`; the
registration rollback and detach/discard paths are active lifecycle work.
Grid subscriptions are `dnd/core/gridmap.py:255,264-272` (subscribe),
`:274,276-278` (unsubscribe), `:280` (query), and `:2119` (unregister
cleanup). Registration becomes registration-only in Phase 4.2; ENTERED remains
the initial/restore reduction as required by the plan.

### Carried/attached lights and suppression tokens

The existing light seams are retained and are Phase 4.2 lifecycle targets:

- `dnd/core/gridmap.py:93` stores `LightSourceData.anchor_uuid`;
  `:137` stores `_block_light_suppressions`.
- `:4156-4195` adds an anchored source and installs existing callbacks;
  `:4197-4222` removes/cleans sources;
  `:4224-4232` computes effective activity;
  `:4234-4269` applies composable suppression tokens;
  `:4271-4313` moves a source;
  `:4437-4465` performs the existing pre-completion attached-light move for
  `SPATIAL_ENTITY_ENTERED` and `SPATIAL_OBJECT_PLACED`.
- `dnd/core/gridmap.py:2120` currently removes a suppression map entry during
  unregister; this is the blind cleanup path bounded by the Phase 4.2 token
  migration.
- `dnd/entities/entity.py:521,1334,1368` owns the existing life-state
  suppression token and death/revival reconciliation.
- `dnd/items/torches.py:343-351,370` covers portable Torch carrier light;
  `:697-707,724,735` covers WallTorch light, put-out, and terminal hook.
- `dnd/spells/evocation.py:3662,3679` owns entity-anchored LightEffect;
  `:3785,3796,3820,3843-3876` owns Continual Flame relocation/removal.
- `dnd/blocks/base_item.py:348` destroys with the existing parent-event
  cleanup seam; `dnd/core/base_block.py:457-466` manages attached UUIDs.

### Exact predeclared characterization selectors

These are the exact public selectors predeclared before implementation. The
six required classes are explicit; no unrelated selector is being counted as
coverage.

1. Publication-failure commitment:
   `tests/engine/test_action_cost_and_position_commit.py::test_spatial_publication_failure_keeps_committed_objective_position_and_raises`
2. Per-step movement settlement:
   `tests/engine/test_senses_light_stealth.py::test_each_move_step_emits_objective_and_subjective_facts_before_step_completion`
3. Initial deployment reduction:
   `tests/engine/test_senses_light_stealth.py::test_supported_deployment_emits_one_empty_to_full_delta`
4. Banishment:
   `tests/engine/test_condition_transform_ownership.py::test_banishment_owns_denial_and_restores_spatial_registration`;
   `tests/manual/test_133_new_spells_batch4_legacy_contract.py::test_banishment_removes_and_restores_spatial_perception`;
   `tests/manual/test_133_new_spells_batch4_legacy_contract.py::test_banishment_return_displaces_an_occupant`;
   `tests/manual/test_133_new_spells_batch4_legacy_contract.py::test_banishment_successful_save_preserves_spatial_state`.
5. Entity-anchored conditions:
   `tests/engine/test_spatial_effects.py::test_authored_anchor_policy_materializes_exact_runtime_identity`;
   `tests/engine/test_spell_families.py::test_eb_15_021_zone_spell_family_entry_turn_start_and_cleanup_edges`.
   No current public selector proves an entity anchor leaving the world and
   restoring from an empty footprint. Predeclare the later public node
   `tests/engine/test_spatial_effects.py::test_entity_anchor_presence_leave_and_restore_reconciles_footprint`
   for that missing Phase 4.2 proof; it is not added in Phase 4.0.
6. Attached/carried light and suppression:
   `tests/engine/test_senses_light_stealth.py::test_attached_light_moves_and_reduces_observers_once_per_step`;
   `tests/engine/test_items_inventory_equipment.py::test_wall_torch_attached_light_follows_move_and_terminal_removal`;
   `tests/engine/test_spell_families.py::test_continual_flame_relocates_and_cleans_up_with_its_anchor`;
   `tests/engine/test_life_state_ownership.py::test_death_suppresses_lights_reversibly_and_preserves_other_owners`;
   `tests/engine/test_life_state_ownership.py::test_light_desired_state_and_nonblocking_survive_death_and_revival`;
   `tests/engine/test_life_state_ownership.py::test_revival_reintroduces_entity_to_incremental_senses`.

### Entity-anchored SpatialCondition footprints

`dnd/spatial/area_conditions.py` owns the relevant fields and handlers:

- anchor fields and validation: `:82,88-89,135-142`;
- `_install_anchor_handler`: `:1024`;
- entity event matching/relocation: `:1049-1057` (currently ENTERED-only);
- relocation interface and area implementation: `:1093,1838,1935-1942`;
- footprint transition: `:889+`;
- object placement handling in the same processor uses typed placement and
  previous-placement semantics and is retained.

`dnd/spatial/transitions.py:30-70` contains generic transition-footprint
handlers. The plan’s Phase 4.2 change is narrowly the entity LEFT/restore-from-
empty lifecycle; it does not redesign object anchors.

Public characterization selectors identified:

- `tests/engine/test_spatial_effects.py` anchor cases at `:219-242,1479,1495,1542`;
- `tests/manual/test_128_antimagic_field.py:92-97,236,397`;
- `tests/engine/test_spell_families.py:2400-2401` and related Entity-anchor
  selectors.

### Banishment

`dnd/spells/abjuration.py:1358-1428` is the only active production path that
directly writes all three old occupancy indexes. It saves the original
position (`:1375`), removes indexes and manually emits LEFT during `_apply`
(`:1391-1403`), then restores indexes and manually emits ENTERED during
`_remove` (`:1409-1428`). `:1415` already uses the public GridMap query for
return displacement. This is the explicit Phase 4.2 migration target; it is
not a contradiction or excluded residue.

Active characterization/test migrations are:

- `tests/engine/test_condition_transform_ownership.py::test_banishment_owns_denial_and_restores_spatial_registration`;
- `tests/manual/test_133_new_spells_batch4_legacy_contract.py::test_banishment_removes_and_restores_spatial_perception`;
- `tests/manual/test_133_new_spells_batch4_legacy_contract.py::test_banishment_return_displaces_an_occupant`; and
- `tests/manual/test_133_new_spells_batch4_legacy_contract.py::test_banishment_successful_save_preserves_spatial_state`.

The private-index assertions in those active tests are migration targets, not
retained contracts. No Banishment compatibility write is authorized.

### Identity-wide spatial scans, adjacency, and Pack Tactics

The two unbounded spatial-rule scans are explicit planned Phase 4.2 callers:

- `dnd/monsters/traits.py:341` `pack_tactics_advantage` scans all identities
  before the ally/distance rule;
- `dnd/monsters/traits.py:1775-1785` `_has_adjacent_ally` scans all identities
  for adjacency.

Both must become bounded Tile plus eight-neighbor reads in Phase 4.2.

`dnd/entities/entity.py:4475-4480` is an explicitly deployed-filtered
navigation materialization traversal and is retained. Other
`Entity.get_all_entities()` matches are identity/preview/controller reads,
not spatial occupancy rules; they are retained or excluded according to their
module boundary and are not ported as a compatibility measure.

The existing public local query readers remain governed retained reads, not
old-index matches. Representative production locations include
`dnd/core/aoe.py:213,417,433`,
`dnd/spatial/area_conditions.py:1256,1297,1337`,
`dnd/spells/conjuration.py:648,1076,3470,3767`,
`dnd/spells/abjuration.py:1415`,
`dnd/spells/illusion.py:1239,1290`,
`dnd/monsters/traits.py:1534,1596`,
`dnd/blocks/sensory.py:776`,
`dnd/content/scenarios/scenario_compatibility.py:213`, and
`dnd/items/environment.py:231,325`. `dnd/core/gridmap.py:2212` is the
public derived query definition. `dnd/core/gridmap.py:4571` is a retained
local `get_positions_near_entities` helper used by
`dnd/entities/entity.py:6300,6639`.

### Required direct test mutation

`tests/manual/test_08_world_model_and_movement.py` is active in-process and
contains the required direct migration:

- `:221` and `:305` call `grid.register_entity` with raw UUIDs;
- `:236` and `:318` call `grid.move_entity` with raw UUIDs and parent events.

The two tests must be rewritten around real Entity/Game ownership and public
movement/settlement behavior in Phase 4.1. No source-layout assertion is being
added.

## Phase 4.0 conclusion

The caller inventory found no unplanned active production caller and no scope
contradiction. The direct Banishment writes, two Pack Tactics/adjacency scans,
the two manual GridMap mutation tests, and the listed active test private
index assertions are all explicitly covered by the approved Phase 4.1/4.2
hard-cut. Transport/API/session and other excluded legacy residue remains
classified and untouched.

## Proposed bounded execution checkpoint

### Phase 4.1 — one atomic occupancy-authority cut

Expected production envelope, subject to the coordinator’s GO and the
zero-reference gate: `dnd/core/base_tiles.py`, `dnd/core/gridmap.py`,
`dnd/entities/entity.py`, `dnd/game.py`, and `dnd/runtime_reset.py`. The cut
adds only private Tile UUID membership and its defensive read, replaces the
two GridMap dictionaries with the existing narrow private commit/publish
boundary, routes Entity/Game lifecycle ordering through it, ports local
collision/replacement/position readers, and deletes the three old indexes,
`GridEntityPositionReceipt`, five public GridMap entity mutators, and
`Entity.get_all_entities_at_position`.

The complete currently known active collecting-test mutation envelope for the
deleted symbols/direct mutators is exactly:

1. `tests/engine/test_action_cost_and_position_commit.py`
2. `tests/engine/test_condition_transform_ownership.py`
3. `tests/engine/test_dice_event_semantics.py`
4. `tests/engine/test_entity_composition.py`
5. `tests/engine/test_manual_07_entity_composition.py`
6. `tests/engine/test_manual_09_conditions.py`
7. `tests/engine/test_manual_10_standard_conditions.py`
8. `tests/engine/test_manual_11_grid_tiles_terrain_movement.py`
9. `tests/engine/test_runtime_identity_registries.py`
10. `tests/engine/test_runtime_reset.py`
11. `tests/manual/test_01_runtime_identity_and_registries.py`
12. `tests/manual/test_02_entity_anatomy.py`
13. `tests/manual/test_08_world_model_and_movement.py`
14. `tests/manual/test_09_action_discovery_and_costs.py`
15. `tests/manual/test_10_combat_resolution.py`
16. `tests/manual/test_11_equipment_inventory_and_items.py`
17. `tests/manual/test_13_spellcasting_core.py`
18. `tests/manual/test_14_spell_families.py`
19. `tests/manual/test_17_encounters_turns_controllers.py`
20. `tests/manual/test_20_content_extension_basics.py`
21. `tests/manual/test_21_spell_and_feature_extensions.py`
22. `tests/manual/test_103_game_summary_store.py`
23. `tests/manual/test_128_antimagic_field.py`
24. `tests/manual/test_133_new_spells_batch4_legacy_contract.py`

`tests/manual/test_18_sessions_api_client_contract.py` is separately
classified excluded transport/API residue and is not a compatibility
requirement. No other currently known collecting test file contains a direct
deleted-symbol or direct-mutator match. The exact changed set must still be
re-established before edits; this ledger authorizes no Phase 4.1 edit by
itself.

### Phase 4.2 — world-presence lifecycle

Expected bounded production envelope: the existing lifecycle seams in
`dnd/entities/entity.py`, `dnd/core/gridmap.py`, and `dnd/blocks/sensory.py`,
plus `dnd/spatial/area_conditions.py`, `dnd/spells/abjuration.py`, and
`dnd/monsters/traits.py`. The cut adds the one suspended-state flag and
commands, registration-only observer ordering, composable world-absence light
suppression, entity-anchor LEFT/restore-from-empty handling, Banishment
suspend/restore ownership, and bounded adjacency/Pack Tactics reads. It does
not add an index, facade, controller, receipt, event path, or serializer.

The exact characterization selectors named above are the predeclared Phase
4.2 proof set for publication failure, per-step settlement, deployment
reduction, Banishment, anchored conditions, attached lights, suppression, and
restore. They are not run in this Phase 4.0 checkpoint.

No Phase 4.1/4.2 production or test changes were made. This checkpoint is
handed back as `READY_FOR_COORDINATOR_REVIEW`, not as an implementation or
approval of Phase 4.

## Ledger-only correction verification

The fixed-string deletion-gate inventory was rerun before freezing this
correction. The corrected `stage_entity_position` and
`publish_staged_entity_position` rows above include both Entity callers and
the internal `GridMap.move_entity` calls; no other active production caller
was found.

The five governing raw-byte hashes in the table above were rerun and all
matched. The accepted 59-member manifest was rehashed member-by-member: 59
members, breakdown `33 production / 26 tests`, mismatch count `0`.

`git diff --no-index --check /dev/null
DND_TILE_WORLD_ITEM_PHASE_4_IMPLEMENTATION_LEDGER_2026-08-25.md` emitted no
whitespace diagnostics; its exit status was `1` only because the ledger is an
untracked file (the only message was the repository's LF/CRLF conversion
warning).

The scoped current-byte comparison after the ledger-only repair reported the
same pre-existing `dnd/` and `tests/` working-set shape: 108 status paths,
105 tracked-diff paths, and 3 untracked paths; the Phase 4 ledger was absent
from that scope. No `dnd/` or `tests/` byte was changed by this correction,
and the 614-node baseline was therefore not rerun.

## Phase 4.1 + 4.2 atomic implementation checkpoint

Status: `PHASE_4_1_4_2_IMPLEMENTATION_CANDIDATE — READY_FOR_COORDINATOR_REVIEW`.
This section records the single unshippable 4.1+4.2 candidate. Slice 4.3 was
not started, and no final Phase 4 manifest or completion ledger was created.

### Governing verification and bounded implementation

The Phase 4 plan, accepted implementation-start ledger, and accepted Phase 3
manifest were verified before editing with the exact hashes recorded above;
the accepted manifest had 59 members (`33 production / 26 tests`) and `0`
mismatches at implementation start. The Phase 4.1+4.2 production envelope
implemented was:

- `dnd/core/base_tiles.py`
- `dnd/core/gridmap.py`
- `dnd/entities/entity.py`
- `dnd/game.py`
- `dnd/blocks/sensory.py`
- `dnd/runtime_reset.py`
- `dnd/spatial/area_conditions.py`
- `dnd/spells/abjuration.py`
- `dnd/monsters/traits.py`

The active collecting-test migrations and public proofs were bounded to:

- `tests/engine/test_action_cost_and_position_commit.py`
- `tests/engine/test_condition_transform_ownership.py`
- `tests/engine/test_dice_event_semantics.py`
- `tests/engine/test_entity_composition.py`
- `tests/engine/test_manual_07_entity_composition.py`
- `tests/engine/test_manual_09_conditions.py`
- `tests/engine/test_manual_10_standard_conditions.py`
- `tests/engine/test_manual_11_grid_tiles_terrain_movement.py`
- `tests/engine/test_runtime_identity_registries.py`
- `tests/engine/test_runtime_reset.py`
- `tests/engine/test_spatial_effects.py`
- `tests/manual/test_01_runtime_identity_and_registries.py`
- `tests/manual/test_02_entity_anatomy.py`
- `tests/manual/test_08_world_model_and_movement.py`
- `tests/manual/test_09_action_discovery_and_costs.py`
- `tests/manual/test_10_combat_resolution.py`
- `tests/manual/test_11_equipment_inventory_and_items.py`
- `tests/manual/test_13_spellcasting_core.py`
- `tests/manual/test_14_spell_families.py`
- `tests/manual/test_17_encounters_turns_controllers.py`
- `tests/manual/test_20_content_extension_basics.py`
- `tests/manual/test_21_spell_and_feature_extensions.py`
- `tests/manual/test_103_game_summary_store.py`
- `tests/manual/test_128_antimagic_field.py`
- `tests/manual/test_133_new_spells_batch4_legacy_contract.py`

The implementation removes the three old occupancy indexes, the old public
GridMap mutator/receipt surface, and `Entity.get_all_entities_at_position`.
Tile UUID membership is private and queried defensively; Entity owns the
objective coordinate; GridMap owns only the private expected-old/new
membership commit/publication boundary. Entity/Game deployment, movement,
detach, unpublished discard, publication-failure commitment, occupancy/path
revision invalidation, observer registration-only ordering, world-absence
light suppression, entity-anchor empty footprints, Banishment suspend/restore,
and bounded monster adjacency reads use that hard cut. No second occupancy
index, compatibility alias, public receipt, new event/callback/system,
serializer, controller, or Phase 5 work was added.

### Exact focused validation results

The following commands were run after the final production/test edits. Counts
are collection results for each command, not a claim about the prohibited
complete active 614-node Slice 4.3 lane:

| command scope | result |
|---|---:|
`tests/engine/test_runtime_identity_registries.py` | `6 passed` |
`tests/engine/test_entity_composition.py`, `test_manual_07_entity_composition.py`, `test_manual_11_grid_tiles_terrain_movement.py`, `test_grid_pathfinding.py`, `test_move_settlement.py`, `test_action_cost_and_position_commit.py`, `test_elevated_jump_transaction.py`, `test_traversal_connectors.py`, `tests/manual/test_08_world_model_and_movement.py` | `170 passed` |
condition, spatial-effect, direct-materialization, spell-family, life-state, senses/light, item/equipment, objective-state, direct-scenario, and active Banishment modules | `300 passed` |
`tests/engine/test_spatial_effects.py::test_entity_anchor_presence_leave_and_restore_reconciles_footprint` | `1 passed` |
event/wire/action/elevation/deployment/encounter characterization scope excluding non-collecting modules | `96 passed` |
`tests/architecture` | `41 passed` |
active manual identity/anatomy/conditions/combat/spell/antimagic scope that collected | `11 passed` after fixture repair; the rerun remained green |
standard-condition/cold-presentation/combat-action/action-discovery scope | `80 passed` |

The initial smoke run had `14 passed / 2 failed`. One failure was an active
identity fixture that attempted deployment without a live Tile; the fixture
was seeded with a public rectangular Tile map. The second was the attached
light movement proof: the world-absence token remained when no prior light
source had installed the existing callback. Entity attach/restore now reuses
the existing callback registration, with no new callback, so deployment and
restore clear only the world-presence token. The repaired smoke command was
`16 passed`.

The first broad occupancy run exposed 20 fixture failures for the same
missing-live-Tile setup; only the affected active test reset fixtures were
seeded, preserving the public missing-Tile rejection contract. No production
behavior was weakened to accommodate those tests.

### Hard-cut, compile, and scope gates

`./.venv/bin/python -m compileall -q dnd tests` exited `0`.

The scoped `git diff --check` over the active Phase 4 production/test files
exited `0`. The fixed-string hard-cut inventory has no active production or
collecting-test matches for the deleted indexes, receipt, deleted Entity
reader, or five deleted public GridMap mutators. The sole remaining match is
the governed excluded transport/API residue:
`tests/manual/test_18_sessions_api_client_contract.py:90`.

Two attempted broader collection commands were classified without edits:
`tests/engine/test_encounter_apis.py`,
`tests/engine/test_manual_14_core_combat_flow.py`,
`tests/engine/test_dice_event_semantics.py`,
`tests/manual/test_09_action_discovery_and_costs.py`,
`tests/manual/test_11_equipment_inventory_and_items.py`,
`tests/manual/test_20_content_extension_basics.py`, and
`tests/manual/test_21_spell_and_feature_extensions.py` import the absent
`dnd.content_system` package; `tests/manual/test_103_game_summary_store.py`
imports the absent `server` package; and `tests/engine/test_monster_presets.py`
imports the absent `dnd.monsters.circus_fighter`. These are pre-existing
collection/environment residues outside the approved Phase 4 active runtime
scope. No import stub, compatibility module, or out-of-scope repair was added.

The complete 614-node active lane, final collection comparison, locality
certification, final manifest, and external review remain intentionally NOT
RUN in this checkpoint because they belong to Slice 4.3.

## Phase 4.1 + 4.2 proof-repair

Status: `PHASE_4_1_4_2_PROOF_REPAIR_CANDIDATE — READY_FOR_COORDINATOR_REVIEW`.
Slice 4.3 was not started; no final manifest or final completion ledger was
created. This section is the single proof-repair checkpoint requested after
the prior 4.1+4.2 candidate review.

### Governing and scope verification

The governing raw-byte hashes remained unchanged:

| authority | SHA-256 |
|---|---|
| `DND_TILE_WORLD_ITEM_PHASE_4_ENTITY_OCCUPANCY_IMPLEMENTATION_PLAN_2026-08-25.md` | `00c31222bbfeb531cf6817c7e3c159c3eace85580796b49df564cc4b8d0e28f8` |
| `DND_TILE_WORLD_ITEM_PHASE_3_COMPLETION_LEDGER_2026-08-25.md` | `086e09c9f1329563e846dac0fd10b46331e456dfa2c83786e5de48cb96e113cb` |
| `DND_TILE_WORLD_ITEM_VERTICAL_BOUNDARY_MIGRATION_PLAN_2026-08-17.md` | `50411e5575e6336ca0301acf032797cdf1d5ea885df5ccd37d6619f593e7a193` |
| `DND_TILE_WORLD_ITEM_ACTIVE_RUNTIME_SCOPE_AMENDMENT_2026-08-24.md` | `f10e2fbbcb6ba8732d078f0c4f2f5276716eb51e32c083068f3cae93c9ba52d6` |
| `HOW_TO_TEST.MD` | `96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013` |
| `agents.md` | `fcc5dd1e15bae2ff86a7203f42b0c55de4d51dd0d93bc3a3ae059b7e58ee39b1` |

The accepted Phase 3 manifest remained the exact raw file
`DND_TILE_WORLD_ITEM_PHASE_3_IMPLEMENTATION_MANIFEST_2026-08-25.json` with
SHA `08c756ee62b953dd7326de9d5d06345eb3b948743b5d328559da8df6b40027f0` and
59 members. Its member-by-member verification was `0` mismatches at the
Phase 4 implementation-start checkpoint; the current expected 12 member
differences are the already-authorized Phase 4 hard-cut bytes, not Phase 3
artifact edits. The Phase 3 artifact itself was not modified.

### Public proof coverage mapped to Section 12

The following exact selectors now cover every required Section 12 row. Rows
listed together share one public behavior proof; no private registry/band
assertion or handler call-count assertion was added.

| Section 12 row | exact public selector(s) |
|---|---|
| 12.1 deploy agreement, move source/destination, co-location, defensive reads, no-op revision | `tests/engine/test_runtime_identity_registries.py::test_eb_01_004_entity_registers_as_block_and_entity`; `::test_entity_tile_membership_is_defensive_and_co_located_noop_is_quiet` |
| 12.1 arbitrary BaseBlock route, Tile replacement, map clear | `tests/engine/test_runtime_identity_registries.py::test_entity_membership_has_no_block_route_and_rejects_live_tile_mutations` |
| 12.1 suspended/detached `get_entity_position`, Game identity, observer loss, no second LEFT | `tests/engine/test_runtime_identity_registries.py::test_suspended_entity_keeps_game_identity_without_observer_or_second_left` |
| 12.1 missing-Tile rejection preserves coordinate, membership, revision, event cursor, light, and Senses | `tests/engine/test_runtime_identity_registries.py::test_missing_tile_move_is_publicly_atomic_for_occupancy_events_light_and_senses` |
| 12.1 publication-failure commitment | `tests/engine/test_action_cost_and_position_commit.py::test_spatial_publication_failure_keeps_committed_objective_position_and_raises` |
| 12.2 LEFT/ENTERED order, destination semantics, committed-position EFFECT, per-step settlement, no-op | `tests/engine/test_move_settlement.py::test_three_step_move_debits_and_reports_one_exact_settlement`; `tests/engine/test_move_settlement.py::test_committed_step_and_root_logs_retain_opportunity_attack_child`; `tests/engine/test_move_settlement.py::test_move_arrival_mutation_is_restored_before_publication_error_escapes`; `tests/engine/test_runtime_identity_registries.py::test_entity_tile_membership_is_defensive_and_co_located_noop_is_quiet` |
| 12.2 jump, connector, forced movement, and existing publication/cost semantics | `tests/engine/test_elevated_jump_transaction.py::test_elevated_jump_commits_one_direct_arc_with_exact_support_cost`; `tests/engine/test_traversal_connectors.py::test_connector_arrival_fires_once_and_preserves_objective_displacement`; `tests/engine/test_move_settlement.py::test_three_step_move_debits_and_reports_one_exact_settlement` |
| 12.3 retained identity/Game ownership/coordinate, absent Tile membership, subscriptions, observer LEFT, quiet suspended detach | `tests/engine/test_runtime_identity_registries.py::test_suspended_entity_keeps_game_identity_without_observer_or_second_left` |
| 12.3 attached light absent/restored destination, undeployed absence, death-token composition | `tests/engine/test_life_state_ownership.py::test_undeployed_attached_light_stays_absent_until_public_deploy`; `::test_world_presence_and_death_light_suppressions_compose_through_restore` |
| 12.3 nonconcentration empty anchored aura, restore, ordinary movement, terminal destruction | `tests/engine/test_spatial_effects.py::test_nonconcentration_entity_anchor_survives_empty_suspended_footprint`; `::test_entity_anchor_presence_leave_and_restore_reconciles_footprint`; `::test_entity_anchor_condition_destruction_while_suspended_does_not_resurrect` |
| 12.3 exact real-transition/no-op/rejected revision behavior and locality | `tests/engine/test_runtime_identity_registries.py::test_entity_membership_queries_are_map_size_invariant_at_public_boundary`; `::test_entity_tile_membership_is_defensive_and_co_located_noop_is_quiet`; `::test_missing_tile_move_is_publicly_atomic_for_occupancy_events_light_and_senses` |
| 12.4 application/denial ownership and suspend precommit/publication failure | `tests/engine/test_condition_transform_ownership.py::test_banishment_owns_denial_and_restores_spatial_registration`; `::test_banishment_suspend_publication_failure_compensates_without_condition_or_denial` |
| 12.4 failure after five provisional denial contributions | `tests/engine/test_condition_transform_ownership.py::test_banishment_provisional_failure_releases_all_denial_ownership` |
| 12.4 absence from collision/perception/carried light and ordinary retained-origin cleanup | `tests/engine/test_condition_transform_ownership.py::test_banishment_owns_denial_and_restores_spatial_registration`; `tests/manual/test_133_new_spells_batch4_legacy_contract.py::test_banishment_removes_and_restores_spatial_perception` |
| 12.4 restore precommit retry and restore ENTERED publication cleanup | `tests/engine/test_condition_transform_ownership.py::test_banishment_restore_failure_keeps_condition_retryable_and_then_cleans_up`; `::test_banishment_restore_publication_failure_keeps_presence_and_finishes_cleanup` |
| 12.4 occupied-origin stable displacement and no-offset/co-location fallback | `tests/manual/test_133_new_spells_batch4_legacy_contract.py::test_banishment_return_displaces_an_occupant`; `::test_banishment_return_co_locates_when_every_displacement_offset_is_blocked` |
| 12.4 condition-to-LEFT and removal-to-ENTERED causal lineage | `tests/engine/test_condition_transform_ownership.py::test_banishment_owns_denial_and_restores_spatial_registration` |
| monster co-located present/suspended adjacency for Pack Tactics and Sneak Attack | `tests/engine/test_combat_actions.py::test_pack_tactics_public_attack_respects_co_located_ally_presence`; `::test_sneak_attack_public_damage_respects_co_located_ally_presence`; active boundary extension `tests/manual/test_53_srd_monster_traits.py::test_pack_tactics_sunlight_and_keen_senses_use_contextual_values` |

### Bounded repairs and exact results

The initial proof run was `31 passed / 1 failed`: the locality assertion
compared fresh UUIDs across two map sizes. It was repaired to compare public
cardinality, empty distant result, objective coordinate, and revision delta.
The first active monster-boundary run exposed an existing authored ally at
the original target coordinate, so the new proof target was moved to an
isolated public coordinate; the corrected selector passed. The first
Banishment failure assertion expected normalized movement `1` while the
fixture's authored movement is `30`; that test-only expectation was corrected.
The condition-effect failure handler was corrected to use the public target
event field. No production behavior was weakened.

The nonconcentration generic `SpatialCondition` proof then exposed a real
bounded production omission: the existing base Entity-anchor transition was
abstract, and `transition_footprint(empty)` retired the condition. Within the
approved `dnd/spatial/area_conditions.py` envelope, the base family now
settles an empty active footprint, relocates it through the existing public
footprint/event machinery, and keeps empty `transition_footprint` nonterminal.
The final exact selector passed, and the full spatial module remained green.

Final focused results after the repairs:

| scope | result |
|---|---:|
| `tests/engine/test_runtime_identity_registries.py` | `10 passed` |
| `tests/engine/test_life_state_ownership.py` | `8 passed` |
| `tests/engine/test_combat_actions.py` | `37 passed` |
| `tests/engine/test_condition_transform_ownership.py` | `17 passed` |
| `tests/engine/test_spatial_effects.py` | `60 passed` |
| movement/path/senses/condition/objective/reset focused command | `151 passed` |
| three Banishment manual selectors, including no-offset fallback | `3 passed` |
| active monster-trait selector | `1 passed` (after isolated-coordinate repair) |
| `tests/architecture` | `41 passed` |
| `./.venv/bin/python -m compileall -q dnd tests` | exit `0` |
| scoped `git diff --check` | exit `0` |

The proof-repair changed no production file except
`dnd/spatial/area_conditions.py`. The test files changed in this checkpoint
are:

- `tests/engine/test_runtime_identity_registries.py`
- `tests/engine/test_spatial_effects.py`
- `tests/engine/test_life_state_ownership.py`
- `tests/engine/test_condition_transform_ownership.py`
- `tests/engine/test_combat_actions.py`
- `tests/manual/test_53_srd_monster_traits.py`
- `tests/manual/test_133_new_spells_batch4_legacy_contract.py`

The active hard-cut scan returned only the classified excluded transport/API
residue `tests/manual/test_18_sessions_api_client_contract.py:90` and the
retained identity-only `dnd/entities/entity.py:792` `Entity.register_entity`
method. There are no active references to the deleted spatial indexes,
receipt, deleted Entity spatial reader, or deleted GridMap occupancy mutators.

No complete 614-node Slice 4.3 lane, final collection comparison, final
manifest, or external review was run. This candidate is handed back as
`READY_FOR_COORDINATOR_REVIEW`, not self-approved.

## Phase 4.1 + 4.2 proof/slop correction

Status: `PHASE_4_1_4_2_PROOF_REPAIR_CORRECTION_CANDIDATE — READY_FOR_COORDINATOR_REVIEW`.
This section supersedes the preceding Section 12 mapping where it corrects or
expands a claimed row. Slice 4.3 was not started, and no final manifest or
completion ledger was created.

### Bounded correction scope

The duplicate `AreaCondition.transition_anchor_to_absence` override was
deleted from `dnd/spatial/area_conditions.py`; the generic
`SpatialCondition.transition_anchor_to_absence` family implementation remains
the sole authority. The full spatial-effects module stayed green. No other
production file changed for this correction.

The public proof additions/extensions were limited to:

- `tests/engine/test_runtime_identity_registries.py` — exact public revision
  deltas for deploy, no-op, move, rejected missing-Tile move, suspend, restore,
  and present detach;
- `tests/engine/test_condition_transform_ownership.py` — detached-target
  suspend-precommit rejection and all five denial-channel cleanup assertions,
  including retry and committed-publication cleanup;
- `tests/engine/test_life_state_ownership.py` — suspend, die while suspended,
  restore while dead, then revive light-token composition;
- `tests/engine/test_spatial_effects.py` — public EFFECT-boundary observation
  that ordinary movement never exposes an empty anchor, dark light field, or
  lost contact;
- `tests/manual/test_133_new_spells_batch4_legacy_contract.py` — public
  collision, objective AoE targeting, perception, attached-light, anchored
  footprint, and stable two-occupant return proofs.

### Corrected Section 12 public mapping

The exact selectors below are the evidence for the corrected rows. The
small/large locality selector proves equal public results and revision deltas;
it is not a work counter. Bounded O(1) Tile lookup is certified by the
approved code-review boundary rather than by a new diagnostic.

| Section 12 row | exact public selector(s) |
|---|---|
| 12.1 authority, arbitrary `BaseBlock` non-membership, defensive reads, co-location, Tile replacement, and `clear` rejection | `tests/engine/test_runtime_identity_registries.py::test_entity_membership_has_no_block_route_and_rejects_live_tile_mutations`; `::test_entity_tile_membership_is_defensive_and_co_located_noop_is_quiet` |
| 12.1 detached/suspended neutral position reads, Game ownership, observer/subscription removal, and quiet suspended detach | `tests/engine/test_runtime_identity_registries.py::test_suspended_entity_keeps_game_identity_without_observer_or_second_left` |
| 12.1 missing-Tile move atomicity across coordinate, Tile membership, revision, event cursor, light, and Senses | `tests/engine/test_runtime_identity_registries.py::test_missing_tile_move_is_publicly_atomic_for_occupancy_events_light_and_senses` |
| 12.1 exact +1/0 occupancy revision table for real deploy/move/suspend/restore/present-detach, no-op, and rejected transition | `tests/engine/test_runtime_identity_registries.py::test_public_entity_lifecycle_revision_deltas_are_exact` |
| 12.1 locality | `tests/engine/test_runtime_identity_registries.py::test_entity_membership_queries_are_map_size_invariant_at_public_boundary`; equal public results are asserted, with no work-counter claim |
| 12.2 per-step LEFT/ENTERED settlement, destination semantics, committed-position EFFECT, and movement completion | `tests/engine/test_move_settlement.py::test_three_step_move_debits_and_reports_one_exact_settlement`; `tests/engine/test_senses_light_stealth.py::test_each_move_step_emits_objective_and_subjective_facts_before_step_completion` |
| 12.2 ordinary LEFT-with-destination has no empty anchor/light/contact interval | `tests/engine/test_spatial_effects.py::test_entity_anchor_presence_leave_and_restore_reconciles_footprint` — its public passive EFFECT-boundary observation asserts the active footprint, bright field, and observer contact for every observed LEFT |
| 12.2 publication-failure commitment and existing jump/connector settlement | `tests/engine/test_action_cost_and_position_commit.py::test_spatial_publication_failure_keeps_committed_objective_position_and_raises`; `tests/engine/test_elevated_jump_transaction.py::test_elevated_jump_commits_one_direct_arc_with_exact_support_cost`; `tests/engine/test_traversal_connectors.py::test_connector_arrival_fires_once_and_preserves_objective_displacement` |
| 12.3 retained identity/coordinate with absent membership, observer loss, and no second LEFT | `tests/engine/test_runtime_identity_registries.py::test_suspended_entity_keeps_game_identity_without_observer_or_second_left` |
| 12.3 attached light at restored destination, undeployed absence, and independent death/world-presence ownership | `tests/engine/test_life_state_ownership.py::test_undeployed_attached_light_stays_absent_until_public_deploy`; `::test_world_presence_and_death_light_suppressions_compose_through_restore` — the latter executes suspend → die → restore while dead → revive |
| 12.3 active empty entity anchor, restore, terminal condition destruction, and ordinary movement | `tests/engine/test_spatial_effects.py::test_nonconcentration_entity_anchor_survives_empty_suspended_footprint`; `::test_entity_anchor_condition_destruction_while_suspended_does_not_resurrect`; `::test_entity_anchor_presence_leave_and_restore_reconciles_footprint` |
| 12.4 Banishment suspend precommit failure: no condition, suspension, Tile membership, or five-channel denial leak | `tests/engine/test_condition_transform_ownership.py::test_banishment_suspend_precommit_failure_is_publicly_atomic` |
| 12.4 Banishment LEFT publication compensation and five-channel provisional failure cleanup | `tests/engine/test_condition_transform_ownership.py::test_banishment_suspend_publication_failure_compensates_without_condition_or_denial`; `::test_banishment_provisional_failure_releases_all_denial_ownership` |
| 12.4 banished absence from collision, objective AoE targeting, perception, attached light, and anchored footprint | `tests/manual/test_133_new_spells_batch4_legacy_contract.py::test_banishment_removes_and_restores_spatial_perception` — uses public `is_walkable_for`, `Sphere.compute_objective`, Senses contact, resolved light, and `DraconicPresenceAura` footprint |
| 12.4 restore precommit retry and restore ENTERED publication cleanup | `tests/engine/test_condition_transform_ownership.py::test_banishment_restore_failure_keeps_condition_retryable_and_then_cleans_up`; `::test_banishment_restore_publication_failure_keeps_presence_and_finishes_cleanup` |
| 12.4 deterministic occupied-origin return: UUID-stable first selection, at most one displacement, second occupant remains co-located, and all-eight-offset fallback | `tests/manual/test_133_new_spells_batch4_legacy_contract.py::test_banishment_return_selects_one_stable_origin_occupant`; `::test_banishment_return_co_locates_when_every_displacement_offset_is_blocked` |
| 12.4 Banishment condition-application → LEFT and condition-removal → ENTERED lineage | `tests/engine/test_condition_transform_ownership.py::test_banishment_owns_denial_and_restores_spatial_registration` |
| 12.5 present co-located ally and suspended retained-coordinate ally for Pack Tactics/Sneak Attack | `tests/engine/test_combat_actions.py::test_pack_tactics_public_attack_respects_co_located_ally_presence`; `::test_sneak_attack_public_damage_respects_co_located_ally_presence`; `tests/manual/test_53_srd_monster_traits.py::test_pack_tactics_sunlight_and_keen_senses_use_contextual_values` |

### Exact correction run

The first correction run exposed only two test-seam defects: the public
`SpatialChangeEvent` uses `position` for the LEFT source rather than a
nonexistent `previous_position` field, and public `Sphere` construction
requires its source UUID. Both were repaired in the named test files; no
production behavior was changed for either failure.

| command | exact result |
|---|---:|
| corrected proof selector matrix (anchor, generic empty footprint, death/light, revision table, five Banishment failure/cleanup rows, absence, stable displacement, and all-eight fallback) | `13 passed in 12.79s` |
| affected proof/lifecycle modules: `test_spatial_effects.py`, `test_life_state_ownership.py`, `test_runtime_identity_registries.py`, `test_condition_transform_ownership.py`, `test_combat_actions.py`, `test_133_new_spells_batch4_legacy_contract.py`, `test_53_srd_monster_traits.py` | `167 passed in 62.24s` |
| affected movement/senses/action/lifecycle modules: `test_senses_light_stealth.py`, `test_move_settlement.py`, `test_condition_lifecycle.py`, `test_runtime_reset.py`, `test_action_discovery.py` | `133 passed in 57.83s` |
| `tests/architecture` | `41 passed in 22.99s` |
| `.venv/bin/python -m compileall -q dnd tests` | exit `0` |
| `git diff --check` | exit `0` |

The corrected hard-cut scan over active `dnd/` and collecting `tests/` Python
returned no active matches for the deleted indexes, receipt, deleted Entity
reader, or deleted GridMap occupancy mutators. The sole match remains the
governed excluded transport/API residue:
`tests/manual/test_18_sessions_api_client_contract.py:90`.

No 614-node Slice 4.3 lane, final collection comparison, final manifest, or
external review was run. This remains a candidate for coordinator review and
is not self-approved.

## Slice 4.3 integrated certification — final candidate

This section records the completed validation-only certification. No
production or test source was edited during Slice 4.3.

### Governing bytes and node accounting

The governing raw-byte hashes were reverified before artifact freezing:

| artifact | SHA-256 |
|---|---|
| Phase 4 plan | `00c31222bbfeb531cf6817c7e3c159c3eace85580796b49df564cc4b8d0e28f8` |
| accepted Phase 3 completion ledger | `086e09c9f1329563e846dac0fd10b46331e456dfa2c83786e5de48cb96e113cb` |
| master | `50411e5575e6336ca0301acf032797cdf1d5ea885df5ccd37d6619f593e7a193` |
| active runtime scope amendment | `f10e2fbbcb6ba8732d078f0c4f2f5276716eb51e32c083068f3cae93c9ba52d6` |
| accepted Phase 3 manifest | `08c756ee62b953dd7326de9d5d06345eb3b948743b5d328559da8df6b40027f0` |
| `agents.md` | `fcc5dd1e15bae2ff86a7203f42b0c55de4d51dd0d93bc3a3ae059b7e58ee39b1` |
| `HOW_TO_TEST.MD` | `96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013` |

The accepted Phase 3 manifest contains 59 members. Its current-byte
verification found 12 differences, all within the authorized Phase 4
occupancy/lifecycle mutation envelope (`dnd/blocks/sensory.py`,
`dnd/core/base_tiles.py`, `dnd/core/gridmap.py`, `dnd/entities/entity.py`,
`dnd/runtime_reset.py`, `dnd/spatial/area_conditions.py`, plus the six
authorized active test files `tests/engine/test_action_cost_and_position_commit.py`,
`tests/engine/test_manual_11_grid_tiles_terrain_movement.py`,
`tests/engine/test_runtime_reset.py`, `tests/engine/test_spatial_effects.py`,
`tests/manual/test_08_world_model_and_movement.py`, and
`tests/manual/test_17_encounters_turns_controllers.py`); no Phase 3 artifact
was edited.

The accepted semantic baseline remains 614 nodes with normalized hash
`774c745d442d5db6b8bfb2878309b4eae118e08d264ae4a12370f2a21db05641`. The
unchanged accepted path command collected and ran 617 nodes because exactly
these three authorized Phase 4 nodes are inside `test_spatial_effects.py`:

- `tests/engine/test_spatial_effects.py::test_entity_anchor_condition_destruction_while_suspended_does_not_resurrect`
- `tests/engine/test_spatial_effects.py::test_entity_anchor_presence_leave_and_restore_reconciles_footprint`
- `tests/engine/test_spatial_effects.py::test_nonconcentration_entity_anchor_survives_empty_suspended_footprint`

The exact path-level result was `617 passed in 209.92s`. Removing those three
nodes from its collect-only set reproduced count 614 and the accepted hash;
there were zero unexpected added nodes. The corrected maintained selectors
outside that path set collected 27 test instances and passed `27 passed in
16.41s`. The exact deduplicated final union therefore collected and ran 644
nodes, with normalized hash
`fbeb7f4995af083079505607164a702b6ff46a25d55c027006507142fde2b3af`:

```text
.venv/bin/python -m pytest --collect-only -q -p no:cacheprovider <the exact
27 frozen path inputs and 26 outside-path selector inputs recorded in the
final manifest metadata>
.venv/bin/python -m pytest -q -p no:cacheprovider <the sorted unique nodes
from that collect-only result>
```

The exact final union result was `644 passed in 185.28s (0:03:05)`. The
manifest records the complete path/selector inputs, the three in-path added
nodes, the 27 outside-path node instances, the normalization algorithm, and
the final node hash for machine reproduction.

### Final validation gates

| gate | exact result |
|---|---:|
| corrected maintained Phase 4 selector collection | `27 collected` |
| corrected maintained Phase 4 selector execution | `27 passed in 16.41s` |
| exact final active union | `644 passed in 185.28s` |
| complete architecture lane | `41 passed in 20.69s` |
| structured locality selectors (small/large maps and bounded local queries) | `10 passed in 25.70s` |
| compile every final scoped Python member (`compileall -q`) | exit `0` |
| scoped `git diff --check` | exit `0` |

The dependency gate returned empty results for GridMap imports of Entity,
concrete items, or SpatialCondition; Entity imports of `dnd.spatial`; core
event imports of GridMap/Entity/Senses/authored content/renderer; public Tile
Entity-membership mutators; and active `Senses.position` writers. The static
scope scan found no `TYPE_CHECKING` mask, late-import/reflection capability,
or second deleted-index/receipt symbol in the authorized active scope. The
hard-cut inventory returned exactly one match,
`tests/manual/test_18_sessions_api_client_contract.py:90`, classified as the
governed excluded transport/API residue. No active production or collecting
test match remained for the deleted indexes, receipt, deleted Entity reader,
or five public GridMap occupancy mutators.

### Final manifest and scope

The deterministic final manifest is
`DND_TILE_WORLD_ITEM_PHASE_4_IMPLEMENTATION_MANIFEST_2026-08-25.json`.
Its membership is the sorted/deduplicated accepted 59-member Phase 3 union
plus only authorized Phase 4 active files: 36 production members and 48 test
members, 84 total. It excludes the manifest and this ledger, governance
Markdown, server/deprecated-server/SDK/transport/generated/renderer/editor/
cross-language files, inactive content, and unrelated dirty files. The
manifest's current raw-byte member hashes were generated from those 84 exact
paths, with no duplicate/missing/extra member.

| artifact | SHA-256 |
|---|---|
| final Phase 4 implementation manifest | `692af1278cec1d0de3dda6893f37415556c789fe734cc7fe66a8c2d08874a121` |

Final status: `READY_FOR_INDEPENDENT_REVIEW`. This is a candidate handoff,
not self-approval; Slice 4.3 is stopped here and Phase 5 remains unopened.


### Committed-event correction and final recertification

Coordinator-required correction was applied narrowly in dnd/core/gridmap.py. The committed membership path now calls EventQueue.publish_preflighted(event) first, storing the already-accepted DECLARATION version without dispatching declaration handlers, then advances that stored event through the existing EXECUTION, EFFECT, and COMPLETION transitions. The interim direct EXECUTION transition with use_register=True was removed. No event API, event state, callback, or second publication path was added.

The approved public regression remains tests/engine/test_action_cost_and_position_commit.py::test_committed_entity_membership_facts_ignore_declaration_veto. It installs a DECLARATION cancellation handler and observes public EFFECT and COMPLETION facts; the objective Entity/Tile membership and reducer-owned Senses position remain committed, with LEFT and ENTERED each reaching both observed phases.

Exact five-proof repair gate:

- tests/engine/test_action_cost_and_position_commit.py::test_committed_entity_membership_facts_ignore_declaration_veto
- tests/engine/test_action_cost_and_position_commit.py::test_spatial_publication_failure_keeps_committed_objective_position_and_raises
- tests/engine/test_senses_light_stealth.py::test_each_move_step_emits_objective_and_subjective_facts_before_step_completion
- tests/engine/test_move_settlement.py::test_three_step_move_debits_and_reports_one_exact_settlement
- tests/engine/test_direct_scenario_deployment.py::test_world_birth_and_deployment_are_ordered_event_facts

Result: 5 passed in 6.40s.

Final recertification results:

- affected event/movement/senses/occupancy lane: 187 passed in 57.96s;
- complete architecture lane: 41 passed in 23.41s;
- corrected structured locality selectors: 10 passed in 29.11s;
- compile of all 84 scoped Python members: exit 0;
- scoped git diff --check: exit 0, with only existing LF-to-CRLF normalization warnings;
- exact active union collect-only: 645 nodes, normalized SHA-256 73c88e8b9261403f42543c6d63cb9103e8a660af802c78f6f36435b3d2183ca6;
- exact active union execution: 645 passed. Execution used fresh bounded pytest processes, with the sorted node prefix through index 142 already green and the resumed run starting at index 143. The two previously resource-heavy direct-scenario nodes each passed in about five seconds after the correction.
- dependency gate: GridMap forbidden imports [], Entity dnd.spatial imports [], core-event forbidden imports {}, Tile public Entity-related methods only get_entity_uuids;
- active deleted-index/receipt/removed-reader hard-cut matches: zero; the only known remaining fixed-string match is the governed excluded transport residue at tests/manual/test_18_sessions_api_client_contract.py:90.

The earlier long-running scenario attempt is recorded as a validation interruption, not a test failure: before this correction pytest was recursively formatting a failed assembled-value assertion because only three spatial event versions were stored. After the preflighted publication correction, the exact public proof and the full 645-node union passed.

Final manifest verification is zero duplicate members, zero missing members, zero extra members, and zero current-byte hash mismatches. The manifest contains 84 members: 36 production and 48 tests. Its SHA-256 is 5e47a5ae778aae0a783b20cf99c86a2199abf340dc6b2193baab34d76be8c009. The final node set remains the accepted 614-node baseline plus four in-path Phase 4 nodes and 27 outside-path maintained node instances, for 645 unique nodes.

Changed scoped files for this correction/certification are dnd/core/gridmap.py, tests/engine/test_action_cost_and_position_commit.py, this existing implementation ledger, and the exact final manifest. No excluded files, Phase 5 files, or unrelated dirty files were edited.

Final status: READY_FOR_INDEPENDENT_REVIEW. This is a candidate handoff, not self-approval; Phase 5 remains unopened.

### Consolidated Phase 4 anti-slop repair and recertification

Four bounded corrections were applied and no other production/test surface was changed.

1. Banishment compensation authority: dnd/spells/abjuration.py now calls target.suspend_spatial_presence directly. The existing idempotent _release_owned_runtime_state hook is the sole uncommitted compensation owner. A compensating PositionPublicationError is accepted only after public Entity/Tile state proves deployment and membership at the retained position. PositionCommitError and other uncommitted compensation failures raise the explicit Banishment suspension-compensation invariant error from the compensation failure, preserving the original LEFT PositionPublicationError in the surfaced exception chain. No flag, receipt, manager, BaseCondition change, or second cleanup path was added.

2. Duplicate ally rule: dnd/monsters/traits.py::pack_tactics_advantage now delegates to the existing _has_adjacent_ally(source, target) and constructs its modifier only for a true result. No helper/cache/type was added.

3. Disabled-event committed facts: dnd/core/gridmap.py::_publish_entity_membership no longer returns early when events are disabled. LEFT and ENTERED always use the existing _fire_committed_spatial_event buffer, and enable_events(flush_pending=True) flushes the already committed four-phase facts.

4. Committed-fact proof: tests/engine/test_action_cost_and_position_commit.py::test_committed_entity_membership_facts_ignore_declaration_veto now uses one removable EventHandler with DECLARATION veto and EFFECT observation triggers, a public cursor, explicit parent UUID, and iter_events_since. It asserts ordered DECLARATION/EXECUTION/EFFECT/COMPLETION versions, stable per-fact lineage, parent linkage, EFFECT observation, and objective/Tile/Senses settlement. The non-removable callback and global EventQueue.reset cleanup were removed.

New public regressions:

- tests/engine/test_condition_transform_ownership.py::test_banishment_compensation_failure_preserves_publication_chain_without_presence
- tests/engine/test_action_cost_and_position_commit.py::test_disabled_move_commits_membership_and_flushes_four_phase_facts

Focused evidence:

- Initial focused Banishment run exposed one test assertion defect: the public exception chain reached the original LEFT PositionPublicationError through the compensation PositionCommitError rather than as the immediate context. The test was repaired to walk the public cause/context chain; no production behavior was broadened.
- corrected Banishment failure/cleanup selectors: 7 passed in 8.47s;
- committed-event, existing publication-exception, causal-Senses, deployment, Pack Tactics, and Sneak Attack selectors: 9 passed in 9.03s;
- affected module lane: 291 passed in 126.38s;
- complete architecture lane: 41 passed in 24.27s;
- structured locality lane: 10 passed in 28.82s;
- compile of all 84 scoped Python members: exit 0;
- scoped diff-check: exit 0, with only LF-to-CRLF normalization warnings;
- dependency gate: GridMap forbidden imports [], Entity dnd.spatial imports [], core-event forbidden imports {}, and Tile public Entity-related methods only get_entity_uuids;
- hard-cut gate: zero active deleted-authority matches; only the governed excluded transport residue remains at tests/manual/test_18_sessions_api_client_contract.py:90.

Final active union:

- collect-only count: 647;
- normalized node-set SHA-256: db7e60df6300812c804034f5bf1779b71adeb8f7f09b6a08efa3b2b9d0fb512c;
- execution: 647 passed using fresh bounded pytest shards, with direct-scenario nodes isolated one per process;
- the five in-path Phase 4 additions are the prior four plus test_disabled_move_commits_membership_and_flushes_four_phase_facts;
- the 28 outside-path node instances include the new Banishment compensation selector.

Final manifest verification: 84 members, 36 production and 48 tests, zero duplicates, zero missing/extra members, and zero current-byte hash mismatches. Final manifest SHA-256: 16aeba7818d3cc9471de52c84b311e85359db40f55ef9a17043be30c3686b33d.

Candidate scoped files changed by this repair package: dnd/spells/abjuration.py, dnd/monsters/traits.py, dnd/core/gridmap.py, tests/engine/test_action_cost_and_position_commit.py, tests/engine/test_condition_transform_ownership.py, this existing ledger, and the final manifest. No excluded files or Phase 5 files were edited.

Final status: READY_FOR_INDEPENDENT_REVIEW. This remains a candidate handoff, not self-approval; Phase 5 remains unopened.

### Final disabled-occupancy atomicity repair and recertification

The anti-slop review reproduced that committed Entity occupancy could be
mutated while GridMap events were disabled, leaving delayed committed facts
unsafe to replay. The bounded repair adds one guard at the existing private
`_commit_entity_membership` boundary, before Tile membership or occupancy
revision mutation. Entity deploy, move, detach, suspend, and restore wrappers
therefore surface `PositionCommitError` and retain their existing rollback
semantics. Generic pending-event flushing was not changed; no replay path,
event API, manager, receipt, flag, facade, or Phase 5 behavior was added.

The stale public regression
`tests/engine/test_action_cost_and_position_commit.py::test_disabled_move_commits_membership_and_flushes_four_phase_facts`
was replaced by
`tests/engine/test_action_cost_and_position_commit.py::test_disabled_entity_occupancy_attempts_are_atomic_and_publish_nothing`.
It proves, through public Entity/Game/GridMap/EventQueue/Tile/Senses seams,
that two sequential moves, deploy, detach, suspend, and restore attempts all
raise `PositionCommitError` while events are disabled; objective position,
Game ownership, Tile membership, occupancy revision, event cursor, resolved
light, and reducer-owned Senses remain unchanged; re-enable flushes no Entity
LEFT/ENTERED fact; and an ordinary move and restore publish and settle after
events are re-enabled.

No active production caller requires Entity occupancy mutation while events
are disabled. The complete active commit-boundary caller inventory remains
`dnd/entities/entity.py` only: `_attach_to_world`, `_detach_from_world`,
`suspend_spatial_presence`, `restore_spatial_presence`,
`update_entity_position`, and `discard_unpublished_runtime`.

Exact repair and validation record:

- initial system `pytest` command was unavailable; the governed `.venv/bin/pytest` command was used thereafter;
- the first full-union execution attempt collected successfully but plain `xargs` split a parametrized node containing spaces (`Sight-True`) and ran no tests; no test or source failure occurred;
- the corrected newline-delimited execution reran the same collected node set and passed `647 passed in 220.36s`;
- direct replacement plus prior committed-event, publication-failure, causal-Senses, occupancy, Banishment, light, Pack Tactics, and Sneak Attack selectors: `28 passed in 16.59s`;
- complete architecture lane: `41 passed in 26.17s`;
- structured locality/rebuild diagnostic subset: `12 passed in 7.41s`;
- changed Python compile: exit `0`;
- scoped diff-check: exit `0`, with only existing LF-to-CRLF normalization warnings;
- dependency gate: GridMap forbidden imports `[]`, Entity `dnd.spatial` imports `[]`, core-event forbidden imports `{}`, and Tile public Entity-related methods only `get_entity_uuids`;
- hard-cut gate: zero active deleted-authority matches; the sole known fixed-string match remains the governed excluded transport residue at `tests/manual/test_18_sessions_api_client_contract.py:90`;
- exact manifest-defined union collect-only: `647` nodes, normalized SHA-256 `0062d230c5a85ab1a08eb4ad6ebdf7c75ffed01e99d81b10dba561e9440e9cbe`;
- exact manifest-defined union execution: `647 passed in 220.36s`;
- manifest verification: `84` members (`36` production, `48` tests), sorted unique membership, zero duplicate/missing/extra members, and zero current-byte hash mismatches.

The current exact member hashes for the two files changed in this repair are:

| path | SHA-256 |
|---|---|
| `dnd/core/gridmap.py` | `7f63c588e141d8ed33cecff61ac8a02d5f76a213ac50c7fada725223dbefe373` |
| `tests/engine/test_action_cost_and_position_commit.py` | `efb37b67bacdac03d005432ecc240bd46243a1a09530a9f14cc9ccecc1550119` |

The final node accounting is the accepted `614` baseline plus the same
in-path Phase 4 additions and maintained outside-path selectors, for `647`
unique nodes. The renamed in-path proof is recorded exactly in the final
manifest metadata. The final manifest is
`DND_TILE_WORLD_ITEM_PHASE_4_IMPLEMENTATION_MANIFEST_2026-08-25.json` with
SHA-256 `95d9fe317a09ceed66745627320d562ddc68c101a9ec54eee6e0be934b2a868b`.

Changed files in this bounded repair are exactly
`dnd/core/gridmap.py`,
`tests/engine/test_action_cost_and_position_commit.py`, this existing
implementation ledger, and the final manifest. No excluded files, Phase 5
files, or unrelated dirty files were edited.

Final status: READY_FOR_INDEPENDENT_REVIEW. This is a candidate handoff, not
self-approval; Phase 5 remains unopened.

### Certification-scope correction and final recertification

The certification-only review identified stale manifest scope, with no new
implementation defect. The redundant stale `recertification` object was
deleted from the final manifest; only `latest_recertification` remains.

The active manifest was corrected from 84 members to 78 sorted unique members:
36 production and 42 active collecting tests. The following six files are
non-collecting governed residue, were removed from all manifest membership and
Phase-4 addition metadata, and were reverted only across their exact
Phase-4-era migration hunks:

- `tests/engine/test_dice_event_semantics.py`
- `tests/manual/test_09_action_discovery_and_costs.py`
- `tests/manual/test_11_equipment_inventory_and_items.py`
- `tests/manual/test_20_content_extension_basics.py`
- `tests/manual/test_21_spell_and_feature_extensions.py`
- `tests/manual/test_103_game_summary_store.py`

`git diff --` over exactly those six paths is empty. Their restored legacy
`Entity._entity_by_position` rows remain classified as excluded governed
residue; they were not edited to satisfy the active hard-cut gate. No active
collecting node or import depends on them.

Exact certification results:

- independent manifest-defined collect-only recollection: `647` nodes, normalized SHA-256 `0062d230c5a85ab1a08eb4ad6ebdf7c75ffed01e99d81b10dba561e9440e9cbe`;
- exact active union execution: `647 passed in 232.02s`;
- compile of all `78` manifest Python members: exit `0`;
- scoped diff-check: exit `0`, with only existing LF-to-CRLF normalization warnings;
- dependency gate: GridMap forbidden imports `[]`, Entity `dnd.spatial` imports `[]`, core-event forbidden imports `{}`, and Tile public Entity-related methods only `get_entity_uuids`;
- hard-cut gate: zero active deleted-authority matches after excluding the six named non-collecting files and the governed transport residue at `tests/manual/test_18_sessions_api_client_contract.py:90`;
- manifest verification: `78` members, `36` production and `42` tests, zero duplicates, zero missing/extra members, and zero current-byte hash mismatches.

The current manifest is
`DND_TILE_WORLD_ITEM_PHASE_4_IMPLEMENTATION_MANIFEST_2026-08-25.json` with
SHA-256 `e66f767412230e0ed9e0c024b1e155d27b581599375ee330d5759dcd498b0d85`.
The accepted governing hashes remain unchanged, and active runtime behavior
is unchanged by this scope correction. No production implementation, active
test, excluded surface, or Phase-5 file was changed beyond the already
authorized disabled-occupancy candidate and the six exact residue reversions.

Final status: READY_FOR_INDEPENDENT_REVIEW. This is a candidate handoff, not
self-approval; Phase 5 remains unopened.
