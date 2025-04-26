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


class SpeedConfig(BaseModel):
    """
    Configuration for the Speed block.
    """
    walk: int = Field(default=30, description="Walk Speed")
    walk_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the walk speed")
    fly: int = Field(default=0, description="Fly Speed")
    fly_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the fly speed")
    swim: int = Field(default=0, description="Swim Speed")
    swim_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the swim speed")
    burrow: int = Field(default=0, description="Burrow Speed")
    burrow_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the burrow speed")
    climb: int = Field(default=0, description="Climb Speed")
    climb_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the climb speed")

class Speed(BaseBlock):
    """
    Represents the movement speeds of an entity in the game system.

    This class extends BaseBlock to represent various types of movement speeds.

    Attributes:
        name (str): The name of this speed block. Defaults to "Speed".
        walk (ModifiableValue): Base walking speed, typically 30 feet.
        fly (ModifiableValue): Flying speed, if any.
        swim (ModifiableValue): Swimming speed, if any.
        burrow (ModifiableValue): Burrowing speed, if any.
        climb (ModifiableValue): Climbing speed, if any.
    """
    name: str = Field(default="Speed")
    walk: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=30,
            value_name="Walk Speed"
        )
    )
    fly: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=0,
            value_name="Fly Speed"
        )
    )
    swim: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=0,
            value_name="Swim Speed"
        )
    )
    burrow: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=0,
            value_name="Burrow Speed"
        )
    )
    climb: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=0,
            value_name="Climb Speed"
        )
    )

    @classmethod
    def create(cls, source_entity_uuid: UUID, name: str = "Speed", source_entity_name: Optional[str] = None, 
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
                config: Optional[SpeedConfig] = None) -> 'Speed':
        """
        Create a new Speed instance with the given parameters.
        """
        if config is None:
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name)
        else:
            walk = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.walk, value_name="Walk Speed")
            for modifier in config.walk_modifiers:
                walk.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            fly = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.fly, value_name="Fly Speed")
            for modifier in config.fly_modifiers:
                fly.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            swim = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.swim, value_name="Swim Speed")
            for modifier in config.swim_modifiers:
                swim.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            burrow = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.burrow, value_name="Burrow Speed")
            for modifier in config.burrow_modifiers:
                burrow.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            climb = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.climb, value_name="Climb Speed")
            for modifier in config.climb_modifiers:
                climb.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, 
                       walk=walk, fly=fly, swim=swim, burrow=burrow, climb=climb)
