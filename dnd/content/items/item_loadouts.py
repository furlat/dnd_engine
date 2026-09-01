"""Cold ordered item plans used by authored entity composition."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional

from dnd.core.equipment_types import BodyPart, EquipmentSlot, WeaponSlot


@dataclass(frozen=True, slots=True)
class ItemLoadoutEntry:
    """One direct item identity and its final authored stack quantity."""

    item_id: str
    quantity: int = 1
    equipment_slot: Optional[EquipmentSlot] = None

    def __post_init__(self) -> None:
        if not self.item_id:
            raise ValueError("loadout item_id cannot be empty")
        if self.quantity < 1:
            raise ValueError("loadout quantity must be positive")


ACOLYTE_STARTING_LOADOUT = (
    ItemLoadoutEntry("gear.holy_symbol"),
    ItemLoadoutEntry("gear.prayer_book"),
    ItemLoadoutEntry("gear.incense", quantity=5),
    ItemLoadoutEntry("gear.vestments"),
    ItemLoadoutEntry("gear.common_clothes"),
)

BACKGROUND_ITEM_LOADOUTS: Mapping[str, tuple[ItemLoadoutEntry, ...]] = (
    MappingProxyType({
        "background.acolyte": ACOLYTE_STARTING_LOADOUT,
    })
)


CLASS_STARTING_LOADOUTS: Mapping[str, tuple[ItemLoadoutEntry, ...]] = (
    MappingProxyType({
        "starting_equipment.fighter.sword_shield": (
            ItemLoadoutEntry("armor.chain_mail", equipment_slot=BodyPart.BODY),
            ItemLoadoutEntry("weapon.longsword", equipment_slot=WeaponSlot.MELEE_MAIN),
            ItemLoadoutEntry("shield.shield", equipment_slot=WeaponSlot.MELEE_OFF),
        ),
        "starting_equipment.fighter.greatsword": (
            ItemLoadoutEntry("armor.chain_mail", equipment_slot=BodyPart.BODY),
            ItemLoadoutEntry("weapon.greatsword", equipment_slot=WeaponSlot.MELEE_MAIN),
        ),
        "starting_equipment.fighter.dual_wield": (
            ItemLoadoutEntry("armor.chain_mail", equipment_slot=BodyPart.BODY),
            ItemLoadoutEntry("weapon.shortsword", equipment_slot=WeaponSlot.MELEE_MAIN),
            ItemLoadoutEntry("weapon.shortsword", equipment_slot=WeaponSlot.MELEE_OFF),
        ),
        "starting_equipment.fighter.archery": (
            ItemLoadoutEntry("armor.studded_leather", equipment_slot=BodyPart.BODY),
            ItemLoadoutEntry("weapon.shortsword", equipment_slot=WeaponSlot.MELEE_MAIN),
            ItemLoadoutEntry("weapon.longbow", equipment_slot=WeaponSlot.RANGED_MAIN),
        ),
        "starting_equipment.barbarian.greataxe": (
            ItemLoadoutEntry("weapon.greataxe", equipment_slot=WeaponSlot.MELEE_MAIN),
        ),
        "starting_equipment.barbarian.dual_axes": (
            ItemLoadoutEntry("weapon.handaxe", equipment_slot=WeaponSlot.MELEE_MAIN),
            ItemLoadoutEntry("weapon.handaxe", equipment_slot=WeaponSlot.MELEE_OFF),
        ),
        "starting_equipment.barbarian.sword_shield": (
            ItemLoadoutEntry("weapon.longsword", equipment_slot=WeaponSlot.MELEE_MAIN),
            ItemLoadoutEntry("shield.shield", equipment_slot=WeaponSlot.MELEE_OFF),
        ),
        "starting_equipment.sorcerer.dagger": (
            ItemLoadoutEntry("weapon.dagger", equipment_slot=WeaponSlot.MELEE_MAIN),
        ),
        "starting_equipment.sorcerer.quarterstaff": (
            ItemLoadoutEntry("weapon.quarterstaff", equipment_slot=WeaponSlot.MELEE_MAIN),
        ),
    })
)


__all__ = [
    "ACOLYTE_STARTING_LOADOUT",
    "BACKGROUND_ITEM_LOADOUTS",
    "CLASS_STARTING_LOADOUTS",
    "ItemLoadoutEntry",
]
