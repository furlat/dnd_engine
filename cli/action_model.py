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
        # Toggle
        "tog",
        # History
        "pt", "nt", "ct", "ft",
    }

    # Preferred shortcuts for known actions - these actions will claim
    # these shortcuts if available (even if reserved for them)
    PREFERRED: Dict[str, str] = {
        # Movement
        "Move": "m",
        "Jump": "j",
        # Self actions
        "Dash": "d",
        "Dodge": "do",
        "Disengage": "di",
        "Hide": "hi",
        # Entity actions
        "Shove": "sh",
        # Spells - AoE
        "Fireball": "fb",
        "Lightning Bolt": "lb",
        "Burning Hands": "bh",
        "Thunderwave": "tw",
        "Shatter": "sha",
        # Spells - Single target
        "Fire Bolt": "fib",
        "Magic Missile": "mm",
        "Sacred Flame": "sf",
        # Spells - Self/Buff
        "Mage Armor": "ma",
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
    # AoE-specific fields (for POSITION_AOE actions)
    affected_entity_uuids: Optional[List[str]] = None
    affected_entity_names: Optional[List[str]] = None
    affected_count: Optional[int] = None
    affected_positions: Optional[List[Tuple[int, int]]] = None
    # Hazard pathfinding fields
    is_path_hazardous: bool = False
    safe_path_cost: Optional[int] = None

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
            path_cost=data.get("path_cost"),
            # AoE fields
            affected_entity_uuids=data.get("affected_entity_uuids"),
            affected_entity_names=data.get("affected_entity_names"),
            affected_count=data.get("affected_count"),
            affected_positions=[tuple(p) for p in data.get("affected_positions", [])] if data.get("affected_positions") else None,
            # Hazard fields
            is_path_hazardous=data.get("is_path_hazardous", False),
            safe_path_cost=data.get("safe_path_cost"),
        )


@dataclass
class AvailableAction:
    """Information about an available action and its targets."""
    template_name: str      # "Attack_MELEE_MAIN", "Dash", "Move"
    display_name: str       # "Scimitar", "Dash", "Move"
    target_type: str        # Full type: "self", "entity", "multi_entity", "position_path", "position_los", "position_aoe"
    valid_targets: List[ActionTarget] = field(default_factory=list)
    can_afford: bool = True
    cost_type: str = "actions"      # "actions", "bonus_actions", "movement"
    cost_amount: int = 1
    description: str = ""
    weapon_slot: Optional[str] = None
    weapon_name: Optional[str] = None
    action_category: str = "ability"  # "ability", "attack", "spell", "movement"
    is_item_use: bool = False
    source_item_uuid: Optional[str] = None
    item_stack_count: Optional[int] = None

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
        return self.action_category == "attack"

    @property
    def is_spell(self) -> bool:
        """Check if this is a spell action."""
        return self.action_category == "spell"

    @property
    def is_movement(self) -> bool:
        """Check if this is a movement action."""
        return self.action_category == "movement"

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
            target_type=data.get("target_type", "self"),  # Full target type preserved
            valid_targets=targets,
            can_afford=data.get("can_afford", True),
            cost_type=data.get("cost_type", "actions"),
            cost_amount=data.get("cost_amount", 1),
            description=data.get("description", ""),
            weapon_slot=data.get("weapon_slot"),
            weapon_name=data.get("weapon_name"),
            action_category=data.get("action_category", "ability"),
            is_item_use=data.get("is_item_use", False),
            source_item_uuid=data.get("source_item_uuid"),
            item_stack_count=data.get("item_stack_count"),
        )


@dataclass
class AvailableActionsState:
    """Complete available actions for an entity.

    Groups actions by type for easy access and provides convenience methods.
    Spells are categorized separately based on is_spell, regardless of target_type.
    """
    entity_uuid: str
    attacks: List[AvailableAction] = field(default_factory=list)
    other_entity: List[AvailableAction] = field(default_factory=list)  # Shove, etc.
    movement: List[AvailableAction] = field(default_factory=list)
    spell_actions: List[AvailableAction] = field(default_factory=list)  # All spells (any target type)
    self_actions: List[AvailableAction] = field(default_factory=list)
    item_use_actions: List[AvailableAction] = field(default_factory=list)  # Non-spell item use (potions, coats)
    object_actions: List[AvailableAction] = field(default_factory=list)  # Pick Up, Attack Object, Pull Lever
    remaining_movement: int = 0

    @property
    def all_actions(self) -> List[AvailableAction]:
        """Get all available actions as a flat list."""
        return self.attacks + self.other_entity + self.movement + self.spell_actions + self.self_actions + self.item_use_actions + self.object_actions

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
        position actions (Move, Jump, etc.), other_entity actions (Shove, etc.),
        and spell_actions.
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

        # Register spell actions (scroll spells use display_name to avoid collision with native spells)
        for action in self.spell_actions:
            if action.is_item_use:
                registry.get_or_create_shortcut(action.display_name)
            else:
                registry.get_or_create_shortcut(action.template_name)

        # Register item use actions by display_name (includes item name for uniqueness)
        for action in self.item_use_actions:
            registry.get_or_create_shortcut(action.display_name)

        # Register object actions
        for action in self.object_actions:
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

    @property
    def affordable_spells(self) -> List[AvailableAction]:
        """Get spell actions that can be afforded and have targets."""
        return [a for a in self.spell_actions if a.can_afford and a.valid_targets]

    def get_spell_action_by_command(
        self, command: str, registry: ShortcutRegistry
    ) -> Optional[AvailableAction]:
        """Find spell action by shortcut OR template_name.

        Args:
            command: User input (could be shortcut like "fb" or full name like "fireball")
            registry: Session shortcut registry

        Returns:
            Matching available action if found and affordable, None otherwise
        """
        cmd = command.lower().replace(" ", "").replace("_", "")

        # Check shortcut registry first
        registered_name = registry.get_action_by_shortcut(cmd)
        if registered_name:
            # Match by template_name (native spells) or display_name (scroll spells)
            return next(
                (a for a in self.spell_actions
                 if (a.template_name == registered_name or a.display_name == registered_name)
                 and a.can_afford),
                None
            )

        # Check full template_name or display_name (no spaces/underscores)
        for action in self.spell_actions:
            normalized_template = action.template_name.lower().replace(" ", "").replace("_", "")
            normalized_display = action.display_name.lower().replace(" ", "").replace("_", "")
            if action.can_afford and (normalized_template == cmd or normalized_display == cmd):
                return action

        return None

    def get_spell_target(self, action_name: str, index: int) -> Optional[Tuple[AvailableAction, ActionTarget]]:
        """Get spell action and target by action name and target index.

        Args:
            action_name: The template_name of the spell (e.g., "Fire Bolt")
            index: 1-based index (as shown to user)

        Returns:
            Tuple of (action, target) or None if invalid
        """
        for action in self.affordable_spells:
            if action.template_name == action_name:
                current_idx = 1
                for target in action.valid_targets:
                    if current_idx == index:
                        return (action, target)
                    current_idx += 1
        return None

    def get_spell_targets(
        self, action_name: str, indices: List[int]
    ) -> Optional[Tuple[AvailableAction, List[ActionTarget]]]:
        """Get spell action and multiple targets by action name and target indices.

        Used for multi-target spells like Magic Missile where multiple targets
        can be specified (e.g., "mm 1 2 3" distributes darts across 3 targets).

        Args:
            action_name: The template_name of the spell (e.g., "Magic Missile")
            indices: List of 1-based indices (as shown to user)

        Returns:
            Tuple of (action, [targets]) or None if invalid
        """
        for action in self.affordable_spells:
            if action.template_name == action_name:
                targets: List[ActionTarget] = []
                for idx in indices:
                    current = 1
                    found = False
                    for target in action.valid_targets:
                        if current == idx:
                            targets.append(target)
                            found = True
                            break
                        current += 1
                    if not found:
                        # Invalid index - but continue to collect what we can
                        pass
                if targets:
                    return (action, targets)
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

    def get_item_use_action_by_command(
        self, command: str, registry: ShortcutRegistry
    ) -> Optional[AvailableAction]:
        """Find item use action by shortcut or display_name.

        Item use actions are registered by display_name (e.g., "Healing Potion (Potion of Healing)").
        """
        cmd = command.lower().replace(" ", "").replace("_", "")

        # Check shortcut registry first
        registered_name = registry.get_action_by_shortcut(cmd)
        if registered_name:
            return next(
                (a for a in self.item_use_actions
                 if (a.template_name == registered_name or a.display_name == registered_name)
                 and a.can_afford),
                None
            )

        # Check display_name or template_name directly
        for action in self.item_use_actions:
            normalized_display = action.display_name.lower().replace(" ", "").replace("_", "")
            normalized_template = action.template_name.lower().replace(" ", "").replace("_", "")
            if action.can_afford and (normalized_display == cmd or normalized_template == cmd):
                return action

        return None

    def get_item_use_target(self, action_display_name: str, index: int) -> Optional[Tuple[AvailableAction, ActionTarget]]:
        """Get item use action and target by display_name and 1-based index."""
        for action in self.item_use_actions:
            if action.display_name == action_display_name and action.can_afford:
                current_idx = 1
                for target in action.valid_targets:
                    if current_idx == index:
                        return (action, target)
                    current_idx += 1
        return None

    def get_object_action_by_command(
        self, command: str, registry: ShortcutRegistry
    ) -> Optional[AvailableAction]:
        """Find object action by shortcut or template_name."""
        cmd = command.lower().replace(" ", "").replace("_", "")

        # Check shortcut registry first
        registered_name = registry.get_action_by_shortcut(cmd)
        if registered_name:
            return next(
                (a for a in self.object_actions
                 if a.template_name == registered_name and a.can_afford),
                None
            )

        # Check template_name directly
        for action in self.object_actions:
            normalized_name = action.template_name.lower().replace(" ", "").replace("_", "")
            if action.can_afford and normalized_name == cmd:
                return action

        return None

    def get_object_action_target(self, template_name: str, index: int) -> Optional[Tuple[AvailableAction, ActionTarget]]:
        """Get object action and target by template_name and 1-based index."""
        for action in self.object_actions:
            if action.template_name == template_name and action.can_afford:
                current_idx = 1
                for target in action.valid_targets:
                    if current_idx == index:
                        return (action, target)
                    current_idx += 1
        return None

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
        """Parse from server AvailableActionsResult JSON.

        Categorizes actions by is_spell FIRST, then by is_attack for non-spells.
        Spells go to spell_actions regardless of target_type.
        Non-spell entity actions split into attacks (is_attack=True) and other_entity.
        Non-spell position actions go to movement.
        """
        # Parse all actions
        all_entity_actions = [AvailableAction.from_server(a) for a in data.get("entity_actions", [])]
        all_position_actions = [AvailableAction.from_server(a) for a in data.get("position_actions", [])]
        all_self_actions = [AvailableAction.from_server(a) for a in data.get("self_actions", [])]
        all_object_actions = [AvailableAction.from_server(a) for a in data.get("object_actions", [])]

        # Spells go to spell_actions regardless of target_type (includes scroll spells)
        spell_actions: List[AvailableAction] = []
        for a in all_entity_actions + all_position_actions + all_self_actions:
            if a.is_spell:
                spell_actions.append(a)

        # Non-spell item use actions go to item_use_actions (potions, weapon coats, etc.)
        item_use_actions: List[AvailableAction] = []
        for a in all_entity_actions + all_self_actions:
            if a.is_item_use and not a.is_spell:
                item_use_actions.append(a)

        # Non-spell, non-item-use entity actions
        attacks = [a for a in all_entity_actions if a.is_attack and not a.is_spell and not a.is_item_use]
        other_entity = [a for a in all_entity_actions if not a.is_attack and not a.is_spell and not a.is_item_use]

        # Non-spell position actions = movement
        movement = [a for a in all_position_actions if not a.is_spell]

        # Non-spell, non-item-use self actions
        self_actions = [a for a in all_self_actions if not a.is_spell and not a.is_item_use]

        return cls(
            entity_uuid=data.get("entity_uuid", ""),
            attacks=attacks,
            other_entity=other_entity,
            movement=movement,
            spell_actions=spell_actions,
            self_actions=self_actions,
            item_use_actions=item_use_actions,
            object_actions=all_object_actions,
            remaining_movement=data.get("remaining_movement", 0)
        )
