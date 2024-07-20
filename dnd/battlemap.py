from typing import Dict, Set, List, Tuple, Optional, Union, Any
from pydantic import BaseModel, Field, computed_field
from fractions import Fraction
import uuid
from colorama import Fore, Back, Style
import colorama
from dnd.statsblock import StatsBlock
from dnd.shadowcast import compute_fov
from dnd.dijkstra import dijkstra
from math import sqrt
from collections import defaultdict


colorama.init()



from typing import List, Tuple, Optional, Set
from pydantic import BaseModel, Field, computed_field
from dnd.core import  Ability
from dnd.spatial import RegistryHolder
from dnd.statsblock import StatsBlock
from dnd.actions import Weapon
from dnd.actions import Attack, ActionCost, Targeting, MovementAction
from dnd.dnd_enums import AttackType, TargetType, TargetRequirementType, ActionType, AttackType,WeaponProperty

class Entity(StatsBlock):
    battlemap_id: Optional[str] = None
    line_of_sight: Set[Tuple[int, int]] = Field(default_factory=set)
    
    def __init__(self, **data):
        super().__init__(**data)
        self.register(self)
        self.update_weapon_attacks()

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
            damage=[damage for damage in weapon.damage],
            targeting=targeting,
            stats_block=self,
            weapon=weapon
        )
        self.add_action(attack)

    def generate_movement_actions(self) -> List[MovementAction]:
        movement_actions = []
        if self.sensory and self.sensory.paths:
            movement_budget = self.action_economy.movement.get_value(self)
            print(f"Movement budget for {self.name}: {movement_budget}")
            reachable_positions = self.sensory.paths.get_reachable_positions(movement_budget/5)
            print(f"Reachable positions for {self.name}: {reachable_positions}")
            
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
    
    def update_weapon_attacks(self):
        self.actions = [action for action in self.actions if not isinstance(action, Attack)]
        # Add weapon attacks
        for weapon in self.weapons:
            self.add_weapon_attack(weapon)
    
    def update_movement_actions(self):
        # Clear existing movement actions
        self.actions = [action for action in self.actions if not isinstance(action, MovementAction)]
        # Generate and add movement actions
        movement_actions = self.generate_movement_actions()
        self.actions.extend(movement_actions)

    def update_available_actions(self):
        self.update_weapon_attacks()
        self.update_movement_actions()



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
        # print(f"Getting tile at {x}, {y}")
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            print(f"Tile at {x}, {y} is out of bounds")
            return None
        return self.tiles.get((x, y))

    def is_blocking(self, x: int, y: int) -> bool:
        # Check if the coordinates are within the battlemap bounds
        if 0 <= x < self.width and 0 <= y < self.height:
            tile = self.get_tile(x, y)
            return tile == "WALL"
        else:
            # Treat out-of-bounds tiles as blocking
            return True


    def compute_line_of_sight(self, entity: 'Entity') -> Set[Tuple[int, int]]:
        los_tiles = set()
        position = entity.get_position()
        
        def mark_visible(x, y):
            los_tiles.add((x, y))
        
        # Use the maximum dimension of the battlemap as the max_distance
        max_distance = max(self.width, self.height)
        
        compute_fov(position, self.is_blocking, mark_visible, max_distance)
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
        print(f"Added entity {entity_id} at position {position}")
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
        print(f"Current position for entity {entity.name}: {position}")
        if position:
            entity.sensory.update_origin(position)
            self.update_entity_fov(entity)
            self.update_entity_distance_matrix(entity)
            self.update_entity_paths(entity)
            entity.update_available_actions()
        else:
            print(f"Warning: Entity {entity.name} has no position on the battlemap.")

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


    

