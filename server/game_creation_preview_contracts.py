"""Exact production projections for normalized encounter recipes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from server.player_replication_contract import EntityVisualLoadout
from server.world_contracts import APIEntitySummary


class GameCreationMemberVisualPreview(BaseModel):
    """One recipe member projected through the production renderer DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    member_id: str = Field(min_length=1)
    deployment_role: str = Field(min_length=1)
    entity: APIEntitySummary
    visual_loadout: EntityVisualLoadout

    @model_validator(mode="after")
    def _validate_projection_owner(
        self,
    ) -> "GameCreationMemberVisualPreview":
        if self.entity.uuid != self.visual_loadout.entity_uuid:
            raise ValueError(
                "preview entity and visual loadout must share one UUID",
            )
        return self


class GameCreationRosterVisualPreview(BaseModel):
    """Ordered production projection of one normalized roster slot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    roster_slot_id: str = Field(min_length=1)
    roster_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    members: tuple[GameCreationMemberVisualPreview, ...] = Field(
        min_length=1,
    )

    @model_validator(mode="after")
    def _validate_member_identity(
        self,
    ) -> "GameCreationRosterVisualPreview":
        member_ids = [member.member_id for member in self.members]
        if len(member_ids) != len(set(member_ids)):
            raise ValueError("preview member ids must be unique within a roster")
        return self


class GameCreationEncounterVisualPreviewResponse(BaseModel):
    """Read-only production projection of one exact encounter recipe."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[2] = 2
    content_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    ruleset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    encounter_recipe_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    rosters: tuple[GameCreationRosterVisualPreview, ...] = Field(
        min_length=2,
    )

    @model_validator(mode="after")
    def _validate_projection_identity(
        self,
    ) -> "GameCreationEncounterVisualPreviewResponse":
        roster_slot_ids = [roster.roster_slot_id for roster in self.rosters]
        if len(roster_slot_ids) != len(set(roster_slot_ids)):
            raise ValueError("preview roster slot ids must be unique")
        entity_uuids = [
            member.entity.uuid
            for roster in self.rosters
            for member in roster.members
        ]
        if len(entity_uuids) != len(set(entity_uuids)):
            raise ValueError("preview entity UUIDs must be globally unique")
        return self


__all__ = [
    "GameCreationEncounterVisualPreviewResponse",
    "GameCreationMemberVisualPreview",
    "GameCreationRosterVisualPreview",
]
