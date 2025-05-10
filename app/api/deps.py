from fastapi import HTTPException, Depends
from uuid import UUID
from typing import Optional, Any

from dnd.entity import Entity
from dnd.core.base_block import BaseBlock

def get_entity(entity_uuid: UUID) -> Entity:
    """
    Dependency to retrieve an entity by UUID from the registry.
    
    Args:
        entity_uuid: The UUID of the entity to retrieve
        
    Returns:
        Entity: The requested entity
        
    Raises:
        HTTPException: If the entity is not found
    """
    entity = Entity.get(entity_uuid)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity with UUID {entity_uuid} not found")
    if not isinstance(entity, Entity):
        raise HTTPException(status_code=400, detail=f"BaseObject with UUID {entity_uuid} is not an instance of Entity")
    return entity

def get_entity_block(entity_uuid: UUID, block_name: str) -> Any:
    """
    Dependency to retrieve a specific block from an entity.
    
    Args:
        entity_uuid: The UUID of the entity
        block_name: The name of the block to retrieve
        
    Returns:
        Any: The requested block (usually a BaseBlock instance)
        
    Raises:
        HTTPException: If the entity or block is not found
    """
    entity = get_entity(entity_uuid)
    
    if not hasattr(entity, block_name):
        raise HTTPException(status_code=400, detail=f"Entity does not have a block named {block_name}")
    
    return getattr(entity, block_name) 