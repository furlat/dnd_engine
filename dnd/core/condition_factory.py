from enum import Enum
from typing import Type, Dict, Optional
from uuid import UUID

from dnd.core.base_conditions import BaseCondition, Duration, DurationType
from dnd.conditions import (
    Blinded, Charmed, Dashing, Deafened, Dodging, Frightened,
    Grappled, Incapacitated, Invisible, Paralyzed, Poisoned,
    Prone, Restrained, Stunned, Unconscious
)

class ConditionType(str, Enum):
    BLINDED = "BLINDED"
    CHARMED = "CHARMED"
    DASHING = "DASHING"
    DEAFENED = "DEAFENED"
    DODGING = "DODGING"
    FRIGHTENED = "FRIGHTENED"
    GRAPPLED = "GRAPPLED"
    INCAPACITATED = "INCAPACITATED"
    INVISIBLE = "INVISIBLE"
    PARALYZED = "PARALYZED"
    POISONED = "POISONED"
    PRONE = "PRONE"
    RESTRAINED = "RESTRAINED"
    STUNNED = "STUNNED"
    UNCONSCIOUS = "UNCONSCIOUS"

# Map enum values to condition classes
CONDITION_MAP: Dict[ConditionType, Type[BaseCondition]] = {
    ConditionType.BLINDED: Blinded,
    ConditionType.CHARMED: Charmed,
    ConditionType.DASHING: Dashing,
    ConditionType.DEAFENED: Deafened,
    ConditionType.DODGING: Dodging,
    ConditionType.FRIGHTENED: Frightened,
    ConditionType.GRAPPLED: Grappled,
    ConditionType.INCAPACITATED: Incapacitated,
    ConditionType.INVISIBLE: Invisible,
    ConditionType.PARALYZED: Paralyzed,
    ConditionType.POISONED: Poisoned,
    ConditionType.PRONE: Prone,
    ConditionType.RESTRAINED: Restrained,
    ConditionType.STUNNED: Stunned,
    ConditionType.UNCONSCIOUS: Unconscious,
}

def create_condition(
    condition_type: ConditionType,
    source_entity_uuid: UUID,
    target_entity_uuid: UUID,
    duration_type: DurationType = DurationType.PERMANENT,
    duration_rounds: Optional[int] = None
) -> BaseCondition:
    """
    Factory function to create a condition of the specified type.
    
    Args:
        condition_type: The type of condition to create
        source_entity_uuid: UUID of the entity causing the condition
        target_entity_uuid: UUID of the entity receiving the condition
        duration_type: Type of duration (PERMANENT, ROUNDS, etc.)
        duration_rounds: Number of rounds if duration_type is ROUNDS
        
    Returns:
        BaseCondition: The created condition instance
    """
    condition_class = CONDITION_MAP[condition_type]
    
    # Create the condition
    condition = condition_class(
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=target_entity_uuid
    )
    
    # Set up duration
    if duration_type == DurationType.ROUNDS and duration_rounds is not None:
        condition.duration.duration_type = DurationType.ROUNDS
        condition.duration.duration = duration_rounds
    else:
        condition.duration.duration_type = duration_type
        condition.duration.duration = None
        
    return condition 