"""
Non-interactive CLI for AI agents (Claude) to control D&D entities.

This module provides a command-line interface that can be called from Bash,
enabling Claude Code to play the game by issuing commands.

Updated to use session-based authentication.

Usage:
    python -m cli.agent [--token TOKEN] <command> [args]
    python -m cli.agent connect              # Connect to game (creates session, joins)
    python -m cli.agent --token hero move X Y  # Multi-session with token
    python -m cli.agent state                # Show game state (map, entities, turn)
    python -m cli.agent actions              # Show available actions
    python -m cli.agent move X Y             # Move to position
    python -m cli.agent attack N             # Attack target by index
    python -m cli.agent dash                 # Take Dash action
    python -m cli.agent dodge                # Take Dodge action
    python -m cli.agent disengage            # Take Disengage action
    python -m cli.agent end                  # End turn
"""

import sys
import os
import re
from typing import Optional, List, Tuple
from cli.api_client import APIClient

# Session persistence file (so we don't create new sessions every command)
SESSION_FILE = "/tmp/dnd_agent_session.txt"
_LIGHT_LABELS = {0: "mag-dark", 1: "dark", 2: "dim", 3: "bright", 4: "very-bright"}


def save_session(session_id: str, entity_uuids: List[str]) -> None:
    """Save session info to file for persistence between commands.

    File format:
        Line 1: session_id
        Lines 2+: entity UUIDs (one per line)
    """
    with open(SESSION_FILE, "w") as f:
        lines = [session_id] + entity_uuids
        f.write("\n".join(lines))


def load_session() -> Tuple[Optional[str], List[str]]:
    """Load session info from file.

    Returns (session_id, entity_uuids) or (None, []).
    """
    if not os.path.exists(SESSION_FILE):
        return None, []
    try:
        with open(SESSION_FILE, "r") as f:
            lines = f.read().strip().split("\n")
            if len(lines) >= 2:
                return lines[0], lines[1:]  # All entity UUIDs after first line
    except Exception:
        pass
    return None, []


def clear_session() -> None:
    """Clear saved session."""
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)


def ensure_session(client: APIClient) -> bool:
    """
    Ensure client has a valid session. Loads from file or returns False.

    Returns True if session loaded successfully, False if need to connect.

    KEY: Also switches client._current_entity_uuid to whichever controlled
    entity's turn it currently is (for multi-entity support).
    """
    session_id, entity_uuids = load_session()
    if not session_id or not entity_uuids:
        return False

    # Set the session on the client
    client._session_id = session_id
    client._controlled_entity_uuids = entity_uuids  # Track all controlled entities
    client._current_entity_uuid = entity_uuids[0]   # Default to first

    # Verify session is still valid by pinging
    try:
        result = client.ping_session()
        if result.get("connection_status") == "disconnected":
            clear_session()
            return False

        # KEY FIX: Switch to active entity if it's one of ours
        active_uuid = result.get("active_entity_uuid")
        if active_uuid and active_uuid in entity_uuids:
            client._current_entity_uuid = active_uuid

        return True
    except Exception:
        clear_session()
        return False


def strip_markdown(text: str) -> str:
    """Strip {color:text} and **bold** markdown from combat log text."""
    text = re.sub(r'\{[^{}:]+:([^}]+)\}', r'\1', text)  # {color:text} -> text
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)        # **bold** -> bold
    text = re.sub(r'\*([^*]+)\*', r'\1', text)             # *italic* -> italic
    text = re.sub(r'~~([^~]+)~~', r'\1', text)             # ~~strike~~ -> strike
    return text


def format_combat_log_entry(entry: dict, indent: int = 0) -> List[str]:
    """Format a combat log entry + sub_entries recursively using verbose text.

    Uses 'verbose' level (includes roll details like 'd20(15)+4=19 vs AC 13')
    so the agent sees the same detail as the human player.
    Falls back to compact if verbose not available.
    """
    lines: List[str] = []
    text = entry.get("verbose", entry.get("compact", entry.get("summary", "")))
    if text:
        prefix = "  " * indent
        lines.append(f"{prefix}{strip_markdown(text)}")
    for sub in entry.get("sub_entries", []):
        lines.extend(format_combat_log_entry(sub, indent + 1))
    return lines


def show_combat_log(entries: List[dict], label: str = "LOG") -> None:
    """Print combat log entries with a label prefix."""
    for entry in entries:
        for line in format_combat_log_entry(entry):
            print(f"  [{label}] {line}")


def show_action_result_status(result: dict) -> None:
    """Show deaths and encounter-end status from an action result."""
    deaths = result.get("deaths", [])
    if deaths:
        for name in deaths:
            print(f"  >>> {name} DIED <<<")
    if result.get("encounter_ended", False):
        print("")
        print("=" * 40)
        print("  ENCOUNTER ENDED — game over!")
        print("=" * 40)


def show_inline_state(result: dict, client: APIClient) -> None:
    """Show map and entity table from the inline state in an action result."""
    state = result.get("state")
    if not state:
        return

    my_entity_uuid = client.current_entity_uuid
    controlled_uuids = getattr(client, '_controlled_entity_uuids', [])

    # Fetch FOV — same pattern as cmd_state()
    visibility = client.get_visibility() or {}
    visible_entity_uuids = None
    visible_cells = None
    memory_cells = None
    sense_modes: list = []
    if my_entity_uuid and my_entity_uuid in visibility:
        my_vis = visibility[my_entity_uuid]
        visible_entity_uuids = set(my_vis.get("visible_entities", []))
        visible_entity_uuids.update(controlled_uuids)
        visible_cells = set(tuple(c) for c in my_vis.get("visible_cells", []))
        seen_cells = set(tuple(c) for c in my_vis.get("seen_cells", []))
        memory_cells = seen_cells - visible_cells
        sense_modes = my_vis.get("sense_modes", [])

    actions_data = result.get("available_actions", {})
    pos_actions = actions_data.get("position_actions", []) if actions_data else []

    print("")
    print(format_map(state, visible_entity_uuids, my_entity_uuid, visible_cells, memory_cells, pos_actions,
                     sense_modes=sense_modes))
    print("")

    entities = state.get("entities", [])
    encounter = state.get("encounter")
    init_order = encounter.get("initiative_order") if encounter else None
    print(format_entities(entities, visible_entity_uuids, my_entity_uuid,
                          controlled_uuids, init_order))


def show_remaining_actions(result: dict) -> None:
    """Show compact summary of remaining actions from execute response."""
    actions = result.get("available_actions")
    if not actions:
        return

    act = actions.get("actions_remaining", 0)
    bonus = actions.get("bonus_actions_remaining", 0)
    movement = actions.get("remaining_movement", 0)
    extra_atk = actions.get("extra_attacks_remaining", 0)
    extra_str = f"  Extra Attacks:{extra_atk}" if extra_atk else ""
    spell_slots = actions.get("spell_slots", {})
    slots_str = ""
    if spell_slots:
        slot_parts = [f"L{lvl}:{info['current']}/{info['max']}" for lvl, info in sorted(spell_slots.items())]
        slots_str = f"  Slots: {' '.join(slot_parts)}"
    print(f"REMAINING: Actions:{act}  Bonus:{bonus}  Movement:{movement}ft{extra_str}{slots_str}")

    # Show ready entity actions (attacks) with targets
    entity_actions = actions.get("entity_actions", [])
    ready_attacks = []
    for i, atk in enumerate(entity_actions):
        if atk.get("can_afford", False) and atk.get("valid_targets"):
            name = atk.get("display_name", atk.get("template_name", "?"))
            cost_type = atk.get("cost_type", "actions")
            cost_label = {"actions": "action", "bonus_actions": "bonus", "extra_attacks": "extra attack"}.get(cost_type, cost_type)
            targets = atk.get("valid_targets", [])
            target_parts = [f"[{t.get('index', j)}]{t.get('target_name', '?')}" for j, t in enumerate(targets[:5])]
            ready_attacks.append(f"[{i}] {name} ({cost_label}) -> {', '.join(target_parts)}")
    if ready_attacks:
        print(f"READY ATTACKS: {' | '.join(ready_attacks)}")


def show_full_actions(result: dict, client: APIClient) -> None:
    """Show full available actions (same info as human's persistent panel)."""
    actions = result.get("available_actions")
    if not actions:
        return
    entity_uuid = client.current_entity_uuid
    state = result.get("state", {})
    entity_name = "???"
    state_entities = state.get("entities", [])
    for e in state_entities:
        if e.get("uuid") == entity_uuid:
            entity_name = e.get("name", "???")
            break
    print("")
    print(format_actions(actions, entity_name))


def get_my_entity(client: APIClient) -> Optional[dict]:
    """
    Get the entity that the agent controls.
    Uses the session's controlled entity UUID instead of hardcoded name lookup.
    Returns entity dict with uuid, name, position, etc.
    """
    entity_uuid = client.current_entity_uuid
    if not entity_uuid:
        return None

    state = client.get_state()
    if not state:
        return None

    entities = state.get("entities", [])
    for e in entities:
        if e.get("uuid") == entity_uuid:
            return e
    return None


def is_my_turn(client: APIClient) -> bool:
    """Check if it's the agent's turn using session ping."""
    if not client.session_id:
        return False

    try:
        result = client.ping_session()
        return result.get("is_my_turn", False)
    except Exception:
        return False


def get_visibility_data(client: APIClient) -> Tuple[
    Optional[set], Optional[set], Optional[set], list
]:
    """Get visibility data (visible entities, visible cells, memory cells, sense_modes).

    Returns (visible_entity_uuids, visible_cells, memory_cells, sense_modes).
    First three are None if no visibility data available (omniscient view).
    sense_modes is always a list (empty if unavailable).
    """
    my_entity_uuid = client.current_entity_uuid
    controlled_uuids = getattr(client, '_controlled_entity_uuids', [])
    visibility = client.get_visibility() or {}

    if not my_entity_uuid or my_entity_uuid not in visibility:
        return None, None, None, []

    my_vis = visibility[my_entity_uuid]
    vis_set: set = set(my_vis.get("visible_entities", []))
    vis_set.update(controlled_uuids)
    vis_cells = set(tuple(c) for c in my_vis.get("visible_cells", []))
    seen_cells = set(tuple(c) for c in my_vis.get("seen_cells", []))
    mem_cells = seen_cells - vis_cells
    sense_modes = my_vis.get("sense_modes", [])
    return vis_set, vis_cells, mem_cells, sense_modes


def format_map(state: dict, visible_entity_uuids: Optional[set] = None,
               my_entity_uuid: Optional[str] = None,
               visible_cells: Optional[set] = None,
               memory_cells: Optional[set] = None,
               position_actions: Optional[list] = None,
               sense_modes: Optional[list] = None) -> str:
    """Format map as structured data + ASCII grid for AI consumption.

    Outputs two sections:
    1. Structured coordinate data (precise positions for targeting)
    2. ASCII grid (spatial layout for understanding adjacency/distance)

    Both sections are filtered by visible_cells (FOV) when provided.
    Only tiles the entity can actually see are included.

    Args:
        state: Full game state from /state endpoint
        visible_entity_uuids: Set of entity UUIDs visible to the observer.
            If None, shows all entities (omniscient view).
        my_entity_uuid: UUID of the observer entity (marked as @).
        visible_cells: Set of (x,y) tuples the entity can currently see.
            If None, shows all tiles (omniscient view).
    """
    grid = state.get("grid", {})
    tiles = grid.get("tiles", [])

    # Build tile lookup
    tile_map: dict[tuple[int, int], dict] = {}
    for t in tiles:
        tile_map[(t.get("x", 0), t.get("y", 0))] = t

    # Get bounds
    min_x = grid.get("min_x", 0)
    max_x = grid.get("max_x", 14)
    min_y = grid.get("min_y", 0)
    max_y = grid.get("max_y", 14)

    entities = state.get("entities", [])
    my_faction: Optional[str] = None
    for e in entities:
        if e.get("uuid") == my_entity_uuid:
            my_faction = e.get("faction")
            break

    def _is_visible(pos: tuple) -> bool:
        """Check if a position is visible to the entity."""
        if visible_cells is None:
            return True
        return pos in visible_cells

    lines: List[str] = []
    lines.append(f"MAP: ({min_x},{min_y})-({max_x},{max_y})")

    # --- Entities section ---
    entity_lines: List[str] = []
    visible_entities: list = []
    for e in entities:
        e_uuid = e.get("uuid")
        if visible_entity_uuids is not None and e_uuid != my_entity_uuid:
            if e_uuid not in visible_entity_uuids:
                continue
        visible_entities.append(e)

    # Build position -> entities map for TILE DETAILS
    entity_pos_map: dict[tuple[int, int], list] = {}
    for e in visible_entities:
        pos = e.get("position", [0, 0])
        pos_tuple = (pos[0], pos[1])
        if pos_tuple not in entity_pos_map:
            entity_pos_map[pos_tuple] = []
        entity_pos_map[pos_tuple].append(e)

    # Build floor object position map (visible only, for TILE DETAILS and ASCII grid)
    obj_pos_map: dict[tuple[int, int], list] = {}
    for obj in state.get("floor_objects", []):
        pos = obj.get("position", [0, 0])
        pos_tuple = (pos[0], pos[1])
        if not _is_visible(pos_tuple):
            continue
        if pos_tuple not in obj_pos_map:
            obj_pos_map[pos_tuple] = []
        obj_pos_map[pos_tuple].append(obj)

    for e in visible_entities:
        e_uuid = e.get("uuid")
        pos = e.get("position", [0, 0])
        name = e.get("name", "?")
        is_dead = e.get("is_dead", False)

        if e_uuid == my_entity_uuid:
            tag = "you"
        elif is_dead:
            tag = "dead"
        else:
            faction = e.get("faction")
            if my_faction and faction == my_faction:
                tag = "ally"
            elif my_faction and faction and faction != my_faction:
                tag = "enemy"
            else:
                tag = ""
        entity_lines.append(f"({pos[0]},{pos[1]}):{name}({tag})")
    if entity_lines:
        lines.append(f"ENTITIES: {' '.join(entity_lines)}")

    # --- Build AoE spell annotations per position (deduped by effect) ---
    aoe_at_pos: dict[tuple[int, int], List[str]] = {}
    if position_actions:
        # Intermediate: pos -> {(base_spell, level, affected_key): [sources]}
        aoe_raw: dict[tuple[int, int], dict[tuple, dict]] = {}
        for action in position_actions:
            if action.get("action_category") != "spell" or not action.get("can_afford", False):
                continue
            # Extract base spell name and level
            display_name = action.get("display_name", action.get("template_name", "?"))
            template_name = action.get("template_name", display_name)
            is_scroll = action.get("is_item_use", False)
            # Spell level from cost_type (spell_slot_N) or template_name for scrolls
            cost_type = action.get("cost_type", "")
            level_str = ""
            if cost_type.startswith("spell_slot_"):
                level_str = f" L{cost_type.split('_')[-1]}"
            # Base spell name (strip __item_UUID suffix from template_name)
            base_name = template_name.split("__item_")[0] if "__item_" in template_name else template_name

            for t in action.get("valid_targets", []):
                affected_uuids = t.get("affected_entity_uuids", [])
                affected_names = t.get("affected_entity_names", [])
                count = t.get("affected_count", 0)
                if not count:
                    continue
                # Skip self-only targets
                if count == 1 and affected_uuids and affected_uuids[0] == my_entity_uuid:
                    continue
                # Build name list: "self" for caster, actual names for others
                name_list: List[str] = []
                for uid, uname in zip(affected_uuids, affected_names):
                    if uid == my_entity_uuid:
                        name_list.append("self")
                    else:
                        name_list.append(uname)
                affected_key = tuple(name_list)
                pos = t.get("position", [0, 0])
                pos_tuple = (pos[0], pos[1])
                if pos_tuple not in aoe_raw:
                    aoe_raw[pos_tuple] = {}
                dedup_key = (base_name, level_str, affected_key)
                if dedup_key not in aoe_raw[pos_tuple]:
                    aoe_raw[pos_tuple][dedup_key] = {"slot": 0, "scroll": 0}
                if is_scroll:
                    aoe_raw[pos_tuple][dedup_key]["scroll"] += 1
                else:
                    aoe_raw[pos_tuple][dedup_key]["slot"] += 1

        # Build final labels from deduped data
        for pos_tuple, effects in aoe_raw.items():
            labels: List[str] = []
            for (base_name, level_str, affected_key), sources in effects.items():
                source_parts: List[str] = []
                if sources["slot"]:
                    source_parts.append("slot")
                if sources["scroll"]:
                    sc = sources["scroll"]
                    source_parts.append(f"scroll x{sc}" if sc > 1 else "scroll")
                source_str = f" ({', '.join(source_parts)})" if source_parts else ""
                labels.append(f"{base_name}{level_str}: {','.join(affected_key)}{source_str}")
            aoe_at_pos[pos_tuple] = labels

    # --- TILE DETAILS (consolidated per-position data for ALL visible tiles) ---
    detail_lines: List[str] = []
    for pos in sorted(tile_map.keys()):
        if not _is_visible(pos):
            continue
        tile = tile_map[pos]
        tile_name = tile.get("name", "Floor")
        is_hazardous = tile.get("is_hazardous", False)
        walking_cost = tile.get("walking_cost", 1)
        conditions = tile.get("conditions", [])

        raw_light = tile.get("light_level", 3)
        objective_label = _LIGHT_LABELS.get(raw_light, f"light-{raw_light}")

        # Show sense-mode shift only when we have real sense mode data.
        # Matches priority order from base_tiles.get_effective_light_for():
        #   Truesight/Blindsight → bright (any darkness)
        #   Devil's Sight → bright (any darkness including magical)
        #   Darkvision → dark->dim, dim->bright (NOT magical darkness)
        #   No sense mode → show raw label
        light_label = objective_label
        if sense_modes and visible_cells is not None:
            sense_types = {sm.get("sense_type", "") for sm in sense_modes}
            has_true_or_blind = bool(sense_types & {"Truesight", "Blindsight"})
            has_devils_sight = "Devils Sight" in sense_types
            has_darkvision = "Darkvision" in sense_types
            if raw_light == 0:  # Magical darkness
                if has_true_or_blind or has_devils_sight:
                    light_label = f"{objective_label}->bright"
            elif raw_light == 1:  # Darkness
                if has_true_or_blind or has_devils_sight:
                    light_label = f"{objective_label}->bright"
                elif has_darkvision:
                    light_label = f"{objective_label}->dim"
            elif raw_light == 2:  # Dim light
                if has_darkvision:
                    light_label = f"{objective_label}->bright"

        pos_entities = entity_pos_map.get(pos, [])
        pos_objects = obj_pos_map.get(pos, [])

        parts: List[str] = []

        # Terrain + light
        terrain_info = [tile_name, light_label]
        if is_hazardous:
            terrain_info.append("hazardous")
        if walking_cost > 1 and "difficult" not in tile_name.lower():
            terrain_info.append("difficult terrain")
        parts.append(", ".join(terrain_info))

        # Tile conditions (zone spells, fire, etc.)
        for cond in conditions:
            parts.append(cond)

        # Entities at this position
        for e in pos_entities:
            e_uuid = e.get("uuid")
            name = e.get("name", "?")
            if e.get("is_dead", False):
                parts.append(f"{name} (dead)")
            elif e_uuid == my_entity_uuid:
                parts.append(f"{name} (you, {e.get('hp', 0)}/{e.get('max_hp', 0)}hp, AC {e.get('ac', 0)})")
            else:
                faction = e.get("faction")
                ftag = ""
                if my_faction and faction == my_faction:
                    ftag = "ally"
                elif my_faction and faction and faction != my_faction:
                    ftag = "enemy"
                hp_str = f"{e.get('hp', 0)}/{e.get('max_hp', 0)}hp"
                if ftag:
                    parts.append(f"{name} ({ftag}, {hp_str}, AC {e.get('ac', 0)})")
                else:
                    parts.append(f"{name} ({hp_str}, AC {e.get('ac', 0)})")

        # Floor objects
        for obj in pos_objects:
            obj_name = obj.get("name", "Item")
            tags: List[str] = []
            if obj.get("is_pickable"):
                tags.append("pickable")
            if obj.get("is_usable"):
                tags.append("usable")
            if tags:
                parts.append(f"{obj_name} ({', '.join(tags)})")
            else:
                parts.append(obj_name)

        # AoE spell annotations
        for label in aoe_at_pos.get(pos, []):
            parts.append(f"[{label}]")

        detail_lines.append(f"  ({pos[0]},{pos[1]}): {' | '.join(parts)}")

    if detail_lines:
        lines.append("TILE DETAILS:")
        lines.extend(detail_lines)

    # --- MEMORY (previously seen, not currently visible) ---
    if memory_cells:
        mem_lines: List[str] = []
        for pos in sorted(memory_cells):
            tile = tile_map.get(pos)
            if not tile:
                continue
            tile_name = tile.get("name", "Floor")
            conditions = tile.get("conditions", [])
            # Objects at memory positions (from full state, not FOV-filtered)
            mem_objects: List[str] = []
            for obj in state.get("floor_objects", []):
                obj_pos = obj.get("position", [0, 0])
                if (obj_pos[0], obj_pos[1]) == pos:
                    mem_objects.append(obj.get("name", "Item"))
            # Only skip completely empty floor (terrain/objects/conditions all default)
            if tile_name == "Floor" and not conditions and not mem_objects:
                continue
            mem_parts = [tile_name]
            mem_parts.extend(conditions)
            mem_parts.extend(mem_objects)
            mem_lines.append(f"  ({pos[0]},{pos[1]}): {', '.join(mem_parts)}")
        if mem_lines:
            lines.append("MEMORY (previously seen, not currently visible):")
            lines.extend(mem_lines)

    # ===== ASCII GRID (spatial layout) =====
    # Assign entity symbols: @ for self, % for dead, letters/numbers for others
    entity_char_map: dict[tuple[int, int], str] = {}
    legend_entries: List[str] = []
    # Count first letters to detect collisions
    first_letters: dict[str, list] = {}
    for e in visible_entities:
        if e.get("uuid") == my_entity_uuid or e.get("is_dead", False):
            continue
        letter = e.get("name", "?")[0].upper()
        if letter not in first_letters:
            first_letters[letter] = []
        first_letters[letter].append(e)

    # Assign chars (priority: @ > alive > dead — never overwrite higher priority)
    next_num = 1
    for e in visible_entities:
        e_uuid = e.get("uuid")
        pos = e.get("position", [0, 0])
        pos_tuple = (pos[0], pos[1])
        name = e.get("name", "?")
        is_dead = e.get("is_dead", False)

        if e_uuid == my_entity_uuid:
            entity_char_map[pos_tuple] = "@"  # Self always wins
        elif is_dead:
            # Dead only renders if no living entity or self already there
            if pos_tuple not in entity_char_map:
                entity_char_map[pos_tuple] = "%"
        else:
            letter = name[0].upper()
            if len(first_letters.get(letter, [])) > 1:
                char = str(next_num)
                next_num += 1
            else:
                char = letter
            # Alive entity overwrites dead but not self
            existing = entity_char_map.get(pos_tuple)
            if existing != "@":
                entity_char_map[pos_tuple] = char
            # Legend entry (always add — entity is listed in ENTITIES section regardless)
            faction = e.get("faction")
            if my_faction and faction == my_faction:
                tag = "ally"
            elif my_faction and faction and faction != my_faction:
                tag = "enemy"
            else:
                tag = ""
            legend_entries.append(f"{char}={name}({tag})" if tag else f"{char}={name}")

    # Build grid rows
    width = max_x - min_x + 1
    border = "=" * (width + 2)
    lines.append("")
    lines.append(border)
    for y in range(min_y, max_y + 1):
        row_chars: List[str] = []
        for x in range(min_x, max_x + 1):
            pos = (x, y)
            # Not visible = space (fog of war)
            if not _is_visible(pos):
                row_chars.append(" ")
                continue
            # Entity takes priority
            if pos in entity_char_map:
                row_chars.append(entity_char_map[pos])
                continue
            # Floor object
            if pos in obj_pos_map:
                row_chars.append("\u03c6")  # φ
                continue
            tile = tile_map.get(pos)
            if tile is None:
                row_chars.append(" ")
                continue
            # Terrain
            if not tile.get("walkable", True):
                tile_name = tile.get("name", "Wall")
                if tile_name == "Water":
                    row_chars.append("~")
                else:
                    row_chars.append("#")
            elif tile.get("is_hazardous", False) or tile.get("name") == "Spikes":
                row_chars.append("^")
            elif tile.get("walking_cost", 1) > 1 or tile.get("name") == "Difficult Terrain":
                row_chars.append(",")
            else:
                row_chars.append(".")
        lines.append("|" + "".join(row_chars) + "|")
    lines.append(border)

    # Legend
    legend_parts = ["@=You"]
    legend_parts.extend(legend_entries)
    legend_parts.extend(["%=Dead", "#=Wall", "~=Water", "^=Hazard", ",=Slow", ".=Floor", "\u03c6=Item"])
    lines.append("LEGEND: " + "  ".join(legend_parts))

    return "\n".join(lines)


def _format_cost_label(cost_type: str, cost_amount: int) -> str:
    """Format cost type and amount into a short label for display."""
    if cost_amount == 0:
        return "FREE"
    label = {"actions": "action", "bonus_actions": "bonus", "reactions": "reaction", "movement": "movement"}.get(cost_type, cost_type)
    return label


def format_entities(entities: list, visible_entity_uuids: Optional[set] = None,
                    my_entity_uuid: Optional[str] = None,
                    controlled_uuids: Optional[List[str]] = None,
                    initiative_order: Optional[list] = None) -> str:
    """Format entity status table sorted by initiative order.

    Args:
        entities: All entities from state.
        visible_entity_uuids: Set of entity UUIDs visible to the observer.
            If None, shows all entities (omniscient view).
        my_entity_uuid: UUID of the observer entity (always shown).
        controlled_uuids: All entity UUIDs controlled by this session (always shown).
        initiative_order: List of {uuid, name, initiative} dicts from encounter.
            If provided, entities are sorted by initiative (turn order).
    """
    # Sort entities by initiative order if available
    if initiative_order:
        order_map = {c.get("uuid"): i for i, c in enumerate(initiative_order)}
        entities = sorted(entities, key=lambda e: order_map.get(e.get("uuid"), 999))

    lines = ["ENTITIES (in turn order):"]
    lines.append(f"{'#':<3} {'Name':<12} {'Faction':<10} {'HP':<8} {'AC':<4} {'Pos':<8} {'Conditions'}")
    lines.append("-" * 70)

    stealth_conditions = {"hidden", "invisible"}
    controlled = set(controlled_uuids or [])

    for i, e in enumerate(entities):
        e_uuid = e.get("uuid")

        # Visibility filtering (dead entities always shown — bodies are visible)
        is_dead = e.get("is_dead", False)
        is_mine = e_uuid == my_entity_uuid or e_uuid in controlled
        if visible_entity_uuids is not None and not is_mine and not is_dead:
            if e_uuid not in visible_entity_uuids:
                # Not visible — show as "[NOT VISIBLE]" with position only
                name = e.get("name", "???")
                lines.append(f"{i:<3} {name:<12} {'?':<10} {'?':<8} {'?':<4} {'?':<8} [NOT VISIBLE]")
                continue

        name = e.get("name", "???")
        faction = e.get("faction") or "(none)"
        hp = f"{e.get('hp', 0)}/{e.get('max_hp', 0)}"
        ac = e.get("ac", 0)
        pos = e.get("position", [0, 0])
        pos_str = f"({pos[0]},{pos[1]})"

        # Build filtered condition display using condition_details
        condition_details = e.get("condition_details", [])
        if e.get("is_dead"):
            conditions = "Dead"
        elif condition_details:
            # Filter by category based on ownership
            real_conds = []
            status_conds = []
            for cd in condition_details:
                cat = cd.get("category", "condition")
                cname = cd.get("name", "")
                if cat == "internal":
                    continue  # Always skip internal
                if cat == "status":
                    status_conds.append(cname)
                    continue
                # Real condition — tag stealth
                if cname.lower() in stealth_conditions:
                    real_conds.append(f"{cname} [STEALTH]")
                else:
                    real_conds.append(cname)
            # Combine: real conditions, then dimmed statuses
            parts = real_conds[:]
            if status_conds:
                parts.append(f"({', '.join(status_conds)})")
            conditions = ", ".join(parts) or "none"
        else:
            # Fallback: old-style conditions list (no details available)
            raw_conditions = e.get("conditions", [])
            tagged = []
            for c in raw_conditions:
                if c.lower() in stealth_conditions:
                    tagged.append(f"{c} [STEALTH]")
                else:
                    tagged.append(c)
            conditions = ", ".join(tagged) or "none"

        # Mark controlled entities
        mine_tag = " *" if is_mine else ""
        lines.append(f"{i:<3} {name:<12} {faction:<10} {hp:<8} {ac:<4} {pos_str:<8} {conditions}{mine_tag}")

    return "\n".join(lines)


def format_actions(actions: dict, entity_name: str) -> str:
    """Format available actions."""
    lines = [f"AVAILABLE ACTIONS FOR {entity_name}:"]

    # Action economy summary
    act = actions.get("actions_remaining", "?")
    bonus = actions.get("bonus_actions_remaining", "?")
    react = actions.get("reactions_remaining", "?")
    movement = actions.get("remaining_movement", 0)
    extra_atk = actions.get("extra_attacks_remaining", 0)
    extra_str = f"  Extra Attacks:{extra_atk}" if extra_atk else ""
    # Spell slots
    spell_slots = actions.get("spell_slots", {})
    slots_str = ""
    if spell_slots:
        slot_parts = [f"L{lvl}:{info['current']}/{info['max']}" for lvl, info in sorted(spell_slots.items())]
        slots_str = f"  Slots: {' '.join(slot_parts)}"
    lines.append(f"RESOURCES: Actions:{act}  Bonus:{bonus}  Reactions:{react}  Movement:{movement}ft{extra_str}{slots_str}")
    lines.append("")

    # Position-based actions (Move, Jump, AoE spells)
    position_actions = actions.get("position_actions", [])
    lines.append("POSITION ACTIONS:")

    for action in position_actions:
        template_name = action.get("template_name", "Unknown")
        display_name = action.get("display_name", template_name)
        valid_targets = action.get("valid_targets", [])
        can_afford = action.get("can_afford", False)
        cost_type = action.get("cost_type", "movement")
        is_spell = action.get("action_category") == "spell"

        # Status
        if not can_afford:
            status = "NO RESOURCE"
        elif not valid_targets:
            status = "NO TARGETS"
        else:
            status = "READY"

        cost_label = {"movement": "movement", "bonus_actions": "bonus", "actions": "action"}.get(cost_type, cost_type)
        spell_tag = "[SPELL] " if is_spell else ""

        lines.append(f"  {spell_tag}{display_name}: {len(valid_targets)} positions ({cost_label}) - {status}")

        if valid_targets and can_afford:
            if is_spell:
                # AoE targets are shown in TILE DETAILS with spell#index annotations
                # Just show usage hint here
                lines.append(f"    Usage: cast {display_name} X Y (see TILE DETAILS for targeting positions)")
            else:
                # Non-spell position actions (Move, Jump): show full position list
                pos_strs = [f"({t.get('position', [0,0])[0]},{t.get('position', [0,0])[1]})" for t in valid_targets]
                lines.append(f"    Targets: {', '.join(pos_strs)}")

    lines.append("")

    # Entity-targeting actions (attacks + entity spells)
    entity_actions = actions.get("entity_actions", [])
    lines.append(f"ENTITY ACTIONS: {len(entity_actions)} options")
    for i, atk in enumerate(entity_actions):
        name = atk.get("display_name", atk.get("template_name", "???"))
        can_afford = atk.get("can_afford", False)
        valid_targets = atk.get("valid_targets", [])
        num_targets = len(valid_targets)
        is_spell = atk.get("action_category") == "spell"
        cost_type = atk.get("cost_type", "actions")
        cost_label = {"actions": "action", "bonus_actions": "bonus", "extra_attacks": "extra attack", "reactions": "reaction", "movement": "movement"}.get(cost_type, cost_type)
        status = "READY" if can_afford and num_targets > 0 else "NO TARGETS" if num_targets == 0 else "NO ACTION"
        spell_tag = "[SPELL] " if is_spell else ""
        target_parts = [f"[{t.get('index', j)}]{t.get('target_name', '?')}" for j, t in enumerate(valid_targets)]
        targets_str = f" -> {', '.join(target_parts)}" if target_parts else ""
        lines.append(f"  [{i}] {spell_tag}{name} ({cost_label}) - {num_targets} targets ({status}){targets_str}")

    lines.append("")

    # Self actions (Dash, Dodge, Disengage, class features, self spells)
    self_actions = actions.get("self_actions", [])
    lines.append("SELF ACTIONS:")
    for action in self_actions:
        action_name = action.get("display_name", action.get("template_name", "???"))
        can_afford = action.get("can_afford", False)
        is_item = action.get("is_item_use", False)
        is_spell = action.get("action_category") == "spell"
        cost_type = action.get("cost_type", "actions")
        cost_amount = action.get("cost_amount", 1)
        cost_label = _format_cost_label(cost_type, cost_amount)
        status = "READY" if can_afford else "NO ACTION"
        tags = []
        if is_spell:
            tags.append("[SPELL]")
        if is_item:
            tags.append("[ITEM]")
        tag_str = " ".join(tags)
        if tag_str:
            tag_str = " " + tag_str
        lines.append(f"  {action_name} ({cost_label}): {status}{tag_str}")

    # Reactions/Handlers (private to this entity)
    handler_details = actions.get("handler_details", [])
    if handler_details:
        lines.append("")
        lines.append("REACTIONS:")
        for h in handler_details:
            name = h.get("name", "???")
            enabled = h.get("enabled", True)
            status = "[ON] " if enabled else "[OFF]"
            trigger = h.get("trigger_event", "")
            trigger_str = f" ({trigger})" if trigger else ""
            lines.append(f"  {status} {name}{trigger_str}")
        lines.append("  Toggle: toggle \"<name>\" on/off")

    # Object actions (Pick Up, Open Door, Attack Object)
    object_actions = actions.get("object_actions", [])
    if object_actions:
        lines.append("")
        lines.append("OBJECT ACTIONS:")
        for i, action in enumerate(object_actions):
            action_name = action.get("display_name", action.get("template_name", "???"))
            can_afford = action.get("can_afford", False)
            cost_type = action.get("cost_type", "actions")
            cost_amount = action.get("cost_amount", 1)
            cost_label = _format_cost_label(cost_type, cost_amount)
            valid_targets = action.get("valid_targets", [])
            status = "READY" if can_afford and valid_targets else "NO TARGETS"
            target_names = [t.get("target_name", "?") for t in valid_targets]
            targets_str = f" -> {', '.join(target_names)}" if target_names else ""
            lines.append(f"  [{i}] {action_name} ({cost_label}): {len(valid_targets)} targets ({status}){targets_str}")

    return "\n".join(lines)


def cmd_connect(client: APIClient) -> int:
    """Connect to the game by creating a session and joining."""
    print("Connecting to game...")

    # Create session
    try:
        session_result = client.create_session(player_type="claude", name="Claude")
        session_id = session_result.get("session_id")
        if not session_id:
            print("ERROR: No session_id returned from server")
            return 1
        print(f"Session created: {session_id[:8]}...")
    except Exception as e:
        print(f"ERROR: Failed to create session: {e}")
        return 1

    # Join game
    try:
        join_result = client.join_game()
        controlled = join_result.get("controlled_entities", [])
        if controlled:
            print(f"Joined game, controlling: {len(controlled)} entities")

            # Save session with ALL entities for future commands
            save_session(session_id, controlled)
            print(f"Session saved. Use other commands to play.")

            # Check if it's our turn
            ping_result = client.ping_session()
            if ping_result.get("is_my_turn"):
                print(">>> IT'S YOUR TURN! Use 'state' and 'actions' <<<")
            else:
                active_name = ping_result.get("active_entity_name", "???")
                print(f"Waiting for {active_name}'s turn...")

            return 0
        else:
            print("ERROR: No entities assigned. Is a game running?")
            return 1
    except Exception as e:
        print(f"ERROR: Failed to join game: {e}")
        return 1


def cmd_disconnect(_client: APIClient) -> int:
    """Disconnect from the game."""
    clear_session()
    print("Disconnected. Session cleared.")
    return 0


def cmd_state(client: APIClient) -> int:
    """Display current game state."""
    if not ensure_session(client):
        print("ERROR: Not connected. Run 'connect' first.")
        return 1

    state = client.get_state()
    if not state:
        print("ERROR: Could not get game state. Is the server running?")
        return 1

    # Get visibility data for subjective view
    visibility = client.get_visibility() or {}

    # Game status - get from encounter object
    encounter = state.get("encounter", {})
    active_uuid = encounter.get("current_entity_uuid")
    round_num = encounter.get("round_number", 1)

    entities = state.get("entities", [])
    active_name = "???"
    my_entity = None
    my_entity_uuid = client.current_entity_uuid
    controlled_uuids = getattr(client, '_controlled_entity_uuids', [])
    for e in entities:
        if e.get("uuid") == active_uuid:
            active_name = e.get("name", "???")
        if my_entity_uuid and e.get("uuid") == my_entity_uuid:
            my_entity = e

    # Build visible entity set and visible cells from the observer's perspective
    visible_entity_uuids: Optional[set] = None
    visible_cells: Optional[set] = None
    memory_cells: Optional[set] = None
    sense_modes: list = []
    if my_entity_uuid and my_entity_uuid in visibility:
        my_vis = visibility[my_entity_uuid]
        visible_entity_uuids = set(my_vis.get("visible_entities", []))
        # Always include all controlled entities
        visible_entity_uuids.update(controlled_uuids)
        visible_cells = set(
            tuple(c) for c in my_vis.get("visible_cells", [])
        )
        seen_cells = set(
            tuple(c) for c in my_vis.get("seen_cells", [])
        )
        memory_cells = seen_cells - visible_cells
        sense_modes = my_vis.get("sense_modes", [])

    # Check if it's my turn using session
    my_turn = is_my_turn(client)
    turn_indicator = ">>> MY TURN <<<" if my_turn else "(waiting)"

    print(f"ROUND {round_num} - {active_name}'s turn {turn_indicator}")

    # Show which of our entities is active (for multi-entity support)
    if my_entity:
        num_controlled = len(controlled_uuids)
        if num_controlled > 1:
            # List all controlled entities with active marker
            print(f"Controlling {num_controlled} entities (* = active):")
            for e in entities:
                if e.get("uuid") in controlled_uuids:
                    marker = ">>>" if e.get("uuid") == my_entity_uuid else "   "
                    print(f"  {marker} {e.get('name', '?')} ({e.get('hp', 0)}/{e.get('max_hp', 0)} HP)")
        else:
            print(f"I control: {my_entity.get('name', '???')}")
    print("")

    # Map (filtered by visibility)
    print(format_map(state, visible_entity_uuids, my_entity_uuid, visible_cells, memory_cells,
                     sense_modes=sense_modes))
    print("")

    # Entities (filtered by visibility, sorted by initiative)
    init_order = encounter.get("initiative_order")
    print(format_entities(entities, visible_entity_uuids, my_entity_uuid, controlled_uuids, init_order))

    # Show if it's my turn
    if my_turn:
        print("")
        print(">>> IT'S MY TURN - Use 'actions' to see options <<<")

    return 0


def cmd_entities(client: APIClient) -> int:
    """List all entities controlled by the session."""
    if not ensure_session(client):
        print("ERROR: Not connected. Run 'connect' first.")
        return 1

    try:
        resp = client.client.get(f"/session/{client.session_id}/entities")
        resp.raise_for_status()
        result = resp.json()
        entities = result.get("controlled_entities", [])

        if not entities:
            print("No entities controlled by this session.")
            return 0

        # Get the currently active entity
        active_uuid = client.current_entity_uuid

        print("CONTROLLED ENTITIES:")
        print(f"{'#':<3} {'Name':<15} {'Faction':<12} {'HP':<8} {'Position':<10} {'Status'}")
        print("-" * 65)

        for i, e in enumerate(entities):
            name = e.get("name", "???")
            faction = e.get("faction") or "(none)"
            hp = e.get("hp", 0)
            pos = e.get("position", [0, 0])
            pos_str = f"({pos[0]},{pos[1]})"
            e_uuid = e.get("uuid")
            status = ">>> ACTIVE" if e_uuid == active_uuid else ""
            print(f"{i:<3} {name:<15} {faction:<12} {hp:<8} {pos_str:<10} {status}")

        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


def cmd_actions(client: APIClient) -> int:
    """Display available actions for my entity."""
    if not ensure_session(client):
        print("ERROR: Not connected. Run 'connect' first.")
        return 1

    entity_uuid = client.current_entity_uuid
    if not entity_uuid:
        print("ERROR: No entity assigned")
        return 1

    # Get entity name
    state = client.get_state()
    entity_name = "???"
    if state:
        for e in state.get("entities", []):
            if e.get("uuid") == entity_uuid:
                entity_name = e.get("name", "???")
                break

    actions = client.get_available_actions(entity_uuid)
    if not actions:
        print("ERROR: Could not get available actions")
        return 1

    print(format_actions(actions, entity_name))
    return 0


def cmd_handlers(client: APIClient) -> int:
    """Display all handlers for my entity with enabled/disabled state."""
    if not ensure_session(client):
        print("ERROR: Not connected. Run 'connect' first.")
        return 1

    entity_uuid = client.current_entity_uuid
    if not entity_uuid:
        print("ERROR: No entity assigned")
        return 1

    try:
        data = client.get_handlers(entity_uuid)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    handlers = data.get("handlers", [])
    if not handlers:
        print("No handlers registered.")
        return 0

    print("Handlers:")
    for h in handlers:
        name = h.get("name", "???")
        enabled = h.get("enabled", True)
        status = "[ON] " if enabled else "[OFF]"
        trigger = h.get("trigger_event", "")
        trigger_str = f" ({trigger})" if trigger else ""
        print(f"  {status} {name}{trigger_str}")
    return 0


def cmd_toggle_handler(client: APIClient, handler_name: str, enabled: bool) -> int:
    """Toggle a handler on or off."""
    if not ensure_session(client):
        print("ERROR: Not connected. Run 'connect' first.")
        return 1

    entity_uuid = client.current_entity_uuid
    if not entity_uuid:
        print("ERROR: No entity assigned")
        return 1

    try:
        client.toggle_handler(handler_name, enabled, entity_uuid)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    state_str = "enabled" if enabled else "disabled"
    print(f"OK: {handler_name} {state_str}")
    return 0


def validate_my_turn(client: APIClient) -> bool:
    """Validate it's the agent's turn."""
    if not ensure_session(client):
        print("ERROR: Not connected. Run 'connect' first.")
        return False

    if not is_my_turn(client):
        print("ERROR: Not my turn")
        return False

    return True


def cmd_move(client: APIClient, x: int, y: int) -> int:
    """Move to position."""
    if not validate_my_turn(client):
        return 1

    try:
        result = client.move((x, y))
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    success = result.get("success", False)
    if success:
        event_data = result.get("event_data", {})
        end_pos = event_data.get("end", [x, y])
        print(f"OK: Moved to ({end_pos[0]},{end_pos[1]})")
        show_combat_log(result.get("combat_log_entries", []))
        show_action_result_status(result)
        show_inline_state(result, client)
        show_full_actions(result, client)
    else:
        message = result.get("message", "Unknown error")
        print(f"ERROR: {message}")
        return 1

    return 0


def cmd_position_action(client: APIClient, action_name: str, x: int, y: int) -> int:
    """Execute any position-based action by name (Move, Jump, etc.)."""
    if not validate_my_turn(client):
        return 1

    entity_uuid = client.current_entity_uuid
    if not entity_uuid:
        print("ERROR: No controlled entity")
        return 1

    actions = client.get_available_actions(entity_uuid)
    if not actions:
        print("ERROR: Could not get available actions")
        return 1

    position_actions = actions.get("position_actions", [])

    # Find action by name (case-insensitive)
    action = None
    for a in position_actions:
        if a.get("template_name", "").lower() == action_name.lower():
            action = a
            break

    if not action:
        available_names = [a.get("template_name", "?") for a in position_actions]
        if available_names:
            print(f"ERROR: No {action_name} action available. Position actions: {', '.join(available_names)}")
        else:
            movement = actions.get("remaining_movement", 0)
            print(f"ERROR: No {action_name} action available (remaining movement: {movement}ft). Run 'actions' to see options.")
        return 1

    if not action.get("can_afford", False):
        cost_type = action.get("cost_type", "movement")
        cost_label = {"movement": "movement", "bonus_actions": "bonus action", "actions": "action"}.get(cost_type, cost_type)
        movement = actions.get("remaining_movement", 0)
        print(f"ERROR: Cannot afford {action_name} (costs {cost_label}, remaining movement: {movement}ft)")
        return 1

    valid_targets = action.get("valid_targets", [])
    if not valid_targets:
        movement = actions.get("remaining_movement", 0)
        print(f"ERROR: No reachable positions for {action_name} (remaining movement: {movement}ft)")
        return 1

    # Find matching position in valid targets
    position = (x, y)
    for target in valid_targets:
        target_pos = target.get("position")
        if target_pos and tuple(target_pos) == position:
            try:
                result = client.execute_action(
                    action.get("template_name"),
                    target.get("index"),
                    entity_uuid
                )
            except Exception as e:
                print(f"ERROR: {e}")
                return 1

            success = result.get("success", False)
            if success:
                event_data = result.get("event_data", {})
                end_pos = event_data.get("end_position", event_data.get("end", [x, y]))
                print(f"OK: {action_name} to ({end_pos[0]},{end_pos[1]})")
                show_combat_log(result.get("combat_log_entries", []))
                show_action_result_status(result)
                show_inline_state(result, client)
                show_full_actions(result, client)
            else:
                message = result.get("message", "Unknown error")
                print(f"ERROR: {message}")
                return 1

            return 0

    # Position not in valid targets — show nearest options
    nearest = sorted(valid_targets, key=lambda t: abs(t.get("position", [0,0])[0] - x) + abs(t.get("position", [0,0])[1] - y))[:5]
    nearest_strs = [f"({t.get('position', [0,0])[0]},{t.get('position', [0,0])[1]})" for t in nearest]
    print(f"ERROR: ({x},{y}) not in range for {action_name}. {len(valid_targets)} valid positions. Nearest: {', '.join(nearest_strs)}")
    return 1


def cmd_attack(client: APIClient, action_index: int, target_index: int = 0) -> int:
    """Attack target by action index and optional target index."""
    if not validate_my_turn(client):
        return 1

    entity_uuid = client.current_entity_uuid

    # Get available actions to find attack action and target
    actions = client.get_available_actions(entity_uuid)
    if not actions:
        print("ERROR: Could not get available actions")
        return 1

    # entity_actions contains attacks (entity-targeting actions)
    entity_actions = actions.get("entity_actions", [])
    if not entity_actions:
        act = actions.get("actions_remaining", 0)
        bonus = actions.get("bonus_actions_remaining", 0)
        extra = actions.get("extra_attacks_remaining", 0)
        print(f"ERROR: No attack actions available (actions:{act}, bonus:{bonus}, extra attacks:{extra})")
        return 1

    if action_index < 0 or action_index >= len(entity_actions):
        names = [f"[{i}]{a.get('display_name', a.get('template_name', '?'))}" for i, a in enumerate(entity_actions)]
        print(f"ERROR: Invalid action index {action_index}. Available: {', '.join(names)}")
        return 1

    attack_info = entity_actions[action_index]
    template_name = attack_info.get("template_name", "Attack")
    display_name = attack_info.get("display_name", template_name)

    if not attack_info.get("can_afford", True):
        cost_type = attack_info.get("cost_type", "actions")
        cost_label = {"actions": "action", "bonus_actions": "bonus action", "extra_attacks": "extra attack"}.get(cost_type, cost_type)
        print(f"ERROR: Cannot afford {display_name} (costs {cost_label})")
        return 1

    valid_targets = attack_info.get("valid_targets", [])
    if not valid_targets:
        print(f"ERROR: No valid targets in range for {display_name}")
        return 1

    if target_index < 0 or target_index >= len(valid_targets):
        target_names = [f"[{i}]{t.get('target_name', '?')}" for i, t in enumerate(valid_targets)]
        print(f"ERROR: Invalid target {target_index} for {display_name}. Targets: {', '.join(target_names)}")
        return 1

    # valid_targets are now objects with target_uuid and index
    target_obj = valid_targets[target_index]
    target_uuid = target_obj.get("target_uuid", "")
    target_idx = target_obj.get("index", 0)

    # Get target name
    state = client.get_state()
    target_name = "???"
    if state:
        for e in state.get("entities", []):
            if e.get("uuid") == target_uuid:
                target_name = e.get("name", "???")
                break

    try:
        # Use execute_action with template_name and target index
        result = client.execute_action(template_name, target_idx)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    success = result.get("success", False)
    if success:
        print(f"OK: Attack vs {target_name}")
        show_combat_log(result.get("combat_log_entries", []))
        show_action_result_status(result)
        show_inline_state(result, client)
        show_full_actions(result, client)
    else:
        message = result.get("message", "Unknown error")
        print(f"ERROR: {message}")
        return 1

    return 0


def cmd_inspect(client: APIClient, x: int, y: int) -> int:
    """Inspect a tile at position (x, y)."""
    if not ensure_session(client):
        print("ERROR: Not connected. Run 'connect' first.")
        return 1

    try:
        tile = client.get_tile_info(x, y)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    name = tile.get("name", "???")
    walkable = tile.get("walkable", False)
    cost = tile.get("walking_cost", 1)
    light_name = tile.get("light_level_name", "???")
    light_level = tile.get("light_level", 0)
    illum_count = tile.get("illumination_count", 0)

    print(f"Tile ({x},{y}): {name}")
    print(f"  Walkable: {walkable}, Cost: {cost}x")
    print(f"  Light: {light_name} ({light_level}) - {illum_count} source(s)")

    conditions = tile.get("conditions", [])
    if conditions:
        print(f"  Conditions: {', '.join(conditions)}")

    entities = tile.get("entities", [])
    if entities:
        for ent in entities:
            status = "DEAD" if ent.get("is_dead") else f"{ent.get('hp', 0)} HP"
            print(f"  Entity: {ent.get('name', '?')} ({status})")

    objects = tile.get("objects", [])
    if objects:
        for obj in objects:
            tags = []
            if obj.get("is_pickable"):
                tags.append("pickable")
            if obj.get("is_usable"):
                tags.append("usable")
            tag_str = f" ({', '.join(tags)})" if tags else ""
            print(f"  Object: {obj.get('name', '?')}{tag_str}")

    return 0


def cmd_self_action(client: APIClient, action_name: str) -> int:
    """Execute any self-targeting action by name (case-insensitive partial match)."""
    if not validate_my_turn(client):
        return 1

    entity_uuid = client.current_entity_uuid
    if not entity_uuid:
        print("ERROR: No controlled entity")
        return 1

    actions = client.get_available_actions(entity_uuid)
    if not actions:
        print("ERROR: Could not get available actions")
        return 1

    self_actions = actions.get("self_actions", [])
    action_name_lower = action_name.lower()

    # Try exact match first, then partial match
    match = None
    for a in self_actions:
        display = a.get("display_name", a.get("template_name", ""))
        if display.lower() == action_name_lower:
            match = a
            break
    if not match:
        for a in self_actions:
            display = a.get("display_name", a.get("template_name", ""))
            if action_name_lower in display.lower():
                match = a
                break

    if not match:
        available = [f"{a.get('display_name', a.get('template_name', ''))} ({'READY' if a.get('can_afford') else 'NO RESOURCE'})" for a in self_actions]
        print(f"ERROR: No self-action matching '{action_name}'")
        if available:
            print(f"  Available: {', '.join(available)}")
        else:
            print(f"  No self-actions available")
        return 1

    if not match.get("can_afford", False):
        cost_type = match.get("cost_type", "actions")
        cost_label = {"actions": "action", "bonus_actions": "bonus action", "reactions": "reaction"}.get(cost_type, cost_type)
        print(f"ERROR: Cannot afford {match.get('display_name', action_name)} (costs {cost_label})")
        return 1

    template_name = match.get("template_name", "")
    try:
        result = client.execute_action(template_name, 0, entity_uuid)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    success = result.get("success", False)
    if success:
        print(f"OK: {match.get('display_name', action_name)}")
        show_combat_log(result.get("combat_log_entries", []))
        show_action_result_status(result)
        show_inline_state(result, client)
        show_full_actions(result, client)
    else:
        message = result.get("message", "Unknown error")
        print(f"ERROR: {message}")
        return 1

    return 0


def cmd_use(client: APIClient, target_arg: str) -> int:
    """Execute an object/environment action by name or index."""
    if not validate_my_turn(client):
        return 1

    entity_uuid = client.current_entity_uuid
    if not entity_uuid:
        print("ERROR: No controlled entity")
        return 1

    actions = client.get_available_actions(entity_uuid)
    if not actions:
        print("ERROR: Could not get available actions")
        return 1

    # Collect usable actions: object_actions + item-use self_actions
    usable_actions = list(actions.get("object_actions", []))
    for a in actions.get("self_actions", []):
        if a.get("is_item_use", False):
            usable_actions.append(a)

    if not usable_actions:
        print("ERROR: No object/item actions available (need to be near an interactable object or have usable items)")
        return 1

    # Try numeric index first
    try:
        idx = int(target_arg)
        if idx < 0 or idx >= len(usable_actions):
            print(f"ERROR: Index {idx} out of range. Valid: 0-{len(usable_actions)-1}")
            return 1
        action = usable_actions[idx]
    except ValueError:
        # String match against display_name or target names
        target_arg_lower = target_arg.lower()
        action = None
        for a in usable_actions:
            display = a.get("display_name", a.get("template_name", ""))
            if target_arg_lower in display.lower():
                action = a
                break
        if not action:
            # Search target names
            for a in usable_actions:
                for t in a.get("valid_targets", []):
                    if target_arg_lower in t.get("target_name", "").lower():
                        action = a
                        break
                if action:
                    break
        if not action:
            print(f"ERROR: No object/item action matching '{target_arg}'")
            for i, a in enumerate(usable_actions):
                targets = [t.get("target_name", "?") for t in a.get("valid_targets", [])]
                print(f"  [{i}] {a.get('display_name', '?')}: {', '.join(targets)}")
            return 1

    if not action.get("can_afford", False):
        cost_type = action.get("cost_type", "actions")
        cost_label = {"actions": "action", "bonus_actions": "bonus action"}.get(cost_type, cost_type)
        print(f"ERROR: Cannot afford {action.get('display_name', '?')} (costs {cost_label})")
        return 1

    valid_targets = action.get("valid_targets", [])
    if not valid_targets:
        print(f"ERROR: No valid targets for {action.get('display_name', '?')} (may need to be closer)")
        return 1

    template_name = action.get("template_name", "")
    target_idx = valid_targets[0].get("index", 0)

    try:
        result = client.execute_action(template_name, target_idx, entity_uuid)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    success = result.get("success", False)
    if success:
        target_name = valid_targets[0].get("target_name", "object")
        print(f"OK: {action.get('display_name', '?')} -> {target_name}")
        show_combat_log(result.get("combat_log_entries", []))
        show_action_result_status(result)
        show_inline_state(result, client)
        show_full_actions(result, client)
    else:
        message = result.get("message", "Unknown error")
        print(f"ERROR: {message}")
        return 1

    return 0


def cmd_cast(client: APIClient, args: List[str]) -> int:
    """Cast a spell. Usage: cast <spell_name> [target_index | X Y]"""
    if not validate_my_turn(client):
        return 1

    entity_uuid = client.current_entity_uuid
    if not entity_uuid:
        print("ERROR: No controlled entity")
        return 1

    if not args:
        print("Usage: cast <spell_name> [target_index | X Y]")
        return 1

    actions = client.get_available_actions(entity_uuid)
    if not actions:
        print("ERROR: Could not get available actions")
        return 1

    # Parse spell name: could be multi-word, so try longest match first
    # Try consuming words from the front until we find a match
    spell_match = None
    spell_source = None  # "entity", "position", "self"
    remaining_args: List[str] = []

    # Collect all spells from all action categories
    all_spells: List[Tuple[dict, str]] = []
    for a in actions.get("entity_actions", []):
        if a.get("action_category") == "spell":
            all_spells.append((a, "entity"))
    for a in actions.get("position_actions", []):
        if a.get("action_category") == "spell":
            all_spells.append((a, "position"))
    for a in actions.get("self_actions", []):
        if a.get("action_category") == "spell":
            all_spells.append((a, "self"))

    if not all_spells:
        print("ERROR: No spells available")
        return 1

    # Try matching spell name (greedy: try longest first)
    for num_words in range(len(args), 0, -1):
        spell_name_try = " ".join(args[:num_words]).lower()
        for spell, source in all_spells:
            display = spell.get("display_name", spell.get("template_name", ""))
            if display.lower() == spell_name_try:
                spell_match = spell
                spell_source = source
                remaining_args = args[num_words:]
                break
        if spell_match:
            break

    # Fallback: partial match
    if not spell_match:
        for num_words in range(len(args), 0, -1):
            spell_name_try = " ".join(args[:num_words]).lower()
            for spell, source in all_spells:
                display = spell.get("display_name", spell.get("template_name", ""))
                if spell_name_try in display.lower():
                    spell_match = spell
                    spell_source = source
                    remaining_args = args[num_words:]
                    break
            if spell_match:
                break

    if not spell_match or not spell_source:
        available = [f"{s.get('display_name', s.get('template_name', ''))} ({'READY' if s.get('can_afford') else 'NO SLOT/ACTION'})" for s, _ in all_spells]
        print(f"ERROR: No spell matching '{' '.join(args)}'")
        if available:
            print(f"  Available: {', '.join(available)}")
        else:
            print(f"  No spells available (check spell slots and action economy)")
        return 1

    if not spell_match.get("can_afford", False):
        cost_type = spell_match.get("cost_type", "actions")
        cost_label = {"actions": "action", "bonus_actions": "bonus action"}.get(cost_type, cost_type)
        spell_slots = actions.get("spell_slots", {})
        slots_str = ""
        if spell_slots:
            slot_parts = [f"L{lvl}:{info['current']}/{info['max']}" for lvl, info in sorted(spell_slots.items())]
            slots_str = f" Slots: {' '.join(slot_parts)}"
        print(f"ERROR: Cannot afford {spell_match.get('display_name', '?')} (costs {cost_label}).{slots_str}")
        return 1

    template_name = spell_match.get("template_name", "")
    spell_display = spell_match.get("display_name", template_name)
    valid_targets = spell_match.get("valid_targets", [])

    # Route based on spell source type
    if spell_source == "self":
        # Self-targeting spell, no args needed
        try:
            result = client.execute_action(template_name, 0, entity_uuid)
        except Exception as e:
            print(f"ERROR: {e}")
            return 1

    elif spell_source == "entity":
        # Entity-targeting spell, needs target index
        if not valid_targets:
            print(f"ERROR: No valid targets for {spell_display}")
            return 1

        if not remaining_args:
            # Show available targets
            print(f"TARGETS for {spell_display}:")
            for i, t in enumerate(valid_targets):
                print(f"  [{i}] {t.get('target_name', '?')}")
            print(f"Usage: cast {spell_display} <target_index>")
            return 1

        try:
            target_num = int(remaining_args[0])
        except ValueError:
            print(f"ERROR: Target must be a number. Usage: cast {spell_display} <target_index>")
            return 1

        if target_num < 0 or target_num >= len(valid_targets):
            print(f"ERROR: Target index {target_num} out of range. Valid: 0-{len(valid_targets)-1}")
            return 1

        target = valid_targets[target_num]
        try:
            result = client.execute_action(template_name, target.get("index", 0), entity_uuid)
        except Exception as e:
            print(f"ERROR: {e}")
            return 1

    elif spell_source == "position":
        # Position-targeting spell (AoE), needs X Y
        if not valid_targets:
            print(f"ERROR: No valid positions for {spell_display}")
            return 1

        if len(remaining_args) < 2:
            # Show sample positions
            print(f"POSITIONS for {spell_display}: {len(valid_targets)} options")
            sample = valid_targets[:8]
            for t in sample:
                pos = t.get("position", [0, 0])
                extras = []
                if t.get("affected_count"):
                    extras.append(f"hits {t['affected_count']}")
                if t.get("affected_entity_names"):
                    extras.append(f"targets: {', '.join(t['affected_entity_names'])}")
                extra_str = f" ({', '.join(extras)})" if extras else ""
                print(f"  ({pos[0]},{pos[1]}){extra_str}")
            if len(valid_targets) > 8:
                print(f"  ... and {len(valid_targets) - 8} more")
            print(f"Usage: cast {spell_display} X Y")
            return 1

        try:
            x, y = int(remaining_args[0]), int(remaining_args[1])
        except ValueError:
            print(f"ERROR: Position must be numbers. Usage: cast {spell_display} X Y")
            return 1

        # Find matching position in prefiltered valid_targets
        target = None
        for t in valid_targets:
            pos = t.get("position", [0, 0])
            if pos[0] == x and pos[1] == y:
                target = t
                break

        if target:
            try:
                result = client.execute_action(template_name, target.get("index", 0), entity_uuid)
            except Exception as e:
                print(f"ERROR: {e}")
                return 1
        else:
            # Position not in prefiltered list — try direct position execution
            # (D&D 5e allows targeting any visible point in range, even empty ground)
            try:
                result = client.execute_position_action(template_name, (x, y), entity_uuid)
            except Exception as e:
                print(f"ERROR: Position ({x},{y}) not valid for {spell_display}: {e}")
                return 1
    else:
        print(f"ERROR: Unknown spell source type")
        return 1

    success = result.get("success", False)
    if success:
        print(f"OK: {spell_display}")
        show_combat_log(result.get("combat_log_entries", []))
        show_action_result_status(result)
        show_inline_state(result, client)
        show_full_actions(result, client)
    else:
        message = result.get("message", "Unknown error")
        print(f"ERROR: {message}")
        return 1

    return 0


def cmd_end(client: APIClient) -> int:
    """End turn."""
    if not ensure_session(client):
        print("ERROR: Not connected.")
        return 1
    # Check if encounter already ended (don't error, just acknowledge)
    state = client.get_state()
    encounter = state.get("encounter", {}) if state else {}
    if encounter.get("state") == "ended" or not encounter.get("encounter_active", True):
        print("OK: Encounter already ended. No turn to end.")
        return 0
    if not is_my_turn(client):
        print("ERROR: Not my turn")
        return 1

    try:
        result = client.end_turn()
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    status = result.get("status", "???")
    print(f"OK: Turn ended")
    print(f"  Status: {status}")

    # Show next turn info
    entity_name = result.get("entity_name", "???")
    round_num = result.get("round", 1)
    print(f"  Now: Round {round_num}, {entity_name}'s turn")

    # Show AI actions that occurred during opponent turns (filtered)
    ai_actions = result.get("ai_actions", [])
    if ai_actions:
        from cli.log_filter import filter_combat_log as _filter_log
        controlled = getattr(client, '_controlled_entity_uuids', [])
        vis_set, _, _, _ = get_visibility_data(client)
        filtered_ai = _filter_log(ai_actions, controlled, vis_set)
        if filtered_ai:
            print("")
            print("OPPONENT ACTIONS:")
            show_combat_log(filtered_ai, label="AI")

    if status == "encounter_ended":
        print("")
        print(">>> ENCOUNTER ENDED <<<")

    return 0


def cmd_wait(client: APIClient) -> int:
    """Check if it's the agent's turn."""
    if not ensure_session(client):
        print("ERROR: Not connected. Run 'connect' first.")
        return 1

    if is_my_turn(client):
        print("MY_TURN")
        return 0
    else:
        state = client.get_state()
        if state:
            encounter = state.get("encounter", {})
            active_uuid = encounter.get("current_entity_uuid")
            for e in state.get("entities", []):
                if e.get("uuid") == active_uuid:
                    print(f"WAITING: {e.get('name', '???')}'s turn")
                    return 1
        print("WAITING")
        return 1


def cmd_watch(client: APIClient, poll_interval: float = 2.0) -> int:
    """
    Watch the game and wait until it's the agent's turn.

    Polls the server every poll_interval seconds. When it becomes the agent's
    turn, outputs the unified turn prompt (same format as orchestrated mode),
    then exits.

    Use Ctrl+C to interrupt.
    """
    import time
    from cli.prompt_builder import build_turn_prompt
    from cli.log_filter import filter_combat_log

    if not ensure_session(client):
        print("ERROR: Not connected. Run 'connect' first.")
        return 1

    print(f"Watching game... (polling every {poll_interval}s, Ctrl+C to stop)")
    print("")

    # Track combat log for opponent actions
    combat_log_index = 0
    try:
        log_data = client.get_combat_log()
        combat_log_index = log_data.get("total", 0)
    except Exception:
        pass

    last_active_name = None
    controlled_uuids = getattr(client, '_controlled_entity_uuids', [])

    while True:
        try:
            # Get state first to check for game end conditions
            state = client.get_state()
            if state:
                encounter = state.get("encounter", {})
                entities = state.get("entities", [])

                # Check if encounter ended (multiple ways to detect)
                encounter_active = encounter.get("encounter_active", True)
                alive = [e for e in entities if not e.get("is_dead", False) and e.get("hp", 0) > 0]

                # Encounter is over if: explicitly ended, or only 1 combatant alive
                if not encounter_active or len(alive) <= 1:
                    print("")
                    print("=" * 60)
                    print("ENCOUNTER ENDED")
                    print("=" * 60)

                    # Show final state
                    for e in entities:
                        hp = e.get("hp", 0)
                        max_hp = e.get("max_hp", 0)
                        name = e.get("name", "???")
                        status = "DEAD" if hp <= 0 else "ALIVE"
                        print(f"  {name}: {hp}/{max_hp} HP - {status}")

                    if len(alive) == 1:
                        print(f"\nWINNER: {alive[0].get('name', '???')}")
                    elif len(alive) == 0:
                        print("\nEVERYONE IS DEAD")

                    return 0

            # Check if it's my turn
            if is_my_turn(client):
                my_entity_uuid = client.current_entity_uuid
                my_entity_name = "???"
                if state:
                    for e in state.get("entities", []):
                        if e.get("uuid") == my_entity_uuid:
                            my_entity_name = e.get("name", "???")
                            break

                # Get visibility
                vis_set, vis_cells, mem_cells, vis_sense_modes = get_visibility_data(client)

                # Get combat log entries since last seen
                log_data = client.get_combat_log(since=combat_log_index)
                new_entries = log_data.get("entries", [])
                combat_log_index = log_data.get("total", combat_log_index)

                # Filter combat log (temporal + identity)
                filtered = filter_combat_log(new_entries, controlled_uuids, vis_set)
                log_lines: List[str] = []
                for entry in filtered:
                    log_lines.extend(format_combat_log_entry(entry))

                # Get available actions
                actions = {}
                try:
                    actions = client.get_available_actions() or {}
                except Exception:
                    pass

                # Build and output unified prompt
                enc = state.get("encounter", {}) if state else {}
                round_num = enc.get("round_number", 1)
                ents = state.get("entities", []) if state else []
                init_order = enc.get("initiative_order")
                pos_actions = actions.get("position_actions", [])

                prompt = build_turn_prompt(
                    entity_name=my_entity_name,
                    faction="",
                    round_number=round_num,
                    notebook_content="",
                    combat_log_text="\n".join(log_lines),
                    entity_table_text=format_entities(
                        ents, vis_set, my_entity_uuid, controlled_uuids, init_order,
                    ),
                    map_text=format_map(
                        state or {}, vis_set, my_entity_uuid, vis_cells, mem_cells, pos_actions,
                        sense_modes=vis_sense_modes,
                    ),
                    action_text=format_actions(actions, my_entity_name),
                )

                print("")
                print("=" * 60)
                num_controlled = len(controlled_uuids)
                if num_controlled > 1:
                    print(f">>> MY TURN: {my_entity_name} ({num_controlled} entities total) <<<")
                else:
                    print(f">>> MY TURN: {my_entity_name} <<<")
                print("=" * 60)
                print("")
                print(prompt)
                print("")

                print("Ready to act. Commands:")
                print("  move X Y | jump X Y | attack N | cast <spell> [N|X Y]")
                print("  self <name> | dash | dodge | disengage | use <name|N>")
                print("  inspect X Y | end")
                return 0

            # Poll combat log for opponent actions (filtered)
            try:
                vis_set_poll, _, _, _ = get_visibility_data(client)
                log_data = client.get_combat_log(since=combat_log_index)
                new_entries = log_data.get("entries", [])
                if new_entries:
                    filtered = filter_combat_log(new_entries, controlled_uuids, vis_set_poll)
                    if filtered:
                        show_combat_log(filtered, label="GAME")
                combat_log_index = log_data.get("total", combat_log_index)
            except Exception:
                pass

            # Show whose turn it is (only when it changes)
            if state:
                encounter = state.get("encounter", {})
                active_uuid = encounter.get("current_entity_uuid")
                for e in state.get("entities", []):
                    if e.get("uuid") == active_uuid:
                        active_name = e.get("name", "???")
                        if active_name != last_active_name:
                            print(f"[TURN] {active_name}'s turn...")
                            last_active_name = active_name
                        break

            time.sleep(poll_interval)

        except KeyboardInterrupt:
            print("\nStopped watching.")
            return 0
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(poll_interval)


def main():
    global SESSION_FILE

    # Parse --token flag (must come before command)
    # Usage: python -m cli.agent --token hero move 5 3
    if len(sys.argv) > 2 and sys.argv[1] == "--token":
        token = sys.argv[2]
        SESSION_FILE = f"/tmp/dnd_game/{token}_session.txt"
        # Remove --token <value> from argv so command parsing works unchanged
        sys.argv = [sys.argv[0]] + sys.argv[3:]

    # Position-based commands that route to cmd_position_action
    POSITION_COMMANDS = ["move", "jump"]

    if len(sys.argv) < 2:
        print("Usage: python -m cli.agent <command> [args]")
        print("")
        print("Connection:")
        print("  connect              Connect to game (create session, join)")
        print("  disconnect           Disconnect from game (clear session)")
        print("  wait                 Check if it's my turn (returns 0 if yes)")
        print("  watch                Wait until my turn, show state+actions (blocks)")
        print("")
        print("Game State:")
        print("  state                Show game state (map, entities, whose turn)")
        print("  actions              Show available actions for my entity")
        print("  entities             List all entities controlled by this session")
        print("  inspect X Y          Inspect tile at position (X, Y)")
        print("")
        print("Position Actions:")
        print("  move X Y             Move to position (X, Y)")
        print("  jump X Y             Jump to position (X, Y)")
        print("")
        print("Combat:")
        print("  attack N             Attack target by index (from entity_actions)")
        print("  cast <spell> [N|X Y] Cast a spell (entity target N, or position X Y)")
        print("")
        print("Self Actions:")
        print("  self <name>          Execute any self-action by name")
        print("  dash                 Shortcut for 'self Dash'")
        print("  dodge                Shortcut for 'self Dodge'")
        print("  disengage            Shortcut for 'self Disengage'")
        print("")
        print("Items & Environment:")
        print("  use <name|N>         Use object action by name or index")
        print("")
        print("Reactions/Handlers:")
        print("  handlers             Show all handlers with enabled/disabled state")
        print("  toggle <name> on/off Toggle a handler on or off")
        print("")
        print("Turn:")
        print("  end                  End turn")
        return 1

    client = APIClient()
    command = sys.argv[1].lower()

    try:
        if command == "connect":
            return cmd_connect(client)

        elif command == "disconnect":
            return cmd_disconnect(client)

        elif command == "state":
            return cmd_state(client)

        elif command == "actions":
            return cmd_actions(client)

        elif command == "entities":
            return cmd_entities(client)

        elif command == "inspect":
            if len(sys.argv) < 4:
                print("Usage: python -m cli.agent inspect X Y")
                return 1
            x = int(sys.argv[2])
            y = int(sys.argv[3])
            return cmd_inspect(client, x, y)

        # Generic position action routing
        elif command in POSITION_COMMANDS:
            if len(sys.argv) < 4:
                print(f"Usage: python -m cli.agent {command} X Y")
                return 1
            x = int(sys.argv[2])
            y = int(sys.argv[3])
            action_name = command.capitalize()
            return cmd_position_action(client, action_name, x, y)

        elif command == "attack":
            if len(sys.argv) < 3:
                print("Usage: python -m cli.agent attack N [T]")
                return 1
            action_index = int(sys.argv[2])
            target_index = int(sys.argv[3]) if len(sys.argv) > 3 else 0
            return cmd_attack(client, action_index, target_index)

        elif command == "cast":
            return cmd_cast(client, sys.argv[2:])

        elif command == "self":
            if len(sys.argv) < 3:
                print("Usage: python -m cli.agent self <action_name>")
                return 1
            action_name = " ".join(sys.argv[2:])
            return cmd_self_action(client, action_name)

        elif command == "use":
            if len(sys.argv) < 3:
                print("Usage: python -m cli.agent use <name|index>")
                return 1
            target_arg = " ".join(sys.argv[2:])
            return cmd_use(client, target_arg)

        elif command in ["dash", "dodge", "disengage"]:
            # Shortcuts that route to self-action
            return cmd_self_action(client, command.capitalize())

        elif command == "handlers":
            return cmd_handlers(client)

        elif command == "toggle":
            if len(sys.argv) < 4:
                print("Usage: python -m cli.agent toggle <handler_name> on/off")
                return 1
            handler_name = sys.argv[2]
            toggle_state = sys.argv[3].lower()
            if toggle_state not in ("on", "off"):
                print("ERROR: toggle state must be 'on' or 'off'")
                return 1
            return cmd_toggle_handler(client, handler_name, toggle_state == "on")

        elif command == "end":
            return cmd_end(client)

        elif command == "wait":
            return cmd_wait(client)

        elif command == "watch":
            return cmd_watch(client)

        else:
            print(f"Unknown command: {command}")
            print("Run 'python -m cli.agent' for help")
            return 1

    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
