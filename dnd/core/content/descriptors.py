"""Player-facing and tooling-facing metadata for content definitions."""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dnd.core.content.identities import (
    ContentRef,
)
from dnd.core.content.icon_bindings_generated import (
    BUILT_IN_CONTENT_ICON_BINDINGS,
)
from dnd.core.equipment_types import EquipmentRenderLayer, VisualLoadoutSlot


class ContentVisibility(str, Enum):
    """Catalog visibility of a content definition or private behavior."""

    PUBLIC = "public"
    OBSERVED = "observed"
    DEVELOPER = "developer"
    INTERNAL = "internal"


class EquipmentSpritePresentation(BaseModel):
    """One exact actor render layer contributed by an equipped loadout slot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    equipment_slot: VisualLoadoutSlot
    render_layer: EquipmentRenderLayer
    sprite_key: str = Field(min_length=1)
    tint_rgb: int = Field(
        ge=0,
        le=0xFFFFFF,
        description="Exact authored 24-bit RGB tint for this actor layer.",
    )


class ContentPresentation(BaseModel):
    """Cold presentation keys authored by the backend content definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    icon_key: str | None = None
    portrait_key: str | None = None
    sprite_key: str | None = None
    visual_variant_key: str | None = None
    tint_rgb: int | None = Field(
        default=None,
        ge=0,
        le=0xFFFFFF,
        description="Optional authored 24-bit RGB tint for this presentation.",
    )
    vfx_profile: str | None = None
    audio_key: str | None = None
    ui_group: str | None = None
    equipment_sprites: tuple[EquipmentSpritePresentation, ...] = ()

    @field_validator("equipment_sprites")
    @classmethod
    def _normalize_equipment_sprites(
        cls,
        value: tuple[EquipmentSpritePresentation, ...],
    ) -> tuple[EquipmentSpritePresentation, ...]:
        layer_keys = [
            (row.equipment_slot, row.render_layer)
            for row in value
        ]
        if len(layer_keys) != len(set(layer_keys)):
            raise ValueError(
                "equipment presentation slot/layer pairs must be unique",
            )
        return tuple(sorted(
            value,
            key=lambda row: (
                row.equipment_slot.value,
                row.render_layer.value,
            ),
        ))


def compute_safe_content_presentation_hash(
    presentation: ContentPresentation,
) -> str:
    """Hash exactly the presentation-only payload disclosed to players."""
    encoded = json.dumps(
        {
            "contract_version": 1,
            "presentation": presentation.model_dump(mode="json"),
        },
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ContentOrdering(BaseModel):
    """Stable catalog grouping and order independent of display labels."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sort_group: str = "default"
    sort_order: int = 0


class ContentDescriptorSpec(BaseModel):
    """Descriptor facts authored before a definition contract hash exists."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    display_name: str = Field(min_length=1)
    description: str = ""
    tags: tuple[str, ...] = ()
    visibility: ContentVisibility
    presentation: ContentPresentation = Field(default_factory=ContentPresentation)
    ordering: ContentOrdering = Field(default_factory=ContentOrdering)
    related_content_refs: tuple[ContentRef, ...] = ()

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted(set(value)))
        if any(not tag or tag != tag.casefold() for tag in normalized):
            raise ValueError("descriptor tags must be non-empty lowercase strings")
        return normalized


class ContentDescriptor(ContentDescriptorSpec):
    """Complete descriptor bound to an exact content reference."""

    ref: ContentRef

    @classmethod
    def from_spec(
        cls,
        ref: ContentRef,
        spec: ContentDescriptorSpec,
    ) -> Self:
        """Bind an authored descriptor spec to an exact definition."""
        icon_key, has_exact_icon_binding = resolve_content_icon_key(
            ref,
            spec.presentation.icon_key,
        )
        if has_exact_icon_binding:
            spec = ContentDescriptorSpec.model_validate({
                **spec.model_dump(mode="python"),
                "presentation": ContentPresentation.model_validate({
                    **spec.presentation.model_dump(mode="python"),
                    "icon_key": icon_key,
                }),
            })
        return cls.model_validate({"ref": ref, **spec.model_dump()})


def resolve_content_icon_key(
    ref: ContentRef,
    authored_icon_key: str | None,
) -> tuple[str | None, bool]:
    """Return an exact built-in key, or preserve an external authored key.

    The boolean distinguishes an explicit built-in null disposition from an
    external reference that has no generated binding row.
    """
    exact_icon_identity = f"{ref.identity_key}#{ref.definition_contract_hash}"
    icon_binding = BUILT_IN_CONTENT_ICON_BINDINGS.get(exact_icon_identity)
    if icon_binding is None:
        return authored_icon_key, False
    (
        expected_contract_hash,
        _,
        icon_key,
        _,
    ) = icon_binding
    if expected_contract_hash != ref.definition_contract_hash:
        raise ValueError(
            "built-in icon binding targets a stale definition contract: "
            f"{ref.identity_key}",
        )
    return icon_key, True
