"""Presentation adaptation of the shared native actor fold."""

from dataclasses import replace
from uuid import UUID

from dnd.actor_projection import apply_actor_fact_change
from dnd.core.condition_types import ConditionCategory
from dnd.types.actor_facts import ActorFactChange, ActorState


def without_internal_conditions(actor: ActorState) -> ActorState:
    """The presented actor holds no INTERNAL memberships; their stats stay applied."""
    if not any(row.category is ConditionCategory.INTERNAL for row in actor.conditions):
        return actor
    return replace(actor, conditions=tuple(
        row for row in actor.conditions if row.category is not ConditionCategory.INTERNAL))


def apply_presented_change(actors: dict[UUID, ActorState], change: ActorFactChange) -> tuple[UUID, ...]:
    """The native fold, then the owner presented without INTERNAL memberships; the identities rewritten."""
    written = apply_actor_fact_change(actors, change)
    if change.owner_uuid is not None and change.owner_uuid in written:
        actors[change.owner_uuid] = without_internal_conditions(actors[change.owner_uuid])
    return written
