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
    computed_field,
    field_validator,
    model_validator,
)

from dnd.core.content.canonical import canonical_content_sha256


LightLevelName = Literal["bright", "darkness"]
BattlefieldPreviewTerrain = Literal[
    "water",
    "difficult_terrain",
    "spikes",
]
BattlefieldPreviewDirection = Literal["north", "south", "east", "west"]
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
    blocked_directions: tuple[BattlefieldPreviewDirection, ...] = Field(
        default=(),
        description="Directions blocked by a wall or closed door.",
    )
    is_open: bool | None = Field(
        default=None,
        description="Door state when the object is a door.",
    )


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
    "BattlefieldPreview",
    "BattlefieldPreviewCell",
    "BattlefieldPreviewDirection",
    "BattlefieldPreviewObject",
    "BattlefieldPreviewObjectKind",
    "BattlefieldPreviewTerrain",
    "LightLevelName",
]
