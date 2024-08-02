from typing import Dict, Set, List, Tuple, Optional, Union, Any, Type, Optional
from pydantic import BaseModel, Field, computed_field
import uuid
from dnd.statsblock import StatsBlock
from dnd.shadowcast import compute_fov
from dnd.dijkstra import dijkstra
from math import sqrt
from collections import defaultdict


from dnd.spatial import RegistryHolder
from dnd.statsblock import StatsBlock
from dnd.actions import Weapon, Attack, ActionCost, MovementAction, Action
from dnd.dnd_enums import AttackType, TargetType, TargetRequirementType, ActionType, AttackHand, WeaponProperty

class Entity(StatsBlock):
    battlemap_id: Optional[str] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        self.register(self)

    @classmethod
    def from_stats_block(cls, stats_block: StatsBlock):
        return cls(**stats_block.model_dump())

    @computed_field
    def is_on_battlemap(self) -> bool:
        return self.battlemap_id is not None
    
    @computed_field
    def position(self) -> Optional[Tuple[int, int]]:
        return self.sensory.origin if self.sensory else None

    @computed_field
    def line_of_sight(self) -> Set[Tuple[int, int]]:
        return self.sensory.fov.visible_tiles if self.sensory and self.sensory.fov else set()

    def set_battlemap(self, battlemap_id: str):
        self.battlemap_id = battlemap_id
        if self.sensory:
            self.sensory.update_battlemap(battlemap_id)
        print(f"Set battlemap_id for entity {self.id} to {battlemap_id}")

    def remove_from_battlemap(self):
        self.battlemap_id = None
        if self.sensory:
            self.sensory.clear_spatial_data()

    def get_battlemap(self) -> Optional['BattleMap']:
        if self.battlemap_id:
            return RegistryHolder.get_instance(self.battlemap_id)
        return None

    def is_in_line_of_sight(self, other: 'Entity') -> bool:
        return self.sensory.is_visible(other.position) if self.sensory else False

    def get_weapon_attacks(self) -> List[Attack]:
        attacks = []
        if self.attacks_manager.melee_right_hand:
            attacks.append(Attack.from_weapon(self.attacks_manager.melee_right_hand, self, AttackHand.MELEE_RIGHT))
        if self.attacks_manager.melee_left_hand:
            attacks.append(Attack.from_weapon(self.attacks_manager.melee_left_hand, self, AttackHand.MELEE_LEFT))
        if self.attacks_manager.ranged_right_hand:
            attacks.append(Attack.from_weapon(self.attacks_manager.ranged_right_hand, self, AttackHand.RANGED_RIGHT))
        if self.attacks_manager.ranged_left_hand:
            attacks.append(Attack.from_weapon(self.attacks_manager.ranged_left_hand, self, AttackHand.RANGED_LEFT))
        return attacks

    def get_valid_attacks(self) -> List[Attack]:
        valid_attacks = []
        potential_targets = self.get_potential_targets()
        for attack in self.get_weapon_attacks():
            for target in potential_targets:
                prerequisites_passed, logs = attack.check_prerequisites(self, target)
                if prerequisites_passed:
                    valid_attacks.append(attack.bind(self, target))
                # TODO: Store logs for failed prerequisites if needed
        return valid_attacks

    def get_potential_targets(self) -> List['Entity']:
        if not self.sensory or not self.sensory.fov:
            return []
        return [
            Entity.get_instance(entity_id)
            for entity_id in self.sensory.get_visible_entities()
            if Entity.get_instance(entity_id) != self
        ]

    def generate_movement_actions(self) -> List[MovementAction]:
        movement_actions = []
        if self.sensory and self.sensory.paths:
            movement_budget = self.action_economy.movement.apply(self).total_bonus
            print(f"Movement budget for {self.name}: {movement_budget}")
            reachable_positions = self.sensory.paths.get_reachable_positions(movement_budget // 5)
            
            for position in reachable_positions:
                path = self.sensory.paths.get_shortest_path_to_position(position)
                if path:
                    movement_actions.append(MovementAction(
                        name=f"Move to {position}",
                        description=f"Move from {self.sensory.origin} to {position}",
                        source=self,
                        target=position,
                        path=path
                    ))
        print(f"Generated {len(movement_actions)} movement actions for {self.name}")

        return movement_actions

    @computed_field
    def actions(self) -> List[Action]:
        return self.generate_movement_actions() + self.get_valid_attacks()

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.register(self)

    @classmethod
    def get_or_create(cls, entity_id: str, **kwargs):
        instance : Optional[Entity] = cls.get_instance(entity_id)
        if instance is None:
            instance = cls(id=entity_id, **kwargs)
        else:
            instance.update(**kwargs)
        return instance
    def __str__(self):
        return f"Entity(id={self.id}, name={self.name})"



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

    def is_in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def set_tile(self, x: int, y: int, tile_type: str):
        self.tiles[(x, y)] = tile_type

    def get_tile(self, x: int, y: int) -> Optional[str]:
        if not self.is_in_bounds(x, y):
            print(f"Tile at {x}, {y} is out of bounds")
            return None
        return self.tiles.get((x, y))

    def is_blocking(self, x: int, y: int) -> bool:
        if self.is_in_bounds(x, y):
            tile = self.get_tile(x, y)
            return tile == "WALL"
        else:
            return True

    def compute_line_of_sight(self, entity: 'Entity') -> Set[Tuple[int, int]]:
        los_tiles = set()
        position = self.get_entity_position(entity.id)
        
        if position is None:
            print(f"Warning: Entity {entity.name} has no position on the battlemap.")
            return los_tiles

        def mark_visible(x, y):
            los_tiles.add((x, y))
        
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
        self.update_entity_position(entity, position)
        self.update_entity_senses(entity)
        print(f"Entity {entity_id} battlemap_id: {entity.battlemap_id}")
        print(f"Entity {entity_id} sensory battlemap_id: {entity.sensory.battlemap_id if entity.sensory else 'No sensory'}")

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
        self.update_entity_position(entity, new_position)
        self.update_entity_senses(entity)

    def move_entity_without_update(self, entity: 'Entity', new_position: Tuple[int, int]):
        entity_id = entity.id
        old_position = self.entities[entity_id]
        self.positions[old_position].remove(entity_id)
        if not self.positions[old_position]:
            del self.positions[old_position]

        self.entities[entity_id] = new_position
        self.positions[new_position].add(entity_id)
        self.update_entity_position(entity, new_position)

    def get_entity_position(self, entity_id: str) -> Optional[Tuple[int, int]]:
        return self.entities.get(entity_id)

    def update_entity_position(self, entity: 'Entity', position: Tuple[int, int]):
        if entity.sensory:
            entity.sensory.update_origin(position)
        else:
            print(f"Warning: Entity {entity.name} has no sensory component.")

    def update_entity_senses(self, entity: 'Entity'):
        if entity.sensory:
            self.update_entity_fov(entity)
            self.update_entity_distance_matrix(entity)
            self.update_entity_paths(entity)
        else:
            print(f"Warning: Entity {entity.name} has no sensory component. Skipping sense updates.")

    def update_entity_fov(self, entity: 'Entity'):
        los_tiles = self.compute_line_of_sight(entity)
        if entity.sensory:
            entity.sensory.update_fov(los_tiles)
        else:
            print(f"Warning: Entity {entity.name} has no sensory component. Skipping FOV update.")

    def update_entity_distance_matrix(self, entity: 'Entity'):
        position = self.get_entity_position(entity.id)
        if position:
            distances, _ = self.compute_dijkstra(position)
            if entity.sensory:
                entity.sensory.update_distance_matrix(distances)
            else:
                print(f"Warning: Entity {entity.name} has no sensory component. Skipping distance matrix update.")
        else:
            print(f"Warning: Entity {entity.name} has no position on the battlemap. Skipping distance matrix update.")

    def update_entity_paths(self, entity: 'Entity'):
        position = self.get_entity_position(entity.id)
        if position:
            _, paths = self.compute_dijkstra(position)
            if entity.sensory:
                entity.sensory.update_paths(paths)
            else:
                print(f"Warning: Entity {entity.name} has no sensory component. Skipping paths update.")
        else:
            print(f"Warning: Entity {entity.name} has no position on the battlemap. Skipping paths update.")

    def __str__(self) -> str:
        return f"BattleMap(id={self.id}, width={self.width}, height={self.height}, entities={len(self.entities)})"
    
