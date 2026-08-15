"""Resolve trusted runtime claims into one subjective projection authority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional
from uuid import UUID

from server.replication_perspective import (
    PerspectiveEpochRegistry,
    PerspectiveScope,
    perspective_epoch_registry,
)
from server.session import PlayerSession, PlayerType
from server.timeline_contracts import CombatLogProjection


class SubjectiveAuthorityError(ValueError):
    """Raised when a request cannot establish one fail-closed perspective."""


@dataclass(frozen=True)
class ResolvedSubjectiveAuthority:
    """Effective scope and opaque epoch selected by trusted server state."""

    scope: PerspectiveScope
    perspective_epoch_id: str


def resolve_subjective_authority(
    session: PlayerSession,
    *,
    observer_entity_uuids: Optional[Iterable[UUID]] = None,
    active_observer_uuid: Optional[UUID] = None,
    registry: PerspectiveEpochRegistry = perspective_epoch_registry,
) -> ResolvedSubjectiveAuthority:
    """Bind a runtime session to its server-owned subjective perspective."""
    controlled = frozenset(session.controlled_entities)
    requested_observers = (
        None
        if observer_entity_uuids is None
        else frozenset(observer_entity_uuids)
    )
    requested_active_observer = active_observer_uuid
    membership_id = f"game:{session.session_id}"
    authority_epoch = 1
    if requested_observers is not None:
        observers = requested_observers
    elif controlled:
        observers = controlled
    else:
        observers = frozenset(session.observer_entities)
    active_observer = (
        requested_active_observer
        if requested_active_observer is not None
        else session.active_observer_uuid
    )

    if controlled and observers != controlled:
        raise SubjectiveAuthorityError(
            "participant observer set must exactly match ownership"
        )
    if not controlled:
        if session.player_type is not PlayerType.OBSERVER:
            raise SubjectiveAuthorityError(
                "only an observer session may use a zero-control spectator perspective"
            )
        if not observers:
            raise SubjectiveAuthorityError(
                "spectator perspective requires an explicit authorized observer set"
            )
    if active_observer is None:
        raise SubjectiveAuthorityError("subjective perspective requires an active observer")
    if active_observer not in observers:
        raise SubjectiveAuthorityError(
            "active observer does not belong to the authorized observer set"
        )
    scope = PerspectiveScope(
        session_id=str(session.session_id),
        membership_id=membership_id,
        authority_epoch=authority_epoch,
        projection=CombatLogProjection.SUBJECTIVE,
        controlled_entity_uuids=tuple(sorted(str(entity_uuid) for entity_uuid in controlled)),
        observer_entity_uuids=tuple(sorted(str(entity_uuid) for entity_uuid in observers)),
        active_observer_uuid=str(active_observer),
    )
    return ResolvedSubjectiveAuthority(
        scope=scope,
        perspective_epoch_id=registry.resolve(scope),
    )


__all__ = [
    "ResolvedSubjectiveAuthority",
    "SubjectiveAuthorityError",
    "resolve_subjective_authority",
]
