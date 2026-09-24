"""Passive registered images shared by world and actor presentation."""

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, ConfigDict, PositiveFloat, PositiveInt, FiniteFloat, NonNegativeInt, TypeAdapter, model_validator


PixelRect = tuple[NonNegativeInt, NonNegativeInt, PositiveInt, PositiveInt]


class ImageRegionSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    rect: PixelRect


@dataclass(frozen=True, slots=True)
class ImageRegion:
    """One untrimmed source cell within a packed raster page."""

    path: Path
    rect: tuple[int, int, int, int]


class ImageResourceSource(BaseModel):
    """Unscaled pixel registration, decoded without touching the raster."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    path: str
    native_size: tuple[PositiveInt, PositiveInt]
    pivot: tuple[FiniteFloat, FiniteFloat]
    scale: PositiveFloat
    rect: PixelRect | None = None

    @model_validator(mode="after")
    def untrimmed_region(self) -> "ImageResourceSource":
        if self.rect is not None and self.rect[2:] != self.native_size:
            raise ValueError("packed image rectangle must retain native_size")
        return self


_IMAGE_RESOURCES = TypeAdapter(dict[str, ImageResourceSource])


@dataclass(frozen=True, slots=True)
class AssetSpec:
    asset_id: str
    path: Path
    native_size: tuple[int, int]
    pivot: tuple[float, float]
    scale: float
    rect: tuple[int, int, int, int] | None = None


def image_resources(rows: Mapping[str, object], root: Path) -> dict[str, AssetSpec]:
    """Read registration values without opening or auditing image files."""
    parsed = _IMAGE_RESOURCES.validate_python(rows)
    return {identity: AssetSpec(identity, root / row.path, row.native_size, row.pivot, row.scale, row.rect)
            for identity, row in parsed.items()}
