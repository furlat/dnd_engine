# CLI and Server Architecture

## Overview

The D&D Engine uses a terminal-based CLI for gameplay. Two CLIs are provided:
- **Human CLI** (`cli/main.py`): Rich terminal interface for human players
- **Agent CLI** (`cli/agent.py`): Simple command interface for Claude to play as opponent

Both connect to a FastAPI server that manages game state, sessions, and combat.

---

## Game Modes

### Human vs AI (`python -m cli play`)

Human controls Hero, AI controls Skeleton. Server auto-runs AI turns.

### Human vs Claude PvP (`python -m cli playpvp`)

Human controls Hero via CLI, Claude controls Skeleton via agent CLI. Both players take turns through session-authenticated actions.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         SERVER                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────────────┐ │
│  │  Encounter  │    │SessionManager│   │   Combat Log         │ │
│  │  (combat)   │    │ (auth)      │    │   (unified)          │ │
│  └─────────────┘    └─────────────┘    └──────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    REST Endpoints                          │ │
│  │  GET  /state           - full game state                   │ │
│  │  GET  /combat-log      - unified combat log                │ │
│  │  GET  /pvp/status      - whose turn, who's connected       │ │
│  │  POST /session/create  - create player session             │ │
│  │  POST /game/join       - join with session                 │ │
│  │  POST /action/move     - move (requires session)           │ │
│  │  POST /action/attack   - attack (requires session)         │ │
│  │  POST /action/dash     - dash action                       │ │
│  │  POST /action/dodge    - dodge action                      │ │
│  │  POST /action/disengage - disengage action                 │ │
│  │  POST /action/end-turn - end turn (requires session)       │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                    │ HTTP
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                     HUMAN CLI (cli/main.py)                      │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────────────┐ │
│  │  APIClient  │    │  GameState  │    │   Display (Rich)     │ │
│  │  (HTTP)     │    │  (local)    │    │   - Header           │ │
│  └─────────────┘    └─────────────┘    │   - Battlefield      │ │
│                                         │   - Combatants       │ │
│  ┌────────────────────────────────────┐│   - Combat Log       │ │
│  │  wait_for_opponent_turn()         ││   - Output           │ │
│  │  - Polls /combat-log              ││   - Actions          │ │
│  │  - Polls /pvp/status              │└──────────────────────┘ │
│  │  - Shows rich opponent actions    │                         │
│  └────────────────────────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   AGENT CLI (cli/agent.py)                       │
│  Simple command-based interface for Claude:                      │
│  - connect     Create session, join game                         │
│  - disconnect  Clear session for new game                        │
│  - watch       Wait for turn, show opponent actions (BLOCKING)   │
│  - state       Show map and entities                             │
│  - actions     Show available actions                            │
│  - move X Y    Move to position                                  │
│  - attack N    Attack target by index                            │
│  - dash        Dash action (double movement)                     │
│  - dodge       Dodge action (attackers have disadvantage)        │
│  - disengage   Disengage action (no opportunity attacks)         │
│  - end         End turn                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Session-Based Authority

PvP mode uses session authentication to ensure only the correct player can control their entity on their turn.

### Flow

```
1. Client: POST /session/create {player_type: "human"|"claude"}
   Server: Returns session_id

2. Client: POST /game/join {session_id, entity_uuids?}
   Server: Assigns entities to session, returns controlled_entities

3. Client: POST /action/attack {session_id, entity_uuid, target_uuid}
   Server: Validates session owns entity, it's their turn, executes action
```

### Session Validation (server/session.py)

```python
def validate_action(session_id, entity_uuid):
    # 1. Session exists and is connected
    # 2. Session owns the entity
    # 3. Entity is the active entity (their turn)
    # 4. Turn is in progress
```

---

## Server-Side Combat Log

The server maintains a unified combat log that both players write to. This ensures consistency and provides rich action details.

### Entry Structure

```python
{
    "index": 5,
    "type": "attack",  # attack, move, action, opportunity_attack, death, turn_end
    "message": "Skeleton hits Hero. d20(17)+4=21 vs AC 15 → 8 damage",
    "details": {
        "attacker": "Skeleton",
        "target": "Hero",
        "weapon": "Shortsword",
        "d20": 17,
        "all_d20_rolls": [17],
        "advantage_status": "none",
        "attack_bonus": 4,
        "attack_total": 21,
        "target_ac": 15,
        "outcome": "hit",
        "total_damage": 8,
        "target_hp": 2
    }
}
```

### Polling

```python
# Client polls for new entries
response = client.get("/combat-log", params={"since": last_index})
for entry in response["entries"]:
    display.show_opponent_action(entry)  # Rich formatted display
    last_index = entry["index"] + 1
```

---

## Display Layout (cli/display.py)

The Human CLI uses a full-screen TUI with Rich panels:

### Panel Order (top to bottom)

1. **Header Panel** - "NEURODRAGON" branding + connection status
   - PvP Mode: Shows Hero/Claude connection status (● Connected / ○ Waiting)
   - Solo Mode: Shows "Human vs AI"

2. **Battlefield Panel** - ASCII map with entities
   - `@` = You (green)
   - First letter = Enemies (red)
   - `#` = Walls
   - `*` = Valid move positions (yellow)
   - `+` = Movement path (magenta)

3. **Combatants Panel** - Entity table with turn info in title
   - Title: "Round X │ EntityName │ YOUR TURN" or "OPPONENT"
   - Shows HP, AC, Position, Conditions
   - `►` marker on active entity

4. **Combat Log Panel** - Rich formatted action history
   - Attacks show: attacker → target, roll details, outcome, damage
   - Moves show: entity moved from→to
   - Color-coded by action type

5. **Output Panel** (conditional) - Command feedback
   - Shows valid move positions when `m` typed without coords
   - Shows attack targets when `a` typed without target
   - Shows error messages

6. **Available Actions Panel** (your turn only) - Action hints
   - Title shows action economy: "Actions:1 Bonus:1 Move:30ft React:1"
   - Lists available MOVE, ATTACK, DASH, DODGE, DISENGAGE, END

### Example Display

```
╔════════════════════════ ⚔ NEURODRAGON ⚔ ════════════════════════╗
║ PvP Mode  │  Hero: ● Connected  │  Claude: ● Connected          ║
╚═════════════════════════════════════════════════════════════════╝

╭──────────────────────── Battlefield ────────────────────────────╮
│    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4                                │
│   +-------------------------------+                             │
│  7| . . @ . . . # . . . . . S . . |                             │
│   +-------------------------------+                             │
│ @ You  S Enemy  # Wall  + Path  * Valid                         │
╰─────────────────────────────────────────────────────────────────╯

╭─────────── Round 1 │ Hero │ YOUR TURN ───────────╮
│ Entity     HP      AC   Pos      Conditions      │
│ ► Hero     10/10   15   (2,7)    none            │
│   Skeleton 17/17   13   (12,7)   none            │
╰──────────────────────────────────────────────────╯

╭───────────────────── Combat Log ─────────────────────╮
│ Hero → Skeleton d20(14)+4=18 vs AC 13 HIT 7dmg      │
│ Skeleton → Hero d20(17)+4=21 vs AC 15 HIT 8dmg      │
╰──────────────────────────────────────────────────────╯

╭──────── Actions:1 Bonus:1 Move:30ft React:1 ─────────╮
│ MOVE (30ft)  [m X Y] or [m] to show positions        │
│ ATTACK Scimitar  [a 0] targets: Skeleton             │
│ DASH [d]  DODGE [o]  DISENGAGE [i]                   │
│ END [e]  HELP [?]  QUIT [q]                          │
╰──────────────────────────────────────────────────────╯
```

---

## Agent CLI: The `watch` Command

The `watch` command is the primary way Claude stays engaged with the game:

```bash
python -m cli.agent watch
```

Behavior:
1. Polls server every 2 seconds
2. Shows opponent actions from combat log as they happen (attacks, moves, deaths)
3. When it becomes Claude's turn, displays full state + available actions
4. Detects encounter end and exits cleanly
5. Ctrl+C to interrupt manually

This enables a smooth flow: `connect` → `watch` → take actions → `end` → `watch` → repeat

### Session Persistence

The agent CLI stores session info in `/tmp/dnd_agent_session.txt` so session persists between commands:

```bash
# First command creates session
python -m cli.agent connect    # Creates session, saves to file

# Subsequent commands load session automatically
python -m cli.agent state      # Loads session from file
python -m cli.agent attack 0   # Uses same session

# Clear session for new game
python -m cli.agent disconnect # Removes session file
```

---

## Key Files

| File | Purpose |
|------|---------|
| `server/event_server.py` | FastAPI server, all endpoints, combat log |
| `server/session.py` | Session/game management, authority validation |
| `cli/main.py` | Human CLI, game loop, opponent turn polling |
| `cli/agent.py` | Claude agent CLI, simple commands |
| `cli/api_client.py` | HTTP client wrapper with session state |
| `cli/display.py` | Rich terminal rendering |
| `cli/commands.py` | Command parsing and execution |

---

## Running

```bash
# Terminal 1: Start server
source .venv/bin/activate
uvicorn server.event_server:app --reload

# Terminal 2: Human player
python -m cli playpvp

# Claude agent (in separate process or Claude Code session)
python -m cli.agent connect
python -m cli.agent watch      # Blocks until your turn
python -m cli.agent attack 0
python -m cli.agent end
python -m cli.agent watch      # Wait for next turn
```

---

## Future Improvements

1. **WebSocket for real-time updates** - Replace polling with push notifications
2. **Multiple entity control** - Support controlling multiple entities per player
3. **Spectator mode** - Watch-only mode for combat viewing
4. **Replay system** - Save and replay combat history
