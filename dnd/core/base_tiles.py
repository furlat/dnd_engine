"""Tile primitives for terrain, lighting, and directional borders."""

from typing import Dict, Optional, Tuple
from uuid import UUID, uuid4
from pydantic import Field, PrivateAttr
from dnd.core.base_block import BaseBlock, MovementMode, LightLevel, SensesType
from dnd.core.values import ModifiableValue
from dnd.core.modifiers import NumericalModifier
from dnd.core.events import SpatialChangeEvent, EventQueue
from dnd.core.geometry import grid_distance_feet

_DARKVISION_SHIFT: Dict[LightLevel, LightLevel] = {
    LightLevel.DARKNESS: LightLevel.DIM_LIGHT,
    LightLevel.DIM_LIGHT: LightLevel.BRIGHT_LIGHT,
}


class Tile(BaseBlock):
    """Single grid cell stored by `GridMap`.

    Tiles inherit condition and event-handler support from `BaseBlock`. They
    carry movement-mode costs, per-channel directional borders, elevation, and
    objective lighting state; `GridMap` owns spatial queries and pathfinding.
    """

    name: str = Field(default="Floor", description="The name of the tile")
    walkable: bool = Field(default=True, description="Whether the tile can be walked on (legacy, use walking_cost)")
    visible: bool = Field(default=True, description="Whether the tile can be seen through")
    sprite_name: Optional[str] = Field(default=None, description="The name of the sprite to use for the tile")
    allow_events_conditions: bool = Field(default=True, description="Tiles can have conditions")

    walking_cost: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=1,
            value_name="Walking Cost"
        ),
        description="Walking movement cost; 1 is normal, 2 is difficult terrain, and 0 is impassable.",
    )
    flying_cost: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=1,
            value_name="Flying Cost"
        ),
        description="Flying movement cost for this tile.",
    )
    swimming_cost: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=0,
            value_name="Swimming Cost"
        ),
        description="Swimming movement cost for this tile.",
    )
    burrowing_cost: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=0,
            value_name="Burrowing Cost"
        ),
        description="Burrowing movement cost for this tile.",
    )

    border_north: bool = Field(default=True, description="Can enter from north (y+1)")
    border_south: bool = Field(default=True, description="Can enter from south (y-1)")
    border_east: bool = Field(default=True, description="Can enter from east (x+1)")
    border_west: bool = Field(default=True, description="Can enter from west (x-1)")
    vision_border_north: bool = Field(default=True, description="Vision can cross north")
    vision_border_south: bool = Field(default=True, description="Vision can cross south")
    vision_border_east: bool = Field(default=True, description="Vision can cross east")
    vision_border_west: bool = Field(default=True, description="Vision can cross west")
    light_border_north: bool = Field(default=True, description="Light can cross north")
    light_border_south: bool = Field(default=True, description="Light can cross south")
    light_border_east: bool = Field(default=True, description="Light can cross east")
    light_border_west: bool = Field(default=True, description="Light can cross west")
    propagation_border_north: bool = Field(default=True, description="Physical propagation can cross north")
    propagation_border_south: bool = Field(default=True, description="Physical propagation can cross south")
    propagation_border_east: bool = Field(default=True, description="Physical propagation can cross east")
    propagation_border_west: bool = Field(default=True, description="Physical propagation can cross west")
    object_movement_border_north: bool = Field(default=True, description="Object-derived movement contribution north")
    object_movement_border_south: bool = Field(default=True, description="Object-derived movement contribution south")
    object_movement_border_east: bool = Field(default=True, description="Object-derived movement contribution east")
    object_movement_border_west: bool = Field(default=True, description="Object-derived movement contribution west")
    object_vision_border_north: bool = Field(default=True, description="Object-derived vision contribution north")
    object_vision_border_south: bool = Field(default=True, description="Object-derived vision contribution south")
    object_vision_border_east: bool = Field(default=True, description="Object-derived vision contribution east")
    object_vision_border_west: bool = Field(default=True, description="Object-derived vision contribution west")
    object_light_border_north: bool = Field(default=True, description="Object-derived light contribution north")
    object_light_border_south: bool = Field(default=True, description="Object-derived light contribution south")
    object_light_border_east: bool = Field(default=True, description="Object-derived light contribution east")
    object_light_border_west: bool = Field(default=True, description="Object-derived light contribution west")
    object_propagation_border_north: bool = Field(default=True, description="Object-derived propagation contribution north")
    object_propagation_border_south: bool = Field(default=True, description="Object-derived propagation contribution south")
    object_propagation_border_east: bool = Field(default=True, description="Object-derived propagation contribution east")
    object_propagation_border_west: bool = Field(default=True, description="Object-derived propagation contribution west")

    height: int = Field(default=0, description="Tile elevation in 5ft increments")
    default_light: LightLevel = Field(
        default=LightLevel.BRIGHT_LIGHT,
        description="Base objective light level before illumination or obscurement modifiers.",
    )
    _illuminations: Dict[UUID, LightLevel] = PrivateAttr(default_factory=dict)
    _obscurements: Dict[UUID, LightLevel] = PrivateAttr(default_factory=dict)

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
        """Return whether this tile blocks vision for an optional observer."""
        if not self.visible:
            return True
        if self.resolved_light_level == LightLevel.MAGICAL_DARKNESS:
            if requesting_entity_uuid is None:
                return True
            observer = BaseBlock.get(requesting_entity_uuid)
            return observer is None or not observer.can_pierce_magical_darkness()
        return False

    def add_illumination(self, source_uuid: UUID, level: LightLevel,
                         fire_event: bool = True) -> bool:
        """Add illumination and optionally notify when resolved light changes."""
        old = self.resolved_light_level
        self._illuminations[source_uuid] = level
        changed = self.resolved_light_level != old
        if changed and fire_event:
            self._notify_light_changed()
        return changed

    def add_obscurement(self, source_uuid: UUID, level: LightLevel,
                        fire_event: bool = True) -> bool:
        """Add obscurement and optionally notify when resolved light changes."""
        old = self.resolved_light_level
        self._obscurements[source_uuid] = level
        changed = self.resolved_light_level != old
        if changed and fire_event:
            self._notify_light_changed()
        return changed

    def remove_light_modifier(self, source_uuid: UUID,
                              fire_event: bool = True) -> bool:
        """Remove any light modifier by UUID from illumination or obscurement."""
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
        """Resolve subjective light for an observer's sense modes."""
        base = self.resolved_light_level
        if observer_uuid is None:
            return base

        observer = BaseBlock.get(observer_uuid)
        if observer is None:
            return base

        sense_modes: list = observer.get_sense_modes()
        if not sense_modes:
            return self._apply_adjacent_rule(base, observer_position)

        for sm in sense_modes:
            if sm.sense_type in (SensesType.TRUESIGHT, SensesType.BLINDSIGHT):
                in_range = (sm.range_feet == 0)
                if not in_range and observer_position is not None and self.position is not None:
                    in_range = grid_distance_feet(self.position, observer_position) <= sm.range_feet
                if in_range:
                    return max(base, LightLevel.BRIGHT_LIGHT)

        if base in (LightLevel.MAGICAL_DARKNESS, LightLevel.DARKNESS):
            for sm in sense_modes:
                if sm.sense_type == SensesType.DEVILS_SIGHT:
                    in_range = (sm.range_feet == 0)
                    if not in_range and observer_position is not None and self.position is not None:
                        in_range = grid_distance_feet(self.position, observer_position) <= sm.range_feet
                    if in_range:
                        base = LightLevel.BRIGHT_LIGHT
                    break

        if base in _DARKVISION_SHIFT:
            for sm in sense_modes:
                if sm.sense_type == SensesType.DARKVISION:
                    in_range = (sm.range_feet == 0)
                    if not in_range and observer_position is not None and self.position is not None:
                        in_range = grid_distance_feet(self.position, observer_position) <= sm.range_feet
                    if in_range:
                        base = _DARKVISION_SHIFT[base]
                    break

        return self._apply_adjacent_rule(base, observer_position)

    def _apply_adjacent_rule(self, level: LightLevel,
                             observer_position: Optional[Tuple[int, int]]) -> LightLevel:
        """Apply the adjacent-cell minimum DIM_LIGHT rule for natural darkness."""
        if observer_position is not None and self.position is not None:
            dx = abs(self.position[0] - observer_position[0])
            dy = abs(self.position[1] - observer_position[1])
            if max(dx, dy) <= 1 and level == LightLevel.DARKNESS:
                return LightLevel.DIM_LIGHT
        return level

    def _notify_light_changed(self, parent_event: Optional[UUID] = None) -> None:
        """Fire a full SPATIAL_LIGHT_CHANGED lifecycle at this tile."""
        event = SpatialChangeEvent.light_changed(self.position, self.uuid, parent_event=parent_event,
                                                       new_light_level=self.resolved_light_level.value)
        EventQueue.publish_lifecycle(event)

    def directions_toward(self, other_position: Tuple[int, int]) -> Tuple[str, ...]:
        """Return tile-relative cardinal directions touched by a transition."""
        if self.position is None:
            return ()

        dx = other_position[0] - self.position[0]
        dy = other_position[1] - self.position[1]
        directions = []
        if dx > 0:
            directions.append("east")
        elif dx < 0:
            directions.append("west")
        if dy > 0:
            directions.append("north")
        elif dy < 0:
            directions.append("south")
        return tuple(directions)

    def _intrinsic_border(self, direction: str, channel: str) -> bool:
        if channel == "movement":
            if direction == "north":
                return self.border_north
            if direction == "south":
                return self.border_south
            if direction == "east":
                return self.border_east
            if direction == "west":
                return self.border_west
        elif channel == "vision":
            if direction == "north":
                return self.vision_border_north
            if direction == "south":
                return self.vision_border_south
            if direction == "east":
                return self.vision_border_east
            if direction == "west":
                return self.vision_border_west
        elif channel == "light":
            if direction == "north":
                return self.light_border_north
            if direction == "south":
                return self.light_border_south
            if direction == "east":
                return self.light_border_east
            if direction == "west":
                return self.light_border_west
        elif channel == "propagation":
            if direction == "north":
                return self.propagation_border_north
            if direction == "south":
                return self.propagation_border_south
            if direction == "east":
                return self.propagation_border_east
            if direction == "west":
                return self.propagation_border_west
        return True

    def _derived_border(self, direction: str, channel: str) -> bool:
        if channel == "movement":
            if direction == "north":
                return self.object_movement_border_north
            if direction == "south":
                return self.object_movement_border_south
            if direction == "east":
                return self.object_movement_border_east
            if direction == "west":
                return self.object_movement_border_west
        elif channel == "vision":
            if direction == "north":
                return self.object_vision_border_north
            if direction == "south":
                return self.object_vision_border_south
            if direction == "east":
                return self.object_vision_border_east
            if direction == "west":
                return self.object_vision_border_west
        elif channel == "light":
            if direction == "north":
                return self.object_light_border_north
            if direction == "south":
                return self.object_light_border_south
            if direction == "east":
                return self.object_light_border_east
            if direction == "west":
                return self.object_light_border_west
        elif channel == "propagation":
            if direction == "north":
                return self.object_propagation_border_north
            if direction == "south":
                return self.object_propagation_border_south
            if direction == "east":
                return self.object_propagation_border_east
            if direction == "west":
                return self.object_propagation_border_west
        return True

    def set_intrinsic_border(self, channel: str, direction: str, passable: bool) -> bool:
        """Set a tile-authored directional border. Returns True if changed."""
        old_value = self._intrinsic_border(direction, channel)
        if old_value == passable:
            return False
        if channel == "movement":
            if direction == "north":
                self.border_north = passable
            elif direction == "south":
                self.border_south = passable
            elif direction == "east":
                self.border_east = passable
            elif direction == "west":
                self.border_west = passable
            else:
                return False
        elif channel == "vision":
            if direction == "north":
                self.vision_border_north = passable
            elif direction == "south":
                self.vision_border_south = passable
            elif direction == "east":
                self.vision_border_east = passable
            elif direction == "west":
                self.vision_border_west = passable
            else:
                return False
        elif channel == "light":
            if direction == "north":
                self.light_border_north = passable
            elif direction == "south":
                self.light_border_south = passable
            elif direction == "east":
                self.light_border_east = passable
            elif direction == "west":
                self.light_border_west = passable
            else:
                return False
        elif channel == "propagation":
            if direction == "north":
                self.propagation_border_north = passable
            elif direction == "south":
                self.propagation_border_south = passable
            elif direction == "east":
                self.propagation_border_east = passable
            elif direction == "west":
                self.propagation_border_west = passable
            else:
                return False
        else:
            return False
        return True

    def set_object_border(self, channel: str, direction: str, passable: bool) -> bool:
        """Set object/entity-derived directional border state. Returns True if changed."""
        old_value = self._derived_border(direction, channel)
        if old_value == passable:
            return False
        if channel == "movement":
            if direction == "north":
                self.object_movement_border_north = passable
            elif direction == "south":
                self.object_movement_border_south = passable
            elif direction == "east":
                self.object_movement_border_east = passable
            elif direction == "west":
                self.object_movement_border_west = passable
            else:
                return False
        elif channel == "vision":
            if direction == "north":
                self.object_vision_border_north = passable
            elif direction == "south":
                self.object_vision_border_south = passable
            elif direction == "east":
                self.object_vision_border_east = passable
            elif direction == "west":
                self.object_vision_border_west = passable
            else:
                return False
        elif channel == "light":
            if direction == "north":
                self.object_light_border_north = passable
            elif direction == "south":
                self.object_light_border_south = passable
            elif direction == "east":
                self.object_light_border_east = passable
            elif direction == "west":
                self.object_light_border_west = passable
            else:
                return False
        elif channel == "propagation":
            if direction == "north":
                self.object_propagation_border_north = passable
            elif direction == "south":
                self.object_propagation_border_south = passable
            elif direction == "east":
                self.object_propagation_border_east = passable
            elif direction == "west":
                self.object_propagation_border_west = passable
            else:
                return False
        else:
            return False
        return True

    def allows_direction(self, direction: str, channel: str = "movement",
                         include_derived: bool = True) -> bool:
        """Check one tile-relative direction for a channel."""
        if direction not in {"north", "south", "east", "west"}:
            return True
        if not self._intrinsic_border(direction, channel):
            return False
        if include_derived and not self._derived_border(direction, channel):
            return False
        return True

    def allows_directions(self, directions: Tuple[str, ...], channel: str = "movement",
                          include_derived: bool = True) -> bool:
        """Check orthogonal or diagonal directional crossing."""
        if not directions:
            return True
        return all(self.allows_direction(direction, channel, include_derived) for direction in directions)

    @classmethod
    def create(cls, position: Tuple[int, int],
               walkable: bool = True,
               visible: bool = True,
               name: str = "Floor",
               sprite_name: Optional[str] = None,
               height: int = 0,
               default_light: LightLevel = LightLevel.BRIGHT_LIGHT) -> 'Tile':
        """Create a tile with movement-mode `ModifiableValue` costs."""
        tile_uuid = uuid4()

        walking_cost = ModifiableValue.create(
            source_entity_uuid=tile_uuid,
            base_value=1 if walkable else 0,
            value_name="Walking Cost"
        )
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
        burrowing_cost.self_static.add_max_constraint(
            NumericalModifier.create(
                source_entity_uuid=tile_uuid,
                name="No Earth",
                value=0
            )
        )

        return cls(
            uuid=tile_uuid,
            source_entity_uuid=tile_uuid,
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

    for mod_uuid in list(tile.swimming_cost.self_static.max_constraints.keys()):
        tile.swimming_cost.self_static.remove_max_constraint(mod_uuid)

    tile.swimming_cost = ModifiableValue.create(
        source_entity_uuid=tile.uuid,
        base_value=1,
        value_name="Swimming Cost"
    )

    return tile


def difficult_terrain_factory(position: Tuple[int, int]) -> Tile:
    """Create a difficult terrain tile (walking costs 2x movement)."""
    tile = Tile.create(position, walkable=True, visible=True, name="Difficult Terrain", sprite_name="rough.png")

    tile.walking_cost.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=tile.uuid,
            name="Difficult Terrain",
            value=1
        )
    )

    return tile
