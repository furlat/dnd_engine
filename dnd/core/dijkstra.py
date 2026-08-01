import heapq
from collections import deque
from typing import Callable, Dict, List, Optional, Tuple


_CARDINAL_DIRECTIONS = ((0, 1), (1, 0), (0, -1), (-1, 0))
_DIAGONAL_DIRECTIONS = _CARDINAL_DIRECTIONS + (
    (1, 1),
    (1, -1),
    (-1, 1),
    (-1, -1),
)


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
    predecessors: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start: None}
    pq: List[Tuple[float, Tuple[int, int]]] = [(float(0), start)]
    visited: set[Tuple[int, int]] = set()
    directions = _DIAGONAL_DIRECTIONS if diagonal else _CARDINAL_DIRECTIONS
    max_x = min_x + width - 1
    max_y = min_y + height - 1

    while pq:
        current_distance, current_position = heapq.heappop(pq)

        if current_position in visited:
            continue
        visited.add(current_position)

        current_x, current_y = current_position
        for dx, dy in directions:
            neighbor = (current_x + dx, current_y + dy)
            if not (
                min_x <= neighbor[0] <= max_x
                and min_y <= neighbor[1] <= max_y
            ):
                continue
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
                predecessors[neighbor] = current_position
                heapq.heappush(pq, (distance, neighbor))

    paths: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
    for destination in true_distances:
        reversed_path: List[Tuple[int, int]] = []
        cursor: Optional[Tuple[int, int]] = destination
        while cursor is not None:
            reversed_path.append(cursor)
            cursor = predecessors[cursor]
        reversed_path.reverse()
        paths[destination] = reversed_path

    return true_distances, paths


def breadth_first_paths(
    start: Tuple[int, int],
    is_walkable: Callable[[int, int], bool],
    width: int,
    height: int,
    diagonal: bool = True,
    max_distance: Optional[int] = None,
    can_enter: Optional[Callable[[Tuple[int, int], Tuple[int, int]], bool]] = None,
    min_x: int = 0,
    min_y: int = 0,
) -> Tuple[Dict[Tuple[int, int], int], Dict[Tuple[int, int], List[Tuple[int, int]]]]:
    """Compute shortest paths for unit-cost grids.

    Args:
        start: Starting position.
        is_walkable: Callback checking whether a tile can be entered.
        width: Search bound width in cells.
        height: Search bound height in cells.
        diagonal: Whether diagonal neighbors are allowed.
        max_distance: Maximum number of movement-cost units to search.
        can_enter: Optional transition callback for directional borders.
        min_x: Minimum x coordinate included in the search bound.
        min_y: Minimum y coordinate included in the search bound.

    Returns:
        `(distances, paths)` with the same public shape as `dijkstra()`.
    """
    distances: Dict[Tuple[int, int], int] = {start: 0}
    predecessors: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start: None}
    queue: deque[Tuple[int, int]] = deque([start])
    directions = _DIAGONAL_DIRECTIONS if diagonal else _CARDINAL_DIRECTIONS
    max_x = min_x + width - 1
    max_y = min_y + height - 1

    while queue:
        current_position = queue.popleft()
        current_distance = distances[current_position]
        current_x, current_y = current_position
        next_distance = current_distance + 1
        if max_distance is not None and next_distance > max_distance:
            continue
        for dx, dy in directions:
            neighbor = (current_x + dx, current_y + dy)
            if not (
                min_x <= neighbor[0] <= max_x
                and min_y <= neighbor[1] <= max_y
            ):
                continue
            if neighbor in distances:
                continue
            if not is_walkable(*neighbor):
                continue
            if can_enter is not None and not can_enter(current_position, neighbor):
                continue
            distances[neighbor] = next_distance
            predecessors[neighbor] = current_position
            queue.append(neighbor)

    paths: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
    for destination in distances:
        reversed_path: List[Tuple[int, int]] = []
        cursor: Optional[Tuple[int, int]] = destination
        while cursor is not None:
            reversed_path.append(cursor)
            cursor = predecessors[cursor]
        reversed_path.reverse()
        paths[destination] = reversed_path

    return distances, paths
