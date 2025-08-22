from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Tuple
from uuid import UUID
from dnd.blocks.sensory import Senses, SensesType



class SensesSnapshot(BaseModel):
    """Interface model for a Senses block"""
    entities: Dict[UUID, Tuple[int, int]] = Field(default_factory=dict)
    visible: Dict[Tuple[int, int], bool] = Field(default_factory=dict)
    walkable: Dict[Tuple[int, int], bool] = Field(default_factory=dict)
    paths: Dict[Tuple[int, int], List[Tuple[int, int]]] = Field(default_factory=dict)
    extra_senses: List[SensesType] = Field(default_factory=list)
    position: Tuple[int, int]
    seen: List[Tuple[int, int]] = Field(default_factory=list)

    @classmethod
    def from_engine(cls, senses: Senses):
        """Create a snapshot from an engine Senses object"""
        return cls(
            entities=senses.entities,
            visible=senses.visible,
            walkable=senses.walkable,
            paths=senses.paths,
            extra_senses=senses.extra_senses,
            position=senses.position,
            seen=list(senses.seen)
        )