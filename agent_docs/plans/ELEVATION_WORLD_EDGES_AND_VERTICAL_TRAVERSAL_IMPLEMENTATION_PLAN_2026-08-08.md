# Elevation, Canonical World Edges, and Vertical Traversal — Lean Unit 4 Implementation Plan

**Status:** FROZEN REVISION 6 CANDIDATE — INTERNAL AND EXTERNAL PLAN REVIEW REQUIRED

**Date:** 2026-08-08

**Unit:** 4, continuing the completed movement-settlement work

**Scope:** one-surface-per-`(x, y)` elevation mechanics; canonical reciprocal
adjacent-edge identity; progressive stairs and ramps; cliffs; height-aware
movement, range, reach, and threat; corrected Jump landing settlement; and one
atomic connector family for ladders, ropes, lifts/elevators, vertical stairs,
and authored passages

## 1. Decision

This is one coherent implementation unit with three bounded checkpoints. It is
not three independently designed features and it is not one unreviewed giant
patch.

```text
tile elevation + canonical adjacent edge
                    |
                    v
      ordinary movement/range/threat
             /                \
            v                  v
 progressive stairs/ramp   cliff and Jump
                                  \
                                   v
                         atomic vertical connector
```

The unit is intentionally a **lean 2.5-D rules feature**:

- a grid coordinate identifies exactly one support tile;
- a tile owns one elevation;
- two walkable surfaces can never share the same `(x, y)`;
- stairs and ramps are several adjacent tiles with progressively changing
  elevations;
- a ladder, rope, lift/elevator, vertical stair, or passage is one authored
  endpoint-to-endpoint transfer;
- no general `(x, y, z)` position type, stacked floor, roof system, simulated
  moving platform, or continuous vertical occupancy is introduced.

The plan must be externally accepted before implementation. Checkpoints A/B
receive one implementation review together because they establish the shared
rules. Checkpoint C receives the final implementation review against the
playable proving battlefield.

## 2. Existing truth and current gaps

The current engine already owns useful foundations:

- `Tile.height` exists in `dnd/core/base_tiles.py` and documents elevation in
  five-foot increments;
- `GridMap` owns tiles, directional channel queries, pathfinding, revisions,
  occupancy, object indexes, spatial events, and `clear()`;
- `Move`, `Swim`, and `Fly` use the corrected Move-family per-edge settlement;
- `Entity.update_entity_position()` is the registry-aware position mutation;
- `StepMovementEvent` is the movement-reaction boundary;
- `DirectionalWall` and `DirectionalDoor` expose exact directional structural
  contributions;
- `Size` is a dependency-neutral creature category;
- battlefield definitions/builders are product content rather than test-only
  fixtures.

Elevation is not currently mechanical:

- `Senses.get_distance()` and `get_feet_distance()` use only `(x, y)`;
- weapon and spell range checks commonly call that 2-D helper;
- `GridMap.can_transition()` ignores `Tile.height`;
- path costs use destination terrain cost without elevation authorization;
- threatened positions and opportunity attacks ignore elevation and creature
  vertical extent;
- `APITile`, map-editor patches, saved-map load, and battlefield previews do
  not carry tile elevation;
- Jump treats its disclosed planar line as successive position commits and
  debits movement after each arrival;
- there is no connector registry, endpoint index, or connector action.

On a current map, an actor may walk between adjacent height `0` and height `20`
tiles, melee across the same vertical separation, and threaten the neighboring
ground cell. This unit closes that gap without introducing a new game runtime.

## 3. Included scope

### 3.1 Canonical adjacent-edge identity

- one frozen canonical identity for a cardinal pair of neighboring cells;
- reciprocal lookup: east from A and west from B resolve the same identity;
- an immutable derived edge view of objective endpoint/elevation facts and
  authored structural channel contributions;
- exact structural contributors, including stable door/wall object UUIDs;
- stable identity across door open/close and no-op state changes;
- no duplicate topology registry whose lifecycle can drift from GridMap;
- clear/remove/replace and map snapshot behavior.

### 3.2 Tile elevation and progressive terrain

- one integer elevation measured in five-foot increments;
- typed terrain surface kind: ordinary, stairs, or ramp;
- optional cardinal slope axis/direction for stairs/ramp authoring;
- same-elevation ordinary walking;
- maximum one elevation step (five feet) per progressive stair/ramp edge;
- no diagonal ascent/descent in this unit;
- an unmarked nonzero adjacent elevation difference is a cliff for walking;
- stairs/ramp entry retains the existing destination terrain movement cost;
- elevation adds no second hidden stairs tax.

### 3.3 Height-aware spatial distance

- point/support distance for movement and position/object targets;
- creature-volume distance for entity targets;
- exact tactical vertical extent by `Size`;
- flat-map mechanics, legal actions, paths, costs, range results, and threat
  results remain equivalent; DTO payloads intentionally gain typed elevation
  fields and are not promised byte-identical serialization;
- weapon range, melee reach, single-target spell/action range, object
  interaction range, threat, opportunity-attack exposure, Jump range, and
  target discovery use the correct distance owner.

### 3.4 Movement modes

- Walk: level cells or explicitly aligned stairs/ramp edges only;
- Swim: retains present water/terrain semantics and may not cross an unmarked
  elevation discontinuity;
- Fly: may cross an adjacent cliff edge, paying exact support-to-support
  distance rather than a flat five feet;
- Burrow remains supported by GridMap and may not gain unreviewed vertical
  behavior;
- forced movement remains mechanically separate and must fail rather than
  push a creature through an unauthorized cliff edge unless its action owns a
  separately accepted displacement rule.

### 3.5 Jump

- height-aware landing distance and affordability;
- immutable requested landing and accepted direct-arc evidence;
- one objective direct-arc leg from takeoff to landing, not ground occupancy at
  every planar cell beneath the arc;
- the disclosed planar line remains presentation/observation geometry only;
- ground entry/hazard effects occur at landing only;
- opportunity attacks compare real takeoff threat with accepted landing threat
  and resolve at the real takeoff position;
- exact movement debit occurs before the landing mutation;
- landing revalidation occurs after reactions and before debit;
- death, displacement, lost action permission, blocked landing, or insufficient
  movement settles truthfully without fabricated arrival;
- one committed `StepMovementEvent` represents the accepted non-adjacent
  `DIRECT_ARC` leg; PATH steps remain adjacent;
- Jump remains its existing action/content identity and does not become a
  transport command or connector.

Jump opportunity attacks use one deliberately lean rule: an accepted Jump that
would leave a reactor's reach provokes while the jumper is still objectively
at takeoff. The attack therefore uses the real entity position and ordinary
Attack validation. Intermediate arc cells never become virtual entity
positions or new reaction authorities.

### 3.6 Atomic traversal connectors

One connector family represents:

- ladder;
- rope;
- lift/elevator;
- steep or vertical stair transfer;
- authored passage.

The executor does not switch on display names or presentation kinds. Each
connector authors its exact directionality, enabled state, action cost,
movement cost, source-exit opportunity-attack policy, endpoints, and
presentation identity.

The transfer is atomic:

```text
interact at current endpoint
    -> validate exact connector revision/digest
    -> validate direction, source endpoint, and destination tile
    -> publish the typed source-exit reaction boundary when authored to provoke
    -> revalidate actor and destination
    -> consume exact accepted costs
    -> commit destination through Entity.update_entity_position()
    -> run ordinary destination arrival effects
    -> publish truthful completion
```

There is no simulated travel duration, platform movement, passenger list,
waiting state, intermediate vertical cell, or background task.

### 3.7 Product proving battlefield

Add one maintained authored battlefield whose runtime builder and cold preview
contain the geometry below. Add one maintained product scenario/encounter
composition that deploys the hostile actors onto it; actors are not falsely
made fields of `BattlefieldDefinition`:

- a closed directional door and reciprocal wall edges;
- a level combat area;
- a progressive stair run;
- a progressive ramp run;
- an unmarked cliff edge;
- a jumpable gap with a landing hazard;
- a ladder;
- a rope;
- a lift/elevator;
- a vertical stair transfer;
- a passage;
- scenario-deployed hostile actors positioned to exercise vertical
  melee/ranged range and OA;
- enough movement budget and legal actions to play the scenario through
  ordinary engine/Encounter APIs.

The battlefield and its scenario composition are product content. They must not
live only in a pytest fixture.

## 4. Explicit non-goals

This unit does **not** add:

- stacked floors at the same `(x, y)`;
- a three-coordinate entity position;
- roofs, ceilings, finite wall height, flying altitude selection, falling, or
  hovering between support surfaces;
- continuous physics or collision volumes;
- simulated moving elevators;
- elevator queues, timers, passengers, capacity, or doors;
- climbing-speed progression or Athletics checks for arbitrary wall climbing;
- arbitrary procedural connector scripting;
- height-aware light, shadow, FOV, cover, or seeing over walls;
- vertical AoE volumes or elevation-filtered spatial-effect footprints;
- frontend animation code;
- a server/runtime reducer, scheduler, journal, retry protocol, lease, worker,
  thread, queue, or persistence framework;
- deterministic RNG;
- a second movement executor for ordinary Move/Swim/Fly.

For this unit, directional vision/light/propagation walls remain infinitely
tall. Area footprints remain the current planar rules. Those limitations must
be documented and the proving battlefield must not falsely claim otherwise.

## 5. Exact coordinate and distance rules

### 5.1 Elevation units

`Tile.height` remains the stored compatibility field:

```python
elevation_feet = tile.height * 5
```

The new code calls it elevation in methods, DTO descriptions, and logs. It does
not introduce a second `elevation` value on `Tile`.

Negative elevations are valid. `bool` is not accepted as an integer elevation.
NaN/infinity cannot enter because the stored type is an exact integer.

### 5.2 Tactical vertical extent — explicit engine rule

D&D size categories specify tactical ground space, not an official creature
height. Unit 4 deliberately defines the following **engine rule** for vertical
range/reach/threat only. It is tactical occupied vertical space, not anatomy
and not a claim about tabletop RAW:

| Size | Vertical extent |
|---|---:|
| Tiny | 2.5 ft |
| Small | 5 ft |
| Medium | 5 ft |
| Large | 10 ft |
| Huge | 15 ft |
| Gargantuan | 20 ft |

This mapping belongs in a dependency-neutral pure module. No spell, action,
server mapper, or frontend may reproduce it.

At support elevation `z`, a creature occupies the closed interval:

```text
[z, z + tactical_vertical_extent(size)]
```

The vertical clearance between two intervals is zero when they overlap.

Creature size does **not** authorize movement across an unmarked elevation
change. A Gargantuan creature and a Tiny creature are equally blocked from
walking across a cliff edge. Size affects entity-to-entity range, reach, and
threat only; ordinary movement uses the exact edge rule in §8.

### 5.3 Preserve the existing planar metric

The current flat-grid result is:

```python
planar_feet = int(sqrt(dx * dx + dy * dy)) * 5
```

Unit 4 must not silently change every diagonal-range result. Elevation extends
that established metric with this explicit engine rule:

```python
distance_feet = max(
    planar_feet,
    ceil(vertical_clearance_feet / 5) * 5,
)
```

Consequences:

- all equal-elevation results remain unchanged;
- a five-foot planar and five-foot vertical separation remains five feet;
- vertical separation cannot be ignored;
- distances remain integral multiples of five for existing APIs.

This is intentionally not true three-dimensional Euclidean distance. It is the
smallest vertical extension that preserves the engine's current flat results.
For example, a four-cell planar separation and three elevation steps of
vertical clearance is 20 feet under this rule (`max(20, 15)`), while true 3-D
Euclidean distance would be 25 feet. Focused tests freeze both that
discriminating case and its symmetric descending case so nobody later mistakes
the formula for Euclidean geometry.

Two explicit owners use the same pure calculation with different vertical
anchors:

1. **Support distance** uses zero-height points at the two tile elevations. It
   is used for Fly cost, Jump distance, position targets, and connector
   geometry validation.
2. **Creature-volume distance** uses both occupied vertical intervals. It is
   used for entity range, reach, and threat.

Movement across stairs/ramp is the deliberate exception: an authorized
adjacent progressive edge costs the destination tile's ordinary movement cost,
not support-distance plus terrain cost.

### 5.4 No hidden fallback

Missing source or destination tiles makes an elevation-aware rules query fail.
It must not silently use elevation zero. Presentation code may display an
unknown fact, but mechanics may not invent one.

## 6. Canonical adjacent-edge contract

Add a dependency-neutral leaf, tentatively `dnd/core/world_edges.py`:

```python
class ElevationSurfaceKind(str, Enum):
    ORDINARY = "ordinary"
    STAIRS = "stairs"
    RAMP = "ramp"


class SlopeAxis(str, Enum):
    NORTH_SOUTH = "north_south"
    EAST_WEST = "east_west"


class WorldEdgeChannel(str, Enum):
    MOVEMENT = "movement"
    VISION = "vision"
    LIGHT = "light"
    PROPAGATION = "propagation"


@dataclass(frozen=True, slots=True)
class AdjacentEdgeKey:
    first: tuple[int, int]
    second: tuple[int, int]

    @classmethod
    def between(cls, first, second):
        # Exact cardinal adjacency, canonical lexical endpoint order.
        ...


@dataclass(frozen=True, slots=True)
class WorldEdgeStructuralContribution:
    provider_uuid: UUID
    blocked_channels: tuple[WorldEdgeChannel, ...]


@dataclass(frozen=True, slots=True)
class WorldEdgeView:
    key: AdjacentEdgeKey
    first_tile_uuid: UUID
    second_tile_uuid: UUID
    first_height_steps: int
    second_height_steps: int
    elevation_delta_steps: int
    first_surface_kind: ElevationSurfaceKind
    second_surface_kind: ElevationSurfaceKind
    first_slope_axis: SlopeAxis | None
    second_slope_axis: SlopeAxis | None
    structural_contributions: tuple[WorldEdgeStructuralContribution, ...]
```

Names are tentative; ownership is binding.

`first`/`second` and the signed elevation delta always follow the canonical
lexical endpoint order. Directional queries orient this same fact at call time;
they do not manufacture a reciprocal copy. Structural contributions are unique
by provider UUID and sorted by UUID; reciprocal sides of one door/wall do not
become two identities.

### 6.1 Identity

The canonical coordinate pair is the encounter-local physical edge identity.
It requires no global UUID, map UUID, or persistence allocator. Facts from
different encounters are never joined without their encounter identity.

Door and wall object UUIDs remain stable contributor identities. Opening a
door changes effective channel state, never its edge key or provider UUID.

### 6.2 Derived view, not duplicate authority

`GridMap.get_world_edge(first, second)` derives one immutable **objective
structural** view from:

- the two exact tiles;
- both intrinsic directional sides;
- current object-derived directional contributions;
- tile elevation/slope facts;
- no requester, movement mode, occupancy, destination legality, or remembered
  subjective collision fact.

It may cache only this objective view behind existing spatial revisions. It
does not
maintain a second mutable topology graph that could survive `GridMap.clear()`
or disagree with the tile/object owners.

The view deliberately contains no effective passability boolean. Each
contribution records only its provider's objective current blocked channels
(for example a wall or closed door); it is not produced by calling
`blocks_directional_movement(..., requester=None, mode=WALKING)` as a fake
universal answer.

`can_transition` combines the reciprocal identity/elevation facts with the
existing contributor calls for the exact direction, movement mode, requester,
occupancy, destination legality, and subjective state. That contextual
decision is not a `WorldEdgeView`, is not cached as objective truth, and is not
projected as an edge fact. Vision, light, propagation, structural projection,
and editor serialization likewise use their existing contextual owners; the
view supplies identity and objective authored state, never default-mode game
authority.


Derivation costs O(1) endpoint lookup plus O(local contributors on those two
endpoints). No all-map scan or new provider graph is permitted.

### 6.3 Diagonals

Canonical edge keys are cardinal only. Existing diagonal movement remains a
two-cardinal-bridge query. Equal-elevation diagonal movement remains legal on a
raised flat plateau when at least one complete two-cardinal bridge route is
legal under the same objective boundary and destination predicates.

Walk, Swim, burrow, and walking-like forced movement reject a diagonal whose
endpoint elevations differ. Fly may change elevation diagonally only when one
of its two cardinal bridge routes has both objective boundaries open and the
destination is otherwise legal; it pays the one support-distance leg cost, not
two position commits. Progressive stairs and ramps are traversed through their
authored cardinal runs.

This rule avoids diagonal cliff/stair corner shortcuts and keeps the plan
bounded.

## 7. Tile authoring contract

Extend `Tile` without introducing a second terrain object:

```python
height: StrictInt = 0
elevation_surface_kind: ElevationSurfaceKind = ORDINARY
slope_axis: SlopeAxis | None = None
```

Validation:

- ordinary tiles require `slope_axis is None`;
- stairs/ramp require a slope axis;
- the authoritative progressive-edge predicate is evaluated from both
  endpoints, never from one display tag;
- equal-height transitions remain legal regardless of slope tag, subject to
  all existing blockers/costs;
- contradictory slope facts do not broaden traversal.

For a nonzero walking transition, all of these are required:

1. the cells are cardinally adjacent;
2. `abs(height_delta) == 1`;
3. both endpoint tiles have the same progressive kind (`STAIRS` or `RAMP`);
4. both endpoint tiles have the same slope axis;
5. that axis is aligned with the transition direction;
6. every existing structural/collision/destination rule also accepts.

An ordinary landing joins a stair/ramp run through an equal-height edge. It
does not authorize the next elevation change by itself. One-sided tags,
STAIRS-to-RAMP pairs, mismatched axes, sideways transitions, and multi-step
changes fail closed.

Tuple-local validation accepts each internally coherent tile update so a map
can be authored incrementally. Whole-map battlefield/save preflight rejects a
finished progressive run containing a contradictory elevated edge; the
runtime transition predicate remains authoritative even for an incomplete
draft map.

Display `name` and `sprite_name` do not authorize movement. A tile may be
called “Grand Stair” while mechanics depend only on the enum/axis.

### 7.1 Authoritative mutation

Add one GridMap-owned mutation:

```python
GridMap.set_tile_elevation(
    position,
    *,
    height,
    surface_kind,
    slope_axis,
    parent_event=None,
) -> bool
```

It validates the complete tuple through a precommit
DECLARATION→EXECUTION→EFFECT event. A canceled/forged proposal mutates nothing.
After accepted EFFECT it commits the tuple, returns `False` for an exact no-op,
bumps the movement/spatial revision once, invalidates path/action caches, and
publishes one non-vetoable COMPLETION fact. Production/editor/battlefield code
does not assign `tile.height` directly.

The lean compound-mutation rule is stricter: changing `height` is rejected while
any connector is anchored to that support tile. The author must remove or
replace the connector first. A surface-kind/axis-only mutation that leaves
height unchanged does not rewrite connector truth. Therefore one elevation
event never silently mutates connector endpoint elevation, revision, digest,
index, or history.

Tile replacement/removal is rejected by the same dependency check while a
connector is anchored; the author removes/replaces connectors first through
their existing lifecycle. Edge caches follow existing revisions. No compound
tile-plus-connector event or rollback framework is introduced.

## 8. Height-aware ordinary movement

### 8.1 Walking edge authorization

After existing adjacency, tile, occupancy, border, and collision checks:

```text
delta == 0
    -> ordinary walking rule

delta != 0 and the exact six-part progressive-edge predicate in §7 accepts
    -> authorized progressive walking rule

otherwise
    -> blocked cliff edge
```

The same rule is used by discovery and objective execution. Subjective path
discovery may omit unknown blockers according to existing privacy policy, but
objective execution revalidates the exact current edge before debit.

### 8.2 Cost

Authorized stairs/ramp edges use the current destination tile cost:

```text
ordinary stair tile      5 ft
difficult stair tile    10 ft
```

There is no extra five-foot vertical charge. This is the intended gameplay
model for progressive terrain.

### 8.3 Flying

Flying ignores the cliff authorization, but not structural walls, occupancy,
destination legality, or movement affordability. One adjacent flying leg
costs support distance between its endpoint tiles, then applies existing
flying destination terrain policy exactly once.

The implementation must define one cost owner; it may not add support distance
and destination cost if both represent the same base five feet. A suitable
formula is:

```python
base_leg_feet = support_distance_feet(from_tile, to_tile)
terrain_multiplier = destination_flying_cost
leg_cost_feet = base_leg_feet * terrain_multiplier
```

### 8.4 Swim and burrow

Swim and burrow retain existing cost rules on equal-height paths. They do not
receive implicit waterfall, vertical tunnel, stairs, or connector behavior.
Explicit future content may add those rules later.

### 8.5 Forced movement

Forced movement continues to own no voluntary movement debit or OA. Its
existing per-step structural validation becomes height-aware for walking-like
displacement. A shove against an unmarked cliff edge stops at that edge; this
unit does not add falling.

## 9. Entity range, reach, and threat migration

### 9.1 Owner surfaces

Add high-level Entity methods because they require both entities and must not
make Senses import upward:

```python
Entity.distance_to_entity(target: Entity) -> int
Entity.distance_to_position(position: tuple[int, int]) -> int
Entity.distance_to_object(obj: BaseBlock) -> int | None
Entity.threatens_entity_at(
    target: Entity,
    target_position: tuple[int, int] | None = None,
) -> bool
```

`Senses.get_feet_distance(position)` becomes support-elevation-aware for its
low-level position contract. It does not learn creature size or import Entity.

### 9.2 Required migration inventory

Classify every production `get_feet_distance` call:

- entity target: migrate to `Entity.distance_to_entity`;
- position/object target: use the height-aware position/object owner;
- explicitly planar geometry algorithm: retain a clearly named planar helper;
- preview/log-only display: consume the same authoritative selected-target
  distance rather than recomputing when available.

At minimum migrate:

- weapon Attack validation and discovery;
- ranged-spell attack and single-target spell validation;
- Shove and other five-foot entity interactions;
- item pickup/drop/use and environment-object discovery;
- chaining/entity-selection spell checks;
- Jump selection and cost;
- ranged-disadvantage threat checks;
- opportunity-attack exposure and execution.

Do not mechanically replace all calls with one signature. AoE shape generation
and planar rendering geometry remain intentionally planar.

### 9.3 Threat truth

The current Senses-owned adjacent-cell threat list cannot answer a size-aware
vertical entity question. Core combat migrates to Entity-owned actual-target
checks:

- reactor and mover must be mutually objective entities;
- current melee reach remains weapon-authored;
- the full existing propagation/raycast route from reactor to the candidate
  target position must be open, including every crossed canonical boundary;
- creature-volume distance must be within reach;
- visibility/privacy rules for preview remain unchanged;
- objective execution never trusts the preview.

Move PATH exposure compares the mover at each accepted from/to position using
that same owner. This supports adjacent and extended weapon reach without
pretending that one edge proves a ten-foot route. Preview may ask about a
prospective mover position, but accepted execution re-evaluates the objective
position and route.

Jump is narrower: candidate reactors are those that objectively threaten the
jumper at takeoff and would no longer threaten it at the accepted landing. The
OA resolves at takeoff before any position mutation. No intermediate arc cell
is used as a virtual target position.

### 9.4 Narrow debit-and-position commit seam

Jump and connector traversal expose an existing engine weakness: accepted
cost modifiers are not reversible, while `Entity.update_entity_position()`
currently mutates several indexes before spatial publication. Unit 4 fixes
that owner boundary directly; it does not add a generic transaction manager.

Add two small engine receipts:

1. ActionEconomy exposes two deliberately separate aggregate operations:

   - `install_prevalidated_aggregate_with_receipt(costs)` validates cost shapes
     and combines repeated channels but **does not recheck current
     affordability**. It installs already-admitted debits without event
     dispatch. Existing singular `consume_prevalidated()` delegates only to
     this install path and discards its receipt, preserving the rule that a
     causal effect may constrain the economy after admission without erasing
     the accepted action's terminal cost.
   - `consume_aggregate_with_receipt(costs)` first proves current aggregate
     affordability for every channel, then calls the same install path. Only
     Jump/connector use this wrapper after their explicit current-state
     revalidation.

   If any internal aggregate installation fails, the install path removes the
   exact handles already installed before re-raising. Success returns one
   one-use aggregate receipt containing every exact value-channel/modifier
   handle. `undo_prevalidated_debit(receipt)` removes only those still-exact
   handles. Receipt owner and one-use state are validated. It does not snapshot
   the whole ActionEconomy or rewind unrelated resource mutations.

   Both operations accept only typed ActionEconomy value-channel costs
   (`actions`, `bonus_actions`, `reactions`, `movement`, or spell-slot
   channels). A named `Resource` cost is not a value-channel cost and cannot
   enter either wrapper or its modifier-handle receipt.
2. Refactor the existing `Entity.update_entity_position()` implementation to
   stage the GridMap occupancy index, Entity position index, `entity.position`,
   and `entity.senses.position` before any spatial event. GridMap owns its index
   write/undo receipt; Entity composes it with its own old/new index and both
   position-field facts. Any exception before the commit marker restores all
   four owners exactly and publishes no SPATIAL_ENTITY_LEFT/ENTERED fact. After
   the commit marker, the normal spatial events publish and the position is
   authoritative.

Failure signaling is closed and local:

- `PositionCommitError(position_committed=False, cause=...)` means staging was
  fully restored before spatial publication; callers undo only their new debit
  receipt and re-raise it;
- `PositionPublicationError(position_committed=True, cause=...)` means indexes
  and both position fields committed but a spatial callback failed; callers
  preserve cost/position and re-raise it;
- neither exception manufactures an action CANCEL, COMPLETION, or persistent
  fault artifact. The ordinary Encounter/action call fails visibly with the
  typed engine exception. This is not Runtime fault coordination.

After its OA boundary, Jump creates a receipt for the movement debit only; its
earlier accepted fixed attempt costs remain final. After its OA boundary, a
connector creates one receipt for its action plus movement debit. In both
flows there is no handler/event dispatch between receipt creation and the
staged position commit. Debit undo runs only when position staging fails before
the commit marker. Once spatial publication begins, neither flow rolls back
position or cost; a callback exception is a typed publication failure with
committed position truth, not a fabricated cancellation. No receipt crosses an event
turn, is serialized, or is exposed to server/frontend code.

## 10. Jump transaction

### 10.1 Event facts and immutable cost admission

Extend `JumpEvent` with immutable/terminal truth equivalent to the useful
Move-family facts:

- `requested_end_position`;
- `objective_end_position`;
- `start_elevation_feet`;
- `requested_end_elevation_feet`;
- terminal `end_elevation_feet`;
- immutable disclosed direct-arc planar path;
- accepted support-distance movement cost;
- typed termination reason using the existing dependency-neutral movement
  vocabulary where possible.

Extend `StepMovementEvent` minimally:

- `disclosed_path`, equal to `(from_position, to_position)` for PATH and the
  full authorized planar line for the one Jump DIRECT_ARC leg;
- exact from/to support elevations;
- immutable `provocation_policy` with only `ORDINARY_EXIT` and
  `DOES_NOT_PROVOKE`; PATH and Jump DIRECT_ARC use `ORDINARY_EXIT`, while a
  connector maps its authored policy into this Step fact;
- PATH remains cardinal/diagonal adjacent according to existing rules;
- DIRECT_ARC may be non-adjacent and represents one committed landing leg.

Handler-family validation freezes these mechanics. A handler cannot rewrite
arc, elevations, cost, landing, identity, lineage, phase, or observer grants.

Jump admission also freezes and aggregate-revalidates every authored cost:

- fixed typed channel costs and named-resource costs as two disjoint tuples;
- the movement cost derived from accepted support distance;
- coherent resource names and positive amounts.

ActionEconomy owns one Jump-specific synchronous helper,
`commit_fixed_costs_without_dispatch(channel_costs, resource_costs)`:

1. combine duplicate channels and duplicate resource names;
2. prove all current channel and named-resource totals affordable before any
   mutation;
3. install the already-proved channel tuple through
   `install_prevalidated_aggregate_with_receipt()`;
4. consume named resources in deterministic resource-name order, with no event
   or handler dispatch between channel installation and the last resource;
5. on an unexpected resource failure/exception, restore only the resource
   values changed by this helper, undo the channel receipt, and raise typed
   `FixedCostCommitError`; on success, discard the channel receipt because the
   fixed attempt cost is final.

The restoration records are method-local and cannot cross an event turn. This
is not a reusable resource transaction/journal. A typed channel-install failure
occurs before any named resource is spent because resource consumption is last.

Fixed costs are consumed exactly once before the Step reaction boundary and
are not consumed again by `BaseAction` after completion. Movement is consumed
only after reactions and landing revalidation. A failure before fixed-cost
consumption spends nothing; a reaction after fixed-cost consumption may stop
the landing but does not refund the accepted fixed attempt cost.

### 10.2 Execution order

```text
accepted Jump EXECUTION
    -> publish root EFFECT
    -> commit accepted fixed channel + named-resource costs once through the
       no-dispatch fixed-cost helper
    -> create one DIRECT_ARC Step at DECLARATION with disclosed path
    -> advance Step through accepted EXECUTION and EFFECT
    -> existing EventQueue handler-order takeoff-exit OA resolves at Step EFFECT
    -> verify actor still alive/action-capable and still at takeoff
    -> revalidate destination tile, occupancy, elevation, propagation, and cost
    -> verify exact movement affordability
    -> debit exact movement cost through the affordability-checking aggregate
       wrapper and retain its receipt until position commit
    -> Entity.update_entity_position(actor, landing)
    -> synchronous landing/arrival children
    -> complete Step committed=True
    -> complete Jump with exact landing/objective truth
```

The root COMPLETION is always last. Exact terminal branches are:

- root DECLARATION/EXECUTION canceled: exact root CANCEL, no cost, Step, debit,
  movement, or root COMPLETION;
- root EFFECT is stored, then a handler may return a guarded exact root CANCEL
  with `canceled_from_phase=EFFECT`; the CANCEL is stored and no fixed cost,
  Step, debit, movement, or root COMPLETION follows;
- accepted root EFFECT followed by fixed-cost validation/affordability failure:
  same-EFFECT noncommitted stop then root COMPLETION; no cost, Step, debit, or
  movement;
- unexpected fixed-cost installation failure: the helper restores its own
  partial channel/resource state, raises `FixedCostCommitError`, and publishes
  no Step or successful root COMPLETION;
- fixed costs commit, then Step DECLARATION/EXECUTION cancels: fixed costs
  remain spent; no movement debit or landing;
- Step EFFECT is accepted, then OA kills/displaces the actor or landing
  revalidation fails: fixed costs remain spent; no movement debit or landing;
- movement debit succeeds but position staging fails before its commit marker:
  undo the exact new debit receipt after the owner restores all indexes and
  both position fields, then re-raise `PositionCommitError`; publish no spatial
  arrival or successful completion;
- spatial publication raises after the position commit marker: preserve the
  committed position and cost, re-raise `PositionPublicationError`, and do not
  publish a successful Jump completion;
- landing commits: movement debit remains spent, arrival children run once,
  Step completes, then Jump completes.

For every uncommitted leg:

- no landing position mutation;
- no landing entry/hazard event;
- no movement debit;
- Step cancels only before accepted EFFECT; an accepted EFFECT that cannot
  commit settles with the same-EFFECT noncommitted stop fact before its
  non-vetoable COMPLETION, following the Unit 3 movement boundary;
- root settles the exact reason and actual objective position;
- no requested landing is reported as actual.

Handler proposals for Jump root/Step identity, path, endpoints, elevations,
costs, lifecycle, observer grants, or lineage are checked before EventQueue
storage and callbacks. Forged proposals become exact family cancellation/stop
facts and cannot enter history.

### 10.3 Direct-arc gameplay and opportunity-attack rule

The planar line is disclosed presentation/observation geometry, not ground
occupancy or reaction authority. Ground
hazards under the arc do not trigger. The destination's hazards do. This unit
does not model an airborne effect intersecting the arc.

OA does **not** evaluate successive disclosed cells. It uses ordinary exit
timing at takeoff:

1. the Step carries `ORDINARY_EXIT`; each existing OA handler tests whether its
   reactor objectively threatens the jumper at the real takeoff position and
   would not threaten it at the accepted landing;
2. handlers run in EventQueue's existing registration order—Jump adds no
   second reactor enumeration or sorting authority;
3. each eligible Attack targets the jumper at its still-current takeoff
   position, so
   ordinary range, visibility, wall propagation, capability, and reaction cost
   validation apply unchanged;
4. after each reaction, subsequent handlers observe current truth and skip on
   death, displacement from takeoff,
   or loss of action permission; merely spending another reactor's reaction
   does not stop later reactors;
5. Disengage suppresses all such OA.

Intermediate cells are disclosed animation/observation geometry only. They do
not recruit reactors, lend visibility, or grant attacks. Observer grants for
the stored Step arc are the per-cell intersection already authorized to that
recipient; hidden cells and their elevations are removed together.

## 11. Traversal connector contract

Add two dependency-neutral frozen facts, tentatively in
`dnd/core/traversal_connectors.py`. Cold authored identity and live encounter
identity are deliberately distinct:

```python
class TraversalConnectorKind(str, Enum):
    LADDER = "ladder"
    ROPE = "rope"
    LIFT = "lift"
    VERTICAL_STAIRS = "vertical_stairs"
    PASSAGE = "passage"


class ConnectorProvocationPolicy(str, Enum):
    PROVOKES_SOURCE_EXIT = "provokes_source_exit"
    DOES_NOT_PROVOKE = "does_not_provoke"


class ConnectorActionCostType(str, Enum):
    ACTIONS = "actions"
    BONUS_ACTIONS = "bonus_actions"


class TraversalConnectorDefinition(BaseModel):
    authored_id: str
    kind: TraversalConnectorKind
    presentation_key: str
    endpoint_positions: tuple[tuple[int, int], tuple[int, int]]
    movement_cost_feet: int
    action_cost_type: ConnectorActionCostType | None
    action_cost_amount: int
    bidirectional: bool
    enabled: bool
    provocation_policy: ConnectorProvocationPolicy


class TraversalConnectorEndpoint(BaseModel):
    position: tuple[int, int]
    support_tile_uuid: UUID
    elevation_feet: int


class TraversalConnector(BaseModel):
    uuid: UUID
    authored_id: str
    kind: TraversalConnectorKind
    presentation_key: str
    endpoints: tuple[TraversalConnectorEndpoint, TraversalConnectorEndpoint]
    movement_cost_feet: int
    action_cost_type: ConnectorActionCostType | None
    action_cost_amount: int
    bidirectional: bool
    enabled: bool
    provocation_policy: ConnectorProvocationPolicy
    revision: int
    objective_digest: str
```

Exact naming may change during implementation, but the facts must remain
frozen, dependency-neutral, and free of callbacks/classes/import paths.
`authored_id` is map-local and stable across save/load and cold rebuild;
runtime UUID is encounter-local. Both appear in runtime event/projection truth,
while commands use runtime UUID plus revision/digest.

### 11.1 Validation

- endpoints occupy distinct `(x, y)` cells;
- both support tile UUIDs are distinct and currently resolve to those cells;
- endpoint elevations exactly equal the supporting tile elevations;
- costs are exact non-boolean nonnegative integers;
- `movement_cost_feet` is the sole movement debit owner;
- connector action cost is limited to ACTIONS or BONUS_ACTIONS; movement,
  reactions, spell slots, and arbitrary named resources are not accepted;
- `action_cost_type is None` iff amount is zero; a non-None type requires a
  strictly positive amount;
- presentation key is a validated authored semantic key, never a Python path;
- PASSAGE may join nonadjacent cells;
- LADDER, ROPE, LIFT, and VERTICAL_STAIRS require cardinal-adjacent endpoint
  cells and a nonzero elevation delta; the adjacent offset is the single lean
  substitute for stacked `(x, y)` surfaces;
- only PASSAGE may join arbitrary distinct support cells;
- directionality is explicit;
- provocation policy is explicit and independent of kind; mechanics never
  infer it from LADDER/LIFT/PASSAGE names;
- authored IDs are nonempty and unique within a map;
- digest covers authored ID and every objective traversal fact except the
  digest itself.

### 11.2 GridMap ownership

GridMap owns:

- `connector_uuid -> connector`;
- `authored_id -> connector_uuid`;
- endpoint position -> ordered connector UUIDs;
- connector revision included only in connector/action-discovery cache keys,
  never ordinary path-cache keys;
- register, replace, enable/disable, remove, and query APIs;
- support-tile dependency validation;
- rejection of support-height change, replacement, or removal while anchored;
- complete connector clearing in `GridMap.clear()` and `GridMap.reset()`.

Connector register/replace/enable/disable/remove uses one
`TraversalConnectorChangeEvent` with precommit
DECLARATION→EXECUTION→EFFECT acceptance, then atomic map/index mutation, then
non-vetoable COMPLETION. Immutable authored/runtime identity, endpoints,
costs, direction, policy, revision, and digest are guarded before queue
storage/callbacks. A canceled or forged change mutates no registry or index.

Registration and replacement are O(1) across UUID/authored-ID maps plus two
endpoint index updates. Endpoint lists use deterministic `(authored_id, uuid)`
ordering. Replace/remove/clear update all three indexes together. No
pathfinder scan, global entity update, thread, or subscriber loop is allowed.

### 11.3 Discovery

An actor standing at an authorized endpoint receives one action variant per
enabled connector/direction. Discovery returns:

- connector UUID and digest/revision;
- destination position and elevation;
- presentation kind/key;
- exact movement/action costs;
- current actor affordability and requester-subjective destination status
  (`KNOWN_CLEAR`, `KNOWN_BLOCKED`, or `UNKNOWN`);
- no undiscovered unrelated endpoint/object facts.

Register exactly one standard `TraverseConnector` action template through the
existing standard-action setup. It is a SELF-target template: selection is the
actor's current endpoint connector variant, never a TARGET entity. Its
`get_discovery_variants()` performs the endpoint-indexed lookup and emits one
oriented variant per enabled/authored direction while the actor is at that
endpoint. Objective hidden occupancy/blockers never suppress the variant or
change its metadata. Destination status derives only from facts the actor is
already permitted to know; empty and secretly occupied destinations are both
`UNKNOWN` and produce the same serialized variant for the same connector/
actor state. Each variant has a collision-free engine
command token containing runtime connector UUID, revision, digest, and oriented
source/destination; label/presentation text is not parsed for execution.
`Entity` stays subclass-agnostic. The variant carries a typed content
declaration and stable action/command identity; AI sees the same destination,
cost, subjective status, and presentation semantics as Human/Codex controllers.
Objective execution revalidates hidden occupancy/blockers and returns the
existing privacy-safe collision/blocked result without naming the hidden cause.
It is not manufactured by server/frontend code and is not disguised as an
inventory item.

### 11.4 Execution

Add `TraverseConnectorEvent` and `TraverseConnector` in the existing action
layer. The root event freezes authored ID, runtime UUID, digest/revision,
oriented endpoints, kind, elevations, direction, provocation policy, and
costs. It follows normal DECLARATION→EXECUTION→EFFECT acceptance.

Execution reads the accepted event plus current GridMap connector. It rejects:

- missing/replaced/disabled connector;
- stale digest or revision;
- wrong direction;
- actor not at the accepted source endpoint;
- removed/replaced destination support tile;
- occupied/blocked destination;
- dead/action-denied actor;
- unaffordable accepted cost.

After accepted root EFFECT:

```text
revalidate connector, actor at source, destination, and aggregate costs
    -> create one CONNECTOR_TRANSFER Step through DECLARATION/EXECUTION/EFFECT
    -> map PROVOKES_SOURCE_EXIT to Step ORDINARY_EXIT and
       DOES_NOT_PROVOKE to Step DOES_NOT_PROVOKE
    -> existing EventQueue OA handlers resolve eligible source-exit reactions
       against the actor's real source position
    -> stop with no cost/arrival on death, displacement, cancellation, or
       destination/cost revalidation failure
    -> consume accepted action and movement costs exactly once through the
       affordability-checking aggregate wrapper and retain its receipt until
       position commit
       through ActionEconomy, bypassing BaseAction post-completion consumption
    -> Entity.update_entity_position(destination)
    -> publish destination entry/arrival children once
    -> complete Step committed=True
    -> complete TraverseConnectorEvent last
```

`CONNECTOR_TRANSFER` is one nonadjacent `StepMovementEvent` trajectory with no
intermediate cells. For `DOES_NOT_PROVOKE`, the same Step lifecycle runs but
each OA handler is ineligible from the immutable Step policy. For
`PROVOKES_SOURCE_EXIT`, each existing handler tests its reactor against the real
source and accepted destination; ordinary Attack validates at the
still-current source. EventQueue registration order remains the sole dispatch
order. No connector kind-name switch or parent-event lookup participates.

Before accepted Step EFFECT, cancellation spends nothing. After accepted Step
EFFECT, lethal/displacing reaction or revalidation spends nothing and commits
nothing. Once costs are consumed and destination commits, arrival effects run
once; synchronous forced displacement may change objective final position but
cannot rewrite the committed connector destination. The root reports requested
destination, committed connector destination or `None`, objective final
position, and exact terminal reason. Handler-forged endpoint/cost/policy/
identity/lifecycle facts never reach storage or callbacks.

The closed lifecycle table is:

- root DECLARATION/EXECUTION cancellation: exact root CANCEL, no Step/cost/
  movement;
- root EFFECT is stored, then a handler may return a guarded exact root CANCEL
  with `canceled_from_phase=EFFECT`; the CANCEL is stored and no Step, cost,
  movement, or root COMPLETION follows;
- accepted root EFFECT followed by Step DECLARATION/EXECUTION cancellation:
  exact Step CANCEL plus same-EFFECT noncommitted root stop, then root
  COMPLETION; no cost/movement;
- accepted Step EFFECT followed by OA/revalidation stop: same-EFFECT
  noncommitted Step stop, then Step/root COMPLETION with no cost/movement;
- accepted Step EFFECT followed by cost/position commit: cost once, position
  once, arrival once, then Step COMPLETION and root COMPLETION last.

If the staged position commit fails before its commit marker, the exact
connector debit receipt is undone under §9.4, every index is restored, and no
arrival/completion is published; `PositionCommitError` is re-raised. If spatial
publication raises after the commit marker, position and cost remain
authoritative and `PositionPublicationError` is re-raised without successful
root completion.

No normal COMPLETION follows the canceled Step lineage; the already accepted
root EFFECT still receives its truthful noncommitted COMPLETION. No handler
sees or vetoes COMPLETION.

## 12. Boundary, terrain, and connector authoring

### 12.1 Battlefield contracts

Extend cold battlefield definitions with dependency-neutral facts for:

- tile elevation overrides;
- stairs/ramp surface kind and axis;
- `TraversalConnectorDefinition` records with stable authored IDs, endpoint
  positions, costs, directionality, provocation policy, kind, enabled state,
  and presentation keys;
- typed two-endpoint connector preview rows; connectors are not forced into a
  single-position object DTO.

The battlefield builder resolves support tile UUIDs only after building the
tiles and registers connectors through GridMap. Preview digest covers the same
authored facts. Runtime-only connector UUIDs are not cold content identities.

### 12.2 Map editor and snapshots

This unit must carry elevation/slope and connector facts through the existing
editor because otherwise the product cannot author or round-trip the proving
terrain:

- `APITile` serializes authoritative `elevation_steps`, surface kind, and slope
  axis; optional `elevation_feet` is computed/read-only and is always exactly
  `elevation_steps * 5`, never stored or accepted as an independent input;
- tile patch accepts only elevation steps plus surface kind/axis;
- save/load round-trip preserves it exactly;
- saved-map schema version increments;
- old supported schema is either migrated explicitly or rejected explicitly;
- saved maps gain a closed typed connector record matching
  `TraversalConnectorDefinition`; arbitrary connector JSON is rejected;
- load preflight validates unique authored IDs, endpoint cells, vertical-kind
  adjacency/elevation rules, costs, direction/policy, presentation key, and
  complete-map progressive runs before mutating GridMap;
- metadata/digest covers connector records in deterministic authored-ID order;
- editor CRUD uses the GridMap connector change lifecycle and returns the
  authoritative new revision/digest;
- structural edge projection continues privacy-safe side appearance while
  reciprocal engine identity comes from cell pair;
- objective preview carries both endpoints; subjective projection follows §13
  and never reuses the objective preview directly.

Connector editor/save/load/projection is mandatory, not conditional on which
route authored the proving battlefield. Do not add a generic arbitrary JSON
“connector config.” Use typed fields.

### 12.3 Content identities

Ladder, rope, lift, vertical-stair, and passage presentation recipes use
authored content/presentation keys. Mechanics do not branch on those names.
Ordinary stairs/ramp remain tile surface facts, not connector objects.

## 13. Projection and privacy

### 13.1 Objective truth

Objective/admin projection may carry exact:

- tile elevation;
- terrain surface kind/axis;
- reciprocal edge endpoints and effective channels;
- connector authored ID/runtime UUID, endpoints, kind, enabled/direction/
  provocation state, revision/digest, and costs;
- movement/jump/connector event elevations and settlement.

### 13.2 Subjective truth

Subjective projection must not reveal:

- an unseen upper/lower endpoint merely because the other endpoint is visible;
- hidden wall/door provider identity;
- an unauthorized destination through action availability;
- requested Jump/connector destination after observation lost contact;
- hidden intermediate arc cells;
- objective elevation of a cell whose location is not authorized.

When an actor is standing at and permitted to use a connector, the action offer
may reveal the exact destination because that is the rule-granted interaction
choice. That grant is actor-specific action truth, not a globally public map
fact.

Combat-log privacy continues to derive noncontrolled movement geometry from
authorized Step/transfer evidence. New elevation values are coordinate facts
and follow the same authorization as their associated positions.

The following fail-closed rules are binding:

- when a noncontrolled PATH Step position is removed, its associated support
  elevation is removed from structured data and text in the same operation;
- a connector root never authorizes either endpoint by itself; only an exact
  surviving same-source `CONNECTOR_TRANSFER` Step or an actor-specific current
  action offer authorizes that oriented endpoint pair;
- partial/hidden connector transfer evidence removes destination position,
  destination elevation, authored/runtime IDs, and endpoint-bearing text;
- ambiguous legacy movement roots with no exact authorized Step evidence may
  keep only the established generic safe summary, never root geometry or
  elevation;
- a subjective edge projection contains only recipient-authorized appearance
  and channel facts; objective wall/door provider UUIDs and hidden reciprocal
  sides are absent rather than pseudonymized or inferred;
- Jump arc positions and their elevations are filtered together, and a root
  cannot lend authority to hidden arc/landing coordinates.

### 13.3 Generated contracts

Event, world, and TypeScript contracts are regenerated only through the
checked-in generators. No handwritten SDK, frontend reducer, runtime journal,
or compatibility mirror is introduced.

The generated Step contract gains closed `CONNECTOR_TRANSFER` trajectory and
the immutable two-value provocation policy. Generated action contracts carry
the connector command token and typed semantics; consumers do not infer them
from labels, connector kind, or parent events.

## 14. Cache and performance rules

This feature must make game creation and action discovery predictably cheap:

- no all-pairs distance/elevation precomputation;
- no topology rebuild per query;
- no per-entity connector copies;
- no connector scan across the map during action discovery;
- endpoint lookup is indexed O(1);
- world-edge derivation is O(1) coordinate/index lookup plus O(local endpoint
  contributors) and may cache only objective revision-scoped views;
- elevation changes invalidate only affected spatial/action revisions;
- connector enable/disable/replace invalidates connector/action-discovery
  state only, never the ordinary path cache;
- flat maps retain the existing unit-cost pathfinder fast path when all other
  fast-path predicates hold;
- the fast path additionally proves all traversed tiles are equal elevation or
  uses the same edge predicate; it may not bypass elevation legality;
- battlefield composition adds work linear in authored elevation cells and
  connectors, not entities × tiles;
- no async task, thread, worker, polling loop, retry loop, journal, or durable
  artifact is added.

Add focused timing evidence for:

- flat-map composition before/after;
- elevated proving-map composition;
- one cold and one warm available-actions query;
- flat and elevated path computation;
- connector discovery at an endpoint and away from endpoints.

The gate is absence of an algorithmic regression, not a fragile wall-clock
number on one machine. Record call counts and asymptotic owner evidence beside
sample timings.

## 15. Dependency direction

Expected dependency flow:

```text
dnd/core/creature_types.py
           |
           v
dnd/core/spatial_distance.py      dnd/core/world_edges.py
           |                                |
           +---------------+----------------+
                           v
                  dnd/core/gridmap.py
                           |
                           v
                 Entity / actions / items
                           |
                           v
             scenario builders and projectors
```

Connector DTOs may depend on dependency-neutral action/cost enums but never on
Entity, GridMap, concrete actions, server models, or content loaders.

Forbidden:

- function-local imports;
- `TYPE_CHECKING` to hide a cycle;
- Senses importing Entity;
- GridMap importing concrete connector action classes;
- core contracts importing server/runtime/frontend modules;
- server/frontend recomputing range, edge legality, or connector destination;
- content-name switches in mechanics.

## 16. Files expected in scope

Exact file placement may be refined before implementation, but scope is
bounded to these owners.

### New production leaves

- `dnd/core/spatial_distance.py`;
- `dnd/core/world_edges.py`;
- `dnd/core/traversal_connectors.py`;
- optionally one high-level connector content/action module if it avoids a
  dependency cycle.

### Existing engine owners

- `dnd/core/base_tiles.py`;
- `dnd/core/gridmap.py`;
- `dnd/core/events.py`;
- `dnd/core/action_execution.py` only if the existing termination vocabulary
  needs one connector-specific value;
- `dnd/blocks/sensory.py`;
- `dnd/entity.py`;
- `dnd/actions.py`;
- `dnd/actions_functional.py` for the standard SELF-target template;
- `dnd/action_dispatch.py` for existing Human command execution;
- `dnd/reactions.py`;
- `dnd/content_system/action_definitions.py` for authenticated action identity;
- `dnd/ai/contracts/semantics.py` and `dnd/ai/runtime/action_semantics.py` for
  the same connector semantics consumed by AI;
- current forced-movement implementations when height revalidation is shared;
- battlefield definition/catalog/builder modules;
- the existing scenario/encounter composition owner for the proving
  battlefield's actor deployment.

### Projection/authoring/contracts

- `server/world_contracts.py`;
- `server/world_projection.py`;
- `server/api_models.py`;
- `server/mapeditor_support.py`;
- `server/event_server.py` for typed map-editor connector CRUD routes only;
- existing subjective movement combat-log projector;
- checked-in generated event/TypeScript contracts and their generators.

### Tests

Add focused owner files rather than expanding archived batches:

- `tests/engine/test_elevation_distance_and_threat.py`;
- `tests/engine/test_action_cost_and_position_commit.py`;
- `tests/engine/test_world_edge_identity_and_elevation.py`;
- `tests/engine/test_progressive_elevation_movement.py`;
- `tests/engine/test_jump_elevation_settlement.py`;
- `tests/engine/test_traversal_connectors.py`;
- `tests/engine/test_elevation_proving_battlefield.py`;
- focused map-editor/world-projection contract tests;
- targeted additions to current movement, combat, Jump, privacy, and generator
  owners.

No archived server suite is run in batch.

## 17. Red-first regression matrix

### 17.1 Pure distance

- equal-height point distance matches every current representative flat result;
- positive and negative elevation differences are symmetric;
- missing tile has no zero-elevation fallback;
- overlapping creature vertical intervals have zero vertical clearance;
- Medium-to-Medium, Tiny-to-Large, Large-to-Huge elevated cases match the
  exact size table;
- adjacent planar plus five-foot clearance remains five feet;
- twenty-foot vertical clearance cannot pass five-foot reach;
- four planar cells plus three elevation steps returns the authored 20-foot
  hybrid result rather than the 25-foot true-3-D result;
- creature size never authorizes walking across an unmarked cliff;
- bool/invalid elevation is rejected.

### 17.2 Canonical edges

- A-east and B-west return equal `AdjacentEdgeKey`;
- invalid diagonal/nonadjacent/same-cell key construction rejects;
- intrinsic wall sides collapse into one effective edge view;
- directional door open/close preserves key/provider UUID while channels
  change;
- no-op door/elevation mutation does not bump revision;
- object removal removes provider without stale cache;
- tile replacement/removal updates/rejects the view;
- objective edge caching never accepts requester/mode/occupancy inputs;
- local contributor lookup scales with those endpoints, not map size;
- canceled/forged elevation mutation stores no forged fact and mutates no tile;
- any anchored support-height mutation/replacement/removal rejects without
  changing tile, connector, digest, revision, or indexes;
- surface-only mutation at an anchored tile leaves connector truth unchanged;
- `clear()` leaves no edge cache or connector fact;
- snapshot round-trip derives the same edge key.

### 17.3 Progressive terrain and cliffs

- flat-to-flat remains walkable;
- equal-elevation diagonal movement works on a raised plateau;
- mixed-height diagonal bridge fails for walking;
- Fly's height-changing diagonal requires one legal two-cardinal bridge and
  pays one support-distance leg;
- unmarked height delta blocks Walk/Swim;
- both-endpoint same-kind/same-axis stairs and ramp permit exactly one step;
- one-sided, mixed-kind, and mixed-axis progressive pairs reject;
- equal-height ordinary landing joins a progressive run but cannot authorize
  the next rise alone;
- sideways stair/ramp crossing does not authorize elevation change;
- two-step cliff is blocked despite stair tag;
- diagonal ascent/descent is blocked;
- multi-cell progressive run paths and spends exact ordinary costs;
- difficult stairs cost exactly difficult terrain once;
- Fly crosses a cliff and pays support-distance × terrain multiplier;
- path discovery and objective execution agree;
- stale discovered slope is revalidated before debit;
- forced movement stops before cliff without falling or voluntary debit.

### 17.4 Range/reach/threat

- melee can reach an adjacent target whose occupied intervals are within five
  feet;
- melee cannot reach an adjacent planar target far below/above;
- ranged normal/long/out-of-range boundaries include vertical clearance;
- single-target spell and object interaction use the correct owner;
- flat-map action discovery remains identical;
- ranged disadvantage ignores a vertically out-of-reach hostile;
- OA preview/execution agree on height-aware threat;
- hidden reactor remains absent from preview;
- accepted current objective threat, not stale preview, controls execution;
- elevated ten-foot reach checks the exact prospective target position;
- an intervening wall or diagonal barrier blocks extended reach;
- flat-map extended-reach behavior remains unchanged.

### 17.5 Jump

- elevated landing discovery uses support distance;
- cliff gap may be jumped when landing is visible, valid, and affordable;
- direct arc does not enter or trigger ground hazards beneath it;
- landing hazard triggers once after debit and arrival;
- Jump publishes one DIRECT_ARC Step with full disclosed path/elevations;
- multiple takeoff-threatening reactors resolve in existing EventQueue handler
  registration order;
- an intermediate-only reactor gets no OA and no virtual target position;
- each OA Attack validates range/visibility/propagation at the actor's real
  takeoff position;
- Disengage prevents OA;
- lethal/displacing reaction prevents landing and movement debit;
- fixed action/resource cost is consumed once before OA and is not refunded by
  a later stopped landing;
- mixed typed-channel plus named-resource fixed costs commit exactly once;
- aggregate fixed-cost unaffordability mutates neither channels nor resources;
- injected typed-channel install failure spends no named resource;
- injected later named-resource failure restores earlier resources and the
  typed channel receipt before raising `FixedCostCommitError`;
- every pre-fixed-cost failure consumes nothing, every post-EFFECT stop emits
  exact noncommitted truth, and Jump COMPLETION is last;
- stored root EFFECT followed by a guarded handler CANCEL produces no cost,
  Step, movement, or root COMPLETION;
- injected position-index failures undo only the new movement debit, restore
  every index, and publish no arrival/success;
- injected spatial-callback failure after commit preserves position/cost and
  raises typed publication failure rather than false cancellation/success;
- stale landing elevation/occupancy blocks before debit;
- successful landing debits exact movement before spatial arrival;
- requested/actual/objective landing and elevation remain truthful;
- handler rewrites of arc/elevation/cost cannot reach storage/callbacks;
- noncontrolled projection hides unauthorized arc/landing elevations.

### 17.6 Connectors

- every kind uses the same executor with no kind-name mechanics branch;
- vertical kinds require cardinal-adjacent distinct cells with nonzero
  elevation delta; only PASSAGE may be nonadjacent;
- cold authored ID survives save/load/rebuild while runtime UUID remains
  encounter-local, and both appear in objective events/projection;
- each endpoint discovers exactly the allowed direction;
- one-way reverse traversal is absent/rejected;
- disabled connector is absent/rejected;
- stale digest/revision is rejected;
- wrong source endpoint is rejected;
- anchored support-height change/replacement/removal rejects until connector
  removal/replacement;
- occupied/blocked destination rejects before cost;
- exact movement/action cost is consumed once before arrival;
- connector action cost rejects movement/reaction/spell-slot channels,
  incoherent None/amount pairs, booleans, and negative amounts;
- unaffordable transfer mutates nothing;
- reaction death/displacement stops transfer truthfully;
- provoking policy resolves OA at real source position; non-provoking policy
  emits no OA without branching on connector kind;
- destination hazard/arrival fires once;
- no intermediate cell entry/OA/hazard is invented;
- synchronous forced displacement after arrival preserves committed connector
  destination separately from objective final position;
- endpoint index removes cleanly;
- connector register/replace/enable/disable/remove cancellation and forged
  proposals never mutate indexes or enter callbacks;
- stored root EFFECT followed by guarded CANCEL produces no Step, cost,
  movement, or root COMPLETION;
- injected precommit position-index failure undoes the exact connector debit
  and restores every index without arrival/success;
- `clear()` and reset erase all connector state;
- typed map/battlefield snapshot and cold two-endpoint preview round-trip the
  authored connector definition and include it in metadata/digest;
- old schema migration/rejection and malformed-load preflight are deterministic;
- subjective discovery does not reveal an unauthorized opposite endpoint;
- empty and secretly occupied hidden destinations produce the same UNKNOWN
  connector variant; execution returns the same privacy-safe blocked result;
- partial connector logs cannot lend endpoint/elevation authority, and hidden
  authored/runtime IDs do not survive.

### 17.7 Product proving battlefield

Run at least one real scripted Human-vs-AI-compatible encounter flow that:

1. moves across level terrain;
2. opens the door and crosses its reciprocal edge;
3. climbs progressive stairs;
4. descends a ramp;
5. fails ordinary movement at a cliff;
6. attacks across a legal and illegal elevation separation;
7. jumps the gap and resolves OA/landing hazard;
8. traverses each connector kind;
9. reconnects/reprojects current board truth through existing product APIs;
10. reaches an ordinary encounter terminal state.

The geometry comes from the maintained battlefield definition; the hostile
deployments come from the maintained scenario/encounter composition. This is
not permission to rebuild Runtime V2. Use the current Encounter, action,
scenario, and projection owners.

### 17.8 Subjective privacy boundary

- unauthorized noncontrolled PATH position and its elevation disappear
  together from structured data and rendered text;
- a partially authorized Jump arc cannot retain hidden arc/landing elevation;
- an ambiguous legacy movement root with no authorized Step reduces to the
  established generic safe summary;
- connector root-only evidence cannot authorize the opposite endpoint;
- an exact same-source surviving CONNECTOR_TRANSFER Step authorizes only its
  oriented endpoint pair;
- partial connector evidence removes destination/elevation/identity-bearing
  text and data;
- subjective structural edge projection never contains hidden wall/door
  provider UUIDs or an unauthorized reciprocal side;
- objective/admin projection retains complete evidence separately.

### 17.9 Debit and position commit seam

- the affordability-checking aggregate wrapper validates every channel before
  mutation, while the admitted install-only primitive deliberately does not;
- both successful aggregate paths return every exact modifier handle in one
  receipt that cannot be applied twice or to another ActionEconomy;
- an accepted ordinary action whose causal effect later constrains its economy
  still installs its admitted terminal cost exactly once through existing
  `consume_prevalidated()` semantics;
- injected failure after each partial aggregate-debit installation unwinds
  every newly installed handle before returning no receipt;
- unrelated action/resource mutations survive receipt undo;
- injected failure at each precommit Entity/GridMap index write restores old
  `entity.position`, `entity.senses.position`, Entity position index, GridMap
  position index, both occupancy buckets, and publishes no left/entered event;
- successful position commit publishes left then entered exactly once after
  all indexes agree;
- a spatial callback exception after the commit marker never rewinds position
  or cost, raises `PositionPublicationError(position_committed=True)`, and
  cannot produce a successful action completion;
- a precommit staging exception raises
  `PositionCommitError(position_committed=False)` only after exact restoration;
- existing Move/Swim/Fly callers retain the same public
  `Entity.update_entity_position()` API while receiving the exception-safe
  implementation.

## 18. Implementation checkpoints

### Checkpoint 0 — freeze baseline and plan acceptance

- record `git status --short` and preserve current line endings;
- record exact plan SHA-256;
- receive explicit internal and external plan ACCEPT for that same hash;
- no production implementation begins before both accept.

### Checkpoint A — pure rules, edge view, and authoring

- add red pure distance/edge/elevation authoring tests;
- add dependency-neutral distance and edge contracts;
- extend Tile and GridMap mutation/view owners;
- carry tile elevation/slope through world projection and map-editor save/load;
- prove clear/remove/replace/no-op behavior;
- run focused tests and scoped Pyright.

Checkpoint A alone is not declared product-complete.

### Checkpoint B — ordinary combat movement and Jump

- add the narrow typed-cost receipt and exception-safe existing position-commit
  implementation with focused injected-failure tests;
- integrate height-aware path legality/cost by movement mode;
- migrate range/reach/object/threat/OA call sites;
- implement progressive stairs/ramp and cliff rules;
- correct Jump to one direct-arc landing leg and truthful settlement;
- refresh event/world/generated contracts;
- build the non-connector portion of the proving battlefield;
- run the first external implementation review over A+B.

The tree must remain playable on flat and elevated maps at this checkpoint.

### Checkpoint C — connector vertical and product battlefield

- add connector fact, GridMap registry/index/lifecycle, action/event, discovery,
  authoring, projection, and privacy;
- add every required connector kind to the proving battlefield;
- run the full focused matrix and real encounter flow;
- run final internal and external implementation reviews;
- do not claim completion until both accept the same final tree cutoff.

## 19. Focused verification commands

Use bounded files only. Expected commands include:

```bash
uv run pytest tests/engine/test_elevation_distance_and_threat.py -q
uv run pytest tests/engine/test_action_cost_and_position_commit.py -q
uv run pytest tests/engine/test_world_edge_identity_and_elevation.py -q
uv run pytest tests/engine/test_progressive_elevation_movement.py -q
uv run pytest tests/engine/test_jump_elevation_settlement.py -q
uv run pytest tests/engine/test_traversal_connectors.py -q
uv run pytest tests/engine/test_elevation_proving_battlefield.py -q
uv run pytest tests/engine/test_move_settlement.py -q
uv run pytest tests/engine/test_grid_pathfinding.py -q
uv run pytest tests/engine/test_combat_actions.py -q
uv run pytest tests/manual/test_126_jump_legacy_contract.py -q
uv run pytest tests/manual/test_113_subjective_combat_log_projection.py -q
uv run pytest tests/engine/test_action_discovery.py -q
uv run pytest tests/engine/test_senses_light_stealth.py -q
uv run pytest tests/engine/test_encounter_apis.py -q
uv run pytest tests/manual/test_147_mapeditor_legacy_contract.py -q
uv run pyright <explicit changed production/test files>
uv run python devtools/generate_event_contract.py --check
uv run python devtools/generate_typescript_sdk.py --check
npm --prefix sdk/typescript run check
```

Do not run the whole pytest suite. Do not batch archived server tests. If a
focused unrelated failure appears, follow `KNOWN_ISSUES.md` policy rather than
silently repairing or weakening it.

## 20. Acceptance gates

### Architecture

- [ ] `(x, y)` remains the only entity/support position.
- [ ] There is exactly one Tile elevation value.
- [ ] Canonical edge identity is reciprocal and derived without a drifting
      mutable topology duplicate.
- [ ] WorldEdgeView is objective boundary truth only; contextual movement and
      subjective decisions remain outside it.
- [ ] GridMap remains the structural/path/connector index owner.
- [ ] Entity remains the position mutation and cross-entity distance owner.
- [ ] ActionEconomy remains the cost owner.
- [ ] Cost rollback is one-use receipt removal of exact new handles, not a
      snapshot/journal/transaction service.
- [ ] EventQueue remains the reaction/history owner.
- [ ] No circular/late/`TYPE_CHECKING` import was added.
- [ ] No runtime/server/frontend game authority was added.

### Mechanics

- [ ] Equal-height existing gameplay remains unchanged.
- [ ] Ordinary walking cannot cross an unmarked cliff.
- [ ] Progressive stairs/ramp work across several tiles and cost correctly.
- [ ] Fly, Swim, burrow, forced movement, and Jump have explicit elevation
      rules with no accidental fallback.
- [ ] Entity range/reach/threat uses occupied vertical extent exactly once.
- [ ] Creature size never authorizes walking across an unmarked cliff.
- [ ] Jump direct arc has no intermediate ground occupancy.
- [ ] Jump OA uses real takeoff position only; no virtual movement authority.
- [ ] Jump and connector debit accepted costs before arrival.
- [ ] Precommit position-index failure restores position/indexes and only the
      exact reversible debit; postcommit callback failure never fabricates
      rollback.
- [ ] Uncommitted movement never fabricates debit or arrival.
- [ ] Vertical connector kinds share one executor.
- [ ] Connector OA behavior comes only from authored provocation policy.
- [ ] Connector replacement/removal/clear cannot leave stale executable facts.

### Product and privacy

- [ ] The proving battlefield and its actor-deploying scenario are maintained
      product content.
- [ ] It can be composed, projected, played, and terminated through current
      owners.
- [ ] APITile/editor/save/load preserve elevation/slope and typed connectors
      exactly.
- [ ] Generated contracts are fresh.
- [ ] Hidden endpoints/elevations/arc geometry do not leak.
- [ ] No frontend content-name switch or handwritten compatibility SDK is
      required.

### Performance and scope

- [ ] Flat-map creation/path/action-discovery call counts do not regress
      algorithmically.
- [ ] Connector discovery is endpoint-indexed.
- [ ] No background task/thread/queue/retry system exists.
- [ ] No stacked-surface, roof, falling, FOV-height, or vertical-AoE work
      entered the diff.
- [ ] Semantic diff has no unrelated formatting or CRLF churn.

## 21. Independent reviewer rejection checklist

Reject the plan or implementation for any of these:

1. a second coordinate/elevation authority;
2. stacked-surface preparation disguised as required connector work;
3. wall/door identity requiring a mutable topology registry that can drift;
4. mechanics branching on tile/object display names;
5. missing or zero-elevation fallback used for mechanics;
6. flat-map distance changes not explicitly proved and accepted;
7. size-aware distance copied into actions/spells/server/frontend;
8. stairs/ramp permitting sideways, diagonal, or multi-step cliff shortcuts;
9. Fly or Jump receiving a flat five-foot cost across a large elevation delta;
10. Jump direct arc entering ground cells beneath it;
11. OA recomputed by a client/server instead of engine event facts;
12. debit after arrival or debit for an uncommitted landing/transfer;
13. requested endpoint reported as actual after reaction/interruption;
14. connector executor switching on `kind` when authored cost/direction facts
    already decide mechanics;
15. connector endpoint scan over all world objects/actions;
16. stale connector surviving tile removal/replacement/clear;
17. hidden opposite endpoint/elevation leaked through map or action discovery;
18. map editor/save/load dropping elevation/slope/connector truth;
19. a test-only arena substituted for authored battlefield content;
20. runtime/transport coordination work added to solve an engine feature;
21. asynchronous/background processing added;
22. tests asserting only model construction rather than real movement,
    reaction, cost, range, privacy, and encounter behavior;
23. compile-green result with stairs, Jump, or connectors missing from the
    playable proving battlefield;
24. unrelated cleanup or line-ending normalization mixed into the patch.
25. Jump inventing virtual intermediate target positions merely to deliver OA;
26. requester/mode/occupancy truth cached or projected as WorldEdgeView;
27. one tagged slope endpoint authorizing a nonzero elevation transition;
28. connector kind implicitly deciding OA instead of its authored policy;
29. a connector elevation mutation partially changing tile/index/digest truth;
30. connector root evidence lending subjective endpoint/elevation authority.
31. connector revision invalidating ordinary path caches;
32. connector action cost duplicating movement or admitting spell/reaction cost;
33. anchored tile mutation silently rewriting connector facts;
34. debit undo restoring unrelated ActionEconomy/resource state;
35. position rollback attempted after spatial publication has begun.
36. named Resource costs passed through a modifier-handle receipt or partially
    spent after fixed-cost commit failure.

## 22. Reviewer questions requiring explicit answer

Before ACCEPT, both reviewers must answer:

1. Does the distance metric preserve current flat behavior while producing
   correct vertical reach boundaries?
2. Is tactical creature size used by one owner without pretending to model
   full horizontal/3-D creature volumes?
3. Can canonical edge identity remain derived and still give walls/doors the
   required stable reciprocal identity?
4. Are slope kind/axis sufficient to prevent unauthorized cliff shortcuts?
5. Is one atomic DIRECT_ARC Jump leg compatible with OA and Unit 3 movement
   settlement using real takeoff position and without a second movement
   authority?
6. Is the connector fact/action the smallest correct way to expose both
   endpoints without duplicating shared state in two items?
7. Does connector discovery remain O(1) and privacy-safe?
8. Are typed authoring/save/load/projection changes and the product scenario
   sufficient for a real playable battlefield?
9. Is any deferred visibility/AoE behavior falsely implied by the plan?
10. Can implementation remain in three checkpoints without speculative middle
    abstractions?

## 23. Handoff format

The implementer's final report must include:

1. exact plan hash implemented;
2. exact files changed;
3. final spatial-distance and edge formulas;
4. final ordinary-step, Jump, and connector transaction order;
5. proving battlefield content identity and playable flow;
6. focused red probes that became green;
7. exact commands and results;
8. scoped Pyright and generator results;
9. performance/call-count evidence;
10. privacy and save/load evidence;
11. semantic diff/CRLF audit;
12. internal and external reviewer verdicts against the same cutoff.

This unit is complete only when an elevated battlefield plays correctly. It is
not complete because a topology model serializes or a connector DTO validates.
