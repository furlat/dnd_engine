from dnd.core.base_conditions import BaseCondition, DurationType

from dnd.entity import Entity
from typing import Dict, Any, Optional, List, Tuple, Type
from dnd.core.modifiers import (  AdvantageModifier, ContextAwareAdvantage,
                                 AutoHitModifier, AdvantageStatus, AdvantageModifier, AutoHitStatus,
                                   ContextualNumericalModifier, NumericalModifier,
                                   ContextualCriticalModifier, CriticalModifier, CriticalStatus,
                                   ContextAwareNumerical, ContextAwareAutoHit, ContextualAutoHitModifier, ContextualAdvantageModifier)
from dnd.blocks.skills import all_skills, skills_requiring_sight, skills_requiring_hearing, skills_social
from dnd.blocks.sensory import SensesType
from uuid import UUID
from functools import partial
from dnd.core.events import Event, EventPhase, EventType, EventHandler, Trigger, EventQueue, TakeDamageEvent, SavingThrowEvent
from enum import Enum


# =============================================================================
# GENERIC COMBAT STATE CONDITIONS
# =============================================================================
# These conditions track combat state for ALL entities (not class-specific).
# They are applied by global handlers registered in setup_standard_actions().

class HasAttacked(BaseCondition):
    """
    Generic marker: entity attacked this turn using an action.

    This is a global combat state condition tracked for ALL entities.
    Applied automatically when any action-costing attack executes.
    Expires at the start of the entity's next turn (duration=1 round).

    Used by:
    - Extra Attack (Fighter) - prerequisite for using extra attacks
    - Rage Maintenance (Barbarian) - checks HasAttacked OR HasTakenDamage

    Note: Only action-cost attacks trigger this (not opportunity attacks or
    bonus action attacks from Two-Weapon Fighting).
    """
    name: str = "HasAttacked"
    description: str = "Has made an attack this turn using an action"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        # No modifiers - just a marker condition
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Marked as HasAttacked"
        )
        return [], [], [], [], effect_event


class HasTakenDamage(BaseCondition):
    """
    Generic marker: entity took damage this turn.

    This is a global combat state condition tracked for ALL entities.
    Applied automatically when the entity takes damage.
    Expires at the start of the entity's next turn (duration=1 round).

    Used by:
    - Rage Maintenance (Barbarian) - checks HasAttacked OR HasTakenDamage
    """
    name: str = "HasTakenDamage"
    description: str = "Took damage this turn"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        # No modifiers - just a marker condition
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Marked as HasTakenDamage"
        )
        return [], [], [], [], effect_event


# =============================================================================
# GENERIC COMBAT STATE HANDLERS
# =============================================================================

def has_attacked_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """
    Generic processor: applies HasAttacked condition on ANY attack.

    Triggers on ATTACK at EXECUTION phase.
    Tracks ALL attacks (action, bonus action, reaction) for rage maintenance.
    Uses EventQueue.is_first_at_phase() to ensure single application.
    """
    # Only trigger for the attacker's own attacks
    if event.source_entity_uuid != source_entity_uuid:
        return None

    # Only on non-canceled events
    if event.canceled:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Only process FIRST event at EXECUTION phase for this attack
    if not EventQueue.is_first_at_phase(event):
        return None

    # Apply HasAttacked if not already present (tracks ANY attack for rage maintenance)
    if "HasAttacked" not in entity.active_conditions:
        has_attacked = HasAttacked(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=source_entity_uuid
        )
        has_attacked.duration.duration_type = DurationType.ROUNDS
        has_attacked.duration.duration = 1
        entity.add_condition(has_attacked)

    return None  # Don't modify the attack event


def has_taken_damage_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """
    Generic processor: applies HasTakenDamage when entity takes damage.

    Triggers on TAKE_DAMAGE at EFFECT phase (when we are the target).
    """
    # We are the TARGET of damage
    if event.target_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Apply HasTakenDamage if not already present
    if "HasTakenDamage" not in entity.active_conditions:
        has_taken_damage = HasTakenDamage(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=source_entity_uuid
        )
        has_taken_damage.duration.duration_type = DurationType.ROUNDS
        has_taken_damage.duration.duration = 1
        entity.add_condition(has_taken_damage)

    return None  # Don't modify the damage event


def create_has_attacked_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create an EventHandler that applies HasAttacked on action-cost attack execution."""
    return EventHandler(
        name="HasAttacked Tracker",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.ATTACK,
                event_phase=EventPhase.EXECUTION
            )
        ],
        event_processor=has_attacked_processor
    )


def create_has_taken_damage_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create an EventHandler that applies HasTakenDamage when taking damage."""
    return EventHandler(
        name="HasTakenDamage Tracker",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.TAKE_DAMAGE,
                event_phase=EventPhase.EFFECT
            )
        ],
        event_processor=has_taken_damage_processor
    )




class Blinded(BaseCondition):
    name: str = "Blinded"
    description: str = "A blinded creature can't see and automatically fails any ability check that requires sight. Attack rolls against the creature have advantage, and the creature's attack rolls have disadvantage."
    

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        
        elif isinstance(target_entity,Entity):
            #the modifier is applied to the target entity henceh the source and target are switched
            outs = []
            self_static_condition_uuid = target_entity.equipment.attack_bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Blinded",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            to_target_static_condition_uuid =target_entity.equipment.ac_bonus.to_target_static.add_advantage_modifier(AdvantageModifier(name="Blinded",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied attack advantage modifers from Blinded to {target_entity.name}")
            outs.append((target_entity.equipment.attack_bonus.uuid,self_static_condition_uuid))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_static_condition_uuid))
            for skill in skills_requiring_sight:
                skill_obj = target_entity.skill_set.get_skill(skill)
               
                modifier_uuid=skill_obj.skill_bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Blinded",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
                outs.append((skill_obj.skill_bonus.uuid,modifier_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied skill advantage modifers from Blinded to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")
        

        
class Charmed(BaseCondition):
    name: str = "Charmed"
    description: str = "A charmed creature can't attack the charmer or target the charmer with harmful abilities or magical effects."
    
    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            #prevent attacking the charmer
            charmed_attack_check = self.get_charmed_attack_check()
            self_static_condition_uuid = target_entity.equipment.attack_bonus.self_contextual.add_auto_hit_modifier(modifier=ContextualAutoHitModifier(name="Charmed",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=charmed_attack_check))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied contextual auto hit modifers from Charmed to {target_entity.name}")
            outs.append((target_entity.equipment.attack_bonus.uuid,self_static_condition_uuid))

            # Add advantage on social checks for the charmer, this is done through the to_target_contextual
            charmed_skill_check = self.get_charmed_skill_check()
            for skill in skills_social:
                skill_obj = target_entity.skill_set.get_skill(skill)
                to_target_static_condition_uuid = skill_obj.skill_bonus.to_target_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Charmed",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=charmed_skill_check))
                outs.append((skill_obj.skill_bonus.uuid,to_target_static_condition_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied contextual advantage modifers from Charmed to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")
    

    @staticmethod
    def charmed_attack_check(charmer_id: UUID, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str, Any]] = None) -> Optional[AutoHitModifier]:
        """ this function is used to prevent the charmer from attacking the charmed entity this is used by the charmed entity
        hence source is the charmed and target is the charmer"""
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

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
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
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied base speed modifier from Dashing to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")


class Deafened(BaseCondition):
    name: str = "Deafened"
    description: str = "A deafened creature can't hear and automatically fails any ability check that requires hearing."

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            for skill in skills_requiring_hearing:
                skill_obj = target_entity.skill_set.get_skill(skill)
                modifier_uuid = skill_obj.skill_bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Deafened",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
                outs.append((skill_obj.skill_bonus.uuid,modifier_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied skills auto hit modifers from Deafened to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")


class Dodging(BaseCondition):
    name: str = "Dodging"
    description: str = "A dodging creature has advantage on Dexterity saving throws against being grappled."

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            #add disadvantage to attacks against this creature
            to_target_static_condition_uuid =target_entity.equipment.ac_bonus.to_target_static.add_advantage_modifier(AdvantageModifier(name="Dodging",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_static_condition_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Dodging self to others advantage modifier to {target_entity.name}")
            #add advantage to Dexterity saving throws
            dex_save = target_entity.saving_throws.get_saving_throw("dexterity")
            dex_save_modifier_uuid = dex_save.bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Dodging",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((dex_save.bonus.uuid,dex_save_modifier_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Dodging Dexterity saving throw advantage modifier to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")


class Disengaging(BaseCondition):
    """
    A disengaging creature's movement doesn't provoke opportunity attacks.

    This condition has no modifiers - it's checked directly by the opportunity
    attack handler in reactions.py.
    """
    name: str = "Disengaging"
    description: str = "Your movement doesn't provoke opportunity attacks for the rest of the turn."

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        # No modifiers to apply - this condition is checked by opportunity attack logic
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Disengaging to {self.target_entity_uuid}"
        )
        return [], [], [], [], effect_event


class Frightened(BaseCondition):
    """ A frightened creature has disadvantage on attack rolls and ability checks and can not move while the frightener is in sight"""
    name: str = "Frightened"
    description: str = "A frightened creature has disadvantage on attack rolls and ability checks and can not move while the frightener is in sight"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            #add disadvantage to attacks from this creature inside the equipment attack bonus static
            disadvantage_uuid = target_entity.equipment.attack_bonus.self_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Frightened",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=self.get_frightener_in_senses_disadvantage()))
            outs.append((target_entity.equipment.attack_bonus.uuid,disadvantage_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Frightened self to others disadvantage modifier to {target_entity.name}")
            #add disadvantage to all ability checks using the same callable
            for skill in all_skills:
                skill_obj = target_entity.skill_set.get_skill(skill)
                skills_modifier_uuid = skill_obj.skill_bonus.self_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Frightened",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=self.get_frightener_in_senses_disadvantage()))
                outs.append((skill_obj.skill_bonus.uuid,skills_modifier_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Frightened skill disadvantage modifier to {target_entity.name}")
            #adds max constraint to the movement value when the frightener is in the senses of the target
            movement_value = target_entity.action_economy.movement
            max_movement_constraint_uuid = movement_value.self_contextual.add_max_constraint(constraint=ContextualNumericalModifier(name="Frightened",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=self.get_frigthener_in_senses_zero_max_speed()))
            outs.append((movement_value.uuid,max_movement_constraint_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Frightened movement constraint to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")
            
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

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            speed_obj = target_entity.action_economy.movement
            grappled_modifer_uuid = speed_obj.self_static.add_max_constraint(constraint=NumericalModifier(name="Grappled",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((speed_obj.uuid,grappled_modifer_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Grappled max speed constraint to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

class Incapacitated(BaseCondition):
    """ max actions, bonus actions, movement and reactions are set to 0 in self static"""
    name: str = "Incapacitated"
    description: str = "A incapacitated creature can't take actions"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            #set max actions, bonus actions, and reactions to 0
            action_max_constrain_uuid = target_entity.action_economy.actions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.action_economy.actions.uuid,action_max_constrain_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Incapacitated action max constraint to {target_entity.name}")
            bonus_action_max_constrain_uuid = target_entity.action_economy.bonus_actions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.action_economy.bonus_actions.uuid,bonus_action_max_constrain_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Incapacitated bonus action max constraint to {target_entity.name}")
            reaction_max_constrain_uuid = target_entity.action_economy.reactions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.action_economy.reactions.uuid,reaction_max_constrain_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Incapacitated reaction max constraint to {target_entity.name}")
            #set max speed to 0
            speed_obj = target_entity.action_economy.movement
            speed_max_constrain_uuid = speed_obj.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((speed_obj.uuid,speed_max_constrain_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Incapacitated movement max constraint to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")
        
class Invisible(BaseCondition):
    """ adds advantage to all attacks from this creature against creature that can not see invisible
     gives disadvantage to all attacks against this creature if the observer can not see invisible"""
    name: str = "Invisible"
    description:str = "An invisible creature is impossible to see without the aid of magic or a special sense"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            #add conditional advantage to all attacks from this creature against creature that can not see invisible
            self_contextual_uuid = target_entity.equipment.attack_bonus.self_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Invisible",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=self.target_can_not_see_invisible_advantage))
            outs.append((target_entity.equipment.attack_bonus.uuid,self_contextual_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Invisible self to others advantage modifier to {target_entity.name}")
            #add conditional disadvantage to all attacks against this creature if the observer can not see invisible
            to_target_contextual_uuid = target_entity.equipment.ac_bonus.to_target_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Invisible",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=self.target_can_not_see_invisible_disadvantage))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_contextual_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Invisible to target disadvantage modifier to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

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

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            sub_conditions_uuids:List[UUID] = []
            #like incapacitated first
            #set max actions, bonus actions, and reactions to 0
            execution_event = declaration_event.phase_to(EventPhase.EXECUTION,update={"condition":self},status_message=f"Applying Incapacitated sub-condition to {target_entity.name}")
            incapacitated_condition = Incapacitated(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.target_entity_uuid,parent_condition=self.uuid)
            sub_conditions_application_event = target_entity.add_condition(incapacitated_condition,parent_event=execution_event)
            if sub_conditions_application_event is not None and sub_conditions_application_event.phase == EventPhase.COMPLETION:
                sub_condition_applied= True
                sub_conditions_uuids.append(incapacitated_condition.uuid)
            else:
                sub_condition_applied= False
            
            effect_event = execution_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Incapacitated to {target_entity.name}" if sub_condition_applied else f"Failed to apply Incapacitated to {target_entity.name}")
            
            # action_max_constrain_uuid = target_entity.action_economy.actions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            # outs.append((target_entity.action_economy.actions.uuid,action_max_constrain_uuid))
            # bonus_action_max_constrain_uuid = target_entity.action_economy.bonus_actions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            # outs.append((target_entity.action_economy.bonus_actions.uuid,bonus_action_max_constrain_uuid))
            # reaction_max_constrain_uuid = target_entity.action_economy.reactions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            # outs.append((target_entity.action_economy.reactions.uuid,reaction_max_constrain_uuid))
            # #set max speed to 0
            # speed_obj = target_entity.action_economy.movement
            # speed_max_constrain_uuid = speed_obj.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            # outs.append((speed_obj.uuid,speed_max_constrain_uuid))

            # Auto-fail STR and DEX saves
            dex_save = target_entity.saving_throws.get_saving_throw("dexterity")
            dex_save_auto_hit_uuid = dex_save.bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Paralyzed",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((dex_save.bonus.uuid,dex_save_auto_hit_uuid))
            str_save = target_entity.saving_throws.get_saving_throw("strength")
            str_save_auto_hit_uuid = str_save.bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Paralyzed",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((str_save.bonus.uuid,str_save_auto_hit_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Paralyzed STR and DEX saves auto hit modifiers to {target_entity.name}")

            #add conditional critical to attacks within 5 feet 
            to_target_contextual_uuid = target_entity.equipment.ac_bonus.to_target_contextual.add_critical_modifier(modifier=ContextualCriticalModifier(name="Paralyzed",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=self.paralyzed_distance_critical))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_contextual_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Paralyzed to target contextual critical modifier to {target_entity.name}")
            return outs, [], sub_conditions_uuids, [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")
            
    @staticmethod
    def paralyzed_distance_critical(source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str, Any]] = None) -> Optional[CriticalModifier]:
        """ if the the source entity is within 5 feet of the target creature it returns a auto critical modifier
        this is given by the paralized creature to attackers via to_target_contextual"""
        if target_entity_uuid:
            target_entity = Entity.get(target_entity_uuid)
            source_entity = Entity.get(source_entity_uuid)
            if isinstance(source_entity,Entity) and isinstance(target_entity,Entity):
                distance = source_entity.senses.get_feet_distance(target_entity.position)
                if distance <= 5:
                    return CriticalModifier(name="Paralyzed",value=CriticalStatus.AUTOCRIT,source_entity_uuid=source_entity_uuid,target_entity_uuid=target_entity_uuid)
        return None

            

class Poisoned(BaseCondition):
    """ adds disadvantage to all attacks and ability checks"""
    name: str = "Poisoned"
    description: str = "A poisoned creature has disadvantage on all ability checks and attack rolls"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []   
            #add disadvantage to all attacks
            self_static_attack_uuid = target_entity.equipment.attack_bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Poisoned",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.attack_bonus.uuid,self_static_attack_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Poisoned self to others advantage modifier to {target_entity.name}")
            #add disadvantage to all ability checks
            for skill in all_skills:
                skill_obj = target_entity.skill_set.get_skill(skill)
                skill_static_modifier_uuid = skill_obj.skill_bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Poisoned",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
                outs.append((skill_obj.skill_bonus.uuid,skill_static_modifier_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Poisoned to all skills disadvantage modifier to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

class Prone(BaseCondition):
    """BG3-style Prone: disadvantage to attacks, advantage/disadvantage for attackers based on distance.

    Auto-stands at turn start (deducts half movement). No manual StandUp action needed.
    If knocked prone during own turn with movement available, immediately stands (condition doesn't apply).
    """
    name: str = "Prone"
    description: str = "A prone creature has disadvantage on all attack rolls. Attack rolls against the creature have advantage if within 5ft, disadvantage otherwise. Automatically stands at turn start (costs half movement)."

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity, Entity):
            # BG3-style: If it's the entity's turn and they have movement, they immediately stand
            # Consume movement and cancel the condition (don't apply it)
            # Note: is_my_turn is only True AFTER action_economy reset, so this only fires mid-turn
            if target_entity.is_my_turn:
                base_movement = target_entity.action_economy.get_base_value("movement")
                half_movement = base_movement // 2
                current_movement = target_entity.action_economy.movement.normalized_score
                if current_movement >= half_movement:
                    target_entity.action_economy.consume("movement", half_movement)
                    # Cancel the event - condition won't be added to active_conditions
                    return [], [], [], [], declaration_event.cancel(
                        status_message=f"{target_entity.name} fell prone but immediately stood up"
                    )

            # Normal case: apply Prone modifiers
            outs: List[Tuple[UUID, UUID]] = []
            handler_uuids: List[UUID] = []

            # Add disadvantage to all attacks
            self_static_attack_uuid = target_entity.equipment.attack_bonus.self_static.add_advantage_modifier(
                AdvantageModifier(name="Prone", value=AdvantageStatus.DISADVANTAGE,
                                  source_entity_uuid=self.target_entity_uuid, target_entity_uuid=self.source_entity_uuid)
            )
            outs.append((target_entity.equipment.attack_bonus.uuid, self_static_attack_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self},
                                                       status_message=f"Applied Prone to {target_entity.name}")

            # Add conditional advantage to attacks within 5 feet
            to_target_contextual_uuid = target_entity.equipment.ac_bonus.to_target_contextual.add_advantage_modifier(
                modifier=ContextualAdvantageModifier(name="Prone", source_entity_uuid=self.target_entity_uuid,
                                                     target_entity_uuid=self.source_entity_uuid, callable=self.prone_distance_advantage)
            )
            outs.append((target_entity.equipment.ac_bonus.uuid, to_target_contextual_uuid))

            # Note: Auto-stand handler is registered by setup_standard_actions(), not here
            # This ensures it's always present regardless of when Prone is applied

            return outs, handler_uuids, [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

    @staticmethod
    def prone_distance_advantage(source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str, Any]] = None) -> Optional[AdvantageModifier]:
        """ if the source entity is within 5 feet of the target creature it returns an advantage modifier
        this is given by the prone creature to attackers via to_target_contextual"""
        if target_entity_uuid:
            target_entity = Entity.get(target_entity_uuid)
            source_entity = Entity.get(source_entity_uuid)
            if isinstance(source_entity, Entity) and isinstance(target_entity, Entity):
                distance = source_entity.senses.get_feet_distance(target_entity.position)
                if distance <= 5:
                    return AdvantageModifier(name="Prone", value=AdvantageStatus.ADVANTAGE, source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid)
                else:
                    return AdvantageModifier(name="Prone", value=AdvantageStatus.DISADVANTAGE, source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid)
        return None



class Stunned(BaseCondition):
    """ like restrained, auto fails str and dex, advantage on attacks against the creature"""
    name: str = "Stunned"
    description: str = "A stunned creature is incapacitated (see the condition), can't move, and can't speak. The creature automatically fails Strength and Dexterity saving throws. Attack rolls against the creature have advantage."

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            sub_conditions_uuids: List[UUID] = []

            execution_event = declaration_event.phase_to(EventPhase.EXECUTION,update={"condition":self},status_message=f"Applying Incapacitated sub-condition to {target_entity.name}")

            incapacitated_condition = Incapacitated(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.target_entity_uuid,parent_condition=self.uuid)
            sub_conditions_application_event = target_entity.add_condition(incapacitated_condition,parent_event=execution_event)
            if sub_conditions_application_event is not None and sub_conditions_application_event.phase == EventPhase.COMPLETION:
                sub_condition_applied = True
                sub_conditions_uuids.append(incapacitated_condition.uuid)
            else:
                sub_condition_applied = False

            effect_event = execution_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Incapacitated to {target_entity.name}" if sub_condition_applied else f"Failed to apply Incapacitated to {target_entity.name}")

            # Auto-fail STR and DEX saves
            dex_save = target_entity.saving_throws.get_saving_throw("dexterity")
            dex_save_auto_hit_uuid = dex_save.bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Stunned",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((dex_save.bonus.uuid,dex_save_auto_hit_uuid))
            str_save = target_entity.saving_throws.get_saving_throw("strength")
            str_save_auto_hit_uuid = str_save.bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Stunned",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((str_save.bonus.uuid,str_save_auto_hit_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Stunned STR and DEX saves auto hit modifiers to {target_entity.name}" if sub_condition_applied else f"Failed to apply Stunned STR and DEX saves auto hit modifiers to {target_entity.name}")

            #add advantage to attacks against this creature
            to_target_static_uuid = target_entity.equipment.ac_bonus.to_target_static.add_advantage_modifier(AdvantageModifier(name="Stunned",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_static_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Stunned to target advantage modifier to {target_entity.name}" if sub_condition_applied else f"Failed to apply Stunned to target advantage modifier to {target_entity.name}")
            return outs, [], sub_conditions_uuids, [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")
        
class Restrained(BaseCondition):
    """ can not move, disadvantage to attacks, disadvantage to dex saves, attackers have advantage"""
    name: str = "Restrained"
    description: str = "A restrained creature can't move and has disadvantage on Dexterity saving throws. Attack rolls against the creature have advantage."

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            #set max speed to 0
            speed_obj = target_entity.action_economy.movement
            speed_max_constrain_uuid = speed_obj.self_static.add_max_constraint(constraint=NumericalModifier(name="Restrained",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((speed_obj.uuid,speed_max_constrain_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Restrained max speed constraint to {target_entity.name}")

            #add disadvantage to all attacks    
            self_static_attack_uuid = target_entity.equipment.attack_bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Restrained",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.attack_bonus.uuid,self_static_attack_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Restrained to self disadvantage modifier to {target_entity.name}")

            #add disadvantage to dex saves
            dex_save = target_entity.saving_throws.get_saving_throw("dexterity")
            dex_save_auto_hit_uuid = dex_save.bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Restrained",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((dex_save.bonus.uuid,dex_save_auto_hit_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Restrained to dex save auto hit modifier to {target_entity.name}")
            #add advantage to attacks against this creature
            to_target_static_uuid = target_entity.equipment.ac_bonus.to_target_static.add_advantage_modifier(AdvantageModifier(name="Restrained",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_static_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Restrained to target contextual advantage modifier to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")
            
            
class Unconscious(BaseCondition):
    """ incapacitated, can't move, can't speak, auto fails str and dex, same as prone and paralyzed regarding attacks"""
    name: str = "Unconscious"
    description: str = "A unconscious creature is incapacitated (see the condition), can't move, and can't speak. The creature automatically fails Strength and Dexterity saving throws. Attack rolls against the creature have advantage."

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            sub_conditions_uuids = []
            #like incapacitated first
            #set max actions, bonus actions, and reactions to 0
            # action_max_constrain_uuid = target_entity.action_economy.actions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            # outs.append((target_entity.action_economy.actions.uuid,action_max_constrain_uuid))
            # bonus_action_max_constrain_uuid = target_entity.action_economy.bonus_actions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            # outs.append((target_entity.action_economy.bonus_actions.uuid,bonus_action_max_constrain_uuid))
            # reaction_max_constrain_uuid = target_entity.action_economy.reactions.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            # outs.append((target_entity.action_economy.reactions.uuid,reaction_max_constrain_uuid))
            # #set max speed to 0
            # speed_obj = target_entity.action_economy.movement
            # speed_max_constrain_uuid = speed_obj.self_static.add_max_constraint(constraint=NumericalModifier(name="Incapacitated",value=0,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            # outs.append((speed_obj.uuid,speed_max_constrain_uuid))
            execution_event = declaration_event.phase_to(EventPhase.EXECUTION,update={"condition":self},status_message=f"Applying Incapacitated sub-condition to {target_entity.name}")
            incapacitated_condition = Incapacitated(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.target_entity_uuid,parent_condition=self.uuid)
            sub_conditions_application_event = target_entity.add_condition(incapacitated_condition,parent_event=execution_event)
            if sub_conditions_application_event is not None and sub_conditions_application_event.phase == EventPhase.COMPLETION:
                sub_condition_applied= True
                sub_conditions_uuids.append(incapacitated_condition.uuid)
            else:
                sub_condition_applied= False

            effect_event = execution_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Incapacitated to {target_entity.name}" if sub_condition_applied else f"Failed to apply Incapacitated to {target_entity.name}")

            #auto fail str and dex saves
            dex_save = target_entity.saving_throws.get_saving_throw("dexterity")
            dex_save_auto_hit_uuid = dex_save.bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Unconscious",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((dex_save.bonus.uuid,dex_save_auto_hit_uuid))
            str_save = target_entity.saving_throws.get_saving_throw("strength")
            str_save_auto_hit_uuid = str_save.bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Unconscious",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((str_save.bonus.uuid,str_save_auto_hit_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Unconscious STR and DEX saves auto hit modifiers to {target_entity.name}" if sub_condition_applied else f"Failed to apply Unconscious STR and DEX saves auto hit modifiers to {target_entity.name}")

            #generic advantage on attacks against
            to_target_static_uuid = target_entity.equipment.ac_bonus.to_target_static.add_advantage_modifier(AdvantageModifier(name="Unconscious",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_static_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Unconscious to target contextual advantage modifier to {target_entity.name}" if sub_condition_applied else f"Failed to apply Unconscious to target contextual advantage modifier to {target_entity.name}")
            #critical on attacks within 5 feet use static method from paralyzed
            to_target_contextual_critical_uuid = target_entity.equipment.ac_bonus.to_target_contextual.add_critical_modifier(modifier=ContextualCriticalModifier(name="Unconscious",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=Paralyzed.paralyzed_distance_critical))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_contextual_critical_uuid))

            #add prone like disadvantages (will cancel out the generic advantage for ranged attacks)
            to_target_contextual_advantage_uuid = target_entity.equipment.ac_bonus.to_target_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Unconscious",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=Prone.prone_distance_advantage))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_contextual_advantage_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Unconscious to target contextual advantage modifier to {target_entity.name}" if sub_condition_applied else f"Failed to apply Unconscious to target contextual advantage modifier to {target_entity.name}")
            return outs, [], sub_conditions_uuids, [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")


class Dead(BaseCondition):
    """
    The entity is dead.

    Includes Incapacitated as sub-condition, which sets all action economy
    to max 0. This automatically prevents:
    - Taking actions (actions = 0)
    - Bonus actions (bonus_actions = 0)
    - Reactions like OA (reactions = 0)
    - Movement (movement = 0)

    The entity remains in registries for resurrection/looting.
    GridMap marks entity as non-blocking separately (in Encounter._handle_death).
    """
    name: str = "Dead"
    description: str = "The entity has died and cannot act."
    # Default duration is PERMANENT (via Duration defaults)

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity, Entity):
            outs: List[Tuple[UUID,UUID]] = []
            sub_conditions_uuids: List[UUID] = []

            # Apply Incapacitated sub-condition (handles all action economy disabling)
            execution_event = declaration_event.phase_to(
                EventPhase.EXECUTION,
                update={"condition": self},
                status_message=f"Applying Incapacitated sub-condition to {target_entity.name}"
            )
            incapacitated_condition = Incapacitated(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                parent_condition=self.uuid
                # Default duration is PERMANENT
            )
            sub_conditions_application_event = target_entity.add_condition(
                incapacitated_condition,
                parent_event=execution_event,
                check_save_throw=False
            )
            if sub_conditions_application_event is not None and sub_conditions_application_event.phase == EventPhase.COMPLETION:
                sub_conditions_uuids.append(incapacitated_condition.uuid)

            effect_event = execution_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Dead condition to {target_entity.name}"
            )
            return outs, [], sub_conditions_uuids, [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")


def death_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """Apply Dead condition when entity dies.

    This processor is triggered by DEATH events. It applies the Dead condition
    and marks the entity as non-blocking in GridMap.

    This uses the event handler pattern to avoid circular imports between
    entity.py and conditions.py.
    """

    # Only process for our entity (DeathEvent has entity_uuid)
    event_entity_uuid = getattr(event, 'entity_uuid', None)
    if event_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity or "Dead" in entity.active_conditions:
        return None

    # Apply Dead condition (includes Incapacitated as sub-condition)
    dead_condition = Dead(
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=source_entity_uuid
    )
    entity.add_condition(dead_condition, check_save_throw=False)

    # Mark entity as non-blocking so corpses don't prevent movement
    entity.non_blocking = True

    return None


def create_death_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create handler that applies Dead condition on DEATH event.

    This handler is registered for all entities via setup_standard_actions().
    When a DEATH event fires for this entity, it applies the Dead condition.
    """
    return EventHandler(
        name="Death Condition Handler",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(event_type=EventType.DEATH, event_phase=EventPhase.EXECUTION)
        ],
        event_processor=death_processor
    )


# =============================================================================
# CONCENTRATION SYSTEM
# =============================================================================

class Concentrating(BaseCondition):
    """
    Tracks concentration on a spell.

    When a caster concentrates on a spell:
    - Only one concentration spell can be active at a time
    - Taking damage requires a CON save (DC = max(10, damage/2))
    - Failing the save or casting another concentration spell ends this effect
    - When concentration ends, the spell effect is also removed via linked_conditions

    This condition is applied when a concentration spell is cast, not directly.
    The spell's _apply() should:
    1. Create this condition on the caster
    2. Apply the spell effect condition to the target
    3. Call concentration.add_linked_condition(target.uuid, effect.uuid)

    The linked_conditions mechanism (inherited from BaseCondition) handles
    cross-block cleanup automatically when concentration breaks.
    """
    name: str = "Concentrating"
    description: str = "Concentrating on a spell"

    # What spell is being concentrated on
    spell_name: str = ""

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [],[], declaration_event.cancel(status_message="Target not found")

        handler_uuids: List[UUID] = []

        # End any existing concentration first
        if "Concentrating" in target.active_conditions:
            target.remove_condition("Concentrating")

        # Register the concentration break handler
        def concentration_break_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
            """On damage, make CON save or lose concentration."""

            # Only trigger for the concentrating entity taking damage
            if event.target_entity_uuid != source_entity_uuid:
                return None

            if not isinstance(event, TakeDamageEvent):
                return None

            # Get the entity
            entity = Entity.get(source_entity_uuid)
            if not entity:
                return None

            # Check if still concentrating
            if "Concentrating" not in entity.active_conditions:
                return None

            # Calculate DC: 10 or half damage, whichever is higher
            damage = event.final_damage if event.final_damage is not None else event.total_damage
            if damage <= 0:
                return None  # No damage, no check needed

            dc = max(10, damage // 2)

            # Make Constitution saving throw
            # Note: The caster is both source and target of this save
            save_request = SavingThrowEvent(
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=source_entity_uuid,
                ability_name="constitution",
                dc=dc,
                source_entity_name=entity.name,
                use_register=False  # Don't register in global registry
            )

            _, _, success = entity.saving_throw(save_request)

            if not success:
                # Get spell name before removing
                conc = entity.active_conditions.get("Concentrating")
                spell_name = "spell"
                if conc is not None and isinstance(conc, Concentrating):
                    spell_name = conc.spell_name

                entity.remove_condition("Concentrating")
                return event.model_copy(update={
                    "concentration_broken": True,
                    "status_message": f"{entity.name} lost concentration on {spell_name} (failed DC {dc} CON save)"
                })

            return None

        handler = EventHandler(
            name=f"Concentration Check ({self.spell_name})",
            source_entity_uuid=self.target_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TAKE_DAMAGE,
                    event_phase=EventPhase.COMPLETION  # After damage is finalized
                )
            ],
            event_processor=concentration_break_processor
        )

        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"{target.name} is concentrating on {self.spell_name}"
        )

        return [], handler_uuids, [], [], effect_event

    def _remove(self, removal_event: Optional[Event] = None) -> Optional[Event]:
        """When concentration ends, spell effects are cleaned up via linked_conditions.

        IMPORTANT: Must call super()._remove() to trigger EXECUTION and EFFECT phases
        so cleanup handlers can respond to the condition removal event.

        Note: Cross-entity spell effect cleanup is now handled automatically by
        BaseCondition.remove_linked_conditions() - no manual cleanup needed here.
        """
        # Call parent to trigger event phase transitions (EXECUTION -> EFFECT)
        # This allows cleanup handlers subscribed to CONDITION_REMOVAL at EFFECT to fire
        return super()._remove(removal_event)


class NoReactions(BaseCondition):
    """
    Prevents the target from taking reactions.

    Used by Shocking Grasp - "target can't take reactions until the start
    of its next turn."

    This condition sets max reactions to 0 via self_static.
    Duration: 1 round (expires at start of target's next turn).
    """
    name: str = "No Reactions"
    description: str = "Cannot take reactions"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")

        outs: List[Tuple[UUID, UUID]] = []

        # Set max reactions to 0
        reaction_max_uuid = target_entity.action_economy.reactions.self_static.add_max_constraint(
            constraint=NumericalModifier(
                name="No Reactions",
                value=0,
                source_entity_uuid=self.source_entity_uuid or self.target_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
        )
        outs.append((target_entity.action_economy.reactions.uuid, reaction_max_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied No Reactions to {target_entity.name}"
        )
        return outs, [], [], [], effect_event


class ConditionType(str, Enum):
    # NOTE: Fighter-specific conditions (HasAttacked, ActionSurging) moved to dnd/classes/fighter.py
    BLINDED = "BLINDED"
    CHARMED = "CHARMED"
    DASHING = "DASHING"
    DEAD = "DEAD"
    DEAFENED = "DEAFENED"
    DISENGAGING = "DISENGAGING"
    DODGING = "DODGING"
    FRIGHTENED = "FRIGHTENED"
    GRAPPLED = "GRAPPLED"
    INCAPACITATED = "INCAPACITATED"
    INVISIBLE = "INVISIBLE"
    PARALYZED = "PARALYZED"
    POISONED = "POISONED"
    PRONE = "PRONE"
    RESTRAINED = "RESTRAINED"
    STUNNED = "STUNNED"
    UNCONSCIOUS = "UNCONSCIOUS"

# Map enum values to condition classes
CONDITION_MAP: Dict[ConditionType, Type[BaseCondition]] = {
    ConditionType.BLINDED: Blinded,
    ConditionType.CHARMED: Charmed,
    ConditionType.DASHING: Dashing,
    ConditionType.DEAD: Dead,
    ConditionType.DEAFENED: Deafened,
    ConditionType.DISENGAGING: Disengaging,
    ConditionType.DODGING: Dodging,
    ConditionType.FRIGHTENED: Frightened,
    ConditionType.GRAPPLED: Grappled,
    ConditionType.INCAPACITATED: Incapacitated,
    ConditionType.INVISIBLE: Invisible,
    ConditionType.PARALYZED: Paralyzed,
    ConditionType.POISONED: Poisoned,
    ConditionType.PRONE: Prone,
    ConditionType.RESTRAINED: Restrained,
    ConditionType.STUNNED: Stunned,
    ConditionType.UNCONSCIOUS: Unconscious,
}

def create_condition(
    condition_type: ConditionType,
    source_entity_uuid: UUID,
    target_entity_uuid: UUID,
    duration_type: DurationType = DurationType.PERMANENT,
    duration_rounds: Optional[int] = None
) -> BaseCondition:
    """
    Factory function to create a condition of the specified type.
    
    Args:
        condition_type: The type of condition to create
        source_entity_uuid: UUID of the entity causing the condition
        target_entity_uuid: UUID of the entity receiving the condition
        duration_type: Type of duration (PERMANENT, ROUNDS, etc.)
        duration_rounds: Number of rounds if duration_type is ROUNDS
        
    Returns:
        BaseCondition: The created condition instance
    """
    condition_class = CONDITION_MAP[condition_type]
    
    # Create the condition
    condition = condition_class(
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=target_entity_uuid
    )
    
    # Set up duration
    if duration_type == DurationType.ROUNDS and duration_rounds is not None:
        condition.duration.duration_type = DurationType.ROUNDS
        condition.duration.duration = duration_rounds
    else:
        condition.duration.duration_type = duration_type
        condition.duration.duration = None
        
    return condition 
