# dnd/interfaces/channels.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Any
from uuid import UUID

from dnd.interfaces.modifiers import (
    NumericalModifierSnapshot,
    AdvantageModifierSnapshot,
    CriticalModifierSnapshot,
    AutoHitModifierSnapshot,
    ResistanceModifierSnapshot,
    SizeModifierSnapshot
)

class ModifierChannelSnapshot(BaseModel):
    """Base model for modifier channels in the interface"""
    name: str
    is_outgoing: bool = False
    is_contextual: bool = False
    
    value_modifiers: List[NumericalModifierSnapshot] = Field(default_factory=list)
    min_constraints: List[NumericalModifierSnapshot] = Field(default_factory=list)
    max_constraints: List[NumericalModifierSnapshot] = Field(default_factory=list)
    advantage_modifiers: List[AdvantageModifierSnapshot] = Field(default_factory=list)
    critical_modifiers: List[CriticalModifierSnapshot] = Field(default_factory=list)
    auto_hit_modifiers: List[AutoHitModifierSnapshot] = Field(default_factory=list)
    size_modifiers: List[SizeModifierSnapshot] = Field(default_factory=list)
    resistance_modifiers: List[ResistanceModifierSnapshot] = Field(default_factory=list)
    
    # Computed data for frontend display
    score: int = 0
    normalized_score: int = 0
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    
    @classmethod
    def from_engine_static(cls, static_value, channel_name):
        """Create a snapshot from an engine StaticValue object"""
        is_outgoing = static_value.is_outgoing_modifier
        
        # Convert all modifiers
        value_modifiers = [NumericalModifierSnapshot.from_engine(mod) 
                          for mod in static_value.value_modifiers.values()]
        
        min_constraints = [NumericalModifierSnapshot.from_engine(mod) 
                          for mod in static_value.min_constraints.values()]
        
        max_constraints = [NumericalModifierSnapshot.from_engine(mod) 
                          for mod in static_value.max_constraints.values()]
        
        advantage_modifiers = [AdvantageModifierSnapshot.from_engine(mod) 
                              for mod in static_value.advantage_modifiers.values()]
        
        critical_modifiers = [CriticalModifierSnapshot.from_engine(mod) 
                             for mod in static_value.critical_modifiers.values()]
        
        auto_hit_modifiers = [AutoHitModifierSnapshot.from_engine(mod) 
                             for mod in static_value.auto_hit_modifiers.values()]
        
        size_modifiers = [SizeModifierSnapshot.from_engine(mod) 
                         for mod in static_value.size_modifiers.values()]
        
        resistance_modifiers = [ResistanceModifierSnapshot.from_engine(mod) 
                               for mod in static_value.resistance_modifiers.values()]
        
        return cls(
            name=channel_name,
            is_outgoing=is_outgoing,
            is_contextual=False,
            value_modifiers=value_modifiers,
            min_constraints=min_constraints,
            max_constraints=max_constraints,
            advantage_modifiers=advantage_modifiers,
            critical_modifiers=critical_modifiers,
            auto_hit_modifiers=auto_hit_modifiers,
            size_modifiers=size_modifiers,
            resistance_modifiers=resistance_modifiers,
            score=static_value.score,
            normalized_score=static_value.normalized_score,
            min_value=static_value.min,
            max_value=static_value.max
        )
    
    @classmethod
    def from_engine_contextual(cls, contextual_value, channel_name):
        """Create a snapshot from an engine ContextualValue object"""
        is_outgoing = contextual_value.is_outgoing_modifier
        
        # Evaluate contextual modifiers with current context
        value_modifiers = []
        for modifier in contextual_value.value_modifiers.values():
            result = modifier.callable(
                contextual_value.source_entity_uuid,
                contextual_value.target_entity_uuid,
                contextual_value.context
            )
            if result is not None:
                value_modifiers.append(NumericalModifierSnapshot.from_engine(result))
        
        # Evaluate contextual constraints
        min_constraints = []
        for constraint in contextual_value.min_constraints.values():
            result = constraint.callable(
                contextual_value.source_entity_uuid,
                contextual_value.target_entity_uuid,
                contextual_value.context
            )
            if result is not None:
                min_constraints.append(NumericalModifierSnapshot.from_engine(result))
        
        max_constraints = []
        for constraint in contextual_value.max_constraints.values():
            result = constraint.callable(
                contextual_value.source_entity_uuid,
                contextual_value.target_entity_uuid,
                contextual_value.context
            )
            if result is not None:
                max_constraints.append(NumericalModifierSnapshot.from_engine(result))
        
        # Evaluate other contextual modifiers
        advantage_modifiers = []
        for modifier in contextual_value.advantage_modifiers.values():
            result = modifier.callable(
                contextual_value.source_entity_uuid,
                contextual_value.target_entity_uuid,
                contextual_value.context
            )
            if result is not None:
                advantage_modifiers.append(AdvantageModifierSnapshot.from_engine(result))
        
        critical_modifiers = []
        for modifier in contextual_value.critical_modifiers.values():
            result = modifier.callable(
                contextual_value.source_entity_uuid,
                contextual_value.target_entity_uuid,
                contextual_value.context
            )
            if result is not None:
                critical_modifiers.append(CriticalModifierSnapshot.from_engine(result))
        
        auto_hit_modifiers = []
        for modifier in contextual_value.auto_hit_modifiers.values():
            result = modifier.callable(
                contextual_value.source_entity_uuid,
                contextual_value.target_entity_uuid,
                contextual_value.context
            )
            if result is not None:
                auto_hit_modifiers.append(AutoHitModifierSnapshot.from_engine(result))
        
        size_modifiers = []
        for modifier in contextual_value.size_modifiers.values():
            result = modifier.callable(
                contextual_value.source_entity_uuid,
                contextual_value.target_entity_uuid,
                contextual_value.context
            )
            if result is not None:
                size_modifiers.append(SizeModifierSnapshot.from_engine(result))
        
        resistance_modifiers = []
        for modifier in contextual_value.resistance_modifiers.values():
            result = modifier.callable(
                contextual_value.source_entity_uuid,
                contextual_value.target_entity_uuid,
                contextual_value.context
            )
            if result is not None:
                resistance_modifiers.append(ResistanceModifierSnapshot.from_engine(result))
        
        return cls(
            name=channel_name,
            is_outgoing=is_outgoing,
            is_contextual=True,
            value_modifiers=value_modifiers,
            min_constraints=min_constraints,
            max_constraints=max_constraints,
            advantage_modifiers=advantage_modifiers,
            critical_modifiers=critical_modifiers,
            auto_hit_modifiers=auto_hit_modifiers,
            size_modifiers=size_modifiers,
            resistance_modifiers=resistance_modifiers,
            score=contextual_value.score,
            normalized_score=contextual_value.normalized_score,
            min_value=contextual_value.min,
            max_value=contextual_value.max
        )