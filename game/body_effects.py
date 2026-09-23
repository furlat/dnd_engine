"""Authored treatment of body/equipment pixels, before independent media layers."""

from math import ceil, sin

import numpy as np
import pygame

from game.condition_types import ConditionBodyDistortion, ConditionLiveCopies


def ghost_body(image: pygame.Surface, palette: tuple[int, int, int, int], maximum: float,
               *, copies: ConditionLiveCopies | None = None, time_ms: float = 0., slot: int = 0) -> pygame.Surface:
    result = image.copy()
    rgb = pygame.surfarray.pixels3d(result)
    luminance = rgb[:, :, 0] * .2126 + rgb[:, :, 1] * .7152 + rgb[:, :, 2] * .0722
    indices = np.clip((luminance * 4 / maximum).astype(np.int32), 0, 3)
    colors = np.array([((color >> 16) & 255, (color >> 8) & 255, color & 255) for color in palette], dtype=np.uint8)
    rgb[:] = colors[indices]
    del rgb
    if copies is not None:
        x, y = np.indices(result.get_size())
        t = time_ms / 1000
        wave = np.sin(x * copies.waveFrequency[0] + y * copies.waveFrequency[1]
                      - t * copies.waveSpeed[0] + slot * copies.slotPhase)
        wave *= np.sin(y * copies.secondaryRowFrequency - t * copies.waveSpeed[1])
        alpha = pygame.surfarray.pixels_alpha(result)
        alpha[:] = np.rint(alpha * (copies.minimumOpacity + (1 - copies.minimumOpacity) * (.5 + .5 * wave)))
        del alpha
    return result


def distort_body(image: pygame.Surface, recipe: ConditionBodyDistortion, time_ms: float, strength: float = 1.,
                 ) -> tuple[pygame.Surface, int]:
    """Row displacement pads its canvas; registration never moves the actor anchor."""
    padding = ceil(sum(abs(wave.amplitudePx) for wave in recipe.waves))
    result = pygame.Surface((image.width + padding * 2, image.height), pygame.SRCALPHA)
    for row in range(0, image.height, recipe.bandHeightPx):
        displacement = sum(sin(row * wave.rowFrequency + time_ms / 1000 * wave.timeFrequency)
                           * wave.amplitudePx * strength for wave in recipe.waves)
        height = min(recipe.bandHeightPx, image.height - row)
        result.blit(image, (padding + round(displacement), row), (0, row, image.width, height))
    return result, padding
