"""
Tile system for the D&D engine.

Tile is a BaseBlock that represents a single cell on the game grid.
As a BaseBlock, tiles can have conditions attached (fire, traps, difficult terrain).

GridMap handles all spatial computation (FOV, pathfinding).
Tiles are stored in GridMap and provide the data/state for each cell.
"""

from typing import Optional, Tuple
from uuid import uuid4
from pydantic import Field

from dnd.core.base_block import BaseBlock


class Tile(BaseBlock):
    """
    A tile on the game grid.

    As a BaseBlock, tiles can:
    - Have conditions attached (OnFire, Trapped, DifficultTerrain, etc.)
    - Have event handlers for when entities enter/leave
    - Be identified by UUID

    GridMap stores tiles and handles spatial computation.
    """
    name: str = Field(default="Floor", description="The name of the tile")
    walkable: bool = Field(default=True, description="Whether the tile can be walked on")
    visible: bool = Field(default=True, description="Whether the tile can be seen through")
    sprite_name: Optional[str] = Field(default=None, description="The name of the sprite to use for the tile")
    # position is inherited from BaseBlock

    # Enable conditions on tiles
    allow_events_conditions: bool = Field(default=True, description="Tiles can have conditions")

    @classmethod
    def create(cls, position: Tuple[int, int],
               walkable: bool = True,
               visible: bool = True,
               name: str = "Floor",
               sprite_name: Optional[str] = None) -> 'Tile':
        """Create a new tile at position."""
        tile_uuid = uuid4()
        return cls(
            uuid=tile_uuid,
            source_entity_uuid=tile_uuid,  # Tiles are their own source
            position=position,
            walkable=walkable,
            visible=visible,
            name=name,
            sprite_name=sprite_name
        )


# Factory functions for common tile types
def floor_factory(position: Tuple[int, int]) -> Tile:
    """Create a floor tile."""
    return Tile.create(position, walkable=True, visible=True, name="Floor", sprite_name="floor.png")


def wall_factory(position: Tuple[int, int]) -> Tile:
    """Create a wall tile."""
    return Tile.create(position, walkable=False, visible=False, name="Wall", sprite_name="wall.png")


def water_factory(position: Tuple[int, int]) -> Tile:
    """Create a water tile (can't walk, can see through)."""
    return Tile.create(position, walkable=False, visible=True, name="Water", sprite_name="water.png")
