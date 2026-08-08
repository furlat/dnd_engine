"""Dependency-neutral tactical elevation and distance rules."""

from math import ceil, sqrt

from dnd.core.creature_types import Size


_TACTICAL_VERTICAL_EXTENT_FEET: dict[Size, float] = {
    Size.TINY: 2.5,
    Size.SMALL: 5.0,
    Size.MEDIUM: 5.0,
    Size.LARGE: 10.0,
    Size.HUGE: 15.0,
    Size.GARGANTUAN: 20.0,
}


def _exact_grid_position(position: tuple[int, int]) -> tuple[int, int]:
    if (
        type(position) is not tuple
        or len(position) != 2
        or any(type(value) is not int for value in position)
    ):
        raise TypeError("grid positions must be exact two-integer tuples")
    return position


def _exact_elevation_feet(elevation_feet: int) -> int:
    if type(elevation_feet) is not int:
        raise TypeError("support elevation must be an exact integer number of feet")
    return elevation_feet


def tactical_vertical_extent_feet(size: Size) -> float:
    """Return the engine's tactical occupied vertical extent for one size."""
    if type(size) is not Size:
        raise TypeError("size must be a Size value")
    return _TACTICAL_VERTICAL_EXTENT_FEET[size]


def planar_grid_distance_feet(
    first_position: tuple[int, int],
    second_position: tuple[int, int],
) -> int:
    """Return the established flat-grid metric without changing diagonals."""
    first_x, first_y = _exact_grid_position(first_position)
    second_x, second_y = _exact_grid_position(second_position)
    dx = second_x - first_x
    dy = second_y - first_y
    return int(sqrt(dx * dx + dy * dy)) * 5


def _hybrid_distance_feet(planar_feet: int, vertical_clearance_feet: float) -> int:
    vertical_feet = ceil(vertical_clearance_feet / 5) * 5
    return max(planar_feet, vertical_feet)


def support_distance_feet(
    first_position: tuple[int, int],
    first_elevation_feet: int,
    second_position: tuple[int, int],
    second_elevation_feet: int,
) -> int:
    """Return hybrid distance between two zero-height support points."""
    first_elevation = _exact_elevation_feet(first_elevation_feet)
    second_elevation = _exact_elevation_feet(second_elevation_feet)
    return _hybrid_distance_feet(
        planar_grid_distance_feet(first_position, second_position),
        abs(second_elevation - first_elevation),
    )


def creature_volume_distance_feet(
    first_position: tuple[int, int],
    first_elevation_feet: int,
    first_size: Size,
    second_position: tuple[int, int],
    second_elevation_feet: int,
    second_size: Size,
) -> int:
    """Return hybrid range between two closed tactical occupied intervals."""
    first_bottom = _exact_elevation_feet(first_elevation_feet)
    second_bottom = _exact_elevation_feet(second_elevation_feet)
    first_top = first_bottom + tactical_vertical_extent_feet(first_size)
    second_top = second_bottom + tactical_vertical_extent_feet(second_size)
    vertical_clearance = max(
        0.0,
        float(second_bottom) - first_top,
        float(first_bottom) - second_top,
    )
    return _hybrid_distance_feet(
        planar_grid_distance_feet(first_position, second_position),
        vertical_clearance,
    )
