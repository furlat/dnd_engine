# dnd/interfaces/abilities.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Any
from uuid import UUID

from dnd.interfaces.values import ModifiableValueSnapshot
from dnd.core.events import AbilityName

class AbilitySnapshot(BaseModel):
    """Interface model for an Ability"""
    uuid: UUID
    name: AbilityName
    ability_score: ModifiableValueSnapshot
    modifier_bonus: ModifiableValueSnapshot
    
    # Computed values
    modifier: int
    
    @classmethod
    def from_engine(cls, ability):
        """Create a snapshot from an engine Ability object"""
        return cls(
            uuid=ability.uuid,
            name=ability.name,
            ability_score=ModifiableValueSnapshot.from_engine(ability.ability_score),
            modifier_bonus=ModifiableValueSnapshot.from_engine(ability.modifier_bonus),
            modifier=ability.modifier
        )

class AbilityScoresSnapshot(BaseModel):
    """Interface model for AbilityScores"""
    uuid: UUID
    name: str
    source_entity_uuid: UUID
    source_entity_name: Optional[str] = None
    
    strength: AbilitySnapshot
    dexterity: AbilitySnapshot
    constitution: AbilitySnapshot
    intelligence: AbilitySnapshot
    wisdom: AbilitySnapshot
    charisma: AbilitySnapshot
    
    # Easy access list of all abilities
    abilities: List[AbilitySnapshot] = Field(default_factory=list)
    
    @classmethod
    def from_engine(cls, ability_scores):
        """Create a snapshot from an engine AbilityScores object"""
        # Create snapshot of each ability
        strength = AbilitySnapshot.from_engine(ability_scores.strength)
        dexterity = AbilitySnapshot.from_engine(ability_scores.dexterity)
        constitution = AbilitySnapshot.from_engine(ability_scores.constitution)
        intelligence = AbilitySnapshot.from_engine(ability_scores.intelligence)
        wisdom = AbilitySnapshot.from_engine(ability_scores.wisdom)
        charisma = AbilitySnapshot.from_engine(ability_scores.charisma)
        
        # Create list of all abilities for easy iteration
        abilities = [strength, dexterity, constitution, intelligence, wisdom, charisma]
        
        return cls(
            uuid=ability_scores.uuid,
            name=ability_scores.name,
            source_entity_uuid=ability_scores.source_entity_uuid,
            source_entity_name=ability_scores.source_entity_name,
            strength=strength,
            dexterity=dexterity,
            constitution=constitution,
            intelligence=intelligence,
            wisdom=wisdom,
            charisma=charisma,
            abilities=abilities
        )