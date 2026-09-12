"""Exact local asset catalogs and finite pygame Surface caches."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, cast

import numpy as np
import pygame


PACKAGE_ROOT = Path(__file__).resolve().parent
ASSET_ROOT = PACKAGE_ROOT / "assets"
DATA_ROOT = PACKAGE_ROOT / "data"


@dataclass(frozen=True, slots=True)
class AssetSpec:
    """One local raster resource used by the pygame presentation."""

    asset_id: str
    path: Path
    native_size: tuple[int, int]
    pivot: tuple[float, float]
    scale: float


@dataclass(frozen=True, slots=True)
class AssetCatalog:
    """Direct resources, bindings, animation, and Water constants."""

    resources: Mapping[str, AssetSpec]
    bindings: Mapping[str, object]
    flame_frames: tuple[str, ...]
    flame_fps: int
    water: Mapping[str, object]


def catalog_from_documents(
    assets: dict[str, object], bindings: dict[str, object]
) -> AssetCatalog:
    """Assemble the checked-in catalog values without filesystem validation."""
    raw_resources = cast(dict, assets["resources"])
    flame = cast(dict, cast(dict, assets["animations"])["torch.flame"])
    resources = {
        asset_id: AssetSpec(
            asset_id=asset_id,
            path=ASSET_ROOT / raw["path"],
            native_size=(raw["native_size"][0], raw["native_size"][1]),
            pivot=(float(raw["pivot"][0]), float(raw["pivot"][1])),
            scale=float(raw["scale"]),
        )
        for asset_id, raw in raw_resources.items()
    }
    return AssetCatalog(
        resources=MappingProxyType(resources),
        bindings=MappingProxyType(bindings),
        flame_frames=tuple(flame["frames"]),
        flame_fps=flame["fps"],
        water=MappingProxyType(cast(dict, assets["water"])),
    )


def load_catalog() -> AssetCatalog:
    """Read bundled catalog values; decode each used raster in the presentation session."""
    return catalog_from_documents(
        json.loads((DATA_ROOT / "assets.json").read_text(encoding="utf-8")),
        json.loads((DATA_ROOT / "world_bindings.json").read_text(encoding="utf-8")),
    )


class SurfaceCache:
    """Canonical decoded Surfaces plus finite scaled/tinted derivatives."""

    def __init__(self, catalog: AssetCatalog) -> None:
        if pygame.display.get_surface() is None:
            raise RuntimeError("pygame display must be initialized before asset loading")
        self.catalog = catalog
        self._canonical: dict[str, pygame.Surface] = {}
        self._scaled: dict[tuple[str, float], pygame.Surface] = {}
        self._treated: dict[tuple[str, float, tuple[float, float, float]], pygame.Surface] = {}
        self._alpha_bounds: dict[tuple[str, float], tuple[int, int, int, int]] = {}
        self._cropped_treated: dict[
            tuple[str, float, tuple[float, float, float]], pygame.Surface
        ] = {}
        self._rgb: dict[str, np.ndarray] = {}
        self._qualified_alpha_counts: dict[tuple[str, float, float], int] = {}
        self.debug_font = pygame.font.Font(None, 18)
        self.cache_hits = 0
        self.cache_rebuilds = 0

    def canonical(self, asset_id: str) -> pygame.Surface:
        """Decode a requested world raster once in this presentation session."""
        cached = self._canonical.get(asset_id)
        if cached is not None:
            return cached
        spec = self.catalog.resources[asset_id]
        try:
            surface = pygame.image.load(spec.path).convert_alpha()
        except pygame.error as exc:
            raise ValueError(f"cannot decode asset {asset_id}: {exc}") from exc
        self._canonical[asset_id] = surface
        return surface

    def rgb(self, asset_id: str) -> np.ndarray:
        """Return one cached x-major RGB sample array for a canonical texture."""
        cached = self._rgb.get(asset_id)
        if cached is not None:
            self.cache_hits += 1
            return cached
        values = pygame.surfarray.array3d(self.canonical(asset_id)).astype(np.float32)
        values *= np.float32(1.0 / 255.0)
        values.setflags(write=False)
        self._rgb[asset_id] = values
        self.cache_rebuilds += 1
        return values

    def qualified_alpha_pixels(
        self,
        asset_id: str,
        zoom: float,
        cutoff: float,
    ) -> int:
        """Count cached scaled-mask pixels admitted by one material cutoff."""
        key = asset_id, zoom, cutoff
        cached = self._qualified_alpha_counts.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        alpha = pygame.surfarray.array_alpha(self.scaled(asset_id, zoom))
        count = int(np.count_nonzero(alpha.astype(np.float32) / 255.0 >= cutoff))
        self._qualified_alpha_counts[key] = count
        self.cache_rebuilds += 1
        return count

    def scaled(self, asset_id: str, zoom: float) -> pygame.Surface:
        """Return a nearest-neighbor scaled immutable-source derivative."""
        key = asset_id, zoom
        cached = self._scaled.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        spec = self.catalog.resources[asset_id]
        source = self.canonical(asset_id)
        factor = zoom * spec.scale
        size = (
            max(1, round(spec.native_size[0] * factor)),
            max(1, round(spec.native_size[1] * factor)),
        )
        scaled = pygame.transform.scale(source, size)
        self._scaled[key] = scaled
        self.cache_rebuilds += 1
        return scaled

    def treated(
        self,
        asset_id: str,
        zoom: float,
        multiplier: tuple[float, float, float],
    ) -> pygame.Surface:
        """Multiply only RGB channels while preserving copied alpha."""
        key = asset_id, zoom, multiplier
        cached = self._treated.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        result = self.scaled(asset_id, zoom).copy()
        pixels = pygame.surfarray.pixels3d(result)
        multiplied = np.clip(
            pixels.astype(np.float32) * np.asarray(multiplier, dtype=np.float32),
            0,
            255,
        ).astype(np.uint8)
        pixels[...] = multiplied
        del pixels
        self._treated[key] = result
        self.cache_rebuilds += 1
        return result

    def alpha_bounds(self, asset_id: str, zoom: float) -> tuple[int, int, int, int]:
        """Return the cached nontransparent bound within one scaled raster."""
        key = asset_id, zoom
        cached = self._alpha_bounds.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        rect = self.scaled(asset_id, zoom).get_bounding_rect(min_alpha=1)
        if rect.width <= 0 or rect.height <= 0:
            raise ValueError(f"asset {asset_id} has no nontransparent pixels")
        bounds = rect.x, rect.y, rect.width, rect.height
        self._alpha_bounds[key] = bounds
        self.cache_rebuilds += 1
        return bounds

    def cropped_treated(
        self,
        asset_id: str,
        zoom: float,
        multiplier: tuple[float, float, float],
    ) -> pygame.Surface:
        """Return a treated raster cropped only around zero-alpha margins."""
        key = asset_id, zoom, multiplier
        cached = self._cropped_treated.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        bounds = self.alpha_bounds(asset_id, zoom)
        cropped = self.treated(asset_id, zoom, multiplier).subsurface(bounds)
        self._cropped_treated[key] = cropped
        self.cache_rebuilds += 1
        return cropped

    def blit_position(
        self,
        asset_id: str,
        zoom: float,
        contact: tuple[float, float],
    ) -> tuple[int, int]:
        """Resolve the authored pivot against one projected support contact."""
        spec = self.catalog.resources[asset_id]
        factor = zoom * spec.scale
        return (
            round(contact[0] - spec.pivot[0] * factor),
            round(contact[1] - spec.pivot[1] * factor),
        )


def flame_frame_index(time_seconds: float, *, frame_count: int = 16, fps: int = 10) -> int:
    """Select the exact authored flame frame from the shared presentation clock."""
    return int(max(0.0, time_seconds) * fps) % frame_count


__all__ = [
    "ASSET_ROOT",
    "AssetCatalog",
    "AssetSpec",
    "SurfaceCache",
    "flame_frame_index",
    "load_catalog",
]
