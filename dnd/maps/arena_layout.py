"""Shared standard arena layout construction."""

from dataclasses import dataclass
from typing import Tuple
from uuid import UUID, uuid4

from dnd.core.base_block import LightLevel
from dnd.core.gridmap import GridMap
from dnd.content.items.environment_item_builders import (
    build_directional_door,
    build_directional_wall,
    build_trap_lever,
    build_wall_torch,
)
from dnd.items.consumables import build_healing_potion
from dnd.items.environment import DirectionalDoor, DirectionalWall
from dnd.items.environment_interactables import TrapLever
from dnd.items.torches import WallTorch
from dnd.core.base_tiles import difficult_terrain_factory
from dnd.types.world import CardinalDirection, WorldEdgeChannel

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

DOOR_DIRECTIONS: Tuple[str, ...] = ("west",)
WALL_DIRECTIONS: Tuple[str, ...] = DOOR_DIRECTIONS
STANDARD_BLOCKING_CHANNELS: Tuple[WorldEdgeChannel, ...] = (
    WorldEdgeChannel.MOVEMENT,
    WorldEdgeChannel.OPTICAL,
    WorldEdgeChannel.PROPAGATION,
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
WALL_TORCH_POSITIONS: Tuple[Tuple[int, int], ...] = ((14, 1), (14, 13))
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


def create_standard_arena_floor(grid: GridMap) -> None:
    """Create the standard 15x15 arena floor."""
    grid.create_rectangle(ARENA_ORIGIN[0], ARENA_ORIGIN[1], ARENA_WIDTH, ARENA_HEIGHT)


def place_standard_directional_barrier(grid: GridMap) -> StandardBarrierObjects:
    """Place the standard arena directional wall strip and door."""
    walls = []
    for position in WALL_POSITIONS:
        grid.set_tile(position[0], position[1], name="Floor")
        wall = build_directional_wall(
            blocked_channels=STANDARD_BLOCKING_CHANNELS,
        )
        wall.place_on_grid(
            position,
            boundary_direction=CardinalDirection.WEST,
        )
        walls.append(wall)

    grid.set_tile(DOOR_POSITION[0], DOOR_POSITION[1], name="Floor")
    door = build_directional_door(
        display_name="Door",
        blocked_channels=STANDARD_BLOCKING_CHANNELS,
        is_open=False,
    )
    door.place_on_grid(
        DOOR_POSITION,
        boundary_direction=CardinalDirection.WEST,
    )

    return StandardBarrierObjects(door=door, walls=tuple(walls))


def darken_arena(grid: GridMap) -> None:
    """Set every current arena tile to darkness."""
    for position in grid.get_all_tiles():
        grid.set_tile_base_light(position, LightLevel.DARKNESS)


def build_dark_standard_barrier_fixture(grid: GridMap) -> StandardBarrierObjects:
    """Create a dark arena with only the standard directional wall and door."""
    create_standard_arena_floor(grid)
    barrier = place_standard_directional_barrier(grid)
    darken_arena(grid)
    return barrier


def build_standard_arena_environment(grid: GridMap) -> StandardArenaObjects:
    """Build the standard arena environment without combat entities."""
    create_standard_arena_floor(grid)
    barrier = place_standard_directional_barrier(grid)

    for position in WATER_POSITIONS:
        grid.set_tile(
            position[0],
            position[1],
            walking_cost=0,
            swimming_cost=1,
            name="Water",
        )

    spike_condition_uuid = uuid4()

    for position in DIFFICULT_TERRAIN_POSITIONS:
        tile = difficult_terrain_factory(position)
        grid.set_tile(position[0], position[1], tile=tile, fire_event=False)

    darken_arena(grid)

    wall_torches_list = []
    for position in WALL_TORCH_POSITIONS:
        wall_torch = build_wall_torch()
        wall_torch.mount(position, lit=False)
        wall_torches_list.append(wall_torch)
    wall_torches = tuple(wall_torches_list)

    healing_potion_uuids = []
    for position in HEALING_POTION_POSITIONS:
        potion = build_healing_potion(uuid4(), heal_amount=10)
        potion.place_on_grid(position)
        healing_potion_uuids.append(potion.uuid)

    lever = build_trap_lever(
        trap_condition_uuid=spike_condition_uuid,
        charges=1,
    )
    lever.place_on_grid(TRAP_LEVER_POSITION)

    return StandardArenaObjects(
        barrier=barrier,
        wall_torches=wall_torches,
        healing_potion_uuids=tuple(healing_potion_uuids),
        trap_lever=lever,
        spike_condition_uuid=spike_condition_uuid,
    )
