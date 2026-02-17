"""PvP Orchestrator: Claude vs Claude with spectator mode.

Run from a terminal:
    source .venv/bin/activate && python -m cli.orchestrator

Flags:
    --dry-run    Skip Claude subprocesses, just end turns (for testing the loop)

Launches two Claude subprocesses (hero + monsters) that take turns
playing D&D via the agent CLI. The user watches as spectator.
"""

import json
import os
import secrets
import string
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from cli.api_client import APIClient
from cli.agent import format_combat_log_entry


def log(msg: str) -> None:
    """Print with flush so output appears immediately in pipes/subprocesses."""
    print(msg, flush=True)


DRY_RUN = "--dry-run" in sys.argv
SERVER_URL = "http://localhost:8000"
PROJECT_DIR = Path(__file__).resolve().parent.parent  # dnd_engine root
SCRATCH_DIR = Path("/tmp/dnd_game")
LOG_DIR = PROJECT_DIR / "game_logs" / "turns"
NOTEBOOK_DIR = PROJECT_DIR / "game_logs" / "notebooks"
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


def display_stream_event(event: dict, slot_id: str) -> None:
    """Display stream-json event for spectator."""
    event_type = event.get("type")

    if event_type == "tool_use":
        tool = event.get("tool", "")
        if tool == "Bash":
            cmd_text = event.get("input", {}).get("command", "")
            if "cli.agent" in cmd_text:
                # Extract the command after "cli.agent --token <token>"
                parts = cmd_text.split("cli.agent")[-1].strip()
                # Strip "--token <random_token>" prefix for clean display
                if parts.startswith("--token"):
                    token_parts = parts.split(None, 2)  # ["--token", "a7k3p2", "move 5 3"]
                    parts = token_parts[2] if len(token_parts) > 2 else parts
                log(f"  [{slot_id}] > {parts}")
        elif tool == "Write":
            filepath = event.get("input", {}).get("file_path", "")
            if "notebook" in filepath.lower():
                log(f"  [{slot_id}] > (writing notebook)")

    elif event_type == "tool_result":
        content = event.get("content", "")
        if content and isinstance(content, str):
            first_line = content.split("\n")[0][:120]
            log(f"  [{slot_id}]   {first_line}")

    elif event_type == "assistant":
        # Show Claude's thinking/text (truncated)
        msg = event.get("message", "")
        if msg and isinstance(msg, str):
            first_line = msg.strip().split("\n")[0][:120]
            if first_line:
                log(f"  [{slot_id}] {first_line}")


def run_claude_turn(slot: PlayerSlot, prompt: str, max_turns: int = 20) -> dict:
    """Run a Claude turn as a blocking subprocess.

    Uses stream-json for real-time spectator view.
    Captures session_id from final result event.
    """
    cmd = ["claude", "-p", prompt]

    # Output format
    cmd += ["--output-format", "stream-json", "--verbose"]

    # Tool restrictions: ONLY agent CLI with this slot's random token + notebook R/W
    agent_prefix = (
        f"source .venv/bin/activate && "
        f"python -m cli.agent --token {slot.token}"
    )
    cmd += ["--allowedTools", f"Bash({agent_prefix} *)"]
    cmd += ["--allowedTools", f"Read({NOTEBOOK_DIR}/*)"]
    cmd += ["--allowedTools", f"Write({NOTEBOOK_DIR}/*)"]

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

    raw_lines: List[str] = []
    session_id = None

    try:
        assert process.stdout is not None
        for line in process.stdout:
            raw_lines.append(line)
            line_stripped = line.strip()
            if not line_stripped:
                continue
            try:
                event = json.loads(line_stripped)
                display_stream_event(event, slot.slot_id)
                if event.get("type") == "result":
                    session_id = event.get("session_id", session_id)
            except json.JSONDecodeError:
                pass

        process.wait(timeout=180)  # 3-minute timeout

    except subprocess.TimeoutExpired:
        log(f"  TIMEOUT: Claude ({slot.slot_id}) exceeded 3 minutes. Killing.")
        process.kill()
        process.wait()

    if session_id:
        slot.claude_session_id = session_id

    returncode = process.returncode
    if returncode and returncode != 0:
        stderr_out = process.stderr.read() if process.stderr else ""
        log(f"  WARNING: Claude exited with code {returncode}")
        if stderr_out:
            log(f"  stderr: {stderr_out[:300]}")

    return {
        "session_id": session_id,
        "returncode": returncode,
        "raw_output": "".join(raw_lines),
    }


# ---------------------------------------------------------------------------
# Turn verification
# ---------------------------------------------------------------------------

def verify_turn_ended(slot_client: APIClient, slot: PlayerSlot, entity_uuid: str) -> None:
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

def run_post_game_reflection(slot: PlayerSlot, state: dict) -> None:
    """After encounter ends, ask Claude to write reflections."""
    if DRY_RUN:
        log(f"  [dry-run] Skipping reflection for {slot.slot_id}")
        return
    prompt = (
        f"The game is over. Final results:\n"
        f"{format_final_results(state)}\n\n"
        f"Please write a post-game reflection to your notebook. Include:\n"
        f"1. What strategies worked and what didn't\n"
        f"2. Things you didn't understand about the game mechanics\n"
        f"3. Commands that behaved unexpectedly or bugs you think you found\n"
        f"4. What you would do differently next time\n"
        f"5. Any confusion about the rules or available actions\n\n"
        f"Write your reflections to your notebook, then you're done."
    )
    result = run_claude_turn(slot, prompt, max_turns=5)
    log_file = LOG_DIR / f"reflection_{slot.slot_id}.log"
    with open(log_file, "w") as f:
        f.write(result.get("raw_output", ""))
    log(f"  Reflection logged: {log_file}")


# ---------------------------------------------------------------------------
# Turn loop
# ---------------------------------------------------------------------------

def turn_loop(
    spectator: APIClient,
    slots: List[PlayerSlot],
    slot_clients: Dict[str, APIClient],
) -> None:
    round_num = 0

    while True:
        state = spectator.get_state()
        encounter = state.get("encounter", {})

        if encounter.get("state") != "active":
            log("\n=== ENCOUNTER ENDED ===")
            show_final_results(state)
            # Post-game reflections
            for slot in slots:
                log(f"\n  Requesting reflection from {slot.slot_id}...")
                run_post_game_reflection(slot, state)
            break

        active_uuid = encounter.get("current_entity_uuid")
        current_round = encounter.get("round_number", 1)

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

        # Get visibility for subjective view
        visibility = spectator.get_visibility()
        vis_set: Optional[set] = None
        if active_uuid in visibility:
            vis_data = visibility[active_uuid]
            vis_set = set(vis_data.get("visible_entities", []))
            vis_set.update(slot.entity_uuids)

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

        # Build prompt
        from cli.prompt_builder import build_turn_prompt
        prompt = build_turn_prompt(
            faction=slot.faction,
            entity_name=entity_name,
            active_entity_uuid=active_uuid,
            controlled_uuids=slot.entity_uuids,
            state=state,
            actions=actions,
            combat_log_entries=new_entries,
            round_number=round_num,
            notebook_content=notebook_content,
            visible_entity_uuids=vis_set,
        )

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
            # Run Claude subprocess (blocking)
            result = run_claude_turn(slot, prompt)

            # Log raw output
            safe_name = entity_name.replace(" ", "_")
            log_file = LOG_DIR / f"turn_{round_num}_{safe_name}.log"
            with open(log_file, "w") as f:
                f.write(result.get("raw_output", ""))
            log(f"  Log: {log_file}")

            # Verify turn ended — force end if Claude forgot
            slot_client = slot_clients[slot.slot_id]
            verify_turn_ended(slot_client, slot, active_uuid)

        # Show post-turn combat log to spectator
        log_data = spectator.get_combat_log(since=slot.combat_log_index)
        post_entries = log_data.get("entries", [])
        if post_entries:
            for entry in post_entries:
                for line in format_combat_log_entry(entry):
                    log(f"  [LOG] {line}")
        slot.combat_log_index = log_data.get("total", slot.combat_log_index)

        time.sleep(0.5)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if DRY_RUN:
        log("=== DRY RUN MODE (no Claude subprocesses) ===")

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
        # 3. Start PvP game (sorcerer hero)
        pvp_result = spectator.start_pvp_game(character_class="sorcerer")
        log(f"PvP started: {pvp_result.get('message', '')}")

        # 4. Get entities by faction
        state = spectator.get_state()
        hero_uuids, monster_uuids = partition_by_faction(state)
        log(f"Heroes: {len(hero_uuids)} entities, Monsters: {len(monster_uuids)} entities")

        # 5. Create slots with random tokens
        hero_token = generate_token()
        monster_token = generate_token()

        hero_slot = PlayerSlot(
            slot_id="hero", token=hero_token, faction="heroes",
            entity_uuids=hero_uuids,
            notebook_path=NOTEBOOK_DIR / "hero.md",
            prompt_file=SCRATCH_DIR / f"prompt_{hero_token}.md",
        )
        monster_slot = PlayerSlot(
            slot_id="monsters", token=monster_token, faction="monsters",
            entity_uuids=monster_uuids,
            notebook_path=NOTEBOOK_DIR / "monsters.md",
            prompt_file=SCRATCH_DIR / f"prompt_{monster_token}.md",
        )

        log(f"Tokens: hero={hero_token}, monsters={monster_token}")

        # 6. Create server sessions and join
        hero_client.create_session(player_type="claude", name="Claude Hero")
        hero_client.join_game(entity_uuids=hero_uuids)
        hero_slot.server_session_id = hero_client.session_id

        monster_client.create_session(player_type="claude", name="Claude Monsters")
        monster_client.join_game(entity_uuids=monster_uuids)
        monster_slot.server_session_id = monster_client.session_id

        log(f"Sessions created: hero={hero_slot.server_session_id}, "
            f"monsters={monster_slot.server_session_id}")

        # 7. Generate per-slot system prompt files
        generate_prompt_files(hero_slot, monster_slot)

        # 8. Create empty notebooks
        if hero_slot.notebook_path:
            hero_slot.notebook_path.write_text("")
        if monster_slot.notebook_path:
            monster_slot.notebook_path.write_text("")

        # 9. Map slots to their APIClient for force-end-turn
        slot_clients: Dict[str, APIClient] = {
            "hero": hero_client,
            "monsters": monster_client,
        }

        # 10. Run turn loop
        log("\n=== GAME START ===\n")
        turn_loop(spectator, [hero_slot, monster_slot], slot_clients)

    except KeyboardInterrupt:
        log("\n\nInterrupted by user.")
    except Exception as e:
        log(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        spectator.close()
        hero_client.close()
        monster_client.close()
        if server_proc:
            log("Stopping server...")
            server_proc.terminate()
            server_proc.wait(timeout=5)


if __name__ == "__main__":
    main()
