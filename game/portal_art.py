"""Passive camera banks and finite transfer markers for ground portals."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, PositiveFloat, PositiveInt, NonNegativeFloat, NonNegativeInt, model_validator


class _PortalSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class PortalBankSource(_PortalSource):
    pages: Annotated[tuple[tuple[str, ...], ...], Field(min_length=4, max_length=4)]
    cell: tuple[PositiveInt, PositiveInt]
    columns: PositiveInt
    framesPerPage: PositiveInt
    pivot: tuple[FiniteFloat, FiniteFloat]
    fps: PositiveFloat
    openingFrames: NonNegativeInt
    holdFrames: PositiveInt
    closingFrames: PositiveInt

    @model_validator(mode="after")
    def frame_capacity(self) -> "PortalBankSource":
        count = self.openingFrames + self.holdFrames + self.closingFrames
        if any(len(pages) * self.framesPerPage < count for pages in self.pages):
            raise ValueError("portal pages must contain the opening, hold and closing frames")
        return self


class PortalHatchSource(_PortalSource):
    sheet: str
    front: str
    cell: tuple[PositiveInt, PositiveInt]
    pivot: tuple[FiniteFloat, FiniteFloat]
    opening: Annotated[tuple[NonNegativeInt, ...], Field(min_length=1)]
    closing: Annotated[tuple[NonNegativeInt, ...], Field(min_length=1)]
    fps: PositiveFloat


class PortalApertureSource(_PortalSource):
    shape: Literal["diamond", "ellipse"]
    halfWidthPx: PositiveFloat
    halfHeightPx: PositiveFloat


class PortalArtSource(_PortalSource):
    entrance: str
    exit: str
    hatch: PortalHatchSource | None = None
    scale: PositiveFloat
    fallDelayMs: NonNegativeFloat
    fallMs: PositiveFloat
    emergeMs: PositiveFloat
    fallDepthPx: PositiveFloat
    transitMs: NonNegativeFloat
    exitHoldMs: NonNegativeFloat
    entranceAperture: PortalApertureSource
    exitAperture: PortalApertureSource


class DoorwayArt(_PortalSource):
    """Upright native banks; finite strides are presentation, never grid steps."""
    back: str
    front: str
    scale: PositiveFloat
    openingMs: PositiveFloat = 750
    walkingDelayMs: NonNegativeFloat = 400
    strideMs: PositiveFloat = 700
    strideCells: PositiveFloat = .9
    thresholdCells: PositiveFloat = .35
    transitMs: NonNegativeFloat = 150
    closingMs: PositiveFloat = 600
    holdFirstFrame: NonNegativeInt = 24
    holdEndFrame: PositiveInt = 65
    fps: PositiveFloat = 32


class PortalDocument(_PortalSource):
    banks: dict[str, PortalBankSource]
    bindings: dict[str, PortalArtSource]
    doorways: dict[str, DoorwayArt] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PortalBank:
    __pydantic_config__ = ConfigDict(extra="forbid")

    pages: tuple[tuple[Path, ...], ...]
    cell: tuple[int, int]
    columns: int
    frames_per_page: int
    pivot: tuple[float, float]
    fps: float
    opening_frames: int
    hold_frames: int
    closing_frames: int


@dataclass(frozen=True, slots=True)
class PortalHatch:
    __pydantic_config__ = ConfigDict(extra="forbid")

    sheet: Path
    front: Path
    cell: tuple[int, int]
    pivot: tuple[float, float]
    opening: tuple[int, ...]
    closing: tuple[int, ...]
    fps: float


@dataclass(frozen=True, slots=True)
class PortalAperture:
    __pydantic_config__ = ConfigDict(extra="forbid")

    shape: Literal["diamond", "ellipse"]
    half_width_px: float
    half_height_px: float


@dataclass(frozen=True, slots=True)
class PortalArt:
    __pydantic_config__ = ConfigDict(extra="forbid")

    entrance: PortalBank
    exit: PortalBank
    hatch: PortalHatch | None
    scale: float
    fall_delay_ms: float
    fall_ms: float
    emerge_ms: float
    fall_depth_px: float
    transit_ms: float
    exit_hold_ms: float
    entrance_aperture: PortalAperture
    exit_aperture: PortalAperture


@lru_cache(maxsize=1)
def load_portal_art() -> Mapping[str, PortalArt | DoorwayArt]:
    root = Path(__file__).resolve().parent
    document = PortalDocument.model_validate_json((root / "data/portals.json").read_text())
    banks = {key: PortalBank(
        tuple(tuple(root / "assets" / page for page in pages) for pages in row.pages),
        row.cell, row.columns, row.framesPerPage, row.pivot, row.fps,
        row.openingFrames, row.holdFrames, row.closingFrames)
        for key, row in document.banks.items()}
    result: dict[str, PortalArt | DoorwayArt] = dict(document.doorways)
    for identity, row in document.bindings.items():
        h = row.hatch
        hatch = None if h is None else PortalHatch(root / "assets" / h.sheet, root / "assets" / h.front,
            h.cell, h.pivot, h.opening, h.closing, h.fps)
        result[identity] = PortalArt(banks[row.entrance], banks[row.exit], hatch, row.scale,
            row.fallDelayMs, row.fallMs, row.emergeMs, row.fallDepthPx, row.transitMs, row.exitHoldMs,
            PortalAperture(row.entranceAperture.shape, row.entranceAperture.halfWidthPx, row.entranceAperture.halfHeightPx),
            PortalAperture(row.exitAperture.shape, row.exitAperture.halfWidthPx, row.exitAperture.halfHeightPx))
    return MappingProxyType(result)


def portal_frame(bank: PortalBank, elapsed_ms: float, *, closing: bool = False) -> int:
    frame = max(0, int(elapsed_ms * bank.fps / 1000))
    if closing:
        return bank.opening_frames + bank.hold_frames + min(bank.closing_frames - 1, frame)
    if frame < bank.opening_frames:
        return frame
    return bank.opening_frames + (frame - bank.opening_frames) % bank.hold_frames
