"""Natural silk pixels survive full visibility; hidden/removed owners don't lend fringe."""

import pygame
import pytest

from game.assets import load_catalog
from game.spatial_field import field_cell, field_supports


@pytest.mark.parametrize("quadrant,pose", enumerate(("e", "s", "w", "n")))
def test_authored_web_fringe_reconstructs_exact_source_and_obeys_partial_cleanup(quadrant, pose):
    catalog = load_catalog()
    animation = catalog.spatial_effects["spatial_effect.spell.web"]
    spec = catalog.resources[animation.frames_by_pose[pose][animation.default_frame]]
    image = pygame.image.load(spec.path)
    # The selected animation's resting frame is the production source. The old
    # web_ground duplicate remains in the archive and is not a playback input.
    assert image.get_size() == spec.native_size
    origin = (8.5, 4.5)
    native = frozenset((x, y) for x in range(7, 11) for y in range(3, 7))
    visible = frozenset((x, y) for x in range(2, 17) for y in range(-2, 13))
    assert animation.footprint_tiles == (4, 4)

    def supports(owners=native, sight=visible):
        return field_supports(image.size, spec.pivot, origin, (4, 4), owners, sight, quadrant, 1)

    def render(positions):
        picture = pygame.Surface(image.size, pygame.SRCALPHA)
        for x, y in positions:
            piece, offset = field_cell(image, spec.pivot, (x - origin[0], y - origin[1]), quadrant, 1)
            picture.blit(piece, offset)
        return pygame.image.tobytes(picture, "RGBA")

    full = render(supports())
    assert full == pygame.image.tobytes(image, "RGBA"), "The native envelope must not cut the natural silhouette"
    assert render(native) != full, "This delivered art really contains authored overspill"
    partial = frozenset(position for position in native if position[0] < 10)
    assert all(position[0] < 10 for position in supports(partial)), "Removed east edge cannot lend fringe to the east"
    assert render(supports(partial)) != full
    west_only = frozenset(position for position in visible if position[0] < 9)
    assert all(position in west_only or position in native for position in supports(sight=west_only))
    assert set(supports(sight=frozenset())) == native, "Existing remembered interiors retain their ordinary disclosure path"
    assert render(supports(sight=west_only)) != full
    assert render(supports(frozenset())) == bytes(image.width * image.height * 4)
    assert render(supports()) == full, "Backward acquisition restores the same source pixels"
    field_cell.cache_clear()
