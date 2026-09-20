"""Finite native context for fear of a residue and its paid entry retreat."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ResidueFearOrigin(BaseModel):
    """The actual tile condition and entry direction that frightened an actor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tile_uuid: UUID
    condition_uuid: UUID
    position: tuple[int, int]
    retreat_position: tuple[int, int] | None
    entry_event_uuid: UUID


class PaidEntryRetreat(BaseModel):
    """An applied condition's request to stop entry and attempt ordinary movement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    destination: tuple[int, int] | None
