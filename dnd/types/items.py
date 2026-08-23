"""Dependency-neutral item observation and location contracts."""

from enum import Enum
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from dnd.types.world import CardinalDirection, WorldEdgeChannel


class ItemRarity(str, Enum):
    """Stable rarity labels carried by item definitions and event facts."""

    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    VERY_RARE = "very_rare"
    LEGENDARY = "legendary"


class ItemKind(str, Enum):
    """Mechanical item families used by rules and authoritative events."""

    ITEM = "item"
    USABLE = "usable"
    WEAPON = "weapon"
    ARMOR = "armor"
    SHIELD = "shield"


class ItemLocation(str, Enum):
    """Authoritative placement represented by an item location-state fact."""

    FLOOR = "floor"
    INVENTORY = "inventory"
    EQUIPMENT = "equipment"
    MERGED = "merged"
    DESTROYED = "destroyed"


class ItemDirectionalStructureState(BaseModel):
    """Cold directional topology contributed by one spatial item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    blocked_directions: Tuple[CardinalDirection, ...]
    blocked_channels: Tuple[WorldEdgeChannel, ...]


class ItemLightSourceState(BaseModel):
    """Cold visible light-emitter state contributed by one item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    is_lit: bool
    very_bright_radius_feet: int = Field(ge=0)
    bright_radius_feet: int = Field(ge=0)
    dim_radius_feet: int = Field(ge=0)


class ItemChargeState(BaseModel):
    """Cold finite-use state contributed by one usable item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    charges: int = Field(ge=-1)
    max_charges: int = Field(ge=-1)


class ItemObservationState(BaseModel):
    """Closed observer-relative state for one spatial item.

    Common item facts remain required. Orthogonal capabilities are nested
    rather than encoded as an open bag of concrete-class fields, so one object
    may truthfully be both usable and structural or usable and luminous.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    blocks_movement: bool
    blocks_optics: bool
    blocks_propagation: bool
    is_pickable: bool
    is_usable: bool
    stack_count: int = Field(ge=1)
    is_hazardous: bool
    is_open: Optional[bool] = None
    directional_structure: Optional[ItemDirectionalStructureState] = None
    light_source: Optional[ItemLightSourceState] = None
    charge_state: Optional[ItemChargeState] = None


__all__ = [
    "ItemChargeState",
    "ItemDirectionalStructureState",
    "ItemKind",
    "ItemLightSourceState",
    "ItemLocation",
    "ItemObservationState",
    "ItemRarity",
]
