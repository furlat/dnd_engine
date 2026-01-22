"""
Non-interactive CLI for AI agents (Claude) to control D&D entities.

This module provides a command-line interface that can be called from Bash,
enabling Claude Code to play the game by issuing commands.

Updated to use session-based authentication.

Usage:
    python -m cli.agent connect              # Connect to game (creates session, joins)
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
from typing import Optional
from cli.api_client import APIClient

# Session persistence file (so we don't create new sessions every command)
SESSION_FILE = "/tmp/dnd_agent_session.txt"


def save_session(session_id: str, entity_uuid: str) -> None:
    """Save session info to file for persistence between commands."""
    with open(SESSION_FILE, "w") as f:
        f.write(f"{session_id}\n{entity_uuid}")


def load_session() -> tuple:
    """Load session info from file. Returns (session_id, entity_uuid) or (None, None)."""
    if not os.path.exists(SESSION_FILE):
        return None, None
    try:
        with open(SESSION_FILE, "r") as f:
            lines = f.read().strip().split("\n")
            if len(lines) >= 2:
                return lines[0], lines[1]
    except Exception:
        pass
    return None, None


def clear_session() -> None:
    """Clear saved session."""
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)


def ensure_session(client: APIClient) -> bool:
    """
    Ensure client has a valid session. Loads from file or returns False.

    Returns True if session loaded successfully, False if need to connect.
    """
    session_id, entity_uuid = load_session()
    if not session_id:
        return False

    # Set the session on the client
    client._session_id = session_id
    client._current_entity_uuid = entity_uuid

    # Verify session is still valid by pinging
    try:
        result = client.ping_session()
        if result.get("connection_status") == "disconnected":
            clear_session()
            return False
        return True
    except Exception:
        clear_session()
        return False


def get_my_entity(client: APIClient) -> Optional[dict]:
    """
    Get the entity that the agent controls (Skeleton).
    Returns entity dict with uuid, name, position, etc.
    """
    state = client.get_state()
    if not state:
        return None

    entities = state.get("entities", [])
    for e in entities:
        # Agent controls the Skeleton (not Hero)
        if e.get("name") == "Skeleton":
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


def format_map(state: dict, visibility: dict) -> str:
    """Format ASCII map from state data."""
    grid = state.get("grid", {})
    tiles = grid.get("tiles", [])

    # Build tile lookup
    tile_map = {}
    for t in tiles:
        tile_map[(t.get("x", 0), t.get("y", 0))] = t

    # Get bounds
    min_x = grid.get("min_x", 0)
    max_x = grid.get("max_x", 14)
    min_y = grid.get("min_y", 0)
    max_y = grid.get("max_y", 14)

    entities = state.get("entities", [])

    # Build entity position map
    entity_map = {}
    for e in entities:
        pos = tuple(e.get("position", [0, 0]))
        name = e.get("name", "?")
        char = "@" if name == "Hero" else name[0].upper()
        entity_map[pos] = char

    lines = []
    width = max_x - min_x + 1
    lines.append("=" * (width + 2))

    for y in range(max_y, min_y - 1, -1):
        row = ""
        for x in range(min_x, max_x + 1):
            pos = (x, y)
            if pos in entity_map:
                row += entity_map[pos]
            elif pos in tile_map and not tile_map[pos].get("walkable", True):
                row += "#"
            else:
                row += "."
        lines.append(f"|{row}|")

    lines.append("=" * (width + 2))
    return "\n".join(lines)


def format_entities(entities: list) -> str:
    """Format entity status table."""
    lines = ["ENTITIES:"]
    lines.append(f"{'#':<3} {'Name':<12} {'HP':<8} {'AC':<4} {'Pos':<8} {'Conditions'}")
    lines.append("-" * 60)

    for i, e in enumerate(entities):
        name = e.get("name", "???")
        hp = f"{e.get('hp', 0)}/{e.get('max_hp', 0)}"
        ac = e.get("ac", 0)
        pos = e.get("position", [0, 0])
        pos_str = f"({pos[0]},{pos[1]})"
        conditions = ", ".join(e.get("conditions", [])) or "none"
        lines.append(f"{i:<3} {name:<12} {hp:<8} {ac:<4} {pos_str:<8} {conditions}")

    return "\n".join(lines)


def format_actions(actions: dict, entity_name: str) -> str:
    """Format available actions."""
    lines = [f"AVAILABLE ACTIONS FOR {entity_name}:"]
    lines.append("")

    # Movement
    movement = actions.get("remaining_movement", 0)
    # valid_positions is inside movement[0], not at top level
    movement_actions = actions.get("movement", [])
    valid_positions = movement_actions[0].get("valid_positions", []) if movement_actions else []
    lines.append(f"MOVEMENT: {movement} ft remaining, {len(valid_positions)} reachable positions")
    if valid_positions:
        # Show a few sample positions
        sample = valid_positions[:10]
        pos_strs = [f"({p[0]},{p[1]})" for p in sample]
        lines.append(f"  Sample positions: {', '.join(pos_strs)}")
        if len(valid_positions) > 10:
            lines.append(f"  ... and {len(valid_positions) - 10} more")

    lines.append("")

    # Attacks
    attacks = actions.get("attacks", [])
    lines.append(f"ATTACKS: {len(attacks)} attack options")
    for i, atk in enumerate(attacks):
        name = atk.get("name", "???")
        can_afford = atk.get("can_afford", False)
        valid_targets = atk.get("valid_targets", [])
        num_targets = len(valid_targets)
        status = "READY" if can_afford and num_targets > 0 else "NO TARGETS" if num_targets == 0 else "NO ACTION"
        lines.append(f"  [{i}] {name} - {num_targets} targets ({status})")

    lines.append("")

    # Other actions
    other = actions.get("other_actions", [])
    lines.append("OTHER ACTIONS:")
    for action in other:
        action_name = action.get("name", action.get("action_id", "???"))
        can_afford = action.get("can_afford", False)
        status = "READY" if can_afford else "NO ACTION"
        lines.append(f"  {action_name}: {status}")

    return "\n".join(lines)


def cmd_connect(client: APIClient) -> int:
    """Connect to the game by creating a session and joining."""
    print("Connecting to game...")

    # Create session
    try:
        session_result = client.create_session(player_type="claude", name="Claude")
        session_id = session_result.get("session_id")
        print(f"Session created: {session_id[:8]}...")
    except Exception as e:
        print(f"ERROR: Failed to create session: {e}")
        return 1

    # Join game
    try:
        join_result = client.join_game()
        controlled = join_result.get("controlled_entities", [])
        if controlled:
            entity_uuid = controlled[0]
            print(f"Joined game, controlling: {len(controlled)} entities")

            # Save session for future commands
            save_session(session_id, entity_uuid)
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


def cmd_disconnect(client: APIClient) -> int:
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

    visibility = client.get_visibility() or {}

    # Game status - get from encounter object
    encounter = state.get("encounter", {})
    active_uuid = encounter.get("current_entity_uuid")
    round_num = encounter.get("round_number", 1)

    entities = state.get("entities", [])
    active_name = "???"
    my_entity = None
    for e in entities:
        if e.get("uuid") == active_uuid:
            active_name = e.get("name", "???")
        if e.get("name") == "Skeleton":
            my_entity = e

    # Check if it's my turn using session
    my_turn = is_my_turn(client)
    turn_indicator = ">>> MY TURN <<<" if my_turn else "(waiting)"

    print(f"ROUND {round_num} - {active_name}'s turn {turn_indicator}")
    if my_entity:
        print(f"I control: {my_entity.get('name', '???')}")
    print("")

    # Map
    print(format_map(state, visibility))
    print("")

    # Entities
    print(format_entities(entities))

    # Show if it's my turn
    if my_turn:
        print("")
        print(">>> IT'S MY TURN - Use 'actions' to see options <<<")

    return 0


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

        # Check for triggered reactions (opportunity attacks)
        reactions = result.get("triggered_reactions", [])
        for r in reactions:
            attacker = r.get("attacker", "???")
            outcome = r.get("outcome", "???")
            damage = r.get("total_damage", 0)
            print(f"  REACTION: {attacker} opportunity attack - {outcome}, {damage} damage")
    else:
        message = result.get("message", "Unknown error")
        print(f"ERROR: {message}")
        return 1

    return 0


def cmd_attack(client: APIClient, target_index: int) -> int:
    """Attack target by index."""
    if not validate_my_turn(client):
        return 1

    entity_uuid = client.current_entity_uuid

    # Get available actions to find target UUID
    actions = client.get_available_actions(entity_uuid)
    if not actions:
        print("ERROR: Could not get available actions")
        return 1

    attacks = actions.get("attacks", [])
    if target_index < 0 or target_index >= len(attacks):
        print(f"ERROR: Invalid target index {target_index}. Valid: 0-{len(attacks)-1}")
        return 1

    attack_info = attacks[target_index]
    valid_targets = attack_info.get("valid_targets", [])
    if not valid_targets:
        print("ERROR: No valid targets for this attack")
        return 1
    target_uuid = valid_targets[0]

    # Get target name
    state = client.get_state()
    target_name = "???"
    if state:
        for e in state.get("entities", []):
            if e.get("uuid") == target_uuid:
                target_name = e.get("name", "???")
                break

    try:
        result = client.attack(target_uuid)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    success = result.get("success", False)
    if success:
        event_data = result.get("event_data", {})
        outcome = event_data.get("outcome", "???")
        d20 = event_data.get("d20", 0)
        all_rolls = event_data.get("all_d20_rolls", [d20])
        adv_status = event_data.get("advantage_status", "none")
        attack_bonus = event_data.get("attack_bonus", 0)
        attack_total = event_data.get("attack_total", 0)
        target_ac = event_data.get("target_ac", 0)
        total_damage = event_data.get("total_damage", 0)

        # Format roll string
        if adv_status == "advantage" and len(all_rolls) >= 2:
            roll_str = f"ADV d20({all_rolls[0]},{all_rolls[1]}->{d20})"
        elif adv_status == "disadvantage" and len(all_rolls) >= 2:
            roll_str = f"DIS d20({all_rolls[0]},{all_rolls[1]}->{d20})"
        else:
            roll_str = f"d20({d20})"

        bonus_str = f"+{attack_bonus}" if attack_bonus >= 0 else str(attack_bonus)

        print(f"OK: Attack vs {target_name}")
        print(f"  Roll: {roll_str} {bonus_str} = {attack_total} vs AC {target_ac}")
        print(f"  Result: {outcome.upper()}")
        if outcome.lower() in ["hit", "crit"]:
            print(f"  Damage: {total_damage}")
    else:
        message = result.get("message", "Unknown error")
        print(f"ERROR: {message}")
        return 1

    return 0


def cmd_special_action(client: APIClient, action: str) -> int:
    """Execute dash, dodge, or disengage."""
    if not validate_my_turn(client):
        return 1

    action_map = {
        "dash": client.dash,
        "dodge": client.dodge,
        "disengage": client.disengage,
    }

    func = action_map.get(action.lower())
    if not func:
        print(f"ERROR: Unknown action {action}")
        return 1

    try:
        result = func()
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    success = result.get("success", False)
    if success:
        print(f"OK: {action.capitalize()} action taken")
    else:
        message = result.get("message", "Unknown error")
        print(f"ERROR: {message}")
        return 1

    return 0


def cmd_end(client: APIClient) -> int:
    """End turn."""
    if not validate_my_turn(client):
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
    turn, outputs the full game state and available actions, then exits.

    Use Ctrl+C to interrupt.
    """
    import time

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
                dead = [e for e in entities if e.get("is_dead", False) or e.get("hp", 0) <= 0]

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
                print("")
                print("=" * 60)
                print(">>> MY TURN <<<")
                print("=" * 60)
                print("")

                # Output full state
                cmd_state(client)
                print("")

                # Output available actions
                cmd_actions(client)
                print("")

                print("Ready to act. Use: move X Y | attack N | dash | dodge | disengage | end")
                return 0

            # Poll combat log for opponent actions
            try:
                log_data = client.get_combat_log(since=combat_log_index)
                new_entries = log_data.get("entries", [])

                for entry in new_entries:
                    entry_type = entry.get("type", "")
                    message = entry.get("message", "")
                    details = entry.get("details", {})

                    # Show opponent actions
                    if entry_type == "attack":
                        attacker = details.get("attacker", "???")
                        target = details.get("target", "???")
                        outcome = details.get("outcome", "???")
                        d20 = details.get("d20", 0)
                        attack_bonus = details.get("attack_bonus", 0)
                        attack_total = details.get("attack_total", 0)
                        target_ac = details.get("target_ac", 0)
                        total_damage = details.get("total_damage", 0)

                        print(f"[OPPONENT] {attacker} attacks {target}")
                        print(f"  Roll: d20({d20}) +{attack_bonus} = {attack_total} vs AC {target_ac}")
                        print(f"  Result: {outcome.upper()}")
                        if outcome.lower() in ["hit", "crit"]:
                            print(f"  Damage: {total_damage}")
                    elif entry_type == "move":
                        print(f"[OPPONENT] {message}")
                    elif entry_type == "turn_end":
                        print(f"[TURN] {message}")
                    elif entry_type == "death":
                        print(f"[DEATH] {message}")

                    combat_log_index = entry.get("index", combat_log_index) + 1
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
    if len(sys.argv) < 2:
        print("Usage: python -m cli.agent <command> [args]")
        print("")
        print("Connection:")
        print("  connect            Connect to game (create session, join)")
        print("  disconnect         Disconnect from game (clear session)")
        print("  wait               Check if it's my turn (returns 0 if yes)")
        print("  watch              Wait until my turn, show state+actions (blocks)")
        print("")
        print("Game State:")
        print("  state              Show game state (map, entities, whose turn)")
        print("  actions            Show available actions for my entity")
        print("")
        print("Actions:")
        print("  move X Y           Move to position (X, Y)")
        print("  attack N           Attack target by index")
        print("  dash               Take Dash action (double movement)")
        print("  dodge              Take Dodge action (attackers have disadvantage)")
        print("  disengage          Take Disengage action (no opportunity attacks)")
        print("  end                End turn")
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

        elif command == "move":
            if len(sys.argv) < 4:
                print("Usage: python -m cli.agent move X Y")
                return 1
            x = int(sys.argv[2])
            y = int(sys.argv[3])
            return cmd_move(client, x, y)

        elif command == "attack":
            if len(sys.argv) < 3:
                print("Usage: python -m cli.agent attack N")
                return 1
            target_index = int(sys.argv[2])
            return cmd_attack(client, target_index)

        elif command in ["dash", "dodge", "disengage"]:
            return cmd_special_action(client, command)

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
