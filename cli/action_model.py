"""
Unified action data structures for CLI.

These dataclasses parse the server's AvailableActionsResult into a format
that's easy to work with in the CLI. They're decoupled from the server
implementation and provide convenience methods for command parsing.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple


class ShortcutRegistry:
    """Session-stable registry mapping actions to shortcuts.

    Once an action gets a shortcut, it keeps it for the entire session.
    This ensures consistent shortcuts even as actions become available/unavailable.
    """

    # Reserved shortcuts - these have fixed meanings and cannot be auto-assigned
    # to other actions. They can only be used by their designated actions.
    RESERVED = {
        # Position actions (hardcoded for consistency)
        "m",    # Move
        "j",    # Jump
        # Entity actions
        "a",    # Attack (number-indexed)
        # Turn management
        "e",    # End turn
        # Meta commands
        "s", "h", "q", "?",
        "la", "list",
        # History
        "pt", "nt", "ct", "ft",
    }

    # Preferred shortcuts for known actions - these actions will claim
    # these shortcuts if available (even if reserved for them)
    PREFERRED: Dict[str, str] = {
        "Move": "m",
        "Jump": "j",
        "Dash": "d",
        "Dodge": "do",
        "Disengage": "di",
        "Shove": "sh",
    }

    def __init__(self):
        self._action_to_shortcut: Dict[str, str] = {}  # template_name -> shortcut
        self._shortcut_to_action: Dict[str, str] = {}  # shortcut -> template_name

    def get_or_create_shortcut(self, template_name: str) -> str:
        """Get existing shortcut or create a new one.

        Multi-word names use full initials (Second Wind -> sw).
        Single-word names start with first letter and expand as needed.
        Reserved shortcuts can only be used by their designated actions.
        """
        if template_name in self._action_to_shortcut:
            return self._action_to_shortcut[template_name]

        # Check for preferred shortcut first
        preferred = self.PREFERRED.get(template_name)
        if preferred and preferred not in self._shortcut_to_action:
            # Preferred shortcut is available - use it
            self._register(template_name, preferred)
            return preferred

        # Generate new shortcut, avoiding reserved and used shortcuts
        words = template_name.split()
        if len(words) > 1:
            # Multi-word: use full initials (e.g., "Second Wind" -> "sw")
            base = "".join(w[0].lower() for w in words if w)
            shortcut = base  # Start with full initials
        else:
            # Single-word: start with first letter
            base = words[0].lower() if words else "x"
            shortcut = base[0]

        # Find non-colliding shortcut (skip reserved AND used shortcuts)
        i = 2
        original_shortcut = shortcut
        while shortcut in self._shortcut_to_action or self._is_reserved_for_other(shortcut, template_name):
            if len(words) > 1:
                # Multi-word collision: append number
                shortcut = original_shortcut + str(i - 1)
            elif i <= len(base):
                # Single-word: expand to more letters
                shortcut = base[:i]
            else:
                # Fallback: append number
                shortcut = base + str(i - len(base))
            i += 1

        # Register
        self._register(template_name, shortcut)
        return shortcut

    def _is_reserved_for_other(self, shortcut: str, template_name: str) -> bool:
        """Check if a shortcut is reserved for a different action.

        A reserved shortcut can only be used by its designated action
        (via PREFERRED mapping).
        """
        if shortcut not in self.RESERVED:
            return False

        # Check if this action is the designated owner of this reserved shortcut
        preferred_shortcut = self.PREFERRED.get(template_name)
        return preferred_shortcut != shortcut

    def _register(self, template_name: str, shortcut: str) -> None:
        """Register a shortcut mapping."""
        self._action_to_shortcut[template_name] = shortcut
        self._shortcut_to_action[shortcut] = template_name

    def get_action_by_shortcut(self, shortcut: str) -> Optional[str]:
        """Get template_name for a shortcut."""
        return self._shortcut_to_action.get(shortcut.lower())

    def get_all_actions(self) -> Dict[str, str]:
        """Get all registered actions with their shortcuts (template_name -> shortcut)."""
        return dict(self._action_to_shortcut)


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
    other_entity: List[AvailableAction] = field(default_factory=list)  # Shove, etc.
    movement: List[AvailableAction] = field(default_factory=list)
    self_actions: List[AvailableAction] = field(default_factory=list)
    remaining_movement: int = 0

    @property
    def all_actions(self) -> List[AvailableAction]:
        """Get all available actions as a flat list."""
        return self.attacks + self.other_entity + self.movement + self.self_actions

    @property
    def affordable_attacks(self) -> List[AvailableAction]:
        """Get attacks that can be afforded and have targets."""
        return [a for a in self.attacks if a.can_afford and a.valid_targets]

    @property
    def affordable_other_entity(self) -> List[AvailableAction]:
        """Get other entity-targeting actions (Shove, etc.) that can be afforded and have targets."""
        return [a for a in self.other_entity if a.can_afford and a.valid_targets]

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

    def register_actions(self, registry: ShortcutRegistry) -> None:
        """Register all actions with the session registry.

        This should be called after fetching actions to ensure all available
        actions have stable shortcuts assigned. Registers self_actions,
        position actions (Move, Jump, etc.), and other_entity actions (Shove, etc.).
        """
        # Register self_actions
        for action in self.self_actions:
            registry.get_or_create_shortcut(action.template_name)

        # Register position actions (movement)
        for action in self.movement:
            registry.get_or_create_shortcut(action.template_name)

        # Register other entity-targeting actions (Shove, etc.)
        for action in self.other_entity:
            registry.get_or_create_shortcut(action.template_name)

    def get_self_action_by_command(
        self, command: str, registry: ShortcutRegistry
    ) -> Optional[AvailableAction]:
        """Find self_action by shortcut OR template_name.

        Args:
            command: User input (could be shortcut like "sw" or full name like "secondwind")
            registry: Session shortcut registry

        Returns:
            Matching available action if found and affordable, None otherwise
        """
        cmd = command.lower().replace(" ", "").replace("_", "")

        # Check shortcut registry first
        template = registry.get_action_by_shortcut(cmd)
        if template:
            return next(
                (a for a in self.self_actions if a.template_name == template and a.can_afford),
                None
            )

        # Check full template_name (no spaces/underscores)
        for action in self.self_actions:
            normalized_name = action.template_name.lower().replace(" ", "").replace("_", "")
            if action.can_afford and normalized_name == cmd:
                return action

        return None

    def get_position_action_by_command(
        self, command: str, registry: ShortcutRegistry
    ) -> Optional[AvailableAction]:
        """Find position action by shortcut OR template_name.

        Args:
            command: User input (could be shortcut like "m" or full name like "move")
            registry: Session shortcut registry

        Returns:
            Matching available action if found and affordable, None otherwise
        """
        cmd = command.lower().replace(" ", "").replace("_", "")

        # Path 1: Check shortcut registry (e.g., "j" → "Jump")
        template = registry.get_action_by_shortcut(cmd)
        if template:
            for action in self.movement:
                if action.template_name == template and action.can_afford:
                    return action

        # Path 2: Check template_name directly (e.g., "jump" → "Jump")
        for action in self.movement:
            if action.template_name.lower() == cmd and action.can_afford:
                return action

        return None

    def get_other_entity_action_by_command(
        self, command: str, registry: ShortcutRegistry
    ) -> Optional[AvailableAction]:
        """Find other_entity action (Shove, etc.) by shortcut OR template_name.

        Args:
            command: User input (could be shortcut like "s" or full name like "shove")
            registry: Session shortcut registry

        Returns:
            Matching available action if found and affordable, None otherwise
        """
        cmd = command.lower().replace(" ", "").replace("_", "")

        # Check shortcut registry first
        template = registry.get_action_by_shortcut(cmd)
        if template:
            return next(
                (a for a in self.other_entity if a.template_name == template and a.can_afford),
                None
            )

        # Check full template_name (no spaces/underscores)
        for action in self.other_entity:
            normalized_name = action.template_name.lower().replace(" ", "").replace("_", "")
            if action.can_afford and normalized_name == cmd:
                return action

        return None

    def get_other_entity_target(self, action_name: str, index: int) -> Optional[Tuple[AvailableAction, ActionTarget]]:
        """Get other_entity action and target by action name and target index.

        Args:
            action_name: The template_name of the action (e.g., "Shove")
            index: 1-based index (as shown to user)

        Returns:
            Tuple of (action, target) or None if invalid
        """
        for action in self.affordable_other_entity:
            if action.template_name == action_name:
                current_idx = 1
                for target in action.valid_targets:
                    if current_idx == index:
                        return (action, target)
                    current_idx += 1
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
        # Split entity_actions: Attack_* -> attacks, everything else -> other_entity
        all_entity_actions = [AvailableAction.from_server(a) for a in data.get("entity_actions", [])]
        attacks = [a for a in all_entity_actions if a.template_name.startswith("Attack")]
        other_entity = [a for a in all_entity_actions if not a.template_name.startswith("Attack")]

        movement = [AvailableAction.from_server(a) for a in data.get("position_actions", [])]
        self_actions = [AvailableAction.from_server(a) for a in data.get("self_actions", [])]

        return cls(
            entity_uuid=data.get("entity_uuid", ""),
            attacks=attacks,
            other_entity=other_entity,
            movement=movement,
            self_actions=self_actions,
            remaining_movement=data.get("remaining_movement", 0)
        )
