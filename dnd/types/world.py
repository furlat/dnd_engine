"""Dependency-neutral grid, lighting, and structural vocabulary."""

from collections.abc import Iterable, Mapping
from enum import Enum, StrEnum
from functools import lru_cache
from typing import NamedTuple


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


class SpatialChannel(StrEnum):
    """Objective world channel whose change invalidates derived spatial state."""

    MOVEMENT = "movement"
    # Physical sight geometry: what shadowcast field of view reads.
    OPTICAL = "optical"
    # Conditional obscurement along sight routes; physical field of view is unchanged.
    OBSCUREMENT = "obscurement"
    ILLUMINATION = "illumination"
    PROPAGATION = "propagation"
    OCCUPANCY = "occupancy"


EDGE_CHANNEL_REVISIONS: Mapping[WorldEdgeChannel, SpatialChannel] = {
    WorldEdgeChannel.MOVEMENT: SpatialChannel.MOVEMENT,
    WorldEdgeChannel.OPTICAL: SpatialChannel.OPTICAL,
    WorldEdgeChannel.PROPAGATION: SpatialChannel.PROPAGATION,
}


def edge_revision_channels(channels: Iterable[WorldEdgeChannel]) -> frozenset[SpatialChannel]:
    """Return the revision channels invalidated by changed structural channels."""
    return frozenset(EDGE_CHANNEL_REVISIONS[channel] for channel in channels)


class ObserverRevisions(NamedTuple):
    """One subscriber's revisions of the channels its sensory field depends on."""

    optical: int = 0
    illumination: int = 0
    propagation: int = 0
    occupancy: int = 0
    obscurement: int = 0


@lru_cache(maxsize=65536)
def cell_key(position: tuple[int, int]) -> str:
    """The wire key of one grid cell ("x,y")."""
    return f"{position[0]},{position[1]}"


@lru_cache(maxsize=65536)
def key_cell(key: str) -> tuple[int, int]:
    """The grid cell of one wire key ("x,y")."""
    x_text, y_text = key.split(",", maxsplit=1)
    return int(x_text), int(y_text)


__all__ = [
    "CardinalDirection",
    "cell_key",
    "key_cell",
    "EDGE_CHANNEL_REVISIONS",
    "LightLevel",
    "MovementMode",
    "ObserverRevisions",
    "OccupancyLayer",
    "SpatialChannel",
    "WorldEdgeChannel",
    "edge_revision_channels",
]


class MovementProvocationPolicy(str, Enum):
    """Objective source-exit reaction policy for one movement leg."""

    ORDINARY_EXIT = "ordinary_exit"
    DOES_NOT_PROVOKE = "does_not_provoke"
