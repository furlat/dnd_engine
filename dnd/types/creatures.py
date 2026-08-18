"""Dependency-neutral creature classification facts."""

from enum import Enum


class Size(str, Enum):
    """Mechanical creature size category."""

    TINY = "Tiny"
    SMALL = "Small"
    MEDIUM = "Medium"
    LARGE = "Large"
    HUGE = "Huge"
    GARGANTUAN = "Gargantuan"


class CreatureType(str, Enum):
    """D&D 5e creature type."""

    ABERRATION = "aberration"
    BEAST = "beast"
    CELESTIAL = "celestial"
    CONSTRUCT = "construct"
    DRAGON = "dragon"
    ELEMENTAL = "elemental"
    FEY = "fey"
    FIEND = "fiend"
    GIANT = "giant"
    HUMANOID = "humanoid"
    MONSTROSITY = "monstrosity"
    OOZE = "ooze"
    PLANT = "plant"
    UNDEAD = "undead"


class Species(str, Enum):
    """Closed built-in ancestry identities carried by an Entity."""

    DRAGONBORN = "dragonborn"
    DWARF = "dwarf"
    ELF = "elf"
    GNOME = "gnome"
    HALF_ELF = "half_elf"
    HALF_ORC = "half_orc"
    HALFLING = "halfling"
    HUMAN = "human"
    TIEFLING = "tiefling"


class SpeciesVariant(str, Enum):
    """Closed built-in ancestry variants carried by an Entity."""

    HILL_DWARF = "dwarf.hill"
    HIGH_ELF = "elf.high"
    ROCK_GNOME = "gnome.rock"
    LIGHTFOOT_HALFLING = "halfling.lightfoot"


class Background(str, Enum):
    """Closed built-in background identities carried by an Entity."""

    ACOLYTE = "acolyte"
    ADVENTURER = "adventurer"


class OriginCapability(str, Enum):
    """Non-numerical creature capabilities granted by an origin."""

    ARTIFICERS_LORE = "origin_capability.artificers_lore"
    HALFLING_NIMBLENESS = "origin_capability.halfling_nimbleness"
    MAGICAL_SLEEP_IMMUNITY = "origin_capability.magical_sleep_immunity"
    NATURALLY_STEALTHY = "origin_capability.naturally_stealthy"
    SHELTER_OF_THE_FAITHFUL = "origin_capability.shelter_of_the_faithful"
    STONECUNNING = "origin_capability.stonecunning"
    TINKER = "origin_capability.tinker"
    TRANCE = "origin_capability.trance"


__all__ = [
    "Background",
    "CreatureType",
    "OriginCapability",
    "Size",
    "Species",
    "SpeciesVariant",
]
