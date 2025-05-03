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
        # For a context value, we need to capture the contextual modifiers with their current resolved values
        # This is a simplified version that won't include runtime-evaluated values
        is_outgoing = contextual_value.is_outgoing_modifier
        
        # We'll only take the UUIDs of contextual modifiers since their current values would depend on context
        value_modifiers = []
        min_constraints = []
        max_constraints = []
        advantage_modifiers = []
        critical_modifiers = []
        auto_hit_modifiers = []
        size_modifiers = []
        resistance_modifiers = []
        
        # For a full implementation, we would evaluate each contextual modifier with the current context
        
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