from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict
from uuid import UUID
from enum import Enum
from pydantic import BaseModel

# Import entity and models
from dnd.entity import Entity
from dnd.interfaces.entitiy import EntitySnapshot
from dnd.interfaces.health import HealthSnapshot
from dnd.interfaces.abilities import AbilityScoresSnapshot
from dnd.interfaces.skills import SkillSetSnapshot
from dnd.interfaces.equipment import EquipmentSnapshot
from dnd.interfaces.saving_throws import SavingThrowSetSnapshot
from dnd.interfaces.values import ModifiableValueSnapshot

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
    include_ac_calculation: bool = False
):
    """Get an entity by UUID and convert to interface model"""
    # Convert the entity to its interface counterpart and return directly
    return EntitySnapshot.from_engine(
        entity, 
        include_skill_calculations=include_skill_calculations,
        include_attack_calculations=include_attack_calculations,
        include_ac_calculation=include_ac_calculation
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
    return EquipmentSnapshot.from_engine(entity.equipment)

@router.get("/{entity_uuid}/saving_throws", response_model=SavingThrowSetSnapshot)
async def get_entity_saving_throws(entity: Entity = Depends(get_entity)):
    """Get entity saving throws snapshot"""
    return SavingThrowSetSnapshot.from_engine(entity.saving_throws, entity)

@router.get("/{entity_uuid}/proficiency_bonus", response_model=ModifiableValueSnapshot)
async def get_entity_proficiency_bonus(entity: Entity = Depends(get_entity)):
    """Get entity proficiency bonus snapshot"""
    return ModifiableValueSnapshot.from_engine(entity.proficiency_bonus) 