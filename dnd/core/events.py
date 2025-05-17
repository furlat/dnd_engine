""" This is the most "designed" and hardcoded part of the codebase it contains most of the dynamics possible in DND 5e and will be constantly expanded
it introduces and Event qeueue which is the source of ground truth information flow between entities, it allows each action to broadcast its intent and results
 and allow it to be intercepted by reactions and or trigger cascade effects at any point in the game"""


from enum import Enum
from logging import handlers
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal as TypeLiteral, Union,List, Optional, Dict, Any, Self, Literal, TypeVar, Protocol, runtime_checkable
from dnd.core.values import ModifiableValue
from uuid import UUID, uuid4
from dnd.core.dice import Dice, DiceRoll, AttackOutcome, RollType
from datetime import datetime
from dnd.core.modifiers import NumericalModifier, DamageType , ResistanceStatus, ContextAwareCondition, saving_throws, ResistanceModifier
from collections import defaultdict
from typing import Callable, Tuple
from dnd.core.base_object import BaseObject
# Type definition for event listeners
T = TypeVar('T', bound='Event')
E = TypeVar('E', bound='Event')

# Replace Protocol with type alias
EventProcessor = Callable[[E, UUID], Optional[E]]

# More specific event listener types
class TypedEventListener(Protocol[T]):
    """Type definition for event listeners with specific event types."""
    def __call__(self, event: T, source_entity_uuid: UUID) -> Optional[T]: ...

class GenericEventModifier(Protocol):
    """A protocol for callables that can modify any event type."""
    def __call__(self, event: 'Event', source_entity_uuid: UUID) -> Optional['Event']: ...

# Protocol for entities that can have event handlers
@runtime_checkable
class EntityWithEventHandlers(Protocol):
    """Protocol defining the expected structure of entities that can have event handlers.
    This allows for type-safe access to the event_handlers attribute without circular imports.
    """
    event_handlers: Dict[UUID, 'EventHandler']
    
    def remove_event_handler_from_dicts(self, event_handler: 'EventHandler') -> None:
        """Remove an event handler from the entity's event handler dictionaries"""
        ...

AbilityName = TypeLiteral[
    'strength', 'dexterity', 'constitution', 
    'intelligence', 'wisdom', 'charisma'
]

SkillName = TypeLiteral[
    'acrobatics', 'animal_handling', 'arcana', 'athletics', 
    'deception', 'history', 'insight', 'intimidation', 
    'investigation', 'medicine', 'nature', 'perception', 
    'performance', 'persuasion', 'religion', 'sleight_of_hand', 
    'stealth', 'survival'
]





class WeaponSlot(str, Enum):
    MAIN_HAND = "MAIN_HAND"
    OFF_HAND = "OFF_HAND"

class EventType(str, Enum):
    # Core events
    BASE_ACTION = "base_action"
    ATTACK = "attack"
    MOVEMENT = "movement"
    ABILITY_CHECK = "ability_check"
    SAVING_THROW = "saving_throw"
    SKILL_CHECK = "skill_check"
    INFLICT_DAMAGE = "inflicted_damage"
    TAKE_DAMAGE = "take_damage"
    HEAL = "heal"
    CAST_SPELL = "cast_spell"
    ATTACK_MISS = "attack_miss"
    ATTACK_HIT = "attack_hit"
    ATTACK_CRITICAL = "attack_critical"
    CONDITION_APPLICATION = "condition_application"
    CONDITION_REMOVAL = "condition_removal"
    WEAPON_EQUIP = "weapon_equip"
    WEAPON_UNEQUIP = "weapon_unequip"
    ARMOR_EQUIP = "armor_equip"
    ARMOR_UNEQUIP = "armor_unequip"
    SHIELD_EQUIP = "shield_equip"
    SHIELD_UNEQUIP = "shield_unequip"

    #Trigger events
    TRIGGER_EVENT = "trigger_event"
    
    #Dice roll events
    DICE_ROLL = "dice_roll"
    DICE_ROLL_RESULT = "dice_roll_result"

    # Combat events
    ENEMY_SPOTTED = "enemy_spotted"
    ENEMY_KILLED = "enemy_killed"
    ENEMY_ENGAGED = "enemy_engaged"


class EventPhase(str, Enum):
    # Progression of an event
    DECLARATION = "declaration"  # Initial creation - could be the user clicking the target, or the ai considering a possible target of an action
    EXECUTION = "execution"      # Main action - once this start the cost is applied
    EFFECT = "effect"            # Applying effects - this is typically when the roll is resolved and the effects have to be applied, there could be multiple effect for a single event - last chance for a reaction to block or modify the application of the effect
    COMPLETION = "completion"    # Finalizing - the event is complete and the effects have been applied - here is like when post effect like consequences of taking damage are applied. last chance for reaction to partecipate as childrens of this event.
    CANCEL = "cancel"            # Canceling - the event is canceled and the effects are not applied

ordered_event_phases = [EventPhase.DECLARATION, EventPhase.EXECUTION, EventPhase.EFFECT, EventPhase.COMPLETION]


class Event(BaseObject):
    """Base class for all game events"""
    name: str = Field(default="Event",description="The name of the event")
    lineage_uuid: UUID = Field(default_factory=uuid4,description="The lineageuuid of the event, this is shared through modifications of the event")
    #human readable timestamp in typed format
    timestamp : datetime = Field(default_factory=datetime.now,description="The timestamp of the event")
    event_type: EventType = Field(description="The type of event")
    phase: EventPhase = Field(default=EventPhase.DECLARATION,description="The phase of the event")
    
    
    # Flag to indicate if event was modified by reactions
    modified: bool = Field(default=False,description="Flag to indicate if event was modified by reactions")
    
    # Flag to indicate if event should be canceled
    canceled: bool = Field(default=False,description="Flag to indicate if event should be canceled")
    parent_event: Optional[UUID] = Field(default=None,description="The parent event of the current event")
    status_message: Optional[str] = Field(default=None,description="A status message for the event")
    
    # Track children events differently
    lineage_children_events: List[UUID] = Field(default_factory=list,description="All children events that happened throughout this event's lifetime")
    children_events: List[UUID] = Field(default_factory=list,description="Children events that happened during the current phase")
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def get_trigger(self) -> 'Trigger':
        """ get the trigger for the event """
        return Trigger(event_type=self.event_type, event_phase=self.phase,event_source_entity_uuid=self.source_entity_uuid,event_target_entity_uuid=self.target_entity_uuid)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.use_register:
            EventQueue.register(self)
    

    def set_target_entity(self, target_entity_uuid: UUID):
        """Set the target entity for the event"""
        self.target_entity_uuid = target_entity_uuid
       
    
    def phase_to(self, new_phase: Optional[EventPhase] = None, status_message: Optional[str] = None, **updates) -> Self:
        """
        Create a copy of this event with a new phase and optional updates, then post it.
        
        Args:
            new_phase: The new phase to transition to (defaults to next in sequence)
            status_message: Optional message explaining the phase change
            **updates: Additional attributes to update on the event
            
        Returns:
            Self: The new event after processing by the event queue
        """
        if self.phase == EventPhase.COMPLETION:
            return self
        
        # Determine new phase if not specified
        if new_phase is None:
            new_phase = ordered_event_phases[ordered_event_phases.index(self.phase) + 1]
            
        # Create update dictionary
        phase_updates = {}
        phase_updates['phase'] = new_phase
        if status_message is not None:
            phase_updates['status_message'] = status_message
            
        # Add any additional updates
        phase_updates.update(updates)
        
        # Preserve lineage_children_events but clear children_events for new phase
        phase_updates['lineage_children_events'] = self.lineage_children_events + self.children_events
        phase_updates['children_events'] = []
        
        # Post the updated event
        return self.post(**phase_updates)
    
    def cancel(self, status_message: Optional[str] = None, **updates) -> Self:
        """
        Mark this event as canceled and post it.
        
        Args:
            status_message: Optional message explaining why the event was canceled
            **updates: Additional attributes to update on the event
            
        Returns:
            Self: The canceled event after processing
        """
        # Create update dictionary
        cancel_updates = {}
        cancel_updates['canceled'] = True
        cancel_updates['phase'] = EventPhase.CANCEL
        if status_message is not None:
            cancel_updates['status_message'] = status_message
            
        # Add any additional updates
        cancel_updates.update(updates)
        
        # Post the canceled event
        return self.post(**cancel_updates)
    
    def set_parent_event(self, parent_event: 'Event'):
        """Set the parent event for the current event this is NOT the older version of itself which is insterad tracked by the shared uuid
        but instead the parent event is the event under which the current event is registered
        e.g. a attack_miss event will have as parent the attack event that it is a miss of"""
        
        self.parent_event = parent_event.uuid
    
    def add_child_event(self, child_event: 'Event'):
        """Add a child event to both current phase and lineage tracking"""
        self.children_events.append(child_event.uuid)
        if child_event.uuid not in self.lineage_children_events:
            self.lineage_children_events.append(child_event.uuid)

    def get_children_events(self) -> List['Event']:
        """Get all children events of the current event"""
        outs = [EventQueue.get_event_by_uuid(child_event) for child_event in self.children_events]
        return [out for out in outs if out is not None]
    
    def get_parent_event(self) -> Optional['Event']:
        """Get the parent event of the current event"""
        if self.parent_event:
            return EventQueue.get_event_by_uuid(self.parent_event)
        return None
    
    def get_history(self) -> List['Event']:
        """ get all previous version of the event by getting the full list by uuid and getting the current event as last element
        """
        history = EventQueue.get_event_history(self.uuid)
        
        outs= []
        for event in history:
            if event.timestamp < self.timestamp:
                outs.append(event)
        return outs
    
    def post(self, **updates) -> Self:
        """
        Update the event with new values and rebroadcast it through the queue.
        
        This method:
        1. Updates the event with any provided values
        2. Marks the event as modified
        3. Rebroadcasts the event through EventQueue
        4. Returns the potentially modified event after processing
        
        Args:
            **updates: Keyword arguments with values to update on the event
            
        Returns:
            Self: The potentially modified event after rebroadcasting
        """
        # Apply updates
        updates['modified'] = True
        updates['timestamp'] = datetime.now()
        
        # Generate a new UUID but preserve the lineage
        updates['uuid'] = uuid4()
        if 'lineage_uuid' not in updates:
            updates['lineage_uuid'] = self.lineage_uuid
        
        # Create updated event
        updated_event = self.model_copy(update=updates)
        
        # Rebroadcast event through queue
        if updated_event.use_register:
            result = EventQueue.register(updated_event)
        else:
            result = updated_event
        
        # Make sure we have the right type
        if not isinstance(result, self.__class__):
            raise TypeError(f"Expected {self.__class__.__name__} but got {result.__class__.__name__}")
            
        return result  
    
class Trigger(BaseModel):
    name: str = Field(default="Trigger",description="The name of the trigger")
    event_type: EventType = Field(description="The type of event to trigger the event handler")
    event_phase: EventPhase = Field(description="The phase of the event to trigger the event handler")
    event_source_entity_uuid: Optional[UUID] = Field(default=None,description="The source entity uuid of the event handler")
    event_target_entity_uuid: Optional[UUID] = Field(default=None,description="The target entity uuid of the event handler")
    
    model_config = ConfigDict(frozen=True)
    
    def __hash__(self):
        """Make the Trigger hashable for use as dictionary keys"""
        return hash((self.event_type, self.event_phase, 
                    self.event_source_entity_uuid, 
                    self.event_target_entity_uuid))
    
    def __eq__(self, other):
        """Define equality for Trigger objects"""
        if not isinstance(other, Trigger):
            return False
        return (self.event_type == other.event_type and
                self.event_phase == other.event_phase and
                self.event_source_entity_uuid == other.event_source_entity_uuid and
                self.event_target_entity_uuid == other.event_target_entity_uuid)

    def __call__(self, event: Event) -> bool:
        """ checks if the trigger condition is satisfied by the event, this does not guarantee that the event processor will modify the event as it could apply further freeform python prevalidation """

        if event.event_type == self.event_type and event.phase == self.event_phase:
            if self.event_source_entity_uuid  and event.source_entity_uuid != self.event_source_entity_uuid:
                return False
            if self.event_target_entity_uuid and event.target_entity_uuid != self.event_target_entity_uuid:
                return False
            return True
        return False
    
    def is_simple(self) -> bool:
        """ check if the trigger is simple, i.e. it is only based on the event type and phase """
        return self.event_source_entity_uuid is None and self.event_target_entity_uuid is None
    
    def get_simple_trigger(self) -> 'Trigger':
        """ get a simple trigger that is only based on the event type and phase """
        return Trigger(event_type=self.event_type, event_phase=self.event_phase)

class EventHandler(BaseObject):
    """A class that can handle events"""
    name: str = Field(default="EventHandler",description="The name of the event handler")
    trigger_conditions: List[Trigger] = Field(default_factory=list,description="The conditions that trigger the event handler")
    event_processor: EventProcessor = Field(description="The event processor to handle the event")
    
    def __call__(self, event: Event, source_entity_uuid: Optional[UUID] = None) -> Optional[Event]:
        if source_entity_uuid is None:
            source_entity_uuid = self.source_entity_uuid
        if any(trigger(event) for trigger in self.trigger_conditions):
            return self.event_processor(event, source_entity_uuid)
        return None
    
    def get_declaration_event(self, parent_event: Optional[Event] = None) -> Event:
        """ get the declaration event for the event handler """
        return Event(name=self.name,event_type=EventType.TRIGGER_EVENT, event_phase=EventPhase.DECLARATION, source_entity_uuid=self.source_entity_uuid, status_message=f"Triggering event handler {self.name}", parent_event=parent_event.uuid if parent_event else None)
    

    def remove(self) -> bool:
        """ Remove the event handler from the EventQueue"""
        if self.uuid not in EventQueue._event_handlers:
            return False
        EventQueue.remove_event_handler(self)
        entity = BaseObject.get(self.source_entity_uuid)

        if entity is not None and hasattr(entity, "event_handlers"):
            # Use the Protocol to ensure type safety
            if isinstance(entity, EntityWithEventHandlers):
                entity.remove_event_handler_from_dicts(self)

        return True

class EventQueue:
    """Static registry for events with additional querying and reaction capabilities"""
    # Static registry dictionaries
    _events_by_lineage : Dict[UUID, List[Event]] = defaultdict(list)
    _events_by_uuid : Dict[UUID, Event] = {}
    _events_by_type : Dict[EventType, List[Event]] = defaultdict(list)
    _events_by_timestamp : Dict[datetime, List[Event]] = defaultdict(list)
    _events_by_phase : Dict[EventPhase, List[Event]] = defaultdict(list)
    _events_by_source : Dict[UUID, List[Event]] = defaultdict(list)
    _events_by_target : Dict[UUID, List[Event]] = defaultdict(list)
    _all_events : List[Event] = []
    _event_handlers : Dict[UUID, EventHandler] = {}
    _event_handlers_by_trigger : Dict[Trigger, List[EventHandler]] = defaultdict(list)
    _event_handlers_by_simple_trigger : Dict[Trigger, List[EventHandler]] = defaultdict(list)
    _event_handlers_by_source_entity_uuid : Dict[UUID, List[EventHandler]] = defaultdict(list)
    @classmethod
    def register(cls, event: Event) -> Event:
        """Register an event and notify listeners"""
        # Store in all appropriate indices
        cls._store_event(event)
        
        # Check for listeners
        handlers = cls._get_handlers_for_event(event)
    
        # If no listeners or event is already in completion phase, return as is
        if not handlers or event.phase == EventPhase.COMPLETION:
            return event
            
        # Process through listeners
        current_event = event
        for handler in handlers:
            #declare the reaction event
            reaction_event = handler.get_declaration_event(current_event)
            # Executehandler
            result = handler(current_event)
            
            # If listener returned None or canceled event, stop processing
            if result and result.canceled:
                # Store the canceled event
                cls._store_event(result)
                return result
            elif not result:
                return current_event
            
            elif result and result.modified:
                # Update current event for next listener
                current_event = result
                # Update the event in the registry
                cls._store_event(current_event)
            
        return current_event
    
    @classmethod
    def get_event_by_uuid(cls, uuid: UUID) -> Optional[Event]:
        """Get an event by UUID"""
        return cls._events_by_uuid.get(uuid)
    
    @classmethod
    def _store_event(cls, event: Event) -> None:
        """Store an event in all indices"""
        # By lineage UUID (for tracking event history)
        cls._events_by_lineage[event.lineage_uuid].append(event)
        
        # By UUID (stores the most recent version of an event)
        cls._events_by_uuid[event.uuid] = event
        
        # By timestamp
        cls._events_by_timestamp[event.timestamp].append(event)

        # Handle parent-child relationships
        if event.parent_event:
            parent_uuid = event.parent_event
            parent_event = cls.get_event_by_uuid(parent_uuid)
            if parent_event and parent_event.uuid not in event.children_events:
                parent_event.add_child_event(event)

        # By type
        cls._events_by_type[event.event_type].append(event)
        
        # By phase
        cls._events_by_phase[event.phase].append(event)
        
        # By source
        cls._events_by_source[event.source_entity_uuid].append(event)
        
        # By target (if applicable)
        if event.target_entity_uuid:
            cls._events_by_target[event.target_entity_uuid].append(event)
        
        # Add to chronological list and sort
        cls._all_events.append(event)
        cls._all_events.sort(key=lambda e: e.timestamp)
    
    @classmethod
    def _get_handlers_for_event(cls, event: Event) -> List[EventHandler]:
        """Get all listeners for a specific event"""

        trigger_condition = event.get_trigger()
        if not trigger_condition.is_simple():
            simple_trigger = trigger_condition.get_simple_trigger()
            simple_handlers = cls._event_handlers_by_simple_trigger.get(simple_trigger, [])
            complex_handlers = cls._event_handlers_by_trigger.get(trigger_condition, [])
            # print(f"Simple handlers: {simple_handlers}")
            # print(f"Complex handlers: {complex_handlers}")
            all_handlers = simple_handlers + complex_handlers
        else:
             all_handlers = cls._event_handlers_by_trigger.get(trigger_condition, [])
        
        
        return all_handlers
    
    @classmethod
    def add_event_handler(cls, event_handler: EventHandler) -> None:
        """
        Add a handler for events of a specific type and phase
        
        Args:
            event_type: Type of event to listen for (or None for all types)
            event_phase: Phase of event to listen for (or None for all phases)
            source_entity_uuid: UUID of the entity that owns this listener
            listener: The listener function to call when an event matches
        """
        for trigger in event_handler.trigger_conditions:
            if trigger.is_simple():
                cls._event_handlers_by_simple_trigger[trigger.get_simple_trigger()].append(event_handler)
            cls._event_handlers_by_trigger[trigger].append(event_handler)
        cls._event_handlers[event_handler.uuid] = event_handler
        cls._event_handlers_by_source_entity_uuid[event_handler.source_entity_uuid].append(event_handler)
    
    @classmethod
    def remove_event_handler(cls, event_handler: EventHandler) -> None:
        """Remove a handler"""
        for trigger in event_handler.trigger_conditions:
            if trigger.is_simple():
                cls._event_handlers_by_simple_trigger[trigger.get_simple_trigger()].remove(event_handler)
            cls._event_handlers_by_trigger[trigger].remove(event_handler)
            cls._event_handlers.pop(event_handler.uuid)
        cls._event_handlers_by_source_entity_uuid[event_handler.source_entity_uuid].remove(event_handler)

    @classmethod
    def remove_event_handlers_by_uuid(cls, uuid: UUID) -> None:
        """Remove a handler by uuid"""
        event_handler = cls._event_handlers.get(uuid)
        if event_handler:
            cls.remove_event_handler(event_handler)
    

    @classmethod
    def get_events_chronological(cls, start_time: Optional[datetime] = None, 
                               end_time: Optional[datetime] = None) -> List[Event]:
        """Get events in chronological order, optionally within a time range"""
        if start_time is None and end_time is None:
            return cls._all_events
            
        filtered_events = cls._all_events
        
        if start_time:
            filtered_events = [e for e in filtered_events if e.timestamp >= start_time]
            
        if end_time:
            filtered_events = [e for e in filtered_events if e.timestamp <= end_time]
            
        return filtered_events
    
    @classmethod
    def get_latest_events(cls, count: int) -> List[Event]:
        """Get the most recent events"""
        return cls._all_events[-count:] if len(cls._all_events) >= count else cls._all_events
    
    @classmethod
    def get_event_history(cls, event_uuid: UUID) -> List[Event]:
        """Get the complete history of an event by its lineage UUID"""
        event = cls._events_by_uuid.get(event_uuid)
        if not event:
            return []
        
        # Return all events with the same lineage UUID
        lineage_uuid = event.lineage_uuid
        return sorted(cls._events_by_lineage.get(lineage_uuid, []), key=lambda e: e.timestamp)
    
    @classmethod
    def get_events_by_type(cls, event_type: EventType) -> List[Event]:
        """Get all events of a specific type"""
        return cls._events_by_type.get(event_type, [])
    
    @classmethod
    def get_events_by_phase(cls, event_phase: EventPhase) -> List[Event]:
        """Get all events in a specific phase"""
        return cls._events_by_phase.get(event_phase, [])
    
    @classmethod
    def get_events_by_source(cls, source_entity_uuid: UUID) -> List[Event]:
        """Get all events from a specific source entity"""
        return cls._events_by_source.get(source_entity_uuid, [])
    
    @classmethod
    def get_events_by_target(cls, target_entity_uuid: UUID) -> List[Event]:
        """Get all events targeting a specific entity"""
        return cls._events_by_target.get(target_entity_uuid, [])
    
    @classmethod
    def get_events_by_timestamp(cls, timestamp: datetime) -> List[Event]:
        """Get all events with a specific timestamp"""
        return cls._events_by_timestamp.get(timestamp, [])
    


class D20Event(Event):
    """A d20 event"""
    name: str = Field(default="D20",description="A d20 event")
    dc: Optional[Union[int, ModifiableValue]] = Field(default=None,description="The dc of the d20")
    bonus: Optional[Union[int, ModifiableValue]] = Field(default=0,description="The bonus to the d20")
    dice: Optional[Dice] = Field(default=None,description="The dice used to roll the d20")
    dice_roll: Optional[DiceRoll] = Field(default=None,description="The result of the dice roll")
    result: Optional[bool] = Field(default=None,description="Whether the d20 event was successful")

    def get_dc(self) -> Optional[int]:
        """Get the dc of the d20 event"""
        if self.dc is None:
            return None
        if isinstance(self.dc, ModifiableValue):
            return self.dc.normalized_score
        return self.dc
    
class SavingThrowEvent(D20Event):
    """An event that represents a saving throw"""
    name: str = Field(default="Saving Throw",description="A saving throw event")
    ability_name: AbilityName = Field(description="The ability that is being saved against")
    event_type: EventType = Field(default=EventType.SAVING_THROW,description="The type of event")

class SkillCheckEvent(D20Event):
    """An event that represents a skill check"""
    name: str = Field(default="Skill Check",description="A skill check event")
    skill_name: SkillName = Field(description="The skill that is being checked")
    event_type: EventType = Field(default=EventType.SKILL_CHECK,description="The type of event")

class RangeType(str, Enum):
    REACH = "Reach"
    RANGE = "Range"

class Range(BaseModel):
    type: RangeType = Field(
        description="The type of range (Reach or Range)"
    )
    normal: int = Field(
        description="Normal range in feet"
    )
    long: Optional[int] = Field(
        default=None,
        description="Long range in feet, only applicable for ranged weapons"
    )

    def __str__(self):
        if self.type == RangeType.REACH:
            return f"{self.normal} ft."
        elif self.type == RangeType.RANGE:
            return f"{self.normal}/{self.long} ft." if self.long else f"{self.normal} ft."
        
class Damage(BaseObject):
    name: str = Field(default="Damage", description="Name of the damage")
    damage_dice: Literal[4,6,8,10,12,20] = Field(
        description="Number of sides on the damage dice (e.g., 6 for d6)"
    )
    dice_numbers: int = Field(
        description="Number of dice to roll for damage (e.g., 2 for 2d6)"
    )
    damage_bonus: Optional[ModifiableValue] = Field(
        default=None,
        description="Fixed bonus to damage rolls"
    )
    damage_type: DamageType = Field(
        description="Type of damage dealt by the weapon"
    )
    
    def get_dice(self, attack_outcome: AttackOutcome) -> Dice:
        return Dice(count=self.dice_numbers, value=self.damage_dice, bonus=self.damage_bonus, roll_type=RollType.DAMAGE, attack_outcome=attack_outcome)

