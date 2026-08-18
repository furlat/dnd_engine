"""Dependency-leaf Dragonborn ancestry and breath geometry values."""

from enum import Enum


class DragonbornAncestry(str, Enum):
    """The ten draconic ancestries defined by SRD 5.1 Dragonborn."""

    BLACK = "black"
    BLUE = "blue"
    BRASS = "brass"
    BRONZE = "bronze"
    COPPER = "copper"
    GOLD = "gold"
    GREEN = "green"
    RED = "red"
    SILVER = "silver"
    WHITE = "white"


class DragonbornBreathGeometry(str, Enum):
    """Closed geometry families used by Dragonborn Breath Weapon."""

    LINE = "line"
    CONE = "cone"


__all__ = ["DragonbornAncestry", "DragonbornBreathGeometry"]
