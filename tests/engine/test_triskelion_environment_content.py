"""Triskelion environment parts: art variants, profiled containers and authored lights."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.blocks.base_item import BaseItem
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_hearth_fire
from dnd.content.items.world_prop_builders import build_world_prop
from dnd.core.creature_types import DamageType
from dnd.entity import Entity, EntityConfig
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemIntegrity
from dnd.game import Game
from dnd.items.environment_interactables import StorageChest
from dnd.items.visual_variants import ItemVisualVariantParameters
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world import LightLevel


@pytest.fixture
def game() -> Iterator[Game]:
    grid = reset_engine_runtime()
    grid.create_rectangle(0, 0, 14, 8, default_light=LightLevel.DARKNESS)
    instance = Game()
    yield instance
    instance.close()
    reset_engine_runtime()


def level(position: tuple[int, int]) -> LightLevel:
    tile = get_map().get_tile(*position)
    assert tile is not None
    return tile.resolved_light_level


def test_a_prop_variant_reaches_the_client_under_its_body_and_unknown_variants_are_refused(game: Game):
    couch = build_world_prop("environment.furniture.couch",
                             variant=ItemVisualVariantParameters(visual_variant_id="dark_green"))
    bear = build_world_prop("environment.furniture.taxidermy_large", variant=ItemVisualVariantParameters(
        visual_variant_id="bear", display_name="Stuffed bear"))
    couch.place_on_grid((2, 2))
    bear.place_on_grid((6, 2))
    couch_fact, bear_fact = couch.to_item_presentation_state(), bear.to_item_presentation_state()
    assert (couch_fact.name, couch_fact.visual_item_name, couch_fact.visual_variant_id) == (
        "Couch", "Couch", "dark_green")
    assert (bear_fact.name, bear_fact.visual_item_name, bear_fact.visual_variant_id) == (
        "Stuffed bear", "Stuffed animal", "bear")
    with pytest.raises(ValueError):
        build_world_prop("environment.furniture.couch",
                         variant=ItemVisualVariantParameters(visual_variant_id="purple"))


@pytest.mark.parametrize(("item_id", "cells", "armor_class"), (
    ("environment.container.footlocker", {(3, 3)}, 15),
    ("environment.container.iron_bound_chest", {(3, 3)}, 15),
    ("environment.container.huge_iron_chest", {(3, 3), (4, 3)}, 19),
    ("environment.container.iron_box", {(3, 3)}, 19),
    ("environment.container.long_wooden_box", {(3, 3)}, 15),
    ("environment.container.coffin", {(3, 3), (4, 3)}, 15),
    ("environment.container.barrel", {(3, 3)}, 15),
))
def test_a_container_covers_its_cells_and_spills_exactly_its_contents_when_broken(
        game: Game, item_id: str, cells: set[tuple[int, int]], armor_class: int):
    container = build_authored_item(item_id, uuid4())
    assert isinstance(container, StorageChest)
    coins = BaseItem(source_entity_uuid=container.uuid, item_id="test.item.coins", name="Coins")
    assert container.chest_inventory.add_item(coins)
    placement = container.place_on_grid((3, 3))
    assert set(placement.positions) == cells and container.armor_class == armor_class
    hit_points = container.get_hp()
    container.receive_damage(hit_points - 1, DamageType.BLUDGEONING, container.uuid)
    assert container.integrity is ItemIntegrity.INTACT and set(container.chest_inventory.items) == {coins.uuid}
    container.receive_damage(1, DamageType.BLUDGEONING, container.uuid)
    assert container.integrity is ItemIntegrity.DESTROYED and not container.chest_inventory.items
    assert get_map().get_object_position(coins.uuid) == (3, 3) and coins.owner_uuid is None


def test_a_continual_light_rod_lights_its_wall_until_someone_takes_it(game: Game):
    rod = build_authored_item("gear.continual_light_rod", uuid4())
    rod.place_on_grid((3, 2))
    assert level((3, 2)) is LightLevel.BRIGHT_LIGHT and level((7, 2)) is LightLevel.BRIGHT_LIGHT
    assert level((8, 2)) is LightLevel.DIM_LIGHT and level((12, 2)) is LightLevel.DARKNESS
    assert rod.douse_exposed_flame() is False and level((3, 2)) is LightLevel.BRIGHT_LIGHT
    taker = Entity.create(uuid4(), "Taker", config=EntityConfig(position=(2, 2)))
    taker.compose_entity()
    game.deploy_entity(taker, (2, 2))
    assert taker.loot_item(rod)
    assert level((3, 2)) is LightLevel.DARKNESS  # the light went with the rod, covered in a pack


def test_a_hearth_fire_lights_the_room_until_it_is_doused(game: Game):
    fireplace = build_world_prop("environment.furniture.fireplace",
                                 variant=ItemVisualVariantParameters(visual_variant_id="ornate"))
    fireplace.place_on_grid((3, 3))
    fire = build_hearth_fire()
    fire.mount((3, 2), lit=True)
    assert level((5, 2)) is LightLevel.BRIGHT_LIGHT and level((7, 2)) is LightLevel.BRIGHT_LIGHT
    assert level((8, 2)) is LightLevel.DIM_LIGHT and level((12, 2)) is LightLevel.DARKNESS
    assert not get_map().is_walkable_for(3, 3) and not get_map().is_walkable_for(4, 3)
    assert fire.douse_exposed_flame() is True
    assert level((3, 2)) is LightLevel.DARKNESS
