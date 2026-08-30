"""Strict cold values for object placement and authored boundaries."""

from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from dnd.types.materials import Material
from dnd.types.world import CardinalDirection, WorldEdgeChannel


class WorldPlacementKind(StrEnum):
    """Whether a world object is placed at a Tile center or boundary."""

    CENTER = "center"
    BOUNDARY = "boundary"


class WorldPlacementSpec(BaseModel):
    """Provider-owned placement capability used by GridMap admission."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: WorldPlacementKind
    occupies_bands: bool
    vertical_extent_steps: StrictInt = Field(ge=1)


class WorldObjectPlacement(BaseModel):
    """Resolved committed placement of one registered world object."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    object_uuid: UUID
    tile_uuid: UUID
    position: tuple[StrictInt, StrictInt]
    kind: WorldPlacementKind
    occupies_bands: bool
    boundary_direction: CardinalDirection | None = None
    base_height_steps: StrictInt
    top_height_steps: StrictInt
    orientation: CardinalDirection | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        """Require exact vertical and center/boundary shape semantics."""
        if self.top_height_steps <= self.base_height_steps:
            raise ValueError(
                "top_height_steps must be greater than base_height_steps"
            )
        if self.kind is WorldPlacementKind.CENTER:
            if self.boundary_direction is not None:
                raise ValueError(
                    "center placement cannot define boundary_direction"
                )
        elif self.boundary_direction is None:
            raise ValueError("boundary placement requires boundary_direction")
        return self


class BoundaryStructureKind(StrEnum):
    """Semantic kind of an authored cardinal boundary structure."""

    CLIFF = "cliff"
    EMBANKMENT = "embankment"
    RETAINING_WALL = "retaining_wall"
    WALL = "wall"
    DOOR = "door"
    FENCE = "fence"


class BoundaryStructure(BaseModel):
    """Computed current structural channels of one boundary provider."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    structure: BoundaryStructureKind
    material: Material
    blocked_channels: tuple[WorldEdgeChannel, ...]

    @model_validator(mode="after")
    def validate_channels(self) -> Self:
        """Require unique channels in canonical order."""
        canonical = tuple(WorldEdgeChannel)
        if len(set(self.blocked_channels)) != len(self.blocked_channels):
            raise ValueError("blocked_channels must not contain duplicates")
        if tuple(
            channel
            for channel in canonical
            if channel in self.blocked_channels
        ) != self.blocked_channels:
            raise ValueError("blocked_channels must use canonical channel order")
        return self


__all__ = [
    "BoundaryStructure",
    "BoundaryStructureKind",
    "WorldObjectPlacement",
    "WorldPlacementKind",
    "WorldPlacementSpec",
]
