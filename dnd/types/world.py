"""Dependency-neutral grid, lighting, and structural vocabulary."""

from enum import Enum, StrEnum


class OccupancyLayer(StrEnum):
    """A creature's physical contact band relative to local support."""

    GROUND = "ground"
    AIR = "air"
    UNDERGROUND = "underground"


class MovementMode(str, Enum):
    """Movement modes supported by world traversal."""

    WALKING = "walking"
    FLYING = "flying"
    SWIMMING = "swimming"
    BURROWING = "burrowing"


class LightLevel(int, Enum):
    """Objective light levels ordered from most obscuring to brightest."""

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
    OPTICAL = "optical"
    PROPAGATION = "propagation"


__all__ = [
    "CardinalDirection",
    "LightLevel",
    "MovementMode",
    "OccupancyLayer",
    "WorldEdgeChannel",
]
