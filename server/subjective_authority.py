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
from server.runtime_authority import RuntimeProjectionAuthority, RuntimeScope
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
    authority: Optional[RuntimeProjectionAuthority],
    *,
    observer_entity_uuids: Optional[Iterable[UUID]] = None,
    active_observer_uuid: Optional[UUID] = None,
    allow_standalone: bool = False,
    registry: PerspectiveEpochRegistry = perspective_epoch_registry,
) -> ResolvedSubjectiveAuthority:
    """Bind a runtime session to one server-authorized subjective perspective.

    Hosted requests must carry claims installed by the private gateway-worker
    hop.  Direct single-server development has no gateway; callers must opt in
    explicitly with ``allow_standalone=True`` rather than silently treating a
    query-string session id as a credential.
    """
    controlled = frozenset(session.controlled_entities)
    requested_observers = (
        None
        if observer_entity_uuids is None
        else frozenset(observer_entity_uuids)
    )
    requested_active_observer = active_observer_uuid
    if authority is None:
        if not allow_standalone:
            raise SubjectiveAuthorityError("trusted runtime authority is required")
        membership_id = f"standalone:{session.session_id}"
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
    else:
        if (
            RuntimeScope.SUBJECTIVE_OBSERVE not in authority.scopes
            and RuntimeScope.ADMINISTER not in authority.scopes
        ):
            raise SubjectiveAuthorityError("runtime authority lacks subjective observation scope")
        if authority.runtime_session_id != session.session_id:
            raise SubjectiveAuthorityError("runtime authority belongs to another runtime session")
        if authority.controlled_entity_uuids != controlled:
            raise SubjectiveAuthorityError("runtime authority ownership does not match worker session")
        membership_id = str(authority.membership_id)
        authority_epoch = authority.authority_epoch
        observers = authority.observer_entity_uuids
        active_observer = authority.active_observer_uuid
        if requested_observers is not None and requested_observers != observers:
            raise SubjectiveAuthorityError(
                "requested observer set does not match runtime authority"
            )
        if (
            requested_active_observer is not None
            and requested_active_observer != active_observer
        ):
            raise SubjectiveAuthorityError(
                "requested active observer does not match runtime authority"
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
