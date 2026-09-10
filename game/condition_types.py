"""Frozen records for NeuroStudio's existing condition presentation document.

The renderer consumes appearance and transition fields. Relationship metadata
is retained as authoring data; it does not install or simulate game rules.
"""

from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.core.content.identities import ContentRef


Color = Annotated[int, Field(ge=0, le=0xFFFFFF)]
Name = Annotated[str, Field(min_length=1)]
Alpha = Annotated[float, Field(ge=0, le=1)]
Duration = Annotated[float, Field(ge=0)]
Priority = Annotated[int, Field(ge=-1000, le=1000)]
Activity = Literal["idle", "move", "jump", "forced_move", "attack", "cast", "act", "hit"]
EquipmentSlot = Literal[
    "shoes", "legs", "mount", "chest", "belt", "hands", "offhand", "weapon", "weaponGlow",
    "backpack", "head", "beard", "helmet",
]


class _Record(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, allow_inf_nan=False)


class ConditionTrigger(_Record):
    effect: Literal["apply", "remove", "cleanse", "reduce"]
    triggerType: Name
    sourceRef: ContentRef | None
    direct: bool
    evidenceStatus: Name
    evidence: str


class ConditionRelation(_Record):
    relation: Name
    targetRef: ContentRef
    evidenceStatus: Name


class ConditionGrantedAction(_Record):
    actionRef: ContentRef
    evidenceStatus: Name
    notes: str


class ConditionRelationships(_Record):
    incomingTriggers: tuple[ConditionTrigger, ...]
    relatedStates: tuple[ConditionRelation, ...]
    grantsActions: tuple[ConditionGrantedAction, ...]


class ConditionClassification(_Record):
    runtimeRole: Name
    visualIntensity: Name
    presentationDomains: tuple[str, ...]
    visualFamily: Name


class ConditionComposition(_Record):
    group: Name
    exclusiveGroup: Name | None
    priority: Priority
    maxLayers: Annotated[int, Field(ge=1, le=3)]


class ConditionColors(_Record):
    primary: Color
    secondary: Color
    tertiary: Color


class ConditionLayer(_Record):
    id: Name
    assetId: Name
    category: Name
    animation: Name
    fps: Annotated[float, Field(gt=0)]
    attachment: Literal["body", "ground"]
    activeDuring: tuple[Activity, ...]
    priority: Priority
    colors: ConditionColors


class ConditionTransitionEffect(_Record):
    id: Name
    assetId: Name
    category: Name
    animation: Name
    attachment: Literal["body", "ground"]
    priority: Priority
    colors: ConditionColors
    durationMs: Duration


class ConditionBodyColor(_Record):
    tintRgb: Color | None
    saturation: Annotated[float, Field(ge=0, le=2)]
    brightness: Annotated[float, Field(ge=0.25, le=2)]


class ConditionEquipmentModifier(_Record):
    id: Name
    slots: tuple[EquipmentSlot, ...]
    alphaMultiplier: Alpha
    tintRgb: Color | None
    saturation: Annotated[float, Field(ge=0, le=2)]
    brightness: Annotated[float, Field(ge=0.25, le=2)]
    priority: Priority


class ConditionAppearanceLayer(_Record):
    id: Name
    slot: EquipmentSlot
    category: Name
    tint: Color
    tint2: Color | None = None
    tint3: Color | None = None
    priority: Priority


class ConditionPersistent(_Record):
    alphaMultiplier: Alpha
    bodyColor: ConditionBodyColor | None
    equipmentModifiers: tuple[ConditionEquipmentModifier, ...]
    appearanceLayers: tuple[ConditionAppearanceLayer, ...]
    layers: tuple[ConditionLayer, ...]


class ConditionTransition(_Record):
    durationMs: Duration
    feedbackEnabled: bool
    feedbackColor: Color
    effects: tuple[ConditionTransitionEffect, ...]


class ConditionRecipe(_Record):
    definitionRef: ContentRef
    label: Name
    disposition: Literal["authored", "state_only"]
    mediaFailurePolicy: Literal["fail_transaction", "omit_optional_track"]
    relationships: ConditionRelationships
    classification: ConditionClassification
    composition: ConditionComposition
    persistent: ConditionPersistent
    application: ConditionTransition
    removal: ConditionTransition

    @model_validator(mode="after")
    def validate_state_only(self) -> "ConditionRecipe":
        if self.disposition == "state_only":
            persistent = self.persistent
            if (self.classification.visualIntensity not in ("state_only", "icon_only")
                    or any(domain not in ("none", "hud_only") for domain in self.classification.presentationDomains)
                    or persistent.alphaMultiplier != 1 or persistent.bodyColor is not None
                    or persistent.equipmentModifiers or persistent.appearanceLayers or persistent.layers
                    or self.application.effects or self.removal.effects):
                raise ValueError("state_only condition recipes require neutral appearance and HUD/none classification")
        return self


class ConditionFile(_Record):
    schema_id: Literal["neuroclient.conditionPresentationRecipes"] = Field(alias="schema")
    version: Literal[12]
    recipes: tuple[ConditionRecipe, ...]


def load_condition_recipes(path: Path) -> Mapping[str, ConditionRecipe]:
    """Bind current engine behavior IDs to exact source content IDs, not labels."""
    document = ConditionFile.model_validate_json(path.read_text(encoding="utf-8"))
    recipes: dict[str, ConditionRecipe] = {}
    for recipe in document.recipes:
        identity = recipe.definitionRef.content_id
        if identity in recipes:
            raise ValueError(f"ambiguous condition behavior identity: {identity}")
        recipes[identity] = recipe
    return MappingProxyType(recipes)
