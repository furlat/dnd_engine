"""
Display module for full-screen TUI with Rich.
"""

from typing import Dict, Any, List, Optional, Tuple, Set, TYPE_CHECKING
from collections import defaultdict
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

# Handler shortcut registry — maps shortcut -> handler name and vice versa
# Populated dynamically from handler_details each render
_handler_shortcut_to_name: dict[str, str] = {}
_handler_name_to_shortcut: dict[str, str] = {}

def _generate_handler_shortcut(name: str) -> str:
    """Generate a shortcut from handler name using initials (same logic as actions)."""
    words = name.split()
    if len(words) > 1:
        return "".join(w[0].lower() for w in words)
    return name[:2].lower() if len(name) > 1 else name.lower()

def build_handler_shortcuts(handler_details: list[dict]) -> None:
    """Build shortcut mappings from handler_details list. Handles collisions."""
    _handler_shortcut_to_name.clear()
    _handler_name_to_shortcut.clear()
    for h in handler_details:
        name = h.get("name", "")
        shortcut = _generate_handler_shortcut(name)
        # Handle collision by appending numbers
        base = shortcut
        i = 2
        while shortcut in _handler_shortcut_to_name:
            shortcut = f"{base}{i}"
            i += 1
        _handler_shortcut_to_name[shortcut] = name
        _handler_name_to_shortcut[name.lower()] = shortcut

def resolve_handler_name(user_input: str) -> str:
    """Resolve a handler shortcut to full name. Returns input as-is if not a shortcut."""
    return _handler_shortcut_to_name.get(user_input.lower(), user_input)

def get_handler_shortcut(name: str) -> str:
    """Get the shortcut for a handler name."""
    return _handler_name_to_shortcut.get(name.lower(), name.lower())

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
    # Note: [^{}:] excludes { from color names to prevent {{color:text} producing [{color]
    text = re.sub(r'\{([^{}:]+):([^}]+)\}', r'[\1]\2[/\1]', text)
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
MAX_COMBAT_LOG = 5  # Max entries to show

# Output buffer for command feedback (valid positions, attack options, etc.)
_output_buffer: List[str] = []
MAX_OUTPUT_LINES = 6

# Claude thinking text (shared file bridge from orchestrator)
_thinking_text: str = ""

# Session/connection info for header
_session_info: Dict[str, Any] = {
    "hero_connected": False,
    "claude_connected": False,
    "session_id": None,
    "pvp_mode": False,
    "spectator_mode": False,
}

# Turn history for replay
_turn_history: List[Dict[str, Any]] = []  # List of cached states
_history_index: Optional[int] = None  # None = viewing current, int = viewing history

# FOV mode state
_fov_mode: str = "self"       # "global", "self", "entity"
_fov_entity_index: int = 0    # For "entity" mode - matches legend numbering

# FOW (Fog of War) mode — temporal combat log filtering for human play
_fow_enabled: bool = False    # Off by default; toggle with `fow on/off`
_fow_visible_entity_uuids: Set[str] = set()  # Populated by main.py on state refresh
_fow_controlled_uuids: List[str] = []  # Populated by main.py on state refresh

# Tile memory: positions ever seen, keyed by entity UUID
_seen_tiles: Dict[str, Set[Tuple[int, int]]] = defaultdict(set)

# Light level background color map (LightLevel enum values)
LIGHT_LEVEL_BG = {
    0: "on grey7",       # MAGICAL_DARKNESS
    1: "on grey15",      # DARKNESS
    2: "on grey23",      # DIM_LIGHT
    3: "on color(58)",   # BRIGHT_LIGHT (subtle dark yellow/olive)
    4: "on color(100)",  # VERY_BRIGHT (brighter warm)
}

# Fog of war background for memory tiles (seen but not currently visible)
FOG_BG = "on grey11"


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
    pvp_mode: Optional[bool] = None,
    spectator_mode: Optional[bool] = None
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
    if spectator_mode is not None:
        _session_info["spectator_mode"] = spectator_mode


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


# ============================================================================
# FOV Mode API
# ============================================================================

def get_fov_mode() -> str:
    """Get current FOV mode as display string."""
    if _fov_mode == "entity":
        return f"entity #{_fov_entity_index}"
    return _fov_mode


def set_fov_mode(mode: str, entity_index: int = 0):
    """Set FOV mode. Modes: 'global', 'self', 'entity'."""
    global _fov_mode, _fov_entity_index
    _fov_mode = mode
    _fov_entity_index = entity_index


def get_fow_enabled() -> bool:
    """Get whether FOW (temporal combat log filtering) is enabled."""
    return _fow_enabled


def set_fow_enabled(enabled: bool):
    """Set FOW mode on/off."""
    global _fow_enabled
    _fow_enabled = enabled


def set_fow_visibility(visible_entity_uuids: Set[str], controlled_uuids: List[str]):
    """Update the FOW visibility context (called by main.py on state refresh)."""
    global _fow_visible_entity_uuids, _fow_controlled_uuids
    _fow_visible_entity_uuids = visible_entity_uuids
    _fow_controlled_uuids = controlled_uuids


def update_seen_tiles(entity_uuid: str, visible_cells: Set[Tuple[int, int]]):
    """Accumulate visible cells into seen set for an entity."""
    _seen_tiles[entity_uuid].update(visible_cells)


def get_seen_tiles(entity_uuid: str) -> Set[Tuple[int, int]]:
    """Get all tiles ever seen by an entity."""
    return _seen_tiles[entity_uuid]


def reset_seen_tiles():
    """Reset seen tiles (on new game)."""
    _seen_tiles.clear()


def get_terminal_size() -> Tuple[int, int]:
    """Get terminal width and height."""
    size = shutil.get_terminal_size((80, 24))
    return size.columns, size.lines


ITEM_DEFAULT_CHAR = "\u03c6"      # phi fallback for items without map_char
GREEK_AUTO_POOL = "\u03b1\u03b2\u03b3\u03b5\u03b6\u03b7\u03b9\u03ba\u03bc\u03bd\u03be\u03bf\u03c1\u03c4\u03c5\u03c7\u03c8\u03c9"  # αβγεζηικμνξορτυχψω


def _resolve_entity_uuid_by_index(
    index: int,
    entities: List[Dict[str, Any]],
    current_entity_uuid: Optional[str]
) -> Optional[str]:
    """Resolve a legend number to entity UUID.

    Legend numbering matches entity_icons: non-player entities ordered by appearance,
    numbered per starting letter when there are collisions.
    """
    count = 0
    for e in entities:
        if e["uuid"] != current_entity_uuid:
            count += 1
            if count == index:
                return e["uuid"]
    return None


def _get_terrain_char(tile: Dict[str, Any]) -> Tuple[str, str]:
    """Get the character and base style for terrain rendering (memory/fog mode).

    Returns (char, style) for the tile's terrain type only — no entity/object overlay.
    Uses FOG_BG background to make memory tiles visually distinct from visible tiles.
    """
    if not tile.get("walkable", True):
        tile_name = tile.get("name", "Wall")
        if tile_name == "Water":
            return "~", f"blue dim {FOG_BG}"
        return "#", f"dim {FOG_BG}"

    tile_name = tile.get("name", "Floor")
    is_hazardous = tile.get("is_hazardous", False)
    walking_cost = tile.get("walking_cost", 1)

    if is_hazardous or tile_name == "Spikes":
        return "^", f"red dim {FOG_BG}"
    elif walking_cost > 1 or tile_name == "Difficult Terrain":
        return ",", f"yellow dim {FOG_BG}"
    else:
        return ".", f"dim {FOG_BG}"


def render_map_content(
    grid: Dict[str, Any],
    entities: List[Dict[str, Any]],
    current_entity_uuid: Optional[str] = None,
    valid_positions: Optional[List[Tuple[int, int]]] = None,
    visibility: Optional[Dict[str, Any]] = None,
    movement_path: Optional[List[Tuple[int, int]]] = None,
    floor_objects: Optional[List[Dict[str, Any]]] = None
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

    # Build floor object position lookup
    object_at: Dict[Tuple[int, int], Dict[str, Any]] = {}
    if floor_objects:
        for obj in floor_objects:
            pos = tuple(obj["position"])
            if pos not in object_at:  # First object wins
                object_at[pos] = obj

    # Build item_char_map: item_name -> display_char (auto-assign unique Greek letters for default φ items)
    item_char_map: Dict[str, str] = {}
    _greek_idx = 0
    for obj in (floor_objects or []):
        obj_name = obj.get("name", "Item")
        if obj_name in item_char_map:
            continue
        char = obj.get("map_char", ITEM_DEFAULT_CHAR)
        if char != ITEM_DEFAULT_CHAR:
            item_char_map[obj_name] = char
        else:
            item_char_map[obj_name] = GREEK_AUTO_POOL[_greek_idx % len(GREEK_AUTO_POOL)]
            _greek_idx += 1

    valid_set = set(tuple(p) for p in valid_positions) if valid_positions else set()
    path_set = set(tuple(p) for p in movement_path) if movement_path else set()

    # Build per-entity visible cell sets from visibility data
    per_entity_visible: Dict[str, Set[Tuple[int, int]]] = {}
    hero_visible: Set[Tuple[int, int]] = set()
    enemy_visible: Set[Tuple[int, int]] = set()
    if visibility:
        for uuid, data in visibility.items():
            cells = set(tuple(c) for c in data.get("visible_cells", []))
            seen = set(tuple(c) for c in data.get("seen_cells", []))
            per_entity_visible[uuid] = cells
            # Use engine's senses.seen (includes intermediate movement steps)
            update_seen_tiles(uuid, seen)
            if uuid == current_entity_uuid:
                hero_visible = cells
            else:
                enemy_visible.update(cells)

    # Compute FOV-mode visible/seen sets
    fov_visible: Optional[Set[Tuple[int, int]]] = None   # Currently visible (None = show all)
    fov_seen: Optional[Set[Tuple[int, int]]] = None       # Ever seen (None = show all)

    # Set of entity UUIDs visible to the FOV observer (None = show all)
    fov_visible_entities: Optional[Set[str]] = None

    # Entity rendered as @ (the observer in current FOV mode)
    at_entity_uuid: Optional[str] = current_entity_uuid  # Default: player

    if _fov_mode == "self" and current_entity_uuid:
        fov_visible = hero_visible
        fov_seen = get_seen_tiles(current_entity_uuid)
        if visibility:
            vis_data = visibility.get(current_entity_uuid, {})
            fov_visible_entities = set(vis_data.get("visible_entities", []))
    elif _fov_mode == "entity":
        # Find entity by legend index
        target_uuid = _resolve_entity_uuid_by_index(_fov_entity_index, entities, current_entity_uuid)
        if target_uuid:
            at_entity_uuid = target_uuid  # FOV entity is the observer → rendered as @
            fov_visible = per_entity_visible.get(target_uuid, set())
            fov_seen = get_seen_tiles(target_uuid)
            if visibility:
                vis_data = visibility.get(target_uuid, {})
                fov_visible_entities = set(vis_data.get("visible_entities", []))
        else:
            # Fallback to global if invalid index
            fov_visible = None
            fov_seen = None
    # _fov_mode == "global": fov_visible/fov_seen/fov_visible_entities stay None (show everything)

    # Build icon mapping for all entities except the @ observer
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

    for y in range(min_y, max_y + 1):
        result.append(f"{y:2}|")
        for x in range(min_x, max_x + 1):
            pos = (x, y)
            tile = tiles.get(pos)

            # FOV filtering: check if position is visible or remembered
            if fov_visible is not None:
                # FOV mode active — apply fog of war
                if pos not in (fov_seen or set()):
                    # Never seen: dark void (very dark background so it doesn't
                    # look like bright light on light terminals)
                    result.append("  ", style="on grey3")
                    continue
                elif pos not in fov_visible:
                    # Seen before but not currently visible: show terrain only (memory)
                    if tile is not None:
                        char, style = _get_terrain_char(tile)
                    else:
                        char, style = " ", ""
                    result.append(" ")
                    result.append(char, style=style)
                    continue
                # else: currently visible — fall through to full rendering

            entity = entity_at.get(pos)
            # In FOV mode, only show entities visible to the FOV observer
            # The @ entity (observer) always renders; others must be in visible list
            if entity and fov_visible_entities is not None:
                if entity["uuid"] != at_entity_uuid and entity["uuid"] not in fov_visible_entities:
                    if not entity.get("is_dead"):
                        entity = None  # Not visible to FOV entity
                    # Dead entities (bodies) still render at visible positions

            # Subjective lighting: in FOV mode, if tile is visible but raw light
            # is DARKNESS, observer sees it via darkvision/adjacent rule → render as DIM
            raw_light = tile.get("light_level", 3) if tile else 3
            if fov_visible is not None and raw_light <= 1:
                raw_light = 2  # DIM_LIGHT — observer can see it, so at least dim
            light_bg = LIGHT_LEVEL_BG.get(raw_light, "")

            if entity:
                in_aoe = pos in valid_set
                if entity["uuid"] == at_entity_uuid:
                    char = "@"
                    # Yellow background if observer is in AoE
                    style = "bold green on yellow" if in_aoe else f"bold green {light_bg}".strip()
                elif entity.get("is_dead"):
                    char, style = "%", f"dim {light_bg}".strip()
                else:
                    # Dynamic icon: number if multiple share letter, else letter
                    letter, num = entity_icons.get(entity["uuid"], (entity["name"][0].upper(), 1))
                    total_with_letter = letter_counts.get(letter, 1)
                    if total_with_letter > 1:
                        char = str(num)
                    else:
                        char = letter
                    # Yellow background if enemy is in AoE
                    style = "bold red on yellow" if in_aoe else f"bold red {light_bg}".strip()
            elif pos in object_at:
                obj = object_at[pos]
                obj_name: str = obj.get("name", "Item")
                if obj_name in item_char_map:
                    char = item_char_map[obj_name]
                else:
                    char = ITEM_DEFAULT_CHAR
                style = f"bold cyan {light_bg}".strip()
            elif pos in path_set:
                char, style = "+", f"bold magenta {light_bg}".strip()
            elif pos in valid_set:
                char, style = "*", f"bold yellow {light_bg}".strip()
            elif tile is None:
                char, style = " ", ""
            elif not tile.get("walkable", True):
                # Distinguish water from walls
                tile_name = tile.get("name", "Wall")
                if tile_name == "Water":
                    char, style = "~", f"bold blue {light_bg}".strip()
                else:
                    char, style = "#", f"white {light_bg}".strip()
            else:
                # Walkable tile - check for terrain types
                tile_name = tile.get("name", "Floor")
                is_hazardous = tile.get("is_hazardous", False)
                walking_cost = tile.get("walking_cost", 1)

                if is_hazardous or tile_name == "Spikes":
                    char, style = "^", f"bold red {light_bg}".strip()
                elif walking_cost > 1 or tile_name == "Difficult Terrain":
                    char, style = ",", f"yellow {light_bg}".strip()
                else:
                    # Normal floor - grey dot with light level background
                    char = "."
                    style = f"grey50 {light_bg}".strip()

            result.append(" ")
            result.append(char, style=style)
        result.append(" |\n")

    result.append("  +" + "-" * ((max_x - min_x + 1) * 2 + 1) + "+\n")

    # Dynamic legend: observer (@) first
    at_name = "You"
    if at_entity_uuid and at_entity_uuid != current_entity_uuid:
        for e in entities:
            if e["uuid"] == at_entity_uuid:
                at_name = e["name"]
                break
    result.append("@ ", style="bold green")
    result.append(f"{at_name}  ")

    # Build legend entries from entity_icons (grouped by display icon)
    icon_to_names: Dict[str, List[Tuple[str, bool]]] = {}  # icon -> [(name, is_dead), ...]
    for e in entities:
        if e["uuid"] != at_entity_uuid and e["uuid"] != current_entity_uuid:
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
    result.append(", ", style="yellow")
    result.append("Slow  ")
    result.append("^ ", style="bold red")
    result.append("Spikes  ")
    if object_at:
        item_legend: Dict[str, str] = {}
        for obj in object_at.values():
            obj_name: str = obj.get("name", "Item")
            if obj_name in item_char_map:
                obj_char = item_char_map[obj_name]
            else:
                obj_char = ITEM_DEFAULT_CHAR
            if obj_char not in item_legend:
                item_legend[obj_char] = obj_name
        for legend_char, legend_name in sorted(item_legend.items()):
            result.append(f"{legend_char} ", style="bold cyan")
            result.append(f"{legend_name}  ")
    result.append("+ ", style="bold magenta")
    result.append("Path")

    # FOV mode indicator
    if _fov_mode != "global":
        result.append("  ")
        result.append(f"FOV:{get_fov_mode()}", style="bold yellow")

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
    elif _session_info.get("spectator_mode"):
        content.append("SPECTATOR MODE", style="bold magenta")
        content.append("  │  ")
        content.append("Watching Claude vs Claude", style="dim")
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


def _format_conditions_rich(entity: Dict[str, Any]) -> str:
    """Format conditions for Rich display, filtering by category.

    Dead entities show only 'Dead'. Internal conditions are always hidden.
    Status conditions are shown dimmed.
    """
    if entity.get("is_dead"):
        return "[dim]Dead[/dim]"

    condition_details = entity.get("condition_details", [])
    if condition_details:
        real_conds: List[str] = []
        status_conds: List[str] = []
        for cd in condition_details:
            cat = cd.get("category", "condition")
            cname = cd.get("name", "")
            if cat == "internal":
                continue
            if cat == "status":
                status_conds.append(cname)
                continue
            real_conds.append(cname)
        parts = real_conds[:]
        if status_conds:
            parts.append(f"[dim]{', '.join(status_conds)}[/dim]")
        return ", ".join(parts)

    # Fallback: old-style conditions list
    return ", ".join(entity.get("conditions", []))


def render_combatants_panel(
    entities: List[Dict[str, Any]],
    turn: Dict[str, Any],
    current_entity_uuid: Optional[str] = None,
    is_my_turn: bool = True,
    visible_uuids: Optional[Set[str]] = None,
) -> Panel:
    """Render the combatants table panel with turn info in title.

    Args:
        visible_uuids: If provided (FOV self mode), entities not in this set
            are anonymized (name/HP/AC/pos hidden). Initiative order preserved.
    """
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
        is_visible = visible_uuids is None or e["uuid"] in visible_uuids
        is_dead = e.get("is_dead", False)
        is_active = e["uuid"] == active_uuid
        is_me = e["uuid"] == current_entity_uuid

        name = e['name']
        if is_dead:
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

        conditions = _format_conditions_rich(e) or "-"
        if is_visible or is_dead:
            pos = f"({e['position'][0]},{e['position'][1]})"
        else:
            pos = "[dim]?[/dim]"
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

        conditions = _format_conditions_rich(e) or "-"
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


def _render_log_entry(entry: Dict[str, Any], content: Text, depth: int = 0):
    """Render a single combat log entry with rich formatting.

    Uses the new verbosity-based markdown format from CombatLogEntry.
    Falls back to legacy type-based rendering for backward compatibility.

    Args:
        entry: The combat log entry dict
        content: Rich Text object to append to
        depth: Indentation depth for sub-entries (0 = top level)
    """
    indent = "  " * depth  # Two spaces per level

    # Check for new verbosity-based format (has compact/verbose/detailed fields)
    if "compact" in entry:
        # New format: use verbosity setting to pick text level
        if COMBAT_LOG_VERBOSITY == CombatLogVerbosity.COMPACT:
            text = entry.get("compact", "")
        elif COMBAT_LOG_VERBOSITY == CombatLogVerbosity.VERBOSE:
            text = entry.get("verbose", entry.get("compact", ""))
        else:  # DETAILED
            text = entry.get("detailed", entry.get("verbose", entry.get("compact", "")))

        # Add indentation to each line
        if depth > 0 and text:
            lines = text.split("\n")
            text = "\n".join(indent + line for line in lines)

        # Convert markdown to Rich markup and append
        rich_text = markdown_to_rich(text)
        content.append(Text.from_markup(rich_text))

        # Recursively render sub-entries with increased depth
        sub_entries = entry.get("sub_entries", [])
        for sub_entry in sub_entries:
            content.append("\n")
            _render_log_entry(sub_entry, content, depth + 1)

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


def render_combat_log_panel(max_entries: Optional[int] = None) -> Panel:
    """Render the combat log with rich formatting."""
    global _combat_log

    limit = max_entries or MAX_COMBAT_LOG
    content = Text()
    entries = _combat_log[-limit:]

    if not entries:
        content.append("No combat history yet", style="dim")
    else:
        for i, entry in enumerate(entries):
            if i > 0:
                content.append("\n")
            _render_log_entry(entry, content)

    return Panel(content, title="Combat Log", box=box.ROUNDED, border_style="blue")


def set_thinking_text(text: str) -> None:
    """Set the latest Claude thinking text (called from spectate poll loop)."""
    global _thinking_text
    _thinking_text = text


def render_thinking_panel(max_chars: int = 600) -> Optional[Panel]:
    """Render Claude's latest thinking as a compact panel."""
    if not _thinking_text:
        return None
    display_text = _thinking_text[:max_chars]
    if len(_thinking_text) > max_chars:
        display_text += "..."
    content = Text(display_text, style="italic")
    return Panel(content, title="Claude Thinking", box=box.ROUNDED, border_style="magenta", padding=(0, 1))


def _categorize_actions(actions: Dict[str, Any], entities: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Categorize raw actions into sections for display.

    Returns dict with keys: movement, attacks, spells, items, objects, self_actions,
    other_entity, entity_lookup. Each list contains only available (can_afford + has targets) actions.
    Also includes 'all_*' variants with ALL actions (including unavailable) for count display.
    """
    entity_lookup = {e["uuid"]: e for e in entities}

    position_actions = actions.get("position_actions", [])
    all_entity_actions = actions.get("entity_actions", [])
    all_self_actions = actions.get("self_actions", [])

    # Movement (position actions that aren't spells)
    movement_actions = [a for a in position_actions if a.get("action_category", "ability") != "spell"]
    valid_movement = [a for a in movement_actions if a.get("valid_targets") and a.get("can_afford")]

    # Spells from all sources
    spell_actions_from_entity = [a for a in all_entity_actions if a.get("action_category", "ability") == "spell"]
    spell_actions_from_position = [a for a in position_actions if a.get("action_category", "ability") == "spell"]
    spell_actions_from_self = [a for a in all_self_actions if a.get("action_category", "ability") == "spell"]
    all_spell_actions = spell_actions_from_entity + spell_actions_from_position + spell_actions_from_self
    valid_spells = [a for a in all_spell_actions if a.get("valid_targets") and a.get("can_afford")]

    # Attacks
    non_spell_entity_actions = [a for a in all_entity_actions if a.get("action_category", "ability") != "spell"]
    all_attacks = [a for a in non_spell_entity_actions if a.get("action_category", "ability") == "attack"]
    other_entity_actions = [a for a in non_spell_entity_actions if a.get("action_category", "ability") != "attack"]
    valid_attacks = [a for a in all_attacks if a.get("valid_targets") and a.get("can_afford")]
    valid_other_entity = [a for a in other_entity_actions if a.get("valid_targets") and a.get("can_afford")]

    # Items (non-spell item use actions)
    item_use_self = [a for a in all_self_actions if a.get("is_item_use") and a.get("action_category", "ability") != "spell"]
    item_use_entity = [a for a in all_entity_actions if a.get("is_item_use") and a.get("action_category", "ability") != "spell"]
    all_items = item_use_self + item_use_entity
    valid_items = [a for a in all_items if a.get("can_afford")]

    # Objects (Pick Up, Attack Object)
    object_actions = actions.get("object_actions", [])
    valid_objects = [a for a in object_actions if a.get("valid_targets") and a.get("can_afford")]

    # Self-actions (non-spell, non-item)
    self_other = [a for a in all_self_actions if a.get("action_category", "ability") != "spell" and not a.get("is_item_use")]
    valid_self = [a for a in self_other if a.get("can_afford")]

    return {
        "movement": valid_movement, "all_movement": movement_actions,
        "attacks": valid_attacks, "all_attacks": all_attacks,
        "spells": valid_spells, "all_spells": all_spell_actions,
        "items": valid_items, "all_items": all_items,
        "objects": valid_objects, "all_objects": object_actions,
        "self_actions": valid_self, "all_self_actions": self_other,
        "other_entity": valid_other_entity, "all_other_entity": other_entity_actions,
        "entity_lookup": entity_lookup,
    }


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
    movement_actions = [a for a in position_actions if a.get("action_category", "ability") != "spell"]

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
    spell_actions_from_entity = [a for a in all_entity_actions if a.get("action_category", "ability") == "spell"]
    spell_actions_from_position = [a for a in position_actions if a.get("action_category", "ability") == "spell"]
    spell_actions_from_self = [a for a in all_self_actions if a.get("action_category", "ability") == "spell"]
    all_spell_actions = spell_actions_from_entity + spell_actions_from_position + spell_actions_from_self
    valid_spells = [a for a in all_spell_actions if a.get("valid_targets") and a.get("can_afford")]

    def is_attack_action(action: Dict[str, Any]) -> bool:
        """Check if action is an attack using explicit is_attack field.

        Attack actions target entities and deal damage.
        Examples: Attack, Extra Attack, Frenzied Strike.
        NOT included: "Reckless Attack" (self-buff that enables advantage).
        """
        return action.get("action_category", "ability") == "attack"

    # Non-spell entity actions
    non_spell_entity_actions = [a for a in all_entity_actions if a.get("action_category", "ability") != "spell"]
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
                if len(targets) == 1:
                    # Single target: show inline name
                    target_name = targets[0].get("target_name") or entity_lookup.get(
                        targets[0].get("target_uuid"), {}).get("name", "?")
                    content.append(f"  [", style="dim")
                    content.append(f"{cmd} 1", style="bold blue")
                    content.append(f"] ", style="dim")
                    content.append(f"{cost_label[0]} ", style=cost_label[1])
                    content.append(f"{display_name}", style="bold")
                    content.append(f" -> {target_name}\n", style="dim")
                else:
                    # Multiple targets: compact grouped line
                    content.append(f"  [", style="dim")
                    content.append(f"{cmd} N", style="bold blue")
                    content.append(f"] ", style="dim")
                    content.append(f"{cost_label[0]} ", style=cost_label[1])
                    content.append(f"{display_name}", style="bold")
                    content.append(f" ({len(targets)} targets)\n", style="dim")

            # Self-targeting spells
            else:
                content.append(f"  [", style="dim")
                content.append(f"{cmd}", style="bold blue")
                content.append(f"] ", style="dim")
                content.append(f"{cost_label[0]} ", style=cost_label[1])
                content.append(f"{display_name}", style="bold")
                content.append(f" (self)\n", style="dim")

    # ITEMS section - non-spell item use actions (potions, levers, weapon coats)
    item_use_self = [a for a in all_self_actions if a.get("is_item_use") and a.get("action_category", "ability") != "spell"]
    item_use_entity = [a for a in all_entity_actions if a.get("is_item_use") and a.get("action_category", "ability") != "spell"]
    valid_item_use = [a for a in item_use_self + item_use_entity if a.get("can_afford")]

    if valid_item_use:
        content.append("ITEMS:", style="bold cyan")
        content.append("\n", style="dim")
        for act in valid_item_use:
            template_name = act.get("template_name", "Unknown")
            display_name = act.get("display_name", template_name)
            target_type = act.get("target_type", "self")
            cost_type = act.get("cost_type", "actions")
            stack_count = act.get("item_stack_count")

            if registry:
                cmd = registry.get_or_create_shortcut(template_name)
            else:
                cmd = template_name[:2].lower()

            # Cost label
            if cost_type == "bonus_actions":
                cost_label = ("BONUS", "magenta")
            elif cost_type == "free" or act.get("cost_amount", 1) == 0:
                cost_label = ("FREE", "green")
            else:
                cost_label = ("ACTION", "cyan")

            # Stack count suffix
            stack_str = f" x{stack_count}" if stack_count and stack_count > 1 else ""

            if target_type == "self":
                content.append(f"  [", style="dim")
                content.append(f"{cmd}", style="bold cyan")
                content.append(f"] ", style="dim")
                content.append(f"{cost_label[0]} ", style=cost_label[1])
                content.append(f"{display_name}", style="bold")
                content.append(f"{stack_str}\n", style="dim")
            else:
                targets = act.get("valid_targets", [])
                for i, target in enumerate(targets):
                    target_name = target.get("target_name") or entity_lookup.get(target.get("target_uuid"), {}).get("name", "?")
                    content.append(f"  [", style="dim")
                    content.append(f"{cmd} {i+1}", style="bold cyan")
                    content.append(f"] ", style="dim")
                    content.append(f"{cost_label[0]} ", style=cost_label[1])
                    content.append(f"{display_name}", style="bold")
                    content.append(f"{stack_str}", style="dim")
                    content.append(f" -> {target_name}\n", style="dim")

    # OBJECTS section - Pick Up, Attack Object (targeting floor items)
    object_actions = actions.get("object_actions", [])
    valid_objects = [a for a in object_actions if a.get("valid_targets") and a.get("can_afford")]

    if valid_objects:
        content.append("OBJECTS:", style="bold cyan")
        content.append("\n", style="dim")
        for act in valid_objects:
            template_name = act.get("template_name", "Unknown")
            display_name = act.get("display_name", template_name)
            cost_type = act.get("cost_type", "free")
            targets = act.get("valid_targets", [])

            if registry:
                cmd = registry.get_or_create_shortcut(template_name)
            else:
                cmd = template_name[:2].lower()

            # Cost label
            if cost_type == "free" or act.get("cost_amount", 1) == 0:
                cost_label = ("FREE", "green")
            elif cost_type == "bonus_actions":
                cost_label = ("BONUS", "magenta")
            else:
                cost_label = ("ACTION", "cyan")

            for i, target in enumerate(targets):
                target_name = target.get("target_name", "Unknown")
                content.append(f"  [", style="dim")
                content.append(f"{cmd} {i+1}", style="bold cyan")
                content.append(f"] ", style="dim")
                content.append(f"{cost_label[0]} ", style=cost_label[1])
                content.append(f"{display_name}", style="bold")
                content.append(f" {target_name}\n", style="dim")

    # Self-actions - fully dynamic using registry (filter out spells and item use)
    other = [a for a in all_self_actions if a.get("action_category", "ability") != "spell" and not a.get("is_item_use")]
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

    # Reactions (handler toggle state)
    handler_details = actions.get("handler_details", [])
    if handler_details:
        build_handler_shortcuts(handler_details)
        content.append("REACTIONS:", style="bold magenta")
        content.append("  tog <shortcut> on/off\n", style="dim")
        for h in handler_details:
            name = h.get("name", "?")
            shortcut = get_handler_shortcut(name)
            enabled = h.get("enabled", True)
            if enabled:
                content.append("  [ON]  ", style="bold green")
            else:
                content.append("  [OFF] ", style="bold red")
            content.append(f"{name} ", style="white")
            content.append(f"[{shortcut}]\n", style="dim")

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
    shortcut_registry: Optional["ShortcutRegistry"] = None,
    floor_objects: Optional[List[Dict[str, Any]]] = None
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
        floor_objects: List of floor object dicts from server state
    """
    clear()

    # 1. Header panel (NEURODRAGON + connection info only)
    header_panel = render_header_panel()

    # 2. Battlefield panel (map)
    map_content = render_map_content(
        grid, entities, current_entity_uuid, valid_positions, visibility, movement_path,
        floor_objects=floor_objects
    )
    map_panel = Panel(map_content, title="Battlefield", box=box.ROUNDED, border_style="cyan")

    # 3. Combatants panel (entity table with turn info in title)
    # In FOV self mode, build set of visible entity UUIDs for anonymization
    fov_visible_uuids: Optional[Set[str]] = None
    if _fov_mode == "self" and visibility and current_entity_uuid:
        vis_data = visibility.get(current_entity_uuid, {})
        fov_visible_uuids = set(vis_data.get("visible_entities", []))
        fov_visible_uuids.add(current_entity_uuid)
    combatants_panel = render_combatants_panel(
        entities, turn, current_entity_uuid, is_my_turn,
        visible_uuids=fov_visible_uuids,
    )

    # 4. Available actions panel (only on player's turn, with economy in title)
    actions_panel = None
    if is_my_turn and actions:
        actions_panel = render_available_actions_panel(actions, entities, turn, shortcut_registry)

    # 5. Thinking panel (above combat log for readability)
    thinking_panel = render_thinking_panel()

    # 6. Combat log panel — fit to remaining terminal height
    _, term_height = get_terminal_size()
    # Estimate lines used: header(3) + map + combatants + margins(4)
    map_lines = map_content.plain.count("\n") + 5  # +borders
    entity_count = len(entities)
    combatant_lines = entity_count + 4  # +header+borders
    fixed_lines = 3 + map_lines + combatant_lines + 4
    if thinking_panel:
        # Estimate thinking panel height from content
        thinking_lines = _thinking_text.count("\n") + 4  # +borders+padding
        thinking_lines = min(thinking_lines, 15)  # Cap estimate
        fixed_lines += thinking_lines
    remaining = max(3, term_height - fixed_lines)
    # Each log entry ~2 lines on average; cap between 3 and 10
    log_max = min(10, max(3, remaining // 2))
    log_panel = render_combat_log_panel(max_entries=log_max)

    # 7. Output panel (command feedback - only if there's content)
    output_panel = render_output_panel()

    # Print all panels in order (with top padding to avoid cutoff)
    console.print()  # Top margin
    console.print(header_panel)
    console.print(map_panel)
    console.print(combatants_panel)
    if thinking_panel:
        console.print(thinking_panel)
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

    When FOW mode is enabled, entries are filtered through log_filter before display.

    Args:
        entry: A CombatLogEntry.to_dict() from the server
    """
    # Apply FOW filtering if enabled (skip system events that always show
    # the real name regardless of visibility: turn boundaries and condition
    # expiration between turns)
    entry_type = entry.get("entry_type", "").lower()
    _skip_fow_types = ("turn_start", "turn_end", "condition_removed", "condition_applied")
    if _fow_enabled and _fow_controlled_uuids and entry_type not in _skip_fow_types:
        from cli.log_filter import filter_combat_log
        filtered = filter_combat_log(
            [entry], _fow_controlled_uuids, _fow_visible_entity_uuids or None,
        )
        if not filtered:
            return  # Filtered out by temporal visibility
        entry = filtered[0]

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
    from rich.text import Text
    error_text = Text("Error: ", style="red")
    error_text.append(message, style="red")
    console.print(error_text)


def show_info(message: str):
    """Display an info message."""
    from rich.text import Text
    info_text = Text(message, style="cyan")
    console.print(info_text)


def show_available_actions(actions: Dict[str, Any], entities: List[Dict[str, Any]]):
    """Display available actions (legacy - now integrated into full screen)."""
    panel = render_available_actions_panel(actions, entities, {"actions_remaining": 1})
    console.print(panel)


def show_filtered_actions(
    actions: Dict[str, Any],
    entities: List[Dict[str, Any]],
    turn: Dict[str, Any],
    filter_type: str,
    registry: Optional["ShortcutRegistry"] = None
):
    """Show a filtered view of available actions for a specific category.

    Args:
        actions: Raw actions dict from server
        entities: Entity list for name lookup
        turn: Turn info for economy
        filter_type: One of 'filter_actions', 'filter_spells', 'filter_items',
                     'filter_attacks', 'filter_move'
        registry: Shortcut registry for command hints
    """
    if not actions:
        console.print("[dim]No actions available.[/dim]")
        return

    cats = _categorize_actions(actions, entities)
    entity_lookup = cats["entity_lookup"]
    content = Text()

    # Map filter type to category key and title
    filter_map = {
        "filter_actions": ("all", "All Actions"),
        "filter_spells": ("spells", "Spells"),
        "filter_items": ("items", "Items"),
        "filter_attacks": ("attacks", "Attacks"),
        "filter_move": ("movement", "Movement"),
    }
    cat_key, title = filter_map.get(filter_type, ("all", "All Actions"))

    if cat_key == "all":
        # Show everything — use full render
        panel = render_available_actions_panel(actions, entities, turn, registry)
        console.print(panel)
        return

    valid_list = cats.get(cat_key, [])
    all_list = cats.get(f"all_{cat_key}", [])
    shown = len(valid_list)
    total = len(all_list)

    if not valid_list:
        content.append(f"No available {title.lower()}.", style="dim")
        if total > 0:
            content.append(f" ({total} registered but unavailable)", style="dim")
        console.print(Panel(content, title=f"{title} [{shown}/{total}]", box=box.ROUNDED, border_style="cyan"))
        return

    for act in valid_list:
        template_name = act.get("template_name", "Unknown")
        display_name = act.get("display_name", template_name)
        target_type = act.get("target_type", "self")
        targets = act.get("valid_targets", [])
        cost_type = act.get("cost_type", "actions")
        cost_amount = act.get("cost_amount", 1)

        # Shortcut
        if registry:
            cmd = registry.get_or_create_shortcut(template_name)
        else:
            cmd = template_name[0].lower()

        # Cost label
        if cost_amount == 0:
            cost_label = ("FREE", "green")
        elif cost_type == "bonus_actions":
            cost_label = ("BONUS", "magenta")
        elif cost_type == "movement":
            remaining = actions.get("remaining_movement", 0)
            cost_label = (f"{remaining}ft", "cyan")
        elif cost_type == "reactions":
            cost_label = ("REACT", "yellow")
        else:
            cost_label = ("ACTION", "cyan")

        # Stack info for items
        stack_count = act.get("item_stack_count")
        stack_str = f" x{stack_count}" if stack_count and stack_count > 1 else ""

        if target_type in ("position_aoe", "position_los", "position_path", "position"):
            content.append(f"  [", style="dim")
            content.append(f"{cmd} X Y", style="bold yellow")
            content.append(f"] ", style="dim")
            content.append(f"{cost_label[0]} ", style=cost_label[1])
            content.append(f"{display_name}", style="bold")
            content.append(f" ({len(targets)} positions)\n", style="dim")
        elif target_type in ("entity", "multi_entity"):
            for i, target in enumerate(targets):
                target_name = target.get("target_name") or entity_lookup.get(target.get("target_uuid"), {}).get("name", "?")
                content.append(f"  [", style="dim")
                content.append(f"{cmd} {i+1}", style="bold yellow")
                content.append(f"] ", style="dim")
                content.append(f"{cost_label[0]} ", style=cost_label[1])
                content.append(f"{display_name}", style="bold")
                content.append(f"{stack_str} -> {target_name}\n", style="dim")
        else:
            # Self-targeting
            content.append(f"  [", style="dim")
            content.append(f"{cmd}", style="bold yellow")
            content.append(f"] ", style="dim")
            content.append(f"{cost_label[0]} ", style=cost_label[1])
            content.append(f"{display_name}", style="bold")
            content.append(f"{stack_str}\n", style="dim")

    console.print(Panel(content, title=f"{title} [{shown}/{total}]", box=box.ROUNDED, border_style="cyan"))


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

[bold cyan]FOV (Field of View):[/bold cyan]
  fov                 Show current FOV mode
  fov self            Your entity's vision (fog of war)
  fov global          All entities merged (default)
  fov N               Enemy N's vision (legend numbering)

[bold cyan]Reactions:[/bold cyan]
  handlers / reactions  Show all handlers (ON/OFF state)
  toggle <name> on/off  Toggle a handler on or off
  t <name> on/off       Shortcut for toggle

[bold cyan]Game:[/bold cyan]
  q / quit            Exit the game
"""
    console.print(Panel(help_text, title="Help", box=box.ROUNDED))
