from typing import Dict, Set, List, Tuple, Optional, Union, Any
from pydantic import BaseModel, Field, computed_field
from fractions import Fraction
import uuid
from colorama import Fore, Back, Style
import colorama
from dnd.core import RegistryHolder
from dnd.statsblock import StatsBlock
from dnd.shadowcast import compute_fov
from dnd.dijkstra import dijkstra
from math import sqrt
from collections import defaultdict


colorama.init()



from typing import List, Tuple, Optional, Set
from pydantic import BaseModel, Field, computed_field
from dnd.core import RegistryHolder, Ability
from dnd.statsblock import StatsBlock
from dnd.equipment import Weapon, WeaponProperty
from dnd.actions import Attack, ActionCost, Targeting, MovementAction
from dnd.dnd_enums import AttackType, TargetType, TargetRequirementType, ActionType, AttackType

class Entity(StatsBlock, RegistryHolder):
    battlemap_id: Optional[str] = None
    line_of_sight: Set[Tuple[int, int]] = Field(default_factory=set)
    
    def __init__(self, **data):
        super().__init__(**data)
        self.register(self)

    @computed_field
    def is_on_battlemap(self) -> bool:
        return self.battlemap_id is not None

    def set_battlemap(self, battlemap_id: str):
        self.battlemap_id = battlemap_id

    def remove_from_battlemap(self):
        self.battlemap_id = None
        self.line_of_sight.clear()

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.register(self)

    @classmethod
    def get_or_create(cls, entity_id: str, **kwargs):
        instance = cls.get_instance(entity_id)
        if instance is None:
            instance = cls(id=entity_id, **kwargs)
        else:
            instance.update(**kwargs)
        return instance

    def is_in_line_of_sight(self, other: 'Entity') -> bool:
        return other.position in self.line_of_sight

    def get_position(self) -> Optional[Tuple[int, int]]:
        if self.battlemap_id:
            battlemap = RegistryHolder.get_instance(self.battlemap_id)
            if battlemap:
                return battlemap.get_entity_position(self.id)
        return None

    def add_weapon_attack(self, weapon: Weapon):
        ability = Ability.DEX if WeaponProperty.FINESSE in weapon.properties else Ability.STR
        if weapon.attack_type == AttackType.RANGED_WEAPON:
            ability = Ability.DEX

        targeting = Targeting(
            type=TargetType.ONE_TARGET,
            range=weapon.range.normal,
            line_of_sight=True,
            requirement=TargetRequirementType.ANY
        )

        attack = Attack(
            name=weapon.name,
            description=f"{weapon.attack_type.value} Attack with {weapon.name}",
            cost=[ActionCost(type=ActionType.ACTION, cost=1)],
            limited_usage=None,
            attack_type=weapon.attack_type,
            ability=ability,
            range=weapon.range,
            damage=[weapon.damage],
            targeting=targeting,
            stats_block=self,
            weapon=weapon
        )
        self.add_action(attack)

    def generate_movement_actions(self) -> List[MovementAction]:
        movement_actions = []
        if self.sensory and self.sensory.paths:
            movement_budget = self.action_economy.movement.get_value(self)
            reachable_positions = self.sensory.paths.get_reachable_positions(movement_budget)
            
            for position in reachable_positions:
                path = self.sensory.paths.get_shortest_path_to_position(position)
                if path:
                    movement_actions.append(MovementAction(
                        name=f"Move to {position}",
                        description=f"Move from {self.sensory.origin} to {position}",
                        cost=[ActionCost(type=ActionType.MOVEMENT, cost=len(path) - 1)],
                        limited_usage=None,
                        targeting=Targeting(type=TargetType.SELF),
                        stats_block=self,
                        path=path
                    ))

        return movement_actions

    def update_available_actions(self):
        # Clear existing movement actions
        self.actions = [action for action in self.actions if not isinstance(action, MovementAction)]
        
        # Add weapon attacks
        for weapon in self.weapons:
            self.add_weapon_attack(weapon)
        
        # Generate and add movement actions
        movement_actions = self.generate_movement_actions()
        self.actions.extend(movement_actions)


class BattleMap(BaseModel, RegistryHolder):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    width: int
    height: int
    tiles: Dict[Tuple[int, int], str] = Field(default_factory=dict)
    entities: Dict[str, Tuple[int, int]] = Field(default_factory=dict)
    positions: Dict[Tuple[int, int], Set[str]] = Field(default_factory=lambda: defaultdict(set))

    def __init__(self, **data):
        super().__init__(**data)
        self.register(self)

    def set_tile(self, x: int, y: int, tile_type: str):
        self.tiles[(x, y)] = tile_type

    def get_tile(self, x: int, y: int) -> Optional[str]:
        return self.tiles.get((x, y))

    def is_blocking(self, x: int, y: int) -> bool:
        tile = self.get_tile(x, y)
        return tile == "WALL"

    def compute_line_of_sight(self, entity: 'Entity') -> Set[Tuple[int, int]]:
        los_tiles = set()
        def mark_visible(x, y):
            los_tiles.add((x, y))
        compute_fov(entity.get_position(), self.is_blocking, mark_visible)
        return los_tiles
    
    def compute_dijkstra(
        self, start: Tuple[int, int], diagonal: bool = True, max_distance: Optional[int] = None
    ) -> Tuple[Dict[Tuple[int, int], int], Dict[Tuple[int, int], List[Tuple[int, int]]]]:
        def is_walkable(x, y):
            return self.get_tile(x, y) == "FLOOR"
        return dijkstra(start, is_walkable, self.width, self.height, diagonal, max_distance)

    def add_entity(self, entity: 'Entity', position: Tuple[int, int]):
        entity_id = entity.id
        entity.set_battlemap(self.id)
        self.entities[entity_id] = position
        self.positions[position].add(entity_id)
        self.update_entity_senses(entity)

    def remove_entity(self, entity: 'Entity'):
        entity_id = entity.id
        position = self.entities.pop(entity_id, None)
        if position:
            self.positions[position].remove(entity_id)
            if not self.positions[position]:
                del self.positions[position]
        entity.remove_from_battlemap()

    def move_entity(self, entity: 'Entity', new_position: Tuple[int, int]):
        entity_id = entity.id
        old_position = self.entities[entity_id]
        self.positions[old_position].remove(entity_id)
        if not self.positions[old_position]:
            del self.positions[old_position]

        self.entities[entity_id] = new_position
        self.positions[new_position].add(entity_id)
        self.update_entity_senses(entity)

    def get_entity_position(self, entity_id: str) -> Optional[Tuple[int, int]]:
        return self.entities.get(entity_id)

    def update_entity_senses(self, entity: 'Entity'):
        entity.sensory.update_battlemap(self.id)
        position = self.get_entity_position(entity.id)
        if position:
            entity.sensory.update_origin(position)
            self.update_entity_fov(entity)
            self.update_entity_distance_matrix(entity)
            self.update_entity_paths(entity)
            entity.update_available_actions()

    def update_entity_fov(self, entity: 'Entity'):
        los_tiles = self.compute_line_of_sight(entity)
        entity.sensory.update_fov(los_tiles)

    def update_entity_distance_matrix(self, entity: 'Entity'):
        distances, _ = self.compute_dijkstra(entity.get_position())
        entity.sensory.update_distance_matrix(distances)

    def update_entity_paths(self, entity: 'Entity'):
        _, paths = self.compute_dijkstra(entity.get_position())
        entity.sensory.update_paths(paths)

    def __str__(self) -> str:
        return f"BattleMap(id={self.id}, width={self.width}, height={self.height}, entities={len(self.entities)})"

class MapDrawer:
    def __init__(self, battle_map: 'BattleMap'):
        self.battle_map = battle_map

    def get_tile_char(self, x: int, y: int) -> str:
        tile = self.battle_map.get_tile(x, y)
        if tile == "WALL":
            return '#'
        elif tile == "WATER":
            return '~'
        elif tile == "FLOOR":
            return '.'
        else:
            return ' '

    def print_ascii_map(self, highlight_los: Optional[Set[Tuple[int, int]]] = None) -> str:
        ascii_map = []
        for y in range(self.battle_map.height):
            row = []
            for x in range(self.battle_map.width):
                char = self.get_tile_char(x, y)
                if highlight_los and (x, y) in highlight_los:
                    char = Back.YELLOW + char + Style.RESET_ALL
                row.append(char)
            ascii_map.append(''.join(row))
        return '\n'.join(ascii_map)

    def visualize_los(self, entity: Entity):
        los_tiles = self.battle_map.compute_line_of_sight(entity)
        position =  entity.get_position()
        print(f"Map with line of sight from {position}:")
        print(self.print_ascii_map(highlight_los=los_tiles))

    def visualize_dijkstra_distances(self, start: Tuple[int, int], diagonal: bool = True, max_distance: Optional[int] = None):
        distances, _ = self.battle_map.compute_dijkstra(start, diagonal, max_distance)
        
        ascii_map = []
        for y in range(self.battle_map.height):
            row = []
            for x in range(self.battle_map.width):
                if (x, y) == start:
                    char = '@'
                elif (x, y) in distances:
                    char = str(distances[(x, y)] % 10)
                else:
                    char = Back.RED + 'X' + Style.RESET_ALL
                row.append(char)
            ascii_map.append(''.join(row))
        return '\n'.join(ascii_map)

    def visualize_dijkstra_path(self, start: Tuple[int, int], end: Tuple[int, int], diagonal: bool = True, max_distance: Optional[int] = None):
        _, paths = self.battle_map.compute_dijkstra(start, diagonal, max_distance)
        
        if end not in paths:
            return "No path found."

        path_set = set(paths[end])
        ascii_map = []
        for y in range(self.battle_map.height):
            row = []
            for x in range(self.battle_map.width):
                if (x, y) == start:
                    char = '@'
                elif (x, y) == end:
                    char = Back.GREEN + 'E' + Style.RESET_ALL
                elif (x, y) in path_set:
                    char = Back.GREEN + '.' + Style.RESET_ALL
                else:
                    char = self.get_tile_char(x, y)
                row.append(char)
            ascii_map.append(''.join(row))
        return '\n'.join(ascii_map)

    @staticmethod
    def compute_absolute_distance(start: Tuple[int, int], end: Tuple[int, int]) -> float:
        return sqrt((start[0] - end[0]) ** 2 + (start[1] - end[1]) ** 2) * 5  # 5 feet per tile

    def visualize_absolute_distances(self, start: Tuple[int, int]):
        ascii_map = []
        for y in range(self.battle_map.height):
            row = []
            for x in range(self.battle_map.width):
                distance = self.compute_absolute_distance(start, (x, y))
                if (x, y) == start:
                    char = '@'
                elif distance < 10:
                    char = f'{int(distance):d}'
                elif distance < 100:
                    char = f'{int(distance):02d}'
                else:
                    char = 'XX'
                row.append(char)
            ascii_map.append(''.join(row))
        return '\n'.join(ascii_map)
    

