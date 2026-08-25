# Tile / World-Item Phase 3 — Ordered Tile-Side Implementation Guidance

Status: APPROVED FOR ACTIVE-RUNTIME IMPLEMENTATION

Previously approved ordered-mechanics revision:
`495914ec28df82b553f23347f2a29eb9be7764f21039e5619e083c1a20b4e7de`

Implementer after approval: Luna. Reviewers must remain independent from the
implementer.

This document refines only Phase 3 of
`DND_TILE_WORLD_ITEM_VERTICAL_BOUNDARY_MIGRATION_PLAN_2026-08-17.md` after the
accepted Phase 0–2 side-geometry correction. It replaces no historical file.
The revoked
`DND_TILE_WORLD_ITEM_PHASE_3_IMPLEMENTATION_GUIDANCE_2026-08-24.md` remains
superseded review history and is not an implementation authority.

## 1. Frozen starting state

Before any edit, verify every exact input and every member of the accepted
implementation manifest:

| Input | Required SHA-256 |
|---|---|
| Corrected master plan with active-runtime amendment | `50411e5575e6336ca0301acf032797cdf1d5ea885df5ccd37d6619f593e7a193` |
| Active-runtime scope amendment | `f10e2fbbcb6ba8732d078f0c4f2f5276716eb51e32c083068f3cae93c9ba52d6` |
| Unified vision/light plan | `3c9c58483440640837bc38fdaa6b624f358e1098c9a957f65923cd64f83a270b` |
| Phase 0–2 side-geometry correction plan | `ae189282687fdcb7baa88ca3b393af593c6db345029a89da9cfcc36b76f021c1` |
| Accepted corrected Phase 0–2 implementation manifest | `3eb3b75864cda77052675e93b82f43bdf89c5177930a4fa4518db3884900d98c` |
| Accepted Slice 3.1 implementation manifest | `2501ed3fb35c9b17ad5ef3dcd3bc289ef2145c9ea2ea60ab47164bacba099320` |
| Corrected Phase 0–2 execution ledger | `cca4f33e324b47accaf01ecb794c1c4325595dd6e2b53adf99252e9e538cf5c1` |
| Revoked shared-edge Phase 3 guidance | `5644d79ed9149b6a028bc34725c0aa01c60ee26b63abe3b2fb5944063fb7d58a` |

Read `AGENTS.md`, all of `HOW_TO_TEST.MD`, the complete master, unified plan,
correction plan, and corrected execution ledger before writing or testing.
Stop immediately on hash/member drift. Preserve the dirty accepted tree; do not
reset, checkout, or reconstruct it from Git history.

The accepted Slice 3.1 starting baseline is:

- 94 exact manifest members;
- 1,322 collected selectors, sorted-set SHA-256
  `9c67b3e4f95c3054354f04d439428b9360a42021931d506ea73acdb49d61fc3a`;
- 113 modules with collected nodes, SHA-256
  `8a609e8b85157ad9c1db2e085c4f3ca82a6bcb9e4abc84ee4e278da4912873bb`;
- 105 blocked modules, SHA-256
  `ff2ebd76d5772a93dff7723f9869316eb92fe05b10d7b916a6465005ef6bf531`;
- 218-module union, SHA-256
  `003720b0a00ac1ab53af1aabdebaeaf10b324b7e7a7e92b0d25e1e702e6ef7a6`;
- accepted capability lane: 286 passed;
- spell-family lane: 62 passed; and
- architecture lane: 42 passed.

The earlier 90-member, 1,318-selector, and 282-capability values are historical
pre-Slice-3.1 evidence and are not a resume checkpoint. Freeze a fresh pre-edit
ledger with the accepted Slice 3.1 manifest, collection, blocked-
signature, and focused-lane algorithms. Historical counts are evidence, not a
substitute for rechecking the live accepted snapshot.

## 2. Goal and exact boundary

At Phase 3 completion:

1. walls, doors, cliffs, attachments, and fixed center blockers are ordinary
   placed objects with explicit placement specifications;
2. one boundary object occupies one side volume owned by one Tile;
3. adjacent opposing Tile sides remain independent and may both contain
   occupants at the same heights;
4. a transition reads its source exit layer and then its destination entry
   layer;
5. movement, ordinary FOV, light geometry, and propagation require the
   relevant channel to transmit through both ordered layers;
6. ordinary sight and light use the same physical `OPTICAL` topology;
7. subjective contact reduction exposes reached boundary layers without
   leaking the far Tile or its contents;
8. exact placements plus semantic item state remain replay authority; and
9. the old Tile/BaseItem directional projection, duplicate door family, and
   authored multi-direction representation are deleted.

This phase does not implement Phase 4 Entity occupancy, change the accepted
per-step movement or turn-start reducer ownership, redesign bootstrap, add a
frontend projection system, or add 3D ray/actor-altitude mechanics.

### 2.1 Active-runtime implementation boundary

Phase 3 changes and proves only the active single-process Python engine and
the authored Python content needed to exercise it. The pygame-facing runtime
may consume the same semantic state in process. `deprecated/**`, removed or
deprecated server/API modules, server-only tests, SDKs, TypeScript/JavaScript
sources or distributions, source maps, generated cross-language contracts,
and deprecated projection/replay artifacts are explicitly outside the
mutation, caller, schema, manifest, collection, and validation envelopes.

Do not port, regenerate, compile, delete, or restore any excluded artifact.
An excluded textual reference is not a stale active caller and does not block
the directional hard cut. Core Pydantic events remain because the in-process
EventQueue, replay facts, light settlement, and sensory reducer use them; they
are not shaped to satisfy a deferred transport schema.

This section implements
`DND_TILE_WORLD_ITEM_ACTIVE_RUNTIME_SCOPE_AMENDMENT_2026-08-24.md`. The only
prospective caller/test authority is
`DND_TILE_WORLD_ITEM_PHASE_3_ACTIVE_RUNTIME_LEDGER_2026-08-24.md`; the older
Phase 3 implementation ledger is revoked review history.

## 3. Non-negotiable geometry

For adjacent Tiles `I` and `J`:

```text
I:EAST != J:WEST
```

The two side volumes are independent placement/collision identities. Both can
hold occupying objects over the same height bands. Only an overlapping
occupant on the same owner Tile, same side, and same integer band collides.
Changing one side mutates no band or placement on the other.

`AdjacentEdgeKey` is only canonical unordered adjacency identity. It is not a
slot, registry key, owner, collision key, or place to store mechanics.

For `I -> J`, the already-landed `WorldEdgeView` is ordered:

```text
exit_contributions  = I:facing(J)
entry_contributions = J:facing(I)
```

The reverse query shares the key, swaps endpoints/directions/layers, and
negates elevation delta. It is not equal to the forward view. Never flatten
the two contribution tuples or reconstruct a shared physical edge.

## 4. Authority after the cut

| Fact | Sole authority | Derived consumer |
|---|---|---|
| Object side, height, orientation | `GridMap._object_placements[uuid]` | events, snapshots, queries, rendering |
| Side membership/occupancy | selected Tile's private center/boundary bands | local lookup and ordered edge derivation |
| Structure kind/material/current channels | provider's freshly computed `BoundaryStructure` | item/event state and edge contributions |
| Ordered transition topology | on-demand `WorldEdgeView` | movement, FOV/light, propagation |
| Center-cell mechanics | Tile intrinsic cell policy plus center objects/conditions | movement, optics, propagation |
| Objective illumination | existing light-source/Tile contribution system | subjective light reduction |
| Subjective contacts | reducer-owned typed `Senses` maps | targeting, knowledge, projection |

`WorldEdgeView` and its contribution rows remain frozen hot derived values.
They are never persisted, published, cached as authority, mirrored onto a
neighbor, or exposed through a second transport DTO.

## 5. Existing values and neutral capabilities

Reuse the existing Pydantic values from `dnd/types/world_placement.py`:

- `WorldPlacementSpec`;
- `WorldObjectPlacement`;
- `BoundaryStructureKind`; and
- `BoundaryStructure`.

Do not add a second placement policy, edge-side type, structure value, or
material enum. Add an ordinary Pydantic validator so
`BoundaryStructure.blocked_channels` is unique and canonical in
`WorldEdgeChannel` declaration order. Do not add custom serialization.

GridMap sees only the neutral BaseBlock capabilities:

```python
def get_world_placement_spec(self) -> WorldPlacementSpec: ...
def get_boundary_structure(self) -> BoundaryStructure | None: ...
```

Defaults remain one nonoccupying center band and no boundary structure. A
boundary provider returns one newly computed current structure. GridMap does
not call another channel method, cache that structure, reflect on concrete
types, or infer policy from content IDs.

The already-landed hot contribution remains exactly:

```python
@dataclass(frozen=True, slots=True)
class WorldEdgeStructuralContribution:
    provider_uuid: UUID
    base_height_steps: int
    top_height_steps: int
    blocked_channels: tuple[WorldEdgeChannel, ...]
```

Kind, material, placement, orientation, and item state remain resolvable from
their authorities and are not copied into every edge query.

## 6. Frozen authored semantics

Luna must not choose these values:

| Family | Placement | Material/structure | Current channels | Base rule |
|---|---|---|---|---|
| Standard wall | boundary, occupying, extent 2 | `STONE` / `WALL` | movement, optical, propagation | Tile support |
| Standard door | boundary, occupying, extent 2 | `WOOD` / `DOOR` | closed: all three; open: none | Tile support |
| Proving cliff | boundary, occupying, extent 2 | `STONE` / `CLIFF` | movement only | explicit 0 |
| WallTorch | boundary, nonoccupying, extent 1 | no structure | none | explicit authored value; maintained arena rows use 1 |
| Boulder/barricade/oil barrel | center, occupying, extent 1 | no boundary structure | preserve center mechanics | Tile support |

The maintained eastern arena WallTorches use owner side EAST, orientation WEST,
base 1, top 2. These are authored row facts, not coordinate inference.
For every object, owner side and orientation remain independent authored facts:
neither value may be inferred from the other.

### 6.1 Wall

Keep `DirectionalWall` unless a public contract proves a rename necessary.
Make each instance one occupying boundary provider with explicit extent,
material, `BoundaryStructureKind.WALL`, and fixed current channels. Delete its
plural `blocked_directions` and twelve per-direction booleans.

### 6.2 Door consolidation

Keep `DirectionalDoor`, its existing action behavior identities, and
`environment.directional_door` as the canonical family. It is one occupying
boundary provider. Its placement never changes when `is_open` changes; its
computed structure retains kind/material and returns an empty channel tuple
when open.

Migrate and delete the active direct-construction `DoorObject`,
`environment.door` catalog identity, `build_door`, `OpenDoorAction`, and
`CloseDoorAction` paths. Leave no alias or second declaration in the active
Python mechanics/content registry. The inactive `door_recipe` packaging,
unused presentation/icon rows, and all external persisted identities are
deferred by Section 2.1; do not restore their toolchain or treat them as
hard-cut blockers.

### 6.3 Cliff

Add one concrete fixed boundary provider for authored cliff faces. The proving
battlefield authors it at `(11, 5)`, owner side WEST, `[0, 2)`, `STONE`, and
`MOVEMENT` only. Never infer or create it from support-height difference.

### 6.4 Wall attachment

`WallTorch` becomes a nonoccupying boundary placement. Remove any private
world coordinate and keep the accepted attached-light owner/UUID. Every
active mount, definition, and authored fixture supplies side/base/orientation
through the existing GridMap command. A torch can share the same local bands
as an occupying wall. An outer torch needs no synthetic neighbor. Deprecated
editor and transport persistence are deferred.

### 6.5 Center blockers

Use `WorldItem(BaseItem)` only if it genuinely owns reused fixed-spec behavior;
do not create semantic-only center/boundary subclasses. Port boulder,
barricade, oil barrel, and every ledgered physical center blocker to explicit
occupying center specs. Preserve their current center mechanics. A current
nonblocking crate remains nonoccupying unless an authored rule says otherwise.

## 7. Authored crosswalk and stop ledger

Every legacy `blocked_directions=(D1, D2, ...)` row expands deterministically
into one new object/UUID/placement per side in canonical cardinal order. Never
place one UUID on several sides. Preserve label, content identity, material,
closed channels, initial state, and maintained route behavior on every
expanded object.

`blocked_directions` is old placement authorship, not current door state. The
maintained initially-open standard door retains its authored WEST side while
its current structure has empty channels. Do not expand its current empty
tuple into zero objects.

Before the boundary hard cut, freeze a caller-level door ledger covering every
active in-process Python mechanic, collecting mechanics test, recipe, builder,
authored map, and direct placement path for both door families. Each row must
record:

- file/caller and maintained capability;
- exact owner Tile and side;
- orientation if distinct;
- material, extent, closed channels, and initial open state;
- whether one old object becomes one or several new objects; and
- the public behavior test proving the migrated route/action.

There is no repository-wide default side. A no-side center door must be
re-authored from maintained route evidence, expanded into reviewed multiple
boundaries, or escalated. The hard cut cannot begin while any caller is
unclassified.

Replace `BattlefieldObjectDefinition.blocked_directions` with exact per-object
placement fields: optional `boundary_direction`, optional explicit base, and
optional orientation. Add `cliff` to the authored kind set. Center definitions
have no boundary side. Cold definitions remain concrete-item-free.

Port all active in-process callers before deletion, including maps,
battlefield definitions/builders, environment item builders, environment
item classes, direct constructors, `place_on_grid`, and WallTorch mount. Do not
touch deprecated editor save/load, server projections, SDKs, or generated
transport artifacts. A blocked module is a migration obligation only when its
maintained subject and imports belong entirely to the active in-process
runtime; a server/SDK/content-system blocker is outside this phase.

## 8. Ordered edge derivation after the hard cut

The corrected `get_world_edge(source, destination)` already preserves order,
height intervals, exact facing-side membership, off-side exclusion, and local
diagnostics. Phase 3 changes only its provider mechanics:

1. validate two live cardinally adjacent endpoint Tiles;
2. keep the existing canonical adjacency key and ordered endpoint facts;
3. read only source center bands plus source exact facing side while the legacy
   center-provider bridge remains, then delete that bridge in the hard cut;
4. read only destination center bands plus destination exact entry side while
   the bridge remains, then delete it;
5. after activation, structural contributions come only from exact facing
   boundary-band providers whose `get_boundary_structure()` is non-`None`;
6. call that capability once per unique provider in deterministic UUID order;
7. retain an open door contribution with empty channels;
8. omit attachments with no boundary structure from structural contributions,
   while the contact route query still exposes them;
9. use committed placement base/top; and
10. remove intrinsic Tile-side and center legacy directional contributions
    when their old authorities are deleted.

An off-side provider on either endpoint never enters this transition. No map
scan, all-object endpoint scan, edge cache/index, or persisted edge row is
allowed.

### 8.1 Channel evaluation

Use exactly `MOVEMENT`, `OPTICAL`, and `PROPAGATION`. Implement one internal
pure evaluation of the existing ordered view; do not create parallel policy
answers.

For `I -> J`, a channel transmits only when both layers transmit it. Search
order for a blocking provider is exit layer, then entry layer, UUID order
within each layer.

- walking first applies existing support/progressive-surface rules, then only
  movement contributions intersecting
  `[min(source_height, destination_height),
  max(source_height, destination_height) + 1)` block;
- ordinary optics uses every `OPTICAL` contribution in both layers and ignores
  vertical interval;
- light-source geometry uses that same optical transition;
- propagation uses every `PROPAGATION` contribution in both layers and
  ignores vertical interval; and
- nonwalking modes retain their current 2D authored-barrier behavior until an
  explicit actor-altitude model exists.

Current wall/door/cliff channels are physically symmetric, so passability can
be symmetric even though the view and observation route are ordered. Do not
infer one-way mechanics from placement side or orientation.

Two opposing walls remain two objects in two layers. Removing/opening only one
does not make the transition passable while the other blocks.

For revision settlement, the transient movement answer is not merely
"some MOVEMENT provider exists." Evaluate both:

- the ordinary walking answer for the current support interval and progressive
  surface rule; and
- the retained height-insensitive authored-barrier answer used by current
  nonwalking modes.

Comparing that pair prevents redundant same-effect blockers from advancing the
movement revision while still detecting a provider that moves between height
bands and changes walking despite leaving nonwalking blocked. Persist no
movement signature or second policy state.

The same public transition query may accept the narrowly named optional
`treat_closed_doors_as_interactable=False` rule input for the existing
scenario-compatibility hypothetical walk. Ordinary gameplay leaves it false.
When true, the same private GridMap layer-derivation pass which already calls
each provider's `get_boundary_structure()` once classifies a provider as
ignorable only when that already-computed kind is
`BoundaryStructureKind.DOOR` and its explicit spatial-open state is closed. It
feeds the resulting transient local UUID set directly to the one pure
evaluator; the caller never constructs or receives that set and no provider is
resolved twice. Walls, surfaces, both ordered layers, support/height rules, and
the diagonal bridge rule remain active. The set is not persisted, cached,
published, or used to create a second transition answer, and no map scan is
allowed.

### 8.2 Center and condition topology remains independent

This hard cut removes directional projections, not intrinsic whole-cell
mechanics. A solid wall Tile or other rule which blocks its entire cell remains
an explicit center-cell movement/optical/propagation input; never translate one
whole-cell blocker into four invented boundary objects. Materials and surfaces
do not silently select channels.

SpatialConditions remain independently owned and Tile-indexed. Their
observer-relative `optical_obscurement` is applied only by
`SpatialSensesSystem`; it never becomes an edge contribution and never causes
ordinary light transport to recompute. Add the master plan's neutral default-
false `BaseCondition.blocks_physical_optics_at(position)` capability if it is
not yet present. An active condition returns true only for its indexed
footprint when an explicitly authored mechanic truly prevents physical
transmission. That condition remains the source owner and contributes through
the center/route optical query.

For activation, footprint transition, movement, and removal of a physically
optical condition, its existing condition-owned transition must:

1. capture the aggregate physical-optics answer across
   `previous_positions | current_positions` from the old indexed state,
   including overlapping Tile, object, and other-condition blockers;
2. commit the condition footprint/index change and derive the aggregate answer
   again from the new indexed state;
3. bump the optical revision once only when at least one answer changes;
4. radius-filter and deduplicate the relevant active light sources across all
   changed positions, then recompute each source once; and
5. publish the existing causal light facts on the condition transition's
   existing lineage before the completed `SpatialEffectChangeEvent` reaches
   sensory reduction.

Overlap which leaves the aggregate answer unchanged causes no optical bump or
light recompute. Use the existing condition transition hooks and light methods;
do not add an EventQueue callback, event type, cache, or condition index. Do not
reclassify observer-relative fog or magical darkness as physical optics, and
do not copy any condition into placement bands, `BoundaryStructure`, or
`WorldEdgeView`.

## 9. Mechanical consumer hard cut

Before any legacy directional field is deleted, route every real consumer to
the ordered transition answer:

1. cardinal and diagonal movement bridges, `can_transition`, paths,
   voluntary/forced movement, and collision reporting;
2. ordinary FOV, visual line of sight, `contact.visual`, and light-source FOV;
3. propagation transitions/FOV, line of effect, total cover, AoE filtering,
   jump/physical reach, and nonvisual special-sense reach;
4. subjective navigation knowledge; and
5. boundary-object contact exposure.

Before Slice 3.3, freeze a caller ledger assigning every migrated consumer to
exactly the existing meaning it needs:

- traversal and collision use `MOVEMENT`;
- visual admission and `contact.visual` use `OPTICAL` plus objective light and
  the observer's sense rules;
- line of effect, total cover, AoE, jump, and physical/nonvisual reach use
  `PROPAGATION`; and
- awareness-only targeting/action discovery reads typed contact existence,
  while an authored visible-target rule reads `contact.visual`.

`scenario_compatibility` is the one separate hypothetical-connectivity row: it
uses `MOVEMENT` through that same public transition query with
`treat_closed_doors_as_interactable=True`. Delete its duplicate cell/side/
cardinal/diagonal transition implementation. It never makes ordinary movement
treat a closed door as open.

Do not route all targeting through propagation, treat physical cover as merely
optical, or add a generic policy/facade to decide for callers. Each maintained
rule keeps its existing public meaning.

Preserve the existing diagonal one-of-two cardinal bridge rule. Do not create
diagonal edges or infer corner walls.

Replace no-argument global barrier discovery with a bounded query accepting
the already-known candidate/geometric footprint. It inspects only those center
cells and incident ordered edges. Delete the global barrier cache. The exact
transition query remains authority; the bounded set is acceleration only.

Directional FOV selection remains bounded to the query footprint. Zero edge
blockers may use the symmetric cell path; one or more uses the established
directional/supercover path. Do not add per-ray dependency indexes.

## 10. Ordered near-side contact reduction

Add one neutral derived GridMap route query over a source cell, one cardinal
direction, and one existing `WorldEdgeChannel` restricted to `OPTICAL` or
`PROPAGATION`. It returns the deterministic reached prefix of at most two UUID
layers:

1. source Tile's exit-side objects, including nonstructural attachments; and
2. when a neighbor exists and the exit layer transmits the requested channel,
   the neighbor Tile's entry-side objects, including the blocker which stops
   further reach.

An outer side returns only its owner layer. This query returns copies/frozen
UUID tuples and owns no state. Do not add another edge/contact dataclass,
registry, reverse index, or parallel query family. Invoke it separately for
visual `OPTICAL` and nonvisual `PROPAGATION` evidence, using the one pure
Section 8.1 channel evaluator rather than duplicating transmission policy.

For visual reduction from `I` toward `J`:

1. expose every object in `I`'s exit layer to the existing exact contact
   resolver;
2. treat co-located occupant and attachments as one co-visible layer;
3. stop before the entry layer if the exit layer blocks optics;
4. otherwise expose every object in `J`'s entry layer;
5. stop before the far Tile/center contents if the entry layer blocks optics;
6. reveal the far Tile/content only when both layers transmit optics; and
7. reverse the route order for `J -> I`.

Nonvisual route exposure uses the analogous ordered propagation answer.
Across one observer recompute, locally aggregate qualifying route cells by
provider UUID across visual, blindsight, and tremorsense footprints. Resolve
each UUID once, deterministically. Evaluate range, route, stealth,
invisibility, and each sense against qualifying route evidence. For visual
contact of either reached boundary layer, use the established effective-light
evidence of the last transmitting near-side/source cell; do not test the entry
provider against the hidden/dark destination Tile and do not add boundary-light
state. Write the committed placement position into the unchanged
`PerceivedContact(position, visual, special_senses)` value. Merge with
`visual=any(...)` and canonical enum-ordered special-sense union.

Do not add the far Tile to `visible`/`seen` merely to expose its entry boundary.
Do not enumerate far center objects/entities across a stopped route. Do not
restore object-owned `is_perceivable_by` or a second contact schema.

Observer candidates come from existing endpoint subscriptions/reverse indexes
and exact spatial hints. No all-observer scan.

## 11. Mutation, caches, light, and events

For runtime side placement, move, orientation, removal, and door state change:

1. identify the owner side and zero or one live incident adjacency;
2. capture every complete affected ordered transition answer before mutation;
3. precompute provider values which may fail;
4. validate local placement/state admission;
5. commit the existing provider state or owner Tile bands/reverse placement;
6. derive the complete transition after mutation;
7. compare aggregate optical/propagation answers and both effective movement
   answers across both layers;
8. bump each changed existing channel revision/cache family once;
9. begin the existing spatial lifecycle with exact after-values and bounded
   `SensesUpdateHint` endpoints/channels;
10. let the existing declaration-time optical callback radius-filter active
    sources, diff footprints, and publish causal light children;
11. let existing EFFECT handlers settle; and
12. let `SpatialSensesSystem` reduce the complete objective result at the
    existing pre-completion seam.

If A and B on opposing sides both block and A is removed/opened, aggregate
topology remains blocked. Movement/optical/propagation revisions do not change,
and no optical light topology recompute occurs. The ordinary object lifecycle
and endpoint hint still run so contact reach changes from terminal A to newly
reached B.

`SensesUpdateHint` endpoint positions select contact recomputation for every
boundary/attachment lifecycle. Its changed-channel/recompute flags describe
only aggregate transition answers which actually changed. Therefore the
redundant-blocker case carries endpoint evidence without falsely requesting
movement, physical-optical/light, or propagation invalidation.

An internal side mutation hints both live endpoints; an outer side hints only
the owner. A nonstructural attachment also hints its incident endpoints for
contact admission/removal even though no channel changes. Hints remain
nonauthoritative acceleration.

Relocation preserves the accepted departure-then-arrival lifecycles and
two-step topology/light/sensory settlement. Do not add a batch event system.

On prepublication failure, restore provider state, local bands/reverse row,
revisions, and source-owned light contributions within the accepted bounded
rollback. Derived caches may be cleared. No false fact survives.

### 11.1 Door state

Use the surviving door's existing action/lifecycle. Validate close admission
before `is_open` changes. Open/close preserves placement/UUID, publishes one
`OBJECT_CHANGED`, changes only differing channel revisions, does not relocate
anchors/lights at the same XY, and settles optical light geometry before
sensory pre-completion.

### 11.2 Cold rebuild

`rebuild_object_placements()` remains event-suppressed cold/load work before
observers and the sole `WorldInitializedEvent`:

1. validate/stage the full local-band/reverse bijection;
2. retain legal opposing side occupants and reject same-local-side collision;
3. deduplicate old/new incident adjacencies;
4. commit placements/bands and compute aggregate channel deltas across both
   ordered layers;
5. settle each changed revision and radius-filtered active-light footprint
   once;
6. roll back all objective state/event cursors on failure; and
7. publish no object, light, or sensory lifecycle.

If a caller requests live/eventful rebuild, stop. Do not manufacture per-object
load events or a batch lifecycle.

### 11.3 Preserve movement-step and turn-start ownership

Phase 3 changes topology inputs, not movement or perception ownership. Every
accepted movement step still follows its existing precommit movement EFFECT,
objective Entity/GridMap commit, LEFT then ENTERED spatial lifecycles, carried
light settlement, and `SpatialSensesSystem` pre-completion reduction. EFFECT
mechanics continue to read objective `Entity.position`; `Senses.position`
remains reducer-owned and may still contain the prior projection until its
sensory delta settles. Do not move FOV/light/contact work into Encounter or an
item action.

`TURN_START` remains an actor-only candidate in `SpatialSensesSystem`. It emits
a causal sensory delta only when the actor's visual/contact projection changes,
and a clean turn neither emits a no-op delta nor dirties clean navigation.

## 12. Event, item, and replay hard cut

Replace `ItemDirectionalStructureState` with the existing semantic value:

```python
ItemState.boundary_structure: BoundaryStructure | None
ItemObservationState.boundary_structure: BoundaryStructure | None
```

Add one exact semantic after-value to the existing spatial object fact:

```python
SpatialChangeEvent.object_boundary_structure: BoundaryStructure | None
```

Use this matrix:

| Operation | After-value |
|---|---|
| initial placement | current structure, or `None` for center/attachment |
| relocation departure | `None` |
| relocation arrival | current structure, or `None` |
| orientation/mechanical state change | current structure, or `None` |
| terminal removal | `None` |

`previous_placement` remains old spatial authority on departure/removal.
Arrival/change carries committed placement. Add no previous-structure field.
Existing center blocking after-values remain center mechanics, not boundary
topology.

Delete authoritative `SpatialChangeEvent.directional_*` map fields after all
consumers migrate. `SensesUpdateHint` may retain bounded endpoint/channel hints
only. Add ordinary Pydantic identity/shape validation, no custom serializer or
objective reducer framework.

Delete `WorldTileState.movement_open`, `optical_open`, and `propagation_open`.
Bootstrap/replay derives topology from each exact `WorldObjectState.placement`
plus `item.boundary_structure`. Keep the one actor-free
`WorldInitializedEvent` cold boundary and ordinary later Entity deployment.

## 13. Safe execution order

Only the following checkpoints may be accepted as green. Local coding commits
inside the hard cut may temporarily be red; no dual-authority state may be
handed off.

### Slice 3.0 — freeze and classify

1. Verify all frozen hashes and 94 accepted Slice 3.1 manifest members.
2. Freeze collection, runnable lanes, blocked signatures, and timings.
3. Freeze every caller of Section 14 deletion symbols.
4. Freeze the complete door-side/product ledger.
5. Add only characterization tests for capabilities that must survive.
6. Stop before production edits for supervisor approval.

### Slice 3.1 — independent center-occupant cut

1. Add reused fixed-spec behavior only if it eliminates real duplication.
2. Port every ledgered physical center blocker and authored builder.
3. Preserve center movement/optical/propagation behavior.
4. Prove collision, failed admission, events, replay, and locality.
5. Freeze and review this independent green slice.

### Slice 3.2 — prepare the atomic boundary ledger

1. Finish exact wall/door/blocked-direction expansion tables.
2. Resolve every no-side door caller or stop for product direction.
3. Freeze the Section 9 consumer-classification ledger.
4. Freeze active schema/content caller dispositions and explicitly list the
   deferred transport/presentation exclusions.
5. Prepare target tests and deletion list without activating a second runtime
   authority.
6. Stop for supervisor approval of the complete hard-cut ledger.

### Slice 3.3 — atomic boundary/topology hard cut

Land together before calling the slice green:

1. wall/door placement specs and computed structures;
2. every active authored/builder/direct caller and one-object-per-side
   expansion;
3. door consolidation;
4. ordered edge provider source switched to `BoundaryStructure`;
5. every movement/FOV/light/propagation consumer switched to both layers;
6. bounded barrier/FOV paths;
7. ordered near-side contact reduction;
8. aggregate revision/light/event settlement;
9. condition-owned physical-optics capability and aggregate settlement;
10. item/spatial/bootstrap schema migration;
11. active Python content identities required for in-process construction; and
12. deletion of all active legacy directional authorities/callers in Section
    14.

Do not hand off a state where new objects no longer feed old booleans while
consumers still read them, or where both answers remain writable.

### Slice 3.4 — cliff and attachment cut

1. Add/authenticate the explicit proving cliff on the authoritative ordered
   topology.
2. Port WallTorch and every ledgered fixture to explicit nonoccupying sides.
3. Prove height/channel independence, same-side coexistence, legal opposing
   occupants, outer-boundary contact, attached light, in-process Pydantic
   `WorldInitializedEvent`/`WorldObjectState` round-trip, cold rebuild, and
   bootstrap. Deprecated editor/transport save-load is not a gate.
4. Do not infer cliff existence or attachment side.

### Slice 3.5 — deletion and certification

1. Prove Section 14 zero-reference gates.
2. Run all active in-process behavior/event/dependency/locality and scoped
   collection lanes.
3. Freeze an exact implementation manifest and execution ledger.
4. Obtain independent correctness and anti-slop implementation approvals.

## 14. Required deletion ledger

At completion, active Python has no gameplay use of:

- Tile intrinsic `border_*`, `optical_border_*`, `propagation_border_*`;
- Tile object-derived directional border fields;
- `_intrinsic_border`, `_derived_border`, `set_intrinsic_border`,
  `set_object_border`, and directional `allows_direction(s)`;
- BaseItem's twelve directional blocking fields and their helper/setter APIs;
- neutral `BaseBlock.blocks_directional_movement`,
  `blocks_directional_optics`, and `blocks_directional_propagation` hooks;
- `get_objective_directional_structural_channels`;
- `ItemDirectionalStructureState` and `directional_structure` fields;
- `_OBJECT_BORDER_FIELDS`, `_directional_block_map`,
  `recompute_tile_directional_blocking`, subjective Tile border rebuilding, and
  `set_tile_directional_border`;
- authored `blocked_directions` fields/parameters/defaults;
- the `scenario_compatibility` directional-hook caller, ported to the one
  ordered public transition query's bounded closed-door-interactable input;
- its duplicate `_topology_cell_walkable`, `_topology_side_allows`,
  `_topology_cardinal_transition_allows`, and `_topology_transition_allows`
  implementations;
- `WorldTileState` directional-open tuples;
- authoritative `SpatialChangeEvent.directional_*` map fields;
- active `DoorObject`, duplicate actions/builder/catalog construction
  paths; unused deprecated/presentation binding rows are deferred;
- no-argument global barrier discovery/cache; and
- object-owned `is_perceivable_by` or subjective boundary bypass hooks.

Historical documents and explicit deletion-gate strings are not gameplay
references. Do not satisfy old tests with aliases, facades, or dual fields.

## 15. Public behavior gates

Tests use public commands, queries, typed values, completed events, replay,
resolved light, and the existing structured diagnostics. No private band/cache
inspection, monkeypatch call counts, AST/source layout, or arbitrary sleep.

### 15.1 Placement and structures

- same-Tile/same-side overlapping occupants reject before mutation/facts;
- opposing side occupants coexist at equal heights and retain distinct UUIDs,
  placements, events, semantic states, and render facts;
- moving/orienting/removing one side leaves the opposing side exact;
- one wall/door instance owns one side;
- multi-side rows expand into distinct UUIDs in canonical order;
- open door remains placed/contributed with empty channels;
- attachment shares local bands without becoming occupant;
- outer attachment remains queryable with one live endpoint; and
- center blockers collide only according to explicit specs.

### 15.2 Ordered topology and height

- forward/reverse views share key and swap ordered layers/endpoints;
- A on source exit and B on destination entry appear only in their layers;
- off-side providers are absent;
- both layers must transmit each channel;
- an OPTICAL-only exit blocker exposes only the exit layer visually while the
  PROPAGATION route still reaches the entry layer, and a PROPAGATION-only exit
  blocker produces the converse channel-selective result;
- with A and B blocking, removing/opening only A leaves aggregate topology and
  channel revisions unchanged but changes reached contact layer A -> B;
- walking alone applies height intersection over both layers;
- lower `[0,2)` cliff does not block height-2 upper walking, while `[2,4)` wall
  does;
- optics/propagation ignore height and obey authored channels;
- elevation alone never creates a cliff or optical blocker;
- whole-cell blocking remains center-cell policy and is not expanded into four
  synthetic boundary objects; and
- condition-owned physical optics and observer-relative obscurement retain
  their separate lifecycle/cache behavior without entering side layers.

### 15.3 Movement, optics, light, propagation

- standard movement/path/forced-movement behavior remains exact;
- ordinary movement remains blocked by a closed door, while the public
  scenario-compatibility check treats that same door as interactable/openable;
  replacing it with a wall keeps the compatibility route blocked;
- diagonal bridge policy remains exact;
- wall optics blocks ordinary FOV and light geometry through the same answer;
- movement-only, optical-only, and propagation-only providers affect only the
  authored channel;
- bounded propagation discovery returns exact results with no global cache;
- door open/close bumps each actually changed revision once;
- moving/removing/rebuilding structures updates active shadows; and
- cold rebuild emits no runtime lifecycle.

The existing per-step movement proofs must also show that objective movement,
carried light, FOV, typed contacts, and the reducer-owned sensory delta settle
before step completion. Existing turn-start proofs must show actor-only
recomputation, a causal delta only on change, and no delta/path dirtying on a
clean turn.

### 15.4 Ordered subjective reduction

- opaque exit layer exposes exit objects but hides entry layer/far content;
- transparent exit plus opaque entry exposes both reached layers but not far
  Tile/center contents;
- reverse observation swaps the reached order;
- occupant and attachment sharing a layer are both exposed;
- one provider reached through multiple routes yields one deterministic
  contact;
- a lit near/source cell exposes an opaque entry-layer wall visually even when
  the hidden destination Tile is dark, while contact position remains the
  provider's committed placement;
- nonvisual route yields canonical blindsight/tremorsense contact without
  falsely visible endpoints;
- darkness, darkvision, truesight, stealth, invisibility, blindsight, and
  tremorsense remain in the shared resolver; and
- perceived/unperceived observers receive identical objective topology.

### 15.5 Events and replay

- place/change/remove carry exact placement and structure after-values;
- relocation departure has no current structure; arrival has committed state;
- door open/close is one `OBJECT_CHANGED`, not remove/place;
- same-XY state change does not relocate anchor/light;
- optical light children and sensory deltas settle before outer completion;
- WorldInitialized reconstructs both opposing placements and semantic states
  with no Tile directional mirror; and
- no generic Event/EventQueue field or objective reducer is introduced.

### 15.6 Failure and locality

- collision/provider/door-close failure preserves item state, placements,
  bands, revisions, light, contacts, and event cursor;
- moving one movement provider from a nonintersecting lower band to an
  intersecting upper band advances movement revision even though the
  height-insensitive nonwalking answer stays blocked, while removing one of
  two same-effect blockers does not advance it;
- overlapping physical-optics conditions which leave aggregate transmission
  unchanged do not bump optical revision or recompute lights, while a real
  aggregate footprint change settles each relevant active source once before
  sensory reduction;
- edge query work depends only on two endpoint facing/center stores and unique
  providers;
- route exposure inspects at most local incident layers;
- fixed-radius FOV/propagation work is independent of distant map area;
- light work is active-source radius scan plus footprint diff, not Tile scan;
- observer eager work uses indexed candidates, not all observers; and
- distant unused Tiles/objects/conditions/observers do not change local eager
  diagnostics.

## 16. Validation and evidence

The implementation ledger records exact commands, selectors, counts, timings,
failures, authorized deletions, and final hashes.

Required sequence:

1. compile and `git diff --check` for changed files;
2. exact new structure/placement/ordered-edge tests;
3. movement/path/forced-movement/elevation lanes;
4. FOV/light/senses/propagation/AoE lanes;
5. in-process item/action/content/bootstrap/event/replay lanes;
6. spatial-anchor/concentration/WallTorch/Continual-Flame regressions;
7. accepted 286-capability, 62-spell, and 42-architecture baselines;
8. dependency and Section 14 deletion gates;
9. structured locality plus repeated warmed timing only where diagnostics
   cannot expose the relationship;
10. active-runtime collection comparison against the exact test paths frozen
    in the corrected Slice 3.2 ledger; and
11. final scoped active Python/JSON manifest with every member hash.

A blocked module keeps a caller migration obligation only when it can be made
to collect using active in-process dependencies alone. Server/SDK/deprecated
modules and tests are excluded, not restored. No collecting active capability
disappears and no active selector is removed except an exact reviewed
replacement/deletion ledger.

## 17. Stop conditions for Luna

Stop and report rather than improvise if:

- any door/fixture caller lacks enough maintained evidence for exact side(s);
- an external content identity must survive beyond repository evidence;
- a movement mode needs actor altitude to preserve behavior;
- existing lifecycle/pre-completion ordering cannot settle objective light and
  sensory state correctly;
- replay appears to require a new reducer framework;
- any proposed fix would enter a deprecated server, editor, SDK, generated
  transport, or cross-language artifact;
- locality appears to require a new edge/light/ray index;
- a test would require private/source-layout coupling; or
- Phase 4 Entity occupancy appears necessary.

Do not broaden Phase 3 to answer those questions.

## 18. Completion definition

Phase 3 is complete only when:

1. Section 15 public gates pass;
2. Section 14 active gameplay references are zero;
3. Tile bands and one reverse placement remain the only object-position
   authority;
4. opposing side occupants remain legal and ordered layers remain distinct;
5. `WorldEdgeView` remains derived/nonauthoritative;
6. movement/optics-light/propagation use the three-channel model through both
   ordered layers;
7. height affects boundary mechanics only for movement;
8. ordered contact reduction leaks no far content;
9. no EventQueue/reducer/controller/compatibility/index layer was introduced;
10. active-runtime collection/locality/replay evidence has no unapproved loss;
11. an exact implementation manifest is frozen; and
12. independent correctness and anti-slop reviewers approve that exact
    manifest.

## 19. Review record

| Review | Revision | Verdict | Notes |
|---|---|---|---|
| Correctness/executability | `495914ec28df82b553f23347f2a29eb9be7764f21039e5619e083c1a20b4e7de` | APPROVED | independent sides, ordered mechanics, caller semantics, atomic cut, events, replay |
| Optics/light/cache/anti-slop | `495914ec28df82b553f23347f2a29eb9be7764f21039e5619e083c1a20b4e7de` | APPROVED + ANTI-SLOP APPROVED | channel-qualified contacts, near-side light, condition optics, locality, no extra authority/framework |
| Active-runtime scope correctness | `ecafd884071bfd0409355611cc844e6006ffc51cc8c1f2a5c93d1add88fabe3a` | APPROVED | active caller/capability completeness, baseline and partial recovery |
| Active-runtime scope anti-slop | `ecafd884071bfd0409355611cc844e6006ffc51cc8c1f2a5c93d1add88fabe3a` | APPROVED + ANTI-SLOP APPROVED | no server/SDK/content-system restoration or transport compatibility layer |
