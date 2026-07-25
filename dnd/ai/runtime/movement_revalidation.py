"""Subjective movement interruption shared by native and remote controllers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from dnd.ai.contracts.observation import (
    KnowledgeState,
    ObservationEntityFact,
    SubjectiveWorldState,
)
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
class SubjectiveMovementContinuationGuard:
    """Reproject assignment knowledge after each committed voluntary step."""

    actor_uuid: str
    world: SubjectiveWorldState
    project_world: Callable[[], SubjectiveWorldState]
    interruption_causes: list[MovementRevalidationCause] = field(
        default_factory=list
    )

    def after_committed_step(
        self,
        boundary: MovementStepBoundary,
    ) -> MovementContinuationResult:
        """Interrupt only when this assignment learns a material new fact."""
        if str(boundary.actor_uuid) != self.actor_uuid:
            return MovementContinuationResult(
                decision=MovementContinuationDecision.CONTINUE,
                observation_cursor=self.world.observation_cursor,
            )
        before = self.world
        after = self.project_world()
        self.world = after
        cause = movement_revalidation_cause(before, after, self.actor_uuid)
        if cause is None:
            return MovementContinuationResult(
                decision=MovementContinuationDecision.CONTINUE,
                observation_cursor=after.observation_cursor,
            )
        self.interruption_causes.append(cause)
        return MovementContinuationResult(
            decision=MovementContinuationDecision.INTERRUPT,
            reason=cause.value,
            observation_cursor=after.observation_cursor,
        )


def movement_revalidation_cause(
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
    return state.get("is_hazardous") is True or state.get("hazardous") is True


def _actor_state_changed(
    before: SubjectiveWorldState,
    after: SubjectiveWorldState,
    actor_uuid: str,
) -> bool:
    prior = before.known_entities.get(actor_uuid)
    current = after.known_entities.get(actor_uuid)
    if prior is None or current is None:
        return False
    return _actor_state_key(prior) != _actor_state_key(current)


def _actor_state_key(fact: ObservationEntityFact) -> tuple[object, ...]:
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
