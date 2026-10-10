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
    LandingParticle, LandingTemplate, ParticleMediaAsset, RegionParticleStyle, ReleaseFamily, BloodResponse,
)


def particle_schedule(particle: LandingParticle, family: ReleaseFamily,
                       response: BloodResponse | None, copy: int = 0) -> tuple[float, float, float]:
    """One delay/flight/melt schedule shared by flight, field growth and tails."""
    delay = particle.delay * family.delayScale * (response.delayScale if response else 1)
    duration = particle.duration * family.durationScale * (1.08 if copy else 1) * (
        response.durationScale if response else 1)
    melt = response.meltBase + min(1, particle.size / 2.75) * response.meltSize if response else 0
    return delay, duration, melt


def landed_fraction(particle: LandingParticle, family: ReleaseFamily,
                      response: BloodResponse | None, age: float) -> float:
    delay, duration, melt = particle_schedule(particle, family, response)
    if age < delay + duration:
        return 0
    return min(1, max(0, (age - delay - duration) / melt)) if melt else 1


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


def surface_start_time(asset_id: str, pattern: str, response: BloodResponse) -> float:
    """First deposited particle on the shared clock of this authored region asset."""
    return _surface_start_time(asset_id, pattern, response.delayScale, response.durationScale)


@lru_cache(maxsize=64)
def _surface_start_time(asset_id: str, pattern: str, delay_scale: float, duration_scale: float) -> float:
    style = region_media_assets()[asset_id].region
    assert style is not None
    return min(delay * delay_scale + flight * duration_scale
               for template in style.templates for p in template.particles
               for delay, flight, _ in (particle_schedule(p, style.families[pattern], None),))


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
    response: BloodResponse | None = None


@dataclass(frozen=True, slots=True)
class ResidueRevealSample:
    reveal: ResidueReveal
    elapsed_ms: float


def sample_residue_reveals(changes: tuple[ResidueReveal, ...], elapsed_ms: float) -> tuple[ResidueRevealSample, ...]:
    """Only actual growth gets an override; saturation never paints then erases."""
    return tuple(ResidueRevealSample(row, (elapsed_ms - row.start_ms) * row.rate)
                 for row in changes if elapsed_ms < row.end_ms)
