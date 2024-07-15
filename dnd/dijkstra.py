import heapq
from typing import Dict, Tuple, List, Optional, Set

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
    is_walkable: callable, 
    width: int, 
    height: int, 
    diagonal: bool = True, 
    max_distance: Optional[int] = None
) -> Tuple[Dict[Tuple[int, int], int], Dict[Tuple[int, int], List[Tuple[int, int]]]]:
    distances = {start: 0}
    paths = {start: [start]}
    pq = [(0, start)]
    visited = set()

    while pq:
        current_distance, current_position = heapq.heappop(pq)
        
        if current_position in visited:
            continue
        visited.add(current_position)
        
        for neighbor in get_neighbors(current_position, diagonal, width, height):
            if not is_walkable(*neighbor):
                continue
            
            distance = current_distance + 1
            if max_distance is not None and distance > max_distance:
                continue
            
            if neighbor not in distances or distance < distances[neighbor]:
                distances[neighbor] = distance
                paths[neighbor] = paths[current_position] + [neighbor]
                heapq.heappush(pq, (distance, neighbor))

    return distances, paths
