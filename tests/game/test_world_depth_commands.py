"""Ground-registered media keeps authored pixels around ordinary world pictures."""

import numpy as np
import pygame
import pytest

from game.draw_commands import DrawCommand
from game.fixture_depth import partition_world_depth, split_world_depth


def command(image: pygame.Surface, depth: float, identity: str, *,
            plane: int = 100, position: tuple[int, int] = (2, 1),
            world_depth: np.ndarray | None = None, blend: int = 0) -> DrawCommand:
    return DrawCommand((plane, depth, 0., 504, (identity,)), image, position,
                       blend, (identity,), world_depth=world_depth)


def render(commands: list[DrawCommand]) -> pygame.Surface:
    target = pygame.Surface((10, 5), pygame.SRCALPHA)
    target.fill((30, 30, 30, 255))
    for row in sorted(commands, key=lambda row: row.key):
        target.blit(row.surface, row.destination, special_flags=row.blend)
    return target


@pytest.mark.parametrize("alpha", (96, 255))
@pytest.mark.parametrize("identity", ("a", "z"))
@pytest.mark.parametrize("blend", (0, pygame.BLEND_RGB_ADD))
def test_air_pixels_cross_front_and_back_of_an_actor_without_changing_alpha(alpha, identity, blend):
    liquid = pygame.Surface((6, 3), pygame.SRCALPHA)
    for x, color in enumerate(((180, 30, 40, alpha), (30, 180, 40, alpha), (40, 30, 180, alpha))):
        liquid.set_at((x + 1, 1), color)
    original = pygame.image.tobytes(liquid, "RGBA")
    depth = np.zeros(liquid.get_size())
    depth[1, 1], depth[2, 1], depth[3, 1] = -1., 0., 1.
    actor = pygame.Surface((3, 1), pygame.SRCALPHA)
    actor.fill((180, 170, 20, 144))
    attached = command(liquid, 0., identity, world_depth=depth, blend=blend)
    body = command(actor, 0., "m", position=(3, 2))
    parts = split_world_depth([attached, body])
    actual = render(parts)
    expected = pygame.Surface(actual.get_size(), pygame.SRCALPHA)
    expected.fill((30, 30, 30, 255))
    # Coplanar pixels stay behind the vertical body, independently of identity.
    expected.blit(liquid, (3, 2), (1, 1, 2, 1), special_flags=blend)
    expected.blit(actor, (3, 2))
    expected.blit(liquid, (5, 2), (3, 1, 1, 1), special_flags=blend)
    assert pygame.image.tobytes(actual, "RGBA") == pygame.image.tobytes(expected, "RGBA")
    assert pygame.image.tobytes(liquid, "RGBA") == original
    assert all(part.world_depth is None for part in parts)
    assert next(part for part in parts if part.evidence == ("m",)) is body


@pytest.mark.parametrize("peer", ("none", "other_plane", "distant"))
def test_without_an_overlapping_same_plane_peer_the_media_draw_is_unchanged(peer):
    image = pygame.Surface((3, 2), pygame.SRCALPHA)
    image.fill((20, 90, 130, 125))
    attached = command(image, 9., "liquid", world_depth=np.arange(6.).reshape((3, 2)))
    rows = [attached]
    if peer != "none":
        rows.append(command(image, 0., "peer", plane=200 if peer == "other_plane" else 100,
                            position=(8, 1)))
        if peer == "other_plane":
            rows[-1] = rows[-1]._replace(destination=attached.destination)
    result = split_world_depth(rows)
    assert len(result) == len(rows)
    assert result[0].surface is image and result[0].key == attached.key
    assert result[0].destination == attached.destination and result[0].world_depth is None
    assert pygame.image.tobytes(render(result), "RGBA") == pygame.image.tobytes(render(rows), "RGBA")


def test_transparent_clipped_media_does_not_create_depth_fragments():
    blank = pygame.Surface((3, 2), pygame.SRCALPHA)
    actor = pygame.Surface((3, 2), pygame.SRCALPHA)
    actor.fill((180, 170, 20, 144))
    rows = [command(blank, 0., "liquid", world_depth=np.zeros((3, 2))),
            command(actor, 0., "actor")]
    result = split_world_depth(rows)
    assert len(result) == 2 and result[0].world_depth is None
    assert pygame.image.tobytes(render(result), "RGBA") == pygame.image.tobytes(render(rows), "RGBA")


def test_earlier_partition_keeps_ground_depth_aligned_with_the_cropped_pixels():
    image = pygame.Surface((5, 3), pygame.SRCALPHA)
    image.set_at((1, 1), (150, 20, 20, 128))
    image.set_at((3, 1), (20, 150, 20, 128))
    world_depth = np.arange(15.).reshape((5, 3))
    row = command(image, 0., "liquid", world_depth=world_depth)
    prior_depth = np.full((5, 3), -1.)
    prior_depth[3, 1] = 1.
    parts = partition_world_depth(row, prior_depth, [0.])
    assert len(parts) == 2
    for part in parts:
        x, y = part.destination[0] - row.destination[0], part.destination[1] - row.destination[1]
        width, height = part.surface.get_size()
        assert part.world_depth is not None and part.world_depth.shape == (width, height)
        np.testing.assert_array_equal(part.world_depth, world_depth[x:x + width, y:y + height])
    assert pygame.image.tobytes(render(parts), "RGBA") == pygame.image.tobytes(render([row]), "RGBA")
