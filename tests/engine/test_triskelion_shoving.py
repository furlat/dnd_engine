"""R63's shoved furniture, through the ordinary Shove Object action."""

from uuid import uuid4

from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.core.gridmap import get_map
from dnd.types.world import CardinalDirection
from tests.engine.test_triskelion_hazards_and_traps import act, arena, creature, row, walk
from dnd.entity import Entity

__all__ = ["arena"]


def shoved(entity: Entity, item, *faces: int) -> None:
    act(entity, "Shove Object", target=item, faces=faces)


def test_a_chair_shoved_from_the_side_moves_one_square_straight_away(arena):
    pusher = creature("Pusher", (2, 2))
    chair = build_authored_item("environment.furniture.wooden_chair", uuid4())
    chair.place_on_grid((3, 2))
    shoved(pusher, chair)  # light: no roll
    assert get_map().get_object_position(chair.uuid) == (4, 2)
    assert get_map().is_walkable_for(3, 2) and not get_map().is_walkable_for(4, 2)


def test_a_wall_or_a_creature_stops_a_shove_and_the_body_stays_put(arena):
    pusher = creature("Pusher", (2, 2))
    chair = build_authored_item("environment.furniture.wooden_chair", uuid4())
    chair.place_on_grid((3, 2))
    wall = build_directional_wall()
    wall.place_on_grid((3, 2), boundary_direction=CardinalDirection.EAST)
    shoved(pusher, chair)
    assert get_map().get_object_position(chair.uuid) == (3, 2)
    other = creature("Other", (3, 3))
    walk(pusher, (2, 1))
    walk(pusher, (3, 1))
    shoved(pusher, chair)  # pushing north into the other creature
    assert get_map().get_object_position(chair.uuid) == (3, 2) and other.position == (3, 3)


def test_a_heavy_couch_moves_whole_only_when_strength_wins(arena):
    pusher = creature("Pusher", (2, 2), strength=18)
    couch = build_authored_item("environment.furniture.couch", uuid4())
    couch.place_on_grid((3, 2))  # covers (3, 2) and (4, 2)
    shoved(pusher, couch, 5)  # Athletics 5 + 4 misses DC 15
    assert set(get_map().get_object_placement(couch.uuid).positions) == {(3, 2), (4, 2)}
    shoved(pusher, couch, 12)
    assert set(get_map().get_object_placement(couch.uuid).positions) == {(4, 2), (5, 2)}


def test_furniture_is_not_shoved_from_a_corner(arena):
    pusher = creature("Pusher", (2, 2))
    chair = build_authored_item("environment.furniture.wooden_chair", uuid4())
    chair.place_on_grid((3, 3))
    info = row(pusher, "Shove Object")
    assert info is None or chair.uuid not in {option.target_uuid for option in info.valid_targets}


def test_a_shove_into_another_body_is_refused_and_both_stay_put(arena):
    pusher = creature("Pusher", (2, 2))
    chair = build_authored_item("environment.furniture.wooden_chair", uuid4())
    chair.place_on_grid((3, 2))
    table = build_authored_item("environment.furniture.table", uuid4())
    table.place_on_grid((4, 2))
    shoved(pusher, chair)
    assert get_map().get_object_position(chair.uuid) == (3, 2)
    assert get_map().get_object_position(table.uuid) == (4, 2)


def test_a_shove_into_a_barrel_is_refused_even_though_it_fills_no_band(arena):
    pusher = creature("Pusher", (2, 2))
    chair = build_authored_item("environment.furniture.wooden_chair", uuid4())
    chair.place_on_grid((3, 2))
    barrel = build_authored_item("environment.blocker.oil_barrel", uuid4())
    barrel.place_on_grid((4, 2))
    shoved(pusher, chair)
    assert get_map().get_object_position(chair.uuid) == (3, 2)


def test_a_fixture_built_in_place_offers_no_shove(arena):
    pusher = creature("Pusher", (2, 2))
    fireplace = build_authored_item("environment.furniture.fireplace", uuid4())
    fireplace.place_on_grid((3, 2))
    info = row(pusher, "Shove Object")
    assert info is None or fireplace.uuid not in {option.target_uuid for option in info.valid_targets}