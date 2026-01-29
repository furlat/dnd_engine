from typing import Optional, List, Tuple, Dict
from uuid import UUID, uuid4
from enum import Enum
from pydantic import BaseModel, Field
from dnd.core.values import ModifiableValue
from dnd.core.modifiers import NumericalModifier
from dnd.core.base_actions import CostType

from dnd.core.base_block import BaseBlock


class RechargeType(str, Enum):
    """When a resource recharges to its maximum value."""
    SHORT_REST = "short_rest"
    LONG_REST = "long_rest"
    TURN_START = "turn_start"
    NEVER = "never"


class Resource(BaseModel):
    """
    A limited-use resource (e.g., Second Wind, spell slots).

    Attributes:
        name: Resource identifier
        current: Current uses remaining
        maximum: Maximum uses
        recharge_type: When the resource recharges
    """
    name: str
    current: int
    maximum: int
    recharge_type: RechargeType

    def can_afford(self, amount: int = 1) -> bool:
        """Check if resource has enough uses."""
        return self.current >= amount

    def consume(self, amount: int = 1) -> bool:
        """Consume uses. Returns True if successful, False if not enough."""
        if not self.can_afford(amount):
            return False
        self.current -= amount
        return True

    def recharge(self) -> None:
        """Restore resource to maximum."""
        self.current = self.maximum

class ActionEconomyConfig(BaseModel):
    """
    Configuration for the ActionEconomy block.
    """
    actions: int = Field(default=1, description="Number of standard actions available")
    actions_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the actions")
    bonus_actions: int = Field(default=1, description="Number of bonus actions available")
    bonus_actions_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the bonus actions")
    reactions: int = Field(default=1, description="Number of reactions available")
    reactions_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the reactions")
    movement: int = Field(default=30, description="Amount of movement available")
    movement_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the movement")
    # Spell slots (default 0 for non-casters)
    spell_slots: Dict[int, int] = Field(
        default_factory=dict,
        description="Spell slot counts by level (1-9). E.g., {1: 4, 2: 3} for 4 L1 slots and 3 L2 slots"
    )
    

class ActionEconomy(BaseBlock):
    """
    Represents the action economy of an entity in the game system.

    This class extends BaseBlock to represent the various actions available to an entity
    during their turn.

    Attributes:
        name (str): The name of this action economy block. Defaults to "ActionEconomy".
        actions (ModifiableValue): Number of standard actions available, typically 1.
        bonus_actions (ModifiableValue): Number of bonus actions available, typically 1.
        reactions (ModifiableValue): Number of reactions available, typically 1.
        movement (ModifiableValue): Amount of movement available, typically 30 feet.
        spell_slot_1-9 (ModifiableValue): Spell slots by level (base=0 for non-casters).
    """
    name: str = Field(default="ActionEconomy")
    actions: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=1,
            value_name="Actions"
        )
    )
    bonus_actions: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=1,
            value_name="Bonus Actions"
        )
    )
    reactions: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=1,
            value_name="Reactions"
        )
    )
    movement: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=30,
            value_name="Movement"
        )
    )
    # Spell slots (base=0 for non-casters, modified by class features)
    spell_slot_1: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 1")
    )
    spell_slot_2: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 2")
    )
    spell_slot_3: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 3")
    )
    spell_slot_4: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 4")
    )
    spell_slot_5: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 5")
    )
    spell_slot_6: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 6")
    )
    spell_slot_7: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 7")
    )
    spell_slot_8: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 8")
    )
    spell_slot_9: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 9")
    )
    resources: Dict[str, Resource] = Field(default_factory=dict)

    # =========================================================================
    # Resource Management Methods
    # =========================================================================

    def add_resource(self, name: str, maximum: int, recharge_type: RechargeType) -> None:
        """Add a new resource (e.g., 'second_wind' with max 1)."""
        self.resources[name] = Resource(
            name=name,
            current=maximum,
            maximum=maximum,
            recharge_type=recharge_type
        )

    def remove_resource(self, name: str) -> None:
        """Remove a resource by name."""
        self.resources.pop(name, None)

    def has_resource(self, name: str) -> bool:
        """Check if a resource exists."""
        return name in self.resources

    def can_afford_resource(self, name: str, amount: int = 1) -> bool:
        """Check if a resource has enough uses remaining."""
        resource = self.resources.get(name)
        if resource is None:
            return False
        return resource.can_afford(amount)

    def consume_resource(self, name: str, amount: int = 1) -> bool:
        """Consume uses of a resource. Returns True if successful."""
        resource = self.resources.get(name)
        if resource is None:
            return False
        return resource.consume(amount)

    def get_resource_current(self, name: str) -> int:
        """Get current uses of a resource. Returns 0 if not found."""
        resource = self.resources.get(name)
        return resource.current if resource else 0

    def on_short_rest(self) -> None:
        """Recharge resources that recharge on short rest."""
        for resource in self.resources.values():
            if resource.recharge_type in (RechargeType.SHORT_REST, RechargeType.LONG_REST):
                resource.recharge()

    def on_long_rest(self) -> None:
        """Recharge resources that recharge on long rest."""
        for resource in self.resources.values():
            if resource.recharge_type == RechargeType.LONG_REST:
                resource.recharge()

    def on_turn_start(self) -> None:
        """Recharge resources that recharge on turn start."""
        for resource in self.resources.values():
            if resource.recharge_type == RechargeType.TURN_START:
                resource.recharge()

    # =========================================================================
    # Turn-Based Action Economy Methods
    # =========================================================================

    def _get_spell_slot_value(self, level: int) -> ModifiableValue:
        """Get the ModifiableValue for a spell slot level."""
        slot_map = {
            1: self.spell_slot_1, 2: self.spell_slot_2, 3: self.spell_slot_3,
            4: self.spell_slot_4, 5: self.spell_slot_5, 6: self.spell_slot_6,
            7: self.spell_slot_7, 8: self.spell_slot_8, 9: self.spell_slot_9,
        }
        if level not in slot_map:
            raise ValueError(f"Invalid spell slot level: {level}")
        return slot_map[level]

    def _get_value_for_cost_type(self, cost_type: CostType) -> ModifiableValue:
        """Get the ModifiableValue for a cost type."""
        if cost_type == "actions":
            return self.actions
        elif cost_type == "bonus_actions":
            return self.bonus_actions
        elif cost_type == "reactions":
            return self.reactions
        elif cost_type == "movement":
            return self.movement
        elif cost_type.startswith("spell_slot_"):
            level = int(cost_type.split("_")[-1])
            return self._get_spell_slot_value(level)
        else:
            raise ValueError(f"Unknown cost type: {cost_type}")

    def get_base_value(self, cost_type: CostType) -> int:
        """Get the base value for a given action type."""
        value = self._get_value_for_cost_type(cost_type)
        base_mod = value.get_base_modifier()
        return base_mod.normalized_value if base_mod else 0

    def get_cost_modifiers(self, cost_type: CostType) -> List[NumericalModifier]:
        """Get all cost modifiers (negative values) for a given action type."""
        value = self._get_value_for_cost_type(cost_type)
        return [mod for mod in value.self_static.value_modifiers.values()
                if mod.name is not None and "cost" in mod.name]

    def can_afford(self, cost_type: CostType, amount: int) -> bool:
        """Check if the entity can afford a given action type and amount.

        Uses value.normalized_score which accounts for all modifiers including
        max constraints from conditions like Incapacitated.
        """
        value = self._get_value_for_cost_type(cost_type)
        return value.normalized_score - amount >= 0

    def reset_all_costs(self) -> None:
        """Reset turn-based costs (actions, bonus_actions, reactions, movement).

        Called at the start of each turn. Does NOT reset spell slot costs -
        use reset_spell_slot_costs() for long rest.
        """
        turn_based_types: List[CostType] = ["actions", "bonus_actions", "reactions", "movement"]
        for cost_type in turn_based_types:
            value = self._get_value_for_cost_type(cost_type)
            for modifier in self.get_cost_modifiers(cost_type):
                value.self_static.remove_value_modifier(modifier.uuid)

    def reset_spell_slot_costs(self) -> None:
        """Reset spell slot costs (restore all spell slots).

        Called on long rest.
        """
        for level in range(1, 10):
            cost_type: CostType = f"spell_slot_{level}"  # type: ignore
            value = self._get_spell_slot_value(level)
            for modifier in self.get_cost_modifiers(cost_type):
                value.self_static.remove_value_modifier(modifier.uuid)

    def consume(self, cost_type: CostType, amount: int, cost_name: Optional[str] = None) -> None:
        """Consume an action resource."""
        value = self._get_value_for_cost_type(cost_type)
        if value.self_static.normalized_score - amount < 0:
            raise ValueError(f"Not enough {cost_type} to consume {amount} {cost_name if cost_name is not None else 'cost'}")

        modifier_name = f"{cost_name}_cost" if cost_name is not None else "cost"
        cost_modifier = NumericalModifier.create(
            source_entity_uuid=self.source_entity_uuid,
            name=modifier_name,
            value=-amount
        )
        value.self_static.add_value_modifier(cost_modifier)

    @classmethod
    def create(cls, source_entity_uuid: UUID, name: str = "ActionEconomy", source_entity_name: Optional[str] = None,
               target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None,
               config: Optional[ActionEconomyConfig] = None) -> 'ActionEconomy':
        """Create a new ActionEconomy instance."""
        if config is None:
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name,
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name)
        else:
            actions = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.actions, value_name="Actions")
            for modifier in config.actions_modifiers:
                actions.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))

            bonus_actions = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.bonus_actions, value_name="Bonus Actions")
            for modifier in config.bonus_actions_modifiers:
                bonus_actions.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))

            reactions = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.reactions, value_name="Reactions")
            for modifier in config.reactions_modifiers:
                reactions.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))

            movement = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.movement, value_name="Movement")
            for modifier in config.movement_modifiers:
                movement.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))

            # Create spell slot ModifiableValues
            spell_slot_1 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(1, 0), value_name="Spell Slot 1")
            spell_slot_2 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(2, 0), value_name="Spell Slot 2")
            spell_slot_3 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(3, 0), value_name="Spell Slot 3")
            spell_slot_4 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(4, 0), value_name="Spell Slot 4")
            spell_slot_5 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(5, 0), value_name="Spell Slot 5")
            spell_slot_6 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(6, 0), value_name="Spell Slot 6")
            spell_slot_7 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(7, 0), value_name="Spell Slot 7")
            spell_slot_8 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(8, 0), value_name="Spell Slot 8")
            spell_slot_9 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(9, 0), value_name="Spell Slot 9")

            return cls(
                source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name,
                target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name,
                actions=actions, bonus_actions=bonus_actions, reactions=reactions, movement=movement,
                spell_slot_1=spell_slot_1, spell_slot_2=spell_slot_2, spell_slot_3=spell_slot_3,
                spell_slot_4=spell_slot_4, spell_slot_5=spell_slot_5, spell_slot_6=spell_slot_6,
                spell_slot_7=spell_slot_7, spell_slot_8=spell_slot_8, spell_slot_9=spell_slot_9,
            )
