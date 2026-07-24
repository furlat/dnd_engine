"""In-process external-vs-external validation runner."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field as dataclass_field
from typing import Callable, Mapping, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from ai.knowledge import AgentFacts, derive_agent_facts
from server.agent_runtime.observation_projector import (
    ObservationAccessError,
    iter_observation_frames,
)
from server.agent_protocol.observation import SubjectiveWorldState
from ai.policy import (
    command_from_policy_decision,
    ExecuteIntent,
    policy_memory_trace,
    PolicyExecutionConstraints,
    PolicyContext,
    PolicyHost,
    PolicyMemoryStore,
    PolicyTraceStep,
)
from ai.policy.contracts import CapabilityTargetProjection
from ai.policy.definitions import PolicyGenerationIdentity, PolicyImplementation
from ai.policy.generations.current_commitments import create_generation_policy_host
from ai.policy.generations.registry import (
    CANDIDATE_GENERATION_ID,
    get_policy_implementation,
)
from server.agent_protocol.control import (
    ActionEconomyState,
    AgentEndTurnCommandRequest,
    AgentExecuteCommandRequest,
    CommandResult,
    CommandResultStatus,
)
from server.runtime_performance import latency_sensitive_gc
from ai.subjective.store import ApplyResultKind, SubjectiveStore
from dnd.controller import ExternalAIController
from dnd.core.combat_log import CombatLogEntry
from dnd.core.events import EventPhase, EventQueue, SensoryUpdateEvent
from dnd.encounter import EncounterState
from dnd.entity import Entity
from dnd.scenarios.ai_validation_arenas import ValidationArena, create_ai_validation_arena
from dnd.spells.effect_ids import COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
from server.arena_mode import ArenaApiClient, reset_standard_arena_runtime
from server.event_server import advance_encounter, sim
from server.session import PlayerType


DEEP_DIAGNOSTIC_SAMPLE_INTERVAL = 10
STALEMATE_COMMAND_WINDOW = 80


class SelfPlayActionSummary(BaseModel):
    """Compact available-action row stored for probe diagnostics."""

    template_name: str = Field(description="Action template name.")
    can_afford: bool = Field(description="Whether the row was affordable.")
    target_count: int = Field(description="Number of executable targets.")


class ExternalSelfPlayTrace(BaseModel):
    """One command selected by the external-vs-external runner."""

    command_index: int = Field(description="Zero-based command index.")
    round_number: int = Field(description="Encounter round at selection time.")
    turn_index: int = Field(description="Encounter turn index at selection time.")
    session_id: str = Field(description="Session that owned the active actor.")
    policy_generation_id: str = Field(
        default="external.default",
        description="Executable policy generation controlling this command.",
    )
    policy_version: str = Field(
        default="unversioned",
        description="Behavior version controlling this command.",
    )
    policy_executable_sha256: Optional[str] = Field(
        default=None,
        description="Authenticated executable generation hash when a registered implementation was used.",
    )
    actor_uuid: str = Field(description="Active actor UUID.")
    actor_name: str = Field(description="Active actor display name.")
    actor_faction: Optional[str] = Field(default=None, description="Active actor faction.")
    actor_position: Optional[tuple[int, int]] = Field(default=None, description="Active actor position.")
    actor_previous_position: Optional[tuple[int, int]] = Field(
        default=None,
        description="Previous actor position inferred from subjective movement logs.",
    )
    actor_hp: Optional[int] = Field(default=None, description="Active actor HP when known locally.")
    actor_conditions: list[str] = Field(default_factory=list, description="Subjective active actor conditions.")
    actor_economy: Optional[ActionEconomyState] = Field(
        default=None,
        description="Server-issued action economy and resources at the selected decision epoch.",
    )
    visible_enemy_names: list[str] = Field(default_factory=list, description="Visible hostile names in subjective facts.")
    remembered_enemy_names: list[str] = Field(default_factory=list, description="Remembered hostile names in subjective facts.")
    suppressed_remembered_enemy_names: list[str] = Field(
        default_factory=list,
        description="Remembered enemy names suppressed by bounded local search memory.",
    )
    policy_memory: dict[str, object] = Field(default_factory=dict, description="Policy memory trace at selection time.")
    routine_revalidation: dict[str, object] = Field(
        default_factory=dict,
        description="Typed reconciliation of routine memory with this subjective epoch.",
    )
    policy_trace: list[PolicyTraceStep] = Field(default_factory=list, description="Hierarchical policy evaluation trace.")
    capability_target_projection: Optional[CapabilityTargetProjection] = Field(
        default=None,
        description="Selected target-bound capability evidence when the policy used a future tactical envelope.",
    )
    fact_invalidated_sections: list[str] = Field(default_factory=list, description="Typed fact sections rebuilt for this decision.")
    fact_timing: dict[str, float] = Field(default_factory=dict, description="Typed fact derivation timings by section.")
    unresolved_hostile_names: list[str] = Field(
        default_factory=list,
        description="Hostile names inferred from subjective combat logs without positioned memory.",
    )
    entity_action_count: int = Field(description="Reduced entity action count.")
    position_action_count: int = Field(description="Reduced position action count.")
    self_actions: list[SelfPlayActionSummary] = Field(default_factory=list, description="First self action summaries.")
    command_type: str = Field(description="Selected command type.")
    row_id: Optional[str] = Field(default=None, description="Selected decision-epoch row id.")
    template_name: Optional[str] = Field(default=None, description="Selected action template name.")
    semantic_key: Optional[str] = Field(default=None, description="Selected typed action-family key.")
    action_category: Optional[str] = Field(
        default=None,
        description="Selected engine action category retained for capability-coverage analysis.",
    )
    available_action_semantic_keys: list[str] = Field(
        default_factory=list,
        description="Distinct action identities exposed in the selected decision epoch.",
    )
    affordable_action_semantic_keys: list[str] = Field(
        default_factory=list,
        description="Distinct exposed action identities affordable in the selected epoch.",
    )
    available_item_action_semantic_keys: list[str] = Field(
        default_factory=list,
        description="Distinct exposed action identities supplied by items or spatial objects.",
    )
    target_uuid: Optional[str] = Field(default=None, description="Selected target UUID when present.")
    target_name: Optional[str] = Field(default=None, description="Selected target name.")
    target_position: Optional[tuple[int, int]] = Field(default=None, description="Selected target position.")
    target_distance: Optional[int] = Field(default=None, description="Selected target distance in feet when known.")
    target_path_cost: Optional[int] = Field(default=None, description="Selected movement path cost when known.")
    target_safe_path_cost: Optional[int] = Field(default=None, description="Selected safe movement path cost when known.")
    target_path_hazardous: bool = Field(default=False, description="Whether the selected movement path crosses known hazards.")
    target_path: list[tuple[int, int]] = Field(default_factory=list, description="Selected movement path cells when known.")
    target_safe_path: list[tuple[int, int]] = Field(default_factory=list, description="Selected safe movement path cells when known.")
    affected_entity_uuids: list[str] = Field(default_factory=list, description="Entity UUIDs affected by a selected area target.")
    affected_entity_names: list[str] = Field(default_factory=list, description="Known names for entities affected by a selected area target.")
    affected_entity_positions: list[tuple[int, int]] = Field(
        default_factory=list,
        description="Known positions for entities affected by a selected area target.",
    )
    affected_enemy_count: int = Field(default=0, description="Known non-controlled living entities affected by the selected target.")
    affected_controlled_count: int = Field(default=0, description="Known controlled living entities affected by the selected target.")
    reference_entity_uuid: Optional[str] = Field(
        default=None,
        description="Subjective entity UUID used as command context when the command has no direct target.",
    )
    reference_entity_name: Optional[str] = Field(
        default=None,
        description="Subjective entity name used as command context when the command has no direct target.",
    )
    reference_entity_position: Optional[tuple[int, int]] = Field(
        default=None,
        description="Subjective entity position used as command context when the command has no direct target.",
    )
    reference_entity_distance_cells: Optional[int] = Field(
        default=None,
        description="Grid-cell distance from the actor to the reference entity.",
    )
    spacing_floor_cells: Optional[int] = Field(
        default=None,
        description="Minimum grid-cell spacing floor used by ranged spacing decisions.",
    )
    spacing_anchor_position: Optional[tuple[int, int]] = Field(
        default=None,
        description="Actor or selected anchor position preserved by a hold-spacing decision.",
    )
    nearest_controlled_ally_distance_cells: Optional[int] = Field(
        default=None,
        description="Nearest controlled ally distance at the selected spacing anchor or destination.",
    )
    ally_spacing_floor_cells: Optional[int] = Field(
        default=None,
        description="Anti-area-effect ally spacing floor used by the selected command.",
    )
    extra_target_uuids: Optional[list[str]] = Field(default=None, description="Additional target UUIDs selected for multi-entity rows.")
    extra_target_names: Optional[list[str]] = Field(default=None, description="Additional target names selected for multi-entity rows.")
    extra_target_positions: Optional[list[tuple[int, int]]] = Field(
        default=None,
        description="Additional target positions selected for multi-entity rows.",
    )
    reason: str = Field(description="Policy reason.")
    logical_tags: list[str] = Field(default_factory=list, description="Selected logical tags.")
    routine_id: Optional[str] = Field(default=None, description="Bounded routine that selected the command.")
    routine_step_id: Optional[str] = Field(default=None, description="Routine step realized by the command.")
    routine_next_step_id: Optional[str] = Field(default=None, description="Progress stored after acceptance.")
    routine_target_uuid: Optional[str] = Field(default=None, description="Subjectively known routine target UUID.")
    routine_target_position: Optional[tuple[int, int]] = Field(
        default=None,
        description="Subjectively known routine target position.",
    )
    routine_started_epoch_index: Optional[int] = Field(
        default=None,
        description="First decision epoch of this actor-owned routine.",
    )
    outcome_logical_tags: list[str] = Field(default_factory=list, description="Outcome tags inferred from command result.")
    command_status: Optional[str] = Field(default=None, description="Command result status.")
    action_resolution: Optional[str] = Field(default=None, description="Typed gameplay resolution of the accepted command.")
    outcome_code: Optional[str] = Field(default=None, description="Stable machine-readable engine outcome.")
    command_message: Optional[str] = Field(default=None, description="Command result message.")
    command_result_payload: dict[str, object] = Field(
        default_factory=dict,
        description="Complete typed command-result response retained for diagnosis.",
    )
    deep_diagnostics_enabled: bool = Field(
        default=False,
        description="Whether this command sampled deep server and engine timing probes.",
    )
    snapshot_loaded: bool = Field(default=False, description="Whether this command bootstrapped a session snapshot.")
    snapshot_ms: Optional[float] = Field(default=None, description="Milliseconds spent fetching and validating snapshot.")
    materialize_ms: Optional[float] = Field(default=None, description="Milliseconds spent materializing subjective world state.")
    frame_fetch_ms: Optional[float] = Field(default=None, description="Aggregate milliseconds spent fetching subjective frames before and after the command.")
    frame_apply_ms: Optional[float] = Field(default=None, description="Aggregate milliseconds spent applying subjective frames before and after the command.")
    frame_count: int = Field(default=0, description="Aggregate subjective frames applied before and after the command.")
    pre_command_sync_ms: Optional[float] = Field(
        default=None,
        description="Milliseconds spent loading or catching up the local subjective store before policy evaluation.",
    )
    pre_command_frame_fetch_ms: Optional[float] = Field(
        default=None,
        description="Milliseconds spent fetching persisted frames before policy evaluation.",
    )
    pre_command_frame_apply_ms: Optional[float] = Field(
        default=None,
        description="Milliseconds spent applying persisted frames before policy evaluation.",
    )
    pre_command_frame_count: int = Field(
        default=0,
        description="Persisted subjective frames applied before policy evaluation.",
    )
    followup_frame_fetch_ms: Optional[float] = Field(
        default=None,
        description="Milliseconds spent fetching persisted command-result and follow-up frames.",
    )
    followup_frame_apply_ms: Optional[float] = Field(
        default=None,
        description="Milliseconds spent applying persisted command-result and follow-up frames.",
    )
    followup_frame_count: int = Field(
        default=0,
        description="Persisted command-result and follow-up frames applied after submission.",
    )
    server_timing: dict[str, object] = Field(default_factory=dict, description="Server-side command timing payload.")
    action_server_timing: dict[str, object] = Field(
        default_factory=dict,
        description="Nested engine action-route timing retained from the subjective command-result frame.",
    )
    affordance_timing: dict[str, float] = Field(
        default_factory=dict,
        description="Subphase timings for decision-epoch affordance projection.",
    )
    policy_diagnostics: dict[str, object] = Field(
        default_factory=dict,
        description="Policy-host stage timings and bounded-work counters for this decision.",
    )
    reduction_timing: dict[str, float] = Field(
        default_factory=dict,
        description="Subphase timings for reduced external-agent state construction.",
    )
    reduce_ms: Optional[float] = Field(default=None, description="Milliseconds spent building available payload and reduced agent state.")
    fact_ms: Optional[float] = Field(default=None, description="Milliseconds spent deriving typed shared policy facts.")
    policy_ms: Optional[float] = Field(default=None, description="Milliseconds spent selecting a behavior-tree command.")
    local_decision_ms: Optional[float] = Field(default=None, description="Combined reduction, fact, and policy time before command submission.")
    command_http_ms: Optional[float] = Field(
        default=None,
        description="Milliseconds spent on the command HTTP request and response.",
    )
    command_followup_sync_ms: Optional[float] = Field(
        default=None,
        description="Milliseconds spent fetching and applying post-command subjective frames.",
    )
    command_submit_ms: Optional[float] = Field(
        default=None,
        description="Aggregate command cycle including transport and follow-up synchronization.",
    )
    total_ms: Optional[float] = Field(default=None, description="Total milliseconds spent selecting and submitting this command.")
    subjective_known_entity_uuids: list[str] = Field(default_factory=list, description="Entity UUIDs present in the subjective world.")
    subjective_known_entity_positions: list[tuple[int, int]] = Field(default_factory=list, description="Known or remembered entity positions.")
    subjective_known_object_uuids: list[str] = Field(default_factory=list, description="Object UUIDs present in the subjective world.")
    subjective_known_object_positions: list[tuple[int, int]] = Field(default_factory=list, description="Known or remembered object positions.")
    subjective_known_tile_positions: list[tuple[int, int]] = Field(default_factory=list, description="Tile positions present in the subjective world.")
    subjective_visible_cell_positions: list[tuple[int, int]] = Field(
        default_factory=list,
        description="Cells currently visible to at least one controlled subjective observer.",
    )
    subjective_seen_cell_positions: list[tuple[int, int]] = Field(
        default_factory=list,
        description="Cells remembered as seen by at least one controlled subjective observer.",
    )
    subjective_affordance_row_ids: list[str] = Field(default_factory=list, description="Server-issued legal row ids for this epoch.")
    subjective_affordance_target_uuids: list[str] = Field(default_factory=list, description="Target UUIDs disclosed by legal rows.")
    subjective_affordance_target_positions: list[tuple[int, int]] = Field(default_factory=list, description="Target positions disclosed by legal rows.")
    audit_controlled_entity_uuids: list[str] = Field(
        default_factory=list,
        description="Evaluator-only controlled identities independently authorized at decision time.",
    )
    audit_authorized_entity_uuids: list[str] = Field(
        default_factory=list,
        description="Evaluator-only entity identities authorized by senses or event-time grants.",
    )
    audit_authorized_object_uuids: list[str] = Field(
        default_factory=list,
        description="Evaluator-only object identities authorized by senses or ownership.",
    )
    audit_authorized_positions: list[tuple[int, int]] = Field(
        default_factory=list,
        description="Evaluator-only cells authorized by accumulated observer perception.",
    )


class ExternalSelfPlayResult(BaseModel):
    """Result of one local external-vs-external validation run."""

    arena_id: str = Field(description="Validation arena id.")
    status: str = Field(description="Run status.")
    command_count: int = Field(description="Number of selected commands.")
    elapsed_ms: float = Field(description="Total runner wall-clock duration in milliseconds.")
    session_ids_by_faction: dict[str, str] = Field(description="AI session UUIDs keyed by faction.")
    policy_generations_by_faction: dict[str, PolicyGenerationIdentity] = Field(
        default_factory=dict,
        description="Authenticated executable policy generation assigned to each faction.",
    )
    final_round: Optional[int] = Field(default=None, description="Encounter round at the end of the run.")
    final_state: Optional[str] = Field(default=None, description="Encounter lifecycle state at the end.")
    final_hp_by_actor: dict[str, int] = Field(default_factory=dict, description="Final HP keyed by actor name.")
    final_faction_by_actor: dict[str, str] = Field(
        default_factory=dict,
        description="Final faction keyed by actor name for outcome extraction.",
    )
    stalemate_evidence: Optional["StalemateEvidence"] = Field(
        default=None,
        description="Evaluator-only finite-horizon evidence when victory progress stopped.",
    )
    traces: list[ExternalSelfPlayTrace] = Field(default_factory=list, description="Selected command traces.")


class StalemateEvidence(BaseModel):
    """Objective evaluator evidence for a finite-horizon draw adjudication."""

    command_window: int = Field(gt=0, description="Accepted-command window with no HP-vector change.")
    start_command_index: int = Field(ge=0, description="First command index in the no-progress window.")
    end_command_index: int = Field(ge=0, description="Last command index in the no-progress window.")
    unchanged_hp_by_actor: dict[str, int] = Field(
        description="Complete combatant HP vector shared by every sample in the window."
    )


@dataclass
class SelfPlayStoreTiming:
    """Timing result for maintaining a persistent self-play subjective store."""

    snapshot_loaded: bool = False
    snapshot_ms: Optional[float] = None
    materialize_ms: Optional[float] = None
    frame_fetch_ms: float = 0.0
    frame_apply_ms: float = 0.0
    frame_count: int = 0
    resynced: bool = False

    def merge(self, other: "SelfPlayStoreTiming") -> None:
        """Merge another timing sample into this one."""
        self.snapshot_loaded = self.snapshot_loaded or other.snapshot_loaded
        self.snapshot_ms = _merge_optional_ms(self.snapshot_ms, other.snapshot_ms)
        self.materialize_ms = _merge_optional_ms(self.materialize_ms, other.materialize_ms)
        self.frame_fetch_ms += other.frame_fetch_ms
        self.frame_apply_ms += other.frame_apply_ms
        self.frame_count += other.frame_count
        self.resynced = self.resynced or other.resynced


@dataclass
class SubjectivityAuditMemory:
    """Independent evaluator memory accumulated from objective perception grants."""

    controlled_entity_uuids: set[str] = dataclass_field(default_factory=set)
    authorized_entity_uuids: set[str] = dataclass_field(default_factory=set)
    authorized_object_uuids: set[str] = dataclass_field(default_factory=set)
    authorized_positions: set[tuple[int, int]] = dataclass_field(default_factory=set)
    source_event_cursor: int = 0


def run_external_selfplay(
    arena_id: str,
    *,
    max_commands: int = 60,
    hero_first: bool = True,
    random_seed: Optional[int] = None,
    arena_observer: Optional[Callable[[ValidationArena], None]] = None,
    policy_implementations_by_faction: Optional[Mapping[str, PolicyImplementation]] = None,
) -> ExternalSelfPlayResult:
    """Run both factions through the external AI subjective command contract.

    Args:
        arena_id: Validation arena id from the scenario catalog.
        max_commands: Maximum commands to select before stopping.
        hero_first: Whether to put the hero at the front of initiative.
        random_seed: Optional deterministic seed restored after the run.
        arena_observer: Optional precombat observer invoked on the exact arena
            instance after external controllers are installed.

    Returns:
        Typed self-play trace result.
    """
    with latency_sensitive_gc():
        if random_seed is None:
            return _run_external_selfplay(
                arena_id,
                max_commands=max_commands,
                hero_first=hero_first,
                arena_observer=arena_observer,
                policy_implementations_by_faction=policy_implementations_by_faction,
            )

        previous_random_state = random.getstate()
        random.seed(random_seed)
        try:
            return _run_external_selfplay(
                arena_id,
                max_commands=max_commands,
                hero_first=hero_first,
                arena_observer=arena_observer,
                policy_implementations_by_faction=policy_implementations_by_faction,
            )
        finally:
            random.setstate(previous_random_state)


def run_external_selfplay_with_arena_factory(
    arena_id: str,
    arena_factory: Callable[[], ValidationArena],
    *,
    max_commands: int = 60,
    random_seed: Optional[int] = None,
    arena_observer: Optional[Callable[[ValidationArena], None]] = None,
    policy_implementations_by_faction: Optional[Mapping[str, PolicyImplementation]] = None,
) -> ExternalSelfPlayResult:
    """Run the subjective self-play loop against a composable arena factory.

    Args:
        arena_id: Stable identifier recorded in the result artifact.
        arena_factory: Zero-argument factory that constructs and starts the
            complete arena, including its requested opening treatment.
        max_commands: Maximum commands to select before stopping.
        random_seed: Optional deterministic seed restored after the run.
        arena_observer: Optional precombat observer invoked on the constructed
            arena after external controllers are installed.

    Returns:
        Typed self-play trace result.
    """
    with latency_sensitive_gc():
        if random_seed is None:
            return _run_external_selfplay(
                arena_id,
                max_commands=max_commands,
                hero_first=True,
                arena_observer=arena_observer,
                arena_factory=arena_factory,
                policy_implementations_by_faction=policy_implementations_by_faction,
            )

        previous_random_state = random.getstate()
        random.seed(random_seed)
        try:
            return _run_external_selfplay(
                arena_id,
                max_commands=max_commands,
                hero_first=True,
                arena_observer=arena_observer,
                arena_factory=arena_factory,
                policy_implementations_by_faction=policy_implementations_by_faction,
            )
        finally:
            random.setstate(previous_random_state)


def _run_external_selfplay(
    arena_id: str,
    *,
    max_commands: int,
    hero_first: bool,
    arena_observer: Optional[Callable[[ValidationArena], None]],
    arena_factory: Optional[Callable[[], ValidationArena]] = None,
    policy_implementations_by_faction: Optional[Mapping[str, PolicyImplementation]] = None,
) -> ExternalSelfPlayResult:
    """Execute one self-play run using the active random generator."""
    started = time.perf_counter()
    reset_standard_arena_runtime()
    opening_faction = "heroes" if hero_first else "monsters"
    arena = (
        arena_factory()
        if arena_factory is not None
        else create_ai_validation_arena(arena_id, opening_faction=opening_faction)
    )
    sim.encounter = arena.encounter
    sim.paused = False
    sim.encounter.clear_combat_log()
    for entity in Entity.get_all_entities():
        if entity.uuid in sim.encounter.combatants:
            sim.encounter.set_controller_for(
                entity.uuid,
                ExternalAIController(source_entity_uuid=entity.uuid),
            )
    if arena_observer is not None:
        arena_observer(arena)

    game = sim.create_game_session(sim.encounter)
    mgr = sim.get_session_manager()
    session_ids_by_faction: dict[str, str] = {}
    for faction in sorted({entity.faction for entity in Entity.get_all_entities() if entity.faction}):
        session = mgr.create_session(PlayerType.AI, f"AI {faction.title()}")
        game.add_player(session)
        session_ids_by_faction[faction] = str(session.session_id)
        for entity in Entity.get_all_entities():
            if entity.faction == faction:
                game.assign_entity(entity.uuid, session.session_id)

    asyncio.run(advance_encounter())
    client = ArenaApiClient()
    traces: list[ExternalSelfPlayTrace] = []
    blocked_row_ids_by_turn: dict[tuple[str, int, int], set[str]] = {}
    blocked_semantic_keys_by_turn: dict[tuple[str, int, int], set[str]] = {}
    blocked_action_categories_by_turn: dict[tuple[str, int, int], set[str]] = {}
    rejected_counts_by_turn: dict[tuple[str, int, int], int] = {}
    policy_hosts_by_session: dict[str, PolicyHost] = {}
    policy_generations_by_faction: dict[str, PolicyGenerationIdentity] = {}
    for faction, session_id in session_ids_by_faction.items():
        implementation = (
            policy_implementations_by_faction.get(faction)
            if policy_implementations_by_faction is not None
            else get_policy_implementation(CANDIDATE_GENERATION_ID)
        )
        if policy_implementations_by_faction is not None and implementation is None:
            raise ValueError(f"No policy implementation assigned to faction {faction!r}.")
        policy_hosts_by_session[session_id] = create_generation_policy_host(
            policy_id=f"external.default.{faction}",
            implementation=implementation,
            memory_store=PolicyMemoryStore(),
        )
        if implementation is not None:
            policy_generations_by_faction[faction] = implementation.identity
    facts_by_session: dict[str, AgentFacts] = {}
    fact_worlds_by_session: dict[str, SubjectiveWorldState] = {}
    stores_by_session: dict[str, SubjectiveStore] = {}
    audit_memories_by_session: dict[str, SubjectivityAuditMemory] = {}
    hp_signatures: list[tuple[tuple[str, int], ...]] = []
    stalemate_evidence: Optional[StalemateEvidence] = None
    status = "command_cap_reached"
    for command_index in range(max_commands):
        if sim.encounter is None or sim.encounter.state != EncounterState.ACTIVE:
            status = "encounter_ended"
            break
        active = sim.encounter.get_current_entity()
        if active is None:
            status = "no_active_actor"
            break
        session_id = _session_for_actor(active.uuid)
        if session_id is None:
            status = "unowned_actor"
            break
        turn_key = (
            str(active.uuid),
            sim.encounter.round_number,
            sim.encounter.current_turn_index,
        )
        trace = _select_and_submit_command(
            client,
            session_id,
            active,
            command_index,
            stores_by_session=stores_by_session,
            policy_host=policy_hosts_by_session[session_id],
            facts_by_session=facts_by_session,
            fact_worlds_by_session=fact_worlds_by_session,
            audit_memory=audit_memories_by_session.setdefault(
                session_id,
                SubjectivityAuditMemory(),
            ),
            blocked_row_ids=blocked_row_ids_by_turn.get(turn_key, set()),
            blocked_semantic_keys=blocked_semantic_keys_by_turn.get(turn_key, set()),
            blocked_action_categories=blocked_action_categories_by_turn.get(turn_key, set()),
        )
        traces.append(trace)
        hp_signatures.append(_combatant_hp_signature())
        if trace.command_status == CommandResultStatus.REJECTED.value:
            rejected_counts_by_turn[turn_key] = rejected_counts_by_turn.get(turn_key, 0) + 1
            if trace.row_id is not None:
                blocked_row_ids_by_turn.setdefault(turn_key, set()).add(trace.row_id)
            if trace.semantic_key is not None and rejected_counts_by_turn[turn_key] >= 2:
                blocked_semantic_keys_by_turn.setdefault(turn_key, set()).add(trace.semantic_key)
            continue
        if trace.command_status == CommandResultStatus.ACCEPTED.value and "control_resisted" in trace.outcome_logical_tags:
            if trace.semantic_key is not None:
                blocked_semantic_keys_by_turn.setdefault(turn_key, set()).add(trace.semantic_key)
        if trace.command_status == CommandResultStatus.STALE.value:
            continue
        if trace.command_status not in {CommandResultStatus.ACCEPTED.value, None}:
            status = f"command_{trace.command_status}"
            break
        if is_stalemate_window(traces, hp_signatures):
            status = "stalemate_draw"
            stalemate_evidence = StalemateEvidence(
                command_window=STALEMATE_COMMAND_WINDOW,
                start_command_index=traces[-STALEMATE_COMMAND_WINDOW].command_index,
                end_command_index=traces[-1].command_index,
                unchanged_hp_by_actor=dict(hp_signatures[-1]),
            )
            break

    if sim.encounter is not None and sim.encounter.state != EncounterState.ACTIVE:
        status = "encounter_ended"

    final_hp = {
        entity.name: entity.get_hp()
        for entity in Entity.get_all_entities()
        if entity.uuid in (sim.encounter.combatants if sim.encounter else {})
    }
    final_factions = {
        entity.name: entity.faction
        for entity in Entity.get_all_entities()
        if entity.uuid in (sim.encounter.combatants if sim.encounter else {}) and entity.faction is not None
    }
    elapsed_ms = (time.perf_counter() - started) * 1000
    result = ExternalSelfPlayResult(
        arena_id=arena_id,
        status=status,
        command_count=len(traces),
        elapsed_ms=round(elapsed_ms, 3),
        session_ids_by_faction=session_ids_by_faction,
        policy_generations_by_faction=policy_generations_by_faction,
        final_round=sim.encounter.round_number if sim.encounter else None,
        final_state=sim.encounter.state.value if sim.encounter else None,
        final_hp_by_actor=final_hp,
        final_faction_by_actor=final_factions,
        stalemate_evidence=stalemate_evidence,
        traces=traces,
    )
    client.close()
    return result


def is_stalemate_window(
    traces: list[ExternalSelfPlayTrace],
    hp_signatures: list[tuple[tuple[str, int], ...]],
    *,
    window: int = STALEMATE_COMMAND_WINDOW,
) -> bool:
    """Return whether accepted commands left the complete HP vector unchanged.

    This is evaluator-side finite-horizon adjudication. The objective HP vector
    is never supplied to either controller or any policy processor.
    """
    if len(traces) != len(hp_signatures):
        raise ValueError("Trace and HP-signature histories must have equal length.")
    if window < 1 or len(traces) < window:
        return False
    for trace in traces[-window:]:
        if trace.command_status != CommandResultStatus.ACCEPTED.value:
            return False
    tail = hp_signatures[-window:]
    return all(signature == tail[0] for signature in tail[1:])


def _combatant_hp_signature() -> tuple[tuple[str, int], ...]:
    """Return an evaluator-only stable HP vector for current combatants."""
    combatants = sim.encounter.combatants if sim.encounter is not None else {}
    return tuple(sorted(
        (entity.name, entity.get_hp())
        for entity in Entity.get_all_entities()
        if entity.uuid in combatants
    ))


def _session_for_actor(actor_uuid: UUID) -> Optional[str]:
    """Return the active game session that controls one actor."""
    if sim.game is None:
        return None
    session_uuid = sim.game.entity_to_player.get(actor_uuid)
    return str(session_uuid) if session_uuid else None


def _refresh_subjectivity_audit_memory(
    session_id: str,
    memory: SubjectivityAuditMemory,
) -> None:
    """Accumulate facts independently authorized for one controller session."""
    if sim.game is None:
        return
    session = sim.game.players.get(UUID(session_id))
    if session is None:
        return
    controlled_uuids = set(session.controlled_entities)
    controlled_strings = {str(entity_uuid) for entity_uuid in controlled_uuids}
    memory.controlled_entity_uuids.update(controlled_strings)
    memory.authorized_entity_uuids.update(controlled_strings)
    for source_index, event in EventQueue.iter_events_since(memory.source_event_cursor):
        memory.source_event_cursor = source_index + 1
        if (
            event.phase == EventPhase.COMPLETION
            and isinstance(event, SensoryUpdateEvent)
            and str(event.observer_uuid) in controlled_strings
        ):
            _apply_sensory_event_audit_grants(event, memory)
    memory.source_event_cursor = EventQueue.event_cursor()
    for entity_uuid in controlled_uuids:
        observer = Entity.get(entity_uuid)
        if observer is None:
            continue
        memory.authorized_positions.add(observer.position)
        memory.authorized_positions.update(observer.senses.seen)
        memory.authorized_entity_uuids.update(str(value) for value in observer.senses.entities)
        memory.authorized_positions.update(observer.senses.entities.values())
        memory.authorized_object_uuids.update(str(value) for value in observer.senses.objects)
        memory.authorized_positions.update(observer.senses.objects.values())
        for item in observer.inventory.items.values():
            memory.authorized_object_uuids.add(str(item.uuid))
        for item in observer.equipment.get_all_equipped_items():
            memory.authorized_object_uuids.add(str(item.uuid))
    if sim.encounter is None:
        return
    for entry in sim.encounter.combat_log:
        _apply_combat_log_audit_grants(entry, controlled_strings, memory)


def _apply_sensory_event_audit_grants(
    event: SensoryUpdateEvent,
    memory: SubjectivityAuditMemory,
) -> None:
    """Accumulate event-time facts independently granted by engine senses."""
    memory.authorized_positions.update(event.visible_cells_added)
    memory.authorized_positions.update(event.visible_cells_removed)
    memory.authorized_positions.update(event.seen_cells_added)
    for entity_uuid, position in (
        *event.visible_entities_added.items(),
        *event.visible_entities_removed.items(),
    ):
        memory.authorized_entity_uuids.add(str(entity_uuid))
        memory.authorized_positions.add(position)
    for entity_uuid, positions in event.visible_entities_moved.items():
        memory.authorized_entity_uuids.add(str(entity_uuid))
        memory.authorized_positions.update(positions)
    for object_uuid, position in (
        *event.visible_objects_added.items(),
        *event.visible_objects_removed.items(),
    ):
        memory.authorized_object_uuids.add(str(object_uuid))
        memory.authorized_positions.add(position)
    for object_uuid, positions in event.visible_objects_moved.items():
        memory.authorized_object_uuids.add(str(object_uuid))
        memory.authorized_positions.update(positions)


def _apply_combat_log_audit_grants(
    entry: CombatLogEntry,
    controlled_uuids: set[str],
    memory: SubjectivityAuditMemory,
) -> None:
    """Apply event-time identity and location grants from one combat-log tree."""
    for entity_uuid, observer_uuids in entry.identified_entity_observer_uuids.items():
        if controlled_uuids.intersection(observer_uuids):
            memory.authorized_entity_uuids.add(entity_uuid)
    for entity_uuid, observer_uuids in entry.located_entity_observer_uuids.items():
        if not controlled_uuids.intersection(observer_uuids):
            continue
        memory.authorized_entity_uuids.add(entity_uuid)
        try:
            entity = Entity.get(UUID(entity_uuid))
        except ValueError:
            entity = None
        if entity is not None:
            memory.authorized_positions.add(entity.position)
    if controlled_uuids.intersection(entry.perceiver_uuids):
        for entity_uuid in entry.revealed_entity_uuids:
            memory.authorized_entity_uuids.add(entity_uuid)
            try:
                entity = Entity.get(UUID(entity_uuid))
            except ValueError:
                entity = None
            if entity is not None:
                memory.authorized_positions.add(entity.position)
    for child in entry.sub_entries:
        _apply_combat_log_audit_grants(child, controlled_uuids, memory)


def _store_for_active_session(
    client: ArenaApiClient,
    session_id: str,
    stores_by_session: dict[str, SubjectiveStore],
    *,
    active_uuid: str,
) -> tuple[SubjectiveStore, SelfPlayStoreTiming]:
    """Return a locally materialized subjective store for the active session."""
    timing = SelfPlayStoreTiming()
    store = stores_by_session.get(session_id)
    if store is None:
        store = SubjectiveStore()
        stores_by_session[session_id] = store
        timing.merge(_load_store_snapshot(client, session_id, store))
    else:
        epoch = store.world.current_epoch if store.world is not None else None
        if epoch is None or epoch.actor_uuid != active_uuid:
            timing.merge(_catch_up_store(client, session_id, store))

    epoch = store.world.current_epoch if store.world is not None else None
    if epoch is None or epoch.actor_uuid != active_uuid:
        timing.merge(_catch_up_store(client, session_id, store))
        epoch = store.world.current_epoch if store.world is not None else None
    if epoch is None or epoch.actor_uuid != active_uuid:
        timing.merge(_load_store_snapshot(client, session_id, store, resynced=True))
    return store, timing


def _load_store_snapshot(
    client: ArenaApiClient,
    session_id: str,
    store: SubjectiveStore,
    *,
    resynced: bool = False,
) -> SelfPlayStoreTiming:
    """Load one subjective snapshot into a local self-play store."""
    timing = SelfPlayStoreTiming(snapshot_loaded=True, resynced=resynced)
    snapshot_started = time.perf_counter()
    snapshot_response = client.get(f"/ai/sessions/{session_id}/observation/snapshot")
    snapshot_response.raise_for_status()
    payload = snapshot_response.json()
    timing.snapshot_ms = _elapsed_ms(snapshot_started)
    materialize_started = time.perf_counter()
    store.load_snapshot(payload)
    timing.materialize_ms = _elapsed_ms(materialize_started)
    return timing


def _catch_up_store(
    client: ArenaApiClient,
    session_id: str,
    store: SubjectiveStore,
    *,
    limit: int = 500,
) -> SelfPlayStoreTiming:
    """Apply persisted subjective frames to a local self-play store."""
    timing = SelfPlayStoreTiming()
    if store.world is None:
        return timing
    while True:
        since = store.world.observation_cursor
        fetch_started = time.perf_counter()
        try:
            payload = iter_observation_frames(
                session_id,
                since=since,
                limit=limit,
                session_manager=sim.get_session_manager(),
            )
            frames = payload.frames
        except ObservationAccessError:
            response = client.get(
                f"/ai/sessions/{session_id}/observation/frames",
                params={"since": since, "limit": limit},
            )
            response.raise_for_status()
            response_payload = response.json()
            frames = response_payload.get("frames", [])
        timing.frame_fetch_ms += _elapsed_ms_float(fetch_started)
        if not isinstance(frames, list) or not frames:
            return timing
        apply_started = time.perf_counter()
        for frame in frames:
            result = store.apply_frame(frame, capture_previous=False)
            if result.kind == ApplyResultKind.GAP:
                timing.frame_apply_ms += _elapsed_ms_float(apply_started)
                timing.merge(_load_store_snapshot(client, session_id, store, resynced=True))
                return timing
            if result.kind == ApplyResultKind.APPLIED:
                timing.frame_count += 1
        timing.frame_apply_ms += _elapsed_ms_float(apply_started)
        if len(frames) < limit:
            return timing


def _select_and_submit_command(
    client: ArenaApiClient,
    session_id: str,
    active: Entity,
    command_index: int,
    *,
    stores_by_session: dict[str, SubjectiveStore],
    policy_host: PolicyHost,
    facts_by_session: dict[str, AgentFacts],
    fact_worlds_by_session: dict[str, SubjectiveWorldState],
    audit_memory: SubjectivityAuditMemory,
    blocked_row_ids: set[str],
    blocked_semantic_keys: set[str],
    blocked_action_categories: set[str],
) -> ExternalSelfPlayTrace:
    """Select and submit one command for the active actor."""
    started = time.perf_counter()
    _refresh_subjectivity_audit_memory(session_id, audit_memory)
    pre_command_sync_started = time.perf_counter()
    store, store_timing = _store_for_active_session(
        client,
        session_id,
        stores_by_session,
        active_uuid=str(active.uuid),
    )
    pre_command_sync_ms = _elapsed_ms(pre_command_sync_started)
    materialized = store.world
    epoch = store.world.current_epoch if store.world is not None else None
    if epoch is None:
        return ExternalSelfPlayTrace(
            command_index=command_index,
            round_number=sim.encounter.round_number if sim.encounter else 0,
            turn_index=sim.encounter.current_turn_index if sim.encounter else 0,
            session_id=session_id,
            policy_generation_id=policy_host.policy_id,
            policy_version=policy_host.policy_version,
            policy_executable_sha256=(
                policy_host.implementation.identity.executable_sha256
                if policy_host.implementation is not None
                else None
            ),
            actor_uuid=str(active.uuid),
            actor_name=active.name,
            actor_faction=active.faction,
            actor_position=active.position,
            actor_hp=active.get_hp(),
            entity_action_count=0,
            position_action_count=0,
            command_type="wait",
            reason="no_epoch",
            snapshot_loaded=store_timing.snapshot_loaded,
            snapshot_ms=store_timing.snapshot_ms,
            materialize_ms=store_timing.materialize_ms,
            frame_fetch_ms=_round_ms(store_timing.frame_fetch_ms),
            frame_apply_ms=_round_ms(store_timing.frame_apply_ms),
            frame_count=store_timing.frame_count,
            pre_command_sync_ms=pre_command_sync_ms,
            pre_command_frame_fetch_ms=_round_ms(store_timing.frame_fetch_ms),
            pre_command_frame_apply_ms=_round_ms(store_timing.frame_apply_ms),
            pre_command_frame_count=store_timing.frame_count,
            audit_controlled_entity_uuids=sorted(audit_memory.controlled_entity_uuids),
            audit_authorized_entity_uuids=sorted(audit_memory.authorized_entity_uuids),
            audit_authorized_object_uuids=sorted(audit_memory.authorized_object_uuids),
            audit_authorized_positions=sorted(audit_memory.authorized_positions),
            total_ms=_elapsed_ms(started),
        )
    if materialized is None:
        raise RuntimeError("Subjective store was loaded without a materialized state.")

    fact_started = time.perf_counter()
    previous_fact_world = fact_worlds_by_session.get(session_id)
    derivation = derive_agent_facts(
        materialized,
        previous_world=previous_fact_world,
        previous_facts=facts_by_session.get(session_id),
    )
    facts_by_session[session_id] = derivation.facts
    fact_worlds_by_session[session_id] = materialized
    fact_ms = _elapsed_ms(fact_started)
    execution_constraints = PolicyExecutionConstraints(
        blocked_row_ids=frozenset(blocked_row_ids),
        blocked_semantic_keys=frozenset(blocked_semantic_keys),
        blocked_action_categories=frozenset(blocked_action_categories),
    )
    policy_context = PolicyContext.model_construct(
        world=materialized,
        facts=derivation.facts,
        execution_constraints=execution_constraints,
        deadline_monotonic=None,
    )
    policy_memory = policy_host.memory_for(session_id, str(active.uuid))
    policy_started = time.perf_counter()
    host_decision = policy_host.decide(
        materialized,
        facts=derivation.facts,
        execution_constraints=execution_constraints,
    )
    host_binding = policy_host.binding_for(
        session_id,
        str(active.uuid),
        epoch.epoch_id,
    )
    policy_diagnostics = policy_host.diagnostics_for(
        session_id,
        str(active.uuid),
        epoch.epoch_id,
    )
    selected_intent = host_decision.selected.intent
    selected_row = (
        derivation.facts.affordances.by_id.get(selected_intent.row_id)
        if isinstance(selected_intent, ExecuteIntent)
        else None
    )
    command = command_from_policy_decision(
        policy_context,
        host_decision,
        host_binding.routine_plan,
    )
    if command is None:
        raise RuntimeError("PolicyHost selected a row absent from its canonical fact index")
    policy_ms = _elapsed_ms(policy_started)
    actor_fact = materialized.known_entities.get(str(active.uuid))
    previous_actor_fact = (
        previous_fact_world.known_entities.get(str(active.uuid))
        if previous_fact_world is not None
        else None
    )
    actor_previous_position = (
        previous_actor_fact.position
        if previous_actor_fact is not None
        and previous_actor_fact.position != (actor_fact.position if actor_fact is not None else None)
        else None
    )
    visible_enemy_names = [
        materialized.known_entities[entity_uuid].name
        for entity_uuid in derivation.facts.contacts.visible_hostile_uuids
    ]
    remembered_enemy_names = [
        materialized.known_entities[entity_uuid].name
        for entity_uuid in derivation.facts.contacts.remembered_hostile_uuids
    ]
    unresolved_hostile_names: list[str] = []
    entity_actions = tuple(epoch.affordances.entity_actions)
    position_actions = tuple(epoch.affordances.position_actions)
    self_action_summaries = [
        SelfPlayActionSummary(
            template_name=row.template_name,
            can_afford=row.can_afford,
            target_count=len(row.targets),
        )
        for row in epoch.affordances.self_actions
    ]
    epoch_rows = epoch.affordances.all_rows
    epoch_targets = [
        target
        for row in epoch_rows
        for target in [*row.targets, *row.target_options]
    ]
    deep_diagnostics_enabled = command_index % DEEP_DIAGNOSTIC_SAMPLE_INTERVAL == 0
    spacing_evidence = host_decision.selected.evidence.spacing
    trace = ExternalSelfPlayTrace(
        command_index=command_index,
        round_number=sim.encounter.round_number if sim.encounter else 0,
        turn_index=sim.encounter.current_turn_index if sim.encounter else 0,
        session_id=session_id,
        policy_generation_id=policy_host.policy_id,
        policy_version=policy_host.policy_version,
        policy_executable_sha256=(
            policy_host.implementation.identity.executable_sha256
            if policy_host.implementation is not None
            else None
        ),
        actor_uuid=str(active.uuid),
        actor_name=active.name,
        actor_faction=active.faction,
        actor_position=actor_fact.position if actor_fact else None,
        actor_previous_position=actor_previous_position,
        actor_hp=actor_fact.hp if actor_fact else None,
        actor_conditions=list(actor_fact.conditions) if actor_fact else [],
        actor_economy=epoch.economy,
        visible_enemy_names=visible_enemy_names,
        remembered_enemy_names=remembered_enemy_names,
        suppressed_remembered_enemy_names=[],
        policy_memory=policy_memory_trace(policy_memory),
        routine_revalidation=host_binding.revalidation.model_dump(mode="json"),
        policy_trace=list(host_decision.trace),
        capability_target_projection=(
            spacing_evidence.capability_target_projection
            if spacing_evidence is not None
            else None
        ),
        fact_invalidated_sections=list(derivation.invalidated_sections),
        fact_timing={metric.section: metric.elapsed_ms for metric in derivation.metrics},
        unresolved_hostile_names=unresolved_hostile_names,
        entity_action_count=len(entity_actions),
        position_action_count=len(position_actions),
        self_actions=self_action_summaries,
        command_type=command.command_type.value,
        row_id=command.row_id,
        template_name=command.template_name,
        semantic_key=selected_row.semantic_key if selected_row is not None else None,
        action_category=selected_row.action_category if selected_row is not None else None,
        available_action_semantic_keys=sorted({row.semantic_key for row in epoch_rows}),
        affordable_action_semantic_keys=sorted({
            row.semantic_key for row in epoch_rows if row.can_afford
        }),
        available_item_action_semantic_keys=sorted({
            row.semantic_key for row in epoch_rows if row.source.is_item_use
        }),
        target_uuid=command.target_uuid,
        target_name=command.target_name,
        target_position=command.target_position,
        target_distance=command.target_distance,
        target_path_cost=command.target_path_cost,
        target_safe_path_cost=command.target_safe_path_cost,
        target_path_hazardous=command.target_path_hazardous,
        target_path=command.target_path,
        target_safe_path=command.target_safe_path,
        affected_entity_uuids=command.affected_entity_uuids,
        affected_entity_names=command.affected_entity_names,
        affected_entity_positions=command.affected_entity_positions,
        affected_enemy_count=command.affected_enemy_count,
        affected_controlled_count=command.affected_controlled_count,
        reference_entity_uuid=command.reference_entity_uuid,
        reference_entity_name=command.reference_entity_name,
        reference_entity_position=command.reference_entity_position,
        reference_entity_distance_cells=command.reference_entity_distance_cells,
        spacing_floor_cells=command.spacing_floor_cells,
        spacing_anchor_position=command.spacing_anchor_position,
        nearest_controlled_ally_distance_cells=command.nearest_controlled_ally_distance_cells,
        ally_spacing_floor_cells=command.ally_spacing_floor_cells,
        extra_target_uuids=command.extra_target_uuids,
        extra_target_names=command.extra_target_names,
        extra_target_positions=command.extra_target_positions,
        reason=command.reason,
        logical_tags=[tag.value for tag in command.logical_tags],
        routine_id=command.routine_id,
        routine_step_id=command.routine_step_id,
        routine_next_step_id=command.routine_next_step_id,
        routine_target_uuid=command.routine_target_uuid,
        routine_target_position=command.routine_target_position,
        routine_started_epoch_index=command.routine_started_epoch_index,
        deep_diagnostics_enabled=deep_diagnostics_enabled,
        snapshot_loaded=store_timing.snapshot_loaded,
        snapshot_ms=store_timing.snapshot_ms,
        materialize_ms=store_timing.materialize_ms,
        frame_fetch_ms=_round_ms(store_timing.frame_fetch_ms),
        frame_apply_ms=_round_ms(store_timing.frame_apply_ms),
        frame_count=store_timing.frame_count,
        pre_command_sync_ms=pre_command_sync_ms,
        pre_command_frame_fetch_ms=_round_ms(store_timing.frame_fetch_ms),
        pre_command_frame_apply_ms=_round_ms(store_timing.frame_apply_ms),
        pre_command_frame_count=store_timing.frame_count,
        affordance_timing={},
        policy_diagnostics=policy_diagnostics.model_dump(mode="json"),
        reduction_timing={},
        reduce_ms=0.0,
        fact_ms=fact_ms,
        policy_ms=policy_ms,
        local_decision_ms=_round_ms(fact_ms + policy_ms),
        subjective_known_entity_uuids=sorted(materialized.known_entities),
        subjective_known_entity_positions=sorted({
            entity.position
            for entity in materialized.known_entities.values()
            if entity.position is not None
        }),
        subjective_known_object_uuids=sorted(materialized.known_objects),
        subjective_known_object_positions=sorted({
            obj.position
            for obj in materialized.known_objects.values()
            if obj.position is not None
        }),
        subjective_known_tile_positions=sorted({tile.position for tile in materialized.known_tiles.values()}),
        subjective_visible_cell_positions=sorted({
            position
            for observer in materialized.observers.values()
            for position in observer.visible_cells
        }),
        subjective_seen_cell_positions=sorted({
            position
            for observer in materialized.observers.values()
            for position in observer.seen_cells
        }),
        subjective_affordance_row_ids=sorted(row.row_id for row in epoch_rows),
        subjective_affordance_target_uuids=sorted({
            target.target_uuid
            for target in epoch_targets
            if target.target_uuid is not None
        }),
        subjective_affordance_target_positions=sorted({
            target.position
            for target in epoch_targets
            if target.position is not None
        }),
        audit_controlled_entity_uuids=sorted(audit_memory.controlled_entity_uuids),
        audit_authorized_entity_uuids=sorted(audit_memory.authorized_entity_uuids),
        audit_authorized_object_uuids=sorted(audit_memory.authorized_object_uuids),
        audit_authorized_positions=sorted(audit_memory.authorized_positions),
    )
    submit_started = time.perf_counter()
    command_id: str
    if command.command_type.value == "execute" and command.row_id:
        request = AgentExecuteCommandRequest(
            actor_uuid=str(active.uuid),
            basis_epoch_id=epoch.epoch_id,
            row_id=command.row_id,
            extra_target_uuids=command.extra_target_uuids,
            prefer_safe=command.prefer_safe,
            include_diagnostics=deep_diagnostics_enabled,
        )
        command_id = request.command_id
        command_endpoint = f"/ai/sessions/{session_id}/commands/execute"
    else:
        request = AgentEndTurnCommandRequest(
            actor_uuid=str(active.uuid),
            basis_epoch_id=epoch.epoch_id,
            include_diagnostics=deep_diagnostics_enabled,
        )
        command_id = request.command_id
        command_endpoint = f"/ai/sessions/{session_id}/commands/end-turn"
    policy_host.prepare_submission(
        session_id=session_id,
        actor_uuid=str(active.uuid),
        epoch_id=epoch.epoch_id,
        command_id=command_id,
    )
    result_response = client.post(
        command_endpoint,
        json=request.model_dump(mode="json"),
    )
    result_response.raise_for_status()
    command_http_ms = _elapsed_ms(submit_started)
    result_payload = result_response.json()
    policy_host.record_result(CommandResult.model_validate(result_payload))
    followup_sync_started = time.perf_counter()
    followup_timing = _catch_up_store(client, session_id, store)
    command_followup_sync_ms = _elapsed_ms(followup_sync_started)
    store_timing.merge(followup_timing)
    outcome_tags = _outcome_logical_tags(result_payload, trace.logical_tags)
    server_timing = _server_timing_from_result_payload(result_payload)
    action_server_timing = _action_server_timing_from_streamed_result(
        store.get_command_result(request.command_id)
    )
    return trace.model_copy(
        update={
            "command_status": result_payload.get("status"),
            "action_resolution": result_payload.get("action_resolution"),
            "outcome_code": result_payload.get("outcome_code"),
            "command_message": result_payload.get("message"),
            "command_result_payload": result_payload,
            "outcome_logical_tags": outcome_tags,
            "snapshot_loaded": store_timing.snapshot_loaded,
            "snapshot_ms": store_timing.snapshot_ms,
            "materialize_ms": store_timing.materialize_ms,
            "frame_fetch_ms": _round_ms(store_timing.frame_fetch_ms),
            "frame_apply_ms": _round_ms(store_timing.frame_apply_ms),
            "frame_count": store_timing.frame_count,
            "followup_frame_fetch_ms": _round_ms(followup_timing.frame_fetch_ms),
            "followup_frame_apply_ms": _round_ms(followup_timing.frame_apply_ms),
            "followup_frame_count": followup_timing.frame_count,
            "server_timing": server_timing,
            "action_server_timing": action_server_timing,
            "command_http_ms": command_http_ms,
            "command_followup_sync_ms": command_followup_sync_ms,
            "command_submit_ms": _elapsed_ms(submit_started),
            "total_ms": _elapsed_ms(started),
        }
    )


def _outcome_logical_tags(
    result: dict[str, object],
    command_logical_tags: list[str],
) -> list[str]:
    """Return outcome tags inferred from a command-result payload."""
    if _is_counterspell_interruption(result):
        return ["spell_interruption"]
    if "control_effect" in command_logical_tags:
        if _control_effect_was_resisted(result):
            return ["control_resisted"]
        if result.get("status") == CommandResultStatus.ACCEPTED.value:
            return ["control_landed"]
    return []


def _is_counterspell_interruption(result: dict[str, object]) -> bool:
    """Return whether a command result carries the Counterspell outcome identity."""
    return result.get("outcome_code") == COUNTERSPELL_INTERRUPTION_OUTCOME_CODE


def _control_effect_was_resisted(result: dict[str, object]) -> bool:
    """Return whether a control command result reports a successful save or resist."""
    text = _result_message_text(result)
    return "target saved" in text or "resisted" in text or "resists" in text


def _result_message_text(result: dict[str, object]) -> str:
    """Return lower-case message text from a command-result payload."""
    message_parts = [str(result.get("message") or "")]
    payload = result.get("payload")
    if isinstance(payload, dict):
        for key in ("engine_message", "message"):
            value = payload.get(key)
            if value:
                message_parts.append(str(value))
        action_result = payload.get("action_result")
        if isinstance(action_result, dict):
            value = action_result.get("message")
            if value:
                message_parts.append(str(value))
    return " ".join(message_parts).lower()


def _server_timing_from_result_payload(result: dict[str, object]) -> dict[str, object]:
    """Return server timing data from a compact command-result payload."""
    payload = result.get("payload")
    if not isinstance(payload, dict):
        return {}
    timing = payload.get("server_timing")
    return timing if isinstance(timing, dict) else {}


def _action_server_timing_from_streamed_result(
    result: Optional[CommandResult],
) -> dict[str, object]:
    """Return nested engine timing from an authoritative streamed result."""
    if result is None:
        return {}
    timing = result.payload.get("action_server_timing")
    if isinstance(timing, dict):
        return timing
    action_result = result.payload.get("action_result")
    if not isinstance(action_result, dict):
        return {}
    nested_timing = action_result.get("action_server_timing")
    return nested_timing if isinstance(nested_timing, dict) else {}


def _elapsed_ms(started: float) -> float:
    """Return elapsed wall-clock milliseconds rounded for trace output."""
    return _round_ms(_elapsed_ms_float(started))


def _elapsed_ms_float(started: float) -> float:
    """Return elapsed wall-clock milliseconds without rounding."""
    return (time.perf_counter() - started) * 1000


def _round_ms(value: float) -> float:
    """Round milliseconds for compact trace output."""
    return round(value, 3)


def _merge_optional_ms(
    current: Optional[float],
    incoming: Optional[float],
) -> Optional[float]:
    """Merge optional timing values by addition."""
    if incoming is None:
        return current
    if current is None:
        return incoming
    return _round_ms(current + incoming)
