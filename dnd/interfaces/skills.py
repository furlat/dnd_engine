# dnd/interfaces/skills.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Any
from uuid import UUID

from dnd.core.events import AbilityName, SkillName
from dnd.interfaces.values import ModifiableValueSnapshot

class SkillSnapshot(BaseModel):
    """Interface model for a Skill"""
    uuid: UUID
    name: SkillName
    ability: AbilityName
    proficiency: bool
    expertise: bool
    skill_bonus: ModifiableValueSnapshot
    
    # Computed values
    proficiency_multiplier: float  # 0 for no proficiency, 1 for proficiency, 2 for expertise
    
    # The effective total bonus for this skill when calculated
    effective_bonus: Optional[int] = None
    
    @classmethod
    def from_engine(cls, skill, entity=None):
        """
        Create a snapshot from an engine Skill object
        
        Args:
            skill: The engine Skill object
            entity: Optional Entity object for calculating effective bonus
        """
        # Determine proficiency multiplier
        proficiency_multiplier = 0
        if skill.proficiency:
            proficiency_multiplier = 1
        if skill.expertise:
            proficiency_multiplier = 2
            
        # Calculate effective bonus if entity is provided
        effective_bonus = None
        if entity:
            total_bonus = entity.skill_bonus(None, skill.name)
            effective_bonus = total_bonus.normalized_score
        
        return cls(
            uuid=skill.uuid,
            name=skill.name,
            ability=skill.ability,
            proficiency=skill.proficiency,
            expertise=skill.expertise,
            skill_bonus=ModifiableValueSnapshot.from_engine(skill.skill_bonus),
            proficiency_multiplier=proficiency_multiplier,
            effective_bonus=effective_bonus
        )
    

class SkillSetSnapshot(BaseModel):
    """Interface model for SkillSet"""
    uuid: UUID
    name: str
    source_entity_uuid: UUID
    source_entity_name: Optional[str] = None
    
    # Individual skills indexed by name for easy access
    skills: Dict[SkillName, SkillSnapshot] = Field(default_factory=dict)
    
    # Lists for filtering
    proficient_skills: List[SkillName] = Field(default_factory=list)
    expertise_skills: List[SkillName] = Field(default_factory=list)
    
    # Skill categories
    skills_requiring_sight: List[SkillName] = Field(default_factory=list)
    skills_requiring_hearing: List[SkillName] = Field(default_factory=list)
    skills_requiring_speak: List[SkillName] = Field(default_factory=list)
    skills_social: List[SkillName] = Field(default_factory=list)
    
    @classmethod
    def from_engine(cls, skill_set, entity=None):
        """
        Create a snapshot from an engine SkillSet object
        
        Args:
            skill_set: The engine SkillSet object
            entity: Optional Entity object for calculating effective bonuses
        """
        # Create snapshots of all skills
        skills = {}
        
        from dnd.blocks.skills import (
            skills_requiring_sight,
            skills_requiring_hearing,
            skills_requiring_speak,
            skills_social,
            all_skills
        )
        
        # Create a snapshot for each skill
        for skill_name in all_skills:
            skill = skill_set.get_skill(skill_name)
            skills[skill_name] = SkillSnapshot.from_engine(skill, entity)
        
        # Create lists of proficient and expertise skills
        proficient_skills = [skill_name for skill_name, skill in skills.items() if skill.proficiency]
        expertise_skills = [skill_name for skill_name, skill in skills.items() if skill.expertise]
        
        return cls(
            uuid=skill_set.uuid,
            name=skill_set.name,
            source_entity_uuid=skill_set.source_entity_uuid,
            source_entity_name=skill_set.source_entity_name,
            skills=skills,
            proficient_skills=proficient_skills,
            expertise_skills=expertise_skills,
            skills_requiring_sight=skills_requiring_sight,
            skills_requiring_hearing=skills_requiring_hearing,
            skills_requiring_speak=skills_requiring_speak,
            skills_social=skills_social
        )



class SkillBonusCalculationSnapshot(BaseModel):
    """Model representing the detailed calculation of a skill's bonus"""
    skill_name: SkillName
    ability_name: AbilityName
    
    # The component parts
    proficiency_bonus: ModifiableValueSnapshot
    normalized_proficiency_bonus: ModifiableValueSnapshot  # After applying proficiency multiplier
    skill_bonus: ModifiableValueSnapshot
    ability_bonus: ModifiableValueSnapshot
    ability_modifier_bonus: ModifiableValueSnapshot
    
    # Cross-entity effects
    has_cross_entity_effects: bool = False
    target_entity_uuid: Optional[UUID] = None
    
    # The final combined result
    total_bonus: ModifiableValueSnapshot
    
    # Shortcut to commonly needed values
    final_modifier: int
    
    @classmethod
    def from_engine(cls, entity, skill_name):
        """
        Create a snapshot of the skill bonus calculation from an entity
        
        Args:
            entity: The engine Entity object
            skill_name: The name of the skill
        """
        # Get all the components using entity._get_bonuses_for_skill
        proficiency_bonus, skill_bonus, ability_bonus, ability_modifier_bonus = entity._get_bonuses_for_skill(skill_name)
        
        # The skill object for getting the ability name
        skill = entity.skill_set.get_skill(skill_name)
        ability_name = skill.ability
        
        # Calculate the total bonus
        total_bonus = entity.skill_bonus(None, skill_name)
        
        return cls(
            skill_name=skill_name,
            ability_name=ability_name,
            proficiency_bonus=ModifiableValueSnapshot.from_engine(entity.proficiency_bonus),
            normalized_proficiency_bonus=ModifiableValueSnapshot.from_engine(proficiency_bonus),
            skill_bonus=ModifiableValueSnapshot.from_engine(skill_bonus),
            ability_bonus=ModifiableValueSnapshot.from_engine(ability_bonus),
            ability_modifier_bonus=ModifiableValueSnapshot.from_engine(ability_modifier_bonus),
            has_cross_entity_effects=entity.target_entity_uuid is not None,
            target_entity_uuid=entity.target_entity_uuid,
            total_bonus=ModifiableValueSnapshot.from_engine(total_bonus),
            final_modifier=total_bonus.normalized_score
        )