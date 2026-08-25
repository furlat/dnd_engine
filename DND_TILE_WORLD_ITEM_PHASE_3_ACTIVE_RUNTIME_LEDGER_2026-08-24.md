# Phase 3 Slice 3.2 active-runtime implementation ledger

Status: APPROVED FOR SLICE 3.3 CLEANUP AND IMPLEMENTATION

Substantive reviewed revision:
`2ce12f873ed468dac893308e90060cf29269c91f87736e2d86f4bc514b1321cc`

This ledger replaces `DND_TILE_WORLD_ITEM_PHASE_3_IMPLEMENTATION_LEDGER_2026-08-24.md`
as the only prospective Slice 3.3 implementation ledger. The old ledger is
historical evidence only.

## 1. Governing scope

Apply `DND_TILE_WORLD_ITEM_ACTIVE_RUNTIME_SCOPE_AMENDMENT_2026-08-24.md`.
Only active in-process Python mechanics and their active tests are governed.
All deprecated server/editor, SDK, TypeScript/JavaScript, generated transport,
and server-only test artifacts are excluded.

Frozen prospective review inputs:

| Artifact | SHA-256 |
|---|---|
| amended master plan | `50411e5575e6336ca0301acf032797cdf1d5ea885df5ccd37d6619f593e7a193` |
| amended Phase 3 guidance | `ed3b4afbe88ab4278c27429b3c9b1727a8ccdc144c3019ab5dcef00ca1715cd0` |
| active-runtime scope amendment | `f10e2fbbcb6ba8732d078f0c4f2f5276716eb51e32c083068f3cae93c9ba52d6` |
| accepted Slice 3.1 manifest | `2501ed3fb35c9b17ad5ef3dcd3bc289ef2145c9ea2ea60ab47164bacba099320` |

## 2. Preserved mechanics decisions

1. `I:EAST` and `J:WEST` are independent Tile-owned side volumes. Equal-height
   occupants on opposing sides are legal; only same-Tile, same-side,
   overlapping occupying bands collide.
2. `WorldEdgeView(I, J)` is ordered: source exit layer, then destination entry
   layer. Reverse lookup shares adjacency identity but swaps layers.
3. Current wall/door/cliff channels are symmetric physical policies. A
   transition must transmit through both ordered layers.
4. Movement may use vertical intervals. OPTICAL and PROPAGATION stay 2D.
5. Ordinary sight and light share OPTICAL topology. Illumination remains
   Tile/source-owned.
6. Objective blocking never depends on whether an observer perceives the
   provider. Subjective boundary contacts use ordered reached-layer evidence.
7. Tile bands plus one GridMap reverse placement dictionary remain the only
   placement authority. No edge registry/cache/index is introduced.
8. Existing EventQueue lifecycle, light callbacks, sensory pre-completion, and
   turn-start/per-step ownership remain unchanged.

## 3. Active production mutation envelope

The complete prospective active production envelope is:

- `dnd/actions/standard.py`;
- `dnd/blocks/base_item.py`;
- `dnd/blocks/sensory.py`;
- `dnd/content/items/authored_item_builders.py`;
- `dnd/content/items/authored_item_definitions.py`;
- `dnd/content/items/environment_item_builders.py`;
- `dnd/content/items/item_catalog.py`;
- `dnd/content/scenarios/battlefield_builders.py`;
- `dnd/content/scenarios/battlefield_definitions.py`;
- `dnd/content/scenarios/scenario_compatibility.py`;
- `dnd/core/aoe.py`;
- `dnd/core/base_block.py`;
- `dnd/core/base_conditions.py`;
- `dnd/core/base_tiles.py`;
- `dnd/core/events/item_events.py`;
- `dnd/core/events/world_events.py`;
- `dnd/core/gridmap.py`;
- `dnd/entities/entity.py`;
- `dnd/items/environment.py`;
- `dnd/items/environment_interactables.py`;
- `dnd/maps/arena_layout.py`;
- `dnd/spatial/area_conditions.py`;
- `dnd/spatial/environmental_conditions.py` only if the generic condition
  capability requires a mechanical port; the current SpikeTrap remains
  default-false for physical optics;
- `dnd/types/items.py`; and
- `dnd/types/world_placement.py`.

`dnd/core/world_edges.py` is reviewed/no edit unless the sole pure ordered
evaluator is deliberately assigned there instead of GridMap. Do not implement
it in both owners.

No path outside this list may be added without stopping for supervisor review.

## 4. Active content crosswalk

- `DirectionalWall`: one object, one explicit side, STONE, extent 2, authored
  current channels.
- Canonical `DirectionalDoor`: one object, one explicit side, WOOD, extent 2;
  closed blocks MOVEMENT/OPTICAL/PROPAGATION and open keeps placement with an
  empty channel tuple.
- Multi-side authored wall/door rows expand before construction into distinct
  UUIDs in NORTH, EAST, SOUTH, WEST order.
- Arena wall/door rows retain explicit WEST.
- Standard battlefield open door retains WEST; opening changes channels only.
- Proving battlefield wall/door rows retain WEST.
- The no-side active `DoorObject` construction family is removed. Active
  maintained callers are reauthored to the canonical door with the exact route
  side proved by active tests.
- `dnd/items/environment_content.py`, its recipe/constants packaging, and its
  tests are inactive in this checkout because they depend on the deleted
  `dnd.content_system`; they are deferred rather than restored or migrated.
  Canonical Phase 3 construction uses the active direct builders under
  `dnd/content/items/` with explicit side data.
- Cliff and WallTorch attachment authorship remain Slice 3.4.
- Deprecated editor/catalog recipes and generated icon rows are not migrated.

Exact active test side facts:

- world-edge source wall at `(0,0)`: EAST;
- opposing destination door at `(1,0)`: WEST;
- senses door at owner `(1,0)` viewed from `(0,0)`: WEST;
- equipment door at owner `(1,0)` viewed from `(0,0)`: WEST;
- active arena/battlefield rows: their authored WEST values; and
- any active caller without maintained side evidence is a STOP, never a
  default or runtime inference.

## 5. Atomic Slice 3.3 work

Land and validate as one hard cut:

1. wall/door placement specs and computed `BoundaryStructure`;
2. active authored/builder/direct caller expansion;
3. active no-side door consolidation;
4. ordered edge mechanics sourced only from current provider structures;
5. movement/FOV/light/propagation consumers using both ordered layers;
6. bounded `get_barrier_positions(footprint)` used only by active AoE and
   Entity action-discovery callers;
7. ordered near-side contact reduction;
8. aggregate channel revision/light/event settlement;
9. condition-owned physical-optics settlement;
10. in-process item/spatial/bootstrap after-value migration; and
11. deletion of active legacy directional authorities and callers.

Cold `rebuild_object_placements` remains event-suppressed and settles local
derived topology/light state atomically before observers/bootstrap.

## 6. Active consumer meanings

- MOVEMENT: traversal/pathfinding/forced movement and movement costs.
- OPTICAL plus `contact.visual`: FOV, light geometry, visible targeting, and
  visual boundary contacts.
- PROPAGATION: line of effect, total-cover/AoE reach, jumps, and other physical
  propagation.
- Typed contact existence: awareness targeting that does not require visual
  contact.

Do not replace these with one generic perceivability or cover policy.

## 7. Active deletion gates

Zero active gameplay references after the cut:

- Tile intrinsic/object-derived directional boolean fields and setters;
- BaseItem directional fields and helpers;
- neutral BaseBlock directional compatibility hooks;
- `ItemDirectionalStructureState` and directional item/event snapshots;
- GridMap directional projection maps/recompute and global barrier cache;
- authored `blocked_directions` defaults/parameters;
- duplicate active `DoorObject` construction/actions/builder/catalog content
  identity;
- no-argument `get_barrier_positions`; and
- object-owned subjective perceivability bypasses.

Searches and tests are scoped to active `dnd/` production and the active test
paths below. Matches under excluded artifacts do not fail these gates.

## 8. Active test mutation and validation envelope

Prospective active test paths:

- `tests/engine/test_tile_surface_contract.py`;
- `tests/engine/test_world_edge_identity_and_elevation.py`;
- `tests/engine/test_senses_light_stealth.py`;
- `tests/engine/test_grid_pathfinding.py`;
- `tests/engine/test_action_discovery.py`;
- `tests/engine/test_elevation_proving_battlefield.py`;
- `tests/engine/test_elevation_performance_contract.py` (validation/no edit);
- `tests/engine/test_spatial_effects.py`;
- `tests/engine/test_direct_spatial_effect_materialization.py`
  (validation/no edit);
- `tests/engine/test_condition_lifecycle.py`;
- `tests/engine/test_event_lifecycle.py` (validation/no edit);
- `tests/engine/test_event_wire_visibility_contract.py`;
- `tests/engine/test_objective_state.py`;
- `tests/engine/test_direct_scenario_deployment.py`;
- `tests/engine/test_items_inventory_equipment.py`;
- `tests/engine/test_spell_families.py`;
- `tests/engine/test_move_settlement.py`;
- `tests/engine/test_action_cost_and_position_commit.py`;
- `tests/engine/test_traversal_connectors.py`;
- `tests/engine/test_elevated_jump_transaction.py`;
- `tests/engine/test_runtime_reset.py` (validation/no edit);
- `tests/engine/test_manual_11_grid_tiles_terrain_movement.py`;
- `tests/architecture/` (complete validation lane, no gameplay-source
  assertions added);
- `tests/manual/test_08_world_model_and_movement.py`;
- `tests/manual/test_37_authored_encounter_mechanics.py` (review/no edit unless
  its canonical door lookup changes); and
- `tests/manual/test_72_battlefield_deployment_catalog.py`;
- `tests/manual/test_17_encounters_turns_controllers.py::test_turn_start_full_senses_refresh_emits_seen_cell_delta`
  (validation/no edit).

Explicitly excluded tests include `test_encounter_apis.py`, server/session/
replication/projection and server/transport/cross-language replay or wire
modules, MapEditor tests, SDK tests, and any module whose maintained subject
requires a removed `server` or `dnd.content_system` dependency. Active
in-process Pydantic event/replay tests remain required.

The following active capabilities currently live inside mixed blocked modules
and must be transplanted into the included collecting modules before the hard
cut; their server/content-system cases remain excluded:

| Mixed source capability | Exact collecting replacement required |
|---|---|
| directional wall is channel-selective and never an action target (`test_directional_environment_legacy_contract.py:97`) | `tests/engine/test_action_discovery.py::test_boundary_wall_is_not_an_action_target_and_preserves_channel_selectivity` |
| door open/change lifecycle plus occupied-close atomic rejection (`test_directional_environment_legacy_contract.py:141`) | `tests/engine/test_items_inventory_equipment.py::test_boundary_door_actions_toggle_one_placed_provider_and_occupied_close_is_atomic` |
| propagation-only boundary removes threat/OA without changing movement or optics (`test_directional_environment_legacy_contract.py:219`) | `tests/engine/test_grid_pathfinding.py::test_propagation_only_boundary_removes_threat_and_opportunity_attack` |
| tutorial/equipment door use-action state (`test_11_equipment_inventory_and_items.py:829`) | extend `tests/engine/test_items_inventory_equipment.py::test_eb_13_009_environment_use_actions_are_stateful_and_spatial` using `build_directional_door(..., boundary_direction=WEST)` |
| newly closed door invalidates a prepared intercept path (`test_legacy_reactive_reaction_coverage.py:916`) | `tests/engine/test_move_settlement.py::test_closed_boundary_door_invalidates_prepared_intercept_path` |
| open door is authoritative for reaction displacement (`test_legacy_reactive_reaction_coverage.py:1029`) | `tests/engine/test_move_settlement.py::test_open_boundary_door_is_authoritative_for_reaction_displacement` |
| two canonical doors discover and toggle independent action state (`test_134_stackable_usable_item_legacy_contract.py:501`) | `tests/engine/test_items_inventory_equipment.py::test_two_boundary_doors_discover_and_toggle_independent_actions` |
| far usable door does not surface an action (`test_134_stackable_usable_item_legacy_contract.py:675`) | `tests/engine/test_action_discovery.py::test_far_boundary_door_does_not_surface_use_action` |

These are behavior migrations, not copies of blocked source structure. They
use active direct builders and public engine commands only; no content-system
or server helper is restored.

Validation must prove public placement/collision, ordered transitions,
channel-selective movement/FOV/light/propagation, near-side contacts, event
ordering, condition optics, bootstrap, replay facts, rollback, and locality.
No private/source-layout gameplay assertions.

## 9. Partial Slice 3.3 recovery rule

Before resuming Luna:

1. compare every changed file after the accepted Slice 3.1 manifest against
   Sections 3 and 8;
2. remove every newly changed excluded file from the Slice 3.3 candidate;
3. review each retained active diff against Sections 2–7;
4. do not assume the stopped partial implementation is correct merely because
   it compiles or one focused module passes; and
5. freeze a new pre-resume active manifest/hash after the cleanup.

The known new excluded deltas are
`deprecated/server_deprecated/event_server.py` and the post-Slice-3.1 changes
to `dnd/items/environment_content.py`. Remove only Luna's Slice 3.3 changes,
restoring each file to its accepted Slice 3.1 state without disturbing older
accepted dirty-worktree edits.

## 10. Final manifest

The final Slice 3.3 manifest contains exact hashes for changed governed active
`.py` and `.json` files only, excluding Markdown governance and the manifest
itself. It contains no deprecated, server, SDK, TypeScript/JavaScript,
declaration, distribution, map, or generated transport artifact.

## 11. Review record

| Review | Revision | Verdict | Notes |
|---|---|---|---|
| Correctness and active capability completeness | `2ce12f873ed468dac893308e90060cf29269c91f87736e2d86f4bc514b1321cc` | APPROVED | active caller/test envelope, baseline, mixed-test replacements, partial recovery |
| Scope/dependency/anti-slop | `2ce12f873ed468dac893308e90060cf29269c91f87736e2d86f4bc514b1321cc` | APPROVED + ANTI-SLOP APPROVED | no hidden transport/content-system dependency, generator, or compatibility layer |
