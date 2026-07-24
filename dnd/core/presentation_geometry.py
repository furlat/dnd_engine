"""Immutable dependency-neutral area presentation geometry.

The runtime AoE models own targeting and propagation. These snapshots retain
only the exact declared geometry needed to present or replay a cast without
consulting a live action, entity, grid, or registry.
"""

from typing import Annotated, Literal, TypeAlias, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


Position: TypeAlias = tuple[int, int]
Direction: TypeAlias = tuple[int, int]


class PresentationGeometryModel(BaseModel):
    """Strict immutable base for cold geometry facts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SpherePresentationGeometry(PresentationGeometryModel):
    """A sphere projected onto the two-dimensional encounter grid."""

    shape: Literal["sphere"] = "sphere"
    center: Position
    radius_feet: int = Field(gt=0)


class ConePresentationGeometry(PresentationGeometryModel):
    """A cone originating at one cell and oriented by a direction vector."""

    shape: Literal["cone"] = "cone"
    origin: Position
    direction: Direction
    length_feet: int = Field(gt=0)
    angle_degrees: int = Field(gt=0, le=360)


class LinePresentationGeometry(PresentationGeometryModel):
    """A widened line originating at one cell."""

    shape: Literal["line"] = "line"
    origin: Position
    direction: Direction
    length_feet: int = Field(gt=0)
    width_feet: int = Field(gt=0)


class CubePresentationGeometry(PresentationGeometryModel):
    """A centered or directionally extended square/cube footprint."""

    shape: Literal["cube"] = "cube"
    origin: Position
    direction: Direction | None = None
    size_feet: int = Field(gt=0)
    centered: bool

    @model_validator(mode="after")
    def validate_centering(self) -> "CubePresentationGeometry":
        """Require only directional cubes to carry an orientation."""
        if self.centered and self.direction is not None:
            raise ValueError("centered cube cannot carry a direction")
        if not self.centered and self.direction is None:
            raise ValueError("directional cube requires a direction")
        return self


class CylinderPresentationGeometry(PresentationGeometryModel):
    """A cylinder projected as a circle with retained vertical extent."""

    shape: Literal["cylinder"] = "cylinder"
    center: Position
    radius_feet: int = Field(gt=0)
    height_feet: int = Field(gt=0)


AoEPresentationGeometry: TypeAlias = Annotated[
    Union[
        SpherePresentationGeometry,
        ConePresentationGeometry,
        LinePresentationGeometry,
        CubePresentationGeometry,
        CylinderPresentationGeometry,
    ],
    Field(discriminator="shape"),
]


__all__ = [
    "AoEPresentationGeometry",
    "ConePresentationGeometry",
    "CubePresentationGeometry",
    "CylinderPresentationGeometry",
    "Direction",
    "LinePresentationGeometry",
    "Position",
    "PresentationGeometryModel",
    "SpherePresentationGeometry",
]
