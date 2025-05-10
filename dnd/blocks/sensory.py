from typing import Dict, Optional, Any, List, Self, Literal,ClassVar, Union, Callable, Tuple
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field,field_validator
from dnd.core.values import ModifiableValue, StaticValue
from dnd.core.modifiers import NumericalModifier, DamageType , ResistanceStatus, ContextAwareCondition, BaseObject, saving_throws, ResistanceModifier

from enum import Enum
from random import randint
from functools import cached_property
from typing import Literal as TypeLiteral
import math

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
    paths: Dict[Tuple[int,int],List[Tuple[int,int]]] = Field(default_factory=dict)
    extra_senses: List[SensesType] = Field(default_factory=list)

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
    
    def update_senses(self,  entities: Dict[UUID,Tuple[int,int]], visible: Dict[Tuple[int,int],bool], walkable: Dict[Tuple[int,int],bool],paths: Dict[Tuple[int,int],List[Tuple[int,int]]]):
        self.entities = entities
        self.visible = visible
        self.walkable = walkable
        self.paths = paths

    @classmethod
    def create(cls,source_entity_uuid: UUID,name: str = "Senses", source_entity_name: Optional[str] = None, target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, position: Tuple[int,int] = (0,0)) -> Self:
        return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, position=position)
    
