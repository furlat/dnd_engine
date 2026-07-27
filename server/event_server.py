"""
Canonical HTTP/SSE server for game control, replication, and diagnostics.

This server:
1. Hooks into EventQueue to capture all events
2. Projects private player replication journals
3. Exposes authorized objective diagnostics separately
4. Controls simulation (start/pause/resume/step)

Usage:
    # Start the canonical game server
    uv run python -m server.event_server

    # Or import the same app programmatically
    from server.event_server import run_server
    run_server(host="0.0.0.0", port=8000)
"""

import argparse
import asyncio
import hmac
import logging
import os
import signal
import subprocess
import sys
import time
import traceback
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Literal, Optional, Sequence
from uuid import UUID
from contextlib import asynccontextmanager, nullcontext

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
    EventType,
)
from dnd.core.gridmap import get_map
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.pack_loader import (
    ENGINE_CONTENT_API_VERSION,
    LoadedContentSystem,
)
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.runtime_reset import reset_engine_runtime
from dnd.entity import Entity
from dnd.encounter import Encounter, EncounterState, TurnState
from dnd.scenarios.evaluation.assembler import (
    IncompatibleScenarioError,
    prepare_composed_scenario,
    prepare_legacy_scenario,
)
from dnd.scenarios.evaluation.combatant_catalog import (
    get_combatant_configuration,
)
from dnd.scenarios.evaluation.compatibility import CompatibilityReport
from dnd.scenarios.evaluation.legacy_recipes import LEGACY_RECIPES, get_legacy_recipe
from dnd.ai.instrumentation import (
    AIInstrumentation,
    BoundedAIInstrumentationSink,
)
from dnd.ai.policy import PolicyDescriptor
from dnd.ai.registry import UnknownPolicyError
from dnd.ai.runtime.controller import NativeAIController
from dnd.controller import (
    Controller,
    ControllerExecutionMode,
    ControllerStepResult,
    HumanController,
)
from dnd.action_dispatch import dispatch_available_action
from dnd.actions_functional import get_available_actions
from server.runtime_performance import latency_sensitive_gc
from dnd.core.base_actions import (
    AvailableActionsResult,
    AvailableHandlerInfo,
    TargetType,
)
from dnd.core.action_execution import movement_continuation_scope

from server.api_models import (
    APIAvailableActions, APIServerTiming,
    SimpleActionRequest, ActionResult, AoEPreviewResult,
    CreateSessionRequest, CreateSessionResponse, SessionPingResponse,
    JoinGameRequest, JoinGameResponse,
    AIExecutionKind,
    AIProviderCatalogEntry, AIProviderCatalogResponse,
    AIProviderDeleteResponse, AIProviderRegistrationRequest,
    GameCreationAIPolicyOption,
    GameCreationCatalogResponse, GameCreationComposedScenario,
    GameCreationPreflightRequest, GameCreationPresetScenario,
    GameCreationEntityAssignment, GameCreationSideRequest, GameCreationSideResult,
    GameCreationActivateRequest, GameCreationActivateResponse,
    GameCreationStartRequest, GameCreationStartResponse,
    EventContractSummary,
    PositionPreviewRequest, ExecuteByIndexRequest,
    ToggleHandlerRequest,
    APIEquippableItems, APIEntityHandlersResponse,
    EquipRequest, UnequipRequest, EquipmentMutationResult, ToggleHandlerResponse,
    AdvanceEncounterResult,
    AgentSessionEntityRow, AgentSessionListResponse, AgentSessionRow,
    TakeoverClaimResponse, TakeoverEntityRow, TakeoverHeartbeatResponse, TakeoverListResponse,
    TakeoverReleaseResponse, TakeoverRequest,
    SpellCatalogResponse,
    MapEditorCatalog, MapEditorCreateMapRequest, MapEditorLightResponse, MapEditorMapSnapshot,
    MapEditorObjectDeleteRequest, MapEditorObjectPlaceRequest, MapEditorTilePatchRequest, MapEditorVisibilityResponse,
    MapEditorWalkabilityResponse, MapEditorSaveMapRequest, MapEditorSavedMapDocument,
    MapEditorSavedMapList, MapEditorSavedMapMetadata,
    ServerCapabilitiesResponse,
    StandaloneGameSessionSummary, StandaloneGameStatusResponse,
)
from server.ai_policy_composition import (
    DEFAULT_NATIVE_POLICY_ID,
    SERVER_NATIVE_POLICY_REGISTRY,
)
from server.content_catalog import (
    ContentCatalogResponse,
    ContentManifestResponse,
    build_content_manifest,
    build_public_content_catalog,
    content_response_etag,
)
from server.character_directory_routes import create_character_directory_router
from server.character_directory_contracts import (
    AdminCharacterAdvancementAwardRequest,
    CharacterAdvancementResponse,
    StandaloneLocalProfileResponse,
)
from server.character_deployment import build_character_deployment_snapshot
from server.character_settlement import project_terminal_character_holdings
from server.character_directory_service import (
    CharacterDirectoryBuildError,
    CharacterDirectoryOwnershipError,
    CharacterDirectoryService,
)
from server.game_directory.errors import (
    CapabilityError,
    ConflictError,
    DirectoryError,
    NotFoundError,
)
from server.game_directory.contracts import DirectoryEventRecord
from server.game_directory.local_profiles import (
    LocalProfileHandle,
    LocalProfileManager,
)
from server.local_game_lifecycle import StandaloneLocalGameCoordinator
from server.game_history import (
    GameHistoryQueryService,
    create_game_history_router,
)
from server.directory_event_stream import (
    DirectoryEventStream,
    create_directory_event_stream_router,
)
from server.external_ai_protocol import (
    EXTERNAL_AI_PROTOCOL_HASH,
    EXTERNAL_AI_PROTOCOL_VERSION,
)
from server.registered_ai_controller import RegisteredAIController
from server.registered_ai_provider import (
    RegisteredAIProviderBusyError,
    RegisteredAIProviderCapacityError,
    RegisteredAIProviderCatalog,
    RegisteredAIProviderCollisionError,
    RegisteredAIProviderError,
    RegisteredAIProviderInfo,
    RegisteredAIProviderNotFoundError,
    RegisteredAIProviderProtocolError,
    RegisteredAIProviderTransportError,
)
from server.world_contracts import APIFloorObject
from server.mapeditor_support import (
    apply_tile_patches,
    build_catalog,
    create_editor_map,
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
)
from server.request_timing import RequestTimingMiddleware
from server.hosted_worker import (
    HostedWorkerAssignment,
    HostedWorkerReadiness,
)
from dnd.core.content.character_deployment import CharacterDeploymentSnapshot
from server.spell_catalog import build_spell_catalog
from server.game_creation_catalog import (
    GameCreationCatalogError,
    build_game_creation_catalog,
    preflight_game_creation as run_game_creation_preflight,
)
from server.event_stream import (
    BoundedSubscription,
    EvictedPayload,
    ObjectiveSourceSnapshot,
    event_stream,
    format_sse,
    make_stream_id,
)
from server.event_contract import (
    event_contract_summary,
)
from server.agent_event_stream import agent_event_stream
from server.gauntlet_event_stream import gauntlet_event_stream
from server.game_summary_store import WorkerSummaryEvidence, game_summary_store
from server.objective_replay import ObjectiveReplayBundle
from server.player_replay import SubjectivePlayerReplayArchive
from server.player_replay_capture import subjective_replay_capture_store
from server.worker_player_replay import (
    WorkerPlayerReplayError,
    WorkerPlayerReplayNotReady,
    build_worker_subjective_replays,
)
from server.worker_replay import WorkerReplayError, build_worker_objective_replay
from server.worker_terminal_spool import WorkerTerminalSpool
from server.action_serialization import serialize_available_actions
from server.session import (
    SessionManager, GameSession,
    PlayerSession, PlayerType, get_session_manager
)
from server.replication_perspective import perspective_epoch_registry
from server.agent_protocol.objective_diagnostics import (
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
from server.runtime_authority import (
    RuntimeAuthorityError,
    RuntimeProjectionAuthority,
    RuntimeScope,
    parse_runtime_projection_authority,
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
from server.agent_protocol.gauntlet import (
    GauntletEventIngestRequest,
    GauntletSummary,
    apply_gauntlet_latency_audit,
    project_live_watcher_state,
    project_watcher_state,
)
from server.ai_takeover_manager import AITakeoverManager, TakeoverClaim, TakeoverError
from dnd.ai.contracts.observation import (
    ObservationFrame,
    ObservationFramesResponse,
    ObservationSnapshot,
)
from server.agent_runtime.observation_projector import (
    ObservationAccessError,
    ObservationOwnershipBoundary,
    append_command_result_frame,
    append_decision_epoch_frame,
    append_epoch_clear_frame,
    build_observation_snapshot,
    clear_observation_projection_cache,
    get_observation_cursor,
    get_materialized_observation_world,
    iter_observation_frames,
    observation_wakeup_stream,
    prepare_observation_ownership_change,
    publish_observation_ownership_changes,
)
from server.agent_protocol.telemetry import PolicySourceManifest
from dnd.ai.contracts.control import (
    ActionAffordance,
    ActionResolutionStatus,
    AgentEndTurnCommandRequest,
    AgentExecuteCommandRequest,
    CommandResult,
    CommandResultStatus,
    DecisionEpoch,
    DecisionEpochReason,
    END_TURN_ROW_ID,
)
from dnd.ai.contracts.semantics import ActionTag
from server.agent_runtime.movement_revalidation import (
    SessionMovementContinuationGuard,
)
from dnd.ai.runtime.decision_epoch import (
    ActionExecutionBinding,
    DecisionEpochExecutionAuthority,
    build_decision_epoch as build_subjective_decision_epoch,
    clear_epoch_value_caches,
)
from server.agent_protocol.telemetry import (
    AgentEventHistoryResponse,
    AgentEventIngestRequest,
)

_available_actions_cache: Dict[str, AvailableActionsResult] = {}
_last_published_epoch_by_session: Dict[str, str] = {}
_current_epoch_by_session: Dict[str, DecisionEpoch] = {}
_execution_authority_by_epoch_id: Dict[str, DecisionEpochExecutionAuthority] = {}
ai_takeover_manager = AITakeoverManager()


@dataclass
class _ServerCommandTiming:
    """Low-overhead phase timing for one server-side AI command."""

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


def _prefixed_timing_recorder(
    timing: Optional[_ServerCommandTiming],
    prefix: str,
) -> Optional[Callable[[str, float], None]]:
    """Return a timing callback that records observation subphases."""
    if timing is None or not timing.diagnostics_enabled:
        return None

    def record(phase: str, started_at: float) -> None:
        timing.add(f"{prefix}.{phase}", started_at)

    return record


async def _first_subscription_envelope(
    subscriptions: list[BoundedSubscription],
    *,
    timeout: float,
) -> Optional[dict[str, Any]]:
    """Return the first live SSE envelope while cleaning up losing wait tasks."""
    tasks = [asyncio.create_task(subscription.get()) for subscription in subscriptions]
    try:
        done, _pending = await asyncio.wait(
            set(tasks),
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done:
            return None
        return next(iter(done)).result()
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


def clear_subjective_projection_state() -> None:
    """Clear all process-local subjective projection and replay identity state."""
    clear_observation_projection_cache()
    clear_epoch_value_caches()
    perspective_epoch_registry.clear_all()
    canonical_subjective_replication_runtime.clear_all()
    subjective_replay_capture_store.clear()
    _last_published_epoch_by_session.clear()
    _current_epoch_by_session.clear()
    _execution_authority_by_epoch_id.clear()


@dataclass(frozen=True)
class _GameActivationIdentity:
    """Exact replication identity that released one prepared game."""

    game_id: UUID
    session_id: UUID
    source_stream_id: str
    generation_id: str
    perspective_epoch_id: str


def _store_current_epoch(session_id: str, epoch: DecisionEpoch) -> None:
    """Store one active epoch and release superseded private authority."""
    previous = _current_epoch_by_session.get(session_id)
    _current_epoch_by_session[session_id] = epoch
    if previous is not None and previous.epoch_id != epoch.epoch_id:
        _execution_authority_by_epoch_id.pop(previous.epoch_id, None)


def _forget_current_epoch(session_id: str) -> Optional[DecisionEpoch]:
    """Forget one active epoch and its private execution bindings."""
    epoch = _current_epoch_by_session.pop(session_id, None)
    if epoch is not None:
        _execution_authority_by_epoch_id.pop(epoch.epoch_id, None)
    return epoch


class SimulationState:
    """Hold mutable server simulation state.

    Attributes:
        encounter: Active encounter, if one has been created.
        combat_task: Background task advancing AI combat, if running.
        paused: Whether automatic simulation advancement is paused.
        turn_delay: Delay in seconds between automatic turns.
        auto_run_ai: Whether AI turns should advance automatically.
        _session_manager: Session registry backing game/player sessions.
        _game_session: Active game session for the current encounter.
    """

    def __init__(self) -> None:
        self.encounter: Optional[Encounter] = None
        self.combat_task: Optional[asyncio.Task] = None
        self.paused: bool = True
        self.turn_delay: float = 0.0
        self.auto_run_ai: bool = True
        self._session_manager = get_session_manager()
        self._game_session: Optional[GameSession] = None
        self.current_creation: Optional[GameCreationStartResponse] = None
        self.activation_identity: Optional[_GameActivationIdentity] = None
        self.native_ai_controllers: list[NativeAIController] = []
        self.registered_ai_controllers: list[RegisteredAIController] = []
        self.native_ai_instrumentation = BoundedAIInstrumentationSink()

    @property
    def game(self) -> Optional[GameSession]:
        """Get the active game session."""
        return self._game_session

    @property
    def waiting_for_human(self) -> bool:
        """Check if waiting for a human/codex player (derived from session state)."""
        if not self._game_session or not self.encounter:
            return False
        active_player = self._game_session.active_player
        if not active_player:
            return False
        return active_player.player_type in (PlayerType.HUMAN, PlayerType.CODEX)

    @property
    def human_entity_uuid(self) -> Optional[UUID]:
        """Get the active entity UUID if it's a human/codex turn."""
        if not self._game_session:
            return None
        return self._game_session.active_entity_uuid

    def create_game_session(
        self,
        encounter: Encounter,
        *,
        game_id: UUID | None = None,
    ) -> GameSession:
        """Create a new game session for the encounter."""
        self._game_session = self._session_manager.create_game(
            encounter,
            game_id=game_id,
        )
        return self._game_session

    def get_session_manager(self) -> SessionManager:
        """Get the session manager."""
        return self._session_manager

    def reset(self) -> None:
        """Reset mutable server session state for a fresh game scene."""
        if self.combat_task is not None and not self.combat_task.done():
            self.combat_task.cancel()
        if self.registered_ai_controllers:
            raise RuntimeError(
                "registered AI controllers require asynchronous teardown "
                "before synchronous simulation reset"
            )
        self.close_native_ai_controllers()
        self.native_ai_instrumentation = BoundedAIInstrumentationSink()
        ai_takeover_manager.clear(self.encounter, self._game_session)
        clear_subjective_projection_state()
        agent_event_stream.clear_all()
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

    def close_native_ai_controllers(self) -> None:
        """Close every side assignment once, including prepared games."""
        for controller in self.native_ai_controllers:
            controller.close()
        self.native_ai_controllers.clear()

    async def close_registered_ai_controllers(self) -> None:
        """Close every remote assignment before releasing engine ownership."""
        controllers = tuple(self.registered_ai_controllers)
        self.registered_ai_controllers.clear()
        first_error: BaseException | None = None
        for controller in controllers:
            try:
                await controller.close()
            except BaseException as error:
                if first_error is None:
                    first_error = error
        if first_error is not None:
            raise RuntimeError(
                "registered AI controller teardown failed"
            ) from first_error

sim = SimulationState()

native_policy_registry = SERVER_NATIVE_POLICY_REGISTRY


def _new_registered_ai_provider_catalog() -> RegisteredAIProviderCatalog:
    """Create one process-lifetime provider catalog with native IDs reserved."""
    return RegisteredAIProviderCatalog(
        reserved_policy_ids={
            descriptor.policy_id
            for descriptor in native_policy_registry.descriptors()
        },
    )


registered_ai_provider_catalog = _new_registered_ai_provider_catalog()
_ai_provider_admin_token: Optional[str] = os.getenv(
    "DND_AI_PROVIDER_ADMIN_TOKEN"
)


def configure_ai_provider_admin_token(token: Optional[str]) -> None:
    """Configure the deployment-only bearer used by provider admin routes."""
    global _ai_provider_admin_token
    _ai_provider_admin_token = token


def _active_registered_ai_provider_catalog() -> RegisteredAIProviderCatalog:
    """Return an open catalog, recreating it after a completed app lifespan."""
    global registered_ai_provider_catalog
    if registered_ai_provider_catalog.closed:
        registered_ai_provider_catalog = _new_registered_ai_provider_catalog()
    return registered_ai_provider_catalog


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

_policy_source_manifest: Optional[PolicySourceManifest] = None
_local_terminal_tasks: set[asyncio.Task[None]] = set()


def configure_policy_source_manifest(
    manifest: Optional[PolicySourceManifest],
) -> None:
    """Install opaque client-owned policy diagnostics for the read-only API.

    The server deliberately does not discover or read client source files. A
    composition root that includes an AI client may build this manifest and
    supply it explicitly; a server-only deployment leaves it unset.

    Args:
        manifest: Validated client manifest, or ``None`` to remove it.
    """
    global _policy_source_manifest
    _policy_source_manifest = manifest


def _active_local_game_coordinator(
) -> StandaloneLocalGameCoordinator | None:
    """Return standalone durable lifecycle ownership when installed."""

    coordinator = getattr(app.state, "local_game_coordinator", None)
    return (
        coordinator
        if isinstance(coordinator, StandaloneLocalGameCoordinator)
        else None
    )


def _publish_standalone_directory_events(
    request: Request | None = None,
) -> None:
    """Fan out every newly durable local-profile directory event."""

    owner_app = app if request is None else request.app
    stream = getattr(owner_app.state, "directory_stream", None)
    if isinstance(stream, DirectoryEventStream):
        stream.publish_pending()


def _ensure_local_terminal_callback() -> None:
    """Attach the ordered batch trigger and exact replay-ready retry signal."""

    EventQueue.remove_on_event_batch_callback(_on_local_terminal_event_batch)
    EventQueue.add_on_event_batch_callback(_on_local_terminal_event_batch)
    subjective_replay_capture_store.remove_source_closed_listener(
        _on_subjective_replay_source_closed
    )
    subjective_replay_capture_store.add_source_closed_listener(
        _on_subjective_replay_source_closed
    )


def _on_local_terminal_event_batch(events: Sequence[Event]) -> None:
    """Commit terminal persistence after every causal observer has drained."""

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
    if _active_local_game_coordinator() is not None:
        try:
            _publish_local_terminal_game(encounter_end.encounter_uuid)
        except BaseException:
            logger.exception(
                "Standalone terminal publication failed for encounter %s",
                encounter_end.encounter_uuid,
            )
    if os.environ.get("DND_GAME_WORKER") == "1":
        try:
            _publish_hosted_terminal_ready(encounter_end.encounter_uuid)
        except BaseException:
            logger.exception(
                "Hosted terminal ready publication failed for encounter %s",
                encounter_end.encounter_uuid,
            )


def _on_subjective_replay_source_closed(source_stream_id: str) -> None:
    """Retry local terminal publication when the last reducer segment seals."""

    try:
        encounter_uuid = UUID(source_stream_id)
    except ValueError:
        return
    try:
        _publish_local_terminal_game(encounter_uuid)
    except BaseException:
        logger.exception(
            "Standalone terminal publication failed after subjective replay "
            "closure for encounter %s",
            encounter_uuid,
        )
    if os.environ.get("DND_GAME_WORKER") == "1":
        try:
            _publish_hosted_terminal_ready(encounter_uuid)
        except BaseException:
            logger.exception(
                "Hosted terminal ready publication failed after subjective "
                "replay closure for encounter %s",
                encounter_uuid,
            )


def _publish_local_terminal_game(encounter_uuid: UUID) -> bool:
    """Freeze and publish the in-process terminal evidence through one path."""

    coordinator = _active_local_game_coordinator()
    current = None if coordinator is None else coordinator.current
    encounter = Encounter.get(encounter_uuid)
    if coordinator is None or current is None or encounter is None:
        return False
    evidence = game_summary_store.get_evidence(current.game.game_id)
    capture = game_summary_store.get_replay_capture(
        current.game.game_id,
    )
    if evidence is None or capture is None:
        return False
    objective_replay = build_worker_objective_replay(
        capture,
        encounter=encounter,
        stream=event_stream,
    )
    try:
        subjective_replay = build_worker_subjective_replays(capture)
    except WorkerPlayerReplayNotReady:
        return False
    coordinator.complete_terminal(
        evidence=evidence,
        objective_replay=objective_replay,
        subjective_replay=subjective_replay,
    )
    task = asyncio.create_task(
        _close_registered_ai_after_terminal(encounter),
        name=f"local-game-terminal-cleanup-{encounter_uuid}",
    )
    _local_terminal_tasks.add(task)
    task.add_done_callback(_local_terminal_tasks.discard)
    return True


def _publish_hosted_terminal_ready(encounter_uuid: UUID) -> bool:
    """Seal one worker-owned generation-fenced terminal ready manifest."""

    if os.environ.get("DND_GAME_WORKER") != "1":
        return False
    game_id_text = os.environ.get("DND_HOSTED_GAME_ID")
    worker_id_text = os.environ.get("DND_WORKER_INSTANCE_ID")
    worker_generation_text = os.environ.get("DND_WORKER_GENERATION")
    runtime_directory = os.environ.get("DND_WORKER_RUNTIME_DIR")
    if (
        game_id_text is None
        or worker_id_text is None
        or worker_generation_text is None
        or runtime_directory is None
    ):
        raise RuntimeError(
            "hosted terminal spool authority is not configured",
        )
    game_id = UUID(game_id_text)
    worker_instance_id = UUID(worker_id_text)
    worker_generation = int(worker_generation_text)
    encounter = Encounter.get(encounter_uuid)
    evidence = game_summary_store.get_evidence(game_id)
    capture = game_summary_store.get_replay_capture(game_id)
    if encounter is None or evidence is None or capture is None:
        return False
    objective_replay = build_worker_objective_replay(
        capture,
        encounter=encounter,
        stream=event_stream,
    )
    try:
        subjective_replay = build_worker_subjective_replays(capture)
    except WorkerPlayerReplayNotReady:
        return False
    holdings_evidence = None
    if _hosted_character_deployment is not None:
        if _hosted_character_entity_uuid is None:
            raise RuntimeError(
                "hosted character deployment has no runtime entity",
            )
        terminal = evidence.summary.terminal_cursor
        holdings_evidence = project_terminal_character_holdings(
            _hosted_character_deployment,
            game_id=game_id,
            generation_id=evidence.generation_id,
            terminal_event_cursor=terminal.event_cursor,
            terminal_combat_log_cursor=terminal.combat_log_cursor,
            runtime_entity_uuid=_hosted_character_entity_uuid,
        )
    WorkerTerminalSpool(runtime_directory).publish(
        game_id=game_id,
        worker_instance_id=worker_instance_id,
        worker_generation=worker_generation,
        summary=evidence,
        objective_replay=objective_replay,
        subjective_replay=subjective_replay,
        holdings=holdings_evidence,
    )
    return True


async def prepare_new_simulation_start() -> None:
    """Stop active automation and clear session-side projection state."""
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()
        try:
            await sim.combat_task
        except asyncio.CancelledError:
            pass

    local_game = _active_local_game_coordinator()
    if local_game is not None:
        local_game.interrupt("local_game_replaced")
    await sim.close_registered_ai_controllers()
    sim.close_native_ai_controllers()
    sim.native_ai_instrumentation = BoundedAIInstrumentationSink()
    ai_takeover_manager.clear(sim.encounter, sim.game)
    clear_subjective_projection_state()
    agent_event_stream.clear_all()
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

async def _abort_failed_simulation_start() -> None:
    """Tear down every engine and server fact from a failed start transaction."""
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()
        try:
            await sim.combat_task
        except asyncio.CancelledError:
            pass

    local_game = _active_local_game_coordinator()
    if local_game is not None:
        local_game.fail("local_game_start_failed")
    await sim.close_registered_ai_controllers()
    sim.close_native_ai_controllers()
    sim.native_ai_instrumentation = BoundedAIInstrumentationSink()
    ai_takeover_manager.clear(sim.encounter, sim.game)
    clear_subjective_projection_state()
    agent_event_stream.clear_all()
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
    _ensure_local_terminal_callback()


async def _close_registered_ai_after_terminal(
    encounter: Encounter,
) -> None:
    """Release remote assignments without rewriting a committed game result."""
    if encounter.state is not EncounterState.ENDED:
        return
    try:
        await sim.close_registered_ai_controllers()
    except BaseException:
        logger.exception(
            "Registered AI teardown failed after encounter %s ended",
            encounter.uuid,
        )


async def advance_encounter(
    timing: Optional[_ServerCommandTiming] = None,
    *,
    publish_decision_epoch: bool = True,
) -> AdvanceEncounterResult:
    """Advance the encounter until a player-controlled turn or terminal state.

    Args:
        timing: Optional phase recorder for command diagnostics.
        publish_decision_epoch: Whether to publish the resulting AI decision epoch.

    Returns:
        Control acknowledgement with the resulting turn boundary and canonical
        replication cursor barriers.
    """
    if sim.encounter is None:
        return AdvanceEncounterResult(status="no_encounter")

    started = time.perf_counter()
    restore_expired_takeovers()
    if timing is not None:
        timing.add("advance.restore_expired_takeovers_ms", started)

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
    result = sim.encounter.advance_until_player()
    if timing is not None:
        timing.add("advance.advance_until_player_ms", started)

    if publish_decision_epoch:
        started = time.perf_counter()
        _publish_decision_epoch_for_active_session(
            DecisionEpochReason.TURN_START,
            timing=timing,
        )
        if timing is not None:
            timing.add("advance.publish_active_epoch_ms", started)

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
        name=f"native-ai-game-{sim.activation_identity.game_id}",
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
            controller = encounter.get_current_controller()
            if controller is None:
                logger.error(
                    "Activated encounter %s has no controller for its current actor",
                    encounter.uuid,
                )
                sim.paused = True
                return
            if (
                controller.execution_mode is ControllerExecutionMode.AUTONOMOUS
                and encounter.turn_state is not TurnState.IN_PROGRESS
            ):
                await asyncio.sleep(max(0.0, sim.turn_delay))
            if (
                sim.encounter is not encounter
                or sim.activation_identity != activation
                or sim.paused
            ):
                return
            result = encounter.advance_one_controller_action_boundary()
            if (
                result.status == "waiting_for_ai_provider"
                and isinstance(controller, RegisteredAIController)
            ):
                entity = encounter.get_current_entity()
                if entity is None:
                    raise RuntimeError(
                        "registered AI boundary has no current actor"
                    )
                controller_uuid = controller.uuid
                actor_uuid = entity.uuid
                frozen_context = encounter.build_current_turn_context()
                pending = await controller.request_intent(
                    entity,
                    frozen_context,
                )
                if (
                    sim.encounter is not encounter
                    or sim.activation_identity != activation
                    or sim.paused
                    or encounter.state is not EncounterState.ACTIVE
                    or encounter.get_current_entity() is not entity
                    or encounter.get_current_controller() is not controller
                ):
                    return
                current_context = encounter.build_current_turn_context()
                if (
                    current_context.round_number
                    != frozen_context.round_number
                    or current_context.turn_index != frozen_context.turn_index
                    or current_context.entity_uuid
                    != frozen_context.entity_uuid
                ):
                    return
                with EventQueue.batch_on_event_callbacks():
                    if isinstance(pending, ControllerStepResult):
                        step = pending
                    else:
                        step = controller.resolve_pending_intent(
                            entity,
                            current_context,
                            pending,
                        )
                    result = encounter.resolve_deferred_controller_step(
                        entity_uuid=actor_uuid,
                        controller_uuid=controller_uuid,
                        step=step,
                    )
            elif result.status == "waiting_for_ai_provider":
                raise RuntimeError(
                    "only RegisteredAIController may expose the external "
                    "provider boundary"
                )
            if result.status in {
                "autonomous_action_completed",
                "advanced_autonomous",
                "deferred_action_completed",
            }:
                # A zero-delay sleep immediately requeues this always-ready
                # task.  Long AI-vs-AI matches can then make an HTTP request
                # wait behind several projection-heavy action boundaries.
                # One millisecond is a scheduler fairness checkpoint, not a
                # gameplay/turn delay: it gives already-ready HTTP and SSE
                # tasks a complete event-loop cycle while adding at most one
                # millisecond per autonomous decision.
                await asyncio.sleep(0.001)
                continue
            if result.status in {
                "waiting_for_human",
                "waiting_for_codex",
            }:
                _publish_decision_epoch_for_active_session(
                    DecisionEpochReason.TURN_START,
                )
            return
    except asyncio.CancelledError:
        raise
    except BaseException:
        sim.paused = True
        logger.exception(
            "Activated encounter coordinator failed for %s",
            encounter.uuid,
        )
    finally:
        if (
            sim.encounter is encounter
            and encounter.state is EncounterState.ENDED
        ):
            await _close_registered_ai_after_terminal(encounter)


def action_cursor_fields() -> dict:
    """Return replication cursors after a state mutation.

    Returns:
        Event and combat-log cursor positions for clients that need deltas.
    """
    return {
        "event_cursor_after": EventQueue.event_cursor(),
        "combat_log_cursor_after": len(sim.encounter.combat_log) if sim.encounter else 0,
    }


def serialize_takeover_claim(claim: TakeoverClaim) -> TakeoverClaimResponse:
    """Serialize a takeover claim with current entity/controller context."""
    rows = []
    for entity_uuid in claim.entity_uuids:
        state = claim.entity_states[entity_uuid]
        entity = Entity.get(entity_uuid)
        previous_controller = Controller.get(state.previous_controller_uuid)
        current_controller = sim.encounter.get_controller_for(entity_uuid) if sim.encounter else None
        rows.append(TakeoverEntityRow(
            entity_uuid=str(entity_uuid),
            entity_name=entity.name if entity else "Unknown",
            faction=entity.faction if entity else None,
            previous_controller_uuid=str(state.previous_controller_uuid),
            previous_controller_type=previous_controller.controller_type if previous_controller else None,
            current_controller_type=current_controller.controller_type if current_controller else None,
            previous_owner_session_id=(
                str(state.previous_owner_session_id)
                if state.previous_owner_session_id else None
            ),
        ))
    return TakeoverClaimResponse(
        claim_id=str(claim.claim_id),
        session_id=str(claim.session_id),
        name=claim.name,
        faction=claim.faction,
        created_at=claim.created_at,
        last_heartbeat_at=claim.last_heartbeat_at,
        lease_seconds=claim.lease_seconds,
        expires_at=claim.expires_at,
        is_expired=claim.is_expired(),
        claimed_entities=rows,
    )


def restore_expired_takeovers() -> list[TakeoverClaim]:
    """Restore expired claims while preserving append-only subjective history."""
    manager = sim.get_session_manager()
    subjective_authority_before = _capture_subjective_session_authority(manager)
    boundary = prepare_observation_ownership_change(manager)
    expired = ai_takeover_manager.restore_expired(sim.encounter, sim.game)
    if expired:
        _publish_takeover_ownership_changes(
            boundary,
            "takeover_expired",
            subjective_authority_before=subjective_authority_before,
        )
    return expired


def _publish_takeover_ownership_changes(
    boundary: ObservationOwnershipBoundary,
    reason: str,
    *,
    subjective_authority_before: dict[
        str,
        _SubjectiveSessionAuthorityFingerprint,
    ],
) -> list[str]:
    """Publish ownership replacements and reconcile affected decision epochs."""
    _retire_changed_subjective_sessions(
        sim.get_session_manager(),
        subjective_authority_before,
    )
    changed_session_ids = publish_observation_ownership_changes(
        boundary,
        reason=reason,
        session_manager=sim.get_session_manager(),
    )
    for session_id in changed_session_ids:
        current = _forget_current_epoch(session_id)
        _last_published_epoch_by_session.pop(session_id, None)
        if current is not None:
            append_epoch_clear_frame(
                session_id,
                reason=reason,
                session_manager=sim.get_session_manager(),
            )
    _publish_decision_epoch_for_active_session(DecisionEpochReason.RESYNC)
    return changed_session_ids


def _takeover_http_exception(error: TakeoverError, **context: Any) -> HTTPException:
    """Convert a takeover manager error to a structured HTTP exception."""
    return _api_http_exception(
        status_code=error.status_code,
        code=error.code,
        message=error.message,
        **context,
    )


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


def _parse_uuid_list(values: Optional[list[str]], field_name: str) -> Optional[list[UUID]]:
    """Parse an optional list of UUID request fields."""
    if values is None:
        return None
    parsed = []
    for value in values:
        parsed_uuid = _parse_optional_uuid(value, field_name)
        if parsed_uuid is not None:
            parsed.append(parsed_uuid)
    return parsed


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
    handler_name: Optional[str] = None,
) -> HTTPException:
    """Create a structured handler API error.

    Args:
        entity: Entity whose handler mutation failed.
        status_code: HTTP status code for the response.
        code: Machine-readable error code.
        message: Human-readable error message.
        handler_name: Optional handler name supplied by the client.

    Returns:
        HTTP exception with valid handler names and handler summaries.
    """
    handlers = _serialize_entity_handlers(entity)
    return _api_http_exception(
        status_code=status_code,
        code=code,
        message=message,
        entity_uuid=str(entity.uuid),
        entity_name=entity.name,
        handler_name=handler_name,
        valid_handler_names=[handler.name for handler in handlers],
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
    projection_authority: Optional[RuntimeProjectionAuthority]
    subjective_authority: ResolvedSubjectiveAuthority


def _resolve_replication_request(
    request: Request,
    session_id: str,
) -> _ReplicationRequestContext:
    """Resolve one canonical request from private claims or standalone mode."""
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

    is_worker = os.environ.get("DND_GAME_WORKER") == "1"
    try:
        projection_authority = parse_runtime_projection_authority(request.headers)
        if is_worker and projection_authority is None:
            raise RuntimeAuthorityError("trusted runtime authority is required")
        if not is_worker and projection_authority is not None:
            raise RuntimeAuthorityError(
                "runtime projection headers are only accepted by a private game worker"
            )

        configured_game_id = os.environ.get("DND_HOSTED_GAME_ID")
        if is_worker and configured_game_id is None:
            raise RuntimeAuthorityError("worker hosted-game identity is unavailable")
        if projection_authority is not None and configured_game_id is not None:
            try:
                matches_worker = projection_authority.hosted_game_id == UUID(configured_game_id)
            except ValueError as exc:
                raise RuntimeAuthorityError("worker hosted-game identity is malformed") from exc
            if not matches_worker:
                raise RuntimeAuthorityError("runtime authority belongs to another hosted game")

        local_game = _active_local_game_coordinator()
        subjective_authority = resolve_subjective_authority(
            session,
            projection_authority,
            standalone_membership_id=(
                local_game.membership_id
                if not is_worker and local_game is not None
                else None
            ),
            allow_standalone=not is_worker,
        )
    except (RuntimeAuthorityError, SubjectiveAuthorityError) as exc:
        raise _api_http_exception(
            status_code=403,
            code="replication_authority_rejected",
            message=str(exc),
            session_id=session_id,
        )

    return _ReplicationRequestContext(
        session_id=sid,
        session=session,
        projection_authority=projection_authority,
        subjective_authority=subjective_authority,
    )


def _replication_runtime_context(
    request_context: _ReplicationRequestContext,
    *,
    expected_source_stream_id: Optional[str] = None,
    expected_generation_id: Optional[str],
    expected_perspective_epoch_id: Optional[str],
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
        _ensure_local_terminal_callback()
        context.validate_identity(
            expected_source_stream_id=expected_source_stream_id,
            expected_generation_id=expected_generation_id,
            expected_perspective_epoch_id=expected_perspective_epoch_id,
        )
        return context
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
    """Require hosted administration authority or explicit standalone access.

    Public hosted requests always arrive with gateway-authenticated projection
    headers. Header-free calls are accepted only by the standalone server.
    Worker-internal terminal evidence uses its distinct private route family.
    """
    try:
        is_worker = os.environ.get("DND_GAME_WORKER") == "1"
        if request.url.path in {
            "/game/evidence/objective-bootstrap",
            "/game/evidence/objective-subscribe",
        }:
            if not is_worker:
                raise RuntimeAuthorityError(
                    "worker-internal objective evidence is unavailable"
                )
            return
        authority = parse_runtime_projection_authority(request.headers)
        if authority is None:
            if is_worker:
                raise RuntimeAuthorityError(
                    "trusted runtime administration authority is required"
                )
            return
        if not is_worker:
            raise RuntimeAuthorityError(
                "runtime projection headers are only accepted by a private game worker"
            )
        configured_game_id = os.environ.get("DND_HOSTED_GAME_ID")
        if configured_game_id is None:
            raise RuntimeAuthorityError("worker hosted-game identity is unavailable")
        try:
            hosted_game_id = UUID(configured_game_id)
        except ValueError as exc:
            raise RuntimeAuthorityError(
                "worker hosted-game identity is malformed"
            ) from exc
        if authority.hosted_game_id != hosted_game_id:
            raise RuntimeAuthorityError(
                "runtime authority belongs to another hosted game"
            )
        if RuntimeScope.ADMINISTER not in authority.scopes:
            raise RuntimeAuthorityError(
                "objective diagnostics require runtime administration authority"
            )
    except RuntimeAuthorityError as exc:
        raise _api_http_exception(
            status_code=403,
            code="objective_diagnostics_authority_rejected",
            message=str(exc),
        ) from exc


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


def _observation_http_exception(
    error: ObservationAccessError,
    session_id: Optional[str] = None,
) -> HTTPException:
    """Convert observation access errors into structured session errors."""
    status_code = 400 if error.code == "invalid_session_uuid" else 404
    return _session_http_exception(
        status_code=status_code,
        code=error.code,
        message=error.message,
        session_id=session_id,
    )


def _event_filter_http_exception(
    code: str,
    message: str,
    event_type: Optional[str] = None,
    phase: Optional[str] = None,
) -> HTTPException:
    """Create a structured event-history filter error.

    Args:
        code: Machine-readable error code.
        message: Human-readable error message.
        event_type: Optional event-type filter supplied by the client.
        phase: Optional event-phase filter supplied by the client.

    Returns:
        HTTP exception with valid event types, phases, and cursor context.
    """
    return _api_http_exception(
        status_code=400,
        code=code,
        message=message,
        event_type=event_type,
        phase=phase,
        valid_event_types=[event_type.value for event_type in EventType],
        valid_phases=[phase.value for phase in EventPhase],
        event_cursor=EventQueue.event_cursor(),
        event_count=len(EventQueue._all_events),
    )


def _simulation_context() -> dict:
    """Build correction context for simulation-control endpoints.

    Returns:
        Simulation status fields used by structured control errors.
    """
    return {
        "has_encounter": sim.encounter is not None,
        "paused": sim.paused,
        "encounter_state": sim.encounter.state.value if sim.encounter else None,
        "round_number": sim.encounter.round_number if sim.encounter else None,
        "turn_delay": sim.turn_delay,
        "min_delay": 0.0,
        "max_delay": 10.0,
    }


def _simulation_http_exception(code: str, message: str, **context: Any) -> HTTPException:
    """Create a structured simulation-control API error.

    Args:
        code: Machine-readable error code.
        message: Human-readable error message.
        **context: Additional JSON-serializable correction context.

    Returns:
        HTTP exception with current simulation-control context.
    """
    return _api_http_exception(
        status_code=400,
        code=code,
        message=message,
        **_simulation_context(),
        **context,
    )


def _mapeditor_context() -> dict:
    """Build correction context for mapeditor endpoint failures.

    Returns:
        Catalog, saved-map, and current-map context for map-editor errors.
    """
    catalog = build_catalog()
    saved_maps = list_saved_editor_maps().maps
    current_map = None
    try:
        snapshot = get_editor_snapshot()
        current_map = {
            "grid_bounds": snapshot.grid_bounds.model_dump(mode="json"),
            "tile_count": len(snapshot.tiles),
            "floor_object_count": len(snapshot.floor_objects),
        }
    except Exception:
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


def validate_session_action(session_id_str: str, entity_uuid_str: str) -> Entity:
    """Validate that a session can perform an action with an entity.

    Args:
        session_id_str: UUID string for the acting session.
        entity_uuid_str: UUID string for the entity trying to act.

    Returns:
        Entity that passed session ownership and turn validation.

    Raises:
        HTTPException: If either UUID is malformed, the entity is missing, or
            the session manager rejects the action.
    """
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

    restore_expired_takeovers()
    mgr = sim.get_session_manager()
    _, _ = mgr.validate_action(session_id, entity_uuid)

    entity = Entity.get(entity_uuid)
    if not entity:
        raise _entity_lookup_exception(
            entity_uuid=entity_uuid_str,
            status_code=404,
            code="entity_not_found",
            message="Entity not found",
        )

    return entity


def _install_standalone_local_profile(
    app: FastAPI,
    content_system: LoadedContentSystem,
) -> LocalProfileHandle | None:
    """Open exactly one physical local profile for standalone directory use."""

    app.state.directory_stream = None
    if os.environ.get("DND_GAME_WORKER") == "1":
        app.state.local_profile_manager = None
        app.state.local_profile_handle = None
        app.state.character_directory = None
        app.state.local_game_coordinator = None
        app.state.game_history = None
        app.state.directory_stream = None
        return None
    manager = LocalProfileManager(
        capability_pepper=os.environ.get(
            "DND_LOCAL_PROFILE_CAPABILITY_PEPPER",
            "local-profile-development-pepper",
        ).encode("utf-8"),
        runtime_root=Path(
            os.environ.get("DND_LOCAL_PROFILE_RUNTIME_ROOT", ".runtime"),
        ),
    )
    selected = os.environ.get("DND_LOCAL_PROFILE_ID")
    if selected is not None:
        handle = manager.open_profile(UUID(selected))
    else:
        profiles = manager.list_profiles()
        if not profiles:
            handle = manager.create_profile(
                os.environ.get(
                    "DND_LOCAL_PROFILE_DISPLAY_NAME",
                    "Local Player",
                ),
            )
        elif len(profiles) == 1:
            handle = manager.open_profile(profiles[0].profile_id)
        else:
            raise RuntimeError(
                "Multiple local profiles exist; set DND_LOCAL_PROFILE_ID",
            )
    app.state.local_profile_manager = manager
    app.state.local_profile_handle = handle
    character_directory = CharacterDirectoryService(
        handle.repository,
        content_system,
    )
    app.state.character_directory = character_directory
    coordinator = StandaloneLocalGameCoordinator(
        repository=handle.repository,
        character_directory=character_directory,
        artifact_root=handle.artifacts_root,
        owner_principal_id=handle.profile_id,
        content_digest=content_system.content_set_digest,
        on_mutation=_publish_standalone_directory_events,
    )
    coordinator.recover_abandoned_games()
    app.state.local_game_coordinator = coordinator
    app.state.game_history = GameHistoryQueryService(
        handle.repository,
        coordinator.artifact_store,
    )
    directory_stream = DirectoryEventStream(
        lambda since, limit: handle.repository.list_directory_events(
            since_cursor=since,
            limit=limit,
        ),
    )
    directory_stream.publish_pending()
    app.state.directory_stream = directory_stream
    return handle


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
    local_profile = _install_standalone_local_profile(
        app,
        installed_content_system,
    )

    with latency_sensitive_gc():
        event_stream.start()
        canonical_subjective_replication_runtime.ensure_attached()
        game_summary_store.ensure_attached()
        _ensure_local_terminal_callback()
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
                coordinator = _active_local_game_coordinator()
                if coordinator is not None:
                    coordinator.interrupt("local_game_server_shutdown")
                await sim.close_registered_ai_controllers()
            finally:
                sim.close_native_ai_controllers()
                try:
                    await _active_registered_ai_provider_catalog().close()
                finally:
                    try:
                        canonical_subjective_replication_runtime.stop()
                    finally:
                        try:
                            event_stream.stop()
                        finally:
                            try:
                                sim.reset()
                            finally:
                                try:
                                    reset_engine_runtime()
                                finally:
                                    if local_profile is not None:
                                        local_profile.close()

app = FastAPI(
    title="D&D Engine Event Server",
    description="Event-driven game engine with canonical player replication and objective diagnostics",
    lifespan=lifespan
)

_world_replacement_lock = asyncio.Lock()
_hosted_character_deployment: CharacterDeploymentSnapshot | None = None
_hosted_character_entity_uuid: UUID | None = None


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


def _resolve_standalone_character_directory(
    request: Request,
) -> CharacterDirectoryService:
    service = request.app.state.character_directory
    if not isinstance(service, CharacterDirectoryService):
        raise _api_http_exception(
            status_code=404,
            code="local_character_directory_unavailable",
            message="Hosted workers do not own local player profiles",
        )
    return service


def _authorize_standalone_character_principal(
    request: Request,
    principal_id: UUID,
    principal_capability: str,
) -> UUID:
    handle = request.app.state.local_profile_handle
    if not isinstance(handle, LocalProfileHandle):
        raise CapabilityError("Local profile is unavailable")
    expected_capability = os.environ.get(
        "DND_LOCAL_PROFILE_CAPABILITY",
        "local-profile",
    )
    if (
        principal_id != handle.profile_id
        or not hmac.compare_digest(
            principal_capability,
            expected_capability,
        )
    ):
        raise CapabilityError("Local profile capability is invalid")
    return handle.profile_id


app.include_router(
    create_character_directory_router(
        resolve_service=_resolve_standalone_character_directory,
        authorize_principal=_authorize_standalone_character_principal,
        on_mutation=_publish_standalone_directory_events,
    ),
)


def _resolve_standalone_game_history(
    request: Request,
) -> GameHistoryQueryService:
    service = request.app.state.game_history
    if not isinstance(service, GameHistoryQueryService):
        raise _api_http_exception(
            status_code=404,
            code="local_game_history_unavailable",
            message="Hosted workers do not own local game history",
        )
    return service


def _authorize_optional_standalone_history_principal(
    request: Request,
    principal_id: UUID | None,
    principal_capability: str | None,
) -> UUID | None:
    if principal_id is None and principal_capability is None:
        return None
    if principal_id is None or principal_capability is None:
        raise _api_http_exception(
            status_code=400,
            code="incomplete_principal_auth",
            message="Both principal fields are required",
        )
    return _authorize_standalone_character_principal(
        request,
        principal_id,
        principal_capability,
    )


def _resolve_standalone_directory_stream(
    request: Request,
) -> DirectoryEventStream:
    stream = request.app.state.directory_stream
    if not isinstance(stream, DirectoryEventStream):
        raise _api_http_exception(
            status_code=404,
            code="local_directory_stream_unavailable",
            message="Hosted workers do not own a cold directory stream",
        )
    return stream


def _resolve_standalone_directory_event_filter(
    request: Request,
    principal_id: UUID | None,
    principal_capability: str | None,
) -> Callable[[DirectoryEventRecord], bool]:
    principal = _authorize_optional_standalone_history_principal(
        request,
        principal_id,
        principal_capability,
    )
    return _resolve_standalone_game_history(
        request,
    ).directory_event_filter(principal)


app.include_router(
    create_directory_event_stream_router(
        resolve_stream=_resolve_standalone_directory_stream,
        resolve_event_filter=_resolve_standalone_directory_event_filter,
    ),
)


app.include_router(
    create_game_history_router(
        resolve_service=_resolve_standalone_game_history,
        authorize_optional_principal=(
            _authorize_optional_standalone_history_principal
        ),
        authorize_required_principal=(
            _authorize_standalone_character_principal
        ),
    ),
)


@app.get(
    "/directory/local-profile",
    response_model=StandaloneLocalProfileResponse,
)
async def get_standalone_local_profile(
    request: Request,
) -> StandaloneLocalProfileResponse:
    """Return the explicitly local-trust profile selected by this process."""

    handle = request.app.state.local_profile_handle
    if not isinstance(handle, LocalProfileHandle):
        raise _api_http_exception(
            status_code=404,
            code="local_profile_unavailable",
            message="Hosted workers do not expose local profiles",
        )
    return StandaloneLocalProfileResponse(
        profile_id=handle.profile_id,
        display_name=handle.display_name,
        principal_capability=os.environ.get(
            "DND_LOCAL_PROFILE_CAPABILITY",
            "local-profile",
        ),
        settings=handle.repository.get_profile_settings(handle.profile_id),
    )


@app.post(
    "/admin/characters/{character_id}/advancement-awards",
    response_model=CharacterAdvancementResponse,
)
async def grant_standalone_character_advancement_award(
    request: Request,
    character_id: UUID,
    body: AdminCharacterAdvancementAwardRequest,
    principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
    principal_capability: str = Header(
        alias="X-Dnd-Principal-Capability",
    ),
) -> CharacterAdvancementResponse:
    """Grant a local-profile level entitlement for creator UI and tooling."""

    owner = _authorize_standalone_character_principal(
        request,
        principal_id,
        principal_capability,
    )
    result = _resolve_standalone_character_directory(
        request,
    ).grant_admin_advancement_award(
        owner,
        character_id,
        body,
    )
    _publish_standalone_directory_events(request)
    return result


@app.exception_handler(CharacterDirectoryBuildError)
async def character_build_exception_handler(
    _request: Request,
    exc: CharacterDirectoryBuildError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.validation.model_dump(mode="json")},
    )


@app.exception_handler(DirectoryError)
async def directory_exception_handler(
    _request: Request,
    exc: DirectoryError,
) -> JSONResponse:
    status = (
        404
        if isinstance(exc, NotFoundError)
        else 403
        if isinstance(exc, (CapabilityError, CharacterDirectoryOwnershipError))
        else 409
        if isinstance(exc, ConflictError)
        else 500
    )
    code = (
        "character_not_owned"
        if isinstance(exc, CharacterDirectoryOwnershipError)
        else type(exc).__name__
    )
    return JSONResponse(
        status_code=status,
        content={"detail": {"code": code, "message": str(exc)}},
    )


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


@app.get(
    "/hosted/readiness",
    response_model=HostedWorkerReadiness,
    include_in_schema=False,
)
async def hosted_worker_readiness() -> HostedWorkerReadiness:
    """Return the frozen content identity used for worker-pool admission."""
    content_system = SERVER_CONTENT_SYSTEM_RUNTIME.require()
    expected_content_set_digest = os.environ.get(
        "DND_EXPECTED_CONTENT_SET_DIGEST",
    )
    return HostedWorkerReadiness(
        status=(
            "content_mismatch"
            if expected_content_set_digest is not None
            and expected_content_set_digest != content_system.content_set_digest
            else "ready"
        ),
        content_api_version=ENGINE_CONTENT_API_VERSION,
        content_set_digest=content_system.content_set_digest,
        built_in_artifact_digest=content_system.built_in_artifact_digest,
        expected_content_set_digest=expected_content_set_digest,
        external_pack_ids=tuple(
            sorted(pack.manifest.pack_id for pack in content_system.packs)
        ),
    )


@app.post("/hosted/configure")
async def configure_hosted_worker(
    assignment: HostedWorkerAssignment,
) -> dict[str, str]:
    """Assign a ready worker to one hosted game before simulation creation.

    Args:
        assignment: Trusted hosted-game identity and public routing metadata.

    Returns:
        Configuration acknowledgement.

    Raises:
        HTTPException: If the process is not a worker or already owns game state.
    """
    global _hosted_character_deployment
    if os.environ.get("DND_GAME_WORKER") != "1":
        raise _api_http_exception(
            status_code=404,
            code="hosted_worker_configuration_unavailable",
            message="Hosted worker configuration is unavailable",
        )
    if sim.encounter is not None or sim.game is not None:
        raise _api_http_exception(
            status_code=409,
            code="hosted_worker_already_initialized",
            message="Hosted worker already owns a game",
        )
    os.environ["DND_HOSTED_GAME_ID"] = str(assignment.hosted_game_id)
    os.environ["DND_PUBLIC_GAME_BASE_URL"] = assignment.public_game_base_url.rstrip("/")
    os.environ["DND_WORKER_INSTANCE_ID"] = str(
        assignment.worker_instance_id,
    )
    os.environ["DND_WORKER_GENERATION"] = str(
        assignment.worker_generation,
    )
    os.environ["DND_WORKER_RUNTIME_DIR"] = (
        assignment.terminal_runtime_directory
    )
    _hosted_character_deployment = assignment.character_deployment
    return {"status": "configured"}


@app.get("/server/capabilities", response_model=ServerCapabilitiesResponse)
async def get_server_capabilities() -> ServerCapabilitiesResponse:
    """Return standalone capabilities backed by the selected local profile."""
    return ServerCapabilitiesResponse(
        server_mode="standalone",
        game_directory_enabled=True,
        persistent_game_history=True,
        isolated_game_workers=False,
    )


@app.get("/content/manifest", response_model=ContentManifestResponse)
async def get_content_manifest(
    request: Request,
    response: Response,
) -> ContentManifestResponse | Response:
    """Return the exact installed content-set and source identity."""
    manifest = build_content_manifest(
        SERVER_CONTENT_SYSTEM_RUNTIME.require(),
    )
    etag = content_response_etag(manifest.content_set_digest)
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=0, must-revalidate",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    return manifest


@app.get("/content/catalog", response_model=ContentCatalogResponse)
async def get_content_catalog(
    request: Request,
    response: Response,
) -> ContentCatalogResponse | Response:
    """Return public code-free descriptors for the installed content set."""
    catalog = build_public_content_catalog(
        SERVER_CONTENT_SYSTEM_RUNTIME.require(),
    )
    etag = content_response_etag(catalog.catalog_digest)
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=0, must-revalidate",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    return catalog


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
        await prepare_new_simulation_start()
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
        await prepare_new_simulation_start()
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


@app.post("/simulation/pause")
async def pause_simulation():
    """Pause the combat loop.

    Returns:
        Status payload confirming the paused state.
    """
    sim.paused = True
    return {"status": "paused"}


@app.post("/simulation/resume")
async def resume_simulation():
    """Resume the combat loop for an existing simulation.

    Returns:
        Status payload confirming the resumed state.

    Raises:
        HTTPException: If no simulation exists.
    """
    if sim.encounter is None or sim.activation_identity is None:
        raise _simulation_http_exception(
            code="simulation_not_started",
            message="No activated game is available to resume.",
        )

    sim.paused = False
    _schedule_activated_game_coordinator()

    return {"status": "resumed"}


@app.post("/simulation/step")
async def step_simulation():
    """Execute a single encounter turn.

    Returns:
        Status payload describing the stepped turn or terminal encounter state.

    Raises:
        HTTPException: If no simulation exists.
    """
    if sim.encounter is None:
        raise _simulation_http_exception(
            code="simulation_not_started",
            message="No simulation. Call /simulation/reset first.",
        )

    if sim.encounter.state == EncounterState.NOT_STARTED:
        sim.encounter.start_encounter()

    if sim.encounter.state != EncounterState.ACTIVE:
        return {
            "status": "encounter_ended",
            "state": sim.encounter.state.value
        }

    sim.encounter.run_turn()

    return {
        "status": "stepped",
        "round": sim.encounter.round_number,
        "turn_index": sim.encounter.current_turn_index
    }


@app.post("/simulation/set-delay")
async def set_turn_delay(delay: float):
    """Set the delay between automated turns.

    Args:
        delay: Delay in seconds.

    Returns:
        Status payload with the effective turn delay.

    Raises:
        HTTPException: If the delay is outside supported bounds.
    """
    if delay < 0:
        raise _simulation_http_exception(
            code="delay_too_low",
            message="Delay cannot be negative",
            requested_delay=delay,
        )
    if delay > 10:
        raise _simulation_http_exception(
            code="delay_too_high",
            message="Delay cannot exceed 10 seconds",
            requested_delay=delay,
        )

    sim.turn_delay = delay
    return {"status": "delay_set", "turn_delay": sim.turn_delay}


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
) -> SubjectiveReplicationBootstrap:
    """Return one atomic renderer-complete subjective reducer seed."""
    response.headers["Cache-Control"] = "private, no-store"
    request_context = _resolve_replication_request(request, session_id)
    context = _replication_runtime_context(
        request_context,
        expected_generation_id=None,
        expected_perspective_epoch_id=None,
    )
    try:
        return context.bootstrap()
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
    mgr.remove_session(sid)
    perspective_epoch_registry.clear_session(session_id)

    return {"status": "deleted", "session_id": session_id}


@app.post("/game/join", response_model=JoinGameResponse)
async def join_game(request: JoinGameRequest):
    """Join the active game with a session.

    Entity assignment priority is explicit UUIDs, then faction, then the demo
    convention where human players receive Hero and Codex players receive
    non-Hero entities.

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
            requested_faction=request.faction,
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
            requested_faction=request.faction,
        )

    game = sim.game
    if not game:
        raise _session_http_exception(
            status_code=400,
            code="no_active_game",
            message="No active game to join",
            session_id=request.session_id,
            requested_entity_uuids=requested_entity_uuids,
            requested_faction=request.faction,
        )

    subjective_authority_before = _capture_subjective_session_authority(mgr)
    if session.session_id not in game.players:
        game.add_player(session)

    if session.player_type == PlayerType.OBSERVER and (requested_entity_uuids or request.faction):
        raise _session_http_exception(
            status_code=400,
            code="observer_cannot_control_entities",
            message="Observer sessions cannot claim entities or factions",
            session_id=request.session_id,
            requested_entity_uuids=requested_entity_uuids,
            requested_faction=request.faction,
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

    ownership_boundary = prepare_observation_ownership_change(mgr)
    assigned = []
    if requested_entity_uuids:
        for uuid_str in requested_entity_uuids:
            try:
                entity_uuid = UUID(uuid_str)
                if game.assign_entity(entity_uuid, session.session_id):
                    assigned.append(str(entity_uuid))
            except ValueError:
                continue
    elif request.faction:
        for entity in Entity.get_all_entities():
            if entity.faction == request.faction:
                if game.assign_entity(entity.uuid, session.session_id):
                    assigned.append(str(entity.uuid))
    else:
        for entity in Entity.get_all_entities():
            if session.player_type == PlayerType.HUMAN and entity.name == "Hero":
                if game.assign_entity(entity.uuid, session.session_id):
                    assigned.append(str(entity.uuid))
            elif session.player_type == PlayerType.CODEX and entity.name != "Hero":
                if game.assign_entity(entity.uuid, session.session_id):
                    assigned.append(str(entity.uuid))

    _publish_takeover_ownership_changes(
        ownership_boundary,
        "game_join_assignment",
        subjective_authority_before=subjective_authority_before,
    )

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


@app.get("/game/evidence/summary", response_model=WorkerSummaryEvidence)
async def get_worker_terminal_summary() -> WorkerSummaryEvidence:
    """Return the worker-local canonical terminal summary.

    This endpoint is private to the hosting gateway. Standalone servers may
    still use it for local inspection, but it never reads or writes a database.
    """
    evidence = game_summary_store.get_evidence(os.environ.get("DND_HOSTED_GAME_ID"))
    if evidence is None:
        raise _api_http_exception(
            status_code=404,
            code="terminal_summary_not_ready",
            message="The active game has no terminal summary yet",
        )
    return evidence


@app.get("/game/evidence/objective-replay", response_model=ObjectiveReplayBundle)
async def get_worker_terminal_objective_replay() -> ObjectiveReplayBundle:
    """Materialize the private immutable replay after terminal journals close."""
    capture = game_summary_store.get_replay_capture(
        os.environ.get("DND_HOSTED_GAME_ID")
    )
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
        return build_worker_objective_replay(
            capture,
            encounter=encounter,
            stream=event_stream,
        )
    except WorkerReplayError as exc:
        raise _api_http_exception(
            status_code=500,
            code="terminal_objective_replay_invalid",
            message=str(exc),
        ) from exc


@app.get(
    "/game/evidence/subjective-replay",
    response_model=SubjectivePlayerReplayArchive,
)
async def get_worker_terminal_subjective_replay() -> SubjectivePlayerReplayArchive:
    """Freeze the exact canonical player reducer inputs retained during play."""

    capture = game_summary_store.get_replay_capture(
        os.environ.get("DND_HOSTED_GAME_ID")
    )
    if capture is None:
        raise _api_http_exception(
            status_code=404,
            code="terminal_subjective_replay_not_ready",
            message="The active game has no terminal player replay yet",
        )
    try:
        return build_worker_subjective_replays(capture)
    except WorkerPlayerReplayNotReady as exc:
        raise _api_http_exception(
            status_code=404,
            code="terminal_subjective_replay_not_ready",
            message=str(exc),
        ) from exc
    except WorkerPlayerReplayError as exc:
        raise _api_http_exception(
            status_code=500,
            code="terminal_subjective_replay_invalid",
            message=str(exc),
        ) from exc


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
    "/game/evidence/objective-bootstrap",
    include_in_schema=False,
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


@app.get(
    "/game/evidence/objective-subscribe",
    include_in_schema=False,
)
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
        if "subscription" in locals():
            event_stream.unsubscribe(subscription)
        raise

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


def _build_decision_epoch(
    session_id: str,
    reason: DecisionEpochReason = DecisionEpochReason.SNAPSHOT,
    *,
    reuse_current: bool = True,
    timing: Optional[_ServerCommandTiming] = None,
    phase_prefix: str = "epoch",
) -> Optional[DecisionEpoch]:
    """Build a decision epoch when the session controls the active actor."""
    if sim.encounter is None or sim.game is None:
        return None

    started = time.perf_counter()
    try:
        parsed_session_id = UUID(session_id)
    except ValueError:
        return None
    if timing is not None:
        timing.add(f"{phase_prefix}.parse_session_id_ms", started)

    started = time.perf_counter()
    session = sim.get_session_manager().get_session(parsed_session_id)
    if session is None:
        return None
    if timing is not None:
        timing.add(f"{phase_prefix}.resolve_session_ms", started)

    if reuse_current:
        started = time.perf_counter()
        cached = _current_decision_epoch(session_id, session)
        if timing is not None:
            timing.add(f"{phase_prefix}.current_epoch_cache_check_ms", started)
        if cached is not None:
            return cached

    started = time.perf_counter()
    active_uuid = sim.game.active_entity_uuid
    if (
        sim.encounter.turn_state is not TurnState.IN_PROGRESS
        or active_uuid is None
        or active_uuid not in session.controlled_entities
    ):
        return None
    if timing is not None:
        timing.add(f"{phase_prefix}.resolve_active_actor_ms", started)
    actor = Entity.get(active_uuid)
    if actor is None or not actor.has_hp:
        return None

    try:
        started = time.perf_counter()
        observation_cursor = get_observation_cursor(
            session_id,
            session_manager=sim.get_session_manager(),
            record_timing=_prefixed_timing_recorder(timing, f"{phase_prefix}.observation_cursor")
            if timing is not None
            else None,
        )
        if timing is not None:
            timing.add(f"{phase_prefix}.get_observation_cursor_ms", started)
    except ObservationAccessError:
        return None

    build = build_subjective_decision_epoch(
        actor,
        epoch_namespace=session_id,
        round_number=sim.encounter.round_number,
        turn_index=sim.encounter.current_turn_index,
        observation_cursor=observation_cursor,
        reason=reason,
        record_timing=_prefixed_timing_recorder(timing, phase_prefix),
    )
    if build is None:
        return None
    _available_actions_cache[build.epoch.actor_uuid] = build.available_actions
    _execution_authority_by_epoch_id[build.epoch.epoch_id] = build.execution_authority
    if reason == DecisionEpochReason.SNAPSHOT:
        _store_current_epoch(session_id, build.epoch)
    return build.epoch


def _current_decision_epoch(session_id: str, session: Any) -> Optional[DecisionEpoch]:
    """Return the published active epoch while it still describes the turn."""
    epoch = _current_epoch_by_session.get(session_id)
    if epoch is None or sim.encounter is None or sim.game is None:
        return None
    active_uuid = sim.game.active_entity_uuid
    if (
        sim.encounter.turn_state != TurnState.IN_PROGRESS
        or active_uuid is None
        or str(active_uuid) != epoch.actor_uuid
        or active_uuid not in session.controlled_entities
        or sim.encounter.round_number != epoch.round_number
        or sim.encounter.current_turn_index != epoch.turn_index
    ):
        _forget_current_epoch(session_id)
        return None
    return epoch


def _snapshot_with_epoch(session_id: str) -> ObservationSnapshot:
    """Build a subjective snapshot and attach the current epoch when present."""
    snapshot = build_observation_snapshot(session_id, session_manager=sim.get_session_manager())
    epoch = _build_decision_epoch(
        session_id,
        DecisionEpochReason.SNAPSHOT,
        phase_prefix="build.current_epoch",
    )
    return snapshot.model_copy(update={"current_epoch": epoch})


def _find_affordance(epoch: DecisionEpoch, row_id: str) -> Optional[ActionAffordance]:
    """Return the affordance row selected by row id."""
    return epoch.affordances.row_by_id(row_id)


def _find_execution_binding(
    epoch: DecisionEpoch,
    affordance: ActionAffordance,
) -> Optional[ActionExecutionBinding]:
    """Return private exact engine authority for one current epoch row."""
    authority = _execution_authority_by_epoch_id.get(epoch.epoch_id)
    return authority.binding_for(affordance) if authority is not None else None


def _command_result(
    status: CommandResultStatus,
    session_id: str,
    *,
    command_id: Optional[str] = None,
    actor_uuid: Optional[str] = None,
    requested_epoch_id: Optional[str] = None,
    current_epoch_id: Optional[str] = None,
    row_id: Optional[str] = None,
    action_resolution: Optional[ActionResolutionStatus] = None,
    outcome_code: Optional[str] = None,
    revalidation_required: bool = False,
    revalidation_reason: Optional[str] = None,
    message: str = "",
    payload: Optional[dict[str, Any]] = None,
    resync_required: bool = False,
) -> CommandResult:
    """Create a command result payload."""
    return CommandResult(
        status=status,
        command_id=command_id,
        session_id=session_id,
        actor_uuid=actor_uuid,
        requested_epoch_id=requested_epoch_id,
        current_epoch_id=current_epoch_id,
        row_id=row_id,
        action_resolution=action_resolution,
        outcome_code=outcome_code,
        revalidation_required=revalidation_required,
        revalidation_reason=revalidation_reason,
        message=message,
        payload=payload or {},
        resync_required=resync_required,
    )


def _with_server_timing(
    result: CommandResult,
    timing: _ServerCommandTiming,
) -> CommandResult:
    """Return a command result with current server timing attached."""
    payload = dict(result.payload)
    payload["server_timing"] = timing.payload()
    return result.model_copy(update={"payload": payload})


def _publish_command_result(
    session_id: str,
    result: CommandResult,
    *,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> CommandResult:
    """Append a command result to the subjective observation stream."""
    frame = append_command_result_frame(
        session_id,
        result,
        session_manager=sim.get_session_manager(),
        record_timing=record_timing,
    )
    return frame.command_result or result


def _publish_command_result_timed(
    session_id: str,
    result: CommandResult,
    timing: _ServerCommandTiming,
) -> CommandResult:
    """Publish a command result and account for publication time."""
    started = time.perf_counter()
    published = _publish_command_result(
        session_id,
        _with_server_timing(result, timing),
        record_timing=_prefixed_timing_recorder(timing, "publish.command_result"),
    )
    timing.add("publish.command_result_ms", started)
    return _with_server_timing(published, timing)


def _command_ack(result: CommandResult) -> CommandResult:
    """Return the small HTTP acknowledgement form of a command result."""
    payload: dict[str, Any] = {}
    if result.status != CommandResultStatus.ACCEPTED:
        return result.model_copy(update={"payload": _compact_command_failure_payload(result)})
    if "server_timing" in result.payload:
        payload["server_timing"] = result.payload["server_timing"]
    if "success" in result.payload:
        payload["success"] = result.payload["success"]
    if "turn_continues" in result.payload:
        payload["turn_continues"] = result.payload["turn_continues"]
    if "encounter_ended" in result.payload:
        payload["encounter_ended"] = result.payload["encounter_ended"]
    elif result.payload.get("status") == "encounter_ended":
        payload["encounter_ended"] = True
    return result.model_copy(update={"payload": payload})


def _compact_command_failure_payload(result: CommandResult) -> dict[str, Any]:
    """Return actionable failure details without objective game state."""
    payload: dict[str, Any] = {"message": result.message}
    source = result.payload if isinstance(result.payload, dict) else {}
    for key in ("code", "reason", "engine_message"):
        if key in source:
            payload[key] = source[key]
    if "server_timing" in source:
        payload["server_timing"] = source["server_timing"]
    detail = source.get("detail")
    if isinstance(detail, dict):
        payload["detail"] = {
            key: value
            for key, value in detail.items()
            if key != "available_actions"
        }
    elif detail is not None:
        payload["detail"] = detail
    action_result = source.get("action_result")
    if isinstance(action_result, dict):
        payload["action_result"] = {
            key: action_result.get(key)
            for key in (
                "success",
                "message",
                "event_type",
                "outcome_code",
                "turn_continues",
                "encounter_ended",
                "event_cursor_after",
                "combat_log_cursor_after",
            )
            if key in action_result
        }
    return payload


def _publish_command_result_ack(
    session_id: str,
    result: CommandResult,
) -> CommandResult:
    """Publish a detailed command result frame and return a small HTTP ack."""
    return _command_ack(_publish_command_result(session_id, result))


def _command_ack_with_timing(
    result: CommandResult,
    timing: _ServerCommandTiming,
) -> CommandResult:
    """Return a compact command ack with final server timing attached."""
    return _command_ack(_with_server_timing(result, timing))


def _publish_decision_epoch_for_session(
    session_id: str,
    reason: DecisionEpochReason,
    *,
    source_command_id: Optional[str] = None,
    timing: Optional[_ServerCommandTiming] = None,
    phase_prefix: str = "publish.followup_epoch",
) -> Optional[DecisionEpoch]:
    """Append a current decision epoch frame for a session when one exists."""
    started = time.perf_counter()
    epoch = _build_decision_epoch(
        session_id,
        reason,
        reuse_current=False,
        timing=timing,
        phase_prefix=phase_prefix,
    )
    if timing is not None:
        timing.add(f"{phase_prefix}.build_decision_epoch_total_ms", started)
    if epoch is None:
        return None
    started = time.perf_counter()
    last_key = f"{epoch.epoch_id}|cmd={source_command_id or ''}"
    if _last_published_epoch_by_session.get(session_id) == last_key:
        _store_current_epoch(session_id, epoch)
        if timing is not None:
            timing.add(f"{phase_prefix}.duplicate_epoch_cache_ms", started)
        return epoch
    if timing is not None:
        timing.add(f"{phase_prefix}.duplicate_epoch_check_ms", started)
    started = time.perf_counter()
    append_decision_epoch_frame(
        session_id,
        epoch,
        source_command_id=source_command_id,
        session_manager=sim.get_session_manager(),
        record_timing=_prefixed_timing_recorder(timing, phase_prefix),
    )
    if timing is not None:
        timing.add(f"{phase_prefix}.append_decision_epoch_total_ms", started)
    started = time.perf_counter()
    _last_published_epoch_by_session[session_id] = last_key
    _store_current_epoch(session_id, epoch)
    if timing is not None:
        timing.add(f"{phase_prefix}.store_current_epoch_ms", started)
    return epoch


def _publish_epoch_clear_for_session(
    session_id: str,
    reason: str,
    *,
    source_command_id: Optional[str] = None,
    actor_uuid: Optional[str] = None,
) -> None:
    """Append an epoch-clear frame and forget the matching active epoch."""
    current = _current_epoch_by_session.get(session_id)
    if actor_uuid is not None and current is not None and current.actor_uuid != actor_uuid:
        return
    append_epoch_clear_frame(
        session_id,
        reason=reason,
        source_command_id=source_command_id,
        session_manager=sim.get_session_manager(),
    )
    if actor_uuid is None or current is None or current.actor_uuid == actor_uuid:
        _last_published_epoch_by_session.pop(session_id, None)
        _forget_current_epoch(session_id)


def _publish_post_command_control(
    session_id: str,
    *,
    command_id: Optional[str],
    actor_uuid: str,
    next_epoch_reason: DecisionEpochReason,
    clear_reason: str,
    timing: Optional[_ServerCommandTiming] = None,
) -> Optional[DecisionEpoch]:
    """Publish exactly one correlated control boundary after a command result."""
    next_epoch = _publish_decision_epoch_for_session(
        session_id,
        next_epoch_reason,
        source_command_id=command_id,
        timing=timing,
        phase_prefix="publish.followup_epoch",
    )
    if next_epoch is not None:
        return next_epoch
    _publish_epoch_clear_for_session(
        session_id,
        clear_reason,
        source_command_id=command_id,
        actor_uuid=actor_uuid,
    )
    _publish_decision_epoch_for_active_session(
        DecisionEpochReason.TURN_START,
        timing=timing,
    )
    return None


def _publish_decision_epoch_for_active_session(
    reason: DecisionEpochReason,
    *,
    timing: Optional[_ServerCommandTiming] = None,
) -> Optional[DecisionEpoch]:
    """Append a decision epoch for the currently active session when possible."""
    started = time.perf_counter()
    game = sim.game
    if timing is not None:
        timing.add("advance.publish_active_epoch.resolve_game_ms", started)
    if game is None:
        return None
    started = time.perf_counter()
    active_player = game.active_player
    if timing is not None:
        timing.add("advance.publish_active_epoch.resolve_active_player_ms", started)
    if active_player is None:
        return None
    if active_player.player_type == PlayerType.HUMAN:
        started = time.perf_counter()
        if timing is not None:
            timing.add("advance.publish_active_epoch.skip_human_session_ms", started)
        return None
    session_id = str(active_player.session_id)
    if (
        active_player.player_type == PlayerType.CODEX
        and not observation_wakeup_stream.has_subscribers(session_id)
        and not ai_takeover_manager.has_active_session_claim(active_player.session_id)
    ):
        started = time.perf_counter()
        if timing is not None:
            timing.add("advance.publish_active_epoch.skip_unwatched_codex_session_ms", started)
        return None
    started = time.perf_counter()
    epoch = _publish_decision_epoch_for_session(
        session_id,
        reason,
        timing=timing,
        phase_prefix="advance.publish_active_epoch",
    )
    if timing is not None:
        timing.add("advance.publish_active_epoch.publish_session_total_ms", started)
    return epoch


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


@app.get("/entity/{entity_uuid}/available-actions", response_model=APIAvailableActions)
async def get_entity_available_actions(entity_uuid: str, session_id: str):
    """Get action affordances for an entity controlled by the session."""
    entity = validate_session_action(session_id, entity_uuid)

    actions = get_available_actions(entity)

    _available_actions_cache[entity_uuid] = actions

    return serialize_available_actions(entity, actions)


@app.post("/ai/takeover", response_model=TakeoverClaimResponse)
async def create_ai_takeover(request: TakeoverRequest):
    """Claim combatants for Codex control without spawning a subprocess."""
    if sim.encounter is None or sim.game is None:
        raise _api_http_exception(
            status_code=400,
            code="no_active_game",
            message="No active game is available for takeover",
        )

    session_id = _parse_optional_uuid(request.session_id, "session_id")
    entity_uuids = _parse_uuid_list(request.entity_uuids, "entity_uuid")
    manager = sim.get_session_manager()
    subjective_authority_before = _capture_subjective_session_authority(manager)
    ownership_boundary = prepare_observation_ownership_change(manager)
    try:
        claim = ai_takeover_manager.claim(
            encounter=sim.encounter,
            game=sim.game,
            session_manager=sim.get_session_manager(),
            faction=request.faction,
            entity_uuids=entity_uuids,
            session_id=session_id,
            name=request.name,
            force=request.force,
            lease_seconds=request.lease_seconds,
        )
    except TakeoverError as error:
        raise _takeover_http_exception(error, faction=request.faction, entity_uuids=request.entity_uuids)

    _publish_takeover_ownership_changes(
        ownership_boundary,
        "takeover_claimed",
        subjective_authority_before=subjective_authority_before,
    )
    return serialize_takeover_claim(claim)


@app.get("/ai/takeover", response_model=TakeoverListResponse)
async def list_ai_takeovers():
    """List active Codex takeover claims."""
    restore_expired_takeovers()
    return TakeoverListResponse(
        claims=[
            serialize_takeover_claim(claim)
            for claim in ai_takeover_manager.active_claims()
        ],
    )


@app.get("/ai/policy/source", response_model=PolicySourceManifest)
async def get_policy_source():
    """Return explicitly supplied client policy diagnostics."""
    if _policy_source_manifest is None:
        raise _api_http_exception(
            status_code=503,
            code="policy_source_unavailable",
            message="No client policy source manifest is configured",
        )
    return _policy_source_manifest


@app.post("/ai/takeover/{claim_id}/heartbeat", response_model=TakeoverHeartbeatResponse)
async def heartbeat_ai_takeover(claim_id: str):
    """Refresh a takeover claim lease."""
    parsed_claim_id = _parse_optional_uuid(claim_id, "claim_id")
    if parsed_claim_id is None:
        raise _api_http_exception(status_code=400, code="invalid_claim_id", message="Invalid claim UUID")
    restore_expired_takeovers()
    claim = ai_takeover_manager.heartbeat(parsed_claim_id)
    if claim is None:
        raise _api_http_exception(
            status_code=404,
            code="takeover_not_found",
            message="Takeover claim not found",
            claim_id=claim_id,
        )
    return TakeoverHeartbeatResponse(status="heartbeat", claim=serialize_takeover_claim(claim))


@app.post("/ai/takeover/{claim_id}/release", response_model=TakeoverReleaseResponse)
async def release_ai_takeover(claim_id: str):
    """Release a takeover claim and restore previous controllers."""
    parsed_claim_id = _parse_optional_uuid(claim_id, "claim_id")
    if parsed_claim_id is None:
        raise _api_http_exception(status_code=400, code="invalid_claim_id", message="Invalid claim UUID")
    manager = sim.get_session_manager()
    subjective_authority_before = _capture_subjective_session_authority(manager)
    ownership_boundary = prepare_observation_ownership_change(manager)
    claim = ai_takeover_manager.release(parsed_claim_id, sim.encounter, sim.game)
    if claim is None:
        raise _api_http_exception(
            status_code=404,
            code="takeover_not_found",
            message="Takeover claim not found",
            claim_id=claim_id,
        )
    _publish_takeover_ownership_changes(
        ownership_boundary,
        "takeover_released",
        subjective_authority_before=subjective_authority_before,
    )
    advance_result = await advance_encounter() if sim.encounter is not None else None
    return TakeoverReleaseResponse(
        status="released",
        claim=serialize_takeover_claim(claim),
        advance_result=advance_result,
    )


@app.get("/ai/sessions", response_model=AgentSessionListResponse)
async def list_ai_observer_sessions(include_empty: bool = False):
    """List AI/Codex sessions available to telemetry observers.

    Args:
        include_empty: Whether to include sessions with no controlled entities
            and no live takeover claim.

    Returns:
        Read-only session rows containing telemetry cursors and owned entity
        labels. The payload intentionally omits objective state, visibility,
        HP, positions, legal actions, and enemy facts.
    """
    restore_expired_takeovers()
    manager = sim.get_session_manager()
    game = sim.game
    claim_ids_by_session: dict[UUID, list[str]] = {}
    for claim in ai_takeover_manager.active_claims():
        claim_ids_by_session.setdefault(claim.session_id, []).append(str(claim.claim_id))

    rows = []
    for session in sorted(manager.sessions.values(), key=lambda row: (row.player_type.value, row.name, str(row.session_id))):
        if session.player_type not in (PlayerType.AI, PlayerType.CODEX):
            continue
        claim_ids = sorted(claim_ids_by_session.get(session.session_id, []))
        if not include_empty and not session.controlled_entities and not claim_ids:
            continue
        rows.append(_serialize_agent_session_row(str(session.session_id), claim_ids))

    return AgentSessionListResponse(
        sessions=rows,
        active_game_id=str(game.game_id) if game else None,
        encounter_active=bool(game and game.encounter is not None and game.encounter.state.value == "active"),
    )


@app.get(
    "/ai/sessions/{session_id}/observation/snapshot",
    response_model=ObservationSnapshot,
)
async def get_ai_observation_snapshot(session_id: str):
    """Return a strict session-subjective observation snapshot."""
    try:
        return _snapshot_with_epoch(session_id)
    except ObservationAccessError as error:
        raise _observation_http_exception(error, session_id=session_id)


@app.get(
    "/ai/sessions/{session_id}/observation/frames",
    response_model=ObservationFramesResponse,
)
async def get_ai_observation_frames(
    session_id: str,
    since: int = 0,
    limit: int = 50,
):
    """Return replayable strict session-subjective observation frames."""
    try:
        return iter_observation_frames(
            session_id,
            since=since,
            limit=limit,
            session_manager=sim.get_session_manager(),
        )
    except ObservationAccessError as error:
        raise _observation_http_exception(error, session_id=session_id)


@app.get("/ai/sessions/{session_id}/observation/subscribe")
async def subscribe_ai_observation(
    request: Request,
    session_id: str,
    since: int = 0,
):
    """Subscribe to strict session-subjective observation frames."""

    async def event_generator():
        cursor = max(0, since)
        subjective_subscription = observation_wakeup_stream.subscribe(session_id)
        try:
            snapshot = _snapshot_with_epoch(session_id)
        except ObservationAccessError as error:
            observation_wakeup_stream.unsubscribe(session_id, subjective_subscription)
            yield format_sse(
                "error",
                {"code": error.code, "message": error.message},
            )
            return

        try:
            if cursor > snapshot.observation_cursor:
                yield format_sse(
                    "error",
                    {
                        "code": "observation_cursor_ahead",
                        "message": (
                            f"Requested cursor {cursor} is ahead of current "
                            f"cursor {snapshot.observation_cursor}."
                        ),
                    },
                )
                return
            yield format_sse(
                "sync",
                {
                    "observation_cursor": snapshot.observation_cursor,
                    "source_event_cursor": snapshot.source_event_cursor,
                    "source_combat_log_cursor": snapshot.source_combat_log_cursor,
                    "current_epoch_id": snapshot.current_epoch.epoch_id if snapshot.current_epoch else None,
                },
                f"o={snapshot.observation_cursor}",
            )

            try:
                replay = iter_observation_frames(
                    session_id,
                    since=cursor,
                    limit=0,
                    session_manager=sim.get_session_manager(),
                )
            except ObservationAccessError as error:
                yield format_sse(
                    "error",
                    {"code": error.code, "message": error.message},
                )
                return
            for frame in replay.frames:
                cursor = frame.observation_cursor
                yield format_sse(
                    "observation_frame",
                    frame,
                    f"o={frame.observation_cursor}",
                )
            while True:
                if await request.is_disconnected():
                    break
                envelope = await _first_subscription_envelope(
                    [subjective_subscription],
                    timeout=10.0,
                )
                if envelope is None:
                    current_snapshot = _snapshot_with_epoch(session_id)
                    yield format_sse(
                        "heartbeat",
                        {
                            "server_time": time.time(),
                            "observation_cursor": current_snapshot.observation_cursor,
                            "source_event_cursor": current_snapshot.source_event_cursor,
                            "source_combat_log_cursor": current_snapshot.source_combat_log_cursor,
                            "current_epoch_id": (
                                current_snapshot.current_epoch.epoch_id
                                if current_snapshot.current_epoch is not None
                                else None
                            ),
                        },
                        f"o={current_snapshot.observation_cursor}",
                    )
                    continue

                if envelope["event"] == "evicted":
                    yield format_sse(
                        "evicted",
                        envelope["data"],
                        envelope.get("id"),
                    )
                    break

                frame_data = envelope.get("data")
                frame = (
                    frame_data
                    if isinstance(frame_data, ObservationFrame)
                    else ObservationFrame.model_validate(frame_data)
                )
                if frame.observation_cursor <= cursor:
                    continue
                if frame.observation_cursor == cursor + 1:
                    cursor = frame.observation_cursor
                    yield format_sse(
                        "observation_frame",
                        frame,
                        f"o={frame.observation_cursor}",
                    )
                    continue

                try:
                    response = iter_observation_frames(
                        session_id,
                        since=cursor,
                        limit=0,
                        session_manager=sim.get_session_manager(),
                    )
                except ObservationAccessError as error:
                    yield format_sse(
                        "error",
                        {"code": error.code, "message": error.message},
                    )
                    break
                for frame in response.frames:
                    cursor = frame.observation_cursor
                    yield format_sse(
                        "observation_frame",
                        frame,
                        f"o={frame.observation_cursor}",
                    )
        finally:
            observation_wakeup_stream.unsubscribe(session_id, subjective_subscription)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post(
    "/ai/sessions/{session_id}/commands/execute",
    response_model=CommandResult,
)
async def execute_ai_session_command(
    session_id: str,
    request: AgentExecuteCommandRequest,
):
    """Execute one row from the session's current decision epoch."""
    timing = _ServerCommandTiming(
        "execute",
        diagnostics_enabled=request.include_diagnostics,
    )
    started = time.perf_counter()
    epoch = _build_decision_epoch(session_id, DecisionEpochReason.SNAPSHOT)
    timing.add("build.current_epoch_ms", started)
    if epoch is None:
        result = _command_result(
            CommandResultStatus.REJECTED,
            session_id,
            command_id=request.command_id,
            actor_uuid=request.actor_uuid,
            requested_epoch_id=request.basis_epoch_id,
            row_id=request.row_id,
            message="Session does not currently control an active actor.",
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        started = time.perf_counter()
        _publish_epoch_clear_for_session(
            session_id,
            "no_active_actor",
            source_command_id=request.command_id,
            actor_uuid=request.actor_uuid,
        )
        timing.add("publish.epoch_clear_ms", started)
        return _command_ack_with_timing(published, timing)

    if epoch.epoch_id != request.basis_epoch_id or epoch.actor_uuid != request.actor_uuid:
        result = _command_result(
            CommandResultStatus.STALE,
            session_id,
            command_id=request.command_id,
            actor_uuid=request.actor_uuid,
            requested_epoch_id=request.basis_epoch_id,
            current_epoch_id=epoch.epoch_id,
            row_id=request.row_id,
            message="Command was based on a stale decision epoch.",
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        started = time.perf_counter()
        _publish_decision_epoch_for_session(
            session_id,
            DecisionEpochReason.ACTION_STALE,
            source_command_id=request.command_id,
            timing=timing,
            phase_prefix="publish.followup_epoch",
        )
        timing.add("publish.followup_epoch_ms", started)
        return _command_ack_with_timing(published, timing)

    started = time.perf_counter()
    affordance = _find_affordance(epoch, request.row_id)
    timing.add("validate.find_affordance_ms", started)
    if affordance is None:
        result = _command_result(
            CommandResultStatus.REJECTED,
            session_id,
            command_id=request.command_id,
            actor_uuid=request.actor_uuid,
            requested_epoch_id=request.basis_epoch_id,
            current_epoch_id=epoch.epoch_id,
            row_id=request.row_id,
            message="Decision epoch row id is not available.",
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        started = time.perf_counter()
        _publish_decision_epoch_for_session(
            session_id,
            DecisionEpochReason.ACTION_REJECTED,
            source_command_id=request.command_id,
            timing=timing,
            phase_prefix="publish.followup_epoch",
        )
        timing.add("publish.followup_epoch_ms", started)
        return _command_ack_with_timing(published, timing)

    if affordance.bucket == "special_commands":
        return await _end_ai_session_turn_from_epoch(
            session_id,
            request.actor_uuid,
            request.basis_epoch_id,
            command_id=request.command_id,
            include_diagnostics=request.include_diagnostics,
        )

    if not affordance.can_afford or not affordance.targets:
        reason = "Decision epoch row is not affordable." if not affordance.can_afford else "Decision epoch row has no legal target."
        result = _command_result(
            CommandResultStatus.REJECTED,
            session_id,
            command_id=request.command_id,
            actor_uuid=request.actor_uuid,
            requested_epoch_id=request.basis_epoch_id,
            current_epoch_id=epoch.epoch_id,
            row_id=request.row_id,
            message=reason,
            payload={
                "code": "row_not_executable",
                "reason": reason,
            },
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        started = time.perf_counter()
        _publish_decision_epoch_for_session(
            session_id,
            DecisionEpochReason.ACTION_REJECTED,
            source_command_id=request.command_id,
            timing=timing,
            phase_prefix="publish.followup_epoch",
        )
        timing.add("publish.followup_epoch_ms", started)
        return _command_ack_with_timing(published, timing)

    try:
        extra_target_uuids = affordance.validated_extra_target_uuids(
            request.extra_target_uuids or (),
        )
    except ValueError as exc:
        result = _command_result(
            CommandResultStatus.REJECTED,
            session_id,
            command_id=request.command_id,
            actor_uuid=request.actor_uuid,
            requested_epoch_id=request.basis_epoch_id,
            current_epoch_id=epoch.epoch_id,
            row_id=request.row_id,
            message="Command target allocation is not authorized by the decision epoch.",
            payload={
                "code": "invalid_target_allocation",
                "reason": str(exc),
            },
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        started = time.perf_counter()
        _publish_decision_epoch_for_session(
            session_id,
            DecisionEpochReason.ACTION_REJECTED,
            source_command_id=request.command_id,
            timing=timing,
            phase_prefix="publish.followup_epoch",
        )
        timing.add("publish.followup_epoch_ms", started)
        return _command_ack_with_timing(published, timing)

    execution_binding = _find_execution_binding(epoch, affordance)
    if execution_binding is None:
        result = _command_result(
            CommandResultStatus.STALE,
            session_id,
            command_id=request.command_id,
            actor_uuid=request.actor_uuid,
            requested_epoch_id=request.basis_epoch_id,
            current_epoch_id=epoch.epoch_id,
            row_id=request.row_id,
            message="Decision epoch execution authority is no longer available.",
            payload={"code": "execution_authority_unavailable"},
            resync_required=True,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        return _command_ack_with_timing(published, timing)

    target = affordance.targets[0]
    started = time.perf_counter()
    semantics = epoch.affordances.semantics_for(affordance)
    movement_guard = None
    if ActionTag.MOVEMENT_VOLUNTARY in semantics.tags:
        movement_guard = SessionMovementContinuationGuard.from_world(
            get_materialized_observation_world(
                session_id,
                session_manager=sim.get_session_manager(),
            ),
            request.actor_uuid,
        )
    timing.add("execute.build_movement_guard_ms", started)
    try:
        started = time.perf_counter()
        execution_scope = (
            movement_continuation_scope(movement_guard)
            if movement_guard is not None
            else nullcontext()
        )
        with execution_scope:
            execution = await _execute_action_by_index_impl(
                ExecuteByIndexRequest(
                    session_id=session_id,
                    entity_uuid=request.actor_uuid,
                    template_name=affordance.template_name,
                    target_index=target.index,
                    extra_target_uuids=list(extra_target_uuids)
                    if extra_target_uuids
                    else None,
                    prefer_safe=request.prefer_safe,
                    return_available_actions=False,
                    include_timing=request.include_diagnostics,
                ),
                execution_binding=execution_binding,
            )
            result = execution.response
        if movement_guard is not None:
            for sample_ms in movement_guard.processing_samples_ms:
                timing.add_elapsed(
                    "execute.movement_revalidation_ms",
                    sample_ms,
                )
        timing.add("execute.action_by_index_ms", started)
    except HTTPException as exc:
        timing.add("execute.action_by_index_ms", started)
        result = _command_result(
            CommandResultStatus.REJECTED,
            session_id,
            command_id=request.command_id,
            actor_uuid=request.actor_uuid,
            requested_epoch_id=request.basis_epoch_id,
            current_epoch_id=epoch.epoch_id,
            row_id=request.row_id,
            message="Command was rejected by the engine.",
            payload={"detail": exc.detail},
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        started = time.perf_counter()
        _publish_decision_epoch_for_session(
            session_id,
            DecisionEpochReason.ACTION_REJECTED,
            source_command_id=request.command_id,
            timing=timing,
            phase_prefix="publish.followup_epoch",
        )
        timing.add("publish.followup_epoch_ms", started)
        return _command_ack_with_timing(published, timing)

    started = time.perf_counter()
    result_payload = _safe_action_result_payload(result)
    timing.add("serialize.safe_action_result_ms", started)
    if _action_result_ends_actor_turn(result_payload):
        started = time.perf_counter()
        advance_result = await _advance_after_non_continuing_action(
            request.actor_uuid,
            publish_decision_epoch=False,
        )
        timing.add("advance.after_non_continuing_action_ms", started)
        if advance_result is not None:
            result_payload["encounter_ended"] = advance_result.status == "encounter_ended"

    action_resolution = _command_action_resolution(execution)
    revalidation_reason = _command_revalidation_reason(execution)
    result = _command_result(
        CommandResultStatus.ACCEPTED,
        session_id,
        command_id=request.command_id,
        actor_uuid=request.actor_uuid,
        requested_epoch_id=request.basis_epoch_id,
        current_epoch_id=None,
        row_id=request.row_id,
        action_resolution=action_resolution,
        outcome_code=result.outcome_code,
        revalidation_required=revalidation_reason is not None,
        revalidation_reason=revalidation_reason,
        message=result.message,
        payload=result_payload,
        resync_required=False,
    )
    published = _publish_command_result_timed(session_id, result, timing)
    started = time.perf_counter()
    next_epoch = _publish_post_command_control(
        session_id,
        command_id=request.command_id,
        actor_uuid=request.actor_uuid,
        next_epoch_reason=(
            DecisionEpochReason.TURN_START
            if _action_result_ends_actor_turn(result_payload)
            else _followup_epoch_reason(
                result.action_resolution,
                revalidation_required=result.revalidation_required,
            )
        ),
        clear_reason=(
            result.action_resolution.value
            if result.action_resolution is not None
            else "action_completed"
        ),
        timing=timing,
    )
    timing.add("publish.post_command_control_ms", started)
    if published.current_epoch_id is None and next_epoch is not None:
        published = published.model_copy(update={"current_epoch_id": next_epoch.epoch_id})
    return _command_ack_with_timing(published, timing)


def _command_action_resolution(execution: _ActionExecutionResult) -> ActionResolutionStatus:
    """Map one engine action response to the controller protocol result."""
    result = execution.response
    if result.outcome_code == "movement.subjective_revalidation":
        if execution.movement_termination_reason == "completed":
            return ActionResolutionStatus.COMPLETED
        return ActionResolutionStatus.INTERRUPTED
    if result.success:
        return ActionResolutionStatus.COMPLETED
    return ActionResolutionStatus.CANCELED


def _followup_epoch_reason(
    resolution: ActionResolutionStatus | None,
    *,
    revalidation_required: bool = False,
) -> DecisionEpochReason:
    """Return the epoch reason corresponding to an accepted action result."""
    if revalidation_required:
        return DecisionEpochReason.MOVEMENT_REVALIDATION
    if resolution is ActionResolutionStatus.INTERRUPTED:
        return DecisionEpochReason.MOVEMENT_REVALIDATION
    if resolution is ActionResolutionStatus.CANCELED:
        return DecisionEpochReason.ACTION_CANCELED
    return DecisionEpochReason.ACTION_COMPLETED


def _command_revalidation_reason(execution: _ActionExecutionResult) -> Optional[str]:
    """Return the typed controller revalidation cause from movement data."""
    result = execution.response
    if result.outcome_code != "movement.subjective_revalidation":
        return None
    reason = execution.movement_revalidation_reason
    return reason if isinstance(reason, str) and reason else None


def _action_result_ends_actor_turn(payload: dict[str, Any]) -> bool:
    """Return whether an accepted action result says the actor cannot continue."""
    return payload.get("turn_continues") is False and payload.get("encounter_ended") is not True


async def _advance_after_non_continuing_action(
    actor_uuid: str,
    *,
    publish_decision_epoch: bool = True,
) -> Optional[AdvanceEncounterResult]:
    """Advance when the active actor died or otherwise cannot continue after a command."""
    if sim.encounter is None or sim.game is None or sim.encounter.state != EncounterState.ACTIVE:
        return None
    active_uuid = sim.game.active_entity_uuid
    if active_uuid is None or str(active_uuid) != actor_uuid:
        return None

    _available_actions_cache.clear()
    sim.encounter.end_turn()
    sim.encounter.current_turn_index += 1
    if sim.encounter.current_turn_index >= len(sim.encounter.initiative_order):
        sim.encounter._advance_round()
    sim.encounter.turn_state = TurnState.NOT_STARTED
    if sim.activation_identity is not None:
        result = _scheduled_advance_result()
        _schedule_activated_game_coordinator()
        return result
    return await advance_encounter(
        publish_decision_epoch=publish_decision_epoch,
    )


@app.post(
    "/ai/sessions/{session_id}/commands/end-turn",
    response_model=CommandResult,
)
async def end_ai_session_turn(
    session_id: str,
    request: AgentEndTurnCommandRequest,
):
    """End the actor turn from the session's current decision epoch."""
    return await _end_ai_session_turn_from_epoch(
        session_id,
        request.actor_uuid,
        request.basis_epoch_id,
        command_id=request.command_id,
        include_diagnostics=request.include_diagnostics,
    )


async def _end_ai_session_turn_from_epoch(
    session_id: str,
    actor_uuid: str,
    basis_epoch_id: str,
    *,
    command_id: Optional[str] = None,
    include_diagnostics: bool = False,
) -> CommandResult:
    """Validate an epoch and end the active actor turn."""
    timing = _ServerCommandTiming(
        "end_turn",
        diagnostics_enabled=include_diagnostics,
    )
    started = time.perf_counter()
    epoch = _build_decision_epoch(
        session_id,
        DecisionEpochReason.SNAPSHOT,
        timing=timing,
        phase_prefix="build.current_epoch",
    )
    timing.add("build.current_epoch_ms", started)
    if epoch is None:
        result = _command_result(
            CommandResultStatus.REJECTED,
            session_id,
            command_id=command_id,
            actor_uuid=actor_uuid,
            requested_epoch_id=basis_epoch_id,
            row_id=END_TURN_ROW_ID,
            message="Session does not currently control an active actor.",
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        started = time.perf_counter()
        _publish_epoch_clear_for_session(
            session_id,
            "no_active_actor",
            source_command_id=command_id,
            actor_uuid=actor_uuid,
        )
        timing.add("publish.epoch_clear_ms", started)
        return _command_ack_with_timing(published, timing)
    if epoch.epoch_id != basis_epoch_id or epoch.actor_uuid != actor_uuid:
        result = _command_result(
            CommandResultStatus.STALE,
            session_id,
            command_id=command_id,
            actor_uuid=actor_uuid,
            requested_epoch_id=basis_epoch_id,
            current_epoch_id=epoch.epoch_id,
            row_id=END_TURN_ROW_ID,
            message="End-turn command was based on a stale decision epoch.",
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        started = time.perf_counter()
        _publish_decision_epoch_for_session(
            session_id,
            DecisionEpochReason.ACTION_STALE,
            source_command_id=command_id,
            timing=timing,
            phase_prefix="publish.followup_epoch",
        )
        timing.add("publish.followup_epoch_ms", started)
        return _command_ack_with_timing(published, timing)
    try:
        started = time.perf_counter()
        result = await _end_turn_and_advance(
            session_id,
            actor_uuid,
            timing=timing,
            publish_decision_epoch=False,
        )
        timing.add("end_turn.total_route_ms", started)
    except HTTPException as exc:
        command_result = _command_result(
            CommandResultStatus.REJECTED,
            session_id,
            command_id=command_id,
            actor_uuid=actor_uuid,
            requested_epoch_id=basis_epoch_id,
            current_epoch_id=epoch.epoch_id,
            row_id=END_TURN_ROW_ID,
            message="End-turn command was rejected by the engine.",
            payload={"detail": exc.detail},
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, command_result, timing)
        started = time.perf_counter()
        _publish_decision_epoch_for_session(
            session_id,
            DecisionEpochReason.ACTION_REJECTED,
            source_command_id=command_id,
            timing=timing,
            phase_prefix="publish.followup_epoch",
        )
        timing.add("publish.followup_epoch_ms", started)
        return _command_ack_with_timing(published, timing)

    started = time.perf_counter()
    payload = _safe_advance_result_payload(result)
    timing.add("serialize.advance_result_ms", started)
    command_result = _command_result(
        CommandResultStatus.ACCEPTED,
        session_id,
        command_id=command_id,
        actor_uuid=actor_uuid,
        requested_epoch_id=basis_epoch_id,
        current_epoch_id=None,
        row_id=END_TURN_ROW_ID,
        message="Turn ended.",
        payload=payload,
        resync_required=False,
    )
    published = _publish_command_result_timed(session_id, command_result, timing)
    started = time.perf_counter()
    next_epoch = _publish_post_command_control(
        session_id,
        command_id=command_id,
        actor_uuid=actor_uuid,
        next_epoch_reason=DecisionEpochReason.TURN_START,
        clear_reason="turn_ended",
        timing=timing,
    )
    timing.add("publish.post_command_control_ms", started)
    if published.current_epoch_id is None and next_epoch is not None:
        published = published.model_copy(update={"current_epoch_id": next_epoch.epoch_id})
    return _command_ack_with_timing(published, timing)


def _safe_action_result_payload(result: ActionResult) -> dict[str, Any]:
    """Return protocol outcome metadata while gameplay arrives through events."""
    payload: dict[str, Any] = {
        "success": result.success,
        "turn_continues": result.turn_continues,
        "encounter_ended": result.encounter_ended,
    }
    action_timing = result.server_timing
    if action_timing is not None:
        payload["action_server_timing"] = action_timing
    return payload


def _safe_advance_result_payload(result: AdvanceEncounterResult) -> dict[str, Any]:
    """Return advancement protocol state without raw automated-controller facts."""
    return {
        "status": result.status,
        "encounter_ended": result.status == "encounter_ended",
    }


@app.post("/ai/sessions/{session_id}/agent-events")
async def post_agent_events(
    session_id: str,
    request: AgentEventIngestRequest,
):
    """Append agent telemetry events to the per-session stream."""
    session = _require_agent_stream_session(session_id)
    rows = []
    for event in request.events:
        actor_uuid = None
        if event.actor_uuid is not None:
            try:
                actor_uuid = UUID(event.actor_uuid)
            except ValueError:
                raise _api_http_exception(
                    status_code=400,
                    code="invalid_agent_event_actor_uuid",
                    message="Agent event actor UUID is invalid.",
                    session_id=session_id,
                    actor_uuid=event.actor_uuid,
                )
        if actor_uuid is not None and actor_uuid not in session.controlled_entities:
            raise _api_http_exception(
                status_code=403,
                code="agent_event_actor_not_controlled",
                message="Agent event actor is not controlled by this session.",
                session_id=session_id,
                actor_uuid=event.actor_uuid,
            )
        rows.append(agent_event_stream.publish(session_id, event))
    return {
        "events": [row.model_dump(mode="json") for row in rows],
        "count": len(rows),
        "total": agent_event_stream.current_agent_cursor(session_id),
        "next_agent_cursor": rows[-1].agent_cursor if rows else agent_event_stream.current_agent_cursor(session_id),
    }


@app.get(
    "/ai/sessions/{session_id}/agent-events",
    response_model=AgentEventHistoryResponse,
)
async def get_agent_events(
    session_id: str,
    since: int = 0,
    limit: int = 100,
):
    """Return agent telemetry events after a session-local cursor."""
    _require_agent_stream_session(session_id)
    rows = agent_event_stream.iter_agent_events_since(session_id, since, limit)
    return AgentEventHistoryResponse(
        events=rows,
        count=len(rows),
        total=agent_event_stream.current_agent_cursor(session_id),
        next_agent_cursor=rows[-1].agent_cursor if rows else max(0, since),
        earliest_agent_cursor=agent_event_stream.earliest_agent_cursor(session_id),
        resync_required=agent_event_stream.is_cursor_evicted(session_id, since),
    )


@app.get("/ai/sessions/{session_id}/agent-events/subscribe")
async def subscribe_agent_events(
    request: Request,
    session_id: str,
    since: int = 0,
):
    """Subscribe to per-session agent telemetry events."""
    _require_agent_stream_session(session_id)

    async def event_generator():
        cursor = max(0, since)
        subscription = agent_event_stream.subscribe(session_id)
        try:
            observation_cursor = _safe_observation_cursor(session_id)
            if agent_event_stream.is_cursor_evicted(session_id, cursor):
                yield format_sse(
                    "evicted",
                    EvictedPayload(reason="agent_history_evicted"),
                    agent_event_stream.current_stream_id(session_id, observation_cursor),
                )
                return
            epoch = _build_decision_epoch(session_id, DecisionEpochReason.SNAPSHOT)
            yield format_sse(
                "sync",
                agent_event_stream.sync_payload(
                    session_id,
                    observation_cursor=observation_cursor,
                    epoch_id=epoch.epoch_id if epoch else None,
                    session=_agent_stream_session_payload(session_id),
                ),
                agent_event_stream.current_stream_id(session_id, observation_cursor),
            )

            for payload in agent_event_stream.iter_agent_events_since(session_id, cursor, 500):
                cursor = payload.agent_cursor
                yield format_sse(
                    "agent_event",
                    payload,
                    agent_event_stream.current_stream_id(session_id, payload.observation_cursor),
                )

            while True:
                if await request.is_disconnected():
                    break
                try:
                    envelope = await asyncio.wait_for(subscription.get(), timeout=10.0)
                except asyncio.TimeoutError:
                    observation_cursor = _safe_observation_cursor(session_id)
                    epoch = _build_decision_epoch(session_id, DecisionEpochReason.SNAPSHOT)
                    yield format_sse(
                        "heartbeat",
                        agent_event_stream.heartbeat_payload(
                            session_id,
                            observation_cursor=observation_cursor,
                            epoch_id=epoch.epoch_id if epoch else None,
                            session=_agent_stream_session_payload(session_id),
                        ),
                        agent_event_stream.current_stream_id(session_id, observation_cursor),
                    )
                    continue

                if envelope["event"] == "evicted":
                    yield format_sse("evicted", envelope["data"], envelope.get("id"))
                    break
                payload = envelope["data"]
                if isinstance(payload, dict):
                    cursor = int(payload.get("agent_cursor", cursor))
                else:
                    cursor = getattr(payload, "agent_cursor", cursor)
                yield format_sse(envelope["event"], payload, envelope.get("id"))
        finally:
            agent_event_stream.unsubscribe(session_id, subscription)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


GAUNTLET_SUMMARY_DIRECTORY = Path(
    os.environ.get("DND_GAUNTLET_SUMMARY_DIRECTORY", "evidence/gauntlets")
)


@app.get("/ai/gauntlets/latest")
async def get_latest_gauntlet_summary():
    """Return the latest retained gauntlet summary JSON."""
    summary = _load_gauntlet_summary("latest")
    return summary.model_dump(mode="json")


@app.get("/ai/gauntlets/live/latest")
async def get_latest_live_gauntlet_watcher_state():
    """Return watcher state for the most recently observed live gauntlet."""
    gauntlet_id = gauntlet_event_stream.latest_gauntlet_id()
    if gauntlet_id is None:
        raise _api_http_exception(
            status_code=404,
            code="live_gauntlet_not_found",
            message="No live gauntlet watcher events are retained.",
        )
    events = gauntlet_event_stream.since(0, gauntlet_id=gauntlet_id, limit=0)
    return project_live_watcher_state(gauntlet_id, events).model_dump(mode="json")


@app.get("/ai/gauntlets/{gauntlet_id}/watch")
async def get_gauntlet_watcher_state(gauntlet_id: str):
    """Return the current watcher projection for a gauntlet."""
    live_events = gauntlet_event_stream.since(0, gauntlet_id=gauntlet_id, limit=0)
    try:
        summary = _load_gauntlet_summary(gauntlet_id)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        if not live_events:
            raise
        return project_live_watcher_state(gauntlet_id, live_events).model_dump(mode="json")
    events = live_events or summary.events
    return project_watcher_state(summary, events).model_dump(mode="json")


@app.get("/ai/gauntlets/{gauntlet_id}/events")
async def get_gauntlet_events(
    gauntlet_id: str,
    since: int = 0,
    limit: int = 100,
):
    """Return retained live watcher events after a gauntlet cursor."""
    _ensure_gauntlet_known(gauntlet_id)
    rows = gauntlet_event_stream.since(since, gauntlet_id=gauntlet_id, limit=limit)
    return {
        "events": [row.model_dump(mode="json") for row in rows],
        "count": len(rows),
        "total": gauntlet_event_stream.current_cursor(),
        "next_cursor": rows[-1].cursor if rows else max(0, since),
        "earliest_cursor": gauntlet_event_stream.earliest_cursor(gauntlet_id),
        "resync_required": gauntlet_event_stream.is_cursor_evicted(since, gauntlet_id),
    }


@app.post("/ai/gauntlets/events")
async def post_gauntlet_events(request: GauntletEventIngestRequest):
    """Publish externally produced gauntlet watcher events."""
    rows = [gauntlet_event_stream.publish(event) for event in request.events]
    return {
        "events": [row.model_dump(mode="json") for row in rows],
        "count": len(rows),
        "total": gauntlet_event_stream.current_cursor(),
        "next_cursor": rows[-1].cursor if rows else gauntlet_event_stream.current_cursor(),
    }


@app.get("/ai/gauntlets/{gauntlet_id}/events/subscribe")
async def subscribe_gauntlet_events(
    request: Request,
    gauntlet_id: str,
    since: int = 0,
):
    """Subscribe to live gauntlet watcher events."""
    _ensure_gauntlet_known(gauntlet_id)

    async def event_generator():
        cursor = max(0, since)
        subscription = gauntlet_event_stream.subscribe(gauntlet_id)
        try:
            if gauntlet_event_stream.is_cursor_evicted(cursor, gauntlet_id):
                yield format_sse(
                    "evicted",
                    EvictedPayload(reason="gauntlet_history_evicted"),
                    gauntlet_event_stream.current_stream_id(),
                )
                return
            yield format_sse(
                "sync",
                {
                    "gauntlet_id": gauntlet_id,
                    "cursor": gauntlet_event_stream.current_cursor(),
                    "earliest_cursor": gauntlet_event_stream.earliest_cursor(gauntlet_id),
                },
                gauntlet_event_stream.current_stream_id(),
            )
            for event in gauntlet_event_stream.since(cursor, gauntlet_id=gauntlet_id, limit=500):
                cursor = event.cursor
                yield format_sse("gauntlet_event", event, f"g={event.cursor}")

            while True:
                if await request.is_disconnected():
                    break
                try:
                    envelope = await asyncio.wait_for(subscription.get(), timeout=10.0)
                except asyncio.TimeoutError:
                    yield format_sse(
                        "heartbeat",
                        {
                            "gauntlet_id": gauntlet_id,
                            "cursor": gauntlet_event_stream.current_cursor(),
                            "server_time": time.time(),
                        },
                        gauntlet_event_stream.current_stream_id(),
                    )
                    continue

                if envelope["event"] == "evicted":
                    yield format_sse("evicted", envelope["data"], envelope.get("id"))
                    break
                payload = envelope["data"]
                cursor = payload.cursor if hasattr(payload, "cursor") else cursor
                yield format_sse(envelope["event"], payload, envelope.get("id"))
        finally:
            gauntlet_event_stream.unsubscribe(gauntlet_id, subscription)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _load_gauntlet_summary(gauntlet_id: str) -> GauntletSummary:
    """Load a retained gauntlet summary by id or latest pointer."""
    file_name = "latest.json" if gauntlet_id == "latest" else f"{gauntlet_id}.json"
    path = GAUNTLET_SUMMARY_DIRECTORY / file_name
    if not path.exists():
        raise _api_http_exception(
            status_code=404,
            code="gauntlet_summary_not_found",
            message="Gauntlet summary was not found.",
            gauntlet_id=gauntlet_id,
            path=str(path),
        )
    try:
        return apply_gauntlet_latency_audit(GauntletSummary.model_validate_json(path.read_text(encoding="utf-8")))
    except ValueError as exc:
        raise _api_http_exception(
            status_code=500,
            code="invalid_gauntlet_summary",
            message="Gauntlet summary JSON could not be parsed.",
            gauntlet_id=gauntlet_id,
            path=str(path),
            error=str(exc),
        ) from exc


def _ensure_gauntlet_known(gauntlet_id: str) -> None:
    """Accept a gauntlet id when it has retained JSON or live events."""
    if gauntlet_id == "latest":
        _load_gauntlet_summary("latest")
        return
    if gauntlet_event_stream.since(0, gauntlet_id=gauntlet_id, limit=1):
        return
    _load_gauntlet_summary(gauntlet_id)


def _serialize_agent_session_row(session_id: str, takeover_claim_ids: list[str]) -> AgentSessionRow:
    """Serialize one AI/Codex session for the observer index."""
    session = _require_agent_stream_session(session_id)
    game = sim.game
    active_uuid = game.active_entity_uuid if game else None
    is_active_turn = bool(active_uuid is not None and active_uuid in session.controlled_entities)
    active_entity = Entity.get(active_uuid) if is_active_turn and active_uuid is not None else None
    epoch = _current_decision_epoch(session_id, session)

    return AgentSessionRow(
        session_id=str(session.session_id),
        player_type=session.player_type.value,
        name=session.name,
        connection_status=session.connection_status.value,
        is_active_turn=is_active_turn,
        active_controlled_entity_uuid=str(active_uuid) if is_active_turn and active_uuid is not None else None,
        active_controlled_entity_name=active_entity.name if active_entity else None,
        controlled_entities=[
            _serialize_agent_session_entity(entity_uuid)
            for entity_uuid in sorted(session.controlled_entities, key=str)
        ],
        agent_cursor=agent_event_stream.current_agent_cursor(session_id),
        earliest_agent_cursor=agent_event_stream.earliest_agent_cursor(session_id),
        observation_cursor=_safe_observation_cursor(session_id),
        current_epoch_id=epoch.epoch_id if epoch is not None else None,
        takeover_claim_ids=takeover_claim_ids,
    )


def _serialize_agent_session_entity(entity_uuid: UUID) -> AgentSessionEntityRow:
    """Serialize a controlled entity label without tactical state."""
    entity = Entity.get(entity_uuid)
    controller_type = None
    if sim.encounter is not None and entity_uuid in sim.encounter.combatants:
        controller = sim.encounter.get_controller_for(entity_uuid)
        controller_type = controller.controller_type if controller is not None else None
    active_uuid = sim.game.active_entity_uuid if sim.game else None
    return AgentSessionEntityRow(
        entity_uuid=str(entity_uuid),
        entity_name=entity.name if entity is not None else str(entity_uuid),
        faction=entity.faction if entity is not None else None,
        controller_type=controller_type,
        is_active_actor=active_uuid == entity_uuid,
    )


def _require_agent_stream_session(session_id: str):
    """Resolve an agent-stream session or raise a structured error."""
    parsed = _parse_optional_uuid(session_id, "session_id")
    if parsed is None:
        raise _api_http_exception(status_code=400, code="invalid_session_id", message="Invalid session UUID")
    session = sim.get_session_manager().get_session(parsed)
    if session is None:
        raise _api_http_exception(
            status_code=404,
            code="session_not_found",
            message="Session not found",
            session_id=session_id,
        )
    return session


def _safe_observation_cursor(session_id: str) -> Optional[int]:
    """Return the current observation cursor, if the session is resolvable."""
    try:
        return get_observation_cursor(session_id, session_manager=sim.get_session_manager())
    except ObservationAccessError:
        return None


def _agent_stream_session_payload(session_id: str) -> Optional[dict[str, Any]]:
    """Return serialized session context for agent-event stream sync frames."""
    parsed = _parse_optional_uuid(session_id, "session_id")
    if parsed is None:
        return None
    session = sim.get_session_manager().get_session(parsed)
    return session.to_dict() if session else None


@app.get("/entity/{entity_uuid}/handlers", response_model=APIEntityHandlersResponse)
async def get_entity_handlers(entity_uuid: str, session_id: str) -> APIEntityHandlersResponse:
    """Get toggleable handlers for an entity controlled by the session."""
    entity = validate_session_action(session_id, entity_uuid)
    handlers = _serialize_entity_handlers(entity)
    return APIEntityHandlersResponse(entity_uuid=entity_uuid, handlers=handlers)


@app.post(
    "/entity/{entity_uuid}/handlers/{handler_name}/toggle",
    response_model=ToggleHandlerResponse,
)
async def toggle_entity_handler(
    entity_uuid: str,
    handler_name: str,
    request: ToggleHandlerRequest,
) -> ToggleHandlerResponse:
    """Toggle a handler's enabled state by name.

    Validates that the session owns the entity and it's their turn.
    """
    entity = validate_session_action(request.session_id, entity_uuid)

    found = entity.set_handler_enabled(handler_name, request.enabled)
    if not found:
        raise _handler_http_exception(
            entity=entity,
            status_code=404,
            code="handler_not_found",
            message=f"Handler '{handler_name}' not found",
            handler_name=handler_name,
        )

    return ToggleHandlerResponse(
        success=True,
        handler_name=handler_name,
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
    """End the session's entity turn and advance through AI turns."""
    return await _end_turn_and_advance(request.session_id, request.entity_uuid)


async def _end_turn_and_advance(
    session_id: str,
    entity_uuid: str,
    *,
    timing: Optional[_ServerCommandTiming] = None,
    publish_decision_epoch: bool = True,
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
            **_simulation_context(),
        )

    _available_actions_cache.clear()

    started = time.perf_counter()
    sim.encounter.end_turn()
    if timing is not None:
        timing.add("end_turn.encounter_end_turn_ms", started)

    started = time.perf_counter()
    sim.encounter.current_turn_index += 1
    if sim.encounter.current_turn_index >= len(sim.encounter.initiative_order):
        sim.encounter._advance_round()
    sim.encounter.turn_state = TurnState.NOT_STARTED
    if timing is not None:
        timing.add("end_turn.advance_turn_index_ms", started)

    if sim.activation_identity is not None:
        result = _scheduled_advance_result()
        _schedule_activated_game_coordinator()
        return result

    started = time.perf_counter()
    result = await advance_encounter(
        timing=timing,
        publish_decision_epoch=publish_decision_epoch,
    )
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
    execution_binding: Optional[ActionExecutionBinding] = None,
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
    action_info = (
        execution_binding.action_info
        if execution_binding is not None
        else next(
            (a for a in available.all_actions if a.template_name == request.template_name),
            None,
        )
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

    selected_target = execution_binding.target if execution_binding is not None else next(
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
    if encounter_ended and sim.encounter is not None:
        await _close_registered_ai_after_terminal(sim.encounter)

    updated_actions = None
    if request.return_available_actions and not encounter_ended and entity.has_hp:
        started = time.perf_counter()
        new_available = get_available_actions(entity)
        if timing is not None:
            timing.add("recompute_available_actions_ms", started)
        started = time.perf_counter()
        _available_actions_cache[request.entity_uuid] = new_available
        updated_actions = serialize_available_actions(entity, new_available)
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


def _game_creation_preflight(
    request: GameCreationPreflightRequest,
) -> CompatibilityReport:
    """Validate one composed scenario selection without constructing engine state.

    Args:
        request: Four canonical scenario component identifiers.

    Returns:
        Static compatibility report for the selected components.

    Raises:
        HTTPException: If a component identifier is unknown.
    """
    try:
        return run_game_creation_preflight(request)
    except GameCreationCatalogError as exc:
        raise _api_http_exception(
            status_code=400,
            code=exc.code,
            message=exc.message,
            **exc.context,
        ) from exc


def _game_creation_selection(
    scenario: GameCreationPresetScenario | GameCreationComposedScenario,
) -> tuple[GameCreationPreflightRequest, Optional[str]]:
    """Resolve a preset or composed selection to four canonical component ids.

    Args:
        scenario: Discriminated game-creation scenario request.

    Returns:
        Preflight request and optional historical preset identifier.

    Raises:
        HTTPException: If a preset identifier is unknown.
    """
    if isinstance(scenario, GameCreationComposedScenario):
        return GameCreationPreflightRequest(
            hero_configuration_id=scenario.hero_configuration_id,
            monster_configuration_id=scenario.monster_configuration_id,
            battlefield_id=scenario.battlefield_id,
            deployment_id=scenario.deployment_id,
        ), None
    try:
        recipe = get_legacy_recipe(scenario.arena_id)
    except ValueError as exc:
        raise _api_http_exception(
            status_code=400,
            code="invalid_game_creation_preset",
            message=str(exc),
            arena_id=scenario.arena_id,
            valid_arena_ids=[recipe.arena_id for recipe in LEGACY_RECIPES],
        ) from exc
    return GameCreationPreflightRequest(
        hero_configuration_id=recipe.hero_configuration_id,
        monster_configuration_id=recipe.monster_configuration_id,
        battlefield_id=recipe.battlefield_id,
        deployment_id=recipe.deployment_id,
    ), recipe.arena_id


def _game_creation_character_deployment(
    creation: GameCreationStartRequest,
) -> CharacterDeploymentSnapshot | None:
    """Resolve the one trusted persistent-character source for this process."""

    selected_character_id = creation.character_id
    is_worker = os.environ.get("DND_GAME_WORKER") == "1"
    if selected_character_id is None:
        if is_worker and _hosted_character_deployment is not None:
            raise _api_http_exception(
                status_code=409,
                code="character_deployment_selection_missing",
                message=(
                    "Hosted character deployment requires the matching "
                    "game-creation character_id"
                ),
            )
        return None
    if not isinstance(creation.scenario, GameCreationComposedScenario):
        raise _api_http_exception(
            status_code=400,
            code="character_deployment_requires_composed_scenario",
            message=(
                "Persistent characters can enter only a composed hero seat"
            ),
        )
    if is_worker:
        deployment = _hosted_character_deployment
        if deployment is None:
            raise _api_http_exception(
                status_code=403,
                code="character_deployment_not_authorized",
                message=(
                    "Hosted worker has no gateway-authenticated character "
                    "deployment"
                ),
            )
        if deployment.character_id != selected_character_id:
            raise _api_http_exception(
                status_code=403,
                code="character_deployment_identity_mismatch",
                message=(
                    "Game-creation character_id differs from the gateway "
                    "assignment"
                ),
            )
        return deployment

    service = app.state.character_directory
    handle = app.state.local_profile_handle
    if (
        not isinstance(service, CharacterDirectoryService)
        or not isinstance(handle, LocalProfileHandle)
    ):
        raise _api_http_exception(
            status_code=404,
            code="local_character_directory_unavailable",
            message="No local profile is available for character deployment",
        )
    return build_character_deployment_snapshot(
        service,
        handle.profile_id,
        selected_character_id,
    )


@dataclass(frozen=True)
class _ResolvedAIPolicy:
    """Cold policy resolution completed before engine replacement."""

    descriptor: PolicyDescriptor
    execution: AIExecutionKind
    provider_id: Optional[str] = None


async def _set_game_creation_side_controllers(
    encounter: Encounter,
    game: GameSession,
    entities: tuple[Entity, ...],
    participant: GameCreationSideRequest,
    side_id: str,
    resolved_policy: Optional[_ResolvedAIPolicy],
) -> Optional[Controller]:
    """Assign human actors or one policy/memory assignment for the whole side."""
    if participant.controller == "human":
        for entity in entities:
            encounter.set_controller_for(
                entity.uuid,
                HumanController(source_entity_uuid=entity.uuid),
            )
        return None

    if not entities or resolved_policy is None:
        raise ValueError(f"{side_id} cannot create an AI without entities and policy")
    controlled_entity_uuids = tuple(entity.uuid for entity in entities)
    assignment_id = f"{game.game_id}:{side_id}"
    instrumentation = AIInstrumentation(
        sink=sim.native_ai_instrumentation,
    )
    if resolved_policy.execution == "in_process":
        controller = NativeAIController.create(
            source_entity_uuid=controlled_entity_uuids[0],
            game_id=str(game.game_id),
            assignment_id=assignment_id,
            controlled_entity_uuids=controlled_entity_uuids,
            policy_id=resolved_policy.descriptor.policy_id,
            registry=native_policy_registry,
            instrumentation=instrumentation,
        )
        controller.start(list(entities))
        for entity in entities:
            encounter.set_controller_for(entity.uuid, controller)
        sim.native_ai_controllers.append(controller)
        return controller

    first_controller: RegisteredAIController | None = None
    for entity in entities:
        controller = await RegisteredAIController.create(
            source_entity_uuid=entity.uuid,
            game_id=str(game.game_id),
            assignment_id=(
                f"{assignment_id}:entity:{entity.uuid}"
            ),
            controlled_entity_uuids=(entity.uuid,),
            policy_id=resolved_policy.descriptor.policy_id,
            provider_catalog=_active_registered_ai_provider_catalog(),
            instrumentation=instrumentation,
        )
        try:
            controller.start([entity])
            encounter.set_controller_for(entity.uuid, controller)
        except BaseException:
            await controller.close()
            raise
        sim.registered_ai_controllers.append(controller)
        if first_controller is None:
            first_controller = controller
    return first_controller


def _resolve_game_creation_policies(
    creation: GameCreationStartRequest,
) -> dict[str, Optional[_ResolvedAIPolicy]]:
    """Validate all policy selections before replacing live engine state."""
    resolved: dict[str, Optional[_ResolvedAIPolicy]] = {}
    provider_catalog = _active_registered_ai_provider_catalog()
    for side_id, participant in (
        ("side_a", creation.side_a),
        ("side_b", creation.side_b),
    ):
        if participant.controller == "human":
            if participant.policy_id is not None:
                raise _api_http_exception(
                    status_code=400,
                    code="ai_policy_not_applicable",
                    message="Human sides cannot select an AI policy",
                    side_id=side_id,
                    policy_id=participant.policy_id,
                )
            resolved[side_id] = None
            continue
        policy_id = participant.policy_id or DEFAULT_NATIVE_POLICY_ID
        try:
            descriptor = native_policy_registry.require_descriptor(policy_id)
        except UnknownPolicyError:
            try:
                descriptor = provider_catalog.policy_descriptor(policy_id)
                provider = provider_catalog.provider_for_policy(policy_id)
            except RegisteredAIProviderNotFoundError as exc:
                valid_policy_ids = [
                    option.descriptor.policy_id
                    for option in _game_creation_ai_policy_options()
                ]
                raise _api_http_exception(
                    status_code=400,
                    code="ai_policy_not_registered",
                    message="Requested AI policy is not registered",
                    side_id=side_id,
                    policy_id=policy_id,
                    valid_policy_ids=valid_policy_ids,
                ) from exc
            resolved[side_id] = _ResolvedAIPolicy(
                descriptor=descriptor,
                execution="registered_provider",
                provider_id=provider.provider_id,
            )
            continue
        resolved[side_id] = _ResolvedAIPolicy(
            descriptor=descriptor,
            execution="in_process",
        )
    return resolved


def _game_creation_side_result(
    *,
    side_id: Literal["side_a", "side_b"],
    title: str,
    entities: tuple[Entity, ...],
    participant: GameCreationSideRequest,
    resolved_policy: Optional[_ResolvedAIPolicy],
    takeover_claim: Optional[TakeoverClaim],
) -> GameCreationSideResult:
    """Serialize one resolved side assignment."""
    return GameCreationSideResult(
        side_id=side_id,
        title=title,
        controller=participant.controller,
        participant_name=participant.name,
        entity_assignments=[
            GameCreationEntityAssignment(
                entity_uuid=str(entity.uuid),
                entity_name=entity.name,
                faction=entity.faction,
            )
            for entity in entities
        ],
        policy_id=(
            resolved_policy.descriptor.policy_id
            if resolved_policy is not None
            else None
        ),
        policy_execution=(
            resolved_policy.execution
            if resolved_policy is not None
            else None
        ),
        provider_id=(
            resolved_policy.provider_id
            if resolved_policy is not None
            else None
        ),
        codex_session_id=(
            str(takeover_claim.session_id)
            if takeover_claim is not None
            else None
        ),
        takeover_claim_id=(
            str(takeover_claim.claim_id)
            if takeover_claim is not None
            else None
        ),
        takeover_expires_at=(
            takeover_claim.expires_at
            if takeover_claim is not None
            else None
        ),
    )


def _require_ai_provider_admin(
    authorization: Optional[str] = Header(default=None),
) -> None:
    """Require the deployment bearer; player/session credentials never apply."""
    configured = _ai_provider_admin_token
    if configured is None:
        raise _api_http_exception(
            status_code=503,
            code="ai_provider_admin_disabled",
            message=(
                "External AI provider administration requires "
                "DND_AI_PROVIDER_ADMIN_TOKEN"
            ),
        )
    scheme, separator, credential = (authorization or "").partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not hmac.compare_digest(credential, configured)
    ):
        raise _api_http_exception(
            status_code=403,
            code="ai_provider_admin_forbidden",
            message="A valid deployment AI-provider bearer is required",
        )


def _provider_catalog_entry(
    info: RegisteredAIProviderInfo,
) -> AIProviderCatalogEntry:
    """Serialize one provider without exposing assignment capabilities."""
    return AIProviderCatalogEntry(
        provider_id=info.provider_id,
        base_url=info.base_url,
        protocol_version=EXTERNAL_AI_PROTOCOL_VERSION,
        protocol_hash=EXTERNAL_AI_PROTOCOL_HASH,
        policies=list(info.policies),
        capacity=info.capacity,
        active_assignments=info.active_assignments,
        available_capacity=info.available_capacity,
    )


def _game_creation_ai_policy_options() -> tuple[GameCreationAIPolicyOption, ...]:
    """Merge native and authenticated provider policies by global identity."""
    options = [
        GameCreationAIPolicyOption(
            descriptor=descriptor,
            execution="in_process",
        )
        for descriptor in native_policy_registry.descriptors()
    ]
    for provider in _active_registered_ai_provider_catalog().providers():
        options.extend(
            GameCreationAIPolicyOption(
                descriptor=descriptor,
                execution="registered_provider",
                provider_id=provider.provider_id,
                capacity=provider.capacity,
                active_assignments=provider.active_assignments,
                available_capacity=provider.available_capacity,
            )
            for descriptor in provider.policies
        )
    return tuple(
        sorted(options, key=lambda option: option.descriptor.policy_id)
    )


def _registered_ai_provider_http_exception(
    error: RegisteredAIProviderError,
) -> HTTPException:
    """Map provider ownership and transport failures to stable admin errors."""
    if isinstance(
        error,
        (RegisteredAIProviderCollisionError, RegisteredAIProviderBusyError),
    ):
        status_code = 409
        code = "ai_provider_conflict"
    elif isinstance(error, RegisteredAIProviderNotFoundError):
        status_code = 404
        code = "ai_provider_not_found"
    elif isinstance(error, RegisteredAIProviderProtocolError):
        status_code = 502
        code = "ai_provider_protocol_invalid"
    elif isinstance(
        error,
        (RegisteredAIProviderTransportError, RegisteredAIProviderCapacityError),
    ):
        status_code = 503
        code = "ai_provider_unavailable"
    else:
        status_code = 500
        code = "ai_provider_error"
    return _api_http_exception(
        status_code=status_code,
        code=code,
        message=str(error),
    )


@app.get(
    "/admin/ai/providers",
    response_model=AIProviderCatalogResponse,
    dependencies=[Depends(_require_ai_provider_admin)],
)
async def list_registered_ai_providers() -> AIProviderCatalogResponse:
    """List authenticated external policy providers for deployment tooling."""
    return AIProviderCatalogResponse(
        providers=[
            _provider_catalog_entry(info)
            for info in _active_registered_ai_provider_catalog().providers()
        ],
    )


@app.post(
    "/admin/ai/providers",
    response_model=AIProviderCatalogEntry,
    dependencies=[Depends(_require_ai_provider_admin)],
)
async def register_ai_provider(
    registration: AIProviderRegistrationRequest,
) -> AIProviderCatalogEntry:
    """Handshake with and register one external policy provider."""
    try:
        info = await _active_registered_ai_provider_catalog().register(
            provider_id=registration.provider_id,
            base_url=registration.base_url,
        )
    except RegisteredAIProviderError as error:
        raise _registered_ai_provider_http_exception(error) from error
    return _provider_catalog_entry(info)


@app.delete(
    "/admin/ai/providers/{provider_id}",
    response_model=AIProviderDeleteResponse,
    dependencies=[
        Depends(_require_ai_provider_admin),
        Depends(_serialize_world_replacement),
    ],
)
async def unregister_ai_provider(
    provider_id: str,
) -> AIProviderDeleteResponse:
    """Remove an idle provider; live game assignments reject the mutation."""
    try:
        await _active_registered_ai_provider_catalog().unregister(provider_id)
    except RegisteredAIProviderError as error:
        raise _registered_ai_provider_http_exception(error) from error
    return AIProviderDeleteResponse(provider_id=provider_id)


@app.get("/game-creation/catalog", response_model=GameCreationCatalogResponse)
async def get_game_creation_catalog() -> GameCreationCatalogResponse:
    """Return canonical scenarios, formations, and controller choices."""
    return build_game_creation_catalog(
        ai_policies=_game_creation_ai_policy_options(),
    )


@app.post("/game-creation/preflight", response_model=CompatibilityReport)
async def preflight_game_creation(
    request: GameCreationPreflightRequest,
) -> CompatibilityReport:
    """Check a composed scenario without replacing the active game."""
    return _game_creation_preflight(request)


@app.post(
    "/game-creation/start",
    response_model=GameCreationStartResponse,
    dependencies=[Depends(_serialize_world_replacement)],
)
async def start_created_game(
    creation: GameCreationStartRequest,
) -> GameCreationStartResponse:
    """Atomically assemble a scenario and configure both controller sides."""

    global _hosted_character_entity_uuid
    _hosted_character_entity_uuid = None
    selection, preset_arena_id = _game_creation_selection(creation.scenario)
    static_report = _game_creation_preflight(selection)
    if not static_report.admitted:
        raise _api_http_exception(
            status_code=400,
            code="incompatible_game_creation",
            message="The selected scenario components are incompatible",
            compatibility=static_report.model_dump(mode="json"),
        )

    character_deployment = _game_creation_character_deployment(creation)
    policies = _resolve_game_creation_policies(creation)
    await prepare_new_simulation_start()
    opening_faction = {
        "initiative": None,
        "side_a": "heroes",
        "side_b": "monsters",
    }[creation.opening_side]
    try:
        local_game = _active_local_game_coordinator()
        prepared_local_game = None
        if local_game is not None:
            scenario_id = (
                preset_arena_id
                if preset_arena_id is not None
                else ":".join(
                    (
                        selection.hero_configuration_id,
                        selection.monster_configuration_id,
                        selection.battlefield_id,
                        selection.deployment_id,
                    ),
                )
            )
            prepared_local_game = local_game.prepare(
                creation_manifest=creation.model_dump(mode="json"),
                scenario_kind=creation.scenario.kind,
                scenario_id=scenario_id,
                display_name=f"Local Game: {scenario_id}",
                character_id=creation.character_id,
            )
            character_deployment = prepared_local_game.character_snapshot
        if preset_arena_id is not None:
            arena = prepare_legacy_scenario(
                preset_arena_id,
                opening_faction=opening_faction,
            )
            compatibility = static_report
        else:
            assembled = prepare_composed_scenario(
                selection.hero_configuration_id,
                selection.monster_configuration_id,
                selection.battlefield_id,
                selection.deployment_id,
                opening_faction=opening_faction,
                hero_deployment=character_deployment,
            )
            arena = assembled.arena
            compatibility = assembled.compatibility

        sim.encounter = arena.encounter
        sim.paused = True
        sim.encounter.clear_combat_log()
        game_summary_store.reset()
        event_stream.ensure_attached()
        _ensure_local_terminal_callback()
        side_a = tuple(arena.side_a)
        side_b = tuple(arena.side_b)
        if (
            os.environ.get("DND_GAME_WORKER") == "1"
            and character_deployment is not None
        ):
            if len(side_a) != 1:
                raise RuntimeError(
                    "hosted persistent character requires exactly one hero "
                    "runtime entity",
                )
            _hosted_character_entity_uuid = side_a[0].uuid

        if prepared_local_game is not None:
            game_summary_store.bind_directory_game_id(
                sim.encounter.uuid,
                prepared_local_game.game.game_id,
            )
        game = sim.create_game_session(
            sim.encounter,
            game_id=(
                prepared_local_game.game.game_id
                if prepared_local_game is not None
                else None
            ),
        )
        if (
            prepared_local_game is not None
            and character_deployment is not None
        ):
            if len(side_a) != 1:
                raise RuntimeError(
                    "persistent local character requires exactly one hero "
                    "runtime entity",
                )
            local_game = _active_local_game_coordinator()
            if local_game is None:
                raise RuntimeError("local game lifecycle ownership disappeared")
            local_game.pin_character(side_a[0].uuid)
        await _set_game_creation_side_controllers(
            sim.encounter,
            game,
            side_a,
            creation.side_a,
            "side_a",
            policies["side_a"],
        )
        await _set_game_creation_side_controllers(
            sim.encounter,
            game,
            side_b,
            creation.side_b,
            "side_b",
            policies["side_b"],
        )

        claims: dict[str, TakeoverClaim] = {}
        manager = sim.get_session_manager()
        subjective_authority_before = _capture_subjective_session_authority(manager)
        ownership_boundary = prepare_observation_ownership_change(manager)
        for side_id, entities, participant in (
            ("side_a", side_a, creation.side_a),
            ("side_b", side_b, creation.side_b),
        ):
            if participant.controller != "codex":
                continue
            claims[side_id] = ai_takeover_manager.claim(
                encounter=sim.encounter,
                game=game,
                session_manager=sim.get_session_manager(),
                faction=None,
                entity_uuids=[entity.uuid for entity in entities],
                name=participant.name,
                lease_seconds=creation.codex_lease_seconds,
            )
        _publish_takeover_ownership_changes(
            ownership_boundary,
            "game_creation_claimed",
            subjective_authority_before=subjective_authority_before,
        )

        hero_spec = get_combatant_configuration(
            selection.hero_configuration_id
        )
        monster_spec = get_combatant_configuration(
            selection.monster_configuration_id
        )
        response = GameCreationStartResponse(
            scenario_kind=creation.scenario.kind,
            preset_arena_id=preset_arena_id,
            encounter_uuid=str(sim.encounter.uuid),
            game_id=str(game.game_id),
            encounter_name=sim.encounter.name,
            opening_side=creation.opening_side,
            compatibility=compatibility,
            side_a=_game_creation_side_result(
                side_id="side_a",
                title=hero_spec.title,
                entities=side_a,
                participant=creation.side_a,
                resolved_policy=policies["side_a"],
                takeover_claim=claims.get("side_a"),
            ),
            side_b=_game_creation_side_result(
                side_id="side_b",
                title=monster_spec.title,
                entities=side_b,
                participant=creation.side_b,
                resolved_policy=policies["side_b"],
                takeover_claim=claims.get("side_b"),
            ),
        )
        sim.current_creation = response
        return response
    except (IncompatibleScenarioError, ValueError) as exc:
        await _abort_failed_simulation_start()
        raise _api_http_exception(
            status_code=400,
            code="game_creation_assembly_failed",
            message=str(exc),
            selection=selection.model_dump(mode="json"),
        ) from exc
    except TakeoverError as exc:
        await _abort_failed_simulation_start()
        raise _takeover_http_exception(exc, faction=None) from exc
    except RegisteredAIProviderError as exc:
        await _abort_failed_simulation_start()
        raise _registered_ai_provider_http_exception(exc) from exc
    except BaseException:
        await _abort_failed_simulation_start()
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
    local_game = _active_local_game_coordinator()
    try:
        if local_game is not None:
            local_game.activate()
        encounter.start_encounter()
        if not _schedule_activated_game_coordinator():
            raise RuntimeError("Activated game coordinator could not be scheduled")
    except BaseException:
        if local_game is not None:
            local_game.fail("local_game_activation_failed")
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
            f"agent processes for PID(s): {sorted(remaining)}"
        )
    print(f"Stopped listener(s) {sorted(pids)} on port {port}")
    return True


def run_server(host: str = "0.0.0.0", port: int = 8000, force: bool = False) -> None:
    """Run the event server."""
    if force:
        kill_process_on_port(port)
        time.sleep(0.5)

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
