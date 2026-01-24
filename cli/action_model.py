"""
Unified action data structures for CLI.

These dataclasses parse the server's AvailableActionsResult into a format
that's easy to work with in the CLI. They're decoupled from the server
implementation and provide convenience methods for command parsing.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple


@dataclass
class ActionTarget:
    """A valid target for an action."""
    index: int
    target_uuid: Optional[str] = None
    position: Optional[Tuple[int, int]] = None
    target_name: Optional[str] = None
    distance: Optional[int] = None
    path_cost: Optional[int] = None

    @classmethod
    def from_server(cls, data: Dict[str, Any]) -> 'ActionTarget':
        """Parse from server AvailableTarget JSON."""
        pos = data.get("position")
        return cls(
            index=data.get("index", 0),
            target_uuid=data.get("target_uuid"),
            position=tuple(pos) if pos else None,
            target_name=data.get("target_name"),
            distance=data.get("distance"),
            path_cost=data.get("path_cost")
        )


@dataclass
class AvailableAction:
    """Information about an available action and its targets."""
    template_name: str      # "Attack_MELEE_MAIN", "Dash", "Move"
    display_name: str       # "Scimitar", "Dash", "Move"
    target_type: str        # "self", "entity", "position"
    valid_targets: List[ActionTarget] = field(default_factory=list)
    can_afford: bool = True
    cost_type: str = "actions"      # "actions", "bonus_actions", "movement"
    cost_amount: int = 1
    description: str = ""
    weapon_slot: Optional[str] = None
    weapon_name: Optional[str] = None

    @property
    def command_name(self) -> str:
        """Get the command name for this action.

        'Attack_MELEE_MAIN' -> 'attack'
        'Dash' -> 'dash'
        'Move' -> 'move'
        """
        # Extract base action type from template name
        base_name = self.template_name.split("_")[0].lower()
        return base_name

    @property
    def is_attack(self) -> bool:
        """Check if this is an attack action."""
        return self.target_type == "entity" and self.template_name.startswith("Attack")

    @property
    def is_bonus_action(self) -> bool:
        """Check if this costs a bonus action."""
        return self.cost_type == "bonus_actions"

    @classmethod
    def from_server(cls, data: Dict[str, Any]) -> 'AvailableAction':
        """Parse from server AvailableActionInfo JSON."""
        targets = [ActionTarget.from_server(t) for t in data.get("valid_targets", [])]
        return cls(
            template_name=data.get("template_name", "Unknown"),
            display_name=data.get("display_name", data.get("template_name", "Unknown")),
            target_type=data.get("target_type", "self"),
            valid_targets=targets,
            can_afford=data.get("can_afford", True),
            cost_type=data.get("cost_type", "actions"),
            cost_amount=data.get("cost_amount", 1),
            description=data.get("description", ""),
            weapon_slot=data.get("weapon_slot"),
            weapon_name=data.get("weapon_name")
        )


@dataclass
class AvailableActionsState:
    """Complete available actions for an entity.

    Groups actions by type for easy access and provides convenience methods.
    """
    entity_uuid: str
    attacks: List[AvailableAction] = field(default_factory=list)
    movement: List[AvailableAction] = field(default_factory=list)
    self_actions: List[AvailableAction] = field(default_factory=list)
    remaining_movement: int = 0

    @property
    def all_actions(self) -> List[AvailableAction]:
        """Get all available actions as a flat list."""
        return self.attacks + self.movement + self.self_actions

    @property
    def affordable_attacks(self) -> List[AvailableAction]:
        """Get attacks that can be afforded and have targets."""
        return [a for a in self.attacks if a.can_afford and a.valid_targets]

    @property
    def can_attack(self) -> bool:
        """Check if any attack is available."""
        return len(self.affordable_attacks) > 0

    @property
    def can_move(self) -> bool:
        """Check if movement is available."""
        return self.remaining_movement > 0 and any(
            a.can_afford and a.valid_targets for a in self.movement
        )

    def get_action_by_command(self, command: str) -> Optional[AvailableAction]:
        """Get an action by its command name.

        Args:
            command: Command name like "dash", "dodge", "attack"

        Returns:
            First matching action, or None
        """
        for action in self.all_actions:
            if action.command_name == command.lower() and action.can_afford:
                return action
        return None

    def get_self_action(self, name: str) -> Optional[AvailableAction]:
        """Get a self-targeting action by template name."""
        for action in self.self_actions:
            if action.template_name.lower() == name.lower() and action.can_afford:
                return action
        return None

    def get_attack_target(self, index: int) -> Optional[Tuple[AvailableAction, ActionTarget]]:
        """Get attack action and target by combined index.

        When listing attacks, we number them 1, 2, 3... across all attack options.
        This method finds the action and specific target for a given number.

        Args:
            index: 1-based index (as shown to user)

        Returns:
            Tuple of (action, target) or None if invalid
        """
        current_idx = 1
        for attack in self.affordable_attacks:
            for target in attack.valid_targets:
                if current_idx == index:
                    return (attack, target)
                current_idx += 1
        return None

    def get_total_attack_count(self) -> int:
        """Get total number of attack targets across all attacks."""
        return sum(len(a.valid_targets) for a in self.affordable_attacks)

    def get_valid_commands(self) -> set:
        """Get set of valid command names based on available actions."""
        valid = {"end"}  # Always can end turn

        for action in self.all_actions:
            if action.can_afford:
                if action.target_type == "self":
                    valid.add(action.command_name)
                elif action.target_type == "entity" and action.valid_targets:
                    valid.add(action.command_name)
                elif action.target_type == "position" and action.valid_targets:
                    valid.add(action.command_name)

        return valid

    @classmethod
    def from_server(cls, data: Dict[str, Any]) -> 'AvailableActionsState':
        """Parse from server AvailableActionsResult JSON."""
        attacks = [AvailableAction.from_server(a) for a in data.get("entity_actions", [])]
        movement = [AvailableAction.from_server(a) for a in data.get("position_actions", [])]
        self_actions = [AvailableAction.from_server(a) for a in data.get("self_actions", [])]

        return cls(
            entity_uuid=data.get("entity_uuid", ""),
            attacks=attacks,
            movement=movement,
            self_actions=self_actions,
            remaining_movement=data.get("remaining_movement", 0)
        )
