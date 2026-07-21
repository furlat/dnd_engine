"""Persistent task-local runtime for direct Codex game control."""

from __future__ import annotations

import logging
from secrets import token_urlsafe
from threading import Event as ThreadEvent
from threading import Lock, RLock, Thread
import time
from typing import Any, Dict, Optional, Protocol, Sequence, Tuple
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ai.codex_tools.client import CodexToolClient
from ai.knowledge.models import TargetEffectBlockHypothesis
from ai.observation.models import (
    KnowledgeState,
    ObservationEntityFact,
    ObservationObjectFact,
    SubjectiveWorldState,
)
from ai.policy import (
    ExecuteIntent,
    PolicyDecision,
    PolicyDecisionUnavailableError,
    PolicyHost,
    PolicyResultRecord,
    PolicyDecisionTelemetry,
    PolicyProposal,
)
from ai.policy.generations.current_commitments import create_generation_policy_host
from ai.policy.generations.registry import (
    CANDIDATE_GENERATION_ID,
    get_policy_implementation,
)
from ai.policy.telemetry import QueuedPolicyTelemetrySink
from ai.policy.host import PolicyDecisionDiagnostics
from ai.protocol.control import ActionAffordance, ActionEconomyState, CommandResult, DecisionEpoch
from ai.subjective.models import AgentState
from ai.subjective.queries import (
    SubjectiveQueries,
    SubjectiveQueryResult,
    SubjectiveQuerySelection,
)
from ai.subjective.runtime import SubjectiveEncounterEndedError, SubjectiveRuntime

logger = logging.getLogger(__name__)


class HotCodexRuntimeError(RuntimeError):
    """Base error for one task-local Codex runtime."""


class HotCodexStaleRevisionError(HotCodexRuntimeError):
    """Raised when a command does not match the local viewed revision."""


class HotCodexBusyError(HotCodexRuntimeError):
    """Raised when another command writer already owns the runtime."""


class HotCodexDegradedError(HotCodexRuntimeError):
    """Raised when lease or upstream state makes writes unsafe."""


class SubjectiveRuntimeLike(Protocol):
    """Runtime operations required by a hot Codex session."""

    store: Any

    def bootstrap(self) -> None:
        """Load the initial subjective snapshot."""
        ...

    def wait_for_epoch(self) -> DecisionEpoch:
        """Consume the subjective stream until a controlled epoch exists."""
        ...

    def execute(
        self,
        row_id: str,
        *,
        command_id: Optional[str] = None,
        prefer_safe: bool = True,
        extra_target_uuids: Optional[list[str]] = None,
    ) -> CommandResult:
        """Submit one current-epoch action and consume its result."""
        ...

    def emit_policy_decision(self, event: PolicyDecisionTelemetry) -> None:
        """Retain one canonical shared-policy decision."""
        ...

    def end_turn(self) -> CommandResult:
        """Submit the current actor's end-turn command."""
        ...

    def close(self) -> None:
        """Close runtime network resources."""
        ...


class HotCodexRevision(BaseModel):
    """Exact local subjective revision viewed by a Codex operator."""

    runtime_id: str = Field(description="Task-local runtime identifier.")
    session_id: str = Field(description="Authoritative controller session identifier.")
    encounter_uuid: Optional[str] = Field(default=None, description="Subjectively known encounter identifier.")
    observation_cursor: int = Field(description="Highest locally applied subjective cursor.")
    epoch_id: Optional[str] = Field(default=None, description="Current decision epoch identifier.")
    actor_uuid: Optional[str] = Field(default=None, description="Current controlled actor identifier.")


class HotCodexExecuteRequest(BaseModel):
    """Revision-fenced direct action request to the task-local runtime."""

    revision: HotCodexRevision = Field(description="Exact local view used to select the row.")
    row_id: str = Field(description="Current epoch row selected by Codex.")
    prefer_safe: bool = Field(default=True, description="Whether movement should prefer a disclosed safe path.")
    extra_target_uuids: Optional[list[str]] = Field(
        default=None,
        description="Additional current-epoch targets for a multi-target action.",
    )


class HotCodexEndTurnRequest(BaseModel):
    """Revision-fenced request to end the current controlled turn."""

    revision: HotCodexRevision = Field(description="Exact local view whose turn Codex is ending.")


class HotCodexActionIndex(BaseModel):
    """Bounded inventory of legal choices without expanding their geometry."""

    total_rows: int = Field(ge=0, description="Current authoritative affordance count.")
    affordable_rows: int = Field(ge=0, description="Currently affordable affordance count.")
    rows_by_bucket: Dict[str, int] = Field(default_factory=dict, description="Row counts by action bucket.")
    rows_by_tag: Dict[str, int] = Field(default_factory=dict, description="Row counts by typed semantic tag.")
    capability_count: int = Field(ge=0, description="Current non-executable actor capability count.")
    multi_target_rows: Tuple["HotCodexMultiTargetRowSummary", ...] = Field(
        default_factory=tuple,
        description="Bounded rows that accept extra target allocation.",
    )


class HotCodexMultiTargetRowSummary(BaseModel):
    """Compact allocation contract for one multi-target affordance row."""

    row_id: str = Field(description="Executable row id that accepts extra targets.")
    display_name: str = Field(description="Human-readable action name.")
    semantic_id: str = Field(description="Stable semantic action family.")
    primary_target_name: Optional[str] = Field(default=None, description="Primary target shown by the row.")
    primary_target_uuid: Optional[str] = Field(default=None, description="Primary target UUID shown by the row.")
    selectable_target_count: int = Field(ge=0, description="Number of legal target options disclosed by the source row.")
    allocation_count: Optional[int] = Field(
        default=None,
        description="Total selectable targets/projectiles for the action, when known.",
    )
    extra_target_slots: Optional[int] = Field(
        default=None,
        description="Additional target UUIDs the operator may supply with this row.",
    )
    allow_same_target: Optional[bool] = Field(
        default=None,
        description="Whether repeated target allocation is legal.",
    )


class HotCodexTopologyIndex(BaseModel):
    """Bounded topology summary over accumulated subjective tile knowledge."""

    known_tile_count: int = Field(ge=0, description="Number of locally known tile facts.")
    hazardous_positions: Tuple[Tuple[int, int], ...] = Field(
        default_factory=tuple,
        description="Known hazardous positions.",
    )
    slow_positions: Tuple[Tuple[int, int], ...] = Field(default_factory=tuple, description="Known slow positions.")
    blocked_positions: Tuple[Tuple[int, int], ...] = Field(default_factory=tuple, description="Known blocked positions.")


class HotCodexCombatLogSubentrySummary(BaseModel):
    """One direct causal child retained from a subjective combat-log entry."""

    entry_type: Optional[str] = Field(default=None, description="Visible child entry type when supplied.")
    target_name: Optional[str] = Field(default=None, description="Visible child target name when supplied.")
    target_uuid: Optional[str] = Field(default=None, description="Visible child target identity when supplied.")
    compact: Optional[str] = Field(default=None, description="Compact visible child rendering when supplied.")
    success: Optional[bool] = Field(default=None, description="Visible child outcome when supplied.")


class HotCodexCombatLogSummary(BaseModel):
    """Bounded visible combat-log reference retained in the default turn index."""

    entry_type: Optional[str] = Field(default=None, description="Visible combat-log entry type when supplied.")
    source_name: Optional[str] = Field(default=None, description="Visible source name when supplied.")
    source_uuid: Optional[str] = Field(default=None, description="Visible source identity when supplied.")
    target_name: Optional[str] = Field(default=None, description="Visible direct target name when supplied.")
    target_uuid: Optional[str] = Field(default=None, description="Visible direct target identity when supplied.")
    compact: Optional[str] = Field(default=None, description="Compact visible combat-log rendering when supplied.")
    success: Optional[bool] = Field(default=None, description="Visible top-level outcome when supplied.")
    sub_entries: Tuple[HotCodexCombatLogSubentrySummary, ...] = Field(
        default_factory=tuple,
        description="At most eight direct subjective causal children.",
    )
    omitted_sub_entry_count: int = Field(
        default=0,
        ge=0,
        description="Additional direct subjective children available through a local detail query.",
    )


class HotCodexTurnIndex(BaseModel):
    """Bounded default read over one complete local subjective revision."""

    revision: HotCodexRevision = Field(description="Revision represented by every field in this index.")
    encounter_state: Optional[str] = Field(default=None, description="Current subjective encounter lifecycle state.")
    is_terminal: bool = Field(default=False, description="Whether the subjective encounter has ended.")
    actor: Optional[ObservationEntityFact] = Field(default=None, description="Current controlled actor fact.")
    economy: Optional[ActionEconomyState] = Field(default=None, description="Current authoritative action economy.")
    controlled_entities: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="All locally known controlled entity facts.",
    )
    visible_hostiles: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Visible living contacts subjectively known to be hostile.",
    )
    remembered_hostiles: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Remembered living contacts subjectively known to be hostile.",
    )
    visible_allies: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Visible non-controlled contacts subjectively known to be allied.",
    )
    unknown_contacts: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Visible or remembered contacts whose relationship is unknown.",
    )
    known_dead_contacts: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Non-controlled contacts subjectively known to be dead.",
    )
    known_objects: Tuple[ObservationObjectFact, ...] = Field(
        default_factory=tuple,
        description="All locally known object facts.",
    )
    combat_memory_hypotheses: Tuple[TargetEffectBlockHypothesis, ...] = Field(
        default_factory=tuple,
        description="Bounded observed-defense hypotheses from the shared AgentFacts revision.",
    )
    topology: HotCodexTopologyIndex = Field(description="Bounded known-topology summary.")
    action_index: HotCodexActionIndex = Field(description="Counts describing locally queryable legal choices.")
    selected_policy: Optional[PolicyProposal] = Field(
        default=None,
        description="Selected shared-policy proposal without candidates or trace duplication.",
    )
    policy_candidate_count: int = Field(default=0, ge=0, description="Locally queryable policy candidate count.")
    policy_trace_step_count: int = Field(default=0, ge=0, description="Locally queryable policy trace step count.")
    policy_unavailable_reason: Optional[str] = Field(
        default=None,
        description="Why the shared policy has no proposal for this epoch.",
    )
    recent_combat_logs: Tuple[HotCodexCombatLogSummary, ...] = Field(
        default_factory=tuple,
        description="At most three compact visible combat-log entries.",
    )
    omitted_combat_log_count: int = Field(
        default=0,
        ge=0,
        description="Older local combat-log entries omitted from the bounded index.",
    )
    warnings: Tuple[str, ...] = Field(default_factory=tuple, description="Important gaps in the current default read.")
    local_timing: "HotCodexIndexTiming" = Field(description="Local index timing for this exact revision.")


class HotCodexIndexTiming(BaseModel):
    """Measured task-local stages for one bounded turn index."""

    policy_ms: float = Field(ge=0, description="Shared policy decision projection time.")
    total_ms: float = Field(ge=0, description="Total local index build time.")
    policy_cache_hit: bool = Field(default=False, description="Whether policy output was reused for this revision.")
    policy_diagnostics: Optional[PolicyDecisionDiagnostics] = Field(
        default=None,
        description="Typed observational stages and routine work for the shared decision.",
    )


class HotCodexQueryRequest(BaseModel):
    """Revision-fenced local detail selection."""

    revision: HotCodexRevision = Field(description="Exact local revision the caller inspected.")
    selection: SubjectiveQuerySelection = Field(default_factory=SubjectiveQuerySelection, description="Requested local facts.")
    include_policy_decision: bool = Field(
        default=False,
        description="Return the complete shared-policy candidates and trace for this revision.",
    )


class HotCodexQueryResult(SubjectiveQueryResult):
    """Local subjective details paired with the exact represented revision."""

    revision: HotCodexRevision = Field(description="Revision represented by all selected facts.")
    policy_decision: Optional[PolicyDecision] = Field(
        default=None,
        description="Complete shared-policy result when explicitly requested.",
    )


class HotCodexCommandView(BaseModel):
    """Authoritative command result and resulting local operator view."""

    command_result: CommandResult = Field(description="Stream-correlated authoritative command result.")
    revision: HotCodexRevision = Field(description="Local revision after consuming command follow-up frames.")
    follow_up: Optional[HotCodexTurnIndex] = Field(
        default=None,
        description="Bounded follow-up index when this session still owns an epoch.",
    )
    policy_result: Optional[PolicyResultRecord] = Field(
        default=None,
        description="Shared policy lifecycle result when Codex selected its proposal.",
    )
    local_total_ms: float = Field(ge=0, description="Task-local command handling time including follow-up projection.")
    local_timing: "HotCodexCommandTiming" = Field(
        description="Measured task-local stages surrounding the subjective runtime command.",
    )
    runtime_timing: Optional[dict[str, Any]] = Field(
        default=None,
        description="SubjectiveRuntime command timing, including server timing when available.",
    )


class HotCodexCommandTiming(BaseModel):
    """Measured task-local stages for one revision-fenced command."""

    total_ms: float = Field(ge=0, description="Total local command handling time.")
    validation_and_prepare_ms: float = Field(
        ge=0,
        description="Revision validation and optional policy submission preparation time.",
    )
    runtime_command_ms: float = Field(
        ge=0,
        description="SubjectiveRuntime execute or end-turn call time.",
    )
    policy_result_ms: float = Field(
        ge=0,
        description="Authoritative command-result correlation time in PolicyHost.",
    )
    followup_projection_ms: float = Field(
        ge=0,
        description="Local revision and optional follow-up turn projection time.",
    )


class HotCodexHealth(BaseModel):
    """Task-local daemon health and binding state."""

    status: str = Field(description="ready, degraded, released, or unbootstrapped.")
    runtime_id: str = Field(description="Task-local runtime identifier.")
    claim_id: str = Field(description="Game-server takeover claim identifier.")
    faction: str = Field(description="Faction originally claimed by this runtime.")
    controlled_entity_uuids: Tuple[str, ...] = Field(description="Entities assigned when the claim was created.")
    revision: Optional[HotCodexRevision] = Field(default=None, description="Current local subjective revision.")
    degraded_reason: Optional[str] = Field(default=None, description="Reason writes are disabled.")
    last_view_timing: Optional[HotCodexIndexTiming] = Field(
        default=None,
        description="Most recent bounded turn-index projection timing.",
    )
    last_command_timing: Optional[dict[str, Any]] = Field(
        default=None,
        description="Most recent SubjectiveRuntime command timing.",
    )


class HotCodexAttachInfo(BaseModel):
    """Safe descriptor printed when a hot runtime is attached."""

    runtime_id: str = Field(description="Task-local runtime identifier.")
    claim_id: str = Field(description="Game-server takeover claim identifier.")
    session_id: str = Field(description="Game-server controller session identifier.")
    faction: str = Field(description="Claimed faction.")
    controlled_entity_uuids: Tuple[str, ...] = Field(description="Claimed entities.")
    bearer_token: str = Field(description="Bearer token required by the loopback daemon.")


class _ContactGroups(BaseModel):
    """Subjective contact partition used by the bounded turn index."""

    controlled_entities: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Locally known controlled entities.",
    )
    visible_hostiles: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Visible living hostile contacts.",
    )
    remembered_hostiles: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Remembered living hostile contacts.",
    )
    visible_allies: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Visible non-controlled allied contacts.",
    )
    unknown_contacts: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Contacts whose faction relationship is not known.",
    )
    known_dead_contacts: Tuple[ObservationEntityFact, ...] = Field(
        default_factory=tuple,
        description="Non-controlled contacts known to be dead.",
    )


class HotCodexSession:
    """One persistent subjective runtime owned by a single Codex task."""

    def __init__(
        self,
        *,
        runtime: SubjectiveRuntimeLike,
        claim_id: str,
        faction: str,
        controlled_entity_uuids: Tuple[str, ...],
        control_client: Optional[CodexToolClient] = None,
        lease_seconds: float = 120.0,
        runtime_id: Optional[str] = None,
        policy_host: Optional[PolicyHost] = None,
    ) -> None:
        """Create an attached but not necessarily bootstrapped local runtime."""
        self.runtime = runtime
        self.claim_id = claim_id
        self.faction = faction
        self.controlled_entity_uuids = controlled_entity_uuids
        self.control_client = control_client
        self.lease_seconds = lease_seconds
        self.runtime_id = runtime_id or str(uuid4())
        self.policy_host = policy_host or create_generation_policy_host(
            get_policy_implementation(CANDIDATE_GENERATION_ID),
            controller_mode="direct_codex",
        )
        self.policy_telemetry = QueuedPolicyTelemetrySink(runtime)
        runtime_state_lock = getattr(runtime, "state_lock", None)
        self._state_lock = runtime_state_lock or RLock()
        self._command_lock = Lock()
        self._wait_lock = Lock()
        self._heartbeat_stop = ThreadEvent()
        self._heartbeat_thread: Optional[Thread] = None
        self._bootstrapped = False
        self._released = False
        self._degraded_reason: Optional[str] = None
        self._last_view_timing: Optional[HotCodexIndexTiming] = None
        self._projection_revision: Optional[HotCodexRevision] = None
        self._cached_index: Optional[HotCodexTurnIndex] = None
        self._cached_policy_decision: Optional[PolicyDecision] = None
        self._cached_policy_diagnostics: Optional[PolicyDecisionDiagnostics] = None
        self._cached_policy_unavailable_reason: Optional[str] = None
        self._policy_cache_ready = False

    @classmethod
    def attach(
        cls,
        *,
        base_url: str,
        faction: str = "monsters",
        entity_uuids: Optional[list[str]] = None,
        claim_id: Optional[str] = None,
        session_id: Optional[str] = None,
        name: str = "Codex",
        force: bool = False,
        lease_seconds: float = 120.0,
    ) -> "HotCodexSession":
        """Claim a live side and bootstrap one persistent subjective runtime."""
        _require_loopback_upstream(base_url)
        control = CodexToolClient(base_url)
        try:
            claim = control.resolve_control_claim(
                faction=faction,
                entity_uuids=entity_uuids,
                claim_id=claim_id,
                session_id=session_id,
                name=name,
                force=force,
                lease_seconds=lease_seconds,
            )
            attached_session_id = claim.session_id
            claimed = tuple(
                row.entity_uuid
                for row in claim.claimed_entities
            )
            runtime = SubjectiveRuntime(base_url=base_url, session_id=attached_session_id)
            session = cls(
                runtime=runtime,
                claim_id=claim.claim_id,
                faction=claim.faction or faction,
                controlled_entity_uuids=claimed,
                control_client=control,
                lease_seconds=claim.lease_seconds,
            )
            session.bootstrap()
            session.start_heartbeat()
            return session
        except BaseException:
            control.close()
            raise

    def bootstrap(self) -> HotCodexTurnIndex:
        """Bootstrap once and return the bounded current turn index."""
        with self._state_lock:
            if not self._bootstrapped:
                self.runtime.bootstrap()
                self._bootstrapped = True
            return self._turn_index_unlocked()

    def revision(self) -> HotCodexRevision:
        """Return the exact currently materialized subjective revision."""
        with self._state_lock:
            return self._revision_unlocked()

    def turn_index(self) -> HotCodexTurnIndex:
        """Return the bounded default read from the persistent local world."""
        with self._state_lock:
            return self._turn_index_unlocked()

    def query(self, request: HotCodexQueryRequest) -> HotCodexQueryResult:
        """Select complete typed details without contacting the game server."""
        with self._state_lock:
            self._validate_revision_unlocked(request.revision)
            world = self._world_unlocked()
            agent_state = getattr(self.runtime.store, "agent_state", AgentState())
            selected = SubjectiveQueries(world, agent_state).select(request.selection)
            policy_decision = None
            if request.include_policy_decision:
                policy_decision, _reason = self._policy_unlocked(request.revision)
            return HotCodexQueryResult(
                revision=request.revision,
                policy_decision=policy_decision,
                **selected.__dict__,
            )

    def wait_for_turn(self) -> HotCodexTurnIndex:
        """Consume the subjective stream until this session owns an epoch."""
        if not self._wait_lock.acquire(blocking=False):
            raise HotCodexBusyError("Another turn waiter already owns the runtime stream")
        try:
            with self._state_lock:
                self._require_writable_unlocked()
            try:
                self.runtime.wait_for_epoch()
            except SubjectiveEncounterEndedError:
                pass
            with self._state_lock:
                self._require_writable_unlocked()
                return self._turn_index_unlocked()
        finally:
            self._wait_lock.release()

    def execute(self, request: HotCodexExecuteRequest) -> HotCodexCommandView:
        """Submit one revision-fenced row through the shared subjective runtime."""
        command_started = time.perf_counter()
        if not self._command_lock.acquire(blocking=False):
            raise HotCodexBusyError("Another command writer already owns this runtime")
        try:
            prepare_started = time.perf_counter()
            with self._state_lock:
                self._require_writable_unlocked()
                self._validate_revision_unlocked(request.revision)
                epoch = self._current_epoch_unlocked()
                if epoch.affordances.row_by_id(request.row_id) is None:
                    raise HotCodexStaleRevisionError(
                        f"Row {request.row_id!r} is absent from epoch {epoch.epoch_id}"
                    )
                command_id = str(uuid4())
                prepared_policy = self._prepare_matching_policy_unlocked(
                    row_id=request.row_id,
                    command_id=command_id,
                )
                validation_and_prepare_ms = _elapsed_ms(prepare_started)
            runtime_started = time.perf_counter()
            try:
                result = self.runtime.execute(
                    request.row_id,
                    command_id=command_id,
                    prefer_safe=request.prefer_safe,
                    extra_target_uuids=request.extra_target_uuids,
                )
            except Exception as exc:
                with self._state_lock:
                    self._degraded_reason = f"ambiguous command submission: {exc}"
                raise
            runtime_command_ms = _elapsed_ms(runtime_started)
            with self._state_lock:
                policy_result_started = time.perf_counter()
                policy_result = (
                    self.policy_host.record_result(result)
                    if prepared_policy
                    else None
                )
                policy_result_ms = _elapsed_ms(policy_result_started)
                return self._command_view_unlocked(
                    result,
                    policy_result=policy_result,
                    command_started=command_started,
                    validation_and_prepare_ms=validation_and_prepare_ms,
                    runtime_command_ms=runtime_command_ms,
                    policy_result_ms=policy_result_ms,
                )
        finally:
            self._command_lock.release()

    def end_turn(self, request: HotCodexEndTurnRequest) -> HotCodexCommandView:
        """End one revision-fenced controlled turn through the shared runtime."""
        command_started = time.perf_counter()
        if not self._command_lock.acquire(blocking=False):
            raise HotCodexBusyError("Another command writer already owns this runtime")
        try:
            prepare_started = time.perf_counter()
            with self._state_lock:
                self._require_writable_unlocked()
                self._validate_revision_unlocked(request.revision)
                self._current_epoch_unlocked()
                validation_and_prepare_ms = _elapsed_ms(prepare_started)
            runtime_started = time.perf_counter()
            try:
                result = self.runtime.end_turn()
            except Exception as exc:
                with self._state_lock:
                    self._degraded_reason = f"ambiguous command submission: {exc}"
                raise
            runtime_command_ms = _elapsed_ms(runtime_started)
            with self._state_lock:
                return self._command_view_unlocked(
                    result,
                    command_started=command_started,
                    validation_and_prepare_ms=validation_and_prepare_ms,
                    runtime_command_ms=runtime_command_ms,
                    policy_result_ms=0.0,
                )
        finally:
            self._command_lock.release()

    def health(self) -> HotCodexHealth:
        """Return current daemon health without contacting the game server."""
        with self._state_lock:
            if self._released:
                status = "released"
            elif self._degraded_reason is not None:
                status = "degraded"
            elif self._bootstrapped:
                status = "ready"
            else:
                status = "unbootstrapped"
            revision = self._revision_unlocked() if self._bootstrapped else None
            return HotCodexHealth(
                status=status,
                runtime_id=self.runtime_id,
                claim_id=self.claim_id,
                faction=self.faction,
                controlled_entity_uuids=self.controlled_entity_uuids,
                revision=revision,
                degraded_reason=self._degraded_reason,
                last_view_timing=self._last_view_timing,
                last_command_timing=getattr(self.runtime, "last_command_timing", None),
            )

    def flush_policy_telemetry(self) -> None:
        """Wait until policy and runtime telemetry reach the server."""
        self.policy_telemetry.flush()
        flush_runtime = getattr(self.runtime, "flush_agent_events", None)
        if callable(flush_runtime):
            flush_runtime()

    def start_heartbeat(self) -> None:
        """Renew the takeover lease independently of operator think time."""
        if self.control_client is None or self._heartbeat_thread is not None:
            return
        interval = max(0.25, min(30.0, self.lease_seconds / 3.0))
        self._heartbeat_thread = Thread(
            target=self._heartbeat_loop,
            args=(interval,),
            name=f"codex-lease-{self.runtime_id}",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def release(self) -> dict[str, Any]:
        """Release the game claim and close all local resources exactly once."""
        with self._state_lock:
            if self._released:
                return {"status": "already_released", "claim_id": self.claim_id}
            self._released = True
            self._heartbeat_stop.set()
        heartbeat = self._heartbeat_thread
        if heartbeat is not None and heartbeat.is_alive():
            heartbeat.join(timeout=1.0)
        result: dict[str, Any] = {"status": "released", "claim_id": self.claim_id}
        try:
            if self.control_client is not None:
                try:
                    result = self.control_client.release(self.claim_id)
                finally:
                    self.control_client.close()
        finally:
            self.policy_telemetry.close()
            self.runtime.close()
        return result

    def _heartbeat_loop(self, interval: float) -> None:
        """Renew the claim until release or the first ambiguous failure."""
        assert self.control_client is not None
        while not self._heartbeat_stop.wait(interval):
            try:
                self.control_client.heartbeat(self.claim_id)
            except Exception as exc:
                logger.exception("hot Codex takeover heartbeat failed")
                with self._state_lock:
                    self._degraded_reason = f"takeover heartbeat failed: {exc}"
                return

    def _world_unlocked(self) -> SubjectiveWorldState:
        """Return the initialized local world while the caller owns the lock."""
        if not self._bootstrapped or self.runtime.store.world is None:
            raise HotCodexRuntimeError("HotCodexSession.bootstrap() must run before local reads")
        return self.runtime.store.world

    def _revision_unlocked(self) -> HotCodexRevision:
        """Build one revision while the caller owns the state lock."""
        world = self._world_unlocked()
        epoch = world.current_epoch
        return HotCodexRevision(
            runtime_id=self.runtime_id,
            session_id=world.session.session_id,
            encounter_uuid=world.encounter.uuid if world.encounter is not None else None,
            observation_cursor=world.observation_cursor,
            epoch_id=epoch.epoch_id if epoch is not None else None,
            actor_uuid=epoch.actor_uuid if epoch is not None else None,
        )

    def _policy_unlocked(
        self,
        revision: HotCodexRevision,
    ) -> tuple[Optional[PolicyDecision], Optional[str]]:
        """Return cached shared-policy output for one exact local revision."""
        self._ensure_projection_revision_unlocked(revision)
        if self._policy_cache_ready:
            return self._cached_policy_decision, self._cached_policy_unavailable_reason
        world = self._world_unlocked()
        if world.current_epoch is not None:
            agent_state = getattr(self.runtime.store, "agent_state", None)
            facts = getattr(agent_state, "facts", None)
            try:
                self._cached_policy_decision = self.policy_host.decide(
                    world,
                    facts=facts,
                    telemetry_sink=self.policy_telemetry,
                )
                epoch = world.current_epoch
                assert epoch is not None
                self._cached_policy_diagnostics = self.policy_host.diagnostics_for(
                    world.session.session_id,
                    epoch.actor_uuid,
                    epoch.epoch_id,
                )
            except PolicyDecisionUnavailableError as exc:
                self._cached_policy_unavailable_reason = str(exc)
        self._policy_cache_ready = True
        return self._cached_policy_decision, self._cached_policy_unavailable_reason

    def _ensure_projection_revision_unlocked(self, revision: HotCodexRevision) -> None:
        """Invalidate derived local projections when the subjective revision changes."""
        if self._projection_revision == revision:
            return
        self._projection_revision = revision
        self._cached_index = None
        self._cached_policy_decision = None
        self._cached_policy_diagnostics = None
        self._cached_policy_unavailable_reason = None
        self._policy_cache_ready = False

    def _turn_index_unlocked(self) -> HotCodexTurnIndex:
        """Build one bounded, internally consistent index under the state lock."""
        total_started = time.perf_counter()
        revision = self._revision_unlocked()
        self._ensure_projection_revision_unlocked(revision)
        if self._cached_index is not None:
            return self._cached_index
        policy_cache_hit = self._policy_cache_ready
        policy_started = time.perf_counter()
        policy_decision, policy_unavailable_reason = self._policy_unlocked(revision)
        policy_ms = _elapsed_ms(policy_started)
        timing = HotCodexIndexTiming(
            policy_ms=policy_ms,
            total_ms=_elapsed_ms(total_started),
            policy_cache_hit=policy_cache_hit,
            policy_diagnostics=self._cached_policy_diagnostics,
        )
        self._last_view_timing = timing
        world = self._world_unlocked()
        agent_state = getattr(self.runtime.store, "agent_state", None)
        facts = getattr(agent_state, "facts", None)
        epoch = world.current_epoch
        actor = world.known_entities.get(epoch.actor_uuid) if epoch is not None else None
        contacts = _classify_contacts(world, actor)
        rows = epoch.affordances.all_rows if epoch is not None else tuple()
        rows_by_bucket: Dict[str, int] = {}
        rows_by_tag: Dict[str, int] = {}
        for row in rows:
            bucket = row.bucket
            rows_by_bucket[bucket] = rows_by_bucket.get(bucket, 0) + 1
            assert epoch is not None
            for tag in epoch.affordances.semantics_for(row).tags:
                rows_by_tag[tag.value] = rows_by_tag.get(tag.value, 0) + 1
        topology = _topology_index(world)
        warnings: list[str] = []
        if epoch is None and world.encounter is not None and world.encounter.state != "ended":
            warnings.append("No controlled decision epoch is active.")
        if contacts.remembered_hostiles and not contacts.visible_hostiles:
            warnings.append("No hostile is currently visible; remembered positions are last-known facts.")
        encounter_state = world.encounter.state if world.encounter is not None else None
        self._cached_index = HotCodexTurnIndex(
            revision=revision,
            encounter_state=encounter_state,
            is_terminal=encounter_state == "ended",
            actor=actor,
            economy=epoch.economy if epoch is not None else None,
            controlled_entities=contacts.controlled_entities,
            visible_hostiles=contacts.visible_hostiles,
            remembered_hostiles=contacts.remembered_hostiles,
            visible_allies=contacts.visible_allies,
            unknown_contacts=contacts.unknown_contacts,
            known_dead_contacts=contacts.known_dead_contacts,
            known_objects=tuple(world.known_objects.values()),
            combat_memory_hypotheses=(
                facts.combat_memory.hypotheses
                if facts is not None
                else tuple()
            ),
            topology=topology,
            action_index=HotCodexActionIndex(
                total_rows=len(rows),
                affordable_rows=sum(1 for row in rows if row.can_afford),
                rows_by_bucket=rows_by_bucket,
                rows_by_tag=rows_by_tag,
                capability_count=len(epoch.affordances.capabilities) if epoch is not None else 0,
                multi_target_rows=_multi_target_row_summaries(rows),
            ),
            selected_policy=policy_decision.selected if policy_decision is not None else None,
            policy_candidate_count=len(policy_decision.candidates) if policy_decision is not None else 0,
            policy_trace_step_count=len(policy_decision.trace) if policy_decision is not None else 0,
            policy_unavailable_reason=policy_unavailable_reason,
            recent_combat_logs=tuple(_compact_combat_log(row) for row in world.combat_logs[-3:]),
            omitted_combat_log_count=max(0, len(world.combat_logs) - 3),
            warnings=tuple(warnings),
            local_timing=timing,
        )
        return self._cached_index

    def _command_view_unlocked(
        self,
        result: CommandResult,
        *,
        policy_result: Optional[PolicyResultRecord] = None,
        command_started: Optional[float] = None,
        validation_and_prepare_ms: float = 0.0,
        runtime_command_ms: float = 0.0,
        policy_result_ms: float = 0.0,
    ) -> HotCodexCommandView:
        """Build a command response after the runtime consumed follow-up frames."""
        projection_started = time.perf_counter()
        revision = self._revision_unlocked()
        follow_up = None
        if revision.epoch_id is not None:
            follow_up = self._turn_index_unlocked()
        followup_projection_ms = _elapsed_ms(projection_started)
        total_ms = _elapsed_ms(command_started) if command_started is not None else 0.0
        local_timing = HotCodexCommandTiming(
            total_ms=total_ms,
            validation_and_prepare_ms=validation_and_prepare_ms,
            runtime_command_ms=runtime_command_ms,
            policy_result_ms=policy_result_ms,
            followup_projection_ms=followup_projection_ms,
        )
        return HotCodexCommandView(
            command_result=result,
            revision=revision,
            follow_up=follow_up,
            policy_result=policy_result,
            local_total_ms=total_ms,
            local_timing=local_timing,
            runtime_timing=getattr(self.runtime, "last_command_timing", None),
        )

    def _prepare_matching_policy_unlocked(self, *, row_id: str, command_id: str) -> bool:
        """Reserve the shared proposal when Codex selected its exact current row."""
        world = self._world_unlocked()
        epoch = self._current_epoch_unlocked()
        decision, _reason = self._policy_unlocked(self._revision_unlocked())
        if decision is None:
            return False
        intent = decision.selected.intent
        if not isinstance(intent, ExecuteIntent) or intent.row_id != row_id:
            return False
        self.policy_host.prepare_submission(
            session_id=world.session.session_id,
            actor_uuid=epoch.actor_uuid,
            epoch_id=epoch.epoch_id,
            command_id=command_id,
        )
        return True

    def _validate_revision_unlocked(self, supplied: HotCodexRevision) -> None:
        """Reject writes selected from any different local revision."""
        current = self._revision_unlocked()
        if supplied != current:
            raise HotCodexStaleRevisionError(
                "Viewed revision is stale; fetch the current task-local turn before writing"
            )

    def _current_epoch_unlocked(self) -> DecisionEpoch:
        """Return the current epoch or reject an inactive write."""
        epoch = self._world_unlocked().current_epoch
        if epoch is None:
            raise HotCodexStaleRevisionError("No controlled decision epoch is active")
        return epoch

    def _require_writable_unlocked(self) -> None:
        """Reject writes when lease or lifecycle state is unsafe."""
        if self._released:
            raise HotCodexDegradedError("This task-local runtime has been released")
        if self._degraded_reason is not None:
            raise HotCodexDegradedError(self._degraded_reason)


def create_hot_codex_app(
    session: HotCodexSession,
    *,
    bearer_token: str,
) -> FastAPI:
    """Create an authenticated loopback API over one persistent runtime."""
    if not bearer_token:
        raise ValueError("A non-empty bearer token is required")
    app = FastAPI(title="NeuroDragon Hot Codex Runtime", docs_url=None, redoc_url=None)

    def authorize(authorization: Optional[str] = Header(default=None)) -> None:
        expected = f"Bearer {bearer_token}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Invalid task-local bearer token")

    @app.exception_handler(HotCodexStaleRevisionError)
    def stale_revision_handler(_request: Any, exc: HotCodexStaleRevisionError) -> Any:
        return _error_response(409, "stale_revision", str(exc))

    @app.exception_handler(HotCodexBusyError)
    def busy_handler(_request: Any, exc: HotCodexBusyError) -> Any:
        return _error_response(409, "command_writer_busy", str(exc))

    @app.exception_handler(HotCodexDegradedError)
    def degraded_handler(_request: Any, exc: HotCodexDegradedError) -> Any:
        return _error_response(503, "runtime_degraded", str(exc))

    @app.get("/v1/health", response_model=HotCodexHealth, dependencies=[Depends(authorize)])
    def health() -> HotCodexHealth:
        return session.health()

    @app.get("/v1/turn", response_model=HotCodexTurnIndex, dependencies=[Depends(authorize)])
    def turn() -> HotCodexTurnIndex:
        return session.turn_index()

    @app.post("/v1/watch", response_model=HotCodexTurnIndex, dependencies=[Depends(authorize)])
    def watch() -> HotCodexTurnIndex:
        return session.wait_for_turn()

    @app.post("/v1/query", response_model=HotCodexQueryResult, dependencies=[Depends(authorize)])
    def query(request: HotCodexQueryRequest) -> HotCodexQueryResult:
        return session.query(request)

    @app.post("/v1/execute", response_model=HotCodexCommandView, dependencies=[Depends(authorize)])
    def execute(request: HotCodexExecuteRequest) -> HotCodexCommandView:
        return session.execute(request)

    @app.post("/v1/end-turn", response_model=HotCodexCommandView, dependencies=[Depends(authorize)])
    def end_turn(request: HotCodexEndTurnRequest) -> HotCodexCommandView:
        return session.end_turn(request)

    @app.post("/v1/release", dependencies=[Depends(authorize)])
    def release() -> dict[str, Any]:
        return session.release()

    return app


def new_hot_codex_token() -> str:
    """Return a high-entropy bearer token for one local runtime."""
    return token_urlsafe(32)


def hot_attach_info(session: HotCodexSession, bearer_token: str) -> HotCodexAttachInfo:
    """Build the descriptor needed by subsequent task-local calls."""
    revision = session.revision()
    return HotCodexAttachInfo(
        runtime_id=session.runtime_id,
        claim_id=session.claim_id,
        session_id=revision.session_id,
        faction=session.faction,
        controlled_entity_uuids=session.controlled_entity_uuids,
        bearer_token=bearer_token,
    )


def _classify_contacts(
    world: SubjectiveWorldState,
    actor: Optional[ObservationEntityFact],
) -> _ContactGroups:
    """Partition only known contacts using explicit faction and knowledge facts."""
    controlled: list[ObservationEntityFact] = []
    visible_hostiles: list[ObservationEntityFact] = []
    remembered_hostiles: list[ObservationEntityFact] = []
    visible_allies: list[ObservationEntityFact] = []
    unknown_contacts: list[ObservationEntityFact] = []
    known_dead: list[ObservationEntityFact] = []
    actor_faction = actor.faction if actor is not None else None
    for entity in world.known_entities.values():
        if entity.controlled:
            controlled.append(entity)
            continue
        if entity.is_dead is True:
            known_dead.append(entity)
            continue
        relationship_known = actor_faction is not None and entity.faction is not None
        if not relationship_known:
            unknown_contacts.append(entity)
        elif entity.faction == actor_faction:
            if entity.knowledge_state is KnowledgeState.VISIBLE:
                visible_allies.append(entity)
        elif entity.knowledge_state is KnowledgeState.VISIBLE:
            visible_hostiles.append(entity)
        elif entity.knowledge_state in {KnowledgeState.SEEN, KnowledgeState.REMEMBERED}:
            remembered_hostiles.append(entity)
    return _ContactGroups(
        controlled_entities=tuple(controlled),
        visible_hostiles=tuple(visible_hostiles),
        remembered_hostiles=tuple(remembered_hostiles),
        visible_allies=tuple(visible_allies),
        unknown_contacts=tuple(unknown_contacts),
        known_dead_contacts=tuple(known_dead),
    )


def _topology_index(world: SubjectiveWorldState) -> HotCodexTopologyIndex:
    """Summarize accumulated terrain without embedding every tile fact."""
    hazardous = []
    slow = []
    blocked = []
    for tile in world.known_tiles.values():
        if tile.is_hazardous is True:
            hazardous.append(tile.position)
        if tile.walking_cost is not None and tile.walking_cost > 5:
            slow.append(tile.position)
        if tile.walkable is False:
            blocked.append(tile.position)
    return HotCodexTopologyIndex(
        known_tile_count=len(world.known_tiles),
        hazardous_positions=tuple(sorted(hazardous)),
        slow_positions=tuple(sorted(slow)),
        blocked_positions=tuple(sorted(blocked)),
    )


def _multi_target_row_summaries(
    rows: Sequence[ActionAffordance],
    *,
    limit: int = 8,
) -> Tuple[HotCodexMultiTargetRowSummary, ...]:
    """Return bounded allocation contracts for rows that accept extra targets."""
    summaries: list[HotCodexMultiTargetRowSummary] = []
    for row in rows:
        allocation_count = row.num_projectiles
        is_multi = allocation_count is not None and allocation_count > 1
        is_multi = is_multi or row.allow_same_target is not None
        is_multi = is_multi or row.target_type == "multi_entity"
        if not is_multi:
            continue
        primary = row.targets[0] if row.targets else None
        extra_slots = None
        if allocation_count is not None:
            extra_slots = max(0, allocation_count - len(row.targets))
        summaries.append(HotCodexMultiTargetRowSummary(
            row_id=row.row_id,
            display_name=row.display_name,
            semantic_id=row.semantic_id,
            primary_target_name=primary.target_name if primary is not None else None,
            primary_target_uuid=primary.target_uuid if primary is not None else None,
            selectable_target_count=len(row.target_options),
            allocation_count=allocation_count,
            extra_target_slots=extra_slots,
            allow_same_target=row.allow_same_target,
        ))
        if len(summaries) >= limit:
            break
    return tuple(summaries)


def _compact_combat_log(row: dict[str, Any]) -> HotCodexCombatLogSummary:
    """Retain bounded direct causality from an already-subjective log row."""
    direct_children = tuple(
        child
        for child in row.get("sub_entries", ())
        if isinstance(child, dict)
    )
    retained_children = direct_children[:8]
    return HotCodexCombatLogSummary(
        entry_type=_optional_text(row.get("entry_type") or row.get("type")),
        source_name=_optional_text(row.get("source_name")),
        source_uuid=_optional_text(row.get("source_uuid")),
        target_name=_optional_text(row.get("target_name")),
        target_uuid=_optional_text(row.get("target_uuid")),
        compact=_optional_text(row.get("compact")),
        success=row.get("success") if isinstance(row.get("success"), bool) else None,
        sub_entries=tuple(
            HotCodexCombatLogSubentrySummary(
                entry_type=_optional_text(child.get("entry_type") or child.get("type")),
                target_name=_optional_text(child.get("target_name")),
                target_uuid=_optional_text(child.get("target_uuid")),
                compact=_optional_text(child.get("compact")),
                success=child.get("success") if isinstance(child.get("success"), bool) else None,
            )
            for child in retained_children
        ),
        omitted_sub_entry_count=len(direct_children) - len(retained_children),
    )


def _optional_text(value: Any) -> Optional[str]:
    """Return one optional transport value as text without inventing content."""
    return str(value) if value is not None else None


def _require_loopback_upstream(base_url: str) -> None:
    """Reject remote upstreams unless a future explicit trust policy allows them."""
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Hot Codex upstream must be an explicit loopback HTTP URL")


def _error_response(status_code: int, code: str, message: str) -> Any:
    """Build one compact JSON error without coupling to the game server."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def _elapsed_ms(started: float) -> float:
    """Return a compact local elapsed duration in milliseconds."""
    return round((time.perf_counter() - started) * 1000, 3)
