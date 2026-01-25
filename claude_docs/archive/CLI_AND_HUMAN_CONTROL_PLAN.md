# CLI and Human Control Implementation Plan

## Overview

Build a nethack-style CLI for human-controlled combat, backed by REST API endpoints for action execution.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI (cli/)                          │
│  - ASCII map display                                        │
│  - Status bars                                              │
│  - Combat log                                               │
│  - Command input                                            │
│  - Polls API for state, POSTs actions                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP (localhost)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Server (server/)                         │
│  GET  /encounter           - Current state + whose turn     │
│  GET  /entity/{uuid}/available-actions                      │
│  POST /action/move         - Execute move                   │
│  POST /action/attack       - Execute attack                 │
│  POST /action/dash|dodge|disengage                          │
│  POST /action/end-turn     - End turn, advance              │
│  WS   /ws                  - Combat log stream (display)    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Engine (dnd/)                            │
│  Encounter, Entity, Actions, etc.                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: API Endpoints for Human Control

### New Endpoints Needed

| Endpoint | Method | Purpose | Request Body |
|----------|--------|---------|--------------|
| `/encounter/current-turn` | GET | Who's turn, is it human? | - |
| `/entity/{uuid}/available-actions` | GET | All possible actions | - |
| `/action/move` | POST | Execute move | `{entity_uuid, position: [x,y]}` |
| `/action/attack` | POST | Execute attack | `{entity_uuid, target_uuid, weapon_slot}` |
| `/action/dash` | POST | Execute dash | `{entity_uuid}` |
| `/action/dodge` | POST | Execute dodge | `{entity_uuid}` |
| `/action/disengage` | POST | Execute disengage | `{entity_uuid}` |
| `/action/end-turn` | POST | End turn, advance | `{entity_uuid}` |

### Server State Changes

```python
class SimulationState:
    encounter: Optional[Encounter] = None
    paused: bool = True
    auto_run_ai: bool = True  # Auto-advance through AI turns

    # Human turn tracking
    waiting_for_human: bool = False
    human_entity_uuid: Optional[UUID] = None
```

### HumanController Class

```python
class HumanController(Controller):
    """Controller for human-controlled entities."""
    name: str = "Human Player"
    controller_type: str = "human"

    def get_next_action(self, entity, context) -> Optional[BaseAction]:
        return None  # Actions come via API

    def can_continue_turn(self, entity, context) -> bool:
        return False  # Exit run_turn loop immediately
```

### Turn Flow Logic

```python
async def advance_encounter():
    """Advance encounter, auto-run AI, stop on human."""
    while sim.encounter.state == EncounterState.ACTIVE:
        controller = sim.encounter.get_current_controller()

        if controller.controller_type == "human":
            # Start human turn and wait
            if sim.encounter.turn_state != TurnState.IN_PROGRESS:
                sim.encounter.start_turn()
            sim.waiting_for_human = True
            sim.human_entity_uuid = sim.encounter.initiative_order[sim.encounter.current_turn_index]
            return  # Stop here, wait for API calls

        else:
            # AI turn - run completely
            sim.encounter.run_turn()
            if not sim.auto_run_ai:
                return  # Manual stepping mode
```

### Validation for Action Endpoints

```python
def validate_human_action(entity_uuid: UUID) -> Entity:
    """Validate it's this human's turn and return entity."""
    if not sim.waiting_for_human:
        raise HTTPException(400, "Not waiting for human input")
    if sim.human_entity_uuid != entity_uuid:
        raise HTTPException(403, "Not this entity's turn")
    entity = Entity.get(entity_uuid)
    if not entity:
        raise HTTPException(404, "Entity not found")
    return entity
```

---

## Phase 2: CLI Structure

### Files

```
cli/
├── __init__.py
├── main.py           # Entry point, main loop
├── api_client.py     # HTTP client for server communication
├── display.py        # ASCII rendering with rich
├── commands.py       # Command parsing and execution
└── config.py         # Server URL, display settings
```

### Dependencies

```
rich              # Terminal formatting, tables, panels
httpx             # HTTP client (sync)
```

### Main Loop

```python
def main():
    client = APIClient(base_url="http://localhost:8000")
    display = Display()

    # Start/reset encounter
    client.post("/simulation/reset")
    client.post("/simulation/resume")  # This advances to first turn

    while True:
        # Get current state
        state = client.get("/state")
        turn_info = client.get("/encounter/current-turn")

        # Render display
        display.clear()
        display.draw_map(state)
        display.draw_entities(state)
        display.draw_combat_log()
        display.draw_status(turn_info)

        if turn_info["waiting_for_human"]:
            # Human turn - show actions and get command
            entity_uuid = turn_info["entity_uuid"]
            available = client.get(f"/entity/{entity_uuid}/available-actions")
            display.draw_available_actions(available)

            command = display.prompt_command()
            result = execute_command(client, command, entity_uuid, available)
            display.show_result(result)
        else:
            # AI turn or encounter ended
            if state["encounter"]["state"] == "ended":
                display.show_encounter_end()
                break
            time.sleep(0.3)  # Brief pause to see AI actions
```

---

## Phase 3: CLI Display

### Map Rendering

```
  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4
 ┌─────────────────────────────┐
0│. . . . . . . . . . . . . . .│
1│. . . . . . . . . . . . . . .│
2│. . . . . . . . . . . . . . .│
3│. . . . . . . . . . . . . . .│
4│. . . . . . . . . . . . . . .│
5│. . . . . @ . . . . . . . . .│   @ = You (Goblin Scout)
6│. . . . . . . . . . . . . . .│   S = Skeleton Warrior
7│. . . . . . . . S . . . . . .│
8│. . . . . . . . . . . . . . .│
 └─────────────────────────────┘
```

### Symbols

| Symbol | Meaning |
|--------|---------|
| `.` | Floor |
| `#` | Wall |
| `~` | Water |
| `@` | Human-controlled entity |
| `A-Z` | AI entities (first letter of name) |
| `*` | Valid move position (when selecting) |

### Status Display

```
┌─ Goblin Scout (YOUR TURN) ─────────────────────────────────┐
│ HP: 7/10    AC: 15    Position: (5, 5)                     │
│ Actions: 1  Bonus: 1  Movement: 30ft  Reaction: 1          │
└────────────────────────────────────────────────────────────┘

┌─ Skeleton Warrior ─────────────────────────────────────────┐
│ HP: 13/13   AC: 13    Position: (8, 7)    Distance: 20ft   │
└────────────────────────────────────────────────────────────┘
```

---

## Phase 4: Command System

### Command Format

```
> command [args...]
```

### Commands

| Command | Args | Description |
|---------|------|-------------|
| `move X Y` | position | Move to position |
| `move` | - | List valid move positions |
| `attack N` | target number | Attack target from list |
| `attack` | - | List valid attack targets |
| `dash` | - | Take Dash action |
| `dodge` | - | Take Dodge action |
| `disengage` | - | Take Disengage action |
| `end` | - | End turn |
| `status` | - | Show detailed status |
| `actions` | - | List ALL available actions |
| `help` | - | Show help |
| `quit` | - | Exit game |

### Action Listing (from available_actions)

```
> actions

ATTACKS (1 action):
  [1] Scimitar vs Skeleton Warrior (20ft) - can afford: YES
  [2] Unarmed vs Skeleton Warrior (20ft) - can afford: YES

MOVEMENT (free, 30ft remaining):
  Valid positions: 119 tiles
  Type 'move' to see positions or 'move X Y' to move

OTHER ACTIONS (1 action each):
  [d] Dash - double movement
  [o] Dodge - disadvantage on attacks against you
  [i] Disengage - no opportunity attacks

FREE ACTIONS:
  [p] Drop Prone

> attack 1
Rolling attack... 18 + 4 = 22 vs AC 13... HIT!
Damage: 1d6+2 = 5 slashing
Skeleton Warrior takes 5 damage (8/13 HP remaining)
```

### Move Position Selection

```
> move

Valid move positions (30ft remaining):
Showing positions within 6 tiles...

  0 1 2 3 4 5 6 7 8 9 0
 ┌─────────────────────┐
3│. . . * * * * * . . .│
4│. . * * * * * * * . .│
5│. . * * * @ * * * . .│
6│. . * * * * * * * . .│
7│. . . * * * * * . . .│
 └─────────────────────┘

Enter position: move 7 5
Moving from (5, 5) to (7, 5)... 10ft movement used.
```

---

## Implementation Order

### Step 1: API Updates (server/event_server.py) - COMPLETE

- [x] Add HumanController to controller.py
- [x] Add `/encounter/current-turn` endpoint
- [x] Add `/entity/{uuid}/available-actions` endpoint
- [x] Add action endpoints: move, attack, dash, dodge, disengage, end-turn
- [x] Add `advance_encounter()` logic for human/AI turn handling
- [x] Add request body models (Pydantic)
- [x] Test endpoints with test_human_control.py

**Files modified:**
- `dnd/controller.py` - Added HumanController class
- `server/api_models.py` - Added APICurrentTurn, MoveRequest, AttackRequest, SimpleActionRequest, ActionResult
- `server/event_server.py` - Added all human control endpoints and advance_encounter() logic
- `server/test_human_control.py` - Integration test for human control flow

**New endpoints:**
```
POST /simulation/start-human     - Start combat with human control
GET  /encounter/current-turn     - Get whose turn it is
GET  /entity/{uuid}/available-actions
POST /action/move                - {entity_uuid, position: [x, y]}
POST /action/attack              - {entity_uuid, target_uuid, weapon_slot}
POST /action/dash                - {entity_uuid}
POST /action/dodge               - {entity_uuid}
POST /action/disengage           - {entity_uuid}
POST /action/end-turn            - {entity_uuid}
```

### Step 2: CLI Foundation (cli/) - COMPLETE
- [x] Create cli/ folder structure
- [x] Implement api_client.py (httpx wrapper)
- [x] Implement basic display.py (map rendering with rich)
- [x] Implement main loop skeleton (main.py with Typer)

**Files created:**
- `cli/__init__.py` - Package init
- `cli/__main__.py` - Entry point for `python -m cli`
- `cli/api_client.py` - HTTP client wrapper for server communication
- `cli/display.py` - ASCII map rendering with Rich
- `cli/commands.py` - Command parsing and execution
- `cli/main.py` - Main game loop with Typer CLI entry

### Step 3: CLI Commands - COMPLETE
- [x] Implement command parser
- [x] Implement `actions` command (list all)
- [x] Implement `move` command (with position picker)
- [x] Implement `attack` command (with target picker)
- [x] Implement other action commands (dash, dodge, disengage)
- [x] Implement `end` command

### Step 4: Polish - COMPLETE
- [x] Combat log display
- [x] Color coding (entities, HP bars)
- [x] Error handling and user feedback
- [x] Help command

**Usage:**
```bash
# Start server first
python -m server.event_server

# In another terminal, start CLI
python -m cli play
python -m cli play --host localhost --port 8000
python -m cli status  # Check server status
```

---

## Testing Strategy

1. **API Testing**: Use httpie/curl to test each endpoint manually
2. **CLI Testing**: Manual testing with server running
3. **Integration**: Full combat from CLI start to finish

---

## Open Questions

1. **Encounter setup via CLI?** Or always through API/preset?
2. **Save/load game state?** Future feature?
3. **Multiple combats?** Switch between encounters?

---

## Notes

- Server runs separately: `python -m server.event_server`
- CLI connects to server: `python -m cli play`
- WebSocket is display-only (combat log), all control via REST
- Start simple: 1 human entity, 1 AI entity, basic arena

## Dependencies Added

```
rich    # Terminal formatting, tables, panels
typer   # CLI framework (integrates with Pydantic)
httpx   # HTTP client (already present)
```
