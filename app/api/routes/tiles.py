from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict, Optional, Union, Literal, Tuple
from uuid import UUID
from enum import Enum
from pydantic import BaseModel

from dnd.core.base_tiles import Tile, floor_factory, wall_factory, water_factory
from app.models.tile import TileSnapshot, TileSummary, GridSnapshot
from dnd.entity import Entity
# Create router
router = APIRouter(
    prefix="/tiles",
    tags=["tiles"],
    responses={404: {"description": "Tile not found"}},
)

# Define tile types for factory creation
class TileType(str, Enum):
    FLOOR = "floor"
    WALL = "wall"
    WATER = "water"

# Model for creating a new tile
class CreateTileRequest(BaseModel):
    position: Tuple[int, int]
    tile_type: TileType

@router.get("/", response_model=GridSnapshot)
async def get_all_tiles():
    """Get a snapshot of the entire tile grid"""
    return GridSnapshot.from_engine()

@router.get("/position/{x}/{y}", response_model=TileSnapshot)
async def get_tile_at_position(x: int, y: int):
    """Get tile at a specific position"""
    tile = Tile.get_tile_at_position((x, y))
    if not tile:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Tile not found",
                "message": f"No tile exists at position ({x}, {y})",
                "position": (x, y)
            }
        )
    return TileSnapshot.from_engine(tile)

@router.get("/{tile_uuid}", response_model=TileSnapshot)
async def get_tile_by_uuid(tile_uuid: UUID):
    """Get tile by UUID"""
    tile = Tile.get(tile_uuid)
    if not tile:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Tile not found",
                "message": f"No tile exists with UUID {tile_uuid}",
                "uuid": tile_uuid
            }
        )
    return TileSnapshot.from_engine(tile)

@router.post("/", response_model=TileSnapshot)
async def create_tile(request: CreateTileRequest):
    """Create a new tile at the specified position using the specified factory"""
    # Check if position is already occupied
    # existing_tile = Tile.get_tile_at_position(request.position)
    # if existing_tile:
    #     raise HTTPException(
    #         status_code=400,
    #         detail={
    #             "error": "Position occupied",
    #             "message": f"A tile already exists at position {request.position}",
    #             "position": request.position
    #         }
    #     )

    # Create tile using appropriate factory
    try:
        if request.tile_type == TileType.FLOOR:
            tile = floor_factory(request.position)
        elif request.tile_type == TileType.WALL:
            tile = wall_factory(request.position)
        elif request.tile_type == TileType.WATER:
            tile = water_factory(request.position)
        else:
            raise ValueError(f"Invalid tile type: {request.tile_type}")
        Entity.update_all_entities_senses()
        return TileSnapshot.from_engine(tile)

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Failed to create tile",
                "message": str(e),
                "request": request.dict()
            }
        )

@router.delete("/position/{x}/{y}")
async def delete_tile_at_position(x: int, y: int):
    """Delete tile at a specific position"""
    tile = Tile.get_tile_at_position((x, y))
    if not tile:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Tile not found",
                "message": f"No tile exists at position ({x}, {y})",
                "position": (x, y)
            }
        )
    
    # Remove from registries
    Tile._tile_registry.pop(tile.uuid, None)
    Tile._tile_by_position.pop(tile.position, None)
    
    return {"message": f"Tile at position ({x}, {y}) deleted successfully"}

@router.get("/walkable/{x}/{y}")
async def is_position_walkable(x: int, y: int):
    """Check if a position is walkable"""
    return {
        "position": (x, y),
        "walkable": Tile.is_walkable((x, y))
    }

@router.get("/visible/{x}/{y}")
async def is_position_visible(x: int, y: int):
    """Check if a position is visible"""
    return {
        "position": (x, y),
        "visible": Tile.is_visible((x, y))
    } 