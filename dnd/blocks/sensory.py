from typing import Dict, Optional, Any, List, Self, Literal,ClassVar, Union, Callable, Tuple, Set, DefaultDict
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field,field_validator
from dnd.core.values import ModifiableValue, StaticValue
from dnd.core.modifiers import NumericalModifier, DamageType , ResistanceStatus, ContextAwareCondition, saving_throws, ResistanceModifier

from enum import Enum
from random import randint
from functools import cached_property
from typing import Literal as TypeLiteral
import math
from collections import defaultdict

from dnd.core.base_block import BaseBlock

class SensesType(str, Enum):
    BLINDSIGHT = "Blindsight"
    DARKVISION = "Darkvision"
    TREMORSENSE = "Tremorsense"
    TRUESIGHT = "Truesight"

class Senses(BaseBlock):
    """ A block that contains the senses of a creature"""
    entities : Dict[UUID,Tuple[int,int]] = Field(default_factory=dict)
    visible: Dict[Tuple[int,int],bool] = Field(default_factory=dict)
    walkable: Dict[Tuple[int,int],bool] = Field(default_factory=dict)
    paths: DefaultDict[Tuple[int,int],List[Tuple[int,int]]] = Field(default_factory=lambda: defaultdict(list))
    extra_senses: List[SensesType] = Field(default_factory=list)
    seen: Set[Tuple[int,int]] = Field(default_factory=set, description="A list of positions that the entity has seen")



    def add_entity(self,entity_uuid: UUID,position: Tuple[int,int]):
        """ add an entity to the senses"""
        self.entities[entity_uuid] = position

    def get_distance(self,position: Tuple[int,int]) -> int:
        """ get the euclidean distance between the position and the position of the senses"""
        return int(math.sqrt((self.position[0] - position[0])**2 + (self.position[1] - position[1])**2))
    
    def get_feet_distance(self,position: Tuple[int,int]) -> int:
        """ get the euclidean distance in feet between the position and the position of the senses and then multiply by 5 to obtain the distance in feet"""
        return self.get_distance(position) * 5
    
    def get_path_to_entity(self,entity_uuid: UUID, max_path_length: Optional[int] = None) -> List[Tuple[int,int]]:
        """ Get the path to the entity"""
        if entity_uuid not in self.entities:
            return []
        path = self.paths.get(self.entities[entity_uuid],[])
        if max_path_length is None or len(path) <= max_path_length:
            return path
        else:
            return []
    
    def update_seen(self, visible: Dict[Tuple[int,int],bool]):
        """ update the seen list"""
        visible_positions = set([key for key,value in visible.items() if value])
        self.seen.update(visible_positions)

    
    def update_senses(self,  entities: Dict[UUID,Tuple[int,int]], visible: Dict[Tuple[int,int],bool], walkable: Dict[Tuple[int,int],bool],paths: DefaultDict[Tuple[int,int],List[Tuple[int,int]]]):
        #sets all to empty dicts
        self.entities = {}
        self.visible = {}
        self.walkable = {}
        self.paths = defaultdict(list)
        #sets all to the new values
        self.entities = entities
        self.visible = visible
        self.update_seen(visible)
        self.walkable = walkable
        self.paths = paths

    def get_threathened_positions(self) -> List[Tuple[int,int]]:
        """ given a position we get all neighbors (also diagonals), we use sets to do quickly and check they are in both visible dict and a path exist"""
        position = self.position
        neighbors = set([(position[0]+1,position[1]),
                        (position[0]-1,position[1]),
                        (position[0],position[1]+1),
                        (position[0],position[1]-1),
                        (position[0]+1,position[1]+1),
                        (position[0]-1,position[1]-1)])
        visible_set = set(self.visible.keys())
        path_set = set(self.paths.keys())
        return list(neighbors & visible_set & path_set)
        

    @classmethod
    def create(cls,source_entity_uuid: UUID,name: str = "Senses", source_entity_name: Optional[str] = None, target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, position: Tuple[int,int] = (0,0)) -> Self:
        return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, position=position)
    
