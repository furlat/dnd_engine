"""Dependency-neutral tactical support-height distance rules."""

from math import ceil

from dnd.core.geometry import grid_distance_feet


def _exact_position(position: tuple[int, int]) -> tuple[int, int]:
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


def support_distance_feet(
    first_position: tuple[int, int],
    first_elevation_feet: int,
    second_position: tuple[int, int],
    second_elevation_feet: int,
) -> int:
    """Return the engine distance between two zero-height support points."""
    first = _exact_position(first_position)
    second = _exact_position(second_position)
    first_elevation = _exact_elevation_feet(first_elevation_feet)
    second_elevation = _exact_elevation_feet(second_elevation_feet)
    vertical_feet = ceil(abs(second_elevation - first_elevation) / 5) * 5
    return max(grid_distance_feet(first, second), vertical_feet)


__all__ = ["support_distance_feet"]
