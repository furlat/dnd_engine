"""Dependency-neutral contracts for approved premade character templates."""

from __future__ import annotations

import hashlib
import json
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dnd.core.content.identities import (
    ContentDefinitionKind,
    validate_namespaced_id,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.equipment_types import EquipmentSlot


def compute_premade_template_digest(
    *,
    schema_version: Literal[1],
    premade_id: str,
    creature_recipe: ContentRecipe,
    starter_holdings: tuple["StarterHoldingTemplate", ...],
) -> str:
    """Authenticate one exact structural recipe and ordered starter loadout."""
    payload = {
        "schema_version": schema_version,
        "premade_id": premade_id,
        "creature_recipe": creature_recipe.model_dump(mode="json"),
        "starter_holdings": [
            holding.model_dump(mode="json")
            for holding in starter_holdings
        ],
    }
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class StarterHoldingTemplate(BaseModel):
    """One immutable starter grant with no persistent or runtime instance ID."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recipe: ContentRecipe
    quantity: int = Field(default=1, ge=1)
    equipped_slot: EquipmentSlot | None = None

    @model_validator(mode="after")
    def _validate_item_recipe(self) -> Self:
        if self.recipe.ref.definition_kind != ContentDefinitionKind.ITEM:
            raise ValueError(
                "StarterHoldingTemplate recipe must reference an item "
                "definition",
            )
        self.recipe.verify_integrity()
        return self


class PremadeCharacterTemplate(BaseModel):
    """One approved character definition plus its one-time starter holdings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    premade_id: str
    creature_recipe: ContentRecipe
    starter_holdings: tuple[StarterHoldingTemplate, ...]
    template_digest: str

    @classmethod
    def create(
        cls,
        *,
        premade_id: str,
        creature_recipe: ContentRecipe,
        starter_holdings: tuple[StarterHoldingTemplate, ...],
        schema_version: Literal[1] = 1,
    ) -> Self:
        """Create one template with its canonical digest."""
        return cls(
            schema_version=schema_version,
            premade_id=premade_id,
            creature_recipe=creature_recipe,
            starter_holdings=starter_holdings,
            template_digest=compute_premade_template_digest(
                schema_version=schema_version,
                premade_id=premade_id,
                creature_recipe=creature_recipe,
                starter_holdings=starter_holdings,
            ),
        )

    @field_validator("premade_id")
    @classmethod
    def _validate_premade_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "premade_id")

    @field_validator("template_digest")
    @classmethod
    def _validate_template_digest(cls, value: str) -> str:
        if len(value) != 64 or any(
            character not in "0123456789abcdef"
            for character in value
        ):
            raise ValueError("template_digest must be a lowercase SHA-256 digest")
        return value

    @model_validator(mode="after")
    def _validate_template(self) -> Self:
        if (
            self.creature_recipe.ref.definition_kind
            != ContentDefinitionKind.CREATURE
        ):
            raise ValueError(
                "PremadeCharacterTemplate requires a creature recipe",
            )
        holding_keys = tuple(
            (
                holding.recipe.recipe_digest,
                (
                    holding.equipped_slot.value
                    if holding.equipped_slot is not None
                    else None
                ),
            )
            for holding in self.starter_holdings
        )
        if len(set(holding_keys)) != len(holding_keys):
            raise ValueError(
                "starter_holdings must combine identical recipe/slot grants "
                "through quantity",
            )
        self.verify_integrity()
        return self

    def verify_integrity(self) -> None:
        """Reject mutation of the structural recipe or ordered starter grants."""
        self.creature_recipe.verify_integrity()
        for holding in self.starter_holdings:
            holding.recipe.verify_integrity()
        expected = compute_premade_template_digest(
            schema_version=self.schema_version,
            premade_id=self.premade_id,
            creature_recipe=self.creature_recipe,
            starter_holdings=self.starter_holdings,
        )
        if self.template_digest != expected:
            raise ValueError(
                "template_digest does not authenticate the premade template",
            )


__all__ = [
    "PremadeCharacterTemplate",
    "StarterHoldingTemplate",
    "compute_premade_template_digest",
]
