"""
Tile system for the D&D engine.

Tile is a BaseBlock that represents a single cell on the game grid.
As a BaseBlock, tiles can have conditions attached (fire, traps, difficult terrain).

GridMap handles all spatial computation (FOV, pathfinding).
Tiles are stored in GridMap and provide the data/state for each cell.
"""

import math
from typing import Dict, Optional, Tuple
from uuid import UUID, uuid4
from pydantic import Field, PrivateAttr
from dnd.core.base_block import BaseBlock, MovementMode, LightLevel, SensesType
from dnd.core.values import ModifiableValue
from dnd.core.modifiers import NumericalModifier
from dnd.core.events import SpatialChangeEvent, EventQueue, EventPhase


# =========================================================================
# Darkvision shift map (explicit, NOT arithmetic)
# =========================================================================

_DARKVISION_SHIFT: Dict[LightLevel, LightLevel] = {
    LightLevel.DARKNESS: LightLevel.DIM_LIGHT,
    LightLevel.DIM_LIGHT: LightLevel.BRIGHT_LIGHT,
}


# =========================================================================
# Helpers
# =========================================================================

def _tile_distance_feet(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    """Euclidean distance between two tile positions, in feet (1 tile = 5ft)."""
    return int(math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)) * 5


# =========================================================================
# Tile
# =========================================================================

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

    Lighting:
    - default_light: base light level (BRIGHT_LIGHT for outdoors, DARKNESS for dungeons)
    - _illuminations: light sources brightening this tile (torch, Light spell)
    - _obscurements: darkness effects dimming this tile (Fog Cloud, Darkness spell)
    - resolved_light_level: objective result = MAX(default, illuminations) then MIN(result, obscurements)
    - get_effective_light_for(observer_uuid): subjective light considering darkvision, truesight, etc.
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

    # Lighting
    default_light: LightLevel = Field(default=LightLevel.BRIGHT_LIGHT,
                                      description="Base light level for this tile")
    _illuminations: Dict[UUID, LightLevel] = PrivateAttr(default_factory=dict)
    _obscurements: Dict[UUID, LightLevel] = PrivateAttr(default_factory=dict)

    # =========================================================================
    # Movement
    # =========================================================================

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
        """A tile blocks vision if it is not visible (e.g., walls).
        Magical darkness also blocks vision unless observer can pierce it."""
        if not self.visible:
            return True  # Wall
        # Magical darkness blocks vision unless observer can pierce it
        if self.resolved_light_level == LightLevel.MAGICAL_DARKNESS:
            if requesting_entity_uuid is None:
                return True
            observer = BaseBlock.get(requesting_entity_uuid)
            return observer is None or not observer.can_pierce_magical_darkness()
        return False

    # =========================================================================
    # Lighting
    # =========================================================================

    def add_illumination(self, source_uuid: UUID, level: LightLevel,
                         fire_event: bool = True) -> bool:
        """Add a light source (torch, Light spell).
        Returns True if resolved light level changed.
        Fires SPATIAL_LIGHT_CHANGED event if fire_event=True and level changed."""
        old = self.resolved_light_level
        self._illuminations[source_uuid] = level
        changed = self.resolved_light_level != old
        if changed and fire_event:
            self._notify_light_changed()
        return changed

    def add_obscurement(self, source_uuid: UUID, level: LightLevel,
                        fire_event: bool = True) -> bool:
        """Add darkness/fog effect.
        Returns True if resolved light level changed.
        Fires SPATIAL_LIGHT_CHANGED event if fire_event=True and level changed."""
        old = self.resolved_light_level
        self._obscurements[source_uuid] = level
        changed = self.resolved_light_level != old
        if changed and fire_event:
            self._notify_light_changed()
        return changed

    def remove_light_modifier(self, source_uuid: UUID,
                              fire_event: bool = True) -> bool:
        """Remove any modifier by UUID (from either dict).
        Returns True if resolved light level changed.
        Fires SPATIAL_LIGHT_CHANGED event if fire_event=True and level changed."""
        old = self.resolved_light_level
        self._illuminations.pop(source_uuid, None)
        self._obscurements.pop(source_uuid, None)
        changed = self.resolved_light_level != old
        if changed and fire_event:
            self._notify_light_changed()
        return changed

    @property
    def resolved_light_level(self) -> LightLevel:
        """Objective light level (no observer). Lights brighten, darkness overrides."""
        brightest = self.default_light
        for level in self._illuminations.values():
            if level.value > brightest.value:
                brightest = level
        if not self._obscurements:
            return brightest
        darkest = min(self._obscurements.values(), key=lambda x: x.value)
        return LightLevel(min(brightest.value, darkest.value))

    def get_effective_light_for(
        self,
        observer_uuid: Optional[UUID] = None,
        observer_position: Optional[Tuple[int, int]] = None,
    ) -> LightLevel:
        """Subjective light level seen by a specific observer.
        Resolves from observer's sense_modes (darkvision, truesight, etc.)."""
        base = self.resolved_light_level
        if observer_uuid is None:
            return base

        observer = BaseBlock.get(observer_uuid)
        if observer is None:
            return base

        sense_modes: list = observer.get_sense_modes()
        if not sense_modes:
            return self._apply_adjacent_rule(base, observer_position)

        # Truesight/Blindsight: see through everything
        for sm in sense_modes:
            if sm.sense_type in (SensesType.TRUESIGHT, SensesType.BLINDSIGHT):
                in_range = (sm.range_feet == 0)
                if not in_range and observer_position is not None and self.position is not None:
                    in_range = _tile_distance_feet(self.position, observer_position) <= sm.range_feet
                if in_range:
                    return max(base, LightLevel.BRIGHT_LIGHT)

        # Devil's Sight: see normally in all darkness (magical and nonmagical) within range
        # SRD: "You can see normally in darkness, both magical and nonmagical, to a distance of 120 feet."
        if base in (LightLevel.MAGICAL_DARKNESS, LightLevel.DARKNESS):
            for sm in sense_modes:
                if sm.sense_type == SensesType.DEVILS_SIGHT:
                    in_range = (sm.range_feet == 0)
                    if not in_range and observer_position is not None and self.position is not None:
                        in_range = _tile_distance_feet(self.position, observer_position) <= sm.range_feet
                    if in_range:
                        base = LightLevel.BRIGHT_LIGHT
                    break

        # Darkvision: explicit upgrade within range (NOT magical darkness)
        if base in _DARKVISION_SHIFT:
            for sm in sense_modes:
                if sm.sense_type == SensesType.DARKVISION:
                    in_range = (sm.range_feet == 0)
                    if not in_range and observer_position is not None and self.position is not None:
                        in_range = _tile_distance_feet(self.position, observer_position) <= sm.range_feet
                    if in_range:
                        base = _DARKVISION_SHIFT[base]
                    break

        # Adjacent cell rule (LAST): minimum DIM_LIGHT at distance <= 1
        return self._apply_adjacent_rule(base, observer_position)

    def _apply_adjacent_rule(self, level: LightLevel,
                             observer_position: Optional[Tuple[int, int]]) -> LightLevel:
        """Minimum DIM_LIGHT at distance <= 1 from observer.
        Only applies to natural DARKNESS, NOT magical darkness."""
        if observer_position is not None and self.position is not None:
            dx = abs(self.position[0] - observer_position[0])
            dy = abs(self.position[1] - observer_position[1])
            if max(dx, dy) <= 1 and level == LightLevel.DARKNESS:
                return LightLevel.DIM_LIGHT
        return level

    def _notify_light_changed(self, parent_event: Optional[UUID] = None) -> None:
        """Fire a SPATIAL_LIGHT_CHANGED event at this tile's position.
        Same pattern as BaseBlock._notify_perceivability_changed()."""
        event = SpatialChangeEvent.light_changed(self.position, self.uuid, parent_event=parent_event)
        current = EventQueue.register(event)
        if current.canceled:
            return
        current = current.phase_to(EventPhase.EXECUTION)
        current = EventQueue.register(current)
        if current.canceled:
            return
        current = current.phase_to(EventPhase.EFFECT)
        current = EventQueue.register(current)
        if current.canceled:
            return
        current = current.phase_to(EventPhase.COMPLETION)
        EventQueue.register(current)

    # =========================================================================
    # Borders
    # =========================================================================

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

    # =========================================================================
    # Factory
    # =========================================================================

    @classmethod
    def create(cls, position: Tuple[int, int],
               walkable: bool = True,
               visible: bool = True,
               name: str = "Floor",
               sprite_name: Optional[str] = None,
               height: int = 0,
               default_light: LightLevel = LightLevel.BRIGHT_LIGHT) -> 'Tile':
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
            height=height,
            default_light=default_light
        )


# =========================================================================
# Factory functions for common tile types
# =========================================================================

def floor_factory(position: Tuple[int, int]) -> Tile:
    """Create a floor tile (bright light, outdoor default)."""
    return Tile.create(position, walkable=True, visible=True, name="Floor", sprite_name="floor.png")


def dark_floor_factory(position: Tuple[int, int]) -> Tile:
    """Create a dark floor tile (darkness, dungeon default)."""
    return Tile.create(position, walkable=True, visible=True, name="Floor", sprite_name="floor.png",
                       default_light=LightLevel.DARKNESS)


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
