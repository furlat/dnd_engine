"""Immutable dependency-neutral area presentation geometry.

The runtime AoE models own targeting and propagation. These snapshots retain
only the exact declared geometry needed to present or replay a cast without
consulting a live action, entity, grid, or registry.
"""

from typing import Annotated, Literal, TypeAlias, Union

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


Position: TypeAlias = tuple[int, int]
Direction: TypeAlias = tuple[int, int]


class PresentationGeometryModel(BaseModel):
    """Strict immutable base for cold geometry facts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SpherePresentationGeometry(PresentationGeometryModel):
    """A sphere projected onto the two-dimensional encounter grid."""

    shape: Literal["sphere"] = "sphere"
    center: Position
    radius_feet: int = Field(ge=0)


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
    radius_feet: int = Field(ge=0)
    height_feet: int = Field(gt=0)


class WallSegment(PresentationGeometryModel):
    """Wall centerline endpoints in native grid units; cell centers are integers."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    form: Literal["segment"] = "segment"
    start: tuple[float, float]
    end: tuple[float, float]

    @model_validator(mode="after")
    def validate_segment(self) -> "WallSegment":
        if self.start == self.end:
            raise ValueError("A wall segment must have positive length")
        return self


class WallRing(PresentationGeometryModel):
    """A circular wall centerline, distinct from a filled sphere footprint."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    form: Literal["ring"] = "ring"
    center: tuple[float, float]
    radius_feet: float = Field(gt=0)


class WallPolyline(PresentationGeometryModel):
    """Ordered connected ground segments, including an explicit closing edge."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    form: Literal["polyline"] = "polyline"
    points: tuple[tuple[float, float], ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_path(self) -> "WallPolyline":
        if any(first == second for first, second in zip(self.points, self.points[1:])):
            raise ValueError("Consecutive wall vertices must differ")
        return self


class WallDome(PresentationGeometryModel):
    """Hollow ground-anchored hemisphere; its projected interior is not solid."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    form: Literal["dome"] = "dome"
    center: tuple[float, float]
    radius_feet: float = Field(gt=0, le=10)


class WallAssemblyPresentationGeometry(PresentationGeometryModel):
    """Passive construction geometry, distinct from Fire's accepted wall banks."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    shape: Literal["wall_assembly"] = "wall_assembly"
    path: Annotated[Union[WallSegment, WallRing, WallPolyline, WallDome], Field(discriminator="form")]
    base_height_steps: StrictInt
    width_feet: float = Field(gt=0)
    height_feet: float = Field(gt=0)


class WallPresentationGeometry(PresentationGeometryModel):
    """Immutable wall placement, retaining physical rather than rasterized width."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    shape: Literal["wall"] = "wall"
    path: Annotated[Union[WallSegment, WallRing], Field(discriminator="form")]
    base_height_steps: StrictInt = Field(description="Wall base elevation in native five-foot support steps.")
    width_feet: float = Field(gt=0)
    height_feet: float = Field(gt=0)
    hot_side: Literal["left", "right", "inside", "outside"] | None = None


AoEPresentationGeometry: TypeAlias = Annotated[
    Union[
        SpherePresentationGeometry,
        ConePresentationGeometry,
        LinePresentationGeometry,
        CubePresentationGeometry,
        CylinderPresentationGeometry,
        WallPresentationGeometry,
        WallAssemblyPresentationGeometry,
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
    "WallPresentationGeometry",
    "WallRing",
    "WallSegment",
    "WallAssemblyPresentationGeometry",
    "WallDome",
    "WallPolyline",
]
