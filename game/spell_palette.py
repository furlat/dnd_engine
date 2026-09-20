"""Exact authored palette mapping, shared by offline overlays and cached bodies."""

from collections import OrderedDict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import pygame

from game.animation_types import PaletteTreatment


@dataclass(slots=True)
class PaletteImageCache:
    limit_bytes: int = 32 * 1024 * 1024
    images: OrderedDict[tuple[object, ...], pygame.Surface] = field(default_factory=OrderedDict)
    decoded_bytes: int = 0


BODY_PALETTES = PaletteImageCache()


def cached_palette(key: tuple[object, ...], cache: PaletteImageCache = BODY_PALETTES) -> pygame.Surface | None:
    image = cache.images.get(key)
    if image is not None:
        cache.images.move_to_end(key)
    return image


def retain_palette(key: tuple[object, ...], image: pygame.Surface,
                   cache: PaletteImageCache = BODY_PALETTES) -> pygame.Surface:
    size = image.get_pitch() * image.height
    while cache.images and cache.decoded_bytes + size > cache.limit_bytes:
        _, expired = cache.images.popitem(last=False)
        cache.decoded_bytes -= expired.get_pitch() * expired.height
    if size <= cache.limit_bytes:
        cache.images[key] = image
        cache.decoded_bytes += size
    return image


@lru_cache(maxsize=8)
def palette_noise(path: Path) -> pygame.Surface:
    return pygame.image.load(path).convert_alpha()


def recolor_palette(image: pygame.Surface, treatment: PaletteTreatment, *,
                    noise: pygame.Surface | None = None,
                    cell_size: tuple[int, int] = (128, 128)) -> pygame.Surface:
    """Map a complete animation row/sheet once, preserving its original alpha.

    The optional noise is the delivered hand shader's actual source texture.
    Its authored cell-local progression preserves dark patches while TakeDamage
    keeps advancing. No game state or spell identity participates in this map.
    """
    result = image.copy()
    alpha = pygame.surfarray.array_alpha(image)
    visible = alpha > 128
    if not visible.any():
        return result
    rgb = pygame.surfarray.array3d(image)
    luminance = rgb @ np.array([.2126, .7152, .0722])
    low, high = np.percentile(luminance[visible], [3, 98])
    value = np.clip((luminance - low) / max(high - low, 1), 0, 1) ** treatment.gamma
    if noise is not None:
        width, height = cell_size
        source = pygame.surfarray.array3d(pygame.transform.scale(noise, cell_size))[:, :, 0]
        source = np.clip((source.astype(float) - 52) / 91, 0, 1)
        pattern = np.concatenate([
            np.tile(np.roll(source, int(frame * height * .05 / 12), axis=1),
                    (1, image.height // height))
            for frame in range(image.width // width)
        ], axis=0)
        value = np.clip(pattern ** 1.5 * .85 + value * .15, 0, 1)
        value[pattern < .10] = 0
    colors = np.array([((c >> 16) & 255, (c >> 8) & 255, c & 255)
                       for c in treatment.colors], dtype=np.uint8)
    index = np.minimum(len(colors) - 1, (value * len(colors)).astype(int))
    pixels = pygame.surfarray.pixels3d(result)
    pixels[:] = colors[index]
    del pixels
    return result
