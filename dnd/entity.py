from typing import Dict, Optional, Any, List, Self, Literal, ClassVar, Union, Tuple, Callable
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field, field_validator
from enum import Enum



from dnd.core.values import ModifiableValue
from dnd.core.modifiers import (
    NumericalModifier, DamageType, ResistanceStatus, 
    ContextAwareCondition, BaseObject
)

from dnd.core.values import  AdvantageStatus, CriticalStatus, AutoHitStatus, StaticValue, ContextualValue

from dnd.core.base_conditions import BaseCondition
from dnd.core.dice import Dice, RollType, DiceRoll, AttackOutcome


from dnd.blocks.base_block import BaseBlock
from dnd.blocks.abilities import (AbilityConfig,AbilityScoresConfig, AbilityScores)
from dnd.blocks.saving_throws import (SavingThrowConfig,SavingThrowSetConfig,SavingThrowSet)
from dnd.blocks.health import (HealthConfig,Health)
from dnd.blocks.equipment import (EquipmentConfig,Equipment,WeaponSlot,RangeType,WeaponProperty, Range, Shield, Damage)
from dnd.blocks.action_economy import (ActionEconomyConfig,ActionEconomy)
from dnd.blocks.skills import (SkillSetConfig,SkillSet,SkillName)
from dnd.blocks.sensory import Senses
from dnd.core.requests import AbilityName, SkillName, SavingThrowRequest, SkillCheckRequest


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

class EntityConfig(BaseModel):
    ability_scores: AbilityScoresConfig = Field(default_factory=lambda: AbilityScoresConfig,description="Ability scores for the entity")
    skill_set: SkillSetConfig = Field(default_factory=lambda: SkillSetConfig,description="Skill set for the entity")
    saving_throws: SavingThrowSetConfig = Field(default_factory=lambda: SavingThrowSetConfig,description="Saving throws for the entity")
    health: HealthConfig = Field(default_factory=lambda: HealthConfig,description="Health for the entity")
    equipment: EquipmentConfig = Field(default_factory=lambda: EquipmentConfig,description="Equipment for the entity")
    action_economy: ActionEconomyConfig = Field(default_factory=lambda: ActionEconomyConfig,description="Action economy for the entity")
    proficiency_bonus: int = Field(default=0,description="Proficiency bonus for the entity")
    proficiency_bonus_modifiers: List[Tuple[str, int]] = Field(default_factory=list,description="Any additional static modifiers applied to the proficiency bonus")
    position: Tuple[int,int] = Field(default_factory=lambda: (0,0),description="Position of the entity")

class Entity(BaseBlock):
    """ Base class for dnd entities in the game it acts as container for blocks and implements common functionalities that
    require interactions between blocks """
    
    name: str = Field(default="Entity")
    ability_scores: AbilityScores = Field(default_factory=lambda: AbilityScores.create(source_entity_uuid=uuid4()))
    skill_set: SkillSet = Field(default_factory=lambda: SkillSet.create(source_entity_uuid=uuid4()))
    saving_throws: SavingThrowSet = Field(default_factory=lambda: SavingThrowSet.create(source_entity_uuid=uuid4()))
    health: Health = Field(default_factory=lambda: Health.create(source_entity_uuid=uuid4()))
    equipment: Equipment = Field(default_factory=lambda: Equipment.create(source_entity_uuid=uuid4()))
    action_economy: ActionEconomy = Field(default_factory=lambda: ActionEconomy.create(source_entity_uuid=uuid4()))
    proficiency_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),value_name="proficiency_bonus",base_value=2))
    senses: Senses = Field(default_factory=lambda: Senses.create(source_entity_uuid=uuid4()))

    active_conditions: Dict[str, BaseCondition] = Field(default_factory=dict)
    condition_immunities: List[Tuple[str,Optional[str]]] = Field(default_factory=list)
    contextual_condition_immunities: Dict[str, List[Tuple[str,ContextualConditionImmunity]]] = Field(default_factory=dict)
    active_conditions_by_source: Dict[str, List[str]] = Field(default_factory=dict)

    
    @classmethod
    def create(cls, source_entity_uuid: UUID, name: str = "Entity",description: Optional[str] = None,config: Optional[EntityConfig] = None) -> 'Entity':
        """
        Create a new Entity instance with the given parameters. All sub-blocks will share
        the same source_entity_uuid as the entity itself.

        Args:
            source_entity_uuid (UUID): The UUID that will be used as both the entity's UUID and source_entity_uuid
            name (str): The name of the entity. Defaults to "Entity"

        Returns:
            Entity: The newly created Entity instance
        """
        if config is None:
            return cls(
                uuid=source_entity_uuid,
                source_entity_uuid=source_entity_uuid,
                name=name)
        else:
            ability_scores = AbilityScores.create(source_entity_uuid=source_entity_uuid,config=config.ability_scores)
            skill_set = SkillSet.create(source_entity_uuid=source_entity_uuid,config=config.skill_set)
            saving_throws = SavingThrowSet.create(source_entity_uuid=source_entity_uuid,config=config.saving_throws)
            health = Health.create(source_entity_uuid=source_entity_uuid,config=config.health)
            equipment = Equipment.create(source_entity_uuid=source_entity_uuid,config=config.equipment)
            senses = Senses.create(source_entity_uuid=source_entity_uuid,position=config.position)
            action_economy = ActionEconomy.create(source_entity_uuid=source_entity_uuid,config=config.action_economy)
            proficiency_bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid,base_value=config.proficiency_bonus)
            for modifier in config.proficiency_bonus_modifiers:
                proficiency_bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid,name=modifier[0],value=modifier[1]))
            return cls(
                uuid=source_entity_uuid,
                source_entity_uuid=source_entity_uuid,
                name=name,
                description=description,
                ability_scores=ability_scores,
                skill_set=skill_set,
                saving_throws=saving_throws,
                health=health,
                equipment=equipment,
                senses=senses,
                action_economy=action_economy,
                proficiency_bonus=proficiency_bonus
            )
        
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
    
    def add_condition(self, BaseCondition: BaseCondition, context: Optional[Dict[str, Any]] = None)  -> bool:
        if BaseCondition.name is None:
            raise ValueError("BaseCondition name is not set")
        if BaseCondition.target_entity_uuid is None:
            BaseCondition.target_entity_uuid = self.uuid
        if context is not None:
            BaseCondition.set_context(context)
        
        if self.check_condition_immunity(BaseCondition.name):
            return False

        condition_applied = BaseCondition.apply()
        if condition_applied:
            self.active_conditions[BaseCondition.name] = BaseCondition

            self.active_conditions_by_source = update_or_concat_to_dict(self.active_conditions_by_source, (str(BaseCondition.source_entity_uuid), BaseCondition.name))
        return condition_applied
    
    def _remove_condition_from_dicts(self, condition_name: str) :
        BaseCondition = self.active_conditions.pop(condition_name)
        assert BaseCondition.source_entity_uuid is not None
        self.active_conditions_by_source[str(BaseCondition.source_entity_uuid)].remove(condition_name)

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
                raise ValueError("Immunity name is required when adding a contextual BaseCondition immunity")
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
        BaseCondition = self.active_conditions[condition_name]
        return BaseCondition.duration.progress()
    
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
        if weapon_slot == WeaponSlot.MAIN_HAND:
            weapon = self.equipment.weapon_main_hand
        elif weapon_slot == WeaponSlot.OFF_HAND:
            weapon = self.equipment.weapon_off_hand

        ability_bonuses : List[ModifiableValue] = []
        dexterity_bonus = self.ability_scores.get_ability("dexterity").ability_score
        dexterity_modifier_bonus = self.ability_scores.get_ability("dexterity").modifier_bonus
        strength_bonus = self.ability_scores.get_ability("strength").ability_score
        strength_modifier_bonus = self.ability_scores.get_ability("strength").modifier_bonus
        attack_bonuses : List[ModifiableValue] = [self.equipment.attack_bonus]
        if weapon is None or isinstance(weapon, Shield):
            weapon_bonus=self.equipment.unarmed_attack_bonus
            attack_bonuses.append(self.equipment.melee_attack_bonus)
            ability_bonuses.append(strength_bonus)
            ability_bonuses.append(strength_modifier_bonus)
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
                combined_strength_bonus = strength_bonus.combine_values([strength_modifier_bonus])
                combined_dexterity_bonus = dexterity_bonus.combine_values([dexterity_modifier_bonus])
                if combined_strength_bonus.normalized_score >= combined_dexterity_bonus.normalized_score:
                    ability_bonuses.append(strength_bonus)
                    ability_bonuses.append(strength_modifier_bonus)
                else:
                    ability_bonuses.append(dexterity_bonus)
                    ability_bonuses.append(dexterity_modifier_bonus)
            else:
                attack_bonuses.append(self.equipment.melee_attack_bonus)
                ability_bonuses.append(strength_bonus)
                ability_bonuses.append(strength_modifier_bonus)
        proficiency_bonus = self.proficiency_bonus
        
        return proficiency_bonus, weapon_bonus, attack_bonuses, ability_bonuses, range
      
    

    
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
        if target_entity is not None:
            target_entity.clear_target_entity() 
            for mod_source, mod_target in zip(skill_bonuses_source, skill_bonuses_target):
                mod_source.reset_from_target()
                mod_target.reset_from_target()

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
        for mod_source, mod_target in zip(skill_bonuses_source, skill_bonuses_target):
            mod_source.reset_from_target()
            mod_target.reset_from_target()

        return total_bonus_source, total_bonus_target
    
    def ac_bonus(self, target_entity_uuid: Optional[UUID]=None) -> ModifiableValue:
        """ missing effects from target attack bonus"""
        if target_entity_uuid is not None:
            self.set_target_entity(target_entity_uuid)

        if self.equipment.is_unarmored():
            unarmored_values = self.equipment.get_unarmored_ac_values()
            abilities = self.equipment.get_unarmored_abilities()
            ability_bonuses = [self.ability_scores.get_ability(ability).ability_score for ability in abilities]
            ability_modifier_bonuses = [self.ability_scores.get_ability(ability).modifier_bonus for ability in abilities]
            ac_bonus = unarmored_values[0].combine_values(unarmored_values[1:]+ability_bonuses+ability_modifier_bonuses)
            
        
        else:
            armored_values = self.equipment.get_armored_ac_values()
            max_dexterity_bonus = self.equipment.get_armored_max_dex_bonus()
            assert max_dexterity_bonus is not None
            dexterity_bonus = self.ability_scores.get_ability("dexterity").ability_score
            dexterity_modifier_bonus = self.ability_scores.get_ability("dexterity").modifier_bonus
            combined_dexterity_bonus = dexterity_bonus.combine_values([dexterity_modifier_bonus])
            if combined_dexterity_bonus.normalized_score > max_dexterity_bonus.normalized_score:
                combined_dexterity_bonus = max_dexterity_bonus
            ac_bonus = armored_values[0].combine_values(armored_values[1:]+[combined_dexterity_bonus])
        if target_entity_uuid is not None:
            self.clear_target_entity()
        return ac_bonus
    
    
    def attack_bonus(self, weapon_slot: WeaponSlot = WeaponSlot.MAIN_HAND, target_entity_uuid: Optional[UUID] = None) -> ModifiableValue:
        """ missing effects from target armor bonus"""
        if target_entity_uuid is not None:
            self.set_target_entity(target_entity_uuid)
    
        proficiency_bonus, weapon_bonus, attack_bonuses, ability_bonuses, range = self._get_attack_bonuses(weapon_slot)
        print("current ability bonuses", ability_bonuses)
        bonuses = [weapon_bonus] + attack_bonuses + ability_bonuses
        source_attack_bonus = proficiency_bonus.combine_values(bonuses)
        if target_entity_uuid is not None:
            self.clear_target_entity()
        return source_attack_bonus
    

    def get_damages(self, weapon_slot: WeaponSlot = WeaponSlot.MAIN_HAND, target_entity_uuid: Optional[UUID] = None) -> List[Damage]:
        if target_entity_uuid is not None:
            self.set_target_entity(target_entity_uuid)
        damages = self.equipment.get_damages(weapon_slot, self.ability_scores)
        if target_entity_uuid is not None:
            self.clear_target_entity()
        return damages
    
    def take_damage(self, damages: List[Damage], attack_outcome: AttackOutcome) -> List[DiceRoll]:
        """ From each damage we get the dice and damage type and we roll it """
        con_modifier = self.ability_scores.get_ability("constitution").get_combined_values()
        print(f"Total Health before taking damage: {self.health.get_total_hit_points(con_modifier.normalized_score)}")
        rolls = []
        for damage in damages:
            dice = damage.get_dice(attack_outcome=attack_outcome)
            roll = dice.roll
            rolls.append(roll)
            print(f"Damage Roll result: {roll.results}, Roll total: {roll.total}")
            self.health.take_damage(roll.total, damage.damage_type, source_entity_uuid=damage.source_entity_uuid)
        print(f"Total Health after taking damage: {self.health.get_total_hit_points(con_modifier.normalized_score)}")

        return rolls
    
    def get_attack_outcome(self, attack_bonus: ModifiableValue, ac: Union[int,ModifiableValue]) -> Tuple[DiceRoll,AttackOutcome]:
        """ Returns the dice roll and the attack outcome """
        attack_dice = Dice(count=1,value=20,bonus=attack_bonus, roll_type=RollType.ATTACK)
        target_ac = ac.normalized_score if isinstance(ac,ModifiableValue) else ac
        print(f"Target AC: {target_ac}")
        print(f"Attack bonus: {attack_bonus.normalized_score}")
        roll = attack_dice.roll
        print(f"Roll result: {roll.results}, Roll total: {roll.total} vs target ac: {target_ac} result: {roll.total >= target_ac} auto hit status: {roll.auto_hit_status} critical status: {roll.critical_status}")
        print(f"Roll auto hit status: {roll.auto_hit_status}")
        print(f"Roll critical status: {roll.critical_status}")
        print(f"Attack bonus advantage modifiers: {attack_bonus.advantage}")
        print(f"Ac advantage modifiers: {ac.advantage}" if isinstance(ac,ModifiableValue) else "No advantage modifiers")
        print(f"Roll Advantage status: {roll.advantage_status}")
        #first BaseCondition to check is auto miss which ovverides everything else
        #second BaseCondition is to check if the roll is a auto hit with two cases (critical and normal based on the roll or critical status)
        #third BaseCondition is to check if the roll is a hit with two cases (critical and normal based on the roll or critical status)
        #fourth BaseCondition is to check if the roll is a roll miss
        if roll.auto_hit_status == AutoHitStatus.AUTOMISS:
            return roll, AttackOutcome.MISS
        elif roll.auto_hit_status == AutoHitStatus.AUTOHIT:
            if roll.critical_status == CriticalStatus.AUTOCRIT or roll.results == 20:
                return roll, AttackOutcome.CRIT
            else:
                return roll, AttackOutcome.HIT
        elif roll.results == 1:
            return roll, AttackOutcome.CRIT_MISS
        elif roll.total >= target_ac:
            if roll.critical_status == CriticalStatus.AUTOCRIT or roll.results == 20:
                return roll, AttackOutcome.CRIT
            else:
                return roll, AttackOutcome.HIT
        else:
            return roll, AttackOutcome.MISS
        
    
    def create_saving_throw_request(self, target_entity_uuid: UUID, ability_name: AbilityName, dc: Union[int,UUID]) -> SavingThrowRequest:
        """ request a saving throw from the target entity """
        #if dc is a uuid get the modifiable value ensure is coming from self (has self.uuid as source entity uuid)
        if isinstance(dc,UUID):
            self.set_target_entity(dc)
            new_dc = ModifiableValue.get(dc)
            if new_dc is None or new_dc.source_entity_uuid != self.uuid:
                raise ValueError("DC is not coming from self oir not present")
            new_dc = new_dc.model_copy(deep=True)
            new_dc.set_target_entity(target_entity_uuid)
            int_dc = new_dc.normalized_score
        else:
            int_dc = dc
        self.clear_target_entity()
        return SavingThrowRequest(source_entity_uuid=self.uuid, target_entity_uuid=target_entity_uuid, ability_name=ability_name, dc=int_dc)
    

    def create_skill_check_request(self, target_entity_uuid: UUID, skill_name: SkillName, dc: Union[int,UUID]) -> SkillCheckRequest:
        """ request a skill check from the target entity """
        if isinstance(dc,UUID):
            self.set_target_entity(dc)
            dc_modifier = ModifiableValue.get(dc)
            if dc_modifier is None or dc_modifier.source_entity_uuid != self.uuid:
                raise ValueError(f"not present {dc_modifier is None} or not coming from self")
            if target_entity_uuid != dc_modifier.target_entity_uuid:
                new_dc = dc_modifier.model_copy(deep=True)
                new_dc.set_target_entity(target_entity_uuid)
            else:
                new_dc = dc_modifier
            int_dc = new_dc.normalized_score
        else:
            int_dc = dc
        self.clear_target_entity()
        return SkillCheckRequest(source_entity_uuid=self.uuid, target_entity_uuid=target_entity_uuid, skill_name=skill_name, dc=int_dc)
    
    def saving_throw(self, request: SavingThrowRequest) -> Tuple[AttackOutcome,DiceRoll,bool]:
        """ make a saving throw"""
        #first assert that the target of the saving throw is self
        if request.target_entity_uuid != self.uuid:
            raise ValueError("Target entity uuid does not match")
        #second set the target to the requester source entity
        self.set_target_entity(request.source_entity_uuid)
        #second get the saving throw from the request
        saving_throw = self.saving_throw_bonus(request.source_entity_uuid, request.ability_name)
        #third get the dc for the saving throw
        dc = request.get_dc()
        #create the dice

        roll,saving_throw_outcome = self.get_attack_outcome(saving_throw,dc)
        self.clear_target_entity()
        return saving_throw_outcome, roll, True if saving_throw_outcome not in [AttackOutcome.MISS,AttackOutcome.CRIT_MISS] else False
    
    def skill_check(self, request: SkillCheckRequest) -> Tuple[AttackOutcome,DiceRoll,bool]:
        """ make a skill check """
        if request.target_entity_uuid != self.uuid:
            raise ValueError("Target entity uuid does not match")
        self.set_target_entity(request.source_entity_uuid)
        skill_check = self.skill_bonus(request.source_entity_uuid, request.skill_name)
        dc = request.get_dc()
        roll,skill_check_outcome = self.get_attack_outcome(skill_check,dc)
        self.clear_target_entity()
        return skill_check_outcome, roll, True if skill_check_outcome not in [AttackOutcome.MISS,AttackOutcome.CRIT_MISS] else False


    def attack(self, target_entity_uuid: UUID, weapon_slot: WeaponSlot = WeaponSlot.MAIN_HAND) -> Tuple[AttackOutcome,DiceRoll,List[Tuple[Damage, DiceRoll]]]:
        """ Full method implementing a complete attack returns two objects:
        This outer methods does not get a copy of the target entity but the actual target entity that will be modified in place
        each submethod is responsible for getting a copy of the target entity if needed for local computations
        1) the list of damages and respective dice rolls 
        2) the attack outcome"""
        self.set_target_entity(target_entity_uuid)
        target_entity = self.get_target_entity(copy=False)
        assert isinstance(target_entity, Entity)
        target_entity.set_target_entity(self.uuid)

        #get attack aggregated bonuses from source
        attack_bonus = self.attack_bonus(weapon_slot= weapon_slot)
        #get ac for target
        ac = target_entity.ac_bonus()
        ac.set_from_target(attack_bonus)
        attack_bonus.set_from_target(ac)
        dice_roll, attack_outcome = self.get_attack_outcome(attack_bonus, ac)
        ac.reset_from_target()
        attack_bonus.reset_from_target()
        if attack_outcome in [AttackOutcome.MISS,AttackOutcome.CRIT_MISS]:
            self.clear_target_entity()
            target_entity.clear_target_entity()
            return attack_outcome, dice_roll, []
        else:
            damages = self.get_damages(weapon_slot)
            damage_rolls = target_entity.take_damage(damages, attack_outcome)
            self.clear_target_entity()
            target_entity.clear_target_entity()
            return attack_outcome, dice_roll, [(damage, roll) for damage, roll in zip(damages, damage_rolls)]

