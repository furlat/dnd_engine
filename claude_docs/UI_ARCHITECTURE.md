# Combat Viewer UI Architecture

## Overview

A web-based visualization tool for watching D&D combat simulations in real-time. The UI connects to the game server via WebSocket for live event streaming and REST for state queries.

---

## Event Payload Analysis

### What Events Contain (Studied from actual code)

| Event Type | Key Fields | Notes |
|------------|------------|-------|
| **MovementEvent** | `source_entity_uuid`, `start_position`, `end_position`, `path` | Full path for animation |
| **AttackEvent** | `source_entity_uuid`, `target_entity_uuid`, `attack_outcome`, `damage_rolls[].total` | Has damage dealt, NOT resulting HP |
| **DeathEvent** | `entity_uuid`, `entity_name`, `final_hp`, `killer_uuid` | Has name! |
| **TurnStartEvent** | `entity_uuid`, `round_number`, `turn_index`, `actions_available`, `movement_available` | Full economy state |
| **TurnEndEvent** | `entity_uuid`, `actions_used`, `movement_used` | What was consumed |
| **ConditionApplicationEvent** | `condition.name`, `condition.target_entity_uuid`, `condition.duration` | Full condition object |
| **ConditionRemovalEvent** | `condition.name`, `condition.target_entity_uuid`, `expired` | Knows if expired vs removed |
| **SpatialChangeEvent** | `position`, `entity_uuid`, `old_position`, `tile_walkable`, `tile_visible` | For grid updates |

### What's MISSING from Events

| Missing Data | Why It Matters | Solution |
|--------------|----------------|----------|
| **Entity names** | Display in UI | Initial load, cache by UUID |
| **Current HP** | HP bars | Track: `hp -= damage_dealt` |
| **Max HP** | HP bar percentage | Initial load |
| **AC** | Display stats | Initial load |
| **Position** (except movement) | Grid display | Initial load, track movements |
| **Conditions list** | Status display | Track add/remove events |
| **Entity emoji/type** | Visual token | Initial load or derive from name |

### Synchronization Strategy

```
INITIAL LOAD (REST):
  - All entities with: uuid, name, position, hp, max_hp, ac, conditions, is_dead
  - Grid bounds and tiles
  - Encounter state (if active)

DELTA UPDATES (WebSocket events):
  - Movement → update entity.position
  - Attack (COMPLETION) → entity.hp -= damage_rolls.sum()
  - Death → entity.is_dead = true
  - Condition Application → entity.conditions.push(name)
  - Condition Removal → entity.conditions.remove(name)
  - Turn Start → currentTurnEntityUuid = entity_uuid, round = round_number
```

### Event Phase Filtering

Events fire at multiple phases (DECLARATION → EXECUTION → EFFECT → COMPLETION).
**Client should only process COMPLETION phase** to avoid duplicate updates.

```javascript
if (event.phase !== 'completion') return; // Skip non-final events
```

---

## Design Principles

1. **Events = Notifications** - WebSocket events are lightweight change notifications
2. **REST = Full State** - HTTP endpoints provide complete state on demand
3. **Client Reconstructs** - Client maintains local state, updates from events
4. **Simple First** - Start with basic HTML/JS, no frameworks

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        SERVER                                │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐  │
│  │  Encounter  │───►│ EventQueue  │───►│  EventMonitor   │  │
│  │  (combat)   │    │ (all events)│    │  (broadcasts)   │  │
│  └─────────────┘    └─────────────┘    └────────┬────────┘  │
│                                                  │           │
│  ┌─────────────────────────────────┐            │           │
│  │       REST Endpoints            │            │           │
│  │  GET /state    - full state     │            │           │
│  │  GET /entities - all entities   │            │           │
│  │  GET /entity/{id} - one entity  │            │           │
│  │  GET /grid     - map data       │            │           │
│  │  GET /encounter - combat state  │            │           │
│  └─────────────────────────────────┘            │           │
└───────────────────────────────────────────────────────────────┘
                    │ HTTP                        │ WebSocket
                    ▼                             ▼
┌─────────────────────────────────────────────────────────────┐
│                        CLIENT                                │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐  │
│  │  StateStore │◄───│EventHandler │◄───│ WebSocket Conn  │  │
│  │  (local)    │    │ (updates)   │    │ (receives)      │  │
│  └──────┬──────┘    └─────────────┘    └─────────────────┘  │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    RENDERER                              ││
│  │  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  ││
│  │  │ GridView │  │ UnitPanels   │  │   CombatLog       │  ││
│  │  │ (2D map) │  │ (HP/status)  │  │   (events)        │  ││
│  │  └──────────┘  └──────────────┘  └───────────────────┘  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Initial Load

```
1. Client opens page
2. Client: GET /state → receives full state (grid, entities, encounter)
3. Client: Connect WebSocket
4. Client renders initial state
```

### During Combat

```
1. Server: Action executed → Event fired
2. WebSocket: Event broadcast to client
3. Client: EventHandler processes event
4. Client: Updates local StateStore
5. Client: Re-renders affected components

If event is lightweight (just IDs):
6. Client: GET /entity/{id} for full details
7. Client: Updates StateStore with full data
```

### Event Types & Client Handling

| Event Type | Client Action |
|------------|---------------|
| `turn_start` | Highlight active entity, update turn indicator |
| `turn_end` | Clear highlight, update economy display |
| `movement` | Animate entity to new position |
| `attack` | Show attack animation/indicator, flash target |
| `take_damage` | Update HP bar, show damage number |
| `death` | Mark entity as dead, gray out, show death effect |
| `condition_application` | Add condition icon to entity |
| `condition_removal` | Remove condition icon |
| `round_start` | Update round counter |
| `encounter_end` | Show victory/defeat screen |

---

## REST API Design (Detailed)

### Architecture: API Models with Factory Methods

**Principle**: Entity stays untouched. API has its own Pydantic models with `.create()` classmethods.

```
Entity (game logic, has callables)
    │
    │  .create(entity)
    ▼
APIEntitySummary (simple Pydantic, serializable)
    │
    │  .model_dump()
    ▼
JSON response
```

**Why this approach:**
- Entity keeps full game logic (callables for contextual modifiers)
- API models are explicit about what's exposed
- Single conversion point (`.create()` classmethod)
- Events carry most data; REST is sparse (initial load only)

### API Models (to be placed in `server/api_models.py`)

```python
from pydantic import BaseModel
from typing import List, Optional, Tuple
from uuid import UUID

class APIEntitySummary(BaseModel):
    """Lightweight entity for list views and event-driven updates."""
    uuid: str
    name: str
    position: Tuple[int, int]
    hp: int
    max_hp: int
    ac: int
    conditions: List[str]
    is_dead: bool

    @classmethod
    def create(cls, entity: 'Entity') -> 'APIEntitySummary':
        # Compute max HP (needs constitution modifier)
        con_mod = entity.ability_scores.get_ability("constitution").get_combined_values().normalized_score
        max_hp = entity.health.get_max_hit_dices_points(con_mod) + entity.health.max_hit_points_bonus.score

        return cls(
            uuid=str(entity.uuid),
            name=entity.name,
            position=entity.position,
            hp=entity.get_hp(),
            max_hp=max_hp,
            ac=entity.ac_bonus().normalized_score,
            conditions=list(entity.active_conditions.keys()),
            is_dead=entity.get_hp() <= 0
        )


class APIEntityFull(APIEntitySummary):
    """Full entity details for single-entity queries."""
    action_economy: dict
    ability_scores: dict
    weapon_name: Optional[str]

    @classmethod
    def create(cls, entity: 'Entity') -> 'APIEntityFull':
        # Compute max HP
        con_mod = entity.ability_scores.get_ability("constitution").get_combined_values().normalized_score
        max_hp = entity.health.get_max_hit_dices_points(con_mod) + entity.health.max_hit_points_bonus.score

        weapon = entity.equipment.weapon_main_hand
        return cls(
            uuid=str(entity.uuid),
            name=entity.name,
            position=entity.position,
            hp=entity.get_hp(),
            max_hp=max_hp,
            ac=entity.ac_bonus().normalized_score,
            conditions=list(entity.active_conditions.keys()),
            is_dead=entity.get_hp() <= 0,
            action_economy={
                'actions': entity.action_economy.actions.normalized_score,
                'bonus_actions': entity.action_economy.bonus_actions.normalized_score,
                'reactions': entity.action_economy.reactions.normalized_score,
                'movement': entity.action_economy.movement.normalized_score,
            },
            ability_scores={
                'strength': entity.ability_scores.strength.ability_score.normalized_score,
                'dexterity': entity.ability_scores.dexterity.ability_score.normalized_score,
                'constitution': entity.ability_scores.constitution.ability_score.normalized_score,
                'intelligence': entity.ability_scores.intelligence.ability_score.normalized_score,
                'wisdom': entity.ability_scores.wisdom.ability_score.normalized_score,
                'charisma': entity.ability_scores.charisma.ability_score.normalized_score,
            },
            weapon_name=weapon.name if weapon else None
        )


class APITile(BaseModel):
    x: int
    y: int
    walkable: bool
    visible: bool


class APIGrid(BaseModel):
    min_x: int
    min_y: int
    max_x: int
    max_y: int
    tiles: List[APITile]

    @classmethod
    def create(cls, grid: 'GridMap') -> 'APIGrid':
        bounds = grid.bounds  # Returns (min_x, min_y, max_x, max_y)
        tiles = [
            APITile(x=x, y=y, walkable=td.walkable, visible=td.visible)
            for (x, y), td in grid._tiles.items()
        ]
        return cls(
            min_x=bounds[0], min_y=bounds[1],
            max_x=bounds[2], max_y=bounds[3],
            tiles=tiles
        )


class APICombatant(BaseModel):
    uuid: str
    name: str
    initiative: int
    is_dead: bool


class APIEncounter(BaseModel):
    uuid: str
    name: str
    state: str
    round_number: int
    current_turn_index: int
    current_entity_uuid: Optional[str]
    initiative_order: List[APICombatant]

    @classmethod
    def create(cls, encounter: 'Encounter') -> 'APIEncounter':
        from dnd.entity import Entity
        combatants = []
        for uuid in encounter.initiative_order:
            entity = Entity.get(uuid)
            combatants.append(APICombatant(
                uuid=str(uuid),
                name=entity.name if entity else "Unknown",
                initiative=encounter.combatants[uuid].initiative_total,
                is_dead=encounter.combatants[uuid].is_dead
            ))
        current_uuid = None
        if encounter.initiative_order:
            current_uuid = str(encounter.initiative_order[encounter.current_turn_index])
        return cls(
            uuid=str(encounter.uuid),
            name=encounter.name,
            state=encounter.state.value,
            round_number=encounter.round_number,
            current_turn_index=encounter.current_turn_index,
            current_entity_uuid=current_uuid,
            initiative_order=combatants
        )


class APIGameState(BaseModel):
    """Full state for initial load."""
    grid: APIGrid
    entities: List[APIEntitySummary]
    encounter: Optional[APIEncounter]
```

---

## Server Initialization

For now, the simulation is initialized in the server's main. The server owns the game state.

```python
# server/event_server.py (main block)

import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

# Game state (module-level, shared with endpoints)
encounter: Optional[Encounter] = None

def setup_combat():
    """Initialize grid, entities, encounter."""
    global encounter

    # Reset state
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Encounter.clear_all_encounters()
    EventQueue._all_events.clear()

    # Create grid
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    # Create combatants
    goblin = create_goblin(name="Goblin Scout", position=(2, 7))
    skeleton = create_skeleton(name="Skeleton Warrior", position=(12, 7))
    Entity.update_all_entities_senses()

    # Create encounter
    encounter = Encounter(name="Test Combat", source_entity_uuid=uuid4())
    encounter.add_combatant(goblin, AggressiveAIController(source_entity_uuid=goblin.uuid))
    encounter.add_combatant(skeleton, AggressiveAIController(source_entity_uuid=skeleton.uuid))

    return encounter


async def run_combat_loop(enc: Encounter, delay: float = 1.0):
    """Run combat with delay between turns (for visualization)."""
    enc.start_encounter()

    while enc.state == EncounterState.ACTIVE:
        enc.run_turn()
        await asyncio.sleep(delay)  # Pause for client to see events


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Server startup/shutdown."""
    # Don't auto-start - wait for POST /simulation/start
    yield
    # Cleanup
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()


app = FastAPI(lifespan=lifespan)
```

**Flow:**
1. Server starts → `setup_combat()` creates grid, entities, encounter
2. Combat loop runs in background with delays between turns
3. Each action fires events → WebSocket broadcasts to connected clients
4. Clients can `GET /state` anytime for full state

---

## Simulation Control Endpoints

```python
# Simulation state
class SimulationState:
    encounter: Optional[Encounter] = None
    combat_task: Optional[asyncio.Task] = None
    paused: bool = False
    turn_delay: float = 1.5  # seconds between turns

sim = SimulationState()


@app.post("/simulation/start")
async def start_simulation():
    """Reset and start a new combat simulation."""
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()

    sim.encounter = setup_combat()
    sim.paused = False
    sim.combat_task = asyncio.create_task(run_combat_loop())

    return {"status": "started", "encounter_uuid": str(sim.encounter.uuid)}


@app.post("/simulation/reset")
async def reset_simulation():
    """Stop current combat and reset to fresh state."""
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()

    sim.encounter = setup_combat()
    sim.paused = True  # Start paused, wait for explicit start

    return {"status": "reset", "encounter_uuid": str(sim.encounter.uuid)}


@app.post("/simulation/pause")
async def pause_simulation():
    """Pause the combat loop."""
    sim.paused = True
    return {"status": "paused"}


@app.post("/simulation/resume")
async def resume_simulation():
    """Resume the combat loop."""
    if sim.encounter is None:
        return JSONResponse(status_code=400, content={"error": "No simulation to resume"})

    sim.paused = False

    # Restart loop if task is done
    if sim.combat_task is None or sim.combat_task.done():
        sim.combat_task = asyncio.create_task(run_combat_loop())

    return {"status": "resumed"}


@app.post("/simulation/step")
async def step_simulation():
    """Execute a single turn (useful when paused)."""
    if sim.encounter is None:
        return JSONResponse(status_code=400, content={"error": "No simulation"})

    if sim.encounter.state != EncounterState.ACTIVE:
        return {"status": "encounter_ended", "state": sim.encounter.state.value}

    sim.encounter.run_turn()
    return {"status": "stepped", "round": sim.encounter.round_number}


@app.get("/simulation/status")
async def get_simulation_status():
    """Get current simulation status."""
    return {
        "has_encounter": sim.encounter is not None,
        "paused": sim.paused,
        "encounter_state": sim.encounter.state.value if sim.encounter else None,
        "round_number": sim.encounter.round_number if sim.encounter else None,
        "turn_delay": sim.turn_delay
    }


async def run_combat_loop():
    """Combat loop that respects pause state."""
    if sim.encounter is None:
        return

    if sim.encounter.state == EncounterState.NOT_STARTED:
        sim.encounter.start_encounter()

    while sim.encounter.state == EncounterState.ACTIVE:
        if sim.paused:
            await asyncio.sleep(0.1)  # Check pause flag frequently
            continue

        sim.encounter.run_turn()
        await asyncio.sleep(sim.turn_delay)
```

**Control Flow:**
```
POST /simulation/start  → Reset + start auto-running
POST /simulation/reset  → Reset + pause (manual control)
POST /simulation/pause  → Stop auto-advance
POST /simulation/resume → Continue auto-advance
POST /simulation/step   → Single turn (when paused)
GET  /simulation/status → Current state
```

---

### Endpoint Specifications

---

### GET /state

Full game state for initial load or resync.

**Server Implementation:**
```python
@app.get("/state", response_model=APIGameState)
async def get_state():
    grid = get_map()

    # Get active encounter (if any)
    encounters = list(Encounter._encounter_registry.values())
    encounter = APIEncounter.create(encounters[0]) if encounters else None

    return APIGameState(
        grid=APIGrid.create(grid),
        entities=[APIEntitySummary.create(e) for e in Entity.get_all_entities()],
        encounter=encounter
    )
```

**Response:**
```json
{
  "grid": {
    "bounds": {"min_x": 0, "min_y": 0, "max_x": 15, "max_y": 15},
    "tiles": [
      {"x": 0, "y": 0, "walkable": true, "visible": true},
      ...
    ]
  },
  "entities": [
    {
      "uuid": "...",
      "name": "Goblin Scout",
      "position": [5, 7],
      "hp": 10,
      "max_hp": 10,
      "ac": 15,
      "conditions": ["Dodging"],
      "is_dead": false
    },
    ...
  ],
  "encounter": {
    "uuid": "...",
    "name": "Test Combat",
    "state": "active",
    "round_number": 2,
    "current_turn_index": 0,
    "current_entity_uuid": "...",
    "initiative_order": [
      {"uuid": "...", "name": "Goblin Scout", "initiative": 15, "is_dead": false},
      {"uuid": "...", "name": "Skeleton Warrior", "initiative": 12, "is_dead": false}
    ]
  }
}
```

### GET /entities

List all entities (lightweight).

**Server Implementation:**
```python
@app.get("/entities")
async def get_entities():
    return {"entities": [APIEntitySummary.create(e) for e in Entity.get_all_entities()]}
```

### GET /entity/{uuid}

Full details for one entity.

**Server Implementation:**
```python
@app.get("/entity/{entity_uuid}", response_model=APIEntityFull)
async def get_entity(entity_uuid: str):
    try:
        uuid_obj = UUID(entity_uuid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    entity = Entity.get(uuid_obj)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    return APIEntityFull.create(entity)
```

### GET /grid

Map/grid data.

**Server Implementation:**
```python
@app.get("/grid", response_model=APIGrid)
async def get_grid():
    return APIGrid.create(get_map())
```

### GET /encounter

Current encounter state (if any).

**Server Implementation:**
```python
@app.get("/encounter")
async def get_encounter():
    encounters = list(Encounter._encounter_registry.values())
    if not encounters:
        return {"active": False, "encounter": None}
    return {"active": True, "encounter": APIEncounter.create(encounters[0])}
```

---

## WebSocket Event Payloads

Events are already serialized by EventQueue. Key fields for UI:

### Movement Event
```json
{
  "type": "event",
  "event": {
    "event_type": "movement",
    "phase": "completion",
    "source_entity_uuid": "...",
    "start_position": [2, 7],
    "end_position": [5, 7],
    "path": [[2,7], [3,7], [4,7], [5,7]]
  }
}
```

### Attack Event
```json
{
  "type": "event",
  "event": {
    "event_type": "attack",
    "phase": "completion",
    "source_entity_uuid": "...",
    "target_entity_uuid": "...",
    "attack_outcome": "hit",
    "damage_rolls": [{"total": 7}],
    "status_message": "Goblin hits Skeleton for 7 damage"
  }
}
```

### Death Event
```json
{
  "type": "event",
  "event": {
    "event_type": "death",
    "phase": "completion",
    "entity_uuid": "...",
    "entity_name": "Skeleton Warrior",
    "final_hp": -4
  }
}
```

### Turn Start Event
```json
{
  "type": "event",
  "event": {
    "event_type": "turn_start",
    "phase": "completion",
    "entity_uuid": "...",
    "round_number": 2,
    "turn_index": 0,
    "actions_available": 1,
    "movement_available": 30
  }
}
```

---

## UI Components

### 1. GridView (Main Display)

- 2D grid rendered with CSS Grid or Canvas
- Each cell is a tile
- Entities displayed as emoji tokens on their positions
- Current turn entity highlighted (glowing border)
- Dead entities grayed out or marked with X

**Entity Tokens (Emojis):**
| Entity Type | Emoji | Dead |
|-------------|-------|------|
| Goblin | 👺 | 💀 |
| Skeleton | 💀 | ⚰️ |
| Generic | 🧙 | 💀 |

**Tile Colors:**
- Floor: light gray
- Wall: dark gray
- Entity position: colored based on team (green/red)

### 2. UnitPanels (Sidebar)

For each entity in encounter:
- Name + emoji
- HP bar (red when low)
- AC value
- Condition icons
- Initiative order number
- Highlight when it's their turn

```
┌─────────────────────┐
│ 👺 Goblin Scout     │
│ ████████░░ 8/10 HP  │
│ AC: 15  Init: 15    │
│ [🛡️ Dodging]        │
└─────────────────────┘
```

### 3. CombatLog (Bottom)

Scrolling log of events:
```
Round 2
  Goblin Scout's turn
  → Goblin Scout moves to (5, 7)
  → Goblin Scout attacks Skeleton Warrior
  → Hit! 7 slashing damage
  Skeleton Warrior's turn
  → Skeleton Warrior attacks Goblin Scout
  → Miss!
```

### 4. TurnIndicator (Top)

```
Round 2 | Goblin Scout's Turn | Actions: 1 | Movement: 30ft
```

---

## Client State Structure

```javascript
const state = {
  // Grid
  grid: {
    width: 16,
    height: 16,
    tiles: Map<"x,y", {walkable, visible}>
  },

  // Entities indexed by UUID
  entities: Map<uuid, {
    uuid, name, position, hp, maxHp, ac,
    conditions, isDead, emoji
  }>,

  // Encounter
  encounter: {
    active: true,
    roundNumber: 2,
    currentEntityUuid: "...",
    initiativeOrder: ["uuid1", "uuid2"]
  },

  // UI state
  ui: {
    selectedEntity: null,
    combatLog: []
  }
};
```

---

## Event Handling Logic

```javascript
function handleEvent(event) {
  const e = event.event;

  switch(e.event_type) {
    case 'movement':
      if (e.phase === 'completion') {
        updateEntityPosition(e.source_entity_uuid, e.end_position);
        animateMovement(e.source_entity_uuid, e.path);
        addToLog(`${getEntityName(e.source_entity_uuid)} moves to ${e.end_position}`);
      }
      break;

    case 'attack':
      if (e.phase === 'completion') {
        const damage = e.damage_rolls?.reduce((sum, r) => sum + r.total, 0) || 0;
        addToLog(`${getEntityName(e.source_entity_uuid)} attacks ${getEntityName(e.target_entity_uuid)}`);
        if (e.attack_outcome === 'hit' || e.attack_outcome === 'crit') {
          addToLog(`→ Hit! ${damage} damage`);
          // Fetch updated HP
          fetchEntity(e.target_entity_uuid);
        } else {
          addToLog(`→ Miss!`);
        }
      }
      break;

    case 'death':
      markEntityDead(e.entity_uuid);
      addToLog(`☠️ ${e.entity_name} has been defeated!`);
      break;

    case 'turn_start':
      setCurrentTurn(e.entity_uuid);
      state.encounter.roundNumber = e.round_number;
      addToLog(`--- ${getEntityName(e.entity_uuid)}'s turn ---`);
      break;

    case 'turn_end':
      clearCurrentTurn();
      break;

    case 'encounter_end':
      showVictoryScreen();
      break;
  }

  render();
}
```

---

## File Structure

```
server/
  event_server.py      # Add REST endpoints here

ui/
  index.html           # Main HTML file
  style.css            # Styling
  app.js               # Main application logic
  state.js             # State management
  renderer.js          # Rendering functions
  websocket.js         # WebSocket connection handling
```

Or single-file for simplicity:
```
ui/
  combat_viewer.html   # All-in-one HTML + CSS + JS
```

---

## Implementation Order

### Phase 1: Minimal Viewer (Read-Only)

1. **Server: REST endpoints**
   - GET /state
   - GET /entities
   - GET /entity/{uuid}
   - GET /grid
   - GET /encounter

2. **Client: Basic HTML**
   - Grid display (CSS grid, no canvas)
   - Entity tokens (emojis)
   - Simple combat log

3. **Client: WebSocket connection**
   - Connect on load
   - Handle movement events (update positions)
   - Handle attack events (log only)
   - Handle death events (mark dead)
   - Handle turn events (highlight current)

### Phase 2: Enhanced Visualization

4. **Movement animation**
   - Smooth transitions between positions
   - Path visualization

5. **HP/Status display**
   - Unit panels with HP bars
   - Condition icons

6. **Polish**
   - Better styling
   - Sound effects?
   - Attack animations?

### Phase 3: User Controller (Future)

7. **Server: Action endpoints**
   - POST /action/move
   - POST /action/attack
   - etc.

8. **Client: Interactive mode**
   - Click to select entity
   - Show available actions
   - Click to execute

---

## Open Questions

1. **Tile data**: Should we send all tiles or just bounds + walkable lookup?
   - For 16x16 = 256 tiles, sending all is fine
   - For larger maps, might want sparse format

2. **Event filtering**: Should client filter events or server?
   - Currently server supports filtering via WebSocket message
   - Probably keep filtering on client for flexibility

3. **Entity details in events**: How much to include?
   - Current events include UUIDs but not always names/HP
   - Options:
     a) Enrich events server-side (more bandwidth)
     b) Client fetches on demand (more requests)
     c) Client maintains cache, fetches on miss

4. **Multiple viewers**: Support multiple clients watching same combat?
   - Current WebSocket setup already supports this
   - Each client maintains own state

5. **Playback**: Should we support replaying past combats?
   - EventQueue stores all events
   - Could add GET /events/replay endpoint
   - Client could replay events in sequence

---

## Example: Minimal HTML Structure

```html
<!DOCTYPE html>
<html>
<head>
  <title>D&D Combat Viewer</title>
  <style>
    /* Grid */
    #grid {
      display: grid;
      grid-template-columns: repeat(var(--grid-width), 30px);
      gap: 1px;
      background: #333;
    }
    .tile {
      width: 30px;
      height: 30px;
      background: #eee;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
    }
    .tile.wall { background: #666; }
    .tile.has-entity { background: #cfc; }
    .tile.current-turn { box-shadow: 0 0 5px 2px gold; }

    /* Layout */
    #container { display: flex; gap: 20px; }
    #sidebar { width: 200px; }
    #log { height: 200px; overflow-y: auto; font-family: monospace; }
  </style>
</head>
<body>
  <h1>D&D Combat Viewer</h1>
  <div id="turn-indicator">Connecting...</div>

  <div id="container">
    <div id="grid"></div>
    <div id="sidebar">
      <h3>Combatants</h3>
      <div id="unit-panels"></div>
    </div>
  </div>

  <h3>Combat Log</h3>
  <div id="log"></div>

  <script>
    // State, WebSocket, rendering logic here
  </script>
</body>
</html>
```

---

## Summary

**Core Idea**: WebSocket for real-time event notifications, REST for full state queries. Client maintains local state and renders based on events.

**MVP Features**:
1. 2D grid with emoji tokens
2. WebSocket event streaming
3. Combat log
4. Basic unit info (HP, conditions)

**Future**: Interactive user controller via WebSocket commands.
