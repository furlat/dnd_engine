"""
Shared action execution logic for CLI.

This module provides a unified interface for executing actions via the API,
handling the translation from CLI commands to API calls.
"""

from typing import Dict, Any, List, Optional
from cli.api_client import APIClient
from cli.action_model import AvailableActionsState, ShortcutRegistry


class ActionExecutor:
    """Executes actions via the API client."""

    def __init__(self, client: APIClient):
        self.client = client

    def execute(
        self,
        command: str,
        args: List[str],
        actions: AvailableActionsState,
        registry: Optional[ShortcutRegistry] = None
    ) -> Dict[str, Any]:
        """
        Execute an action by command name.

        Args:
            command: Command name (e.g., "attack", "move", "dash")
            args: Command arguments
            actions: Available actions state
            registry: Optional shortcut registry for dynamic self-action lookup

        Returns:
            Action result dict from server

        Raises:
            ValueError: If action cannot be executed
        """
        cmd = command.lower()

        if cmd == "attack":
            return self._execute_attack(args, actions)
        elif cmd == "move":
            return self._execute_move(args, actions)
        elif cmd == "end":
            return self.client.end_turn()
        else:

            if registry:
                action = actions.get_self_action_by_command(cmd, registry)
                if action:
                    return self._execute_self_action_by_template(action.template_name, actions)

            action = actions.get_self_action(cmd.title())
            if action:
                return self._execute_self_action_by_template(action.template_name, actions)
            raise ValueError(f"Unknown command: {command}")

    def _execute_attack(
        self,
        args: List[str],
        actions: AvailableActionsState
    ) -> Dict[str, Any]:
        """Execute an attack action."""
        if not args:
            raise ValueError("Attack requires target number. Usage: attack N")

        try:
            target_num = int(args[0])
        except ValueError:
            raise ValueError(f"Invalid target number: {args[0]}")

        result = actions.get_attack_target(target_num)
        if not result:
            total = actions.get_total_attack_count()
            if total == 0:
                raise ValueError("No targets in range")
            raise ValueError(f"Invalid target. Choose 1-{total}")

        attack_action, target = result

        return self.client.execute_action(attack_action.template_name, target.index)

    def _execute_move(
        self,
        args: List[str],
        actions: AvailableActionsState
    ) -> Dict[str, Any]:
        """Execute a move action. Use 'move X Y short' to force shortest path."""
        if len(args) < 2:
            raise ValueError("Move requires position. Usage: move X Y [short]")

        try:
            x = int(args[0])
            y = int(args[1])
        except ValueError:
            raise ValueError("Invalid position. Usage: move X Y [short]")

        prefer_safe = not (len(args) >= 3 and args[2].lower() == "short")

        position = (x, y)
        for move_action in actions.movement:
            for target in move_action.valid_targets:
                if target.position == position:
                    return self.client.execute_action(
                        move_action.template_name, target.index,
                        prefer_safe=prefer_safe
                    )

        raise ValueError(f"Position ({x}, {y}) is not reachable")

    def _execute_self_action_by_template(
        self,
        template_name: str,
        actions: AvailableActionsState
    ) -> Dict[str, Any]:
        """Execute a self-targeting action by its exact template name."""
        action = actions.get_self_action(template_name)
        if not action:
            raise ValueError(f"Action '{template_name}' not available")

        return self.client.execute_action(action.template_name, 0)

    def execute_self_action(
        self,
        template_name: str,
        actions: AvailableActionsState,
        registry: ShortcutRegistry
    ) -> Dict[str, Any]:
        """Execute a self-targeting action by template name.

        This is the preferred method for game_loop to use, as it handles
        the registry properly for dynamic action lookup.

        Args:
            template_name: Full template name like "Dash", "Second Wind"
            actions: Available actions state
            registry: Session shortcut registry (for potential future use)

        Returns:
            Action result from server

        Raises:
            ValueError: If action not available
        """
        _ = registry
        return self._execute_self_action_by_template(template_name, actions)

    def execute_by_index(
        self,
        action_type: str,
        index: int,
        actions: AvailableActionsState
    ) -> Dict[str, Any]:
        """
        Execute an action by type and target index.

        This is useful for UI interactions where actions are pre-selected
        and targets are numbered.

        Args:
            action_type: "attack", "move", etc.
            index: 1-based target index
            actions: Available actions state

        Returns:
            Action result from server
        """
        return self.execute(action_type, [str(index)], actions)
