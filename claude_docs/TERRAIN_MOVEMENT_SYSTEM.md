# Terrain and Movement System

## Overview

This document describes the terrain movement cost system, zone spell conditions, and tile entry/exit handlers.

## Implementation Status

- [x] Plan document
- [x] Tile movement costs (ModifiableValues) - `dnd/core/base_tiles.py`
- [x] Tile borders (directional walkability)
- [x] Tile height field
- [x] Dijkstra cost_func and can_enter parameters - `dnd/core/dijkstra.py`
- [x] GridMap terrain-aware pathfinding - `dnd/core/gridmap.py`
- [x] GridMap tile UUID lookup
- [x] BaseCondition.terrain_conditions - `dnd/core/base_conditions.py`
- [x] ZoneControlCondition base class - `dnd/core/tile_conditions.py`
- [x] TileEffectCondition base class - `dnd/core/tile_conditions.py`
- [x] Test file - `examples/test_difficult_terrain.py`

## Architecture

### Tile Movement Costs

Each tile has per-mode movement costs as ModifiableValues:
- `walking_cost` - Default 1 for floor, max=0 for wall/water
- `flying_cost` - Default 1 for air, max=0 for solid ceiling
- `swimming_cost` - Default max=0 (no water), 1 for water
- `burrowing_cost` - Default max=0 (no earth), 1 for earth

Cost values:
- `1` = normal movement
- `2` = difficult terrain
- `0` (via max_constraint) = impassable

### Tile Factories

| Factory | Walking | Flying | Swimming | Burrowing |
|---------|---------|--------|----------|-----------|
| `floor_factory` | 1 | 1 | 0 | 0 |
| `wall_factory` | 0 | 0 | 0 | 0 |
| `water_factory` | 0 | 1 | 1 | 0 |
| `difficult_terrain_factory` | 2 | 1 | 0 | 0 |

### Tile Borders

Each tile has 4 borders controlling directional entry:
- `border_north`, `border_south`, `border_east`, `border_west` (bool, default True)
- `can_enter_from(from_position)` method checks if entry is allowed

Use cases: one-way ledges, doors, trapdoors.

### Tile Height

`height: int` field for elevation (0 = ground, +N = elevated, -N = below).

### Movement Modes

`MovementMode` enum in `dnd/core/base_tiles.py`:
- `WALKING` - Standard ground movement
- `FLYING` - Aerial movement
- `SWIMMING` - Water movement
- `BURROWING` - Underground movement

### Pathfinding Integration

`GridMap.compute_paths()` now accepts:
- `movement_mode: MovementMode = MovementMode.WALKING`

The pathfinding automatically:
1. Uses mode-specific tile costs via `tile.get_movement_cost(mode)`
2. Checks tile borders via `tile.can_enter_from(from_pos)`
3. Returns distances in movement cost units (not grid squares)

### Zone Spell Pattern

```
Caster: Concentrating(spell_name="Fog Cloud")
    |
    +-- external_conditions -> FogCloudZone (on caster)
            |
            +-- terrain_conditions -> FogCloudTileEffect (on each tile)
```

When concentration breaks, the chain cleans up automatically via:
1. `Concentrating.remove()` calls `remove_external_conditions()`
2. `FogCloudZone.remove()` calls `remove_terrain_conditions()`
3. Each `FogCloudTileEffect` is removed from its tile

### BaseCondition.terrain_conditions

New field tracking conditions placed on tiles:
```python
terrain_conditions: List[Tuple[UUID, UUID]]  # (tile_uuid, condition_uuid)
```

Methods:
- `add_terrain_condition(tile_uuid, condition_uuid)` - Track a tile condition
- `remove_terrain_conditions()` - Remove all tracked tile conditions (called in `remove()`)

### TileEffectCondition Base Class

Base condition for effects applied to tiles. Features:
- `adds_difficult_terrain: bool` - If True, adds +1 to walking cost
- `heavily_obscured: bool` - Blocks vision
- `lightly_obscured: bool` - Provides light obscurement
- `damage_on_entry_dice: str` - E.g., "2d4" for entry damage
- `damage_on_entry_type: DamageType` - Damage type
- `damage_on_turn_start_dice: str` - Damage at turn start
- `damage_on_turn_start_type: DamageType`

### ZoneControlCondition Base Class

Base condition for controlling a zone of tile effects. Features:
- `zone_center: Tuple[int, int]` - Center position
- `zone_shape: str` - "sphere", "cone", "line", "cube"
- `zone_radius_feet: int` - Radius in feet
- `zone_direction: Optional[Tuple[int, int]]` - For cones/lines

Methods:
- `get_tile_effect_class()` - Override to return specific TileEffectCondition subclass
- `_compute_affected_positions()` - Uses AoE shapes to compute affected tiles
- `move_zone(new_center)` - Move the zone to a new position

## Usage Examples

### Creating Difficult Terrain

```python
from dnd.core.base_tiles import difficult_terrain_factory
from dnd.core.gridmap import get_map

# Create a difficult terrain tile
tile = difficult_terrain_factory((5, 5))
grid = get_map()
grid._tiles[(5, 5)] = tile
grid._tiles_by_uuid[tile.uuid] = (5, 5)

# Or add difficult terrain modifier to existing tile
from dnd.core.modifiers import NumericalModifier
tile = grid.get_tile(3, 3)
tile.walking_cost.self_static.add_value_modifier(
    NumericalModifier.create(
        source_entity_uuid=tile.uuid,
        name="Web Difficult Terrain",
        value=1
    )
)
```

### Pathfinding with Movement Mode

```python
from dnd.core.gridmap import get_map
from dnd.core.base_tiles import MovementMode

grid = get_map()

# Walking pathfinding (accounts for difficult terrain)
distances, paths = grid.compute_paths((0, 0), movement_mode=MovementMode.WALKING)

# Flying pathfinding (ignores ground-based difficult terrain)
distances, paths = grid.compute_paths((0, 0), movement_mode=MovementMode.FLYING)
```

### Creating a Zone Spell Effect

```python
from dnd.core.tile_conditions import ZoneControlCondition, TileEffectCondition

# Define the tile effect
class WebTileEffect(TileEffectCondition):
    name: str = "Web"
    adds_difficult_terrain: bool = True
    # Could add: restrained on entry via handler

# Define the zone control
class WebZone(ZoneControlCondition):
    name: str = "Web Zone"
    zone_shape: str = "cube"
    zone_radius_feet: int = 20

    def get_tile_effect_class(self):
        return WebTileEffect

# Apply to caster (in spell's _apply method)
zone = WebZone(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=caster.uuid,
    zone_center=(5, 5)
)
caster.add_condition(zone)
```

## Future Work

- [ ] Movement modes on entities (fly speed, swim speed)
- [ ] Cell-by-cell movement (for terrain damage triggers)
- [ ] Light system (obscurement affects FOV)
- [ ] Cover calculation
- [ ] Specific zone spells (Fog Cloud, Web, Wall of Fire, etc.)
