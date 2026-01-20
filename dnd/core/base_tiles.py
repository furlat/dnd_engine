"""
Tile system for the D&D engine.

The Tile class provides backwards-compatible API but delegates to GridMap internally.
For new code, prefer using GridMap directly via `from dnd.core.gridmap import get_map`.
"""

from typing import Dict, Optional, List, Tuple
from uuid import UUID, uuid4
from pydantic import Field

from dnd.core.base_object import BaseObject
from dnd.core.gridmap import  TileData, get_map


class Tile(BaseObject):
    """
    A tile on the game grid.

    Note: This class maintains backwards compatibility but delegates to GridMap.
    For new code, consider using GridMap directly for better performance.
    """
    name: str = Field(default="Floor", description="The name of the tile")
    position: Tuple[int, int] = Field(description="The position of the tile on the grid")
    walkable: bool = Field(default=True, description="Whether the tile can be walked on")
    visible: bool = Field(default=True, description="Whether the tile can be seen through")
    sprite_name: Optional[str] = Field(default=None, description="The name of the sprite to use for the tile")

    def __init__(self, **data):
        """Initialize tile and register with GridMap."""
        super().__init__(**data)
        # Register with GridMap
        grid = get_map()
        grid.set_tile(
            self.position[0], self.position[1],
            walkable=self.walkable,
            visible=self.visible,
            name=self.name,
            sprite_name=self.sprite_name
        )

    @classmethod
    def get_all_tiles(cls) -> List['Tile']:
        """
        Get all tiles.

        Note: Returns TileData wrapped in a list for compatibility.
        For better performance, use GridMap.get_all_tiles() directly.
        """
        # This is inefficient but maintains backwards compatibility
        # New code should use GridMap directly
        grid = get_map()
        tiles = []
        for pos, tile_data in grid.get_all_tiles().items():
            # Create lightweight tile objects (not registered again)
            tiles.append(_create_tile_view(pos, tile_data))
        return tiles

    @classmethod
    def get_tile_at_position(cls, position: Tuple[int, int]) -> Optional['Tile']:
        """Get tile at position."""
        grid = get_map()
        tile_data = grid.get_tile(position[0], position[1])
        if tile_data is None:
            return None
        return _create_tile_view(position, tile_data)

    @classmethod
    def get(cls, uuid: UUID) -> Optional['Tile']:
        """
        Get tile by UUID.

        Note: GridMap doesn't track UUIDs, so this always returns None.
        Use get_tile_at_position instead.
        """
        # GridMap doesn't track individual tile UUIDs
        # This is kept for API compatibility but won't work
        return None

    @classmethod
    def grid_size(cls) -> Tuple[int, int]:
        """Get grid dimensions as (width, height)."""
        grid = get_map()
        return grid.size

    @classmethod
    def create(cls, position: Tuple[int, int], sprite_name: Optional[str] = None,
               can_walk: bool = True, can_see: bool = True, name: str = "Floor") -> 'Tile':
        """Create a new tile at position."""
        tile_uuid = uuid4()
        return cls(
            uuid=tile_uuid,
            source_entity_uuid=tile_uuid,
            target_entity_uuid=tile_uuid,
            position=position,
            sprite_name=sprite_name,
            walkable=can_walk,
            visible=can_see,
            name=name
        )

    @classmethod
    def is_visible(cls, position: Tuple[int, int]) -> bool:
        """Check if position allows vision."""
        return get_map().is_visible(position[0], position[1])

    @classmethod
    def is_walkable(cls, position: Tuple[int, int]) -> bool:
        """Check if position is walkable."""
        return get_map().is_walkable(position[0], position[1])

    @classmethod
    def get_fov(cls, source_pos: Tuple[int, int], max_distance: Optional[float] = None) -> List[Tuple[int, int]]:
        """Compute field of view from position using shadowcasting."""
        return get_map().compute_fov(source_pos, max_distance)

    @classmethod
    def get_paths(cls, start_pos: Tuple[int, int], max_distance: Optional[int] = None
                  ) -> Tuple[Dict[Tuple[int, int], int], Dict[Tuple[int, int], List[Tuple[int, int]]]]:
        """Compute paths from position using Dijkstra."""
        return get_map().compute_paths(start_pos, max_distance)


def _create_tile_view(position: Tuple[int, int], tile_data: TileData) -> Tile:
    """Create a Tile view object without registering it again."""
    # Temporarily disable registration by creating object directly
    tile = object.__new__(Tile)
    BaseObject.__init__(tile, uuid=uuid4(), source_entity_uuid=uuid4(), target_entity_uuid=uuid4())
    tile.name = tile_data.name
    tile.position = position
    tile.walkable = tile_data.walkable
    tile.visible = tile_data.visible
    tile.sprite_name = tile_data.sprite_name
    return tile


# Factory functions
def floor_factory(position: Tuple[int, int]) -> Tile:
    """Create a floor tile."""
    return Tile.create(position, sprite_name="floor.png", can_walk=True, can_see=True, name="Floor")


def wall_factory(position: Tuple[int, int]) -> Tile:
    """Create a wall tile."""
    return Tile.create(position, sprite_name="wall.png", can_walk=False, can_see=False, name="Wall")


def water_factory(position: Tuple[int, int]) -> Tile:
    """Create a water tile (can't walk, can see through)."""
    return Tile.create(position, sprite_name="water.png", can_walk=False, can_see=True, name="Water")
