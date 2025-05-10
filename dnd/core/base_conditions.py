from uuid import UUID, uuid4
from pydantic import Field, computed_field
from typing import Dict, Any, Optional, Self, Union, List, Tuple

from pydantic import BaseModel, model_validator
from enum import Enum
from dnd.core.modifiers import ContextAwareCondition, BaseObject
from dnd.core.values import ModifiableValue
from dnd.core.events import Event, EventPhase, EventType, SavingThrowEvent, EventHandler
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


class ConditionRemovalEvent(Event):
    """An event that represents the removal of a condition"""
    name: str = Field(default="Condition Removal", description="A condition removal event")
    condition: 'BaseCondition' = Field(description="The condition that is being removed")
    expired: bool = Field(default=False, description="Whether the condition was removed due to expiration")
    event_type: EventType = Field(default=EventType.CONDITION_REMOVAL, description="The type of event")


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

    def declare_event(self, parent_event: Optional[Event] = None) -> Event:
        """ Declare the event """
        if not self.name:
            raise ValueError("Condition name is not set")
        return ConditionApplicationEvent(name=self.name,condition=self,source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.target_entity_uuid, phase=EventPhase.DECLARATION, parent_event=parent_event.uuid if parent_event else None)

    def _declare_removal_event(self, expired: bool = False, parent_event: Optional[Event] = None) -> Event:
        """Declare the removal event"""
        return ConditionRemovalEvent(
            name=self.name if self.name else "Condition Removal",
            condition=self,
            expired=expired,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            phase=EventPhase.DECLARATION,
            parent_event=parent_event.uuid if parent_event else None
        )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        """ Apply the condition and return the modifiers associated with the condition full implementation is in the subclass 
        the event is used as parent if subconditions are triggered (e.g. sub conditons application)"""
        # event is declared in the main apply method
        
        event = declaration_event.phase_to(EventPhase.EXECUTION, update={"condition":self}) # execution is defined, last chance to modify it
        event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self}) # effect is defined reactions to the effect applications
        #completions happend in main apply method such that 
        
        return [],[],[], event
    
    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Custom extra Remove the condition full implementation is in the subclass if needed"""
        if event:
            event = event.phase_to(EventPhase.EXECUTION, update={"condition": self})
            event = event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return event

    def _expire(self, event: Optional[Event] = None) -> Optional[Event]:
        """Custom extra Expire called during removal from natural expiration"""
        if event:
            event = event.phase_to(EventPhase.EXECUTION, update={"condition": self})
            event = event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return event

    def apply(self, parent_event: Optional[Event] = None,declaration_event: Optional[Event] = None) -> Optional[Event]:
        """ Apply the condition """
        if self.applied or self.duration.is_expired:
            return None
        #first create the declaration event
        if declaration_event is None:
            declaration_event = self.declare_event(parent_event)
     
        if declaration_event.canceled: #check if event was canceled at declaration
            return None
        
        #
        #then apply the condition
        modifers_uuids, event_handlers_uuids, sub_conditions_uuids, effect_event = self._apply(declaration_event)
        if not effect_event or (len(modifers_uuids) == 0 and len(event_handlers_uuids) == 0 and len(sub_conditions_uuids) == 0):
            return declaration_event.cancel(status_message=f"Condition {self.name} was not applied for some unknown reason, check the implementaiton of _apply method")
        
        
        for block_uuid, modifiers_uuids in modifers_uuids:
            if block_uuid not in self.modifers_uuids:
                self.modifers_uuids[block_uuid] = []
            self.modifers_uuids[block_uuid].append(modifiers_uuids)

        for event_handler_uuid in event_handlers_uuids:
            if event_handler_uuid not in self.event_handlers_uuids:
                self.event_handlers_uuids.append(event_handler_uuid)
        print(f"Sub conditions uuids: {sub_conditions_uuids}")
        for sub_condition_uuid in sub_conditions_uuids:
            if sub_condition_uuid not in self.sub_conditions:
                print(f"Adding sub condition {sub_condition_uuid} to {self.name} with UUID {self.uuid}")
                self.sub_conditions.append(sub_condition_uuid)

        self.applied = True
        completed_event = effect_event.phase_to(EventPhase.COMPLETION)
        return completed_event
    
    def remove_condition_modifiers(self) -> bool:
        """ Remove the condition """
        if not self.applied:
            return False

        for value_uuid, modifiers_uuids in self.modifers_uuids.items():
            value = ModifiableValue.get(value_uuid)
            if value is None:
                raise ValueError(f"Trying to remove value with UUID {value_uuid} not found")
            for modifier_uuid in modifiers_uuids:
                value.remove_modifier(modifier_uuid)
        self.applied = False

        return True
    
    def remove_sub_conditions(self,parent_event: Optional[Event] = None) -> bool:
        """ Remove the sub conditions """
        # if not self.applied:
        #     return False
        print(f"Removing sub conditions for {self.name} with UUID {self.uuid}")
        if len(self.sub_conditions) == 0:
            print(f"No sub conditions to remove for {self.name} with UUID {self.uuid}")
        print(f"Sub conditions to remove: {self.sub_conditions}")
        for sub_condition_uuid in self.sub_conditions:
            sub_condition = BaseCondition.get(sub_condition_uuid)
            if sub_condition is None:
                raise ValueError(f"Trying to remove sub condition with UUID {sub_condition_uuid} not found sub-condition removal should remove it from the parent reference")
            elif isinstance(sub_condition,BaseCondition):
                print(f"Removing sub condition {sub_condition.name} with UUID {sub_condition_uuid}")
                sub_condition.remove(skip_parent_removal=True,parent_event=parent_event)
        return True
    
    def remove_condition_from_parent(self,skip_parent_removal: bool = False) -> bool:
        
        #remove the condition from the parent
        if self.parent_condition and not skip_parent_removal:
            parent_condition = BaseCondition.get(self.parent_condition)
            if parent_condition is None:
                raise ValueError(f"Trying to remove condition with UUID {self.uuid} from parent with UUID {self.parent_condition} not found, parent removal should remove children")
            elif isinstance(parent_condition,BaseCondition):
                parent_condition.sub_conditions.remove(self.uuid)
               
        return True
    
    def remove_event_handlers(self) -> bool:
        """ Remove the event handlers from the EventQueue"""
        if not self.applied:
            return False
        for event_handler_uuid in self.event_handlers_uuids:
            event_handler = EventHandler.get(event_handler_uuid)
            if event_handler is None:
                return True #event handler not found, it was already removed
            elif isinstance(event_handler,EventHandler):
                event_handler.remove()
        return True

    def remove(self, expire: bool = False, skip_parent_removal: bool = False, parent_event: Optional[Event] = None) -> bool:
        """Remove the condition with event handling"""
        if not self.applied:
            return False
        print(f"remove has been called for {self.name} with UUID {self.uuid}")
        # First declare the removal event
        event = self._declare_removal_event(expired=expire, parent_event=parent_event)
        if event.canceled:  # Check if event was canceled at declaration
            return False

        # Handle expiration if needed
        if expire:
            expired_event = self._expire(event)
            if expired_event and expired_event.canceled:
                return False

        # Handle removal
        removed_event = self._remove(event)
        if removed_event and removed_event.canceled:
            return False

        # Proceed with actual removal operations
        self.remove_condition_modifiers()
        print("just outside remove sub conditions")
        self.remove_sub_conditions(parent_event=event)
        if not skip_parent_removal:
            self.remove_condition_from_parent()
        self.remove_event_handlers()

        # Complete the event
        if event:
            event.phase_to(EventPhase.COMPLETION)

        return True
    
    def progress(self) -> bool:
        """Progress the duration returns True if the condition is removed"""
        progress_result = self.duration.progress()
        if progress_result:
            self.remove(expire=True)
        return progress_result
    
    def long_rest(self) -> None:
        """ Set the long rested flag to True """
        self.duration.long_rest()
