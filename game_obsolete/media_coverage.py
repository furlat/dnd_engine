"""Apply neutral coverage without recoloring or mutating shared source pixels."""

import numpy as np
import pygame


def covered_media(image: pygame.Surface, coverage: pygame.Surface, blend: int,
                  *, canvas: tuple[int, int] | None = None,
                  offset: tuple[int, int] = (0, 0)) -> pygame.Surface:
    """Sparse parts share one mask in their original untransformed canvas."""
    size = canvas or image.get_size()
    mask = pygame.transform.scale(coverage, size) if coverage.get_size() != size else coverage
    part = pygame.Surface(image.get_size(), pygame.SRCALPHA)
    part.blit(mask, (-offset[0], -offset[1]))
    alpha = pygame.surfarray.array_alpha(part).astype(np.uint16)
    result = image.copy()
    if blend == pygame.BLEND_RGB_ADD:
        # Additive materials already premultiply their source alpha. RGB_ADD
        # ignores alpha at composition, so coverage must attenuate their RGB.
        rgb = pygame.surfarray.pixels3d(result)
        rgb[:] = ((rgb.astype(np.uint16) * alpha[:, :, None] + 127) // 255).astype(np.uint8)
        del rgb
    else:
        opacity = pygame.surfarray.pixels_alpha(result)
        opacity[:] = ((opacity.astype(np.uint16) * alpha + 127) // 255).astype(np.uint8)
        del opacity
    return result
