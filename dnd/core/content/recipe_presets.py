"""Named, authenticated recipes for curated content variants."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dnd.core.content.canonical import canonical_content_sha256
from dnd.core.content.descriptors import ContentDescriptorSpec
from dnd.core.content.identities import validate_namespaced_id, validate_sha256
from dnd.core.content.provenance import ContentProvenance
from dnd.core.content.recipes import ContentRecipe


class ContentRecipePresetRef(BaseModel):
    """Stable pack-owned identity for one curated exact recipe."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pack_id: str = Field(description="Pack that authors and owns this preset.")
    preset_id: str = Field(
        description="Namespaced semantic identity within the owning pack.",
    )
    preset_version: int = Field(ge=1)
    preset_contract_hash: str = Field(
        description=(
            "SHA-256 authenticating the recipe, descriptor, and provenance."
        ),
    )

    @field_validator("pack_id")
    @classmethod
    def _validate_pack_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "pack_id")

    @field_validator("preset_id")
    @classmethod
    def _validate_preset_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "preset_id")

    @field_validator("preset_contract_hash")
    @classmethod
    def _validate_contract_hash(cls, value: str) -> str:
        return validate_sha256(value, "preset_contract_hash")

    @property
    def identity_key(self) -> str:
        """Return the hash-independent registry identity."""
        return (
            f"{self.pack_id}:recipe_preset:"
            f"{self.preset_id}@{self.preset_version}"
        )


def compute_recipe_preset_contract_hash(
    *,
    recipe: ContentRecipe,
    descriptor: ContentDescriptorSpec,
    provenance: ContentProvenance,
) -> str:
    """Hash every authored fact that gives one preset its meaning."""
    payload = {
        "contract_version": 1,
        "recipe": recipe.model_dump(mode="json"),
        "descriptor": descriptor.model_dump(mode="json"),
        "provenance": provenance.model_dump(mode="json"),
    }
    return canonical_content_sha256(payload)


class ContentRecipePreset(BaseModel):
    """One named catalog choice backed by an exact constructible recipe."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: ContentRecipePresetRef
    recipe: ContentRecipe
    descriptor: ContentDescriptorSpec
    provenance: ContentProvenance

    @classmethod
    def create(
        cls,
        *,
        pack_id: str,
        preset_id: str,
        preset_version: int,
        recipe: ContentRecipe,
        descriptor: ContentDescriptorSpec,
        provenance: ContentProvenance,
    ) -> Self:
        """Create a preset whose reference authenticates its complete payload."""
        return cls(
            ref=ContentRecipePresetRef(
                pack_id=pack_id,
                preset_id=preset_id,
                preset_version=preset_version,
                preset_contract_hash=compute_recipe_preset_contract_hash(
                    recipe=recipe,
                    descriptor=descriptor,
                    provenance=provenance,
                ),
            ),
            recipe=recipe,
            descriptor=descriptor,
            provenance=provenance,
        )

    @model_validator(mode="after")
    def _validate_contract_hash(self) -> Self:
        self.recipe.verify_integrity()
        expected = compute_recipe_preset_contract_hash(
            recipe=self.recipe,
            descriptor=self.descriptor,
            provenance=self.provenance,
        )
        if self.ref.preset_contract_hash != expected:
            raise ValueError(
                "preset_contract_hash does not authenticate the recipe preset",
            )
        return self
