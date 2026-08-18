"""Temporary quarantine for backend-owned renderer and projection contracts.

The remaining enums are still imported by deferred action and authored visual
metadata. Item and equipment event facts no longer depend on this module.
"""

from enum import Enum


class ActionPresentationKind(str, Enum):
    """Stable presentation semantics for an action event."""

    DEFAULT = "default"
    DRINK = "drink"


class VisualLoadoutSlot(str, Enum):
    """Dependency-neutral actor presentation slots shared with transport."""

    WEAPON_MELEE_MAIN = "weapon_melee_main"
    WEAPON_MELEE_OFF = "weapon_melee_off"
    WEAPON_RANGED_MAIN = "weapon_ranged_main"
    WEAPON_RANGED_OFF = "weapon_ranged_off"
    HELMET = "helmet"
    BODY_ARMOR = "body_armor"
    GAUNTLETS = "gauntlets"
    GREAVES = "greaves"
    BOOTS = "boots"
    AMULET = "amulet"
    CLOAK = "cloak"
    RING_LEFT = "ring_left"
    RING_RIGHT = "ring_right"


class EquipmentRenderLayer(str, Enum):
    """Dependency-neutral renderer layers contributed by equipped items."""

    BELT = "belt"
    CHEST = "chest"
    HANDS = "hands"
    HELMET = "helmet"
    LEGS = "legs"
    OFFHAND = "offhand"
    SHOES = "shoes"
    WEAPON = "weapon"


__all__ = [
    "ActionPresentationKind",
    "EquipmentRenderLayer",
    "VisualLoadoutSlot",
]
