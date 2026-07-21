"""Project objective engine state into session-subjective observations."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from uuid import UUID

from dnd.action_timing import action_timing_enabled, record_action_timing
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, ConditionApplicationEvent, ConditionTag
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.events import (
    DamageAppliedEvent,
    Event,
    EventPhase,
    EventQueue,
    EventType,
    HealEvent,
    SensoryUpdateEvent,
    SensoryUpdateReason,
)
from dnd.core.gridmap import get_map
from dnd.core.modifiers import DamageType, ResistanceStatus
from dnd.encounter import Encounter
from dnd.entity import Entity
from server.session import GameSession, PlayerSession, SessionManager

from ai.observation.materializer import apply_observation_frame
from ai.observation.models import (
    AdjacentOffset,
    KnowledgeState,
    ObservationCombatantState,
    ObservationConditionFact,
    ObservationEncounterState,
    ObservationEffectProtection,
    ObservationEntityFact,
    ObservationFrame,
    ObservationFramesResponse,
    ObservationFrameType,
    ObservationObjectFact,
    ObservationObserverState,
    ObservationPatch,
    ObservationPatchType,
    ObservationSessionState,
    ObservationSourceKind,
    ObservationSnapshot,
    ObservationStateReplacement,
    SubjectiveWorldState,
    ObservationTileFact,
    SpatialDomainKnowledge,
)
from ai.protocol.control import CommandResult, DecisionEpoch
from server.event_stream import BoundedSubscription, DEFAULT_SUBSCRIPTION_MAX_DEPTH


class ObservationAccessError(ValueError):
    """Raised when an observation request cannot be authorized or resolved."""

    def __init__(self, code: str, message: str) -> None:
        """Create a structured observation access error.

        Args:
            code: Machine-readable error code.
            message: Human-readable error message.
        """
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class _ProjectionCacheEntry:
    """Cached subjective frame projection for one session."""

    source_event_cursor: int = 0
    controlled_key: Tuple[str, ...] = ()
    encounter_uuid: Optional[str] = None
    frames: List[ObservationFrame] = field(default_factory=list)
    materialized_state: Optional[SubjectiveWorldState] = None


@dataclass(frozen=True)
class ObservationOwnershipBoundary:
    """Initialized session projections captured before ownership mutation."""

    session_ids: Tuple[str, ...]


@dataclass
class _CombatLogFilterContext:
    """Reusable combat-log visibility context for one projection pass."""

    known_entity_uuids: Set[str]
    controlled_entity_uuids: Set[str]
    filtered_cache: Dict[int, Optional[CombatLogEntry]] = field(default_factory=dict)


@dataclass
class _ProjectionPassContext:
    """Reusable subjective facts for one incremental projection pass."""

    combat_logs: _CombatLogFilterContext
    entity_facts: Dict[Tuple[UUID, str, Optional[Tuple[int, int]]], Optional[ObservationEntityFact]] = field(default_factory=dict)
    tile_facts: Dict[Tuple[Tuple[int, int], Tuple[str, ...]], ObservationTileFact] = field(default_factory=dict)
    has_any_hazards: Optional[bool] = None


class _ObservationWakeupStream:
    """Per-session live delivery for projected and controller subjective frames."""

    def __init__(self) -> None:
        self._subscriptions: Dict[str, List[BoundedSubscription]] = {}

    def clear_all(self) -> None:
        """Evict all subscribers and clear subscriptions."""
        for subscriptions in self._subscriptions.values():
            for sub in list(subscriptions):
                sub.try_enqueue({"event": "evicted", "data": {"reason": "observation_reset"}, "id": None})
        self._subscriptions.clear()

    def subscribe(self, session_id: str, max_depth: int = DEFAULT_SUBSCRIPTION_MAX_DEPTH) -> BoundedSubscription:
        """Subscribe to wakeups for one session."""
        sub = BoundedSubscription(max_depth=max_depth)
        self._subscriptions.setdefault(session_id, []).append(sub)
        return sub

    def unsubscribe(self, session_id: str, sub: BoundedSubscription) -> None:
        """Remove one wakeup subscription."""
        if sub in self._subscriptions.get(session_id, []):
            self._subscriptions[session_id].remove(sub)

    def has_subscribers(self, session_id: str) -> bool:
        """Return whether a session has live observation subscribers."""
        return bool(self._subscriptions.get(session_id))

    def publish(self, session_id: str, frame: ObservationFrame) -> None:
        """Wake subscribers for one newly appended frame."""
        envelope = {
            "event": "observation_frame",
            "data": frame,
            "id": f"o={frame.observation_cursor}",
        }
        for sub in list(self._subscriptions.get(session_id, [])):
            if not sub.try_enqueue(envelope):
                self.unsubscribe(session_id, sub)


_projection_cache: Dict[str, _ProjectionCacheEntry] = {}
_adjacent_domain_cache_revision: Optional[int] = None
_adjacent_domain_cache: Dict[
    Tuple[int, int],
    Dict[AdjacentOffset, SpatialDomainKnowledge],
] = {}
observation_wakeup_stream = _ObservationWakeupStream()
_pending_observation_wakeups: ContextVar[
    Optional[List[Tuple[str, ObservationFrame]]]
] = ContextVar("pending_observation_wakeups", default=None)
_deferred_projection_requested: ContextVar[bool] = ContextVar(
    "deferred_projection_requested",
    default=False,
)


def clear_observation_projection_cache() -> None:
    """Clear cached subjective frame projections."""
    global _adjacent_domain_cache_revision
    _projection_cache.clear()
    _adjacent_domain_cache_revision = None
    _adjacent_domain_cache.clear()
    _pending_observation_wakeups.set(None)
    _deferred_projection_requested.set(False)
    observation_wakeup_stream.clear_all()


def ensure_observation_projection_attached() -> None:
    """Attach objective-event and standalone-log subjective projection."""
    EventQueue.add_on_event_sequence_callback(
        _capture_initialized_sessions_on_events,
        phases={EventPhase.COMPLETION},
    )
    EventQueue.add_on_event_batch_callback(_flush_projected_frame_wakeups)
    Encounter.add_combat_log_listener(_project_initialized_sessions_on_combat_log)


def prepare_observation_ownership_change(
    session_manager: Optional[SessionManager] = None,
) -> ObservationOwnershipBoundary:
    """Freeze pending subjective events before an ownership mutation."""
    ensure_observation_projection_attached()
    manager = session_manager or SessionManager.get()
    game = manager.get_active_game()
    encounter = game.encounter if game else Encounter.get_active()
    prepared: List[str] = []
    for session_id in tuple(_projection_cache):
        try:
            parsed_session_id = UUID(session_id)
        except ValueError:
            continue
        session = manager.get_session(parsed_session_id)
        if session is None:
            continue
        _update_projection_cache(session, game, encounter)
        prepared.append(session_id)
    return ObservationOwnershipBoundary(session_ids=tuple(prepared))


def publish_observation_ownership_changes(
    boundary: ObservationOwnershipBoundary,
    *,
    reason: str,
    session_manager: Optional[SessionManager] = None,
) -> List[str]:
    """Append state-replacement frames for sessions whose ownership changed."""
    manager = session_manager or SessionManager.get()
    game = manager.get_active_game()
    encounter = game.encounter if game else Encounter.get_active()
    changed: List[str] = []
    for session_id in boundary.session_ids:
        entry = _projection_cache.get(session_id)
        if entry is None:
            continue
        previous_key = entry.controlled_key
        try:
            parsed_session_id = UUID(session_id)
        except ValueError:
            continue
        session = manager.get_session(parsed_session_id)
        if session is None:
            continue
        updated = _update_projection_cache(
            session,
            game,
            encounter,
            ownership_reason=reason,
        )
        if updated.controlled_key != previous_key:
            changed.append(session_id)
    return changed


def _capture_initialized_sessions_on_events(events: Sequence[Event]) -> None:
    """Capture one ordered event sequence against its derived-state boundary."""
    if not _projection_cache:
        return
    completions = tuple(
        event
        for event in events
        if event.phase == EventPhase.COMPLETION
    )
    if not completions:
        return
    if EventQueue.is_event_batch_active() and not _completion_sequence_needs_immediate_projection(completions):
        _deferred_projection_requested.set(True)
        return
    general_completion = any(
        event.event_type != EventType.SENSORY_UPDATE
        for event in completions
    )
    sensory_observer_uuids = {
        event.observer_uuid
        for event in completions
        if isinstance(event, SensoryUpdateEvent)
        and _sensory_event_has_subjective_delta(event)
    }
    if not general_completion and not sensory_observer_uuids:
        return
    record_timing = _event_queue_projection_timing_recorder() if action_timing_enabled() else None
    session_filter: Optional[Set[UUID]] = None
    if not general_completion:
        session_filter = sensory_observer_uuids
    _project_initialized_sessions_to_current_cursor(record_timing=record_timing, session_filter=session_filter)


def _project_initialized_sessions_to_current_cursor(
    *,
    record_timing: Optional[Callable[[str, float], None]] = None,
    session_filter: Optional[Set[UUID]] = None,
) -> None:
    """Update initialized session projections through the current event cursor."""
    manager = SessionManager.get()
    game = manager.get_active_game()
    encounter = game.encounter if game else Encounter.get_active()
    for session_id in tuple(_projection_cache):
        try:
            parsed_session_id = UUID(session_id)
        except ValueError:
            continue
        session = manager.get_session(parsed_session_id)
        if session is None:
            continue
        if (
            session_filter is not None
            and session_filter.isdisjoint(session.controlled_entities)
        ):
            continue
        _update_projection_cache(session, game, encounter, record_timing=record_timing)


def _completion_sequence_needs_immediate_projection(completions: Sequence[Event]) -> bool:
    """Return whether a batch sequence must be projected before action end.

    Non-movement action batches already defer wakeup delivery to the command
    boundary. Projecting every damage, condition, and death child event inside
    the batch only duplicates work for AoE and multi-target actions. Movement is
    different: controller revalidation can ask for the materialized subjective
    world after a committed step, so movement and sensory boundary events remain
    immediate.
    """
    immediate_types = {
        EventType.MOVEMENT,
        EventType.STEP_MOVEMENT,
        EventType.MOVEMENT_COLLISION,
        EventType.SPATIAL_ENTITY_ENTERED,
        EventType.SPATIAL_ENTITY_LEFT,
        EventType.SPATIAL_PERCEIVABILITY_CHANGED,
        EventType.SENSORY_UPDATE,
    }
    return any(event.event_type in immediate_types for event in completions)


def _event_queue_projection_timing_recorder() -> Callable[[str, float], None]:
    """Return an action-timing recorder for event-time observation projection."""

    def record(phase: str, started_at: float) -> None:
        record_action_timing(f"observation_projection.{phase}", started_at)

    return record


def _publish_or_defer_frame(session_id: str, frame: ObservationFrame) -> None:
    """Persist wakeup ordering while deferring delivery to an action boundary."""
    if not EventQueue.is_event_batch_active():
        observation_wakeup_stream.publish(session_id, frame)
        return
    pending = _pending_observation_wakeups.get()
    if pending is None:
        pending = []
        _pending_observation_wakeups.set(pending)
    pending.append((session_id, frame))


def _flush_projected_frame_wakeups(_events: Sequence[Event]) -> None:
    """Publish event-time subjective frames after the outer action closes."""
    if _deferred_projection_requested.get() and _projection_cache:
        record_timing = _event_queue_projection_timing_recorder() if action_timing_enabled() else None
        _project_initialized_sessions_to_current_cursor(record_timing=record_timing)
    _deferred_projection_requested.set(False)
    pending = tuple(_pending_observation_wakeups.get() or ())
    _pending_observation_wakeups.set(None)
    for session_id, frame in pending:
        observation_wakeup_stream.publish(session_id, frame)


def _project_initialized_sessions_on_combat_log(
    encounter: Encounter,
    index: int,
    combat_log: CombatLogEntry,
    event: Event,
) -> None:
    """Publish combat logs that have no registered engine-event completion.

    Registered completion events are projected by the EventQueue callback after
    storage. Informational logs such as entity-spotted and hazard-detected use an
    unregistered carrier event, so the encounter append is their causal delivery
    boundary.
    """
    if (
        event.context is None
        or event.context.get("combat_log_origin") != "standalone"
        or not _projection_cache
    ):
        return

    manager = SessionManager.get()
    game = manager.get_active_game()
    session_encounter = game.encounter if game else Encounter.get_active()
    if session_encounter is None or session_encounter.uuid != encounter.uuid:
        return

    for session_id in tuple(_projection_cache):
        try:
            parsed_session_id = UUID(session_id)
        except ValueError:
            continue
        session = manager.get_session(parsed_session_id)
        if session is None:
            continue

        entry = _update_projection_cache(session, game, encounter)
        observers = _controlled_observers(session)
        filtered_log = _filtered_combat_log(combat_log, session, observers)
        if filtered_log is None:
            continue

        combat_log_json = filtered_log.model_dump(mode="json")
        frame = ObservationFrame(
            observation_cursor=len(entry.frames) + 1,
            frame_type=ObservationFrameType.COMBAT_LOG,
            source_kind=ObservationSourceKind.COMBAT_LOG,
            source_event_cursor=EventQueue.event_cursor(),
            source_combat_log_cursor=index + 1,
            patches=[_combat_log_patch(filtered_log, combat_log_json)],
            combat_log=combat_log_json,
        )
        entry.frames.append(frame)
        _publish_or_defer_frame(session_id, frame)


def build_observation_snapshot(
    session_id: str | UUID,
    session_manager: Optional[SessionManager] = None,
) -> ObservationSnapshot:
    """Build the current strict subjective snapshot for one session.

    Args:
        session_id: Session UUID string or object.

    Returns:
        Snapshot containing the session's currently known world facts.

    Raises:
        ObservationAccessError: If the session cannot be resolved.
    """
    session, game = _resolve_session(session_id, session_manager)
    encounter = game.encounter if game else Encounter.get_active()
    entry = _update_projection_cache(session, game, encounter)
    state = _observation_state_replacement(session, game, encounter, entry)
    entry.materialized_state = _world_from_replacement(state, len(entry.frames))

    return ObservationSnapshot(
        observation_cursor=len(entry.frames),
        source_event_cursor=EventQueue.event_cursor(),
        source_combat_log_cursor=len(encounter.combat_log) if encounter else 0,
        session=state.session,
        encounter=state.encounter,
        observers=state.observers,
        known_entities=state.known_entities,
        known_objects=state.known_objects,
        known_tiles=state.known_tiles,
        combat_logs=state.combat_logs,
    )


def _observation_state_replacement(
    session: PlayerSession,
    game: Optional[GameSession],
    encounter: Optional[Encounter],
    entry: _ProjectionCacheEntry,
    bootstrap_combat_logs: Optional[List[Dict[str, Any]]] = None,
) -> ObservationStateReplacement:
    """Build one complete current subjective materialization."""
    prior_world = _materialized_entry_world(entry)
    observers = _controlled_observers(session)
    remembered_entities = _remembered_entity_facts_from_world(prior_world)
    known_objects = _merge_remembered_objects(
        _known_object_facts(observers),
        prior_world,
    )
    known_tiles = _merge_seen_tiles(
        _known_tile_facts(observers),
        prior_world,
    )
    return ObservationStateReplacement(
        session=_session_state(session, game),
        encounter=_encounter_state(encounter, session, observers) if encounter else None,
        observers=[_observer_state(observer) for observer in observers],
        known_entities=_known_entity_facts(
            session,
            observers,
            remembered_entity_facts=remembered_entities,
        ),
        known_objects=known_objects,
        known_tiles=known_tiles,
        combat_logs=(
            list(prior_world.combat_logs)
            if prior_world is not None
            else list(bootstrap_combat_logs or [])
        ),
    )


def _materialized_entry_world(
    entry: _ProjectionCacheEntry,
) -> Optional[SubjectiveWorldState]:
    """Apply unapplied cached frames to the session's last materialization."""
    world = entry.materialized_state
    if world is None:
        return None
    for frame in entry.frames:
        if frame.observation_cursor > world.observation_cursor:
            world = apply_observation_frame(world, frame)
    entry.materialized_state = world
    return world


def _world_from_replacement(
    replacement: ObservationStateReplacement,
    observation_cursor: int,
) -> SubjectiveWorldState:
    """Create a cached materialized world from a complete replacement."""
    return SubjectiveWorldState(
        observation_cursor=observation_cursor,
        session=replacement.session,
        encounter=replacement.encounter,
        observers={observer.observer_uuid: observer for observer in replacement.observers},
        known_entities={entity.uuid: entity for entity in replacement.known_entities},
        known_objects={obj.uuid: obj for obj in replacement.known_objects},
        known_tiles={tile.key: tile for tile in replacement.known_tiles},
        combat_logs=list(replacement.combat_logs),
        current_epoch=replacement.current_epoch,
        epoch_cursor=(
            replacement.current_epoch.epoch_index
            if replacement.current_epoch is not None
            else 0
        ),
    )


def get_observation_cursor(
    session_id: str | UUID,
    session_manager: Optional[SessionManager] = None,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> int:
    """Return the current session-local observation cursor."""
    session, game = _resolve_session(session_id, session_manager)
    encounter = game.encounter if game else Encounter.get_active()
    return _current_observation_cursor(session, game, encounter, record_timing=record_timing)


def get_materialized_observation_world(
    session_id: str | UUID,
    session_manager: Optional[SessionManager] = None,
) -> SubjectiveWorldState:
    """Return the projector's current session-subjective materialization."""
    session, game = _resolve_session(session_id, session_manager)
    encounter = game.encounter if game else Encounter.get_active()
    entry = _update_projection_cache(session, game, encounter)
    world = _materialized_entry_world(entry)
    if world is not None:
        return world
    state = _observation_state_replacement(session, game, encounter, entry)
    world = _world_from_replacement(state, len(entry.frames))
    entry.materialized_state = world
    return world


def iter_observation_frames(
    session_id: str | UUID,
    since: int = 0,
    limit: int = 50,
    session_manager: Optional[SessionManager] = None,
) -> ObservationFramesResponse:
    """Return projected subjective frames after a session-local cursor.

    Args:
        session_id: Session UUID string or object.
        since: Session-local observation cursor already consumed by the client.
        limit: Maximum frames to return. A value of 0 means no limit.

    Returns:
        Cursor-addressed frame page.

    Raises:
        ObservationAccessError: If the session cannot be resolved.
    """
    session, game = _resolve_session(session_id, session_manager)
    encounter = game.encounter if game else Encounter.get_active()
    entry = _update_projection_cache(session, game, encounter)
    start = max(0, since)
    frames = entry.frames[start:]
    if limit > 0:
        frames = frames[:limit]
    next_cursor = frames[-1].observation_cursor if frames else start
    return ObservationFramesResponse(
        frames=frames,
        count=len(frames),
        total=len(entry.frames),
        next_observation_cursor=next_cursor,
    )


def append_decision_epoch_frame(
    session_id: str | UUID,
    epoch: DecisionEpoch,
    *,
    source_command_id: Optional[str] = None,
    session_manager: Optional[SessionManager] = None,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> ObservationFrame:
    """Append a controller-facing decision epoch frame for one session."""
    total_started = _timing_start(record_timing)
    started = _timing_start(record_timing)
    frame = ObservationFrame(
        observation_cursor=0,
        frame_type=ObservationFrameType.DECISION_EPOCH,
        source_kind=ObservationSourceKind.DECISION_EPOCH,
        source_command_id=source_command_id,
        decision_epoch=epoch,
        patches=[
            ObservationPatch(
                patch_type=ObservationPatchType.DECISION_EPOCH,
                reason=epoch.reason.value,
                data={
                    "epoch_id": epoch.epoch_id,
                    "actor_uuid": epoch.actor_uuid,
                    "reason": epoch.reason.value,
                },
            )
        ],
    )
    _record_timing(record_timing, "append.make_decision_epoch_frame_ms", started)
    final_frame = append_observation_control_frame(
        session_id,
        frame,
        session_manager=session_manager,
        record_timing=record_timing,
    )
    _record_timing(record_timing, "append.decision_epoch_total_ms", total_started)
    return final_frame


def append_epoch_clear_frame(
    session_id: str | UUID,
    *,
    reason: str,
    source_command_id: Optional[str] = None,
    session_manager: Optional[SessionManager] = None,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> ObservationFrame:
    """Append a decision-epoch clear frame for one session."""
    started = _timing_start(record_timing)
    frame = ObservationFrame(
        observation_cursor=0,
        frame_type=ObservationFrameType.DECISION_EPOCH,
        source_kind=ObservationSourceKind.DECISION_EPOCH,
        source_command_id=source_command_id,
        decision_epoch=None,
        patches=[
            ObservationPatch(
                patch_type=ObservationPatchType.DECISION_EPOCH,
                reason=reason,
                data={"cleared": True, "reason": reason},
            )
        ],
    )
    _record_timing(record_timing, "append.make_epoch_clear_frame_ms", started)
    return append_observation_control_frame(
        session_id,
        frame,
        session_manager=session_manager,
        record_timing=record_timing,
    )


def append_command_result_frame(
    session_id: str | UUID,
    result: CommandResult,
    *,
    session_manager: Optional[SessionManager] = None,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> ObservationFrame:
    """Append a controller-command result frame for one session."""
    started = _timing_start(record_timing)
    frame = ObservationFrame(
        observation_cursor=0,
        frame_type=ObservationFrameType.COMMAND_RESULT,
        source_kind=ObservationSourceKind.CONTROLLER_COMMAND,
        source_command_id=result.command_id,
        command_result=result,
        patches=[
            ObservationPatch(
                patch_type=ObservationPatchType.COMMAND_RESULT,
                reason=result.status.value,
                data={
                    "command_id": result.command_id,
                    "status": result.status.value,
                    "actor_uuid": result.actor_uuid,
                    "row_id": result.row_id,
                },
            )
        ],
    )
    _record_timing(record_timing, "append.make_command_result_frame_ms", started)
    return append_observation_control_frame(
        session_id,
        frame,
        session_manager=session_manager,
        record_timing=record_timing,
    )


def append_observation_control_frame(
    session_id: str | UUID,
    frame: ObservationFrame,
    *,
    session_manager: Optional[SessionManager] = None,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> ObservationFrame:
    """Append a non-EventQueue subjective frame after projected engine events."""
    total_started = _timing_start(record_timing)
    started = _timing_start(record_timing)
    session, game = _resolve_session(session_id, session_manager)
    _record_timing(record_timing, "append.resolve_session_ms", started)
    encounter = game.encounter if game else Encounter.get_active()
    started = _timing_start(record_timing)
    entry = _update_projection_cache(session, game, encounter, record_timing=record_timing)
    _record_timing(record_timing, "append.update_projection_cache_ms", started)
    cursor = len(entry.frames) + 1
    command_result = frame.command_result
    if command_result is not None:
        started = _timing_start(record_timing)
        command_result = command_result.model_copy(update={
            "accepted_at_observation_cursor": cursor,
            "result_expected_after_cursor": cursor,
        })
        _record_timing(record_timing, "append.copy_command_result_ms", started)
    started = _timing_start(record_timing)
    final_frame = frame.model_copy(update={
        "observation_cursor": cursor,
        "command_result": command_result,
    })
    _record_timing(record_timing, "append.copy_frame_ms", started)
    if command_result is not None:
        started = _timing_start(record_timing)
        patched = []
        for patch in final_frame.patches:
            if patch.patch_type == ObservationPatchType.COMMAND_RESULT:
                patched.append(patch.model_copy(update={
                    "data": {
                        "command_id": command_result.command_id,
                        "status": command_result.status.value,
                        "actor_uuid": command_result.actor_uuid,
                        "row_id": command_result.row_id,
                    },
                }))
            else:
                patched.append(patch)
        final_frame = final_frame.model_copy(update={"patches": patched})
        _record_timing(record_timing, "append.patch_command_result_ms", started)
    started = _timing_start(record_timing)
    entry.frames.append(final_frame)
    _record_timing(record_timing, "append.store_frame_ms", started)
    started = _timing_start(record_timing)
    _publish_or_defer_frame(str(session.session_id), final_frame)
    _record_timing(record_timing, "append.wakeup_publish_ms", started)
    _record_timing(record_timing, "append.control_frame_total_ms", total_started)
    return final_frame


def _append_ownership_state_frame(
    session: PlayerSession,
    game: Optional[GameSession],
    encounter: Optional[Encounter],
    entry: _ProjectionCacheEntry,
    *,
    reason: str,
) -> ObservationFrame:
    """Append an atomic subjective-state replacement for ownership changes."""
    replacement = _observation_state_replacement(
        session,
        game,
        encounter,
        entry,
    )
    patches = [_session_patch(replacement.session, reason)]
    if replacement.encounter is not None:
        patches.append(_encounter_patch(replacement.encounter, reason))
    frame = ObservationFrame(
        observation_cursor=len(entry.frames) + 1,
        frame_type=ObservationFrameType.STATE_REPLACEMENT,
        source_kind=ObservationSourceKind.SESSION_CONTROL,
        source_event_cursor=entry.source_event_cursor,
        source_combat_log_cursor=len(encounter.combat_log) if encounter else 0,
        patches=patches,
        state_replacement=replacement,
    )
    entry.frames.append(frame)
    _publish_or_defer_frame(str(session.session_id), frame)
    return frame


def _resolve_session(
    session_id: str | UUID,
    session_manager: Optional[SessionManager] = None,
) -> tuple[PlayerSession, Optional[GameSession]]:
    """Resolve a session and active game for observation requests."""
    ensure_observation_projection_attached()
    try:
        sid = session_id if isinstance(session_id, UUID) else UUID(session_id)
    except ValueError as exc:
        raise ObservationAccessError("invalid_session_uuid", "Invalid session ID format") from exc

    manager = session_manager or SessionManager.get()
    session = manager.get_session(sid)
    if session is None:
        raise ObservationAccessError("session_not_found", "Session not found")
    return session, manager.get_active_game()


def _current_observation_cursor(
    session: PlayerSession,
    game: Optional[GameSession],
    encounter: Optional[Encounter],
    *,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> int:
    """Return the current session-local observation cursor."""
    return len(_project_all_frames(session, game, encounter, record_timing=record_timing))


def _project_all_frames(
    session: PlayerSession,
    game: Optional[GameSession],
    encounter: Optional[Encounter],
    *,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> List[ObservationFrame]:
    """Project all currently visible event frames for a session."""
    return list(_update_projection_cache(session, game, encounter, record_timing=record_timing).frames)


def _update_projection_cache(
    session: PlayerSession,
    game: Optional[GameSession],
    encounter: Optional[Encounter],
    *,
    record_timing: Optional[Callable[[str, float], None]] = None,
    ownership_reason: str = "session_ownership_changed",
) -> _ProjectionCacheEntry:
    """Incrementally update cached subjective frames for one session."""
    started = _timing_start(record_timing)
    current_event_cursor = EventQueue.event_cursor()
    cache_key = str(session.session_id)
    controlled_key = tuple(sorted(str(uuid) for uuid in session.controlled_entities))
    encounter_uuid = str(encounter.uuid) if encounter is not None else None
    _record_timing(record_timing, "projection.cache_key_ms", started)
    started = _timing_start(record_timing)
    entry = _projection_cache.get(cache_key)
    initialized_entry = False
    if (
        entry is None
        or entry.source_event_cursor > current_event_cursor
        or entry.encounter_uuid != encounter_uuid
    ):
        entry = _ProjectionCacheEntry(
            source_event_cursor=current_event_cursor,
            controlled_key=controlled_key,
            encounter_uuid=encounter_uuid,
        )
        _projection_cache[cache_key] = entry
        initialized_entry = True
    _record_timing(record_timing, "projection.ensure_entry_ms", started)

    if initialized_entry:
        observers = _controlled_observers(session)
        bootstrap_state = _observation_state_replacement(
            session,
            game,
            encounter,
            entry,
            bootstrap_combat_logs=_visible_combat_logs(session, observers, encounter),
        )
        entry.materialized_state = _world_from_replacement(bootstrap_state, 0)

    if entry.controlled_key != controlled_key:
        started = _timing_start(record_timing)
        entry.source_event_cursor = current_event_cursor
        entry.controlled_key = controlled_key
        _append_ownership_state_frame(
            session,
            game,
            encounter,
            entry,
            reason=ownership_reason,
        )
        _record_timing(record_timing, "projection.append_ownership_transition_ms", started)
        return entry

    if entry.source_event_cursor == current_event_cursor:
        return entry

    started = _timing_start(record_timing)
    observers = _controlled_observers(session)
    _record_timing(record_timing, "projection.controlled_observers_ms", started)
    projection_context = _ProjectionPassContext(
        combat_logs=_build_combat_log_filter_context(session, observers),
    )
    started = _timing_start(record_timing)
    project_completion_seconds = 0.0
    cursor_assignment_seconds = 0.0
    project_completion_seconds_by_type: Dict[str, float] = {}
    for source_index, event in EventQueue.iter_events_since(entry.source_event_cursor):
        if event.phase != EventPhase.COMPLETION:
            entry.source_event_cursor = source_index + 1
            continue
        event_type_key = event.event_type.value
        project_started = _timing_start(record_timing)
        frame = _project_completed_event(
            session,
            game,
            encounter,
            observers,
            source_index,
            event,
            projection_context,
            record_timing,
        )
        project_elapsed = _timing_start(record_timing) - project_started
        project_completion_seconds += project_elapsed
        project_completion_seconds_by_type[event_type_key] = (
            project_completion_seconds_by_type.get(event_type_key, 0.0) + project_elapsed
        )
        if frame is None:
            entry.source_event_cursor = source_index + 1
            continue
        cursor_started = _timing_start(record_timing)
        final_frame = frame.model_copy(update={"observation_cursor": len(entry.frames) + 1})
        entry.frames.append(final_frame)
        _publish_or_defer_frame(str(session.session_id), final_frame)
        cursor_assignment_seconds += _timing_start(record_timing) - cursor_started
        entry.source_event_cursor = source_index + 1
    entry.source_event_cursor = current_event_cursor
    _record_elapsed(record_timing, "projection.project_completion_events_ms", project_completion_seconds)
    for event_type, elapsed_seconds in sorted(project_completion_seconds_by_type.items()):
        _record_elapsed(
            record_timing,
            f"projection.project_completion_event.{event_type}_ms",
            elapsed_seconds,
        )
    _record_elapsed(record_timing, "projection.assign_observation_cursors_ms", cursor_assignment_seconds)
    _record_timing(record_timing, "projection.project_events_ms", started)
    return entry


def _timing_start(
    record_timing: Optional[Callable[[str, float], None]],
) -> float:
    """Read the diagnostic clock only when detailed timing is requested."""
    return time.perf_counter() if record_timing is not None else 0.0


def _record_timing(
    record_timing: Optional[Callable[[str, float], None]],
    phase: str,
    started_at: float,
) -> None:
    """Record an optional observation projection timing phase."""
    if record_timing is not None:
        record_timing(phase, started_at)


def _record_elapsed(
    record_timing: Optional[Callable[[str, float], None]],
    phase: str,
    elapsed_seconds: float,
) -> None:
    """Record an already-measured elapsed phase."""
    if record_timing is not None and elapsed_seconds > 0:
        record_timing(phase, _timing_start(record_timing) - elapsed_seconds)


def _project_completed_event(
    session: PlayerSession,
    game: Optional[GameSession],
    encounter: Optional[Encounter],
    observers: List[Entity],
    source_index: int,
    event: Event,
    projection_context: _ProjectionPassContext,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> Optional[ObservationFrame]:
    """Project one completed engine event into a safe subjective frame."""
    if _is_redundant_child_movement_event(event):
        return None

    patches: List[ObservationPatch] = []
    source_kind = ObservationSourceKind.ENGINE_EVENT
    event_type_key = event.event_type.value
    if event.event_type == EventType.SENSORY_UPDATE and isinstance(event, SensoryUpdateEvent):
        if event.observer_uuid not in session.controlled_entities:
            return None
        if not _sensory_event_has_subjective_delta(event):
            return None
        source_kind = ObservationSourceKind.SENSORY_EVENT
        started = _timing_start(record_timing)
        patches.extend(_sensory_patches(event, session, observers, projection_context, record_timing))
        _record_timing(record_timing, f"projection.project_completion_event_detail.{event_type_key}.build_patches_ms", started)
        if not patches:
            return None
        started = _timing_start(record_timing)
        frame = ObservationFrame(
            observation_cursor=0,
            frame_type=ObservationFrameType.EVENT,
            source_kind=source_kind,
            event_type=event.event_type.value,
            event_uuid=str(event.uuid),
            lineage_uuid=str(event.lineage_uuid),
            phase=event.phase.value,
            source_event_cursor=source_index + 1,
            source_combat_log_cursor=None,
            patches=patches,
            combat_log=None,
        )
        _record_timing(record_timing, f"projection.project_completion_event_detail.{event_type_key}.construct_frame_ms", started)
        return frame

    started = _timing_start(record_timing)
    event_combat_log = _filtered_combat_log(event.combat_log, session, observers, projection_context.combat_logs)
    _record_timing(record_timing, f"projection.project_completion_event_detail.{event_type_key}.filter_event_log_ms", started)
    top_level_log = _top_level_combat_log(event)
    started = _timing_start(record_timing)
    combat_log = _filtered_combat_log(top_level_log, session, observers, projection_context.combat_logs)
    _record_timing(record_timing, f"projection.project_completion_event_detail.{event_type_key}.filter_top_level_log_ms", started)
    if _event_visible_to_session(
        event,
        session,
        observers,
        filtered_combat_log=event_combat_log,
        combat_log_checked=True,
    ):
        started = _timing_start(record_timing)
        patches.extend(_event_state_patches(
            event,
            session,
            game,
            encounter,
            observers,
            source_event_cursor=source_index + 1,
            projection_context=projection_context,
            record_timing=record_timing,
        ))
        _record_timing(record_timing, f"projection.project_completion_event_detail.{event_type_key}.build_patches_ms", started)
    else:
        if combat_log is None:
            return None
        source_kind = ObservationSourceKind.COMBAT_LOG

    started = _timing_start(record_timing)
    combat_log_json = combat_log.model_dump(mode="json") if combat_log is not None else None
    _record_timing(record_timing, f"projection.project_completion_event_detail.{event_type_key}.dump_combat_log_ms", started)
    if combat_log is not None and not any(p.patch_type == ObservationPatchType.COMBAT_LOG for p in patches):
        patches.append(_combat_log_patch(combat_log, combat_log_json))

    if not patches:
        return None

    started = _timing_start(record_timing)
    frame = ObservationFrame(
        observation_cursor=0,
        frame_type=ObservationFrameType.EVENT,
        source_kind=source_kind,
        event_type=event.event_type.value,
        event_uuid=str(event.uuid),
        lineage_uuid=str(event.lineage_uuid),
        phase=event.phase.value,
        source_event_cursor=source_index + 1,
        source_combat_log_cursor=_combat_log_cursor(event.combat_log, encounter),
        patches=patches,
        combat_log=combat_log_json,
    )
    _record_timing(record_timing, f"projection.project_completion_event_detail.{event_type_key}.construct_frame_ms", started)
    return frame


def _is_redundant_child_movement_event(event: Event) -> bool:
    """Return whether movement breadcrumbs are already carried by a parent move."""
    if getattr(event, "parent_event", None) is None:
        return False
    return event.event_type in {
        EventType.STEP_MOVEMENT,
        EventType.SPATIAL_ENTITY_ENTERED,
        EventType.SPATIAL_ENTITY_LEFT,
    }


def _session_state(
    session: PlayerSession,
    game: Optional[GameSession],
) -> ObservationSessionState:
    """Build session state visible to the controller."""
    active_uuid = game.active_entity_uuid if game else None
    active_entity = Entity.get(active_uuid) if active_uuid else None
    active_known = active_uuid in session.controlled_entities if active_uuid else False
    if active_uuid and not active_known:
        active_known = _entity_visible_to_session(active_uuid, _controlled_observers(session))
    return ObservationSessionState(
        session_id=str(session.session_id),
        player_type=session.player_type.value,
        name=session.name,
        connection_status=session.connection_status.value,
        controlled_entity_uuids=sorted(str(uuid) for uuid in session.controlled_entities),
        active_entity_uuid=str(active_uuid) if active_uuid and active_known else None,
        active_entity_name=active_entity.name if active_entity and active_known else None,
        is_my_turn=game.is_player_turn(session.session_id) if game else False,
    )


def _encounter_state(
    encounter: Encounter,
    session: PlayerSession,
    observers: List[Entity],
) -> ObservationEncounterState:
    """Build encounter state from combatants known to the session."""
    rows: List[ObservationCombatantState] = []
    for combatant_uuid in encounter.initiative_order:
        entity = Entity.get(combatant_uuid)
        controlled = combatant_uuid in session.controlled_entities
        observer_uuids = _observers_that_see(combatant_uuid, observers)
        visible = bool(observer_uuids) or controlled
        combatant = encounter.combatants.get(combatant_uuid)
        if visible and entity is not None:
            rows.append(ObservationCombatantState(
                uuid=str(combatant_uuid),
                name=entity.name,
                initiative=combatant.initiative_total if combatant else None,
                is_dead=not entity.has_hp,
                is_controlled=controlled,
                knowledge_state=KnowledgeState.VISIBLE,
                observer_uuids=observer_uuids,
            ))

    current_uuid = encounter.initiative_order[encounter.current_turn_index] if encounter.initiative_order else None
    current_entity = Entity.get(current_uuid) if current_uuid else None
    current_known = current_uuid in session.controlled_entities if current_uuid else False
    if current_uuid and not current_known:
        current_known = _entity_visible_to_session(current_uuid, observers)
    subjective_turn_index = -1
    if current_uuid and current_known:
        for index, row in enumerate(rows):
            if row.uuid == str(current_uuid):
                subjective_turn_index = index
                break

    return ObservationEncounterState(
        uuid=str(encounter.uuid),
        name=encounter.name,
        state=encounter.state.value,
        round_number=encounter.round_number,
        current_turn_index=subjective_turn_index,
        current_entity_uuid=str(current_uuid) if current_uuid and current_known else None,
        current_entity_name=current_entity.name if current_entity and current_known else None,
        turn_started_source_event_cursor=(
            encounter.current_turn_started_source_event_cursor
            if current_uuid and current_known
            else None
        ),
        initiative_order=rows,
    )


def _controlled_observers(session: PlayerSession) -> List[Entity]:
    """Return controlled entities that can act as subjective observers."""
    observers: List[Entity] = []
    for entity_uuid in sorted(session.controlled_entities, key=str):
        entity = Entity.get(entity_uuid)
        if entity is not None:
            observers.append(entity)
    return observers


def _observer_state(observer: Entity) -> ObservationObserverState:
    """Serialize one controlled entity's senses cache."""
    visible_cells = sorted(
        [position for position, visible in observer.senses.visible.items() if visible],
        key=_position_sort_key,
    )
    seen_cells = sorted(observer.senses.seen, key=_position_sort_key)
    return ObservationObserverState(
        observer_uuid=str(observer.uuid),
        entity_name=observer.name,
        position=observer.position,
        passive_perception=observer.get_passive_perception(),
        sense_modes=[
            {"sense_type": mode.sense_type.value, "range_feet": mode.range_feet}
            for mode in observer.senses.get_sense_modes()
        ],
        visible_cells=visible_cells,
        seen_cells=seen_cells,
        visible_entity_uuids=sorted(str(uuid) for uuid in observer.senses.entities),
        visible_object_uuids=sorted(str(uuid) for uuid in observer.senses.objects),
    )


def _known_entity_facts(
    session: PlayerSession,
    observers: List[Entity],
    remembered_entity_facts: Optional[Dict[str, ObservationEntityFact]] = None,
) -> List[ObservationEntityFact]:
    """Build entity facts known to the session."""
    known_uuids: Set[UUID] = set(session.controlled_entities)
    for observer in observers:
        known_uuids.update(observer.senses.entities.keys())
    facts_by_uuid: Dict[str, ObservationEntityFact] = {}
    for entity_uuid in sorted(known_uuids, key=str):
        if Entity.get(entity_uuid) is None:
            continue
        fact = _entity_fact(entity_uuid, session, observers, KnowledgeState.VISIBLE)
        if fact is not None:
            facts_by_uuid[fact.uuid] = fact
    for fact in (remembered_entity_facts or {}).values():
        if fact.uuid in facts_by_uuid:
            continue
        try:
            entity_uuid = UUID(fact.uuid)
        except ValueError:
            continue
        if Entity.get(entity_uuid) is None:
            continue
        if fact.knowledge_state not in {KnowledgeState.SEEN, KnowledgeState.REMEMBERED}:
            continue
        facts_by_uuid[fact.uuid] = fact
    return [facts_by_uuid[uuid] for uuid in sorted(facts_by_uuid)]


def _remembered_entity_facts_from_world(
    world: Optional[SubjectiveWorldState],
) -> Dict[str, ObservationEntityFact]:
    """Convert previously known entities into conservative last-known facts."""
    if world is None:
        return {}
    return {
        fact.uuid: fact.model_copy(update={
            "knowledge_state": KnowledgeState.REMEMBERED,
            "observer_uuids": [],
            "controlled": False,
            "hp": None,
            "max_hp": None,
            "ac": None,
            "conditions": [],
            "condition_semantic_keys": None,
            "condition_facts": None,
            "effect_protections": None,
            "damage_vulnerabilities": [],
            "damage_resistances": [],
            "damage_immunities": [],
            "is_dead": True if fact.is_dead is True else None,
        })
        for fact in world.known_entities.values()
    }


def _merge_remembered_objects(
    current: List[ObservationObjectFact],
    world: Optional[SubjectiveWorldState],
) -> List[ObservationObjectFact]:
    """Merge current objects with objects previously observed by the session."""
    facts = {fact.uuid: fact for fact in current}
    if world is not None:
        for fact in world.known_objects.values():
            facts.setdefault(
                fact.uuid,
                fact.model_copy(update={
                    "knowledge_state": KnowledgeState.REMEMBERED,
                    "observer_uuids": [],
                }),
            )
    return [facts[uuid] for uuid in sorted(facts)]


def _merge_seen_tiles(
    current: List[ObservationTileFact],
    world: Optional[SubjectiveWorldState],
) -> List[ObservationTileFact]:
    """Merge current tile knowledge with conservative previously seen cells."""
    facts = {fact.key: fact for fact in current}
    if world is not None:
        for fact in world.known_tiles.values():
            facts.setdefault(
                fact.key,
                ObservationTileFact(
                    key=fact.key,
                    position=fact.position,
                    knowledge_state=KnowledgeState.SEEN,
                ),
            )
    return [facts[key] for key in sorted(facts)]


def _entity_fact(
    entity_uuid: UUID,
    session: PlayerSession,
    observers: List[Entity],
    fallback_state: KnowledgeState = KnowledgeState.VISIBLE,
    remembered_position: Optional[Tuple[int, int]] = None,
    fact_cache: Optional[Dict[Tuple[UUID, str, Optional[Tuple[int, int]]], Optional[ObservationEntityFact]]] = None,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> Optional[ObservationEntityFact]:
    """Create an entity fact when the entity is currently known."""
    cache_key = (entity_uuid, fallback_state.value, remembered_position)
    if fact_cache is not None and cache_key in fact_cache:
        return fact_cache[cache_key]

    started = _timing_start(record_timing)
    entity = Entity.get(entity_uuid)
    _record_timing(record_timing, "projection.entity_fact.resolve_entity_ms", started)
    if entity is None:
        if fact_cache is not None:
            fact_cache[cache_key] = None
        return None
    started = _timing_start(record_timing)
    controlled = entity_uuid in session.controlled_entities
    observer_uuids = _observers_that_see(entity_uuid, observers)
    visible = bool(observer_uuids) or controlled
    knowledge_state = KnowledgeState.VISIBLE if visible else fallback_state
    _record_timing(record_timing, "projection.entity_fact.visibility_ms", started)
    if not visible and knowledge_state == KnowledgeState.UNKNOWN:
        if fact_cache is not None:
            fact_cache[cache_key] = None
        return None
    include_live_details = visible or knowledge_state == KnowledgeState.VISIBLE
    position = entity.position if include_live_details else remembered_position
    started = _timing_start(record_timing)
    vulnerabilities, resistances, immunities = _damage_affinities(entity) if include_live_details else ([], [], [])
    _record_timing(record_timing, "projection.entity_fact.damage_affinities_ms", started)
    started = _timing_start(record_timing)
    if include_live_details:
        hp, normal_hp, temporary_hp, max_hp, is_dead, healing_blocked = _entity_health_details(entity)
    else:
        hp = normal_hp = temporary_hp = max_hp = is_dead = healing_blocked = None
    _record_timing(record_timing, "projection.entity_fact.hp_ms", started)
    started = _timing_start(record_timing)
    ac = entity.ac_bonus().normalized_score if include_live_details else None
    _record_timing(record_timing, "projection.entity_fact.ac_ms", started)
    started = _timing_start(record_timing)
    conditions = list(entity.active_conditions.keys()) if include_live_details else []
    condition_semantic_keys = (
        sorted(_condition_semantic_key(condition) for condition in entity.active_conditions.values())
        if include_live_details
        else None
    )
    condition_facts = (
        sorted(
            (_condition_fact(condition) for condition in entity.active_conditions.values()),
            key=lambda fact: fact.semantic_key,
        )
        if include_live_details
        else None
    )
    effect_protections = (
        _entity_effect_protections(entity)
        if include_live_details
        else None
    )
    is_concentrating = (
        any(
            ConditionTag.CONCENTRATION in condition.tags
            for condition in entity.active_conditions.values()
        )
        if include_live_details
        else False
    )
    _record_timing(record_timing, "projection.entity_fact.conditions_death_ms", started)
    started = _timing_start(record_timing)
    fact = ObservationEntityFact(
        uuid=str(entity.uuid),
        name=entity.name,
        knowledge_state=knowledge_state,
        observer_uuids=observer_uuids,
        controlled=controlled,
        position=position,
        hp=hp,
        normal_hp=normal_hp,
        temporary_hp=temporary_hp,
        max_hp=max_hp,
        healing_blocked=healing_blocked,
        ac=ac,
        conditions=conditions,
        condition_semantic_keys=condition_semantic_keys,
        condition_facts=condition_facts,
        effect_protections=effect_protections,
        is_concentrating=is_concentrating,
        damage_vulnerabilities=vulnerabilities,
        damage_resistances=resistances,
        damage_immunities=immunities,
        creature_type=entity.creature_type.value if include_live_details else None,
        faction=entity.faction if include_live_details else None,
        is_dead=is_dead,
    )
    _record_timing(record_timing, "projection.entity_fact.construct_model_ms", started)
    if fact_cache is not None:
        fact_cache[cache_key] = fact
    return fact


def _damage_affinities(entity: Entity) -> tuple[List[str], List[str], List[str]]:
    """Return visible damage affinity labels for an entity."""
    vulnerabilities: List[str] = []
    resistances: List[str] = []
    immunities: List[str] = []
    for damage_type in DamageType:
        resistance = entity.health.get_resistance(damage_type)
        if resistance == ResistanceStatus.VULNERABILITY:
            vulnerabilities.append(damage_type.value)
        elif resistance == ResistanceStatus.RESISTANCE:
            resistances.append(damage_type.value)
        elif resistance == ResistanceStatus.IMMUNITY:
            immunities.append(damage_type.value)
    return vulnerabilities, resistances, immunities


def _entity_effect_protections(entity: Entity) -> List[ObservationEffectProtection]:
    """Return typed protections supplied by currently visible conditions."""
    protections = [
        ObservationEffectProtection(
            protection_id=protection.protection_id,
            blocked_effect_ids=sorted(protection.blocked_effect_ids),
            source_condition_semantic_key=_condition_semantic_key(condition),
        )
        for condition in entity.active_conditions.values()
        for protection in condition.outcome_protections
    ]
    return sorted(
        protections,
        key=lambda protection: (
            protection.protection_id,
            protection.source_condition_semantic_key or "",
        ),
    )


def _known_object_facts(observers: List[Entity]) -> List[ObservationObjectFact]:
    """Build object facts known to the session."""
    object_observers: Dict[UUID, Set[str]] = {}
    object_positions: Dict[UUID, Tuple[int, int]] = {}
    for observer in observers:
        for object_uuid, position in observer.senses.objects.items():
            object_observers.setdefault(object_uuid, set()).add(str(observer.uuid))
            object_positions[object_uuid] = position

    facts: List[ObservationObjectFact] = []
    for object_uuid in sorted(object_observers, key=str):
        fact = _object_fact(object_uuid, object_positions.get(object_uuid), object_observers[object_uuid])
        if fact is not None:
            facts.append(fact)
    return facts


def _object_fact(
    object_uuid: UUID,
    position: Optional[Tuple[int, int]],
    observer_uuids: Iterable[str],
) -> Optional[ObservationObjectFact]:
    """Create an object fact from current engine state."""
    obj = BaseBlock.get(object_uuid)
    if obj is None:
        return None
    return ObservationObjectFact(
        uuid=str(object_uuid),
        name=obj.name or "Object",
        knowledge_state=KnowledgeState.VISIBLE,
        observer_uuids=sorted(observer_uuids),
        position=position or obj.position,
        map_char=getattr(obj, "map_char", None),
        state=_object_state(obj),
    )


def _known_tile_facts(observers: List[Entity]) -> List[ObservationTileFact]:
    """Build tile facts visible or previously seen by controlled observers."""
    visible_by_pos: Dict[Tuple[int, int], Set[str]] = {}
    seen_by_pos: Dict[Tuple[int, int], Set[str]] = {}
    for observer in observers:
        observer_id = str(observer.uuid)
        for position, visible in observer.senses.visible.items():
            if visible:
                visible_by_pos.setdefault(position, set()).add(observer_id)
        for position in observer.senses.seen:
            seen_by_pos.setdefault(position, set()).add(observer_id)

    facts: List[ObservationTileFact] = []
    all_positions = set(visible_by_pos) | set(seen_by_pos)
    hazards_present = get_map().has_any_hazards()
    for position in sorted(all_positions, key=_position_sort_key):
        if position in visible_by_pos:
            facts.append(
                _visible_tile_fact(
                    position,
                    visible_by_pos[position],
                    hazards_present=hazards_present,
                )
            )
        else:
            facts.append(ObservationTileFact(
                key=_tile_key(position),
                position=position,
                knowledge_state=KnowledgeState.SEEN,
                observer_uuids=sorted(seen_by_pos[position]),
                adjacent_domain=_adjacent_domain_knowledge(position),
            ))
    return facts


def _visible_tile_fact(
    position: Tuple[int, int],
    observer_uuids: Iterable[str],
    *,
    hazards_present: Optional[bool] = None,
) -> ObservationTileFact:
    """Create a visible tile fact with current public tile data."""
    observer_ids = sorted(observer_uuids)
    grid = get_map()
    tile = grid.get_tile(*position)
    if tile is None:
        return ObservationTileFact(
            key=_tile_key(position),
            position=position,
            knowledge_state=KnowledgeState.VISIBLE,
            observer_uuids=observer_ids,
        )
    first_observer = observer_ids[0] if observer_ids else None
    is_hazardous = (
        grid.is_position_hazardous_for(
            position[0],
            position[1],
            UUID(first_observer) if first_observer else None,
        )
        if (grid.has_any_hazards() if hazards_present is None else hazards_present)
        else False
    )
    return ObservationTileFact(
        key=_tile_key(position),
        position=position,
        knowledge_state=KnowledgeState.VISIBLE,
        observer_uuids=observer_ids,
        name=tile.name,
        walkable=tile.walkable,
        walking_cost=int(tile.walking_cost.normalized_score) if hasattr(tile, "walking_cost") else 1,
        is_hazardous=is_hazardous,
        conditions=list(getattr(tile, "active_conditions", {}).keys()),
        light_level=tile.resolved_light_level.value,
        directional_blocks_movement=_directional_blocks(tile, "movement"),
        directional_blocks_vision=_directional_blocks(tile, "vision"),
        directional_blocks_light=_directional_blocks(tile, "light"),
        directional_blocks_propagation=_directional_blocks(tile, "propagation"),
        adjacent_domain=_adjacent_domain_knowledge(position),
    )


def _adjacent_domain_knowledge(
    position: Tuple[int, int],
) -> Dict[AdjacentOffset, SpatialDomainKnowledge]:
    """Disclose only known local boundaries around one perceived tile."""
    global _adjacent_domain_cache_revision
    grid = get_map()
    revision = grid.movement_revision
    if _adjacent_domain_cache_revision != revision:
        _adjacent_domain_cache_revision = revision
        _adjacent_domain_cache.clear()
    cached = _adjacent_domain_cache.get(position)
    if cached is not None:
        return dict(cached)
    result = {
        offset: (
            SpatialDomainKnowledge.INVALID
            if grid.get_tile(
                position[0] + offset.delta[0],
                position[1] + offset.delta[1],
            )
            is None
            else SpatialDomainKnowledge.UNKNOWN
        )
        for offset in AdjacentOffset
    }
    _adjacent_domain_cache[position] = result
    return dict(result)


def _visible_tile_fact_cached(
    position: Tuple[int, int],
    observer_uuids: Iterable[str],
    projection_context: Optional[_ProjectionPassContext] = None,
) -> ObservationTileFact:
    """Create a visible tile fact, reusing pass-local projection cache."""
    observer_ids = tuple(sorted(observer_uuids))
    if projection_context is None:
        return _visible_tile_fact(position, observer_ids)
    cache_key = (position, observer_ids)
    fact = projection_context.tile_facts.get(cache_key)
    if fact is None:
        if projection_context.has_any_hazards is None:
            projection_context.has_any_hazards = get_map().has_any_hazards()
        fact = _visible_tile_fact(
            position,
            observer_ids,
            hazards_present=projection_context.has_any_hazards,
        )
        projection_context.tile_facts[cache_key] = fact
    return fact


def _sensory_patches(
    event: SensoryUpdateEvent,
    session: PlayerSession,
    observers: List[Entity],
    projection_context: Optional[_ProjectionPassContext] = None,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> List[ObservationPatch]:
    """Build observer and fact patches from a sensory update event."""
    started = _timing_start(record_timing)
    data = {
        "observer_uuid": str(event.observer_uuid),
        "position": (
            list(event.observer_position)
            if event.observer_position_changed
            else None
        ),
        "update_reason": event.update_reason.value,
        "visible_cells_added": [list(position) for position in event.visible_cells_added],
        "visible_cells_removed": [list(position) for position in event.visible_cells_removed],
        "seen_cells_added": [list(position) for position in event.seen_cells_added],
        "visible_entities_added": _uuid_position_json(event.visible_entities_added),
        "visible_entities_removed": _uuid_position_json(event.visible_entities_removed),
        "visible_entities_moved": _uuid_move_json(event.visible_entities_moved),
        "visible_objects_added": _uuid_position_json(event.visible_objects_added),
        "visible_objects_removed": _uuid_position_json(event.visible_objects_removed),
        "visible_objects_moved": _uuid_move_json(event.visible_objects_moved),
        "paths_dirty": event.paths_dirty,
        "passive_perception": event.passive_perception,
        "sense_modes": event.sense_modes,
    }
    _record_timing(record_timing, "projection.sensory_patches.observer_data_ms", started)
    started = _timing_start(record_timing)
    patches = [
        ObservationPatch(
            patch_type=ObservationPatchType.OBSERVER,
            reason=event.update_reason.value,
            observer_uuid=str(event.observer_uuid),
            data=data,
        )
    ]
    _record_timing(record_timing, "projection.sensory_patches.observer_patch_ms", started)

    started = _timing_start(record_timing)
    for entity_uuid, position in event.visible_entities_added.items():
        fact = _entity_fact(
            entity_uuid,
            session,
            observers,
            KnowledgeState.VISIBLE,
            position,
            projection_context.entity_facts if projection_context else None,
            record_timing,
        )
        if fact is not None:
            patches.append(_entity_patch(fact, event.update_reason.value))
    _record_timing(record_timing, "projection.sensory_patches.entity_added_ms", started)
    started = _timing_start(record_timing)
    for entity_uuid, positions in event.visible_entities_moved.items():
        patch = _entity_position_patch_if_known(
            entity_uuid,
            session,
            observers,
            positions[1],
            event.update_reason.value,
        )
        if patch is not None:
            patches.append(patch)
    _record_timing(record_timing, "projection.sensory_patches.entity_moved_ms", started)
    started = _timing_start(record_timing)
    for entity_uuid, position in event.visible_entities_removed.items():
        fact = _entity_fact(
            entity_uuid,
            session,
            observers,
            KnowledgeState.REMEMBERED,
            position,
            projection_context.entity_facts if projection_context else None,
            record_timing,
        )
        if fact is not None:
            if event.update_reason == SensoryUpdateReason.DEATH:
                fact = fact.model_copy(update={"is_dead": True})
            patches.append(_entity_patch(fact, event.update_reason.value))
    _record_timing(record_timing, "projection.sensory_patches.entity_removed_ms", started)

    started = _timing_start(record_timing)
    for object_uuid, position in event.visible_objects_added.items():
        fact = _object_fact(object_uuid, position, [str(event.observer_uuid)])
        if fact is not None:
            patches.append(_object_patch(fact, event.update_reason.value))
    _record_timing(record_timing, "projection.sensory_patches.object_added_ms", started)
    started = _timing_start(record_timing)
    for object_uuid, position in event.visible_objects_removed.items():
        fact = _object_fact(object_uuid, position, [str(event.observer_uuid)])
        if fact is not None:
            remembered = fact.model_copy(update={"knowledge_state": KnowledgeState.REMEMBERED})
            patches.append(_object_patch(remembered, event.update_reason.value))
    _record_timing(record_timing, "projection.sensory_patches.object_removed_ms", started)

    started = _timing_start(record_timing)
    observer_id = str(event.observer_uuid)
    tile_facts: List[ObservationTileFact] = []
    for position in sorted(
        set(event.visible_cells_added) | set(event.seen_cells_added),
        key=_position_sort_key,
    ):
        tile_facts.append(
            _visible_tile_fact_cached(position, [observer_id], projection_context)
        )
    _record_timing(record_timing, "projection.sensory_patches.visible_tile_patches_ms", started)
    started = _timing_start(record_timing)
    for position in sorted(event.visible_cells_removed, key=_position_sort_key):
        tile_facts.append(ObservationTileFact(
            key=_tile_key(position),
            position=position,
            knowledge_state=KnowledgeState.SEEN,
            observer_uuids=[observer_id],
        ))
    if tile_facts:
        patches.append(_tiles_patch(tile_facts, event.update_reason.value))
    _record_timing(record_timing, "projection.sensory_patches.removed_tile_patches_ms", started)
    return patches


def _sensory_event_has_subjective_delta(event: SensoryUpdateEvent) -> bool:
    """Return whether a sensory event carries changed session facts.

    Path dirtiness by itself is an engine cache invalidation signal. The
    subjective stream only needs a frame when visible cells, seen cells,
    visible entities, visible objects, passive perception, or sense modes
    actually changed.
    """
    return bool(
        event.visible_cells_added
        or event.visible_cells_removed
        or event.seen_cells_added
        or event.visible_entities_added
        or event.visible_entities_removed
        or event.visible_entities_moved
        or event.visible_objects_added
        or event.visible_objects_removed
        or event.visible_objects_moved
        or event.observer_position_changed
        or event.sense_modes_changed
        or event.passive_perception_changed
    )


def _event_state_patches(
    event: Event,
    session: PlayerSession,
    game: Optional[GameSession],
    encounter: Optional[Encounter],
    observers: List[Entity],
    source_event_cursor: int,
    projection_context: Optional[_ProjectionPassContext] = None,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> List[ObservationPatch]:
    """Build state patches from a visible completion event."""
    patches: List[ObservationPatch] = []
    event_type_key = event.event_type.value
    if event.event_type in {
        EventType.ENCOUNTER_START,
        EventType.ENCOUNTER_END,
        EventType.ROUND_START,
        EventType.ROUND_END,
        EventType.TURN_START,
        EventType.TURN_END,
    }:
        started = _timing_start(record_timing)
        patches.append(_session_patch(_session_state(session, game), event.event_type.value))
        _record_timing(
            record_timing,
            f"projection.project_completion_event_detail.{event_type_key}.state_patches.session_ms",
            started,
        )
        if encounter is not None:
            started = _timing_start(record_timing)
            patches.append(_encounter_patch(_encounter_state(encounter, session, observers), event.event_type.value))
            _record_timing(
                record_timing,
                f"projection.project_completion_event_detail.{event_type_key}.state_patches.encounter_ms",
                started,
            )

    if _event_should_patch_entity_hit_points(event.event_type):
        referenced_started = _timing_start(record_timing)
        for entity_uuid in _entity_uuids_referenced_by(event):
            started = _timing_start(record_timing)
            patch = _entity_hit_point_patch_if_known(
                entity_uuid,
                session,
                observers,
                event,
            )
            _record_timing(
                record_timing,
                f"projection.project_completion_event_detail.{event_type_key}.state_patches.entity_hp_patch_ms",
                started,
            )
            if patch is not None:
                patches.append(patch)
        _record_timing(
            record_timing,
            f"projection.project_completion_event_detail.{event_type_key}.state_patches.referenced_entity_hp_total_ms",
            referenced_started,
        )
    elif _event_should_patch_entity_positions(event.event_type):
        referenced_started = _timing_start(record_timing)
        for entity_uuid in _entity_uuids_referenced_by(event):
            position = _event_entity_position(entity_uuid, event)
            if position is None:
                continue
            started = _timing_start(record_timing)
            patch = _entity_position_patch_if_known(
                entity_uuid,
                session,
                observers,
                position,
                event.event_type.value,
            )
            _record_timing(
                record_timing,
                f"projection.project_completion_event_detail.{event_type_key}.state_patches.entity_position_patch_ms",
                started,
            )
            if patch is not None:
                patches.append(patch)
        _record_timing(
            record_timing,
            f"projection.project_completion_event_detail.{event_type_key}.state_patches.referenced_entity_positions_total_ms",
            referenced_started,
        )
    elif _event_should_patch_referenced_entities(event.event_type):
        referenced_started = _timing_start(record_timing)
        for entity_uuid in _entity_uuids_referenced_by(event):
            started = _timing_start(record_timing)
            entity_known_live = entity_uuid in session.controlled_entities or _entity_visible_to_session(entity_uuid, observers)
            _record_timing(
                record_timing,
                f"projection.project_completion_event_detail.{event_type_key}.state_patches.entity_visibility_ms",
                started,
            )
            started = _timing_start(record_timing)
            fact = _entity_fact(
                entity_uuid,
                session,
                observers,
                KnowledgeState.VISIBLE if entity_known_live else KnowledgeState.UNKNOWN,
                fact_cache=projection_context.entity_facts if projection_context else None,
                record_timing=record_timing,
            )
            if fact is not None:
                fact = _entity_fact_at_event_completion(
                    fact,
                    event,
                    source_event_cursor=source_event_cursor,
                )
            _record_timing(
                record_timing,
                f"projection.project_completion_event_detail.{event_type_key}.state_patches.entity_fact_ms",
                started,
            )
            if fact is not None:
                started = _timing_start(record_timing)
                patches.append(_entity_patch(fact, event.event_type.value))
                _record_timing(
                    record_timing,
                    f"projection.project_completion_event_detail.{event_type_key}.state_patches.entity_patch_ms",
                    started,
                )
        _record_timing(
            record_timing,
            f"projection.project_completion_event_detail.{event_type_key}.state_patches.referenced_entities_total_ms",
            referenced_started,
        )

    for block_uuid in _block_uuids_referenced_by(event):
        spatial_location = _spatial_block_location(block_uuid)
        if spatial_location is None:
            continue
        block_position, location_kind = spatial_location
        if not _position_visible_to_session(block_position, observers):
            continue
        observer_uuids = _observers_that_see_position(block_position, observers)
        if location_kind == "tile":
            patches.append(_tile_patch(
                _visible_tile_fact_cached(block_position, observer_uuids, projection_context),
                event.event_type.value,
            ))
            continue
        fact = _object_fact(block_uuid, block_position, observer_uuids)
        if fact is not None:
            patches.append(_object_patch(fact, event.event_type.value))

    position = getattr(event, "position", None)
    if isinstance(position, tuple) and _position_visible_to_session(position, observers):
        started = _timing_start(record_timing)
        patches.append(_tile_patch(
            _visible_tile_fact_cached(
                position,
                _observers_that_see_position(position, observers),
                projection_context,
            ),
            event.event_type.value,
        ))
        _record_timing(
            record_timing,
            f"projection.project_completion_event_detail.{event_type_key}.state_patches.tile_patch_ms",
            started,
        )

    object_uuid = getattr(event, "object_uuid", None)
    if object_uuid and position and _position_visible_to_session(position, observers):
        started = _timing_start(record_timing)
        fact = _object_fact(object_uuid, position, _observers_that_see_position(position, observers))
        if fact is not None:
            patches.append(_object_patch(fact, event.event_type.value))
        _record_timing(
            record_timing,
            f"projection.project_completion_event_detail.{event_type_key}.state_patches.object_patch_ms",
            started,
        )

    return patches


def _entity_fact_at_event_completion(
    fact: ObservationEntityFact,
    event: Event,
    *,
    source_event_cursor: int,
) -> ObservationEntityFact:
    """Apply event-owned facts not yet indexed during synchronous callbacks.

    Condition modifiers and subconditions are applied before the application
    completion is emitted, while the owning block indexes the condition
    immediately after that callback returns. The completed event is the
    authoritative post-application boundary, so its condition belongs in the
    projected fact even during the synchronous callback.

    Args:
        fact: Entity fact read from the current engine indexes.
        event: Completed engine event being projected.

    Returns:
        Event-time entity fact with authoritative application data merged in.
    """
    if (
        not isinstance(event, ConditionApplicationEvent)
        or event.target_entity_uuid is None
        or fact.uuid != str(event.target_entity_uuid)
    ):
        return fact
    condition_name = event.condition.name
    condition_semantic_key = _condition_semantic_key(event.condition)
    condition_fact = _condition_fact(
        event.condition,
        applied_source_event_cursor=source_event_cursor,
    )
    condition_protections = [
        ObservationEffectProtection(
            protection_id=protection.protection_id,
            blocked_effect_ids=sorted(protection.blocked_effect_ids),
            source_condition_semantic_key=condition_semantic_key,
        )
        for protection in event.condition.outcome_protections
    ]
    has_name = condition_name is not None and condition_name in fact.conditions
    has_semantic_key = (
        fact.condition_semantic_keys is not None
        and condition_semantic_key in fact.condition_semantic_keys
    )
    has_condition_fact = (
        fact.condition_facts is not None
        and any(
            row.semantic_key == condition_semantic_key
            for row in fact.condition_facts
        )
    )
    if has_name and has_semantic_key and has_condition_fact:
        return fact
    return fact.model_copy(
        update={
            "conditions": (
                fact.conditions
                if condition_name is None or has_name
                else [*fact.conditions, condition_name]
            ),
            "condition_semantic_keys": (
                None
                if fact.condition_semantic_keys is None
                else (
                    fact.condition_semantic_keys
                    if has_semantic_key
                    else [*fact.condition_semantic_keys, condition_semantic_key]
                )
            ),
            "condition_facts": (
                None
                if fact.condition_facts is None
                else sorted(
                    {
                        row.semantic_key: row
                        for row in [*fact.condition_facts, condition_fact]
                    }.values(),
                    key=lambda row: row.semantic_key,
                )
            ),
            "effect_protections": (
                None
                if fact.effect_protections is None
                else sorted(
                    {
                        protection.protection_id: protection
                        for protection in [
                            *fact.effect_protections,
                            *condition_protections,
                        ]
                    }.values(),
                    key=lambda protection: protection.protection_id,
                )
            ),
            "is_concentrating": (
                fact.is_concentrating
                or ConditionTag.CONCENTRATION in event.condition.tags
            ),
        }
    )


def _condition_semantic_key(condition: object) -> str:
    """Return a stable type key for one condition without using display text."""
    condition_type = type(condition)
    return f"{condition_type.__module__}.{condition_type.__qualname__}"


def _condition_fact(
    condition: BaseCondition,
    *,
    applied_source_event_cursor: Optional[int] = None,
) -> ObservationConditionFact:
    """Project visible engine-owned lifecycle semantics for one condition."""
    return ObservationConditionFact(
        semantic_key=_condition_semantic_key(condition),
        removal_triggers=sorted(
            condition.removal_triggers,
            key=lambda trigger: trigger.value,
        ),
        agency_denial=condition.agency_denial,
        applied_source_event_cursor=(
            condition.applied_source_event_cursor
            if applied_source_event_cursor is None
            else applied_source_event_cursor
        ),
    )


def _event_should_patch_referenced_entities(event_type: EventType) -> bool:
    """Return whether an event can change visible entity facts."""
    return event_type in {
        EventType.MOVEMENT,
        EventType.STEP_MOVEMENT,
        EventType.FORCED_MOVEMENT,
        EventType.CONDITION_APPLICATION,
        EventType.CONDITION_REMOVAL,
        EventType.WEAPON_EQUIP,
        EventType.WEAPON_UNEQUIP,
        EventType.ARMOR_EQUIP,
        EventType.ARMOR_UNEQUIP,
        EventType.SHIELD_EQUIP,
        EventType.SHIELD_UNEQUIP,
        EventType.SPATIAL_ENTITY_ENTERED,
        EventType.SPATIAL_ENTITY_LEFT,
        EventType.SPATIAL_PERCEIVABILITY_CHANGED,
        EventType.DEATH_SAVE,
        EventType.INSTANT_DEATH,
        EventType.DEATH,
    }


def _event_should_patch_entity_hit_points(event_type: EventType) -> bool:
    """Return whether an event needs only HP/death entity fact updates."""
    return event_type in {
        EventType.DAMAGE_APPLIED,
        EventType.HEAL,
    }


def _event_should_patch_entity_positions(event_type: EventType) -> bool:
    """Return whether an event needs only final known position updates."""
    return event_type in {
        EventType.MOVEMENT,
        EventType.FORCED_MOVEMENT,
    }


def _event_visible_to_session(
    event: Event,
    session: PlayerSession,
    observers: List[Entity],
    *,
    filtered_combat_log: Optional[CombatLogEntry] = None,
    combat_log_checked: bool = False,
) -> bool:
    """Return whether a source event should produce any subjective frame."""
    if event.event_type in {
        EventType.ENCOUNTER_START,
        EventType.ENCOUNTER_END,
        EventType.ROUND_START,
        EventType.ROUND_END,
        EventType.TURN_START,
        EventType.TURN_END,
    }:
        return True
    if combat_log_checked:
        if filtered_combat_log is not None:
            return True
    elif _filtered_combat_log(event.combat_log, session, observers) is not None:
        return True
    for entity_uuid in _entity_uuids_referenced_by(event):
        if entity_uuid in session.controlled_entities or _entity_visible_to_session(entity_uuid, observers):
            return True
    for block_uuid in _block_uuids_referenced_by(event):
        spatial_location = _spatial_block_location(block_uuid)
        if spatial_location is not None and _position_visible_to_session(spatial_location[0], observers):
            return True
    for position in event.get_affected_positions():
        if _position_visible_to_session(position, observers):
            return True
    return False


def _filtered_combat_log(
    log: Optional[CombatLogEntry],
    session: PlayerSession,
    observers: List[Entity],
    context: Optional[_CombatLogFilterContext] = None,
) -> Optional[CombatLogEntry]:
    """Return a combat log filtered to this session, or None when hidden."""
    if log is None:
        return None
    filter_context = context or _build_combat_log_filter_context(session, observers)
    return _filtered_combat_log_with_context(log, filter_context)


def _build_combat_log_filter_context(
    session: PlayerSession,
    observers: List[Entity],
) -> _CombatLogFilterContext:
    """Build reusable visibility facts for combat-log filtering."""
    known_entity_uuids = {str(uuid) for uuid in session.controlled_entities}
    for observer in observers:
        known_entity_uuids.update(str(uuid) for uuid in observer.senses.entities)

    return _CombatLogFilterContext(
        known_entity_uuids=known_entity_uuids,
        controlled_entity_uuids={str(uuid) for uuid in session.controlled_entities},
    )


def _filtered_combat_log_with_context(
    log: CombatLogEntry,
    context: _CombatLogFilterContext,
) -> Optional[CombatLogEntry]:
    """Filter one combat-log tree using a reusable session visibility context."""
    cache_key = id(log)
    if cache_key in context.filtered_cache:
        return context.filtered_cache[cache_key]

    perceivers = set(log.perceiver_uuids)
    directly_involved = {value for value in (log.source_uuid, log.target_uuid) if value}
    visible = bool(perceivers & context.controlled_entity_uuids) or bool(directly_involved & context.controlled_entity_uuids)
    if not perceivers:
        visible = visible or bool(directly_involved & context.known_entity_uuids)

    filtered_children: List[CombatLogEntry] = []
    children_unchanged = True
    for child in log.sub_entries:
        filtered_child = _filtered_combat_log_with_context(child, context)
        if filtered_child is None:
            children_unchanged = False
            continue
        if filtered_child is not child:
            children_unchanged = False
        filtered_children.append(filtered_child)

    if not visible and not filtered_children:
        context.filtered_cache[cache_key] = None
        return None

    hidden_uuids, hidden_names = _collect_unknown_log_identities(log, context)
    sanitized_log = _sanitize_unseen_log_identity(
        log,
        context,
        hidden_uuids=hidden_uuids,
        hidden_names=hidden_names,
        filtered_children=filtered_children,
    )
    sanitized_log = _sanitize_unlocated_movement_step(sanitized_log, context)
    sanitized_log = _sanitize_partially_observed_movement(
        log,
        sanitized_log,
        filtered_children,
    )
    if visible and sanitized_log is log and children_unchanged and len(filtered_children) == len(log.sub_entries):
        context.filtered_cache[cache_key] = log
        return log

    filtered_log = sanitized_log.model_copy(update={"sub_entries": filtered_children})
    context.filtered_cache[cache_key] = filtered_log
    return filtered_log


def _identified_entities_for_session(
    log: CombatLogEntry,
    context: _CombatLogFilterContext,
) -> Set[str]:
    """Return participants identified by a controlled observer at event time."""
    return {
        entity_uuid
        for entity_uuid, observer_uuids in log.identified_entity_observer_uuids.items()
        if observer_uuids & context.controlled_entity_uuids
    }


def _sanitize_unseen_log_identity(
    log: CombatLogEntry,
    context: _CombatLogFilterContext,
    *,
    hidden_uuids: Optional[Set[str]] = None,
    hidden_names: Optional[Set[str]] = None,
    filtered_children: Optional[List[CombatLogEntry]] = None,
) -> CombatLogEntry:
    """Remove live identity and path facts for log entities not known to this session."""
    known_or_revealed = (
        context.known_entity_uuids
        | context.controlled_entity_uuids
        | set(log.revealed_entity_uuids)
        | _identified_entities_for_session(log, context)
    )
    source_unknown = bool(log.source_uuid and log.source_uuid not in known_or_revealed)
    target_unknown = bool(log.target_uuid and log.target_uuid not in known_or_revealed)
    hidden_uuids = set(hidden_uuids or set())
    hidden_names = set(hidden_names or set())
    if not source_unknown and not target_unknown and not hidden_uuids and not hidden_names:
        return log

    updates: Dict[str, Any] = {}
    hidden_uuids.update({
        uuid
        for uuid, hidden in ((log.source_uuid, source_unknown), (log.target_uuid, target_unknown))
        if uuid and hidden
    })
    hidden_names.update({
        name
        for name, hidden in ((log.source_name, source_unknown), (log.target_name, target_unknown))
        if name and hidden
    })
    updates["perceiver_uuids"] = set(log.perceiver_uuids) - hidden_uuids
    updates["revealed_entity_uuids"] = set(log.revealed_entity_uuids) - hidden_uuids
    data = _sanitize_unseen_log_data(log.data, hidden_uuids, hidden_names)
    if filtered_children is not None:
        data = _sanitize_multi_entity_log_summary(log, filtered_children, data)
    updates["data"] = data
    updates["compact"] = _sanitize_unseen_log_text(log.compact, hidden_uuids, hidden_names)
    updates["verbose"] = _sanitize_unseen_log_text(log.verbose, hidden_uuids, hidden_names)
    updates["detailed"] = _sanitize_unseen_log_text(log.detailed, hidden_uuids, hidden_names)
    if source_unknown:
        updates.update({
            "source_name": "Unknown",
            "source_uuid": "",
        })
    if target_unknown:
        updates.update({
            "target_name": "Unknown",
            "target_uuid": "",
        })

    if log.entry_type.value == "movement" and source_unknown:
        updates.update({
            "compact": "Something moves nearby",
            "verbose": "Something moves nearby",
            "detailed": "Something moves nearby",
            "data": {"type": "movement", "observed": True},
        })
    elif log.entry_type.value == "turn_start" and source_unknown:
        updates.update({
            "compact": "An unknown combatant's turn begins",
            "verbose": "An unknown combatant's turn begins",
            "detailed": "An unknown combatant's turn begins",
        })
    elif log.entry_type.value == "turn_end" and source_unknown:
        updates.update({
            "compact": "An unknown combatant's turn ends",
            "verbose": "An unknown combatant's turn ends",
            "detailed": "An unknown combatant's turn ends",
        })

    return log.model_copy(update=updates)


def _sanitize_unlocated_movement_step(
    log: CombatLogEntry,
    context: _CombatLogFilterContext,
) -> CombatLogEntry:
    """Retain a known mover's identity while removing an unlocated step."""
    if (
        log.entry_type is not CombatLogEntryType.MOVEMENT
        or log.data.get("type") != "step_movement"
        or not log.source_uuid
    ):
        return log
    located_by = log.located_entity_observer_uuids.get(log.source_uuid, set())
    if located_by & context.controlled_entity_uuids:
        return log
    source_name = log.source_name or "Known entity"
    text = f"{{cyan:{source_name}}} moves outside current perception"
    return log.model_copy(update={
        "compact": text,
        "verbose": text,
        "detailed": text,
        "data": {
            "type": "movement",
            "observation_complete": False,
        },
    })


def _sanitize_partially_observed_movement(
    original_log: CombatLogEntry,
    sanitized_log: CombatLogEntry,
    filtered_children: List[CombatLogEntry],
) -> CombatLogEntry:
    """Replace an objective movement summary with only perceived step segments."""
    if original_log.entry_type is not CombatLogEntryType.MOVEMENT or not sanitized_log.source_uuid:
        return sanitized_log

    original_steps = [
        child
        for child in original_log.sub_entries
        if child.entry_type is CombatLogEntryType.MOVEMENT
        and child.data.get("type") == "step_movement"
    ]
    filtered_steps = [
        child
        for child in filtered_children
        if child.entry_type is CombatLogEntryType.MOVEMENT
        and child.data.get("type") == "step_movement"
    ]
    if not original_steps or len(filtered_steps) == len(original_steps):
        return sanitized_log

    ordered_steps = sorted(
        filtered_steps,
        key=lambda child: int(child.data.get("path_index", 0)),
    )
    segments: List[List[Tuple[int, int]]] = []
    observed_cost = 0.0
    for step in ordered_steps:
        origin = _combat_log_position(step.data.get("from_position"))
        destination = _combat_log_position(step.data.get("to_position"))
        if origin is None or destination is None:
            continue
        observed_cost += float(step.data.get("movement_cost", 0.0))
        if segments and segments[-1][-1] == origin:
            segments[-1].append(destination)
        else:
            segments.append([origin, destination])

    identity_data = {
        key: value
        for key, value in sanitized_log.data.items()
        if key in {"entity_name", "entity_uuid", "movement_type"}
    }
    data: Dict[str, Any] = {
        **identity_data,
        "type": "movement",
        "observation_complete": False,
        "observed_path_segments": segments,
        "observed_distance_feet": observed_cost,
    }
    if len(segments) == 1:
        data.update({
            "start_position": segments[0][0],
            "end_position": segments[0][-1],
            "path": segments[0],
            "distance_feet": observed_cost,
            "movement_cost": observed_cost,
        })

    source_name = sanitized_log.source_name or "Known entity"
    if len(segments) == 1:
        destination = segments[0][-1]
        compact = (
            f"{{cyan:{source_name}}} is observed moving "
            f"{{green:{observed_cost:g}ft}} to {{yellow:{destination}}}"
        )
        verbose = f"{compact} (partial movement observation)"
        path_text = " -> ".join(str(position) for position in segments[0])
        detailed = f"{verbose}\n  Observed path: {path_text}"
    elif segments:
        compact = f"{{cyan:{source_name}}} is observed moving across {len(segments)} visible segments"
        verbose = f"{compact} (partial movement observation)"
        segment_text = "; ".join(
            " -> ".join(str(position) for position in segment)
            for segment in segments
        )
        detailed = f"{verbose}\n  Observed segments: {segment_text}"
    else:
        compact = f"{{cyan:{source_name}}} moves outside current perception"
        verbose = compact
        detailed = compact

    return sanitized_log.model_copy(update={
        "compact": compact,
        "verbose": verbose,
        "detailed": detailed,
        "data": data,
    })


def _combat_log_position(value: Any) -> Optional[Tuple[int, int]]:
    """Normalize a structured combat-log position without accepting other shapes."""
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(coordinate, int) and not isinstance(coordinate, bool) for coordinate in value)
    ):
        return int(value[0]), int(value[1])
    return None


def _sanitize_unseen_log_data(
    data: Dict[str, Any],
    hidden_uuids: Set[str],
    hidden_names: Set[str],
) -> Dict[str, Any]:
    """Remove hidden entity identity values from structured combat-log data."""
    sanitized: Dict[str, Any] = {}
    for key, value in data.items():
        sanitized_value = _sanitize_unseen_log_value(key, value, hidden_uuids, hidden_names)
        if sanitized_value is _DROP_HIDDEN_VALUE:
            continue
        sanitized[key] = sanitized_value
    return sanitized


_DROP_HIDDEN_VALUE = object()


def _sanitize_unseen_log_value(
    key: str,
    value: Any,
    hidden_uuids: Set[str],
    hidden_names: Set[str],
) -> Any:
    """Sanitize a structured combat-log value recursively."""
    if isinstance(value, str):
        if value in hidden_uuids:
            return _DROP_HIDDEN_VALUE
        return _sanitize_unseen_log_text(value, hidden_uuids, hidden_names)
    if isinstance(value, dict):
        sanitized_dict: Dict[str, Any] = {}
        for child_key, child_value in value.items():
            sanitized_value = _sanitize_unseen_log_value(str(child_key), child_value, hidden_uuids, hidden_names)
            if sanitized_value is not _DROP_HIDDEN_VALUE:
                sanitized_dict[str(child_key)] = sanitized_value
        return sanitized_dict
    if isinstance(value, list):
        sanitized_list: List[Any] = []
        for item in value:
            sanitized_value = _sanitize_unseen_log_value(key, item, hidden_uuids, hidden_names)
            if sanitized_value is not _DROP_HIDDEN_VALUE:
                sanitized_list.append(sanitized_value)
        return sanitized_list
    if isinstance(value, tuple):
        sanitized_items: List[Any] = []
        for item in value:
            sanitized_value = _sanitize_unseen_log_value(key, item, hidden_uuids, hidden_names)
            if sanitized_value is not _DROP_HIDDEN_VALUE:
                sanitized_items.append(sanitized_value)
        return tuple(sanitized_items)
    return value


def _sanitize_unseen_log_text(
    text: str,
    hidden_uuids: Set[str],
    hidden_names: Set[str],
) -> str:
    """Replace hidden identity tokens in a subjective combat-log string."""
    sanitized = text
    for hidden_uuid in hidden_uuids:
        sanitized = sanitized.replace(hidden_uuid, "")
    for hidden_name in hidden_names:
        sanitized = sanitized.replace(hidden_name, "Unknown")
    return sanitized


def _collect_unknown_log_identities(
    log: CombatLogEntry,
    context: _CombatLogFilterContext,
    inherited_revealed_uuids: Optional[Set[str]] = None,
) -> Tuple[Set[str], Set[str]]:
    """Collect unknown source/target identities from a log tree."""
    inherited_revealed_uuids = inherited_revealed_uuids or set()
    revealed_uuids = inherited_revealed_uuids | set(log.revealed_entity_uuids)
    known_or_revealed = (
        context.known_entity_uuids
        | context.controlled_entity_uuids
        | revealed_uuids
        | _identified_entities_for_session(log, context)
    )
    hidden_uuids: Set[str] = set()
    hidden_names: Set[str] = set()
    for uuid_value, name_value in ((log.source_uuid, log.source_name), (log.target_uuid, log.target_name)):
        if uuid_value and uuid_value not in known_or_revealed:
            hidden_uuids.add(uuid_value)
            if name_value:
                hidden_names.add(name_value)
    hidden_uuids.update(uuid for uuid in log.perceiver_uuids if uuid not in known_or_revealed)
    for child in log.sub_entries:
        child_uuids, child_names = _collect_unknown_log_identities(child, context, revealed_uuids)
        hidden_uuids.update(child_uuids)
        hidden_names.update(child_names)
    return hidden_uuids, hidden_names


def _sanitize_multi_entity_log_summary(
    log: CombatLogEntry,
    filtered_children: List[CombatLogEntry],
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Rebuild multi-target summary data from visible child logs only."""
    if log.entry_type != CombatLogEntryType.MULTI_ENTITY_ACTION:
        return data

    sanitized = dict(data)
    for key in (
        "target_names",
        "per_target_damage",
        "per_target_logs",
        "total_damage",
        "saves_succeeded",
        "saves_failed",
    ):
        sanitized.pop(key, None)

    target_names = _visible_target_names(filtered_children)
    per_target_logs: List[Optional[Dict[str, Any]]] = []
    per_target_damage: List[int] = []
    saves_succeeded = 0
    saves_failed = 0
    for child in filtered_children:
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

    sanitized["total_targets"] = len(filtered_children)
    if target_names:
        sanitized["target_names"] = target_names
    if per_target_damage:
        sanitized["per_target_damage"] = per_target_damage
        sanitized["total_damage"] = sum(per_target_damage)
    if per_target_logs:
        sanitized["per_target_logs"] = per_target_logs
    sanitized["saves_succeeded"] = saves_succeeded
    sanitized["saves_failed"] = saves_failed
    return sanitized


def _visible_target_names(logs: List[CombatLogEntry]) -> List[str]:
    """Return visible target names from direct filtered action children."""
    names: List[str] = []
    seen: Set[str] = set()
    for log in logs:
        name = log.target_name
        if not name or name == "Unknown" or name in seen:
            continue
        names.append(name)
        seen.add(name)
    return names


def _damage_from_log_data(data: Dict[str, Any]) -> Optional[int]:
    """Extract a damage total from visible structured log data."""
    for key in ("final_damage", "total_damage", "damage"):
        value = data.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    return None


def _top_level_combat_log(event: Event) -> Optional[CombatLogEntry]:
    """Return the event combat log only at the engine log boundary."""
    if getattr(event, "parent_event", None) is not None:
        return None
    return event.combat_log


def _visible_combat_logs(
    session: PlayerSession,
    observers: List[Entity],
    encounter: Optional[Encounter],
) -> List[Dict[str, Any]]:
    """Filter existing logs once when a subjective session first bootstraps."""
    if encounter is None:
        return []
    context = _build_combat_log_filter_context(session, observers)
    logs: List[Dict[str, Any]] = []
    for log in encounter.combat_log:
        filtered = _filtered_combat_log(log, session, observers, context)
        if filtered is not None:
            logs.append(filtered.model_dump(mode="json"))
    return logs


def _entity_uuids_referenced_by(event: Event) -> Set[UUID]:
    """Collect entity UUIDs directly referenced by an event."""
    values: Set[UUID] = set()
    for attr in ("source_entity_uuid", "target_entity_uuid", "entity_uuid", "killer_uuid"):
        value = getattr(event, attr, None)
        if isinstance(value, UUID):
            values.add(value)
    return values


def _event_entity_position(
    entity_uuid: UUID,
    event: Event,
) -> Optional[Tuple[int, int]]:
    """Return the event-time position for a movement-like event entity."""
    if event.event_type == EventType.MOVEMENT and getattr(event, "source_entity_uuid", None) == entity_uuid:
        end_position = getattr(event, "end_position", None)
        return end_position if isinstance(end_position, tuple) else None
    if (
        event.event_type == EventType.FORCED_MOVEMENT
        and getattr(event, "target_entity_uuid", None) == entity_uuid
    ):
        end_position = getattr(event, "end_position", None)
        return end_position if isinstance(end_position, tuple) else None
    entity = Entity.get(entity_uuid)
    return entity.position if entity is not None else None


def _block_uuids_referenced_by(event: Event) -> Set[UUID]:
    """Collect block UUIDs that may own visible tile or object state."""
    values: Set[UUID] = set()
    for attr in (
        "source_entity_uuid",
        "target_entity_uuid",
        "item_uuid",
        "object_uuid",
    ):
        value = getattr(event, attr, None)
        if isinstance(value, UUID):
            values.add(value)
    return values


def _spatial_block_location(
    block_uuid: UUID,
) -> Optional[Tuple[Tuple[int, int], str]]:
    """Return an event-referenced block's authoritative map location.

    ``BaseBlock.position`` defaults to ``(0, 0)`` and is propagated through
    non-spatial child blocks. It therefore cannot establish that an inventory
    item, equipment item, condition, or component is present on the map. The
    grid indexes are the authority for spatial disclosure.

    Args:
        block_uuid: Referenced block UUID.

    Returns:
        A ``(position, kind)`` pair for registered tiles or floor objects, or
        ``None`` when the block has no independent map location.
    """
    block = BaseBlock.get(block_uuid)
    if block is None or isinstance(block, Entity):
        return None
    grid = get_map()
    object_position = grid.get_object_position(block_uuid)
    if object_position is not None:
        return object_position, "object"
    block_position = block.position
    if grid.get_tile(*block_position) is block:
        return block_position, "tile"
    return None


def _entity_visible_to_session(entity_uuid: UUID, observers: List[Entity]) -> bool:
    """Return whether any controlled observer currently sees an entity."""
    return any(entity_uuid in observer.senses.entities for observer in observers)


def _position_visible_to_session(position: Tuple[int, int], observers: List[Entity]) -> bool:
    """Return whether any controlled observer currently sees a position."""
    return any(observer.senses.visible.get(position, False) for observer in observers)


def _observers_that_see(entity_uuid: UUID, observers: List[Entity]) -> List[str]:
    """Return controlled observer UUIDs that currently see an entity."""
    return sorted(str(observer.uuid) for observer in observers if entity_uuid in observer.senses.entities or entity_uuid == observer.uuid)


def _observers_that_see_position(position: Tuple[int, int], observers: List[Entity]) -> List[str]:
    """Return controlled observer UUIDs that currently see a position."""
    return sorted(str(observer.uuid) for observer in observers if observer.senses.visible.get(position, False))


def _entity_patch(fact: ObservationEntityFact, reason: str) -> ObservationPatch:
    """Create an entity patch from a fact."""
    return ObservationPatch(
        patch_type=ObservationPatchType.ENTITY,
        reason=reason,
        entity_uuid=fact.uuid,
        data={"entity": fact.model_dump(mode="json")},
    )


def _entity_hit_point_patch_if_known(
    entity_uuid: UUID,
    session: PlayerSession,
    observers: List[Entity],
    event: Event,
) -> Optional[ObservationPatch]:
    """Create a partial HP/death patch for a known entity."""
    entity = Entity.get(entity_uuid)
    if entity is None:
        return None
    if event.target_entity_uuid is not None and entity_uuid != event.target_entity_uuid:
        return None
    if entity_uuid not in session.controlled_entities and not _entity_visible_to_session(entity_uuid, observers):
        return None
    hp, normal_hp, temporary_hp, _max_hp_value, is_dead, healing_blocked = _entity_health_details(entity)
    if isinstance(event, DamageAppliedEvent):
        normal_hp = event.resulting_normal_hp
        temporary_hp = event.resulting_temporary_hp
        hp = normal_hp + temporary_hp
        is_dead = normal_hp <= 0
    elif (
        isinstance(event, HealEvent)
        and event.resulting_normal_hp is not None
        and event.resulting_temporary_hp is not None
    ):
        normal_hp = event.resulting_normal_hp
        temporary_hp = event.resulting_temporary_hp
        hp = normal_hp + temporary_hp
        is_dead = normal_hp <= 0
    return ObservationPatch(
        patch_type=ObservationPatchType.ENTITY,
        reason=event.event_type.value,
        entity_uuid=str(entity_uuid),
        data={
            "entity_update": {
                "uuid": str(entity_uuid),
                "hp": hp,
                "normal_hp": normal_hp,
                "temporary_hp": temporary_hp,
                "healing_blocked": healing_blocked,
                "is_dead": is_dead,
            }
        },
    )


def _entity_position_patch_if_known(
    entity_uuid: UUID,
    session: PlayerSession,
    observers: List[Entity],
    position: Tuple[int, int],
    reason: str,
) -> Optional[ObservationPatch]:
    """Create a partial position patch for a currently known moving entity."""
    if entity_uuid not in session.controlled_entities and not _entity_visible_to_session(entity_uuid, observers):
        return None
    return ObservationPatch(
        patch_type=ObservationPatchType.ENTITY,
        reason=reason,
        entity_uuid=str(entity_uuid),
        data={
            "entity_update": {
                "uuid": str(entity_uuid),
                "knowledge_state": KnowledgeState.VISIBLE.value,
                "position": list(position),
            }
        },
    )


def _entity_health_details(entity: Entity) -> Tuple[int, int, int, int, bool, bool]:
    """Return visible total, restorable, temporary, maximum, death, and healing facts."""
    con_modifier = entity.ability_scores.get_ability("constitution").get_combined_values().normalized_score
    max_hp = (
        entity.health.get_max_hit_dices_points(con_modifier)
        + entity.health.max_hit_points_bonus.normalized_score
    )
    normal_hp = max_hp - entity.health.damage_taken
    temporary_hp = entity.health.temporary_hit_points.normalized_score
    total_hp = normal_hp + temporary_hp
    return (
        total_hp,
        normal_hp,
        temporary_hp,
        max_hp,
        normal_hp <= 0,
        entity.health.is_healing_blocked(),
    )


def _object_patch(fact: ObservationObjectFact, reason: str) -> ObservationPatch:
    """Create an object patch from a fact."""
    return ObservationPatch(
        patch_type=ObservationPatchType.OBJECT,
        reason=reason,
        object_uuid=fact.uuid,
        data={"object": fact.model_dump(mode="json")},
    )


def _tile_patch(fact: ObservationTileFact, reason: str) -> ObservationPatch:
    """Create a tile patch from a fact."""
    return ObservationPatch(
        patch_type=ObservationPatchType.TILE,
        reason=reason,
        tile_key=fact.key,
        data={"tile": fact.model_dump(mode="json")},
    )


def _tiles_patch(facts: Iterable[ObservationTileFact], reason: str) -> ObservationPatch:
    """Create a tile patch carrying one or more tile facts."""
    facts = list(facts)
    if len(facts) == 1:
        return _tile_patch(facts[0], reason)
    return ObservationPatch(
        patch_type=ObservationPatchType.TILE,
        reason=reason,
        data={"tiles": [fact.model_dump(mode="json") for fact in facts]},
    )


def _session_patch(state: ObservationSessionState, reason: str) -> ObservationPatch:
    """Create a session patch."""
    return ObservationPatch(
        patch_type=ObservationPatchType.SESSION,
        reason=reason,
        data={"session": state.model_dump(mode="json")},
    )


def _encounter_patch(state: ObservationEncounterState, reason: str) -> ObservationPatch:
    """Create an encounter patch."""
    return ObservationPatch(
        patch_type=ObservationPatchType.ENCOUNTER,
        reason=reason,
        data={"encounter": state.model_dump(mode="json")},
    )


def _combat_log_patch(
    log: CombatLogEntry,
    combat_log_json: Optional[Dict[str, Any]] = None,
) -> ObservationPatch:
    """Create a visible combat-log patch."""
    return ObservationPatch(
        patch_type=ObservationPatchType.COMBAT_LOG,
        reason="combat_log",
        data={"combat_log": combat_log_json if combat_log_json is not None else log.model_dump(mode="json")},
    )


def _combat_log_cursor(
    log: Optional[CombatLogEntry],
    encounter: Optional[Encounter],
) -> Optional[int]:
    """Return the combat-log cursor for a visible log when known."""
    if log is None or encounter is None:
        return None
    for index in range(len(encounter.combat_log) - 1, -1, -1):
        entry = encounter.combat_log[index]
        if entry is log or entry == log:
            return index + 1
    return len(encounter.combat_log)


def _object_state(obj: BaseBlock) -> Dict[str, Any]:
    """Return stable public object state fields when present."""
    state: Dict[str, Any] = {}
    for field_name in (
        "is_open",
        "blocked_directions",
        "blocked_channels",
        "blocks_movement",
        "blocks_vision",
        "blocks_vision_field",
        "is_pickable",
        "is_usable",
        "charges",
        "stack_count",
    ):
        if hasattr(obj, field_name):
            value = getattr(obj, field_name)
            if value is not None:
                safe_value = _json_safe_state_value(value)
                if safe_value is not None:
                    state[field_name] = safe_value
    return state


def _json_safe_state_value(value: Any) -> Any:
    """Return a JSON-safe public state value or None when unsupported."""
    if callable(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [
            safe_item for item in value
            if (safe_item := _json_safe_state_value(item)) is not None
        ]
    if isinstance(value, list):
        return [
            safe_item for item in value
            if (safe_item := _json_safe_state_value(item)) is not None
        ]
    if isinstance(value, set):
        return sorted(
            safe_item for item in value
            if (safe_item := _json_safe_state_value(item)) is not None
        )
    if isinstance(value, dict):
        return {
            str(key): safe_value
            for key, item in value.items()
            if (safe_value := _json_safe_state_value(item)) is not None
        }
    return None


def _directional_blocks(tile: Any, channel: str) -> Dict[str, bool]:
    """Return visible directional blockers for a tile and movement channel."""
    return {
        direction: not tile.allows_direction(direction, channel)
        for direction in ("north", "south", "east", "west")
    }


def _uuid_position_json(values: Dict[UUID, Tuple[int, int]]) -> Dict[str, List[int]]:
    """Serialize UUID-position mappings to JSON-safe dictionaries."""
    return {str(uuid): [position[0], position[1]] for uuid, position in values.items()}


def _uuid_move_json(values: Dict[UUID, Tuple[Tuple[int, int], Tuple[int, int]]]) -> Dict[str, List[List[int]]]:
    """Serialize UUID movement mappings to JSON-safe dictionaries."""
    return {
        str(uuid): [[old[0], old[1]], [new[0], new[1]]]
        for uuid, (old, new) in values.items()
    }


def _tile_key(position: Tuple[int, int]) -> str:
    """Return a stable string key for a grid position."""
    return f"{position[0]},{position[1]}"


def _position_sort_key(position: Tuple[int, int]) -> Tuple[int, int]:
    """Sort grid positions by x and y."""
    return position
