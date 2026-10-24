"""Locks and bars on doors and containers: keys, Thieves' Tools and force, through ordinary actions."""

from uuid import uuid4

from dnd.content.items.authored_item_builders import build_authored_item
from dnd.blocks.base_item import BaseItem
from dnd.content.items.environment_item_builders import build_directional_door
from dnd.content.items.world_prop_builders import build_searchable_prop
from dnd.entity import Entity
from dnd.items.environment_interactables import StorageChest
from dnd.items.locks import Unlock, build_key, build_thieves_tools, install_lock
from dnd.types.world import CardinalDirection
from tests.engine.test_triskelion_hazards_and_traps import act, arena, creature, row, trapped_footlocker, walk

__all__ = ["arena"]


def locked_chest(position: tuple[int, int], **lock: object) -> StorageChest:
    chest = build_authored_item("environment.container.iron_bound_chest", uuid4())
    assert isinstance(chest, StorageChest)
    chest.place_on_grid(position)
    install_lock(chest, **lock)
    return chest


def shown_effects(chest: StorageChest) -> list[str]:
    return [effect.display_name for effect in chest.to_item_presentation_state().item_effects]


def test_a_locked_chest_opens_only_after_its_own_key_unlocks_it(arena):
    keyholder = creature("Keyholder", (2, 2))
    key = build_key(keyholder.uuid, "Iron key")
    chest = locked_chest((3, 2), key=key)
    stranger_key = build_key(keyholder.uuid, "Brass key")
    assert keyholder.loot_item(stranger_key)
    assert row(keyholder, "Open Chest") is None and row(keyholder, "Unlock") is None
    assert shown_effects(chest) == ["Locked"]
    assert keyholder.loot_item(key)
    act(keyholder, "Unlock", target=chest)  # no die: a key needs no roll
    assert shown_effects(chest) == []
    act(keyholder, "Open Chest")
    assert chest.is_open
    act(keyholder, "Close Chest")
    act(keyholder, "Lock", target=chest)
    assert shown_effects(chest) == ["Locked"] and row(keyholder, "Open Chest") is None


def test_a_failed_pick_breaks_one_set_of_tools_and_another_set_may_try_again(arena):
    rogue = creature("Rogue", (2, 2), dexterity=18)
    chest = locked_chest((3, 2), lock_dc=15)
    assert row(rogue, "Pick Lock") is None  # no tools, no pick
    assert rogue.loot_item(build_thieves_tools(rogue.uuid, 2))
    act(rogue, "Pick Lock", target=chest, faces=(5,))  # 5 + 4 misses DC 15
    tools = next(item for item in rogue.inventory.items.values() if item.item_id == "tool.thieves_tools")
    assert tools.stack_count == 1 and shown_effects(chest) == ["Locked"]
    act(rogue, "Pick Lock", target=chest, faces=(12,))  # 12 + 4 beats DC 15
    assert shown_effects(chest) == [] and tools.stack_count == 1
    act(rogue, "Open Chest")
    assert chest.is_open


def test_forcing_a_lock_bursts_it_open_and_breaks_it_for_good(arena):
    brute = creature("Brute", (2, 2), strength=18)
    key = build_key(brute.uuid)
    chest = locked_chest((3, 2), force_dc=15, key=key)
    assert brute.loot_item(key)
    act(brute, "Force Lock", target=chest, faces=(4,))  # 4 + 4 does not move it
    assert shown_effects(chest) == ["Locked"] and not chest.is_open
    act(brute, "Force Lock", target=chest, faces=(14,))
    assert shown_effects(chest) == [] and chest.is_open
    act(brute, "Close Chest")
    assert row(brute, "Lock") is None  # even its own key has no lock left to turn


def test_an_unlock_refused_by_its_rules_leaves_the_lock_as_it_was(arena):
    stranger = creature("Stranger", (2, 2))
    chest = locked_chest((3, 2), key=build_key(stranger.uuid))
    stranger.action_economy.reset_all_costs()
    stranger.update_entity_senses()
    result = Unlock(source_entity_uuid=stranger.uuid, target_entity_uuid=chest.uuid).apply()
    assert result is None or result.canceled
    assert shown_effects(chest) == ["Locked"] and row(stranger, "Open Chest") is None


def test_the_published_lock_shows_neither_its_key_nor_its_dcs(arena):
    keyholder = creature("Keyholder", (2, 2))
    key = build_key(keyholder.uuid)
    chest = locked_chest((3, 2), key=key, lock_dc=17, force_dc=19)
    published = chest.to_item_presentation_state().model_dump_json()
    assert "Locked" in published
    assert str(key.uuid) not in published and "lock_dc" not in published and "force_dc" not in published


def test_opening_a_trapped_chest_by_key_still_springs_its_needle(arena):
    footlocker = trapped_footlocker((3, 2))
    keyholder = creature("Keyholder", (2, 2))
    key = build_key(keyholder.uuid)
    install_lock(footlocker, key=key)
    assert keyholder.loot_item(key)
    act(keyholder, "Unlock", target=footlocker)
    act(keyholder, "Open Chest", faces=(5,))  # the needle's Constitution save fails
    assert "Needle paralysis" in keyholder.active_conditions


def test_a_locked_door_stays_shut_until_its_key_turns(arena):
    keyholder = creature("Keyholder", (3, 2))
    door = build_directional_door()
    door.place_on_grid((3, 2), boundary_direction=CardinalDirection.EAST)
    key = build_key(keyholder.uuid)
    install_lock(door, key=key)
    assert row(keyholder, "Open Door") is None
    assert keyholder.loot_item(key)
    act(keyholder, "Unlock", target=door)
    act(keyholder, "Open Door")
    assert door.is_open


def test_a_bar_is_lifted_and_set_only_from_its_own_side(arena):
    door = build_directional_door()
    door.place_on_grid((3, 2), boundary_direction=CardinalDirection.EAST)
    install_lock(door, lock_dc=None, bar_side="across")  # the bar is on the tile across the boundary
    outside = creature("Outside", (2, 2))
    inside = creature("Inside", (4, 2))
    act(inside, "Unlock", target=door)
    act(inside, "Open Door")
    act(inside, "Close Door")
    act(inside, "Lock", target=door)
    assert outside.loot_item(build_thieves_tools(outside.uuid))
    walk(outside, (3, 2))
    assert row(outside, "Unlock") is None and row(outside, "Pick Lock") is None  # a bar has nothing to pick
    assert row(outside, "Open Door") is None


def searchable(item_id: str, position: tuple[int, int], *, skill: str, holder: Entity) -> tuple[StorageChest, BaseItem]:
    body = build_searchable_prop(item_id, dc=13, skill=skill)
    body.place_on_grid(position)
    ring = build_key(holder.uuid, "Gold ring")
    assert body.chest_inventory.add_item(ring)
    return body, ring


def test_a_false_back_frees_its_contents_only_to_an_investigation_that_beats_it(arena):
    sharp = creature("Sharp", (2, 2), wisdom=20, dexterity=10)
    partner = creature("Partner", (2, 3))
    wardrobe, ring = searchable("environment.furniture.wardrobe", (3, 2), skill="investigation", holder=sharp)
    assert wardrobe.uuid in sharp.senses.objects  # the wardrobe itself is in plain view
    act(sharp, "Open Chest")
    assert row(sharp, "Loot All") is None and row(sharp, "Loot Gold ring") is None
    act(sharp, "Search Inside", target=wardrobe, faces=(8,))  # Investigation 8 + 4 misses DC 13
    assert row(sharp, "Loot All") is None
    searches = row(sharp, "Search Inside")  # one try each: the wardrobe is no longer sharp's to search
    assert searches is None or wardrobe.uuid not in {option.target_uuid for option in searches.valid_targets}
    act(partner, "Search Inside", target=wardrobe, faces=(16,))  # 16 beats it; the false back is open to all
    act(sharp, "Loot All")
    assert ring.uuid in sharp.inventory.items


def test_every_searchable_body_offers_a_search_whether_or_not_it_hides_anything(arena):
    looker = creature("Looker", (2, 2))
    empty = build_searchable_prop("environment.furniture.writing_desk", skill="perception")
    empty.place_on_grid((3, 2))
    full, _ = searchable("environment.furniture.dresser", (2, 3), skill="perception", holder=looker)
    info = row(looker, "Search Inside")
    assert info is not None and {option.target_uuid for option in info.valid_targets} >= {empty.uuid, full.uuid}

