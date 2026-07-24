"""Session-subjective revalidation after committed voluntary movement steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time

from server.agent_protocol.observation import (
    KnowledgeState,
    ObservationEntityFact,
    ObservationSnapshot,
    SubjectiveWorldState,
)
from server.agent_protocol.observation_replay import (
    apply_observation_frame,
    materialize_snapshot,
)
from server.agent_runtime.observation_projector import iter_observation_frames
from dnd.core.action_execution import (
    MovementContinuationDecision,
    MovementContinuationResult,
    MovementStepBoundary,
)


class MovementRevalidationCause(str, Enum):
    """Decision-relevant subjective change discovered after movement."""

    NEWLY_VISIBLE_HOSTILE = "newly_visible_hostile"
    NEWLY_VISIBLE_HAZARD = "newly_visible_hazard"
    ACTOR_STATE_CHANGED = "actor_state_changed"


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
        cause = _movement_revalidation_cause(
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


def _movement_revalidation_cause(
    before: SubjectiveWorldState | None,
    after: SubjectiveWorldState | None,
    actor_uuid: str,
) -> MovementRevalidationCause | None:
    """Return the highest-priority material subjective change."""
    if before is None or after is None:
        return None
    if _newly_visible_hostile(before, after):
        return MovementRevalidationCause.NEWLY_VISIBLE_HOSTILE
    if _newly_visible_hazard(before, after):
        return MovementRevalidationCause.NEWLY_VISIBLE_HAZARD
    if _actor_state_changed(before, after, actor_uuid):
        return MovementRevalidationCause.ACTOR_STATE_CHANGED
    return None


def _newly_visible_hostile(
    before: SubjectiveWorldState,
    after: SubjectiveWorldState,
) -> bool:
    """Return whether a living hostile or unknown contact became visible."""
    controlled = set(after.session.controlled_entity_uuids)
    controlled_factions = {
        fact.faction
        for entity_uuid in controlled
        for fact in [after.known_entities.get(entity_uuid)]
        if fact is not None and fact.faction is not None
    }
    for entity_uuid, fact in after.known_entities.items():
        if (
            entity_uuid in controlled
            or fact.controlled
            or fact.is_dead is True
            or fact.knowledge_state is not KnowledgeState.VISIBLE
        ):
            continue
        previous = before.known_entities.get(entity_uuid)
        if (
            previous is not None
            and previous.knowledge_state is KnowledgeState.VISIBLE
        ):
            continue
        if fact.faction is None or fact.faction not in controlled_factions:
            return True
    return False


def _newly_visible_hazard(
    before: SubjectiveWorldState,
    after: SubjectiveWorldState,
) -> bool:
    """Return whether a visible tile or object newly discloses a hazard."""
    for key, tile in after.known_tiles.items():
        if (
            tile.knowledge_state is not KnowledgeState.VISIBLE
            or tile.is_hazardous is not True
        ):
            continue
        previous = before.known_tiles.get(key)
        if (
            previous is None
            or previous.knowledge_state is not KnowledgeState.VISIBLE
            or previous.is_hazardous is not True
        ):
            return True
    for object_uuid, obj in after.known_objects.items():
        if (
            obj.knowledge_state is not KnowledgeState.VISIBLE
            or not _object_is_hazardous(obj.state)
        ):
            continue
        previous = before.known_objects.get(object_uuid)
        if (
            previous is None
            or previous.knowledge_state is not KnowledgeState.VISIBLE
            or not _object_is_hazardous(previous.state)
        ):
            return True
    return False


def _object_is_hazardous(state: dict[str, object]) -> bool:
    """Return explicit object hazard truth without inferring from its name."""
    return state.get("is_hazardous") is True or state.get("hazardous") is True


def _actor_state_changed(
    before: SubjectiveWorldState,
    after: SubjectiveWorldState,
    actor_uuid: str,
) -> bool:
    """Return whether disclosed actor health, death, or conditions changed."""
    prior = before.known_entities.get(actor_uuid)
    current = after.known_entities.get(actor_uuid)
    if prior is None or current is None:
        return False
    return _actor_state_key(prior) != _actor_state_key(current)


def _actor_state_key(
    fact: ObservationEntityFact,
) -> tuple[object, ...]:
    """Return only actor fields that can invalidate the remaining route."""
    return (
        fact.hp,
        fact.normal_hp,
        fact.temporary_hp,
        fact.is_dead,
        tuple(fact.conditions),
        (
            tuple(fact.condition_semantic_keys)
            if fact.condition_semantic_keys is not None
            else None
        ),
    )
