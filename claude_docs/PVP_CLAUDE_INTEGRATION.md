# PvP Claude Integration — Architecture Design

## 1. Architecture Overview

### Core Principle

The human CLI (`cli/main.py`) is the **sole orchestrator**. It creates all server sessions, assigns entities to players, manages Claude subprocess lifecycles, and dispatches turns. Claude never polls — the orchestrator invokes `claude -p` when it's Claude's turn, blocking until Claude finishes.

### Player Assignment Model

The key abstraction replacing the hardcoded "human=Hero, Claude=Skeletons" pattern. A `PlayerSlot` describes who controls what:

```python
@dataclass
class PlayerSlot:
    slot_id: str                           # "human_1", "claude_alpha", "claude_bravo"
    player_type: Literal["human", "claude"]
    name: str                              # Display name ("Tommaso", "Claude Alpha")
    entity_uuids: List[str]                # Entities this player controls
    faction: str                           # "heroes", "monsters", etc.
    server_session_id: Optional[str]       # Server PlayerSession UUID (from POST /session/create)
    claude_code_session_id: Optional[str]  # --resume ID (None until first invocation)
    notebook_path: Optional[Path]          # /tmp/dnd_notebooks/{slot_id}.md
```

Game modes are just different `PlayerSlot` configurations — no code changes per mode:

| Mode | Slots |
|------|-------|
| **Classic PvP** | `human_1(Hero)`, `claude_alpha(Skeleton 1-3)` |
| **Per-monster Claude** | `human_1(Hero)`, `claude_1(Skel1)`, `claude_2(Skel2)`, `claude_3(Skel3)` |
| **Full AI (spectator)** | `claude_hero(Hero)`, `claude_monsters(Skel 1-3)` |
| **Mixed hero side** | `human_1(Hero1)`, `claude_ally(Hero2)`, `claude_monsters(Skel 1-3)` |

### Mapping to Existing Server Code (No Server Changes)

Each `PlayerSlot` maps 1:1 to the existing server session system:

| PlayerSlot field | Server concept | API |
|-----------------|----------------|-----|
| `server_session_id` | `PlayerSession.session_id` | `POST /session/create` → returns `session_id` |
| `entity_uuids` | `PlayerSession.controlled_entities` | `POST /game/join` with `entity_uuids` |
| Turn validation | `SessionManager.validate_action()` | Already checks entity ownership |
| Turn detection | `GameSession.is_player_turn()` | Already checks active entity ∈ session's entities |
| Entity→player mapping | `GameSession.entity_to_player` | Already maintained |

**No server changes needed.** The session system (`server/session.py`) already supports multiple sessions with per-entity ownership, turn validation, and the `is_player_turn()` check. The orchestrator just creates sessions via API instead of requiring manual `connect`.

### Game Loop Dispatch

The orchestrator replaces `wait_for_opponent_turn()` with direct dispatch:

```python
while encounter_active:
    active_uuid = turn_info["current_entity_uuid"]
    slot = orchestrator.get_slot_for_entity(active_uuid)

    if slot is None:
        # AI-controlled entity (MeleeAIController) — server auto-advances
        advance_and_check()
        continue

    if slot.player_type == "human":
        handle_human_turn(slot, ...)       # Existing TUI input loop
        notify_claude_slots(...)           # Background thinking updates (optional)
    elif slot.player_type == "claude":
        run_claude_turn(slot, ...)         # Blocking claude -p subprocess

    advance_and_check()
```

**Spectator mode**: When no slot has `player_type == "human"`, the loop just dispatches Claude turns and streams their output to the terminal. No human input phase, no blocking — pure observation.

## 2. Turn Lifecycle

### Per-Entity Invocation

Initiative order interleaves factions (e.g., Skel1 → Hero → Skel2 → Skel3). Each entity turn dispatches to its owning `PlayerSlot`. One `claude -p --resume` call per entity turn.

```
Round 1:
  Skel1 (claude_alpha) → claude -p --resume alpha_session "It's Skeleton 1's turn..."
  Hero  (human_1)      → human plays via Rich TUI
  Skel2 (claude_alpha) → claude -p --resume alpha_session "It's Skeleton 2's turn..."
  Skel3 (claude_alpha) → claude -p --resume alpha_session "It's Skeleton 3's turn..."
Round 2:
  ...
```

When multiple entities share a slot (e.g., all skeletons under `claude_alpha`), the same `--resume` session accumulates context across all their turns. Claude sees a continuous narrative of its faction's actions.

**Session ID capture** (from Agent SDK docs): First invocation returns `session_id` in JSON output. Subsequent calls use `--resume <session_id>`.

**ALWAYS use `--resume <session_id>`, NEVER `--continue`.** The `--continue` flag resumes the most recent conversation — with multiple Claude slots running concurrently, "most recent" is unpredictable and will cross-contaminate sessions. Explicit `--resume` with the stored session ID is the only safe option.

```python
# First turn (no resume — new session)
result = subprocess.run(
    ["claude", "-p", prompt, "--output-format", "json", ...],
    capture_output=True, text=True, cwd="/tmp/dnd_game"
)
session_id = json.loads(result.stdout)["session_id"]
slot.claude_code_session_id = session_id

# Subsequent turns (resume same session)
result = subprocess.run(
    ["claude", "-p", prompt, "--resume", session_id, "--output-format", "json", ...],
    capture_output=True, text=True, cwd="/tmp/dnd_game"
)
```

### Session File Protocol

Before each Claude invocation, the orchestrator writes `/tmp/dnd_agent_session.txt` with the slot's `server_session_id` and the active entity's UUID:

```python
def prepare_session_file(slot: PlayerSlot, active_entity_uuid: str):
    with open("/tmp/dnd_agent_session.txt", "w") as f:
        f.write(f"{slot.server_session_id}\n")
        f.write(f"{active_entity_uuid}\n")
        # Also include all controlled entities for multi-entity display
        for uuid in slot.entity_uuids:
            if uuid != active_entity_uuid:
                f.write(f"{uuid}\n")
```

The agent CLI's `ensure_session()` (`cli/agent.py:66`) already loads this file, and `ping_session()` auto-switches `_current_entity_uuid` to whichever controlled entity's turn it is. **No agent CLI changes needed for session loading.**

### Integration with Existing Server Flow

1. `setup_arena_combat()` at `server/event_server.py:225` creates entities with `ClaudeController` for non-human entities. `ClaudeController.can_continue_turn()` returns `False`, so the server waits for API commands.

2. `POST /action/end-turn` at `server/event_server.py:1404` calls `advance_encounter()` which auto-runs AI turns (entities with `MeleeAIController`) and stops at the next human/Claude-controlled entity.

3. The response from `end-turn` includes `entity_uuid` and `entity_name` for the next active entity. The orchestrator uses this to look up the owning `PlayerSlot` and dispatch.

4. `POST /session/ping` returns `is_my_turn`, `active_entity_uuid`, and `active_entity_name` — used by the agent CLI to detect its turn and switch active entity.

## 3. Turn Flow (Simple)

Each Claude turn is a blocking `subprocess.run` call. No background thinking, no concurrency — just:

```
Build turn prompt → claude -p --resume → Claude plays till `end` → parse output → next turn
```

The turn prompt includes full state (map, entities, actions, combat log, notebook), so Claude has everything it needs. One `--resume` call per entity turn, sequential, no overlap.

**Future enhancement**: Interleaved background thinking during human turns (non-blocking `Popen`, state machine to avoid concurrent `--resume` on same session). Not in v1 — the simple sequential model is sufficient and avoids concurrency complexity.

**Concurrency note for the record**: The `claude` CLI docs say concurrent `--resume` calls to the same session interleave messages "like two people writing in the same notebook" — nothing corrupts but context becomes jumbled. There's also no reliable way to gracefully interrupt a running `claude -p` (SIGINT has known bugs during tool calls). These are the reasons to keep v1 simple.

## 4. Turn Prompt Design

### Rich Inlined Prompt

The turn prompt inlines all context so Claude doesn't waste tool calls on `state` or `actions`:

```python
def build_turn_prompt(slot: PlayerSlot, active_entity_uuid: str,
                      state: dict, actions: dict, combat_log: List[dict],
                      notebook_content: str, round_number: int) -> str:
    entity_name = get_entity_name(state, active_entity_uuid)
    entities = state.get("entities", [])
    visibility = get_visibility_for(slot)  # GET /visibility

    sections = []

    # Header
    sections.append(
        f"## {entity_name}'s Turn — Round {round_number}\n"
        f"You control the **{slot.faction}** faction."
    )

    # Notebook (inlined to save a Read tool call)
    sections.append(
        f"## Your Notebook\n"
        f"{notebook_content or '(empty — first turn)'}"
    )

    # Combat log since last turn
    if combat_log:
        log_lines = []
        for entry in combat_log:
            log_lines.extend(format_combat_log_entry(entry))  # from cli/agent.py:111
        sections.append(
            f"## What Happened Since Your Last Turn\n" +
            "\n".join(log_lines)
        )

    # Entity status table
    sections.append(format_entities(entities, visible_entity_uuids=visibility,
                                     my_entity_uuid=active_entity_uuid,
                                     controlled_uuids=slot.entity_uuids))

    # ASCII map
    sections.append(format_map(state, visible_entity_uuids=visibility,
                                my_entity_uuid=active_entity_uuid))

    # Available actions
    sections.append(format_actions(actions, entity_name))

    # Instructions
    sections.append(
        "## Instructions\n"
        "State and actions are provided above to save tool calls. "
        "You can ALWAYS run `state`, `actions`, or `inspect X Y` to get full up-to-date data "
        "(e.g., after Dash for new movement targets, or to see all AoE positions).\n\n"
        "1. Execute your actions: `move X Y`, `attack N`, `cast <spell> [N|X Y]`, etc.\n"
        "2. After Dash, run `actions` to see updated movement targets\n"
        "3. Use `inspect X Y` on unknown map symbols\n"
        "4. Update your notebook with observations and strategy\n"
        "5. ALWAYS run `end` to end your turn"
    )

    return "\n\n".join(sections)
```

### Data Sources

The orchestrator calls the same API endpoints the agent CLI uses, then formats with the existing agent format functions:

| Data | Endpoint | Formatter |
|------|----------|-----------|
| Map + entities | `GET /state` | `format_map()` from `cli/agent.py:163` |
| Entity table | (same state) | `format_entities()` from `cli/agent.py:232` |
| Available actions | `GET /entity/{uuid}/available-actions` | `format_actions()` from `cli/agent.py:285` |
| Combat log | `GET /combat-log?since=N` | `format_combat_log_entry()` from `cli/agent.py:111` |
| Visibility | `GET /visibility` | Used as filter parameter |

All format functions are already importable from `cli.agent` — no extraction needed.

### AoE Spell Targeting in Prompts

AoE spells (Fireball, Thunderwave, etc.) return position-based targets with faction-aware hit data. The API response already filters `affected_count` and `affected_entity_names` by the spell's `valid_target_filter` — so for offensive spells, these only count **enemies**, not allies. This is computed in `_compute_aoe_at_position()` (`dnd/entity.py:2035-2052`).

`format_actions()` (`cli/agent.py:322`) displays AoE targets sorted by `affected_count` (best positions first) with entity names:

```
[SPELL] Fireball: 45 positions (action) - READY
    Targets: (5,3) hits 3: Skeleton 1, Skeleton 2, Goblin, (4,3) hits 2: Skeleton 1, Goblin, ...
```

For the inlined prompt, the orchestrator summarizes AoE positions to avoid bloat:

```python
def summarize_position_targets(actions: dict, state: dict, faction: str) -> dict:
    """Trim position_actions for prompt. Full data always available via `actions` command."""
    enemies = get_enemy_positions(state, faction)
    for action in actions.get("position_actions", []):
        targets = action.get("valid_targets", [])
        total = len(targets)
        if total <= 10:
            continue  # Small enough to show in full

        template = action.get("template_name", "")
        is_spell = action.get("action_category") == "spell"

        if is_spell:
            # AoE spells: show top 5 by affected_count (enemies only)
            sorted_targets = sorted(targets, key=lambda t: t.get("affected_count", 0), reverse=True)
            action["valid_targets"] = sorted_targets[:5]
        else:
            # Move/Jump: show 5 nearest to closest enemy
            sorted_targets = sort_by_nearest_enemy(targets, enemies)
            action["valid_targets"] = sorted_targets[:5]

        action["_total_targets"] = total
        action["_summarized"] = True
    return actions
```

### Commands Always Available

The prompt inlines state and actions to save tool calls, but Claude can **always** run commands to get full, up-to-date data:

- `state` — full map, all entities, conditions, lighting (useful after environment changes)
- `actions` — complete target lists including all AoE positions (useful after Dash or when prompt was summarized)
- `inspect X Y` — detailed tile info for unknown symbols

The instructions in the prompt say "don't call `state`/`actions` unless something changed" — this is a hint to save tool calls, not a restriction. Claude should run `actions` whenever it needs the full unsummarized target list (e.g., to find a specific AoE position not in the top 5).

## 5. Streaming & Real-Time Display

### Stream Format

During Claude turns, the orchestrator streams Claude's activity to the human's terminal using `--output-format stream-json --verbose --include-partial-messages`. This emits newline-delimited JSON events — each line is a JSON object with a `type` field.

From the Agent SDK docs, the stream event structure is:
- `type: "stream_event"` with `event.delta.type == "text_delta"` → Claude's reasoning text
- `type: "tool_use"` → tool invocation (Bash commands)
- `type: "tool_result"` → tool output
- `type: "result"` → final result with `session_id`

### Session ID Capture

The `session_id` is in the final `result` event or extractable via JSON output:

```python
# Non-streaming (blocking): capture session_id from json output
result = subprocess.run(
    ["claude", "-p", prompt, "--output-format", "json", ...],
    capture_output=True, text=True, cwd="/tmp/dnd_game"
)
output = json.loads(result.stdout)
session_id = output["session_id"]  # Always present in json output

# Streaming: session_id appears in result event at end of stream
# Also extractable with jq: | jq -r 'select(.type == "result") | .session_id'
```

### Streaming Turn Invocation

```python
def run_claude_turn_streaming(slot: PlayerSlot, prompt: str) -> dict:
    cmd = [
        "claude", "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--allowedTools",
        f"Bash(cd {PROJECT_DIR} && source .venv/bin/activate && python -m cli.agent *)",
        f"Read({NOTEBOOK_DIR}/*)",
        f"Write({NOTEBOOK_DIR}/*)",
        "--append-system-prompt-file", SKILL_PATH,
        "--max-turns", "15",
    ]
    if slot.claude_code_session_id:
        cmd.extend(["--resume", slot.claude_code_session_id])

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd="/tmp/dnd_game", text=True
    )

    session_id = None
    for line in process.stdout:
        line = line.strip()
        if not line:
            continue
        event = json.loads(line)
        # Capture session_id from result event
        if event.get("type") == "result":
            session_id = event.get("session_id", session_id)
        display_stream_event(event)

    process.wait()
    return {"session_id": session_id, "returncode": process.returncode}
```

### Parsing Stream Events for Display

```python
def display_stream_event(event: dict):
    event_type = event.get("type")

    if event_type == "tool_use":
        # Show agent CLI commands Claude is running
        tool = event.get("tool", "")
        if tool == "Bash":
            cmd = event.get("input", {}).get("command", "")
            if "cli.agent" in cmd:
                agent_cmd = cmd.split("cli.agent")[-1].strip()
                console.print(f"  [dim]Claude:[/dim] > {agent_cmd}")

    elif event_type == "tool_result":
        # Show command output (first line)
        content = event.get("content", "")
        if content:
            first_line = content.split("\n")[0][:120]
            console.print(f"  [dim]{first_line}[/dim]")

    elif event_type == "stream_event":
        # Streaming text deltas — Claude's reasoning
        delta = event.get("event", {}).get("delta", {})
        if delta.get("type") == "text_delta":
            text = delta.get("text", "")
            if text:
                # Accumulate and show periodically (don't spam per-token)
                pass  # Buffer and display in Rich Live panel
```

### Rich Live Panel

During Claude's turn, display a Rich `Live` panel replacing the current `wait_for_opponent_turn()` polling:

```python
with Live(Panel("Claude is thinking...", title="Opponent Turn"), refresh_per_second=4) as live:
    for line in process.stdout:
        event = json.loads(line.strip())
        update_panel(live, event)  # Append commands/results to panel
    # After turn completes, refresh full TUI with updated state
```

## 6. Error Handling & Recovery

### Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Non-zero exit code | `process.returncode != 0` | Check if turn ended via `POST /session/ping`. If `is_my_turn` still True → force `POST /action/end-turn`. |
| Timeout (120s default) | `process.wait(timeout=120)` raises `TimeoutExpired` | `process.kill()`, force end turn. |
| Didn't call `end` | Process exited cleanly but `is_my_turn` still True | Force `POST /action/end-turn`. Log warning. |
| Thinking interrupted | Background `Popen` killed or timed out | Acceptable loss — turn prompt has full state. Clear slot state to IDLE. |
| Session file conflict | Two Claude slots active simultaneously | Orchestrator serializes turn dispatch — never happens. |

### Force End Turn

```python
def force_end_turn(slot: PlayerSlot):
    """Force end a Claude slot's turn via server API."""
    response = httpx.post(
        f"{SERVER_URL}/action/end-turn",
        json={"entity_uuid": active_entity_uuid},
        headers={"X-Session-ID": slot.server_session_id}
    )
    if response.status_code == 200:
        console.print("[yellow]Claude's turn force-ended (timeout/error)[/yellow]")
    else:
        console.print(f"[red]Failed to force end turn: {response.text}[/red]")
```

### Crash Recovery

Persist slot data to `/tmp/dnd_game/session_recovery.json` after every turn:

```python
recovery_data = {
    "game_id": game_session_id,
    "slots": [
        {
            "slot_id": slot.slot_id,
            "player_type": slot.player_type,
            "entity_uuids": slot.entity_uuids,
            "server_session_id": slot.server_session_id,
            "claude_code_session_id": slot.claude_code_session_id,
            "combat_log_index": slot.combat_log_index,
        }
        for slot in all_slots
    ]
}
```

On `playpvp` restart, check for this file:
1. Ping the server — is the game still active?
2. If yes, reload slot data and reconnect. Claude Code sessions resume via `--resume`.
3. If no (server restarted), discard recovery file and start fresh.

## 7. Context Isolation

### Problem

Claude Code auto-discovers `CLAUDE.md` from the cwd and walks UP parent directories. Running `claude -p` from the project root would inject the full 500+ line architecture CLAUDE.md — the game-playing Claude doesn't need engine internals.

### Solution

Run `claude -p` from `/tmp/dnd_game/` (no CLAUDE.md in this directory or any parent):

```python
SCRATCH_DIR = "/tmp/dnd_game"
os.makedirs(SCRATCH_DIR, exist_ok=True)

subprocess.run(
    ["claude", "-p", turn_prompt,
     "--append-system-prompt-file", f"{PROJECT_DIR}/cli/dnd_auto_prompt.md",
     "--allowedTools",
     # NOTE: space before * is critical — prefix matching rule from Agent SDK docs.
     # "Bash(git diff *)" matches "git diff HEAD" but NOT "git diff-index"
     f"Bash(cd {PROJECT_DIR} && source .venv/bin/activate && python -m cli.agent *)",
     f"Read({NOTEBOOK_DIR}/ *)",
     f"Write({NOTEBOOK_DIR}/ *)",
     "--output-format", "stream-json",
     "--verbose",
     "--include-partial-messages",
     "--max-turns", "15"],
    cwd=SCRATCH_DIR  # Clean directory, no CLAUDE.md
)
```

**`--allowedTools` syntax** (from Agent SDK docs): Uses permission rule prefix matching. The trailing ` *` (space + asterisk) enables prefix matching — `Bash(python -m cli.agent *)` allows any command starting with `python -m cli.agent `. The space before `*` matters: without it, `cli.agent*` would also match `cli.agentX`.

**What game-Claude gets:**
- Claude Code default system prompt (tool usage instructions, Bash formatting)
- `cli/dnd_auto_prompt.md` content (orchestrated command reference, tactics, map symbols)
- Turn-specific prompt (faction, entity, state, actions, notebook)
- **NOT** the full engine CLAUDE.md

**What game-Claude can access:**
- `Bash` — only `python -m cli.agent *` (sandboxed to agent commands)
- `Read` / `Write` — only notebook files in `/tmp/dnd_notebooks/`

### Per-Slot Skill File (Optional)

For advanced scenarios where different Claude slots need different instructions (e.g., a Claude playing heroes vs monsters), generate a slot-specific skill file at runtime:

```python
def generate_skill_file(slot: PlayerSlot) -> Path:
    """Generate a slot-specific SKILL.md with faction name and paths filled in."""
    template = Path(f"{PROJECT_DIR}/cli/dnd_auto_prompt.md").read_text()
    customized = template.replace("{FACTION}", slot.faction)
    customized = customized.replace("{NOTEBOOK_PATH}", str(slot.notebook_path))

    skill_path = Path(f"/tmp/dnd_game/skill_{slot.slot_id}.md")
    skill_path.write_text(customized)
    return skill_path
```

For v1, a single generic SKILL.md + context in the prompt is sufficient.

## 8. Notebook System

### Location and Lifecycle

```
/tmp/dnd_notebooks/
├── claude_alpha.md        # claude_alpha slot's notebook
├── claude_bravo.md        # claude_bravo slot's notebook
└── ...
```

Created by the orchestrator at game start (empty files). Claude writes to them during turns. Deleted on game end or restart.

### Inlining in Turn Prompt

The notebook contents are inlined in the turn prompt to save Claude a `Read` tool call:

```python
notebook_content = ""
if slot.notebook_path and slot.notebook_path.exists():
    notebook_content = slot.notebook_path.read_text()

# Truncate if too long (context budget)
MAX_NOTEBOOK_CHARS = 2000
if len(notebook_content) > MAX_NOTEBOOK_CHARS:
    # Keep the last 1500 chars (most recent notes are most relevant)
    notebook_content = "...(truncated)...\n" + notebook_content[-1500:]
```

### What Claude Writes

The notebook is free-form. Claude might write:

```markdown
## Turn 3 — Skeleton 2
- Hero is a sorcerer — has Lightning Bolt (DEX save DC 15, ~25 damage)
- Hero ran south after casting — prefers hit-and-run
- Spike Growth trap active around (3,11) to (4,12) — AVOID
- There's a lever at (1,2) — might deactivate the trap
- Skeleton 1 is dead (caught in Spike Growth turn 2)
- Strategy: Skeleton 2 pulls lever, Skeleton 3 flanks from north
```

### Write Permissions

Claude needs `Write` access to the notebook directory. The `--allowedTools` flag scopes this:

```
--allowedTools "Write(/tmp/dnd_notebooks/*)"
```

## 9. Game Instructions: Skill vs System Prompt

Two separate instruction files for the two invocation modes:

| Skill | File | Invocation |
|-------|------|------------|
| **Interactive** | `.claude/skills/dnd_manual/SKILL.md` | `/dnd_manual` slash command inside a Claude Code session |
| **Orchestrated** | `cli/dnd_auto_prompt.md` | `--append-system-prompt-file` flag on `claude -p` subprocess |

**Important** (from Agent SDK docs): User-invoked skills (slash commands) are only available in interactive mode. In `-p` mode, skills aren't available — the orchestrated prompt is injected as a system prompt file via `--append-system-prompt-file`.

### Interactive Skill (`.claude/skills/dnd_manual/SKILL.md`) — Keep As-Is

The existing SKILL.md stays unchanged. It has the full `connect → watch → play → end → watch` loop, all commands, tactical priorities, map symbols. Used when a developer opens a Claude Code session and wants to manually play or debug.

No changes needed — it already works.

### Orchestrated System Prompt (`cli/dnd_auto_prompt.md`) — New

System prompt file for `claude -p` subprocesses. No connect/watch (session is pre-configured), assumes state is in the prompt, has notebook instructions, emphasizes `end`. Not a skill — injected via `--append-system-prompt-file`.

```markdown
# D&D PvP — Orchestrated Turn

You are playing as the **{FACTION}** faction. Your session is pre-configured — do NOT run `connect` or `watch`.

## State Is In The Prompt

The turn prompt includes: map, entity table, available actions, combat log, and your notebook.
Use this data directly. Run `state` or `actions` only when state changes mid-turn (after Dash, door interaction, etc.).

All commands: `cd {PROJECT_DIR} && source .venv/bin/activate && python -m cli.agent <command>`

## Commands

| Command | When To Use |
|---------|-------------|
| `move X Y` | Move to position — pick from listed targets |
| `jump X Y` | Jump to position |
| `attack N` | Attack target by entity action index |
| `cast <spell> [N\|X Y]` | Cast spell at target index or position |
| `self <name>` | Self-action (Dash, Dodge, Disengage, Hide) |
| `dash` / `dodge` / `disengage` | Shortcuts |
| `use <name\|N>` | Use object/item (Open Door, Pull Lever, etc.) |
| `inspect X Y` | Inspect unknown tile/symbol |
| `state` | Refresh full state (only if needed) |
| `actions` | Refresh full action list (after Dash, or to see all AoE positions) |
| `end` | **End your turn — REQUIRED, always run this last** |

## Rules

1. **ALWAYS run `end`** to finish your turn. Timeout force-ends if you don't.
2. **Pick positions from listed targets only.** Never guess.
3. **After Dash, run `actions`** — movement targets expand.
4. **Inspect unknown symbols** (`inspect X Y`) before moving near them.
5. **Update your notebook** before ending.

## Notebook

Your notebook persists between turns. Before running `end`, write updated observations:
- Enemy abilities/spells/patterns observed
- Hazards and terrain discovered
- Strategy for next turns
- Faction status (alive, HP, conditions)

## Tactical Priorities

1. Scout: `inspect` unknowns, check map layout
2. Environment: doors, levers, deactivate traps
3. Focus fire: concentrate on one target
4. Avoid hazards: don't repeat a path that killed an ally
5. Dash wisely: extra movement but costs your action

## Map Symbols

| Symbol | Meaning |
|--------|---------|
| `@` | Your active entity |
| `S` | Your allies (same faction) |
| `H` | Enemy |
| `#` | Wall |
| `.` | Floor |
| `~` | Water |
| `π` | Door |
| `θ`, `λ`, `♦` | Objects — `inspect X Y` to identify |
```

## 10. Implementation Spec

### Files Changed

| File | Change | Key Details |
|------|--------|-------------|
| `claude_docs/PVP_CLAUDE_INTEGRATION.md` | **Rewrite** | This design doc |
| `cli/claude_opponent.py` | **New** | `PlayerSlot`, `ClaudeSlotManager` (subprocess lifecycle), `Orchestrator` (multi-slot coordination, turn dispatch, crash recovery) |
| `cli/prompt_builder.py` | **New** | `build_turn_prompt()`, `summarize_position_targets()`. Imports `format_map`, `format_entities`, `format_actions`, `format_combat_log_entry` from `cli/agent.py`. Calls server API endpoints and formats into prompt strings. |
| `cli/main.py` | **Modify** | `playpvp()`: create PlayerSlots, set up Orchestrator, create server sessions via API. New `game_loop_pvp()` replacing `game_loop(pvp_mode=True)` + `wait_for_opponent_turn()`. Streaming display panel for Claude turns. Spectator mode when no human slots. |
| `cli/agent.py` | **Minor** | Make `SESSION_FILE` path configurable via `DND_SESSION_FILE` env var (default unchanged). Format functions already importable — no changes needed. All commands stay as-is. |
| `.claude/skills/dnd_manual/SKILL.md` | **No change** | Interactive skill — stays as-is for manual play/debugging inside a Claude Code session. |
| `cli/dnd_auto_prompt.md` | **New** | System prompt for `claude -p` subprocess — stripped-down instructions, no connect/watch, assumes state in prompt, notebook protocol. Injected via `--append-system-prompt-file`. See section 9. |
| `server/*` | **None** | No server changes. Existing session system, action validation, turn advancement, combat log all work as-is. |

### `cli/claude_opponent.py` — Module Structure

```python
"""
Claude opponent management for PvP games.

Manages Claude Code subprocess lifecycles, turn dispatch, background thinking,
and crash recovery.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional
import json
import os
import subprocess

# --- Data ---

@dataclass
class PlayerSlot:
    slot_id: str
    player_type: Literal["human", "claude"]
    name: str
    entity_uuids: List[str]
    faction: str
    server_session_id: Optional[str] = None
    claude_code_session_id: Optional[str] = None
    notebook_path: Optional[Path] = None
    combat_log_index: int = 0


# --- Slot Manager ---

class ClaudeSlotManager:
    """Manages a single Claude slot's subprocess lifecycle."""

    def __init__(self, slot: PlayerSlot, project_dir: str, skill_path: str):
        ...

    def run_turn(self, prompt: str, timeout: int = 120) -> dict:
        """Blocking turn invocation. Returns parsed output with session_id."""
        ...

    def force_end_turn(self, server_url: str, active_entity_uuid: str):
        """Force end via server API if Claude didn't call `end`."""
        ...


# --- Orchestrator ---

class Orchestrator:
    """Coordinates multiple PlayerSlots for a PvP game."""

    def __init__(self, slots: List[PlayerSlot], project_dir: str):
        ...

    def get_slot_for_entity(self, entity_uuid: str) -> Optional[PlayerSlot]:
        """Look up which slot controls an entity."""
        ...

    def dispatch_turn(self, active_entity_uuid: str, state: dict, actions: dict):
        """Dispatch to the correct slot (human input or Claude subprocess)."""
        ...

    def save_recovery(self, path: str = "/tmp/dnd_game/session_recovery.json"):
        """Persist slot data for crash recovery."""
        ...

    def load_recovery(self, path: str = "/tmp/dnd_game/session_recovery.json") -> bool:
        """Attempt to restore from crash recovery file."""
        ...
```

### `cli/prompt_builder.py` — Module Structure

```python
"""
Prompt construction for Claude PvP turns.

Imports format functions from cli/agent.py and calls server API endpoints
to build rich turn prompts with inlined state, actions, and notebook.
"""

from typing import Dict, List, Optional
from cli.agent import format_map, format_entities, format_actions, format_combat_log_entry

def build_turn_prompt(
    slot: 'PlayerSlot',
    active_entity_uuid: str,
    state: dict,
    actions: dict,
    combat_log: List[dict],
    round_number: int,
) -> str:
    """Build the full turn prompt with inlined state, actions, and notebook."""
    ...

def summarize_position_targets(
    actions: dict,
    state: dict,
    faction: str,
    max_targets: int = 5,
) -> dict:
    """Trim position_actions to show only nearest targets + total count."""
    ...
```

## 11. Open Questions

1. **`--output-format stream-json` fields**: Need to test with actual `claude` CLI to confirm exact JSON structure for `tool_use`, `tool_result`, `assistant`, and where `session_id` appears in the stream. The field names above are best-guess based on documentation.

2. **Per-slot vs generic skill file**: v1 uses one SKILL.md with faction name injected via the turn prompt. If Claude slots need meaningfully different instructions (e.g., "you're the heroes, play defensively" vs "you're the monsters, be aggressive"), generate per-slot skill files at runtime.

3. **Token/cost tracking**: `--output-format json` includes `usage` with `input_tokens` and `output_tokens`. Track per-slot per-turn for visibility. Not critical for Max subscription but useful for debugging prompt bloat.

## Appendix: Dual-Mode Architecture

### Both Systems Coexist

The orchestrated mode (`game_loop_pvp()` + `claude -p`) and the interactive mode (`connect → watch → play`) run on the **same server session infrastructure**. They are not mutually exclusive:

- **Orchestrated mode**: `playpvp` creates sessions programmatically, dispatches Claude turns via subprocess. This is the primary play mode.
- **Interactive mode**: A developer opens a Claude Code session, runs `connect`, `watch`, plays manually. This is for debugging, testing, and development.

Both modes can even run simultaneously — the server doesn't care how commands arrive, only that the session owns the entity and it's that entity's turn.

### What Changes in CLI

| Component | Change |
|-----------|--------|
| `cli/claude_opponent.py` | **New** — Orchestrator, PlayerSlot, ClaudeSlotManager |
| `cli/prompt_builder.py` | **New** — Turn prompt construction |
| `cli/main.py` | **Add** `game_loop_pvp()` alongside existing `game_loop()`. `playpvp` command uses new loop. Old `wait_for_opponent_turn()` stays — used by `game_loop(pvp_mode=True)` if someone still wants the old flow. |
| `cli/agent.py` | **Keep everything** — `connect`, `watch`, `disconnect`, all commands. Add `DND_SESSION_FILE` env var for session file path configurability. |
| `.claude/skills/dnd_manual/SKILL.md` | **No change** — Interactive skill stays as-is |
| `cli/dnd_auto_prompt.md` | **New** — System prompt for `claude -p` subprocess |
| `server/*` | **No changes** |

### Migration Path

1. Implement `cli/claude_opponent.py` + `cli/prompt_builder.py`
2. Add `game_loop_pvp()` to `cli/main.py` alongside existing `game_loop()`
3. Update `playpvp` command to use new loop (old loop available via flag if needed)
4. Create `cli/dnd_auto_prompt.md` (system prompt for subprocess)
5. Test classic PvP (human vs 1 Claude) with orchestrator
6. Test interactive mode still works (`connect → watch → play` via `/dnd_manual` skill)
7. Test per-monster Claude mode
8. Test spectator mode (Claude vs Claude)
