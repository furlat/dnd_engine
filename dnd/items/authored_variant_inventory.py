"""Validated backend-owned inventory of authored item presentation variants."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from dnd.core.equipment_types import EquipmentRenderLayer, VisualLoadoutSlot


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AUTHORED_ITEM_VISUAL_LEDGER_PATH = (
    REPOSITORY_ROOT
    / "content_data"
    / "ledgers"
    / "neuroclient_authored_item_visuals.json"
)


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class AuthoredItemEquipmentLayer(BaseModel):
    """One fully resolved renderer layer from the reviewed source artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    render_layer: EquipmentRenderLayer
    sprite_key: str = Field(min_length=1)
    tint_rgb: int = Field(ge=0, le=0xFFFFFF)


def _normalize_equipment_layers(
    value: tuple[AuthoredItemEquipmentLayer, ...],
) -> tuple[AuthoredItemEquipmentLayer, ...]:
    if not value:
        raise ValueError("authored item presentation requires a render layer")
    render_layers = [row.render_layer for row in value]
    if len(render_layers) != len(set(render_layers)):
        raise ValueError("authored item render layers must be unique")
    return tuple(sorted(value, key=lambda row: row.render_layer.value))


class AuthoredItemBasePresentation(BaseModel):
    """Cold renderer facts inherited by named rows in one source category."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    equipment_layers: tuple[AuthoredItemEquipmentLayer, ...]
    notes: str
    tags: tuple[str, ...]

    @field_validator("equipment_layers")
    @classmethod
    def _validate_equipment_layers(
        cls,
        value: tuple[AuthoredItemEquipmentLayer, ...],
    ) -> tuple[AuthoredItemEquipmentLayer, ...]:
        return _normalize_equipment_layers(value)


class AuthoredItemVariantInventoryRow(BaseModel):
    """One exact named sub-item and its migration classification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    display_name: str = Field(min_length=1)
    inventory_id: str = Field(min_length=1)
    mechanical_factory_identity: str | None
    notes: str
    preset_id: str | None
    source_order: int = Field(ge=0)
    source_visual_variant_id: str = Field(min_length=1)
    equipment_layers: tuple[AuthoredItemEquipmentLayer, ...]
    tags: tuple[str, ...]
    visual_variant_id: str | None

    @field_validator("equipment_layers")
    @classmethod
    def _validate_equipment_layers(
        cls,
        value: tuple[AuthoredItemEquipmentLayer, ...],
    ) -> tuple[AuthoredItemEquipmentLayer, ...]:
        return _normalize_equipment_layers(value)


class AuthoredItemFactoryPresentationBinding(BaseModel):
    """One exact installed factory and slot receiving a category presentation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    equipment_slot: VisualLoadoutSlot
    factory_identity: str = Field(min_length=1)
    root_presentation_owner: bool


class AuthoredItemVariantCategory(BaseModel):
    """One mechanical base and every authored named presentation row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_category: str = Field(min_length=1)
    base_presentation: AuthoredItemBasePresentation
    classification: Literal[
        "supported_existing_factory",
        "unsupported_missing_factory",
    ]
    equipment_slot: VisualLoadoutSlot
    factory_presentation_bindings: tuple[
        AuthoredItemFactoryPresentationBinding,
        ...,
    ]
    mechanical_factory_identity: str | None
    primary_render_layer: EquipmentRenderLayer
    source_order: int = Field(ge=0)
    unsupported_reason: str | None
    variants: tuple[AuthoredItemVariantInventoryRow, ...]

    @model_validator(mode="after")
    def _validate_classification(self) -> Self:
        supported = self.classification == "supported_existing_factory"
        if supported:
            if self.mechanical_factory_identity is None:
                raise ValueError("supported category requires a factory")
            if self.unsupported_reason is not None:
                raise ValueError("supported category cannot have an issue reason")
        else:
            if self.mechanical_factory_identity is not None:
                raise ValueError("unsupported category cannot bind a factory")
            if not self.unsupported_reason:
                raise ValueError("unsupported category requires a reason")
            if self.factory_presentation_bindings:
                raise ValueError(
                    "unsupported category cannot bind runtime presentations",
                )
        if supported and not any(
            binding.factory_identity == self.mechanical_factory_identity
            and binding.equipment_slot is self.equipment_slot
            for binding in self.factory_presentation_bindings
        ):
            raise ValueError(
                "supported category must bind its mechanical factory and slot",
            )
        for row in self.variants:
            authored_fields = (
                row.mechanical_factory_identity,
                row.preset_id,
                row.visual_variant_id,
            )
            if supported and any(value is None for value in authored_fields):
                raise ValueError("supported variant has an incomplete binding")
            if not supported and any(
                value is not None for value in authored_fields
            ):
                raise ValueError("unsupported variant cannot enter runtime")
        presentations = (
            self.base_presentation,
            *self.variants,
        )
        for presentation in presentations:
            matches = tuple(
                layer
                for layer in presentation.equipment_layers
                if layer.render_layer is self.primary_render_layer
            )
            if len(matches) != 1:
                raise ValueError(
                    "authored item presentation requires exactly one primary "
                    f"render layer: {self.base_category}",
                )
        return self


class AuthoredItemVariantInventory(BaseModel):
    """Normalized source rows plus explicit raw-identity anomaly evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    categories: tuple[AuthoredItemVariantCategory, ...]
    source_visual_variant_id_collisions: dict[str, tuple[str, ...]]


class AuthoredItemVariantSource(BaseModel):
    """Immutable provenance of the imported NeuroClient source artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    captured_date: str
    license_scope: str
    provenance: str
    repository: str
    repository_relative_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_base_category_count: int = Field(ge=1)


class AuthoredItemVariantLedger(BaseModel):
    """Self-authenticating backend-owned snapshot of the authored inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authored_category_count: int = Field(ge=1)
    authored_variant_count: int = Field(ge=1)
    inventory_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    inventory: AuthoredItemVariantInventory
    schema_version: Literal[3]
    source: AuthoredItemVariantSource

    @model_validator(mode="after")
    def _validate_inventory(self) -> Self:
        if self.authored_category_count != len(self.inventory.categories):
            raise ValueError("authored category count does not match inventory")
        rows = tuple(
            row
            for category in self.inventory.categories
            for row in category.variants
        )
        if self.authored_variant_count != len(rows):
            raise ValueError("authored variant count does not match inventory")
        expected_digest = _canonical_digest(
            self.inventory.model_dump(mode="json"),
        )
        if self.inventory_digest != expected_digest:
            raise ValueError("inventory_digest does not authenticate inventory")

        inventory_ids = [row.inventory_id for row in rows]
        if len(inventory_ids) != len(set(inventory_ids)):
            raise ValueError("authored inventory IDs must be globally unique")
        supported = tuple(
            row
            for category in self.inventory.categories
            if category.classification == "supported_existing_factory"
            for row in category.variants
        )
        preset_ids = [row.preset_id for row in supported]
        if len(preset_ids) != len(set(preset_ids)):
            raise ValueError("supported preset IDs must be globally unique")
        presentation_keys = [
            (
                primary_authored_item_equipment_layer(category, row).sprite_key,
                row.visual_variant_id,
            )
            for category in self.inventory.categories
            if category.classification == "supported_existing_factory"
            for row in category.variants
        ]
        if len(presentation_keys) != len(set(presentation_keys)):
            raise ValueError(
                "supported sprite and visual variant pairs must be unique",
            )

        category_names = [
            category.base_category
            for category in self.inventory.categories
        ]
        if len(category_names) != len(set(category_names)):
            raise ValueError("authored base categories must be unique")
        bindings = tuple(
            binding
            for category in self.inventory.categories
            for binding in category.factory_presentation_bindings
        )
        identities = {
            binding.factory_identity
            for binding in bindings
        }
        for identity in identities:
            owners = tuple(
                binding
                for binding in bindings
                if binding.factory_identity == identity
                and binding.root_presentation_owner
            )
            if len(owners) != 1:
                raise ValueError(
                    "supported factory identity requires exactly one root "
                    f"presentation owner: {identity}",
                )
            slots = [
                binding.equipment_slot
                for binding in bindings
                if binding.factory_identity == identity
            ]
            if len(slots) != len(set(slots)):
                raise ValueError(
                    "factory presentation slots must be unique: "
                    f"{identity}",
                )

        raw_ids: dict[str, list[str]] = {}
        for row in rows:
            raw_ids.setdefault(row.source_visual_variant_id, []).append(
                row.inventory_id,
            )
        collisions = {
            raw_id: tuple(inventory_ids)
            for raw_id, inventory_ids in sorted(raw_ids.items())
            if len(inventory_ids) > 1
        }
        if self.inventory.source_visual_variant_id_collisions != collisions:
            raise ValueError(
                "source visual variant collision evidence is incomplete",
            )
        return self


def primary_authored_item_equipment_layer(
    category: AuthoredItemVariantCategory,
    presentation: AuthoredItemBasePresentation
    | AuthoredItemVariantInventoryRow,
) -> AuthoredItemEquipmentLayer:
    """Return the explicitly classified primary layer for one authored row."""
    matches = tuple(
        layer
        for layer in presentation.equipment_layers
        if layer.render_layer is category.primary_render_layer
    )
    if len(matches) != 1:
        raise ValueError(
            "authored item presentation requires exactly one primary render "
            f"layer: {category.base_category}",
        )
    return matches[0]


AUTHORED_ITEM_VARIANT_LEDGER = AuthoredItemVariantLedger.model_validate_json(
    AUTHORED_ITEM_VISUAL_LEDGER_PATH.read_text(encoding="utf-8"),
)
AUTHORED_ITEM_VARIANT_CATEGORIES = (
    AUTHORED_ITEM_VARIANT_LEDGER.inventory.categories
)
AUTHORED_ITEM_VARIANT_ROWS = tuple(
    row
    for category in AUTHORED_ITEM_VARIANT_CATEGORIES
    for row in category.variants
)
SUPPORTED_AUTHORED_ITEM_VARIANT_ROWS = tuple(
    row
    for category in AUTHORED_ITEM_VARIANT_CATEGORIES
    if category.classification == "supported_existing_factory"
    for row in category.variants
)
UNSUPPORTED_AUTHORED_ITEM_VARIANT_ROWS = tuple(
    row
    for category in AUTHORED_ITEM_VARIANT_CATEGORIES
    if category.classification == "unsupported_missing_factory"
    for row in category.variants
)
SUPPORTED_AUTHORED_ITEM_VARIANTS_BY_PRESENTATION_KEY = MappingProxyType({
    (
        primary_authored_item_equipment_layer(category, row).sprite_key,
        str(row.visual_variant_id),
    ): row
    for category in AUTHORED_ITEM_VARIANT_CATEGORIES
    if category.classification == "supported_existing_factory"
    for row in category.variants
})
