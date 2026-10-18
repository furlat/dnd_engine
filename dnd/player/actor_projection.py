"""Presentation adaptation of the shared native actor fold."""

from dataclasses import replace
from uuid import UUID

from dnd.actor_projection import actor_from_birth, apply_actor_fact_change
from dnd.core.condition_types import ConditionCategory
from dnd.core.events import EntityCreatedEvent, Event, SpatialChangeEvent
from dnd.types.actor_facts import ActorFactChange, ActorState


def without_internal_conditions(actor: ActorState) -> ActorState:
    """The presented actor holds no INTERNAL memberships; their stats stay applied."""
    if not any(row.category is ConditionCategory.INTERNAL for row in actor.conditions):
        return actor
    return replace(actor, conditions=tuple(
        row for row in actor.conditions if row.category is not ConditionCategory.INTERNAL))


def ended_lifetime(event: Event) -> UUID | None:
    """The actor whose lifetime a completed version ends (a terminal release), if any."""
    if isinstance(event, SpatialChangeEvent) and event.terminal_release is not None:
        return event.entity_uuid
    return None


def fold_completed_actors(actors: dict[UUID, ActorState], event: Event, change: ActorFactChange | None) -> None:
    """A completed version's actor after-values, the shared fold's and the session projection's alike: its
    recorded change (the presented fold) and, at a lifetime's end, the actor's removal. A birth is folded
    before (`actor_from_birth`): the version's evidence reads the born actor."""
    if change is not None:
        apply_presented_change(actors, change)
    if (ended := ended_lifetime(event)) is not None:
        actors.pop(ended, None)


def fold_birth(actors: dict[UUID, ActorState], event: Event) -> UUID | None:
    """A completed birth's actor; the born uuid, None when the event is no birth."""
    if not isinstance(event, EntityCreatedEvent):
        return None
    actors[event.entity_uuid] = actor_from_birth(event)
    return event.entity_uuid


def apply_presented_change(actors: dict[UUID, ActorState], change: ActorFactChange) -> tuple[UUID, ...]:
    """The native fold, then the owner presented without INTERNAL memberships; the identities rewritten."""
    written = apply_actor_fact_change(actors, change)
    if change.owner_uuid is not None and change.owner_uuid in written:
        actors[change.owner_uuid] = without_internal_conditions(actors[change.owner_uuid])
    return written
