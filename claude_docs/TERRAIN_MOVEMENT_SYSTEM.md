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
- [x] **Position-indexed spatial handlers** - O(1) handler lookup via `EventQueue.add_spatial_handler()`
- [x] **Prone auto-stand (BG3 style)** - `dnd/conditions.py:632`
- [x] **HazardFilter enum** - `dnd/core/base_conditions.py` (ALL, ENEMIES, NON_SOURCE)
- [x] **condition_stealth_dc** - Perception-gated hazard detection
- [x] **is_hazardous_for()** - Entity-subjective hazard checks on BaseBlock/GridMap
- [x] **Safe pathfinding** - Two-pass Dijkstra with `walk_in_danger=False`
- [x] **SpikeTrapCondition / ZoneMarkerCondition** - Lightweight tile hazard markers
- [x] **prefer_safe on Move** - Auto-safe movement with safe_paths fallback

### Zone Spells (Complete)

| Spell | Level | File | Key Features |
|-------|-------|------|--------------|
| **Spike Growth** | 2nd | `dnd/spells/transmutation.py` | 2d4 piercing on entry, difficult terrain |
| **Grease** | 1st | `dnd/spells/conjuration.py` | DEX save → Prone, difficult terrain, turn start saves |
| **Web** | 2nd | `dnd/spells/conjuration.py` | DEX save → Restrained, escape action (STR check), difficult terrain |
| **Cloudkill** | 5th | `dnd/spells/conjuration.py` | CON save → 5d8 poison (half on save), auto-moves 10ft from caster |
| **Spirit Guardians** | 3rd | `dnd/spells/conjuration.py` | WIS save → 3d8 radiant (half on save), follows caster, speed halved for enemies |

### Tested Features

**Core System** (Verified in `test_terrain_movement_system.py`):
- [x] Flying movement mode (ignores difficult terrain, blocked by walls)
- [x] Swimming movement mode (works in water, blocked on land)
- [x] Diagonal tile borders
- [x] TileEffectCondition (difficult terrain, entry damage, turn start damage)
- [x] ZoneControlCondition (zone creation, cleanup, movement)
- [x] Zone + Concentration integration
- [x] Multi-step movement damage (entry damage per tile)

**Zone Spells** (Individual test files):
- [x] `test_prone_auto_stand.py` - BG3-style Prone behavior (5 tests)
- [x] `test_spike_growth.py` - Entry damage + difficult terrain (4 tests)
- [x] `test_grease.py` - DEX save → Prone, turn start + entry (6 tests)
- [x] `test_web.py` - DEX save → Restrained, escape action (5 tests)
- [x] `test_cloudkill.py` - CON save + auto-move zone (6 tests)
- [x] `test_spirit_guardians.py` - WIS save + follow caster + speed halving (9 tests)

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

### New Architecture: Position-Indexed Spatial Handlers

**Key insight**: Instead of one handler per tile (O(tiles)), zones now use **one handler per effect type** registered for all positions in the zone. Handler lookup is O(1) via position-indexed map.

```
Caster: Concentrating(spell_name="Web")
    │
    └── external_conditions ──► WebZone (ZoneControlCondition on caster)
                                    │
                                    ├── _entry_handler_uuid  (ONE handler for all positions)
                                    ├── _exit_handler_uuid   (ONE handler for all positions)
                                    ├── _turn_start_handler_uuid (regular event handler)
                                    └── _terrain_modifier_uuids  (modifiers on tile.walking_cost)
```

### Handler Registration

```python
# In ZoneControlCondition._apply():
# Create entry handler (fires for ANY position in the zone)
handler = self._create_zone_entry_handler()
EventQueue.add_spatial_handler(
    handler,
    self.affected_positions,           # Set of (x, y) positions
    EventType.SPATIAL_ENTITY_ENTERED,
    EventPhase.EFFECT
)
self._entry_handler_uuid = handler.uuid
```

### Zone Movement (O(delta))

When zone moves, only the difference is updated:

```python
def move_zone(self, new_center: Tuple[int, int]) -> bool:
    # Remove old terrain modifiers
    self._remove_terrain_modifiers()

    # Compute new positions
    self.zone_center = new_center
    new_positions = self._compute_affected_positions()

    # Efficient batch update (only changes delta positions)
    EventQueue.update_spatial_handler_positions(
        self._entry_handler_uuid,
        new_positions,
        EventType.SPATIAL_ENTITY_ENTERED,
        EventPhase.EFFECT
    )

    self.affected_positions = new_positions
    self._apply_terrain_modifiers()
    return True
```

### Automatic Cleanup

When concentration breaks:
1. `Concentrating.remove()` calls `remove_external_conditions()`
2. `WebZone._remove()` removes spatial handlers via `EventQueue.remove_spatial_handler()`
3. `WebZone._remove()` removes terrain modifiers from tiles
4. Standard event handler cleanup via parent class

### TileEffectCondition Base Class

Base condition for effects applied to tiles. Features:
- `adds_difficult_terrain: bool` - If True, adds +1 to walking cost
- `heavily_obscured: bool` - Blocks vision (see `VISION_HIDING_COVER_PLAN.md` for integration plan)
- `lightly_obscured: bool` - Light obscurement (see `VISION_HIDING_COVER_PLAN.md` for integration plan)

**Note**: Entry damage and turn start damage are now handled via ZoneControlCondition's spatial handlers, not TileEffectCondition fields.

### ZoneControlCondition Base Class

Base condition for controlling a zone of effects. **Primary pattern for zone spells**.

**Fields**:
- `zone_center: Tuple[int, int]` - Center position
- `zone_shape: str` - "sphere", "cone", "line", "cube"
- `zone_radius_feet: int` - Radius in feet
- `zone_direction: Optional[Tuple[int, int]]` - For cones/lines
- `adds_difficult_terrain: bool` - If True, adds +1 to walking cost
- `affected_positions: Set[Tuple[int, int]]` - Computed tile positions

**Override Points**:
```python
def _has_entry_effect(self) -> bool: ...     # Return True if entry triggers effect
def _has_exit_effect(self) -> bool: ...      # Return True if exit triggers effect
def _has_turn_start_effect(self) -> bool: ... # Return True if turn start triggers effect

def _create_zone_entry_handler(self) -> EventHandler: ...
def _create_zone_exit_handler(self) -> EventHandler: ...
def _create_zone_turn_start_handler(self) -> EventHandler: ...
```

**Methods**:
- `_compute_affected_positions()` - Uses AoE shapes to compute affected tiles
- `move_zone(new_center)` - Move the zone to a new position (efficient O(delta))

---

## Prone Auto-Stand (BG3 Style)

Prone has been updated to match Baldur's Gate 3 behavior - automatic standing with movement cost, no manual "Stand Up" action needed.

### Behavior Rules

| Situation | Result |
|-----------|--------|
| **Turn start while Prone** | Auto-stand, consume half base movement (e.g., 15ft for 30ft speed) |
| **Knocked Prone during own turn with movement** | Immediately stand, consume half movement, Prone doesn't apply |
| **Knocked Prone during own turn without movement** | Stay Prone (can't afford to stand) |
| **Knocked Prone outside own turn** | Stay Prone (will auto-stand at next turn start) |

### Implementation Details

**File**: `dnd/conditions.py:632`

The `Prone._apply()` method checks `entity.is_my_turn` and available movement:

```python
def _apply(self, declaration_event):
    # BG3-style: If it's the entity's turn and they have movement, immediately stand
    if target_entity.is_my_turn:
        base_movement = target_entity.action_economy.get_base_value("movement")
        half_movement = base_movement // 2
        current_movement = target_entity.action_economy.movement.normalized_score
        if current_movement >= half_movement:
            target_entity.action_economy.consume("movement", half_movement)
            # Return empty lists - condition doesn't apply
            return [], [], [], [], effect_event

    # Normal case: apply Prone modifiers + auto-stand handler for turn start
    # ...
```

The auto-stand handler fires at `TURN_START` in `EventPhase.EFFECT`:
1. Checks `event.source_entity_uuid == target_uuid` (is it the Prone entity's turn?)
2. Deducts half movement
3. Removes the Prone condition

### Integration with Grease

Grease spell applies Prone on failed DEX saves. Because of BG3 auto-stand:
- Entity knocked Prone during **their own turn** with movement → immediately stands (movement consumed)
- Entity knocked Prone **outside their turn** → stays Prone until turn start
- Entity starting turn in Grease zone → DEX save, if fail: Prone applied, then auto-stand (movement consumed)

### Test Coverage

`examples/test_prone_auto_stand.py` verifies:
1. Turn start auto-stand with movement cost
2. Prone only auto-stands on own turn
3. StandUp action is not registered
4. Immediate stand when Prone applied during own turn with movement
5. Stay Prone when no movement available

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

### Creating a Zone Spell Effect (Modern Pattern)

The modern pattern uses position-indexed spatial handlers for efficiency:

```python
from dnd.tile_conditions import ZoneControlCondition
from dnd.conditions import Concentrating
from dnd.core.events import EventHandler, Trigger, EventType, EventPhase

class MyZone(ZoneControlCondition):
    """Zone with entry damage and difficult terrain."""
    name: str = "My Zone"
    zone_shape: str = "sphere"
    zone_radius_feet: int = 20
    adds_difficult_terrain: bool = True  # Built-in terrain modifier
    spell_dc: int = 15  # Custom field

    def _has_entry_effect(self) -> bool:
        return True  # Triggers _create_zone_entry_handler

    def _create_zone_entry_handler(self) -> EventHandler:
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc

        def processor(event, _):
            entity_uuid = getattr(event, 'entity_uuid', None)
            entity = Entity.get(entity_uuid)
            if not entity or entity.uuid == source_uuid:
                return None
            # Your effect logic here (e.g., save, damage, condition)
            return None

        return EventHandler(
            name="My Zone Entry",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

# In spell's _apply method:
zone = MyZone(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=caster.uuid,
    zone_center=(5, 5),
    spell_dc=caster.spell_save_dc()
)
caster.add_condition(zone)

# Link to concentration for auto-cleanup
concentration = Concentrating(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=caster.uuid,
    spell_name="My Spell"
)
caster.add_condition(concentration)
concentration.add_external_condition(caster.uuid, zone.uuid)
```

### Existing Zone Spell Examples

See implemented spells for complete patterns:

| Spell | Pattern | Key Handlers |
|-------|---------|--------------|
| `SpikeGrowthZone` | Entry damage only | `_create_zone_entry_handler` |
| `GreaseZone` | Entry + turn start save → Prone | Entry + turn start handlers |
| `WebZone` | Entry save → WebRestrained | Entry handler, grants escape action |
| `CloudkillZone` | Entry + turn start + auto-move | Entry + turn start + caster turn handler |
| `SpiritGuardiansZone` | Entry + turn start + follow caster + exit cleanup | All four handler types |

---

## Test Coverage

### Core Infrastructure: `examples/test_terrain_movement_system.py`

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

### Prone Auto-Stand: `examples/test_prone_auto_stand.py`

| Test | Description |
|------|-------------|
| `test_prone_auto_stand` | Turn start removes Prone, deducts half movement |
| `test_prone_not_auto_stand_on_other_turn` | Prone only removes on entity's own turn |
| `test_stand_up_no_longer_registered` | StandUp action is not in available actions |
| `test_prone_during_own_turn_with_movement` | Immediate stand when Prone applied during own turn |
| `test_prone_during_own_turn_no_movement` | Stay Prone when no movement available |

---

### Zone Spell Tests

#### `examples/test_spike_growth.py`

| Test | Description |
|------|-------------|
| `test_spike_growth_zone_creation` | Zone created, caster concentrating |
| `test_spike_growth_entry_damage` | 2d4 piercing on entry |
| `test_spike_growth_difficult_terrain` | Tiles have walking cost 2 |
| `test_spike_growth_concentration_break` | Zone removed when concentration breaks |

#### `examples/test_grease.py`

| Test | Description |
|------|-------------|
| `test_grease_zone_creation` | Zone created with difficult terrain |
| `test_grease_entry_prone` | DEX save on entry, Prone on fail |
| `test_grease_turn_start_prone` | DEX save at turn start, BG3 auto-stand |
| `test_grease_turn_start_no_movement` | Stay Prone if no movement for auto-stand |
| `test_grease_not_own_turn` | Stay Prone when knocked down outside turn |
| `test_grease_concentration_break` | Zone removed, terrain restored |

#### `examples/test_web.py`

| Test | Description |
|------|-------------|
| `test_web_zone_creation` | Zone created with difficult terrain |
| `test_web_entry_restrained` | DEX save on entry, Restrained on fail |
| `test_web_escape_success` | Escape action STR check removes Restrained |
| `test_web_escape_failure` | Failed STR check, still Restrained |
| `test_web_concentration_break` | Zone removed, Restrained persists (spell-specific) |

#### `examples/test_cloudkill.py`

| Test | Description |
|------|-------------|
| `test_cloudkill_zone_creation` | Zone created at target position |
| `test_cloudkill_entry_damage` | 5d8 poison on entry (CON save half) |
| `test_cloudkill_turn_start_damage` | Damage on turn start in zone |
| `test_cloudkill_auto_move` | Zone moves 10ft from caster at caster's turn |
| `test_cloudkill_upcast` | +1d8 per level above 5th |
| `test_cloudkill_concentration_break` | Zone removed when concentration breaks |

#### `examples/test_spirit_guardians.py`

| Test | Description |
|------|-------------|
| `test_spirit_guardians_zone_creation` | Zone created centered on caster |
| `test_spirit_guardians_enemy_damage` | 3d8 radiant on enemy entry (WIS save half) |
| `test_spirit_guardians_ally_safe` | Allies not affected |
| `test_spirit_guardians_entry_damage` | Damage when enemy enters |
| `test_spirit_guardians_once_per_turn` | Marker prevents repeat damage |
| `test_spirit_guardians_follows_caster` | Zone center updates on caster move |
| `test_spirit_guardians_speed_halved` | Enemy speed halved in zone |
| `test_spirit_guardians_speed_restored` | Speed restored on exit |
| `test_spirit_guardians_concentration_break` | Zone removed when concentration breaks |

---

## Implemented Zone Spells Reference

### Spike Growth (2nd level, Transmutation)

**File**: `dnd/spells/transmutation.py`

| Property | Value |
|----------|-------|
| Range | 150ft |
| Zone | 20ft radius sphere |
| Duration | Concentration, up to 10 minutes |
| Terrain | Difficult terrain (+1 walking cost) |
| Effect | 2d4 piercing on entry (no save) |
| Notes | Caster is immune. Camouflaged (WIS Perception DC = spell DC to notice - not implemented). |

### Grease (1st level, Conjuration)

**File**: `dnd/spells/conjuration.py`

| Property | Value |
|----------|-------|
| Range | 60ft |
| Zone | 10ft cube |
| Duration | Concentration (BG3-style for cleanup) |
| Terrain | Difficult terrain |
| Effect | DEX save on entry/turn start or Prone |
| Notes | Creatures in zone on cast also save. Uses BG3 auto-stand. |

### Web (2nd level, Conjuration)

**File**: `dnd/spells/conjuration.py`

| Property | Value |
|----------|-------|
| Range | 60ft |
| Zone | 20ft cube |
| Duration | Concentration, up to 1 hour |
| Terrain | Difficult terrain |
| Effect | DEX save on entry or Restrained |
| Escape | Action + STR (Athletics) check vs spell DC |
| Notes | `WebRestrained` applies Restrained sub-condition + grants `EscapeWebAction`. |

### Cloudkill (5th level, Conjuration)

**File**: `dnd/spells/conjuration.py`

| Property | Value |
|----------|-------|
| Range | 120ft |
| Zone | 20ft radius sphere |
| Duration | Concentration, up to 10 minutes |
| Terrain | Heavily obscured (see `VISION_HIDING_COVER_PLAN.md`) |
| Effect | 5d8 poison on entry/turn start (CON save for half) |
| Movement | Zone moves 10ft away from caster at caster's turn start |
| Upcast | +1d8 per level above 5th |
| Notes | Affects everyone including caster. Uses `move_zone()` for efficient movement. |

### Spirit Guardians (3rd level, Conjuration)

**File**: `dnd/spells/conjuration.py`

| Property | Value |
|----------|-------|
| Range | Self |
| Zone | 15ft radius sphere centered on caster |
| Duration | Concentration, up to 10 minutes |
| Effect | Enemies: 3d8 radiant (WIS save for half), speed halved |
| Movement | Zone follows caster automatically |
| Once per turn | Marker condition prevents multiple damage |
| Upcast | +1d8 per level above 3rd |
| Notes | Allies unaffected. Uses faction system (`is_ally()`). Exit removes speed debuff. |

**Helper Conditions**:
- `SpiritGuardiansTriggered` - Marker removed at target's turn end
- `SpiritGuardiansSlowed` - Speed halving, removed on zone exit

---

## Hazard Detection & Safe Pathfinding

### Overview

Hazard-aware pathfinding allows entities to avoid dangerous tile conditions (traps, zone spells) when safe alternatives exist. The system is **subjective** — what counts as hazardous depends on the observer's faction and perception.

### HazardFilter Enum (`dnd/core/base_conditions.py`)

Controls which entities consider a condition hazardous:

| Value | Meaning | Example |
|-------|---------|---------|
| `ALL` | Hazardous to everyone | Grease, Web |
| `ENEMIES` | Only hazardous to enemies of the source | Spirit Guardians |
| `NON_SOURCE` | Hazardous to everyone except the caster | Spike Growth |

Set on `BaseCondition.hazard_filter`. Conditions without `hazard_filter = None` are not hazards.

### Condition Stealth DC (`BaseCondition.condition_stealth_dc`)

Optional perception DC to detect the hazard. If set, the hazard is only visible/avoidable when the observer's passive perception ≥ the DC. Used for hidden traps.

### Key Methods

**BaseBlock** (`dnd/core/base_block.py`):
- `is_hazardous_for(entity_uuid)` — checks own conditions for hazards, evaluates `hazard_filter` + `condition_stealth_dc` vs observer's perception
- `is_enemy_of(entity_uuid)` — faction check. BaseBlock defaults to `True`, Entity overrides with faction logic.

**GridMap** (`dnd/core/gridmap.py`):
- `is_position_hazardous_for(x, y, entity_uuid)` — delegates to tile's `is_hazardous_for()`
- `is_position_hazardous(x, y)` — non-entity-aware check (any hazard present)
- `is_walkable_for(x, y, entity_uuid, walk_in_danger=True)` — when `walk_in_danger=False`, hazardous tiles treated as impassable
- `compute_paths(position, max_distance, ..., walk_in_danger=True)` — Dijkstra with hazard avoidance

### Safe Pathfinding (Two-Pass Dijkstra)

In `Entity.compute_senses_from_position()`:

1. **Pass 1**: Normal Dijkstra → `paths` (all reachable tiles)
2. **Check**: Do any paths cross hazardous tiles?
3. **Pass 2** (only if needed): Dijkstra with `walk_in_danger=False` → `safe_paths` (hazard-avoiding routes)

`Senses.safe_paths` is empty when no hazards affect the entity's paths.

### Move Action Integration

- `Move` has `prefer_safe: bool = True` (default). When True, uses `safe_paths` if available, falls back to `paths`.
- `execute_by_index()` and `ExecuteByIndexRequest` accept `prefer_safe` parameter.
- CLI: `move ? X Y` previews path, `move X Y short` forces shortest (through hazards).

### Spike Trap Rework

Old: `Spikes` tile type with hardcoded behavior.
New: `Floor` tile + `SpikeTrapCondition` marker + shared `SpatialHandler` for damage.

- `create_spike_zone(positions, ...)` in `dnd/tiles.py` creates the zone
- `SpikeTrapCondition` (`dnd/tile_conditions.py`) — marker with `hazard_filter=HazardFilter.ALL`
- Deactivation removes the condition, tile stays Floor

### Zone Spell Markers

`ZoneControlCondition` has marker fields for hazard detection:
- `marker_name: Optional[str]` — display name for the marker condition
- `marker_hazard_filter: Optional[HazardFilter]` — hazard classification
- `marker_stealth_dc: Optional[int]` — perception DC to detect

`_apply_tile_markers()` creates `ZoneMarkerCondition` on each affected tile.

| Zone Spell | HazardFilter | stealth_dc |
|-----------|-------------|-----------|
| Spike Growth | NON_SOURCE | 15 (hidden) |
| Grease | ALL | None |
| Web | ALL | None |
| Cloudkill | ALL | None |
| Spirit Guardians | ENEMIES | None |

### Tests

- `examples/test_hazard_pathfinding.py` — 48 assertions covering all hazard scenarios

---

## Related Documentation

- `CLAUDE.md` - Main codebase guide
- `IMPLEMENTATION_GUIDE.md` - How to implement conditions and event handlers
- `AOE_TARGETING_REFERENCE.md` - AoE shape calculations
- `VISION_HIDING_COVER_PLAN.md` - Design doc for lighting, obscurement, hiding/stealth, invisibility, and cover
- `Z_AXIS_PLAN.md` - Design doc for z-axis/verticality
- `archive/ZONE_SPELLS_IMPLEMENTATION_PLAN.md` - Original planning document for zone spells (historical)
