# 11. Grid, Tiles, Terrain, And Pathfinding

## Purpose

This chapter documents the engine's spatial substrate: how the map stores
tiles, entities, and objects; how tile costs become movement costs; how
pathfinding accounts for terrain, occupancy, directional borders, and hazards;
and how pure geometry becomes grid-aware area effects.

The examples are executable in both:

- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py`

The pytest file calls the same example functions, so the book examples and the
proper test suite stay in 1:1 parity.

## Source Files Studied

- `dnd/core/gridmap.py`
- `dnd/core/base_tiles.py`
- `dnd/core/dijkstra.py`
- `dnd/core/geometry.py`
- `dnd/core/aoe.py`
- `dnd/core/shadowcast.py`
- `dnd/tiles.py`
- `dnd/tile_conditions.py`
- `dnd/blocks/base_item.py`
- `dnd/items/environment.py`
- `dnd/blocks/sensory.py`
- `dnd/entity.py`
- `dnd/actions.py`
- `examples/test_difficult_terrain.py`
- `examples/test_terrain_movement_system.py`
- `examples/test_hazard_pathfinding.py`
- `examples/test_geometry.py`
- `examples/test_tile_directional_blocking.py`
- `examples/test_directional_environment_items.py`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py`

## Rules Relationship

Status: mixed.

- `SRD-aligned`: difficult terrain costs extra movement. The engine models this
  as a tile walking cost of `2`, and movement actions convert cost units to feet.
  See `interactive_ruleset/Gameplay/Combat.md`, "Difficult Terrain".
- `SRD-aligned`: creatures cannot willingly end movement in another creature's
  space. The engine enforces this by blocking occupied destination cells for
  other entities.
- `SRD-aligned`: walls, cover, and physical barriers can block line of sight and
  area propagation. The engine models these through visibility, object blockers,
  and directional propagation borders.
- `Engine adaptation`: diagonal movement is allowed and costs the same as a
  cardinal tile; a tiny internal epsilon is used only for tie-breaking path
  selection.
- `Engine adaptation`: occupied creature spaces block pathfinding rather than
  acting as difficult terrain.
- `Engine extension`: directional borders split movement, vision, light, and
  physical propagation into separate channels.
- `Engine extension`: safe paths can exclude hazard-marked tiles when the hazard
  is perceptible to the moving entity.
- `Engine extension`: cylinder AoE ignores lateral walls in the engine's 2D
  abstraction, while sphere/cone/line/cube use propagation FOV.

## GridMap And Tile Identity

`GridMap` is the authoritative spatial index. It stores:

- `_tiles`: map position to `Tile`;
- `_tiles_by_uuid`: tile UUID to position;
- entity positions and reverse position indexes;
- object positions and reverse position indexes;
- cell subscriptions;
- light sources.

Tiles are `BaseBlock` objects, so they have UUIDs, registry identity, conditions,
handlers, and modifiable values. Grid operations should go through `GridMap`
rather than mutating entity or tile indexes directly.

Example EB-11-001:

```python
tile = grid.set_tile(3, 4, walkable=True, visible=True, name="Marble Floor")

assert tile.position == (3, 4)
assert grid.get_tile(3, 4) is tile
assert grid.get_tile_by_uuid(tile.uuid) is tile
assert grid.bounds == (0, 0, 3, 4)

grid.remove_tile(3, 4)
assert grid.get_tile_by_uuid(tile.uuid) is None
```

Parity tests:

- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_001_tiles_are_grid_stored_blocks_with_uuid_lookup`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py`

## Movement Costs Define Passability

The old `Tile.walkable` boolean is legacy state. Actual passability comes from
movement-mode cost:

- cost `> 0`: passable for that mode;
- cost `<= 0`: blocked for that mode.

`Tile.get_movement_cost(mode)` reads a `ModifiableValue`, so terrain effects can
modify tile costs through normal modifier channels.

Common factories:

- `floor_factory()`: walking `1`, flying `1`, swimming `0`;
- `wall_factory()`: walking `0`, flying `0`, visible `False`;
- `water_factory()`: walking `0`, swimming `1`;
- `difficult_terrain_factory()`: walking `2`, flying `1`.

Example EB-11-002:

```python
assert floor.get_movement_cost(MovementMode.WALKING) == 1
assert wall.get_movement_cost(MovementMode.WALKING) == 0
assert water.get_movement_cost(MovementMode.SWIMMING) == 1
assert difficult.get_movement_cost(MovementMode.WALKING) == 2
```

Example EB-11-010 pins the legacy-field distinction:

```python
tile.walkable = False
assert tile.get_movement_cost(MovementMode.WALKING) == 1
assert grid.is_walkable(1, 0)

tile.walking_cost.self_static.add_max_constraint(...)
assert not grid.is_walkable(1, 0)
```

Parity tests:

- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_002_tile_movement_modes_define_walkability`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_010_walkability_is_cost_driven_not_the_legacy_flag`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py`

## Dijkstra Pathfinding

`GridMap.compute_paths()` calls `dijkstra()` with engine-specific callbacks:

- `is_walkable` checks tile movement mode;
- `cost_func` charges the destination tile's movement cost;
- `can_enter` delegates transition checks to `GridMap.can_transition()`;
- optional occupancy, subjective visibility, hazard avoidance, and remembered
  collision blockers are threaded into those callbacks.

Movement cost is paid on entry into each destination tile. A path:

```text
(0,0) -> (1,0) -> (2,0) -> (3,0) -> (4,0)
```

with `(2,0)` set to difficult terrain costs:

```text
1 + 2 + 1 + 1 = 5 cost units
```

Example EB-11-003:

```python
distances, paths = grid.compute_paths((0, 0), movement_mode=MovementMode.WALKING)
easy_distances, _ = grid.compute_paths(
    (0, 0),
    movement_mode=MovementMode.WALKING,
    ignore_difficult_terrain=True,
)

assert distances[(2, 0)] == 3
assert distances[(4, 0)] == 5
assert easy_distances[(4, 0)] == 4
```

Diagonal exact-range example EB-11-012:

```python
distances, paths = grid.compute_paths((0, 0), movement_mode=MovementMode.WALKING)
limited_distances, limited_paths = grid.compute_paths(
    (0, 0),
    max_distance=1,
    movement_mode=MovementMode.WALKING,
)

assert distances[(1, 1)] == 1
assert paths[(1, 1)] == [(0, 0), (1, 1)]
assert (1, 0) in limited_distances
assert (0, 1) in limited_distances
assert limited_distances[(1, 1)] == 1
assert limited_paths[(1, 1)] == [(0, 0), (1, 1)]
```

The diagonal step's returned movement cost is `1`, but Dijkstra adds a tiny
internal epsilon to diagonal moves for tie-breaking. The pruning check compares
against the public movement cost without epsilon, so an exact `max_distance=1`
admits cardinal neighbors and the one-cell diagonal neighbor consistently.

Diagonal bridge-route example EB-11-021:

```python
grid.set_tile_directional_border((0, 0), "movement", "east", False)

assert not grid.can_transition((0, 0), (1, 0))
assert grid.can_transition((0, 0), (0, 1))
assert grid.can_transition((0, 0), (1, 1))
assert one_bridge_paths[(1, 1)] == [(0, 0), (1, 1)]

grid.set_tile_directional_border((0, 0), "movement", "north", False)

assert not grid.can_transition((0, 0), (1, 1))
assert (1, 1) not in no_bridge_paths
```

A diagonal transition is allowed when at least one of the two cardinal bridge
routes is passable. In the example, blocking east still leaves the north-then-east
bridge available, so the diagonal neighbor remains reachable. Once both
east and north exits from the origin are blocked, neither bridge route exists
and the diagonal transition is excluded from pathfinding.

Negative-coordinate example EB-11-013:

```python
reset_grid_state(width=4, height=1, x=-2, y=0)

assert grid.bounds == (-2, 0, 1, 0)
assert grid.has_tile(-2, 0)
assert grid.can_transition((-2, 0), (-1, 0))

distances, paths = grid.compute_paths((-2, 0), movement_mode=MovementMode.WALKING)
edge_distances, edge_paths = grid.compute_paths((-1, 0), movement_mode=MovementMode.WALKING)

assert distances[(1, 0)] == 3
assert paths[(1, 0)] == [(-2, 0), (-1, 0), (0, 0), (1, 0)]
assert (0, 0) in edge_distances
assert edge_distances[(-2, 0)] == 1
assert edge_paths[(-2, 0)] == [(-1, 0), (-2, 0)]
```

`GridMap` stores negative positions and reports negative bounds, and
`compute_paths()` passes those bounds into the Dijkstra neighbor generator. Paths
can therefore move through negative coordinates in either direction as long as
tiles exist and transition checks allow the step.

Parity tests:

- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_003_dijkstra_paths_sum_tile_costs_and_can_ignore_difficult_terrain`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_012_diagonal_cost_return_and_exact_max_distance_match`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_021_diagonal_transitions_need_one_cardinal_bridge_route`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_013_negative_coordinate_tiles_are_reachable`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py`

## Move Action Cost Conversion

`Move` uses pathfinding output but pays action economy in feet. It walks the path
from index `1`, sums each destination tile's movement cost, and multiplies by
5 feet.

Example EB-11-004:

```python
move = Move(source_entity_uuid=entity.uuid, end_position=(4, 0))
event = move.apply()

movement_cost = next(cost.cost for cost in move.costs if cost.cost_type == "movement")
assert movement_cost == 25
assert entity.action_economy.movement.normalized_score == 5
```

Parity tests:

- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_004_move_action_converts_tile_cost_units_to_feet`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py`

## Occupants And Objects

`GridMap.is_walkable(x, y)` answers only whether the tile can be entered by the
movement mode. `GridMap.is_walkable_for(x, y, entity_uuid)` additionally checks
blocking entities and placed objects via polymorphic `BaseBlock` methods.

Entities block other entities unless the entity is the requester or is otherwise
non-blocking. Objects block when their `BaseItem.blocks_movement` or directional
blocker fields say they do.

Example EB-11-005:

```python
assert grid.is_walkable(1, 0)
assert not grid.is_walkable_for(1, 0, mover.uuid)
assert grid.identify_blocker_at((1, 0), mover.uuid) == blocker.name

grid.place_object(boulder.uuid, (2, 0))
assert not grid.is_walkable_for(2, 0, mover.uuid)
assert grid.identify_blocker_at((2, 0), mover.uuid) == "Boulder"
```

EB-11-011 records the corrected object re-placement invariant:

```python
grid.place_object(crate.uuid, (1, 0))
grid.place_object(crate.uuid, (2, 0))

assert grid.get_object_position(crate.uuid) == (2, 0)
assert crate.uuid not in grid.get_objects_at((1, 0))
assert crate.uuid in grid.get_objects_at((2, 0))
```

Primitive removal example EB-11-016:

```python
raw_item.place_on_grid((1, 0))
raw_tile_uuid = raw_item.tile_uuid

grid.remove_object(raw_item.uuid)

assert grid.get_object_position(raw_item.uuid) is None
assert raw_item.uuid not in observer.senses.objects
assert raw_item.tile_uuid is None
assert raw_item.get_position() is None
assert BaseBlock.get(raw_item.uuid) is raw_item

lifecycle_item.place_on_grid((2, 0))
lifecycle_item.destroy()

assert grid.get_object_position(lifecycle_item.uuid) is None
assert lifecycle_item.tile_uuid is None
assert BaseBlock.get(lifecycle_item.uuid) is None
```

`GridMap.remove_object()` is a primitive spatial operation. It removes the UUID
from grid indexes and emits spatial events, so observer senses drop the object.
For `BaseItem` floor objects, the grid removal also calls the block-level removal
hook so `tile_uuid` is cleared and `BaseItem.get_position()` no longer reports a
stale floor location. Raw grid removal still does not destroy the item or remove
it from the block registry; item lifecycle APIs such as `BaseItem.destroy()` own
registry cleanup, container cleanup, conditions, and attached light sources.

Dead-entity path example EB-11-015:

```python
assert blocker.blocks_walking(requesting_entity_uuid=mover.uuid) is True
assert not grid.is_walkable_for(2, 0, mover.uuid)
assert (2, 0) not in mover.senses.paths

blocker.receive_damage(blocker.get_hp() + 5, DamageType.BLUDGEONING, mover.uuid)

assert "Dead" in blocker.active_conditions
assert blocker.non_blocking is True
assert grid.is_walkable_for(2, 0, mover.uuid)
assert blocker.uuid not in mover.senses.entities
assert mover.senses._paths_dirty is True

mover.get_available_actions()

assert mover.senses.paths[(2, 0)] == [(0, 0), (1, 0), (2, 0)]
assert mover.senses.paths[(4, 0)] == [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]
```

The death handler applies `Dead`, marks the dead entity as `non_blocking`, and
the sensory callback removes the corpse from visible entities while marking
paths dirty. The next action discovery call recomputes paths and can route
through the corpse's still-occupied grid cell.

Parity tests:

- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_005_occupants_and_objects_block_walkable_tiles_polymorphically`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_015_dead_entities_become_non_blocking_for_paths`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_011_replacing_object_position_removes_old_grid_membership`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_016_raw_object_removal_clears_item_floor_location_state`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py`

## Directional Borders

Directional borders block crossings, not entire tiles. A tile can remain
walkable while its east side blocks movement. Transitions consult both endpoint
tiles, so either the source side or destination side can block a crossing.

Channels are independent:

- `movement`;
- `vision`;
- `light`;
- `propagation`.

Changing an intrinsic tile border emits `SPATIAL_TILE_CHANGED` with directional
metadata so observers can update only the affected senses.

Example EB-11-006:

```python
changed = grid.set_tile_directional_border((1, 0), "movement", "east", False)

assert changed is True
assert grid.is_walkable(1, 0)
assert not grid.can_transition((1, 0), (2, 0))
assert not grid.can_transition((2, 0), (1, 0))
assert event.directional_directions == ["east"]
assert event.directional_channels == ["movement"]
```

Example EB-11-007:

```python
screen = BaseItem(
    source_entity_uuid=uuid4(),
    name="Screen",
    is_pickable=False,
    blocks_vision_east=True,
    blocks_light_east=True,
    blocks_propagation_east=True,
)
grid.place_object(screen.uuid, (1, 1))

assert grid.can_transition((1, 1), (2, 1))
assert (2, 1) not in set(grid.compute_fov((1, 1), max_distance=3))
assert (2, 1) not in set(grid.compute_light_fov((1, 1), max_distance=3))
assert (2, 1) not in set(grid.compute_propagation_fov((1, 1), max_distance=3))
```

Forced movement and Jump example EB-11-017:

```python
wall = BaseItem(
    name="Directional Force Wall",
    blocks_movement_east=True,
    blocks_propagation_east=True,
    ...
)
grid.place_object(wall.uuid, (1, 1))

final_pos, distance, blocked, blocker_name = Shove.calculate_final_position(
    start=(1, 1),
    direction=(1, 0),
    distance_feet=10,
    target_uuid=actor.uuid,
)

assert final_pos == (1, 1)
assert distance == 0
assert blocked is True
assert blocker_name == "obstacle"
assert not grid.can_transition((1, 1), (2, 1), actor.uuid)

jump = Jump(source_entity_uuid=actor.uuid, template=True)
assert (3, 1) in actor.senses.visible
assert not grid.raycast_clear((1, 1), (3, 1), channel="propagation", observer_uuid=actor.uuid)
assert (3, 1) not in jump.get_valid_positions()
```

Forced movement walks candidate cells with `GridMap.can_transition()`, so a
movement-direction blocker on the source side stops the push before the target
leaves its current cell. Jump is LOS-targeted, so the destination can remain
visible, but the Jump target filter and validation still require a clear
physical-propagation ray. A source-side directional blocker currently reports a
generic `"obstacle"` blocker name because the destination cell itself is empty.

Parity tests:

- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_006_directional_borders_block_transitions_and_emit_metadata`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_007_directional_channels_are_independent`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_017_forced_movement_and_jump_respect_directional_blockers`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py`

## Hazards And Safe Paths

Hazards are conditions on tiles or objects with a `hazard_filter`.
`GridMap.is_position_hazardous_for()` checks tile conditions and placed-object
conditions. `compute_paths(..., walk_in_danger=False)` treats hazardous
positions as blocked for that entity.

Hidden hazards are only avoided if the entity can perceive them. That perception
edge belongs in deeper Chapter 12/terrain coverage; this chapter pins the basic
visible hazard behavior.

Example EB-11-008:

```python
hazard_tile.add_condition(
    BaseCondition(
        name="Burning Ground",
        hazard_filter=HazardFilter.ALL,
        ...
    )
)

normal_distances, normal_paths = grid.compute_paths(..., walk_in_danger=True)
safe_distances, safe_paths = grid.compute_paths(..., walk_in_danger=False)

assert normal_paths[(2, 0)] == [(0, 0), (1, 0), (2, 0)]
assert (1, 0) not in safe_paths[(2, 0)]
```

Because diagonal movement is allowed at cardinal cost in this engine, the safe
route can avoid the hazard without increasing returned movement cost in a small
grid. The important invariant here is path exclusion, not necessarily a larger
integer distance.

Hidden-hazard recomputation example EB-11-014:

```python
base_perception = observer.get_passive_perception()
hidden_trap = BaseCondition(
    name="Hidden Trap",
    hazard_filter=HazardFilter.ALL,
    condition_stealth_dc=base_perception + 5,
    ...
)
trap_tile.add_condition(hidden_trap)
Entity.update_all_entities_senses(max_distance=20)

assert (2, 1) in observer.senses.paths[destination]
assert not grid.is_position_hazardous_for(2, 1, observer.uuid)
assert observer.senses.safe_paths == {}

observer.add_condition(PerceptionBoost(..., boost_amount=10))

assert grid.is_position_hazardous_for(2, 1, observer.uuid)
assert observer.senses._paths_dirty is True
assert observer.senses.safe_paths == {}

observer.get_available_actions()

assert (2, 1) in observer.senses.paths[destination]
assert (2, 1) not in observer.senses.safe_paths[destination]
assert observer.senses._paths_dirty is False
```

Hidden hazards are checked against the observer's current passive perception.
When a perception-affecting condition changes that value, the sensory callback
marks paths dirty but does not immediately run Dijkstra. The next action
discovery call refreshes senses, computes the normal path that still crosses the
now-detected hazard, and computes a safe alternative that avoids it.

Parity tests:

- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_008_hazards_can_be_excluded_from_safe_paths`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_014_hidden_hazard_perception_change_recomputes_safe_paths`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py`

## Geometry And AoE

`dnd/core/geometry.py` functions are pure grid math. They do not know about
walls, entities, light, or the current map.

`dnd/core/aoe.py` wraps those geometry sets in `AoEShape` classes that consult
`GridMap`:

- `Sphere`, `Cone`, `Line`, and `Cube` use propagation FOV for objective
  execution;
- `Cylinder` ignores lateral barriers in this 2D abstraction and affects its
  full geometric circle;
- all shapes gather entity UUIDs from `GridMap.get_entities_at()`.

Example EB-11-009:

```python
assert circle_positions((1, 1), radius=1) == {
    (1, 1), (0, 1), (2, 1), (1, 0), (1, 2)
}

sphere = Sphere(source_entity_uuid=caster.uuid, target=(1, 1), radius_feet=15)
sphere.compute_objective(caster.position)
cylinder = Cylinder(source_entity_uuid=caster.uuid, target=(1, 1), radius_feet=15)
cylinder.compute_objective(caster.position)

assert target.uuid not in sphere.affected_entity_uuids
assert target.uuid in cylinder.affected_entity_uuids
```

Example EB-11-018 proves generic zone construction uses the same directional
geometry as direct AoE construction:

```python
direct_cone = Cone(source_entity_uuid=source_uuid, target=(8, 2), length_feet=30)
direct_cone.compute_objective(caster_pos=(2, 2))
direct_line = Line(source_entity_uuid=source_uuid, target=(8, 2), length_feet=30)
direct_line.compute_objective(caster_pos=(2, 2))

generic_cone_zone = ZoneControlCondition(
    zone_shape="cone",
    zone_center=(2, 2),
    zone_radius_feet=30,
    zone_direction=(1, 0),
    ...
)

assert (5, 2) in direct_cone.affected_positions
assert (8, 2) in direct_line.affected_positions
assert generic_cone_zone._compute_affected_positions() == direct_cone.affected_positions
assert generic_line_zone._compute_affected_positions() == direct_line.affected_positions
```

Direct `Cone` and `Line` shapes use the caster position as the origin and the
`target` point as the direction anchor, so they expand east in the example
above. The generic `ZoneControlCondition._compute_affected_positions()` path
converts `zone_direction` into a target point relative to `zone_center`, passes
`zone_radius_feet` as the cone/line length, and passes `zone_width_feet` to line
zones. Directional zones can still override `_compute_affected_positions()` for
spell-specific geometry, but the base path no longer collapses cone and line
zones to the origin.

Example EB-11-019 documents cylinder preview parity:

```python
subjective = Cylinder(source_entity_uuid=caster.uuid, target=(1, 1), radius_feet=15)
subjective.compute_subjective(caster.position, caster.senses, ...)

targeting = Cylinder(source_entity_uuid=caster.uuid, target=(1, 1), radius_feet=15)
targeting.compute_for_targeting(caster.position, caster.senses, ...)

objective = Cylinder(source_entity_uuid=caster.uuid, target=(1, 1), radius_feet=15)
objective.compute_objective(caster.position)

assert (3, 1) in subjective.affected_positions
assert (3, 1) in targeting.affected_positions
assert (3, 1) in objective.affected_positions
assert subjective.affected_positions == targeting.affected_positions
assert subjective.affected_positions == objective.affected_positions
```

`Cylinder.compute_subjective()`, `compute_for_targeting()`, and
`compute_objective()` all use the full geometric circle because a cylinder
descends vertically in this 2D model. Subjective preview and targeting still
filter affected entity UUIDs through the caster's perceived entities; they show
the full footprint but do not reveal a creature the caster cannot see. Objective
execution includes all entities in the footprint.

Example EB-11-020 covers zone cleanup across the spatial, terrain, and marker
layers:

```python
zone = EntryCleanupZone(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=caster.uuid,
    zone_center=(2, 1),
)
caster.add_condition(zone)

assert center_tile.get_movement_cost(MovementMode.WALKING) == 2
assert len(zone.spatial_handler_uuids) == 1
assert "Entry Cleanup Marker" in center_tile.active_conditions
assert EventQueue.get_spatial_handlers_at((2, 1))

caster.remove_condition(zone.name)

assert center_tile.get_movement_cost(MovementMode.WALKING) == 1
assert zone.spatial_handler_uuids == []
assert "Entry Cleanup Marker" not in center_tile.active_conditions
assert EventQueue.get_spatial_handlers_at((2, 1)) == []
```

`ZoneControlCondition._apply()` computes the affected positions, registers
position-indexed entry/exit handlers, applies terrain modifiers to tile
`walking_cost`, applies light modifiers when configured, and adds optional
`ZoneMarkerCondition` children to affected tiles. Cleanup runs through
`BaseBlock.remove_condition()` and `BaseCondition.cleanup_own_state()`: linked
tile marker conditions are removed, terrain modifiers are removed from their
values, and `EventQueue.remove_spatial_handler()` removes the handler from every
indexed position and the reverse position registry.

Parity tests:

- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_009_geometry_and_aoe_are_grid_aware_where_needed`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_018_zone_control_cone_and_line_use_directional_geometry`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_019_cylinder_subjective_preview_matches_targeting_footprint`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::test_eb_11_020_zone_removal_cleans_spatial_handlers_terrain_and_markers`
- `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py`

## Findings And Follow-Up Coverage

The chapter tests now cover tile identity, movement costs, terrain-cost
pathfinding, diagonal bridge-route pruning, move-cost conversion, occupancy/object blocking, directional
channels, hazards, hidden-hazard safe-path recomputation, dead-entity
non-blocking path recomputation, primitive object-removal location cleanup,
grid-aware AoE, directional zone construction, cylinder preview/execution
differences, and zone cleanup across spatial handlers, terrain modifiers, and
tile markers.

## Documentation Hygiene Notes

- Chapter 11 hygiene reviewed `dnd/core/base_tiles.py`, `dnd/core/gridmap.py`, `dnd/core/geometry.py`, `dnd/core/aoe.py`, `dnd/core/shadowcast.py`, and `dnd/tile_conditions.py` from executable behavior and parity tests rather than trusting comments.
- The cleaned scope covers tile movement/light/border fields, grid tile/entity/object indexes, Dijkstra/FOV/AoE helper contracts, light-source batching, directional propagation, directional environment object metadata, and zone-control terrain/marker/spatial-handler cleanup.
- Inline narrative comments and section banners were removed from the cleaned Chapter 11 files; non-obvious behavior was moved into Google-style docstrings and Pydantic field descriptions.
- Known behavior was preserved: diagonal exact-distance pruning and zone cleanup contracts remain as documented above.
- `GridMap` directional metadata now uses a dynamic metadata-bag type so pyright can validate event-factory calls without changing runtime payloads.
