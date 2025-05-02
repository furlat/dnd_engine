from uuid import UUID, uuid4
from pydantic import Field, computed_field
from typing import Dict, Any, Optional, Self, Union, List, Tuple

from pydantic import BaseModel, model_validator
from enum import Enum
from dnd.core.modifiers import ContextAwareCondition, BaseObject
from dnd.core.values import ModifiableValue
from dnd.core.events import Event, EventPhase, EventType, SavingThrowEvent
class DurationType(str,Enum):
    ROUNDS = "rounds"
    PERMANENT = "permanent"
    UNTIL_LONG_REST = "until_long_rest"
    ON_CONDITION = "on_condition"

class Duration(BaseObject):
    duration : Optional[Union[int,ContextAwareCondition]] = Field(default=None,description="The duration of the condition")
    duration_type: DurationType = Field(default=DurationType.PERMANENT,description="The type of duration")
    source_entity_uuid: UUID = Field(default_factory=uuid4,description="The UUID of the source entity")
    target_entity_uuid: UUID = Field(default_factory=uuid4,description="The UUID of the target entity")
    context: Optional[Dict[str,Any]] = Field(default=None,description="The context of the condition")
    long_rested: bool = Field(default=False,description="Whether the condition has been long rested")
    owned_by_condition: Optional[UUID] = Field(default=None,description="The UUID of the condition that owns this duration")
    

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
            duration = self.duration(self.source_entity_uuid,self.target_entity_uuid,self.context)
            if duration is None:
                return False
            return duration
        elif self.duration_type == DurationType.UNTIL_LONG_REST:
            return self.long_rested
        else:
            return False
    
    def progress(self) -> bool:
        """ Progress the duration by one round """
        if self.duration_type == DurationType.ROUNDS:
            assert isinstance(self.duration,int)
            self.duration -= 1
            if self.is_expired:
                return True
            return False
        else:
            return False
    
    def long_rest(self) -> None:
        """ Set the long rested flag to True """
        self.long_rested = True


class ConditionApplicationEvent(Event):
    """An event that represents the application of a condition"""
    name: str = Field(default="Condition Application",description="A condition application event")
    condition: 'BaseCondition' = Field(description="The condition that is being applied")
    event_type: EventType = Field(default=EventType.CONDITION_APPLICATION,description="The type of event")


class BaseCondition(BaseObject):
    """ Noticed that removal and application saving throws are not implemented yet at the level of Entity class"""
    duration: Duration = Field(default_factory=Duration)
    application_saving_throw: Optional[SavingThrowEvent] = None
    removal_saving_throw: Optional[SavingThrowEvent] = None
    applied:bool = Field(default=False)
    modifers_uuids: Dict[UUID,List[UUID]] = Field(default_factory=dict,description="keys are ModifiableValues UUID and values are list of modifiers UUIDs applied to those blocks")
    parent_condition: Optional[UUID] = Field(default=None,description="the UUID of the parent condition, if it exists")
    sub_conditions: List[UUID] = Field(default_factory=list,description="list of condition UUIDs that are sub conditions of this condition, they will be removed when this condition is removed, they must be applied in the _apply if an ApplyConditionEvent object is given as input to _apply the sub conditions will triget sub events ")
    event_handlers_uuids: List[UUID] = Field(default_factory=list,description="list of event handler UUIDs that are event handlers of this condition, they will be removed when this condition is removed, they must be applied in the _apply if an ApplyConditionEvent object is given as input to _apply the event handlers will trigger event handlers ")
    @model_validator(mode="after")
    def check_duration_consistency(self) -> Self:
        """ ensure the the duration ownership is consistent """
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

    def _declare_event(self, parent_event: Optional[Event] = None) -> Event:
        """ Declare the event """
        return ConditionApplicationEvent(condition=self,source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.target_entity_uuid, phase=EventPhase.DECLARATION, parent_event=parent_event.uuid if parent_event else None)

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        """ Apply the condition and return the modifiers associated with the condition full implementation is in the subclass 
        the event is used as parent if subconditions are triggered (e.g. sub conditons application)"""
        # event is declared in the main apply method
        
        event = event.phase_to(EventPhase.EXECUTION, update={"condition":self}) # execution is defined, last chance to modify it
        event = event.phase_to(EventPhase.EFFECT, update={"condition":self}) # effect is defined reactions to the effect applications
        #completions happend in main apply method such that 
        
        return [],[],[], event
    
    def _remove(self) -> Optional[Event]:
        """Custom extra Remove the condition full implementation is in the subclass if needed, should try to use the registries if possible"""
        return None
    
    def apply(self, parent_event: Optional[Event] = None) -> Optional[Event]:
        """ Apply the condition """
        if self.applied or self.duration.is_expired:
            return None
        #first create the declaration event
        event = self._declare_event(parent_event)
        if event.canceled: #check if event was canceled at declaration
            return None
        #then apply the condition
        modifers_uuids, event_handlers_uuids, sub_conditions_uuids, applied_event = self._apply(event)
        if not applied_event or (len(modifers_uuids) == 0 and len(event_handlers_uuids) == 0 and len(sub_conditions_uuids) == 0):
            return event.cancel(status_message=f"Condition {self.name} was not applied for some unknown reason, check the implementaiton of _apply method")
        
        
        for block_uuid, modifiers_uuids in modifers_uuids:
            if block_uuid not in self.modifers_uuids:
                self.modifers_uuids[block_uuid] = []
            self.modifers_uuids[block_uuid].append(modifiers_uuids)

        for event_handler_uuid in event_handlers_uuids:
            if event_handler_uuid not in self.event_handlers_uuids:
                self.event_handlers_uuids.append(event_handler_uuid)
        
        for sub_condition_uuid in sub_conditions_uuids:
            if sub_condition_uuid not in self.sub_conditions:
                self.sub_conditions.append(sub_condition_uuid)

        self.applied = True
        completed_event = applied_event.phase_to(EventPhase.COMPLETION)
        return completed_event
    
    def remove(self,skip_parent_removal: bool = False) -> bool:
        """ Remove the condition """
        if not self.applied:
            return False
        #first apply the remove method
        remove_result = self._remove()
        if not remove_result:
            return False
        for value_uuid, modifiers_uuids in self.modifers_uuids.items():
            value = ModifiableValue.get(value_uuid)
            if value is None:
                raise ValueError(f"Trying to remove value with UUID {value_uuid} not found")
            for modifier_uuid in modifiers_uuids:
                value.remove_modifier(modifier_uuid)
        self.applied = False
        for sub_condition_uuid in self.sub_conditions:
            sub_condition = BaseCondition.get(sub_condition_uuid)
            if sub_condition is None:
                raise ValueError(f"Trying to remove sub condition with UUID {sub_condition_uuid} not found sub-condition removal should remove it from the parent reference")
            elif isinstance(sub_condition,BaseCondition):
                sub_condition.remove(skip_parent_removal=True)
        
        #remove the condition from the parent
        if self.parent_condition and not skip_parent_removal:
            parent_condition = BaseCondition.get(self.parent_condition)
            if parent_condition is None:
                raise ValueError(f"Trying to remove condition with UUID {self.uuid} from parent with UUID {self.parent_condition} not found, parent removal should remove children")
            elif isinstance(parent_condition,BaseCondition):
                parent_condition.sub_conditions.remove(self.uuid)
               
        return True
    
    def progress(self) -> bool:
        """ Progress the duration returns True if the condition is removed """
        progress_result = self.duration.progress()
        if progress_result:
            self.remove()
        return progress_result
    
    def long_rest(self) -> None:
        """ Set the long rested flag to True """
        self.duration.long_rest()
