"""Dependency-neutral authored starting-equipment package contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dnd.core.content.identities import validate_namespaced_id
from dnd.core.equipment_types import EquipmentSlot


class StartingEquipmentPackageEntry(BaseModel):
    """One exact durable possession granted by a starting package."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    quantity: int = Field(default=1, ge=1)
    equipped_slot: EquipmentSlot | None = None

    @field_validator("item_id")
    @classmethod
    def _validate_item_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "item_id")


class StartingEquipmentPackageDefinition(BaseModel):
    """Ordered exact item grants selected during character creation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entries: tuple[StartingEquipmentPackageEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_entries(self) -> "StartingEquipmentPackageDefinition":
        identities = tuple(
            (
                row.item_id,
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
