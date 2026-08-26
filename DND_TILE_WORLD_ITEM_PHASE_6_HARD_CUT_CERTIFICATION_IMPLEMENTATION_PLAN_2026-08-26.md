# Phase 6 hard-cut and certification implementation plan

Status: `APPROVED — READY FOR SLICE 6.0`

Substantive reviewed SHA-256:
`e1b56a6cb29dd64ee2b033eb4e3440e43489f96b4ef409aa56d9319239d8606b`

Date: 2026-08-26

This is the practical implementation authority for Phase 6 of the accepted
Tile / world-item migration. It converts the master plan's final certification
phase into bounded, reviewable slices. It does not begin content recovery,
presentation recovery, Phase 7, server work, SDK work, or transport work.

## 1. Governing authority and precedence

The implementation must follow, in order:

1. `DND_TILE_WORLD_ITEM_VERTICAL_BOUNDARY_MIGRATION_PLAN_2026-08-17.md`,
   SHA-256 `50411e5575e6336ca0301acf032797cdf1d5ea885df5ccd37d6619f593e7a193`;
2. `DND_TILE_WORLD_ITEM_ACTIVE_RUNTIME_SCOPE_AMENDMENT_2026-08-24.md`,
   SHA-256 `f10e2fbbcb6ba8732d078f0c4f2f5276716eb51e32c083068f3cae93c9ba52d6`;
3. the accepted Phase 5 implementation plan,
   SHA-256 `892e07aea27cb777fcb6fda6a7f7415d46bd4825a582d5f6001fb383f4a10870`;
4. the accepted Phase 5 completion ledger,
   SHA-256 `b75f690bfe7486d5f63cef3e20a8b8031944e4ae776a4adf4422ef255fe46cfa`;
5. the accepted Phase 5 manifest,
   SHA-256 `c10171e9e64ea96ca93f0b971917aad1824654d950a82bed1b7cb516cbef70b1`;
6. `HOW_TO_TEST.MD`,
   SHA-256 `96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013`;
7. `agents.md` and this reviewed plan.

If those bytes differ at Slice 6.0, stop. Historical, revoked, draft, or
server-oriented documents are not authority.

## 2. Outcome

Phase 6 is complete only when the accepted in-process Python runtime has:

- no generic or item-owned floor coordinate beside GridMap placement;
- no stored Boolean Tile walkability beside the exact movement-mode costs;
- no renderer identifier in active Tile or world-item mechanics contracts;
- replay-sufficient cold and incremental Tile movement after-values;
- no active caller of any retired Phase 0-5 authority;
- public behavioral, replay, dependency, locality, and architecture evidence
  for the completed design; and
- one exact final active manifest and one accepted completion ledger.

The initial audit proves Phase 6 is a bounded repair plus certification phase,
not a test-only pass.

## 3. Non-goals and exclusions

Do not:

- restore `dnd.content_system`, `server`, removed progression packages, or any
  other dependency merely to reduce repository-wide collection errors;
- edit `server/**`, `deprecated/**`, SDK, TypeScript/JavaScript, generated,
  transport, API, session, editor, renderer, pygame-asset, or cross-language
  files;
- edit inactive `dnd/items/environment_content.py` or its blocked consumers;
- begin general item/content/presentation recovery;
- remove or redesign `Entity.sprite_name`, `Appearance`, semantic item content
  identity, inventory/equipment behavior, recipes, or presentation packaging
  that is not an active floor/world caller;
- change movement, optics, light, propagation, conditions, concentration,
  targeting, action costs, or encounter rules except where the accepted
  authority cut requires the same existing behavior to be expressed from the
  canonical state;
- add a compatibility property, alias, dual write, secondary index, manager,
  controller, service, registry, reducer framework, receipt family, callback
  path, event path, serializer, or asset-binding system;
- make height affect optics, illumination, or propagation; or
- treat excluded collection failures as an acceptance gate.

The content recovery track starts after this geometry/world-state migration.
Phase 6 removes renderer data only from the active mechanics boundary; it does
not build its client-side replacement.

## 4. Accepted starting state

### 4.1 Active candidate

The accepted Phase 5 manifest has 80 sorted unique members: 37 production and
43 tests, with zero current-byte mismatches at planning time. Its exact frozen
inputs recollect:

- 650 unique nodes;
- node-set SHA-256
  `8202c5f659be52244112818848d40d01f2a358adf3cce17200ccd075e172c2e6`;
- successful collection and execution in the accepted Phase 5 ledger.

Slice 6.0 must independently reproduce the count, hash, and green execution
before editing production or tests.

### 4.2 Repository-wide diagnostic baseline

The diagnostic command is:

```text
.venv/bin/python -m pytest --collect-only -q -p no:cacheprovider
```

At planning time it collects 1,382 nodes and reports 105 collection errors.
The stable normalized signature is the sorted tuple of:

```text
(collecting test path, terminal exception class,
 root-normalized terminal exception message)
```

The planning signature SHA-256 is
`eccd100453848ac9af6a6e028692862dbf0866daaf0c0e3d275b13d4d4e06cd9`.
Absolute checkout prefixes, traceback line numbers, order, elapsed time, and
pytest decoration are excluded from this hash.

The known groups are 57 missing `dnd.content_system`, 15 missing `server`, and
33 removed content/progression/presentation/devtool dependencies or files.
Slice 6.0 records the exact 105-row table in the ledger. The final diagnostic
must introduce no new active geometry failure. A difference confined to an
already excluded family is reported, not repaired.

### 4.3 Accepted dirty state

The Phase 5 production and test edits, plan, ledger, and manifest are accepted
input. They must remain in the worktree. No reset, checkout, clean, commit, or
broad formatter is permitted. Slice 6.0 records the exact `git status --short`
and current hashes before creating the Phase 6 ledger.

## 5. Decisive pre-audit

The following Phase 0-5 cuts are already clean in active scope and must remain
clean:

- old Tile directional/open/blocked authority;
- shared or reciprocal edge storage;
- flat object-position dictionaries other than the one canonical reverse
  `GridMap._object_placements` placement map;
- multi-side objects and duplicate door families;
- WallTorch private position;
- Entity class/GridMap position indexes;
- direct private-index Banishment writes; and
- object anchors reading a BaseItem-owned coordinate.

Three live residue families remain.

### 5.1 Generic floor position residue

`BaseBlock.position` is inherited by every BaseItem, so a fresh item currently
serializes the false floor coordinate `(0, 0)` while `BaseItem.get_position()`
correctly derives its effective coordinate from its owner or GridMap placement.
This violates the Phase 2 hard cut and completion definition.

### 5.2 Stored walkability residue

`Tile.walkable` is a stored mutable Boolean duplicate of `walking_cost`.
Changing the Boolean does not change mechanics. It also drives incomplete
incremental event and revision comparisons. `BattlefieldTileDefinition`,
`GridMap` constructors, `WorldTileState`, and `SpatialChangeEvent` still carry
parts of this scalar contract.

### 5.3 Renderer-data residue

`Tile.sprite_name`, `BaseItem.map_char`, `BaseItem.visual_item_name`,
`BaseItem.visual_variant_id`, `BaseBlock.get_map_char`, and active floor/world
constructor declarations or arguments remain. They violate the master plan's
renderer-neutral Tile/item boundary. `WorldInitializedEvent`, `ItemState`, and
current placement facts are already renderer-neutral and must remain so.

## 6. Final contracts

### 6.1 Objective position ownership

The final neutral contract is:

| Object family | Objective coordinate contract |
|---|---|
| Entity | explicit `Entity.position`; Tile inverse membership |
| Tile | explicit `Tile.position`; GridMap coordinate/UUID indexes |
| SpatialCondition | explicit condition anchor plus indexed footprint |
| Senses | explicit reducer-owned subjective `Senses.position` |
| BaseItem on floor | exact GridMap `WorldObjectPlacement` query |
| BaseItem owned/contained | owner neutral position query or no coordinate |
| neutral non-spatial BaseBlock | `get_position()` returns `None` |

Implementation rules:

- remove the field `BaseBlock.position`;
- remove the unused recursive `BaseBlock.set_position()`;
- make neutral `BaseBlock.get_position()` return `None`;
- declare `position` directly on Tile and Senses; Entity and
  SpatialCondition already declare it;
- type every one of those four owner fields as an exact two-component tuple of
  Pydantic `StrictInt` values so booleans, floats, and strings are rejected;
- give Tile, Entity, SpatialCondition, and Senses explicit `get_position()`
  implementations returning their declared field rather than inheriting the
  neutral BaseBlock result;
- keep `BaseItem.get_position()` as the existing derived owner/GridMap query;
- change neutral call sites such as action AoE origin resolution to use
  `get_position()` and handle `None` explicitly;
- let GridMap Entity membership validation use the public neutral query or a
  proven Entity instance, never a generic inherited field; and
- add no BaseItem `position` property, hidden cache, or compatibility input.

The affected BaseBlock model hierarchy must reject unknown construction/model
validation inputs rather than silently ignore them. Use ordinary Pydantic
`extra="forbid"` configuration at the affected base boundary, not a field alias,
custom serializer, compatibility validator, or hand-maintained retired-key
list. Public construction and round-trip tests must prove that a deleted
`position` input is rejected for a neutral BaseBlock/BaseItem while the four
declared owners accept only strict coordinates.

Any collecting active BaseBlock subclass that truly needs objective position
must be identified in Slice 6.0 and approved at the checkpoint before a field
is added. Child combat/configuration blocks do not inherit their owner's
position as stored authority.

### 6.2 Tile movement authority

The four exact movement-mode costs are the only intrinsic traversal scalars:

```text
walking_cost, flying_cost, swimming_cost, burrowing_cost
```

Rules:

- each public Tile/GridMap construction command accepts exact nonnegative
  integer costs, with current defaults `1, 1, 0, 0`;
- Boolean values are rejected as costs;
- cost zero means intrinsically unavailable for that mode;
- `Tile.walkable` and every `walkable=` construction input are deleted in the
  same atomic caller migration; no derived compatibility property remains;
- factories express existing mechanics directly: ordinary floor, wall,
  water, and difficult terrain retain their current per-mode behavior;
- `BattlefieldTileDefinition` stores exact movement costs, permits zero, and
  has no Boolean walkability field;
- authored definitions and builders provide exact final costs rather than a
  Boolean plus a later modifier workaround;
- Tile replacement compares the complete effective four-cost tuple for
  movement revision/path invalidation;
- surface-only changes do not dirty movement; and
- any one-mode effective cost change dirties movement but not optics or
  propagation unless those channels separately changed.

Do not introduce a second `MovementProfile` model, policy object, cache, or
manager in Phase 6. The existing four `ModifiableValue` owners remain.

### 6.3 Incremental and cold Tile facts

`WorldTileState` contains exactly the four committed effective movement cost
after-values and no `walkable` Boolean. Each cost is a Pydantic `StrictInt`
that accepts zero and rejects bool, float, and string input.
`SpatialChangeEvent` Tile changes expose four exact optional `StrictInt`
after-values:

```text
tile_walking_cost
tile_flying_cost
tile_swimming_cost
tile_burrowing_cost
```

`tile_walkable` is deleted. `SpatialChangeEvent` uses ordinary Pydantic
`extra="forbid"` configuration so the retired input cannot be silently ignored.
`SpatialChangeEvent.tile_changed(...)` and every active producer supply the
complete four-cost tuple whenever movement state is part of the committed Tile
change. Existing intrinsic optics, propagation, surface, height, placement,
lifecycle, and sensory-hint facts retain their accepted meanings.

Tile construction, replacement, surface replacement, and terrain-condition
modifier paths mutate their authoritative state before their observation fact
is published. Every such already-committed change must therefore use the
existing GridMap committed-spatial-fact boundary. Declaration cancellation
cannot veto or erase a fact for state that has already committed. Do not add a
second publisher or redesign EventQueue.

A multi-Tile terrain-condition activation/removal publishes one existing
`SpatialChangeEvent` Tile-change fact for every position whose effective
movement tuple actually changed. Facts are published in lexicographic
coordinate order, carry the condition source and existing parent lineage when
available, and contain that Tile's own complete after-tuple. One representative
position, a batch DTO, or a shared tuple is not replay-sufficient because
different Tiles can have different base costs and modifiers.

Spatial-condition application installs some owned mechanics provisionally
before the condition application completes. During that admission window,
terrain changes are collected as pending per-Tile after-values on the existing
condition-owned pending-runtime-fact seam; they are not published as committed
facts yet. Successful application publishes the sorted pending facts only
after the condition footprint and application have committed, using the effect
event as existing causal lineage. Rejected, cancelled, or exceptional
application rolls the modifiers back and discards the pending terrain facts
without publishing either provisional or inverse Tile-change lifecycles.
Ordinary removal, relocation, footprint change, and already-applied condition
transitions continue to publish their sorted after-values at their existing
post-commit pending-runtime-fact boundary. Do not add a transaction manager,
event buffer framework, or new event type.

The event fields are flat values on the existing event. Do not add a movement
event, delta envelope, replay manager, or serialized edge/navigation cache.
Hints remain invalidation/locality hints and are not replay authority.

### 6.4 Renderer-neutral mechanics boundary

Delete from active Tile/world-item mechanics:

- `Tile.sprite_name` and its Tile factory/GridMap rectangle/setter inputs;
- `BaseItem.map_char`, `visual_item_name`, and `visual_variant_id`;
- `BaseBlock.get_map_char` and the BaseItem override; and
- active floor/world subclass fields, authored `map_character` fields, and
  constructor arguments whose only purpose is those deleted runtime fields.

Affected Tile and BaseItem models reject retired/unknown inputs through the
same ordinary Pydantic `extra="forbid"` boundary described above. Deleted
`walkable`, `sprite_name`, `map_char`, `visual_item_name`, and
`visual_variant_id` inputs must fail publicly; silent ignore is a compatibility
path and fails Phase 6.

Retain semantic rules data: stable content identity/reference, name,
description, tags, material, boundary structure, open state, placement,
blocking channels, light semantics, item state, and inventory/equipment rules.

Do not replace deleted fields with an asset key, glyph enum, presentation
component, lookup table, or binding interface. Entity presentation and general
variant/content packaging are outside this cut. If an apparently active
presentation caller cannot be separated without redesigning general content
packaging, stop at the slice checkpoint and classify it; do not silently widen
the phase.

## 7. Initial implementation envelope

### 7.1 Expected production members

The initial expected set is:

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
- active world-item definitions/builders or subclasses proven by Slice 6.0 to
  declare or pass a deleted Tile/item presentation field.

The last category is caller-completeness work, not authority to sweep all item
content. The Slice 6.0 ledger must list each admitted file and exact active
caller. Any other production file is stop-only until coordinator review.

### 7.2 Expected maintained test members

The affected active set initially includes:

- Tile surface, grid pathfinding, terrain movement, event-wire, objective
  state, world-edge/elevation, spatial-effects, senses/light, item/inventory,
  direct item content, direct scenario, battlefield elevation, authored
  encounter, and scenario catalog tests;
- architecture dependency and deletion tests; and
- the exact Phase 5 accepted lane.

Slice 6.0 also admits these already collecting maintained capabilities after
any private-helper assertions are rewritten through public behavior:

- all 3 nodes in `tests/manual/test_84_generic_roster_duels.py`;
- the 1 node in `tests/manual/test_150_prepared_scenario_lifecycle.py`;
- all 8 nodes in `tests/engine/test_progressive_elevation_movement.py`;
- all 6 nodes in
  `tests/engine/test_spatial_effect_reveal_idempotency.py`; and
- `tests/engine/test_combat_actions.py::test_eb_10_021_forced_movement_traverses_terrain_without_step_costs`.

These 19 existing nodes expand the unchanged-code minimum from 650 to 669.
The exact final count will be 669 plus the new Phase 6 public proof nodes.

Do not admit blocked server/content-system/presentation modules wholesale. A
valuable missing public mechanic is transplanted into a maintained active test
only when the ledger proves it is not already covered.

## 8. Slice sequence

### Slice 6.0 — preflight and exact caller ledger

No production or test edit is allowed.

1. Read this full reviewed plan, the master, scope amendment, Phase 5 plan,
   final ledger, manifest, `HOW_TO_TEST.MD`, and `agents.md`.
2. Verify every governing hash.
3. Verify all 80 Phase 5 manifest members against current bytes.
4. Recollect the exact 650 nodes and hash, then run the exact node set green.
5. Record the exact dirty-state snapshot.
6. Run the repository-wide diagnostic and record all normalized 105 rows,
   group counts, collected-node count/hash, and exit status.
7. Produce an AST plus runtime-schema inventory of every active caller and
   declaration for:
   `position`, `set_position`, `walkable`, `tile_walkable`, `sprite_name`,
   `map_char`, `visual_item_name`, and `visual_variant_id`.
8. Classify every match as MUST-MIGRATE, VALID RETAINED, or GOVERNED EXCLUDED.
9. Record the exact initial production/test envelope and the 19 collecting
   lane additions.
10. Create the single Phase 6 implementation ledger and stop for coordinator
    review.

The checkpoint is rejected if it treats textual words such as
`GridMap.is_walkable`, `Senses.walkable`, valid Tile UUID identities,
`Entity.register_entity`, or semantic content names as retired authority.

### Slice 6.1 — objective position hard cut

Atomically implement Section 6.1 and migrate every admitted active caller.

Required public proofs:

- a new BaseItem has no `position` model field or serialized coordinate;
- a floor item reports only its exact committed GridMap placement;
- an owned item follows the owner's neutral public position query without
  gaining stored position;
- a contained/non-spatial item with no positioned owner reports `None`;
- Entity move/suspend/restore and Tile membership remain coherent;
- Tile, Entity, SpatialCondition, and reducer-owned Senses preserve their
  explicit coordinates and serialization rules, expose their coordinate
  through their own neutral query implementation, and reject Boolean, float,
  string, and deleted-input coordinates;
- position-based AoE resolves from a positioned source and fails/returns the
  established neutral result for a non-positioned source without inventing
  `(0, 0)`; and
- no accepted per-step objective-to-subjective event ordering changes.

Run the focused position, placement, action, item, condition, movement,
Banishment, and architecture groups. Append exact files, nodes, results, and
hard-cut scans to the ledger. Stop for coordinator review.

### Slice 6.2 — movement scalar and Tile-fact hard cut

Atomically implement Sections 6.2 and 6.3 and migrate all admitted active
constructors, authored definitions, producers, and tests.

Required public proofs:

- all four movement costs construct and serialize exactly, including zero;
- bool and negative input are rejected;
- ordinary, wall, water, difficult, and authored battlefield Tiles preserve
  current movement-mode behavior;
- no Tile, WorldTileState, battlefield row, or SpatialChangeEvent schema has a
  `walkable`/`tile_walkable` field;
- all persisted/cold/incremental cost fields accept zero only as a strict
  integer and reject Boolean, float, and string inputs;
- replacing a Tile with one changed mode cost invalidates movement results and
  preserves unrelated channel revisions;
- a surface-only update preserves all four costs and movement results;
- terrain/condition modifier activation and removal publish one non-vetoable
  committed fact per actually changed Tile, in deterministic coordinate order,
  with each Tile's exact complete effective four-cost after-tuple;
- the cold world event has the exact complete four-cost rows;
- detached test-only application of cold plus incremental public facts over a
  heterogeneous multi-cell condition footprint yields the same Tile movement
  projection as live state;
- a declaration-phase cancelling handler cannot suppress the completed fact
  for an already-committed Tile replacement or terrain modifier;
- a condition application forced to fail after provisional terrain-modifier
  installation but before application completion publishes no completed Tile-
  cost fact, restores the exact live Tile costs, clears pending terrain facts,
  and leaves detached replay equal to live state; and
- subjective `Senses.walkable` remains reducer-owned derived navigation and
  is not renamed or serialized as objective authority.

No production replay subsystem is authorized. The replay proof is a small
test-side state application of public event after-values.

Run focused Tile, pathfinding, movement-mode, event, condition, cold bootstrap,
scenario, replay, revision, and locality groups. Stop for coordinator review.

### Slice 6.3 — renderer-neutral Tile/world-item hard cut

Atomically implement Section 6.4 for the exact active caller ledger.

Required public proofs:

- Tile and BaseItem public schemas/dumps contain none of the deleted renderer
  fields;
- public model validation and constructor calls reject the deleted renderer,
  walkability, and item-position inputs rather than silently ignoring them;
- Tile factories, GridMap commands, active world-object builders, item state,
  item location facts, object state, and cold world state carry no glyph,
  sprite, visual-item, or visual-variant field;
- semantic identity, placement, wall/door/cliff/torch/trap behavior,
  inventory/equipment behavior, light ownership, and action discovery are
  unchanged; and
- no replacement renderer abstraction enters mechanics.

Do not rewrite renderer or content-presentation tests. Run focused schema,
surface, direct item, inventory/equipment, environment object, WallTorch,
scenario, bootstrap, and architecture groups. Stop for coordinator review.

### Slice 6.4 — completion proof and test-quality closure

This slice changes tests and narrowly owned structured diagnostics only when a
public locality proof cannot be expressed with an existing diagnostic.

1. Add migration-specific AST gates for the exact dependency arrows in master
   Section 16.7.
2. Prove only GridMap calls Tile private membership replacement methods and
   only GridMap owns reverse object placement.
3. Prove only `SpatialSensesSystem` or sensory-event replay mutates materialized
   Senses projection fields.
4. Re-run the complete retired-symbol inventory for Phases 0-6 with explicit
   retained-name and excluded-path allowlists.
5. Add public same-XY orient/open anchor-stability behavior.
6. Add public ordinary-step and lethal-stop SpikeTrap behavior, without
   `_paths_dirty` assertions.
7. Prove unchanged turn start does not recompute navigation work.
8. Prove spatial-condition work scales with the changed footprint, not total
   map area.
9. Replace affected evidence that relies on monkey-patched engine
   collaborators, private cache state, or wall-clock-only ratios with public
   results or one narrow immutable diagnostic snapshot at the existing owner.

A diagnostic may report only work already counted by that owner. It may not
control behavior, become serialized state, create a second index, expose
private dictionaries, or introduce a generic instrumentation framework.

Run the 669 existing-node lane plus every new Phase 6 proof, the complete
architecture lane, and focused locality gates. Stop for coordinator review.

### Slice 6.5 — final certification and freeze

No behavior repair is combined with final certification.

1. Recollect the exact sorted union of the accepted 650 nodes, the 19 admitted
   existing nodes, and every authorized Phase 6 node.
2. Record path/selector inputs, exact sorted node IDs, count, and normalized
   SHA-256.
3. Execute that exact newline/NUL-safe node set byte-identically.
4. Run compileall on every changed active Python file.
5. Run `git diff --check` and the scoped changed-file check.
6. Run complete architecture, dependency, authority, locality, replay,
   hard-cut, and runtime-schema gates.
7. Re-run the repository-wide diagnostic and compare the normalized signature.
8. Write the exact final active-only JSON manifest with current hashes and
   validation facts.
9. Append the final caller/deletion ledger and freeze the candidate as
   `READY_FOR_INDEPENDENT_REVIEW`.
10. Make no further code/test edit until coordinator validation and two exact-
    candidate reviews.

Any code or test repair after the freeze invalidates the node set, manifest,
validation, and both reviews. Re-run every affected gate and freeze a new
candidate.

## 9. Public proof matrix

| Contract | Required evidence |
|---|---|
| position authority | schema absence plus floor/owner/none public queries |
| Entity occupancy | deploy/move/suspend/restore public behavior and Tile query |
| per-step settlement | carried light/FOV/senses changes after each committed step |
| movement authority | four exact costs, per-mode path/traversal outcomes |
| revisions | public changed/unchanged result plus narrow revision diagnostic already owned by GridMap |
| cold facts | complete actor-free initialization rows |
| incremental facts | exact four-cost Tile after-values |
| replay | detached test-side public fact application equals live projection |
| renderer neutrality | public Pydantic schemas/dumps and events |
| ordered geometry | both source-exit and destination-entry mechanics remain green |
| conditions/light | optics, light, concentration, anchor, reveal, and reaction lanes |
| locality | structured counts, never wall-clock alone |
| dependencies | AST/import ownership checks |
| hard cut | semantic AST/runtime-schema scan with explicit valid/excluded matches |

Tests follow `HOW_TO_TEST.MD`: public behavior first, deterministic inputs,
exact structured after-values, no tests that merely mirror implementation,
and no private-state or collaborator-monkey-patch proof. Static AST/schema
tests are appropriate only for explicit dependency and deletion contracts.

## 10. Hard-cut gates

### 10.1 Must be absent in governed active scope

- BaseBlock/BaseItem stored floor `position` and `set_position`;
- Tile `walkable` field, reads, writes, and constructor arguments;
- BattlefieldTileDefinition `walkable`;
- WorldTileState `walkable`;
- SpatialChangeEvent `tile_walkable`;
- Tile/GridMap `sprite_name`;
- BaseItem/world-item `map_char`, `visual_item_name`, and
  `visual_variant_id` declarations, reads, writes, and constructor arguments;
- BaseBlock/BaseItem `get_map_char`;
- all retired Phase 3 directional/duplicate-door/private-wall-torch symbols;
- all retired Phase 4 Entity/GridMap occupancy indexes and compatibility
  movement/registration paths; and
- any second floor placement dictionary, Entity coordinate index, serialized
  WorldEdge authority, or renderer binding inside mechanics.

### 10.2 Valid retained concepts

- `GridMap.is_walkable` and ordinary prose/function names describing derived
  walkability;
- `Senses.walkable` as subjective reducer-owned navigation;
- `SensesUpdateHint.directional_positions`, `directional_neighbors`, and
  `directional_channels_changed`;
- `Senses.directional_collision_blocked`;
- `Tile.position`, `Entity.position`, `SpatialCondition.position`, and
  `Senses.position` under Section 6.1;
- `WorldObjectPlacement.position`/`tile_uuid`, event before/after placements,
  connector support Tile UUIDs, and GridMap Tile UUID lookup;
- `Entity.register_entity` as identity registration;
- derived `GridMap.get_object_position()`, `get_entity_position()`, and
  `get_entities_at()` queries;
- semantic `blocked_channels`, explicit cardinal placement sides, and bounded
  propagation caches; and
- Entity/Appearance or inactive content-presentation fields explicitly outside
  the active Tile/world-item boundary.

The final ledger records AST-qualified matches, not an unreviewed grep count.

## 11. Validation and manifest rules

The ledger must include:

- all authority hashes;
- exact preflight and final dirty snapshots;
- Phase 5 manifest verification;
- baseline 650 and expanded/final node counts and hashes;
- exact added/removed/renamed node IDs with reasons;
- focused and final command/result pairs;
- full normalized blocked-signature rows and comparison;
- production/test caller classification;
- compile, diff, dependency, architecture, locality, replay, schema, and hard-
  cut outputs;
- exact final manifest membership and SHA-256; and
- every checkpoint authorization and independent verdict.

The final manifest contains only governed active Python/JSON members and the
facts required to reconstruct the exact active lane. It excludes Markdown,
server/deprecated/SDK/generated/renderer/editor/cross-language files, inactive
content-system packaging, caches, and temporary output.

## 12. Stop rules

Luna must stop and return to the coordinator when:

- a governing hash or accepted Phase 5 member differs;
- baseline 650 count/hash or execution differs;
- a required mechanic appears to need an excluded file or dependency;
- another collecting neutral BaseBlock subclass depends on the generic stored
  position and the fix is not an obvious move to an already accepted owner;
- renderer removal requires redesign of general content/variant packaging;
- an unlisted production file or new abstraction appears necessary;
- an existing objective/subjective event boundary must change;
- a focused group reveals a behavior regression unrelated to the admitted
  hard cut; or
- any final certification step discovers a code/test repair.

The coordinator may authorize only a bounded correction consistent with this
plan. A new rules or scope decision returns to the user.

## 13. Review and supervision protocol

Before implementation:

1. one independent reviewer validates correctness, completeness, replay, and
   consistency with the accepted master/scope/Phase 5 candidate;
2. a second independent reviewer validates anti-slop, dependency direction,
   scope containment, test quality, and absence of redundant machinery;
3. every substantive correction invalidates both verdicts; and
4. both reviewers reconfirm the final plan bytes after review metadata is
   appended.

Implementation uses the existing gpt-5.6-luna xhigh task. Luna receives the
exact final plan SHA and is authorized for Slice 6.0 only. The coordinator
independently inspects every checkpoint and sends the next bounded instruction
directly. Luna does not spawn subagents. A ten-minute supervision automation
monitors that exact task until Phase 6 is genuinely complete.

Final acceptance requires coordinator validation plus two independent exact-
candidate reviews: correctness/replay/scope and anti-slop/dependency/locality.
Only review metadata may be appended afterward; both reviewers reconfirm the
final ledger bytes. The automation is then deleted.

## 14. Completion definition

Phase 6 is accepted only when:

1. Sections 6.1-6.4 are implemented with no compatibility interval;
2. all master completion items remain true on the active runtime;
3. the exact final active lane is green;
4. repository-wide blockers are unchanged or explicitly explained within
   governed exclusions;
5. active hard-cut, architecture, replay, dependency, and locality gates are
   green;
6. exact manifest and ledger artifacts are independently approved; and
7. no required work remains inside the Tile/world-item migration.

Content recovery, renderer/client binding, server/transport modernization, and
other separately planned work remain after this migration; their existence
does not block Phase 6.

## 15. Review record

The first candidate, SHA
`ddb732dbc53db54f59b75c901daf0ea920b6f9ecaeaa4ab8bba6917276395980`,
was rejected for incomplete committed-fact, per-Tile replay, strict-input, and
strict-type contracts. The intermediate SHA
`13b685605c1e2270bc3c69e647e7ab139dd697f22f6c8934182ea63ee0d53f37`
closed those findings but was rejected for provisional spatial-condition fact
publication. Both reviewers approved the corrected exact substantive bytes:

| Review | Exact substantive SHA-256 | Verdict |
|---|---|---|
| correctness, scope, event order, replay | `e1b56a6cb29dd64ee2b033eb4e3440e43489f96b4ef409aa56d9319239d8606b` | APPROVED |
| anti-slop, dependency, locality, test quality | `e1b56a6cb29dd64ee2b033eb4e3440e43489f96b4ef409aa56d9319239d8606b` | APPROVED + ANTI-SLOP APPROVED |

The status and this review record are metadata-only additions. Both reviewers
must reconfirm the final raw plan bytes before Slice 6.0 begins.
