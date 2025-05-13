# dnd/interfaces/saving_throws.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Any
from uuid import UUID

from dnd.core.events import AbilityName
from app.models.values import ModifiableValueSnapshot

class SavingThrowSnapshot(BaseModel):
    """Interface model for a SavingThrow"""
    uuid: UUID
    name: str  # Format: "{ability_name}_saving_throw"
    ability: AbilityName
    proficiency: bool
    bonus: ModifiableValueSnapshot
    
    # Computed values
    proficiency_multiplier: float  # 0 for no proficiency, 1 for proficiency
    
    # The effective total bonus for this saving throw when calculated
    effective_bonus: Optional[int] = None
    
    @classmethod
    def from_engine(cls, saving_throw, entity=None):
        """
        Create a snapshot from an engine SavingThrow object
        
        Args:
            saving_throw: The engine SavingThrow object
            entity: Optional Entity object for calculating effective bonus
        """
        # Determine proficiency multiplier
        proficiency_multiplier = 1 if saving_throw.proficiency else 0
        
        # Calculate effective bonus if entity is provided
        effective_bonus = None
        if entity:
            total_bonus = entity.saving_throw_bonus(None, saving_throw.ability)
            effective_bonus = total_bonus.normalized_score
        
        return cls(
            uuid=saving_throw.uuid,
            name=saving_throw.name,
            ability=saving_throw.ability,
            proficiency=saving_throw.proficiency,
            bonus=ModifiableValueSnapshot.from_engine(saving_throw.bonus),
            proficiency_multiplier=proficiency_multiplier,
            effective_bonus=effective_bonus
        )

class SavingThrowSetSnapshot(BaseModel):
    """Interface model for SavingThrowSet"""
    uuid: UUID
    name: str
    source_entity_uuid: UUID
    source_entity_name: Optional[str] = None
    
    # Individual saving throws indexed by ability name for easy access
    saving_throws: Dict[AbilityName, SavingThrowSnapshot] = Field(default_factory=dict)
    
    # Lists for filtering
    proficient_saving_throws: List[AbilityName] = Field(default_factory=list)
    
    @classmethod
    def from_engine(cls, saving_throw_set, entity=None):
        """
        Create a snapshot from an engine SavingThrowSet object
        
        Args:
            saving_throw_set: The engine SavingThrowSet object
            entity: Optional Entity object for calculating effective bonuses
        """
        # Create snapshots of all saving throws
        saving_throws = {}
        
        # Ability names used for saving throws
        ability_names = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
        
        # Create a snapshot for each saving throw
        for ability_name in ability_names:
            saving_throw = saving_throw_set.get_saving_throw(ability_name)
            saving_throws[ability_name] = SavingThrowSnapshot.from_engine(saving_throw, entity)
        
        # Create list of proficient saving throws
        proficient_saving_throws = [ability_name for ability_name, saving_throw in saving_throws.items() 
                                   if saving_throw.proficiency]
        
        return cls(
            uuid=saving_throw_set.uuid,
            name=saving_throw_set.name,
            source_entity_uuid=saving_throw_set.source_entity_uuid,
            source_entity_name=saving_throw_set.source_entity_name,
            saving_throws=saving_throws,
            proficient_saving_throws=proficient_saving_throws
        )

class SavingThrowBonusCalculationSnapshot(BaseModel):
    """Model representing the detailed calculation of a saving throw's bonus"""
    ability_name: AbilityName
    
    # The component parts
    proficiency_bonus: ModifiableValueSnapshot
    normalized_proficiency_bonus: ModifiableValueSnapshot  # After applying proficiency multiplier
    saving_throw_bonus: ModifiableValueSnapshot
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
    def from_engine(cls, entity, ability_name):
        """
        Create a snapshot of the saving throw bonus calculation from an entity
        
        Args:
            entity: The engine Entity object
            ability_name: The ability for the saving throw
        """
        # Get all the components using entity._get_bonuses_for_saving_throw
        proficiency_bonus, saving_throw_bonus, ability_bonus, ability_modifier_bonus = entity._get_bonuses_for_saving_throw(ability_name)
        
        # Calculate the total bonus
        total_bonus = entity.saving_throw_bonus(None, ability_name)
        
        return cls(
            ability_name=ability_name,
            proficiency_bonus=ModifiableValueSnapshot.from_engine(entity.proficiency_bonus),
            normalized_proficiency_bonus=ModifiableValueSnapshot.from_engine(proficiency_bonus),
            saving_throw_bonus=ModifiableValueSnapshot.from_engine(saving_throw_bonus),
            ability_bonus=ModifiableValueSnapshot.from_engine(ability_bonus),
            ability_modifier_bonus=ModifiableValueSnapshot.from_engine(ability_modifier_bonus),
            has_cross_entity_effects=entity.target_entity_uuid is not None,
            target_entity_uuid=entity.target_entity_uuid,
            total_bonus=ModifiableValueSnapshot.from_engine(total_bonus),
            final_modifier=total_bonus.normalized_score
        )

class SavingThrowResultSnapshot(BaseModel):
    """Represents the result of a saving throw"""
    ability_name: AbilityName
    dc: int
    roll: Any  # DiceRoll snapshot would go here
    outcome: str  # "Success" or "Failure"
    total_bonus: int
    roll_total: int
    
    # Entity information
    source_entity_uuid: UUID
    target_entity_uuid: UUID
    
    @classmethod
    def from_engine_result(cls, entity, ability_name, outcome, dice_roll, success, dc):
        """
        Create a snapshot from the results of a saving throw
        
        Args:
            entity: The entity making the saving throw
            ability_name: The ability used for the saving throw
            outcome: The AttackOutcome enum value
            dice_roll: The DiceRoll object
            success: Boolean indicating success
            dc: The difficulty class
        """
        return cls(
            ability_name=ability_name,
            dc=dc,
            roll=dice_roll.results,  # Simplified, would need a DiceRollSnapshot
            outcome="Success" if success else "Failure",
            total_bonus=dice_roll.bonus,
            roll_total=dice_roll.total,
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.target_entity_uuid or entity.uuid  # Default to self if no target
        )