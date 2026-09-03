"""Tile primitives for terrain, lighting, elevation, and object bands."""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from uuid import UUID, uuid4
from pydantic import Field, PrivateAttr, StrictInt, model_validator
from dnd.core.base_block import BaseBlock, MovementMode, LightLevel
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_object import BaseObject
from dnd.core.values import BaseValue, ModifiableValue
from dnd.core.modifiers import NumericalModifier
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.types.materials import Material, TileSurface
from dnd.types.world import CardinalDirection
from dnd.types.spatial_effects import SpatialEffectLayer

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
            raise ValueError(
                "ordinary elevation surfaces cannot define a slope axis"
            )
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
    carry movement-mode costs, intrinsic optical/propagation policy, elevation, and
    objective lighting state; `GridMap` owns spatial queries and pathfinding.
    """

    name: str = Field(default="Floor", description="The name of the tile")
    position: Tuple[StrictInt, StrictInt] = Field(
        default=(0, 0),
        description="Strict objective coordinate owned by this Tile.",
    )
    surface: TileSurface = Field(
        default_factory=lambda: TileSurface(base_material=Material.STONE),
        description="Validated semantic support surface.",
    )
    blocks_optics: bool = Field(
        default=False,
        description="Whether the Tile intrinsically blocks ordinary XY optics.",
    )
    blocks_propagation_field: bool = Field(
        default=False,
        description="Whether the Tile intrinsically blocks physical propagation.",
    )
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

    height: StrictInt = Field(
        default=0,
        description="Support elevation in five-foot steps.",
    )
    elevation_surface_kind: ElevationSurfaceKind = Field(
        default=ElevationSurfaceKind.ORDINARY,
        description="Authored support-surface kind for progressive elevation.",
    )
    slope_axis: Optional[SlopeAxis] = Field(
        default=None,
        description="Cardinal axis of stairs or ramp.",
    )
    default_light: LightLevel = Field(
        default=LightLevel.BRIGHT_LIGHT,
        description="Base objective light level before illumination or obscurement modifiers.",
    )
    _illuminations: Dict[UUID, LightLevel] = PrivateAttr(default_factory=dict)
    _illumination_caps: Dict[UUID, LightLevel] = PrivateAttr(default_factory=dict)
    _center_object_bands: Dict[int, TileObjectBand] = PrivateAttr(
        default_factory=dict
    )
    _boundary_object_bands: Dict[
        CardinalDirection,
        Dict[int, TileObjectBand],
    ] = PrivateAttr(default_factory=_empty_boundary_object_bands)
    _entity_uuids: set[UUID] = PrivateAttr(default_factory=set)
    _spatial_condition_uuids: Dict[
        SpatialEffectLayer,
        set[UUID],
    ] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def validate_elevation_surface(self) -> "Tile":
        """Keep every stored elevation tuple internally coherent."""
        validate_elevation_surface_tuple(
            self.height,
            self.elevation_surface_kind,
            self.slope_axis,
        )
        return self

    def get_center_object_bands(self) -> Tuple[Tuple[int, TileObjectBand], ...]:
        """Return immutable center-band snapshots ordered by height."""
        return tuple(sorted(self._center_object_bands.items()))

    def get_boundary_object_bands(
        self,
        direction: CardinalDirection,
    ) -> Tuple[Tuple[int, TileObjectBand], ...]:
        """Return immutable boundary-band snapshots ordered by height."""
        return tuple(
            sorted(self._boundary_object_bands.get(direction, {}).items())
        )

    def _replace_center_object_band(
        self,
        height: int,
        band: Optional[TileObjectBand],
    ) -> None:
        """Replace one complete center band; owned by GridMap commits."""
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
        """Replace one complete boundary band; owned by GridMap commits."""
        direction_bands = self._boundary_object_bands.setdefault(direction, {})
        if band is None:
            direction_bands.pop(height, None)
        else:
            direction_bands[height] = band

    def get_entity_uuids(self) -> set[UUID]:
        """Return a defensive snapshot of the Tile's present Entities."""
        return set(self._entity_uuids)

    def _replace_entity_uuids(self, entity_uuids: set[UUID]) -> None:
        """Replace complete occupancy; called only by GridMap commits."""
        self._entity_uuids = set(entity_uuids)

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
            self._spatial_condition_uuids.pop(layer)

    def get_spatial_condition_uuids(
        self,
        layer: Optional[SpatialEffectLayer] = None,
    ) -> set[UUID]:
        """Return independent condition UUIDs affecting this Tile."""
        if layer is not None:
            return set(self._spatial_condition_uuids.get(layer, set()))
        return {
            condition_uuid
            for condition_uuids in self._spatial_condition_uuids.values()
            for condition_uuid in condition_uuids
        }

    def get_conditions(self) -> Dict[UUID, BaseCondition]:
        """Return every directly or independently owned condition here."""
        conditions = dict(self.active_conditions_by_uuid)
        for condition_uuid in self.get_spatial_condition_uuids():
            condition = BaseCondition.get(condition_uuid)
            if not isinstance(condition, BaseCondition):
                raise RuntimeError(
                    "Tile references a missing spatial condition "
                    f"{condition_uuid}",
                )
            if not condition.is_active_spatial_condition():
                raise RuntimeError(
                    "Tile references an inactive spatial condition "
                    f"{condition_uuid}",
                )
            conditions[condition_uuid] = condition
        return conditions

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

    def blocks_optics_at_center(self) -> bool:
        """Return the Tile's intrinsic ordinary-optics policy."""
        return self.blocks_optics

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
        return resolve_tile_light_level(self, self.default_light)

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
               blocks_optics: bool = False,
               blocks_propagation: bool = False,
               name: str = "Floor",
               sprite_name: Optional[str] = None,
               height: int = 0,
               surface: Optional[TileSurface] = None,
               walking_cost: int = 1,
               flying_cost: int = 1,
               swimming_cost: int = 0,
               burrowing_cost: int = 0,
               elevation_surface_kind: ElevationSurfaceKind = ElevationSurfaceKind.ORDINARY,
               slope_axis: Optional[SlopeAxis] = None,
               default_light: LightLevel = LightLevel.BRIGHT_LIGHT) -> 'Tile':
        """Create a tile with movement-mode `ModifiableValue` costs."""
        validate_tile_creation_inputs(
            position, blocks_optics=blocks_optics,
            blocks_propagation=blocks_propagation, name=name,
            sprite_name=sprite_name, height=height, surface=surface,
            walking_cost=walking_cost, flying_cost=flying_cost,
            swimming_cost=swimming_cost, burrowing_cost=burrowing_cost,
            elevation_surface_kind=elevation_surface_kind,
            slope_axis=slope_axis, default_light=default_light,
        )
        cost_values = {
            "walking_cost": walking_cost,
            "flying_cost": flying_cost,
            "swimming_cost": swimming_cost,
            "burrowing_cost": burrowing_cost,
        }
        tile_uuid = uuid4()

        walking_cost_value = ModifiableValue.create(
            source_entity_uuid=tile_uuid,
            base_value=cost_values["walking_cost"],
            value_name="Walking Cost"
        )
        if cost_values["walking_cost"] <= 0:
            walking_cost_value.self_static.add_max_constraint(
                NumericalModifier.create(
                    source_entity_uuid=tile_uuid,
                    name="Impassable",
                    value=0
                )
            )

        flying_cost_value = ModifiableValue.create(
            source_entity_uuid=tile_uuid,
            base_value=cost_values["flying_cost"],
            value_name="Flying Cost"
        )

        swimming_cost_value = ModifiableValue.create(
            source_entity_uuid=tile_uuid,
            base_value=cost_values["swimming_cost"],
            value_name="Swimming Cost"
        )
        if cost_values["swimming_cost"] <= 0:
            swimming_cost_value.self_static.add_max_constraint(
                NumericalModifier.create(
                    source_entity_uuid=tile_uuid,
                    name="No Water",
                    value=0
                )
            )

        burrowing_cost_value = ModifiableValue.create(
            source_entity_uuid=tile_uuid,
            base_value=cost_values["burrowing_cost"],
            value_name="Burrowing Cost"
        )
        if cost_values["burrowing_cost"] <= 0:
            burrowing_cost_value.self_static.add_max_constraint(
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
            surface=surface if surface is not None else TileSurface(base_material=Material.STONE),
            blocks_optics=blocks_optics,
            blocks_propagation_field=blocks_propagation,
            name=name,
            sprite_name=sprite_name,
            walking_cost=walking_cost_value,
            flying_cost=flying_cost_value,
            swimming_cost=swimming_cost_value,
            burrowing_cost=burrowing_cost_value,
            height=height,
            elevation_surface_kind=elevation_surface_kind,
            slope_axis=slope_axis,
            default_light=default_light
        )


# Factory locations are governed by the content-recovery visual overlay.
# Keep new Tile helper definitions below these authored factories.





def floor_factory(position: Tuple[int, int]) -> Tile:
    """Create a floor tile (bright light, outdoor default)."""
    return Tile.create(position, name="Floor", sprite_name="floor.png")


def dark_floor_factory(position: Tuple[int, int]) -> Tile:
    """Create a dark floor tile (darkness, dungeon default)."""
    return Tile.create(position, name="Floor", sprite_name="floor.png",
                       default_light=LightLevel.DARKNESS)


def wall_factory(position: Tuple[int, int]) -> Tile:
    """Create a wall tile."""
    tile = Tile.create(
        position,
        walking_cost=0,
        flying_cost=0,
        blocks_optics=True,
        blocks_propagation=True,
        name="Wall",
        sprite_name="wall.png",
    )
    return tile


def water_factory(position: Tuple[int, int]) -> Tile:
    """Create a water tile (can't walk, can see through, can swim)."""
    tile = Tile.create(
        position,
        walking_cost=0,
        swimming_cost=1,
        name="Water",
        sprite_name="water.png",
    )

    return tile


def difficult_terrain_factory(position: Tuple[int, int]) -> Tile:
    """Create a difficult terrain tile (walking costs 2x movement)."""
    tile = Tile.create(
        position,
        walking_cost=2,
        name="Difficult Terrain",
        sprite_name="rough.png",
    )

    return tile


def validate_tile_creation_inputs(
    position: Tuple[int, int],
    *,
    blocks_optics: bool,
    blocks_propagation: bool,
    name: str,
    sprite_name: Optional[str],
    height: int,
    surface: Optional[TileSurface],
    walking_cost: int,
    flying_cost: int,
    swimming_cost: int,
    burrowing_cost: int,
    elevation_surface_kind: ElevationSurfaceKind,
    slope_axis: Optional[SlopeAxis],
    default_light: LightLevel,
) -> None:
    """Validate every Tile creation input before allocating owned values."""
    if (
        type(position) is not tuple
        or len(position) != 2
        or any(type(coordinate) is not int for coordinate in position)
    ):
        raise TypeError("tile position must be a pair of exact integers")
    if type(blocks_optics) is not bool:
        raise TypeError("blocks_optics must be an exact boolean")
    if type(blocks_propagation) is not bool:
        raise TypeError("blocks_propagation must be an exact boolean")
    if type(name) is not str:
        raise TypeError("tile name must be a string")
    if sprite_name is not None and type(sprite_name) is not str:
        raise TypeError("sprite_name must be a string or None")
    if surface is not None and type(surface) is not TileSurface:
        raise TypeError("surface must be a TileSurface or None")
    for cost_name, cost in {
        "walking_cost": walking_cost,
        "flying_cost": flying_cost,
        "swimming_cost": swimming_cost,
        "burrowing_cost": burrowing_cost,
    }.items():
        if type(cost) is not int or cost < 0:
            raise ValueError(
                f"{cost_name} must be a nonnegative strict integer"
            )
    if type(default_light) is not LightLevel:
        raise TypeError("default_light must be a LightLevel")
    validate_elevation_surface_tuple(
        height,
        elevation_surface_kind,
        slope_axis,
    )


def resolve_tile_light_level(
    tile: Tile,
    default_light: LightLevel,
) -> LightLevel:
    """Preview objective light with another authored default, without mutation."""
    if type(default_light) is not LightLevel:
        raise TypeError("default_light must be a LightLevel")
    brightest = default_light
    for level in tile._illuminations.values():
        if level.value > brightest.value:
            brightest = level
    if not tile._illumination_caps:
        return brightest
    darkest = min(tile._illumination_caps.values(), key=lambda level: level.value)
    return LightLevel(min(brightest.value, darkest.value))


def tile_light_contributions(
    tile: Tile,
) -> Tuple[Dict[UUID, LightLevel], Dict[UUID, LightLevel]]:
    """Return detached GridMap-owned illumination and cap contributions."""
    return dict(tile._illuminations), dict(tile._illumination_caps)


def validate_tile_owned_movement_graph(tile: Tile) -> None:
    """Authenticate every locally owned movement root, channel, and modifier."""
    if tile.source_entity_uuid != tile.uuid or BaseBlock.get(tile.uuid) is not tile:
        raise ValueError("Tile registry ownership is not current")
    values = (
        tile.walking_cost,
        tile.flying_cost,
        tile.swimming_cost,
        tile.burrowing_cost,
    )
    if len({value.uuid for value in values}) != len(values):
        raise ValueError("Tile movement value identities are not distinct")
    channels = tuple(
        channel
        for value in values
        for channel in (
            value.self_static,
            value.to_target_static,
            value.self_contextual,
            value.to_target_contextual,
        )
    )
    if len({channel.uuid for channel in channels}) != len(channels):
        raise ValueError("Tile movement channel identities are not distinct")

    seen_modifier_uuids = set()
    for value in values:
        if value.source_entity_uuid != tile.uuid or BaseValue.get(value.uuid) is not value:
            raise ValueError("Tile movement value ownership is not current")
        for channel in (
            value.self_static,
            value.to_target_static,
            value.self_contextual,
            value.to_target_contextual,
        ):
            if channel.source_entity_uuid != tile.uuid or BaseValue.get(channel.uuid) is not channel:
                raise ValueError("Tile movement channel ownership is not current")
            modifier_entries = (
                tuple(channel.value_modifiers.items())
                + tuple(channel.min_constraints.items())
                + tuple(channel.max_constraints.items())
                + tuple(channel.advantage_modifiers.items())
                + tuple(channel.critical_modifiers.items())
                + tuple(channel.auto_hit_modifiers.items())
                + tuple(channel.size_modifiers.items())
                + tuple(channel.damage_type_modifiers.items())
                + tuple(channel.resistance_modifiers.items())
            )
            if any(
                modifier_uuid != modifier.uuid
                for modifier_uuid, modifier in modifier_entries
            ):
                raise ValueError("Tile movement modifier key does not match identity")
            modifiers = tuple(modifier for _, modifier in modifier_entries)
            modifier_uuids = {modifier.uuid for modifier in modifiers}
            if (
                len(modifier_uuids) != len(modifiers)
                or seen_modifier_uuids & modifier_uuids
            ):
                raise ValueError("Tile movement modifier identities are not distinct")
            seen_modifier_uuids.update(modifier_uuids)
            if any(
                modifier.source_entity_uuid != tile.uuid
                or BaseObject.get(modifier.uuid) is not modifier
                for modifier in modifiers
            ):
                raise ValueError("Tile movement modifier ownership is not current")


def release_tile_owned_movement_graph(tile: Tile) -> None:
    """Release one detached Tile's authenticated finite value graph."""
    validate_tile_owned_movement_graph(tile)
    for value in (
        tile.walking_cost,
        tile.flying_cost,
        tile.swimming_cost,
        tile.burrowing_cost,
    ):
        value.reset_from_target()
        for channel in (
            value.self_static,
            value.to_target_static,
            value.self_contextual,
            value.to_target_contextual,
        ):
            modifier_uuids = tuple(channel.get_all_modifier_uuids())
            channel.remove_all_modifiers()
            for modifier_uuid in modifier_uuids:
                BaseObject.unregister(modifier_uuid)
            BaseValue.unregister(channel.uuid)
        BaseValue.unregister(value.uuid)
    BaseBlock.unregister(tile.uuid)
