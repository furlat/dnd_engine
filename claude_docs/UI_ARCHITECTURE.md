# CLI and Server Architecture

## Overview

The D&D Engine uses a terminal-based CLI for gameplay instead of a web UI. Two CLIs are provided:
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
│  │  POST /action/end-turn - end turn (requires session)       │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                    │ HTTP
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                     HUMAN CLI (cli/main.py)                      │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────────────┐ │
│  │  APIClient  │    │  GameState  │    │   Display (Rich)     │ │
│  │  (HTTP)     │    │  (local)    │    │   - Map              │ │
│  └─────────────┘    └─────────────┘    │   - Combat Log       │ │
│                                         │   - Action Results   │ │
│  ┌────────────────────────────────────┐│   - Turn Info        │ │
│  │  wait_for_opponent_turn()         ││                       │ │
│  │  - Polls /combat-log              ││                       │ │
│  │  - Polls /pvp/status              │└──────────────────────┘ │
│  │  - Shows rich opponent actions    │                         │
│  └────────────────────────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   AGENT CLI (cli/agent.py)                       │
│  Simple command-based interface for Claude:                      │
│  - connect     Create session, join game                         │
│  - state       Show map and entities                             │
│  - actions     Show available actions                            │
│  - move X Y    Move to position                                  │
│  - attack N    Attack target by index                            │
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
    state.add_to_log(entry["message"])   # Local log
    last_index = entry["index"] + 1
```

---

## Display Components (cli/display.py)

### Map View

```
╭──────────────────────── Battlefield ────────────────────────╮
│    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4                            │
│   +-------------------------------+                         │
│  7| . . @ . . . S . . . . . . . . |                         │
│   +-------------------------------+                         │
│ @ = You  S = Enemy  + = Path  # = Wall                      │
╰─────────────────────────────────────────────────────────────╯
```

### Action Results

When you attack:
```
Hero attacks Skeleton with Scimitar
  Attack Roll: d20(14) +4 = 18 vs AC 13
  Result: HIT!
  Damage: (5)+2 = 7
  Skeleton HP: 10
```

When opponent attacks (same format via `show_opponent_action()`):
```
Skeleton attacks Hero with Shortsword
  Attack Roll: d20(17) +4 = 21 vs AC 15
  Result: HIT!
  Damage: 8
  Hero HP: 2
```

### Combat Log

```
Combat Log:
  Skeleton moves to (6, 7).
  You move to (5, 7).
  Hit! d20(14)+4=18 vs AC 13 → 7 dmg to Skeleton
  Skeleton hits Hero. d20(17)+4=21 vs AC 15 → 8 damage
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
uvicorn server.event_server:app --reload

# Terminal 2: Human player
python -m cli playpvp

# Terminal 3: Claude agent (or let Claude run these commands)
python -m cli.agent connect
python -m cli.agent state
python -m cli.agent attack 0
python -m cli.agent end
```

---

## Future Improvements

1. **Movement path display for opponent moves** - Show path on map like player moves
2. **WebSocket for real-time updates** - Replace polling with push notifications
3. **Multiple entity control** - Support controlling multiple entities per player
4. **Spectator mode** - Watch-only mode for combat viewing
