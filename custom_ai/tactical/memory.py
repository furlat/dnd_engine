"""Typed per-assignment memory and pure reducer functions for tactical AI."""

from __future__ import annotations

from dataclasses import dataclass, field

from dnd.ai.contracts.observation import (
    KnowledgeState,
    ObservationEntityFact,
    SubjectiveWorldState,
)
from dnd.ai.feedback import NativeAIDecisionFeedback, NativeAIDecisionOutcome


MAXIMUM_RETAINED_OUTCOMES = 16


@dataclass(slots=True)
class TacticalActorMemory:
    """Non-world control memory retained for one actor."""

    focused_target_uuid: str | None = None
    turn_key: tuple[int, int] | None = None
    last_epoch_id: str | None = None
    observed_epochs: int = 0
    blocked_row_ids: set[str] = field(default_factory=set)
    recent_outcomes: tuple[NativeAIDecisionOutcome, ...] = ()


@dataclass(frozen=True, slots=True)
class TacticalActorMemorySnapshot:
    """Immutable diagnostic snapshot used without exposing mutable internals."""

    actor_uuid: str
    focused_target_uuid: str | None
    turn_key: tuple[int, int] | None
    last_epoch_id: str | None
    observed_epochs: int
    blocked_row_ids: tuple[str, ...]
    recent_outcomes: tuple[NativeAIDecisionOutcome, ...]


@dataclass(slots=True)
class TacticalPolicyMemory:
    """Assignment-owned memory with isolated state for every controlled actor."""

    actors: dict[str, TacticalActorMemory] = field(default_factory=dict)

    def actor(self, actor_uuid: str) -> TacticalActorMemory:
        """Return actor memory, creating it only for a core reducer."""
        memory = self.actors.get(actor_uuid)
        if memory is None:
            memory = TacticalActorMemory()
            self.actors[actor_uuid] = memory
        return memory

    def known_actor(self, actor_uuid: str) -> TacticalActorMemory | None:
        """Return existing actor memory without mutating assignment state."""
        return self.actors.get(actor_uuid)

    def snapshot(self) -> tuple[TacticalActorMemorySnapshot, ...]:
        """Return a deterministic immutable diagnostic snapshot."""
        return tuple(
            TacticalActorMemorySnapshot(
                actor_uuid=actor_uuid,
                focused_target_uuid=memory.focused_target_uuid,
                turn_key=memory.turn_key,
                last_epoch_id=memory.last_epoch_id,
                observed_epochs=memory.observed_epochs,
                blocked_row_ids=tuple(sorted(memory.blocked_row_ids)),
                recent_outcomes=memory.recent_outcomes,
            )
            for actor_uuid, memory in sorted(self.actors.items())
        )


def reduce_tactical_state(
    memory: TacticalPolicyMemory,
    state: SubjectiveWorldState,
) -> None:
    """Update focus and turn-local exclusions before policy evaluation."""
    epoch = state.current_epoch
    if epoch is None:
        return
    actor_uuid = epoch.actor_uuid
    actor_memory = memory.actor(actor_uuid)
    turn_key = (epoch.round_number, epoch.turn_index)
    if actor_memory.turn_key != turn_key:
        actor_memory.turn_key = turn_key
        actor_memory.blocked_row_ids.clear()
    if actor_memory.last_epoch_id != epoch.epoch_id:
        actor_memory.last_epoch_id = epoch.epoch_id
        actor_memory.observed_epochs += 1

    actor = state.known_entities.get(actor_uuid)
    focused = (
        state.known_entities.get(actor_memory.focused_target_uuid)
        if actor_memory.focused_target_uuid is not None
        else None
    )
    if focused is not None and _is_actionable_hostile(actor, focused):
        return
    candidates = tuple(
        entity
        for entity in state.known_entities.values()
        if _is_actionable_hostile(actor, entity)
    )
    actor_memory.focused_target_uuid = (
        min(candidates, key=lambda entity: _focus_key(actor, entity)).uuid
        if candidates
        else None
    )


def reduce_tactical_feedback(
    memory: TacticalPolicyMemory,
    feedback: NativeAIDecisionFeedback,
) -> None:
    """Retain bounded authoritative failures independently of policy logic."""
    actor_memory = memory.actor(feedback.actor_uuid)
    if (
        feedback.row_id is not None
        and feedback.outcome
        in {
            NativeAIDecisionOutcome.CANCELED,
            NativeAIDecisionOutcome.REJECTED,
            NativeAIDecisionOutcome.FAILED,
        }
    ):
        actor_memory.blocked_row_ids.add(feedback.row_id)
    actor_memory.recent_outcomes = (
        *actor_memory.recent_outcomes,
        feedback.outcome,
    )[-MAXIMUM_RETAINED_OUTCOMES:]


def _is_actionable_hostile(
    actor: ObservationEntityFact | None,
    other: ObservationEntityFact,
) -> bool:
    if (
        other.controlled
        or other.is_dead is True
        or other.knowledge_state
        not in {KnowledgeState.VISIBLE, KnowledgeState.REMEMBERED}
    ):
        return False
    if actor is None or actor.faction is None:
        return True
    return other.faction != actor.faction


def _focus_key(
    actor: ObservationEntityFact | None,
    target: ObservationEntityFact,
) -> tuple[int, int, int, int, str]:
    visible_rank = 0 if target.knowledge_state is KnowledgeState.VISIBLE else 1
    known_hp = target.normal_hp if target.normal_hp is not None else target.hp
    hp_unknown = 1 if known_hp is None else 0
    hp_value = known_hp if known_hp is not None else 0
    distance = _known_distance(actor, target)
    distance_value = distance if distance is not None else 1_000_000
    return (
        visible_rank,
        hp_unknown,
        hp_value,
        distance_value,
        target.uuid,
    )


def _known_distance(
    actor: ObservationEntityFact | None,
    target: ObservationEntityFact,
) -> int | None:
    if actor is None or actor.position is None or target.position is None:
        return None
    return max(
        abs(actor.position[0] - target.position[0]),
        abs(actor.position[1] - target.position[1]),
    )

