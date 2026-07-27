"""Dependency-neutral schema-2 character-build and premade contracts."""

from __future__ import annotations

import hashlib
import json
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dnd.core.content.identities import (
    ContentDefinitionKind,
    validate_namespaced_id,
)
from dnd.core.content.durable_characters import (
    AbilityScoreAllocation,
    BuildChoiceSelection,
    CharacterAppearanceSelection,
    ClassLevelEntry,
    FeatureToggleSelection,
    FlexibleAbilityBonusSelection,
    PreparedSpellSourceLoadout,
)
from dnd.core.content.identities import ContentRef
from dnd.core.content.recipes import ContentRecipe
from dnd.core.equipment_types import EquipmentSlot


class CharacterBuildDraft(BaseModel):
    """Client-owned structural selections before server normalization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    body_recipe: ContentRecipe
    species_ref: ContentRef
    species_variant_ref: ContentRef | None = None
    background_ref: ContentRef
    immutable_origin_choices: tuple[BuildChoiceSelection, ...] = ()
    appearance: CharacterAppearanceSelection
    base_ability_scores: AbilityScoreAllocation
    flexible_ability_bonuses: FlexibleAbilityBonusSelection
    class_levels: tuple[ClassLevelEntry, ...] = Field(
        min_length=1,
        max_length=20,
    )
    premade_id: str | None = None


class CharacterLoadoutDraft(BaseModel):
    """Client-owned mutable loadout selections before server normalization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prepared_spells: tuple[PreparedSpellSourceLoadout, ...] = ()
    feature_toggles: tuple[FeatureToggleSelection, ...] = ()


def compute_premade_build_digest(
    *,
    schema_version: Literal[2],
    premade_id: str,
    display_name: str,
    build: CharacterBuildDraft,
    loadout: CharacterLoadoutDraft,
) -> str:
    """Authenticate one exact schema-2 definition and loadout draft."""

    payload = {
        "schema_version": schema_version,
        "premade_id": premade_id,
        "display_name": display_name,
        "build": build.model_dump(mode="json"),
        "loadout": loadout.model_dump(mode="json"),
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


class PremadeCharacterBuild(BaseModel):
    """One exact creator preset that fills the canonical creation request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[2] = 2
    premade_id: str
    display_name: str = Field(min_length=1, max_length=80)
    build: CharacterBuildDraft
    loadout: CharacterLoadoutDraft
    premade_digest: str

    @classmethod
    def create(
        cls,
        *,
        premade_id: str,
        display_name: str,
        build: CharacterBuildDraft,
        loadout: CharacterLoadoutDraft,
        schema_version: Literal[2] = 2,
    ) -> Self:
        """Create one premade row with its canonical digest."""

        normalized_display_name = " ".join(display_name.split())
        return cls(
            schema_version=schema_version,
            premade_id=premade_id,
            display_name=normalized_display_name,
            build=build,
            loadout=loadout,
            premade_digest=compute_premade_build_digest(
                schema_version=schema_version,
                premade_id=premade_id,
                display_name=normalized_display_name,
                build=build,
                loadout=loadout,
            ),
        )

    @field_validator("premade_id")
    @classmethod
    def _validate_premade_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "premade_id")

    @field_validator("display_name")
    @classmethod
    def _normalize_display_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("display_name cannot be blank")
        return normalized

    @field_validator("premade_digest")
    @classmethod
    def _validate_premade_digest(cls, value: str) -> str:
        if len(value) != 64 or any(
            character not in "0123456789abcdef"
            for character in value
        ):
            raise ValueError(
                "premade_digest must be a lowercase SHA-256 digest",
            )
        return value

    @model_validator(mode="after")
    def _validate_build(self) -> Self:
        if self.build.premade_id != self.premade_id:
            raise ValueError(
                "premade build identity must match build.premade_id",
            )
        if (
            self.build.body_recipe.ref.definition_kind
            is not ContentDefinitionKind.CREATURE
        ):
            raise ValueError(
                "premade character build requires a creature body recipe",
            )
        self.verify_integrity()
        return self

    def verify_integrity(self) -> None:
        """Reject mutation of the authenticated schema-2 drafts."""

        self.build.body_recipe.verify_integrity()
        expected = compute_premade_build_digest(
            schema_version=self.schema_version,
            premade_id=self.premade_id,
            display_name=self.display_name,
            build=self.build,
            loadout=self.loadout,
        )
        if self.premade_digest != expected:
            raise ValueError(
                "premade_digest does not authenticate the premade build",
            )


__all__ = [
    "CharacterBuildDraft",
    "CharacterLoadoutDraft",
    "PremadeCharacterBuild",
    "StarterHoldingTemplate",
    "compute_premade_build_digest",
]
