"""Dependency-neutral durable character and possession revision contracts."""

from __future__ import annotations

import hashlib
import json
from typing import Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from dnd.core.content.identities import (
    ContentDefinitionKind,
    ContentRef,
    validate_namespaced_id,
    validate_sha256,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.equipment_types import EquipmentSlot


def _canonical_sha256(payload: object) -> str:
    """Return the SHA-256 of one exact canonical JSON payload."""
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compute_item_augmentation_digest(
    *,
    content_ref: ContentRef,
    parameters: dict[str, JsonValue],
    durable_state: dict[str, JsonValue],
) -> str:
    """Authenticate one permanent item augmentation record."""
    return _canonical_sha256(
        {
            "content_ref": content_ref.model_dump(mode="json"),
            "parameters": parameters,
            "durable_state": durable_state,
        },
    )


class ItemAugmentationRecord(BaseModel):
    """Permanent item behavior rebuilt through its authored content identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content_ref: ContentRef
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    durable_state: dict[str, JsonValue] = Field(default_factory=dict)
    augmentation_digest: str

    @classmethod
    def create(
        cls,
        *,
        content_ref: ContentRef,
        parameters: dict[str, JsonValue] | None = None,
        durable_state: dict[str, JsonValue] | None = None,
    ) -> Self:
        """Create one augmentation with its exact canonical digest."""
        validated_parameters = parameters or {}
        validated_state = durable_state or {}
        return cls(
            content_ref=content_ref,
            parameters=validated_parameters,
            durable_state=validated_state,
            augmentation_digest=compute_item_augmentation_digest(
                content_ref=content_ref,
                parameters=validated_parameters,
                durable_state=validated_state,
            ),
        )

    @field_validator("augmentation_digest")
    @classmethod
    def _validate_augmentation_digest_shape(cls, value: str) -> str:
        return validate_sha256(value, "augmentation_digest")

    @model_validator(mode="after")
    def _validate_augmentation_digest(self) -> Self:
        self.verify_integrity()
        return self

    def verify_integrity(self) -> None:
        """Reject augmentation parameters or state changed after hashing."""
        expected = compute_item_augmentation_digest(
            content_ref=self.content_ref,
            parameters=self.parameters,
            durable_state=self.durable_state,
        )
        if self.augmentation_digest != expected:
            raise ValueError(
                "augmentation_digest does not authenticate the content "
                "reference, parameters, and durable state",
            )


def compute_character_item_digest(
    *,
    schema_version: Literal[1],
    character_item_id: UUID,
    recipe: ContentRecipe,
    quantity: int,
    remaining_charges: int | None,
    durability_damage: int | None,
    durable_augmentations: tuple[ItemAugmentationRecord, ...],
    equipped_slot: EquipmentSlot | None,
) -> str:
    """Authenticate one exact durable possession record."""
    return _canonical_sha256(
        {
            "schema_version": schema_version,
            "character_item_id": str(character_item_id),
            "recipe": recipe.model_dump(mode="json"),
            "quantity": quantity,
            "remaining_charges": remaining_charges,
            "durability_damage": durability_damage,
            "durable_augmentations": [
                augmentation.model_dump(mode="json")
                for augmentation in durable_augmentations
            ],
            "equipped_slot": (
                equipped_slot.value if equipped_slot is not None else None
            ),
        },
    )


class CharacterItemV1(BaseModel):
    """One durable possession, independent from every runtime item instance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    character_item_id: UUID
    recipe: ContentRecipe
    quantity: int = Field(default=1, ge=1)
    remaining_charges: int | None = Field(default=None, ge=0)
    durability_damage: int | None = Field(default=None, ge=0)
    durable_augmentations: tuple[ItemAugmentationRecord, ...] = ()
    equipped_slot: EquipmentSlot | None = None
    character_item_digest: str

    @classmethod
    def create(
        cls,
        *,
        character_item_id: UUID,
        recipe: ContentRecipe,
        quantity: int = 1,
        remaining_charges: int | None = None,
        durability_damage: int | None = None,
        durable_augmentations: tuple[ItemAugmentationRecord, ...] = (),
        equipped_slot: EquipmentSlot | None = None,
        schema_version: Literal[1] = 1,
    ) -> Self:
        """Create one possession with its exact canonical digest."""
        return cls(
            schema_version=schema_version,
            character_item_id=character_item_id,
            recipe=recipe,
            quantity=quantity,
            remaining_charges=remaining_charges,
            durability_damage=durability_damage,
            durable_augmentations=durable_augmentations,
            equipped_slot=equipped_slot,
            character_item_digest=compute_character_item_digest(
                schema_version=schema_version,
                character_item_id=character_item_id,
                recipe=recipe,
                quantity=quantity,
                remaining_charges=remaining_charges,
                durability_damage=durability_damage,
                durable_augmentations=durable_augmentations,
                equipped_slot=equipped_slot,
            ),
        )

    @field_validator("character_item_digest")
    @classmethod
    def _validate_character_item_digest_shape(cls, value: str) -> str:
        return validate_sha256(value, "character_item_digest")

    @model_validator(mode="after")
    def _validate_character_item(self) -> Self:
        if self.recipe.ref.definition_kind != ContentDefinitionKind.ITEM:
            raise ValueError(
                "CharacterItemV1 recipe must reference an item definition",
            )
        augmentation_digests = tuple(
            augmentation.augmentation_digest
            for augmentation in self.durable_augmentations
        )
        if len(set(augmentation_digests)) != len(augmentation_digests):
            raise ValueError(
                "durable_augmentations contain duplicate augmentation_digest "
                "values",
            )
        if augmentation_digests != tuple(sorted(augmentation_digests)):
            raise ValueError(
                "durable_augmentations must be ordered by augmentation_digest",
            )
        self.verify_integrity()
        return self

    def verify_integrity(self) -> None:
        """Reject any mutation of this durable possession record."""
        self.recipe.verify_integrity()
        for augmentation in self.durable_augmentations:
            augmentation.verify_integrity()
        expected = compute_character_item_digest(
            schema_version=self.schema_version,
            character_item_id=self.character_item_id,
            recipe=self.recipe,
            quantity=self.quantity,
            remaining_charges=self.remaining_charges,
            durability_damage=self.durability_damage,
            durable_augmentations=self.durable_augmentations,
            equipped_slot=self.equipped_slot,
        )
        if self.character_item_digest != expected:
            raise ValueError(
                "character_item_digest does not authenticate the durable item",
            )


def compute_character_definition_digest(
    *,
    character_id: UUID,
    schema_version: Literal[1],
    definition_revision: int,
    creature_recipe: ContentRecipe,
    premade_id: str | None,
    content_set_digest: str,
) -> str:
    """Authenticate one immutable structural character revision."""
    return _canonical_sha256(
        {
            "character_id": str(character_id),
            "schema_version": schema_version,
            "definition_revision": definition_revision,
            "creature_recipe": creature_recipe.model_dump(mode="json"),
            "premade_id": premade_id,
            "content_set_digest": content_set_digest,
        },
    )


class CharacterDefinitionRevision(BaseModel):
    """Immutable structural build from which one runtime creature is rebuilt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    character_id: UUID
    schema_version: Literal[1] = 1
    definition_revision: int = Field(ge=1)
    creature_recipe: ContentRecipe
    premade_id: str | None = None
    content_set_digest: str
    definition_digest: str

    @classmethod
    def create(
        cls,
        *,
        character_id: UUID,
        definition_revision: int,
        creature_recipe: ContentRecipe,
        content_set_digest: str,
        premade_id: str | None = None,
        schema_version: Literal[1] = 1,
    ) -> Self:
        """Create one structural revision with its canonical digest."""
        return cls(
            character_id=character_id,
            schema_version=schema_version,
            definition_revision=definition_revision,
            creature_recipe=creature_recipe,
            premade_id=premade_id,
            content_set_digest=content_set_digest,
            definition_digest=compute_character_definition_digest(
                character_id=character_id,
                schema_version=schema_version,
                definition_revision=definition_revision,
                creature_recipe=creature_recipe,
                premade_id=premade_id,
                content_set_digest=content_set_digest,
            ),
        )

    @field_validator("premade_id")
    @classmethod
    def _validate_premade_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_namespaced_id(value, "premade_id")

    @field_validator("content_set_digest")
    @classmethod
    def _validate_content_set_digest(cls, value: str) -> str:
        return validate_sha256(value, "content_set_digest")

    @field_validator("definition_digest")
    @classmethod
    def _validate_definition_digest_shape(cls, value: str) -> str:
        return validate_sha256(value, "definition_digest")

    @model_validator(mode="after")
    def _validate_definition(self) -> Self:
        if (
            self.creature_recipe.ref.definition_kind
            != ContentDefinitionKind.CREATURE
        ):
            raise ValueError(
                "CharacterDefinitionRevision requires a creature recipe",
            )
        self.verify_integrity()
        return self

    def verify_integrity(self) -> None:
        """Reject any mutation of the structural build or its provenance."""
        self.creature_recipe.verify_integrity()
        expected = compute_character_definition_digest(
            character_id=self.character_id,
            schema_version=self.schema_version,
            definition_revision=self.definition_revision,
            creature_recipe=self.creature_recipe,
            premade_id=self.premade_id,
            content_set_digest=self.content_set_digest,
        )
        if self.definition_digest != expected:
            raise ValueError(
                "definition_digest does not authenticate the character "
                "definition revision",
            )


def compute_character_holdings_digest(
    *,
    character_id: UUID,
    schema_version: Literal[1],
    holdings_revision: int,
    items: tuple[CharacterItemV1, ...],
) -> str:
    """Authenticate one immutable, deterministically ordered holdings revision."""
    return _canonical_sha256(
        {
            "character_id": str(character_id),
            "schema_version": schema_version,
            "holdings_revision": holdings_revision,
            "items": [item.model_dump(mode="json") for item in items],
        },
    )


class CharacterHoldingsRevision(BaseModel):
    """Immutable possessions independently revisioned for one character."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    character_id: UUID
    schema_version: Literal[1] = 1
    holdings_revision: int = Field(ge=1)
    items: tuple[CharacterItemV1, ...] = ()
    holdings_digest: str

    @classmethod
    def create(
        cls,
        *,
        character_id: UUID,
        holdings_revision: int,
        items: tuple[CharacterItemV1, ...] = (),
        schema_version: Literal[1] = 1,
    ) -> Self:
        """Create one holdings revision with its canonical digest."""
        return cls(
            character_id=character_id,
            schema_version=schema_version,
            holdings_revision=holdings_revision,
            items=items,
            holdings_digest=compute_character_holdings_digest(
                character_id=character_id,
                schema_version=schema_version,
                holdings_revision=holdings_revision,
                items=items,
            ),
        )

    @field_validator("holdings_digest")
    @classmethod
    def _validate_holdings_digest_shape(cls, value: str) -> str:
        return validate_sha256(value, "holdings_digest")

    @model_validator(mode="after")
    def _validate_holdings(self) -> Self:
        item_ids = tuple(item.character_item_id for item in self.items)
        if len(set(item_ids)) != len(item_ids):
            raise ValueError(
                "items contain duplicate character_item_id values",
            )
        if item_ids != tuple(sorted(item_ids, key=lambda item_id: item_id.hex)):
            raise ValueError(
                "items must be ordered by character_item_id",
            )
        self.verify_integrity()
        return self

    def verify_integrity(self) -> None:
        """Reject any mutation of the base identity or durable possessions."""
        for item in self.items:
            item.verify_integrity()
        expected = compute_character_holdings_digest(
            character_id=self.character_id,
            schema_version=self.schema_version,
            holdings_revision=self.holdings_revision,
            items=self.items,
        )
        if self.holdings_digest != expected:
            raise ValueError(
                "holdings_digest does not authenticate the character "
                "holdings revision",
            )
