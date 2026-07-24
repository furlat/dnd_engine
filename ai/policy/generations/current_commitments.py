"""Candidate-owned tactical commitments layered over the frozen policy host."""

from __future__ import annotations

from dataclasses import replace
from enum import Enum
from hashlib import sha256
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ai.planning.composition import compose_option
from ai.planning.contracts import LogicalStep, OptionContract
from ai.policy.generations.current_options import option_for_routine
from ai.policy.candidates import PolicyCandidateSet
from ai.policy.contracts import (
    NodeStatus,
    ExecuteIntent,
    PolicyContext,
    PolicyGoal,
    PolicyProposal,
    PolicyTraceStep,
)
from ai.policy.default import DefaultPolicyEvaluation, evaluate_default_policy
from ai.policy.definitions import (
    PolicyGenerationRole,
    PolicyImplementation,
)
from ai.policy.host import (
    PolicyHost,
    PolicyTelemetrySink,
    PolicyResultDisposition,
    PolicyResultRecord,
)
from ai.policy.routines import RoutinePlan
from ai.policy.source import POLICY_NAME
from ai.policy.memory import PolicyMemoryStore
from server.agent_protocol.control import CommandResult
from server.agent_protocol.semantics import (
    ComparisonOperator,
    EffectOperation,
    FactExpression,
    FactOperator,
    FactPredicate,
    FactValue,
    LogicalEffect,
)


EXECUTION_SWITCH_COST = 8.0
COORDINATION_BREAK_COST = 4.0
HYSTERESIS_MARGIN = 6.0
PROGRESS_VALUE_PER_ACCEPTED_STEP = 3.0
MAX_PROGRESS_VALUE = 12.0
SURVIVAL_INTERRUPT_HP_FRACTION = 0.35


class CommitmentModel(BaseModel):
    """Immutable base for candidate-owned commitment state and evidence."""

    model_config = ConfigDict(frozen=True)


class CommitmentSubjectKind(str, Enum):
    """Subjective referent pursued by a tactical commitment."""

    ENTITY = "entity"
    OBJECT = "object"
    POSITION = "position"
    FRONTIER = "frontier"
    ACTOR = "actor"


class CommitmentStatus(str, Enum):
    """Lifecycle state of one persistent intention."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    INVALIDATED = "invalidated"


class CommitmentTransitionKind(str, Enum):
    """Inspectable change applied during one decision or command result."""

    NONE = "none"
    ADOPT = "adopt"
    RETAIN = "retain"
    SWITCH = "switch"
    SUSPEND = "suspend"
    INTERRUPT = "interrupt"
    RESUME = "resume"
    COMPLETE = "complete"
    INVALIDATE = "invalidate"
    ADVANCE = "advance"


class CommitmentSubject(CommitmentModel):
    """Reference retained without copying current world facts."""

    kind: CommitmentSubjectKind = Field(description="Kind of subjective referent.")
    subject_uuid: Optional[str] = Field(default=None, description="Stable entity or object UUID.")


class LogicalCommitmentContract(CommitmentModel):
    """Executable logical lifecycle contract for one tactical intention."""

    adoption: FactExpression = Field(description="Facts required to adopt the intention.")
    invariants: FactExpression = Field(description="Facts required to keep it active.")
    desired_state: FactExpression = Field(description="State pursued by the commitment.")
    completion: FactExpression = Field(description="Facts establishing successful completion.")
    invalidation: FactExpression = Field(description="Facts proving the intention invalid.")
    progress_effects: tuple[LogicalEffect, ...] = Field(
        default_factory=tuple,
        description="Abstract progress expected from accepted supporting steps.",
    )


class SessionCommitment(CommitmentModel):
    """Team-level objective shared by actors controlled by one session."""

    commitment_id: str = Field(description="Stable identity of this adoption.")
    session_id: str = Field(description="Owning subjective session.")
    policy_id: str = Field(description="Candidate policy owning the intention.")
    revision: int = Field(ge=1, description="Monotonic team-objective revision.")
    objective: PolicyGoal = Field(description="Stable tactical objective.")
    subject: CommitmentSubject = Field(description="Subjective focus of the objective.")
    contract: LogicalCommitmentContract = Field(description="Logical lifecycle contract.")
    adopted_at_cursor: int = Field(ge=0, description="Subjective cursor at adoption.")
    adopted_at_epoch_id: str = Field(description="Decision epoch at adoption.")
    adoption_value: float = Field(description="Proposal value at adoption.")
    accepted_steps: int = Field(default=0, ge=0, description="Accepted completed supporting commands.")
    status: CommitmentStatus = Field(default=CommitmentStatus.ACTIVE, description="Current lifecycle state.")


class ActorCommitment(CommitmentModel):
    """Actor-local method serving one team objective."""

    commitment_id: str = Field(description="Stable actor intention identity.")
    session_id: str = Field(description="Owning subjective session.")
    actor_uuid: str = Field(description="Controlled actor serving the objective.")
    policy_id: str = Field(description="Candidate policy owning the intention.")
    parent_commitment_id: str = Field(description="Session commitment being served.")
    parent_revision: int = Field(ge=1, description="Team objective revision at actor binding.")
    objective: PolicyGoal = Field(description="Actor tactical objective.")
    subject: CommitmentSubject = Field(description="Subjective focus of the method.")
    option_id: str = Field(description="Logical option or primitive semantic family.")
    accepted_steps: int = Field(default=0, ge=0, description="Accepted completed supporting commands.")
    status: CommitmentStatus = Field(default=CommitmentStatus.ACTIVE, description="Current lifecycle state.")


class ProposalCommitmentDescriptor(CommitmentModel):
    """Stable proposal meaning used for commitment arbitration."""

    objective: PolicyGoal = Field(description="Proposal tactical objective.")
    target_uuids: tuple[str, ...] = Field(description="Subjective entities affected or pursued.")
    option_id: str = Field(description="Routine or primitive semantic identity.")
    supports_information_search: bool = Field(description="Whether the proposal investigates remembered knowledge.")
    logical_option: Optional[OptionContract] = Field(
        default=None,
        description="Composed primitive option contract when available.",
    )


class CommitmentTransition(CommitmentModel):
    """Inspectable commitment change and switch arithmetic."""

    kind: CommitmentTransitionKind = Field(description="Lifecycle transition.")
    reason: str = Field(description="Stable explanation.")
    incumbent_commitment_id: Optional[str] = Field(default=None, description="Commitment before transition.")
    selected_commitment_id: Optional[str] = Field(default=None, description="Commitment after transition.")
    incumbent_value: Optional[float] = Field(default=None, description="Best supporting proposal value.")
    alternative_value: Optional[float] = Field(default=None, description="Best competing proposal value.")
    execution_switch_cost: float = Field(default=0.0, ge=0.0, description="Cost of abandoning execution context.")
    unfinished_progress_value: float = Field(default=0.0, ge=0.0, description="Value retained by unfinished progress.")
    coordination_break_cost: float = Field(default=0.0, ge=0.0, description="Cost of revising the shared objective.")
    hysteresis_margin: float = Field(default=0.0, ge=0.0, description="Minimum dominance margin.")

    @property
    def required_switch_advantage(self) -> float:
        """Return the explicit threshold an alternative must exceed."""
        return (
            self.execution_switch_cost
            + self.unfinished_progress_value
            + self.coordination_break_cost
            + self.hysteresis_margin
        )


class CandidateCommitmentStore:
    """Control-only commitment memory scoped by session, actor, and policy."""

    def __init__(self) -> None:
        """Create an empty candidate state store."""
        self.session_commitments: dict[tuple[str, str], SessionCommitment] = {}
        self.actor_commitments: dict[tuple[str, str, str], ActorCommitment] = {}
        self.last_transition_by_session: dict[tuple[str, str], CommitmentTransition] = {}

    def session(
        self,
        session_id: str,
        policy_id: str,
    ) -> Optional[SessionCommitment]:
        """Return one session objective without manufacturing a default."""
        return self.session_commitments.get((session_id, policy_id))

    def actor(
        self,
        session_id: str,
        actor_uuid: str,
        policy_id: str,
    ) -> Optional[ActorCommitment]:
        """Return one actor method without manufacturing a default."""
        return self.actor_commitments.get((session_id, actor_uuid, policy_id))

    def clear_session(self, session_id: str, policy_id: str) -> None:
        """Remove all candidate control memory for one subjective session."""
        self.session_commitments.pop((session_id, policy_id), None)
        self.last_transition_by_session.pop((session_id, policy_id), None)
        for key in [
            key
            for key in self.actor_commitments
            if key[0] == session_id and key[2] == policy_id
        ]:
            self.actor_commitments.pop(key, None)


class CandidateCommitmentEvaluator:
    """Stateful candidate evaluator retaining tactical intent across epochs."""

    def __init__(
        self,
        *,
        policy_id: str,
        store: Optional[CandidateCommitmentStore] = None,
    ) -> None:
        """Create one host-local evaluator and commitment store."""
        self.policy_id = policy_id
        self.store = store or CandidateCommitmentStore()

    def __call__(
        self,
        context: PolicyContext,
        routine_plans: tuple[RoutinePlan, ...],
        candidates: Optional[PolicyCandidateSet] = None,
    ) -> DefaultPolicyEvaluation:
        """Revalidate intent, arbitrate within it, and trace every transition."""
        context.validate_alignment()
        if candidates is None:
            return evaluate_default_policy(context, routine_plans, candidates)
        epoch = context.world.current_epoch
        assert epoch is not None
        session_id = context.world.session.session_id

        key = (session_id, self.policy_id)
        incumbent = self.store.session(session_id, self.policy_id)
        transition = self._revalidate(context, incumbent)
        incumbent = self.store.session(session_id, self.policy_id)
        global_evaluation = evaluate_default_policy(context, routine_plans, candidates)
        if global_evaluation.decision is None:
            return global_evaluation

        selected_evaluation = global_evaluation
        if incumbent is not None:
            focused_candidates = _supporting_candidate_set(
                context,
                candidates,
                incumbent,
            )
            focused_plans = tuple(
                plan
                for plan in routine_plans
                if plan.proposal is None
                or _proposal_supports_commitment(
                    context,
                    plan.proposal,
                    incumbent,
                    routine_plans,
                )
            )
            focused_evaluation = evaluate_default_policy(
                context,
                focused_plans,
                focused_candidates,
            )
            selected_evaluation, transition = self._arbitrate(
                context,
                incumbent,
                focused_evaluation,
                global_evaluation,
                routine_plans,
                transition,
            )

        selected = selected_evaluation.decision
        assert selected is not None
        descriptor = describe_proposal(
            context,
            selected.selected,
            selected_evaluation.selected_routine_plan,
        )
        active = self.store.session(session_id, self.policy_id)
        if active is None and descriptor.target_uuids:
            transition = self._adopt(
                context,
                selected.selected,
                descriptor,
                previous=None,
                kind=CommitmentTransitionKind.ADOPT,
                reason="adopt_selected_tactical_objective",
            )
            active = self.store.session(session_id, self.policy_id)
        if active is not None:
            self._bind_actor(
                context,
                active,
                descriptor,
            )

        self.store.last_transition_by_session[key] = transition
        return _with_commitment_trace(selected_evaluation, active, transition)

    def _revalidate(
        self,
        context: PolicyContext,
        incumbent: Optional[SessionCommitment],
    ) -> CommitmentTransition:
        """Reconcile one retained objective against fresh subjective facts."""
        if incumbent is None:
            return CommitmentTransition(
                kind=CommitmentTransitionKind.NONE,
                reason="no_active_commitment",
            )
        session_key = (incumbent.session_id, incumbent.policy_id)
        target_uuid = incumbent.subject.subject_uuid
        if target_uuid is None:
            return CommitmentTransition(
                kind=CommitmentTransitionKind.RETAIN,
                reason="subjectless_commitment_retained",
                incumbent_commitment_id=incumbent.commitment_id,
                selected_commitment_id=incumbent.commitment_id,
            )
        target = context.world.known_entities.get(target_uuid)
        if target is not None and target.is_dead is True:
            self.store.session_commitments.pop(session_key, None)
            self._clear_actors_for_parent(incumbent.commitment_id)
            return CommitmentTransition(
                kind=CommitmentTransitionKind.COMPLETE,
                reason="subjectively_known_target_dead",
                incumbent_commitment_id=incumbent.commitment_id,
            )
        visible = target_uuid in context.facts.contacts.visible_hostile_uuids
        remembered = target_uuid in context.facts.contacts.remembered_hostile_uuids
        if visible:
            if incumbent.status is CommitmentStatus.SUSPENDED:
                resumed = incumbent.model_copy(update={
                    "status": CommitmentStatus.ACTIVE,
                    "revision": incumbent.revision + 1,
                })
                self.store.session_commitments[session_key] = resumed
                return CommitmentTransition(
                    kind=CommitmentTransitionKind.RESUME,
                    reason="target_reacquired_from_subjective_observation",
                    incumbent_commitment_id=incumbent.commitment_id,
                    selected_commitment_id=resumed.commitment_id,
                )
            return CommitmentTransition(
                kind=CommitmentTransitionKind.RETAIN,
                reason="commitment_invariants_subjectively_hold",
                incumbent_commitment_id=incumbent.commitment_id,
                selected_commitment_id=incumbent.commitment_id,
            )
        if remembered:
            suspended = incumbent.model_copy(update={
                "status": CommitmentStatus.SUSPENDED,
                "revision": incumbent.revision + 1,
            })
            self.store.session_commitments[session_key] = suspended
            return CommitmentTransition(
                kind=CommitmentTransitionKind.SUSPEND,
                reason="target_only_remembered_requires_search_not_targeting",
                incumbent_commitment_id=incumbent.commitment_id,
                selected_commitment_id=suspended.commitment_id,
            )
        self.store.session_commitments.pop(session_key, None)
        self._clear_actors_for_parent(incumbent.commitment_id)
        return CommitmentTransition(
            kind=CommitmentTransitionKind.INVALIDATE,
            reason="target_no_longer_present_in_subjective_knowledge",
            incumbent_commitment_id=incumbent.commitment_id,
        )

    def _arbitrate(
        self,
        context: PolicyContext,
        incumbent: SessionCommitment,
        focused: DefaultPolicyEvaluation,
        global_evaluation: DefaultPolicyEvaluation,
        routine_plans: tuple[RoutinePlan, ...],
        revalidation: CommitmentTransition,
    ) -> tuple[DefaultPolicyEvaluation, CommitmentTransition]:
        """Retain, interrupt, or switch using explicit typed arithmetic."""
        global_decision = global_evaluation.decision
        assert global_decision is not None
        global_proposal = global_decision.selected
        if _is_survival_emergency(context, global_proposal):
            return global_evaluation, CommitmentTransition(
                kind=CommitmentTransitionKind.INTERRUPT,
                reason="typed_survival_emergency",
                incumbent_commitment_id=incumbent.commitment_id,
                selected_commitment_id=incumbent.commitment_id,
                incumbent_value=(
                    focused.decision.selected.score
                    if focused.decision is not None
                    else None
                ),
                alternative_value=global_proposal.score,
            )
        if focused.decision is None or focused.decision.selected.goal is PolicyGoal.END_TURN:
            return global_evaluation, CommitmentTransition(
                kind=CommitmentTransitionKind.RETAIN,
                reason="actor_has_no_supporting_command_team_objective_retained",
                incumbent_commitment_id=incumbent.commitment_id,
                selected_commitment_id=incumbent.commitment_id,
            )
        focused_proposal = focused.decision.selected
        global_descriptor = describe_proposal(
            context,
            global_proposal,
            global_evaluation.selected_routine_plan,
        )
        incumbent_target = incumbent.subject.subject_uuid
        alternative_target = (
            global_descriptor.target_uuids[0]
            if global_descriptor.target_uuids
            else None
        )
        if alternative_target in {None, incumbent_target}:
            return focused, revalidation

        unfinished = min(
            MAX_PROGRESS_VALUE,
            incumbent.accepted_steps * PROGRESS_VALUE_PER_ACCEPTED_STEP,
        )
        transition = CommitmentTransition(
            kind=CommitmentTransitionKind.RETAIN,
            reason="alternative_did_not_exceed_explicit_switch_threshold",
            incumbent_commitment_id=incumbent.commitment_id,
            selected_commitment_id=incumbent.commitment_id,
            incumbent_value=focused_proposal.score,
            alternative_value=global_proposal.score,
            execution_switch_cost=EXECUTION_SWITCH_COST,
            unfinished_progress_value=unfinished,
            coordination_break_cost=COORDINATION_BREAK_COST,
            hysteresis_margin=HYSTERESIS_MARGIN,
        )
        advantage = global_proposal.score - focused_proposal.score
        if advantage <= transition.required_switch_advantage:
            return focused, transition
        switched = self._adopt(
            context,
            global_proposal,
            global_descriptor,
            previous=incumbent,
            kind=CommitmentTransitionKind.SWITCH,
            reason="alternative_exceeded_explicit_switch_threshold",
        )
        switched = switched.model_copy(update={
            "incumbent_value": focused_proposal.score,
            "alternative_value": global_proposal.score,
            "execution_switch_cost": EXECUTION_SWITCH_COST,
            "unfinished_progress_value": unfinished,
            "coordination_break_cost": COORDINATION_BREAK_COST,
            "hysteresis_margin": HYSTERESIS_MARGIN,
        })
        return global_evaluation, switched

    def _adopt(
        self,
        context: PolicyContext,
        proposal: PolicyProposal,
        descriptor: ProposalCommitmentDescriptor,
        *,
        previous: Optional[SessionCommitment],
        kind: CommitmentTransitionKind,
        reason: str,
    ) -> CommitmentTransition:
        """Adopt one proposal as a session objective."""
        epoch = context.world.current_epoch
        assert epoch is not None
        session_id = context.world.session.session_id
        target_uuid = descriptor.target_uuids[0]
        revision = previous.revision + 1 if previous is not None else 1
        commitment_id = _commitment_id(
            session_id,
            self.policy_id,
            target_uuid,
            proposal.goal,
            revision,
            context.world.observation_cursor,
        )
        contract = _entity_commitment_contract()
        commitment = SessionCommitment(
            commitment_id=commitment_id,
            session_id=session_id,
            policy_id=self.policy_id,
            revision=revision,
            objective=proposal.goal,
            subject=CommitmentSubject(
                kind=CommitmentSubjectKind.ENTITY,
                subject_uuid=target_uuid,
            ),
            contract=contract,
            adopted_at_cursor=context.world.observation_cursor,
            adopted_at_epoch_id=epoch.epoch_id,
            adoption_value=proposal.score,
            status=CommitmentStatus.ACTIVE,
        )
        self.store.session_commitments[(session_id, self.policy_id)] = commitment
        if previous is not None:
            self._clear_actors_for_parent(previous.commitment_id)
        return CommitmentTransition(
            kind=kind,
            reason=reason,
            incumbent_commitment_id=previous.commitment_id if previous is not None else None,
            selected_commitment_id=commitment_id,
        )

    def _bind_actor(
        self,
        context: PolicyContext,
        session_commitment: SessionCommitment,
        descriptor: ProposalCommitmentDescriptor,
    ) -> None:
        """Bind the active actor to the current team objective and method."""
        epoch = context.world.current_epoch
        assert epoch is not None
        actor_key = (
            session_commitment.session_id,
            epoch.actor_uuid,
            self.policy_id,
        )
        prior = self.store.actor_commitments.get(actor_key)
        if (
            prior is not None
            and prior.parent_commitment_id == session_commitment.commitment_id
            and prior.option_id == descriptor.option_id
        ):
            return
        self.store.actor_commitments[actor_key] = ActorCommitment(
            commitment_id=_actor_commitment_id(
                session_commitment.commitment_id,
                epoch.actor_uuid,
                descriptor.option_id,
            ),
            session_id=session_commitment.session_id,
            actor_uuid=epoch.actor_uuid,
            policy_id=self.policy_id,
            parent_commitment_id=session_commitment.commitment_id,
            parent_revision=session_commitment.revision,
            objective=session_commitment.objective,
            subject=session_commitment.subject,
            option_id=descriptor.option_id,
        )

    def record_result(self, record: PolicyResultRecord) -> CommitmentTransition:
        """Advance only matched accepted and completed supporting commands."""
        submission = record.submission
        if (
            record.disposition is not PolicyResultDisposition.ACCEPTED
            or submission is None
            or not record.result.action_completed
            or submission.decision.selected.goal is PolicyGoal.END_TURN
        ):
            return CommitmentTransition(
                kind=CommitmentTransitionKind.NONE,
                reason="command_result_did_not_commit_completed_supporting_effect",
            )
        session_key = (submission.session_id, self.policy_id)
        session = self.store.session_commitments.get(session_key)
        actor_key = (
            submission.session_id,
            submission.actor_uuid,
            self.policy_id,
        )
        actor = self.store.actor_commitments.get(actor_key)
        if session is None or actor is None:
            return CommitmentTransition(
                kind=CommitmentTransitionKind.NONE,
                reason="no_matching_candidate_commitment",
            )
        updated_session = session.model_copy(update={
            "accepted_steps": session.accepted_steps + 1,
        })
        updated_actor = actor.model_copy(update={
            "accepted_steps": actor.accepted_steps + 1,
        })
        self.store.session_commitments[session_key] = updated_session
        self.store.actor_commitments[actor_key] = updated_actor
        transition = CommitmentTransition(
            kind=CommitmentTransitionKind.ADVANCE,
            reason="matched_accepted_completed_supporting_command",
            incumbent_commitment_id=session.commitment_id,
            selected_commitment_id=session.commitment_id,
        )
        self.store.last_transition_by_session[session_key] = transition
        return transition

    def _clear_actors_for_parent(self, parent_commitment_id: str) -> None:
        """Remove actor methods serving a completed or replaced team objective."""
        for key in [
            key
            for key, commitment in self.store.actor_commitments.items()
            if commitment.parent_commitment_id == parent_commitment_id
        ]:
            self.store.actor_commitments.pop(key, None)


class CurrentCandidatePolicyHost(PolicyHost):
    """Policy host whose only added behavior is candidate-owned commitments."""

    def __init__(
        self,
        *,
        implementation: PolicyImplementation,
        commitment_store: Optional[CandidateCommitmentStore] = None,
        policy_id: str = POLICY_NAME,
        controller_mode: str = "shared",
        memory_store: Optional[PolicyMemoryStore] = None,
        telemetry_sink: Optional[PolicyTelemetrySink] = None,
    ) -> None:
        """Wrap the candidate evaluator while retaining host lifecycle logic."""
        if implementation.identity.role is not PolicyGenerationRole.CANDIDATE:
            raise ValueError("CurrentCandidatePolicyHost requires a candidate generation")
        evaluator = CandidateCommitmentEvaluator(
            policy_id=implementation.identity.generation_id,
            store=commitment_store,
        )
        self.commitment_evaluator = evaluator
        wrapped = replace(implementation, evaluate=evaluator)
        super().__init__(
            implementation=wrapped,
            policy_id=policy_id,
            controller_mode=controller_mode,
            memory_store=memory_store,
            telemetry_sink=telemetry_sink,
        )

    @property
    def commitment_store(self) -> CandidateCommitmentStore:
        """Return host-local candidate commitment memory for observability."""
        return self.commitment_evaluator.store

    def record_result(self, result: CommandResult) -> PolicyResultRecord:
        """Apply the authoritative host gate before candidate progress."""
        record = super().record_result(result)
        self.commitment_evaluator.record_result(record)
        return record


def create_generation_policy_host(
    implementation: Optional[PolicyImplementation],
    *,
    commitment_store: Optional[CandidateCommitmentStore] = None,
    policy_id: str = POLICY_NAME,
    controller_mode: str = "shared",
    memory_store: Optional[PolicyMemoryStore] = None,
    telemetry_sink: Optional[PolicyTelemetrySink] = None,
) -> PolicyHost:
    """Create the correct host without changing frozen baseline behavior."""
    if (
        implementation is not None
        and implementation.identity.role is PolicyGenerationRole.CANDIDATE
    ):
        return CurrentCandidatePolicyHost(
            implementation=implementation,
            policy_id=policy_id,
            commitment_store=commitment_store,
            controller_mode=controller_mode,
            memory_store=memory_store,
            telemetry_sink=telemetry_sink,
        )
    return PolicyHost(
        policy_id=policy_id,
        implementation=implementation,
        controller_mode=controller_mode,
        memory_store=memory_store,
        telemetry_sink=telemetry_sink,
    )


def describe_proposal(
    context: PolicyContext,
    proposal: PolicyProposal,
    routine_plan: Optional[RoutinePlan],
) -> ProposalCommitmentDescriptor:
    """Reduce proposal evidence to stable target and option meaning."""
    targets: list[str] = []
    evidence = proposal.evidence
    if evidence.target_plan is not None:
        plan = evidence.target_plan
        if plan.primary_target_uuid is not None:
            targets.append(plan.primary_target_uuid)
        targets.extend(plan.hostile_entity_uuids)
        targets.extend(plan.selected_target_uuids)
    targets.extend(outcome.entity_uuid for outcome in evidence.damage_outcomes)
    targets.extend(outcome.entity_uuid for outcome in evidence.target_effects)
    if evidence.spacing is not None:
        projection = evidence.spacing.capability_target_projection
        if projection is not None:
            targets.append(projection.target_entity_uuid)
        if evidence.spacing.reference_entity_uuid is not None:
            targets.append(evidence.spacing.reference_entity_uuid)
    if evidence.exploration is not None and evidence.exploration.remembered_target_uuid is not None:
        targets.append(evidence.exploration.remembered_target_uuid)
    if routine_plan is not None and routine_plan.target_uuid is not None:
        targets.append(routine_plan.target_uuid)
    stable_targets = tuple(dict.fromkeys(
        target
        for target in targets
        if (
            target in context.facts.contacts.visible_hostile_uuids
            or target in context.facts.contacts.remembered_hostile_uuids
        )
    ))
    option_id = (
        routine_plan.routine_id
        if routine_plan is not None
        else _proposal_semantic_id(context, proposal)
    )
    return ProposalCommitmentDescriptor(
        objective=proposal.goal,
        target_uuids=stable_targets,
        option_id=option_id,
        supports_information_search=(
            evidence.exploration is not None
            and evidence.exploration.remembered_target_uuid is not None
        ),
        logical_option=_proposal_logical_option(context, proposal, routine_plan, option_id),
    )


def _proposal_logical_option(
    context: PolicyContext,
    proposal: PolicyProposal,
    routine_plan: Optional[RoutinePlan],
    option_id: str,
) -> Optional[OptionContract]:
    """Return authored routine meaning before falling back to primitive rows."""
    if routine_plan is not None:
        return option_for_routine(routine_plan.routine_id)
    return _primitive_logical_option(context, proposal, option_id)


def _supporting_candidate_set(
    context: PolicyContext,
    candidates: PolicyCandidateSet,
    commitment: SessionCommitment,
) -> PolicyCandidateSet:
    """Restrict utility competition to proposals serving retained intent."""

    def retain(proposals: tuple[PolicyProposal, ...]) -> tuple[PolicyProposal, ...]:
        return tuple(
            proposal
            for proposal in proposals
            if _proposal_supports_commitment(
                context,
                proposal,
                commitment,
                (),
            )
            or _is_survival_emergency(context, proposal)
        )

    return PolicyCandidateSet(
        direct_damage=retain(candidates.direct_damage),
        healing=retain(candidates.healing),
        control=retain(candidates.control),
        control_preservation=retain(candidates.control_preservation),
        target_effects=retain(candidates.target_effects),
        self_setup=retain(candidates.self_setup),
        spacing=retain(candidates.spacing),
        exploration=retain(candidates.exploration),
    )


def _proposal_supports_commitment(
    context: PolicyContext,
    proposal: PolicyProposal,
    commitment: SessionCommitment,
    routine_plans: tuple[RoutinePlan, ...],
) -> bool:
    """Return whether one proposal advances or investigates retained intent."""
    routine_plan = next(
        (
            plan
            for plan in routine_plans
            if plan.proposal is proposal or plan.proposal == proposal
        ),
        None,
    )
    descriptor = describe_proposal(context, proposal, routine_plan)
    target_uuid = commitment.subject.subject_uuid
    if target_uuid is None:
        return proposal.goal is commitment.objective
    if target_uuid not in descriptor.target_uuids:
        return False
    if commitment.status is CommitmentStatus.SUSPENDED:
        return descriptor.supports_information_search
    return proposal.goal in {
        PolicyGoal.DIRECT_PRESSURE,
        PolicyGoal.HOSTILE_CONTROL,
        PolicyGoal.CONDITIONAL_TARGET_EFFECT,
        PolicyGoal.ROUTINE,
        PolicyGoal.POSITION_AND_SURVIVAL,
        PolicyGoal.CONTROL_PRESERVATION,
    }


def _is_survival_emergency(
    context: PolicyContext,
    proposal: PolicyProposal,
) -> bool:
    """Recognize an explicit low-HP survival interrupt."""
    if proposal.goal is not PolicyGoal.SURVIVAL_RECOVERY:
        return False
    hp = (
        context.facts.actor.normal_hp
        if context.facts.actor.normal_hp is not None
        else context.facts.actor.hp
    )
    maximum = context.facts.actor.max_hp
    if hp is None or maximum is None or maximum == 0:
        return False
    return hp / maximum <= SURVIVAL_INTERRUPT_HP_FRACTION


def _entity_commitment_contract() -> LogicalCommitmentContract:
    """Return the common logical lifecycle for a hostile entity objective."""
    return LogicalCommitmentContract(
        adoption=_predicate("subject.known_hostile", True),
        invariants=_predicate("subject.known_dead", False),
        desired_state=_predicate("subject.defeated", True),
        completion=_predicate("subject.known_dead", True),
        invalidation=_predicate("subject.valid_commitment_subject", False),
        progress_effects=(LogicalEffect(
            fact_id="subject.pressure_progress",
            operation=EffectOperation.INCREASE,
            value=1,
        ),),
    )


def _predicate(
    fact_id: str,
    expected_value: FactValue,
) -> FactExpression:
    """Build a compact commitment predicate."""
    return FactExpression(
        operator=FactOperator.PREDICATE,
        predicate=FactPredicate(
            fact_id=fact_id,
            comparison=ComparisonOperator.EQUALS,
            expected_value=expected_value,
        ),
    )


def _proposal_semantic_id(
    context: PolicyContext,
    proposal: PolicyProposal,
) -> str:
    """Return primitive action meaning without retaining an epoch row id."""


    if not isinstance(proposal.intent, ExecuteIntent):
        return f"policy.{proposal.goal.value}"
    semantics = context.facts.affordances.semantics_by_row_id.get(
        proposal.intent.row_id
    )
    return semantics.semantic_id if semantics is not None else "action.unknown"


def _primitive_logical_option(
    context: PolicyContext,
    proposal: PolicyProposal,
    option_id: str,
) -> Optional[OptionContract]:
    """Compose one selected primitive semantics for interpretability."""


    if not isinstance(proposal.intent, ExecuteIntent):
        return None
    semantics = context.facts.affordances.semantics_by_row_id.get(
        proposal.intent.row_id
    )
    if semantics is None:
        return None
    step = LogicalStep.from_action_semantics(
        step_id=semantics.semantic_id,
        semantics=semantics,
        description=proposal.reason,
    )
    return compose_option(
        option_id,
        (step,),
    )


def _commitment_id(
    session_id: str,
    policy_id: str,
    target_uuid: str,
    goal: PolicyGoal,
    revision: int,
    observation_cursor: int,
) -> str:
    """Build deterministic commitment identity without an epoch row id."""
    payload = "\0".join((
        session_id,
        policy_id,
        target_uuid,
        goal.value,
        str(revision),
        str(observation_cursor),
    ))
    return sha256(payload.encode("utf-8")).hexdigest()


def _actor_commitment_id(
    parent_commitment_id: str,
    actor_uuid: str,
    option_id: str,
) -> str:
    """Build deterministic actor-method identity."""
    payload = "\0".join((parent_commitment_id, actor_uuid, option_id))
    return sha256(payload.encode("utf-8")).hexdigest()


def _with_commitment_trace(
    evaluation: DefaultPolicyEvaluation,
    commitment: Optional[SessionCommitment],
    transition: CommitmentTransition,
) -> DefaultPolicyEvaluation:
    """Append complete commitment and switch evidence to a decision."""
    decision = evaluation.decision
    if decision is None:
        return evaluation
    commitment_detail = (
        "none"
        if commitment is None
        else (
            f"{commitment.status.value}:"
            f"{commitment.objective.value}:"
            f"subject={commitment.subject.subject_uuid}:"
            f"revision={commitment.revision}:"
            f"accepted_steps={commitment.accepted_steps}:"
            "preconditions=subject.known_hostile:"
            "invariants=!subject.known_dead:"
            "completion=subject.known_dead:"
            "invalidation=!subject.valid_commitment_subject"
        )
    )
    arithmetic = (
        f"incumbent={transition.incumbent_value}:"
        f"alternative={transition.alternative_value}:"
        f"switch={transition.execution_switch_cost}:"
        f"progress={transition.unfinished_progress_value}:"
        f"coordination={transition.coordination_break_cost}:"
        f"hysteresis={transition.hysteresis_margin}:"
        f"required={transition.required_switch_advantage}"
    )
    trace = (
        PolicyTraceStep(
            node_path="CurrentCommitment/Revalidate",
            status=NodeStatus.SUCCESS,
            detail=commitment_detail,
        ),
        PolicyTraceStep(
            node_path="CurrentCommitment/Arbitrate",
            status=NodeStatus.SUCCESS,
            detail=f"{transition.kind.value}:{transition.reason}:{arithmetic}",
        ),
        *decision.trace,
    )
    return evaluation.model_copy(update={
        "decision": decision.model_copy(update={"trace": trace}),
    })
