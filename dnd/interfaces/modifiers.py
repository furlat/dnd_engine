# dnd/interfaces/modifiers.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Any, ClassVar
from uuid import UUID
from enum import Enum

# Re-export the enums from the engine for consistency
from dnd.core.modifiers import (
    AdvantageStatus, AutoHitStatus, CriticalStatus, 
    ResistanceStatus, DamageType, Size
)

class ModifierSnapshot(BaseModel):
    """Base model for all modifier snapshots in the interface"""
    uuid: UUID
    name: Optional[str] = None
    source_entity_uuid: UUID
    source_entity_name: Optional[str] = None
    target_entity_uuid: Optional[UUID] = None
    target_entity_name: Optional[str] = None
    
    @classmethod
    def from_engine(cls, modifier):
        """Create a snapshot from an engine modifier object"""
        return cls(
            uuid=modifier.uuid,
            name=modifier.name,
            source_entity_uuid=modifier.source_entity_uuid,
            source_entity_name=modifier.source_entity_name,
            target_entity_uuid=modifier.target_entity_uuid,
            target_entity_name=modifier.target_entity_name
        )

class NumericalModifierSnapshot(ModifierSnapshot):
    """Snapshot of a numerical modifier"""
    value: int
    normalized_value: int
    
    @classmethod
    def from_engine(cls, modifier):
        """Create a snapshot from an engine NumericalModifier"""
        base = super().from_engine(modifier)
        return cls(
            **base.model_dump(),
            value=modifier.value,
            normalized_value=modifier.normalized_value if hasattr(modifier, 'normalized_value') else modifier.value
        )

class AdvantageModifierSnapshot(ModifierSnapshot):
    """Snapshot of an advantage modifier"""
    value: AdvantageStatus
    numerical_value: int
    
    @classmethod
    def from_engine(cls, modifier):
        """Create a snapshot from an engine AdvantageModifier"""
        base = super().from_engine(modifier)
        return cls(
            **base.model_dump(),
            value=modifier.value,
            numerical_value=modifier.numerical_value
        )

class CriticalModifierSnapshot(ModifierSnapshot):
    """Snapshot of a critical modifier"""
    value: CriticalStatus
    
    @classmethod
    def from_engine(cls, modifier):
        """Create a snapshot from an engine CriticalModifier"""
        base = super().from_engine(modifier)
        return cls(
            **base.model_dump(),
            value=modifier.value
        )

class AutoHitModifierSnapshot(ModifierSnapshot):
    """Snapshot of an auto-hit modifier"""
    value: AutoHitStatus
    
    @classmethod
    def from_engine(cls, modifier):
        """Create a snapshot from an engine AutoHitModifier"""
        base = super().from_engine(modifier)
        return cls(
            **base.model_dump(),
            value=modifier.value
        )

class ResistanceModifierSnapshot(ModifierSnapshot):
    """Snapshot of a resistance modifier"""
    value: ResistanceStatus
    damage_type: DamageType
    numerical_value: int
    
    @classmethod
    def from_engine(cls, modifier):
        """Create a snapshot from an engine ResistanceModifier"""
        base = super().from_engine(modifier)
        return cls(
            **base.model_dump(),
            value=modifier.value,
            damage_type=modifier.damage_type,
            numerical_value=modifier.numerical_value
        )

class SizeModifierSnapshot(ModifierSnapshot):
    """Snapshot of a size modifier"""
    value: Size
    
    @classmethod
    def from_engine(cls, modifier):
        """Create a snapshot from an engine SizeModifier"""
        base = super().from_engine(modifier)
        return cls(
            **base.model_dump(),
            value=modifier.value
        )