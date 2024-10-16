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
    epsilon: float = 0.001  # Small cost added for diagonal moves
) -> Tuple[Dict[Tuple[int, int], int], Dict[Tuple[int, int], List[Tuple[int, int]]]]:
    distances : Dict[Tuple[int, int], float] = {start: 0}
    true_distances = {start: 0}  # Distances without epsilon for final return
    paths = {start: [start]}
    pq = [(float(0), start)]
    visited = set()

    while pq:
        current_distance, current_position = heapq.heappop(pq)
        
        if current_position in visited:
            continue
        visited.add(current_position)
        
        for neighbor in get_neighbors(current_position, diagonal, width, height):
            if not is_walkable(*neighbor):
                continue
            
            # Calculate cost: add epsilon for diagonal moves
            is_diagonal = (neighbor[0] != current_position[0]) and (neighbor[1] != current_position[1])
            additional_cost = epsilon if is_diagonal else 0
            distance = current_distance + 1 + additional_cost
            
            if max_distance is not None and distance > max_distance:
                continue
            
            if neighbor not in distances or distance < distances[neighbor]:
                
                distances[neighbor] = distance
                true_distances[neighbor] = int(true_distances[current_position] + 1)  # Keep true distance without epsilon
                paths[neighbor] = paths[current_position] + [neighbor]
                heapq.heappush(pq, (distance, neighbor))

    return true_distances, paths

