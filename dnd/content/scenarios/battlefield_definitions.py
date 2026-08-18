"""Cold authored battlefield facts with no registry or digest machinery."""

import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from dnd.core.traversal_connectors import TraversalConnectorDefinition
from dnd.core.world_edges import (
    ElevationSurfaceKind,
    SlopeAxis,
    contradictory_progressive_elevation_edge,
)
from dnd.types.world import CardinalDirection


LightLevelName = Literal["bright", "darkness"]
BattlefieldTerrain = Literal["gap", "water", "difficult_terrain", "spikes"]
BattlefieldObjectKind = Literal[
    "wall",
    "door",
    "wall_torch",
    "healing_potion",
    "trap_lever",
    "fireball_cannon",
    "loot_chest",
]

_BATTLEFIELD_ID = re.compile(
    r"^battlefield\.[a-z][a-z0-9_]*(?:[.-][a-z0-9_]+)*$",
)


class BattlefieldTileDefinition(BaseModel):
    """One non-default authored tile fact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    position: tuple[int, int]
    terrain: BattlefieldTerrain
    walkable: bool = True
    walking_cost: int = Field(default=1, ge=1)
    hazardous: bool = False


class BattlefieldObjectDefinition(BaseModel):
    """One static world-object placement shown by the cold definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    position: tuple[int, int]
    kind: BattlefieldObjectKind
    label: str
    blocked_directions: tuple[CardinalDirection, ...] = ()
    is_open: bool | None = None


class BattlefieldElevationDefinition(BaseModel):
    """One authored support-surface override."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    position: tuple[StrictInt, StrictInt]
    elevation_steps: StrictInt
    surface_kind: ElevationSurfaceKind = ElevationSurfaceKind.ORDINARY
    slope_axis: SlopeAxis | None = None

    @model_validator(mode="after")
    def _validate_surface(self) -> Self:
        if self.surface_kind is ElevationSurfaceKind.ORDINARY:
            if self.slope_axis is not None:
                raise ValueError("ordinary surfaces cannot declare a slope axis")
        elif self.slope_axis is None:
            raise ValueError("stairs and ramps require a slope axis")
        return self


class BattlefieldLayoutDefinition(BaseModel):
    """Compact cold projection of one deterministic battlefield builder."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tiles: tuple[BattlefieldTileDefinition, ...] = ()
    objects: tuple[BattlefieldObjectDefinition, ...] = ()
    elevation: tuple[BattlefieldElevationDefinition, ...] = ()
    connectors: tuple[TraversalConnectorDefinition, ...] = ()

    @model_validator(mode="after")
    def _validate_unique_rows(self) -> Self:
        elevation_positions = [row.position for row in self.elevation]
        if len(elevation_positions) != len(set(elevation_positions)):
            raise ValueError("battlefield elevation positions must be unique")
        connector_ids = [row.authored_id for row in self.connectors]
        if len(connector_ids) != len(set(connector_ids)):
            raise ValueError("battlefield connector IDs must be unique")
        return self


class BattlefieldDefinition(BaseModel):
    """Renderer-independent identity, geometry, and capabilities for one map."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    battlefield_id: str
    title: str
    width: int = Field(default=15, ge=1)
    height: int = Field(default=15, ge=1)
    tags: tuple[str, ...] = ()
    light_level: LightLevelName = "bright"
    capabilities: tuple[str, ...] = ()
    layout: BattlefieldLayoutDefinition = Field(
        default_factory=BattlefieldLayoutDefinition,
    )

    @field_validator("battlefield_id")
    @classmethod
    def _validate_battlefield_id(cls, value: str) -> str:
        if not _BATTLEFIELD_ID.fullmatch(value):
            raise ValueError("battlefield_id must be a battlefield.* identity")
        return value

    @model_validator(mode="after")
    def _validate_definition(self) -> Self:
        if len(self.tags) != len(set(self.tags)):
            raise ValueError("battlefield tags must be unique")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("battlefield capabilities must be unique")
        positions = {
            row.position: (row.elevation_steps, row.surface_kind, row.slope_axis)
            for row in self.layout.elevation
        }
        if any(
            not (0 <= x < self.width and 0 <= y < self.height)
            for x, y in positions
        ):
            raise ValueError("battlefield elevation must be inside map bounds")
        contradiction = contradictory_progressive_elevation_edge(
            positions,
            implicit_surface=(0, ElevationSurfaceKind.ORDINARY, None),
            bounds=(self.width, self.height),
        )
        if contradiction is not None:
            raise ValueError(
                "battlefield has contradictory progressive elevation at "
                f"{contradiction!r}",
            )
        for connector in self.layout.connectors:
            if any(
                not (0 <= x < self.width and 0 <= y < self.height)
                for x, y in connector.endpoint_positions
            ):
                raise ValueError("connector endpoints must be inside map bounds")
        return self


__all__ = [
    "BattlefieldDefinition",
    "BattlefieldElevationDefinition",
    "BattlefieldLayoutDefinition",
    "BattlefieldObjectDefinition",
    "BattlefieldObjectKind",
    "BattlefieldTerrain",
    "BattlefieldTileDefinition",
    "LightLevelName",
]
