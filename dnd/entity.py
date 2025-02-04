from typing import Dict, Optional, Any, List, Self, Literal, ClassVar, Union, Tuple, Callable
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field, field_validator
from enum import Enum

from dnd.blocks import (
    BaseBlock, AbilityScores, SavingThrowSet, Health, 
    Equipped, Speed, ActionEconomy,SkillSet,SkillName,AbilityName,SkillName
)
from dnd.values import ModifiableValue
from dnd.modifiers import (
    NumericalModifier, DamageType, ResistanceStatus, 
    ContextAwareCondition, BaseObject
)
from dnd.conditions import Condition
from dnd.equipment import (
    Armor, Weapon, Shield, BodyArmor, Gauntlets, Greaves,
    Boots, Amulet, Ring, Cloak, Helmet, BodyPart
)
from dnd.dice import Dice, RollType, DiceRoll

def update_or_concat_to_dict(d: Dict[str, list], kv: Tuple[str, Union[list,Any]]) -> Dict[str, list]:
    key, value = kv
    if not isinstance(value, list):
        value = [value]
    if key in d:
        d[key] += value
    else:
        d[key] = value
    return d

ContextualConditionImmunity = Callable[['Entity', Optional['Entity'],Optional[dict]], bool]


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
    
    active_conditions: Dict[str, Condition] = Field(default_factory=dict)
    condition_immunities: List[str] = Field(default_factory=list)
    contextual_condition_immunities: Dict[str, List[Tuple[str, ContextualConditionImmunity]]] = Field(default_factory=dict)
    active_conditions_by_source: Dict[str, List[str]] = Field(default_factory=dict)

    
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
    
    def get_target_entity(self,copy: bool = False) -> Optional['Entity']:
        if self.target_entity_uuid is None:
            return None
        target_entity = Entity.get(self.target_entity_uuid)
        assert isinstance(target_entity, Entity)
        return target_entity if not copy else target_entity.model_copy(deep=True)
    
    def add_condition(self, condition: Condition, context: Optional[Dict[str, Any]] = None)  -> bool:
        if condition.name is None:
            raise ValueError("Condition name is not set")
        if condition.target_entity_uuid is None:
            condition.target_entity_uuid = self.uuid
        if context is not None:
            condition.set_context(context)
        

        condition_applied = condition.apply()
        if condition_applied:
            self.active_conditions[condition.name] = condition

            self.active_conditions_by_source = update_or_concat_to_dict(self.active_conditions_by_source, (str(condition.source_entity_uuid), condition.name))
        return condition_applied
    
    def _remove_condition_from_dicts(self, condition_name: str) :
        condition = self.active_conditions.pop(condition_name)
        assert condition.source_entity_uuid is not None
        self.active_conditions_by_source[str(condition.source_entity_uuid)].remove(condition_name)
    
    

    
    def _get_bonuses_for_skill(self, skill_name: SkillName) -> Tuple[ModifiableValue,ModifiableValue,ModifiableValue,ModifiableValue]:
        proficiency_bonus = self.proficiency_bonus
        skill = self.skill_set.get_skill(skill_name)
        skill_bonus = skill.skill_bonus
        proficiency_bonus_multiplier_callable = skill._get_proficiency_converter()
        ability_name = skill.ability
        ability = self.ability_scores.get_ability(ability_name)
        ability_bonus = ability.ability_score
        ability_modifier_bonus = ability.modifier_bonus
        normalized_proficiency_bonus = proficiency_bonus.model_copy(deep=True)
        normalized_proficiency_bonus.update_normalizers(proficiency_bonus_multiplier_callable)
        return normalized_proficiency_bonus, skill_bonus, ability_bonus, ability_modifier_bonus
    
    def _get_bonuses_for_saving_throw(self, ability_name: AbilityName) -> Tuple[ModifiableValue,ModifiableValue,ModifiableValue,ModifiableValue]:
        saving_throw = self.saving_throws.get_saving_throw(ability_name)
        saving_throw_bonus = saving_throw.bonus
        proficiency_bonus_multiplier_callable = saving_throw._get_proficiency_converter()
        proficiency_bonus = self.proficiency_bonus
        ability_bonus = self.ability_scores.get_ability(ability_name).ability_score
        ability_modifier_bonus = self.ability_scores.get_ability(ability_name).modifier_bonus

        normalized_proficiency_bonus = proficiency_bonus.model_copy(deep=True)
        normalized_proficiency_bonus.update_normalizers(proficiency_bonus_multiplier_callable)
        return normalized_proficiency_bonus, saving_throw_bonus, ability_bonus,ability_modifier_bonus
    
    def saving_throw_bonus(self, target_entity_uuid: Optional[UUID], ability_name: AbilityName) -> ModifiableValue:
        if target_entity_uuid is not None:
            self.set_target_entity(target_entity_uuid)
        target_entity = None
        if self.target_entity_uuid:
            target_entity = self.get_target_entity(copy=True)
            assert isinstance(target_entity, Entity)
            target_entity.set_target_entity(self.uuid)
            saving_throw_bonuses_target = target_entity._get_bonuses_for_saving_throw(ability_name)

        saving_throw_bonuses_source =self._get_bonuses_for_saving_throw(ability_name)
        if target_entity is not None:
            for mod_source,mod_target in zip(saving_throw_bonuses_source,saving_throw_bonuses_target):
                mod_source.set_from_target(mod_target)    
        total_bonus_source = saving_throw_bonuses_source[0].combine_values(list(saving_throw_bonuses_source)[1:]).model_copy(deep=True)
        self.clear_target_entity()

        return total_bonus_source

    def skill_bonus(self, target_entity_uuid: Optional[UUID], skill_name: SkillName) -> ModifiableValue:
        if target_entity_uuid is not None:
            self.set_target_entity(target_entity_uuid)
        
        target_entity = None
        if self.target_entity_uuid:
            target_entity = self.get_target_entity(copy=True)
            assert isinstance(target_entity, Entity)
            target_entity.set_target_entity(self.uuid)
            skill_bonuses_target = target_entity._get_bonuses_for_skill(skill_name)

        skill_bonuses_source = self._get_bonuses_for_skill(skill_name)
        if target_entity is not None:
            for mod_source, mod_target in zip(skill_bonuses_source, skill_bonuses_target):
                mod_source.set_from_target(mod_target)
        
        total_bonus_source = skill_bonuses_source[0].combine_values(list(skill_bonuses_source)[1:]).model_copy(deep=True)
        self.clear_target_entity()

        return total_bonus_source

    def skill_bonus_cross(self, target_entity_uuid: UUID, skill_name: SkillName) -> Tuple[ModifiableValue, ModifiableValue]:
        self.set_target_entity(target_entity_uuid)
        target_entity = self.get_target_entity(copy=True)
        assert isinstance(target_entity, Entity)
        target_entity.set_target_entity(self.uuid)

        skill_bonuses_source = self._get_bonuses_for_skill(skill_name)
        skill_bonuses_target = target_entity._get_bonuses_for_skill(skill_name)

        for mod_source, mod_target in zip(skill_bonuses_source, skill_bonuses_target):
            mod_target.set_from_target(mod_source)
            mod_source.set_from_target(mod_target)

        total_bonus_source = skill_bonuses_source[0].combine_values(list(skill_bonuses_source)[1:]).model_copy(deep=True)
        total_bonus_target = skill_bonuses_target[0].combine_values(list(skill_bonuses_target)[1:]).model_copy(deep=True)

        self.clear_target_entity()
        target_entity.clear_target_entity()

        return total_bonus_source, total_bonus_target