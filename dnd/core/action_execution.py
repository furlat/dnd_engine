"""Dependency-neutral scoped contracts for controller-aware action execution."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol
from uuid import UUID


class MovementContinuationDecision(str, Enum):
    """Controller decision after one voluntary movement step commits."""

    CONTINUE = "continue"
    INTERRUPT = "interrupt"


class MovementTerminationReason(str, Enum):
    """Reason an authoritative voluntary movement path ended."""

    COMPLETED = "completed"
    COLLISION = "collision"
    INSUFFICIENT_MOVEMENT = "insufficient_movement"
    STEP_CANCELED = "step_canceled"
    INCAPACITATED = "incapacitated"
    DEAD = "dead"
    SUBJECTIVE_REVALIDATION = "subjective_revalidation"
    POSITION_DIVERGED = "position_diverged"
    INVALID_PATH = "invalid_path"
    ACTION_DENIED = "action_denied"
    INVALID_COST = "invalid_cost"


class MovementProvocationPolicy(str, Enum):
    """Objective source-exit reaction policy for one movement leg."""

    ORDINARY_EXIT = "ordinary_exit"
    DOES_NOT_PROVOKE = "does_not_provoke"


@dataclass(frozen=True, slots=True)
class MovementStepBoundary:
    """Truth committed by one voluntary movement step before revalidation."""

    actor_uuid: UUID
    movement_event_uuid: UUID
    movement_lineage_uuid: UUID
    step_event_uuid: UUID
    from_position: tuple[int, int]
    to_position: tuple[int, int]
    objective_position: tuple[int, int]
    step_movement_cost: int
    traversed_path: tuple[tuple[int, int], ...]
    movement_spent: int
    movement_remaining: int
    source_event_cursor_start: int
    source_event_cursor_end: int


@dataclass(frozen=True, slots=True)
class MovementContinuationResult:
    """Controller response to one committed voluntary movement boundary."""

    decision: MovementContinuationDecision
    reason: Optional[str] = None
    observation_cursor: Optional[int] = None


class MovementContinuationGuard(Protocol):
    """Dependency-neutral observer of committed voluntary movement steps."""

    def after_committed_step(
        self,
        boundary: MovementStepBoundary,
    ) -> MovementContinuationResult:
        """Return whether the current path should continue."""
        ...


_movement_continuation_guard: ContextVar[
    Optional[MovementContinuationGuard]
] = ContextVar("movement_continuation_guard", default=None)


@contextmanager
def movement_continuation_scope(
    guard: MovementContinuationGuard,
) -> Iterator[None]:
    """Install one controller guard for the current action execution scope."""
    token = _movement_continuation_guard.set(guard)
    try:
        yield
    finally:
        _movement_continuation_guard.reset(token)


def revalidate_after_committed_movement_step(
    boundary: MovementStepBoundary,
) -> MovementContinuationResult:
    """Invoke the active guard or continue when execution is unguarded."""
    guard = _movement_continuation_guard.get()
    if guard is None:
        return MovementContinuationResult(
            decision=MovementContinuationDecision.CONTINUE,
        )
    return guard.after_committed_step(boundary)
