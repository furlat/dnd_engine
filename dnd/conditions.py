from pydantic import Field, PrivateAttr
from dnd.core.base_conditions import BaseCondition, ConditionCategory, DurationType, ConditionApplicationEvent

from dnd.entity import Entity
from typing import Dict, Any, Optional, List, Literal, Tuple, Type
from dnd.core.modifiers import (  AdvantageModifier, ContextAwareAdvantage,
                                 AutoHitModifier, AdvantageStatus, AdvantageModifier, AutoHitStatus,
                                   ContextualNumericalModifier, NumericalModifier,
                                   ContextualCriticalModifier, CriticalModifier, CriticalStatus,
                                   ContextAwareNumerical, ContextAwareAutoHit, ContextualAutoHitModifier, ContextualAdvantageModifier)
from dnd.blocks.skills import all_skills, skills_requiring_sight, skills_requiring_hearing, skills_social
from dnd.core.base_block import SensesType, LightLevel
from dnd.core.gridmap import get_map
from uuid import UUID
from functools import partial
from dnd.core.events import Event, EventPhase, EventType, EventHandler, Trigger, EventQueue, TakeDamageEvent, SavingThrowEvent, DeathEvent, SpatialChangeEvent
from dnd.core.base_actions import ActionEvent
from dnd.core.dice import RollType
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, SkillCheckLogData, DiceRollDisplay, ModifierBreakdown
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
    condition_category: ConditionCategory = ConditionCategory.INTERNAL

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
    condition_category: ConditionCategory = ConditionCategory.INTERNAL

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
        entity.add_condition(has_attacked, parent_event=event)

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
        entity.add_condition(has_taken_damage, parent_event=event)

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
    condition_category: ConditionCategory = ConditionCategory.STATUS

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
    condition_category: ConditionCategory = ConditionCategory.STATUS

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
    condition_category: ConditionCategory = ConditionCategory.STATUS

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
            # Set invisibility flag (fires perceivability event to update observer senses)
            target_entity.set_invisible(True)
            # Unseen attacker advantage (uses senses-based check)
            self_contextual_uuid = target_entity.equipment.attack_bonus.self_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Invisible",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=unseen_attacker_advantage))
            outs.append((target_entity.equipment.attack_bonus.uuid,self_contextual_uuid))
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Invisible self to others advantage modifier to {target_entity.name}")
            # Unseen target disadvantage (uses senses-based check)
            to_target_contextual_uuid = target_entity.equipment.ac_bonus.to_target_contextual.add_advantage_modifier(modifier=ContextualAdvantageModifier(name="Invisible",source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid, callable=unseen_target_disadvantage))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_contextual_uuid))
            effect_event = effect_event.phase_to(EventPhase.EFFECT, update={"condition":self},status_message=f"Applied Invisible to target disadvantage modifier to {target_entity.name}")
            return outs, [], [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clear invisibility flag when condition is removed."""
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.set_invisible(False)
        return super()._remove(event)

    @staticmethod
    def can_see_invisible(observer: Entity) -> bool:
        """ returns true if the observer can see invisible"""
        return observer.senses.has_sense(SensesType.TRUESIGHT) or observer.senses.has_sense(SensesType.TREMORSENSE)


def unseen_attacker_advantage(source_entity_uuid: UUID, target_entity_uuid: Optional[UUID] = None, context: Optional[Dict[str, Any]] = None) -> Optional[AdvantageModifier]:
    """Advantage if attacker is NOT in target's senses. Used by both Hidden and Invisible."""
    if target_entity_uuid:
        target_entity = Entity.get(target_entity_uuid)
        if isinstance(target_entity, Entity) and source_entity_uuid not in target_entity.senses.entities:
            return AdvantageModifier(name="Unseen Attacker", value=AdvantageStatus.ADVANTAGE, source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid)
    return None


def unseen_target_disadvantage(source_entity_uuid: UUID, target_entity_uuid: Optional[UUID] = None, context: Optional[Dict[str, Any]] = None) -> Optional[AdvantageModifier]:
    """Disadvantage for attacker if defender is NOT in attacker's senses.
    source_entity_uuid is the invisible/hidden entity, target_entity_uuid is the attacker
    (via to_target_contextual propagation during attack computation)."""
    if target_entity_uuid:
        attacker = Entity.get(target_entity_uuid)
        if isinstance(attacker, Entity) and source_entity_uuid not in attacker.senses.entities:
            return AdvantageModifier(name="Unseen Target", value=AdvantageStatus.DISADVANTAGE, source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid)
    return None


class Paralyzed(BaseCondition):
    """A paralyzed creature is incapacitated (see the condition) and can't move or speak.
    The creature automatically fails Strength and Dexterity saving throws.
    Attack rolls against the creature have advantage.
    Any attack that hits the creature is a critical hit if the attacker is within 5 feet of the creature."""
    name: str = "Paralyzed"
    description: str = "A paralyzed creature is incapacitated (see the condition) and can't move or speak. The creature automatically fails Strength and Dexterity saving throws. Attack rolls against the creature have advantage. Any attack that hits the creature is a critical hit if the attacker is within 5 feet of the creature."

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

            # Clean up any light sources attached to the dead entity
            grid = get_map()
            grid.cleanup_block_light_sources(self.target_entity_uuid)

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
    if not isinstance(event, DeathEvent) or event.entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity or "Dead" in entity.active_conditions:
        return None

    # Apply Dead condition (includes Incapacitated as sub-condition)
    dead_condition = Dead(
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=source_entity_uuid
    )
    entity.add_condition(dead_condition, parent_event=event, check_save_throw=False)

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

class ConcentrationSlot(BaseObject):
    """A single concentration slot tracking one spell's linked conditions.

    Inherits from BaseObject for UUID registry integration.
    source_entity_uuid = caster UUID.
    """
    name: Optional[str] = "Concentration Slot"
    spell_name: str = ""
    linked_entries: List[Tuple[UUID, UUID]] = Field(default_factory=list)
    # each entry: (target_block_uuid, condition_uuid)


class Concentrating(BaseCondition):
    """
    Tracks concentration on a spell.

    When a caster concentrates on a spell:
    - Only one concentration spell can be active at a time (configurable via max_concentration_slots)
    - Taking damage requires a CON save (DC = max(10, damage/2))
    - Failing the save or casting another concentration spell ends this effect
    - When concentration ends, the spell effect is also removed via linked_conditions

    All spells should use SpellAction.ensure_concentration() which:
    1. Creates or reuses this condition on the caster
    2. Returns it for linking via add_linked_condition()

    Multi-slot support: When max_concentration_slots > 1, multiple different spells
    can coexist via concentration_slots dict. Each slot tracks one spell's linked conditions.
    """
    name: str = "Concentrating"
    description: str = "Concentrating on a spell"
    condition_category: ConditionCategory = ConditionCategory.STATUS
    child_removal_policy: Literal["none", "any", "last"] = "last"

    # What spell is being concentrated on (synced from slots)
    spell_name: str = ""

    # Multi-slot support: slot_uuid → ConcentrationSlot
    concentration_slots: Dict[UUID, ConcentrationSlot] = Field(default_factory=dict)

    # Routes add_linked_condition() calls to the correct slot
    _active_slot_uuid: Optional[UUID] = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        # Auto-create slot from spell_name (single path to slot creation)
        if self.spell_name and not self.concentration_slots:
            self._active_slot_uuid = self.add_slot(self.spell_name)

    def _sync_spell_name(self) -> None:
        """Keep spell_name field in sync with slots (slots are source of truth)."""
        self.spell_name = ", ".join(slot.spell_name for slot in self.concentration_slots.values()) or ""

    def get_slot_by_spell_name(self, spell_name: str) -> Optional[UUID]:
        """Find a slot UUID by spell name. Returns None if not found."""
        for slot_uuid, slot in self.concentration_slots.items():
            if slot.spell_name == spell_name:
                return slot_uuid
        return None

    def add_slot(self, spell_name: str) -> UUID:
        """Add a new concentration slot for a spell. Returns the slot UUID."""
        # Check if slot for this spell already exists
        existing = self.get_slot_by_spell_name(spell_name)
        if existing is not None:
            self._active_slot_uuid = existing
            self._sync_spell_name()
            return existing
        source_uuid = self.source_entity_uuid if self.source_entity_uuid else self.target_entity_uuid
        assert source_uuid is not None
        slot = ConcentrationSlot(
            source_entity_uuid=source_uuid,
            spell_name=spell_name,
        )
        self.concentration_slots[slot.uuid] = slot
        self._active_slot_uuid = slot.uuid
        self._sync_spell_name()
        return slot.uuid

    def drop_slot(self, slot_uuid: UUID, parent_event: Optional[Event] = None) -> None:
        """Remove a single spell slot and its linked conditions.

        If this is the last slot, removes the entire Concentrating condition.
        Otherwise, removes just this slot's conditions and updates state.
        """
        if slot_uuid not in self.concentration_slots:
            return

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return

        if len(self.concentration_slots) <= 1:
            # Last slot — remove entire Concentrating (full cascade)
            target.remove_condition("Concentrating", parent_event=parent_event)
            return

        # Remove this slot's linked conditions
        slot = self.concentration_slots[slot_uuid]
        for block_uuid, condition_uuid in slot.linked_entries:
            # Clear parent_link to prevent policy cascade back to us
            child = BaseCondition.get(condition_uuid)
            if child is not None and isinstance(child, BaseCondition):
                child.parent_link = None
            # Remove from our linked_conditions list
            pair = (block_uuid, condition_uuid)
            if pair in self.linked_conditions:
                self.linked_conditions.remove(pair)
            # Remove the actual condition
            block = BaseBlock.get(block_uuid)
            if block:
                block.remove_condition_by_uuid(condition_uuid, parent_event=parent_event)

        # Unregister slot from BaseObject registry, delete, and sync
        slot.remove_from_register()
        del self.concentration_slots[slot_uuid]
        self._sync_spell_name()

    def cleanup_if_no_effects(self, parent_event: Optional[Event] = None) -> None:
        """Remove Concentrating if it has no linked children (0-children bug fix)."""
        if not self.linked_conditions:
            target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
            if target and "Concentrating" in target.active_conditions:
                target.remove_condition("Concentrating", parent_event=parent_event)

    def add_linked_condition(self, target_block_uuid: UUID, condition_uuid: UUID) -> None:
        """Override to also route into the active slot."""
        super().add_linked_condition(target_block_uuid, condition_uuid)
        # Route into active slot
        if self._active_slot_uuid and self._active_slot_uuid in self.concentration_slots:
            self.concentration_slots[self._active_slot_uuid].linked_entries.append((target_block_uuid, condition_uuid))

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        handler_uuids: List[UUID] = []

        # Check for existing concentration
        existing = target.active_conditions.get("Concentrating")
        if existing and isinstance(existing, Concentrating):
            max_slots = target.max_concentration_slots.normalized_score

            # Evict oldest slots until under limit
            while len(existing.concentration_slots) >= max_slots:
                oldest_uuid = next(iter(existing.concentration_slots))
                existing.drop_slot(oldest_uuid, parent_event=declaration_event)
                # Re-check: drop_slot of last slot removes entire Concentrating
                existing = target.active_conditions.get("Concentrating")
                if not existing or not isinstance(existing, Concentrating):
                    break

            # Re-check after eviction loop
            existing = target.active_conditions.get("Concentrating")
            if existing and isinstance(existing, Concentrating):
                # MERGE: transfer existing's slots + linked_conditions to self
                for slot_uuid, slot in existing.concentration_slots.items():
                    if slot_uuid not in self.concentration_slots:
                        self.concentration_slots[slot_uuid] = slot
                    else:
                        self.concentration_slots[slot_uuid].linked_entries.extend(slot.linked_entries)
                for pair in existing.linked_conditions:
                    if pair not in self.linked_conditions:
                        self.linked_conditions.append(pair)
                # Update parent_links on children to point to self
                for _, condition_uuid in existing.linked_conditions:
                    child = BaseObject.get(condition_uuid)
                    if child and isinstance(child, BaseCondition):
                        child.parent_link = (target.uuid, self.uuid)
                # Clear existing to prevent cascade on removal
                existing.linked_conditions.clear()
                existing.sub_conditions.clear()
                # Don't unregister transferred slots — they're now ours
                existing.concentration_slots.clear()
                self._sync_spell_name()
                # Remove old Concentrating (no cascade since we cleared linked/sub)
                target.remove_condition("Concentrating", parent_event=declaration_event)

        # Register the concentration break handler
        def concentration_break_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
            """On damage, make CON save or lose concentration. On death, auto-break."""

            # Only trigger for the concentrating entity
            if event.target_entity_uuid != source_entity_uuid:
                return None

            # Get the entity
            entity = Entity.get(source_entity_uuid)
            if not entity:
                return None

            # Check if still concentrating
            if "Concentrating" not in entity.active_conditions:
                return None

            # Death: auto-break concentration (no save)
            if isinstance(event, DeathEvent):
                conc = entity.active_conditions.get("Concentrating")
                spell_name = "spell"
                if conc is not None and isinstance(conc, Concentrating):
                    spell_name = conc.spell_name
                entity.remove_condition("Concentrating", parent_event=event)
                return None

            # Damage: CON save to maintain
            if not isinstance(event, TakeDamageEvent):
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
                target_entity_name=entity.name,
                parent_event=event.uuid  # Link to damage event
            )

            _, _, success = entity.saving_throw(save_request)

            if not success:
                # Get spell name before removing
                conc = entity.active_conditions.get("Concentrating")
                spell_name = "spell"
                if conc is not None and isinstance(conc, Concentrating):
                    spell_name = conc.spell_name

                entity.remove_condition("Concentrating", parent_event=event)
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
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=self.target_entity_uuid
                ),
                Trigger(
                    event_type=EventType.DEATH,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=self.target_entity_uuid
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
        """When concentration ends, spell effects are cleaned up via linked_conditions."""
        # Unregister all ConcentrationSlot objects from BaseObject registry
        for slot in self.concentration_slots.values():
            slot.remove_from_register()
        return super()._remove(removal_event)


class ConcentrationActionMarker(BaseCondition):
    """Marker condition for action-grant concentration spells (CallLightning, Sunbeam).

    When removed (via concentration break), deregisters the granted action template.
    """
    name: str = "Concentration Action"
    description: str = "Tracking concentration on an action-grant spell"
    condition_category: ConditionCategory = ConditionCategory.STATUS
    action_name: str = ""

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Tracking concentration on {self.action_name}"
        )
        return [], [], [], [], effect_event

    def _remove(self, removal_event: Optional[Event] = None) -> Optional[Event]:
        entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if entity and self.action_name:
            entity.unregister_action(self.action_name)
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


class Hidden(BaseCondition):
    """Hidden from observers via Stealth. Entity cannot be perceived by observers
    whose passive perception is below the stealth result.

    Removed automatically when the entity:
    - Makes an attack
    - Takes damage
    - Becomes incapacitated

    While hidden, the entity has advantage on attacks (Unseen Attacker).
    """
    name: str = "Hidden"
    description: str = "Hidden from observers via Stealth"
    stealth_result: int = Field(default=0, description="Stealth check result used as perception DC")
    creation_lineage_uuid: Optional[UUID] = Field(default=None, description="Lineage UUID of the event that created this condition")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity, Entity):
            outs: List[Tuple[UUID, UUID]] = []
            handler_uuids: List[UUID] = []

            # Set stealth DC flag (fires perceivability event to update observer senses)
            target_entity.set_stealth_dc(self.stealth_result)

            # Unseen Attacker advantage (shared callable with Invisible)
            adv_uuid = target_entity.equipment.attack_bonus.self_contextual.add_advantage_modifier(
                modifier=ContextualAdvantageModifier(
                    name="Hidden (Unseen Attacker)",
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                    callable=unseen_attacker_advantage
                )
            )
            outs.append((target_entity.equipment.attack_bonus.uuid, adv_uuid))

            effect_event = declaration_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Hidden to {target_entity.name} (Stealth DC {self.stealth_result})"
            )

            # Store creation lineage to avoid self-triggering reveal handler
            # Use parent action's lineage if available (e.g. potion/item actions add condition before EFFECT)
            parent = declaration_event.get_parent_event()
            self.creation_lineage_uuid = parent.lineage_uuid if parent else declaration_event.lineage_uuid

            # Reveal handler: removes Hidden on attack, damage, incapacitated, spell cast, shove,
            # or when tile light changes to VERY_BRIGHT / entity moves into VERY_BRIGHT tile
            handler = EventHandler(
                name="Hidden: Reveal",
                source_entity_uuid=target_entity.uuid,
                trigger_conditions=[
                    Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.TAKE_DAMAGE, event_phase=EventPhase.EFFECT,
                            event_target_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.CONDITION_APPLICATION, event_phase=EventPhase.EFFECT,
                            event_target_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.CAST_SPELL, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.BASE_ACTION, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.SPATIAL_LIGHT_CHANGED, event_phase=EventPhase.EFFECT),
                    Trigger(event_type=EventType.SPATIAL_ENTITY_ENTERED, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.MOVEMENT_COLLISION, event_phase=EventPhase.EFFECT),
                ],
                event_processor=hidden_reveal_processor
            )
            target_entity.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

            return outs, handler_uuids, [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clear stealth DC flag when condition is removed."""
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.set_stealth_dc(None)
        return super()._remove(event)


# Actions that do NOT break stealth (everything else reveals)
NON_REVEALING_ACTIONS = {
    "Dash", "Dodge", "Disengage", "Hide", "Stand Up", "Drop Prone",
    "Open Door", "Close Door",
    "Ignite Torch", "Extinguish Torch", "Light Wall Torch", "Extinguish Wall Torch",
}


def hidden_reveal_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """Remove Hidden on attack, damage, incapacitated, spell cast, revealing action,
    or when tile becomes VERY_BRIGHT (light change or movement)."""
    # Only reveal on the last EFFECT event (after damage is fully applied)
    if not event.is_last:
        return None

    # For MOVEMENT_COLLISION: de-stealth hidden entity if collision at their position
    if event.event_type == EventType.MOVEMENT_COLLISION:
        entity = Entity.get(source_entity_uuid)
        if entity and isinstance(entity, Entity) and isinstance(event, SpatialChangeEvent):
            if event.position == entity.position and "Hidden" in entity.active_conditions:
                entity.remove_condition("Hidden", parent_event=event)
        return None

    # For SPATIAL_LIGHT_CHANGED: check if tile under hidden entity became VERY_BRIGHT
    if event.event_type == EventType.SPATIAL_LIGHT_CHANGED:
        entity = Entity.get(source_entity_uuid)
        if entity and isinstance(entity, Entity) and "Hidden" in entity.active_conditions:
            if isinstance(event, SpatialChangeEvent) and event.position == entity.position:
                tile = get_map().get_tile(*entity.position)
                if tile and tile.resolved_light_level == LightLevel.VERY_BRIGHT:
                    # Use movement event as parent (not light event) so removal
                    # appears in movement combat log tree
                    removal_parent = event.get_parent_event() or event
                    entity.remove_condition("Hidden", parent_event=removal_parent)
        return None

    # For SPATIAL_ENTITY_ENTERED: check if entity moved into VERY_BRIGHT tile
    if event.event_type == EventType.SPATIAL_ENTITY_ENTERED:
        entity = Entity.get(source_entity_uuid)
        if entity and isinstance(entity, Entity) and "Hidden" in entity.active_conditions:
            tile = get_map().get_tile(*entity.position)
            if tile and tile.resolved_light_level == LightLevel.VERY_BRIGHT:
                entity.remove_condition("Hidden", parent_event=event)
        return None

    # For CONDITION_APPLICATION: only break on Incapacitated
    if event.event_type == EventType.CONDITION_APPLICATION:
        if not isinstance(event, ConditionApplicationEvent) or event.condition.name != "Incapacitated":
            return None

    # For BASE_ACTION: only break on revealing actions (not Dash, Dodge, etc.)
    if event.event_type == EventType.BASE_ACTION:
        if not isinstance(event, ActionEvent):
            return None
        if event.name in NON_REVEALING_ACTIONS:
            return None

    entity = Entity.get(source_entity_uuid)
    if entity and isinstance(entity, Entity) and "Hidden" in entity.active_conditions:
        condition = entity.active_conditions.get("Hidden")
        # Skip if this event is from the same lineage that created the condition
        if isinstance(condition, Hidden) and condition.creation_lineage_uuid == event.lineage_uuid:
            return None
        entity.remove_condition("Hidden", parent_event=event)
    return None


class InvisibilityEffect(BaseCondition):
    """Applied by Invisibility spell. Sets is_invisible flag and unseen attacker/target modifiers.
    Removed automatically when the entity attacks or casts a spell."""
    name: str = "Invisible"
    description: str = "Invisible until attacking or casting a spell"
    creation_lineage_uuid: Optional[UUID] = Field(default=None, description="Lineage UUID of the event that created this condition")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity, Entity):
            outs: List[Tuple[UUID, UUID]] = []
            handler_uuids: List[UUID] = []

            # Set invisibility flag
            target_entity.set_invisible(True)

            # Unseen attacker advantage (shared callable with Invisible/Hidden)
            self_ctx_uuid = target_entity.equipment.attack_bonus.self_contextual.add_advantage_modifier(
                modifier=ContextualAdvantageModifier(
                    name="Invisible (Unseen Attacker)",
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                    callable=unseen_attacker_advantage
                )
            )
            outs.append((target_entity.equipment.attack_bonus.uuid, self_ctx_uuid))

            # Unseen target disadvantage
            to_target_ctx_uuid = target_entity.equipment.ac_bonus.to_target_contextual.add_advantage_modifier(
                modifier=ContextualAdvantageModifier(
                    name="Invisible (Unseen Target)",
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                    callable=unseen_target_disadvantage
                )
            )
            outs.append((target_entity.equipment.ac_bonus.uuid, to_target_ctx_uuid))

            effect_event = declaration_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Invisibility to {target_entity.name}"
            )

            # Store creation lineage to avoid self-triggering reveal handler
            # Use parent action's lineage if available (e.g. potion/item actions add condition before EFFECT)
            parent = declaration_event.get_parent_event()
            self.creation_lineage_uuid = parent.lineage_uuid if parent else declaration_event.lineage_uuid

            # Self-removal handler: attack, spell cast, or revealing action breaks invisibility
            handler = EventHandler(
                name="Invisibility: Reveal",
                source_entity_uuid=target_entity.uuid,
                trigger_conditions=[
                    Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.CAST_SPELL, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.BASE_ACTION, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                ],
                event_processor=invisibility_reveal_processor
            )
            target_entity.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

            return outs, handler_uuids, [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity")

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clear invisibility flag when condition is removed."""
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.set_invisible(False)
        return super()._remove(event)


def invisibility_reveal_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """Remove Invisible (InvisibilityEffect) when entity attacks, casts a spell, or performs a revealing action."""
    # Only reveal on the last EFFECT event (after damage is fully applied)
    if not event.is_last:
        return None

    # For BASE_ACTION: only break on revealing actions (not Dash, Dodge, etc.)
    if event.event_type == EventType.BASE_ACTION:
        if not isinstance(event, ActionEvent):
            return None
        if event.name in NON_REVEALING_ACTIONS:
            return None

    entity = Entity.get(source_entity_uuid)
    if entity and isinstance(entity, Entity) and "Invisible" in entity.active_conditions:
        condition = entity.active_conditions.get("Invisible")
        if isinstance(condition, InvisibilityEffect):
            # Skip if this event is from the same lineage that created the condition
            if condition.creation_lineage_uuid == event.lineage_uuid:
                return None
            entity.remove_condition("Invisible", parent_event=event)
    return None


class GreaterInvisibilityEffect(BaseCondition):
    """BG3-style Greater Invisibility. Sets is_invisible flag.
    On attack or spell cast, rolls Stealth check vs escalating DC to maintain.
    DC starts at base_dc and increases by 1 per successful check."""
    name: str = "Invisible"
    description: str = "Greater Invisibility - Stealth check to maintain"
    check_count: int = Field(default=0, description="Number of successful stealth checks")
    base_dc: int = Field(default=15, description="Starting DC for stealth check")
    creation_lineage_uuid: Optional[UUID] = Field(default=None, description="Lineage UUID of the event that created this condition")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity, Entity):
            outs: List[Tuple[UUID, UUID]] = []
            handler_uuids: List[UUID] = []

            # Set invisibility flag
            target_entity.set_invisible(True)

            # Unseen attacker advantage
            self_ctx_uuid = target_entity.equipment.attack_bonus.self_contextual.add_advantage_modifier(
                modifier=ContextualAdvantageModifier(
                    name="Greater Invisibility (Unseen Attacker)",
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                    callable=unseen_attacker_advantage
                )
            )
            outs.append((target_entity.equipment.attack_bonus.uuid, self_ctx_uuid))

            # Unseen target disadvantage
            to_target_ctx_uuid = target_entity.equipment.ac_bonus.to_target_contextual.add_advantage_modifier(
                modifier=ContextualAdvantageModifier(
                    name="Greater Invisibility (Unseen Target)",
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid,
                    callable=unseen_target_disadvantage
                )
            )
            outs.append((target_entity.equipment.ac_bonus.uuid, to_target_ctx_uuid))

            effect_event = declaration_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Greater Invisibility to {target_entity.name}"
            )

            # Store creation lineage to avoid self-triggering stealth check handler
            # Use parent action's lineage if available (e.g. potion/item actions add condition before EFFECT)
            parent = declaration_event.get_parent_event()
            self.creation_lineage_uuid = parent.lineage_uuid if parent else declaration_event.lineage_uuid

            # Stealth check handler: rolls stealth vs escalating DC on attack/cast/revealing action
            handler = EventHandler(
                name="Greater Invisibility: Stealth Check",
                source_entity_uuid=target_entity.uuid,
                trigger_conditions=[
                    Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.CAST_SPELL, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                    Trigger(event_type=EventType.BASE_ACTION, event_phase=EventPhase.EFFECT,
                            event_source_entity_uuid=target_entity.uuid),
                ],
                event_processor=greater_invisibility_check_processor
            )
            target_entity.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

            return outs, handler_uuids, [], [], effect_event
        else:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity")

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clear invisibility flag when condition is removed."""
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.set_invisible(False)
        return super()._remove(event)


def greater_invisibility_check_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """Stealth check to maintain Greater Invisibility. DC = base_dc + check_count."""
    # Only check on the last EFFECT event (after damage is fully applied)
    if not event.is_last:
        return None

    # For BASE_ACTION: only break on revealing actions (not Dash, Dodge, etc.)
    if event.event_type == EventType.BASE_ACTION:
        if not isinstance(event, ActionEvent):
            return None
        if event.name in NON_REVEALING_ACTIONS:
            return None

    entity = Entity.get(source_entity_uuid)
    if not entity or not isinstance(entity, Entity):
        return None
    condition = entity.active_conditions.get("Invisible")
    if not condition or not isinstance(condition, GreaterInvisibilityEffect):
        return None

    # Skip if this event is from the same lineage that created the condition
    if condition.creation_lineage_uuid == event.lineage_uuid:
        return None

    dc = condition.base_dc + condition.check_count
    skill_bonus = entity.skill_bonus(target_entity_uuid=None, skill_name="stealth")
    stealth_roll, check_event = entity.roll_d20_event(skill_bonus, RollType.CHECK, skill_name="stealth")
    # Link as child of the triggering event so it appears as a sub-entry in combat log
    check_event.parent_event = event.uuid
    event.add_child_event(check_event)
    success = stealth_roll.total >= dc

    if success:
        condition.check_count += 1  # Harder next time
    else:
        entity.remove_condition("Invisible", parent_event=check_event)

    # Build combat log for the stealth check event
    entity_name = entity.name
    # Extract d20 result from DiceRoll.results
    roll_results = stealth_roll.results if isinstance(stealth_roll.results, list) else [stealth_roll.results]
    d20_used = roll_results[0] if roll_results else 0
    adv_status = None
    if stealth_roll.advantage_status == AdvantageStatus.ADVANTAGE:
        adv_status = "advantage"
    elif stealth_roll.advantage_status == AdvantageStatus.DISADVANTAGE:
        adv_status = "disadvantage"

    roll_display = DiceRollDisplay(
        dice_str="d20",
        results=roll_results,
        bonus=stealth_roll.bonus,
        total=stealth_roll.total,
        all_d20_rolls=roll_results if len(roll_results) > 1 else None,
        d20_used=d20_used,
        advantage_status=adv_status
    )

    if success:
        compact = f"{{cyan:{entity_name}}} maintains invisibility (Stealth {stealth_roll.total} vs DC {dc})"
    else:
        compact = f"{{cyan:{entity_name}}} loses invisibility! (Stealth {stealth_roll.total} vs DC {dc})"

    verbose = f"{{cyan:{entity_name}}} Stealth check: d20({d20_used}) +{stealth_roll.bonus} = {stealth_roll.total} vs DC {dc}"
    if success:
        verbose += " → maintains invisibility"
    else:
        verbose += " → {{red:loses invisibility!}}"

    # Build bonus/advantage breakdowns from the skill MV
    stealth_bonus_breakdown: List[ModifierBreakdown] = []
    stealth_advantage_breakdown: List[ModifierBreakdown] = []
    for mod in skill_bonus.get_breakdown():
        stealth_bonus_breakdown.append(ModifierBreakdown(
            name=mod.get('name', 'Unknown'),
            value=mod.get('value', 0),
            source=mod.get('source', 'self')
        ))
    for mod in skill_bonus.get_full_advantage_breakdown():
        adv_val = mod.get('value', 'inactive')
        if adv_val == 'advantage':
            stealth_advantage_breakdown.append(ModifierBreakdown(
                name=mod.get('name', 'Unknown'), value=1, source=mod.get('source', 'self')
            ))
        elif adv_val == 'disadvantage':
            stealth_advantage_breakdown.append(ModifierBreakdown(
                name=mod.get('name', 'Unknown'), value=-1, source=mod.get('source', 'self')
            ))

    check_event.combat_log = CombatLogEntry(
        entry_type=CombatLogEntryType.SKILL_CHECK,
        source_name=entity_name,
        source_uuid=str(entity.uuid),
        compact=compact,
        verbose=verbose,
        detailed=verbose,
        success=success,
        data=SkillCheckLogData(
            entity_name=entity_name,
            entity_uuid=str(entity.uuid),
            skill="stealth",
            dc=dc,
            roll=roll_display,
            bonus_breakdown=stealth_bonus_breakdown,
            advantage_breakdown=stealth_advantage_breakdown,
            success=success
        ).model_dump()
    )

    # Complete the event — collects child logs (removal event) as sub_entries
    check_event.phase_to(EventPhase.COMPLETION)
    return None


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
    HIDDEN = "HIDDEN"
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
    ConditionType.HIDDEN: Hidden,
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
