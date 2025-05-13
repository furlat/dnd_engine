from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Any, Tuple
from uuid import UUID
from dnd.core.base_tiles import Tile

class TileSummary(BaseModel):
    """Lightweight summary of a tile's core properties"""
    uuid: UUID
    name: str
    position: Tuple[int, int]
    walkable: bool
    visible: bool
    sprite_name: Optional[str] = None

    @classmethod
    def from_engine(cls, tile: Tile):
        """Create a summary from an engine Tile object"""
        return cls(
            uuid=tile.uuid,
            name=tile.name,
            position=tile.position,
            walkable=tile.walkable,
            visible=tile.visible,
            sprite_name=tile.sprite_name
        )

class TileSnapshot(BaseModel):
    """Interface model for a Tile snapshot with complete information"""
    uuid: UUID
    name: str
    position: Tuple[int, int]
    walkable: bool
    visible: bool
    sprite_name: Optional[str] = None
    entities: List[UUID] = Field(default_factory=list)  # List of entity UUIDs on this tile

    @classmethod
    def from_engine(cls, tile: Tile):
        """
        Create a snapshot from an engine Tile object
        
        Args:
            tile: The engine Tile object
        """
        from dnd.entity import Entity
        
        # Get all entities at this tile's position
        entities_at_position = Entity.get_all_entities_at_position(tile.position)
        entity_uuids = [entity.uuid for entity in entities_at_position]

        return cls(
            uuid=tile.uuid,
            name=tile.name,
            position=tile.position,
            walkable=tile.walkable,
            visible=tile.visible,
            sprite_name=tile.sprite_name,
            entities=entity_uuids
        )

class GridSnapshot(BaseModel):
    """Interface model for the entire grid of tiles"""
    width: int
    height: int
    tiles: Dict[Tuple[int, int], TileSummary] = Field(default_factory=dict)

    @classmethod
    def from_engine(cls):
        """Create a snapshot of the entire tile grid"""
        tiles = {}
        width, height = Tile.grid_size()
        
        for x in range(width):
            for y in range(height):
                pos = (x, y)
                tile = Tile.get_tile_at_position(pos)
                if tile is not None:
                    tiles[pos] = TileSummary.from_engine(tile)

        return cls(
            width=width,
            height=height,
            tiles=tiles
        ) 