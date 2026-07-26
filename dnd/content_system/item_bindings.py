"""Deployment-local bindings between runtime items and durable content recipes."""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from dnd.core.content.identities import validate_sha256
from dnd.core.content.item_definitions import (
    ItemDefinition,
    ItemPersistencePolicy,
)
from dnd.core.content.recipe_presets import ContentRecipePresetRef
from dnd.core.content.recipes import ContentRecipe


class ItemRuntimeOrigin(str, Enum):
    """How one runtime item entered the active deployment."""

    STARTER = "starter"
    PERSISTED = "persisted"
    LOOT = "loot"
    REWARD = "reward"
    INTRINSIC = "intrinsic"
    ENCOUNTER_ONLY = "encounter_only"
    ENVIRONMENT = "environment"


class ItemRuntimeBinding(BaseModel):
    """Exact reconstruction and provenance facts for one runtime item UUID."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime_item_uuid: UUID
    recipe: ContentRecipe
    content_set_digest: str
    origin: ItemRuntimeOrigin
    recipe_preset_ref: ContentRecipePresetRef | None = None
    character_item_id: UUID | None = None

    @field_validator("content_set_digest")
    @classmethod
    def _validate_content_set_digest(cls, value: str) -> str:
        return validate_sha256(value, "content_set_digest")


class ItemRuntimeBindingRegistry:
    """Own item bindings for one engine-runtime generation."""

    def __init__(self) -> None:
        self._bindings: dict[UUID, ItemRuntimeBinding] = {}

    def validate_origin(
        self,
        definition: ItemDefinition,
        origin: ItemRuntimeOrigin,
        character_item_id: UUID | None,
    ) -> None:
        """Reject origins incompatible with the authored persistence policy."""
        allowed = {
            ItemPersistencePolicy.POSSESSION: {
                ItemRuntimeOrigin.STARTER,
                ItemRuntimeOrigin.PERSISTED,
                ItemRuntimeOrigin.LOOT,
                ItemRuntimeOrigin.REWARD,
            },
            ItemPersistencePolicy.INTRINSIC: {
                ItemRuntimeOrigin.INTRINSIC,
            },
            ItemPersistencePolicy.ENCOUNTER_ONLY: {
                ItemRuntimeOrigin.ENCOUNTER_ONLY,
            },
            ItemPersistencePolicy.ENVIRONMENT: {
                ItemRuntimeOrigin.ENVIRONMENT,
            },
        }[definition.persistence_policy]
        if origin not in allowed:
            raise ValueError(
                f"Item origin {origin.value} is incompatible with persistence "
                f"policy {definition.persistence_policy.value}",
            )
        if origin == ItemRuntimeOrigin.PERSISTED:
            if character_item_id is None:
                raise ValueError(
                    "persisted item origin requires character_item_id",
                )
        elif character_item_id is not None:
            raise ValueError(
                "character_item_id is reserved for persisted item origin",
            )

    def bind(
        self,
        binding: ItemRuntimeBinding,
        definition: ItemDefinition,
    ) -> ItemRuntimeBinding:
        """Store one exact binding after validating its definition policy."""
        binding.recipe.verify_integrity()
        self.validate_origin(
            definition,
            binding.origin,
            binding.character_item_id,
        )
        existing = self._bindings.get(binding.runtime_item_uuid)
        if existing is not None:
            if existing == binding:
                return existing
            raise ValueError(
                f"Runtime item {binding.runtime_item_uuid} is already bound",
            )
        self._bindings[binding.runtime_item_uuid] = binding
        return binding

    def require(self, runtime_item_uuid: UUID) -> ItemRuntimeBinding:
        """Return one binding or fail rather than infer from a runtime class."""
        binding = self._bindings.get(runtime_item_uuid)
        if binding is None:
            raise KeyError(f"Runtime item {runtime_item_uuid} is not bound")
        return binding

    def discard(self, runtime_item_uuid: UUID) -> None:
        """Discard one provisional or retired runtime binding if present."""
        self._bindings.pop(runtime_item_uuid, None)

    @property
    def bindings(self):
        """Return an immutable view of all bindings in this generation."""
        return MappingProxyType(dict(self._bindings))

    def reset(self) -> None:
        """Retire every deployment-local binding for an engine reset."""
        self._bindings.clear()


ITEM_RUNTIME_BINDINGS = ItemRuntimeBindingRegistry()
