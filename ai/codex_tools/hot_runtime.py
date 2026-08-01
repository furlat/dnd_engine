"""Persistent task-local runtime for direct Codex game control."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from secrets import token_urlsafe
from threading import Event as ThreadEvent
from threading import Lock, RLock, Thread
import time
from typing import Any, Dict, Literal, Optional, Protocol, Tuple
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ai.codex_tools.client import CodexToolClient
from ai.codex_tools.contracts import TakeoverClaimInfo
from ai.codex_tools.representation.components import (
    ActionCapabilitySummary,
    ActionFamilyBlock,
    ActionFamilySummary,
    ActionSemanticCoverage,
    AdvicePayload,
    AdviceBlock,
    CombatHypothesisBlock,
    ContactLedgerBlock,
    CodexTurnRepresentation,
    EncounterSummaryBlock,
    EncounterSummaryPayload,
    KnownObjectSummary,
    ObjectLedgerBlock,
    OracleAdviceBasis,
    RecentCombatLogsBlock,
    RuntimeTelemetryInput,
    TopologySummaryBlock,
    TurnCoreBlock,
    WarningBlock,
)
from ai.codex_tools.representation.inspection import (
    InspectionArchive,
    InspectionCatalog,
    InspectionDiffRequest,
    InspectionDiffResult,
    InspectionDocument,
    InspectionExport,
    InspectionGetRequest,
    InspectionGetResult,
    InspectionSchemaBundle,
    InspectionSearchRequest,
    InspectionSearchResult,
    capture_inspection_document,
)
from ai.codex_tools.representation.geometry import (
    GeometryQuery,
    GeometryResult,
    SubjectiveGeometry,
)
from ai.codex_tools.representation.models import (
    ExposureTiming,
    RepresentationComponentSpec,
    RepresentationProfile,
    ResolvedRepresentationManifest,
)
from ai.codex_tools.representation.oracle import advice_from_policy_decision
from ai.codex_tools.representation.predicates import (
    DerivedFactDefinition,
    PredicateDefinition,
    PredicateFocusProfile,
    PredicateLedger,
    PredicateLedgerSnapshot,
)
from ai.codex_tools.representation.profiles import (
    BALANCED_V2_PROFILE_ID,
    CURRENT_V1_PROFILE_ID,
    build_builtin_representation_registry,
)
from ai.codex_tools.representation.projector import (
    ComponentProjectionEvent,
    CodexRepresentationProjector,
    RequiredRepresentationComponentError,
    RepresentationProjectionInput,
)
from ai.codex_tools.session_transcript import (
    CodexSessionTranscript,
    SessionReleasePayload,
    SessionTranscript,
    SessionTranscriptStatus,
)
from ai.knowledge import derive_agent_facts
from ai.knowledge.models import AgentFacts, TargetEffectBlockHypothesis
from dnd.ai.contracts.observation import (
    ObservationEntityFact,
    ObservationObjectFact,
    SubjectiveWorldState,
)
from ai.policy import (
    PolicyDecision,
    PolicyDecisionUnavailableError,
    PolicyHost,
    PolicyResultRecord,
    PolicyDecisionTelemetry,
    PolicyProposal,
)
from dnd.ai.contracts.decision import ExecuteIntent
from ai.policy.generations.current_commitments import create_generation_policy_host
from ai.policy.generations.registry import get_active_policy_implementation
from ai.policy.telemetry import QueuedPolicyTelemetrySink
from ai.policy.host import PolicyDecisionDiagnostics
from dnd.ai.contracts.control import ActionCostProfile, ActionEconomyState, CommandResult, DecisionEpoch
from ai.subjective.models import AgentState
from server.agent_protocol.telemetry import AgentEvent
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


class HotCodexProfileViolationError(HotCodexRuntimeError):
    """Raised when an operation bypasses the active representation profile."""


class HotCodexRepresentationError(HotCodexRuntimeError):
    """Raised when a required representation component fails safely."""


class HotCodexUnknownProfileError(HotCodexRuntimeError):
    """Raised when a profile selection references no registered definition."""


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


class HotCodexEntitySummary(BaseModel):
    """Compact subjective entity fact for automatic Codex context."""

    uuid: str = Field(description="Known entity identity.")
    name: str = Field(description="Known entity display name.")
    knowledge_state: str = Field(description="Visible or remembered knowledge state.")
    controlled: bool = Field(description="Whether this session controls the entity.")
    position: Optional[Tuple[int, int]] = Field(default=None, description="Known or last-known position.")
    hp: Optional[int] = Field(default=None, description="Known current hit points.")
    max_hp: Optional[int] = Field(default=None, description="Known maximum hit points.")
    ac: Optional[int] = Field(default=None, description="Known Armor Class.")
    conditions: Tuple[str, ...] = Field(default_factory=tuple, description="Known condition names.")
    condition_semantic_keys: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Known stable condition identities.",
    )
    faction: Optional[str] = Field(default=None, description="Known faction.")
    is_dead: Optional[bool] = Field(default=None, description="Known death state.")


class HotCodexObjectSummary(BaseModel):
    """Compact subjective object fact for automatic Codex context."""

    uuid: str = Field(description="Known object identity.")
    name: str = Field(description="Known object display name.")
    knowledge_state: str = Field(description="Visible or remembered knowledge state.")
    position: Optional[Tuple[int, int]] = Field(default=None, description="Known or last-known position.")
    is_open: Optional[bool] = Field(default=None, description="Known open state when supplied.")
    state_keys: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Locally inspectable state fields omitted from automatic context.",
    )


class HotCodexActionFamilyDigest(BaseModel):
    """Actionable family metadata without semantic-catalog duplication."""

    source_action_id: str = Field(description="Epoch-local action-source identity.")
    semantic_key: str = Field(description="Stable action-definition identity.")
    display_name: str = Field(description="Human-readable action name.")
    semantic_id: str = Field(description="Stable semantic action family.")
    bucket: str = Field(description="Server-issued affordance bucket.")
    action_category: str = Field(description="Engine action category.")
    target_type: str = Field(description="Configured target allocation type.")
    row_count: int = Field(ge=1, description="Executable rows generated by this source.")
    direct_row_id: Optional[str] = Field(default=None, description="Executable row id for singleton families.")
    affordable_row_count: int = Field(ge=0, description="Currently affordable rows in this family.")
    cost: ActionCostProfile = Field(description="Shared action-economy and resource cost.")
    target_option_count: int = Field(ge=0, description="Legal source-level target count.")
    allocation_count: Optional[int] = Field(default=None, ge=0, description="Target allocations when declared.")
    allow_same_target: Optional[bool] = Field(default=None, description="Whether allocations may repeat a target.")
    spell_level: Optional[int] = Field(default=None, ge=0, description="Base spell level when applicable.")
    cast_at_level: Optional[int] = Field(default=None, ge=0, description="Selected slot level when applicable.")
    requires_concentration: bool = Field(description="Whether execution starts or replaces concentration.")
    tags: Tuple[str, ...] = Field(default_factory=tuple, description="Stable semantic tags.")


class HotCodexTurnBrief(BaseModel):
    """Compact neutral decision context produced by the persistent runtime."""

    revision: HotCodexRevision = Field(description="Exact represented local subjective revision.")
    encounter_state: Optional[str] = Field(default=None, description="Subjective encounter lifecycle state.")
    is_terminal: bool = Field(description="Whether the encounter has ended.")
    actor: Optional[HotCodexEntitySummary] = Field(default=None, description="Current controlled actor.")
    economy: Optional[ActionEconomyState] = Field(default=None, description="Current authoritative economy.")
    controlled_entities: Tuple[HotCodexEntitySummary, ...] = Field(
        default_factory=tuple,
        description="Compact controlled roster.",
    )
    visible_hostiles: Tuple[HotCodexEntitySummary, ...] = Field(
        default_factory=tuple,
        description="Currently visible known hostiles.",
    )
    remembered_hostiles: Tuple[HotCodexEntitySummary, ...] = Field(
        default_factory=tuple,
        description="Remembered hostiles with last-known facts.",
    )
    known_objects: Tuple[HotCodexObjectSummary, ...] = Field(
        default_factory=tuple,
        description="Known scene objects without engine-private data.",
    )
    action_families: Tuple[HotCodexActionFamilyDigest, ...] = Field(
        default_factory=tuple,
        description="Bounded legal source-action families with singleton row handles.",
    )
    omitted_action_family_count: int = Field(
        default=0,
        ge=0,
        description="Additional action families available through local typed queries.",
    )
    capabilities: Tuple[ActionCapabilitySummary, ...] = Field(
        default_factory=tuple,
        description="Bounded non-executable actor capabilities.",
    )
    omitted_capability_count: int = Field(
        default=0,
        ge=0,
        description="Additional capabilities available through local typed queries.",
    )
    semantic_coverage: ActionSemanticCoverage = Field(
        default_factory=lambda: ActionSemanticCoverage(
            source_action_count=0,
            exact_count=0,
            structured_profile_count=0,
            category_fallback_count=0,
            unknown_count=0,
        ),
        description="Coverage and unresolved keys across current source actions.",
    )
    multi_target_rows: Tuple[HotCodexMultiTargetRowSummary, ...] = Field(
        default_factory=tuple,
        description="Rows requiring explicit multi-target allocation.",
    )
    topology: HotCodexTopologyIndex = Field(description="Known hazards, blockers, and slow terrain.")
    recent_combat_logs: Tuple[HotCodexCombatLogSummary, ...] = Field(
        default_factory=tuple,
        description="Newest visible causal outcomes.",
    )
    encounter_summary: Optional[EncounterSummaryPayload] = Field(
        default=None,
        description="Subjective match outcome and aggregate statistics.",
    )
    warnings: Tuple[str, ...] = Field(default_factory=tuple, description="Current representation warnings.")
    transcript: Optional[SessionTranscriptStatus] = Field(
        default=None,
        description="Durable evidence cursor and paths.",
    )


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


class HotCodexFollowUpDigest(BaseModel):
    """Immediately actionable post-command context without repeated detail indexes."""

    revision: HotCodexRevision = Field(description="Exact represented subjective revision.")
    encounter_state: Optional[str] = Field(default=None, description="Subjective encounter lifecycle state.")
    is_terminal: bool = Field(description="Whether the encounter has ended.")
    actor: Optional[HotCodexEntitySummary] = Field(default=None, description="Current controlled actor.")
    economy: Optional[ActionEconomyState] = Field(default=None, description="Current authoritative economy.")
    visible_hostiles: Tuple[HotCodexEntitySummary, ...] = Field(default_factory=tuple)
    remembered_hostiles: Tuple[HotCodexEntitySummary, ...] = Field(default_factory=tuple)
    known_objects: Tuple[HotCodexObjectSummary, ...] = Field(default_factory=tuple)
    action_families: Tuple[HotCodexActionFamilyDigest, ...] = Field(default_factory=tuple)
    omitted_action_family_count: int = Field(default=0, ge=0)
    semantic_coverage: ActionSemanticCoverage = Field(description="Current semantic coverage.")
    multi_target_rows: Tuple[HotCodexMultiTargetRowSummary, ...] = Field(default_factory=tuple)
    recent_combat_logs: Tuple[HotCodexCombatLogSummary, ...] = Field(default_factory=tuple)
    encounter_summary: Optional[EncounterSummaryPayload] = Field(default=None)
    warnings: Tuple[str, ...] = Field(default_factory=tuple)


class HotCodexCommandReceipt(BaseModel):
    """Compact command outcome plus immediately usable follow-up context."""

    status: str = Field(description="Controller-protocol status.")
    command_id: Optional[str] = Field(default=None, description="Command correlation identity.")
    actor_uuid: Optional[str] = Field(default=None, description="Actor that attempted the command.")
    row_id: Optional[str] = Field(default=None, description="Executed legal row identity.")
    action_resolution: Optional[str] = Field(default=None, description="Completed, canceled, or interrupted result.")
    outcome_code: Optional[str] = Field(default=None, description="Stable engine outcome code.")
    message: str = Field(description="Short human-readable outcome.")
    revalidation_required: bool = Field(description="Whether new information invalidated the prior plan.")
    revalidation_reason: Optional[str] = Field(default=None, description="Reason a fresh decision is required.")
    resync_required: bool = Field(description="Whether the local runtime had to resynchronize.")
    resulting_revision: HotCodexRevision = Field(description="Revision after command follow-up frames.")
    follow_up: Optional[HotCodexFollowUpDigest] = Field(
        default=None,
        description="Next compact decision context when this session still controls an actor.",
    )
    local_total_ms: float = Field(ge=0, description="Complete daemon-side command handling latency.")
    transcript: Optional[SessionTranscriptStatus] = Field(
        default=None,
        description="Durable evidence state after recording this command.",
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
    representation_profile_id: str = Field(description="Active automatic representation profile.")
    representation_manifest_digest: str = Field(description="Resolved active profile digest.")
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
    transcript: Optional[SessionTranscriptStatus] = Field(
        default=None,
        description="Durable session-subjective transcript state.",
    )


class HotCodexReleaseView(BaseModel):
    """Typed result after closing one task-local runtime and takeover claim."""

    status: str = Field(description="Release lifecycle result.")
    claim_id: str = Field(description="Takeover claim released by the runtime.")
    upstream_status: Optional[str] = Field(
        default=None,
        description="Game-server release status when an upstream claim existed.",
    )


class HotCodexAttachInfo(BaseModel):
    """Safe descriptor printed when a hot runtime is attached."""

    runtime_id: str = Field(description="Task-local runtime identifier.")
    claim_id: str = Field(description="Game-server takeover claim identifier.")
    session_id: str = Field(description="Game-server controller session identifier.")
    faction: str = Field(description="Claimed faction.")
    controlled_entity_uuids: Tuple[str, ...] = Field(description="Claimed entities.")
    representation_profile_id: str = Field(description="Initial automatic representation profile.")
    representation_manifest_digest: str = Field(description="Resolved initial profile digest.")
    bearer_token: str = Field(description="Bearer token required by the loopback daemon.")
    transcript: Optional[SessionTranscriptStatus] = Field(
        default=None,
        description="Durable transcript paths and initial record state.",
    )


class HotCodexProfileView(BaseModel):
    """Active representation profile and its fully resolved manifest."""

    revision: HotCodexRevision = Field(description="Current local subjective revision.")
    profile: RepresentationProfile = Field(description="Active immutable profile definition.")
    manifest: ResolvedRepresentationManifest = Field(description="Resolved active component manifest.")


class HotCodexProfileSelectRequest(BaseModel):
    """Revision-fenced request to select one registered representation profile."""

    revision: HotCodexRevision = Field(description="Local revision at which the profile is changed.")
    profile_id: str = Field(description="Registered representation profile identity.")


class HotCodexComponentCatalog(BaseModel):
    """Discoverable representation components and profiles."""

    revision: HotCodexRevision = Field(description="Current local subjective revision.")
    active_profile_id: str = Field(description="Profile currently used for automatic projection.")
    components: Tuple[RepresentationComponentSpec, ...] = Field(
        description="Registered component semantic definitions.",
    )
    profiles: Tuple[RepresentationProfile, ...] = Field(
        description="Registered ordered profile definitions.",
    )


class HotCodexRepresentationView(BaseModel):
    """Profile-driven representation paired with its hot-runtime revision fence."""

    revision: HotCodexRevision = Field(description="Exact local revision represented.")
    representation: CodexTurnRepresentation = Field(description="Typed ordered representation envelope.")


class HotCodexOracleRequest(BaseModel):
    """Explicit revision-fenced request for optional traditional-policy advice."""

    revision: HotCodexRevision = Field(description="Exact local revision to evaluate.")
    detail: Literal["selected_only", "ranked", "full_trace"] = Field(
        default="selected_only",
        description="Amount of oracle result returned.",
    )


class HotCodexOracleView(BaseModel):
    """Optional tactical advice that remains separate from automatic context."""

    revision: HotCodexRevision = Field(description="Exact local revision evaluated.")
    advice: AdvicePayload = Field(description="Policy-independent typed oracle advice.")


class HotCodexGeometryRequest(BaseModel):
    """Revision-fenced local subjective geometry request."""

    revision: HotCodexRevision = Field(description="Exact local revision to evaluate.")
    query: GeometryQuery = Field(description="Typed read-only geometry operation.")


class HotCodexGeometryView(BaseModel):
    """Subjective geometry result paired with its exact revision fence."""

    revision: HotCodexRevision = Field(description="Exact local revision evaluated.")
    result: GeometryResult = Field(description="Typed geometry result and provenance.")


class HotCodexPredicateCatalog(BaseModel):
    """Complete declarative fact and predicate definitions for one runtime."""

    revision: HotCodexRevision = Field(description="Current local subjective revision.")
    facts: Tuple[DerivedFactDefinition, ...] = Field(description="Registered derived-fact definitions.")
    predicates: Tuple[PredicateDefinition, ...] = Field(description="Registered predicate definitions.")


class HotCodexPredicateRegisterRequest(BaseModel):
    """Revision-fenced registration of one non-executable declarative predicate."""

    revision: HotCodexRevision = Field(description="Local revision at registration time.")
    definition: PredicateDefinition = Field(description="Validated JSON-native predicate definition.")


class HotCodexPredicateEvaluateRequest(BaseModel):
    """Revision-fenced request to evaluate the complete local predicate ledger."""

    revision: HotCodexRevision = Field(description="Exact local revision to evaluate.")


class HotCodexPredicateFocusRequest(BaseModel):
    """Revision-fenced replacement of automatic predicate attention rules."""

    revision: HotCodexRevision = Field(description="Local revision at focus-change time.")
    focus: PredicateFocusProfile = Field(description="Complete replacement focus profile.")


class HotCodexInspectionGetRequest(BaseModel):
    """Revision-fenced exact reads over the immutable subjective document."""

    revision: HotCodexRevision = Field(description="Exact local revision to inspect.")
    query: InspectionGetRequest = Field(description="Bounded RFC 6901 pointer batch.")


class HotCodexInspectionSearchRequest(BaseModel):
    """Revision-fenced literal search over the immutable subjective document."""

    revision: HotCodexRevision = Field(description="Exact local revision to inspect.")
    query: InspectionSearchRequest = Field(description="Bounded literal search request.")


class HotCodexInspectionDiffRequest(BaseModel):
    """Revision-fenced structural comparison of retained subjective documents."""

    revision: HotCodexRevision = Field(description="Current local revision authorizing archive access.")
    query: InspectionDiffRequest = Field(description="Retained document digests and bounded diff page.")


class HotCodexInspectionCatalogView(BaseModel):
    """Discoverable immutable inspection roots for the current local revision."""

    revision: HotCodexRevision = Field(description="Exact local revision cataloged.")
    catalog: InspectionCatalog = Field(description="Canonical root, schema, and operation catalog.")


class HotCodexInspectionGetView(BaseModel):
    """Exact immutable inspection results paired with the hot revision fence."""

    revision: HotCodexRevision = Field(description="Exact local revision inspected.")
    result: InspectionGetResult = Field(description="Exact JSON Pointer lookup results.")


class HotCodexInspectionSearchView(BaseModel):
    """Bounded immutable search results paired with the hot revision fence."""

    revision: HotCodexRevision = Field(description="Exact local revision inspected.")
    result: InspectionSearchResult = Field(description="Deterministic literal search results.")


class HotCodexInspectionDiffView(BaseModel):
    """Structural archive diff paired with the current authorization revision."""

    revision: HotCodexRevision = Field(description="Current local revision at diff time.")
    result: InspectionDiffResult = Field(description="Structural retained-document comparison.")


class HotCodexInspectionSchemaView(BaseModel):
    """Inspection schemas paired with the exact captured subjective revision."""

    revision: HotCodexRevision = Field(description="Exact local revision whose schemas are returned.")
    schema_bundle: InspectionSchemaBundle = Field(description="Versioned schemas and open-JSON declarations.")


class HotCodexInspectionExportView(BaseModel):
    """Complete canonical subjective artifact paired with the hot revision fence."""

    revision: HotCodexRevision = Field(description="Exact local revision exported.")
    export: InspectionExport = Field(description="Canonical JSON text, digest, and byte count.")


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
        representation_profile_id: str = CURRENT_V1_PROFILE_ID,
        transcript: Optional[CodexSessionTranscript] = None,
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
            get_active_policy_implementation(),
            controller_mode="direct_codex",
        )
        self.policy_telemetry = QueuedPolicyTelemetrySink(runtime)
        self.representation_registry = build_builtin_representation_registry()
        self.representation_profile_id = representation_profile_id
        self.representation_manifest = self.representation_registry.resolve_profile(
            representation_profile_id
        )
        self.representation_projector = CodexRepresentationProjector()
        self.predicate_ledger = PredicateLedger()
        self.predicate_focus = _default_predicate_focus()
        self.inspection_archive = InspectionArchive()
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
        self._cached_policy_evaluation_ms = 0.0
        self._policy_cache_ready = False
        self._cached_predicate_snapshot: Optional[PredicateLedgerSnapshot] = None
        self._cached_representation: Optional[CodexTurnRepresentation] = None
        self._cached_inspection_document: Optional[InspectionDocument] = None
        self._previous_representation_world: Optional[SubjectiveWorldState] = None
        self._previous_representation_agent_state: Optional[AgentState] = None
        self._inspection_count = 0
        self._command_count = 0
        self.transcript = transcript

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
        representation_profile_id: str = BALANCED_V2_PROFILE_ID,
        transcript_directory: Path = Path("game_logs/codex_sessions"),
        include_command_diagnostics: bool = False,
    ) -> "HotCodexSession":
        """Claim a live side and bootstrap one persistent subjective runtime."""
        _require_loopback_upstream(base_url)
        representation_registry = build_builtin_representation_registry()
        representation_registry.profile(representation_profile_id)
        representation_manifest = representation_registry.resolve_profile(
            representation_profile_id
        )
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
            resolved_faction = _resolved_claim_faction(claim, faction)
            runtime_id = str(uuid4())
            transcript = CodexSessionTranscript(
                runtime_id=runtime_id,
                session_id=attached_session_id,
                claim_id=claim.claim_id,
                faction=resolved_faction,
                controlled_entity_uuids=claimed,
                representation_manifest=representation_manifest,
                directory=transcript_directory,
            )
            runtime = SubjectiveRuntime(
                base_url=base_url,
                session_id=attached_session_id,
                evidence_recorder=transcript,
                include_command_diagnostics=include_command_diagnostics,
            )
            session = cls(
                runtime=runtime,
                claim_id=claim.claim_id,
                faction=resolved_faction,
                controlled_entity_uuids=claimed,
                control_client=control,
                lease_seconds=claim.lease_seconds,
                runtime_id=runtime_id,
                representation_profile_id=representation_profile_id,
                transcript=transcript,
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
                self._emit_agent_event_unlocked(
                    "representation.profile_resolved",
                    "Codex representation profile resolved for this runtime.",
                    payload={
                        "profile_id": self.representation_profile_id,
                        "manifest_digest": self.representation_manifest.manifest_digest,
                    },
                    tags=["representation", "profile"],
                )
            return self._turn_index_unlocked()

    def revision(self) -> HotCodexRevision:
        """Return the exact currently materialized subjective revision."""
        with self._state_lock:
            return self._revision_unlocked()

    def turn_index(self) -> HotCodexTurnIndex:
        """Return the bounded default read from the persistent local world."""
        with self._state_lock:
            return self._turn_index_unlocked()

    def brief(self) -> HotCodexTurnBrief:
        """Return compact neutral context from the materialized subjective world."""
        with self._state_lock:
            return self._brief_unlocked()

    def query(self, request: HotCodexQueryRequest) -> HotCodexQueryResult:
        """Select complete typed details without contacting the game server."""
        with self._state_lock:
            self._validate_revision_unlocked(request.revision)
            world = self._world_unlocked()
            agent_state = getattr(self.runtime.store, "agent_state", AgentState())
            selected = SubjectiveQueries(world, agent_state).select(request.selection)
            policy_decision = None
            if request.include_policy_decision:
                if not self.representation_manifest.compatibility.preserves_eager_policy_lifecycle:
                    raise HotCodexProfileViolationError(
                        "Raw policy decisions are disabled by this profile; use /v1/representation/oracle."
                    )
                policy_decision, _reason = self._policy_unlocked(request.revision)
            return HotCodexQueryResult(
                revision=request.revision,
                policy_decision=policy_decision,
                **selected.__dict__,
            )

    def profile_view(self) -> HotCodexProfileView:
        """Return the active profile and resolved behavior manifest."""
        with self._state_lock:
            return HotCodexProfileView(
                revision=self._revision_unlocked(),
                profile=self.representation_registry.profile(self.representation_profile_id),
                manifest=self.representation_manifest,
            )

    def select_profile(self, request: HotCodexProfileSelectRequest) -> HotCodexProfileView:
        """Select a registered profile without reloading subjective state."""
        if not self._command_lock.acquire(blocking=False):
            raise HotCodexBusyError("Cannot change representation profile while a command is in flight")
        try:
            with self._state_lock:
                self._validate_revision_unlocked(request.revision)
                if request.profile_id == self.representation_profile_id:
                    return HotCodexProfileView(
                        revision=self._revision_unlocked(),
                        profile=self.representation_registry.profile(self.representation_profile_id),
                        manifest=self.representation_manifest,
                    )
                previous_digest = self.representation_manifest.manifest_digest
                try:
                    profile = self.representation_registry.profile(request.profile_id)
                    manifest = self.representation_registry.resolve_profile(request.profile_id)
                except ValueError as exc:
                    raise HotCodexUnknownProfileError(str(exc)) from exc
                self.representation_profile_id = profile.profile_id
                self.representation_manifest = manifest
                self._invalidate_representation_unlocked(reset_predicates=False)
                self._emit_agent_event_unlocked(
                    "representation.profile_changed",
                    "Codex representation profile changed.",
                    payload={
                        "old_manifest_digest": previous_digest,
                        "new_manifest_digest": manifest.manifest_digest,
                        "profile_id": profile.profile_id,
                    },
                    tags=["representation", "profile"],
                )
                return HotCodexProfileView(
                    revision=self._revision_unlocked(),
                    profile=profile,
                    manifest=manifest,
                )
        finally:
            self._command_lock.release()

    def component_catalog(self) -> HotCodexComponentCatalog:
        """Return all registered representation definitions and profiles."""
        with self._state_lock:
            return HotCodexComponentCatalog(
                revision=self._revision_unlocked(),
                active_profile_id=self.representation_profile_id,
                components=self.representation_registry.components(),
                profiles=self.representation_registry.profiles(),
            )

    def representation(self) -> HotCodexRepresentationView:
        """Return automatic profile output without contacting the game server."""
        with self._state_lock:
            revision = self._revision_unlocked()
            return HotCodexRepresentationView(
                revision=revision,
                representation=self._representation_unlocked(),
            )

    def oracle(self, request: HotCodexOracleRequest) -> HotCodexOracleView:
        """Evaluate optional tactical advice only after an explicit request."""
        with self._state_lock:
            self._validate_revision_unlocked(request.revision)
            decision, reason = self._policy_unlocked(request.revision)
            advice = (
                self._advice_unlocked(decision, request.revision, detail=request.detail)
                if decision is not None
                else AdvicePayload(
                    available=False,
                    detail=request.detail,
                    unavailable_reason=reason,
                )
            )
            self._emit_agent_event_unlocked(
                "representation.oracle_requested",
                "Optional policy oracle evaluated.",
                payload={
                    "detail": request.detail,
                    "available": advice.available,
                    "unavailable_reason": reason,
                },
                tags=["representation", "oracle"],
            )
            return HotCodexOracleView(revision=request.revision, advice=advice)

    def geometry(self, request: HotCodexGeometryRequest) -> HotCodexGeometryView:
        """Evaluate geometry from the current local subjective materialization."""
        with self._state_lock:
            self._validate_revision_unlocked(request.revision)
            result = SubjectiveGeometry(self._world_unlocked()).evaluate(request.query)
            self._emit_agent_event_unlocked(
                "representation.geometry_evaluated",
                "Local subjective geometry query evaluated.",
                payload={
                    "operation": request.query.operation.value,
                    "result_kind": result.result_kind.value,
                    "truth": result.truth.value,
                    "position_count": len(result.positions),
                    "unknown_position_count": len(result.unknown_positions),
                    "authoritative_row_id": result.authoritative_row_id,
                },
                tags=["representation", "geometry"],
            )
            return HotCodexGeometryView(revision=request.revision, result=result)

    def predicate_catalog(self) -> HotCodexPredicateCatalog:
        """Return complete declarative fact and predicate definitions."""
        with self._state_lock:
            return HotCodexPredicateCatalog(
                revision=self._revision_unlocked(),
                facts=self.predicate_ledger.fact_definitions,
                predicates=self.predicate_ledger.predicate_definitions,
            )

    def register_predicate(
        self,
        request: HotCodexPredicateRegisterRequest,
    ) -> PredicateDefinition:
        """Register one bounded JSON-native predicate without executable code."""
        with self._state_lock:
            self._validate_revision_unlocked(request.revision)
            registered = self.predicate_ledger.register_predicate(request.definition)
            self._invalidate_representation_unlocked(reset_predicates=True)
            self._emit_agent_event_unlocked(
                "representation.predicate_registered",
                "Declarative predicate registered.",
                payload={"predicate_id": registered.predicate_id},
                tags=["representation", "predicate"],
            )
            return registered

    def evaluate_predicates(
        self,
        request: HotCodexPredicateEvaluateRequest,
    ) -> PredicateLedgerSnapshot:
        """Evaluate the complete predicate ledger against one exact revision."""
        with self._state_lock:
            self._validate_revision_unlocked(request.revision)
            return self._predicate_snapshot_unlocked()

    def predicate_focus_view(self) -> PredicateFocusProfile:
        """Return the active automatic predicate focus profile."""
        with self._state_lock:
            return self.predicate_focus

    def set_predicate_focus(
        self,
        request: HotCodexPredicateFocusRequest,
    ) -> PredicateFocusProfile:
        """Replace automatic predicate attention without changing the ledger."""
        with self._state_lock:
            self._validate_revision_unlocked(request.revision)
            snapshot = self.predicate_ledger.evaluate(
                self._world_unlocked(),
                self._agent_facts_unlocked(),
                focus_profile=request.focus,
            )
            self.predicate_focus = request.focus
            self._cached_predicate_snapshot = snapshot
            self._cached_representation = None
            self._cached_inspection_document = None
            self._emit_agent_event_unlocked(
                "representation.predicate_focus_changed",
                "Predicate attention focus changed.",
                payload={"focus_profile_id": request.focus.profile_id},
                tags=["representation", "predicate", "focus"],
            )
            return self.predicate_focus

    def inspection_catalog(self) -> HotCodexInspectionCatalogView:
        """Return canonical inspection roots for the current captured revision."""
        with self._state_lock:
            revision = self._revision_unlocked()
            document = self._inspection_document_unlocked()
            self._record_inspection_unlocked("catalog", 0)
            return HotCodexInspectionCatalogView(revision=revision, catalog=document.catalog())

    def inspection_get(
        self,
        request: HotCodexInspectionGetRequest,
    ) -> HotCodexInspectionGetView:
        """Resolve exact canonical local paths for one revision."""
        with self._state_lock:
            self._validate_revision_unlocked(request.revision)
            result = self._inspection_document_unlocked().get(request.query)
            self._record_inspection_unlocked("get", result.returned_bytes)
            return HotCodexInspectionGetView(revision=request.revision, result=result)

    def inspection_search(
        self,
        request: HotCodexInspectionSearchRequest,
    ) -> HotCodexInspectionSearchView:
        """Run bounded literal search over one immutable local document."""
        with self._state_lock:
            self._validate_revision_unlocked(request.revision)
            result = self._inspection_document_unlocked().search(request.query)
            self._record_inspection_unlocked("search", len(result.hits))
            return HotCodexInspectionSearchView(revision=request.revision, result=result)

    def inspection_diff(
        self,
        request: HotCodexInspectionDiffRequest,
    ) -> HotCodexInspectionDiffView:
        """Compare retained immutable local documents structurally."""
        with self._state_lock:
            self._validate_revision_unlocked(request.revision)
            self._inspection_document_unlocked()
            result = self.inspection_archive.diff(request.query)
            self._record_inspection_unlocked("diff", len(result.changes))
            return HotCodexInspectionDiffView(revision=request.revision, result=result)

    def inspection_schema(self) -> HotCodexInspectionSchemaView:
        """Return schemas for the exact current immutable inspection document."""
        with self._state_lock:
            revision = self._revision_unlocked()
            document = self._inspection_document_unlocked()
            self._record_inspection_unlocked("schema", len(document.schema_bytes))
            return HotCodexInspectionSchemaView(
                revision=revision,
                schema_bundle=document.schema_bundle(),
            )

    def inspection_export(self) -> HotCodexInspectionExportView:
        """Return complete canonical local subjective JSON for offline inspection."""
        with self._state_lock:
            revision = self._revision_unlocked()
            exported = self._inspection_document_unlocked().export()
            self._record_inspection_unlocked("export", exported.byte_count)
            return HotCodexInspectionExportView(revision=revision, export=exported)

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
                self._record_terminal_if_reached_unlocked()
                return self._turn_index_unlocked()
        finally:
            self._wait_lock.release()

    def wait_for_brief(self) -> HotCodexTurnBrief:
        """Wait for a controlled epoch and return compact neutral context."""
        self.wait_for_turn()
        with self._state_lock:
            return self._brief_unlocked()

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
                self._command_count += 1
                policy_result_started = time.perf_counter()
                policy_result = (
                    self.policy_host.record_result(result)
                    if prepared_policy
                    else None
                )
                policy_result_ms = _elapsed_ms(policy_result_started)
                view = self._command_view_unlocked(
                    result,
                    policy_result=policy_result,
                    command_started=command_started,
                    validation_and_prepare_ms=validation_and_prepare_ms,
                    runtime_command_ms=runtime_command_ms,
                    policy_result_ms=policy_result_ms,
                )
                self._record_command_unlocked("execute", request, view)
                return view
        finally:
            self._command_lock.release()

    def execute_compact(self, request: HotCodexExecuteRequest) -> HotCodexCommandReceipt:
        """Execute one row and omit diagnostic trees from the operator response."""
        view = self.execute(request)
        with self._state_lock:
            return self._command_receipt_unlocked(view)

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
                self._command_count += 1
                view = self._command_view_unlocked(
                    result,
                    command_started=command_started,
                    validation_and_prepare_ms=validation_and_prepare_ms,
                    runtime_command_ms=runtime_command_ms,
                    policy_result_ms=0.0,
                )
                self._record_command_unlocked("end_turn", request, view)
                return view
        finally:
            self._command_lock.release()

    def end_turn_compact(self, request: HotCodexEndTurnRequest) -> HotCodexCommandReceipt:
        """End the turn and return only the next usable decision context."""
        view = self.end_turn(request)
        with self._state_lock:
            return self._command_receipt_unlocked(view)

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
                representation_profile_id=self.representation_profile_id,
                representation_manifest_digest=self.representation_manifest.manifest_digest,
                revision=revision,
                degraded_reason=self._degraded_reason,
                last_view_timing=self._last_view_timing,
                last_command_timing=getattr(self.runtime, "last_command_timing", None),
                transcript=self.transcript.status() if self.transcript is not None else None,
            )

    def transcript_status(self) -> SessionTranscriptStatus:
        """Return durable transcript state for this hot session."""
        if self.transcript is None:
            raise HotCodexRuntimeError("This runtime has no transcript recorder")
        return self.transcript.status()

    def transcript_export(self) -> SessionTranscript:
        """Return the complete validated session-subjective transcript."""
        if self.transcript is None:
            raise HotCodexRuntimeError("This runtime has no transcript recorder")
        return self.transcript.export()

    def record_operator_interaction(
        self,
        operation: str,
        response: BaseModel,
        *,
        request: Optional[BaseModel] = None,
    ) -> None:
        """Retain the exact typed payload delivered through one operator endpoint."""
        if self.transcript is None:
            return
        with self._state_lock:
            revision = self._revision_unlocked() if self._bootstrapped else None
            response_payload = response.model_dump(mode="json")
            self.transcript.record_operator_interaction(
                operation,
                {
                    "request": request.model_dump(mode="json") if request is not None else None,
                    "response": response_payload,
                    "response_byte_count": len(
                        json.dumps(
                            response_payload,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ),
                },
                encounter_uuid=revision.encounter_uuid if revision is not None else None,
                observation_cursor=(
                    revision.observation_cursor if revision is not None else None
                ),
                epoch_id=revision.epoch_id if revision is not None else None,
                actor_uuid=revision.actor_uuid if revision is not None else None,
            )

    def flush_policy_telemetry(self) -> None:
        """Wait until queued policy telemetry reaches the runtime sink."""
        self.policy_telemetry.flush()

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

    def release(self) -> HotCodexReleaseView:
        """Release the game claim and close all local resources exactly once."""
        with self._state_lock:
            if self._released:
                return HotCodexReleaseView(
                    status="already_released",
                    claim_id=self.claim_id,
                )
            self._released = True
            self._heartbeat_stop.set()
        heartbeat = self._heartbeat_thread
        if heartbeat is not None and heartbeat.is_alive():
            heartbeat.join(timeout=1.0)
        upstream_status: Optional[str] = None
        shutdown_failures: list[str] = []
        # Both local telemetry queues may still contain actor-scoped events.
        # Drain them while this session still owns its claimed entities; the
        # server correctly rejects those events after ownership is released.
        try:
            self.policy_telemetry.close()
        except Exception as exc:
            shutdown_failures.append(f"policy telemetry close: {type(exc).__name__}: {exc}")
            logger.warning("hot Codex policy telemetry close failed", exc_info=True)
        try:
            self.runtime.close()
        except Exception as exc:
            shutdown_failures.append(f"subjective runtime close: {type(exc).__name__}: {exc}")
            logger.warning("hot Codex subjective runtime close failed", exc_info=True)
        if self.control_client is not None:
            try:
                upstream = self.control_client.release(self.claim_id)
                status_value = upstream.get("status")
                upstream_status = str(status_value) if status_value is not None else None
            except Exception as exc:
                upstream_status = "unavailable"
                shutdown_failures.append(f"upstream release: {type(exc).__name__}: {exc}")
                logger.warning("hot Codex upstream release failed during local shutdown", exc_info=True)
            finally:
                try:
                    self.control_client.close()
                except Exception as exc:
                    shutdown_failures.append(f"control client close: {type(exc).__name__}: {exc}")
                    logger.warning("hot Codex control client close failed", exc_info=True)
        view = HotCodexReleaseView(
            status="released",
            claim_id=self.claim_id,
            upstream_status=upstream_status,
        )
        if self.transcript is not None:
            self.transcript.record_release(SessionReleasePayload(
                status=view.status,
                claim_id=view.claim_id,
                upstream_status=view.upstream_status,
                shutdown_failures=tuple(shutdown_failures),
            ))
        return view

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

    def _agent_state_unlocked(self) -> AgentState:
        """Return the aligned derived workspace, deriving facts when absent."""
        world = self._world_unlocked()
        agent_state = getattr(self.runtime.store, "agent_state", None)
        if not isinstance(agent_state, AgentState):
            return AgentState(facts=derive_agent_facts(world).facts)
        facts = agent_state.facts
        epoch_id = world.current_epoch.epoch_id if world.current_epoch is not None else None
        if (
            facts is None
            or facts.observation_cursor != world.observation_cursor
            or facts.epoch_id != epoch_id
        ):
            return agent_state.model_copy(update={"facts": derive_agent_facts(world).facts})
        return agent_state

    def _agent_facts_unlocked(self) -> AgentFacts:
        """Return complete typed facts aligned to the current subjective revision."""
        facts = self._agent_state_unlocked().facts
        assert facts is not None
        return facts

    def _predicate_snapshot_unlocked(self) -> PredicateLedgerSnapshot:
        """Return one cached complete predicate ledger for the current revision."""
        if self._cached_predicate_snapshot is None:
            self._cached_predicate_snapshot = self.predicate_ledger.evaluate(
                self._world_unlocked(),
                self._agent_facts_unlocked(),
                focus_profile=self.predicate_focus,
            )
        return self._cached_predicate_snapshot

    def _representation_unlocked(self) -> CodexTurnRepresentation:
        """Generate automatic profile output from local state only."""
        revision = self._revision_unlocked()
        self._ensure_projection_revision_unlocked(revision)
        if self._cached_representation is not None:
            return self._cached_representation
        world = self._world_unlocked()
        agent_state = self._agent_state_unlocked()
        retained_frames = tuple(getattr(self.runtime.store, "observation_frames", ()))
        boundary_cursor = (
            self._previous_representation_world.observation_cursor
            if self._previous_representation_world is not None
            else world.observation_cursor
        )
        decision_frames = tuple(
            frame
            for frame in retained_frames
            if boundary_cursor < frame.observation_cursor <= world.observation_cursor
        )
        policy_advice = None
        if self.representation_manifest.compatibility.preserves_eager_policy_lifecycle:
            decision, _reason = self._policy_unlocked(revision)
            if decision is not None:
                policy_advice = self._advice_unlocked(
                    decision,
                    revision,
                    detail="selected_only",
                )
        inputs = RepresentationProjectionInput(
            world=world,
            agent_state=agent_state,
            predicate_snapshot=self._predicate_snapshot_unlocked(),
            previous_world=self._previous_representation_world,
            previous_agent_state=self._previous_representation_agent_state,
            observation_frames=decision_frames,
            policy_advice=policy_advice,
            runtime_telemetry=RuntimeTelemetryInput(
                inspection_count=self._inspection_count,
                command_count=self._command_count,
                resync_count=_nonnegative_runtime_counter(self.runtime, "resync_count"),
            ),
        )
        try:
            self._cached_representation = self.representation_projector.project(
                self.representation_manifest,
                inputs,
                exposure=ExposureTiming.DECISION_EPOCH,
                component_observer=self._component_projection_event_unlocked,
            )
        except RequiredRepresentationComponentError as exc:
            self._emit_agent_event_unlocked(
                "representation.required_component_failed",
                "A required representation component failed safely.",
                payload={
                    "component_id": exc.component_id,
                    "error_type": exc.error_type,
                    "profile_id": self.representation_profile_id,
                    "manifest_digest": self.representation_manifest.manifest_digest,
                },
                tags=["representation", "failure"],
            )
            raise HotCodexRepresentationError(str(exc)) from exc
        self._previous_representation_world = world
        self._previous_representation_agent_state = AgentState(facts=agent_state.facts)
        for block in self._cached_representation.blocks:
            if isinstance(block, EncounterSummaryBlock) and block.payload.available:
                self._emit_agent_event_unlocked(
                    "representation.encounter_summary",
                    "Subjective end-of-encounter summary generated.",
                    payload={
                        "outcome": block.payload.outcome,
                        "rounds_observed": block.payload.rounds_observed,
                        "observed_damage_dealt": block.payload.observed_damage_dealt,
                        "observed_damage_taken": block.payload.observed_damage_taken,
                        "incomplete_statistics": block.payload.incomplete_statistics,
                    },
                    tags=["representation", "encounter", "summary"],
                )
        self._emit_agent_event_unlocked(
            "representation.generated",
            "Profile-driven Codex representation generated.",
            payload={
                "profile_id": self.representation_profile_id,
                "manifest_digest": self.representation_manifest.manifest_digest,
                "component_count": len(self._cached_representation.blocks),
                "timing_ms": self._cached_representation.total_timing_ms,
            },
            tags=["representation"],
        )
        return self._cached_representation

    def _inspection_document_unlocked(self) -> InspectionDocument:
        """Capture and retain the current immutable subjective inspection view."""
        if self._cached_inspection_document is not None:
            return self._cached_inspection_document
        representation = self._representation_unlocked()
        retained_frames = tuple(getattr(self.runtime.store, "observation_frames", ()))
        predicate_snapshot = self._predicate_snapshot_unlocked()
        self._cached_inspection_document = capture_inspection_document(
            world=self._world_unlocked(),
            agent_state=self._agent_state_unlocked(),
            observation_frames=retained_frames,
            predicates={
                "fact_definitions": self.predicate_ledger.fact_definitions,
                "predicate_definitions": self.predicate_ledger.predicate_definitions,
                "focus": self.predicate_focus,
                "snapshot": predicate_snapshot,
            },
            representation={
                "profile": self.representation_registry.profile(self.representation_profile_id),
                "manifest": self.representation_manifest,
                "output": representation,
            },
            profile_digest=self.representation_manifest.manifest_digest,
        )
        self.inspection_archive.add(self._cached_inspection_document)
        return self._cached_inspection_document

    def _invalidate_representation_unlocked(self, *, reset_predicates: bool) -> None:
        """Invalidate derived context without touching the local subjective world."""
        self._cached_index = None
        self._cached_representation = None
        self._cached_inspection_document = None
        self._cached_predicate_snapshot = None
        if reset_predicates:
            self.predicate_ledger.reset_history()

    def _record_inspection_unlocked(self, operation: str, result_size: int) -> None:
        """Record bounded inspection telemetry without embedding inspected values."""
        self._inspection_count += 1
        self._cached_index = None
        self._cached_representation = None
        self._cached_inspection_document = None
        self._emit_agent_event_unlocked(
            "representation.inspection_completed",
            "Local subjective inspection completed.",
            payload={
                "operation": operation,
                "result_size": result_size,
                "inspection_count": self._inspection_count,
                "manifest_digest": self.representation_manifest.manifest_digest,
            },
            tags=["representation", "inspection"],
        )

    def _emit_agent_event_unlocked(
        self,
        event_type: str,
        summary: str,
        *,
        payload: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
    ) -> None:
        """Emit representation telemetry through the shared agent-event sink."""
        sink = getattr(self.runtime, "event_sink", None)
        emit = getattr(sink, "emit", None)
        if not callable(emit):
            return
        world = self._world_unlocked()
        epoch = world.current_epoch
        try:
            emit(AgentEvent(
                session_id=world.session.session_id,
                actor_uuid=epoch.actor_uuid if epoch is not None else None,
                epoch_id=epoch.epoch_id if epoch is not None else None,
                observation_cursor=world.observation_cursor,
                event_type=event_type,
                source="ai.codex_tools.representation",
                summary=summary,
                payload=payload or {},
                tags=tags or [],
            ))
        except Exception:
            logger.exception("representation telemetry delivery failed")

    def _component_projection_event_unlocked(
        self,
        event: ComponentProjectionEvent,
    ) -> None:
        """Forward typed component lifecycle evidence to the shared telemetry sink."""
        self._emit_agent_event_unlocked(
            f"representation.component_{event.phase}",
            f"Representation component {event.phase}.",
            payload={
                **event.model_dump(mode="json"),
                "profile_id": self.representation_profile_id,
                "manifest_digest": self.representation_manifest.manifest_digest,
            },
            tags=["representation", "component", event.phase],
        )

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
            evaluation_started = time.perf_counter()
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
            except Exception as exc:
                logger.exception("optional traditional-policy oracle failed")
                self._cached_policy_unavailable_reason = (
                    f"Traditional-policy oracle failed safely ({type(exc).__name__})."
                )
            finally:
                self._cached_policy_evaluation_ms = _elapsed_ms(evaluation_started)
        self._policy_cache_ready = True
        return self._cached_policy_decision, self._cached_policy_unavailable_reason

    def _advice_unlocked(
        self,
        decision: PolicyDecision,
        revision: HotCodexRevision,
        *,
        detail: Literal["selected_only", "ranked", "full_trace"],
    ) -> AdvicePayload:
        """Bind one cached policy decision to its exact subjective revision."""
        if revision.epoch_id is None or revision.actor_uuid is None:
            raise HotCodexStaleRevisionError("Policy advice requires an active decision epoch")
        return advice_from_policy_decision(
            decision,
            basis=OracleAdviceBasis(
                session_id=revision.session_id,
                observation_cursor=revision.observation_cursor,
                epoch_id=revision.epoch_id,
                actor_uuid=revision.actor_uuid,
                policy_id=self.policy_host.policy_id,
                policy_version=self.policy_host.policy_version,
            ),
            evaluation_ms=self._cached_policy_evaluation_ms,
            detail=detail,
        )

    def _ensure_projection_revision_unlocked(self, revision: HotCodexRevision) -> None:
        """Invalidate derived local projections when the subjective revision changes."""
        if self._projection_revision == revision:
            return
        self._projection_revision = revision
        self._cached_index = None
        self._cached_policy_decision = None
        self._cached_policy_diagnostics = None
        self._cached_policy_unavailable_reason = None
        self._cached_policy_evaluation_ms = 0.0
        self._policy_cache_ready = False
        self._cached_predicate_snapshot = None
        self._cached_representation = None
        self._cached_inspection_document = None

    def _brief_unlocked(self) -> HotCodexTurnBrief:
        """Build compact context without policy advice or diagnostic timing trees."""
        index = self._turn_index_unlocked()
        action_families: Tuple[ActionFamilySummary, ...] = tuple()
        known_objects: Tuple[KnownObjectSummary, ...] = tuple()
        omitted_action_family_count = 0
        capabilities: Tuple[ActionCapabilitySummary, ...] = tuple()
        omitted_capability_count = 0
        semantic_coverage = ActionSemanticCoverage(
            source_action_count=0,
            exact_count=0,
            structured_profile_count=0,
            category_fallback_count=0,
            unknown_count=0,
        )
        encounter_summary = None
        for block in self._representation_unlocked().blocks:
            if isinstance(block, ObjectLedgerBlock):
                known_objects = block.payload.objects
            elif isinstance(block, ActionFamilyBlock):
                action_families = block.payload.families
                omitted_action_family_count = block.payload.omitted_family_count
                capabilities = block.payload.capabilities
                omitted_capability_count = block.payload.omitted_capability_count
                semantic_coverage = block.payload.semantic_coverage
            elif isinstance(block, EncounterSummaryBlock):
                encounter_summary = block.payload
        return HotCodexTurnBrief(
            revision=index.revision,
            encounter_state=index.encounter_state,
            is_terminal=index.is_terminal,
            actor=_compact_entity(index.actor) if index.actor is not None else None,
            economy=index.economy,
            controlled_entities=tuple(
                _compact_entity(entity)
                for entity in index.controlled_entities
                if entity is not None
            ),
            visible_hostiles=tuple(
                _compact_entity(entity)
                for entity in index.visible_hostiles
                if entity is not None
            ),
            remembered_hostiles=tuple(
                _compact_entity(entity)
                for entity in index.remembered_hostiles
                if entity is not None
            ),
            known_objects=tuple(_compact_known_object(item) for item in known_objects),
            action_families=tuple(
                _compact_action_family(family)
                for family in action_families
            ),
            omitted_action_family_count=omitted_action_family_count,
            capabilities=capabilities,
            omitted_capability_count=omitted_capability_count,
            semantic_coverage=semantic_coverage,
            multi_target_rows=index.action_index.multi_target_rows,
            topology=index.topology,
            recent_combat_logs=index.recent_combat_logs,
            encounter_summary=encounter_summary,
            warnings=index.warnings,
            transcript=self.transcript.status() if self.transcript is not None else None,
        )

    def _command_receipt_unlocked(
        self,
        view: HotCodexCommandView,
    ) -> HotCodexCommandReceipt:
        """Reduce a complete retained command lifecycle to operator essentials."""
        result = view.command_result
        current_brief = self._brief_unlocked()
        include_follow_up = self._component_parameter_unlocked(
            "presentation.typed_json",
            "include_command_follow_up",
        )
        follow_up = (
            _follow_up_digest(current_brief)
            if include_follow_up
            and (view.revision.epoch_id is not None or current_brief.is_terminal)
            else None
        )
        return HotCodexCommandReceipt(
            status=result.status.value,
            command_id=result.command_id,
            actor_uuid=result.actor_uuid,
            row_id=result.row_id,
            action_resolution=(
                result.action_resolution.value
                if result.action_resolution is not None
                else None
            ),
            outcome_code=result.outcome_code,
            message=result.message,
            revalidation_required=result.revalidation_required,
            revalidation_reason=result.revalidation_reason,
            resync_required=result.resync_required,
            resulting_revision=view.revision,
            follow_up=follow_up,
            local_total_ms=view.local_total_ms,
            transcript=self.transcript.status() if self.transcript is not None else None,
        )

    def _component_parameter_unlocked(
        self,
        component_id: str,
        parameter_id: str,
    ) -> bool:
        """Read one resolved boolean presentation setting from the active manifest."""
        component = next(
            (
                candidate
                for candidate in self.representation_manifest.components
                if candidate.spec.component_id == component_id
            ),
            None,
        )
        if component is None:
            raise HotCodexProfileViolationError(
                f"Active profile omits required component {component_id}"
            )
        value = component.parameters.get(parameter_id)
        if not isinstance(value, bool):
            raise HotCodexProfileViolationError(
                f"Resolved parameter {component_id}.{parameter_id} is not boolean"
            )
        return value

    def _turn_index_unlocked(self) -> HotCodexTurnIndex:
        """Adapt the profile-driven representation to the legacy turn response."""
        total_started = time.perf_counter()
        revision = self._revision_unlocked()
        self._ensure_projection_revision_unlocked(revision)
        if self._cached_index is not None:
            return self._cached_index
        policy_cache_hit = self._policy_cache_ready
        representation = self._representation_unlocked()
        turn_block: Optional[TurnCoreBlock] = None
        contact_block: Optional[ContactLedgerBlock] = None
        object_block: Optional[ObjectLedgerBlock] = None
        topology_block: Optional[TopologySummaryBlock] = None
        action_block: Optional[ActionFamilyBlock] = None
        log_block: Optional[RecentCombatLogsBlock] = None
        hypothesis_block: Optional[CombatHypothesisBlock] = None
        warning_block: Optional[WarningBlock] = None
        advice_block: Optional[AdviceBlock] = None
        for block in representation.blocks:
            if isinstance(block, TurnCoreBlock):
                turn_block = block
            elif isinstance(block, ContactLedgerBlock):
                contact_block = block
            elif isinstance(block, ObjectLedgerBlock):
                object_block = block
            elif isinstance(block, TopologySummaryBlock):
                topology_block = block
            elif isinstance(block, ActionFamilyBlock):
                action_block = block
            elif isinstance(block, RecentCombatLogsBlock):
                log_block = block
            elif isinstance(block, CombatHypothesisBlock):
                hypothesis_block = block
            elif isinstance(block, WarningBlock):
                warning_block = block
            elif isinstance(block, AdviceBlock):
                advice_block = block

        turn = turn_block.payload if turn_block is not None else None
        contacts = contact_block.payload if contact_block is not None else None
        objects = object_block.payload if object_block is not None else None
        topology_payload = topology_block.payload if topology_block is not None else None
        actions = action_block.payload if action_block is not None else None
        logs = log_block.payload if log_block is not None else None
        hypotheses = hypothesis_block.payload if hypothesis_block is not None else None
        warnings = warning_block.payload if warning_block is not None else None
        advice = advice_block.payload if advice_block is not None else None

        selected_policy = None
        policy_candidate_count = 0
        policy_trace_step_count = 0
        policy_unavailable_reason = (
            advice.unavailable_reason
            if advice is not None
            else "Policy advice is not part of the active automatic representation profile."
        )
        if advice is not None and advice.available:
            policy_decision = self._cached_policy_decision
            if policy_decision is not None:
                selected_policy = policy_decision.selected
                policy_candidate_count = len(policy_decision.candidates)
                policy_trace_step_count = len(policy_decision.trace)
                policy_unavailable_reason = None

        policy_ms = advice.evaluation_ms if advice is not None else 0.0
        timing = HotCodexIndexTiming(
            policy_ms=policy_ms,
            total_ms=representation.total_timing_ms + _elapsed_ms(total_started),
            policy_cache_hit=policy_cache_hit,
            policy_diagnostics=self._cached_policy_diagnostics,
        )
        self._last_view_timing = timing
        encounter_state = (
            turn.encounter.state
            if turn is not None and turn.encounter is not None
            else None
        )
        unknown_contacts = (
            contacts.visible_unknown_relationship
            + contacts.remembered_unknown_relationship
            + contacts.unknown_contacts
            if contacts is not None
            else tuple()
        )
        self._cached_index = HotCodexTurnIndex(
            revision=revision,
            encounter_state=encounter_state,
            is_terminal=turn.is_terminal if turn is not None else False,
            actor=turn.actor if turn is not None else None,
            economy=turn.economy if turn is not None else None,
            controlled_entities=(
                contacts.controlled_entities if contacts is not None else tuple()
            ),
            visible_hostiles=(contacts.visible_hostiles if contacts is not None else tuple()),
            remembered_hostiles=(
                contacts.remembered_hostiles if contacts is not None else tuple()
            ),
            visible_allies=(contacts.visible_allies if contacts is not None else tuple()),
            unknown_contacts=unknown_contacts,
            known_dead_contacts=(
                contacts.known_dead_contacts if contacts is not None else tuple()
            ),
            known_objects=(
                objects.complete_objects
                if objects is not None and objects.complete_objects is not None
                else tuple()
            ),
            combat_memory_hypotheses=(
                hypotheses.hypotheses if hypotheses is not None else tuple()
            ),
            topology=HotCodexTopologyIndex(
                known_tile_count=(topology_payload.known_tile_count if topology_payload is not None else 0),
                hazardous_positions=(
                    topology_payload.hazardous_positions if topology_payload is not None else tuple()
                ),
                slow_positions=(topology_payload.slow_positions if topology_payload is not None else tuple()),
                blocked_positions=(
                    topology_payload.blocked_positions if topology_payload is not None else tuple()
                ),
            ),
            action_index=HotCodexActionIndex(
                total_rows=actions.total_rows if actions is not None else 0,
                affordable_rows=actions.affordable_rows if actions is not None else 0,
                rows_by_bucket=(
                    {bucket: count for bucket, count in actions.rows_by_bucket if count > 0}
                    if actions is not None
                    else {}
                ),
                rows_by_tag=(
                    {tag: count for tag, count in actions.rows_by_tag if count > 0}
                    if actions is not None
                    else {}
                ),
                capability_count=len(actions.capabilities) if actions is not None else 0,
                multi_target_rows=tuple(
                    HotCodexMultiTargetRowSummary(**row.model_dump())
                    for row in (actions.multi_target_rows if actions is not None else tuple())
                ),
            ),
            selected_policy=selected_policy,
            policy_candidate_count=policy_candidate_count,
            policy_trace_step_count=policy_trace_step_count,
            policy_unavailable_reason=policy_unavailable_reason,
            recent_combat_logs=tuple(
                HotCodexCombatLogSummary(
                    entry_type=row.entry_type,
                    source_name=row.source_name,
                    source_uuid=row.source_uuid,
                    target_name=row.target_name,
                    target_uuid=row.target_uuid,
                    compact=row.compact,
                    success=row.success,
                    sub_entries=tuple(
                        HotCodexCombatLogSubentrySummary(
                            entry_type=child.entry_type,
                            target_name=child.target_name,
                            target_uuid=child.target_uuid,
                            compact=child.compact,
                            success=child.success,
                        )
                        for child in row.sub_entries
                    ),
                    omitted_sub_entry_count=row.omitted_sub_entry_count,
                )
                for row in (logs.logs if logs is not None else tuple())
            ),
            omitted_combat_log_count=(
                logs.source_log_count - len(logs.logs) if logs is not None else 0
            ),
            warnings=tuple(
                warning.message
                for warning in (warnings.warnings if warnings is not None else tuple())
            ),
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
        if not self.representation_manifest.compatibility.preserves_eager_policy_lifecycle:
            return False
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

    def _record_command_unlocked(
        self,
        operation: Literal["execute", "end_turn"],
        request: HotCodexExecuteRequest | HotCodexEndTurnRequest,
        view: HotCodexCommandView,
    ) -> None:
        """Retain one command lifecycle and terminal subjective state, if reached."""
        if self.transcript is None:
            return
        result = view.command_result
        self.transcript.record_command(
            {
                "operation": operation,
                "request": request.model_dump(mode="json"),
                "result": result.model_dump(mode="json"),
                "resulting_revision": view.revision.model_dump(mode="json"),
                "policy_result": (
                    view.policy_result.model_dump(mode="json")
                    if view.policy_result is not None
                    else None
                ),
                "local_timing": view.local_timing.model_dump(mode="json"),
                "runtime_timing": view.runtime_timing,
            },
            encounter_uuid=view.revision.encounter_uuid,
            observation_cursor=view.revision.observation_cursor,
            epoch_id=result.current_epoch_id or result.requested_epoch_id,
            actor_uuid=result.actor_uuid,
            command_id=result.command_id,
        )
        self._record_terminal_if_reached_unlocked()

    def _record_terminal_if_reached_unlocked(self) -> None:
        """Retain terminal subjective state once, regardless of who ended play."""
        if self.transcript is None:
            return
        world = self._world_unlocked()
        if world.encounter is None or world.encounter.state != "ended":
            return
        revision = self._revision_unlocked()
        summary = self._brief_unlocked().encounter_summary
        self.transcript.record_terminal(
            {
                "final_revision": revision.model_dump(mode="json"),
                "final_subjective_world": world.model_dump(mode="json"),
                "encounter_summary": (
                    summary.model_dump(mode="json")
                    if summary is not None
                    else None
                ),
            },
            encounter_uuid=world.encounter.uuid,
            cursor=world.observation_cursor,
        )

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

    @app.exception_handler(HotCodexProfileViolationError)
    def profile_violation_handler(_request: Any, exc: HotCodexProfileViolationError) -> Any:
        return _error_response(409, "profile_violation", str(exc))

    @app.exception_handler(HotCodexRepresentationError)
    def representation_failure_handler(_request: Any, exc: HotCodexRepresentationError) -> Any:
        return _error_response(503, "representation_failed", str(exc))

    @app.exception_handler(HotCodexUnknownProfileError)
    def unknown_profile_handler(_request: Any, exc: HotCodexUnknownProfileError) -> Any:
        return _error_response(404, "unknown_profile", str(exc))

    @app.get("/v1/health", response_model=HotCodexHealth, dependencies=[Depends(authorize)])
    def health() -> HotCodexHealth:
        response = session.health()
        session.record_operator_interaction("health", response)
        return response

    @app.get("/v1/revision", response_model=HotCodexRevision, dependencies=[Depends(authorize)])
    def revision() -> HotCodexRevision:
        response = session.revision()
        session.record_operator_interaction("revision", response)
        return response

    @app.get("/v1/turn", response_model=HotCodexTurnIndex, dependencies=[Depends(authorize)])
    def turn() -> HotCodexTurnIndex:
        response = session.turn_index()
        session.record_operator_interaction("turn", response)
        return response

    @app.get("/v1/brief", response_model=HotCodexTurnBrief, dependencies=[Depends(authorize)])
    def brief() -> HotCodexTurnBrief:
        response = session.brief()
        session.record_operator_interaction("brief", response)
        return response

    @app.post("/v1/watch", response_model=HotCodexTurnIndex, dependencies=[Depends(authorize)])
    def watch() -> HotCodexTurnIndex:
        response = session.wait_for_turn()
        session.record_operator_interaction("watch", response)
        return response

    @app.post(
        "/v1/watch/brief",
        response_model=HotCodexTurnBrief,
        dependencies=[Depends(authorize)],
    )
    def watch_brief() -> HotCodexTurnBrief:
        response = session.wait_for_brief()
        session.record_operator_interaction("watch_brief", response)
        return response

    @app.post("/v1/query", response_model=HotCodexQueryResult, dependencies=[Depends(authorize)])
    def query(request: HotCodexQueryRequest) -> HotCodexQueryResult:
        response = session.query(request)
        session.record_operator_interaction("query", response, request=request)
        return response

    @app.get(
        "/v1/representation/profile",
        response_model=HotCodexProfileView,
        dependencies=[Depends(authorize)],
    )
    def representation_profile() -> HotCodexProfileView:
        response = session.profile_view()
        session.record_operator_interaction("profile", response)
        return response

    @app.post(
        "/v1/representation/profile/select",
        response_model=HotCodexProfileView,
        dependencies=[Depends(authorize)],
    )
    def select_representation_profile(
        request: HotCodexProfileSelectRequest,
    ) -> HotCodexProfileView:
        response = session.select_profile(request)
        session.record_operator_interaction("profile_select", response, request=request)
        return response

    @app.get(
        "/v1/representation/components",
        response_model=HotCodexComponentCatalog,
        dependencies=[Depends(authorize)],
    )
    def representation_components() -> HotCodexComponentCatalog:
        response = session.component_catalog()
        session.record_operator_interaction("component_catalog", response)
        return response

    @app.get(
        "/v1/representation/current",
        response_model=HotCodexRepresentationView,
        dependencies=[Depends(authorize)],
    )
    def current_representation() -> HotCodexRepresentationView:
        response = session.representation()
        session.record_operator_interaction("representation", response)
        return response

    @app.post(
        "/v1/representation/oracle",
        response_model=HotCodexOracleView,
        dependencies=[Depends(authorize)],
    )
    def representation_oracle(request: HotCodexOracleRequest) -> HotCodexOracleView:
        response = session.oracle(request)
        session.record_operator_interaction("oracle", response, request=request)
        return response

    @app.post(
        "/v1/geometry/query",
        response_model=HotCodexGeometryView,
        dependencies=[Depends(authorize)],
    )
    def subjective_geometry(request: HotCodexGeometryRequest) -> HotCodexGeometryView:
        response = session.geometry(request)
        session.record_operator_interaction("geometry", response, request=request)
        return response

    @app.get(
        "/v1/predicates/catalog",
        response_model=HotCodexPredicateCatalog,
        dependencies=[Depends(authorize)],
    )
    def predicate_catalog() -> HotCodexPredicateCatalog:
        response = session.predicate_catalog()
        session.record_operator_interaction("predicate_catalog", response)
        return response

    @app.post(
        "/v1/predicates/register",
        response_model=PredicateDefinition,
        dependencies=[Depends(authorize)],
    )
    def register_predicate(
        request: HotCodexPredicateRegisterRequest,
    ) -> PredicateDefinition:
        response = session.register_predicate(request)
        session.record_operator_interaction("predicate_register", response, request=request)
        return response

    @app.post(
        "/v1/predicates/evaluate",
        response_model=PredicateLedgerSnapshot,
        dependencies=[Depends(authorize)],
    )
    def evaluate_predicates(
        request: HotCodexPredicateEvaluateRequest,
    ) -> PredicateLedgerSnapshot:
        response = session.evaluate_predicates(request)
        session.record_operator_interaction("predicate_evaluate", response, request=request)
        return response

    @app.get(
        "/v1/predicates/focus",
        response_model=PredicateFocusProfile,
        dependencies=[Depends(authorize)],
    )
    def predicate_focus() -> PredicateFocusProfile:
        response = session.predicate_focus_view()
        session.record_operator_interaction("predicate_focus", response)
        return response

    @app.post(
        "/v1/predicates/focus",
        response_model=PredicateFocusProfile,
        dependencies=[Depends(authorize)],
    )
    def set_predicate_focus(
        request: HotCodexPredicateFocusRequest,
    ) -> PredicateFocusProfile:
        response = session.set_predicate_focus(request)
        session.record_operator_interaction("predicate_focus_set", response, request=request)
        return response

    @app.get(
        "/v1/inspect/catalog",
        response_model=HotCodexInspectionCatalogView,
        dependencies=[Depends(authorize)],
    )
    def inspection_catalog() -> HotCodexInspectionCatalogView:
        response = session.inspection_catalog()
        session.record_operator_interaction("inspection_catalog", response)
        return response

    @app.post(
        "/v1/inspect/get",
        response_model=HotCodexInspectionGetView,
        dependencies=[Depends(authorize)],
    )
    def inspection_get(request: HotCodexInspectionGetRequest) -> HotCodexInspectionGetView:
        response = session.inspection_get(request)
        session.record_operator_interaction("inspection_get", response, request=request)
        return response

    @app.post(
        "/v1/inspect/search",
        response_model=HotCodexInspectionSearchView,
        dependencies=[Depends(authorize)],
    )
    def inspection_search(
        request: HotCodexInspectionSearchRequest,
    ) -> HotCodexInspectionSearchView:
        response = session.inspection_search(request)
        session.record_operator_interaction("inspection_search", response, request=request)
        return response

    @app.post(
        "/v1/inspect/diff",
        response_model=HotCodexInspectionDiffView,
        dependencies=[Depends(authorize)],
    )
    def inspection_diff(request: HotCodexInspectionDiffRequest) -> HotCodexInspectionDiffView:
        response = session.inspection_diff(request)
        session.record_operator_interaction("inspection_diff", response, request=request)
        return response

    @app.get(
        "/v1/inspect/schema",
        response_model=HotCodexInspectionSchemaView,
        dependencies=[Depends(authorize)],
    )
    def inspection_schema() -> HotCodexInspectionSchemaView:
        response = session.inspection_schema()
        session.record_operator_interaction("inspection_schema", response)
        return response

    @app.get(
        "/v1/inspect/export",
        response_model=HotCodexInspectionExportView,
        dependencies=[Depends(authorize)],
    )
    def inspection_export() -> HotCodexInspectionExportView:
        response = session.inspection_export()
        session.record_operator_interaction("inspection_export", response)
        return response

    @app.post("/v1/execute", response_model=HotCodexCommandView, dependencies=[Depends(authorize)])
    def execute(request: HotCodexExecuteRequest) -> HotCodexCommandView:
        response = session.execute(request)
        session.record_operator_interaction("execute_diagnostic", response, request=request)
        return response

    @app.post(
        "/v1/execute/compact",
        response_model=HotCodexCommandReceipt,
        dependencies=[Depends(authorize)],
    )
    def execute_compact(request: HotCodexExecuteRequest) -> HotCodexCommandReceipt:
        response = session.execute_compact(request)
        session.record_operator_interaction("execute", response, request=request)
        return response

    @app.post("/v1/end-turn", response_model=HotCodexCommandView, dependencies=[Depends(authorize)])
    def end_turn(request: HotCodexEndTurnRequest) -> HotCodexCommandView:
        response = session.end_turn(request)
        session.record_operator_interaction("end_turn_diagnostic", response, request=request)
        return response

    @app.post(
        "/v1/end-turn/compact",
        response_model=HotCodexCommandReceipt,
        dependencies=[Depends(authorize)],
    )
    def end_turn_compact(request: HotCodexEndTurnRequest) -> HotCodexCommandReceipt:
        response = session.end_turn_compact(request)
        session.record_operator_interaction("end_turn", response, request=request)
        return response

    @app.post(
        "/v1/release",
        response_model=HotCodexReleaseView,
        dependencies=[Depends(authorize)],
    )
    def release() -> HotCodexReleaseView:
        return session.release()

    @app.get(
        "/v1/transcript/status",
        response_model=SessionTranscriptStatus,
        dependencies=[Depends(authorize)],
    )
    def transcript_status() -> SessionTranscriptStatus:
        return session.transcript_status()

    @app.get(
        "/v1/transcript",
        response_model=SessionTranscript,
        dependencies=[Depends(authorize)],
    )
    def transcript_export() -> SessionTranscript:
        return session.transcript_export()

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
        representation_profile_id=session.representation_profile_id,
        representation_manifest_digest=session.representation_manifest.manifest_digest,
        bearer_token=bearer_token,
        transcript=session.transcript.status() if session.transcript is not None else None,
    )


def _resolved_claim_faction(claim: TakeoverClaimInfo, requested_faction: str) -> str:
    """Resolve an accurate display faction for faction or explicit-entity claims."""
    if claim.faction is not None:
        return claim.faction
    entity_factions = {
        row.faction
        for row in claim.claimed_entities
        if row.faction is not None
    }
    if len(entity_factions) == 1:
        return next(iter(entity_factions))
    if len(entity_factions) > 1:
        return "mixed"
    return requested_faction


def _compact_entity(entity: ObservationEntityFact) -> HotCodexEntitySummary:
    """Remove detailed condition internals from one automatic entity summary."""
    return HotCodexEntitySummary(
        uuid=entity.uuid,
        name=entity.name,
        knowledge_state=entity.knowledge_state.value,
        controlled=entity.controlled,
        position=entity.position,
        hp=entity.hp,
        max_hp=entity.max_hp,
        ac=entity.ac,
        conditions=tuple(entity.conditions),
        condition_semantic_keys=tuple(entity.condition_semantic_keys or ()),
        faction=entity.faction,
        is_dead=entity.is_dead,
    )


def _compact_known_object(item: KnownObjectSummary) -> HotCodexObjectSummary:
    """Keep typed object state while omitting observer and rendering details."""
    return HotCodexObjectSummary(
        uuid=item.uuid,
        name=item.name,
        knowledge_state=item.knowledge_state.value,
        position=item.position,
        is_open=item.is_open,
        state_keys=item.state_keys,
    )


def _compact_action_family(item: ActionFamilySummary) -> HotCodexActionFamilyDigest:
    """Remove catalog references and derivation internals from one family summary."""
    return HotCodexActionFamilyDigest(
        source_action_id=item.source_action_id,
        semantic_key=item.semantic_key,
        display_name=item.display_name,
        semantic_id=item.semantic_id,
        bucket=item.bucket,
        action_category=item.action_category,
        target_type=item.target_type,
        row_count=item.row_count,
        direct_row_id=item.direct_row_id,
        affordable_row_count=item.affordable_row_count,
        cost=item.cost,
        target_option_count=item.target_option_count,
        allocation_count=item.allocation_count,
        allow_same_target=item.allow_same_target,
        spell_level=item.spell_level,
        cast_at_level=item.cast_at_level,
        requires_concentration=item.requires_concentration,
        tags=item.tags,
    )


def _follow_up_digest(brief: HotCodexTurnBrief) -> HotCodexFollowUpDigest:
    """Project a full automatic brief into one command-chain continuation payload."""
    return HotCodexFollowUpDigest(
        revision=brief.revision,
        encounter_state=brief.encounter_state,
        is_terminal=brief.is_terminal,
        actor=brief.actor,
        economy=brief.economy,
        visible_hostiles=brief.visible_hostiles,
        remembered_hostiles=brief.remembered_hostiles,
        known_objects=brief.known_objects,
        action_families=brief.action_families,
        omitted_action_family_count=brief.omitted_action_family_count,
        semantic_coverage=brief.semantic_coverage,
        multi_target_rows=brief.multi_target_rows,
        recent_combat_logs=brief.recent_combat_logs,
        encounter_summary=brief.encounter_summary,
        warnings=brief.warnings,
    )


def _default_predicate_focus() -> PredicateFocusProfile:
    """Return neutral automatic logical attention for the balanced Codex view."""
    predicate_ids = (
        "actor.can_act",
        "contacts.has_visible_hostile",
        "contacts.has_remembered_hostile",
        "objects.has_known_closed_door",
        "topology.has_known_hazard",
        "affordances.has_legal_action",
        "memory.has_effect_block_hypothesis",
        "encounter.is_terminal",
    )
    return PredicateFocusProfile(
        profile_id="codex.default_focus_v1",
        always_include=("actor.can_act", "affordances.has_legal_action", "encounter.is_terminal"),
        include_when_true=predicate_ids,
        include_when_changed=predicate_ids,
        max_automatic_items=16,
    )


def _nonnegative_runtime_counter(runtime: object, attribute: str) -> int:
    """Read one optional runtime counter without accepting booleans or negatives."""
    value = getattr(runtime, attribute, 0)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


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
