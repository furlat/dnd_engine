"""Event lifecycle contracts, handler dispatch, and causal journal storage.

Concrete event facts live in the sibling event-family modules.  This module
never imports those families; every family depends one-way on this registry.
"""

from collections import defaultdict
from contextvars import ContextVar
from datetime import UTC, datetime
from enum import Enum
import logging
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Iterator,
    List,
    Optional,
    Protocol,
    Self,
    Sequence,
    Set,
    Tuple,
    TypeVar,
    Union,
    cast,
    runtime_checkable,
)
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from dnd.core.base_object import BaseObject
from dnd.core.combat_log import (
    CombatLogEntry,
    CombatLogEntryType,
    damage_total_from_log_data,
)
from dnd.core.behavior_context import active_behavior, behavior_scope
from dnd.types.behaviors import (
    EffectiveHandlerPresentation,
    HandlerDispatchEvidence,
    HandlerDispatchOutcome,
    RuntimeBehaviorKind,
    validate_behavior_id,
)
from dnd.types.effects import EffectOrigin

logger = logging.getLogger(__name__)

EventT = TypeVar("EventT", bound="Event")
E = TypeVar("E", bound="Event")
EventProcessor = Callable[[E, UUID], Optional[E]]

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
    TEMPORARY_HIT_POINTS = "temporary_hit_points"
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
    TRAVERSAL_CONNECTOR_CHANGED = "traversal_connector_changed"

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
    SPATIAL_EFFECT_CHANGED = "spatial_effect_changed"
    MOVEMENT_COLLISION = "movement_collision"
    SENSORY_UPDATE = "sensory_update"
    SPATIAL_EFFECT_INTERACTION = "spatial_effect_interaction"
    WORLD_INITIALIZED = "world_initialized"

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

    ENTITY_CREATED = "entity_created"
    ENTITY_LEVEL_ADDED = "entity_level_added"
    ENTITY_LEVEL_REMOVED = "entity_level_removed"

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

ordered_event_phases = [
    EventPhase.DECLARATION,
    EventPhase.EXECUTION,
    EventPhase.EFFECT,
    EventPhase.COMPLETION,
]

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
    _handler_validation_token: Optional[UUID] = PrivateAttr(default=None)
    inert_terminal_fact: ClassVar[bool] = False
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
        *,
        completion_committed: bool,
    ) -> Dict[str, Set[str]]:
        """Return coordinate grants to freeze onto the completion version."""
        del completion_locations
        del completion_committed
        return {
            key: set(observer_uuids)
            for key, observer_uuids in self.located_position_observer_uuids.items()
        }

    def resolve_sub_events(self) -> None:
        """Resolve concrete child mechanics before a terminal is stored."""

    def finalize_terminal(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Build terminal evidence from the currently stored causal journal."""
        completion_updates = dict(updates)
        if EventQueue._identified_entity_observer_computer is not None:
            completion_updates["located_entity_observer_uuids"] = {
                entity_uuid: set(observer_uuids)
                for entity_uuid, observer_uuids in (
                    EventQueue._identified_entity_observer_computer(self).items()
                )
            }
        completion_locations = completion_updates.get(
            "located_entity_observer_uuids",
            self.located_entity_observer_uuids,
        )
        completion_updates["located_position_observer_uuids"] = (
            self.completion_position_observer_evidence(
                completion_locations,
                completion_committed=(
                    completion_updates.get("committed") is True
                ),
            )
        )

        terminal_lineage_members = EventQueue._events_by_lineage.get(
            self.lineage_uuid,
            [],
        )
        terminal_lineage_uuids = {
            event.uuid for event in terminal_lineage_members
        }
        terminal_lineage_uuids.add(self.uuid)
        terminal_start = len(EventQueue._all_events)
        for index, event in enumerate(EventQueue._all_events):
            if event.uuid in terminal_lineage_uuids:
                terminal_start = index
                break

        direct_child_lineages: List[UUID] = []
        journal_suffix = EventQueue._all_events[terminal_start:]
        for candidate in journal_suffix:
            if candidate.lineage_uuid == self.lineage_uuid:
                continue
            current = candidate
            visited_parent_uuids: Set[UUID] = set()
            while current.parent_event is not None:
                parent_uuid = current.parent_event
                if parent_uuid in visited_parent_uuids:
                    break
                visited_parent_uuids.add(parent_uuid)
                parent = EventQueue._events_by_uuid.get(parent_uuid)
                if parent is None:
                    break
                if parent.uuid in terminal_lineage_uuids:
                    if current.lineage_uuid not in direct_child_lineages:
                        direct_child_lineages.append(current.lineage_uuid)
                    break
                current = parent

        direct_child_lineage_set = set(direct_child_lineages)
        direct_children = [
            event.uuid
            for event in journal_suffix
            if event.lineage_uuid in direct_child_lineage_set
        ]
        completion_updates["lineage_children_events"] = list(direct_children)
        completion_updates["children_events"] = list(direct_children)

        if self.parent_event:
            parent = EventQueue.get_event_by_uuid(self.parent_event)
            if parent:
                completion_updates["parent_lineage"] = parent.lineage_uuid

        completion_updates["children_lineages"] = list(direct_child_lineages)

        try:
            temp_event = self.model_copy(update=completion_updates)
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
                    combat_log.revealed_entity_uuids |= EventQueue._revealed_computer(
                        temp_event,
                        child_logs or [],
                    )

                completion_updates["combat_log"] = combat_log
        except Exception:
            logger.exception(
                "Combat-log projection failed for %s event %s at phase %s",
                type(self).__name__,
                self.uuid,
                EventPhase.COMPLETION,
            )
        return completion_updates

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

        Completion resolves stable parent/child lineage metadata and attaches
        any generated combat log to the terminal fact.

        Args:
            new_phase: Phase to transition to. When omitted, the next ordered
                phase is used.
            status_message: Optional message explaining the phase change.
            **updates: Additional model fields to apply to the new event version.

        Returns:
            The new event version after queue registration and handler dispatch.
        """
        if self.phase in (EventPhase.COMPLETION, EventPhase.CANCEL):
            return self

        if new_phase is None:
            new_phase = ordered_event_phases[ordered_event_phases.index(self.phase) + 1]

        if new_phase is EventPhase.CANCEL:
            return self.cancel(status_message=status_message, **updates)

        if EventQueue.is_active_handler_proposal(self):
            handler_updates: Dict[str, Any] = {"phase": new_phase}
            if status_message is not None:
                handler_updates["status_message"] = status_message
            handler_updates.update(updates)
            return self.post(**handler_updates)

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
            existing_terminal = EventQueue._stored_terminal_for_lineage(
                self.lineage_uuid,
            )
            if existing_terminal is not None:
                return cast(Self, existing_terminal)
            self.resolve_sub_events()
            phase_updates = self.finalize_terminal(phase_updates)
        else:
            phase_updates['lineage_children_events'] = self.lineage_children_events + self.children_events
            phase_updates['children_events'] = []

        return self.post(**phase_updates)

    def cancel(self, status_message: Optional[str] = None, **updates) -> Self:
        """Mark this event as canceled and post the cancel version.

        Args:
            status_message: Optional message explaining why the event was canceled.
            **updates: Additional model fields to apply to the cancel version.

        Returns:
            The cancel event version after queue registration.
        """
        existing_terminal = EventQueue._stored_terminal_for_lineage(
            self.lineage_uuid,
        )
        if existing_terminal is not None:
            return cast(Self, existing_terminal)

        cancel_updates = dict(updates)
        cancel_updates['canceled'] = True
        cancel_updates['phase'] = EventPhase.CANCEL
        cancel_updates['canceled_from_phase'] = self.canceled_from_phase or self.phase
        cancel_updates['is_first'] = True
        cancel_updates['is_last'] = True
        if status_message is not None:
            cancel_updates['status_message'] = status_message

        if not EventQueue.is_active_handler_proposal(self):
            cancel_updates = self.finalize_terminal(cancel_updates)
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
        updated_event = EventQueue.validate_active_handler_post(
            self,
            updated_event,
        )

        if updated_event.use_register:
            result = EventQueue.register(updated_event)
        else:
            result = updated_event

        if not isinstance(result, self.__class__):
            raise TypeError(f"Expected {self.__class__.__name__} but got {result.__class__.__name__}")

        return result

    def validate_handler_result(self, result: "Event") -> "Event":
        """Validate one handler-produced version before it is observable.

        Event families with immutable causal evidence may override this hook
        to convert an attempted rewrite into a valid cancellation. The default
        preserves the existing handler-mutation contract.
        """
        return result

    def guards_handler_result(self) -> bool:
        """Return whether handler proposals use the family validation guard.

        The default preserves the existing opt-in rule: an event family is
        guarded when it overrides :meth:`validate_handler_result`. Families
        with a narrower discriminant may override this selector.
        """
        return (
            type(self).validate_handler_result
            is not Event.validate_handler_result
        )

    def guarded_related_queue_inputs(self) -> tuple["Event", ...]:
        """Return queue-owned causal inputs restored after each guarded handler.

        Most event families own only the event version being dispatched. A
        guarded child family may override this hook when its handlers can
        resolve an already-stored parent whose causal evidence must remain
        immutable between handlers.
        """
        return ()

    def handler_result_stops_dispatch(self, result: "Event") -> bool:
        """Return whether a validated publication must remain terminal."""
        return result.canceled

    def handler_result_preserves_lifecycle(self, result: "Event") -> bool:
        """Return whether a handler preserved this dispatch boundary.

        A handler may return the same phase with modified domain fields or may
        cancel exactly the phase it received.  It may not advance, rewind, or
        disguise the lifecycle, change the lineage/event family, or alter the
        registration mode selected by the publisher.
        """
        if (
            type(result.event_type) is not type(self.event_type)
            or result.event_type is not self.event_type
            or type(result.lineage_uuid) is not type(self.lineage_uuid)
            or result.lineage_uuid != self.lineage_uuid
            or type(result.use_register) is not bool
            or result.use_register is not self.use_register
            or type(result.canceled) is not bool
        ):
            return False
        if result.canceled:
            return (
                result.phase is EventPhase.CANCEL
                and result.canceled_from_phase is self.phase
            )
        return (
            result.phase is self.phase
            and result.canceled_from_phase is self.canceled_from_phase
        )

    def invalid_handler_result_cancellation(
        self,
        result: "Event",
        *,
        status_message: str,
    ) -> "Event":
        """Build one exact cancellation for a rejected handler proposal."""
        result_uuid = result.uuid
        if type(result_uuid) is not UUID or result_uuid == self.uuid:
            result_uuid = uuid4()
        result_timestamp = result.timestamp
        if type(result_timestamp) is not datetime:
            result_timestamp = datetime.now(UTC)
        return self.model_copy(
            update={
                "uuid": result_uuid,
                "timestamp": result_timestamp,
                "lineage_uuid": self.lineage_uuid,
                "use_register": self.use_register,
                "modified": True,
                "canceled": True,
                "phase": EventPhase.CANCEL,
                "canceled_from_phase": self.phase,
                "status_message": status_message,
            },
        )

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

class SpatiallyIndexedEvent(Event):
    """Explicit base for events dispatched through one or more grid cells."""

    def spatial_dispatch_positions(self) -> tuple[Tuple[int, int], ...]:
        """Return canonical positions used by the spatial-handler index."""
        raise NotImplementedError

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
        damage = damage_total_from_log_data(child_data)
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

def _exact_event_evidence_equal(expected: Any, candidate: Any) -> bool:
    """Compare guarded event evidence without Python's bool/int equivalence."""
    if type(candidate) is not type(expected):
        return False
    if isinstance(expected, BaseModel):
        return all(
            _exact_event_evidence_equal(
                getattr(expected, field_name),
                getattr(candidate, field_name),
            )
            for field_name in type(expected).model_fields
        )
    if isinstance(expected, (list, tuple)):
        return len(expected) == len(candidate) and all(
            _exact_event_evidence_equal(left, right)
            for left, right in zip(expected, candidate)
        )
    if isinstance(expected, dict):
        return expected.keys() == candidate.keys() and all(
            _exact_event_evidence_equal(expected[key], candidate[key])
            for key in expected
        )
    if isinstance(expected, (set, frozenset)):
        return len(expected) == len(candidate) and all(
            any(
                _exact_event_evidence_equal(left, right)
                for right in candidate
            )
            for left in expected
        )
    return candidate == expected

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
    behavior_id: str = Field(
        default="system.unclassified",
        description="Direct renderer-independent handler identity.",
    )
    provided_by_id: Optional[str] = Field(
        default=None,
        description="Direct semantic identity that installed this handler.",
    )
    origin_root_id: Optional[str] = Field(
        default=None,
        description="Optional durable semantic root of this handler.",
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
        """Return the handler's direct semantic identity."""
        return self.behavior_id

    def bind_behavior_owner(self) -> None:
        """Finalize direct ownership before queue or block admission."""
        active = active_behavior()
        if self.semantic_key is not None:
            self.behavior_id = self.semantic_key
        elif self.behavior_id == "system.unclassified" and active is not None:
            self.behavior_id = active.behavior_id
        validate_behavior_id(self.behavior_id)
        if self.provided_by_id is None:
            self.provided_by_id = (
                active.behavior_id if active is not None else self.behavior_id
            )
        validate_behavior_id(self.provided_by_id, "provided_by_id")
        if self.origin_root_id is None and active is not None:
            self.origin_root_id = active.origin_root_id
        if self.origin_root_id is not None:
            validate_behavior_id(self.origin_root_id, "origin_root_id")

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

    def remove(self) -> bool:
        """Remove this handler from all spatial queue indexes."""
        return EventQueue.remove_spatial_handler(self.uuid)

class EventQueue:
    """Global event store and handler dispatcher.

    The queue keeps independent indexes for event history, trigger-based
    handlers, and position-indexed spatial handlers. It is intentionally
    class-scoped because the engine currently has one active event stream per
    process.
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

    # A single open root is enough to validate the append-only journal. Tree
    # boundaries are derived from ``_all_events`` by ``next_committed_tree``.
    _open_root_lineage: Optional[UUID] = None
    _open_root_type: Optional[type['Event']] = None
    _handler_dispatch_cursor: int = 0
    _preflight_depth: ContextVar[int] = ContextVar(
        "event_queue_preflight_depth",
        default=0,
    )
    _active_handler_input: ContextVar[Optional['Event']] = ContextVar(
        "event_queue_active_handler_input",
        default=None,
    )
    _active_handler_proposal: ContextVar[Optional['Event']] = ContextVar(
        "event_queue_active_handler_proposal",
        default=None,
    )
    _active_handler_validation_token: ContextVar[Optional[UUID]] = ContextVar(
        "event_queue_active_handler_validation_token",
        default=None,
    )
    _active_handler_storage_result: ContextVar[
        Optional[Tuple['Event', bool]]
    ] = ContextVar(
        "event_queue_active_handler_storage_result",
        default=None,
    )
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
    def _invoke_handler(cls, handler: BaseHandler, event: Event) -> Optional[Event]:
        """Invoke one matched handler and publish passive effect evidence."""
        before_cursor = cls.event_cursor()
        before_event_index = len(cls._all_events)
        guards_handler_result = event.guards_handler_result()
        validation_input = event.model_copy(deep=True) if guards_handler_result else event
        handler_entry_input = (
            validation_input.model_copy(deep=True)
            if guards_handler_result
            else event
        )
        related_inputs = (
            event.guarded_related_queue_inputs()
            if guards_handler_result
            else ()
        )
        related_validation_inputs = tuple(
            (related_input, related_input.model_copy(deep=True))
            for related_input in related_inputs
        )
        handler_input = (
            validation_input.model_copy(deep=True)
            if guards_handler_result
            else event
        )
        validation_token = uuid4() if guards_handler_result else None
        handler_input._handler_validation_token = validation_token
        handler_token = cls._active_handler_input.set(
            validation_input if guards_handler_result else None,
        )
        proposal_token = cls._active_handler_proposal.set(
            handler_input if guards_handler_result else None,
        )
        validation_token_context = (
            cls._active_handler_validation_token.set(validation_token)
        )
        storage_result_context = cls._active_handler_storage_result.set(None)
        detached_storage_result: Optional[Tuple[Event, bool]] = None
        result: Optional[Event] = None
        stored_input_tampered = False
        tampered_candidate: Optional[Event] = None
        try:
            handler.bind_behavior_owner()
            assert handler.provided_by_id is not None
            with behavior_scope(
                behavior_id=handler.behavior_id,
                provided_by_id=handler.provided_by_id,
                origin_root_id=handler.origin_root_id,
            ):
                result = handler(handler_input)
        finally:
            detached_storage_result = cls._active_handler_storage_result.get()
            if guards_handler_result:
                tampered_candidate = event.model_copy(deep=True)
                stored_input_tampered = cls._restore_guarded_handler_input(
                    event,
                    validation_input,
                    before_event_index,
                )
                validation_input.children_events = list(event.children_events)
                validation_input.lineage_children_events = list(
                    event.lineage_children_events
                )
                validation_input.children_lineages = list(
                    event.children_lineages
                )
                for related_input, related_validation_input in (
                    related_validation_inputs
                ):
                    cls._restore_guarded_handler_input(
                        related_input,
                        related_validation_input,
                        before_event_index,
                    )
            cls._active_handler_storage_result.reset(storage_result_context)
            cls._active_handler_validation_token.reset(
                validation_token_context,
            )
            cls._active_handler_proposal.reset(proposal_token)
            cls._active_handler_input.reset(handler_token)
        if stored_input_tampered:
            result = tampered_candidate
        elif detached_storage_result is not None:
            result = detached_storage_result[0]
        if result is not None and guards_handler_result:
            handler_changed_child_evidence = any(
                not _exact_event_evidence_equal(
                    getattr(handler_entry_input, field_name),
                    getattr(result, field_name),
                )
                for field_name in (
                    "children_events",
                    "lineage_children_events",
                    "children_lineages",
                )
            )
            if not handler_changed_child_evidence:
                result = result.model_copy(update={
                    "children_events": list(validation_input.children_events),
                    "lineage_children_events": list(
                        validation_input.lineage_children_events
                    ),
                    "children_lineages": list(
                        validation_input.children_lineages
                    ),
                }, deep=True)
            result = validation_input.validate_handler_result(result)
            public_candidate = result.model_copy(
                update={"use_register": validation_input.use_register},
                deep=True,
            )
            if _exact_event_evidence_equal(
                validation_input,
                public_candidate,
            ):
                result = event
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
        if (
            result is not None
            and evidence.effected
            and handler.content_kind is RuntimeBehaviorKind.REACTION
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
                    behavior_id=handler.behavior_id,
                    provided_by_id=(
                        handler.provided_by_id or handler.behavior_id
                    ),
                    origin_root_id=handler.origin_root_id,
                    source_entity_uuid=handler.source_entity_uuid,
                    triggering_event_uuid=event.uuid,
                    triggering_lineage_uuid=event.lineage_uuid,
                    emitted_lineage_uuids=emitted_lineages,
                    outcome=evidence.outcome,
                ),
            )
        cls._handler_dispatch_cursor += 1
        return result

    @classmethod
    def _restore_guarded_handler_input(
        cls,
        stored_input: Event,
        validation_input: Event,
        emitted_start_index: int,
    ) -> bool:
        """Restore a guarded stored input while retaining real child linkage."""
        expected = validation_input.model_copy(deep=True)
        expected_children = list(expected.children_events)
        expected_lineage_children = list(expected.lineage_children_events)
        for child in cls._all_events[emitted_start_index:]:
            if child.parent_event == validation_input.uuid:
                if child.uuid not in expected_children:
                    expected_children.append(child.uuid)
            parent = (
                cls._events_by_uuid.get(child.parent_event)
                if child.parent_event is not None
                else None
            )
            if (
                parent is not None
                and parent.lineage_uuid == validation_input.lineage_uuid
                and child.uuid not in expected_lineage_children
            ):
                expected_lineage_children.append(child.uuid)
        expected.children_events = expected_children
        expected.lineage_children_events = expected_lineage_children
        tampered = any(
            getattr(stored_input, field_name) != getattr(expected, field_name)
            for field_name in type(expected).model_fields
        )
        restored = expected.model_copy(deep=True)
        for field_name in type(restored).model_fields:
            setattr(stored_input, field_name, getattr(restored, field_name))
        stored_input._handler_validation_token = None
        return tampered

    @classmethod
    def event_cursor(cls) -> int:
        """Return the raw append cursor for the event stream."""
        return len(cls._all_events)

    @classmethod
    def _stored_terminal_for_lineage(cls, lineage_uuid: UUID) -> Optional[Event]:
        """Return the existing terminal journal fact for one event lineage."""
        for event in reversed(cls._events_by_lineage.get(lineage_uuid, [])):
            if event.is_last and event.phase in (
                EventPhase.COMPLETION,
                EventPhase.CANCEL,
            ):
                return event
        return None

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
    def register(cls, event: Event) -> Event:
        """Store an event version and dispatch matching pre-completion handlers.

        Args:
            event: Event version to index and potentially dispatch.

        Returns:
            The final event version after handler processing.
        """
        detached_proposal = cls._detach_active_handler_storage(event)
        if detached_proposal is not None:
            return detached_proposal
        stored_event = cls._events_by_uuid.get(event.uuid)
        if stored_event is event:
            return event
        if stored_event is not None:
            raise ValueError(f"Event UUID collision for {event.uuid}")
        cls._store_event(event)

        handlers = cls._get_handlers_for_event(event)
        if not handlers or event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL):
            return event

        current_event = event
        for handler in handlers:
            result = cls._invoke_handler(handler, current_event)

            if result is None:
                continue

            if result.canceled:
                existing_terminal = cls._stored_terminal_for_lineage(
                    result.lineage_uuid,
                )
                if existing_terminal is not None:
                    return existing_terminal
                completion_updates = result.finalize_terminal({
                    "phase": EventPhase.CANCEL,
                    "is_first": True,
                    "is_last": True,
                    "canceled": True,
                    "canceled_from_phase": result.canceled_from_phase,
                })
                result = result.model_copy(update=completion_updates)
                return cls._record_handler_result(result)

            if result.modified:
                current_event = cls._record_handler_result(result)

        return current_event

    @classmethod
    def validate_active_handler_post(
        cls,
        source: Event,
        candidate: Event,
    ) -> Event:
        """Validate a guarded handler's post before it can self-register.

        The proposal identity check distinguishes a same-family event version
        from ordinary child events emitted while the handler is running.  UUID
        and lineage fallbacks also cover a shallow copy of that proposal.
        """
        active_input = cls._active_handler_input.get()
        if active_input is None or not cls.is_active_handler_proposal(source):
            return candidate
        return active_input.validate_handler_result(candidate)

    @classmethod
    def _detach_active_handler_storage(
        cls,
        event: Event,
    ) -> Optional[Event]:
        """Validate and detach a guarded proposal before any storage path."""
        active_input = cls._active_handler_input.get()
        if active_input is None or not cls.is_active_handler_proposal(event):
            return None
        validated = active_input.validate_handler_result(event)
        terminal = active_input.handler_result_stops_dispatch(validated)
        retained = cls._active_handler_storage_result.get()
        if retained is None or not retained[1]:
            cls._active_handler_storage_result.set((validated, terminal))
        return validated

    @classmethod
    def is_active_handler_proposal(cls, source: Event) -> bool:
        """Return whether an event value derives from the guarded proposal."""
        active_input = cls._active_handler_input.get()
        active_proposal = cls._active_handler_proposal.get()
        active_token = cls._active_handler_validation_token.get()
        if (
            active_input is None
            or active_proposal is None
            or active_token is None
        ):
            return False
        return (
            source._handler_validation_token == active_token
            or source is active_proposal
            or source.uuid == active_input.uuid
            or source.lineage_uuid == active_input.lineage_uuid
        )

    @classmethod
    def publish_declaration(cls, event: EventT) -> EventT:
        """Publish an unregistered declaration and retain handler output.

        Args:
            event: Declaration event constructed with ``use_register=False``.

        Returns:
            The exact accepted, modified, or canceled declaration value.

        Raises:
            ValueError: If the event auto-registers or is not a declaration.
        """
        if event.use_register:
            raise ValueError(
                "Explicit declaration publication requires use_register=False"
            )
        if event.phase is not EventPhase.DECLARATION:
            raise ValueError(
                "Explicit declaration publication requires a declaration event"
            )
        published = cast(EventT, cls.register(event))
        return cast(
            EventT,
            published.model_copy(update={"use_register": True}),
        )

    @classmethod
    def publish_lifecycle(cls, event: EventT) -> Optional[EventT]:
        """Publish one unregistered event through the canonical lifecycle.

        The constructor must not auto-register because callers need the exact
        functional result returned by declaration handlers. Each accepted
        phase result is then the sole input to the next phase.

        Args:
            event: Unregistered declaration event to publish.

        Returns:
            Completed event, or ``None`` when a handler cancels a phase.

        Raises:
            ValueError: If the event auto-registers or does not begin at
                declaration.
        """
        current = cls.publish_declaration(event)
        if current.canceled:
            return None
        for phase in (
            EventPhase.EXECUTION,
            EventPhase.EFFECT,
            EventPhase.COMPLETION,
        ):
            current = current.phase_to(phase)
            if current.canceled:
                return None
        return current

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
                guards_handler_result = current_event.guards_handler_result()
                handler_input = (
                    current_event.model_copy()
                    if guards_handler_result
                    else current_event
                )
                result = handler(handler_input)
            finally:
                cls._preflight_depth.reset(depth_token)
            if cls.event_cursor() != before_cursor:
                raise RuntimeError(
                    f"Validation-only handler {handler.name!r} emitted an event during preflight"
                )
            if result is None:
                continue
            if guards_handler_result:
                result = current_event.validate_handler_result(result)
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
        detached_proposal = cls._detach_active_handler_storage(event)
        if detached_proposal is not None:
            return cast(EventT, detached_proposal)
        event.use_register = True
        event.timestamp = datetime.now(UTC)
        cls._store_event(event)
        return event

    @classmethod
    def publish_inert_terminal_fact(cls, event: EventT) -> EventT:
        """Store one reviewed terminal fact whose state is already committed."""
        if event.use_register:
            raise ValueError("Inert terminal facts must be constructed unregistered")
        if event.phase is not EventPhase.COMPLETION:
            raise ValueError("Inert terminal facts must already be in completion phase")
        if not type(event).inert_terminal_fact:
            raise ValueError(
                f"{type(event).__name__} is not an admitted inert terminal fact",
            )
        completion_updates = event.finalize_terminal({
            "phase": EventPhase.COMPLETION,
            "is_first": True,
            "is_last": True,
        })
        committed = event.model_copy(update={
            **completion_updates,
            "use_register": True,
            "timestamp": datetime.now(UTC),
        })
        cls._store_event(committed)
        return cast(EventT, committed)

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
    def _stored_root_for_event(cls, event: Event) -> Event:
        """Resolve a stored event's parent chain to its one root."""
        current = event
        visited: Set[UUID] = set()
        while current.parent_event is not None:
            if current.uuid in visited:
                raise ValueError("event parent cycle is not admissible")
            visited.add(current.uuid)
            parent = cls._events_by_uuid.get(current.parent_event)
            if parent is None:
                raise ValueError(
                    f"event {current.uuid} references missing parent {current.parent_event}"
                )
            current = parent
        return current

    @classmethod
    def _validate_event_admission(cls, event: Event) -> None:
        """Validate one event against the currently open append-only tree."""
        terminal_phases = (EventPhase.COMPLETION, EventPhase.CANCEL)
        phase_order = {
            EventPhase.DECLARATION: 0,
            EventPhase.EXECUTION: 1,
            EventPhase.EFFECT: 2,
            EventPhase.COMPLETION: 3,
        }
        is_terminal = event.phase in terminal_phases
        if is_terminal and not event.is_last:
            raise ValueError("terminal event must be the last event in its lineage")
        if type(event).inert_terminal_fact and event.phase is not EventPhase.COMPLETION:
            raise ValueError("an inert terminal fact must be completion-only")
        if event.phase is EventPhase.CANCEL and (
            not event.canceled or event.canceled_from_phase is None
        ):
            raise ValueError("cancel terminal must carry cancellation evidence")
        lineage_events = cls._events_by_lineage.get(event.lineage_uuid, [])
        if lineage_events and type(event) is not type(lineage_events[0]):
            raise ValueError("an event lineage must preserve its exact concrete class")

        if event.parent_event is None:
            opening_root = cls._open_root_lineage is None
            if opening_root:
                if not type(event).inert_terminal_fact and is_terminal:
                    raise ValueError(
                        "a non-inert terminal cannot open a root without a prior phase"
                    )
                elif event.phase not in phase_order:
                    raise ValueError("root must begin at a handler-visible lifecycle phase")
            elif (
                event.lineage_uuid != cls._open_root_lineage
                or type(event) is not cls._open_root_type
            ):
                raise ValueError(
                    "only the active root's exact class and lineage may be parentless"
                )

            if any(
                candidate.phase in terminal_phases and candidate.is_last
                for candidate in lineage_events
            ):
                raise ValueError("an event lineage cannot receive facts after its terminal")
            if lineage_events and not is_terminal:
                latest_phase = max(
                    phase_order.get(candidate.phase, -1)
                    for candidate in lineage_events
                )
                if phase_order[event.phase] < latest_phase:
                    raise ValueError("event phase cannot move backwards")
            if opening_root and not is_terminal:
                cls._open_root_lineage = event.lineage_uuid
                cls._open_root_type = type(event)
            return

        parent = cls._events_by_uuid.get(event.parent_event)
        if parent is None:
            raise ValueError(
                f"event {event.uuid} references missing parent {event.parent_event}"
            )
        if cls._stored_terminal_for_lineage(parent.lineage_uuid) is not None:
            raise ValueError("a closed lineage cannot receive a child event")
        if event.lineage_uuid == cls._open_root_lineage:
            raise ValueError("the active root lineage must remain parentless")
        root = cls._stored_root_for_event(parent)
        if (
            cls._open_root_lineage is None
            or root.lineage_uuid != cls._open_root_lineage
        ):
            raise ValueError("child event does not belong to the active root")
        if event.lineage_uuid == parent.lineage_uuid:
            raise ValueError("a parented event must have its own lineage")
        if any(
            candidate.phase in terminal_phases and candidate.is_last
            for candidate in lineage_events
        ):
            raise ValueError("an event lineage cannot receive facts after its terminal")
        if lineage_events and not is_terminal:
            latest_phase = max(
                phase_order.get(candidate.phase, -1)
                for candidate in lineage_events
            )
            if phase_order[event.phase] < latest_phase:
                raise ValueError("event phase cannot move backwards")

    @classmethod
    def next_committed_tree(
        cls,
        source_cursor: int,
        *,
        generation_id: Optional[UUID] = None,
    ) -> Optional[Tuple[Event, ...]]:
        """Return the next complete tree directly from the event journal.

        The queue stores no range or batch records.  A cursor must point to a
        parentless root; the terminal boundary is found by following the
        stored parent facts and the root's exact class/lineage.
        """
        if generation_id is not None and generation_id != cls._generation_uuid:
            raise RuntimeError("event queue generation changed before tree pull")
        cursor = cls.event_cursor()
        if not isinstance(source_cursor, int) or not 0 <= source_cursor <= cursor:
            raise ValueError("tree source cursor must be within the current queue")
        if source_cursor == cursor:
            return None
        first = cls._all_events[source_cursor]
        if first.parent_event is not None:
            raise ValueError("tree cursor must point at its parentless root")
        if type(first).inert_terminal_fact:
            if first.phase is not EventPhase.COMPLETION:
                raise ValueError("inert tree root must be a completion fact")
        elif first.phase in (EventPhase.COMPLETION, EventPhase.CANCEL):
            raise ValueError("non-inert tree root must begin before its terminal")
        root_lineage = first.lineage_uuid
        root_type = type(first)
        phase_order = {
            EventPhase.DECLARATION: 0,
            EventPhase.EXECUTION: 1,
            EventPhase.EFFECT: 2,
            EventPhase.COMPLETION: 3,
        }
        latest_phases: Dict[UUID, int] = {}
        lineage_types: Dict[UUID, type[Event]] = {}
        for index in range(source_cursor, cursor):
            event = cls._all_events[index]
            if (
                type(event).inert_terminal_fact
                and event.phase is not EventPhase.COMPLETION
            ):
                raise ValueError("inert tree member must be a completion fact")
            lineage_type = lineage_types.setdefault(event.lineage_uuid, type(event))
            if type(event) is not lineage_type:
                raise ValueError("tree lineage changes concrete event class")
            if event.parent_event is None:
                if event.lineage_uuid != root_lineage or type(event) is not root_type:
                    raise ValueError("tree contains a second or mismatched root")
            else:
                if event.lineage_uuid == root_lineage:
                    raise ValueError("tree root lineage must remain parentless")
                parent_index = cls.get_event_index(event.parent_event)
                if parent_index is None or parent_index >= index:
                    raise ValueError("tree child parent must be an earlier stored fact")
                root = cls._stored_root_for_event(event)
                if root.lineage_uuid != root_lineage:
                    raise ValueError("tree child ancestry resolves outside its root")
            if event.phase is EventPhase.CANCEL:
                if not event.is_last:
                    raise ValueError("cancel terminal must be last")
                if not event.canceled or event.canceled_from_phase is None:
                    raise ValueError("cancel terminal lacks cancellation evidence")
            else:
                phase_value = phase_order.get(event.phase)
                if phase_value is None:
                    raise ValueError("unknown event phase in source journal")
                previous = latest_phases.get(event.lineage_uuid, -1)
                if phase_value < previous:
                    raise ValueError("tree lineage contains a phase regression")
                latest_phases[event.lineage_uuid] = phase_value
            if (
                event.parent_event is None
                and event.lineage_uuid == root_lineage
                and type(event) is root_type
                and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)
            ):
                if not event.is_last:
                    raise ValueError("root terminal must be last")
                return tuple(cls._all_events[source_cursor:index + 1])
        return None

    @classmethod
    def _store_event(
        cls,
        event: Event,
    ) -> None:
        """Store one event fact after enforcing the active root admission law."""
        if cls._preflight_depth.get() > 0:
            raise RuntimeError("Validation-only handlers cannot publish events during preflight")
        if cls._detach_active_handler_storage(event) is not None:
            raise RuntimeError(
                "Guarded handler proposals must return through dispatch before storage"
            )
        if event.uuid in cls._events_by_uuid:
            raise ValueError(f"Event UUID collision for {event.uuid}")
        cls._validate_event_admission(event)
        identified = {
            entity_uuid: set(observer_uuids)
            for entity_uuid, observer_uuids in event.identified_entity_observer_uuids.items()
        }
        located = {
            entity_uuid: set(observer_uuids)
            for entity_uuid, observer_uuids in event.located_entity_observer_uuids.items()
        }
        if cls._identified_entity_observer_computer is not None:
            captured = cls._identified_entity_observer_computer(event)
            located = {
                entity_uuid: set(observer_uuids)
                for entity_uuid, observer_uuids in captured.items()
            }
            for entity_uuid, observer_uuids in captured.items():
                identified.setdefault(entity_uuid, set()).update(observer_uuids)

        parent_event = cls.get_event_by_uuid(event.parent_event) if event.parent_event else None
        if parent_event is not None:
            for entity_uuid, observer_uuids in parent_event.identified_entity_observer_uuids.items():
                identified.setdefault(entity_uuid, set()).update(observer_uuids)
        event.identified_entity_observer_uuids = identified
        event.located_entity_observer_uuids = located

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

        cls._events_by_type[event.event_type].append(event)
        cls._events_by_phase[event.phase].append(event)
        cls._events_by_source[event.source_entity_uuid].append(event)

        if event.target_entity_uuid:
            cls._events_by_target[event.target_entity_uuid].append(event)

        cls._all_events.append(event)
        if event.parent_event is None and event.phase in (
            EventPhase.COMPLETION,
            EventPhase.CANCEL,
        ):
            cls._open_root_lineage = None
            cls._open_root_type = None

    @classmethod
    def _get_handlers_for_event(cls, event: Event) -> List['BaseHandler']:
        """Return queue-discovered handlers for an event.

        Explicit spatial-event values use every declared dispatch position.
        Other events use trigger indexes and trigger predicates.
        """
        if isinstance(event, SpatiallyIndexedEvent):
            positions = event.spatial_dispatch_positions()
            if positions:
                return cls._get_handlers_for_spatial_event(event, positions)

        return cls._get_handlers_for_non_spatial_event(event)

    @classmethod
    def _get_handlers_for_spatial_event(
        cls,
        event: Event,
        positions: tuple[Tuple[int, int], ...],
    ) -> List['BaseHandler']:
        """Return handlers for one spatial event across exact grid positions.

        Position-indexed spatial handlers are discovered in O(1). Trigger-based
        event handlers are still included for global spatial reactions such as
        opportunity attacks. A handler covering several affected cells runs
        exactly once.

        Args:
            event: Spatial event version being dispatched.
            positions: Canonically ordered grid positions used for lookup.

        Returns:
            De-duplicated handlers in queue dispatch order.
        """
        event_key = (event.event_type, event.phase)
        handlers: List['BaseHandler'] = []
        seen: Set[UUID] = set()

        for position in positions:
            pos_handlers = cls._spatial_handlers_by_position[event_key].get(
                position,
                [],
            )
            for handler in pos_handlers:
                if handler.uuid not in seen:
                    handlers.append(handler)
                    seen.add(handler.uuid)

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
        event_handler.bind_behavior_owner()
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
        event_handler.remove_from_register()

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
        handler.bind_behavior_owner()
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

        handler.remove_from_register()
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
        """Clear all event, handler, and causal-journal runtime state."""
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
        cls._open_root_lineage = None
        cls._open_root_type = None
        cls._handler_dispatch_cursor = 0
        cls._active_turn_execution_id = None
        cls._preflight_depth.set(0)
        cls._active_handler_input.set(None)
        cls._active_handler_proposal.set(None)
        cls._active_handler_validation_token.set(None)
        cls._active_handler_storage_result.set(None)
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
