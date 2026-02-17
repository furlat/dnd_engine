# PvP Claude Integration — Design Doc

## Problem

The current PvP architecture has Claude running as a separate process that **polls** the server every 2 seconds via `cmd_watch()` to detect its turn. This is wasteful and fragile — it requires the user to manually start a Claude Code session, run `connect`, then `watch`, and hope the polling stays in sync.

## Proposed Design: Per-Turn Invocation

Instead of Claude polling, the **human CLI drives Claude's turns** via `claude -p` subprocess calls. When it's Claude's turn, the human CLI invokes Claude directly, Claude takes its actions, and control returns.

### Flow

```
Human starts playpvp
  │
  ├── Server creates encounter (Hero vs Skeletons)
  ├── Human session created, Hero assigned
  ├── Claude session(s) created (one per enemy faction)
  │
  └── Game Loop:
        ├── Human's turn → human plays via Rich CLI
        ├── Human ends turn
        ├── Claude's turn → human CLI invokes:
        │     claude -p "<turn prompt>" \
        │       --resume <session_id> \
        │       --output-format json \
        │       --allowedTools "Bash(...)" "Read" "Write" \
        │       --append-system-prompt-file /path/to/dnd/SKILL.md \
        │       --max-turns 15
        │     (run from /tmp/dnd_game/ — NOT project root)
        │
        ├── Claude takes actions (move, attack, use, end)
        ├── claude -p returns (blocking)
        ├── Parse JSON output → get session_id for next --resume
        └── Loop back to human's turn
```

### Context Isolation: Preventing CLAUDE.md Leakage

**Problem**: Claude Code auto-discovers CLAUDE.md from the cwd and walks UP parent directories. Running `claude -p` from the project root would inject the full architecture CLAUDE.md (~500 lines of engine internals) — the game-playing Claude doesn't need any of that.

**Behavior of prompt flags**:
| Flag | Loads CLAUDE.md? | Use case |
|------|-----------------|----------|
| `--append-system-prompt` | YES — adds on top of defaults + CLAUDE.md | Not suitable |
| `--system-prompt` | NO — replaces everything (loses Claude Code defaults) | Last resort |
| Run from outside project tree | NO — no CLAUDE.md in cwd or parents | Best approach |

**Solution**: Run `claude -p` from a **scratch directory** outside the project tree (e.g., `/tmp/dnd_game/`). This preserves Claude Code's default system prompt (tool usage, Bash formatting, etc.) while avoiding CLAUDE.md. The game skill is injected via `--append-system-prompt-file` pointing to the absolute path of the SKILL.md.

```python
# Scratch dir — no CLAUDE.md here or in any parent
os.makedirs("/tmp/dnd_game", exist_ok=True)

subprocess.run(
    ["claude", "-p", turn_prompt,
     "--append-system-prompt-file", f"{PROJECT_DIR}/.claude/skills/dnd/SKILL.md",
     "--allowedTools",
     f"Bash(cd {PROJECT_DIR} && source .venv/bin/activate && python -m cli.agent *)",
     "Read", "Write",
     "--output-format", "json"],
    cwd="/tmp/dnd_game"  # Clean directory, no CLAUDE.md
)
```

**What the game-Claude gets**:
- Claude Code default system prompt (tool usage instructions)
- `.claude/skills/dnd/SKILL.md` content (command reference, tactics, map symbols)
- Turn-specific prompt (faction, entity, notebook)
- **NOT** the full engine CLAUDE.md

### Key Mechanism: `--resume <session_id>`

Each `claude -p` invocation with `--output-format json` returns a `session_id` in the response. By passing `--resume <session_id>` on the next invocation, Claude continues the **same conversation** — it remembers the map layout, enemy positions, its strategy, what happened on previous turns.

```python
# First invocation (no resume — new session)
result = subprocess.run(
    ["claude", "-p", turn_prompt, "--output-format", "json",
     "--allowedTools", "Bash(source .venv/bin/activate && python -m cli.agent *)"],
    capture_output=True, text=True, cwd=project_dir
)
output = json.loads(result.stdout)
session_id = output["session_id"]  # Save this

# Subsequent invocations (resume same session)
result = subprocess.run(
    ["claude", "-p", turn_prompt, "--resume", session_id,
     "--output-format", "json",
     "--allowedTools", "Bash(source .venv/bin/activate && python -m cli.agent *)"],
    capture_output=True, text=True, cwd=project_dir
)
```

### Multi-Faction Support

Each enemy faction gets its own Claude session:

```
Hero (human)         → playpvp CLI
Skeleton faction     → claude session A (--resume skeleton_session_id)
Goblin faction       → claude session B (--resume goblin_session_id)
```

Each session:
- Has its own conversation context (remembers only what that faction has seen)
- Develops independent strategy
- Gets invoked in turn order when any entity of that faction acts

```python
# In playpvp game loop
faction_sessions: Dict[str, str] = {}  # faction_name → session_id

for turn in encounter_turns:
    entity = turn.entity
    if entity.faction == human_faction:
        # Human plays
        human_turn()
    else:
        # Claude plays for this faction
        session_id = faction_sessions.get(entity.faction)
        result = invoke_claude(session_id, entity, game_state)
        faction_sessions[entity.faction] = result["session_id"]
```

## Session Notebooks

Each Claude session gets a **notebook file** — a scratchpad for persisting observations, strategy, and notes between turns. Since each `claude -p` call is a fresh process (even with `--resume`), the notebook gives Claude a way to explicitly save information it wants to remember.

### Location

```
/tmp/dnd_notebooks/
├── skeleton_faction.md    # Skeleton faction's notes
├── goblin_faction.md      # Goblin faction's notes
└── ...
```

Or within the project:
```
.claude/notebooks/
├── skeleton_faction.md
└── goblin_faction.md
```

### Usage

Claude is told about its notebook in the turn prompt and allowed to Read/Write it:

```
--allowedTools "Bash(source .venv/bin/activate && python -m cli.agent *)" "Read" "Write"
```

Turn prompt includes:
```
Your notebook is at: .claude/notebooks/{faction_name}.md
Use it to track observations, enemy patterns, and strategy between turns.
Read it at the start of each turn. Write to it before ending your turn.
```

### What Claude Writes

The notebook is free-form. Claude might write:
```markdown
## Turn 3 Notes
- Hero is a sorcerer — has Lightning Bolt (DEX save DC 15, ~25 damage)
- Hero ran south after casting — prefers hit-and-run
- Spike Growth trap active around (3,11) to (4,12) — AVOID
- There's a lever at (1,2) — might deactivate the trap
- Strategy: send one skeleton to pull lever, others flank from north
```

### Notebook in the Prompt

The turn prompt can optionally **inline** the notebook contents so Claude doesn't need to spend a tool call reading it:

```python
notebook_path = f".claude/notebooks/{faction_name}.md"
notebook_content = ""
if os.path.exists(notebook_path):
    with open(notebook_path) as f:
        notebook_content = f.read()

turn_prompt = f"""
It's your turn. You control the {faction_name} faction.

YOUR NOTEBOOK (from previous turns):
{notebook_content}

Take your turn: check state, plan, execute actions, end turn.
Update your notebook with observations before ending.
"""
```

## Turn Prompt Design

The prompt sent to Claude each turn should include:

```python
turn_prompt = f"""
It's {entity_name}'s turn (Round {round_number}).
You control the {faction_name} faction ({n_alive} alive).

YOUR NOTEBOOK:
{notebook_content}

Instructions:
1. Run `state` to see the current map and entity positions
2. Run `actions` to see what you can do
3. Use `inspect X Y` on any unknown map symbols
4. Execute your actions (move, attack, use, cast, etc.)
5. Run `end` when done
6. Write updated observations to your notebook at {notebook_path}
"""
```

## Changes Required

### `cli/main.py` — playpvp command

1. After creating the encounter, create Claude session(s) via the agent CLI `connect` command (or directly via server API)
2. In `game_loop`, replace `wait_for_opponent_turn()` polling with `invoke_claude()` subprocess call
3. Track `faction_sessions` dict mapping faction names to Claude session IDs
4. Create/manage notebook files per faction

### `cli/agent.py` — minimal changes

The agent CLI commands (`state`, `actions`, `move`, `attack`, `end`, etc.) already work. The only change needed:
- The `connect` command needs to work without interactive session persistence (or we handle session setup from the human CLI side directly via the server API)
- `watch` command becomes unnecessary for this flow but can stay for backwards compatibility

### Server — no changes needed

The server already supports:
- Multiple sessions (human + claude)
- Entity-to-session assignment
- Turn-based action validation
- Combat log streaming

### New: `cli/claude_opponent.py` (or in `cli/commands.py`)

Helper module for the Claude invocation:

```python
import subprocess
import json
import os
from typing import Optional, Dict

def invoke_claude_turn(
    faction_name: str,
    entity_name: str,
    round_number: int,
    session_id: Optional[str],
    notebook_dir: str,
    project_dir: str,
    max_turns: int = 15,
) -> Dict:
    """Invoke Claude to take a turn for a faction. Returns parsed JSON with session_id."""

    notebook_path = os.path.join(notebook_dir, f"{faction_name}.md")
    notebook_content = ""
    if os.path.exists(notebook_path):
        with open(notebook_path) as f:
            notebook_content = f.read()

    prompt = f"""It's {entity_name}'s turn (Round {round_number}).
You control the {faction_name} faction.

YOUR NOTEBOOK:
{notebook_content or "(empty — first turn)"}

Take your turn: run state, actions, execute, end.
Update your notebook at {notebook_path} before ending."""

    skill_path = os.path.join(project_dir, ".claude", "skills", "dnd", "SKILL.md")
    bash_prefix = f"cd {project_dir} && source .venv/bin/activate && python -m cli.agent"

    # Run from /tmp to avoid loading project CLAUDE.md
    scratch_dir = "/tmp/dnd_game"
    os.makedirs(scratch_dir, exist_ok=True)

    cmd = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--allowedTools", f"Bash({bash_prefix} *)", "Read", "Write",
        "--max-turns", str(max_turns),
        "--append-system-prompt-file", skill_path,
    ]

    if session_id:
        cmd.extend(["--resume", session_id])

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=scratch_dir)

    if result.returncode != 0:
        raise RuntimeError(f"Claude invocation failed: {result.stderr}")

    return json.loads(result.stdout)
```

## Open Questions

1. **Session ID persistence**: If the human CLI crashes, can we recover session IDs? Should we save them to a file?
2. **Turn timeout**: Should we set `--max-turns` or a time limit to prevent Claude from looping?
3. **Streaming**: Should we stream Claude's output to show the human what Claude is thinking? (Uses `--output-format stream-json`)
4. **Cost control**: `--max-budget-usd` per turn? Probably not needed on Max subscription.
5. **Error recovery**: What if `claude -p` fails mid-turn? The encounter state may be partially modified. Need a rollback mechanism or at minimum a retry.
6. **Notebook file permissions**: If Claude is sandboxed, can it write to `.claude/notebooks/`? May need `--allowedTools "Write(.claude/notebooks/*)"`.

## Benefits Over Current Architecture

| Current (polling) | Proposed (per-turn invocation) |
|---|---|
| Claude runs as separate background process | Human CLI orchestrates everything |
| Polls every 2s, wastes cycles | Event-driven, zero waste |
| Single Claude session for all entities | Per-faction sessions with independent memory |
| No persistent memory between commands | Notebook persists strategy across turns |
| Manual `connect` + `watch` workflow | Automatic, seamless |
| Fragile — session drops, polling failures | Robust — each invocation is independent |
| Hard to debug | Easy — each turn is a single subprocess call |
