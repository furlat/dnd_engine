# dnd/interfaces/health.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Any
from uuid import UUID

from app.models.values import ModifiableValueSnapshot
from dnd.core.modifiers import DamageType, ResistanceStatus

class HitDiceSnapshot(BaseModel):
    """Interface model for a HitDice"""
    uuid: UUID
    name: str
    hit_dice_value: ModifiableValueSnapshot
    hit_dice_count: ModifiableValueSnapshot
    mode: str  # "average", "maximums", or "roll"
    ignore_first_level: bool
    
    # Computed values
    hit_points: int
    
    @classmethod
    def from_engine(cls, hit_dice):
        """Create a snapshot from an engine HitDice object"""
        return cls(
            uuid=hit_dice.uuid,
            name=hit_dice.name,
            hit_dice_value=ModifiableValueSnapshot.from_engine(hit_dice.hit_dice_value),
            hit_dice_count=ModifiableValueSnapshot.from_engine(hit_dice.hit_dice_count),
            mode=hit_dice.mode,
            ignore_first_level=hit_dice.ignore_first_level,
            hit_points=hit_dice.hit_points
        )

class ResistanceSnapshot(BaseModel):
    """Interface model for damage type resistance"""
    damage_type: str
    status: str  # NORMAL, RESISTANCE, VULNERABILITY, IMMUNITY
    
    @classmethod
    def from_engine(cls, damage_type, status):
        """Create a snapshot from engine resistance data"""
        return cls(
            damage_type=damage_type.value,
            status=status.value
        )

class HealthSnapshot(BaseModel):
    """Interface model for Health"""
    uuid: UUID
    name: str
    source_entity_uuid: UUID
    source_entity_name: Optional[str] = None
    
    hit_dices: List[HitDiceSnapshot]
    max_hit_points_bonus: ModifiableValueSnapshot
    temporary_hit_points: ModifiableValueSnapshot
    damage_taken: int
    damage_reduction: ModifiableValueSnapshot
    
    # Resistances
    resistances: List[ResistanceSnapshot] = Field(default_factory=list)
    
    # Computed values
    hit_dices_total_hit_points: int
    total_hit_dices_number: int
    
    # Additional calculated values that need constitution
    current_hit_points: Optional[int] = None
    max_hit_points: Optional[int] = None
    
    @classmethod
    def from_engine(cls, health, entity=None):
        """
        Create a snapshot from an engine Health object
        
        Args:
            health: The engine Health object
            entity: The parent entity (optional, for constitution-based calculations)
        """
        # Create snapshots of hit dice
        hit_dices = [HitDiceSnapshot.from_engine(hit_dice) for hit_dice in health.hit_dices]
        
        # Create resistance snapshots
        resistance_snapshots = []
        for damage_type in DamageType:
            status = health.get_resistance(damage_type)
            # Only add non-default resistances (RESISTANCE, VULNERABILITY, IMMUNITY)
            if status in [ResistanceStatus.RESISTANCE, ResistanceStatus.VULNERABILITY, ResistanceStatus.IMMUNITY]:
                resistance_snapshots.append(ResistanceSnapshot.from_engine(damage_type, status))
        
        # Create base snapshot
        snapshot = cls(
            uuid=health.uuid,
            name=health.name,
            source_entity_uuid=health.source_entity_uuid,
            source_entity_name=health.source_entity_name,
            hit_dices=hit_dices,
            max_hit_points_bonus=ModifiableValueSnapshot.from_engine(health.max_hit_points_bonus),
            temporary_hit_points=ModifiableValueSnapshot.from_engine(health.temporary_hit_points),
            damage_taken=health.damage_taken,
            damage_reduction=ModifiableValueSnapshot.from_engine(health.damage_reduction),
            resistances=resistance_snapshots,
            hit_dices_total_hit_points=health.hit_dices_total_hit_points,
            total_hit_dices_number=health.total_hit_dices_number
        )
        
        # Add constitution-based calculations if entity is provided
        if entity and hasattr(entity, 'ability_scores') and hasattr(entity.ability_scores, 'constitution'):
            constitution_modifier = entity.ability_scores.constitution.modifier
            snapshot.max_hit_points = health.get_max_hit_dices_points(constitution_modifier) + health.max_hit_points_bonus.score
            snapshot.current_hit_points = health.get_total_hit_points(constitution_modifier)
            
        return snapshot 