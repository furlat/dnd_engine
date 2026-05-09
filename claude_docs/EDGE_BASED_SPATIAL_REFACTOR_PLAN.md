# Edge-Based Spatial Refactor Plan

> **OBSOLETE / DO NOT IMPLEMENT.**
>
> This plan has been superseded by
> [TILE_DIRECTIONAL_BLOCKING_REFACTOR_PLAN.md](TILE_DIRECTIONAL_BLOCKING_REFACTOR_PLAN.md).
>
> The architectural direction in this document is rejected: do not introduce an
> edge object layer, `EdgeWall`, `EdgeDoor`, `spatial_layer="edge"`,
> `APIEdgeObject`, normalized edge object placement, or event payloads centered
> on `edge_key`. The current direction is minimal and tile-owned: ordinary
> placed blocks/items/entities remain on tiles, may contribute directional
> blocking data, and GridMap derives transitions by checking the directional
> state of both endpoint tiles.

Status: obsolete / superseded

This document proposes a refactor for representing walls, doors, height changes,
windows, portcullises, and similar map features as blockers between cells rather
than as blockers that consume a whole grid cell.

The current code already has two important ingredients:

- Cell-level derived walkability via tiles, entities, objects, hazards, subjective
  perception, and remembered collisions.
- Directional tile borders via `Tile.border_north`, `border_south`,
  `border_east`, `border_west`, consumed by Dijkstra pathfinding.

The missing piece is a first-class edge layer that can derive movement and vision
blocking from edge-local objects and effects without asking those objects to
mutate tile state directly.

## Problem Statement

Current walls and doors in examples are modeled at full-cell granularity.

- Walls are full tiles: `walkable=False`, `visible=False`, `name="Wall"`.
- Doors are full-cell objects: `blocks_movement=True`,
  `blocks_vision_field=True` when closed.
- The renderer and map editor inherit this model, so a one-cell wall or door
  occupies the same canonical grid space that a creature would otherwise use.

That is not ideal for D&D-style maps. Many walls and doors should exist on the
edge between two cells. A door between `(4, 2)` and `(5, 2)` should block passage
between those cells, but it should not make either cell intrinsically unwalkable.

There is a tempting implementation shortcut:

```text
Door object closes -> mutates tile.border_east / tile.border_west
Door object opens  -> restores those tile fields
```

That is not the desired architecture. It makes the object imperatively rewrite
tile state instead of participating in the same derived-query process used for
full-cell blockers.

The target design is:

```text
Cell walkability = derived from tile + cell objects + entities + hazards
Edge walkability = derived from intrinsic edge data + edge objects + edge effects
Cell visibility  = derived from tile + cell objects + light/perception
Edge visibility  = derived from intrinsic edge data + edge objects + edge effects
```

## Current Behavior Summary

### Cell Walkability

`GridMap.is_walkable(x, y, mode)` checks only whether a tile exists and whether
that tile blocks movement for the given movement mode.

`GridMap.is_walkable_for(...)` layers in the full cell-level logic:

- Tile must be walkable for the movement mode.
- Blocking entities prevent movement unless the requester is itself or the
  entity is non-blocking.
- Blocking objects prevent movement.
- Subjective pathing can ignore imperceivable blockers so hidden or invisible
  entities do not leak through path availability.
- Hazard avoidance can treat hazardous tiles and objects as unwalkable.
- Previously bumped imperceivable blockers can be remembered in
  `senses.collision_blocked`.

### Directional Tile Borders

`Tile.can_enter_from(from_position)` uses the destination tile's borders.

For orthogonal movement:

- Entering from west checks destination `border_west`.
- Entering from east checks destination `border_east`.
- Entering from south checks destination `border_south`.
- Entering from north checks destination `border_north`.

For diagonal movement, the current rule is permissive: at least one of the two
touching destination borders must be open.

`GridMap.compute_paths()` passes a `can_enter` callback to Dijkstra, so normal
path generation respects tile borders.

### Senses

`Entity.compute_senses_from_position()` computes:

- Geometric FOV via `GridMap.compute_fov()`.
- Effective visibility by filtering FOV through light and observer senses.
- Paths via `GridMap.compute_paths(... subjective=True, ...)`.
- Safe paths via a second pathing pass with `walk_in_danger=False` when needed.
- Visible entities and objects through perceivability checks.
- `senses.walkable` from tile-only `GridMap.is_walkable()`.

Important distinction:

- `senses.paths` is the movement legality surface.
- `senses.walkable` is a lightweight tile-only snapshot used by rendering and
  threat logic. It does not include occupancy, objects, hazards, or edge borders.

### Vision And Propagation

FOV currently asks `GridMap.is_blocking(x, y, observer_uuid)`, which checks
tile/object vision blocking for a full cell.

AoE propagation has a related but distinct physical-barrier query:
`GridMap.is_blocking_propagation(x, y)`, which intentionally ignores magical
darkness and checks physical barriers such as walls and closed doors.

Neither FOV nor AoE propagation currently understands edge blockers.

### Movement Execution

Normal `Move` uses a precomputed `senses.paths` path, so its initial route is
border-aware. During execution it rechecks `GridMap.is_walkable_for()` before
and after step handlers, but it does not recheck directional border entry. This
matters if an edge blocker changes after path computation.

Forced movement and shove-like movement currently walk cell-by-cell using
`is_walkable_for()` and appear to ignore tile border rules.

Jump validates landing with `is_walkable_for()` but intentionally bypasses
intermediate terrain. Whether it should respect edge blockers for landing is a
rules decision.

## Design Goals

1. Make tile edges first-class spatial participants inside the existing tile
   spatial model.

   Walls and doors can live between cells without consuming a canonical grid
   space, but this should extend the current tile/border/event machinery rather
   than create a second spatial system.

2. Preserve derived-state architecture.

   Dynamic objects should not directly rewrite unrelated tile fields as a
   side-effect. `GridMap` should derive transition legality from the tile,
   tile-border fields, edge-attached objects, conditions, entities, and
   objective/subjective context.

3. Support objective and subjective evaluations.

   Movement, pathfinding, FOV, object discovery, and rendering already need
   different answers depending on what the observer knows or can perceive.
   Edge blockers need the same split.

4. Apply to both movement and vision.

   A closed door may block both. A window may block movement but not vision. A
   curtain may block vision but not movement. A low wall may block walking but
   not flying, and may provide cover without fully blocking vision.

5. Keep cell and edge semantics explicit.

   A cell object blocks or modifies a cell. An edge object blocks or modifies a
   transition. Both should remain part of the same spatial/tile pipeline, with
   one derived transition query deciding how they combine.

6. Keep object spam manageable.

   Structural edge objects should not flood normal item/object action discovery
   unless they are interactable and relevant.

7. Keep migration incremental.

   Full-cell walls and doors should continue to work while edge-aware walls and
   doors are introduced.

8. Keep movement, senses, light, and propagation in parity.

   Do not ship a state where pathing understands an edge wall but FOV, light,
   targeting, and AoE still see through it. That is worse than the current
   full-cell model because it creates contradictory authoritative answers.

## Full-Parity Architecture

The refactor should be built around one spatial transition kernel, not around
separate movement and vision patches.

Current derived products:

```text
senses.paths      -> GridMap.compute_paths(...)
senses.visible    -> GridMap.compute_fov(...)
light             -> GridMap.compute_fov(...) from light source
AoE propagation   -> GridMap.compute_propagation_fov(...)
targeting/LOS     -> senses.visible / senses.entities
rendering/fog     -> senses.visible, senses.seen, senses.walkable, senses.objects
```

Today these products do not all ask the same spatial question:

- Pathing asks cell walkability and destination tile border movement.
- FOV asks only whether the target cell blocks vision.
- Light asks FOV.
- AoE propagation asks cell physical blocking.
- Targeting usually trusts `senses.visible` or `senses.entities`.

That split is the root problem. The target architecture:

```text
Tile + cell objects + edge-attached objects + entities + conditions
    -> GridMap.transition_state(from_pos, to_pos, context)
        -> movement paths
        -> FOV / visible cells
        -> light propagation
        -> AoE propagation / line of effect
        -> sensory update deltas
        -> renderer edge state
```

The transition kernel must expose separate channels because D&D map geometry is
not one boolean:

```python
class TransitionContext:
    requester_uuid: Optional[UUID]
    observer_uuid: Optional[UUID]
    movement_mode: MovementMode
    subjective: bool
    collision_blocked_cells: set[Position]
    collision_blocked_edges: set[EdgeKey]

class TransitionState:
    from_pos: Position
    to_pos: Position
    edge_key: EdgeKey

    cell_enterable: bool
    movement_allowed: bool
    vision_allowed: bool
    light_allowed: bool
    propagation_allowed: bool

    movement_cost: float
    blocks: list[TransitionBlockReason]
```

Suggested public query surface:

```python
grid.transition_state(from_pos, to_pos, context) -> TransitionState
grid.can_transition(from_pos, to_pos, context) -> bool
grid.can_see_transition(from_pos, to_pos, context) -> bool
grid.can_light_transition(from_pos, to_pos, context) -> bool
grid.can_propagate_transition(from_pos, to_pos, context) -> bool
```

No consumer should independently combine tile walkability, tile visibility,
object blocking, borders, and subjective memory. Consumers choose the channel;
`GridMap` derives the answer.

### Non-Negotiable Parity Rule

Any feature that creates or changes a wall/door/boundary must update all
affected channels in the same vertical slice:

```text
movement pathing
actual movement validation
visible cells / senses.visible
visible entities / senses.entities
visible objects / senses.objects
light propagation
AoE propagation / line of effect
event hints and sensory updates
snapshot/rendering state
```

A movement-only edge door is not an acceptable final slice. It can exist only
behind tests that prove the old behavior is preserved and before the edge door
is exposed as a real gameplay/map object.

## Computational Geometry First

The first code layer to change is computational geometry. `GridMap` can only
derive good answers if the geometry helpers can express boundary crossings.

Current state:

- `dnd/core/geometry.py` has cell sets and Bresenham lines.
- `dnd/core/shadowcast.py` computes FOV by asking `is_blocking(x, y)`.
- `GridMap.compute_fov()` passes `GridMap.is_blocking(x, y)`.
- `GridMap.compute_propagation_fov()` passes
  `GridMap.is_blocking_propagation(x, y)`.

That means the algorithms are currently cell-aware. Shadowcast scans quadrants
and internally reasons about wall/floor transitions, but the engine callback it
receives is still cell-only. To reach the desired standard, the geometry layer
must expose transition-aware primitives.

### Geometry Primitives To Add

Keep these pure: no `GridMap`, no `Entity`, no objects.

```python
Position = tuple[int, int]
EdgeKey = tuple[Position, Position]

def normalize_edge(a: Position, b: Position) -> EdgeKey: ...

def adjacent_transitions(path: list[Position]) -> list[tuple[Position, Position]]:
    ...

def supercover_line(start: Position, end: Position) -> list[Position]:
    ...

def raycast_clear(
    start: Position,
    end: Position,
    can_cross: Callable[[Position, Position], bool],
    blocks_cell: Callable[[Position], bool],
) -> bool:
    ...
```

`bresenham_line()` can remain, but any LOS/vision correctness check should use a
line representation that does not skip boundary crossings. If normal Bresenham
misses a touched cell at a corner, add a supercover variant and use that for
LOS/FOV/propagation tests.

### Shadowcast API To Add

Do not leave recursive shadowcast as a cell-only primitive. Either adapt it or
wrap it behind an edge-aware FOV API in the same module:

```python
def compute_fov_edge_aware(
    origin: Position,
    blocks_cell: Callable[[Position], bool],
    can_cross: Callable[[Position, Position], bool],
    mark_visible: Callable[[Position], None],
    max_distance: Optional[float] = None,
) -> None:
    ...
```

The first correct implementation can be radius + supercover raycast:

```text
for candidate in circle_positions(origin, radius):
    if raycast_clear(origin, candidate, can_cross, blocks_cell):
        mark_visible(candidate)
```

That is acceptable as the correctness baseline. Once tests pin the behavior,
recursive shadowcast can be optimized to call `can_cross(...)` directly, but it
must not remain authoritative while ignoring edge blockers.

### Computational Geometry Consumers

Every geometry consumer should be audited:

- `GridMap.compute_fov()` uses `compute_fov_edge_aware(..., can_see_transition)`.
- `GridMap.compute_propagation_fov()` uses
  `compute_fov_edge_aware(..., can_propagate_transition)`.
- AoE shapes use transition-aware propagation FOV.
- Line spells and ray-like effects use transition-aware line/raycast helpers.
- `POSITION_LOS` targeting continues to use `senses.visible`, but
  `senses.visible` must come from transition-aware FOV.

This is not a feature layer. It is the ground floor.

## Dependency Direction / Import DAG

This refactor must preserve the existing strict dependency direction. The right
shape is not a new parallel "edge system"; it is the existing tile/spatial
system gaining complete boundary semantics.

Preferred module ownership:

```text
server/api + renderer adapters
    -> dnd/entity.py, dnd/actions.py, dnd/blocks/*
        -> dnd/core/gridmap.py
            -> dnd/core/events.py, dnd/core/base_block.py, tile/edge primitive types
```

Concrete placement rules:

- Edge key/value primitives can live beside `GridMap` or in a tiny low-level
  helper module if that reduces duplication. They should be simple aliases and
  helpers, not the root of a new subsystem.
- Event models belong in `dnd/core/events.py` and must remain pure data. They
  must not import `GridMap`, `Entity`, `Senses`, item classes, or action
  classes.
- `GridMap` owns transition aggregation. It already asks tiles whether entry is
  allowed through `Tile.can_enter_from()`. The refactor should centralize all
  movement, forced movement, FOV, light, and propagation checks around similar
  transition queries.
- `BaseBlock` may expose default edge-query hooks if needed, such as
  `blocks_edge_movement(...)`, because blocks are below entities/items in the
  dependency hierarchy. Those hooks should accept primitive context parameters
  and not import `GridMap` or `Entity`.
- Structural objects may live under `dnd/blocks/` as item-like objects with an
  edge attachment field. They should participate in the same object placement,
  object change, and senses invalidation flow used by current floor objects.
- `Senses` and `SpatialSensesCallback` can import `get_map()` and event data as
  they do today. They should keep using UUIDs and block APIs rather than
  importing `Entity`.
- `Entity` and movement/actions are higher-level consumers. They call
  `grid.can_transition(...)`; transition logic does not call back into
  `Entity`.
- Server/API/stream code imports event and snapshot models. Core spatial code
  must not import server modules.

The most important anti-pattern to avoid:

```python
# Wrong shape:
edge_object.open()
edge_object.tile.border_east = False
edge_object.owner.senses.update_senses(...)
```

That creates hidden coupling between object state, tile state, and observer
state. The correct shape is:

```python
# Correct shape:
edge_object.set_open(...)
grid.reindex_object(edge_object_uuid)
SpatialChangeEvent.object_changed(..., edge_key=..., senses_hint=...)
SpatialSensesCallback reacts through the normal event path
```

The edge object contributes facts. `GridMap` derives the transition result.
Senses update because spatial events flow through the normal pre-completion
callback path.

No late imports, `TYPE_CHECKING` imports, or inside-function imports should be
introduced for this refactor. If a new edge helper wants to import `Entity`, the
helper is in the wrong layer; move the caller upward or pass primitive context
instead.

## Proposed Spatial Model

### Cells

Cells remain keyed by `(x, y)`.

Cell residents:

- Tile.
- Entities.
- Cell objects.
- Tile and object conditions.
- Light and darkness state.

Cell-level queries:

```python
grid.is_cell_walkable(...)
grid.is_cell_walkable_for(...)
grid.is_cell_blocking_vision(...)
grid.is_cell_blocking_propagation(...)
grid.is_cell_hazardous_for(...)
```

The existing `is_walkable()` and `is_walkable_for()` can either keep their names
as compatibility wrappers or be renamed over time.

### Edges

An edge is the relationship between two adjacent cells.

Suggested canonical key:

```python
EdgeKey = tuple[Position, Position]  # normalized sorted pair
Position = tuple[int, int]
```

Rules:

- Only adjacent cells can form a normal movement edge.
- Orthogonal edges are the primary use case for walls and doors.
- Diagonal transitions can be represented either as a direct diagonal edge or
  derived from the two orthogonal edge barriers around the corner.

Edge contributors inside the existing tile/spatial model:

- Intrinsic tile border state: `Tile.border_north`, `border_south`,
  `border_east`, `border_west`.
- Edge objects: doors, wall segments, windows, gates, portcullises.
- Edge conditions/effects: magical wall, temporary barrier, force field,
  broken/locked/burning state.

Transition-level queries on `GridMap`:

```python
grid.can_cross_edge(from_pos, to_pos, requester_uuid=None, mode=MovementMode.WALKING, subjective=False)
grid.edge_blocks_movement(from_pos, to_pos, requester_uuid=None, mode=MovementMode.WALKING, subjective=False)
grid.edge_blocks_vision(from_pos, to_pos, observer_uuid=None, subjective=False)
grid.edge_blocks_propagation(from_pos, to_pos)
grid.can_see_transition(from_pos, to_pos, observer_uuid=None, subjective=False)
grid.can_propagate_transition(from_pos, to_pos)
```

Top-level transition query:

```python
grid.can_transition(
    from_pos,
    to_pos,
    requesting_entity_uuid=None,
    mode=MovementMode.WALKING,
    walk_in_danger=True,
    subjective=False,
    collision_blocked=None,
) -> bool
```

This should become the one predicate for movement from one cell to another.

It should check:

1. `to_pos` exists.
2. `to_pos` is cell-walkable for the requester and movement mode.
3. `from_pos -> to_pos` is edge-passable for the requester and movement mode.
4. Hazard avoidance if `walk_in_danger=False`.
5. Remembered collision blocking.

Dijkstra should call `can_transition()` rather than separately calling
`is_walkable_for()` and `Tile.can_enter_from()`.

Vision should get the same treatment, but through a separate query. Do not
reuse movement passability as vision passability. A cliff or low wall can block
walking but not sight; a curtain can block sight but not walking; a window can
block walking while allowing sight and light.

## Object Edge Attachment

Current full-cell objects use:

```python
blocks_walking(requesting_entity_uuid=None, mode=MovementMode.WALKING) -> bool
blocks_vision(requesting_entity_uuid=None) -> bool
```

Objects attached to an edge should have analogous methods:

```python
class EdgeBlockerMixin:
    edge_key: EdgeKey

    def blocks_edge_movement(
        self,
        from_pos: Position,
        to_pos: Position,
        requesting_entity_uuid: Optional[UUID] = None,
        mode: MovementMode = MovementMode.WALKING,
    ) -> bool:
        ...

    def blocks_edge_vision(
        self,
        from_pos: Position,
        to_pos: Position,
        observer_uuid: Optional[UUID] = None,
    ) -> bool:
        ...

    def blocks_edge_propagation(
        self,
        from_pos: Position,
        to_pos: Position,
    ) -> bool:
        ...
```

### Minimal Object-Level Change

This should mostly extend the existing object path, not replace it.

Current cell objects already have:

- `BaseItem.blocks_movement`
- `BaseItem.blocks_vision_field`
- `BaseItem.blocks_walking(...)`
- `BaseItem.blocks_vision(...)`
- `BaseItem._notify_blocking_changed(...)`
- `GridMap.place_object(...)`
- `GridMap.remove_object(...)`
- `SpatialChangeEvent.object_changed(...)`

Add edge attachment as optional metadata:

```python
spatial_layer: Literal["cell", "edge"] = "cell"
edge_key: Optional[EdgeKey] = None
edge_anchor_position: Optional[Position] = None
```

`position` can remain the interaction/render anchor, so object action discovery
does not need to be redesigned. For an edge door, the anchor can be one of the
two adjacent cells or a deterministic canonical cell. The edge key tells
movement/FOV/light/AoE which boundary the object modifies.

Default edge behavior can delegate to existing cell behavior:

```python
def blocks_edge_movement(...):
    return self.blocks_walking(...)

def blocks_edge_vision(...):
    return self.blocks_vision(...)

def blocks_edge_light(...):
    return self.blocks_edge_vision(...)

def blocks_edge_propagation(...):
    return self.blocks_edge_vision(...)
```

Then special objects override only where needed:

- Window: movement blocked, vision/light allowed, maybe propagation blocked.
- Curtain: movement allowed, vision/light blocked, propagation maybe allowed.
- Portcullis: movement blocked, vision/light allowed, projectile/cover special
  later.
- Closed door: movement blocked, vision/light/propagation blocked.
- Open door: all allowed.

`GridMap` should keep existing cell object indexes and add sparse edge indexes:

```python
_object_positions: dict[UUID, Position]          # existing anchor
_objects_by_position: dict[Position, set[UUID]]  # existing anchor lookup
_object_edges: dict[UUID, EdgeKey]               # new, optional
_objects_by_edge: dict[EdgeKey, set[UUID]]       # new, optional
```

This keeps edge walls/doors as objects without making walls appear as normal
loot/actions. Action discovery can filter by `spatial_layer`, `object_role`,
`is_interactable`, and perceivability.

### Object Change Flow

Opening a door should look like the current cell door flow, plus edge metadata:

```text
OpenDoorAction / CloseDoorAction
    -> mutate object state
    -> object._notify_blocking_changed(...)
        -> GridMap finds object position and optional edge_key
        -> SpatialChangeEvent.object_changed(..., edge_key=..., senses_hint=...)
        -> EventQueue callbacks
        -> light recomputation if vision/light geometry changed
        -> SpatialSensesCallback recomputes visibility or marks paths dirty
```

No tile border fields are mutated by the door. The door object contributes facts
to `GridMap.transition_state(...)`.

This keeps the same polymorphic direction as the existing cell object model:
`GridMap` asks the object whether it blocks the relevant operation. The object
does not rewrite the tile.

### Door Example

Closed door:

```text
cell blocking:
  blocks_movement = False
  blocks_vision_field = False

edge blocking:
  blocks_edge_movement = True
  blocks_edge_vision = True
  blocks_edge_propagation = True
```

Open door:

```text
edge blocking:
  blocks_edge_movement = False
  blocks_edge_vision = False
  blocks_edge_propagation = False
```

The door remains discoverable/interactable from nearby cells, but no longer
makes either adjacent cell unwalkable.

### Wall Segment Example

Thin wall:

```text
cell blocking:
  none

edge blocking:
  movement: blocked for walking, swimming, burrowing
  vision: blocked
  propagation: blocked
```

Flying is a design question. A floor-to-ceiling wall blocks flying. A low wall
may not.

### Window Example

Closed glass window:

```text
movement: blocked
vision: not blocked
propagation: depends on effect
cover: likely yes, but cover is a separate mechanic
```

### Curtain Example

```text
movement: not blocked
vision: blocked or obscured
propagation: usually not blocked
```

### Portcullis Example

```text
movement: blocked for normal movement
vision: not blocked
projectile line: partially blocked / cover
propagation: maybe not blocked for gas/light, blocked for creatures
```

This shows why movement and vision cannot be collapsed into one boolean.

## Intrinsic Edge State

Existing `Tile.border_*` fields are intrinsic movement-edge data, but they are
stored on a tile. That is not a problem to solve first; it is the existing
edge mechanism.

Important current limitation: these four directional fields are movement-only.
There is no parallel four-directional vision blocker today. Current vision is
cell-level:

- `Tile.visible` / `Tile.blocks_vision(...)`
- floor objects with `blocks_vision(...)`
- FOV calling `GridMap.is_blocking(x, y, observer_uuid)`

So a tile can currently block vision as a whole cell, and an object can block
vision as a whole cell, but neither can block only the transition between two
cells.

Keep `Tile.border_*` as intrinsic tile-edge contributors.

`GridMap.edge_blocks_movement()` checks:

1. Destination `Tile.can_enter_from(from_pos)`.
2. Edge-attached objects.
3. Edge-targeted conditions, if/when they exist.

This is the safest and smallest path because the code already has exactly one
canonical way to ask whether a destination tile can be entered from a neighbor.

### Recommendation

Treat tile borders as the existing intrinsic edge state. Do not move them out of
`Tile` during this refactor. The refactor is about making every consumer use the
same derived transition query, not about inventing a new storage model.

For intrinsic directional vision, prefer adding a separate tile-border concept
rather than reusing movement borders:

```python
vision_border_north: bool = True
vision_border_south: bool = True
vision_border_east: bool = True
vision_border_west: bool = True
```

Names can change, but the semantics should be separate. Movement borders answer
"can a creature cross this boundary?" Vision borders answer "can sight/light
cross this boundary?" Edge-attached objects then contribute through
`blocks_edge_movement(...)`, `blocks_edge_vision(...)`, and
`blocks_edge_propagation(...)` without mutating those tile fields.

## Objective Vs Subjective Semantics

The current pathing model has a critical privacy rule:

```text
Subjective pathfinding ignores imperceivable blocking entities/objects.
Actual movement uses objective blocking and may collide.
```

Edge blockers need the same split.

### Objective Edge Query

Objective query answers the true map state.

Use cases:

- Actual movement execution.
- Server-authoritative collision.
- Combat log facts after events resolve.
- DM/global map view.
- Save/load.
- Non-leaky simulation.

Objective edge blockers include:

- Known and hidden wall segments.
- Closed doors, even if not visible to the mover.
- Illusory walls if they physically block, or not if they only deceive.
- Invisible force walls.
- Magical barriers.

### Subjective Edge Query

Subjective query answers what a specific observer can infer.

Use cases:

- `senses.paths`.
- Player-visible move destinations.
- AI planning with limited information.
- Fog-of-war rendering.

Subjective edge blockers should be skipped if imperceivable, analogous to
imperceivable cell blockers.

If an entity tries to move through a subjectively open edge that is objectively
blocked, movement should stop and the engine should record that edge as
collision-blocked for future pathing.

### Collision Memory

Current `senses.collision_blocked` is a set of positions. For edge blockers,
that is not precise enough. We need edge collision memory:

```python
senses.collision_blocked_cells: set[Position]
senses.collision_blocked_edges: set[EdgeKey]
```

Backward-compatible approach:

- Keep `collision_blocked` for cells.
- Add `edge_collision_blocked`.
- `can_transition(... subjective=True)` checks both.

When a subjective path crosses a hidden closed door and actual movement bumps
it, add the edge key, not the destination cell. The destination cell may still
be reachable from another direction.

### Hidden Edge Objects

Examples:

- Secret door.
- Illusory wall.
- Hidden tripwire across an edge.
- Invisible wall of force.

Subjective treatment should be object-specific:

- A hidden secret door might look like a wall, so subjective movement should be
  blocked until found.
- An invisible wall might look open, so subjective movement should be allowed
  until collision.
- An illusory wall might look blocked, but objective movement is open.

This suggests edge objects may need both objective blocking and perceived
blocking:

```python
def blocks_edge_movement_objectively(...) -> bool
def blocks_edge_movement_subjectively(observer_uuid, ...) -> bool
```

Or a single method with `subjective` in the context:

```python
def blocks_edge_movement(..., subjective=False) -> bool
```

The single-method API is simpler but must be used carefully.

## Vision And Senses Propagation

Movement-only edge support is not enough. Walls and doors between cells must
also affect FOV, visible objects/entities, AoE propagation, light propagation,
and sensory updates.

### Edge-Aware FOV

Current FOV checks whether cells block vision. Specifically, shadowcasting calls
`GridMap.is_blocking(x, y, observer_uuid)`, which checks tile/object vision
blocking at that cell. It does not check `Tile.border_*`, and it has no
directional vision-border equivalent.

Edge-aware FOV therefore needs a transition barrier check.

Possible API:

```python
grid.compute_fov(
    origin,
    max_distance=None,
    observer_uuid=None,
    use_edge_blocking=True,
)
```

The FOV implementation should check whether light/sight can pass from one cell
to the next.

Important nuance: the current shadowcast algorithm already scans in quadrants
and tracks wall/floor transitions internally, but its public callback is still
cell-based:

```python
is_blocking(x, y) -> bool
```

It does not receive the previous cell, the transition edge, or the direction of
entry. So shadowcast is spatially structured, but the engine's use of it is not
yet edge-aware. It can probably be adapted, but not by only changing
`GridMap.is_blocking(...)`.

Event propagation alone is not enough here. `SPATIAL_TILE_CHANGED` or
`SPATIAL_OBJECT_CHANGED` with `requires_fov=True` can tell senses to recompute
FOV, but the recompute will still be wrong until FOV asks an edge-aware vision
query.

Implementation rule:

- The authoritative FOV helper must live in the computational geometry layer and
  must accept a transition callback.
- The first implementation can be raycast-per-candidate for correctness.
- The existing recursive shadowcast can stay only if it is adapted to ask
  `can_cross(prev, next)` or clearly wrapped as a compatibility optimization
  for maps with no edge vision blockers.

Do not leave FOV as "cell shadowcast plus edge cleanup" unless tests prove the
cleanup exactly matches transition-aware raycast. The authoritative answer must
be boundary-aware.

### Edge-Aware Light Propagation

Light currently uses FOV. If FOV becomes edge-aware, light follows naturally.

Important cases:

- Closed door blocks torchlight.
- Open door lets torchlight through.
- Window lets light through but blocks walking.
- Magical darkness can still be cell-based, but an edge barrier should determine
  which cells receive illumination.

### Edge-Aware AoE Propagation

AoE propagation currently has physical-barrier FOV that ignores magical
darkness. Edge-aware AoE should use:

```python
grid.edge_blocks_propagation(from_pos, to_pos)
```

This must remain distinct from normal vision:

- Darkness blocks sight but not fireball propagation.
- Glass may block a creature but not necessarily light.
- A wall blocks physical propagation.
- Some spell shapes, such as cylinders from above, intentionally ignore lateral
  barriers.

### Senses Update Hints

Current spatial hints include:

- `requires_fov`
- `requires_paths`
- entity/object/light changed positions

Edge changes need equivalent hints:

```python
edge_changed: Optional[EdgeKey]
edge_changed_positions: set[Position]  # both cells adjacent to the edge
requires_fov: bool
requires_paths: bool
requires_light_recompute: bool
requires_propagation_cache_clear: bool
```

Those flags must be set from the transition channels affected by the change:

```text
movement_allowed changed     -> requires_paths
vision_allowed changed       -> requires_fov
light_allowed changed        -> requires_light_recompute and usually requires_fov
propagation_allowed changed  -> requires_propagation_cache_clear
rendered edge state changed  -> sensory edge delta / snapshot delta
```

This is how the existing event model remains sufficient. The event does not need
to become edge-specific, but the hint must describe the full transition impact.
If a door opens and changes both movement and vision, the same
`SPATIAL_OBJECT_CHANGED` event carries both `requires_paths=True` and
`requires_fov=True`.

When an edge door opens/closes:

- Paths may change for observers whose known movement graph includes nearby
  cells.
- FOV may change if the door blocks vision.
- Light propagation may change if the door blocks light.
- Visible entities and objects may change behind the door.
- Object state itself may change for clients.

The current `SpatialSensesCallback` already handles `SpatialChangeEvent`. Edge
changes should use that same path. The event can keep its primary `position`
field as the canonical tile/cell anchor and add optional edge details when the
change affects a transition:

```python
class SpatialChangeEvent(Event):
    position: Position
    edge_key: Optional[EdgeKey] = None
    edge_from_position: Optional[Position] = None
    edge_to_position: Optional[Position] = None
    object_uuid: Optional[UUID] = None
    edge_blocks_movement: Optional[bool] = None
    edge_blocks_vision: Optional[bool] = None
    edge_blocks_propagation: Optional[bool] = None
    senses_hint: Optional[SensesUpdateHint] = None

    def get_affected_positions(self) -> set[Position]:
        positions = {self.position}
        if self.edge_from_position is not None:
            positions.add(self.edge_from_position)
        if self.edge_to_position is not None:
            positions.add(self.edge_to_position)
        return positions
```

The existing event types can carry the distinction:

- `SPATIAL_TILE_CHANGED` for tile property changes, including intrinsic border
  changes such as `border_north`.
- `SPATIAL_OBJECT_PLACED`, `SPATIAL_OBJECT_REMOVED`, and
  `SPATIAL_OBJECT_CHANGED` for object changes, with `edge_key` present when the
  object is attached to an edge rather than placed in a cell.
- Existing `MOVEMENT_COLLISION` for a failed movement attempt, with `edge_key`
  present if the collision was against an edge blocker rather than a cell
  blocker.

### Event Updates Required

No new `EventType` is required for the first implementation. Update the existing
event payloads and factories:

1. `SensesUpdateHint`

   Add:

   ```python
   edge_changed: Optional[EdgeKey] = None
   edge_changed_positions: Optional[set[Position]] = None
   requires_light_recompute: bool = False
   requires_propagation_cache_clear: bool = False
   ```

2. `SpatialChangeEvent`

   Add optional edge metadata:

   ```python
   edge_key: Optional[EdgeKey] = None
   edge_from_position: Optional[Position] = None
   edge_to_position: Optional[Position] = None
   edge_blocks_movement: Optional[bool] = None
   edge_blocks_vision: Optional[bool] = None
   edge_blocks_light: Optional[bool] = None
   edge_blocks_propagation: Optional[bool] = None
   ```

   Update `get_affected_positions()` to include both endpoints when edge fields
   are present.

3. `SpatialChangeEvent.tile_changed(...)`

   Add optional edge fields for intrinsic tile border changes. A tile border
   edit should produce `SPATIAL_TILE_CHANGED`, not a new edge event.

4. `SpatialChangeEvent.object_placed(...)`,
   `SpatialChangeEvent.object_removed(...)`, and
   `SpatialChangeEvent.object_changed(...)`

   Add optional edge fields. Edge-attached doors/walls still use object events.
   The edge metadata says the object modifies a boundary rather than only a
   floor cell.

5. `SpatialChangeEvent.movement_collision(...)`

   Add optional `edge_key`, `edge_from_position`, and `edge_to_position`. This
   preserves the existing movement collision event while making hidden edge
   collisions precise.

6. `GridMap._on_vision_blocking_changed(...)`

   Today it recomputes lights at `event.position` when `requires_fov=True`.
   For edge events, it must recompute around all affected positions:

   ```python
   for pos in event.get_affected_positions():
       grid.recompute_lights_at_position(pos, parent_event=event.uuid)
   ```

   Or use a batch helper if duplicate light recomputation becomes noisy.

7. `SpatialSensesCallback._apply_hint(...)`

   It already reacts to `requires_fov` and `requires_paths`. Extend it so
   `edge_changed_positions` are treated like subscription-relevant cells and so
   `MOVEMENT_COLLISION` with `edge_key` records edge collision memory.

8. SSE/event serialization

   No new stream event category. Ensure edge fields serialize as JSON-friendly
   arrays or typed objects. Do not use tuple keys in JSON maps.

`SensesUpdateHint` should gain only edge invalidation fields:

```python
edge_changed: Optional[EdgeKey] = None
edge_changed_positions: Optional[set[Position]] = None
requires_light_recompute: bool = False
requires_propagation_cache_clear: bool = False
```

The hint should stay about invalidation, not about taxonomy. It does not need
separate "edge object placed", "edge object removed", and "edge object changed"
fields unless the sensory callback truly needs different behavior for those
cases. For senses, the important question is usually: did this edge change path
topology, vision geometry, light, propagation, or known rendering state?

`SensoryUpdateEvent` should also gain edge deltas if clients render fogged or
remembered edge state incrementally:

```python
visible_edges_added: list[EdgeKey]
visible_edges_removed: list[EdgeKey]
visible_edges_changed: dict[EdgeKey, EdgePerceptionSnapshot]
seen_edges_added: list[EdgeKey]
known_edges_changed: dict[EdgeKey, EdgePerceptionSnapshot]
```

If clients do not need incremental edge rendering in the first slice, the event
can initially carry only `paths_dirty=True` and normal visible-cell/object
deltas. But the model should leave room for edge deltas immediately; otherwise
the stream will become cell-aware but edge-blind.

### Subscription Model

Current subscriptions are cell-based. An observer subscribes to geometric FOV
cells. Edge changes should notify relevant observers without requiring a full
global senses recompute.

Possible approaches:

1. Subscribe to edges explicitly.

   `GridMap` maintains:

   ```python
   _edge_subscribers: dict[EdgeKey, set[UUID]]
   _entity_edge_subscriptions: dict[UUID, set[EdgeKey]]
   ```

   Full senses update subscribes to edges bordering the observer's FOV and known
   path frontier.

2. Reuse cell subscriptions.

   Edge change at `(a, b)` notifies subscribers of cell `a` and cell `b`.

   This is simpler and likely enough for first implementation.

Recommendation: start with cell subscription fan-out. Add explicit edge
subscriptions only if performance or correctness requires it.

## Rendering And API Contract

The renderer needs to know structural edge data without treating every wall
segment as a normal floor object.

### Separate Structural Objects From Floor Objects

Add a classification field:

```python
spatial_layer: Literal["cell", "edge"]
object_role: Literal["loot", "environment", "structure", "device", "hazard"]
is_interactable: bool
show_in_object_actions: bool
show_in_object_list: bool
```

An edge wall should likely be:

```text
spatial_layer = "edge"
object_role = "structure"
is_interactable = False
show_in_object_actions = False
show_in_object_list = False
```

A door should be:

```text
spatial_layer = "edge"
object_role = "structure"
is_interactable = True
show_in_object_actions = True when adjacent/perceivable
```

This avoids flooding `senses.objects` and action discovery with hundreds of wall
segments.

### Snapshot Shape

Map/API snapshots should expose edge blockers separately from floor objects:

```json
{
  "edges": [
    {
      "edge_id": "4,2|5,2",
      "a": [4, 2],
      "b": [5, 2],
      "blocks_movement": true,
      "blocks_vision": true,
      "kind": "door",
      "state": {"is_open": false},
      "object_uuid": "..."
    }
  ]
}
```

For subjective client views, the payload may need:

```json
{
  "known_edges": [...],
  "visible_edges": [...],
  "remembered_edges": [...]
}
```

This matters for fog of war. A player may remember a closed door, see that it is
now open, or not know a secret door exists.

### Map Editor

The map editor should eventually support:

- Full-cell wall tile, legacy mode.
- Edge wall segment.
- Edge door segment.
- Edge window.
- Rotate/flip edge object orientation.
- Select edge object without selecting a cell occupant.

The catalog should not model edge walls as normal objects in the same list as
loot or chests unless the UI can filter them.

## Events

Do not add a family of edge-specific event types in the first design. Normal
tiles currently use one generic tile spatial change event:

```python
SPATIAL_TILE_CHANGED
```

Objects already have their own generic spatial events:

```python
SPATIAL_OBJECT_PLACED
SPATIAL_OBJECT_REMOVED
SPATIAL_OBJECT_CHANGED
MOVEMENT_COLLISION
```

Edges should follow the same pattern. Extend `SpatialChangeEvent` with optional
edge details rather than creating a second event class:

```python
edge_key: Optional[EdgeKey]
edge_from_position: Optional[Position]
edge_to_position: Optional[Position]
edge_blocks_movement: Optional[bool]
edge_blocks_vision: Optional[bool]
edge_blocks_propagation: Optional[bool]
```

Meaning by event type:

- `SPATIAL_TILE_CHANGED`: tile state changed. This includes `walkable`,
  `visible`, light-affecting tile state, and intrinsic border fields like
  `border_north`.
- `SPATIAL_OBJECT_PLACED`: object placed into the spatial model. If `edge_key`
  is present, the object is attached to the edge instead of occupying only a
  floor cell.
- `SPATIAL_OBJECT_REMOVED`: object removed from the spatial model. If
  `edge_key` is present, remove it from the edge attachment.
- `SPATIAL_OBJECT_CHANGED`: object state changed. A door opening or closing can
  use this event with `edge_key` and the same `senses_hint` mechanism used by
  cell doors today.
- `MOVEMENT_COLLISION`: movement failed against an imperceivable blocker. If
  `edge_key` is present, the blocker was on the transition rather than in the
  destination cell.

This keeps the event stream aligned with the existing tile/object distinction:
what changed is still tile or object state; `edge_key` just says which part of
the tile spatial shape was affected.

### EventQueue Impact

The current spatial handler fast path is position-indexed and only special-cases
`SPATIAL_ENTITY_ENTERED`, `SPATIAL_ENTITY_LEFT`, and `SPATIAL_TILE_CHANGED`.
That can stay true. `SPATIAL_TILE_CHANGED` remains the tile/topology event for
spatial handlers. Edge-attached object changes can continue to be normal
spatial object events observed by callbacks and the stream, just like current
door state changes.

For subscription fan-out, `SpatialChangeEvent.get_affected_positions()` should
return both cells adjacent to the edge when `edge_key` is present. That lets
existing cell subscription logic see the change without adding an edge-specific
event queue index.

For movement, the causality should be:

```text
StepMovementEvent / ForcedMovementEvent
    -> GridMap.can_transition(...)
        -> allowed: normal entity-left/entity-entered cell events
        -> blocked by unknown edge: MOVEMENT_COLLISION child event with edge_key
```

`MOVEMENT_COLLISION` already exists. Reusing it with edge details is enough.
It should be parented under the movement step, just like cell spatial events are
parented today. That keeps combat log and stream lineage honest.

### Sense Propagation Impact

`SpatialSensesCallback.SPATIAL_EVENTS` does not need new event types for the
first implementation. It already includes tile, object, light, perceivability,
and movement collision events. It only needs to understand that a
`SpatialChangeEvent` may carry `edge_key` and that affected positions can be the
two cells adjacent to that edge.

For a spatial event with `edge_key`:

- If `requires_fov` is true, recompute visibility for subscribed observers.
- If `requires_paths` is true, mark `senses._paths_dirty = True`.
- If `requires_light_recompute` is true, recompute light before visibility
  deltas are emitted.
- If the event is `MOVEMENT_COLLISION`, add the edge to
  `senses.collision_blocked_edges` or an equivalent edge-memory field.
- If the edge object becomes newly visible or hidden, emit edge/object deltas in
  `SensoryUpdateEvent`.

Cell subscriptions can support the first implementation:

```python
subscribers =
    grid.get_subscribers_at(position_a)
    | grid.get_subscribers_at(position_b)
```

Do not add explicit edge subscriptions in the first implementation. The existing
cell subscription model can cover edge changes by notifying both adjacent cells.
Only add edge subscriptions later if profiling or fog-memory behavior proves
the cell fan-out is too coarse.

### Stream/API Impact

The SSE stream is mostly event-model driven. `DndEventStream` already publishes
every registered `EventQueue` event as a `game_event`. If we extend
`SpatialChangeEvent`, no new stream event category is needed.

Required downstream work:

- Ensure the added `SpatialChangeEvent` edge fields serialize cleanly through
  Pydantic `model_dump(mode="json")`. Use JSON-friendly edge keys, probably
  either `[[x1, y1], [x2, y2]]` or a typed object, not a tuple used as a dict
  key.
- Update frontend reducers for existing event types to read optional edge
  payload fields.
- Add edge state to full-state snapshots, map-editor snapshots, and resync
  endpoints. A reconnecting client cannot reconstruct all edge state from only
  replayed recent events.
- Add edge/object fields to API map models so the renderer can draw doors and
  walls between cells rather than as floor objects.
- Decide whether `SensoryUpdateEvent` includes edge deltas in the first slice or
  only marks `paths_dirty`. If the renderer needs fog-aware edge rendering, add
  edge deltas immediately.

Combat log impact should be small. Structural changes such as placing a wall or
opening a door usually do not need combat log entries. Edge collisions and edge
trigger effects may need logs, but those should be generated by their parent
movement/action events rather than by passive senses updates.

## Data Structures

Suggested additions to `GridMap`:

```python
_edge_objects_by_edge: dict[EdgeKey, set[UUID]]
_edge_position_by_object: dict[UUID, EdgeKey]
```

These are attachment indexes for objects, not a replacement for tiles. Intrinsic
movement borders remain on `Tile.border_*`.

Avoid creating a new object for every adjacent pair. Prefer sparse edge
attachments:

- No edge record means normal open edge.
- Edge record exists only when there is a blocker, modifier, condition, or
  editor-authored metadata.
- If a future feature truly needs conditions on a bare edge with no object,
  add the smallest sparse target object for that feature then.

## Diagonal Movement Rules

Current pathfinding allows diagonals. Existing tile border diagonal behavior is
permissive: at least one touching destination border must be open.

For edge blockers, this must be made explicit.

Possible policies:

### Permissive Corner Policy

Diagonal from `(x, y)` to `(x + 1, y + 1)` is allowed if at least one of these
orthogonal transitions is open:

```text
(x, y) -> (x + 1, y)
(x, y) -> (x, y + 1)
```

This matches the current destination-tile border spirit.

### Strict Corner Policy

Diagonal is allowed only if both touching orthogonal transitions are open.

This avoids "squeezing through a closed corner" and is common in tactical
pathfinding.

### Direct Diagonal Edge Policy

Diagonal edges exist separately and can be blocked independently.

This is powerful but likely overkill for D&D 5e grid maps.

Recommendation: keep the existing permissive rule during migration, but make
the policy a named function:

```python
grid.can_diagonal_transition(from_pos, to_pos, ...)
```

That way changing the rule later does not require hunting through Dijkstra,
movement, shove, jump, threat, and FOV code.

## Movement Refactor

### Dijkstra

Current Dijkstra accepts:

- `is_walkable(x, y)`
- `can_enter(from_pos, to_pos)`
- `cost_func(x, y)`

Target:

```python
can_transition(from_pos, to_pos) -> bool
cost_transition(from_pos, to_pos) -> float
```

Initial implementation can keep the old function shape and pass:

```python
is_walkable = lambda x, y: True for tile existence prefilter
can_enter = grid.can_transition
cost_func = destination tile movement cost
```

Long-term, transition cost may need to include edge costs:

- Climbing over low wall.
- Opening heavy curtain.
- Squeezing through bars.
- Difficult threshold.
- Height step.

### Move Execution

`Move._apply()` should use the same transition query used by Dijkstra:

```python
if not grid.can_transition(from_pos, to_pos, source_entity.uuid, subjective=False):
    if grid.can_transition(... subjective=True):
        record collision
    break
```

This closes the current gap where path generation honors borders but execution
only rechecks cell walkability.

### Forced Movement

Forced movement should also use `can_transition()` unless a specific effect says
it ignores walls/edges.

This fixes the current asymmetry where shove-like logic can ignore tile borders.

### Jump

Jump is a rules decision.

Options:

- Landing-only: only destination cell must be walkable; edge blockers do not
  matter. Good for jumping over low walls and pits.
- Landing-edge-aware: final transition into the landing cell must be legal.
  Good for closed windows, floor-to-ceiling barriers, and sealed rooms.
- Path-aware: every transition along the jump path must be legal. This makes
  Jump too similar to Move and contradicts current behavior.

Recommendation: introduce `MovementBypassProfile` rather than hardcoding.

```python
class MovementBypassProfile:
    ignores_intermediate_cell_walkability: bool
    ignores_intermediate_edge_movement: bool
    requires_landing_edge_access: bool
```

Normal Move:

```text
requires all cells and edges
```

Jump:

```text
ignores intermediate cell walkability
ignores intermediate low obstacles
requires landing cell walkable
landing edge policy TBD
```

Teleport:

```text
ignores all intermediate cells and edges
requires destination cell valid
```

Forced movement:

```text
requires all cells and edges unless effect says otherwise
```

## Threat, Reach, And Opportunity Attacks

Current threat uses `Senses.get_threathened_positions()`, based on adjacent
visible tile-walkable positions.

This can leak through edge blockers:

- Enemy behind a closed edge-door may still be in a tile-walkable adjacent cell.
- A wall between two cells should usually prevent melee threat across that edge.

Target:

```python
entity.get_threatened_positions()
```

should derive from:

- Reach.
- Visibility/perceivability.
- Destination cell walkability for standing creatures.
- Edge attackability/line of effect.

This should not live in `Senses` long-term if it needs `Entity`-level access and
combat rules.

Opportunity attacks should use the new threat model. `StepMovementEvent` already
contains `from_position` and `to_position`, which is enough to reason about
leaving threatened space once threat is edge-aware.

## Object Discovery And Action Spam

If walls become objects, the normal `senses.objects` and
`get_available_actions()` pipeline can become noisy.

Avoid this by separating:

- Perceivable map structures.
- Interactable objects.
- Targetable/breakable objects.
- Loot/pickup objects.

Suggested flags:

```python
is_structure: bool
is_interactable: bool
is_targetable: bool
include_in_senses_objects: bool
include_in_available_object_actions: bool
```

For a plain wall segment:

```text
is_structure=True
is_interactable=False
is_targetable=False or True only if destructible
include_in_senses_objects=False
include_in_available_object_actions=False
```

For a door:

```text
is_structure=True
is_interactable=True
include_in_senses_objects=True when visible/perceivable and nearby enough
include_in_available_object_actions=True when usable
```

For a secret door:

```text
include only if detected
```

## Conditions On Edges

The condition system is block-based and already works on entities, tiles, and
items. Edge effects should use those existing targets first.

Preferred targets:

1. Conditions attach to edge-attached objects.

   Good for doors, walls, windows, force fields, and anything that already has a
   structural object.

2. Conditions attach to one of the adjacent tiles with an `edge_key` or
   direction field.

   Good for a temporary effect on a bare transition, while still using the
   existing tile condition lifecycle.

Only introduce a dedicated sparse edge target later if tile-attached edge
conditions become awkward in practice.

Edge condition examples:

- Arcane Lock: modifies a door edge object.
- Wall of Force: creates edge blockers.
- Web over doorway: adds movement cost or restraint trigger on crossing.
- Burning doorway: hazard on crossing, not occupying either cell.

Crossing hazards should first be handled during `StepMovementEvent`, using the
same transition data used by movement validation. A new crossing event should
only be added if multiple independent systems later need to subscribe to
boundary crossing as its own trigger surface.

## Serialization And Save/Load

Map saves currently serialize tiles and floor objects. Edge objects need their
own save layer:

```json
{
  "edge_objects": [
    {
      "uuid": "...",
      "catalog_id": "door",
      "edge": [[4, 2], [5, 2]],
      "state": {
        "is_open": false,
        "locked": false
      }
    }
  ]
}
```

Intrinsic edges can be saved sparsely:

```json
{
  "edges": [
    {
      "edge": [[4, 2], [5, 2]],
      "blocks_movement": true,
      "blocks_vision": true,
      "kind": "stone_wall"
    }
  ]
}
```

Backward compatibility:

- Existing wall tiles remain valid.
- Existing door cell objects remain valid.
- New maps can choose edge walls/doors.
- A migration utility can convert certain wall-tile corridors into edge walls
  later, but this should not be automatic at first.

## Testing Plan

Add focused tests. Do not run the full test suite.

### Edge Model Tests

File suggestion: `examples/test_edge_spatial_model.py`

Cases:

- Empty edge allows transition.
- Closed edge wall blocks transition but both cells remain walkable.
- Open edge door allows transition.
- One-way edge blocks only one direction.
- Edge movement mode behavior: walking blocked, flying allowed or blocked by
  configured wall type.
- Diagonal policy matches current intended behavior.

### Pathfinding Tests

Cases:

- `senses.paths` cannot cross closed edge door.
- Opening edge door marks paths dirty and recomputes reachable cells.
- Hidden/invisible edge blocker does not leak through subjective pathing.
- Actual movement collides with hidden objective edge blocker.
- Edge collision memory blocks the edge but not the destination cell from other
  directions.

### Vision Tests

Cases:

- Closed edge wall blocks FOV.
- Open edge door restores FOV.
- Window blocks movement but not FOV.
- Curtain blocks FOV but not movement.
- Magical darkness remains cell-based and distinct from physical edge blocking.

### Light Tests

Cases:

- Torchlight does not pass through closed edge door.
- Torchlight updates after edge door opens.
- Wall torch mounted on edge illuminates correct side(s), depending on design.

### AoE Tests

Cases:

- Sphere/cone/line blocked by edge wall.
- Cylinder ignores lateral edge walls if that remains the spell model.
- Thunderwave/gust forced movement stops at edge wall.

### Action Discovery Tests

Cases:

- Plain edge walls do not appear as object actions.
- Edge door appears when adjacent/perceivable.
- Secret edge door appears only after detection.

### Map Editor Tests

Cases:

- Can place edge wall and edge door.
- Snapshot includes edge objects separately from floor objects.
- Save/load round-trips edge objects.
- Walkability endpoint reports transition blockers, not just cell blockers.
- Visibility endpoint reports edge blockers.

## Bottom-Up File Guidelines

Implement from low-level pure geometry upward. Do not start with door gameplay.

### 1. `dnd/core/geometry.py`

- Add `EdgeKey` normalization helpers or import them from a tiny low-level
  spatial helper.
- Add supercover/transition-preserving line traversal.
- Add helpers that expose adjacent transitions from a path.
- Keep this module pure. No `GridMap`, no `Entity`, no events.

### 2. `dnd/core/shadowcast.py`

- Add the authoritative edge-aware FOV API.
- It must accept `blocks_cell(position)` and `can_cross(from_pos, to_pos)`.
- The first implementation can use radius + supercover raycast for correctness.
- Existing recursive shadowcast can remain as compatibility only until it can
  call the same transition predicate.

### 3. `dnd/core/events.py`

- Extend `SensesUpdateHint`.
- Extend `SpatialChangeEvent` with optional edge fields.
- Extend existing factory methods; do not add new event types first.
- Ensure `get_affected_positions()` returns both adjacent cells for edge
  changes.

### 4. `dnd/core/base_block.py` And `dnd/blocks/base_item.py`

- Add default edge blocker hooks that delegate to existing cell hooks.
- Add optional object metadata for `spatial_layer`, `object_role`, and edge
  attachment.
- Extend `_notify_blocking_changed(...)` to include edge metadata and full
  channel hints when the item is edge-attached.

### 5. `dnd/core/gridmap.py`

- Add transition query helpers.
- Add optional object edge indexes.
- Route `compute_paths()` through `can_transition()`.
- Route `compute_fov()` through edge-aware geometry and `can_see_transition()`.
- Route light propagation through `can_light_transition()`.
- Route `compute_propagation_fov()` and barrier checks through
  `can_propagate_transition()`.
- Update `_on_vision_blocking_changed()` to recompute light for all affected
  positions from `SpatialChangeEvent.get_affected_positions()`.

### 6. `dnd/blocks/sensory.py`

- Add edge collision memory to `Senses`.
- Teach `SpatialSensesCallback` to use `edge_changed_positions` for
  subscription checks.
- Keep `requires_fov` and `requires_paths` as the main invalidation channels.
- Add edge deltas to `SensoryUpdateEvent` only when the renderer needs them;
  do not invent a second senses pipeline.

### 7. `dnd/entity.py`

- `compute_senses_from_position()` should keep one flow:
  - transition-aware FOV
  - light filtering
  - transition-aware paths
  - visible entity/object filtering
- `senses.walkable` can remain cell-oriented, but any UI that needs boundary
  rendering must read edge state separately.

### 8. Actions, Spells, And AoE

- `Move`, forced movement, shove, and interception-like movement must validate
  each step with `can_transition()`.
- Attack/spell LOS can keep using `senses.entities` / `senses.visible`, because
  those become transition-aware.
- `POSITION_LOS` actions keep using `senses.visible`.
- `dnd/core/aoe.py` must use transition-aware propagation FOV.
- Line/ray spells should use the transition-aware line helper where they need
  exact boundary blocking.

### 9. Server/API/Renderer

- Keep the SSE event category unchanged.
- Add optional edge fields to event payload models if mirrored in API schemas.
- Add edge object/snapshot data for full-state resync.
- Keep structural wall segments out of normal object-action spam.

## Migration Plan

### Phase 1: Update Computational Geometry

- Add `EdgeKey` helper functions in the low-level geometry/spatial helper layer.
- Add `supercover_line(...)` or equivalent line traversal that preserves touched
  cells and adjacent transitions.
- Add `adjacent_transitions(path)` / edge normalization helpers.
- Add `raycast_clear(...)` that receives `blocks_cell` and `can_cross`
  callbacks.
- Add an authoritative edge-aware FOV helper in `dnd/core/shadowcast.py` or a
  sibling geometry module:
  - accepts `blocks_cell(position)`
  - accepts `can_cross(from_pos, to_pos)`
  - marks visible positions
  - preserves old cell-only behavior when `can_cross` always returns true
- Keep the existing recursive shadowcast API as compatibility only until it can
  ask transition questions directly.

No game objects or events required yet. This phase is pure computational
geometry.

### Phase 2: Add Transition Kernel, Preserve Current Behavior

- Add `TransitionContext` / `TransitionState` or equivalent simple helpers.
- Add `GridMap.can_transition()` for movement.
- Add `GridMap.can_see_transition()` for vision.
- Add `GridMap.can_light_transition()` for light.
- Add `GridMap.can_propagate_transition()` for AoE/line-of-effect.
- Keep current behavior exactly:
  - movement uses existing `Tile.can_enter_from()`
  - vision still derives from cell `Tile.visible` / `blocks_vision()`
  - light still follows current FOV semantics
  - propagation still follows current physical cell blockers
- Do not add new event types.

No new edge objects required yet. This phase is successful only if all existing
tests for pathing, senses, light, and AoE still pass with consumers routed
through the new queries.

### Phase 3: Route Every Consumer Through Transition Queries

- Update `GridMap.compute_paths()` to call `can_transition()`.
- Update `Move._apply()` step rechecks.
- Update forced movement/shove logic.
- Update `GridMap.compute_fov()` to use the new edge-aware FOV helper with
  `can_see_transition()`.
- Update light propagation to use the same edge-aware FOV helper with
  `can_light_transition()`.
- Update `compute_propagation_fov()` / AoE filtering to use the same geometry
  helper with `can_propagate_transition()`.
- Update LOS helpers and `POSITION_LOS` assumptions to rely on the new visible
  cells derived from transition-aware FOV.
- Add cell and edge collision memory to `Senses`, but keep existing cell
  behavior unchanged.

This phase is the parity checkpoint: movement, senses, light, and propagation
all consume the same transition source of truth before new edge content is
introduced.

### Phase 4: Add Intrinsic Directional Vision/Propagation

- Add directional tile vision border data or equivalent tile-owned transition
  contributors.
- Add directional propagation/light border data if it differs from vision.
- Keep movement borders separate from vision/light/propagation borders.
- Add tests for windows, curtains, low walls, and full walls:
  - movement blocked but vision allowed
  - vision blocked but movement allowed
  - movement and vision both blocked
  - light blocked independently if needed
  - AoE propagation blocked independently if needed

### Phase 5: Edge-Attached Doors And Walls

- Add optional edge attachment indexes for objects in `GridMap`.
- Add edge blocker interface methods to `BaseBlock` or a mixin.
- Add an edge door item/object class.
- It does not set cell `blocks_movement` or cell `blocks_vision_field`.
- It contributes movement, vision, light, and propagation facts through the
  transition kernel.
- Opening/closing fires existing `SPATIAL_OBJECT_CHANGED` with `edge_key` and
  full senses hints:
  - `requires_paths` when movement changed
  - `requires_fov` when vision changed
  - `requires_light_recompute` when light changed
  - propagation cache invalidation when propagation changed
- Add tests showing one edge door changes paths, visible cells, visible
  entities/objects, light, and AoE propagation consistently.

This is the first phase where edge doors/walls become real gameplay/map
content.

### Phase 6: API, Renderer, Map Editor

- Expose edge objects in snapshots.
- Add editor placement for edge walls and doors.
- Add rendering metadata for wall orientation and door state.
- Add stream reducer support for optional edge fields on existing spatial events
  and `SensoryUpdateEvent` edge deltas.
- Filter structural walls out of normal object lists/actions.

### Phase 7: Example Migration

- Keep existing full-tile wall tests.
- Add edge wall/door examples.
- Slowly migrate arena maps where a thin wall is intended.
- Keep full-cell blockers for boulders, pillars, water, rubble, and large
  obstacles.

## Caveats And Design Decisions

### FOV Algorithm Risk

Shadowcasting is cell-blocker oriented. Edge blockers require careful handling
or a different algorithm. Movement can become edge-aware earlier than vision, but
the final design must not stop there.

### Diagonal Semantics

Current diagonal border behavior is permissive. Edge blockers force us to name
the policy. This affects movement, reach, OA, and possibly FOV.

### Subjective Edge Blockers Are Subtle

Different hidden edge objects have different perceived behavior:

- Secret door may be perceived as a wall.
- Invisible wall may be perceived as open.
- Illusory wall may be perceived as blocked but objectively open.

The subjective API must not assume "imperceivable means passable" for every edge
object. It needs object-specific perceived-state logic.

### Object Spam

If every wall segment is an object, naive object discovery becomes unusable.
Structural object filtering is not optional.

### Conditions Need Edge Targets

Some effects target an edge without a physical object. First try a tile
condition with an `edge_key` or direction field so the existing tile condition
lifecycle remains the owner. Add a dedicated sparse edge target only if that
becomes genuinely strained.

### Cover Is Related But Separate

Edge blockers are not enough to model cover. A low wall, arrow slit, window, or
portcullis may not fully block vision but may affect attacks. This proposal
should not try to solve cover completely, but it should avoid blocking future
cover work.

### Backward Compatibility

Full-cell walls are still useful:

- Pillars.
- Large boulders.
- Rubble.
- Solid rock cells.
- Water/lava/gaps.
- Occupied terrain hazards.

The refactor should add edge geometry, not delete cell geometry.

## Open Questions

1. Should edge walls be represented as edge-attached objects, or should some
   authored walls remain intrinsic tile border data?

2. Should edge-attached objects use `BaseItem` directly, or should there be a
   small structural-object flag/mixin on top of existing item/object behavior?

3. Should recursive shadowcast be adapted to `can_cross(from, to)`, or should
   the first authoritative FOV use edge-aware raycast-per-candidate and keep
   shadowcast as an optimization?

4. Should diagonal movement remain permissive or become strict around blocked
   corners?

5. How should secret doors report subjective movement?

6. Should a closed door block light exactly like vision?

7. How should wall-mounted objects, such as wall torches, attach to edges rather
   than cells?

8. Should attack targeting use edge propagation, FOV, or a named line-of-effect
   transition query?

9. What should the player remember about edge state under fog of war?

10. How much of the old `Tile.border_*` API should remain public after the edge
    layer is introduced?

## Recommended First Implementation Slice

A safe first slice:

1. Add pure geometry helpers first:
   - `EdgeKey` normalization
   - supercover/transition-preserving line traversal
   - `raycast_clear(...)`
   - edge-aware FOV helper in `shadowcast.py` or a sibling geometry module
2. Add `TransitionContext` and transition query helpers in `GridMap` without
   importing `Entity`, item, action, or server code.
3. Implement all four core channels with old behavior preserved:
   - movement: existing cell walkability plus `Tile.can_enter_from()`
   - vision: existing `is_blocking()` semantics
   - light: existing FOV/light semantics
   - propagation: existing physical cell blockers
4. Route the existing consumers through those queries:
   - Dijkstra and movement validation
   - FOV / visible cells through the new edge-aware FOV API
   - light recomputation through the same geometry API
   - AoE propagation through the same geometry API
   - LOS/position targeting through `senses.visible`
5. Extend `SpatialChangeEvent` and `SensesUpdateHint` with optional edge fields,
   without adding new event types.
6. Add parity regression tests proving old full-cell walls, doors, tile
   borders, light, AoE, and targeting behave exactly as before.

Only after that:

7. Add directional vision/light/propagation border semantics.
8. Add sparse edge object attachment indexes.
9. Add a prototype `EdgeDoor` that affects movement and vision together.
10. Emit existing `SPATIAL_OBJECT_CHANGED` with `edge_key` when the prototype
   door opens/closes.
11. Add parity tests for one edge door:
    - paths change
    - `senses.visible` changes
    - visible entities/objects change
    - light changes
    - AoE/line-of-effect changes
    - stream payload carries the same spatial event with edge details

This keeps the first implementation slice honest: no exposed edge gameplay
until movement, senses, light, propagation, and rendering are reading the same
transition facts.
