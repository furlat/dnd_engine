from dnd.core.base_conditions import BaseCondition, Duration, DurationType

from dnd.entity import Entity
from typing import Dict, Any, Optional, List, Tuple
from dnd.core.modifiers import ( ContextAwareCondition, BaseObject, AdvantageModifier, ContextAwareAdvantage,
                                 AutoHitModifier, AdvantageStatus, AdvantageModifier, AutoHitStatus,
                                   ContextualNumericalModifier, NumericalModifier,
                                   ContextualCriticalModifier, CriticalModifier, CriticalStatus,
                                   ContextAwareNumerical, ContextAwareAutoHit, ContextualAutoHitModifier, ContextualAdvantageModifier)
from dnd.blocks.skills import all_skills, skills_requiring_sight, skills_requiring_hearing, skills_requiring_speak, skills_social
from dnd.blocks.sensory import SensesType
from uuid import UUID, uuid4
from pydantic import Field
from functools import partial
from dnd.core.events import Event, EventPhase, AbilityName, SkillName


class Blinded(BaseCondition):
    name: str = "Blinded"
    description: str = "A blinded creature can't see and automatically fails any ability check that requires sight. Attack rolls against the creature have advantage, and the creature's attack rolls have disadvantage."
    
    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        
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
            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")
        

        
class Charmed(BaseCondition):
    name: str = "Charmed"
    description: str = "A charmed creature can't attack the charmer or target the charmer with harmful abilities or magical effects."
    
    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
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
            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")
    

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

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
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
            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")


class Deafened(BaseCondition):
    name: str = "Deafened"
    description: str = "A deafened creature can't hear and automatically fails any ability check that requires hearing."

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            for skill in skills_requiring_hearing:
                skill_obj = target_entity.skill_set.get_skill(skill)
                modifier_uuid = skill_obj.skill_bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Deafened",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
                outs.append((skill_obj.skill_bonus.uuid,modifier_uuid))
            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")


class Dodging(BaseCondition):
    name: str = "Dodging"
    description: str = "A dodging creature has advantage on Dexterity saving throws against being grappled."

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            #add disadvantage to attacks against this creature
            to_target_static_condition_uuid =target_entity.equipment.ac_bonus.to_target_static.add_advantage_modifier(AdvantageModifier(name="Dodging",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_static_condition_uuid))
            #add advantage to Dexterity saving throws
            dex_save = target_entity.saving_throws.get_saving_throw("dexterity")
            dex_save.bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Dodging",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((dex_save.bonus.uuid,dex_save.bonus.uuid))
            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")


class Frightened(BaseCondition):
    """ A frightened creature has disadvantage on attack rolls and ability checks and can not move while the frightener is in sight"""
    name: str = "Frightened"
    description: str = "A frightened creature has disadvantage on attack rolls and ability checks and can not move while the frightener is in sight"

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
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
            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")
            
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


class Grappled(BaseCondition):
    """ max speed is set to 0 in self static"""
    name: str = "Grappled"
    description: str = "A grappled creature can't move through the space of the grappler"

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            speed_obj = target_entity.action_economy.movement
            speed_obj.self_static.add_max_constraint(constraint=NumericalModifier(name="Grappled",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((speed_obj.uuid,speed_obj.uuid))
            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

class Incapacitated(BaseCondition):
    """ max actions, bonus actions, movement and reactions are set to 0 in self static"""
    name: str = "Incapacitated"
    description: str = "A incapacitated creature can't take actions"

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            #set max actions, bonus actions, and reactions to 0
            action_max_constrain_uuid = target_entity.action_economy.actions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.action_economy.actions.uuid,action_max_constrain_uuid))
            bonus_action_max_constrain_uuid = target_entity.action_economy.bonus_actions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.action_economy.bonus_actions.uuid,bonus_action_max_constrain_uuid))
            reaction_max_constrain_uuid = target_entity.action_economy.reactions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.action_economy.reactions.uuid,reaction_max_constrain_uuid))
            #set max speed to 0
            speed_obj = target_entity.action_economy.movement
            speed_max_constrain_uuid = speed_obj.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((speed_obj.uuid,speed_max_constrain_uuid))
            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")
        
class Invisible(BaseCondition):
    """ adds advantage to all attacks from this creature against creature that can not see invisible
     gives disadvantage to all attacks against this creature if the observer can not see invisible"""
    name: str = "Invisible"
    description:str = "An invisible creature is impossible to see without the aid of magic or a special sense"

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            #add conditional advantage to all attacks from this creature against creature that can not see invisible
            self_contextual_uuid = target_entity.equipment.attack_bonus.self_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Invisible",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=self.target_can_not_see_invisible_advantage))
            outs.append((target_entity.equipment.attack_bonus.uuid,self_contextual_uuid))

            #add conditional disadvantage to all attacks against this creature if the observer can not see invisible
            to_target_contextual_uuid = target_entity.equipment.ac_bonus.to_target_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Invisible",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=self.target_can_not_see_invisible_disadvantage))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_contextual_uuid))
            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

    @staticmethod
    def can_see_invisible(observer: Entity) -> bool:
        """ returns true if the observer can see invisible"""
        return SensesType.TRUESIGHT in observer.senses.extra_senses or SensesType.TREMORSENSE in observer.senses.extra_senses

    @staticmethod
    def target_can_not_see_invisible_advantage(source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str, Any]] = None) -> Optional[AdvantageModifier]:
        """ if the target creature does not have neither truesight nor tremorsense it returns an advantage modifier used for self contextual of the invisible creature"""
        if target_entity_uuid:
            target_entity = Entity.get(target_entity_uuid)
            if isinstance(target_entity,Entity) and not Invisible.can_see_invisible(target_entity):
                return AdvantageModifier(name="Invisible",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=source_entity_uuid,target_entity_uuid=target_entity_uuid)
        return None
    
    @staticmethod
    def target_can_not_see_invisible_disadvantage(source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str, Any]] = None) -> Optional[AdvantageModifier]:
        """ if the target creature does not have neither truesight nor tremorsense it returns a disadvantage modifier
        used in the to_target_contextual of the invisible creature this condition wil lbe triggered by the attacker so source entity wil lbe the target of the invisible condition which will transfer its self to other during attack computation"""
        if target_entity_uuid:
            target_entity = Entity.get(target_entity_uuid)
            if isinstance(target_entity,Entity) and not Invisible.can_see_invisible(target_entity):
                return AdvantageModifier(name="Invisible",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=source_entity_uuid,target_entity_uuid=target_entity_uuid)
        return None


class Paralyzed(BaseCondition):
    """A paralyzed creature is incapacitated (see the condition) and can’t move or speak.
    The creature automatically fails Strength and Dexterity saving throws.
    Attack rolls against the creature have advantage.
    Any attack that hits the creature is a critical hit if the attacker is within 5 feet of the creature."""
    name: str = "Paralyzed"
    description: str = "A paralyzed creature is incapacitated (see the condition) and can’t move or speak. The creature automatically fails Strength and Dexterity saving throws. Attack rolls against the creature have advantage. Any attack that hits the creature is a critical hit if the attacker is within 5 feet of the creature."

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            #like incapacitated first
            #set max actions, bonus actions, and reactions to 0
            action_max_constrain_uuid = target_entity.action_economy.actions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.action_economy.actions.uuid,action_max_constrain_uuid))
            bonus_action_max_constrain_uuid = target_entity.action_economy.bonus_actions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.action_economy.bonus_actions.uuid,bonus_action_max_constrain_uuid))
            reaction_max_constrain_uuid = target_entity.action_economy.reactions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.action_economy.reactions.uuid,reaction_max_constrain_uuid))
            #set max speed to 0
            speed_obj = target_entity.action_economy.movement
            speed_max_constrain_uuid = speed_obj.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((speed_obj.uuid,speed_max_constrain_uuid))

            # Auto-fail STR and DEX saves
            dex_save = target_entity.saving_throws.get_saving_throw("dexterity")
            dex_save_auto_hit_uuid = dex_save.bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Paralyzed",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((dex_save.bonus.uuid,dex_save_auto_hit_uuid))
            str_save = target_entity.saving_throws.get_saving_throw("strength")
            str_save_auto_hit_uuid = str_save.bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Paralyzed",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((str_save.bonus.uuid,str_save_auto_hit_uuid))

            #add conditional critical to attacks within 5 feet 
            to_target_contextual_uuid = target_entity.equipment.ac_bonus.to_target_contextual.add_critical_modifier(modifier=ContextualCriticalModifier(name="Paralyzed",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=self.paralyzed_distance_critical))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_contextual_uuid))
            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")
            
    @staticmethod
    def paralyzed_distance_critical(source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str, Any]] = None) -> Optional[CriticalModifier]:
        """ if the the source entity is within 5 feet of the target creature it returns a auto critical modifier
        this is given by the paralized creature to attackers via to_target_contextual"""
        if target_entity_uuid:
            target_entity = Entity.get(target_entity_uuid)
            source_entity = Entity.get(source_entity_uuid)
            if isinstance(source_entity,Entity) and isinstance(target_entity,Entity):
                distance = source_entity.senses.get_feet_distance(target_entity.senses.position)
                if distance <= 5:
                    return CriticalModifier(name="Paralyzed",value=CriticalStatus.AUTOCRIT,source_entity_uuid=source_entity_uuid,target_entity_uuid=target_entity_uuid)
        return None

            

class Poisoned(BaseCondition):
    """ adds disadvantage to all attacks and ability checks"""
    name: str = "Poisoned"
    description: str = "A poisoned creature has disadvantage on all ability checks and attack rolls"

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []   
            #add disadvantage to all attacks
            self_static_attack_uuid = target_entity.equipment.attack_bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Poisoned",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.attack_bonus.uuid,self_static_attack_uuid))
            #add disadvantage to all ability checks
            for skill in all_skills:
                skill_obj = target_entity.skill_set.get_skill(skill)
                skill_static_modifier_uuid = skill_obj.skill_bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Poisoned",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
                outs.append((skill_obj.skill_bonus.uuid,skill_static_modifier_uuid))
            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

class Prone(BaseCondition):
    """disadvantage to prone entity attacksa and when targeted add disadvantage to attacks from >5feet and advantage to attacks within 5 feet"""
    name: str = "Prone"
    description: str = "A prone creature has disadvantage on all attack rolls and ability checks. Attack rolls against the creature have advantage, and the creature's attack rolls have disadvantage."

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            #add disadvantage to all attacks
            self_static_attack_uuid = target_entity.equipment.attack_bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Prone",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.attack_bonus.uuid,self_static_attack_uuid))

            #add conditional advantage to attacks within 5 feet
            to_target_contextual_uuid = target_entity.equipment.ac_bonus.to_target_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Prone",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=self.prone_distance_advantage))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_contextual_uuid))
            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

    @staticmethod
    def prone_distance_advantage(source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str, Any]] = None) -> Optional[AdvantageModifier]:
        """ if the source entity is within 5 feet of the target creature it returns an advantage modifier
        this is given by the prone creature to attackers via to_target_contextual"""
        if target_entity_uuid:
            target_entity = Entity.get(target_entity_uuid)
            source_entity = Entity.get(source_entity_uuid)
            if isinstance(source_entity,Entity) and isinstance(target_entity,Entity):
                distance = source_entity.senses.get_feet_distance(target_entity.senses.position)
                if distance <= 5:
                    return AdvantageModifier(name="Prone",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=source_entity_uuid,target_entity_uuid=target_entity_uuid)
                else:
                    return AdvantageModifier(name="Prone",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=source_entity_uuid,target_entity_uuid=target_entity_uuid)
        return None



class Stunned(BaseCondition):
    """ like restrained, auto fails str and dex, advantage on attacks against the creature"""
    name: str = "Stunned"
    description: str = "A stunned creature is incapacitated (see the condition), can't move, and can't speak. The creature automatically fails Strength and Dexterity saving throws. Attack rolls against the creature have advantage."

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            #like incapacitated first
            #set max actions, bonus actions, and reactions to 0
            action_max_constrain_uuid = target_entity.action_economy.actions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.action_economy.actions.uuid,action_max_constrain_uuid))
            bonus_action_max_constrain_uuid = target_entity.action_economy.bonus_actions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.action_economy.bonus_actions.uuid,bonus_action_max_constrain_uuid))
            reaction_max_constrain_uuid = target_entity.action_economy.reactions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.action_economy.reactions.uuid,reaction_max_constrain_uuid))
            #set max speed to 0
            speed_obj = target_entity.action_economy.movement
            speed_max_constrain_uuid = speed_obj.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((speed_obj.uuid,speed_max_constrain_uuid))

            # Auto-fail STR and DEX saves
            dex_save = target_entity.saving_throws.get_saving_throw("dexterity")
            dex_save_auto_hit_uuid = dex_save.bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Stunned",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((dex_save.bonus.uuid,dex_save_auto_hit_uuid))
            str_save = target_entity.saving_throws.get_saving_throw("strength")
            str_save_auto_hit_uuid = str_save.bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Stunned",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((str_save.bonus.uuid,str_save_auto_hit_uuid))

            #add conditional advantage to attacks within 5 feet
            to_target_contextual_uuid = target_entity.equipment.ac_bonus.to_target_static.add_advantage_modifier(AdvantageModifier(name="Stunned",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_contextual_uuid))
            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")
        
class Restrained(BaseCondition):
    """ can not move, disadvantage to attacks, disadvantage to dex saves, attackers have advantage"""
    name: str = "Restrained"
    description: str = "A restrained creature can't move and has disadvantage on Dexterity saving throws. Attack rolls against the creature have advantage."

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            #set max speed to 0
            speed_obj = target_entity.action_economy.movement
            speed_max_constrain_uuid = speed_obj.self_static.add_max_constraint(constraint=NumericalModifier(name="Restrained",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((speed_obj.uuid,speed_max_constrain_uuid))

            #add disadvantage to all attacks    
            self_static_attack_uuid = target_entity.equipment.attack_bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Restrained",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.attack_bonus.uuid,self_static_attack_uuid))

            #add disadvantage to dex saves
            dex_save = target_entity.saving_throws.get_saving_throw("dexterity")
            dex_save_auto_hit_uuid = dex_save.bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Restrained",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((dex_save.bonus.uuid,dex_save_auto_hit_uuid))

            #add advantage to attacks against this creature
            to_target_static_uuid = target_entity.equipment.ac_bonus.to_target_static.add_advantage_modifier(AdvantageModifier(name="Restrained",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_static_uuid))

            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")
            
            
class Unconscious(BaseCondition):
    """ incapacitated, can't move, can't speak, auto fails str and dex, same as prone and paralyzed regarding attacks"""
    name: str = "Unconscious"
    description: str = "A unconscious creature is incapacitated (see the condition), can't move, and can't speak. The creature automatically fails Strength and Dexterity saving throws. Attack rolls against the creature have advantage."

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            #like incapacitated first
            #set max actions, bonus actions, and reactions to 0
            action_max_constrain_uuid = target_entity.action_economy.actions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.action_economy.actions.uuid,action_max_constrain_uuid))
            bonus_action_max_constrain_uuid = target_entity.action_economy.bonus_actions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.action_economy.bonus_actions.uuid,bonus_action_max_constrain_uuid))
            reaction_max_constrain_uuid = target_entity.action_economy.reactions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.action_economy.reactions.uuid,reaction_max_constrain_uuid))
            #set max speed to 0
            speed_obj = target_entity.action_economy.movement
            speed_max_constrain_uuid = speed_obj.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((speed_obj.uuid,speed_max_constrain_uuid))

            #auto fail str and dex saves
            dex_save = target_entity.saving_throws.get_saving_throw("dexterity")
            dex_save_auto_hit_uuid = dex_save.bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Unconscious",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((dex_save.bonus.uuid,dex_save_auto_hit_uuid))
            str_save = target_entity.saving_throws.get_saving_throw("strength")
            str_save_auto_hit_uuid = str_save.bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Unconscious",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((str_save.bonus.uuid,str_save_auto_hit_uuid))

            #generic advantage on attacks against
            to_target_static_uuid = target_entity.equipment.ac_bonus.to_target_static.add_advantage_modifier(AdvantageModifier(name="Unconscious",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_static_uuid))

            #critical on attacks within 5 feet use static method from paralyzed
            to_target_contextual_critical_uuid = target_entity.equipment.ac_bonus.to_target_contextual.add_critical_modifier(modifier=ContextualCriticalModifier(name="Unconscious",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=Paralyzed.paralyzed_distance_critical))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_contextual_critical_uuid))

            #add prone like disadvantages (will cancel out the generic advantage for ranged attacks)
            to_target_contextual_advantage_uuid = target_entity.equipment.ac_bonus.to_target_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Unconscious",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=Prone.prone_distance_advantage))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_contextual_advantage_uuid))

            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")
            
            
            
            
            
            
            
            
            
            
