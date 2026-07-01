"""Pure grid-geometry helpers for shape and ray calculations."""
import math
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
    positions: Set[Tuple[int, int]] = set()
    cx, cy = center
    r_sq = radius * radius

    for dx in range(-radius, radius + 1):
        max_dy = int((r_sq - dx * dx) ** 0.5)
        for dy in range(-max_dy, max_dy + 1):
            if dx == 0 and dy == 0 and not include_center:
                continue
            positions.add((cx + dx, cy + dy))

    return positions


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
    if start == end:
        return [start]

    x0, y0 = start
    x1, y1 = end
    dx = x1 - x0
    dy = y1 - y0
    nx = abs(dx)
    ny = abs(dy)
    sign_x = 1 if dx > 0 else -1 if dx < 0 else 0
    sign_y = 1 if dy > 0 else -1 if dy < 0 else 0

    x, y = x0, y0
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

    return positions


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

    for tx in range(-length, length + 1):
        for ty in range(-length, length + 1):
            if tx == 0 and ty == 0:
                continue

            dist = math.sqrt(tx * tx + ty * ty)
            if dist > length:
                continue

            tile_angle = math.atan2(ty, tx)
            angle_diff = abs(tile_angle - base_angle)

            if angle_diff > math.pi:
                angle_diff = 2 * math.pi - angle_diff

            if angle_diff <= half_angle:
                positions.add((ax + tx, ay + ty))

    return positions


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
    half = size // 2
    positions: Set[Tuple[int, int]] = set()

    if centered:
        for dx in range(-half, half + 1):
            for dy in range(-half, half + 1):
                positions.add((ox + dx, oy + dy))
    else:
        if direction is None:
            direction = (ox + 1, oy)

        dx = direction[0] - ox
        dy = direction[1] - oy

        if abs(dx) >= abs(dy):
            dir_x = 1 if dx >= 0 else -1
            for i in range(size):
                for j in range(-half, half + 1):
                    positions.add((ox + dir_x * i, oy + j))
        else:
            dir_y = 1 if dy >= 0 else -1
            for i in range(size):
                for j in range(-half, half + 1):
                    positions.add((ox + j, oy + dir_y * i))

    return positions
