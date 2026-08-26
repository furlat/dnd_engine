"""Shared standard arena layout construction."""

from dataclasses import dataclass
from typing import Mapping, Tuple
from uuid import UUID, uuid4

from dnd.types.world import LightLevel
from dnd.core.base_tiles import Tile, difficult_terrain_factory, water_factory
from dnd.core.gridmap import GridMap
from dnd.types.materials import Material, TileSurface
from dnd.types.world import WorldEdgeChannel, CardinalDirection
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import (
    build_directional_door,
    build_directional_wall,
    build_trap_lever,
    build_wall_torch,
)
from dnd.items.environment import DIRECTIONAL_CHANNELS, DirectionalDoor, DirectionalWall
from dnd.items.environment_interactables import TrapLever
from dnd.items.torches import WallTorch

ARENA_WIDTH = 15
ARENA_HEIGHT = 15
ARENA_ORIGIN = (0, 0)

WALL_COLUMN = 7
WALL_Y_VALUES: Tuple[int, ...] = tuple(range(3, 12))
DOOR_POSITION = (7, 7)
WALL_POSITIONS: Tuple[Tuple[int, int], ...] = tuple(
    (WALL_COLUMN, y)
    for y in WALL_Y_VALUES
    if (WALL_COLUMN, y) != DOOR_POSITION
)

STANDARD_BLOCKING_CHANNELS: Tuple[WorldEdgeChannel, ...] = (
    DIRECTIONAL_CHANNELS
)

WATER_POSITIONS: Tuple[Tuple[int, int], ...] = (
    *((2, y) for y in range(4)),
    *((x, 3) for x in range(2)),
)
SPIKE_ZONE_POSITIONS = frozenset((x, y) for x in range(5) for y in range(11, 15))
DIFFICULT_TERRAIN_POSITIONS: Tuple[Tuple[int, int], ...] = (
    *((x, y) for x in range(6, 9) for y in range(0, 3)),
    *((x, y) for x in range(6, 9) for y in range(12, 15)),
)
WALL_TORCH_MOUNTS: Tuple[
    Tuple[Tuple[int, int], CardinalDirection, int, CardinalDirection],
    ...,
] = (
    ((14, 1), CardinalDirection.EAST, 1, CardinalDirection.WEST),
    ((14, 13), CardinalDirection.EAST, 1, CardinalDirection.WEST),
)
HEALING_POTION_POSITIONS: Tuple[Tuple[int, int], ...] = ((1, 12), (3, 13))
TRAP_LEVER_POSITION = (5, 12)


@dataclass(frozen=True)
class StandardBarrierObjects:
    door: DirectionalDoor
    walls: Tuple[DirectionalWall, ...]


@dataclass(frozen=True)
class StandardArenaObjects:
    barrier: StandardBarrierObjects
    wall_torches: Tuple[WallTorch, ...]
    healing_potion_uuids: Tuple[UUID, ...]
    trap_lever: TrapLever
    spike_condition_uuid: UUID


def create_standard_arena_floor(
    grid: GridMap,
    *,
    water_positions: Tuple[Tuple[int, int], ...] = (),
    difficult_positions: Tuple[Tuple[int, int], ...] = (),
    gap_positions: Tuple[Tuple[int, int], ...] = (),
    elevation_by_position: Mapping[
        Tuple[int, int],
        Tuple[int, ElevationSurfaceKind, SlopeAxis | None],
    ] | None = None,
) -> None:
    """Create each authored arena Tile once with its final state.

    Object-free floors retain the existing rectangle fast path. Authored
    terrain/elevation variants are created directly at their final
    coordinates so later builder steps never replace a live Tile identity.
    """
    water = set(water_positions)
    difficult = set(difficult_positions)
    gaps = set(gap_positions)
    elevations = elevation_by_position or {}
    if not water and not difficult and not gaps and not elevations:
        grid.create_rectangle(
            ARENA_ORIGIN[0],
            ARENA_ORIGIN[1],
            ARENA_WIDTH,
            ARENA_HEIGHT,
            surface=TileSurface(base_material=Material.STONE),
        )
        return

    for x in range(ARENA_ORIGIN[0], ARENA_ORIGIN[0] + ARENA_WIDTH):
        for y in range(ARENA_ORIGIN[1], ARENA_ORIGIN[1] + ARENA_HEIGHT):
            position = (x, y)
            height, surface_kind, slope_axis = elevations.get(
                position,
                (0, ElevationSurfaceKind.ORDINARY, None),
            )
            if position in gaps:
                tile = Tile.create(
                    position,
                    surface=TileSurface(base_material=Material.STONE),
                    walking_cost=0,
                    flying_cost=1,
                    swimming_cost=0,
                    burrowing_cost=0,
                    name="Gap",
                    height=height,
                    elevation_surface_kind=surface_kind,
                    slope_axis=slope_axis,
                )
            elif position in water:
                tile = water_factory(position)
            elif position in difficult:
                tile = difficult_terrain_factory(
                    position,
                    height=height,
                    elevation_surface_kind=surface_kind,
                    slope_axis=slope_axis,
                )
            else:
                tile = Tile.create(
                    position,
                    surface=TileSurface(base_material=Material.STONE),
                    name="Floor",
                    height=height,
                    elevation_surface_kind=surface_kind,
                    slope_axis=slope_axis,
                )
            grid.set_tile(x, y, tile=tile)


def place_standard_directional_barrier(grid: GridMap) -> StandardBarrierObjects:
    """Place the standard arena directional wall strip and door."""
    walls = []
    for position in WALL_POSITIONS:
        wall = build_directional_wall(
            blocked_channels=STANDARD_BLOCKING_CHANNELS,
        )
        grid.place_object(
            wall.uuid,
            position,
            boundary_direction=CardinalDirection.WEST,
        )
        walls.append(wall)

    door = build_directional_door(
        display_name="Door",
        blocked_channels=STANDARD_BLOCKING_CHANNELS,
        is_open=False,
    )
    grid.place_object(
        door.uuid,
        DOOR_POSITION,
        boundary_direction=CardinalDirection.WEST,
    )

    return StandardBarrierObjects(door=door, walls=tuple(walls))


def darken_arena(grid: GridMap) -> None:
    """Set every current arena tile to darkness."""
    for position in grid.get_all_tiles():
        grid.set_tile_base_light(position, LightLevel.DARKNESS)


def build_standard_arena_environment(grid: GridMap) -> StandardArenaObjects:
    """Build the standard arena environment without combat entities."""
    create_standard_arena_floor(
        grid,
        water_positions=WATER_POSITIONS,
        difficult_positions=DIFFICULT_TERRAIN_POSITIONS,
    )
    barrier = place_standard_directional_barrier(grid)
    spike_condition_uuid = uuid4()

    darken_arena(grid)

    wall_torches_list = []
    for position, boundary_direction, base_height_steps, orientation in WALL_TORCH_MOUNTS:
        wall_torch = build_wall_torch()
        wall_torch.mount(
            position,
            boundary_direction=boundary_direction,
            base_height_steps=base_height_steps,
            orientation=orientation,
            lit=False,
        )
        wall_torches_list.append(wall_torch)
    wall_torches = tuple(wall_torches_list)

    healing_potion_uuids = []
    for position in HEALING_POTION_POSITIONS:
        potion = build_authored_item(
            "consumable.healing_potion",
            uuid4(),
        )
        potion.place_on_grid(position)
        healing_potion_uuids.append(potion.uuid)

    lever = build_trap_lever(spike_condition_uuid, charges=1)
    lever.place_on_grid(TRAP_LEVER_POSITION)

    return StandardArenaObjects(
        barrier=barrier,
        wall_torches=wall_torches,
        healing_potion_uuids=tuple(healing_potion_uuids),
        trap_lever=lever,
        spike_condition_uuid=spike_condition_uuid,
    )
