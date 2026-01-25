"""
Display module for full-screen TUI with Rich.
"""

from typing import Dict, Any, List, Optional, Tuple
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
import sys
import shutil


console = Console()

# Track if we're in alternate screen mode
_in_alternate_screen = False

# Store rich combat log entries (full action data, not just strings)
_combat_log: List[Dict[str, Any]] = []
MAX_COMBAT_LOG = 10  # Max entries to show

# Output buffer for command feedback (valid positions, attack options, etc.)
_output_buffer: List[str] = []
MAX_OUTPUT_LINES = 6

# Session/connection info for header
_session_info: Dict[str, Any] = {
    "hero_connected": False,
    "claude_connected": False,
    "session_id": None,
    "pvp_mode": False,
}

# Turn history for replay
_turn_history: List[Dict[str, Any]] = []  # List of cached states
_history_index: Optional[int] = None  # None = viewing current, int = viewing history


def enter_alternate_screen():
    """Enter alternate screen buffer (like vim/htop). Content won't scroll past terminal."""
    global _in_alternate_screen
    if not _in_alternate_screen and sys.stdout.isatty():
        sys.stdout.write("\033[?1049h")
        sys.stdout.flush()
        _in_alternate_screen = True


def exit_alternate_screen():
    """Exit alternate screen buffer, returning to normal terminal."""
    global _in_alternate_screen
    if _in_alternate_screen:
        sys.stdout.write("\033[?1049l")
        sys.stdout.flush()
        _in_alternate_screen = False


def clear():
    """Clear the terminal."""
    if _in_alternate_screen:
        sys.stdout.write("\033[H\033[J")
        sys.stdout.flush()
    else:
        console.clear()


def add_to_combat_log(entry: Dict[str, Any]):
    """Add a rich entry to the combat log."""
    global _combat_log
    _combat_log.append(entry)
    # Keep only recent entries
    if len(_combat_log) > MAX_COMBAT_LOG * 2:
        _combat_log = _combat_log[-MAX_COMBAT_LOG * 2:]


def add_simple_log(message: str):
    """Add a simple text message to the combat log."""
    add_to_combat_log({"type": "message", "message": message})


def clear_combat_log():
    """Clear the combat log."""
    global _combat_log
    _combat_log = []


def get_combat_log() -> List[Dict[str, Any]]:
    """Get the combat log entries."""
    return _combat_log.copy()


# ============================================================================
# Output Buffer (for command feedback)
# ============================================================================

def set_output(lines: List[str]):
    """Set the output buffer content."""
    global _output_buffer
    _output_buffer = lines[-MAX_OUTPUT_LINES:]


def add_output(line: str):
    """Add a line to the output buffer."""
    global _output_buffer
    _output_buffer.append(line)
    if len(_output_buffer) > MAX_OUTPUT_LINES:
        _output_buffer = _output_buffer[-MAX_OUTPUT_LINES:]


def clear_output():
    """Clear the output buffer."""
    global _output_buffer
    _output_buffer = []


def get_output() -> List[str]:
    """Get the output buffer."""
    return _output_buffer.copy()


# ============================================================================
# Session Info (for header)
# ============================================================================

def set_session_info(
    hero_connected: Optional[bool] = None,
    claude_connected: Optional[bool] = None,
    session_id: Optional[str] = None,
    pvp_mode: Optional[bool] = None
):
    """Update session info for header display."""
    global _session_info
    if hero_connected is not None:
        _session_info["hero_connected"] = hero_connected
    if claude_connected is not None:
        _session_info["claude_connected"] = claude_connected
    if session_id is not None:
        _session_info["session_id"] = session_id
    if pvp_mode is not None:
        _session_info["pvp_mode"] = pvp_mode


def get_session_info() -> Dict[str, Any]:
    """Get session info."""
    return _session_info.copy()


# ============================================================================
# Turn History Management
# ============================================================================

def save_turn_snapshot(
    turn: Dict[str, Any],
    entities: List[Dict[str, Any]],
    grid: Dict[str, Any],
    combat_log: Optional[List[Dict[str, Any]]] = None
):
    """Save a snapshot of the current turn state for history replay."""
    global _turn_history, _combat_log

    snapshot = {
        "turn": turn.copy() if turn else {},
        "entities": [e.copy() for e in entities] if entities else [],
        "grid": grid,  # Grid doesn't change, just reference it
        "combat_log": [e.copy() for e in (combat_log or _combat_log)],
        "round": turn.get("round_number", 1) if turn else 1,
        "entity_name": turn.get("current_entity_name", "???") if turn else "???",
    }
    _turn_history.append(snapshot)


def get_history_count() -> int:
    """Get total number of saved turns."""
    return len(_turn_history)


def get_history_index() -> Optional[int]:
    """Get current history index (None = current turn)."""
    return _history_index


def is_viewing_history() -> bool:
    """Check if we're viewing historical state."""
    return _history_index is not None


def goto_previous_turn() -> Optional[Dict[str, Any]]:
    """Go to previous turn in history. Returns snapshot or None."""
    global _history_index

    if not _turn_history:
        return None

    if _history_index is None:
        # Currently viewing current - go to last saved
        _history_index = len(_turn_history) - 1
    elif _history_index > 0:
        _history_index -= 1

    return _turn_history[_history_index] if _history_index is not None else None


def goto_next_turn() -> Optional[Dict[str, Any]]:
    """Go to next turn in history. Returns snapshot or None if at current."""
    global _history_index

    if _history_index is None:
        return None  # Already at current

    if _history_index < len(_turn_history) - 1:
        _history_index += 1
        return _turn_history[_history_index]
    else:
        # At end of history, return to current
        _history_index = None
        return None


def goto_current_turn():
    """Return to viewing current turn."""
    global _history_index
    _history_index = None


def goto_first_turn() -> Optional[Dict[str, Any]]:
    """Go to first turn in history."""
    global _history_index

    if not _turn_history:
        return None

    _history_index = 0
    return _turn_history[0]


def get_current_snapshot() -> Optional[Dict[str, Any]]:
    """Get the snapshot at current history index, or None if viewing current turn."""
    if _history_index is None or not _turn_history:
        return None
    if 0 <= _history_index < len(_turn_history):
        return _turn_history[_history_index]
    return None


def clear_history():
    """Clear turn history."""
    global _turn_history, _history_index
    _turn_history = []
    _history_index = None


def get_terminal_size() -> Tuple[int, int]:
    """Get terminal width and height."""
    size = shutil.get_terminal_size((80, 24))
    return size.columns, size.lines


def render_map_content(
    grid: Dict[str, Any],
    entities: List[Dict[str, Any]],
    current_entity_uuid: Optional[str] = None,
    valid_positions: Optional[List[Tuple[int, int]]] = None,
    visibility: Optional[Dict[str, Any]] = None,
    movement_path: Optional[List[Tuple[int, int]]] = None
) -> Text:
    """Render ASCII map with Rich formatting."""
    tiles = {(t["x"], t["y"]): t for t in grid.get("tiles", [])}
    min_x, min_y = grid.get("min_x", 0), grid.get("min_y", 0)
    max_x, max_y = grid.get("max_x", 14), grid.get("max_y", 14)

    entity_at = {}
    for e in entities:
        pos = tuple(e["position"])
        entity_at[pos] = e

    valid_set = set(tuple(p) for p in valid_positions) if valid_positions else set()
    path_set = set(tuple(p) for p in movement_path) if movement_path else set()

    hero_visible = set()
    enemy_visible = set()
    if visibility and current_entity_uuid:
        for uuid, data in visibility.items():
            cells = set(tuple(c) for c in data.get("visible_cells", []))
            if uuid == current_entity_uuid:
                hero_visible = cells
            else:
                enemy_visible.update(cells)

    result = Text()

    # Header row with column numbers
    result.append("   ")
    for x in range(min_x, max_x + 1):
        result.append(f"{x % 10} ")
    result.append("\n")

    # Top border
    result.append("  +" + "-" * ((max_x - min_x + 1) * 2 + 1) + "+\n")

    for y in range(max_y, min_y - 1, -1):
        result.append(f"{y:2}|")
        for x in range(min_x, max_x + 1):
            pos = (x, y)
            tile = tiles.get(pos)
            entity = entity_at.get(pos)

            if entity:
                if entity["uuid"] == current_entity_uuid:
                    char, style = "@", "bold green"
                elif entity.get("is_dead"):
                    char, style = "%", "dim"
                else:
                    char, style = entity["name"][0].upper(), "bold red"
            elif pos in path_set:
                char, style = "+", "bold magenta"
            elif pos in valid_set:
                char, style = "*", "bold yellow"
            elif tile is None:
                char, style = " ", ""
            elif not tile.get("walkable", True):
                char, style = "#", "white"
            else:
                char = "."
                in_hero = pos in hero_visible
                in_enemy = pos in enemy_visible
                if in_hero and in_enemy:
                    style = "yellow"
                elif in_hero:
                    style = "green"
                elif in_enemy:
                    style = "red"
                else:
                    style = "dim"

            result.append(" ")
            result.append(char, style=style)
        result.append(" |\n")

    result.append("  +" + "-" * ((max_x - min_x + 1) * 2 + 1) + "+\n")

    # Legend
    result.append("@ ", style="bold green")
    result.append("You  ")
    result.append("X ", style="bold red")
    result.append("Enemy  ")
    result.append("# ", style="white")
    result.append("Wall  ")
    result.append("+ ", style="bold magenta")
    result.append("Path")

    return result


def render_header_panel(
    history_mode: bool = False,
    history_position: Optional[str] = None
) -> Panel:
    """Render the header panel with app name and connection info only."""
    global _session_info

    content = Text()

    if history_mode:
        content.append(f"HISTORY MODE {history_position or ''}", style="bold yellow")
    elif _session_info.get("pvp_mode"):
        content.append("PvP Mode", style="bold")
        content.append("  │  ")
        # Hero connection
        content.append("Hero: ", style="dim")
        if _session_info.get("hero_connected"):
            content.append("● Connected", style="green")
        else:
            content.append("○ Waiting", style="red")
        content.append("  │  ")
        # Claude connection
        content.append("Claude: ", style="dim")
        if _session_info.get("claude_connected"):
            content.append("● Connected", style="green")
        else:
            content.append("○ Waiting", style="yellow")
    else:
        content.append("Solo Mode", style="bold")
        content.append("  │  ")
        content.append("Human vs AI", style="dim")

    border_style = "yellow" if history_mode else "cyan"
    return Panel(content, title="⚔ NEURODRAGON ⚔", box=box.DOUBLE, border_style=border_style)


def render_combatants_panel(
    entities: List[Dict[str, Any]],
    turn: Dict[str, Any],
    current_entity_uuid: Optional[str] = None,
    is_my_turn: bool = True
) -> Panel:
    """Render the combatants table panel with turn info in title."""
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("Entity", style="cyan")
    table.add_column("HP", justify="right")
    table.add_column("AC", justify="center")
    table.add_column("Pos", justify="center")
    table.add_column("Conditions")

    active_uuid = turn.get("current_entity_uuid")
    for e in entities:
        is_active = e["uuid"] == active_uuid
        is_me = e["uuid"] == current_entity_uuid
        name = e['name']
        if e.get("is_dead"):
            name = f"[dim strikethrough]{name}[/dim strikethrough]"
        elif is_active and is_my_turn:
            name = f"[bold green]► {name}[/bold green]"
        elif is_active:
            name = f"[bold red]► {name}[/bold red]"
        elif is_me:
            name = f"[green]{name}[/green]"

        hp_val = e["hp"]
        max_hp = e["max_hp"]
        hp_pct = hp_val / max_hp if max_hp > 0 else 0
        hp_color = "green" if hp_pct > 0.5 else "yellow" if hp_pct > 0.25 else "red"
        hp = f"[{hp_color}]{hp_val}/{max_hp}[/{hp_color}]"

        conditions = ", ".join(e.get("conditions", [])) or "-"
        pos = f"({e['position'][0]},{e['position'][1]})"
        table.add_row(name, hp, str(e.get("ac", "?")), pos, conditions)

    # Build title with round and turn info
    round_num = turn.get("round_number", 1)
    current_name = turn.get("current_entity_name", "???")
    turn_indicator = "[green]YOUR TURN[/green]" if is_my_turn else "[red]OPPONENT[/red]"
    title = f"Round {round_num} │ {current_name} │ {turn_indicator}"

    border_style = "green" if is_my_turn else "red"
    return Panel(table, title=title, box=box.ROUNDED, border_style=border_style)


def render_output_panel() -> Optional[Panel]:
    """Render the output buffer panel (command feedback)."""
    global _output_buffer

    if not _output_buffer:
        return None

    content = Text()
    for i, line in enumerate(_output_buffer):
        if i > 0:
            content.append("\n")
        content.append(line)

    return Panel(content, title="Output", box=box.ROUNDED, border_style="magenta")


def render_turn_info_panel(
    turn: Dict[str, Any],
    entities: List[Dict[str, Any]],
    is_my_turn: bool,
    actions: Optional[Dict[str, Any]] = None,
    history_mode: bool = False,
    history_position: Optional[str] = None
) -> Panel:
    """Render turn info and entity status as a panel."""
    current_uuid = turn.get("current_entity_uuid")
    current = next((e for e in entities if e["uuid"] == current_uuid), None)
    round_num = turn.get("round_number", 1)

    # Turn indicator
    if history_mode:
        turn_text = f"[bold yellow]HISTORY[/bold yellow] {history_position or ''}"
    elif is_my_turn:
        turn_text = "[bold green]YOUR TURN[/bold green]"
    else:
        turn_text = "[bold red]OPPONENT'S TURN[/bold red]"
    current_name = current["name"] if current else "???"

    # Entity table
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("Entity", style="cyan")
    table.add_column("HP", justify="right")
    table.add_column("AC", justify="center")
    table.add_column("Position", justify="center")
    table.add_column("Conditions")

    for e in entities:
        is_current = e["uuid"] == current_uuid
        name = e['name']
        if e.get("is_dead"):
            name = f"[dim strikethrough]{name}[/dim strikethrough]"
        elif is_current and is_my_turn:
            name = f"[bold green]{name}[/bold green]"
        elif is_current:
            name = f"[bold]{name}[/bold]"

        hp_val = e["hp"]
        max_hp = e["max_hp"]
        hp_color = "green" if hp_val > max_hp // 2 else "yellow" if hp_val > 0 else "red"
        hp = f"[{hp_color}]{hp_val}/{max_hp}[/{hp_color}]"

        conditions = ", ".join(e.get("conditions", [])) or "-"
        table.add_row(name, hp, str(e.get("ac", "?")), f"({e['position'][0]},{e['position'][1]})", conditions)

    # Action economy line
    economy_line = ""
    if is_my_turn:
        economy_line = (
            f"\n[bold]Economy:[/bold] "
            f"Actions:[cyan]{turn.get('actions_remaining', 0)}[/cyan] "
            f"Bonus:[cyan]{turn.get('bonus_actions_remaining', 0)}[/cyan] "
            f"Move:[cyan]{turn.get('movement_remaining', 0)}ft[/cyan] "
            f"React:[cyan]{turn.get('reactions_remaining', 0)}[/cyan]"
        )

    content = Group(table, Text.from_markup(economy_line) if economy_line else Text(""))
    title = f"Round {round_num} │ {current_name} │ {turn_text}"

    return Panel(content, title=title, box=box.ROUNDED, border_style="blue")


def _format_breakdown(breakdown: List[Dict[str, Any]]) -> str:
    """Format breakdown list as '[DEX +2, Prof +2]'."""
    if not breakdown:
        return ""
    parts = []
    for m in breakdown:
        val = m.get('value', 0)
        if val == 0:
            continue
        name = m.get('name', 'Unknown')
        parts.append(f"{name} {val:+d}")
    return f"[{', '.join(parts)}]" if parts else ""


def _render_log_entry(entry: Dict[str, Any], content: Text):
    """Render a single combat log entry with rich formatting."""
    entry_type = entry.get("type", "message")

    if entry_type == "attack":
        attacker = entry.get("attacker", "Someone")
        target = entry.get("target", "Unknown")
        weapon = entry.get("weapon", "weapon")
        d20 = entry.get("d20", 0)
        all_rolls = entry.get("all_d20_rolls", [d20])
        adv_status = entry.get("advantage_status", "none")
        attack_bonus = entry.get("attack_bonus", 0)
        attack_total = entry.get("attack_total", 0)
        target_ac = entry.get("target_ac", 0)
        outcome = (entry.get("outcome") or "").lower()
        total_damage = entry.get("total_damage", 0)

        # Get breakdown data
        attack_breakdown = entry.get("attack_breakdown", [])
        ac_breakdown = entry.get("ac_breakdown", [])
        damage_breakdown = entry.get("damage_breakdown", [])
        damage_dice_str = entry.get("damage_dice_str", "")
        damage_rolls = entry.get("damage_rolls", [])
        is_opportunity_attack = entry.get("is_opportunity_attack", False)

        # Header: Attacker → Target (Weapon)
        content.append(f"{attacker}", style="bold cyan")
        content.append(" → ")
        content.append(f"{target}", style="bold yellow")
        content.append(f" ({weapon})", style="dim")

        # Add advantage indicator
        if adv_status == "advantage":
            content.append(" ADV", style="green")
        elif adv_status == "disadvantage":
            content.append(" DIS", style="red")

        content.append("\n")

        # Attack roll line with breakdown - show (OA) after "Attack:"
        if is_opportunity_attack:
            content.append("  Attack ", style="dim")
            content.append("(OA)", style="bold magenta")
            content.append(": ", style="dim")
        else:
            content.append("  Attack: ", style="dim")

        # d20 roll(s)
        if adv_status in ["advantage", "disadvantage"] and len(all_rolls) >= 2:
            content.append(f"d20({all_rolls[0]},{all_rolls[1]}→{d20})", style="cyan")
        else:
            content.append(f"d20({d20})", style="cyan")

        # Attack bonus with breakdown
        bonus_str = f" {attack_bonus:+d}" if attack_bonus != 0 else ""
        content.append(bonus_str)
        if attack_breakdown:
            content.append(f" {_format_breakdown(attack_breakdown)}", style="dim")

        # = total vs AC
        content.append(f" = {attack_total} vs AC {target_ac}")
        if ac_breakdown:
            content.append(f" {_format_breakdown(ac_breakdown)}", style="dim")

        content.append(" → ")

        # Outcome
        if outcome == "crit":
            content.append("CRIT!", style="bold yellow")
        elif outcome == "hit":
            content.append("HIT", style="green")
        elif outcome == "crit miss":
            content.append("FUMBLE!", style="bold red")
        else:
            content.append("MISS", style="dim")

        # Damage line (only on hit/crit)
        if outcome in ["hit", "crit"] and total_damage > 0:
            content.append("\n")
            content.append("  Damage: ", style="dim")

            # Show damage dice
            if damage_rolls and len(damage_rolls) > 0:
                dr = damage_rolls[0]
                dice = dr.get("dice", [])
                bonus = dr.get("bonus", 0)
                if dice:
                    dice_str = ",".join(str(d) for d in dice)
                    content.append(f"{damage_dice_str}({dice_str})", style="red")
                else:
                    content.append(f"{damage_dice_str}", style="red")

                # Damage bonus with breakdown
                if bonus != 0:
                    content.append(f" {bonus:+d}")
                if damage_breakdown:
                    content.append(f" {_format_breakdown(damage_breakdown)}", style="dim")

                content.append(f" = {total_damage}", style="bold red")
            else:
                content.append(f"{total_damage}", style="bold red")

    elif entry_type == "move":
        mover = entry.get("entity", "Someone")
        from_pos = entry.get("from", [0, 0])
        to_pos = entry.get("to", [0, 0])
        content.append(f"{mover}", style="bold cyan")
        content.append(" moved ")
        content.append(f"({from_pos[0]},{from_pos[1]})→({to_pos[0]},{to_pos[1]})", style="green")

    elif entry_type == "death":
        entity = entry.get("entity", "Someone")
        content.append(f"☠ {entity} defeated!", style="bold red")

    elif entry_type == "action":
        entity = entry.get("entity", "Someone")
        action_name = entry.get("action", "action")
        content.append(f"{entity}", style="bold cyan")
        content.append(f" uses ", style="dim")
        content.append(f"{action_name.title()}", style="bold magenta")

    elif entry_type == "turn_end":
        entity = entry.get("entity", "Someone")
        content.append(f"─ {entity}'s turn ends ─", style="dim")

    else:
        # Simple message fallback
        message = entry.get("message", str(entry))
        content.append(f"{message}", style="dim")


def render_combat_log_panel() -> Panel:
    """Render the combat log with rich formatting."""
    global _combat_log

    content = Text()
    entries = _combat_log[-MAX_COMBAT_LOG:]

    if not entries:
        content.append("No combat history yet", style="dim")
    else:
        for i, entry in enumerate(entries):
            if i > 0:
                content.append("\n")
            _render_log_entry(entry, content)

    return Panel(content, title="Combat Log", box=box.ROUNDED, border_style="blue")


def render_available_actions_panel(
    actions: Dict[str, Any],
    entities: List[Dict[str, Any]],
    turn: Dict[str, Any]
) -> Panel:
    """Render available actions as a compact panel with economy in title."""
    content = Text()
    entity_lookup = {e["uuid"]: e for e in entities}

    actions_remaining = turn.get("actions_remaining", 0)
    bonus_remaining = turn.get("bonus_actions_remaining", 0)
    movement_remaining = actions.get("remaining_movement", 0)
    reactions_remaining = turn.get("reactions_remaining", 0)

    # Movement - new format uses position_actions, old uses can_move
    has_movement = actions.get("position_actions") or actions.get("can_move")
    if has_movement and movement_remaining > 0:
        content.append("MOVE", style="bold cyan")
        content.append(f" ({movement_remaining}ft)  ")
        content.append("[m X Y] or [m] to show positions\n", style="dim")

    # Attacks - show all available attack options with target numbers
    # Support both old format (attacks) and new format (entity_actions)
    attacks = actions.get("entity_actions", actions.get("attacks", []))
    valid_attacks = [a for a in attacks if a.get("valid_targets") and a.get("can_afford")]

    if valid_attacks:
        content.append("ATTACKS:", style="bold red")
        content.append("  [a N] to attack\n", style="dim")
        target_num = 1
        for atk in valid_attacks:
            targets = atk.get("valid_targets", [])
            cost_type = atk.get("cost_type", "actions")

            # Cost label with color
            if cost_type == "bonus_actions":
                cost_label = ("BONUS", "magenta")
            else:
                cost_label = ("ACTION", "cyan")

            # Get weapon/action display name (new format: display_name/weapon_name, old: name)
            action_name = atk.get("weapon_name") or atk.get("display_name") or atk.get("name", "Attack")

            for target in targets:
                # Handle both old format (UUID string) and new format (dict with target_uuid/target_name)
                if isinstance(target, dict):
                    target_uuid = target.get("target_uuid")
                    target_name = target.get("target_name") or entity_lookup.get(target_uuid, {}).get("name", "?")
                else:
                    # Old format: target is just a UUID string
                    target_uuid = target
                    target_name = entity_lookup.get(target_uuid, {}).get("name", "?")

                content.append(f"  [", style="dim")
                content.append(f"{target_num}", style="bold yellow")
                content.append(f"] ", style="dim")
                content.append(f"{cost_label[0]} ", style=cost_label[1])
                content.append(f"{action_name}", style="bold")
                content.append(f" -> {target_name}\n", style="dim")
                target_num += 1
    elif attacks:
        content.append("ATTACK", style="dim")
        content.append(" - no targets in range\n", style="dim")

    # Other actions (horizontal)
    # Support both old format (other_actions with action_id) and new format (self_actions with template_name)
    other = actions.get("self_actions", actions.get("other_actions", []))
    other_items = []
    for act in other:
        if act.get("can_afford"):
            # Get action name from template_name (new) or action_id (old)
            action_id = (act.get("template_name") or act.get("action_id", "")).lower()
            if action_id == "dash":
                other_items.append(("DASH", "bold magenta", "[d]"))
            elif action_id == "dodge":
                other_items.append(("DODGE", "bold blue", "[o]"))
            elif action_id == "disengage":
                other_items.append(("DISENGAGE", "bold green", "[i]"))
            elif action_id == "standup":
                other_items.append(("STAND UP", "bold yellow", "[su]"))

    if other_items:
        for i, (name, style, key) in enumerate(other_items):
            if i > 0:
                content.append("  ")
            content.append(name, style=style)
            content.append(f" {key}", style="dim")
        content.append("\n")

    # Always available
    content.append("END", style="bold white")
    content.append(" [e]  ", style="dim")
    content.append("HELP", style="bold white")
    content.append(" [?]  ", style="dim")
    content.append("QUIT", style="bold white")
    content.append(" [q]", style="dim")

    # Build title with action economy
    title = f"Actions:{actions_remaining} Bonus:{bonus_remaining} Move:{movement_remaining}ft React:{reactions_remaining}"

    return Panel(content, title=title, box=box.ROUNDED, border_style="green")


def render_history_snapshot(snapshot: Dict[str, Any], current_entity_uuid: Optional[str] = None):
    """Render a historical turn snapshot."""
    global _combat_log

    # Temporarily set combat log from snapshot
    old_combat_log = _combat_log
    _combat_log = snapshot.get("combat_log", [])

    history_pos = f"[{_history_index + 1}/{len(_turn_history)}]" if _history_index is not None else ""

    clear()

    # Header panel with history indicator
    header_panel = render_header_panel(
        history_mode=True,
        history_position=history_pos
    )

    # Map panel
    map_content = render_map_content(
        snapshot["grid"],
        snapshot["entities"],
        current_entity_uuid,
        None, None, None
    )
    map_panel = Panel(map_content, title="Battlefield (History)", box=box.ROUNDED, border_style="yellow")

    # Combatants panel (showing historical state)
    combatants_panel = render_combatants_panel(
        snapshot["entities"],
        snapshot["turn"],
        current_entity_uuid,
        is_my_turn=False  # In history mode, never "your turn"
    )

    # Combat log panel
    log_panel = render_combat_log_panel()

    # Print panels (with top padding to avoid cutoff)
    console.print()  # Top margin
    console.print(header_panel)
    console.print(map_panel)
    console.print(combatants_panel)
    console.print(log_panel)

    # History navigation help
    console.print("[dim]History: [pt] prev [nt] next [ft] first [ct] current[/dim]")

    # Restore
    _combat_log = old_combat_log


def render_full_screen(
    grid: Dict[str, Any],
    entities: List[Dict[str, Any]],
    turn: Dict[str, Any],
    current_entity_uuid: Optional[str] = None,
    actions: Optional[Dict[str, Any]] = None,
    visibility: Optional[Dict[str, Any]] = None,
    movement_path: Optional[List[Tuple[int, int]]] = None,
    valid_positions: Optional[List[Tuple[int, int]]] = None,
    is_my_turn: bool = True
):
    """Render the full screen layout."""
    clear()

    # 1. Header panel (NEURODRAGON + connection info only)
    header_panel = render_header_panel()

    # 2. Battlefield panel (map)
    map_content = render_map_content(
        grid, entities, current_entity_uuid, valid_positions, visibility, movement_path
    )
    map_panel = Panel(map_content, title="Battlefield", box=box.ROUNDED, border_style="cyan")

    # 3. Combatants panel (entity table with turn info in title)
    combatants_panel = render_combatants_panel(entities, turn, current_entity_uuid, is_my_turn)

    # 4. Combat log panel
    log_panel = render_combat_log_panel()

    # 5. Output panel (command feedback - only if there's content)
    output_panel = render_output_panel()

    # 6. Available actions panel (only on player's turn, with economy in title)
    actions_panel = None
    if is_my_turn and actions:
        actions_panel = render_available_actions_panel(actions, entities, turn)

    # Print all panels in order (with top padding to avoid cutoff)
    console.print()  # Top margin
    console.print(header_panel)
    console.print(map_panel)
    console.print(combatants_panel)
    console.print(log_panel)
    if output_panel:
        console.print(output_panel)
    if actions_panel:
        console.print(actions_panel)


# ============================================================================
# Legacy functions for backward compatibility
# ============================================================================

def show_map(
    grid: Dict[str, Any],
    entities: List[Dict[str, Any]],
    current_entity_uuid: Optional[str] = None,
    valid_positions: Optional[List[Tuple[int, int]]] = None,
    visibility: Optional[Dict[str, Any]] = None,
    movement_path: Optional[List[Tuple[int, int]]] = None,
    title: str = "Battlefield"
):
    """Display the map in a panel (legacy)."""
    map_text = render_map_content(grid, entities, current_entity_uuid, valid_positions, visibility, movement_path)
    console.print(Panel(map_text, title=title, box=box.ROUNDED))


def show_turn_info(turn: Dict[str, Any], entities: List[Dict[str, Any]], is_my_turn: Optional[bool] = None):
    """Display turn information (legacy)."""
    panel = render_turn_info_panel(turn, entities, is_my_turn or False)
    console.print(panel)


def show_combat_log(messages: List[str], max_lines: int = 5):
    """Display recent combat log messages (legacy)."""
    if not messages:
        return
    console.print("\n[bold]Combat Log:[/bold]")
    for msg in messages[-max_lines:]:
        console.print(f"  [dim]{msg}[/dim]")


def format_attack_roll(d20, all_d20_rolls, advantage_status, attack_bonus, attack_total, target_ac):
    """Format attack roll display with advantage/disadvantage info."""
    bonus_str = f"+{attack_bonus}" if attack_bonus >= 0 else str(attack_bonus)

    if advantage_status == "advantage" and len(all_d20_rolls) >= 2:
        rolls_display = f"d20([green]{all_d20_rolls[0]}[/green], [green]{all_d20_rolls[1]}[/green] → [bold green]{d20}[/bold green])"
        adv_text = "[bold green]ADV[/bold green] "
    elif advantage_status == "disadvantage" and len(all_d20_rolls) >= 2:
        rolls_display = f"d20([red]{all_d20_rolls[0]}[/red], [red]{all_d20_rolls[1]}[/red] → [bold red]{d20}[/bold red])"
        adv_text = "[bold red]DIS[/bold red] "
    else:
        rolls_display = f"d20([cyan]{d20}[/cyan])"
        adv_text = ""

    return f"  {adv_text}Attack Roll: {rolls_display} {bonus_str} = [bold]{attack_total}[/bold] vs AC [bold]{target_ac}[/bold]"


def _build_attack_log_entry(data: Dict[str, Any], attacker_default: str = "Someone", target_default: str = "Unknown") -> Dict[str, Any]:
    """Build a standardized attack log entry from server data.

    This helper ensures all attack log entries have the same structure,
    including breakdown fields for detailed display.
    """
    return {
        "type": "attack",
        "attacker": data.get("attacker", attacker_default),
        "target": data.get("target", target_default),
        "weapon": data.get("weapon", "weapon"),
        "d20": data.get("d20"),
        "all_d20_rolls": data.get("all_d20_rolls", []),
        "advantage_status": data.get("advantage_status", "none"),
        "attack_bonus": data.get("attack_bonus", 0),
        "attack_total": data.get("attack_total"),
        "target_ac": data.get("target_ac"),
        "outcome": data.get("outcome"),
        "total_damage": data.get("total_damage", 0),
        # Breakdown fields for detailed display
        "attack_breakdown": data.get("attack_breakdown", []),
        "ac_breakdown": data.get("ac_breakdown", []),
        "damage_breakdown": data.get("damage_breakdown", []),
        "damage_dice_str": data.get("damage_dice_str", ""),
        "damage_rolls": data.get("damage_rolls", []),
        # Opportunity attack flag
        "is_opportunity_attack": data.get("is_opportunity_attack", False),
    }


def show_opponent_action(entry: Dict[str, Any]):
    """Process a combat log entry from the server and add to our rich combat log."""
    entry_type = entry.get("type", "").lower()
    details = entry.get("details", {})

    # Convert server entry to our rich format
    if entry_type in ("attack", "opportunity_attack"):
        add_to_combat_log(_build_attack_log_entry(details, "Opponent", "Unknown"))
    elif entry_type in ("move", "movement"):
        add_to_combat_log({
            "type": "move",
            "entity": details.get("entity", "Opponent"),
            "from": details.get("from", [0, 0]),
            "to": details.get("to", [0, 0]),
        })
    elif entry_type == "death":
        add_to_combat_log({
            "type": "death",
            "entity": details.get("entity", "Someone"),
        })
    elif entry_type == "action":
        add_to_combat_log({
            "type": "action",
            "entity": details.get("entity", "Someone"),
            "action": details.get("action", "action"),
        })
    elif entry_type == "turn_end":
        add_to_combat_log({
            "type": "turn_end",
            "entity": details.get("entity", "Someone"),
        })


def show_action_result(result: Dict[str, Any], player_entity_name: str = "You"):
    """Process a player action result and add to rich combat log.

    Args:
        result: The action result from the server
        player_entity_name: The name of the player's entity (e.g., "Hero")
    """
    event_type = result.get("event_type", "")
    message = result.get("message", "")

    # Add to rich combat log based on event type
    # Note: event_type is template name like "attack_melee_main", not just "attack"
    if event_type.startswith("attack"):
        data = result.get("event_data", {})
        # Use attacker name from data, fallback to player_entity_name
        add_to_combat_log(_build_attack_log_entry(data, player_entity_name, "Unknown"))
    elif event_type in ("move", "movement"):
        data = result.get("event_data", {})
        # Use entity name from data if available
        entity_name = data.get("entity", player_entity_name)
        add_to_combat_log({
            "type": "move",
            "entity": entity_name,
            "from": data.get("start", [0, 0]),
            "to": data.get("end", [0, 0]),
        })
    elif event_type in ("dash", "dodge", "disengage"):
        add_to_combat_log({
            "type": "action",
            "entity": player_entity_name,
            "action": event_type,
        })
    elif message:
        add_to_combat_log({"type": "message", "message": message})

    # Show any triggered reactions (opportunity attacks against the player)
    triggered = result.get("triggered_reactions", [])
    for reaction in triggered:
        if reaction.get("type") == "opportunity_attack":
            reaction_data = dict(reaction)
            # Mark as opportunity attack and use player's actual name as target
            reaction_data["is_opportunity_attack"] = True
            reaction_data["target"] = player_entity_name
            add_to_combat_log(_build_attack_log_entry(reaction_data, "Enemy", player_entity_name))

    # Show deaths
    deaths = result.get("deaths", [])
    for name in deaths:
        add_to_combat_log({"type": "death", "entity": name})


def show_error(message: str):
    """Display an error message."""
    console.print(f"[red]Error: {message}[/red]")


def show_info(message: str):
    """Display an info message."""
    console.print(f"[cyan]{message}[/cyan]")


def show_available_actions(actions: Dict[str, Any], entities: List[Dict[str, Any]]):
    """Display available actions (legacy - now integrated into full screen)."""
    panel = render_available_actions_panel(actions, entities, {"actions_remaining": 1})
    console.print(panel)


def show_opportunity_attack(reaction: Dict[str, Any]):
    """Display an opportunity attack that was triggered."""
    attacker = reaction.get("attacker", "Unknown")
    outcome = (reaction.get("outcome") or "").lower()
    total_damage = reaction.get("total_damage", 0)

    console.print(f"\n[bold magenta]*** OPPORTUNITY ATTACK! ***[/bold magenta]")
    console.print(f"[red]{attacker}[/red] attacks you!")

    if outcome in ("hit", "crit"):
        console.print(f"  [green]HIT![/green] {total_damage} damage")
    else:
        console.print(f"  [dim]MISS[/dim]")


def show_ai_actions(actions: List[Dict[str, Any]]):
    """Display AI actions that occurred during AI turn."""
    if not actions:
        return

    for action in actions:
        action_type = action.get("type", "")
        if action_type == "attack":
            add_to_combat_log(_build_attack_log_entry(action, "AI", "you"))
        elif action_type == "move":
            add_to_combat_log({
                "type": "move",
                "entity": action.get("entity", "AI"),
                "from": action.get("from", [0, 0]),
                "to": action.get("to", [0, 0]),
            })


def prompt_command() -> str:
    """Prompt for a command."""
    console.print()
    return console.input("[bold yellow]>[/bold yellow] ").strip().lower()


def show_help():
    """Display help information."""
    help_text = """
[bold underline]Commands:[/bold underline]

[bold cyan]Movement:[/bold cyan]
  m X Y / move X Y    Move to position (X, Y)
  m / move            Show valid move positions on map

[bold cyan]Combat:[/bold cyan]
  a N / attack N      Attack target number N

[bold cyan]Actions:[/bold cyan]
  d / dash            Dash (double movement this turn)
  o / dodge           Dodge (attackers have disadvantage)
  i / disengage       Disengage (no opportunity attacks)

[bold cyan]Turn:[/bold cyan]
  e / end             End your turn

[bold cyan]History:[/bold cyan]
  pt / prev           Previous turn
  nt / next           Next turn
  ft / first          First turn
  ct / current        Return to current turn

[bold cyan]Info:[/bold cyan]
  ? / help            Show this help

[bold cyan]Game:[/bold cyan]
  q / quit            Exit the game
"""
    console.print(Panel(help_text, title="Help", box=box.ROUNDED))
