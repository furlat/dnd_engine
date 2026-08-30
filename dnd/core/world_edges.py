"""Dependency-neutral elevation surfaces and directed adjacent world edges."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from dnd.types.world import CardinalDirection, WorldEdgeChannel


class ElevationSurfaceKind(str, Enum):
    """Authored support-surface behavior for ordinary walking."""

    ORDINARY = "ordinary"
    STAIRS = "stairs"
    RAMP = "ramp"


class SlopeAxis(str, Enum):
    """Cardinal axis along which a progressive surface changes height."""

    NORTH_SOUTH = "north_south"
    EAST_WEST = "east_west"


def _exact_position(position: tuple[int, int]) -> tuple[int, int]:
    if (
        type(position) is not tuple
        or len(position) != 2
        or any(type(value) is not int for value in position)
    ):
        raise TypeError("edge endpoints must be exact two-integer tuples")
    return position


@dataclass(frozen=True, slots=True)
class AdjacentEdgeKey:
    """Encounter-local identity of one cardinal boundary."""

    first: tuple[int, int]
    second: tuple[int, int]

    def __post_init__(self) -> None:
        first = _exact_position(self.first)
        second = _exact_position(self.second)
        if abs(first[0] - second[0]) + abs(first[1] - second[1]) != 1:
            raise ValueError("world-edge endpoints must be cardinally adjacent")
        if first >= second:
            raise ValueError(
                "world-edge endpoints must use canonical lexical order"
            )

    @classmethod
    def between(
        cls,
        first: tuple[int, int],
        second: tuple[int, int],
    ) -> "AdjacentEdgeKey":
        """Build canonical identity for one exact cardinal boundary."""
        exact_first = _exact_position(first)
        exact_second = _exact_position(second)
        ordered = sorted((exact_first, exact_second))
        return cls(first=ordered[0], second=ordered[1])


@dataclass(frozen=True, slots=True)
class WorldEdgeStructuralContribution:
    """One provider's exact vertical interval and blocked channels."""

    provider_uuid: UUID
    base_height_steps: int
    top_height_steps: int
    blocked_channels: tuple[WorldEdgeChannel, ...]


@dataclass(frozen=True, slots=True)
class WorldEdgeView:
    """Immutable ordered objective facts for one directed edge query."""

    key: AdjacentEdgeKey
    source_position: tuple[int, int]
    destination_position: tuple[int, int]
    source_tile_uuid: UUID
    destination_tile_uuid: UUID
    source_height_steps: int
    destination_height_steps: int
    elevation_delta_steps: int
    source_surface_kind: ElevationSurfaceKind
    destination_surface_kind: ElevationSurfaceKind
    source_slope_axis: SlopeAxis | None
    destination_slope_axis: SlopeAxis | None
    exit_direction: CardinalDirection
    entry_direction: CardinalDirection
    exit_contributions: tuple[WorldEdgeStructuralContribution, ...]
    entry_contributions: tuple[WorldEdgeStructuralContribution, ...]


def transition_axis(
    first: tuple[int, int],
    second: tuple[int, int],
) -> SlopeAxis:
    """Return the cardinal axis of one adjacent edge."""
    key = AdjacentEdgeKey.between(first, second)
    if key.first[0] == key.second[0]:
        return SlopeAxis.NORTH_SOUTH
    return SlopeAxis.EAST_WEST


def progressive_elevation_transition(
    first_height_steps: int,
    first_surface_kind: ElevationSurfaceKind,
    first_slope_axis: SlopeAxis | None,
    second_height_steps: int,
    second_surface_kind: ElevationSurfaceKind,
    second_slope_axis: SlopeAxis | None,
    axis: SlopeAxis,
) -> bool:
    """Return whether both endpoint facts authorize one walking height step."""
    return (
        abs(second_height_steps - first_height_steps) == 1
        and first_surface_kind
        in (ElevationSurfaceKind.STAIRS, ElevationSurfaceKind.RAMP)
        and second_surface_kind is first_surface_kind
        and first_slope_axis is axis
        and second_slope_axis is axis
    )


ElevationSurfaceFacts = tuple[
    int,
    ElevationSurfaceKind,
    SlopeAxis | None,
]


def contradictory_progressive_elevation_edge(
    cells: Mapping[tuple[int, int], ElevationSurfaceFacts],
    *,
    implicit_surface: ElevationSurfaceFacts | None = None,
    bounds: tuple[int, int] | None = None,
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """Return the first contradictory authored progressive edge, if any."""
    visited: set[AdjacentEdgeKey] = set()
    for position, first in cells.items():
        for neighbor_position in (
            (position[0] - 1, position[1]),
            (position[0] + 1, position[1]),
            (position[0], position[1] - 1),
            (position[0], position[1] + 1),
        ):
            if bounds is not None and not (
                0 <= neighbor_position[0] < bounds[0]
                and 0 <= neighbor_position[1] < bounds[1]
            ):
                continue
            second = cells.get(neighbor_position, implicit_surface)
            if second is None:
                continue
            edge = AdjacentEdgeKey.between(position, neighbor_position)
            if edge in visited:
                continue
            visited.add(edge)
            if first[0] == second[0]:
                continue
            axis = transition_axis(position, neighbor_position)
            has_aligned_progressive_surface = any(
                endpoint[1]
                in (ElevationSurfaceKind.STAIRS, ElevationSurfaceKind.RAMP)
                and endpoint[2] is axis
                for endpoint in (first, second)
            )
            if has_aligned_progressive_surface and not progressive_elevation_transition(
                first[0],
                first[1],
                first[2],
                second[0],
                second[1],
                second[2],
                axis,
            ):
                return edge.first, edge.second
    return None


__all__ = [
    "AdjacentEdgeKey",
    "ElevationSurfaceKind",
    "SlopeAxis",
    "WorldEdgeStructuralContribution",
    "WorldEdgeView",
    "contradictory_progressive_elevation_edge",
    "progressive_elevation_transition",
    "transition_axis",
]
