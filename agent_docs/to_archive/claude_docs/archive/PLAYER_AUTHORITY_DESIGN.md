# Player Authority System Design

> **IMPORTANT CONTEXT**: This document contains critical knowledge from debugging sessions. Read fully before implementing.

## Table of Contents
1. [Problem Statement](#problem-statement)
2. [Current Bugs Found](#current-bugs-found)
3. [Current Architecture (Broken)](#current-architecture-broken)
4. [API Field Mappings](#api-field-mappings)
5. [Design Goals](#design-goals)
6. [New Architecture](#new-architecture)
7. [Migration Path](#migration-path)

---

## Current Bugs Found

These bugs were discovered during PvP testing (January 2026):

### Bug 1: Turn Auto-Ends After Action
**Symptom**: After Claude moves or attacks, the turn switches to Hero even without calling end-turn.

**Root Cause**: State desync between:
- `sim.human_entity_uuid` (set once when turn starts)
- `sim.encounter.get_current_entity()` (actual turn state)

When agent CLI checks `is_my_turn()`, it uses encounter state. But `validate_human_action()` checks `sim.human_entity_uuid`. These can get out of sync.

**Error Message**: `{"detail": "Not this entity's turn"}`

### Bug 2: User CLI Doesn't Refresh During Opponent Turn
**Symptom**: User's CLI shows static display while Claude takes actions. Only updates when turn switches.

**Root Cause**: `wait_for_opponent_turn()` polls `/pvp/status` but doesn't receive action events. No event broadcasting system exists.

### Bug 3: Attack Display Shows Wrong Values
**Symptom**: `d20(0) +0 = 0 vs AC 0, Result: ???`

**Root Cause**: Agent CLI `cmd_attack` was reading wrong fields from API response. The response uses `event_data.d20`, `event_data.attack_bonus`, etc.

### Bug 4: Agent CLI Field Name Mismatches (FIXED)
Multiple field name bugs were fixed:
- `state.active_entity_uuid` → `state.encounter.current_entity_uuid`
- `state.round` → `state.encounter.round_number`
- `entity.current_hp` → `entity.hp`
- `entity.is_hero` → doesn't exist, check `entity.name == "Hero"`
- `attack.target_uuid` → `attack.valid_targets[0]`
- `other_actions` is a list, not a dict

---

## Current Architecture (Broken)

### Server State (`server/event_server.py`)

```python
class SimulationState:
    encounter: Optional[Encounter]
    paused: bool
    auto_run_ai: bool

    # Human turn tracking (PROBLEMATIC)
    waiting_for_human: bool
    human_entity_uuid: Optional[UUID]  # Set when human turn starts

    # PvP tracking (ADDED)
    pvp_mode: bool
    hero_uuid: Optional[UUID]
    opponent_uuid: Optional[UUID]

    # Agent tracking (ADDED)
    agent_connected: bool
    agent_last_ping: float
```

**Problem**: `human_entity_uuid` is set in `advance_encounter()` when a HumanController's turn starts, but:
1. It's only set once at turn start
2. If anything changes encounter state, they desync
3. Both hero and opponent use HumanController in PvP, causing confusion

### Validation Flow (Current - Broken)

```python
def validate_human_action(entity_uuid_str: str) -> Entity:
    # Check 1: Must be waiting for human
    if not sim.waiting_for_human:
        raise HTTPException(400, "Not waiting for human input")

    # Check 2: Must be the expected entity (PROBLEMATIC)
    if sim.human_entity_uuid != entity_uuid:
        raise HTTPException(403, "Not this entity's turn")

    # Check 3: Turn must be in progress
    if sim.encounter.turn_state != TurnState.IN_PROGRESS:
        raise HTTPException(400, "Turn not in progress")
```

### Turn Flow (Current)

```
1. advance_encounter() called
2. Loop through initiative order
3. For each entity:
   - Get controller via encounter.get_current_controller()
   - If controller.controller_type == "human":
     - Set sim.waiting_for_human = True
     - Set sim.human_entity_uuid = entity.uuid
     - Return and wait for API calls
   - Else (AI):
     - Run encounter.run_turn() automatically
     - Continue to next entity
```

### Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/state` | GET | Full game state (grid, entities, encounter) |
| `/pvp/status` | GET | PvP-specific status + agent connection |
| `/encounter/current-turn` | GET | Current turn info, action economy |
| `/entity/{uuid}/available-actions` | GET | What actions entity can take |
| `/action/move` | POST | Move entity to position |
| `/action/attack` | POST | Attack target |
| `/action/dash` | POST | Take Dash action |
| `/action/dodge` | POST | Take Dodge action |
| `/action/disengage` | POST | Take Disengage action |
| `/action/end-turn` | POST | End current turn |
| `/simulation/start-human` | POST | Start PvE game (human vs AI) |
| `/simulation/start-pvp` | POST | Start PvP game (human vs Claude) |
| `/agent/ping` | POST | Claude pings to show connected |

---

## API Field Mappings

### `/state` Response Structure
```json
{
  "grid": {
    "min_x": 0, "min_y": 0, "max_x": 14, "max_y": 14,
    "tiles": [{"x": 0, "y": 0, "walkable": true, "visible": true}, ...]
  },
  "entities": [
    {
      "uuid": "...",
      "name": "Hero",
      "position": [2, 7],
      "hp": 10,           // NOT current_hp
      "max_hp": 10,
      "ac": 15,
      "conditions": [],
      "is_dead": false
      // NOTE: NO is_hero field!
    }
  ],
  "encounter": {
    "uuid": "...",
    "name": "PvP Arena",
    "state": "active",
    "round_number": 1,           // NOT round
    "current_turn_index": 0,
    "current_entity_uuid": "...", // NOT at root level!
    "initiative_order": [...]
  }
}
```

### `/entity/{uuid}/available-actions` Response
```json
{
  "entity_uuid": "...",
  "can_move": true,
  "remaining_movement": 30,
  "valid_positions": [],  // Often empty due to senses not updating
  "attacks": [
    {
      "action_id": "attack_main_hand",
      "name": "Attack (Shortsword)",
      "description": "1d6 Piercing",
      "cost_type": "actions",
      "cost_amount": 1,
      "can_afford": true,
      "valid_targets": ["target-uuid-here"],  // NOT target_uuid
      "weapon_slot": "MAIN_HAND"
    }
  ],
  "other_actions": [  // This is a LIST not dict
    {
      "action_id": "dash",
      "name": "Dash",
      "can_afford": true,
      ...
    }
  ]
}
```

### `/action/attack` Response
```json
{
  "success": true,
  "message": "Attack executed",
  "event_type": "attack",
  "event_data": {
    "attacker": "Skeleton",
    "target": "Hero",
    "weapon": "Shortsword",
    "d20": 15,
    "all_d20_rolls": [15],
    "advantage_status": "none",
    "attack_bonus": 4,
    "attack_total": 19,
    "target_ac": 15,
    "outcome": "Hit",
    "damage_rolls": [{"dice": [4], "bonus": 2, "total": 6}],
    "total_damage": 6
  },
  "entity_hp": 17,
  "target_hp": 4,
  "deaths": [],
  "turn_continues": true,
  "encounter_ended": false
}
```

---

## CLI File Structure

### User CLI (`cli/`)
```
cli/
├── __main__.py      # Entry point: python -m cli
├── api_client.py    # APIClient class - HTTP calls to server
├── commands.py      # parse_command(), execute_command()
├── display.py       # Rich-based ASCII map rendering
├── main.py          # Typer app, game_loop(), play/playpvp commands
└── agent.py         # Non-interactive CLI for Claude
```

### Agent CLI Commands (`cli/agent.py`)
```bash
python -m cli.agent state      # Show board + whose turn
python -m cli.agent actions    # Show available actions
python -m cli.agent move X Y   # Move to position
python -m cli.agent attack N   # Attack target by index
python -m cli.agent dash       # Take Dash
python -m cli.agent dodge      # Take Dodge
python -m cli.agent disengage  # Take Disengage
python -m cli.agent end        # End turn
python -m cli.agent ping       # Check if my turn
python -m cli.agent connect    # Loop and wait for turn
python -m cli.agent start-pvp  # Start new PvP game
```

### Agent CLI Key Functions
```python
def get_my_entity(client):
    """Returns entity where name == 'Skeleton'"""

def is_my_turn(client):
    """Checks encounter.current_entity_uuid == my_entity.uuid"""

def validate_my_turn(client):
    """Pings server + checks is_my_turn, returns entity_uuid or None"""
```

---

## Problem Statement

The current implementation has multiple issues:
1. **Duplicate state tracking** - `sim.human_entity_uuid` vs `encounter.current_entity_uuid`
2. **Hardcoded player types** - "human" vs "AI" baked into validation logic
3. **No session concept** - Can't track multiple connected clients
4. **Race conditions** - Multiple sources of truth lead to state desync
5. **Not extensible** - Adding multiplayer or multiple Claudes requires rewrites

---

## New Architecture

### Design Goals

1. **Server is authoritative** - Single source of truth for all game state
2. **Clean player abstraction** - Human, Claude, AI are all "players" with different connection types
3. **Entity ownership** - Clear mapping of player → entities they control
4. **Turn-based validation** - Simple check: "Does this player own the active entity?"
5. **Multiplayer ready** - Support N players controlling M entities
6. **Observable** - Other players can see actions as they happen

### Core Concepts

### Player
A connected client that can control entities. Has a session and connection type.

```python
class PlayerSession:
    session_id: UUID           # Unique session identifier
    player_type: PlayerType    # HUMAN, CLAUDE, AI
    connection_status: ConnectionStatus  # CONNECTED, DISCONNECTED, WAITING
    last_activity: float       # Timestamp for timeout detection
    controlled_entities: Set[UUID]  # Entities this player can control
```

### PlayerType
```python
class PlayerType(str, Enum):
    HUMAN = "human"      # User via CLI
    CLAUDE = "claude"    # Claude via agent CLI
    AI = "ai"            # Built-in AI (MeleeAIController etc)
```

### Connection Status
```python
class ConnectionStatus(str, Enum):
    CONNECTED = "connected"       # Active, responding to pings
    DISCONNECTED = "disconnected" # Timed out or explicitly disconnected
    WAITING = "waiting"           # Turn started, waiting for action
```

## Server State

Replace scattered `sim.*` variables with a clean `GameSession`:

```python
class GameSession:
    # Game identification
    session_id: UUID
    encounter: Encounter

    # Player management
    players: Dict[UUID, PlayerSession]  # session_id -> PlayerSession
    entity_to_player: Dict[UUID, UUID]  # entity_uuid -> session_id (owner)

    # Turn state (derived from encounter, not duplicated)
    @property
    def active_entity_uuid(self) -> Optional[UUID]:
        return self.encounter.get_current_entity().uuid if self.encounter else None

    @property
    def active_player(self) -> Optional[PlayerSession]:
        entity_uuid = self.active_entity_uuid
        if entity_uuid and entity_uuid in self.entity_to_player:
            player_id = self.entity_to_player[entity_uuid]
            return self.players.get(player_id)
        return None
```

## API Design

### Session Management

```
POST /session/create
  Request: { player_type: "human" | "claude", entities?: [uuid] }
  Response: { session_id, player_type, controlled_entities }

POST /session/{session_id}/ping
  Response: { status, is_my_turn, active_entity }

DELETE /session/{session_id}
  Disconnects the session
```

### Game Setup

```
POST /game/create
  Request: { mode: "pvp" | "pve", players: [...] }
  Response: { game_id, players, entities, first_turn }

POST /game/{game_id}/join
  Request: { session_id, entities_to_control: [uuid] }
  Response: { success, your_entities }
```

### Actions (Unified)

All actions use the same pattern - session_id identifies who's acting:

```
POST /action/move
  Request: { session_id, entity_uuid, position: [x, y] }

POST /action/attack
  Request: { session_id, entity_uuid, target_uuid, weapon_slot? }

POST /action/end-turn
  Request: { session_id, entity_uuid }
```

### Validation Flow

```python
def validate_action(session_id: UUID, entity_uuid: UUID) -> Entity:
    """
    Unified validation for all actions.

    Checks:
    1. Session exists and is connected
    2. Session owns the entity
    3. Entity is the active entity (it's their turn)
    4. Turn is in progress
    """
    # Get session
    session = game.players.get(session_id)
    if not session:
        raise HTTPException(401, "Invalid session")

    if session.connection_status == ConnectionStatus.DISCONNECTED:
        raise HTTPException(401, "Session disconnected")

    # Check entity ownership
    if entity_uuid not in session.controlled_entities:
        raise HTTPException(403, "You don't control this entity")

    # Check it's their turn
    if entity_uuid != game.active_entity_uuid:
        raise HTTPException(403, "Not this entity's turn")

    # Check turn state
    if game.encounter.turn_state != TurnState.IN_PROGRESS:
        raise HTTPException(400, "Turn not in progress")

    return Entity.get(entity_uuid)
```

## Turn Flow

### Turn Start
```
1. Encounter advances to next entity
2. Server looks up entity owner: player = entity_to_player[entity_uuid]
3. Server sets player.connection_status = WAITING
4. If player.type == AI:
     - Server runs AI logic automatically
     - Actions are recorded and broadcast
   Else:
     - Server waits for player to take actions via API
```

### During Turn
```
1. Player sends action request with session_id
2. Server validates via validate_action()
3. Action executes
4. Event is broadcast to all connected sessions
5. Response includes: success, event_data, turn_continues
```

### Turn End
```
1. Player sends end-turn request (or turn auto-ends for AI)
2. Server validates it's their turn
3. Encounter.end_turn() is called
4. Server advances to next turn (goto Turn Start)
```

## Multiplayer Support

The design naturally supports multiplayer:

```python
# 2v2 PvP Example
game = GameSession(
    players={
        player1.session_id: PlayerSession(type=HUMAN, entities={hero1}),
        player2.session_id: PlayerSession(type=HUMAN, entities={hero2}),
        claude1.session_id: PlayerSession(type=CLAUDE, entities={skeleton1}),
        claude2.session_id: PlayerSession(type=CLAUDE, entities={skeleton2}),
    },
    entity_to_player={
        hero1.uuid: player1.session_id,
        hero2.uuid: player2.session_id,
        skeleton1.uuid: claude1.session_id,
        skeleton2.uuid: claude2.session_id,
    }
)
```

## Event Broadcasting

When any action occurs, broadcast to all players:

```python
class ActionBroadcast:
    event_type: str           # "move", "attack", "end_turn"
    actor_entity: UUID        # Who acted
    actor_session: UUID       # Which player
    event_data: dict          # Action-specific data
    timestamp: float

# All connected sessions receive broadcasts
async def broadcast_action(action: ActionBroadcast):
    for session in game.players.values():
        if session.connection_status == ConnectionStatus.CONNECTED:
            await session.send(action)
```

## CLI Changes

### User CLI
```python
# On start
session = api.create_session(player_type="human")
game = api.join_game(session.session_id, entities=[hero_uuid])

# Game loop
while True:
    status = api.ping(session.session_id)
    if status.is_my_turn:
        # Take actions
        api.move(session.session_id, hero_uuid, position)
    else:
        # Poll for updates, show opponent actions
        events = api.get_events_since(last_event_id)
        display_events(events)
```

### Agent CLI
```python
# On connect
session = api.create_session(player_type="claude")
# Session auto-joins existing game as opponent

# Commands
def cmd_state():
    status = api.ping(session.session_id)
    # Show board, indicate if my turn

def cmd_move(x, y):
    result = api.move(session.session_id, my_entity_uuid, [x, y])
    # Show result
```

## Migration Path

1. **Phase 1**: Add PlayerSession and GameSession classes
2. **Phase 2**: Update action endpoints to use new validation
3. **Phase 3**: Add session management endpoints
4. **Phase 4**: Update CLIs to use sessions
5. **Phase 5**: Remove old sim.* state variables
6. **Phase 6**: Add event broadcasting for live updates

## Benefits

1. **Single source of truth** - No duplicate turn tracking
2. **Clean validation** - One function validates all actions
3. **Extensible** - Add new player types easily
4. **Multiplayer ready** - N players, M entities, any combination
5. **Observable** - All players see all actions in real-time
6. **Testable** - Session-based API is easy to test

## File Structure

```
server/
├── session.py          # PlayerSession, GameSession, SessionManager
├── validation.py       # validate_action() and related
├── event_server.py     # Updated endpoints using sessions
├── broadcast.py        # Event broadcasting to connected clients
└── api_models.py       # Updated request/response models

cli/
├── session_client.py   # Session-aware API client
├── main.py             # Updated to use sessions
└── agent.py            # Updated to use sessions
```

---

## Implementation Notes

### Running the System

```bash
# Terminal 1: Start server
source .venv/bin/activate
python -m server.event_server --force

# Terminal 2: User CLI (PvP mode)
source .venv/bin/activate
python -m cli playpvp

# Terminal 3: Claude agent CLI (in Claude Code session)
source .venv/bin/activate && python -m cli.agent connect
```

### Key Classes in dnd/

| File | Key Classes | Purpose |
|------|-------------|---------|
| `entity.py` | `Entity` | Main game object with all blocks |
| `encounter.py` | `Encounter`, `CombatantState` | Turn-based combat management |
| `controller.py` | `Controller`, `HumanController` | Player control abstraction |
| `actions.py` | `Move`, `Attack`, `Dash`, `Dodge`, `Disengage` | Game actions |
| `available_actions.py` | `get_available_actions()` | Query what entity can do |
| `reactions.py` | `add_opportunity_attack_handler()` | Opportunity attacks |

### Encounter Turn State Machine

```
EncounterState: NOT_STARTED -> ACTIVE -> ENDED

TurnState: NOT_STARTED -> IN_PROGRESS -> ENDED
```

Turn lifecycle:
1. `encounter.start_turn()` - Sets TurnState.IN_PROGRESS, resets action economy
2. Player takes actions via API
3. `encounter.end_turn()` - Sets TurnState.ENDED, advances conditions
4. `encounter.next_turn()` or manual index advance

### Action Economy (per turn)

```python
entity.action_economy:
    actions: 1          # Standard actions (Attack, Dash, Dodge, Disengage)
    bonus_actions: 1    # Bonus actions
    reactions: 1        # Reactions (Opportunity Attack)
    movement: 30        # Feet of movement (typical)
```

Actions consume from economy:
- Move: consumes movement (5ft per square)
- Attack: consumes 1 action
- Dash: consumes 1 action, adds base_speed to movement
- Dodge: consumes 1 action, applies Dodging condition
- Disengage: consumes 1 action, applies Disengaging condition

### Dice Rolling with Advantage/Disadvantage

The `dnd/core/dice.py` was fixed to roll 2 dice for advantage/disadvantage:
```python
def _roll_with_advantage(self) -> Tuple[int, List[int]]:
    rolls = [random.randint(1, self.value) for _ in range(2)]
    return max(rolls), rolls  # Return (selected, all_rolls)

def _roll_with_disadvantage(self) -> Tuple[int, List[int]]:
    rolls = [random.randint(1, self.value) for _ in range(2)]
    return min(rolls), rolls
```

`DiceRoll.results` contains ALL dice rolled (both for adv/dis).
`DiceRoll.advantage_status` is an enum: `AdvantageStatus.ADVANTAGE`, `.DISADVANTAGE`, `.NONE`

**Important**: The enum value is capitalized (`"Advantage"` not `"advantage"`), use `.lower()` for comparisons.

### Entity Senses

```python
entity.update_entity_senses(max_distance=20)  # Updates visibility, paths
Entity.update_all_entities_senses()            # Updates all entities

entity.senses.entities      # Dict[UUID, position] - visible entities
entity.senses.visible       # Dict[position, bool] - visible cells
entity.senses.paths         # Dict[position, List[position]] - paths to cells
```

**Bug**: `valid_positions` in available_actions is often empty because senses aren't updated. Move still works because it computes path at execution time.

### Conditions System

Conditions add modifiers to entities:
- `Dodging`: Attackers have disadvantage (via `to_target_static`)
- `Disengaging`: No opportunity attacks when moving
- `Dashing`: Extra movement equal to base speed

Apply: `entity.add_condition(condition)`
Remove: `entity.remove_condition("ConditionName")`

---

## Testing Commands

```bash
# Verify dice rolling
python examples/test_dodging_attack.py

# Basic combat
python examples/combat_basic.py

# Condition effects
python examples/combat_conditions.py

# Available actions
python examples/test_available_actions.py
```

---

## Debug Checklist

When debugging PvP issues:

1. **Check server is running**: `curl http://localhost:8000/`
2. **Check game state**: `curl http://localhost:8000/state | python -m json.tool`
3. **Check whose turn**: `curl http://localhost:8000/pvp/status`
4. **Check available actions**: `curl http://localhost:8000/entity/{uuid}/available-actions`

Common issues:
- **"Not waiting for human input"**: `sim.waiting_for_human` is False
- **"Not this entity's turn"**: `sim.human_entity_uuid` doesn't match
- **"Turn not in progress"**: `encounter.turn_state != IN_PROGRESS`

---

## Summary of Changes Needed

1. **Create `server/session.py`**: PlayerSession, GameSession classes
2. **Update `server/event_server.py`**:
   - Replace `sim.*` state with GameSession
   - Update all action endpoints to use session-based validation
   - Add session management endpoints
3. **Update `cli/api_client.py`**: Add session support
4. **Update `cli/main.py`**: Create session on start, pass to all calls
5. **Update `cli/agent.py`**: Create session on connect, use for all calls
6. **Add event broadcasting**: WebSocket or polling for real-time updates
