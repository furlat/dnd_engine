# CLI Status and Known Issues

## Current State (January 2026)

The CLI provides a nethack-style terminal interface for D&D combat with ASCII map visualization. **PvP mode is fully functional** with human vs Claude gameplay.

### Working Features

1. **Map Display**
   - ASCII grid with entities (`@` = player, first letter = enemies)
   - Wall visualization (`#`)
   - Valid move positions (`*`)
   - Movement path display (`+` in magenta)
   - Visibility coloring:
     - Green: Only hero sees
     - Red: Only enemy sees
     - Yellow: Both see
     - Dim: Neither sees

2. **Combat Actions**
   - `move X Y` / `m X Y` - Move to position
   - `m` alone - Show valid move positions on map
   - `attack N` / `a N` - Attack target by number
   - `a` alone - Show attack targets
   - `dash` / `d` - Double movement this turn
   - `dodge` / `o` - Attackers have disadvantage
   - `disengage` / `i` - No opportunity attacks when moving
   - `end` / `e` - End turn

3. **Display Panels**
   - Header: "NEURODRAGON" branding + connection status
   - Battlefield: ASCII map with entities
   - Combatants: Entity table with HP, AC, conditions
   - Combat Log: Rich formatted action history
   - Output: Command feedback (valid positions, targets)
   - Available Actions: What you can do (with economy in title)

4. **Information Display**
   - Full attack breakdown: d20 roll + bonus vs AC, outcome, damage
   - **Advantage/Disadvantage**: Shows both dice rolls (e.g., `ADV d20(14,8→14)`)
   - ADV/DIS indicators with color coding (green=ADV, red=DIS)
   - Entity status table with HP, AC, position, conditions

5. **PvP Mode**
   - Session-based authority (only control your own entity)
   - Combat log polling to see opponent actions
   - Connection status display in header

### Agent CLI (for Claude)

The agent CLI (`cli/agent.py`) provides a simple interface for Claude to play:

```bash
# Connection
python -m cli.agent connect     # Create session, join game
python -m cli.agent disconnect  # Clear session for new game

# Turn Management
python -m cli.agent watch       # BLOCKING - wait for turn, show opponent actions
python -m cli.agent state       # Show current game state
python -m cli.agent actions     # Show available actions

# Actions
python -m cli.agent move X Y    # Move to position
python -m cli.agent attack N    # Attack target by index
python -m cli.agent dash        # Dash action
python -m cli.agent dodge       # Dodge action
python -m cli.agent disengage   # Disengage action
python -m cli.agent end         # End turn
```

**Important**: The `watch` command is the key for staying engaged. It:
1. Polls server every 2 seconds
2. Shows opponent actions from combat log as they happen
3. When it becomes Claude's turn, displays full state + available actions
4. Detects encounter end and exits cleanly

**Typical Claude workflow**:
```bash
python -m cli.agent connect
python -m cli.agent watch      # Blocks until your turn
python -m cli.agent move 5 7
python -m cli.agent attack 0
python -m cli.agent end
python -m cli.agent watch      # Wait for next turn
```

### Configuration

**Vision Range**: Consistently set to `max_distance=20` (100ft) across:
- `dnd/encounter.py:start_turn()`
- `dnd/actions.py` (after movement)
- `server/event_server.py:setup_combat_with_human()`

**Map Setup**:
- 15x15 grid (0-14 on each axis)
- Vertical wall at x=7 from y=3 to y=11 (gap at y=7)
- Hero starts at (2, 7)
- Skeleton starts at (12, 7)

### API Endpoints

See `CLI_API_REFERENCE.md` for full API documentation.

**Key endpoints**:
- `POST /simulation/start-human` - Start game (player vs AI)
- `POST /simulation/start-pvp` - Start PvP game
- `GET /state` - Full game state
- `GET /visibility` - Entity visibility data
- `GET /entity/{uuid}/available-actions` - Available actions
- `GET /combat-log` - Server-side combat log
- `GET /pvp/status` - Whose turn, who's connected
- `POST /action/move` - Move (includes `triggered_reactions`)
- `POST /action/attack` - Attack
- `POST /action/dash` - Dash
- `POST /action/dodge` - Dodge
- `POST /action/disengage` - Disengage
- `POST /action/end-turn` - End turn

### Files Structure

```
cli/
├── __main__.py      # Module entry point
├── agent.py         # Agent CLI for Claude (connect, watch, state, actions, move, attack, end)
├── api_client.py    # HTTP client for server with session management
├── commands.py      # Command parsing and execution for human CLI
├── display.py       # Rich-based TUI rendering (panels, map, combat log)
└── main.py          # Typer entry point (play, playpvp commands)

server/
├── event_server.py  # FastAPI server with all endpoints
├── session.py       # Session/game management, authority validation
└── api_models.py    # Pydantic models for API
```

### Running the CLI

```bash
# Terminal 1: Start server
source .venv/bin/activate
uvicorn server.event_server:app --reload

# Terminal 2: Human player
python -m cli play       # vs AI
python -m cli playpvp    # vs Claude

# Claude (via agent CLI)
python -m cli.agent connect
python -m cli.agent watch
```

### Known Issues / Limitations

1. **Polling-based updates**: Uses HTTP polling instead of WebSockets. Works fine but adds latency.

2. **Single entity per player**: Each session controls one entity. Multi-entity control not implemented.

3. **No ranged weapon long range**: Ranged attacks work but long range disadvantage not implemented.

4. **No cover system**: No AC bonuses from cover/obstacles.

### Recent Fixes (January 2026)

- **Dice Rolling Bug**: Fixed advantage/disadvantage rolling only 1 die instead of 2
- **Advantage Status Case Sensitivity**: Fixed server not selecting correct min/max die
- **Opportunity Attacks**: Fixed handlers not being registered in setup
- **Agent CLI `watch` command**: Added blocking turn-wait with opponent action display
- **Rich Combat Log**: Consolidated to single panel with color-coded actions
- **Output Panel**: Added for command feedback (valid positions, attack targets)
- **Header Panel**: Added NEURODRAGON branding + connection status
- **Action Economy in Title**: Available actions panel shows remaining economy
