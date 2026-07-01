# Tile Directional Blocking Refactor Plan

Status: governing plan, supersedes `EDGE_BASED_SPATIAL_REFACTOR_PLAN.md`

This document describes the minimal refactor for directional movement, vision,
light, and propagation blocking. It is based on the current code and the
existing tile-positioned block model.

The core rule is:

```text
Blocks/items/entities stay on tiles.
Those blocks can contribute directional blocking to their own tile.
A transition from tile A to adjacent tile B checks both A and B.
Movement, FOV, light, AoE/line-of-effect, senses, targeting, and streams must
all consume those same tile directional facts.
```

Existing blocks/items/entities expose directional blocking behavior. GridMap
recomputes tile-owned derived directional state. All spatial algorithms ask
GridMap whether a transition is allowed.

## Current Code Facts

### Tiles

`dnd/core/base_tiles.py`

- `Tile` is a `BaseBlock`.
- `Tile.walkable` and movement-cost `ModifiableValue`s control cell movement.
- `Tile.visible` controls cell vision blocking.
- Current movement borders are:
  - `border_north`
  - `border_south`
  - `border_east`
  - `border_west`
- `Tile.can_enter_from(from_position)` checks only the destination tile.
- Diagonal movement currently uses a permissive rule: one of the relevant
  orthogonal borders being open is enough.

### Cell Walkability

`dnd/core/gridmap.py`

- `GridMap.is_walkable(x, y, mode)` checks whether the tile exists and allows
  movement for the mode.
- `GridMap.is_walkable_for(...)` adds:
  - blocking entities on the destination cell;
  - blocking objects on the destination cell;
  - subjective hiding/invisibility logic;
  - hazard avoidance when `walk_in_danger=False`;
  - `senses.collision_blocked` remembered cells.
- `GridMap.compute_paths(...)` uses Dijkstra.
- The Dijkstra `walkable_check` is cell-based.
- The Dijkstra `can_enter` callback currently calls only
  `destination_tile.can_enter_from(from_pos)`.

### Vision And Propagation

`dnd/core/gridmap.py`, `dnd/core/shadowcast.py`, `dnd/core/aoe.py`

- `GridMap.compute_fov(...)` uses recursive shadowcast with a cell callback:
  `is_blocking(x, y, observer_uuid)`.
- `GridMap.is_blocking(...)` checks the tile and objects in that cell.
- `GridMap.compute_propagation_fov(...)` uses the same shadowcast shape with
  `is_blocking_propagation(...)`.
- `GridMap.is_blocking_propagation(...)` is cell-based and treats non-visible
  tiles and vision-blocking objects as physical barriers.
- AoE shape filtering in `dnd/core/aoe.py` uses `compute_propagation_fov(...)`
  when barrier filtering is needed.
- `POSITION_LOS`, spell LOS, and attack LOS mostly inherit from
  `Entity.senses.visible`.

### Items And Objects

`dnd/blocks/base_item.py`

- `BaseItem` is a `BaseBlock`.
- Floor objects already have:
  - `blocks_movement`
  - `blocks_vision_field`
- `BaseItem.blocks_walking(...)` returns `blocks_movement`.
- `BaseItem.blocks_vision(...)` returns `blocks_vision_field`.
- `_notify_blocking_changed(...)` fires existing
  `SPATIAL_OBJECT_CHANGED` when an object changes movement or vision blocking.

`dnd/items/test_items.py`

- `TestDoorA` is a normal tile-positioned `UsableItem`.
- Open/close actions update `is_open`, `blocks_movement`, and
  `blocks_vision_field`, then call `_notify_blocking_changed(...)`.
- These doors are full-cell blockers today. They should keep working during the
  migration.

### Senses And Reactive Events

`dnd/blocks/sensory.py`

- `Senses.visible` is the authoritative visible-position map used by LOS and
  targeting.
- `Senses.paths` and `Senses.safe_paths` are path maps.
- `Senses.walkable` is used by `get_threatened_positions()`.
- `Senses.collision_blocked` remembers cells discovered blocked by subjective
  pathing collisions.
- `SpatialSensesCallback` listens to:
  - `SPATIAL_ENTITY_ENTERED`
  - `SPATIAL_ENTITY_LEFT`
  - `SPATIAL_TILE_CHANGED`
  - `SPATIAL_OBJECT_PLACED`
  - `SPATIAL_OBJECT_REMOVED`
  - `SPATIAL_OBJECT_CHANGED`
  - `SPATIAL_PERCEIVABILITY_CHANGED`
  - `SPATIAL_LIGHT_CHANGED`
- The callback uses `SensesUpdateHint`:
  - `requires_fov=True` recomputes visibility and can mark paths dirty.
  - `requires_paths=True` marks paths dirty.
  - `light_changed_positions` performs targeted light filtering.
  - object/entity placed/removed hints update visible dictionaries.
- The callback emits `SENSORY_UPDATE` events with visible cell/entity/object
  deltas and `paths_dirty`.

### Event Stream

`server/event_server.py`

- Events are serialized with `model_dump(mode="json")`.
- SSE emits `"game_event"` payloads.
- The websocket stream sends event dictionaries and filters by
  `event_type`.
- Adding optional JSON-safe fields to existing event models is compatible with
  this stream shape.

## Target Model

### Direction Names

Use the existing tile-relative direction language:

- `north`: neighbor at `(x, y + 1)` relative to a tile.
- `south`: neighbor at `(x, y - 1)`.
- `east`: neighbor at `(x + 1, y)`.
- `west`: neighbor at `(x - 1, y)`.

For a transition `A -> B`, each endpoint evaluates the direction from itself to
the other endpoint:

```text
A blocks leaving east?  A=(0,0), B=(1,0)
B blocks entering west? B=(1,0), A=(0,0)
Transition is allowed only if both answers allow it.
```

This makes asymmetry explicit. A wall-like object on A can block leaving east.
A different object on B can block entering west. Both facts belong to their
respective tiles.

### Tile Directional State

Extend `Tile` with per-channel directional state. Keep the current movement
fields working.

Movement:

- Existing `border_north/south/east/west` remain supported.
- Add derived object/entity contribution for movement while preserving intrinsic
  tile borders.

Vision:

- Add directional tile state for vision.
- It must be separate from `Tile.visible`, because `visible=False` is still a
  full-cell wall while directional vision blocking is per direction.

Light:

- Add directional tile state for light.
- It must be separate from vision because later effects may block light and
  vision differently.

Propagation:

- Add directional tile state for physical propagation / line-of-effect.
- It must be separate from ordinary vision because current AoE propagation
  intentionally ignores magical darkness while still respecting physical
  barriers.

Recommended implementation shape:

```text
Tile intrinsic directional fields:
  movement: existing border_north/south/east/west
  vision: vision_border_north/south/east/west, default True
  light: light_border_north/south/east/west, default True
  propagation: propagation_border_north/south/east/west, default True

Tile derived contribution fields:
  object_movement_border_north/south/east/west, default True
  object_vision_border_north/south/east/west, default True
  object_light_border_north/south/east/west, default True
  object_propagation_border_north/south/east/west, default True
```

The effective answer is intrinsic AND derived contribution.

For movement, this preserves existing direct uses of `border_*` as intrinsic
tile data and avoids losing authored one-way terrain when an object opens or
closes.

Tile methods:

- `can_exit_to(to_position, channel, requester_uuid=None, subjective=False)`
- `can_enter_from(from_position, channel="movement", requester_uuid=None, subjective=False)`
- `can_see_to(...)` / `can_see_from(...)` can be thin wrappers if useful.
- `can_light_to(...)` / `can_light_from(...)`.
- `can_propagate_to(...)` / `can_propagate_from(...)`.

Compatibility:

- Existing `can_enter_from(from_position)` call sites may keep the default
  movement channel.
- Existing tests that mutate `border_*` directly should still pass.

### Objective And Subjective Resolution

Directional blocking must preserve the existing objective/subjective pattern
used by cell walkability, perceivability, light, and AoE.

Current code has these layers:

- Objective/default data lives on tiles, entities, and objects.
- `BaseBlock.blocks_walking(requesting_entity_uuid, ...)` and
  `BaseBlock.blocks_vision(requesting_entity_uuid)` already accept a requester
  so custom blockers can resolve per observer/requester.
- `GridMap.is_walkable_for(..., subjective=True)` ignores imperceivable
  blocking entities/objects, so path previews do not reveal hidden or invisible
  blockers.
- Actual movement rechecks objective walkability and records
  `MOVEMENT_COLLISION` when subjective pathing allowed a blocked step.
- `BaseBlock.is_perceivable_by(requesting_entity_uuid)` resolves stealth and
  invisibility against the observer.
- `Tile.blocks_vision(requesting_entity_uuid)` resolves magical darkness against
  the observer.
- `Tile.get_effective_light_for(observer_uuid, observer_position)` resolves
  darkvision, truesight, Devil's Sight, and the adjacent-cell darkness rule.
- `AoEShape.compute_subjective(...)` uses the caster's existing senses for
  previews; `compute_objective(...)` computes actual propagation from the shape
  origin.

Directional state follows the same split:

- Tile directional fields are the objective/default spatial facts.
- Block directional methods accept requester/observer context and can override
  field-based defaults for subjective or custom behavior.
- Subjective movement/pathing can treat imperceivable directional blockers as
  open.
- Objective movement execution uses the same transition query with
  `subjective=False`.
- Directional vision uses observer-aware methods, then ordinary senses filtering
  still applies light and perceivability.
- Directional light and propagation keep their own channel semantics; they do
  not inherit ordinary vision answers by default.

### Block Directional Contributions

Extend `BaseBlock` with default directional methods that return no blocking.
`BaseItem` can implement those methods from data fields, and subclasses can
override for dynamic or subjective behavior.

Data fields on `BaseItem` should be tile-relative:

```text
blocks_movement_north/south/east/west: bool = False
blocks_vision_north/south/east/west: bool = False
blocks_light_north/south/east/west: bool = False
blocks_propagation_north/south/east/west: bool = False
```

Method surface on `BaseBlock`:

```text
blocks_directional_movement(direction, requester_uuid=None, mode=MovementMode.WALKING) -> bool
blocks_directional_vision(direction, observer_uuid=None, subjective=False) -> bool
blocks_directional_light(direction, observer_uuid=None, subjective=False) -> bool
blocks_directional_propagation(direction, requester_uuid=None, subjective=False) -> bool
```

The default implementation returns `False`.

`BaseItem` returns the corresponding field value. A door can override the
methods or update the fields when opening/closing. A future subjective illusion
or secret door can override the methods and inspect requester/observer while
preserving GridMap's dependency direction.

Full-cell fields remain:

- `blocks_movement`
- `blocks_vision_field`

These continue to mean “this whole tile blocks the cell.” Directional fields
mean “this object contributes blocking from its own tile in these directions.”

### GridMap Derived Tile Recompute

GridMap owns propagation from placed blocks to tile directional state.

Add:

- `GridMap.recompute_tile_directional_blocking(position)`
- `GridMap.recompute_directional_blocking_for_positions(positions)`

For one tile position:

1. Reset the tile's derived object/entity directional contribution fields to
   all `True`.
2. Scan objects in `_objects_by_position[position]`.
3. For each object, ask the directional methods for each direction/channel.
4. If any object blocks a channel/direction, set that derived border to `False`.
5. If entities are allowed to contribute directional blockers, scan
   `_entities_by_position[position]` the same way. Default entity behavior leaves
   every directional contribution open.
6. Return a compact diff of channel/direction pairs that changed.

The recompute writes only the tile at `position`. The transition query reads
both endpoints, so a tile-local contribution is enough.

The derived tile contribution is the objective/default contribution. Subjective
exceptions are resolved at query time by calling the contributing block methods
with requester/observer context. This mirrors current cell behavior: the map can
hold objective blockers while subjective pathing and senses selectively ignore
imperceivable blockers.

Trigger recompute from:

- `GridMap.place_object(...)`
- `GridMap.remove_object(...)`
- `BaseItem._notify_blocking_changed(...)`, through GridMap
- `GridMap.move_entity(...)` old and new positions if entity directional
  blockers are enabled
- any future tile/object setter that changes directional blocking fields

Object actions update their own state and notify GridMap, exactly like current
door open/close does for cell blocking. GridMap owns the derived tile
directional contribution fields.

## Transition Queries

Add direct GridMap channel-specific transition queries. The first implementation
keeps the result as a boolean query surface.

### Movement

```text
can_move_between(from_pos, to_pos, requester_uuid=None, mode=..., walk_in_danger=True,
                 subjective=False, collision_blocked=None,
                 directional_collision_blocked=None)
```

Checks:

1. `from_pos` and `to_pos` are adjacent enough for the current movement step.
2. Source tile exists.
3. Destination tile exists.
4. Source tile effective movement border allows exiting toward destination for
   this requester and subjective/objective mode.
5. Destination tile effective movement border allows entering from source for
   this requester and subjective/objective mode.
6. Destination cell is walkable via existing `is_walkable_for(...)` cell logic.
7. Directional collision memory leaves this exact tile-local direction open.

`is_walkable_for(...)` should remain the cell-level query. Movement callers use
`can_move_between(...)` when they know both endpoints.

When `subjective=True`, directional movement blockers that are imperceivable to
the requester resolve as open. When actual movement executes, callers use
objective resolution. If subjective movement allowed the step and objective
movement blocks it, the movement action records directional collision memory and
fires the existing `MOVEMENT_COLLISION`.

### Vision

```text
can_see_between(from_pos, to_pos, observer_uuid=None, subjective=True)
```

Checks:

1. Source and destination tiles exist.
2. Source tile effective vision border allows looking toward destination for
   this observer.
3. Destination tile effective vision border allows being seen from source for
   this observer.
4. Cell blocking is still evaluated separately by ray/FOV logic using
   `is_blocking(...)`.

Magical darkness remains cell/observer light behavior. Directional borders model
spatial crossing rules.

Geometric FOV can therefore be observer-specific before light filtering. After
geometric FOV is known, `Entity.compute_senses_from_position(...)` still filters
by effective light and `is_perceivable_by(...)` exactly as today.

### Light

```text
can_light_between(from_pos, to_pos, observer_uuid=None, subjective=False)
```

Checks source and destination light borders. Light propagation still also stops
on cell blockers through the light computation. The default light computation is
objective. Observer-specific light interpretation remains in
`Tile.get_effective_light_for(...)`.

### Propagation

```text
can_propagate_between(from_pos, to_pos, requester_uuid=None, subjective=False)
```

Checks source and destination propagation borders. AoE/line-of-effect still also
stops on physical cell blockers through `is_blocking_propagation(...)`.
Actual AoE effects use objective propagation. Targeting previews use subjective
shape computation, intersecting propagation with the caster's existing senses as
the current AoE code does.

## Geometry Changes

### Shared Traversal

Add pure geometry helpers in `dnd/core/geometry.py` or a sibling pure module
with no imports from GridMap, Entity, actions, server, or items:

- adjacent step extraction from a cell path;
- supercover/transition-preserving line traversal;
- `raycast_clear(start, end, can_cross, blocks_cell)`.

The helpers should accept callbacks:

```text
can_cross(from_pos, to_pos) -> bool
blocks_cell(position) -> bool
```

This keeps geometry pure and avoids import loops.

### Shadowcast

Current `dnd/core/shadowcast.py` is cell-callback based. It can reveal/block
cells, but it cannot by itself evaluate directional crossing rules between the
origin and each candidate.

Minimal correct path:

1. Keep the current recursive shadowcast when no directional vision blockers are
   active.
2. When any tile has effective directional vision blocking, compute candidate
   cells in radius and validate each candidate with transition-aware raycast:
   - `blocks_cell(position)` uses `GridMap.is_blocking(...)`.
   - `can_cross(a, b)` uses `GridMap.can_see_between(a, b, observer_uuid)`.
3. `GridMap.compute_fov(...)` remains the public API and chooses the correct
   internal path.

The same pattern applies to:

- light source propagation with `can_light_between(...)`;
- AoE/line-of-effect propagation with `can_propagate_between(...)`.

Movement, FOV, light, and AoE all route through their channel-specific
transition checks.

### Diagonal Policy

Preserve current permissive diagonal behavior for now.

For diagonal movement or diagonal rays:

- source tile checks its two relevant outgoing orthogonal directions using the
  existing “at least one open” logic;
- destination tile checks its two relevant incoming orthogonal directions using
  the same logic.

This preserves current tests around `Tile.can_enter_from(...)` while extending
the rule to both endpoints and other channels.

## Consumer Routing

### Pathfinding

`GridMap.compute_paths(...)`

- Keep Dijkstra.
- Keep cell `walkable_check` for destination cell occupancy/hazard logic.
- Replace destination-only `can_enter_tile(from_pos, to_pos)` with
  `GridMap.can_move_between(from_pos, to_pos, ...)`.
- Ensure `requesting_entity_uuid`, `movement_mode`, `walk_in_danger`,
  `subjective`, `collision_blocked`, and `ignore_difficult_terrain` still flow
  through.
- Entity senses continue to request paths with `subjective=True`, so hidden or
  invisible directional blockers do not leak through available path previews.

### Actual Movement

`dnd/actions.py`

- `Move._apply(...)` currently revalidates each step with
  `grid.is_walkable_for(to_pos...)`.
- Change step validation to objective
  `grid.can_move_between(from_pos, to_pos, subjective=False, ...)`.
- The post-`StepMovementEvent` recheck must use the same transition query,
  because a handler can close a door or change blocking after the precheck.
- If a planned subjective path crosses an imperceivable directional blocker,
  objective step validation fires `MOVEMENT_COLLISION` and records directional
  collision memory on the mover's senses.

### Forced Movement

`dnd/actions.py`, `dnd/spells/evocation.py`

- Forced movement currently advances by checking the next cell with
  `grid.is_walkable_for(next_pos...)`.
- Change it to use `can_move_between(current, next_pos, target_uuid, ...)`.
- `identify_blocker_at(...)` remains cell-based. Add a companion
`identify_transition_blocker(from_pos, to_pos, ...)` only if the status
message needs to name a directional blocker. Correctness comes from the
transition query; the message helper can follow later.

### Jump

Jump currently validates visible target and landing cell walkability, then steps
through the path for events.

Required:

- landing cell still uses cell walkability;
- if the jump path is intended to be physically blocked by walls/doors, validate
  the line/path using `can_propagate_between(...)` and
  `is_blocking_propagation(...)`;
- step events still fire for traversed cells as they do now.

### FOV And LOS

`Entity.compute_senses_from_position(...)`

- Continue to call `grid.compute_fov(...)`.
- Once `compute_fov(...)` is transition-aware and observer-aware,
  `senses.visible` becomes transition-aware.
- Attack LOS, spell LOS, teleport-to-visible, `POSITION_LOS`, object
  positioning actions, and other visible-position checks inherit the result.
- Geometric FOV remains distinct from final visibility. Final
  `senses.visible` still filters by effective observer light, and visible
  entities/objects still filter by `is_perceivable_by(observer_uuid)`.

### Light

`GridMap._compute_light_tiles(...)` and related light recompute paths must use
the same transition-aware geometry pattern as FOV, but with
`can_light_between(...)`.

`GridMap._on_vision_blocking_changed(...)` currently recomputes lights when a
spatial event has `requires_fov=True`. After this refactor, directional light
blocking changes also trigger light recomputation; ordinary FOV can stay open
for blockers that affect only light.

### AoE / Line Of Effect

`dnd/core/aoe.py`

- Existing barrier-aware shapes call `grid.compute_propagation_fov(...)`.
- Make `compute_propagation_fov(...)` transition-aware with
  `can_propagate_between(...)`.
- `get_barrier_positions()` remains a fast path for full-cell blockers. Add a
  GridMap boolean such as `has_directional_propagation_blockers()` so AoE uses
  the fast path only when directional propagation is fully open.
- `AoEShape.compute_subjective(...)` continues to use caster senses for
  targeting/preview.
- `AoEShape.compute_objective(...)` uses objective propagation for actual
  effects.

### Threat And Opportunity Attacks

`Senses.get_threatened_positions()` currently uses visible cells plus
`Senses.walkable`. That means it is cell-oriented.

Required audit:

- Adjacent threat stops at a directional physical blocker.
- First minimal correction: when deriving threatened adjacent cells, require
  `grid.can_propagate_between(attacker_pos, threatened_pos)` or a melee-specific
  wrapper that currently delegates to propagation.
- Opportunity attack event schemas remain unchanged; their triggering positions
  become correct once threatened positions are transition-aware.

## Event Changes

Existing event types remain the event surface.

Spatial events carry optional directional metadata when a tile-owned
directional state changes. The event type continues to describe the cause: tile
change, object placement/removal/change, entity movement, light change, or
movement collision.

### Backend Event Lifecycle

Spatial changes go through the same lifecycle as today:

```text
DECLARATION -> EXECUTION -> EFFECT -> COMPLETION
```

`GridMap._fire_spatial_event(...)` is the normal path for grid-originated
spatial events. It registers each phase through `EventQueue.register(...)`.

Important lifecycle facts:

- Normal `EventHandler` and `SpatialHandler` processing happens before
  completion. Completion is the stable observational phase.
- `Event.phase_to(COMPLETION)` runs `EventQueue.run_pre_completion_callbacks(...)`
  before the completion event is finalized.
- `SpatialSensesCallback` is registered per entity as a pre-completion callback.
  It mutates that observer's backend `Senses` and emits a child
  `SENSORY_UPDATE` event before the causative event completes.
- `SENSORY_UPDATE` itself is skipped by pre-completion callbacks to avoid
  recursive sensory updates.
- `EventQueue.register(...)` stores every phase and calls passive
  `on_event_callback` listeners for every stored event.
- The SSE bridge is one of those passive listeners, so stream publication
  follows stored event order.

Directional metadata must therefore be present on the causative spatial event
before its completion phase is created. That lets `SpatialSensesCallback` see
the final hint, recompute visibility if needed, mark paths dirty if needed, and
emit the correct child sensory delta.

### Grid Subscription Loop

`Entity.update_entity_senses(...)` subscribes the entity to the full geometric
FOV, not only currently lit visible cells. This is why light changes in a dark
but geometrically visible room can still update an observer later.

Directional changes must preserve that loop:

- `SpatialChangeEvent.get_affected_positions()` includes the changed tile and
  any adjacent tile whose transition with that tile may have changed.
- `SpatialSensesCallback` checks affected positions against
  `GridMap.get_entity_subscriptions(observer_uuid)`.
- FOV-affecting directional changes use `requires_fov=True`.
- Movement-only directional changes use `requires_paths=True`.
- Light-affecting directional changes trigger light recomputation before senses
  consume the resulting `SPATIAL_LIGHT_CHANGED` deltas.
- Propagation-only changes update backend propagation behavior and event
  metadata, while ordinary senses react only when FOV, light, movement, or
  perceivability changed.

### Senses Callback Contract

The reactive senses callback keeps the current performance boundary:

- It can recompute visibility/FOV.
- It can update visible entities/objects incrementally.
- It can update light filtering for positions in `light_changed_positions`.
- It marks `_paths_dirty` for path changes.
- Dijkstra path recomputation stays deferred to explicit full senses refreshes,
  currently turn start and movement end.

Directional movement changes must therefore mark paths dirty rather than forcing
path recomputation inside the callback.

### SSE And Client Roundtrip

Current backend stream:

```text
EventQueue.register(event)
  -> passive event_stream callback
  -> GameEventPayload(event_index, event_cursor, combat_log_cursor, event)
  -> SSE "game_event"
```

`server/event_stream.py` serializes payloads with `model_dump(mode="json")`.
Optional directional fields must be JSON-safe: lists, dicts with string keys,
booleans, numbers, strings, and nulls.

The current NeuroClient flow is:

```text
/events/subscribe SSE
  -> engine/eventStream.ts
  -> engine/eventIngestion.ts
  -> completion events only are merged/reduced
  -> engine/reducer.ts mutates authoritative world fields
  -> engine/perception.ts consumes SENSORY_UPDATE deltas
  -> render/perceptionIntent.ts stages fog/light/door visual patches
```

Observed client behavior:

- `engine/eventIngestion.ts` ignores non-completion events for reduction.
- `engine/reducer.ts` currently reduces tile walkability, tile light levels,
  floor-object placement/removal/change, entity movement, damage, conditions,
  and encounter turn state.
- `engine/perception.ts` applies `SENSORY_UPDATE` visible/seen/entity/object
  deltas to authoritative and visual perception maps.
- `render/perceptionIntent.ts` consumes `SPATIAL_LIGHT_CHANGED` for visual light
  patches and `SPATIAL_OBJECT_CHANGED.object_is_open` for visual door patches.
- `engine/awDiff.ts` currently diffs only tile `walkable` and `light_level`, and
  floor-object position/existence.

Backend implementation can land first with optional directional fields. The
client will ignore unknown runtime JSON fields until the frontend types/reducer
are extended. Full frontend parity later requires:

- adding directional tile fields to the client `Tile` type;
- storing directional fields in reducer tile state;
- updating `reduceEvent(...)` for directional tile/object payloads;
- extending AW diff to compare directional tile fields;
- rendering tile-positioned directional walls/doors from tile/object data;
- using existing `SENSORY_UPDATE`, `SPATIAL_LIGHT_CHANGED`, and
  `SPATIAL_OBJECT_CHANGED` streams for visual fog/light/object updates.

### New Optional Event/Hint Fields

Add JSON-safe fields to `SensesUpdateHint`:

```text
directional_positions: Optional[Set[Tuple[int, int]]]
directional_neighbors: Optional[Set[Tuple[int, int]]]
directional_channels_changed: Optional[Set[str]]
requires_light_recompute: bool = False
requires_propagation_recompute: bool = False
```

Meaning:

- `directional_positions`: tiles whose own directional state changed.
- `directional_neighbors`: adjacent tiles that may observe different transitions
  because the changed tile is one endpoint.
- `directional_channels_changed`: any of `movement`, `vision`, `light`,
  `propagation`.
- `requires_light_recompute`: light propagation geometry changed.
- `requires_propagation_recompute`: AoE/line-of-effect geometry changed. This
  mostly matters for caches and tests; AoE is usually computed on demand.

Add JSON-safe fields to `SpatialChangeEvent`:

```text
directional_position: Optional[Tuple[int, int]]
directional_directions: Optional[List[str]]
directional_channels: Optional[List[str]]
directional_blocks_movement: Optional[Dict[str, bool]]
directional_blocks_vision: Optional[Dict[str, bool]]
directional_blocks_light: Optional[Dict[str, bool]]
directional_blocks_propagation: Optional[Dict[str, bool]]
transition_from: Optional[Tuple[int, int]]
transition_to: Optional[Tuple[int, int]]
```

These are payload details for existing semantics. Use lists/dicts with string
keys so event stream JSON remains straightforward.

### `SPATIAL_TILE_CHANGED`

Current role:

- Fired when tile `walkable`/`visible` changes.
- Used by senses as FOV/path invalidation.
- Used by tile conditions and terrain effects to mark paths dirty.

Directional refactor:

- Also fired when authored tile directional borders change.
- Carry `directional_position`, `directional_directions`, and
  `directional_channels`.
- `requires_paths=True` if movement direction changed.
- `requires_fov=True` if vision direction changed.
- `requires_light_recompute=True` if light direction changed.
- `requires_propagation_recompute=True` if propagation direction changed.
- `get_affected_positions()` must include:
  - `event.position`;
  - all adjacent positions named by changed directions.

The existing event type carries the directional tile payload.

### `SPATIAL_OBJECT_PLACED`

Current role:

- Fired by `GridMap.place_object(...)`.
- Carries object metadata and coarse `blocks_vision`/`blocks_walking` hints.

Directional refactor:

- After placing the object, GridMap recomputes directional state for that tile.
- If the recompute changes any directional channel, include directional metadata
  in this same event.
- Preserve existing full-cell object placement semantics.
- `requires_paths` is true if full-cell movement or directional movement
  changed.
- `requires_fov` is true if full-cell vision or directional vision changed.
- `requires_light_recompute` is true if directional light changed or full-cell
  vision changed in a way that affects light blockers.
- `get_affected_positions()` includes the object tile and adjacent tiles for
  changed directions.

### `SPATIAL_OBJECT_REMOVED`

Current role:

- Fired by `GridMap.remove_object(...)`.
- Carries object removal and coarse blocking hints.

Directional refactor:

- Capture the old object's full-cell and directional blocking before removing it
  from the map.
- Remove it.
- Recompute directional state for the old tile.
- Include directional metadata in the same removal event when the tile's
  directional state changes.
- Existing visible-object removal behavior remains.

### `SPATIAL_OBJECT_CHANGED`

Current role:

- Fired by `BaseItem._notify_blocking_changed(...)`.
- Used for door open/close and similar state changes.
- Carries object name/map char/open state and coarse movement/vision flags.

Directional refactor:

- `BaseItem._notify_blocking_changed(...)` must compare both:
  - old/new full-cell movement and vision fields;
  - old/new directional contribution fields, or ask GridMap for the tile-state
    diff after recompute.
- Fire the same `SPATIAL_OBJECT_CHANGED` event.
- Include directional metadata if directional state changed.
- Preserve current object metadata fields:
  - `object_name`
  - `object_map_char`
  - `object_blocks_movement`
  - `object_blocks_vision`
  - `object_is_open`
- Tile-positioned directional doors/walls use this same object-change event.

This is the main event for tile-positioned directional doors/walls changing
state.

### `SPATIAL_ENTITY_ENTERED` And `SPATIAL_ENTITY_LEFT`

Current role:

- Fired by `GridMap.move_entity(...)`.
- Spatial handlers for hazards/zones listen to `SPATIAL_ENTITY_ENTERED`.
- Senses mark paths dirty and update visible entity dictionaries.
- Self movement triggers visibility recompute.

Directional refactor:

- Default behavior is unchanged.
- If entities later contribute directional blockers, moving an entity must
  recompute directional state for the old and new tile.
- Include directional metadata only when that recompute changes tile state.
- Zone/terrain spatial handlers continue to care about entity position.

### `SPATIAL_PERCEIVABILITY_CHANGED`

Current role:

- Fired when an entity's hidden/invisible/perceivability state changes.
- Leaves zone effects untouched.
- Senses recheck that entity and mark paths dirty.

Directional refactor:

- If directional blockers can be subjective/perceiver-dependent, this event may
  need stronger hints.
- For hidden entity/object blockers:
  - subjective pathing/FOV may ignore an imperceivable directional blocker;
  - objective movement may collide with it.
- Add directional metadata only if the entity itself contributes directional
  blockers and its perceivability changes how observers derive transitions.
- Usually keep existing behavior: `perceivability_entity` plus
  `requires_paths=True`.

### `SPATIAL_LIGHT_CHANGED`

Current role:

- Fired when a tile's resolved light level changes.
- Senses use `light_changed_positions` for targeted filtering.
- Hidden reveal logic listens for very bright light changes.

Directional refactor:

- The event type stays the same.
- Directional wall/door state changes are announced by the tile or object event
  that caused the geometry change.
- Directional light blockers should cause light recomputation, and recomputation
  then emits `SPATIAL_LIGHT_CHANGED` for tiles whose resolved light level
  actually changed.
- `light_level_map` remains the batch payload for changed light levels.

### `MOVEMENT_COLLISION`

Current role:

- Fired when objective movement is blocked but subjective pathing had allowed
  the step.
- Hidden entities at the collision position can be revealed by existing hidden
  reveal logic.
- `Senses.collision_blocked` stores blocked cells.

Directional refactor:

- Keep the event type.
- Add `transition_from` and `transition_to` when the collision is directional.
- Add optional `directional_position` and `directional_directions` if the
  blocker is a tile-owned directional blocker.
- Add directional collision memory to `Senses`, represented as tile-local data:

```text
directional_collision_blocked: Set[Tuple[Tuple[int, int], str]]
```

Example:

```text
((3, 4), "east")
```

This means: from tile `(3, 4)`, attempting to move east is remembered blocked.
The neighboring tile may still be entered from other directions when those
tile-local directions remain open.

The movement action should record both:

- old cell memory when the blocker is a hidden full-cell blocker;
- directional memory when the blocker is a hidden directional blocker.

The event represents the objective/subjective mismatch: subjective pathing saw
the transition as open, objective movement execution found it blocked. Hidden
reveal behavior keeps using `MOVEMENT_COLLISION`; directional metadata tells the
movement/senses layer which tile-local direction was learned.

### `SENSORY_UPDATE`

Current role:

- Observer-specific delta emitted by `SpatialSensesCallback`.
- Carries visible cells/entities/objects changes, seen cells, perception changes,
  and `paths_dirty`.

Directional refactor:

- The event type remains unchanged.
- The existing schema is sufficient for correctness when visible/path deltas are
  emitted after recomputation.
- Optional future field:

```text
directional_paths_dirty: bool
```

This is probably unnecessary because existing `paths_dirty` already covers
path invalidation. Avoid adding it unless a frontend reducer needs to distinguish
why paths became dirty.

### `StepMovementEvent`

Current role:

- Fired per movement step.
- Opportunity attacks and terrain handlers see this event.
- Carries `from_position` and `to_position`.

Directional refactor:

- The schema remains unchanged.
- The action must validate `can_move_between(from_position, to_position, ...)`
  before firing and again after handlers process the step.
- Because the event already has both endpoints, downstream reactions can inspect
  transition context with the existing event shape.

### `ForcedMovementEvent`

Current role:

- Represents push/pull movement and intentionally bypasses opportunity attacks.
- The actual grid movement still emits spatial enter/left events.

Directional refactor:

- The schema remains unchanged.
- Final-position calculation must use `can_move_between(...)`.

## Senses Callback Changes

`SpatialSensesCallback._apply_hint(...)`

Current behavior:

- `requires_fov` recomputes visibility and optionally marks paths dirty.
- `light_changed_positions` updates light filtering in subscribed visible cells.
- object/entity changes update visible dictionaries.
- `requires_paths` marks paths dirty.

Required behavior:

- If `requires_fov=True`, existing full visibility recompute remains correct,
  as long as `GridMap.compute_fov(...)` is transition-aware.
- If `requires_paths=True`, existing `_paths_dirty=True` remains correct.
- If `requires_light_recompute=True`, GridMap should have already recomputed
  light and emitted `SPATIAL_LIGHT_CHANGED`; the senses callback treats light
  recomputation as upstream work.
- When checking whether an event affects an observer, include both
  `directional_positions`, `directional_neighbors`, and `event.position`.
- `SpatialChangeEvent.get_affected_positions()` should return those positions so
  subscription/stream filters can remain simple.

## API, Renderer, And Map Editor

Expose directional state through tile data and ordinary tile-positioned floor
objects.

### `APITile`

Add fields:

```text
movement_borders: Dict[str, bool]
vision_borders: Dict[str, bool]
light_borders: Dict[str, bool]
propagation_borders: Dict[str, bool]
```

These are effective tile-owned borders after intrinsic plus derived
object/entity contributions.

### `APIGrid` And `APIGameState`

- Existing `tiles` list carries the directional data through `APITile`.
- Existing `floor_objects` remain tile-positioned objects.
- Existing door/wall object snapshots remain normal floor objects.

### Map Editor

Add editor support in tile/object terms:

- Tile patches can set intrinsic directional borders on the tile.
- Object placement remains tile placement.
- Object options may specify directional blocking fields for the object on that
  tile.
- Saving/loading round-trips tile directional fields and object directional
  fields.
- Visibility/walkability overlays use transition queries when showing
  directional blocking, alongside cell walkability.

## Import Direction

Keep the DAG:

```text
pure geometry
  <- GridMap
      <- Entity/actions/spells/server

BaseBlock/BaseItem expose polymorphic blocking methods.
GridMap asks BaseBlock methods through UUID lookup.
Tiles keep dependencies below the entity/item-subclass layer.
Senses receive transition results through GridMap-facing call sites.
```

Imports remain direct and acyclic, with shared primitives placed below GridMap.

## Implementation Slices

### Slice 1: Tile And Block Directional Surface

Files:

- `dnd/core/base_block.py`
- `dnd/blocks/base_item.py`
- `dnd/core/base_tiles.py`

Work:

- Add default directional methods to `BaseBlock`.
- Add directional data fields and method implementations to `BaseItem`.
- Add vision/light/propagation directional tile fields.
- Add derived object/entity directional contribution fields.
- Add effective directional helpers on `Tile`.
- Preserve `Tile.can_enter_from(from_position)` behavior by defaulting to the
  movement channel.

Tests:

- Existing movement border tests still pass.
- New asymmetric tile tests:
  - A blocks east, B leaves west open: `A -> B` blocked.
  - B blocks west, A leaves east open: `A -> B` blocked.
  - A blocks east only: `B -> A` is also blocked, because B must cross through
    A's east side to enter A from B.
  - A blocks east and B leaves west open proves tile-local asymmetry against
    B's authored state. One-way travel requires directional state that differs
    by travel direction.

### Slice 2: GridMap Recompute And Transition Queries

Files:

- `dnd/core/gridmap.py`

Work:

- Add `recompute_tile_directional_blocking(position)`.
- Call it from object placement/removal/change.
- Add `can_move_between`, `can_see_between`, `can_light_between`,
  `can_propagate_between`.
- Keep `is_walkable_for`, `is_blocking`, and `is_blocking_propagation` as
  cell-level helpers.

Tests:

- Tile-positioned object with `blocks_movement_east=True` changes only its own
  tile state.
- Transition checks both endpoint tiles.
- Full-cell doors still block cells as before.
- Subjective movement query treats an imperceivable directional blocker as open.
- Objective movement query treats the same blocker as closed.

### Slice 3: Geometry And FOV/Light/Propagation

Files:

- `dnd/core/geometry.py`
- `dnd/core/shadowcast.py` if needed
- `dnd/core/gridmap.py`
- `dnd/core/aoe.py`

Work:

- Add pure transition-aware line/raycast helpers.
- Route `compute_fov` through transition-aware raycast when directional vision
  blockers are active.
- Route light computation through transition-aware light crossing.
- Route propagation computation through transition-aware propagation crossing.
- Add `has_directional_*_blockers()` helpers for fast-path decisions.

Tests:

- Directional vision blocker changes FOV while movement stays open.
- Directional movement blocker changes movement while FOV stays open.
- Directional light blocker changes illumination while ordinary vision can stay
  open.
- Directional propagation blocker changes AoE spread while movement can stay
  open.
- Observer-specific directional vision blocker can differ by observer.
- AoE subjective preview and objective execution keep their current split.

### Slice 4: Movement, Forced Movement, Jump, Threat

Files:

- `dnd/actions.py`
- `dnd/spells/evocation.py`
- `dnd/blocks/sensory.py` for threat derivation

Work:

- Movement step validation uses `can_move_between`.
- Forced movement uses `can_move_between`.
- Jump path/physical travel uses propagation transition checks where relevant.
- Threat derivation uses propagation transition checks for adjacent threatened
  cells.

Tests:

- Pathing and actual movement agree.
- A hidden directional blocker causes `MOVEMENT_COLLISION` and remembers only
  that tile-local direction.
- Subjective path preview crosses an imperceivable directional blocker, then
  objective movement collides and records directional memory.
- Forced movement stops at a directional movement blocker.
- Threat stops at a directional propagation blocker.

### Slice 5: Events And Senses

Files:

- `dnd/core/events.py`
- `dnd/blocks/sensory.py`
- `dnd/conditions.py` hidden reveal collision hook, if directional collision
  metadata is needed

Work:

- Add optional directional fields to `SensesUpdateHint`.
- Add optional directional fields to `SpatialChangeEvent`.
- Update `SpatialChangeEvent.get_affected_positions()`.
- Update object/tile event constructors to accept directional metadata.
- Ensure `_on_vision_blocking_changed` also responds to light blocking changes
  through `requires_light_recompute`.
- Ensure `SpatialSensesCallback` considers affected directional positions.
- Preserve all existing event types.

Tests:

- Object directional state change emits `SPATIAL_OBJECT_CHANGED`.
- Tile directional state change emits `SPATIAL_TILE_CHANGED`.
- Existing event types appear in the event stream.
- Event JSON contains only primitive/list/dict data.
- `SENSORY_UPDATE` deltas reflect visibility/path changes after directional
  changes.

### Slice 6: API And Editor

Files:

- `server/api_models.py`
- `server/mapeditor_support.py`
- `server/event_server.py` if endpoint payloads need new fields

Work:

- Add directional border fields to `APITile`.
- Map editor save/load round-trips intrinsic tile directional fields.
- Object options can set tile-positioned directional blocking fields.
- Walkability/visibility overlays use transition-aware queries where they show
  crossing state.

Tests:

- `/grid` or state snapshots include tile directional border data.
- Map editor save/load preserves tile directional fields.
- Placed tile object with directional blocking round-trips as a normal floor
  object with options.

## Regression Tests To Run Individually

Run focused examples individually.

Core:

- `python examples/test_difficult_terrain.py`
- `python examples/test_terrain_movement_system.py`
- `python examples/spatial_events_test.py`
- `python examples/test_reactive_senses.py`
- `python examples/test_light_propagation.py`
- `python examples/test_usable_items.py`
- `python examples/test_entity_blocking.py`
- `python examples/test_invisibility_pathfinding_leak.py`
- `python examples/test_jump.py`
- `python examples/test_door_interaction.py`
- `python examples/test_thunderwave.py`

Server/editor, selected only:

- `python examples/test_mapeditor_api.py`

Add new focused examples:

- `examples/test_tile_directional_blocking.py`
- `examples/test_tile_directional_events.py`
- `examples/test_tile_directional_vision_light_propagation.py`

## Acceptance Criteria

- Existing full-cell walls and doors still work.
- Existing tile movement borders still work.
- Tile-positioned objects can contribute directional blocking while the cell
  remains otherwise usable.
- Transition `A -> B` checks both A's tile-owned direction toward B and B's
  tile-owned direction toward A.
- Movement, actual movement collision, FOV, light, AoE propagation, LOS
  targeting, senses, threat, opportunity attacks, and event streams agree.
- Objective/default tile facts and subjective/requester-aware resolution both
  work for directional movement and vision.
- Existing spatial event types carry optional directional details when tile
  directional state changes.
- API/editor expose directional data as tile and floor-object data.
