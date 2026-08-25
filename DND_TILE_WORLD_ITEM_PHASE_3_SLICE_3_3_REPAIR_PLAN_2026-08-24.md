# Phase 3 Slice 3.3 bounded repair plan

Status: DRAFT FOR INDEPENDENT REVIEW. NOT IMPLEMENTATION AUTHORITY.

This repair plan is bound to the rejected Slice 3.3 candidate:

- implementation manifest: `cbb26f3106e2b70418cafbd0077c3a735cc69e9e36c20e58885346dce94ce692`;
- certification ledger: `2ff1f863efcf3eda2c8dc826898e8a8c9fc329982dd36cf8c3091fa357aa4051`;
- master plan: `50411e5575e6336ca0301acf032797cdf1d5ea885df5ccd37d6619f593e7a193`;
- Phase 3 guidance: `ed3b4afbe88ab4278c27429b3c9b1727a8ccdc144c3019ab5dcef00ca1715cd0`;
- active-runtime amendment: `f10e2fbbcb6ba8732d078f0c4f2f5276716eb51e32c083068f3cae93c9ba52d6`;
- active-runtime ledger: `63e25aac3f0136daa8d43b860c328fe8b7b9f26529f65792b123dc77293c059a`.
- accepted Slice 3.1 manifest: `2501ed3fb35c9b17ad5ef3dcd3bc289ef2145c9ea2ea60ab47164bacba099320`;
- pre-resume Slice 3.3 manifest: `c39258b83b911792d44dca3a2600e209b30bd5f76ded2778dfed2b676141c507`.

It corrects only independently reproduced Slice 3.3 defects and dead residue.
It does not reopen the approved geometry, add Slice 3.4 cliff/WallTorch work,
or enter excluded server, editor, SDK, generated transport, or inactive
content-system files.

## 1. Exact authority separation

1. `WorldEdgeView` derives structural contributions only from the source
   Tile's exact facing boundary band and the destination Tile's exact opposing
   boundary band. It never reads center bands and never asks a center placement
   for `BoundaryStructure`.
2. Whole-cell walking, optical, propagation, and blocker queries read only
   center placements through the existing center query. Boundary placements
   participate only through the ordered transition evaluator.
3. Cold rebuild resolves `get_boundary_structure()` only for boundary
   placements.
4. Runtime `DirectionalWall` and `DirectionalDoor` no longer store a
   `boundary_direction`. Authored definitions/local construction rows retain
   side input, and committed `WorldObjectPlacement` is the only runtime side
   authority. Direct wall/door builders no longer accept or return a duplicate
   side; their callers pass the authored/local side directly to
   `GridMap.place_object()`.
5. Do not add a validation alias, runtime mirror, provider adapter, or fallback
   from center mechanics to boundary mechanics.

Public proofs:

- a center object whose neutral test provider can return a boundary structure
  does not affect any adjacent edge;
- a boundary object does not become a whole-cell center blocker;
- an exact-side provider affects only its placed side;
- an object can be placed on a side different from a construction-time local
  variable without any contradictory item-side field because no such runtime
  field exists.

## 2. One provider resolution and bounded rollback

1. Before each placement, move, orientation, removal, door-state, or cold
   rebuild commit, resolve every affected boundary provider value exactly once.
2. The override map is `UUID -> BoundaryStructure | None`; key membership is
   authoritative even when the value is `None`. A nonstructural attachment is
   never resolved again because its precomputed value is `None`.
3. Before/after ordered views reuse those exact values. Do not perform a second
   provider lookup after local bands/reverse placement have committed.
4. Keep the complete post-commit derivation inside the existing bounded
   rollback window. A provider exception restores bands, reverse placement,
   item state when applicable, revisions, local light contributions, and event
   cursor. Derived caches may be cleared.
5. Terminal removal retains its already accepted one-shot terminal-hook
   behavior; do not invent an EventQueue transaction.

Public proofs:

- a nonstructural boundary attachment resolves once on runtime placement and
  once on cold rebuild, with `None` retained as the authoritative result;
- an opposing-side sibling that throws during candidate derivation leaves the
  target placement, both local bands, revisions, resolved light, and event
  cursor unchanged;
- place, move, and orient preserve the existing public failure-atomicity
  contract without a private failure-injection seam.

## 3. Relocation lifecycle and settlement

Preserve the governing departure-then-arrival lifecycle. The repair must not
batch the two facts or assign the final topology delta to departure.

1. Preflight the entire move before mutation: candidate/admission, every
   provider value, local rollback state, and both affected endpoint sets. Any
   failure leaves the old placement intact and publishes nothing.
2. Remove the old bands and reverse-placement row. Derive the intermediate
   state with the object absent from both positions.
3. Compare pre-move to intermediate aggregate answers, bump each changed
   revision once, and fire the complete departure lifecycle. At departure
   declaration, `get_object_placement()` is `None`; old membership is absent,
   new membership is not installed, `previous_placement` is old, the existing
   relocation-destination field names the candidate position, and current
   placement/structure after-values are `None`. The declaration light callback
   causally settles the intermediate topology before EFFECT. Attached lights
   and object anchors remain at the old coordinate; relocation-aware anchors
   do not retire, and terminal-removal cleanup does not run. Spatial senses
   skips departure reduction.
4. Only after departure completes, install the already-admitted new bands and
   reverse-placement row. Derive the final state, compare intermediate to
   final answers, and bump each changed revision once.
5. Fire the complete arrival lifecycle with committed placement/current
   structure and `previous_placement=old`. Its declaration light callback
   settles final topology. Object-anchored conditions relocate during EFFECT;
   their condition-owned optics settle before their completed footprint fact.
   Existing ordinary attached-light settlement then runs at arrival
   pre-completion, followed by exactly one spatial-senses reduction using the
   old/new affected-position union.
6. Both lifecycles keep the shared outer parent and their existing order. A
   move may legitimately produce two revision/light settlements: old to
   absent, then absent to new. No batch event, callback family, receipt, or
   EventQueue change is allowed.
7. A failure before the departure fact restores the original
   placement/topology/light and emits no surviving fact. The post-departure
   installation path is prevalidated and must contain no newly fallible
   provider/admission work.
8. Runtime `move_object()` rejects before mutation when spatial event
   publication is disabled. Cold/load relocation uses
   `rebuild_object_placements()` and is finalized by the sole
   `WorldInitializedEvent`; queued two-phase relocation is forbidden.

Public lifecycle observers must prove the exact intermediate departure state
and complete final arrival state above. A separate public proof requires
event-disabled rejection to preserve placement, bands, revisions, light, and
event cursor.

## 4. Subjective movement and collision memory

1. Objective movement, optics, light, and propagation always include every
   boundary provider.
2. Only the existing subjective movement query may omit a boundary provider
   absent from the requester's typed `Senses.objects` contacts.
3. Existing directed collision memory is applied before that subjective
   result. On the first attempted crossing of an unknown objective boundary,
   movement fails objectively, publishes the existing collision/reveal fact,
   and records the directed transition. Later subjective routing rejects that
   remembered transition even while the object remains otherwise unknown.
4. Center collision memory remains separate. Do not add an object-owned
   perceivability hook, generic policy object, or second contact schema.

Public proof: an invisible/unknown movement wall is absent from contacts; the
first subjective route considers the edge possible, the objective attempt
fails and records directed memory, and the later subjective route blocks it.

## 5. Ordered blocker identity

1. Extend the existing blocker query with the transition source and make it
   the single complete transition-decision plus blocker-identity query for the
   four active caller pairs: `dnd/actions/standard.py` at the current
   `4443/4445` and `4632/4638` pairs, `dnd/spells/necromancy.py` at the current
   `1250/1252` pair, and `dnd/spells/evocation.py` at the current `1231/1233`
   pair. It returns `None` when the transition is admissible and must not call
   `can_transition()` and then derive the edge again.
2. For a blocked cardinal transition, use the one locally derived canonical
   ordered edge/evaluator and
   return the first blocking provider in exit layer, then entry layer, then UUID
   order. Fall back to a center/destination blocker only when no boundary
   provider blocks the transition.
3. Do not create a result DTO, second blocker registry, or collision policy.

Public proofs cover exit-side and entry-side wall/door identity and ensure
forced movement reports the actual provider name rather than generic
`"obstacle"`.

## 6. AoE propagation semantics and dead plumbing

1. Base Cone/Line/other ordinary shapes apply their existing objective
   propagation semantics even when the AoE origin equals the caster.
2. Cylinder preserves its existing shape-owned barrier-ignoring contract for
   both caster-origin and targeted previews.
3. Reuse the shape's existing objective semantics on the transient preview
   shape. Ordinary shapes then intersect propagated positions with the actor's
   authorized visible positions. Cylinder retains its complete geometric
   `affected_positions` and filters only `affected_entity_uuids` through typed
   contacts plus self-authority. Do not add a new propagation policy or shape
   hierarchy.
4. Remove Entity's dead `_aoe_origin_fov_cache*` state and dead internal
   `fov_cache`/`barrier_positions` threading. Retain the real bounded GridMap
   propagation query and the existing footprint/preview caches.

Public action-discovery proofs cover caster-origin Cone and Line across a
propagation-only boundary and targeted Cylinder behind a horizontal wall. The
Cylinder proof must assert both the retained behind-wall position and exclusion
of an entity absent from typed contacts.

## 7. Required residue deletion

Delete only the following proven dead residue from the rejected cut:

- `_DIRECTION_DELTAS` and `_directional_neighbors` in `world_events.py`;
- the always-empty `border_snapshots` return/parameter/call plumbing and stale
  derived-border wording in GridMap object rollback;
- `dnd/core/gridmap.py`'s unused shadowcast `compute_fov` import and its two
  unused local legacy FOV callback blocks (`mark_visible`/`is_blocking_for` and
  the optical `blocking_cache` block);
- `SpatialChangeEvent` from `dnd/blocks/base_item.py`;
- `cast`, `DOOR_DIRECTIONS`, and `WALL_DIRECTIONS` from
  `dnd/content/scenarios/battlefield_builders.py`;
- `BaseBlock` from `dnd/content/scenarios/scenario_compatibility.py`;
- `Tuple` from `dnd/types/items.py`; and
- `PositionCommitError` from exactly
  `tests/engine/test_action_cost_and_position_commit.py`,
  `tests/engine/test_elevated_jump_transaction.py`,
  `tests/engine/test_move_settlement.py`, and
  `tests/engine/test_traversal_connectors.py`.

No other opportunistic import or style cleanup is authorized.

Retain `SensesUpdateHint.directional_positions`, `directional_neighbors`, and
`directional_channels_changed` as the approved nonauthoritative bounded hints.
Retain `Senses.directional_collision_blocked` as observer-owned collision
memory. Cosmetic words such as `place_standard_directional_barrier` or a test
name do not justify a gameplay rename in this repair.

## 8. Prohibited scope

No Slice 3.4 cliff or WallTorch attachment authorship. No server/editor/SDK,
TypeScript/JavaScript, generated transport/presentation, or inactive
`dnd/items/environment_content.py`. No EventQueue, reducer, controller,
Encounter, cache/index/manager, receipt, compatibility facade, custom
serializer, dynamic/late import, or source-layout gameplay test.

## 9. Validation and new freeze

Luna must stop after each bounded implementation checkpoint for supervisor
review. The rejected candidate's exact active collection is frozen as 607
sorted node IDs with SHA-256
`198ed9a575f4cae44e8cb85a954eae779e5a5a085db9670cf129f6c5c7b1102b`.
Every one of those node IDs remains, except no deletion/rename is authorized by
this repair. Existing selectors may be extended in place:

- `tests/engine/test_tile_surface_contract.py::test_boundary_bands_are_exact_side_queries_and_independent_collisions`;
- `tests/engine/test_tile_surface_contract.py::test_boundary_lifecycle_emits_exact_structure_facts_for_move_orient_remove`;
- `tests/engine/test_tile_surface_contract.py::test_rebuild_provider_failure_restores_live_state_and_current_diagnostics`;
- `tests/engine/test_tile_surface_contract.py::test_object_commands_restore_bands_borders_and_events_when_provider_throws`;
- `tests/engine/test_grid_pathfinding.py::test_eb_11_017_forced_movement_and_jump_respect_directional_blockers`; and
- `tests/engine/test_grid_pathfinding.py::test_eb_11_019_cylinder_subjective_preview_matches_targeting_footprint`.

Exactly five new node IDs are authorized:

- `tests/engine/test_tile_surface_contract.py::test_move_object_rejects_while_events_are_disabled_without_mutation`;
- `tests/engine/test_grid_pathfinding.py::test_unknown_boundary_collision_records_directed_memory_before_reroute`;
- `tests/engine/test_action_discovery.py::test_caster_origin_preview_obeys_propagation[line]`; and
- `tests/engine/test_action_discovery.py::test_caster_origin_preview_obeys_propagation[cone]`; and
- `tests/engine/test_action_discovery.py::test_targeted_cylinder_preview_keeps_full_geometry_and_filters_hidden_contacts`.

The repaired active collection is therefore the frozen 607-node set plus those
five exact nodes: 612 sorted node IDs. The final ledger records and hashes that
exact union; any other added, removed, or renamed node is a stop condition.

The final repaired candidate must run:

1. focused public regressions for Sections 1-6;
2. the exact changed-module lane;
3. the 14-module capability lane;
4. spell, complete architecture, and exact active 612-selector collection;
5. the complete active in-process lane;
6. scoped Section 14/dead-residue searches;
7. compile and `git diff --check`.

Then recompute the complete governed active changed `.py`/`.json` member set
against the accepted Slice 3.1 baseline and approved exclusions, hash every
current raw member, regenerate the Slice 3.3 manifest and certification ledger,
and record both final artifact hashes. Obtain independent correctness and
anti-slop approvals. The old `cbb26f...` manifest remains rejected history.
