"""Dependency-neutral equipment slot, property, and policy enums."""

from enum import Enum
from typing import TypeAlias, Union


class WeaponSlot(str, Enum):
    """Weapon positions exposed by an entity's equipment block."""

    MELEE_MAIN = "MELEE_MAIN"
    MELEE_OFF = "MELEE_OFF"
    RANGED_MAIN = "RANGED_MAIN"
    RANGED_OFF = "RANGED_OFF"


class WeaponSet(str, Enum):
    """Engine-owned weapon stance selected by accepted gameplay transitions."""

    NONE = "none"
    MELEE = "melee"
    RANGED = "ranged"


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


class BodyPart(str, Enum):
    """Body positions that may hold armor or accessories."""

    HEAD = "Head"
    BODY = "Body"
    HANDS = "Hands"
    LEGS = "Legs"
    FEET = "Feet"
    AMULET = "Amulet"
    RING = "Ring"
    CLOAK = "Cloak"


class RingSlot(str, Enum):
    """Concrete ring positions for items whose body part is ``RING``."""

    LEFT = "Left Ring"
    RIGHT = "Right Ring"


EquipmentSlot: TypeAlias = Union[WeaponSlot, BodyPart, RingSlot]


class UnarmoredAc(str, Enum):
    """Supported unarmored Armor Class formulas."""

    BARBARIAN = "Barbarian"
    MONK = "Monk"
    DRACONIC_SORCERER = "Draconic Sorcerer"
    MAGIC_ARMOR = "Magic Armor"
    NONE = "None"


class ArmorType(str, Enum):
    """Armor weight categories used by AC and movement rules."""

    LIGHT = "Light"
    MEDIUM = "Medium"
    HEAVY = "Heavy"
    CLOTH = "Cloth"


class WeaponProperty(str, Enum):
    """Weapon properties used by attack, damage, and equipment validation."""

    FINESSE = "Finesse"
    VERSATILE = "Versatile"
    RANGED = "Ranged"
    THROWN = "Thrown"
    TWO_HANDED = "Two-Handed"
    LIGHT = "Light"
    HEAVY = "Heavy"
    MARTIAL = "Martial"
    SIMPLE = "Simple"
