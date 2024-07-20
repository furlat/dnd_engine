from typing import List, Tuple, Dict, Set, Optional, Callable
from pydantic import BaseModel, Field

class RegistryHolder:
    _registry: Dict[str, 'RegistryHolder'] = {}
    _types: Set[type] = set()
    
    @classmethod
    def is_in_registry(cls, instance_id: str):
        return instance_id in cls._registry
    @classmethod
    def register(cls, instance: 'RegistryHolder'):
        cls._registry[instance.id] = instance
        cls._types.add(type(instance))

    @classmethod
    def get_instance(cls, instance_id: str):
        return cls._registry.get(instance_id)

    @classmethod
    def all_instances(cls, filter_type=True):
        if filter_type:
            return [instance for instance in cls._registry.values() if isinstance(instance, cls)]
        return list(cls._registry.values())

    @classmethod
    def all_instances_by_type(cls, type: type):
        return [instance for instance in cls._registry.values() if isinstance(instance, type)]

    @classmethod
    def all_types(cls, as_string=True):
        if as_string:
            return [type_name.__name__ for type_name in cls._types]
        return cls._types
    
class BaseSpatial(BaseModel):
    battlemap_id: str
    origin: Tuple[int, int]

    def get_entities_at(self, position: Tuple[int, int]) -> List[str]:
        battlemap = RegistryHolder.get_instance(self.battlemap_id)
        return list(battlemap.positions.get(position, set()))

    def filter_positions(self, condition: Callable[[Tuple[int, int]], bool]) -> List[Tuple[int, int]]:
        raise NotImplementedError("Subclasses must implement this method")

    def get_entities(self, positions: List[Tuple[int, int]]) -> List[str]:
        battlemap = RegistryHolder.get_instance(self.battlemap_id)
        return [entity_id for pos in positions for entity_id in battlemap.positions.get(pos, set())]
    
class FOV(BaseSpatial):
    visible_tiles: Set[Tuple[int, int]] = Field(default_factory=set)

    @staticmethod
    def bresenham(start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
        x0, y0 = start
        x1, y1 = end
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        ray = []
        while True:
            ray.append((x0, y0))
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

        return ray

    def get_ray_to(self, position: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        if position in self.visible_tiles:
            return self.bresenham(self.origin, position)
        return None

    def get_all_rays(self) -> Dict[Tuple[int, int], List[Tuple[int, int]]]:
        return {pos: self.bresenham(self.origin, pos) for pos in self.visible_tiles}

    def is_visible(self, position: Tuple[int, int]) -> bool:
        return position in self.visible_tiles

    def filter_positions(self, condition: Callable[[Tuple[int, int]], bool]) -> List[Tuple[int, int]]:
        return [pos for pos in self.visible_tiles if condition(pos)]

    def get_visible_positions(self) -> List[Tuple[int, int]]:
        return list(self.visible_tiles)

    def get_visible_entities(self) -> List[str]:
        return self.get_entities(self.get_visible_positions())

    def get_positions_in_range(self, range: int) -> List[Tuple[int, int]]:
        return self.filter_positions(lambda pos: 
            ((pos[0] - self.origin[0])**2 + (pos[1] - self.origin[1])**2)**0.5 * 5 <= range
        )

    def get_entities_in_range(self, range: int) -> List[str]:
        return self.get_entities(self.get_positions_in_range(range))
    
class DistanceMatrix(BaseSpatial):
    distances: Dict[Tuple[int, int], int] = Field(default_factory=dict)

    def get_distance(self, position: Tuple[int, int]) -> Optional[int]:
        return self.distances.get(position)

    def filter_positions(self, condition: Callable[[Tuple[int, int]], bool]) -> List[Tuple[int, int]]:
        return [pos for pos, distance in self.distances.items() if condition(pos)]

    def get_positions_within_distance(self, max_distance: int) -> List[Tuple[int, int]]:
        return self.filter_positions(lambda pos: self.distances[pos] <= max_distance)

    def get_entities_within_distance(self, max_distance: int) -> List[str]:
        return self.get_entities(self.get_positions_within_distance(max_distance))

    def get_adjacent_positions(self) -> List[Tuple[int, int]]:
        return self.get_positions_within_distance(1)

    def get_adjacent_entities(self) -> List[str]:
        return self.get_entities(self.get_adjacent_positions())

class Path(BaseSpatial):
    path: List[Tuple[int, int]]
    
    def get_path_length(self) -> int:
        return len(self.path) - 1  # Subtract 1 because the start position is included

    def is_valid_movement(self, movement_budget: int) -> bool:
        return self.get_path_length() <= movement_budget

    def get_positions_on_path(self) -> List[Tuple[int, int]]:
        return self.path

    def get_entities_on_path(self) -> List[str]:
        return self.get_entities(self.get_positions_on_path())
    
class Paths(BaseSpatial):
    paths: Dict[Tuple[int, int], List[Tuple[int, int]]] = Field(default_factory=dict)

    def get_path_to(self, destination: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        return self.paths.get(destination)

    def filter_positions(self, condition: Callable[[Tuple[int, int]], bool]) -> List[Tuple[int, int]]:
        return [pos for pos in self.paths.keys() if condition(pos)]

    def get_reachable_positions(self, movement_budget: int) -> List[Tuple[int, int]]:
        return self.filter_positions(lambda pos: len(self.paths[pos]) - 1 <= movement_budget)

    def get_reachable_entities(self, movement_budget: int) -> List[str]:
        return self.get_entities(self.get_reachable_positions(movement_budget))

    def get_shortest_path_to_position(self, position: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        return self.get_path_to(position)
    
