from typing import Dict, Optional, Any, List, Self, Literal, ClassVar, Union, Tuple, Callable
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field, field_validator
from enum import Enum

from dnd.blocks import (
    BaseBlock, AbilityScores, SavingThrowSet, Health, 
    Equipment, Speed, ActionEconomy,SkillSet,SkillName,AbilityName,SkillName,WeaponSlot,RangeType,WeaponProperty, Range
)
from dnd.values import ModifiableValue
from dnd.modifiers import (
    NumericalModifier, DamageType, ResistanceStatus, 
    ContextAwareCondition, BaseObject
)
from dnd.conditions import Condition

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
    equipment: Equipment = Field(default_factory=lambda: Equipment.create(source_entity_uuid=uuid4()))
    speed: Speed = Field(default_factory=lambda: Speed.create(source_entity_uuid=uuid4()))
    action_economy: ActionEconomy = Field(default_factory=lambda: ActionEconomy.create(source_entity_uuid=uuid4()))
    proficiency_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),value_name="proficiency_bonus",base_value=2))
    
    active_conditions: Dict[str, Condition] = Field(default_factory=dict)
    condition_immunities: List[Tuple[str,Optional[str]]] = Field(default_factory=list)
    contextual_condition_immunities: Dict[str, List[Tuple[str,ContextualConditionImmunity]]] = Field(default_factory=dict)
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
    
    def check_condition_immunity(self, condition_name: str) -> bool:
        #first check static immunities
        for static_immunity in self.condition_immunities:
            if static_immunity[0] == condition_name:
                return True
        #then check contextual immunities
        condition_contextual_immunities = self.contextual_condition_immunities.get(condition_name,[])
        for immunity_name, immunity_check in condition_contextual_immunities:
            if immunity_check(self,self.get_target_entity(copy=True),self.context):
                return True
        return False
    
    def add_condition(self, condition: Condition, context: Optional[Dict[str, Any]] = None)  -> bool:
        if condition.name is None:
            raise ValueError("Condition name is not set")
        if condition.target_entity_uuid is None:
            condition.target_entity_uuid = self.uuid
        if context is not None:
            condition.set_context(context)
        
        if self.check_condition_immunity(condition.name):
            return False

        condition_applied = condition.apply()
        if condition_applied:
            self.active_conditions[condition.name] = condition

            self.active_conditions_by_source = update_or_concat_to_dict(self.active_conditions_by_source, (str(condition.source_entity_uuid), condition.name))
        return condition_applied
    
    def _remove_condition_from_dicts(self, condition_name: str) :
        condition = self.active_conditions.pop(condition_name)
        assert condition.source_entity_uuid is not None
        self.active_conditions_by_source[str(condition.source_entity_uuid)].remove(condition_name)

    def add_static_condition_immunity(self, condition_name: str,immunity_name: Optional[str]=None):
        self.condition_immunities.append((condition_name,immunity_name))
    
    def _remove_static_condition_immunity(self, condition_name: str,immunity_name: Optional[str]=None):
        for condition_tuple in self.condition_immunities:
            if condition_tuple[0] == condition_name:
                if immunity_name is None:
                    self.condition_immunities.remove(condition_tuple)                
                else:
                    if condition_tuple[1] == immunity_name:
                        self.condition_immunities.remove(condition_tuple)
                        break
        return
    
    def add_contextual_condition_immunity(self, condition_name: str, immunity_name:str, immunity_check: ContextualConditionImmunity):
        if condition_name not in self.contextual_condition_immunities:
            self.contextual_condition_immunities[condition_name] = []
        self.contextual_condition_immunities[condition_name].append((immunity_name,immunity_check))

    def add_condition_immunity(self, condition_name: str, immunity_name: Optional[str]=None, immunity_check: Optional[ContextualConditionImmunity]=None):
        if immunity_check is not None:
            if immunity_name is None:
                raise ValueError("Immunity name is required when adding a contextual condition immunity")
            self.add_contextual_condition_immunity(condition_name,immunity_name,immunity_check)
        else:
            self.add_static_condition_immunity(condition_name,immunity_name)
    
    def _remove_contextual_condition_immunity(self, condition_name: str, immunity_name: Optional[str]=None):
        for self_condition_name in self.contextual_condition_immunities:
            if self_condition_name == condition_name:
                if immunity_name is None:
                    self.contextual_condition_immunities.pop(self_condition_name)
                    break
                else:
                    for immunity_tuple in self.contextual_condition_immunities[self_condition_name]:
                        if immunity_tuple[0] == immunity_name:
                            self.contextual_condition_immunities[self_condition_name].remove(immunity_tuple)
                            break

    
    def remove_condition_immunity(self, condition_name: str):
        self._remove_static_condition_immunity(condition_name)
        self._remove_contextual_condition_immunity(condition_name)
        return

    def advance_duration_condition(self,condition_name:str) -> bool:
        condition = self.active_conditions[condition_name]
        return condition.duration.progress()
    
    def advance_durations(self) -> List[str]:
        removed_conditions = []
        for condition_name in list(self.active_conditions.keys()):
            removed = self.advance_duration_condition(condition_name)
            if removed:
                removed_conditions.append(condition_name)
        return removed_conditions
    
    
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
    
    def _get_attack_bonuses(self,weapon_slot: WeaponSlot = WeaponSlot.MAIN_HAND) -> Tuple[ModifiableValue,ModifiableValue,List[ModifiableValue],List[ModifiableValue],Range ]:
        """ We have to get from weapon and then from equipment 
        attack_bonus 
        ability bonuses
        weapon attack bonus """
        weapon = self.equipment.weapon_main_hand
        ability_bonuses : List[ModifiableValue] = []
        dexterity_bonus = self.ability_scores.get_ability("dexterity").ability_score
        dexterity_modifier_bonus = self.ability_scores.get_ability("dexterity").modifier_bonus
        strength_bonus = self.ability_scores.get_ability("strength").ability_score
        strength_modifier_bonus = self.ability_scores.get_ability("strength").modifier_bonus
        attack_bonuses : List[ModifiableValue] = []
        if weapon is None:
            weapon_bonus=self.equipment.unarmed_attack_bonus
            attack_bonuses.append(self.equipment.melee_attack_bonus)
            range = Range(type=RangeType.REACH,normal=5)
        else:
            weapon_bonus=weapon.attack_bonus
            range = weapon.range
            if range.type == RangeType.RANGE:

                attack_bonuses.append(self.equipment.ranged_attack_bonus)
                ability_bonuses.append(dexterity_bonus)
                ability_bonuses.append(dexterity_modifier_bonus)
            elif range.type == RangeType.REACH and WeaponProperty.FINESSE in weapon.properties:
                attack_bonuses.append(self.equipment.melee_attack_bonus)
                ability_bonuses.append(strength_bonus)
                ability_bonuses.append(strength_modifier_bonus)
                ability_bonuses.append(dexterity_bonus)
                ability_bonuses.append(dexterity_modifier_bonus)
            else:
                attack_bonuses.append(self.equipment.melee_attack_bonus)
                ability_bonuses.append(strength_bonus)
                ability_bonuses.append(strength_modifier_bonus)
        proficiency_bonus = self.proficiency_bonus
        
        return proficiency_bonus, weapon_bonus, attack_bonuses, ability_bonuses, range
      
    
    def _get_damage_bonuses(self,weapon_slot: WeaponSlot = WeaponSlot.MAIN_HAND) -> Tuple[List[ModifiableValue],List[ModifiableValue],DamageType,int,int]:
        """ currently not considering extra damage bonuses from weapon"""
        weapon = self.equipment.weapon_main_hand
        ability_bonuses : List[ModifiableValue] = []
        dexterity_bonus = self.ability_scores.get_ability("dexterity").ability_score
        dexterity_modifier_bonus = self.ability_scores.get_ability("dexterity").modifier_bonus
        strength_bonus = self.ability_scores.get_ability("strength").ability_score
        strength_modifier_bonus = self.ability_scores.get_ability("strength").modifier_bonus
        damage_bonuses : List[ModifiableValue] = []
        if weapon is None:
            weapon_bonus=self.equipment.unarmed_damage_bonus
            damage_bonuses.append(self.equipment.melee_damage_bonus)
            damage_type = self.equipment.unarmed_damage_type
            damage_dice = self.equipment.unarmed_damage_dice
            num_damage_dice = self.equipment.unarmed_dice_numbers
            range = Range(type=RangeType.REACH,normal=5)
        else:
            weapon_bonus=weapon.attack_bonus
            damage_dice = weapon.damage_dice
            num_damage_dice = weapon.dice_numbers
            range = weapon.range
            damage_type = weapon.damage_type
            if range.type == RangeType.RANGE:

                damage_bonuses.append(self.equipment.ranged_damage_bonus)
                ability_bonuses.append(dexterity_bonus)
                ability_bonuses.append(dexterity_modifier_bonus)
            elif range.type == RangeType.REACH and WeaponProperty.FINESSE in weapon.properties:
                damage_bonuses.append(self.equipment.melee_damage_bonus)
                ability_bonuses.append(strength_bonus)
                ability_bonuses.append(strength_modifier_bonus)
                ability_bonuses.append(dexterity_bonus)
                ability_bonuses.append(dexterity_modifier_bonus)
            else:
                damage_bonuses.append(self.equipment.melee_damage_bonus)
                ability_bonuses.append(strength_bonus)
                ability_bonuses.append(strength_modifier_bonus)
        return damage_bonuses, ability_bonuses, damage_type, damage_dice, num_damage_dice
    
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
    
    