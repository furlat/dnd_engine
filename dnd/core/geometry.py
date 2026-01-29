"""
Geometry primitives for grid-based calculations.

All functions take positions as Tuple[int, int] and return Set[Tuple[int, int]].
These are pure functions with no dependencies on Entity, GridMap, or game state.

Usage:
    from dnd.core.geometry import circle_positions, line_positions, cone_positions

    positions = circle_positions(center=(5, 5), radius=4)
"""
import math
from typing import Set, Tuple, List, Optional


def circle_positions(
    center: Tuple[int, int],
    radius: int,
    include_center: bool = True
) -> Set[Tuple[int, int]]:
    """
    Get all positions within a filled circle.

    Args:
        center: Center point (x, y)
        radius: Radius in tiles (not feet)
        include_center: If True, include center position

    Returns:
        Set of (x, y) positions within the circle

    Algorithm:
        For each tile in bounding box [-r, +r]:
            if dx² + dy² ≤ r²: include tile
    """
    positions: Set[Tuple[int, int]] = set()
    cx, cy = center

    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            if dx * dx + dy * dy <= radius * radius:
                if dx == 0 and dy == 0 and not include_center:
                    continue
                positions.add((cx + dx, cy + dy))

    return positions


def bresenham_line(
    start: Tuple[int, int],
    end: Tuple[int, int]
) -> List[Tuple[int, int]]:
    """
    Bresenham's line algorithm - get all tiles on line from start to end.

    Returns:
        List of positions from start to end (inclusive), ordered.
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


def line_positions(
    start: Tuple[int, int],
    direction: Tuple[int, int],
    length: int,
    width: int = 1
) -> Set[Tuple[int, int]]:
    """
    Get positions in a line from start toward direction.

    Args:
        start: Starting position (x, y)
        direction: Target direction point (determines angle)
        length: Length in tiles
        width: Width in tiles (1 = single tile, 3 = tile + 1 on each side)

    Returns:
        Set of positions along the line

    Algorithm:
        1. Compute endpoint using normalized direction × length
        2. Get centerline via Bresenham
        3. For width > 1, expand perpendicular at each centerline point
    """
    sx, sy = start
    dx = direction[0] - sx
    dy = direction[1] - sy
    dist = math.sqrt(dx * dx + dy * dy)

    if dist == 0:
        return {start}

    # Normalize and compute endpoint
    ndx, ndy = dx / dist, dy / dist
    end_x = int(round(sx + ndx * length))
    end_y = int(round(sy + ndy * length))

    # Get centerline
    centerline = bresenham_line(start, (end_x, end_y))

    if width <= 1:
        return set(centerline)

    # Expand perpendicular for width
    positions: Set[Tuple[int, int]] = set()
    px, py = -ndy, ndx  # Perpendicular vector
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
    """
    Get positions in a cone from apex toward direction.

    Args:
        apex: Cone apex position (x, y)
        direction: Direction target (determines cone orientation)
        length: Cone length in tiles
        angle_degrees: Cone angle in degrees (D&D 5e standard is 53°)

    Returns:
        Set of positions within the cone

    Algorithm:
        For each tile in bounding box:
            1. Check distance ≤ length
            2. Compute angle to tile: atan2(ty, tx)
            3. Compute angle difference from base direction
            4. Normalize angle diff to [0, π] (handle wraparound)
            5. Include if angle_diff ≤ half_angle
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
                continue  # Apex not included

            # Distance check
            dist = math.sqrt(tx * tx + ty * ty)
            if dist > length:
                continue

            # Angle check
            tile_angle = math.atan2(ty, tx)
            angle_diff = abs(tile_angle - base_angle)

            # Normalize to [0, π] for wraparound at ±π
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
    """
    Get positions in a rectangle/square.

    Args:
        origin: Origin point (center if centered, edge if not)
        size: Size in tiles (e.g., 3 = 3×3 square)
        direction: For non-centered, direction to extend toward
        centered: If True, center on origin. If False, extend from origin.

    Returns:
        Set of positions in the rectangle

    Algorithm:
        Centered: simple box from origin-half to origin+half
        Non-centered: extend in primary direction (horizontal or vertical)
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
            direction = (ox + 1, oy)  # Default: east

        dx = direction[0] - ox
        dy = direction[1] - oy

        # Determine primary direction
        if abs(dx) >= abs(dy):
            # Horizontal primary
            dir_x = 1 if dx >= 0 else -1
            for i in range(size):
                for j in range(-half, half + 1):
                    positions.add((ox + dir_x * i, oy + j))
        else:
            # Vertical primary
            dir_y = 1 if dy >= 0 else -1
            for i in range(size):
                for j in range(-half, half + 1):
                    positions.add((ox + j, oy + dir_y * i))

    return positions
