"""Partition one registered floor picture into disjoint world-cell draw pieces."""

from functools import lru_cache
from math import ceil, floor

import numpy as np
import pygame

from dnd.core.geometry import line_positions
from game.projection import Camera, TILE_HEIGHT, TILE_WIDTH, inverse_plane, project_world


def _raster_supports(size: tuple[int, int], pivot: tuple[float, float], origin: tuple[float, float],
                     quadrant: int, zoom: float) -> tuple[tuple[int, int], ...]:
    projected = project_world(origin, quadrant=quadrant)
    camera = Camera(quadrant, zoom, (pivot[0] - projected[0] * zoom,
                                    pivot[1] - projected[1] * zoom))
    corners = tuple(inverse_plane(point, camera)
                    for point in ((0, 0), (size[0], 0), size, (0, size[1])))
    return tuple((x, y)
        for x in range(floor(min(p[0] for p in corners) + .5), floor(max(p[0] for p in corners) + .5) + 1)
        for y in range(floor(min(p[1] for p in corners) + .5), floor(max(p[1] for p in corners) + .5) + 1))


def field_supports(size: tuple[int, int], pivot: tuple[float, float], origin: tuple[float, float],
                   footprint: tuple[int, int], positions: frozenset[tuple[int, int]],
                   visible: frozenset[tuple[int, int]], quadrant: int, zoom: float,
                   ) -> tuple[tuple[int, int], ...]:
    """Lend an authored fringe to its observed edge owner, on visible support.

    The complete authoring footprint defines ownership; partial observations or
    native cell removal never redefine the image's origin or its edge bounds.
    Pixels remain the author's raster, partitioned by field_cell as usual.
    """
    left = ceil(origin[0] - (footprint[0] - 1) / 2)
    bottom = ceil(origin[1] - (footprint[1] - 1) / 2)
    right, top = left + footprint[0] - 1, bottom + footprint[1] - 1
    return tuple((x, y) for x, y in _raster_supports(size, pivot, origin, quadrant, zoom)
        if (x, y) in positions or ((x, y) in visible
            and (min(right, max(left, x)), min(top, max(bottom, y))) in positions))


@lru_cache(maxsize=64)
def _line_owners(origin: tuple[int, int], direction: tuple[int, int], length: int,
                  width: int) -> tuple[tuple[int, int], ...]:
    # This is the declared geometry's stable ownership lattice, not occupants,
    # propagation or discovered cells. No world access is needed or permitted.
    return tuple(sorted(line_positions(origin, (origin[0] + direction[0], origin[1] + direction[1]), length, width)))


@lru_cache(maxsize=2048)
def _line_owner(origin: tuple[int, int], direction: tuple[int, int], length: int,
                 width: int, position: tuple[int, int]) -> tuple[int, int]:
    return min(_line_owners(origin, direction, length, width),
        key=lambda point: ((point[0] - position[0]) ** 2 + (point[1] - position[1]) ** 2, point))


def line_field_supports(size: tuple[int, int], pivot: tuple[float, float], origin: tuple[int, int],
                        direction: tuple[int, int], length_tiles: int, width_tiles: int,
                        positions: frozenset[tuple[int, int]], visible: frozenset[tuple[int, int]],
                        quadrant: int, zoom: float) -> tuple[tuple[int, int], ...]:
    """Use the disclosed full line's discrete owners, never remaining bounds."""
    return line_owned_supports(_raster_supports(size, pivot, origin, quadrant, zoom), origin,
                               direction, length_tiles, width_tiles, positions, visible)


def line_owned_supports(candidates: tuple[tuple[int, int], ...], origin: tuple[int, int],
                        direction: tuple[int, int], length_tiles: int, width_tiles: int,
                        positions: frozenset[tuple[int, int]], visible: frozenset[tuple[int, int]],
                        ) -> tuple[tuple[int, int], ...]:
    """The same disclosed ownership for raster supports and true XYZ samples."""
    return tuple(position for position in candidates if position in visible
        and _line_owner(origin, direction, length_tiles, width_tiles, position) in positions)


@lru_cache(maxsize=512)
def field_cell(image: pygame.Surface, pivot: tuple[float, float],
               offset: tuple[float, float], quadrant: int, zoom: float,
               ) -> tuple[pygame.Surface, tuple[int, int]]:
    """Cache immutable pieces, preserving the full image's origin and pixels.

    Cell ownership is half-open in grid space, so neighboring pieces neither
    repeat alpha nor leave a seam. The caller supplies each observed support's
    height/lighting and submits the piece at that support's painter depth.
    """
    x, y = project_world(offset, quadrant=quadrant)
    ox, oy = project_world((0, 0), quadrant=quadrant)
    cx, cy = (x - ox) * zoom + pivot[0], (y - oy) * zoom + pivot[1]
    half_width, half_height = TILE_WIDTH * zoom / 2, TILE_HEIGHT * zoom / 2
    rect = pygame.Rect(floor(cx - half_width), floor(cy - half_height),
                       ceil(cx + half_width) - floor(cx - half_width),
                       ceil(cy + half_height) - floor(cy - half_height)).clip(image.get_rect())
    if not rect.width or not rect.height:
        return pygame.Surface((1, 1), pygame.SRCALPHA), (rect.x, rect.y)
    piece = image.subsurface(rect).copy()
    xs = np.arange(rect.left, rect.right, dtype=float)[:, None] + .5 - cx
    ys = np.arange(rect.top, rect.bottom, dtype=float)[None, :] + .5 - cy
    gx = xs / (TILE_WIDTH * zoom) + ys / (TILE_HEIGHT * zoom)
    gy = ys / (TILE_HEIGHT * zoom) - xs / (TILE_WIDTH * zoom)
    outside = (gx < -.5) | (gx >= .5) | (gy < -.5) | (gy >= .5)
    pygame.surfarray.pixels_alpha(piece)[outside] = 0
    return piece, (rect.x, rect.y)
