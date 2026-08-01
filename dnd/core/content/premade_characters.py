"""Dependency-neutral character-build and editable creation-plan contracts."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dnd.core.content.canonical import canonical_content_sha256
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


class CharacterCreationPlanKind(str, Enum):
    """Closed authority behind one editable creator roster seed."""

    BLANK_CUSTOM = "blank_custom"
    PREMADE_TEMPLATE = "premade_template"


def compute_character_creation_plan_digest(
    *,
    schema_version: Literal[1],
    plan_id: str,
    plan_kind: CharacterCreationPlanKind,
    display_name: str,
    build: CharacterBuildDraft,
    loadout: CharacterLoadoutDraft,
    character_level_entitlement: int,
    supplemental_holdings: tuple[StarterHoldingTemplate, ...],
    source_premade_id: str | None,
) -> str:
    """Authenticate one editable seed and its creation entitlement."""

    payload = {
        "schema_version": schema_version,
        "plan_id": plan_id,
        "plan_kind": plan_kind.value,
        "display_name": display_name,
        "build": build.model_dump(mode="json"),
        "loadout": loadout.model_dump(mode="json"),
        "character_level_entitlement": character_level_entitlement,
        "supplemental_holdings": [
            row.model_dump(mode="json")
            for row in supplemental_holdings
        ],
        "source_premade_id": source_premade_id,
    }
    return canonical_content_sha256(payload)


class CharacterCreationPlan(BaseModel):
    """One backend-authored editable seed with exact level/item authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    plan_id: str
    plan_kind: CharacterCreationPlanKind
    display_name: str = Field(min_length=1, max_length=80)
    build: CharacterBuildDraft
    loadout: CharacterLoadoutDraft
    character_level_entitlement: int = Field(ge=1, le=20)
    supplemental_holdings: tuple[StarterHoldingTemplate, ...] = ()
    source_premade_id: str | None = None
    plan_digest: str

    @classmethod
    def create(
        cls,
        *,
        plan_id: str,
        plan_kind: CharacterCreationPlanKind,
        display_name: str,
        build: CharacterBuildDraft,
        loadout: CharacterLoadoutDraft,
        character_level_entitlement: int,
        supplemental_holdings: tuple[StarterHoldingTemplate, ...] = (),
        source_premade_id: str | None = None,
    ) -> Self:
        """Create one self-authenticating creation plan."""

        normalized_display_name = " ".join(display_name.split())
        return cls(
            plan_id=plan_id,
            plan_kind=plan_kind,
            display_name=normalized_display_name,
            build=build,
            loadout=loadout,
            character_level_entitlement=character_level_entitlement,
            supplemental_holdings=supplemental_holdings,
            source_premade_id=source_premade_id,
            plan_digest=compute_character_creation_plan_digest(
                schema_version=1,
                plan_id=plan_id,
                plan_kind=plan_kind,
                display_name=normalized_display_name,
                build=build,
                loadout=loadout,
                character_level_entitlement=character_level_entitlement,
                supplemental_holdings=supplemental_holdings,
                source_premade_id=source_premade_id,
            ),
        )

    @field_validator("plan_id")
    @classmethod
    def _validate_plan_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "plan_id")

    @field_validator("source_premade_id")
    @classmethod
    def _validate_source_premade_id(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        return validate_namespaced_id(value, "source_premade_id")

    @model_validator(mode="after")
    def _validate_plan(self) -> Self:
        if len(self.build.class_levels) != self.character_level_entitlement:
            raise ValueError(
                "creation-plan level entitlement must match its seed build",
            )
        if (
            self.plan_kind is CharacterCreationPlanKind.BLANK_CUSTOM
            and (
                self.source_premade_id is not None
                or self.build.premade_id is not None
            )
        ):
            raise ValueError(
                "blank custom plans cannot carry premade identity",
            )
        if self.plan_kind is CharacterCreationPlanKind.PREMADE_TEMPLATE:
            if (
                self.source_premade_id is None
                or self.build.premade_id != self.source_premade_id
            ):
                raise ValueError(
                    "premade plans require one matching source identity",
                )
        expected = compute_character_creation_plan_digest(
            schema_version=self.schema_version,
            plan_id=self.plan_id,
            plan_kind=self.plan_kind,
            display_name=self.display_name,
            build=self.build,
            loadout=self.loadout,
            character_level_entitlement=self.character_level_entitlement,
            supplemental_holdings=self.supplemental_holdings,
            source_premade_id=self.source_premade_id,
        )
        if self.plan_digest != expected:
            raise ValueError(
                "plan_digest does not authenticate the creation plan",
            )
        return self

    def normalize_requested_build(
        self,
        *,
        build: CharacterBuildDraft,
        loadout: CharacterLoadoutDraft,
    ) -> CharacterBuildDraft:
        """Retain premade identity only for the exact authenticated seed."""

        requested_without_premade = build.model_copy(
            update={"premade_id": None},
        )
        source_premade_id = None
        if (
            self.source_premade_id is not None
            and requested_without_premade
            == self.build.model_copy(update={"premade_id": None})
            and loadout == self.loadout
        ):
            source_premade_id = self.source_premade_id
        return build.model_copy(
            update={"premade_id": source_premade_id},
        )


__all__ = [
    "CharacterCreationPlan",
    "CharacterCreationPlanKind",
    "CharacterBuildDraft",
    "CharacterLoadoutDraft",
    "StarterHoldingTemplate",
    "compute_character_creation_plan_digest",
]
