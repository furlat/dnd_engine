"""Canonical objective-slot to nullable subjective combat-log projection."""

from __future__ import annotations

from server.combat_log_projection import (
    make_combat_log_projection_context,
    project_combat_log,
)
from server.combat_log_source import CombatLogSourceSlot
from server.player_replication.journal import SubjectiveCombatLogProjectionContext
from server.player_replication_contract import SubjectiveCombatLogFrame


class CanonicalSubjectiveCombatLogProjector:
    """Project one exact source slot without changing its cursor coordinates."""

    def project_combat_log(
        self,
        source: CombatLogSourceSlot,
        context: SubjectiveCombatLogProjectionContext,
    ) -> SubjectiveCombatLogFrame:
        """Return a subjective slot whose entry may be hidden but whose barrier remains."""
        protocol = context.protocol
        perspective = context.perspective
        if source.source_stream_id != protocol.source_stream_id:
            raise ValueError("combat-log slot belongs to another source stream")
        if source.generation_id != protocol.generation_id:
            raise ValueError("combat-log slot belongs to another generation")
        if source.combat_log_cursor != context.next_combat_log_cursor:
            raise ValueError("combat-log source cursor is not contiguous")
        if not source.finalized or not source.causal_cursor_exact:
            raise ValueError("combat-log source slot lacks an exact finalized barrier")

        projection_context = make_combat_log_projection_context(
            controlled_entity_uuids=perspective.controlled_entity_uuids,
            observer_entity_uuids=perspective.observer_entity_uuids,
        )
        projected = project_combat_log(source.entry, projection_context)
        return SubjectiveCombatLogFrame(
            source_stream_id=source.source_stream_id,
            generation_id=source.generation_id,
            perspective_epoch_id=perspective.perspective_epoch_id,
            combat_log_cursor=source.combat_log_cursor,
            event_cursor=source.event_cursor,
            entry=None if projected is None else projected.model_copy(deep=True),
        )


canonical_subjective_combat_log_projector = CanonicalSubjectiveCombatLogProjector()


__all__ = [
    "CanonicalSubjectiveCombatLogProjector",
    "canonical_subjective_combat_log_projector",
]
