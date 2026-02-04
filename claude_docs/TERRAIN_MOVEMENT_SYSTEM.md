# Terrain and Movement System

## Overview

This document describes the terrain movement cost system, zone spell conditions, and tile entry/exit handlers.

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

### Tile Borders

Each tile has 4 borders controlling directional entry:
- `border_north`, `border_south`, `border_east`, `border_west` (bool, default True)
- `can_enter_from(from_position)` method checks if entry is allowed

Use cases: one-way ledges, doors, trapdoors.

### Tile Height

`height: int` field for elevation (0 = ground, +N = elevated, -N = below).

### Movement Modes

Entities have available modes and per-mode speeds in ActionEconomy:
- `MovementMode` enum: WALKING, FLYING, SWIMMING, BURROWING
- Per-mode speeds: `walking_speed`, `flying_speed`, etc.

### Zone Spell Pattern

```
Caster: Concentrating(spell_name="Fog Cloud")
    |
    +-- external_conditions -> FogCloudZone (on caster)
            |
            +-- terrain_conditions -> FogCloudTileEffect (on each tile)
```

When concentration breaks, the chain cleans up automatically.

### BaseCondition.terrain_conditions

New field tracking conditions placed on tiles:
```python
terrain_conditions: List[Tuple[UUID, UUID]]  # (tile_uuid, condition_uuid)
```

Methods:
- `add_terrain_condition(tile_uuid, condition_uuid)`
- `remove_terrain_conditions()` - called in remove()

## Implementation Status

- [x] Plan document
- [ ] Tile movement costs (ModifiableValues)
- [ ] Tile borders
- [ ] Dijkstra cost_func parameter
- [ ] GridMap terrain-aware pathfinding
- [ ] BaseCondition.terrain_conditions
- [ ] ZoneControlCondition base class
- [ ] TileEffectCondition base class
- [ ] Test file
