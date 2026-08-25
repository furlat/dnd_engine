# Phase 3 Slice 3.3 Repair Certification Ledger

Status: `CANDIDATE_FOR_INDEPENDENT_REVIEW`. This package does not claim full
Phase 3 completion and does not begin Slice 3.4.

## Governing binds

| Authority | SHA-256 |
|---|---|
| Repair plan | `5b8c50f6cbbd8100380fb5fc091e9b4389406d024256063d03632af6445b937e` |
| Master plan | `50411e5575e6336ca0301acf032797cdf1d5ea885df5ccd37d6619f593e7a193` |
| Phase 3 guidance | `ed3b4afbe88ab4278c27429b3c9b1727a8ccdc144c3019ab5dcef00ca1715cd0` |
| Active-runtime amendment | `f10e2fbbcb6ba8732d078f0c4f2f5276716eb51e32c083068f3cae93c9ba52d6` |
| Active-runtime ledger | `63e25aac3f0136daa8d43b860c328fe8b7b9f26529f65792b123dc77293c059a` |
| Accepted Slice 3.1 manifest | `2501ed3fb35c9b17ad5ef3dcd3bc289ef2145c9ea2ea60ab47164bacba099320` |
| Pre-resume manifest | `c39258b83b911792d44dca3a2600e209b30bd5f76ded2778dfed2b676141c507` |

## Exact certification artifacts

- Manifest: `DND_TILE_WORLD_ITEM_PHASE_3_SLICE_3_3_IMPLEMENTATION_MANIFEST_2026-08-24.json`
- Manifest SHA-256: `2e1ed59f9615bc4c97863cb46cbfa9328d35d145f080f48b90b44656c852a296`
- Manifest members: `44` (`25` production, `19` test), sorted unique, exact raw-byte SHA-256 verified with zero mismatches.
- The manifest enumerates the complete governed active `.py`/`.json` member set. Its membership is the 24 frozen pre-resume active paths plus the 20 explicitly authorized active checkpoint paths, excluding all repair-plan exclusions. Rejected candidate hashes were not copied.
- The 20 authorized additions beyond the pre-resume set are: `dnd/blocks/sensory.py`, `tests/architecture/test_content_ledger_boundary.py`, `tests/architecture/test_dependency_boundaries.py`, `tests/engine/test_action_cost_and_position_commit.py`, `tests/engine/test_action_discovery.py`, `tests/engine/test_direct_spatial_effect_materialization.py`, `tests/engine/test_elevated_jump_transaction.py`, `tests/engine/test_elevation_proving_battlefield.py`, `tests/engine/test_event_wire_visibility_contract.py`, `tests/engine/test_items_inventory_equipment.py`, `tests/engine/test_manual_11_grid_tiles_terrain_movement.py`, `tests/engine/test_move_settlement.py`, `tests/engine/test_senses_light_stealth.py`, `tests/engine/test_spatial_effects.py`, `tests/engine/test_traversal_connectors.py`, `tests/engine/test_world_edge_identity_and_elevation.py`, `dnd/spells/evocation.py`, `dnd/spells/necromancy.py`, `tests/manual/test_08_world_model_and_movement.py`, and `tests/manual/test_72_battlefield_deployment_catalog.py`.

Scope excludes Markdown governance, the manifest itself, deprecated/server/editor,
inactive `dnd/items/environment_content.py`, SDK, TypeScript/JavaScript,
declarations/dist/maps, generated transport/presentation, and other excluded
artifacts.

## Collection freeze

Command: the exact active path recorded in the active-runtime ledger, using
`pytest -q -p no:cacheprovider --collect-only` over the 26 active paths and
the single turn-start selector.

Result: exit `0`; `612 tests collected in 9.46s`.

The frozen pre-repair set was reconstructed by removing exactly these five
authorized node IDs from the current set:

1. `tests/engine/test_tile_surface_contract.py::test_move_object_rejects_while_events_are_disabled_without_mutation`
2. `tests/engine/test_grid_pathfinding.py::test_unknown_boundary_collision_records_directed_memory_before_reroute`
3. `tests/engine/test_action_discovery.py::test_caster_origin_preview_obeys_propagation[line]`
4. `tests/engine/test_action_discovery.py::test_caster_origin_preview_obeys_propagation[cone]`
5. `tests/engine/test_action_discovery.py::test_targeted_cylinder_preview_keeps_full_geometry_and_filters_hidden_contacts`

The remaining `607` sorted IDs have SHA-256
`198ed9a575f4cae44e8cb85a954eae779e5a5a085db9670cf129f6c5c7b1102b`, exactly
matching the repair plan. The final `612` sorted IDs use the deterministic
algorithm “sort unique normalized node IDs, join with one newline and one
terminal newline, SHA-256 UTF-8 bytes” and have SHA-256
`44879b5db62038d56191eb427d9c29c9b2f9194a2bae70ac32b1a20a51f03184`.
No selector was removed, renamed, or added beyond those five IDs.

## Test and validation results

All commands used `./.venv/bin/pytest -q -p no:cacheprovider` unless noted.

| Gate | Result | Duration |
|---|---:|---:|
| Sections 1–6 focused public regressions (11 exact selectors) | 11 passed | 5.72s |
| Changed modules: `test_action_discovery.py` + `test_grid_pathfinding.py` | 49 passed | 11.99s |
| Exact 14-module capability lane | 319 passed | 62.51s |
| Section 5/R2 blocker identity selector `test_eb_11_017_forced_movement_and_jump_respect_directional_blockers` | 1 passed | 3.84s |
| `tests/engine/test_spell_families.py` | 62 passed | 28.02s |
| `tests/architecture` | 41 passed | 20.24s |
| Complete active in-process lane | 612 passed | 173.19s |
| Exact active collect-only | 612 collected, exit 0 | 9.67s |
| `py_compile` over all 25 governed production members | exit 0 | — |
| `git diff --check` | exit 0; existing LF/CRLF warnings only | — |

The focused Sections 1–6 command covered the four boundary-side/lifecycle
selectors, the event-disabled move rejection, EB-11-017, unknown-boundary
memory, EB-11-019, and all three public action-discovery selectors.

The complete active lane was:

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

## Scoped Section 14 and dead-residue audit

The active production/test envelope was searched for legacy Tile directional
setters/projections, `blocked_directions`, active `DoorObject`/`build_door`,
no-argument `get_barrier_positions`, dead AoE cache parameters, dynamic-import
cycle masks, edge caches/indexes, and custom serializers. No active-envelope
match required a repair. Matches found only under excluded
`tests/engine/test_encounter_apis.py`, generated icon bindings, or inactive
`dnd/items/environment_content.py` were excluded from this gate.

Dead-plumbing checks found no `_DIRECTION_DELTAS`, `_directional_neighbors`,
`border_snapshots`, `DOOR_DIRECTIONS`/`WALL_DIRECTIONS` in the targeted
battlefield builder, unused shadowcast import, or deleted test-side
`PositionCommitError` imports. Retained matches are intentional: the public
`SpatialChangeEvent`, `SensesUpdateHint.directional_positions`/
`directional_neighbors`/`directional_channels_changed`, observer-owned
`directional_collision_blocked`, core `PositionCommitError` handling, and the
bounded GridMap propagation caches.

The audit did not silently claim global zero residue. The active review residue
remaining outside the repaired R3 obligations includes the authored WEST
constants/helper in `dnd/maps/arena_layout.py`, retained directional hint and
collision-memory fields, and the historical directional wording/selector noted
by the active ledger. These are preserved approved authorities or review items,
not new R3 machinery.

## Exclusions and deferred work

No server/deprecated/editor/SDK/TS/JS/generated transport or inactive
`dnd/items/environment_content.py` file was edited or admitted to the manifest.
No EventQueue schema, reducer, controller, cache/index/registry, facade,
custom serializer, dynamic import, or source-layout gameplay test was added.

Slice 3.4 remains deferred: authored proving cliff behavior and explicit
WallTorch boundary attachment/fixtures. The control-room WallTorch decision is
unresolved and does not block this Slice 3.3 repair certification. This package
does not claim Phase 3 complete.

## Final handoff

Candidate status only; stop for supervisor freeze and independent correctness
and anti-slop review. The ledger SHA-256 is computed externally after this
final write and is intentionally not self-referential.
