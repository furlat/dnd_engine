"""
Main entry point for the D&D Engine CLI.

Usage:
    python -m cli play          # Start interactive combat (vs AI)
    python -m cli playpvp       # Start PvP combat (vs Claude)
    python -m cli play --host localhost --port 8000
"""

import typer
from typing import Optional
import time

from cli.api_client import APIClient
from cli.commands import parse_command, execute_command, GameState, MetaCommand
from cli import display


def prompt_with_connection_poll(client: APIClient, pvp_mode: bool = False, poll_interval: float = 2.0) -> str:
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
        except Exception:
            pass  # Don't fail render if status check fails

    # Use the new full-screen render
    display.render_full_screen(
        grid=state.grid,
        entities=state.entities,
        turn=state.turn,
        current_entity_uuid=player_uuid,
        actions=state.actions_raw if is_my_turn else None,
        visibility=state.visibility,
        movement_path=state.last_movement_path,
        valid_positions=state.valid_move_positions,
        is_my_turn=is_my_turn
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

        except Exception:
            continue

    display.show_error("Timeout waiting for AI turn")
    return False


def wait_for_opponent_turn(client: APIClient, state: GameState, hero_uuid: str) -> bool:
    """
    Wait while opponent (Claude) takes their turn in PvP mode.

    Polls the server-side combat log for new entries and updates display.
    Returns True if game should continue, False if encounter ended.
    """
    import httpx

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
                # Add to local combat log
                state.add_to_log(entry.get("message", ""))
                need_redraw = True
                combat_log_index = entry.get("index", combat_log_index) + 1

            # Check PvP status AFTER processing combat log
            response = httpx.get(f"{client.base_url}/pvp/status", timeout=5.0)
            if response.status_code == 200:
                pvp_status = response.json()

                claude_connected = pvp_status.get("claude_connected", False)
                is_hero_turn = pvp_status.get("is_hero_turn", False)
                current_turn = pvp_status.get("current_turn", "???")

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
            pass  # Silently ignore connection hiccups during polling

        time.sleep(poll_interval)


def game_loop(client: APIClient, initial_ai_path: list = None, pvp_mode: bool = False, hero_uuid: str = None):
    """Main game loop."""
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
        try:
            log_response = client.get_combat_log(since=0)
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
                    # Check for self-targeting actions
                    if state.actions.get_self_action("Dash"):
                        hints.append("Dash")
                    if state.actions.get_self_action("Dodge"):
                        hints.append("Dodge")
                    if state.actions.get_self_action("Disengage"):
                        hints.append("Disengage")
                hints.append("End")

                display.show_info(f"Actions: {', '.join(hints)} | ? for help")

            need_redraw = True  # Default to redraw next iteration

            # Get command (with connection status polling in PvP mode)
            cmd_str = prompt_with_connection_poll(client, pvp_mode=pvp_mode)
            cmd = parse_command(cmd_str)

            # Execute command
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
            elif result is None:
                # Command handled itself (e.g., showing help, targets, positions)
                # Don't redraw - let user see the output and enter another command
                need_redraw = False

        # Show final state with full display (including combat log)
        # Save final snapshot for history
        display.save_turn_snapshot(state.turn, state.entities, state.grid)

        # Determine winner message
        alive = [e for e in state.entities if not e.get("is_dead", False)]
        if len(alive) == 1:
            winner = alive[0]
            winner_msg = f"[bold green]*** {winner['name']} WINS! ***[/bold green]"
        elif len(alive) == 0:
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
    host: str = typer.Option("localhost", "--host", "-h", help="Server hostname"),
    port: int = typer.Option(8000, "--port", "-p", help="Server port"),
):
    """
    Start an interactive combat session.

    Connects to the D&D Engine server and starts a human-controlled combat.
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
        display.console.print("[cyan]Rolling initiative...[/cyan]")
        result = client.start_human_game()
        hero_uuid = result.get("hero_uuid")

        # Create session and join game
        display.console.print("[cyan]Creating session...[/cyan]")
        client.create_session(player_type="human", name="Player")
        join_result = client.join_game(entity_uuids=[hero_uuid] if hero_uuid else None)
        display.console.print(f"[green]Joined as: {join_result.get('message')}[/green]")

        entity_name = result.get("entity_name", "Unknown")
        display.console.print(f"[green]You control: {entity_name}[/green]")

        # Show any AI actions that occurred before our turn (if AI went first)
        ai_actions = result.get("ai_actions", [])
        if ai_actions:
            display.show_ai_actions(ai_actions)
            # Capture any AI movement path for display
            for action in ai_actions:
                if action.get("type") == "move" and action.get("path"):
                    # Store the last AI movement path
                    initial_ai_path = [tuple(p) for p in action.get("path", [])]
                    break
            else:
                initial_ai_path = None
        else:
            initial_ai_path = None

        # Run the game loop, passing initial AI path
        game_loop(client, initial_ai_path=initial_ai_path)

    except Exception as e:
        display.show_error(f"Connection failed: {e}")
        display.show_info(f"Make sure the server is running: python -m server.event_server")
        raise typer.Exit(1)

    finally:
        client.close()


@app.command()
def playpvp(
    host: str = typer.Option("localhost", "--host", "-h", help="Server hostname"),
    port: int = typer.Option(8000, "--port", "-p", help="Server port"),
):
    """
    Start a PvP combat session (User vs Claude).

    You control the Hero, Claude controls the Skeleton via agent CLI.
    Both players take turns manually - no auto-AI.
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
        display.console.print("[cyan]Starting PvP match...[/cyan]")
        result = client.start_pvp_game()

        hero_uuid = result.get("hero_uuid")
        skeleton_uuid = result.get("skeleton_uuid")

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
