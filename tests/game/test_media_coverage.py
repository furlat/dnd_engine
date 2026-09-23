"""Dispersal preserves original colors, atlas registration, and shared pixels."""

import pygame
import pytest

from game.media_coverage import covered_media


@pytest.mark.parametrize("blend", (0, pygame.BLEND_RGB_ADD))
def test_neutral_coverage_preserves_color_and_does_not_mutate_source(blend):
    image = pygame.Surface((2, 1), pygame.SRCALPHA)
    image.fill((200, 100, 50, 180))
    mask = pygame.Surface((2, 1), pygame.SRCALPHA)
    mask.set_at((0, 0), (23, 99, 71, 255))
    mask.set_at((1, 0), (255, 0, 255, 128))
    result = covered_media(image, mask, blend)
    assert result.get_at((0, 0)) == image.get_at((0, 0))
    assert result.get_at((1, 0)) == ((100, 50, 25, 180) if blend else (200, 100, 50, 90))
    assert image.get_at((1, 0)) == (200, 100, 50, 180)


def test_sparse_parts_use_common_canvas_coverage_not_independently_stretched_masks():
    image = pygame.Surface((2, 1), pygame.SRCALPHA)
    image.fill((180, 20, 50, 255))
    mask = pygame.Surface((4, 1), pygame.SRCALPHA)
    mask.fill((255, 255, 255, 255), (0, 0, 2, 1))
    left = covered_media(image, mask, 0, canvas=(4, 1), offset=(0, 0))
    right = covered_media(image, mask, 0, canvas=(4, 1), offset=(2, 0))
    assert left.get_at((0, 0)).a == left.get_at((1, 0)).a == 255
    assert right.get_at((0, 0)).a == right.get_at((1, 0)).a == 0
