"""Deterministic utility arbitration over typed policy proposals."""

from __future__ import annotations

from typing import Sequence

from ai.policy.contracts import ExecuteIntent, PolicyProposal


class UtilityArbiter:
    """Rank proposals by score with explicit stable tie breaking."""

    def rank(self, proposals: Sequence[PolicyProposal]) -> tuple[PolicyProposal, ...]:
        """Return proposals in deterministic descending utility order."""
        return tuple(sorted(proposals, key=self._sort_key))

    def select(self, proposals: Sequence[PolicyProposal]) -> PolicyProposal | None:
        """Return the highest-ranked proposal, or None for an empty choice set."""
        ranked = self.rank(proposals)
        return ranked[0] if ranked else None

    @staticmethod
    def _sort_key(proposal: PolicyProposal) -> tuple[float, tuple[str, ...], str, str]:
        """Sort high scores first and make equal scores replay-stable."""
        row_id = proposal.intent.row_id if isinstance(proposal.intent, ExecuteIntent) else proposal.intent.kind
        identity_fallback = row_id if not proposal.replay_key else ""
        return (-proposal.score, proposal.replay_key, identity_fallback, proposal.source_node)
