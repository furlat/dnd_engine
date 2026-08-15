"""Dependency-neutral grid, lighting, and structural channel vocabulary."""

from enum import Enum, StrEnum


class MovementMode(str, Enum):
    """Movement modes supported by world traversal."""

    WALKING = "walking"
    FLYING = "flying"
    SWIMMING = "swimming"
    BURROWING = "burrowing"


class LightLevel(int, Enum):
    """Tile light levels ordered from most obscuring to brightest."""

    MAGICAL_DARKNESS = 0
    DARKNESS = 1
    DIM_LIGHT = 2
    BRIGHT_LIGHT = 3
    VERY_BRIGHT = 4


class CardinalDirection(StrEnum):
    """Cardinal grid direction used by authored structures."""

    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class WorldEdgeChannel(str, Enum):
    """Objective structural channel blocked by one contribution."""

    MOVEMENT = "movement"
    VISION = "vision"
    LIGHT = "light"
    PROPAGATION = "propagation"


__all__ = [
    "CardinalDirection",
    "LightLevel",
    "MovementMode",
    "WorldEdgeChannel",
]
