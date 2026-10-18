"""Use contact from many origins admits exactly the origins a single contact admits.

Plan §14.2 #4: the origins within reach of the contact surface contain every
origin `manual_object_contact` admits; the GridMap query traces only those.
"""

from collections.abc import Callable, Iterator
from typing import Tuple
from uuid import uuid4

import pytest

from dnd.blocks.base_item import BaseItem
from dnd.content.items.environment_item_builders import build_directional_door, build_trap_lever
from dnd.content.items.world_prop_builders import build_world_prop
from dnd.core.gridmap import get_map
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world import CardinalDirection

Cells = Tuple[Tuple[int, int], ...]
ANCHOR = (4, 4)
WEST = (1, 4)
SOUTH = (4, 1)


@pytest.fixture
def game() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(9, 9))
    instance = Game()
    yield instance
    instance.close()
    reset_engine_runtime()


def lever() -> BaseItem:
    item = build_trap_lever()
    item.place_on_grid(ANCHOR)
    return item


def two_cell(item_id: str) -> Callable[[], BaseItem]:
    """A two-cell prop rotated north: supports (4, 4) and (4, 5)."""
    def place() -> BaseItem:
        item = build_world_prop(item_id)
        item.place_on_grid(ANCHOR, orientation=CardinalDirection.NORTH)
        return item
    return place


def door() -> BaseItem:
    item = build_directional_door(is_open=False)
    item.place_on_grid(ANCHOR, boundary_direction=CardinalDirection.EAST)
    return item


AROUND_LEVER: Cells = ((3, 3), (3, 4), (3, 5), (4, 3), (4, 4), (4, 5), (5, 3), (5, 4), (5, 5))
AROUND_TWO_CELLS: Cells = ((3, 3), (3, 4), (3, 5), (3, 6), (4, 3), (4, 4), (4, 5), (4, 6),
                           (5, 3), (5, 4), (5, 5), (5, 6))
# Seen from the south, an opaque body hides its far support: only the near one can be touched.
NEAR_SUPPORT_ONLY: Cells = tuple(cell for cell in AROUND_TWO_CELLS if cell[1] != 6)
RAISED_EAST: Cells = tuple(cell for cell in AROUND_LEVER if cell != (5, 4))

# Each case: placement, raised tiles (support distance above grid distance), actor position,
# and the origins expected to make contact objectively and subjectively.
CASES: dict[str, tuple[Callable[[], BaseItem], Cells, Tuple[int, int], Cells, Cells]] = {
    "center lever, 5 ft": (lever, (), WEST, AROUND_LEVER, AROUND_LEVER),
    "center lever, raised neighbour": (lever, ((5, 4),), WEST, RAISED_EAST, RAISED_EAST),
    "two-cell cart": (two_cell("environment.furniture.parked_cart"), (), WEST, AROUND_TWO_CELLS, AROUND_TWO_CELLS),
    "opaque wagon hiding its far support": (two_cell("environment.furniture.loaded_wagon"), (), SOUTH,
        AROUND_TWO_CELLS, NEAR_SUPPORT_ONLY),
    "boundary door, 0 ft, both incident cells": (door, (), WEST, ((4, 4), (5, 4)), ((4, 4), (5, 4))),
}


def check(game: Game, place: Callable[[], BaseItem], raised: Cells, actor_position: Tuple[int, int],
          objective: Cells, subjective: Cells) -> None:
    grid = get_map()
    item = place()
    for position in raised:
        assert grid.set_tile_elevation(position, height=2, surface_kind=ElevationSurfaceKind.ORDINARY,
                                       slope_axis=None)
    actor = Entity.create(uuid4(), "Toucher", config=EntityConfig(position=actor_position))
    actor.compose_entity()
    game.deploy_entity(actor, actor_position)
    Entity.update_all_entities_senses()
    every_cell = {(x, y) for x in range(9) for y in range(9)}
    for mode, expected in ((False, objective), (True, subjective)):
        single = tuple(sorted(origin for origin in every_cell if grid.manual_object_contact(
            actor.uuid, item.uuid, subjective=mode, origin=origin) is not None))
        many = grid.manual_object_contact_origins(actor.uuid, item.uuid, every_cell, subjective=mode)
        assert (many, single) == (expected, expected), f"subjective={mode}"


@pytest.mark.parametrize("case", CASES)
def test_contact_origins_equal_single_contacts(game: Game, case: str) -> None:
    check(game, *CASES[case])
