from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict, Optional, Union, Literal, Tuple
from uuid import UUID
from enum import Enum
from pydantic import BaseModel, Field

# Import entity and models
from app.models.sensory import SensesSnapshot
from dnd.entity import Entity
from app.models.entity import EntitySnapshot, ConditionSnapshot, EntitySummary
from app.models.health import HealthSnapshot
from app.models.abilities import AbilityScoresSnapshot
from app.models.skills import SkillSetSnapshot
from app.models.equipment import EquipmentSnapshot
from app.models.saving_throws import SavingThrowSetSnapshot
from app.models.values import ModifiableValueSnapshot
from app.models.events import EventSnapshot
from dnd.core.events import WeaponSlot
from dnd.blocks.equipment import Equipment, BaseBlock, Armor, Weapon, Shield, BodyPart, RingSlot
from dnd.core.base_conditions import DurationType
from dnd.conditions import ConditionType, create_condition
from dnd.actions import Attack, Move, MovementEvent

# Import dependencies
from app.api.deps import get_entity

# Position-related models
class Position(BaseModel):
    x: int
    y: int

class MoveRequest(BaseModel):
    position: Tuple[int, int]
    include_paths_senses: bool = False

class MovementResponse(BaseModel):
    event: EventSnapshot
    entity: EntitySummary
    path_senses: Dict[Tuple[int,int],SensesSnapshot] = Field(default_factory=dict)

# NEW: Attack-related models to preserve metadata lost in event translation
class AttackMetadata(BaseModel):
    """Metadata extracted from AttackEvent that gets lost in event translation"""
    weapon_slot: str  # WeaponSlot enum value
    attack_roll: Optional[int] = None  # The d20 roll result
    attack_total: Optional[int] = None  # Total attack bonus + roll
    target_ac: Optional[int] = None  # Target's AC
    attack_outcome: Optional[str] = None  # Hit/Miss/Crit/etc
    damage_rolls: Optional[List[int]] = None  # Individual damage roll totals
    total_damage: Optional[int] = None  # Sum of all damage
    damage_types: Optional[List[str]] = None  # Types of damage dealt

class AttackResponse(BaseModel):
    event: EventSnapshot
    metadata: AttackMetadata

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
    entities = Entity.get_all_entities()
    
    # Convert to a list of basic info
    return [EntityListItem(uuid=entity.uuid, name=entity.name) for entity in entities]

@router.get("/summaries", response_model=List[EntitySummary])
async def list_entity_summaries():
    """List all entities with their summary information (name, HP, AC, target)"""
    # Get all entities from the registry
    entities = Entity.get_all_entities()
    
    # Convert to a list of summaries with proper error handling
    summaries = []
    for entity in entities:
        try:
            summary = EntitySummary.from_engine(entity)
            # print(f"Summary for entity {entity.uuid}: {summary} with target {entity.target_entity_uuid}")
            summaries.append(summary)
        except Exception as e:
            print(f"Error creating summary for entity {entity.uuid}: {str(e)}")
            continue
    
    return summaries

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

@router.post("/{entity_uuid}/action-economy/refresh", response_model=EntitySnapshot)
async def refresh_action_economy(
    entity: Entity = Depends(get_entity),
    include_skill_calculations: bool = False,
    include_attack_calculations: bool = False,
    include_ac_calculation: bool = False,
    include_saving_throw_calculations: bool = False
):
    """Reset all action economy costs for an entity"""
    entity.action_economy.reset_all_costs()
    return EntitySnapshot.from_engine(
        entity,
        include_skill_calculations=include_skill_calculations,
        include_attack_calculations=include_attack_calculations,
        include_ac_calculation=include_ac_calculation,
        include_saving_throw_calculations=include_saving_throw_calculations
    ) 

@router.post("/{entity_uuid}/target/{target_uuid}", response_model=EntitySnapshot)
async def set_entity_target(
    entity_uuid: UUID,
    target_uuid: UUID,
    include_skill_calculations: bool = False,
    include_attack_calculations: bool = False,
    include_ac_calculation: bool = False,
    include_saving_throw_calculations: bool = False
):
    """Set an entity's target"""
    entity = Entity.get(entity_uuid)
    target = Entity.get(target_uuid)
    
    if not entity:
        raise HTTPException(status_code=404, detail="Source entity not found")
    if not target:
        raise HTTPException(status_code=404, detail="Target entity not found")
        
    entity.set_target_entity(target_uuid)
    return EntitySnapshot.from_engine(
        entity,
        include_skill_calculations=include_skill_calculations,
        include_attack_calculations=include_attack_calculations,
        include_ac_calculation=include_ac_calculation,
        include_saving_throw_calculations=include_saving_throw_calculations
    ) 

@router.post("/{entity_uuid}/attack/{target_uuid}", response_model=AttackResponse)
async def execute_attack(
    entity_uuid: UUID,
    target_uuid: UUID,
    weapon_slot: WeaponSlot = Query(WeaponSlot.MAIN_HAND, description="Which weapon slot to use for the attack"),
    attack_name: str = Query("Attack", description="Name of the attack")
):
    """Execute an attack from one entity to another and return event + metadata"""
    entity = Entity.get(entity_uuid)
    target = Entity.get(target_uuid)
    
    if not entity:
        raise HTTPException(status_code=404, detail="Source entity not found")
    if not target:
        raise HTTPException(status_code=404, detail="Target entity not found")
    
    # Create and execute the attack
    attack = Attack(
        name=attack_name,
        source_entity_uuid=entity_uuid,
        target_entity_uuid=target_uuid,
        weapon_slot=weapon_slot
    )
    
    result_event = attack.apply()
    if not result_event:
        raise HTTPException(status_code=400, detail="Attack could not be executed")
    
    # Cast to AttackEvent to access attack-specific attributes
    from dnd.actions import AttackEvent
    if not isinstance(result_event, AttackEvent):
        raise HTTPException(status_code=500, detail="Expected AttackEvent but got different event type")
    
    # Extract metadata from the AttackEvent that gets lost in event translation
    attack_roll = None
    if result_event.dice_roll and result_event.dice_roll.results:
        # For d20 rolls, results is typically a list with the natural roll as first element
        if isinstance(result_event.dice_roll.results, list) and len(result_event.dice_roll.results) > 0:
            attack_roll = result_event.dice_roll.results[0]
        elif isinstance(result_event.dice_roll.results, int):
            attack_roll = result_event.dice_roll.results
    
    metadata = AttackMetadata(
        weapon_slot=weapon_slot.value,
        attack_roll=attack_roll,
        attack_total=result_event.dice_roll.total if result_event.dice_roll else None,
        target_ac=result_event.ac.normalized_score if result_event.ac else None,
        attack_outcome=result_event.attack_outcome.value if result_event.attack_outcome else None,
        damage_rolls=[roll.total for roll in result_event.damage_rolls] if result_event.damage_rolls else None,
        total_damage=sum(roll.total for roll in result_event.damage_rolls) if result_event.damage_rolls else None,
        damage_types=[damage.damage_type.value for damage in result_event.damages] if result_event.damages else None
    )
    
    return AttackResponse(
        event=EventSnapshot.from_engine(result_event, include_children=True),
        metadata=metadata
    ) 

@router.get("/position/{x}/{y}", response_model=List[EntitySummary])
async def get_entities_at_position(x: int, y: int):
    """Get all entities at a specific position"""
    try:
        entities = Entity.get_all_entities_at_position((x, y))
        return [EntitySummary.from_engine(entity) for entity in entities]
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Failed to get entities at position",
                "message": str(e),
                "position": (x, y)
            }
        )

@router.post("/{entity_uuid}/move", response_model=MovementResponse)
async def move_entity(
    request: MoveRequest,
    entity: Entity = Depends(get_entity)
):
    """Move an entity to a new position and return its updated summary"""
    try:
        Entity.update_entity_senses(entity)
        movement_action = Move(name=f"{entity.name} moves to {request.position}",source_entity_uuid=entity.uuid,target_entity_uuid=entity.uuid,end_position=request.position)
        movement_event = movement_action.apply()
        entity_summary = EntitySummary.from_engine(entity)
        assert isinstance(movement_event, MovementEvent)
        if request.include_paths_senses and movement_event.path:
            if movement_event.status_message:
                movement_event.status_message += f"\n added senses info"
            else:
                movement_event.status_message = f"added senses info"
        return MovementResponse(
            event=EventSnapshot.from_engine(movement_event, include_children=True),
            entity=entity_summary,
            path_senses= {pos: SensesSnapshot.from_engine(entity.create_senses_copy_at_position(pos)) for pos in movement_event.path} if request.include_paths_senses and movement_event.path else {}
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Failed to move entity",
                "message": str(e),
                "position": request.position
            }
        ) 