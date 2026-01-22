# Server and Movement System Analysis

## Overview

This document describes the server architecture, movement system, and the Tile/GridMap refactor that was completed to fix occupancy-aware pathfinding.

---

## Server Folder Overview

### Files

| File | Purpose |
|------|---------|
| `event_server.py` | Main FastAPI server - REST API + WebSocket |
| `api_models.py` | Pydantic models for REST responses |
| `test_client.py` | CLI WebSocket client for testing |
| `test_monitor.py` | In-process EventMonitor tests |
| `test_websocket.py` | End-to-end tests with FastAPI TestClient |

### Current REST Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Health check + listener count |
| `/state` | GET | Full state (grid + entities + encounter) |
| `/entities` | GET | All entities lightweight |
| `/entity/{uuid}` | GET | Single entity full details |
| `/grid` | GET | Grid/map data |
| `/encounter` | GET | Encounter state |
| `/events` | GET | Recent events (filterable) |
| `/event-types` | GET | List available types/phases |
| `/simulation/start` | POST | Reset + auto-run |
| `/simulation/reset` | POST | Reset + pause |
| `/simulation/pause` | POST | Pause loop |
| `/simulation/resume` | POST | Resume loop |
| `/simulation/step` | POST | Execute one turn |
| `/simulation/status` | GET | Current status |
| `/simulation/set-delay` | POST | Set turn delay |

### What's Missing for Human Controller

1. **No player action endpoints** - Currently AI-only
2. **No available actions endpoint** - Frontend can't query "what can entity X do?"
3. **No manual turn control** - Can't say "it's now player's turn, wait for input"

---

## Tile/GridMap Architecture (COMPLETED)

### The Refactored System

The system now has a clean separation:

**Tile** (`dnd/core/base_tiles.py`) - Game object for grid cells
- Inherits from `BaseBlock` (can have conditions, UUID, event handlers)
- Stores properties: `walkable`, `visible`, `name`, `sprite_name`
- Position stored on tile, managed by GridMap

**GridMap** (`dnd/core/gridmap.py`) - Centralized spatial manager
- Stores Tile objects: `_tiles: Dict[Tuple[int, int], Tile]`
- Handles all spatial computation (FOV, pathfinding)
- Tracks entity positions with occupancy awareness
- Fires spatial events on changes

### Key Methods

| Method | Purpose |
|--------|---------|
| `is_walkable(x, y)` | Tile property only - is the tile walkable? |
| `is_walkable_for(x, y, entity_uuid)` | Tile + occupancy - can this entity walk here? |
| `compute_paths(start, max_dist, requesting_entity_uuid)` | Dijkstra with occupancy awareness |
| `compute_fov(origin, max_dist)` | Shadowcast for visibility |
| `get_tile(x, y)` | Get the Tile object at position |

### Occupancy-Aware Pathfinding

```python
# GridMap.is_walkable_for()
def is_walkable_for(self, x: int, y: int, requesting_entity_uuid: Optional[UUID] = None) -> bool:
    # First check tile walkability
    if not self.is_walkable(x, y):
        return False
    # Check occupancy
    occupants = self._entities_by_position.get((x, y), set())
    if not occupants:
        return True
    # If there are occupants, only allow if it's just the requesting entity
    if requesting_entity_uuid is None:
        return False
    return occupants == {requesting_entity_uuid}

# GridMap.compute_paths() uses is_walkable_for when entity_uuid provided
def compute_paths(self, start, max_distance=None, requesting_entity_uuid=None):
    if requesting_entity_uuid is not None:
        walkable_check = lambda x, y: self.is_walkable_for(x, y, requesting_entity_uuid)
    else:
        walkable_check = lambda x, y: self.is_walkable(x, y)
    return dijkstra(start, walkable_check, ...)
```

### Entity Integration

```python
# Entity.compute_senses_from_position() - uses GridMap directly
def compute_senses_from_position(position, seen, max_distance, entity_uuid):
    grid = get_map()

    # FOV via shadowcast
    visible_positions = grid.compute_fov(position, max_distance)

    # Paths with occupancy check - excludes cells occupied by OTHER entities
    _, paths = grid.compute_paths(position, max_distance, requesting_entity_uuid=entity_uuid)

    # Walkable dict - tile property only (for threat calculation)
    walkable = {pos: grid.is_walkable(pos[0], pos[1]) for pos in visible_positions}

    return visible_dict, filtered_paths, walkable, visible_entities
```

---

## Senses Data: paths vs walkable

**Critical distinction** for systems like Opportunity Attacks:

| Field | Contains | Use Case |
|-------|----------|----------|
| `senses.paths` | Positions entity can move to (excludes occupied cells) | Movement options |
| `senses.walkable` | Tile walkability property only | Threatened positions for OA |

### Why This Matters

Opportunity Attacks threaten adjacent positions that are:
1. Visible to the entity
2. On walkable tiles
3. **Including occupied cells** - an enemy standing there is still threatened

```python
# Senses.get_threathened_positions() - uses walkable, NOT paths
def get_threathened_positions(self) -> List[Tuple[int,int]]:
    neighbors = set([
        (position[0] + 1, position[1]), (position[0] - 1, position[1]),
        (position[0], position[1] + 1), (position[0], position[1] - 1),
        (position[0] + 1, position[1] + 1), (position[0] - 1, position[1] - 1),
        (position[0] + 1, position[1] - 1), (position[0] - 1, position[1] + 1),
    ])
    visible_set = set(self.visible.keys())
    walkable_set = set(pos for pos, is_walkable in self.walkable.items() if is_walkable)
    return list(neighbors & visible_set & walkable_set)
```

---

## Movement System Flow

### The Chain (Post-Refactor)

```
Move Action (dnd/actions.py)
    │
    │  _setup_path(): self.path = entity.senses.paths[end_position]
    │  validate_path(): checks path exists in senses.paths
    │  _apply(): Entity.update_entity_position() + update_all_entities_senses()
    │
    ▼
Entity.senses.paths (dnd/blocks/sensory.py)
    │
    │  Dict[position, path_list]
    │  Populated by Entity.update_entity_senses()
    │  ✓ NOW EXCLUDES CELLS OCCUPIED BY OTHER ENTITIES
    │
    ▼
Entity.compute_senses_from_position() (dnd/entity.py)
    │
    │  Uses GridMap.compute_fov() for visibility
    │  Uses GridMap.compute_paths(requesting_entity_uuid=entity_uuid) for pathfinding
    │  ✓ PASSES ENTITY UUID FOR OCCUPANCY CHECK
    │
    ▼
GridMap.compute_paths() (dnd/core/gridmap.py)
    │
    │  Uses is_walkable_for() when requesting_entity_uuid provided
    │  ✓ EXCLUDES OCCUPIED CELLS FROM PATHS
    │
    ▼
GridMap.is_walkable_for() (dnd/core/gridmap.py)
    │
    │  Checks: tile exists AND tile.walkable AND not occupied by others
    │  ✓ OCCUPANCY CHECK AT SOURCE
```

---

## Position Tracking

Entity positions are tracked in **3 places** (kept in sync):

| Registry | Location | Updated By |
|----------|----------|------------|
| `Entity._entity_by_position` | Class variable | `Entity.update_entity_position()` |
| `GridMap._entity_positions` | Singleton | `GridMap.move_entity()` (called by above) |
| `entity.senses.entities` | Instance | `Entity.update_entity_senses()` |

### Sync Flow

```
Entity.update_entity_position(entity, new_pos)
    ├── Entity._entity_by_position[old].remove(entity)
    ├── Entity._entity_by_position[new].append(entity)
    ├── entity._set_position(new_pos)  # Updates entity.position and senses.position
    └── get_map().move_entity(entity.uuid, new_pos)  # Updates GridMap + fires events
        ├── GridMap._entity_positions[uuid] = new_pos
        ├── GridMap._entities_by_position[old].discard(uuid)
        ├── GridMap._entities_by_position[new].add(uuid)
        └── Fires SpatialChangeEvent (ENTITY_LEFT, ENTITY_ENTERED)

Entity.update_all_entities_senses()  # Called after movement
    └── For each entity:
        └── entity.update_entity_senses()
            └── senses.entities = {visible entities and their positions}
```

---

## Tests Passing

All tests in `examples/test_available_actions.py` pass (9/9):

| Test | Status |
|------|--------|
| Basic Available Actions | ✓ |
| Dash Action | ✓ |
| Dodge Action | ✓ |
| Disengage Action | ✓ |
| Disengage Prevents OA | ✓ |
| OA Without Disengage | ✓ |
| Prone Actions | ✓ |
| Condition Duration at Turn Start | ✓ |
| Blocking Conditions | ✓ |

The OA test confirms that:
1. Moving away from a threatening enemy without Disengage triggers OA
2. Moving away with Disengage condition does NOT trigger OA
3. Threatened positions correctly include occupied cells

---

## Future: Tile Conditions

With Tile as BaseBlock, we can add environmental effects:

```python
# Tile on fire - damages entities that enter
fire_tile = grid.get_tile(5, 5)
fire_tile.add_condition(OnFire(damage="1d6", source_entity_uuid=caster.uuid))

# Trapped tile - triggers on entry
trap_tile = grid.get_tile(3, 3)
trap_tile.add_condition(PitTrap(damage="2d6", perception_dc=15, disable_dc=12))

# Difficult terrain - costs double movement
mud_tile = grid.get_tile(7, 7)
mud_tile.add_condition(DifficultTerrain())
```

---

## Next Steps: Human Controller

### Needed Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/entity/{uuid}/available-actions` | GET | What can this entity do? |
| `/action/move` | POST | Execute move (body: entity_uuid, position) |
| `/action/attack` | POST | Execute attack (body: entity_uuid, target_uuid, weapon_slot) |
| `/action/dash` | POST | Execute dash |
| `/action/dodge` | POST | Execute dodge |
| `/action/disengage` | POST | Execute disengage |
| `/action/end-turn` | POST | End current turn |

### Controller Architecture

```
Controller (abstract)
├── AggressiveAIController (existing) - auto-picks actions
├── PassController (existing) - does nothing, passes turn
└── HumanController (new) - waits for REST input
    └── get_next_action() returns None until REST endpoint called
```

### Turn Flow with Human

```
1. Encounter.run_turn() starts
2. Gets controller for current entity
3. If HumanController:
   a. Fire TURN_START event (UI can show "your turn")
   b. Wait for action via REST endpoint
   c. Execute action
   d. Loop until end-turn or no actions remaining
4. Fire TURN_END event
```
