"""Tile primitives for terrain, lighting, and movement."""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from uuid import UUID, uuid4
from pydantic import Field, PrivateAttr, StrictInt, model_validator
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.types.world import CardinalDirection, MovementMode, LightLevel
from dnd.types.spatial_effects import SpatialEffectLayer
from dnd.types.materials import Material, TileSurface
from dnd.core.values import ModifiableValue
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis


def validate_elevation_surface_tuple(
    height: int,
    surface_kind: ElevationSurfaceKind,
    slope_axis: Optional[SlopeAxis],
) -> None:
    """Validate one exact stored support tuple without creating a Tile."""
    if type(height) is not int:
        raise TypeError("tile height must be an exact integer number of steps")
    if type(surface_kind) is not ElevationSurfaceKind:
        raise TypeError("surface_kind must be an ElevationSurfaceKind")
    if slope_axis is not None and type(slope_axis) is not SlopeAxis:
        raise TypeError("slope_axis must be a SlopeAxis or None")
    if surface_kind is ElevationSurfaceKind.ORDINARY:
        if slope_axis is not None:
            raise ValueError("ordinary elevation surfaces cannot define a slope axis")
    elif slope_axis is None:
        raise ValueError("stairs and ramps require a slope axis")


@dataclass(frozen=True, slots=True)
class TileObjectBand:
    """Immutable occupancy snapshot for one vertical Tile band."""

    object_uuids: frozenset[UUID] = frozenset()
    occupant_uuid: Optional[UUID] = None


def _empty_boundary_object_bands() -> Dict[
    CardinalDirection,
    Dict[int, TileObjectBand],
]:
    """Create all four private boundary-band buckets for one Tile."""
    return {direction: {} for direction in CardinalDirection}


class Tile(BaseBlock):
    """Single grid cell stored by `GridMap`.

    Tiles inherit condition and event-handler support from `BaseBlock`. They
    carry movement-mode costs, elevation, and objective lighting state;
    `GridMap` owns spatial queries and pathfinding.
    """

    name: str = Field(default="Floor", description="The name of the tile")
    position: Tuple[StrictInt, StrictInt] = Field(
        default=(0, 0),
        description="Strict objective coordinate owned by this Tile.",
    )
    surface: TileSurface = Field(description="Validated semantic support surface.")
    blocks_optics: bool = Field(
        default=False,
        description="Whether the Tile intrinsically blocks ordinary XY optics.",
    )
    blocks_propagation_field: bool = Field(
        default=False,
        description="Whether the Tile intrinsically blocks physical propagation.",
    )
    allow_events_conditions: bool = Field(default=True, description="Tiles can have conditions")

    def get_position(self) -> Tuple[StrictInt, StrictInt]:
        """Return this Tile's strict objective coordinate."""
        return self.position

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


    height: StrictInt = Field(default=0, description="Support elevation in five-foot steps.")
    elevation_surface_kind: ElevationSurfaceKind = Field(
        default=ElevationSurfaceKind.ORDINARY,
        description="Authored support-surface kind governing progressive elevation.",
    )
    slope_axis: Optional[SlopeAxis] = Field(
        default=None,
        description="Cardinal axis of stairs or ramp; absent for ordinary support.",
    )
    default_light: LightLevel = Field(
        default=LightLevel.BRIGHT_LIGHT,
        description="Base objective light level before illumination or obscurement modifiers.",
    )
    _illuminations: Dict[UUID, LightLevel] = PrivateAttr(default_factory=dict)
    _illumination_caps: Dict[UUID, LightLevel] = PrivateAttr(default_factory=dict)
    _entity_uuids: set[UUID] = PrivateAttr(default_factory=set)
    _spatial_condition_uuids: Dict[
        SpatialEffectLayer,
        set[UUID],
    ] = PrivateAttr(default_factory=dict)
    _center_object_bands: Dict[int, TileObjectBand] = PrivateAttr(default_factory=dict)
    _boundary_object_bands: Dict[
        CardinalDirection,
        Dict[int, TileObjectBand],
    ] = PrivateAttr(default_factory=_empty_boundary_object_bands)

    @model_validator(mode="after")
    def validate_elevation_surface(self) -> "Tile":
        """Keep every stored elevation tuple internally coherent."""
        validate_elevation_surface_tuple(
            self.height,
            self.elevation_surface_kind,
            self.slope_axis,
        )
        return self

    def get_movement_cost(self, mode: MovementMode) -> int:
        """Get the movement cost for a specific mode."""
        cost_map = {
            MovementMode.WALKING: self.walking_cost,
            MovementMode.FLYING: self.flying_cost,
            MovementMode.SWIMMING: self.swimming_cost,
            MovementMode.BURROWING: self.burrowing_cost,
        }
        return cost_map[mode].normalized_score

    def add_spatial_condition_reference(
        self,
        condition_uuid: UUID,
        layer: SpatialEffectLayer,
    ) -> None:
        """Index one independently owned condition affecting this Tile."""
        self._spatial_condition_uuids.setdefault(layer, set()).add(
            condition_uuid,
        )

    def remove_spatial_condition_reference(
        self,
        condition_uuid: UUID,
        layer: SpatialEffectLayer,
    ) -> None:
        """Remove one independently owned condition reference from this Tile."""
        condition_uuids = self._spatial_condition_uuids.get(layer)
        if condition_uuids is None:
            return
        condition_uuids.discard(condition_uuid)
        if not condition_uuids:
            del self._spatial_condition_uuids[layer]

    def get_spatial_condition_uuids(
        self,
        layer: Optional[SpatialEffectLayer] = None,
    ) -> set[UUID]:
        """Return independently owned condition UUIDs affecting this Tile."""
        if layer is not None:
            return set(self._spatial_condition_uuids.get(layer, set()))
        return {
            condition_uuid
            for condition_uuids in self._spatial_condition_uuids.values()
            for condition_uuid in condition_uuids
        }

    def get_conditions(self) -> Dict[UUID, BaseCondition]:
        """Return every direct or spatial condition affecting this Tile."""
        conditions = dict(self.active_conditions_by_uuid)
        for condition_uuid in self.get_spatial_condition_uuids():
            condition = BaseCondition.get(condition_uuid)
            if not isinstance(condition, BaseCondition):
                raise RuntimeError(
                    "Tile spatial-condition index references a missing "
                    f"condition {condition_uuid}",
                )
            if not condition.is_active_spatial_condition():
                raise RuntimeError(
                    "Tile spatial-condition index references an inactive "
                    f"condition {condition_uuid}",
                )
            conditions[condition_uuid] = condition
        return conditions

    def get_entity_uuids(self) -> set[UUID]:
        """Return a defensive snapshot of the Tile's entity membership."""
        return set(self._entity_uuids)

    def _replace_entity_uuids(self, entity_uuids: set[UUID]) -> None:
        """Replace complete entity membership; called only by GridMap."""
        self._entity_uuids = set(entity_uuids)

    def get_center_object_bands(self) -> Tuple[Tuple[int, TileObjectBand], ...]:
        """Return immutable center-band snapshots ordered by height."""
        return tuple(sorted(self._center_object_bands.items()))

    def get_boundary_object_bands(
        self,
        direction: CardinalDirection,
    ) -> Tuple[Tuple[int, TileObjectBand], ...]:
        """Return immutable boundary-band snapshots ordered by height."""
        return tuple(sorted(self._boundary_object_bands.get(direction, {}).items()))

    def _replace_center_object_band(
        self,
        height: int,
        band: Optional[TileObjectBand],
    ) -> None:
        """Replace one complete center band; owned by GridMap placement commits."""
        if band is None:
            self._center_object_bands.pop(height, None)
        else:
            self._center_object_bands[height] = band

    def _replace_boundary_object_band(
        self,
        direction: CardinalDirection,
        height: int,
        band: Optional[TileObjectBand],
    ) -> None:
        """Replace one complete boundary band; owned by GridMap placement commits."""
        direction_bands = self._boundary_object_bands.setdefault(direction, {})
        if band is None:
            direction_bands.pop(height, None)
        else:
            direction_bands[height] = band

    def blocks_walking(self, requesting_entity_uuid: Optional['UUID'] = None,
                       mode: MovementMode = MovementMode.WALKING) -> bool:
        """A tile blocks walking if its movement cost for the given mode is 0 or less."""
        return self.get_movement_cost(mode) <= 0

    def blocks_propagation(self) -> bool:
        """Return the Tile's intrinsic physical-propagation policy."""
        return self.blocks_propagation_field

    def _add_illumination(self, source_uuid: UUID, level: LightLevel) -> bool:
        """Install one GridMap-owned objective illumination contribution."""
        old = self.resolved_light_level
        self._illuminations[source_uuid] = level
        return self.resolved_light_level != old

    def _add_illumination_cap(self, source_uuid: UUID, level: LightLevel) -> bool:
        """Install one GridMap-owned source cap on objective illumination."""
        old = self.resolved_light_level
        self._illumination_caps[source_uuid] = level
        return self.resolved_light_level != old

    def _remove_light_modifier(self, source_uuid: UUID) -> bool:
        """Remove one GridMap-owned illumination contribution or cap."""
        old = self.resolved_light_level
        self._illuminations.pop(source_uuid, None)
        self._illumination_caps.pop(source_uuid, None)
        return self.resolved_light_level != old

    @property
    def resolved_light_level(self) -> LightLevel:
        """Objective light level (no observer). Lights brighten, darkness overrides."""
        brightest = self.default_light
        for level in self._illuminations.values():
            if level.value > brightest.value:
                brightest = level
        if not self._illumination_caps:
            return brightest
        darkest = min(self._illumination_caps.values(), key=lambda x: x.value)
        return LightLevel(min(brightest.value, darkest.value))

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

    @classmethod
    def create(cls, position: Tuple[int, int],
               *,
               surface: TileSurface,
               walking_cost: int = 1,
               flying_cost: int = 1,
               swimming_cost: int = 0,
               burrowing_cost: int = 0,
               blocks_optics: bool = False,
               blocks_propagation: bool = False,
               name: str = "Floor",
               height: int = 0,
               elevation_surface_kind: ElevationSurfaceKind = ElevationSurfaceKind.ORDINARY,
               slope_axis: Optional[SlopeAxis] = None,
               default_light: LightLevel = LightLevel.BRIGHT_LIGHT) -> 'Tile':
        """Create a tile with movement-mode `ModifiableValue` costs."""
        costs = {
            "walking_cost": walking_cost,
            "flying_cost": flying_cost,
            "swimming_cost": swimming_cost,
            "burrowing_cost": burrowing_cost,
        }
        for cost_name, cost in costs.items():
            if type(cost) is not int or cost < 0:
                raise ValueError(
                    f"{cost_name} must be a nonnegative strict integer",
                )

        tile_uuid = uuid4()

        walking_cost = ModifiableValue.create(
            source_entity_uuid=tile_uuid,
            base_value=costs["walking_cost"],
            value_name="Walking Cost"
        )

        flying_cost = ModifiableValue.create(
            source_entity_uuid=tile_uuid,
            base_value=costs["flying_cost"],
            value_name="Flying Cost"
        )

        swimming_cost = ModifiableValue.create(
            source_entity_uuid=tile_uuid,
            base_value=costs["swimming_cost"],
            value_name="Swimming Cost"
        )

        burrowing_cost = ModifiableValue.create(
            source_entity_uuid=tile_uuid,
            base_value=costs["burrowing_cost"],
            value_name="Burrowing Cost"
        )

        return cls(
            uuid=tile_uuid,
            source_entity_uuid=tile_uuid,
            position=position,
            surface=surface,
            blocks_optics=blocks_optics,
            blocks_propagation_field=blocks_propagation,
            name=name,
            walking_cost=walking_cost,
            flying_cost=flying_cost,
            swimming_cost=swimming_cost,
            burrowing_cost=burrowing_cost,
            height=height,
            elevation_surface_kind=elevation_surface_kind,
            slope_axis=slope_axis,
            default_light=default_light
        )


def floor_factory(position: Tuple[int, int]) -> Tile:
    """Create a floor tile (bright light, outdoor default)."""
    return Tile.create(
        position,
        surface=TileSurface(base_material=Material.STONE),
        name="Floor",
    )


def dark_floor_factory(position: Tuple[int, int]) -> Tile:
    """Create a dark floor tile (darkness, dungeon default)."""
    return Tile.create(
        position,
        surface=TileSurface(base_material=Material.STONE),
        name="Floor",
        default_light=LightLevel.DARKNESS,
    )


def wall_factory(position: Tuple[int, int]) -> Tile:
    """Create a wall tile."""
    tile = Tile.create(
        position,
        surface=TileSurface(base_material=Material.STONE),
        walking_cost=0,
        flying_cost=0,
        swimming_cost=0,
        burrowing_cost=0,
        blocks_optics=True,
        blocks_propagation=True,
        name="Wall",
    )
    return tile


def water_factory(position: Tuple[int, int]) -> Tile:
    """Create a water tile (can't walk, can see through, can swim)."""
    tile = Tile.create(
        position,
        surface=TileSurface(base_material=Material.WATER),
        walking_cost=0,
        flying_cost=1,
        swimming_cost=1,
        burrowing_cost=0,
        name="Water",
    )

    return tile


def difficult_terrain_factory(
    position: Tuple[int, int],
    *,
    height: int = 0,
    elevation_surface_kind: ElevationSurfaceKind = ElevationSurfaceKind.ORDINARY,
    slope_axis: Optional[SlopeAxis] = None,
) -> Tile:
    """Create a difficult terrain tile (walking costs 2x movement)."""
    tile = Tile.create(
        position,
        surface=TileSurface(base_material=Material.EARTH),
        walking_cost=2,
        name="Difficult Terrain",
        height=height,
        elevation_surface_kind=elevation_surface_kind,
        slope_axis=slope_axis,
    )

    return tile
