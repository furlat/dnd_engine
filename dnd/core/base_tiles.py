"""
Tile system for the D&D engine.

Tile is a BaseBlock that represents a single cell on the game grid.
As a BaseBlock, tiles can have conditions attached (fire, traps, difficult terrain).

GridMap handles all spatial computation (FOV, pathfinding).
Tiles are stored in GridMap and provide the data/state for each cell.
"""

from typing import Optional, Tuple
from uuid import UUID, uuid4
from pydantic import Field
from dnd.core.base_block import BaseBlock, MovementMode
from dnd.core.values import ModifiableValue
from dnd.core.modifiers import NumericalModifier


class Tile(BaseBlock):
    """
    A tile on the game grid.

    As a BaseBlock, tiles can:
    - Have conditions attached (OnFire, Trapped, DifficultTerrain, etc.)
    - Have event handlers for when entities enter/leave
    - Be identified by UUID

    GridMap stores tiles and handles spatial computation.

    Movement Costs:
    - Each movement mode has its own cost ModifiableValue
    - Cost of 1 = normal, 2 = difficult terrain
    - Cost of 0 (via max_constraint) = impassable for that mode

    Borders:
    - Each border (N/S/E/W) controls whether entry from that direction is allowed
    - Used for one-way passages, doors, etc.

    Height:
    - Elevation in 5ft increments (0 = ground level)
    """
    name: str = Field(default="Floor", description="The name of the tile")
    walkable: bool = Field(default=True, description="Whether the tile can be walked on (legacy, use walking_cost)")
    visible: bool = Field(default=True, description="Whether the tile can be seen through")
    sprite_name: Optional[str] = Field(default=None, description="The name of the sprite to use for the tile")
    # position is inherited from BaseBlock

    # Enable conditions on tiles
    allow_events_conditions: bool = Field(default=True, description="Tiles can have conditions")

    # Movement costs per mode (1 = normal, 2 = difficult terrain, 0 via max = impassable)
    walking_cost: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=1,
            value_name="Walking Cost"
        )
    )
    flying_cost: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=1,
            value_name="Flying Cost"
        )
    )
    swimming_cost: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=0,
            value_name="Swimming Cost"
        )
    )
    burrowing_cost: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=0,
            value_name="Burrowing Cost"
        )
    )

    # Border walkability (True = can pass, False = blocked from that direction)
    border_north: bool = Field(default=True, description="Can enter from north (y+1)")
    border_south: bool = Field(default=True, description="Can enter from south (y-1)")
    border_east: bool = Field(default=True, description="Can enter from east (x+1)")
    border_west: bool = Field(default=True, description="Can enter from west (x-1)")

    # Elevation (0 = ground level, each unit = 5ft)
    height: int = Field(default=0, description="Tile elevation in 5ft increments")

    def get_movement_cost(self, mode: MovementMode) -> float:
        """Get the movement cost for a specific mode."""
        cost_map = {
            MovementMode.WALKING: self.walking_cost,
            MovementMode.FLYING: self.flying_cost,
            MovementMode.SWIMMING: self.swimming_cost,
            MovementMode.BURROWING: self.burrowing_cost,
        }
        return cost_map[mode].normalized_score

    def blocks_walking(self, requesting_entity_uuid: Optional['UUID'] = None,
                       mode: MovementMode = MovementMode.WALKING) -> bool:
        """A tile blocks walking if its movement cost for the given mode is 0 or less."""
        return self.get_movement_cost(mode) <= 0

    def blocks_vision(self, requesting_entity_uuid: Optional['UUID'] = None) -> bool:
        """A tile blocks vision if it is not visible (e.g., walls)."""
        return not self.visible

    def can_enter_from(self, from_position: Tuple[int, int]) -> bool:
        """
        Check if an entity can enter this tile from an adjacent position.

        Args:
            from_position: The position the entity is coming FROM

        Returns:
            True if the border allows passage
        """
        if self.position is None:
            return True

        dx = self.position[0] - from_position[0]
        dy = self.position[1] - from_position[1]

        # Orthogonal movement - check single border
        if dx == 1 and dy == 0:
            return self.border_west   # Coming from west
        elif dx == -1 and dy == 0:
            return self.border_east   # Coming from east
        elif dx == 0 and dy == 1:
            return self.border_south  # Coming from south
        elif dx == 0 and dy == -1:
            return self.border_north  # Coming from north

        # Diagonal movement - at least ONE touching border must be open
        elif dx == 1 and dy == 1:
            return self.border_west or self.border_south
        elif dx == 1 and dy == -1:
            return self.border_west or self.border_north
        elif dx == -1 and dy == 1:
            return self.border_east or self.border_south
        elif dx == -1 and dy == -1:
            return self.border_east or self.border_north

        return True  # Same position or non-adjacent

    @classmethod
    def create(cls, position: Tuple[int, int],
               walkable: bool = True,
               visible: bool = True,
               name: str = "Floor",
               sprite_name: Optional[str] = None,
               height: int = 0) -> 'Tile':
        """Create a new tile at position."""
        tile_uuid = uuid4()

        # Create movement cost ModifiableValues
        walking_cost = ModifiableValue.create(
            source_entity_uuid=tile_uuid,
            base_value=1 if walkable else 0,
            value_name="Walking Cost"
        )
        # If not walkable, add max constraint of 0
        if not walkable:
            walking_cost.self_static.add_max_constraint(
                NumericalModifier.create(
                    source_entity_uuid=tile_uuid,
                    name="Impassable",
                    value=0
                )
            )

        flying_cost = ModifiableValue.create(
            source_entity_uuid=tile_uuid,
            base_value=1,
            value_name="Flying Cost"
        )

        swimming_cost = ModifiableValue.create(
            source_entity_uuid=tile_uuid,
            base_value=0,
            value_name="Swimming Cost"
        )
        # No swimming by default
        swimming_cost.self_static.add_max_constraint(
            NumericalModifier.create(
                source_entity_uuid=tile_uuid,
                name="No Water",
                value=0
            )
        )

        burrowing_cost = ModifiableValue.create(
            source_entity_uuid=tile_uuid,
            base_value=0,
            value_name="Burrowing Cost"
        )
        # No burrowing by default
        burrowing_cost.self_static.add_max_constraint(
            NumericalModifier.create(
                source_entity_uuid=tile_uuid,
                name="No Earth",
                value=0
            )
        )

        return cls(
            uuid=tile_uuid,
            source_entity_uuid=tile_uuid,  # Tiles are their own source
            position=position,
            walkable=walkable,
            visible=visible,
            name=name,
            sprite_name=sprite_name,
            walking_cost=walking_cost,
            flying_cost=flying_cost,
            swimming_cost=swimming_cost,
            burrowing_cost=burrowing_cost,
            height=height
        )


# Factory functions for common tile types
def floor_factory(position: Tuple[int, int]) -> Tile:
    """Create a floor tile."""
    return Tile.create(position, walkable=True, visible=True, name="Floor", sprite_name="floor.png")


def wall_factory(position: Tuple[int, int]) -> Tile:
    """Create a wall tile."""
    tile = Tile.create(position, walkable=False, visible=False, name="Wall", sprite_name="wall.png")
    # Walls also block flying
    tile.flying_cost.self_static.add_max_constraint(
        NumericalModifier.create(
            source_entity_uuid=tile.uuid,
            name="Solid",
            value=0
        )
    )
    return tile


def water_factory(position: Tuple[int, int]) -> Tile:
    """Create a water tile (can't walk, can see through, can swim)."""
    tile = Tile.create(position, walkable=False, visible=True, name="Water", sprite_name="water.png")

    # Remove the "No Water" constraint and set swimming cost to 1
    # First clear existing constraints
    for mod_uuid in list(tile.swimming_cost.self_static.max_constraints.keys()):
        tile.swimming_cost.self_static.remove_max_constraint(mod_uuid)

    # Set swimming as possible (cost 1)
    tile.swimming_cost = ModifiableValue.create(
        source_entity_uuid=tile.uuid,
        base_value=1,
        value_name="Swimming Cost"
    )

    return tile


def difficult_terrain_factory(position: Tuple[int, int]) -> Tile:
    """Create a difficult terrain tile (walking costs 2x movement)."""
    tile = Tile.create(position, walkable=True, visible=True, name="Difficult Terrain", sprite_name="rough.png")

    # Add +1 to walking cost (total = 2, difficult terrain)
    tile.walking_cost.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=tile.uuid,
            name="Difficult Terrain",
            value=1
        )
    )

    return tile
