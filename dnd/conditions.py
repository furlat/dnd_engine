from dnd.core.base_conditions import BaseCondition, Duration, DurationType
from dnd.core.requests import AbilityName
from dnd.entity import Entity
from typing import Dict, Any, Optional, List, Tuple
from dnd.core.modifiers import ( ContextAwareCondition, BaseObject, AdvantageModifier, ContextAwareAdvantage,
                                 AutoHitModifier, AdvantageStatus, AdvantageModifier, AutoHitStatus,
                                   ContextualNumericalModifier, NumericalModifier,
                                   ContextAwareNumerical, ContextAwareAutoHit, ContextualAutoHitModifier, ContextualAdvantageModifier)
from dnd.blocks.skills import all_skills, skills_requiring_sight, skills_requiring_hearing, skills_requiring_speak, skills_social
from uuid import UUID, uuid4
from pydantic import Field
from functools import partial


class Blinded(BaseCondition):
    name: str = "Blinded"
    description: str = "A blinded creature can't see and automatically fails any ability check that requires sight. Attack rolls against the creature have advantage, and the creature's attack rolls have disadvantage."
    
    def _apply(self,context: Optional[Dict[str, Any]] = None) -> List[Tuple[UUID,UUID]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return []
        
        elif isinstance(target_entity,Entity):
            #the modifier is applied to the target entity henceh the source and target are switched
            outs = []
   
            self_static_condition_uuid = target_entity.equipment.attack_bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Blinded",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            to_target_static_condition_uuid =target_entity.equipment.ac_bonus.to_target_static.add_advantage_modifier(AdvantageModifier(name="Blinded",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.attack_bonus.uuid,self_static_condition_uuid))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_static_condition_uuid))
            for skill in skills_requiring_sight:
                skill_obj = target_entity.skill_set.get_skill(skill)
               
                modifier_uuid=skill_obj.skill_bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Blinded",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
                outs.append((skill_obj.skill_bonus.uuid,modifier_uuid))
            return outs
        else:
            return []   
        

        
class Charmed(BaseCondition):
    name: str = "Charmed"
    description: str = "A charmed creature can't attack the charmer or target the charmer with harmful abilities or magical effects."
    
    def _apply(self,context: Optional[Dict[str, Any]] = None) -> List[Tuple[UUID,UUID]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return []
        elif isinstance(target_entity,Entity):
            outs = []
            #prevent attacking the charmer
            charmed_attack_check = self.get_charmed_attack_check()
            self_static_condition_uuid = target_entity.equipment.attack_bonus.self_contextual.add_auto_hit_modifier(modifier=ContextualAutoHitModifier(name="Charmed",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=charmed_attack_check))
            outs.append((target_entity.equipment.attack_bonus.uuid,self_static_condition_uuid))

            # Add advantage on social checks for the charmer, this is done through the to_target_contextual
            charmed_skill_check = self.get_charmed_skill_check()
            for skill in skills_social:
                skill_obj = target_entity.skill_set.get_skill(skill)
                to_target_static_condition_uuid = skill_obj.skill_bonus.to_target_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Charmed",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=charmed_skill_check))
                outs.append((skill_obj.skill_bonus.uuid,to_target_static_condition_uuid))
            
            return outs
        else:
            return []
    

    @staticmethod
    def charmed_attack_check(charmer_id: UUID, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str, Any]] = None) -> Optional[AutoHitModifier]:
        """ this function is used to prevent the charmer from attacking the charmed entity this is used by the charmed entity
        hence source is the charmed and target is the charmer"""
        print(f"charmer_id: {charmer_id}, source_entity_uuid: {source_entity_uuid}, target_entity_uuid: {target_entity_uuid}")
        if  target_entity_uuid:
            entity = Entity.get(target_entity_uuid)
            if entity and entity.uuid == charmer_id:
                return AutoHitModifier(name="Charmed",value=AutoHitStatus.AUTOMISS,source_entity_uuid=source_entity_uuid,target_entity_uuid=target_entity_uuid)
        return None

    def get_charmed_attack_check(self) -> ContextAwareAutoHit:
        """ uses the self.source_entity_uuid as the charmer_id and creates a partial function with hardcoded charmer_id such that it can be used as a callable for the ContextualAutoHitModifier"""
        partial_function = partial(self.charmed_attack_check, self.source_entity_uuid)
        return partial_function

    @staticmethod
    def charmed_skill_check(charmer_id: UUID,charmed_id: UUID, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str, Any]] = None) -> Optional[AdvantageModifier]:
        """ this function is used to add advantage to the skill check of the charmer if the target is the charmed entity 
        it is stored inside the charmed and passed to the charmer via skill_bonus.to_target_contextual 
        because of this the function will be callsed by the charmer with inverted source and target mantaining the consistenct that the source is the charmed and target is the charmer"""
        print(f"charmer_id: {charmer_id},charmed_id: {charmed_id}, source_entity_uuid: {source_entity_uuid}, target_entity_uuid: {target_entity_uuid}")
        if charmer_id == target_entity_uuid and charmed_id == source_entity_uuid:
            return AdvantageModifier(name="Charmed",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=source_entity_uuid,target_entity_uuid=target_entity_uuid)
        return None

    def get_charmed_skill_check(self) -> ContextAwareAdvantage:
        """ uses the self.source_entity_uuid as the charmer_id and creates a partial function with hardcoded charmer_id such that it can be used as a callable for the ContextualAdvantageModifier"""
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set hence cannot generate the callable for the ContextualAdvantageModifier")
        partial_function = partial(self.charmed_skill_check, self.source_entity_uuid, self.target_entity_uuid)
        return partial_function


class Dashing(BaseCondition):
    name: str = "Dashing"
    description: str = "A dashing creature gets a movement bonues equal to it base movement speed"

    def _apply(self,context: Optional[Dict[str, Any]] = None) -> List[Tuple[UUID,UUID]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return []
        elif isinstance(target_entity,Entity):
            outs = []
            base_speed_modifier = target_entity.action_economy.movement.get_base_modifier()
            if not base_speed_modifier:
                raise ValueError(f"Base speed modifier is not set for the entity {target_entity.uuid}")
            base_speed = base_speed_modifier.value
            if base_speed > 0:
                extra_modifier = NumericalModifier(name="Dashing",value=base_speed,source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.target_entity_uuid)
                target_entity.action_economy.movement.self_static.add_value_modifier(extra_modifier)
                outs.append((target_entity.action_economy.movement.uuid,extra_modifier.uuid))
            return outs
        else:
            return []


class Deafened(BaseCondition):
    name: str = "Deafened"
    description: str = "A deafened creature can't hear and automatically fails any ability check that requires hearing."

    def _apply(self,context: Optional[Dict[str, Any]] = None) -> List[Tuple[UUID,UUID]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return []
        elif isinstance(target_entity,Entity):
            outs = []
            for skill in skills_requiring_hearing:
                skill_obj = target_entity.skill_set.get_skill(skill)
                modifier_uuid = skill_obj.skill_bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Deafened",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
                outs.append((skill_obj.skill_bonus.uuid,modifier_uuid))
            return outs
        else:
            return []


class Dodging(BaseCondition):
    name: str = "Dodging"
    description: str = "A dodging creature has advantage on Dexterity saving throws against being grappled."

    def _apply(self,context: Optional[Dict[str, Any]] = None) -> List[Tuple[UUID,UUID]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return []
        elif isinstance(target_entity,Entity):
            outs = []
            #add disadvantage to attacks against this creature
            to_target_static_condition_uuid =target_entity.equipment.ac_bonus.to_target_static.add_advantage_modifier(AdvantageModifier(name="Dodging",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_static_condition_uuid))
            #add advantage to Dexterity saving throws
            dex_save = target_entity.saving_throws.get_saving_throw("dexterity")
            dex_save.bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Dodging",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((dex_save.bonus.uuid,dex_save.bonus.uuid))
            return outs
        else:
            return []


class Frightened(BaseCondition):
    """ A frightened creature has disadvantage on attack rolls and ability checks and can not move while the frightener is in sight"""
    name: str = "Frightened"
    description: str = "A frightened creature has disadvantage on attack rolls and ability checks and can not move while the frightener is in sight"

    def _apply(self, context: Optional[Dict[str, Any]] = None) -> List[Tuple[UUID,UUID]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return []
        elif isinstance(target_entity,Entity):
            outs = []
            #add disadvantage to attacks from this creature inside the equipment attack bonus static
            disadvantage_uuid = target_entity.equipment.attack_bonus.self_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Frightened",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=self.get_frightener_in_senses_disadvantage()))
            outs.append((target_entity.equipment.attack_bonus.uuid,disadvantage_uuid))

            #add disadvantage to all ability checks using the same callable
            for skill in all_skills:
                skill_obj = target_entity.skill_set.get_skill(skill)
                skills_modifier_uuid = skill_obj.skill_bonus.self_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Frightened",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=self.get_frightener_in_senses_disadvantage()))
                outs.append((skill_obj.skill_bonus.uuid,skills_modifier_uuid))

            #adds max constraint to the movement value when the frightener is in the senses of the target
            movement_value = target_entity.action_economy.movement
            movement_value.self_contextual.add_max_constraint(constraint=ContextualNumericalModifier(name="Frightened",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=self.get_frigthener_in_senses_zero_max_speed()))
            outs.append((movement_value.uuid,movement_value.uuid))
            return outs
        else:
            return []
            
    @staticmethod
    def frightener_in_senses_disadvantage(frightener_uuid: UUID, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str, Any]] = None) -> Optional[AdvantageModifier]:
        """ this function is used to add a disadvantage to the attack bonus and ability checks of the target entity if the frightener is in the senses of the target"""
        source_entity = Entity.get(source_entity_uuid)
        if isinstance(source_entity,Entity) and frightener_uuid in source_entity.senses.entities:
            return AdvantageModifier(name="Frightened",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=source_entity_uuid,target_entity_uuid=target_entity_uuid)
        return None

    def get_frightener_in_senses_disadvantage(self) -> ContextAwareAdvantage:
        """ uses the self.source_entity_uuid as the frightener_uuid and creates a partial function with hardcoded frightener_uuid such that it can be used as a callable for the ContextualAdvantageModifier"""
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set hence cannot generate the callable for the ContextualAdvantageModifier")
        partial_function = partial(self.frightener_in_senses_disadvantage, self.source_entity_uuid)
        return partial_function
    
    @staticmethod
    def frigthener_in_senses_zero_max_speed(frightener_uuid: UUID, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str, Any]] = None) -> Optional[NumericalModifier]:
        """ this function is used to set the max speed of the target entity to 0 if the frightener is in the senses of the target"""
        source_entity = Entity.get(source_entity_uuid)
        if isinstance(source_entity,Entity) and frightener_uuid in source_entity.senses.entities:
            return NumericalModifier(name="Frightened",value=0,source_entity_uuid=source_entity_uuid,target_entity_uuid=target_entity_uuid)
        return None
    

    def get_frigthener_in_senses_zero_max_speed(self) -> ContextAwareNumerical:
        """ uses the self.source_entity_uuid as the frightener_uuid and creates a partial function with hardcoded frightener_uuid such that it can be used as a callable for the ContextualNumericalModifier"""
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set hence cannot generate the callable for the ContextualNumericalModifier")
        partial_function = partial(self.frigthener_in_senses_zero_max_speed, self.source_entity_uuid)
        return partial_function


