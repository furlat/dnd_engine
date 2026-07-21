"""Frozen v31 tactical hierarchy used as the first promotion baseline."""

from __future__ import annotations

from typing import Optional

from ai.policy.candidates import PolicyCandidateSet, end_turn_proposal
from ai.policy.contracts import NodeResult, PolicyContext, PolicyDecision
from ai.policy.default import DefaultPolicyEvaluation
from ai.policy.routines import RoutinePlan, routine_trace_name
from ai.policy.tree import (
    ConditionNode,
    ProposalLeaf,
    SelectorNode,
    SequenceNode,
    UtilitySelectorNode,
)


def create_v31_policy_tree(
    routine_plans: tuple[RoutinePlan, ...],
    candidates: PolicyCandidateSet,
) -> SelectorNode:
    """Compose the accepted v31 branch hierarchy without current-policy imports."""
    routine_branches = tuple(
        ProposalLeaf(
            routine_trace_name(plan.routine_id),
            lambda _context, proposal=plan.proposal: (proposal,) if proposal is not None else tuple(),
        )
        for plan in routine_plans
    )
    tactical_goals = UtilitySelectorNode(
        "TacticalGoalUtility",
        (
            ProposalLeaf("SurvivalRecovery", lambda _context: candidates.healing),
            ProposalLeaf("ConditionalTargetEffects", lambda _context: candidates.target_effects),
            SequenceNode(
                "Control",
                (
                    ConditionNode(
                        "HasVisibleHostiles",
                        lambda context: bool(context.facts.contacts.visible_hostile_uuids),
                        detail="visible hostile contact required",
                    ),
                    ProposalLeaf("HostileControl", lambda _context: candidates.control),
                ),
            ),
            ProposalLeaf("PreserveNewControl", lambda _context: candidates.control_preservation),
            SequenceNode(
                "Pressure",
                (
                    ConditionNode(
                        "HasVisibleHostiles",
                        lambda context: bool(context.facts.contacts.visible_hostile_uuids),
                        detail="visible hostile contact required",
                    ),
                    ProposalLeaf("DirectDamage", lambda _context: candidates.direct_damage),
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
                    ProposalLeaf("DurableSelfSetup", lambda _context: candidates.self_setup),
                ),
            ),
            ProposalLeaf("PositionAndSurvival", lambda _context: candidates.spacing),
            ProposalLeaf("InformationGathering", lambda _context: candidates.exploration),
            UtilitySelectorNode("Routines", routine_branches),
        ),
    )
    return SelectorNode(
        "ReactiveRoot",
        (
            tactical_goals,
            SequenceNode(
                "TerminalFallback",
                (ProposalLeaf("EndTurn", lambda _context: (end_turn_proposal(),)),),
            ),
        ),
    )


def evaluate_v31_policy(
    context: PolicyContext,
    routine_plans: tuple[RoutinePlan, ...],
    candidates: Optional[PolicyCandidateSet] = None,
) -> DefaultPolicyEvaluation:
    """Evaluate the frozen v31 hierarchy over the supplied typed candidates."""
    context.validate_alignment()
    if candidates is None:
        raise ValueError("A generation evaluator requires its generation-owned candidate set.")
    result: NodeResult = create_v31_policy_tree(routine_plans, candidates).tick(context)
    if not result.proposals:
        return DefaultPolicyEvaluation(
            tree_result=result,
            unavailable_reason="all_tactical_goal_branches_failed",
        )
    selected = result.proposals[0]
    decision = PolicyDecision(selected=selected, candidates=result.proposals, trace=result.trace)
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
