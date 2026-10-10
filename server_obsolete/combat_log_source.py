"""Dependency-light objective source records for combat-log replication."""

from __future__ import annotations

from typing import Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.core.combat_log import CombatLogEntry


class CombatLogSourceError(RuntimeError):
    """Raised when the objective combat-log journal cannot prove exact history."""


class CombatLogSourceSlot(BaseModel):
    """Immutable objective source record for one encounter combat-log slot.

    ``causal_cursor_exact`` records whether the source journal captured the
    causal barrier synchronously. Canonical projections consume only finalized,
    exact slots and never infer a barrier after the fact.
    """

    model_config = ConfigDict(frozen=True)

    source_stream_id: str = Field(
        min_length=1,
        description="Opaque encounter/stream namespace owning this cursor.",
    )
    generation_id: str = Field(
        min_length=1,
        description="EventQueue generation containing this source slot.",
    )
    combat_log_cursor: int = Field(
        ge=1,
        description="Cursor after this objective log slot.",
    )
    event_cursor: int = Field(
        ge=0,
        description="Original causal event barrier for this log slot.",
    )
    entry: CombatLogEntry = Field(
        description="Objective combat-log entry stored in the encounter.",
    )
    finalized: bool = Field(
        default=True,
        description="Whether the causal completion cursor has been finalized.",
    )
    causal_cursor_exact: bool = Field(
        default=True,
        description="Whether the cursor was captured synchronously rather than inferred.",
    )


class CombatLogSourceWindow(BaseModel):
    """Atomically captured exact window of one objective combat-log stream."""

    model_config = ConfigDict(frozen=True)

    source_stream_id: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)
    retained_from_cursor: int = Field(
        ge=0,
        description="Oldest consumed cursor from which exact replay is retained.",
    )
    from_cursor: int = Field(
        ge=0,
        description="Consumed source cursor immediately before this window.",
    )
    through_cursor: int = Field(
        ge=0,
        description="Exact source cursor represented through this window.",
    )
    total: int = Field(ge=0, description="Source cursor captured with this window.")
    slots: Tuple[CombatLogSourceSlot, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_exact_window(self) -> "CombatLogSourceWindow":
        """Reject gaps, mixed streams, and unproven causal barriers."""
        if self.retained_from_cursor > self.from_cursor:
            raise ValueError("from_cursor precedes retained combat-log history")
        if self.from_cursor > self.through_cursor:
            raise ValueError("from_cursor must not exceed through_cursor")
        if self.through_cursor > self.total:
            raise ValueError("through_cursor must not exceed total")
        if len(self.slots) != self.through_cursor - self.from_cursor:
            raise ValueError("source slots must cover the exact cursor window")

        previous_event_cursor = -1
        for expected_cursor, slot in enumerate(
            self.slots,
            start=self.from_cursor + 1,
        ):
            if slot.combat_log_cursor != expected_cursor:
                raise ValueError("source slots must be contiguous and ordered")
            if slot.source_stream_id != self.source_stream_id:
                raise ValueError("source slot belongs to another stream")
            if slot.generation_id != self.generation_id:
                raise ValueError("source slot belongs to another generation")
            if not slot.finalized or not slot.causal_cursor_exact:
                raise ValueError("source slot lacks a finalized exact causal cursor")
            if slot.event_cursor < previous_event_cursor:
                raise ValueError("source event cursors must be nondecreasing")
            previous_event_cursor = slot.event_cursor
        return self


__all__ = [
    "CombatLogSourceError",
    "CombatLogSourceSlot",
    "CombatLogSourceWindow",
]
