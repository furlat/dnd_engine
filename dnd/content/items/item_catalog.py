"""Cold catalog of item identities supported by direct construction."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from dnd.content.items.authored_item_definitions import (
    ACOLYTE_GEAR_DEFINITIONS,
    AUTHORED_WEAPON_DEFINITIONS,
    AUTHORED_WEARABLE_DEFINITIONS,
    STATIC_BLOCKER_DEFINITIONS,
)


@dataclass(frozen=True, slots=True)
class ItemCatalogEntry:
    """Renderer-independent item identity and authoring text."""

    item_id: str
    display_name: str
    description: str


_SPECIAL_DIRECT_ITEMS = (
    ItemCatalogEntry(
        "consumable.healing_potion",
        "Healing Potion",
        "A stackable potion that restores hit points when consumed.",
    ),
    ItemCatalogEntry(
        "consumable.potion_haste",
        "Potion of Haste",
        "A potion that applies the Haste spell effect.",
    ),
    ItemCatalogEntry(
        "consumable.potion_greater_invisibility",
        "Potion of Greater Invisibility",
        "A potion that applies the Greater Invisibility spell effect.",
    ),
    ItemCatalogEntry(
        "consumable.weapon_coat.fire",
        "Fire Weapon Coating",
        "A consumable coating that adds temporary fire damage to a weapon.",
    ),
    ItemCatalogEntry(
        "consumable.weapon_coat.lightning",
        "Lightning Weapon Coating",
        "A consumable coating that adds temporary lightning damage to a weapon.",
    ),
    ItemCatalogEntry(
        "consumable.weapon_coat.concentration_fire",
        "Concentrated Weapon Coat of Flame",
        "A single-use fire coating maintained by concentration.",
    ),
    ItemCatalogEntry(
        "consumable.weapon_coat.timed_fire",
        "Timed Weapon Coat of Flame",
        "A single-use fire coating lasting a fixed number of rounds.",
    ),
    ItemCatalogEntry(
        "consumable.acid_flask",
        "Acid Flask",
        "A thrown consumable that deals acid damage.",
    ),
    ItemCatalogEntry(
        "spell_item.scroll_fireball",
        "Scroll of Fireball",
        "A consumable scroll that casts Fireball.",
    ),
    ItemCatalogEntry(
        "spell_item.scroll_magic_missile",
        "Scroll of Magic Missile",
        "A consumable scroll that casts Magic Missile.",
    ),
    ItemCatalogEntry(
        "spell_item.scroll_hold_person",
        "Scroll of Hold Person",
        "A consumable scroll that casts Hold Person.",
    ),
    ItemCatalogEntry(
        "spell_item.scroll_mage_armor",
        "Scroll of Mage Armor",
        "A consumable scroll that casts Mage Armor.",
    ),
    ItemCatalogEntry(
        "spell_item.scroll_spike_growth",
        "Scroll of Spike Growth",
        "A consumable scroll that casts Spike Growth.",
    ),
    ItemCatalogEntry(
        "spell_item.scroll_invisibility",
        "Scroll of Invisibility",
        "A consumable scroll that casts Invisibility.",
    ),
    ItemCatalogEntry(
        "spell_item.scroll_fire_bolt",
        "Scroll of Fire Bolt",
        "A consumable scroll with level-scaled Fire Bolt.",
    ),
    ItemCatalogEntry(
        "spell_item.wand_magic_missiles",
        "Wand of Magic Missiles",
        "A charged wand that casts Magic Missile.",
    ),
    ItemCatalogEntry(
        "spell_item.wand_fire",
        "Wand of Fire",
        "A charged wand that casts Fireball.",
    ),
    ItemCatalogEntry(
        "equipment.portable_torch",
        "Portable Torch",
        "A portable light source that can be ignited and extinguished.",
    ),
    ItemCatalogEntry(
        "environment.directional_door",
        "Directional Door",
        "A stateful door that blocks selected world-edge channels while closed.",
    ),
    ItemCatalogEntry(
        "environment.campfire",
        "Campfire",
        "A fixed camp object that supports resting and cooking.",
    ),
    ItemCatalogEntry(
        "environment.arcane_device",
        "Arcane Device",
        "An Arcana-gated fixed device that restores health.",
    ),
    ItemCatalogEntry(
        "environment.arcane_machine_gun",
        "Arcane Machine Gun",
        "A fixed device with unlimited Magic Missile uses.",
    ),
    ItemCatalogEntry(
        "environment.directional_wall",
        "Directional Wall",
        "A wall that blocks selected world-edge channels.",
    ),
    ItemCatalogEntry(
        "environment.cliff_face",
        "Cliff Face",
        "A fixed movement-only cliff boundary.",
    ),
    ItemCatalogEntry(
        "environment.wall_torch",
        "Wall Torch",
        "A fixed wall-mounted light source.",
    ),
    ItemCatalogEntry(
        "environment.trap_lever",
        "Trap Lever",
        "An interactive lever linked to a trap effect.",
    ),
    ItemCatalogEntry(
        "environment.storage_chest",
        "Storage Chest",
        "An interactive container that can hold item state.",
    ),
    ItemCatalogEntry(
        "environment.fireball_cannon",
        "Fireball Cannon",
        "A finite-charge environmental device that casts Fireball.",
    ),
    ItemCatalogEntry(
        "environment.spell_object.heroes_feast",
        "Heroes' Feast",
        "A conjured feast whose servings grant the spell's protections.",
    ),
    ItemCatalogEntry(
        "gear.field_kit",
        "Field Kit",
        "A compact kit that deploys tactical focus gear.",
    ),
    ItemCatalogEntry(
        "weapon.assassin_dagger",
        "Assassin's Dagger",
        "A dagger that strikes harder when its target cannot see the wielder.",
    ),
)


def _definition_entries() -> tuple[ItemCatalogEntry, ...]:
    definitions = {
        **ACOLYTE_GEAR_DEFINITIONS,
        **AUTHORED_WEAPON_DEFINITIONS,
        **AUTHORED_WEARABLE_DEFINITIONS,
        **STATIC_BLOCKER_DEFINITIONS,
    }
    return tuple(
        ItemCatalogEntry(row.item_id, row.name, row.description)
        for row in definitions.values()
    )


DIRECT_ITEM_CATALOG: tuple[ItemCatalogEntry, ...] = (
    *_definition_entries(),
    *_SPECIAL_DIRECT_ITEMS,
)
DIRECT_ITEM_CATALOG_BY_ID: Mapping[str, ItemCatalogEntry] = MappingProxyType({
    row.item_id: row for row in DIRECT_ITEM_CATALOG
})

if len(DIRECT_ITEM_CATALOG_BY_ID) != len(DIRECT_ITEM_CATALOG):
    raise ValueError("direct item catalog contains duplicate identities")


__all__ = [
    "DIRECT_ITEM_CATALOG",
    "DIRECT_ITEM_CATALOG_BY_ID",
    "ItemCatalogEntry",
]
