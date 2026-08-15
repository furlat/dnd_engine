"""Dependency-neutral authored starting-equipment package contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.recipes import ContentRecipe
from dnd.types.equipment import EquipmentSlot


class StartingEquipmentPackageEntry(BaseModel):
    """One exact durable possession granted by a starting package."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recipe: ContentRecipe
    quantity: int = Field(default=1, ge=1)
    equipped_slot: EquipmentSlot | None = None

    @model_validator(mode="after")
    def _validate_item_recipe(self) -> "StartingEquipmentPackageEntry":
        if self.recipe.ref.definition_kind is not ContentDefinitionKind.ITEM:
            raise ValueError(
                "starting equipment entries must reference item recipes",
            )
        self.recipe.verify_integrity()
        return self


class StartingEquipmentPackageDefinition(BaseModel):
    """Ordered exact item grants selected during character creation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entries: tuple[StartingEquipmentPackageEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_entries(self) -> "StartingEquipmentPackageDefinition":
        identities = tuple(
            (
                row.recipe.recipe_digest,
                row.quantity,
                row.equipped_slot.value
                if row.equipped_slot is not None
                else None,
            )
            for row in self.entries
        )
        if len(set(identities)) != len(identities):
            raise ValueError(
                "starting equipment entries must be exact and unique; use "
                "quantity for repeated identical items",
            )
        equipped_slots = tuple(
            row.equipped_slot
            for row in self.entries
            if row.equipped_slot is not None
        )
        if len(set(equipped_slots)) != len(equipped_slots):
            raise ValueError(
                "a starting equipment package cannot equip two items in the "
                "same slot",
            )
        return self


__all__ = [
    "StartingEquipmentPackageDefinition",
    "StartingEquipmentPackageEntry",
]
