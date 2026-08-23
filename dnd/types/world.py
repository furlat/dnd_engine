"""Dependency-neutral grid, lighting, and structural channel vocabulary."""

from enum import Enum, StrEnum


class MovementMode(str, Enum):
    """Movement modes supported by world traversal."""

    WALKING = "walking"
    FLYING = "flying"
    SWIMMING = "swimming"
    BURROWING = "burrowing"


class LightLevel(int, Enum):
    """Objective illumination levels ordered from darkest to brightest."""

    DARKNESS = 0
    DIM_LIGHT = 1
    BRIGHT_LIGHT = 2
    VERY_BRIGHT = 3


class CardinalDirection(StrEnum):
    """Cardinal grid direction used by authored structures."""

    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class WorldEdgeChannel(str, Enum):
    """Objective structural channel blocked by one contribution."""

    MOVEMENT = "movement"
    OPTICAL = "optical"
    PROPAGATION = "propagation"


__all__ = [
    "CardinalDirection",
    "LightLevel",
    "MovementMode",
    "WorldEdgeChannel",
]
