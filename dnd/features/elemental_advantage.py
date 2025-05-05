from uuid import UUID
from typing import Optional, Dict, Any
from dnd.core.modifiers import AdvantageModifier, ContextualAdvantageModifier, AdvantageStatus, DamageType
from dnd.blocks.equipment import Equipment, Weapon
from dnd.core.events import WeaponSlot
from dnd.entity import Entity

def elemental_advantage(source_uuid: UUID, target_uuid: Optional[UUID], context: Optional[Dict[str, Any]]) -> Optional[AdvantageModifier]:
    """
    Provides advantage on attack rolls when using a weapon with elemental damage.
    
    Args:
        source_uuid (UUID): The UUID of the source entity
        target_uuid (Optional[UUID]): The UUID of the target entity
        context (Optional[Dict[str, Any]]): Additional context information (unused)
        
    Returns:
        Optional[AdvantageModifier]: An advantage modifier if using a weapon with elemental damage, None otherwise
    """
    # Get the source entity (the character with the elemental weapon)
    source_entity = Entity.get(source_uuid)
    if not isinstance(source_entity, Entity):
        return None

    # Check both weapons for elemental damage
    weapons = [
        source_entity.equipment.weapon_main_hand,
        source_entity.equipment.weapon_off_hand
    ]

    # Check if it's a weapon with elemental damage
    for weapon in weapons:
        if not isinstance(weapon, Weapon):
            continue


        # Check for elemental damage types
        elemental_types = {
            DamageType.ACID,
            DamageType.COLD,
            DamageType.FIRE,
            DamageType.LIGHTNING,
            DamageType.POISON,
            DamageType.THUNDER
        }

        # Check main damage type and extra damage types
        has_elemental = (weapon.damage_type in elemental_types or
                        any(dtype in elemental_types for dtype in weapon.extra_damage_type))

        if has_elemental:
            # If we get here, the weapon has elemental damage
            return AdvantageModifier(
                source_entity_uuid=source_uuid,
                target_entity_uuid=target_uuid,
                name="Elemental Weapon Advantage",
                value=AdvantageStatus.ADVANTAGE
            )

    return None

def create_elemental_advantage_modifier(source_uuid: UUID, target_uuid: UUID) -> ContextualAdvantageModifier:
    """
    Creates a contextual modifier that provides advantage when using elemental weapons.
    
    Args:
        source_uuid (UUID): The UUID of the source entity
        target_uuid (UUID): The UUID of the target entity
        
    Returns:
        ContextualAdvantageModifier: The elemental advantage modifier
    """
    return ContextualAdvantageModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        name="Elemental Weapon",
        callable=elemental_advantage
    ) 