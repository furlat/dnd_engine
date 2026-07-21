"""Shared hierarchical policy composition for traditional and LLM agents."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ai.policy.candidates import (
    PolicyCandidateSet,
    build_policy_candidate_set,
    end_turn_proposal,
)
from ai.policy.contracts import NodeResult, PolicyContext, PolicyDecision
from ai.policy.routines import RoutinePlan, routine_trace_name
from ai.policy.tree import (
    ConditionNode,
    ProposalLeaf,
    SelectorNode,
    SequenceNode,
    UtilitySelectorNode,
)


class DefaultPolicyEvaluation(BaseModel):
    """Pure shared-policy result before host command correlation."""

    model_config = ConfigDict(frozen=True)

    decision: Optional[PolicyDecision] = Field(
        default=None,
        description="Selected decision when at least one branch proposed a command.",
    )
    selected_routine_plan: Optional[RoutinePlan] = Field(
        default=None,
        description="Acceptance-gated routine plan when the selected proposal belongs to one.",
    )
    tree_result: NodeResult = Field(description="Complete hierarchy result including failed branches.")
    unavailable_reason: Optional[str] = Field(
        default=None,
        description="Stable explanation when no branch produced a proposal.",
    )


def create_default_policy_tree(
    routine_plans: tuple[RoutinePlan, ...],
    candidates: PolicyCandidateSet,
) -> SelectorNode:
    """Compose the current shared hierarchy from typed policy branches.

    Args:
        routine_plans: Revalidated routine proposals for this exact context.
        candidates: Decision-scoped tactical candidates shared across branches.

    Returns:
        Pure behavior tree whose tactical choice point evaluates every branch.
    """
    routine_branches = tuple(
        ProposalLeaf(
            routine_trace_name(plan.routine_id),
            lambda _context, proposal=plan.proposal: (
                (proposal,)
                if proposal is not None
                else tuple()
            ),
        )
        for plan in routine_plans
    )
    tactical_goals = UtilitySelectorNode(
        "TacticalGoalUtility",
        (
            ProposalLeaf(
                "SurvivalRecovery",
                lambda _context: candidates.healing,
            ),
            ProposalLeaf(
                "ConditionalTargetEffects",
                lambda _context: candidates.target_effects,
            ),
            SequenceNode(
                "Control",
                (
                    ConditionNode(
                        "HasVisibleHostiles",
                        lambda context: bool(context.facts.contacts.visible_hostile_uuids),
                        detail="visible hostile contact required",
                    ),
                    ProposalLeaf(
                        "HostileControl",
                        lambda _context: candidates.control,
                    ),
                ),
            ),
            ProposalLeaf(
                "PreserveNewControl",
                lambda _context: candidates.control_preservation,
            ),
            SequenceNode(
                "Pressure",
                (
                    ConditionNode(
                        "HasVisibleHostiles",
                        lambda context: bool(context.facts.contacts.visible_hostile_uuids),
                        detail="visible hostile contact required",
                    ),
                    ProposalLeaf(
                        "DirectDamage",
                        lambda _context: candidates.direct_damage,
                    ),
                ),
            ),
            SequenceNode(
                "Preparation",
                (
                    ConditionNode(
                        "HasVisibleHostiles",
                        lambda context: bool(context.facts.contacts.visible_hostile_uuids),
                        detail="visible hostile contact required",
                    ),
                    ProposalLeaf(
                        "DurableSelfSetup",
                        lambda _context: candidates.self_setup,
                    ),
                ),
            ),
            ProposalLeaf(
                "PositionAndSurvival",
                lambda _context: candidates.spacing,
            ),
            ProposalLeaf(
                "InformationGathering",
                lambda _context: candidates.exploration,
            ),
            UtilitySelectorNode("Routines", routine_branches),
        ),
    )
    end_turn = SequenceNode(
        "TerminalFallback",
        (
            ProposalLeaf(
                "EndTurn",
                lambda _context: (end_turn_proposal(),),
            ),
        ),
    )
    return SelectorNode("ReactiveRoot", (tactical_goals, end_turn))


def evaluate_default_policy(
    context: PolicyContext,
    routine_plans: tuple[RoutinePlan, ...],
    candidates: Optional[PolicyCandidateSet] = None,
) -> DefaultPolicyEvaluation:
    """Evaluate the shared hierarchy without executing or reserving a command."""
    context.validate_alignment()
    candidate_set = candidates or build_policy_candidate_set(context)
    result = create_default_policy_tree(routine_plans, candidate_set).tick(context)
    if not result.proposals:
        return DefaultPolicyEvaluation(
            tree_result=result,
            unavailable_reason="all_tactical_goal_branches_failed",
        )
    selected = result.proposals[0]
    decision = PolicyDecision(
        selected=selected,
        candidates=result.proposals,
        trace=result.trace,
    )
    selected_routine_plan = next(
        (
            plan
            for plan in routine_plans
            if plan.proposal is not None and plan.proposal.intent == selected.intent
        ),
        None,
    )
    return DefaultPolicyEvaluation(
        decision=decision,
        selected_routine_plan=selected_routine_plan,
        tree_result=result,
    )
