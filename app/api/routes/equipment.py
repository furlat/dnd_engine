from fastapi import APIRouter, HTTPException, Query
from uuid import UUID
from typing import List, Union, Optional

from dnd.blocks.equipment import Equipment, Weapon, Shield, Armor, BaseBlock
from app.models.equipment import (
    WeaponSnapshot,
    ArmorSnapshot,
    ShieldSnapshot,
    EquipmentSnapshot
)

router = APIRouter(prefix="/equipment", tags=["equipment"])

@router.get("/", response_model=List[Union[WeaponSnapshot, ArmorSnapshot, ShieldSnapshot]])
async def list_equipment(source_entity_uuid: Optional[UUID] = Query(None, description="Filter equipment by source entity UUID")):
    """
    Get a list of all available equipment with their details.
    Returns a list of equipment snapshots, properly typed based on the equipment type.
    
    Args:
        source_entity_uuid: Optional UUID to filter equipment by source entity
    """
    equipment_list = []
    for item in BaseBlock._registry.values():
        if isinstance(item, (Weapon, Armor, Shield)):
            # Skip if source_entity_uuid filter is provided and doesn't match
            if source_entity_uuid and item.source_entity_uuid != source_entity_uuid:
                continue
                
            if isinstance(item, Weapon):
                equipment_list.append(WeaponSnapshot.from_engine(item))
            elif isinstance(item, Armor):
                equipment_list.append(ArmorSnapshot.from_engine(item))
            elif isinstance(item, Shield):
                equipment_list.append(ShieldSnapshot.from_engine(item))
    return equipment_list

@router.get("/{equipment_uuid}", response_model=Union[WeaponSnapshot, ArmorSnapshot, ShieldSnapshot])
async def get_equipment(equipment_uuid: UUID):
    """
    Get detailed information about a specific piece of equipment.
    Returns a properly typed snapshot based on the equipment type.
    """
    equipment = BaseBlock.get(equipment_uuid)
    if not equipment:
        raise HTTPException(status_code=404, detail="Equipment not found")
    
    if isinstance(equipment, Weapon):
        return WeaponSnapshot.from_engine(equipment)
    elif isinstance(equipment, Armor):
        return ArmorSnapshot.from_engine(equipment)
    elif isinstance(equipment, Shield):
        return ShieldSnapshot.from_engine(equipment)
    else:
        raise HTTPException(status_code=400, detail="Invalid equipment type") 