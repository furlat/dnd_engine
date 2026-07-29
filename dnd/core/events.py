"""Event contracts and dispatch registries for game-state changes.

The event layer represents declarations, execution, effects, completion, and
cancelation as versioned event objects. `EventQueue` stores each version,
dispatches matching handlers before completion, and exposes passive callbacks
for logs, sensory updates, and API streams.
"""

__all__ = [
    "EventType", "SpatialChangeType", "EventPhase", "RangeType", "MovementTrajectory",
    "AbilityName", "SkillName",
    "Event", "Trigger", "BaseHandler", "EventHandler", "SpatialHandler", "EventQueue",
    "SensoryUpdateReason", "SensoryUpdateEvent",
    "D20Event", "SavingThrowEvent", "SkillCheckEvent",
    "RollModificationOperation", "RollModification", "DiceRollResultEvent",
    "DamageRollPacket",
    "D20RollResultEvent",
    "AttackD20RollResultEvent",
    "SavingThrowD20RollResultEvent",
    "SkillCheckD20RollResultEvent",
    "DamageRollResultEvent",
    "SensesUpdateHint", "SpatialChangeEvent", "FireExposureEvent", "ExposedFlameEvent",
    "WindExposureEvent", "ForcedMovementEvent",
    "TakeDamageEvent", "DamageAppliedEvent",
    "Range", "Damage",
    "EncounterEvent", "EncounterStartEvent", "EncounterEndEvent",
    "RoundEvent", "RoundStartEvent", "RoundEndEvent",
    "TurnEvent", "TurnStartEvent", "TurnEndEvent",
    "LifeStateChangeEvent", "ReviveEvent",
    "DeathSaveEvent", "InstantDeathEvent", "DeathEvent",
]

from contextlib import contextmanager
from contextvars import ContextVar
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, PrivateAttr, field_serializer, model_validator
from typing import Literal as TypeLiteral, Union, List, Optional, Dict, Self, Literal, TypeVar, Protocol, runtime_checkable, Tuple, Any, Set, Iterator, Sequence, cast
from dnd.core.values import ModifiableValue

from dnd.core.combat_log import (
    CombatLogEntry,
    CombatLogEntryType, ModifierBreakdown, DiceRollDisplay,
    SavingThrowLogData, SkillCheckLogData, DamageTakenLogData, HealLogData,
    RollModificationLogData, RollModificationLogFact,
    md_color, md_d20_roll, md_breakdown, position_evidence_key
)
from dnd.core.content.runtime import (
    BehaviorBinding,
    EffectiveHandlerPresentation,
    HandlerDispatchEvidence,
    HandlerDispatchOutcome,
    RuntimeBehaviorKind,
    bind_runtime_handler_before_admission,
    runtime_behavior_provider,
)
from dnd.core.damage import DamageResolution
from dnd.core.effect_types import EffectOrigin
from dnd.core.life_types import LifeState, LifeStateChangeReason
from dnd.core.creature_types import DamageType
from dnd.core.saving_throw_types import SavingThrowContext
from dnd.core.senses import SenseMode
from dnd.core.equipment_types import WeaponSlot
from uuid import UUID, uuid4
from dnd.core.dice import Dice, DiceRoll, AttackOutcome, RollType
from datetime import UTC, datetime
from collections import defaultdict
from typing import Callable, Tuple
import logging
import time

from dnd.action_timing import action_timing_enabled, record_action_timing
from dnd.core.base_object import BaseObject

logger = logging.getLogger(__name__)

EventT = TypeVar('EventT', bound='Event')
E = TypeVar('E', bound='Event')

EventProcessor = Callable[[E, UUID], Optional[E]]


def _preserve_nullable_unique_array_schema(schema: Dict[str, Any]) -> None:
    """Retain set uniqueness metadata after a JSON-only list serializer."""
    schema["default"] = None
    for option in schema.get("anyOf", []):
        if isinstance(option, dict) and option.get("type") == "array":
            option["uniqueItems"] = True


class PreCompletionSystem(Protocol):
    """Dependency-neutral lifecycle system invoked for selected event types."""

    def __call__(self, event: 'Event') -> None: ...

    def reset(self) -> None: ...


@runtime_checkable
class EntityWithEventHandlers(Protocol):
    """Structural contract for blocks that own event-handler indexes.

    The event layer cannot import `Entity` or other owner types directly. This
    protocol lets handler cleanup remove block-local indexes without adding an
    upward dependency.
    """

    event_handlers: Dict[UUID, 'EventHandler']

    def remove_event_handler_from_dicts(self, event_handler: 'EventHandler') -> None:
        """Remove one handler from the owner's local lookup dictionaries.

        Args:
            event_handler: Handler being removed from the global queue.
        """
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


class EventType(str, Enum):
    """Kinds of state transitions that handlers and logs can subscribe to."""

    BASE_ACTION = "base_action"
    ATTACK = "attack"
    MOVEMENT = "movement"
    STEP_MOVEMENT = "step_movement"
    FORCED_MOVEMENT = "forced_movement"
    ABILITY_CHECK = "ability_check"
    SAVING_THROW = "saving_throw"
    SKILL_CHECK = "skill_check"
    INFLICT_DAMAGE = "inflicted_damage"
    TAKE_DAMAGE = "take_damage"
    DAMAGE_APPLIED = "damage_applied"
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
    ITEM_LOCATION_STATE = "item_location_state"
    ITEM_CHARGE_CONSUMPTION = "item_charge_consumption"

    TRIGGER_EVENT = "trigger_event"

    DICE_ROLL = "dice_roll"
    D20_ROLL_RESULT = "d20_roll_result"
    ATTACK_D20_ROLL_RESULT = "attack_d20_roll"
    SAVE_D20_ROLL_RESULT = "save_d20_roll"
    CHECK_D20_ROLL_RESULT = "check_d20_roll"
    DAMAGE_ROLL_RESULT = "damage_roll_result"
    HEAL_ROLL_RESULT = "heal_roll_result"
    ENEMY_SPOTTED = "enemy_spotted"
    ENEMY_KILLED = "enemy_killed"
    ENEMY_ENGAGED = "enemy_engaged"

    SPATIAL_ENTITY_ENTERED = "spatial_entity_entered"
    SPATIAL_ENTITY_LEFT = "spatial_entity_left"
    SPATIAL_TILE_CHANGED = "spatial_tile_changed"
    SPATIAL_OBJECT_PLACED = "spatial_object_placed"
    SPATIAL_OBJECT_REMOVED = "spatial_object_removed"
    SPATIAL_PERCEIVABILITY_CHANGED = "spatial_perceivability_changed"
    SPATIAL_LIGHT_CHANGED = "spatial_light_changed"
    SPATIAL_OBJECT_CHANGED = "spatial_object_changed"
    MOVEMENT_COLLISION = "movement_collision"
    SENSORY_UPDATE = "sensory_update"
    FIRE_EXPOSURE = "fire_exposure"
    EXPOSED_FLAME_IGNITED = "exposed_flame_ignited"
    WIND_EXPOSURE = "wind_exposure"

    ENCOUNTER_START = "encounter_start"
    ENCOUNTER_END = "encounter_end"
    ROUND_START = "round_start"
    ROUND_END = "round_end"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    LIFE_STATE_CHANGE = "life_state_change"
    REVIVE = "revive"
    DEATH_SAVE = "death_save"
    INSTANT_DEATH = "instant_death"
    DEATH = "death"


class MovementTrajectory(str, Enum):
    """Geometry used to present an ordered voluntary movement transition."""

    PATH = "path"
    DIRECT_ARC = "direct_arc"


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
    LIFE_STATE = "life_state"
    TURN_START = "turn_start"
    UNKNOWN = "unknown"


class EventPhase(str, Enum):
    """Lifecycle phase for one logical event lineage.

    `DECLARATION`, `EXECUTION`, and `EFFECT` are handler-visible phases.
    `COMPLETION` stores final lineage and combat-log data but does not dispatch
    event handlers. `CANCEL` records an aborted lineage.
    """

    DECLARATION = "declaration"
    EXECUTION = "execution"
    EFFECT = "effect"
    COMPLETION = "completion"
    CANCEL = "cancel"

ordered_event_phases = [EventPhase.DECLARATION, EventPhase.EXECUTION, EventPhase.EFFECT, EventPhase.COMPLETION]


class Event(BaseObject):
    """Versioned state-transition record.

    Each call to `post()` or `phase_to()` creates a new UUID while preserving
    `lineage_uuid`, allowing the queue to store both the current phase and the
    history of a logical event. Subclasses add domain-specific payload fields
    and may override `generate_combat_log()`.
    """

    name: str = Field(default="Event", description="Human-readable event label.")
    lineage_uuid: UUID = Field(
        default_factory=uuid4,
        description="Stable UUID shared by all phase versions of one logical event.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Creation time for this event version.",
    )
    event_type: EventType = Field(description="Dispatch category used by triggers and history indexes.")
    phase: EventPhase = Field(
        default=EventPhase.DECLARATION,
        description="Current lifecycle phase for this event version.",
    )
    source_entity_name: Optional[str] = Field(
        default=None,
        description="Display name of the acting entity, captured for log generation.",
    )
    target_entity_name: Optional[str] = Field(
        default=None,
        description="Display name of the target entity, captured for log generation.",
    )
    modified: bool = Field(
        default=False,
        description="Whether a handler or repost changed this event version.",
    )
    canceled: bool = Field(
        default=False,
        description="Whether this event lineage has been canceled before applying its effects.",
    )
    canceled_from_phase: Optional[EventPhase] = Field(
        default=None,
        description="Lifecycle phase from which cancellation terminated this event lineage.",
    )
    parent_event: Optional[UUID] = Field(
        default=None,
        description="UUID of the parent event version that caused this child event.",
    )
    turn_execution_id: Optional[UUID] = Field(
        default=None,
        description=(
            "Opaque identity of the actual encounter turn that caused this "
            "event; inherited by phased versions and child events."
        ),
    )
    status_message: Optional[str] = Field(
        default=None,
        description="Short status or cancellation reason attached to this event version.",
    )
    outcome_code: Optional[str] = Field(
        default=None,
        description="Stable machine-readable outcome identity attached by engine rules.",
    )
    outcome_source_entity_uuid: Optional[UUID] = Field(
        default=None,
        description="Entity responsible for the terminal outcome when distinct from the event source.",
    )
    is_first: bool = Field(
        default=True,
        description="Whether this is the first event at this phase in its lineage.",
    )
    is_last: bool = Field(
        default=True,
        description="Whether this is the last event at this phase in its lineage.",
    )
    lineage_children_events: List[UUID] = Field(
        default_factory=list,
        description="Child event UUIDs accumulated across this lineage's earlier phases.",
    )
    children_events: List[UUID] = Field(
        default_factory=list,
        description="Child event UUIDs attached during this event version's phase.",
    )
    parent_lineage: Optional[UUID] = Field(
        default=None,
        description="Stable lineage UUID of the parent, resolved during completion.",
    )
    children_lineages: List[UUID] = Field(
        default_factory=list,
        description="Stable child lineage UUIDs resolved during completion.",
    )
    combat_log: Optional[CombatLogEntry] = Field(
        default=None,
        exclude=True,
        description="Generated combat-log entry for completed events; excluded from model serialization.",
    )
    _effective_handler_presentations: tuple[
        EffectiveHandlerPresentation,
        ...,
    ] = PrivateAttr(default=())
    identified_entity_observer_uuids: Dict[str, Set[str]] = Field(
        default_factory=dict,
        exclude=True,
        description=(
            "Internal event-time identity grants keyed by participant UUID; "
            "values are observer UUIDs that identified that participant."
        ),
    )
    located_entity_observer_uuids: Dict[str, Set[str]] = Field(
        default_factory=dict,
        exclude=True,
        description=(
            "Internal event-time exact-location grants keyed by participant UUID; "
            "unlike identity grants these are recomputed at every event version."
        ),
    )
    located_position_observer_uuids: Dict[str, Set[str]] = Field(
        default_factory=dict,
        exclude=True,
        description=(
            "Internal event-time coordinate grants keyed by canonical x,y; "
            "used only when every carried coordinate has independent evidence."
        ),
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Generate a combat log entry for this event.

        Default implementation returns self.combat_log (pre-set if any).
        Subclasses that want combat log generation should override this method.

        Returns:
            CombatLogEntry if this event type supports combat logging, None otherwise.
        """
        return self.combat_log

    def get_effect_origin(self) -> Optional[EffectOrigin]:
        """Return neutral effect provenance when this event carries any."""
        return None

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Grid positions spatially relevant to this event.

        Returns only positions carried as fields. Entity-UUID-derived
        positions are added by the perceiver computer (which has GridMap access).
        Override in subclasses with explicit position fields.
        """
        return set()

    def get_participant_entity_uuids(self) -> Set[UUID]:
        """Return entity UUIDs that participate directly in this event.

        Returns:
            Source and target UUIDs when they identify registered entities.
        """
        return {
            entity_uuid
            for entity_uuid in (self.source_entity_uuid, self.target_entity_uuid)
            if entity_uuid is not None
        }

    def completion_position_observer_evidence(
        self,
        completion_locations: Dict[str, Set[str]],
    ) -> Dict[str, Set[str]]:
        """Return coordinate grants to freeze onto the completion version."""
        del completion_locations
        return {
            key: set(observer_uuids)
            for key, observer_uuids in self.located_position_observer_uuids.items()
        }

    def model_post_init(self, __context: Any) -> None:
        if self.turn_execution_id is None:
            parent = (
                EventQueue.get_event_by_uuid(self.parent_event)
                if self.parent_event is not None
                else None
            )
            self.turn_execution_id = (
                parent.turn_execution_id
                if parent is not None
                else EventQueue.current_turn_execution_id()
            )
        super().model_post_init(__context)
        if self.use_register:
            EventQueue.register(self)

    def set_target_entity(self, target_entity_uuid: UUID):
        """Set the target entity for the event.

        Args:
            target_entity_uuid: Entity UUID to store as the event target.
        """
        self.target_entity_uuid = target_entity_uuid

    def phase_to(self, new_phase: Optional[EventPhase] = None, status_message: Optional[str] = None, **updates) -> Self:
        """Create, post, and return a new event version at another phase.

        Completion resolves stable parent/child lineage metadata, generates
        combat logs, and invokes the top-level combat-log callback if present.

        Args:
            new_phase: Phase to transition to. When omitted, the next ordered
                phase is used.
            status_message: Optional message explaining the phase change.
            **updates: Additional model fields to apply to the new event version.

        Returns:
            The new event version after queue registration and handler dispatch.
        """
        if self.phase == EventPhase.COMPLETION:
            return self

        if new_phase is None:
            new_phase = ordered_event_phases[ordered_event_phases.index(self.phase) + 1]

        phase_updates = {}
        phase_updates['phase'] = new_phase
        if status_message is not None:
            phase_updates['status_message'] = status_message

        phase_updates.update(updates)

        if 'is_first' not in phase_updates:
            phase_updates['is_first'] = True
        if 'is_last' not in phase_updates:
            phase_updates['is_last'] = True

        if new_phase == EventPhase.COMPLETION:
            EventQueue.run_pre_completion_callbacks(self)
            if EventQueue._identified_entity_observer_computer is not None:
                phase_updates["located_entity_observer_uuids"] = {
                    entity_uuid: set(observer_uuids)
                    for entity_uuid, observer_uuids in (
                        EventQueue._identified_entity_observer_computer(self).items()
                    )
                }
            completion_locations = phase_updates.get(
                "located_entity_observer_uuids",
                self.located_entity_observer_uuids,
            )
            phase_updates["located_position_observer_uuids"] = (
                self.completion_position_observer_evidence(completion_locations)
            )

            all_children = list(dict.fromkeys(self.lineage_children_events + self.children_events))
            phase_updates['lineage_children_events'] = all_children
            phase_updates['children_events'] = all_children

            if self.parent_event:
                parent = EventQueue.get_event_by_uuid(self.parent_event)
                if parent:
                    phase_updates['parent_lineage'] = parent.lineage_uuid

            child_lineages: List[UUID] = []
            seen_lineages: Set[UUID] = set()
            for child_uuid in all_children:
                child = EventQueue.get_event_by_uuid(child_uuid)
                if child and child.lineage_uuid not in seen_lineages:
                    child_lineages.append(child.lineage_uuid)
                    seen_lineages.add(child.lineage_uuid)
            phase_updates['children_lineages'] = child_lineages
        else:
            phase_updates['lineage_children_events'] = self.lineage_children_events + self.children_events
            phase_updates['children_events'] = []

        if new_phase == EventPhase.COMPLETION:
            try:
                temp_event = self.model_copy(update=phase_updates)
                combat_log = temp_event.generate_combat_log()
                if combat_log is not None:
                    combat_log.identified_entity_observer_uuids = {
                        entity_uuid: set(observer_uuids)
                        for entity_uuid, observer_uuids in temp_event.identified_entity_observer_uuids.items()
                    }
                    combat_log.located_entity_observer_uuids = {
                        entity_uuid: set(observer_uuids)
                        for entity_uuid, observer_uuids in temp_event.located_entity_observer_uuids.items()
                    }
                    combat_log.located_position_observer_uuids = {
                        position: set(observer_uuids)
                        for position, observer_uuids in temp_event.located_position_observer_uuids.items()
                    }
                    if EventQueue._perceiver_computer:
                        combat_log.perceiver_uuids = EventQueue._perceiver_computer(temp_event)

                    child_logs = temp_event._collect_child_combat_logs()
                    if child_logs:
                        combat_log.sub_entries = child_logs
                        for child_log in child_logs:
                            combat_log.perceiver_uuids |= child_log.perceiver_uuids
                            combat_log.revealed_entity_uuids |= child_log.revealed_entity_uuids
                            for entity_uuid, observer_uuids in child_log.identified_entity_observer_uuids.items():
                                combat_log.identified_entity_observer_uuids.setdefault(entity_uuid, set()).update(
                                    observer_uuids
                                )
                        _enrich_multi_entity_log_from_children(combat_log, child_logs)

                    if EventQueue._revealed_computer:
                        combat_log.revealed_entity_uuids |= EventQueue._revealed_computer(temp_event, child_logs or [])

                    phase_updates['combat_log'] = combat_log

                    if self.parent_event is None and EventQueue._combat_log_callback:
                        final_event = self.model_copy(update=phase_updates)
                        EventQueue._combat_log_callback(final_event)
            except Exception:
                logger.exception(
                    "Combat-log projection failed for %s event %s at phase %s",
                    type(self).__name__,
                    self.uuid,
                    new_phase,
                )

        return self.post(**phase_updates)

    def cancel(self, status_message: Optional[str] = None, **updates) -> Self:
        """Mark this event as canceled and post the cancel version.

        Args:
            status_message: Optional message explaining why the event was canceled.
            **updates: Additional model fields to apply to the cancel version.

        Returns:
            The cancel event version after queue registration.
        """
        cancel_updates = {}
        cancel_updates['canceled'] = True
        cancel_updates['phase'] = EventPhase.CANCEL
        cancel_updates['canceled_from_phase'] = self.canceled_from_phase or self.phase
        if status_message is not None:
            cancel_updates['status_message'] = status_message

        cancel_updates.update(updates)
        return self.post(**cancel_updates)

    def add_child_event(self, child_event: 'Event'):
        """Add a child event to current-phase and lineage-level child lists.

        Args:
            child_event: Event version caused by this event.
        """
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
                    result.append(lineage_events[-1])
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
                return events[-1]
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
            for lineage_id in self.children_lineages:
                events = EventQueue._events_by_lineage.get(lineage_id, [])
                found_log = False
                for ev in reversed(events):
                    if ev.combat_log:
                        child_logs.append(ev.combat_log)
                        found_log = True
                        break
                if not found_log and events:
                    child_logs.extend(events[-1]._collect_child_combat_logs())
        else:
            seen_lineages: Set[UUID] = set()
            for child_uuid in self.lineage_children_events:
                child = EventQueue.get_event_by_uuid(child_uuid)
                if child is None or child.lineage_uuid in seen_lineages:
                    continue
                seen_lineages.add(child.lineage_uuid)
                lineage_events = EventQueue._events_by_lineage.get(child.lineage_uuid, [])
                logged_event = next(
                    (candidate for candidate in reversed(lineage_events) if candidate.combat_log),
                    None,
                )
                if logged_event is not None:
                    logged_combat_log = logged_event.combat_log
                    if logged_combat_log is not None:
                        child_logs.append(logged_combat_log)
                elif lineage_events:
                    child_logs.extend(lineage_events[-1]._collect_child_combat_logs())
        return child_logs

    @property
    def effective_handler_presentations(
        self,
    ) -> tuple[EffectiveHandlerPresentation, ...]:
        """Return exact reaction evidence retained across this event lineage."""
        return self._effective_handler_presentations

    def post(self, **updates) -> Self:
        """Create a modified version of this event and rebroadcast it.

        The new version receives a fresh UUID and timestamp while preserving
        the logical lineage unless `lineage_uuid` is explicitly supplied.

        Args:
            **updates: Model fields to override on the new event version.

        Returns:
            The new event version after queue registration and handler dispatch.
        """
        updates['modified'] = True
        updates['timestamp'] = datetime.now(UTC)
        updates['uuid'] = uuid4()
        if 'lineage_uuid' not in updates:
            updates['lineage_uuid'] = self.lineage_uuid

        updated_event = self.model_copy(update=updates)

        if updated_event.use_register:
            result = EventQueue.register(updated_event)
        else:
            result = updated_event

        if not isinstance(result, self.__class__):
            raise TypeError(f"Expected {self.__class__.__name__} but got {result.__class__.__name__}")

        return result

    def with_updates(
        self,
        *,
        status_message: Optional[str] = None,
        **updates: Any,
    ) -> Self:
        """Return an unposted modified event value.

        Validation pipelines use this method to carry accepted facts to the
        next validator without re-dispatching handlers for the current phase.
        Publishing and lifecycle advancement remain explicit through
        :meth:`post` and :meth:`phase_to`.
        """
        updates["modified"] = True
        if status_message is not None:
            updates["status_message"] = status_message
        return self.model_copy(update=updates)


def _enrich_multi_entity_log_from_children(
    combat_log: CombatLogEntry,
    child_logs: List[CombatLogEntry],
) -> None:
    """Fill parent multi-target summary data from child combat logs.

    Args:
        combat_log: Parent combat-log entry generated by a multi-target action.
        child_logs: Direct child logs produced by individual target effects.
    """
    if combat_log.entry_type != CombatLogEntryType.MULTI_ENTITY_ACTION:
        return

    data = dict(combat_log.data)
    target_logs = _multi_entity_target_logs(child_logs, data.get("total_targets"))
    target_names = _unique_nonempty([child.target_name for child in target_logs])

    per_target_damage: List[int] = []
    per_target_logs: List[Optional[Dict[str, Any]]] = []
    saves_succeeded = 0
    saves_failed = 0

    for child in target_logs:
        child_data = dict(child.data)
        per_target_logs.append(child_data if child_data else None)
        damage = _damage_from_log_data(child_data)
        if damage is not None:
            per_target_damage.append(damage)
        if child.entry_type == CombatLogEntryType.SPELL_SAVE:
            if bool(child_data.get("save_success")):
                saves_succeeded += 1
            else:
                saves_failed += 1

    if target_names:
        data["target_names"] = target_names
    if per_target_damage:
        data["per_target_damage"] = per_target_damage
        data["total_damage"] = sum(per_target_damage)
    if per_target_logs:
        data["per_target_logs"] = per_target_logs
    data["saves_succeeded"] = saves_succeeded
    data["saves_failed"] = saves_failed
    combat_log.data = data


def _multi_entity_target_logs(
    child_logs: Sequence[CombatLogEntry],
    total_targets: Any,
) -> List[CombatLogEntry]:
    """Return direct children that represent target applications.

    Auxiliary causal children such as condition cleanup remain nested in the
    parent log, but they must not become action targets or per-target results.

    Args:
        child_logs: Direct causal children collected from the parent event.
        total_targets: Declared number of target applications on the parent.

    Returns:
        Ordered target-effect logs, bounded by the declared application count.
    """
    target_entry_types = {
        CombatLogEntryType.ACTION,
        CombatLogEntryType.ATTACK,
        CombatLogEntryType.HEAL,
        CombatLogEntryType.SPELL_DAMAGE,
        CombatLogEntryType.SPELL_SAVE,
    }
    candidates = [
        child
        for child in child_logs
        if child.entry_type in target_entry_types and child.target_uuid is not None
    ]
    if isinstance(total_targets, int) and not isinstance(total_targets, bool) and total_targets >= 0:
        return candidates[:total_targets]
    return candidates


def _unique_nonempty(values: Sequence[Optional[str]]) -> List[str]:
    """Return non-empty strings in first-seen order."""
    out: List[str] = []
    seen: Set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        out.append(value)
        seen.add(value)
    return out


def _damage_from_log_data(data: Dict[str, Any]) -> Optional[int]:
    """Extract the main damage total from a child combat-log payload."""
    for key in ("final_damage", "total_damage", "damage"):
        value = data.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    return None


class Trigger(BaseModel):
    """Hashable event-matching predicate used by `EventHandler`."""

    name: str = Field(default="Trigger", description="Human-readable trigger label.")
    event_type: EventType = Field(description="Event category that must match.")
    event_phase: EventPhase = Field(description="Event lifecycle phase that must match.")
    event_source_entity_uuid: Optional[UUID] = Field(
        default=None,
        description="Optional source-entity filter; absent means any source.",
    )
    event_target_entity_uuid: Optional[UUID] = Field(
        default=None,
        description="Optional target-entity filter; absent means any target.",
    )

    model_config = ConfigDict(frozen=True)

    def __hash__(self):
        """Return a stable hash for queue indexes."""
        return hash((self.event_type, self.event_phase,
                    self.event_source_entity_uuid,
                    self.event_target_entity_uuid))

    def __eq__(self, other):
        """Return whether another object matches this trigger exactly."""
        if not isinstance(other, Trigger):
            return False
        return (self.event_type == other.event_type and
                self.event_phase == other.event_phase and
                self.event_source_entity_uuid == other.event_source_entity_uuid and
                self.event_target_entity_uuid == other.event_target_entity_uuid)

    def __call__(self, event: Event) -> bool:
        """Return whether an event satisfies this trigger.

        Args:
            event: Event version to test.

        Returns:
            True when event type, phase, and optional source/target filters
            match. A true match does not imply the handler will modify the event.
        """
        if event.event_type == self.event_type and event.phase == self.event_phase:
            if self.event_source_entity_uuid  and event.source_entity_uuid != self.event_source_entity_uuid:
                return False
            if self.event_target_entity_uuid and event.target_entity_uuid != self.event_target_entity_uuid:
                return False
            return True
        return False

    def is_simple(self) -> bool:
        """Return True when the trigger has no source or target filters."""
        return self.event_source_entity_uuid is None and self.event_target_entity_uuid is None

    def get_simple_trigger(self) -> 'Trigger':
        """Return a trigger that keeps only event type and phase."""
        return Trigger(event_type=self.event_type, event_phase=self.event_phase)

class BaseHandler(BaseObject):
    """Shared callable wrapper for event and spatial handlers.

    A handler stores the processor callable, the owning source entity, and
    toggle/cleanup metadata. Subclasses decide how the queue discovers them.
    """

    name: str = Field(default="BaseHandler", description="Human-readable handler label.")
    semantic_key: Optional[str] = Field(
        default=None,
        description="Stable rules-content identity; defaults to the processor's code identity.",
    )
    behavior_binding: Optional[BehaviorBinding] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Validated runtime content binding installed once before queue "
            "admission."
        ),
    )
    content_kind: RuntimeBehaviorKind = Field(
        default=RuntimeBehaviorKind.UNCLASSIFIED,
        description="Rules-content family used by evaluation and developer tooling.",
    )
    event_processor: EventProcessor = Field(
        exclude=True,
        description="Callable that may inspect, replace, cancel, or ignore a matching event.",
    )
    enabled: bool = Field(
        default=True,
        description="Whether queue dispatch should invoke this handler.",
    )
    player_toggleable: bool = Field(
        default=False,
        description="Whether player-facing controls may enable or disable this handler.",
    )
    validation_only: bool = Field(
        default=False,
        description=(
            "Whether this handler is a pure transactional validator. Validation-only "
            "handlers may inspect, modify, or cancel an unpublished proposal, but must "
            "not mutate engine state or emit events."
        ),
    )
    owner_block: Optional[EntityWithEventHandlers] = Field(
        default=None,
        exclude=True,
        description="Block that registered this handler, used to clean block-local handler indexes."
    )

    def get_semantic_key(self) -> str:
        """Return an explicit/bound key or an explicit unbound diagnostic."""
        if self.semantic_key:
            return self.semantic_key
        if self.behavior_binding is not None:
            return self.behavior_binding.definition_ref.identity_key
        module = getattr(self.event_processor, "__module__", type(self.event_processor).__module__)
        qualname = getattr(self.event_processor, "__qualname__", type(self.event_processor).__qualname__)
        code_identity = f"{module}.{qualname}".replace(".<locals>.", ".")
        return f"unbound:{code_identity}"

    def __call__(self, event: Event, source_entity_uuid: Optional[UUID] = None) -> Optional[Event]:
        """Execute the stored event processor if this handler is enabled.

        Args:
            event: Event version being dispatched.
            source_entity_uuid: Source UUID supplied by the queue. Defaults to
                the handler's own source.

        Returns:
            A modified/canceled event, the same event, or None for no change.
        """
        if not self.enabled:
            return None
        if source_entity_uuid is None:
            source_entity_uuid = self.source_entity_uuid
        return self.event_processor(event, source_entity_uuid)

class EventHandler(BaseHandler):
    """Trigger-indexed handler for non-position-specific event reactions.

    Empty `trigger_conditions` means the handler fires whenever code calls it
    directly. Queue discovery uses populated triggers.
    """

    name: str = Field(default="EventHandler", description="Human-readable event-handler label.")
    trigger_conditions: List[Trigger] = Field(
        default_factory=list,
        description="Predicates that make the queue dispatch this handler.",
    )

    def __call__(self, event: Event, source_entity_uuid: Optional[UUID] = None) -> Optional[Event]:
        """Execute the processor when enabled and at least one trigger matches.

        Args:
            event: Event version being dispatched.
            source_entity_uuid: Source UUID supplied by the queue. Defaults to
                the handler's own source.

        Returns:
            A modified/canceled event, the same event, or None for no change.
        """
        if not self.enabled:
            return None
        if source_entity_uuid is None:
            source_entity_uuid = self.source_entity_uuid
        if not self.trigger_conditions or any(trigger(event) for trigger in self.trigger_conditions):
            return self.event_processor(event, source_entity_uuid)
        return None

    def remove(self) -> bool:
        """Remove this handler from queue and owner-local indexes.

        Returns:
            True when the handler was present in the global queue.
        """
        if self.uuid not in EventQueue._event_handlers:
            return False
        EventQueue.remove_event_handler(self)
        owner = self.owner_block
        if owner is not None and isinstance(owner, EntityWithEventHandlers):
            if self.uuid in owner.event_handlers:
                owner.remove_event_handler_from_dicts(self)
            return True

        entity = BaseObject.get(self.source_entity_uuid)

        if entity is not None and isinstance(entity, EntityWithEventHandlers):
            if self.uuid in entity.event_handlers:
                entity.remove_event_handler_from_dicts(self)

        return True


class SpatialHandler(BaseHandler):
    """Position-indexed handler for spatial events.

    Zone spells and terrain effects use this type when only specific cells
    should dispatch the handler. The queue stores these in spatial indexes
    rather than trigger indexes.
    """

    name: str = Field(default="SpatialHandler", description="Human-readable spatial-handler label.")
    positions: Set[Tuple[int, int]] = Field(
        default_factory=set,
        description="Grid positions where this handler is indexed.",
    )
    event_type: EventType = Field(
        default=EventType.SPATIAL_ENTITY_ENTERED,
        description="Spatial event category this handler receives.",
    )
    event_phase: EventPhase = Field(
        default=EventPhase.EFFECT,
        description="Spatial event phase this handler receives.",
    )

    def __call__(self, event: Event, source_entity_uuid: Optional[UUID] = None) -> Optional[Event]:
        """Execute the processor after position-index lookup has matched.

        Args:
            event: Spatial event version being dispatched.
            source_entity_uuid: Source UUID supplied by the queue. Defaults to
                the handler's own source.

        Returns:
            A modified/canceled event, the same event, or None for no change.
        """
        if not self.enabled:
            return None
        if source_entity_uuid is None:
            source_entity_uuid = self.source_entity_uuid
        return self.event_processor(event, source_entity_uuid)

    def remove(self) -> bool:
        """Remove this handler from all spatial queue indexes."""
        return EventQueue.remove_spatial_handler(self.uuid)

class EventQueue:
    """Global event store and handler dispatcher.

    The queue keeps independent indexes for event history, trigger-based
    handlers, position-indexed spatial handlers, passive callbacks, and
    completion-time log helpers. It is intentionally class-scoped because the
    engine currently has one active event stream per process.
    """

    _events_by_lineage: Dict[UUID, List[Event]] = defaultdict(list)
    _events_by_uuid: Dict[UUID, Event] = {}
    _events_by_type: Dict[EventType, List[Event]] = defaultdict(list)
    _events_by_timestamp: Dict[datetime, List[Event]] = defaultdict(list)
    _events_by_phase: Dict[EventPhase, List[Event]] = defaultdict(list)
    _events_by_source: Dict[UUID, List[Event]] = defaultdict(list)
    _events_by_target: Dict[UUID, List[Event]] = defaultdict(list)
    _all_events: List[Event] = []
    _generation_uuid: UUID = uuid4()
    _active_turn_execution_id: Optional[UUID] = None

    _event_handlers: Dict[UUID, 'EventHandler'] = {}
    _event_handlers_by_trigger: Dict[Trigger, List['EventHandler']] = defaultdict(list)
    _event_handlers_by_simple_trigger: Dict[Trigger, List['EventHandler']] = defaultdict(list)
    _event_handlers_by_source_entity_uuid: Dict[UUID, List['EventHandler']] = defaultdict(list)

    _spatial_handlers: Dict[UUID, 'SpatialHandler'] = {}
    _spatial_handlers_by_position: Dict[
        Tuple[EventType, EventPhase],
        Dict[Tuple[int, int], List['BaseHandler']]
    ] = defaultdict(lambda: defaultdict(list))
    _spatial_handlers_by_source_entity_uuid: Dict[UUID, List['SpatialHandler']] = defaultdict(list)
    _handler_positions: Dict[UUID, Tuple[Tuple[EventType, EventPhase], Set[Tuple[int, int]]]] = {}

    _on_event_callbacks: List[Callable[['Event'], None]] = []
    _on_event_callback_filters: Dict[
        Callable[['Event'], None],
        Tuple[Optional[frozenset[EventType]], Optional[frozenset[EventPhase]]],
    ] = {}
    _on_event_sequence_callbacks: List[
        Callable[[Sequence['Event']], None]
    ] = []
    _on_event_sequence_callback_filters: Dict[
        Callable[[Sequence['Event']], None],
        Tuple[Optional[frozenset[EventType]], Optional[frozenset[EventPhase]]],
    ] = {}
    _on_event_batch_callbacks: List[Callable[[Sequence['Event']], None]] = []
    _on_handler_dispatch_callbacks: List[Callable[[HandlerDispatchEvidence], None]] = []
    _handler_dispatch_cursor: int = 0
    _event_batch_depth: ContextVar[int] = ContextVar(
        "event_queue_batch_depth",
        default=0,
    )
    _pending_event_batch: ContextVar[Optional[List['Event']]] = ContextVar(
        "event_queue_pending_batch",
        default=None,
    )
    _preflight_depth: ContextVar[int] = ContextVar(
        "event_queue_preflight_depth",
        default=0,
    )
    _pre_completion_callbacks: List[Callable[['Event'], None]] = []
    _pre_completion_systems: Dict[str, PreCompletionSystem] = {}
    _pre_completion_systems_by_event_type: Dict[
        EventType,
        Dict[str, PreCompletionSystem],
    ] = defaultdict(dict)
    _pre_completion_running: Set[UUID] = set()
    _combat_log_callback: Optional[Callable[['Event'], None]] = None
    _perceiver_computer: Optional[Callable[['Event'], Set[str]]] = None
    _revealed_computer: Optional[Callable[['Event', List['CombatLogEntry']], Set[str]]] = None
    _identified_entity_observer_computer: Optional[Callable[['Event'], Dict[str, Set[str]]]] = None

    @classmethod
    def begin_turn_execution(cls, execution_id: Optional[UUID] = None) -> UUID:
        """Open one causal encounter-turn scope and return its opaque identity."""
        active = cls._active_turn_execution_id
        if active is not None:
            raise RuntimeError("A turn execution is already active")
        resolved = execution_id or uuid4()
        cls._active_turn_execution_id = resolved
        return resolved

    @classmethod
    def current_turn_execution_id(cls) -> Optional[UUID]:
        """Return the causal identity of the active encounter turn, if any."""
        return cls._active_turn_execution_id

    @classmethod
    def end_turn_execution(cls, execution_id: UUID) -> None:
        """Close the matching causal encounter-turn scope."""
        active = cls._active_turn_execution_id
        if active != execution_id:
            raise RuntimeError("Cannot close a different turn execution")
        cls._active_turn_execution_id = None

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
    def set_identified_entity_observer_computer(
        cls,
        func: Optional[Callable[['Event'], Dict[str, Set[str]]]],
    ) -> None:
        """Register the event-time participant identity provider.

        The provider runs before an event version is stored or dispatched. Its
        grants remain immutable for each participant across later phases, so
        effects such as death cannot erase identity that an observer already
        possessed when the event began.

        Args:
            func: Callback returning participant UUID keys and the observer
                UUIDs that currently identify each participant.
        """
        cls._identified_entity_observer_computer = func

    @classmethod
    def push_combat_log(cls, entry: 'CombatLogEntry', source_entity_uuid: UUID) -> None:
        """Push a standalone combat log entry to the encounter.

        Used for informational logs (like "entity spotted") that don't correspond
        to a normal event lifecycle. Creates a lightweight Event just to carry the
        combat_log to the callback.
        """
        if cls._preflight_depth.get() > 0:
            raise RuntimeError("Validation-only handlers cannot publish combat logs during preflight")
        if cls._combat_log_callback is None:
            return
        event = Event(
            source_entity_uuid=source_entity_uuid,
            event_type=EventType.CONDITION_APPLICATION,
            phase=EventPhase.COMPLETION,
            use_register=False,
            combat_log=entry,
            context={"combat_log_origin": "standalone"},
        )
        cls._combat_log_callback(event)

    @classmethod
    def add_on_event_callback(
        cls,
        callback: Callable[['Event'], None],
        *,
        event_types: Optional[Set[EventType]] = None,
        phases: Optional[Set[EventPhase]] = None,
    ) -> None:
        """Add a passive callback that fires after event storage.

        Unlike EventHandlers, these callbacks:
        - Cannot modify or cancel events
        - Are for passive monitoring (logging, websocket broadcast, etc.)

        Args:
            callback: Passive observer invoked after storage.
            event_types: Optional event-type filter. Omit for every type.
            phases: Optional phase filter. Omit for every phase.
        """
        if callback not in cls._on_event_callbacks:
            cls._on_event_callbacks.append(callback)
        cls._on_event_callback_filters[callback] = (
            frozenset(event_types) if event_types is not None else None,
            frozenset(phases) if phases is not None else None,
        )

    @classmethod
    def add_on_handler_dispatch_callback(
        cls,
        callback: Callable[[HandlerDispatchEvidence], None],
    ) -> None:
        """Add a passive observer for matched handler invocations.

        Dispatch observers run after the handler and cannot replace or cancel
        its result. Observer failures are isolated from engine execution.

        Args:
            callback: Observer receiving immutable dispatch evidence.
        """
        if callback not in cls._on_handler_dispatch_callbacks:
            cls._on_handler_dispatch_callbacks.append(callback)

    @classmethod
    def remove_on_handler_dispatch_callback(
        cls,
        callback: Callable[[HandlerDispatchEvidence], None],
    ) -> None:
        """Remove a previously registered handler-dispatch observer."""
        if callback in cls._on_handler_dispatch_callbacks:
            cls._on_handler_dispatch_callbacks.remove(callback)

    @classmethod
    def _invoke_handler(cls, handler: BaseHandler, event: Event) -> Optional[Event]:
        """Invoke one matched handler and publish passive effect evidence."""
        before_cursor = cls.event_cursor()
        before_event_index = len(cls._all_events)
        with runtime_behavior_provider(handler):
            result = handler(event)
        emitted_event_count = cls.event_cursor() - before_cursor
        result_changed = result is not None and result != event
        if result_changed and result is not None and result.canceled:
            outcome = HandlerDispatchOutcome.CANCELED_EVENT
        elif result_changed and result is not None and result.modified:
            outcome = HandlerDispatchOutcome.MODIFIED_EVENT
        elif emitted_event_count:
            outcome = HandlerDispatchOutcome.EMITTED_EVENTS
        else:
            outcome = HandlerDispatchOutcome.NO_EFFECT
        evidence = HandlerDispatchEvidence(
            dispatch_index=cls._handler_dispatch_cursor,
            handler_semantic_key=handler.get_semantic_key(),
            handler_name=handler.name,
            content_kind=handler.content_kind,
            handler_uuid=str(handler.uuid),
            source_entity_uuid=str(handler.source_entity_uuid) if handler.source_entity_uuid else None,
            event_uuid=str(event.uuid),
            lineage_uuid=str(event.lineage_uuid),
            event_type=event.event_type.value,
            event_phase=event.phase.value,
            outcome=outcome,
            emitted_event_count=emitted_event_count,
        )
        binding = handler.behavior_binding
        if (
            result is not None
            and evidence.effected
            and handler.content_kind is RuntimeBehaviorKind.REACTION
            and isinstance(binding, BehaviorBinding)
        ):
            emitted_lineages = tuple(dict.fromkeys(
                emitted.lineage_uuid
                for emitted in cls._all_events[before_event_index:]
            ))
            result._effective_handler_presentations = (
                *result.effective_handler_presentations,
                EffectiveHandlerPresentation(
                    dispatch_index=evidence.dispatch_index,
                    handler_name=handler.name,
                    behavior_binding=binding,
                    source_entity_uuid=handler.source_entity_uuid,
                    triggering_event_uuid=event.uuid,
                    triggering_lineage_uuid=event.lineage_uuid,
                    emitted_lineage_uuids=emitted_lineages,
                    outcome=evidence.outcome,
                ),
            )
        cls._handler_dispatch_cursor += 1
        for callback in tuple(cls._on_handler_dispatch_callbacks):
            try:
                callback(evidence)
            except Exception:
                logger.exception(
                    "Passive handler-dispatch observer %s failed",
                    cls._timing_callback_name(callback),
                )
        return result

    @classmethod
    def remove_on_event_callback(cls, callback: Callable[['Event'], None]) -> None:
        """Remove an event callback."""
        if callback in cls._on_event_callbacks:
            cls._on_event_callbacks.remove(callback)
        cls._on_event_callback_filters.pop(callback, None)

    @classmethod
    def add_on_event_sequence_callback(
        cls,
        callback: Callable[[Sequence['Event']], None],
        *,
        event_types: Optional[Set[EventType]] = None,
        phases: Optional[Set[EventPhase]] = None,
    ) -> None:
        """Add a callback for one atomic sequence of stored event versions.

        Args:
            callback: Passive observer receiving events in storage order.
            event_types: Optional event-type filter. Omit for every type.
            phases: Optional phase filter. Omit for every phase.
        """
        if callback not in cls._on_event_sequence_callbacks:
            cls._on_event_sequence_callbacks.append(callback)
        cls._on_event_sequence_callback_filters[callback] = (
            frozenset(event_types) if event_types is not None else None,
            frozenset(phases) if phases is not None else None,
        )

    @classmethod
    def remove_on_event_sequence_callback(
        cls,
        callback: Callable[[Sequence['Event']], None],
    ) -> None:
        """Remove an event-sequence callback.

        Args:
            callback: Previously registered sequence observer.
        """
        if callback in cls._on_event_sequence_callbacks:
            cls._on_event_sequence_callbacks.remove(callback)
        cls._on_event_sequence_callback_filters.pop(callback, None)

    @classmethod
    def _dispatch_event_sequence(cls, events: Sequence['Event']) -> None:
        """Notify passive observers of one atomic stored sequence."""
        timing = action_timing_enabled()
        total_started = time.perf_counter() if timing else 0.0
        for callback in list(cls._on_event_sequence_callbacks):
            event_types, phases = cls._on_event_sequence_callback_filters.get(
                callback,
                (None, None),
            )
            if event_types is not None and not any(
                event.event_type in event_types for event in events
            ):
                continue
            if phases is not None and not any(event.phase in phases for event in events):
                continue
            callback_started = time.perf_counter() if timing else 0.0
            try:
                callback(events)
            except Exception:
                logger.exception(
                    "Passive event-sequence observer %s failed",
                    cls._timing_callback_name(callback),
                )
            finally:
                if timing:
                    callback_name = cls._timing_callback_name(callback)
                    record_action_timing(
                        f"event_queue.sequence.callback.{callback_name}_ms",
                        callback_started,
                    )
        if timing:
            record_action_timing("event_queue.sequence.callbacks_ms", total_started)

    @classmethod
    def add_on_event_batch_callback(
        cls,
        callback: Callable[[Sequence['Event']], None],
    ) -> None:
        """Add a passive callback that receives one completed causal batch.

        Events registered outside an explicit batch are delivered as a
        one-event sequence. Nested action applications share the outer action's
        batch, preserving authoritative storage order across reactions and
        child actions.

        Args:
            callback: Passive observer invoked after the batch boundary.
        """
        if callback not in cls._on_event_batch_callbacks:
            cls._on_event_batch_callbacks.append(callback)

    @classmethod
    def remove_on_event_batch_callback(
        cls,
        callback: Callable[[Sequence['Event']], None],
    ) -> None:
        """Remove a passive causal-batch callback.

        Args:
            callback: Previously registered batch observer.
        """
        if callback in cls._on_event_batch_callbacks:
            cls._on_event_batch_callbacks.remove(callback)

    @classmethod
    def is_event_batch_active(cls) -> bool:
        """Return whether the current context is inside a causal event batch."""
        return cls._event_batch_depth.get() > 0

    @classmethod
    @contextmanager
    def batch_on_event_callbacks(cls) -> Iterator[None]:
        """Collect passive batch notifications until the outer action closes.

        Immediate per-event callbacks and event handlers are unaffected. Only
        observers registered through `add_on_event_batch_callback` are delayed.
        Nested scopes append to the same ordered batch and only the outermost
        scope dispatches it.

        Yields:
            Control while event registrations append to the current batch.
        """
        depth = cls._event_batch_depth.get()
        pending_token = None
        if depth == 0:
            pending_token = cls._pending_event_batch.set([])
        depth_token = cls._event_batch_depth.set(depth + 1)
        try:
            yield
        finally:
            cls._event_batch_depth.reset(depth_token)
            if depth == 0:
                pending = tuple(cls._pending_event_batch.get() or ())
                if pending_token is not None:
                    cls._pending_event_batch.reset(pending_token)
                if pending:
                    cls._dispatch_event_batch(pending)

    @classmethod
    def _dispatch_event_batch(cls, events: Sequence['Event']) -> None:
        """Notify passive batch observers without affecting engine execution."""
        timing = action_timing_enabled()
        total_started = time.perf_counter() if timing else 0.0
        for callback in list(cls._on_event_batch_callbacks):
            callback_started = time.perf_counter() if timing else 0.0
            try:
                callback(events)
            except Exception:
                logger.exception(
                    "Passive event-batch observer %s failed",
                    cls._timing_callback_name(callback),
                )
            finally:
                if timing:
                    callback_name = cls._timing_callback_name(callback)
                    record_action_timing(
                        f"event_queue.batch.callback.{callback_name}_ms",
                        callback_started,
                    )
        if timing:
            record_action_timing("event_queue.batch.callbacks_ms", total_started)

    @classmethod
    def event_cursor(cls) -> int:
        """Return the raw append cursor for the event stream."""
        return len(cls._all_events)

    @classmethod
    def generation_id(cls) -> UUID:
        """Return the identity of the current event-history generation.

        Cursors are meaningful only within one generation. `reset()` creates a
        new identity so reconnecting clients can never confuse events from a
        previous game with events at the same numeric cursor in the new game.
        """
        return cls._generation_uuid

    @classmethod
    def iter_events_since(cls, since: int) -> Iterator[Tuple[int, 'Event']]:
        """Yield raw events with their zero-based event-stream indexes."""
        start = max(0, since)
        for index in range(start, len(cls._all_events)):
            yield index, cls._all_events[index]

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
    def add_pre_completion_system(
        cls,
        name: str,
        system: PreCompletionSystem,
        event_types: Set[EventType],
    ) -> None:
        """Register one indexed lifecycle system for selected event types.

        Args:
            name: Stable registry identity for replacement and removal.
            system: Callable lifecycle system with explicit reset behavior.
            event_types: Event categories that can affect the system.
        """
        cls.remove_pre_completion_system(name)
        cls._pre_completion_systems[name] = system
        for event_type in event_types:
            cls._pre_completion_systems_by_event_type[event_type][name] = system

    @classmethod
    def remove_pre_completion_system(cls, name: str) -> None:
        """Remove an indexed lifecycle system from every event-type registry."""
        system = cls._pre_completion_systems.pop(name, None)
        if system is None:
            return
        for event_type, systems in tuple(cls._pre_completion_systems_by_event_type.items()):
            systems.pop(name, None)
            if not systems:
                cls._pre_completion_systems_by_event_type.pop(event_type, None)

    @classmethod
    def run_pre_completion_callbacks(cls, event: Event) -> None:
        """Run lifecycle systems before an event completes."""
        if event.event_type == EventType.SENSORY_UPDATE:
            return
        if event.uuid in cls._pre_completion_running:
            return
        cls._pre_completion_running.add(event.uuid)
        timing = action_timing_enabled()
        total_started = time.perf_counter() if timing else 0.0
        try:
            callbacks: List[Callable[[Event], None]] = list(cls._pre_completion_callbacks)
            callbacks.extend(
                cls._pre_completion_systems_by_event_type.get(event.event_type, {}).values()
            )
            for callback in callbacks:
                started = time.perf_counter() if timing else 0.0
                try:
                    callback(event)
                finally:
                    if timing:
                        callback_name = cls._timing_callback_name(callback)
                        record_action_timing(
                            f"event_queue.pre_completion.callback.{callback_name}_ms",
                            started,
                        )
        finally:
            cls._pre_completion_running.discard(event.uuid)
            if timing:
                record_action_timing("event_queue.pre_completion.total_ms", total_started)

    @staticmethod
    def _timing_callback_name(callback: Callable[..., Any]) -> str:
        """Return a stable, payload-safe name for callback timing groups."""
        owner = getattr(callback, "__self__", None)
        if owner is not None:
            raw_name = f"{type(owner).__name__}.{getattr(callback, '__name__', 'call')}"
        else:
            raw_name = getattr(callback, "__qualname__", type(callback).__name__)
        normalized = "".join(character if character.isalnum() else "_" for character in raw_name)
        return "_".join(part for part in normalized.split("_") if part)

    @classmethod
    def register(cls, event: Event) -> Event:
        """Store an event version and dispatch matching pre-completion handlers.

        Args:
            event: Event version to index and potentially dispatch.

        Returns:
            The final event version after handler processing.
        """
        stored_event = cls._events_by_uuid.get(event.uuid)
        if stored_event is event:
            return event
        if stored_event is not None:
            raise ValueError(f"Event UUID collision for {event.uuid}")
        cls._store_event(event)

        handlers = cls._get_handlers_for_event(event)
        if not handlers or event.phase == EventPhase.COMPLETION:
            return event

        current_event = event
        for handler in handlers:
            result = cls._invoke_handler(handler, current_event)

            if result is None:
                continue

            if result.canceled:
                return cls._record_handler_result(result)

            if result.modified:
                current_event = cls._record_handler_result(result)

        return current_event

    @classmethod
    def preflight(cls, event: EventT) -> EventT:
        """Evaluate pure validation handlers without publishing an event.

        This is the validation half of an explicit transactional boundary.
        Every matching handler must opt into the ``validation_only`` contract:
        it may return a modified or canceled proposal, but it must not mutate
        engine state or emit child events. The queue enforces the observable
        part of that contract by rejecting emitted events. Accepted proposals
        can later be published exactly once with :meth:`publish_preflighted`.

        Args:
            event: Unregistered declaration or execution proposal.

        Returns:
            The final proposed version after validation handlers run.

        Raises:
            ValueError: If the proposal is already configured for publication.
            RuntimeError: If a matching handler is not validation-only or emits
                an event while validating.
            TypeError: If a validator replaces the proposal with another type.
        """
        if event.use_register:
            raise ValueError("Preflight events must use use_register=False")
        if event.phase not in (EventPhase.DECLARATION, EventPhase.EXECUTION):
            raise ValueError("Only declaration and execution events may be preflighted")

        current_event = event
        for handler in cls._get_handlers_for_event(event):
            if not handler.enabled:
                continue
            if not handler.validation_only:
                raise RuntimeError(
                    f"Handler {handler.name!r} matches a transactional preflight but is not "
                    "declared validation_only; move state changes to EFFECT or mark a pure "
                    "validator explicitly"
                )
            before_cursor = cls.event_cursor()
            depth_token = cls._preflight_depth.set(cls._preflight_depth.get() + 1)
            try:
                result = handler(current_event)
            finally:
                cls._preflight_depth.reset(depth_token)
            if cls.event_cursor() != before_cursor:
                raise RuntimeError(
                    f"Validation-only handler {handler.name!r} emitted an event during preflight"
                )
            if result is None:
                continue
            if not isinstance(result, event.__class__):
                raise TypeError(
                    f"Expected {event.__class__.__name__} but got {result.__class__.__name__}"
                )
            if result.use_register:
                raise RuntimeError(
                    f"Validation-only handler {handler.name!r} returned a publishable event"
                )
            current_event = cast(EventT, result)
            if result.canceled:
                return cast(EventT, result)
        return current_event

    @classmethod
    def publish_preflighted(cls, event: EventT) -> EventT:
        """Publish one accepted proposal without dispatching validators twice.

        Args:
            event: Unregistered event version already accepted by ``preflight``.

        Returns:
            The stored publishable event version.

        Raises:
            ValueError: If the event is publishable already or was canceled.
        """
        if event.use_register:
            raise ValueError("Preflighted events must still use use_register=False")
        if event.canceled:
            raise ValueError("Canceled preflight events cannot be published")
        event.use_register = True
        event.timestamp = datetime.now(UTC)
        cls._store_event(event)
        return event

    @classmethod
    def register_completion_sequence(
        cls,
        events: Sequence[Event],
    ) -> Tuple[Event, ...]:
        """Store simultaneous completion events and notify reducers once.

        Immediate per-event callbacks still receive every event. Sequence
        observers run once after all events are indexed, allowing reducers to
        process one causative derived-state boundary without losing individual
        event identities.

        Args:
            events: Completion events ordered by deterministic observer order.

        Returns:
            Stored events in the same order.

        Raises:
            ValueError: If any event is not a completion or reuses a UUID.
        """
        stored: List[Event] = []
        for event in events:
            if event.phase != EventPhase.COMPLETION:
                raise ValueError("Completion sequences may only store completion events")
            existing = cls._events_by_uuid.get(event.uuid)
            if existing is not None:
                raise ValueError(f"Event UUID collision for {event.uuid}")
            cls._store_event(
                event,
                notify_sequence_callbacks=False,
                notify_batch_callbacks=False,
            )
            stored.append(event)
        if stored:
            cls._dispatch_event_sequence(stored)
            if cls._pending_event_batch.get() is None:
                cls._dispatch_event_batch(stored)
        return tuple(stored)

    @classmethod
    def _record_handler_result(cls, result: Event) -> Event:
        """Store one handler-produced version without duplicating event identity."""
        stored_event = cls._events_by_uuid.get(result.uuid)
        if stored_event is result:
            return result
        if stored_event is not None:
            result = result.model_copy(update={
                "uuid": uuid4(),
                "timestamp": datetime.now(UTC),
            })
        cls._store_event(result)
        return result

    @classmethod
    def get_event_by_uuid(cls, uuid: UUID) -> Optional[Event]:
        """Return an event version by UUID, if it is indexed."""
        return cls._events_by_uuid.get(uuid)

    @classmethod
    def _store_event(
        cls,
        event: Event,
        *,
        notify_sequence_callbacks: bool = True,
        notify_batch_callbacks: bool = True,
    ) -> None:
        """Store an event in all queue indexes and notify passive observers."""
        if cls._preflight_depth.get() > 0:
            raise RuntimeError("Validation-only handlers cannot publish events during preflight")
        if event.uuid in cls._events_by_uuid:
            raise ValueError(f"Event UUID collision for {event.uuid}")
        timing = action_timing_enabled()
        total_started = time.perf_counter() if timing else 0.0
        started = time.perf_counter() if timing else 0.0
        identified = {
            entity_uuid: set(observer_uuids)
            for entity_uuid, observer_uuids in event.identified_entity_observer_uuids.items()
        }
        located = {
            entity_uuid: set(observer_uuids)
            for entity_uuid, observer_uuids in event.located_entity_observer_uuids.items()
        }
        if timing:
            record_action_timing("event_queue.store.copy_identified_ms", started)
        if cls._identified_entity_observer_computer is not None:
            started = time.perf_counter() if timing else 0.0
            captured = cls._identified_entity_observer_computer(event)
            located = {
                entity_uuid: set(observer_uuids)
                for entity_uuid, observer_uuids in captured.items()
            }
            if timing:
                record_action_timing("event_queue.store.compute_identified_ms", started)
            started = time.perf_counter() if timing else 0.0
            for entity_uuid, observer_uuids in captured.items():
                identified.setdefault(entity_uuid, set()).update(observer_uuids)
            if timing:
                record_action_timing("event_queue.store.merge_identified_ms", started)

        started = time.perf_counter() if timing else 0.0
        parent_event = cls.get_event_by_uuid(event.parent_event) if event.parent_event else None
        if parent_event is not None:
            for entity_uuid, observer_uuids in parent_event.identified_entity_observer_uuids.items():
                identified.setdefault(entity_uuid, set()).update(observer_uuids)
        event.identified_entity_observer_uuids = identified
        event.located_entity_observer_uuids = located
        if timing:
            record_action_timing("event_queue.store.parent_identity_ms", started)

        started = time.perf_counter() if timing else 0.0
        cls._events_by_lineage[event.lineage_uuid].append(event)
        cls._events_by_uuid[event.uuid] = event
        cls._events_by_timestamp[event.timestamp].append(event)

        if event.parent_event:
            if parent_event and event.uuid not in parent_event.children_events:
                parent_event.add_child_event(event)
                for lineage_event in cls._events_by_lineage.get(parent_event.lineage_uuid, []):
                    if lineage_event.uuid != parent_event.uuid:
                        if event.uuid not in lineage_event.lineage_children_events:
                            lineage_event.add_child_event(event)
        if timing:
            record_action_timing("event_queue.store.lineage_ms", started)

        started = time.perf_counter() if timing else 0.0
        cls._events_by_type[event.event_type].append(event)
        cls._events_by_phase[event.phase].append(event)
        cls._events_by_source[event.source_entity_uuid].append(event)

        if event.target_entity_uuid:
            cls._events_by_target[event.target_entity_uuid].append(event)

        cls._all_events.append(event)
        pending_batch = cls._pending_event_batch.get()
        if pending_batch is not None:
            pending_batch.append(event)
        if timing:
            record_action_timing("event_queue.store.indexes_ms", started)

        started = time.perf_counter() if timing else 0.0
        for callback in list(cls._on_event_callbacks):
            event_types, phases = cls._on_event_callback_filters.get(
                callback,
                (None, None),
            )
            if event_types is not None and event.event_type not in event_types:
                continue
            if phases is not None and event.phase not in phases:
                continue
            callback_started = time.perf_counter() if timing else 0.0
            try:
                callback(event)
            except Exception:
                logger.exception(
                    "Passive event observer %s failed for %s event %s",
                    cls._timing_callback_name(callback),
                    type(event).__name__,
                    event.uuid,
                )
            finally:
                if timing:
                    callback_name = cls._timing_callback_name(callback)
                    record_action_timing(
                        f"event_queue.store.callback.{callback_name}_ms",
                        callback_started,
                    )
        if timing:
            record_action_timing("event_queue.store.callbacks_ms", started)
            record_action_timing("event_queue.store.total_ms", total_started)
        if notify_sequence_callbacks:
            cls._dispatch_event_sequence((event,))
        if pending_batch is None and notify_batch_callbacks:
            cls._dispatch_event_batch((event,))

    @classmethod
    def _get_handlers_for_event(cls, event: Event) -> List['BaseHandler']:
        """Return queue-discovered handlers for an event.

        Spatial entity/tile events with a position use the position index first.
        Other events use trigger indexes and trigger predicates.
        """
        spatial_event_types = (
            EventType.SPATIAL_ENTITY_ENTERED,
            EventType.SPATIAL_ENTITY_LEFT,
            EventType.SPATIAL_TILE_CHANGED
        )
        if event.event_type in spatial_event_types:
            if isinstance(event, SpatialChangeEvent) and event.position is not None:
                return cls._get_handlers_for_spatial_event(event, event.position)

        return cls._get_handlers_for_non_spatial_event(event)

    @classmethod
    def _get_handlers_for_spatial_event(
        cls,
        event: Event,
        position: Tuple[int, int]
    ) -> List['BaseHandler']:
        """Return handlers for one spatial event at one grid position.

        Position-indexed spatial handlers are discovered in O(1). Trigger-based
        event handlers are still included for global spatial reactions such as
        opportunity attacks.

        Args:
            event: Spatial event version being dispatched.
            position: Grid position used for the spatial lookup.

        Returns:
            De-duplicated handlers in queue dispatch order.
        """
        event_key = (event.event_type, event.phase)
        handlers: List['BaseHandler'] = []
        seen: Set[UUID] = set()

        pos_handlers = cls._spatial_handlers_by_position[event_key].get(position, [])
        for h in pos_handlers:
            if h.uuid not in seen:
                handlers.append(h)
                seen.add(h.uuid)

        simple_trigger = Trigger(event_type=event.event_type, event_phase=event.phase)
        for h in cls._event_handlers_by_simple_trigger.get(simple_trigger, []):
            if h.uuid not in seen:
                handlers.append(h)
                seen.add(h.uuid)

        for handler in cls._event_handlers.values():
            if handler.uuid in seen:
                continue
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
        """Return trigger-indexed handlers for a non-spatial event."""
        simple_trigger = Trigger(event_type=event.event_type, event_phase=event.phase)
        simple_handlers = cls._event_handlers_by_simple_trigger.get(simple_trigger, [])

        handler_set: Set[UUID] = {h.uuid for h in simple_handlers}
        matching_handlers: List['BaseHandler'] = list(simple_handlers)

        for handler in cls._event_handlers.values():
            if handler.uuid in handler_set:
                continue
            for trigger in handler.trigger_conditions:
                if trigger(event):
                    matching_handlers.append(handler)
                    handler_set.add(handler.uuid)
                    break

        return matching_handlers

    @classmethod
    def add_event_handler(cls, event_handler: EventHandler) -> None:
        """Add a trigger-indexed handler to queue lookup tables.

        Args:
            event_handler: Handler containing one or more trigger conditions.
        """
        bind_runtime_handler_before_admission(event_handler)
        for trigger in event_handler.trigger_conditions:
            if trigger.is_simple():
                cls._event_handlers_by_simple_trigger[trigger.get_simple_trigger()].append(event_handler)
            cls._event_handlers_by_trigger[trigger].append(event_handler)
        cls._event_handlers[event_handler.uuid] = event_handler
        cls._event_handlers_by_source_entity_uuid[event_handler.source_entity_uuid].append(event_handler)

    @classmethod
    def remove_event_handler(cls, event_handler: EventHandler) -> None:
        """Remove a handler from all indices."""
        for trigger in event_handler.trigger_conditions:
            if trigger.is_simple():
                simple_trigger = trigger.get_simple_trigger()
                if event_handler in cls._event_handlers_by_simple_trigger.get(simple_trigger, []):
                    cls._event_handlers_by_simple_trigger[simple_trigger].remove(event_handler)
            if event_handler in cls._event_handlers_by_trigger.get(trigger, []):
                cls._event_handlers_by_trigger[trigger].remove(event_handler)

        cls._event_handlers.pop(event_handler.uuid, None)

        source_handlers = cls._event_handlers_by_source_entity_uuid.get(event_handler.source_entity_uuid, [])
        if event_handler in source_handlers:
            source_handlers.remove(event_handler)

        cls._remove_from_spatial_indices(event_handler.uuid)

    @classmethod
    def get_handlers_by_source_entity(
        cls,
        source_entity_uuid: UUID,
    ) -> tuple["EventHandler", ...]:
        """Return source-owned non-spatial event handlers."""
        return tuple(
            handler
            for handler in cls._event_handlers_by_source_entity_uuid.get(
                source_entity_uuid,
                (),
            )
            if isinstance(handler, EventHandler)
        )

    @classmethod
    def get_spatial_handler_registration(
        cls,
        handler_uuid: UUID,
    ) -> Optional[tuple["BaseHandler", frozenset[Tuple[int, int]]]]:
        """Return one handler and its exact indexed spatial positions."""
        registration = cls._handler_positions.get(handler_uuid)
        handler = (
            cls._spatial_handlers.get(handler_uuid)
            or cls._event_handlers.get(handler_uuid)
        )
        if registration is None or handler is None:
            return None
        _event_key, positions = registration
        return handler, frozenset(positions)

    @classmethod
    def add_spatial_handler(
        cls,
        handler: Union['EventHandler', 'SpatialHandler'],
        positions: Optional[Set[Tuple[int, int]]] = None,
        event_type: EventType = EventType.SPATIAL_ENTITY_ENTERED,
        event_phase: EventPhase = EventPhase.EFFECT
    ) -> None:
        """Register a handler for spatial lookup at specific positions.

        `SpatialHandler` instances use their own positions and event metadata
        unless explicit positions are supplied. Legacy `EventHandler` instances
        can also be position-indexed with the provided event type and phase.

        Args:
            handler: Spatial or legacy event handler to register.
            positions: Grid positions for lookup. Optional for `SpatialHandler`.
            event_type: Spatial event type for legacy handlers.
            event_phase: Spatial event phase for legacy handlers.
        """
        bind_runtime_handler_before_admission(handler)
        if isinstance(handler, SpatialHandler):
            actual_positions = handler.positions if not positions else positions
            event_key = (handler.event_type, handler.event_phase)

            if positions:
                handler.positions = positions.copy()

            for pos in actual_positions:
                cls._spatial_handlers_by_position[event_key][pos].append(handler)

            cls._handler_positions[handler.uuid] = (event_key, actual_positions.copy())

            cls._spatial_handlers[handler.uuid] = handler
            cls._spatial_handlers_by_source_entity_uuid[handler.source_entity_uuid].append(handler)

        else:
            if positions is None:
                positions = set()

            event_key = (event_type, event_phase)

            for pos in positions:
                cls._spatial_handlers_by_position[event_key][pos].append(handler)

            cls._handler_positions[handler.uuid] = (event_key, positions.copy())

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
        """Update one spatial handler's indexed positions.

        The queue computes a position delta when event type/phase are unchanged
        and fully reindexes when the event key changes.

        Args:
            handler_uuid: Handler UUID to update.
            new_positions: Replacement grid-position set.
            event_type: Optional replacement spatial event type.
            event_phase: Optional replacement spatial event phase.

        Returns:
            True if the handler was found and updated.
        """
        if handler_uuid not in cls._handler_positions:
            return False

        handler: Optional['BaseHandler'] = cls._spatial_handlers.get(handler_uuid)
        if not handler:
            handler = cls._event_handlers.get(handler_uuid)
        if not handler:
            return False

        old_event_key, old_positions = cls._handler_positions[handler_uuid]

        if event_type is not None and event_phase is not None:
            new_event_key = (event_type, event_phase)
        else:
            new_event_key = old_event_key

        if new_event_key != old_event_key:
            for pos in old_positions:
                handlers_at_pos = cls._spatial_handlers_by_position[old_event_key].get(pos, [])
                if handler in handlers_at_pos:
                    handlers_at_pos.remove(handler)
                    if not handlers_at_pos:
                        del cls._spatial_handlers_by_position[old_event_key][pos]

            for pos in new_positions:
                cls._spatial_handlers_by_position[new_event_key][pos].append(handler)
        else:
            positions_to_remove = old_positions - new_positions
            positions_to_add = new_positions - old_positions

            for pos in positions_to_remove:
                handlers_at_pos = cls._spatial_handlers_by_position[new_event_key].get(pos, [])
                if handler in handlers_at_pos:
                    handlers_at_pos.remove(handler)
                    if not handlers_at_pos:
                        del cls._spatial_handlers_by_position[new_event_key][pos]

            for pos in positions_to_add:
                cls._spatial_handlers_by_position[new_event_key][pos].append(handler)

        cls._handler_positions[handler_uuid] = (new_event_key, new_positions.copy())

        if isinstance(handler, SpatialHandler):
            handler.positions = new_positions.copy()

        return True

    @classmethod
    def remove_spatial_handler(cls, handler_uuid: UUID) -> bool:
        """Remove a spatial handler from all queue indexes.

        Works for both native `SpatialHandler` objects and legacy
        `EventHandler` objects registered with `add_spatial_handler()`.

        Args:
            handler_uuid: Handler UUID to remove.

        Returns:
            True if the handler or its spatial index entry was found.
        """
        if handler_uuid not in cls._handler_positions:
            return False

        handler: Optional['BaseHandler'] = cls._spatial_handlers.get(handler_uuid)
        is_spatial_handler = handler is not None

        if not handler:
            handler = cls._event_handlers.get(handler_uuid)

        if not handler:
            cls._remove_from_spatial_indices(handler_uuid)
            return True

        cls._remove_from_spatial_indices(handler_uuid)

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
        """Remove a handler from the position index and reverse index."""
        if handler_uuid not in cls._handler_positions:
            return

        event_key, positions = cls._handler_positions[handler_uuid]

        handler: Optional['BaseHandler'] = cls._spatial_handlers.get(handler_uuid)
        if not handler:
            handler = cls._event_handlers.get(handler_uuid)

        for pos in positions:
            handlers_at_pos = cls._spatial_handlers_by_position[event_key].get(pos, [])
            if handler and handler in handlers_at_pos:
                handlers_at_pos.remove(handler)
                if not handlers_at_pos:
                    del cls._spatial_handlers_by_position[event_key][pos]

        del cls._handler_positions[handler_uuid]

    @classmethod
    def get_spatial_handlers_at(
        cls,
        position: Tuple[int, int],
        event_type: EventType = EventType.SPATIAL_ENTITY_ENTERED,
        event_phase: EventPhase = EventPhase.EFFECT
    ) -> List['BaseHandler']:
        """Return spatial handlers registered for a specific position.

        Args:
            position: Grid position to query.
            event_type: Spatial event type index.
            event_phase: Spatial event phase index.

        Returns:
            A copy of the handlers registered at that key.
        """
        event_key = (event_type, event_phase)
        return cls._spatial_handlers_by_position[event_key].get(position, []).copy()

    @classmethod
    def reset(cls) -> None:
        """Clear all event, handler, and callback registries."""
        cls._generation_uuid = uuid4()
        cls._all_events.clear()
        cls._events_by_uuid.clear()
        cls._events_by_type.clear()
        cls._events_by_phase.clear()
        cls._events_by_source.clear()
        cls._events_by_target.clear()
        cls._events_by_lineage.clear()
        cls._events_by_timestamp.clear()
        cls._event_handlers.clear()
        cls._event_handlers_by_trigger.clear()
        cls._event_handlers_by_simple_trigger.clear()
        cls._event_handlers_by_source_entity_uuid.clear()
        cls._spatial_handlers.clear()
        cls._spatial_handlers_by_position.clear()
        cls._spatial_handlers_by_source_entity_uuid.clear()
        cls._handler_positions.clear()
        cls._on_event_callbacks.clear()
        cls._on_event_callback_filters.clear()
        cls._on_event_sequence_callbacks.clear()
        cls._on_event_sequence_callback_filters.clear()
        cls._on_event_batch_callbacks.clear()
        cls._on_handler_dispatch_callbacks.clear()
        cls._handler_dispatch_cursor = 0
        cls._active_turn_execution_id = None
        cls._event_batch_depth.set(0)
        cls._pending_event_batch.set(None)
        cls._preflight_depth.set(0)
        cls._pre_completion_callbacks.clear()
        for system in tuple(cls._pre_completion_systems.values()):
            system.reset()
        cls._pre_completion_systems.clear()
        cls._pre_completion_systems_by_event_type.clear()
        cls._pre_completion_running.clear()
        cls._perceiver_computer = None
        cls._revealed_computer = None
        cls._identified_entity_observer_computer = None

    @classmethod
    def get_events_chronological(cls, start_time: Optional[datetime] = None,
                               end_time: Optional[datetime] = None) -> List[Event]:
        """Return events in chronological order, optionally within a time range.

        Args:
            start_time: Optional inclusive lower timestamp bound.
            end_time: Optional inclusive upper timestamp bound.

        Returns:
            Stored event versions ordered by timestamp.
        """
        chronological_events = sorted(cls._all_events, key=lambda e: e.timestamp)
        if start_time is None and end_time is None:
            return chronological_events

        filtered_events = chronological_events

        if start_time:
            filtered_events = [e for e in filtered_events if e.timestamp >= start_time]

        if end_time:
            filtered_events = [e for e in filtered_events if e.timestamp <= end_time]

        return filtered_events

    @classmethod
    def get_event_history(cls, event_uuid: UUID) -> List[Event]:
        """Return all stored versions in the lineage containing `event_uuid`.

        Args:
            event_uuid: UUID of any event version in the lineage.

        Returns:
            Chronological event versions for that lineage, or an empty list.
        """
        event = cls._events_by_uuid.get(event_uuid)
        if not event:
            return []

        lineage_uuid = event.lineage_uuid
        return sorted(cls._events_by_lineage.get(lineage_uuid, []), key=lambda e: e.timestamp)

    @classmethod
    def get_events_by_type(cls, event_type: EventType) -> List[Event]:
        """Return all events indexed under an event type."""
        return cls._events_by_type.get(event_type, [])

    @classmethod
    def get_events_by_phase(cls, event_phase: EventPhase) -> List[Event]:
        """Return all events indexed under an event phase."""
        return cls._events_by_phase.get(event_phase, [])

    @classmethod
    def get_events_by_source(cls, source_entity_uuid: UUID) -> List[Event]:
        """Return all events indexed under a source entity UUID."""
        return cls._events_by_source.get(source_entity_uuid, [])

    @classmethod
    def get_events_by_target(cls, target_entity_uuid: UUID) -> List[Event]:
        """Return all events indexed under a target entity UUID."""
        return cls._events_by_target.get(target_entity_uuid, [])

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
                continue
            if e.phase == event.phase and e.timestamp < event.timestamp:
                return False
        return True


class D20Event(Event):
    """Legacy event payload for a resolved d20 check."""

    name: str = Field(default="D20", description="Human-readable d20 event label.")
    dc: Optional[Union[int, ModifiableValue]] = Field(
        default=None,
        description="Difficulty class for the roll, either fixed or modifiable.",
    )
    bonus: Optional[Union[int, ModifiableValue]] = Field(
        default=0,
        description="Roll bonus, either fixed or represented by a modifiable value.",
    )
    dice: Optional[Dice] = Field(default=None, description="Dice object used to create the roll.")
    dice_roll: Optional[DiceRoll] = Field(default=None, description="Resolved dice roll.")
    result: Optional[bool] = Field(default=None, description="Whether the roll met or exceeded its DC.")

    def get_dc(self) -> Optional[int]:
        """Return the current numeric difficulty class."""
        if self.dc is None:
            return None
        if isinstance(self.dc, ModifiableValue):
            return self.dc.normalized_score
        return self.dc

class SavingThrowEvent(D20Event):
    """Legacy event payload for a resolved saving throw."""

    name: str = Field(default="Saving Throw", description="Human-readable saving throw label.")
    ability_name: AbilityName = Field(description="Ability used for the saving throw.")
    saving_throw_context: Optional[SavingThrowContext] = Field(
        default=None,
        description=(
            "Exact authored cause, effect identity, magical fact, and closed "
            "rule semantics for this saving throw."
        ),
    )
    condition_context: Optional[str] = Field(
        default=None,
        description="Optional condition name this save is made against, such as Poisoned.",
    )
    event_type: EventType = Field(
        default=EventType.SAVING_THROW,
        description="Event category for saving throw events.",
    )

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for this saving throw event.

        Uses self.* fields only - no external lookups. Entity names must be
        populated when the event is created.
        """
        target_name = self.target_entity_name or "Unknown"
        source_name = self.source_entity_name or "Unknown"

        dc = self.get_dc() or 0

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

        bonus_breakdown: List[ModifierBreakdown] = []
        if self.bonus and isinstance(self.bonus, ModifiableValue):
            for mod in self.bonus.get_breakdown():
                bonus_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

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

        success = self.result if self.result is not None else (roll.total >= dc if dc > 0 else None)

        ability_display = self.ability_name.upper()[:3]

        success_str = md_color("succeeds", "green") if success else md_color("fails", "red")

        compact_text = f"{md_color(target_name, 'cyan')} {success_str} {md_color(ability_display, 'yellow')} save (DC {dc})"

        d20_str = md_d20_roll(roll)
        bonus_str = f"+{roll.bonus}" if roll.bonus >= 0 else str(roll.bonus)
        verbose_text = f"{md_color(target_name, 'cyan')} {md_color(ability_display, 'yellow')} save vs DC {dc}"
        verbose_text += f"\n  Save: {d20_str} {bonus_str} = {roll.total} → {success_str}"

        detailed_text = f"{md_color(target_name, 'cyan')} {md_color(ability_display, 'yellow')} save vs DC {dc}"
        breakdown_str = md_breakdown(bonus_breakdown)
        detailed_text += f"\n  Save: {d20_str} {bonus_str}"
        if breakdown_str:
            detailed_text += f" {breakdown_str}"
        detailed_text += f" = {roll.total} → {success_str}"

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
    """Legacy event payload for a resolved skill check."""

    name: str = Field(default="Skill Check", description="Human-readable skill check label.")
    skill_name: SkillName = Field(description="Skill used for the check.")
    event_type: EventType = Field(
        default=EventType.SKILL_CHECK,
        description="Event category for skill check events.",
    )

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for this skill check event.

        Uses self.* fields only - no external lookups. Entity names must be
        populated when the event is created.
        """
        source_name = self.source_entity_name or "Unknown"

        dc = self.get_dc()

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

        bonus_breakdown: List[ModifierBreakdown] = []
        if self.bonus and isinstance(self.bonus, ModifiableValue):
            for mod in self.bonus.get_breakdown():
                bonus_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

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

        success = self.result if self.result is not None else (roll.total >= dc if dc is not None and dc > 0 else None)

        skill_display = self.skill_name.replace('_', ' ').title()

        d20_str = md_d20_roll(roll)
        bonus_str = f"+{roll.bonus}" if roll.bonus >= 0 else str(roll.bonus)
        breakdown_str = md_breakdown(bonus_breakdown)

        if dc is not None:
            success_str = md_color("succeeds", "green") if success else md_color("fails", "red")

            compact_text = f"{md_color(source_name, 'cyan')} {success_str} {md_color(skill_display, 'yellow')} check (DC {dc})"

            verbose_text = f"{md_color(source_name, 'cyan')} {md_color(skill_display, 'yellow')} check vs DC {dc}"
            verbose_text += f"\n  {skill_display}: {d20_str} {bonus_str} = {roll.total} → {success_str}"

            detailed_text = f"{md_color(source_name, 'cyan')} {md_color(skill_display, 'yellow')} check vs DC {dc}"
            detailed_text += f"\n  {skill_display}: {d20_str} {bonus_str}"
            if breakdown_str:
                detailed_text += f" {breakdown_str}"
            detailed_text += f" = {roll.total} → {success_str}"
        else:
            compact_text = f"{md_color(source_name, 'cyan')} rolls {md_color(skill_display, 'yellow')}: {md_color(str(roll.total), 'cyan')}"
            verbose_text = f"{md_color(source_name, 'cyan')} {md_color(skill_display, 'yellow')} check"
            verbose_text += f"\n  {skill_display}: {d20_str} {bonus_str} = {roll.total}"
            detailed_text = verbose_text
            if breakdown_str:
                detailed_text = f"{md_color(source_name, 'cyan')} {md_color(skill_display, 'yellow')} check"
                detailed_text += f"\n  {skill_display}: {d20_str} {bonus_str} {breakdown_str} = {roll.total}"

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
    """Incremental recomputation hint carried by spatial events.

    The hints separate field-of-view geometry, movement topology, light/filter
    updates, object dictionaries, and directional blocking so observers can
    update only the senses layers affected by a spatial change.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    requires_fov: bool = Field(
        default=False,
        description="Whether vision geometry must be recomputed.",
    )
    requires_paths: bool = Field(
        default=False,
        description="Whether movement/path topology must be recomputed.",
    )
    entity_entered: Optional[Tuple[UUID, Tuple[int, int]]] = Field(
        default=None,
        description="Entity UUID and position for an O(1) visible-entity insertion.",
    )
    entity_left: Optional[Tuple[UUID, Tuple[int, int]]] = Field(
        default=None,
        description="Entity UUID and position for an O(1) visible-entity removal.",
    )
    light_changed_positions: Optional[Set[Tuple[int, int]]] = Field(
        default=None,
        description="Positions whose resolved light should be re-filtered.",
        json_schema_extra=_preserve_nullable_unique_array_schema,
    )
    perceivability_entity: Optional[UUID] = Field(
        default=None,
        description="Entity UUID whose hidden/invisible perceivability should be rechecked.",
    )
    object_placed: Optional[Tuple[UUID, Tuple[int, int]]] = Field(
        default=None,
        description="Object UUID and position for an O(1) visible-object insertion.",
    )
    object_removed: Optional[Tuple[UUID, Tuple[int, int]]] = Field(
        default=None,
        description="Object UUID and position for an O(1) visible-object removal.",
    )
    entity_died: Optional[Tuple[UUID, Tuple[int, int]]] = Field(
        default=None,
        description="Entity UUID and position for path updates after death stops blocking movement.",
    )
    directional_positions: Optional[Set[Tuple[int, int]]] = Field(
        default=None,
        description="Tiles whose directional blocking metadata changed.",
        json_schema_extra=_preserve_nullable_unique_array_schema,
    )
    directional_neighbors: Optional[Set[Tuple[int, int]]] = Field(
        default=None,
        description="Neighbor cells affected by directional blocking metadata.",
        json_schema_extra=_preserve_nullable_unique_array_schema,
    )
    directional_channels_changed: Optional[Set[str]] = Field(
        default=None,
        description="Directional channels affected, such as movement, vision, light, or propagation.",
        json_schema_extra=_preserve_nullable_unique_array_schema,
    )
    requires_light_recompute: bool = Field(
        default=False,
        description="Whether light propagation must be recomputed.",
    )
    requires_propagation_recompute: bool = Field(
        default=False,
        description="Whether non-light propagation fields must be recomputed.",
    )

    @field_serializer(
        "light_changed_positions",
        "directional_positions",
        "directional_neighbors",
        when_used="json",
    )
    def serialize_position_sets(
        self,
        value: Optional[Set[Tuple[int, int]]],
    ) -> Optional[List[Tuple[int, int]]]:
        """Emit unordered coordinate hints in canonical wire order."""
        return None if value is None else sorted(value)

    @field_serializer("directional_channels_changed", when_used="json")
    def serialize_directional_channels(
        self,
        value: Optional[Set[str]],
    ) -> Optional[List[str]]:
        """Emit unordered directional channels in canonical wire order."""
        return None if value is None else sorted(value)


class SensoryUpdateEvent(Event):
    """Observer-specific sensory state delta.

    This event records the backend-authoritative change to one observer's
    visibility/fog/entity/object perception. It is emitted before the causative
    parent completes, so clients can animate perception changes from the event
    tree without recomputing FOV or polling snapshots for timing.
    """
    name: str = Field(default="Sensory Update", description="Observer sensory state changed.")
    event_type: EventType = Field(
        default=EventType.SENSORY_UPDATE,
        description="Event category for observer-specific sensory deltas.",
    )
    observer_uuid: UUID = Field(description="Observer whose sensory state changed.")
    observer_position: Tuple[int, int] = Field(
        default=(0, 0),
        description="Observer grid position after the sensory update.",
    )
    observer_position_changed: bool = Field(
        default=False,
        description="Whether this update changed the observer's grid position.",
    )
    effective_light_levels: Dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Backend-resolved subjective light levels for every currently visible "
            "cell, keyed as 'x,y'."
        ),
    )
    cause_event_uuid: UUID = Field(description="Event UUID that caused this sensory update.")
    update_reason: SensoryUpdateReason = Field(
        default=SensoryUpdateReason.UNKNOWN,
        description="Reason category used by clients to interpret the delta.",
    )
    visible_cells_added: List[Tuple[int, int]] = Field(
        default_factory=list,
        description="Cells newly visible to the observer.",
    )
    visible_cells_removed: List[Tuple[int, int]] = Field(
        default_factory=list,
        description="Cells no longer visible to the observer.",
    )
    seen_cells_added: List[Tuple[int, int]] = Field(
        default_factory=list,
        description="Cells newly added to the observer's explored area.",
    )
    visible_entities_added: Dict[UUID, Tuple[int, int]] = Field(
        default_factory=dict,
        description="Entity UUIDs and positions newly visible to the observer.",
    )
    visible_entities_removed: Dict[UUID, Tuple[int, int]] = Field(
        default_factory=dict,
        description="Entity UUIDs and last positions no longer visible to the observer.",
    )
    visible_entities_moved: Dict[UUID, Tuple[Tuple[int, int], Tuple[int, int]]] = Field(
        default_factory=dict,
        description="Entity UUIDs mapped to old and new visible positions.",
    )
    visible_objects_added: Dict[UUID, Tuple[int, int]] = Field(
        default_factory=dict,
        description="Object UUIDs and positions newly visible to the observer.",
    )
    visible_objects_removed: Dict[UUID, Tuple[int, int]] = Field(
        default_factory=dict,
        description="Object UUIDs and last positions no longer visible to the observer.",
    )
    visible_objects_moved: Dict[UUID, Tuple[Tuple[int, int], Tuple[int, int]]] = Field(
        default_factory=dict,
        description="Object UUIDs mapped to old and new visible positions.",
    )
    sense_modes_changed: bool = Field(
        default=False,
        description="Whether the observer's sense modes changed.",
    )
    sense_modes: Optional[List[SenseMode]] = Field(
        default=None,
        description="Typed sense modes after a sense-mode change.",
    )
    passive_perception_changed: bool = Field(
        default=False,
        description="Whether the observer's passive perception changed.",
    )
    passive_perception: Optional[int] = Field(
        default=None,
        description="Current passive perception value when it changed.",
    )
    paths_dirty: bool = Field(
        default=False,
        description="Whether the observer should refresh cached path data.",
    )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return every grid cell referenced by this sensory delta."""
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

_DIRECTION_DELTAS: Dict[str, Tuple[int, int]] = {
    "north": (0, 1),
    "south": (0, -1),
    "east": (1, 0),
    "west": (-1, 0),
}


def _directional_neighbors(position: Tuple[int, int], directions: Optional[List[str]]) -> Set[Tuple[int, int]]:
    """Return neighboring cells touched by directional tile metadata.

    Args:
        position: Origin tile for the directional metadata.
        directions: Direction labels such as north, south, east, and west.

    Returns:
        Neighboring grid positions for recognized direction labels.
    """
    neighbors: Set[Tuple[int, int]] = set()
    if not directions:
        return neighbors
    for direction in directions:
        delta = _DIRECTION_DELTAS.get(direction)
        if delta is not None:
            neighbors.add((position[0] + delta[0], position[1] + delta[1]))
    return neighbors


class SpatialChangeEvent(Event):
    """Event fired when grid occupancy, tile state, light, or blocking changes.

    GridMap creates these as declaration events and controls registration as it
    advances the event lifecycle. The payload is consumed by senses, spatial
    handlers, combat logs, and frontend reducers.
    """

    name: str = Field(default="Spatial Change", description="A spatial change event")
    event_type: EventType = Field(default=EventType.SPATIAL_ENTITY_ENTERED, description="Type of spatial change")
    change_type: SpatialChangeType = Field(description="Specific type of spatial change")
    position: Tuple[int, int] = Field(description="Grid position where change occurred")
    entity_uuid: Optional[UUID] = Field(default=None, description="UUID of entity involved (if any)")
    object_uuid: Optional[UUID] = Field(default=None, description="UUID of object involved (if any)")
    old_position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Secondary movement position: previous position on enter events, destination on leave events.",
    )
    tile_walkable: Optional[bool] = Field(default=None, description="New walkable state (for tile changes)")
    tile_visible: Optional[bool] = Field(default=None, description="New visible state (for tile changes)")
    senses_hint: Optional[SensesUpdateHint] = Field(default=None, description="Hint for incremental senses updates")

    new_light_level: Optional[int] = Field(default=None, description="Resolved light level at position after change")
    light_level_map: Optional[Dict[str, int]] = Field(default=None, description="Map of 'x,y' -> resolved light_level for all changed positions in batch")

    object_name: Optional[str] = Field(default=None, description="Object name (e.g. 'Door', 'Torch')")
    object_map_char: Optional[str] = Field(default=None, description="Object map character (e.g. 'D', 'φ')")
    object_blocks_movement: Optional[bool] = Field(default=None, description="Object blocks_movement after change")
    object_blocks_vision: Optional[bool] = Field(default=None, description="Object blocks_vision after change")
    object_is_open: Optional[bool] = Field(default=None, description="Object is_open state (doors)")

    directional_position: Optional[Tuple[int, int]] = Field(default=None, description="Tile whose directional state changed")
    directional_directions: Optional[List[str]] = Field(default=None, description="Tile-relative directions changed")
    directional_channels: Optional[List[str]] = Field(default=None, description="Directional channels changed")
    directional_blocks_movement: Optional[Dict[str, bool]] = Field(default=None, description="Direction -> movement blocked")
    directional_blocks_vision: Optional[Dict[str, bool]] = Field(default=None, description="Direction -> vision blocked")
    directional_blocks_light: Optional[Dict[str, bool]] = Field(default=None, description="Direction -> light blocked")
    directional_blocks_propagation: Optional[Dict[str, bool]] = Field(default=None, description="Direction -> propagation blocked")
    transition_from: Optional[Tuple[int, int]] = Field(default=None, description="Transition source for directional movement/collision")
    transition_to: Optional[Tuple[int, int]] = Field(default=None, description="Transition destination for directional movement/collision")

    @classmethod
    def entity_entered(cls, position: Tuple[int, int], entity_uuid: UUID,
                       old_position: Optional[Tuple[int, int]] = None,
                       source_entity_uuid: Optional[UUID] = None,
                       parent_event: Optional[UUID] = None,
                       directional_position: Optional[Tuple[int, int]] = None,
                       directional_directions: Optional[List[str]] = None,
                       directional_channels: Optional[List[str]] = None,
                       directional_blocks_movement: Optional[Dict[str, bool]] = None,
                       directional_blocks_vision: Optional[Dict[str, bool]] = None,
                       directional_blocks_light: Optional[Dict[str, bool]] = None,
                       directional_blocks_propagation: Optional[Dict[str, bool]] = None) -> 'SpatialChangeEvent':
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
        directional_channels_set = set(directional_channels or [])
        directional_pos = directional_position or position
        directional_neighbors = _directional_neighbors(directional_pos, directional_directions)
        hint = SensesUpdateHint(
            requires_fov="vision" in directional_channels_set,
            requires_paths=True,
            entity_entered=(entity_uuid, position),
            entity_left=(entity_uuid, old_position) if old_position is not None else None,
            directional_positions={directional_pos} if directional_channels_set else None,
            directional_neighbors=directional_neighbors or None,
            directional_channels_changed=directional_channels_set or None,
            requires_light_recompute="light" in directional_channels_set,
            requires_propagation_recompute="propagation" in directional_channels_set,
        )
        return cls(
            source_entity_uuid=source_entity_uuid or entity_uuid,
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            change_type=SpatialChangeType.ENTITY_ENTERED,
            position=position,
            entity_uuid=entity_uuid,
            old_position=old_position,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=hint,
            directional_position=directional_position,
            directional_directions=directional_directions,
            directional_channels=directional_channels,
            directional_blocks_movement=directional_blocks_movement,
            directional_blocks_vision=directional_blocks_vision,
            directional_blocks_light=directional_blocks_light,
            directional_blocks_propagation=directional_blocks_propagation,
        )

    @classmethod
    def entity_left(cls, position: Tuple[int, int], entity_uuid: UUID,
                    new_position: Optional[Tuple[int, int]] = None,
                    source_entity_uuid: Optional[UUID] = None,
                    parent_event: Optional[UUID] = None,
                    directional_position: Optional[Tuple[int, int]] = None,
                    directional_directions: Optional[List[str]] = None,
                    directional_channels: Optional[List[str]] = None,
                    directional_blocks_movement: Optional[Dict[str, bool]] = None,
                    directional_blocks_vision: Optional[Dict[str, bool]] = None,
                    directional_blocks_light: Optional[Dict[str, bool]] = None,
                    directional_blocks_propagation: Optional[Dict[str, bool]] = None) -> 'SpatialChangeEvent':
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
        directional_channels_set = set(directional_channels or [])
        directional_pos = directional_position or position
        directional_neighbors = _directional_neighbors(directional_pos, directional_directions)
        hint = SensesUpdateHint(
            requires_fov="vision" in directional_channels_set,
            requires_paths=True,
            entity_left=(entity_uuid, position),
            directional_positions={directional_pos} if directional_channels_set else None,
            directional_neighbors=directional_neighbors or None,
            directional_channels_changed=directional_channels_set or None,
            requires_light_recompute="light" in directional_channels_set,
            requires_propagation_recompute="propagation" in directional_channels_set,
        )
        return cls(
            source_entity_uuid=source_entity_uuid or entity_uuid,
            event_type=EventType.SPATIAL_ENTITY_LEFT,
            change_type=SpatialChangeType.ENTITY_LEFT,
            position=position,
            entity_uuid=entity_uuid,
            old_position=new_position,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=hint,
            directional_position=directional_position,
            directional_directions=directional_directions,
            directional_channels=directional_channels,
            directional_blocks_movement=directional_blocks_movement,
            directional_blocks_vision=directional_blocks_vision,
            directional_blocks_light=directional_blocks_light,
            directional_blocks_propagation=directional_blocks_propagation,
        )

    @classmethod
    def tile_changed(cls, position: Tuple[int, int], walkable: bool, visible: bool,
                     source_entity_uuid: Optional[UUID] = None,
                     senses_hint: Optional['SensesUpdateHint'] = None,
                     parent_event: Optional[UUID] = None,
                     directional_position: Optional[Tuple[int, int]] = None,
                     directional_directions: Optional[List[str]] = None,
                     directional_channels: Optional[List[str]] = None,
                     directional_blocks_movement: Optional[Dict[str, bool]] = None,
                     directional_blocks_vision: Optional[Dict[str, bool]] = None,
                     directional_blocks_light: Optional[Dict[str, bool]] = None,
                     directional_blocks_propagation: Optional[Dict[str, bool]] = None) -> 'SpatialChangeEvent':
        """Create an event for a tile property change.

        Event starts at DECLARATION phase to allow full lifecycle.
        If no senses_hint is provided, one is auto-generated from walkable/visible flags
        requiring FOV if visible changed and paths if walkable changed.
        """
        directional_channels_set = set(directional_channels or [])
        directional_pos = directional_position or position
        directional_neighbors = _directional_neighbors(directional_pos, directional_directions)
        if senses_hint is None:
            senses_hint = SensesUpdateHint(
                requires_fov=True or "vision" in directional_channels_set,
                requires_paths=True or "movement" in directional_channels_set,
                directional_positions={directional_pos} if directional_channels_set else None,
                directional_neighbors=directional_neighbors or None,
                directional_channels_changed=directional_channels_set or None,
                requires_light_recompute="light" in directional_channels_set,
                requires_propagation_recompute="propagation" in directional_channels_set,
            )
        return cls(
            source_entity_uuid=source_entity_uuid or uuid4(),
            event_type=EventType.SPATIAL_TILE_CHANGED,
            change_type=SpatialChangeType.TILE_CHANGED,
            position=position,
            tile_walkable=walkable,
            tile_visible=visible,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=senses_hint,
            directional_position=directional_position,
            directional_directions=directional_directions,
            directional_channels=directional_channels,
            directional_blocks_movement=directional_blocks_movement,
            directional_blocks_vision=directional_blocks_vision,
            directional_blocks_light=directional_blocks_light,
            directional_blocks_propagation=directional_blocks_propagation,
        )

    @classmethod
    def object_placed(cls, position: Tuple[int, int], object_uuid: UUID,
                      source_entity_uuid: Optional[UUID] = None,
                      parent_event: Optional[UUID] = None,
                      blocks_vision: bool = False,
                      blocks_walking: bool = False,
                      object_name: Optional[str] = None,
                      object_map_char: Optional[str] = None,
                      directional_position: Optional[Tuple[int, int]] = None,
                      directional_directions: Optional[List[str]] = None,
                      directional_channels: Optional[List[str]] = None,
                      directional_blocks_movement: Optional[Dict[str, bool]] = None,
                      directional_blocks_vision: Optional[Dict[str, bool]] = None,
                      directional_blocks_light: Optional[Dict[str, bool]] = None,
                      directional_blocks_propagation: Optional[Dict[str, bool]] = None) -> 'SpatialChangeEvent':
        """Create an event for an object being placed on the grid."""
        directional_channels_set = set(directional_channels or [])
        directional_pos = directional_position or position
        directional_neighbors = _directional_neighbors(directional_pos, directional_directions)
        hint = SensesUpdateHint(
            requires_fov=blocks_vision or "vision" in directional_channels_set,
            requires_paths=blocks_walking or "movement" in directional_channels_set,
            object_placed=(object_uuid, position),
            directional_positions={directional_pos} if directional_channels_set else None,
            directional_neighbors=directional_neighbors or None,
            directional_channels_changed=directional_channels_set or None,
            requires_light_recompute="light" in directional_channels_set,
            requires_propagation_recompute="propagation" in directional_channels_set,
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
            directional_position=directional_position,
            directional_directions=directional_directions,
            directional_channels=directional_channels,
            directional_blocks_movement=directional_blocks_movement,
            directional_blocks_vision=directional_blocks_vision,
            directional_blocks_light=directional_blocks_light,
            directional_blocks_propagation=directional_blocks_propagation,
        )

    @classmethod
    def object_removed(cls, position: Tuple[int, int], object_uuid: UUID,
                       source_entity_uuid: Optional[UUID] = None,
                       parent_event: Optional[UUID] = None,
                       blocks_vision: bool = False,
                       blocks_walking: bool = False,
                       directional_position: Optional[Tuple[int, int]] = None,
                       directional_directions: Optional[List[str]] = None,
                       directional_channels: Optional[List[str]] = None,
                       directional_blocks_movement: Optional[Dict[str, bool]] = None,
                       directional_blocks_vision: Optional[Dict[str, bool]] = None,
                       directional_blocks_light: Optional[Dict[str, bool]] = None,
                       directional_blocks_propagation: Optional[Dict[str, bool]] = None) -> 'SpatialChangeEvent':
        """Create an event for an object being removed from the grid."""
        directional_channels_set = set(directional_channels or [])
        directional_pos = directional_position or position
        directional_neighbors = _directional_neighbors(directional_pos, directional_directions)
        hint = SensesUpdateHint(
            requires_fov=blocks_vision or "vision" in directional_channels_set,
            requires_paths=blocks_walking or "movement" in directional_channels_set,
            object_removed=(object_uuid, position),
            directional_positions={directional_pos} if directional_channels_set else None,
            directional_neighbors=directional_neighbors or None,
            directional_channels_changed=directional_channels_set or None,
            requires_light_recompute="light" in directional_channels_set,
            requires_propagation_recompute="propagation" in directional_channels_set,
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
            directional_position=directional_position,
            directional_directions=directional_directions,
            directional_channels=directional_channels,
            directional_blocks_movement=directional_blocks_movement,
            directional_blocks_vision=directional_blocks_vision,
            directional_blocks_light=directional_blocks_light,
            directional_blocks_propagation=directional_blocks_propagation,
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
            entity_uuid=tile_uuid,
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
                       object_is_open: Optional[bool] = None,
                       directional_position: Optional[Tuple[int, int]] = None,
                       directional_directions: Optional[List[str]] = None,
                       directional_channels: Optional[List[str]] = None,
                       directional_blocks_movement: Optional[Dict[str, bool]] = None,
                       directional_blocks_vision: Optional[Dict[str, bool]] = None,
                       directional_blocks_light: Optional[Dict[str, bool]] = None,
                       directional_blocks_propagation: Optional[Dict[str, bool]] = None) -> 'SpatialChangeEvent':
        """Create an event for an object's blocking state changing (door open/close).

        Fires when an object's blocks_movement or blocks_vision_field changes
        while on the grid. Carries hint indicating which senses layers are affected.
        """
        directional_channels_set = set(directional_channels or [])
        directional_pos = directional_position or position
        directional_neighbors = _directional_neighbors(directional_pos, directional_directions)
        hint = SensesUpdateHint(
            requires_fov=blocks_vision_changed or "vision" in directional_channels_set,
            requires_paths=blocks_walking_changed or "movement" in directional_channels_set,
            directional_positions={directional_pos} if directional_channels_set else None,
            directional_neighbors=directional_neighbors or None,
            directional_channels_changed=directional_channels_set or None,
            requires_light_recompute="light" in directional_channels_set,
            requires_propagation_recompute="propagation" in directional_channels_set,
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
            directional_position=directional_position,
            directional_directions=directional_directions,
            directional_channels=directional_channels,
            directional_blocks_movement=directional_blocks_movement,
            directional_blocks_vision=directional_blocks_vision,
            directional_blocks_light=directional_blocks_light,
            directional_blocks_propagation=directional_blocks_propagation,
        )

    @classmethod
    def movement_collision(cls, position: Tuple[int, int], mover_uuid: UUID,
                           source_entity_uuid: Optional[UUID] = None,
                           parent_event: Optional[UUID] = None,
                           transition_from: Optional[Tuple[int, int]] = None,
                           transition_to: Optional[Tuple[int, int]] = None,
                           directional_position: Optional[Tuple[int, int]] = None,
                           directional_directions: Optional[List[str]] = None,
                           directional_channels: Optional[List[str]] = None) -> 'SpatialChangeEvent':
        """Create an event for an entity bumping into an imperceivable blocker.

        Fired when objective walkability blocks but subjective would allow.
        Hidden entities at this position will be de-stealthed by their reveal handler.
        """
        directional_channels_set = set(directional_channels or [])
        directional_pos = directional_position or position
        directional_neighbors = _directional_neighbors(directional_pos, directional_directions)
        hint = SensesUpdateHint(
            requires_paths=True,
            directional_positions={directional_pos} if directional_channels_set else None,
            directional_neighbors=directional_neighbors or None,
            directional_channels_changed=directional_channels_set or None,
        )
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
            transition_from=transition_from,
            transition_to=transition_to,
            directional_position=directional_position,
            directional_directions=directional_directions,
            directional_channels=directional_channels,
        )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        positions = {self.position}
        if self.old_position:
            positions.add(self.old_position)
        if self.directional_position:
            positions.add(self.directional_position)
            positions.update(_directional_neighbors(self.directional_position, self.directional_directions))
        if self.transition_from:
            positions.add(self.transition_from)
        if self.transition_to:
            positions.add(self.transition_to)
        if self.senses_hint:
            if self.senses_hint.directional_positions:
                positions.update(self.senses_hint.directional_positions)
            if self.senses_hint.directional_neighbors:
                positions.update(self.senses_hint.directional_neighbors)
        return positions


class FireExposureEvent(Event):
    """Position-level event for environmental fire exposure."""

    name: str = Field(default="Fire Exposure", description="Human-readable fire exposure event label.")
    event_type: EventType = Field(default=EventType.FIRE_EXPOSURE, description="Event category for fire exposure.")
    position: Tuple[int, int] = Field(description="Grid position exposed to fire.")
    duration_rounds: int = Field(
        default=1,
        ge=1,
        description="Number of rounds the exposure's lingering fire should last.",
    )
    damage_dice: str = Field(
        default="2d4",
        description="Rules-facing lingering fire damage expression for consumers that apply damage.",
    )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return the exposed grid position."""
        return {self.position}


class ExposedFlameEvent(Event):
    """Event emitted after an item creates an exposed flame."""

    name: str = Field(default="Exposed Flame Ignited", description="Human-readable exposed-flame event label.")
    event_type: EventType = Field(
        default=EventType.EXPOSED_FLAME_IGNITED,
        description="Event category for a newly ignited exposed flame.",
    )
    item_uuid: UUID = Field(description="Item that owns the exposed flame.")
    position: Tuple[int, int] = Field(description="Grid position where the flame is exposed.")

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return the exposed flame position."""
        return {self.position}


class WindExposureEvent(Event):
    """Area-level event for environmental wind exposure."""

    name: str = Field(default="Wind Exposure", description="Human-readable wind exposure event label.")
    event_type: EventType = Field(
        default=EventType.WIND_EXPOSURE,
        description="Event category for wind exposure.",
    )
    positions: Set[Tuple[int, int]] = Field(
        default_factory=set,
        description="Grid positions exposed to the wind.",
        json_schema_extra={"uniqueItems": True},
    )
    wind_speed_mph: int = Field(
        default=0,
        ge=0,
        description="Wind speed in miles per hour.",
    )
    source_description: str = Field(
        default="wind",
        description="Rules-facing description of the wind source.",
    )

    @field_serializer("positions", when_used="json")
    def serialize_positions(
        self,
        value: Set[Tuple[int, int]],
    ) -> List[Tuple[int, int]]:
        """Emit wind-exposed cells in canonical wire order."""
        return sorted(value)

    def gas_dispersal_rounds(self) -> Optional[int]:
        """Return SRD gas dispersal rounds for this wind speed.

        Returns:
            One round for strong wind, four rounds for moderate wind, or
            ``None`` when the wind is too weak to disperse gas.
        """
        if self.wind_speed_mph >= 20:
            return 1
        if self.wind_speed_mph >= 10:
            return 4
        return None

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return positions exposed to wind."""
        return set(self.positions)


class ForcedMovementEvent(Event):
    """Forced movement event for pushes, pulls, and similar displacement.

    This uses `FORCED_MOVEMENT` rather than `MOVEMENT`, so opportunity-attack
    handlers that listen to voluntary movement do not trigger. GridMap still
    emits spatial enter/leave events when the target position changes.
    """

    name: str = Field(default="Forced Movement", description="Human-readable forced-movement label.")
    event_type: EventType = Field(
        default=EventType.FORCED_MOVEMENT,
        description="Event category for forced displacement.",
    )
    start_position: Tuple[int, int] = Field(description="Target position before displacement.")
    end_position: Tuple[int, int] = Field(description="Target position after displacement.")
    direction: Tuple[int, int] = Field(description="Displacement direction as (dx, dy).")
    intended_distance: int = Field(description="Requested displacement distance in feet.")
    actual_distance: int = Field(default=0, description="Distance actually moved in feet.")
    blocked_by_obstacle: bool = Field(default=False, description="Whether an obstacle stopped movement early.")
    blocked_by: Optional[str] = Field(default=None, description="Obstacle or entity that blocked movement.")
    cause: str = Field(default="shove", description="Mechanic that caused the displacement.")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate combat log for forced movement."""
        source_name = self.source_entity_name or "Unknown"
        target_name = self.target_entity_name or "Unknown"

        blocked_suffix = ""
        if self.blocked_by_obstacle:
            if self.blocked_by:
                blocked_suffix = f" (blocked by {self.blocked_by})"
            else:
                blocked_suffix = " (blocked)"

        if self.actual_distance == 0:
            compact_text = f"{md_color(target_name, 'yellow')} resists being pushed"
        elif self.blocked_by_obstacle:
            compact_text = f"{md_color(target_name, 'yellow')} pushed {md_color(f'{self.actual_distance}ft', 'green')}{blocked_suffix}"
        else:
            compact_text = f"{md_color(target_name, 'yellow')} pushed {md_color(f'{self.actual_distance}ft', 'green')}"

        verbose_text = f"{md_color(source_name, 'cyan')} pushes {md_color(target_name, 'yellow')}"
        if self.actual_distance > 0:
            verbose_text += f" {md_color(f'{self.actual_distance}ft', 'green')}"
            verbose_text += f": {self.start_position} \u2192 {self.end_position}"
            if self.blocked_by_obstacle:
                verbose_text += blocked_suffix
        else:
            verbose_text += f" - {md_color('resisted', 'red')}"

        detailed_text = verbose_text
        detailed_text += f"\n  Direction: {self.direction}"
        detailed_text += f"\n  {self.start_position} → {self.end_position}"
        if self.actual_distance != self.intended_distance:
            detailed_text += f"\n  Intended: {self.intended_distance}ft, Actual: {self.actual_distance}ft"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.MOVEMENT,
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

    def completion_position_observer_evidence(
        self,
        completion_locations: Dict[str, Set[str]],
    ) -> Dict[str, Set[str]]:
        """Freeze independent pre-displacement and post-displacement grants."""
        if (
            self.target_entity_uuid is None
            or self.phase is not EventPhase.EFFECT
        ):
            return super().completion_position_observer_evidence(
                completion_locations
            )
        entity_key = str(self.target_entity_uuid)
        evidence = super().completion_position_observer_evidence(
            completion_locations
        )
        evidence[position_evidence_key(self.start_position)] = set(
            self.located_entity_observer_uuids.get(entity_key, set())
        )
        evidence[position_evidence_key(self.end_position)] = set(
            completion_locations.get(entity_key, set())
        )
        return evidence


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
    trajectory: MovementTrajectory = Field(
        default=MovementTrajectory.PATH,
        description="Typed trajectory shared by every step in the movement action.",
    )
    committed: bool = Field(
        default=False,
        description="Whether the entity position was committed to the destination cell.",
    )

    def completion_position_observer_evidence(
        self,
        completion_locations: Dict[str, Set[str]],
    ) -> Dict[str, Set[str]]:
        """Freeze independent pre-step and post-step coordinate grants."""
        entity_key = str(self.source_entity_uuid)
        evidence = super().completion_position_observer_evidence(
            completion_locations
        )
        evidence[position_evidence_key(self.from_position)] = set(
            self.located_entity_observer_uuids.get(entity_key, set())
        )
        evidence[position_evidence_key(self.to_position)] = set(
            completion_locations.get(entity_key, set())
        )
        return evidence

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
                "movement_cost": self.movement_cost,
                "trajectory": self.trajectory.value,
                "committed": self.committed,
            },
            success=True
        )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        return {self.from_position, self.to_position}


class RangeType(str, Enum):
    REACH = "Reach"
    RANGE = "Range"
    SELF = "Self"


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
    """Damage dice specification plus damage type."""

    name: str = Field(default="Damage", description="Human-readable damage label.")
    damage_dice: Literal[4, 6, 8, 10, 12, 20] = Field(
        description="Number of sides on each damage die."
    )
    dice_numbers: int = Field(
        description="Number of damage dice to roll."
    )
    damage_bonus: Optional[ModifiableValue] = Field(
        default=None,
        description="Modifiable flat bonus added to damage rolls."
    )
    damage_type: DamageType = Field(
        description="Damage type applied to this damage packet."
    )

    def get_dice(self, attack_outcome: AttackOutcome, crit_extra_dice: int = 0) -> Dice:
        """Build a `Dice` object for this damage packet.

        Args:
            attack_outcome: Attack outcome used for critical-damage handling.
            crit_extra_dice: Extra critical dice to add beyond the base rule.

        Returns:
            Dice configured for a damage roll.
        """
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
        """Build a `Dice` object for this healing packet."""
        assert self.healing_bonus is not None, "Healing requires healing_bonus to be set"
        return Dice(
            count=self.dice_numbers,
            value=self.healing_dice,
            bonus=self.healing_bonus,
            roll_type=RollType.HEAL
        )


class RollModificationOperation(str, Enum):
    """Closed operation applied to an effective dice result."""

    REPLACE = "replace"
    APPEND = "append"


class RollModification(BaseModel):
    """Typed audit fact for one handler-owned dice-result change.

    Replacement facts carry the effective total that was replaced. Append
    facts identify the newly appended damage-packet index and have no previous
    total.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: RollModificationOperation = Field(
        description="Whether the handler replaced a roll or appended a damage packet.",
    )
    handler_name: str = Field(
        min_length=1,
        description="Human-readable handler that owned the change.",
    )
    packet_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="Damage-packet index; absent for single-roll replacements.",
    )
    previous_total: Optional[int] = Field(
        default=None,
        description="Effective total replaced by this change; absent for append operations.",
    )
    final_total: int = Field(
        description="Effective total after replacement or the appended packet total.",
    )
    reason: str = Field(
        min_length=1,
        description="Rules-facing reason for the change.",
    )

    @model_validator(mode="after")
    def validate_operation_shape(self) -> "RollModification":
        """Reject ambiguous replacement and append audit facts."""
        if (
            self.operation is RollModificationOperation.REPLACE
            and self.previous_total is None
        ):
            raise ValueError("roll replacement requires previous_total")
        if self.operation is RollModificationOperation.APPEND:
            if self.packet_index is None:
                raise ValueError("roll append requires packet_index")
            if self.previous_total is not None:
                raise ValueError("roll append cannot carry previous_total")
        return self


class DiceRollResultEvent(Event):
    """Abstract base for post-roll, pre-application dice interception.

    Result processors such as Lucky, Great Weapon Fighting, or healing dice
    maximizers modify these events after dice have been rolled but before the
    consuming action applies the result. Concrete result events own distinct
    dispatch categories; the base itself is never published.
    """

    roll_type: RollType = Field(
        ...,
        description="Roll category used by handlers to decide eligibility.",
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary handler context carried with the roll result.",
    )
    roll_modifications: List[RollModification] = Field(
        default_factory=list,
        description="Typed ordered audit facts describing handler-owned roll changes.",
    )

    def _combat_log_packet_details(
        self,
        modification: RollModification,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Return optional damage-packet display facts for one modification."""
        return None, None

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Project actual result changes into one causal combat-log child."""
        if not self.roll_modifications:
            return None

        facts: List[RollModificationLogFact] = []
        detail_lines: List[str] = []
        for modification in self.roll_modifications:
            damage_type, dice_expression = self._combat_log_packet_details(
                modification,
            )
            fact = RollModificationLogFact(
                operation=modification.operation.value,
                handler_name=modification.handler_name,
                packet_index=modification.packet_index,
                previous_total=modification.previous_total,
                final_total=modification.final_total,
                reason=modification.reason,
                packet_damage_type=damage_type,
                packet_dice=dice_expression,
            )
            facts.append(fact)
            if modification.operation is RollModificationOperation.REPLACE:
                locus = (
                    f"damage packet {modification.packet_index}"
                    if modification.packet_index is not None
                    else f"{self.roll_type.value.lower()} roll"
                )
                detail_lines.append(
                    f"{modification.handler_name}: {locus} "
                    f"{modification.previous_total} → {modification.final_total} "
                    f"({modification.reason})"
                )
            else:
                packet_description = "damage packet"
                if dice_expression and damage_type:
                    packet_description = f"{dice_expression} {damage_type} damage"
                detail_lines.append(
                    f"{modification.handler_name}: added {packet_description} "
                    f"for {modification.final_total} "
                    f"({modification.reason})"
                )

        handler_names = list(dict.fromkeys(
            modification.handler_name
            for modification in self.roll_modifications
        ))
        source_name = self.source_entity_name or "Roll"
        compact = (
            f"{md_color(source_name, 'cyan')}'s roll changed: "
            f"{', '.join(handler_names)}"
        )
        verbose = f"{compact}\n  " + "\n  ".join(detail_lines)
        return CombatLogEntry(
            entry_type=CombatLogEntryType.ROLL_MODIFICATION,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=self.target_entity_name,
            target_uuid=(
                str(self.target_entity_uuid)
                if self.target_entity_uuid is not None
                else None
            ),
            compact=compact,
            verbose=verbose,
            detailed=verbose,
            data=RollModificationLogData(
                roll_type=self.roll_type.value.lower(),
                modifications=facts,
            ).model_dump(mode="json"),
        )


class D20RollResultEvent(DiceRollResultEvent):
    """Generic d20 result event when no attack/save/check subtype applies."""

    event_type: EventType = Field(
        default=EventType.D20_ROLL_RESULT,
        description="Base event category for d20 result interception.",
    )
    original_roll: DiceRoll = Field(..., description="Immutable d20 roll kept for audit.")
    final_roll: Optional[DiceRoll] = Field(
        default=None,
        description="Replacement d20 roll after handlers modify the result.",
    )
    dc: Optional[int] = Field(default=None, description="Difficulty class or armor class, if known.")
    bonus: Optional[ModifiableValue] = Field(default=None, description="Modifiers used for the d20 roll.")
    result: Optional[bool] = Field(default=None, description="Success flag set after the outcome is evaluated.")

    @model_validator(mode="after")
    def validate_roll_categories(self) -> "D20RollResultEvent":
        """Keep original and replacement rolls in this event's d20 category."""
        if self.original_roll.roll_type is not self.roll_type:
            raise ValueError("d20 original_roll must match event roll_type")
        if (
            self.final_roll is not None
            and self.final_roll.roll_type is not self.roll_type
        ):
            raise ValueError("d20 final_roll must match event roll_type")
        return self

    def replace_roll(
        self,
        new_roll: DiceRoll,
        handler_name: str,
        reason: str,
    ) -> Self:
        """Return a new event value with the effective d20 roll replaced.

        Args:
            new_roll: Replacement roll result.
            handler_name: Name of the handler making the replacement.
            reason: Human-readable reason for the replacement.

        Returns:
            Modified event value for the queue to store as handler evidence.
        """
        if new_roll.roll_type is not self.roll_type:
            raise ValueError("d20 replacement roll must match event roll_type")
        old_total = self.get_effective_roll().total
        modification = RollModification(
            operation=RollModificationOperation.REPLACE,
            handler_name=handler_name,
            previous_total=old_total,
            final_total=new_roll.total,
            reason=reason,
        )
        return self.with_updates(
            final_roll=new_roll,
            roll_modifications=[*self.roll_modifications, modification],
        )

    def get_effective_roll(self) -> DiceRoll:
        """Return final_roll if modified, otherwise original roll."""
        return (
            self.final_roll
            if self.final_roll is not None
            else self.original_roll
        )


class AttackD20RollResultEvent(D20RollResultEvent):
    """D20 result event for attack rolls."""

    event_type: EventType = Field(
        default=EventType.ATTACK_D20_ROLL_RESULT,
        description="Event category for attack d20 result interception.",
    )
    roll_type: RollType = Field(default=RollType.ATTACK, description="Roll category for attack d20 results.")
    weapon_slot: Optional[WeaponSlot] = Field(default=None, description="Weapon slot used for the attack.")


class SavingThrowD20RollResultEvent(D20RollResultEvent):
    """D20 result event for saving throws."""

    event_type: EventType = Field(
        default=EventType.SAVE_D20_ROLL_RESULT,
        description="Event category for saving throw d20 result interception.",
    )
    roll_type: RollType = Field(default=RollType.SAVE, description="Roll category for saving throw d20 results.")
    ability_name: Optional[AbilityName] = Field(
        default=None,
        description="Ability used for the saving throw; absent for ability-neutral death saves.",
    )


class SkillCheckD20RollResultEvent(D20RollResultEvent):
    """D20 result event for skill checks."""

    event_type: EventType = Field(
        default=EventType.CHECK_D20_ROLL_RESULT,
        description="Event category for skill check d20 result interception.",
    )
    roll_type: RollType = Field(default=RollType.CHECK, description="Roll category for skill check d20 results.")
    skill_name: Optional[SkillName] = Field(
        default=None,
        description="Skill used for the check; absent for a generic ability check.",
    )


class DamageRollPacket(BaseModel):
    """One typed damage definition and its original/effective roll result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    damage: Damage = Field(
        description="Damage definition that produced this packet.",
    )
    original_roll: DiceRoll = Field(
        description="Immutable damage roll captured before result handlers.",
    )
    final_roll: DiceRoll = Field(
        description="Effective damage roll consumed after result handlers.",
    )

    @model_validator(mode="after")
    def validate_roll_types(self) -> "DamageRollPacket":
        """Require both packet rolls to remain damage-category results."""
        if self.original_roll.roll_type is not RollType.DAMAGE:
            raise ValueError("damage packet original_roll must be a damage roll")
        if self.final_roll.roll_type is not RollType.DAMAGE:
            raise ValueError("damage packet final_roll must be a damage roll")
        return self


class DamageRollResultEvent(DiceRollResultEvent):
    """Damage-roll result event fired before damage is applied.

    Handlers replace a packet's effective roll while its original roll remains
    available for audit. They may also append complete packets for effects such
    as Divine Smite or monster bonus damage.
    """

    name: str = Field(default="Damage Roll Result", description="Human-readable damage-roll result label.")
    event_type: EventType = Field(
        default=EventType.DAMAGE_ROLL_RESULT,
        description="Event category for damage-roll result interception.",
    )
    roll_type: RollType = Field(default=RollType.DAMAGE, description="Roll category for damage results.")
    weapon_slot: WeaponSlot = Field(description="Weapon slot used for the attack.")
    attack_outcome: AttackOutcome = Field(description="Attack outcome associated with this damage roll.")
    damage_packets: List[DamageRollPacket] = Field(
        min_length=1,
        description=(
            "Ordered damage definitions with their original and effective "
            "rolls; one record is the indivisible rules packet."
        ),
    )

    @model_validator(mode="after")
    def validate_roll_category(self) -> "DamageRollResultEvent":
        """Require the event discriminator to remain damage-category."""
        if self.roll_type is not RollType.DAMAGE:
            raise ValueError("damage result event roll_type must be damage")
        return self

    def _combat_log_packet_details(
        self,
        modification: RollModification,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Project the affected damage packet's type and dice expression."""
        packet_index = modification.packet_index
        if packet_index is None or packet_index >= len(self.damage_packets):
            return None, None
        damage = self.damage_packets[packet_index].damage
        return (
            damage.damage_type.value.lower(),
            f"{damage.dice_numbers}d{damage.damage_dice}",
        )

    def replace_roll(
        self,
        packet_index: int,
        new_roll: DiceRoll,
        handler_name: str,
        reason: str,
    ) -> Self:
        """Return a new event value with one effective damage roll replaced.

        Args:
            packet_index: Index of the damage packet to replace.
            new_roll: Replacement damage roll.
            handler_name: Name of the handler making the replacement.
            reason: Human-readable reason for the replacement.

        Returns:
            Modified event value for the queue to store as handler evidence.
        """
        old_packet = self.damage_packets[packet_index]
        damage_packets = list(self.damage_packets)
        damage_packets[packet_index] = DamageRollPacket(
            damage=old_packet.damage,
            original_roll=old_packet.original_roll,
            final_roll=new_roll,
        )
        modification = RollModification(
            operation=RollModificationOperation.REPLACE,
            handler_name=handler_name,
            packet_index=packet_index,
            previous_total=old_packet.final_roll.total,
            final_total=new_roll.total,
            reason=reason,
        )
        return self.with_updates(
            damage_packets=damage_packets,
            roll_modifications=[*self.roll_modifications, modification],
        )

    def append_damage_roll(
        self,
        damage: Damage,
        roll: DiceRoll,
        handler_name: str,
        reason: str,
    ) -> Self:
        """Return a new event value with one typed damage packet appended."""
        packet_index = len(self.damage_packets)
        modification = RollModification(
            operation=RollModificationOperation.APPEND,
            handler_name=handler_name,
            packet_index=packet_index,
            final_total=roll.total,
            reason=reason,
        )
        return self.with_updates(
            damage_packets=[
                *self.damage_packets,
                DamageRollPacket(
                    damage=damage,
                    original_roll=roll,
                    final_roll=roll,
                ),
            ],
            roll_modifications=[*self.roll_modifications, modification],
        )


class HealRollResultEvent(DiceRollResultEvent):
    """Healing-roll result event fired before healing is applied.

    Mirrors the damage-roll result pattern for effects that maximize or replace
    healing dice.
    """

    name: str = Field(default="Heal Roll Result", description="Human-readable healing-roll result label.")
    event_type: EventType = Field(
        default=EventType.HEAL_ROLL_RESULT,
        description="Event category for healing-roll result interception.",
    )
    roll_type: RollType = Field(default=RollType.HEAL, description="Roll category for healing results.")
    spell_name: str = Field(default="", description="Name of the healing spell or effect.")
    original_roll: DiceRoll = Field(description="Original immutable healing roll.")
    final_roll: DiceRoll = Field(description="Healing roll to apply after handler modifications.")

    @model_validator(mode="after")
    def validate_roll_categories(self) -> "HealRollResultEvent":
        """Require healing events to contain only healing-category rolls."""
        if self.roll_type is not RollType.HEAL:
            raise ValueError("heal result event roll_type must be heal")
        if self.original_roll.roll_type is not RollType.HEAL:
            raise ValueError("heal original_roll must be a healing roll")
        if self.final_roll.roll_type is not RollType.HEAL:
            raise ValueError("heal final_roll must be a healing roll")
        return self

    def replace_roll(
        self,
        new_roll: DiceRoll,
        handler_name: str,
        reason: str,
    ) -> Self:
        """Return a new event value with the effective healing roll replaced.

        Args:
            new_roll: Replacement healing roll.
            handler_name: Name of the handler making the replacement.
            reason: Human-readable reason for the replacement.

        Returns:
            Modified event value for the queue to store as handler evidence.
        """
        if new_roll.roll_type is not RollType.HEAL:
            raise ValueError("heal replacement roll must be a healing roll")
        modification = RollModification(
            operation=RollModificationOperation.REPLACE,
            handler_name=handler_name,
            previous_total=self.final_roll.total,
            final_total=new_roll.total,
            reason=reason,
        )
        return self.with_updates(
            final_roll=new_roll,
            roll_modifications=[*self.roll_modifications, modification],
        )


class TakeDamageEvent(Event):
    """Damage-application event for tracking, reduction, and cancellation.

    Handlers use this event to reduce, replace, cancel, or react to incoming
    damage. `final_damage` overrides `total_damage` when present.
    """

    name: str = Field(default="Take Damage", description="Human-readable damage-application label.")
    event_type: EventType = Field(
        default=EventType.TAKE_DAMAGE,
        description="Event category for damage application.",
    )
    total_damage: int = Field(description="Total damage before any modifications")
    damage_rolls: List[DiceRoll] = Field(default_factory=list, description="Individual damage rolls")
    damages: List['Damage'] = Field(default_factory=list, description="Damage specifications (types)")
    effect_id: Optional[str] = Field(
        default=None,
        description="Stable identity of the effect causing this damage application.",
    )
    final_damage: Optional[int] = Field(
        default=None,
        description="Modified damage after handlers. If None, use total_damage."
    )
    normal_hit_point_damage_cap: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "Maximum normal hit points this packet may remove after defenses and temporary hit points. "
            "Multiple survival effects compose by retaining the lowest cap."
        ),
    )
    resulting_hp: Optional[int] = Field(
        default=None,
        description="Entity HP after damage applied (set at EFFECT phase)"
    )
    resolution: Optional[DamageResolution] = Field(
        default=None,
        description="Factual defense and hit-point allocation attached at completion.",
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
        source_name = self.source_entity_name or "terrain"

        damage = self.get_effective_damage()

        damage_type_str = "damage"
        if self.damages:
            damage_type_str = str(self.damages[0].damage_type.value).lower()

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
                data=DamageTakenLogData(
                    target_name=target_name,
                    damage=0,
                    damage_type=damage_type_str,
                    source_name=source_name,
                    effect_id=self.effect_id,
                    blocked=True,
                    blocked_reason=reason,
                ).model_dump(exclude_none=True),
                success=False
            )

        compact_text = f"{md_color(target_name, 'yellow')} takes {md_color(str(damage), 'red')} {damage_type_str}"

        verbose_text = f"{md_color(target_name, 'yellow')} takes {md_color(str(damage), 'red')} {damage_type_str}"
        if source_name and source_name != "terrain":
            verbose_text += f" from {md_color(source_name, 'cyan')}"

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
            data=DamageTakenLogData(
                target_name=target_name,
                damage=damage,
                damage_type=damage_type_str,
                source_name=source_name,
                effect_id=self.effect_id,
            ).model_dump(exclude_none=True),
            success=True
        )


class DamageAppliedEvent(Event):
    """Factual post-mitigation boundary for positive damage.

    `TakeDamageEvent` represents the interruptible incoming packet. This event
    is emitted only after defenses and temporary hit points have been applied,
    and only when a positive amount of damage was actually absorbed or lost.
    Consequences of taking damage subscribe to this event rather than the
    mutable incoming packet.
    """

    name: str = Field(default="Damage Applied", description="Human-readable applied-damage label.")
    event_type: EventType = Field(
        default=EventType.DAMAGE_APPLIED,
        description="Event category for a positive post-mitigation damage result.",
    )
    applied_damage: int = Field(
        gt=0,
        description="Positive damage remaining after defenses, including temporary hit points lost.",
    )
    normal_hit_point_damage: int = Field(
        ge=0,
        description="Damage applied beyond temporary hit points to the normal hit-point pool.",
    )
    temporary_hit_point_damage: int = Field(
        ge=0,
        description="Temporary hit points consumed by the damage application.",
    )
    resulting_normal_hp: int = Field(
        description="Target normal hit points immediately after damage application.",
    )
    resulting_temporary_hp: int = Field(
        ge=0,
        description="Target temporary hit points immediately after damage application.",
    )
    damage_type: DamageType = Field(description="Primary damage type used by the incoming packet.")
    damages: List['Damage'] = Field(
        default_factory=list,
        description="Typed damage components carried by the incoming packet.",
    )
    effect_id: Optional[str] = Field(
        default=None,
        description="Stable identity of the effect that caused the applied damage.",
    )
    resolution: Optional[DamageResolution] = Field(
        default=None,
        description="Complete resolution of the parent incoming damage packet.",
    )


class HealEvent(Event):
    """Healing-application event for HP restoration and blocking."""

    name: str = Field(default="Heal", description="Human-readable healing event label.")
    event_type: EventType = Field(default=EventType.HEAL, description="Event category for healing application.")
    total_healing: int = Field(default=0, description="Requested healing amount before HP caps.")
    actual_healing: int = Field(default=0, description="HP actually restored after caps and blockers.")
    source_description: str = Field(default="", description="Human-readable description of the healing source.")
    was_blocked: bool = Field(default=False, description="Whether healing was blocked by an effect.")
    spell_level: int = Field(default=0, description="Spell level used, or 0 for non-spell healing.")

    resulting_hp: Optional[int] = Field(
        default=None,
        description="Entity HP after healing applied (set at EFFECT phase)"
    )
    resulting_normal_hp: Optional[int] = Field(
        default=None,
        description="Entity normal hit points immediately after healing.",
    )
    resulting_temporary_hp: Optional[int] = Field(
        default=None,
        ge=0,
        description="Entity temporary hit points immediately after healing.",
    )

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Generate a combat log entry for healing application."""
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


class EncounterEvent(Event):
    """Base event for encounter lifecycle."""

    name: str = Field(default="Encounter Event", description="Human-readable encounter event label.")
    encounter_uuid: UUID = Field(description="Encounter whose lifecycle changed.")
    combatant_uuids: List[UUID] = Field(default_factory=list, description="Combatants participating in the encounter.")


class EncounterStartEvent(EncounterEvent):
    """Fired when an encounter begins."""

    name: str = Field(default="Encounter Start", description="Human-readable encounter-start label.")
    event_type: EventType = Field(
        default=EventType.ENCOUNTER_START,
        description="Event category for encounter start.",
    )
    initiative_order: List[UUID] = Field(default_factory=list, description="Combatants sorted by initiative.")


class EncounterEndEvent(EncounterEvent):
    """Fired when an encounter ends."""

    name: str = Field(default="Encounter End", description="Human-readable encounter-end label.")
    event_type: EventType = Field(
        default=EventType.ENCOUNTER_END,
        description="Event category for encounter end.",
    )
    reason: Optional[str] = Field(default=None, description="Reason the encounter ended.")


class RoundEvent(Event):
    """Base event for round lifecycle."""

    name: str = Field(default="Round Event", description="Human-readable round event label.")
    encounter_uuid: UUID = Field(description="Encounter whose round changed.")
    round_number: int = Field(description="Current 1-indexed round number.")


class RoundStartEvent(RoundEvent):
    """Fired at the start of a new round."""

    name: str = Field(default="Round Start", description="Human-readable round-start label.")
    event_type: EventType = Field(default=EventType.ROUND_START, description="Event category for round start.")


class RoundEndEvent(RoundEvent):
    """Fired at the end of a round."""

    name: str = Field(default="Round End", description="Human-readable round-end label.")
    event_type: EventType = Field(default=EventType.ROUND_END, description="Event category for round end.")


class TurnEvent(Event):
    """Base event for turn lifecycle."""

    name: str = Field(default="Turn Event", description="Human-readable turn event label.")
    encounter_uuid: UUID = Field(description="Encounter whose turn order advanced.")
    entity_uuid: UUID = Field(description="Entity whose turn is represented.")
    round_number: int = Field(description="Current round number.")
    turn_index: int = Field(description="0-indexed position in initiative order.")


class TurnStartEvent(TurnEvent):
    """Fired at the start of an entity's turn."""

    name: str = Field(default="Turn Start", description="Human-readable turn-start label.")
    event_type: EventType = Field(default=EventType.TURN_START, description="Event category for turn start.")
    actions_available: int = Field(default=1, description="Actions available at turn start.")
    bonus_actions_available: int = Field(default=1, description="Bonus actions available at turn start.")
    movement_available: int = Field(default=30, description="Movement available at turn start, in feet.")
    reaction_available: int = Field(default=1, description="Reactions available at turn start.")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for turn start."""
        entity_name = self.source_entity_name or "Unknown"

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

    name: str = Field(default="Turn End", description="Human-readable turn-end label.")
    event_type: EventType = Field(default=EventType.TURN_END, description="Event category for turn end.")
    actions_used: int = Field(default=0, description="Actions spent during this turn.")
    bonus_actions_used: int = Field(default=0, description="Bonus actions spent during this turn.")
    movement_used: int = Field(default=0, description="Movement spent during this turn, in feet.")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for turn end."""
        entity_name = self.source_entity_name or "Unknown"

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


class LifeStateChangeEvent(Event):
    """Typed transition of an entity's authoritative health life state."""

    name: str = Field(default="Life State Change", description="Human-readable lifecycle transition label.")
    event_type: EventType = Field(
        default=EventType.LIFE_STATE_CHANGE,
        description="Event category for authoritative life-state transitions.",
    )
    entity_uuid: UUID = Field(description="Entity whose life state is changing.")
    entity_name: str = Field(default="", description="Display name of the affected entity.")
    previous_state: LifeState = Field(description="Authoritative state before execution.")
    new_state: LifeState = Field(description="Authoritative state after the transition.")
    reason: LifeStateChangeReason = Field(description="Rules-facing cause of the transition.")
    normal_hit_points: int = Field(
        default=0,
        description="Normal hit points observed when the transition was requested.",
    )


class ReviveEvent(Event):
    """Typed revival request with revival-specific condition options."""

    name: str = Field(default="Revive", description="Human-readable revival label.")
    event_type: EventType = Field(default=EventType.REVIVE, description="Event category for revival.")
    entity_uuid: UUID = Field(description="Entity being restored to life.")
    entity_name: str = Field(default="", description="Display name of the revived entity.")
    hit_points: int = Field(default=1, ge=1, description="Normal hit points restored by revival.")
    reduce_exhaustion: bool = Field(
        default=True,
        description="Whether condition-owned revival rules may reduce Exhaustion.",
    )


class DeathSaveEvent(Event):
    """Fired when a player-style dying entity makes a death saving throw."""

    name: str = Field(default="Death Save", description="Human-readable death-save event label.")
    event_type: EventType = Field(default=EventType.DEATH_SAVE, description="Event category for death saving throws.")
    entity_uuid: UUID = Field(description="Entity making the death saving throw.")
    entity_name: str = Field(default="", description="Display name of the entity making the death save.")
    roll: Optional[DiceRoll] = Field(default=None, description="Effective d20 roll after result handlers.")
    natural_roll: Optional[int] = Field(default=None, description="Natural d20 face used for death-save special rules.")
    dc: int = Field(default=10, description="Death saving throw DC.")
    succeeded: bool = Field(default=False, description="Whether this death save succeeded.")
    successes: int = Field(default=0, ge=0, description="Death-save successes after this event.")
    failures: int = Field(default=0, ge=0, description="Death-save failures after this event.")
    became_stable: bool = Field(default=False, description="Whether this event stabilized the entity.")
    regained_hit_point: bool = Field(default=False, description="Whether a natural 20 restored 1 hit point.")
    died: bool = Field(default=False, description="Whether this event caused death.")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for a death saving throw."""
        entity_name = self.entity_name or self.source_entity_name or "Unknown"
        roll_total = self.roll.total if self.roll else 0
        natural = self.natural_roll if self.natural_roll is not None else roll_total
        outcome = "success" if self.succeeded else "failure"
        if self.regained_hit_point:
            outcome = "natural 20"
        elif self.died:
            outcome = "death"
        elif self.became_stable:
            outcome = "stable"

        text = (
            f"{md_color(entity_name, 'yellow')} death save "
            f"{md_color(str(natural), 'cyan')} vs DC {self.dc}: {outcome} "
            f"({self.successes} successes, {self.failures} failures)"
        )
        return CombatLogEntry(
            entry_type=CombatLogEntryType.SAVING_THROW,
            source_name=entity_name,
            source_uuid=str(self.entity_uuid),
            target_name=entity_name,
            target_uuid=str(self.entity_uuid),
            compact=text,
            verbose=text,
            detailed=text,
            data={
                "entity_name": entity_name,
                "entity_uuid": str(self.entity_uuid),
                "roll": roll_total,
                "natural_roll": natural,
                "dc": self.dc,
                "successes": self.successes,
                "failures": self.failures,
                "became_stable": self.became_stable,
                "regained_hit_point": self.regained_hit_point,
                "died": self.died,
            },
            success=self.succeeded or self.regained_hit_point or self.became_stable,
        )


class DeathEvent(Event):
    """Fired when an accepted rule transitions an entity to dead."""

    name: str = Field(default="Death", description="Human-readable death event label.")
    event_type: EventType = Field(default=EventType.DEATH, description="Event category for entity death.")
    entity_uuid: UUID = Field(description="Entity that died.")
    entity_name: str = Field(default="", description="Display name of the dead entity.")
    killer_uuid: Optional[UUID] = Field(default=None, description="Entity that dealt the killing blow, if known.")
    killer_name: str = Field(default="", description="Display name of the killer, if known.")
    final_hp: int = Field(default=0, description="Final HP value after lethal damage.")
    encounter_uuid: Optional[UUID] = Field(default=None, description="Encounter where the death occurred, if any.")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate combat log entry for death."""
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


class InstantDeathEvent(Event):
    """Interruptible event for effects that kill without dealing damage."""

    name: str = Field(default="Instant Death", description="Human-readable instant-death event label.")
    event_type: EventType = Field(default=EventType.INSTANT_DEATH, description="Event category for no-damage death effects.")
    entity_uuid: UUID = Field(description="Entity subjected to the instant-death effect.")
    entity_name: str = Field(default="", description="Display name of the affected entity.")
    killer_uuid: Optional[UUID] = Field(default=None, description="Entity or effect source causing the instant-death effect.")
    killer_name: str = Field(default="", description="Display name of the instant-death source, if known.")
    source_description: str = Field(default="", description="Rules-facing source or effect description.")
