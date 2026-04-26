""" This is the most "designed" and hardcoded part of the codebase it contains most of the dynamics possible in DND 5e and will be constantly expanded
it introduces and Event qeueue which is the source of ground truth information flow between entities, it allows each action to broadcast its intent and results
 and allow it to be intercepted by reactions and or trigger cascade effects at any point in the game"""

__all__ = [
    # Enums
    "WeaponSlot", "BodyPart", "RingSlot", "EquipmentSlot",
    "EventType", "SpatialChangeType", "EventPhase", "RangeType",
    # Type literals
    "AbilityName", "SkillName",
    # Core event classes
    "Event", "Trigger", "BaseHandler", "EventHandler", "SpatialHandler", "EventQueue",
    # Sensory events
    "SensoryUpdateReason", "SensoryUpdateEvent",
    # D20 events (legacy)
    "D20Event", "SavingThrowEvent", "SkillCheckEvent",
    # Unified dice roll events
    "DiceRollResultEvent",
    "D20RollResultEvent",
    "AttackD20RollResultEvent",
    "SavingThrowD20RollResultEvent",
    "SkillCheckD20RollResultEvent",
    "DamageRollResultEvent",
    # Spatial events
    "SensesUpdateHint", "SpatialChangeEvent", "ForcedMovementEvent",
    # Combat events
    "DamageRolledEvent", "TakeDamageEvent",  # DamageRolledEvent is DEPRECATED
    # Combat data
    "Range", "Damage",
    # Encounter/Turn events
    "EncounterEvent", "EncounterStartEvent", "EncounterEndEvent",
    "RoundEvent", "RoundStartEvent", "RoundEndEvent",
    "TurnEvent", "TurnStartEvent", "TurnEndEvent",
    # Death event
    "DeathEvent",
]

from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal as TypeLiteral, Union, List, Optional, Dict, Self, Literal, TypeVar, Protocol, runtime_checkable, Tuple, Any, Set
from dnd.core.values import ModifiableValue

# Import combat log utilities for generate_combat_log methods and combat_log field
from dnd.core.combat_log import (
    CombatLogEntry,
    CombatLogEntryType, ModifierBreakdown, DiceRollDisplay,
    SavingThrowLogData, SkillCheckLogData, HealLogData,
    md_color, md_d20_roll, md_breakdown
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

class BodyPart(str, Enum):
    HEAD = "Head"
    BODY = "Body"
    HANDS = "Hands"
    LEGS = "Legs"
    FEET = "Feet"
    AMULET = "Amulet"
    RING = "Ring"
    CLOAK = "Cloak"

class RingSlot(str, Enum):
    LEFT = "Left Ring"
    RIGHT = "Right Ring"

EquipmentSlot = Union[WeaponSlot, BodyPart, RingSlot]

class EventType(str, Enum):
    # Core events
    BASE_ACTION = "base_action"
    ATTACK = "attack"
    MOVEMENT = "movement"
    STEP_MOVEMENT = "step_movement"  # Single cell transition within a path - triggers OA
    FORCED_MOVEMENT = "forced_movement"  # Push, pull, teleport by others - does NOT trigger OA
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
    DICE_ROLL_RESULT = "dice_roll_result"  # Base type for unified dice roll events
    D20_ROLL_RESULT = "d20_roll_result"    # D20 base (Lucky triggers on this)
    ATTACK_D20_ROLL_RESULT = "attack_d20_roll"  # Attack rolls
    SAVE_D20_ROLL_RESULT = "save_d20_roll"      # Saving throws
    CHECK_D20_ROLL_RESULT = "check_d20_roll"    # Skill checks
    DAMAGE_ROLL_RESULT = "damage_roll_result"   # After damage dice rolled, before applied
    HEAL_ROLL_RESULT = "heal_roll_result"       # After healing dice rolled, before applied
    DAMAGE_ROLLED = "damage_rolled"  # DEPRECATED: Use DAMAGE_ROLL_RESULT instead

    # Combat events
    ENEMY_SPOTTED = "enemy_spotted"
    ENEMY_KILLED = "enemy_killed"
    ENEMY_ENGAGED = "enemy_engaged"

    # Spatial events (for GridMap subscriptions)
    SPATIAL_ENTITY_ENTERED = "spatial_entity_entered"  # Entity moved into a cell
    SPATIAL_ENTITY_LEFT = "spatial_entity_left"        # Entity left a cell
    SPATIAL_TILE_CHANGED = "spatial_tile_changed"      # Tile properties changed
    SPATIAL_OBJECT_PLACED = "spatial_object_placed"    # Object placed on grid
    SPATIAL_OBJECT_REMOVED = "spatial_object_removed"  # Object removed from grid
    SPATIAL_PERCEIVABILITY_CHANGED = "spatial_perceivability_changed"  # Entity's perceivability changed (hidden/invisible)
    SPATIAL_LIGHT_CHANGED = "spatial_light_changed"  # Tile's resolved light level changed
    SPATIAL_OBJECT_CHANGED = "spatial_object_changed"  # Object blocking state changed (door open/close)
    MOVEMENT_COLLISION = "movement_collision"  # Entity bumped into imperceivable blocker
    SENSORY_UPDATE = "sensory_update"  # Observer-specific visibility/fog/entity/object delta

    # Encounter/Turn events
    ENCOUNTER_START = "encounter_start"
    ENCOUNTER_END = "encounter_end"
    ROUND_START = "round_start"
    ROUND_END = "round_end"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    DEATH = "death"


class SpatialChangeType(str, Enum):
    """Types of spatial changes that can occur."""
    ENTITY_ENTERED = "entity_entered"
    ENTITY_LEFT = "entity_left"
    TILE_CHANGED = "tile_changed"
    TILE_CREATED = "tile_created"
    TILE_REMOVED = "tile_removed"
    OBJECT_PLACED = "object_placed"
    OBJECT_REMOVED = "object_removed"
    PERCEIVABILITY_CHANGED = "perceivability_changed"
    LIGHT_CHANGED = "light_changed"
    OBJECT_CHANGED = "object_changed"
    MOVEMENT_COLLISION = "movement_collision"


class SensoryUpdateReason(str, Enum):
    """Why an observer's sensory state changed."""
    SPATIAL = "spatial"
    SELF_MOVEMENT = "self_movement"
    LIGHT = "light"
    PERCEIVABILITY = "perceivability"
    DEATH = "death"
    CONDITION = "condition"
    UNKNOWN = "unknown"


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

    # Phase repetition flags (for events like Attack that fire EFFECT twice)
    is_first: bool = Field(default=True, description="True if this is the first event of this phase in this lineage")
    is_last: bool = Field(default=True, description="True if this is the last event of this phase in this lineage")
    
    # Track children events differently
    lineage_children_events: List[UUID] = Field(default_factory=list,description="All children events that happened throughout this event's lifetime")
    children_events: List[UUID] = Field(default_factory=list,description="Children events that happened during the current phase")

    # Stable hierarchy fields — populated automatically at COMPLETION phase
    # by resolving stale phase-specific UUIDs through EventQueue lookups.
    # Never set by callers.
    parent_lineage: Optional[UUID] = Field(default=None, description="Parent's lineage_uuid (stable across phases)")
    children_lineages: List[UUID] = Field(default_factory=list, description="Lineage UUIDs of all children (stable, deduped)")

    # Auto-generated combat log entry (populated at COMPLETION phase)
    # Excluded from serialization - generated on demand via generate_combat_log()
    combat_log: Optional[CombatLogEntry] = Field(default=None, exclude=True, description="Auto-generated combat log entry")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Generate a combat log entry for this event.

        Default implementation returns self.combat_log (pre-set if any).
        Subclasses that want combat log generation should override this method.

        Returns:
            CombatLogEntry if this event type supports combat logging, None otherwise.
        """
        return self.combat_log

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Grid positions spatially relevant to this event.

        Returns only positions carried as fields. Entity-UUID-derived
        positions are added by the perceiver computer (which has GridMap access).
        Override in subclasses with explicit position fields.
        """
        return set()

    def get_trigger(self) -> 'Trigger':
        """ get the trigger for the event """
        return Trigger(event_type=self.event_type, event_phase=self.phase,event_source_entity_uuid=self.source_entity_uuid,event_target_entity_uuid=self.target_entity_uuid)
    
    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
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
        
        # Reset is_first/is_last to defaults unless explicitly overridden
        if 'is_first' not in phase_updates:
            phase_updates['is_first'] = True
        if 'is_last' not in phase_updates:
            phase_updates['is_last'] = True

        if new_phase == EventPhase.COMPLETION:
            EventQueue.run_pre_completion_callbacks(self)

            # COMPLETION: carry forward ALL children and resolve stable lineage references
            all_children = list(dict.fromkeys(self.lineage_children_events + self.children_events))
            phase_updates['lineage_children_events'] = all_children
            phase_updates['children_events'] = all_children

            # Resolve parent_lineage from stale parent_event UUID
            if self.parent_event:
                parent = EventQueue.get_event_by_uuid(self.parent_event)
                if parent:
                    phase_updates['parent_lineage'] = parent.lineage_uuid

            # Build children_lineages by dereferencing child UUIDs → lineage UUIDs
            child_lineages: List[UUID] = []
            seen_lineages: Set[UUID] = set()
            for child_uuid in all_children:
                child = EventQueue.get_event_by_uuid(child_uuid)
                if child and child.lineage_uuid not in seen_lineages:
                    child_lineages.append(child.lineage_uuid)
                    seen_lineages.add(child.lineage_uuid)
            phase_updates['children_lineages'] = child_lineages
        else:
            # Non-COMPLETION: existing behavior unchanged
            phase_updates['lineage_children_events'] = self.lineage_children_events + self.children_events
            phase_updates['children_events'] = []

        # Auto-generate combat log at COMPLETION phase
        if new_phase == EventPhase.COMPLETION:
            try:
                # Update self with phase_updates first so generate_combat_log has access to final state
                temp_event = self.model_copy(update=phase_updates)
                combat_log = temp_event.generate_combat_log()
                if combat_log is not None:
                    # Stamp perceivers using GridMap subscribers (O(1) per position)
                    if EventQueue._perceiver_computer:
                        combat_log.perceiver_uuids = EventQueue._perceiver_computer(temp_event)

                    # CENTRALIZED: Collect children here, not in each generate_combat_log()
                    child_logs = temp_event._collect_child_combat_logs()
                    if child_logs:
                        combat_log.sub_entries = child_logs
                        # Union child perceivers into parent — if ANY sub-event
                        # was perceivable, the parent is too
                        for child_log in child_logs:
                            combat_log.perceiver_uuids |= child_log.perceiver_uuids
                            combat_log.revealed_entity_uuids |= child_log.revealed_entity_uuids

                    # Compute revealed entities from condition removal logs in tree
                    if EventQueue._revealed_computer:
                        combat_log.revealed_entity_uuids |= EventQueue._revealed_computer(temp_event, child_logs or [])

                    phase_updates['combat_log'] = combat_log

                    # Auto-add top-level events via callback
                    if self.parent_event is None and EventQueue._combat_log_callback:
                        # Create temp event with updated combat_log for callback
                        final_event = self.model_copy(update=phase_updates)
                        EventQueue._combat_log_callback(final_event)
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
        """Get all children events of the current event.

        Prefers stable children_lineages (latest event per child lineage) when
        available, falls back to children_events UUID lookup.
        """
        if self.children_lineages:
            result: List[Event] = []
            for lineage_id in self.children_lineages:
                lineage_events = EventQueue._events_by_lineage.get(lineage_id, [])
                if lineage_events:
                    result.append(lineage_events[-1])  # Latest version in lineage
            return result
        resolved = [EventQueue.get_event_by_uuid(child_event) for child_event in self.children_events]
        return [out for out in resolved if out is not None]

    def get_parent_event(self) -> Optional['Event']:
        """Get the parent event of the current event.

        Prefers stable parent_lineage (latest event in parent's lineage) when
        available, falls back to parent_event UUID lookup.
        """
        if self.parent_lineage:
            events = EventQueue._events_by_lineage.get(self.parent_lineage, [])
            if events:
                return events[-1]  # Latest version in parent lineage
        if self.parent_event:
            return EventQueue.get_event_by_uuid(self.parent_event)
        return None

    def _collect_child_combat_logs(self) -> List['CombatLogEntry']:
        """Collect combat logs from direct children (recursive via sub_entries).

        Returns a list of CombatLogEntry objects from child events.
        Each child's combat_log already has ITS children in sub_entries
        (because this method runs when each child completes).

        Prefers children_lineages for direct lineage-based lookup, falling back
        to lineage_children_events with de-duplication by lineage_uuid.
        """
        child_logs: List[CombatLogEntry] = []

        if self.children_lineages:
            # Direct lookup: each entry is already a unique lineage UUID
            for lineage_id in self.children_lineages:
                events = EventQueue._events_by_lineage.get(lineage_id, [])
                # Walk backwards to find the COMPLETION event with combat_log
                for ev in reversed(events):
                    if ev.combat_log:
                        child_logs.append(ev.combat_log)
                        break
        else:
            # Fallback: de-duplicate by lineage_uuid
            seen_lineages: Set[UUID] = set()
            for child_uuid in self.lineage_children_events:
                child = EventQueue.get_event_by_uuid(child_uuid)
                if child and child.combat_log and child.lineage_uuid not in seen_lineages:
                    child_logs.append(child.combat_log)
                    seen_lineages.add(child.lineage_uuid)
        return child_logs

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

class BaseHandler(BaseObject):
    """Base class for all handlers (EventHandler and SpatialHandler).

    Provides common fields and invocation logic.
    """
    name: str = Field(default="BaseHandler", description="The name of the handler")
    event_processor: EventProcessor = Field(exclude=True, description="The event processor to handle the event")
    enabled: bool = Field(default=True, description="Whether this handler is active. Disabled handlers are skipped during event dispatch.")
    player_toggleable: bool = Field(default=False, description="Whether the player can toggle this handler on/off. Only True for reactions and optional features like Divine Smite.")

    def __call__(self, event: Event, source_entity_uuid: Optional[UUID] = None) -> Optional[Event]:
        """Execute the event processor."""
        if not self.enabled:
            return None
        if source_entity_uuid is None:
            source_entity_uuid = self.source_entity_uuid
        return self.event_processor(event, source_entity_uuid)

    def get_declaration_event(self, parent_event: Optional[Event] = None) -> Event:
        """Get the declaration event for this handler."""
        return Event(
            name=self.name,
            event_type=EventType.TRIGGER_EVENT,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            status_message=f"Triggering handler {self.name}",
            parent_event=parent_event.uuid if parent_event else None
        )


class EventHandler(BaseHandler):
    """A trigger-based handler that matches events via Trigger conditions.

    Use this for:
    - Non-spatial events (attacks, damage rolls, saves, etc.)
    - Global spatial event listening (OA needs to check ALL movements)
    """
    name: str = Field(default="EventHandler", description="The name of the event handler")
    trigger_conditions: List[Trigger] = Field(default_factory=list, description="The conditions that trigger the event handler")

    def __call__(self, event: Event, source_entity_uuid: Optional[UUID] = None) -> Optional[Event]:
        """Check triggers then execute processor if any match."""
        if not self.enabled:
            return None
        if source_entity_uuid is None:
            source_entity_uuid = self.source_entity_uuid
        # Empty trigger_conditions means this handler always fires when called
        # For spatial handlers with empty triggers, they rely on position index
        if not self.trigger_conditions or any(trigger(event) for trigger in self.trigger_conditions):
            return self.event_processor(event, source_entity_uuid)
        return None

    def remove(self) -> bool:
        """Remove the event handler from the EventQueue."""
        if self.uuid not in EventQueue._event_handlers:
            return False
        EventQueue.remove_event_handler(self)
        entity = BaseObject.get(self.source_entity_uuid)

        if entity is not None and isinstance(entity, EntityWithEventHandlers):
                entity.remove_event_handler_from_dicts(self)

        return True


class SpatialHandler(BaseHandler):
    """A position-indexed handler for spatial events.

    Use this for zone spells and terrain effects that only care about
    specific positions. Provides O(1) lookup at those positions.

    Unlike EventHandler, SpatialHandler:
    - Does NOT use trigger_conditions (position filtering is done by registry)
    - Is stored in a SEPARATE registry (_spatial_handlers)
    - Is found via position index, not trigger matching
    """
    name: str = Field(default="SpatialHandler", description="The name of the spatial handler")
    positions: Set[Tuple[int, int]] = Field(default_factory=set, description="Positions this handler fires at")
    event_type: EventType = Field(default=EventType.SPATIAL_ENTITY_ENTERED, description="The spatial event type")
    event_phase: EventPhase = Field(default=EventPhase.EFFECT, description="The event phase to trigger at")

    # No trigger check - position filtering is done by registry lookup
    def __call__(self, event: Event, source_entity_uuid: Optional[UUID] = None) -> Optional[Event]:
        """Execute the event processor (position already validated by registry)."""
        if not self.enabled:
            return None
        if source_entity_uuid is None:
            source_entity_uuid = self.source_entity_uuid
        return self.event_processor(event, source_entity_uuid)

    def remove(self) -> bool:
        """Remove the spatial handler from the EventQueue."""
        return EventQueue.remove_spatial_handler(self.uuid)

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

    # =========================================================================
    # EventHandler registries (trigger-based)
    # =========================================================================
    _event_handlers : Dict[UUID, 'EventHandler'] = {}
    _event_handlers_by_trigger : Dict[Trigger, List['EventHandler']] = defaultdict(list)
    _event_handlers_by_simple_trigger : Dict[Trigger, List['EventHandler']] = defaultdict(list)
    _event_handlers_by_source_entity_uuid : Dict[UUID, List['EventHandler']] = defaultdict(list)

    # =========================================================================
    # SpatialHandler registries (position-indexed) - COMPLETELY SEPARATE
    # =========================================================================
    # Main registry for spatial handlers
    _spatial_handlers: Dict[UUID, 'SpatialHandler'] = {}

    # Position-indexed spatial handlers for O(1) lookup
    # (EventType, EventPhase) -> position -> List[BaseHandler]
    # Accepts both SpatialHandler (preferred) and legacy EventHandler
    _spatial_handlers_by_position: Dict[
        Tuple[EventType, EventPhase],
        Dict[Tuple[int, int], List['BaseHandler']]
    ] = defaultdict(lambda: defaultdict(list))

    # Source entity index for spatial handlers
    _spatial_handlers_by_source_entity_uuid: Dict[UUID, List['SpatialHandler']] = defaultdict(list)

    # Reverse index for batch position updates (handler_uuid -> positions)
    # Used by update_spatial_handler_positions for efficient delta computation
    _handler_positions: Dict[UUID, Tuple[Tuple[EventType, EventPhase], Set[Tuple[int, int]]]] = {}

    # Passive event callbacks (for monitoring, logging, websocket broadcast)
    # These are called for ALL events after storage, cannot modify events
    _on_event_callbacks: List[Callable[['Event'], None]] = []

    # Pre-completion callbacks are lifecycle systems. They run immediately
    # before an event phases to COMPLETION, while the causative event can still
    # receive child events that will be captured in children_lineages.
    _pre_completion_callbacks: List[Callable[['Event'], None]] = []
    _pre_completion_running: Set[UUID] = set()

    # Callback for combat log auto-capture (set by Encounter)
    # Called for top-level events (parent_event=None) when they complete with combat_log
    _combat_log_callback: Optional[Callable[['Event'], None]] = None

    # Callback for computing perceiver UUIDs at COMPLETION phase.
    # Takes an Event, returns Set[str] of entity UUIDs that can perceive it.
    _perceiver_computer: Optional[Callable[['Event'], Set[str]]] = None

    # Callback for computing revealed entity UUIDs at COMPLETION phase.
    # Takes an Event and child combat logs, returns Set[str] of entity UUIDs
    # that were revealed (Hidden/Invisible removed) during the event chain.
    _revealed_computer: Optional[Callable[['Event', List['CombatLogEntry']], Set[str]]] = None

    @classmethod
    def set_combat_log_callback(cls, callback: Optional[Callable[['Event'], None]]) -> None:
        """Register callback for auto-adding events to combat log.

        Called by Encounter when it becomes active. The callback receives
        top-level events (parent_event=None) when they complete with a combat_log.
        """
        cls._combat_log_callback = callback

    @classmethod
    def set_perceiver_computer(cls, func: Optional[Callable[['Event'], Set[str]]]) -> None:
        """Register callback for computing perceiver UUIDs on combat log entries.

        Called at COMPLETION phase when a combat log is generated. The callback
        receives the event and returns the set of entity UUID strings that can
        perceive it (based on GridMap subscriber lookups at affected positions).
        """
        cls._perceiver_computer = func

    @classmethod
    def set_revealed_computer(cls, func: Optional[Callable[['Event', List['CombatLogEntry']], Set[str]]]) -> None:
        """Register callback for computing revealed entity UUIDs on combat log entries.

        Called at COMPLETION phase when a combat log with child logs is generated.
        The callback receives the event and child combat logs, returns entity UUID
        strings that were revealed (Hidden/Invisible removed) during the event chain.
        """
        cls._revealed_computer = func

    @classmethod
    def push_combat_log(cls, entry: 'CombatLogEntry', source_entity_uuid: UUID) -> None:
        """Push a standalone combat log entry to the encounter.

        Used for informational logs (like "entity spotted") that don't correspond
        to a normal event lifecycle. Creates a lightweight Event just to carry the
        combat_log to the callback.
        """
        if cls._combat_log_callback is None:
            return
        event = Event(
            source_entity_uuid=source_entity_uuid,
            event_type=EventType.CONDITION_APPLICATION,
            phase=EventPhase.COMPLETION,
            use_register=False,
            combat_log=entry
        )
        cls._combat_log_callback(event)

    @classmethod
    def add_on_event_callback(cls, callback: Callable[['Event'], None]) -> None:
        """Add a callback that fires for every event after storage.

        Unlike EventHandlers, these callbacks:
        - Fire for ALL events regardless of phase
        - Cannot modify or cancel events
        - Are for passive monitoring (logging, websocket broadcast, etc.)
        """
        if callback not in cls._on_event_callbacks:
            cls._on_event_callbacks.append(callback)

    @classmethod
    def remove_on_event_callback(cls, callback: Callable[['Event'], None]) -> None:
        """Remove an event callback."""
        if callback in cls._on_event_callbacks:
            cls._on_event_callbacks.remove(callback)

    @classmethod
    def event_cursor(cls) -> int:
        """Return the raw append cursor for the event stream."""
        return len(cls._all_events)

    @classmethod
    def iter_events_since(cls, since: int) -> List[Tuple[int, 'Event']]:
        """Return raw events with their zero-based event-stream indexes."""
        start = max(0, since)
        return list(enumerate(cls._all_events[start:], start=start))

    @classmethod
    def get_event_index(cls, event_uuid: UUID) -> Optional[int]:
        """Return an event's raw stream index by UUID, if present."""
        for index, event in enumerate(cls._all_events):
            if event.uuid == event_uuid:
                return index
        return None

    @classmethod
    def add_pre_completion_callback(cls, callback: Callable[['Event'], None]) -> None:
        """Add a lifecycle callback that runs before event completion.

        Unlike passive on-event callbacks, these callbacks may emit child events.
        They run before completion metadata is computed, so child lineage fields
        remain structurally honest for animated clients and event-tree readers.
        """
        if callback not in cls._pre_completion_callbacks:
            cls._pre_completion_callbacks.append(callback)

    @classmethod
    def remove_pre_completion_callback(cls, callback: Callable[['Event'], None]) -> None:
        """Remove a pre-completion lifecycle callback."""
        if callback in cls._pre_completion_callbacks:
            cls._pre_completion_callbacks.remove(callback)

    @classmethod
    def run_pre_completion_callbacks(cls, event: Event) -> None:
        """Run lifecycle systems before an event completes."""
        if event.event_type == EventType.SENSORY_UPDATE:
            return
        if event.uuid in cls._pre_completion_running:
            return
        cls._pre_completion_running.add(event.uuid)
        try:
            for callback in list(cls._pre_completion_callbacks):
                callback(event)
        finally:
            cls._pre_completion_running.discard(event.uuid)

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
            # Execute handler
            result = handler(current_event)

            # If listener returned None, continue to next handler
            if result is None:
                continue

            # If event was canceled, stop processing
            if result.canceled:
                cls._store_event(result)
                return result

            # If event was modified, update for next handler
            if result.modified:
                current_event = result
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
            if parent_event and event.uuid not in parent_event.children_events:
                parent_event.add_child_event(event)
                # Propagate child to ALL lineage versions of parent so the latest
                # version has all children when its COMPLETION runs
                for lineage_event in cls._events_by_lineage.get(parent_event.lineage_uuid, []):
                    if lineage_event.uuid != parent_event.uuid:
                        if event.uuid not in lineage_event.lineage_children_events:
                            lineage_event.add_child_event(event)

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
        for callback in list(cls._on_event_callbacks):
            try:
                callback(event)
            except Exception:
                pass  # Don't let callback errors affect event processing
    
    @classmethod
    def _get_handlers_for_event(cls, event: Event) -> List['BaseHandler']:
        """Get all handlers that should process this event.

        This finds handlers by:
        1. For spatial events with position: O(1) lookup via position index
        2. Getting simple handlers (no source/target filter) via simple trigger lookup
        3. Iterating through all handlers and checking if their trigger matches the event
           using Trigger.__call__ which properly handles source/target filtering
        """
        # Check if this is a spatial event with position - use position-indexed lookup
        spatial_event_types = (
            EventType.SPATIAL_ENTITY_ENTERED,
            EventType.SPATIAL_ENTITY_LEFT,
            EventType.SPATIAL_TILE_CHANGED
        )
        if event.event_type in spatial_event_types:
            if isinstance(event, SpatialChangeEvent) and event.position is not None:
                return cls._get_handlers_for_spatial_event(event, event.position)

        # Non-spatial events: use existing lookup logic
        return cls._get_handlers_for_non_spatial_event(event)

    @classmethod
    def _get_handlers_for_spatial_event(
        cls,
        event: Event,
        position: Tuple[int, int]
    ) -> List['BaseHandler']:
        """Get handlers for spatial events using position-indexed lookup.

        Returns a mix of SpatialHandler and EventHandler instances:
        1. Position-indexed SpatialHandlers (O(1) lookup) - from _spatial_handlers
        2. Simple trigger EventHandlers (backward compatibility for OA pattern)
        3. Complex trigger EventHandlers that match this event

        Key insight: Step 3 only iterates _event_handlers, NOT _spatial_handlers.
        This prevents O(N) iteration over all spatial handlers.
        """
        event_key = (event.event_type, event.phase)
        handlers: List['BaseHandler'] = []
        seen: Set[UUID] = set()

        # 1. Position-indexed SpatialHandlers (O(1) lookup) - from SEPARATE registry
        pos_handlers = cls._spatial_handlers_by_position[event_key].get(position, [])
        for h in pos_handlers:
            if h.uuid not in seen:
                handlers.append(h)
                seen.add(h.uuid)

        # 2. Simple trigger EventHandlers (e.g., OA on STEP_MOVEMENT)
        simple_trigger = Trigger(event_type=event.event_type, event_phase=event.phase)
        for h in cls._event_handlers_by_simple_trigger.get(simple_trigger, []):
            if h.uuid not in seen:
                handlers.append(h)
                seen.add(h.uuid)

        # 3. Complex trigger EventHandlers (source/target filtering)
        # Only iterates _event_handlers, NOT _spatial_handlers
        # IMPORTANT: Skip handlers that are position-indexed (in _handler_positions)
        # - those should ONLY fire at their registered positions, not globally
        for handler in cls._event_handlers.values():
            if handler.uuid in seen:
                continue
            # Skip position-indexed handlers - they should only fire via step 1 at their positions
            if handler.uuid in cls._handler_positions:
                continue
            for trigger in handler.trigger_conditions:
                if trigger(event):
                    handlers.append(handler)
                    seen.add(handler.uuid)
                    break

        return handlers

    @classmethod
    def _get_handlers_for_non_spatial_event(cls, event: Event) -> List['BaseHandler']:
        """Get handlers for non-spatial events using existing lookup logic."""
        # Get the simple trigger for the event (just type + phase)
        simple_trigger = Trigger(event_type=event.event_type, event_phase=event.phase)

        # Get handlers registered with simple triggers
        simple_handlers = cls._event_handlers_by_simple_trigger.get(simple_trigger, [])

        # For handlers with complex triggers (source/target filtering),
        # we need to check each one since their trigger may filter by source/target UUID.
        # Use a set to avoid duplicates (handlers may be in both registries)
        handler_set: Set[UUID] = {h.uuid for h in simple_handlers}
        matching_handlers: List['BaseHandler'] = list(simple_handlers)

        # Check all handlers to find ones with complex triggers that match this event
        for handler in cls._event_handlers.values():
            if handler.uuid in handler_set:
                continue  # Already included
            # Check if any of the handler's triggers match this event
            for trigger in handler.trigger_conditions:
                if trigger(event):  # Uses Trigger.__call__ for proper matching
                    matching_handlers.append(handler)
                    handler_set.add(handler.uuid)
                    break  # Only add handler once even if multiple triggers match

        return matching_handlers
    
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
        """Remove a handler from all indices."""
        # Remove from trigger indices
        for trigger in event_handler.trigger_conditions:
            if trigger.is_simple():
                simple_trigger = trigger.get_simple_trigger()
                if event_handler in cls._event_handlers_by_simple_trigger.get(simple_trigger, []):
                    cls._event_handlers_by_simple_trigger[simple_trigger].remove(event_handler)
            if event_handler in cls._event_handlers_by_trigger.get(trigger, []):
                cls._event_handlers_by_trigger[trigger].remove(event_handler)

        # Remove from main handler dict (only once, outside the loop)
        cls._event_handlers.pop(event_handler.uuid, None)

        # Remove from source entity index
        source_handlers = cls._event_handlers_by_source_entity_uuid.get(event_handler.source_entity_uuid, [])
        if event_handler in source_handlers:
            source_handlers.remove(event_handler)

        # Remove from spatial handler indices if present
        cls._remove_from_spatial_indices(event_handler.uuid)

    @classmethod
    def remove_event_handlers_by_uuid(cls, uuid: UUID) -> None:
        """Remove a handler by uuid"""
        event_handler = cls._event_handlers.get(uuid)
        if event_handler:
            cls.remove_event_handler(event_handler)

    # =========================================================================
    # Position-Indexed Spatial Handlers
    # =========================================================================

    @classmethod
    def add_spatial_handler(
        cls,
        handler: Union['EventHandler', 'SpatialHandler'],
        positions: Optional[Set[Tuple[int, int]]] = None,
        event_type: EventType = EventType.SPATIAL_ENTITY_ENTERED,
        event_phase: EventPhase = EventPhase.EFFECT
    ) -> None:
        """
        Register a handler for specific positions only.

        This provides O(1) handler lookup for spatial events instead of
        iterating through all handlers. Used by zone spells to efficiently
        handle entry/exit effects.

        Accepts either:
        - SpatialHandler: Uses handler.positions, handler.event_type, handler.event_phase
        - EventHandler: Uses provided positions, event_type, event_phase (legacy support)

        Args:
            handler: The handler to register (SpatialHandler or EventHandler)
            positions: Set of (x, y) positions (optional if handler is SpatialHandler)
            event_type: The spatial event type (default: SPATIAL_ENTITY_ENTERED)
            event_phase: The event phase to trigger at (default: EFFECT)
        """
        # Handle SpatialHandler - use its built-in positions and event settings
        if isinstance(handler, SpatialHandler):
            actual_positions = handler.positions if not positions else positions
            event_key = (handler.event_type, handler.event_phase)

            # Update handler's positions if provided
            if positions:
                handler.positions = positions.copy()

            # Add to position index
            for pos in actual_positions:
                cls._spatial_handlers_by_position[event_key][pos].append(handler)

            # Track positions in reverse index for efficient updates
            cls._handler_positions[handler.uuid] = (event_key, actual_positions.copy())

            # Add to SPATIAL handler registries (SEPARATE from _event_handlers)
            cls._spatial_handlers[handler.uuid] = handler
            cls._spatial_handlers_by_source_entity_uuid[handler.source_entity_uuid].append(handler)

        else:
            # Legacy EventHandler support - add to position index but also main registry
            if positions is None:
                positions = set()

            event_key = (event_type, event_phase)

            # Add to position index
            for pos in positions:
                cls._spatial_handlers_by_position[event_key][pos].append(handler)

            # Track positions in reverse index for efficient updates
            cls._handler_positions[handler.uuid] = (event_key, positions.copy())

            # Also add to main handler registry (for general queries)
            cls._event_handlers[handler.uuid] = handler
            cls._event_handlers_by_source_entity_uuid[handler.source_entity_uuid].append(handler)

    @classmethod
    def update_spatial_handler_positions(
        cls,
        handler_uuid: UUID,
        new_positions: Set[Tuple[int, int]],
        event_type: Optional[EventType] = None,
        event_phase: Optional[EventPhase] = None
    ) -> bool:
        """
        Batch update handler positions - compute delta, only change affected positions.

        This is efficient for zone movement: instead of removing all positions
        and adding all new positions, we only modify the difference.

        Args:
            handler_uuid: UUID of the handler to update
            new_positions: New set of positions for this handler
            event_type: Override event type (uses stored value if None)
            event_phase: Override event phase (uses stored value if None)

        Returns:
            True if handler was found and updated, False otherwise
        """
        if handler_uuid not in cls._handler_positions:
            return False

        # Look for handler in both registries
        handler: Optional['BaseHandler'] = cls._spatial_handlers.get(handler_uuid)
        if not handler:
            handler = cls._event_handlers.get(handler_uuid)
        if not handler:
            return False

        old_event_key, old_positions = cls._handler_positions[handler_uuid]

        # Use new event key if provided, otherwise keep old
        if event_type is not None and event_phase is not None:
            new_event_key = (event_type, event_phase)
        else:
            new_event_key = old_event_key

        # If event key changed, remove from all old positions and add to all new
        if new_event_key != old_event_key:
            # Remove from old event key positions
            for pos in old_positions:
                handlers_at_pos = cls._spatial_handlers_by_position[old_event_key].get(pos, [])
                if handler in handlers_at_pos:
                    handlers_at_pos.remove(handler)
                    if not handlers_at_pos:
                        del cls._spatial_handlers_by_position[old_event_key][pos]

            # Add to new event key positions
            for pos in new_positions:
                cls._spatial_handlers_by_position[new_event_key][pos].append(handler)
        else:
            # Same event key - compute position delta
            positions_to_remove = old_positions - new_positions
            positions_to_add = new_positions - old_positions

            # Remove handler from positions we're leaving
            for pos in positions_to_remove:
                handlers_at_pos = cls._spatial_handlers_by_position[new_event_key].get(pos, [])
                if handler in handlers_at_pos:
                    handlers_at_pos.remove(handler)
                    if not handlers_at_pos:
                        del cls._spatial_handlers_by_position[new_event_key][pos]

            # Add handler to new positions
            for pos in positions_to_add:
                cls._spatial_handlers_by_position[new_event_key][pos].append(handler)

        # Update reverse index
        cls._handler_positions[handler_uuid] = (new_event_key, new_positions.copy())

        # If this is a SpatialHandler, also update its positions field
        if isinstance(handler, SpatialHandler):
            handler.positions = new_positions.copy()

        return True

    @classmethod
    def remove_spatial_handler(cls, handler_uuid: UUID) -> bool:
        """
        Remove a spatial handler from all position indices.

        Works with both SpatialHandler (in _spatial_handlers) and
        legacy EventHandler (in _event_handlers) registered via add_spatial_handler.

        Args:
            handler_uuid: UUID of the handler to remove

        Returns:
            True if handler was found and removed, False otherwise
        """
        if handler_uuid not in cls._handler_positions:
            return False

        # Look for handler in both registries
        handler: Optional['BaseHandler'] = cls._spatial_handlers.get(handler_uuid)
        is_spatial_handler = handler is not None

        if not handler:
            handler = cls._event_handlers.get(handler_uuid)

        if not handler:
            # Still clean up indices even if handler is gone
            cls._remove_from_spatial_indices(handler_uuid)
            return True

        # Remove from spatial indices
        cls._remove_from_spatial_indices(handler_uuid)

        # Remove from appropriate registry
        if is_spatial_handler:
            cls._spatial_handlers.pop(handler_uuid, None)
            source_handlers = cls._spatial_handlers_by_source_entity_uuid.get(handler.source_entity_uuid, [])
            if handler in source_handlers:
                source_handlers.remove(handler)
        else:
            cls._event_handlers.pop(handler_uuid, None)
            source_handlers = cls._event_handlers_by_source_entity_uuid.get(handler.source_entity_uuid, [])
            if handler in source_handlers:
                source_handlers.remove(handler)

        return True

    @classmethod
    def _remove_from_spatial_indices(cls, handler_uuid: UUID) -> None:
        """Internal helper to remove handler from spatial position indices."""
        if handler_uuid not in cls._handler_positions:
            return

        event_key, positions = cls._handler_positions[handler_uuid]

        # Look for handler in both registries
        handler: Optional['BaseHandler'] = cls._spatial_handlers.get(handler_uuid)
        if not handler:
            handler = cls._event_handlers.get(handler_uuid)

        # Remove from each position
        for pos in positions:
            handlers_at_pos = cls._spatial_handlers_by_position[event_key].get(pos, [])
            if handler and handler in handlers_at_pos:
                handlers_at_pos.remove(handler)
                if not handlers_at_pos:
                    del cls._spatial_handlers_by_position[event_key][pos]

        # Remove from reverse index
        del cls._handler_positions[handler_uuid]

    @classmethod
    def get_spatial_handlers_at(
        cls,
        position: Tuple[int, int],
        event_type: EventType = EventType.SPATIAL_ENTITY_ENTERED,
        event_phase: EventPhase = EventPhase.EFFECT
    ) -> List['BaseHandler']:
        """
        Get all spatial handlers registered for a specific position.

        Args:
            position: The (x, y) position to query
            event_type: The spatial event type
            event_phase: The event phase

        Returns:
            List of handlers registered at this position (may be empty)
        """
        event_key = (event_type, event_phase)
        return cls._spatial_handlers_by_position[event_key].get(position, []).copy()

    # =========================================================================
    # End Spatial Handler Methods
    # =========================================================================

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
        # Clear EventHandler registries
        cls._event_handlers.clear()
        cls._event_handlers_by_trigger.clear()
        cls._event_handlers_by_simple_trigger.clear()
        cls._event_handlers_by_source_entity_uuid.clear()
        # Clear SpatialHandler registries (SEPARATE)
        cls._spatial_handlers.clear()
        cls._spatial_handlers_by_position.clear()
        cls._spatial_handlers_by_source_entity_uuid.clear()
        cls._handler_positions.clear()
        # Clear event callbacks (spatial senses callbacks, etc.)
        cls._on_event_callbacks.clear()
        cls._pre_completion_callbacks.clear()
        cls._pre_completion_running.clear()
        cls._perceiver_computer = None
        cls._revealed_computer = None


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
                adv_status = self.dice_roll.advantage_status
                if adv_status:
                    adv_value = adv_status.value.lower()
                    roll.advantage_status = adv_value
                    if len(results) >= 2:
                        if adv_value == "advantage":
                            roll.d20_used = max(results)
                        elif adv_value == "disadvantage":
                            roll.d20_used = min(results)
            elif isinstance(results, int):
                roll.results = [results]
                roll.d20_used = results

            roll.bonus = self.dice_roll.bonus
            roll.total = self.dice_roll.total

        # Build bonus breakdown
        bonus_breakdown: List[ModifierBreakdown] = []
        if self.bonus and isinstance(self.bonus, ModifiableValue):
            for mod in self.bonus.get_breakdown():
                bonus_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

        # Build advantage breakdown
        advantage_breakdown: List[ModifierBreakdown] = []
        if self.bonus and isinstance(self.bonus, ModifiableValue):
            for mod in self.bonus.get_full_advantage_breakdown():
                adv_val = mod.get('value', 'inactive')
                if adv_val == 'advantage':
                    advantage_breakdown.append(ModifierBreakdown(
                        name=mod.get('name', 'Unknown'), value=1, source=mod.get('source', 'self')
                    ))
                elif adv_val == 'disadvantage':
                    advantage_breakdown.append(ModifierBreakdown(
                        name=mod.get('name', 'Unknown'), value=-1, source=mod.get('source', 'self')
                    ))

        # Determine success
        success = self.result if self.result is not None else (roll.total >= dc if dc > 0 else None)

        # Build ability name display
        ability_display = self.ability_name.upper()[:3]  # STR, DEX, etc.

        # Build markdown-formatted verbosity levels
        success_str = md_color("succeeds", "green") if success else md_color("fails", "red")

        # COMPACT: "{cyan:Hero} {green:succeeds} {yellow:DEX} save (DC 14)"
        compact_text = f"{md_color(target_name, 'cyan')} {success_str} {md_color(ability_display, 'yellow')} save (DC {dc})"

        # VERBOSE: Add the roll details
        d20_str = md_d20_roll(roll)
        bonus_str = f"+{roll.bonus}" if roll.bonus >= 0 else str(roll.bonus)
        verbose_text = f"{md_color(target_name, 'cyan')} {md_color(ability_display, 'yellow')} save vs DC {dc}"
        verbose_text += f"\n  Save: {d20_str} {bonus_str} = {roll.total} → {success_str}"

        # DETAILED: Add breakdown
        detailed_text = f"{md_color(target_name, 'cyan')} {md_color(ability_display, 'yellow')} save vs DC {dc}"
        breakdown_str = md_breakdown(bonus_breakdown)
        detailed_text += f"\n  Save: {d20_str} {bonus_str}"
        if breakdown_str:
            detailed_text += f" {breakdown_str}"
        detailed_text += f" = {roll.total} → {success_str}"

        # Build structured data
        data = SavingThrowLogData(
            entity_name=target_name,
            entity_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else str(self.source_entity_uuid),
            ability=self.ability_name,
            dc=dc,
            roll=roll,
            bonus_breakdown=bonus_breakdown,
            advantage_breakdown=advantage_breakdown,
            success=success or False,
            source_name=source_name if source_name != target_name else None
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.SAVING_THROW,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else None,
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
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
                adv_status = self.dice_roll.advantage_status
                if adv_status:
                    adv_value = adv_status.value.lower()
                    roll.advantage_status = adv_value
                    if len(results) >= 2:
                        if adv_value == "advantage":
                            roll.d20_used = max(results)
                        elif adv_value == "disadvantage":
                            roll.d20_used = min(results)
            elif isinstance(results, int):
                roll.results = [results]
                roll.d20_used = results

            roll.bonus = self.dice_roll.bonus
            roll.total = self.dice_roll.total

        # Build bonus breakdown
        bonus_breakdown: List[ModifierBreakdown] = []
        if self.bonus and isinstance(self.bonus, ModifiableValue):
            for mod in self.bonus.get_breakdown():
                bonus_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

        # Build advantage breakdown
        advantage_breakdown: List[ModifierBreakdown] = []
        if self.bonus and isinstance(self.bonus, ModifiableValue):
            for mod in self.bonus.get_full_advantage_breakdown():
                adv_val = mod.get('value', 'inactive')
                if adv_val == 'advantage':
                    advantage_breakdown.append(ModifierBreakdown(
                        name=mod.get('name', 'Unknown'), value=1, source=mod.get('source', 'self')
                    ))
                elif adv_val == 'disadvantage':
                    advantage_breakdown.append(ModifierBreakdown(
                        name=mod.get('name', 'Unknown'), value=-1, source=mod.get('source', 'self')
                    ))

        # Determine success
        success = self.result if self.result is not None else (roll.total >= dc if dc is not None and dc > 0 else None)

        # Build skill name display (capitalize first letter)
        skill_display = self.skill_name.replace('_', ' ').title()

        # Build markdown-formatted verbosity levels
        d20_str = md_d20_roll(roll)
        bonus_str = f"+{roll.bonus}" if roll.bonus >= 0 else str(roll.bonus)
        breakdown_str = md_breakdown(bonus_breakdown)

        if dc is not None:
            success_str = md_color("succeeds", "green") if success else md_color("fails", "red")

            # COMPACT: "{cyan:Hero} {green:succeeds} {yellow:Athletics} check (DC 14)"
            compact_text = f"{md_color(source_name, 'cyan')} {success_str} {md_color(skill_display, 'yellow')} check (DC {dc})"

            # VERBOSE: Add the roll details
            verbose_text = f"{md_color(source_name, 'cyan')} {md_color(skill_display, 'yellow')} check vs DC {dc}"
            verbose_text += f"\n  {skill_display}: {d20_str} {bonus_str} = {roll.total} → {success_str}"

            # DETAILED: Add breakdown
            detailed_text = f"{md_color(source_name, 'cyan')} {md_color(skill_display, 'yellow')} check vs DC {dc}"
            detailed_text += f"\n  {skill_display}: {d20_str} {bonus_str}"
            if breakdown_str:
                detailed_text += f" {breakdown_str}"
            detailed_text += f" = {roll.total} → {success_str}"
        else:
            # No DC - just show the roll
            compact_text = f"{md_color(source_name, 'cyan')} rolls {md_color(skill_display, 'yellow')}: {md_color(str(roll.total), 'cyan')}"
            verbose_text = f"{md_color(source_name, 'cyan')} {md_color(skill_display, 'yellow')} check"
            verbose_text += f"\n  {skill_display}: {d20_str} {bonus_str} = {roll.total}"
            detailed_text = verbose_text
            if breakdown_str:
                detailed_text = f"{md_color(source_name, 'cyan')} {md_color(skill_display, 'yellow')} check"
                detailed_text += f"\n  {skill_display}: {d20_str} {bonus_str} {breakdown_str} = {roll.total}"

        # Build structured data
        data = SkillCheckLogData(
            entity_name=source_name,
            entity_uuid=str(self.source_entity_uuid),
            skill=self.skill_name,
            dc=dc,
            roll=roll,
            bonus_breakdown=bonus_breakdown,
            advantage_breakdown=advantage_breakdown,
            success=success
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.SKILL_CHECK,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data=data.model_dump(),
            success=success
        )


class SensesUpdateHint(BaseModel):
    """Carried by spatial events — tells observers what to update incrementally.

    Encodes which of the three independent senses layers changed:
    - FOV (geometric visibility): walls, magical darkness, vision-blocking objects
    - Paths (movement routes): entities moving, walkability changes, movement-blocking objects
    - Entity filter (who's seen): light levels, perceivability, entity presence
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Which senses layers need recomputing
    requires_fov: bool = False       # Vision geometry changed (magical darkness, wall, door vision blocking)
    requires_paths: bool = False     # Path topology changed (entity moved, walkability changed, door movement blocking)

    # Entity dict updates (O(1) per entry)
    entity_entered: Optional[Tuple[UUID, Tuple[int, int]]] = None
    entity_left: Optional[Tuple[UUID, Tuple[int, int]]] = None

    # Light-based re-filtering at specific positions
    light_changed_positions: Optional[Set[Tuple[int, int]]] = None

    # Perceivability re-check for one entity
    perceivability_entity: Optional[UUID] = None

    # Object dict updates
    object_placed: Optional[Tuple[UUID, Tuple[int, int]]] = None
    object_removed: Optional[Tuple[UUID, Tuple[int, int]]] = None

    # Death: entity stopped blocking
    entity_died: Optional[Tuple[UUID, Tuple[int, int]]] = None


class SensoryUpdateEvent(Event):
    """Observer-specific sensory state delta.

    This event records the backend-authoritative change to one observer's
    visibility/fog/entity/object perception. It is emitted before the causative
    parent completes, so clients can animate perception changes from the event
    tree without recomputing FOV or polling snapshots for timing.
    """
    name: str = Field(default="Sensory Update", description="Observer sensory state changed")
    event_type: EventType = Field(default=EventType.SENSORY_UPDATE)
    observer_uuid: UUID = Field(description="Observer whose sensory state changed")
    cause_event_uuid: UUID = Field(description="Event UUID that caused this sensory update")
    update_reason: SensoryUpdateReason = Field(default=SensoryUpdateReason.UNKNOWN)

    visible_cells_added: List[Tuple[int, int]] = Field(default_factory=list)
    visible_cells_removed: List[Tuple[int, int]] = Field(default_factory=list)
    seen_cells_added: List[Tuple[int, int]] = Field(default_factory=list)

    visible_entities_added: Dict[UUID, Tuple[int, int]] = Field(default_factory=dict)
    visible_entities_removed: Dict[UUID, Tuple[int, int]] = Field(default_factory=dict)
    visible_entities_moved: Dict[UUID, Tuple[Tuple[int, int], Tuple[int, int]]] = Field(default_factory=dict)

    visible_objects_added: Dict[UUID, Tuple[int, int]] = Field(default_factory=dict)
    visible_objects_removed: Dict[UUID, Tuple[int, int]] = Field(default_factory=dict)
    visible_objects_moved: Dict[UUID, Tuple[Tuple[int, int], Tuple[int, int]]] = Field(default_factory=dict)

    sense_modes_changed: bool = Field(default=False)
    sense_modes: Optional[List[Dict[str, Any]]] = Field(default=None)
    passive_perception_changed: bool = Field(default=False)
    passive_perception: Optional[int] = Field(default=None)
    paths_dirty: bool = Field(default=False)

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        positions: Set[Tuple[int, int]] = set(self.visible_cells_added)
        positions.update(self.visible_cells_removed)
        positions.update(self.seen_cells_added)
        positions.update(self.visible_entities_added.values())
        positions.update(self.visible_entities_removed.values())
        for old_pos, new_pos in self.visible_entities_moved.values():
            positions.add(old_pos)
            positions.add(new_pos)
        positions.update(self.visible_objects_added.values())
        positions.update(self.visible_objects_removed.values())
        for old_pos, new_pos in self.visible_objects_moved.values():
            positions.add(old_pos)
            positions.add(new_pos)
        return positions


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
    object_uuid: Optional[UUID] = Field(default=None, description="UUID of object involved (if any)")
    old_position: Optional[Tuple[int, int]] = Field(default=None, description="Previous position (for movement)")
    tile_walkable: Optional[bool] = Field(default=None, description="New walkable state (for tile changes)")
    tile_visible: Optional[bool] = Field(default=None, description="New visible state (for tile changes)")
    senses_hint: Optional[SensesUpdateHint] = Field(default=None, description="Hint for incremental senses updates")

    # For frontend reducer — light level after change
    new_light_level: Optional[int] = Field(default=None, description="Resolved light level at position after change")
    light_level_map: Optional[Dict[str, int]] = Field(default=None, description="Map of 'x,y' -> resolved light_level for all changed positions in batch")

    # For frontend reducer — object metadata (placed/changed events)
    object_name: Optional[str] = Field(default=None, description="Object name (e.g. 'Door', 'Torch')")
    object_map_char: Optional[str] = Field(default=None, description="Object map character (e.g. 'D', 'φ')")
    object_blocks_movement: Optional[bool] = Field(default=None, description="Object blocks_movement after change")
    object_blocks_vision: Optional[bool] = Field(default=None, description="Object blocks_vision after change")
    object_is_open: Optional[bool] = Field(default=None, description="Object is_open state (doors)")

    @classmethod
    def entity_entered(cls, position: Tuple[int, int], entity_uuid: UUID,
                       old_position: Optional[Tuple[int, int]] = None,
                       source_entity_uuid: Optional[UUID] = None,
                       parent_event: Optional[UUID] = None) -> 'SpatialChangeEvent':
        """Create an event for an entity entering a cell.

        Event starts at DECLARATION phase to allow full lifecycle:
        DECLARATION -> EXECUTION -> EFFECT -> COMPLETION

        Handlers can react at EFFECT phase (entry damage, saves, etc.)
        Callbacks fire at COMPLETION for passive updates (senses).

        Args:
            position: Grid position being entered
            entity_uuid: UUID of entity entering
            old_position: Previous position (if moving)
            source_entity_uuid: Source entity for event (defaults to entity_uuid)
            parent_event: Optional parent event UUID for lineage (e.g., StepMovementEvent)
        """
        hint = SensesUpdateHint(
            requires_paths=True,
            entity_entered=(entity_uuid, position),
        )
        return cls(
            source_entity_uuid=source_entity_uuid or entity_uuid,
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            change_type=SpatialChangeType.ENTITY_ENTERED,
            position=position,
            entity_uuid=entity_uuid,
            old_position=old_position,
            phase=EventPhase.DECLARATION,
            use_register=False,  # GridMap controls registration via _fire_spatial_event
            parent_event=parent_event,
            senses_hint=hint,
        )

    @classmethod
    def entity_left(cls, position: Tuple[int, int], entity_uuid: UUID,
                    new_position: Optional[Tuple[int, int]] = None,
                    source_entity_uuid: Optional[UUID] = None,
                    parent_event: Optional[UUID] = None) -> 'SpatialChangeEvent':
        """Create an event for an entity leaving a cell.

        Event starts at DECLARATION phase to allow full lifecycle:
        DECLARATION -> EXECUTION -> EFFECT -> COMPLETION

        Note: old_position field stores the new_position for reference.

        Args:
            position: Grid position being left
            entity_uuid: UUID of entity leaving
            new_position: New position (if moving)
            source_entity_uuid: Source entity for event (defaults to entity_uuid)
            parent_event: Optional parent event UUID for lineage (e.g., StepMovementEvent)
        """
        hint = SensesUpdateHint(
            requires_paths=True,
            entity_left=(entity_uuid, position),
        )
        return cls(
            source_entity_uuid=source_entity_uuid or entity_uuid,
            event_type=EventType.SPATIAL_ENTITY_LEFT,
            change_type=SpatialChangeType.ENTITY_LEFT,
            position=position,
            entity_uuid=entity_uuid,
            old_position=new_position,  # Store new position in old_position field for reference
            phase=EventPhase.DECLARATION,
            use_register=False,  # GridMap controls registration via _fire_spatial_event
            parent_event=parent_event,
            senses_hint=hint,
        )

    @classmethod
    def tile_changed(cls, position: Tuple[int, int], walkable: bool, visible: bool,
                     source_entity_uuid: Optional[UUID] = None,
                     senses_hint: Optional['SensesUpdateHint'] = None,
                     parent_event: Optional[UUID] = None) -> 'SpatialChangeEvent':
        """Create an event for a tile property change.

        Event starts at DECLARATION phase to allow full lifecycle.
        If no senses_hint is provided, one is auto-generated from walkable/visible flags
        requiring FOV if visible changed and paths if walkable changed.
        """
        if senses_hint is None:
            senses_hint = SensesUpdateHint(
                requires_fov=True,    # Tile change may affect vision
                requires_paths=True,  # Tile change may affect walkability
            )
        return cls(
            source_entity_uuid=source_entity_uuid or uuid4(),
            event_type=EventType.SPATIAL_TILE_CHANGED,
            change_type=SpatialChangeType.TILE_CHANGED,
            position=position,
            tile_walkable=walkable,
            tile_visible=visible,
            phase=EventPhase.DECLARATION,
            use_register=False,  # GridMap controls registration via _fire_spatial_event
            parent_event=parent_event,
            senses_hint=senses_hint,
        )

    @classmethod
    def object_placed(cls, position: Tuple[int, int], object_uuid: UUID,
                      source_entity_uuid: Optional[UUID] = None,
                      parent_event: Optional[UUID] = None,
                      blocks_vision: bool = False,
                      blocks_walking: bool = False,
                      object_name: Optional[str] = None,
                      object_map_char: Optional[str] = None) -> 'SpatialChangeEvent':
        """Create an event for an object being placed on the grid."""
        hint = SensesUpdateHint(
            requires_fov=blocks_vision,
            requires_paths=blocks_walking,
            object_placed=(object_uuid, position),
        )
        return cls(
            source_entity_uuid=source_entity_uuid or uuid4(),
            event_type=EventType.SPATIAL_OBJECT_PLACED,
            change_type=SpatialChangeType.OBJECT_PLACED,
            position=position,
            object_uuid=object_uuid,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=hint,
            object_name=object_name,
            object_map_char=object_map_char,
        )

    @classmethod
    def object_removed(cls, position: Tuple[int, int], object_uuid: UUID,
                       source_entity_uuid: Optional[UUID] = None,
                       parent_event: Optional[UUID] = None,
                       blocks_vision: bool = False,
                       blocks_walking: bool = False) -> 'SpatialChangeEvent':
        """Create an event for an object being removed from the grid."""
        hint = SensesUpdateHint(
            requires_fov=blocks_vision,
            requires_paths=blocks_walking,
            object_removed=(object_uuid, position),
        )
        return cls(
            source_entity_uuid=source_entity_uuid or uuid4(),
            event_type=EventType.SPATIAL_OBJECT_REMOVED,
            change_type=SpatialChangeType.OBJECT_REMOVED,
            position=position,
            object_uuid=object_uuid,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=hint,
        )

    @classmethod
    def perceivability_changed(cls, position: Tuple[int, int], entity_uuid: UUID,
                               source_entity_uuid: Optional[UUID] = None,
                               parent_event: Optional[UUID] = None) -> 'SpatialChangeEvent':
        """Create an event for an entity's perceivability changing (hidden/invisible).

        This is a lightweight event that only triggers senses re-evaluation
        on observers subscribed to this cell. Does NOT trigger SpatialHandlers (zone effects).
        """
        hint = SensesUpdateHint(
            perceivability_entity=entity_uuid,
            requires_paths=True,
        )
        return cls(
            source_entity_uuid=source_entity_uuid or entity_uuid,
            event_type=EventType.SPATIAL_PERCEIVABILITY_CHANGED,
            change_type=SpatialChangeType.PERCEIVABILITY_CHANGED,
            position=position,
            entity_uuid=entity_uuid,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=hint,
        )

    @classmethod
    def light_changed(cls, position: Tuple[int, int], tile_uuid: UUID,
                      source_entity_uuid: Optional[UUID] = None,
                      senses_hint: Optional['SensesUpdateHint'] = None,
                      parent_event: Optional[UUID] = None,
                      new_light_level: Optional[int] = None,
                      light_level_map: Optional[Dict[str, int]] = None) -> 'SpatialChangeEvent':
        """Create an event for a tile's resolved light level changing.

        Triggers senses re-evaluation on observers subscribed to this cell.
        Does NOT trigger SpatialHandlers (zone effects).
        """
        if senses_hint is None:
            senses_hint = SensesUpdateHint(
                light_changed_positions={position},
            )
        return cls(
            source_entity_uuid=source_entity_uuid or tile_uuid,
            event_type=EventType.SPATIAL_LIGHT_CHANGED,
            change_type=SpatialChangeType.LIGHT_CHANGED,
            position=position,
            entity_uuid=tile_uuid,  # Tile UUID stored in entity_uuid field
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=senses_hint,
            new_light_level=new_light_level,
            light_level_map=light_level_map,
        )

    @classmethod
    def object_changed(cls, position: Tuple[int, int], object_uuid: UUID,
                       blocks_vision_changed: bool = False,
                       blocks_walking_changed: bool = False,
                       source_entity_uuid: Optional[UUID] = None,
                       parent_event: Optional[UUID] = None,
                       object_name: Optional[str] = None,
                       object_map_char: Optional[str] = None,
                       object_blocks_movement: Optional[bool] = None,
                       object_blocks_vision: Optional[bool] = None,
                       object_is_open: Optional[bool] = None) -> 'SpatialChangeEvent':
        """Create an event for an object's blocking state changing (door open/close).

        Fires when an object's blocks_movement or blocks_vision_field changes
        while on the grid. Carries hint indicating which senses layers are affected.
        """
        hint = SensesUpdateHint(
            requires_fov=blocks_vision_changed,
            requires_paths=blocks_walking_changed,
        )
        return cls(
            source_entity_uuid=source_entity_uuid or object_uuid,
            event_type=EventType.SPATIAL_OBJECT_CHANGED,
            change_type=SpatialChangeType.OBJECT_CHANGED,
            position=position,
            object_uuid=object_uuid,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=hint,
            object_name=object_name,
            object_map_char=object_map_char,
            object_blocks_movement=object_blocks_movement,
            object_blocks_vision=object_blocks_vision,
            object_is_open=object_is_open,
        )

    @classmethod
    def movement_collision(cls, position: Tuple[int, int], mover_uuid: UUID,
                           source_entity_uuid: Optional[UUID] = None,
                           parent_event: Optional[UUID] = None) -> 'SpatialChangeEvent':
        """Create an event for an entity bumping into an imperceivable blocker.

        Fired when objective walkability blocks but subjective would allow.
        Hidden entities at this position will be de-stealthed by their reveal handler.
        """
        hint = SensesUpdateHint(requires_paths=True)
        return cls(
            source_entity_uuid=source_entity_uuid or mover_uuid,
            event_type=EventType.MOVEMENT_COLLISION,
            change_type=SpatialChangeType.MOVEMENT_COLLISION,
            position=position,
            entity_uuid=mover_uuid,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=hint,
        )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        positions = {self.position}
        if self.old_position:
            positions.add(self.old_position)
        return positions


class ForcedMovementEvent(Event):
    """Forced movement (push/pull) - does NOT trigger opportunity attacks.

    This event type intentionally uses FORCED_MOVEMENT instead of MOVEMENT to ensure
    OA handlers never fire. GridMap spatial events still fire normally when the
    target's position is updated.

    Used by: Shove, Thunderwave, repelling effects, etc.

    Note: target_entity_uuid is inherited from Event and should always be set
    for forced movement events (it's the entity being pushed).
    """
    name: str = Field(default="Forced Movement")
    event_type: EventType = Field(default=EventType.FORCED_MOVEMENT)

    # Movement details (target_entity_uuid is inherited from Event - it's who's being pushed)
    start_position: Tuple[int, int] = Field(description="Position before push")
    end_position: Tuple[int, int] = Field(description="Position after push")
    direction: Tuple[int, int] = Field(description="Push direction as (dx, dy)")
    intended_distance: int = Field(description="How far we tried to push (feet)")
    actual_distance: int = Field(default=0, description="How far they actually moved")
    blocked_by_obstacle: bool = Field(default=False, description="Stopped by wall/entity")
    blocked_by: Optional[str] = Field(default=None, description="What blocked the push (e.g. 'Wall', 'Skeleton 1')")
    cause: str = Field(default="shove", description="What caused this: shove, thunderwave, etc.")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate combat log for forced movement."""
        source_name = self.source_entity_name or "Unknown"
        target_name = self.target_entity_name or "Unknown"

        # Build blocked suffix
        blocked_suffix = ""
        if self.blocked_by_obstacle:
            if self.blocked_by:
                blocked_suffix = f" (blocked by {self.blocked_by})"
            else:
                blocked_suffix = " (blocked)"

        # Build markdown-formatted verbosity levels
        if self.actual_distance == 0:
            compact_text = f"{md_color(target_name, 'yellow')} resists being pushed"
        elif self.blocked_by_obstacle:
            compact_text = f"{md_color(target_name, 'yellow')} pushed {md_color(f'{self.actual_distance}ft', 'green')}{blocked_suffix}"
        else:
            compact_text = f"{md_color(target_name, 'yellow')} pushed {md_color(f'{self.actual_distance}ft', 'green')}"

        # VERBOSE: Add pusher
        verbose_text = f"{md_color(source_name, 'cyan')} pushes {md_color(target_name, 'yellow')}"
        if self.actual_distance > 0:
            verbose_text += f" {md_color(f'{self.actual_distance}ft', 'green')}"
            if self.blocked_by_obstacle:
                verbose_text += blocked_suffix
        else:
            verbose_text += f" - {md_color('resisted', 'red')}"

        # DETAILED: Add direction and positions
        detailed_text = verbose_text
        detailed_text += f"\n  Direction: {self.direction}"
        detailed_text += f"\n  {self.start_position} → {self.end_position}"
        if self.actual_distance != self.intended_distance:
            detailed_text += f"\n  Intended: {self.intended_distance}ft, Actual: {self.actual_distance}ft"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.MOVEMENT,  # Reuse existing type for display
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid),
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data={
                "type": "forced_movement",
                "cause": self.cause,
                "direction": list(self.direction),
                "intended_distance": self.intended_distance,
                "actual_distance": self.actual_distance,
                "blocked": self.blocked_by_obstacle,
                "blocked_by": self.blocked_by,
                "start_position": list(self.start_position),
                "end_position": list(self.end_position)
            },
            success=self.actual_distance > 0
        )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        return {self.start_position, self.end_position}


class StepMovementEvent(Event):
    """Single cell transition within a movement path.

    Fires for each step during cell-by-cell movement. Opportunity attacks
    and terrain effects trigger on this event type.

    The source_entity_uuid is the entity moving.
    """
    name: str = Field(default="Step Movement")
    event_type: EventType = Field(default=EventType.STEP_MOVEMENT)

    from_position: Tuple[int, int] = Field(description="Position before this step")
    to_position: Tuple[int, int] = Field(description="Position after this step")
    path_index: int = Field(default=0, description="Index of this step in the overall path")
    total_path_length: int = Field(default=0, description="Total number of positions in path")
    movement_cost: float = Field(default=5.0, description="Movement cost in feet for this step")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate combat log for a movement step (usually not logged individually)."""
        source_name = self.source_entity_name or "Unknown"

        compact_text = f"{md_color(source_name, 'cyan')} steps to {self.to_position}"
        verbose_text = f"{md_color(source_name, 'cyan')} {self.from_position} → {self.to_position}"
        detailed_text = f"{verbose_text} (step {self.path_index}/{self.total_path_length - 1}, {self.movement_cost}ft)"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.MOVEMENT,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data={
                "type": "step_movement",
                "from_position": list(self.from_position),
                "to_position": list(self.to_position),
                "path_index": self.path_index,
                "movement_cost": self.movement_cost
            },
            success=True
        )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        return {self.from_position, self.to_position}


class RangeType(str, Enum):
    REACH = "Reach"
    RANGE = "Range"
    SELF = "Self"  # For spells that originate from caster (cone, line, cube from self)


class Range(BaseModel):
    type: RangeType = Field(
        description="The type of range (Reach, Range, or Self)"
    )
    normal: int = Field(
        default=0,
        description="Normal range in feet (0 for Self range)"
    )
    long: Optional[int] = Field(
        default=None,
        description="Long range in feet, only applicable for ranged weapons"
    )

    def __str__(self):
        if self.type == RangeType.SELF:
            return "Self"
        elif self.type == RangeType.REACH:
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
        assert self.damage_bonus is not None, "Damage requires damage_bonus to be set"
        return Dice(count=self.dice_numbers, value=self.damage_dice, bonus=self.damage_bonus, roll_type=RollType.DAMAGE, attack_outcome=attack_outcome, crit_extra_dice=crit_extra_dice)


class Healing(BaseObject):
    """Healing specification — analogous to Damage but for healing rolls."""
    name: str = Field(default="Healing", description="Name of the healing")
    healing_dice: Literal[4, 6, 8, 10, 12, 20] = Field(
        description="Number of sides on the healing dice (e.g., 8 for d8)"
    )
    dice_numbers: int = Field(
        description="Number of dice to roll for healing (e.g., 2 for 2d8)"
    )
    healing_bonus: Optional[ModifiableValue] = Field(
        default=None,
        description="Bonus to healing rolls (typically spellcasting ability modifier)"
    )

    def get_dice(self) -> Dice:
        assert self.healing_bonus is not None, "Healing requires healing_bonus to be set"
        return Dice(
            count=self.dice_numbers,
            value=self.healing_dice,
            bonus=self.healing_bonus,
            roll_type=RollType.HEAL
        )


# =============================================================================
# Unified Dice Roll Event Hierarchy
# =============================================================================

class DiceRollResultEvent(Event):
    """
    Base class for all dice roll result events.

    Provides unified handler interception for d20 rolls, damage rolls, etc.
    """
    event_type: EventType = Field(default=EventType.DICE_ROLL_RESULT)

    # Roll type classification
    roll_type: RollType = Field(
        ...,
        description="ATTACK, SAVE, CHECK, or DAMAGE - determines handler eligibility"
    )

    # Handler context (arbitrary data for handler decisions)
    context: Dict[str, Any] = Field(default_factory=dict)

    # Modification tracking
    roll_modifications: List[Tuple[str, str]] = Field(
        default_factory=list,
        description="[(handler_name, reason), ...] for combat log/debugging"
    )

    def add_modification(self, handler_name: str, reason: str) -> None:
        """Track that a handler modified this roll."""
        self.roll_modifications.append((handler_name, reason))
        self.modified = True


class D20RollResultEvent(DiceRollResultEvent):
    """
    Base class for d20 roll results.

    Subclasses: AttackD20RollResultEvent, SavingThrowD20RollResultEvent, SkillCheckD20RollResultEvent

    Handlers like Lucky can register for this base type to catch ALL d20 rolls.
    Type-specific handlers register for the specific subclass.
    """
    event_type: EventType = Field(default=EventType.D20_ROLL_RESULT)

    # The Roll (single d20)
    roll: DiceRoll = Field(..., description="The initial roll result")
    original_roll: DiceRoll = Field(..., description="Immutable copy for audit trail")
    final_roll: Optional[DiceRoll] = Field(default=None, description="After handler modifications")

    # D20-specific context
    dc: Optional[int] = Field(default=None, description="Difficulty class if known")
    bonus: Optional[ModifiableValue] = Field(default=None, description="All modifiers applied")
    result: Optional[bool] = Field(default=None, description="Success/failure - set AFTER outcome")

    def replace_roll(self, new_roll: DiceRoll, handler_name: str, reason: str) -> None:
        """Replace the roll result. Handler helper method."""
        old_total = self.roll.total
        new_total = new_roll.total
        self.final_roll = new_roll
        self.add_modification(handler_name, f"{reason} ({old_total} → {new_total})")

    def get_effective_roll(self) -> DiceRoll:
        """Return final_roll if modified, otherwise original roll."""
        return self.final_roll if self.final_roll is not None else self.roll


class AttackD20RollResultEvent(D20RollResultEvent):
    """
    Event for attack d20 rolls.

    Additional context: weapon_slot for weapon-specific handlers.
    """
    event_type: EventType = Field(default=EventType.ATTACK_D20_ROLL_RESULT)
    roll_type: RollType = Field(default=RollType.ATTACK)

    # Attack-specific context
    weapon_slot: Optional[WeaponSlot] = Field(default=None, description="Weapon used for attack")


class SavingThrowD20RollResultEvent(D20RollResultEvent):
    """
    Event for saving throw d20 rolls.

    Additional context: ability_name for ability-specific handlers (e.g., Evasion for DEX saves).
    """
    event_type: EventType = Field(default=EventType.SAVE_D20_ROLL_RESULT)
    roll_type: RollType = Field(default=RollType.SAVE)

    # Save-specific context
    ability_name: AbilityName = Field(..., description="The ability being saved against")


class SkillCheckD20RollResultEvent(D20RollResultEvent):
    """
    Event for skill check d20 rolls.

    Additional context: skill_name for skill-specific handlers (e.g., Reliable Talent).
    """
    event_type: EventType = Field(default=EventType.CHECK_D20_ROLL_RESULT)
    roll_type: RollType = Field(default=RollType.CHECK)

    # Skill-specific context
    skill_name: SkillName = Field(..., description="The skill being checked")


# =============================================================================
# Damage Roll Result Event (for damage dice manipulation)
# =============================================================================

class DamageRollResultEvent(DiceRollResultEvent):
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
    name: str = Field(default="Damage Roll Result")
    event_type: EventType = Field(default=EventType.DAMAGE_ROLL_RESULT)
    roll_type: RollType = Field(default=RollType.DAMAGE)

    # Attack context (read-only)
    weapon_slot: WeaponSlot = Field(description="The weapon slot used for the attack")
    attack_outcome: AttackOutcome = Field(description="The outcome of the attack (HIT, CRIT, etc.)")
    damages: List[Damage] = Field(description="Damage specifications")

    # IMMUTABLE: Original rolls (never modified)
    original_rolls: List[DiceRoll] = Field(description="Original dice rolls before any modifications")

    # MUTABLE: Current best rolls (handlers replace with new versions)
    # Initialized to copy of original_rolls
    final_rolls: List[DiceRoll] = Field(description="Final dice rolls after handler modifications")

    # AUDIT: History of modifications (override parent's simpler format)
    roll_modifications: List[Tuple[str, int, int, int, str]] = Field(  # type: ignore[assignment]
        default_factory=list,
        description="Audit trail of roll modifications: (handler_name, roll_index, old_total, new_total, reason)"
    )

    def replace_roll(self, index: int, new_roll: DiceRoll, handler_name: str, reason: str) -> None:  # type: ignore[override]
        """Helper for handlers to replace a roll and track the change."""
        old_roll = self.final_rolls[index]
        self.roll_modifications.append((handler_name, index, old_roll.total, new_roll.total, reason))
        self.final_rolls[index] = new_roll


class HealRollResultEvent(DiceRollResultEvent):
    """
    Event fired after healing dice are rolled but before healing is applied.

    Mirrors DamageRollResultEvent pattern. Handlers can maximize or replace
    healing dice (e.g., Beacon of Hope maximizes all healing dice).
    """
    name: str = Field(default="Heal Roll Result")
    event_type: EventType = Field(default=EventType.HEAL_ROLL_RESULT)
    roll_type: RollType = Field(default=RollType.HEAL)

    # Context
    spell_name: str = Field(default="", description="Name of the healing spell")

    # IMMUTABLE: Original roll
    original_roll: DiceRoll = Field(description="Original healing dice roll before modifications")

    # MUTABLE: Current best roll (handlers replace)
    final_roll: DiceRoll = Field(description="Final healing dice roll after handler modifications")

    def replace_roll(self, new_roll: DiceRoll, handler_name: str, reason: str) -> None:  # type: ignore[override]
        """Helper for handlers to replace the healing roll and track the change."""
        self.roll_modifications.append((handler_name, reason))
        self.final_roll = new_roll
        self.modified = True


# =============================================================================
# DEPRECATED: DamageRolledEvent - Use DamageRollResultEvent instead
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
    - Tracking damage taken (e.g., rage maintenance - HasTakenDamage marker)
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

    # For frontend reducer — authoritative HP after damage applied
    resulting_hp: Optional[int] = Field(
        default=None,
        description="Entity HP after damage applied (set at EFFECT phase)"
    )

    def get_effective_damage(self) -> int:
        """Get the damage amount to apply (final_damage if set, else total_damage)."""
        return self.final_damage if self.final_damage is not None else self.total_damage

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for taking damage.

        Used for damage from zones, terrain, environmental effects, etc.
        Attack damage is logged by the attack event itself.
        """
        target_name = self.target_entity_name or "Unknown"
        source_name = self.source_entity_name or "terrain"  # Default to terrain for zone damage

        damage = self.get_effective_damage()

        # Get damage type from first damage entry, or default to "damage"
        damage_type_str = "damage"
        if self.damages:
            damage_type_str = str(self.damages[0].damage_type.value).lower()

        # Canceled damage (e.g., Shield blocks Magic Missile)
        if self.canceled:
            reason = self.status_message or "blocked"
            compact_text = f"{md_color(target_name, 'yellow')} takes {md_color('0', 'green')} {damage_type_str} ({reason})"
            return CombatLogEntry(
                entry_type=CombatLogEntryType.DAMAGE_TAKEN,
                source_name=source_name,
                source_uuid=str(self.source_entity_uuid) if self.source_entity_uuid else "",
                target_name=target_name,
                target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
                compact=compact_text,
                verbose=compact_text,
                detailed=compact_text,
                data={
                    "target_name": target_name,
                    "damage": 0,
                    "damage_type": damage_type_str,
                    "source_name": source_name,
                    "blocked": True,
                    "blocked_reason": reason,
                },
                success=False
            )

        # COMPACT: "Skeleton takes 5 piercing"
        compact_text = f"{md_color(target_name, 'yellow')} takes {md_color(str(damage), 'red')} {damage_type_str}"

        # VERBOSE: Add source
        verbose_text = f"{md_color(target_name, 'yellow')} takes {md_color(str(damage), 'red')} {damage_type_str}"
        if source_name and source_name != "terrain":
            verbose_text += f" from {md_color(source_name, 'cyan')}"

        # DETAILED: Add roll info if available
        detailed_text = verbose_text
        if self.damage_rolls:
            roll_strs = []
            for roll in self.damage_rolls:
                if roll.results:
                    roll_strs.append(f"{roll.results}")
            if roll_strs:
                detailed_text += f"\n  Rolls: {', '.join(roll_strs)}"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.DAMAGE_TAKEN,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid) if self.source_entity_uuid else "",
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data={
                "target_name": target_name,
                "damage": damage,
                "damage_type": damage_type_str,
                "source_name": source_name,
            },
            success=True
        )


# =============================================================================
# Heal Event
# =============================================================================

class HealEvent(Event):
    """Fired when an entity receives healing."""
    name: str = Field(default="Heal", description="Healing event")
    event_type: EventType = Field(default=EventType.HEAL)
    total_healing: int = Field(default=0, description="Healing amount requested")
    actual_healing: int = Field(default=0, description="Actual HP restored (after cap)")
    source_description: str = Field(default="", description="Description of healing source (e.g. 'Second Wind: d10(7)+1')")
    was_blocked: bool = Field(default=False, description="True if healing was blocked (e.g. Chill Touch)")
    spell_level: int = Field(default=0, description="Spell level used (0 = non-spell healing)")

    # For frontend reducer — authoritative HP after healing applied
    resulting_hp: Optional[int] = Field(
        default=None,
        description="Entity HP after healing applied (set at EFFECT phase)"
    )

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        target_name = self.target_entity_name or "Unknown"

        if self.was_blocked:
            text = f"{md_color(target_name, 'cyan')} healing blocked!"
            return CombatLogEntry(
                entry_type=CombatLogEntryType.HEAL,
                source_name=target_name,
                source_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
                compact=text,
                verbose=text,
                detailed=text,
                data=HealLogData(
                    entity_name=target_name,
                    entity_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
                    amount=0,
                    source_description=self.source_description
                ).model_dump(),
                success=False
            )

        amount = self.actual_healing
        compact = f"{md_color(target_name, 'cyan')} heals for {md_color(str(amount), 'green')} HP"
        verbose = compact
        if self.source_description:
            verbose = f"{compact} ({self.source_description})"
        detailed = verbose

        return CombatLogEntry(
            entry_type=CombatLogEntryType.HEAL,
            source_name=target_name,
            source_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
            compact=compact,
            verbose=verbose,
            detailed=detailed,
            data=HealLogData(
                entity_name=target_name,
                entity_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
                amount=amount,
                source_description=self.source_description
            ).model_dump(),
            success=True
        )


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

        # Turn start/end use the same format at all verbosity levels
        text = f"─── {md_color(entity_name, 'bold yellow')}'s turn ───"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.TURN_START,
            source_name=entity_name,
            source_uuid=str(self.entity_uuid),
            compact=text,
            verbose=text,
            detailed=text,
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

        # Turn end uses dimmer formatting
        text = f"─ {md_color(entity_name, 'dim')}'s turn ends ─"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.TURN_END,
            source_name=entity_name,
            source_uuid=str(self.entity_uuid),
            compact=text,
            verbose=text,
            detailed=text,
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
        # Death uses dramatic formatting
        compact_text = f"☠ {md_color(self.entity_name, 'bold red')} has been defeated!"
        verbose_text = compact_text
        detailed_text = f"☠ {md_color(self.entity_name, 'bold red')} has been defeated!"
        detailed_text += f"\n  Dropped to {self.final_hp} HP"
        if self.killer_name:
            detailed_text += f"\n  Killed by: {md_color(self.killer_name, 'cyan')}"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.DEATH,
            source_name=self.entity_name,
            source_uuid=str(self.entity_uuid),
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data={"entity_name": self.entity_name, "final_hp": self.final_hp},
            success=True
        )
