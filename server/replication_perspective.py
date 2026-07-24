"""Opaque perspective epochs for subjective replication security partitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from server.timeline_contracts import CombatLogProjection


class PerspectiveScope(BaseModel):
    """Effective authority and observer scope represented by one epoch."""

    model_config = ConfigDict(frozen=True)

    session_id: str = Field(min_length=1, description="Runtime session receiving the projection.")
    membership_id: str = Field(
        default="standalone",
        min_length=1,
        description="Durable authority owner, or the explicit standalone boundary.",
    )
    authority_epoch: int = Field(
        default=1,
        ge=1,
        description="Monotonic authority version supplied by the trusted gateway.",
    )
    projection: CombatLogProjection = Field(description="Knowledge projection authorized for this scope.")
    controlled_entity_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Entity ownership contributing to this perspective.",
    )
    observer_entity_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Effective observer set contributing knowledge to this perspective.",
    )
    active_observer_uuid: str = Field(
        min_length=1,
        description="Observer selected for focus within the authorized observer union.",
    )

    def canonical_key(self) -> tuple[object, ...]:
        """Return an order-independent identity for security-relevant scope."""
        return (
            self.session_id,
            self.membership_id,
            self.authority_epoch,
            self.projection.value,
            tuple(sorted(set(self.controlled_entity_uuids))),
            tuple(sorted(set(self.observer_entity_uuids))),
            self.active_observer_uuid,
        )


@dataclass(frozen=True)
class _PerspectiveEpochEntry:
    """Registry row pairing one scope key with its opaque epoch."""

    scope_key: tuple[object, ...]
    epoch_id: str


class PerspectiveEpochRegistry:
    """Issue stable opaque epochs and rotate them on scope changes."""

    def __init__(self) -> None:
        self._entries: Dict[str, _PerspectiveEpochEntry] = {}

    def resolve(self, scope: PerspectiveScope) -> str:
        """Return the current epoch, rotating when effective authority changes."""
        scope_key = scope.canonical_key()
        current = self._entries.get(scope.session_id)
        if current is not None and current.scope_key == scope_key:
            return current.epoch_id

        epoch_id = uuid4().hex
        self._entries[scope.session_id] = _PerspectiveEpochEntry(
            scope_key=scope_key,
            epoch_id=epoch_id,
        )
        return epoch_id

    def clear_session(self, session_id: str) -> None:
        """Invalidate one session's perspective epoch."""
        self._entries.pop(session_id, None)

    def clear_all(self) -> None:
        """Invalidate every cached perspective epoch."""
        self._entries.clear()


perspective_epoch_registry = PerspectiveEpochRegistry()


__all__ = [
    "PerspectiveEpochRegistry",
    "PerspectiveScope",
    "perspective_epoch_registry",
]
