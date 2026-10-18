"""Use contact from many origins admits exactly the origins a single contact admits (plan §14.2 #4)."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.blocks.base_item import BaseItem, WorldItem
from dnd.content.items.environment_item_builders import build_directional_door, build_trap_lever
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemDestructionProfile
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world import CardinalDirection
from dnd.types.world_placement import WorldPlacementKind, WorldPlacementSpec

ANCHOR = (4, 4)


@pytest.fixture
def game() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(9, 9))
    instance = Game()
    yield instance
    instance.close()
    reset_engine_runtime()


def wide_prop() -> WorldItem:
    owner = uuid4()
    return WorldItem(source_entity_uuid=owner, item_id="test.wide_prop", name="Wide prop",
        is_targetable=True, blocks_movement=True, blocks_propagation_field=True,
        health=BaseItem.create_item_health(owner, 30),
        world_placement_spec=WorldPlacementSpec(kind=WorldPlacementKind.CENTER,
            occupies_bands=True, vertical_extent_steps=1, footprint_offsets=((0, 0), (1, 0))),
        destruction_profile=ItemDestructionProfile(name="Debris"))


def place(kind: str) -> BaseItem:
    if kind == "lever":
        item: BaseItem = build_trap_lever()
        item.place_on_grid(ANCHOR)
    elif kind == "wide":
        item = wide_prop()
        item.place_on_grid(ANCHOR, orientation=CardinalDirection.NORTH)
    else:
        item = build_directional_door(is_open=False)
        item.place_on_grid(ANCHOR, boundary_direction=CardinalDirection.EAST)
    return item


# Each case: object, raised tiles (support distance above grid distance), and the origins
# expected to make contact.
CASES = {
    "center lever, 5 ft": ("lever", (),
        ((3, 3), (3, 4), (3, 5), (4, 3), (4, 4), (4, 5), (5, 3), (5, 4), (5, 5))),
    "center lever, raised neighbour": ("lever", ((5, 4),),
        ((3, 3), (3, 4), (3, 5), (4, 3), (4, 4), (4, 5), (5, 3), (5, 5))),
    "rotated two-cell prop": ("wide", (),
        ((3, 3), (3, 4), (3, 5), (3, 6), (4, 3), (4, 4), (4, 5), (4, 6), (5, 3), (5, 4), (5, 5), (5, 6))),
    "boundary door, 0 ft, both incident cells": ("door", (), ((4, 4), (5, 4))),
}


def check(game: Game, kind: str, raised: tuple, expected: tuple) -> None:
    grid = get_map()
    item = place(kind)
    for position in raised:
        assert grid.set_tile_elevation(position, height=2, surface_kind=ElevationSurfaceKind.ORDINARY,
                                       slope_axis=None)
    actor = Entity.create(uuid4(), "Toucher", config=EntityConfig(position=(1, 4)))
    actor.compose_entity()
    game.deploy_entity(actor, actor.position)
    Entity.update_all_entities_senses()
    every_cell = {(x, y) for x in range(9) for y in range(9)}
    for subjective in (False, True):
        single = tuple(sorted(origin for origin in every_cell if grid.manual_object_contact(
            actor.uuid, item.uuid, subjective=subjective, origin=origin) is not None))
        many = grid.manual_object_contact_origins(actor.uuid, item.uuid, every_cell, subjective=subjective)
        assert many == single, subjective
    assert many == expected


@pytest.mark.parametrize("case", CASES)
def test_contact_origins_equal_single_contacts(game: Game, case: str) -> None:
    check(game, *CASES[case])
