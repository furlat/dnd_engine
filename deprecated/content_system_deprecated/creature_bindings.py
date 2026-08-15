"""Deployment-local bindings between runtime creatures and authored recipes."""

from __future__ import annotations

from types import MappingProxyType
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from dnd.core.content.identities import ContentDefinitionKind, validate_sha256
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.content.recipes import ContentRecipe


class CreatureRuntimeBinding(BaseModel):
    """Exact construction and deployment facts for one runtime entity UUID."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime_entity_uuid: UUID
    recipe: ContentRecipe
    content_set_digest: str
    deployment_role: CreatureDeploymentRole
    possession_mode: CreaturePossessionMode

    @field_validator("content_set_digest")
    @classmethod
    def _validate_content_set_digest(cls, value: str) -> str:
        return validate_sha256(value, "content_set_digest")

    @model_validator(mode="after")
    def _validate_creature_recipe(self) -> "CreatureRuntimeBinding":
        if self.recipe.ref.definition_kind != ContentDefinitionKind.CREATURE:
            raise ValueError(
                "CreatureRuntimeBinding recipe must reference a creature",
            )
        return self


class CreatureRuntimeBindingRegistry:
    """Own exact creature bindings for one engine-runtime generation."""

    def __init__(self) -> None:
        self._bindings: dict[UUID, CreatureRuntimeBinding] = {}

    def bind(
        self,
        binding: CreatureRuntimeBinding,
    ) -> CreatureRuntimeBinding:
        """Store one exact binding without inferring from class or display name."""
        binding.recipe.verify_integrity()
        existing = self._bindings.get(binding.runtime_entity_uuid)
        if existing is not None:
            if existing == binding:
                return existing
            raise ValueError(
                f"Runtime creature {binding.runtime_entity_uuid} is already bound",
            )
        self._bindings[binding.runtime_entity_uuid] = binding
        return binding

    def require(self, runtime_entity_uuid: UUID) -> CreatureRuntimeBinding:
        """Return one exact binding or fail when the entity was not materialized."""
        binding = self._bindings.get(runtime_entity_uuid)
        if binding is None:
            raise KeyError(
                f"Runtime creature {runtime_entity_uuid} is not bound",
            )
        return binding

    def discard(self, runtime_entity_uuid: UUID) -> None:
        """Discard one provisional or retired creature binding if present."""
        self._bindings.pop(runtime_entity_uuid, None)

    @property
    def bindings(self):
        """Return an immutable snapshot of this generation's bindings."""
        return MappingProxyType(dict(self._bindings))

    def reset(self) -> None:
        """Retire every creature binding owned by the current generation."""
        self._bindings.clear()


CREATURE_RUNTIME_BINDINGS = CreatureRuntimeBindingRegistry()
