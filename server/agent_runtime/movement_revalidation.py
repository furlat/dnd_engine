"""Session-subjective revalidation after committed voluntary movement steps."""

from __future__ import annotations

from dataclasses import dataclass, field
import time

from dnd.ai.contracts.observation import ObservationSnapshot, SubjectiveWorldState
from dnd.ai.contracts.observation_replay import (
    apply_observation_frame,
    materialize_snapshot,
)
from server.agent_runtime.observation_projector import iter_observation_frames
from dnd.ai.runtime.movement_revalidation import (
    MovementRevalidationCause,
    movement_revalidation_cause,
)
from dnd.core.action_execution import (
    MovementContinuationDecision,
    MovementContinuationResult,
    MovementStepBoundary,
)


@dataclass(slots=True)
class SessionMovementContinuationGuard:
    """Reduce one session's new frames and interrupt on material changes."""

    session_id: str
    actor_uuid: str
    world: SubjectiveWorldState
    observation_cursor: int
    interruption_causes: list[MovementRevalidationCause] = field(
        default_factory=list
    )
    processing_samples_ms: list[float] = field(default_factory=list)

    @classmethod
    def from_snapshot(
        cls,
        snapshot: ObservationSnapshot,
        actor_uuid: str,
    ) -> "SessionMovementContinuationGuard":
        """Create a guard from the server's current subjective baseline."""
        return cls(
            session_id=snapshot.session.session_id,
            actor_uuid=actor_uuid,
            world=materialize_snapshot(snapshot),
            observation_cursor=snapshot.observation_cursor,
        )

    @classmethod
    def from_world(
        cls,
        world: SubjectiveWorldState,
        actor_uuid: str,
    ) -> "SessionMovementContinuationGuard":
        """Create a guard from an already-materialized projector world."""
        return cls(
            session_id=world.session.session_id,
            actor_uuid=actor_uuid,
            world=world,
            observation_cursor=world.observation_cursor,
        )

    def after_committed_step(
        self,
        boundary: MovementStepBoundary,
    ) -> MovementContinuationResult:
        """Apply newly projected frames and classify material information."""
        started = time.perf_counter()
        if str(boundary.actor_uuid) != self.actor_uuid:
            return self._finish(
                started,
                MovementContinuationResult(
                    decision=MovementContinuationDecision.CONTINUE,
                    observation_cursor=self.observation_cursor,
                ),
            )
        before = self.world
        response = iter_observation_frames(
            self.session_id,
            since=self.observation_cursor,
            limit=0,
        )
        for frame in response.frames:
            self.world = apply_observation_frame(self.world, frame)
        self.observation_cursor = response.next_observation_cursor
        after = self.world
        cause = movement_revalidation_cause(
            before,
            after,
            self.actor_uuid,
        )
        if cause is None:
            return self._finish(
                started,
                MovementContinuationResult(
                    decision=MovementContinuationDecision.CONTINUE,
                    observation_cursor=self.observation_cursor,
                ),
            )
        self.interruption_causes.append(cause)
        return self._finish(
            started,
            MovementContinuationResult(
                decision=MovementContinuationDecision.INTERRUPT,
                reason=cause.value,
                observation_cursor=self.observation_cursor,
            ),
        )

    def _finish(
        self,
        started: float,
        result: MovementContinuationResult,
    ) -> MovementContinuationResult:
        """Record one guard sample and return its immutable result."""
        self.processing_samples_ms.append(
            round((time.perf_counter() - started) * 1000.0, 6)
        )
        return result
