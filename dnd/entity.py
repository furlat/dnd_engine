from typing import Dict, Optional, Any, List, Self, Literal, ClassVar, Union
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field, field_validator
from enum import Enum

from dnd.blocks import (
    BaseBlock, AbilityScores, SavingThrowSet, Health, 
    Equipped, Speed, ActionEconomy,SkillSet,SkillName
)
from dnd.values import ModifiableValue
from dnd.modifiers import (
    NumericalModifier, DamageType, ResistanceStatus, 
    ContextAwareCondition, BaseObject
)

from dnd.equipment import (
    Armor, Weapon, Shield, BodyArmor, Gauntlets, Greaves,
    Boots, Amulet, Ring, Cloak, Helmet, BodyPart
)
from dnd.dice import Dice, RollType, DiceRoll
class Entity(BaseBlock):
    """ Base class for dnd entities in the game it acts as container for blocks and implements common functionalities that
    require interactions between blocks """
    
    name: str = Field(default="Entity")
    ability_scores: AbilityScores = Field(default_factory=lambda: AbilityScores.create(source_entity_uuid=uuid4()))
    skill_set: SkillSet = Field(default_factory=lambda: SkillSet.create(source_entity_uuid=uuid4()))
    saving_throws: SavingThrowSet = Field(default_factory=lambda: SavingThrowSet.create(source_entity_uuid=uuid4()))
    health: Health = Field(default_factory=lambda: Health.create(source_entity_uuid=uuid4()))
    equipped: Equipped = Field(default_factory=lambda: Equipped.create(source_entity_uuid=uuid4()))
    speed: Speed = Field(default_factory=lambda: Speed.create(source_entity_uuid=uuid4()))
    action_economy: ActionEconomy = Field(default_factory=lambda: ActionEconomy.create(source_entity_uuid=uuid4()))
    proficiency_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),value_name="proficiency_bonus",base_value=2))
    

    
    @classmethod
    def create(cls, source_entity_uuid: UUID, name: str = "Entity") -> 'Entity':
        """
        Create a new Entity instance with the given parameters. All sub-blocks will share
        the same source_entity_uuid as the entity itself.

        Args:
            source_entity_uuid (UUID): The UUID that will be used as both the entity's UUID and source_entity_uuid
            name (str): The name of the entity. Defaults to "Entity"

        Returns:
            Entity: The newly created Entity instance
        """
        return cls(
            uuid=source_entity_uuid,
            source_entity_uuid=source_entity_uuid,
            name=name)
    
    def get_target_entity(self) -> Optional['Entity']:
        if self.target_entity_uuid is None:
            return None
        target_entity = Entity.get(self.target_entity_uuid)
        assert isinstance(target_entity, Entity)
        return target_entity 