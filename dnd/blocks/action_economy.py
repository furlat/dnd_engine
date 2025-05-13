from typing import Dict, Optional, Any, List, Self, Literal,ClassVar, Union, Callable, Tuple
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field,field_validator
from dnd.core.values import ModifiableValue, StaticValue
from dnd.core.modifiers import NumericalModifier, DamageType , ResistanceStatus, ContextAwareCondition, BaseObject, saving_throws, ResistanceModifier
from dnd.core.base_actions import CostType
from enum import Enum
from random import randint
from functools import cached_property
from typing import Literal as TypeLiteral


from dnd.core.base_block import BaseBlock

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

    def get_base_value(self, cost_type: CostType) -> int:
        """Get the base value for a given action type."""
        if cost_type == "actions":
            base_mod = self.actions.get_base_modifier()
        elif cost_type == "bonus_actions":
            base_mod = self.bonus_actions.get_base_modifier()
        elif cost_type == "reactions":
            base_mod = self.reactions.get_base_modifier()
        elif cost_type == "movement":
            base_mod = self.movement.get_base_modifier()
        else:
            raise ValueError(f"Unknown cost type: {cost_type}")
        
        return base_mod.normalized_value if base_mod else 0

    def get_cost_modifiers(self, cost_type: CostType) -> List[NumericalModifier]:
        """Get all cost modifiers (negative values) for a given action type."""
        if cost_type == "actions":
            value = self.actions
        elif cost_type == "bonus_actions":
            value = self.bonus_actions
        elif cost_type == "reactions":
            value = self.reactions
        elif cost_type == "movement":
            value = self.movement
        else:
            raise ValueError(f"Unknown cost type: {cost_type}")
        return [mod for mod in value.self_static.value_modifiers.values() 
                if mod.name is not None and "cost" in mod.name]
    
    def can_afford(self, cost_type: CostType, amount: int) -> bool:
        """Check if the entity can afford a given action type and amount."""
        if cost_type == "actions":
            print("actions cazzo minchia",self.actions.self_static.normalized_score,amount)
            return self.actions.self_static.normalized_score - amount >= 0
        elif cost_type == "bonus_actions":
            return self.bonus_actions.self_static.normalized_score - amount >= 0
        elif cost_type == "reactions":
            return self.reactions.self_static.normalized_score - amount >= 0
        elif cost_type == "movement":
            return self.movement.self_static.normalized_score - amount >= 0

    def reset_all_costs(self):
        """Reset the cost for a given action type."""
        all_cost_modifiers = self.get_cost_modifiers("actions") + self.get_cost_modifiers("bonus_actions") + self.get_cost_modifiers("reactions") + self.get_cost_modifiers("movement")
        for modifier in all_cost_modifiers:
            self.actions.self_static.remove_value_modifier(modifier.uuid)

            self.bonus_actions.self_static.remove_value_modifier(modifier.uuid)
    
            self.reactions.self_static.remove_value_modifier(modifier.uuid)
            self.movement.self_static.remove_value_modifier(modifier.uuid)
        

    def consume(self, cost_type: CostType, amount: int, cost_name: Optional[str] = None):
        """Consume an action resource."""
        modifier_name = f"{cost_name}_cost" if cost_name is not None else "cost"
        cost_modifier = NumericalModifier.create(
            source_entity_uuid=self.source_entity_uuid, 
            name=modifier_name, 
            value=-amount
        )
        
        if cost_type == "actions":
            if self.actions.self_static.normalized_score - amount < 0:
                raise ValueError(f"Not enough actions to consume {amount} {cost_name if cost_name is not None else 'cost'}")
            self.actions.self_static.add_value_modifier(cost_modifier)
        elif cost_type == "bonus_actions":
            if self.bonus_actions.self_static.normalized_score - amount < 0:
                raise ValueError(f"Not enough bonus actions to consume {amount} {cost_name if cost_name is not None else 'cost'}")
            self.bonus_actions.self_static.add_value_modifier(cost_modifier)
        elif cost_type == "reactions":
            if self.reactions.self_static.normalized_score - amount < 0:
                raise ValueError(f"Not enough reactions to consume {amount} {cost_name if cost_name is not None else 'cost'}")
            self.reactions.self_static.add_value_modifier(cost_modifier)
        elif cost_type == "movement":
            if self.movement.self_static.normalized_score - amount < 0:
                raise ValueError(f"Not enough movement to consume {amount} {cost_name if cost_name is not None else 'cost'}")
            self.movement.self_static.add_value_modifier(cost_modifier)

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
            
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name,
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name,
                       actions=actions, bonus_actions=bonus_actions, reactions=reactions, movement=movement)
