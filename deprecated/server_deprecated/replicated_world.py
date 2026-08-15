"""Projection-neutral world consumed by live play and replay reducers.

The transport structure is deliberately independent of HTTP, sessions, and
engine registries.  Subjective player replication and authorized objective
replay use the same shape; only the producer's projection policy differs.
"""

from __future__ import annotations

from typing import Dict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from server.world_contracts import (
    APIEquipmentOverview,
    APIGameState,
    APIVisibilityResponse,
)


class ReplicatedWorld(BaseModel):
    """One complete reducer seed under an explicit external projection.

    Equipment belongs in the world rather than a command-response side
    channel: entity appearance and subsequent equipment completion events must
    reduce from the same initial value during live play and ended-game replay.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: APIGameState = Field(description="Projected grid, entities, encounter, and objects.")
    visibility: APIVisibilityResponse = Field(description="Projected observer visibility state.")
    equipment_by_entity: Dict[str, APIEquipmentOverview] = Field(
        default_factory=dict,
        description="Projected equipment reducer seeds keyed by entity UUID.",
    )

    @model_validator(mode="after")
    def validate_equipment_entities(self) -> "ReplicatedWorld":
        """Reject equipment rows that have no entity in the projected state."""
        entity_uuids = {entity.uuid for entity in self.state.entities}
        unknown = sorted(set(self.equipment_by_entity) - entity_uuids)
        if unknown:
            raise ValueError(
                "equipment rows reference entities absent from projected state: "
                f"{unknown}"
            )
        return self


__all__ = ["ReplicatedWorld"]
