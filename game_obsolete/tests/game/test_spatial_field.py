"""A continuous floor field is partitioned, never repeated for every tile."""

import numpy as np
import pygame
import pytest

from game.spatial_field import field_cell


@pytest.mark.parametrize('quadrant', range(4))
def test_field_cells_reconstruct_one_picture_without_repetition_or_alpha_seams(quadrant):
    # Every pixel has its own location-dependent color; repeated full sprites
    # or recentering each crop cannot reconstruct this image.
    image = pygame.Surface((200, 100), pygame.SRCALPHA)
    pixels = pygame.surfarray.pixels3d(image)
    pixels[:, :, 0] = np.arange(200)[:, None]
    pixels[:, :, 1] = np.arange(100)[None, :]
    pixels[:, :, 2] = 190
    del pixels
    pygame.surfarray.pixels_alpha(image)[:] = 80
    combined = pygame.Surface(image.get_size(), pygame.SRCALPHA)
    pivot = (100.0, 50.0)
    for x in range(-3, 4):
        for y in range(-3, 4):
            piece, offset = field_cell(image, pivot, (x, y), quadrant, 1.0)
            combined.blit(piece, offset)
    assert pygame.image.tobytes(combined, 'RGBA') == pygame.image.tobytes(image, 'RGBA')
    field_cell.cache_clear()
