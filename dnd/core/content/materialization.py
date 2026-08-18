"""Dependency-neutral contexts supplied to canonical content factories."""

from __future__ import annotations

from enum import Enum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dnd.core.content.identities import (
    ContentDefinitionKind,
    ContentRef,
    validate_namespaced_id,
)


class CreatureDeploymentRole(BaseModel):
    """Stable deployment-local role independent from creature construction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role_id: str = Field(
        description=(
            "Namespaced scenario or deployment role for this creature instance."
        ),
    )

    @field_validator("role_id")
    @classmethod
    def _validate_role_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "role_id")


class CreaturePossessionMode(str, Enum):
    """Whether a creature factory may grant authored default possessions."""

    INCLUDE_DEFAULT_POSSESSIONS = "include_default_possessions"
    STRUCTURE_AND_INTRINSICS_ONLY = "structure_and_intrinsics_only"


class CreatureBuildContext(BaseModel):
    """Runtime deployment facts supplied to one canonical creature factory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime_entity_uuid: UUID = Field(
        description=(
            "Fresh runtime UUID used as both entity UUID and source entity UUID."
        ),
    )
    requested_ref: ContentRef
    display_name: str = Field(min_length=1)
    faction: str | None = None
    position: tuple[int, int]
    deployment_role: CreatureDeploymentRole
    possession_mode: CreaturePossessionMode

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("display_name must not contain surrounding whitespace")
        return value

    @field_validator("faction")
    @classmethod
    def _validate_faction(cls, value: str | None) -> str | None:
        if value is not None and (not value or value != value.strip()):
            raise ValueError(
                "faction must be non-empty and have no surrounding whitespace",
            )
        return value

    @model_validator(mode="after")
    def _validate_creature_definition(self) -> Self:
        if self.requested_ref.definition_kind != ContentDefinitionKind.CREATURE:
            raise ValueError(
                "CreatureBuildContext requires a creature content reference",
            )
        return self


class ItemBuildContext(BaseModel):
    """Runtime ownership and exact identity supplied to an item factory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_entity_uuid: UUID
    requested_ref: ContentRef

    @model_validator(mode="after")
    def _validate_item_definition(self) -> Self:
        if self.requested_ref.definition_kind not in {
            ContentDefinitionKind.ITEM,
            ContentDefinitionKind.ENVIRONMENT_OBJECT,
        }:
            raise ValueError(
                "ItemBuildContext requires an item or environment_object "
                "content reference",
            )
        return self
