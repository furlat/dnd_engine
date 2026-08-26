# Phase 5 authored bootstrap implementation ledger

Status: `SLICE_5_0_PREFLIGHT_COMPLETE — READY_FOR_COORDINATOR_REVIEW`

This is the one authorized Slice 5.0 append-only ledger. No production or
test file was edited during this pre-flight. The approved Phase 5 plan remains
unchanged.

## Authority verification

| artifact | SHA-256 | result |
|---|---|---|
| `DND_TILE_WORLD_ITEM_PHASE_5_AUTHORED_BOOTSTRAP_IMPLEMENTATION_PLAN_2026-08-26.md` | `892e07aea27cb777fcb6fda6a7f7415d46bd4825a582d5f6001fb383f4a10870` | exact |
| plan substantive reviewed SHA | `fdfb1584f166960af17f48c626bcf165a16b2436959f5ee6c65c311b649be1fe` | recorded by authority; not a raw file hash claim |
| `DND_TILE_WORLD_ITEM_VERTICAL_BOUNDARY_MIGRATION_PLAN_2026-08-17.md` | `50411e5575e6336ca0301acf032797cdf1d5ea885df5ccd37d6619f593e7a193` | exact |
| `DND_TILE_WORLD_ITEM_ACTIVE_RUNTIME_SCOPE_AMENDMENT_2026-08-24.md` | `f10e2fbbcb6ba8732d078f0c4f2f5276716eb51e32c083068f3cae93c9ba52d6` | exact |
| `DND_TILE_WORLD_ITEM_PHASE_4_IMPLEMENTATION_LEDGER_2026-08-25.md` | `b8f5fb6e1f7aed573900120f5705e561465ad4c45d76eaaf57763f4da2b86395` | exact |
| `DND_TILE_WORLD_ITEM_PHASE_4_IMPLEMENTATION_MANIFEST_2026-08-25.json` | `e66f767412230e0ed9e0c024b1e155d27b581599375ee330d5759dcd498b0d85` | exact |
| `HOW_TO_TEST.MD` | `96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013` | exact |
| `agents.md` | `fcc5dd1e15bae2ff86a7203f42b0c55de4d51dd0d93bc3a3ae059b7e58ee39b1` | exact |

The complete 848-line Phase 5 plan, all 517 lines of `HOW_TO_TEST.MD`, and
`agents.md` were read completely. No revoked or historical plan was used as
authority.

## Accepted Phase 4 baseline

The accepted manifest verification reported 78 sorted unique members: 36
production and 42 active collecting tests, with zero duplicates and zero
current-byte hash mismatches.

The manifest-defined active command was recollected with the frozen path and
selector inputs. Result: `647` nodes, normalized SHA-256
`0062d230c5a85ab1a08eb4ad6ebdf7c75ffed01e99d81b10dba561e9440e9cbe`.

The exact sorted unique node set was executed using newline-delimited pytest
arguments so parametrized node IDs containing spaces remain intact:

```text
printf '%s\n' "$NODES" | xargs -d '\n' .venv/bin/python -m pytest -q -p no:cacheprovider
```

Result: `647 passed in 221.08s (0:03:41)`. The accepted node set and hash are
unchanged. No production or test bytes changed during this baseline run.

## Pre-flight dirty-state snapshot

Immediately before creating this ledger, `git status --short` was exactly:

```text
?? DND_TILE_WORLD_ITEM_PHASE_5_AUTHORED_BOOTSTRAP_IMPLEMENTATION_PLAN_2026-08-26.md
```

That untracked governing plan is preserved. No reset, checkout, clean, commit,
or broad formatting operation was used. After creation, this ledger is the
only additional intended artifact.

## Active authored case inventory

The ten registered active battlefield IDs are `battlefield.standard_hazards_closed`,
`battlefield.open_floor_bright`, `battlefield.standard_hazards_open`,
`battlefield.double_door_dark`, `battlefield.arcane_device_bright`,
`battlefield.reveal_labyrinth_dark`, `battlefield.field_cache_bright`,
`battlefield.multi_object_dark`, `battlefield.open_floor_dark`, and
`battlefield.elevation_proving_ground`.

The corrected read-only catalog probe reset the in-process runtime between
maps and inspected public GridMap state plus the explicitly authorized
read-only Tile registry scan. The total cursor includes the one currently
published `WorldInitializedEvent`; pre-world lifecycle versions are total
minus one:

| map family | total cursor | pre-world versions | current/registered/stale Tiles | connectors | SpikeTraps | WallTorches |
|---|---:|---:|---|---:|---:|---:|
| standard hazards closed | 18 | 17 | 225 / 258 / 33 | 0 | 1 | 2 |
| standard hazards open | 18 | 17 | 225 / 258 / 33 | 0 | 1 | 2 |
| multi-object dark | 22 | 21 | 225 / 258 / 33 | 0 | 1 | 3 |
| elevation proving ground | 90 | 89 | 225 / 235 / 10 | 5 | 1 | 0 |
| open floor bright | 1 | 0 | 225 / 225 / 0 | 0 | 0 | 0 |
| double-door dark | 1 | 0 | 225 / 243 / 18 | 0 | 0 | 0 |
| arcane device bright | 1 | 0 | 225 / 225 / 0 | 0 | 0 | 0 |
| reveal labyrinth dark | 1 | 0 | 225 / 243 / 18 | 0 | 0 | 0 |
| field cache bright | 1 | 0 | 225 / 225 / 0 | 0 | 0 | 0 |
| open floor dark | 1 | 0 | 225 / 225 / 0 | 0 | 0 | 0 |

Dynamic classification is exact: standard closed/open each have one
SpikeTrap, one TrapLever link, and two WallTorches; multi-object dark has one
SpikeTrap, one TrapLever link, and three WallTorches; the proving ground has
one landing SpikeTrap at `(11, 9)`, five connectors, and no WallTorch; and the
other six maps have no authored dynamic condition or light source. There are
seven WallTorch catalog instances total across the three applicable builds,
four SpikeTrap map builds, no direct Tile BaseCondition, and no Entity in a
cold builder.

The first probe attempt used the nonexistent import
`dnd.core.base_item.BaseItem` and stopped before inventory output. It was
corrected to `dnd.blocks.base_item.BaseItem` and completed with the table
above. This was a read-only subprocess error; no repository bytes changed.

## Active caller inventory

The exact production ownership path is `dnd/content/scenarios/battlefield_builders.py::build_battlefield`
(definition line 848), called by `dnd/content/scenarios/scenario_deployment.py::assemble_scenario`
(definition line 369, builder call line 387); `prepare_scenario` is the active
no-start wrapper at lines 459-464. Standard authored dynamic construction is
in `dnd/maps/arena_layout.py::build_standard_arena_environment` (spike line
150, torch line 163). The additional control-room torch is mounted at
`dnd/content/scenarios/battlefield_builders.py:709`. Proving elevation,
connectors, and landing SpikeTrap are at lines 755-759, 763, and 786.

Direct `build_battlefield` test callers are
`tests/manual/test_72_battlefield_deployment_catalog.py:40,45,93,101,150,215`,
`tests/engine/test_direct_scenario_deployment.py:149,186,240`,
`tests/engine/test_elevation_proving_battlefield.py:57,139,264`, and
`tests/engine/test_elevation_performance_contract.py:43,50`.

Active `assemble_scenario`/`prepare_scenario` callers are
`tests/engine/test_elevation_proving_battlefield.py:315`,
`tests/manual/test_37_authored_encounter_mechanics.py:85,188`,
`tests/manual/test_84_generic_roster_duels.py:45`,
`tests/manual/authored_encounter_support.py:54`,
`tests/engine/test_direct_scenario_deployment.py:81,111,125,289,302,330`,
and `tests/manual/test_150_prepared_scenario_lifecycle.py:28`.

Direct generic SpikeTrap materializer tests are retained runtime tests rather
than authored-builder callers: `tests/engine/test_combat_actions.py:824`,
`tests/engine/test_spatial_effect_reveal_idempotency.py`,
`tests/manual/test_spike_zone_movement_legacy_contract.py`,
`tests/manual/test_122_canonical_replication_runtime.py`, and
`tests/manual/test_134_stackable_usable_item_legacy_contract.py`.

## Authorized initial envelope

The expected production envelope from plan Section 9 is exactly:
`dnd/core/gridmap.py`, `dnd/content/spike_trap_materialization.py`,
`dnd/maps/arena_layout.py`, `dnd/content/scenarios/battlefield_builders.py`,
`dnd/core/events/item_events.py`, and `dnd/items/environment_interactables.py`.

The expected active test envelope from Section 8.2 is exactly:
`tests/engine/test_direct_scenario_deployment.py`,
`tests/engine/test_elevation_proving_battlefield.py`,
`tests/engine/test_elevation_performance_contract.py`,
`tests/engine/test_traversal_connectors.py`,
`tests/engine/test_world_edge_identity_and_elevation.py`,
`tests/engine/test_spatial_effects.py`, `tests/engine/test_senses_light_stealth.py`,
`tests/engine/test_objective_state.py`,
`tests/engine/test_event_wire_visibility_contract.py`,
`tests/engine/test_tile_surface_contract.py`,
`tests/engine/test_items_inventory_equipment.py`,
`tests/manual/test_72_battlefield_deployment_catalog.py`,
`tests/manual/test_37_authored_encounter_mechanics.py`,
`tests/manual/test_84_generic_roster_duels.py`, and
`tests/manual/test_150_prepared_scenario_lifecycle.py`.

A dedicated authored-bootstrap behavioral module may be added only if the
approved proofs require it. No test edit or new test node is made in Slice
5.0. `scenario_deployment.py`, `base_item.py`, `torches.py`, and
`world_events.py` remain stop-only optional surfaces; no expansion is
requested now.

## Governed exclusions

Excluded are `server/**`, `deprecated/**`, SDK, TypeScript/JavaScript,
generated wire contracts, transports, sessions, APIs, editor, renderer,
pygame assets, source maps, cross-language fixtures, inactive
`dnd.content_system`, blocked tests, generic EventQueue mute/replay/registry/
manager/controller/service/receipt/callback frameworks, dynamic condition or
light snapshot schemas unused by active maps, generic Tile retirement, Phase 6
hard-cut certification, and unrelated cleanup or content expansion.

`tests/manual/authored_encounter_support.py` feeds excluded server/content-
system consumers as well as active tests; excluded consumers are not migrated.
The six non-collecting files excluded from the accepted Phase 4 manifest remain
governed residue and are not part of the Phase 5 active envelope:
`tests/engine/test_dice_event_semantics.py`,
`tests/manual/test_09_action_discovery_and_costs.py`,
`tests/manual/test_11_equipment_inventory_and_items.py`,
`tests/manual/test_20_content_extension_basics.py`,
`tests/manual/test_21_spell_and_feature_extensions.py`, and
`tests/manual/test_103_game_summary_store.py`.

## Slice 5.0 checkpoint

No authority, accepted baseline, or active authored classification differed
materially from the approved Phase 5 plan. No production or test edit was
made. The only write authorized in this slice is this new ledger:
`DND_TILE_WORLD_ITEM_PHASE_5_IMPLEMENTATION_LEDGER_2026-08-26.md`.

Stop here before Slice 5.1. Status: `READY_FOR_COORDINATOR_REVIEW`.

## Slice 5.1 checkpoint — cold-build boundary and identity hard cut

The approved Slice 5.1 implementation changed only these nine repository
files, all inside the predeclared envelope:

- `dnd/content/scenarios/battlefield_builders.py`
- `dnd/content/spike_trap_materialization.py`
- `dnd/core/events/item_events.py`
- `dnd/core/gridmap.py`
- `dnd/items/environment_interactables.py`
- `dnd/maps/arena_layout.py`
- `tests/engine/test_direct_scenario_deployment.py`
- `tests/engine/test_elevation_performance_contract.py`
- `tests/engine/test_elevation_proving_battlefield.py`

`build_battlefield` now resolves the definition and builder before the
pre-mutation admission checks. It rejects a nonzero EventQueue cursor, any
current Tiles, object placements, connectors, or SpatialConditions, and any
registered Tile found by the one authorized read-only filtered
`BaseBlock._registry` scan. Rejection occurs before `GridMap.disable_events`.
The cold builder creates the complete unregistered `WorldInitializedEvent`
inside the disabled construction guard, validates it, re-enables with
`flush_pending=False`, and publishes that one retained existing world fact.
No post-initialization SpikeTrap or WallTorch setup was added in this slice;
retaining the existing final world publication is the minimal executable
checkpoint for the existing public scenario/event consumers, with no second
publication path.

The standard terrain helper now creates authored water, difficult, and stone
Tiles once at their final coordinates. The proving helper creates the final
gap, support heights, progressive surface kinds, and slope axes in those
same first Tile identities. Both barrier helpers no longer replace their
support Tiles. `register_connector` has only the initial-registration direct
commit branch while events are disabled; enabled registration and all
replacement/toggle/removal paths retain their existing guarded lifecycles.

Standard and proving builders reserve SpikeTrap UUIDs without constructing or
registering conditions. Standard TrapLevers retain their future UUID link;
proving retains `object_uuids["landing_hazard"]`. `materialize_spike_trap_condition`
accepts and forwards an optional exact UUID through the existing materializer.
`ItemState` has only the optional `linked_spatial_condition_uuid` field, and
`TrapLever.to_item_state` derives one target from its PullLeverAction template,
rejecting multiple distinct non-null targets. Every authored WallTorch is
mounted unlit.

The content-local cold invariant checks the EventQueue cursor, exact current
Tile positions, the filtered registered UUID-to-Tile object mapping, the
world-event UUID-to-position rows, direct/spatial condition absence, empty
Tile entity membership, object placement/item closure, connector closure,
reserved SpikeTrap identity/footprint coherence, and the known authored
WallTorch classification (`is_lit=False` with no attached source). It does not
inspect a private GridMap light-source map and does not add a light
enumeration API.

The first focused run exposed three stale public expectations from the
pre-cut behavior: the elevation performance test expected runtime elevation
mutator calls, the proving cold test expected a live landing SpikeTrap, and
the world snapshot test expected lit cold torches. Those existing test nodes
were repaired to assert final-Tile-once construction, reserved-but-not-live
SpikeTrap identity, and unlit cold WallTorch state. The admission proof was
also strengthened to make a second public `open_floor_dark` call after
`open_floor_bright` and compare the unchanged event stream, current Tile
identity map, filtered registered Tile identity map, empty object/connector/
SpatialCondition projection, and WorldInitialized projection. No private
registry inspection was added outside that explicit Tile-authority proof.

### Exact Slice 5.1 validation

Final focused command:

```text
./.venv/bin/pytest -q \
  tests/engine/test_direct_scenario_deployment.py::test_real_world_initialized_fact_keeps_surface_and_object_identity \
  tests/engine/test_direct_scenario_deployment.py::test_world_initialized_round_trip_preserves_cliff_and_wall_torch_boundary_state \
  tests/engine/test_elevation_performance_contract.py::test_battlefield_composition_work_tracks_authored_elevation_cells \
  tests/engine/test_elevation_proving_battlefield.py::test_elevation_proving_battlefield_cold_layout_matches_runtime \
  tests/engine/test_elevation_proving_battlefield.py::test_elevation_proving_battlefield_exercises_ordered_edge_rules \
  tests/engine/test_traversal_connectors.py::test_connector_runtime_uuid_is_not_cold_authored_identity \
  tests/engine/test_traversal_connectors.py::test_gridmap_connector_registry_indexes_lifecycle_and_clear \
  tests/engine/test_tile_surface_contract.py::test_phase_one_public_values_expose_strict_json_schemas \
  tests/engine/test_tile_surface_contract.py::test_world_initialized_round_trip_rebuilds_opposing_boundary_placements \
  tests/engine/test_tile_surface_contract.py::test_active_tile_factories_have_explicit_semantic_surfaces \
  tests/manual/test_72_battlefield_deployment_catalog.py::test_battlefield_catalog_has_ten_exact_mechanical_states \
  tests/manual/test_72_battlefield_deployment_catalog.py::test_battlefield_layouts_retain_terrain_barriers_and_objects \
  tests/manual/test_72_battlefield_deployment_catalog.py::test_every_battlefield_has_one_builder_and_layout_matches_runtime \
  tests/manual/test_72_battlefield_deployment_catalog.py::test_battlefield_contract_is_renderer_neutral
```

Result: `14 passed in 8.53s`.

The exact-UUID materializer smoke proof used the public reset, Tile creation,
and `materialize_spike_trap_condition(..., condition_uuid=...)` seam and
returned `exact condition UUID materialization: PASS`.

All ten authored catalog cases were independently probed after reset. Each
emitted exactly one completed `WorldInitializedEvent`, had 225 current Tiles,
zero active SpatialConditions, and zero cold light sources by the public
WallTorch classification. The object/connector counts were:

| battlefield | objects | connectors | wall torches |
|---|---:|---:|---:|
| standard_hazards_closed | 14 | 0 | 2 |
| open_floor_bright | 0 | 0 | 0 |
| standard_hazards_open | 14 | 0 | 2 |
| double_door_dark | 18 | 0 | 0 |
| arcane_device_bright | 2 | 0 | 0 |
| reveal_labyrinth_dark | 18 | 0 | 0 |
| field_cache_bright | 1 | 0 | 0 |
| multi_object_dark | 17 | 0 | 3 |
| open_floor_dark | 0 | 0 | 0 |
| elevation_proving_ground | 10 | 5 | 0 |

Changed active Python files were compiled with:

```text
./.venv/bin/python -m compileall -q [the nine changed Python files]
```

Result: `PASS`. `git diff --check` result: `PASS`. The scoped changed-path
comparison found no unauthorized active `dnd/` or `tests/` path. The bounded
forbidden-authored-call scan found no `materialize_spike_trap_condition`,
`set_tile_elevation`, or `lit=True` use in the authored builder/layout
surfaces. The remaining `grid.set_tile` call is the single final-Tile install
inside the authored floor helper; neither barrier helper contains a support
replacement.

No Slice 5.1 production/test failure remains. The accepted 647-node baseline,
full Phase 5 manifest, dynamic SpikeTrap activation, WallTorch lighting, and
post-light item-location certification remain intentionally unrun and
unimplemented for the later approved slices. No excluded file changed.

Status: `READY_FOR_COORDINATOR_REVIEW` before Slice 5.2.

## Exact Slice 5.2 checkpoint — initialization and ordinary dynamic setup

Slice 5.2 was implemented under the approved plan SHA
`892e07aea27cb777fcb6fda6a7f7415d46bd4825a582d5f6001fb383f4a10870`.
The Slice 5.1 acceptance ledger state was preserved; this checkpoint adds the
post-initialization setup and updates the affected public proofs. No Slice 5.3
certification, 647-node union, or final manifest was run or created.

### Production sequence and bounded failure behavior

`build_battlefield` still constructs and validates the complete unregistered
`WorldInitializedEvent` inside the disabled cold-build guard. It re-enables
GridMap with `flush_pending=False`, publishes that exact event as the first
stored fact, and retains the returned completion event for the authored torch
causal parent. After publication it materializes each reserved SpikeTrap with
the existing `materialize_spike_trap_condition` root lifecycle, passing the
reserved UUID and exact footprint but no world-event parent. Thus the ordinary
BASE_ACTION root phases remain present after `WorldInitializedEvent`.

Standard closed/open and multi-object builds use their reserved environment
UUID and `SPIKE_ZONE_POSITIONS`; the proving build uses
`object_uuids["landing_hazard"]` and `{(11, 9)}`. Each returned condition is
checked against the exact reserved UUID and public `BaseCondition.get` identity.

Placed WallTorches are collected from exact public object-placement rows and
sorted by `(placement.position, object_uuid)`. Each call records the public
EventQueue cursor, invokes the existing `light()` once, and inspects only
`iter_events_since(cursor)`. One-pass `(index, event)` pairs require a
completed, uncanceled `SPATIAL_LIGHT_CHANGED` before the exact completed
`IGNITE` interaction for that torch. Only then is the existing floor
`ItemLocationStateEvent` published with the unchanged placement and completed
IGNITE parent. Missing/canceled lifecycles raise a post-initialization setup
error before that torch's item after-value; the published world fact and any
partial dynamic history remain, with reset required by the existing terminal
failure rule. No torch/event/queue API, callback, source registry, or rollback
path was added.

Slice 5.2 code/test edits were limited to:

- `dnd/content/scenarios/battlefield_builders.py`;
- `tests/engine/test_direct_scenario_deployment.py`;
- `tests/engine/test_elevation_proving_battlefield.py`; and
- `tests/manual/test_72_battlefield_deployment_catalog.py`.

### Public proof coverage

The ten-battlefield catalog proof now checks that every build starts with one
completed `WorldInitializedEvent`, has exactly one such event, classifies the
reserved standard/proving condition and exact footprint when present, has no
dynamic condition otherwise, and verifies every placed torch's completed
light-change-before-IGNITE order, lit public state, exact floor placement, and
one complete item after-value. The direct scenario proof now verifies the cold
world row remains unlit while the live torch is lit, the reserved condition is
live with its exact footprint, the TrapLever link remains exact, and the item
after-value is parented to the completed IGNITE fact. The proving layout proof
now distinguishes the cold world fact from the post-world landing condition.

The detached public projection proof reduces the cold world Tile light/item
rows and subsequent completed SpatialEffectChange, SPATIAL_LIGHT_CHANGED, and
ItemLocationState facts, then compares the resulting condition identity and
footprint, resolved light map, and item states with the live GridMap/BaseItem
state. Two parameterized public EventQueue-handler proofs cancel light-change
and IGNITE declaration lifecycles separately; both prove the world completion
remains, cancellation is recorded, the builder raises, and no failed torch
item after-value is published. No mock, call-count assertion, private light
map, or source-layout gameplay assertion was added.

### Exact Slice 5.2 validation

Focused chronology/rebuild/cancellation proof command:

```text
./.venv/bin/pytest -q \
  tests/engine/test_direct_scenario_deployment.py::test_authored_dynamic_setup_rejects_public_lifecycle_cancellation \
  tests/engine/test_direct_scenario_deployment.py::test_world_initialized_round_trip_preserves_cliff_and_wall_torch_boundary_state \
  tests/engine/test_elevation_proving_battlefield.py::test_elevation_proving_battlefield_cold_layout_matches_runtime \
  tests/engine/test_direct_scenario_deployment.py::test_world_birth_and_deployment_are_ordered_event_facts
```

Result: `5 passed in 6.09s` (the parameterized cancellation node accounts for
the two cases).

The authored direct/catalog rerun:

```text
./.venv/bin/pytest -q tests/engine/test_direct_scenario_deployment.py \
  tests/manual/test_72_battlefield_deployment_catalog.py
```

Result: `55 passed in 34.49s`.

The detached projection selector passed: `1 passed in 4.79s`.

The affected capability command was:

```text
./.venv/bin/pytest -q \
  tests/engine/test_traversal_connectors.py \
  tests/engine/test_world_edge_identity_and_elevation.py \
  tests/engine/test_spatial_effects.py \
  tests/engine/test_senses_light_stealth.py \
  tests/engine/test_objective_state.py \
  tests/engine/test_event_wire_visibility_contract.py \
  tests/engine/test_items_inventory_equipment.py \
  tests/manual/test_37_authored_encounter_mechanics.py \
  tests/manual/test_84_generic_roster_duels.py \
  tests/manual/test_150_prepared_scenario_lifecycle.py
```

Result: `253 passed in 81.63s`.

The initial Slice 5.2 affected authored/elevation/catalog command over the
five directly affected modules returned `102 passed in 42.92s`; the final
direct/catalog rerun above includes the new proof nodes. Architecture returned
`41 passed in 23.63s`.

Changed active Python compilation passed for all ten currently changed Python
files. Scoped `git diff --check` passed. The current active diff contains only
the six authorized Slice 5.1 production files plus the four Slice 5.2-affected
test/builder paths listed above; no excluded server, SDK, transport, generated,
renderer, editor, or cross-language path changed. Private light-source access
in the new tests is absent. Dependency gates passed: GridMap has no Entity,
concrete item, or SpatialCondition import; Entity has no `dnd.spatial` import;
core event modules import none of GridMap, Entity, Senses, authored content, or
renderer. The authored pre-init path contains no dynamic setup call; the only
SpikeTrap materializer call is the post-world helper described above.

No failure or repair remains in this checkpoint. The accepted Phase 4/5.0
baseline and Slice 5.1 results remain historical; the full 647-node Phase 5.3
union, final manifest, and certification gates were intentionally not run.

Status: `READY_FOR_COORDINATOR_REVIEW` before Slice 5.3.


## Slice 5.2 proof-repair checkpoint — authored link and scenario sensory order

This test-only repair remained within Slice 5.2. No production file changed.

The standard authored lever proof now requires one public `PullLeverAction`
template and asserts that its runtime `trap_condition_uuid`, the cold
`ItemState.linked_spatial_condition_uuid`,
`StandardArenaObjects.spike_condition_uuid`, and the live materialized
condition UUID are one identical value.

`test_world_birth_and_deployment_are_ordered_event_facts` now identifies the
authored SpikeTrap and WallTorch UUIDs from the public WorldInitialized rows and
proves every authored condition, light, IGNITE, and WallTorch item after-value
fact occurs after the single completed WorldInitialized fact and before the
first EntityCreated fact. For every assembled Entity it proves the EntityCreated
fact precedes that Entity's one initial ENTERED lineage, the ENTERED EFFECT
causes exactly one public `SELF_MOVEMENT` SensoryUpdate before ENTERED
COMPLETION when the projection changes, and the causal parent is the ENTERED
EFFECT. All completed SensoryUpdateEvent deltas for each observer are applied to
a fresh public `Senses` value with `apply_sensory_update`; its replay-owned
perception fields from `capture_senses_snapshot` match the live observer. The
derived navigation-dirty flag is intentionally not treated as a perception
field.

The first three-selector attempt was `2 passed, 1 failed`: the new order proof
initially overmatched later entity setup events by event type alone. The bounded
repair keyed the authored facts to the frozen public condition and WallTorch
identities. No implementation behavior was changed. The anti-slop repair also
hoisted the local perception projection helper outside the Entity loop.

Exact corrected proof command:

```text
./.venv/bin/pytest -q \
  tests/engine/test_direct_scenario_deployment.py::test_world_birth_and_deployment_are_ordered_event_facts \
  tests/engine/test_direct_scenario_deployment.py::test_world_initialized_round_trip_preserves_cliff_and_wall_torch_boundary_state \
  tests/engine/test_senses_light_stealth.py::test_supported_deployment_emits_one_empty_to_full_delta
```

Result: `3 passed in 5.85s`.

Exact affected rerun:

```text
./.venv/bin/pytest -q \
  tests/engine/test_direct_scenario_deployment.py \
  tests/engine/test_senses_light_stealth.py::test_supported_deployment_emits_one_empty_to_full_delta
```

Result: `50 passed in 27.28s`.

The changed direct scenario test compiled successfully with `compileall`,
`git diff --check` passed, and the public-test scan found no private light-map
access, mocks, or monkeypatching. The active changed-path set remains within
the accepted Slice 5.1/5.2 envelope; no excluded path changed.

Status: `READY_FOR_COORDINATOR_REVIEW` before Slice 5.3.
## Slice 5.3 final certification — candidate frozen for independent review

This is the final physical ledger section for the Phase 5 candidate. The
bounded anti-slop recertification changed only the authorized cold-world
validator and elevation correctness test; no other production/test or
excluded-surface bytes changed. The accepted governing Phase 5 plan remains
`892e07aea27cb777fcb6fda6a7f7415d46bd4825a582d5f6001fb383f4a10870`.
The reverified HOW_TO_TEST.MD SHA is
`96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013`, the
accepted Phase 4 completion ledger SHA is
`b8f5fb6e1f7aed573900120f5705e561465ad4c45d76eaaf57763f4da2b86395`, and
the accepted Phase 4 manifest SHA is
`e66f767412230e0ed9e0c024b1e155d27b581599375ee330d5759dcd498b0d85`.
The master SHA is
`50411e5575e6336ca0301acf032797cdf1d5ea885df5ccd37d6619f593e7a193` and
the active-runtime scope amendment SHA is
`f10e2fbbcb6ba8732d078f0c4f2f5276716eb51e32c083068f3cae93c9ba52d6`.

### Bounded anti-slop repair

The rejected candidate had two bounded defects. `_validate_cold_world`
recomputed spike positions and accepted a subset; it now computes the
authored spike-position set once, requires exact standard
`SPIKE_ZONE_POSITIONS` or exact proving `{(11, 9)}` identity, rejects authored
spike positions without a reserved identity, and requires the reserved set to
be contained in the current Tile-position set. The reserved UUID-not-live and
post-world materialization behavior is unchanged.

The elevation composition test is now named
`test_final_tiles_preserve_authored_elevation_and_identity` and proves
final-Tile identity/elevation correctness without wall-clock measurements or
nonnegative elapsed-time assertions. The locality gate uses only the public
entity map-size invariant selector, the cold/warm action-discovery bounded
pathfinder-call selector, and both parameterized local-edge path-call cases.

The focused cold-boundary/direct-scenario/elevation/catalog command returned
`67 passed in 40.75s`. The exact locality group returned `4 passed in 6.15s`.
No test failure or further repair occurred after these bounded changes.

### Active node set and execution

The accepted Phase 3 semantic baseline remains 614 nodes with normalized
SHA-256 `774c745d442d5db6b8bfb2878309b4eae118e08d264ae4a12370f2a21db05641`.
The accepted Phase 4 candidate remains 647 nodes with normalized SHA-256
`0062d230c5a85ab1a08eb4ad6ebdf7c75ffed01e99d81b10dba561e9440e9cbe`.
The accepted Phase 4 path-input union plus the authorized Phase 5 additions
collected 650 unique nodes. The three additional Phase 5 node IDs remain:

- `tests/engine/test_direct_scenario_deployment.py::test_authored_dynamic_setup_rejects_public_lifecycle_cancellation[ignite]`
- `tests/engine/test_direct_scenario_deployment.py::test_authored_dynamic_setup_rejects_public_lifecycle_cancellation[light-change]`
- `tests/engine/test_direct_scenario_deployment.py::test_cold_world_plus_dynamic_facts_reproduces_live_authored_state`

The renamed elevation correctness node replaces the former path-owned
characterization node without changing the count:

- removed: `tests/engine/test_elevation_performance_contract.py::test_battlefield_composition_work_tracks_authored_elevation_cells`
- replacement: `tests/engine/test_elevation_performance_contract.py::test_final_tiles_preserve_authored_elevation_and_identity`

The exact newline-safe algorithm was: collect the accepted Phase 4
`frozen_path_inputs` plus `outside_path_selector_inputs` with
`.venv/bin/pytest --collect-only -q -p no:cacheprovider`; retain node lines
containing `::`, sort and deduplicate them, join with a terminal newline, and
hash the UTF-8 bytes. The final count is 650 and the normalized SHA-256 is
`8202c5f659be52244112818848d40d01f2a358adf3cce17200ccd075e172c2e6`.
Executing that exact sorted node set returned:
`650 passed in 217.62s (0:03:37)`.

### Certification gates

The exact changed active Python compilation command covered all ten governed
changed Python files and returned exit 0. Scoped `git diff --check` returned
exit 0 (only Git's LF-to-CRLF working-copy warnings were emitted). The
complete architecture command returned `41 passed in 24.87s`. The explicit
locality/bounded-work selectors returned `4 passed in 6.15s` for public
map-size-invariant entity lookup, bounded cold/warm action discovery, and the
two parameterized local-edge path-call cases. The exact 650-node union above covers the
focused cold-boundary, final-Tile identity/elevation, connector, spike/lever,
object-placement, catalog, dynamic chronology/cancellation, event, light,
FOV, senses, spatial-condition, spell, item, scenario, reset, Banishment, and
monster-trait lanes required for this slice.

Dependency direction passed: GridMap has no Entity, concrete-item, or
SpatialCondition import; Entity has no `dnd.spatial` import; core event
modules import none of GridMap, Entity, Senses, authored content, or renderer.
The active hard-cut scan is clean; the sole match is the governed excluded
legacy residue `tests/engine/test_dice_event_semantics.py:100`, outside the
active collecting scope. The no-private-light scan is clean: the builder and
tests use only public attached-light queries, with no `_light_sources`
inspection. The cold-boundary, stale-Tile-identity, no-pre-world-dynamic-
construction, and bounded locality gates are green through the exact union
and the public locality selectors. No compatibility facade, manager, replay
framework, callback/event detour, or excluded-surface change was introduced.

The historical Slice 5.2 proof repair remains recorded above: the exact
runtime lever target UUID was added to the cold/runtime link proof; the
scenario chronology proof now checks authored setup facts, EntityCreated and
ENTERED ordering, SELF_MOVEMENT causality, and replayed public Senses fields;
the local projection helper was hoisted outside the Entity loop. The repaired
direct scenario/senses selectors returned `3 passed in 5.85s`, and the
affected direct scenario plus senses selector returned `50 passed in 27.28s`.
The current certification includes the bounded anti-slop repair recorded
above; no failure occurred after its repair.

### Final manifest and scope

The single final manifest is
`DND_TILE_WORLD_ITEM_PHASE_5_IMPLEMENTATION_MANIFEST_2026-08-26.json` with
raw-byte SHA-256
`c10171e9e64ea96ca93f0b971917aad1824654d950a82bed1b7cb516cbef70b1`.
It contains exactly 80 sorted unique governed active members: 37 production
and 43 active collecting test files. Every member exists and has the recorded
current raw-byte SHA; verification found zero duplicates, zero missing
members, zero extra members, and zero hash mismatches. The two Phase 5 paths
new beyond the accepted Phase 4 manifest are
`dnd/content/spike_trap_materialization.py` and
`tests/engine/test_elevation_performance_contract.py`; the remaining eight
Phase 5 changed paths are existing accepted members. The manifest records the
full path-input/selector metadata, node accounting, authority hashes, scope
exclusions, and status `READY_FOR_INDEPENDENT_REVIEW`.

The exact authorized changed path set is:
`dnd/content/scenarios/battlefield_builders.py`,
`dnd/content/spike_trap_materialization.py`, `dnd/core/events/item_events.py`,
`dnd/core/gridmap.py`, `dnd/items/environment_interactables.py`,
`dnd/maps/arena_layout.py`,
`tests/engine/test_direct_scenario_deployment.py`,
`tests/engine/test_elevation_performance_contract.py`,
`tests/engine/test_elevation_proving_battlefield.py`, and
`tests/manual/test_72_battlefield_deployment_catalog.py`.

The three untracked governance artifacts are the approved Phase 5 plan, this
ledger, and the final Phase 5 manifest; none is a governed active
production/test manifest member. No server, deprecated-server, SDK,
transport, generated, renderer, editor, cross-language, inactive
content-system, or unrelated dirty path changed.

Final status: `READY_FOR_INDEPENDENT_REVIEW`.

## Phase 5 final acceptance

Both independent implementation reviews approved this exact candidate. The
correctness/replay/scope verdict is `APPROVED`, including the independent
650-node pass and 14 active caller tests. The anti-slop/dependency/locality
verdict is `APPROVED`, including closure of the exact footprint and
timing-theater findings.

Authority and frozen-candidate records:

- Phase 5 plan SHA-256: `892e07aea27cb777fcb6fda6a7f7415d46bd4825a582d5f6001fb383f4a10870`
- Final manifest SHA-256: `c10171e9e64ea96ca93f0b971917aad1824654d950a82bed1b7cb516cbef70b1`
- Pre-review ledger SHA-256: `b958f6afddd0b865577ce2604fc9096dd9b543355ec9e09a3923705e41910b66`
- Node set: 650; normalized SHA-256 `8202c5f659be52244112818848d40d01f2a358adf3cce17200ccd075e172c2e6`
- Coordinator independent result: `650 passed in 227.38s`

No production, test, plan, or manifest bytes were changed for finalization, and
no tests were rerun. Phase 6 does not begin automatically.

Final status: `PHASE_5_COMPLETE — ACCEPTED`.
