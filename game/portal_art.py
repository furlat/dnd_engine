"""Passive camera banks and finite transfer markers for ground portals."""

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping


@dataclass(frozen=True, slots=True)
class PortalBank:
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
    sheet: Path
    front: Path
    cell: tuple[int, int]
    pivot: tuple[float, float]
    opening: tuple[int, ...]
    closing: tuple[int, ...]
    fps: float


@dataclass(frozen=True, slots=True)
class PortalAperture:
    shape: Literal["diamond", "ellipse"]
    half_width_px: float
    half_height_px: float


@dataclass(frozen=True, slots=True)
class PortalArt:
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
def load_portal_art() -> Mapping[str, PortalArt]:
    root = Path(__file__).resolve().parent
    document = json.loads((root / "data/portals.json").read_text())

    def bank(row: dict) -> PortalBank:
        return PortalBank(tuple(tuple(root / "assets" / page for page in pages) for pages in row["pages"]),
            tuple(row["cell"]), row["columns"], row["framesPerPage"], tuple(row["pivot"]),
            row["fps"], row["openingFrames"], row["holdFrames"], row["closingFrames"])

    def aperture(row: dict) -> PortalAperture:
        return PortalAperture(row["shape"], row["halfWidthPx"], row["halfHeightPx"])

    banks = {key: bank(row) for key, row in document["banks"].items()}
    result = {}
    for identity, row in document["bindings"].items():
        h = row.get("hatch")
        hatch = None if h is None else PortalHatch(root / "assets" / h["sheet"], root / "assets" / h["front"],
            tuple(h["cell"]), tuple(h["pivot"]), tuple(h["opening"]), tuple(h["closing"]), h["fps"])
        result[identity] = PortalArt(banks[row["entrance"]], banks[row["exit"]], hatch, row["scale"],
            row["fallDelayMs"], row["fallMs"], row["emergeMs"], row["fallDepthPx"], row["transitMs"], row["exitHoldMs"],
            aperture(row["entranceAperture"]), aperture(row["exitAperture"]))
    return MappingProxyType(result)


def portal_frame(bank: PortalBank, elapsed_ms: float, *, closing: bool = False) -> int:
    frame = max(0, int(elapsed_ms * bank.fps / 1000))
    if closing:
        return bank.opening_frames + bank.hold_frames + min(bank.closing_frames - 1, frame)
    if frame < bank.opening_frames:
        return frame
    return bank.opening_frames + (frame - bank.opening_frames) % bank.hold_frames
