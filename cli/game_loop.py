"""
Unified game loop for CLI modes.

Provides a single game loop implementation that works with different
input handlers (TUI for humans, headless for agents).
"""

from typing import Optional, Callable, Dict, Any
import time

from cli.api_client import APIClient
from cli.action_executor import ActionExecutor
from cli.input_handler import InputHandler
from cli.action_model import ShortcutRegistry
from cli.commands import parse_command, execute_meta_command, GameState
from cli import display


class GameLoop:
    """
    Unified game loop that works with any input handler.

    This is the core loop that:
    1. Polls server state
    2. Waits for turn (if not player's turn)
    3. Shows state
    4. Gets and executes commands
    5. Handles turn transitions
    """

    def __init__(
        self,
        client: APIClient,
        executor: ActionExecutor,
        handler: InputHandler,
        poll_interval: float = 2.0
    ):
        self.client = client
        self.executor = executor
        self.handler = handler
        self.poll_interval = poll_interval
        self.state = GameState()
        self.running = False
        # Session-stable shortcut registry for self-actions
        self.shortcut_registry = ShortcutRegistry()

    def _is_my_turn(self, entity_uuid: str) -> bool:
        """Check if it's the given entity's turn."""
        current_uuid = self.state.turn.get("current_entity_uuid")
        return current_uuid == entity_uuid

    def _refresh_state(self, entity_uuid: str) -> bool:
        """Refresh state from server.

        Returns True if successful, False if encounter ended.
        """
        try:
            state_resp = self.client.get_state()
            self.state.update_from_state(state_resp)
            self.state.turn = state_resp.get("turn", {})
            self.state.visibility = state_resp.get("visibility", {})

            # Get available actions for entity
            actions_resp = self.client.get_available_actions(entity_uuid)
            self.state.update_actions(actions_resp)

            # Register actions with session-stable shortcut registry
            if self.state.actions:
                self.state.actions.register_actions(self.shortcut_registry)

            return True
        except Exception as e:
            self.handler.show_error(f"Failed to refresh state: {e}")
            return False

    def _handle_action_command(
        self,
        cmd_str: str,
        entity_uuid: str
    ) -> Optional[str]:
        """Handle an action command.

        Returns:
            "refresh" - refresh display
            "encounter_ended" - encounter ended
            None - no action needed
        """
        _ = entity_uuid  # Reserved for future use
        parsed = parse_command(cmd_str, self.state.actions)

        # Meta commands (help, quit, history)
        if parsed.is_meta:
            result = execute_meta_command(parsed, self.client, self.state)
            return result

        # Handle "la" (list actions) command
        if parsed.command == "la":
            panel = display.render_all_actions(self.shortcut_registry, self.state.actions)
            display.console.print(panel)
            return None

        # Action commands
        try:
            if parsed.command == "move":
                return self._handle_move(parsed.args)
            elif parsed.command == "attack":
                return self._handle_attack(parsed.args)
            elif parsed.command == "end":
                return self._handle_end_turn()
            else:
                # Dynamic self-action routing using registry
                if self.state.actions:
                    action = self.state.actions.get_self_action_by_command(
                        parsed.command, self.shortcut_registry
                    )
                    if action:
                        return self._handle_self_action(action.template_name)

                self.handler.show_error(f"Unknown command: {parsed.command}")
                return "refresh"
        except ValueError as e:
            self.handler.show_error(str(e))
            return "refresh"
        except Exception as e:
            self.handler.show_error(f"Action failed: {e}")
            return "refresh"

    def _handle_move(self, args: list) -> Optional[str]:
        """Handle move command."""
        if len(args) < 2:
            # Show valid positions
            if self.state.actions and self.state.actions.movement:
                positions = []
                for move_action in self.state.actions.movement:
                    for target in move_action.valid_targets:
                        if target.position:
                            positions.append(target.position)
                self.state.valid_move_positions = positions
                display.set_output([
                    "Valid move positions shown on map (*)",
                    f"Movement remaining: {self.state.actions.remaining_movement}ft",
                    "Enter 'm X Y' to move"
                ])
            else:
                display.set_output(["No movement available"])
            return "refresh"

        if not self.state.actions:
            self.handler.show_error("No actions available")
            return "refresh"

        result = self.executor.execute("move", args, self.state.actions)
        self.handler.show_result(result, self.state.player_entity_name)

        if result.get("encounter_ended"):
            return "encounter_ended"
        return "refresh"

    def _handle_attack(self, args: list) -> Optional[str]:
        """Handle attack command."""
        if not self.state.actions:
            self.handler.show_error("No actions available")
            return "refresh"

        if not args:
            # Show attack options
            attacks = self.state.actions.affordable_attacks
            if not attacks:
                display.set_output(["No targets in range"])
                return "refresh"

            entity_lookup = {e["uuid"]: e for e in self.state.entities}
            display.console.print("\n[bold]Attack targets:[/bold]")
            idx = 1
            for atk in attacks:
                cost_label = "[magenta]BONUS[/magenta]" if atk.is_bonus_action else "[cyan]ACTION[/cyan]"
                weapon = atk.weapon_name or atk.display_name
                for target in atk.valid_targets:
                    target_entity = entity_lookup.get(target.target_uuid, {})
                    hp = target_entity.get("hp", "?")
                    max_hp = target_entity.get("max_hp", "?")
                    display.console.print(
                        f"  [{idx}] {cost_label} {weapon} -> [yellow]{target.target_name}[/yellow] "
                        f"(HP: {hp}/{max_hp})"
                    )
                    idx += 1
            display.console.print("[dim]Usage: a N[/dim]")
            return None

        result = self.executor.execute("attack", args, self.state.actions)
        self.handler.show_result(result, self.state.player_entity_name)

        if result.get("encounter_ended"):
            return "encounter_ended"
        return "refresh"

    def _handle_self_action(self, template_name: str) -> Optional[str]:
        """Handle self-targeting action by template name.

        Args:
            template_name: Full template name like "Dash", "Second Wind", etc.
        """
        if not self.state.actions:
            self.handler.show_error("No actions available")
            return "refresh"

        result = self.executor.execute_self_action(
            template_name, self.state.actions, self.shortcut_registry
        )
        self.handler.show_result(result, self.state.player_entity_name)
        return "refresh"

    def _handle_end_turn(self) -> Optional[str]:
        """Handle end turn command."""
        self.handler.show_info("Ending turn...")
        result = self.client.end_turn()

        # Show AI actions if any
        ai_actions = result.get("ai_actions", [])
        if ai_actions:
            display.show_ai_actions(ai_actions)

        status = result.get("status")
        if status == "encounter_ended":
            return "encounter_ended"
        return "refresh"

    def wait_for_turn(
        self,
        entity_uuid: str,
        on_opponent_action: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> bool:
        """
        Wait for it to be the entity's turn.

        Args:
            entity_uuid: UUID of entity to wait for
            on_opponent_action: Callback for opponent actions (from combat log)

        Returns:
            True if turn started, False if encounter ended
        """
        last_log_index = 0

        while self.running:
            try:
                # Get current state
                pvp_status = self.client.get_pvp_status()
                turn = pvp_status.get("turn", {})
                current_uuid = turn.get("current_entity_uuid")

                # Check if it's our turn
                if current_uuid == entity_uuid:
                    return True

                # Check for encounter end
                if pvp_status.get("encounter_state") != "ACTIVE":
                    return False

                # Process combat log for opponent actions
                if on_opponent_action:
                    log_resp = self.client.get_combat_log(since=last_log_index)
                    entries = log_resp.get("entries", [])
                    for entry in entries:
                        on_opponent_action(entry)
                    last_log_index = log_resp.get("next_index", last_log_index)

                time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                return False
            except Exception as e:
                self.handler.show_error(f"Wait failed: {e}")
                time.sleep(self.poll_interval)

        return False

    def run(
        self,
        entity_uuid: str,
        on_opponent_action: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> str:
        """
        Run the main game loop.

        Args:
            entity_uuid: UUID of entity to control
            on_opponent_action: Callback for opponent actions

        Returns:
            Exit reason: "quit", "encounter_ended", "disconnected"
        """
        self.running = True

        try:
            while self.running:
                # Refresh state
                if not self._refresh_state(entity_uuid):
                    return "disconnected"

                is_my_turn = self._is_my_turn(entity_uuid)

                if not is_my_turn:
                    # Wait for turn
                    self.handler.show_info("Waiting for your turn...")
                    if not self.wait_for_turn(entity_uuid, on_opponent_action):
                        return "encounter_ended"
                    # Refresh after turn starts
                    if not self._refresh_state(entity_uuid):
                        return "disconnected"
                    is_my_turn = True

                # Show state
                self.handler.show_state(
                    grid=self.state.grid,
                    entities=self.state.entities,
                    turn=self.state.turn,
                    actions=self.state.actions,
                    actions_raw=self.state.actions_raw,
                    is_my_turn=is_my_turn,
                    current_entity_uuid=entity_uuid,
                    valid_positions=self.state.valid_move_positions,
                    movement_path=self.state.last_movement_path,
                    visibility=self.state.visibility,
                    shortcut_registry=self.shortcut_registry
                )

                # Clear temporary display state
                self.state.valid_move_positions = None
                self.state.last_movement_path = None

                # Get and execute command
                try:
                    cmd = self.handler.get_command()
                except NotImplementedError:
                    # Headless handler doesn't support get_command
                    # This path shouldn't be reached in normal usage
                    return "disconnected"

                result = self._handle_action_command(cmd, entity_uuid)

                if result == "quit":
                    return "quit"
                elif result == "encounter_ended":
                    return "encounter_ended"
                # "refresh" or None continues the loop

        except KeyboardInterrupt:
            return "quit"
        finally:
            self.running = False

        return "quit"

    def stop(self):
        """Stop the game loop."""
        self.running = False
