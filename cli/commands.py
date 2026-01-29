"""
Command parsing and execution.

This module handles parsing user input into commands and executing them.
Commands are dynamically validated against available actions rather than
a hardcoded enum.
"""

from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum

from cli.api_client import APIClient
from cli.action_model import AvailableActionsState
from cli import display


# =============================================================================
# Meta Commands (not action-based)
# =============================================================================

class MetaCommand(Enum):
    """Meta commands that aren't game actions."""
    STATUS = "status"
    ACTIONS = "actions"
    MAP = "map"
    HELP = "help"
    QUIT = "quit"
    LIST_ACTIONS = "la"
    # History navigation
    PREV_TURN = "pt"
    NEXT_TURN = "nt"
    CURRENT_TURN = "ct"
    FIRST_TURN = "ft"


# Command aliases
# NOTE: Self-action shortcuts (d, o, i, sw, as, etc.) are dynamically managed
# by ShortcutRegistry - do NOT add them here as hardcoded aliases.
# Position action shortcuts (m, j) are ALSO managed by ShortcutRegistry.
# DO NOT add position shortcuts here - they must go through the registry.
ALIASES: Dict[str, str] = {
    # Entity actions
    "a": "attack",
    "e": "end",
    # Meta aliases
    "s": "status",
    "?": "help",
    "h": "help",
    "q": "quit",
    "exit": "quit",
    "la": "la",  # list actions
    "list": "la",
    # History navigation
    "pt": "pt",
    "nt": "nt",
    "ct": "ct",
    "ft": "ft",
    "prev": "pt",
    "next": "nt",
    "current": "ct",
    "first": "ft",
}


@dataclass
class ParsedCommand:
    """A parsed command with type classification."""
    command: str          # Normalized command name
    args: List[str]       # Command arguments
    raw: str              # Original input
    is_meta: bool = False # True if this is a meta command (not a game action)

    @property
    def is_action(self) -> bool:
        """True if this is a game action command."""
        return not self.is_meta


def parse_command(input_str: str, actions: Optional[AvailableActionsState] = None) -> ParsedCommand:
    """
    Parse a command string into a ParsedCommand.

    Args:
        input_str: Raw user input
        actions: Available actions (for validation, optional)

    Returns:
        ParsedCommand with normalized command and args
    """
    parts = input_str.strip().lower().split()
    if not parts:
        return ParsedCommand(command="unknown", args=[], raw=input_str, is_meta=True)

    cmd = parts[0]
    args = parts[1:]

    # Apply aliases
    cmd = ALIASES.get(cmd, cmd)

    # Check if meta command
    is_meta = False
    try:
        MetaCommand(cmd)
        is_meta = True
    except ValueError:
        pass

    return ParsedCommand(command=cmd, args=args, raw=input_str, is_meta=is_meta)


def get_valid_commands(actions: Optional[AvailableActionsState] = None) -> Set[str]:
    """
    Get set of valid commands based on available actions.

    Args:
        actions: Available actions state

    Returns:
        Set of valid command names
    """
    # Meta commands are always valid
    valid: Set[str] = {m.value for m in MetaCommand}
    valid.add("end")  # End turn is always available

    if actions:
        valid.update(actions.get_valid_commands())

    return valid


# =============================================================================
# GameState (tracks CLI state)
# =============================================================================

class GameState:
    """Holds current game state for the CLI."""

    def __init__(self):
        self.grid: Dict[str, Any] = {}
        self.entities: List[Dict[str, Any]] = []
        self.turn: Dict[str, Any] = {}
        self.actions: Optional[AvailableActionsState] = None
        self.actions_raw: Dict[str, Any] = {}  # Raw server response for display
        self.combat_log: List[str] = []
        self.visibility: Dict[str, Any] = {}
        self.last_movement_path: Optional[List[Tuple[int, int]]] = None
        self.valid_move_positions: Optional[List[Tuple[int, int]]] = None

    def update_from_state(self, state: Dict[str, Any]):
        """Update from /state response."""
        self.grid = state.get("grid", {})
        self.entities = state.get("entities", [])

    def update_actions(self, actions_data: Dict[str, Any]):
        """Update available actions from server response."""
        self.actions_raw = actions_data
        self.actions = AvailableActionsState.from_server(actions_data)

    def add_to_log(self, message: str):
        """Add a message to the combat log."""
        self.combat_log.append(message)
        # Keep last 20 messages
        if len(self.combat_log) > 20:
            self.combat_log = self.combat_log[-20:]

    @property
    def player_entity_name(self) -> str:
        """Get the current player's entity name."""
        return self.turn.get("current_entity_name", "You")


# =============================================================================
# Command Execution (Meta Commands)
# =============================================================================

def execute_meta_command(
    cmd: ParsedCommand,
    client: APIClient,
    state: GameState
) -> Optional[str]:
    """
    Execute a meta command (not a game action).

    Returns:
        "quit" - user wants to quit
        "refresh" - refresh display
        None - command handled, no refresh needed
    """
    try:
        if cmd.command == MetaCommand.QUIT.value:
            return "quit"

        elif cmd.command == MetaCommand.HELP.value:
            display.show_help()
            return None

        elif cmd.command == MetaCommand.STATUS.value:
            display.show_turn_info(state.turn, state.entities)
            return None

        elif cmd.command == MetaCommand.ACTIONS.value:
            display.show_available_actions(state.actions_raw, state.entities)
            return None

        elif cmd.command == MetaCommand.MAP.value:
            return "refresh"

        # History navigation
        elif cmd.command == MetaCommand.PREV_TURN.value:
            return handle_history_prev(state)

        elif cmd.command == MetaCommand.NEXT_TURN.value:
            return handle_history_next(state)

        elif cmd.command == MetaCommand.CURRENT_TURN.value:
            return handle_history_current()

        elif cmd.command == MetaCommand.FIRST_TURN.value:
            return handle_history_first(state)

        else:
            display.set_output([
                f"Unknown command: {cmd.raw}",
                "Type '?' for help"
            ])
            return "refresh"

    except Exception as e:
        display.set_output([f"Error: {str(e)}"])
        return "refresh"


# =============================================================================
# Legacy Command Execution (for backward compatibility)
# =============================================================================

def execute_command(
    cmd: ParsedCommand,
    client: APIClient,
    state: GameState
) -> Optional[str]:
    """
    Execute a command (legacy interface).

    This handles meta commands and delegates action commands to the caller.
    For a fully unified experience, use ActionExecutor for actions.

    NOTE: Self-actions are now handled dynamically by GameLoop using
    ShortcutRegistry. This legacy function only handles move/attack/end.

    Returns:
        "quit" - user wants to quit
        "refresh" - refresh display
        "encounter_ended" - encounter has ended
        None - command handled, no refresh needed
    """
    if cmd.is_meta:
        return execute_meta_command(cmd, client, state)

    # Action commands - attack and end only
    # Position actions (Move, Jump) and self-actions (Dash, Dodge) are
    # handled by try_execute_dynamic_position_action and try_execute_dynamic_self_action
    try:
        if cmd.command == "attack":
            return handle_attack(cmd, client, state)
        elif cmd.command == "end":
            return handle_end_turn(client, state)
        else:
            # Unknown command - NO FALLBACK for position/self actions
            display.set_output([
                f"Unknown command: {cmd.raw}",
                "Type '?' for help or 'la' to list actions"
            ])
            return "refresh"

    except Exception as e:
        display.set_output([f"Error: {str(e)}"])
        return "refresh"


# =============================================================================
# Action Handlers
# =============================================================================

def handle_attack(cmd: ParsedCommand, client: APIClient, state: GameState) -> Optional[str]:
    """Handle attack command."""
    if not state.actions:
        display.set_output(["No actions available."])
        return "refresh"

    attacks = state.actions.affordable_attacks
    if not attacks:
        display.set_output(["No targets in range."])
        return "refresh"

    if len(cmd.args) < 1:
        # Show attack options
        entity_lookup = {e["uuid"]: e for e in state.entities}
        display.console.print("\n[bold]Attack targets:[/bold]")
        target_num = 1
        for atk in attacks:
            cost_label = "[magenta]BONUS[/magenta]" if atk.is_bonus_action else "[cyan]ACTION[/cyan]"
            for target in atk.valid_targets:
                target_entity = entity_lookup.get(target.target_uuid, {})
                target_name = target.target_name or target_entity.get("name", "Unknown")
                hp = target_entity.get("hp", "?")
                max_hp = target_entity.get("max_hp", "?")
                weapon_name = atk.weapon_name or atk.display_name
                display.console.print(
                    f"  [{target_num}] {cost_label} {weapon_name} → [yellow]{target_name}[/yellow] "
                    f"(HP: {hp}/{max_hp})"
                )
                target_num += 1
        display.console.print("[dim]Usage: a N (attack target number N)[/dim]")
        return None

    try:
        target_num = int(cmd.args[0])
    except ValueError:
        display.set_output(["Invalid target number. Usage: a N"])
        return "refresh"

    result = state.actions.get_attack_target(target_num)
    if not result:
        total = state.actions.get_total_attack_count()
        display.set_output([f"Invalid target. Choose 1-{total}."])
        return "refresh"

    attack_action, target = result
    weapon_name = attack_action.weapon_name or attack_action.display_name

    # Get target name for logging
    entity_lookup = {e["uuid"]: e for e in state.entities}
    target_entity = entity_lookup.get(target.target_uuid, {})
    target_name = target.target_name or target_entity.get("name", "Unknown")

    # Execute using template name and target index directly
    api_result = client.execute_action(attack_action.template_name, target.index)
    display.show_action_result(api_result, state.player_entity_name)

    # Log the attack
    _log_attack(api_result, weapon_name, target_name, state)

    if api_result.get("encounter_ended"):
        return "encounter_ended"
    return "refresh"


def handle_end_turn(client: APIClient, state: GameState) -> Optional[str]:
    """Handle end turn command."""
    display.show_info("Ending turn...")
    result = client.end_turn()

    # Show AI actions if any
    ai_actions = result.get("ai_actions", [])
    if ai_actions:
        display.show_ai_actions(ai_actions)
        for action in ai_actions:
            _log_ai_action(action, state)

        # Capture AI movement path for display on map
        for action in ai_actions:
            if action.get("entry_type") == "movement":
                path = action.get("data", {}).get("path")
                if path:
                    state.last_movement_path = [tuple(p) for p in path]
                    break

    status = result.get("status")
    if status == "encounter_ended":
        return "encounter_ended"
    elif status == "waiting_for_human":
        if result.get("entity_name"):
            display.show_info(f"Your turn: {result['entity_name']}")
        return "refresh"
    else:
        display.show_info(f"Turn ended. Status: {status}")
        return "refresh"


# =============================================================================
# History Navigation
# =============================================================================

def handle_history_prev(state: GameState) -> Optional[str]:
    """Go to previous turn in history."""
    snapshot = display.goto_previous_turn()
    if snapshot:
        display.render_history_snapshot(snapshot)
        return None
    else:
        display.show_info("No earlier history available.")
        return None


def handle_history_next(state: GameState) -> Optional[str]:
    """Go to next turn in history."""
    snapshot = display.goto_next_turn()
    if snapshot:
        display.render_history_snapshot(snapshot)
        return None
    else:
        display.goto_current_turn()
        return "refresh"


def handle_history_current() -> Optional[str]:
    """Return to current turn."""
    display.goto_current_turn()
    return "refresh"


def handle_history_first(state: GameState) -> Optional[str]:
    """Go to first turn in history."""
    snapshot = display.goto_first_turn()
    if snapshot:
        display.render_history_snapshot(snapshot)
        return None
    else:
        display.show_info("No history available.")
        return None


# =============================================================================
# Logging Helpers
# =============================================================================

def _log_attack(result: Dict[str, Any], weapon_name: str, target_name: str, state: GameState):
    """Log a player attack to combat log."""
    event_data = result.get("event_data", {})
    outcome = (event_data.get("outcome") or "miss").lower()
    total_damage = event_data.get("total_damage", 0)
    d20 = event_data.get("d20", "?")
    all_d20_rolls = event_data.get("all_d20_rolls", [])
    advantage_status = event_data.get("advantage_status", "none")
    attack_bonus = event_data.get("attack_bonus", 0)
    attack_total = event_data.get("attack_total", "?")
    target_ac = event_data.get("target_ac", "?")

    roll_str = _format_roll_string(d20, all_d20_rolls, advantage_status, attack_bonus, attack_total)

    if outcome == "crit":
        state.add_to_log(f"CRIT with {weapon_name}! {roll_str} vs AC {target_ac} → {total_damage} dmg to {target_name}!")
    elif outcome == "hit":
        state.add_to_log(f"Hit with {weapon_name}! {roll_str} vs AC {target_ac} → {total_damage} dmg to {target_name}")
    elif outcome == "crit miss":
        state.add_to_log(f"Critical miss with {weapon_name} vs {target_name}!")
    else:
        state.add_to_log(f"Miss with {weapon_name} vs {target_name} {roll_str} vs AC {target_ac}")


def _log_ai_action(action: Dict[str, Any], state: GameState):
    """Log an AI action to combat log.

    Uses CombatLogEntry structure: entry_type, data dict.
    """
    entry_type = action.get("entry_type", "")
    data = action.get("data", {})

    if entry_type == "attack":
        attacker = data.get("attacker_name", "Unknown")
        target_name = data.get("target_name", "Unknown")
        weapon = data.get("weapon_name", "weapon")
        outcome = (data.get("outcome") or "miss").lower()
        total_damage = data.get("total_damage", 0)
        target_ac = data.get("target_ac", "?")
        is_opp = data.get("is_opportunity_attack", False)
        opp_text = "(OA) " if is_opp else ""

        # Extract from nested attack_roll
        attack_roll = data.get("attack_roll", {})
        d20 = attack_roll.get("d20_used", "?")
        all_d20_rolls = attack_roll.get("all_d20_rolls", [])
        advantage_status = attack_roll.get("advantage_status") or "none"
        attack_bonus = attack_roll.get("bonus", 0)
        attack_total = attack_roll.get("total", "?")

        roll_str = _format_roll_string(d20, all_d20_rolls, advantage_status, attack_bonus, attack_total)

        if outcome == "crit":
            state.add_to_log(f"{opp_text}{attacker} CRIT with {weapon}! {roll_str} vs AC {target_ac} → {total_damage} dmg!")
        elif outcome == "hit":
            state.add_to_log(f"{opp_text}{attacker} hit with {weapon}! {roll_str} vs AC {target_ac} → {total_damage} dmg")
        else:
            state.add_to_log(f"{opp_text}{attacker} missed with {weapon} vs {target_name} {roll_str} vs AC {target_ac}")
    elif entry_type == "movement":
        entity = data.get("entity_name", "Unknown")
        from_pos = data.get("start_position", [0, 0])
        to_pos = data.get("end_position", [0, 0])
        path = data.get("path", [])
        state.add_to_log(f"{entity} moves {tuple(from_pos)} → {tuple(to_pos)}")
        if path:
            state.last_movement_path = [tuple(p) for p in path]


def _format_roll_string(d20: Any, all_d20_rolls: List[Any], advantage_status: str, attack_bonus: int, attack_total: Any) -> str:
    """Format a roll string with advantage/disadvantage info."""
    if advantage_status == "advantage" and len(all_d20_rolls) >= 2:
        return f"ADV d20({all_d20_rolls[0]},{all_d20_rolls[1]}→{d20})+{attack_bonus}={attack_total}"
    elif advantage_status == "disadvantage" and len(all_d20_rolls) >= 2:
        return f"DIS d20({all_d20_rolls[0]},{all_d20_rolls[1]}→{d20})+{attack_bonus}={attack_total}"
    else:
        return f"d20({d20})+{attack_bonus}={attack_total}"


# =============================================================================
# Backward Compatibility (CommandType enum)
# =============================================================================

class CommandType(Enum):
    """Legacy command types for backward compatibility."""
    MOVE = "move"
    ATTACK = "attack"
    DASH = "dash"
    DODGE = "dodge"
    DISENGAGE = "disengage"
    END = "end"
    STATUS = "status"
    ACTIONS = "actions"
    MAP = "map"
    HELP = "help"
    QUIT = "quit"
    PREV_TURN = "pt"
    NEXT_TURN = "nt"
    CURRENT_TURN = "ct"
    FIRST_TURN = "ft"
    UNKNOWN = "unknown"


@dataclass
class Command:
    """Legacy command structure for backward compatibility."""
    type: CommandType
    args: List[str]
    raw: str


def parse_command_legacy(input_str: str) -> Command:
    """Parse command (legacy interface)."""
    parsed = parse_command(input_str)
    try:
        cmd_type = CommandType(parsed.command)
    except ValueError:
        cmd_type = CommandType.UNKNOWN
    return Command(type=cmd_type, args=parsed.args, raw=parsed.raw)
