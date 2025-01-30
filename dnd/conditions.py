from uuid import UUID, uuid4
from pydantic import Field, computed_field
from typing import Dict, Any, Optional, Self, Union
from pydantic import BaseModel, model_validator
from enum import Enum
from dnd.modifiers import ContextAwareCondition, SavingThrowRequest

class DurationType(Enum,str):
    ROUNDS = "rounds"
    PERMANENT = "permanent"
    UNTIL_LONG_REST = "until_long_rest"
    ON_CONDITION = "on_condition"

class Duration(BaseModel):
    duration : Optional[Union[int,ContextAwareCondition]]
    duration_type: DurationType = Field(default=DurationType.ROUNDS)
    source_entity_uuid: UUID
    target_entity_uuid: UUID
    context: Optional[Dict[str,Any]] = None
    long_rested: bool = Field(default=False)
    owned_by_condition: Optional[UUID] = None
    

    def set_owned_by_condition(self,condition_uuid: UUID) -> None:
        """ Set the condition that owns this duration """
        self.owned_by_condition = condition_uuid

    @model_validator(mode="after")
    def check_duration_type_consistency(self) -> Self:
        """ ROUNDS --> int , PERMANENT --> None , UNTIL_DEATH --> None , ON_CONDITION --> ContextAwareCondition """
        if self.duration_type == DurationType.ROUNDS:
            if not isinstance(self.duration,int):
                raise ValueError(f"Duration must be an int when duration_type is ROUNDS instead of {type(self.duration)}")
        elif self.duration_type == DurationType.PERMANENT:
            if self.duration is not None:
                raise ValueError(f"Duration must be None when duration_type is PERMANENT instead of {self.duration}")
        elif self.duration_type == DurationType.UNTIL_LONG_REST:
            if self.duration is not None:
                raise ValueError(f"Duration must be None when duration_type is UNTIL_LONG_REST instead of {self.duration}")
        elif self.duration_type == DurationType.ON_CONDITION:
            if not isinstance(self.duration,ContextAwareCondition):
                raise ValueError(f"Duration must be a ContextAwareCondition when duration_type is ON_CONDITION instead of {type(self.duration)}")
        return self
    
    @computed_field
    @property
    def is_expired(self) -> bool:
        """ Check if the duration is expired """
        if self.duration_type == DurationType.ROUNDS:
            assert isinstance(self.duration,int)
            return self.duration >= 0
        elif self.duration_type == DurationType.ON_CONDITION:
            assert isinstance(self.duration,ContextAwareCondition)
            return self.duration(self.source_entity_uuid,self.target_entity_uuid,self.context)
        elif self.duration_type == DurationType.UNTIL_LONG_REST:
            return self.long_rested
        else:
            return False
    
    def progress(self) -> None:
        """ Progress the duration by one round """
        if self.duration_type == DurationType.ROUNDS:
            assert isinstance(self.duration,int)
            self.duration -= 1
    
    def long_rest(self) -> None:
        """ Set the long rested flag to True """
        self.long_rested = True
        

class BaseCondition(BaseModel):
    name: str
    uuid: UUID = Field(default_factory=lambda: uuid4())
    description: str
    duration: Duration
    source_entity_uuid: UUID
    target_entity_uuid: UUID
    context: Optional[Dict[str,Any]] = None
    application_saving_throw: Optional[SavingThrowRequest] = None
    removal_saving_throw: Optional[SavingThrowRequest] = None
    applied:bool = Field(default=False)

    @model_validator(mode="after")
    def check_duration_consistency(self) -> Self:
        """ Check if the duration is consistent """
        self.duration.set_owned_by_condition(self.uuid)
        return self
    
    def set_context(self,context: Dict[str,Any]) -> None:
        """ Set the context for the duration """
        self.context = context
        self.duration.context = context
    
    def clear_context(self) -> None:
        """ Clear the context for the duration """
        self.context = None
        self.duration.context = None
    def set_source_entity(self,source_entity_uuid: UUID) -> None:
        """ Set the source entity for the duration """
        self.source_entity_uuid = source_entity_uuid
        self.duration.source_entity_uuid = source_entity_uuid
    def set_target_entity(self,target_entity_uuid: UUID) -> None:
        """ Set the target entity for the duration """
        self.target_entity_uuid = target_entity_uuid
        self.duration.target_entity_uuid = target_entity_uuid

    def _apply(self) -> bool:
        """ Apply the condition full implementation is in the subclass """
        return True
    
    def apply(self) -> bool:
        """ Apply the condition """
        if self.applied or self.duration.is_expired:
            return False
        self.applied = self._apply()
        return self.applied