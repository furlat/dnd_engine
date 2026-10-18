"""Pure grid-geometry helpers for shape and ray calculations."""
import math
from functools import lru_cache
from typing import Literal, Set, Tuple, List, Optional

import numpy as np


def grid_distance_cells(
    origin: Tuple[int, int],
    target: Tuple[int, int],
) -> int:
    """Return the engine's floored Euclidean distance in grid cells."""
    return int(math.sqrt(
        (origin[0] - target[0]) ** 2
        + (origin[1] - target[1]) ** 2
    ))


def grid_distance_feet(
    origin: Tuple[int, int],
    target: Tuple[int, int],
) -> int:
    """Return the engine's floored Euclidean distance in feet."""
    return grid_distance_cells(origin, target) * 5


def grid_distances_feet(origin: Tuple[int, int], positions: List[Tuple[int, int]]) -> List[int]:
    """`grid_distance_feet` from one origin to each position (IEEE sqrt, as `math.sqrt`)."""
    if not positions:
        return []
    offsets = np.array(positions, dtype=np.int64) - origin
    squared = (offsets * offsets).sum(axis=1).astype(np.float64)
    return (np.sqrt(squared).astype(np.int64) * 5).tolist()


def position_in_sector(
    origin: Tuple[int, int],
    forward: Tuple[int, int],
    target: Tuple[int, int],
    width_degrees: float,
) -> bool:
    """Test a selected point against a sector around a nonzero forward vector."""
    dx, dy = target[0] - origin[0], target[1] - origin[1]
    if forward == (0, 0) or (dx, dy) == (0, 0):
        return False
    angle = abs(math.atan2(forward[0] * dy - forward[1] * dx,
                           forward[0] * dx + forward[1] * dy))
    return angle <= math.radians(width_degrees / 2)


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


def supercover_line_relative(dx: int, dy: int) -> Tuple[Tuple[int, int], ...]:
    """The supercover line from the origin to (dx, dy), as offsets from the origin."""
    return _supercover_line_relative_cached(dx, dy)


@lru_cache(maxsize=32768)
def supercover_cells_relative(dx: int, dy: int) -> frozenset[Tuple[int, int]]:
    """The cells of `supercover_line_relative(dx, dy)`, for set intersection."""
    return frozenset(_supercover_line_relative_cached(dx, dy))


# The route table's step code: an entry is ``cell << ROUTE_STEP_SHIFT | kind``, the kind of the
# step into that cell (none for the origin and the padding).
ROUTE_STEP_SHIFT = 2
STEP_NONE, STEP_ALONG_X, STEP_ALONG_Y, STEP_DIAGONAL = 0, 1, 2, 3

# Square radius in cells of the cached route table (161 x 161 endpoints, about 17 MB): the
# engine's perception reach (`update_all_entities_senses(max_distance=80)`). Routes beyond it
# come from the same stepping rule, computed for the endpoints asked about.
ROUTE_TABLE_RADIUS = 80


def supercover_route_steps(dx: np.ndarray, dy: np.ndarray, radius: int) -> Tuple[np.ndarray, np.ndarray]:
    """Every `supercover_line_relative` from the origin to the endpoints (dx, dy), as its steps.

    Row k holds the line to (dx[k], dy[k]) in order, one entry per cell: ``cell << ROUTE_STEP_SHIFT
    | kind``, the cell flattened as ``(x + radius) * (2 * radius + 1) + (y + radius)`` and the kind
    of the step into it (STEP_NONE for the origin, the first cell). Rows are padded with the cell
    ``(2 * radius + 1) ** 2`` (one past the frame) and STEP_NONE. The second array holds each
    line's length. Every endpoint lies within the radius. The same stepping rule as the scalar
    line, applied to every endpoint at once.
    """
    side = 2 * radius + 1
    nx, ny, sx, sy = np.abs(dx), np.abs(dy), np.sign(dx), np.sign(dy)
    x, y, ix, iy = (np.zeros_like(dx) for _ in range(4))
    longest = int((nx + ny).max()) + 1 if dx.size else 1
    steps = np.full((dx.size, longest), (side * side) << ROUTE_STEP_SHIFT | STEP_NONE, dtype=np.int32)
    steps[:, 0] = (radius * side + radius) << ROUTE_STEP_SHIFT | STEP_NONE
    lengths = np.ones(dx.size, dtype=np.int32)
    for step in range(1, longest):
        active = (ix < nx) | (iy < ny)
        x_mid = (1 + 2 * ix) * ny
        y_mid = (1 + 2 * iy) * nx
        move_x = active & (ix < nx) & ((iy >= ny) | (x_mid < y_mid))
        move_y = active & ~move_x & (iy < ny) & ((ix >= nx) | (y_mid < x_mid))
        step_x = move_x | (active & ~move_x & ~move_y)
        step_y = move_y | (active & ~move_x & ~move_y)
        x += sx * step_x
        y += sy * step_y
        ix += step_x
        iy += step_y
        kind = np.where(step_x & step_y, STEP_DIAGONAL, np.where(step_x, STEP_ALONG_X, STEP_ALONG_Y))
        steps[active, step] = ((((x + radius) * side + (y + radius)) << ROUTE_STEP_SHIFT) | kind)[active]
        lengths += active
    return steps, lengths


@lru_cache(maxsize=1)
def supercover_route_table() -> Tuple[np.ndarray, np.ndarray]:
    """The routes to every endpoint within ROUTE_TABLE_RADIUS (`supercover_route_steps`), kept:
    row ``(dx + r) * (2r + 1) + (dy + r)`` holds the route to (dx, dy)."""
    radius = ROUTE_TABLE_RADIUS
    dx, dy = (axis.ravel() for axis in np.meshgrid(
        np.arange(-radius, radius + 1), np.arange(-radius, radius + 1), indexing="ij"))
    return supercover_route_steps(dx, dy, radius)


def supercover_routes(dx: np.ndarray, dy: np.ndarray, radius: int) -> Tuple[np.ndarray, np.ndarray]:
    """The routes to the endpoints (dx, dy) in the frame of ``radius``, trimmed to the longest:
    read from the kept table when the radius is the table's, computed by the same rule otherwise."""
    if radius != ROUTE_TABLE_RADIUS:
        return supercover_route_steps(dx, dy, radius)
    steps, lengths = supercover_route_table()
    rows = (dx + radius) * (2 * radius + 1) + (dy + radius)
    kept = lengths[rows]
    return steps[rows, :int(kept.max()) if rows.size else 1], kept


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


@lru_cache(maxsize=8192)
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


def cube_axis(origin: Tuple[int, int], aim: Tuple[int, int]) -> Tuple[Literal["x", "y"], int]:
    """Return the axis and sign an extended cube grows along toward ``aim``."""
    dx = aim[0] - origin[0]
    dy = aim[1] - origin[1]
    if abs(dx) >= abs(dy):
        return "x", 1 if dx >= 0 else -1
    return "y", 1 if dy >= 0 else -1


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
        axis, sign = cube_axis(origin, direction if direction is not None else (ox + 1, oy))
        offsets = _directional_rectangle_offsets(size, axis, sign)
        return {
            (ox + rel_x, oy + rel_y)
            for rel_x, rel_y in offsets
        }


@lru_cache(maxsize=64)
def _centered_rectangle_offsets(size: int) -> Tuple[Tuple[int, int], ...]:
    """Return relative offsets for one centered square size."""
    lower = -(size // 2)
    upper = lower + size
    return tuple(
        (dx, dy)
        for dx in range(lower, upper)
        for dy in range(lower, upper)
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
