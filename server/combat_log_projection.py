"""Legacy call signature for the shared engine-owned log projector."""

from dataclasses import dataclass
from typing import FrozenSet, Iterable, Optional
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.subjective_combat_log import project_combat_log as project_native_log

SUBJECTIVE_COMBAT_LOG_ENTRY_TYPES = frozenset(CombatLogEntryType)


@dataclass
class CombatLogProjectionContext:
    """Reusable ownership and observer authority for one projection pass."""

    controlled_entity_uuids: FrozenSet[str]
    observer_entity_uuids: FrozenSet[str]


def make_combat_log_projection_context(
    *,
    controlled_entity_uuids: Iterable[str],
    observer_entity_uuids: Optional[Iterable[str]] = None,
) -> CombatLogProjectionContext:
    """Create a context from authoritative ownership and observer scope."""
    controlled = frozenset(controlled_entity_uuids)
    return CombatLogProjectionContext(
        controlled_entity_uuids=controlled,
        observer_entity_uuids=(
            controlled
            if observer_entity_uuids is None
            else frozenset(observer_entity_uuids)
        ),
    )


def project_combat_log(log: CombatLogEntry | None,
                       context: CombatLogProjectionContext) -> CombatLogEntry | None:
    return project_native_log(log,
        controlled_entity_uuids=context.controlled_entity_uuids,
        observer_entity_uuids=context.observer_entity_uuids)
