"""Dependency-neutral authored battlefield contracts.

Battlefields are product content, not evaluation fixtures.  This module owns
only cold geometry, lighting, capability, and preview facts.  Runtime builders
live in :mod:`dnd.scenarios.battlefield_catalog`.
"""

from __future__ import annotations

import re
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    computed_field,
    field_validator,
    model_validator,
)

from dnd.core.content.canonical import canonical_content_sha256
from dnd.core.world_edges import (
    ElevationSurfaceKind,
    SlopeAxis,
    contradictory_progressive_elevation_edge,
)
from dnd.core.traversal_connectors import TraversalConnectorDefinition
from dnd.types.world import CardinalDirection


LightLevelName = Literal["bright", "darkness"]
BattlefieldPreviewTerrain = Literal[
    "gap",
    "water",
    "difficult_terrain",
    "spikes",
]
BattlefieldPreviewObjectKind = Literal[
    "wall",
    "door",
    "wall_torch",
    "healing_potion",
    "trap_lever",
    "fireball_cannon",
    "loot_chest",
]

_BATTLEFIELD_ID_PATTERN = re.compile(
    r"^battlefield\.[a-z][a-z0-9_]*(?:[.-][a-z0-9_]+)*$",
)


def _canonical_digest(payload: object) -> str:
    return canonical_content_sha256(payload)


class BattlefieldPreviewCell(BaseModel):
    """One non-default terrain cell in the cold battlefield preview."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    position: tuple[int, int] = Field(
        description="Grid coordinate of the terrain override.",
    )
    terrain: BattlefieldPreviewTerrain = Field(
        description="Stable visual and mechanical terrain category.",
    )
    walkable: bool = Field(
        description="Whether actors can enter the cell.",
    )
    walking_cost: int = Field(
        default=1,
        ge=1,
        description="Movement-cost multiplier for entering the cell.",
    )
    hazardous: bool = Field(
        default=False,
        description="Whether entering the cell can cause harm.",
    )


class BattlefieldPreviewObject(BaseModel):
    """One static object placement in the cold battlefield preview."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    position: tuple[int, int] = Field(
        description="Grid coordinate containing the object.",
    )
    kind: BattlefieldPreviewObjectKind = Field(
        description="Stable object presentation category.",
    )
    label: str = Field(description="Player-facing object label.")
    blocked_directions: tuple[CardinalDirection, ...] = Field(
        default=(),
        description="Directions blocked by a wall or closed door.",
    )
    is_open: bool | None = Field(
        default=None,
        description="Door state when the object is a door.",
    )


class BattlefieldElevationCell(BaseModel):
    """One authored support-surface override in a cold battlefield."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    position: tuple[StrictInt, StrictInt] = Field(
        description="Grid coordinate whose support surface is overridden.",
    )
    elevation_steps: StrictInt = Field(
        description="Signed support elevation in exact five-foot steps.",
    )
    surface_kind: ElevationSurfaceKind = Field(
        default=ElevationSurfaceKind.ORDINARY,
        description="Ordinary, stairs, or ramp support-surface kind.",
    )
    slope_axis: SlopeAxis | None = Field(
        default=None,
        description="Required traversal axis for stairs and ramps.",
    )

    @model_validator(mode="after")
    def _validate_surface_tuple(self) -> "BattlefieldElevationCell":
        if self.surface_kind is ElevationSurfaceKind.ORDINARY:
            if self.slope_axis is not None:
                raise ValueError("ordinary support surfaces cannot have a slope axis")
        elif self.slope_axis is None:
            raise ValueError("stairs and ramps require a slope axis")
        return self


class BattlefieldPreview(BaseModel):
    """Compact projection of canonical battlefield construction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cells: tuple[BattlefieldPreviewCell, ...] = Field(
        default=(),
        description="Terrain cells differing from the default floor.",
    )
    objects: tuple[BattlefieldPreviewObject, ...] = Field(
        default=(),
        description="Walls, doors, lights, loot, and devices on the floor.",
    )
    elevation_cells: tuple[BattlefieldElevationCell, ...] = Field(
        default=(),
        description="Exact non-flat support surfaces in the authored layout.",
    )
    connectors: tuple[TraversalConnectorDefinition, ...] = Field(
        default=(),
        description="Stable authored two-endpoint traversal connector rows.",
    )

    @model_validator(mode="after")
    def _validate_elevation_positions(self) -> "BattlefieldPreview":
        positions = [cell.position for cell in self.elevation_cells]
        if len(positions) != len(set(positions)):
            raise ValueError("battlefield elevation positions must be unique")
        connector_ids = [connector.authored_id for connector in self.connectors]
        if len(connector_ids) != len(set(connector_ids)):
            raise ValueError("battlefield connector authored IDs must be unique")
        return self


class BattlefieldDefinition(BaseModel):
    """Cold authored battlefield geometry and mechanical capabilities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    battlefield_id: str = Field(
        description="Stable battlefield catalog identifier.",
    )
    title: str = Field(description="Human-readable battlefield title.")
    width: int = Field(
        default=15,
        ge=1,
        description="Battlefield width in grid cells.",
    )
    height: int = Field(
        default=15,
        ge=1,
        description="Battlefield height in grid cells.",
    )
    tags: tuple[str, ...] = Field(
        default=(),
        description="Terrain, lighting, and object discovery tags.",
    )
    light_level: LightLevelName = Field(
        default="bright",
        description="Default light level outside explicit light sources.",
    )
    capabilities: tuple[str, ...] = Field(
        default=(),
        description="Mechanical capabilities used by compose preflight.",
    )
    preview: BattlefieldPreview = Field(
        default_factory=BattlefieldPreview,
        description="Exact cold projection of the canonical layout.",
    )
    mechanical_revision: int = Field(
        default=1,
        ge=1,
        description="Explicit authored mechanical revision.",
    )

    @field_validator("battlefield_id")
    @classmethod
    def _validate_battlefield_id(cls, value: str) -> str:
        if not _BATTLEFIELD_ID_PATTERN.fullmatch(value):
            raise ValueError(
                "battlefield_id must be a stable battlefield.* identifier",
            )
        return value

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("title must be non-empty and trimmed")
        return value

    @model_validator(mode="after")
    def _validate_sets(self) -> Self:
        if len(self.tags) != len(set(self.tags)):
            raise ValueError("battlefield tags must be unique")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("battlefield capabilities must be unique")
        elevation_cells = {}
        for cell in self.preview.elevation_cells:
            if not (
                0 <= cell.position[0] < self.width
                and 0 <= cell.position[1] < self.height
            ):
                raise ValueError(
                    "battlefield elevation positions must be inside its bounds"
                )
            elevation_cells[cell.position] = (
                cell.elevation_steps,
                cell.surface_kind,
                cell.slope_axis,
            )
        contradiction = contradictory_progressive_elevation_edge(
            elevation_cells,
            implicit_surface=(0, ElevationSurfaceKind.ORDINARY, None),
            bounds=(self.width, self.height),
        )
        if contradiction is not None:
            raise ValueError(
                "battlefield contains a contradictory progressive elevation "
                f"edge between {contradiction[0]} and {contradiction[1]}"
            )
        for connector in self.preview.connectors:
            if any(
                not (0 <= position[0] < self.width and 0 <= position[1] < self.height)
                for position in connector.endpoint_positions
            ):
                raise ValueError("battlefield connector endpoints must be inside bounds")
            first, second = connector.endpoint_positions
            first_height = elevation_cells.get(
                first,
                (0, ElevationSurfaceKind.ORDINARY, None),
            )[0]
            second_height = elevation_cells.get(
                second,
                (0, ElevationSurfaceKind.ORDINARY, None),
            )[0]
            if connector.kind.value != "passage" and first_height == second_height:
                raise ValueError(
                    "battlefield vertical connector requires nonzero elevation delta"
                )
        return self

    @computed_field(return_type=str)
    @property
    def content_digest(self) -> str:
        """Authenticate every product-visible battlefield fact."""
        return _canonical_digest(
            self.model_dump(
                mode="json",
                exclude={"content_digest"},
            ),
        )


__all__ = [
    "BattlefieldDefinition",
    "BattlefieldElevationCell",
    "BattlefieldPreview",
    "BattlefieldPreviewCell",
    "BattlefieldPreviewObject",
    "BattlefieldPreviewObjectKind",
    "BattlefieldPreviewTerrain",
    "LightLevelName",
]
