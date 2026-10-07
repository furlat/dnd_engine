"""Authored passage alignment resolved from disclosed boundary placements."""

from dnd.core.item_types import ItemIntegrity
from dnd.types.world import CardinalDirection
from game.environment_art import load_environment_art
from dnd.player.facts import PlayerState


def passage_point(state: PlayerState, start: tuple[float, float], end: tuple[float, float]
                  ) -> tuple[float, float, float] | None:
    """Find the authored opening on the one received boundary this step crosses."""
    art = load_environment_art()
    for obj in state.objects.values():
        prop = art.props.get(obj.item.item_id)
        if prop is None or prop.passage_point is None or obj.item.integrity is ItemIntegrity.DESTROYED:
            continue
        placement = obj.placement
        direction = placement.boundary_direction
        if direction is None:
            continue
        nx, ny = {
            CardinalDirection.EAST: (1, 0), CardinalDirection.NORTH: (0, 1),
            CardinalDirection.WEST: (-1, 0), CardinalDirection.SOUTH: (0, -1),
        }[direction]
        x, y = placement.position
        if {start, end} != {(x, y), (x + nx, y + ny)}:
            continue
        normal, tangent, height = prop.passage_point
        return (x + nx * normal - ny * tangent, y + ny * normal + nx * tangent,
                placement.base_height_steps + height)
    return None
