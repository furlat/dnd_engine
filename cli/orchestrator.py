"""PvP Orchestrator: Claude vs Claude with spectator mode.

Run from a terminal:
    source .venv/bin/activate && python -m cli.orchestrator

Flags:
    --dry-run    Skip Claude subprocesses, just end turns (for testing the loop)
    --best-of N  Run a best-of-N series (default: 1 = single match)

Launches two Claude subprocesses (hero + monsters) that take turns
playing D&D via the agent CLI. The user watches as spectator.
"""

import json
import os
import secrets
import string
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import atexit
import signal

from cli.api_client import APIClient
from cli.agent import format_combat_log_entry, format_map, format_entities, format_actions
from cli.log_filter import filter_combat_log


_log_epoch = time.time()

# Track all Claude subprocesses for cleanup on exit
_active_subprocesses: List[subprocess.Popen] = []


def _cleanup_subprocesses() -> None:
    """Kill all tracked Claude subprocesses."""
    for proc in _active_subprocesses:
        if proc.poll() is None:
            try:
                proc.kill()
                proc.wait(timeout=3)
            except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
                pass
    _active_subprocesses.clear()


atexit.register(_cleanup_subprocesses)


def _sigterm_handler(_signum: int, _frame: object) -> None:
    """Handle SIGTERM by cleaning up subprocesses and exiting."""
    _cleanup_subprocesses()
    sys.exit(0)


# SIGTERM is sent by spectate's os.killpg
signal.signal(signal.SIGTERM, _sigterm_handler)


def log(msg: str) -> None:
    """Print with relative timestamp so output appears immediately in pipes/subprocesses."""
    elapsed = time.time() - _log_epoch
    print(f"[{elapsed:7.1f}s] {msg}", flush=True)


DRY_RUN = "--dry-run" in sys.argv
CHARACTER_CLASS = "sorcerer"
CLAUDE_MODEL = ""  # Empty = use default
_RUN_DIR_OVERRIDE = ""
BEST_OF = 1  # Default: single match (no series)
for _i, _arg in enumerate(sys.argv):
    if _arg == "--character-class" and _i + 1 < len(sys.argv):
        CHARACTER_CLASS = sys.argv[_i + 1]
    if _arg == "--model" and _i + 1 < len(sys.argv):
        CLAUDE_MODEL = sys.argv[_i + 1]
    if _arg == "--run-dir" and _i + 1 < len(sys.argv):
        _RUN_DIR_OVERRIDE = sys.argv[_i + 1]
    if _arg == "--best-of" and _i + 1 < len(sys.argv):
        BEST_OF = int(sys.argv[_i + 1])
SERVER_URL = "http://localhost:8000"
PROJECT_DIR = Path(__file__).resolve().parent.parent  # dnd_engine root
SCRATCH_DIR = Path("/tmp/dnd_game")

# Run directory: use --run-dir if provided (from spectate), else create timestamped
from datetime import datetime
if _RUN_DIR_OVERRIDE:
    RUN_DIR = Path(_RUN_DIR_OVERRIDE)
else:
    RUN_DIR = PROJECT_DIR / "game_logs" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_DIR = RUN_DIR / "turns"
NOTEBOOK_DIR = RUN_DIR / "notebooks"
PROMPT_TEMPLATE = PROJECT_DIR / "cli" / "dnd_auto_prompt.md"


def generate_token(length: int = 6) -> str:
    """Generate a random short token (e.g., 'a7k3p2')."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@dataclass
class PlayerSlot:
    slot_id: str  # "hero" or "monsters" — readable, for display/logs
    token: str  # Random 6-char token — for session auth
    faction: str  # "heroes" or "monsters"
    entity_uuids: List[str] = field(default_factory=list)
    server_session_id: Optional[str] = None
    claude_session_id: Optional[str] = None  # For --resume
    notebook_path: Optional[Path] = None
    prompt_file: Optional[Path] = None
    combat_log_index: int = 0
    trajectory_path: Optional[Path] = None
    trajectory_started: bool = False

    @property
    def session_file(self) -> str:
        """Path to session file — matches what --token produces in agent.py."""
        return f"/tmp/dnd_game/{self.token}_session.txt"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def partition_by_faction(state: dict) -> Tuple[List[str], List[str]]:
    """Split entities into hero and monster UUID lists."""
    hero_uuids: List[str] = []
    monster_uuids: List[str] = []
    for e in state.get("entities", []):
        if e.get("faction") == "heroes":
            hero_uuids.append(e["uuid"])
        elif e.get("faction") == "monsters":
            monster_uuids.append(e["uuid"])
    return hero_uuids, monster_uuids


def get_slot_for_entity(slots: List[PlayerSlot], entity_uuid: str) -> Optional[PlayerSlot]:
    for slot in slots:
        if entity_uuid in slot.entity_uuids:
            return slot
    return None


def get_entity_name(state: dict, entity_uuid: str) -> str:
    for e in state.get("entities", []):
        if e.get("uuid") == entity_uuid:
            return e.get("name", "???")
    return "???"


def show_final_results(state: dict) -> None:
    entities = state.get("entities", [])
    for e in entities:
        status = "ALIVE" if e.get("hp", 0) > 0 else "DEAD"
        log(f"  {e.get('name', '?')}: {e.get('hp', 0)}/{e.get('max_hp', 0)} HP - {status}")
    alive = [e for e in entities if e.get("hp", 0) > 0]
    if alive:
        factions = set(e.get("faction", "?") for e in alive)
        if len(factions) == 1:
            log(f"\nWINNER: {list(factions)[0].upper()} faction!")


def format_final_results(state: dict) -> str:
    lines: List[str] = []
    for e in state.get("entities", []):
        status = "ALIVE" if e.get("hp", 0) > 0 else "DEAD"
        lines.append(f"  {e.get('name', '?')}: {e.get('hp', 0)}/{e.get('max_hp', 0)} HP - {status}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Server management
# ---------------------------------------------------------------------------

def verify_server(client: APIClient) -> bool:
    try:
        client.get_simulation_status()
        return True
    except Exception:
        return False


def start_server() -> subprocess.Popen:
    log("Starting server...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.event_server:app",
         "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(PROJECT_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return proc


def wait_for_server(client: APIClient, timeout: int = 15) -> None:
    start = time.time()
    while time.time() - start < timeout:
        if verify_server(client):
            log("Server ready.")
            return
        time.sleep(1)
    raise RuntimeError("Server failed to start within timeout")


# ---------------------------------------------------------------------------
# Session file writing (matches agent.py's load_session format)
# ---------------------------------------------------------------------------

def write_session_file(slot: PlayerSlot, active_entity_uuid: str) -> None:
    """Write session file that agent.py's load_session() reads.

    Format:
        Line 1: server_session_id
        Line 2: active entity UUID (becomes _current_entity_uuid)
        Lines 3+: other controlled entity UUIDs
    """
    lines = [slot.server_session_id or "", active_entity_uuid]
    for uuid in slot.entity_uuids:
        if uuid != active_entity_uuid:
            lines.append(uuid)
    path = Path(slot.session_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Prompt file generation
# ---------------------------------------------------------------------------

def generate_prompt_files(*slots: PlayerSlot) -> None:
    """Read template, replace placeholders, write per-slot files."""
    template = PROMPT_TEMPLATE.read_text()
    for slot in slots:
        content = template.replace("{TOKEN}", slot.token)
        content = content.replace("{PROJECT_DIR}", str(PROJECT_DIR))
        content = content.replace("{NOTEBOOK_PATH}", str(slot.notebook_path or ""))
        if slot.prompt_file:
            slot.prompt_file.parent.mkdir(parents=True, exist_ok=True)
            slot.prompt_file.write_text(content)


# ---------------------------------------------------------------------------
# Claude subprocess
# ---------------------------------------------------------------------------

def _clean_env() -> dict:
    """Strip Claude Code env vars to avoid recursive guard in claude -p subprocess."""
    env = os.environ.copy()
    for key in list(env.keys()):
        if "CLAUDE" in key.upper():
            del env[key]
    return env


def append_trajectory_turn(
    raw_output: str,
    prompt: str,
    entity_name: str,
    round_num: int,
    trajectory_file: Path,
    token: str = "",
    system_prompt: str = "",
    is_first_turn: bool = False,
) -> None:
    """Append a turn's trajectory to a per-faction trajectory file.

    Each faction gets ONE trajectory file for the whole combat.
    Uses ~~~~ fences (not backticks) to avoid nesting issues with markdown content.

    Args:
        raw_output: Raw stream-json output from Claude subprocess
        prompt: The exact turn prompt sent to Claude
        entity_name: Name of the active entity this turn
        round_num: Current round number
        trajectory_file: Path to the faction's trajectory file (appended to)
        token: Session token (stripped from commands for readability)
        system_prompt: System prompt content (only included on first turn)
        is_first_turn: Whether this is the first turn for this faction
    """
    lines: List[str] = []

    # Header for this faction's trajectory (only on first turn)
    if is_first_turn:
        lines.append(f"# Trajectory Log\n")
        if system_prompt:
            lines.append("## System Prompt")
            lines.append("~~~~")
            lines.append(system_prompt)
            lines.append("~~~~\n")

    # Turn header
    lines.append(f"---\n## Round {round_num} — {entity_name}\n")

    # Turn prompt
    lines.append("### Observation")
    lines.append("~~~~")
    lines.append(prompt)
    lines.append("~~~~\n")

    # Parse stream-json events into action steps
    # Stream-json format from `claude -p --output-format stream-json`:
    #   {"type": "assistant", "message": {"content": [{"type": "text", "text": "..."}]}}
    #   {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {...}}]}}
    #   {"type": "user", "message": {"content": [{"type": "tool_result", "content": "..."}]}}
    lines.append("### Actions")
    step_num = 0
    pending_tool: Optional[dict] = None

    for raw_line in raw_output.split("\n"):
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type")

        if event_type == "assistant":
            # Parse content blocks from message
            message = event.get("message", {})
            content_blocks = message.get("content", []) if isinstance(message, dict) else []
            for block in content_blocks:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")

                if block_type == "text":
                    text = block.get("text", "").strip()
                    if text:
                        step_num += 1
                        lines.append(f"**Step {step_num}** (reasoning)")
                        lines.append("~~~~")
                        lines.append(text[:2000])
                        lines.append("~~~~\n")

                elif block_type == "tool_use":
                    pending_tool = {
                        "tool": block.get("name", "?"),
                        "input": block.get("input", {}),
                    }

        elif event_type == "user":
            # Tool results are nested in user message content
            message = event.get("message", {})
            content_blocks = message.get("content", []) if isinstance(message, dict) else []
            for block in content_blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_result":
                    continue

                step_num += 1
                tool_name = pending_tool["tool"] if pending_tool else "?"
                tool_input = pending_tool["input"] if pending_tool else {}
                result_content = block.get("content", "")

                lines.append(f"**Step {step_num}** — {tool_name}")

                # Format input based on tool type
                if tool_name == "Bash":
                    cmd = tool_input.get("command", "")
                    if token:
                        cmd = cmd.replace(f"--token {token}", "--token ***")
                    lines.append(f"Input: `{cmd}`")
                elif tool_name == "Write":
                    fp = tool_input.get("file_path", "")
                    content_preview = tool_input.get("content", "")
                    if len(content_preview) > 500:
                        content_preview = content_preview[:500] + "..."
                    lines.append(f"Input: Write {fp}")
                    lines.append("~~~~")
                    lines.append(content_preview)
                    lines.append("~~~~")
                elif tool_name == "Read":
                    fp = tool_input.get("file_path", "")
                    lines.append(f"Input: Read {fp}")
                else:
                    lines.append(f"Input: {json.dumps(tool_input, indent=2)[:500]}")

                # Output
                lines.append("Response:")
                lines.append("~~~~")
                if isinstance(result_content, str):
                    lines.append(result_content)
                else:
                    lines.append(str(result_content))
                lines.append("~~~~\n")

                pending_tool = None

    if step_num == 0:
        lines.append("(no actions taken)\n")

    # Append to file (create if first turn)
    trajectory_file.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if is_first_turn else "a"
    with open(trajectory_file, mode, encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def display_stream_event(event: dict, slot_id: str) -> None:
    """Display stream-json event for spectator.

    Handles both nested format (type: assistant/user with message.content blocks)
    and legacy flat format (type: tool_use/tool_result at top level).
    """
    event_type = event.get("type")

    # --- Nested format: assistant message with content blocks ---
    if event_type == "assistant":
        message = event.get("message", {})
        if isinstance(message, str):
            # Legacy flat: message is a string
            first_line = message.strip().split("\n")[0]
            if first_line:
                log(f"  [{slot_id}] {first_line}")
            return

        content_blocks = message.get("content", []) if isinstance(message, dict) else []
        for block in content_blocks:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text", "").strip()
                if text:
                    first_line = text.split("\n")[0]
                    log(f"  [{slot_id}] {first_line}")
                    # Write latest thinking to shared file for spectate display
                    try:
                        (RUN_DIR / f"thinking_{slot_id}.txt").write_text(text)
                    except OSError:
                        pass
            elif block_type == "tool_use":
                tool = block.get("name", "")
                tool_input = block.get("input", {})
                if tool == "Bash":
                    cmd_text = tool_input.get("command", "")
                    if "cli.agent" in cmd_text:
                        parts = cmd_text.split("cli.agent")[-1].strip()
                        if parts.startswith("--token"):
                            token_parts = parts.split(None, 2)
                            parts = token_parts[2] if len(token_parts) > 2 else parts
                        log(f"  [{slot_id}] > {parts}")
                elif tool == "Write":
                    filepath = tool_input.get("file_path", "")
                    if "notebook" in filepath.lower():
                        log(f"  [{slot_id}] > (writing notebook)")
        return

    # --- Nested format: user message with tool_result blocks ---
    if event_type == "user":
        message = event.get("message", {})
        content_blocks = message.get("content", []) if isinstance(message, dict) else []
        for block in content_blocks:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_result":
                content = block.get("content", "")
                if content and isinstance(content, str):
                    first_line = content.split("\n")[0]
                    log(f"  [{slot_id}]   {first_line}")
        return

    # --- Legacy flat format fallback ---
    if event_type == "tool_use":
        tool = event.get("tool", "")
        if tool == "Bash":
            cmd_text = event.get("input", {}).get("command", "")
            if "cli.agent" in cmd_text:
                parts = cmd_text.split("cli.agent")[-1].strip()
                if parts.startswith("--token"):
                    token_parts = parts.split(None, 2)
                    parts = token_parts[2] if len(token_parts) > 2 else parts
                log(f"  [{slot_id}] > {parts}")
        elif tool == "Write":
            filepath = event.get("input", {}).get("file_path", "")
            if "notebook" in filepath.lower():
                log(f"  [{slot_id}] > (writing notebook)")

    elif event_type == "tool_result":
        content = event.get("content", "")
        if content and isinstance(content, str):
            first_line = content.split("\n")[0]
            log(f"  [{slot_id}]   {first_line}")


def _is_turn_ended_event(event: dict) -> bool:
    """Detect 'OK: Turn ended' in a stream-json event.

    Checks nested format (user → tool_result content blocks) and
    legacy flat format (tool_result at top level).
    """
    def _check_content(content: object) -> bool:
        if isinstance(content, str) and "OK: Turn ended" in content:
            return True
        return False

    event_type = event.get("type")

    # Nested format: type="user" with tool_result content blocks
    if event_type == "user":
        message = event.get("message", {})
        content_blocks = message.get("content", []) if isinstance(message, dict) else []
        for block in content_blocks:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                if _check_content(block.get("content", "")):
                    return True

    # Legacy flat format
    if event_type == "tool_result":
        if _check_content(event.get("content", "")):
            return True

    return False


@dataclass
class TurnMetrics:
    """Metrics for a single entity turn."""
    slot_id: str
    entity_name: str
    round_num: int
    match_num: int = 1
    # Timing
    turn_start: float = 0.0
    turn_end: float = 0.0
    total_time_s: float = 0.0
    duration_ms: int = 0          # from result event
    duration_api_ms: int = 0      # from result event
    prompt_build_s: float = 0.0
    time_to_first_output_s: float = 0.0
    time_to_first_action_s: float = 0.0
    # Actions (from stream event parsing)
    game_actions: int = 0         # Bash calls to agent CLI
    thinking_steps: int = 0       # assistant text blocks
    read_actions: int = 0         # Read tool calls
    num_turns: int = 0            # from result event (API round-trips)
    action_list: List[str] = field(default_factory=list)
    action_timestamps: List[Tuple[float, str]] = field(default_factory=list)
    # Tokens & cost (from result event)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    total_cost_usd: float = 0.0

    def log_summary(self) -> str:
        actions_str = ", ".join(self.action_list) if self.action_list else "none"
        return (
            f"[{self.slot_id}] {self.entity_name} R{self.round_num}: "
            f"{self.total_time_s:.1f}s (API {self.duration_api_ms / 1000:.1f}s) | "
            f"{self.game_actions} actions ({actions_str}) | "
            f"{self.thinking_steps} thinks | "
            f"${self.total_cost_usd:.3f} | "
            f"{self.output_tokens} out_tok"
        )

    def to_dict(self) -> dict:
        return {
            "slot_id": self.slot_id,
            "entity": self.entity_name,
            "round": self.round_num,
            "match_num": self.match_num,
            "total_time_s": round(self.total_time_s, 1),
            "duration_ms": self.duration_ms,
            "duration_api_ms": self.duration_api_ms,
            "prompt_build_s": round(self.prompt_build_s, 1),
            "time_to_first_output_s": round(self.time_to_first_output_s, 1),
            "time_to_first_action_s": round(self.time_to_first_action_s, 1),
            "game_actions": self.game_actions,
            "thinking_steps": self.thinking_steps,
            "read_actions": self.read_actions,
            "num_turns": self.num_turns,
            "actions": self.action_list,
            "action_timestamps": [(round(t, 1), a) for t, a in self.action_timestamps],
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cost_usd": round(self.total_cost_usd, 4),
        }


@dataclass
class NotebookMetrics:
    """Metrics for a notebook reflection subprocess."""
    slot_id: str
    round_num: int
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    total_cost_usd: float = 0.0

    def to_dict(self) -> dict:
        return {
            "slot_id": self.slot_id,
            "round": self.round_num,
            "duration_ms": self.duration_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cost_usd": round(self.total_cost_usd, 4),
        }


@dataclass
class TurnResult:
    """Result from a Claude subprocess turn, supporting background drain."""
    session_id: Optional[str] = None
    raw_lines: List[str] = field(default_factory=list)
    returncode: Optional[int] = None
    turn_ended: bool = False
    _drain_thread: Optional[threading.Thread] = field(default=None, repr=False)
    _drain_complete: threading.Event = field(default_factory=threading.Event, repr=False)
    _process: Optional[subprocess.Popen] = field(default=None, repr=False)
    # Metrics collection (populated during streaming, thread-safe via append)
    _turn_start: float = field(default_factory=time.time, repr=False)
    _turn_end: float = 0.0
    _game_actions: List[str] = field(default_factory=list, repr=False)
    _action_timestamps: List[Tuple[float, str]] = field(default_factory=list, repr=False)
    _thinking_steps: int = 0
    _read_actions: int = 0
    # Timing instrumentation
    _first_output_time: float = 0.0    # First assistant text event
    _first_action_time: float = 0.0    # First Bash game action
    _prompt_build_s: float = 0.0       # Set externally by turn loop
    # From result event (may arrive in drain thread)
    _result_data: Optional[dict] = field(default=None, repr=False)

    @property
    def raw_output(self) -> str:
        return "".join(self.raw_lines)

    def wait_for_drain(self, timeout: float = 45) -> None:
        """Block until background drain finishes (or timeout)."""
        if self._drain_thread is not None:
            self._drain_complete.wait(timeout=timeout)
            # If drain timed out and process is still alive, kill it
            if self._process and self._process.poll() is None:
                log(f"  WARNING: Drain timeout ({timeout}s), killing subprocess.")
                self._process.kill()
                self._process.wait(timeout=5)

    def build_metrics(self, slot_id: str, entity_name: str, round_num: int, match_num: int = 1) -> TurnMetrics:
        """Build TurnMetrics from collected data. Call after drain completes."""
        rd = self._result_data or {}
        usage = rd.get("usage", {})
        turn_end = self._turn_end if self._turn_end > 0 else time.time()
        ttfo = (self._first_output_time - self._turn_start) if self._first_output_time > 0 else 0.0
        ttfa = (self._first_action_time - self._turn_start) if self._first_action_time > 0 else 0.0
        return TurnMetrics(
            slot_id=slot_id,
            entity_name=entity_name,
            round_num=round_num,
            match_num=match_num,
            turn_start=self._turn_start,
            turn_end=turn_end,
            total_time_s=turn_end - self._turn_start,
            duration_ms=rd.get("duration_ms", 0),
            duration_api_ms=rd.get("duration_api_ms", 0),
            prompt_build_s=self._prompt_build_s,
            time_to_first_output_s=ttfo,
            time_to_first_action_s=ttfa,
            game_actions=len(self._game_actions),
            thinking_steps=self._thinking_steps,
            read_actions=self._read_actions,
            num_turns=rd.get("num_turns", 0),
            action_list=list(self._game_actions),
            action_timestamps=list(self._action_timestamps),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
            cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
            total_cost_usd=rd.get("total_cost_usd", 0.0),
        )


@dataclass
class GameMetrics:
    """Aggregate metrics for the entire game (or series of games)."""
    game_start: float = field(default_factory=time.time)
    game_start_iso: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    turn_metrics: List[TurnMetrics] = field(default_factory=list)
    notebook_metrics: List[NotebookMetrics] = field(default_factory=list)
    match_results: List[dict] = field(default_factory=list)
    series_score: Dict[str, int] = field(default_factory=lambda: {"heroes": 0, "monsters": 0})
    best_of: int = 1
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add_turn(self, m: TurnMetrics) -> None:
        with self._lock:
            self.turn_metrics.append(m)

    def add_notebook(self, m: NotebookMetrics) -> None:
        with self._lock:
            self.notebook_metrics.append(m)

    def to_dict(self) -> dict:
        game_duration = time.time() - self.game_start
        turns = self.turn_metrics
        notebooks = self.notebook_metrics
        total_cost = sum(t.total_cost_usd for t in turns) + sum(n.total_cost_usd for n in notebooks)

        # Per-slot summary
        slot_ids = sorted(set(t.slot_id for t in turns))
        per_slot: Dict[str, dict] = {}
        for sid in slot_ids:
            st = [t for t in turns if t.slot_id == sid]
            sn = [n for n in notebooks if n.slot_id == sid]
            per_slot[sid] = {
                "total_turns": len(st),
                "avg_turn_s": round(sum(t.total_time_s for t in st) / max(len(st), 1), 1),
                "avg_actions": round(sum(t.game_actions for t in st) / max(len(st), 1), 1),
                "total_cost_usd": round(sum(t.total_cost_usd for t in st), 4),
                "total_output_tokens": sum(t.output_tokens for t in st),
                "notebook_cost_usd": round(sum(n.total_cost_usd for n in sn), 4),
            }

        result = {
            "game_start": self.game_start_iso,
            "game_duration_s": round(game_duration, 1),
            "total_turns": len(turns),
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": {
                "input": sum(t.input_tokens for t in turns),
                "output": sum(t.output_tokens for t in turns),
                "cache_read": sum(t.cache_read_tokens for t in turns),
                "cache_creation": sum(t.cache_creation_tokens for t in turns),
            },
            "turns": [t.to_dict() for t in turns],
            "notebooks": [n.to_dict() for n in notebooks],
            "per_slot_summary": per_slot,
        }
        if self.best_of > 1:
            result["best_of"] = self.best_of
            result["series_score"] = dict(self.series_score)
            result["match_results"] = list(self.match_results)
        return result

    def log_summary(self) -> None:
        d = self.to_dict()
        log(f"\n{'=' * 60}")
        log(f"  GAME METRICS")
        log(f"{'=' * 60}")
        log(f"  Duration: {d['game_duration_s']}s | Turns: {d['total_turns']} | Cost: ${d['total_cost_usd']:.2f}")
        log(f"  Tokens — out: {d['total_tokens']['output']}, cache_read: {d['total_tokens']['cache_read']}, cache_create: {d['total_tokens']['cache_creation']}")
        for sid, ss in d.get("per_slot_summary", {}).items():
            log(f"  [{sid}] {ss['total_turns']} turns, avg {ss['avg_turn_s']}s, avg {ss['avg_actions']} actions, ${ss['total_cost_usd']:.2f} + notebook ${ss['notebook_cost_usd']:.2f}")

    def write_json(self, path: Path) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        log(f"  Metrics: {path}")


def _classify_stream_event(result: TurnResult, event: dict, token: str) -> None:
    """Extract metrics data from a stream-json event."""
    event_type = event.get("type")
    elapsed = time.time() - result._turn_start

    if event_type == "assistant":
        message = event.get("message", {})
        content_blocks = message.get("content", []) if isinstance(message, dict) else []
        for block in content_blocks:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "tool_use":
                tool_name = block.get("name", "")
                if tool_name == "Bash":
                    cmd_text = block.get("input", {}).get("command", "")
                    # Extract the agent command (part after --token TOKEN)
                    parts = cmd_text.split(token)
                    action_name = parts[-1].strip() if len(parts) > 1 else cmd_text[-60:]
                    result._game_actions.append(action_name)
                    result._action_timestamps.append((elapsed, action_name))
                    if result._first_action_time == 0.0:
                        result._first_action_time = time.time()
                elif tool_name == "Read":
                    result._read_actions += 1
            elif block_type == "text":
                result._thinking_steps += 1
                if result._first_output_time == 0.0:
                    result._first_output_time = time.time()

    elif event_type == "result":
        result._result_data = event
        result.session_id = event.get("session_id", result.session_id)


def run_claude_turn(
    slot: PlayerSlot,
    prompt: str,
    max_turns: int = 20,
    allow_write: bool = True,
) -> TurnResult:
    """Run a Claude turn as a subprocess.

    Uses stream-json for real-time spectator view.
    When 'OK: Turn ended' is detected in the stream, returns early while a
    background thread drains the remaining output.

    Args:
        allow_write: If False, omits Write from --allowedTools (game turns).
    """
    cmd = ["claude", "-p", prompt]

    # Model override (if specified)
    if CLAUDE_MODEL:
        cmd += ["--model", CLAUDE_MODEL]

    # Output format
    cmd += ["--output-format", "stream-json", "--verbose"]

    # Tool restrictions
    agent_prefix = (
        f"source .venv/bin/activate && "
        f"python -m cli.agent --token {slot.token}"
    )
    cmd += ["--allowedTools", f"Bash({agent_prefix} *)"]
    cmd += ["--allowedTools", "Read"]
    if allow_write:
        cmd += ["--allowedTools", "Write"]

    # System prompt (per-slot, with token filled in)
    if slot.prompt_file and slot.prompt_file.exists():
        cmd += ["--append-system-prompt-file", str(slot.prompt_file)]

    # Safety limits
    cmd += ["--max-turns", str(max_turns)]

    # Resume existing session (continuous narrative per faction)
    if slot.claude_session_id:
        cmd += ["--resume", slot.claude_session_id]

    log(f"  Invoking Claude ({slot.slot_id})...")

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=str(PROJECT_DIR),  # CWD = project root so agent imports work
        text=True,
        env=_clean_env(),
    )
    _active_subprocesses.append(process)

    result = TurnResult(_process=process)

    try:
        assert process.stdout is not None
        for line in process.stdout:
            result.raw_lines.append(line)
            line_stripped = line.strip()
            if not line_stripped:
                continue
            try:
                event = json.loads(line_stripped)
                display_stream_event(event, slot.slot_id)
                _classify_stream_event(result, event, slot.token)

                # Detect turn ended — return early, drain rest in background
                if not result.turn_ended and _is_turn_ended_event(event):
                    result.turn_ended = True
                    result._turn_end = time.time()
                    log(f"  [{slot.slot_id}] [turn ended detected, starting next turn]")

                    # Spawn daemon thread to drain remaining stdout
                    def _drain(proc: subprocess.Popen, res: TurnResult, sid: str, tok: str) -> None:
                        try:
                            assert proc.stdout is not None
                            for rest_line in proc.stdout:
                                res.raw_lines.append(rest_line)
                                rest_stripped = rest_line.strip()
                                if not rest_stripped:
                                    continue
                                try:
                                    rest_event = json.loads(rest_stripped)
                                    display_stream_event(rest_event, sid)
                                    _classify_stream_event(res, rest_event, tok)
                                except json.JSONDecodeError:
                                    pass
                            proc.wait(timeout=60)
                            res.returncode = proc.returncode
                        except Exception:
                            if proc.poll() is None:
                                proc.kill()
                                proc.wait(timeout=5)
                        finally:
                            res._drain_complete.set()

                    t = threading.Thread(
                        target=_drain, args=(process, result, slot.slot_id, slot.token),
                        daemon=True,
                    )
                    t.start()
                    result._drain_thread = t
                    return result

            except json.JSONDecodeError:
                pass

        process.wait(timeout=180)  # 3-minute timeout
        result.returncode = process.returncode

    except subprocess.TimeoutExpired:
        log(f"  TIMEOUT: Claude ({slot.slot_id}) exceeded 3 minutes. Killing.")
        process.kill()
        process.wait()
        result.returncode = process.returncode

    # Mark drain as complete (no background thread needed)
    result._drain_complete.set()
    result._turn_end = time.time()

    if result.session_id:
        slot.claude_session_id = result.session_id

    if result.returncode and result.returncode != 0:
        stderr_out = process.stderr.read() if process.stderr else ""
        log(f"  WARNING: Claude exited with code {result.returncode}")
        if stderr_out:
            log(f"  stderr: {stderr_out[:300]}")

    return result


# ---------------------------------------------------------------------------
# Turn verification
# ---------------------------------------------------------------------------

def verify_turn_ended(slot_client: APIClient, entity_uuid: str) -> None:
    """Check if Claude ended its turn. Force-end if not."""
    try:
        ping = slot_client.ping_session()
        if ping.get("is_my_turn", False):
            if ping.get("active_entity_uuid") == entity_uuid:
                log(f"  WARNING: Claude didn't end turn. Forcing.")
                slot_client.end_turn(entity_uuid=entity_uuid)
                log(f"  Turn force-ended.")
    except Exception as e:
        log(f"  WARNING: Could not verify turn: {e}")


# ---------------------------------------------------------------------------
# Post-game reflection
# ---------------------------------------------------------------------------

def run_post_game_reflection(
    slot: PlayerSlot, state: dict,
    combat_log_text: str = "",
    series_result: str = "",
) -> None:
    """After encounter ends, ask Claude to write reflections.

    Args:
        slot: The player slot (hero or monsters).
        state: Final game state dict (entities with HP, etc.).
        combat_log_text: Formatted combat log from the final turns of the game.
        series_result: Series result string (e.g., "Heroes win 2-1").
    """
    if DRY_RUN:
        log(f"  [dry-run] Skipping reflection for {slot.slot_id}")
        return

    # Build context sections
    sections = []
    if series_result:
        sections.append(f"**{series_result}**\n")
    sections.append(f"Final entity status:\n{format_final_results(state)}")
    if combat_log_text:
        sections.append(f"Combat log (final turns):\n{combat_log_text}")

    notebook_path = slot.notebook_path or "(unknown)"
    prompt = (
        f"The game is over.\n\n"
        + "\n\n".join(sections)
        + "\n\n"
        f"Please write a post-game reflection to your notebook at "
        f"`{notebook_path}` using the Write tool. Include:\n"
        f"1. What strategies worked and what didn't\n"
        f"2. Things you didn't understand about the game mechanics\n"
        f"3. Commands that behaved unexpectedly or bugs you think you found\n"
        f"4. What you would do differently next time\n"
        f"5. Any confusion about the rules or available actions\n\n"
        f"Use the Write tool to write the full reflection to `{notebook_path}`."
    )
    result = run_claude_turn(slot, prompt, max_turns=5)
    result.wait_for_drain(timeout=60)
    log_file = LOG_DIR / f"reflection_{slot.slot_id}.log"
    with open(log_file, "w") as f:
        f.write(result.raw_output)
    log(f"  Reflection logged: {log_file}")


# ---------------------------------------------------------------------------
# Deferred turn logging
# ---------------------------------------------------------------------------

@dataclass
class _PendingLog:
    """Data needed to write turn log/trajectory after drain completes."""
    result: TurnResult
    slot: PlayerSlot
    prompt: str
    entity_name: str
    round_num: int
    active_uuid: str


def _flush_turn_log(pending: _PendingLog, slot_clients: Dict[str, APIClient]) -> None:
    """Wait for drain to complete, then write turn log and trajectory."""
    pending.result.wait_for_drain(timeout=45)

    # Update session_id from drained output (may have arrived after early return)
    if pending.result.session_id:
        pending.slot.claude_session_id = pending.result.session_id

    # Write turn log file
    safe_name = pending.entity_name.replace(" ", "_")
    log_file = LOG_DIR / f"turn_{pending.round_num}_{safe_name}.log"
    with open(log_file, "w") as f:
        if pending.slot.prompt_file and pending.slot.prompt_file.exists():
            f.write("=== SYSTEM PROMPT ===\n")
            f.write(pending.slot.prompt_file.read_text())
            f.write("\n=== END SYSTEM PROMPT ===\n\n")
        f.write("=== TURN PROMPT ===\n")
        f.write(pending.prompt)
        f.write("\n=== END TURN PROMPT ===\n\n")
        f.write("=== STREAM OUTPUT ===\n")
        f.write(pending.result.raw_output)
    log(f"  Log: {log_file}")

    # Append to per-faction trajectory file
    if pending.slot.trajectory_path:
        sys_prompt = ""
        if not pending.slot.trajectory_started and pending.slot.prompt_file and pending.slot.prompt_file.exists():
            sys_prompt = pending.slot.prompt_file.read_text()
        append_trajectory_turn(
            pending.result.raw_output,
            pending.prompt, pending.entity_name, pending.round_num,
            pending.slot.trajectory_path,
            token=pending.slot.token,
            system_prompt=sys_prompt,
            is_first_turn=not pending.slot.trajectory_started,
        )
        pending.slot.trajectory_started = True
        log(f"  Trajectory: {pending.slot.trajectory_path}")

    # Verify turn ended — force end if Claude forgot (only if NOT early-returned)
    if not pending.result.turn_ended:
        slot_client = slot_clients[pending.slot.slot_id]
        verify_turn_ended(slot_client, pending.active_uuid)


# ---------------------------------------------------------------------------
# Transition detection
# ---------------------------------------------------------------------------

def _next_alive_slot(
    slots: List[PlayerSlot],
    initiative_order: List[dict],
    current_turn_index: int,
) -> Optional[PlayerSlot]:
    """Find the slot that owns the next alive entity in initiative order."""
    n = len(initiative_order)
    for offset in range(1, n + 1):
        idx = (current_turn_index + offset) % n
        combatant = initiative_order[idx]
        if combatant.get("is_dead"):
            continue
        return get_slot_for_entity(slots, combatant["uuid"])
    return None


# ---------------------------------------------------------------------------
# Turn loop
# ---------------------------------------------------------------------------

def turn_loop(
    spectator: APIClient,
    slots: List[PlayerSlot],
    slot_clients: Dict[str, APIClient],
    game_metrics: GameMetrics,
    match_num: int = 1,
    series_info: str = "",
) -> Optional[str]:
    """Run the turn loop for a single match.

    Returns the winning faction string ("heroes" or "monsters"), or None if
    the encounter ended without a clear winner.
    """
    round_num = 0
    winner: Optional[str] = None
    # Fire-and-forget background threads — never block the turn loop.
    _bg_threads: List[threading.Thread] = []

    while True:
        state = spectator.get_state()
        encounter = state.get("encounter", {})

        if encounter.get("state") != "active":
            log("\n=== ENCOUNTER ENDED ===")
            show_final_results(state)
            # Wait for in-flight background threads
            for t in _bg_threads:
                t.join(timeout=30)
            _bg_threads.clear()
            # Determine winner
            entities = state.get("entities", [])
            alive = [e for e in entities if e.get("hp", 0) > 0]
            if alive:
                factions = set(e.get("faction", "?") for e in alive)
                if len(factions) == 1:
                    winner = list(factions)[0]
            break

        active_uuid = encounter.get("current_entity_uuid")
        current_round = encounter.get("round_number", 1)
        current_turn_index = encounter.get("current_turn_index", 0)

        if current_round != round_num:
            round_num = current_round
            log(f"\n{'=' * 60}")
            log(f"  ROUND {round_num}")
            log(f"{'=' * 60}")

        if not active_uuid:
            log("ERROR: No active entity")
            break

        # Find owning slot
        slot = get_slot_for_entity(slots, active_uuid)
        if not slot:
            log(f"ERROR: No slot for entity {active_uuid[:8]}...")
            break

        entity_name = get_entity_name(state, active_uuid)
        log(f"\n--- {entity_name}'s Turn (R{round_num}, {slot.faction}) ---")

        # Detect inter-Claude transition (is next entity a different Claude?)
        init_order_list = encounter.get("initiative_order", [])
        next_slot = _next_alive_slot(slots, init_order_list, current_turn_index)
        is_transition = (next_slot is not None and next_slot.slot_id != slot.slot_id)
        if is_transition and next_slot is not None:
            log(f"  [transition → {next_slot.slot_id} after this turn]")

        # Build prompt (timed)
        prompt_build_start = time.time()

        # Get visibility for subjective view
        visibility = spectator.get_visibility()
        vis_set: Optional[set] = None
        vis_cells: Optional[set] = None
        mem_cells: Optional[set] = None
        vis_sense_modes: list = []
        if active_uuid in visibility:
            vis_data = visibility[active_uuid]
            vis_set = set(vis_data.get("visible_entities", []))
            vis_set.update(slot.entity_uuids)
            vis_cells = set(
                tuple(c) for c in vis_data.get("visible_cells", [])
            )
            seen_cells = set(
                tuple(c) for c in vis_data.get("seen_cells", [])
            )
            mem_cells = seen_cells - vis_cells
            vis_sense_modes = vis_data.get("sense_modes", [])

        # Get available actions
        actions = spectator.get_available_actions(active_uuid)

        # Get new combat log entries
        log_data = spectator.get_combat_log(since=slot.combat_log_index)
        new_entries = log_data.get("entries", [])
        slot.combat_log_index = log_data.get("total", slot.combat_log_index)

        # Read notebook
        notebook_content = ""
        if slot.notebook_path and slot.notebook_path.exists():
            notebook_content = slot.notebook_path.read_text()

        # Filter combat log (both layers) and format sections
        from cli.prompt_builder import build_turn_prompt
        visible_entries = filter_combat_log(new_entries, slot.entity_uuids, vis_set)
        log_lines: List[str] = []
        for entry in visible_entries:
            log_lines.extend(format_combat_log_entry(entry))

        entities = state.get("entities", [])
        encounter_data = state.get("encounter", {})
        init_order = encounter_data.get("initiative_order")
        pos_actions = actions.get("position_actions", [])

        prompt = build_turn_prompt(
            entity_name=entity_name,
            faction=slot.faction,
            round_number=round_num,
            notebook_content=notebook_content,
            combat_log_text="\n".join(log_lines),
            entity_table_text=format_entities(
                entities, vis_set, active_uuid, slot.entity_uuids, init_order,
            ),
            map_text=format_map(
                state, vis_set, active_uuid, vis_cells, mem_cells, pos_actions,
                sense_modes=vis_sense_modes,
            ),
            action_text=format_actions(actions, entity_name),
            series_info=series_info,
        )

        prompt_build_s = time.time() - prompt_build_start
        log(f"  [prompt built in {prompt_build_s:.1f}s]")

        # Write session file (before Claude invocation)
        write_session_file(slot, active_uuid)

        if DRY_RUN:
            # Dry run: log the prompt, force-end the turn
            log(f"  [dry-run] Prompt built ({len(prompt)} chars)")
            log(f"  [dry-run] Session file written: {slot.session_file}")
            slot_client = slot_clients[slot.slot_id]
            try:
                slot_client.end_turn(entity_uuid=active_uuid)
                log(f"  [dry-run] Turn ended for {entity_name}")
            except Exception as e:
                log(f"  [dry-run] End turn failed: {e}")
                break
        else:
            # Run Claude subprocess — no Write tool during game turns
            result = run_claude_turn(slot, prompt, allow_write=False)
            result._prompt_build_s = prompt_build_s

            # Log per-turn metrics (immediate — uses data collected before drain)
            turn_metrics = result.build_metrics(slot.slot_id, entity_name, round_num, match_num=match_num)
            game_metrics.add_turn(turn_metrics)
            log(f"  {turn_metrics.log_summary()}")
            tm = turn_metrics
            log(f"  [timing] prompt={tm.prompt_build_s:.1f}s, "
                f"first_output={tm.time_to_first_output_s:.1f}s, "
                f"first_action={tm.time_to_first_action_s:.1f}s, "
                f"total={tm.total_time_s:.1f}s")

            # Fire-and-forget: flush log/trajectory in background
            pending = _PendingLog(
                result=result,
                slot=slot,
                prompt=prompt,
                entity_name=entity_name,
                round_num=round_num,
                active_uuid=active_uuid,
            )
            flush_t = threading.Thread(
                target=_flush_turn_log,
                args=(pending, slot_clients),
                daemon=True,
            )
            flush_t.start()
            _bg_threads.append(flush_t)

            # No between-turn notebooks — they run a full Claude subprocess
            # with Bash access to game commands, which causes race conditions:
            # entity bindings get stolen, actions get consumed by the wrong
            # subprocess. Notebooks are written only at end of series
            # (post-game reflections).

        # Show post-turn combat log to spectator
        log_data = spectator.get_combat_log(since=slot.combat_log_index)
        post_entries = log_data.get("entries", [])
        if post_entries:
            for entry in post_entries:
                for line in format_combat_log_entry(entry):
                    log(f"  [LOG] {line}")
        slot.combat_log_index = log_data.get("total", slot.combat_log_index)

        time.sleep(0.5)

    # Wait for any remaining background threads
    for t in _bg_threads:
        t.join(timeout=30)

    return winner


# ---------------------------------------------------------------------------
# Run single match
# ---------------------------------------------------------------------------

def run_single_match(
    spectator: APIClient,
    slots: List[PlayerSlot],
    slot_clients: Dict[str, APIClient],
    game_metrics: GameMetrics,
    match_num: int,
    series_score: Dict[str, int],
) -> Optional[str]:
    """Run a single match within a series.

    Creates a new game on the server, assigns entity UUIDs, creates server
    sessions, and runs the turn loop. Claude sessions and notebooks persist.

    Returns the winning faction string, or None.
    """
    global LOG_DIR
    is_series = BEST_OF > 1
    match_start = time.time()

    # 1. Start a new PvP game (resets game state on server)
    if match_num > 1:
        log(f"\n{'=' * 60}")
        log(f"  MATCH {match_num}")
        log(f"{'=' * 60}")

    pvp_result = spectator.start_pvp_game(character_class=CHARACTER_CLASS)
    log(f"PvP started: {pvp_result.get('message', '')}")

    # 2. Get new entity UUIDs (change each match!)
    state = spectator.get_state()
    hero_uuids, monster_uuids = partition_by_faction(state)
    log(f"Heroes: {len(hero_uuids)} entities, Monsters: {len(monster_uuids)} entities")

    # Update slot entity UUIDs
    for s in slots:
        if s.faction == "heroes":
            s.entity_uuids = hero_uuids
        else:
            s.entity_uuids = monster_uuids

    # 3. Create NEW server sessions (sessions don't persist across game resets)
    hero_client = slot_clients["hero"]
    monster_client = slot_clients["monsters"]

    hero_client.create_session(player_type="claude", name="Claude Hero")
    hero_client.join_game(entity_uuids=hero_uuids)

    monster_client.create_session(player_type="claude", name="Claude Monsters")
    monster_client.join_game(entity_uuids=monster_uuids)

    for s in slots:
        client = slot_clients[s.slot_id]
        s.server_session_id = client.session_id
        s.combat_log_index = 0  # New game, new combat log
        # DO NOT reset claude_session_id — keeps Claude memory!
        # DO NOT touch notebooks — persist across matches!

    log(f"Sessions: hero={slots[0].server_session_id}, monsters={slots[1].server_session_id}")

    # 4. Set up per-match log directories for series
    if is_series:
        match_log_dir = RUN_DIR / f"match_{match_num}" / "turns"
        match_log_dir.mkdir(parents=True, exist_ok=True)
        # Update trajectory paths for this match
        for s in slots:
            s.trajectory_path = RUN_DIR / f"match_{match_num}" / f"trajectory_{s.slot_id}.md"
            s.trajectory_started = False
    else:
        match_log_dir = LOG_DIR  # Flat structure for single match

    # Temporarily swap LOG_DIR for this match
    saved_log_dir = LOG_DIR
    LOG_DIR = match_log_dir

    # 5. Build series info string for prompts
    series_info = ""
    if is_series:
        series_info = (
            f"**Series: Match {match_num} of {BEST_OF} (Best of {BEST_OF}) "
            f"— Heroes {series_score['heroes']}, Monsters {series_score['monsters']}**"
        )

    # 6. Write session files (before turn loop)
    for s in slots:
        if s.entity_uuids:
            write_session_file(s, s.entity_uuids[0])

    # 7. Run turn loop
    log(f"\n=== {'MATCH ' + str(match_num) + ' ' if is_series else ''}GAME START ===\n")
    winner = turn_loop(
        spectator, slots, slot_clients, game_metrics,
        match_num=match_num, series_info=series_info,
    )

    # 8. Record match result
    match_duration = time.time() - match_start
    game_metrics.match_results.append({
        "match": match_num,
        "winner": winner,
        "duration_s": round(match_duration, 1),
    })

    # Restore LOG_DIR
    LOG_DIR = saved_log_dir

    return winner


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if DRY_RUN:
        log("=== DRY RUN MODE (no Claude subprocesses) ===")
    is_series = BEST_OF > 1
    if is_series:
        log(f"=== BEST-OF-{BEST_OF} SERIES MODE ===")

    # 1. Create directories
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Verify/start server
    spectator = APIClient(base_url=SERVER_URL)
    server_proc: Optional[subprocess.Popen] = None
    if not verify_server(spectator):
        server_proc = start_server()
        wait_for_server(spectator)
    else:
        log("Server already running.")

    hero_client = APIClient(base_url=SERVER_URL)
    monster_client = APIClient(base_url=SERVER_URL)

    try:
        # 3. Create slots with random tokens (persist across matches)
        hero_token = generate_token()
        monster_token = generate_token()

        hero_slot = PlayerSlot(
            slot_id="hero", token=hero_token, faction="heroes",
            notebook_path=NOTEBOOK_DIR / "hero.md",
            prompt_file=SCRATCH_DIR / f"prompt_{hero_token}.md",
            trajectory_path=RUN_DIR / "trajectory_hero.md",
        )
        monster_slot = PlayerSlot(
            slot_id="monsters", token=monster_token, faction="monsters",
            notebook_path=NOTEBOOK_DIR / "monsters.md",
            prompt_file=SCRATCH_DIR / f"prompt_{monster_token}.md",
            trajectory_path=RUN_DIR / "trajectory_monsters.md",
        )
        slots = [hero_slot, monster_slot]

        log(f"Tokens: hero={hero_token}, monsters={monster_token}")

        # 4. Generate per-slot system prompt files (ONCE — tokens baked in)
        generate_prompt_files(hero_slot, monster_slot)

        # 5. Create empty notebooks (ONCE — persist across matches)
        if hero_slot.notebook_path:
            hero_slot.notebook_path.write_text("")
        if monster_slot.notebook_path:
            monster_slot.notebook_path.write_text("")

        # 6. Map slots to their APIClient for force-end-turn
        slot_clients: Dict[str, APIClient] = {
            "hero": hero_client,
            "monsters": monster_client,
        }

        # 7. Series loop
        game_metrics = GameMetrics(best_of=BEST_OF)
        series_score: Dict[str, int] = {"heroes": 0, "monsters": 0}
        wins_needed = (BEST_OF + 1) // 2

        for match_num in range(1, BEST_OF + 1):
            winner = run_single_match(
                spectator, slots, slot_clients, game_metrics,
                match_num=match_num, series_score=series_score,
            )

            if winner:
                series_score[winner] += 1
                game_metrics.series_score = dict(series_score)
                loser = "monsters" if winner == "heroes" else "heroes"

                if is_series:
                    log(f"\n  Match {match_num} winner: {winner.upper()}")
                    log(f"  Series: Heroes {series_score['heroes']} - {series_score['monsters']} Monsters")

                # Check if series is clinched
                if series_score[winner] >= wins_needed:
                    if is_series:
                        log(f"\n{'=' * 60}")
                        log(f"  {winner.upper()} WINS THE SERIES "
                            f"{series_score[winner]}-{series_score[loser]}")
                        log(f"{'=' * 60}")
                    break

                # No between-match prompts — proceed straight to next game.
                # Notebooks are written only at end of series (post-game reflections).
            else:
                log("  Match ended with no clear winner.")
                if not is_series:
                    break

        # 8. Final metrics
        game_metrics.log_summary()
        game_metrics.write_json(RUN_DIR / "metrics.json")

        # 9. Post-series reflections
        log("\n  Requesting post-game reflections...")
        state = spectator.get_state()

        # Build series result string
        if is_series:
            h, m = series_score["heroes"], series_score["monsters"]
            if h > m:
                series_result = f"Heroes win the series {h}-{m}"
            elif m > h:
                series_result = f"Monsters win the series {m}-{h}"
            else:
                series_result = f"Series tied {h}-{h}"
        else:
            # Single match
            entities = state.get("entities", [])
            alive = [e for e in entities if e.get("hp", 0) > 0]
            if alive:
                factions = set(e.get("faction", "?") for e in alive)
                if len(factions) == 1:
                    series_result = f"{list(factions)[0].capitalize()} win"
                else:
                    series_result = "Match ended"
            else:
                series_result = "Everyone is dead"

        # Fetch final combat log for each slot (subjective view)
        slot_combat_logs: Dict[str, str] = {}
        for s in slots:
            try:
                # Get the last ~20 entries for context about the ending
                full_log = spectator.get_combat_log(since=max(0, s.combat_log_index - 20))
                entries = full_log.get("entries", [])
                # Filter to this slot's visible entries
                vis_set = set(s.entity_uuids) if s.entity_uuids else None
                visible = filter_combat_log(entries, s.entity_uuids, vis_set)
                log_lines: List[str] = []
                for entry in visible:
                    log_lines.extend(format_combat_log_entry(entry))
                slot_combat_logs[s.slot_id] = "\n".join(log_lines)
            except Exception:
                slot_combat_logs[s.slot_id] = ""

        reflection_threads: List[threading.Thread] = []
        for s in slots:
            log(f"  Starting reflection for {s.slot_id}...")
            t = threading.Thread(
                target=run_post_game_reflection,
                args=(s, state),
                kwargs={
                    "combat_log_text": slot_combat_logs.get(s.slot_id, ""),
                    "series_result": series_result,
                },
            )
            t.start()
            reflection_threads.append(t)
        for t in reflection_threads:
            t.join(timeout=120)

    except KeyboardInterrupt:
        log("\n\nInterrupted by user.")
    except Exception as e:
        log(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        _cleanup_subprocesses()
        spectator.close()
        hero_client.close()
        monster_client.close()
        if server_proc:
            log("Stopping server...")
            server_proc.terminate()
            server_proc.wait(timeout=5)


if __name__ == "__main__":
    main()
