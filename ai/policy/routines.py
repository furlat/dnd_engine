"""Typed, revalidating multi-epoch policy routines."""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from ai.knowledge import derive_agent_facts
from ai.knowledge.topology import (
    KnownLineOfSightWorkspace,
    grid_distance_feet,
    known_line_of_sight,
)
from ai.policy.candidates import (
    DIRECT_DAMAGE_TAGS,
    PolicyCandidateSet,
    build_policy_candidate_set,
    direct_damage_candidates,
    self_setup_effect_may_already_be_active,
)
from ai.policy.contracts import (
    PolicyContext,
    PolicyGoal,
    PolicyProposal,
    UtilityComponent,
)
from dnd.ai.contracts.decision import EndTurnIntent, ExecuteIntent
from ai.policy.economy import (
    AffordabilityWorkspace,
    ProjectedCapability,
    action_economy_opportunity_cost,
    affordance_matches_selector,
    capability_matches_selector,
    capability_is_turn_refreshable,
    combined_costs_affordable,
    project_capability_transformation,
)
from ai.policy.outcomes import (
    DamageOutcomeWorkspace,
    estimate_damage_outcome,
    project_outcome_profile,
)
from ai.policy.memory import ActorPolicyMemory, RoutineProgress, SemanticActionGoal
from ai.knowledge.replay import (
    entity_fact_replay_token,
    object_fact_replay_token,
    position_replay_token,
)
from ai.policy.utility import UtilityArbiter
from dnd.ai.contracts.control import (
    ActionAffordance,
    ActionCapability,
    ActionCostProfile,
    ActionTarget,
)
from dnd.ai.contracts.semantics import (
    ActionSemantics,
    ActionTag,
    ComparisonOperator,
    EffectOperation,
    FactExpression,
    FactOperator,
    FactPredicate,
    FactValue,
    LogicalEffect,
    SelfSetupDuration,
    TargetAllocation,
    TruthValue,
)


Position = Tuple[int, int]
DOMINANT_DURABLE_SETUP_SCORE = 110.0
PURSUE_CAPABILITY_STARTER_SCORE = 65.0


class RoutineModel(BaseModel):
    """Immutable base for routine definitions and evaluations."""

    model_config = ConfigDict(frozen=True)


class RoutinePlanStatus(str, Enum):
    """Outcome of planning one routine step."""

    PROPOSED = "proposed"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class RoutineRevalidationStatus(str, Enum):
    """Outcome of checking remembered routine progress against a new epoch."""

    IDLE = "idle"
    VALID = "valid"
    ADVANCED = "advanced"
    EXHAUSTED = "exhausted"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    INVALIDATED = "invalidated"


class RoutinePurpose(str, Enum):
    """Stable tactical meaning of a bounded routine."""

    SUBJECTIVE_DISCOVERY = "subjective_discovery"
    OFFENSIVE_ENABLEMENT = "offensive_enablement"
    OFFENSIVE_AUGMENTATION = "offensive_augmentation"
    CAPABILITY_TRANSFORMATION = "capability_transformation"
    OFFENSIVE_PURSUIT = "offensive_pursuit"


class RoutineStepContract(RoutineModel):
    """Planner-readable contract for one bounded routine step."""

    step_id: str = Field(description="Stable step identifier.")
    description: str = Field(description="Purpose of this step.")
    preconditions: FactExpression = Field(description="Subjective facts required by the step.")
    accepted_action_tags: frozenset[ActionTag] = Field(
        default_factory=frozenset,
        description="Semantic capabilities that can realize the step.",
    )
    expected_effects: tuple[LogicalEffect, ...] = Field(
        default_factory=tuple,
        description="Expected facts after successful execution.",
    )
    preserved_resources: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Resources the step should preserve when possible.",
    )


class RoutineContract(RoutineModel):
    """Logical definition of a bounded, revalidating policy routine."""

    routine_id: str = Field(description="Stable routine identity.")
    purpose: RoutinePurpose = Field(description="Typed tactical meaning of the routine.")
    description: str = Field(description="High-level goal pursued by the routine.")
    applicability: FactExpression = Field(description="Facts required to start the routine.")
    invariants: FactExpression = Field(description="Facts that must remain true while it runs.")
    completion: FactExpression = Field(description="Facts that establish completion.")
    steps: tuple[RoutineStepContract, ...] = Field(description="Ordered abstract routine steps.")
    revalidate_after: tuple[str, ...] = Field(
        description="Boundaries that require fresh subjective validation.",
    )
    interposes_before_action_tags: frozenset[ActionTag] = Field(
        default_factory=frozenset,
        description=(
            "Action meanings in an active routine before which this routine may "
            "start for the same retained target."
        ),
    )


class RoutinePlan(RoutineModel):
    """Pure proposal for one routine step in the current decision epoch."""

    routine_id: str = Field(description="Routine definition that produced the plan.")
    purpose: RoutinePurpose = Field(description="Typed tactical meaning inherited from the routine contract.")
    status: RoutinePlanStatus = Field(description="Whether a legal step was proposed.")
    step_id: Optional[str] = Field(default=None, description="Selected abstract step.")
    target_uuid: Optional[str] = Field(default=None, description="Subjective routine target UUID.")
    target_position: Optional[Position] = Field(default=None, description="Known routine target position.")
    selected_target_index: Optional[int] = Field(default=None, description="Target index inside the selected row.")
    proposal: Optional[PolicyProposal] = Field(default=None, description="Current-epoch legal proposal.")
    next_progress_on_success: Optional[RoutineProgress] = Field(
        default=None,
        description="Actor-scoped progress to store only after command acceptance.",
    )
    clear_progress_on_success: bool = Field(
        default=False,
        description="Whether acceptance completes and clears the actor routine.",
    )
    reason: str = Field(description="Traceable planning outcome.")


class RoutineRevalidation(RoutineModel):
    """Pure reconciliation of remembered progress with current subjective facts."""

    routine_id: str = Field(description="Routine definition being checked.")
    status: RoutineRevalidationStatus = Field(description="Revalidation outcome.")
    progress: Optional[RoutineProgress] = Field(
        default=None,
        description="Progress that remains valid after reconciliation.",
    )
    reason: str = Field(description="Traceable revalidation explanation.")


class RoutinePlanningDiagnostics(RoutineModel):
    """Bounded work counters collected across one decision's routine planning."""

    movement_endpoints: int = Field(default=0, ge=0)
    damage_capabilities: int = Field(default=0, ge=0)
    affordability_pair_evaluations: int = Field(default=0, ge=0)
    affordability_pair_cache_misses: int = Field(default=0, ge=0)
    replay_token_builds: int = Field(default=0, ge=0)
    line_of_sight_evaluations: int = Field(default=0, ge=0)
    line_of_sight_cache_hits: int = Field(default=0, ge=0)


@dataclass
class RoutinePlanningInstrumentation:
    """Low-overhead mutable counters used only while planning one decision."""

    affordability: AffordabilityWorkspace
    movement_endpoints: int = 0
    damage_capabilities: int = 0
    replay_token_builds: int = 0
    line_of_sight_evaluations: int = 0
    line_of_sight_cache_hits: int = 0
    line_of_sight_cache: Optional[dict[tuple[Position, Position], TruthValue]] = None

    def snapshot(self) -> RoutinePlanningDiagnostics:
        """Freeze the collected work counters for observational evidence."""
        return RoutinePlanningDiagnostics(
            movement_endpoints=self.movement_endpoints,
            damage_capabilities=self.damage_capabilities,
            affordability_pair_evaluations=self.affordability.pair_evaluations,
            affordability_pair_cache_misses=self.affordability.pair_cache_misses,
            replay_token_builds=self.replay_token_builds,
            line_of_sight_evaluations=self.line_of_sight_evaluations,
            line_of_sight_cache_hits=self.line_of_sight_cache_hits,
        )

    def known_line_of_sight(
        self,
        context: PolicyContext,
        origin: Position,
        target: Position,
        *,
        workspace: Optional[KnownLineOfSightWorkspace] = None,
    ) -> TruthValue:
        """Return decision-local cached LOS for one subjective geometry pair."""
        if self.line_of_sight_cache is None:
            self.line_of_sight_cache = {}
        key = (origin, target)
        cached = self.line_of_sight_cache.get(key)
        if cached is not None:
            self.line_of_sight_cache_hits += 1
            return cached
        self.line_of_sight_evaluations += 1
        value = known_line_of_sight(
            context.world,
            origin,
            target,
            workspace=workspace,
            vision_blocker_positions=(
                None if workspace is not None else context.facts.topology.vision_blocker_positions
            ),
        )
        self.line_of_sight_cache[key] = value
        return value


def _predicate(
    fact_id: str,
    expected_value: FactValue,
    comparison: ComparisonOperator = ComparisonOperator.EQUALS,
) -> FactExpression:
    """Build one routine fact predicate."""
    return FactExpression(
        operator=FactOperator.PREDICATE,
        predicate=FactPredicate(
            fact_id=fact_id,
            comparison=comparison,
            expected_value=expected_value,
        ),
    )


def _all(*operands: FactExpression) -> FactExpression:
    """Build a conjunction for routine contracts."""
    return FactExpression(operator=FactOperator.ALL, operands=operands)


APPROACH_OPEN_REASSESS = RoutineContract(
    routine_id="routine.approach_open_reassess",
    purpose=RoutinePurpose.SUBJECTIVE_DISCOVERY,
    description="Reach a known closed door, open it, and reconsider the newly revealed world.",
    applicability=_all(
        _predicate("actor.is_active", True),
        _predicate("visible_hostile.count", 0),
        _predicate("known_closed_door.count", 0, ComparisonOperator.GREATER_THAN),
    ),
    invariants=_all(
        _predicate("actor.is_active", True),
        _predicate("routine.target.known", True),
    ),
    completion=_predicate("routine.target.open", True),
    steps=(
        RoutineStepContract(
            step_id="approach",
            description="Use ordinary legal movement to make progress toward the target door.",
            preconditions=_predicate("route.to_routine_target.exists", True),
            accepted_action_tags=frozenset({ActionTag.MOVEMENT_VOLUNTARY}),
            expected_effects=(
                LogicalEffect(
                    fact_id="actor.distance_to_routine_target",
                    operation=EffectOperation.DECREASE,
                ),
            ),
            preserved_resources=("actions", "bonus_actions", "spell_slots", "concentration"),
        ),
        RoutineStepContract(
            step_id="extend_mobility",
            description="Extend movement only when ordinary movement cannot currently advance the routine.",
            preconditions=_predicate("routine.ordinary_movement_progress_available", False),
            accepted_action_tags=frozenset({ActionTag.MOBILITY_EXTEND}),
            expected_effects=(
                LogicalEffect(
                    fact_id="actor.movement_remaining",
                    operation=EffectOperation.INCREASE,
                ),
            ),
            preserved_resources=("bonus_actions", "spell_slots", "concentration"),
        ),
        RoutineStepContract(
            step_id="open",
            description="Execute a legal door-open affordance for the routine target.",
            preconditions=_predicate("routine.target.open_affordance_available", True),
            accepted_action_tags=frozenset({ActionTag.INTERACTION_DOOR_OPEN}),
            expected_effects=(
                LogicalEffect(
                    fact_id="routine.target.open",
                    operation=EffectOperation.SET,
                    value=True,
                ),
            ),
            preserved_resources=("actions", "bonus_actions", "spell_slots", "concentration"),
        ),
        RoutineStepContract(
            step_id="reassess",
            description="Consume the resulting subjective events before choosing another goal.",
            preconditions=_predicate("routine.target.open_command_accepted", True),
            expected_effects=(
                LogicalEffect(
                    fact_id="subjective.frontier",
                    operation=EffectOperation.INVALIDATE,
                ),
            ),
            preserved_resources=("all_remaining_resources",),
        ),
    ),
    revalidate_after=(
        "subjective_event",
        "decision_epoch",
        "command_result",
        "turn_transition",
    ),
)


ENABLE_THEN_ACT = RoutineContract(
    routine_id="routine.enable_then_act",
    purpose=RoutinePurpose.OFFENSIVE_ENABLEMENT,
    description="Use one legal enabler, revalidate, then resolve an abstract action goal from fresh rows.",
    applicability=_all(
        _predicate("actor.is_active", True),
        _predicate("visible_hostile.count", 0, ComparisonOperator.GREATER_THAN),
    ),
    invariants=_all(
        _predicate("actor.is_active", True),
        _predicate("routine.target.visible", True),
        _predicate("routine.same_turn", True),
    ),
    completion=_predicate("routine.semantic_goal.executed", True),
    steps=(
        RoutineStepContract(
            step_id="enable",
            description="Execute one legal action predicted to make the semantic goal available.",
            preconditions=_predicate("routine.enablers_used", 0),
            accepted_action_tags=frozenset({ActionTag.MOVEMENT_VOLUNTARY}),
            expected_effects=(
                LogicalEffect(
                    fact_id="routine.semantic_goal.legal",
                    operation=EffectOperation.SET,
                    value=True,
                ),
            ),
            preserved_resources=("required_followup_cost", "concentration"),
        ),
        RoutineStepContract(
            step_id="reassess",
            description="Inspect the fresh authoritative epoch after the bounded enabler.",
            preconditions=_predicate("routine.enable_command.accepted", True),
            expected_effects=(
                LogicalEffect(
                    fact_id="actor.affordance_set",
                    operation=EffectOperation.INVALIDATE,
                ),
            ),
            preserved_resources=("all_remaining_resources",),
        ),
        RoutineStepContract(
            step_id="act",
            description="Resolve the semantic goal against a newly issued legal row.",
            preconditions=_predicate("routine.semantic_goal.legal", True),
            accepted_action_tags=DIRECT_DAMAGE_TAGS,
            expected_effects=(
                LogicalEffect(
                    fact_id="routine.semantic_goal.executed",
                    operation=EffectOperation.SET,
                    value=True,
                ),
            ),
        ),
    ),
    revalidate_after=("decision_epoch", "command_result", "turn_transition"),
)


PURSUE_CAPABILITY = RoutineContract(
    routine_id="routine.pursue_capability",
    purpose=RoutinePurpose.OFFENSIVE_PURSUIT,
    description=(
        "Make monotonic, revalidated progress toward a visible target until an "
        "owned damage capability becomes legal."
    ),
    applicability=_all(
        _predicate("actor.is_active", True),
        _predicate("visible_hostile.count", 0, ComparisonOperator.GREATER_THAN),
        _predicate("owned_damage_capability.count", 0, ComparisonOperator.GREATER_THAN),
    ),
    invariants=_all(
        _predicate("actor.is_active", True),
        _predicate("routine.target.visible", True),
        _predicate("routine.target.alive", True),
    ),
    completion=_predicate("routine.semantic_goal.executed", True),
    steps=(
        RoutineStepContract(
            step_id="approach",
            description="Use ordinary legal movement that reduces the known route deficit.",
            preconditions=_predicate("routine.ordinary_movement_progress_available", True),
            accepted_action_tags=frozenset({ActionTag.MOVEMENT_VOLUNTARY}),
            expected_effects=(LogicalEffect(
                fact_id="actor.route_deficit_to_capability_envelope",
                operation=EffectOperation.DECREASE,
            ),),
            preserved_resources=("actions", "bonus_actions", "persistent_resources"),
        ),
        RoutineStepContract(
            step_id="extend_mobility",
            description=(
                "Use at most one typed mobility extension per turn after ordinary "
                "movement can no longer advance the routine."
            ),
            preconditions=_predicate("routine.ordinary_movement_progress_available", False),
            accepted_action_tags=frozenset({ActionTag.MOBILITY_EXTEND}),
            expected_effects=(LogicalEffect(
                fact_id="actor.movement_remaining",
                operation=EffectOperation.INCREASE,
            ),),
            preserved_resources=("persistent_resources", "concentration"),
        ),
        RoutineStepContract(
            step_id="yield_turn",
            description="Yield exhausted turn economy while retaining the semantic pursuit goal.",
            preconditions=_predicate("routine.progress_command_available", False),
            accepted_action_tags=frozenset({ActionTag.TURN_END}),
            expected_effects=(LogicalEffect(
                fact_id="actor.is_active",
                operation=EffectOperation.SET,
                value=False,
            ),),
            preserved_resources=("routine.semantic_goal",),
        ),
        RoutineStepContract(
            step_id="act",
            description="Resolve the retained damage goal from a fresh server-issued legal row.",
            preconditions=_predicate("routine.semantic_goal.legal", True),
            accepted_action_tags=DIRECT_DAMAGE_TAGS,
            expected_effects=(LogicalEffect(
                fact_id="routine.semantic_goal.executed",
                operation=EffectOperation.SET,
                value=True,
            ),),
        ),
    ),
    revalidate_after=(
        "subjective_event",
        "decision_epoch",
        "command_result",
        "turn_transition",
    ),
)


AUGMENT_THEN_ACT = RoutineContract(
    routine_id="routine.augment_then_act",
    purpose=RoutinePurpose.OFFENSIVE_AUGMENTATION,
    description=(
        "Apply one typed transient outcome augmentation, reassess, and execute "
        "the improved direct-pressure goal from a fresh authoritative row."
    ),
    applicability=_all(
        _predicate("actor.is_active", True),
        _predicate("visible_hostile.count", 0, ComparisonOperator.GREATER_THAN),
    ),
    invariants=_all(
        _predicate("actor.is_active", True),
        _predicate("routine.target.visible", True),
        _predicate("routine.same_turn", True),
    ),
    completion=_predicate("routine.semantic_goal.executed", True),
    steps=(
        RoutineStepContract(
            step_id="augment",
            description="Execute one setup whose typed projection improves a legal attack.",
            preconditions=_predicate("routine.projected_marginal_utility", 0, ComparisonOperator.GREATER_THAN),
            accepted_action_tags=frozenset({ActionTag.SETUP_SELF}),
            expected_effects=(LogicalEffect(
                fact_id="actor.outcome_profile",
                operation=EffectOperation.INVALIDATE,
            ),),
            preserved_resources=("projected_followup_cost", "concentration"),
        ),
        RoutineStepContract(
            step_id="reassess",
            description="Discard the projection and inspect the next authoritative epoch.",
            preconditions=_predicate("routine.augment_command.accepted", True),
            expected_effects=(LogicalEffect(
                fact_id="actor.affordance_set",
                operation=EffectOperation.INVALIDATE,
            ),),
        ),
        RoutineStepContract(
            step_id="act",
            description="Resolve the retained pressure goal against a fresh legal row.",
            preconditions=_predicate("routine.semantic_goal.legal", True),
            accepted_action_tags=DIRECT_DAMAGE_TAGS,
            expected_effects=(LogicalEffect(
                fact_id="routine.semantic_goal.executed",
                operation=EffectOperation.SET,
                value=True,
            ),),
        ),
    ),
    revalidate_after=("decision_epoch", "command_result", "turn_transition"),
    interposes_before_action_tags=DIRECT_DAMAGE_TAGS,
)


TRANSFORM_THEN_ACT = RoutineContract(
    routine_id="routine.transform_then_act",
    purpose=RoutinePurpose.CAPABILITY_TRANSFORMATION,
    description="Apply one typed capability rewrite, reassess, and use a fresh authoritative row.",
    applicability=_all(
        _predicate("actor.is_active", True),
        _predicate("visible_hostile.count", 0, ComparisonOperator.GREATER_THAN),
    ),
    invariants=_all(
        _predicate("actor.is_active", True),
        _predicate("routine.target.visible", True),
        _predicate("routine.same_turn", True),
    ),
    completion=_predicate("routine.semantic_goal.executed", True),
    steps=(
        RoutineStepContract(
            step_id="transform",
            description="Execute a legal action declaring a useful capability transformation.",
            preconditions=_predicate("routine.capability_projection.affordable", True),
            accepted_action_tags=frozenset({ActionTag.CAPABILITY_TRANSFORM}),
            expected_effects=(LogicalEffect(
                fact_id="actor.capability_set",
                operation=EffectOperation.INVALIDATE,
            ),),
            preserved_resources=("projected_followup_cost", "concentration"),
        ),
        RoutineStepContract(
            step_id="reassess",
            description="Discard the projection and inspect the next authoritative epoch.",
            preconditions=_predicate("routine.transform_command.accepted", True),
            expected_effects=(LogicalEffect(
                fact_id="actor.affordance_set",
                operation=EffectOperation.INVALIDATE,
            ),),
        ),
        RoutineStepContract(
            step_id="act",
            description="Resolve the retained semantic goal against a fresh legal row.",
            preconditions=_predicate("routine.semantic_goal.legal", True),
            accepted_action_tags=DIRECT_DAMAGE_TAGS,
            expected_effects=(LogicalEffect(
                fact_id="routine.semantic_goal.executed",
                operation=EffectOperation.SET,
                value=True,
            ),),
        ),
    ),
    revalidate_after=("decision_epoch", "command_result", "turn_transition"),
)


def revalidate_approach_open_reassess(
    context: PolicyContext,
    progress: Optional[RoutineProgress],
    _candidates: Optional[PolicyCandidateSet] = None,
) -> RoutineRevalidation:
    """Reconcile remembered door progress with one fresh subjective epoch."""
    context.validate_alignment()
    if progress is None:
        return RoutineRevalidation(
            routine_id=APPROACH_OPEN_REASSESS.routine_id,
            status=RoutineRevalidationStatus.IDLE,
            progress=None,
            reason="no_active_routine",
        )
    if progress.routine_id != APPROACH_OPEN_REASSESS.routine_id:
        return RoutineRevalidation(
            routine_id=APPROACH_OPEN_REASSESS.routine_id,
            status=RoutineRevalidationStatus.VALID,
            progress=progress,
            reason="different_routine_owned_by_actor",
        )
    if context.facts.contacts.visible_hostile_uuids:
        return RoutineRevalidation(
            routine_id=APPROACH_OPEN_REASSESS.routine_id,
            status=RoutineRevalidationStatus.INTERRUPTED,
            progress=None,
            reason="visible_hostile_requires_reactive_replanning",
        )
    if progress.target_uuid is None:
        return RoutineRevalidation(
            routine_id=APPROACH_OPEN_REASSESS.routine_id,
            status=RoutineRevalidationStatus.INVALIDATED,
            progress=None,
            reason="routine_target_identity_missing",
        )
    target = context.world.known_objects.get(progress.target_uuid)
    if target is None or target.position is None:
        return RoutineRevalidation(
            routine_id=APPROACH_OPEN_REASSESS.routine_id,
            status=RoutineRevalidationStatus.INVALIDATED,
            progress=None,
            reason="routine_target_no_longer_subjectively_known",
        )
    if progress.target_uuid in context.facts.objects.open_door_uuids:
        return RoutineRevalidation(
            routine_id=APPROACH_OPEN_REASSESS.routine_id,
            status=RoutineRevalidationStatus.COMPLETED,
            progress=None,
            reason="door_opened_reassess_complete",
        )
    if progress.target_uuid not in context.facts.objects.closed_door_uuids:
        return RoutineRevalidation(
            routine_id=APPROACH_OPEN_REASSESS.routine_id,
            status=RoutineRevalidationStatus.INVALIDATED,
            progress=None,
            reason="routine_target_state_became_unknown",
        )
    next_step = "open" if _open_door_row(context, progress.target_uuid) is not None else "approach"
    status = (
        RoutineRevalidationStatus.ADVANCED
        if next_step != progress.step_id
        else RoutineRevalidationStatus.VALID
    )
    return RoutineRevalidation(
        routine_id=APPROACH_OPEN_REASSESS.routine_id,
        status=status,
        progress=progress.model_copy(
            update={
                "step_id": next_step,
                "target_position": target.position,
            }
        ),
        reason=f"routine_target_closed_next_step:{next_step}",
    )


def apply_routine_revalidation(
    memory: ActorPolicyMemory,
    revalidation: RoutineRevalidation,
) -> None:
    """Apply a pure revalidation result to actor-owned control memory."""
    memory.last_routine_revalidation_status = revalidation.status.value
    memory.last_routine_revalidation_reason = revalidation.reason
    if (
        memory.active_routine is not None
        and memory.active_routine.routine_id != revalidation.routine_id
        and revalidation.progress is memory.active_routine
    ):
        return
    memory.active_routine = revalidation.progress


def apply_routine_plan_result(
    memory: ActorPolicyMemory,
    plan: Optional[RoutinePlan],
    *,
    completed: bool,
) -> None:
    """Advance actor-owned progress only after authoritative completion."""
    if not completed or plan is None:
        return
    if plan.clear_progress_on_success:
        memory.active_routine = None
        return
    if plan.next_progress_on_success is None:
        return
    memory.active_routine = plan.next_progress_on_success


def revalidate_enable_then_act(
    context: PolicyContext,
    progress: Optional[RoutineProgress],
    candidates: Optional[PolicyCandidateSet] = None,
) -> RoutineRevalidation:
    """Reconcile one accepted enabler against the next subjective epoch."""
    context.validate_alignment()
    if progress is None:
        return RoutineRevalidation(
            routine_id=ENABLE_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.IDLE,
            reason="no_active_routine",
        )
    if progress.routine_id != ENABLE_THEN_ACT.routine_id:
        return RoutineRevalidation(
            routine_id=ENABLE_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.VALID,
            progress=progress,
            reason="different_routine_owned_by_actor",
        )
    epoch = context.world.current_epoch
    if epoch is None or not context.facts.actor.is_my_turn:
        return RoutineRevalidation(
            routine_id=ENABLE_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.INTERRUPTED,
            reason="controlled_actor_inactive",
        )
    if (
        progress.started_round_number != epoch.round_number
        or progress.started_turn_index != epoch.turn_index
    ):
        return RoutineRevalidation(
            routine_id=ENABLE_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.INTERRUPTED,
            reason="same_turn_routine_expired",
        )
    if progress.goal is None or progress.enablers_used != 1:
        return RoutineRevalidation(
            routine_id=ENABLE_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.INVALIDATED,
            reason="bounded_semantic_goal_missing_or_invalid",
        )
    target = context.world.known_entities.get(progress.goal.target_uuid)
    if (
        target is None
        or target.knowledge_state.value != "visible"
        or target.is_dead is True
    ):
        return RoutineRevalidation(
            routine_id=ENABLE_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.INTERRUPTED,
            reason="semantic_goal_target_no_longer_visible_and_alive",
        )
    if _matching_goal_proposal(context, progress.goal, candidates) is None:
        return RoutineRevalidation(
            routine_id=ENABLE_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.EXHAUSTED,
            progress=progress.model_copy(update={"step_id": "reassess"}),
            reason="bounded_enabler_exhausted_without_legal_followup",
        )
    return RoutineRevalidation(
        routine_id=ENABLE_THEN_ACT.routine_id,
        status=RoutineRevalidationStatus.ADVANCED,
        progress=progress.model_copy(update={"step_id": "act"}),
        reason="fresh_epoch_contains_matching_legal_followup",
    )


def plan_enable_then_act(
    context: PolicyContext,
    progress: Optional[RoutineProgress],
    candidates: Optional[PolicyCandidateSet] = None,
    instrumentation: Optional[RoutinePlanningInstrumentation] = None,
) -> RoutinePlan:
    """Propose one enabler or resolve its semantic goal from fresh legal rows."""
    context.validate_alignment()
    if progress is not None:
        if progress.routine_id != ENABLE_THEN_ACT.routine_id or progress.goal is None:
            return _no_plan(
                RoutinePlanStatus.NOT_APPLICABLE,
                "different_active_routine",
                routine_id=ENABLE_THEN_ACT.routine_id,
            )
        followup = _matching_goal_proposal(context, progress.goal, candidates)
        if followup is None:
            return _no_plan(
                RoutinePlanStatus.BLOCKED,
                "semantic_followup_not_legal_after_single_enabler",
                routine_id=ENABLE_THEN_ACT.routine_id,
            )
        return RoutinePlan(
            routine_id=ENABLE_THEN_ACT.routine_id,
            purpose=ENABLE_THEN_ACT.purpose,
            status=RoutinePlanStatus.PROPOSED,
            step_id="act",
            target_uuid=progress.goal.target_uuid,
            target_position=progress.target_position,
            proposal=followup.model_copy(
                update={
                    "source_node": "Pressure/EnableThenAct/Act",
                    "reason": "fresh legal row satisfies retained semantic goal",
                }
            ),
            clear_progress_on_success=True,
            reason="resolve_fresh_semantic_followup",
        )
    return _plan_damage_enabling_movement(context, candidates, instrumentation)


@dataclass(frozen=True)
class _PursuitGoalOption:
    """One subjective target and owned capability envelope worth pursuing."""

    capability: ActionCapability
    target_uuid: str
    target_position: Position
    goal_tags: frozenset[ActionTag]
    maximum_range_feet: int
    replay_key: tuple[str, str]


def revalidate_pursue_capability(
    context: PolicyContext,
    progress: Optional[RoutineProgress],
    candidates: Optional[PolicyCandidateSet] = None,
) -> RoutineRevalidation:
    """Reconcile a multi-turn capability pursuit with fresh subjective truth."""
    context.validate_alignment()
    if progress is None:
        return RoutineRevalidation(
            routine_id=PURSUE_CAPABILITY.routine_id,
            status=RoutineRevalidationStatus.IDLE,
            reason="no_active_routine",
        )
    if progress.routine_id != PURSUE_CAPABILITY.routine_id:
        return RoutineRevalidation(
            routine_id=PURSUE_CAPABILITY.routine_id,
            status=RoutineRevalidationStatus.VALID,
            progress=progress,
            reason="different_routine_owned_by_actor",
        )
    epoch = context.world.current_epoch
    if epoch is None or not context.facts.actor.is_my_turn:
        return RoutineRevalidation(
            routine_id=PURSUE_CAPABILITY.routine_id,
            status=RoutineRevalidationStatus.INTERRUPTED,
            reason="controlled_actor_inactive",
        )
    if progress.goal is None or progress.target_uuid is None:
        return RoutineRevalidation(
            routine_id=PURSUE_CAPABILITY.routine_id,
            status=RoutineRevalidationStatus.INVALIDATED,
            reason="pursuit_semantic_goal_missing",
        )
    target = context.world.known_entities.get(progress.target_uuid)
    if target is None or target.is_dead is True:
        return RoutineRevalidation(
            routine_id=PURSUE_CAPABILITY.routine_id,
            status=RoutineRevalidationStatus.COMPLETED,
            reason="pursuit_target_dead_or_absent",
        )
    if (
        progress.target_uuid not in context.facts.contacts.visible_hostile_uuids
        or target.position is None
    ):
        return RoutineRevalidation(
            routine_id=PURSUE_CAPABILITY.routine_id,
            status=RoutineRevalidationStatus.INTERRUPTED,
            reason="pursuit_target_no_longer_visible",
        )
    actor_position = context.facts.actor.position
    if actor_position is None:
        return RoutineRevalidation(
            routine_id=PURSUE_CAPABILITY.routine_id,
            status=RoutineRevalidationStatus.INVALIDATED,
            reason="pursuit_actor_position_unknown",
        )
    extension_count = progress.mobility_extensions_used_this_turn
    if (
        progress.mobility_extension_round_number != epoch.round_number
        or progress.mobility_extension_turn_index != epoch.turn_index
    ):
        extension_count = 0
    next_progress = progress.model_copy(update={
        "target_position": target.position,
        "last_target_distance_feet": grid_distance_feet(
            actor_position,
            target.position,
        ),
        "mobility_extensions_used_this_turn": extension_count,
        "mobility_extension_round_number": epoch.round_number,
        "mobility_extension_turn_index": epoch.turn_index,
    })
    if _matching_goal_proposal(context, progress.goal, candidates) is not None:
        return RoutineRevalidation(
            routine_id=PURSUE_CAPABILITY.routine_id,
            status=RoutineRevalidationStatus.ADVANCED,
            progress=next_progress.model_copy(update={"step_id": "act"}),
            reason="fresh_epoch_contains_pursued_damage_row",
        )
    return RoutineRevalidation(
        routine_id=PURSUE_CAPABILITY.routine_id,
        status=RoutineRevalidationStatus.VALID,
        progress=next_progress.model_copy(update={"step_id": "approach"}),
        reason="visible_target_still_outside_legal_capability_envelope",
    )


def plan_pursue_capability(
    context: PolicyContext,
    progress: Optional[RoutineProgress],
    candidates: Optional[PolicyCandidateSet] = None,
    _instrumentation: Optional[RoutinePlanningInstrumentation] = None,
) -> RoutinePlan:
    """Choose one monotonic pursuit step from the current authoritative epoch."""
    context.validate_alignment()
    epoch = context.world.current_epoch
    if (
        epoch is None
        or not context.facts.actor.is_my_turn
        or context.facts.actor.position is None
        or not context.facts.contacts.visible_hostile_uuids
    ):
        return _no_plan(
            RoutinePlanStatus.NOT_APPLICABLE,
            "active_actor_or_visible_hostile_missing",
            routine_id=PURSUE_CAPABILITY.routine_id,
        )
    candidate_set = candidates or build_policy_candidate_set(context)
    if progress is None and candidate_set.direct_damage:
        return _no_plan(
            RoutinePlanStatus.NOT_APPLICABLE,
            "direct_damage_already_legal",
            routine_id=PURSUE_CAPABILITY.routine_id,
        )
    if progress is not None:
        if progress.routine_id != PURSUE_CAPABILITY.routine_id or progress.goal is None:
            return _no_plan(
                RoutinePlanStatus.NOT_APPLICABLE,
                "different_active_routine",
                routine_id=PURSUE_CAPABILITY.routine_id,
            )
        followup = _matching_goal_proposal(context, progress.goal, candidate_set)
        if followup is not None:
            return RoutinePlan(
                routine_id=PURSUE_CAPABILITY.routine_id,
                purpose=PURSUE_CAPABILITY.purpose,
                status=RoutinePlanStatus.PROPOSED,
                step_id="act",
                target_uuid=progress.target_uuid,
                target_position=progress.target_position,
                proposal=followup.model_copy(update={
                    "source_node": "Pressure/PursueCapability/Act",
                    "reason": "fresh legal row satisfies pursued capability goal",
                }),
                clear_progress_on_success=True,
                reason="resolve_fresh_pursued_damage_row",
            )

    options = _pursuit_goal_options(context, progress)
    route_cost_cache: dict[
        tuple[Position, int, bool],
        dict[Position, int],
    ] = {}
    movement_steps = [
        step
        for option in options
        for step in [
            _pursuit_movement_step(context, option, route_cost_cache, _instrumentation)
        ]
        if step is not None
    ]
    if movement_steps:
        _, row, target, option = min(movement_steps, key=lambda step: step[0])
        return _pursuit_execute_plan(
            context,
            progress,
            option,
            row,
            target,
            step_id="approach",
            source_node="Pressure/PursueCapability/Approach",
            reason="ordinary movement reduces the known capability route deficit",
            score=65.0,
        )

    mobility_options = [
        (option.replay_key, row, option)
        for option in options
        for row in [
            _pursuit_mobility_extension_row(
                context,
                progress,
                option,
                route_cost_cache,
                _instrumentation,
            )
        ]
        if row is not None
    ]
    if mobility_options:
        _, row, option = min(mobility_options, key=lambda item: item[0])
        target = row.targets[0] if row.targets else ActionTarget(index=0)
        return _pursuit_execute_plan(
            context,
            progress,
            option,
            row,
            target,
            step_id="extend_mobility",
            source_node="Pressure/PursueCapability/ExtendMobility",
            reason="ordinary movement is exhausted and a known route remains",
            score=55.0,
        )

    if progress is None:
        return _no_plan(
            RoutinePlanStatus.BLOCKED,
            "no_subjectively_known_pursuit_progress",
            routine_id=PURSUE_CAPABILITY.routine_id,
        )
    return RoutinePlan(
        routine_id=PURSUE_CAPABILITY.routine_id,
        purpose=PURSUE_CAPABILITY.purpose,
        status=RoutinePlanStatus.PROPOSED,
        step_id="yield_turn",
        target_uuid=progress.target_uuid,
        target_position=progress.target_position,
        proposal=PolicyProposal(
            intent=EndTurnIntent(),
            goal=PolicyGoal.ROUTINE,
            source_node="Pressure/PursueCapability/YieldTurn",
            reason="turn economy cannot make further pursuit progress",
            score=1.0,
            replay_key=(PURSUE_CAPABILITY.routine_id, "yield_turn"),
            semantic_tags=frozenset({ActionTag.TURN_END}),
        ),
        next_progress_on_success=progress.model_copy(update={"step_id": "approach"}),
        reason="yield_exhausted_turn_and_revalidate_next_turn",
    )


def _pursuit_goal_options(
    context: PolicyContext,
    progress: Optional[RoutineProgress],
) -> tuple[_PursuitGoalOption, ...]:
    """Return stable visible-target and persistent damage-envelope pairs."""
    epoch = context.world.current_epoch
    if epoch is None:
        return tuple()
    target_uuids = (
        (progress.target_uuid,)
        if progress is not None and progress.target_uuid is not None
        else context.facts.contacts.visible_hostile_uuids
    )
    options: dict[
        tuple[str, int, bool, frozenset[ActionTag]],
        _PursuitGoalOption,
    ] = {}
    for capability in context.facts.capabilities.rows:
        semantics = context.facts.capabilities.semantics_by_capability_id.get(
            capability.capability_id
        )
        maximum_range = capability.long_range_feet or capability.normal_range_feet
        if (
            semantics is None
            or ActionTag.DAMAGE_SINGLE_TARGET not in semantics.tags
            or capability.valid_target_filter not in {"enemies", "all"}
            or maximum_range is None
            or not capability_is_turn_refreshable(epoch.economy, capability)
        ):
            continue
        goal_tags = frozenset({ActionTag.DAMAGE_SINGLE_TARGET})
        if (
            progress is not None
            and progress.goal is not None
            and not progress.goal.required_tags.issubset(semantics.tags)
        ):
            continue
        capability_key = _capability_replay_token(capability)
        for target_uuid in target_uuids:
            if target_uuid is None:
                continue
            target = context.world.known_entities.get(target_uuid)
            if (
                target is None
                or target.position is None
                or target.is_dead is True
                or target_uuid not in context.facts.contacts.visible_hostile_uuids
            ):
                continue
            option = _PursuitGoalOption(
                capability=capability,
                target_uuid=target_uuid,
                target_position=target.position,
                goal_tags=goal_tags,
                maximum_range_feet=maximum_range,
                replay_key=(
                    capability_key,
                    entity_fact_replay_token(target),
                ),
            )
            envelope_key = (
                target_uuid,
                maximum_range,
                capability.requires_line_of_sight,
                goal_tags,
            )
            current = options.get(envelope_key)
            if current is None or option.replay_key < current.replay_key:
                options[envelope_key] = option
    return tuple(sorted(options.values(), key=lambda option: option.replay_key))


def _pursuit_movement_step(
    context: PolicyContext,
    option: _PursuitGoalOption,
    route_cost_cache: dict[
        tuple[Position, int, bool],
        dict[Position, int],
    ],
    instrumentation: Optional[RoutinePlanningInstrumentation],
) -> Optional[
    tuple[
        tuple[int, int, int, float, int, str, str, int, tuple[str, str]],
        ActionAffordance,
        ActionTarget,
        _PursuitGoalOption,
    ]
]:
    """Return the best legal ordinary movement that reduces pursuit deficit."""
    epoch = context.world.current_epoch
    actor_position = context.facts.actor.position
    if epoch is None or actor_position is None:
        return None
    route_costs = _cached_capability_envelope_route_costs(
        context,
        option,
        route_cost_cache,
        instrumentation,
    )
    actor_route_cost = route_costs.get(actor_position)
    actor_distance_deficit = max(
        0,
        grid_distance_feet(actor_position, option.target_position)
        - option.maximum_range_feet,
    )
    candidates: list[
        tuple[
            tuple[int, int, int, float, int, str, str, int, tuple[str, str]],
            ActionAffordance,
            ActionTarget,
            _PursuitGoalOption,
        ]
    ] = []
    for row_id in context.facts.affordances.row_ids_by_tag.get(
        ActionTag.MOVEMENT_VOLUNTARY,
        tuple(),
    ):
        row = context.facts.affordances.by_id.get(row_id)
        if (
            row is None
            or not row.can_afford
            or not context.execution_constraints.allows(row)
            or action_economy_opportunity_cost(row.cost) > 0.0
        ):
            continue
        for target in row.targets:
            if target.position is None or target.position == actor_position:
                continue
            movement_cost = (
                target.safe_path_cost
                if target.safe_path_cost is not None
                else target.path_cost
            )
            if movement_cost is None or movement_cost > epoch.economy.movement_remaining:
                continue
            endpoint_route_cost = route_costs.get(target.position)
            endpoint_distance_deficit = max(
                0,
                grid_distance_feet(target.position, option.target_position)
                - option.maximum_range_feet,
            )
            if actor_route_cost is not None and endpoint_route_cost is not None:
                if endpoint_route_cost >= actor_route_cost:
                    continue
                route_rank = endpoint_route_cost
            elif endpoint_distance_deficit < actor_distance_deficit:
                route_rank = endpoint_distance_deficit
            else:
                continue
            unsafe = int(target.is_path_hazardous and not target.safe_path)
            score = (
                unsafe,
                route_rank,
                endpoint_distance_deficit,
                action_economy_opportunity_cost(row.cost),
                movement_cost,
                row.semantic_key,
                position_replay_token(target.position),
                target.index,
                option.replay_key,
            )
            candidates.append((score, row, target, option))
    return min(candidates, key=lambda item: item[0]) if candidates else None


def _pursuit_mobility_extension_row(
    context: PolicyContext,
    progress: Optional[RoutineProgress],
    option: _PursuitGoalOption,
    route_cost_cache: dict[
        tuple[Position, int, bool],
        dict[Position, int],
    ],
    instrumentation: Optional[RoutinePlanningInstrumentation],
) -> Optional[ActionAffordance]:
    """Return one typed extension only when a known route exceeds current movement."""
    epoch = context.world.current_epoch
    actor_position = context.facts.actor.position
    if epoch is None or actor_position is None:
        return None
    used = progress.mobility_extensions_used_this_turn if progress is not None else 0
    if used >= 1:
        return None
    route_costs = _cached_capability_envelope_route_costs(
        context,
        option,
        route_cost_cache,
        instrumentation,
    )
    route_cost = route_costs.get(actor_position)
    if route_cost is None or route_cost <= epoch.economy.movement_remaining:
        return None
    rows = [
        row
        for row_id in context.facts.affordances.row_ids_by_tag.get(
            ActionTag.MOBILITY_EXTEND,
            tuple(),
        )
        for row in [context.facts.affordances.by_id.get(row_id)]
        if (
            row is not None
            and row.can_afford
            and context.execution_constraints.allows(row)
        )
    ]
    return min(
        rows,
        key=lambda row: (
            action_economy_opportunity_cost(row.cost),
            row.semantic_key,
            row.row_id,
        ),
    ) if rows else None


def _cached_capability_envelope_route_costs(
    context: PolicyContext,
    option: _PursuitGoalOption,
    cache: dict[
        tuple[Position, int, bool],
        dict[Position, int],
    ],
    instrumentation: Optional[RoutinePlanningInstrumentation],
) -> dict[Position, int]:
    """Reuse one subjective route field for equivalent capability envelopes."""
    key = (
        option.target_position,
        option.maximum_range_feet,
        option.capability.requires_line_of_sight,
    )
    route_costs = cache.get(key)
    if route_costs is None:
        route_costs = _route_costs_to_capability_envelope(
            context,
            option.target_position,
            option.maximum_range_feet,
            requires_line_of_sight=option.capability.requires_line_of_sight,
            instrumentation=instrumentation,
        )
        cache[key] = route_costs
    return route_costs


def _pursuit_execute_plan(
    context: PolicyContext,
    progress: Optional[RoutineProgress],
    option: _PursuitGoalOption,
    row: ActionAffordance,
    target: ActionTarget,
    *,
    step_id: str,
    source_node: str,
    reason: str,
    score: float,
) -> RoutinePlan:
    """Build one acceptance-gated pursuit command and semantic continuation."""
    epoch = context.world.current_epoch
    actor_position = context.facts.actor.position
    if epoch is None or actor_position is None:
        return _no_plan(
            RoutinePlanStatus.NOT_APPLICABLE,
            "pursuit_epoch_or_actor_missing",
            routine_id=PURSUE_CAPABILITY.routine_id,
        )
    semantics = context.facts.affordances.semantics_by_row_id[row.row_id]
    next_actor_position = (
        target.position
        if step_id == "approach" and target.position is not None
        else actor_position
    )
    extension_count = progress.mobility_extensions_used_this_turn if progress is not None else 0
    if step_id == "extend_mobility":
        extension_count += 1
    goal = (
        progress.goal
        if progress is not None and progress.goal is not None
        else SemanticActionGoal(
            required_tags=option.goal_tags,
            target_uuid=option.target_uuid,
        )
    )
    next_progress = RoutineProgress(
        routine_id=PURSUE_CAPABILITY.routine_id,
        step_id="approach",
        started_epoch_index=(
            progress.started_epoch_index if progress is not None else epoch.epoch_index
        ),
        target_uuid=option.target_uuid,
        target_position=option.target_position,
        goal=goal,
        enablers_used=(progress.enablers_used if progress is not None else 0) + 1,
        started_round_number=(
            progress.started_round_number if progress is not None else epoch.round_number
        ),
        started_turn_index=(
            progress.started_turn_index if progress is not None else epoch.turn_index
        ),
        last_target_distance_feet=grid_distance_feet(
            next_actor_position,
            option.target_position,
        ),
        mobility_extensions_used_this_turn=extension_count,
        mobility_extension_round_number=epoch.round_number,
        mobility_extension_turn_index=epoch.turn_index,
    )
    proposal = PolicyProposal(
        intent=ExecuteIntent(row_id=row.row_id, prefer_safe=True),
        goal=PolicyGoal.ROUTINE,
        source_node=source_node,
        reason=reason,
        score=score,
        replay_key=(
            row.semantic_key,
            position_replay_token(target.position),
            *option.replay_key,
        ),
        utility_components=(UtilityComponent(
            name="pursuit_route_progress",
            raw_value=1.0,
            weight=score,
            contribution=score,
            reason="typed routine step advances a visible-target capability goal",
        ),),
        semantic_tags=semantics.tags,
    )
    return RoutinePlan(
        routine_id=PURSUE_CAPABILITY.routine_id,
        purpose=PURSUE_CAPABILITY.purpose,
        status=RoutinePlanStatus.PROPOSED,
        step_id=step_id,
        target_uuid=option.target_uuid,
        target_position=option.target_position,
        selected_target_index=target.index,
        proposal=proposal,
        next_progress_on_success=next_progress,
        reason=reason,
    )


def _route_costs_to_capability_envelope(
    context: PolicyContext,
    target_position: Position,
    maximum_range_feet: int,
    *,
    requires_line_of_sight: bool,
    instrumentation: Optional[RoutinePlanningInstrumentation] = None,
) -> dict[Position, int]:
    """Return subjective safe-route costs to a damage capability envelope."""
    tiles = {
        tile.position: tile
        for tile in context.world.known_tiles.values()
        if tile.walkable is True
    }
    if not tiles:
        return {}
    line_workspace = (
        KnownLineOfSightWorkspace.from_world(
            context.world,
            vision_blocker_positions=(
                context.facts.topology.vision_blocker_positions
            ),
        )
        if requires_line_of_sight
        else None
    )
    goals: list[Position] = []
    for position in tiles:
        if (
            position == target_position
            or grid_distance_feet(position, target_position) > maximum_range_feet
        ):
            continue
        if line_workspace is not None:
            if instrumentation is not None:
                line = instrumentation.known_line_of_sight(
                    context,
                    position,
                    target_position,
                    workspace=line_workspace,
                )
            else:
                line = known_line_of_sight(
                    context.world,
                    position,
                    target_position,
                    workspace=line_workspace,
                )
            if line is TruthValue.FALSE:
                continue
        goals.append(position)
    if not goals:
        return {}
    costs: dict[Position, int] = {position: 0 for position in goals}
    heap: list[tuple[int, Position]] = [(0, position) for position in goals]
    heapq.heapify(heap)
    while heap:
        cost, position = heapq.heappop(heap)
        if costs[position] != cost:
            continue
        for neighbor in _neighbors(position):
            tile = tiles.get(neighbor)
            if tile is None:
                continue
            step_cost = max(1, tile.walking_cost or 5)
            if tile.is_hazardous is True:
                step_cost += 100
            next_cost = cost + step_cost
            if next_cost < costs.get(neighbor, 999_999):
                costs[neighbor] = next_cost
                heapq.heappush(heap, (next_cost, neighbor))
    return costs


def revalidate_augment_then_act(
    context: PolicyContext,
    progress: Optional[RoutineProgress],
    candidates: Optional[PolicyCandidateSet] = None,
) -> RoutineRevalidation:
    """Reconcile an accepted transient augmentation with its fresh epoch."""
    context.validate_alignment()
    if progress is None:
        return RoutineRevalidation(
            routine_id=AUGMENT_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.IDLE,
            reason="no_active_routine",
        )
    if progress.routine_id != AUGMENT_THEN_ACT.routine_id:
        return RoutineRevalidation(
            routine_id=AUGMENT_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.VALID,
            progress=progress,
            reason="different_routine_owned_by_actor",
        )
    epoch = context.world.current_epoch
    if epoch is None or not context.facts.actor.is_my_turn:
        return RoutineRevalidation(
            routine_id=AUGMENT_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.INTERRUPTED,
            reason="controlled_actor_inactive",
        )
    if (
        progress.started_round_number != epoch.round_number
        or progress.started_turn_index != epoch.turn_index
    ):
        return RoutineRevalidation(
            routine_id=AUGMENT_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.INTERRUPTED,
            reason="same_turn_augmentation_expired",
        )
    if progress.goal is None or progress.enablers_used != 1:
        return RoutineRevalidation(
            routine_id=AUGMENT_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.INVALIDATED,
            reason="bounded_augmentation_goal_missing_or_invalid",
        )
    target = context.world.known_entities.get(progress.goal.target_uuid)
    if target is None or target.knowledge_state.value != "visible" or target.is_dead is True:
        return RoutineRevalidation(
            routine_id=AUGMENT_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.INTERRUPTED,
            reason="augmentation_goal_target_no_longer_visible_and_alive",
        )
    if _matching_goal_proposal(context, progress.goal, candidates) is None:
        return RoutineRevalidation(
            routine_id=AUGMENT_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.INVALIDATED,
            reason="authoritative_epoch_did_not_contain_augmented_followup",
        )
    return RoutineRevalidation(
        routine_id=AUGMENT_THEN_ACT.routine_id,
        status=RoutineRevalidationStatus.ADVANCED,
        progress=progress.model_copy(update={"step_id": "act"}),
        reason="fresh_epoch_contains_augmented_legal_followup",
    )


def plan_augment_then_act(
    context: PolicyContext,
    progress: Optional[RoutineProgress],
    candidates: Optional[PolicyCandidateSet] = None,
    instrumentation: Optional[RoutinePlanningInstrumentation] = None,
) -> RoutinePlan:
    """Propose one useful augmentation or resolve its fresh follow-up row."""
    context.validate_alignment()
    if progress is not None:
        if progress.routine_id != AUGMENT_THEN_ACT.routine_id or progress.goal is None:
            return _no_plan(
                RoutinePlanStatus.NOT_APPLICABLE,
                "different_active_routine",
                routine_id=AUGMENT_THEN_ACT.routine_id,
            )
        followup = _matching_goal_proposal(context, progress.goal, candidates)
        if followup is None:
            return _no_plan(
                RoutinePlanStatus.BLOCKED,
                "augmented_followup_not_legal_in_authoritative_epoch",
                routine_id=AUGMENT_THEN_ACT.routine_id,
            )
        return RoutinePlan(
            routine_id=AUGMENT_THEN_ACT.routine_id,
            purpose=AUGMENT_THEN_ACT.purpose,
            status=RoutinePlanStatus.PROPOSED,
            step_id="act",
            target_uuid=progress.goal.target_uuid,
            target_position=progress.target_position,
            proposal=followup.model_copy(update={
                "source_node": "Pressure/AugmentThenAct/Act",
                "reason": "fresh legal row satisfies retained augmented pressure goal",
            }),
            clear_progress_on_success=True,
            reason="resolve_fresh_augmented_followup",
        )
    return _plan_outcome_augmentation(context, candidates, instrumentation)


def revalidate_transform_then_act(
    context: PolicyContext,
    progress: Optional[RoutineProgress],
    candidates: Optional[PolicyCandidateSet] = None,
) -> RoutineRevalidation:
    """Reconcile an accepted transformation against the next subjective epoch."""
    context.validate_alignment()
    if progress is None:
        return RoutineRevalidation(
            routine_id=TRANSFORM_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.IDLE,
            reason="no_active_routine",
        )
    if progress.routine_id != TRANSFORM_THEN_ACT.routine_id:
        return RoutineRevalidation(
            routine_id=TRANSFORM_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.VALID,
            progress=progress,
            reason="different_routine_owned_by_actor",
        )
    epoch = context.world.current_epoch
    if epoch is None or not context.facts.actor.is_my_turn:
        return RoutineRevalidation(
            routine_id=TRANSFORM_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.INTERRUPTED,
            reason="controlled_actor_inactive",
        )
    if (
        progress.started_round_number != epoch.round_number
        or progress.started_turn_index != epoch.turn_index
    ):
        return RoutineRevalidation(
            routine_id=TRANSFORM_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.INTERRUPTED,
            reason="same_turn_transformation_expired",
        )
    if progress.goal is None or progress.enablers_used != 1:
        return RoutineRevalidation(
            routine_id=TRANSFORM_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.INVALIDATED,
            reason="bounded_transformation_goal_missing_or_invalid",
        )
    target = context.world.known_entities.get(progress.goal.target_uuid)
    if target is None or target.knowledge_state.value != "visible" or target.is_dead is True:
        return RoutineRevalidation(
            routine_id=TRANSFORM_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.INTERRUPTED,
            reason="transformation_goal_target_no_longer_visible_and_alive",
        )
    if _matching_goal_proposal(context, progress.goal, candidates) is None:
        return RoutineRevalidation(
            routine_id=TRANSFORM_THEN_ACT.routine_id,
            status=RoutineRevalidationStatus.INVALIDATED,
            reason="authoritative_epoch_did_not_contain_transformed_followup",
        )
    return RoutineRevalidation(
        routine_id=TRANSFORM_THEN_ACT.routine_id,
        status=RoutineRevalidationStatus.ADVANCED,
        progress=progress.model_copy(update={"step_id": "act"}),
        reason="fresh_epoch_contains_transformed_legal_followup",
    )


def plan_transform_then_act(
    context: PolicyContext,
    progress: Optional[RoutineProgress],
    candidates: Optional[PolicyCandidateSet] = None,
    instrumentation: Optional[RoutinePlanningInstrumentation] = None,
) -> RoutinePlan:
    """Propose one typed transformation or resolve its fresh semantic follow-up."""
    context.validate_alignment()
    if progress is not None:
        if progress.routine_id != TRANSFORM_THEN_ACT.routine_id or progress.goal is None:
            return _no_plan(
                RoutinePlanStatus.NOT_APPLICABLE,
                "different_active_routine",
                routine_id=TRANSFORM_THEN_ACT.routine_id,
            )
        followup = _matching_goal_proposal(context, progress.goal, candidates)
        if followup is None:
            return _no_plan(
                RoutinePlanStatus.BLOCKED,
                "transformed_followup_not_legal_in_authoritative_epoch",
                routine_id=TRANSFORM_THEN_ACT.routine_id,
            )
        return RoutinePlan(
            routine_id=TRANSFORM_THEN_ACT.routine_id,
            purpose=TRANSFORM_THEN_ACT.purpose,
            status=RoutinePlanStatus.PROPOSED,
            step_id="act",
            target_uuid=progress.goal.target_uuid,
            target_position=progress.target_position,
            proposal=followup.model_copy(update={
                "source_node": "Pressure/TransformThenAct/Act",
                "reason": "fresh legal row satisfies retained transformed semantic goal",
            }),
            clear_progress_on_success=True,
            reason="resolve_fresh_transformed_followup",
        )
    return _plan_capability_transformation(context, instrumentation)


def plan_approach_open_reassess(
    context: PolicyContext,
    progress: Optional[RoutineProgress],
    _candidates: Optional[PolicyCandidateSet] = None,
    _instrumentation: Optional[RoutinePlanningInstrumentation] = None,
) -> RoutinePlan:
    """Propose one legal step toward opening and reassessing a known door."""
    context.validate_alignment()
    facts = context.facts
    if not facts.actor.is_my_turn or facts.actor.actor_uuid is None:
        return _no_plan(RoutinePlanStatus.NOT_APPLICABLE, "controlled_actor_inactive")
    if facts.contacts.visible_hostile_uuids:
        return _no_plan(RoutinePlanStatus.NOT_APPLICABLE, "visible_hostile_requires_combat_policy")
    target_uuid = _routine_target_uuid(context, progress)
    if target_uuid is None:
        return _no_plan(RoutinePlanStatus.NOT_APPLICABLE, "no_known_closed_door")
    target = context.world.known_objects.get(target_uuid)
    if target is None or target.position is None:
        return _no_plan(RoutinePlanStatus.BLOCKED, "door_target_position_unknown")
    target_position = target.position

    open_row = _open_door_row(context, target_uuid)
    if open_row is not None:
        selected_target = open_row.targets[0] if open_row.targets else ActionTarget(index=0)
        return _proposed_plan(
            context,
            open_row,
            selected_target,
            step_id="open",
            reason="open_adjacent_door",
            target_uuid=target_uuid,
            target_position=target_position,
            next_step="reassess",
            progress=progress,
        )

    movement = _movement_progress_row(context, target_position)
    if movement is not None:
        row, selected_target = movement
        return _proposed_plan(
            context,
            row,
            selected_target,
            step_id="approach",
            reason="move_toward_closed_door",
            target_uuid=target_uuid,
            target_position=target_position,
            next_step="approach",
            progress=progress,
        )

    mobility = _mobility_extension_row(context, target_position)
    if mobility is not None:
        selected_target = mobility.targets[0] if mobility.targets else ActionTarget(index=0)
        return _proposed_plan(
            context,
            mobility,
            selected_target,
            step_id="extend_mobility",
            reason="dash_toward_closed_door",
            target_uuid=target_uuid,
            target_position=target_position,
            next_step="approach",
            progress=progress,
        )

    return RoutinePlan(
        routine_id=APPROACH_OPEN_REASSESS.routine_id,
        purpose=APPROACH_OPEN_REASSESS.purpose,
        status=RoutinePlanStatus.BLOCKED,
        target_uuid=target_uuid,
        target_position=target_position,
        reason="no_legal_progress_affordance",
    )


def _proposed_plan(
    context: PolicyContext,
    row: ActionAffordance,
    target: ActionTarget,
    *,
    step_id: str,
    reason: str,
    target_uuid: str,
    target_position: Position,
    next_step: str,
    progress: Optional[RoutineProgress],
) -> RoutinePlan:
    """Build a proposal and its acceptance-gated progress update."""
    epoch = context.world.current_epoch
    if epoch is None:
        return _no_plan(RoutinePlanStatus.NOT_APPLICABLE, "decision_epoch_missing")
    semantics = context.facts.affordances.semantics_by_row_id[row.row_id]
    started_epoch_index = progress.started_epoch_index if progress is not None else epoch.epoch_index
    next_progress = RoutineProgress(
        routine_id=APPROACH_OPEN_REASSESS.routine_id,
        step_id=next_step,
        started_epoch_index=started_epoch_index,
        target_uuid=target_uuid,
        target_position=target_position,
    )
    proposal = PolicyProposal(
        intent=ExecuteIntent(row_id=row.row_id),
        goal=PolicyGoal.ROUTINE,
        source_node="ObjectAndSearch/ApproachOpenReassess",
        reason=reason,
        replay_key=(
            row.semantic_key,
            position_replay_token(target.position),
            position_replay_token(target_position),
        ),
        semantic_tags=semantics.tags,
    )
    return RoutinePlan(
        routine_id=APPROACH_OPEN_REASSESS.routine_id,
        purpose=APPROACH_OPEN_REASSESS.purpose,
        status=RoutinePlanStatus.PROPOSED,
        step_id=step_id,
        target_uuid=target_uuid,
        target_position=target_position,
        selected_target_index=target.index,
        proposal=proposal,
        next_progress_on_success=next_progress,
        reason=reason,
    )


def _plan_outcome_augmentation(
    context: PolicyContext,
    candidates: Optional[PolicyCandidateSet],
    instrumentation: Optional[RoutinePlanningInstrumentation],
) -> RoutinePlan:
    """Choose one transient setup only when its projected attack is better."""
    epoch = context.world.current_epoch
    if (
        epoch is None
        or not context.facts.actor.is_my_turn
        or not context.facts.contacts.visible_hostile_uuids
    ):
        return _no_plan(
            RoutinePlanStatus.NOT_APPLICABLE,
            "active_actor_or_visible_hostile_missing",
            routine_id=AUGMENT_THEN_ACT.routine_id,
        )
    candidate_set = candidates or build_policy_candidate_set(context)
    baseline = UtilityArbiter().select(candidate_set.direct_damage)
    if baseline is None:
        return _no_plan(
            RoutinePlanStatus.NOT_APPLICABLE,
            "no_legal_direct_pressure_to_augment",
            routine_id=AUGMENT_THEN_ACT.routine_id,
        )

    best: Optional[tuple[tuple[float, tuple[str, ...]], RoutinePlan]] = None
    for row_id in context.facts.affordances.row_ids_by_tag.get(
        ActionTag.SETUP_SELF,
        tuple(),
    ):
        row = context.facts.affordances.by_id.get(row_id)
        semantics = context.facts.affordances.semantics_by_row_id.get(row_id)
        setup = semantics.self_setup if semantics is not None else None
        if (
            row is None
            or semantics is None
            or setup is None
            or setup.duration is SelfSetupDuration.UNTIL_REMOVED
            or not setup.outcome_adjustments
            or self_setup_effect_may_already_be_active(context, semantics)
            or not row.can_afford
            or row.cost.affordability == "unaffordable"
            or not context.execution_constraints.allows(row)
        ):
            continue
        projected_context = _project_augmentation_context(context, semantics)
        if projected_context is None:
            continue
        projected_pressure = UtilityArbiter().select(
            direct_damage_candidates(projected_context)
        )
        if projected_pressure is None or not isinstance(
            projected_pressure.intent,
            ExecuteIntent,
        ):
            continue
        projected_row = context.facts.affordances.by_id.get(
            projected_pressure.intent.row_id
        )
        projected_semantics = context.facts.affordances.semantics_by_row_id.get(
            projected_pressure.intent.row_id
        )
        target_plan = projected_pressure.evidence.target_plan
        target_uuid = target_plan.primary_target_uuid if target_plan is not None else None
        target = context.world.known_entities.get(target_uuid or "")
        if (
            projected_row is None
            or projected_semantics is None
            or target_uuid is None
            or target is None
            or target.position is None
            or not (
                instrumentation.affordability.combined_costs_affordable(
                    row.cost,
                    projected_row.cost,
                )
                if instrumentation is not None
                else combined_costs_affordable(
                    epoch.economy,
                    row.cost,
                    projected_row.cost,
                )
            )
        ):
            continue
        surviving_hostile_agency = _expected_surviving_visible_hostile_agency(
            context,
            projected_pressure,
        )
        actor_fragility = _actor_fragility_multiplier(context)
        setup_opportunity_cost = action_economy_opportunity_cost(row.cost)
        limited_resource_cost = float(_limited_resource_units(row.cost))
        first_attack_marginal_utility = projected_pressure.score - baseline.score
        additional_matching_attacks = _additional_matching_attack_count(
            context,
            setup_semantics=semantics,
            projected_row=projected_row,
            projected_semantics=projected_semantics,
        )
        exposure_liability = (
            surviving_hostile_agency * actor_fragility
            if setup.grants_incoming_attack_advantage
            else 0.0
        )
        components = (
            UtilityComponent(
                name="projected_followup_utility",
                raw_value=projected_pressure.score,
                weight=1.0,
                contribution=projected_pressure.score,
                reason="same shared direct-pressure scorer over the projected profile",
            ),
            UtilityComponent(
                name="additional_matching_attack_marginal_utility",
                raw_value=float(additional_matching_attacks),
                weight=first_attack_marginal_utility,
                contribution=(
                    float(additional_matching_attacks)
                    * first_attack_marginal_utility
                ),
                reason=(
                    "remaining attack slots whose owned capability matches the "
                    "same turn-duration outcome adjustment"
                ),
            ),
            UtilityComponent(
                name="setup_action_economy_opportunity_cost",
                raw_value=setup_opportunity_cost,
                weight=-4.0,
                contribution=setup_opportunity_cost * -4.0,
                reason="typed flexibility consumed before the follow-up",
            ),
            UtilityComponent(
                name="setup_limited_resource_cost",
                raw_value=limited_resource_cost,
                weight=-2.0,
                contribution=limited_resource_cost * -2.0,
                reason="spell slots, named resources, or charges consumed by setup",
            ),
            UtilityComponent(
                name="surviving_hostile_exposure_liability",
                raw_value=exposure_liability,
                weight=-2.0,
                contribution=exposure_liability * -2.0,
                reason=(
                    "visible hostile agency scaled by the reciprocal of the "
                    "actor's known remaining-HP fraction"
                ),
            ),
            UtilityComponent(
                name="actor_fragility_multiplier",
                raw_value=actor_fragility,
                weight=0.0,
                contribution=0.0,
                reason=(
                    "one at full or unknown health, increasing continuously as "
                    "known total hit points are depleted"
                ),
            ),
            UtilityComponent(
                name="projected_marginal_utility",
                raw_value=first_attack_marginal_utility,
                weight=0.0,
                contribution=0.0,
                reason="unpenalized gain over the current best direct pressure",
            ),
        )
        score = sum(component.contribution for component in components)
        if score <= baseline.score:
            continue
        goal_tags = frozenset(
            tag for tag in projected_pressure.semantic_tags if tag in DIRECT_DAMAGE_TAGS
        )
        if not goal_tags:
            continue
        proposal = PolicyProposal(
            intent=ExecuteIntent(row_id=row.row_id),
            goal=PolicyGoal.ROUTINE,
            source_node="Pressure/AugmentThenAct/Augment",
            reason="typed transient augmentation improves projected direct pressure",
            score=score,
            replay_key=(
                row.semantic_key,
                projected_row.semantic_key,
                entity_fact_replay_token(target),
            ),
            utility_components=components,
            semantic_tags=semantics.tags,
        )
        progress = RoutineProgress(
            routine_id=AUGMENT_THEN_ACT.routine_id,
            step_id="reassess",
            started_epoch_index=epoch.epoch_index,
            target_uuid=target_uuid,
            target_position=target.position,
            goal=SemanticActionGoal(
                required_tags=goal_tags,
                target_uuid=target_uuid,
                required_target_allocation=projected_semantics.targeting.allocation,
                minimum_selected_targets=1,
            ),
            enablers_used=1,
            started_round_number=epoch.round_number,
            started_turn_index=epoch.turn_index,
        )
        plan = RoutinePlan(
            routine_id=AUGMENT_THEN_ACT.routine_id,
            purpose=AUGMENT_THEN_ACT.purpose,
            status=RoutinePlanStatus.PROPOSED,
            step_id="augment",
            target_uuid=target_uuid,
            target_position=target.position,
            selected_target_index=row.targets[0].index if row.targets else 0,
            proposal=proposal,
            next_progress_on_success=progress,
            reason=f"augment_once_then_reassess:{semantics.semantic_id}",
        )
        ordering = (-score, proposal.replay_key)
        if best is None or ordering < best[0]:
            best = (ordering, plan)
    if best is None:
        return _no_plan(
            RoutinePlanStatus.NOT_APPLICABLE,
            "no_positive_marginal_transient_augmentation",
            routine_id=AUGMENT_THEN_ACT.routine_id,
        )
    return best[1]


def _additional_matching_attack_count(
    context: PolicyContext,
    *,
    setup_semantics: ActionSemantics,
    projected_row: ActionAffordance,
    projected_semantics: ActionSemantics,
) -> int:
    """Count remaining attack slots covered by the selected augmentation."""
    epoch = context.world.current_epoch
    setup = setup_semantics.self_setup
    if epoch is None or setup is None or epoch.economy.extra_attacks <= 0:
        return 0
    matching_selectors = tuple(
        adjustment.selector
        for adjustment in setup.outcome_adjustments
        if affordance_matches_selector(
            projected_row,
            projected_semantics,
            adjustment.selector,
        )
    )
    if not matching_selectors:
        return 0
    for capability in epoch.affordances.capabilities:
        capability_semantics = epoch.affordances.semantic_catalog.get(
            capability.semantics_ref
        )
        if (
            capability_semantics is not None
            and capability.cost.consumes_attack_slot
            and any(
                capability_matches_selector(
                    capability,
                    capability_semantics,
                    selector,
                )
                for selector in matching_selectors
            )
        ):
            return epoch.economy.extra_attacks
    return 0


def _project_augmentation_context(
    context: PolicyContext,
    setup_semantics: ActionSemantics,
) -> Optional[PolicyContext]:
    """Project typed outcome adjustments without granting rows or state mutation."""
    epoch = context.world.current_epoch
    setup = setup_semantics.self_setup
    if epoch is None or setup is None:
        return None
    changed = False

    def project_row(row: ActionAffordance) -> ActionAffordance:
        nonlocal changed
        profile = row.outcome_profile
        row_semantics = epoch.affordances.semantic_catalog.get(row.semantics_ref)
        if profile is None or row_semantics is None:
            return row
        adjustments = tuple(
            adjustment
            for adjustment in setup.outcome_adjustments
            if affordance_matches_selector(row, row_semantics, adjustment.selector)
        )
        if not adjustments:
            return row
        projected = project_outcome_profile(profile, adjustments)
        if projected == profile:
            return row
        changed = True
        return row.model_copy(update={"outcome_profile": projected})

    affordances = epoch.affordances.model_copy(update={
        bucket: tuple(project_row(row) for row in getattr(epoch.affordances, bucket))
        for bucket in (
            "entity_actions",
            "position_actions",
            "self_actions",
            "object_actions",
            "special_commands",
        )
    })
    if not changed:
        return None
    projected_world = context.world.model_copy(update={
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    projected_facts = derive_agent_facts(projected_world).facts
    return context.model_copy(update={
        "world": projected_world,
        "facts": projected_facts,
    })


def _expected_surviving_visible_hostile_agency(
    context: PolicyContext,
    proposal: PolicyProposal,
) -> float:
    """Return bounded expected visible hostile count after one projected action."""
    defeat_probability = {
        outcome.entity_uuid: outcome.defeat_probability
        for outcome in proposal.evidence.damage_outcomes
    }
    return sum(
        1.0 - defeat_probability.get(entity_uuid, 0.0)
        for entity_uuid in context.facts.contacts.visible_hostile_uuids
        for entity in [context.world.known_entities.get(entity_uuid)]
        if entity is not None and entity.is_dead is not True
    )


def _actor_fragility_multiplier(context: PolicyContext) -> float:
    """Scale downside by the reciprocal of known remaining health fraction."""
    hp = context.facts.actor.hp
    max_hp = context.facts.actor.max_hp
    if hp is None or max_hp is None or max_hp <= 0:
        return 1.0
    return max(1.0, float(max_hp) / float(max(1, hp)))


def _plan_capability_transformation(
    context: PolicyContext,
    instrumentation: Optional[RoutinePlanningInstrumentation],
) -> RoutinePlan:
    """Choose a legal transform whose projected follow-up improves pressure."""
    facts = context.facts
    epoch = context.world.current_epoch
    actor_position = facts.actor.position
    if epoch is None or actor_position is None or not facts.contacts.visible_hostile_uuids:
        return _no_plan(
            RoutinePlanStatus.NOT_APPLICABLE,
            "active_actor_or_visible_hostile_missing",
            routine_id=TRANSFORM_THEN_ACT.routine_id,
        )
    transform_rows = [
        row
        for row_id in facts.affordances.row_ids_by_tag.get(
            ActionTag.CAPABILITY_TRANSFORM,
            tuple(),
        )
        for row in [facts.affordances.by_id.get(row_id)]
        if row is not None
        and row.can_afford
        and context.execution_constraints.allows(row)
    ]
    best: Optional[
        tuple[
            tuple[float, str, str, str],
            ActionAffordance,
            ActionCapability,
            ProjectedCapability,
            str,
            Position,
            frozenset[ActionTag],
            int,
            TruthValue,
        ]
    ] = None
    line_cache: dict[tuple[Position, Position], TruthValue] = {}
    outcome_workspace = DamageOutcomeWorkspace(shared_value_cache=True)
    damage_capability_ids = {
        capability_id
        for tag in DIRECT_DAMAGE_TAGS
        for capability_id in facts.capabilities.capability_ids_by_tag.get(
            tag,
            tuple(),
        )
    }
    damage_capabilities = tuple(
        capability
        for capability in facts.capabilities.rows
        if capability.capability_id in damage_capability_ids
    )
    for row in transform_rows:
        row_semantics = facts.affordances.semantics_by_row_id.get(row.row_id)
        if row_semantics is None:
            continue
        for transformation in row_semantics.capability_transformations:
            for capability in damage_capabilities:
                capability_semantics = facts.capabilities.semantics_by_capability_id.get(
                    capability.capability_id
                )
                if capability_semantics is None:
                    continue
                projection = project_capability_transformation(
                    capability,
                    capability_semantics,
                    transformation,
                    epoch.economy,
                )
                if projection is None or not (
                    instrumentation.affordability.combined_costs_affordable(
                        row.cost,
                        projection.cost,
                    )
                    if instrumentation is not None
                    else combined_costs_affordable(
                        epoch.economy,
                        row.cost,
                        projection.cost,
                    )
                ):
                    continue
                goal_tags = _projected_damage_goal_tags(
                    capability_semantics.tags,
                    projection.targeting.allocation,
                )
                if not goal_tags:
                    continue
                targets = _eligible_projection_targets(
                    context,
                    capability,
                    projection,
                    actor_position,
                    line_cache,
                )
                if not targets:
                    continue
                minimum_targets = max(1, projection.targeting.minimum_targets)
                if (
                    not projection.targeting.allows_repeated_targets
                    and len(targets) < minimum_targets
                ):
                    continue
                maximum_targets = projection.targeting.maximum_targets or minimum_targets
                applications = (
                    maximum_targets
                    if projection.targeting.allows_repeated_targets
                    else min(maximum_targets, len(targets))
                )
                projected_targets = []
                for target_projection in targets:
                    target_uuid = target_projection[0]
                    target = context.world.known_entities[target_uuid]
                    estimate = (
                        estimate_damage_outcome(
                            capability.outcome_profile,
                            target,
                            applications=(
                                applications
                                if projection.targeting.allows_repeated_targets
                                else 1
                            ),
                            workspace=outcome_workspace,
                        )
                        if capability.outcome_profile is not None
                        else None
                    )
                    if estimate is not None and estimate.guaranteed_zero:
                        continue
                    projected_targets.append(target_projection)
                if not projected_targets:
                    continue
                if not projection.targeting.allows_repeated_targets:
                    applications = min(applications, len(projected_targets))
                hostile_uuid, hostile_position, line = projected_targets[0]
                components = _transformation_utility_components(
                    row.cost,
                    projection.cost,
                    applications,
                    line,
                )
                score = sum(component.contribution for component in components)
                ordering = (
                    -score,
                    row.semantic_key,
                    _capability_replay_token(capability),
                    entity_fact_replay_token(
                        context.world.known_entities[hostile_uuid]
                    ),
                )
                candidate = (
                    ordering,
                    row,
                    capability,
                    projection,
                    hostile_uuid,
                    hostile_position,
                    goal_tags,
                    applications,
                    line,
                )
                if best is None or ordering < best[0]:
                    best = candidate
    if best is None:
        return _no_plan(
            RoutinePlanStatus.NOT_APPLICABLE,
            "no_affordable_useful_capability_transformation",
            routine_id=TRANSFORM_THEN_ACT.routine_id,
        )
    (
        _,
        row,
        capability,
        projection,
        hostile_uuid,
        hostile_position,
        goal_tags,
        applications,
        line,
    ) = best
    row_semantics = facts.affordances.semantics_by_row_id[row.row_id]
    components = _transformation_utility_components(
        row.cost,
        projection.cost,
        applications,
        line,
    )
    proposal = PolicyProposal(
        intent=ExecuteIntent(row_id=row.row_id),
        goal=PolicyGoal.ROUTINE,
        source_node="Pressure/TransformThenAct/Transform",
        reason="typed capability transformation predicts a stronger affordable follow-up",
        score=sum(component.contribution for component in components),
        replay_key=(
            row.semantic_key,
            projection.transformation_id,
            _capability_replay_token(capability),
            position_replay_token(hostile_position),
        ),
        utility_components=components,
        semantic_tags=row_semantics.tags,
    )
    progress = RoutineProgress(
        routine_id=TRANSFORM_THEN_ACT.routine_id,
        step_id="reassess",
        started_epoch_index=epoch.epoch_index,
        target_uuid=hostile_uuid,
        target_position=hostile_position,
        goal=SemanticActionGoal(
            required_tags=goal_tags,
            target_uuid=hostile_uuid,
            required_target_allocation=projection.targeting.allocation,
            minimum_selected_targets=max(1, projection.targeting.minimum_targets),
        ),
        enablers_used=1,
        started_round_number=epoch.round_number,
        started_turn_index=epoch.turn_index,
        consumption_selector=(
            next(
                transformation.consumed_by
                for transformation in row_semantics.capability_transformations
                if transformation.transformation_id == projection.transformation_id
            )
        ),
    )
    return RoutinePlan(
        routine_id=TRANSFORM_THEN_ACT.routine_id,
        purpose=TRANSFORM_THEN_ACT.purpose,
        status=RoutinePlanStatus.PROPOSED,
        step_id="transform",
        target_uuid=hostile_uuid,
        target_position=hostile_position,
        selected_target_index=row.targets[0].index if row.targets else 0,
        proposal=proposal,
        next_progress_on_success=progress,
        reason=f"transform_once_then_reassess:{projection.transformation_id}",
    )


def _eligible_projection_targets(
    context: PolicyContext,
    capability: ActionCapability,
    projection: ProjectedCapability,
    actor_position: Position,
    line_cache: dict[tuple[Position, Position], TruthValue],
) -> list[tuple[str, Position, TruthValue]]:
    """Return visible hostiles inside the projected capability envelope."""
    maximum_range = capability.long_range_feet or capability.normal_range_feet
    if maximum_range is None or capability.valid_target_filter not in {"enemies", "all"}:
        return []
    targets: list[tuple[str, Position, TruthValue]] = []
    for hostile_uuid in context.facts.contacts.visible_hostile_uuids:
        hostile = context.world.known_entities.get(hostile_uuid)
        if hostile is None or hostile.position is None or hostile.is_dead is True:
            continue
        if grid_distance_feet(actor_position, hostile.position) > maximum_range:
            continue
        line_key = (actor_position, hostile.position)
        line = TruthValue.TRUE
        if capability.requires_line_of_sight:
            line = line_cache.get(line_key) or known_line_of_sight(
                context.world,
                actor_position,
                hostile.position,
                vision_blocker_positions=context.facts.topology.vision_blocker_positions,
            )
            line_cache[line_key] = line
        if line is TruthValue.FALSE:
            continue
        targets.append((hostile_uuid, hostile.position, line))
    return sorted(
        targets,
        key=lambda target: entity_fact_replay_token(
            context.world.known_entities[target[0]]
        ),
    )


def _projected_damage_goal_tags(
    tags: frozenset[ActionTag],
    allocation: TargetAllocation,
) -> frozenset[ActionTag]:
    """Return the damage-shape tags expected from the transformed epoch."""
    if not tags.intersection(DIRECT_DAMAGE_TAGS):
        return frozenset()
    if allocation is TargetAllocation.MULTI_ENTITY:
        return frozenset({ActionTag.DAMAGE_MULTI_TARGET})
    if allocation in {TargetAllocation.AREA, TargetAllocation.POSITION}:
        return frozenset({ActionTag.DAMAGE_AREA})
    return frozenset({ActionTag.DAMAGE_SINGLE_TARGET})


def _transformation_utility_components(
    activation_cost: ActionCostProfile,
    projected_cost: ActionCostProfile,
    applications: int,
    line: TruthValue,
) -> tuple[UtilityComponent, ...]:
    """Score a transform from its projected pressure and complete sequence cost."""
    limited_resources = float(
        _limited_resource_units(activation_cost)
        + _limited_resource_units(projected_cost)
    )
    opportunity_cost = (
        action_economy_opportunity_cost(activation_cost)
        + action_economy_opportunity_cost(projected_cost)
    )
    return (
        UtilityComponent(
            name="projected_direct_pressure",
            raw_value=1.0,
            weight=100.0,
            contribution=100.0,
            reason="typed transformation projects an actor-owned damage capability",
        ),
        UtilityComponent(
            name="projected_target_applications",
            raw_value=float(applications),
            weight=15.0,
            contribution=15.0 * float(applications),
            reason="transformed targeting applications over visible hostile contacts",
        ),
        UtilityComponent(
            name="sequence_action_economy_opportunity_cost",
            raw_value=opportunity_cost,
            weight=-4.0,
            contribution=-4.0 * opportunity_cost,
            reason="activation and projected follow-up consume flexible economy",
        ),
        UtilityComponent(
            name="sequence_limited_resource_cost",
            raw_value=limited_resources,
            weight=-2.0,
            contribution=-2.0 * limited_resources,
            reason="activation and projected follow-up consume typed limited resources",
        ),
        UtilityComponent(
            name="projected_line_unknown",
            raw_value=float(line is TruthValue.UNKNOWN),
            weight=-10.0,
            contribution=-10.0 if line is TruthValue.UNKNOWN else 0.0,
            reason="unknown subjective line requires next-epoch revalidation",
        ),
    )


def _limited_resource_units(cost: ActionCostProfile) -> int:
    """Count typed non-economy resources consumed by one cost profile."""
    return (
        int(cost.spell_slot_cost is not None)
        + sum(cost.resource_costs.values())
        + sum(cost.item_charge_costs.values())
    )


def _plan_damage_enabling_movement(
    context: PolicyContext,
    candidates: Optional[PolicyCandidateSet] = None,
    instrumentation: Optional[RoutinePlanningInstrumentation] = None,
) -> RoutinePlan:
    """Choose one legal move predicted to enable an owned damage capability."""
    facts = context.facts
    epoch = context.world.current_epoch
    actor_position = facts.actor.position
    if epoch is None or actor_position is None or not facts.contacts.visible_hostile_uuids:
        return _no_plan(
            RoutinePlanStatus.NOT_APPLICABLE,
            "active_actor_or_visible_hostile_missing",
            routine_id=ENABLE_THEN_ACT.routine_id,
        )
    candidate_set = candidates or build_policy_candidate_set(context)
    if candidate_set.direct_damage:
        return _no_plan(
            RoutinePlanStatus.NOT_APPLICABLE,
            "direct_damage_already_legal",
            routine_id=ENABLE_THEN_ACT.routine_id,
        )
    damage_capabilities: list[
        tuple[ActionCapability, int, frozenset[ActionTag], str]
    ] = []
    for capability in facts.capabilities.rows:
        semantics = facts.capabilities.semantics_by_capability_id.get(
            capability.capability_id
        )
        if semantics is None:
            continue
        goal_tags = frozenset(semantics.tags & DIRECT_DAMAGE_TAGS)
        maximum_range = capability.long_range_feet or capability.normal_range_feet
        if (
            not goal_tags
            or capability.valid_target_filter not in {"enemies", "all"}
            or capability.cost.affordability == "unaffordable"
            or maximum_range is None
        ):
            continue
        capability_key = _capability_replay_token(capability)
        damage_capabilities.append((
            capability,
            maximum_range,
            goal_tags,
            capability_key,
        ))
        if instrumentation is not None:
            instrumentation.replay_token_builds += 1
    if not damage_capabilities:
        return _no_plan(
            RoutinePlanStatus.NOT_APPLICABLE,
            "no_owned_damage_capability",
            routine_id=ENABLE_THEN_ACT.routine_id,
        )

    movement_ids = facts.affordances.row_ids_by_tag.get(
        ActionTag.MOVEMENT_VOLUNTARY,
        tuple(),
    )
    if instrumentation is not None:
        instrumentation.damage_capabilities += len(damage_capabilities)
    movement_options: list[
        tuple[ActionAffordance, ActionTarget, int, float, str]
    ] = []
    for row_id in movement_ids:
        row = facts.affordances.by_id.get(row_id)
        if (
            row is None
            or not row.can_afford
            or not context.execution_constraints.allows(row)
        ):
            continue
        for target in row.targets:
            movement_cost = target.path_cost
            if (
                target.position is None
                or movement_cost is None
                or movement_cost > epoch.economy.movement_remaining
            ):
                continue
            movement_options.append((
                row,
                target,
                movement_cost,
                action_economy_opportunity_cost(row.cost),
                position_replay_token(target.position),
            ))
    if instrumentation is not None:
        instrumentation.movement_endpoints += len(movement_options)

    hostile_options: list[tuple[str, Position, str, str]] = []
    for hostile_uuid in facts.contacts.visible_hostile_uuids:
        hostile = context.world.known_entities.get(hostile_uuid)
        if hostile is None or hostile.position is None:
            continue
        hostile_options.append((
            hostile_uuid,
            hostile.position,
            entity_fact_replay_token(hostile),
            position_replay_token(hostile.position),
        ))

    best: Optional[
        tuple[
            tuple[int, int, int, float, int, str, str, int, str, str],
            ActionAffordance,
            ActionTarget,
            ActionCapability,
            str,
            Position,
            frozenset[ActionTag],
            TruthValue,
            str,
            str,
        ]
    ] = None
    affordability = (
        instrumentation.affordability
        if instrumentation is not None
        else AffordabilityWorkspace(epoch.economy)
    )
    line_cache: dict[tuple[Position, Position], TruthValue] = {}
    for hostile_uuid, hostile_position, hostile_key, hostile_position_key in hostile_options:
        for row, target, movement_cost, row_opportunity_cost, target_position_key in movement_options:
            if target.position is None:
                continue
            endpoint_distance = grid_distance_feet(
                target.position,
                hostile_position,
            )
            line_key = (target.position, hostile_position)
            eligible: list[
                tuple[int, str, ActionCapability, frozenset[ActionTag], TruthValue]
            ] = []
            for capability, maximum_range, goal_tags, capability_key in damage_capabilities:
                if endpoint_distance > maximum_range:
                    continue
                if not affordability.combined_costs_affordable(
                    row.cost,
                    capability.cost,
                    first_movement_cost=movement_cost,
                ):
                    continue
                if capability.requires_line_of_sight:
                    if instrumentation is not None:
                        line = instrumentation.known_line_of_sight(
                            context,
                            target.position,
                            hostile_position,
                        )
                    else:
                        line = line_cache.get(line_key)
                        if line is None:
                            line = known_line_of_sight(
                                context.world,
                                target.position,
                                hostile_position,
                                vision_blocker_positions=(
                                    facts.topology.vision_blocker_positions
                                ),
                            )
                            line_cache[line_key] = line
                else:
                    line = TruthValue.TRUE
                if line is TruthValue.FALSE:
                    continue
                eligible.append((
                    0 if line is TruthValue.TRUE else 1,
                    capability_key,
                    capability,
                    goal_tags,
                    line,
                ))
            if not eligible:
                continue
            line_rank, capability_key, capability, goal_tags, line = min(
                eligible,
                key=lambda candidate: (candidate[0], candidate[1]),
            )
            unsafe = int(target.is_path_hazardous and not target.safe_path)
            score = (
                line_rank,
                unsafe,
                endpoint_distance,
                row_opportunity_cost,
                movement_cost,
                row.semantic_key,
                target_position_key,
                target.index,
                capability_key,
                hostile_key,
            )
            planned = (
                score,
                row,
                target,
                capability,
                hostile_uuid,
                hostile_position,
                goal_tags,
                line,
                target_position_key,
                hostile_position_key,
            )
            if best is None or score < best[0]:
                best = planned
    if best is None:
        return _no_plan(
            RoutinePlanStatus.NOT_APPLICABLE,
            "no_single_move_enabling_opportunity",
            routine_id=ENABLE_THEN_ACT.routine_id,
        )
    (
        _,
        row,
        target,
        capability,
        hostile_uuid,
        hostile_position,
        goal_tags,
        line,
        target_position_key,
        hostile_position_key,
    ) = best
    row_semantics = facts.affordances.semantics_by_row_id[row.row_id]
    utility_components = (
        UtilityComponent(
            name="enables_owned_damage_capability",
            raw_value=1.0,
            weight=80.0,
            contribution=80.0,
            reason="one legal movement step reaches an actor-owned damage capability envelope",
        ),
        UtilityComponent(
            name="counterfactual_line_unknown",
            raw_value=float(line is TruthValue.UNKNOWN),
            weight=-10.0,
            contribution=-10.0 if line is TruthValue.UNKNOWN else 0.0,
            reason="unknown subjective directional facts require next-epoch revalidation",
        ),
    )
    proposal = PolicyProposal(
        intent=ExecuteIntent(row_id=row.row_id),
        goal=PolicyGoal.ROUTINE,
        source_node="Pressure/EnableThenAct/Enable",
        reason="legal movement predicts a bounded semantic damage follow-up",
        score=sum(component.contribution for component in utility_components),
        replay_key=(
            row.semantic_key,
            target_position_key,
            hostile_position_key,
        ),
        utility_components=utility_components,
        semantic_tags=row_semantics.tags,
    )
    progress = RoutineProgress(
        routine_id=ENABLE_THEN_ACT.routine_id,
        step_id="reassess",
        started_epoch_index=epoch.epoch_index,
        target_uuid=hostile_uuid,
        target_position=hostile_position,
        goal=SemanticActionGoal(
            required_tags=goal_tags,
            target_uuid=hostile_uuid,
        ),
        enablers_used=1,
        started_round_number=epoch.round_number,
        started_turn_index=epoch.turn_index,
    )
    return RoutinePlan(
        routine_id=ENABLE_THEN_ACT.routine_id,
        purpose=ENABLE_THEN_ACT.purpose,
        status=RoutinePlanStatus.PROPOSED,
        step_id="enable",
        target_uuid=hostile_uuid,
        target_position=hostile_position,
        selected_target_index=target.index,
        proposal=proposal,
        next_progress_on_success=progress,
        reason=f"move_once_to_enable:{capability.semantic_id}",
    )


def _matching_goal_proposal(
    context: PolicyContext,
    goal: SemanticActionGoal,
    candidates: Optional[PolicyCandidateSet] = None,
) -> Optional[PolicyProposal]:
    """Resolve an abstract semantic goal against only fresh legal rows."""
    candidate_set = candidates or build_policy_candidate_set(context)
    for proposal in candidate_set.direct_damage:
        if not goal.required_tags.issubset(proposal.semantic_tags):
            continue
        if not isinstance(proposal.intent, ExecuteIntent):
            continue
        row = context.facts.affordances.by_id.get(proposal.intent.row_id)
        if row is None or not context.execution_constraints.allows(row):
            continue
        semantics = context.facts.affordances.semantics_by_row_id.get(row.row_id)
        if (
            goal.required_target_allocation is not None
            and (
                semantics is None
                or semantics.targeting.allocation is not goal.required_target_allocation
            )
        ):
            continue
        affected = {
            target_uuid
            for target in row.targets
            for target_uuid in (
                [target.target_uuid] if target.target_uuid is not None else []
            )
        }
        affected.update(
            entity_uuid
            for target in row.targets
            for entity_uuid in target.affected_entity_uuids
        )
        affected.update(proposal.intent.extra_target_uuids)
        if goal.target_uuid not in affected:
            continue
        target_plan = proposal.evidence.target_plan
        selected_count = (
            len(target_plan.selected_target_uuids)
            if target_plan is not None
            else 1 + len(proposal.intent.extra_target_uuids)
        )
        if selected_count >= goal.minimum_selected_targets:
            return proposal
    return None


def _capability_replay_token(capability: ActionCapability) -> str:
    """Return the UUID-free semantic identity of one actor-owned capability."""
    return "|".join((
        capability.semantic_key,
        capability.semantic_id,
        capability.target_type,
        str(capability.base_spell_level or 0),
        str(capability.cast_at_level or 0),
        capability.weapon_slot or "",
        str(capability.normal_range_feet or 0),
        str(capability.long_range_feet or 0),
    ))


def _no_plan(
    status: RoutinePlanStatus,
    reason: str,
    *,
    routine_id: str = APPROACH_OPEN_REASSESS.routine_id,
) -> RoutinePlan:
    """Build a plan without a legal command proposal."""
    return RoutinePlan(
        routine_id=routine_id,
        purpose=_routine_purpose(routine_id),
        status=status,
        reason=reason,
    )


def _routine_purpose(routine_id: str) -> RoutinePurpose:
    """Resolve a registered routine identity to its typed tactical purpose."""
    registered = _ROUTINES_BY_ID.get(routine_id)
    if registered is None:
        raise ValueError(f"Unknown routine id: {routine_id}")
    return registered.contract.purpose


def _routine_target_uuid(
    context: PolicyContext,
    progress: Optional[RoutineProgress],
) -> Optional[str]:
    """Select a stable target, preserving valid actor-owned progress."""
    closed = context.facts.objects.closed_door_uuids
    if progress is not None and progress.routine_id == APPROACH_OPEN_REASSESS.routine_id:
        if progress.target_uuid in closed:
            return progress.target_uuid
    actor_position = context.facts.actor.position
    candidates = [
        obj
        for object_uuid in closed
        for obj in [context.world.known_objects.get(object_uuid)]
        if obj is not None and obj.position is not None
    ]
    if not candidates:
        return None
    if actor_position is None:
        return min(candidates, key=object_fact_replay_token).uuid
    return min(
        candidates,
        key=lambda obj: (
            _distance(actor_position, obj.position or actor_position),
            object_fact_replay_token(obj),
        ),
    ).uuid


def _open_door_row(
    context: PolicyContext,
    target_uuid: str,
) -> Optional[ActionAffordance]:
    """Return a legal semantic door-open row for the routine target."""
    row_ids = context.facts.affordances.row_ids_by_tag.get(ActionTag.INTERACTION_DOOR_OPEN, tuple())
    candidates = [
        row
        for row_id in row_ids
        for row in [context.facts.affordances.by_id.get(row_id)]
        if row is not None
        and row.can_afford
        and context.execution_constraints.allows(row)
        and (
            row.source_item_uuid == target_uuid
            or any(target.target_uuid == target_uuid for target in row.targets)
        )
    ]
    return min(candidates, key=lambda row: row.row_id) if candidates else None


def _movement_progress_row(
    context: PolicyContext,
    target_position: Position,
) -> Optional[tuple[ActionAffordance, ActionTarget]]:
    """Choose ordinary movement that improves the known route to the door."""
    actor_position = context.facts.actor.position
    if actor_position is None:
        return None
    route_costs = _route_costs_to_door(context, target_position)
    actor_route_cost = route_costs.get(actor_position)
    actor_distance = _distance(actor_position, target_position)
    candidates: list[
        tuple[tuple[int, int, float, int, str, int], ActionAffordance, ActionTarget]
    ] = []
    row_ids = context.facts.affordances.row_ids_by_tag.get(ActionTag.MOVEMENT_VOLUNTARY, tuple())
    for row_id in row_ids:
        row = context.facts.affordances.by_id.get(row_id)
        if (
            row is None
            or not row.can_afford
            or not context.execution_constraints.allows(row)
        ):
            continue
        for target in row.targets:
            if target.position is None:
                continue
            endpoint_route_cost = route_costs.get(target.position)
            endpoint_distance = _distance(target.position, target_position)
            if actor_route_cost is not None and endpoint_route_cost is not None:
                if endpoint_route_cost >= actor_route_cost:
                    continue
                progress_cost = endpoint_route_cost
            elif endpoint_distance < actor_distance:
                progress_cost = endpoint_distance * 5
            else:
                continue
            unsafe = int(target.is_path_hazardous and not target.safe_path)
            movement_cost = (
                target.safe_path_cost
                if target.safe_path_cost is not None
                else target.path_cost if target.path_cost is not None else 999_999
            )
            score = (
                unsafe,
                progress_cost,
                action_economy_opportunity_cost(row.cost),
                movement_cost,
                row.row_id,
                target.index,
            )
            candidates.append((score, row, target))
    if not candidates:
        return None
    _, row, target = min(candidates, key=lambda candidate: candidate[0])
    return row, target


def _mobility_extension_row(
    context: PolicyContext,
    target_position: Position,
) -> Optional[ActionAffordance]:
    """Return mobility extension only when the known door route can continue."""
    actor_position = context.facts.actor.position
    if actor_position is None or _distance(actor_position, target_position) <= 1:
        return None
    route_costs = _route_costs_to_door(context, target_position)
    if route_costs and actor_position not in route_costs:
        return None
    row_ids = context.facts.affordances.row_ids_by_tag.get(ActionTag.MOBILITY_EXTEND, tuple())
    candidates = [
        row
        for row_id in row_ids
        for row in [context.facts.affordances.by_id.get(row_id)]
        if (
            row is not None
            and row.can_afford
            and context.execution_constraints.allows(row)
        )
    ]
    return min(candidates, key=lambda row: row.row_id) if candidates else None


def _route_costs_to_door(
    context: PolicyContext,
    door_position: Position,
) -> dict[Position, int]:
    """Return known safe topology costs to a cell adjacent to the door."""
    tiles = {
        tile.position: tile
        for tile in context.world.known_tiles.values()
        if tile.walkable is True
    }
    if not tiles:
        return {}
    goals = [
        position
        for position in tiles
        if _distance(position, door_position) <= 1
    ]
    if not goals:
        return {}
    costs: dict[Position, int] = {position: 0 for position in goals}
    heap: list[tuple[int, Position]] = [(0, position) for position in goals]
    heapq.heapify(heap)
    while heap:
        cost, position = heapq.heappop(heap)
        if costs[position] != cost:
            continue
        for neighbor in _neighbors(position):
            tile = tiles.get(neighbor)
            if tile is None:
                continue
            step_cost = max(1, tile.walking_cost or 5)
            if tile.is_hazardous is True:
                step_cost += 100
            next_cost = cost + step_cost
            if next_cost < costs.get(neighbor, 999_999):
                costs[neighbor] = next_cost
                heapq.heappush(heap, (next_cost, neighbor))
    return costs


def _neighbors(position: Position) -> tuple[Position, Position, Position, Position]:
    """Return cardinal grid neighbors in stable order."""
    x, y = position
    return ((x - 1, y), (x, y - 1), (x, y + 1), (x + 1, y))


def _distance(origin: Position, target: Position) -> int:
    """Return Manhattan grid distance for target ordering and fallback progress."""
    return abs(origin[0] - target[0]) + abs(origin[1] - target[1])


RoutinePlanner = Callable[
    [
        PolicyContext,
        Optional[RoutineProgress],
        Optional[PolicyCandidateSet],
        Optional[RoutinePlanningInstrumentation],
    ],
    RoutinePlan,
]
RoutineRevalidator = Callable[
    [PolicyContext, Optional[RoutineProgress], Optional[PolicyCandidateSet]],
    RoutineRevalidation,
]


@dataclass(frozen=True)
class RegisteredRoutine:
    """Runtime dispatch record for one typed routine contract."""

    contract: RoutineContract
    trace_name: str
    planner: RoutinePlanner
    revalidator: RoutineRevalidator


REGISTERED_ROUTINES = (
    RegisteredRoutine(
        contract=APPROACH_OPEN_REASSESS,
        trace_name="ApproachOpenReassess",
        planner=plan_approach_open_reassess,
        revalidator=revalidate_approach_open_reassess,
    ),
    RegisteredRoutine(
        contract=AUGMENT_THEN_ACT,
        trace_name="AugmentThenAct",
        planner=plan_augment_then_act,
        revalidator=revalidate_augment_then_act,
    ),
    RegisteredRoutine(
        contract=TRANSFORM_THEN_ACT,
        trace_name="TransformThenAct",
        planner=plan_transform_then_act,
        revalidator=revalidate_transform_then_act,
    ),
    RegisteredRoutine(
        contract=ENABLE_THEN_ACT,
        trace_name="EnableThenAct",
        planner=plan_enable_then_act,
        revalidator=revalidate_enable_then_act,
    ),
    RegisteredRoutine(
        contract=PURSUE_CAPABILITY,
        trace_name="PursueCapability",
        planner=plan_pursue_capability,
        revalidator=revalidate_pursue_capability,
    ),
)
_ROUTINES_BY_ID = {
    routine.contract.routine_id: routine
    for routine in REGISTERED_ROUTINES
}


def revalidate_active_routine(
    context: PolicyContext,
    progress: Optional[RoutineProgress],
    candidates: Optional[PolicyCandidateSet] = None,
) -> RoutineRevalidation:
    """Dispatch actor progress to its registered routine implementation."""
    if progress is None:
        return RoutineRevalidation(
            routine_id="routine.registry",
            status=RoutineRevalidationStatus.IDLE,
            reason="no_active_routine",
        )
    registered = _ROUTINES_BY_ID.get(progress.routine_id)
    if registered is None:
        return RoutineRevalidation(
            routine_id=progress.routine_id,
            status=RoutineRevalidationStatus.INVALIDATED,
            reason="active_routine_not_registered",
        )
    return registered.revalidator(context, progress, candidates)


def plan_registered_routines(
    context: PolicyContext,
    prior_progress: Optional[RoutineProgress],
    revalidation: RoutineRevalidation,
    candidates: Optional[PolicyCandidateSet] = None,
    instrumentation: Optional[RoutinePlanningInstrumentation] = None,
) -> tuple[RoutinePlan, ...]:
    """Plan active progress plus typed same-target interposers, or all starters."""
    candidate_set = candidates or build_policy_candidate_set(context)
    if prior_progress is not None and revalidation.progress is not None:
        registered = _ROUTINES_BY_ID.get(revalidation.progress.routine_id)
        if registered is None:
            return tuple()
        active_plan = registered.planner(
            context,
            revalidation.progress,
            candidate_set,
            instrumentation,
        )
        return (active_plan, *_interposing_routine_plans(
            context,
            active_plan,
            candidate_set,
            instrumentation,
        ))
    if _dominant_durable_setup_preempts_routine_starters(candidate_set):
        return tuple()
    plans: list[RoutinePlan] = []
    for registered in REGISTERED_ROUTINES:
        if (
            registered.contract.routine_id == PURSUE_CAPABILITY.routine_id
            and _existing_candidates_preempt_pursuit_starter(candidate_set)
        ):
            plans.append(_no_plan(
                RoutinePlanStatus.NOT_APPLICABLE,
                "existing_candidate_dominates_pursuit_starter",
                routine_id=PURSUE_CAPABILITY.routine_id,
            ))
            continue
        plans.append(registered.planner(context, None, candidate_set, instrumentation))
    return tuple(plans)


def _dominant_durable_setup_preempts_routine_starters(
    candidates: PolicyCandidateSet,
) -> bool:
    """Return whether a legal durable setup makes starter planning dominated.

    Starter routines are expensive because they evaluate future movement and
    line-of-sight endpoints. When no direct pressure is already legal, a
    high-scoring durable self-setup is an immediate bounded command that the
    tree will prefer over speculative offensive enablement. Active routines are
    still revalidated before this helper is consulted, so this only prunes new
    starter planning for the current epoch.
    """
    if candidates.direct_damage:
        return False
    return any(
        proposal.goal is PolicyGoal.SELF_SETUP
        and proposal.source_node == "Preparation/DurableSelfSetup"
        and proposal.score >= DOMINANT_DURABLE_SETUP_SCORE
        for proposal in candidates.self_setup
    )


def _existing_candidates_preempt_pursuit_starter(
    candidates: PolicyCandidateSet,
) -> bool:
    """Return whether current proposals dominate a new pursuit starter.

    `PURSUE_CAPABILITY` starts with a fixed-score approach proposal. When
    existing non-routine candidates already outrank that starter, planning the
    route search cannot change the selected command and only burns latency.
    Active pursuit progress is handled before this helper is consulted.
    """
    current_best = max(
        (
            proposal.score
            for group in (
                candidates.healing,
                candidates.control,
                candidates.control_preservation,
                candidates.target_effects,
                candidates.self_setup,
                candidates.spacing,
                candidates.exploration,
            )
            for proposal in group
        ),
        default=float("-inf"),
    )
    return current_best > PURSUE_CAPABILITY_STARTER_SCORE


def _interposing_routine_plans(
    context: PolicyContext,
    active_plan: RoutinePlan,
    candidates: PolicyCandidateSet,
    instrumentation: Optional[RoutinePlanningInstrumentation],
) -> tuple[RoutinePlan, ...]:
    """Start typed setup routines immediately before a retained action step."""
    proposal = active_plan.proposal
    if proposal is None:
        return tuple()
    plans: list[RoutinePlan] = []
    for registered in REGISTERED_ROUTINES:
        contract = registered.contract
        if (
            contract.routine_id == active_plan.routine_id
            or not contract.interposes_before_action_tags.intersection(
                proposal.semantic_tags
            )
        ):
            continue
        plan = registered.planner(
            context,
            None,
            candidates,
            instrumentation,
        )
        if (
            plan.status is not RoutinePlanStatus.PROPOSED
            or plan.proposal is None
            or (
                active_plan.target_uuid is not None
                and plan.target_uuid != active_plan.target_uuid
            )
        ):
            continue
        plans.append(plan)
    return tuple(plans)


def routine_trace_name(routine_id: str) -> str:
    """Return the stable trace label for a registered routine or the registry."""
    registered = _ROUTINES_BY_ID.get(routine_id)
    return registered.trace_name if registered is not None else "RegisteredRoutines"
