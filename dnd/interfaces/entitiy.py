# dnd/interfaces/entity.py (updated for equipment)
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Any
from uuid import UUID

from dnd.interfaces.abilities import AbilityScoresSnapshot
from dnd.interfaces.skills import SkillSetSnapshot, SkillBonusCalculationSnapshot
from dnd.interfaces.equipment import EquipmentSnapshot, AttackBonusCalculationSnapshot, ACBonusCalculationSnapshot
from dnd.interfaces.values import ModifiableValueSnapshot
from dnd.core.events import SkillName, WeaponSlot
from dnd.interfaces.saving_throws import SavingThrowSetSnapshot
from dnd.interfaces.health import HealthSnapshot

class EntitySnapshot(BaseModel):
    """Interface model for an Entity snapshot"""
    uuid: UUID
    name: str
    description: Optional[str] = None
    
    # Main blocks
    ability_scores: AbilityScoresSnapshot
    skill_set: SkillSetSnapshot
    equipment: EquipmentSnapshot
    
    # Add other blocks as they're implemented
    saving_throws: SavingThrowSetSnapshot 
    health: HealthSnapshot
    # action_economy: ActionEconomySnapshot
    
    # Core values
    proficiency_bonus: ModifiableValueSnapshot
    
    # Detailed calculations - only populated on demand
    skill_calculations: Dict[SkillName, SkillBonusCalculationSnapshot] = Field(default_factory=dict)
    attack_calculations: Dict[WeaponSlot, AttackBonusCalculationSnapshot] = Field(default_factory=dict)
    ac_calculation: Optional[ACBonusCalculationSnapshot] = None
    
    # Other important data
    # active_conditions: Dict[str, ConditionSnapshot] = Field(default_factory=dict)
    
    @classmethod
    def from_engine(cls, entity, include_skill_calculations=False, include_attack_calculations=False, include_ac_calculation=False):
        """
        Create a snapshot from an engine Entity object
        
        Args:
            entity: The engine Entity object
            include_skill_calculations: Whether to include detailed skill calculations
            include_attack_calculations: Whether to include detailed attack calculations
            include_ac_calculation: Whether to include detailed AC calculation
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
        
        return cls(
            uuid=entity.uuid,
            name=entity.name,
            description=entity.description,
            ability_scores=AbilityScoresSnapshot.from_engine(entity.ability_scores),
            skill_set=SkillSetSnapshot.from_engine(entity.skill_set, entity),
            equipment=EquipmentSnapshot.from_engine(entity.equipment),
            proficiency_bonus=ModifiableValueSnapshot.from_engine(entity.proficiency_bonus),
            skill_calculations=skill_calculations,
            attack_calculations=attack_calculations,
            ac_calculation=ac_calculation,
            saving_throws=SavingThrowSetSnapshot.from_engine(entity.saving_throws, entity),
            health=HealthSnapshot.from_engine(entity.health, entity),
            # Add other blocks as they're implemented
        )