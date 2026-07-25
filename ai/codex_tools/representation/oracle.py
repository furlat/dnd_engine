"""Optional adapter from traditional policy results to representation advice."""

from __future__ import annotations

from typing import Literal

from ai.codex_tools.representation.components import (
    AdvicePayload,
    OracleAdviceBasis,
    OracleProposalSummary,
    OracleTraceStepSummary,
)
from ai.policy.contracts import PolicyDecision, PolicyProposal, PolicyTraceStep
from dnd.ai.contracts.decision import ExecuteIntent


OracleDetail = Literal["selected_only", "ranked", "full_trace"]


def advice_from_policy_decision(
    decision: PolicyDecision,
    *,
    basis: OracleAdviceBasis,
    evaluation_ms: float,
    detail: OracleDetail = "selected_only",
) -> AdvicePayload:
    """Convert one policy decision into policy-independent advice contracts.

    Args:
        decision: Already-computed traditional policy decision.
        basis: Exact subjective revision and policy implementation evaluated.
        evaluation_ms: Measured evaluation time for the cached decision.
        detail: Amount of advice exposed by the representation profile.

    Returns:
        Typed representation advice containing no live policy objects.
    """
    return AdvicePayload(
        available=True,
        detail=detail,
        basis=basis,
        evaluation_ms=evaluation_ms,
        selected=_proposal_summary(decision.selected),
        candidates=(
            tuple(_proposal_summary(proposal) for proposal in decision.candidates)
            if detail in {"ranked", "full_trace"}
            else tuple()
        ),
        trace=(
            tuple(_trace_summary(step) for step in decision.trace)
            if detail == "full_trace"
            else tuple()
        ),
    )


def _proposal_summary(proposal: PolicyProposal) -> OracleProposalSummary:
    """Reduce one policy proposal to stable controller-facing advice."""
    intent = proposal.intent
    return OracleProposalSummary(
        intent_kind=intent.kind,
        row_id=intent.row_id if isinstance(intent, ExecuteIntent) else None,
        goal=proposal.goal.value,
        source_node=proposal.source_node,
        reason=proposal.reason,
        score=proposal.score,
        semantic_tags=tuple(sorted(tag.value for tag in proposal.semantic_tags)),
    )


def _trace_summary(step: PolicyTraceStep) -> OracleTraceStepSummary:
    """Reduce one policy trace step to its stable presentation fields."""
    return OracleTraceStepSummary(
        node_path=step.node_path,
        status=step.status.value,
        detail=step.detail,
        proposal_count=step.proposal_count,
    )
