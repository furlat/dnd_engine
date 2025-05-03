from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Path
from inspect import getdoc

from dnd.core.values import ModifiableValue, StaticValue, ContextualValue
from dnd.core.modifiers import (
    NumericalModifier, AdvantageModifier, CriticalModifier, AutoHitModifier,
    SizeModifier, DamageTypeModifier, ResistanceModifier,
    ContextualNumericalModifier, ContextualAdvantageModifier, ContextualCriticalModifier,
    ContextualAutoHitModifier, ContextualSizeModifier, ContextualDamageTypeModifier,
    ContextualResistanceModifier
)

from app.models.values import (
    ModifiableValueResponse, ModifiableValueListEntry,
    StaticValueResponse, ContextualValueResponse,
    NumericalModifierResponse, AdvantageModifierResponse, CriticalModifierResponse,
    AutoHitModifierResponse, SizeModifierResponse, DamageTypeModifierResponse,
    ResistanceModifierResponse, ContextualNumericalModifierResponse,
    ContextualAdvantageModifierResponse, ContextualCriticalModifierResponse,
    ContextualAutoHitModifierResponse, ContextualSizeModifierResponse,
    ContextualDamageTypeModifierResponse, ContextualResistanceModifierResponse,
    ModifiableValueComponentSummary
)

router = APIRouter()

def convert_static_value(value: StaticValue) -> StaticValueResponse:
    """Convert a StaticValue to a StaticValueResponse."""
    return StaticValueResponse(
        uuid=value.uuid,
        name=value.name,
        source_entity_uuid=value.source_entity_uuid,
        source_entity_name=value.source_entity_name,
        target_entity_uuid=value.target_entity_uuid,
        target_entity_name=value.target_entity_name,
        is_outgoing_modifier=value.is_outgoing_modifier,
        score=value.score,
        normalized_score=value.normalized_score,
        min=value.min,
        max=value.max,
        advantage=value.advantage,
        critical=value.critical,
        auto_hit=value.auto_hit,
        value_modifiers={str(k): NumericalModifierResponse(**v.dict()) for k, v in value.value_modifiers.items()},
        min_constraints={str(k): NumericalModifierResponse(**v.dict()) for k, v in value.min_constraints.items()},
        max_constraints={str(k): NumericalModifierResponse(**v.dict()) for k, v in value.max_constraints.items()},
        advantage_modifiers={str(k): AdvantageModifierResponse(**v.dict()) for k, v in value.advantage_modifiers.items()},
        critical_modifiers={str(k): CriticalModifierResponse(**v.dict()) for k, v in value.critical_modifiers.items()},
        auto_hit_modifiers={str(k): AutoHitModifierResponse(**v.dict()) for k, v in value.auto_hit_modifiers.items()},
        size_modifiers={str(k): SizeModifierResponse(**v.dict()) for k, v in value.size_modifiers.items()},
        damage_type_modifiers={str(k): DamageTypeModifierResponse(**v.dict()) for k, v in value.damage_type_modifiers.items()},
        resistance_modifiers={str(k): ResistanceModifierResponse(**v.dict()) for k, v in value.resistance_modifiers.items()},
    )

def convert_contextual_value(value: ContextualValue) -> ContextualValueResponse:
    """Convert a ContextualValue to a ContextualValueResponse."""
    return ContextualValueResponse(
        uuid=value.uuid,
        name=value.name,
        source_entity_uuid=value.source_entity_uuid,
        source_entity_name=value.source_entity_name,
        target_entity_uuid=value.target_entity_uuid,
        target_entity_name=value.target_entity_name,
        is_outgoing_modifier=value.is_outgoing_modifier,
        context=value.context,
        score=value.score,
        normalized_score=value.normalized_score,
        min=value.min,
        max=value.max,
        advantage=value.advantage,
        critical=value.critical,
        auto_hit=value.auto_hit,
        value_modifiers={
            str(k): ContextualNumericalModifierResponse(
                **v.dict(),
                callable_description=getdoc(v.callable) or "No description available"
            ) for k, v in value.value_modifiers.items()
        },
        min_constraints={
            str(k): ContextualNumericalModifierResponse(
                **v.dict(),
                callable_description=getdoc(v.callable) or "No description available"
            ) for k, v in value.min_constraints.items()
        },
        max_constraints={
            str(k): ContextualNumericalModifierResponse(
                **v.dict(),
                callable_description=getdoc(v.callable) or "No description available"
            ) for k, v in value.max_constraints.items()
        },
        advantage_modifiers={
            str(k): ContextualAdvantageModifierResponse(
                **v.dict(),
                callable_description=getdoc(v.callable) or "No description available"
            ) for k, v in value.advantage_modifiers.items()
        },
        critical_modifiers={
            str(k): ContextualCriticalModifierResponse(
                **v.dict(),
                callable_description=getdoc(v.callable) or "No description available"
            ) for k, v in value.critical_modifiers.items()
        },
        auto_hit_modifiers={
            str(k): ContextualAutoHitModifierResponse(
                **v.dict(),
                callable_description=getdoc(v.callable) or "No description available"
            ) for k, v in value.auto_hit_modifiers.items()
        },
        size_modifiers={
            str(k): ContextualSizeModifierResponse(
                **v.dict(),
                callable_description=getdoc(v.callable) or "No description available"
            ) for k, v in value.size_modifiers.items()
        },
        damage_type_modifiers={
            str(k): ContextualDamageTypeModifierResponse(
                **v.dict(),
                callable_description=getdoc(v.callable) or "No description available"
            ) for k, v in value.damage_type_modifiers.items()
        },
        resistance_modifiers={
            str(k): ContextualResistanceModifierResponse(
                **v.dict(),
                callable_description=getdoc(v.callable) or "No description available"
            ) for k, v in value.resistance_modifiers.items()
        },
    )

def convert_modifiable_value(value: ModifiableValue) -> ModifiableValueResponse:
    """Convert a ModifiableValue to a ModifiableValueResponse."""
    # Create component summaries
    components = {
        "self_static": ModifiableValueComponentSummary(
            type="static",
            name=value.self_static.name,
            uuid=value.self_static.uuid,
            score=value.self_static.score,
            normalized_score=value.self_static.normalized_score
        ),
        "to_target_static": ModifiableValueComponentSummary(
            type="static",
            name=value.to_target_static.name,
            uuid=value.to_target_static.uuid,
            score=value.to_target_static.score,
            normalized_score=value.to_target_static.normalized_score
        ),
        "self_contextual": ModifiableValueComponentSummary(
            type="contextual",
            name=value.self_contextual.name,
            uuid=value.self_contextual.uuid,
            score=value.self_contextual.score,
            normalized_score=value.self_contextual.normalized_score
        ),
        "to_target_contextual": ModifiableValueComponentSummary(
            type="contextual",
            name=value.to_target_contextual.name,
            uuid=value.to_target_contextual.uuid,
            score=value.to_target_contextual.score,
            normalized_score=value.to_target_contextual.normalized_score
        ),
    }
    
    # Add from_target components if present
    if value.from_target_static:
        components["from_target_static"] = ModifiableValueComponentSummary(
            type="static",
            name=value.from_target_static.name,
            uuid=value.from_target_static.uuid,
            score=value.from_target_static.score,
            normalized_score=value.from_target_static.normalized_score
        )
        
    if value.from_target_contextual:
        components["from_target_contextual"] = ModifiableValueComponentSummary(
            type="contextual",
            name=value.from_target_contextual.name,
            uuid=value.from_target_contextual.uuid,
            score=value.from_target_contextual.score,
            normalized_score=value.from_target_contextual.normalized_score
        )
    
    # Prepare the response
    response = ModifiableValueResponse(
        uuid=value.uuid,
        name=value.name,
        source_entity_uuid=value.source_entity_uuid,
        source_entity_name=value.source_entity_name,
        target_entity_uuid=value.target_entity_uuid,
        target_entity_name=value.target_entity_name,
        context=value.context,
        score=value.score,
        normalized_score=value.normalized_score,
        advantage=value.advantage,
        critical=value.critical,
        auto_hit=value.auto_hit,
        components=components,
        self_static=convert_static_value(value.self_static),
        to_target_static=convert_static_value(value.to_target_static),
        self_contextual=convert_contextual_value(value.self_contextual),
        to_target_contextual=convert_contextual_value(value.to_target_contextual),
        from_target_static=convert_static_value(value.from_target_static) if value.from_target_static else None,
        from_target_contextual=convert_contextual_value(value.from_target_contextual) if value.from_target_contextual else None,
    )
    
    return response

@router.get("/values", response_model=List[ModifiableValueListEntry])
async def list_modifiable_values(entity_uuid: Optional[UUID] = Query(None)):
    """
    List all ModifiableValue instances, optionally filtered by entity UUID.
    """
    values = []
    
    # Scan registry for ModifiableValue objects
    for obj_id, obj in ModifiableValue._registry.items():
        if isinstance(obj, ModifiableValue):
            # Filter by entity if specified
            if entity_uuid is None or obj.source_entity_uuid == entity_uuid:
                values.append(ModifiableValueListEntry(
                    uuid=obj.uuid,
                    name=obj.name,
                    source_entity_uuid=obj.source_entity_uuid,
                    source_entity_name=obj.source_entity_name,
                    score=obj.score,
                    normalized_score=obj.normalized_score
                ))
    
    return values

@router.get("/values/{value_uuid}", response_model=ModifiableValueResponse)
async def get_modifiable_value(value_uuid: UUID = Path(...)):
    """
    Get detailed information about a specific ModifiableValue.
    """
    value = ModifiableValue.get(value_uuid)
    if not value:
        raise HTTPException(status_code=404, detail="ModifiableValue not found")
    
    return convert_modifiable_value(value)