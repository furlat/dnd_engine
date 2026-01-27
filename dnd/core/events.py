""" This is the most "designed" and hardcoded part of the codebase it contains most of the dynamics possible in DND 5e and will be constantly expanded
it introduces and Event qeueue which is the source of ground truth information flow between entities, it allows each action to broadcast its intent and results
 and allow it to be intercepted by reactions and or trigger cascade effects at any point in the game"""

__all__ = [
    # Enums
    "WeaponSlot", "EventType", "SpatialChangeType", "EventPhase", "RangeType",
    # Type literals
    "AbilityName", "SkillName",
    # Core event classes
    "Event", "Trigger", "EventHandler", "EventQueue",
    # D20 events
    "D20Event", "SavingThrowEvent", "SkillCheckEvent",
    # Spatial events
    "SpatialChangeEvent",
    # Combat events
    "DamageRolledEvent", "TakeDamageEvent",
    # Combat data
    "Range", "Damage",
    # Encounter/Turn events
    "EncounterEvent", "EncounterStartEvent", "EncounterEndEvent",
    "RoundEvent", "RoundStartEvent", "RoundEndEvent",
    "TurnEvent", "TurnStartEvent", "TurnEndEvent",
    # Death/Unconscious events
    "DeathEvent", "UnconsciousEvent",
]

from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal as TypeLiteral, Union, List, Optional, Dict, Self, Literal, TypeVar, Protocol, runtime_checkable, Tuple
from dnd.core.values import ModifiableValue

# Import combat log utilities for generate_combat_log methods and combat_log field
from dnd.core.combat_log import (
    CombatLogEntry,
    CombatLogEntryType, ModifierBreakdown, DiceRollDisplay,
    SavingThrowLogData, SkillCheckLogData, format_d20_roll_line
)
from dnd.core.modifiers import DamageType
from uuid import UUID, uuid4
from dnd.core.dice import Dice, DiceRoll, AttackOutcome, RollType
from datetime import datetime
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
    MELEE_MAIN = "MELEE_MAIN"
    MELEE_OFF = "MELEE_OFF"
    RANGED_MAIN = "RANGED_MAIN"
    RANGED_OFF = "RANGED_OFF"

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
    DAMAGE_ROLLED = "damage_rolled"  # After damage dice rolled, before applied

    # Combat events
    ENEMY_SPOTTED = "enemy_spotted"
    ENEMY_KILLED = "enemy_killed"
    ENEMY_ENGAGED = "enemy_engaged"

    # Spatial events (for GridMap subscriptions)
    SPATIAL_ENTITY_ENTERED = "spatial_entity_entered"  # Entity moved into a cell
    SPATIAL_ENTITY_LEFT = "spatial_entity_left"        # Entity left a cell
    SPATIAL_TILE_CHANGED = "spatial_tile_changed"      # Tile properties changed

    # Encounter/Turn events
    ENCOUNTER_START = "encounter_start"
    ENCOUNTER_END = "encounter_end"
    ROUND_START = "round_start"
    ROUND_END = "round_end"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    DEATH = "death"
    UNCONSCIOUS = "unconscious"  # Entity dropped to 0 HP (before death determination)


class SpatialChangeType(str, Enum):
    """Types of spatial changes that can occur."""
    ENTITY_ENTERED = "entity_entered"
    ENTITY_LEFT = "entity_left"
    TILE_CHANGED = "tile_changed"
    TILE_CREATED = "tile_created"
    TILE_REMOVED = "tile_removed"


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

    # Entity names (populated by actions at creation/execution time for combat log generation)
    source_entity_name: Optional[str] = Field(default=None, description="Name of the source entity")
    target_entity_name: Optional[str] = Field(default=None, description="Name of the target entity")
    
    
    # Flag to indicate if event was modified by reactions
    modified: bool = Field(default=False,description="Flag to indicate if event was modified by reactions")
    
    # Flag to indicate if event should be canceled
    canceled: bool = Field(default=False,description="Flag to indicate if event should be canceled")
    parent_event: Optional[UUID] = Field(default=None,description="The parent event of the current event")
    status_message: Optional[str] = Field(default=None,description="A status message for the event")
    
    # Track children events differently
    lineage_children_events: List[UUID] = Field(default_factory=list,description="All children events that happened throughout this event's lifetime")
    children_events: List[UUID] = Field(default_factory=list,description="Children events that happened during the current phase")

    # Auto-generated combat log entry (populated at COMPLETION phase)
    # Excluded from serialization - generated on demand via generate_combat_log()
    combat_log: Optional[CombatLogEntry] = Field(default=None, exclude=True, description="Auto-generated combat log entry")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Generate a combat log entry for this event.

        Default implementation returns None. Subclasses that want combat log
        generation should override this method.

        Returns:
            CombatLogEntry if this event type supports combat logging, None otherwise.
        """
        return None

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

        # Auto-generate combat log at COMPLETION phase
        if new_phase == EventPhase.COMPLETION:
            try:
                # Update self with phase_updates first so generate_combat_log has access to final state
                temp_event = self.model_copy(update=phase_updates)
                combat_log = temp_event.generate_combat_log()
                if combat_log is not None:
                    phase_updates['combat_log'] = combat_log
            except Exception:
                pass  # Don't break event flow if log generation fails

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

    # Passive event callbacks (for monitoring, logging, websocket broadcast)
    # These are called for ALL events after storage, cannot modify events
    _on_event_callbacks: List[Callable[['Event'], None]] = []

    @classmethod
    def add_on_event_callback(cls, callback: Callable[['Event'], None]) -> None:
        """Add a callback that fires for every event after storage.

        Unlike EventHandlers, these callbacks:
        - Fire for ALL events regardless of phase
        - Cannot modify or cancel events
        - Are for passive monitoring (logging, websocket broadcast, etc.)
        """
        cls._on_event_callbacks.append(callback)

    @classmethod
    def remove_on_event_callback(cls, callback: Callable[['Event'], None]) -> None:
        """Remove an event callback."""
        if callback in cls._on_event_callbacks:
            cls._on_event_callbacks.remove(callback)
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
            # reaction_event = handler.get_declaration_event(current_event)
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

        # Notify passive callbacks (for monitoring/logging)
        for callback in cls._on_event_callbacks:
            try:
                callback(event)
            except Exception:
                pass  # Don't let callback errors affect event processing
    
    @classmethod
    def _get_handlers_for_event(cls, event: Event) -> List[EventHandler]:
        """Get all listeners for a specific event"""

        trigger_condition = event.get_trigger()
        if not trigger_condition.is_simple():
            simple_trigger = trigger_condition.get_simple_trigger()
            simple_handlers = cls._event_handlers_by_simple_trigger.get(simple_trigger, [])
            complex_handlers = cls._event_handlers_by_trigger.get(trigger_condition, [])
   
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
    def reset(cls) -> None:
        """Clear all events and handlers. Call when starting a new game."""
        # Clear events
        cls._all_events.clear()
        cls._events_by_uuid.clear()
        cls._events_by_type.clear()
        cls._events_by_phase.clear()
        cls._events_by_source.clear()
        cls._events_by_target.clear()
        cls._events_by_lineage.clear()
        cls._events_by_timestamp.clear()
        # Clear handlers
        cls._event_handlers.clear()
        cls._event_handlers_by_trigger.clear()
        cls._event_handlers_by_simple_trigger.clear()
        cls._event_handlers_by_source_entity_uuid.clear()
    

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

    @classmethod
    def is_first_at_phase(cls, event: Event) -> bool:
        """Check if this event is the first of its lineage at its current phase.

        Useful for handlers that should only trigger once per logical action,
        even if the action uses multiple post() calls at the same phase.

        Returns:
            True if no other events with the same lineage_uuid exist at this phase
            (considering only events registered before this one).
        """
        history = cls._events_by_lineage.get(event.lineage_uuid, [])
        for e in history:
            if e.uuid == event.uuid:
                continue  # Skip self
            if e.phase == event.phase and e.timestamp < event.timestamp:
                return False  # Found an earlier event at same phase
        return True
    


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

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for this saving throw event.

        Uses self.* fields only - no external lookups. Entity names must be
        populated when the event is created.
        """
        # Use entity names from self - no external lookups
        target_name = self.target_entity_name or "Unknown"
        source_name = self.source_entity_name or "Unknown"

        # Get DC
        dc = self.get_dc() or 0

        # Build dice roll display
        roll = DiceRollDisplay(
            dice_str="d20",
            results=[],
            bonus=0,
            total=0
        )

        if self.dice_roll:
            results = self.dice_roll.results
            if isinstance(results, list):
                roll.results = list(results)
                roll.all_d20_rolls = list(results)
                roll.d20_used = results[0] if results else 0

                # Check for advantage/disadvantage
                adv_status = getattr(self.dice_roll, 'advantage_status', None)
                if adv_status:
                    adv_value = adv_status.value.lower() if hasattr(adv_status, 'value') else str(adv_status).lower()
                    roll.advantage_status = adv_value
                    if len(results) >= 2:
                        if adv_value == "advantage":
                            roll.d20_used = max(results)
                        elif adv_value == "disadvantage":
                            roll.d20_used = min(results)
            elif isinstance(results, int):
                roll.results = [results]
                roll.d20_used = results

            roll.bonus = getattr(self.dice_roll, 'bonus', 0)
            roll.total = self.dice_roll.total

        # Build bonus breakdown
        bonus_breakdown: List[ModifierBreakdown] = []
        if self.bonus and isinstance(self.bonus, ModifiableValue) and hasattr(self.bonus, 'get_breakdown'):
            for mod in self.bonus.get_breakdown():
                bonus_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

        # Determine success
        success = self.result if self.result is not None else (roll.total >= dc if dc > 0 else None)

        # Build ability name display
        ability_display = self.ability_name.upper()[:3]  # STR, DEX, etc.

        # Build summary
        result_str = "succeeds" if success else "fails"
        summary = f"{target_name} {result_str} {ability_display} save (DC {dc})"

        # Build detail line
        detail_lines = []
        detail_line = format_d20_roll_line(roll, bonus_breakdown, dc, success or False, "Save")
        detail_lines.append(detail_line)

        # Build structured data
        data = SavingThrowLogData(
            entity_name=target_name,
            entity_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else str(self.source_entity_uuid),
            ability=self.ability_name,
            dc=dc,
            roll=roll,
            bonus_breakdown=bonus_breakdown,
            success=success or False,
            source_name=source_name if source_name != target_name else None
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.SAVING_THROW,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else None,
            summary=summary,
            detail_lines=detail_lines,
            data=data.model_dump(),
            success=success
        )


class SkillCheckEvent(D20Event):
    """An event that represents a skill check"""
    name: str = Field(default="Skill Check",description="A skill check event")
    skill_name: SkillName = Field(description="The skill that is being checked")
    event_type: EventType = Field(default=EventType.SKILL_CHECK,description="The type of event")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for this skill check event.

        Uses self.* fields only - no external lookups. Entity names must be
        populated when the event is created.
        """
        # Use entity name from self - no external lookups
        source_name = self.source_entity_name or "Unknown"

        # Get DC (may not exist for opposed checks)
        dc = self.get_dc()

        # Build dice roll display
        roll = DiceRollDisplay(
            dice_str="d20",
            results=[],
            bonus=0,
            total=0
        )

        if self.dice_roll:
            results = self.dice_roll.results
            if isinstance(results, list):
                roll.results = list(results)
                roll.all_d20_rolls = list(results)
                roll.d20_used = results[0] if results else 0

                # Check for advantage/disadvantage
                adv_status = getattr(self.dice_roll, 'advantage_status', None)
                if adv_status:
                    adv_value = adv_status.value.lower() if hasattr(adv_status, 'value') else str(adv_status).lower()
                    roll.advantage_status = adv_value
                    if len(results) >= 2:
                        if adv_value == "advantage":
                            roll.d20_used = max(results)
                        elif adv_value == "disadvantage":
                            roll.d20_used = min(results)
            elif isinstance(results, int):
                roll.results = [results]
                roll.d20_used = results

            roll.bonus = getattr(self.dice_roll, 'bonus', 0)
            roll.total = self.dice_roll.total

        # Build bonus breakdown
        bonus_breakdown: List[ModifierBreakdown] = []
        if self.bonus and isinstance(self.bonus, ModifiableValue) and hasattr(self.bonus, 'get_breakdown'):
            for mod in self.bonus.get_breakdown():
                bonus_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

        # Determine success
        success = self.result if self.result is not None else (roll.total >= dc if dc is not None and dc > 0 else None)

        # Build skill name display (capitalize first letter)
        skill_display = self.skill_name.replace('_', ' ').title()

        # Build summary
        if dc is not None:
            result_str = "succeeds" if success else "fails"
            summary = f"{source_name} {result_str} {skill_display} check (DC {dc})"
        else:
            summary = f"{source_name} rolls {skill_display} check: {roll.total}"

        # Build detail line
        detail_lines = []
        if dc is not None:
            detail_line = format_d20_roll_line(roll, bonus_breakdown, dc, success or False, skill_display)
        else:
            # No DC - just show the roll
            bonus_str = f"+{roll.bonus}" if roll.bonus >= 0 else str(roll.bonus)
            if bonus_breakdown:
                breakdown_str = " [" + ", ".join(
                    f"{m.name} {'+' if m.value >= 0 else ''}{m.value}" for m in bonus_breakdown
                ) + "]"
            else:
                breakdown_str = ""
            d20_val = roll.d20_used if roll.d20_used is not None else (roll.results[0] if roll.results else "?")
            detail_line = f"{skill_display}: d20({d20_val}) {bonus_str}{breakdown_str} = {roll.total}"
        detail_lines.append(detail_line)

        # Build structured data
        data = SkillCheckLogData(
            entity_name=source_name,
            entity_uuid=str(self.source_entity_uuid),
            skill=self.skill_name,
            dc=dc,
            roll=roll,
            bonus_breakdown=bonus_breakdown,
            success=success
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.SKILL_CHECK,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            summary=summary,
            detail_lines=detail_lines,
            data=data.model_dump(),
            success=success
        )


class SpatialChangeEvent(Event):
    """
    Event fired when something changes at a grid position.

    Used for:
    - Entity sense updates (entities subscribe to visible cells)
    - UI/renderer updates (websocket broadcasts these events)

    Entities can subscribe to cells via EventHandler with triggers matching:
    - event_type: SPATIAL_ENTITY_ENTERED, SPATIAL_ENTITY_LEFT, or SPATIAL_TILE_CHANGED
    - event_phase: COMPLETION (spatial changes are instantaneous)
    """
    name: str = Field(default="Spatial Change", description="A spatial change event")
    event_type: EventType = Field(default=EventType.SPATIAL_ENTITY_ENTERED, description="Type of spatial change")
    change_type: SpatialChangeType = Field(description="Specific type of spatial change")
    position: Tuple[int, int] = Field(description="Grid position where change occurred")
    entity_uuid: Optional[UUID] = Field(default=None, description="UUID of entity involved (if any)")
    old_position: Optional[Tuple[int, int]] = Field(default=None, description="Previous position (for movement)")
    tile_walkable: Optional[bool] = Field(default=None, description="New walkable state (for tile changes)")
    tile_visible: Optional[bool] = Field(default=None, description="New visible state (for tile changes)")

    @classmethod
    def entity_entered(cls, position: Tuple[int, int], entity_uuid: UUID,
                       old_position: Optional[Tuple[int, int]] = None,
                       source_entity_uuid: Optional[UUID] = None) -> 'SpatialChangeEvent':
        """Create an event for an entity entering a cell."""
        return cls(
            source_entity_uuid=source_entity_uuid or entity_uuid,
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            change_type=SpatialChangeType.ENTITY_ENTERED,
            position=position,
            entity_uuid=entity_uuid,
            old_position=old_position,
            phase=EventPhase.COMPLETION
        )

    @classmethod
    def entity_left(cls, position: Tuple[int, int], entity_uuid: UUID,
                    new_position: Optional[Tuple[int, int]] = None,
                    source_entity_uuid: Optional[UUID] = None) -> 'SpatialChangeEvent':
        """Create an event for an entity leaving a cell."""
        return cls(
            source_entity_uuid=source_entity_uuid or entity_uuid,
            event_type=EventType.SPATIAL_ENTITY_LEFT,
            change_type=SpatialChangeType.ENTITY_LEFT,
            position=position,
            entity_uuid=entity_uuid,
            old_position=new_position,  # Store new position in old_position field for reference
            phase=EventPhase.COMPLETION
        )

    @classmethod
    def tile_changed(cls, position: Tuple[int, int], walkable: bool, visible: bool,
                     source_entity_uuid: Optional[UUID] = None) -> 'SpatialChangeEvent':
        """Create an event for a tile property change."""
        return cls(
            source_entity_uuid=source_entity_uuid or uuid4(),
            event_type=EventType.SPATIAL_TILE_CHANGED,
            change_type=SpatialChangeType.TILE_CHANGED,
            position=position,
            tile_walkable=walkable,
            tile_visible=visible,
            phase=EventPhase.COMPLETION
        )


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
    
    def get_dice(self, attack_outcome: AttackOutcome, crit_extra_dice: int = 0) -> Dice:
        return Dice(count=self.dice_numbers, value=self.damage_dice, bonus=self.damage_bonus, roll_type=RollType.DAMAGE, attack_outcome=attack_outcome, crit_extra_dice=crit_extra_dice)


# =============================================================================
# Damage Rolled Event (for damage dice manipulation)
# =============================================================================

class DamageRolledEvent(Event):
    """
    Event fired after damage dice are rolled but before damage is applied.

    Handlers create new DiceRoll versions - original rolls are immutable.
    After all handlers run, final_rolls contains the versions to apply.

    This enables:
    - Reroll and substitute (Great Weapon Fighting)
    - Reroll and keep best (Halfling Lucky, Elemental Adept)
    - Partial rerolls (only lightning damage dice)
    - Audit trail (see what changed and why)
    """
    name: str = Field(default="Damage Rolled")
    event_type: EventType = Field(default=EventType.DAMAGE_ROLLED)

    # Attack context (read-only)
    weapon_slot: WeaponSlot = Field(description="The weapon slot used for the attack")
    attack_outcome: AttackOutcome = Field(description="The outcome of the attack (HIT, CRIT, etc.)")
    damages: List[Damage] = Field(description="Damage specifications")

    # IMMUTABLE: Original rolls (never modified)
    original_rolls: List[DiceRoll] = Field(description="Original dice rolls before any modifications")

    # MUTABLE: Current best rolls (handlers replace with new versions)
    # Initialized to copy of original_rolls
    final_rolls: List[DiceRoll] = Field(description="Final dice rolls after handler modifications")

    # AUDIT: History of modifications [(handler_name, roll_index, old_total, new_total, reason), ...]
    roll_modifications: List[Tuple[str, int, int, int, str]] = Field(
        default_factory=list,
        description="Audit trail of roll modifications: (handler_name, roll_index, old_total, new_total, reason)"
    )

    def replace_roll(self, index: int, new_roll: DiceRoll, handler_name: str, reason: str) -> None:
        """Helper for handlers to replace a roll and track the change."""
        old_roll = self.final_rolls[index]
        self.roll_modifications.append((handler_name, index, old_roll.total, new_roll.total, reason))
        self.final_rolls[index] = new_roll


# =============================================================================
# Take Damage Event (for damage tracking and interception)
# =============================================================================

class TakeDamageEvent(Event):
    """
    Event fired when an entity is about to take damage.

    This event enables:
    - Tracking damage taken (e.g., rage maintenance - KeepRage marker)
    - Modifying damage (e.g., resistance, vulnerability, reduction)
    - Canceling damage (e.g., immunity, absorption)
    - Reacting to lethal damage (e.g., Relentless Rage)

    Phases:
    - DECLARATION: Damage is about to be applied
    - EXECUTION: Processing begins
    - EFFECT: Handlers can modify/reduce/cancel damage
    - COMPLETION: Damage has been applied (or canceled)

    Handlers should check `canceled` flag before applying damage.
    If `final_damage` is set, use that instead of `total_damage`.
    """
    name: str = Field(default="Take Damage")
    event_type: EventType = Field(default=EventType.TAKE_DAMAGE)

    # Damage details
    total_damage: int = Field(description="Total damage before any modifications")
    damage_rolls: List[DiceRoll] = Field(default_factory=list, description="Individual damage rolls")
    damages: List['Damage'] = Field(default_factory=list, description="Damage specifications (types)")

    # For handlers that need to modify damage
    final_damage: Optional[int] = Field(
        default=None,
        description="Modified damage after handlers. If None, use total_damage."
    )

    def get_effective_damage(self) -> int:
        """Get the damage amount to apply (final_damage if set, else total_damage)."""
        return self.final_damage if self.final_damage is not None else self.total_damage


# =============================================================================
# Encounter/Turn Events
# =============================================================================

class EncounterEvent(Event):
    """Base event for encounter lifecycle."""
    name: str = Field(default="Encounter Event", description="An encounter lifecycle event")
    encounter_uuid: UUID = Field(description="UUID of the encounter")
    combatant_uuids: List[UUID] = Field(default_factory=list, description="UUIDs of all combatants")


class EncounterStartEvent(EncounterEvent):
    """Fired when an encounter begins."""
    name: str = Field(default="Encounter Start", description="Encounter has started")
    event_type: EventType = Field(default=EventType.ENCOUNTER_START)
    initiative_order: List[UUID] = Field(default_factory=list, description="Combatants sorted by initiative")


class EncounterEndEvent(EncounterEvent):
    """Fired when an encounter ends."""
    name: str = Field(default="Encounter End", description="Encounter has ended")
    event_type: EventType = Field(default=EventType.ENCOUNTER_END)
    reason: Optional[str] = Field(default=None, description="Why the encounter ended")


class RoundEvent(Event):
    """Base event for round lifecycle."""
    name: str = Field(default="Round Event", description="A round lifecycle event")
    encounter_uuid: UUID = Field(description="UUID of the encounter")
    round_number: int = Field(description="Current round number (1-indexed)")


class RoundStartEvent(RoundEvent):
    """Fired at the start of a new round."""
    name: str = Field(default="Round Start", description="A new round has started")
    event_type: EventType = Field(default=EventType.ROUND_START)


class RoundEndEvent(RoundEvent):
    """Fired at the end of a round."""
    name: str = Field(default="Round End", description="The round has ended")
    event_type: EventType = Field(default=EventType.ROUND_END)


class TurnEvent(Event):
    """Base event for turn lifecycle."""
    name: str = Field(default="Turn Event", description="A turn lifecycle event")
    encounter_uuid: UUID = Field(description="UUID of the encounter")
    entity_uuid: UUID = Field(description="UUID of the entity whose turn it is")
    round_number: int = Field(description="Current round number")
    turn_index: int = Field(description="Position in initiative order (0-indexed)")


class TurnStartEvent(TurnEvent):
    """Fired at the start of an entity's turn."""
    name: str = Field(default="Turn Start", description="Entity's turn has started")
    event_type: EventType = Field(default=EventType.TURN_START)
    actions_available: int = Field(default=1, description="Actions available this turn")
    bonus_actions_available: int = Field(default=1, description="Bonus actions available")
    movement_available: int = Field(default=30, description="Movement available in feet")
    reaction_available: int = Field(default=1, description="Reaction available")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for turn start."""
        entity_name = self.source_entity_name or "Unknown"
        return CombatLogEntry(
            entry_type=CombatLogEntryType.TURN_START,
            source_name=entity_name,
            source_uuid=str(self.entity_uuid),
            summary=f"{entity_name}'s turn begins",
            data={
                "entity_name": entity_name,
                "entity_uuid": str(self.entity_uuid),
                "round_number": self.round_number,
                "turn_index": self.turn_index,
            }
        )


class TurnEndEvent(TurnEvent):
    """Fired at the end of an entity's turn."""
    name: str = Field(default="Turn End", description="Entity's turn has ended")
    event_type: EventType = Field(default=EventType.TURN_END)
    actions_used: int = Field(default=0, description="Actions used this turn")
    bonus_actions_used: int = Field(default=0, description="Bonus actions used")
    movement_used: int = Field(default=0, description="Movement used in feet")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for turn end."""
        entity_name = self.source_entity_name or "Unknown"
        return CombatLogEntry(
            entry_type=CombatLogEntryType.TURN_END,
            source_name=entity_name,
            source_uuid=str(self.entity_uuid),
            summary=f"{entity_name}'s turn ends",
            data={
                "entity_name": entity_name,
                "entity_uuid": str(self.entity_uuid),
                "round_number": self.round_number,
                "turn_index": self.turn_index,
            }
        )


class DeathEvent(Event):
    """Fired when an entity dies (HP drops to 0 or below)."""
    name: str = Field(default="Death", description="Entity has died")
    event_type: EventType = Field(default=EventType.DEATH)
    entity_uuid: UUID = Field(description="UUID of the entity that died")
    entity_name: str = Field(default="", description="Name of the entity that died")
    killer_uuid: Optional[UUID] = Field(default=None, description="UUID of entity that dealt killing blow")
    killer_name: str = Field(default="", description="Name of killer if known")
    final_hp: int = Field(default=0, description="Final HP value (typically negative)")
    encounter_uuid: Optional[UUID] = Field(default=None, description="UUID of encounter if in combat")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate combat log entry for death."""
        return CombatLogEntry(
            entry_type=CombatLogEntryType.DEATH,
            source_name=self.entity_name,
            source_uuid=str(self.entity_uuid),
            summary=f"{self.entity_name} has been defeated!",
            detail_lines=[f"{self.entity_name} dropped to {self.final_hp} HP and died."],
            data={"entity_name": self.entity_name, "final_hp": self.final_hp},
            success=True
        )


class UnconsciousEvent(Event):
    """
    Fired when an entity drops to 0 HP (before death determination).

    This event allows handlers to react to becoming unconscious:
    - Rage ending (Barbarian)
    - Concentration checks
    - Other features that trigger on dropping to 0 HP

    Note: This fires AFTER damage is applied, so RelentlessRage (which modifies
    damage at TAKE_DAMAGE EFFECT) has already had its chance to prevent this.
    If RelentlessRage succeeds, HP stays at 1 and this event never fires.
    """
    name: str = Field(default="Unconscious", description="Entity dropped to 0 HP")
    event_type: EventType = Field(default=EventType.UNCONSCIOUS)
    entity_uuid: UUID = Field(description="UUID of the entity that dropped to 0 HP")
    entity_name: str = Field(default="", description="Name of the entity")
    damage_source_uuid: Optional[UUID] = Field(default=None, description="UUID of entity that caused the unconsciousness")
    final_hp: int = Field(default=0, description="HP after damage (typically 0 or negative)")

