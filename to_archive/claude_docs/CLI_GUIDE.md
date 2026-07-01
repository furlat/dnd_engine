# CLI Guide

Reference for using the D&D Engine CLI and Agent commands.

## Quick Start

```bash
# Terminal 1: Start server
source .venv/bin/activate
uvicorn server.event_server:app --reload

# Terminal 2: Human player
python -m cli play       # vs AI
python -m cli playpvp    # vs Claude (PvP)

# Claude agent (separate terminal)
python -m cli.agent connect
python -m cli.agent watch
```

---

## Human CLI Commands

The human CLI (`python -m cli play` or `playpvp`) uses a Rich terminal interface with these commands:

| Command | Alias | Description |
|---------|-------|-------------|
| `move X Y` | `m X Y` | Move to position (X, Y) |
| `m` | - | Show valid move positions on map |
| `jump X Y` | `j X Y` | Jump to visible position (costs bonus action + movement) |
| `j` | - | Show valid jump positions on map |
| `attack N` | `a N` | Attack target by number |
| `a` | - | Show attack targets |
| `dash` | `d` | Dash (double movement this turn) |
| `dodge` | `o` | Dodge (attackers have disadvantage) |
| `disengage` | `i` | Disengage (no opportunity attacks when moving) |
| `end` | `e` | End turn |
| `? X Y` | - | Inspect tile at (X, Y) — shows tile info, entities, and floor objects |

### Display Panels

- **Battlefield**: ASCII map with entities (`@` = player, letters = enemies, `#` = wall, `~` = water, `θ` = potion, `λ` = lever, `φ` = other items)
- **Combatants**: Entity table (HP, AC, position, conditions)
- **Combat Log**: Formatted action history with roll breakdowns
- **Available Actions**: What you can do (with action economy in title)

---

## Agent CLI Commands

The agent CLI (`python -m cli.agent`) enables Claude to play via separate commands.

### Connection

```bash
python -m cli.agent connect     # Create session, join game
python -m cli.agent disconnect  # Clear session for new game
```

### Turn Management

```bash
python -m cli.agent watch       # BLOCKING - wait for turn, show opponent actions
python -m cli.agent wait        # Quick check if it's my turn (returns 0 if yes)
python -m cli.agent state       # Show current game state
python -m cli.agent actions     # Show available actions
```

### Actions

```bash
python -m cli.agent move X Y    # Move to position (X, Y)
python -m cli.agent jump X Y    # Jump to visible position
python -m cli.agent attack N    # Attack target by index
python -m cli.agent dash        # Take Dash action
python -m cli.agent dodge       # Take Dodge action
python -m cli.agent disengage   # Take Disengage action
python -m cli.agent end         # End turn
```

### Typical Workflow

**Critical**: After `end`, you MUST run `watch` again to stay connected!

```bash
python -m cli.agent connect
python -m cli.agent watch      # Blocks until your turn
python -m cli.agent state      # Optional: see full state
python -m cli.agent move 5 7
python -m cli.agent attack 0
python -m cli.agent end
python -m cli.agent watch      # Wait for next turn
```

The `watch` command:
1. Polls server every 2 seconds
2. Shows opponent actions from combat log as they happen
3. When it becomes your turn, displays full state + available actions
4. Detects encounter end and exits cleanly
5. Ctrl+C to interrupt

### Session Persistence

Session info is stored in `/tmp/dnd_agent_session.txt` so it persists between commands.

To restart: User restarts `playpvp`, Claude runs `disconnect` -> `connect` -> `watch`

---

## Server API Reference

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/state` | GET | Full game state (grid, entities, encounter) |
| `/visibility` | GET | Entity visibility data |
| `/entity/{uuid}/available-actions` | GET | Available actions for entity |
| `/tile/{x}/{y}` | GET | Tile info: terrain, conditions, entities, floor objects |
| `/combat-log` | GET | Server-side combat log entries |
| `/pvp/status` | GET | Whose turn, who's connected |

### Action Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/action/execute` | POST | Execute action by template name + target index |
| `/action/end-turn` | POST | End turn, advance encounter |

### Session Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/session/create` | POST | Create player session |
| `/game/join` | POST | Join game with session |
| `/session/{id}/ping` | POST | Check session status, whose turn |

### Response Formats

**Available Actions** (`GET /entity/{uuid}/available-actions`):
```json
{
  "entity_actions": [{"template_name": "Attack_MELEE_MAIN", "valid_targets": [...]}],
  "position_actions": [
    {"template_name": "Move", "valid_targets": [...]},
    {"template_name": "Jump", "valid_targets": [...]}
  ],
  "self_actions": [{"template_name": "Dash", "can_afford": true}],
  "remaining_movement": 30
}
```

**Action Result** (`POST /action/execute`):
```json
{
  "success": true,
  "event_type": "attack",
  "event_data": {
    "attack_roll": {"d20_used": 15, "bonus": 4, "total": 19},
    "target_ac": 13,
    "outcome": "Hit",
    "total_damage": 7
  },
  "triggered_reactions": []
}
```

---

## Map Configuration

- **Grid**: 15x15 (0-14 on each axis)
- **Wall**: Vertical at x=7 from y=3 to y=11 (gap at y=7)
- **Hero**: Starts at (2, 7)
- **Skeleton**: Starts at (12, 7)
- **Vision Range**: 20 cells (100ft)

---

## Known Limitations

1. **Polling-based updates**: Uses HTTP polling, not WebSockets
2. **Single entity per player**: Each session controls one entity
3. **No ranged long range**: Ranged attacks work but long range disadvantage not implemented
4. **No cover system**: No AC bonuses from cover/obstacles

---

## Files Reference

| File | Purpose |
|------|---------|
| `cli/__main__.py` | Module entry point |
| `cli/main.py` | Human CLI (`play`, `playpvp` commands) |
| `cli/agent.py` | Agent CLI for Claude |
| `cli/api_client.py` | HTTP client with session management |
| `cli/display.py` | Rich TUI rendering |
| `cli/commands.py` | Command parsing for human CLI |
| `server/event_server.py` | FastAPI server |
| `server/session.py` | Session/game management |
