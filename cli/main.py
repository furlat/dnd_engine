"""
Main entry point for the D&D Engine CLI.

Usage:
    python -m cli play          # Start interactive combat
    python -m cli play --host localhost --port 8000
"""

import typer
from typing import Optional
import time

from cli.api_client import APIClient
from cli.commands import parse_command, execute_command, GameState
from cli import display


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
            state.actions = client.get_available_actions()
        else:
            state.actions = {}

        return True

    except Exception as e:
        display.show_error(f"Failed to refresh state: {e}")
        return False


def render_display(client: APIClient, state: GameState):
    """Render the full display."""
    display.clear()

    # Show map with visibility and movement path
    display.show_map(
        state.grid,
        state.entities,
        client.current_entity_uuid,
        visibility=state.visibility,
        movement_path=state.last_movement_path
    )

    # Clear the path after showing it once
    state.last_movement_path = None

    # Show turn info and entity status
    display.show_turn_info(state.turn, state.entities)

    # Show combat log
    display.show_combat_log(state.combat_log)


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


def game_loop(client: APIClient, initial_ai_path: list = None):
    """Main game loop."""
    state = GameState()

    # Set initial AI path if provided (from AI turn before our first turn)
    if initial_ai_path:
        state.last_movement_path = initial_ai_path

    # Initial state refresh
    if not refresh_state(client, state):
        display.show_info("Encounter has ended or not started.")
        return

    need_redraw = True  # Track if we need to redraw the display

    while True:
        # Render display only when needed
        if need_redraw:
            render_display(client, state)

            # Check whose turn
            if not state.turn.get("is_human_turn", False):
                # AI turn - wait for it to complete
                if not wait_for_ai_turn(client, state):
                    # Encounter ended
                    break
                # Refresh and continue
                if not refresh_state(client, state):
                    break
                continue

            # Human turn - show available actions summary based on economy
            can_move = state.actions.get("can_move", False) and state.actions.get("remaining_movement", 0) > 0
            attacks = state.actions.get("attacks", [])
            actions_remaining = state.turn.get("actions_remaining", 0)
            has_attacks = actions_remaining > 0 and any(a.get("valid_targets") and a.get("can_afford") for a in attacks)

            # Check for other actions (dash, dodge, disengage)
            other_actions = state.actions.get("other_actions", [])
            can_dash = any(a.get("action_id") == "dash" and a.get("can_afford") for a in other_actions)
            can_dodge = any(a.get("action_id") == "dodge" and a.get("can_afford") for a in other_actions)
            can_disengage = any(a.get("action_id") == "disengage" and a.get("can_afford") for a in other_actions)

            hints = []
            if can_move:
                hints.append(f"Move:{state.actions.get('remaining_movement', 0)}ft")
            if has_attacks:
                hints.append("Attack")
            if can_dash:
                hints.append("Dash")
            if can_dodge:
                hints.append("Dodge")
            if can_disengage:
                hints.append("Disengage")
            hints.append("End")

            display.show_info(f"Actions: {', '.join(hints)} | ? for help")

        need_redraw = True  # Default to redraw next iteration

        # Get command
        cmd_str = display.prompt_command()
        cmd = parse_command(cmd_str)

        # Execute command
        result = execute_command(cmd, client, state)

        if result == "quit":
            display.show_info("Goodbye!")
            break
        elif result == "encounter_ended":
            break
        elif result == "refresh":
            # Refresh state after action
            if not refresh_state(client, state):
                break
        elif result is None:
            # Command handled itself (e.g., showing help, targets, positions)
            # Don't redraw - let user see the output and enter another command
            need_redraw = False

    # Show final state
    display.clear()
    display.show_map(state.grid, state.entities, client.current_entity_uuid, visibility=state.visibility)
    display.show_turn_info(state.turn, state.entities)

    # Determine winner
    alive = [e for e in state.entities if not e.get("is_dead", False)]
    if len(alive) == 1:
        winner = alive[0]
        display.console.print(f"\n[bold green]*** {winner['name']} WINS! ***[/bold green]\n")
    elif len(alive) == 0:
        display.console.print("\n[bold red]*** EVERYONE IS DEAD ***[/bold red]\n")
    else:
        display.console.print("\n[bold yellow]*** ENCOUNTER ENDED ***[/bold yellow]\n")


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
