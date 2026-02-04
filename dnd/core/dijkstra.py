import heapq
from typing import Dict, Tuple, List, Optional, Callable

def get_neighbors(position: Tuple[int, int], diagonal: bool, width: int, height: int) -> List[Tuple[int, int]]:
    x, y = position
    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    if diagonal:
        directions += [(1, 1), (1, -1), (-1, 1), (-1, -1)]

    neighbors = []
    for dx, dy in directions:
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height:
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
    epsilon: float = 0.001  # Small cost added for diagonal moves
) -> Tuple[Dict[Tuple[int, int], int], Dict[Tuple[int, int], List[Tuple[int, int]]]]:
    """
    Compute shortest paths from start position using Dijkstra's algorithm.

    Args:
        start: Starting position
        is_walkable: Function (x, y) -> bool checking if a tile is walkable
        width: Grid width
        height: Grid height
        diagonal: Allow diagonal movement
        max_distance: Maximum distance to search (in movement cost units)
        cost_func: Optional function (x, y) -> float returning movement cost for a tile.
                   If not provided, all walkable tiles cost 1.
                   If returns <= 0, tile is impassable.
        can_enter: Optional function (from_pos, to_pos) -> bool checking if entry
                   from from_pos to to_pos is allowed (for directional borders).
        epsilon: Small cost added to diagonal moves for tie-breaking

    Returns:
        Tuple of (distances_dict, paths_dict) where:
        - distances_dict maps position -> integer distance (movement cost units)
        - paths_dict maps position -> list of positions forming the path
    """
    distances: Dict[Tuple[int, int], float] = {start: 0}
    true_distances: Dict[Tuple[int, int], int] = {start: 0}  # Distances without epsilon for final return
    paths: Dict[Tuple[int, int], List[Tuple[int, int]]] = {start: [start]}
    pq: List[Tuple[float, Tuple[int, int]]] = [(float(0), start)]
    visited: set[Tuple[int, int]] = set()

    while pq:
        current_distance, current_position = heapq.heappop(pq)

        if current_position in visited:
            continue
        visited.add(current_position)

        for neighbor in get_neighbors(current_position, diagonal, width, height):
            # Check basic walkability
            if not is_walkable(*neighbor):
                continue

            # Check directional border (can we enter neighbor from current position?)
            if can_enter is not None and not can_enter(current_position, neighbor):
                continue

            # Get tile cost
            if cost_func is not None:
                tile_cost = cost_func(neighbor[0], neighbor[1])
                if tile_cost <= 0:  # Impassable (e.g., max_constraint set to 0)
                    continue
            else:
                tile_cost = 1

            # Calculate distance: add epsilon for diagonal moves
            is_diagonal = (neighbor[0] != current_position[0]) and (neighbor[1] != current_position[1])
            additional_cost = epsilon if is_diagonal else 0
            distance = current_distance + tile_cost + additional_cost

            if max_distance is not None and distance > max_distance:
                continue

            if neighbor not in distances or distance < distances[neighbor]:
                distances[neighbor] = distance
                # True distance tracks actual movement cost (without epsilon)
                true_distances[neighbor] = int(true_distances[current_position] + tile_cost)
                paths[neighbor] = paths[current_position] + [neighbor]
                heapq.heappush(pq, (distance, neighbor))

    return true_distances, paths
