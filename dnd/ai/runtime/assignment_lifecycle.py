"""Shared lifecycle and decision-budget primitives for AI assignments."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final
from uuid import UUID

from dnd.controller import TurnContext
from dnd.entity import Entity


DEFAULT_MAXIMUM_DECISIONS_PER_TURN: Final = 32
DEFAULT_MAXIMUM_CONSECUTIVE_CANCELED_ACTIONS: Final = 3


class AIAssignmentState(str, Enum):
    """Lifecycle shared by native and registered-provider assignments."""

    CREATED = "created"
    STARTED = "started"
    CLOSED = "closed"


@dataclass(slots=True)
class AIDecisionBudget:
    """Own per-turn limits and the assignment-wide decision sequence."""

    maximum_decisions_per_turn: int
    maximum_consecutive_canceled_actions: int
    turn_key: tuple[str, int, int] | None = None
    turn_decisions: int = 0
    consecutive_canceled_actions: int = 0
    decision_sequence: int = 0

    def __post_init__(self) -> None:
        if self.maximum_decisions_per_turn < 1:
            raise ValueError("maximum_decisions_per_turn must be positive")
        if self.maximum_consecutive_canceled_actions < 1:
            raise ValueError(
                "maximum_consecutive_canceled_actions must be positive",
            )

    @property
    def limit_reached(self) -> bool:
        return self.turn_decisions >= self.maximum_decisions_per_turn

    def reset_for_turn(self, turn_key: tuple[str, int, int]) -> bool:
        """Reset turn-scoped counters and report whether the turn changed."""
        if self.turn_key == turn_key:
            return False
        self.turn_key = turn_key
        self.turn_decisions = 0
        self.consecutive_canceled_actions = 0
        return True

    def begin_decision(self) -> int:
        """Consume one decision and return its assignment-wide sequence."""
        if self.limit_reached:
            raise RuntimeError("AI decision budget is exhausted")
        self.turn_decisions += 1
        return self.next_sequence()

    def next_sequence(self) -> int:
        """Reserve one assignment-wide decision identity."""
        self.decision_sequence += 1
        return self.decision_sequence

    def record_resolution(self, *, action_canceled: bool) -> bool:
        """Reduce cancellation streak and report whether it reached its limit."""
        if action_canceled:
            self.consecutive_canceled_actions += 1
        else:
            self.consecutive_canceled_actions = 0
        return (
            self.consecutive_canceled_actions
            >= self.maximum_consecutive_canceled_actions
        )

    def close_turn(self) -> None:
        """Clear turn-scoped state while preserving decision identity history."""
        self.turn_key = None
        self.turn_decisions = 0
        self.consecutive_canceled_actions = 0


def assignment_turn_key(
    entity: Entity,
    context: TurnContext,
) -> tuple[str, int, int]:
    """Build the authoritative turn identity used by every AI executor."""
    return (str(entity.uuid), context.round_number, context.turn_index)


def require_controlled_entities(
    controlled_entity_uuids: tuple[UUID, ...],
) -> list[Entity]:
    """Resolve every controlled entity or fail before assignment execution."""
    entities = [
        entity
        for entity_uuid in controlled_entity_uuids
        for entity in [Entity.get(entity_uuid)]
        if entity is not None
    ]
    if len(entities) != len(controlled_entity_uuids):
        raise ValueError("AI assignment has missing controlled entities")
    return entities


def validate_assignment_ownership(
    controlled_entity_uuids: tuple[UUID, ...],
    entities: list[Entity],
) -> None:
    """Require encounter controller ownership to match an assignment exactly."""
    if {entity.uuid for entity in entities} != set(controlled_entity_uuids):
        raise ValueError(
            "encounter controller ownership does not match AI assignment",
        )


__all__ = [
    "AIAssignmentState",
    "AIDecisionBudget",
    "DEFAULT_MAXIMUM_CONSECUTIVE_CANCELED_ACTIONS",
    "DEFAULT_MAXIMUM_DECISIONS_PER_TURN",
    "assignment_turn_key",
    "require_controlled_entities",
    "validate_assignment_ownership",
]
