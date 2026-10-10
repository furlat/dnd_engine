"""Transport-free owner of typed policy decisions and command correlation."""

from __future__ import annotations

from enum import Enum
from hashlib import sha256
import logging
import time
from typing import Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ai.knowledge.deriver import derive_agent_facts
from ai.knowledge.topology import grid_distance_feet
from ai.policy.candidates import PolicyCandidateSet, build_policy_candidate_set
from ai.knowledge.models import AgentFacts
from dnd.ai.contracts.observation import SubjectiveWorldState
from ai.policy.contracts import (
    NodeStatus,
    PolicyContext,
    PolicyDecision,
    PolicyDecisionCorrelation,
    PolicyDecisionTelemetry,
    PolicyExecutionConstraints,
    PolicyProposal,
    PolicyTraceStep,
)
from ai.policy.default import evaluate_default_policy
from ai.policy.definitions import PolicyImplementation
from ai.policy.economy import (
    AffordabilityWorkspace,
    action_shape_matches_selector,
    positive_cost_resource_ids,
)
from ai.policy.memory import (
    ActorPolicyMemory,
    MaintainMinimumDistanceIntention,
    PolicyMemoryStore,
    execution_constraints_with_memory,
    policy_control_memory_view,
    reconcile_policy_memory,
    reconcile_turn_action_failures,
    record_canceled_action,
    record_remembered_investigation,
    revalidate_same_turn_spacing_intention,
)
from ai.policy.routines import (
    RoutinePlan,
    RoutinePlanningDiagnostics,
    RoutinePlanningInstrumentation,
    RoutinePlanStatus,
    RoutineRevalidation,
    apply_routine_plan_result,
    apply_routine_revalidation,
    plan_registered_routines,
    revalidate_active_routine,
    routine_trace_name,
)
from ai.policy.source import POLICY_NAME, POLICY_VERSION
from dnd.ai.contracts.control import (
    ActionResolutionStatus,
    CommandResult,
    CommandResultStatus,
    END_TURN_ROW_ID,
)
from dnd.ai.contracts.decision import (
    EndTurnIntent,
    ExecuteIntent,
    PolicyIntent,
)
from dnd.ai.contracts.semantics import ActionTag, TargetAllocation


EpochKey = tuple[str, str, str]
EvaluationKey = tuple[str, str, str, tuple[str, ...]]
logger = logging.getLogger(__name__)


class PolicyHostError(ValueError):
    """Base error for an invalid local policy-host operation."""


class PolicyContextAlignmentError(PolicyHostError):
    """Raised when subjective world, facts, authority, and epoch disagree."""


class PolicyDecisionUnavailableError(PolicyHostError):
    """Raised when the shared policy hierarchy has no legal proposal."""


class UnknownPolicyDecisionError(PolicyHostError):
    """Raised when submission references an epoch the host has not decided."""


class DuplicateEpochSubmissionError(PolicyHostError):
    """Raised when a second command is prepared for one actor epoch."""


class DuplicateCommandIdError(PolicyHostError):
    """Raised when a command id has already been used by this host."""


class HostModel(BaseModel):
    """Immutable base for inspectable policy-host lifecycle records."""

    model_config = ConfigDict(frozen=True)


class PolicyTelemetrySink(Protocol):
    """Transport-neutral destination for canonical policy telemetry."""

    def emit_policy_decision(self, event: PolicyDecisionTelemetry) -> None:
        """Retain one freshly bound policy decision."""
        ...


class SubmittedActionShape(HostModel):
    """Minimal semantic shape of the executable row reserved for submission."""

    action_category: str = Field(description="Structured action category.")
    semantic_key: str = Field(description="Stable engine action semantic identity.")
    target_allocation: TargetAllocation = Field(description="Typed target-allocation shape.")
    semantic_tags: frozenset[ActionTag] = Field(description="Typed semantic capabilities.")
    weapon_slot: Optional[str] = Field(
        default=None,
        description="Configured weapon slot when the selected action uses one.",
    )
    positive_cost_resource_ids: frozenset[str] = Field(
        description="Stable identifiers for every positive row cost.",
    )


class PolicyDecisionBinding(HostModel):
    """One policy decision bound to its subjective authority revision."""

    policy_id: str = Field(description="Policy definition that owns this decision.")
    session_id: str = Field(description="Subjective session that produced the decision.")
    actor_uuid: str = Field(description="Controlled actor authorized by the epoch.")
    epoch_id: str = Field(description="Decision epoch authorizing the selected intent.")
    observation_cursor: int = Field(description="Subjective cursor used for policy evaluation.")
    decision_id: str = Field(description="Stable identity shared with policy telemetry.")
    decision: PolicyDecision = Field(description="Shared typed decision exposed to every consumer.")
    routine_plan: Optional[RoutinePlan] = Field(
        default=None,
        description="Typed routine plan retained when the selected proposal belongs to one.",
    )
    revalidation: RoutineRevalidation = Field(description="Routine-memory reconciliation applied before planning.")
    selected_action_shape: Optional[SubmittedActionShape] = Field(
        default=None,
        description="Structural action shape used for accepted transformation-consumption checks.",
    )
    spacing_intention_on_accept: Optional[MaintainMinimumDistanceIntention] = Field(
        default=None,
        description="Same-turn spatial intent staged until authoritative acceptance.",
    )


class PolicyStageTiming(HostModel):
    """Wall and current-thread CPU time for one host decision stage."""

    wall_ms: float = Field(ge=0, description="Elapsed wall time for the stage.")
    thread_cpu_ms: float = Field(ge=0, description="Current-thread CPU time for the stage.")


class PolicyHostStageDiagnostics(HostModel):
    """Typed non-overlapping stages for one freshly evaluated decision."""

    context: PolicyStageTiming
    candidates: PolicyStageTiming
    routine_revalidation: PolicyStageTiming
    routine_planning: PolicyStageTiming
    tree: PolicyStageTiming
    binding_and_telemetry: PolicyStageTiming


class PolicyDecisionDiagnostics(HostModel):
    """Observational timing and bounded-work evidence for one decision."""

    wall_total_ms: float = Field(ge=0, description="Total host wall time.")
    thread_cpu_total_ms: float = Field(ge=0, description="Total host current-thread CPU time.")
    stages: PolicyHostStageDiagnostics
    routine: RoutinePlanningDiagnostics


class PreparedPolicySubmission(HostModel):
    """Transport-neutral intent reserved as the sole command for one epoch."""

    command_id: str = Field(description="Command correlation id chosen by the caller.")
    policy_id: str = Field(description="Policy definition that owns the command.")
    session_id: str = Field(description="Session authorized to submit the command.")
    actor_uuid: str = Field(description="Actor authorized to execute the intent.")
    epoch_id: str = Field(description="Decision epoch authorizing the intent.")
    observation_cursor: int = Field(description="Subjective cursor where the decision was made.")
    intent: PolicyIntent = Field(description="Typed transport-neutral command intent.")
    decision: PolicyDecision = Field(description="Decision and trace shared by all controller adapters.")
    routine_plan: Optional[RoutinePlan] = Field(
        default=None,
        description="Acceptance-gated routine plan when the command belongs to one.",
    )
    selected_action_shape: Optional[SubmittedActionShape] = Field(
        default=None,
        description="Structural action shape retained only until command correlation.",
    )
    spacing_intention_on_accept: Optional[MaintainMinimumDistanceIntention] = Field(
        default=None,
        description="Same-turn spatial intent committed only by an accepted result.",
    )


class PolicyResultDisposition(str, Enum):
    """How one authoritative command result affected policy-host state."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    STALE = "stale"
    ERROR = "error"
    UNMATCHED = "unmatched"
    ALREADY_RECORDED = "already_recorded"


class PolicyResultRecord(HostModel):
    """Inspectible outcome of correlating one server command result."""

    command_id: Optional[str] = Field(default=None, description="Result command id, when supplied.")
    disposition: PolicyResultDisposition = Field(description="Correlation and terminal-result outcome.")
    memory_advanced: bool = Field(
        description="Whether the correlated result advanced gameplay intention or routine memory."
    )
    reason: str = Field(description="Stable explanation of the correlation outcome.")
    result: CommandResult = Field(description="Authoritative result observed by the host.")
    submission: Optional[PreparedPolicySubmission] = Field(
        default=None,
        description="Matched prepared submission, when one exists.",
    )


class PolicyHost:
    """Own one typed policy's decisions, writer ledger, and routine memory.

    The host performs no HTTP or engine mutation. Controller adapters ask it for
    a decision, reserve that decision under a command id, submit the typed intent
    through their own transport, and return the authoritative ``CommandResult``.
    """

    def __init__(
        self,
        *,
        policy_id: str = POLICY_NAME,
        policy_version: str = POLICY_VERSION,
        implementation: Optional[PolicyImplementation] = None,
        controller_mode: str = "shared",
        memory_store: Optional[PolicyMemoryStore] = None,
        telemetry_sink: Optional[PolicyTelemetrySink] = None,
    ) -> None:
        """Create an empty host for one shared policy definition.

        Args:
            policy_id: Stable policy identity used to isolate actor memory.
            policy_version: Version of the policy definition and scoring contract.
            controller_mode: Controller adapter consuming this host.
            memory_store: Optional actor-scoped store shared with another host.
            telemetry_sink: Optional destination for one event per fresh binding.
        """
        self.implementation = implementation
        self.policy_id = implementation.identity.generation_id if implementation is not None else policy_id
        self.policy_version = implementation.identity.policy_version if implementation is not None else policy_version
        self.controller_mode = controller_mode
        self.memory_store = memory_store or PolicyMemoryStore()
        self.telemetry_sink = telemetry_sink
        self._bindings: dict[EvaluationKey, PolicyDecisionBinding] = {}
        self._latest_binding_by_epoch: dict[EpochKey, PolicyDecisionBinding] = {}
        self._diagnostics: dict[EvaluationKey, PolicyDecisionDiagnostics] = {}
        self._latest_diagnostics_by_epoch: dict[EpochKey, PolicyDecisionDiagnostics] = {}
        self._submitted_epochs: dict[EpochKey, str] = {}
        self._pending_by_command_id: dict[str, PreparedPolicySubmission] = {}
        self._recorded_by_command_id: dict[str, PolicyResultRecord] = {}

    def build_context(
        self,
        world: SubjectiveWorldState,
        *,
        facts: Optional[AgentFacts] = None,
        execution_constraints: Optional[PolicyExecutionConstraints] = None,
        deadline_monotonic: Optional[float] = None,
    ) -> PolicyContext:
        """Build and strictly validate one shared subjective policy context.

        Args:
            world: Canonical materialized session-subjective world.
            facts: Facts already derived from exactly this world revision. When
                omitted, the host derives them locally.
            execution_constraints: Turn-local exclusions learned from prior
                authoritative command results.
            deadline_monotonic: Optional local decision deadline.

        Returns:
            An aligned policy context suitable for deterministic or LLM use.

        Raises:
            PolicyContextAlignmentError: If authority or revision fields differ.
        """
        derived_facts = facts if facts is not None else derive_agent_facts(world).facts
        context = PolicyContext(
            world=world,
            facts=derived_facts,
            execution_constraints=execution_constraints or PolicyExecutionConstraints(),
            deadline_monotonic=deadline_monotonic,
        )
        try:
            context.validate_alignment()
        except ValueError as exc:
            raise PolicyContextAlignmentError(str(exc)) from exc
        self._validate_actor_alignment(context)
        epoch = context.world.current_epoch
        assert epoch is not None
        memory = self.memory_for(context.world.session.session_id, epoch.actor_uuid)
        reconcile_policy_memory(context, memory)
        reconcile_turn_action_failures(context, memory)
        return context.model_copy(update={
            "execution_constraints": execution_constraints_with_memory(
                context.execution_constraints,
                memory,
            ),
            "control_memory": policy_control_memory_view(memory),
        })

    def decide(
        self,
        world: SubjectiveWorldState,
        *,
        facts: Optional[AgentFacts] = None,
        execution_constraints: Optional[PolicyExecutionConstraints] = None,
        deadline_monotonic: Optional[float] = None,
        telemetry_sink: Optional[PolicyTelemetrySink] = None,
    ) -> PolicyDecision:
        """Revalidate routines and evaluate the shared hierarchical policy.

        Repeated readers of the same session-actor-epoch receive the exact same
        immutable decision object. This is the shared view used by traditional
        and LLM controller adapters.

        Args:
            world: Canonical materialized session-subjective world.
            facts: Optional facts derived from exactly this world revision.
            execution_constraints: Turn-local row, semantic-family, or category
                exclusions applied before utility ranking.
            deadline_monotonic: Optional local decision deadline.
            telemetry_sink: Optional per-call destination for a fresh binding.

        Returns:
            The immutable decision bound to the current actor epoch.
        """
        total_started = _timing_started()
        context_started = _timing_started()
        context = self.build_context(
            world,
            facts=facts,
            execution_constraints=execution_constraints,
            deadline_monotonic=deadline_monotonic,
        )
        context_timing = _finish_timing(context_started)
        key = self._key_from_context(context)
        evaluation_key = (*key, context.execution_constraints.replay_key)
        existing = self._bindings.get(evaluation_key)
        if existing is not None:
            self._latest_binding_by_epoch[key] = existing
            existing_diagnostics = self._diagnostics.get(evaluation_key)
            if existing_diagnostics is not None:
                self._latest_diagnostics_by_epoch[key] = existing_diagnostics
            return existing.decision

        candidates_started = _timing_started()
        actor_uuid = key[1]
        memory = self.memory_for(key[0], actor_uuid)
        spacing_intention = revalidate_same_turn_spacing_intention(context, memory)
        prior_progress = memory.active_routine
        candidate_builder = (
            self.implementation.build_candidates
            if self.implementation is not None
            else build_policy_candidate_set
        )
        candidates = _filter_candidate_set(
            context,
            candidate_builder(context),
            spacing_intention,
        )
        candidates_timing = _finish_timing(candidates_started)

        revalidation_started = _timing_started()
        revalidation = revalidate_active_routine(
            context,
            prior_progress,
            candidates,
        )
        apply_routine_revalidation(memory, revalidation)
        revalidation_timing = _finish_timing(revalidation_started)

        planning_started = _timing_started()
        epoch = context.world.current_epoch
        assert epoch is not None
        routine_instrumentation = RoutinePlanningInstrumentation(
            AffordabilityWorkspace(epoch.economy)
        )
        routine_planner = (
            self.implementation.plan_routines
            if self.implementation is not None
            else plan_registered_routines
        )
        plans = routine_planner(
            context,
            prior_progress,
            revalidation,
            candidates,
            routine_instrumentation,
        )
        plans = tuple(
            _constrain_routine_plan(context, plan, spacing_intention)
            for plan in plans
        )
        planning_timing = _finish_timing(planning_started)

        tree_started = _timing_started()
        evaluator = (
            self.implementation.evaluate
            if self.implementation is not None
            else evaluate_default_policy
        )
        evaluation = evaluator(context, plans, candidates)
        if evaluation.decision is None:
            raise PolicyDecisionUnavailableError(
                f"{self.policy_id} produced no proposal: {evaluation.unavailable_reason}"
            )
        decision = evaluation.decision.model_copy(
            update={
                "trace": (
                    PolicyTraceStep(
                        node_path="PolicyHost/ExecutionConstraints",
                        status=NodeStatus.SUCCESS,
                        detail=(
                            "none"
                            if not context.execution_constraints.replay_key
                            else "applied:" + ",".join(context.execution_constraints.replay_key)
                        ),
                    ),
                    PolicyTraceStep(
                        node_path=(
                            "PolicyHost/RoutineMemory/"
                            f"{routine_trace_name(revalidation.routine_id)}/Revalidate"
                        ),
                        status=NodeStatus.SUCCESS,
                        detail=f"{revalidation.status.value}:{revalidation.reason}",
                    ),
                    *evaluation.decision.trace,
                )
            }
        )
        tree_timing = _finish_timing(tree_started)

        binding_started = _timing_started()
        decision_id = _policy_decision_id(
            self.policy_id,
            key[0],
            actor_uuid,
            key[2],
            world.observation_cursor,
            context.execution_constraints.replay_key,
        )
        binding = PolicyDecisionBinding(
            policy_id=self.policy_id,
            session_id=key[0],
            actor_uuid=actor_uuid,
            epoch_id=key[2],
            observation_cursor=world.observation_cursor,
            decision_id=decision_id,
            decision=decision,
            routine_plan=evaluation.selected_routine_plan,
            revalidation=revalidation,
            selected_action_shape=_submitted_action_shape(context, decision.selected),
            spacing_intention_on_accept=_spacing_intention_on_accept(
                context,
                decision.selected,
            ),
        )
        self._bindings[evaluation_key] = binding
        self._latest_binding_by_epoch[key] = binding
        self._emit_decision(binding, telemetry_sink or self.telemetry_sink)
        binding_timing = _finish_timing(binding_started)
        total_timing = _finish_timing(total_started)
        diagnostics = PolicyDecisionDiagnostics(
            wall_total_ms=total_timing.wall_ms,
            thread_cpu_total_ms=total_timing.thread_cpu_ms,
            stages=PolicyHostStageDiagnostics(
                context=context_timing,
                candidates=candidates_timing,
                routine_revalidation=revalidation_timing,
                routine_planning=planning_timing,
                tree=tree_timing,
                binding_and_telemetry=binding_timing,
            ),
            routine=routine_instrumentation.snapshot(),
        )
        self._diagnostics[evaluation_key] = diagnostics
        self._latest_diagnostics_by_epoch[key] = diagnostics
        return decision

    def _emit_decision(
        self,
        binding: PolicyDecisionBinding,
        sink: Optional[PolicyTelemetrySink],
    ) -> None:
        """Emit one canonical event without making telemetry policy-authoritative."""
        if sink is None:
            return
        correlation = PolicyDecisionCorrelation(
            session_id=binding.session_id,
            actor_uuid=binding.actor_uuid,
            epoch_id=binding.epoch_id,
            observation_cursor=binding.observation_cursor,
            decision_id=binding.decision_id,
        )
        event = PolicyDecisionTelemetry.model_construct(
            schema_version=2,
            event_id=f"policy-decision:{binding.decision_id}",
            decision_id=binding.decision_id,
            policy_id=binding.policy_id,
            policy_version=self.policy_version,
            controller_mode=self.controller_mode,
            correlation=correlation,
            decision=binding.decision,
        )
        try:
            sink.emit_policy_decision(event)
        except Exception:
            logger.exception("policy decision telemetry emission failed")

    def decision_for(
        self,
        session_id: str,
        actor_uuid: str,
        epoch_id: str,
    ) -> PolicyDecision:
        """Return the immutable shared decision bound to an evaluated epoch."""
        return self.binding_for(session_id, actor_uuid, epoch_id).decision

    def binding_for(
        self,
        session_id: str,
        actor_uuid: str,
        epoch_id: str,
    ) -> PolicyDecisionBinding:
        """Return the complete inspectable binding for an evaluated epoch."""
        key = (session_id, actor_uuid, epoch_id)
        binding = self._latest_binding_by_epoch.get(key)
        if binding is None:
            raise UnknownPolicyDecisionError(
                f"No policy decision for session={session_id}, actor={actor_uuid}, epoch={epoch_id}"
            )
        return binding

    def diagnostics_for(
        self,
        session_id: str,
        actor_uuid: str,
        epoch_id: str,
    ) -> PolicyDecisionDiagnostics:
        """Return observational timing and work evidence for a fresh decision."""
        key = (session_id, actor_uuid, epoch_id)
        diagnostics = self._latest_diagnostics_by_epoch.get(key)
        if diagnostics is None:
            raise UnknownPolicyDecisionError(
                f"No policy diagnostics for session={session_id}, actor={actor_uuid}, epoch={epoch_id}"
            )
        return diagnostics

    def prepare_submission(
        self,
        *,
        session_id: str,
        actor_uuid: str,
        epoch_id: str,
        command_id: str,
    ) -> PreparedPolicySubmission:
        """Reserve the selected typed intent as the sole command for one epoch.

        Args:
            session_id: Session from the evaluated subjective context.
            actor_uuid: Actor authorized by the decision epoch.
            epoch_id: Epoch authorizing the selected intent.
            command_id: Unique id later echoed by ``CommandResult``.

        Returns:
            A transport-neutral prepared submission.

        Raises:
            DuplicateEpochSubmissionError: If this epoch already has a writer.
            DuplicateCommandIdError: If the command id was used previously.
            UnknownPolicyDecisionError: If the epoch was not evaluated.
        """
        key = (session_id, actor_uuid, epoch_id)
        binding = self.binding_for(*key)
        existing_command_id = self._submitted_epochs.get(key)
        if existing_command_id is not None:
            raise DuplicateEpochSubmissionError(
                f"Epoch {epoch_id} already has command {existing_command_id}"
            )
        if command_id in self._pending_by_command_id or command_id in self._recorded_by_command_id:
            raise DuplicateCommandIdError(f"Command id {command_id} has already been used")
        intent = binding.decision.selected.intent
        prepared = PreparedPolicySubmission(
            command_id=command_id,
            policy_id=self.policy_id,
            session_id=session_id,
            actor_uuid=actor_uuid,
            epoch_id=epoch_id,
            observation_cursor=binding.observation_cursor,
            intent=intent,
            decision=binding.decision,
            routine_plan=binding.routine_plan,
            selected_action_shape=binding.selected_action_shape,
            spacing_intention_on_accept=binding.spacing_intention_on_accept,
        )
        self._submitted_epochs[key] = command_id
        self._pending_by_command_id[command_id] = prepared
        return prepared

    def pending_submission(self, command_id: str) -> Optional[PreparedPolicySubmission]:
        """Return the retained plan and intent awaiting a matching result."""
        return self._pending_by_command_id.get(command_id)

    def record_result(self, result: CommandResult) -> PolicyResultRecord:
        """Correlate an authoritative result and conditionally advance memory.

        Mismatched results leave the pending submission intact. Matching terminal
        results consume it, while only explicit intent completion commits retained
        routine and spacing plans.
        """
        command_id = result.command_id
        if command_id is not None and command_id in self._recorded_by_command_id:
            prior = self._recorded_by_command_id[command_id]
            return PolicyResultRecord(
                command_id=command_id,
                disposition=PolicyResultDisposition.ALREADY_RECORDED,
                memory_advanced=False,
                reason="command_result_already_recorded",
                result=result,
                submission=prior.submission,
            )
        submission = self._pending_by_command_id.get(command_id or "")
        mismatch_reason = self._result_mismatch_reason(submission, result)
        if mismatch_reason is not None:
            return PolicyResultRecord(
                command_id=command_id,
                disposition=PolicyResultDisposition.UNMATCHED,
                memory_advanced=False,
                reason=mismatch_reason,
                result=result,
                submission=submission,
            )

        assert submission is not None
        assert command_id is not None
        self._pending_by_command_id.pop(command_id, None)
        accepted = result.status is CommandResultStatus.ACCEPTED
        intent_completed = _submission_completed(submission, result)
        if not accepted:
            self._submitted_epochs.pop(
                (submission.session_id, submission.actor_uuid, submission.epoch_id),
                None,
            )
        memory = self.memory_for(submission.session_id, submission.actor_uuid)
        before = memory.active_routine.model_copy() if memory.active_routine is not None else None
        before_spacing = (
            memory.same_turn_spacing_intention.model_copy()
            if memory.same_turn_spacing_intention is not None
            else None
        )
        before_search_failures = dict(memory.remembered_search_failures)
        before_search_positions = {
            entity_uuid: set(positions)
            for entity_uuid, positions in memory.remembered_search_visited_positions.items()
        }
        consumed_transformation = (
            result.action_effect_committed
            and _submission_consumes_active_transformation(memory, submission)
        )
        if consumed_transformation:
            memory.active_routine = None
        else:
            apply_routine_plan_result(
                memory,
                submission.routine_plan,
                completed=intent_completed,
            )
        if (
            result.action_effect_committed
            and submission.spacing_intention_on_accept is not None
        ):
            memory.same_turn_spacing_intention = submission.spacing_intention_on_accept
        if (
            result.status is CommandResultStatus.ACCEPTED
            and result.action_resolution is ActionResolutionStatus.CANCELED
            and isinstance(submission.intent, ExecuteIntent)
        ):
            record_canceled_action(
                memory,
                row_id=submission.intent.row_id,
                semantic_key=(
                    submission.selected_action_shape.semantic_key
                    if submission.selected_action_shape is not None
                    else None
                ),
            )
        exploration = submission.decision.selected.evidence.exploration
        if (
            intent_completed
            and submission.decision.selected.reason in {
                "investigate_remembered_contact",
                "expand_remembered_contact_search",
            }
            and exploration is not None
            and exploration.remembered_target_uuid is not None
        ):
            record_remembered_investigation(
                memory,
                entity_uuid=exploration.remembered_target_uuid,
                destination=exploration.anchor_position,
            )
        memory_advanced = (
            memory.active_routine != before
            or memory.same_turn_spacing_intention != before_spacing
            or memory.remembered_search_failures != before_search_failures
            or memory.remembered_search_visited_positions != before_search_positions
        )
        record = PolicyResultRecord(
            command_id=command_id,
            disposition=_disposition_for_status(result.status),
            memory_advanced=memory_advanced,
            reason=_result_record_reason(submission, result, intent_completed),
            result=result,
            submission=submission,
        )
        self._recorded_by_command_id[command_id] = record
        return record

    def memory_for(self, session_id: str, actor_uuid: str) -> ActorPolicyMemory:
        """Return memory isolated to this host's session-actor-policy tuple."""
        return self.memory_store.for_actor(session_id, actor_uuid, self.policy_id)

    def invalidate_same_turn_spacing_intention(
        self,
        session_id: str,
        actor_uuid: str,
    ) -> bool:
        """Explicitly release one actor's committed same-turn spacing intent."""
        memory = self.memory_for(session_id, actor_uuid)
        if memory.same_turn_spacing_intention is None:
            return False
        memory.same_turn_spacing_intention = None
        return True

    @staticmethod
    def _validate_actor_alignment(context: PolicyContext) -> None:
        """Validate session authority and every actor-bearing epoch field."""
        world = context.world
        facts = context.facts
        epoch = world.current_epoch
        if epoch is None:
            raise PolicyContextAlignmentError("Subjective world has no decision epoch")
        actor_uuid = epoch.actor_uuid
        if not world.session.is_my_turn:
            raise PolicyContextAlignmentError("Session does not own the current decision epoch")
        if actor_uuid not in world.session.controlled_entity_uuids:
            raise PolicyContextAlignmentError("Decision epoch actor is not a controlled actor")
        if world.session.active_entity_uuid != actor_uuid:
            raise PolicyContextAlignmentError("Session active entity does not match the decision epoch actor")
        if epoch.affordances.actor_uuid != actor_uuid:
            raise PolicyContextAlignmentError("Affordance actor does not match the decision epoch actor")
        if epoch.economy.actor_uuid != actor_uuid:
            raise PolicyContextAlignmentError("Action economy actor does not match the decision epoch actor")
        if epoch.affordances.computed_at_observation_cursor != epoch.basis_observation_cursor:
            raise PolicyContextAlignmentError("Affordances do not match the decision epoch basis cursor")
        if epoch.basis_observation_cursor > world.observation_cursor:
            raise PolicyContextAlignmentError("Decision epoch is newer than the subjective world cursor")
        if facts.actor.session_id != world.session.session_id:
            raise PolicyContextAlignmentError("Policy facts do not match the subjective session")
        if facts.actor.actor_uuid != actor_uuid or not facts.actor.is_my_turn:
            raise PolicyContextAlignmentError("Policy actor facts do not match the controlled actor")
        if facts.affordances.epoch_id != epoch.epoch_id:
            raise PolicyContextAlignmentError("Policy affordances do not match the decision epoch")
        if facts.actor.economy != epoch.economy:
            raise PolicyContextAlignmentError("Policy action economy does not match the decision epoch")

    @staticmethod
    def _key_from_context(context: PolicyContext) -> EpochKey:
        """Return the authoritative session-actor-epoch decision key."""
        epoch = context.world.current_epoch
        assert epoch is not None
        return (context.world.session.session_id, epoch.actor_uuid, epoch.epoch_id)

    @staticmethod
    def _result_mismatch_reason(
        submission: Optional[PreparedPolicySubmission],
        result: CommandResult,
    ) -> Optional[str]:
        """Return a stable mismatch reason without consuming pending state."""
        if result.command_id is None:
            return "command_result_missing_command_id"
        if submission is None:
            return "command_result_has_no_pending_submission"
        if result.session_id != submission.session_id:
            return "command_result_session_mismatch"
        if result.actor_uuid != submission.actor_uuid:
            return "command_result_actor_mismatch"
        if result.requested_epoch_id != submission.epoch_id:
            return "command_result_epoch_mismatch"
        intent = submission.intent
        if isinstance(intent, ExecuteIntent) and result.row_id != intent.row_id:
            return "command_result_row_mismatch"
        if isinstance(intent, EndTurnIntent) and result.row_id != END_TURN_ROW_ID:
            return "end_turn_result_row_mismatch"
        return None


def _timing_started() -> tuple[int, int]:
    """Capture wall and current-thread CPU clocks for one bounded stage."""
    return (time.perf_counter_ns(), time.thread_time_ns())


def _finish_timing(started: tuple[int, int]) -> PolicyStageTiming:
    """Freeze elapsed wall and current-thread CPU milliseconds."""
    wall_started, cpu_started = started
    cpu_elapsed = time.thread_time_ns() - cpu_started
    wall_elapsed = time.perf_counter_ns() - wall_started
    return PolicyStageTiming(
        wall_ms=wall_elapsed / 1_000_000,
        thread_cpu_ms=cpu_elapsed / 1_000_000,
    )


def _submitted_action_shape(
    context: PolicyContext,
    proposal: PolicyProposal,
) -> Optional[SubmittedActionShape]:
    """Extract the selected row's structural contract for result correlation."""
    if not isinstance(proposal.intent, ExecuteIntent):
        return None
    row = context.facts.affordances.by_id.get(proposal.intent.row_id)
    semantics = context.facts.affordances.semantics_by_row_id.get(proposal.intent.row_id)
    if row is None or semantics is None:
        return None
    return SubmittedActionShape(
        action_category=row.action_category,
        semantic_key=row.semantic_key,
        target_allocation=semantics.targeting.allocation,
        semantic_tags=semantics.tags,
        weapon_slot=row.weapon_slot,
        positive_cost_resource_ids=positive_cost_resource_ids(row.cost),
    )


def _submission_consumes_active_transformation(
    memory: ActorPolicyMemory,
    submission: PreparedPolicySubmission,
) -> bool:
    """Return whether the submitted action shape consumes pending setup."""
    progress = memory.active_routine
    shape = submission.selected_action_shape
    if progress is None or progress.consumption_selector is None or shape is None:
        return False
    return action_shape_matches_selector(
        action_category=shape.action_category,
        target_allocation=shape.target_allocation,
        semantic_tags=shape.semantic_tags,
        positive_cost_resource_ids=shape.positive_cost_resource_ids,
        weapon_slot=shape.weapon_slot,
        selector=progress.consumption_selector,
    )


def _submission_completed(
    submission: PreparedPolicySubmission,
    result: CommandResult,
) -> bool:
    """Classify completion using the prepared command kind and typed result."""
    if isinstance(submission.intent, ExecuteIntent):
        return result.action_completed
    if isinstance(submission.intent, EndTurnIntent):
        return result.status is CommandResultStatus.ACCEPTED
    return False


def _result_record_reason(
    submission: PreparedPolicySubmission,
    result: CommandResult,
    intent_completed: bool,
) -> str:
    """Return a stable lifecycle reason without treating absence as success."""
    if (
        result.status is CommandResultStatus.ACCEPTED
        and isinstance(submission.intent, ExecuteIntent)
        and not intent_completed
    ):
        resolution = (
            result.action_resolution.value
            if result.action_resolution is not None
            else "unresolved"
        )
        return f"matched_accepted_{resolution}_command_result"
    return f"matched_{result.status.value}_command_result"


def _disposition_for_status(status: CommandResultStatus) -> PolicyResultDisposition:
    """Map protocol command status to the host lifecycle disposition."""
    return {
        CommandResultStatus.ACCEPTED: PolicyResultDisposition.ACCEPTED,
        CommandResultStatus.REJECTED: PolicyResultDisposition.REJECTED,
        CommandResultStatus.STALE: PolicyResultDisposition.STALE,
        CommandResultStatus.ERROR: PolicyResultDisposition.ERROR,
    }[status]


def _policy_decision_id(
    policy_id: str,
    session_id: str,
    actor_uuid: str,
    epoch_id: str,
    observation_cursor: int,
    execution_constraints: tuple[str, ...],
) -> str:
    """Build a stable opaque identity for one subjective policy binding."""
    identity = "\0".join((
        policy_id,
        session_id,
        actor_uuid,
        epoch_id,
        str(observation_cursor),
        *execution_constraints,
    ))
    return sha256(identity.encode("utf-8")).hexdigest()


def _filter_candidate_set(
    context: PolicyContext,
    candidates: PolicyCandidateSet,
    spacing_intention: Optional[MaintainMinimumDistanceIntention] = None,
) -> PolicyCandidateSet:
    """Remove constrained executable rows before the shared utility choice point."""
    return PolicyCandidateSet(
        direct_damage=_allowed_proposals(context, candidates.direct_damage, spacing_intention),
        healing=_allowed_proposals(context, candidates.healing, spacing_intention),
        control=_allowed_proposals(context, candidates.control, spacing_intention),
        control_preservation=_allowed_proposals(
            context,
            candidates.control_preservation,
            spacing_intention,
        ),
        target_effects=_allowed_proposals(context, candidates.target_effects, spacing_intention),
        self_setup=_allowed_proposals(context, candidates.self_setup, spacing_intention),
        spacing=_allowed_proposals(context, candidates.spacing, spacing_intention),
        exploration=_allowed_proposals(context, candidates.exploration, spacing_intention),
    )


def _allowed_proposals(
    context: PolicyContext,
    proposals: tuple[PolicyProposal, ...],
    spacing_intention: Optional[MaintainMinimumDistanceIntention] = None,
) -> tuple[PolicyProposal, ...]:
    """Return proposals that satisfy execution and retained spatial constraints."""
    allowed: list[PolicyProposal] = []
    for proposal in proposals:
        intent = proposal.intent
        if not isinstance(intent, ExecuteIntent):
            allowed.append(proposal)
            continue
        row = context.facts.affordances.by_id.get(intent.row_id)
        if (
            row is not None
            and context.execution_constraints.allows(row)
            and _respects_spacing_intention(context, proposal, spacing_intention)
        ):
            allowed.append(proposal)
    return tuple(allowed)


def _constrain_routine_plan(
    context: PolicyContext,
    plan: RoutinePlan,
    spacing_intention: Optional[MaintainMinimumDistanceIntention] = None,
) -> RoutinePlan:
    """Block a routine proposal when its legal row was excluded this turn."""
    if plan.proposal is None or _allowed_proposals(
        context,
        (plan.proposal,),
        spacing_intention,
    ):
        return plan
    return plan.model_copy(update={
        "status": RoutinePlanStatus.BLOCKED,
        "proposal": None,
        "next_progress_on_success": None,
        "clear_progress_on_success": False,
        "reason": "blocked_by_policy_execution_constraints",
    })


def _respects_spacing_intention(
    context: PolicyContext,
    proposal: PolicyProposal,
    spacing_intention: Optional[MaintainMinimumDistanceIntention],
) -> bool:
    """Return whether voluntary movement preserves an accepted distance floor."""
    if spacing_intention is None or ActionTag.MOVEMENT_VOLUNTARY not in proposal.semantic_tags:
        return True
    intent = proposal.intent
    if not isinstance(intent, ExecuteIntent):
        return True
    row = context.facts.affordances.by_id.get(intent.row_id)
    if row is None:
        return False
    target = row.targets[0] if row.targets else None
    if target is None or target.position is None:
        return True
    distance_cells = grid_distance_feet(
        target.position,
        spacing_intention.target_position,
    ) // 5
    return distance_cells >= spacing_intention.minimum_distance_cells


def _spacing_intention_on_accept(
    context: PolicyContext,
    proposal: PolicyProposal,
) -> Optional[MaintainMinimumDistanceIntention]:
    """Stage a typed distance floor for an accepted spacing movement."""
    if (
        not isinstance(proposal.intent, ExecuteIntent)
        or ActionTag.MOVEMENT_VOLUNTARY not in proposal.semantic_tags
    ):
        return None
    spacing = proposal.evidence.spacing
    if (
        spacing is None
        or spacing.reference_entity_uuid is None
        or spacing.reference_position is None
        or spacing.selected_distance_cells is None
        or spacing.anchor_position is None
    ):
        return None
    epoch = context.world.current_epoch
    assert epoch is not None
    return MaintainMinimumDistanceIntention(
        target_uuid=spacing.reference_entity_uuid,
        target_position=spacing.reference_position,
        minimum_distance_cells=min(
            spacing.selected_distance_cells,
            spacing.spacing_floor_cells,
        ),
        started_round_number=epoch.round_number,
        started_turn_index=epoch.turn_index,
    )
