from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict, Optional, Union, Literal
from uuid import UUID
from enum import Enum
from pydantic import BaseModel

# Import entity and models
from dnd.entity import Entity
from dnd.interfaces.entitiy import EntitySnapshot, ConditionSnapshot
from dnd.interfaces.health import HealthSnapshot
from dnd.interfaces.abilities import AbilityScoresSnapshot
from dnd.interfaces.skills import SkillSetSnapshot
from dnd.interfaces.equipment import EquipmentSnapshot
from dnd.interfaces.saving_throws import SavingThrowSetSnapshot
from dnd.interfaces.values import ModifiableValueSnapshot
from dnd.core.events import WeaponSlot
from dnd.blocks.equipment import Equipment, BaseBlock, Armor, Weapon, Shield, BodyPart, RingSlot
from dnd.core.base_conditions import DurationType
from dnd.core.condition_factory import ConditionType, create_condition

# Import dependencies
from app.api.deps import get_entity

# Create router
router = APIRouter(
    prefix="/entities",
    tags=["entities"],
    responses={404: {"description": "Entity not found"}},
)

# Define available subblocks for query parameter validation
class SubblockName(str, Enum):
    HEALTH = "health"
    ABILITY_SCORES = "ability_scores"
    SKILL_SET = "skill_set"
    EQUIPMENT = "equipment" 
    SAVING_THROWS = "saving_throws"
    PROFICIENCY_BONUS = "proficiency_bonus"

# Basic entity list model
class EntityListItem(BaseModel):
    uuid: UUID
    name: str

class SlotType(str, Enum):
    MAIN_HAND = "MAIN_HAND"
    OFF_HAND = "OFF_HAND"
    HEAD = "Head"
    BODY = "Body"
    HANDS = "Hands"
    LEGS = "Legs"
    FEET = "Feet"
    AMULET = "Amulet"
    RING_LEFT = "LEFT"
    RING_RIGHT = "RIGHT"
    CLOAK = "Cloak"

class EquipRequest(BaseModel):
    equipment_uuid: UUID
    slot: Optional[SlotType] = None  # Optional since some equipment auto-determines slot

@router.get("/", response_model=List[EntityListItem])
async def list_entities():
    """List all entities in the registry"""
    # Get all entities from the registry
    entities = [entity for entity in Entity._registry.values() if isinstance(entity, Entity)]
    
    # Convert to a list of basic info
    return [EntityListItem(uuid=entity.uuid, name=entity.name) for entity in entities]

@router.get("/{entity_uuid}", response_model=EntitySnapshot)
async def get_entity_by_uuid(
    entity: Entity = Depends(get_entity), 
    include_skill_calculations: bool = False,
    include_attack_calculations: bool = False,
    include_ac_calculation: bool = False,
    include_saving_throw_calculations: bool = False
):
    """Get an entity by UUID and convert to interface model"""
    # Convert the entity to its interface counterpart and return directly
    return EntitySnapshot.from_engine(
        entity, 
        include_skill_calculations=include_skill_calculations,
        include_attack_calculations=include_attack_calculations,
        include_ac_calculation=include_ac_calculation,
        include_saving_throw_calculations=include_saving_throw_calculations
    )

@router.get("/{entity_uuid}/health", response_model=HealthSnapshot)
async def get_entity_health(entity: Entity = Depends(get_entity)):
    """Get entity health snapshot"""
    return HealthSnapshot.from_engine(entity.health, entity)

@router.get("/{entity_uuid}/ability_scores", response_model=AbilityScoresSnapshot)
async def get_entity_ability_scores(entity: Entity = Depends(get_entity)):
    """Get entity ability scores snapshot"""
    return AbilityScoresSnapshot.from_engine(entity.ability_scores)

@router.get("/{entity_uuid}/skill_set", response_model=SkillSetSnapshot)
async def get_entity_skill_set(entity: Entity = Depends(get_entity)):
    """Get entity skill set snapshot"""
    return SkillSetSnapshot.from_engine(entity.skill_set, entity)

@router.get("/{entity_uuid}/equipment", response_model=EquipmentSnapshot)
async def get_entity_equipment(entity: Entity = Depends(get_entity)):
    """Get entity equipment snapshot"""
    return EquipmentSnapshot.from_engine(entity.equipment, entity=entity)

@router.get("/{entity_uuid}/saving_throws", response_model=SavingThrowSetSnapshot)
async def get_entity_saving_throws(entity: Entity = Depends(get_entity)):
    """Get entity saving throws snapshot"""
    return SavingThrowSetSnapshot.from_engine(entity.saving_throws, entity)

@router.get("/{entity_uuid}/proficiency_bonus", response_model=ModifiableValueSnapshot)
async def get_entity_proficiency_bonus(entity: Entity = Depends(get_entity)):
    """Get entity proficiency bonus snapshot"""
    return ModifiableValueSnapshot.from_engine(entity.proficiency_bonus)

@router.post("/{entity_uuid}/equip", response_model=EntitySnapshot)
async def equip_item(request: EquipRequest, entity: Entity = Depends(get_entity)):
    """
    Equip an item to an entity. The slot can be automatically determined for most items
    except weapons and rings which require explicit slot specification.
    """
    equipment = BaseBlock.get(request.equipment_uuid)
    if not equipment:
        raise HTTPException(status_code=404, detail="Equipment not found")
    if not isinstance(equipment, (Armor, Weapon, Shield)):
        raise HTTPException(status_code=400, detail="Invalid equipment type")
    
    try:
        # Convert slot enum to appropriate type
        slot = None
        if request.slot:
            if request.slot in [SlotType.MAIN_HAND, SlotType.OFF_HAND]:
                slot = WeaponSlot(request.slot.value)
            elif request.slot in [SlotType.RING_LEFT, SlotType.RING_RIGHT]:
                slot = RingSlot(request.slot.value)
            else:
                slot = BodyPart(request.slot.value)

        entity.equipment.equip(equipment, slot)
        return EntitySnapshot.from_engine(
            entity,
            include_skill_calculations=True,
            include_attack_calculations=True,
            include_ac_calculation=True,
            include_saving_throw_calculations=True
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{entity_uuid}/unequip/{slot}", response_model=EntitySnapshot)
async def unequip_item(slot: SlotType, entity: Entity = Depends(get_entity)):
    """
    Unequip an item from a specific slot on an entity.
    """
    try:
        print(f"Unequipping from slot: {slot}, value: {slot.value}")  # Debug log
        
        # First validate that there's actually something equipped in that slot
        if slot in [SlotType.MAIN_HAND, SlotType.OFF_HAND]:
            weapon_slot = WeaponSlot(slot.value)
            if weapon_slot == WeaponSlot.MAIN_HAND and not entity.equipment.weapon_main_hand:
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "error": "Nothing to unequip",
                        "message": "No weapon equipped in main hand",
                        "slot": slot.value
                    }
                )
            if weapon_slot == WeaponSlot.OFF_HAND and not entity.equipment.weapon_off_hand:
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "error": "Nothing to unequip",
                        "message": "No weapon or shield equipped in off hand",
                        "slot": slot.value
                    }
                )
            slot_type = weapon_slot
        elif slot in [SlotType.RING_LEFT, SlotType.RING_RIGHT]:
            if slot == SlotType.RING_LEFT and not entity.equipment.ring_left:
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "error": "Nothing to unequip",
                        "message": "No ring equipped in left ring slot",
                        "slot": slot.value
                    }
                )
            if slot == SlotType.RING_RIGHT and not entity.equipment.ring_right:
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "error": "Nothing to unequip",
                        "message": "No ring equipped in right ring slot",
                        "slot": slot.value
                    }
                )
            slot_type = RingSlot[slot.value]
        else:
            # Handle armor slots
            armor_slot_map = {
                SlotType.HEAD: ("helmet", "head"),
                SlotType.BODY: ("body_armor", "body"),
                SlotType.HANDS: ("gauntlets", "hands"),
                SlotType.LEGS: ("greaves", "legs"),
                SlotType.FEET: ("boots", "feet"),
                SlotType.AMULET: ("amulet", "amulet"),
                SlotType.CLOAK: ("cloak", "cloak"),
            }
            if slot not in armor_slot_map:
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "error": "Invalid slot",
                        "message": f"Slot {slot.value} is not a valid equipment slot",
                        "slot": slot.value
                    }
                )
            attr_name, slot_name = armor_slot_map[slot]
            if not getattr(entity.equipment, attr_name):
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "error": "Nothing to unequip",
                        "message": f"No armor equipped in {slot_name} slot",
                        "slot": slot.value
                    }
                )
            slot_type = BodyPart(slot.value)  # Create enum instance with the value instead of looking up by key
            
        try:
            entity.equipment.unequip(slot_type)
            return EntitySnapshot.from_engine(
                entity,
                include_skill_calculations=True,
                include_attack_calculations=True,
                include_ac_calculation=True,
                include_saving_throw_calculations=True
            )
        except Exception as e:
            print(f"Error during unequip operation: {str(e)}")  # Debug log
            raise HTTPException(
                status_code=400, 
                detail={
                    "error": "Unequip failed",
                    "message": str(e),
                    "slot": slot.value
                }
            )
            
    except HTTPException:
        raise  # Re-raise HTTP exceptions as is
    except Exception as e:
        print(f"Unexpected error during unequip: {str(e)}")  # Debug log
        raise HTTPException(
            status_code=400, 
            detail={
                "error": "Unexpected error",
                "message": str(e),
                "slot": slot.value
            }
        ) 

# Add new models for condition management
class AddConditionRequest(BaseModel):
    condition_type: ConditionType
    source_entity_uuid: UUID
    duration_type: DurationType = DurationType.PERMANENT
    duration_rounds: Optional[int] = None

class RemoveConditionRequest(BaseModel):
    condition_name: str

@router.post("/{entity_uuid}/conditions", response_model=EntitySnapshot)
async def add_condition(
    request: AddConditionRequest,
    entity: Entity = Depends(get_entity)
):
    """
    Add a condition to an entity.
    The entity_uuid in the path is the target entity.
    The source_entity_uuid in the request is the entity causing the condition.
    Returns the full updated entity snapshot.
    """
    try:
        # Create the condition
        condition = create_condition(
            condition_type=request.condition_type,
            source_entity_uuid=request.source_entity_uuid,
            target_entity_uuid=entity.uuid,
            duration_type=request.duration_type,
            duration_rounds=request.duration_rounds
        )
        
        # Add the condition to the entity
        result = entity.add_condition(condition)
        if not result:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Failed to apply condition",
                    "message": "The condition could not be applied. The entity might be immune or have passed a saving throw.",
                    "condition": request.condition_type
                }
            )
            
        # Return updated entity snapshot with all calculations
        return EntitySnapshot.from_engine(
            entity,
            include_skill_calculations=True,
            include_attack_calculations=True,
            include_ac_calculation=True,
            include_saving_throw_calculations=True
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Failed to add condition",
                "message": str(e),
                "condition": request.condition_type
            }
        )

@router.delete("/{entity_uuid}/conditions/{condition_name}", response_model=EntitySnapshot)
async def remove_condition(
    condition_name: str,
    entity: Entity = Depends(get_entity)
):
    """
    Remove a condition from an entity by its name.
    Returns the full updated entity snapshot.
    """
    try:
        if condition_name not in entity.active_conditions:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Condition not found",
                    "message": f"The condition '{condition_name}' is not active on this entity",
                    "condition": condition_name
                }
            )
            
        entity.remove_condition(condition_name)
        
        # Return updated entity snapshot with all calculations
        return EntitySnapshot.from_engine(
            entity,
            include_skill_calculations=True,
            include_attack_calculations=True,
            include_ac_calculation=True,
            include_saving_throw_calculations=True
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Failed to remove condition",
                "message": str(e),
                "condition": condition_name
            }
        )

@router.get("/{entity_uuid}/conditions", response_model=Dict[str, ConditionSnapshot])
async def get_conditions(entity: Entity = Depends(get_entity)):
    """
    Get all active conditions on an entity.
    For just the conditions list, use this endpoint.
    For full entity state including conditions, use GET /entities/{entity_uuid}
    """
    return entity.active_conditions 