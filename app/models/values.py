from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from uuid import UUID

# Import the enums from the engine to ensure consistency
from dnd.core.modifiers import (
    AdvantageStatus, 
    CriticalStatus, 
    AutoHitStatus, 
    Size, 
    DamageType, 
    ResistanceStatus
)

# Basic modifier models
class ModifierBase(BaseModel):
    uuid: UUID
    name: Optional[str]
    source_entity_uuid: UUID
    source_entity_name: Optional[str]
    target_entity_uuid: Optional[UUID]
    target_entity_name: Optional[str]

class NumericalModifierResponse(ModifierBase):
    value: int
    normalized_value: int

class AdvantageModifierResponse(ModifierBase):
    value: AdvantageStatus
    numerical_value: int

class CriticalModifierResponse(ModifierBase):
    value: CriticalStatus

class AutoHitModifierResponse(ModifierBase):
    value: AutoHitStatus

class SizeModifierResponse(ModifierBase):
    value: Size

class DamageTypeModifierResponse(ModifierBase):
    value: DamageType

class ResistanceModifierResponse(ModifierBase):
    value: ResistanceStatus
    damage_type: DamageType
    numerical_value: int

# Contextual modifier models
class ContextualModifierBase(ModifierBase):
    callable_description: str = Field(description="Human-readable description of what the callable does")

class ContextualNumericalModifierResponse(ContextualModifierBase):
    type: str = "numerical"

class ContextualAdvantageModifierResponse(ContextualModifierBase):
    type: str = "advantage"

class ContextualCriticalModifierResponse(ContextualModifierBase):
    type: str = "critical"

class ContextualAutoHitModifierResponse(ContextualModifierBase):
    type: str = "auto_hit"

class ContextualSizeModifierResponse(ContextualModifierBase):
    type: str = "size"

class ContextualDamageTypeModifierResponse(ContextualModifierBase):
    type: str = "damage_type"

class ContextualResistanceModifierResponse(ContextualModifierBase):
    type: str = "resistance"

# ModifiableValue component models
class StaticValueResponse(BaseModel):
    uuid: UUID
    name: str
    source_entity_uuid: UUID
    source_entity_name: Optional[str]
    target_entity_uuid: Optional[UUID]
    target_entity_name: Optional[str]
    is_outgoing_modifier: bool
    
    # Computed properties
    score: int
    normalized_score: int
    min: Optional[int]
    max: Optional[int]
    advantage: AdvantageStatus
    critical: CriticalStatus
    auto_hit: AutoHitStatus
    
    # Modifiers
    value_modifiers: Dict[str, NumericalModifierResponse]
    min_constraints: Dict[str, NumericalModifierResponse]
    max_constraints: Dict[str, NumericalModifierResponse]
    advantage_modifiers: Dict[str, AdvantageModifierResponse]
    critical_modifiers: Dict[str, CriticalModifierResponse]
    auto_hit_modifiers: Dict[str, AutoHitModifierResponse]
    size_modifiers: Dict[str, SizeModifierResponse]
    damage_type_modifiers: Dict[str, DamageTypeModifierResponse]
    resistance_modifiers: Dict[str, ResistanceModifierResponse]

class ContextualValueResponse(BaseModel):
    uuid: UUID
    name: str
    source_entity_uuid: UUID
    source_entity_name: Optional[str]
    target_entity_uuid: Optional[UUID]
    target_entity_name: Optional[str]
    is_outgoing_modifier: bool
    context: Optional[Dict[str, Any]]
    
    # Computed properties
    score: int
    normalized_score: int
    min: Optional[int]
    max: Optional[int]
    advantage: AdvantageStatus
    critical: CriticalStatus
    auto_hit: AutoHitStatus
    
    # Modifiers
    value_modifiers: Dict[str, ContextualNumericalModifierResponse]
    min_constraints: Dict[str, ContextualNumericalModifierResponse]
    max_constraints: Dict[str, ContextualNumericalModifierResponse]
    advantage_modifiers: Dict[str, ContextualAdvantageModifierResponse]
    critical_modifiers: Dict[str, ContextualCriticalModifierResponse]
    auto_hit_modifiers: Dict[str, ContextualAutoHitModifierResponse]
    size_modifiers: Dict[str, ContextualSizeModifierResponse]
    damage_type_modifiers: Dict[str, ContextualDamageTypeModifierResponse]
    resistance_modifiers: Dict[str, ContextualResistanceModifierResponse]

class ModifiableValueComponentSummary(BaseModel):
    type: str
    name: str
    uuid: UUID
    score: int
    normalized_score: int

class ModifiableValueResponse(BaseModel):
    uuid: UUID
    name: str
    source_entity_uuid: UUID
    source_entity_name: Optional[str]
    target_entity_uuid: Optional[UUID]
    target_entity_name: Optional[str]
    context: Optional[Dict[str, Any]]
    
    # Computed attributes
    score: int
    normalized_score: int
    advantage: AdvantageStatus
    critical: CriticalStatus
    auto_hit: AutoHitStatus
    
    # Component summaries (for overview)
    components: Dict[str, ModifiableValueComponentSummary]
    
    # Full components (detailed view)
    self_static: StaticValueResponse
    to_target_static: StaticValueResponse
    self_contextual: ContextualValueResponse
    to_target_contextual: ContextualValueResponse
    from_target_static: Optional[StaticValueResponse]
    from_target_contextual: Optional[ContextualValueResponse]

class ModifiableValueListEntry(BaseModel):
    uuid: UUID
    name: str
    source_entity_uuid: UUID
    source_entity_name: Optional[str]
    score: int
    normalized_score: int