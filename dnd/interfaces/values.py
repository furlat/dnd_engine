# dnd/interfaces/values.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Any
from uuid import UUID

from dnd.core.modifiers import AdvantageStatus, CriticalStatus, AutoHitStatus, DamageType, ResistanceStatus

from dnd.interfaces.channels import ModifierChannelSnapshot
from dnd.interfaces.modifiers import NumericalModifierSnapshot

class ModifiableValueSnapshot(BaseModel):
    """Interface model for a ModifiableValue"""
    uuid: UUID
    name: str
    source_entity_uuid: UUID
    source_entity_name: Optional[str] = None
    target_entity_uuid: Optional[UUID] = None
    target_entity_name: Optional[str] = None
    
    # Computed values for frontend display
    score: int
    normalized_score: int
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    advantage: AdvantageStatus
    critical: CriticalStatus
    auto_hit: AutoHitStatus
    
    # Resistance summary for quick reference
    resistances: Dict[DamageType, ResistanceStatus] = Field(default_factory=dict)
    
    # Base modifier for quick reference
    base_modifier: Optional[NumericalModifierSnapshot] = None
    
    # All modifier channels
    channels: List[ModifierChannelSnapshot] = Field(default_factory=list)
    
    @classmethod
    def from_engine(cls, modifiable_value):
        """Create a snapshot from an engine ModifiableValue object"""
        # Extract the base modifier if it exists
        base_modifier = None
        if hasattr(modifiable_value, 'get_base_modifier'):
            base_mod = modifiable_value.get_base_modifier()
            if base_mod:
                base_modifier = NumericalModifierSnapshot.from_engine(base_mod)
        
        # Create channel snapshots
        channels = []
        
        # Self Static channel
        if hasattr(modifiable_value, 'self_static'):
            channels.append(ModifierChannelSnapshot.from_engine_static(
                modifiable_value.self_static, "self_static"))
        
        # To Target Static channel
        if hasattr(modifiable_value, 'to_target_static'):
            channels.append(ModifierChannelSnapshot.from_engine_static(
                modifiable_value.to_target_static, "to_target_static"))
        
        # Self Contextual channel
        if hasattr(modifiable_value, 'self_contextual'):
            channels.append(ModifierChannelSnapshot.from_engine_contextual(
                modifiable_value.self_contextual, "self_contextual"))
        
        # To Target Contextual channel
        if hasattr(modifiable_value, 'to_target_contextual'):
            channels.append(ModifierChannelSnapshot.from_engine_contextual(
                modifiable_value.to_target_contextual, "to_target_contextual"))
        
        # From Target Static channel (if present)
        if hasattr(modifiable_value, 'from_target_static') and modifiable_value.from_target_static:
            channels.append(ModifierChannelSnapshot.from_engine_static(
                modifiable_value.from_target_static, "from_target_static"))
        
        # From Target Contextual channel (if present)
        if hasattr(modifiable_value, 'from_target_contextual') and modifiable_value.from_target_contextual:
            channels.append(ModifierChannelSnapshot.from_engine_contextual(
                modifiable_value.from_target_contextual, "from_target_contextual"))
        
        # Get basic properties directly
        uuid = modifiable_value.uuid
        name = modifiable_value.name
        source_entity_uuid = modifiable_value.source_entity_uuid
        source_entity_name = modifiable_value.source_entity_name
        target_entity_uuid = modifiable_value.target_entity_uuid
        target_entity_name = modifiable_value.target_entity_name
        
        # Get calculated properties directly
        score = modifiable_value.score
        normalized_score = modifiable_value.normalized_score
        min_value = modifiable_value.min
        max_value = modifiable_value.max
        advantage = modifiable_value.advantage
        critical = modifiable_value.critical
        auto_hit = modifiable_value.auto_hit
        
        # Get resistances directly
        resistances = {}
        if hasattr(modifiable_value, 'resistance'):
            resistances = modifiable_value.resistance
        
        return cls(
            uuid=uuid,
            name=name,
            source_entity_uuid=source_entity_uuid,
            source_entity_name=source_entity_name,
            target_entity_uuid=target_entity_uuid,
            target_entity_name=target_entity_name,
            score=score,
            normalized_score=normalized_score,
            min_value=min_value,
            max_value=max_value,
            advantage=advantage,
            critical=critical,
            auto_hit=auto_hit,
            resistances=resistances,
            base_modifier=base_modifier,
            channels=channels
        )