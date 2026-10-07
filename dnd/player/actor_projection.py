"""Presentation adaptation of the shared native after-value fold."""

from dataclasses import replace

from dnd.actor_projection import (
    actor_from_birth as actor_from_birth, actor_fact_owner as actor_fact_owner,
    apply_actor_fact as apply_recorded_actor_fact,
)
from dnd.core.condition_types import ConditionCategory
from dnd.core.events import Event
from dnd.types.actor_facts import ActorState, ConditionFact


def apply_actor_fact(actor: ActorState, event: Event, condition: ConditionFact | None = None) -> ActorState:
    """Keep the existing presentation membership while sharing native reduction."""
    result = apply_recorded_actor_fact(actor, event, condition)
    if any(row.category is ConditionCategory.INTERNAL for row in result.conditions):
        result = replace(result, conditions=tuple(
            row for row in result.conditions if row.category is not ConditionCategory.INTERNAL
        ))
    return result
