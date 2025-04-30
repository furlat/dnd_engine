from typing import Dict, Optional, Any, List, Self, Literal,ClassVar, Union, Callable, Tuple
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field,field_validator
from dnd.core.values import ModifiableValue, StaticValue
from dnd.core.modifiers import NumericalModifier, DamageType , ResistanceStatus, ContextAwareCondition, BaseObject, saving_throws, ResistanceModifier

from enum import Enum
from random import randint
from functools import cached_property
from typing import Literal as TypeLiteral


from dnd.blocks.base_block import BaseBlock


class Senses(BaseBlock):
    """ A block that contains the senses of a creature"""
    position: Tuple[int,int] = Field(default_factory=lambda: (0,0))
    entities : Dict[UUID,Tuple[int,int]] = Field(default_factory=dict)
    visible: Dict[Tuple[int,int],bool] = Field(default_factory=dict)
    walkable: Dict[Tuple[int,int],bool] = Field(default_factory=dict)
    paths: Dict[Tuple[int,int],List[Tuple[int,int]]] = Field(default_factory=dict)

    def get_path_to_entity(self,entity_uuid: UUID, max_path_length: Optional[int] = None) -> List[Tuple[int,int]]:
        """ Get the path to the entity"""
        if entity_uuid not in self.entities:
            return []
        path = self.paths.get(self.entities[entity_uuid],[])
        if max_path_length is None or len(path) <= max_path_length:
            return path
        else:
            return []
    
    def update_senses(self, position: Tuple[int,int], entities: Dict[UUID,Tuple[int,int]], visible: Dict[Tuple[int,int],bool], walkable: Dict[Tuple[int,int],bool],paths: Dict[Tuple[int,int],List[Tuple[int,int]]]):
        self.position = position
        self.entities = entities
        self.visible = visible
        self.walkable = walkable
        self.paths = paths

    @classmethod
    def create(cls,source_entity_uuid: UUID,name: str = "Senses", source_entity_name: Optional[str] = None, target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, position: Tuple[int,int] = (0,0)) -> Self:
        return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, position=position)
    
