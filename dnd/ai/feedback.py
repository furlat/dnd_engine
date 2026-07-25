"""Dependency-neutral execution feedback reduced into native policy memory."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NativeAIDecisionOutcome(str, Enum):
    """Core-owned result of one admitted or rejected policy decision."""

    EXECUTED = "executed"
    CANCELED = "canceled"
    INTERRUPTED = "interrupted"
    END_TURN = "end_turn"
    REJECTED = "rejected"
    FAILED = "failed"
    LIMIT_REACHED = "limit_reached"


@dataclass(frozen=True, slots=True)
class NativeAIDecisionFeedback:
    """Bounded authoritative feedback supplied to an assignment reducer."""

    decision_id: str
    actor_uuid: str
    epoch_id: str | None
    row_id: str | None
    outcome: NativeAIDecisionOutcome
    event_uuid: str | None = None
    outcome_code: str | None = None
    revalidation_reason: str | None = None
    error_type: str | None = None
    error_message: str | None = None
