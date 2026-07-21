"""Pure grid-geometry helpers for shape and ray calculations."""
import math
from functools import lru_cache
from typing import Set, Tuple, List, Optional


def circle_positions(
    center: Tuple[int, int],
    radius: int,
    include_center: bool = True
) -> Set[Tuple[int, int]]:
    """Return all grid positions inside a filled circle.

    Args:
        center: Center point as `(x, y)`.
        radius: Radius in tiles.
        include_center: Whether to include the center tile.

    Returns:
        Positions whose squared distance is within the radius.
    """
    cx, cy = center
    return {
        (cx + dx, cy + dy)
        for dx, dy in _circle_relative_offsets(radius, include_center)
    }


@lru_cache(maxsize=128)
def _circle_relative_offsets(
    radius: int,
    include_center: bool,
) -> Tuple[Tuple[int, int], ...]:
    """Return relative offsets for one filled circle definition."""
    positions: List[Tuple[int, int]] = []
    r_sq = radius * radius

    for dx in range(-radius, radius + 1):
        max_dy = int((r_sq - dx * dx) ** 0.5)
        for dy in range(-max_dy, max_dy + 1):
            if dx == 0 and dy == 0 and not include_center:
                continue
            positions.append((dx, dy))

    return tuple(positions)


def bresenham_line(
    start: Tuple[int, int],
    end: Tuple[int, int]
) -> List[Tuple[int, int]]:
    """Return Bresenham line cells from start to end.

    Args:
        start: Inclusive start position.
        end: Inclusive end position.

    Returns:
        Ordered list of positions from start to end.
    """
    x0, y0 = start
    x1, y1 = end
    positions: List[Tuple[int, int]] = []

    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    x, y = x0, y0
    while True:
        positions.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy

    return positions


def supercover_line(
    start: Tuple[int, int],
    end: Tuple[int, int]
) -> List[Tuple[int, int]]:
    """
    Ordered grid traversal from start to end for transition-aware ray checks.

    Consecutive cells are always adjacent. When the mathematical line advances
    diagonally, the transition is represented as a diagonal step so callers can
    apply their own diagonal policy while checking the crossed tile directions.
    """
    return list(_supercover_line_cached(start, end))


def supercover_line_offsets(
    delta: Tuple[int, int],
) -> Tuple[Tuple[int, int], ...]:
    """Return immutable offsets for a supercover ray delta."""
    return _supercover_line_relative_cached(delta[0], delta[1])


@lru_cache(maxsize=8192)
def _supercover_line_cached(
    start: Tuple[int, int],
    end: Tuple[int, int],
) -> Tuple[Tuple[int, int], ...]:
    """Return immutable supercover-line geometry for one start/end pair."""
    x0, y0 = start
    return tuple(
        (x0 + dx, y0 + dy)
        for dx, dy in _supercover_line_relative_cached(
            end[0] - start[0],
            end[1] - start[1],
        )
    )


@lru_cache(maxsize=1024)
def _supercover_line_relative_cached(
    dx: int,
    dy: int,
) -> Tuple[Tuple[int, int], ...]:
    """Return immutable supercover-line offsets for one relative ray."""
    if dx == 0 and dy == 0:
        return ((0, 0),)

    nx = abs(dx)
    ny = abs(dy)
    sign_x = 1 if dx > 0 else -1 if dx < 0 else 0
    sign_y = 1 if dy > 0 else -1 if dy < 0 else 0

    x, y = 0, 0
    ix = 0
    iy = 0
    positions: List[Tuple[int, int]] = [(x, y)]

    while ix < nx or iy < ny:
        x_mid = (1 + 2 * ix) * ny
        y_mid = (1 + 2 * iy) * nx
        if ix < nx and (iy >= ny or x_mid < y_mid):
            x += sign_x
            ix += 1
        elif iy < ny and (ix >= nx or y_mid < x_mid):
            y += sign_y
            iy += 1
        else:
            x += sign_x
            y += sign_y
            ix += 1
            iy += 1
        positions.append((x, y))

    return tuple(positions)


def line_positions(
    start: Tuple[int, int],
    direction: Tuple[int, int],
    length: int,
    width: int = 1
) -> Set[Tuple[int, int]]:
    """Return positions in a widened line from start toward direction.

    Args:
        start: Starting position.
        direction: Target point that determines the line angle.
        length: Length in tiles.
        width: Width in tiles.

    Returns:
        Set of positions along the centerline and width expansion.
    """
    sx, sy = start
    dx = direction[0] - sx
    dy = direction[1] - sy
    dist = math.sqrt(dx * dx + dy * dy)

    if dist == 0:
        return {start}

    ndx, ndy = dx / dist, dy / dist
    end_x = int(round(sx + ndx * length))
    end_y = int(round(sy + ndy * length))

    centerline = bresenham_line(start, (end_x, end_y))

    if width <= 1:
        return set(centerline)

    positions: Set[Tuple[int, int]] = set()
    px, py = -ndy, ndx
    half_width = width // 2

    for cx, cy in centerline:
        for w in range(-half_width, half_width + 1):
            tile_x = int(round(cx + px * w))
            tile_y = int(round(cy + py * w))
            positions.add((tile_x, tile_y))

    return positions


def cone_positions(
    apex: Tuple[int, int],
    direction: Tuple[int, int],
    length: int,
    angle_degrees: int = 53
) -> Set[Tuple[int, int]]:
    """Return positions in a cone from apex toward direction.

    Args:
        apex: Cone apex position.
        direction: Target point that determines cone orientation.
        length: Cone length in tiles.
        angle_degrees: Cone angle in degrees.

    Returns:
        Set of positions within the angular and distance bounds.
    """
    ax, ay = apex
    dx = direction[0] - ax
    dy = direction[1] - ay

    if dx == 0 and dy == 0:
        return {apex}

    base_angle = math.atan2(dy, dx)
    half_angle = math.radians(angle_degrees / 2)
    positions: Set[Tuple[int, int]] = set()

    for tx, ty, tile_angle in _cone_relative_tiles(length):
        angle_diff = abs(tile_angle - base_angle)

        if angle_diff > math.pi:
            angle_diff = 2 * math.pi - angle_diff

        if angle_diff <= half_angle:
            positions.add((ax + tx, ay + ty))

    return positions


@lru_cache(maxsize=64)
def _cone_relative_tiles(length: int) -> Tuple[Tuple[int, int, float], ...]:
    """Return radius-filtered relative cells and angles for one cone length."""
    radius_squared = length * length
    return tuple(
        (tx, ty, math.atan2(ty, tx))
        for tx in range(-length, length + 1)
        for ty in range(-length, length + 1)
        if (tx != 0 or ty != 0)
        and tx * tx + ty * ty <= radius_squared
    )


def rectangle_positions(
    origin: Tuple[int, int],
    size: int,
    direction: Optional[Tuple[int, int]] = None,
    centered: bool = True
) -> Set[Tuple[int, int]]:
    """Return positions in a centered or directional square.

    Args:
        origin: Center or edge origin.
        size: Square size in tiles.
        direction: Direction to extend toward when not centered.
        centered: Whether to center the square on origin.

    Returns:
        Set of positions in the square.
    """
    ox, oy = origin

    if centered:
        return {
            (ox + dx, oy + dy)
            for dx, dy in _centered_rectangle_offsets(size)
        }
    else:
        if direction is None:
            direction = (ox + 1, oy)

        dx = direction[0] - ox
        dy = direction[1] - oy

        if abs(dx) >= abs(dy):
            dir_x = 1 if dx >= 0 else -1
            offsets = _directional_rectangle_offsets(size, "x", dir_x)
        else:
            dir_y = 1 if dy >= 0 else -1
            offsets = _directional_rectangle_offsets(size, "y", dir_y)
        return {
            (ox + rel_x, oy + rel_y)
            for rel_x, rel_y in offsets
        }


@lru_cache(maxsize=64)
def _centered_rectangle_offsets(size: int) -> Tuple[Tuple[int, int], ...]:
    """Return relative offsets for one centered square size."""
    half = size // 2
    return tuple(
        (dx, dy)
        for dx in range(-half, half + 1)
        for dy in range(-half, half + 1)
    )


@lru_cache(maxsize=64)
def _directional_rectangle_offsets(
    size: int,
    axis: str,
    sign: int,
) -> Tuple[Tuple[int, int], ...]:
    """Return relative offsets for one directional square definition."""
    half = size // 2
    if axis == "x":
        return tuple(
            (sign * i, j)
            for i in range(size)
            for j in range(-half, half + 1)
        )
    return tuple(
        (j, sign * i)
        for i in range(size)
        for j in range(-half, half + 1)
    )
