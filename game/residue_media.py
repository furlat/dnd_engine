"""Shared landing artwork and passive floor-reveal values on the media clock."""

from dataclasses import dataclass
from functools import lru_cache
import json
from math import cos, floor, sin
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from dnd.types.residues import ResidueEllipse, TileResidueState
from game.animation_types import (
    LandingTemplate, ParticleMediaAsset, RegionParticleStyle, ReleaseFamily,
)


@lru_cache(maxsize=1)
def region_media_assets() -> Mapping[str, ParticleMediaAsset]:
    """Read one checked-in value document, shared by floor and action media."""
    raw = json.loads((Path(__file__).parent / "data/neuroclient/body-release-regions.json").read_text())
    templates = tuple(LandingTemplate.model_validate_json(json.dumps(row)) for row in raw["templates"])
    families = MappingProxyType({key: ReleaseFamily(**row) for key, row in raw["families"].items()})
    return MappingProxyType({row["assetId"]: ParticleMediaAsset(
        assetId=row["assetId"], legacyAssetId=row.get("legacyAssetId"), frames=row.get("frames", 24), defaultFps=24, colors=tuple(row["colors"]),
        tailSeconds=row.get("tailSeconds", .014), tailMinPx=row.get("tailMinPx", 1),
        tailMaxPx=row.get("tailMaxPx", 12), snapPx=row.get("snapPx", 1),
        region=RegionParticleStyle(templates=tuple(LandingTemplate.model_validate_json(json.dumps(value))
            for value in row["templates"]) if "templates" in row else templates, families=families,
            primitive=row["primitive"], palette=tuple(row["palette"]) if row["palette"] else None),
    ) for row in raw["materials"]})


def landing_template(style: RegionParticleStyle, ellipse: ResidueEllipse) -> LandingTemplate:
    # Stable world variation shared across clipped pieces, including later sight.
    index = round(ellipse.center[0] * 100) * 31 + round(ellipse.center[1] * 100) * 17
    return style.templates[index % len(style.templates)]


def landing_point(ellipse: ResidueEllipse, target: tuple[float, float]) -> tuple[float, float]:
    x, y = target[0] * ellipse.radius_x, target[1] * ellipse.radius_y
    co, si = cos(ellipse.angle), sin(ellipse.angle)
    return ellipse.center[0] + x * co - y * si, ellipse.center[1] + x * si + y * co


def target_cell(point: tuple[float, float]) -> tuple[int, int]:
    return floor(point[0] + .5), floor(point[1] + .5)


@dataclass(frozen=True, slots=True)
class ResidueReveal:
    position: tuple[int, int]
    before: TileResidueState | None
    after: TileResidueState
    asset: ParticleMediaAsset
    pattern: str
    start_ms: float
    end_ms: float
    rate: float


@dataclass(frozen=True, slots=True)
class ResidueRevealSample:
    reveal: ResidueReveal
    elapsed_ms: float


def sample_residue_reveals(changes: tuple[ResidueReveal, ...], elapsed_ms: float) -> tuple[ResidueRevealSample, ...]:
    """Only actual growth gets an override; saturation never paints then erases."""
    return tuple(ResidueRevealSample(row, (elapsed_ms - row.start_ms) * row.rate)
                 for row in changes if elapsed_ms < row.end_ms)
