"""Small ground-material queries using the map's existing physical boundaries."""

from dnd.core.base_block import BaseBlock
from dnd.core.gridmap import GridMap, get_map


def _open_ground(grid: GridMap, position: tuple[int, int]) -> bool:
    if not grid.is_walkable(*position) or grid.is_blocking_propagation(*position):
        return False
    return not any(
        block is not None and block.blocks_walking()
        for identity in grid.get_center_objects_at(position)
        for block in (BaseBlock.get(identity),)
    )


def ground_neighbors(position: tuple[int, int]) -> set[tuple[int, int]]:
    """Adjacent connected floor, ignoring creatures but retaining solid scenery."""
    grid = get_map()
    origin = grid.get_tile(*position)
    if origin is None or not _open_ground(grid, position):
        return set()
    result: set[tuple[int, int]] = set()
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        neighbor = (position[0] + dx, position[1] + dy)
        tile = grid.get_tile(*neighbor)
        if tile is None or tile.height != origin.height or not _open_ground(grid, neighbor):
            continue
        if grid.can_transition(position, neighbor) and grid.can_propagate_transition(position, neighbor):
            result.add(neighbor)
    return result


def ground_footprint(origin: tuple[int, int], radius_cells: int) -> set[tuple[int, int]]:
    """Resolve connected floor within the authored neighboring-cell extent."""
    if radius_cells < 0:
        raise ValueError("Ground footprint radius cannot be negative")
    if not _open_ground(get_map(), origin):
        return set()
    reached = {origin}
    pending = [origin]
    while pending:
        for neighbor in ground_neighbors(pending.pop()):
            if neighbor in reached or max(abs(neighbor[0] - origin[0]), abs(neighbor[1] - origin[1])) > radius_cells:
                continue
            reached.add(neighbor)
            pending.append(neighbor)
    return reached
