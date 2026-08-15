"""Dependency-neutral snapshot pinned for one character deployment."""

from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.core.content.durable_characters import (
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
)
from dnd.types.progression import MulticlassSlotRoundingPolicy


class CharacterDeploymentSnapshot(BaseModel):
    """Exact immutable character heads and rules used to build one runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    character_id: UUID
    character_row_version: int = Field(ge=1)
    display_name: str
    definition: CharacterDefinitionRevisionV2
    holdings: CharacterHoldingsRevision
    loadout: CharacterLoadoutRevisionV1
    expected_ruleset_digest: str
    multiclass_slot_rounding_policy: MulticlassSlotRoundingPolicy
    permissive_multiclass_prerequisites: bool

    @model_validator(mode="after")
    def _validate_pinned_heads(self) -> Self:
        if not self.display_name.strip():
            raise ValueError("character deployment display_name cannot be blank")
        if (
            self.definition.character_id != self.character_id
            or self.holdings.character_id != self.character_id
            or self.loadout.character_id != self.character_id
        ):
            raise ValueError(
                "character deployment revisions must share character_id",
            )
        if (
            self.loadout.based_on_definition_revision
            != self.definition.definition_revision
        ):
            raise ValueError(
                "character deployment loadout must target its definition",
            )
        if self.definition.ruleset_digest != self.expected_ruleset_digest:
            raise ValueError(
                "character deployment ruleset digest does not match definition",
            )
        self.definition.verify_integrity()
        self.holdings.verify_integrity()
        self.loadout.verify_integrity()
        return self


__all__ = ["CharacterDeploymentSnapshot"]
