"""Dependency-neutral context for one concrete spell execution.

The runtime action UUID is not a rules identity.  Once the declaration exists,
the spell event lineage becomes the exact causal key shared by every target
application in that cast.  Low-level spell-damage contributors can therefore
apply once per cast without importing ``SpellAction`` or ``Entity``.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator
from uuid import UUID

from dnd.core.modifiers import DamageType


@dataclass(slots=True)
class SpellExecutionState:
    """Current spell execution facts visible to lower-level damage helpers."""

    source_entity_uuid: UUID
    damage_type: DamageType | None
    lineage_uuid: UUID | None = None


_CURRENT_SPELL_EXECUTION: ContextVar[SpellExecutionState | None] = ContextVar(
    "dnd_current_spell_execution",
    default=None,
)


@contextmanager
def spell_execution_scope(
    *,
    source_entity_uuid: UUID,
    damage_type: DamageType | None,
) -> Iterator[SpellExecutionState]:
    """Open one isolated spell-execution context."""

    state = SpellExecutionState(
        source_entity_uuid=source_entity_uuid,
        damage_type=damage_type,
    )
    token = _CURRENT_SPELL_EXECUTION.set(state)
    try:
        yield state
    finally:
        _CURRENT_SPELL_EXECUTION.reset(token)


def bind_spell_execution_lineage(lineage_uuid: UUID) -> None:
    """Bind the current scope to the declaration's exact event lineage."""

    state = _CURRENT_SPELL_EXECUTION.get()
    if state is None:
        raise RuntimeError("spell lineage requires an active execution scope")
    if state.lineage_uuid is not None and state.lineage_uuid != lineage_uuid:
        raise RuntimeError("spell execution scope already has another lineage")
    state.lineage_uuid = lineage_uuid


def current_spell_execution() -> SpellExecutionState | None:
    """Return the current isolated spell execution, when one is active."""

    return _CURRENT_SPELL_EXECUTION.get()


__all__ = [
    "SpellExecutionState",
    "bind_spell_execution_lineage",
    "current_spell_execution",
    "spell_execution_scope",
]
