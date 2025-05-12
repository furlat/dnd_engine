# dnd/interfaces/entity.py (updated for equipment)
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Any, Tuple
from uuid import UUID

from app.models.abilities import AbilityScoresSnapshot
from app.models.skills import SkillSetSnapshot, SkillBonusCalculationSnapshot
from app.models.equipment import EquipmentSnapshot, AttackBonusCalculationSnapshot, ACBonusCalculationSnapshot
from app.models.values import ModifiableValueSnapshot
from dnd.core.events import SkillName, WeaponSlot, AbilityName
from app.models.saving_throws import SavingThrowSetSnapshot, SavingThrowBonusCalculationSnapshot
from app.models.health import HealthSnapshot
from app.models.action_economy import ActionEconomySnapshot
from dnd.core.base_conditions import DurationType
from dnd.entity import Entity

class EntitySummary(BaseModel):
    """Lightweight summary of an entity's core stats"""
    uuid: UUID
    name: str
    current_hp: int
    max_hp: int
    armor_class: Optional[int] = None
    target_entity_uuid: Optional[UUID] = None
    position: Tuple[int,int]

    @classmethod
    def from_engine(cls, entity):
        """Create a summary from an engine Entity object"""
        # Get current and max HP
        con_modifier = entity.ability_scores.get_ability("constitution").get_combined_values()
        current_hp = entity.health.get_total_hit_points(constitution_modifier=con_modifier.normalized_score)
        max_hp = entity.health.get_max_hit_dices_points(constitution_modifier=con_modifier.normalized_score) + entity.health.max_hit_points_bonus.score
        
        # Get AC using the proper calculation method
        try:
            ac_value = entity.ac_bonus()
            ac = ac_value.normalized_score if hasattr(ac_value, "normalized_score") else None
        except Exception:
            ac = None
        
        return cls(
            uuid=entity.uuid,
            name=entity.name,
            current_hp=current_hp,
            max_hp=max_hp,
            armor_class=ac,
            target_entity_uuid=entity.target_entity_uuid,
            position=entity.position
        )

# Add a ConditionSnapshot interface
class ConditionSnapshot(BaseModel):
    """Interface model for a Condition"""
    uuid: UUID
    name: str
    description: Optional[str]
    duration_type: DurationType
    duration_value: Optional[Union[int, str]]  # int for ROUNDS, None for PERMANENT/UNTIL_LONG_REST, str for ON_CONDITION
    source_entity_name: Optional[str]
    source_entity_uuid: UUID
    applied: bool

class EntitySnapshot(BaseModel):
    """Interface model for an Entity snapshot"""
    uuid: UUID
    name: str
    description: Optional[str] = None
    target_entity_uuid: Optional[UUID] = None
    target_summary: Optional[EntitySummary] = None
    position: Tuple[int,int]
    # Main blocks
    ability_scores: AbilityScoresSnapshot
    skill_set: SkillSetSnapshot
    equipment: EquipmentSnapshot
    
    # Add other blocks as they're implemented
    saving_throws: SavingThrowSetSnapshot 
    health: HealthSnapshot
    action_economy: ActionEconomySnapshot
    
    # Core values
    proficiency_bonus: ModifiableValueSnapshot
    
    # Detailed calculations - only populated on demand
    skill_calculations: Dict[SkillName, SkillBonusCalculationSnapshot] = Field(default_factory=dict)
    attack_calculations: Dict[WeaponSlot, AttackBonusCalculationSnapshot] = Field(default_factory=dict)
    ac_calculation: Optional[ACBonusCalculationSnapshot] = None
    saving_throw_calculations: Dict[AbilityName, SavingThrowBonusCalculationSnapshot] = Field(default_factory=dict)
    
    # Active conditions
    active_conditions: Dict[str, ConditionSnapshot] = Field(default_factory=dict)
    
    @classmethod
    def from_engine(cls, entity, include_skill_calculations=False, include_attack_calculations=False, 
                   include_ac_calculation=False, include_saving_throw_calculations=False,
                   include_target_summary=False):
        """
        Create a snapshot from an engine Entity object
        
        Args:
            entity: The engine Entity object
            include_skill_calculations: Whether to include detailed skill calculations
            include_attack_calculations: Whether to include detailed attack calculations
            include_ac_calculation: Whether to include detailed AC calculation
            include_saving_throw_calculations: Whether to include detailed saving throw calculations
            include_target_summary: Whether to include target entity summary
        """
        # Create skill calculations if requested
        skill_calculations = {}
        if include_skill_calculations:
            from dnd.blocks.skills import all_skills
            for skill_name in all_skills:
                skill_calculations[skill_name] = SkillBonusCalculationSnapshot.from_engine(entity, skill_name)
        
        # Create attack calculations if requested
        attack_calculations = {}
        if include_attack_calculations:
            attack_calculations[WeaponSlot.MAIN_HAND] = AttackBonusCalculationSnapshot.from_engine(
                entity, WeaponSlot.MAIN_HAND)
            attack_calculations[WeaponSlot.OFF_HAND] = AttackBonusCalculationSnapshot.from_engine(
                entity, WeaponSlot.OFF_HAND)
        
        # Create AC calculation if requested
        ac_calculation = None
        if include_ac_calculation:
            ac_calculation = ACBonusCalculationSnapshot.from_engine(entity)
        
        # Create saving throw calculations if requested
        saving_throw_calculations = {}
        if include_saving_throw_calculations:
            ability_names = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
            from app.models.saving_throws import SavingThrowBonusCalculationSnapshot
            for ability_name in ability_names:
                saving_throw_calculations[ability_name] = SavingThrowBonusCalculationSnapshot.from_engine(entity, ability_name)

        # Create condition snapshots
        active_conditions = {}
        for name, condition in entity.active_conditions.items():
            duration_value = None
            if condition.duration.duration_type == DurationType.ROUNDS:
                duration_value = condition.duration.duration
            elif condition.duration.duration_type == DurationType.ON_CONDITION:
                duration_value = str(condition.duration.duration)
            
            active_conditions[name] = ConditionSnapshot(
                uuid=condition.uuid,
                name=condition.name,
                description=condition.description,
                duration_type=condition.duration.duration_type,
                duration_value=duration_value,
                source_entity_name=condition.source_entity_name,
                source_entity_uuid=condition.source_entity_uuid,
                applied=condition.applied
            )

        # Get target summary if requested
        target_summary = None
        if include_target_summary and entity.target_entity_uuid:
            target_entity = Entity.get(entity.target_entity_uuid)
            if target_entity:
                target_summary = EntitySummary.from_engine(target_entity)
        
        return cls(
            uuid=entity.uuid,
            name=entity.name,
            description=entity.description,
            target_entity_uuid=entity.target_entity_uuid,
            target_summary=target_summary,
            ability_scores=AbilityScoresSnapshot.from_engine(entity.ability_scores),
            skill_set=SkillSetSnapshot.from_engine(entity.skill_set, entity),
            equipment=EquipmentSnapshot.from_engine(entity.equipment, entity=entity),
            proficiency_bonus=ModifiableValueSnapshot.from_engine(entity.proficiency_bonus),
            skill_calculations=skill_calculations,
            attack_calculations=attack_calculations,
            ac_calculation=ac_calculation,
            saving_throws=SavingThrowSetSnapshot.from_engine(entity.saving_throws, entity),
            health=HealthSnapshot.from_engine(entity.health, entity),
            saving_throw_calculations=saving_throw_calculations,
            action_economy=ActionEconomySnapshot.from_engine(entity.action_economy, entity),
            active_conditions=active_conditions,
            position=entity.position
        )