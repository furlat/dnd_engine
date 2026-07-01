"""
Input handlers for different CLI modes.

Provides abstract base class and implementations for:
- TUIInputHandler: Rich terminal UI for human players (used by main.py)
- HeadlessInputHandler: Simple output for agent mode (used by agent.py)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING

from cli.action_model import AvailableActionsState
from cli import display

if TYPE_CHECKING:
    from cli.action_model import ShortcutRegistry


class InputHandler(ABC):
    """Abstract base class for input handlers."""

    @abstractmethod
    def get_command(self) -> str:
        """Get a command from the user/agent."""
        pass

    @abstractmethod
    def show_state(
        self,
        grid: Dict[str, Any],
        entities: List[Dict[str, Any]],
        turn: Dict[str, Any],
        actions: Optional[AvailableActionsState],
        actions_raw: Optional[Dict[str, Any]],
        is_my_turn: bool,
        current_entity_uuid: Optional[str] = None,
        valid_positions: Optional[List[Tuple[int, int]]] = None,
        movement_path: Optional[List[Tuple[int, int]]] = None,
        visibility: Optional[Dict[str, Any]] = None,
        shortcut_registry: Optional["ShortcutRegistry"] = None
    ) -> None:
        """Display the current game state."""
        pass

    @abstractmethod
    def show_result(self, result: Dict[str, Any], player_name: str = "You") -> None:
        """Display the result of an action."""
        pass

    @abstractmethod
    def show_error(self, message: str) -> None:
        """Display an error message."""
        pass

    @abstractmethod
    def show_info(self, message: str) -> None:
        """Display an info message."""
        pass

    def on_turn_start(self, entity_name: str) -> None:
        """Called when a turn starts."""
        pass

    def on_turn_end(self, entity_name: str) -> None:
        """Called when a turn ends."""
        pass

    def on_encounter_end(self, result: str) -> None:
        """Called when encounter ends."""
        pass


class TUIInputHandler(InputHandler):
    """
    Rich terminal UI input handler for human players.

    Provides full-screen TUI with map, combatants table, combat log,
    and available actions panel.
    """

    def __init__(self, use_alternate_screen: bool = True):
        self.use_alternate_screen = use_alternate_screen

    def get_command(self) -> str:
        """Get command via Rich prompt."""
        return display.prompt_command()

    def show_state(
        self,
        grid: Dict[str, Any],
        entities: List[Dict[str, Any]],
        turn: Dict[str, Any],
        actions: Optional[AvailableActionsState],
        actions_raw: Optional[Dict[str, Any]],
        is_my_turn: bool,
        current_entity_uuid: Optional[str] = None,
        valid_positions: Optional[List[Tuple[int, int]]] = None,
        movement_path: Optional[List[Tuple[int, int]]] = None,
        visibility: Optional[Dict[str, Any]] = None,
        shortcut_registry: Optional["ShortcutRegistry"] = None
    ) -> None:
        """Render full-screen TUI."""
        _ = actions
        display.render_full_screen(
            grid=grid,
            entities=entities,
            turn=turn,
            current_entity_uuid=current_entity_uuid,
            actions=actions_raw,
            visibility=visibility,
            movement_path=movement_path,
            valid_positions=valid_positions,
            is_my_turn=is_my_turn,
            shortcut_registry=shortcut_registry
        )

    def show_result(self, result: Dict[str, Any], player_name: str = "You") -> None:
        """Process action result and add to combat log."""
        display.show_action_result(result, player_name)

    def show_error(self, message: str) -> None:
        """Display error message."""
        display.show_error(message)

    def show_info(self, message: str) -> None:
        """Display info message."""
        display.show_info(message)

    def enter_screen(self) -> None:
        """Enter alternate screen mode."""
        if self.use_alternate_screen:
            display.enter_alternate_screen()

    def exit_screen(self) -> None:
        """Exit alternate screen mode."""
        if self.use_alternate_screen:
            display.exit_alternate_screen()

    def on_encounter_end(self, result: str) -> None:
        """Show encounter end screen."""
        display.clear()
        display.console.print(f"\n[bold]Encounter ended: {result}[/bold]\n")


class HeadlessInputHandler(InputHandler):
    """
    Headless input handler for agent mode.

    Provides simple text output suitable for automated agents.
    Does not use alternate screen or Rich formatting.
    """

    def __init__(self, silent: bool = False):
        self.silent = silent

    def get_command(self) -> str:
        """Headless mode doesn't prompt for commands."""

        raise NotImplementedError("HeadlessInputHandler.get_command() should not be called")

    def show_state(
        self,
        grid: Dict[str, Any],
        entities: List[Dict[str, Any]],
        turn: Dict[str, Any],
        actions: Optional[AvailableActionsState],
        actions_raw: Optional[Dict[str, Any]],
        is_my_turn: bool,
        current_entity_uuid: Optional[str] = None,
        valid_positions: Optional[List[Tuple[int, int]]] = None,
        movement_path: Optional[List[Tuple[int, int]]] = None,
        visibility: Optional[Dict[str, Any]] = None,
        shortcut_registry: Optional["ShortcutRegistry"] = None
    ) -> None:
        """Print simple text state summary."""

        _ = grid, actions_raw, valid_positions, movement_path, visibility, shortcut_registry

        if self.silent:
            return

        print("\n=== Game State ===")

        current_name = turn.get("current_entity_name", "???")
        round_num = turn.get("round_number", 1)
        turn_indicator = "YOUR TURN" if is_my_turn else "OPPONENT'S TURN"
        print(f"Round {round_num} | {current_name} | {turn_indicator}")

        print("\nEntities:")
        for e in entities:
            status = "DEAD" if e.get("is_dead") else f"HP:{e.get('hp')}/{e.get('max_hp')}"
            pos = e.get("position", [0, 0])
            conditions = e.get("conditions", [])
            cond_str = f" ({', '.join(conditions)})" if conditions else ""
            marker = " <--" if e.get("uuid") == current_entity_uuid else ""
            print(f"  {e['name']}: {status} at ({pos[0]},{pos[1]}){cond_str}{marker}")

        if is_my_turn:
            print(f"\nEconomy: Actions:{turn.get('actions_remaining', 0)} "
                  f"Bonus:{turn.get('bonus_actions_remaining', 0)} "
                  f"Movement:{turn.get('movement_remaining', 0)}ft")

        if actions and is_my_turn:
            attacks = actions.affordable_attacks
            if attacks:
                print("\nAttacks:")
                idx = 1
                for atk in attacks:
                    cost_label = "BONUS" if atk.is_bonus_action else "ACTION"
                    weapon = atk.weapon_name or atk.display_name
                    for target in atk.valid_targets:
                        print(f"  [{idx}] {cost_label} {weapon} -> {target.target_name}")
                        idx += 1

    def show_result(self, result: Dict[str, Any], player_name: str = "You") -> None:
        """Print simple result message."""
        if self.silent:
            return
        message = result.get("message", "Action completed")
        success = result.get("success", True)
        status = "OK" if success else "FAILED"
        print(f"[{status}] {message}")

    def show_error(self, message: str) -> None:
        """Print error message."""
        if not self.silent:
            print(f"ERROR: {message}")

    def show_info(self, message: str) -> None:
        """Print info message."""
        if not self.silent:
            print(f"INFO: {message}")

    def on_turn_start(self, entity_name: str) -> None:
        """Print turn start."""
        if not self.silent:
            print(f"\n>>> {entity_name}'s turn <<<")

    def on_turn_end(self, entity_name: str) -> None:
        """Print turn end."""
        if not self.silent:
            print(f"--- {entity_name}'s turn ends ---")

    def on_encounter_end(self, result: str) -> None:
        """Print encounter end."""
        if not self.silent:
            print(f"\n=== ENCOUNTER ENDED: {result} ===\n")
