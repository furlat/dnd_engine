"""Dependency-neutral equipment slot, property, and policy enums."""

from enum import Enum
from typing import TypeAlias, Union


class WeaponUsage(str, Enum):
    """Whether a weapon is held gear or an explicitly intrinsic body attack."""

    HELD = "held"
    BODY = "body"


class WeaponKind(str, Enum):
    """Base weapon form, independent of recipe, possession and visual identity."""

    CLUB = "club"
    SPEAR = "spear"
    MACE = "mace"
    DAGGER = "dagger"
    HANDAXE = "handaxe"
    JAVELIN = "javelin"
    LIGHT_HAMMER = "light_hammer"
    QUARTERSTAFF = "quarterstaff"
    SICKLE = "sickle"
    DART = "dart"
    SLING = "sling"
    BATTLEAXE = "battleaxe"
    GREATAXE = "greataxe"
    GREATSWORD = "greatsword"
    DOUBLE_BLADED_SWORD = "double_bladed_sword"
    LONGSWORD = "longsword"
    MORNINGSTAR = "morningstar"
    RAPIER = "rapier"
    LONGBOW = "longbow"
    SHORTSWORD = "shortsword"
    SCIMITAR = "scimitar"
    TRIDENT = "trident"
    WARHAMMER = "warhammer"
    SHORTBOW = "shortbow"
    LIGHT_CROSSBOW = "light_crossbow"
    HEAVY_CROSSBOW = "heavy_crossbow"
    HAND_CROSSBOW = "hand_crossbow"
    GREATCLUB = "greatclub"
    MAUL = "maul"
    MUSKET = "musket"


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
    BACKPACK = "backpack"
    RING_LEFT = "ring_left"
    RING_RIGHT = "ring_right"


class EquipmentRenderLayer(str, Enum):
    """Dependency-neutral renderer layers contributed by equipped items."""

    BACKPACK = "backpack"
    CLOAK = "cloak"
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
    BACKPACK = "Backpack"


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
