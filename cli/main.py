"""
Main entry point for the D&D Engine CLI.

Usage:
    python -m cli play          # Start interactive combat (vs AI)
    python -m cli playpvp       # Start PvP combat (vs Claude)
    python -m cli play --host localhost --port 8000
"""

import typer
from typing import Dict, List, Optional
import time
import httpx

from cli.api_client import APIClient
from cli.commands import parse_command, execute_command, GameState, MetaCommand
from cli.action_model import ShortcutRegistry
from cli import display

# Module-level shortcut registry for session-stable shortcuts
_shortcut_registry: Optional[ShortcutRegistry] = None


def get_shortcut_registry() -> ShortcutRegistry:
    """Get or create the session shortcut registry."""
    global _shortcut_registry
    if _shortcut_registry is None:
        _shortcut_registry = ShortcutRegistry()
    return _shortcut_registry


def reset_shortcut_registry():
    """Reset the shortcut registry (for new games)."""
    global _shortcut_registry
    _shortcut_registry = ShortcutRegistry()


def safe_execute_action(
    client: APIClient,
    template_name: str,
    target_index: int,
    extra_target_uuids: Optional[List[str]] = None
) -> Optional[dict]:
    """Execute action with error handling. Returns result or None on error.

    Args:
        client: API client
        template_name: Action template name
        target_index: Primary target index
        extra_target_uuids: Additional target UUIDs for multi-target spells (Magic Missile)
    """
    try:
        return client.execute_action(template_name, target_index, extra_target_uuids=extra_target_uuids)
    except httpx.HTTPStatusError as e:
        # Extract error detail from response if available
        try:
            json_response = e.response.json()
            if isinstance(json_response, dict):
                detail = json_response.get("detail", str(e))
            else:
                detail = str(e)
        except Exception:
            detail = str(e)
        display.set_output([f"Action failed: {detail}"])
        return None
    except Exception as e:
        display.set_output([f"Action failed: {e}"])
        return None


def try_execute_dynamic_self_action(cmd_str: str, client: APIClient, state: GameState) -> Optional[str]:
    """
    Try to execute a dynamic self-action using the shortcut registry.

    Returns:
        "refresh" if action was executed
        None if command wasn't a self-action (fall through to execute_command)
    """
    if not state.actions:
        return None

    registry = get_shortcut_registry()
    action = state.actions.get_self_action_by_command(cmd_str.strip().lower(), registry)

    if action:
        # Execute the self-action
        result = safe_execute_action(client, action.template_name, 0)
        if result is None:
            return "refresh"  # Error already shown by safe_execute_action
        display.show_action_result(result, state.turn.get("current_entity_name", "You"))
        state.add_to_log(f"{state.turn.get('current_entity_name', 'You')} uses {action.display_name}.")
        return "refresh"

    return None  # Not a self-action, fall through


def try_execute_dynamic_other_entity_action(cmd_str: str, args: List[str], client: APIClient, state: GameState) -> Optional[str]:
    """
    Try to execute a dynamic other_entity action (Shove, etc.) using the shortcut registry.

    Returns:
        "refresh" if action was executed or showing targets
        "encounter_ended" if encounter ended
        None if command wasn't an other_entity action
    """
    if not state.actions:
        return None

    registry = get_shortcut_registry()
    cmd = cmd_str.strip().lower().split()[0] if cmd_str.strip() else ""
    action = state.actions.get_other_entity_action_by_command(cmd, registry)

    if not action:
        return None

    # No target index - show valid targets
    if len(args) < 1:
        targets = action.valid_targets
        shortcut = registry.get_or_create_shortcut(action.template_name)
        display.set_output([
            f"Valid {action.display_name} targets:",
            *[f"  [{i+1}] {t.target_name or 'Unknown'}" for i, t in enumerate(targets)],
            f"Enter '{shortcut} N' to {action.display_name.lower()} target N"
        ])
        return "refresh"

    # Parse target index
    try:
        target_num = int(args[0])
    except ValueError:
        shortcut = registry.get_or_create_shortcut(action.template_name)
        display.set_output([f"Invalid target. Usage: {shortcut} N"])
        return "refresh"

    # Find target
    result = state.actions.get_other_entity_target(action.template_name, target_num)
    if not result:
        total = len(action.valid_targets)
        display.set_output([f"Invalid target. Choose 1-{total}."])
        return "refresh"

    action_obj, target = result

    # Execute
    api_result = safe_execute_action(client, action_obj.template_name, target.index)
    if api_result is None:
        return "refresh"  # Error already shown by safe_execute_action
    display.show_action_result(api_result, state.turn.get("current_entity_name", "You"))
    state.add_to_log(f"{state.turn.get('current_entity_name', 'You')} uses {action.display_name} on {target.target_name}.")

    if api_result.get("encounter_ended"):
        return "encounter_ended"
    return "refresh"


def try_execute_dynamic_position_action(cmd_str: str, args: List[str], client: APIClient, state: GameState) -> Optional[str]:
    """
    Try to execute a dynamic position-action using the shortcut registry.
    Handles Move, Jump, and any future position-based actions.

    Returns:
        "refresh" if action was executed or showing positions
        "encounter_ended" if encounter ended
        None if command wasn't a position-action
    """
    if not state.actions:
        return None

    registry = get_shortcut_registry()
    cmd = cmd_str.strip().lower().split()[0] if cmd_str.strip() else ""
    action = state.actions.get_position_action_by_command(cmd, registry)

    if not action:
        return None

    # No coordinates - show valid positions
    if len(args) < 2:
        positions = [t.position for t in action.valid_targets if t.position]
        state.valid_move_positions = positions
        shortcut = registry.get_or_create_shortcut(action.template_name)
        display.set_output([
            f"Valid {action.display_name.lower()} positions shown on map (*)",
            f"{len(positions)} positions available",
            f"Enter '{shortcut} X Y' to {action.display_name.lower()} to position (X, Y)"
        ])
        return "refresh"

    # Parse coordinates
    try:
        x, y = int(args[0]), int(args[1])
    except ValueError:
        shortcut = registry.get_or_create_shortcut(action.template_name)
        display.set_output([f"Invalid position. Usage: {shortcut} X Y"])
        return "refresh"

    # Execute
    position = (x, y)
    for target in action.valid_targets:
        if target.position == position:
            result = safe_execute_action(client, action.template_name, target.index)
            if result is None:
                return "refresh"  # Error already shown by safe_execute_action
            display.show_action_result(result, state.turn.get("current_entity_name", "You"))
            state.add_to_log(f"{state.turn.get('current_entity_name', 'You')} {action.display_name.lower()}s to ({x}, {y}).")

            event_data = result.get("event_data", {})
            path = event_data.get("path", [])
            state.last_movement_path = [tuple(p) for p in path] if path else None

            # Handle opportunity attacks
            triggered = result.get("triggered_reactions", [])
            for reaction in triggered:
                if reaction.get("type") == "opportunity_attack":
                    attacker = reaction.get("attacker", "Unknown")
                    outcome = (reaction.get("outcome") or "miss").lower()
                    total_damage = reaction.get("total_damage", 0)
                    if outcome in ("hit", "crit"):
                        state.add_to_log(f"(OA) {attacker} hit for {total_damage} damage!")
                    else:
                        state.add_to_log(f"(OA) {attacker} missed.")

            if result.get("encounter_ended"):
                return "encounter_ended"
            return "refresh"

    shortcut = registry.get_or_create_shortcut(action.template_name)
    display.set_output([f"Position ({x}, {y}) is not valid. Type '{shortcut}' to see valid positions."])
    return "refresh"


def try_execute_dynamic_spell_action(cmd_str: str, args: List[str], client: APIClient, state: GameState) -> Optional[str]:
    """
    Try to execute a dynamic spell action using the shortcut registry.
    Handles spells of all target types: position_aoe, entity, multi_entity, self.

    Supports preview syntax: "fb ? X Y" to show affected targets without casting.

    Returns:
        "refresh" if action was executed or showing info
        "encounter_ended" if encounter ended
        None if command wasn't a spell action
    """
    if not state.actions:
        return None

    registry = get_shortcut_registry()
    cmd = cmd_str.strip().lower().split()[0] if cmd_str.strip() else ""
    action = state.actions.get_spell_action_by_command(cmd, registry)

    if not action:
        return None

    shortcut = registry.get_or_create_shortcut(action.template_name)
    target_type = action.target_type

    # Check for preview mode ("?" in args)
    preview_mode = "?" in args
    if preview_mode:
        args = [a for a in args if a != "?"]

    # === Position AoE spells (Fireball, Lightning Bolt, etc.) ===
    if target_type == "position_aoe":
        # No coordinates - show valid positions
        if len(args) < 2:
            positions = [t.position for t in action.valid_targets if t.position]
            state.valid_move_positions = positions
            display.set_output([
                f"Valid {action.display_name} positions shown on map (*)",
                f"{len(positions)} positions available",
                f"Usage: '{shortcut} X Y' to cast, '{shortcut} ? X Y' to preview"
            ])
            return "refresh"

        # Parse coordinates
        try:
            x, y = int(args[0]), int(args[1])
        except ValueError:
            display.set_output([f"Invalid position. Usage: {shortcut} X Y"])
            return "refresh"

        # Find the target for this position
        position = (x, y)
        for target in action.valid_targets:
            if target.position == position:
                if preview_mode:
                    # Store AoE positions for map highlighting
                    state.valid_move_positions = target.affected_positions or []

                    # Store preview info for "!" command
                    state.last_preview = {
                        "template_name": action.template_name,
                        "target_index": target.index,
                        "display_name": action.display_name,
                        "position": (x, y)
                    }

                    # Build preview message for output panel
                    affected = target.affected_entity_names or []
                    count = target.affected_count or len(affected)
                    if count > 0:
                        lines = [f"{action.display_name} at ({x}, {y}) would affect {count} targets:"]
                        for name in affected:
                            lines.append(f"  • {name}")
                        lines.append("[dim]Type '!' to cast[/dim]")
                    else:
                        lines = [f"{action.display_name} at ({x}, {y}) would affect no targets"]
                        lines.append("[dim]Type '!' to cast anyway[/dim]")

                    display.set_output(lines)
                    # Use "preview" to refresh display but keep output text
                    return "preview"

                # Execute the spell
                result = safe_execute_action(client, action.template_name, target.index)
                if result is None:
                    return "refresh"
                display.show_action_result(result, state.turn.get("current_entity_name", "You"))
                affected_count = target.affected_count or 0
                state.add_to_log(f"{state.turn.get('current_entity_name', 'You')} casts {action.display_name} at ({x}, {y}), affecting {affected_count} targets.")

                if result.get("encounter_ended"):
                    return "encounter_ended"
                return "refresh"

        display.set_output([f"Position ({x}, {y}) is not valid. Type '{shortcut}' to see valid positions."])
        return "refresh"

    # === Entity-targeting spells (Fire Bolt, Magic Missile, etc.) ===
    elif target_type in ("entity", "multi_entity"):
        # No target - show valid targets
        if len(args) < 1:
            targets = action.valid_targets
            if target_type == "multi_entity":
                # Multi-target spells (Magic Missile) can have multiple targets
                display.set_output([
                    f"Valid {action.display_name} targets:",
                    *[f"  [{i+1}] {t.target_name or 'Unknown'}" for i, t in enumerate(targets)],
                    f"Enter '{shortcut} N [N2 N3...]' to cast (e.g., '{shortcut} 1 2 3' splits projectiles)"
                ])
            else:
                display.set_output([
                    f"Valid {action.display_name} targets:",
                    *[f"  [{i+1}] {t.target_name or 'Unknown'}" for i, t in enumerate(targets)],
                    f"Enter '{shortcut} N' to cast at target N"
                ])
            return "refresh"

        # Parse all target indices
        target_indices: List[int] = []
        for arg in args:
            try:
                target_indices.append(int(arg))
            except ValueError:
                display.set_output([f"Invalid target '{arg}'. Usage: {shortcut} N [N2 N3...]"])
                return "refresh"

        if not target_indices:
            display.set_output([f"No targets specified. Usage: {shortcut} N [N2 N3...]"])
            return "refresh"

        # For multi_entity spells with multiple indices, use get_spell_targets
        if target_type == "multi_entity" and len(target_indices) > 1:
            result = state.actions.get_spell_targets(action.template_name, target_indices)
            if not result:
                total = len(action.valid_targets)
                display.set_output([f"Invalid targets. Choose from 1-{total}."])
                return "refresh"

            spell_action, targets = result
            primary_target = targets[0]
            extra_target_uuids = [t.target_uuid for t in targets[1:] if t.target_uuid]

            # Execute with extra targets
            api_result = safe_execute_action(
                client,
                spell_action.template_name,
                primary_target.index,
                extra_target_uuids=extra_target_uuids
            )
            if api_result is None:
                return "refresh"
            display.show_action_result(api_result, state.turn.get("current_entity_name", "You"))
            target_names = [t.target_name or "Unknown" for t in targets]
            state.add_to_log(f"{state.turn.get('current_entity_name', 'You')} casts {action.display_name} at {', '.join(target_names)}.")

            if api_result.get("encounter_ended"):
                return "encounter_ended"
            return "refresh"

        # Single target (or single index for multi_entity spell - all projectiles at one target)
        result = state.actions.get_spell_target(action.template_name, target_indices[0])
        if not result:
            total = len(action.valid_targets)
            display.set_output([f"Invalid target. Choose 1-{total}."])
            return "refresh"

        spell_action, target = result

        # Execute
        api_result = safe_execute_action(client, spell_action.template_name, target.index)
        if api_result is None:
            return "refresh"
        display.show_action_result(api_result, state.turn.get("current_entity_name", "You"))
        state.add_to_log(f"{state.turn.get('current_entity_name', 'You')} casts {action.display_name} at {target.target_name}.")

        if api_result.get("encounter_ended"):
            return "encounter_ended"
        return "refresh"

    # === Self-targeting spells (Mage Armor, etc.) ===
    else:  # target_type == "self" or other
        result = safe_execute_action(client, action.template_name, 0)
        if result is None:
            return "refresh"
        display.show_action_result(result, state.turn.get("current_entity_name", "You"))
        state.add_to_log(f"{state.turn.get('current_entity_name', 'You')} casts {action.display_name}.")

        if result.get("encounter_ended"):
            return "encounter_ended"
        return "refresh"


def try_execute_dynamic_item_use_action(cmd_str: str, args: List[str], client: APIClient, state: GameState) -> Optional[str]:
    """
    Try to execute a dynamic item use action (potions, weapon coats, etc.).

    Returns:
        "refresh" if action was executed or showing targets
        "encounter_ended" if encounter ended
        None if command wasn't an item use action
    """
    if not state.actions:
        return None

    registry = get_shortcut_registry()
    cmd = cmd_str.strip().lower().split()[0] if cmd_str.strip() else ""
    action = state.actions.get_item_use_action_by_command(cmd, registry)

    if not action:
        return None

    shortcut = registry.get_or_create_shortcut(action.display_name)

    # Self-targeting items (potions, etc.)
    if action.target_type == "self":
        result = safe_execute_action(client, action.template_name, 0)
        if result is None:
            return "refresh"
        display.show_action_result(result, state.turn.get("current_entity_name", "You"))
        state.add_to_log(f"{state.turn.get('current_entity_name', 'You')} uses {action.display_name}.")
        if result.get("encounter_ended"):
            return "encounter_ended"
        return "refresh"

    # Entity-targeting items (weapon coats applied to target, etc.)
    if len(args) < 1:
        targets = action.valid_targets
        display.set_output([
            f"Valid {action.display_name} targets:",
            *[f"  [{i+1}] {t.target_name or 'Unknown'}" for i, t in enumerate(targets)],
            f"Enter '{shortcut} N' to use on target N"
        ])
        return "refresh"

    try:
        target_num = int(args[0])
    except ValueError:
        display.set_output([f"Invalid target. Usage: {shortcut} N"])
        return "refresh"

    result = state.actions.get_item_use_target(action.display_name, target_num)
    if not result:
        total = len(action.valid_targets)
        display.set_output([f"Invalid target. Choose 1-{total}."])
        return "refresh"

    action_obj, target = result
    api_result = safe_execute_action(client, action_obj.template_name, target.index)
    if api_result is None:
        return "refresh"
    display.show_action_result(api_result, state.turn.get("current_entity_name", "You"))
    state.add_to_log(f"{state.turn.get('current_entity_name', 'You')} uses {action.display_name} on {target.target_name}.")

    if api_result.get("encounter_ended"):
        return "encounter_ended"
    return "refresh"


def try_execute_dynamic_object_action(cmd_str: str, args: List[str], client: APIClient, state: GameState) -> Optional[str]:
    """
    Try to execute a dynamic object action (Pick Up, Attack Object, Pull Lever, etc.).

    Returns:
        "refresh" if action was executed or showing targets
        "encounter_ended" if encounter ended
        None if command wasn't an object action
    """
    if not state.actions:
        return None

    registry = get_shortcut_registry()
    cmd = cmd_str.strip().lower().split()[0] if cmd_str.strip() else ""
    action = state.actions.get_object_action_by_command(cmd, registry)

    if not action:
        return None

    shortcut = registry.get_or_create_shortcut(action.template_name)

    # Self-targeting object actions (Pull Lever, etc.)
    if action.target_type == "self":
        result = safe_execute_action(client, action.template_name, 0)
        if result is None:
            return "refresh"
        display.show_action_result(result, state.turn.get("current_entity_name", "You"))
        state.add_to_log(f"{state.turn.get('current_entity_name', 'You')} uses {action.display_name}.")
        if result.get("encounter_ended"):
            return "encounter_ended"
        return "refresh"

    # Entity/object-targeting actions (Pick Up, Attack Object)
    if len(args) < 1:
        targets = action.valid_targets
        display.set_output([
            f"Valid {action.display_name} targets:",
            *[f"  [{i+1}] {t.target_name or 'Unknown'}" for i, t in enumerate(targets)],
            f"Enter '{shortcut} N' to target N"
        ])
        return "refresh"

    try:
        target_num = int(args[0])
    except ValueError:
        display.set_output([f"Invalid target. Usage: {shortcut} N"])
        return "refresh"

    result = state.actions.get_object_action_target(action.template_name, target_num)
    if not result:
        total = len(action.valid_targets)
        display.set_output([f"Invalid target. Choose 1-{total}."])
        return "refresh"

    action_obj, target = result
    api_result = safe_execute_action(client, action_obj.template_name, target.index)
    if api_result is None:
        return "refresh"
    display.show_action_result(api_result, state.turn.get("current_entity_name", "You"))
    state.add_to_log(f"{state.turn.get('current_entity_name', 'You')} uses {action.display_name} on {target.target_name}.")

    if api_result.get("encounter_ended"):
        return "encounter_ended"
    return "refresh"


def prompt_with_connection_poll(_client: APIClient, pvp_mode: bool = False, poll_interval: float = 2.0) -> str:
    """
    Prompt for input while polling connection status in PvP mode.

    Returns the user's input string.

    Note: select.select() doesn't work on Windows/WSL stdin, so we use
    simple input for now. Connection status polling can be added via
    a background thread if needed.
    """
    # Use normal input for all modes - select.select() doesn't work on Windows/WSL
    return display.prompt_command()


app = typer.Typer(
    name="dnd-cli",
    help="Nethack-style CLI for D&D Engine combat."
)


def refresh_state(client: APIClient, state: GameState, clear_path: bool = False) -> bool:
    """
    Refresh game state from server.

    Returns True if game should continue, False if encounter ended.
    """
    try:
        # Get full state
        full_state = client.get_state()
        state.update_from_state(full_state)

        # Get turn info
        state.turn = client.get_current_turn()

        # Get visibility data
        state.visibility = client.get_visibility()

        # Clear movement path on refresh (unless we want to keep showing it)
        if clear_path:
            state.last_movement_path = None

        # Check if encounter ended
        if not state.turn.get("encounter_active", False):
            return False

        # Get available actions if it's human turn
        if state.turn.get("is_human_turn", False):
            actions_data = client.get_available_actions()
            state.update_actions(actions_data)
            # Register actions with session-stable shortcut registry
            if state.actions:
                state.actions.register_actions(get_shortcut_registry())
            state.shortcut_registry = get_shortcut_registry()
        else:
            state.actions = None
            state.actions_raw = {}

        return True

    except Exception as e:
        display.show_error(f"Failed to refresh state: {e}")
        return False


def render_display(client: APIClient, state: GameState, my_entity_uuid: Optional[str] = None, pvp_mode: bool = False):
    """Render the full display.

    Args:
        client: API client
        state: Current game state
        my_entity_uuid: UUID of the entity THIS player controls (for @ symbol).
                       Falls back to client.current_entity_uuid if not provided.
        pvp_mode: If True, check and update Claude's connection status
    """
    # Use provided UUID or fall back to client's tracked entity
    player_uuid = my_entity_uuid or client.current_entity_uuid

    # Determine if it's MY turn (for display)
    active_uuid = state.turn.get("current_entity_uuid")
    is_my_turn = (active_uuid == player_uuid) if player_uuid else state.turn.get("is_human_turn", False)

    # Update connection status in PvP mode
    if pvp_mode:
        try:
            pvp_status = client.get_pvp_status()
            claude_connected = pvp_status.get("claude_connected", False)
            display.set_session_info(claude_connected=claude_connected)
        except Exception as e:
            # Log but don't fail render
            display.console.print(f"[dim red]PvP status error: {e}[/dim red]")

    # Use the new full-screen render with session-stable shortcuts
    display.render_full_screen(
        grid=state.grid,
        entities=state.entities,
        turn=state.turn,
        current_entity_uuid=player_uuid,
        actions=state.actions_raw if is_my_turn else None,
        visibility=state.visibility,
        movement_path=state.last_movement_path,
        valid_positions=state.valid_move_positions,
        is_my_turn=is_my_turn,
        shortcut_registry=get_shortcut_registry(),
        floor_objects=state.floor_objects,
    )

    # Clear transient display state after showing
    state.last_movement_path = None
    state.valid_move_positions = None


def wait_for_ai_turn(client: APIClient, state: GameState) -> bool:
    """
    Wait while AI takes its turn.

    Returns True if game should continue, False if encounter ended.
    """
    display.show_info("AI is taking their turn...")

    # Poll until it's human turn again or encounter ends
    max_wait = 30  # seconds
    poll_interval = 0.5
    elapsed = 0

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        try:
            state.turn = client.get_current_turn()

            if not state.turn.get("encounter_active", False):
                return False

            if state.turn.get("is_human_turn", False):
                return True

        except Exception as e:
            # Log but continue polling - transient errors are OK
            display.console.print(f"[dim red]AI poll error: {e}[/dim red]")
            continue

    display.show_error("Timeout waiting for AI turn")
    return False


def wait_for_opponent_turn(client: APIClient, state: GameState, hero_uuid: str) -> bool:
    """
    Wait while opponent (Claude) takes their turn in PvP mode.

    Polls the server-side combat log for new entries and updates display.
    Returns True if game should continue, False if encounter ended.
    """
    poll_interval = 0.5
    last_connected = False
    shown_waiting = False

    # Track combat log position
    combat_log_index = client.get_combat_log().get("total", 0)

    # Track entity state for detecting visual changes
    last_positions = {e["uuid"]: tuple(e["position"]) for e in state.entities}
    last_hp = {e["uuid"]: e.get("hp", 0) for e in state.entities}

    while True:
        try:
            # Poll combat log FIRST to capture all opponent actions
            log_response = client.get_combat_log(since=combat_log_index)
            new_entries = log_response.get("entries", [])
            need_redraw = False

            for entry in new_entries:
                # Show rich display for opponent actions
                display.show_opponent_action(entry)
                # Add to local combat log (CombatLogEntry uses "summary")
                summary = entry.get("summary", "")
                if summary:
                    state.add_to_log(summary)
                need_redraw = True

            # Update combat log index to total (new format doesn't have per-entry index)
            combat_log_index = log_response.get("total", combat_log_index)

            # Check PvP status AFTER processing combat log
            response = httpx.get(f"{client.base_url}/pvp/status", timeout=5.0)
            if response.status_code == 200:
                pvp_status = response.json()

                claude_connected = pvp_status.get("claude_connected", False)
                is_hero_turn = pvp_status.get("is_hero_turn", False)
                _ = pvp_status.get("current_turn", "???")

                # Check if it's now hero's turn (after processing opponent actions)
                if is_hero_turn:
                    display.console.print("[green]Your turn![/green]")
                    return True

                # Show Claude connection status changes
                if claude_connected and not last_connected:
                    display.set_session_info(claude_connected=True)
                    last_connected = True
                elif not claude_connected and not shown_waiting:
                    display.set_session_info(claude_connected=False)
                    shown_waiting = True

            # Check for visual state changes (position, HP)
            full_state = client.get_state()
            if full_state:
                new_entities = full_state.get("entities", [])

                for e in new_entities:
                    uuid = e["uuid"]
                    new_pos = tuple(e["position"])
                    new_hp = e.get("hp", 0)

                    if last_positions.get(uuid) != new_pos:
                        last_positions[uuid] = new_pos
                        need_redraw = True

                    if last_hp.get(uuid) != new_hp:
                        last_hp[uuid] = new_hp
                        need_redraw = True

                # Redraw map if anything changed
                if need_redraw:
                    state.update_from_state(full_state)
                    state.visibility = client.get_visibility()
                    state.turn = client.get_current_turn()
                    render_display(client, state, my_entity_uuid=hero_uuid, pvp_mode=True)
                    display.console.print("[dim]Opponent's turn...[/dim]")

            # Check encounter status
            state.turn = client.get_current_turn()
            if not state.turn.get("encounter_active", False):
                display.console.print("")
                return False

        except Exception as e:
            # Log error but don't break loop - transient failures are OK
            # This helps debug server hangs/errors
            display.console.print(f"[dim red]Poll error: {e}[/dim red]")
            time.sleep(0.5)
            continue

        time.sleep(poll_interval)


def game_loop(client: APIClient, initial_ai_path: Optional[list] = None, pvp_mode: bool = False, hero_uuid: Optional[str] = None, initial_log_index: int = 0):
    """Main game loop."""
    # Reset shortcut registry for new game session
    reset_shortcut_registry()

    # Enter alternate screen for clean full-screen display
    display.enter_alternate_screen()

    try:
        state = GameState()

        # Track which entity THIS player controls
        my_entity_uuid = hero_uuid or client.current_entity_uuid

        # Set initial AI path if provided (from AI turn before our first turn)
        if initial_ai_path:
            state.last_movement_path = initial_ai_path

        # Initial state refresh
        if not refresh_state(client, state):
            display.show_info("Encounter has ended or not started.")
            display.console.print("[dim]Press Enter to exit...[/dim]")
            input()
            return

        # Fetch and process any combat log entries from before we joined
        # (e.g., if opponent moved first before our turn)
        # Start from initial_log_index to avoid duplicates with ai_actions already shown
        try:
            log_response = client.get_combat_log(since=initial_log_index)
            for entry in log_response.get("entries", []):
                display.show_opponent_action(entry)
        except Exception:
            pass  # Not critical if this fails

        # Clear history and save initial snapshot
        display.clear_history()
        display.save_turn_snapshot(state.turn, state.entities, state.grid)

        need_redraw = True  # Track if we need to redraw the display

        while True:
            # Render display only when needed
            if need_redraw:
                render_display(client, state, my_entity_uuid=my_entity_uuid, pvp_mode=pvp_mode)

                # Check whose turn
                if pvp_mode and hero_uuid:
                    # PvP mode: check if it's MY (hero's) turn
                    active_uuid = state.turn.get("current_entity_uuid")
                    is_my_turn = active_uuid == hero_uuid

                    if not is_my_turn:
                        # Opponent's turn - wait for Claude
                        if not wait_for_opponent_turn(client, state, hero_uuid):
                            break
                        # Refresh and continue
                        if not refresh_state(client, state):
                            break
                        # Save snapshot after opponent's turn
                        display.save_turn_snapshot(state.turn, state.entities, state.grid)
                        continue
                elif not state.turn.get("is_human_turn", False):
                    # AI turn - wait for it to complete
                    if not wait_for_ai_turn(client, state):
                        # Encounter ended
                        break
                    # Refresh and continue
                    if not refresh_state(client, state):
                        break
                    # Save snapshot after AI turn
                    display.save_turn_snapshot(state.turn, state.entities, state.grid)
                    continue

                # Human turn - show available actions summary based on economy
                hints = []
                if state.actions:
                    if state.actions.can_move:
                        hints.append(f"Move:{state.actions.remaining_movement}ft")
                    if state.actions.can_attack:
                        hints.append("Attack")
                    # Dynamic self-action hints using registry
                    registry = get_shortcut_registry()
                    for act in state.actions.self_actions:
                        if act.can_afford:
                            shortcut = registry.get_or_create_shortcut(act.template_name)
                            hints.append(f"{act.display_name}[{shortcut}]")
                hints.append("End")

                display.show_info(f"Actions: {', '.join(hints)} | ? for help")

            need_redraw = True  # Default to redraw next iteration

            # Get command (with connection status polling in PvP mode)
            cmd_str = prompt_with_connection_poll(client, pvp_mode=pvp_mode)
            cmd = parse_command(cmd_str)

            # Handle "la" (list actions) command
            if cmd.command == "la":
                panel = display.render_all_actions(get_shortcut_registry(), state.actions)
                display.console.print(panel)
                need_redraw = False
                continue

            # Handle "!" to execute last preview
            if cmd_str.strip() == "!":
                if state.last_preview:
                    preview = state.last_preview
                    result = safe_execute_action(client, preview["template_name"], preview["target_index"])
                    state.last_preview = None  # Clear after use
                    if result is None:
                        continue
                    display.show_action_result(result, state.turn.get("current_entity_name", "You"))
                    pos = preview["position"]
                    state.add_to_log(f"{state.turn.get('current_entity_name', 'You')} casts {preview['display_name']} at {pos}.")
                    if result.get("encounter_ended"):
                        refresh_state(client, state)
                        break
                    if not refresh_state(client, state):
                        break
                    display.clear_output()
                    continue
                else:
                    display.set_output(["No preview to execute. Use '?' to preview first (e.g., 'fb ? 5 3')"])
                    continue

            # Clear preview when doing any other action
            state.last_preview = None

            # Position actions (Move, Jump) - ONLY path, no fallback
            result = try_execute_dynamic_position_action(cmd_str, cmd.args, client, state)

            # Spell actions (Fireball, Fire Bolt, scroll spells, etc.) - all target types
            if result is None:
                result = try_execute_dynamic_spell_action(cmd_str, cmd.args, client, state)

            # Item use actions (potions, weapon coats, etc.)
            if result is None:
                result = try_execute_dynamic_item_use_action(cmd_str, cmd.args, client, state)

            # Object actions (Pick Up, Attack Object, Pull Lever)
            if result is None:
                result = try_execute_dynamic_object_action(cmd_str, cmd.args, client, state)

            # Other entity-targeting actions (Shove, etc.) - ONLY path, no fallback
            if result is None:
                result = try_execute_dynamic_other_entity_action(cmd_str, cmd.args, client, state)

            # Self actions (Dash, Dodge, etc.) - ONLY path, no fallback
            if result is None:
                result = try_execute_dynamic_self_action(cmd_str, client, state)

            # Attack and End only (NOT a fallback - these are different command types)
            if result is None:
                result = execute_command(cmd, client, state)

            if result == "quit":
                display.show_info("Goodbye!")
                break
            elif result == "encounter_ended":
                # Refresh state to get final HP values before showing end screen
                refresh_state(client, state)
                break
            elif result == "refresh":
                # Refresh state after action
                if not refresh_state(client, state):
                    break
                # Clear output after successful action (unless it was just showing info)
                display.clear_output()
                # Save snapshot after player action
                display.save_turn_snapshot(state.turn, state.entities, state.grid)
            elif result == "preview":
                # Like refresh but keep output text visible (for spell previews)
                # Don't refresh state - just redraw with current positions/output
                pass  # need_redraw stays True, so display will render with positions and output
            elif result is None:
                # Command handled itself (e.g., showing help, targets, positions)
                # Don't redraw - let user see the output and enter another command
                need_redraw = False

        # Show final state with full display (including combat log)
        # Save final snapshot for history
        display.save_turn_snapshot(state.turn, state.entities, state.grid)

        # Determine winner message using faction system
        alive = [e for e in state.entities if not e.get("is_dead", False)]
        factions_alive: Dict[str, List[str]] = {}
        for e in alive:
            faction = e.get("faction", "unknown")
            if faction not in factions_alive:
                factions_alive[faction] = []
            factions_alive[faction].append(e["name"])

        if len(factions_alive) == 1:
            # One faction wins
            faction_name = list(factions_alive.keys())[0]
            winners = factions_alive[faction_name]
            if len(winners) == 1:
                winner_msg = f"[bold green]*** {winners[0]} WINS! ***[/bold green]"
            else:
                winner_msg = f"[bold green]*** {faction_name.upper()} FACTION WINS! ({', '.join(winners)}) ***[/bold green]"
        elif len(factions_alive) == 0:
            winner_msg = "[bold red]*** EVERYONE IS DEAD ***[/bold red]"
        else:
            winner_msg = "[bold yellow]*** ENCOUNTER ENDED ***[/bold yellow]"

        # End-game loop: show final state and allow history navigation
        viewing_history = False
        while True:
            # Render appropriate view
            if viewing_history:
                snapshot = display.get_current_snapshot()
                if snapshot:
                    display.render_history_snapshot(snapshot)
            else:
                render_display(client, state, my_entity_uuid=my_entity_uuid, pvp_mode=pvp_mode)

            # Show winner and instructions
            display.console.print(f"\n{winner_msg}")
            display.console.print("[dim]History: pt/nt/ft/ct | Enter or q to exit[/dim]")

            # Get command
            cmd_str = display.prompt_command()
            cmd = parse_command(cmd_str)

            # Handle history navigation or quit
            if cmd.command == "quit" or cmd_str == "":
                break
            elif cmd.command == MetaCommand.PREV_TURN.value:
                if display.goto_previous_turn():
                    viewing_history = True
            elif cmd.command == MetaCommand.NEXT_TURN.value:
                if not display.goto_next_turn():
                    display.goto_current_turn()
                    viewing_history = False
                else:
                    viewing_history = True
            elif cmd.command == MetaCommand.FIRST_TURN.value:
                if display.goto_first_turn():
                    viewing_history = True
            elif cmd.command == MetaCommand.CURRENT_TURN.value:
                display.goto_current_turn()
                viewing_history = False

    finally:
        # Always exit alternate screen mode
        display.exit_alternate_screen()


@app.command()
def play(
    character_class: str = typer.Argument("fighter", help="Character class: fighter, barbarian, or sorcerer"),
    host: str = typer.Option("localhost", "--host", "-h", help="Server hostname"),
    port: int = typer.Option(8000, "--port", "-p", help="Server port"),
):
    """
    Start an interactive combat session.

    Connects to the D&D Engine server and starts a human-controlled combat.
    Use 'fighter' for a L5 dual-wield DEX Fighter, 'barbarian' for a L5 Berserker,
    or 'sorcerer' for a L5 Sorcerer with AoE spells (Fireball, Lightning Bolt, etc.).
    """
    base_url = f"http://{host}:{port}"
    display.console.print(f"[cyan]Connecting to {base_url}...[/cyan]")

    client = APIClient(base_url=base_url)

    try:
        # Prompt user before starting
        display.console.print(f"[green]Connected to server![/green]")
        display.console.print("[dim]Press Enter to begin combat...[/dim]")
        input()

        # NOW start the game (this rolls initiative and may run AI turn first)
        display.console.print(f"[cyan]Creating {character_class.title()} and rolling initiative...[/cyan]")
        display.reset_seen_tiles()  # Clear fog of war memory from previous game
        result = client.start_human_game(character_class=character_class)
        hero_uuid = result.get("hero_uuid")

        # Create session and join game
        display.console.print("[cyan]Creating session...[/cyan]")
        client.create_session(player_type="human", name="Player")
        join_result = client.join_game(entity_uuids=[hero_uuid] if hero_uuid else None)
        display.console.print(f"[green]Joined as: {join_result.get('message')}[/green]")

        entity_name = result.get("entity_name", "Unknown")
        display.console.print(f"[green]You control: {entity_name}[/green]")

        # Get initial combat log index (AI actions already in log)
        # game_loop will fetch from this index, so no duplicates
        initial_log_index = result.get("new_log_since", 0)

        # Check for AI movement path in ai_actions (CombatLogEntry structure)
        ai_actions = result.get("ai_actions", [])
        initial_ai_path = None
        for action in ai_actions:
            if action.get("entry_type") == "movement":
                path = action.get("data", {}).get("path")
                if path:
                    initial_ai_path = [tuple(p) for p in path]
                    break

        # Run the game loop
        game_loop(client, initial_ai_path=initial_ai_path, initial_log_index=initial_log_index)

    except Exception as e:
        display.show_error(f"Connection failed: {e}")
        display.show_info(f"Make sure the server is running: python -m server.event_server")
        raise typer.Exit(1)

    finally:
        client.close()


@app.command()
def playpvp(
    character_class: str = typer.Argument("fighter", help="Character class: fighter, barbarian, or sorcerer"),
    host: str = typer.Option("localhost", "--host", "-h", help="Server hostname"),
    port: int = typer.Option(8000, "--port", "-p", help="Server port"),
):
    """
    Start a PvP combat session (User vs Claude).

    You control the Hero, Claude controls the Skeletons via agent CLI.
    Both players take turns manually - no auto-AI.
    Use 'fighter' for a L5 dual-wield DEX Fighter, 'barbarian' for a L5 Berserker,
    or 'sorcerer' for a L5 Sorcerer with AoE spells.
    """
    base_url = f"http://{host}:{port}"
    display.console.print(f"[cyan]Connecting to {base_url}...[/cyan]")

    client = APIClient(base_url=base_url)

    try:
        # Prompt user before starting
        display.console.print(f"[green]Connected to server![/green]")
        display.console.print("[bold yellow]PvP MODE: You (Hero) vs Claude (Skeleton)[/bold yellow]")
        display.console.print("[dim]Press Enter to begin combat...[/dim]")
        input()

        # Start PvP game
        display.console.print(f"[cyan]Creating {character_class.title()} and starting PvP match...[/cyan]")
        display.reset_seen_tiles()  # Clear fog of war memory from previous game
        result = client.start_pvp_game(character_class=character_class)

        hero_uuid = result.get("hero_uuid")
        _ = result.get("skeleton_uuid")

        # Create session and join game
        display.console.print("[cyan]Creating session...[/cyan]")
        client.create_session(player_type="human", name="Player")
        join_result = client.join_game(entity_uuids=[hero_uuid] if hero_uuid else None)
        display.console.print(f"[green]Joined: {join_result.get('message')}[/green]")

        # Get first turn info
        turn_info = client.get_current_turn()
        entity_name = turn_info.get("current_entity_name", "Unknown")

        display.console.print(f"[green]You control: Hero[/green]")
        display.console.print(f"[red]Claude controls: Skeleton[/red]")
        display.console.print(f"[cyan]First turn: {entity_name}[/cyan]")
        display.console.print("[dim]Waiting for Claude to connect...[/dim]")

        # Set session info for header display
        display.set_session_info(
            pvp_mode=True,
            hero_connected=True,
            claude_connected=False
        )

        # Run the game loop in PvP mode
        game_loop(client, pvp_mode=True, hero_uuid=hero_uuid)

    except Exception as e:
        display.show_error(f"Connection failed: {e}")
        display.show_info(f"Make sure the server is running: python -m server.event_server")
        raise typer.Exit(1)

    finally:
        client.close()


@app.command()
def status(
    host: str = typer.Option("localhost", "--host", "-h", help="Server hostname"),
    port: int = typer.Option(8000, "--port", "-p", help="Server port"),
):
    """
    Check server status without starting a game.
    """
    base_url = f"http://{host}:{port}"
    client = APIClient(base_url=base_url)

    try:
        status = client.get_simulation_status()
        display.console.print(f"[green]Server is running[/green]")
        display.console.print(f"  Encounter active: {status.get('encounter_active', False)}")
        display.console.print(f"  Paused: {status.get('paused', True)}")
    except Exception as e:
        display.show_error(f"Cannot connect to server: {e}")
        raise typer.Exit(1)
    finally:
        client.close()


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
