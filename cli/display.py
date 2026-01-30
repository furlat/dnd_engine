"""
Display module for full-screen TUI with Rich.
"""

from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
import sys
import shutil
import re

if TYPE_CHECKING:
    from cli.action_model import ShortcutRegistry, AvailableActionsState

from dnd.core.combat_log import CombatLogVerbosity


# Color mapping based on cost_type (derived from API data)
COST_TYPE_COLORS = {
    "bonus_actions": "bold cyan",
    "actions": "bold magenta",
    "reactions": "bold yellow",
    "movement": "bold green",
}
DEFAULT_ACTION_COLOR = "bold white"

# Combat log verbosity setting
COMBAT_LOG_VERBOSITY = CombatLogVerbosity.VERBOSE


def set_combat_log_verbosity(verbosity: CombatLogVerbosity):
    """Set the combat log verbosity level."""
    global COMBAT_LOG_VERBOSITY
    COMBAT_LOG_VERBOSITY = verbosity


def markdown_to_rich(text: str) -> str:
    """Convert markdown-like format to Rich markup.

    Supported formats:
    - {color:text} -> [color]text[/color]
    - **text** -> [bold]text[/bold]
    - *text* -> [italic]text[/italic]
    - ~~text~~ -> [strike]text[/strike]
    """
    # Color syntax: {color:text} -> [color]text[/color]
    text = re.sub(r'\{([^}:]+):([^}]+)\}', r'[\1]\2[/\1]', text)
    # Bold: **text** -> [bold]text[/bold]
    text = re.sub(r'\*\*([^*]+)\*\*', r'[bold]\1[/bold]', text)
    # Italic: *text* -> [italic]text[/italic]
    text = re.sub(r'\*([^*]+)\*', r'[italic]\1[/italic]', text)
    # Strikethrough: ~~text~~ -> [strike]text[/strike]
    text = re.sub(r'~~([^~]+)~~', r'[strike]\1[/strike]', text)
    return text


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
        # Prioritize alive entities over dead ones at the same position
        existing = entity_at.get(pos)
        if existing is None or (existing.get("is_dead") and not e.get("is_dead")):
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

    # Build icon mapping for ALL non-player entities (dynamic count)
    # First pass: count entities per starting letter
    letter_counts: Dict[str, int] = {}
    entity_icons: Dict[str, Tuple[str, int]] = {}  # uuid -> (letter, number)

    for e in entities:
        if e["uuid"] != current_entity_uuid:
            letter = e["name"][0].upper()
            letter_counts[letter] = letter_counts.get(letter, 0) + 1
            entity_icons[e["uuid"]] = (letter, letter_counts[letter])

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
                in_aoe = pos in valid_set
                if entity["uuid"] == current_entity_uuid:
                    char = "@"
                    # Yellow background if player is in AoE
                    style = "bold green on yellow" if in_aoe else "bold green"
                elif entity.get("is_dead"):
                    char, style = "%", "dim"
                else:
                    # Dynamic icon: number if multiple share letter, else letter
                    letter, num = entity_icons.get(entity["uuid"], (entity["name"][0].upper(), 1))
                    total_with_letter = letter_counts.get(letter, 1)
                    if total_with_letter > 1:
                        char = str(num)
                    else:
                        char = letter
                    # Yellow background if enemy is in AoE
                    style = "bold red on yellow" if in_aoe else "bold red"
            elif pos in path_set:
                char, style = "+", "bold magenta"
            elif pos in valid_set:
                char, style = "*", "bold yellow"
            elif tile is None:
                char, style = " ", ""
            elif not tile.get("walkable", True):
                # Distinguish water from walls
                tile_name = tile.get("name", "Wall")
                if tile_name == "Water":
                    char, style = "~", "bold blue"
                else:
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

    # Dynamic legend: player first
    result.append("@ ", style="bold green")
    result.append("You  ")

    # Build legend entries from entity_icons (grouped by display icon)
    icon_to_names: Dict[str, List[Tuple[str, bool]]] = {}  # icon -> [(name, is_dead), ...]
    for e in entities:
        if e["uuid"] != current_entity_uuid:
            letter, num = entity_icons.get(e["uuid"], (e["name"][0].upper(), 1))
            total_with_letter = letter_counts.get(letter, 1)
            icon = str(num) if total_with_letter > 1 else letter
            if icon not in icon_to_names:
                icon_to_names[icon] = []
            icon_to_names[icon].append((e["name"], e.get("is_dead", False)))

    # Show each icon -> name mapping
    for icon, name_dead_list in sorted(icon_to_names.items()):
        name, is_dead = name_dead_list[0]
        if is_dead:
            result.append("% ", style="dim")
            result.append(f"{name}  ", style="dim strike")
        else:
            result.append(f"{icon} ", style="bold red")
            result.append(f"{name}  ")

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
    # Sort entities by initiative order
    initiative_order = turn.get("initiative_order", [])
    if initiative_order:
        order_map = {c["uuid"]: i for i, c in enumerate(initiative_order)}
        entities = sorted(entities, key=lambda e: order_map.get(e["uuid"], 999))

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
            name = f"[dim strike]{name}[/dim strike]"
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

    # Join lines and parse as markup
    content = Text.from_markup("\n".join(_output_buffer))

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
            name = f"[dim strike]{name}[/dim strike]"
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
    """Render a single combat log entry with rich formatting.

    Uses the new verbosity-based markdown format from CombatLogEntry.
    Falls back to legacy type-based rendering for backward compatibility.
    """
    # Check for new verbosity-based format (has compact/verbose/detailed fields)
    if "compact" in entry:
        # New format: use verbosity setting to pick text level
        if COMBAT_LOG_VERBOSITY == CombatLogVerbosity.COMPACT:
            text = entry.get("compact", "")
        elif COMBAT_LOG_VERBOSITY == CombatLogVerbosity.VERBOSE:
            text = entry.get("verbose", entry.get("compact", ""))
        else:  # DETAILED
            text = entry.get("detailed", entry.get("verbose", entry.get("compact", "")))

        # Convert markdown to Rich markup and append
        rich_text = markdown_to_rich(text)
        content.append(Text.from_markup(rich_text))
        return

    # Legacy format: use type-based rendering
    entry_type = entry.get("type", "message")

    if entry_type == "attack":
        # New nested structure (AttackLogData)
        attacker = entry.get("attacker_name", "Someone")
        target = entry.get("target_name", "Unknown")
        weapon = entry.get("weapon_name", "weapon")

        # Extract from nested attack_roll
        attack_roll = entry.get("attack_roll", {})
        d20 = attack_roll.get("d20_used", 0)
        all_rolls = attack_roll.get("all_d20_rolls", [])
        if not all_rolls and d20:
            all_rolls = [d20]
        adv_status = attack_roll.get("advantage_status") or "none"
        attack_bonus = attack_roll.get("bonus", 0)
        attack_total = attack_roll.get("total", 0)

        target_ac = entry.get("target_ac", 0)
        outcome = (entry.get("outcome") or "").lower()
        total_damage = entry.get("total_damage", 0)

        # Breakdown data
        attack_breakdown = entry.get("attack_breakdown", [])
        ac_breakdown = entry.get("ac_breakdown", [])

        # Damage from damage_rolls list
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
        elif outcome == "crit miss" or outcome == "crit_miss":
            content.append("CRIT MISS", style="bold red")
        else:
            content.append("MISS", style="dim")

        # Damage line (only on hit/crit)
        if outcome in ["hit", "crit"] and total_damage > 0:
            content.append("\n")
            content.append("  Damage: ", style="dim")

            # Show damage from DamageRollDisplay structure
            if damage_rolls and len(damage_rolls) > 0:
                dr = damage_rolls[0]
                dice = dr.get("dice_results", [])
                bonus = dr.get("bonus", 0)
                roll_dice_str = dr.get("dice_str", "")
                roll_breakdown = dr.get("bonus_breakdown", [])

                if dice:
                    dice_str_display = ",".join(str(d) for d in dice)
                    content.append(f"{roll_dice_str}({dice_str_display})", style="red")
                elif roll_dice_str:
                    content.append(f"{roll_dice_str}", style="red")

                # Damage bonus with breakdown
                if bonus != 0:
                    content.append(f" {bonus:+d}")
                if roll_breakdown:
                    content.append(f" {_format_breakdown(roll_breakdown)}", style="dim")

                content.append(f" = {total_damage}", style="bold red")
            else:
                content.append(f"{total_damage}", style="bold red")

    elif entry_type == "move":
        # MovementLogData structure
        mover = entry.get("entity_name", "Someone")
        from_pos = entry.get("start_position", [0, 0])
        to_pos = entry.get("end_position", [0, 0])
        # Use action_verb if provided (e.g., "jumped", "moved")
        action_verb = entry.get("action_verb", "moved")
        content.append(f"{mover}", style="bold cyan")
        content.append(f" {action_verb} ")
        content.append(f"({from_pos[0]},{from_pos[1]})→({to_pos[0]},{to_pos[1]})", style="green")

    elif entry_type == "death":
        entity = entry.get("entity", "Someone")
        content.append(f"☠ {entity} defeated!", style="bold red")

    elif entry_type == "action":
        # SelfActionLogData structure
        entity = entry.get("entity_name", "Someone")
        action_name = entry.get("action_name", "action")
        content.append(f"{entity}", style="bold cyan")
        content.append(f" uses ", style="dim")
        content.append(f"{action_name.title()}", style="bold magenta")

    elif entry_type == "entity_action":
        # Entity-targeting action (Shove, Grapple, etc.) - full details
        summary = entry.get("summary", "Action")
        detail_lines = entry.get("detail_lines", [])
        success = entry.get("success")

        # Header line - use summary which contains the outcome
        content.append(f"{summary}", style="bold yellow")

        # Success/failure indicator
        if success is True:
            content.append(" ✓", style="green")
        elif success is False:
            content.append(" ✗", style="red")

        # Detail lines (contest roll, etc.)
        for line in detail_lines:
            content.append("\n")
            content.append(f"  {line}", style="dim")

    elif entry_type == "turn_start":
        entity = entry.get("entity_name", entry.get("entity", "Someone"))
        content.append(f"─── {entity}'s turn ───", style="bold yellow")

    elif entry_type == "turn_end":
        entity = entry.get("entity_name", entry.get("entity", "Someone"))
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
    turn: Dict[str, Any],
    registry: Optional["ShortcutRegistry"] = None
) -> Panel:
    """Render available actions as a compact panel with economy in title.

    Args:
        actions: Raw actions dict from server
        entities: List of entities for name lookup
        turn: Turn info for economy display
        registry: Session-stable shortcut registry for self_actions
    """
    content = Text()
    entity_lookup = {e["uuid"]: e for e in entities}

    actions_remaining = turn.get("actions_remaining", 0)
    bonus_remaining = turn.get("bonus_actions_remaining", 0)
    movement_remaining = actions.get("remaining_movement", 0)
    reactions_remaining = turn.get("reactions_remaining", 0)

    # Position-based actions (Move, Jump, etc.) - iterate ALL position_actions
    # Filter out spells (is_spell=True) - those go in SPELLS section
    position_actions = actions.get("position_actions", [])
    movement_actions = [a for a in position_actions if not a.get("is_spell", False)]

    for action in movement_actions:
        template_name = action.get("template_name", "Unknown")
        display_name = action.get("display_name", template_name)
        can_afford = action.get("can_afford", False)
        valid_targets = action.get("valid_targets", [])
        cost_type = action.get("cost_type", "movement")

        if not valid_targets or not can_afford:
            continue  # Skip unavailable actions

        # Get shortcut from registry (session-stable)
        if registry:
            cmd = registry.get_or_create_shortcut(template_name)
        else:
            cmd = template_name[0].lower()

        # Cost label based on cost_type
        if cost_type == "movement":
            cost_info = f"{movement_remaining}ft"
            style = "bold cyan"
        elif cost_type == "bonus_actions":
            cost_info = "bonus"
            style = "bold magenta"
        elif cost_type == "actions":
            cost_info = "action"
            style = "bold yellow"
        else:
            cost_info = cost_type
            style = "bold white"

        content.append(display_name.upper(), style=style)
        content.append(f" ({cost_info}, {len(valid_targets)} pos)  ")
        content.append(f"[{cmd} X Y] or [{cmd}] to show\n", style="dim")

    # Collect all spells from all sources (entity_actions, position_actions, self_actions)
    all_entity_actions = actions.get("entity_actions", [])
    all_self_actions = actions.get("self_actions", [])

    # Filter spells from all sources
    spell_actions_from_entity = [a for a in all_entity_actions if a.get("is_spell", False)]
    spell_actions_from_position = [a for a in position_actions if a.get("is_spell", False)]
    spell_actions_from_self = [a for a in all_self_actions if a.get("is_spell", False)]
    all_spell_actions = spell_actions_from_entity + spell_actions_from_position + spell_actions_from_self
    valid_spells = [a for a in all_spell_actions if a.get("valid_targets") and a.get("can_afford")]

    def is_attack_action(action: Dict[str, Any]) -> bool:
        """Check if action is an attack using explicit is_attack field.

        Attack actions target entities and deal damage.
        Examples: Attack, Extra Attack, Frenzied Strike.
        NOT included: "Reckless Attack" (self-buff that enables advantage).
        """
        return action.get("is_attack", False)

    # Non-spell entity actions
    non_spell_entity_actions = [a for a in all_entity_actions if not a.get("is_spell", False)]
    attacks = [a for a in non_spell_entity_actions if is_attack_action(a)]
    other_entity_actions = [a for a in non_spell_entity_actions if not is_attack_action(a)]

    valid_attacks = [a for a in attacks if a.get("valid_targets") and a.get("can_afford")]
    valid_other_entity = [a for a in other_entity_actions if a.get("valid_targets") and a.get("can_afford")]

    # Other entity-targeting actions (Shove, etc.) - show before attacks
    if valid_other_entity:
        content.append("ACTIONS:", style="bold yellow")
        content.append("\n", style="dim")
        for act in valid_other_entity:
            template_name = act.get("template_name", "Unknown")
            display_name = act.get("display_name", template_name)
            targets = act.get("valid_targets", [])
            cost_type = act.get("cost_type", "actions")

            # Get shortcut from registry
            if registry:
                cmd = registry.get_or_create_shortcut(template_name)
            else:
                cmd = template_name[0].lower()

            # Cost label with color
            if cost_type == "bonus_actions":
                cost_label = ("BONUS", "magenta")
            else:
                cost_label = ("ACTION", "cyan")

            # Show each target with index
            target_num = 1
            for target in targets:
                target_uuid = target.get("target_uuid")
                target_name = target.get("target_name") or entity_lookup.get(target_uuid, {}).get("name", "?")

                content.append(f"  [", style="dim")
                content.append(f"{cmd} {target_num}", style="bold yellow")
                content.append(f"] ", style="dim")
                content.append(f"{cost_label[0]} ", style=cost_label[1])
                content.append(f"{display_name}", style="bold")
                content.append(f" -> {target_name}\n", style="dim")
                target_num += 1

    # Attacks - show all available attack options with target numbers
    if valid_attacks:
        content.append("ATTACKS:", style="bold red")
        content.append("  [a N] to attack\n", style="dim")
        target_num = 1
        for atk in valid_attacks:
            targets = atk.get("valid_targets", [])
            cost_type = atk.get("cost_type", "actions")
            cost_amount = atk.get("cost_amount", 1)

            # Cost label with color - handle Extra Attack (cost_amount=0)
            if cost_amount == 0:
                cost_label = ("EXTRA", "green")  # Free extra attack
            elif cost_type == "bonus_actions":
                cost_label = ("BONUS", "magenta")
            else:
                cost_label = ("ACTION", "cyan")

            # Get weapon/action display name
            action_name = atk.get("weapon_name") or atk.get("display_name", "Attack")

            for target in targets:
                target_uuid = target.get("target_uuid")
                target_name = target.get("target_name") or entity_lookup.get(target_uuid, {}).get("name", "?")

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

    # SPELLS section - show all spells grouped by target type
    if valid_spells:
        content.append("SPELLS:", style="bold blue")
        content.append("\n", style="dim")

        for spell in valid_spells:
            template_name = spell.get("template_name", "Unknown")
            display_name = spell.get("display_name", template_name)
            target_type = spell.get("target_type", "self")
            targets = spell.get("valid_targets", [])
            cost_type = spell.get("cost_type", "actions")

            # Get shortcut from registry
            if registry:
                cmd = registry.get_or_create_shortcut(template_name)
            else:
                cmd = template_name[:2].lower()

            # Cost label with color
            if cost_type == "bonus_actions":
                cost_label = ("BONUS", "magenta")
            else:
                cost_label = ("ACTION", "cyan")

            # Position-based spells (AoE, LOS)
            if target_type in ("position_aoe", "position_los"):
                # Show as position action with preview option
                content.append(f"  [", style="dim")
                content.append(f"{cmd}", style="bold blue")
                content.append(f"] ", style="dim")
                content.append(f"{cost_label[0]} ", style=cost_label[1])
                content.append(f"{display_name}", style="bold")
                content.append(f" ({len(targets)} pos) [{cmd} X Y] or [{cmd} ? X Y] preview\n", style="dim")

            # Entity-targeting spells (single or multi)
            elif target_type in ("entity", "multi_entity"):
                for i, target in enumerate(targets):
                    target_name = target.get("target_name") or entity_lookup.get(target.get("target_uuid"), {}).get("name", "?")
                    content.append(f"  [", style="dim")
                    content.append(f"{cmd} {i+1}", style="bold blue")
                    content.append(f"] ", style="dim")
                    content.append(f"{cost_label[0]} ", style=cost_label[1])
                    content.append(f"{display_name}", style="bold")
                    content.append(f" -> {target_name}\n", style="dim")

            # Self-targeting spells
            else:
                content.append(f"  [", style="dim")
                content.append(f"{cmd}", style="bold blue")
                content.append(f"] ", style="dim")
                content.append(f"{cost_label[0]} ", style=cost_label[1])
                content.append(f"{display_name}", style="bold")
                content.append(f" (self)\n", style="dim")

    # Self-actions - fully dynamic using registry (filter out spells)
    other = [a for a in all_self_actions if not a.get("is_spell", False)]
    other_items = []

    for act in other:
        if act.get("can_afford"):
            template_name = act.get("template_name", "")
            display_name = act.get("display_name", template_name).upper()
            cost_type = act.get("cost_type", "actions")

            # Get session-stable shortcut from registry
            if registry:
                shortcut = registry.get_or_create_shortcut(template_name)
            else:
                # Fallback: derive shortcut from template_name
                words = template_name.split()
                if len(words) > 1:
                    shortcut = "".join(w[0].lower() for w in words)
                else:
                    shortcut = template_name[0].lower() if template_name else "?"

            # Color based on cost_type
            color = COST_TYPE_COLORS.get(cost_type, DEFAULT_ACTION_COLOR)

            other_items.append((display_name, color, f"[{shortcut}]"))

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
    content.append("LIST", style="bold white")
    content.append(" [la]  ", style="dim")
    content.append("LOG", style="bold white")
    content.append(" [log]  ", style="dim")
    content.append("HELP", style="bold white")
    content.append(" [?]  ", style="dim")
    content.append("QUIT", style="bold white")
    content.append(" [q]", style="dim")

    # Build title with action economy
    title = f"Actions:{actions_remaining} Bonus:{bonus_remaining} Move:{movement_remaining}ft React:{reactions_remaining}"

    return Panel(content, title=title, box=box.ROUNDED, border_style="green")


def render_all_actions(
    registry: "ShortcutRegistry",
    current_actions: Optional["AvailableActionsState"] = None
) -> Panel:
    """Show all actions encountered this session with availability status.

    Args:
        registry: Session shortcut registry with all known actions
        current_actions: Current available actions state for availability check

    Returns:
        Panel with list of all actions and their shortcuts
    """
    content = Text()
    content.append("All Actions (this session):\n\n", style="bold")

    all_actions = registry.get_all_actions()  # template_name -> shortcut

    if not all_actions:
        content.append("  No actions registered yet.", style="dim")
    else:
        for template_name, shortcut in sorted(all_actions.items(), key=lambda x: x[1]):
            # Check if currently available (self_actions or position actions)
            action = None
            action_type = ""
            if current_actions:
                # Check self_actions first
                action = current_actions.get_self_action(template_name)
                if action:
                    action_type = "self"
                else:
                    # Check position actions (movement)
                    for pos_action in current_actions.movement:
                        if pos_action.template_name == template_name:
                            action = pos_action
                            action_type = "position"
                            break

            available = action is not None and action.can_afford

            if available:
                # Color based on action type
                style = "bold cyan" if action_type == "position" else "bold green"
                content.append(f"  [{shortcut}] ", style=style)
                content.append(f"{template_name}", style="bold")
                if action_type == "position":
                    content.append(" - AVAILABLE (position)\n", style="cyan")
                else:
                    content.append(" - AVAILABLE\n", style="green")
            else:
                content.append(f"  [{shortcut}] ", style="dim")
                content.append(f"{template_name}", style="dim")
                content.append(" - unavailable\n", style="dim")

    return Panel(content, title="Actions List", box=box.ROUNDED, border_style="blue")


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
    is_my_turn: bool = True,
    shortcut_registry: Optional["ShortcutRegistry"] = None
):
    """Render the full screen layout.

    Args:
        grid: Map grid data
        entities: List of entity data
        turn: Turn state info
        current_entity_uuid: UUID of current player's entity
        actions: Raw actions dict from server
        visibility: Visibility data
        movement_path: Path to highlight on map
        valid_positions: Valid move positions to highlight
        is_my_turn: Whether it's the player's turn
        shortcut_registry: Session-stable shortcut registry for actions
    """
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
        actions_panel = render_available_actions_panel(actions, entities, turn, shortcut_registry)

    # Print all panels in order (with top padding to avoid cutoff)
    console.print()  # Top margin
    console.print(header_panel)
    console.print(map_panel)
    console.print(combatants_panel)
    console.print(log_panel)
    if actions_panel:
        console.print(actions_panel)
    if output_panel:
        console.print(output_panel)


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

    Uses the new AttackLogData structure exclusively.
    """
    # Extract from nested attack_roll
    attack_roll = data.get("attack_roll", {})

    # Get attacker/target/weapon from new field names
    attacker = data.get("attacker_name", attacker_default)
    target = data.get("target_name", target_default)
    weapon = data.get("weapon_name", "weapon")

    # Extract attack roll values from nested structure
    d20 = attack_roll.get("d20_used", 0)
    all_rolls = attack_roll.get("all_d20_rolls", [])
    if not all_rolls and d20:
        all_rolls = [d20]
    adv_status = attack_roll.get("advantage_status") or "none"
    attack_bonus = attack_roll.get("bonus", 0)
    attack_total = attack_roll.get("total", 0)

    return {
        "type": "attack",
        "attacker_name": attacker,
        "target_name": target,
        "weapon_name": weapon,
        "attack_roll": {
            "d20_used": d20,
            "all_d20_rolls": all_rolls,
            "advantage_status": adv_status,
            "bonus": attack_bonus,
            "total": attack_total,
        },
        "target_ac": data.get("target_ac", 0),
        "outcome": data.get("outcome", ""),
        "total_damage": data.get("total_damage", 0),
        "attack_breakdown": data.get("attack_breakdown", []),
        "ac_breakdown": data.get("ac_breakdown", []),
        "damage_rolls": data.get("damage_rolls", []),
        "is_opportunity_attack": data.get("is_opportunity_attack", False),
    }


def display_combat_log_entry(entry: Dict[str, Any]):
    """Display any CombatLogEntry from server.

    New format entries have compact/verbose/detailed fields and are passed through
    directly for rendering. Legacy entries without these fields are handled via
    type-specific conversion.

    Args:
        entry: A CombatLogEntry.to_dict() from the server
    """
    # Check for new verbosity-based format (has compact/verbose/detailed fields)
    if "compact" in entry and entry.get("compact"):
        # New format: pass through directly for _render_log_entry
        add_to_combat_log(entry)
        return

    # Legacy format: convert based on entry_type
    entry_type = entry.get("entry_type", "").lower()
    data = entry.get("data", {})

    if entry_type in ("attack", "opportunity_attack"):
        log_entry = _build_attack_log_entry(data, "Someone", "Unknown")
        if entry_type == "opportunity_attack":
            log_entry["is_opportunity_attack"] = True
        add_to_combat_log(log_entry)
    elif entry_type == "movement":
        # Extract action verb from compact (e.g., "Hero jumps 15ft..." -> "jumped")
        compact = entry.get("compact", "")
        action_verb = "moved"  # Default
        if " jumps " in compact.lower() or "{yellow:jumps}" in compact.lower():
            action_verb = "jumped"
        add_to_combat_log({
            "type": "move",
            "entity_name": data.get("entity_name", "Someone"),
            "start_position": data.get("start_position", [0, 0]),
            "end_position": data.get("end_position", [0, 0]),
            "action_verb": action_verb,
        })
    elif entry_type == "death":
        add_to_combat_log({
            "type": "death",
            "entity": data.get("entity_name", "Someone"),
        })
    elif entry_type == "action":
        # Check if self-action (has action_name) or entity-targeting (has target)
        if data.get("action_name"):
            # Self-action (Dash, Dodge, etc.)
            add_to_combat_log({
                "type": "action",
                "entity_name": data.get("entity_name", "Someone"),
                "action_name": data.get("action_name", "action"),
            })
        else:
            # Entity-targeting action (Shove, etc.) - pass through full entry
            add_to_combat_log({
                "type": "entity_action",
                "source_name": entry.get("source_name", "Someone"),
                "target_name": entry.get("target_name", "Unknown"),
                "summary": entry.get("compact", entry.get("summary", "")),
                "detail_lines": [],
                "data": data,
                "success": entry.get("success"),
            })
    elif entry_type == "turn_start":
        add_to_combat_log({
            "type": "turn_start",
            "entity_name": data.get("entity_name", "Someone"),
        })
    elif entry_type == "turn_end":
        add_to_combat_log({
            "type": "turn_end",
            "entity_name": data.get("entity_name", "Someone"),
        })
    else:
        # Unknown entry type - pass through full entry data
        compact = entry.get("compact", "")
        if compact:
            add_to_combat_log({
                "type": "entity_action",
                "source_name": entry.get("source_name", "Someone"),
                "target_name": entry.get("target_name"),
                "summary": compact,
                "detail_lines": [],
                "data": data,
                "success": entry.get("success"),
            })


def show_opponent_action(entry: Dict[str, Any]):
    """Process a combat log entry from the server and add to our rich combat log.

    Uses CombatLogEntry structure: entry_type, data dict, summary.
    Delegates to unified display_combat_log_entry().
    """
    display_combat_log_entry(entry)


def show_action_result(result: Dict[str, Any], player_entity_name: str = "You"):
    """Process a player action result and add to rich combat log.

    Uses combat_log_entries as the ONLY source of truth.

    Args:
        result: The action result from the server (must contain combat_log_entries)
        player_entity_name: Unused, kept for API compatibility
    """
    # Suppress unused parameter warning
    _ = player_entity_name

    # combat_log_entries is the ONLY source of truth
    entries = result.get("combat_log_entries", [])
    for entry in entries:
        display_combat_log_entry(entry)


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
    """Display AI actions that occurred during AI turn.

    Uses CombatLogEntry structure. Delegates to unified display_combat_log_entry().
    """
    if not actions:
        return

    for action in actions:
        display_combat_log_entry(action)


def prompt_command() -> str:
    """Prompt for a command."""
    console.print()
    return console.input("[bold yellow]>[/bold yellow] ").strip().lower()


def show_help():
    """Display help information."""
    help_text = """
[bold underline]Commands:[/bold underline]

[bold cyan]Position Actions:[/bold cyan]
  m X Y / move X Y    Move to position (X, Y)
  j X Y / jump X Y    Jump to position (X, Y)
  <cmd>               Show valid positions on map (e.g., 'm' or 'j')

[bold cyan]Combat:[/bold cyan]
  a N / attack N      Attack target number N

[bold cyan]Spells:[/bold cyan]
  fb X Y              Cast Fireball at position (X, Y)
  fb ? X Y            Preview Fireball targets at (X, Y)
  fb                  Show valid Fireball positions on map
  fib N               Cast Fire Bolt at target N
  mm N                Cast Magic Missile at target N
  ma                  Cast Mage Armor (self)

[bold cyan]Actions:[/bold cyan]
  Use shortcuts shown in brackets, e.g. [d] for Dash
  New actions get shortcuts automatically (initials for multi-word)

[bold cyan]Turn:[/bold cyan]
  e / end             End your turn

[bold cyan]Info:[/bold cyan]
  la / list           List all actions with shortcuts
  ? / help            Show this help

[bold cyan]History:[/bold cyan]
  pt / prev           Previous turn
  nt / next           Next turn
  ft / first          First turn
  ct / current        Return to current turn

[bold cyan]Display:[/bold cyan]
  log / v             Show/set log verbosity
  log c               Compact (one-line)
  log v               Verbose (default)
  log d               Detailed (full breakdowns)

[bold cyan]Game:[/bold cyan]
  q / quit            Exit the game
"""
    console.print(Panel(help_text, title="Help", box=box.ROUNDED))
