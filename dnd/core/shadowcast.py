"""Symmetric shadowcasting field-of-view primitive."""

import math
from fractions import Fraction
from typing import Tuple, Callable, Optional, Iterator


def compute_fov(
    origin: Tuple[int, int],
    is_blocking: Callable[[int, int], bool],
    mark_visible: Callable[[int, int], None],
    max_distance: Optional[float] = None
) -> None:
    """Visit visible cells around an origin with symmetric shadowcasting.

    Args:
        origin: Origin position.
        is_blocking: Callback returning whether a cell blocks sight.
        mark_visible: Callback invoked for visible cells.
        max_distance: Optional maximum Euclidean radius in tiles.
    """
    ox, oy = origin
    mark_visible(ox, oy)

    for i in range(4):
        quadrant = Quadrant(i, origin)

        def reveal(tile: Tuple[int, int]) -> None:
            x, y = quadrant.transform(tile)
            if max_distance is None or math.sqrt((x-ox)**2 + (y-oy)**2) <= max_distance:
                mark_visible(x, y)

        def is_wall(tile: Optional[Tuple[int, int]]) -> bool:
            if tile is None:
                return False
            x, y = quadrant.transform(tile)
            return is_blocking(x, y)

        def is_floor(tile: Optional[Tuple[int, int]]) -> bool:
            if tile is None:
                return False
            x, y = quadrant.transform(tile)
            return not is_blocking(x, y)

        first_row = Row(1, Fraction(-1), Fraction(1))
        scan_iterative(
            first_row,
            reveal,
            is_wall,
            is_floor,
            max_depth=math.floor(max_distance) if max_distance is not None else None,
        )


class Quadrant:
    """Coordinate transform for one cardinal shadowcasting quadrant."""

    north = 0
    east = 1
    south = 2
    west = 3

    def __init__(self, cardinal: int, origin: Tuple[int, int]):
        """Create a quadrant transform.

        Args:
            cardinal: One of `north`, `east`, `south`, or `west`.
            origin: World-space origin for the transform.
        """
        if cardinal not in range(4):
            raise ValueError("Cardinal must be 0, 1, 2, or 3")
        self.cardinal: int = cardinal
        self.ox, self.oy = origin

    def transform(self, tile: Tuple[int, int]) -> Tuple[int, int]:
        """Convert quadrant-local row/column coordinates to world position."""
        row, col = tile
        if self.cardinal == self.north:
            return (self.ox + col, self.oy - row)
        elif self.cardinal == self.south:
            return (self.ox + col, self.oy + row)
        elif self.cardinal == self.east:
            return (self.ox + row, self.oy + col)
        else:
            assert self.cardinal == self.west
            return (self.ox - row, self.oy + col)


class Row:
    """One shadowcasting row bounded by start and end slopes."""

    def __init__(self, depth: int, start_slope: Fraction, end_slope: Fraction):
        """Create a row at a depth with slope bounds."""
        self.depth = depth
        self.start_slope = start_slope
        self.end_slope = end_slope

    def tiles(self) -> Iterator[Tuple[int, int]]:
        """Yield row-local tile coordinates within the current slopes."""
        min_col = round_ties_up(self.depth * self.start_slope)
        max_col = round_ties_down(self.depth * self.end_slope)
        for col in range(min_col, max_col + 1):
            yield (self.depth, col)

    def next(self) -> 'Row':
        """Return the next deeper row with the same slope bounds."""
        return Row(self.depth + 1, self.start_slope, self.end_slope)


def slope(tile: Tuple[int, int]) -> Fraction:
    """Return the slope for the leading edge of a row-local tile."""
    row_depth, col = tile
    return Fraction(2 * col - 1, 2 * row_depth)


def is_symmetric(row: Row, tile: Tuple[int, int]) -> bool:
    """Return whether a tile lies within a row's symmetric visibility bounds."""
    _, col = tile
    return (col >= row.depth * row.start_slope
            and col <= row.depth * row.end_slope)


def round_ties_up(n: Fraction) -> int:
    """Round half values upward."""
    return math.floor(float(n) + 0.5)


def round_ties_down(n: Fraction) -> int:
    """Round half values downward."""
    return math.ceil(float(n) - 0.5)


def scan_iterative(
    row: Row,
    reveal: Callable[[Tuple[int, int]], None],
    is_wall: Callable[[Optional[Tuple[int, int]]], bool],
    is_floor: Callable[[Optional[Tuple[int, int]]], bool],
    max_depth: Optional[int] = None,
) -> None:
    """Scan rows iteratively to avoid recursive shadowcasting depth.

    Args:
        row: First shadowcasting row.
        reveal: Callback for cells accepted by the visibility scan.
        is_wall: Callback identifying opaque cells.
        is_floor: Callback identifying transparent cells.
        max_depth: Optional cardinal row limit for a bounded-radius query.
    """
    rows = [row]
    while rows:
        row = rows.pop()
        if max_depth is not None and row.depth > max_depth:
            continue
        prev_tile: Optional[Tuple[int, int]] = None
        for tile in row.tiles():
            if is_wall(tile) or is_symmetric(row, tile):
                reveal(tile)
            if is_wall(prev_tile) and is_floor(tile):
                row.start_slope = slope(tile)
            if is_floor(prev_tile) and is_wall(tile):
                next_row = row.next()
                next_row.end_slope = slope(tile)
                rows.append(next_row)
            prev_tile = tile
        if is_floor(prev_tile):
            rows.append(row.next())
