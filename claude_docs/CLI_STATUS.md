# CLI Status and Known Issues

## Current State (January 2026)

The CLI provides a nethack-style terminal interface for D&D combat with ASCII map visualization.

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
   - `attack N` / `a N` - Attack target by number
   - `dash` / `d` - Double movement this turn
   - `dodge` / `o` - Attackers have disadvantage
   - `disengage` / `i` - No opportunity attacks when moving
   - `end` / `e` - End turn
   - Action hints at bottom show available actions

3. **Information Display**
   - Full attack breakdown: d20 roll + bonus vs AC, outcome, damage dice
   - **Advantage/Disadvantage**: Shows both dice rolls (e.g., `d20(14, 8 → 14)` for ADV)
   - ADV/DIS indicators with color coding (green=ADV, red=DIS)
   - Entity status table with HP, AC, position, conditions
   - Combat log with recent actions
   - AI turn actions displayed with full details

4. **AI Behavior**
   - MeleeAIController moves toward enemies and attacks
   - AI actions captured and displayed between turns
   - AI movement paths now displayed

### Known Issues

#### 1. Opportunity Attacks Not Triggering (ROOT CAUSE FOUND)

**Problem**: When the player moves out of an enemy's threatened area, opportunity attacks should trigger but they don't.

**Root cause**: `add_opportunity_attack_handler()` is NOT being called for entities in `setup_combat_with_human()`. The bestiary factory functions (`create_skeleton`, `create_goblin`) don't automatically add the handler.

**How OA works in the engine** (`dnd/reactions.py`):
- `EventHandler` registered on `MOVEMENT` events at `EFFECT` phase
- `opportunity_attack_processor` checks:
  1. Moving entity started in threatened position
  2. Path goes outside threatened area
  3. Moving entity doesn't have "Disengaging" condition
- If conditions met, executes an `Attack` action

**FIXED**: Added to `server/event_server.py:setup_combat_with_human()`:
```python
from dnd.reactions import add_opportunity_attack_handler

# After creating entities:
add_opportunity_attack_handler(player)
add_opportunity_attack_handler(enemy)
```

**Capture mechanism** (already implemented in `execute_move`):
- Registers callback via `EventQueue.add_on_event_callback()`
- Captures attack events targeting the moving entity during movement
- Returns in `triggered_reactions` array

#### 2. Dash/Dodge/Disengage Availability (VERIFIED WORKING)

**Tested**: API correctly returns these actions with `can_afford=True`.

```bash
# Test shows:
other_actions:
  dash: can_afford=True
  dodge: can_afford=True
  disengage: can_afford=True
```

**CLI Commands**:
- `d` or `dash` - Take Dash action (double movement)
- `o` or `dodge` - Take Dodge action (attackers have disadvantage)
- `i` or `disengage` - Take Disengage action (no opportunity attacks)

**Display**: These appear in the "OTHER ACTIONS" section when running `actions` command.

**Note**: The user may have missed these in the display. They show under a separate section from attacks and movement.

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
- `POST /simulation/start-pvp` - Start PvP game (both human controlled)
- `GET /state` - Full game state
- `GET /visibility` - Entity visibility data
- `GET /entity/{uuid}/available-actions` - Available actions
- `POST /action/move` - Move (includes `triggered_reactions`, `path`)
- `POST /action/attack` - Attack
- `POST /action/dash` - Dash
- `POST /action/dodge` - Dodge
- `POST /action/disengage` - Disengage
- `POST /action/end-turn` - End turn (includes `ai_actions` with paths in AI mode)

### Files Structure

```
cli/
├── __main__.py      # Module entry point
├── agent.py         # Non-interactive CLI for Claude agent
├── api_client.py    # HTTP client for server
├── commands.py      # Command parsing and execution
├── display.py       # Rich-based ASCII rendering
└── main.py          # Typer entry point and game loop

server/
├── event_server.py  # FastAPI server with all endpoints
└── api_models.py    # Pydantic models for API
```

### Running the CLI

```bash
# Terminal 1: Start server
python -m server.event_server --force

# Terminal 2: Start CLI (player vs AI)
python -m cli play
```

### PvP Mode (User vs Claude)

PvP mode allows Claude to play against a human user via the agent CLI.

```bash
# Terminal 1: Start server
python -m server.event_server --force

# Terminal 2: User starts PvP game via regular CLI
python -m cli play
# Then use "start-pvp" command (or call POST /simulation/start-pvp)

# Claude uses agent CLI to control the Skeleton:
python -m cli.agent state         # See board state
python -m cli.agent actions       # See available actions
python -m cli.agent move 5 3      # Move to position
python -m cli.agent attack 0      # Attack target #0
python -m cli.agent end           # End turn
```

**Agent CLI Commands:**
- `state` - Show game state (map, entities, whose turn)
- `actions` - Show available actions for active entity
- `wait` - Check if it's my turn (exit code 0 = yes)
- `move X Y` - Move to position
- `attack N` - Attack target by index
- `dash` - Take Dash action
- `dodge` - Take Dodge action
- `disengage` - Take Disengage action
- `end` - End turn
- `start-pvp` - Start new PvP game

### Recent Fixes (January 2026)

#### Dice Rolling Bug - FIXED
**Problem**: Advantage/disadvantage was only rolling 1 die instead of 2.

**Root cause**: `_roll_with_advantage()` and `_roll_with_disadvantage()` in `dnd/core/dice.py` used `range(self.count)` where `self.count=1` for d20 rolls.

**Fix**: Changed both methods to always use `range(2)`:
```python
def _roll_with_advantage(self) -> Tuple[int, List[int]]:
    rolls = [random.randint(1, self.value) for _ in range(2)]
    return max(rolls), rolls
```

#### Advantage Status Case Sensitivity - FIXED
**Problem**: Server wasn't correctly selecting min/max die for advantage/disadvantage.

**Root cause**: `AdvantageStatus.DISADVANTAGE.value` is `"Disadvantage"` (capital D), but comparisons used lowercase `"disadvantage"`.

**Fix**: Applied `.lower()` to all advantage status comparisons in `event_server.py`.

### Next Steps

1. ~~**Debug opportunity attacks**~~: FIXED - handlers now registered in setup_combat_with_human()
2. ~~**Debug action availability**~~: FIXED - dash/dodge/disengage now shown in action hints
3. ~~**Test dodge condition effect**~~: VERIFIED WORKING - `examples/test_dodging_attack.py` confirms attackers get disadvantage
4. **Test disengage condition effect**: Verify no opportunity attacks trigger when Disengaging
5. **Add ranged weapon support**: Currently only melee weapons work
