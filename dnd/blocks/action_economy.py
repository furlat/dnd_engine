from typing import Dict, Optional, Any, List, Self, Literal,ClassVar, Union, Callable, Tuple
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field,field_validator
from dnd.core.values import ModifiableValue, StaticValue
from dnd.core.modifiers import NumericalModifier, DamageType , ResistanceStatus, ContextAwareCondition, BaseObject, saving_throws, ResistanceModifier

from enum import Enum
from random import randint
from functools import cached_property
from typing import Literal as TypeLiteral


from dnd.blocks.base_block import BaseBlock

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

    @classmethod
    def create(cls, source_entity_uuid: UUID, name: str = "ActionEconomy", source_entity_name: Optional[str] = None, 
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
                config: Optional[ActionEconomyConfig] = None) -> 'ActionEconomy':

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
