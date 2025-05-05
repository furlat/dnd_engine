from uuid import UUID
from typing import Optional, Dict, Any
from dnd.core.modifiers import NumericalModifier, ContextualNumericalModifier
from dnd.blocks.equipment import Equipment, WeaponProperty, Weapon
from dnd.core.events import WeaponSlot
from dnd.entity import Entity

def dual_wielder_ac_bonus(source_uuid: UUID, target_uuid: Optional[UUID], context: Optional[Dict[str, Any]]) -> Optional[NumericalModifier]:
    """
    Provides a +1 bonus to AC when wielding a melee weapon in each hand.
    
    Args:
        source_uuid (UUID): The UUID of the source entity
        target_uuid (Optional[UUID]): The UUID of the target entity
        context (Optional[Dict[str, Any]]): Additional context information
        
    Returns:
        Optional[NumericalModifier]: A +1 AC bonus if dual wielding melee weapons, None otherwise
    """
    # Get the source entity (the character with the dual wielder feature)
    source_entity = Entity.get(source_uuid)
    if not isinstance(source_entity, Entity):
        return None
        
    # Check both weapon slots
    main_hand = source_entity.equipment.weapon_main_hand
    off_hand = source_entity.equipment.weapon_off_hand
    
    # Both slots must have weapons (not shields)
    if not (isinstance(main_hand, Weapon) and isinstance(off_hand, Weapon)):
        return None
        
    # Both weapons must be melee (not have the RANGED property)
    if (WeaponProperty.RANGED in main_hand.properties or 
        WeaponProperty.RANGED in off_hand.properties):
        return None
    
    # If we get here, we're dual wielding melee weapons
    return NumericalModifier.create(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        name="Dual Wielder AC Bonus",
        value=1
    )

def create_dual_wielder_ac_modifier(source_uuid: UUID, target_uuid: UUID) -> ContextualNumericalModifier:
    """
    Creates a contextual modifier that provides +1 AC when dual wielding.
    
    Args:
        source_uuid (UUID): The UUID of the source entity
        target_uuid (UUID): The UUID of the target entity
        
    Returns:
        ContextualNumericalModifier: The dual wielder AC bonus modifier
    """
    return ContextualNumericalModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        name="Dual Wielder",
        callable=dual_wielder_ac_bonus
    ) 