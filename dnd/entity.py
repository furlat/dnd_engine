from typing import Dict, Optional, Any, List, Self, Literal, ClassVar, Union
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field, field_validator
from enum import Enum

from dnd.blocks import (
    BaseBlock, AbilityScores, SavingThrowSet, Health, 
    Equipped, Speed, ActionEconomy,SkillSet,skill_names
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
    proficiency_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),value_name="proficiency_bonus",base_value=0))


    # No need for post_init as BaseBlock.set_values_and_blocks_source already handles this
    def skill_roll(self, skill_name: skill_names, target: Union['Entity', UUID, None] = None) -> DiceRoll:
        """
        Perform a skill check roll using a d20 and adding relevant modifiers.
        
        Args:
            skill_name (str): The name of the skill to roll for
            target (Union[Entity, UUID, None]): The target entity or its UUID, if any
            
        Returns:
            DiceRoll: The result of the skill check roll
            
        Raises:
            ValueError: If the skill name is invalid
        """
        # Get target UUID if an Entity was passed
        target_uuid = target.uuid if isinstance(target, Entity) else target
        assert target_uuid is not None, "Target UUID cannot be None"
        target_entity = Entity.get(target_uuid)

        


        #bonus for a skill roll is composed by
        # proficiency bonus
        proficiency_bonus = self.proficiency_bonus
        proficiency_bonus_multiplier = self.skill_set.get_skill(skill_name)._get_proficiency_converter()
        temporary_proficiency_bonus = proficiency_bonus.model_copy(update={"self_static.score_normalizer":lambda x: x*proficiency_bonus_multiplier})
        self_skill_bonus = self.skill_set.get_skill(skill_name).skill_bonus
        # modfier from skill

        # modifier from proficiency
        # modifier from target skill
        
        # Create a d20 for the roll
        d20 = Dice(
            count=1,
            value=20,
            bonus=ModifiableValue.create(
                source_entity_uuid=self.uuid,
                target_entity_uuid=target_uuid,
                base_value=self.proficiency_bonus.score,  # Add proficiency bonus
                value_name=f"{skill_name} check"
            ),
            roll_type=RollType.CHECK
        )
        
        # Perform the roll
        roll_result = d20.roll
        
        return roll_result 