"""Bounded Pygame source frames for legacy atlases and finite frame storage.

The cache owns immutable, ready-to-blit pixels. File storage changes how a
sample is fetched, not its authored phase clock, registration or direction.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping

import numpy as np
import pygame

from game.animation_types import (
    AnimationData, AuthoredProjectileAsset, BlendMode, Facing8, ProjectileSprite,
)


FrameKey = tuple[Path, tuple[int, int, int, int], int, float, BlendMode]


@dataclass(slots=True)
class ProjectileFrameCache:
    """Session pixel storage; the byte limit counts owned decoded surfaces."""

    limit_bytes: int = 128 * 1024 * 1024
    frames: OrderedDict[FrameKey, pygame.Surface] = field(default_factory=OrderedDict)
    decoded_bytes: int = 0


@dataclass(frozen=True, slots=True)
class FrameCacheUsage:
    decoded_bytes: int
    limit_bytes: int
    frames: int


@dataclass(frozen=True, slots=True)
class ProjectileFrameImage:
    image: pygame.Surface
    blend: int


# Four-camera reviews and concurrent historical cast media share source pixels.
SHARED_PROJECTILE_FRAMES = ProjectileFrameCache()


def frame_cache_usage(cache: ProjectileFrameCache = SHARED_PROJECTILE_FRAMES) -> FrameCacheUsage:
    """Decoded-source diagnostics, independent of cache keys and eviction order."""
    return FrameCacheUsage(cache.decoded_bytes, cache.limit_bytes, len(cache.frames))


def _cached(cache: ProjectileFrameCache, key: FrameKey) -> pygame.Surface | None:
    image = cache.frames.get(key)
    if image is not None:
        cache.frames.move_to_end(key)
    return image


def _reserve(cache: ProjectileFrameCache, size: int) -> None:
    while cache.frames and cache.decoded_bytes + size > cache.limit_bytes:
        _, expired = cache.frames.popitem(last=False)
        cache.decoded_bytes -= expired.get_pitch() * expired.height


def _remember(cache: ProjectileFrameCache, key: FrameKey, image: pygame.Surface) -> pygame.Surface:
    size = image.get_pitch() * image.height
    _reserve(cache, size)
    if size <= cache.limit_bytes:
        cache.frames[key] = image
        cache.decoded_bytes += size
    return image


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
        layers = storage.phases[phase_name].layers
        result = []
        for layer in layers:
            path = data.media_root / layer.pattern.format(direction=direction, frame=frame)
            key = (path, (0, 0, width, height), visual.tint, visual.alpha, layer.blendMode)
            image = _cached(cache, key)
            if image is None:
                _reserve(cache, width * height * 4)
                image = pygame.image.load(path).convert_alpha()
                if image.get_size() != (width, height):
                    raise ValueError(f"projectile frame dimensions differ from its authored asset: {path}")
                image = _remember(cache, key, _prepare(image, visual.tint, visual.alpha, layer.blendMode))
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
