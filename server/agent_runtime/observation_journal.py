"""Journal canonical subjective AI facts as cursored transport frames."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from uuid import UUID

from dnd.action_timing import action_timing_enabled, record_action_timing
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.condition_types import ConditionTag
from dnd.core.combat_log import CombatLogEntry
from dnd.core.events import (
    DamageAppliedEvent,
    Event,
    EventPhase,
    EventQueue,
    EventType,
    HealEvent,
    SensoryUpdateEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.ai.runtime.subjective_projection import (
    clear_subjective_projection_fact_cache,
    condition_semantic_key,
    entity_health_details,
    observers_that_see,
    observers_that_see_position,
    project_condition_fact,
    project_entity_fact,
    project_object_fact,
    project_subjective_world,
    project_visible_tile_fact,
    resolve_controlled_observers,
    subjective_tile_key,
)
from server.combat_log_projection import (
    CombatLogProjectionContext,
    make_combat_log_projection_context,
    project_combat_log,
)
from server.session import GameSession, PlayerSession, SessionManager

from dnd.ai.contracts.observation_replay import apply_observation_frame
from dnd.ai.contracts.observation import (
    KnowledgeState,
    ObservationCombatantState,
    ObservationEncounterState,
    ObservationEffectProtection,
    ObservationEntityFact,
    ObservationFrame,
    ObservationFramesResponse,
    ObservationFrameType,
    ObservationObjectFact,
    ObservationPatch,
    ObservationPatchType,
    ObservationSessionState,
    ObservationSourceKind,
    ObservationSnapshot,
    ObservationStateReplacement,
    SubjectiveWorldState,
    ObservationTileFact,
)
from dnd.ai.contracts.control import CommandResult, DecisionEpoch
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
class _ProjectionPassContext:
    """Reusable subjective facts for one incremental projection pass."""

    combat_logs: CombatLogProjectionContext
    entity_facts: Dict[Tuple[UUID, str, Optional[Tuple[int, int]]], Optional[ObservationEntityFact]] = field(default_factory=dict)
    tile_facts: Dict[Tuple[Tuple[int, int], Tuple[str, ...]], ObservationTileFact] = field(default_factory=dict)
    has_any_hazards: Optional[bool] = None


class _ObservationWakeupStream:
    """Per-session live delivery for projected and controller subjective frames."""

    def __init__(self) -> None:
        self._subscriptions: Dict[str, List[BoundedSubscription]] = {}

    def clear_all(self) -> None:
        """Evict all subscribers and clear subscriptions."""
        for session_id in tuple(self._subscriptions):
            self.evict_session(session_id, reason="observation_reset")

    def evict_session(self, session_id: str, *, reason: str) -> None:
        """Wake and detach every subscriber for one session."""
        subscriptions = self._subscriptions.pop(session_id, [])
        for sub in subscriptions:
            sub.try_enqueue({
                "event": "evicted",
                "data": {"reason": reason},
                "id": None,
            })

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
    _projection_cache.clear()
    clear_subjective_projection_fact_cache()
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
        filtered_log = _filtered_combat_log(combat_log, session)
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
    world = project_subjective_world(
        observation_cursor=len(entry.frames),
        session=_session_state(session, game),
        encounter=(
            _encounter_state(
                encounter,
                session,
                list(resolve_controlled_observers(session.controlled_entities)),
            )
            if encounter is not None
            else None
        ),
        controlled_entity_uuids=session.controlled_entities,
        prior_world=prior_world,
        combat_logs=(
            prior_world.combat_logs
            if prior_world is not None
            else bootstrap_combat_logs or ()
        ),
    )
    return ObservationStateReplacement(
        session=world.session,
        encounter=world.encounter,
        observers=[world.observers[key] for key in sorted(world.observers)],
        known_entities=[
            world.known_entities[key] for key in sorted(world.known_entities)
        ],
        known_objects=[
            world.known_objects[key] for key in sorted(world.known_objects)
        ],
        known_tiles=[world.known_tiles[key] for key in sorted(world.known_tiles)],
        combat_logs=list(world.combat_logs),
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
        observers = list(
            resolve_controlled_observers(session.controlled_entities)
        )
        bootstrap_state = _observation_state_replacement(
            session,
            game,
            encounter,
            entry,
            bootstrap_combat_logs=_visible_combat_logs(session, encounter),
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
    observers = list(resolve_controlled_observers(session.controlled_entities))
    _record_timing(record_timing, "projection.controlled_observers_ms", started)
    projection_context = _ProjectionPassContext(
        combat_logs=_build_combat_log_filter_context(session),
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
    event_combat_log = _filtered_combat_log(
        event.combat_log,
        session,
        projection_context.combat_logs,
    )
    _record_timing(record_timing, f"projection.project_completion_event_detail.{event_type_key}.filter_event_log_ms", started)
    top_level_log = _top_level_combat_log(event)
    started = _timing_start(record_timing)
    combat_log = _filtered_combat_log(
        top_level_log,
        session,
        projection_context.combat_logs,
    )
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
        active_known = _entity_visible_to_session(
            active_uuid,
            list(resolve_controlled_observers(session.controlled_entities)),
        )
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
        observer_uuids = observers_that_see(combatant_uuid, observers)
        visible = bool(observer_uuids) or controlled
        combatant = encounter.combatants.get(combatant_uuid)
        if visible and entity is not None:
            rows.append(ObservationCombatantState(
                uuid=str(combatant_uuid),
                name=entity.name,
                initiative=combatant.initiative_total if combatant else None,
                life_state=entity.health.life_state,
                is_dead=entity.health.life_state is LifeState.DEAD,
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


def _entity_fact(
    entity_uuid: UUID,
    session: PlayerSession,
    observers: List[Entity],
    fallback_state: KnowledgeState = KnowledgeState.VISIBLE,
    remembered_position: Optional[Tuple[int, int]] = None,
    fact_cache: Optional[Dict[Tuple[UUID, str, Optional[Tuple[int, int]]], Optional[ObservationEntityFact]]] = None,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> Optional[ObservationEntityFact]:
    """Cache canonical entity projection within one transport pass."""
    cache_key = (entity_uuid, fallback_state.value, remembered_position)
    if fact_cache is not None and cache_key in fact_cache:
        return fact_cache[cache_key]

    started = _timing_start(record_timing)
    try:
        fact = project_entity_fact(
            entity_uuid,
            controlled_entity_uuids=session.controlled_entities,
            observers=observers,
            fallback_state=fallback_state,
            remembered_position=remembered_position,
        )
    except ValueError:
        fact = None
    _record_timing(record_timing, "projection.entity_fact.canonical_ms", started)
    if fact_cache is not None:
        fact_cache[cache_key] = fact
    return fact


def _visible_tile_fact_cached(
    position: Tuple[int, int],
    observer_uuids: Iterable[str],
    projection_context: Optional[_ProjectionPassContext] = None,
) -> ObservationTileFact:
    """Create a visible tile fact, reusing pass-local projection cache."""
    observer_ids = tuple(sorted(observer_uuids))
    if projection_context is None:
        return project_visible_tile_fact(position, observer_ids)
    cache_key = (position, observer_ids)
    fact = projection_context.tile_facts.get(cache_key)
    if fact is None:
        if projection_context.has_any_hazards is None:
            projection_context.has_any_hazards = get_map().has_any_hazards()
        fact = project_visible_tile_fact(
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
            entity = Entity.get(entity_uuid)
            life_state = entity.health.life_state if entity is not None else None
            if life_state is LifeState.DEAD:
                fact = fact.model_copy(update={
                    "life_state": life_state,
                    "is_dead": True,
                })
            patches.append(_entity_patch(fact, event.update_reason.value))
    _record_timing(record_timing, "projection.sensory_patches.entity_removed_ms", started)

    started = _timing_start(record_timing)
    for object_uuid, position in event.visible_objects_added.items():
        fact = project_object_fact(object_uuid, position, [str(event.observer_uuid)])
        if fact is not None:
            patches.append(_object_patch(fact, event.update_reason.value))
    _record_timing(record_timing, "projection.sensory_patches.object_added_ms", started)
    started = _timing_start(record_timing)
    for object_uuid, position in event.visible_objects_removed.items():
        fact = project_object_fact(object_uuid, position, [str(event.observer_uuid)])
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
            key=subjective_tile_key(position),
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
        observer_uuids = observers_that_see_position(block_position, observers)
        if location_kind == "tile":
            patches.append(_tile_patch(
                _visible_tile_fact_cached(block_position, observer_uuids, projection_context),
                event.event_type.value,
            ))
            continue
        fact = project_object_fact(block_uuid, block_position, observer_uuids)
        if fact is not None:
            patches.append(_object_patch(fact, event.event_type.value))

    position = getattr(event, "position", None)
    if isinstance(position, tuple) and _position_visible_to_session(position, observers):
        started = _timing_start(record_timing)
        patches.append(_tile_patch(
            _visible_tile_fact_cached(
                position,
                observers_that_see_position(position, observers),
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
        fact = project_object_fact(object_uuid, position, observers_that_see_position(position, observers))
        if fact is not None:
            patches.append(_object_patch(fact, event.event_type.value))
        _record_timing(
            record_timing,
            f"projection.project_completion_event_detail.{event_type_key}.state_patches.object_patch_ms",
            started,
        )

    if event.event_type is EventType.SPATIAL_EFFECT_CHANGED:
        tile_facts = [
            _visible_tile_fact_cached(
                affected_position,
                observers_that_see_position(affected_position, observers),
                projection_context,
            )
            for affected_position in sorted(event.get_affected_positions())
            if _position_visible_to_session(affected_position, observers)
        ]
        if tile_facts:
            patches.append(_tiles_patch(tile_facts, event.event_type.value))

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
    semantic_key = condition_semantic_key(event.condition)
    condition_fact = project_condition_fact(
        event.condition,
        applied_source_event_cursor=source_event_cursor,
    )
    condition_protections = [
        ObservationEffectProtection(
            protection_id=protection.protection_id,
            blocked_effect_ids=sorted(protection.blocked_effect_ids),
            source_condition_semantic_key=semantic_key,
        )
        for protection in event.condition.outcome_protections
    ]
    has_name = condition_name is not None and condition_name in fact.conditions
    has_semantic_key = (
        fact.condition_semantic_keys is not None
        and semantic_key in fact.condition_semantic_keys
    )
    has_condition_fact = (
        fact.condition_facts is not None
        and any(
            row.semantic_key == semantic_key
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
                    else sorted([*fact.condition_semantic_keys, semantic_key])
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
        EventType.LIFE_STATE_CHANGE,
        EventType.REVIVE,
    }


def _event_should_patch_entity_hit_points(event_type: EventType) -> bool:
    """Return whether an event needs only HP/lifecycle entity fact updates."""
    return event_type in {
        EventType.DAMAGE_APPLIED,
        EventType.HEAL,
        EventType.LIFE_STATE_CHANGE,
        EventType.REVIVE,
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
    elif _filtered_combat_log(event.combat_log, session) is not None:
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
    context: Optional[CombatLogProjectionContext] = None,
) -> Optional[CombatLogEntry]:
    """Return a combat log filtered to this session, or None when hidden."""
    if log is None:
        return None
    filter_context = context or _build_combat_log_filter_context(session)
    return project_combat_log(log, filter_context)


def _build_combat_log_filter_context(
    session: PlayerSession,
) -> CombatLogProjectionContext:
    """Build projection authority without consulting mutable current senses."""
    return make_combat_log_projection_context(
        controlled_entity_uuids={str(uuid) for uuid in session.controlled_entities},
    )


def _top_level_combat_log(event: Event) -> Optional[CombatLogEntry]:
    """Return the event combat log only at the engine log boundary."""
    if getattr(event, "parent_event", None) is not None:
        return None
    return event.combat_log


def _visible_combat_logs(
    session: PlayerSession,
    encounter: Optional[Encounter],
) -> List[Dict[str, Any]]:
    """Filter existing logs once when a subjective session first bootstraps."""
    if encounter is None:
        return []
    context = _build_combat_log_filter_context(session)
    logs: List[Dict[str, Any]] = []
    for log in encounter.combat_log:
        filtered = _filtered_combat_log(log, session, context)
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
    """Create a partial HP/lifecycle patch for a known entity."""
    entity = Entity.get(entity_uuid)
    if entity is None:
        return None
    if event.target_entity_uuid is not None and entity_uuid != event.target_entity_uuid:
        return None
    if entity_uuid not in session.controlled_entities and not _entity_visible_to_session(entity_uuid, observers):
        return None
    hp, normal_hp, temporary_hp, _max_hp_value, life_state, is_dead, healing_blocked = entity_health_details(entity)
    if isinstance(event, DamageAppliedEvent):
        normal_hp = event.resulting_normal_hp
        temporary_hp = event.resulting_temporary_hp
        hp = normal_hp + temporary_hp
    elif (
        isinstance(event, HealEvent)
        and event.resulting_normal_hp is not None
        and event.resulting_temporary_hp is not None
    ):
        normal_hp = event.resulting_normal_hp
        temporary_hp = event.resulting_temporary_hp
        hp = normal_hp + temporary_hp
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
                "life_state": life_state.value,
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


def _uuid_position_json(values: Dict[UUID, Tuple[int, int]]) -> Dict[str, List[int]]:
    """Serialize UUID-position mappings to JSON-safe dictionaries."""
    return {str(uuid): [position[0], position[1]] for uuid, position in values.items()}


def _uuid_move_json(values: Dict[UUID, Tuple[Tuple[int, int], Tuple[int, int]]]) -> Dict[str, List[List[int]]]:
    """Serialize UUID movement mappings to JSON-safe dictionaries."""
    return {
        str(uuid): [[old[0], old[1]], [new[0], new[1]]]
        for uuid, (old, new) in values.items()
    }


def _position_sort_key(position: Tuple[int, int]) -> Tuple[int, int]:
    """Sort grid positions by x and y."""
    return position
