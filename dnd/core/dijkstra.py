import heapq
from typing import Callable, Dict, List, Optional, Tuple


def get_neighbors(
    position: Tuple[int, int],
    diagonal: bool,
    width: int,
    height: int,
    min_x: int = 0,
    min_y: int = 0,
) -> List[Tuple[int, int]]:
    """Return neighboring coordinates inside an origin-aware bound.

    Args:
        position: Position whose neighbors should be inspected.
        diagonal: Whether diagonal neighbors are allowed.
        width: Bound width in cells.
        height: Bound height in cells.
        min_x: Minimum x coordinate included in the bound.
        min_y: Minimum y coordinate included in the bound.

    Returns:
        Neighbor coordinates that fall inside the bound.
    """
    if width <= 0 or height <= 0:
        return []

    x, y = position
    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    if diagonal:
        directions += [(1, 1), (1, -1), (-1, 1), (-1, -1)]

    max_x = min_x + width - 1
    max_y = min_y + height - 1
    neighbors = []
    for dx, dy in directions:
        nx, ny = x + dx, y + dy
        if min_x <= nx <= max_x and min_y <= ny <= max_y:
            neighbors.append((nx, ny))
    return neighbors


def dijkstra(
    start: Tuple[int, int],
    is_walkable: Callable[[int, int], bool],
    width: int,
    height: int,
    diagonal: bool = True,
    max_distance: Optional[int] = None,
    cost_func: Optional[Callable[[int, int], float]] = None,
    can_enter: Optional[Callable[[Tuple[int, int], Tuple[int, int]], bool]] = None,
    epsilon: float = 0.001,
    min_x: int = 0,
    min_y: int = 0,
) -> Tuple[Dict[Tuple[int, int], int], Dict[Tuple[int, int], List[Tuple[int, int]]]]:
    """Compute shortest paths from start position using Dijkstra's algorithm.

    Args:
        start: Starting position.
        is_walkable: Callback checking whether a tile can be entered.
        width: Search bound width in cells.
        height: Search bound height in cells.
        diagonal: Whether diagonal movement is allowed.
        max_distance: Maximum movement cost to search.
        cost_func: Optional movement-cost callback. Costs less than or equal to
            zero are impassable.
        can_enter: Optional transition callback for directional borders.
        epsilon: Small priority cost added to diagonal moves for tie-breaking.
        min_x: Minimum x coordinate included in the search bound.
        min_y: Minimum y coordinate included in the search bound.

    Returns:
        `(distances, paths)` where distances are movement costs and paths are
        position lists from start to each reachable destination.
    """
    distances: Dict[Tuple[int, int], float] = {start: 0}
    true_distances: Dict[Tuple[int, int], int] = {start: 0}
    paths: Dict[Tuple[int, int], List[Tuple[int, int]]] = {start: [start]}
    pq: List[Tuple[float, Tuple[int, int]]] = [(float(0), start)]
    visited: set[Tuple[int, int]] = set()

    while pq:
        current_distance, current_position = heapq.heappop(pq)

        if current_position in visited:
            continue
        visited.add(current_position)

        for neighbor in get_neighbors(current_position, diagonal, width, height, min_x, min_y):
            if not is_walkable(*neighbor):
                continue

            if can_enter is not None and not can_enter(current_position, neighbor):
                continue

            if cost_func is not None:
                tile_cost = cost_func(neighbor[0], neighbor[1])
                if tile_cost <= 0:
                    continue
            else:
                tile_cost = 1

            is_diagonal = (neighbor[0] != current_position[0]) and (neighbor[1] != current_position[1])
            additional_cost = epsilon if is_diagonal else 0
            distance = current_distance + tile_cost + additional_cost
            true_distance = true_distances[current_position] + tile_cost

            if max_distance is not None and true_distance > max_distance:
                continue

            if neighbor not in distances or distance < distances[neighbor]:
                distances[neighbor] = distance
                true_distances[neighbor] = int(true_distance)
                paths[neighbor] = paths[current_position] + [neighbor]
                heapq.heappush(pq, (distance, neighbor))

    return true_distances, paths
