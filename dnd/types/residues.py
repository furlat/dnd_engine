"""Passive native facts for a body release and persistent tile residue."""

from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from dnd.types.world import CardinalDirection, OccupancyLayer
from dnd.types.material_deposits import MaterialDepositSource
from dnd.core.creature_types import DamageType


class ResidueEllipse(BaseModel):
    """An oriented world-space ellipse; tile ownership clips its original basis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    center: tuple[float, float]
    radius_x: float = Field(gt=0)
    radius_y: float = Field(gt=0)
    angle: float = 0  # Radians, measured from world +X.


class ResidueContribution(BaseModel):
    """Current deposited shape in owning-tile coordinates, without injury history."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ellipses: tuple[ResidueEllipse, ...]
    amount: int = Field(default=1, ge=1)
    deposit_source: MaterialDepositSource | None = None


class BodyReleaseRegion(BaseModel):
    """One common world ellipse and its actual receiving floor pieces."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ellipse: ResidueEllipse
    positions: tuple[tuple[int, int], ...]
    elevation_steps: int


class BodyReleaseResult(BaseModel):
    """One injury's release, with an optional actual residue destination."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    release_id: str
    position: tuple[int, int]
    occupancy_layer: OccupancyLayer
    deposited_position: tuple[int, int] | None = None
    pattern: Literal["piercing", "slashing", "blunt"] | None = None
    critical_hit: bool = False
    regions: tuple[BodyReleaseRegion, ...] = ()
    primary_damage_type: DamageType | None = None
    secondary_damage_type: DamageType | None = None


class TileResidueState(BaseModel):
    """Observable membership of one persistent residue on its owning tile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    condition_uuid: UUID
    residue_id: str
    description: str
    amount: int = Field(default=1, ge=1)
    max_amount: int = Field(default=1, ge=1)
    contributions: tuple[ResidueContribution, ...] = ()


class ObjectResidueState(BaseModel):
    """One inert residue on the contacted world-facing sides of an object."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    condition_uuid: UUID
    residue_id: str
    description: str
    faces: tuple[CardinalDirection, ...]
