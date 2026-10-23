"""Taking things off racks and walls, torches from holders, curtains and pumps, through ordinary actions."""

from uuid import uuid4

from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_authored_door, build_wall_torch
from dnd.content.items.world_prop_builders import build_display_prop
from dnd.core.gridmap import get_map
from dnd.items.torches import Torch
from dnd.items.water_fixtures import build_waterskin
from dnd.types.world import CardinalDirection, LightLevel
from tests.engine.test_triskelion_hazards_and_traps import act, arena, creature, row

__all__ = ["arena"]


def look(display) -> str | None:
    return display.to_item_presentation_state().visual_variant_id


def test_a_rack_shows_full_partly_emptied_and_empty_as_its_pieces_are_taken(arena):
    taker = creature("Taker", (2, 2))
    rack = build_display_prop("environment.furniture.wall_rack", look="swords", capacity=2)
    rack.place_on_grid((3, 2))
    first, second = (build_authored_item("weapon.longsword", rack.uuid) for _ in range(2))
    assert rack.chest_inventory.add_item(first) and rack.chest_inventory.add_item(second)
    assert look(rack) == "swords_full"
    act(taker, "Loot Longsword")
    assert look(rack) == "swords_partly_empty"
    act(taker, "Loot All")
    assert look(rack) == "swords_empty" and {first.uuid, second.uuid} <= set(taker.inventory.items)


def test_a_shield_comes_off_its_wall_mount(arena):
    taker = creature("Taker", (2, 2))
    mount = build_display_prop("environment.furniture.mounted_shield")
    mount.place_on_grid((3, 2))
    shield = build_authored_item("shield.shield", mount.uuid)
    assert mount.chest_inventory.add_item(shield)
    assert look(mount) == "full"
    act(taker, "Loot All")
    assert look(mount) == "empty" and shield.uuid in taker.inventory.items


def test_a_burning_torch_taken_from_its_holder_keeps_burning_in_hand(arena):
    taker = creature("Taker", (2, 2))
    fixture = build_wall_torch()
    fixture.removable = True
    fixture.mount((3, 2), lit=True)
    act(taker, "Take Torch")
    carried = [item for item in taker.inventory.items.values() if isinstance(item, Torch)]
    assert len(carried) == 1 and carried[0].is_lit
    assert get_map().get_object_position(fixture.uuid) is None
    tile = get_map().get_tile(2, 2)
    assert tile is not None and tile.resolved_light_level is not LightLevel.DARKNESS


def test_a_fixed_wall_torch_offers_no_take(arena):
    taker = creature("Taker", (2, 2))
    build_wall_torch().mount((3, 2), lit=True)
    assert row(taker, "Take Torch") is None


def test_a_closed_curtain_hides_the_alcove_but_never_blocks_the_way(arena):
    curtain = build_authored_door("environment.door.alcove_curtain")
    curtain.place_on_grid((3, 2), boundary_direction=CardinalDirection.EAST)
    manikin = build_authored_item("environment.furniture.manikin", uuid4())
    manikin.place_on_grid((5, 2))  # deeper in the alcove behind the curtain
    looker = creature("Looker", (3, 2))
    assert manikin.uuid not in looker.senses.objects
    assert get_map().can_transition((3, 2), (4, 2))  # closed, it still lets a walker through
    act(looker, "Open Door")
    looker.update_entity_senses()
    assert manikin.uuid in looker.senses.objects


def test_a_working_pump_fills_an_empty_waterskin_and_a_dry_tap_gives_nothing(arena):
    drinker = creature("Drinker", (2, 2))
    pump = build_authored_item("environment.furniture.hand_pump", uuid4())
    pump.place_on_grid((3, 2))
    tap = build_authored_item("environment.furniture.pump_faucet", uuid4())
    tap.place_on_grid((2, 3))
    empty = build_waterskin(drinker.uuid)
    assert drinker.loot_item(empty)
    act(drinker, "Work Pump", target=tap)
    assert [item.item_id for item in drinker.inventory.items.values()] == ["gear.waterskin.empty"]
    act(drinker, "Work Pump", target=pump)
    assert [item.item_id for item in drinker.inventory.items.values()] == ["gear.waterskin.full"]


def test_a_hunting_tapestry_comes_down_off_its_hooks(arena):
    taker = creature("Taker", (2, 2))
    hooks = build_display_prop("environment.furniture.tapestry")
    hooks.place_on_grid((3, 2))
    tapestry = build_authored_item("treasure.hunting_tapestry", hooks.uuid)
    assert hooks.chest_inventory.add_item(tapestry)
    act(taker, "Loot All")
    assert look(hooks) == "empty" and tapestry.uuid in taker.inventory.items
