"""
Command parsing and execution.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from cli.api_client import APIClient
from cli import display


class CommandType(Enum):
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
    # History navigation
    PREV_TURN = "pt"
    NEXT_TURN = "nt"
    CURRENT_TURN = "ct"
    FIRST_TURN = "ft"
    UNKNOWN = "unknown"


@dataclass
class Command:
    """Parsed command."""
    type: CommandType
    args: List[str]
    raw: str


def parse_command(input_str: str) -> Command:
    """Parse a command string into a Command object."""
    parts = input_str.strip().lower().split()
    if not parts:
        return Command(CommandType.UNKNOWN, [], input_str)

    cmd = parts[0]
    args = parts[1:]

    # Command aliases
    aliases = {
        "m": "move",
        "a": "attack",
        "d": "dash",
        "o": "dodge",
        "i": "disengage",
        "e": "end",
        "s": "status",
        "?": "help",
        "h": "help",
        "q": "quit",
        "exit": "quit",
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

    cmd = aliases.get(cmd, cmd)

    # Map to CommandType
    try:
        cmd_type = CommandType(cmd)
    except ValueError:
        cmd_type = CommandType.UNKNOWN

    return Command(cmd_type, args, input_str)


class GameState:
    """Holds current game state for the CLI."""

    def __init__(self):
        self.grid: Dict[str, Any] = {}
        self.entities: List[Dict[str, Any]] = []
        self.turn: Dict[str, Any] = {}
        self.actions: Dict[str, Any] = {}
        self.combat_log: List[str] = []
        self.visibility: Dict[str, Any] = {}
        self.last_movement_path: Optional[List[Tuple[int, int]]] = None
        self.valid_move_positions: Optional[List[Tuple[int, int]]] = None  # For showing valid moves

    def update_from_state(self, state: Dict[str, Any]):
        """Update from /state response."""
        self.grid = state.get("grid", {})
        self.entities = state.get("entities", [])

    def add_to_log(self, message: str):
        """Add a message to the combat log."""
        self.combat_log.append(message)
        # Keep last 20 messages
        if len(self.combat_log) > 20:
            self.combat_log = self.combat_log[-20:]


def execute_command(
    cmd: Command,
    client: APIClient,
    state: GameState
) -> Optional[str]:
    """
    Execute a command.

    Returns:
        Optional message to display, or None if handled internally.
        Returns "quit" if user wants to quit.
        Returns "refresh" if display should be refreshed.
    """
    try:
        if cmd.type == CommandType.QUIT:
            return "quit"

        elif cmd.type == CommandType.HELP:
            display.show_help()
            return None

        elif cmd.type == CommandType.STATUS:
            display.show_turn_info(state.turn, state.entities)
            return None

        elif cmd.type == CommandType.ACTIONS:
            display.show_available_actions(state.actions, state.entities)
            return None

        elif cmd.type == CommandType.MAP:
            return "refresh"

        elif cmd.type == CommandType.MOVE:
            return handle_move(cmd, client, state)

        elif cmd.type == CommandType.ATTACK:
            return handle_attack(cmd, client, state)

        elif cmd.type == CommandType.DASH:
            result = client.dash()
            display.show_action_result(result)
            state.add_to_log(f"You dash! Movement doubled.")
            return "refresh"

        elif cmd.type == CommandType.DODGE:
            result = client.dodge()
            display.show_action_result(result)
            state.add_to_log(f"You take the Dodge action.")
            return "refresh"

        elif cmd.type == CommandType.DISENGAGE:
            result = client.disengage()
            display.show_action_result(result)
            state.add_to_log(f"You disengage.")
            return "refresh"

        elif cmd.type == CommandType.END:
            return handle_end_turn(client, state)

        # History navigation
        elif cmd.type == CommandType.PREV_TURN:
            return handle_history_prev(state)

        elif cmd.type == CommandType.NEXT_TURN:
            return handle_history_next(state)

        elif cmd.type == CommandType.CURRENT_TURN:
            return handle_history_current()

        elif cmd.type == CommandType.FIRST_TURN:
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


def handle_move(cmd: Command, client: APIClient, state: GameState) -> Optional[str]:
    """Handle move command."""
    if len(cmd.args) < 2:
        # Show valid positions - store them for next render and show in output
        movement = state.actions.get("movement", [])
        if movement:
            valid_pos = movement[0].get("valid_positions", [])
            valid_tuples = [tuple(p) for p in valid_pos]
            # Store valid positions for map display
            state.valid_move_positions = valid_tuples
            remaining = state.actions.get('remaining_movement', 0)
            display.set_output([
                f"Valid move positions shown on map (*)",
                f"Movement remaining: {remaining}ft",
                f"Enter 'm X Y' to move to position (X, Y)"
            ])
        else:
            display.set_output(["No movement available."])
        return "refresh"  # Refresh to show valid positions on map

    try:
        x = int(cmd.args[0])
        y = int(cmd.args[1])
    except ValueError:
        display.set_output(["Invalid position. Usage: m X Y"])
        return "refresh"

    # Check if position is valid
    movement = state.actions.get("movement", [])
    if movement:
        valid_pos = movement[0].get("valid_positions", [])
        if [x, y] not in valid_pos and (x, y) not in [tuple(p) for p in valid_pos]:
            display.set_output([
                f"Position ({x}, {y}) is not reachable.",
                "Type 'm' to see valid positions."
            ])
            return "refresh"

    result = client.move((x, y))
    display.show_action_result(result)
    state.add_to_log(f"You move to ({x}, {y}).")

    # Store the path for display on next render
    event_data = result.get("event_data", {})
    path = event_data.get("path", [])
    if path:
        state.last_movement_path = [tuple(p) for p in path]
    else:
        state.last_movement_path = None

    # Log any opportunity attacks that were triggered
    triggered = result.get("triggered_reactions", [])
    for reaction in triggered:
        if reaction.get("type") == "opportunity_attack":
            attacker = reaction.get("attacker", "Unknown")
            weapon = reaction.get("weapon", "weapon")
            outcome = (reaction.get("outcome") or "miss").lower()
            total_damage = reaction.get("total_damage", 0)
            d20 = reaction.get("d20", "?")
            all_d20_rolls = reaction.get("all_d20_rolls", [])
            advantage_status = reaction.get("advantage_status", "none")
            attack_bonus = reaction.get("attack_bonus", 0)
            attack_total = reaction.get("attack_total", "?")
            target_ac = reaction.get("target_ac", "?")

            # Format roll display with advantage info
            if advantage_status == "advantage" and len(all_d20_rolls) >= 2:
                roll_str = f"ADV d20({all_d20_rolls[0]},{all_d20_rolls[1]}→{d20})+{attack_bonus}={attack_total}"
            elif advantage_status == "disadvantage" and len(all_d20_rolls) >= 2:
                roll_str = f"DIS d20({all_d20_rolls[0]},{all_d20_rolls[1]}→{d20})+{attack_bonus}={attack_total}"
            else:
                roll_str = f"d20({d20})+{attack_bonus}={attack_total}"

            if outcome == "crit":
                state.add_to_log(f"(OA) {attacker} CRIT! {roll_str} vs AC {target_ac} → {total_damage} to you!")
            elif outcome == "hit":
                state.add_to_log(f"(OA) {attacker} hit! {roll_str} vs AC {target_ac} → {total_damage} to you")
            else:
                state.add_to_log(f"(OA) {attacker} missed you {roll_str} vs AC {target_ac}")

    if result.get("encounter_ended"):
        return "encounter_ended"
    return "refresh"


def handle_attack(cmd: Command, client: APIClient, state: GameState) -> Optional[str]:
    """Handle attack command."""
    attacks = state.actions.get("attacks", [])
    valid_attacks = [a for a in attacks if a.get("valid_targets")]

    if not valid_attacks:
        display.set_output(["No targets in range."])
        return "refresh"

    if len(cmd.args) < 1:
        # Show attack options in output panel
        entity_lookup = {e["uuid"]: e for e in state.entities}
        output_lines = ["Attack targets:"]
        target_num = 1
        for atk in valid_attacks:
            for t_uuid in atk.get("valid_targets", []):
                target = entity_lookup.get(t_uuid, {})
                output_lines.append(
                    f"  [{target_num}] {atk['name']} → {target.get('name', 'Unknown')} "
                    f"(HP: {target.get('hp', '?')}/{target.get('max_hp', '?')})"
                )
                target_num += 1
        output_lines.append("Usage: a N (attack target number N)")
        display.set_output(output_lines)
        return "refresh"

    try:
        target_num = int(cmd.args[0])
    except ValueError:
        display.set_output(["Invalid target number. Usage: a N"])
        return "refresh"

    # Find target (simple: just use first attack with targets, pick by index)
    all_targets = []
    for atk in valid_attacks:
        for t_uuid in atk.get("valid_targets", []):
            all_targets.append((atk, t_uuid))

    if target_num < 1 or target_num > len(all_targets):
        display.set_output([f"Invalid target. Choose 1-{len(all_targets)}."])
        return "refresh"

    attack_info, target_uuid = all_targets[target_num - 1]
    weapon_slot = "main_hand"
    if attack_info.get("weapon_slot") == "off_hand":
        weapon_slot = "off_hand"

    # Get target name for log
    entity_lookup = {e["uuid"]: e for e in state.entities}
    target = entity_lookup.get(target_uuid, {})
    target_name = target.get("name", "Unknown")

    result = client.attack(target_uuid, weapon_slot)
    display.show_action_result(result)

    # Add to combat log with detailed info
    event_data = result.get("event_data", {})
    outcome = (event_data.get("outcome") or "miss").lower()
    total_damage = event_data.get("total_damage", 0)
    weapon = event_data.get("weapon", "weapon")
    d20 = event_data.get("d20", "?")
    all_d20_rolls = event_data.get("all_d20_rolls", [])
    advantage_status = event_data.get("advantage_status", "none")
    attack_bonus = event_data.get("attack_bonus", 0)
    attack_total = event_data.get("attack_total", "?")
    target_ac = event_data.get("target_ac", "?")

    # Format roll display with advantage info
    if advantage_status == "advantage" and len(all_d20_rolls) >= 2:
        roll_str = f"ADV d20({all_d20_rolls[0]},{all_d20_rolls[1]}→{d20})+{attack_bonus}={attack_total}"
    elif advantage_status == "disadvantage" and len(all_d20_rolls) >= 2:
        roll_str = f"DIS d20({all_d20_rolls[0]},{all_d20_rolls[1]}→{d20})+{attack_bonus}={attack_total}"
    else:
        roll_str = f"d20({d20})+{attack_bonus}={attack_total}"

    if outcome == "crit":
        state.add_to_log(f"CRIT! {roll_str} vs AC {target_ac} → {total_damage} dmg to {target_name}!")
    elif outcome == "hit":
        state.add_to_log(f"Hit! {roll_str} vs AC {target_ac} → {total_damage} dmg to {target_name}")
    elif outcome == "crit miss":
        state.add_to_log(f"Critical miss vs {target_name}!")
    else:
        state.add_to_log(f"Miss vs {target_name} {roll_str} vs AC {target_ac}")

    if result.get("encounter_ended"):
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
        # Add to combat log with detailed info
        for action in ai_actions:
            action_type = action.get("type", "")
            if action_type == "attack":
                attacker = action.get("attacker", "Unknown")
                target_name = action.get("target", "Unknown")
                weapon = action.get("weapon", "weapon")
                outcome = (action.get("outcome") or "miss").lower()
                total_damage = action.get("total_damage", 0)
                d20 = action.get("d20", "?")
                all_d20_rolls = action.get("all_d20_rolls", [])
                advantage_status = action.get("advantage_status", "none")
                attack_bonus = action.get("attack_bonus", 0)
                attack_total = action.get("attack_total", "?")
                target_ac = action.get("target_ac", "?")
                is_opp = action.get("is_opportunity_attack", False)
                opp_text = "(OA) " if is_opp else ""

                # Format roll display with advantage info
                if advantage_status == "advantage" and len(all_d20_rolls) >= 2:
                    roll_str = f"ADV d20({all_d20_rolls[0]},{all_d20_rolls[1]}→{d20})+{attack_bonus}={attack_total}"
                elif advantage_status == "disadvantage" and len(all_d20_rolls) >= 2:
                    roll_str = f"DIS d20({all_d20_rolls[0]},{all_d20_rolls[1]}→{d20})+{attack_bonus}={attack_total}"
                else:
                    roll_str = f"d20({d20})+{attack_bonus}={attack_total}"

                if outcome == "crit":
                    state.add_to_log(f"{opp_text}{attacker} CRIT! {roll_str} vs AC {target_ac} → {total_damage} dmg!")
                elif outcome == "hit":
                    state.add_to_log(f"{opp_text}{attacker} hit! {roll_str} vs AC {target_ac} → {total_damage} dmg")
                else:
                    state.add_to_log(f"{opp_text}{attacker} missed {target_name} {roll_str} vs AC {target_ac}")
            elif action_type == "move":
                entity = action.get("entity", "Unknown")
                from_pos = action.get("from", [0, 0])
                to_pos = action.get("to", [0, 0])
                path = action.get("path", [])
                state.add_to_log(f"{entity} moves {tuple(from_pos)} → {tuple(to_pos)}")
                # Store the path for display (last AI move wins if multiple)
                if path:
                    state.last_movement_path = [tuple(p) for p in path]

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


# ============================================================================
# History Navigation
# ============================================================================

def handle_history_prev(state: GameState) -> Optional[str]:
    """Go to previous turn in history."""
    snapshot = display.goto_previous_turn()
    if snapshot:
        display.render_history_snapshot(snapshot)
        return None  # Don't refresh - we're showing history
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
        # Returned to current
        display.goto_current_turn()
        return "refresh"  # Go back to live view


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
