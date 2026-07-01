# CLI Play Modes — Complete Architecture Reference

This document covers every play mode, how they work, where responsibility lives in code, and every difference between them.

## Overview

Four modes, one shared server, three client configurations:

| Mode | Command | Hero Controller | Monster Controller | Who Drives Turns |
|------|---------|-----------------|-------------------|------------------|
| **vs AI** | `python -m cli play` | `HumanController` | `MeleeAIController` | Server auto-runs AI, waits for human |
| **vs Claude (PvP)** | `python -m cli playpvp` | `HumanController` | `ClaudeController` | Both wait for API input |
| **Claude vs Claude** | `python -m cli spectate` | `ClaudeController` | `ClaudeController` | Orchestrator spawns Claude subprocesses |
| **Orchestrator (headless)** | `python -m cli.orchestrator` | `ClaudeController` | `ClaudeController` | Same as spectate, no Rich TUI |

**Key insight**: `HumanController` and `ClaudeController` are functionally identical — both return `can_continue_turn()=False`, causing the server to exit the turn loop and wait for HTTP API calls. The only difference is `controller_type` (`"human"` vs `"claude"`) used for identification and routing in `advance_until_player()`.

---

## 1. The Controller System

**File**: `dnd/controller.py`

### Controller Base Class (line 53)

The encounter calls two methods on each controller during a turn:

```python
def can_continue_turn(self, entity, context) -> bool:
    """Should the run_turn loop keep running? Default: True."""
    return True

def get_next_action(self, entity, context) -> Optional[BaseAction]:
    """What action to take next? None = end turn. Default: None."""
    return None
```

### PassController (line 136) — Tests Only

```python
can_continue_turn() → False   # Exit immediately
get_next_action()  → None     # No actions
```

Used in test files where the entity should never act.

### HumanController (line 153) — Human Player

```python
can_continue_turn() → False   # Exit run_turn loop IMMEDIATELY
get_next_action()  → None     # Never returns actions — actions come via HTTP API
```

The server exits `run_turn()` instantly. The human provides actions by calling `/action/execute` via the CLI.

### ClaudeController (line 179) — Claude Agent

```python
can_continue_turn() → False   # Identical to HumanController
get_next_action()  → None     # Actions come via agent CLI → HTTP API
```

Functionally identical to `HumanController`. Separate class for `controller_type="claude"` identification.

### MeleeAIController (line 203) — Built-in AI

**This is the only controller that actually computes actions.** The server loops internally until the AI has no more actions.

```python
can_continue_turn() → True    # Default (let encounter check action economy)
get_next_action()  → action or None
```

**Priority logic** (lines 221-273):

1. **Attack if possible**: Iterates `available.entity_actions`, finds first with `can_afford=True` and `valid_targets`. Instantiates template with first target's UUID.

2. **Move toward enemy if can still attack afterward**: Only moves if `can_afford("actions", 1)` is true (saves action for attack after moving). Finds the reachable position that minimizes Manhattan distance to nearest visible enemy. Only moves if it gets closer than current position.

3. **End turn**: Returns `None` — no good action available.

**Limitations**:
- No spell casting, no bonus actions, no item use
- Always targets first available target (no focus fire logic)
- Manhattan distance heuristic (not pathfinding distance)
- Doesn't use Dash, Dodge, Disengage
- No reaction management

---

## 2. Server-Side Game Setup

**File**: `server/event_server.py`

### `setup_arena_combat()` (line 230)

**THE single function that creates all game state for play/playpvp/spectate modes.**

Parameters: `player_position=(2,7)`, `pvp_mode=False`, `character_class="fighter"`

**Step-by-step**:

1. **Reset ALL state** (lines 244-251):
   ```python
   reset_map()
   Entity._entity_registry.clear()
   Entity._entity_by_position.clear()
   Encounter.clear_registry()
   Controller._controller_registry.clear()
   SessionManager.reset()
   EventQueue.reset()
   ```

2. **Create 15x15 grid** (lines 254-255)

3. **Build arena features** (lines 258-297):
   - Vertical wall at column 7 (y=3 to y=12, gap at y=7 for door)
   - `TestDoorA` at (7,7) — blocks movement AND vision until opened
   - Water island in top-left (0,0)-(1,2) — reachable only by Jump
   - Spike zone in bottom-left (0-4, 11-14) — 20 tiles, one SpatialHandler
   - Difficult terrain at wall ends — 3x3 zones at (6-8, 0-2) and (6-8, 12-14)
   - All tiles default to `LightLevel.DARKNESS`
   - Wall torches at (14,1) and (14,13)

4. **Create Hero** (lines 307-337) based on `character_class`:
   - `"fighter"` → `create_dex_fighter()` — L5 DEX Fighter with dual wield
   - `"barbarian"` → `create_barbarian_hero()` — L5 Berserker
   - `"sorcerer"` → `create_sorcerer_class(SorcererConfig(...))` — L5 with metamagic
   - All heroes get: lit torch, Greater Invisibility potion
   - Sorcerers also get: spell scrolls (Magic Missile x2, Fireball L3, Fireball L5)

5. **Create 3 Skeletons** (lines 366-375), all `faction="monsters"`, `darkvision=True`:
   - `create_skeleton_warrior("Skeleton Warrior", position=(12,5))`
   - `create_skeleton_archer("Skeleton Archer", position=(12,7))`
   - `create_skeleton_warlock("Skeleton Warlock", position=(12,9))`

6. **Register opportunity attacks** (lines 377-380) for all entities

7. **Update senses** (line 382): `Entity.update_all_entities_senses(max_distance=20)`

8. **Create Encounter and assign controllers** (lines 385-395):
   ```python
   encounter.add_combatant(player, HumanController(...))  # Hero ALWAYS HumanController

   for skeleton in skeletons:
       if pvp_mode:
           encounter.add_combatant(skeleton, ClaudeController(...))
       else:
           encounter.add_combatant(skeleton, MeleeAIController(...))
   ```

   **This is the key divergence point**: `pvp_mode` determines monster controller.

### `/simulation/start-human` (line 2074)

**Starts vs-AI mode.** Calls `setup_arena_combat(pvp_mode=False)`.

1. Creates game session: `sim.create_game_session(sim.encounter)`
2. Creates AI session: `mgr.create_session(PlayerType.AI, "AI Monsters")`
3. Assigns all `faction="monsters"` entities to AI session
4. Calls `advance_encounter()` — auto-runs AI turns, stops at human turn
5. Returns `hero_uuid` — human CLI creates session and joins with this UUID

### `/simulation/start-pvp` (line 2185)

**Starts PvP mode.** Calls `setup_arena_combat(pvp_mode=True)`.

1. Creates game session (NO AI session — both players create explicit sessions)
2. Calls `advance_encounter()` — rolls initiative, stops at first turn
3. Returns both `hero_uuid` and `skeleton_uuid`
4. Both players must create sessions and join independently

### `advance_encounter()` (line 555)

**Runs AI turns until a human/claude turn is reached.**

```python
# Roll initiative and start if not started
if encounter.state == EncounterState.NOT_STARTED:
    encounter.roll_initiative()
    encounter.start_encounter()

# This is the key call — auto-runs AI, stops on human/claude
result = encounter.advance_until_player()

# Collect AI combat log entries for the response
new_entries = encounter.get_combat_log(log_start)
return {"status": result.status, "ai_actions": [...], ...}
```

---

## 3. Encounter Turn Management

**File**: `dnd/encounter.py`

### Turn State Machine

```
NOT_STARTED → IN_PROGRESS → ENDED
     ↑                        │
     └────────────────────────┘  (next_turn resets)
```

### `run_turn()` (line 970) — Complete Turn Execution

Called by `advance_until_player()` for AI controllers:

```python
def run_turn(self):
    # 1. Start turn if needed → fires TurnStartEvent, resets action economy
    if self.turn_state != TurnState.IN_PROGRESS:
        self.start_turn()

    entity = self.get_current_entity()
    controller = self.get_current_controller()

    # 2. Main loop — keep asking controller for actions
    while self.can_continue_turn():
        context = self._build_turn_context(entity)

        if not controller.can_continue_turn(entity, context):
            break  # HumanController/ClaudeController exit HERE

        action = controller.get_next_action(entity, context)
        if action is None:
            break  # MeleeAI returns None when out of options

        action.apply()  # Execute the action
        deaths = self.check_deaths()
        if deaths and self.state != EncounterState.ACTIVE:
            return None  # Encounter ended mid-turn

    # 3. End turn → fires TurnEndEvent
    end_event = self.end_turn()
    self.current_turn_index += 1
    if self.current_turn_index >= len(self.initiative_order):
        self._advance_round()
    self.turn_state = TurnState.NOT_STARTED
    return end_event
```

**For HumanController/ClaudeController**: The loop body executes once — `can_continue_turn()` returns `False` on the first check, and the loop breaks immediately. `run_turn()` then calls `end_turn()` and advances.

**For MeleeAIController**: The loop runs until `get_next_action()` returns `None` or action economy is exhausted.

### `advance_until_player()` (line 1039) — Auto-Run AI Turns

This is the server's main dispatch loop:

```python
def advance_until_player(self) -> AdvanceResult:
    while self.state == EncounterState.ACTIVE:
        entity = self.get_current_entity()
        controller = self.get_current_controller()

        # Skip dead combatants
        if combatant.is_dead:
            self.current_turn_index += 1
            continue

        # Human or Claude: STOP and wait for API
        if controller.controller_type in ("human", "claude"):
            if self.turn_state != TurnState.IN_PROGRESS:
                self.start_turn()  # Start their turn before returning
            return AdvanceResult(
                status="waiting_for_human" or "waiting_for_claude",
                entity_uuid=entity.uuid,
                ...
            )

        # AI: run turn internally, then continue loop
        self.run_turn()

    return AdvanceResult(status="encounter_ended")
```

**Key**: This method calls `start_turn()` for human/claude controllers before returning. The turn is IN_PROGRESS when the client starts receiving API calls.

---

## 4. Session & Authority System

**File**: `server/session.py`

### PlayerType (line 23)

```python
class PlayerType(str, Enum):
    HUMAN = "human"    # User via CLI
    CLAUDE = "claude"  # Claude via agent CLI
    AI = "ai"          # Built-in MeleeAIController
```

### PlayerSession (line 37)

Tracks a single connected player:
- `session_id: UUID`
- `player_type: PlayerType`
- `connection_status: ConnectionStatus` — CONNECTED, DISCONNECTED, WAITING
- `controlled_entities: Set[UUID]` — which entities this session owns
- `owns_entity(uuid)` — check ownership
- `ping()` — update last_activity timestamp

### GameSession (line 87)

Maps entities to sessions:
- `players: Dict[UUID, PlayerSession]` — all connected sessions
- `entity_to_player: Dict[UUID, UUID]` — entity UUID → session UUID
- `assign_entity(entity_uuid, session_id)` — register ownership
- `active_entity_uuid` — property returning current turn entity's UUID
- `is_player_turn(session_id)` — check if it's this session's turn

### Authority Flow

Every action endpoint calls `validate_session_action()` (event_server.py line 593):

```
POST /action/{session_id}/execute
  → validate_session_action(session_id, entity_uuid)
    → SessionManager.validate_action()
      1. Session exists and is connected?
      2. Session owns this entity?
      3. Entity is the active entity (it's their turn)?
      4. Turn is IN_PROGRESS?
    → Returns entity or raises HTTPException 403/404
  → execute_by_index(entity, template_name, target_index)
  → check_deaths()
```

---

## 5. CLI Client — Human Player

**File**: `cli/main.py`

### `play()` (line 1178) — vs AI Entry Point

```python
def play(character_class="fighter", host="localhost", port=8000):
    client = APIClient(base_url=f"http://{host}:{port}")

    # 1. Start game (rolls initiative, auto-runs AI if they go first)
    result = client.start_human_game(character_class)  # POST /simulation/start-human
    hero_uuid = result["hero_uuid"]
    initial_log_index = result["new_log_since"]

    # 2. Create session and join
    client.create_session(player_type="human", name="Player")
    client.join_game(entity_uuids=[hero_uuid])

    # 3. Extract AI movement path for display
    ai_actions = result.get("ai_actions", [])
    initial_ai_path = ...  # From movement combat log entries

    # 4. Run game loop
    game_loop(client, initial_ai_path=initial_ai_path, initial_log_index=initial_log_index)
```

### `playpvp()` (line 1243) — vs Claude Entry Point

```python
def playpvp(character_class="fighter", host="localhost", port=8000):
    client = APIClient(base_url=f"http://{host}:{port}")

    # 1. Start PvP game
    result = client.start_pvp_game(character_class)  # POST /simulation/start-pvp
    hero_uuid = result["hero_uuid"]

    # 2. Create session and join
    client.create_session(player_type="human", name="Player")
    client.join_game(entity_uuids=[hero_uuid])

    # 3. Set PvP display mode
    display.set_session_info(pvp_mode=True, hero_connected=True, claude_connected=False)

    # 4. Run game loop in PvP mode
    game_loop(client, pvp_mode=True, hero_uuid=hero_uuid)
```

### `game_loop()` (line 897) — Main Loop

Shared by all human-facing modes. Uses Rich alternate screen for full-screen TUI.

**Core branching logic** (lines 938-970):

```python
while True:
    render_display(client, state, my_entity_uuid, pvp_mode)

    if pvp_mode and hero_uuid:
        # PvP: check if it's MY turn by comparing active UUID to hero UUID
        active_uuid = state.turn["current_entity_uuid"]
        is_my_turn = (active_uuid == hero_uuid)
        if not is_my_turn:
            wait_for_opponent_turn(client, state, hero_uuid)  # Block until Claude done
            continue

    elif not state.turn.get("is_human_turn", False):
        # vs AI: server tells us if it's human turn via is_human_turn flag
        wait_for_ai_turn(client, state)  # Block until AI done
        continue

    # MY TURN — prompt for input, execute commands
    command = display.prompt_command()
    result = execute_command(client, command, state)
```

### `wait_for_ai_turn()` (line 761) — vs AI Mode

Simple polling loop:
- Polls `GET /encounter/current-turn` every 0.5s
- Checks `is_human_turn` flag
- 30-second timeout
- No combat log polling (AI actions shown after turn ends)

### `wait_for_opponent_turn()` (line 796) — PvP Mode

Rich polling loop with real-time updates:
- Polls combat log (`GET /combat-log?since=N`) for opponent actions — displays them live
- Polls `/pvp/status` for `is_hero_turn` flag and Claude connection status
- Polls full state for position/HP changes — triggers map redraw
- No timeout (waits indefinitely for Claude)
- Shows Claude connection status changes in header

**Key difference table**:

| Aspect | `wait_for_ai_turn` | `wait_for_opponent_turn` |
|--------|-------------------|------------------------|
| Turn detection | `is_human_turn` flag | `/pvp/status` → `is_hero_turn` |
| Combat log polling | No | Yes — shows opponent actions live |
| Map redraw | No | Yes — on position/HP changes |
| Connection status | N/A | Shows Claude connected/disconnected |
| Timeout | 30 seconds | None (infinite) |
| Polling interval | 0.5s | 0.5s |

### `refresh_state()` (line 660)

Called after each turn change. Fetches:
- `GET /state` — grid, entities, encounter state
- `GET /encounter/current-turn` — whose turn, round number
- `GET /visibility` — per-entity FOV data for fog of war
- `GET /entity/{uuid}/available-actions` — only if it's human's turn

---

## 6. Agent CLI — Claude's Interface

**File**: `cli/agent.py`

### Architecture

The agent CLI is a **stateless command-line tool**. Each command is a separate process invocation:

```bash
python -m cli.agent --token hero connect    # Create session, join game
python -m cli.agent --token hero state      # Show game state
python -m cli.agent --token hero move 5 3   # Execute move
python -m cli.agent --token hero end        # End turn
```

State persists between invocations via session files on disk.

### Session Persistence (lines 30-102)

**File format** (`/tmp/dnd_game/{token}_session.txt`):
```
<server_session_id>
<active_entity_uuid>
<other_entity_uuid_1>
<other_entity_uuid_2>
```

- `save_session(session_id, entity_uuids)` — writes file
- `load_session()` → `(session_id, entity_uuids)` — reads file
- `ensure_session(client)` — loads session, pings server to validate, switches `_current_entity_uuid` to whichever controlled entity's turn it currently is (multi-entity support)

### `--token` Flag (line 2235+)

When orchestrator runs agent CLI, it passes `--token hero` or `--token monsters`:

```python
if sys.argv[1] == "--token":
    token = sys.argv[2]
    SESSION_FILE = f"/tmp/dnd_game/{token}_session.txt"  # Override default path
    sys.argv = [sys.argv[0]] + sys.argv[3:]  # Strip --token from args
```

This allows multiple concurrent agent sessions with separate session files.

### Command Reference

| Command | Function | Description |
|---------|----------|-------------|
| `connect` | `cmd_connect()` | Create session (`POST /session/create`), join game (`POST /game/join`), save session file |
| `disconnect` | `cmd_disconnect()` | Clear session file |
| `state` | `cmd_state()` | Full state: map + entities + turn info, filtered by visibility |
| `actions` | `cmd_actions()` | Available actions formatted for AI consumption |
| `watch` | `cmd_watch()` | **Blocking poll** — wait for turn, output unified prompt |
| `move X Y` | `cmd_move()` | Move to position (prefers safe paths by default) |
| `jump X Y` | `cmd_jump()` | Jump to position |
| `attack N [T]` | `cmd_attack()` | Attack action N, target T (default 0) |
| `cast <spell> [args]` | `cmd_cast()` | Cast spell with entity/position targets |
| `self <name>` | `cmd_self_action()` | Self-targeting action (Dash, Dodge, etc.) |
| `use <name\|N>` | `cmd_use()` | Use item/object action |
| `end` | `cmd_end()` | End turn (`POST /action/{sid}/execute` with End action) |
| `inspect X Y` | `cmd_inspect()` | Inspect tile at position |
| `handlers` | `cmd_handlers()` | Show all event handlers with ON/OFF state |
| `toggle <name> on/off` | `cmd_toggle()` | Toggle handler enabled state |

### `cmd_watch()` (line 2062) — Turn Waiting

**Critical for PvP mode.** Blocks until it's the agent's turn, then outputs a unified prompt with all game state.

```python
def cmd_watch(client, poll_interval=2.0):
    combat_log_index = client.get_combat_log()["total"]

    while True:
        # Check for game end
        state = client.get_state()
        if encounter_ended:
            return 0

        # Check if it's my turn
        if is_my_turn(client):
            # Build unified prompt (same format as orchestrator)
            vis_set, vis_cells, mem_cells, sense_modes = get_visibility_data(client)
            log_data = client.get_combat_log(since=combat_log_index)
            actions = client.get_available_actions()

            prompt = build_turn_prompt(
                entity_name=..., faction="", round_number=...,
                combat_log_text=..., entity_table_text=...,
                map_text=..., action_text=...,
            )
            print(prompt)
            return 0  # Exit — Claude reads output and acts

        # Poll combat log for opponent actions (filtered by FOW)
        log_data = client.get_combat_log(since=combat_log_index)
        filtered = filter_combat_log(new_entries, controlled_uuids, vis_set)
        show_combat_log(filtered)

        time.sleep(poll_interval)  # 2-second intervals
```

### Map Formatting — `format_map()` (line 304)

Outputs two sections for AI consumption:

**1. Structured data** (precise, machine-readable):
```
MAP: (0,0)-(14,14)
ENTITIES: (2,7):Hero(you) (12,5):Skeleton Warrior(enemy) (12,7):Skeleton Archer(enemy)
TILE DETAILS:
  (2,7): Floor, bright | Hero (you, 45hp, AC 16)
  (7,7): Floor, bright | Door (closed) | [USE: Open Door]
  (12,5): Floor, dim | Skeleton Warrior (enemy, 15hp, AC 13)
  (5,5): Floor, bright | [Fireball L3: Skeleton 1, Skeleton 2 (slot)]
```

**2. ASCII grid** (spatial awareness):
```
   0123456789...
 0 ..~#......
 1 ..~#..A...
 2 ..~#......
 ...
 7 ..@..D..B.
```

Both sections are filtered by `visible_cells` (FOV) — only tiles the entity can see are shown. Tiles in `memory_cells` (previously seen) shown in MEMORY section.

**AoE spell annotations**: Position-targeted spells show `[SpellName: target1, target2]` on tiles where entities would be affected. Deduped by spell+level+targets.

### Entity Formatting — `format_entities()` (line 703)

Table sorted by initiative order:

```
ENTITIES (sorted by initiative):
  #  Name              Faction   HP        AC  Conditions         Position
  1  Hero              heroes    45/45     16                     (2,7)     <<< YOU
  2  Skeleton Warrior  monsters  15/15     13                     (12,5)
  3  Skeleton Archer   monsters  12/12     14                     (12,7)
```

Filtered by `visible_entity_uuids` — hidden entities not shown. Own entities always visible.

### Action Formatting — `format_actions()` (line 794)

```
=== Hero's Available Actions ===
REMAINING: Actions:1  Bonus:1  Movement:30ft  Slots: L1:4/4 L2:2/2 L3:2/2

ENTITY ACTIONS (attacks targeting entities):
  [0] Scimitar Attack (action) -> [0]Skeleton Warrior (12,5), [1]Skeleton Archer (12,7)

POSITION ACTIONS (movement):
  Move (FREE) -> 25 positions | Jump (FREE) -> 3 positions

SELF ACTIONS:
  Dash (action) | Dodge (action) | Disengage (action) | Hide (action)

SPELLS:
  Fire Bolt (action, cantrip) -> [0]Skeleton Warrior (12,5)
  Fireball (action, L3 slot) -> 5 positions [AoE Sphere r=20ft]

REACTIONS:
  Opportunity Attack [ON] | Shield [ON]
```

---

## 7. The Orchestrator — Claude vs Claude

**File**: `cli/orchestrator.py`

### Architecture

```
User runs: python -m cli spectate sorcerer --model claude-sonnet-4-5-20250929
    │
    ├─ Spectator TUI (cli/main.py:spectate) ─── polls /state, renders Rich display
    │
    └─ Orchestrator subprocess (cli/orchestrator.py:main)
         ├─ Server (subprocess if not running)
         ├─ Hero Claude (subprocess per turn) ─── claude -p "..." --token hero
         └─ Monsters Claude (subprocess per turn) ─── claude -p "..." --token monsters
```

### PlayerSlot (line 106)

```python
@dataclass
class PlayerSlot:
    slot_id: str           # "hero" or "monsters"
    token: str             # Random 6-char token for session auth (e.g., "a7k3p2")
    faction: str           # "heroes" or "monsters"
    entity_uuids: List[str]          # Assigned entity UUIDs (change per match)
    server_session_id: Optional[str]  # Server session ID (change per match)
    claude_session_id: Optional[str]  # Claude CLI session ID (persists across matches)
    notebook_path: Optional[Path]     # Persists across matches
    prompt_file: Optional[Path]       # System prompt with token baked in
    combat_log_index: int             # Tracks which log entries have been sent
    trajectory_path: Optional[Path]   # Per-match trajectory log
```

Session file path: `/tmp/dnd_game/{token}_session.txt`

### `main()` (line 1408) — Full Startup

1. **Create directories**: `/tmp/dnd_game/`, `game_logs/{timestamp}/turns/`, `game_logs/{timestamp}/notebooks/`
2. **Verify/start server**: Auto-starts uvicorn if not running
3. **Generate tokens**: `hero_token = generate_token()` — random 6-char
4. **Create PlayerSlots**: One per faction with tokens, paths
5. **Generate system prompts**: Read `cli/dnd_auto_prompt.md`, replace `{TOKEN}` and `{NOTEBOOK_PATH}` placeholders, write to `/tmp/dnd_game/prompt_{token}.md`
6. **Create empty notebooks**: `game_logs/{timestamp}/notebooks/hero.md`
7. **Series loop**: Run `run_single_match()` up to `BEST_OF` times, track score

### `run_single_match()` (line 1296) — Per-Match Setup

1. **Start new PvP game**: `spectator.start_pvp_game(character_class)` — resets server state
2. **Partition entities by faction**: `hero_uuids, monster_uuids = partition_by_faction(state)`
3. **Update slot entity UUIDs**: Entity UUIDs change each match!
4. **Create NEW server sessions**: Sessions don't persist across game resets
   ```python
   hero_client.create_session(player_type="claude", name="Claude Hero")
   hero_client.join_game(entity_uuids=hero_uuids)
   # DO NOT reset claude_session_id — keeps Claude memory across matches!
   ```
5. **Write session files**: Before turn loop starts
6. **Run turn loop**: `turn_loop(spectator, slots, slot_clients, ...)`

### `turn_loop()` (line 1087) — The Core Game Loop

```python
def turn_loop(spectator, slots, slot_clients, game_metrics, ...):
    while True:
        state = spectator.get_state()

        # Check encounter end
        if encounter["state"] != "active":
            break

        # Find whose turn it is
        active_uuid = encounter["current_entity_uuid"]
        slot = get_slot_for_entity(slots, active_uuid)  # Map UUID → faction slot

        # 1. Get visibility for SUBJECTIVE view
        visibility = spectator.get_visibility()
        vis_set = set(visibility[active_uuid]["visible_entities"])
        vis_set.update(slot.entity_uuids)  # Always see own units

        # 2. Get combat log since last seen (FILTERED by faction)
        log_data = spectator.get_combat_log(since=slot.combat_log_index)
        visible_entries = filter_combat_log(new_entries, slot.entity_uuids, vis_set)

        # 3. Read notebook content
        notebook_content = slot.notebook_path.read_text()

        # 4. Build prompt with all sections
        prompt = build_turn_prompt(
            entity_name=entity_name,
            faction=slot.faction,
            round_number=round_num,
            notebook_content=notebook_content,
            combat_log_text=format(visible_entries),
            entity_table_text=format_entities(entities, vis_set, active_uuid, ...),
            map_text=format_map(state, vis_set, active_uuid, vis_cells, ...),
            action_text=format_actions(actions, entity_name),
            series_info=series_info,
        )

        # 5. Write session file (before Claude invocation)
        write_session_file(slot, active_uuid)

        # 6. Run Claude subprocess
        result = run_claude_turn(slot, prompt, allow_write=False)

        # 7. Log metrics, flush trajectory in background
        turn_metrics = result.build_metrics(...)
        game_metrics.add_turn(turn_metrics)

        time.sleep(0.5)
```

**Visibility is per-faction**: Each Claude subprocess only sees what its entities can see. The map, entity table, combat log — everything is filtered through the active entity's FOV.

### `run_claude_turn()` (line 800) — Claude Subprocess

**THE critical function that spawns Claude.**

**Command construction**:

```python
cmd = ["claude", "-p", prompt]                          # Prompt is the turn data

if CLAUDE_MODEL:
    cmd += ["--model", CLAUDE_MODEL]                    # Model override

cmd += ["--output-format", "stream-json", "--verbose"]  # Real-time output

# Tool restrictions — CRITICAL
agent_prefix = f"source .venv/bin/activate && python -m cli.agent --token {slot.token}"
cmd += ["--allowedTools", f"Bash({agent_prefix} *)"]    # ONLY agent CLI commands
cmd += ["--allowedTools", "Read"]                        # Can read files
if allow_write:
    cmd += ["--allowedTools", "Write"]                   # Only during reflections

# System prompt (per-slot, token baked in)
cmd += ["--append-system-prompt-file", str(slot.prompt_file)]

cmd += ["--max-turns", str(max_turns)]                   # Usually 20

# Session continuity — CRITICAL for series
if slot.claude_session_id:
    cmd += ["--resume", slot.claude_session_id]          # Resume previous conversation
```

**Tool restrictions explained**:
- `Bash(source .venv/bin/activate && python -m cli.agent --token {TOKEN} *)` — Claude can ONLY run agent CLI commands with its token. Cannot run arbitrary bash.
- `Read` — Can read files (for inspecting game docs, map data)
- `Write` — Only allowed during post-game reflection (notebooks). Disabled during game turns to prevent race conditions.

**Subprocess execution**:

```python
process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    cwd=str(PROJECT_DIR),     # Project root for imports
    text=True,
    env=_clean_env(),         # Strip CLAUDE_* env vars to avoid recursive guard
)
```

**`_clean_env()`** (line 251): Strips all env vars containing "CLAUDE" from `os.environ` — prevents the subprocess Claude from detecting it's running inside another Claude instance.

**Stream parsing and early return**:

```python
for line in process.stdout:
    event = json.loads(line)        # stream-json format
    display_stream_event(event)      # Log to spectator
    _classify_stream_event(result)   # Collect metrics

    # CRITICAL: Detect turn end early
    if _is_turn_ended_event(event):
        result.turn_ended = True

        # Spawn background thread to drain remaining output
        threading.Thread(target=_drain, daemon=True).start()

        return result  # RETURN IMMEDIATELY — next turn starts!
```

**`_is_turn_ended_event()`** (line 512): Scans stream-json events for tool_result content containing `"OK: Turn ended"` — this is what `cmd_end()` prints when the turn is successfully ended.

**Why early return matters**: When turn-end is detected, the orchestrator immediately starts the next entity's turn. The previous Claude subprocess continues outputting (summary text, etc.) which is drained by a background thread. This enables **pipelining** — Claude A's cleanup overlaps with Claude B's prompt building.

### `verify_turn_ended()` (line 939) — Safety Net

After `run_claude_turn()` returns, the orchestrator verifies the turn actually ended:

```python
def verify_turn_ended(slot_client, entity_uuid):
    ping = slot_client.ping_session()
    if ping.get("is_my_turn"):
        if ping.get("active_entity_uuid") == entity_uuid:
            slot_client.end_turn(entity_uuid=entity_uuid)  # Force-end
```

This catches cases where Claude forgot to run `end` or the stream-json detection failed.

### `write_session_file()` (line 213) — Session Handoff

Writes the session file that `agent.py`'s `load_session()` reads:

```python
def write_session_file(slot, active_entity_uuid):
    """
    File format:
        Line 1: server_session_id
        Line 2: active entity UUID (becomes _current_entity_uuid)
        Lines 3+: other controlled entity UUIDs
    """
    lines = [slot.server_session_id, active_entity_uuid]
    for uuid in slot.entity_uuids:
        if uuid != active_entity_uuid:
            lines.append(uuid)
    Path(slot.session_file).write_text("\n".join(lines))
```

Active entity UUID is on line 2 — `ensure_session()` in agent.py picks it up and sets it as `_current_entity_uuid` so all commands target the right entity.

---

## 8. System Prompt Template

**File**: `cli/dnd_auto_prompt.md`

The template is read once by `generate_prompt_files()` and written per-slot with `{TOKEN}` and `{NOTEBOOK_PATH}` replaced.

**Key sections**:

1. **Session token**: Every command must use `source .venv/bin/activate && python -m cli.agent --token {TOKEN} <command>`

2. **"State Is In The Prompt"**: Claude is told the turn prompt includes map, entities, actions, combat log — no need to run `state` separately. After each action, inline state updates are returned.

3. **Command reference**: Full table of all agent CLI commands with syntax

4. **Attack mechanics**: Explains Extra Attack, target indices, multi-attack turns

5. **Rules**: Always run `end` last, don't retry failed commands, inspect unknowns

6. **How Actions Work**: Actions are dynamic — only appear when prerequisites pass (range, LOS, resources, action economy). "If you see 0 entity actions, move closer."

7. **Map format guide**: Explains TILE DETAILS, ASCII grid, entity tags, light levels, AoE annotations

8. **Multi-target spells**: Syntax for projectile spells (repeatable targets) vs unique-target spells

9. **Reactions**: Toggle handlers on/off with `toggle <name> off`

10. **Tactical priorities**: Scout → Environment → Focus fire → Avoid hazards → Dash wisely

---

## 9. Turn Prompt Assembly

**File**: `cli/prompt_builder.py`

`build_turn_prompt()` assembles 7 sections:

```
## {entity_name}'s Turn — Round {round_number}
You control the **{faction}** faction.
{series_info}

## Your Notebook
{notebook_content or "(empty — first turn)"}

## What Happened Since Your Last Turn
{combat_log_text}  ← FOW-filtered

## Entities
{entity_table_text}  ← visibility-filtered

## Map
{map_text}  ← FOV-filtered with AoE annotations

## Actions
{action_text}  ← dynamic, all affordability checks done

## Reminders
- Use commands with your token
- After Dash, run `actions`
- **Always run `end` as your last action**
```

The prompt is passed to `claude -p` as the primary input. Combined with the system prompt (from `--append-system-prompt-file`), Claude has everything needed to play a turn.

---

## 10. Combat Log Filtering

**File**: `cli/log_filter.py`

Two-layer filtering ensures fog of war applies to combat logs:

### Layer 1: Temporal Perception

"Could the observer perceive this event when it happened?"

Each combat log entry has `perceiver_uuids` — the set of entity UUIDs that could perceive the event at the time it occurred.

- If `perceiver_uuids` does NOT intersect with `controlled_uuids` → **fully anonymize**: all names become `"???"`, all coordinates become `"(?,?)"`
- The entry is KEPT (not dropped) so the player knows something happened

```
Original: "Skeleton Warrior attacks Hero for 7 damage at (2,7)"
Anonymized: "??? attacks ??? for ??? damage at (?,?)"
```

### Layer 2: Identity Anonymization

"Can the observer currently identify the entities involved?"

For perceived events, entity names are checked against `visible_entity_uuids`:
- Visible entities → show real name
- Hidden/invisible entities → replace name with `"???"`
- Movement entries with hidden sources → coordinates replaced with `"(?,?)"`

### Revealed Entities

When a Hidden/Invisible condition is removed mid-event-chain (e.g., AoE damage breaks Hidden), the entity's UUID is added to `revealed_entity_uuids`. These bypass both anonymization layers — the observer now knows who it was.

`revealed_entity_uuids` propagate from parent entries to sub-entries, so if a Fireball reveals a hidden entity, all damage sub-entries show the real name.

---

## 11. Visibility & FOV

### Per-Entity Visibility

`GET /visibility` returns per-entity FOV data:

```json
{
    "entity-uuid-1": {
        "visible_entities": ["uuid-a", "uuid-b"],
        "visible_cells": [[2,7], [3,7], ...],
        "seen_cells": [[2,7], [3,7], [10,5], ...],   // includes memory
        "sense_modes": [{"sense_type": "Darkvision", "range": 60}]
    }
}
```

### How Each Mode Uses Visibility

**vs AI** (`game_loop`): Uses hero's visibility for FOW display. `display.set_fow_visibility(vis_set, controlled)` filters the Rich TUI.

**PvP** (`game_loop` + `wait_for_opponent_turn`): Same as vs AI. Hero only sees what hero sees.

**Orchestrator** (`turn_loop`): Each faction gets its own visibility:
- When it's Hero's turn: `visibility[hero_uuid]` filters map, entities, combat log
- When it's Skeleton's turn: `visibility[skeleton_uuid]` filters everything
- `vis_set.update(slot.entity_uuids)` — always see own units regardless of FOV

**Spectator** (`spectate`): Configurable via `--fov`:
- `--fov global` (default): Omniscient view, see everything
- `--fov self`: Active entity's perspective, switches each turn

### Sense Mode Display

Light levels adjusted by sense modes in `format_map()` (agent.py lines 490-540):

```
(4,5): Floor, dark->dim    ← Darkvision shifts dark to dim
(4,5): Floor, mag-dark->bright  ← Truesight/Devil's Sight pierces magical darkness
```

---

## 12. Metrics & Logging

### TurnMetrics (orchestrator.py line 652)

Collected per turn from stream-json events:

| Metric | Source |
|--------|--------|
| `total_time_s` | Wall clock from start to turn-end detection |
| `prompt_build_s` | Time to build prompt (API calls + formatting) |
| `time_to_first_output_s` | Time until first text block from Claude |
| `time_to_first_action_s` | Time until first Bash tool use |
| `game_actions` | Count of agent CLI commands (Bash calls) |
| `thinking_steps` | Count of text blocks (reasoning) |
| `input_tokens` / `output_tokens` | From `result` event |
| `total_cost_usd` | From `result` event |

### Trajectory Files

Per-faction markdown files recording full prompt-response pairs:
- `game_logs/{timestamp}/trajectory_hero.md`
- `game_logs/{timestamp}/trajectory_monsters.md`

Written by `append_trajectory_turn()` (line 260) in background threads. Includes system prompt (first turn only), turn prompt, and Claude's full response with tool calls.

### Turn Log Files

Per-turn raw output: `game_logs/{timestamp}/turns/R{round}_T{turn}_{entity_name}_{slot}.log`

### Notebooks

Per-faction persistent files: `game_logs/{timestamp}/notebooks/hero.md`

- Created empty at series start
- Read into turn prompt each turn (truncated to last 1500 chars if >2000)
- Written by Claude during post-game reflection only (Write tool enabled)
- Persist across matches in best-of-N series

### Post-Game Reflection (line 956)

After encounter ends, `run_post_game_reflection()` is called for each slot:

```python
prompt = (
    f"The game is over.\n\n"
    f"Final entity status:\n{format_final_results(state)}\n\n"
    f"Please write a post-game reflection to your notebook..."
)
result = run_claude_turn(slot, prompt, max_turns=5)  # allow_write=True
```

Claude writes reflections about strategy, mechanics confusion, bugs, and improvement ideas.

---

## 13. Best-of-N Series

**Flags**: `--best-of N` (default 1)

### What Persists Across Matches

| Component | Persists? | Why |
|-----------|-----------|-----|
| `slot.token` | Yes | Same session file path |
| `slot.claude_session_id` | Yes | `--resume` maintains Claude's memory |
| `slot.notebook_path` | Yes | Notes accumulate |
| `slot.entity_uuids` | **No** | New entities each match |
| `slot.server_session_id` | **No** | Server sessions reset with game |
| `slot.combat_log_index` | Reset to 0 | New combat log each match |
| Game state | **No** | `start_pvp_game()` resets everything |

### Series Flow

```python
series_score = {"heroes": 0, "monsters": 0}
wins_needed = (BEST_OF + 1) // 2

for match_num in range(1, BEST_OF + 1):
    winner = run_single_match(...)
    series_score[winner] += 1

    if series_score[winner] >= wins_needed:
        break  # Series clinched
```

Series info string is injected into turn prompts:
```
**Series: Match 2 of 3 — Heroes 1, Monsters 0**
```

---

## 14. End-to-End Flows

### Flow A: Human vs AI (`python -m cli play fighter`)

```
1. User starts server:  uvicorn server.event_server:app --port 8000
2. User runs:           python -m cli play fighter
3. CLI calls:           POST /simulation/start-human?character_class=fighter
4. Server:              setup_arena_combat(pvp_mode=False)
                        → Hero: HumanController, Skeletons: MeleeAIController
                        → advance_encounter() auto-runs skeleton turns
                        → Returns hero_uuid + ai_actions (combat log from AI turns)
5. CLI calls:           POST /session/create (human)
                        POST /game/join (hero_uuid)
6. CLI enters:          game_loop()
7. On human turn:       render_display() → prompt_command() → execute_command()
                        → POST /action/{sid}/execute → display result
8. On AI turn:          wait_for_ai_turn() polls GET /encounter/current-turn
                        → Server calls advance_encounter() after human's end_turn
                        → MeleeAIController.get_next_action() runs in server loop
9. Loop until encounter ends
```

### Flow B: Human vs Claude (`python -m cli playpvp sorcerer`)

```
1. User starts server:  uvicorn server.event_server:app --port 8000
2. User runs:           python -m cli playpvp sorcerer
3. CLI calls:           POST /simulation/start-pvp?character_class=sorcerer
4. Server:              setup_arena_combat(pvp_mode=True)
                        → Hero: HumanController, Skeletons: ClaudeController
                        → advance_encounter() stops at first turn
5. CLI calls:           POST /session/create (human), POST /game/join (hero_uuid)
6. Claude runs:         python -m cli.agent connect
                        → POST /session/create (claude), POST /game/join (auto-assigns skeletons)
7. Claude runs:         python -m cli.agent watch
                        → Polls until turn, outputs unified prompt
8. On human turn:       CLI: prompt → execute → POST /action/execute
                        Agent: cmd_watch() polling, shows opponent combat log
9. On Claude turn:      CLI: wait_for_opponent_turn() polls /pvp/status + combat log
                        Agent: Claude reads prompt, runs move/attack/cast/end commands
10. After end:          Server calls advance_encounter() → stops at next controller
11. Loop until encounter ends
```

### Flow C: Claude vs Claude (`python -m cli spectate`)

```
1. User starts server:  uvicorn server.event_server:app --port 8000
2. User runs:           python -m cli spectate sorcerer --model claude-sonnet-4-5-20250929
3. spectate() spawns:   python -m cli.orchestrator --character-class sorcerer --model ...
4. Orchestrator:        generate_token() × 2 (hero, monsters)
                        generate_prompt_files() (bake tokens into system prompts)
5. Per match:           POST /simulation/start-pvp
                        POST /session/create (claude) × 2
                        POST /game/join (hero_uuids), /game/join (monster_uuids)
6. Turn loop:           For each turn:
                        a. spectator.get_state() → find active entity
                        b. get_slot_for_entity() → map to hero/monsters slot
                        c. spectator.get_visibility() → get FOV for active entity
                        d. spectator.get_combat_log(since=...) → filter by faction
                        e. build_turn_prompt() → assemble all sections
                        f. write_session_file() → /tmp/dnd_game/{token}_session.txt
                        g. run_claude_turn() → claude -p "..." subprocess
                           → Claude reads prompt, runs agent CLI commands via Bash
                           → "OK: Turn ended" detected → return immediately
                           → Background thread drains remaining output
                        h. verify_turn_ended() → force-end if Claude forgot
                        i. time.sleep(0.5) → brief pause
7. Spectate TUI:        Polls GET /state every 0.5s, renders full-screen Rich display
8. Post-game:           run_post_game_reflection() per faction (Write tool enabled)
9. Series:              Repeat from step 5 if best-of-N, score tracked
```

---

## 15. Key Design Decisions

### Why HumanController ≡ ClaudeController?

Both exit the `run_turn()` loop immediately. The server doesn't care WHO is providing actions — it just waits for HTTP requests to `/action/execute`. The controller type is only used in `advance_until_player()` for routing (`"waiting_for_human"` vs `"waiting_for_claude"` status) and display purposes.

### Why Not WebSockets for Turn Notification?

The system uses polling (0.5-2s intervals). This simplifies the architecture — no persistent connections to manage, no reconnection logic, no state synchronization issues. The tradeoff is latency (up to 2s for turn detection in agent mode).

### Why Subprocess Claude, Not API?

The orchestrator uses `claude -p` (Claude Code CLI) rather than the Anthropic API directly because:
1. **Tool use**: Claude needs to run Bash commands (agent CLI). The Claude Code CLI handles tool execution natively.
2. **Session continuity**: `--resume` maintains conversation history across turns/matches without manual context management.
3. **Stream parsing**: `--output-format stream-json` enables real-time spectator display and early turn-end detection.
4. **Tool restrictions**: `--allowedTools` constrains Claude to only agent CLI commands.

### Why `_clean_env()`?

Claude Code detects if it's running inside another Claude instance via environment variables. `_clean_env()` strips all `CLAUDE_*` env vars to prevent the recursive guard from blocking the subprocess.

### Why Early Return on Turn-End Detection?

When `"OK: Turn ended"` is detected in the stream, `run_claude_turn()` returns immediately while a background thread drains remaining output. This enables pipelining: the next entity's prompt is built and Claude subprocess started while the previous one is still outputting summary text.

### Why `allow_write=False` During Game Turns?

If Claude has Write tool access during game turns, it might write to notebooks while another thread is flushing trajectory logs — causing race conditions. Write is only enabled during post-game reflections when no concurrent activity occurs.
