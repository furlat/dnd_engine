"""Pure hierarchical behavior-tree primitives over shared policy context."""

from __future__ import annotations

from typing import Callable, Protocol, Sequence

from ai.policy.contracts import (
    NodeResult,
    NodeStatus,
    PolicyContext,
    PolicyProposal,
    PolicyTraceStep,
)
from ai.policy.utility import UtilityArbiter


PolicyPredicate = Callable[[PolicyContext], bool]
ProposalFactory = Callable[[PolicyContext], tuple[PolicyProposal, ...]]


class PolicyNode(Protocol):
    """Protocol for pure behavior-tree nodes."""

    name: str

    def tick(self, context: PolicyContext, path: str = "") -> NodeResult:
        """Evaluate the node without executing engine commands."""
        ...


class ConditionNode:
    """Leaf that exposes one named typed guard."""

    def __init__(self, name: str, predicate: PolicyPredicate, detail: str = "") -> None:
        self.name = name
        self.predicate = predicate
        self.detail = detail

    def tick(self, context: PolicyContext, path: str = "") -> NodeResult:
        node_path = _child_path(path, self.name)
        status = NodeStatus.SUCCESS if self.predicate(context) else NodeStatus.FAILURE
        trace = PolicyTraceStep(node_path=node_path, status=status, detail=self.detail)
        return NodeResult(status=status, trace=(trace,))


class ProposalLeaf:
    """Leaf that creates policy proposals but never executes them."""

    def __init__(self, name: str, factory: ProposalFactory) -> None:
        self.name = name
        self.factory = factory

    def tick(self, context: PolicyContext, path: str = "") -> NodeResult:
        node_path = _child_path(path, self.name)
        proposals = self.factory(context)
        status = NodeStatus.SUCCESS if proposals else NodeStatus.FAILURE
        trace = PolicyTraceStep(
            node_path=node_path,
            status=status,
            detail="proposal_generated" if proposals else "no_applicable_proposal",
            proposal_count=len(proposals),
        )
        return NodeResult(status=status, proposals=proposals, trace=(trace,))


class SelectorNode:
    """Try named child branches in order and retain the complete trace."""

    def __init__(self, name: str, children: Sequence[PolicyNode]) -> None:
        self.name = name
        self.children = tuple(children)

    def tick(self, context: PolicyContext, path: str = "") -> NodeResult:
        node_path = _child_path(path, self.name)
        trace: list[PolicyTraceStep] = []
        for child in self.children:
            result = child.tick(context, node_path)
            trace.extend(result.trace)
            if result.status is not NodeStatus.FAILURE:
                trace.append(
                    PolicyTraceStep(
                        node_path=node_path,
                        status=result.status,
                        detail=f"selected:{child.name}",
                        proposal_count=len(result.proposals),
                    )
                )
                return NodeResult(status=result.status, proposals=result.proposals, trace=tuple(trace))
        trace.append(PolicyTraceStep(node_path=node_path, status=NodeStatus.FAILURE, detail="all_children_failed"))
        return NodeResult(status=NodeStatus.FAILURE, trace=tuple(trace))


class UtilitySelectorNode:
    """Evaluate every child and rank all proposals at one choice point."""

    def __init__(
        self,
        name: str,
        children: Sequence[PolicyNode],
        arbiter: UtilityArbiter | None = None,
    ) -> None:
        """Create an order-independent tactical choice point.

        Args:
            name: Stable trace name for this selector.
            children: Proposal-producing tactical branches.
            arbiter: Optional deterministic ranking policy.
        """
        self.name = name
        self.children = tuple(children)
        self.arbiter = arbiter or UtilityArbiter()

    def tick(self, context: PolicyContext, path: str = "") -> NodeResult:
        """Evaluate every branch before selecting the highest-utility proposal."""
        node_path = _child_path(path, self.name)
        proposals: list[PolicyProposal] = []
        trace: list[PolicyTraceStep] = []
        saw_running = False
        for child in self.children:
            result = child.tick(context, node_path)
            trace.extend(result.trace)
            proposals.extend(result.proposals)
            saw_running = saw_running or result.status is NodeStatus.RUNNING

        ranked = self.arbiter.rank(proposals)
        if ranked:
            selected = ranked[0]
            trace.append(
                PolicyTraceStep(
                    node_path=node_path,
                    status=NodeStatus.SUCCESS,
                    detail=f"selected:{selected.source_node}:{selected.score:.3f}",
                    proposal_count=len(ranked),
                )
            )
            return NodeResult(
                status=NodeStatus.SUCCESS,
                proposals=ranked,
                trace=tuple(trace),
            )

        status = NodeStatus.RUNNING if saw_running else NodeStatus.FAILURE
        trace.append(
            PolicyTraceStep(
                node_path=node_path,
                status=status,
                detail="no_rankable_proposals",
            )
        )
        return NodeResult(status=status, trace=tuple(trace))


class SequenceNode:
    """Require every child in order and return proposals from successful leaves."""

    def __init__(self, name: str, children: Sequence[PolicyNode]) -> None:
        self.name = name
        self.children = tuple(children)

    def tick(self, context: PolicyContext, path: str = "") -> NodeResult:
        node_path = _child_path(path, self.name)
        proposals: list[PolicyProposal] = []
        trace: list[PolicyTraceStep] = []
        for child in self.children:
            result = child.tick(context, node_path)
            trace.extend(result.trace)
            proposals.extend(result.proposals)
            if result.status is not NodeStatus.SUCCESS:
                trace.append(
                    PolicyTraceStep(
                        node_path=node_path,
                        status=result.status,
                        detail=f"stopped:{child.name}",
                        proposal_count=len(proposals),
                    )
                )
                return NodeResult(status=result.status, proposals=tuple(proposals), trace=tuple(trace))
        trace.append(
            PolicyTraceStep(
                node_path=node_path,
                status=NodeStatus.SUCCESS,
                detail="all_children_succeeded",
                proposal_count=len(proposals),
            )
        )
        return NodeResult(status=NodeStatus.SUCCESS, proposals=tuple(proposals), trace=tuple(trace))


def _child_path(parent: str, child: str) -> str:
    """Build a stable slash-delimited trace path."""
    return f"{parent}/{child}" if parent else child
