# Terrain and Movement System

## Overview

This document describes the terrain movement cost system, zone spell conditions, tile entry/exit handlers, and the spatial event lifecycle.

## Implementation Status

### Core Infrastructure (Complete)

- [x] Tile movement costs (ModifiableValues) - `dnd/core/base_tiles.py`
- [x] Tile borders (directional walkability) - orthogonal and diagonal
- [x] Tile height field (exists but **unused** - no code reads it)
- [x] Dijkstra cost_func and can_enter parameters - `dnd/core/dijkstra.py`
- [x] GridMap terrain-aware pathfinding - `dnd/core/gridmap.py`
- [x] GridMap tile UUID lookup
- [x] BaseCondition.terrain_conditions - `dnd/core/base_conditions.py`
- [x] ZoneControlCondition base class - `dnd/tile_conditions.py`
- [x] TileEffectCondition base class - `dnd/tile_conditions.py`
- [x] Cell-by-cell movement events - `dnd/actions.py` (StepMovementEvent per cell)
- [x] Move action terrain cost integration - `dnd/actions.py`
- [x] **Spatial Event Lifecycle Fix (P0)** - Events now progress through all 4 phases
- [x] **EventHandler-based entry damage** - No more callbacks needed

### Tested Features (Verified in `test_terrain_movement_system.py`)

- [x] Flying movement mode (ignores difficult terrain, blocked by walls)
- [x] Swimming movement mode (works in water, blocked on land)
- [x] Diagonal tile borders
- [x] TileEffectCondition (difficult terrain, entry damage, turn start damage)
- [x] ZoneControlCondition (zone creation, cleanup, movement)
- [x] Zone + Concentration integration
- [x] Multi-step movement damage (entry damage per tile)

### Not Yet Implemented

- [ ] Movement modes on entities (fly speed, swim speed) - entities assume WALKING
- [ ] Light system (connect obscurement fields to FOV)
- [ ] Cover calculation
- [ ] Save-based entry effects (Web, Grease)
- [ ] Per-5ft-movement damage (Spike Growth)
- [ ] Turn-end handlers (Grease)
- [ ] Escape action grants (Web)

---

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

**Diagonal handling**: For diagonal movement (e.g., NE), the tile checks BOTH relevant borders. Entry is blocked only if BOTH borders are closed.

Use cases: one-way ledges, doors, trapdoors.

### Movement Modes

`MovementMode` enum in `dnd/core/base_tiles.py`:
- `WALKING` - Standard ground movement
- `FLYING` - Aerial movement (ignores difficult terrain, blocked by walls)
- `SWIMMING` - Water movement (only works on water tiles)
- `BURROWING` - Underground movement

### Pathfinding Integration

`GridMap.compute_paths()` accepts:
- `movement_mode: MovementMode = MovementMode.WALKING`

The pathfinding automatically:
1. Uses mode-specific tile costs via `tile.get_movement_cost(mode)`
2. Checks tile borders via `tile.can_enter_from(from_pos)`
3. Returns distances in movement cost units (not grid squares)

---

## Spatial Event Lifecycle (P0 Complete)

### The Fix

Previously, spatial events fired only at COMPLETION phase, which meant EventHandlers couldn't react to them (EventQueue.register() skips handlers at COMPLETION). Entry damage had to use a callback workaround.

**Now**: Spatial events progress through all 4 phases like other events:
```
DECLARATION → EXECUTION → EFFECT → COMPLETION
```

### Changes Made

| Component | Change | File |
|-----------|--------|------|
| SpatialChangeEvent factories | Changed `phase=COMPLETION` → `phase=DECLARATION` + `use_register=False` | `dnd/core/events.py:1020-1075` |
| GridMap._fire_spatial_event() | Now progresses through all 4 phases | `dnd/core/gridmap.py:86-121` |
| GridMap.enable_events() | Fires pending events through full lifecycle | `dnd/core/gridmap.py:123-130` |
| TileEntryDamageCallback | DELETED - replaced with EventHandler | `dnd/tile_conditions.py` |
| TileEffectCondition._apply() | Uses EventHandler for entry damage at EFFECT phase | `dnd/tile_conditions.py:72-112` |

### Event Flow for Entity Movement

When `GridMap.move_entity(uuid, new_position)` is called:

```
1. SPATIAL_ENTITY_LEFT event fires (4 phases)
   - DECLARATION: Handlers can see entity leaving
   - EXECUTION: Handlers can process
   - EFFECT: Effects like opportunity attacks could trigger
   - COMPLETION: SpatialSensesCallback updates observers

2. Position update happens in GridMap

3. SPATIAL_ENTITY_ENTERED event fires (4 phases)
   - DECLARATION: Handlers can see entity entering
   - EXECUTION: Handlers can process
   - EFFECT: Entry damage, saves, conditions apply HERE
   - COMPLETION: SpatialSensesCallback updates observers
```

### EventHandler for Entry Damage

```python
# In TileEffectCondition._create_entry_damage_handler():
return EventHandler(
    name=f"{self.name} Entry Damage",
    source_entity_uuid=tile_uuid,
    trigger_conditions=[Trigger(
        event_type=EventType.SPATIAL_ENTITY_ENTERED,
        event_phase=EventPhase.EFFECT  # Fires at EFFECT, not COMPLETION
    )],
    event_processor=entry_damage_processor
)
```

### Design Choices vs Original Plan

| Original Plan | Actual Implementation | Reason |
|---------------|----------------------|--------|
| `move_entity()` returns bool for cancellation | Not implemented | Position updates happen after events fire; cancellation needs more refactoring |
| `register_entity()` checks cancelled | Not implemented | Same reason - deferred to future if needed |

**Key Insight**: The goal was to enable EventHandlers to react at EFFECT phase. That's achieved. Movement cancellation is a separate feature.

---

## Associated Components

### GridMap System

**File**: `dnd/core/gridmap.py`

Key methods:
- `move_entity(uuid, position)` - Fires LEFT then ENTERED events with full lifecycle
- `register_entity(uuid, position)` - Fires ENTERED event
- `unregister_entity(uuid)` - Fires LEFT event
- `_fire_spatial_event(event)` - Progresses through all 4 phases
- `compute_paths(start, mode)` - Terrain-aware Dijkstra
- `get_tile_by_uuid(uuid)` - Lookup for handlers
- `enable_events() / disable_events()` - Batch operations

### Spatial Events

**File**: `dnd/core/events.py`

| Event Type | Factory Method | Purpose |
|------------|----------------|---------|
| `SPATIAL_ENTITY_ENTERED` | `SpatialChangeEvent.entity_entered()` | Entity moved into a cell |
| `SPATIAL_ENTITY_LEFT` | `SpatialChangeEvent.entity_left()` | Entity moved out of a cell |
| `SPATIAL_TILE_CHANGED` | `SpatialChangeEvent.tile_changed()` | Tile properties changed |

All factory methods create events at DECLARATION phase with `use_register=False` so GridMap controls the full lifecycle.

### Move Action Integration

**File**: `dnd/actions.py`

The Move action integrates with terrain:
1. Uses `GridMap.compute_paths()` for terrain-aware costs
2. Fires `StepMovementEvent` for each cell in path (cell-by-cell movement)
3. Each step triggers `GridMap.move_entity()` → spatial events → entry damage handlers fire per step

### SpatialSensesCallback (Unchanged)

**File**: `dnd/blocks/sensory.py`

- Fires at COMPLETION phase via `EventQueue._on_event_callbacks`
- Updates entity's `senses.entities` dict when visible entities move
- This is correct use of callbacks - passive observation, no modification of events

---

## Zone Spell Pattern

### Hierarchy

```
Caster: Concentrating(spell_name="Fog Cloud")
    │
    └── external_conditions ──► FogCloudZone (on caster)
                                    │
                                    └── terrain_conditions ──► FogCloudTileEffect (on each tile)
```

### Automatic Cleanup

When concentration breaks, the chain cleans up automatically:
1. `Concentrating.remove()` calls `remove_external_conditions()`
2. `FogCloudZone.remove()` calls `remove_terrain_conditions()`
3. Each `FogCloudTileEffect` is removed from its tile
4. Tile costs return to normal

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
- `heavily_obscured: bool` - Blocks vision (NOT CONNECTED TO FOV YET)
- `lightly_obscured: bool` - Light obscurement (NOT CONNECTED TO FOV YET)
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

---

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
from dnd.tile_conditions import ZoneControlCondition, TileEffectCondition
from dnd.conditions import Concentrating
from typing import Type

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

    def get_tile_effect_class(self) -> Type[TileEffectCondition]:
        return WebTileEffect

# In spell's _apply method:
# 1. Create and apply zone to caster
zone = WebZone(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=caster.uuid,
    zone_center=(5, 5)
)
caster.add_condition(zone)

# 2. Create and apply concentration
concentration = Concentrating(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=caster.uuid,
    spell_name="Web"
)
caster.add_condition(concentration)

# 3. Link zone as external condition (automatic cleanup on concentration break)
concentration.add_external_condition(caster.uuid, zone.uuid)
```

### Entry Damage Tile Effect

```python
from dnd.tile_conditions import TileEffectCondition
from dnd.core.modifiers import DamageType

class FireTileEffect(TileEffectCondition):
    name: str = "Fire"
    description: str = "Burns entities that enter"
    damage_on_entry_dice: str = "2d4"
    damage_on_entry_type: DamageType = DamageType.FIRE

# Apply to a tile
tile = grid.get_tile(5, 5)
effect = FireTileEffect(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=tile.uuid
)
tile.add_condition(effect)

# When entity enters tile (5,5), handler fires at EFFECT phase
# Entity takes 2d4 fire damage automatically
```

---

## Test Coverage

### Test File: `examples/test_terrain_movement_system.py`

All tests passing.

#### Group 1: Movement Mode Pathfinding

| Test | Status | Description |
|------|--------|-------------|
| `test_flying_pathfinding_ignores_difficult_terrain` | PASS | Flying cost=4, walking cost=5 through difficult terrain |
| `test_flying_pathfinding_blocked_by_walls` | PASS | wall_factory sets flying_cost=0 |
| `test_swimming_pathfinding_through_water` | PASS | water_factory allows swimming (cost=1) |
| `test_swimming_blocked_on_land` | PASS | Floor has swimming_cost=0 |
| `test_walking_blocked_by_water` | PASS | Cannot walk through water |
| `test_mixed_terrain_path_cost` | PASS | floor-floor-difficult-floor = cost 4 |

#### Group 2: Diagonal Borders

| Test | Status | Description |
|------|--------|-------------|
| `test_diagonal_border_northeast_blocked` | PASS | Both N+E borders closed blocks NE entry |
| `test_diagonal_border_partial_allows` | PASS | Only N closed, E open allows NE entry |
| `test_orthogonal_borders_dont_affect_diagonal` | PASS | N border doesn't affect SW diagonal |

#### Group 3: TileEffectCondition

| Test | Status | Description |
|------|--------|-------------|
| `test_tile_effect_adds_difficult_terrain` | PASS | adds_difficult_terrain=True → cost 2 |
| `test_tile_effect_entry_damage` | PASS | Entry damage fires on SPATIAL_ENTITY_ENTERED |
| `test_tile_effect_turn_start_damage` | PASS | Turn start damage fires on TURN_START |
| `test_tile_effect_cleanup_on_removal` | PASS | Removing condition removes modifiers |

#### Group 4: ZoneControlCondition

| Test | Status | Description |
|------|--------|-------------|
| `test_zone_control_computes_affected_positions` | PASS | AoE shapes compute correctly |
| `test_zone_control_applies_tile_effects` | PASS | Effects applied to all tiles |
| `test_zone_control_cleanup_removes_all_effects` | PASS | Zone removal cleans up all tiles |
| `test_zone_move_updates_affected_tiles` | PASS | move_zone() removes old, applies new |

#### Group 5: Zone + Concentration

| Test | Status | Description |
|------|--------|-------------|
| `test_concentration_break_removes_zone` | PASS | external_conditions cleanup works |

#### Group 6: Multi-Step Movement

| Test | Status | Description |
|------|--------|-------------|
| `test_entry_damage_on_each_step` | PASS | 3 fire tiles = 3 damage events |

---

## Future Work

### Priority 1: Extended TileEffectCondition Features

Based on SRD spells, the infrastructure needs more than basic entry damage:

#### 1a. Per-Movement Damage (Spike Growth)

Spike Growth deals 2d4 per **5 feet traveled**, not per entry. Need:

```python
# New fields
damage_per_5ft_dice: Optional[str] = None  # "2d4"
damage_per_5ft_type: DamageType = DamageType.PIERCING
```

Implementation: Use `StepMovementEvent` instead of `SPATIAL_ENTITY_ENTERED`.

#### 1b. Turn-End Handler (Grease)

Grease triggers save on **ending turn** in the area.

```python
# New fields
save_on_turn_end_ability: Optional[str] = None
save_on_turn_end_dc: Optional[int] = None
condition_on_turn_end_failed_save: Optional[str] = None  # "Prone"
```

Implementation: Add `_create_turn_end_handler()` listening for `TURN_END`.

#### 1c. Save + Condition on Entry/Turn Start (Web, Grease)

```python
# New fields
save_on_entry_ability: Optional[str] = None  # "dexterity"
save_on_entry_dc: Optional[int] = None
condition_on_entry_failed_save: Optional[str] = None  # "Restrained"
```

#### 1d. Escape Action Grant (Web)

Web-restrained creatures can use action to escape. Need "Break Free" action template.

### Priority 2: Zone Spell Implementations

| Spell | Level | Key Features | Infrastructure Needed |
|-------|-------|--------------|----------------------|
| **Spike Growth** | 2nd | 2d4 per 5ft traveled, no save | Per-5ft-movement damage |
| **Grease** | 1st | DEX save → Prone on entry/turn end | Turn-end handler, Prone |
| **Web** | 2nd | DEX save → Restrained, escape action | Restrained, action grant |

**Skipped** (needs vision/light system):
- Fog Cloud - Needs obscurement affecting FOV
- Darkness - Needs light system

**Deferred** (movement-following zones):
- Spirit Guardians - Zone moves with caster
- Cloudkill - Moving zone

### Priority 3: Vision/Light System (Deferred)

Requires significant refactoring:
- Connect `heavily_obscured` / `lightly_obscured` to FOV calculations
- Light source system
- Darkvision, Blindsight, etc.

---

## Related Documentation

- `CLAUDE.md` - Main codebase guide
- `IMPLEMENTATION_GUIDE.md` - How to implement conditions and event handlers
- `AOE_TARGETING_REFERENCE.md` - AoE shape calculations
- `TERRAIN_AND_3D_PLAN.md` - Original terrain planning document (historical)
