from uuid import UUID, uuid4
from pydantic import Field, computed_field
from typing import Dict, Any, Optional, Self, Union, List, Tuple

from pydantic import  model_validator
from enum import Enum
from dnd.core.modifiers import ContextAwareCondition
from dnd.core.base_object import BaseObject
from dnd.core.values import ModifiableValue
from dnd.core.events import Event, EventPhase, EventType, SavingThrowEvent, EventHandler, EventQueue
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType

# Internal marker conditions that should never generate combat logs
INTERNAL_MARKER_CONDITIONS = {"HasAttacked", "HasTakenDamage"}

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
            if not callable(self.duration):
                raise ValueError(f"Duration must be a ContextAwareCondition (callable) when duration_type is ON_CONDITION instead of {type(self.duration)}")
        return self
    
    @computed_field
    @property
    def is_expired(self) -> bool:
        """ Check if the duration is expired """
        if self.duration_type == DurationType.ROUNDS:
            assert isinstance(self.duration,int)
            return self.duration <= 0  # Expired when duration reaches 0 or below
        elif self.duration_type == DurationType.ON_CONDITION:
            assert callable(self.duration)
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
    source_entity_name: Optional[str] = Field(default=None, description="Name of the source entity")
    target_entity_name: Optional[str] = Field(default=None, description="Name of the target entity")

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Generate combat log for condition application."""
        cond = self.condition
        condition_name = cond.name or "Unknown"

        # Suppress combat logs for internal marker conditions
        if condition_name in INTERNAL_MARKER_CONDITIONS:
            return None

        target_name = self.target_entity_name or "Unknown"
        source_name = self.source_entity_name or "Unknown"

        # Build condition-specific compact text
        if condition_name == "Hidden":
            stealth_dc = getattr(cond, 'stealth_result', 0)
            compact = f"{{cyan:{target_name}}} gains **Hidden** (Stealth DC {stealth_dc})"
        elif condition_name == "Invisible":
            compact = f"{{cyan:{target_name}}} becomes **invisible**"
        else:
            compact = f"{{cyan:{target_name}}} gains **{condition_name}**"

        # Verbose adds source info when source != target
        verbose = compact
        if self.source_entity_uuid != self.target_entity_uuid and source_name != target_name:
            verbose = compact + f" from {{yellow:{source_name}}}"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.CONDITION_APPLIED,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else None,
            compact=compact,
            verbose=verbose,
            detailed=verbose,
            success=True,
        )


class ConditionRemovalEvent(Event):
    """An event that represents the removal of a condition"""
    name: str = Field(default="Condition Removal", description="A condition removal event")
    condition: 'BaseCondition' = Field(description="The condition that is being removed")
    expired: bool = Field(default=False, description="Whether the condition was removed due to expiration")
    event_type: EventType = Field(default=EventType.CONDITION_REMOVAL, description="The type of event")
    source_entity_name: Optional[str] = Field(default=None, description="Name of the source entity")
    target_entity_name: Optional[str] = Field(default=None, description="Name of the target entity")

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Generate combat log for condition removal."""
        cond = self.condition
        condition_name = cond.name or "Unknown"

        # Suppress combat logs for internal marker conditions
        if condition_name in INTERNAL_MARKER_CONDITIONS:
            return None

        target_name = self.target_entity_name or "Unknown"
        source_name = self.source_entity_name or "Unknown"

        compact = f"{{cyan:{target_name}}} is no longer **{condition_name}**"

        verbose = compact
        if self.expired:
            verbose = compact + " (expired)"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.CONDITION_REMOVED,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else None,
            compact=compact,
            verbose=verbose,
            detailed=verbose,
            success=True,
        )


class BaseCondition(BaseObject):
    """ Noticed that removal and application saving throws are not implemented yet at the level of Entity class"""
    duration: Duration = Field(default_factory=Duration)
    application_saving_throw: Optional[SavingThrowEvent] = None
    removal_saving_throw: Optional[SavingThrowEvent] = None
    applied:bool = Field(default=False)
    source_entity_name: Optional[str] = Field(default=None, description="Name of the source entity (populated by Entity.add_condition)")
    target_entity_name: Optional[str] = Field(default=None, description="Name of the target entity (populated by Entity.add_condition)")
    modifers_uuids: Dict[UUID,List[UUID]] = Field(default_factory=dict,description="keys are ModifiableValues UUID and values are list of modifiers UUIDs applied to those blocks")
    parent_condition: Optional[UUID] = Field(default=None,description="the UUID of the parent condition, if it exists")
    sub_conditions: List[UUID] = Field(default_factory=list,description="list of condition UUIDs that are sub conditions of this condition, they will be removed when this condition is removed, they must be applied in the _apply if an ApplyConditionEvent object is given as input to _apply the sub conditions will triget sub events ")
    event_handlers_uuids: List[UUID] = Field(default_factory=list,description="list of event handler UUIDs that are event handlers of this condition, they will be removed when this condition is removed, they must be applied in the _apply if an ApplyConditionEvent object is given as input to _apply the event handlers will trigger event handlers ")
    spatial_handler_uuids: List[UUID] = Field(default_factory=list, description="list of spatial handler UUIDs that are spatial handlers of this condition, they will be removed when this condition is removed via remove_spatial_handlers()")
    linked_conditions: List[Tuple[UUID, UUID]] = Field(
        default_factory=list,
        description="(target_block_uuid, condition_uuid) pairs for conditions placed on OTHER BaseBlocks (entities, tiles, items). Removed when this condition is removed."
    )
    
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
        return ConditionApplicationEvent(
            name=self.name,
            condition=self,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            phase=EventPhase.DECLARATION,
            parent_event=parent_event.uuid if parent_event else None,
            source_entity_name=self.source_entity_name,
            target_entity_name=self.target_entity_name
        )

    def _declare_removal_event(self, expired: bool = False, parent_event: Optional[Event] = None) -> Event:
        """Declare the removal event"""
        return ConditionRemovalEvent(
            name=self.name if self.name else "Condition Removal",
            condition=self,
            expired=expired,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            phase=EventPhase.DECLARATION,
            parent_event=parent_event.uuid if parent_event else None,
            source_entity_name=self.source_entity_name,
            target_entity_name=self.target_entity_name
        )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],List[UUID],Optional[Event]]:
        """Apply the condition and return the modifiers associated with the condition.

        Full implementation is in the subclass. The event is used as parent if
        subconditions are triggered (e.g. sub conditions application).

        Returns:
            Tuple of:
            - List[Tuple[UUID, UUID]]: (modifiable_value_uuid, modifier_uuid) pairs
            - List[UUID]: event_handler_uuids (trigger-based handlers)
            - List[UUID]: subcondition_uuids
            - List[UUID]: spatial_handler_uuids (position-indexed handlers)
            - Optional[Event]: completion event
        """
        # event is declared in the main apply method

        event = declaration_event.phase_to(EventPhase.EXECUTION, update={"condition":self}) # execution is defined, last chance to modify it
        event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition":self}) # effect is defined reactions to the effect applications
        #completions happen in main apply method such that

        return [],[],[],[], event
    
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
        modifers_uuids, event_handlers_uuids, sub_conditions_uuids, spatial_handler_uuids, effect_event = self._apply(declaration_event)

        # Check if _apply returned an effect event (marker conditions are valid even without modifiers)
        if not effect_event:
            return declaration_event.cancel(status_message=f"Condition {self.name} was not applied - _apply() returned no effect event")


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
        for spatial_handler_uuid in spatial_handler_uuids:
            if spatial_handler_uuid not in self.spatial_handler_uuids:
                self.spatial_handler_uuids.append(spatial_handler_uuid)

        self.applied = True
        completed_event = effect_event.phase_to(EventPhase.COMPLETION)
        return completed_event
    
    def remove_condition_modifiers(self) -> bool:
        """ Remove the condition modifiers (does NOT set self.applied = False) """
        if not self.applied:
            return False

        for value_uuid, modifiers_uuids in self.modifers_uuids.items():
            value = ModifiableValue.get(value_uuid)
            if value is None:
                raise ValueError(f"Trying to remove value with UUID {value_uuid} not found")
            for modifier_uuid in modifiers_uuids:
                value.remove_modifier(modifier_uuid)
        return True
    
    def add_linked_condition(self, target_block_uuid: UUID, condition_uuid: UUID) -> None:
        """Track a condition this condition placed on another BaseBlock.

        When this condition is removed, the linked condition will also be removed
        from the target block. Works for entities, tiles, and future items.

        Args:
            target_block_uuid: The UUID of the BaseBlock that has the condition
            condition_uuid: The UUID of the condition on that block
        """
        self.linked_conditions.append((target_block_uuid, condition_uuid))

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
                continue  # event handler not found, it was already removed
            elif isinstance(event_handler, EventHandler):
                event_handler.remove()
        self.event_handlers_uuids.clear()
        return True

    def remove_spatial_handlers(self) -> bool:
        """Remove all spatial handlers owned by this condition.

        Spatial handlers are position-indexed handlers registered via
        EventQueue.add_spatial_handler(). They are stored separately
        from trigger-based EventHandlers.
        """
        if not self.applied:
            return False
        for handler_uuid in self.spatial_handler_uuids:
            EventQueue.remove_spatial_handler(handler_uuid)
        self.spatial_handler_uuids.clear()
        return True

    def cleanup_own_state(self, expire: bool = False, parent_event: Optional[Event] = None) -> bool:
        """Clean up ONLY this condition's modifiers, handlers, and events.

        Cross-object cleanup (sub_conditions, linked_conditions)
        is handled by BaseBlock._remove_condition_tree().

        NOTE: _remove() hook is PRESERVED for custom cleanup logic.

        Args:
            expire: Whether this is an expiration removal
            parent_event: Parent event for event chain tracking

        Returns:
            True if cleanup succeeded, False if canceled
        """
        if not self.applied:
            return False

        # Declare the removal event
        event = self._declare_removal_event(expired=expire, parent_event=parent_event)
        if event.canceled:
            return False

        # Handle expiration hook if needed
        if expire:
            expired_event = self._expire(event)
            if expired_event and expired_event.canceled:
                return False

        # Custom removal logic - PRESERVED HOOK
        removed_event = self._remove(event)
        if removed_event and removed_event.canceled:
            return False

        # Clean up own modifiers and handlers ONLY
        self.remove_condition_modifiers()
        self.remove_event_handlers()
        self.remove_spatial_handlers()

        # Unlink from parent (but don't remove parent)
        if self.parent_condition:
            parent = BaseCondition.get(self.parent_condition)
            if parent is not None and isinstance(parent, BaseCondition):
                if self.uuid in parent.sub_conditions:
                    parent.sub_conditions.remove(self.uuid)

        self.applied = False

        # Complete event
        event.phase_to(EventPhase.COMPLETION)
        return True

    def progress(self) -> bool:
        """Progress the duration, return True if expired.

        NOTE: Does NOT remove the condition - caller must handle removal.
        This avoids circular imports by letting Entity handle tree traversal.
        """
        return self.duration.progress()
    
    def long_rest(self) -> None:
        """ Set the long rested flag to True """
        self.duration.long_rest()
