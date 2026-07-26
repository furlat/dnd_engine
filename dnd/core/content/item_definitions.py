"""Dependency-neutral persistence semantics for authored item definitions."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class ItemPersistencePolicy(str, Enum):
    """Whether and how an item definition may outlive one encounter runtime."""

    POSSESSION = "possession"
    INTRINSIC = "intrinsic"
    ENCOUNTER_ONLY = "encounter_only"
    ENVIRONMENT = "environment"


class ItemStackCompatibility(str, Enum):
    """Stable rule used to decide whether two durable item rows may merge."""

    RECIPE_DIGEST = "recipe_digest"


class ItemDefinition(BaseModel):
    """Cold item semantics that are not mutable runtime instance state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    persistence_policy: ItemPersistencePolicy
    stack_compatibility: ItemStackCompatibility = (
        ItemStackCompatibility.RECIPE_DIGEST
    )

    @property
    def may_enter_character_holdings(self) -> bool:
        """Return whether settlement may persist this item as a possession."""
        return self.persistence_policy == ItemPersistencePolicy.POSSESSION
