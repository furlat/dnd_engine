"""
Canonical HTTP/SSE server for game control, replication, and diagnostics.

This server:
1. Hooks into EventQueue to capture all events
2. Projects private player replication journals
3. Exposes authorized objective diagnostics separately
4. Activates and advances games through one controller coordinator

Usage:
    # Start the canonical game server
    uv run python -m server.event_server

    # Or import the same app programmatically
    from server.event_server import run_server
    run_server(host="0.0.0.0", port=8000)
"""

import argparse
import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
import traceback
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Sequence
from uuid import UUID
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logger = logging.getLogger("dnd_server")

from dnd.core.equipment_types import BodyPart, RingSlot, WeaponSlot
from dnd.core.events import (
    EncounterEndEvent,
    Event,
    EventPhase,
    EventQueue,
)
from dnd.core.gridmap import get_map
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.runtime_reset import reset_engine_runtime
from dnd.entities.entity import Entity
from dnd.encounters.encounter import Encounter, EncounterState, TurnState
from dnd.scenarios.encounter_assembler import (
    AssembledEncounter,
    IncompatibleEncounterError,
    prepare_encounter_recipe,
)
from dnd.encounters.controllers import HumanController, PassController
from dnd.action_dispatch import dispatch_available_action
from dnd.actions_functional import get_available_actions
from server.runtime_performance import latency_sensitive_gc
from dnd.core.base_actions import (
    AvailableActionsResult,
    AvailableHandlerInfo,
    TargetType,
)
from server.api_models import (
    APIAvailableActions, APIServerTiming, ActionExecutionAuthorization,
    SimpleActionRequest, ActionResult, AoEPreviewResult,
    CreateSessionRequest, CreateSessionResponse, SessionPingResponse,
    JoinGameRequest, JoinGameResponse,
    GameCreationCatalogResponse,
    GameCreationComposeRequest, GameCreationComposeResponse,
    GameCreationPreviewRequest,
    GameCreationEntityAssignment, GameCreationRosterResult,
    GameCreationActivateRequest, GameCreationActivateResponse,
    GameCreationStartRequest, GameCreationStartResponse,
    EventContractSummary,
    PositionPreviewRequest, ExecuteByIndexRequest,
    ToggleHandlerRequest,
    APIEquippableItems, APIEntityHandlersResponse,
    EquipRequest, UnequipRequest, EquipmentMutationResult, ToggleHandlerResponse,
    AdvanceEncounterResult,
    SpellCatalogResponse,
    MapEditorCatalog, MapEditorCreateMapRequest, MapEditorLightResponse, MapEditorMapSnapshot,
    MapEditorConnectorDeleteRequest, MapEditorConnectorEnabledRequest, MapEditorConnectorMutationResponse, MapEditorConnectorUpsertRequest,
    MapEditorObjectDeleteRequest, MapEditorObjectPlaceRequest, MapEditorTilePatchRequest, MapEditorVisibilityResponse,
    MapEditorWalkabilityResponse, MapEditorSaveMapRequest, MapEditorSavedMapDocument,
    MapEditorSavedMapList, MapEditorSavedMapMetadata,
    ServerCapabilitiesResponse,
    StandaloneGameSessionSummary, StandaloneGameStatusResponse,
)
from server.content_catalog import (
    ContentCatalogResponse,
    ContentManifestResponse,
)
from server.content_http import serve_content_catalog, serve_content_manifest
from server.world_contracts import APIFloorObject
from server.mapeditor_support import (
    apply_tile_patches,
    build_catalog,
    create_editor_map,
    delete_editor_connector,
    delete_catalog_object,
    delete_saved_editor_map,
    get_editor_snapshot,
    get_objective_light,
    get_saved_editor_map,
    get_visibility_blockers,
    get_walkability,
    list_saved_editor_maps,
    load_saved_editor_map,
    place_catalog_object,
    save_current_editor_map,
    set_editor_connector_enabled,
    upsert_editor_connector,
)
from server.request_timing import RequestTimingMiddleware
from dnd.content_system.builtin_character_builds import (
    DEFAULT_CHARACTER_RULESET_DIGEST,
)
from server.spell_catalog import build_spell_catalog
from server.game_creation_catalog import build_game_creation_catalog
from server.game_creation_composition import (
    GameCreationCompositionError,
    normalize_encounter_recipe,
)
from server.game_creation_preview import (
    GameCreationPreviewError,
    build_game_creation_encounter_visual_preview,
    close_game_creation_preview_worker,
    prewarm_game_creation_preview_worker,
)
from server.game_creation_preview_contracts import (
    GameCreationEncounterVisualPreviewResponse,
)
from server.event_stream import (
    ObjectiveSourceSnapshot,
    event_stream,
    format_sse,
    make_stream_id,
)
from server.event_contract import (
    event_contract_summary,
)
from server.game_archive import (
    GameArchive,
    GameArchiveStore,
    build_game_archive,
)
from server.game_summary_store import GameSummaryEvidence, game_summary_store
from server.objective_replay import ObjectiveReplayBundle
from server.player_replay_capture import subjective_replay_capture_store
from server.game_replay import GameReplayError, build_objective_replay
from server.action_serialization import serialize_available_actions
from server.session import (
    SessionManager, GameSession,
    PlayerSession, PlayerType, get_session_manager
)
from server.replication_perspective import perspective_epoch_registry
from server.objective_diagnostics_contracts import (
    ObjectiveDiagnosticsBootstrap,
    ObjectiveDiagnosticsSync,
    SubjectiveRenderParityDiagnosticsResponse,
)
from server.combat_log_source import (
    CombatLogSourceError,
    CombatLogSourceSlot,
    CombatLogSourceWindow,
)
from server.objective_state import build_current_objective_world
from server.subjective_parity_diagnostics import (
    SubjectiveParityDiagnosticsError,
    build_subjective_render_parity_diagnostics,
)
from server.objective_timeline import (
    ObjectiveTimelineError,
    build_objective_combat_log_frames,
    build_objective_game_event_frames,
)
from server.timeline_contracts import (
    GameEventFrame,
    GameEventFramesResponse,
    ObjectiveCombatLogFramesResponse,
)
from server.subjective_authority import (
    ResolvedSubjectiveAuthority,
    SubjectiveAuthorityError,
    resolve_subjective_authority,
)
from server.player_replication.journal import (
    SubjectiveJournalError,
    SubjectiveJournalResyncRequired,
    SubjectiveSubscriptionClosedError,
)
from server.player_replication.runtime import (
    CanonicalSubjectiveReplicationContext,
    SubjectiveBootstrapDeferredError,
    SubjectiveRuntimeError,
    SubjectiveRuntimeIdentityError,
    canonical_subjective_replication_runtime,
)
from server.player_replication_contract import (
    PlayerReplicationWatermarks,
    SubjectiveCombatLogFramesResponse,
    SubjectiveCombatLogDelivery,
    SubjectiveFrameDelivery,
    SubjectiveFramesResponse,
    SubjectiveReplicationBootstrap,
    SubjectiveSyncDelivery,
)
_available_actions_cache: Dict[str, AvailableActionsResult] = {}


@dataclass
class _ServerCommandTiming:
    """Low-overhead phase timing for one server-side command."""

    command_type: str
    diagnostics_enabled: bool = False
    started_at: float = field(default_factory=time.perf_counter)
    phases: Dict[str, float] = field(default_factory=dict)
    phase_counts: Dict[str, int] = field(default_factory=dict)
    phase_max_ms: Dict[str, float] = field(default_factory=dict)

    def add(self, phase: str, started_at: float) -> None:
        """Add elapsed time to one named phase."""
        self.add_elapsed(phase, (time.perf_counter() - started_at) * 1000)

    def add_elapsed(self, phase: str, elapsed_ms: float) -> None:
        """Add a measured duration and retain its multiplicity and maximum."""
        self.phases[phase] = self.phases.get(phase, 0.0) + elapsed_ms
        self.phase_counts[phase] = self.phase_counts.get(phase, 0) + 1
        self.phase_max_ms[phase] = max(self.phase_max_ms.get(phase, 0.0), elapsed_ms)

    def payload(self) -> dict[str, Any]:
        """Return a JSON-friendly timing payload."""
        return {
            "command_type": self.command_type,
            "diagnostics_enabled": self.diagnostics_enabled,
            "total_ms": round((time.perf_counter() - self.started_at) * 1000, 3),
            "phases": {
                phase: round(elapsed_ms, 3)
                for phase, elapsed_ms in self.phases.items()
            },
            "phase_counts": dict(self.phase_counts),
            "phase_max_ms": {
                phase: round(elapsed_ms, 3)
                for phase, elapsed_ms in self.phase_max_ms.items()
            },
        }


@dataclass(frozen=True)
class _ActionExecutionResult:
    """Private engine result plus the minimal public command acknowledgement."""

    response: ActionResult
    movement_termination_reason: Optional[str] = None
    movement_revalidation_reason: Optional[str] = None




def clear_subjective_projection_state() -> None:
    """Clear all process-local subjective projection and replay identity state."""
    perspective_epoch_registry.clear_all()
    canonical_subjective_replication_runtime.clear_all()
    subjective_replay_capture_store.clear()


@dataclass(frozen=True)
class _GameActivationIdentity:
    """Exact replication identity that released one prepared game."""

    game_id: UUID
    session_id: UUID
    source_stream_id: str
    generation_id: str
    perspective_epoch_id: str




class StandaloneGameState:
    """Hold mutable standalone game runtime state.

    Attributes:
        encounter: Active encounter, if one has been created.
        combat_task: Background task advancing autonomous turns, if running.
        paused: Whether automatic game advancement is inactive.
        _session_manager: Session registry backing game/player sessions.
        _game_session: Active game session for the current encounter.
    """

    def __init__(self) -> None:
        self.encounter: Optional[Encounter] = None
        self.combat_task: Optional[asyncio.Task] = None
        self.paused: bool = True
        self._session_manager = get_session_manager()
        self._game_session: Optional[GameSession] = None
        self.current_creation: Optional[GameCreationStartResponse] = None
        self.activation_identity: Optional[_GameActivationIdentity] = None

    @property
    def game(self) -> Optional[GameSession]:
        """Get the active game session."""
        return self._game_session

    @property
    def waiting_for_human(self) -> bool:
        """Check if waiting for a human player (derived from session state)."""
        if not self._game_session or not self.encounter:
            return False
        active_player = self._game_session.active_player
        if not active_player:
            return False
        return active_player.player_type is PlayerType.HUMAN

    @property
    def human_entity_uuid(self) -> Optional[UUID]:
        """Get the active entity UUID if it is a human turn."""
        if not self._game_session:
            return None
        return self._game_session.active_entity_uuid

    def create_game_session(
        self,
        encounter: Encounter,
    ) -> GameSession:
        """Create a new game session for the encounter."""
        self._game_session = self._session_manager.create_game(encounter)
        return self._game_session

    def get_session_manager(self) -> SessionManager:
        """Get the session manager."""
        return self._session_manager

    def reset(self) -> None:
        """Reset mutable server session state for a fresh game scene."""
        if self.combat_task is not None and not self.combat_task.done():
            self.combat_task.cancel()
        clear_subjective_projection_state()
        self.encounter = None
        self._game_session = None
        self.current_creation = None
        self.activation_identity = None
        self.combat_task = None
        self.paused = True
        self._session_manager.sessions.clear()
        self._session_manager.games.clear()
        self._session_manager.active_game = None
        _available_actions_cache.clear()
        event_stream.ensure_attached()

sim = StandaloneGameState()




@dataclass(frozen=True)
class _SubjectiveSessionAuthorityFingerprint:
    """Session-owned facts that define one canonical player perspective."""

    player_type: PlayerType
    controlled_entity_uuids: tuple[str, ...]
    observer_entity_uuids: tuple[str, ...]
    active_observer_uuid: Optional[str]


def _capture_subjective_session_authority(
    manager: SessionManager,
) -> dict[str, _SubjectiveSessionAuthorityFingerprint]:
    """Freeze session perspective facts before an ownership mutation."""
    return {
        str(session.session_id): _SubjectiveSessionAuthorityFingerprint(
            player_type=session.player_type,
            controlled_entity_uuids=tuple(
                sorted(str(entity_uuid) for entity_uuid in session.controlled_entities)
            ),
            observer_entity_uuids=tuple(
                sorted(str(entity_uuid) for entity_uuid in session.observer_entities)
            ),
            active_observer_uuid=(
                str(session.active_observer_uuid)
                if session.active_observer_uuid is not None
                else None
            ),
        )
        for session in manager.sessions.values()
    }


def _retire_changed_subjective_sessions(
    manager: SessionManager,
    before: dict[str, _SubjectiveSessionAuthorityFingerprint],
) -> None:
    """Close old journals immediately after a session authority mutation."""
    after = _capture_subjective_session_authority(manager)
    for session_id in set(before) | set(after):
        if before.get(session_id) != after.get(session_id):
            canonical_subjective_replication_runtime.retire_session(session_id)

game_archive_store = GameArchiveStore(
    os.environ.get("DND_GAME_ARCHIVE_ROOT", ".runtime/game-archives"),
)


def _ensure_game_terminal_callback() -> None:
    """Attach the terminal archive trigger after source observers."""

    EventQueue.remove_on_event_batch_callback(_on_terminal_event_batch)
    EventQueue.add_on_event_batch_callback(_on_terminal_event_batch)


def _on_terminal_event_batch(events: Sequence[Event]) -> None:
    """Write the terminal summary and full objective event archive."""

    encounter_end = next(
        (
            event
            for event in events
            if isinstance(event, EncounterEndEvent)
            and event.phase is EventPhase.COMPLETION
        ),
        None,
    )
    if encounter_end is None:
        return
    try:
        _archive_terminal_game(encounter_end.encounter_uuid)
    except BaseException:
        logger.exception(
            "Terminal game archive failed for encounter %s",
            encounter_end.encounter_uuid,
        )


def _archive_terminal_game(encounter_uuid: UUID) -> bool:
    """Freeze one terminal game to its database-free filesystem archive."""

    encounter = Encounter.get(encounter_uuid)
    if encounter is None:
        return False
    evidence = game_summary_store.get_evidence(encounter_uuid)
    capture = game_summary_store.get_replay_capture(encounter_uuid)
    if evidence is None or capture is None:
        return False
    archive = build_game_archive(
        evidence,
        capture,
        encounter=encounter,
        stream=event_stream,
    )
    store = getattr(app.state, "game_archive_store", game_archive_store)
    store.write(archive)
    return True


async def prepare_new_game_start() -> None:
    """Stop active gameplay and clear session-side projection state."""
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()
        try:
            await sim.combat_task
        except asyncio.CancelledError:
            pass

    clear_subjective_projection_state()
    sim._game_session = None
    sim._session_manager.sessions.clear()
    sim._session_manager.games.clear()
    sim._session_manager.active_game = None
    sim.encounter = None
    sim.combat_task = None
    sim.current_creation = None
    sim.activation_identity = None
    _available_actions_cache.clear()
    sim.paused = True

async def _abort_failed_game_start() -> None:
    """Tear down every engine and server fact from a failed start transaction."""
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()
        try:
            await sim.combat_task
        except asyncio.CancelledError:
            pass

    clear_subjective_projection_state()
    manager = sim.get_session_manager()
    manager.sessions.clear()
    manager.games.clear()
    manager.active_game = None
    sim.encounter = None
    sim._game_session = None
    sim.current_creation = None
    sim.activation_identity = None
    sim.combat_task = None
    sim.paused = True
    _available_actions_cache.clear()
    reset_engine_runtime()
    game_summary_store.reset()
    event_stream.ensure_attached()
    _ensure_game_terminal_callback()




async def advance_encounter(
    timing: Optional[_ServerCommandTiming] = None,
) -> AdvanceEncounterResult:
    """Advance the encounter until an external-control boundary or terminal state.

    Args:
        timing: Optional phase recorder for command diagnostics.
    Returns:
        Control acknowledgement with the resulting turn boundary and canonical
        replication cursor barriers.
    """
    if sim.encounter is None:
        return AdvanceEncounterResult(status="no_encounter")

    if sim.encounter.state == EncounterState.NOT_STARTED:
        if not sim.encounter.initiative_order:
            sim.encounter.roll_initiative()
        sim.encounter.start_encounter()

    if sim.encounter.state == EncounterState.ENDED:
        return AdvanceEncounterResult(
            status="encounter_ended",
            **action_cursor_fields(),
        )

    started = time.perf_counter()
    result = sim.encounter.advance_until_external_boundary()
    if timing is not None:
        timing.add("advance.external_boundary_ms", started)

    return AdvanceEncounterResult(
        status=result.status,
        entity_uuid=str(result.entity_uuid) if result.entity_uuid else None,
        entity_name=result.entity_name,
        round=result.round_number,
        turn_index=result.turn_index,
        **action_cursor_fields(),
    )


def _schedule_activated_game_coordinator() -> bool:
    """Schedule the sole autonomous continuation path when activation is live."""
    encounter = sim.encounter
    if (
        encounter is None
        or sim.activation_identity is None
        or encounter.state is not EncounterState.ACTIVE
        or sim.paused
    ):
        return False
    existing = sim.combat_task
    if existing is not None and not existing.done():
        return True
    sim.combat_task = asyncio.create_task(
        _run_activated_game(),
        name=f"game-coordinator-{sim.activation_identity.game_id}",
    )
    return True


def _scheduled_advance_result() -> AdvanceEncounterResult:
    """Capture the command barrier before the coordinator receives control."""
    encounter = sim.encounter
    current = encounter.get_current_entity() if encounter is not None else None
    return AdvanceEncounterResult(
        status="advancement_scheduled",
        entity_uuid=str(current.uuid) if current is not None else None,
        entity_name=current.name if current is not None else None,
        round=encounter.round_number if encounter is not None else 0,
        turn_index=encounter.current_turn_index if encounter is not None else 0,
        **action_cursor_fields(),
    )


async def _run_activated_game() -> None:
    """Advance native controllers cooperatively until an external boundary.

    Activation starts the encounter synchronously so the opening lifecycle
    barrier is committed exactly once. Autonomous turns then run one bounded
    controller at a time and yield between them, allowing replication and
    diagnostics subscribers to consume every published batch.
    """
    encounter = sim.encounter
    activation = sim.activation_identity
    if encounter is None or activation is None:
        return

    try:
        while (
            sim.encounter is encounter
            and sim.activation_identity == activation
            and encounter.state == EncounterState.ACTIVE
            and not sim.paused
        ):
            if encounter.get_current_controller() is None:
                logger.error(
                    "Activated encounter %s has no controller for its current actor",
                    encounter.uuid,
                )
                sim.paused = True
                return
            if (
                sim.encounter is not encounter
                or sim.activation_identity != activation
                or sim.paused
            ):
                return
            result = encounter.advance_one_controller_action_boundary()
            if result.status in {
                "autonomous_action_completed",
                "advanced_autonomous",
            }:
                # A zero-delay sleep immediately requeues this always-ready
                # task. Long autonomous sequences can make an HTTP request
                # wait behind several projection-heavy action boundaries.
                # One millisecond is a scheduler fairness checkpoint, not a
                # gameplay/turn delay: it gives already-ready HTTP and SSE
                # tasks a complete event-loop cycle while adding at most one
                # millisecond per autonomous decision.
                await asyncio.sleep(0.001)
                continue
            return
    except asyncio.CancelledError:
        raise
    except BaseException:
        sim.paused = True
        logger.exception(
            "Activated encounter coordinator failed for %s",
            encounter.uuid,
        )


def action_cursor_fields() -> dict:
    """Return replication cursors after a state mutation.

    Returns:
        Event and combat-log cursor positions for clients that need deltas.
    """
    return {
        "event_cursor_after": EventQueue.event_cursor(),
        "combat_log_cursor_after": len(sim.encounter.combat_log) if sim.encounter else 0,
    }




def _parse_optional_uuid(value: Optional[str], field_name: str) -> Optional[UUID]:
    """Parse an optional UUID request field."""
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError:
        raise _api_http_exception(
            status_code=400,
            code=f"invalid_{field_name}",
            message=f"Invalid {field_name} UUID format",
            **{field_name: value},
        )




def _api_http_exception(
    status_code: int,
    code: str,
    message: str,
    **context: Any,
) -> HTTPException:
    """Create a structured HTTP exception detail payload.

    Args:
        status_code: HTTP status code for the response.
        code: Machine-readable error code.
        message: Human-readable error message.
        **context: Additional JSON-serializable correction context.

    Returns:
        HTTP exception with a structured detail body.
    """
    detail = {"code": code, "message": message}
    detail.update(context)
    return HTTPException(status_code=status_code, detail=detail)


def _entity_lookup_exception(entity_uuid: str, status_code: int, code: str, message: str) -> HTTPException:
    """Create a structured entity lookup error.

    Args:
        entity_uuid: Entity UUID string that failed validation or lookup.
        status_code: HTTP status code for the response.
        code: Machine-readable error code.
        message: Human-readable error message.

    Returns:
        HTTP exception with only the rejected entity identity.
    """
    return _api_http_exception(
        status_code=status_code,
        code=code,
        message=message,
        entity_uuid=entity_uuid,
    )


def _serialize_entity_handlers(entity: Entity) -> list[AvailableHandlerInfo]:
    """Serialize player-toggleable handlers for one entity.

    Args:
        entity: Entity whose player-toggleable event handlers should be exposed.

    Returns:
        Handler summaries with name, UUID, enabled state, and trigger event.
    """
    return entity.get_player_toggleable_handler_infos()


def _handler_http_exception(
    entity: Entity,
    status_code: int,
    code: str,
    message: str,
    handler_uuid: Optional[str] = None,
) -> HTTPException:
    """Create a structured handler API error.

    Args:
        entity: Entity whose handler mutation failed.
        status_code: HTTP status code for the response.
        code: Machine-readable error code.
        message: Human-readable error message.
        handler_uuid: Optional handler UUID supplied by the client.

    Returns:
        HTTP exception with exact valid handler summaries.
    """
    handlers = _serialize_entity_handlers(entity)
    return _api_http_exception(
        status_code=status_code,
        code=code,
        message=message,
        entity_uuid=str(entity.uuid),
        entity_name=entity.name,
        handler_uuid=handler_uuid,
        handlers=[handler.model_dump(mode="json") for handler in handlers],
    )


def _equipment_slot_map() -> dict[str, Any]:
    """Return API slot names mapped to engine equipment-slot enums.

    Returns:
        Mapping from request slot names to weapon, body-part, and ring slots.
    """
    return {
        "weapon_melee_main": WeaponSlot.MELEE_MAIN,
        "weapon_melee_off": WeaponSlot.MELEE_OFF,
        "weapon_ranged_main": WeaponSlot.RANGED_MAIN,
        "weapon_ranged_off": WeaponSlot.RANGED_OFF,
        "helmet": BodyPart.HEAD,
        "body_armor": BodyPart.BODY,
        "gauntlets": BodyPart.HANDS,
        "greaves": BodyPart.LEGS,
        "boots": BodyPart.FEET,
        "amulet": BodyPart.AMULET,
        "cloak": BodyPart.CLOAK,
        "ring_left": RingSlot.LEFT,
        "ring_right": RingSlot.RIGHT,
    }


def _equipment_context(entity: Entity) -> dict:
    """Build correction metadata for equipment commands.

    Args:
        entity: Entity receiving the equipment command.

    Returns:
        Stable correction metadata without a parallel state snapshot.
    """
    return {
        "entity_uuid": str(entity.uuid),
        "entity_name": entity.name,
        "valid_slots": list(_equipment_slot_map().keys()),
    }


def _equipment_http_exception(
    entity: Entity,
    status_code: int,
    code: str,
    message: str,
    item_uuid: Optional[str] = None,
    slot: Optional[str] = None,
) -> HTTPException:
    """Create a structured equipment API error.

    Args:
        entity: Entity whose equipment mutation failed.
        status_code: HTTP status code for the response.
        code: Machine-readable error code.
        message: Human-readable error message.
        item_uuid: Optional item UUID supplied by the client.
        slot: Optional equipment slot supplied by the client.

    Returns:
        HTTP exception with equipment correction context.
    """
    return _api_http_exception(
        status_code=status_code,
        code=code,
        message=message,
        item_uuid=item_uuid,
        slot=slot,
        **_equipment_context(entity),
    )


def _session_context() -> dict:
    """Build correction context for session and game endpoints.

    Returns:
        Known session, player type, active game, and entity context.
    """
    mgr = sim.get_session_manager()
    game = sim.game
    return {
        "valid_player_types": [player_type.value for player_type in PlayerType],
        "known_sessions": [
            session.to_dict()
            for session in mgr.sessions.values()
        ],
        "active_game_id": str(game.game_id) if game else None,
        "active_entity_uuid": str(game.active_entity_uuid) if game and game.active_entity_uuid else None,
    }


def _session_http_exception(
    status_code: int,
    code: str,
    message: str,
    session_id: Optional[str] = None,
    **context: Any,
) -> HTTPException:
    """Create a structured session or game API error.

    Args:
        status_code: HTTP status code for the response.
        code: Machine-readable error code.
        message: Human-readable error message.
        session_id: Optional session ID supplied by the client.
        **context: Additional JSON-serializable correction context.

    Returns:
        HTTP exception with session and active-game context.
    """
    correction_context = _session_context()
    correction_context.update(context)
    return _api_http_exception(
        status_code=status_code,
        code=code,
        message=message,
        session_id=session_id,
        **correction_context,
    )


@dataclass(frozen=True)
class _ReplicationRequestContext:
    """Trusted player session and its resolved subjective authority."""

    session_id: UUID
    session: PlayerSession
    subjective_authority: ResolvedSubjectiveAuthority


def _resolve_replication_request(
    request: Request,
    session_id: str,
) -> _ReplicationRequestContext:
    """Resolve one canonical request from the in-process session registry."""
    try:
        sid = UUID(session_id)
    except ValueError:
        raise _api_http_exception(
            status_code=400,
            code="invalid_session_uuid",
            message="Invalid session ID format",
            session_id=session_id,
        )

    session = sim.get_session_manager().get_session(sid)
    if session is None:
        raise _api_http_exception(
            status_code=404,
            code="session_not_found",
            message="Session not found",
            session_id=session_id,
        )

    try:
        subjective_authority = resolve_subjective_authority(
            session,
        )
    except SubjectiveAuthorityError as exc:
        raise _api_http_exception(
            status_code=403,
            code="replication_authority_rejected",
            message=str(exc),
            session_id=session_id,
        )

    return _ReplicationRequestContext(
        session_id=sid,
        session=session,
        subjective_authority=subjective_authority,
    )


def _replication_runtime_context(
    request_context: _ReplicationRequestContext,
    *,
    expected_source_stream_id: Optional[str] = None,
    expected_generation_id: Optional[str],
    expected_perspective_epoch_id: Optional[str],
    allow_bootstrap_deferral: bool = False,
) -> CanonicalSubjectiveReplicationContext:
    """Bind and identity-check one canonical journal partition."""
    if sim.encounter is None:
        raise _api_http_exception(
            status_code=409,
            code="replication_source_unavailable",
            message="An active encounter is required for player replication",
        )
    try:
        context = canonical_subjective_replication_runtime.bind(
            request_context.subjective_authority,
            encounter=sim.encounter,
        )
        _ensure_game_terminal_callback()
        context.validate_identity(
            expected_source_stream_id=expected_source_stream_id,
            expected_generation_id=expected_generation_id,
            expected_perspective_epoch_id=expected_perspective_epoch_id,
        )
        return context
    except SubjectiveBootstrapDeferredError as exc:
        if allow_bootstrap_deferral:
            raise
        raise _api_http_exception(
            status_code=409,
            code="replication_partition_unavailable",
            message=str(exc),
        ) from exc
    except SubjectiveRuntimeIdentityError as exc:
        raise _api_http_exception(
            status_code=409,
            code="replication_identity_changed",
            message=str(exc),
            expected_source_stream_id=expected_source_stream_id,
            expected_generation_id=expected_generation_id,
            expected_perspective_epoch_id=expected_perspective_epoch_id,
        ) from exc
    except (SubjectiveRuntimeError, SubjectiveJournalError) as exc:
        raise _api_http_exception(
            status_code=409,
            code="replication_partition_unavailable",
            message=str(exc),
        ) from exc


def _replication_window_http_exception(
    exc: SubjectiveJournalError | SubjectiveRuntimeError,
) -> HTTPException:
    """Map an exact journal read failure to one structured recovery response."""
    if isinstance(exc, SubjectiveJournalResyncRequired):
        return _api_http_exception(
            status_code=409,
            code="replication_resync_required",
            message=str(exc),
            requested_cursor=exc.requested_cursor,
            retained_from_cursor=exc.retained_from_cursor,
        )
    if isinstance(exc, SubjectiveRuntimeIdentityError):
        return _api_http_exception(
            status_code=409,
            code="replication_identity_changed",
            message=str(exc),
        )
    return _api_http_exception(
        status_code=409,
        code="replication_partition_unavailable",
        message=str(exc),
    )


def _replication_delivery_watermarks(
    delivery: (
        SubjectiveSyncDelivery
        | SubjectiveFrameDelivery
        | SubjectiveCombatLogDelivery
    ),
) -> PlayerReplicationWatermarks:
    """Return the four-cursor boundary represented by one stream delivery."""
    if isinstance(delivery, SubjectiveFrameDelivery):
        return delivery.frame.watermarks
    return delivery.watermarks


def _replication_stream_id(
    delivery: (
        SubjectiveSyncDelivery
        | SubjectiveFrameDelivery
        | SubjectiveCombatLogDelivery
    ),
) -> str:
    """Encode all independent player cursors into one diagnostic SSE ID."""
    watermarks = _replication_delivery_watermarks(delivery)
    return (
        f"s={watermarks.source_event_cursor};"
        f"o={watermarks.observation_cursor};"
        f"p={watermarks.presentation_cursor};"
        f"l={watermarks.combat_log_cursor}"
    )


def _assert_objective_diagnostics_access(request: Request) -> None:
    """Accept objective diagnostics on the direct single-game server."""


def _build_objective_event_window(
    *,
    source: ObjectiveSourceSnapshot,
) -> GameEventFramesResponse:
    """Build one all-phase window from a previously locked source boundary."""
    try:
        return build_objective_game_event_frames(
            source.event_source_slots,
            source_stream_id=source.source_stream_id,
            generation_id=source.generation_id,
            combat_log_source=source.complete_combat_log_source,
            retained_from_cursor=0,
            from_cursor=source.event_from_cursor,
            through_cursor=source.event_through_cursor,
            total=source.event_cursor,
        )
    except ObjectiveTimelineError as exc:
        raise _api_http_exception(
            status_code=409,
            code="objective_diagnostics_window_unavailable",
            message=str(exc),
            from_cursor=source.event_from_cursor,
            through_cursor=source.event_through_cursor,
        ) from exc


def _capture_objective_source_snapshot(
    *,
    from_event_cursor: Optional[int] = None,
    through_event_cursor: Optional[int] = None,
    event_limit: Optional[int] = None,
    from_combat_log_cursor: Optional[int] = None,
    through_combat_log_cursor: Optional[int] = None,
    combat_log_limit: Optional[int] = None,
    expected_source_stream_id: Optional[str] = None,
    expected_generation_id: Optional[str] = None,
) -> ObjectiveSourceSnapshot:
    """Capture one locked objective event/log boundary or fail closed."""
    encounter = sim.encounter
    if encounter is None:
        raise _api_http_exception(
            status_code=409,
            code="objective_diagnostics_source_unavailable",
            message="Objective diagnostics require an encounter",
        )
    event_stream.ensure_attached()
    try:
        return event_stream.capture_objective_source_snapshot(
            encounter,
            from_event_cursor=from_event_cursor,
            through_event_cursor=through_event_cursor,
            event_limit=event_limit,
            from_combat_log_cursor=from_combat_log_cursor,
            through_combat_log_cursor=through_combat_log_cursor,
            combat_log_limit=combat_log_limit,
            expected_source_stream_id=expected_source_stream_id,
            expected_generation_id=expected_generation_id,
        )
    except CombatLogSourceError as exc:
        code = (
            "objective_diagnostics_source_changed"
            if "changed" in str(exc)
            else "objective_diagnostics_window_unavailable"
        )
        raise _api_http_exception(
            status_code=409,
            code=code,
            message=str(exc),
            from_event_cursor=from_event_cursor,
            through_event_cursor=through_event_cursor,
            from_combat_log_cursor=from_combat_log_cursor,
            through_combat_log_cursor=through_combat_log_cursor,
        ) from exc


def _objective_backfill_deliveries(
    events: GameEventFramesResponse,
    logs: ObjectiveCombatLogFramesResponse,
) -> tuple[tuple[str, Any], ...]:
    """Merge exact event/log backfill in causal cursor order."""
    deliveries: list[tuple[int, int, int, str, Any]] = []
    deliveries.extend(
        (
            frame.event_cursor,
            0,
            frame.event_cursor,
            "game_event",
            frame,
        )
        for frame in events.frames
    )
    deliveries.extend(
        (
            frame.event_cursor,
            1,
            frame.combat_log_cursor,
            "combat_log",
            frame,
        )
        for frame in logs.frames
    )
    deliveries.sort(key=lambda row: row[:3])
    return tuple(
        (event_name, frame)
        for _event_cursor, _channel_order, _channel_cursor, event_name, frame
        in deliveries
    )




def _encounter_context() -> dict:
    """Build correction context for the active standalone encounter.

    Returns:
        Encounter status fields used by structured command errors.
    """
    return {
        "has_encounter": sim.encounter is not None,
        "paused": sim.paused,
        "encounter_state": sim.encounter.state.value if sim.encounter else None,
        "round_number": sim.encounter.round_number if sim.encounter else None,
    }


def _mapeditor_context() -> dict:
    """Build correction context for mapeditor endpoint failures.

    Returns:
        Catalog, saved-map, and current-map context for map-editor errors.
    """
    catalog = build_catalog()
    saved_maps = list_saved_editor_maps().maps
    try:
        snapshot = get_editor_snapshot()
        current_map = {
            "grid_bounds": snapshot.grid_bounds.model_dump(mode="json"),
            "tile_count": len(snapshot.tiles),
            "floor_object_count": len(snapshot.floor_objects),
        }
    except Exception:
        logger.exception("Failed to build current map-editor correction context")
        current_map = None

    return {
        "valid_presets": [entry.id for entry in catalog.presets],
        "valid_tiles": [entry.id for entry in catalog.tiles],
        "content_set_digest": catalog.content_set_digest,
        "valid_object_recipes": [
            entry.recipe.model_dump(mode="json")
            for entry in catalog.objects
        ],
        "valid_loot_recipes": [
            entry.recipe.model_dump(mode="json")
            for entry in catalog.loot
        ],
        "saved_map_ids": [metadata.id for metadata in saved_maps],
        "current_map": current_map,
        "directional_patch_required_fields": ["directional_channel", "direction", "passable"],
    }


def _mapeditor_http_exception(
    status_code: int,
    code: str,
    message: str,
    **context: Any,
) -> HTTPException:
    """Create a structured mapeditor API error.

    Args:
        status_code: HTTP status code for the response.
        code: Machine-readable error code.
        message: Human-readable error message.
        **context: Additional JSON-serializable correction context.

    Returns:
        HTTP exception with map-editor correction context.
    """
    return _api_http_exception(
        status_code=status_code,
        code=code,
        message=message,
        **_mapeditor_context(),
        **context,
    )


def _parse_session_entity_ids(
    session_id_str: str,
    entity_uuid_str: str,
) -> tuple[UUID, UUID]:
    """Parse one session/entity authority pair with structured diagnostics."""
    try:
        session_id = UUID(session_id_str)
    except ValueError:
        raise _api_http_exception(
            status_code=400,
            code="invalid_session_uuid",
            message="Invalid session ID format",
            session_id=session_id_str,
        )

    try:
        entity_uuid = UUID(entity_uuid_str)
    except ValueError:
        raise _entity_lookup_exception(
            entity_uuid=entity_uuid_str,
            status_code=400,
            code="invalid_entity_uuid",
            message="Invalid entity UUID format",
        )

    return session_id, entity_uuid


def _require_runtime_entity(entity_uuid: UUID) -> Entity:
    """Resolve an authorized runtime entity through the canonical registry."""
    entity = Entity.get(entity_uuid)
    if not entity:
        raise _entity_lookup_exception(
            entity_uuid=str(entity_uuid),
            status_code=404,
            code="entity_not_found",
            message="Entity not found",
        )
    return entity


def validate_session_action(session_id_str: str, entity_uuid_str: str) -> Entity:
    """Validate session ownership plus active-turn command authority."""
    session_id, entity_uuid = _parse_session_entity_ids(
        session_id_str,
        entity_uuid_str,
    )
    mgr = sim.get_session_manager()
    _, _ = mgr.validate_action(session_id, entity_uuid)
    return _require_runtime_entity(entity_uuid)


def validate_session_entity_inspection(
    session_id_str: str,
    entity_uuid_str: str,
) -> tuple[Entity, GameSession]:
    """Authorize a read of one controlled entity without granting a command."""
    session_id, entity_uuid = _parse_session_entity_ids(
        session_id_str,
        entity_uuid_str,
    )
    manager = sim.get_session_manager()
    _, game = manager.validate_controlled_entity(session_id, entity_uuid)
    return _require_runtime_entity(entity_uuid), game


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage event-stream resources for the FastAPI application lifespan.

    Args:
        app: FastAPI application using the lifespan hook.

    Yields:
        None while the application is running.
    """
    loaded_content_system = bootstrap_content_system()
    installed_content_system = SERVER_CONTENT_SYSTEM_RUNTIME.install(
        loaded_content_system,
    )
    app.state.content_system = installed_content_system
    app.state.game_archive_store = GameArchiveStore(
        os.environ.get("DND_GAME_ARCHIVE_ROOT", ".runtime/game-archives"),
    )
    await asyncio.to_thread(prewarm_game_creation_preview_worker)

    with latency_sensitive_gc():
        event_stream.start()
        canonical_subjective_replication_runtime.ensure_attached()
        game_summary_store.ensure_attached()
        _ensure_game_terminal_callback()
        try:
            yield
        finally:
            if sim.combat_task and not sim.combat_task.done():
                sim.combat_task.cancel()
                try:
                    await sim.combat_task
                except asyncio.CancelledError:
                    pass
            try:
                canonical_subjective_replication_runtime.stop()
            finally:
                try:
                    event_stream.stop()
                finally:
                    sim.reset()
                    reset_engine_runtime()
                    await asyncio.to_thread(
                        close_game_creation_preview_worker,
                    )

app = FastAPI(
    title="D&D Engine Event Server",
    description="Event-driven game engine with canonical player replication and objective diagnostics",
    lifespan=lifespan
)

_world_replacement_lock = asyncio.Lock()


async def _serialize_world_replacement() -> AsyncIterator[None]:
    """Serialize every route that can replace session or engine ownership."""
    async with _world_replacement_lock:
        yield

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestTimingMiddleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Log structured HTTP errors and return their detail payload.

    Args:
        request: Incoming HTTP request.
        exc: HTTP exception raised by route logic.

    Returns:
        JSON response containing the exception detail.
    """
    logger.error(f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log unhandled exceptions and return a generic JSON response.

    Args:
        request: Incoming HTTP request.
        exc: Unhandled exception raised by route logic.

    Returns:
        JSON response with a 500 status code and exception detail string.
    """
    logger.error(f"Unhandled error on {request.method} {request.url.path}:\n{traceback.format_exc()}")
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/")
async def root():
    """Return a state-free process health acknowledgement.

    Returns:
        Process health payload without game or session state.
    """
    return {"status": "running"}


@app.get("/server/capabilities", response_model=ServerCapabilitiesResponse)
async def get_server_capabilities() -> ServerCapabilitiesResponse:
    """Return the direct single-game server topology."""
    return ServerCapabilitiesResponse()


@app.get("/content/manifest", response_model=ContentManifestResponse)
async def get_content_manifest(
    request: Request,
    response: Response,
) -> ContentManifestResponse | Response:
    """Return the exact installed content-set and source identity."""
    return serve_content_manifest(
        content_system=SERVER_CONTENT_SYSTEM_RUNTIME.require(),
        request=request,
        response=response,
    )


@app.get("/content/catalog", response_model=ContentCatalogResponse)
async def get_content_catalog(
    request: Request,
    response: Response,
) -> ContentCatalogResponse | Response:
    """Return public code-free descriptors for the installed content set."""
    return serve_content_catalog(
        content_system=SERVER_CONTENT_SYSTEM_RUNTIME.require(),
        request=request,
        response=response,
    )


@app.get("/mapeditor/catalog", response_model=MapEditorCatalog)
async def get_mapeditor_catalog():
    """Return map-editor presets, terrain, objects, and loot catalog data.

    Returns:
        Catalog DTO for map-editor clients.
    """
    return build_catalog()


@app.get("/catalog/spells", response_model=SpellCatalogResponse)
async def get_spell_catalog():
    """Return spell templates and design-time VFX/rules metadata.

    Returns:
        Spell catalog DTO for clients.
    """
    return build_spell_catalog()


@app.post(
    "/mapeditor/maps",
    response_model=MapEditorMapSnapshot,
    dependencies=[Depends(_serialize_world_replacement)],
)
async def create_mapeditor_map(request: MapEditorCreateMapRequest):
    """Create or reset an entity-free map-editor map.

    Args:
        request: Map creation request describing source, preset, and size.

    Returns:
        Snapshot for the newly active editor map.

    Raises:
        HTTPException: If the requested map source, preset, or size is invalid.
    """
    try:
        await prepare_new_game_start()
        return create_editor_map(request)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=400,
            code="mapeditor_map_create_failed",
            message=str(exc),
            requested_source=request.source,
            requested_preset_id=request.preset_id,
            include_entities=request.include_entities,
            requested_size={"width": request.width, "height": request.height},
        )


@app.get("/mapeditor/map", response_model=MapEditorMapSnapshot)
async def get_mapeditor_map():
    """Return the current entity-free map-editor snapshot.

    Returns:
        Current editor map snapshot.
    """
    return get_editor_snapshot()


@app.get("/mapeditor/saves", response_model=MapEditorSavedMapList)
async def list_mapeditor_saves():
    """Return file-backed map-editor map saves.

    Returns:
        Saved map metadata list.
    """
    return list_saved_editor_maps()


@app.post("/mapeditor/saves", response_model=MapEditorSavedMapMetadata)
async def save_mapeditor_map(request: MapEditorSaveMapRequest):
    """Save the current entity-free editor map state.

    Args:
        request: Save request containing map ID, display name, and overwrite
            policy.

    Returns:
        Metadata for the saved map.

    Raises:
        HTTPException: If the save ID is invalid or overwrite is not allowed.
    """
    try:
        return save_current_editor_map(request)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=400,
            code="mapeditor_save_failed",
            message=str(exc),
            requested_map_id=request.id,
            requested_name=request.name,
            overwrite=request.overwrite,
        )


@app.get("/mapeditor/saves/{map_id}", response_model=MapEditorSavedMapDocument)
async def get_mapeditor_save(map_id: str):
    """Read a saved editor map document without loading it.

    Args:
        map_id: Saved map identifier.

    Returns:
        Saved map document.

    Raises:
        HTTPException: If the saved map cannot be found.
    """
    try:
        return get_saved_editor_map(map_id)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=404,
            code="mapeditor_save_not_found",
            message=str(exc),
            requested_map_id=map_id,
        )


@app.post(
    "/mapeditor/saves/{map_id}/load",
    response_model=MapEditorMapSnapshot,
    dependencies=[Depends(_serialize_world_replacement)],
)
async def load_mapeditor_save(map_id: str):
    """Load a saved editor map into the entity-free editor world.

    Args:
        map_id: Saved map identifier.

    Returns:
        Snapshot for the loaded editor map.

    Raises:
        HTTPException: If the saved map cannot be loaded.
    """
    try:
        await prepare_new_game_start()
        return load_saved_editor_map(map_id)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=404,
            code="mapeditor_save_load_failed",
            message=str(exc),
            requested_map_id=map_id,
        )


@app.delete("/mapeditor/saves/{map_id}", status_code=204)
async def delete_mapeditor_save(map_id: str):
    """Delete a saved editor map document.

    Args:
        map_id: Saved map identifier.

    Returns:
        None.

    Raises:
        HTTPException: If the saved map cannot be deleted.
    """
    try:
        delete_saved_editor_map(map_id)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=404,
            code="mapeditor_save_delete_failed",
            message=str(exc),
            requested_map_id=map_id,
        )


@app.post("/mapeditor/map/tiles", response_model=MapEditorMapSnapshot)
async def patch_mapeditor_tiles(request: MapEditorTilePatchRequest):
    """Patch editor tiles through GridMap and terrain factories.

    Args:
        request: Tile patch request with terrain and directional-border edits.

    Returns:
        Updated editor map snapshot.

    Raises:
        HTTPException: If any requested tile patch is invalid.
    """
    try:
        return apply_tile_patches(request.tiles)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=400,
            code="mapeditor_tile_patch_failed",
            message=str(exc),
            requested_tiles=[tile.model_dump(mode="json") for tile in request.tiles],
        )


@app.post("/mapeditor/map/connectors", response_model=MapEditorConnectorMutationResponse)
async def upsert_mapeditor_connector(request: MapEditorConnectorUpsertRequest):
    """Create or replace one exact authored connector definition."""
    try:
        return upsert_editor_connector(request)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=400,
            code="mapeditor_connector_upsert_failed",
            message=str(exc),
            requested_connector=request.definition.model_dump(mode="json"),
        )


@app.post("/mapeditor/map/connectors/enabled", response_model=MapEditorConnectorMutationResponse)
async def enable_mapeditor_connector(request: MapEditorConnectorEnabledRequest):
    """Enable or disable one connector through GridMap ownership."""
    try:
        return set_editor_connector_enabled(request)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=400,
            code="mapeditor_connector_enable_failed",
            message=str(exc),
            requested_authored_id=request.authored_id,
        )


@app.post("/mapeditor/map/connectors/delete", response_model=MapEditorConnectorMutationResponse)
async def delete_mapeditor_connector(request: MapEditorConnectorDeleteRequest):
    """Delete one connector by stable authored identity."""
    try:
        return delete_editor_connector(request)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=400,
            code="mapeditor_connector_delete_failed",
            message=str(exc),
            requested_authored_id=request.authored_id,
        )


@app.post("/mapeditor/map/objects", response_model=APIFloorObject)
async def place_mapeditor_object(request: MapEditorObjectPlaceRequest):
    """Place an exact public item or environment recipe on the editor map.

    Args:
        request: Exact content recipe, expected content set, position, and
            mutable post-materialization state.

    Returns:
        Serialized floor object that was placed.

    Raises:
        HTTPException: If content identity, policy, state, or position is invalid.
    """
    try:
        return place_catalog_object(request)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=400,
            code="mapeditor_object_place_failed",
            message=str(exc),
            requested_recipe=request.recipe.model_dump(mode="json"),
            requested_content_set_digest=request.content_set_digest,
            requested_position=list(request.position),
            requested_runtime_state=request.runtime_state.model_dump(
                mode="json",
            ),
        )


@app.post("/mapeditor/map/objects/delete", response_model=MapEditorMapSnapshot)
async def delete_mapeditor_object(request: MapEditorObjectDeleteRequest):
    """Delete editor objects by UUID or tile position.

    Args:
        request: Object deletion request with object UUID or tile position.

    Returns:
        Updated editor map snapshot.

    Raises:
        HTTPException: If the requested object deletion is invalid.
    """
    try:
        return delete_catalog_object(request)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=400,
            code="mapeditor_object_delete_failed",
            message=str(exc),
            requested_object_uuid=request.object_uuid,
            requested_position=list(request.position) if request.position is not None else None,
        )


@app.get("/mapeditor/map/walkability", response_model=MapEditorWalkabilityResponse)
async def get_mapeditor_walkability():
    """Return objective walkability without entities.

    Returns:
        Walkability layer DTO.
    """
    return get_walkability()


@app.get("/mapeditor/map/visibility", response_model=MapEditorVisibilityResponse)
async def get_mapeditor_visibility():
    """Return objective line-of-sight blockers without observer visibility.

    Returns:
        Visibility-blocker layer DTO.
    """
    return get_visibility_blockers()


@app.get("/mapeditor/map/light", response_model=MapEditorLightResponse)
async def get_mapeditor_light():
    """Return objective resolved tile light levels.

    Returns:
        Objective light layer DTO.
    """
    return get_objective_light()


@app.post("/session/create", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """Create a new player session.

    Args:
        request: Session creation request with player type and optional display
            name.

    Returns:
        Created session identifier, player type, and display name.

    Raises:
        HTTPException: If the requested player type is invalid.
    """
    try:
        ptype = PlayerType(request.player_type.lower())
    except ValueError:
        raise _session_http_exception(
            status_code=400,
            code="invalid_player_type",
            message=f"Invalid player_type: {request.player_type}",
            player_type=request.player_type,
        )

    mgr = sim.get_session_manager()
    session = mgr.create_session(ptype, request.name)

    return CreateSessionResponse(
        session_id=str(session.session_id),
        player_type=session.player_type.value,
        name=session.name
    )


def build_session_status(sid: UUID, ping: bool = False) -> SessionPingResponse:
    """Build the shared session status payload.

    Args:
        sid: Session UUID to report.
        ping: Whether to update the session activity timestamp first.

    Returns:
        Session ping/status response with active-turn and controlled-entity
        context.

    Raises:
        HTTPException: If the session does not exist.
    """
    mgr = sim.get_session_manager()
    session = mgr.get_session(sid)

    if not session:
        raise _session_http_exception(
            status_code=404,
            code="session_not_found",
            message="Session not found",
            session_id=str(sid),
        )

    if ping:
        session.ping()

    game = sim.game
    is_my_turn = False
    active_entity_uuid = None
    active_entity_name = None

    if game:
        active_entity_uuid = game.active_entity_uuid
        if active_entity_uuid:
            entity = Entity.get(active_entity_uuid)
            active_entity_name = entity.name if entity else None
            is_my_turn = game.is_player_turn(session.session_id)

    return SessionPingResponse(
        status="ok",
        session_id=str(session.session_id),
        connection_status=session.connection_status.value,
        is_my_turn=is_my_turn,
        active_entity_uuid=str(active_entity_uuid) if active_entity_uuid else None,
        active_entity_name=active_entity_name,
        controlled_entities=[str(e) for e in session.controlled_entities]
    )


@app.get(
    "/replication/bootstrap",
    response_model=SubjectiveReplicationBootstrap,
)
async def get_replication_bootstrap(
    request: Request,
    response: Response,
    session_id: str,
) -> SubjectiveReplicationBootstrap | JSONResponse:
    """Return one atomic renderer-complete subjective reducer seed."""
    response.headers["Cache-Control"] = "private, no-store"
    request_context = _resolve_replication_request(request, session_id)
    try:
        context = _replication_runtime_context(
            request_context,
            expected_generation_id=None,
            expected_perspective_epoch_id=None,
            allow_bootstrap_deferral=True,
        )
        return context.bootstrap()
    except SubjectiveBootstrapDeferredError as exc:
        return JSONResponse(
            status_code=409,
            content=exc.deferral.model_dump(mode="json"),
            headers={"Cache-Control": "private, no-store"},
        )
    except (SubjectiveRuntimeError, SubjectiveJournalError) as exc:
        raise _replication_window_http_exception(exc) from exc


@app.get(
    "/replication/frames",
    response_model=SubjectiveFramesResponse,
)
async def get_replication_frames(
    request: Request,
    response: Response,
    session_id: str,
    expected_source_stream_id: str,
    expected_generation_id: str,
    expected_perspective_epoch_id: str,
    from_observation_cursor: int = Query(default=0, ge=0),
    limit: Optional[int] = Query(default=None, ge=1),
) -> SubjectiveFramesResponse:
    """Return one exact retained page of reducer and presentation frames."""
    response.headers["Cache-Control"] = "private, no-store"
    request_context = _resolve_replication_request(request, session_id)
    context = _replication_runtime_context(
        request_context,
        expected_source_stream_id=expected_source_stream_id,
        expected_generation_id=expected_generation_id,
        expected_perspective_epoch_id=expected_perspective_epoch_id,
    )
    try:
        return context.frames(
            from_observation_cursor=from_observation_cursor,
            limit=limit,
        )
    except (SubjectiveRuntimeError, SubjectiveJournalError) as exc:
        raise _replication_window_http_exception(exc) from exc


@app.get(
    "/replication/combat-log",
    response_model=SubjectiveCombatLogFramesResponse,
)
async def get_replication_combat_log(
    request: Request,
    response: Response,
    session_id: str,
    expected_source_stream_id: str,
    expected_generation_id: str,
    expected_perspective_epoch_id: str,
    from_combat_log_cursor: int = Query(default=0, ge=0),
    limit: Optional[int] = Query(default=None, ge=1),
) -> SubjectiveCombatLogFramesResponse:
    """Return one exact nullable source-cursor window for a player perspective."""
    response.headers["Cache-Control"] = "private, no-store"
    request_context = _resolve_replication_request(request, session_id)
    context = _replication_runtime_context(
        request_context,
        expected_source_stream_id=expected_source_stream_id,
        expected_generation_id=expected_generation_id,
        expected_perspective_epoch_id=expected_perspective_epoch_id,
    )
    try:
        return context.combat_log(
            from_combat_log_cursor=from_combat_log_cursor,
            limit=limit,
        )
    except (SubjectiveRuntimeError, SubjectiveJournalError) as exc:
        raise _replication_window_http_exception(exc) from exc


@app.post("/session/{session_id}/ping", response_model=SessionPingResponse)
async def ping_session(session_id: str):
    """Ping a session and return its current status.

    Args:
        session_id: Session UUID string from the route path.

    Returns:
        Session status response after refreshing session activity.

    Raises:
        HTTPException: If the session UUID is malformed or unknown.
    """
    try:
        sid = UUID(session_id)
    except ValueError:
        raise _session_http_exception(
            status_code=400,
            code="invalid_session_uuid",
            message="Invalid session ID format",
            session_id=session_id,
        )

    return build_session_status(sid, ping=True)


@app.delete(
    "/session/{session_id}",
    dependencies=[Depends(_serialize_world_replacement)],
)
async def delete_session(session_id: str):
    """Delete a session and remove its game associations.

    Args:
        session_id: Session UUID string from the route path.

    Returns:
        Deletion status payload.

    Raises:
        HTTPException: If the session UUID is malformed or unknown.
    """
    try:
        sid = UUID(session_id)
    except ValueError:
        raise _session_http_exception(
            status_code=400,
            code="invalid_session_uuid",
            message="Invalid session ID format",
            session_id=session_id,
        )

    mgr = sim.get_session_manager()
    session = mgr.get_session(sid)

    if not session:
        raise _session_http_exception(
            status_code=404,
            code="session_not_found",
            message="Session not found",
            session_id=session_id,
        )

    canonical_subjective_replication_runtime.retire_session(session_id)
    controlled_entities = tuple(session.controlled_entities)
    mgr.remove_session(sid)
    perspective_epoch_registry.clear_session(session_id)
    if sim.encounter is not None:
        for entity_uuid in controlled_entities:
            if entity_uuid in sim.encounter.combatants:
                sim.encounter.set_controller_for(
                    entity_uuid,
                    PassController(source_entity_uuid=entity_uuid),
                )

    return {"status": "deleted", "session_id": session_id}


@app.post("/game/join", response_model=JoinGameResponse)
async def join_game(request: JoinGameRequest):
    """Join the active game with a session.

    Participant sessions claim one explicit entity UUID sequence. Observer
    sessions claim no entities and provide one explicit subjective observer
    sequence.

    Args:
        request: Join request with session ID and optional entity or faction
            selection.

    Returns:
        Join result with controlled entity UUIDs.

    Raises:
        HTTPException: If the session UUID is malformed, the session is missing,
            or no active game exists.
    """
    requested_entity_uuids = request.requested_entity_uuids()
    requested_observer_entity_uuids = request.requested_observer_entity_uuids()
    try:
        sid = UUID(request.session_id)
    except ValueError:
        raise _session_http_exception(
            status_code=400,
            code="invalid_session_uuid",
            message="Invalid session ID format",
            session_id=request.session_id,
            requested_entity_uuids=requested_entity_uuids,
        )

    mgr = sim.get_session_manager()
    session = mgr.get_session(sid)

    if not session:
        raise _session_http_exception(
            status_code=404,
            code="session_not_found",
            message="Session not found",
            session_id=request.session_id,
            requested_entity_uuids=requested_entity_uuids,
        )

    game = sim.game
    if not game:
        raise _session_http_exception(
            status_code=400,
            code="no_active_game",
            message="No active game to join",
            session_id=request.session_id,
            requested_entity_uuids=requested_entity_uuids,
        )

    if session.player_type == PlayerType.OBSERVER and requested_entity_uuids:
        raise _session_http_exception(
            status_code=400,
            code="observer_cannot_control_entities",
            message="Observer sessions cannot claim controlled entities",
            session_id=request.session_id,
            requested_entity_uuids=requested_entity_uuids,
        )

    if session.player_type == PlayerType.OBSERVER:
        if not requested_observer_entity_uuids:
            raise _session_http_exception(
                status_code=400,
                code="observer_perspective_required",
                message="Observer sessions require an explicit subjective observer set",
                session_id=request.session_id,
            )
        try:
            observer_entities = frozenset(
                UUID(value) for value in requested_observer_entity_uuids
            )
            active_observer_uuid = (
                UUID(request.active_observer_uuid)
                if request.active_observer_uuid is not None
                else min(observer_entities, key=str)
            )
        except ValueError:
            raise _session_http_exception(
                status_code=400,
                code="invalid_observer_uuid",
                message="Observer perspective contains an invalid entity UUID",
                session_id=request.session_id,
            )
        if active_observer_uuid not in observer_entities:
            raise _session_http_exception(
                status_code=400,
                code="active_observer_outside_perspective",
                message="Active observer must belong to the observer set",
                session_id=request.session_id,
            )
        missing_observers = [
            str(entity_uuid)
            for entity_uuid in observer_entities
            if Entity.get(entity_uuid) is None
        ]
        if missing_observers:
            raise _session_http_exception(
                status_code=400,
                code="observer_entity_not_found",
                message="Observer perspective references an unknown entity",
                session_id=request.session_id,
                observer_entity_uuids=missing_observers,
            )
        session.configure_subjective_observers(
            observer_entities,
            active_observer_uuid=active_observer_uuid,
        )
    elif requested_observer_entity_uuids or request.active_observer_uuid is not None:
        raise _session_http_exception(
            status_code=400,
            code="participant_observer_override_rejected",
            message="Participant observer knowledge is derived exactly from controlled entities",
            session_id=request.session_id,
        )
    elif not requested_entity_uuids:
        raise _session_http_exception(
            status_code=400,
            code="controlled_entity_selection_required",
            message="Participant sessions require explicit controlled entity UUIDs",
            session_id=request.session_id,
        )

    try:
        controlled_entity_uuids = tuple(
            UUID(value) for value in requested_entity_uuids
        )
    except ValueError:
        raise _session_http_exception(
            status_code=400,
            code="invalid_entity_uuid",
            message="Controlled entity selection contains an invalid UUID",
            session_id=request.session_id,
            requested_entity_uuids=requested_entity_uuids,
        )
    missing_entities = [
        str(entity_uuid)
        for entity_uuid in controlled_entity_uuids
        if Entity.get(entity_uuid) is None
    ]
    if missing_entities:
        raise _session_http_exception(
            status_code=400,
            code="controlled_entity_not_found",
            message="Controlled entity selection references an unknown entity",
            session_id=request.session_id,
            requested_entity_uuids=requested_entity_uuids,
            missing_entity_uuids=missing_entities,
        )

    subjective_authority_before = _capture_subjective_session_authority(mgr)
    if session.session_id not in game.players:
        game.add_player(session)
    assigned = []
    for entity_uuid in controlled_entity_uuids:
        if game.assign_entity(entity_uuid, session.session_id):
            assigned.append(str(entity_uuid))
            if sim.encounter is not None:
                sim.encounter.set_controller_for(
                    entity_uuid,
                    HumanController(source_entity_uuid=entity_uuid),
                )
    _retire_changed_subjective_sessions(mgr, subjective_authority_before)

    observer_join = session.player_type == PlayerType.OBSERVER
    return JoinGameResponse(
        success=observer_join or len(assigned) > 0,
        game_id=str(game.game_id),
        session_id=str(session.session_id),
        controlled_entities=assigned,
        observer_entities=[
            str(entity_uuid) for entity_uuid in sorted(session.observer_entities, key=str)
        ],
        active_observer_uuid=(
            str(session.active_observer_uuid)
            if session.active_observer_uuid is not None
            else None
        ),
        message=(
            "Joined game as observer"
            if observer_join
            else f"Joined game, controlling {len(assigned)} entities"
        ),
    )


@app.get("/game/status", response_model=StandaloneGameStatusResponse)
async def get_game_status() -> StandaloneGameStatusResponse:
    """Return current game status including all joined sessions.

    Returns:
        Game status payload with active entity, encounter activity, and session
        summaries.
    """
    game = sim.game

    if not game:
        return StandaloneGameStatusResponse(
            active=False,
            encounter_active=False,
            sessions=[],
        )

    sessions_info = []
    for session in game.players.values():
        sessions_info.append(StandaloneGameSessionSummary(
            session_id=str(session.session_id),
            player_type=session.player_type.value,
            name=session.name,
            connection_status=session.connection_status.value,
            controlled_entities=[str(entity_uuid) for entity_uuid in session.controlled_entities],
            is_their_turn=game.is_player_turn(session.session_id),
        ))

    return StandaloneGameStatusResponse(
        active=True,
        game_id=str(game.game_id),
        encounter_active=(
            game.encounter is not None and game.encounter.state.value == "active"
        ),
        active_entity_uuid=(str(game.active_entity_uuid) if game.active_entity_uuid else None),
        sessions=sessions_info,
        creation=sim.current_creation,
    )


@app.get("/game/evidence/summary", response_model=GameSummaryEvidence)
async def get_terminal_summary() -> GameSummaryEvidence:
    """Return the latest in-process canonical terminal summary."""
    evidence = game_summary_store.get_evidence()
    if evidence is None:
        raise _api_http_exception(
            status_code=404,
            code="terminal_summary_not_ready",
            message="The active game has no terminal summary yet",
        )
    return evidence


@app.get("/game/evidence/objective-replay", response_model=ObjectiveReplayBundle)
async def get_terminal_objective_replay() -> ObjectiveReplayBundle:
    """Materialize the immutable replay after terminal journals close."""
    capture = game_summary_store.get_replay_capture()
    if capture is None:
        raise _api_http_exception(
            status_code=404,
            code="terminal_objective_replay_not_ready",
            message="The active game has no terminal objective replay yet",
        )
    encounter = Encounter.get(UUID(capture.encounter_uuid))
    if encounter is None:
        raise _api_http_exception(
            status_code=500,
            code="terminal_objective_replay_encounter_missing",
            message="The terminal encounter is no longer retained",
        )
    try:
        return build_objective_replay(
            capture,
            encounter=encounter,
            stream=event_stream,
        )
    except GameReplayError as exc:
        raise _api_http_exception(
            status_code=500,
            code="terminal_objective_replay_invalid",
            message=str(exc),
        ) from exc


@app.get("/game/evidence/archive", response_model=GameArchive)
async def get_terminal_game_archive() -> GameArchive:
    """Return the latest validated database-free terminal archive."""
    evidence = game_summary_store.get_evidence()
    if evidence is None:
        raise _api_http_exception(
            status_code=404,
            code="terminal_archive_not_ready",
            message="The active game has no terminal archive yet",
        )
    store = getattr(app.state, "game_archive_store", game_archive_store)
    archive = store.read(evidence.summary.game_id)
    if archive is None:
        raise _api_http_exception(
            status_code=404,
            code="terminal_archive_not_ready",
            message="The terminal archive has not been written",
        )
    return archive


@app.get(
    "/diagnostics/subjective-parity",
    response_model=SubjectiveRenderParityDiagnosticsResponse,
)
async def get_subjective_render_parity_diagnostics(
    request: Request,
    response: Response,
    session_id: str,
) -> SubjectiveRenderParityDiagnosticsResponse:
    """Compare an open player reducer with objective state plus independent censorship."""

    _assert_objective_diagnostics_access(request)
    response.headers["Cache-Control"] = "private, no-store"
    request_context = _resolve_replication_request(request, session_id)
    for _attempt in range(3):
        with event_stream.source_boundary():
            encounter = sim.encounter
            if encounter is None:
                raise _api_http_exception(
                    status_code=409,
                    code="objective_diagnostics_source_unavailable",
                    message="Subjective parity diagnostics require an encounter",
                )
            source = _capture_objective_source_snapshot()
            objective = build_current_objective_world(encounter=encounter)
            try:
                subjective = (
                    canonical_subjective_replication_runtime.diagnostic_snapshot(
                        request_context.subjective_authority,
                        encounter=encounter,
                    )
                )
            except (SubjectiveRuntimeError, SubjectiveJournalError) as exc:
                raise _api_http_exception(
                    status_code=409,
                    code="subjective_parity_partition_unavailable",
                    message=str(exc),
                    session_id=session_id,
                ) from exc
            same_boundary = (
                subjective.protocol.source_stream_id == source.source_stream_id
                and subjective.protocol.generation_id == source.generation_id
                and subjective.watermarks.source_event_cursor == source.event_cursor
            )
            if (
                same_boundary
                and sim.encounter is encounter
                and event_stream.objective_source_snapshot_is_current(
                    source,
                    encounter,
                )
            ):
                try:
                    return build_subjective_render_parity_diagnostics(
                        objective=objective,
                        subjective=subjective.world,
                        perspective=subjective.perspective,
                        watermarks=subjective.watermarks,
                        source_stream_id=source.source_stream_id,
                        generation_id=source.generation_id,
                        grid=get_map(),
                    )
                except SubjectiveParityDiagnosticsError as exc:
                    raise _api_http_exception(
                        status_code=409,
                        code="subjective_parity_comparison_unavailable",
                        message=str(exc),
                        session_id=session_id,
                    ) from exc
    raise _api_http_exception(
        status_code=409,
        code="subjective_parity_source_changed",
        message=(
            "Objective and subjective reducers did not share one current source boundary"
        ),
        session_id=session_id,
    )


@app.get(
    "/diagnostics/objective/bootstrap",
    response_model=ObjectiveDiagnosticsBootstrap,
)
async def get_objective_diagnostics_bootstrap(
    request: Request,
    response: Response,
) -> ObjectiveDiagnosticsBootstrap:
    """Return one atomic objective reducer seed and its exact source cursors."""
    _assert_objective_diagnostics_access(request)
    response.headers["Cache-Control"] = "private, no-store"
    for _attempt in range(3):
        with event_stream.source_boundary():
            encounter = sim.encounter
            if encounter is None:
                raise _api_http_exception(
                    status_code=409,
                    code="objective_diagnostics_source_unavailable",
                    message="Objective diagnostics require an encounter",
                )
            source = _capture_objective_source_snapshot()
            world = build_current_objective_world(encounter=encounter)
            if (
                sim.encounter is encounter
                and event_stream.objective_source_snapshot_is_current(
                    source,
                    encounter,
                )
            ):
                return ObjectiveDiagnosticsBootstrap(
                    source_stream_id=source.source_stream_id,
                    generation_id=source.generation_id,
                    event_cursor=source.event_cursor,
                    combat_log_cursor=source.combat_log_cursor,
                    world=world,
                )
    raise _api_http_exception(
        status_code=409,
        code="objective_diagnostics_source_changed",
        message="Objective runtime changed while capturing its reducer seed",
    )


@app.get(
    "/diagnostics/objective/events",
    response_model=GameEventFramesResponse,
)
async def get_objective_diagnostics_events(
    request: Request,
    response: Response,
    from_cursor: int = Query(default=0, ge=0),
    through_cursor: Optional[int] = Query(default=None, ge=0),
    limit: Optional[int] = Query(default=None, ge=0),
    expected_source_stream_id: Optional[str] = None,
    expected_generation_id: Optional[str] = None,
) -> GameEventFramesResponse:
    """Return one exact contiguous all-phase objective event window."""
    _assert_objective_diagnostics_access(request)
    response.headers["Cache-Control"] = "private, no-store"
    source = _capture_objective_source_snapshot(
        from_event_cursor=from_cursor,
        through_event_cursor=through_cursor,
        event_limit=limit,
        expected_source_stream_id=expected_source_stream_id,
        expected_generation_id=expected_generation_id,
    )
    return _build_objective_event_window(
        source=source,
    )


@app.get(
    "/diagnostics/objective/combat-log",
    response_model=ObjectiveCombatLogFramesResponse,
)
async def get_objective_diagnostics_combat_log(
    request: Request,
    response: Response,
    from_cursor: int = Query(default=0, ge=0),
    through_cursor: Optional[int] = Query(default=None, ge=0),
    limit: Optional[int] = Query(default=None, ge=0),
    expected_source_stream_id: Optional[str] = None,
    expected_generation_id: Optional[str] = None,
) -> ObjectiveCombatLogFramesResponse:
    """Return one exact non-null objective combat-log source window."""
    _assert_objective_diagnostics_access(request)
    response.headers["Cache-Control"] = "private, no-store"
    source = _capture_objective_source_snapshot(
        from_combat_log_cursor=from_cursor,
        through_combat_log_cursor=through_cursor,
        combat_log_limit=limit,
        expected_source_stream_id=expected_source_stream_id,
        expected_generation_id=expected_generation_id,
    )
    try:
        return build_objective_combat_log_frames(
            source.combat_log_backfill_source,
            expected_source_stream_id=expected_source_stream_id,
            expected_generation_id=expected_generation_id,
        )
    except ObjectiveTimelineError as exc:
        raise _api_http_exception(
            status_code=409,
            code="objective_diagnostics_window_unavailable",
            message=str(exc),
            from_cursor=from_cursor,
            through_cursor=through_cursor,
        ) from exc


@app.get("/event-contract", response_model=EventContractSummary)
async def get_event_contract() -> EventContractSummary:
    """Return the identity and exhaustive discriminators of the event wire contract."""
    return EventContractSummary.model_validate(event_contract_summary())


@app.get("/diagnostics/objective/subscribe")
async def subscribe_objective_diagnostics(
    request: Request,
    since_event: int = Query(default=0, ge=0),
    since_log: int = Query(default=0, ge=0),
    expected_source_stream_id: Optional[str] = None,
    expected_generation_id: Optional[str] = None,
) -> StreamingResponse:
    """Stream only cold objective sync, event, and combat-log frames."""
    _assert_objective_diagnostics_access(request)
    event_stream.ensure_attached()
    encounter = sim.encounter
    if encounter is None:
        raise _api_http_exception(
            status_code=409,
            code="objective_diagnostics_source_unavailable",
            message="Objective diagnostics require an encounter",
        )
    subscription = None
    try:
        subscribed = event_stream.subscribe_with_objective_backfill(
            encounter,
            from_event_cursor=since_event,
            from_combat_log_cursor=since_log,
            expected_source_stream_id=expected_source_stream_id,
            expected_generation_id=expected_generation_id,
        )
        subscription = subscribed.subscription
        source = subscribed.source
        source_stream_id = source.source_stream_id
        generation_id = source.generation_id
        initial_events = _build_objective_event_window(
            source=source,
        )
        initial_logs = build_objective_combat_log_frames(
            source.combat_log_backfill_source,
            expected_source_stream_id=source_stream_id,
            expected_generation_id=generation_id,
        )
        sync = ObjectiveDiagnosticsSync(
            source_stream_id=source_stream_id,
            generation_id=generation_id,
            event_cursor=source.event_cursor,
            combat_log_cursor=source.combat_log_cursor,
        )
        initial_deliveries = _objective_backfill_deliveries(
            initial_events,
            initial_logs,
        )
    except CombatLogSourceError as exc:
        raise _api_http_exception(
            status_code=409,
            code=(
                "objective_diagnostics_source_changed"
                if "changed" in str(exc)
                else "objective_diagnostics_window_unavailable"
            ),
            message=str(exc),
            since_event=since_event,
            since_log=since_log,
        ) from exc
    except Exception:
        if subscription is not None:
            event_stream.unsubscribe(subscription)
        raise
    assert subscription is not None

    async def event_generator():
        last_event_cursor = sync.event_cursor
        last_combat_log_cursor = sync.combat_log_cursor
        try:
            yield format_sse(
                "sync",
                sync,
                make_stream_id(sync.event_cursor, sync.combat_log_cursor),
            )
            for event_name, frame in initial_deliveries:
                yield format_sse(
                    event_name,
                    frame,
                    make_stream_id(frame.event_cursor, frame.combat_log_cursor),
                )

            while True:
                current_encounter = sim.encounter
                if (
                    current_encounter is None
                    or str(current_encounter.uuid) != source_stream_id
                    or str(EventQueue.generation_id()) != generation_id
                ):
                    break
                try:
                    envelope = await asyncio.wait_for(subscription.get(), timeout=10.0)
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        break
                    continue

                envelope_type = envelope["event"]
                if envelope_type == "evicted":
                    break
                try:
                    if envelope_type == "game_event":
                        payload = envelope["data"]
                        if (
                            payload.source_stream_id != source_stream_id
                            or payload.generation_id != generation_id
                        ):
                            break
                        if payload.event_cursor <= last_event_cursor:
                            continue
                        if payload.event_cursor != last_event_cursor + 1:
                            break
                        frame = GameEventFrame(
                            source_stream_id=source_stream_id,
                            generation_id=generation_id,
                            event_index=payload.event_index,
                            event_cursor=payload.event_cursor,
                            combat_log_cursor=payload.combat_log_cursor,
                            event=payload.event.model_copy(deep=True),
                        )
                        last_event_cursor = frame.event_cursor
                        yield format_sse(
                            "game_event",
                            frame,
                            make_stream_id(
                                frame.event_cursor,
                                frame.combat_log_cursor,
                            ),
                        )
                    elif envelope_type == "combat_log":
                        payload = envelope["data"]
                        if (
                            payload.source_stream_id != source_stream_id
                            or payload.generation_id != generation_id
                        ):
                            break
                        if payload.combat_log_cursor <= last_combat_log_cursor:
                            continue
                        if (
                            payload.combat_log_cursor
                            != last_combat_log_cursor + 1
                            or payload.event_cursor > last_event_cursor
                        ):
                            break
                        live_source = CombatLogSourceWindow(
                            source_stream_id=source_stream_id,
                            generation_id=generation_id,
                            retained_from_cursor=0,
                            from_cursor=payload.combat_log_cursor - 1,
                            through_cursor=payload.combat_log_cursor,
                            total=payload.combat_log_cursor,
                            slots=(
                                CombatLogSourceSlot(
                                    source_stream_id=source_stream_id,
                                    generation_id=generation_id,
                                    combat_log_cursor=payload.combat_log_cursor,
                                    event_cursor=payload.event_cursor,
                                    entry=payload.entry,
                                    finalized=True,
                                    causal_cursor_exact=True,
                                ),
                            ),
                        )
                        frames = build_objective_combat_log_frames(
                            live_source,
                            expected_source_stream_id=source_stream_id,
                            expected_generation_id=generation_id,
                        )
                        frame = frames.frames[0]
                        last_combat_log_cursor = frame.combat_log_cursor
                        yield format_sse(
                            "combat_log",
                            frame,
                            make_stream_id(
                                frame.event_cursor,
                                frame.combat_log_cursor,
                            ),
                        )
                except (HTTPException, ObjectiveTimelineError):
                    break
        finally:
            event_stream.unsubscribe(subscription)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "private, no-store",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/replication/subscribe")
async def subscribe_replication(
    request: Request,
    session_id: str,
    expected_source_stream_id: str,
    expected_generation_id: str,
    expected_perspective_epoch_id: str,
    from_observation_cursor: int = Query(default=0, ge=0),
    from_combat_log_cursor: int = Query(default=0, ge=0),
):
    """Stream only canonical subjective sync, frame, and combat-log deliveries."""
    request_context = _resolve_replication_request(request, session_id)
    context = _replication_runtime_context(
        request_context,
        expected_source_stream_id=expected_source_stream_id,
        expected_generation_id=expected_generation_id,
        expected_perspective_epoch_id=expected_perspective_epoch_id,
    )
    try:
        snapshot = context.subscribe_with_backfill(
            from_observation_cursor=from_observation_cursor,
            from_combat_log_cursor=from_combat_log_cursor,
        )
    except (SubjectiveRuntimeError, SubjectiveJournalError) as exc:
        raise _replication_window_http_exception(exc) from exc
    subscription = snapshot.subscription
    initial_sync = snapshot.sync
    backfill_deliveries = snapshot.backfill_deliveries

    heartbeat_seconds = 10.0

    async def event_generator():
        try:
            queued_sync = await subscription.get()
            if not isinstance(queued_sync, SubjectiveSyncDelivery):
                return
            if queued_sync != initial_sync:
                return
            yield format_sse(
                "sync",
                queued_sync,
                _replication_stream_id(queued_sync),
            )

            for delivery in backfill_deliveries:
                event_name = (
                    "frame"
                    if isinstance(delivery, SubjectiveFrameDelivery)
                    else "combat_log"
                )
                yield format_sse(
                    event_name,
                    delivery,
                    _replication_stream_id(delivery),
                )

            while True:
                if await request.is_disconnected():
                    break
                try:
                    delivery = await asyncio.wait_for(
                        subscription.get(),
                        timeout=heartbeat_seconds,
                    )
                except asyncio.TimeoutError:
                    try:
                        refreshed_request = _resolve_replication_request(
                            request,
                            session_id,
                        )
                        refreshed = _replication_runtime_context(
                            refreshed_request,
                            expected_source_stream_id=context.protocol.source_stream_id,
                            expected_generation_id=context.protocol.generation_id,
                            expected_perspective_epoch_id=(
                                context.perspective.perspective_epoch_id
                            ),
                        )
                        if refreshed.partition_key != context.partition_key:
                            break
                    except HTTPException:
                        break
                    continue
                except SubjectiveSubscriptionClosedError:
                    break

                if not isinstance(
                    delivery,
                    (
                        SubjectiveFrameDelivery,
                        SubjectiveCombatLogDelivery,
                    ),
                ):
                    break
                yield format_sse(
                    delivery.kind,
                    delivery,
                    _replication_stream_id(delivery),
                )
        finally:
            context.unsubscribe(subscription)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "private, no-store",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )




def _action_error_detail(
    entity: Entity,
    available: AvailableActionsResult,
    code: str,
    message: str,
    **context: Any,
) -> dict:
    """Build structured action-error detail for API clients."""
    detail = {
        "code": code,
        "message": message,
        "entity_uuid": str(entity.uuid),
        "entity_name": entity.name,
        "valid_action_names": [
            action.template_name for action in available.all_actions
        ],
    }
    detail.update(context)
    return detail


def _action_execution_authorization(
    game: GameSession,
    entity_uuid: UUID,
) -> ActionExecutionAuthorization:
    """Return command authority independently from row mechanics."""
    encounter = game.encounter
    if encounter is None or encounter.state is not EncounterState.ACTIVE:
        return ActionExecutionAuthorization.ENCOUNTER_INACTIVE
    if encounter.turn_state is not TurnState.IN_PROGRESS:
        return ActionExecutionAuthorization.TURN_NOT_IN_PROGRESS
    if not game.is_entity_turn(entity_uuid):
        return ActionExecutionAuthorization.NOT_ACTIVE_TURN
    return ActionExecutionAuthorization.AUTHORIZED


@app.get("/entity/{entity_uuid}/available-actions", response_model=APIAvailableActions)
async def get_entity_available_actions(entity_uuid: str, session_id: str):
    """Get action affordances for an entity controlled by the session."""
    entity, game = validate_session_entity_inspection(session_id, entity_uuid)

    actions = get_available_actions(entity)

    _available_actions_cache[entity_uuid] = actions

    return serialize_available_actions(
        entity,
        actions,
        execution_authorization=_action_execution_authorization(
            game,
            entity.uuid,
        ),
    )




@app.get("/entity/{entity_uuid}/handlers", response_model=APIEntityHandlersResponse)
async def get_entity_handlers(entity_uuid: str, session_id: str) -> APIEntityHandlersResponse:
    """Get toggleable handlers for an entity controlled by the session."""
    entity = validate_session_action(session_id, entity_uuid)
    handlers = _serialize_entity_handlers(entity)
    return APIEntityHandlersResponse(entity_uuid=entity_uuid, handlers=handlers)


@app.post(
    "/entity/{entity_uuid}/handlers/{handler_uuid}/toggle",
    response_model=ToggleHandlerResponse,
)
async def toggle_entity_handler(
    entity_uuid: str,
    handler_uuid: str,
    request: ToggleHandlerRequest,
) -> ToggleHandlerResponse:
    """Toggle a handler's enabled state by exact UUID.

    Validates that the session owns the entity and it's their turn.
    """
    entity = validate_session_action(request.session_id, entity_uuid)
    parsed_handler_uuid = _parse_optional_uuid(handler_uuid, "handler_uuid")
    if parsed_handler_uuid is None:
        raise AssertionError("required handler UUID parsed as missing")

    found = entity.set_handler_enabled_by_uuid(
        parsed_handler_uuid,
        request.enabled,
    )
    if not found:
        raise _handler_http_exception(
            entity=entity,
            status_code=404,
            code="handler_not_found",
            message=f"Handler '{handler_uuid}' not found",
            handler_uuid=handler_uuid,
        )

    return ToggleHandlerResponse(
        success=True,
        handler_uuid=parsed_handler_uuid,
        enabled=request.enabled,
    )


@app.get("/entity/{entity_uuid}/equippable-items", response_model=APIEquippableItems)
async def get_equippable_items(entity_uuid: str, session_id: str) -> APIEquippableItems:
    """Get controlled inventory equip affordances grouped by valid slots."""
    entity = validate_session_action(session_id, entity_uuid)
    return APIEquippableItems(
        entity_uuid=entity_uuid,
        equippable=entity.get_equippable_items(),
    )


@app.post("/entity/{entity_uuid}/equip", response_model=EquipmentMutationResult)
async def equip_item(entity_uuid: str, request: EquipRequest):
    """Equip an item from inventory to a slot.

    Removes item from inventory, equips it. If slot is occupied, the old item
    goes to inventory (swap). Validates session ownership and turn.
    """
    entity = validate_session_action(request.session_id, entity_uuid)

    try:
        item_uuid_obj = UUID(request.item_uuid)
    except ValueError:
        raise _equipment_http_exception(
            entity=entity,
            status_code=400,
            code="invalid_item_uuid",
            message="Invalid item UUID format",
            item_uuid=request.item_uuid,
        )

    if not entity.inventory.has_item(item_uuid_obj):
        raise _equipment_http_exception(
            entity=entity,
            status_code=404,
            code="inventory_item_not_found",
            message="Item not found in inventory",
            item_uuid=request.item_uuid,
        )

    if not entity.is_inventory_item_equippable(item_uuid_obj):
        raise _equipment_http_exception(
            entity=entity,
            status_code=400,
            code="item_not_equippable",
            message="Item is not equippable",
            item_uuid=request.item_uuid,
        )

    parsed_slot = None
    if request.slot is not None:
        slot_str_map = _equipment_slot_map()
        parsed_slot = slot_str_map.get(request.slot)
        if parsed_slot is None:
            raise _equipment_http_exception(
                entity=entity,
                status_code=400,
                code="invalid_slot",
                message=f"Invalid slot: {request.slot}",
                item_uuid=request.item_uuid,
                slot=request.slot,
            )

    try:
        if not entity.equip_item(item_uuid_obj, parsed_slot):
            raise ValueError("Item could not be equipped")
    except ValueError as e:
        raise _equipment_http_exception(
            entity=entity,
            status_code=400,
            code="equipment_operation_failed",
            message=str(e),
            item_uuid=request.item_uuid,
            slot=request.slot,
        )

    return EquipmentMutationResult(
        success=True,
        message=f"Equipped item {request.item_uuid}",
        **action_cursor_fields(),
    )


@app.post("/entity/{entity_uuid}/unequip", response_model=EquipmentMutationResult)
async def unequip_item(entity_uuid: str, request: UnequipRequest):
    """Unequip an item from a slot to inventory.

    Validates session ownership and turn.
    """
    entity = validate_session_action(request.session_id, entity_uuid)

    slot_str_map = _equipment_slot_map()
    parsed_slot = slot_str_map.get(request.slot)
    if parsed_slot is None:
        raise _equipment_http_exception(
            entity=entity,
            status_code=400,
            code="invalid_slot",
            message=f"Invalid slot: {request.slot}",
            slot=request.slot,
        )

    unequipped = entity.unequip_item(parsed_slot)
    if unequipped is None:
        raise _equipment_http_exception(
            entity=entity,
            status_code=400,
            code="empty_or_canceled_slot",
            message="Slot is empty or unequip was canceled",
            slot=request.slot,
        )

    return EquipmentMutationResult(
        success=True,
        message=f"Unequipped {unequipped.name}",
        **action_cursor_fields(),
    )


@app.post("/action/end-turn", response_model=AdvanceEncounterResult)
async def end_human_turn(request: SimpleActionRequest):
    """End the session's entity turn and advance through autonomous turns."""
    return await _end_turn_and_advance(request.session_id, request.entity_uuid)


async def _end_turn_and_advance(
    session_id: str,
    entity_uuid: str,
    *,
    timing: Optional[_ServerCommandTiming] = None,
) -> AdvanceEncounterResult:
    """End one validated actor turn and advance to the next controller boundary."""
    started = time.perf_counter()
    entity = validate_session_action(session_id, entity_uuid)
    if timing is not None:
        timing.add("end_turn.validate_session_ms", started)

    if sim.encounter is None:
        raise _api_http_exception(
            status_code=400,
            code="no_active_encounter",
            message="No active encounter",
            session_id=session_id,
            entity_uuid=entity_uuid,
            entity_name=entity.name,
            **_session_context(),
            **_encounter_context(),
        )

    _available_actions_cache.clear()

    started = time.perf_counter()
    sim.encounter.complete_current_turn()
    if timing is not None:
        timing.add("end_turn.complete_current_turn_ms", started)

    if sim.activation_identity is not None:
        result = _scheduled_advance_result()
        _schedule_activated_game_coordinator()
        return result

    started = time.perf_counter()
    result = await advance_encounter(timing=timing)
    if timing is not None:
        timing.add("end_turn.advance_encounter_ms", started)

    return result

@app.post("/action/execute", response_model=ActionResult)
async def execute_action_by_index(request: ExecuteByIndexRequest):
    """Execute one public template-name and target-index request."""
    execution = await _execute_action_by_index_impl(request)
    return execution.response


async def _execute_action_by_index_impl(
    request: ExecuteByIndexRequest,
) -> _ActionExecutionResult:
    """Execute action by template name and target index.

    Enables 'attack 0', 'move 3' style commands from the available actions list.
    Uses cached available actions from the display call to avoid recomputing.
    """
    timing = _ServerCommandTiming("action_execute") if request.include_timing else None
    started = time.perf_counter()
    entity = validate_session_action(request.session_id, request.entity_uuid)
    if timing is not None:
        timing.add("validate_session_action_ms", started)

    started = time.perf_counter()
    available = _available_actions_cache.get(request.entity_uuid)
    if timing is not None:
        timing.add("available_actions_cache_lookup_ms", started)
    if available is None:
        started = time.perf_counter()
        available = get_available_actions(entity)
        if timing is not None:
            timing.add("get_available_actions_on_miss_ms", started)

    started = time.perf_counter()
    action_info = next(
        (a for a in available.all_actions if a.template_name == request.template_name),
        None,
    )
    if timing is not None:
        timing.add("find_action_info_ms", started)
    if action_info is None:
        raise HTTPException(
            status_code=400,
            detail=_action_error_detail(
                entity=entity,
                available=available,
                code="unknown_action",
                message=f"Unknown action: {request.template_name}",
            ),
        )

    selected_target = next(
        (
            target
            for target in action_info.valid_targets
            if target.index == request.target_index
        ),
        None,
    )
    if selected_target is None:
        raise HTTPException(
            status_code=400,
            detail=_action_error_detail(
                entity=entity,
                available=available,
                code="invalid_action_target",
                message=(
                    f"Target index {request.target_index} not valid for "
                    f"{request.template_name}"
                ),
            ),
        )

    try:
        started = time.perf_counter()
        dispatch = dispatch_available_action(
            entity,
            action_info=action_info,
            target=selected_target,
            extra_target_uuids=tuple(request.extra_target_uuids or ()),
            prefer_safe=request.prefer_safe,
            record_timing=(
                lambda phase, phase_started: timing.add(
                    f"execute_by_index.{phase}",
                    phase_started,
                )
            )
            if timing is not None
            else None,
        )
        event = dispatch.event
        if timing is not None:
            timing.add("execute_by_index_ms", started)
    except ValueError as e:
        if timing is not None:
            timing.add("execute_by_index_ms", started)
        raise HTTPException(
            status_code=400,
            detail=_action_error_detail(
                entity=entity,
                available=available,
                code="invalid_action_target",
                message=str(e),
            ),
        )

    started = time.perf_counter()
    _available_actions_cache.pop(request.entity_uuid, None)
    if timing is not None:
        timing.add("clear_available_actions_cache_ms", started)

    started = time.perf_counter()
    if sim.encounter:
        sim.encounter.check_deaths()
    if timing is not None:
        timing.add("check_deaths_ms", started)

    encounter_ended = sim.encounter.state != EncounterState.ACTIVE if sim.encounter else True
    updated_actions = None
    if request.return_available_actions and not encounter_ended and entity.has_hp:
        started = time.perf_counter()
        new_available = get_available_actions(entity)
        if timing is not None:
            timing.add("recompute_available_actions_ms", started)
        started = time.perf_counter()
        _available_actions_cache[request.entity_uuid] = new_available
        game = sim.game
        if game is None:
            raise RuntimeError(
                "validated action execution lost its active game session"
            )
        updated_actions = serialize_available_actions(
            entity,
            new_available,
            execution_authorization=_action_execution_authorization(
                game,
                entity.uuid,
            ),
        )
        if timing is not None:
            timing.add("serialize_available_actions_ms", started)

    started = time.perf_counter()
    cursor_fields = action_cursor_fields()
    if timing is not None:
        timing.add("final.action_cursor_fields_ms", started)

    if event is None:
        action_message = f"{request.template_name} could not be executed"
    elif event.status_message:
        action_message = event.status_message
    elif event.canceled:
        action_message = f"{request.template_name} was rejected"
    else:
        action_message = f"{request.template_name} executed"

    started = time.perf_counter()
    action_result = ActionResult(
        success=not event.canceled if event else False,
        message=action_message,
        event_type=request.template_name.lower(),
        outcome_code=event.outcome_code if event else None,
        turn_continues=not encounter_ended and entity.has_hp,
        encounter_ended=encounter_ended,
        available_actions=updated_actions,
        server_timing=None,
        **cursor_fields,
    )
    if timing is not None:
        timing.add("build_action_result_model_ms", started)
        action_result.server_timing = APIServerTiming.model_validate(timing.payload())
    return _ActionExecutionResult(
        response=action_result,
        movement_termination_reason=dispatch.movement_termination_reason,
        movement_revalidation_reason=dispatch.movement_revalidation_reason,
    )


@app.post("/action/position/preview")
async def preview_position_action(request: PositionPreviewRequest) -> AoEPreviewResult:
    """Preview AoE at a position: returns affected cells and entities without executing."""
    entity = validate_session_action(request.session_id, request.entity_uuid)

    template = entity.get_action_template(request.action_name)
    if template is None:
        return AoEPreviewResult(success=False, message=f"Unknown action: {request.action_name}")

    if template.target_type != TargetType.POSITION_AOE or template.aoe_shape is None:
        return AoEPreviewResult(success=False, message=f"{request.action_name} is not a position AoE action")

    pos = (request.position[0], request.position[1])
    grid = get_map()

    shape = template.aoe_shape.model_copy(update={'target': pos})
    shape.compute_subjective(
        entity.position, entity.senses,
        fov_cache={}, barrier_positions=grid.get_barrier_positions(),
        caster_uuid=entity.uuid,
    )

    affected_uuids = list(shape.affected_entity_uuids)

    if not template.include_self:
        affected_uuids = [uid for uid in affected_uuids if uid != entity.uuid]

    vtf = template.valid_target_filter
    if vtf != "all":
        filtered = []
        for uid in affected_uuids:
            ent = Entity.get(uid)
            if ent:
                if vtf == "enemies" and entity.is_enemy(ent):
                    filtered.append(uid)
                elif vtf == "allies" and entity.is_ally(ent):
                    filtered.append(uid)
                elif vtf == "self_or_allies":
                    if uid == entity.uuid or entity.is_ally(ent):
                        filtered.append(uid)
        affected_uuids = filtered

    if not template.include_dead:
        affected_uuids = [uid for uid in affected_uuids if (ent := Entity.get(uid)) and ent.has_hp]

    affected_names = []
    for uid in affected_uuids:
        ent = Entity.get(uid)
        if ent:
            affected_names.append(ent.name or "Unknown")

    return AoEPreviewResult(
        success=True,
        affected_positions=list(shape.affected_positions),
        affected_entity_names=affected_names,
        affected_count=len(affected_uuids),
    )


def _set_game_creation_member_controller(
    encounter: Encounter,
    entity: Entity,
) -> None:
    """Install the deterministic unclaimed controller for one exact member."""
    encounter.set_controller_for(
        entity.uuid,
        PassController(source_entity_uuid=entity.uuid),
    )
    return None




def _game_creation_roster_results(
    assembled: AssembledEncounter,
) -> tuple[GameCreationRosterResult, ...]:
    """Serialize exact member sources and runtime identities."""
    results: list[GameCreationRosterResult] = []
    for roster_slot in assembled.recipe.roster_slots:
        assignments: list[GameCreationEntityAssignment] = []
        for member in roster_slot.roster.members:
            address = (roster_slot.roster_slot_id, member.member_id)
            entity = assembled.entities_by_member_address[address]
            assignments.append(GameCreationEntityAssignment(
                member_id=member.member_id,
                entity_uuid=str(entity.uuid),
                entity_name=entity.name,
                faction=entity.faction,
                participant_name=roster_slot.participant_name,
            ))
        results.append(GameCreationRosterResult(
            roster_slot_id=roster_slot.roster_slot_id,
            roster_id=roster_slot.roster.roster_id,
            roster_recipe_digest=roster_slot.roster.recipe_digest,
            title=roster_slot.roster.title,
            entity_assignments=tuple(assignments),
        ))
    return tuple(results)




@app.get("/game-creation/catalog", response_model=GameCreationCatalogResponse)
async def get_game_creation_catalog() -> GameCreationCatalogResponse:
    """Return canonical scenarios and formations."""
    return build_game_creation_catalog()


def _validate_game_creation_protocol_identity(
    request: GameCreationPreviewRequest,
) -> None:
    content_digest = (
        SERVER_CONTENT_SYSTEM_RUNTIME.require().content_set_digest
    )
    if request.expected_content_set_digest != content_digest:
        raise _api_http_exception(
            status_code=409,
            code="game_creation_content_changed",
            message="Installed content changed after encounter normalization",
            expected_content_set_digest=request.expected_content_set_digest,
            current_content_set_digest=content_digest,
        )
    if request.expected_ruleset_digest != DEFAULT_CHARACTER_RULESET_DIGEST:
        raise _api_http_exception(
            status_code=409,
            code="game_creation_ruleset_changed",
            message="Character rules changed after encounter normalization",
            expected_ruleset_digest=request.expected_ruleset_digest,
            current_ruleset_digest=DEFAULT_CHARACTER_RULESET_DIGEST,
        )


@app.post(
    "/game-creation/compose",
    response_model=GameCreationComposeResponse,
)
async def compose_game_creation(
    request: GameCreationComposeRequest,
) -> GameCreationComposeResponse:
    """Normalize authored ids, then project that exact recipe."""
    try:
        recipe, compatibility = normalize_encounter_recipe(request)
        content_digest = (
            SERVER_CONTENT_SYSTEM_RUNTIME.require().content_set_digest
        )
        preview = await asyncio.to_thread(
            build_game_creation_encounter_visual_preview,
            recipe,
            expected_content_set_digest=content_digest,
            expected_ruleset_digest=DEFAULT_CHARACTER_RULESET_DIGEST,
        )
        return GameCreationComposeResponse(
            content_set_digest=content_digest,
            ruleset_digest=DEFAULT_CHARACTER_RULESET_DIGEST,
            recipe=recipe,
            compatibility=compatibility,
            preview=preview,
        )
    except GameCreationCompositionError as exc:
        raise _api_http_exception(
            status_code=400,
            code="game_creation_composition_invalid",
            message=str(exc),
        ) from exc
    except GameCreationPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail(),
        ) from exc


@app.post(
    "/game-creation/preview",
    response_model=GameCreationEncounterVisualPreviewResponse,
)
async def preview_game_creation(
    request: GameCreationPreviewRequest,
) -> GameCreationEncounterVisualPreviewResponse:
    """Project an already-normalized recipe without mutating the live engine."""
    _validate_game_creation_protocol_identity(request)
    try:
        return await asyncio.to_thread(
            build_game_creation_encounter_visual_preview,
            request.recipe,
            expected_content_set_digest=request.expected_content_set_digest,
            expected_ruleset_digest=request.expected_ruleset_digest,
        )
    except GameCreationPreviewError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail(),
        ) from exc


@app.post(
    "/game-creation/start",
    response_model=GameCreationStartResponse,
    dependencies=[Depends(_serialize_world_replacement)],
)
async def start_created_game(
    creation: GameCreationStartRequest,
) -> GameCreationStartResponse:
    """Atomically assemble one authored encounter recipe."""

    _validate_game_creation_protocol_identity(creation)
    await prepare_new_game_start()
    try:
        assembled = prepare_encounter_recipe(creation.recipe)
        sim.encounter = assembled.encounter
        sim.paused = True
        sim.encounter.clear_combat_log()
        game_summary_store.reset()
        event_stream.ensure_attached()
        event_stream.install_prepared_source(sim.encounter)
        canonical_subjective_replication_runtime.ensure_attached()
        _ensure_game_terminal_callback()
        game = sim.create_game_session(sim.encounter)
        for roster_slot in creation.recipe.roster_slots:
            for member in roster_slot.roster.members:
                address = (roster_slot.roster_slot_id, member.member_id)
                _set_game_creation_member_controller(
                    sim.encounter,
                    assembled.entities_by_member_address[address],
                )

        response = GameCreationStartResponse(
            recipe_digest=creation.recipe.recipe_digest,
            encounter_uuid=str(sim.encounter.uuid),
            game_id=str(game.game_id),
            encounter_name=sim.encounter.name,
            compatibility=assembled.compatibility,
            rosters=_game_creation_roster_results(assembled),
        )
        sim.current_creation = response
        return response
    except (IncompatibleEncounterError, ValueError) as exc:
        await _abort_failed_game_start()
        raise _api_http_exception(
            status_code=400,
            code="game_creation_assembly_failed",
            message=str(exc),
            recipe_digest=creation.recipe.recipe_digest,
        ) from exc
    except BaseException:
        await _abort_failed_game_start()
        raise


@app.post(
    "/game-creation/activate",
    response_model=GameCreationActivateResponse,
    dependencies=[Depends(_serialize_world_replacement)],
)
async def activate_created_game(
    request: Request,
    activation: GameCreationActivateRequest,
) -> GameCreationActivateResponse:
    """Release a prepared encounter from one exact replication bootstrap."""
    encounter = sim.encounter
    game = sim.game
    creation = sim.current_creation
    if encounter is None or game is None or creation is None:
        raise _api_http_exception(
            status_code=409,
            code="prepared_game_unavailable",
            message="No prepared game is available for activation",
        )

    request_context = _resolve_replication_request(request, activation.session_id)
    if request_context.session_id not in game.players:
        raise _api_http_exception(
            status_code=403,
            code="activation_session_not_joined",
            message="Activation requires a session joined to the prepared game",
            session_id=activation.session_id,
            game_id=str(game.game_id),
        )
    context = _replication_runtime_context(
        request_context,
        expected_source_stream_id=activation.expected_source_stream_id,
        expected_generation_id=activation.expected_generation_id,
        expected_perspective_epoch_id=activation.expected_perspective_epoch_id,
    )
    context.bootstrap()

    identity = _GameActivationIdentity(
        game_id=game.game_id,
        session_id=request_context.session_id,
        source_stream_id=activation.expected_source_stream_id,
        generation_id=activation.expected_generation_id,
        perspective_epoch_id=activation.expected_perspective_epoch_id,
    )
    existing = sim.activation_identity
    if existing is not None:
        if existing != identity:
            raise _api_http_exception(
                status_code=409,
                code="game_activation_identity_changed",
                message="The prepared game was activated by another replication identity",
                game_id=str(game.game_id),
            )
        return GameCreationActivateResponse(
            status="already_active",
            game_id=str(game.game_id),
            encounter_uuid=str(encounter.uuid),
        )

    if encounter.state != EncounterState.NOT_STARTED:
        raise _api_http_exception(
            status_code=409,
            code="game_activation_state_invalid",
            message="Encounter crossed its start boundary without canonical activation",
            game_id=str(game.game_id),
            encounter_state=encounter.state.value,
        )

    sim.activation_identity = identity
    sim.paused = False
    try:
        encounter.start_encounter()
        if not _schedule_activated_game_coordinator():
            raise RuntimeError("Activated game coordinator could not be scheduled")
    except BaseException:
        sim.activation_identity = None
        sim.paused = True
        raise

    return GameCreationActivateResponse(
        status="activated",
        game_id=str(game.game_id),
        encounter_uuid=str(encounter.uuid),
    )


def kill_process_on_port(port: int) -> bool:
    """Gracefully stop listeners so they can retire their owned children."""
    if sys.platform == "win32":
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            check=False,
        )
        pids = {
            int(parts[-1])
            for line in result.stdout.splitlines()
            if f":{port}" in line and "LISTENING" in line
            for parts in [line.split()]
            if parts and parts[-1].isdigit()
        }
    else:
        result = subprocess.run(
            ["lsof", f"-tiTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            check=False,
        )
        pids = {
            int(line)
            for line in result.stdout.splitlines()
            if line.strip().isdigit()
        }
    if not pids:
        return False
    if os.getpid() in pids:
        raise RuntimeError(
            f"Refusing to stop the current server process on port {port}"
        )

    for pid in pids:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(pid)],
                capture_output=True,
                text=True,
                check=False,
            )
        else:
            os.kill(pid, signal.SIGTERM)

    deadline = time.monotonic() + 5.0
    remaining = set(pids)
    while remaining and time.monotonic() < deadline:
        for pid in tuple(remaining):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                remaining.discard(pid)
            except PermissionError:
                pass
        if remaining:
            time.sleep(0.05)
    if remaining:
        raise RuntimeError(
            "Listener did not shut down gracefully; refusing to orphan owned "
            f"server processes for PID(s): {sorted(remaining)}"
        )
    print(f"Stopped listener(s) {sorted(pids)} on port {port}")
    return True


def run_server(host: str = "0.0.0.0", port: int = 8000, force: bool = False) -> None:
    """Run the event server."""
    if force:
        kill_process_on_port(port)

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        timeout_graceful_shutdown=2,
    )
    try:
        uvicorn.Server(config).run()
    except KeyboardInterrupt:
        pass


def main(argv: Sequence[str] | None = None) -> None:
    """Parse the shared server CLI and run the currently composed application."""
    parser = argparse.ArgumentParser(description="D&D Engine Event Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--force", "-f", action="store_true", help="Kill existing process on port")
    args = parser.parse_args(argv)

    run_server(host=args.host, port=args.port, force=args.force)


if __name__ == "__main__":
    main()
