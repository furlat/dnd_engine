"""Bounded Pygame source frames for legacy atlases and finite frame storage.

The cache owns immutable, ready-to-blit pixels. File storage changes how a
sample is fetched, not its authored phase clock, registration or direction.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import gzip
from pathlib import Path
import struct
from typing import Literal, Mapping

import numpy as np
import pygame

from game.animation_types import (
    AnimationData, AuthoredProjectileAsset, BlendMode, Facing8, ProjectileSprite,
)


FrameKey = tuple[Path, tuple[int, int, int, int], int, float, BlendMode | Literal["raw"]]


@dataclass(frozen=True, slots=True)
class SurfacePositions:
    """Raw XYZ and ownership, aligned with the color before any transform."""

    coordinates: np.ndarray
    ownership: np.ndarray
    bounds: tuple[float, float]
    vertical_scale: float
    position_scale: float = 1


@dataclass(frozen=True, slots=True)
class CachedSource:
    image: pygame.Surface
    positions: SurfacePositions | None = None
    offset: tuple[int, int] = (0, 0)

    @property
    def nbytes(self) -> int:
        return (self.image.get_pitch() * self.image.height
                + (self.positions.coordinates.nbytes + self.positions.ownership.nbytes
                   if self.positions is not None else 0))


@dataclass(slots=True)
class ProjectileFrameCache:
    """Session pixel storage; the byte limit counts owned decoded surfaces."""

    limit_bytes: int = 128 * 1024 * 1024
    frames: OrderedDict[FrameKey, CachedSource] = field(default_factory=OrderedDict)
    decoded_bytes: int = 0


@dataclass(frozen=True, slots=True)
class FrameCacheUsage:
    decoded_bytes: int
    limit_bytes: int
    frames: int


@dataclass(frozen=True, slots=True)
class FootpointImage:
    """Raw aligned XY bytes; its alpha byte is data, never coverage."""

    image: pygame.Surface
    bounds: tuple[float, float]


@dataclass(frozen=True, slots=True)
class ProjectileFrameImage:
    image: pygame.Surface
    blend: int
    offset: tuple[float, float] = (0, 0)
    footpoint: FootpointImage | None = None
    positions: SurfacePositions | None = None


# Four-camera reviews and concurrent historical cast media share source pixels.
# Eight 4096px pages cover four cameras with two simultaneous source layers.
# This is a ceiling, allocated only as requested; normal play needs one view.
SHARED_PROJECTILE_FRAMES = ProjectileFrameCache(limit_bytes=640 * 1024 * 1024)


def frame_cache_usage(cache: ProjectileFrameCache = SHARED_PROJECTILE_FRAMES) -> FrameCacheUsage:
    """Decoded-source diagnostics, independent of cache keys and eviction order."""
    return FrameCacheUsage(cache.decoded_bytes, cache.limit_bytes, len(cache.frames))


def _cached(cache: ProjectileFrameCache, key: FrameKey) -> pygame.Surface | None:
    source = cache.frames.get(key)
    if source is not None:
        cache.frames.move_to_end(key)
        return source.image
    return None


def _reserve(cache: ProjectileFrameCache, size: int) -> None:
    while cache.frames and cache.decoded_bytes + size > cache.limit_bytes:
        _, expired = cache.frames.popitem(last=False)
        cache.decoded_bytes -= expired.nbytes


def _remember(cache: ProjectileFrameCache, key: FrameKey, image: pygame.Surface) -> pygame.Surface:
    _remember_source(cache, key, CachedSource(image))
    return image


def _remember_source(cache: ProjectileFrameCache, key: FrameKey, source: CachedSource) -> None:
    size = source.nbytes
    _reserve(cache, size)
    if size <= cache.limit_bytes:
        cache.frames[key] = source
        cache.decoded_bytes += size


def _prepare(image: pygame.Surface, tint: int, alpha: float, blend: BlendMode) -> pygame.Surface:
    """Process an owned source once, before it becomes immutable cache data."""
    if tint != 0xFFFFFF:
        image.fill((tint >> 16 & 255, tint >> 8 & 255, tint & 255, 255),
                   special_flags=pygame.BLEND_RGBA_MULT)
    if alpha != 1:
        image.set_alpha(round(alpha * 255))
    if blend == "add":
        # RGB_ADD ignores source alpha. Preserve the existing rendering rule.
        rgb = pygame.surfarray.pixels3d(image)
        opacity = pygame.surfarray.array_alpha(image).astype(np.float32) * alpha / 255
        rgb[:] = np.rint(rgb * opacity[:, :, None]).astype(np.uint8)
        del rgb
    return image


def _raw_part(cache: ProjectileFrameCache, path: Path,
              rectangle: tuple[int, int, int, int]) -> pygame.Surface:
    """Read data pixels without display conversion or any material operation."""
    key: FrameKey = (path, rectangle, 0xFFFFFF, 1, "raw")
    image = _cached(cache, key)
    if image is None:
        page_key: FrameKey = (path, (0, 0, 0, 0), 0xFFFFFF, 1, "raw")
        page = _cached(cache, page_key)
        if page is None:
            page = _remember(cache, page_key, pygame.image.load(path))
        image = _remember(cache, key, page.subsurface(rectangle).copy())
    return image


def _surface_packet(cache: ProjectileFrameCache, path: Path, blends: tuple[Literal["normal", "add"], ...],
                    visual: ProjectileSprite, bounds: tuple[float, float], vertical_scale: float,
                    position_scale: float) -> tuple[CachedSource, ...]:
    keys: tuple[FrameKey, ...] = tuple((path, (index, 0, 0, 0), visual.tint, visual.alpha, blend)
                                     for index, blend in enumerate(blends))
    if all(key in cache.frames for key in keys):
        for key in keys:
            cache.frames.move_to_end(key)
        return tuple(cache.frames[key] for key in keys)
    payload = gzip.decompress(path.read_bytes())
    width, height, ox, oy = struct.unpack_from("<HHhh", payload)
    pixels, offset = width * height, 8
    sources = []
    for key, blend in zip(keys, blends):
        image = pygame.image.frombytes(payload[offset:offset + pixels * 4], (width, height), "RGBA")
        offset += pixels * 4
        xyz = np.frombuffer(payload, dtype=">u2", count=pixels * 3, offset=offset).reshape(
            height, width, 3).transpose(1, 0, 2).copy()
        offset += pixels * 6
        owners = np.frombuffer(payload, dtype=np.uint8, count=pixels, offset=offset).reshape(height, width).T.copy()
        offset += pixels
        xyz.setflags(write=False)
        owners.setflags(write=False)
        source = CachedSource(_prepare(image, visual.tint, visual.alpha, blend),
            SurfacePositions(xyz, owners, bounds, vertical_scale, position_scale), (ox, oy))
        prior = cache.frames.pop(key, None)
        if prior is not None:
            cache.decoded_bytes -= prior.nbytes
        _remember_source(cache, key, source)
        sources.append(source)
    return tuple(sources)


def projectile_frame_layers(
    data: AnimationData, asset: AuthoredProjectileAsset,
    phase_name: Literal["cast", "travel", "impact"], frame: int, direction: Facing8,
    visual: ProjectileSprite, legacy_rows: Mapping[tuple[str, int], pygame.Surface], *,
    cache: ProjectileFrameCache = SHARED_PROJECTILE_FRAMES,
) -> tuple[ProjectileFrameImage, ...]:
    """Resolve one phase-local sample without loading other phases or directions.

    Returned images are shared read-only sources. A caller applying a physical
    mask must own its working surface rather than changing these cached pixels.
    """
    phase = {"cast": asset.phases.cast, "travel": asset.phases.travel,
             "impact": asset.phases.impact}[phase_name]
    if phase is None or not 0 <= frame < phase.frames:
        raise ValueError(f"projectile sample is outside its authored phase: {asset.assetId}/{phase_name}/{frame}")
    width, height = asset.frame.width, asset.frame.height
    storage = data.projectile_storage.get(asset.assetId)
    if storage is not None:
        packet = storage.phases[phase_name].surfaceFrames
        if packet is not None:
            pivot = (asset.anchorsByFacing or {}).get(direction, asset.anchor)
            asset_pivot = pivot.x * asset.frame.width, pivot.y * asset.frame.height
            files: list[tuple[str, tuple[Literal["normal", "add"], ...], tuple[float, float]]]
            if packet.componentsByFacing is not None:
                files = [(part.pattern, (part.blendMode,), part.pivot)
                         for part in packet.componentsByFacing[direction]]
            else:
                assert packet.pattern is not None
                files = [(packet.pattern, packet.blendModes, asset_pivot)]
            result = []
            for pattern, blends, source_pivot in files:
                path = data.media_root / pattern.format(direction=direction, frame=packet.frameIndices[frame])
                sources = _surface_packet(cache, path, blends, visual, packet.bounds,
                                          packet.verticalScale, packet.positionScale)
                for source, blend in zip(sources, blends):
                    offset = tuple(source.offset[i] + round(source_pivot[i]) - source_pivot[i]
                                   + asset_pivot[i] for i in range(2))
                    result.append(ProjectileFrameImage(source.image,
                        pygame.BLEND_RGB_ADD if blend == "add" else 0, (offset[0], offset[1]),
                        positions=source.positions))
            return tuple(result)
        layers = storage.phases[phase_name].layers
        result = []
        for layer in layers:
            parts = layer.partsByFacing[direction] if layer.partsByFacing is not None else layer.parts
            if parts is not None:
                for part in parts[frame]:
                    path = data.media_root / part.file
                    alpha = visual.alpha * layer.gain
                    key = (path, part.rect, visual.tint, alpha, layer.blendMode)
                    image = _cached(cache, key)
                    if image is None:
                        page_key = (path, (0, 0, 0, 0), 0xFFFFFF, 1.0, "normal")
                        sheet = _cached(cache, page_key)
                        if sheet is None:
                            sheet = _remember(cache, page_key, pygame.image.load(path).convert_alpha())
                        image = _remember(cache, key, _prepare(sheet.subsurface(part.rect).copy(),
                                                              visual.tint, alpha, layer.blendMode))
                    footpoint = (FootpointImage(_raw_part(cache, data.media_root / part.footpoint.file,
                        part.rect), part.footpoint.bounds) if part.footpoint is not None else None)
                    result.append(ProjectileFrameImage(image,
                        pygame.BLEND_RGB_ADD if layer.blendMode == "add" else 0, part.offset, footpoint))
                continue
            if layer.pages is not None:
                page = next(page for page in layer.pages[direction]
                            if page.firstFrame <= frame < page.firstFrame + page.frameCount)
                path = data.media_root / page.file
                local = frame - page.firstFrame
                rectangle = ((local % page.columns) * width, (local // page.columns) * height, width, height)
            else:
                assert layer.pattern is not None
                path = data.media_root / layer.pattern.format(direction=direction, frame=frame)
                rectangle = (0, 0, width, height)
            alpha = visual.alpha * layer.gain
            key = (path, rectangle, visual.tint, alpha, layer.blendMode)
            image = _cached(cache, key)
            if image is None:
                _reserve(cache, width * height * 4)
                if layer.pages is not None:
                    page_key = (path, (0, 0, 0, 0), 0xFFFFFF, 1.0, "normal")
                    sheet = _cached(cache, page_key)
                    if sheet is None:
                        sheet = _remember(cache, page_key, pygame.image.load(path).convert_alpha())
                    image = sheet.subsurface(rectangle).copy()
                else:
                    image = pygame.image.load(path).convert_alpha()
                if image.get_size() != (width, height):
                    raise ValueError(f"projectile frame dimensions differ from its authored asset: {path}")
                image = _remember(cache, key, _prepare(image, visual.tint, alpha, layer.blendMode))
            result.append(ProjectileFrameImage(image, pygame.BLEND_RGB_ADD if layer.blendMode == "add" else 0))
        return tuple(result)
    if visual.blendMode == "screen":
        raise ValueError("screen blend requires a separate pixel parity proof")
    row, column = asset.rowOrder.index(direction), phase.start + frame
    rectangle = (column * width, row * height, width, height)
    key = (data.resources[asset.sheet], rectangle, visual.tint, visual.alpha, visual.blendMode)
    image = _cached(cache, key)
    if image is None:
        _reserve(cache, width * height * 4)
        # Own this crop; a cached subsurface would retain the entire atlas row.
        image = legacy_rows[asset.assetId, row].subsurface((column * width, 0, width, height)).copy()
        image = _remember(cache, key, _prepare(image, visual.tint, visual.alpha, visual.blendMode))
    return (ProjectileFrameImage(image, pygame.BLEND_RGB_ADD if visual.blendMode == "add" else 0),)
